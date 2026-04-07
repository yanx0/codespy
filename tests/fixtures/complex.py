# Complex fixture — high cyclomatic complexity

def parse_token(token, mode, context, fallback, strict, encoding, timeout):
    """Parse a token — intentionally complex and has too many args."""
    if token is None:
        if fallback:
            return fallback
        elif strict:
            raise ValueError("Token cannot be None in strict mode")
        else:
            return None

    if mode == "json":
        try:
            import json
            result = json.loads(token)
            if isinstance(result, dict):
                for key, value in result.items():
                    if key.startswith("_"):
                        continue
                    if value is None:
                        continue
                    if isinstance(value, list):
                        for item in value:
                            if item and isinstance(item, str):
                                pass
            return result
        except Exception as e:
            if strict:
                raise
            return fallback
    elif mode == "xml":
        if encoding == "utf-8":
            token = token.encode("utf-8").decode("utf-8")
        elif encoding == "latin-1":
            token = token.encode("latin-1").decode("latin-1")
        return token.strip()
    elif mode == "base64":
        import base64
        try:
            return base64.b64decode(token).decode(encoding or "utf-8")
        except Exception:
            if strict:
                raise
            return fallback
    else:
        return token


def simple_func(x):
    return x * 2  # TODO: add more operations here


# FIXME: this is a hack
MAGIC_CONST = 42

def deeply_nested(data):
    result = []
    for item in data:
        if item:
            for sub in item:
                if sub:
                    for val in sub:
                        if val > 0:
                            if val < 100:
                                result.append(val * 3.14159)
    return result
