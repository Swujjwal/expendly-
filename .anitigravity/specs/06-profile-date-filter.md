# Spec 06 — Date Range Filter for Profile Page & Analytics

## 1. Overview

Implement comprehensive **Date Range Filtering for the User Profile & Analytics Dashboard** (Step 6) in the Spendly personal finance application.

The profile dashboard displays a user's financial overview, activity metrics (`TOTAL SPENT`, `TRANSACTIONS`, `TOP CATEGORY`), `Recent Transactions` history, and `By Category` distribution graphs. Currently, all metrics aggregate lifetime spending without time boundaries.

This specification introduces a flexible, production-grade **date filtering system** supporting both predefined temporal presets and custom date ranges. It empowers users to analyze spending across specific periods (such as current month, trailing 30 days, or past calendar months) with instantaneous UI synchronization.

In accordance with core project architectural constraints (**"for database use only db.py"**):
- All date-boundary filtering queries are encapsulated strictly within `database/db.py`.
- No raw SQL queries or string concatenations exist in `app.py`.
- Endpoints enforce session-based authentication guards, rejecting unauthenticated requests.

---

## 2. Depends on

- **Step 1: Database Setup** (`database/db.py`)
  - `expenses` table schema: `(id, user_id, amount, category, date, description, created_at)`
  - Parameterized SQLite queries with `PRAGMA foreign_keys = ON;`
- **Step 2: User Registration** (`users` table)
- **Step 3: User Authentication** (`session["user_id"]`, login guards)
- **Step 4: Profile Page Design** (`templates/profile.html`, `static/css/style.css`)
- **Step 5: Profile Backend Routes** (`/api/expenses`, `/api/stats/summary`, `/api/stats/categories`)

---

## 3. Routes & Endpoints

| Method | Endpoint | Query Parameters | Access | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/profile` | `period`, `start_date`, `end_date` | Authenticated | Renders profile dashboard with server-side filtered metrics, transactions, and category graphs |
| `GET` | `/api/expenses` | `limit`, `offset`, `start_date`, `end_date` | Authenticated | Returns JSON list of user expenses bounded by date range with total count |
| `GET` | `/api/stats/summary` | `start_date`, `end_date` | Authenticated | Returns JSON summary metrics (`total_count`, `total_spent`, `average_spent`) for the period |
| `GET` | `/api/stats/categories` | `start_date`, `end_date` | Authenticated | Returns JSON breakdown of category spending, transaction counts, and percentages for the period |

---

## 4. Date Range Presets & Calculation Logic

The filter supports 5 selectable temporal scopes. All dates are evaluated in ISO-8601 (`YYYY-MM-DD`) format:

### A. Predefined Presets

1. **`this_month` (Default)**:
   - **Start Date:** First day of the current calendar month (`YYYY-MM-01`).
   - **End Date:** Today's date (`date.today().isoformat()`).
   - *Example:* On `2026-11-09`, start is `2026-11-01` and end is `2026-11-09`.

2. **`last_30_days`**:
   - **Start Date:** Exactly 30 days prior (`date.today() - timedelta(days=30)`).
   - **End Date:** Today's date (`date.today().isoformat()`).
   - *Example:* On `2026-11-09`, start is `2026-10-10` and end is `2026-11-09`.

3. **`last_month`**:
   - **Start Date:** First day of the preceding calendar month.
   - **End Date:** Final day of the preceding calendar month.
   - *Calculation:*
     ```python
     first_this_month = today.replace(day=1)
     last_prev_month = first_this_month - timedelta(days=1)
     first_prev_month = last_prev_month.replace(day=1)
     ```
   - *Example:* On `2026-11-09`, start is `2026-10-01` and end is `2026-10-31`. Handles January rollbacks to December of prior year cleanly.

4. **`all_time`**:
   - **Start Date:** `None` (unbounded lower limit).
   - **End Date:** `None` (unbounded upper limit).
   - Aggregates the entire lifetime expense history.

5. **`custom`**:
   - **Start Date:** User-supplied `start_date` (`YYYY-MM-DD`).
   - **End Date:** User-supplied `end_date` (`YYYY-MM-DD`).
   - If either boundary is missing or invalid:
     - Fallback gracefully to `this_month` or clamp to today.

---

## 5. Route Behaviors & Business Logic

### A. Helper: Period Resolver (`resolve_date_range`)
Encapsulate date resolution in a reusable utility:
```python
def resolve_date_range(period, custom_start=None, custom_end=None):
    today = date.today()
    if period == "last_30_days":
        start = (today - timedelta(days=30)).isoformat()
        end = today.isoformat()
    elif period == "last_month":
        last_day_prev = today.replace(day=1) - timedelta(days=1)
        start = last_day_prev.replace(day=1).isoformat()
        end = last_day_prev.isoformat()
    elif period == "all_time":
        start = None
        end = None
    elif period == "custom" and custom_start and custom_end:
        # Validate format & enforce start <= end
        start = custom_start[:10]
        end = custom_end[:10]
        if start > end:
            start, end = end, start
    else:  # default: this_month
        period = "this_month"
        start = today.replace(day=1).isoformat()
        end = today.isoformat()
    return period, start, end
