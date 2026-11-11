# Spec 07 — Add Expense (Create Transaction)

## 1. Overview

Implement the **Add Expense** feature (Step 7) in the Spendly personal finance application.

Currently, the application displays a user profile dashboard with analytical metrics (`TOTAL SPENT`, `TRANSACTIONS`, `TOP CATEGORY`), a `Recent Transactions` history table, `By Category` progress distribution graphs, and a temporal date filter (Step 6). However, users cannot log their own transactions through the interface; expenses currently exist only through mock seeding.

This specification defines the complete Create (C in CRUD) transaction management flow, enabling authenticated users to record new expenses with an amount, category, date, and description.

In accordance with core project architectural constraints (**"for database use only db.py"**):
- All database mutation operations are strictly encapsulated in `database/db.py`.
- No raw SQL queries or cursor executions exist in `app.py`.
- Authentication guards protect all expense logging endpoints, rejecting unauthenticated requests.
- All database queries enforce parameterized SQL bindings to eliminate SQL injection vulnerabilities.

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

---

## 3. Routes & Endpoints

| Method | Endpoint | Query / Body Parameters | Access | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/expenses/add` | None | Authenticated | Renders the expense creation form with pre-populated today's date and standard categories |
| `POST` | `/expenses/add` | `amount`, `category`, `date`, `description` (Form Data) | Authenticated | Validates input, inserts new expense via `db.py`, flashes success message, and redirects to `/profile` |
| `POST` | `/api/expenses` | `{ "amount", "category", "date", "description" }` (JSON) | Authenticated | REST API endpoint to programmatically create an expense; returns JSON representation of created record |

---

## 4. Business Logic & Validation Rules

### A. Input Field Requirements

1. **`amount` (Required)**:
   - Must be a valid positive numeric value (integer or float).
   - Minimum value: `0.01` (cannot be zero or negative).
   - Maximum value: `10,000,000.00` (reasonable threshold against overflow).
   - Formatted to 2 decimal places before persistence.

2. **`category` (Required)**:
   - Must belong to the pre-approved standard categories list:
     - `Food`
     - `Transport`
     - `Bills`
     - `Health`
     - `Entertainment`
     - `Shopping`
     - `Other`
   - Case-sensitive or title-cased upon validation.

3. **`date` (Required)**:
   - Must be a valid ISO-8601 date string in `YYYY-MM-DD` format.
   - Default value for GET form: Today's date (`date.today().isoformat()`).
   - Must be parseable by Python's `datetime.strptime(d, "%Y-%m-%d")` or `date.fromisoformat()`.
   - Cannot exceed future threshold (e.g. more than 1 year in the future) or predate reasonable minimum (e.g. before year 2000).

4. **`description` (Optional)**:
   - Optional text detailing the transaction (e.g. "Groceries at BigBasket").
   - Maximum length: 200 characters.
   - Stripped of leading and trailing whitespace. Stored as `None` or empty string if left blank.

### B. Route Behaviors

#### 1. `GET /expenses/add`
- **Auth Guard:** If `not session.get("user_id")`, redirect to `/login` with HTTP 302.
- **Context:**
  - `today`: Current date string in `YYYY-MM-DD` format.
  - `categories`: `["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]`.
  - `selected_category`: Default to `"Food"` or none.
- **Response:** Renders `templates/add_expense.html` (HTTP 200).

#### 2. `POST /expenses/add`
- **Auth Guard:** If `not session.get("user_id")`, redirect to `/login` with HTTP 302.
- **Form Data Extraction:**
  - `amount_raw = request.form.get("amount", "").strip()`
  - `category = request.form.get("category", "").strip()`
  - `date_str = request.form.get("date", "").strip()`
  - `description = request.form.get("description", "").strip()`
- **Validation Pipeline:**
  1. Amount validation: Float conversion check, `amount > 0`.
  2. Category validation: `category in VALID_CATEGORIES`.
  3. Date validation: Valid format `YYYY-MM-DD`.
  4. Description length: `<= 200` chars.
- **Failure:** If validation fails, re-render `templates/add_expense.html` with error message, status code 400, preserving previously entered inputs.
- **Success:**
  1. Calls `create_expense(user_id=session["user_id"], amount=amount, category=category, date=date_str, description=description)` in `database/db.py`.
  2. Sets flash or success message: `"Expense of ₹{amount:,.2f} added successfully!"`.
  3. Redirects to `/profile` (HTTP 302).

#### 3. `POST /api/expenses`
- **Auth Guard:** Return `401 Unauthorized` if `not session.get("user_id")`.
- **Payload Parsing:** JSON payload from `request.get_json()`.
- **Validation:** Same rules as HTML form. Returns `400 Bad Request` with `{ "error": "<details>" }` on failure.
- **Success:** Returns `201 Created` with:
  ```json
  {
    "message": "Expense created successfully",
    "expense": {
      "id": 9,
      "user_id": 4,
      "amount": 450.0,
      "category": "Food",
      "date": "2026-11-11",
      "description": "Groceries from BigBasket"
    }
  }
  ```

---

## 5. Database Layer Specification (`database/db.py`)

Strictly add the creation function using parameterized SQL:

```python
def create_expense(user_id, amount, category, date, description=None):
    """Insert a new expense record for a user.
    
    Parameters:
        user_id (int): ID of the authenticated user.
        amount (float): Transaction amount (must be positive).
        category (str): Valid category name.
        date (str): Transaction date in YYYY-MM-DD ISO format.
        description (str, optional): Short note or description.
        
    Returns:
        int: The auto-incremented primary key ID of the newly created expense.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?);
            """,
            (user_id, round(float(amount), 2), category.strip(), str(date).strip(), description.strip() if description else None)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()
```

Also expose a helper to retrieve standard categories:
```python
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
```

---

## 6. Frontend UI / UX Specification

### A. Add Expense Page Template (`templates/add_expense.html`)
- Extends `base.html`.
- Styled using Spendly's core design system tokens (`--paper`, `--paper-card`, `--ink`, `--accent`, `--border`).
- **Layout Structure:**
  - Breadcrumb / Back Link: `<a href="{{ url_for('profile') }}" class="back-link">← Back to Profile</a>`.
  - Central Card Component (`.expense-card`):
    - Title: `"Add Expense"` in `'DM Serif Display'`.
    - Subtitle: `"Record a transaction to track your spending and update analytics."`.
    - Alert Banner (`.auth-error` / `.alert-error`) if validation errors occur.
    - Form Elements:
      1. **Amount Input**:
         - Label: `Amount (₹)`
         - Input type: `number`, step: `0.01`, min: `0.01`, placeholder: `0.00`, autofocus, required.
         - Styled with high-contrast font and clean focus ring.
      2. **Category Selector**:
         - Label: `Category`
         - Input type: `<select>` dropdown populated dynamically with `Food`, `Transport`, `Bills`, `Health`, `Entertainment`, `Shopping`, `Other`.
      3. **Date Input**:
         - Label: `Date`
         - Input type: `date`, required, defaulted to today's date (`{{ today }}`).
      4. **Description Input**:
         - Label: `Description (Optional)`
         - Input type: `text`, max: 200, placeholder: `e.g., Grocery shopping, Uber ride`.
      5. **Action Buttons**:
         - Primary submit button: `"Save Expense"` (dark green `#143e26`, full width or prominent).
         - Secondary cancel button / link: `"Cancel"` (redirects to `/profile`).

### B. Global Navigation Updates
- **`templates/base.html` Navbar:**
  - When user is logged in (`{% if session.get('user_id') %}`), insert an `+ Add Expense` CTA pill link next to the profile/sign-out controls:
    `<a href="{{ url_for('add_expense') }}" class="btn-nav-add">+ Add Expense</a>`.
- **`templates/profile.html` Dashboard Integration:**
  - Add an `+ Add Expense` button directly within the `Recent Transactions` header card:
    `<a href="{{ url_for('add_expense') }}" class="btn-action-add">+ Add Expense</a>`.

---

## 7. Error Handling & Edge Cases

1. **Non-Numeric / Negative Amount:**
   - Handled server-side and client-side (`min="0.01"`). Form returns clear error: `"Amount must be greater than zero."`.
2. **Invalid Category:**
   - If user tampers with the `<select>` options, server rejects the request with `"Please select a valid expense category."`.
3. **Invalid Date Format:**
   - Server validates ISO-8601 parsing (`YYYY-MM-DD`). Rejects invalid strings like `"abc"` or empty date.
4. **Unauthenticated Session:**
   - `GET /expenses/add` and `POST /expenses/add` redirect to `/login`.
   - `POST /api/expenses` returns `401 Unauthorized`.
5. **Special Characters / XSS in Description:**
   - Jinja2 auto-escapes all HTML in templates.
   - Text is trimmed and validated to <= 200 chars.
6. **Immediate Profile Dashboard Synchronization:**
   - Once inserted, navigating to `/profile` immediately recalculates `TOTAL SPENT`, `TRANSACTIONS`, `TOP CATEGORY`, `Recent Transactions`, and `By Category` progress bars.

---

## 8. Definition of Done

- [ ] `database/db.py` contains `create_expense(user_id, amount, category, date, description)` with parameterized SQL and strict connection cleanup.
- [ ] `database/db.py` exposes `get_standard_categories()`.
- [ ] `app.py` implements `GET /expenses/add` (renders form with today's date and categories) and `POST /expenses/add` (validates, inserts, redirects to `/profile`).
- [ ] `app.py` implements authenticated `POST /api/expenses` returning 201 Created on success and 400 Bad Request on validation failure.
- [ ] `templates/add_expense.html` created matching Spendly aesthetic design tokens.
- [ ] `templates/base.html` and `templates/profile.html` include navigation links to `add_expense`.
- [ ] Unit and integration tests verify authentication guards, validation boundaries, DB insertion, and profile synchronization.
