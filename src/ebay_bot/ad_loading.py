# SPDX-FileCopyrightText: © Jens Bergmann and contributors
# SPDX-FileCopyrightText: © Tomblarom and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-ArtifactOfProjectHomePage: https://github.com/Tomblarom/ebay-bot/
"""Discovery, validation, and image resolution for local source files.

Sources are the stable upstream ``ad_*.yaml``/``ad_*.json`` files; only
the fields eBay publication needs are validated, everything else is
ignored.
"""

__all__ = ["abspath", "discover_ad_files", "load_ad", "load_ad_configs", "resolve_ad_images"]

import os
from typing import Any, Final

from wcmatch import glob

from ebay_bot import files
from ebay_bot.i18n import gettext as _
from ebay_bot.loggers import Logger, get_logger
from ebay_bot.models import SourceAd, SourceDefaults, SourcePartial

LOG: Final[Logger] = get_logger(__name__)

SUPPORTED_IMAGE_SUFFIXES: Final[frozenset[str]] = frozenset({".gif", ".jpg", ".jpeg", ".png"})


def abspath(relative_path: str, relative_to: str | None = None) -> str:
    """Return a normalized absolute path based on *relative_to* (or the cwd).

    A *relative_to* value pointing at a file resolves against its directory.
    """
    if not relative_to:
        return os.path.abspath(relative_path)
    if os.path.isabs(relative_path):
        return os.path.normpath(relative_path)
    base = os.path.abspath(relative_to)
    if os.path.isfile(base):
        base = os.path.dirname(base)
    return os.path.normpath(os.path.join(base, relative_path))


def discover_ad_files(config_file_path: str, ad_file_patterns: list[str]) -> dict[str, str]:
    """Glob for source files matching *ad_file_patterns*.

    Returns a ``{abspath: relative_path}`` dict, excluding any file whose
    basename is ``ad_fields.yaml``.
    """
    ad_files: dict[str, str] = {}
    data_root_dir = os.path.dirname(config_file_path)
    for file_pattern in ad_file_patterns:
        for ad_file in glob.glob(
            file_pattern,
            root_dir=data_root_dir,
            flags=glob.GLOBSTAR | glob.BRACE | glob.EXTGLOB,
        ):
            if not str(ad_file).endswith("ad_fields.yaml"):
                ad_files[abspath(ad_file, relative_to=data_root_dir)] = ad_file
    return ad_files


def load_ad(ad_cfg_orig: dict[str, Any], ad_defaults: SourceDefaults, ad_file: str) -> SourceAd:
    """Validate a raw source dict into a `SourceAd` with *ad_defaults* applied."""
    return SourcePartial.model_validate(ad_cfg_orig, context=ad_file).to_source(ad_defaults, context=ad_file)


def load_ad_configs(
    *,
    config_file_path: str,
    ad_file_patterns: list[str],
    ad_defaults: SourceDefaults,
) -> list[tuple[str, str, SourceAd, dict[str, Any]]]:
    """Discover, load raw YAML, validate, and apply defaults for every source file.

    This is a neutral loading step: no selector filtering, no image
    globbing. Returns a sorted list of ``(abspath, relpath, SourceAd,
    raw_dict)`` tuples.
    """
    ad_files = discover_ad_files(config_file_path, ad_file_patterns)
    result: list[tuple[str, str, SourceAd, dict[str, Any]]] = []
    for ad_file, ad_file_relative in sorted(ad_files.items()):
        ad_cfg_orig = files.load_dict(ad_file, "ad")
        ad_cfg = load_ad(ad_cfg_orig, ad_defaults, ad_file)
        result.append((ad_file, ad_file_relative, ad_cfg, ad_cfg_orig))
    return result


def resolve_ad_images(ad_file: str, image_patterns: list[str]) -> list[str]:
    """Glob and validate image files matching *image_patterns*.

    Images resolve relative to *ad_file*'s directory. Supported
    extensions: ``.gif``, ``.jpg``, ``.jpeg``, ``.png``.

    Returns a deduplicated, ordered list of absolute paths.
    """
    if not image_patterns:
        return []
    images: list[str] = []
    ad_dir = os.path.dirname(ad_file)
    for image_pattern in image_patterns:
        pattern_images: set[str] = set()
        for image_file in glob.glob(
            image_pattern,
            root_dir=ad_dir,
            flags=glob.GLOBSTAR | glob.BRACE | glob.EXTGLOB,
        ):
            image_file_ext = os.path.splitext(image_file)[1]
            if image_file_ext.lower() not in SUPPORTED_IMAGE_SUFFIXES:
                raise ValueError(_("Unsupported image file type [%s]") % image_file)
            if os.path.isabs(image_file):
                pattern_images.add(image_file)
            else:
                pattern_images.add(abspath(image_file, relative_to=ad_file))
        images.extend(sorted(pattern_images))
    if not images:
        raise ValueError(_("No images found for given file patterns %s at %s") % (image_patterns, ad_dir))
    return list(dict.fromkeys(images))
