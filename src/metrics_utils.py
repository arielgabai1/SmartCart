"""Shared metrics utilities to avoid circular imports."""
import logging
import db

logger = logging.getLogger(__name__)

def update_db_metrics(db_connections_gauge, items_total_gauge):
    """Updates DB metrics. Called periodically by metrics server."""
    try:
        if db.db_client:
            status = db.db_client.admin.command('serverStatus')
            current = status.get('connections', {}).get('current', 0)
            db_connections_gauge.set(current)

            database = db.get_db()
            count = database['items'].count_documents({})
            items_total_gauge.set(count)
    except Exception as e:
        logger.error(f"Error updating DB metrics: {e}")
