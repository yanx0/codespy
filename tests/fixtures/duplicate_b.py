def validate_product(product_id, title, sku):
    if not product_id:
        raise ValueError("product_id is required")
    if not title:
        raise ValueError("title is required")
    if not sku:
        raise ValueError("sku is required")
    return {"id": product_id, "title": title, "sku": sku}


def another_function():
    return 99


# Shared utility — copy-pasted in both files
def _parse_config(data):
    result = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, str):
            result[key] = value.strip()
        else:
            result[key] = value
    return result
