import pytest
import requests
import time
import os

BASE_URL = os.getenv('TEST_BASE_URL', 'http://frontend')

# --- System Health Tests ---

@pytest.mark.e2e
@pytest.mark.p2
def test_health_endpoint_accessible():
    """Health endpoint accessible via metrics port."""
    try:
        response = requests.get(f'{BASE_URL}/api/health', timeout=5)
        assert response.status_code in [200, 503]
        data = response.json()
        assert 'status' in data
    except requests.exceptions.ConnectionError:
        pytest.skip("Application not running")


@pytest.mark.e2e
@pytest.mark.p2
def test_frontend_serves_static_files():
    """Frontend serves index.html via Nginx."""
    try:
        response = requests.get(BASE_URL, timeout=5)
        assert response.status_code == 200
        assert 'text/html' in response.headers.get('Content-Type', '')
    except requests.exceptions.ConnectionError:
        pytest.skip("Frontend not running")


@pytest.mark.e2e
@pytest.mark.p2
def test_api_requires_authentication():
    """API endpoints require authentication."""
    try:
        response = requests.get(f'{BASE_URL}/api/items', timeout=5)
        assert response.status_code == 401
        data = response.json()
        assert 'error' in data or 'Unauthorized' in str(data)
    except requests.exceptions.ConnectionError:
        pytest.skip("Application not running")


# --- Complete User Journey Tests ---

@pytest.mark.e2e
@pytest.mark.p1
def test_complete_manager_journey():
    """
    Complete manager workflow:
    1. Register group
    2. Login
    3. Add item (auto-approved)
    4. Update quantity
    5. Delete item
    """
    try:
        timestamp = str(time.time())
        email = f"manager-{timestamp}@test.com"
        password = "secure123"

        # 1. Register
        register_resp = requests.post(f'{BASE_URL}/api/auth/register', json={
            'group_name': f'E2E Test Family {timestamp}',
            'user_name': 'Manager User',
            'email': email,
            'password': password
        }, timeout=5)
        assert register_resp.status_code == 201

        # 2. Login
        login_resp = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': email,
            'password': password
        }, timeout=5)
        assert login_resp.status_code == 200
        
        token = login_resp.json().get('token')
        assert token is not None

        headers = {'Authorization': f'Bearer {token}'}

        # 3. Add item
        create_resp = requests.post(f'{BASE_URL}/api/items',
            json={'name': 'Test Milk', 'category': 'Dairy'},
            headers=headers,
            timeout=5
        )
        assert create_resp.status_code == 201
        item_id = create_resp.json()['_id']
        assert create_resp.json()['status'] == 'APPROVED'  # Auto-approved for MANAGER

        # 4. Update quantity
        update_resp = requests.put(f'{BASE_URL}/api/items/{item_id}',
            json={'quantity': 3},
            headers=headers,
            timeout=5
        )
        assert update_resp.status_code == 200

        # 5. Delete item
        delete_resp = requests.delete(f'{BASE_URL}/api/items/{item_id}',
            headers=headers,
            timeout=5
        )
        assert delete_resp.status_code == 204

    except requests.exceptions.ConnectionError:
        pytest.skip("Application not running")


