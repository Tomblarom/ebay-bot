# SPDX-FileCopyrightText: © Sebastian Thomschke and contributors
# SPDX-FileCopyrightText: © Tomblarom and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-ArtifactOfProjectHomePage: https://github.com/Tomblarom/ebay-bot/
"""Source and eBay configuration models.

`SourceAd` describes only the fields eBay publication needs; every other
key of the upstream ``ad_*.yaml``/``ad_*.json`` files is ignored, so the
stable upstream file interface can be reused unchanged. `Config` mirrors
the same ``config.yaml`` keys (``ad_files``, ``ad_defaults``, ``ebay``)
and likewise ignores all unrelated upstream settings.
"""

from __future__ import annotations

__all__ = [
    "Config",
    "ContextualModel",
    "ContextualValidationError",
    "EbayConfig",
    "EbayListing",
    "SourceAd",
    "SourceDefaults",
    "SourcePartial",
    "format_validation_error",
]

import math
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Self, cast

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from pydantic_core import InitErrorDetails

from ebay_bot.i18n import gettext as _


class ContextualValidationError(ValidationError):
    context: Any


class ContextualModel(BaseModel):
    """Base model that attaches caller context (usually a file path) to errors."""

    @classmethod
    def model_validate(
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        extra: Any = None,
        from_attributes: bool | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        try:
            _ = extra  # accepted for signature compatibility; never forwarded (unsupported on pydantic>=2.11 call sites)
            return super().model_validate(
                obj,
                strict=strict,
                from_attributes=from_attributes,
                context=context,
                by_alias=by_alias,
                by_name=by_name,
            )
        except ValidationError as ex:
            new_ex = ContextualValidationError.from_exception_data(
                title=ex.title,
                line_errors=cast(list[InitErrorDetails], ex.errors()),
            )
            new_ex.context = context
            raise new_ex from ex


def format_validation_error(exc: ValidationError) -> str:
    """Render a validation error as short human-readable lines."""
    lines = [f"{exc.error_count()} validation error(s) for {exc.title}"]
    context = getattr(exc, "context", None)
    if context:
        lines.append(f"in file: {context}")
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        lines.append(f"  {location}: {error['msg']}")
    return "\n".join(lines)


class EbayListing(ContextualModel):
    category_id: str | None = Field(default=None, description="eBay leaf category ID (never inferred from the source category)")
    condition_id: int | None = Field(default=None, gt=0, description="eBay condition ID supported by the selected category")
    aspects: dict[str, list[str]] = Field(default_factory=dict, description="Category-specific item specifics, with one or more values per name")
    listing_format: Literal["fixed", "auction"] = Field(default="fixed", description="Buy It Now (fixed) or auction")
    best_offer: bool = Field(default=False, description="Enable Best Offer for fixed-price listings")
    price: Decimal | None = Field(default=None, gt=0, description="Explicit eBay price override; required for wanted/giveaway/nonpositive-price sources")
    auction_start_price: Decimal | None = Field(default=None, gt=0, description="Explicit auction starting price; source price is never used for auctions")
    auction_duration: Literal["Days_3", "Days_5", "Days_7", "Days_10"] | None = Field(default=None, description="Explicit auction duration")
    quantity: int = Field(default=1, ge=1, description="Number of identical items; auctions require one")
    shipping_profile_id: str | None = Field(default=None, description="Seller's eBay shipping business policy ID")
    return_profile_id: str | None = Field(default=None, description="Seller's eBay return business policy ID")
    payment_profile_id: str | None = Field(default=None, description="Seller's eBay payment business policy ID")
    postal_code: str | None = Field(default=None, description="Item location postal code")
    country: str = Field(default="DE", min_length=2, max_length=2, description="Item location country code")

    @field_validator("price", "auction_start_price", mode="before")
    @classmethod
    def parse_price(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError(_("price must be a number"))
        if isinstance(value, (str, int, float)):
            try:
                return Decimal(str(value))
            except InvalidOperation:
                raise ValueError(_("price must be a number")) from None
        return value


class EbayConfig(ContextualModel):
    environment: Literal["sandbox", "production"] = Field(default="sandbox", description="Separate eBay API environment; sandbox is the default")
    account: str = Field(default="", description="Actual eBay seller username, checked against the authorized account before network commands")
    client_id: str = Field(default="", description="Public eBay application client ID for this environment; never put the client secret here")
    redirect_uri: str = Field(default="", description="eBay developer application's redirect URL name (RuName)")
    site_id: int = Field(default=77, ge=0, description="Trading API site ID (77 = Germany)")
    currency: str = Field(default="EUR", min_length=3, max_length=3, description="Source and fee currency; no currency conversion is performed")
    defaults: EbayListing = Field(default_factory=EbayListing, description="Default eBay listing settings, overridden by a source's ebay section")


class SourceDefaults(ContextualModel):
    active: bool = Field(default=True, description="whether the source should be published (false = skip this source)")
    type: Literal["OFFER", "WANTED"] = Field(default="OFFER", description="type of the source listing")
    description_prefix: str | None = Field(default="", description="text to prepend to each description (optional)")
    description_suffix: str | None = Field(default="", description="text to append to each description (optional)")
    price_type: Literal["FIXED", "NEGOTIABLE", "GIVE_AWAY", "NOT_APPLICABLE"] = Field(
        default="NEGOTIABLE", description="pricing strategy of the source listing"
    )
    images: list[str] | None = Field(default_factory=list, description="default image glob patterns (optional). Leave empty for no default images")

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_description(cls, values: Any) -> Any:
        # Flat prefix/suffix take precedence over the deprecated nested
        # "description: {prefix, suffix}" mapping of older config files.
        if not isinstance(values, dict):
            return values
        values = dict(values)
        legacy = values.get("description")
        if isinstance(legacy, dict):
            if not values.get("description_prefix") and legacy.get("prefix") is not None:
                values["description_prefix"] = legacy["prefix"]
            if not values.get("description_suffix") and legacy.get("suffix") is not None:
                values["description_suffix"] = legacy["suffix"]
        return values


class SourcePartial(ContextualModel):
    id: int | None = Field(default=None, description="Upstream ad ID; used for selectors and identity aliases")
    active: bool | None = Field(default=None, description="whether the source should be published")
    type: Literal["OFFER", "WANTED"] | None = Field(default=None, description="type of the source listing")
    title: str = Field(min_length=1, description="Listing title, published verbatim")
    description: str = Field(description="Listing description, sanitized before publication")
    description_prefix: str | None = Field(default=None, description="text to prepend to the description (overrides the default)")
    description_suffix: str | None = Field(default=None, description="text to append to the description (overrides the default)")
    price: int | float | None = Field(default=None, description="Source price; fixed-price listings use it unless overridden")
    price_type: Literal["FIXED", "NEGOTIABLE", "GIVE_AWAY", "NOT_APPLICABLE"] | None = Field(default=None, description="pricing strategy")
    images: list[str] | None = Field(default=None, description="Image file paths or glob patterns relative to the source file")
    ebay: EbayListing | None = Field(default=None, description="eBay-only overrides for this source")
    ebay_source_id: str | None = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{32}$",
        description="Stable cross-run source identity; keep on rename, republication, and redownload",
    )

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(_("title must not be blank"))
        return value

    @field_validator("price", mode="before")
    @classmethod
    def _validate_price(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError(_("price must be a finite number"))
        if isinstance(value, (int, float, Decimal)) and not math.isfinite(value):
            raise ValueError(_("price must be a finite number"))
        return value

    def to_source(self, ad_defaults: SourceDefaults, *, context: Any | None = None) -> SourceAd:
        """Merge this partial source with defaults into a complete validated `SourceAd`.

        Affixes are intentionally not merged here: preparation resolves the
        source-level value against the default, preserving the precedence.
        """
        data = self.model_dump()
        if self.ebay is not None:
            # Retain the explicitly set fields for main-config eBay defaults.
            data["ebay"] = self.ebay
        if data.get("active") is None:
            data["active"] = ad_defaults.active
        if data.get("type") is None:
            data["type"] = ad_defaults.type
        if data.get("price_type") is None:
            data["price_type"] = ad_defaults.price_type
        if data.get("images") is None:
            data["images"] = list(ad_defaults.images or [])
        return SourceAd.model_validate(data, context=context)


# pyright: reportGeneralTypeIssues=false, reportIncompatibleVariableOverride=false
class SourceAd(SourcePartial):
    active: bool
    type: Literal["OFFER", "WANTED"]
    price_type: Literal["FIXED", "NEGOTIABLE", "GIVE_AWAY", "NOT_APPLICABLE"]


class Config(ContextualModel):
    ad_files: list[str] = Field(
        default_factory=lambda: ["./**/ad_*.{json,yml,yaml}"],
        min_length=1,
        description="glob patterns selecting local source files. Relative patterns resolve against this configuration file",
    )
    ad_defaults: SourceDefaults = Field(default_factory=SourceDefaults, description="Default values, can be overwritten in each source file")
    ebay: EbayConfig = Field(default_factory=EbayConfig, description="eBay API configuration and listing defaults")

    @field_validator("ad_files")
    @classmethod
    def _validate_ad_files(cls, value: list[str]) -> list[str]:
        for pattern in value:
            if not pattern.strip():
                raise ValueError(_("must be a non-empty, non-blank glob pattern"))
        return value
