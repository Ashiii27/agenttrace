"""Every event the recorder writes must match schema/event.schema.json."""

from __future__ import annotations

import json

import jsonschema
from conftest import REPO, read_events

SCHEMA = json.loads((REPO / "schema" / "event.schema.json").read_text("utf-8"))


def test_recorded_events_match_schema(session):
    validator = jsonschema.Draft202012Validator(
        SCHEMA, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
    )
    for ev in read_events(session):
        errors = list(validator.iter_errors(ev))
        assert not errors, (ev["seq"], [e.message for e in errors])


def test_test_vectors_match_schema():
    vectors = json.loads((REPO / "schema" / "test-vectors" / "chain-v1.json").read_text("utf-8"))
    for ev in vectors["events"]:
        jsonschema.validate(ev, SCHEMA)
