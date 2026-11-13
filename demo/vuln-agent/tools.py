"""Tools for the demo email assistant. Everything is local and fake: no network, no real email.

* ``fetch_url`` serves pages from ``web/<host>/<path>.html`` only.
* ``read_inbox`` reads ``data/inbox.json``.
* ``send_email`` appends to an outbox file — nothing leaves the machine.
"""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from langchain_core.tools import BaseTool, tool

HERE = Path(__file__).parent
WEB_ROOT = HERE / "web"
INBOX = HERE / "data" / "inbox.json"


class _TextExtractor(HTMLParser):
    """Naive text extraction that ignores CSS — exactly like many real agent browsing tools,
    which is why white-on-white text reaches the model."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self.parts.append(" ".join(data.split()))


def _page_path(url: str) -> Path:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"unsupported URL: {url}")
    rel = parsed.path.strip("/") or "index"
    path = (WEB_ROOT / parsed.hostname / rel).with_suffix(".html").resolve()
    if WEB_ROOT.resolve() not in path.parents:
        raise ValueError("path escapes the demo web root")
    return path


def make_tools(outbox: Path) -> list[BaseTool]:
    @tool
    def fetch_url(url: str) -> str:
        """Fetch a web page and return its text."""
        path = _page_path(url)
        if not path.is_file():
            return f"404: {url} not found"
        parser = _TextExtractor()
        parser.feed(path.read_text(encoding="utf-8"))
        return "\n".join(parser.parts)

    @tool
    def read_inbox(limit: int = 5) -> str:
        """Return the most recent emails in the user's inbox as JSON."""
        return json.dumps(json.loads(INBOX.read_text(encoding="utf-8"))[:limit])

    @tool
    def send_email(to: str, subject: str, body: str) -> str:
        """Send an email on the user's behalf."""
        outbox.parent.mkdir(parents=True, exist_ok=True)
        with outbox.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"to": to, "subject": subject, "body": body}) + "\n")
        return f"sent to {to}"

    return [fetch_url, read_inbox, send_email]
