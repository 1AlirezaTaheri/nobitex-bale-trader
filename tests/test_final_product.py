import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import time
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from app import bale_setup, doctor, forward_report, forward_shadow, product_ops, product_shadow
from app.product_ops import BaleOptions
from app.product_weekly import deliver, persian_summary
from notify import NotifyError
from notify.product import Delivery, ProductBale, diagnostic, owner_message, shadow_command


def options(**kwargs):
    return BaleOptions(
        _env_file=None, bale_bot_token="synthetic-token-only", bale_chat_id=777, **kwargs
    )


def update(text="/stop", timestamp=1000, **extra):
    return {
        "update_id": 1,
        "message": {
            "date": timestamp,
            "text": text,
            "chat": {"id": 777, "type": "private"},
            "from": {"id": 777, "is_bot": False},
            **extra,
        },
    }


@pytest.mark.parametrize("command", ["/status", "/help", "/pause", "/resume", "/stop", "/report"])
def test_product_command_allowlist(command):
    assert shadow_command(update(command), 777, 1000, 999) == command


@pytest.mark.parametrize(
    "change",
    [
        {"forward_from": {}},
        {"forward_from_chat": {}},
        {"forward_origin": {}},
        {"forward_date": 998},
        {"edit_date": 1000},
        {"sender_chat": {}},
        {"date": 800},
        {"date": 1006},
        {"text": "/stop extra"},
        {"chat": {"id": 888, "type": "private"}},
        {"from": {"id": 888, "is_bot": False}},
        {"chat": {"id": 777, "type": "group"}},
        {"from": {"id": 777, "is_bot": True}},
    ],
)
def test_product_rejects_stale_forwarded_unknown_without_response(change):
    assert shadow_command(update(**change), 777, 1000, 999) is None


def test_owner_challenge_exact_and_fresh():
    assert owner_message(update("/setup nonce"), 777, 1000, 999, "/setup nonce")
    assert not owner_message(update("/setup old"), 777, 1000, 999, "/setup nonce")
    assert not owner_message(update("/setup nonce"), 777, 1000, 1001, "/setup nonce")
    assert shadow_command(None, 777, 1000, 999) is None


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_product_http_failures_redacted(status):
    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(status))
        ) as http:
            bot = ProductBale(http, "synthetic-secret", 777)
            with pytest.raises(NotifyError) as caught:
                await bot.send("safe")
            assert "synthetic-secret" not in str(caught.value)
            assert "777" not in diagnostic(caught.value)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"ok": False, "description": "synthetic-secret"},
        {"ok": True},
        {"ok": True, "result": {}},
    ],
)
def test_malformed_ack_does_not_create_user_receipt(tmp_path, payload):
    async def scenario():
        def handler(request):
            body = (
                {"ok": True, "result": {"is_bot": True}}
                if request.url.path.endswith("getMe")
                else payload
            )
            return httpx.Response(200, json=body)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(NotifyError):
                await bale_setup.setup(options(), False, http, receipt_path=tmp_path / "receipt")
        assert not (tmp_path / "receipt").exists()

    asyncio.run(scenario())


def test_explicit_user_test_receipt_bound_to_current_configuration(tmp_path, capsys):
    async def scenario():
        calls = []

        def handler(request):
            calls.append(request.url.path.rsplit("/", 1)[-1])
            result = {"is_bot": True} if calls[-1] == "getMe" else {"message_id": 1}
            return httpx.Response(200, json={"ok": True, "result": result})

        receipt = tmp_path / "receipt"
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            assert await bale_setup.setup(options(), False, http, receipt_path=receipt) == 0
        assert calls == ["getMe", "sendMessage"]
        assert product_ops.delivery_verified(options(), receipt)
        assert not product_ops.delivery_verified(BaleOptions(_env_file=None), receipt)
        assert "synthetic-token-only" not in receipt.read_text()
        assert "777" not in receipt.read_text()

    asyncio.run(scenario())
    text = capsys.readouterr().out
    assert "synthetic-token-only" not in text and "777" not in text


