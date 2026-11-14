"""Scientific and infrastructure regressions, using unittest and no network."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin

from eoasset.catalogue import Catalogue, cache_lock
from eoasset.config import load_config, processing_hash, validate
from eoasset.evaluate import evaluate, ranking, skill
from eoasset.features import FEATURES, complete_weeks, supervised, weekly_table
from eoasset.grid import make_grid
from eoasset.ingest import asset_metadata, ingest, load_scene, search_items, source_hash
from eoasset.model import run_model
from eoasset.pipeline import run
from eoasset.preprocess import block_stats, ndvi, reflectance, scene_rows, write_ndvi
from eoasset.synthetic import make_scenes
from eoasset.util import file_hash, write_json

ROOT = Path(__file__).resolve().parents[1]


def config():
    cfg = load_config(ROOT / "config.json")
    cfg["aoi"]["bbox"] = [76.0, 30.6, 76.07, 30.67]
    cfg["aoi"]["resolution_m"] = 100
    cfg["model"]["max_iter"] = 8
    cfg["evaluation"].update(top_n=2, bootstrap_replicates=20)
    return cfg


def item(ident="SCENE_A", date="2025-01-15T05:30:00Z"):
    return {"type": "Feature", "id": ident, "collection": "sentinel-2-l2a", "geometry": None,
            "properties": {"datetime": date, "eo:cloud_cover": 5.0},
            "assets": {b: {"href": f"https://example.test/{b}.tif", "type": "image/tiff", "raster:bands": [{"scale": .0001, "offset": -.1, "nodata": 0}]} for b in ("red", "nir", "scl")}}


class PreprocessingTests(unittest.TestCase):
    def test_ndvi_known_values_and_zero(self):
        out = ndvi(np.array([.1, .2, 0, -.1]), np.array([.5, .2, 0, .4]))
        np.testing.assert_allclose(out[:2], [2 / 3, 0], rtol=1e-6)
        self.assertTrue(np.isnan(out[2:]).all())

    def test_explicit_scale_offset_and_nodata(self):
        out = reflectance(np.array([0, 1500, 4000, 500]), .0001, -.1)
        np.testing.assert_allclose(out[1:3], [.05, .3], atol=1e-7)
        self.assertTrue(np.isnan(out[[0, 3]]).all())
        self.assertAlmostEqual(float(reflectance(np.array([.2]), 1, 0)[0]), .2, places=6)

    def test_asset_metadata_requires_explicit_scale(self):
        src = item()
        self.assertEqual(asset_metadata(src, "red")["offset"], -.1)
        del src["assets"]["red"]["raster:bands"]
        with self.assertRaisesRegex(ValueError, "scale missing"):
            asset_metadata(src, "red")

    def test_masked_array_invalid_stays_missing(self):
        arr = np.ma.array([2000, 3000], mask=[True, False])
        converted = reflectance(arr, .0001, 0)
        self.assertTrue(np.isnan(converted[0]))
        self.assertAlmostEqual(float(converted[1]), .3, places=6)

    def test_empty_cell_is_nan(self):
        means, counts = block_stats(np.array([[1, 1, 2]]), np.array([[.2, .4, np.nan]]), 2)
        np.testing.assert_allclose(means[0], .3)
        self.assertTrue(np.isnan(means[1]))
        self.assertEqual(counts.tolist(), [2, 0])

    def test_scene_keeps_cloudy_cells_and_rejects_water(self):
        cfg, src = config(), item()
        grid = make_grid(cfg)
        red, nir = np.full(grid.labels.shape, .1), np.full(grid.labels.shape, .4)
        scl = np.full(grid.labels.shape, 4)
        scl[grid.labels == 1] = 9
        scl[grid.labels == 2] = 6
        rows, arr = scene_rows(src, red, nir, scl, grid, cfg)
        self.assertEqual(len(rows), len(grid.ids))
        self.assertEqual(rows.iloc[0].valid_fraction, 0)
        self.assertTrue(np.isnan(rows.iloc[1].ndvi_mean))
        np.testing.assert_allclose(rows.iloc[2:].ndvi_mean, .6, rtol=1e-5)
        self.assertTrue(np.isnan(arr[grid.labels == 0]).all())

    def test_fixed_grid_raster_roundtrip(self):
        grid = make_grid(config())
        self.assertEqual(len(set(grid.ids)), len(grid.ids))
        self.assertEqual(int(grid.totals.sum()), int((grid.labels > 0).sum()))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ndvi.tif"
            arr = np.full(grid.labels.shape, .5, dtype="float32")
            arr[0, 0] = np.nan
            write_ndvi(path, arr, grid)
            with rasterio.open(path) as ds:
                self.assertEqual(ds.transform, grid.transform)
                self.assertEqual(ds.crs.to_epsg(), 32643)
                self.assertTrue(ds.read(1, masked=True).mask[0, 0])

    def test_local_rasters_load_on_one_grid(self):
        cfg, src = config(), item()
        grid = make_grid(cfg)
        with tempfile.TemporaryDirectory() as tmp:
            metas = {}
            for band, value in [("red", 1500), ("nir", 4000), ("scl", 4)]:
                p = Path(tmp) / f"{band}.tif"
                with rasterio.open(p, "w", driver="GTiff", height=grid.labels.shape[0], width=grid.labels.shape[1], count=1,
                                   dtype="uint16", crs=grid.crs, transform=grid.transform, nodata=0) as ds:
                    ds.write(np.full(grid.labels.shape, value, dtype="uint16"), 1)
                metas[band] = {"href": str(p), "scale": .0001, "offset": -.1, "nodata": 0}
            with patch("eoasset.ingest.asset_metadata", side_effect=lambda i, b: metas[b]):
                rows, arr, _ = load_scene(src, grid, cfg)
            np.testing.assert_allclose(rows.ndvi_mean, 5 / 7, rtol=1e-5)
            self.assertEqual(arr.shape, grid.labels.shape)


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config()
        self.grid = make_grid(self.cfg)
        self.scenes = make_scenes(self.cfg, self.grid)

    def test_complete_weeks_exclude_partial_ends(self):
        cfg = deepcopy(self.cfg)
        cfg["time"]["end"] = "2026-04-30"
        dates = complete_weeks(cfg)
        self.assertEqual(str(dates[0].date()), "2024-11-04")
        self.assertEqual(str(dates[-1].date()), "2026-04-20")

    def test_targets_and_seasonal_baseline_alignment(self):
        weekly = weekly_table(self.scenes, self.grid.ids, self.cfg)
        table = supervised(weekly)
        block = table[table.block_id == self.grid.ids[0]].reset_index(drop=True)
        self.assertAlmostEqual(block.iloc[55].seasonal, block.iloc[4].raw_ndvi)
        self.assertAlmostEqual(block.iloc[55].y, block.iloc[56].raw_ndvi)
        self.assertEqual((block.iloc[55].target_week - block.iloc[55].week).days, 7)

    def test_no_future_leakage_prefix_invariance(self):
        cutoff = pd.Timestamp("2025-02-02")
        before = self.scenes[pd.to_datetime(self.scenes.date) <= cutoff]
        full = supervised(weekly_table(self.scenes, self.grid.ids, self.cfg))
        short = supervised(weekly_table(before, self.grid.ids, self.cfg))
        mask = full.week <= cutoff - pd.Timedelta(days=6)
        pd.testing.assert_frame_equal(full.loc[mask, FEATURES], short.loc[mask, FEATURES])

    def test_gap_fill_uses_past_only_and_not_targets(self):
        d = self.scenes.copy()
        days = pd.to_datetime(d.date)
        d = d[~days.between("2025-01-06", "2025-01-26")]
        weekly = weekly_table(d, self.grid.ids, self.cfg)
        b = weekly[weekly.block_id == self.grid.ids[0]].set_index("week")
        self.assertTrue(b.loc["2025-01-06", "filled"])
        self.assertFalse(b.loc["2025-01-06", "observed"])
        self.assertTrue(np.isnan(b.loc["2025-01-13", "ndvi"]))
        table = supervised(weekly)
        target = table[table.target_week == "2025-01-06"]
        self.assertFalse(target.y_observed.any())
        self.assertTrue(target.y.isna().all())

    def test_low_coverage_excluded_and_all_missing_preserved(self):
        d = self.scenes.assign(valid_fraction=0.1)
        weekly = weekly_table(d, self.grid.ids, self.cfg)
        self.assertFalse(weekly.observed.any())
        self.assertTrue(weekly.ndvi.isna().all())
        self.assertEqual(weekly.block_id.nunique(), len(self.grid.ids))

    def test_same_day_dedup_prefers_coverage(self):
        d = self.scenes.head(1).copy()
        d["date"], d["valid_fraction"], d["ndvi_mean"] = "2025-01-07", .8, .4
        duplicate = d.assign(item_id="OTHER", valid_fraction=.5, ndvi_mean=.9)
        weekly = weekly_table(pd.concat([d, duplicate]), self.grid.ids, self.cfg)
        row = weekly[(weekly.week == "2025-01-06") & (weekly.block_id == d.iloc[0].block_id)].iloc[0]
        self.assertEqual(row.n_days, 1)
        self.assertAlmostEqual(row.raw_ndvi, .4)


class CatalogueTests(unittest.TestCase):
    def test_transaction_query_cache_corruption_and_export(self):
        cfg, src = config(), item()
        grid = make_grid(cfg)
        rows, arr = scene_rows(src, np.full(grid.labels.shape, .1), np.full(grid.labels.shape, .4),
                               np.full(grid.labels.shape, 4), grid, cfg)
        with tempfile.TemporaryDirectory() as tmp, Catalogue(tmp) as cat:
            p = Path(tmp) / "rasters" / "a.tif"
            write_ndvi(p, arr, grid)
            for _ in range(2):
                cat.commit_scene(src, source_hash(src), {}, cfg["aoi"]["bbox"], p, rows)
            self.assertEqual(len(cat.features([src["id"]])), len(grid.ids))
            self.assertTrue(cat.current(src["id"], source_hash(src)))
            self.assertEqual(len(cat.query("2025-01-01", "2025-01-31", cfg["aoi"]["bbox"])), 1)
            self.assertEqual(cat.query("2025-01-01", "2025-01-31", [0, 0, 1, 1]), [])
            self.assertEqual(cat.query("2026-01-01", "2026-01-31"), [])
            cat.export_stac(cfg)
            entry = next((Path(tmp) / "stac/items").glob("*.json"))
            content = json.loads(entry.read_text())
            self.assertTrue((entry.parent / content["assets"]["ndvi"]["href"]).resolve().is_file())
            p.write_bytes(b"corrupt")
            self.assertFalse(cat.current(src["id"], source_hash(src)))

    def test_failed_scene_retried_and_trial_idempotent(self):
        cfg, src = config(), item()
        grid = make_grid(cfg)
        rows, arr = scene_rows(src, np.full(grid.labels.shape, .1), np.full(grid.labels.shape, .4), np.full(grid.labels.shape, 4), grid, cfg)
        with tempfile.TemporaryDirectory() as tmp, Catalogue(tmp) as cat:
            with patch("eoasset.ingest.search_items", return_value=[src]), patch("eoasset.ingest.load_scene", side_effect=RuntimeError("temporary failure")):
                _, stats, _ = ingest(cfg, grid, cat, 1)
            self.assertEqual(len(stats["failed"]), 1)
            self.assertEqual(cat.query("2024-01-01", "2026-01-01"), [])
            with patch("eoasset.ingest.search_items", return_value=[src]), patch("eoasset.ingest.load_scene", return_value=(rows, arr, {})) as loader:
                ingest(cfg, grid, cat, 1)
                _, again, _ = ingest(cfg, grid, cat, 1)
            self.assertEqual(loader.call_count, 1)
            self.assertEqual(again["cached"], 1)

    def test_discovery_sort_cap_and_pagination(self):
        cfg = config()
        pages = [{"features": [item("Z", "2025-02-01T00:00:00Z")], "links": [{"rel": "next", "href": "https://example.test/next"}]},
                 {"features": [item("A", "2025-01-01T00:00:00Z")], "links": []}]
        with patch("eoasset.ingest.request_json", side_effect=pages):
            found = search_items(cfg, 1)
        self.assertEqual([i["id"] for i in found], ["A"])

    def test_cache_fingerprint_changes_with_preprocessing_not_dates(self):
        a, b = config(), config()
        b["time"]["end"] = "2026-05-03"
        self.assertEqual(processing_hash(a), processing_hash(b))
        b["quality"]["scl_keep"] = [4]
        self.assertNotEqual(processing_hash(a), processing_hash(b))

    def test_exclusive_cache_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            with cache_lock(tmp):
                with self.assertRaises(RuntimeError):
                    with cache_lock(tmp):
                        pass
            self.assertFalse((Path(tmp) / "writer.lock").exists())


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = config()
        cls.grid = make_grid(cls.cfg)
        cls.weekly = weekly_table(make_scenes(cls.cfg, cls.grid), cls.grid.ids, cls.cfg)
        cls.table = supervised(cls.weekly)
        cls.result = run_model(cls.table, cls.cfg)

    def test_chronological_split_and_observed_targets(self):
        metrics, test, forecast, _, _ = self.result
        self.assertTrue(test.y_observed.all())
        self.assertGreaterEqual(test.target_week.min(), pd.Timestamp(self.cfg["split"]["test_start"]))
        self.assertLess(metrics["training"]["target_end"], metrics["test_start"])
        self.assertEqual(len(forecast), len(self.grid.ids))
        self.assertTrue(np.isfinite(metrics["primary"]["model"]["mae"]))

    def test_missing_seasonal_values_do_not_drop_primary_rows(self):
        _, test, _, _, _ = self.result
        test = test.assign(seasonal=np.nan)
        metrics = evaluate(test, self.cfg, len(test))
        self.assertEqual(metrics["n_test_rows"], len(test))
        self.assertEqual(metrics["seasonal_common_sample"]["n"], 0)

    def test_zero_error_baseline_skill_undefined(self):
        self.assertIsNone(skill(0, 0))
        self.assertEqual(skill(.2, .1), -1)

    def test_ranking_excludes_filled_lags_and_reports_small_sample(self):
        frame = pd.DataFrame({"target_week": pd.Timestamp("2025-01-06"), "block_id": ["A", "B", "C", "D", "E"],
                              "history_observed": [True, True, True, True, False],
                              "y": [.1, .2, .3, .4, 0], "model": [.2, .1, .4, .3, -1]})
        result = ranking(frame, "model", 2)
        self.assertEqual(result["mean_overlap"], 1.0)
        self.assertEqual(result["n_weeks"], 1)
        result = ranking(frame.iloc[:3], "model", 2)
        self.assertIsNone(result["mean_overlap"])
        self.assertEqual(result["n_weeks"], 0)

    def test_no_current_observations_means_no_forecast(self):
        table = self.table.copy()
        latest = table.week == table.week.max()
        table.loc[latest, ["feature_ready", "observed"]] = False
        table.loc[latest, "raw_ndvi"] = np.nan
        _, _, forecast, _, _ = run_model(table, self.cfg)
        self.assertTrue(forecast.prediction.isna().all())
        self.assertFalse(forecast.shortlisted.any())

    def test_too_little_data_fails(self):
        with self.assertRaisesRegex(ValueError, "Insufficient training"):
            run_model(self.table[self.table.week >= "2026-01-01"], self.cfg)

    def test_bad_config_overlap_fails(self):
        cfg = deepcopy(self.cfg)
        cfg["split"]["test_start"] = cfg["split"]["train_end"]
        with self.assertRaises(ValueError):
            validate(cfg)


class IntegrationTests(unittest.TestCase):
    def test_offline_output_contract_and_manifest(self):
        cfg = config()
        with tempfile.TemporaryDirectory() as tmp:
            output = run(cfg, tmp, offline=True, make_figures=True)
            manifest = json.loads((output / "manifest.json").read_text())
            metrics = json.loads((output / "metrics.json").read_text())
            signals = json.loads((output / "block_signals.geojson").read_text())
            self.assertEqual(metrics["data_mode"], "synthetic")
            self.assertTrue((Path(tmp) / "outputs/demo/latest.json").exists())
            for name, meta in manifest["outputs"].items():
                self.assertEqual(file_hash(output / name), meta["sha256"])
            self.assertEqual(len({f["properties"]["block_id"] for f in signals["features"]}), len(signals["features"]))
            html = (output / "dashboard.html").read_text(encoding="utf-8")
            self.assertIn("SYNTHETIC DEMONSTRATION", html)
            self.assertNotIn("__DATA_JSON__", html)
            self.assertNotIn('<script src=', html)
            self.assertEqual(len(list((output / "figures").glob("*.png"))), 3)

    def test_strict_json_nulls(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "values.json"
            write_json(path, {"nan": np.nan, "inf": np.inf, "value": np.int64(3)})
            self.assertEqual(json.loads(path.read_text()), {"nan": None, "inf": None, "value": 3})


if __name__ == "__main__":
    unittest.main()
