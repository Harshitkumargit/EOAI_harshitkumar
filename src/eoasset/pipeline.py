"""CLI for dependency inspection, ingestion, evaluation and portable publication."""
import argparse
import importlib
import json
import logging
from pathlib import Path
import sys
import time

from .config import load_config, processing_hash
from .util import clean, environment, write_json

LOG = logging.getLogger(__name__)


def doctor():
    print(f"Interpreter: {sys.executable}")
    print(json.dumps(environment(), indent=2))
    failed = []
    for name in ("numpy", "pandas", "rasterio", "sklearn", "matplotlib", "joblib", "scipy", "threadpoolctl"):
        try:
            importlib.import_module(name)
            print(f"OK import {name}")
        except Exception as exc:
            failed.append(name)
            print(f"FAILED {name}: {exc}")
    if failed:
        print("No packages were installed. Choose the documented Python 3.10 interpreter or review requirements.txt.")
    return 1 if failed else 0


def run(cfg, root, offline=False, cached_only=False, ingest_only=False, max_items=None,
        allow_partial=False, out_dir=None, make_figures=True):
    from .catalogue import Catalogue, cache_lock
    from .features import supervised, weekly_table
    from .grid import make_grid
    from .ingest import ingest
    from .model import run_model
    from .outputs import publish
    from .synthetic import make_scenes

    started, root = time.monotonic(), Path(root)
    grid = make_grid(cfg)
    if offline:
        mode = "synthetic"
        scene = make_scenes(cfg, grid)
        stats = {"discovered": int(scene.item_id.nunique()), "processed": 0, "cached": 0, "failed": [], "note": "Artificial summaries, no satellite input."}
        sources = [{"id": ident, "type": "synthetic", "seed": cfg["model"]["seed"]} for ident in sorted(scene.item_id.unique())]
    else:
        mode = "satellite"
        cache_root = root / cfg["paths"]["cache"] / processing_hash(cfg)
        if cached_only and not (cache_root / "catalogue.sqlite").exists():
            raise ValueError("No compatible cache exists. First run --ingest-only or a full satellite pipeline.")
        with cache_lock(cache_root), Catalogue(cache_root) as catalog:
            if cached_only:
                entries = catalog.query(cfg["time"]["start"], cfg["time"]["end"], cfg["aoi"]["bbox"])
                entries = [r for r in entries if json.loads(r["source_json"])["properties"].get("eo:cloud_cover", 100) <= cfg["stac"]["max_cloud"]]
                bad = [r["id"] for r in entries if not catalog.current(r["id"], r["source_hash"])]
                if bad:
                    raise ValueError(f"Cached rasters/rows are incomplete or corrupt: {bad[:5]}. Run normal ingestion to repair.")
                scene = catalog.features([r["id"] for r in entries])
                sources = [json.loads(r["source_json"]) for r in entries]
                stats = {"discovered": len(entries), "processed": 0, "cached": len(entries), "failed": catalog.failures(), "note": "Cached-only: discovery completeness is unknown; unresolved cache failures are retained conservatively; no network request."}
            else:
                scene, stats, sources = ingest(cfg, grid, catalog, max_items)
            stats["cache_path"] = str(cache_root)
            stats["processing_hash"] = cache_root.name
            stats["cache_raster_bytes"] = sum(p.stat().st_size for p in (cache_root / "rasters").glob("*.tif"))
            write_json(cache_root / "ingestion_status.json", stats)
        print(json.dumps(clean(stats), indent=2))
        if stats["failed"] and not allow_partial:
            raise RuntimeError("Some scenes failed. Successful scenes are cached. Retry ingestion, or explicitly use --allow-partial; no new dashboard was published.")
        if ingest_only:
            LOG.info("Ingestion trial complete; no model fitting requested.")
            return cache_root
    if scene.empty:
        raise ValueError("No observations available for this configuration.")
    LOG.info("Building complete weekly observations for %d cells", len(grid.ids))
    weekly = weekly_table(scene, grid.ids, cfg)
    table = supervised(weekly)
    LOG.info("Fitting and evaluating fixed chronological experiment")
    metrics, test, forecast, assessment, final = run_model(table, cfg)
    default_output = cfg["paths"]["demo_outputs" if offline else "live_outputs"]
    destination = Path(out_dir) if out_dir else root / default_output
    if not destination.is_absolute():
        destination = root / destination
    result = publish(destination, cfg, grid, scene, weekly, metrics, test, forecast,
                     (assessment, final), mode, stats, sources, started, make_figures=make_figures)
    print(f"\nCompleted {mode} run. Open this file in your browser:\n{result / 'dashboard.html'}")
    print(f"Metrics: {result / 'metrics.json'}\nReport: {result / 'report.md'}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[2] / "config.json"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--doctor", action="store_true", help="inspect imports; install nothing")
    mode.add_argument("--offline", action="store_true", help="synthetic demo, no network")
    mode.add_argument("--cached-only", action="store_true", help="analyze existing compatible cache without network")
    mode.add_argument("--ingest-only", action="store_true", help="retrieve and catalogue scenes without fitting")
    mode.add_argument("--catalog-query", action="store_true", help="query local scene catalogue by dates and bbox")
    parser.add_argument("--max-items", type=int, help="deterministic discovery cap, only for --ingest-only")
    parser.add_argument("--allow-partial", action="store_true", help="explicitly publish despite failed scenes")
    parser.add_argument("--out-dir", help="output root; immutable run directories are written underneath")
    parser.add_argument("--candidate-pool", choices=("stable", "research"), default=None,
                        help="stable preserves the established three candidates; research enables the experimental pool")
    parser.add_argument("--start", help="catalogue query start date, YYYY-MM-DD")
    parser.add_argument("--end", help="catalogue query end date, YYYY-MM-DD")
    parser.add_argument("--bbox", type=float, nargs=4, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("rasterio.session").setLevel(logging.WARNING)
    if args.doctor:
        return doctor()
    if args.max_items is not None and (not args.ingest_only or args.max_items < 1):
        parser.error("--max-items must be positive and used with --ingest-only")
    try:
        config_path = Path(args.config).resolve()
        cfg = load_config(config_path)
        if args.candidate_pool is not None:
            cfg["model"]["candidate_pool"] = args.candidate_pool
        root = config_path.parent
        if args.catalog_query:
            from datetime import date
            from .catalogue import Catalogue
            start, end = args.start or cfg["time"]["start"], args.end or cfg["time"]["end"]
            if date.fromisoformat(start) > date.fromisoformat(end):
                raise ValueError("Query start is after end.")
            if args.bbox and (args.bbox[0] >= args.bbox[2] or args.bbox[1] >= args.bbox[3]):
                raise ValueError("Invalid query bbox order.")
            cache = root / cfg["paths"]["cache"] / processing_hash(cfg)
            if not (cache / "catalogue.sqlite").exists():
                raise ValueError("No catalogue yet; run ingestion first.")
            with Catalogue(cache) as catalog:
                rows = catalog.query(start, end, args.bbox)
            fields = ("id", "acquired", "raster", "row_count", "completed")
            print(json.dumps([{k: row[k] for k in fields} for row in rows], indent=2))
            return 0
        run(cfg, root, args.offline, args.cached_only, args.ingest_only, args.max_items,
            args.allow_partial, args.out_dir)
        return 0
    except (ValueError, RuntimeError, OSError, ImportError) as exc:
        LOG.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
