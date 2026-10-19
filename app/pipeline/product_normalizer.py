"""Turn the LLM's product list into complete products in the API target format."""
import re

from app.core.constants import DEFAULT_PRICE, DEFAULT_QUANTITY, DEFAULT_PREPARATION_TIME, DEFAULT_DESCRIPTION

# First number in a value such as "12 oz" or "$5.50"
NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def to_number(value, cast, default):
    """Convert LLM output like 12, "12", "12 oz" or "$5.50" to a number; default if missing or not numeric."""
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, (int, float)):
        return cast(value)
    match = NUMBER_PATTERN.search(str(value))
    return cast(float(match.group())) if match else default


def normalize_products(products: list) -> list:
    """Validate extracted products and fill every field, using defaults for missing values."""
    normalized_products = []
    for p in products:
        if not isinstance(p, dict) or not p.get("product_name"):
            continue
        price = to_number(p.get("price"), float, DEFAULT_PRICE)
        variants = [
            {
                "name": str(v["name"]),
                # A variant without its own price inherits the product price
                "vendorPrice": to_number(v.get("price"), float, price),
                "availableQuantity": to_number(v.get("quantity"), int, DEFAULT_QUANTITY),
            }
            for v in (p.get("variants") if isinstance(p.get("variants"), list) else [])
            if isinstance(v, dict) and v.get("name")
        ]
        normalized_products.append({
            "name": str(p["product_name"]),
            "description": str(p["description"]) if p.get("description") is not None else DEFAULT_DESCRIPTION,
            "price": price,
            "quantity": to_number(p.get("quantity"), int, DEFAULT_QUANTITY),
            "preparationTime": to_number(p.get("preparation_time"), int, DEFAULT_PREPARATION_TIME),
            "variants": variants,
        })
    return normalized_products
