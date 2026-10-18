# SPDX-FileCopyrightText: © Tomblarom and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-ArtifactOfProjectHomePage: https://github.com/Tomblarom/ebay-bot/
"""CLI boundaries and the external executable contract, entirely offline."""

import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ebay_bot import cli


@pytest.mark.parametrize("command", ["prepare", "ebay-prepare", "publish", "ebay-publish"])
def test_command_aliases_and_defaults(command: str) -> None:
    parsed = cli.parse_args([command, "--dry-run"])
    assert parsed.command == command.removeprefix("ebay-")
    assert parsed.ads == "new"
    assert parsed.fee_limit == Decimal(0)


@pytest.mark.parametrize(
    "arguments",
    [
        ["prepare", "--refresh"],
        ["verify", "--fee-limit=1"],
        ["publish", "--fee-limit=NaN"],
        ["publish", "--fee-limit=-1"],
        ["download", "--dry-run", "--kleinanzeigen-config=config.yaml"],
        ["download"],
        ["prepare", "--ads=due"],
    ],
)
def test_invalid_options_fail_before_execution(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.parse_args(arguments)
    assert exc.value.code == 2


def test_download_uses_external_cli_without_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config with spaces;touch.yaml"
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 7)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    assert cli.main(["download", "--kleinanzeigen-config", str(config), "--ads=42,43", "--kleinanzeigen-command=/opt/bin/kleinanzeigen-bot"]) == 7
    assert calls == [
        (["/opt/bin/kleinanzeigen-bot", "download", "--ads=42,43", "--workspace-mode=portable", "--config=" + str(config.resolve())], {"check": False})
    ]
