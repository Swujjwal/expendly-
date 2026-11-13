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
# seed_db() & seed_user_expenses()                                    #
# ------------------------------------------------------------------ #

def seed_user_expenses(user_id):
    """Insert sample expenses for a user across all standard categories."""
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

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?);",
            expenses
        )
        conn.commit()
        return len(expenses)
    finally:
        conn.close()


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
    conn.commit()
    conn.close()

    seed_user_expenses(user_id)


# ------------------------------------------------------------------ #
# User operations                                                     #
# ------------------------------------------------------------------ #

def get_user_by_email(email):
    """Retrieve a user row by email (case-insensitive lookup).
    Returns sqlite3.Row if found, None otherwise.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        user = cursor.execute(
            "SELECT * FROM users WHERE LOWER(email) = LOWER(?);",
            (email.strip(),)
        ).fetchone()
        return user
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Retrieve a user row by user ID.
    Returns sqlite3.Row if found, None otherwise.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        user = cursor.execute(
            "SELECT * FROM users WHERE id = ?;",
            (user_id,)
        ).fetchone()
        return user
    finally:
        conn.close()


def create_user(name, email, password_hash):
    """Insert a new user record into the database.
    Returns the new user ID on success, or None if the email already exists.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?);",
            (name.strip(), email.strip().lower(), password_hash)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def update_user_name(user_id, name):
    """Update a user's display name. Returns True on success, False otherwise."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET name = ? WHERE id = ?;",
            (name.strip(), user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()



def get_user_stats(user_id, start_date=None, end_date=None):
    """Calculate summary stats for a user's expenses with optional date range.
    Returns a dict with: total_count, total_spent.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = """
            SELECT 
                COUNT(*) as total_count,
                COALESCE(SUM(amount), 0.0) as total_spent
            FROM expenses
            WHERE user_id = ?
        """
        params = [user_id]
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        row = cursor.execute(query, params).fetchone()
        return {
            "total_count": int(row["total_count"]) if row else 0,
            "total_spent": float(row["total_spent"]) if row else 0.0
        }
    finally:
        conn.close()


def get_user_expenses(user_id, limit=None, offset=0, start_date=None, end_date=None):
    """Retrieve expenses for a user ordered by date descending with optional date range."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = "SELECT id, user_id, amount, category, date, description, created_at FROM expenses WHERE user_id = ?"
        params = [user_id]
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC, id DESC"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_category_breakdown(user_id, start_date=None, end_date=None):
    """Retrieve spending total and transaction count grouped by category for a user with optional date range."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = """
            SELECT category, COUNT(*) as count, COALESCE(SUM(amount), 0.0) as total_amount
            FROM expenses
            WHERE user_id = ?
        """
        params = [user_id]
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " GROUP BY category ORDER BY total_amount DESC;"
        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ------------------------------------------------------------------ #
# Expense Categories & Creation Operations                            #
# ------------------------------------------------------------------ #

EXPENSE_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other"
]


def get_standard_categories():
    """Return the list of standard expense categories."""
    return list(EXPENSE_CATEGORIES)


def create_expense(user_id, amount, category, date, description=None):
    """Insert a new expense record for a user.

    Parameters:
        user_id (int): Foreign key referencing users(id).
        amount (float): Transaction amount (must be positive).
        category (str): Valid category name.
        date (str): Transaction date in YYYY-MM-DD ISO format.
        description (str, optional): Short note or transaction detail.

    Returns:
        int: The auto-incremented primary key ID of the newly created expense.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        desc_val = description.strip() if (description and description.strip()) else None
        cursor.execute(
            """
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?);
            """,
            (
                user_id,
                round(float(amount), 2),
                category.strip(),
                str(date).strip(),
                desc_val
            )
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_expense_by_id(expense_id):
    """Retrieve an expense record by its primary key ID.
    Returns dict if found, None otherwise.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        row = cursor.execute(
            "SELECT id, user_id, amount, category, date, description, created_at FROM expenses WHERE id = ?;",
            (expense_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_expense_by_id(expense_id, user_id):
    """Retrieve an expense record by ID ensuring strict user ownership.

    Parameters:
        expense_id (int): Primary key of the expense.
        user_id (int): ID of the authenticated user.

    Returns:
        dict: Expense dictionary if found and owned by user, None otherwise.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        row = cursor.execute(
            """
            SELECT id, user_id, amount, category, date, description, created_at
            FROM expenses
            WHERE id = ? AND user_id = ?;
            """,
            (expense_id, user_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_expense(expense_id, user_id, amount, category, date, description=None):
    """Update an existing expense record belonging to a specific user.

    Parameters:
        expense_id (int): ID of the expense to update.
        user_id (int): ID of the authenticated owner.
        amount (float): Updated transaction amount (positive number).
        category (str): Valid category name.
        date (str): Updated date in YYYY-MM-DD ISO format.
        description (str, optional): Updated description text.

    Returns:
        bool: True if record was updated, False if not found or unauthorized.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        desc_val = description.strip() if (description and description.strip()) else None
        cursor.execute(
            """
            UPDATE expenses
            SET amount = ?, category = ?, date = ?, description = ?
            WHERE id = ? AND user_id = ?;
            """,
            (
                round(float(amount), 2),
                category.strip(),
                str(date).strip(),
                desc_val,
                expense_id,
                user_id
            )
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_expense(expense_id, user_id):
    """Delete an expense record belonging to a specific user.

    Parameters:
        expense_id (int): Primary key ID of the expense to delete.
        user_id (int): Foreign key ID of the authenticated user.

    Returns:
        bool: True if an expense was deleted, False if record not found or unauthorized.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            DELETE FROM expenses
            WHERE id = ? AND user_id = ?;
            """,
            (expense_id, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()