def test_find_chat_uses_challenge_without_printing_any_identity(tmp_path, monkeypatch, capsys):
    env = tmp_path / ".env"
    env.write_text(
        "MODE=paper\nBALE_BOT_TOKEN=synthetic-token-only\nBALE_CHAT_ID=\n", encoding="utf-8"
    )
    monkeypatch.setattr(bale_setup.secrets, "token_urlsafe", lambda _: "fresh-nonce")

    async def scenario():
        def handler(request):
            method = request.url.path.rsplit("/", 1)[-1]
            assert method in {"getMe", "getWebhookInfo", "getUpdates"}
            result = (
                {"is_bot": True}
                if method == "getMe"
                else {"url": ""}
                if method == "getWebhookInfo"
                else [
                    {"update_id": 0, "message": {"chat": {"id": 123456789}}},
                    update("/setup fresh-nonce", int(time.time())),
                ]
            )
            return httpx.Response(200, json={"ok": True, "result": result})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            assert await bale_setup.setup(options(), True, http, env_path=env, duration=1) == 0
        assert BaleOptions(_env_file=env).bale_chat_id == 777

    asyncio.run(scenario())
    text = capsys.readouterr().out
    assert all(secret not in text for secret in ("777", "123456789", "synthetic-token-only"))


def test_active_webhook_is_never_modified(tmp_path):
    async def scenario():
        calls = []

        def handler(request):
            method = request.url.path.rsplit("/", 1)[-1]
            calls.append(method)
            result = {"is_bot": True} if method == "getMe" else {"url": "https://example.invalid"}
            return httpx.Response(200, json={"ok": True, "result": result})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            with pytest.raises(ValueError, match="Webhook"):
                await bale_setup.setup(options(), True, http)
        assert calls == ["getMe", "getWebhookInfo"]

    asyncio.run(scenario())


def test_timeout_and_photo_error_fallback_never_expose_request(tmp_path, capsys):
    async def scenario():
        def handler(request):
            raise httpx.ReadTimeout("synthetic-secret chat=777", request=request)

        photo = tmp_path / "weekly.png"
        photo.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            bot = ProductBale(http, "synthetic-secret", 777)
            with pytest.raises(NotifyError) as caught:
                await bot.photo(photo, "safe")
            assert "synthetic-secret" not in str(caught.value)
            box = Delivery(bot)
            worker = asyncio.create_task(box.work())
            box.emit("safe local report", photo)
            await box.close(worker)

    asyncio.run(scenario())
    text = capsys.readouterr().out
    assert "safe local report" in text and "synthetic-secret" not in text and "777" not in text


def test_photo_uses_official_multipart_endpoint(tmp_path):
    async def scenario():
        path = tmp_path / "weekly.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\nfixture")

        def handler(request):
            assert request.url.host == "tapi.bale.ai" and request.url.path.endswith("/sendPhoto")
            assert "multipart/form-data" in request.headers["content-type"]
            assert b'name="photo"' in request.content
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            await ProductBale(http, "synthetic-secret", 777).photo(path, "safe")

    asyncio.run(scenario())


def test_weekly_without_receipt_never_contacts_bale(tmp_path, monkeypatch):
    summary = {}

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: pytest.fail("No Bale"))
        ) as http:
            monkeypatch.setattr("app.product_weekly.persian_summary", lambda _: "safe summary")
            await deliver(summary, tmp_path, http, options(), tmp_path / "missing")

    asyncio.run(scenario())


def test_mutable_atomic_failure_preserves_original(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_bytes(b"old")
    monkeypatch.setattr(
        product_ops.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("failure"))
    )
    with pytest.raises(OSError):
        product_ops.atomic_json(path, {"new": True})
    assert path.read_bytes() == b"old"
    assert not list(tmp_path.glob(".pending_*"))


