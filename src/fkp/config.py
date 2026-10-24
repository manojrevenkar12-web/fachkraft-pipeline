"""Loading the YAML configuration. Thresholds, texts and vocabularies live in config/, not in code."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(os.environ.get("FKP_HOME") or Path(__file__).resolve().parents[2])
CONFIG_DIR = Path(os.environ.get("FKP_CONFIG_DIR") or ROOT / "config")
DATA_DIR = ROOT / "data"


class _WordsLoader(yaml.SafeLoader):
    """YAML 1.1 reads unquoted no, yes, on, off as booleans; in word lists they are words."""


_WordsLoader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:bool"] for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_WordsLoader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF"))
_WORD_FILES = {"lexicon", "occupations", "messages", "cities"}


@lru_cache(maxsize=32)
def load(name: str) -> Any:
    text = (CONFIG_DIR / f"{name}.yaml").read_text(encoding="utf-8")
    return yaml.load(text, Loader=_WordsLoader) if name in _WORD_FILES else yaml.safe_load(text)  # noqa: S506 - SafeLoader subclass


def settings() -> dict[str, Any]:
    return load("settings")


def lexicon() -> dict[str, Any]:
    return load("lexicon")


def occupations() -> dict[str, Any]:
    return load("occupations")


def messages() -> dict[str, Any]:
    return load("messages")


def languages() -> list[str]:
    return list(lexicon()["languages"])
