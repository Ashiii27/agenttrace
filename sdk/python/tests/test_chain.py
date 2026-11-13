from __future__ import annotations

import json

import pytest
from conftest import REPO

from agenttrace.chain import canonical, event_hash, genesis, lowest_trust

VECTORS = json.loads((REPO / "schema" / "test-vectors" / "chain-v1.json").read_text("utf-8"))


@pytest.mark.parametrize("case", VECTORS["canonical"], ids=lambda c: c["jcs"][:30])
def test_canonical_vectors(case):
    assert canonical(case["input"]).decode("utf-8") == case["jcs"]


def test_chain_vectors():
    assert genesis(VECTORS["session_id"]) == VECTORS["genesis"]
    prev = VECTORS["genesis"]
    for ev in VECTORS["events"]:
        assert ev["prev_hash"] == prev
        assert event_hash(ev) == ev["hash"]
        prev = ev["hash"]


def test_genesis_is_bound_to_session():
    assert genesis("s_aaaaaa") != genesis("s_bbbbbb")


@pytest.mark.parametrize("field", ["seq", "type", "trust", "attrs", "inputs", "prev_hash"])
def test_any_field_change_changes_hash(field):
    ev = dict(VECTORS["events"][2])
    before = event_hash(ev)
    replacements = {
        "seq": 99,
        "type": "tool.result",
        "trust": "user",
        "attrs": {},
        "inputs": [],
        "prev_hash": "00" * 32,
    }
    ev[field] = replacements[field]
    assert event_hash(ev) != before


def test_hash_ignores_key_order():
    ev = VECTORS["events"][2]
    assert event_hash(dict(reversed(list(ev.items())))) == ev["hash"]


def test_lowest_trust():
    assert lowest_trust(["system", "user"]) == "user"
    assert lowest_trust(["system", "untrusted", "user"]) == "untrusted"
    assert lowest_trust([]) == "system"
    with pytest.raises(ValueError):
        lowest_trust(["admin"])
