"""
Integration tests for MongoDB persistence across container restarts.

Tests verify that data persists when:
1. MongoDB container is stopped and restarted
2. Entire Docker Compose stack is stopped and restarted
3. Volume can be inspected and contains MongoDB data files

Prerequisites:
- Docker and Docker Compose must be running
- Application must be running via docker-compose up
"""

import time
import pytest
import requests
import docker
from docker.errors import NotFound


BASE_URL = 'http://localhost:5001'
MONGODB_CONTAINER_NAME = 'mongodb'
MONGODB_RESTART_WAIT = 10  # seconds to wait for MongoDB to be ready
STACK_RESTART_WAIT = 15  # seconds to wait for full stack to be ready


@pytest.fixture
def docker_client():
    """Provide Docker client for container management."""
    return docker.from_env()


@pytest.fixture
def cleanup_test_items():
    """Clean up test items after each test."""
    yield
    # Cleanup runs after test
    try:
        response = requests.get(f'{BASE_URL}/api/items', timeout=5)
        if response.status_code == 200:
            items = response.json()
            for item in items:
                if item.get('name', '').startswith('PersistenceTest'):
                    requests.delete(f"{BASE_URL}/api/items/{item['_id']}", timeout=5)
    except Exception:
        pass  # Best effort cleanup


def create_test_item(name, user_role='MANAGER'):
    """Helper to create a test item via API."""
    response = requests.post(
        f'{BASE_URL}/api/items',
        json={'name': name, 'user_role': user_role},
        timeout=10
    )
    assert response.status_code == 201, f"Failed to create item: {response.text}"
    return response.json()


def wait_for_backend_ready(max_attempts=30, delay=1):
    """Wait for backend to be ready by polling health endpoint."""
    for attempt in range(max_attempts):
        try:
            response = requests.get(f'{BASE_URL}/health', timeout=2)
            if response.status_code == 200:
                health = response.json()
                if health.get('db') == 'connected':
                    return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(delay)
    return False


def test_data_persists_after_mongodb_container_restart(docker_client, cleanup_test_items):
    """
    Test that data persists when MongoDB container is stopped and restarted.
    Verifies AC2: Data persists when MongoDB container is stopped and restarted.
    """
    # 1. Create test item
    test_item_name = 'PersistenceTest_MongoRestart'
    created_item = create_test_item(test_item_name)
    item_id = created_item['_id']

    # 2. Stop MongoDB container
    try:
        mongo_container = docker_client.containers.get(MONGODB_CONTAINER_NAME)
    except NotFound:
        pytest.skip(f"MongoDB container '{MONGODB_CONTAINER_NAME}' not found. Is docker-compose running?")

    mongo_container.stop()
    time.sleep(2)

    # 3. Start MongoDB container
    mongo_container.start()

    # 4. Wait for backend to reconnect to MongoDB
    assert wait_for_backend_ready(), "Backend did not reconnect to MongoDB after restart"

    # 5. Verify item still exists
    response = requests.get(f'{BASE_URL}/api/items', timeout=10)
    assert response.status_code == 200
    items = response.json()

    item_ids = [item['_id'] for item in items]
    assert item_id in item_ids, f"Item {item_id} not found after MongoDB restart"

    persisted_item = next((item for item in items if item['_id'] == item_id), None)
    assert persisted_item is not None
    assert persisted_item['name'] == test_item_name


def test_data_persists_after_full_stack_restart(docker_client, cleanup_test_items):
    """
    Test that data persists when entire Docker Compose stack is restarted.
    Verifies AC3: Data persists when entire Docker Compose stack is stopped and restarted.
    """
    # 1. Create multiple test items
    test_items = [
        create_test_item('PersistenceTest_StackRestart_1'),
        create_test_item('PersistenceTest_StackRestart_2'),
        create_test_item('PersistenceTest_StackRestart_3')
    ]
    item_ids = [item['_id'] for item in test_items]

    # 2. Stop all containers (simulating docker-compose down)
    containers_to_restart = []
    for container_name in [MONGODB_CONTAINER_NAME, 'SmartCart', 'nginx']:
        try:
            container = docker_client.containers.get(container_name)
            containers_to_restart.append(container)
            container.stop()
        except NotFound:
            pass  # Container might not exist with this exact name

    time.sleep(3)

    # 3. Start all containers (simulating docker-compose up)
    for container in containers_to_restart:
        container.start()

    # 4. Wait for backend to be fully ready
    assert wait_for_backend_ready(max_attempts=45, delay=1), "Backend not ready after full stack restart"

    # 5. Verify all items still exist
    response = requests.get(f'{BASE_URL}/api/items', timeout=10)
    assert response.status_code == 200
    items = response.json()

    retrieved_ids = [item['_id'] for item in items]
    for item_id in item_ids:
        assert item_id in retrieved_ids, f"Item {item_id} not found after full stack restart"


