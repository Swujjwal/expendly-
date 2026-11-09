## 1. Overview

Implement the **Backend Routes & Account Services for the User Profile** (Step 5) for the Spendly personal finance application.

While Step 4 established the profile interface layout and basic name editing, this specification establishes the complete, production-grade **backend endpoint architecture** powering profile management. It provides authenticated API and form-handling routes for:
1. **User Identity Updates (`POST /profile`):** Validating and persisting profile metadata changes with real-time session synchronization.
2. **Password & Credential Management (`POST /profile/password`):** Secure password rotation enforcing timing-safe re-authentication of the current password, length policies, confirmation matching, and cryptographic hashing via Werkzeug.
3. **Data Portability & Export (`GET /profile/export`):** Generating and streaming a comprehensive CSV export containing the user's profile and entire expense transaction history.
4. **Account Termination & Cascade Deletion (`POST /profile/delete`):** Secure account destruction requiring password verification, leveraging SQLite foreign key cascades (`ON DELETE CASCADE`) to purge all linked expenses, terminating the active session, and redirecting cleanly.

In strict compliance with project architecture rules (**"for database use only db.py"**), all database queries and transaction boundaries are encapsulated within `database/db.py`, with zero raw SQL in `app.py`.

---

## 2. Depends on

- **Step 1: Database Setup** (`database/db.py`)
  - `users` table: `(id, name, email, password_hash, created_at)`
  - `expenses` table with `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE`
  - `PRAGMA foreign_keys = ON;` in `get_db()`
- **Step 2: User Registration** (`users` table, Werkzeug password hashing)
- **Step 3: User Authentication** (`session["user_id"]`, login state)
- **Step 4: Profile Page Design** (`templates/profile.html`, `static/css/style.css`)

---

## 3. Routes & Endpoints

