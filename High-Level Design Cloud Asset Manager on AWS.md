# High-Level Design: Cloud Asset Manager on AWS

This document describes the system as it runs today. Planned work is listed separately in section 11.

## 1. Purpose and scope

Cloud Asset Manager is a small web application for recording and managing IT assets such as servers and laptops: tag, hostname, IP address, operating system, location, assigned user, warranty dates and status. It is built as a production-like learning environment, with a private database, no stored credentials and a supervised service.

In scope: the EC2 host, Nginx, gunicorn, the Flask app, RDS MySQL, Secrets Manager, IAM and the network rules between them.

Out of scope: CI/CD, Grafana alerting and a load balancer. These are planned and appear in the roadmap.

## 2. Architecture at a glance

A request travels through these layers:

1. The user's browser sends an HTTP request to the Elastic IP.
2. The Internet Gateway delivers it into the VPC, and the `[Public]` security group allows port 80.
3. Nginx on the EC2 instance receives it and forwards it to gunicorn on `localhost:5000` or `unix:flaskapp.sock`.
4. A gunicorn worker runs the Flask application.
5. Flask opens a connection to RDS MySQL on port 3306 inside the private subnet, runs the query and renders an HTML page.
6. The response returns the same way.

At startup the application also reads its credentials from AWS Secrets Manager, using the IAM role attached to the instance. The existing architecture diagram in the repository README shows this layout.

## 3. Components

| Component | Role | In plain language |
| --- | --- | --- |
| Internet Gateway | Connects the VPC to the internet | The front door of the network |
| Elastic IP | Fixed public address on the EC2 instance | An address that does not change when the server restarts |
| `[Public]` security group | Allows SSH (22) from your IP and HTTP (80) from anywhere | A firewall attached to the server |
| EC2 instance (Ubuntu) | Runs everything except the database | The server, 908 MB RAM, no swap |
| Nginx | Public web entry point on port 80 | Receives visitors and passes requests to the app |
| gunicorn | Python application server, one master and three workers | Runs the Flask code and handles several requests at once |
| Flask application | Business logic and HTML pages | The actual app |
| systemd (`flask-app.service`) | Starts, stops and restarts gunicorn | The supervisor that keeps the app running |
| `wait_db.py` | Pre-start check run by systemd | A gate that waits until the database answers before the app starts |
| AWS Secrets Manager | Stores DB credentials and the Flask secret key | A locked vault so no passwords are in the code |
| IAM role (`instanceRole`) | Lets the instance read one secret | Permission for the server to open that vault, and nothing else |
| Amazon RDS MySQL 8.4 | The database, Single-AZ, private subnet, no public IP | Where the data lives |
| `[Private]` security group | Allows port 3306 only from the `[Public]` group | Only the web server may talk to the database |

## 4. Network and security design

**Placement.** The EC2 instance is in a public subnet with the Elastic IP. RDS is in a private subnet with no public IP and no Elastic IP, so it cannot be reached from the internet. The DB subnet group spans multiple Availability Zones because RDS requires that, although the database itself runs in one.

**Security group chain.**

| Group | Direction | Port | Source | Purpose |
| --- | --- | --- | --- | --- |
| `[Public]` | Inbound | 22 | Your IP | Administration |
| `[Public]` | Inbound | 80 | 0.0.0.0/0 | Public web traffic |
| `[Private]` | Inbound | 3306 | `[Public]` security group | Only the web server can reach MySQL |

Security groups are stateful, so replies to allowed connections need no extra inbound rule. Port 5000 is bound to localhost only and is not exposed.

