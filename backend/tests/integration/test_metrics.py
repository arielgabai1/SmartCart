import pytest
from prometheus_client import make_wsgi_app, REGISTRY
from werkzeug.test import Client
from ai_engine import AI_LATENCY # Import to ensure it's registered

def test_metrics_registry_contains_ai_latency():
    """Test that ai_latency_seconds is registered in the global registry"""
    metric_names = [m.name for m in REGISTRY.collect()]
    assert 'ai_latency_seconds' in metric_names

def test_metrics_endpoint_content():
    """Test that the metrics WSGI app returns the ai_latency_seconds metric"""
    app = make_wsgi_app()
    client = Client(app)
    response = client.get('/metrics')
    
    assert response.status_code == 200
    # Prometheus client returns bytes
    assert b'ai_latency_seconds' in response.data
    assert b'# HELP ai_latency_seconds' in response.data
    assert b'# TYPE ai_latency_seconds histogram' in response.data