| Method | Endpoint | Handler | Access | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/profile` | `profile()` | Authenticated | Renders profile dashboard with user information and expense statistics |
| `POST` | `/profile` | `profile()` | Authenticated | Updates user's display name and synchronizes active session |
| `POST` | `/profile/password` | `change_password()` | Authenticated | Verifies current password and updates to new hashed password |
| `GET` | `/profile/export` | `export_data()` | Authenticated | Generates and streams downloadable CSV containing all user transactions |
| `POST` | `/profile/delete` | `delete_account()` | Authenticated | Re-authenticates password and permanently deletes account and expenses |

---

## 4. Route Behaviors & Business Logic

### A. `GET /profile`
- **Auth Guard:** If `not session.get("user_id")`, return `redirect(url_for('login'))` (HTTP 302).
- Queries user via `get_user_by_id(user_id)`.
  - If user not found (stale session): calls `session.clear()` and returns `redirect(url_for('login'))`.
- Queries summary metrics via `get_user_stats(user_id)`.
- Renders `templates/profile.html` with `user` and `stats` context.

### B. `POST /profile` (Profile Information Update)
- **Auth Guard:** If `not session.get("user_id")`, return `redirect(url_for('login'))`.
- Extracts `name = request.form.get("name", "").strip()`.
- **Validation:**
  - If empty: return `error="Name cannot be empty."`
  - If length $> 100$: return `error="Name must not exceed 100 characters."`
- **Persistence:** Calls `update_user_name(user_id, name)` in `db.py`.
- **Session Sync:** Updates `session["user_name"] = name`.
- Re-renders `profile.html` with `success="Profile updated successfully."` and refreshed `user` model.

### C. `POST /profile/password` (Password Change)
- **Auth Guard:** If `not session.get("user_id")`, return `redirect(url_for('login'))`.
- Extracts form values:
  - `current_password = request.form.get("current_password", "")`
  - `new_password = request.form.get("new_password", "")`
  - `confirm_password = request.form.get("confirm_password", "")`
- **Sequential Validation:**
  1. *Presence Check:* If not `current_password` or not `new_password` or not `confirm_password`:
     - Return `error="All password fields are required."`
  2. *Current Password Verification:* Fetch user via `get_user_by_id(user_id)`:
     - If not `check_password_hash(user["password_hash"], current_password)`:
       - Return `error="Incorrect current password."`
  3. *New Password Length:* If `len(new_password) < 8`:
     - Return `error="New password must be at least 8 characters long."`
  4. *Confirmation Parity:* If `new_password != confirm_password`:
     - Return `error="New passwords do not match."`
  5. *Password Reuse Prevention:* If `current_password == new_password`:
     - Return `error="New password must be different from current password."`
- **Persistence:**
  - Hashes new credential: `new_hash = generate_password_hash(new_password)`.
  - Calls `update_user_password(user_id, new_hash)` in `db.py`.
- Re-renders `profile.html` with `success="Password changed successfully."`.

### D. `GET /profile/export` (Financial Data Portability)
- **Auth Guard:** If `not session.get("user_id")`, return `redirect(url_for('login'))`.
- Calls `get_user_expenses_for_export(user_id)` from `database/db.py`.
- Formats rows into RFC 4180 standard CSV string buffer (`io.StringIO`):
  - **CSV Headers:** `Date,Category,Amount (INR),Description,Created At`
  - Formats floats as standard decimals (`%.2f`).
- Sets HTTP response headers:
  - `Content-Type: text/csv; charset=utf-8`
  - `Content-Disposition: attachment; filename="spendly_expenses_<date>.csv"`
- Streams or returns raw CSV text directly.

### E. `POST /profile/delete` (Account Destruction)
- **Auth Guard:** If `not session.get("user_id")`, return `redirect(url_for('login'))`.
- Extracts `password = request.form.get("password", "")`.
- **Validation:**
  - If not `password`: return `error="Password is required to delete your account."`
  - Fetch user: `user = get_user_by_id(user_id)`.
  - Verify password: if not `check_password_hash(user["password_hash"], password)`:
    - Return `error="Incorrect password. Account was not deleted."`
- **Deletion:**
  - Calls `delete_user_account(user_id)` in `db.py`.
  - SQLite foreign key cascade purges all expenses associated with `user_id`.
- **Teardown:**
  - Calls `session.clear()`.
  - Redirects to `/` (`url_for('landing')`) with HTTP 302.

---

## 5. Form Fields & Validation Rules

| Form / Action | Field | Type | Required | Constraints | Error Message |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Profile Info** | `name` | `text` | Yes | Non-empty after strip, $\le 100$ chars | `"Name cannot be empty."` / `"Name must not exceed 100 characters."` |
| **Password Change** | `current_password` | `password` | Yes | Non-empty, matches DB hash | `"All password fields are required."` / `"Incorrect current password."` |
| **Password Change** | `new_password` | `password` | Yes | $\ge 8$ chars, different from current | `"New password must be at least 8 characters long."` / `"New password must be different from current password."` |
| **Password Change** | `confirm_password` | `password` | Yes | Matches `new_password` | `"New passwords do not match."` |
| **Account Deletion** | `password` | `password` | Yes | Non-empty, matches DB hash | `"Password is required to delete your account."` / `"Incorrect password. Account was not deleted."` |

---

## 6. Password Security & Re-Authentication Rules

- **Zero Plaintext Storage:** Plaintext passwords are never logged, stored, or passed into templates.
- **Timing-Safe Verification:** All password checks delegate to `werkzeug.security.check_password_hash`.
- **Re-Authentication Gate:** Destructive operations (changing password and account termination) require explicit password re-verification.
- **Cryptographic Hashing:** Password updates use `werkzeug.security.generate_password_hash`.

---

## 7. Database Operations (`database/db.py`)

All queries must be encapsulated inside `database/db.py` to preserve the architectural boundary (**"for database use only db.py"**).

### New & Updated Functions in `database/db.py`:

#### 1. `update_user_password(user_id, password_hash)`
```python
def update_user_password(user_id, password_hash):
    """Update a user's password hash in the database. Returns True on success."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?;",
            (password_hash, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
```

#### 2. `get_user_expenses_for_export(user_id)`
```python
def get_user_expenses_for_export(user_id):
    """Retrieve all expense transactions for a user ordered by date descending."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        rows = cursor.execute("""
            SELECT date, category, amount, description, created_at
            FROM expenses
            WHERE user_id = ?
            ORDER BY date DESC, id DESC;
        """, (user_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
```

#### 3. `delete_user_account(user_id)`
```python
def delete_user_account(user_id):
    """Permanently delete a user account.
    Foreign key ON DELETE CASCADE will automatically remove associated expenses.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE id = ?;", (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