def test_immutable_atomic_publish_failure_leaves_no_partial_snapshot(tmp_path, monkeypatch):
    path = tmp_path / "snapshot.json"
    monkeypatch.setattr(
        forward_shadow.os, "link", lambda *_: (_ for _ in ()).throw(OSError("failure"))
    )
    with pytest.raises(OSError):
        forward_shadow.exclusive_json(path, {"new": True})
    assert not path.exists() and not list(tmp_path.glob(".pending_*"))


def test_disk_corrupt_database_and_clock_discontinuity_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(product_ops.shutil, "disk_usage", lambda _: SimpleNamespace(free=1))
    with pytest.raises(ValueError, match="disk"):
        product_ops.disk_check(tmp_path)
    path = tmp_path / "broken.db"
    path.write_bytes(b"broken")
    with pytest.raises(sqlite3.DatabaseError):
        product_ops.database_check(path)
    with pytest.raises(ValueError, match="Clock"):
        product_ops.clock_check(100, 10, 99, 11)
    with pytest.raises(ValueError, match="Clock"):
        product_ops.clock_check(100, 10, 200, 11)
    product_ops.clock_check(100, 10, 101, 11)


def test_pause_resume_stop_only_touch_experiment_controls(tmp_path):
    async def scenario():
        box = Delivery()
        controls = product_shadow.Controls(tmp_path, box)
        await controls.dispatch("/pause")
        assert (tmp_path / "PAUSE").exists()
        await controls.dispatch("/resume")
        assert not (tmp_path / "PAUSE").exists()
        await controls.dispatch("/stop")
        assert (tmp_path / "KILL").exists()
        assert sorted(p.name for p in tmp_path.iterdir()) == ["KILL"]

    asyncio.run(scenario())


def test_rotated_log_redacts_configuration(tmp_path):
    logger = product_ops.product_logger(tmp_path, options())
    logger.info("synthetic-token-only chat=777")
    for handler in logger.handlers[:]:
        assert handler.maxBytes == 1_000_000 and handler.backupCount == 3
        handler.close()
        logger.removeHandler(handler)
    text = (tmp_path / "logs/operations.jsonl").read_text()
    assert "synthetic-token-only" not in text and "777" not in text


def test_doctor_is_offline_and_redacts_invalid_configuration(tmp_path, monkeypatch):
    monkeypatch.setattr(forward_shadow, "PRODUCT_BASE", tmp_path)
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *_a, **_k: pytest.fail("doctor must be offline")
    )
    monkeypatch.setattr(doctor, "load", lambda: (_ for _ in ()).throw(ConfigFailure()))
    result = doctor.diagnose(tmp_path / "root")
    assert result["offline"] and result["failed"] >= 1
    assert "synthetic-secret" not in json.dumps(result)


class ConfigFailure(ValueError):
    def __str__(self):
        return "synthetic-secret"


@pytest.mark.parametrize("value", ["live", "LIVE", "production"])
def test_product_options_refuse_live(value):
    with pytest.raises(ValidationError):
        BaleOptions(_env_file=None, mode=value)


