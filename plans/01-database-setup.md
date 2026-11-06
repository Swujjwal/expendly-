# Plan: 01 — Database Setup

> **Spec Document:** `specs/01-database-setup.md`  
> **Target Status:** Ready for Implementation  
> **Estimated Changes:** 2 files to modify (`database/db.py`, `app.py`), 0 files to create, 0 new dependencies.

---

## 1. Executive Summary

This plan outlines the implementation of the foundational SQLite data access layer for the **Spendly** personal expense tracking application. It replaces the placeholder comment stub in `database/db.py` with three core functions (`get_db`, `init_db`, `seed_db`), ensures database table integrity with foreign keys and unique constraints, and wires startup initialization into `app.py`.

---

## 2. Architecture & Design Specification

### 2.1 Database File Location
The SQLite database file (`spendly.db` or `expense_tracker.db`) will be resolved relative to the project directory to ensure consistent discovery regardless of the current working directory:
```python
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "spendly.db"
)
```

### 2.2 Relational Schema Definition

#### `users` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Unique identifier for user |
| `name` | `TEXT` | `NOT NULL` | User full name |
| `email` | `TEXT` | `UNIQUE NOT NULL` | Unique account email address |
| `password_hash` | `TEXT` | `NOT NULL` | Cryptographic password hash (Werkzeug) |
| `created_at` | `TEXT` | `DEFAULT (datetime('now'))` | ISO timestamp of record creation |

```sql
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    DEFAULT (datetime('now'))
);
```

#### `expenses` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Unique expense transaction identifier |
| `user_id` | `INTEGER` | `NOT NULL, FOREIGN KEY → users(id)` | Associated user record |
| `amount` | `REAL` | `NOT NULL` | Floating point transaction amount |
| `category` | `TEXT` | `NOT NULL` | Expense category from the fixed domain |
| `date` | `TEXT` | `NOT NULL` | Transaction date in `YYYY-MM-DD` format |
| `description` | `TEXT` | `NULLABLE` | Optional descriptive note |
| `created_at` | `TEXT` | `DEFAULT (datetime('now'))` | ISO timestamp of record creation |

```sql
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
```

### 2.3 Category Domain (Strict 7-Value Enum)
All expense records will strictly adhere to the following category values:
- `Food`
- `Transport`
- `Bills`
- `Health`
- `Entertainment`
- `Shopping`
- `Other`

---

## 3. Implementation Steps

### Step 1: Implement `database/db.py`

#### A. Connection Factory: `get_db()`
- Connects to `DB_PATH`.
- Assigns `conn.row_factory = sqlite3.Row` to enable dict-like column access (`row['email']`).
- Executes `conn.execute("PRAGMA foreign_keys = ON;")` on every connection to enforce relational integrity (disabled by default in SQLite).
- Returns the active connection instance.

#### B. Schema Initialization: `init_db()`
- Opens a database connection via `get_db()`.
- Executes `CREATE TABLE IF NOT EXISTS` for `users` first, then `expenses`.
- Commits transactions and closes connection cleanly.
- Safe for repetitive executions without data corruption or errors.

#### C. Data Seeding: `seed_db()`
- **Idempotency Check:** Runs `SELECT COUNT(*) FROM users;`. If count > 0, returns immediately to avoid duplicate seed data.
- **Demo User:**
  - Name: `Demo User`
  - Email: `demo@spendly.com`
  - Password: `demo123` (hashed via `werkzeug.security.generate_password_hash`)
- **Sample Expenses (8 records):**
  - All assigned to the created demo `user_id`.
  - Amounts represented as `REAL` (float).
  - Dates distributed across current month in strict `YYYY-MM-DD` format.
  - Covers all 7 categories (`Food` [x2], `Transport`, `Bills`, `Health`, `Entertainment`, `Shopping`, `Other`).
  - Executed using parameterized query (`executemany` with `?` placeholders).

---

### Step 2: Wire Startup Lifecycle into `app.py`

#### A. Import DB Helpers
```python
from database.db import get_db, init_db, seed_db
```

#### B. Initialize Database in Application Context
Place immediately after `app = Flask(__name__)`, prior to route registrations:
```python
with app.app_context():
    init_db()
    seed_db()
```

#### C. Existing Routes Preserved
Leave all existing routes (`/`, `/register`, `/login`, `/terms`, `/privacy`, and placeholder routes) untouched.

---

## 4. Verification and Validation Checklist

| # | Check / Requirement | Verification Method | Expected Result |
| :--- | :--- | :--- | :--- |
| 1 | **Database File Creation** | Check `os.path.exists(DB_PATH)` | `spendly.db` created on app launch |
| 2 | **Table Creation** | Query `sqlite_master` for tables | Both `users` and `expenses` tables exist |
| 3 | **Row Factory Access** | Retrieve user row and inspect `row['email']` | Value accessible via key notation |
| 4 | **Foreign Key Enforcement** | Insert expense with non-existent `user_id = 9999` | Raises `sqlite3.IntegrityError` |
| 5 | **Unique Constraint** | Insert duplicate user with `demo@spendly.com` | Raises `sqlite3.IntegrityError` |
| 6 | **Demo User Exists** | Query `SELECT * FROM users WHERE email='demo@spendly.com'` | Returns 1 record with hashed password |
| 7 | **Sample Expenses (8 records)** | Query `SELECT COUNT(*) FROM expenses` | Exactly 8 records returned |
| 8 | **Category Coverage** | Query `SELECT DISTINCT category FROM expenses` | All 7 categories represented |
| 9 | **Date Formatting** | Regex check `^\d{4}-\d{2}-\d{2}$` on expense dates | 100% of dates conform to ISO format |
| 10 | **Idempotent Seeding** | Run `init_db()` and `seed_db()` twice consecutively | Counts remain 1 user and 8 expenses |
| 11 | **Parameterized Queries Only** | Code review of `database/db.py` | 0 instances of string formatting in SQL |
| 12 | **Flask App Health** | Send `GET /` and `GET /terms` to Flask test client | Both return HTTP 200 OK |

---

## 5. Potential Risks & Mitigations

- **Working Directory Drift:** If started from outside `expense-tracker/`, relative paths could create `.db` in unintended folders.  
  *Mitigation:* Use `os.path.abspath(__file__)` in `DB_PATH`.
- **Foreign Keys Disabled by Default:** In SQLite, foreign keys are connection-scoped and disabled by default.  
  *Mitigation:* Execute `PRAGMA foreign_keys = ON;` in `get_db()` on every single connection.
- **Duplicate Seeding on Hot Reload:** In Flask debug mode, the server reloads on code change.  
  *Mitigation:* Guard `seed_db()` with `SELECT COUNT(*) FROM users;` so multiple reloads never insert duplicate rows.
