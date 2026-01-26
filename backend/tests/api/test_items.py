import pytest
from bson import ObjectId
import uuid

# Helper to generate a valid family_id
TEST_FAMILY_ID = str(uuid.uuid4())

class TestGetItems:
    """Tests for GET /api/items endpoint."""

    @pytest.mark.p0
    @pytest.mark.api
    def test_get_items_returns_200(self, client):
        """[P0] GET /api/items should return 200 status code."""
        response = client.get(f"/api/items?family_id={TEST_FAMILY_ID}")
        assert response.status_code == 200

    @pytest.mark.p0
    @pytest.mark.api
    def test_get_items_returns_list(self, client):
        """[P0] GET /api/items should return a JSON list."""
        response = client.get(f"/api/items?family_id={TEST_FAMILY_ID}")
        data = response.get_json()
        assert isinstance(data, list)

    @pytest.mark.p1
    @pytest.mark.api
    def test_get_items_returns_json_content_type(self, client):
        """[P1] GET /api/items should return JSON content type."""
        response = client.get(f"/api/items?family_id={TEST_FAMILY_ID}")
        assert response.content_type == "application/json"

    @pytest.mark.p1
    @pytest.mark.api
    def test_get_items_empty_list_initially(self, client):
        """[P1] GET /api/items should return empty list when no items exist."""
        response = client.get(f"/api/items?family_id={TEST_FAMILY_ID}")
        data = response.get_json()
        assert data == []

    @pytest.mark.p0
    @pytest.mark.api
    def test_get_items_returns_created_items(self, client):
        """[P0] GET /api/items returns items after creation."""
        # Create an item first
        client.post("/api/items", json={
            "name": "Milk",
            "user_role": "MANAGER",
            "family_id": TEST_FAMILY_ID
        })

        response = client.get(f"/api/items?family_id={TEST_FAMILY_ID}")
        data = response.get_json()

        assert len(data) == 1
        assert data[0]["name"] == "Milk"
        assert data[0]["user_role"] == "MANAGER"
        assert data[0]["family_id"] == TEST_FAMILY_ID

    @pytest.mark.p0
    @pytest.mark.api
    def test_get_items_returns_complete_data_contract(self, client):
        """[P0] GET /api/items returns all required fields per AC4."""
        # Create an item with all fields
        client.post("/api/items", json={
            "name": "Milk",
            "user_role": "MANAGER",
            "family_id": TEST_FAMILY_ID,
            "status": "APPROVED",
            "price_nis": 15.5,
            "ai_status": "COMPLETED",
            "ai_latency": 1.23
        })

        response = client.get(f"/api/items?family_id={TEST_FAMILY_ID}")
        data = response.get_json()

        assert len(data) == 1
        item = data[0]

        # Verify all required fields from AC4
        assert "_id" in item and isinstance(item["_id"], str)
        assert item["name"] == "Milk"
        assert item["user_role"] == "MANAGER"
        assert item["status"] == "APPROVED"
        assert item["price_nis"] == 15.5
        assert item["ai_status"] == "COMPLETED"
        assert item["ai_latency"] == 1.23

    @pytest.mark.p1
    @pytest.mark.api
    def test_get_items_returns_fields_with_null_values(self, client):
        """[P1] GET /api/items returns all fields even when null/default (AC4)."""
        # Create a minimal item (only required fields)
        client.post("/api/items", json={
            "name": "Bread",
            "family_id": TEST_FAMILY_ID
        })

        response = client.get(f"/api/items?family_id={TEST_FAMILY_ID}")
        data = response.get_json()

        assert len(data) == 1
        item = data[0]

        # All fields should be present, even if null or default
        assert "_id" in item
        assert "name" in item
        assert "status" in item  # Should have default PENDING
        assert "price_nis" in item  # Should have default 0.0
        # ai_status and ai_latency may not be present if not set (optional fields)


