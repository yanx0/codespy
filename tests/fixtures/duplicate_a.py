def process_user(user_id, name, email):
    if not user_id:
        raise ValueError("user_id is required")
    if not name:
        raise ValueError("name is required")
    if not email:
        raise ValueError("email is required")
    return {"id": user_id, "name": name, "email": email}


def other_function():
    return 42


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
