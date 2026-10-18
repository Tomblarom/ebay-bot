# ebay-bot

An independent CLI for publishing local ad files and pictures on eBay through the
Trading and Media APIs. Supports fixed price, Best Offer and explicit auctions.
Sandbox is the default. All automated tests use offline fakes; live seller
authorization and publication have not been tested.

This community companion is separate from [kleinanzeigen-bot](https://github.com/Second-Hand-Friends/kleinanzeigen-bot).
It uses only the external download CLI and generated YAML/JSON files and pictures,
never internal Python modules. Orders, sales, stock and removals are not synchronized.

## Installation and local preparation

Python 3.12 or later is required:

```sh
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/ebay-bot prepare --config=config.yaml --ads=all
.venv/bin/ebay-bot publish --config=config.yaml --ads=all --dry-run
```

Preparation shows the cleaned final description including prefix/suffix, pictures,
price and missing requirements without network access. It persists a source ID and
local state. Links and active HTML are removed; labels and paragraphs are retained.
The original description and photos are preserved.

## Configuration

Keep a separate companion configuration:

```yaml
ad_files:
  - /absolute/path/to/downloaded-ads/**/ad_*.yaml
ad_defaults:
  description_prefix: ''
  description_suffix: ''
ebay:
  environment: sandbox
  account: YOUR_SANDBOX_SELLER_USERNAME
  client_id: YOUR_PUBLIC_SANDBOX_CLIENT_ID
  redirect_uri: YOUR_EBAY_RUNAME
  site_id: 77
  currency: EUR
  defaults:
    country: DE
    postal_code: '10115'
    shipping_profile_id: YOUR_SANDBOX_SHIPPING_POLICY_ID
    return_profile_id: YOUR_SANDBOX_RETURN_POLICY_ID
    payment_profile_id: YOUR_SANDBOX_PAYMENT_POLICY_ID
```

Each source ad can add `ebay.category_id`, `condition_id`, and category-specific
`aspects` (mapping names to value lists). Use actual eBay IDs and policies for the
selected seller/environment. The positive source price is copied numerically;
`ebay.price` overrides it. Wanted, giveaway and unpriced sources require an explicit
positive eBay price. No currency conversion is performed.

Auctions require `listing_format: auction`, `auction_start_price`, explicit
`auction_duration` (`Days_3`, `Days_5`, `Days_7`, `Days_10`), quantity one and
`best_offer: false`. The source price is never an implicit auction starting price.
Verification rejects missing category/regulatory details; fields that cannot be
represented by these settings need another supported listing workflow.

## Authorization and publication

Create an [eBay developer application](https://developer.ebay.com/), sandbox
keyset, test seller and seller business policies. Set an OAuth redirect page from
which the complete callback URL (with code/state) can be copied. Configure its
**RuName**, not its URL, as `redirect_uri`.

```sh
ebay-bot login --config=config.yaml
ebay-bot verify --config=config.yaml --ads=all
ebay-bot publish --config=config.yaml --ads=new
ebay-bot status --config=config.yaml --ads=all --refresh
```

Login asks for the client secret and callback URL through hidden prompts. For
unattended refresh supply `EBAY_SANDBOX_CLIENT_SECRET` or
`EBAY_PRODUCTION_CLIENT_SECRET` using your secret-management tooling. Never place
secrets/tokens in ad/config files or command-line arguments. Private token storage
uses the OS user config directory for `ebay-bot`. Consent requests Trading base
and Media `sell.inventory` scopes; every online workflow checks the seller.

`verify` uploads pictures but creates no offer. `publish` verifies current data
before submission. The default maximum estimated listing fees is zero; accepting
an estimate requires an explicit value such as `--fee-limit=0.35` per listing in
the configured currency. Estimates do not guarantee final eBay charges. Production
needs its own keyset, authorization, seller and policies.

Selectors are `new` (default), `all`, or comma-separated **Kleinanzeigen** IDs.
Existing mapped offers, including ended ones, are never implicitly relisted.
Inactive sources are skipped for preparation/publication, but may appear in status.
`--dry-run` always means local preparation. `--lang=de` enables German runtime
translations. The former `ebay-*` command names are also accepted.

## External download CLI

Install kleinanzeigen-bot independently, then optionally run:

```sh
ebay-bot download --kleinanzeigen-config=/path/to/kleinanzeigen-config.yaml --ads=all
```

`--kleinanzeigen-command=/path/to/kleinanzeigen-bot` selects another executable.
The wrapper invokes only `download`; publishing never downloads automatically.
Point the companion's `ad_files` at the downloaded folder.

## Identity and recovery

Keep `ebay_source_id` when moving/renaming or republishing the same physical item
on Kleinanzeigen. State uses the OS user state directory for `ebay-bot` with
seller/environment separation. ID aliases recover identity after redownload.
Per-source eBay overrides are retained in companion state; explicit source values
take precedence. A new Kleinanzeigen ID without retained identity needs manual
association: titles/content hashes are never used to guess physical identity.

The durable journal reserves a source and UUID before Add. Concurrent runs cannot
both submit it. Uncertain outcomes stay blocked while `status --refresh` reconciles
seller listings. An empty lookup never permits another Add. Complete rejections
can retry after correction/reconciliation with the same UUID. Never delete state
or IDs to bypass the barrier. Back up sources and state together. Fresh source
files without copied identity represent different physical items. Older integrated
draft state is separate; preserve it and inspect any previously published offers
before migrating them.

## Development and origin

```sh
pdm install
pdm run format
pdm run lint
pdm run test
```

Tests never contact either marketplace. This code derives from
[draft PR #1353](https://github.com/Second-Hand-Friends/kleinanzeigen-bot/pull/1353),
following [the maintainer discussion](https://github.com/Second-Hand-Friends/kleinanzeigen-bot/discussions/1354#discussioncomment-19002733).
Original public history remains on `archive/kleinanzeigen-ebay-draft`; SPDX
copyright notices, necessary credits and AGPL-3.0-or-later are preserved. Changes
in this standalone version are recorded in Git history. This is not an official
feature of kleinanzeigen-bot.
