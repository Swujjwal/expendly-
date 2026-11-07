## 1. Overview

Implement the **User Login & Session Authentication** and **Logout** features for the Spendly personal finance application.

This step establishes the credential verification and session management lifecycle. It allows registered users to securely authenticate with their email and password, creates an encrypted, cookie-based Flask session, dynamically adapts navigation links across the application based on authentication state, and provides a clean sign-out workflow that terminates active user sessions.

---

## 2. Depends on

- **Step 1: Database Setup** (`database/db.py`)
  - `users` table schema: `(id, name, email, password_hash, created_at)`
- **Step 2: User Registration** (`app.py`, `database/db.py`)
  - `get_user_by_email(email)` in `database/db.py`
  - Passwords hashed using `werkzeug.security.generate_password_hash`
- **Existing Templates**:
  - `templates/login.html` (sign-in form)
  - `templates/base.html` (navbar with auth actions)

---

## 3. Routes & Endpoints

| Method | Endpoint | Handler | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/login` | `login()` | Renders the login form (`templates/login.html`), or redirects authenticated users to `/profile` |
| `POST` | `/login` | `login()` | Validates credentials, verifies password hash, initiates session, and redirects to `/profile` |
| `GET` | `/logout` | `logout()` | Clears active session data and redirects to `/login` |

### Route Behaviors:

#### A. `GET /login`
- **If already logged in (`session.get("user_id")` exists):**
  - Redirects immediately to `/profile` (HTTP 302).
- **If unauthenticated:**
  - Renders `templates/login.html` with an empty form.
  - Returns HTTP 200.

#### B. `POST /login`
- Extracts form values: `email` and `password`.
- Normalizes email via `.strip().lower()`.
- Validates field presence (both `email` and `password` are required).
- Fetches user record via `get_user_by_email(email)` from `database/db.py`.
- **Credential Verification:**
  - If user is not found **OR** `check_password_hash(user["password_hash"], password)` returns `False`:
    - Re-renders `templates/login.html` with generic error message: `"Invalid email or password."`
    - Preserves entered `email` in the form (`value="{{ email or '' }}"`).
    - Does not retain or return `password`.
    - Returns HTTP 400 or 200 with error banner.
- **Successful Authentication:**
  - Clears existing session data (`session.clear()`) to prevent session fixation.
  - Populates session keys:
    - `session["user_id"] = user["id"]`
    - `session["user_name"] = user["name"]`
    - `session["user_email"] = user["email"]`
  - Redirects to `/profile` via `redirect(url_for('profile'))` (HTTP 302).

#### C. `GET /logout`
- Calls `session.clear()` to remove all stored authentication keys.
- Redirects user to `/login` via `redirect(url_for('login'))` (HTTP 302).

---

## 4. Form Fields & Input Specifications

Matches inputs defined in `templates/login.html`:

| Field Name | HTML Input Type | Required | Constraints & Sanitization | Validation Failure Message |
| :--- | :--- | :--- | :--- | :--- |
| `email` | `email` | Yes | Non-empty string, normalized via `.strip().lower()` | `"All fields are required."` / `"Invalid email or password."` |
| `password` | `password` | Yes | Non-empty string | `"All fields are required."` / `"Invalid email or password."` |

---

## 5. Input Validation & Authentication Rules

1. **Required Fields Check:**
   - Both `email` and `password` must be present and non-empty.
   - If either field is empty or missing: return `"All fields are required."`

2. **Case-Insensitive Email Lookup:**
   - Always lowercase and trim email before querying: `email = request.form.get("email", "").strip().lower()`.

3. **Generic Error Message (Security Standard):**
   - Whether the email does not exist in the database OR the password does not match the hash, the error message **must always be identical**:
     ```
     "Invalid email or password."
     ```
   - **Rationale:** Prevents username/email enumeration attacks.

4. **Timing-Safe Password Verification:**
   - Use `werkzeug.security.check_password_hash`:
     ```python
     from werkzeug.security import check_password_hash

     if not user or not check_password_hash(user["password_hash"], password):
         return render_template("login.html", error="Invalid email or password.", email=email)
     ```

---

## 6. Session Management & Configuration

### A. Secret Key Configuration (`app.py`)
Flask requires a secret key to cryptographically sign session cookies:
```python
import os

