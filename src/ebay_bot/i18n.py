# SPDX-FileCopyrightText: © Tomblarom and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-ArtifactOfProjectHomePage: https://github.com/Tomblarom/ebay-bot/
"""Small message catalog shared by exceptions and logging."""

import json
from importlib.resources import files
from typing import Any

_language = "en"
_catalog: dict[str, str] = {}


def configure(language: str) -> None:
    global _language, _catalog
    _language = language
    _catalog = json.loads(files("ebay_bot.resources").joinpath("translations.de.json").read_text(encoding="utf-8")) if language == "de" else {}


def gettext(message: str) -> str:
    return _catalog.get(message, message)


def pluralize(message: str, number: Any) -> str:
    count = number if isinstance(number, int) else len(number)
    return f"{count} {gettext(message if count == 1 else message + 's')}"
