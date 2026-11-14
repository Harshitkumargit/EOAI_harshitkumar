"""Self-contained asset rendering; no server or JavaScript dependencies."""
import json
from pathlib import Path

from .util import atomic_text, clean


def render(path, payload):
    template = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")
    # Prevent a source string from terminating the embedded JSON script element.
    encoded = json.dumps(clean(payload), allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    atomic_text(path, template.replace("__DATA_JSON__", encoded))