def test_product_live_refusal_precedes_network(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", lambda *_a, **_k: pytest.fail("No network"))
    with pytest.raises(ValueError):
        asyncio.run(
            product_shadow.run(
                SimpleNamespace(mode="live", root=tmp_path, max_seconds=1, bale=False)
            )
        )


def test_12_month_checkpoint_and_risk_comparison_no_zero_data_winner(tmp_path, monkeypatch):
    monkeypatch.setattr(forward_shadow, "PRODUCT_BASE", tmp_path)
    summary, _ = forward_report.summarize(tmp_path / "root", as_of=1800000000)
    checkpoint = summary["checkpoints"]["12"]
    assert checkpoint["minimum_observed_intervals"] == 320
    assert checkpoint["candidates"]["A"]["status"] == "PENDING"
    risk = summary["matched_risk_constant_mix"]
    assert risk["status"] == "INSUFFICIENT_OBSERVATIONS"
    assert risk["candidates"]["A"]["closest_realized_dd_descriptive_only"] is None
    assert len(risk["candidates"]["D"]["comparisons"]) == 3
    assert "Performance" not in persian_summary(summary)


def test_matched_risk_uses_all_registered_mixes_with_hindsight_label():
    accounts = {name: {"net_return": 0.1, "max_drawdown": -0.1} for name in forward_shadow.NAMES}
    summary = {"accounts": accounts, "observed_intervals": 20}
    records = [
        {
            "payload": {
                "returns": {
                    name: {"interval_observed": True, "clean_observed_return": 0.001 * (i % 3)}
                    for name in accounts
                }
            }
        }
        for i in range(20)
    ]
    result = forward_report.risk_comparisons(summary, records)
    assert "hindsight" in result["method"]
    assert result["candidates"]["A"]["comparisons"][0]["clean_annualized_volatility"]["A"] > 0
    assert set(accounts) == set(forward_shadow.NAMES)


def test_forward_pause_guard_skips_boundary_fetch(tmp_path, monkeypatch):
    root = tmp_path / "shadow"
    root.mkdir()
    (root / "PAUSE").touch()
    monkeypatch.setattr(forward_shadow, "PRODUCT_BASE", tmp_path)
    monkeypatch.setattr(forward_shadow, "registration", lambda _: {"not_before": 0})

    class Market:
        def __init__(self, *args):
            pass

        async def get_fees(self, *_):
            return 0.0025

        async def get_candles(self, *_):
            pytest.fail("Paused recorder must not fetch a fill boundary")

    monkeypatch.setattr(forward_shadow, "NobitexClient", Market)
    monkeypatch.setattr(forward_shadow, "boundary", lambda now, *_: now)
    assert (
        asyncio.run(forward_shadow.run(SimpleNamespace(mode="shadow", root=root, max_seconds=0.02)))
        == 0
    )
    assert not list((root / "snapshots").glob("*.json"))


def test_poll_persists_offset_and_ignores_unknown_sender(tmp_path):
    async def scenario():
        stop = asyncio.Event()
        now = int(time.time())
        commands = []

        class Bot:
            chat_id = 777

            async def call(self, *_):
                good = update("/stop", now)
                good["update_id"] = 2
                return [update("/pause", now, chat={"id": 888, "type": "private"}), good]

        class Control:
            root = tmp_path
            delivery = Delivery()

            async def dispatch(self, command):
                commands.append(command)
                stop.set()

        await product_shadow.poll(Bot(), Control(), stop, now)
        assert commands == ["/stop"]
        assert json.loads((tmp_path / "bale_offset.json").read_bytes())["offset"] == 3

    asyncio.run(scenario())


def test_broken_offset_disables_controls_with_visible_safe_alert(tmp_path):
    (tmp_path / "bale_offset.json").write_bytes(b"broken")
    box = Delivery()
    controls = product_shadow.Controls(tmp_path, box)
    asyncio.run(product_shadow.poll(None, controls, asyncio.Event(), 0))
    assert box.queue.qsize() == 1


def test_product_orchestration_without_receipt_is_console_only(tmp_path, monkeypatch):
    root = tmp_path / "shadow"
    monkeypatch.setattr(forward_shadow, "PRODUCT_BASE", tmp_path)
    monkeypatch.setattr(product_shadow, "PRODUCT", tmp_path)
    monkeypatch.setattr(product_shadow, "startup_checks", lambda _: {})
    monkeypatch.setattr(product_shadow, "recording_options", lambda: options())
    monkeypatch.setattr(product_shadow, "delivery_verified", lambda _: False)
    monkeypatch.setattr(
        httpx.AsyncClient, "post", lambda *_a, **_k: pytest.fail("No real Bale HTTP")
    )

    async def recorder(args):
        await asyncio.sleep(0.01)
        return 0

    monkeypatch.setattr(forward_shadow, "run", recorder)
    assert (
        asyncio.run(
            product_shadow.run(
                SimpleNamespace(root=root, mode="shadow", max_seconds=0.01, bale=True)
            )
        )
        == 0
    )
    assert (root / "clock.json").exists()


def test_critical_monitor_failure_cancels_recorder(tmp_path, monkeypatch):
    root = tmp_path / "shadow"
    monkeypatch.setattr(forward_shadow, "PRODUCT_BASE", tmp_path)
    monkeypatch.setattr(product_shadow, "PRODUCT", tmp_path)
    monkeypatch.setattr(product_shadow, "startup_checks", lambda _: {})
    monkeypatch.setattr(product_shadow, "recording_options", lambda: options())
    stopped = []

    async def recorder(_):
        try:
            await asyncio.Event().wait()
        finally:
            stopped.append(True)

    async def monitor(*_):
        raise ValueError("Injected clock failure")

    monkeypatch.setattr(forward_shadow, "run", recorder)
    monkeypatch.setattr(product_shadow, "monitor", monitor)
    with pytest.raises(ValueError, match="clock"):
        asyncio.run(
            product_shadow.run(SimpleNamespace(root=root, mode="shadow", max_seconds=0, bale=False))
        )
    assert stopped == [True]


def test_12_month_gate_uses_timely_intervals_and_never_late_rescue(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    (root / "configuration.json").write_text('{"test_fixture": true}')
    monkeypatch.setattr(forward_shadow, "PRODUCT_BASE", tmp_path)
    first = 1735689600
    records = []
    for i in range(367):
        accounts = {
            name: {"equity": 110, "costs": 1, "exposure": 0.25, "trade_legs": 1, "round_trips": 0}
            for name in forward_shadow.NAMES
        }
        records.append(
            {
                "hash": "test",
                "payload": {
                    "timestamp": first + i * 86400,
                    "accounts": accounts,
                    "interrupted": False,
                    "missing_boundaries": [],
                    "returns": {
                        name: {"interval_observed": i > 0, "clean_observed_return": 0.0}
                        for name in accounts
                    },
                },
            }
        )
    monkeypatch.setattr(forward_report, "load_chain", lambda *_: records)
    due = forward_report.months_after(first, 12)
    summary, _ = forward_report.summarize(root, due + 86400)
    check = summary["checkpoints"]["12"]["candidates"]["A"]
    assert check["observed_intervals"] == 365
    assert check["status"] == "PASS_CONTINUE_OBSERVING_ONLY"
    for record in records[:60]:
        record["payload"]["returns"]["A"]["interval_observed"] = False
    summary, _ = forward_report.summarize(root, due + 86400)
    assert summary["checkpoints"]["12"]["candidates"]["A"]["status"] == "FAIL_NOT_VALIDATED"


@pytest.mark.parametrize("mode", ["paper", "live"])
def test_invalid_optional_bale_falls_back_but_live_still_refuses(monkeypatch, capsys, mode):
    real_options = BaleOptions

    def loader(**kwargs):
        if kwargs:
            return real_options(**kwargs)
        return real_options(_env_file=None, mode=mode, bale_chat_id="synthetic-invalid-owner")

    monkeypatch.setattr(product_ops, "BaleOptions", loader)
    if mode == "live":
        with pytest.raises(ValueError, match="PAPER"):
            product_ops.recording_options()
    else:
        result = product_ops.recording_options()
        assert result.bale_bot_token is None and result.bale_chat_id is None
    assert "synthetic-invalid-owner" not in capsys.readouterr().out


@pytest.mark.parametrize("payload", [[], None, 1, "bad", {"user_test": True}])
def test_malformed_receipt_is_console_only(tmp_path, payload):
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    assert not product_ops.delivery_verified(options(), receipt)


@pytest.mark.parametrize(
    "module,args",
    [
        ("app.product_shadow", ["--mode", "live"]),
        ("app.product_weekly", []),
        ("app.bale_setup", ["--test"]),
        ("app.doctor", []),
    ],
)
def test_persian_cli_safe_under_forced_ascii_pipes(module, args):
    script = """
import importlib, socket, sys
def blocked(*args, **kwargs):
    raise AssertionError('Network forbidden in subprocess regression')
original_connect = socket.socket.connect
def connect(sock, address):
    if isinstance(address, tuple) and address[0] in {'127.0.0.1', '::1'}:
        return original_connect(sock, address)
    return blocked(sock, address)
socket.socket.connect = connect
socket.socket.connect_ex = blocked
socket.create_connection = blocked
module = importlib.import_module(sys.argv[1])
sys.argv = [sys.argv[1], *sys.argv[2:]]
raise SystemExit(module.main())
"""
    env = {**os.environ, "MODE": "live", "PYTHONIOENCODING": "ascii", "PYTHONUTF8": "0"}
    result = subprocess.run(
        [sys.executable, "-c", script, module, *args], capture_output=True, env=env, timeout=20
    )
    assert result.returncode == 2
    assert b"UnicodeEncodeError" not in result.stderr
    assert (
        "خطا" in result.stdout.decode("utf-8")
        or "مسدود" in result.stdout.decode("utf-8")
        or "رد" in result.stdout.decode("utf-8")
        or "گزارش" in result.stdout.decode("utf-8")
    )


def test_changed_product_fingerprint_refused_before_network_or_mutation(tmp_path, monkeypatch):
    root = tmp_path / "old"
    root.mkdir()
    monkeypatch.setattr(forward_shadow, "PRODUCT_BASE", tmp_path)
    monkeypatch.setattr(product_shadow, "PRODUCT", tmp_path)
    monkeypatch.setattr(forward_shadow, "registration", lambda _: {"not_before": 0})
    config = forward_shadow.config_for({"not_before": 0}, 0.0025)
    config["source_hashes"]["app/product_shadow.py"] = "old"
    (root / "configuration.json").write_bytes(forward_shadow.canonical(config) + b"\n")
    (root / "shadow.db").write_bytes(b"pre-existing database must not even be opened")
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    monkeypatch.setattr(product_shadow, "recording_options", options)
    monkeypatch.setattr(
        product_ops,
        "database_check",
        lambda *_: pytest.fail("Database opened before fingerprint refusal"),
    )
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *_a, **_k: pytest.fail("No network before refusal")
    )
    with pytest.raises(ValueError, match="fingerprint"):
        asyncio.run(
            product_shadow.run(SimpleNamespace(root=root, mode="shadow", max_seconds=1, bale=False))
        )
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}


