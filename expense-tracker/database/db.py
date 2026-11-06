import sqlite3
import os
from datetime import date, timedelta
from werkzeug.security import generate_password_hash


# ------------------------------------------------------------------ #
# Database path                                                       #
# ------------------------------------------------------------------ #

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "spendly.db"
)


# ------------------------------------------------------------------ #
# get_db()                                                            #
# ------------------------------------------------------------------ #

def get_db():
    """Return a SQLite connection with row_factory and foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# ------------------------------------------------------------------ #
# init_db()                                                           #
# ------------------------------------------------------------------ #

def init_db():
    """Create all tables using CREATE TABLE IF NOT EXISTS.
    Safe to call multiple times — will not drop or alter existing data.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

    conn.commit()
    conn.close()


# ------------------------------------------------------------------ #
# seed_db()                                                           #
# ------------------------------------------------------------------ #

def seed_db():
    """Insert demo user and 8 sample expenses on first run only.
    If the users table already contains data, returns immediately
    to prevent duplicate seed records.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Idempotency guard — skip if any users already exist
    count = cursor.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
    if count > 0:
        conn.close()
        return

    # Insert demo user with hashed password
    hashed = generate_password_hash("demo123")
    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?);",
        ("Demo User", "demo@spendly.com", hashed)
    )
    user_id = cursor.lastrowid

    # Generate dates spread across the current month
    today = date.today()
    first_of_month = today.replace(day=1)

    # 8 sample expenses covering all 7 categories
    expenses = [
        (user_id, 450.0,  "Food",          (first_of_month + timedelta(days=1)).isoformat(),  "Groceries from BigBasket"),
        (user_id, 120.0,  "Transport",     (first_of_month + timedelta(days=3)).isoformat(),  "Uber to office"),
        (user_id, 1500.0, "Bills",         (first_of_month + timedelta(days=5)).isoformat(),  "Electricity bill"),
        (user_id, 800.0,  "Health",        (first_of_month + timedelta(days=7)).isoformat(),  "Pharmacy — medicines"),
        (user_id, 350.0,  "Entertainment", (first_of_month + timedelta(days=10)).isoformat(), "Movie tickets"),
        (user_id, 2200.0, "Shopping",      (first_of_month + timedelta(days=14)).isoformat(), "New headphones"),
        (user_id, 150.0,  "Other",         (first_of_month + timedelta(days=18)).isoformat(), "Stationery supplies"),
        (user_id, 600.0,  "Food",          (first_of_month + timedelta(days=21)).isoformat(), "Dinner at restaurant"),
    ]

    cursor.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?);",
        expenses
    )

    conn.commit()
    conn.close()