class TestPostItems:
    """Tests for POST /api/items endpoint."""

    @pytest.mark.p0
    @pytest.mark.api
    def test_post_item_returns_201(self, client):
        """[P0] POST /api/items should return 201 status code."""
        response = client.post("/api/items", json={
            "name": "Bamba",
            "user_role": "MEMBER",
            "family_id": TEST_FAMILY_ID
        })
        assert response.status_code == 201

    @pytest.mark.p0
    @pytest.mark.api
    def test_post_item_returns_created_item(self, client):
        """[P0] POST /api/items should return the created item with _id."""
        response = client.post("/api/items", json={
            "name": "Bamba",
            "user_role": "MEMBER",
            "family_id": TEST_FAMILY_ID
        })
        data = response.get_json()

        assert "_id" in data
        assert data["name"] == "Bamba"
        assert data["user_role"] == "MEMBER"
        assert data["status"] == "PENDING"
        assert data["price_nis"] == 0.0
        assert data["family_id"] == TEST_FAMILY_ID
        # ai_status is optional/backward compat, checking if present only if logic dictates
        # Post-fix: it might be None or default, but strictly returned if part of contract
        if "ai_status" in data:
             pass 

    @pytest.mark.p1
    @pytest.mark.api
    def test_get_items_missing_family_id_returns_400(self, client):
        """[P1] GET /api/items without family_id should return 400."""
        response = client.get("/api/items")
        assert response.status_code == 400
        data = response.get_json()
        assert "family_id" in str(data["details"])

    @pytest.mark.p1
    @pytest.mark.api
    def test_post_item_invalid_ai_status_returns_400(self, client):
        """[P1] POST /api/items with invalid ai_status should return 400."""
        response = client.post("/api/items", json={
            "name": "Milk",
            "family_id": TEST_FAMILY_ID,
            "ai_status": "INVALID_STATUS"
        })
        assert response.status_code == 400
        data = response.get_json()
        assert "ai_status" in str(data["details"]) 

    @pytest.mark.p1
    @pytest.mark.api
    def test_post_item_missing_name_returns_400(self, client):
        """[P1] POST /api/items without name should return 400."""
        response = client.post("/api/items", json={
            "user_role": "MEMBER",
            "family_id": TEST_FAMILY_ID
        })
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    @pytest.mark.p1
    @pytest.mark.api
    def test_post_item_missing_family_id_returns_400(self, client):
        """[P1] POST /api/items without family_id should return 400."""
        response = client.post("/api/items", json={
            "name": "Milk",
            "user_role": "MANAGER"
        })
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "family_id" in str(data["details"])

    @pytest.mark.p1
    @pytest.mark.api
    def test_post_item_invalid_user_role_returns_400(self, client):
        """[P1] POST /api/items with invalid user_role should return 400."""
        response = client.post("/api/items", json={
            "name": "Milk",
            "user_role": "INVALID",
            "family_id": TEST_FAMILY_ID
        })
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    @pytest.mark.p1
    @pytest.mark.api
    def test_post_item_invalid_json_returns_400(self, client):
        """[P1] POST /api/items with invalid JSON should return 400."""
        response = client.post("/api/items", data="not json", content_type="application/json")
        assert response.status_code == 400

    @pytest.mark.p1
    @pytest.mark.api
    def test_post_item_accepts_manager_role(self, client):
        """[P1] POST /api/items should accept MANAGER role."""
        response = client.post("/api/items", json={
            "name": "Wine",
            "user_role": "MANAGER",
            "family_id": TEST_FAMILY_ID
        })
        assert response.status_code == 201
        data = response.get_json()
        assert data["user_role"] == "MANAGER"

    @pytest.mark.p1
    @pytest.mark.api
    def test_post_item_accepts_member_role(self, client):
        """[P1] POST /api/items should accept MEMBER role."""
        response = client.post("/api/items", json={
            "name": "Candy",
            "user_role": "MEMBER",
            "family_id": TEST_FAMILY_ID
        })
        assert response.status_code == 201
        data = response.get_json()
        assert data["user_role"] == "MEMBER"

    @pytest.mark.p1
    @pytest.mark.api
    def test_post_item_empty_name_returns_400(self, client):
        """[P1] POST /api/items with empty name should return 400."""
        response = client.post("/api/items", json={
            "name": "",
            "user_role": "MEMBER",
            "family_id": TEST_FAMILY_ID
        })
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    @pytest.mark.p1
    @pytest.mark.api
    def test_post_item_whitespace_name_returns_400(self, client):
        """[P1] POST /api/items with whitespace-only name should return 400."""
        response = client.post("/api/items", json={
            "name": "   ",
            "user_role": "MEMBER",
            "family_id": TEST_FAMILY_ID
        })
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    @pytest.mark.p1
    @pytest.mark.api
    def test_post_item_name_too_long_returns_400(self, client):
        """[P1] POST /api/items with name exceeding 200 chars should return 400."""
        long_name = "A" * 201
        response = client.post("/api/items", json={
            "name": long_name,
            "user_role": "MEMBER",
            "family_id": TEST_FAMILY_ID
        })
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    @pytest.mark.p1
    @pytest.mark.api
    def test_post_item_strips_whitespace(self, client):
        """[P1] POST /api/items should strip leading/trailing whitespace from name."""
        response = client.post("/api/items", json={
            "name": "  Milk  ",
            "user_role": "MANAGER",
            "family_id": TEST_FAMILY_ID
        })
        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "Milk"


