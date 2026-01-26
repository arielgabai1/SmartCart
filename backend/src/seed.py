import os
import logging
from db import get_db, get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_data():
    logger.info("Starting database seeding...")
    
    # Force connection
    get_db_connection()
    db = get_db()
    
    items_collection = db['items']
    
    # Initial data
    seed_items = [
        {
            "name": "Milk 3%",
            "group_id": "demo-group",
            "user_role": "MANAGER",
            "status": "PENDING",
            "price_nis": 0.0,
            "ai_status": "COMPLETED", 
            "ai_latency": 0.5,
            "created_at": "2024-01-26T12:00:00Z"
        },
        {
            "name": "Eggs (L)",
            "group_id": "demo-group",
            "user_role": "MEMBER",
            "status": "APPROVED",
            "price_nis": 25.90,
            "ai_status": None,
            "ai_latency": None,
             "created_at": "2024-01-26T12:05:00Z"
        },
        {
            "name": "Bread",
            "group_id": "other-group",
            "user_role": "MANAGER",
            "status": "PENDING",
            "price_nis": 0.0,
            "ai_status": None,
            "ai_latency": None,
            "created_at": "2024-01-26T12:10:00Z"
        }
    ]
    
    # Clear existing demo data
    result = items_collection.delete_many({"group_id": {"$in": ["demo-group", "other-group"]}})
    logger.info(f"Cleared {result.deleted_count} existing demo items.")
    
    # Insert new data
    if seed_items:
        result = items_collection.insert_many(seed_items)
        logger.info(f"Seeded {len(result.inserted_ids)} items.")
    
    logger.info("Seeding complete.")

if __name__ == "__main__":
    seed_data()
