import os
import uuid

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

ASSET_FIELDS = (
    "asset_tag",
    "hostname",
    "ip_address",
    "operating_system",
    "cpu",
    "ram_gb",
    "asset_type",
    "location",
    "assigned_user",
    "purchase_date",
    "warranty_expiry",
    "status",
    "notes",
)


def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
    )


def initialize_database():
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS assets (
                asset_key CHAR(36) NOT NULL PRIMARY KEY,
                asset_tag VARCHAR(64) NOT NULL UNIQUE,
                hostname VARCHAR(255) NOT NULL,
                ip_address VARCHAR(45) NOT NULL,
                operating_system VARCHAR(120) NOT NULL,
                cpu VARCHAR(120) NULL,
                ram_gb DECIMAL(8, 2) NULL,
                asset_type VARCHAR(80) NOT NULL,
                location VARCHAR(160) NOT NULL,
                assigned_user VARCHAR(160) NULL,
                purchase_date DATE NULL,
                warranty_expiry DATE NULL,
                status VARCHAR(40) NOT NULL DEFAULT 'Active',
                notes TEXT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_assets_hostname (hostname),
                INDEX idx_assets_ip_address (ip_address),
                INDEX idx_assets_type (asset_type),
                INDEX idx_assets_location (location),
                INDEX idx_assets_status (status)
            )
            """
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def get_assets(filters):
    conditions = []
    parameters = []
    search = filters.get("search", "")
    if search:
        search_term = f"%{search}%"
        conditions.append(
            "(asset_tag LIKE %s OR hostname LIKE %s OR ip_address LIKE %s "
            "OR assigned_user LIKE %s)"
        )
        parameters.extend([search_term] * 4)
    for field in ("asset_type", "location", "status"):
        value = filters.get(field, "")
        if value:
            conditions.append(f"{field} = %s")
            parameters.append(value)

    query = "SELECT * FROM assets"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY updated_at DESC, hostname ASC"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(query, parameters)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def get_filter_options():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        options = {}
        for field in ("asset_type", "location"):
            cursor.execute(
                f"SELECT DISTINCT {field} FROM assets ORDER BY {field}"
            )
            options[field] = [row[field] for row in cursor.fetchall()]
        return options
    finally:
        cursor.close()
        connection.close()


def get_asset(asset_key):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM assets WHERE asset_key = %s", (asset_key,))
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def create_asset(values):
    fields = ", ".join(ASSET_FIELDS)
    placeholders = ", ".join(["%s"] * len(ASSET_FIELDS))
    parameters = [values.get(field) for field in ASSET_FIELDS]
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"INSERT INTO assets (asset_key, {fields}) "
            f"VALUES (%s, {placeholders})",
            (str(uuid.uuid4()), *parameters),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def update_asset(asset_key, values):
    assignments = ", ".join(f"{field} = %s" for field in ASSET_FIELDS)
    parameters = [values.get(field) for field in ASSET_FIELDS]
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"UPDATE assets SET {assignments} WHERE asset_key = %s",
            (*parameters, asset_key),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def decommission_asset(asset_key):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE assets SET status = 'Decommissioned' WHERE asset_key = %s",
            (asset_key,),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def delete_asset(asset_key):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM assets WHERE asset_key = %s", (asset_key,))
        connection.commit()
    finally:
        cursor.close()
        connection.close()