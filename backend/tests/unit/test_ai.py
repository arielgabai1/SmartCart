import pytest
import os
from unittest.mock import patch, MagicMock
from ai_engine import estimate_item_price, AI_LATENCY

# Helper to mock client response
def setup_mock_client(mock_get_client, content_str):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content_str
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client

@patch('ai_engine.get_openai_client')
def test_ai_latency_metric_recorded(mock_get_client):
    """Test metric recording"""
    setup_mock_client(mock_get_client, "10.5")
    initial_count = sum(s.value for s in AI_LATENCY.collect()[0].samples if s.name.endswith('_count'))
    estimate_item_price("Milk", "Dairy")
    final_count = sum(s.value for s in AI_LATENCY.collect()[0].samples if s.name.endswith('_count'))
    assert final_count == initial_count + 1

@patch('ai_engine.get_openai_client')
def test_estimate_price_parsing(mock_get_client):
    """Test various response parsing scenarios"""
    
    # 1. Clean number
    setup_mock_client(mock_get_client, "10.50")
    price, status = estimate_item_price("Milk", "Dairy")
    assert price == 10.50
    assert status == 'COMPLETED'
    
    # 2. Text with number
    setup_mock_client(mock_get_client, "The price is about 20 NIS.")
    price, status = estimate_item_price("Bread", "Bakery")
    assert price == 20.0
    assert status == 'COMPLETED'
    
    # 3. Invalid format (no numbers) -> Should return default
    setup_mock_client(mock_get_client, "Ten Fifty")
    price, status = estimate_item_price("Weird", "Thing")
    assert price == 0.0 # Fallback
    assert status == 'ERROR'

    # 4. Zero or negative
    setup_mock_client(mock_get_client, "0")
    price, status = estimate_item_price("Free", "Air")
    assert price == 0.0 # Fallback
    assert status == 'ERROR'

@patch('ai_engine.get_openai_client')
def test_api_failure_fallback(mock_get_client):
    """Test fallback when API raises exception"""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("API Error")
    
    price, status = estimate_item_price("Error", "Item")
    assert price == 0.0
    assert status == 'ERROR'

def test_missing_api_key_fallback():
    """Test fallback when API Key is missing"""
    with patch.dict(os.environ, {}, clear=True):
        price, status = estimate_item_price("NoKey", "Test")
        assert price == 0.0
        assert status == 'ERROR'