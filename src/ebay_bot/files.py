# SPDX-FileCopyrightText: © Sebastian Thomschke and contributors
# SPDX-FileCopyrightText: © Tomblarom and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-ArtifactOfProjectHomePage: https://github.com/Tomblarom/ebay-bot/
"""Roundtrip YAML/JSON file IO for configs and sources.

YAML is loaded in roundtrip mode, so comments survive a load/modify/save
cycle untouched. Paths are NFC-normalized for cross-platform consistency.
"""

__all__ = ["load_dict", "load_dict_if_exists", "save_dict"]

import json
import os
import unicodedata
from pathlib import Path
from typing import Any, Final

from ruamel.yaml import YAML

from ebay_bot.i18n import gettext as _
from ebay_bot.loggers import Logger, get_logger

LOG: Final[Logger] = get_logger(__name__)

SUPPORTED_SUFFIXES: Final[frozenset[str]] = frozenset({".json", ".yaml", ".yml"})


def load_dict(filepath: str, content_label: str = "") -> dict[str, Any]:
    """:raises FileNotFoundError: if the file does not exist."""
    data = load_dict_if_exists(filepath, content_label)
    if data is None:
        raise FileNotFoundError(filepath)
    return data


def load_dict_if_exists(filepath: str, content_label: str = "") -> dict[str, Any] | None:
    where = f"{content_label} from " if content_label else ""
    LOG.debug("Loading %s[%s]...", where, os.path.abspath(filepath))
    _require_supported_suffix(filepath)
    if not os.path.exists(filepath):
        return None
    with open(filepath, encoding="utf-8") as file:
        if filepath.endswith(".json"):
            data = json.load(file)
        else:
            data = YAML().load(file)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(_('File "%s" must contain a mapping at the top level') % filepath)
    return data


def save_dict(filepath: str | Path, content: dict[str, Any], *, header: str | None = None) -> None:
    filepath = Path(unicodedata.normalize("NFC", str(filepath)))
    filepath.parent.mkdir(parents=True, exist_ok=True)
    LOG.debug("Saving [%s]...", filepath)
    with open(filepath, "w", encoding="utf-8") as file:
        if header:
            file.write(header)
            file.write("\n")
        if filepath.suffix == ".json":
            file.write(json.dumps(content, indent=2, ensure_ascii=False))
        else:
            _configure_yaml().dump(content, file)


def _require_supported_suffix(filepath: str) -> None:
    _root, suffix = os.path.splitext(filepath)
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(_('Unsupported file type. The filename "%s" must end with *.json, *.yaml, or *.yml') % filepath)


def _configure_yaml() -> YAML:
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.representer.add_representer(
        str,  # use YAML | block style for multi-line strings
        lambda dumper, data: dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|" if "\n" in data else None),
    )
    yaml.allow_duplicate_keys = False
    yaml.explicit_start = False
    return yaml