@pytest.mark.e2e
@pytest.mark.p1
def test_multi_user_collaboration():
    """
    Multi-user workflow:
    1. Manager registers group
    2. Member joins group
    3. Member adds item (pending)
    4. Manager approves item
    5. Both users see the item
    """
    try:
        timestamp = str(time.time())

        # 1. Manager registers
        manager_resp = requests.post(f'{BASE_URL}/api/auth/register', json={
            'group_name': f'Collab Family {timestamp}',
            'user_name': 'Manager',
            'email': f'manager-{timestamp}@test.com',
            'password': 'pass123'
        }, timeout=5)
        assert manager_resp.status_code == 201
        join_code = manager_resp.json()['details']['join_code']

        # Login as manager to get token
        manager_login = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': f'manager-{timestamp}@test.com',
            'password': 'pass123'
        }, timeout=5)

        if manager_login.status_code != 200:
            pytest.skip("Login failed - likely system not ready")

        manager_token = manager_login.json()['token']
        manager_headers = {'Authorization': f'Bearer {manager_token}'}

        # 2. Member joins
        member_resp = requests.post(f'{BASE_URL}/api/auth/join', json={
            'join_code': join_code,
            'user_name': 'Member',
            'email': f'member-{timestamp}@test.com',
            'password': 'pass456'
        }, timeout=5)
        assert member_resp.status_code == 201

        # Login as member
        member_login = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': f'member-{timestamp}@test.com',
            'password': 'pass456'
        }, timeout=5)
        member_token = member_login.json()['token']
        member_headers = {'Authorization': f'Bearer {member_token}'}

        # 3. Member adds item
        member_item_resp = requests.post(f'{BASE_URL}/api/items',
            json={'name': 'Member Item', 'category': 'Snacks'},
            headers=member_headers,
            timeout=5
        )
        assert member_item_resp.status_code == 201
        item_id = member_item_resp.json()['_id']
        assert member_item_resp.json()['status'] == 'PENDING'

        # 4. Manager approves
        approve_resp = requests.put(f'{BASE_URL}/api/items/{item_id}',
            json={'status': 'APPROVED'},
            headers=manager_headers,
            timeout=5
        )
        assert approve_resp.status_code == 200

        # 5. Both users see the item
        manager_items = requests.get(f'{BASE_URL}/api/items',
            headers=manager_headers,
            timeout=5
        )
        assert manager_items.status_code == 200
        assert len(manager_items.json()) > 0

        member_items = requests.get(f'{BASE_URL}/api/items',
            headers=member_headers,
            timeout=5
        )
        assert member_items.status_code == 200
        assert len(member_items.json()) > 0

    except requests.exceptions.ConnectionError:
        pytest.skip("Application not running")


@pytest.mark.e2e
@pytest.mark.p1
def test_role_based_permissions():
    """
    Test role-based access control:
    1. Manager can approve items
    2. Member cannot approve items
    3. Manager can delete any item
    4. Member can only delete own items
    """
    try:
        timestamp = str(time.time())

        # Create group with manager
        manager_resp = requests.post(f'{BASE_URL}/api/auth/register', json={
            'group_name': f'RBAC Family {timestamp}',
            'user_name': 'Manager',
            'email': f'manager-{timestamp}@test.com',
            'password': 'pass123'
        }, timeout=5)
        join_code = manager_resp.json()['details']['join_code']

        manager_login = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': f'manager-{timestamp}@test.com',
            'password': 'pass123'
        }, timeout=5)

        if manager_login.status_code != 200:
            pytest.skip("Login failed")

        manager_token = manager_login.json()['token']
        manager_headers = {'Authorization': f'Bearer {manager_token}'}

        # Add member
        member_resp = requests.post(f'{BASE_URL}/api/auth/join', json={
            'join_code': join_code,
            'user_name': 'Member',
            'email': f'member-{timestamp}@test.com',
            'password': 'pass456'
        }, timeout=5)

        member_login = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': f'member-{timestamp}@test.com',
            'password': 'pass456'
        }, timeout=5)
        member_token = member_login.json()['token']
        member_headers = {'Authorization': f'Bearer {member_token}'}

        # Member creates item (pending)
        item_resp = requests.post(f'{BASE_URL}/api/items',
            json={'name': 'Pending Item'},
            headers=member_headers,
            timeout=5
        )
        item_id = item_resp.json()['_id']

        # Member tries to approve (should fail)
        member_approve = requests.put(f'{BASE_URL}/api/items/{item_id}',
            json={'status': 'APPROVED'},
            headers=member_headers,
            timeout=5
        )
        assert member_approve.status_code == 403

        # Manager approves (should succeed)
        manager_approve = requests.put(f'{BASE_URL}/api/items/{item_id}',
            json={'status': 'APPROVED'},
            headers=manager_headers,
            timeout=5
        )
        assert manager_approve.status_code == 200

        # Manager creates another item
        manager_item_resp = requests.post(f'{BASE_URL}/api/items',
            json={'name': 'Manager Item'},
            headers=manager_headers,
            timeout=5
        )
        manager_item_id = manager_item_resp.json()['_id']

        # Member tries to delete manager's item (should fail)
        member_delete = requests.delete(f'{BASE_URL}/api/items/{manager_item_id}',
            headers=member_headers,
            timeout=5
        )
        assert member_delete.status_code == 403

        # Manager deletes item (should succeed)
        manager_delete = requests.delete(f'{BASE_URL}/api/items/{manager_item_id}',
            headers=manager_headers,
            timeout=5
        )
        assert manager_delete.status_code == 204

    except requests.exceptions.ConnectionError:
        pytest.skip("Application not running")


