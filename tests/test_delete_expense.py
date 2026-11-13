import os
import sys
import pytest

# Ensure expense-tracker directory is on python path
app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "expense-tracker")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from app import app
from database.db import (
    create_expense,
    get_user_expense_by_id,
    delete_expense,
    get_user_stats,
    get_category_breakdown,
    get_user_by_email
)
from datetime import date


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client


@pytest.fixture
def test_users():
    # User 1 is Demo User; User 4 is test user
    u1 = get_user_by_email("demo@spendly.com")
    u1_id = u1["id"] if u1 else 1

    # Try to find another user or use id 4
    u2 = get_user_by_email("test@example.com")
    u2_id = u2["id"] if u2 else 4
    return {"owner": u2_id, "other": u1_id}


def test_unauthenticated_delete_web_redirects(client):
    """Unauthenticated POST to /expenses/<id>/delete must redirect to /login."""
    res = client.post("/expenses/1/delete", follow_redirects=False)
    assert res.status_code == 302
    assert "/login" in res.headers.get("Location", "")


def test_unauthenticated_delete_api_unauthorized(client):
    """Unauthenticated DELETE to /api/expenses/<id> must return 401."""
    res = client.delete("/api/expenses/1")
    assert res.status_code == 401
    json_data = res.get_json()
    assert json_data["error"] == "Authentication required"


def test_get_delete_route_method_not_allowed(client, test_users):
    """Bare GET requests to /expenses/<id>/delete must be rejected with 405 Method Not Allowed."""
    with client.session_transaction() as sess:
        sess["user_id"] = test_users["owner"]

    res = client.get("/expenses/1/delete")
    assert res.status_code == 405


def test_delete_nonexistent_expense_404(client, test_users):
    """Deleting a non-existent expense ID must return 404 for both web and API."""
    with client.session_transaction() as sess:
        sess["user_id"] = test_users["owner"]

    # Web route
    res_web = client.post("/expenses/9999999/delete")
    assert res_web.status_code == 404

    # API route
    res_api = client.delete("/api/expenses/9999999")
    assert res_api.status_code == 404
    assert res_api.get_json()["error"] == "Expense not found"


def test_delete_expense_idor_protection(client, test_users):
    """A user must NEVER be able to delete another user's expense (IDOR protection)."""
    # Create an expense owned by user 'other'
    today_str = date.today().isoformat()
    other_exp_id = create_expense(
        user_id=test_users["other"],
        amount=250.0,
        category="Utilities",
        date=today_str,
        description="Electricity bill for Other User"
    )
    assert other_exp_id > 0

    # Log in as 'owner' (different user)
    with client.session_transaction() as sess:
        sess["user_id"] = test_users["owner"]

    # Attempt to delete via web route
    res_web = client.post(f"/expenses/{other_exp_id}/delete")
    assert res_web.status_code == 404

    # Attempt to delete via API route
    res_api = client.delete(f"/api/expenses/{other_exp_id}")
    assert res_api.status_code == 404
    assert res_api.get_json()["error"] == "Expense not found"

    # Verify the record still exists in the database
    record = get_user_expense_by_id(other_exp_id, test_users["other"])
    assert record is not None
    assert record["id"] == other_exp_id

    # Clean up test expense using legitimate owner
    assert delete_expense(other_exp_id, test_users["other"]) is True


def test_successful_web_deletion(client, test_users):
    """Legitimate owner can delete expense via POST /expenses/<id>/delete and get redirected."""
    today_str = date.today().isoformat()
    exp_id = create_expense(
        user_id=test_users["owner"],
        amount=199.99,
        category="Entertainment",
        date=today_str,
        description="Movie ticket"
    )
    assert exp_id > 0

    with client.session_transaction() as sess:
        sess["user_id"] = test_users["owner"]

    res = client.post(f"/expenses/{exp_id}/delete", follow_redirects=True)
    assert res.status_code == 200
    assert b"Expense deleted successfully." in res.data or b"Recent Transactions" in res.data

    # Verify deleted from DB
    assert get_user_expense_by_id(exp_id, test_users["owner"]) is None


def test_successful_api_deletion(client, test_users):
    """Legitimate owner can delete expense via DELETE /api/expenses/<id> and receive 200 JSON."""
    today_str = date.today().isoformat()
    exp_id = create_expense(
        user_id=test_users["owner"],
        amount=350.0,
        category="Health",
        date=today_str,
        description="Vitamins"
    )
    assert exp_id > 0

    with client.session_transaction() as sess:
        sess["user_id"] = test_users["owner"]

    res = client.delete(f"/api/expenses/{exp_id}")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["message"] == "Expense deleted successfully"
    assert json_data["id"] == exp_id

    # Verify deleted from DB
    assert get_user_expense_by_id(exp_id, test_users["owner"]) is None


def test_stats_recalculation_after_deletion(client, test_users):
    """Deleting an expense must immediately reduce total_spent and total_count in stats."""
    today_str = date.today().isoformat()
    user_id = test_users["owner"]

    # Initial stats
    initial_stats = get_user_stats(user_id)
    initial_total = initial_stats["total_spent"]
    initial_count = initial_stats["total_count"]

    # Add expense
    added_amount = 750.50
    exp_id = create_expense(
        user_id=user_id,
        amount=added_amount,
        category="Food",
        date=today_str,
        description="Dinner with friends"
    )

    stats_after_add = get_user_stats(user_id)
    assert round(stats_after_add["total_spent"], 2) == round(initial_total + added_amount, 2)
    assert stats_after_add["total_count"] == initial_count + 1

    # Delete expense via db function
    deleted = delete_expense(exp_id, user_id)
    assert deleted is True

    # Stats after delete must revert exactly
    stats_after_delete = get_user_stats(user_id)
    assert round(stats_after_delete["total_spent"], 2) == round(initial_total, 2)
    assert stats_after_delete["total_count"] == initial_count


def test_direct_db_delete_expense_idempotency_and_isolation(test_users):
    """Direct database unit test for delete_expense function in database/db.py."""
    today_str = date.today().isoformat()
    user_id = test_users["owner"]
    other_user = test_users["other"]

    exp_id = create_expense(
        user_id=user_id,
        amount=120.0,
        category="Travel",
        date=today_str,
        description="Metro recharge"
    )

    # Unauthorized delete attempt
    assert delete_expense(exp_id, other_user) is False

    # Authorized delete
    assert delete_expense(exp_id, user_id) is True

    # Secondary delete attempt (already deleted) returns False
    assert delete_expense(exp_id, user_id) is False