```

---

## 8. Changes to `app.py`

1. **Update Imports:**
   ```python
   import csv
   import io
   from datetime import datetime
   from flask import Flask, render_template, request, redirect, url_for, session, Response
   from werkzeug.security import generate_password_hash, check_password_hash
   from database.db import (
       init_db, seed_db, get_user_by_email, create_user,
       get_user_by_id, update_user_name, get_user_stats,
       update_user_password, get_user_expenses_for_export, delete_user_account
   )
   ```

2. **Refactor `/profile` Handler:**
   - Handle `GET` and `POST` for general profile updates.

3. **Add `/profile/password` Handler:**
   - Accepts `POST`.
   - Validates current password, length, and confirmation matching.
   - Updates password hash via `update_user_password`.

4. **Add `/profile/export` Handler:**
   - Accepts `GET`.
   - Retrieves expense records with `get_user_expenses_for_export(user_id)`.
   - Writes CSV to memory buffer using Python `csv.writer`.
   - Returns Flask `Response` with CSV MIME type and attachment header.

5. **Add `/profile/delete` Handler:**
   - Accepts `POST`.
   - Verifies confirmation password.
   - Executes `delete_user_account(user_id)`.
   - Clears `session` and redirects to `url_for('landing')`.

---

## 9. Template Integration (`templates/profile.html`)

Expand `templates/profile.html` with:

1. **Security & Password Card:**
   - Heading: "Security & Credentials"
   - Password update form pointing to `action="{{ url_for('change_password') }}"`:
     - Current Password (`current_password`)
     - New Password (`new_password`)
     - Confirm Password (`confirm_password`)
     - Submit: "Update Password"

2. **Data Export Action:**
   - Inside an "Account Data" or "Export" card:
     - Text description: "Download a full record of your logged expenses in CSV format."
     - Link button: `<a href="{{ url_for('export_data') }}" class="btn-secondary">Export Data (CSV)</a>`

3. **Danger Zone Card:**
   - Heading: "Danger Zone"
   - Warning text: "Permanently delete your account and all associated expense history. This action cannot be undone."
   - Delete form pointing to `action="{{ url_for('delete_account') }}"`:
     - Confirm Password input (`password`, placeholder="Enter password to confirm")
     - Submit button: "Delete Account" (`.btn-danger`)

---

## 10. Files to Change & Create

| File | Action | Scope |
| :--- | :--- | :--- |
| `expense-tracker/database/db.py` | **Modify** | Add `update_user_password`, `get_user_expenses_for_export`, `delete_user_account` |
| `expense-tracker/app.py` | **Modify** | Add route handlers: `change_password`, `export_data`, `delete_account` |
| `expense-tracker/templates/profile.html` | **Modify** | Add password change form, export button, and delete account danger zone |
| `expense-tracker/static/css/style.css` | **Modify** | Add `.btn-secondary`, `.btn-danger`, `.danger-card`, and form section dividers |

---

## 11. Rules for Implementation

- **Strict Database Decoupling:** Every SQL operation is executed in `database/db.py`; zero raw queries in `app.py`.
- **Timing-Safe Checks:** Always use `check_password_hash` to compare passwords.
- **Foreign Key Integrity:** SQLite `PRAGMA foreign_keys = ON;` must be active to ensure `ON DELETE CASCADE` removes expenses when a user is deleted.
- **Session Cleanup:** On account deletion, `session.clear()` is mandatory to prevent dangling authentication states.
- **Defensive Error Handling:** Return actionable feedback to the user on validation errors without exposing internal exceptions.

---

## 12. Expected Behavior & Status Codes

- **Unauthenticated access to any profile endpoint (`/profile`, `/profile/password`, `/profile/export`, `/profile/delete`):**
  - Responds with HTTP 302 redirecting to `/login`.
- **Valid password change (`POST /profile/password`):**
  - Responds with HTTP 200 re-rendering `profile.html` with `"Password changed successfully."`.
  - Subsequent login requires the new password; old password fails.
- **Invalid password change (wrong current password, short, mismatched):**
  - Responds with HTTP 200 with clear error message; DB remains untouched.
- **Data Export (`GET /profile/export`):**
  - Responds with HTTP 200, headers `Content-Disposition: attachment; filename="spendly_expenses_<date>.csv"`, and valid CSV stream.
- **Account Deletion (`POST /profile/delete`) with correct password:**
  - Purges user and linked expenses from SQLite.
  - Clears session.
  - Responds with HTTP 302 redirecting to `/`.
  - Attempting to log in with deleted account fails (`"Invalid email or password."`).

---

## 13. Definition of Done

- [ ] All 4 profile backend routes (`/profile`, `/profile/password`, `/profile/export`, `/profile/delete`) enforce authentication checks
- [ ] Changing name updates SQLite `users` table and syncs `session["user_name"]`
- [ ] Password change requires verification of current password
- [ ] Password change enforces $\ge 8$ character limit and confirmation parity
- [ ] Password updates are hashed via Werkzeug
- [ ] Data export streams a valid RFC 4180 CSV containing all user transactions
- [ ] Account deletion requires password confirmation
- [ ] Account deletion cascades and removes all linked user expenses from SQLite
- [ ] Account deletion clears the Flask session and redirects to `/`
- [ ] All database queries are isolated inside `database/db.py` (zero SQL in `app.py`)
