# SPDX-FileCopyrightText: © Tomblarom and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-ArtifactOfProjectHomePage: https://github.com/Tomblarom/ebay-bot/
"""Tests for source discovery, validation, and image resolution (fully offline)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ebay_bot import files
from ebay_bot.ad_loading import abspath, discover_ad_files, load_ad, load_ad_configs, resolve_ad_images
from ebay_bot.models import Config, SourceDefaults


def _write(path: Path, content: dict[str, Any]) -> None:
    files.save_dict(path, content)


def test_abspath_resolves_files_and_directories(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("{}", encoding="utf-8")
    assert abspath("ads/a.yaml", relative_to=str(config)) == str(tmp_path / "ads" / "a.yaml")
    assert abspath("a.yaml", relative_to=str(tmp_path)) == str(tmp_path / "a.yaml")
    assert abspath(str(tmp_path)) == str(tmp_path)


def test_discover_expands_braces_relative_to_config(tmp_path: Path) -> None:
    (tmp_path / "ads").mkdir()
    (tmp_path / "ads" / "ad_one.yaml").write_text("{}", encoding="utf-8")
    (tmp_path / "ads" / "ad_two.json").write_text("{}", encoding="utf-8")
    (tmp_path / "ads" / "notes.txt").write_text("x", encoding="utf-8")
    found = discover_ad_files(str(tmp_path / "config.yaml"), ["ads/ad_*.{json,yml,yaml}"])
    assert {Path(value) for value in found.values()} == {Path("ads") / "ad_one.yaml", Path("ads") / "ad_two.json"}
    assert all(path.startswith(str(tmp_path)) for path in found)


def test_discover_skips_ad_fields_file(tmp_path: Path) -> None:
    (tmp_path / "ad_fields.yaml").write_text("{}", encoding="utf-8")
    assert discover_ad_files(str(tmp_path / "config.yaml"), ["*.yaml"]) == {}


def test_load_ad_applies_defaults_with_context(tmp_path: Path) -> None:
    ad_file = tmp_path / "ad_a.yaml"
    ad = load_ad({"title": "A used camera for sale", "description": "Clean."}, SourceDefaults(), str(ad_file))
    assert ad.active is True
    assert ad.type == "OFFER"


def test_load_ad_configs_returns_sorted_validated_sources(tmp_path: Path) -> None:
    _write(tmp_path / "ad_b.yaml", {"title": "Second title here", "description": "B."})
    _write(tmp_path / "ad_a.yaml", {"title": "First title here", "description": "A."})
    config = Config.model_validate({"ad_files": ["ad_*.yaml"]})
    loaded = load_ad_configs(config_file_path=str(tmp_path / "config.yaml"), ad_file_patterns=config.ad_files, ad_defaults=config.ad_defaults)
    assert [relative for _path, relative, _ad, _raw in loaded] == ["ad_a.yaml", "ad_b.yaml"]
    assert loaded[0][2].title == "First title here"
    assert loaded[0][3]["description"] == "A."


def test_resolve_ad_images_globs_dedupes_and_absolutizes(tmp_path: Path) -> None:
    (tmp_path / "pics").mkdir()
    (tmp_path / "pics" / "one.jpg").write_bytes(b"a")
    (tmp_path / "pics" / "two.png").write_bytes(b"b")
    (tmp_path / "ad_a.yaml").write_text("title: x", encoding="utf-8")
    ad_file = str(tmp_path / "ad_a.yaml")
    images = resolve_ad_images(ad_file, ["pics/*.jpg", "pics/*.{jpg,png}"])
    assert images == [str(tmp_path / "pics" / "one.jpg"), str(tmp_path / "pics" / "two.png")]


def test_resolve_ad_images_rejects_unsupported_types(tmp_path: Path) -> None:
    (tmp_path / "movie.mp4").write_bytes(b"x")
    with pytest.raises(ValueError, match="Unsupported image file type"):
        resolve_ad_images(str(tmp_path / "ad_a.yaml"), ["*.mp4"])


def test_resolve_ad_images_empty_patterns_return_empty_list(tmp_path: Path) -> None:
    assert resolve_ad_images(str(tmp_path / "ad_a.yaml"), []) == []


def test_resolve_ad_images_without_match_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No images found"):
        resolve_ad_images(str(tmp_path / "ad_a.yaml"), ["*.jpg"])
