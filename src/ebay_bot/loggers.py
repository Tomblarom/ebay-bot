# SPDX-FileCopyrightText: © Tomblarom and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-ArtifactOfProjectHomePage: https://github.com/Tomblarom/ebay-bot/
"""Standard logging with automatic translation of known message templates."""

import logging

from .i18n import gettext

Logger = logging.Logger
INFO = logging.INFO


class TranslationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = gettext(record.msg)
        return True


def get_logger(name: str) -> Logger:
    logger = logging.getLogger(name)
    if not any(isinstance(item, TranslationFilter) for item in logger.filters):
        logger.addFilter(TranslationFilter())
    return logger


def configure_console_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
