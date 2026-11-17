"""Deterministic safety rules, loaded from a human-readable YAML file."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    phrases: list[str] = Field(min_length=1)
    requester_roles: list[str] | None = None
    next_step: str


@dataclass(frozen=True)
class RuleMatch:
    rule: Rule
    phrase: str
    """The phrase from the rules file that matched."""


def load_rules(path: Path) -> list[Rule]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    rules = [Rule.model_validate(entry) for entry in raw.get("rules", [])]
    ids = [rule.id for rule in rules]
    duplicates = sorted({rule_id for rule_id in ids if ids.count(rule_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate safety rule ids in {path}: {', '.join(duplicates)}")
    return rules


def matching_rules(rules: list[Rule], text: str, requester_role: str | None) -> list[RuleMatch]:
    """Return a match for every rule that fires on ``text``, in rules-file order."""
    text = _normalise(text)
    role = _normalise(requester_role or "")
    matches = []
    for rule in rules:
        if rule.requester_roles is not None and role not in map(_normalise, rule.requester_roles):
            continue
        phrase = next((p for p in rule.phrases if _phrase_pattern(p).search(text)), None)
        if phrase is not None:
            matches.append(RuleMatch(rule=rule, phrase=phrase))
    return matches


def _normalise(text: str) -> str:
    text = text.lower().replace("’", "'").replace("‘", "'")
    return " ".join(text.split())


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    phrase = _normalise(phrase)
    prefix = phrase.endswith("*")
    body = re.escape(phrase.rstrip("*"))
    return re.compile(rf"(?<!\w){body}" + (r"\w*" if prefix else r"(?!\w)"))