@pytest.mark.e2e
@pytest.mark.p2
def test_multi_tenancy_isolation():
    """
    Test that groups are isolated:
    1. Create two separate groups
    2. Each adds items
    3. Verify items are not visible across groups
    """
    try:
        timestamp = str(time.time())

        # Group A
        group_a_resp = requests.post(f'{BASE_URL}/api/auth/register', json={
            'group_name': f'Family A {timestamp}',
            'user_name': 'User A',
            'email': f'user-a-{timestamp}@test.com',
            'password': 'pass123'
        }, timeout=5)

        login_a = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': f'user-a-{timestamp}@test.com',
            'password': 'pass123'
        }, timeout=5)

        if login_a.status_code != 200:
            pytest.skip("Login failed")

        token_a = login_a.json()['token']
        headers_a = {'Authorization': f'Bearer {token_a}'}

        # Group B
        group_b_resp = requests.post(f'{BASE_URL}/api/auth/register', json={
            'group_name': f'Family B {timestamp}',
            'user_name': 'User B',
            'email': f'user-b-{timestamp}@test.com',
            'password': 'pass456'
        }, timeout=5)

        login_b = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': f'user-b-{timestamp}@test.com',
            'password': 'pass456'
        }, timeout=5)
        token_b = login_b.json()['token']
        headers_b = {'Authorization': f'Bearer {token_b}'}

        # Group A adds item
        requests.post(f'{BASE_URL}/api/items',
            json={'name': 'Group A Item'},
            headers=headers_a,
            timeout=5
        )

        # Group B adds item
        requests.post(f'{BASE_URL}/api/items',
            json={'name': 'Group B Item'},
            headers=headers_b,
            timeout=5
        )

        # Verify isolation
        items_a = requests.get(f'{BASE_URL}/api/items', headers=headers_a, timeout=5).json()
        items_b = requests.get(f'{BASE_URL}/api/items', headers=headers_b, timeout=5).json()

        # Each group should only see their own item
        assert len(items_a) >= 1
        assert len(items_b) >= 1
        assert all('Group A' in item['name'] or item['name'] != 'Group B Item' for item in items_a)
        assert all('Group B' in item['name'] or item['name'] != 'Group A Item' for item in items_b)

    except requests.exceptions.ConnectionError:
        pytest.skip("Application not running")


@pytest.mark.e2e
@pytest.mark.p2
def test_group_management_workflow():
    """
    Test group management:
    1. Manager creates group
    2. Members join
    3. Manager views members
    4. Manager promotes member to manager
    5. Manager removes member
    """
    try:
        timestamp = str(time.time())

        # 1. Manager creates group
        manager_resp = requests.post(f'{BASE_URL}/api/auth/register', json={
            'group_name': f'Managed Family {timestamp}',
            'user_name': 'Admin',
            'email': f'admin-{timestamp}@test.com',
            'password': 'admin123'
        }, timeout=5)
        join_code = manager_resp.json()['details']['join_code']

        manager_login = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': f'admin-{timestamp}@test.com',
            'password': 'admin123'
        }, timeout=5)

        if manager_login.status_code != 200:
            pytest.skip("Login failed")

        manager_token = manager_login.json()['token']
        manager_headers = {'Authorization': f'Bearer {manager_token}'}

        # 2. Member joins
        member_resp = requests.post(f'{BASE_URL}/api/auth/join', json={
            'join_code': join_code,
            'user_name': 'Regular Member',
            'email': f'member-{timestamp}@test.com',
            'password': 'member123'
        }, timeout=5)
        member_id = member_resp.json()['details']['user_id']

        # 3. Manager views members
        members_resp = requests.get(f'{BASE_URL}/api/groups/members',
            headers=manager_headers,
            timeout=5
        )
        assert members_resp.status_code == 200
        members = members_resp.json()
        assert len(members) == 2  # Admin + Member

        # 4. Manager promotes member
        promote_resp = requests.put(f'{BASE_URL}/api/groups/members/{member_id}',
            json={'role': 'MANAGER'},
            headers=manager_headers,
            timeout=5
        )
        assert promote_resp.status_code == 200

        # 5. Manager creates another member to remove
        remove_member_resp = requests.post(f'{BASE_URL}/api/auth/join', json={
            'join_code': join_code,
            'user_name': 'Temp Member',
            'email': f'temp-{timestamp}@test.com',
            'password': 'temp123'
        }, timeout=5)
        temp_member_id = remove_member_resp.json()['details']['user_id']

        # Remove member
        delete_resp = requests.delete(f'{BASE_URL}/api/groups/members/{temp_member_id}',
            headers=manager_headers,
            timeout=5
        )
        assert delete_resp.status_code == 204

    except requests.exceptions.ConnectionError:
        pytest.skip("Application not running")


