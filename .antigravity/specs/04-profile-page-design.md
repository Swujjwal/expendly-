## 1. Overview

Implement the **User Profile Page Design & Account Management** feature for the Spendly personal finance application.

This step establishes the authenticated user profile hub. It transitions the `/profile` endpoint from a placeholder string into a rich, responsive account center that reflects Spendly's refined editorial aesthetic (warm paper surfaces, DM Serif typography, forest green accents). 

The profile page provides users with:
1. An **Identity Header** with a stylized avatar badge, member metadata, and account status.
2. An **Activity & Financial Summary Grid** displaying personal expense metrics (total logged transactions, lifetime spending sum, and average spend).
3. A **Personal Information Form** allowing users to edit and update their full name with real-time feedback, while keeping their registered email secure and read-only.
4. **Security & Session Controls** enabling clean account navigation and logout actions.

---

## 2. Depends on

- **Step 1: Database Setup** (`database/db.py`)
  - `users` table: `(id, name, email, password_hash, created_at)`
  - `expenses` table: `(id, user_id, amount, category, date, description, created_at)`
  - SQLite foreign key enforcement
- **Step 2: User Registration** (`users` records)
- **Step 3: User Authentication & Session** (`session["user_id"]`, login state)
- **Design Tokens**: `static/css/style.css` (CSS custom variables, typography, reset)
- **Master Layout**: `templates/base.html` (navbar with session-aware links)

---

## 3. Routes & Authorization

| Method | Endpoint | Handler | Access | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/profile` | `profile()` | Authenticated Only | Renders the profile page with user details and financial activity stats |
| `POST` | `/profile` | `profile()` | Authenticated Only | Validates and updates user profile information (e.g., full name) |

### Route Behavior & Access Control:
- **Authentication Guard:**
  - If `session.get("user_id")` is missing or invalid:
    - Immediately redirect to `/login` via `redirect(url_for('login'))` (HTTP 302).
- **`GET /profile`**:
  - Fetches the user record via `get_user_by_id(session["user_id"])`.
  - If user is not found in database (e.g. stale session): clear session and redirect to `/login`.
  - Fetches user expense statistics via `get_user_stats(session["user_id"])`.
  - Renders `templates/profile.html` (HTTP 200).
- **`POST /profile`**:
  - Extracts form field `name`.
  - Validates `name`: must be non-empty after `.strip()` and $\le 100$ characters.
  - If validation fails: re-renders `templates/profile.html` with an `error` message.
  - If validation succeeds:
    - Calls `update_user_name(session["user_id"], name)`.
    - Updates `session["user_name"] = name`.
    - Re-renders `templates/profile.html` with a `success="Profile updated successfully."` banner.

---

## 4. Visual Design System & Component Specifications

The profile interface follows Spendly's editorial design system defined in `style.css`:

### 4.1 Design Tokens Applied

| Token | CSS Variable | Value | Usage in Profile Page |
| :--- | :--- | :--- | :--- |
| **Canvas** | `--paper` | `#f7f6f3` | Page background |
| **Card Surface** | `--paper-card` | `#ffffff` | Profile cards and forms background |
| **Warm Accent** | `--paper-warm` | `#f0ede6` | Avatar background & stat card highlights |
| **Primary Accent** | `--accent` | `#1a472a` | Primary CTA buttons, avatar initials, borders |
| **Primary Soft** | `--accent-light` | `#e8f0eb` | Success badges and subtle pill borders |
| **Amber Accent** | `--accent-2` | `#c17f24` | Highlights, badges, secondary metrics |
| **Borders** | `--border` | `#e4e1da` | Card borders, dividers, input borders |
| **Typography Display** | `--font-display` | `'DM Serif Display', Georgia, serif` | Page title, user display name, stat numbers |
| **Typography Body** | `--font-body` | `'DM Sans', sans-serif` | Labels, inputs, helper copy, body text |
| **Border Radius** | `--radius-md` | `12px` | Card corners, modal boundaries |
| **Container Width** | `--profile-width` | `780px` | Centered profile container maximum width |

---

### 4.2 Page Layout & Structural Breakdown

