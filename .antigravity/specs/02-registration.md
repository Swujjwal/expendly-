## 1. Overview

Implement the **User Registration** feature for the Spendly personal finance application.

This step establishes the onboarding workflow that allows new users to create an account by providing their full name, email address, and a secure password.

It transitions the `/register` endpoint from a placeholder template into a fully functional authentication entry point that validates inputs, prevents duplicate accounts, securely hashes credentials using Werkzeug, persists user records into the SQLite database via `get_db()`, and seamlessly redirects users to the login screen.

---

## 2. Depends on

- **Step 1: Database Setup** (`database/db.py`)
  - `get_db()`: SQLite connection provider configured with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON;`
  - `init_db()`: Initializes the `users` and `expenses` tables
  - `users` table schema: `(id, name, email, password_hash, created_at)`
- Existing template: `templates/register.html`

---

## 3. Routes

| Method | Endpoint | Handler | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/register` | `register()` | Renders the registration form (`templates/register.html`) |
| `POST` | `/register` | `register()` | Validates form data, hashes password, inserts user into database, and redirects to `/login` |

### Route Behavior:
- **`GET /register`**:
  - Renders `templates/register.html` with an empty form.
  - Returns HTTP 200.

- **`POST /register`**:
  - Extracts form values: `name`, `email`, `password`.
  - Performs validation checks sequentially.
  - If validation fails: re-renders `templates/register.html` with an `error` message and pre-populates existing inputs (`name`, `email`). Returns HTTP 400 or 200 with error banner.
  - If validation succeeds:
    - Normalizes email to lowercase and strips whitespace.
    - Hashes password using `werkzeug.security.generate_password_hash`.
    - Inserts new user record into the `users` table.
    - Redirects to `/login` via `redirect(url_for('login'))` (HTTP 302).

---

## 4. Form Fields & Input Specifications

Matches inputs defined in `templates/register.html`:

| Field Name | HTML Input Type | Required | Constraints & Sanitization | Error Message |
| :--- | :--- | :--- | :--- | :--- |
| `name` | `text` | Yes | Non-empty string after `.strip()`, max 100 characters | `"All fields are required."` / `"Full name is required."` |
| `email` | `email` | Yes | Valid email format, normalized via `.strip().lower()`, unique in database | `"Please enter a valid email address."` / `"An account with this email already exists."` |
| `password` | `password` | Yes | Minimum 8 characters, non-empty | `"Password must be at least 8 characters long."` |

---

## 5. Input Validation Rules

The application must validate incoming POST request data before interacting with the database:

1. **Required Fields Check:**
   - Verify `name`, `email`, and `password` are present in `request.form`.
   - Strip leading and trailing whitespace from `name` and `email`.
   - If any field is empty: return `"All fields are required."`

2. **Full Name Validation:**
   - Must contain at least 1 non-whitespace character.
   - Length must not exceed 100 characters.

3. **Email Validation:**
   - Must match standard email formatting (e.g. contains `@` and domain with `.`, or regex check `^[\w\.-]+@[\w\.-]+\.\w+$`).
   - Must be converted to lowercase before database query and insertion to guarantee case-insensitive uniqueness (e.g., `User@Example.COM` -> `user@example.com`).

4. **Password Length Validation:**
   - Length check: `len(password) >= 8`.
   - If fewer than 8 characters: return `"Password must be at least 8 characters long."`

5. **Email Uniqueness Check:**
   - Query the `users` table to verify if the normalized email is already registered:
     ```sql
     SELECT id FROM users WHERE email = ?;
     ```
   - If a matching record is found: return `"An account with this email already exists."`

---

## 6. Password Hashing & Security

- **Hashing Algorithm:** Use `werkzeug.security.generate_password_hash`.
  ```python
  from werkzeug.security import generate_password_hash

  password_hash = generate_password_hash(password)
  ```
- **Security Guarantees:**
  - Never store plaintext passwords in SQLite or session.
  - Never log raw passwords or hashed values.
  - Never pass raw passwords back to the template during error re-renders.
  - Rely on Werkzeug's secure defaults (`scrypt` or `pbkdf2:sha256` with cryptographic salt).

---

## 7. Database Operations

All database interactions must use `get_db()` from `database.db`.

### A. Check Existing User by Email
```python
conn = get_db()
cursor = conn.cursor()
existing_user = cursor.execute(
    "SELECT id FROM users WHERE email = ?;",
    (email,)
).fetchone()
```

### B. Insert New User
```python
cursor.execute(
    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?);",
    (name, email, password_hash)
)
conn.commit()
conn.close()
```

### C. Integrity & Transaction Management
- Always wrap database execution to ensure `conn.close()` is executed.
- Defensive handling for `sqlite3.IntegrityError` in case of race conditions during concurrent registration with identical emails.

---

## 8. Changes to `app.py`

1. **Update Imports:**
   ```python
   from flask import Flask, render_template, request, redirect, url_for
   from werkzeug.security import generate_password_hash
   from database.db import get_db, init_db, seed_db
   ```

