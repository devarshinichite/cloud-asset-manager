# Low-Level Design: Cloud Asset Manager

This document covers the code, data and runtime configuration behind the High-Level Design. It is based on `app.py`, `db.py`, `config.py`, `wait_db.py`, the systemd unit and the logs from testing.

## 1. Project layout

| Path | Purpose |
| --- | --- |
| `/opt/cloud-asset-manager/app.py` | Flask application: routes, form handling, validation |
| `db.py` | All database access |
| `config.py` | Environment-aware settings, fetches secrets in production |
| `wait_db.py` | Pre-start gate run by systemd |
| `wsgi.py` | gunicorn entry point exposing `app` (Assumption: not reviewed) |
| `templates/` | `index.html`, `asset_form.html`, `asset_details.html` (names taken from `render_template` calls) |
| `static/` | `style.css` (seen in access logs), other files not reviewed |
| `venv/` | Python virtual environment, Python 3.14, gunicorn 26.2.0 |
| `.env` | Local development settings only, not committed, not on the server |

## 2. config.py

A `Config` class is instantiated once at import time and exposed as `settings`.

**Environment selection.** `APP_ENV` is read from the `FLASK_ENV` environment variable and defaults to `development`.

- `production`: `_fetch_aws_secrets()` creates a boto3 Secrets Manager client in `ap-south-1` and calls `get_secret_value` for `production/cloud-asset-manager/secrets`, then parses the JSON string. On `ClientError` it prints a message and re-raises, so the process stops.
- Any other value: `_fetch_local_env()` reads the same keys from environment variables, after `load_dotenv()` has loaded a local `.env` file if one exists. `DB_PORT` defaults to 3306 here.

