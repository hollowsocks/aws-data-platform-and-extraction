# TripleWhale Ingestion Module

This package houses the reusable client, models, and transformation logic for TripleWhale data pulls. It is imported by the TripleWhale Lambda and any offline replay tooling.

## Layout

- `src/triplewhale_ingestion/` – shared Python code (clients, SQL helpers, aggregations).
- `tests/` – unit tests covering transforms and API helpers (to be added).

The module will be packaged via the root build tooling; no standalone virtualenv is required.