**Identity and secrets.** The IAM role allows only `secretsmanager:GetSecretValue` on one secret, `production/cloud-asset-manager/secrets`. The secret holds `FLASK_SECRET_KEY`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME` and `DB_PORT`, and it is encrypted with the default AWS-managed key. No credentials are stored on disk or in the repository.

**Not present today.** HTTPS (port 80 only), user authentication, CSRF protection on form posts, and a web application firewall. These are the main security gaps and are listed in section 10.

## 5. Environment selection

The `FLASK_ENV` variable decides where configuration comes from:

- `production` (set in the systemd unit): secrets come from Secrets Manager. If the fetch fails, startup stops with an error. There is deliberately no silent fallback, so a production server can never quietly use a different database.
- Anything else: values come from a local `.env` file. The `.env` file is not committed and no local database exists on the server.

## 6. Startup flow

1. systemd starts `flask-app.service` after the network is online.
2. `ExecStartPre` runs `wait_db.py`. It loads the config (one Secrets Manager call), then tries to connect to MySQL with a 5 second timeout, backing off between attempts for up to 120 seconds.
3. When the connection succeeds, `wait_db.py` creates the `assets` table if it does not exist and exits with code 0. If it gives up, it exits with code 1.
4. On success, systemd starts gunicorn with `--preload`. The master loads the application once (a second Secrets Manager call) and then forks three workers.
5. On failure, systemd waits 10 seconds and tries again, up to five times in 30 minutes. After that the unit enters the `failed` state and stays there until `systemctl reset-failed` is run.

This arrangement keeps all import-time work (secrets fetch and table creation) out of the workers, so a worker that respawns never repeats it.

## 7. Failure behaviour

| Situation | What happens | Visible to systemd |
| --- | --- | --- |
| DB down when the service starts | `wait_db.py` retries for 120 s, fails, systemd retries up to the start limit, then `failed` | Yes |
| DB comes back during retries | The next attempt succeeds and gunicorn starts by itself | Yes |
| DB goes down while running, connection refused | Requests return HTTP 500 within moments, workers keep running | No |
| DB goes down while running, packets dropped | Each request fails after at most 5 s (connect timeout), returns 500 | No |
| DB returns while running | Requests return 200 again with no restart, because every query opens a fresh connection | No |
| A gunicorn worker hangs for 60 s | gunicorn kills and replaces it. The replacement forks from the master and does no import-time work | No |
| Master process dies | systemd restarts it under the start limit | Yes |

A runtime database outage is deliberately treated as an application-level failure, not a service failure. Restarting gunicorn cannot repair a database, and the app recovers on its own when the database returns.

## 8. Operations

- **Logging.** gunicorn access and error logs go to stdout and then to the systemd journal (`journalctl -u flask-app`).
- **Resource limits.** `MemoryHigh=300M` throttles and `MemoryMax=400M` is the kill line, on a host with 908 MB and no swap. Measured use is roughly 60 to 130 MB.
- **Planned alert signals.** Two separate signals: an elevated rate of HTTP 5xx responses or a failing `/health` route means the app is up but the database is not. The `flask-app.service` unit in `failed` state means the service cannot start.

## 9. Known limitations and risks

1. No HTTPS, authentication or CSRF protection.
2. A single EC2 instance and a Single-AZ database mean no automatic failover.
3. Each database query opens a new connection, and the index page opens two.
4. With `--preload`, a code change needs a full restart, not a graceful reload.
5. After the start limit trips, the service stays down until someone resets it.
6. `config.py` does not validate its values. A missing `DB_PORT` raises a `TypeError`, and some boto3 errors are not caught.

## 10. Roadmap

From the README and this work, not yet implemented:

1. `/health` route (`SELECT 1`, 200 or 503) for monitoring and deploy checks.
2. Grafana alerting on 5xx rate and on the unit's `failed` state.
3. CI/CD, with the unit file and `wait_db.py` stored in the repository.
4. Application Load Balancer with Auto Scaling across Availability Zones.
5. CloudWatch alarms, Route 53 domain, AWS WAF and HTTPS.
6. VPC endpoint for Secrets Manager.
7. Terraform for repeatable infrastructure.
8. CSRF protection, `db.py` refactor and `config.py` validation.

## 12. Assumptions and open items

- Subnet CIDRs are placeholders in the diagram and are not recorded here.
- The S3 permission shown in the diagram is being removed and is not part of this design.
