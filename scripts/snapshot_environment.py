"""Record the existing interpreter's required versions; never install anything."""
from importlib import metadata
from pathlib import Path
import sys

try:
    from packaging.requirements import Requirement
except ImportError:
    from pip._vendor.packaging.requirements import Requirement

DIRECT = ["numpy", "pandas", "rasterio", "scikit-learn", "matplotlib", "joblib", "threadpoolctl"]


def main():
    root = Path(__file__).resolve().parents[1]
    todo, found = list(DIRECT), {}
    while todo:
        name = todo.pop()
        dist = metadata.distribution(name)
        canonical = dist.metadata["Name"]
        if canonical.lower() in found:
            continue
        found[canonical.lower()] = (canonical, dist.version)
        for line in dist.requires or []:
            req = Requirement(line)
            if req.marker is None or req.marker.evaluate({"extra": ""}):
                todo.append(req.name)
    header = f"# Snapshot of existing Python {sys.version.split()[0]}; no installation performed.\n"
    (root / "requirements.txt").write_text(header + "".join(f"{n}=={metadata.version(n)}\n" for n in DIRECT), encoding="utf-8")
    (root / "requirements-lock.txt").write_text(header + "# Required installed dependency closure; Windows Python 3.10 reference.\n" + "".join(f"{name}=={version}\n" for name, version in sorted(found.values(), key=lambda x: x[0].lower())), encoding="utf-8")
    print(f"Recorded {len(DIRECT)} direct packages and {len(found)} total required installed packages.")


if __name__ == "__main__":
    main()
