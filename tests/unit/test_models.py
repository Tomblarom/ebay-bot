# SPDX-FileCopyrightText: © Tomblarom and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-ArtifactOfProjectHomePage: https://github.com/Tomblarom/ebay-bot/
"""Tests for source and eBay configuration models (fully offline)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ebay_bot.models import (
    Config,
    ContextualValidationError,
    EbayConfig,
    EbayListing,
    SourceAd,
    SourceDefaults,
    SourcePartial,
    format_validation_error,
)


def test_config_defaults() -> None:
    config = Config.model_validate({})
    assert config.ad_files == ["./**/ad_*.{json,yml,yaml}"]
    assert config.ad_defaults.description_prefix == ""
    assert config.ebay.environment == "sandbox"
    assert config.ebay.site_id == 77
    assert config.ebay.currency == "EUR"


def test_config_ignores_unrelated_upstream_keys() -> None:
    config = Config.model_validate(
        {
            "ad_files": ["ads/*.yaml"],
            "browser": {"arguments": ["--headless"]},
            "login": {"username": "u", "password": "p"},
            "download": {"dir": "downloaded-ads"},
            "timeouts": {"default": 5.0},
        }
    )
    assert config.ad_files == ["ads/*.yaml"]
    assert config.ebay.account == ""


def test_config_rejects_blank_or_empty_ad_files() -> None:
    with pytest.raises(ValidationError):
        Config.model_validate({"ad_files": ["  "]})
    with pytest.raises(ValidationError):
        Config.model_validate({"ad_files": []})


def test_source_defaults_migrate_legacy_description() -> None:
    defaults = SourceDefaults.model_validate({"description": {"prefix": "P_", "suffix": "_S"}})
    assert defaults.description_prefix == "P_"
    assert defaults.description_suffix == "_S"


def test_source_defaults_flat_affixes_win_over_legacy() -> None:
    defaults = SourceDefaults.model_validate(
        {
            "description_prefix": "flat",
            "description": {"prefix": "legacy", "suffix": "legacy"},
        }
    )
    assert defaults.description_prefix == "flat"
    assert defaults.description_suffix == "legacy"


def test_source_partial_ignores_unrelated_source_keys() -> None:
    partial = SourcePartial.model_validate(
        {
            "title": "A used camera for sale",
            "description": "Clean camera.",
            "category": "161",
            "contact": {"name": "Test", "zipcode": "12345"},
            "shipping_type": "SHIPPING",
            "republication_interval": 7,
        }
    )
    assert partial.title == "A used camera for sale"


def test_source_partial_requires_title_and_description() -> None:
    with pytest.raises(ValidationError):
        SourcePartial.model_validate({"description": "No title"})
    with pytest.raises(ValidationError):
        SourcePartial.model_validate({"title": "No description here"})
    with pytest.raises(ValidationError):
        SourcePartial.model_validate({"title": "   ", "description": "Blank title"})


def test_source_partial_rejects_bad_identity_and_price() -> None:
    with pytest.raises(ValidationError):
        SourcePartial.model_validate({"title": "Valid title here", "description": "d", "ebay_source_id": "nope"})
    for bad_price in (float("nan"), float("inf"), True):
        with pytest.raises(ValidationError):
            SourcePartial.model_validate({"title": "Valid title here", "description": "d", "price": bad_price})


def test_to_source_merges_defaults() -> None:
    partial = SourcePartial.model_validate({"title": "A used camera for sale", "description": "Clean."})
    ad = partial.to_source(SourceDefaults())
    assert isinstance(ad, SourceAd)
    assert ad.active is True
    assert ad.type == "OFFER"
    assert ad.price_type == "NEGOTIABLE"
    assert ad.images == []
    assert ad.description_prefix is None
    assert ad.description_suffix is None


def test_to_source_keeps_explicit_values_and_empty_images() -> None:
    partial = SourcePartial.model_validate(
        {
            "title": "A used camera for sale",
            "description": "Clean.",
            "active": False,
            "type": "WANTED",
            "price_type": "FIXED",
            "images": [],
            "description_prefix": "P_",
        }
    )
    ad = partial.to_source(SourceDefaults())
    assert ad.active is False
    assert ad.type == "WANTED"
    assert ad.price_type == "FIXED"
    assert ad.images == []
    assert ad.description_prefix == "P_"


def test_to_source_falls_back_to_default_images() -> None:
    partial = SourcePartial.model_validate({"title": "A used camera for sale", "description": "Clean."})
    ad = partial.to_source(SourceDefaults.model_validate({"images": ["*.jpg"]}))
    assert ad.images == ["*.jpg"]


def test_ebay_listing_parses_price_formats() -> None:
    assert EbayListing.model_validate({"price": "11.20"}).price == Decimal("11.20")
    assert EbayListing.model_validate({"price": 11}).price == Decimal("11")
    assert EbayListing.model_validate({"price": 11.5}).price == Decimal("11.5")
    with pytest.raises(ValidationError):
        EbayListing.model_validate({"price": "not-a-number"})
    with pytest.raises(ValidationError):
        EbayListing.model_validate({"price": True})


def test_ebay_config_environment_is_sandbox_by_default() -> None:
    assert EbayConfig().environment == "sandbox"


def test_validation_error_carries_file_context() -> None:
    with pytest.raises(ContextualValidationError) as error:
        SourcePartial.model_validate({"description": "No title"}, context="ads/ad_1.yaml")
    assert error.value.context == "ads/ad_1.yaml"
    assert "title" in format_validation_error(error.value)
    assert "ads/ad_1.yaml" in format_validation_error(error.value)