```
+-----------------------------------------------------------------------+
|  Navbar (Spendly logo, [Profile], [Log out])                          |
+-----------------------------------------------------------------------+
|                                                                       |
|  [ .profile-container ] (max-width: 780px; centered)                  |
|                                                                       |
|  1. IDENTITY HEADER CARD (.profile-card .profile-header-card)         |
|     +---------------------------------------------------------------+ |
|     |  [ (U) Avatar ]   Ujjwal Sharma             [ Member Badge ]  | |
|     |                   ujjwal@example.com                          | |
|     |                   Member since March 2026                     | |
|     +---------------------------------------------------------------+ |
|                                                                       |
|  2. ACTIVITY METRICS GRID (.profile-stats-grid: 3 columns)            |
|     +------------------+  +------------------+  +------------------+  |
|     | Total Expenses   |  | Lifetime Spend   |  | Account Status   |  |
|     |       8          |  |    ₹6,170.00     |  |  Active · Free   |  |
|     | logged to date   |  | across all cats  |  | Standard Tier    |  |
|     +------------------+  +------------------+  +------------------+  |
|                                                                       |
|  3. ACCOUNT DETAILS FORM (.profile-card)                              |
|     +---------------------------------------------------------------+ |
|     |  <h3>Personal Information</h3>                                | |
|     |  <p>Update your display name and view account settings.</p>   | |
|     |                                                               | |
|     |  [ Alert: Success / Error block ]                             | |
|     |                                                               | |
|     |  Full name:      [ Ujjwal Sharma                         ]    | |
|     |  Email address:  [ ujjwal@example.com (locked/disabled)  ]    | |
|     |                  <small>Email cannot be changed.</small>      | |
|     |                                                               | |
|     |  [ Save Changes Button ]                                      | |
|     +---------------------------------------------------------------+ |
|                                                                       |
|  4. ACCOUNT ACTIONS FOOTER                                            |
|     +---------------------------------------------------------------+ |
|     |  <a href="/">← Back to Home</a>   |   <a href="/logout">Logout| |
|     +---------------------------------------------------------------+ |
+-----------------------------------------------------------------------+
```

---

## 5. Component Specifications