```

### B. `GET /profile`
1. **Authentication Guard:** If `not session.get("user_id")`, redirect to `/login` (HTTP 302).
2. **Query Parameters:**
   - Extract `period = request.args.get("period", "this_month")`.
   - Extract `custom_start = request.args.get("start_date")`.
   - Extract `custom_end = request.args.get("end_date")`.
3. **Resolution:** Call `resolve_date_range(period, custom_start, custom_end)`.
4. **Data Retrieval via `db.py`:**
   - User profile: `get_user_by_id(user_id)`
   - Activity metrics: `get_user_stats(user_id, start_date=start, end_date=end)`
   - Top category: Computed from `get_category_breakdown(user_id, start_date=start, end_date=end)`
   - Recent transactions: `get_user_expenses(user_id, limit=5, start_date=start, end_date=end)`
5. **Render Context:**
   Pass `selected_period`, `start_date`, `end_date`, `stats`, `top_category`, `recent_expenses`, `categories` to `profile.html`.

### C. `GET /api/expenses`
1. **Auth Guard:** Return `401 Unauthorized` if unauthenticated.
2. **Parameters:**
   - `limit` (int, optional)
   - `offset` (int, default 0)
   - `start_date` (ISO date string, optional)
   - `end_date` (ISO date string, optional)
3. **Execution:** Calls `get_user_expenses(user_id, limit=limit, offset=offset, start_date=start_date, end_date=end_date)`.
4. **Response:**
   ```json
   {
     "expenses": [ ... ],
     "count": 5,
     "start_date": "2026-11-01",
     "end_date": "2026-11-09"
   }
   ```

### D. `GET /api/stats/summary`
1. **Auth Guard:** Return `401 Unauthorized` if unauthenticated.
2. **Parameters:** `start_date`, `end_date` (optional).
3. **Execution:** Calls `get_user_stats(user_id, start_date=start_date, end_date=end_date)`.
4. **Response:**
   ```json
   {
     "total_count": 8,
     "total_spent": 6170.0,
     "average_spent": 771.25,
     "start_date": "2026-11-01",
     "end_date": "2026-11-09"
   }
   ```

### E. `GET /api/stats/categories`
1. **Auth Guard:** Return `401 Unauthorized` if unauthenticated.
2. **Parameters:** `start_date`, `end_date` (optional).
3. **Execution:** Calls `get_category_breakdown(user_id, start_date=start_date, end_date=end_date)`.
4. **Calculations:** Sums total spent and attaches percentage share for each category in the given date range.
5. **Response:**
   ```json
   {
     "categories": [
       { "category": "Shopping", "count": 1, "total_amount": 2200.0, "percentage": 35.7 },
       { "category": "Bills", "count": 1, "total_amount": 1500.0, "percentage": 24.3 }
     ],
     "total_spent": 6170.0,
     "start_date": "2026-11-01",
     "end_date": "2026-11-09"
   }
   ```

---

## 6. Database Layer Updates (`database/db.py`)

All queries must use dynamic parameter binding to support optional date bounds while strictly preventing SQL injection:

### A. `get_user_stats(user_id, start_date=None, end_date=None)`
```python
def get_user_stats(user_id, start_date=None, end_date=None):
    """Calculate summary stats for a user's expenses with optional date range."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = "SELECT COUNT(*) as total_count, COALESCE(SUM(amount), 0.0) as total_spent FROM expenses WHERE user_id = ?"
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
```

### B. `get_user_expenses(user_id, limit=None, offset=0, start_date=None, end_date=None)`
```python
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
```

### C. `get_category_breakdown(user_id, start_date=None, end_date=None)`
```python
def get_category_breakdown(user_id, start_date=None, end_date=None):
    """Retrieve category totals and counts grouped by category with optional date range."""
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
```

---

## 7. Frontend UI / UX Specification

### A. Date Filter Control Bar
Positioned directly above the 3 metric stat cards in `templates/profile.html`:

```html
<div class="profile-filter-card">
    <div class="filter-presets-group">
        <a href="?period=this_month" class="filter-pill {% if selected_period == 'this_month' %}active{% endif %}" data-period="this_month">This Month</a>
        <a href="?period=last_30_days" class="filter-pill {% if selected_period == 'last_30_days' %}active{% endif %}" data-period="last_30_days">Last 30 Days</a>
        <a href="?period=last_month" class="filter-pill {% if selected_period == 'last_month' %}active{% endif %}" data-period="last_month">Last Month</a>
        <a href="?period=all_time" class="filter-pill {% if selected_period == 'all_time' %}active{% endif %}" data-period="all_time">All Time</a>
        <button type="button" class="filter-pill filter-custom-trigger {% if selected_period == 'custom' %}active{% endif %}" id="customRangeToggle">Custom</button>
    </div>

    <!-- Custom Date Range Form (collapsible / expandable) -->
    <form method="GET" action="{{ url_for('profile') }}" class="custom-range-form {% if selected_period != 'custom' %}is-hidden{% endif %}" id="customRangeForm">
        <input type="hidden" name="period" value="custom">
        <div class="custom-range-inputs">
            <div class="date-field">
                <label for="startDate">From</label>
                <input type="date" id="startDate" name="start_date" value="{{ start_date or '' }}" required>
            </div>
            <div class="date-field">
                <label for="endDate">To</label>
                <input type="date" id="endDate" name="end_date" value="{{ end_date or '' }}" required>
            </div>
            <button type="submit" class="btn-filter-apply">Apply</button>
            <a href="{{ url_for('profile') }}" class="btn-filter-reset">Reset</a>
        </div>
    </form>
</div>
```

### B. Visual Design & CSS Styling (`static/css/style.css`)
- **Filter Card Container:**
  - Background: `#ffffff`
  - Border: `1px solid #e5e7eb`
  - Border-radius: `14px`
  - Padding: `1rem 1.25rem`
  - Box shadow: `0 1px 3px rgba(0, 0, 0, 0.02)`
- **Preset Pills (`.filter-pill`):**
  - Padding: `0.4rem 0.95rem`
  - Border-radius: `9999px`
  - Font size: `0.8125rem`, font-weight: `500`
  - Color: `#4b5563`, Background: `#f3f4f6`
  - Hover: Background `#e5e7eb`, Color `#111827`
  - Active: Background `#153e26` (dark forest green), Color `#ffffff`
- **Custom Range Inputs:**
  - Integrated date inputs with clean borders (`#d1d5db`), focus rings (`#153e26`), and subtle labels.
  - Smooth display toggle when "Custom" pill is clicked.

### C. Client-Side Asynchronous Refresh Hook
When switching presets or applying dates, client-side JavaScript updates query strings on the API requests:
```javascript
async function fetchFilteredDashboard(startDate, endDate) {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const queryString = params.toString() ? `?${params.toString()}` : "";

    const [txRes, catRes, sumRes] = await Promise.all([
        fetch(`{{ url_for('api_expenses') }}${queryString ? queryString + '&limit=5' : '?limit=5'}`),
        fetch(`{{ url_for('api_stats_categories') }}${queryString}`),
        fetch(`{{ url_for('api_stats_summary') }}${queryString}`)
    ]);

    // Re-renders metrics, recent transactions table, and category progress bars
}
```

---

## 8. Error Handling & Edge Cases

1. **Inverted Date Boundaries:**
   - If `start_date > end_date` in custom input, swap values gracefully without raising unhandled errors.
2. **Invalid Date Format:**
   - If `start_date` or `end_date` is not `YYYY-MM-DD`, fallback to standard `this_month` bounds.
3. **Zero Transactions in Selected Period:**
   - Metrics display `₹0.00`, `0` transactions, and `TOP CATEGORY: —`.
   - Recent Transactions displays: `"No recent transactions found for this date range."`.
   - By Category displays: `"No category spending recorded for this date range."`.
4. **Future Dates:**
   - Queries execute cleanly and return 0 results without errors if dates are set in the future.
5. **Session Expiry:**
   - Protected API routes return HTTP 401; web routes redirect to `/login`.

---

## 9. Definition of Done

- [ ] `database/db.py` supports optional `start_date` and `end_date` filters in `get_user_stats`, `get_user_expenses`, and `get_category_breakdown`.
- [ ] All database queries strictly use parameterized SQL (zero SQL string formatting).
- [ ] `app.py` resolves temporal presets (`this_month`, `last_30_days`, `last_month`, `all_time`, `custom`).
- [ ] Endpoints `/api/expenses`, `/api/stats/summary`, and `/api/stats/categories` support `start_date` and `end_date` query parameters.
- [ ] `profile.html` includes filter toolbar with active pill states and custom date pickers.
- [ ] Metric cards (`TOTAL SPENT`, `TRANSACTIONS`, `TOP CATEGORY`) recalculate accurately for the selected period.
- [ ] `Recent Transactions` and `By Category` progress bars reflect the filtered date range.
- [ ] Clean empty states render when no transactions fall within the selected period.
- [ ] Full test coverage verifies all presets, custom date inputs, and authentication guards.
