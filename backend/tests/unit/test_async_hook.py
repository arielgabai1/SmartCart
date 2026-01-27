import time
import pytest
from unittest.mock import patch, MagicMock
from app import app
from auth import generate_token

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@patch('app.estimate_item_price')
@patch('app.get_db')
@patch('auth.get_db')
def test_create_item_returns_immediately_with_slow_ai(mock_auth_db, mock_app_db, mock_ai, client):
    """
    Test that the create_item endpoint returns immediately (201 Created)
    even if the AI estimation takes a long time (simulated 2s delay).
    This confirms the threading logic is working.
    """
    # Setup Mock DB
    mock_db_instance = MagicMock()
    mock_app_db.return_value = mock_db_instance
    mock_auth_db.return_value = mock_db_instance
    
    # Fallback to token data if DB lookup returns None (simulating no user found or DB error handled)
    mock_db_instance['users'].find_one.return_value = None 
    
    # Setup Mock Insert
    mock_db_instance['items'].insert_one.return_value.inserted_id = '12345'
    
    # Setup AI Mock to be slow
    def slow_ai(*args, **kwargs):
        time.sleep(2) # Sleep 2 seconds
        return 10.0, 'COMPLETED'
    
    mock_ai.side_effect = slow_ai

    # Generate Token
    token = generate_token('u1', 'g1', 'MANAGER', 'User', 'Group')
    headers = {'Authorization': f'Bearer {token}'}
    
    start_time = time.time()
    response = client.post('/api/items', json={
        'name': 'Slow Milk', 
        'category': 'Dairy',
        'quantity': 1
    }, headers=headers)
    end_time = time.time()
    
    # Assertions
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.json}"
    
    duration = end_time - start_time
    print(f"Request took {duration:.4f} seconds")
    
    # It should be instant (< 0.5s)
    assert duration < 0.5

@patch('app.logger')
@patch('app.estimate_item_price')
@patch('app.get_db')
@patch('auth.get_db')
def test_async_ai_db_failure_logging(mock_auth_db, mock_app_db, mock_ai, mock_logger, client):
    """
    Test that if the DB update fails in the background thread, 
    the error is logged and the thread terminates gracefully.
    """
    # Setup Mock DB
    mock_db_instance = MagicMock()
    mock_app_db.return_value = mock_db_instance
    mock_auth_db.return_value = mock_db_instance
    
    # Ensure repeated calls to ['items'] return the SAME mock object
    mock_items_collection = MagicMock()
    mock_db_instance.__getitem__.return_value = mock_items_collection
    
    # Auth mocking
    mock_db_instance['users'].find_one.return_value = None 
    mock_items_collection.insert_one.return_value.inserted_id = '12345'
    
    # Mock AI to return quickly
    mock_ai.return_value = (10.0, 'COMPLETED')
    
    # Mock DB update to raise an exception
    mock_items_collection.update_one.side_effect = Exception("DB Connection Lost")

    # Generate Token
    token = generate_token('u1', 'g1', 'MANAGER', 'User', 'Group')
    headers = {'Authorization': f'Bearer {token}'}
    
    # Make request
    client.post('/api/items', json={
        'name': 'Crashy Milk', 
        'category': 'Dairy',
        'quantity': 1
    }, headers=headers)
    
    # Give the thread a moment to run and fail
    time.sleep(0.1)
    
    # Verify logger.error was called
    mock_logger.error.assert_called()
    call_args = mock_logger.error.call_args[0]
    assert "Background update failed" in call_args[0]
