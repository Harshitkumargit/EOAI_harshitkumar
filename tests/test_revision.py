"""Regression checks for missing-history support, transport retries and selection separation."""
import unittest
import tempfile
from unittest.mock import patch
import joblib
import numpy as np
import pandas as pd
from test_project import config
from eoasset.features import supervised, FEATURES
from eoasset.ingest import _transient_raster_error
from eoasset.selection import select_candidate, fit_candidate
from eoasset.config import processing_hash
from eoasset.util import file_hash

class RevisionTests(unittest.TestCase):
    def test_recent_level_blend_and_missing_trend(self):
        cfg=config()
        d=pd.DataFrame({f:[0.,0.] for f in FEATURES})
        d["lag0"]=[.2,.6];d["lag1"]=[.6,np.nan];d["lag2"]=[.6,np.nan];d["lag3"]=[.6,np.nan]
        d["y"]=[.5,.6]
        m=fit_candidate(d,cfg,"median_25")
        np.testing.assert_allclose(m.predict(d[FEATURES]),[.3,.6])
        np.testing.assert_allclose(fit_candidate(d,cfg,"trend_25").predict(d[FEATURES]),[.1,.6])
        with self.assertRaises(ValueError):fit_candidate(d,cfg,"unknown")

    def test_ridge_scaler_is_fit_only_on_supplied_rows_and_roundtrips(self):
        cfg=config(); d=pd.DataFrame({f:np.zeros(40) for f in FEATURES})
        d["lag0"]=np.linspace(.2,.5,40);d["lag1"]=np.nan;d["y"]=d.lag0+.01
        m=fit_candidate(d,cfg,"ridge_100")
        before=m.estimator[0].mean_.copy()
        future=d.copy();future["lag0"]=.9
        self.assertTrue(np.isfinite(m.predict(future[FEATURES])).all())
        np.testing.assert_array_equal(before,m.estimator[0].mean_)
        with tempfile.TemporaryDirectory() as tmp:
            p=tmp+'/ridge.joblib';joblib.dump(m,p)
            np.testing.assert_allclose(m.predict(d[FEATURES]),joblib.load(p).predict(d[FEATURES]))

    def test_transport_only_hash_alias_is_exact_and_future_edits_invalidate(self):
        cfg = config()
        current = processing_hash(cfg)
        def legacy(path):
            return "55721f41462ac6394a57880714477f1d09eb1f285a1586450b7d90ae6545cc09" if path.name == "ingest.py" else file_hash(path)
        with patch("eoasset.config.file_hash", side_effect=legacy):
            self.assertEqual(current, processing_hash(cfg))
        def future(path):
            return "future-unreviewed-implementation" if path.name == "ingest.py" else file_hash(path)
        with patch("eoasset.config.file_hash", side_effect=future):
            self.assertNotEqual(current, processing_hash(cfg))

    def test_both_boosting_candidates_accept_missing_historical_inputs(self):
        cfg = config()
        d = pd.DataFrame({f: np.zeros(60) for f in FEATURES})
        d["lag0"] = np.linspace(.2, .6, 60)
        d["y"] = d.lag0 + .02
        d.loc[::2, ["lag1", "lag2", "lag3", "delta1", "roll4"]] = np.nan
        for kind in ("direct", "residual"):
            m = fit_candidate(d, cfg, kind)
            self.assertTrue(np.isfinite(m.predict(d[FEATURES])).all())

    def test_missing_past_keeps_observed_origin_but_not_shortlist_history(self):
        w = pd.DataFrame({"block_id":["A"]*5,"week":pd.date_range("2025-01-06",periods=5,freq="W-MON"),
            "raw_ndvi":[.2,np.nan,np.nan,.4,.5],"ndvi":[.2,.2,np.nan,.4,.5],
            "observed":[True,False,False,True,True],"valid_fraction":[.8,0,0,.8,.8],"n_days":[1,0,0,1,1]})
        d=supervised(w)
        self.assertTrue(d.iloc[3].feature_ready)
        self.assertFalse(d.iloc[3].history_observed)
        self.assertAlmostEqual(d.iloc[3].y,.5)
        self.assertFalse(d.iloc[2].feature_ready)

    def test_nested_network_and_generic_read_errors_retry_but_metadata_does_not(self):
        e=RuntimeError("outer");e.__cause__=OSError("CURL error: Could not resolve host: example")
        self.assertTrue(_transient_raster_error(e))
        self.assertTrue(_transient_raster_error(RuntimeError("Read failed. See previous exception for details.")))
        self.assertFalse(_transient_raster_error(ValueError("explicit scale missing")))
        e.__cause__=e
        self.assertFalse(_transient_raster_error(e))

    def test_selection_uses_past_folds_and_persistence_roundtrip(self):
        cfg=config(); cfg["model"]["min_train_rows"]=4
        weeks=pd.date_range("2024-11-04",periods=24,freq="W-MON")
        d=pd.DataFrame({f:np.zeros(48) for f in FEATURES})
        d["lag0"]=.4; d["y"]=.4
        d["target_week"]=np.repeat(weeks,2)
        kind, audit=select_candidate(d,cfg)
        self.assertEqual(kind,"persistence")
        self.assertTrue(audit["folds"])
        for fold in audit["folds"]:
            self.assertLess(pd.Timestamp(fold["train_end"])+pd.Timedelta(days=7),pd.Timestamp(fold["validation_start"]))
        m=fit_candidate(d,cfg,kind)
        with tempfile.TemporaryDirectory() as tmp:
            p=tmp+"/model.joblib";joblib.dump(m,p)
            np.testing.assert_allclose(joblib.load(p).predict(d[FEATURES]),.4)

if __name__=="__main__": unittest.main()

