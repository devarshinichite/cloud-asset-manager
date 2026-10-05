# Cloud Asset Manager

Cloud Asset Manager is a Python/Flask application for organizing and managing cloud asset records.

## Overview

- Manage cloud asset records.
- Store data in a relational database.
- Expose functionality through a Flask web application.
- Use environment-based configuration for local and deployment settings.

## Tech stack

This project uses Python and Flask, with dependencies managed through pip/requirements files (or the repository's actual Python dependency manifest).

Typical project stack for this repository:

- Python 3
- Flask
- SQLAlchemy or a project-specific database layer
- A relational database such as PostgreSQL or SQLite for local development
- Flask extensions or helpers as used by the app
- pytest for tests

## Getting started

### Prerequisites

- Python 3.x
- pip
- A virtual environment tool such as `venv`
- A local database or configured cloud database connection, depending on how the app is set up

### Local setup

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install Python dependencies from the project requirements file.

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use .venv\Scripts\activate
pip install -r requirements.txt
```

4. Create a local environment file (for example, `.env`) with the configuration values the app expects.
5. Run the Flask development server.

```bash
flask run
```

If the app uses a custom startup command, use the command defined in the project instead of assuming a generic toolchain.

## Configuration

Store configuration in environment variables or a `.env` file. Do not hard-code secrets.

Common variables may include:

| Variable | Description |
|---|---|
| `FLASK_SECRET` | Flask secret key |
| `DB_HOST` | Database host |
| `DB_PORT` | Database port |
| `DB_NAME` | Database name |
| `DB_USER` | Database username |
| `DB_PASSWORD` | Database password |

Use the exact variable names defined by the project. Do not add Node/npm-specific configuration unless the app actually uses it.

## Development workflow

1. Create a feature branch.
2. Install dependencies in a virtual environment.
3. Implement the Flask route, service, and data-layer changes.
4. Run the project's Python tests and linting commands.
5. Verify the app locally before opening a pull request.

Typical commands may include:

```bash
pytest
flask --app app run
```

Use the repository's actual scripts and commands rather than assuming a JavaScript toolchain.

## Application design

This application follows a standard Flask server structure, typically with separation between:

- Routes/controllers: HTTP endpoints and request handling
- Services/business logic: validation and domain logic
- Data access layer: database queries and persistence
- Templates/static files: UI rendering and frontend assets if applicable

The application should validate user input on the server side, never trust client-side data as the only protection, and use parameterized database queries.

## Deployment

Deployment should use the environment and infrastructure actually configured for this repository. If the app is hosted in AWS, use the project's approved deployment configuration, IAM roles, and secrets management.

## Security

- Use environment variables or a managed secret store for credentials.
- Keep database credentials out of source control.
- Enforce HTTPS in production.
- Validate inputs and protect against common web vulnerabilities.
- Use least-privilege access for database and cloud resources.