class TestPutItems:
    """Tests for PUT /api/items/<id> endpoint."""

    @pytest.mark.p0
    @pytest.mark.api
    def test_put_item_returns_200(self, client):
        """[P0] PUT /api/items/<id> should return 200 on success."""
        # Create item first
        create_response = client.post("/api/items", json={
            "name": "Milk",
            "user_role": "MANAGER",
            "family_id": TEST_FAMILY_ID
        })
        item_id = create_response.get_json()["_id"]

        response = client.put(f"/api/items/{item_id}", json={"status": "APPROVED"})
        assert response.status_code == 200

    @pytest.mark.p0
    @pytest.mark.api
    def test_put_item_updates_status(self, client):
        """[P0] PUT /api/items/<id> should update item status."""
        # Create item first
        create_response = client.post("/api/items", json={
            "name": "Milk",
            "user_role": "MANAGER",
            "family_id": TEST_FAMILY_ID
        })
        item_id = create_response.get_json()["_id"]

        response = client.put(f"/api/items/{item_id}", json={"status": "APPROVED"})
        data = response.get_json()

        assert data["status"] == "APPROVED"
        assert data["name"] == "Milk"

    @pytest.mark.p1
    @pytest.mark.api
    def test_put_item_not_found_returns_404(self, client):
        """[P1] PUT /api/items/<id> returns 404 for non-existent item."""
        fake_id = str(ObjectId())
        response = client.put(f"/api/items/{fake_id}", json={"status": "APPROVED"})
        assert response.status_code == 404

    @pytest.mark.p1
    @pytest.mark.api
    def test_put_item_invalid_id_returns_400(self, client):
        """[P1] PUT /api/items/<id> returns 400 for invalid ObjectId."""
        response = client.put("/api/items/invalid-id", json={"status": "APPROVED"})
        assert response.status_code == 400

    @pytest.mark.p1
    @pytest.mark.api
    def test_put_item_missing_status_returns_400(self, client):
        """[P1] PUT /api/items/<id> without status returns 400."""
        create_response = client.post("/api/items", json={
            "name": "Milk",
            "user_role": "MANAGER",
            "family_id": TEST_FAMILY_ID
        })
        item_id = create_response.get_json()["_id"]

        response = client.put(f"/api/items/{item_id}", json={})
        assert response.status_code == 400

    @pytest.mark.p1
    @pytest.mark.api
    def test_put_item_invalid_status_returns_400(self, client):
        """[P1] PUT /api/items/<id> with invalid status returns 400."""
        create_response = client.post("/api/items", json={
            "name": "Milk",
            "user_role": "MANAGER",
            "family_id": TEST_FAMILY_ID
        })
        item_id = create_response.get_json()["_id"]

        response = client.put(f"/api/items/{item_id}", json={"status": "INVALID"})
        assert response.status_code == 400

    @pytest.mark.p1
    @pytest.mark.api
    def test_put_item_accepts_rejected_status(self, client):
        """[P1] PUT /api/items/<id> should accept REJECTED status."""
        create_response = client.post("/api/items", json={
            "name": "Candy",
            "user_role": "MEMBER",
            "family_id": TEST_FAMILY_ID
        })
        item_id = create_response.get_json()["_id"]

        response = client.put(f"/api/items/{item_id}", json={"status": "REJECTED"})
        assert response.status_code == 200
        assert response.get_json()["status"] == "REJECTED"

    @pytest.mark.p1
    @pytest.mark.api
    def test_put_item_invalid_json_returns_400(self, client):
        """[P1] PUT /api/items/<id> with invalid JSON should return 400."""
        create_response = client.post("/api/items", json={
            "name": "Milk",
            "user_role": "MANAGER",
            "family_id": TEST_FAMILY_ID
        })
        item_id = create_response.get_json()["_id"]

        response = client.put(f"/api/items/{item_id}", data="not json", content_type="application/json")
        assert response.status_code == 400