app.secret_key = os.environ.get("SECRET_KEY", "spendly-dev-secret-key-change-in-production")
```

### B. Session Lifecycle
- **On Login Success:**
  ```python
  session.clear()
  session["user_id"] = user["id"]
  session["user_name"] = user["name"]
  session["user_email"] = user["email"]
  ```
- **On Logout:**
  ```python
  session.clear()
  ```

### C. Cookie Security Best Practices
- `SESSION_COOKIE_HTTPONLY = True`: Prevents client-side scripts from reading session cookies.
- `SESSION_COOKIE_SAMESITE = 'Lax'`: Mitigates Cross-Site Request Forgery (CSRF) on cross-origin requests.

---

## 7. Database Operations Policy (`database/db.py`)

In strict accordance with the project architecture rule (**"for database use only db.py"**):
- **No SQL queries or connection handlers in `app.py`.**
- `app.py` must only call the existing helper function:
  ```python
  from database.db import get_user_by_email
  ```
- All connection opening (`get_db()`), cursor execution, row mapping, and connection closing (`conn.close()`) remain fully encapsulated in `database/db.py`.

---

## 8. Changes to `app.py`

1. **Update Imports:**
   ```python
   import os
   from flask import Flask, render_template, request, redirect, url_for, session
   from werkzeug.security import generate_password_hash, check_password_hash
   from database.db import init_db, seed_db, get_user_by_email, create_user
   ```

2. **Set Secret Key:**
   ```python
   app.secret_key = os.environ.get("SECRET_KEY", "spendly-dev-secret-key-change-in-production")
   ```

3. **Update `/login` Route:**
   - Support `GET` and `POST`.
   - Redirect logged-in users to `/profile` on `GET`.
   - Validate input presence on `POST`.
   - Authenticate with `get_user_by_email` and `check_password_hash`.
   - Establish `session` and redirect to `/profile`.

4. **Update `/logout` Route:**
   - Clear session: `session.clear()`.
   - Redirect to `url_for('login')`.

---

## 9. Template Integration

### A. `templates/login.html`
- Form already includes `<div class="auth-error">{{ error }}</div>`.
- Ensure email input retains value on failed attempt:
  ```html
  <input type="email" id="email" name="email" class="form-input"
         placeholder="Ujjwal@example.com" value="{{ email or '' }}" required autofocus>
  ```
- Password input must remain empty (`value` attribute omitted).

### B. `templates/base.html` (Dynamic Navigation Bar)
Update navbar links to reflect authentication status dynamically:
```html
<div class="nav-links">
    {% if session.get('user_id') %}
        <a href="{{ url_for('profile') }}">Profile</a>
        <a href="{{ url_for('logout') }}" class="nav-cta">Log out</a>
    {% else %}
        <a href="{{ url_for('login') }}">Sign in</a>
        <a href="{{ url_for('register') }}" class="nav-cta">Get started</a>
    {% endif %}
</div>
```

---

## 10. Files to Change

- `expense-tracker/app.py`:
  - Add `session` and `check_password_hash` imports.
  - Configure `app.secret_key`.
  - Implement `/login` (`GET` and `POST`) and `/logout` (`GET`).
- `expense-tracker/templates/login.html`:
  - Add `value="{{ email or '' }}"` to email input.
- `expense-tracker/templates/base.html`:
  - Add conditional navbar rendering based on `session.get('user_id')`.

---

## 11. Files to Create

- None required for core feature (optional test file `tests/test_auth.py`).

---

## 12. Dependencies

- No new pip packages required.
- Standard libraries:
  - `os`
- Existing dependencies:
  - `Flask`
  - `Werkzeug`

---

## 13. Rules for Implementation

- **Database Isolation:** All database reads go through `database/db.py`; zero SQL in `app.py`.
- **Timing-Safe Password Checks:** Always use `check_password_hash`; never compare passwords directly.
- **Account Enumeration Prevention:** Return identical error message `"Invalid email or password."` for non-existent users and invalid passwords.
- **Session Hygiene:** Call `session.clear()` before setting new session values on login, and on logout.
- **Credential Privacy:** Never store passwords in session, logs, or template context.
- **Preserve Non-Sensitive Input:** Retain `email` in form on error so user does not re-type; never retain `password`.

---

## 14. Expected Behavior

- **`GET /login` (Unauthenticated)**:
  - Returns HTTP 200 with sign-in form.
- **`GET /login` (Already Authenticated)**:
  - Returns HTTP 302 redirecting to `/profile`.
- **`POST /login` with Valid Credentials**:
  - `session["user_id"]` is set to user's integer ID.
  - Returns HTTP 302 redirecting to `/profile`.
- **`POST /login` with Unregistered Email**:
  - Returns HTTP 200/400 re-rendering `login.html` with `"Invalid email or password."`.
  - `session` remains empty.
- **`POST /login` with Wrong Password**:
  - Returns HTTP 200/400 re-rendering `login.html` with `"Invalid email or password."`.
  - `session` remains empty.
- **`POST /login` with Empty Fields**:
  - Returns HTTP 200/400 re-rendering `login.html` with `"All fields are required."`.
- **`GET /logout`**:
  - Clears `session`.
  - Returns HTTP 302 redirecting to `/login`.
- **Navigation Bar**:
  - Displays "Profile" and "Log out" when logged in.
  - Displays "Sign in" and "Get started" when logged out.

---

## 15. Error Handling Expectations

- **Missing Secret Key:** Ensure fallback secret key is configured so Flask does not crash when writing to session.
- **Malformed Form Data:** Safely `.strip()` strings using `request.form.get("email", "")` defaults to prevent `AttributeError`.
- **Database Exceptions:** Handled internally by `database/db.py`; connection guaranteed to close.

---

## 16. Definition of Done

- [ ] `app.secret_key` is configured in `app.py`
- [ ] `GET /login` renders `templates/login.html` with HTTP 200 for visitors
- [ ] `GET /login` redirects active session users to `/profile`
- [ ] `POST /login` extracts and trims email and password
- [ ] Missing form fields return `"All fields are required."`
- [ ] Non-existent email returns `"Invalid email or password."`
- [ ] Incorrect password returns `"Invalid email or password."`
- [ ] Valid credentials verify with `check_password_hash`
- [ ] Valid login sets `session["user_id"]`, `session["user_name"]`, `session["user_email"]`
- [ ] Valid login redirects to `/profile` (`302 Found`)
- [ ] `GET /logout` clears session and redirects to `/login` (`302 Found`)
- [ ] Navbar conditionally displays "Sign in" vs "Log out" based on session state
- [ ] All database interactions use `database/db.py` only (no SQL in `app.py`)
