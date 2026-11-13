"""Local recorder: writes a hash-chained ``events.jsonl`` plus a content-addressed blob store.

Session layout::

    <root>/<session_id>/events.jsonl
    <root>/<session_id>/blobs/sha256/ab/cdef…
"""

from __future__ import annotations

import json
import os
import secrets
import threading
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .blobs import BlobStore
from .chain import EVENT_TYPES, SCHEMA, canonical, content_ref, event_hash, genesis, lowest_trust
from .redact import Redactor


def new_session_id() -> str:
    return "s_" + secrets.token_hex(8)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _json_safe(obj: Any) -> Any:
    """Round-trip through json so arbitrary objects become plain JSON values."""
    return json.loads(json.dumps(obj, default=str))


class Recorder:
    """Records one agent session. Thread-safe; use as a context manager.

    >>> with Recorder("runs", attrs={"agent": "demo"}) as rec:
    ...     rec.user_input("hello")
    """

    def __init__(
        self,
        root: str | os.PathLike[str],
        session_id: str | None = None,
        *,
        actor: str = "agent",
        attrs: dict[str, Any] | None = None,
        redactor: Redactor | None = None,
        fsync: bool = False,
    ) -> None:
        self.session_id = session_id or new_session_id()
        self.dir = Path(root) / self.session_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.dir / "events.jsonl"
        if self.events_path.exists():
            raise FileExistsError(f"session already recorded: {self.events_path}")
        self.blobs = BlobStore(self.dir / "blobs")
        self.actor = actor
        self.redactor = redactor or Redactor()
        self._fsync = fsync
        self._lock = threading.RLock()
        self._seq = 0
        self._prev = genesis(self.session_id)
        self._trust: dict[str, str] = {}
        self._file = open(self.events_path, "a", encoding="utf-8", newline="\n")  # noqa: SIM115
        self._closed = False
        self.emit("session.start", attrs=attrs or {}, trust="system")

    # -- segments ---------------------------------------------------------------------------

    def _encode(self, obj: Any) -> bytes:
        return canonical(self.redactor.redact(_json_safe(obj)))

    def ref_for(self, obj: Any) -> str:
        """The content ref `obj` would get, without storing it."""
        return content_ref(self._encode(obj))

    def trust_of(self, ref: str) -> str | None:
        return self._trust.get(ref)

    def put_segment(self, obj: Any, trust: str) -> str:
        """Store a segment and return its ref. Repeated content keeps its lowest trust label."""
        with self._lock:
            ref = self.blobs.put(self._encode(obj))
            known = self._trust.get(ref)
            self._trust[ref] = lowest_trust([trust, known] if known else [trust])
            return ref

    # -- events -----------------------------------------------------------------------------

    def emit(
        self,
        type: str,  # noqa: A002 - matches the schema field name
        *,
        content: Any = None,
        content_trust: str | None = None,
        inputs: Iterable[str] = (),
        trust: str | None = None,
        attrs: dict[str, Any] | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Append one event. `trust` defaults to the lowest trust among `inputs`."""
        if type not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {type!r}")
        with self._lock:
            if self._closed:
                raise RuntimeError("recorder is closed")
            inputs = list(dict.fromkeys(inputs))  # dedupe, keep order
            input_trust = [self._trust.get(r, "untrusted") for r in inputs]
            if trust is None:
                trust = lowest_trust(input_trust)
            event: dict[str, Any] = {
                "schema": SCHEMA,
                "session_id": self.session_id,
                "seq": self._seq,
                "ts": _utc_now(),
                "type": type,
                "actor": actor or self.actor,
                "inputs": inputs,
                "trust": trust,
                "attrs": self.redactor.redact(_json_safe(attrs or {})),
                "prev_hash": self._prev,
            }
            if content is not None:
                event["content_ref"] = self.put_segment(content, content_trust or trust)
            event["hash"] = event_hash(event)
            self._file.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            self._file.flush()
            if self._fsync:
                os.fsync(self._file.fileno())
            self._seq += 1
            self._prev = event["hash"]
            return event

    def user_input(self, text: str, **attrs: Any) -> dict[str, Any]:
        from .segments import message_segment

        return self.emit(
            "user.input", content=message_segment("user", text), trust="user", attrs=attrs
        )

    def close(self, **attrs: Any) -> None:
        with self._lock:
            if self._closed:
                return
            self.emit("session.end", attrs=attrs, trust="system")
            self._closed = True
            self._file.close()

    def __enter__(self) -> Recorder:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close(status="error" if exc_type else "ok")