**Exposed attributes:** `FLASK_SECRET_KEY`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`, `DB_PORT` (converted to `int`).

**Defects to fix later:**

- A missing `DB_PORT` in the secret raises `TypeError` at `int(None)`.
- Only `ClientError` is caught. `NoCredentialsError` and `EndpointConnectionError` are `BotoCoreError` subclasses and are not caught, although they still stop the process.
- `raise e` should be a bare `raise`.
- No validation that required keys are present.
- `FLASK_ENV` was removed as a Flask setting in version 2.3. It works here only because it is read by this project's own code, so renaming it (for example `APP_ENV`) would avoid confusion.

## 3. db.py

**Connection.** `get_db_connection()` calls `mysql.connector.connect()` with host, port, user, password and database from `settings`, and `connection_timeout=5`. Every function below opens its own connection and closes it in a `finally` block.

| Function | Operation | Notes |
| --- | --- | --- |
| `initialize_database()` | `CREATE TABLE IF NOT EXISTS assets` | Called by `wait_db.py`, no longer at import time |
| `get_assets(filters)` | `SELECT *` with optional `WHERE`, ordered by `updated_at DESC, hostname ASC` | `search` matches asset tag, hostname, IP and assigned user with `LIKE`. `asset_type`, `location` and `status` are exact matches. Values are passed as parameters |
| `get_filter_options()` | `SELECT DISTINCT` for `asset_type` and `location` | Column names come from a fixed tuple, so the f-string SQL is safe today |
| `get_asset(asset_key)` | Single row by key | Returns a dict or `None` |
| `create_asset(values)` | `INSERT` with a new `uuid4` as `asset_key` | Raises `IntegrityError` on a duplicate `asset_tag` |
| `update_asset(asset_key, values)` | `UPDATE` of all 13 editable fields | Same `IntegrityError` behaviour |
| `decommission_asset(asset_key)` | Sets `status = 'Decommissioned'` | Soft retirement |
| `delete_asset(asset_key)` | `DELETE` by key | Permanent |

The eight functions repeat the same connect, cursor, try and close pattern. A single helper or context manager would remove most of that duplication.

## 4. Database schema

Table `assets` (MySQL 8.4):

| Column | Type | Constraints |
| --- | --- | --- |
| `asset_key` | `CHAR(36)` | Primary key, a UUID |
| `asset_tag` | `VARCHAR(64)` | Not null, unique |
| `hostname` | `VARCHAR(255)` | Not null, indexed |
| `ip_address` | `VARCHAR(45)` | Not null, indexed (long enough for IPv6) |
| `operating_system` | `VARCHAR(120)` | Not null |
| `cpu` | `VARCHAR(120)` | Null |
| `ram_gb` | `DECIMAL(8,2)` | Null |
| `asset_type` | `VARCHAR(80)` | Not null, indexed |
| `location` | `VARCHAR(160)` | Not null, indexed |
| `assigned_user` | `VARCHAR(160)` | Null |
| `purchase_date` | `DATE` | Null |
| `warranty_expiry` | `DATE` | Null |
| `status` | `VARCHAR(40)` | Not null, default `Active`, indexed |
| `notes` | `TEXT` | Null |
| `created_at` | `TIMESTAMP` | Default current time |
| `updated_at` | `TIMESTAMP` | Default current time, updated automatically on change |

## 5. app.py

The Flask app sets `SECRET_KEY` from `settings.FLASK_SECRET_KEY`. Valid statuses are `Active`, `In repair`, `Retired` and `Decommissioned`.

**Routes**

| Route | Methods | Behaviour |
| --- | --- | --- |
| `/` | GET | Lists assets, applies the `search`, `asset_type`, `location` and `status` query filters, loads the filter dropdown options |
| `/assets/new` | GET, POST | Shows the form, or validates and creates an asset |
| `/assets/<asset_key>` | GET | Shows one asset, 404 if missing |
| `/assets/<asset_key>/edit` | GET, POST | Shows the form, or validates and updates, 404 if missing |
| `/assets/<asset_key>/decommission` | POST | Sets status to `Decommissioned`, 404 if missing |
| `/assets/<asset_key>/delete` | POST | Deletes the asset, 404 if missing |

**Form handling.** `form_values()` trims each field and turns empty optional fields into `None`. `validate_form_values()` checks that `asset_tag`, `hostname`, `ip_address`, `operating_system`, `asset_type` and `location` are present, that the status is allowed, that `ram_gb` is a non-negative decimal, and that dates parse as `YYYY-MM-DD`. It returns an error message or `None`.

**Responses.** Validation failure returns the form again with HTTP 400. A duplicate asset tag returns HTTP 409. Success flashes a message and redirects. Any other database error is not caught and becomes HTTP 500.

**Gaps:**

- No CSRF token on the POST routes, and no authentication.
- The edit, decommission and delete routes fetch the row first and then run a second statement, so they open two connections. Checking `cursor.rowcount` would avoid the first query.
- `IP address` is only checked for presence, not format.

## 6. wait_db.py

Runs before gunicorn, as the service user, with the working directory set to the project root.

1. Importing `config` loads the settings, which makes the single Secrets Manager call in production.
2. Loop: try to connect with `connection_timeout=5`, close it, then call `initialize_database()`.
3. On success, print `DB ready (attempt N)` and exit 0.
4. On `mysql.connector.Error`, print `DB not ready (attempt N)` and wait. The delay starts at 2 s and doubles up to a cap of 15 s.
5. When the next wait would pass the 120 s deadline, print `Giving up after 120s` and exit 1.

The retries reuse the settings already in memory, so they make no further AWS calls. An import error (for example from `config`) exits with a traceback and code 1, which systemd treats as a failed start.

## 7. systemd unit (`/etc/systemd/system/flask-app.service`)

| Setting | Value | Reason |
| --- | --- | --- |
| `After` / `Wants` | `network-online.target` | Wait for the network |
| `StartLimitIntervalSec` / `StartLimitBurst` | 1800 / 5 | At most five start attempts in 30 minutes. These belong in `[Unit]` |
| `User` / `Group` | `ubuntu` / `www-data` | Unprivileged service user |
| `WorkingDirectory` | `/opt/cloud-asset-manager` | Lets `wait_db.py` import `config` and `db` |
| `Environment` | `FLASK_ENV=production` | Selects Secrets Manager |
| `ExecStartPre` | `venv/bin/python wait_db.py` | Database gate |
| `TimeoutStartSec` | 180 | Longer than the 120 s retry window |
| `Restart` / `RestartSec` | `on-failure` / 10 s | Restart after a failure, with a pause |
| `MemoryHigh` / `MemoryMax` | 300M / 400M | Throttle, then kill |
| `CPUQuota` | Confirm on the server | Recommended value was 100% |
| Logs | `StandardOutput` and `StandardError` to the journal | Read with `journalctl` |

## 8. gunicorn runtime

Command: `gunicorn --workers 3 --bind 127.0.0.1:5000 --preload --timeout 60 --graceful-timeout 30 --access-logfile - --error-logfile - wsgi:app`.

- **Worker class:** sync, the default. Each worker handles one request at a time, so three workers serve three concurrent requests.
- **`--preload`:** the application is imported once in the master before forking. Workers share that memory, which is why total use dropped from about 128 MB to about 61 MB after the change.
- **`--timeout 60`:** a worker silent for 60 s is killed and replaced. Database connects are capped at 5 s, so a normal outage never reaches this.
- **Control socket:** gunicorn 26.2.0 creates `/home/ubuntu/.gunicorn/gunicorn.ctl`. It is harmless and can be ignored.
- **Code changes** need a full `systemctl restart` because of `--preload`.

## 9. Nginx

The live configuration listens on port 80 and passes requests to `http://127.0.0.1:5000` or `unix:flask-app.sock`, with `Host`, `X-Real-IP`, `X-Forwarded-For` and `X-Forwarded-Proto` headers and 90 s proxy timeouts. The README's `proxy_pass` to a Unix socket is out of date. Replace this section with the output of `sudo nginx -T` once reviewed.

If Nginx sits in front, gunicorn's access log shows `127.0.0.1` for every request. The real client address is in Nginx's own log or the `X-Forwarded-For` header.

## 10. Error handling matrix

| Error | Where | Result |
| --- | --- | --- |
| Secrets Manager `ClientError` | `config.py` import | Process stops, systemd treats the start as failed |
| Other boto3 error or missing key | `config.py` import | Process stops with a traceback |
| DB unreachable at start | `wait_db.py` | Retries 120 s, exits 1 |
| DB unreachable at runtime | Any route | Uncaught exception, HTTP 500, logged with a traceback, worker survives |
| Duplicate asset tag | create and edit | HTTP 409 and a flash message |
| Invalid form input | create and edit | HTTP 400 and a flash message |
| Unknown asset key | detail, edit, decommission, delete | HTTP 404 |

## 11. Known defects and technical debt

1. No CSRF protection or authentication.
2. `config.py` validation and exception handling, as listed in section 2.
3. Repeated connection code in `db.py` and one new connection per query.
4. Two database connections for the index page and for the edit, decommission and delete routes.
5. No `/health` route.
6. The IP address field is not format-checked.
7. `FLASK_ENV` naming.