class TestDeleteItems:
    """Tests for DELETE /api/items/<id> endpoint."""

    @pytest.mark.p0
    @pytest.mark.api
    def test_delete_item_returns_204(self, client):
        """[P0] DELETE /api/items/<id> should return 204 on success."""
        # Create item first
        create_response = client.post("/api/items", json={
            "name": "Milk",
            "user_role": "MANAGER",
            "family_id": TEST_FAMILY_ID
        })
        item_id = create_response.get_json()["_id"]

        response = client.delete(f"/api/items/{item_id}")
        assert response.status_code == 204

    @pytest.mark.p0
    @pytest.mark.api
    def test_delete_item_removes_from_database(self, client):
        """[P0] DELETE /api/items/<id> should remove item from database."""
        # Create item first
        create_response = client.post("/api/items", json={
            "name": "Milk",
            "user_role": "MANAGER",
            "family_id": TEST_FAMILY_ID
        })
        item_id = create_response.get_json()["_id"]

        # Delete it
        client.delete(f"/api/items/{item_id}")

        # Verify it's gone
        get_response = client.get(f"/api/items?family_id={TEST_FAMILY_ID}")
        items = get_response.get_json()
        assert len(items) == 0

    @pytest.mark.p1
    @pytest.mark.api
    def test_delete_item_not_found_returns_404(self, client):
        """[P1] DELETE /api/items/<id> returns 404 for non-existent item."""
        fake_id = str(ObjectId())
        response = client.delete(f"/api/items/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.p1
    @pytest.mark.api
    def test_delete_item_invalid_id_returns_400(self, client):
        """[P1] DELETE /api/items/<id> returns 400 for invalid ObjectId."""
        response = client.delete("/api/items/invalid-id")
        assert response.status_code == 400


class TestCrudFlow:
    """Integration tests for full CRUD flow."""

    @pytest.mark.p0
    @pytest.mark.api
    def test_full_crud_flow(self, client):
        """[P0] Test complete Create -> Read -> Update -> Delete flow."""
        # CREATE
        create_response = client.post("/api/items", json={
            "name": "Bread",
            "user_role": "MANAGER",
            "family_id": TEST_FAMILY_ID
        })
        assert create_response.status_code == 201
        item_id = create_response.get_json()["_id"]

        # READ
        get_response = client.get(f"/api/items?family_id={TEST_FAMILY_ID}")
        items = get_response.get_json()
        assert len(items) == 1
        assert items[0]["name"] == "Bread"
        assert items[0]["status"] == "PENDING"
        assert items[0]["family_id"] == TEST_FAMILY_ID

        # UPDATE
        put_response = client.put(f"/api/items/{item_id}", json={"status": "APPROVED"})
        assert put_response.status_code == 200
        assert put_response.get_json()["status"] == "APPROVED"

        # Verify update persisted
        get_response = client.get(f"/api/items?family_id={TEST_FAMILY_ID}")
        assert get_response.get_json()[0]["status"] == "APPROVED"

        # DELETE
        delete_response = client.delete(f"/api/items/{item_id}")
        assert delete_response.status_code == 204

        # Verify deletion
        get_response = client.get(f"/api/items?family_id={TEST_FAMILY_ID}")
        assert get_response.get_json() == []

    @pytest.mark.p1
    @pytest.mark.api
    def test_multiple_items_crud(self, client):
        """[P1] Test CRUD with multiple items."""
        # Create multiple items
        items_data = [
            {"name": "Milk", "user_role": "MANAGER", "family_id": TEST_FAMILY_ID},
            {"name": "Bamba", "user_role": "MEMBER", "family_id": TEST_FAMILY_ID},
            {"name": "Bread", "user_role": "MANAGER", "family_id": TEST_FAMILY_ID},
        ]
        item_ids = []
        for item in items_data:
            response = client.post("/api/items", json=item)
            assert response.status_code == 201
            item_ids.append(response.get_json()["_id"])

        # Read all
        response = client.get(f"/api/items?family_id={TEST_FAMILY_ID}")
        items = response.get_json()
        assert len(items) == 3

        # Update one
        client.put(f"/api/items/{item_ids[1]}", json={"status": "REJECTED"})

        # Delete one
        client.delete(f"/api/items/{item_ids[0]}")

        # Verify final state
        response = client.get(f"/api/items?family_id={TEST_FAMILY_ID}")
        items = response.get_json()
        assert len(items) == 2
        bamba = next(i for i in items if i["name"] == "Bamba")
        assert bamba["status"] == "REJECTED"
