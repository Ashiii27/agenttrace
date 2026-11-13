"""AgentTrace: a tamper-evident flight recorder for AI agents."""

from .chain import SCHEMA, event_hash, genesis
from .recorder import Recorder, new_session_id
from .redact import Redactor
from .verify import Report, verify_session

__all__ = [
    "SCHEMA",
    "Recorder",
    "Redactor",
    "Report",
    "event_hash",
    "genesis",
    "new_session_id",
    "verify_session",
]
__version__ = "0.1.0.dev0"
