import json
import os
import sqlite3
from datetime import datetime

DATABASE_NAME = os.environ.get("DATABASE_PATH", "hospital.db")
DATA_JSON_PATH = os.path.join(os.path.dirname(__file__), "initial_data.json")


def get_db_connection(db_path=None):
    """Establishes connection to SQLite database."""
    path = db_path or os.environ.get("DATABASE_PATH", DATABASE_NAME)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    """
    Initializes schema and seeds 50 Indian doctors and patients from JSON.
    Supports manual patient entry with name, age, address, and phone number.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT NOT NULL,
            consultation_fee REAL NOT NULL DEFAULT 500.0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            age INTEGER,
            address TEXT,
            email TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            slot_time TEXT NOT NULL,
            fee REAL NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'CANCELLED')),
            refund_amount REAL DEFAULT 0.0,
            refund_percentage REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (doctor_id) REFERENCES doctors (id),
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
    """)

    # Seed doctors if doctors table has fewer than 50
    cursor.execute("SELECT COUNT(*) AS count FROM doctors")
    doc_count = cursor.fetchone()["count"]

    if doc_count < 50 and os.path.exists(DATA_JSON_PATH):
        with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        doctors_list = data.get("doctors", [])
        cursor.execute("DELETE FROM doctors")

        doctor_tuples = [
            (d["name"], d["specialization"], d["consultation_fee"])
            for d in doctors_list
        ]
        cursor.executemany(
            "INSERT INTO doctors (name, specialization, consultation_fee) "
            "VALUES (?, ?, ?)",
            doctor_tuples
        )

    # Seed default patients from JSON if table empty (for tests/fallback)
    cursor.execute("SELECT COUNT(*) AS count FROM patients")
    pat_count = cursor.fetchone()["count"]
    if pat_count == 0 and os.path.exists(DATA_JSON_PATH):
        with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        patients_list = data.get("patients", [])
        patient_tuples = [
            (p["name"], f"9876543{i:03d}", 30 + (i % 35),
             "Mumbai, India", p.get("email"))
            for i, p in enumerate(patients_list)
        ]
        cursor.executemany(
            "INSERT INTO patients (name, phone, age, address, email) "
            "VALUES (?, ?, ?, ?, ?)",
            patient_tuples
        )

    conn.commit()
    conn.close()


def parse_datetime(dt_str):
    """Parses standard ISO or YYYY-MM-DD HH:MM string to datetime."""
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid datetime format: {dt_str}")
