"""
Resilience and Failure Mode tests (Phase 3).
Verifies system behavior under degraded conditions:
1. Database connection failure
2. AI Engine failures/timeouts
3. Authentication failures (expired/malformed tokens)
"""
import pytest
from unittest.mock import patch
from pymongo.errors import ConnectionFailure
import auth as auth_module
import ai_engine as ai_module
import datetime
import jwt
from auth import SECRET_KEY, ALGORITHM

@pytest.mark.resilience
def test_db_connection_failure_health(client):
    """Verify health endpoint reports 503 when DB is down."""
    with patch('db.db_client') as mock_client:
        # Mock ping failure
        mock_client.admin.command.side_effect = ConnectionFailure("Connection refused")
        response = client.get('/health')
        assert response.status_code == 503
        assert response.get_json()['status'] == 'unhealthy'

@pytest.mark.resilience
def test_db_connection_failure_api(client):
    """Verify API returns 500 when DB is completely unreachable."""
    with patch('app.get_db') as mock_get_db:
        mock_get_db.side_effect = ConnectionFailure("Database unreachable")
        response = client.get('/api/items')
        assert response.status_code == 500
        assert 'error' in response.get_json()

@pytest.mark.resilience
def test_ai_engine_failure_handling(client, mock_db):
    """Verify item creation succeeds even if AI engine fails (graceful degradation)."""
    with patch('app.estimate_item_price') as mock_estimate:
        mock_estimate.side_effect = Exception("AI Engine Timeout")
        
        # Creation should still succeed with 201
        response = client.post('/api/items', json={'name': 'Bread', 'category': 'Bakery'})
        assert response.status_code == 201
        # The background thread will log an error but the API response is already sent

@pytest.mark.resilience
def test_expired_token_returns_401(app):
    """Verify expired JWT tokens are rejected."""
    # Create an expired token
    payload = {
        'user_id': 'test-user',
        'group_id': 'test-group',
        'role': 'MANAGER',
        'exp': datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    }
    expired_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    test_client = app.test_client()
    response = test_client.get('/api/items', headers={'Authorization': f'Bearer {expired_token}'})
    assert response.status_code == 401
    assert 'expired' in response.get_json()['details'].lower()

@pytest.mark.resilience
def test_malformed_token_returns_401(app):
    """Verify malformed JWT tokens are rejected."""
    test_client = app.test_client()
    response = test_client.get('/api/items', headers={'Authorization': 'Bearer not-a-valid-token'})
    assert response.status_code == 401
    assert 'invalid' in response.get_json()['details'].lower()