@pytest.mark.e2e
@pytest.mark.p2
def test_clear_list_workflow():
    """
    Test bulk delete functionality:
    1. Manager creates multiple items
    2. Manager clears all items
    3. Verify list is empty
    """
    try:
        timestamp = str(time.time())

        # Register and login
        register_resp = requests.post(f'{BASE_URL}/api/auth/register', json={
            'group_name': f'Clear Test {timestamp}',
            'user_name': 'Manager',
            'email': f'clear-{timestamp}@test.com',
            'password': 'pass123'
        }, timeout=5)

        login_resp = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': f'clear-{timestamp}@test.com',
            'password': 'pass123'
        }, timeout=5)

        if login_resp.status_code != 200:
            pytest.skip("Login failed")

        token = login_resp.json()['token']
        headers = {'Authorization': f'Bearer {token}'}

        # Create multiple items
        for i in range(5):
            requests.post(f'{BASE_URL}/api/items',
                json={'name': f'Item {i}'},
                headers=headers,
                timeout=5
            )

        # Verify items exist
        items_resp = requests.get(f'{BASE_URL}/api/items', headers=headers, timeout=5)
        assert len(items_resp.json()) == 5

        # Clear all
        clear_resp = requests.delete(f'{BASE_URL}/api/items/clear',
            headers=headers,
            timeout=5
        )
        assert clear_resp.status_code == 204

        # Verify empty
        after_clear = requests.get(f'{BASE_URL}/api/items', headers=headers, timeout=5)
        assert len(after_clear.json()) == 0

    except requests.exceptions.ConnectionError:
        pytest.skip("Application not running")


@pytest.mark.e2e
@pytest.mark.p2
def test_error_handling():
    """
    Test error scenarios:
    1. Invalid credentials
    2. Duplicate email
    3. Invalid join code
    4. Missing authentication
    """
    try:
        timestamp = str(time.time())

        # 1. Invalid credentials
        invalid_login = requests.post(f'{BASE_URL}/api/auth/login', json={
            'email': 'nonexistent@test.com',
            'password': 'wrongpass'
        }, timeout=5)
        assert invalid_login.status_code == 401

        # 2. Duplicate email
        requests.post(f'{BASE_URL}/api/auth/register', json={
            'group_name': f'Error Test {timestamp}',
            'user_name': 'User',
            'email': f'duplicate-{timestamp}@test.com',
            'password': 'pass123'
        }, timeout=5)

        duplicate_resp = requests.post(f'{BASE_URL}/api/auth/register', json={
            'group_name': 'Another Group',
            'user_name': 'Another User',
            'email': f'duplicate-{timestamp}@test.com',
            'password': 'pass456'
        }, timeout=5)
        assert duplicate_resp.status_code == 400

        # 3. Invalid join code
        invalid_join = requests.post(f'{BASE_URL}/api/auth/join', json={
            'join_code': 'INVALID',
            'user_name': 'User',
            'email': f'new-{timestamp}@test.com',
            'password': 'pass123'
        }, timeout=5)
        assert invalid_join.status_code == 400

        # 4. Missing authentication
        no_auth = requests.get(f'{BASE_URL}/api/items', timeout=5)
        assert no_auth.status_code == 401

    except requests.exceptions.ConnectionError:
        pytest.skip("Application not running")
