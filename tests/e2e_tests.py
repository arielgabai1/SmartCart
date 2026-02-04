"""
E2E Tests - Browser-based tests using Playwright against docker-compose stack.
Tests critical user journeys through the actual UI.
"""
import pytest
import uuid
import os
from playwright.sync_api import sync_playwright, expect

BASE_URL = os.getenv('TEST_BASE_URL', 'http://localhost:80')


def unique_email():
    return f"e2e-{uuid.uuid4().hex[:8]}@test.com"


def unique_name():
    return f"TestUser-{uuid.uuid4().hex[:6]}"


def unique_group():
    return f"Group-{uuid.uuid4().hex[:6]}"


@pytest.fixture
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def page(browser):
    p = browser.new_page()
    yield p
    p.close()


def register_new_group(page, group_name=None, user_name=None, email=None, password="pass123"):
    """Register a new group via UI. Returns (email, password, join_code)."""
    group_name = group_name or unique_group()
    user_name = user_name or unique_name()
    email = email or unique_email()

    page.goto(f"{BASE_URL}/register.html")
    page.wait_for_selector("#register-form")

    # "New Group" tab is active by default
    page.fill("#group_name", group_name)
    page.fill("#user_name", user_name)
    page.fill("#email", email)
    page.fill("#password", password)

    # Capture the alert that shows the join code
    join_code = None

    def handle_dialog(dialog):
        nonlocal join_code
        text = dialog.message
        if "invite code" in text.lower():
            join_code = text.split(":")[-1].strip()
        dialog.accept()

    page.on("dialog", handle_dialog)
    page.click('#register-form button[type="submit"]')

    # Wait for redirect to index.html
    page.wait_for_url("**/index.html", timeout=10000)

    return email, password, join_code, user_name


def login_user(page, email, password):
    """Login via UI."""
    page.goto(f"{BASE_URL}/login.html")
    page.wait_for_selector("#login-form")
    page.fill("#email", email)
    page.fill("#password", password)
    page.click('#login-form button[type="submit"]')
    page.wait_for_url("**/index.html", timeout=10000)


def register_member(page, join_code, user_name=None, email=None, password="pass123"):
    """Register as a member joining an existing group via UI."""
    user_name = user_name or unique_name()
    email = email or unique_email()

    page.goto(f"{BASE_URL}/register.html")
    page.wait_for_selector("#register-form")

    # Switch to "Join Existing" tab
    page.click("#btn-join")

    page.fill("#join_code", join_code)
    page.fill("#user_name", user_name)
    page.fill("#email", email)
    page.fill("#password", password)

    def handle_dialog(dialog):
        dialog.accept()

    page.on("dialog", handle_dialog)
    page.click('#register-form button[type="submit"]')
    page.wait_for_url("**/index.html", timeout=10000)

    return email, password


# --- Tests ---


@pytest.mark.e2e
def test_register_new_group(page):
    """Register a new group, verify join code is returned and dashboard loads."""
    _, _, join_code, user_name = register_new_group(page)

    assert join_code is not None, "Join code was not shown in alert"
    assert len(join_code) > 0, "Join code is empty"

    # Verify dashboard loaded with user info
    expect(page.locator("#user-name-display")).to_have_text(user_name, timeout=10000)
    expect(page.locator("#user-role-display")).to_have_text("MANAGER")


@pytest.mark.e2e
def test_login_and_view_dashboard(page):
    """Login with registered user, verify dashboard loads with user name and empty list."""
    creds = register_new_group(page)

    # Logout by clearing storage and navigating to login
    page.evaluate("localStorage.clear()")
    login_user(page, creds[0], creds[1])

    # Verify dashboard
    expect(page.locator("#user-name-display")).to_have_text(creds[3], timeout=10000)
    expect(page.locator("#user-role-display")).to_have_text("MANAGER")

    # Empty list shows empty state
    expect(page.locator(".empty-state")).to_be_visible(timeout=10000)


@pytest.mark.e2e
def test_manager_add_item(page):
    """Login as manager, add item via form, verify it appears as APPROVED."""
    register_new_group(page)

    # Wait for dashboard to fully load
    page.wait_for_selector("#item-form", timeout=10000)

    # Add an item
    page.fill("#name", "Milk")
    page.select_option("#category", "DAIRY")
    page.click('#submit-btn')

    # Verify item appears in the list
    item_card = page.locator(".item-card").first
    expect(item_card).to_be_visible(timeout=10000)
    expect(item_card.locator(".item-title")).to_have_text("Milk")
    expect(item_card.locator(".status-pill")).to_have_text("APPROVED")


