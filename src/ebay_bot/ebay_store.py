# SPDX-FileCopyrightText: © Tomblarom and contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-ArtifactOfProjectHomePage: https://github.com/Tomblarom/ebay-bot/
"""Durable source identities, eBay overrides, and publish journal.

A committed pending row is a publication barrier: only its creator may
submit. Other runs reconcile it, and never interpret an empty lookup as
permission to retry.

Identity recovery without upstream hooks: the upstream redownload does
not preserve ``ebay``/``ebay_source_id`` fields, so per-source eBay
overrides are additionally persisted in `source_metadata` (keyed by the
durable source ID, with alias lookup by upstream ad ID) and restored
during preparation. Republication to a new upstream ID cannot be
observed; the same physical item keeps its identity only while the
source file retains its ``ebay_source_id``. Identity is never inferred
from titles or content hashes.
"""

__all__ = [
    "EbayStore",
    "ListingRecord",
    "default_state_path",
    "save_source",
]

import json
import os
import sqlite3
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from platformdirs import user_state_path

from ebay_bot import files
from ebay_bot.i18n import gettext as _


def default_state_path() -> Path:
    return user_state_path("ebay-bot") / "listings.sqlite3"


@dataclass(frozen=True)
class ListingRecord:
    source_id: str
    item_id: str | None
    status: str
    submitted_at: str
    listing_uuid: str


def save_source(path: Path, raw: dict[str, Any]) -> None:
    """Replace source data atomically, preserving YAML comments and JSON format."""
    fd, name = tempfile.mkstemp(prefix=".ebay-source-", suffix=path.suffix, dir=path.parent)
    temporary = Path(name)
    os.close(fd)
    try:
        files.save_dict(temporary, raw)
        # Windows requires a writable handle for fsync/FlushFileBuffers.
        with temporary.open("r+b") as stream:
            os.fsync(stream.fileno())
        temporary.chmod(path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class EbayStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else default_state_path()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        self.connection = sqlite3.connect(self.path, timeout=30)
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS source_aliases (
                ad_id INTEGER PRIMARY KEY, source_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_metadata (
                source_id TEXT PRIMARY KEY, ebay_json TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS listings (
                environment TEXT NOT NULL, seller TEXT NOT NULL, source_id TEXT NOT NULL,
                item_id TEXT, status TEXT NOT NULL, submitted_at TEXT NOT NULL,
                listing_uuid TEXT NOT NULL,
                PRIMARY KEY (environment, seller, source_id)
            );
        """)

    def close(self) -> None:
        self.connection.close()

    def identify(self, path: Path, raw: dict[str, Any]) -> str:
        """Register identity before publication and retain aliases across republication.

        Re-read under the SQLite writer lock so concurrent initial preparations
        cannot assign different IDs. Aliases recover identity after redownload
        into a different folder with the same upstream ID.
        """
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            current = files.load_dict(str(path), "ad")
            ad_id = current.get("id")
            alias = self.connection.execute("SELECT source_id FROM source_aliases WHERE ad_id=?", (ad_id,)).fetchone()
            source_id = str(current.get("ebay_source_id") or (alias[0] if alias else uuid4().hex)).upper()
            if alias and alias[0] != source_id:
                raise ValueError(_("Conflicting eBay source identities; restore the original source ID before continuing"))
            if ad_id:
                self.connection.execute("INSERT OR IGNORE INTO source_aliases VALUES (?, ?)", (ad_id, source_id))
            if current.get("ebay_source_id") != source_id:
                current["ebay_source_id"] = source_id
                save_source(path, current)
            self.connection.commit()
            raw["ebay_source_id"] = source_id
            return source_id
        except BaseException:
            self.connection.rollback()
            raise

    def lookup_identity(self, raw: dict[str, Any]) -> str | None:
        if raw.get("ebay_source_id"):
            return str(raw["ebay_source_id"]).upper()
        row = self.connection.execute("SELECT source_id FROM source_aliases WHERE ad_id=?", (raw.get("id"),)).fetchone()
        return str(row[0]) if row else None

    def remember_alias(self, ad_id: int, source_id: str) -> None:
        with self.connection:
            row = self.connection.execute("SELECT source_id FROM source_aliases WHERE ad_id=?", (ad_id,)).fetchone()
            if row and row[0] != source_id.upper():
                raise ValueError(_("Conflicting eBay source identities; restore the original source ID before continuing"))
            self.connection.execute("INSERT OR IGNORE INTO source_aliases VALUES (?, ?)", (ad_id, source_id.upper()))

    def source_metadata(self, source_id: str) -> dict[str, Any]:
        """Return the persisted eBay overrides for *source_id* (empty when unknown)."""
        row = self.connection.execute("SELECT ebay_json FROM source_metadata WHERE source_id=?", (source_id.upper(),)).fetchone()
        if not row:
            return {}
        data = json.loads(row[0])
        return data if isinstance(data, dict) else {}

    def remember_source_metadata(self, source_id: str, ebay: Mapping[str, Any]) -> None:
        """Persist the effective eBay overrides so redownloads cannot discard them."""
        payload = json.loads(json.dumps(dict(ebay)))
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO source_metadata VALUES (?, ?, ?)",
                (source_id.upper(), json.dumps(payload, sort_keys=True), datetime.now(UTC).isoformat()),
            )

    def get(self, environment: str, seller: str, source_id: str) -> ListingRecord | None:
        row = self.connection.execute(
            "SELECT source_id, item_id, status, submitted_at, listing_uuid FROM listings WHERE environment=? AND seller=? AND source_id=?",
            (environment, seller.casefold(), source_id.upper()),
        ).fetchone()
        return ListingRecord(*row) if row else None

    def begin_publish(self, environment: str, seller: str, source_id: str) -> bool:
        """Atomically reserve publication; any existing row blocks another Add call."""
        with self.connection:
            result = self.connection.execute(
                "INSERT OR IGNORE INTO listings VALUES (?, ?, ?, NULL, 'pending', ?, ?)",
                (environment, seller.casefold(), source_id.upper(), datetime.now(UTC).isoformat(), uuid4().hex.upper()),
            )
            if result.rowcount == 1:
                return True
            result = self.connection.execute(
                "UPDATE listings SET status='pending', submitted_at=? "
                "WHERE environment=? AND seller=? AND source_id=? AND status='rejected' AND item_id IS NULL",
                (datetime.now(UTC).isoformat(), environment, seller.casefold(), source_id.upper()),
            )
        return result.rowcount == 1

    def record_rejection(self, environment: str, seller: str, source_id: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE listings SET status='rejected' WHERE environment=? AND seller=? AND source_id=? AND item_id IS NULL",
                (environment, seller.casefold(), source_id.upper()),
            )

    def record_listing(self, environment: str, seller: str, source_id: str, item_id: str, status: str) -> None:
        if not item_id.isdigit():
            raise ValueError(_("eBay returned an invalid listing ID"))
        with self.connection:
            self.connection.execute(
                "UPDATE listings SET item_id=?, status=? WHERE environment=? AND seller=? AND source_id=?",
                (item_id, status, environment, seller.casefold(), source_id.upper()),
            )

    def records(self, environment: str, seller: str) -> list[ListingRecord]:
        return [
            ListingRecord(*row)
            for row in self.connection.execute(
                "SELECT source_id, item_id, status, submitted_at, listing_uuid FROM listings WHERE environment=? AND seller=? ORDER BY submitted_at",
                (environment, seller.casefold()),
            )
        ]
