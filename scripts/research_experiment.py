"""Run the fixed candidate study on earlier-season data only. Never scores later-season targets."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import joblib
import pandas as pd
from eoasset.config import load_config
from eoasset.features import supervised
from eoasset.selection import select_candidate, fit_candidate, CANDIDATES
from eoasset.util import code_hash, environment, file_hash

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weekly", type=Path, required=True)
    args = parser.parse_args()
    cfg = load_config(ROOT / "config.json")
    cfg["model"]["candidate_pool"] = "research"
    weekly = pd.read_csv(args.weekly, parse_dates=["week"])
    # Truncate before even constructing targets; future values cannot affect selection.
    weekly = weekly[weekly.week <= pd.Timestamp(cfg["split"]["train_end"])]
    table = supervised(weekly)
    train = table[table.feature_ready & table.y_observed & table.y.notna() &
                  table.target_week.between(cfg["split"]["train_start"], cfg["split"]["train_end"])]
    out = ROOT / "outputs/research" / ("experiment_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    # A freshly extracted submission has no outputs/research directory yet.
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    chosen, selection = select_candidate(train, cfg)
    for kind in CANDIDATES:
        joblib.dump(fit_candidate(train,cfg,kind), out / (kind+".joblib"))
    result = {"selection":selection, "training_rows":len(train), "config":cfg,
              "source_weekly":str(args.weekly.resolve()), "source_sha256":file_hash(args.weekly),
              "code_hash":code_hash(), "environment":environment(),
              "elapsed_seconds":time.perf_counter()-started,
              "scope":"Earlier-season selection only. No later-season candidate scoring."}
    (out/"experiment.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(out)
    print(json.dumps(selection["candidate_scores"],indent=2))
    print("Selected:",chosen)

if __name__ == "__main__":
    main()
