import hashlib
import hmac
import json
from typing import Dict, Any
from urllib.parse import parse_qsl, unquote


def _build_data_check_string(data: Dict[str, str]) -> str:
    # Exclude hash
    pairs = []
    for key in sorted(k for k in data.keys() if k != "hash"):
        value = data[key]
        pairs.append(f"{key}={value}")
    return "\n".join(pairs)


def validate_init_data(init_data: str, bot_token: str) -> Dict[str, Any]:
    """
    Validates Telegram WebApp initData string per docs.
    Returns parsed dict (including 'user' parsed) if valid, else {}.
    """
    if not init_data or not bot_token:
        return {}

    # Parse query-like string
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    # decode percent-encoding
    pairs = {k: unquote(v) for k, v in pairs.items()}
    tg_hash = pairs.get("hash", "")
    if not tg_hash:
        return {}

    data_check_string = _build_data_check_string(pairs)

    # secret_key = HMAC_SHA256("WebAppData", bot_token)
    secret_key = hmac.new(
        key=b"WebAppData", msg=bot_token.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()

    computed_hash = hmac.new(
        key=secret_key, msg=data_check_string.encode("utf-8"), digestmod=hashlib.sha256
    ).hexdigest()

    if computed_hash != tg_hash:
        return {}

    # Parse user JSON if present
    result: Dict[str, Any] = dict(pairs)
    if "user" in result:
        try:
            result["user"] = json.loads(result["user"])  # type: ignore
        except Exception:
            pass

    return result


