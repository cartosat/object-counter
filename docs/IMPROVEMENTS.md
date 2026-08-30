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


### 6. `print()` used for logging

`TFSObjectDetector` currently uses `print()` for debugging output, including prediction data.

**Fix:** use the `logging` module. `logger.debug()` for the prediction dump,
`logger.info()` for the request to TF Serving.


### 7. Hardcoded relative paths

Two files are opened with paths relative to the working directory:

- `counter/adapters/mscoco_label_map.json` in `object_detector.py`
- `counter/resources/arial.ttf` in `debug.py`

So the app only runs if you start it from the repo root. Running `pytest` from any other
folder fails with an `OSError`. 

**Fix:** resolve both with `Path(__file__).parent / "..."`. For the label map, make it a
constructor argument so each detector can have its own.


### 8. `.env.example` file

The app has a lot of env vars (`ENV`, `TFS_HOST`, `TFS_PORT`, `MONGO_*`,
`POSTGRES_*`, `MODEL_NAME`) but these are not written down anywhere. We need to
find them by reading `config.py`.

**Fix:** add a `.env.example` listing every variable with its default, and mention it in
the README.


### 9. Makefile, docker compose, Dockerfile

Setup used around 15 commands spread over 5 README sections, and nothing was
automated.

Now there is a `docker-compose.yml` for TF Serving, MongoDB and Postgres, and a
`Makefile` so setup is `make setup && make up && make run`.

`Dockerfile` is missing. So the app runs on the host while everything else 
runs in containers.

**Fix:** add a `Dockerfile` and an `app` service in compose, so the whole thing comes up
with one command.

---

## Application architecture

### 10. Debug image drawing sits inside the domain

`CountDetectedObjects` calls `__debug_image()` two times for each request, which opens the image and writes two JPEGs into `tmp/debug/`. 
The guard is `if __debug__`, which is `True` unless we run Python with `-O`, so this happens on every production request.

Two problems with it:

- writing files to disk is infrastructure work, it should not belong to domain layer.
`Image.open(image)` leaves the `BytesIO` at end-of-file.

**Fix:** take the `draw` call out of `actions.py`. Either drop `debug.py` or put it
behind a small port with a no-op default, switched on by a `DEBUG_IMAGES` env var.


### 11. `config.py` - Replace dynamic factory lookup

```python
count_action_fn = f"{env}_count_action"
return globals()[count_action_fn]()
```

The configuration currently builds a function name dynamically and looks
it up using `globals()`. It works, but wrong env values e.g `ENV=production`
will give  `KeyError: 'production_count_action'`.

**Fix:** use an explicit dict mapping env to factory, and raise a clear error listing the
valid values when the key is missing.


### 12. Missing type hints

The ports have proper type hints, but the actions do not have:

```python
def predict(self, image: BinaryIO) -> List[Prediction]     # ports.py, typed
def execute(self, image, threshold) -> CountResponse       # actions.py, not typed
```

Reading `execute()` you cannot tell what `image` is, you have to go find the caller.
Same for both repo `__init__` methods and `_read_request()` in `webapp.py`.

**Fix:** annotate the parameters, `image: BinaryIO, threshold: float`. Simple to do and
it documents the code better.

---

## Testing

### 13. Separate development dependencies

Module `pytest` is in `requirements.txt`, so it gets installed in production too.

**Fix:** 
    1. Move it to `requirements-dev.txt` and install that only for development.
    2. Another way would be using `pyproject.toml` for handling environment specific dependencies.


### 14. adapter does not tests.

The domain and API have tests, but the database adapters are not covered
sufficiently.
This is important because adapter code contains integration logic and
can fail even when the domain tests pass.

**Fix:** write the tests once against the `ObjectCountRepo` interface and run them
against all three implementations with a parametrized fixture.

---

## Docs

### 15. README says the wrong model

The README links the Kaggle OpenImages MobileNet, but the setup script downloads the
COCO one and the label map is MS-COCO. Small thing but it is confusing if you follow the
link.

**Fix:** point the link at the model that is actually used.