2. **Update `/register` Route:**
   - Change decorator to accept both `GET` and `POST` methods:
     ```python
     @app.route("/register", methods=["GET", "POST"])
     def register():
         if request.method == "POST":
             name = request.form.get("name", "").strip()
             email = request.form.get("email", "").strip().lower()
             password = request.form.get("password", "")

             # 1. Validate required fields
             if not name or not email or not password:
                 return render_template("register.html", error="All fields are required.", name=name, email=email)

             # 2. Validate email format
             if "@" not in email or "." not in email:
                 return render_template("register.html", error="Please enter a valid email address.", name=name, email=email)

             # 3. Validate password length
             if len(password) < 8:
                 return render_template("register.html", error="Password must be at least 8 characters long.", name=name, email=email)

             # 4. Check for existing user
             conn = get_db()
             cursor = conn.cursor()
             existing_user = cursor.execute("SELECT id FROM users WHERE email = ?;", (email,)).fetchone()
             if existing_user:
                 conn.close()
                 return render_template("register.html", error="An account with this email already exists.", name=name, email=email)

             # 5. Hash password and insert user
             password_hash = generate_password_hash(password)
             cursor.execute(
                 "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?);",
                 (name, email, password_hash)
             )
             conn.commit()
             conn.close()

             # 6. Redirect to login
             return redirect(url_for("login"))

         return render_template("register.html")
     ```

---

## 9. Template Integration (`templates/register.html`)

`templates/register.html` is already set up to display error notifications:
```html
{% if error %}
<div class="auth-error">{{ error }}</div>
{% endif %}
```

- When validation fails, pass `error` string to template context: `render_template("register.html", error=error)`.
- Pre-fill `name` and `email` input values if preserved during re-render:
  ```html
  value="{{ name or '' }}"
  value="{{ email or '' }}"
  ```

---

## 10. Files to Change

- `expense-tracker/app.py` → Update `/register` route to support `POST` and implement validation/registration logic.

---

## 11. Files to Create

- None required for core functionality.

---

## 12. Dependencies

- No new pip packages.
- Standard libraries:
  - `sqlite3`
  - `re` (optional for advanced regex email validation)
- Existing installed dependencies:
  - `Flask`
  - `Werkzeug`

---

## 13. Rules for Implementation

- **No ORMs:** No SQLAlchemy; standard SQLite queries only.
- **Parameterized Queries Only:** Never use string concatenation or f-strings in SQL statements.
- **Normalized Email:** Always `.strip().lower()` email addresses before checking or storing.
- **Sanitized Inputs:** Always `.strip()` strings to prevent whitespace pollution.
- **Secure Password Storage:** Always store hashed passwords using `werkzeug.security.generate_password_hash`.
- **Resource Cleanup:** Always commit changes and close SQLite connections.
- **Redirection:** On success, redirect to `/login` using `redirect(url_for('login'))`.
- **Error Feedback:** Render descriptive, user-friendly error messages into `{{ error }}` block.

---

## 14. Expected Behavior

- **`GET /register`**:
  - Responds with HTTP 200.
  - Displays empty registration form with Name, Email, and Password fields.
- **`POST /register` with Valid Data**:
  - Creates a new record in `users` table with hashed password.
  - Responds with HTTP 302 redirecting to `/login`.
  - Plaintext password is never saved in the database.
- **`POST /register` with Empty / Missing Fields**:
  - Re-renders `register.html` with error: `"All fields are required."`
  - No record created in database.
- **`POST /register` with Password < 8 Characters**:
  - Re-renders `register.html` with error: `"Password must be at least 8 characters long."`
  - No record created in database.
- **`POST /register` with Existing Email**:
  - Re-renders `register.html` with error: `"An account with this email already exists."`
  - No duplicate record created.
- **`POST /register` with Invalid Email Syntax**:
  - Re-renders `register.html` with error: `"Please enter a valid email address."`

---

## 15. Error Handling Expectations

- **Duplicate Email:**
  - Check before insert: `SELECT id FROM users WHERE email = ?`
  - Defensive `try...except sqlite3.IntegrityError` in case of concurrent submissions.
  - Never allow an unhandled database exception (500 Internal Server Error) to crash the application.
- **Database Operational Errors:**
  - Gracefully log errors and present a user-friendly error banner if database access fails.

---

## 16. Definition of Done

- [ ] `GET /register` loads the registration page with HTTP 200
- [ ] `POST /register` accepts `name`, `email`, and `password`
- [ ] Inputs are sanitized (trimmed, email converted to lowercase)
- [ ] Missing or empty fields show `"All fields are required."`
- [ ] Password shorter than 8 characters shows `"Password must be at least 8 characters long."`
- [ ] Invalid email syntax displays `"Please enter a valid email address."`
- [ ] Duplicate email submission is blocked and displays `"An account with this email already exists."`
- [ ] Passwords are cryptographically hashed before database storage
- [ ] Successful registration inserts user into SQLite `users` table
- [ ] Successful registration redirects user to `/login` (`302 Found`)
- [ ] All database queries use parameterized SQL (`?` placeholders)
- [ ] Database connection is committed and closed cleanly
