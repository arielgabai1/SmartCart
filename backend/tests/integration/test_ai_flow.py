import time
import pytest
from unittest.mock import patch
from app import app
from auth import generate_token
from bson import ObjectId

@patch.dict('os.environ', {}, clear=True)
def test_ai_flow_invalid_api_key(client, mock_db):
    """
    Integration-like test: Verify that when API Key is missing,
    the system gracefully falls back to ERROR status and 0.0 price
    in the database via the background thread.
    """
    # 1. Setup Auth
    token = generate_token('u1', 'g1', 'MANAGER', 'User', 'Group')
    headers = {'Authorization': f'Bearer {token}'}

    # 2. Post Item
    response = client.post('/api/items', json={
        'name': 'NoKey Item',
        'category': 'Test',
        'quantity': 1
    }, headers=headers)
    
    assert response.status_code == 201
    item_id = response.json['_id']

    # 3. Wait for background thread to finish
    # Since we are using real threads with a mock DB, we need to wait a tiny bit
    time.sleep(0.5)

    # 4. Verify DB State
    # We access the mock_db directly to verify the background update happened
    items_collection = mock_db['items']
    stored_item = items_collection.find_one({'_id': ObjectId(item_id)})
    
    assert stored_item is not None
    assert stored_item['ai_status'] == 'ERROR'
    assert stored_item['price_nis'] == 0.0
