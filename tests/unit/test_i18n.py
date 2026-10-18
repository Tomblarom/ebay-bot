# SPDX-FileCopyrightText: © Tomblarom and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-ArtifactOfProjectHomePage: https://github.com/Tomblarom/ebay-bot/
"""Translation coverage and the independent package boundary."""

import ast
import json
from importlib.resources import files
from pathlib import Path

import pytest

from ebay_bot import cli, i18n


def test_runtime_templates_have_german_translations() -> None:
    root = Path(str(files("ebay_bot")))
    catalog = json.loads((root / "resources/translations.de.json").read_text(encoding="utf-8"))
    missing: set[str] = set()
    for source in root.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            explicit = isinstance(target, ast.Name) and target.id == "_"
            logging = (
                isinstance(target, ast.Attribute)
                and target.attr in {"info", "warning", "error", "debug", "exception"}
                and isinstance(target.value, ast.Name)
                and target.value.id == "LOG"
            )
            if (explicit or logging) and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                message = node.args[0].value
                if message not in catalog:
                    missing.add(message)
    assert not missing


def test_german_help(capsys: pytest.CaptureFixture[str]) -> None:
    try:
        with pytest.raises(SystemExit) as error:
            cli.parse_args(["--lang=de", "--help"])
        assert error.value.code == 0
        assert "Nur lokale Vorbereitung" in capsys.readouterr().out
    finally:
        i18n.configure("en")


def test_no_kleinanzeigen_python_imports() -> None:
    root = Path(str(files("ebay_bot")))
    for source in root.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                assert all(not alias.name.startswith("kleinanzeigen_bot") for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("kleinanzeigen_bot")
