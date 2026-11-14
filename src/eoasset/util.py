"""Small atomic I/O and provenance helpers."""
from datetime import date, datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import tempfile

import numpy as np


def clean(value):
    """Convert scientific values to strict JSON; missing is null, never NaN."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def digest(value):
    return hashlib.sha256(json.dumps(clean(value), sort_keys=True, allow_nan=False).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path, value):
    atomic_text(path, json.dumps(clean(value), indent=2, allow_nan=False) + "\n")


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def environment():
    names = ["numpy", "pandas", "rasterio", "scikit-learn", "matplotlib", "joblib", "scipy", "threadpoolctl"]
    versions = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "MISSING"
    return {"python": platform.python_version(), "platform": platform.platform(), "packages": versions}


def code_hash():
    root = Path(__file__).parent
    return digest({p.name: file_hash(p) for p in sorted(root.iterdir()) if p.suffix in (".py", ".html")})
