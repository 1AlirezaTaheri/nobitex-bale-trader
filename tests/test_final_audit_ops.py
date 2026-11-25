from app.final_audit_ops import secret_findings


def test_secret_scan_only_returns_category_counts_never_values():
    synthetic = "BALE_BOT_TOKEN=" + "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcd"
    result = secret_findings(synthetic)
    assert result["credential_assignment"] == 1
    assert result["bot_token_shape"] == 1
    assert "123456789" not in repr(result)


def test_secret_scan_ignores_obvious_placeholders():
    assert secret_findings("BALE_BOT_TOKEN=your_bot_token_here") == {}
    assert secret_findings("NOBITEX_PRIVATE_KEY=example_only_not_real") == {}


def test_blank_credentials_do_not_capture_the_next_line():
    assert secret_findings("BALE_BOT_TOKEN=\nNOBITEX_PUBLIC_KEY=\nNOBITEX_PRIVATE_KEY=\n") == {}