def test_failing_bale_does_not_stop_recorder(tmp_path, monkeypatch, capsys):
    root = tmp_path / "root"
    monkeypatch.setattr(forward_shadow, "PRODUCT_BASE", tmp_path)
    monkeypatch.setattr(product_shadow, "PRODUCT", tmp_path)
    monkeypatch.setattr(product_shadow, "startup_checks", lambda _: {})
    monkeypatch.setattr(product_shadow, "recording_options", options)
    monkeypatch.setattr(product_shadow, "delivery_verified", lambda _: True)
    completed = []

    class Bot:
        chat_id = 777

        def __init__(self, *_):
            pass

        async def call(self, method, *_):
            return {"url": ""} if method == "getWebhookInfo" else []

        async def send(self, _):
            raise NotifyError("synthetic-secret 777")

    async def recorder(_):
        await asyncio.sleep(0.02)
        completed.append(True)
        return 0

    monkeypatch.setattr(product_shadow, "ProductBale", Bot)
    monkeypatch.setattr(forward_shadow, "run", recorder)
    assert (
        asyncio.run(
            product_shadow.run(SimpleNamespace(root=root, mode="shadow", max_seconds=1, bale=True))
        )
        == 0
    )
    assert completed == [True]
    text = capsys.readouterr().out
    assert "synthetic-secret" not in text and "777" not in text
