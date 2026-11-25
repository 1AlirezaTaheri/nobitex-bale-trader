import asyncio
import json
import logging
import time

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings, StrategyConfig
from app.logging_setup import SafeFormatter
from app.safety import live_startup
from exchange.base import Blocked, Request, Side
from exchange.nobitex import NobitexClient, Spec
from notify import BaleNotifier, NotifyError, Outbox, authorized_command


def update(chat=777, sender=777, command="/pause", **extra):
    return {
        "update_id": 10,
        "message": {
            "chat": {"id": chat, "type": "private"},
            "from": {"id": sender, "is_bot": False},
            "date": 1000,
            "text": command,
            **extra,
        },
    }


def test_whitelisted_private_commands_only():
    assert authorized_command(update(), 777, 1000, 999) == "/pause"
    assert authorized_command(update(chat=888), 777, 1000, 999) is None
    assert authorized_command(update(sender=888), 777, 1000, 999) is None


@pytest.mark.parametrize(
    "extra",
    [
        {"date": 800},
        {"date": 1020},
        {"forward_date": 999},
        {"forward_origin": {}},
        {"sender_chat": {}},
        {"text": "/pause extra"},
        {"chat": {"id": 777, "type": "group"}},
    ],
)
def test_stale_forwarded_group_and_malformed_commands_ignored(extra):
    assert authorized_command(update(**extra), 777, 1000, 999) is None


def test_edited_or_callback_commands_are_not_control_commands():
    assert authorized_command({"edited_message": update()["message"]}, 777, 1000, 999) is None
    assert authorized_command({"callback_query": {}}, 777, 1000, 999) is None


def test_bale_poll_filters_other_chats_and_persists_offset(monkeypatch):
    async def scenario():
        now = int(time.time())
        good, bad = update(command="/stop"), update(chat=888, sender=888)
        good["message"]["date"] = bad["message"]["date"] = now
        bad["update_id"] = 9
        offsets, commands, stop = [], [], asyncio.Event()

        def handler(request):
            assert request.url.host == "tapi.bale.ai"
            assert json.loads(request.content)["timeout"] == 20
            return httpx.Response(200, json={"ok": True, "result": [bad, good]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            notifier = BaleNotifier(http, "test-token", 777)

            async def dispatch(command):
                commands.append(command)
                stop.set()

            await notifier.poll(dispatch, stop, now, 0, offsets.append)
        assert commands == ["/stop"]
        assert offsets == [10, 11]

    asyncio.run(scenario())


def test_bale_http_failure_never_leaks_token():
    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(500))
        ) as http:
            notifier = BaleNotifier(http, "secret-token", 777)
            with pytest.raises(NotifyError) as caught:
                await notifier.send("test")
            assert "secret-token" not in str(caught.value)

    asyncio.run(scenario())


def test_outbox_falls_back_to_console_without_crashing(capsys):
    class Unavailable:
        async def send(self, message):
            raise NotifyError("unavailable")

    async def scenario():
        box = Outbox(Unavailable())
        task = asyncio.create_task(box.work())
        box.emit("order safely simulated")
        await asyncio.wait_for(box.queue.join(), 2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(scenario())
    assert "console fallback" in capsys.readouterr().out


def test_secrets_redacted_and_tracebacks_excluded():
    formatter = SafeFormatter(("hidden-key",))
    record = logging.LogRecord(
        "test",
        logging.ERROR,
        "",
        0,
        "hidden-key https://tapi.bale.ai/botabc:XYZ/sendMessage",
        (),
        None,
    )
    result = formatter.format(record)
    assert "hidden-key" not in result and "abc:XYZ" not in result
    assert json.loads(result)["event"].count("REDACTED") == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"mode": "production"},
        {"max_capital_quote": 0},
        {"max_capital_quote": "NaN"},
        {"bale_chat_id": 777},
        {"bale_bot_token": "example"},
        {"nobitex_public_key": "example"},
    ],
)
def test_bad_settings_fail_closed(overrides):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **overrides)


def test_environment_mode_is_not_silently_ignored(monkeypatch):
    monkeypatch.setenv("MODE", "live")
    assert Settings(_env_file=None).mode == "live"


def test_invalid_periods_and_unknown_yaml_keys_rejected(cfg):
    with pytest.raises(ValidationError):
        StrategyConfig(**{**cfg.model_dump(), "fast": 100})
    with pytest.raises(ValidationError):
        StrategyConfig(**{**cfg.model_dump(), "typo_parameter": 3})


def test_live_always_blocked_with_unverified_contracts(monkeypatch, capsys):
    monkeypatch.setenv("MODE", "live")
    from app.config import ConfigError

    with pytest.raises(ConfigError, match="UNVERIFIED"):
        live_startup(Settings(_env_file=None), Spec.load())
    output = capsys.readouterr().out
    assert "PAPER-TO-LIVE CHECKLIST" in output and "unprotected offline" in output


def test_editing_verification_yaml_cannot_unlock_writes(settings):
    from decimal import Decimal as D

    async def scenario():
        spec = Spec.load()
        spec.raw["verification"] = {k: "VERIFIED" for k in spec.raw["verification"]}
        assert spec.unverified()
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: pytest.fail("No live HTTP"))
        ) as http:
            client = NobitexClient(spec, http, settings)
            with pytest.raises(Blocked):
                await client.place_order("BTC/USDT", Request("abc", Side.BUY, D("0.001"), D(100)))
            with pytest.raises(Blocked):
                await client.cancel_order("BTC/USDT", "1")

    asyncio.run(scenario())
