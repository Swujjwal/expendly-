# Spec 09 — Delete Expense (Delete Transaction & Automated Tests)

## 1. Overview

Implement the **Delete Expense (Delete Transaction & Automated Tests)** feature (Step 9) in the Spendly personal finance application.

Step 9 completes the full CRUD (Create, Read, Update, Delete) capability of the Spendly personal finance platform. Users can already create expenses (Step 7), inspect them via aggregate metrics, category distribution, recent transactions, and date filters (Steps 4–6), and edit existing records (Step 8). 

This specification introduces safe, ownership-guarded deletion of transactions, ensuring that deleting an expense immediately recalculates financial analytics (`TOTAL SPENT`, `TRANSACTIONS`, `TOP CATEGORY`, and `By Category` progress bars) across the platform.

In accordance with core project architectural constraints (**"for database use only db.py"**):
- All database deletion queries are encapsulated strictly within `database/db.py`.
- No raw SQL queries or cursor executions exist in `app.py`.
- Strict user ownership and IDOR (Insecure Direct Object Reference) guards guarantee users can only delete their own transactions.
- Deletions require explicit HTTP POST or DELETE verbs to protect against accidental crawling or CSRF vulnerabilities.
- Automated tests verify deletion flows, tenant isolation, and analytical recalculation.

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
- **Step 8: Edit Expense** (`update_expense()`, `get_user_expense_by_id()`, `templates/edit_expense.html`)

---

## 3. Routes & Endpoints

| Method | Endpoint | Query / Body Parameters | Access | Description |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/expenses/<int:id>/delete` | None | Authenticated (Owner) | Deletes the specified expense record and redirects to `/profile` |
| `DELETE` | `/api/expenses/<int:id>` | None | Authenticated (Owner) | REST API endpoint to programmatically delete an expense by ID |

> **Security Note on HTTP Verbs:** Deletion MUST NEVER be triggered via a bare `GET` request. Web crawlers, browser link pre-fetchers, and accidental clicks could lead to catastrophic data loss if `GET` were used for mutations.

---

## 4. Business Logic & Security Rules

### A. Authorization & Security (IDOR Prevention)

1. **Authentication Guard:**
   - Unauthenticated requests to `POST /expenses/<int:id>/delete` redirect to `/login` (HTTP 302).
   - Unauthenticated requests to `DELETE /api/expenses/<int:id>` return `401 Unauthorized`.
2. **Ownership Guard (Tenant Isolation):**
   - An authenticated user may **only** delete transactions where `expenses.user_id == session["user_id"]`.
   - If an expense does not exist, or if it belongs to another user:
     - Web route: Abort with `404 Not Found`.
     - API route: Return `404 Not Found` with `{ "error": "Expense not found" }`.
   - Enforcing `WHERE id = ? AND user_id = ?` at the database level guarantees atomic tenant isolation.

### B. Analytical Recalculation

When an expense is deleted:
1. `TOTAL SPENT` decreases by the deleted expense's `amount`.
2. `TRANSACTIONS` count decreases by 1.
3. The deleted transaction disappears from `Recent Transactions`.
4. `By Category` progress bars recalculate their total amount and percentage shares immediately.
5. If the deleted expense was the only transaction in the chosen date range or lifetime, the dashboard gracefully transitions to the clean empty state (`₹0.00`, `0` transactions, `TOP CATEGORY: —`).

---

## 5. Route Behaviors & Specifications

### 1. `POST /expenses/<int:id>/delete`
1. **Authentication Check:** Redirect to `/login` if `not session.get("user_id")`.
2. **Database Deletion via `db.py`:** Call `delete_expense(expense_id=id, user_id=session["user_id"])`.
3. **Ownership & Existence Verification:**
   - If `delete_expense` returns `False`: Abort with HTTP `404 Not Found`.
4. **On Success:**
   - Set flash message: `"Expense deleted successfully."`.
   - Return redirect (`302`) to `/profile`.

### 2. `DELETE /api/expenses/<int:id>`
1. **Authentication Check:** Return `401 Unauthorized` if `not session.get("user_id")`.
2. **Database Deletion via `db.py`:** Call `delete_expense(expense_id=id, user_id=session["user_id"])`.
3. **Response:**
   - If `False`: Return `jsonify({"error": "Expense not found"}), 404`.
   - If `True`: Return `jsonify({"message": "Expense deleted successfully", "id": id}), 200`.

---

## 6. Database Layer Specification (`database/db.py`)

All deletion logic resides strictly in `database/db.py` using parameterized SQL:

### `delete_expense(expense_id, user_id)`
```python
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
```

---

## 7. Frontend UI / UX Specification

### A. Recent Transactions Table Integration (`templates/profile.html`)
- In `Recent Transactions` table header:
  - Header column: `<th class="th-actions">ACTIONS</th>`.
- In server-side Jinja loop (`{% for exp in recent_expenses %}`):
  - In each row's `.td-actions` cell, display both "Edit" and "Delete" buttons side-by-side:
    ```html
    <td class="td-actions">
        <a href="{{ url_for('edit_expense', id=exp.id) }}" class="btn-table-edit" title="Edit transaction">Edit</a>
        <form method="POST" action="{{ url_for('delete_expense', id=exp.id) }}" class="inline-delete-form" onsubmit="return confirm('Are you sure you want to delete this expense?');">
            <button type="submit" class="btn-table-delete" title="Delete transaction">Delete</button>
        </form>
    </td>
    ```
- In client-side JS dynamic renderer (`renderRecentTransactions(expenses)`):
  - Dynamically render the same action buttons for each transaction item:
    ```javascript
    <td class="td-actions">
        <a href="/expenses/${exp.id}/edit" class="btn-table-edit" title="Edit transaction">Edit</a>
        <form method="POST" action="/expenses/${exp.id}/delete" class="inline-delete-form" onsubmit="return confirm('Are you sure you want to delete this expense?');">
            <button type="submit" class="btn-table-delete" title="Delete transaction">Delete</button>
        </form>
    </td>
    ```

### B. Edit Expense Page Integration (`templates/edit_expense.html`)
- In `.form-actions-row`, add an optional secondary Delete button:
  - Gives users the convenience of deleting an expense directly while reviewing its details on the edit page.

### C. Visual Design & CSS Styling (`static/css/style.css`)
- **`.btn-table-delete`**:
  - Compact text pill button: font-size `0.75rem`, font-weight `500`, padding `0.25rem 0.65rem`.
  - Border: `1px solid #fee2e2`, border-radius `6px`.
  - Color: `#dc2626` (crimson red), Background: `#fef2f2`.
  - Hover: Background `#dc2626`, Color `#ffffff`, Border `#dc2626`.
