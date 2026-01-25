from faker import Faker

fake = Faker()


def create_item(overrides=None):
    """Create a fake item for testing.

    Args:
        overrides: Dictionary of fields to override

    Returns:
        Dictionary representing an item
    """
    item = {
        "name": fake.word(),
        "user_role": fake.random_element(["PARENT", "KID"]),
        "status": fake.random_element(["PENDING", "APPROVED", "REJECTED"]),
        "price_nis": round(fake.pyfloat(min_value=1, max_value=500, right_digits=2), 2),
        "ai_status": fake.random_element(["CALCULATING", "COMPLETED", "ERROR"]),
    }
    if overrides:
        item.update(overrides)
    return item


def create_items(count, overrides=None):
    """Create multiple fake items for testing.

    Args:
        count: Number of items to create
        overrides: Dictionary of fields to override for all items

    Returns:
        List of item dictionaries
    """
    return [create_item(overrides) for _ in range(count)]