def test_volume_contains_mongodb_data_files(docker_client):
    """
    Test that the Docker volume contains actual MongoDB data files.
    Verifies AC6 (partial): Volume inspection confirms MongoDB is writing to persistent storage.
    """
    # Get the MongoDB container
    try:
        mongo_container = docker_client.containers.get(MONGODB_CONTAINER_NAME)
    except NotFound:
        pytest.skip(f"MongoDB container '{MONGODB_CONTAINER_NAME}' not found")

    # Inspect the container's mounts
    mounts = mongo_container.attrs.get('Mounts', [])

    # Find the /data/db mount
    db_mount = next((m for m in mounts if m.get('Destination') == '/data/db'), None)
    assert db_mount is not None, "No mount found for /data/db"
    assert db_mount.get('Type') == 'volume', "Mount is not a volume type"

    volume_name = db_mount.get('Name')
    assert volume_name is not None, "Volume has no name"

    # Verify volume exists in Docker
    try:
        volume = docker_client.volumes.get(volume_name)
        assert volume is not None
    except NotFound:
        pytest.fail(f"Volume '{volume_name}' not found in Docker")

    # Execute command inside container to verify MongoDB data files exist
    exit_code, output = mongo_container.exec_run('ls -la /data/db')
    assert exit_code == 0, "Failed to list /data/db directory"

    output_str = output.decode('utf-8')
    # MongoDB creates WiredTiger files and collection files
    assert 'WiredTiger' in output_str or 'collection' in output_str, \
        "MongoDB data files not found in /data/db"


def test_multiple_items_persist_correctly(docker_client, cleanup_test_items):
    """
    Test that multiple items persist with correct data across restarts.
    Verifies data integrity is maintained during persistence.
    """
    # 1. Create items with different attributes
    test_items = [
        create_test_item('PersistenceTest_Multi_Milk', 'MANAGER'),
        create_test_item('PersistenceTest_Multi_Bread', 'MEMBER'),
        create_test_item('PersistenceTest_Multi_Eggs', 'MANAGER'),
    ]

    # Store original data for comparison
    original_data = {item['_id']: item for item in test_items}

    # 2. Restart MongoDB
    try:
        mongo_container = docker_client.containers.get(MONGODB_CONTAINER_NAME)
    except NotFound:
        pytest.skip(f"MongoDB container '{MONGODB_CONTAINER_NAME}' not found")

    mongo_container.restart()
    assert wait_for_backend_ready(), "Backend not ready after MongoDB restart"

    # 3. Retrieve items and verify data integrity
    response = requests.get(f'{BASE_URL}/api/items', timeout=10)
    assert response.status_code == 200
    items = response.json()

    for item_id, original_item in original_data.items():
        persisted_item = next((item for item in items if item['_id'] == item_id), None)
        assert persisted_item is not None, f"Item {item_id} not found after restart"

        # Verify critical fields match
        assert persisted_item['name'] == original_item['name']
        # Note: user_role might not be stored in current implementation
        # Add more field checks as schema evolves


def test_connection_retry_handles_mongodb_not_ready(docker_client):
    """
    Test that connection retry logic handles MongoDB starting after Flask.
    Verifies AC4: MongoDB connection retry logic handles container startup order gracefully.
    """
    # This test verifies the retry logic works by checking health endpoint
    # when MongoDB is temporarily unavailable

    # 1. Get baseline - backend should be healthy
    response = requests.get(f'{BASE_URL}/health', timeout=5)
    assert response.status_code == 200
    initial_health = response.json()
    assert initial_health.get('db') == 'connected'

    # 2. Stop MongoDB briefly
    try:
        mongo_container = docker_client.containers.get(MONGODB_CONTAINER_NAME)
    except NotFound:
        pytest.skip(f"MongoDB container '{MONGODB_CONTAINER_NAME}' not found")

    mongo_container.stop()
    time.sleep(2)

    # 3. Start MongoDB (backend should retry and reconnect)
    mongo_container.start()

    # 4. Wait and verify backend reconnects
    assert wait_for_backend_ready(max_attempts=20, delay=1), \
        "Backend failed to reconnect after MongoDB restart (retry logic may be broken)"

    # 5. Verify backend is fully functional again
    response = requests.get(f'{BASE_URL}/health', timeout=5)
    assert response.status_code == 200
    health = response.json()
    assert health.get('db') == 'connected', "Backend database not reconnected"