- **`.inline-delete-form`**:
  - `display: inline-block; margin: 0; padding: 0;`
- **`.td-actions`**:
  - `display: flex; align-items: center; justify-content: flex-end; gap: 0.4rem;`

---

## 8. Error Handling & Edge Cases

| Scenario | Expected Behavior | Status Code |
| :--- | :--- | :--- |
| Unauthenticated user sends POST to `/expenses/<id>/delete` | Redirect to `/login` | `302 Found` |
| Unauthenticated client sends DELETE to `/api/expenses/<id>` | Return `401 Unauthorized` JSON | `401 Unauthorized` |
| Expense ID does not exist in database | Return `404 Not Found` | `404 Not Found` |
| User A attempts to delete User B's expense ID (IDOR) | Return `404 Not Found` (blocks deletion and prevents existence leakage) | `404 Not Found` |
| User triggers deletion via bare GET request | Block deletion; redirect to `/profile` or return 405 Method Not Allowed | `405 / 302` |
| Deleting the last transaction for a user | Metrics transition cleanly to zero (`₹0.00`, `0`, `—`) with empty states | `302 Found` |
| Concurrent deletion requests | First succeeds (returns 200/302); second returns 404 cleanly without database corruption | `404 Not Found` |

---

## 9. Definition of Done

- [ ] `database/db.py` implements `delete_expense(expense_id, user_id)` with parameterized SQLite queries.
- [ ] Strictly adheres to **"for database use only db.py"** (zero raw SQL in `app.py`).
- [ ] `app.py` implements authenticated `POST /expenses/<int:id>/delete` route with user ownership verification.
- [ ] `app.py` implements authenticated `DELETE /api/expenses/<int:id>` REST endpoint.
- [ ] `templates/profile.html` Recent Transactions table incorporates delete action with browser confirmation prompt in both server-rendered and client-rendered JavaScript.
- [ ] `static/css/style.css` styles `.btn-table-delete`, `.inline-delete-form`, and action button layout.
- [ ] IDOR protection verified: Non-owners cannot delete another user's expenses.
- [ ] Comprehensive test suite verifies authorization, database deletion, analytics recalculation, and empty state transitions.
