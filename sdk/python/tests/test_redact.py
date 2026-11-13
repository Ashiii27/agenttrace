from __future__ import annotations

import pytest

from agenttrace import Recorder
from agenttrace.redact import Redactor

# Fake values shaped like real secrets. None of them are live credentials.
SAMPLES = {
    "aws_access_key": "AKIAIOSFODNN7EXAMPLE",
    "github_token": "ghp_" + "a1B2c3D4e5" * 4,
    "anthropic_key": "sk-ant-api03-" + "x" * 30,
    "openai_key": "sk-proj-" + "Y" * 30,
    "slack_token": "xoxb-1234567890-abcdefghij",
    "google_api_key": "AIza" + "b" * 35,
    "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTYifQ.c2lnbmF0dXJlLXZhbHVl",
    "bearer_token": "Bearer abcdefghijklmnopqrstuvwxyz012345",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----",
}


@pytest.mark.parametrize("kind", sorted(SAMPLES))
def test_each_pattern_is_redacted(kind):
    out = Redactor(b"k" * 32).redact_text(f"value: {SAMPLES[kind]} end")
    assert SAMPLES[kind] not in out
    assert f"[REDACTED:{kind}:" in out
    assert out.endswith(" end")


def test_markers_are_stable_in_a_session_and_unlinkable_across_sessions():
    secret = SAMPLES["aws_access_key"]
    a = Redactor(b"a" * 32)
    assert a.redact_text(secret) == a.redact_text(secret)
    assert a.redact_text(secret) != Redactor(b"b" * 32).redact_text(secret)


def test_redacts_nested_values_and_keys():
    r = Redactor(b"k" * 32)
    out = r.redact({"args": [{"token": SAMPLES["github_token"]}], SAMPLES["openai_key"]: 1})
    assert SAMPLES["github_token"] not in str(out)
    assert SAMPLES["openai_key"] not in str(out)


def test_plain_text_is_untouched():
    text = "Invoice INV-2026-1187, amount due 14,250.00 EUR, see skeleton-key docs"
    assert Redactor().redact_text(text) == text


def test_secrets_never_reach_disk(tmp_path):
    secret = SAMPLES["aws_access_key"]
    with Recorder(tmp_path) as rec:
        rec.user_input(f"my key is {secret}")
        rec.emit("tool.call", attrs={"args": {"key": secret}}, trust="untrusted")
    for path in rec.dir.rglob("*"):
        if path.is_file():
            assert secret.encode() not in path.read_bytes(), path
