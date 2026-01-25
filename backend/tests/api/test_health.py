import pytest


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    @pytest.mark.p0
    @pytest.mark.api
    def test_health_returns_200(self, client):
        """[P0] GET /health should return 200 status code.

        GIVEN: The backend service is running
        WHEN: GET request is made to /health
        THEN: Response status code is 200
        """
        response = client.get("/health")

        assert response.status_code == 200

    @pytest.mark.p0
    @pytest.mark.api
    def test_health_returns_healthy_status(self, client):
        """[P0] GET /health should return healthy status in JSON.

        GIVEN: The backend service is running
        WHEN: GET request is made to /health
        THEN: Response contains status: healthy
        """
        response = client.get("/health")
        data = response.get_json()

        assert data["status"] == "healthy"

    @pytest.mark.p1
    @pytest.mark.api
    def test_health_returns_service_name(self, client):
        """[P1] GET /health should identify the service.

        GIVEN: The backend service is running
        WHEN: GET request is made to /health
        THEN: Response contains service: backend
        """
        response = client.get("/health")
        data = response.get_json()

        assert data["service"] == "backend"

    @pytest.mark.p1
    @pytest.mark.api
    def test_health_returns_json_content_type(self, client):
        """[P1] GET /health should return JSON content type.

        GIVEN: The backend service is running
        WHEN: GET request is made to /health
        THEN: Content-Type header is application/json
        """
        response = client.get("/health")

        assert response.content_type == "application/json"
