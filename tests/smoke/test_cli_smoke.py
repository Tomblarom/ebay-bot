# SPDX-FileCopyrightText: © Tomblarom and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-ArtifactOfProjectHomePage: https://github.com/Tomblarom/ebay-bot/
"""Minimal installed CLI preparation health check with synthetic local data."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.smoke
def test_dry_run_needs_no_credentials_or_browser(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text('ad_files: ["ad_*.yaml"]\nebay: {}\n', encoding="utf-8")
    ad = tmp_path / "ad_camera.yaml"
    ad.write_text('title: Camera with original box\ndescription: "Good condition. Visit https://example.com"\nprice: 50\n', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "ebay_bot", "publish", "--dry-run", "--ads=all", "--config", str(config)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "user-config")},
    )
    assert result.returncode == 0, result.stderr + result.stdout
    output = result.stderr + result.stdout
    assert "1 links removed" in output
    assert "Good condition. Visit" in output
    assert "ebay_source_id" in ad.read_text(encoding="utf-8")
    assert not (tmp_path / "user-config" / "ebay-bot").exists()
