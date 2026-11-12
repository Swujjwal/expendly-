# Spec 08 — Edit Expense (Update Transaction)

## 1. Overview

Implement the **Edit Expense (Update Transaction)** feature (Step 8) in the Spendly personal finance application.

Currently, Spendly allows authenticated users to log new expenses (Step 7) and view their aggregate metrics, dynamic category breakdown, recent transaction history, and temporal filters on the profile dashboard (Steps 4–6). However, users cannot modify existing expenses to correct mistakes in amounts, reclassify categories, update dates, or edit descriptions.

This specification defines the complete Update (U in CRUD) transaction management flow, enabling authenticated users to safely edit their previously recorded transactions.

In accordance with core project architectural constraints (**"for database use only db.py"**):
- All database mutation and retrieval operations are encapsulated strictly within `database/db.py`.
- No raw SQL queries or cursor executions exist in `app.py`.
- Strict user ownership and IDOR (Insecure Direct Object Reference) guards ensure users can only view and edit their own expenses.
- All database queries enforce parameterized SQL bindings.

---

## 2. Depends on

- **Step 1: Database Setup** (`database/db.py`)
  - `expenses` table schema: `(id, user_id, amount, category, date, description, created_at)`
  - Parameterized SQLite queries with `PRAGMA foreign_keys = ON;`
- **Step 2: User Registration** (`users` table)
- **Step 3: User Authentication** (`session["user_id"]`, login guards, `/logout`)
- **Step 4: Profile Page Design** (`templates/profile.html`, `static/css/style.css`)
- **Step 5: Profile Backend Routes** (`/api/expenses`, `/api/stats/summary`, `/api/stats/categories`)
- **Step 6: Date Range Filter** (`resolve_date_range`, temporal presets, dynamic category distribution)
- **Step 7: Add Expense** (`create_expense()`, `get_standard_categories()`, `templates/add_expense.html`)

---

## 3. Routes & Endpoints

