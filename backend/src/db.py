"""
Database connection module for Smart Cart.

Provides centralized MongoDB connection logic with retry mechanism.
"""
import logging
import os
import time
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

logger = logging.getLogger(__name__)

# Lazy DB initialization
db_client = None
db = None


def get_db_connection(max_retries=5, retry_delay=2):
    """
    Establish MongoDB connection with retry logic.

    Args:
        max_retries: Maximum number of connection attempts (default: 5)
        retry_delay: Delay in seconds between retries (default: 2)

    Returns:
        MongoClient instance

    Raises:
        ConnectionFailure: If connection fails after max_retries
    """
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://database:27017/smartcart')

    for attempt in range(1, max_retries + 1):
        try:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            logger.info('MongoDB connection established', extra={'attempt': attempt})
            return client
        except ConnectionFailure as e:
            logger.warning(
                'MongoDB connection failed, retrying...',
                extra={'attempt': attempt, 'max_retries': max_retries, 'error': str(e)}
            )
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                logger.error('MongoDB connection failed after max retries')
                raise
    return None


def get_db():
    """
    Get database instance with lazy initialization.

    Returns:
        Database instance
    """
    global db_client, db
    if db_client is None:
        db_client = get_db_connection()
        db = db_client.get_database()
    return db
