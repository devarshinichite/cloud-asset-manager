import os
import json
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load local .env file ONLY if it exists (for local development)
load_dotenv()

class Config:
    """Central configuration resolver for Flask and Database setups."""
    
    # 1. Determine environment (default to development if not explicitly set)
    APP_ENV = os.getenv('FLASK_ENV', 'development')
    
    def __init__(self):
        if self.APP_ENV == 'production':
            # Run production mode: Pull completely from memory using AWS Secrets Manager
            self._secrets = self._fetch_aws_secrets()
        else:
            # Run local development mode: Pull directly from your local system/.env file
            self._secrets = self._fetch_local_env()

        # 2. Map standard properties cleanly for the rest of your application
        self.FLASK_SECRET_KEY = self._secrets.get('FLASK_SECRET_KEY')
        self.DB_USER = self._secrets.get('DB_USER')
        self.DB_PASSWORD = self._secrets.get('DB_PASSWORD')
        self.DB_HOST = self._secrets.get('DB_HOST')
        self.DB_NAME = self._secrets.get('DB_NAME')
        self.DB_PORT = int(self._secrets.get('DB_PORT'))

    def _fetch_aws_secrets(self):
        """Retrieves and deserializes production keys directly from AWS."""
        secret_name = "production/cloud-asset-manager/secrets"
        region_name = "ap-south-1"

        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager', region_name=region_name)

        try:
            response = client.get_secret_value(SecretId=secret_name)
            return json.loads(response['SecretString'])
        except ClientError as e:
            print(f"CRITICAL: Failed fetching production secrets from AWS: {e}")
            raise e

    def _fetch_local_env(self):
        """Fallback that reads local developer configurations standardly."""
        return {
            'FLASK_SECRET_KEY': os.getenv('FLASK_SECRET_KEY'),
            'DB_USER': os.getenv('DB_USER'),
            'DB_PASSWORD': os.getenv('DB_PASSWORD'),
            'DB_HOST': os.getenv('DB_HOST'),
            'DB_NAME': os.getenv('DB_NAME'),
            'DB_PORT': os.getenv('DB_PORT', 3306)
        }

# Instantiate a single config instance to import across modules
settings = Config()