| Method | Endpoint | Query / Body Parameters | Access | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/expenses/<int:id>/edit` | None | Authenticated (Owner) | Renders the edit expense form pre-populated with the existing transaction data |
| `POST` | `/expenses/<int:id>/edit` | `amount`, `category`, `date`, `description` (Form Data) | Authenticated (Owner) | Validates input, updates the expense in SQLite via `db.py`, and redirects to `/profile` |
| `GET` | `/api/expenses/<int:id>` | None | Authenticated (Owner) | Returns JSON representation of a single expense record |
| `PUT` | `/api/expenses/<int:id>` | `{ "amount", "category", "date", "description" }` (JSON) | Authenticated (Owner) | Programmatically updates an expense record; returns updated JSON |

---

## 4. Business Logic & Validation Rules

### A. Authorization & Security (IDOR Prevention)

1. **Authentication Guard:**
   - If `not session.get("user_id")`: redirect to `/login` (HTTP 302) for web routes, or return `401 Unauthorized` for API routes.
2. **Ownership Guard (Tenant Isolation):**
   - An authenticated user may **only** inspect and modify transactions where `expenses.user_id == session["user_id"]`.
   - If the expense does not exist, or if it belongs to another user:
     - Web route: Abort with `404 Not Found` (or redirect to `/profile` with an error message).
     - API route: Return `404 Not Found` with `{ "error": "Expense not found" }`.
     - Returning 404 for unauthorized IDs prevents resource enumeration attacks.

### B. Input Validation Rules

1. **`amount` (Required):**
   - Must be convertible to `float`.
   - Boundary: `0.01 <= amount <= 10,000,000.00`.
   - Error message: `"Amount must be greater than zero."` or `"Amount must be a valid number."`.
   - Stored rounded to 2 decimal places.

2. **`category` (Required):**
   - Must belong to canonical categories list from `get_standard_categories()`:
     `["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]`.
   - Error message: `"Please select a valid expense category."`.

3. **`date` (Required):**
   - Must be a valid ISO-8601 date string (`YYYY-MM-DD`).
   - Parsed via `datetime.strptime(date_str, "%Y-%m-%d")` or `date.fromisoformat()`.
   - Year must fall within reasonable limits (`2000 <= year <= current_year + 1`).
   - Error message: `"Please enter a valid date (YYYY-MM-DD)."`.

4. **`description` (Optional):**
   - String, trimmed of leading and trailing whitespace.
   - Maximum length: 200 characters.
   - Error message: `"Description must not exceed 200 characters."`.
   - Stored as `None` if empty.

---

## 5. Route Behaviors & Specifications

### 1. `GET /expenses/<int:id>/edit`
1. **Authentication Check:** Redirect to `/login` if `not session.get("user_id")`.
2. **Fetch Expense via `db.py`:** Call `get_user_expense_by_id(expense_id=id, user_id=session["user_id"])`.
3. **Existence & Ownership Check:** If `expense is None`, abort with HTTP 404.
4. **Context Preparation:**
   - `expense`: The dictionary representation of the expense row.
   - `categories`: Canonical list from `get_standard_categories()`.
   - `values`: Default form values dictionary populated with existing `expense` data (`amount`, `category`, `date`, `description`).
5. **Render:** Return `render_template("edit_expense.html", expense=expense, categories=categories, values=values)` (HTTP 200).

### 2. `POST /expenses/<int:id>/edit`
1. **Authentication Check:** Redirect to `/login` if unauthenticated.
2. **Ownership Check:** Verify expense exists and belongs to current user via `get_user_expense_by_id(id, session["user_id"])`. If not found, return 404.
3. **Form Extraction:**
   - `amount_raw = request.form.get("amount", "").strip()`
   - `category = request.form.get("category", "").strip()`
   - `date_str = request.form.get("date", "").strip()`
   - `description = request.form.get("description", "").strip()`
4. **Validation:** Execute validation pipeline (amount, category, date, description).
5. **On Validation Failure:**
   - Return `render_template("edit_expense.html", expense=expense, categories=categories, error=error, values=request.form), 400`.
6. **On Validation Success:**
   - Call `update_expense(expense_id=id, user_id=session["user_id"], amount=amount, category=category, date=date_str, description=description)` in `database/db.py`.
   - Flash or pass success message: `"Expense updated successfully!"`.
   - Redirect to `/profile` (HTTP 302).

### 3. `GET /api/expenses/<int:id>`
- Auth guarded (401 if unauthenticated).
- Calls `get_user_expense_by_id(id, user_id)`.
- If not found: return `jsonify({"error": "Expense not found"}), 404`.
- If found: return `jsonify({"expense": expense}), 200`.

### 4. `PUT /api/expenses/<int:id>`
- Auth guarded (401 if unauthenticated).
- Validates JSON payload `{ "amount", "category", "date", "description" }`.
- Calls `update_expense(id, user_id, ...)`.
- If not found or not owned: return `jsonify({"error": "Expense not found"}), 404`.
- On success: return `jsonify({"message": "Expense updated successfully", "expense": { ... }}), 200`.

---

## 6. Database Layer Specification (`database/db.py`)

All updates must strictly reside in `database/db.py` using parameterized SQLite queries:

### A. `get_user_expense_by_id(expense_id, user_id)`
```python
def get_user_expense_by_id(expense_id, user_id):
    """Retrieve an expense record by its primary key ID ensuring user ownership.
    
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
```

### B. `update_expense(expense_id, user_id, amount, category, date, description=None)`
```python
def update_expense(expense_id, user_id, amount, category, date, description=None):
    """Update an existing expense record belonging to a specific user.
    
    Parameters:
        expense_id (int): ID of the expense to update.
        user_id (int): ID of the authenticated owner.
        amount (float): Updated transaction amount.
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
```

---

## 7. Frontend UI / UX Specification

### A. Edit Expense Template (`templates/edit_expense.html`)
- **Inheritance:** Extends `base.html`.
- **Page Title:** `Edit Expense — Spendly`
- **Layout Structure:**
  - Back Link: `<a href="{{ url_for('profile') }}" class="back-link">← Back to Profile</a>`.
  - Main Card (`.expense-card`):
    - Title: `"Edit Expense"` in `'DM Serif Display'` typography.
    - Subtitle: `"Update transaction details. Analytics and category graphs will recalculate immediately."`.
    - Error Banner: `{% if error %}<div class="auth-error">{{ error }}</div>{% endif %}`.
    - Form Action: `POST` to `{{ url_for('edit_expense', id=expense.id) }}`.
    - Fields:
      1. **Amount Input**:
         - Currency prefix: `₹`.
         - Pre-filled: `value="{{ values.amount if values.amount is defined else expense.amount }}"`.
         - Numeric input with `step="0.01"`, `min="0.01"`, `required`.
      2. **Category Selector**:
         - `<select name="category">` with standard categories.
         - Pre-selected with the expense's current category.
      3. **Date Picker**:
         - Input `type="date"`.
         - Pre-filled: `value="{{ values.date if values.date is defined else expense.date }}"`.
      4. **Description**:
         - Text input with `maxlength="200"`.
         - Pre-filled: `value="{{ values.description if values.description is defined else (expense.description or '') }}"`.
      5. **Action Buttons (`.form-actions-row`)**:
         - Primary submit button: `"Save Changes"` (dark forest green `#143e26`).
         - Cancel link: `"Cancel"` (returns to `/profile`).

### B. Profile Page Table Integration (`templates/profile.html`)
- In `Recent Transactions` table header:
  - Add `<th>` column for actions:
    ```html
    <thead>
        <tr>
            <th>DATE</th>
            <th>DESCRIPTION</th>
            <th>CATEGORY</th>
            <th class="th-amount">AMOUNT</th>
            <th class="th-actions">ACTION</th>
        </tr>
    </thead>
    ```
- In server-side Jinja loop (`{% for exp in recent_expenses %}`):
  - Add table cell with edit button:
    ```html
    <td class="td-actions">
        <a href="{{ url_for('edit_expense', id=exp.id) }}" class="btn-table-edit" title="Edit transaction">Edit</a>
    </td>
    ```
- In client-side JS dynamic renderer (`renderRecentTransactions(expenses)`):
  - Add `<td class="td-actions"><a href="/expenses/${exp.id}/edit" class="btn-table-edit">Edit</a></td>` so dynamically filtered tables retain the edit button.

### C. CSS Styling (`static/css/style.css`)
- **`.btn-table-edit`**:
  - Compact text pill button: font-size `0.75rem`, font-weight `500`, padding `0.2rem 0.65rem`.
  - Border: `1px solid #e5e7eb`, border-radius `6px`.
  - Color: `#4b5563`, Background: `#f9fafb`.
  - Hover: Background `#143e26`, Color `#ffffff`, Border `#143e26`.
- **`.th-actions` / `.td-actions`**:
  - Right-aligned or centered action column styling.

---

## 8. Error Handling & Edge Cases

| Scenario | Expected Behavior | Status Code |
| :--- | :--- | :--- |
| Unauthenticated user accesses `/expenses/<id>/edit` | Redirect to `/login` | `302 Found` |
| Expense ID does not exist in database | Return standard 404 page / message | `404 Not Found` |
| Expense ID belongs to another user (IDOR attempt) | Block access and return 404 (prevents leakage) | `404 Not Found` |
| Negative or zero amount on submit | Re-render form with error `"Amount must be greater than zero."` | `400 Bad Request` |
| Non-numeric amount | Re-render form with error `"Amount must be a valid number."` | `400 Bad Request` |
| Unrecognized category | Re-render form with error `"Please select a valid expense category."` | `400 Bad Request` |
| Invalid date string | Re-render form with error `"Please enter a valid date (YYYY-MM-DD)."` | `400 Bad Request` |
| Description > 200 characters | Re-render form with error `"Description must not exceed 200 characters."` | `400 Bad Request` |
| Successful update | Redirect to `/profile` with updated metrics & recent transactions | `302 Found` |

---

## 9. Definition of Done

- [ ] `database/db.py` implements `get_user_expense_by_id(expense_id, user_id)` and `update_expense(expense_id, user_id, amount, category, date, description)`.
- [ ] Parameterized queries used exclusively; zero raw SQL in `app.py`.
- [ ] `app.py` implements authenticated, ownership-guarded `GET /expenses/<int:id>/edit` and `POST /expenses/<int:id>/edit`.
- [ ] `app.py` implements authenticated API endpoints `GET /api/expenses/<int:id>` and `PUT /api/expenses/<int:id>`.
- [ ] `templates/edit_expense.html` created matching Spendly aesthetic design language.
- [ ] `templates/profile.html` table headers, Jinja loops, and client-side JavaScript include "Edit" action links.
- [ ] IDOR protection verified: Users cannot view or modify transactions belonging to other users.
- [ ] Comprehensive test suite verifies authorization, input validation boundaries, database persistence, and profile recalculation.
