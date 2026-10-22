# Cloud Asset Manager

Cloud Asset Manager is a Flask application for managing cloud asset records. It stores application data in an RDS database and runs on an EC2 instance.

## Architecture

- **EC2:** Hosts the Flask application, served by Gunicorn and Nginx.
- **RDS:** Stores application data.
- **AWS Secrets Manager:** Stores the Flask secret key and RDS credentials.
- **IAM role:** Allows the EC2 instance to retrieve the required secrets using least-privilege permissions.
- **`config.py`:** Centralizes application configuration.

## Requirements

- Python 3
- pip and `venv`
- The dependencies listed in `requirements.txt`
- For local development, the configuration and database access required by the application

## Local development

1. Clone the repository and enter the project directory.
2. Create and activate a virtual environment, then install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure the values required by the application. Refer to `config.py` for the exact settings and supported configuration sources. Do not commit credentials or secret values.
4. Start the development server:

   ```bash
   flask run
   ```

Use the application's configured Flask entry point if `flask run` does not discover it automatically.

## Configuration and secrets

`config.py` is the central place to review how the application loads its settings. Use the configuration names and sources defined there rather than assuming variable names.

In the AWS deployment, the Flask secret key and RDS credentials are stored in Secrets Manager. The EC2 instance accesses them through its attached IAM role. Do not put long-lived AWS credentials or secret values in source code.

## Tests

Run the project tests, if present, from the repository root:

```bash
pytest
```

## Deployment overview

The deployed request path is:

1. Nginx receives the request and forwards it to Gunicorn.
2. Gunicorn serves the Flask application.
3. Database-backed requests connect to RDS.
4. The application retrieves required secrets from Secrets Manager using the EC2 instance role.

The `flask-app.service` systemd unit manages the application service. Confirm its environment, working directory, startup command, and restart settings, CPU and memory limit when deploying or troubleshooting. See [the troubleshooting guide](docs/TROUBLESHOOTING.md) for service, Nginx, database, and secrets-access checks.

## Security

- Keep database credentials and the Flask secret key out of source control.
- Grant the EC2 IAM role only the permissions needed to retrieve the application’s specific secrets.
- Restrict EC2 and RDS network access to the required ports and sources.
- Validate user input on the server and use safe, parameterized database operations.

## HLD & LLD 

Refer 
[HLD](https://github.com/devarshinichite/cloud-asset-manager/blob/master/High-Level%20Design%20Cloud%20Asset%20Manager%20on%20AWS.md)
[LLD](https://github.com/devarshinichite/cloud-asset-manager/blob/master/Low-Level%20Design%20Cloud%20Asset%20Manager.md)
