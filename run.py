from flask import Flask, render_template
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


# -----------------------------
# Database connection
# -----------------------------
def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME")
    )


# -----------------------------
# Create table + insert data
# -----------------------------
def initialize_database():

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS asset (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL,
            age INT
        )
    """)

    # Check whether data already exists
    cursor.execute("SELECT COUNT(*) FROM asset")
    count = cursor.fetchone()[0]

    if count == 0:

        asset = [
            ("John", "john@example.com", 25),
            ("Alice", "alice@example.com", 30),
            ("Bob", "bob@example.com", 22)
        ]

        cursor.executemany("""
            INSERT INTO asset (name, email, age)
            VALUES (%s, %s, %s)
        """, asset)

    connection.commit()

    cursor.close()
    connection.close()


# -----------------------------
# Display data
# -----------------------------
@app.route("/")
def asset():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name, email, age
        FROM asset
        ORDER BY id
    """)

    asset = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "index.html",
        asset=asset
    )


# -----------------------------
# Application startup
# -----------------------------
if __name__ == "__main__":

    initialize_database()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