### A. Avatar Badge Component (`.profile-avatar`)
- **Dimensions:** 72px $\times$ 72px circle (`border-radius: 50%`).
- **Background:** `--accent` (#1a472a) or `--accent-light` (#e8f0eb).
- **Text:** First letter of user's name capitalized (`{{ user.name[0].upper() }}`).
- **Font:** `'DM Serif Display'`, font-size: `2rem`, color: `--paper` or `--accent`.
- **Border:** 2px solid `--border`.

### B. Stat Cards (`.profile-stat-card`)
- Three responsive columns on desktop (`grid-template-columns: repeat(3, 1fr)`), stacking to 1 column on mobile screens ($<640\text{px}$).
- **Content:**
  1. **Transactions:** `{{ stats.total_count }}` (`INTEGER`, e.g. "8").
  2. **Total Spending:** `₹{{ "%.2f"|format(stats.total_spent) }}` (`REAL`, e.g. "₹6,170.00").
  3. **Plan / Status:** "Active · Free Tier" with a green status indicator dot.
- **Card styling:** Background `--paper-card`, border `1px solid var(--border)`, border-radius `var(--radius-md)`, padding `1.25rem`.

### C. Personal Information Form
- **Full Name (`name`):**
  - Type: `text`, required, max length 100.
  - Class: `.form-input`
  - Current value: `value="{{ user.name }}"`.
- **Email (`email`):**
  - Type: `email`, `readonly` or `disabled`.
  - Class: `.form-input .form-input-readonly`
  - Background: `--paper-warm`, cursor: `not-allowed`, color: `--ink-muted`.
  - Helper note: `"Email address is permanently linked to your account."`
- **Submit Button:**
  - Class: `.btn-submit`
  - Label: `"Save Changes"`

### D. Flash / Feedback Alerts
- **Success Banner (`.auth-success` / `.profile-alert-success`):**
  - Background: `--accent-light` (#e8f0eb)
  - Color: `--accent` (#1a472a)
  - Border: `1px solid #c2dec9`
  - Displayed when `success` parameter is passed.
- **Error Banner (`.auth-error`):**
  - Background: `--danger-light` (#fdecea)
  - Color: `--danger` (#c0392b)
  - Border: `1px solid #f5c6cb`
  - Displayed when `error` parameter is passed.

---

## 6. Database Operations (`database/db.py`)

In strict compliance with the project rule (**"for database use only db.py"**):
No raw SQL queries or cursor logic in `app.py`. All database operations are encapsulated in `database/db.py`.

### Functions to Provide in `database/db.py`:

#### 1. `get_user_by_id(user_id)`
*(Already existing from Step 2)*
- Retrieves the user row by `id`.
- Returns `sqlite3.Row` containing `(id, name, email, created_at)` or `None`.

#### 2. `update_user_name(user_id, name)`
- Updates the `name` column in `users` table for the specified user ID:
  ```python
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
  ```

#### 3. `get_user_stats(user_id)`
- Aggregates expense metrics for the user:
  ```python
  def get_user_stats(user_id):
      """Calculate summary stats for a user's expenses.
      Returns dict with: total_count, total_spent, first_date.
      """
      conn = get_db()
      cursor = conn.cursor()
      try:
          row = cursor.execute("""
              SELECT 
                  COUNT(*) as total_count,
                  COALESCE(SUM(amount), 0.0) as total_spent
              FROM expenses
              WHERE user_id = ?;
          """, (user_id,)).fetchone()

          return {
              "total_count": row["total_count"] if row else 0,
              "total_spent": float(row["total_spent"]) if row else 0.0
          }
      finally:
          conn.close()
  ```

---

## 7. Changes to `app.py`

1. **Update Imports:**
   ```python
   from database.db import (
       init_db, seed_db, get_user_by_email, create_user,
       get_user_by_id, update_user_name, get_user_stats
   )
   ```

2. **Replace Placeholder `/profile` Route:**
   ```python
   @app.route("/profile", methods=["GET", "POST"])
   def profile():
       user_id = session.get("user_id")
       if not user_id:
           return redirect(url_for("login"))

       user = get_user_by_id(user_id)
       if not user:
           session.clear()
           return redirect(url_for("login"))

       stats = get_user_stats(user_id)
       error = None
       success = None

       if request.method == "POST":
           name = request.form.get("name", "").strip()
           if not name:
               error = "Name cannot be empty."
           elif len(name) > 100:
               error = "Name must not exceed 100 characters."
           else:
               update_user_name(user_id, name)
               session["user_name"] = name
               user = get_user_by_id(user_id)  # Refresh updated record
               success = "Profile updated successfully."

       return render_template(
           "profile.html",
           user=user,
           stats=stats,
           error=error,
           success=success
       )
   ```

---

## 8. Template & CSS Specifications

### 8.1 Template: `templates/profile.html`
- Extends `base.html`.
- Implements:
  - Header with avatar badge, member display name, email, member since date.
  - Stat cards grid (Total Expenses, Total Amount Spent, Plan Status).
  - Profile settings card with update form.
  - Links to return home or sign out.

### 8.2 CSS Classes to Add to `static/css/style.css`
- `.profile-section`: Outer wrapper with padding `3rem 1.5rem`.
- `.profile-container`: Main wrapper, `max-width: var(--max-width, 780px)`, `margin: 0 auto`.
- `.profile-header-card`: Flexbox container aligning avatar with user identity info.
- `.profile-avatar`: 72px circle with DM Serif Display initial.
- `.profile-badge`: Pill badge displaying "Member" or "Active".
- `.profile-stats-grid`: CSS Grid with `repeat(3, 1fr)`, gap `1rem`.
- `.profile-stat-card`: Surface card displaying label, formatted currency/count, and subtle subtitle.
- `.form-input-readonly`: Read-only input styling with `--paper-warm` background and muted text.
- `.alert-success`: Green success banner matching `--accent` and `--accent-light`.

---

## 9. Files to Change & Create

| Action | File Path | Scope |
| :--- | :--- | :--- |
| **Create** | `expense-tracker/templates/profile.html` | New Jinja2 template for user profile view |
| **Modify** | `expense-tracker/database/db.py` | Add `update_user_name()` and `get_user_stats()` helpers |
| **Modify** | `expense-tracker/app.py` | Implement `profile()` view function with GET/POST handling |
| **Modify** | `expense-tracker/static/css/style.css` | Add `.profile-*` styles aligned with design system |

---

## 10. Rules for Implementation

- **Strict Access Control:** Unauthenticated visitors must never see profile data; redirect to `/login`.
- **Database Encapsulation:** Zero raw SQL queries in `app.py`; all SQL operations live in `database/db.py`.
- **Defensive Error Handling:** Handle cases where a session has an invalid `user_id` by gracefully clearing the session.
- **Input Sanitization:** Always `.strip()` submitted names and reject whitespace-only strings.
- **Immutable Email:** Email address must be displayed as read-only/disabled; account emails remain unique and uneditable from this form.
- **Session Consistency:** Updating user's name must update both SQLite and the active `session["user_name"]`.

---

## 11. Expected Behavior

1. **Unauthenticated Visit to `/profile`**:
   - Responds with HTTP 302 redirecting to `/login`.
2. **Authenticated Visit to `/profile`**:
   - Responds with HTTP 200 rendering `profile.html`.
   - Displays user avatar with correct initial.
   - Displays accurate total expenses count and total spent formatted in rupees (₹).
   - Shows user's current name and email in form fields.
3. **Submit Valid Name Update**:
   - Updates `users` table in SQLite.
   - Updates `session["user_name"]`.
   - Re-renders page with `"Profile updated successfully."` banner.
   - Top navbar immediately shows the updated name.
4. **Submit Empty Name**:
   - Re-renders page with `"Name cannot be empty."` error banner.
   - Database record is unchanged.

---

## 12. Definition of Done

- [ ] `/profile` rejects unauthenticated users and redirects to `/login`
- [ ] Profile page displays stylized avatar badge with user's initial
- [ ] User name, email address, and member-since date are cleanly displayed
- [ ] Activity stats grid renders total expense count and total spending sum from database
- [ ] All database interactions use `database/db.py` exclusively (no SQL in `app.py`)
- [ ] Submitting a new valid name updates the database and the active session
- [ ] Submitting an invalid or empty name shows a clear validation error
- [ ] Email field is displayed as read-only
- [ ] Visual design strictly matches Spendly design system (DM Serif, warm paper, green accents)
- [ ] Responsive layout adapts cleanly to desktop, tablet, and mobile viewports
