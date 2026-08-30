# Improvement Proposal

## Overview

I reviewed the codebase with a focus on reliability, maintainability,
testing, and local setup. The main functionality is clear and the
project already has a good separation between the domain, ports, and
adapters.

The improvements below are focused on making the application safer to
run, easier to maintain, easier to test, and better prepared for future
model or infrastructure changes.

------------------------------------------------------------------------

## Database

### 1. Connection pooling for Postgres

`CountPostgresRepo.__connect()` opens a brand new connection on every call. Each
request does a TCP connect plus auth handshake, twice (once for the write, once for
the read). Under any real load this becomes the slowest part of the request.

`CountMongoDBRepo.__get_counter_col()` has the same problem, it builds a new
`MongoClient` every call and throws away the pooling pymongo gives you for free.

**Fix:** create a `psycopg2.pool.SimpleConnectionPool` once in `__init__` and borrow
connections from it. For Mongo, build the `MongoClient` once in `__init__`.


### 2. Batch the writes

`update_values()` loops over the counts and runs one `INSERT` per class. An image with
5 classes means 5 round trips to the database.

**Fix:** use `cursor.executemany()` with the same upsert, so it is one round trip.


### 3. Database migrations

There was no schema at all, the first request failed with
`relation "counter" does not exist`.

Right now `sql/schema.sql` is mounted into `/docker-entrypoint-initdb.d`, so Postgres
creates the table on first start. `make migrate` applies it to a database that already
exists.

This works for setup but it is not really a migration system. It can build the database
from empty, it cannot change a database that already has data. Once the schema starts
changing you need Alembic (versioned migrations with upgrade/downgrade).

**Fix:** add Alembic when the schema needs to evolve. For this exercise the SQL file is
enough and I am calling it out as a shortcut on purpose.

---

## Code practice

### 4. No error handling on the API

Any bad input returns a 500 with a stack trace:

- missing `file` field -> `KeyError` -> 500
- `threshold=abc` -> `ValueError` -> 500
- TF Serving down -> raw `requests` exception -> 500

Also `TFSObjectDetector.predict()` never checks the HTTP status. If TF Serving returns
an error the code fails later on `response.json()['predictions']` with a confusing
`KeyError`.

**Fix:** add Flask error handlers that return JSON like `{"error": "..."}` with the
right status (400 for bad input, 503 when TF Serving is unreachable). Add
`response.raise_for_status()` in the adapter.


### 5. No input validation

`threshold` is never checked, `threshold=5` or `threshold=-1` is accepted silently. The
uploaded file is never checked either, no size limit and no check that it is actually an
image.

Related bug: `__to_np_array()` does `.reshape((height, width, 3))`, so a grayscale or
RGBA image crashes with a shape error.

**Fix:** validate `threshold` is between 0 and 1, require the `file` field, set
`MAX_CONTENT_LENGTH` on the Flask app, and call `.convert("RGB")` before converting to
numpy.


