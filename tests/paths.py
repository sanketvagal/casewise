"""Paths to the committed files some tests run against."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIXTURE_KB = ROOT / "eval" / "fixtures-kb"
"""The three hand-written articles the issue 01-04 tests and fixtures use."""

RULES = ROOT / "safety_rules.yaml"
