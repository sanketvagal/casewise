"""What a model would say at each triage step, as the JSON text the scripted fake returns.

Pass these to ``ScriptedGateway(chat_replies={...})`` keyed by step: ``intent``,
``grounding``, ``draft`` and ``review_draft``. A string answers every call to that step;
a list answers successive calls (retries included) in order.
"""

import json


def intent(label: str, confidence: float = 0.9) -> str:
    return json.dumps({"intent": label, "confidence": confidence})


def grounded(reason: str = "The article answers exactly what the ticket asks.") -> str:
    return json.dumps({"answers_ticket": True, "reason": reason})


def not_grounded(reason: str) -> str:
    return json.dumps({"answers_ticket": False, "reason": reason})


def draft(reply: str, cited_article_id: str) -> str:
    return json.dumps({"reply": reply, "cited_article_id": cited_article_id})


def review_draft(text: str) -> str:
    return json.dumps({"draft": text})
