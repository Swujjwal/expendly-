import os
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import (
    init_db, seed_db, get_user_by_email, create_user,
    get_user_by_id, update_user_name, get_user_stats,
    get_user_expenses, get_category_breakdown
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "spendly-dev-secret-key-change-in-production")


# ------------------------------------------------------------------ #
# Database initialization                                             #
# ------------------------------------------------------------------ #

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # 1. Validate required fields
        if not name or not email or not password:
            return render_template(
                "register.html",
                error="All fields are required.",
                name=name,
                email=email
            )

        # 2. Validate name length
        if len(name) > 100:
            return render_template(
                "register.html",
                error="Full name must not exceed 100 characters.",
                name=name,
                email=email
            )

        # 3. Validate email structure
        if "@" not in email or "." not in email:
            return render_template(
                "register.html",
                error="Please enter a valid email address.",
                name=name,
                email=email
            )

        # 4. Validate password length
        if len(password) < 8:
            return render_template(
                "register.html",
                error="Password must be at least 8 characters long.",
                name=name,
                email=email
            )

        # 5. Database operations via db.py
        if get_user_by_email(email):
            return render_template(
                "register.html",
                error="An account with this email already exists.",
                name=name,
                email=email
            )

        password_hash = generate_password_hash(password)
        user_id = create_user(name, email, password_hash)
        if not user_id:
            return render_template(
                "register.html",
                error="An account with this email already exists.",
                name=name,
                email=email
            )

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # 1. Validate required fields
        if not email or not password:
            return render_template(
                "login.html",
                error="All fields are required.",
                email=email
            )

        # 2. Retrieve user and verify credentials
        user = get_user_by_email(email)
        if not user or not check_password_hash(user["password_hash"], password):
            return render_template(
                "login.html",
                error="Invalid email or password.",
                email=email
            )

        # 3. Establish session
        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]

        return redirect(url_for("profile"))

    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def resolve_date_range(period, custom_start=None, custom_end=None):
    """Resolve a temporal preset or custom date range into ISO (YYYY-MM-DD) boundaries."""
    today = date.today()

    if period == "last_30_days":
        start = (today - timedelta(days=30)).isoformat()
        end = today.isoformat()
    elif period == "last_month":
        # First day of this month minus 1 day gives the last day of previous month
        first_of_this_month = today.replace(day=1)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        start = last_of_prev_month.replace(day=1).isoformat()
        end = last_of_prev_month.isoformat()
    elif period == "all_time":
        start = None
        end = None
    elif period == "custom" and custom_start and custom_end:
        start = str(custom_start).strip()[:10]
        end = str(custom_end).strip()[:10]
        # Inverted date boundary auto-correction
        if start > end:
            start, end = end, start
    else:
        # Default preset: this_month
        period = "this_month"
        start = today.replace(day=1).isoformat()
        end = today.isoformat()

    return period, start, end


@app.route("/profile", methods=["GET", "POST"])
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if not user:
        session.clear()
        return redirect(url_for("login"))

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
            user = get_user_by_id(user_id)
            success = "Profile updated successfully."

    # Parse date range filter query params
    period = request.args.get("period", "this_month")
    req_start = request.args.get("start_date")
    req_end = request.args.get("end_date")

    selected_period, start_date, end_date = resolve_date_range(period, req_start, req_end)

    stats = get_user_stats(user_id, start_date=start_date, end_date=end_date)
    categories = get_category_breakdown(user_id, start_date=start_date, end_date=end_date)
    recent_raw = get_user_expenses(user_id, limit=5, start_date=start_date, end_date=end_date)
    total_spent = stats["total_spent"]

    # Member since formatting
    member_since = "Member"
    if user and "created_at" in user.keys() and user["created_at"]:
        try:
            member_since = datetime.fromisoformat(str(user["created_at"])[:10]).strftime("Member since %B %Y")
        except Exception:
            member_since = f"Member since {str(user['created_at'])[:10]}"

    # Top category
    top_category = categories[0]["category"] if categories else "—"

    # Category breakdown formatting
    formatted_categories = []
    for c in categories:
        cat_dict = dict(c)
        cat_dict["percentage"] = round((cat_dict["total_amount"] / total_spent * 100), 1) if total_spent > 0 else 0.0
        cat_dict["bar_class"] = f"cat-bar-{cat_dict['category'].lower()}"
        formatted_categories.append(cat_dict)

    # Recent transactions formatting
    recent_expenses = []
    for exp in recent_raw:
        exp_dict = dict(exp)
        try:
            exp_dict["formatted_date"] = datetime.fromisoformat(str(exp_dict.get("date"))[:10]).strftime("%d %b %Y")
        except Exception:
            exp_dict["formatted_date"] = str(exp_dict.get("date"))
        exp_dict["badge_class"] = f"cat-badge-{exp_dict.get('category', 'other').lower()}"
        recent_expenses.append(exp_dict)

    return render_template(
        "profile.html",
        user=user,
        member_since=member_since,
        stats=stats,
        top_category=top_category,
        categories=formatted_categories,
        recent_expenses=recent_expenses,
        selected_period=selected_period,
        start_date=start_date,
        end_date=end_date,
        filter_start_date=start_date,
        filter_end_date=end_date,
        error=error,
        success=success
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


# ------------------------------------------------------------------ #
# SECTION 1: Transaction History Routes (Subagent 1)                 #
# ------------------------------------------------------------------ #
@app.route("/api/expenses", methods=["GET"])
def api_expenses():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    limit = request.args.get("limit", type=int)
    offset = request.args.get("offset", default=0, type=int)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    expenses = get_user_expenses(user_id, limit=limit, offset=offset, start_date=start_date, end_date=end_date)
    return jsonify({
        "expenses": expenses,
        "count": len(expenses),
        "start_date": start_date,
        "end_date": end_date
    })


# ------------------------------------------------------------------ #
# SECTION 2: Summary Stats Routes (Subagent 2)                       #
# ------------------------------------------------------------------ #
@app.route("/api/stats/summary", methods=["GET"])
def api_stats_summary():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    stats = get_user_stats(user_id, start_date=start_date, end_date=end_date)
    avg_spent = round(stats["total_spent"] / stats["total_count"], 2) if stats["total_count"] > 0 else 0.0

    return jsonify({
        "total_count": stats["total_count"],
        "total_spent": stats["total_spent"],
        "average_spent": avg_spent,
        "start_date": start_date,
        "end_date": end_date
    })


# ------------------------------------------------------------------ #
# SECTION 3: Category Breakdown Routes (Subagent 3)                  #
# ------------------------------------------------------------------ #
@app.route("/api/stats/categories", methods=["GET"])
def api_stats_categories():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    categories = get_category_breakdown(user_id, start_date=start_date, end_date=end_date)
    total_spent = sum(c["total_amount"] for c in categories)
    for c in categories:
        c["percentage"] = round((c["total_amount"] / total_spent * 100), 1) if total_spent > 0 else 0.0

    return jsonify({
        "categories": categories,
        "total_spent": total_spent,
        "start_date": start_date,
        "end_date": end_date
    })


if __name__ == "__main__":
    app.run(debug=True, port=5001)
