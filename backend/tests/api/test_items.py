import pytest


class TestItemsEndpoint:
    """Tests for /api/items endpoint."""

    @pytest.mark.p0
    @pytest.mark.api
    def test_get_items_returns_200(self, client):
        """[P0] GET /api/items should return 200 status code.

        GIVEN: The backend service is running
        WHEN: GET request is made to /api/items
        THEN: Response status code is 200
        """
        response = client.get("/api/items")

        assert response.status_code == 200

    @pytest.mark.p0
    @pytest.mark.api
    def test_get_items_returns_list(self, client):
        """[P0] GET /api/items should return a JSON list.

        GIVEN: The backend service is running
        WHEN: GET request is made to /api/items
        THEN: Response is a JSON array
        """
        response = client.get("/api/items")
        data = response.get_json()

        assert isinstance(data, list)

    @pytest.mark.p1
    @pytest.mark.api
    def test_get_items_returns_json_content_type(self, client):
        """[P1] GET /api/items should return JSON content type.

        GIVEN: The backend service is running
        WHEN: GET request is made to /api/items
        THEN: Content-Type header is application/json
        """
        response = client.get("/api/items")

        assert response.content_type == "application/json"

    @pytest.mark.p1
    @pytest.mark.api
    def test_get_items_empty_list_initially(self, client):
        """[P1] GET /api/items should return empty list when no items exist.

        GIVEN: No items have been added
        WHEN: GET request is made to /api/items
        THEN: Response is an empty list
        """
        response = client.get("/api/items")
        data = response.get_json()

        assert data == []
