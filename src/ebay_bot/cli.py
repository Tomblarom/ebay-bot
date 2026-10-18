# SPDX-FileCopyrightText: © Tomblarom and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-ArtifactOfProjectHomePage: https://github.com/Tomblarom/ebay-bot/
"""Public CLI; Kleinanzeigen integration uses only an external executable."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

from . import __version__
from .i18n import configure
from .i18n import gettext as _
from .loggers import configure_console_logging, get_logger

COMMANDS = ("login", "prepare", "verify", "publish", "status", "download")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    values = list(argv) if argv is not None else sys.argv[1:]
    language = "de" if "--lang=de" in values or any(a == "--lang" and b == "de" for a, b in zip(values, values[1:], strict=False)) else "en"
    configure(language)
    parser = argparse.ArgumentParser(description=_("Publish local ad files on eBay. Sandbox is the default."))
    parser.add_argument("command", choices=(*COMMANDS, *("ebay-" + value for value in COMMANDS if value != "download")))
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", type=Path, default=Path("config.yaml"), help=_("Companion bot configuration"))
    parser.add_argument("--ads", default="new", help=_("new, all, or comma-separated Kleinanzeigen IDs"))
    parser.add_argument("--dry-run", action="store_true", help=_("Local preparation only"))
    parser.add_argument("--refresh", action="store_true", help=_("Refresh eBay status and reconcile uncertain submissions"))
    parser.add_argument("--fee-limit", type=Decimal, default=None, help=_("Maximum estimated listing fees per listing; default zero"))
    parser.add_argument("--lang", choices=("en", "de"), default="en")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--kleinanzeigen-config", type=Path, help=_("Existing kleinanzeigen-bot configuration for download"))
    parser.add_argument("--kleinanzeigen-command", default="kleinanzeigen-bot", help=_("Path to the separately installed Kleinanzeigen CLI"))
    result = parser.parse_args(argv)
    result.command = result.command.removeprefix("ebay-")
    if result.refresh and result.command != "status":
        parser.error(_("--refresh is available only for status"))
    if result.fee_limit is not None and result.command != "publish":
        parser.error(_("--fee-limit is available only for publish"))
    if result.fee_limit is not None and (not result.fee_limit.is_finite() or result.fee_limit < 0):
        parser.error(_("--fee-limit must be a finite nonnegative amount"))
    if result.ads not in {"new", "all"} and not all(part.strip().isdigit() for part in result.ads.split(",")):
        parser.error(_("--ads must be new, all, or comma-separated Kleinanzeigen IDs"))
    if result.command == "download":
        if result.dry_run:
            parser.error(_("download does not support --dry-run; use prepare for local inspection"))
        if result.kleinanzeigen_config is None:
            parser.error(_("download requires --kleinanzeigen-config"))
    elif result.kleinanzeigen_config is not None or result.kleinanzeigen_command != "kleinanzeigen-bot":
        parser.error(_("--kleinanzeigen-config and --kleinanzeigen-command are available only for download"))
    if result.fee_limit is None:
        result.fee_limit = Decimal(0)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    configure(args.lang)
    configure_console_logging()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    try:
        if args.command == "download":
            command = [
                args.kleinanzeigen_command,
                "download",
                "--ads=" + args.ads,
                "--workspace-mode=portable",
                "--config=" + str(args.kleinanzeigen_config.resolve()),
            ]
            return subprocess.run(command, check=False).returncode
        from .ebay_workflow import run

        run(args.config.resolve(), "ebay-" + args.command, args.ads, dry_run=args.dry_run, refresh=args.refresh, fee_limit=args.fee_limit)
        return 0
    except Exception as exc:
        get_logger(__name__).error("%s", str(exc))
        return 1
