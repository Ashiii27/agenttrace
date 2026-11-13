"""Content-addressed blob store on local disk: blobs/sha256/ab/cdef…"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from .chain import content_ref

_PREFIX = "sha256:"


class BlobStore:
    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)

    def path(self, ref: str) -> Path:
        if not ref.startswith(_PREFIX):
            raise ValueError(f"unsupported content ref: {ref!r}")
        digest = ref[len(_PREFIX) :]
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"malformed content ref: {ref!r}")
        return self.root / "sha256" / digest[:2] / digest[2:]

    def put(self, data: bytes) -> str:
        ref = content_ref(data)
        target = self.path(ref)
        if target.exists():
            return ref
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return ref

    def get(self, ref: str) -> bytes:
        return self.path(ref).read_bytes()

    def check(self, ref: str) -> str | None:
        """None if the blob exists and matches its ref, else "missing" or "tampered"."""
        p = self.path(ref)
        if not p.is_file():
            return "missing"
        if "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest() != ref:
            return "tampered"
        return None
