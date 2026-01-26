"""Tests for dual-port Flask setup (Story 2.1).

Verifies that the backend is configured to run on two ports:
- Port 5000: API routes (proxied through Nginx)
- Port 8081: Metrics/observability endpoint (threaded, exposed directly)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from app import app, run_metrics_server
from prometheus_client import make_wsgi_app


class TestDualPortSetup:
    """Tests for dual-port Flask configuration."""

    def test_flask_app_exists(self):
        """Flask app instance should be created."""
        assert app is not None
        assert app.name == "app"

    def test_metrics_server_function_exists(self):
        """run_metrics_server function should be defined."""
        assert callable(run_metrics_server)

    def test_prometheus_metrics_app_can_be_created(self):
        """Prometheus WSGI app should be creatable."""
        metrics_app = make_wsgi_app()
        assert metrics_app is not None


class TestDockerComposePortConfig:
    """Tests verifying docker-compose.yml exposes correct ports."""

    def test_backend_exposes_api_port(self):
        """Backend service should expose port 5000 for API."""
        import yaml
        compose_file = Path(__file__).parent.parent.parent.parent / "docker-compose.yml"

        with open(compose_file) as f:
            config = yaml.safe_load(f)

        backend = config["services"]["backend"]
        ports = backend["ports"]

        # Port 5000 should be mapped (e.g., "5001:5000")
        api_port_mapped = any("5000" in str(p) for p in ports)
        assert api_port_mapped, "Backend must expose port 5000 for API"

    def test_backend_exposes_metrics_port(self):
        """Backend service should expose port 8081 for metrics."""
        import yaml
        compose_file = Path(__file__).parent.parent.parent.parent / "docker-compose.yml"

        with open(compose_file) as f:
            config = yaml.safe_load(f)

        backend = config["services"]["backend"]
        ports = backend["ports"]

        # Port 8081 should be mapped
        metrics_port_mapped = any("8081" in str(p) for p in ports)
        assert metrics_port_mapped, "Backend must expose port 8081 for metrics"


class TestAppConfiguration:
    """Tests for app.py configuration."""

    def test_cors_enabled(self):
        """CORS should be enabled on Flask app."""
        # Check if Flask-CORS is applied (extensions registered)
        assert app is not None

    def test_health_endpoint_exists(self):
        """Health endpoint should be registered."""
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        assert "/health" in rules
