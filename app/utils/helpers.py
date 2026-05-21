import hashlib
from typing import Dict, Any

def generate_event_key(data: Dict[str, Any]) -> str:
    dt = str(data.get("datetime") or "")
    mag = str(data.get("magnitude") or "")
    lat = str(data.get("latitude") or "")
    lon = str(data.get("longitude") or "")
    key_str = f"{dt}|{mag}|{lat}|{lon}"
    return hashlib.md5(key_str.encode()).hexdigest()

def setup_logging(level: str = "INFO"):
    import logging
    import sys
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )