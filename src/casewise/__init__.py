"""casewise: safety-first LLM triage for clinical SaaS support."""

from casewise.cache import CachedGateway, CacheMiss
from casewise.config import Settings
from casewise.gateway import ChatResult, ModelGateway, ScriptedGateway
from casewise.live import LiveGateway, build_gateway
from casewise.triage import Ticket, TriageResult, triage

__all__ = [
    "CacheMiss",
    "CachedGateway",
    "ChatResult",
    "LiveGateway",
    "ModelGateway",
    "ScriptedGateway",
    "Settings",
    "Ticket",
    "TriageResult",
    "build_gateway",
    "triage",
]
