"""Compare saved runs on identical observations; no fitting or downloads."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

def compare(baseline, revised):
    a = pd.read_csv(Path(baseline)/"test_predictions.csv")
    b = pd.read_csv(Path(revised)/"test_predictions.csv")
    keys = ["block_id", "target_week"]
    common = a.merge(b, on=keys, suffixes=("_old", "_new"), validate="one_to_one")
    if common.empty or not np.allclose(common.y_old, common.y_new):
        raise ValueError("Comparison requires shared identical observed targets.")
    def score(pred, truth):
        return {"mae":float(abs(pred-truth).mean()),"rmse":float(np.sqrt(((pred-truth)**2).mean()))}
    return {"baseline":str(baseline),"revised":str(revised),
        "original_rows":len(a),"revised_rows":len(b),"common_rows":len(common),
        "same_sample":{"original":score(common.model_old,common.y_old),
                       "revised":score(common.model_new,common.y_new),
                       "persistence":score(common.persist_new,common.y_new)},
        "note":"Expanded-sample MAE cannot be directly compared to original-sample MAE."}

if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("baseline",type=Path);p.add_argument("revised",type=Path)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    result=json.dumps(compare(a.baseline,a.revised),indent=2)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(result+"\n",encoding="utf-8")
    print(result)

