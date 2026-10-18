# SPDX-FileCopyrightText: © Tomblarom and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-ArtifactOfProjectHomePage: https://github.com/Tomblarom/ebay-bot/
"""Tests for roundtrip YAML/JSON file IO (fully offline)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from ebay_bot import files

if TYPE_CHECKING:
    from pathlib import Path


def test_save_and_load_yaml_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "ad.yaml"
    files.save_dict(path, {"title": "Camera", "price": 80})
    assert files.load_dict(str(path)) == {"title": "Camera", "price": 80}


def test_yaml_comments_survive_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "ad.yaml"
    path.write_text("# top comment\ntitle: Camera  # side comment\n", encoding="utf-8")
    data = files.load_dict(str(path))
    data["price"] = 80
    files.save_dict(path, data)
    text = path.read_text(encoding="utf-8")
    assert "# top comment" in text
    assert "# side comment" in text
    assert files.load_dict(str(path))["price"] == 80


def test_multiline_strings_use_block_style(tmp_path: Path) -> None:
    path = tmp_path / "ad.yaml"
    files.save_dict(path, {"description": "first\nsecond"})
    assert "|" in path.read_text(encoding="utf-8")


def test_json_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "ad.json"
    files.save_dict(path, {"title": "Grüße", "price": 80})
    assert files.load_dict(str(path)) == {"title": "Grüße", "price": 80}


def test_header_is_written_first(tmp_path: Path) -> None:
    path = tmp_path / "ad.yaml"
    files.save_dict(path, {"title": "Camera"}, header="# generated")
    assert path.read_text(encoding="utf-8").startswith("# generated\n")


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deep" / "ad.yaml"
    files.save_dict(path, {"title": "Camera"})
    assert files.load_dict(str(path)) == {"title": "Camera"}


def test_unsupported_suffix_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported file type"):
        files.load_dict("ad.txt")


def test_missing_file_returns_none_for_if_exists(tmp_path: Path) -> None:
    assert files.load_dict_if_exists(str(tmp_path / "absent.yaml")) is None


def test_missing_file_raises_for_load(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        files.load_dict(str(tmp_path / "absent.yaml"))


def test_empty_file_loads_as_empty_dict(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    assert files.load_dict(str(path)) == {}


def test_non_mapping_content_raises(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        files.load_dict(str(path))


def test_loaded_data_supports_mutation(tmp_path: Path) -> None:
    path = tmp_path / "ad.yaml"
    files.save_dict(path, {"a": {"b": 1}})
    data: dict[str, Any] = files.load_dict(str(path))
    data["a"]["b"] = 2
    files.save_dict(path, data)
    assert files.load_dict(str(path)) == {"a": {"b": 2}}