@pytest.mark.e2e
def test_member_submit_and_manager_approves(browser):
    """Register member via join, add item (PENDING), login as manager, approve it."""
    # Step 1: Manager registers group
    manager_page = browser.new_page()
    mgr_email, mgr_pass, join_code, _ = register_new_group(manager_page)
    manager_page.close()

    # Step 2: Member joins and adds item
    member_page = browser.new_page()
    register_member(member_page, join_code)

    member_page.wait_for_selector("#item-form", timeout=10000)
    member_page.fill("#name", "Bread")
    member_page.click("#submit-btn")

    # Member sees item in "My Submissions" as PENDING
    my_items = member_page.locator("#my-items-container .item-card").first
    expect(my_items).to_be_visible(timeout=10000)
    expect(my_items.locator(".status-pill")).to_contain_text("PENDING")
    member_page.close()

    # Step 3: Manager logs in and approves
    mgr_page = browser.new_page()
    login_user(mgr_page, mgr_email, mgr_pass)
    mgr_page.wait_for_selector("#items-container", timeout=10000)

    # Wait for pending section to appear
    pending_section = mgr_page.locator("#pending-section")
    expect(pending_section).to_be_visible(timeout=10000)

    # Click Approve on the pending item
    approve_btn = mgr_page.locator("#pending-container .item-card button", has_text="Approve").first
    expect(approve_btn).to_be_visible(timeout=5000)
    approve_btn.click()

    # Verify item moved to main list as APPROVED
    approved_item = mgr_page.locator("#items-container .item-card .status-pill", has_text="APPROVED")
    expect(approved_item).to_be_visible(timeout=10000)
    mgr_page.close()


@pytest.mark.e2e
def test_delete_item(page):
    """Login as manager, add item, delete it, verify it's gone."""
    register_new_group(page)
    page.wait_for_selector("#item-form", timeout=10000)

    # Add item
    page.fill("#name", "Juice")
    page.click("#submit-btn")

    # Wait for item to appear
    item_card = page.locator(".item-card").first
    expect(item_card).to_be_visible(timeout=10000)

    # Click delete and confirm dialog
    page.on("dialog", lambda d: d.accept())
    delete_btn = item_card.locator("button", has_text="Delete")
    expect(delete_btn).to_be_visible(timeout=5000)
    delete_btn.click()

    # Verify item is gone and empty state shows
    expect(page.locator(".empty-state")).to_be_visible(timeout=10000)


@pytest.mark.e2e
def test_join_existing_group(browser):
    """Register as member via join code, verify MEMBER role on dashboard."""
    # Manager creates group
    mgr_page = browser.new_page()
    _, _, join_code, _ = register_new_group(mgr_page)
    mgr_page.close()

    # Member joins
    mem_page = browser.new_page()
    register_member(mem_page, join_code, user_name="JoinedMember")

    expect(mem_page.locator("#user-name-display")).to_have_text("JoinedMember", timeout=10000)
    expect(mem_page.locator("#user-role-display")).to_have_text("MEMBER")

    # Member sees "Submit Request" instead of "Add Item"
    expect(mem_page.locator("#submit-btn")).to_have_text("Submit Request")
    mem_page.close()


@pytest.mark.e2e
def test_manager_rejects_item(browser):
    """Member submits item, manager rejects it, member sees REJECTED status."""
    # Manager registers
    mgr_page = browser.new_page()
    mgr_email, mgr_pass, join_code, _ = register_new_group(mgr_page)
    mgr_page.close()

    # Member joins and submits item
    mem_page = browser.new_page()
    register_member(mem_page, join_code)
    mem_page.wait_for_selector("#item-form", timeout=10000)
    mem_page.fill("#name", "Candy")
    mem_page.click("#submit-btn")
    expect(mem_page.locator("#my-items-container .item-card").first).to_be_visible(timeout=10000)
    mem_page.close()

    # Manager rejects
    mgr_page = browser.new_page()
    login_user(mgr_page, mgr_email, mgr_pass)
    mgr_page.wait_for_selector("#items-container", timeout=10000)

    reject_btn = mgr_page.locator("#pending-container .item-card button", has_text="Reject").first
    expect(reject_btn).to_be_visible(timeout=10000)
    reject_btn.click()

    # Verify item shows REJECTED in main list
    rejected_pill = mgr_page.locator("#items-container .item-card .status-pill", has_text="REJECTED")
    expect(rejected_pill).to_be_visible(timeout=10000)
    mgr_page.close()


@pytest.mark.e2e
def test_clear_all_items(page):
    """Manager adds multiple items, clears all, verifies empty state."""
    register_new_group(page)
    page.wait_for_selector("#item-form", timeout=10000)
    page.on("dialog", lambda d: d.accept())

    # Add 3 items
    for item in ["Eggs", "Bread", "Cheese"]:
        page.fill("#name", item)
        page.click("#submit-btn")
        page.wait_for_timeout(500)

    expect(page.locator(".item-card").first).to_be_visible(timeout=10000)

    # Clear all
    page.click("#clear-all-btn")

    expect(page.locator(".empty-state")).to_be_visible(timeout=10000)


