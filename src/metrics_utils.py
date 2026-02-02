"""Shared metrics utilities to avoid circular imports."""
import logging
import db

logger = logging.getLogger(__name__)

def update_db_metrics(db_connections_gauge, items_total_gauge):
    """Updates DB metrics. Called periodically by metrics server."""
    try:
        database = db.get_db()
        if database is None:
            return

        # Count items in database
        count = database['items'].count_documents({})
        items_total_gauge.set(count)

        # Get active connections from MongoDB server
        if db.db_client:
            try:
                status = db.db_client.admin.command('serverStatus')
                current = status.get('connections', {}).get('current', 0)
                db_connections_gauge.set(current)
            except Exception:
                # serverStatus requires admin privileges, set to 1 if connected
                db_connections_gauge.set(1)
    except Exception as e:
        logger.error(f"Error updating DB metrics: {e}")