@pytest.mark.e2e
def test_sidebar_shows_join_code(page):
    """Open sidebar, verify join code is displayed."""
    _, _, join_code, _ = register_new_group(page)
    page.wait_for_selector("#menu-toggle", timeout=10000)

    # Open sidebar
    page.click("#menu-toggle")

    code_display = page.locator("#sidebar-join-code")
    expect(code_display).to_be_visible(timeout=5000)
    expect(code_display).to_have_text(join_code)


@pytest.mark.e2e
def test_login_invalid_credentials(page):
    """Login with wrong password, verify error alert and no redirect."""
    register_new_group(page)
    page.evaluate("localStorage.clear()")

    page.goto(f"{BASE_URL}/login.html")
    page.wait_for_selector("#login-form")
    page.fill("#email", "wrong@test.com")
    page.fill("#password", "wrongpass")

    alert_msg = None

    def handle_dialog(dialog):
        nonlocal alert_msg
        alert_msg = dialog.message
        dialog.accept()

    page.on("dialog", handle_dialog)
    page.click('#login-form button[type="submit"]')
    page.wait_for_timeout(2000)

    assert alert_msg is not None, "No error alert shown"
    # Should still be on login page
    assert "login.html" in page.url


@pytest.mark.e2e
def test_quantity_adjustment(page):
    """Add item, use +/- buttons to change quantity, verify it updates."""
    register_new_group(page)
    page.wait_for_selector("#item-form", timeout=10000)

    page.fill("#name", "Rice")
    page.click("#submit-btn")

    item_card = page.locator(".item-card").first
    expect(item_card).to_be_visible(timeout=10000)

    # Default quantity is 1
    expect(item_card.locator(".quantity-value")).to_have_text("1")

    # Click + button
    item_card.locator(".quantity-btn", has_text="+").click()
    expect(item_card.locator(".quantity-value")).to_have_text("2", timeout=5000)

    # Click + again
    item_card.locator(".quantity-btn", has_text="+").click()
    expect(item_card.locator(".quantity-value")).to_have_text("3", timeout=5000)

    # Click - button
    item_card.locator(".quantity-btn", has_text="-").click()
    expect(item_card.locator(".quantity-value")).to_have_text("2", timeout=5000)


@pytest.mark.e2e
def test_stats_bar_updates(page):
    """Add items, verify approved count and total update in stats bar."""
    register_new_group(page)
    page.wait_for_selector("#item-form", timeout=10000)

    # Initially zero
    expect(page.locator("#approved-count")).to_have_text("0")

    # Add first item
    page.fill("#name", "Milk")
    page.click("#submit-btn")
    expect(page.locator("#approved-count")).to_have_text("1", timeout=10000)

    # Add second item
    page.fill("#name", "Eggs")
    page.click("#submit-btn")
    expect(page.locator("#approved-count")).to_have_text("2", timeout=10000)


@pytest.mark.e2e
def test_member_sees_approved_items(browser):
    """After manager approves member's item, member sees it in main list."""
    # Manager registers
    mgr_page = browser.new_page()
    mgr_email, mgr_pass, join_code, _ = register_new_group(mgr_page)
    mgr_page.close()

    # Member joins and submits
    mem_page = browser.new_page()
    mem_email, mem_pass = register_member(mem_page, join_code)
    mem_page.wait_for_selector("#item-form", timeout=10000)
    mem_page.fill("#name", "Pasta")
    mem_page.click("#submit-btn")
    expect(mem_page.locator("#my-items-container .item-card").first).to_be_visible(timeout=10000)
    mem_page.close()

    # Manager approves
    mgr_page = browser.new_page()
    login_user(mgr_page, mgr_email, mgr_pass)
    approve_btn = mgr_page.locator("#pending-container .item-card button", has_text="Approve").first
    expect(approve_btn).to_be_visible(timeout=10000)
    approve_btn.click()
    expect(mgr_page.locator("#items-container .item-card .status-pill", has_text="APPROVED")).to_be_visible(timeout=10000)
    mgr_page.close()

    # Member logs back in, sees item in main list
    mem_page = browser.new_page()
    login_user(mem_page, mem_email, mem_pass)
    mem_page.wait_for_selector("#items-container", timeout=10000)

    item = mem_page.locator("#items-container .item-card").first
    expect(item).to_be_visible(timeout=10000)
    expect(item.locator(".item-title")).to_have_text("Pasta")
    expect(item.locator(".status-pill")).to_have_text("APPROVED")
    mem_page.close()


@pytest.mark.e2e
def test_register_empty_fields(page):
    """Submit register form with empty fields, verify no redirect."""
    page.goto(f"{BASE_URL}/register.html")
    page.wait_for_selector("#register-form")

    # Submit without filling anything - HTML5 validation should block
    page.click('#register-form button[type="submit"]')
    page.wait_for_timeout(1000)

    # Should still be on register page
    assert "register.html" in page.url
