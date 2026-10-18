"""Run the teacher harness repeatedly, checkpoint results, and retain real outputs."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from evaluation_harness import DEFAULT_BEDROCK_MODEL_ID, OFFER_TEST_CASES, RAGEvaluator, RAGTestCase
from rag_index import write_json
from rag_pipeline import OfferPipeline

METRICS = ["faithfulness", "answer_relevancy", "context_recall"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategies", nargs="+", default=["A", "B", "C", "CB"])
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--generate-only", action="store_true")
    args = parser.parse_args()
    out = REPO / "docs/lab3-evidence"
    phases = out / "rag-runs"
    phases.mkdir(parents=True, exist_ok=True)
    for strategy in args.strategies:
        checkpoints=[phases / f"scores-{strategy}-{repeat}.csv" for repeat in range(1,args.repetitions+1)]
        if not args.generate_only and (phases / f"offers-{strategy}.json").exists() and all(
            path.exists() and len(pd.read_csv(path))==4 and pd.read_csv(path)[METRICS].notna().all().all()
            for path in checkpoints):
            print(f"Keeping completed {strategy} outputs and score checkpoints unchanged",flush=True)
            continue
        pipeline = OfferPipeline(strategy.split("_")[0],
                                 prompt_variant="controlled" if strategy.endswith("_controlled") else
                                 "hardened" if strategy.endswith("_hardened") else "base")
        cases = [RAGTestCase(t.customer_id,dict(t.customer_context,customer_id=t.customer_id),
                             t.question,t.ground_truth) for t in OFFER_TEST_CASES]
        generated = []
        for case in cases:
            result = pipeline(case.customer_context,case.question)
            generated.append(result)
            print(f"{strategy} {case.customer_id}: {result['answer']}",flush=True)
        write_json(phases / f"offers-{strategy}.json",generated)
        if args.generate_only:
            continue
        for repeat in range(1,args.repetitions+1):
            target = phases / f"scores-{strategy}-{repeat}.csv"
            if target.exists():
                previous = pd.read_csv(target)
                if len(previous)==4 and previous[METRICS].notna().all().all():
                    print(f"Using completed checkpoint {target.name}",flush=True)
                    continue
            evaluator = RAGEvaluator(pipeline,DEFAULT_BEDROCK_MODEL_ID)
            frame = evaluator.run(cases)
            frame["customer_id"]=[c.customer_id for c in cases]
            # Retry failed cases only; NaN is a failed judge call, never a zero.
            for attempt in range(2):
                bad = frame[METRICS].isna().any(axis=1)
                if not bad.any():
                    break
                frame.loc[bad].to_csv(phases / f"failed-{strategy}-{repeat}-{attempt}.csv",index=False)
                indices = np.flatnonzero(bad.to_numpy())
                rerun = evaluator.run([cases[i] for i in indices])
                for offset,index in enumerate(indices):
                    for metric in METRICS:
                        frame.loc[index,metric]=rerun.iloc[offset][metric]
            if frame[METRICS].isna().any().any():
                raise RuntimeError("Judge failures remain; resume after fixing them")
            frame["strategy"],frame["repeat"] = strategy,repeat
            frame["judge_model"] = DEFAULT_BEDROCK_MODEL_ID
            frame["generator_model"] = pipeline.model_id
            frame["evaluated_at_utc"] = datetime.now(timezone.utc).isoformat()
            frame.to_csv(target,index=False)
            print(f"SAVED {target.name}: {frame[METRICS].mean().to_dict()}",flush=True)
            all_frames = [pd.read_csv(p) for p in sorted(phases.glob("scores-*.csv"))]
            pd.concat(all_frames,ignore_index=True).to_csv(out / "rag_eval.csv",index=False)
    if not args.generate_only:
        all_scores = pd.read_csv(out / "rag_eval.csv")
        summary = all_scores.groupby("strategy")[METRICS].agg(["mean","min","max"])
        summary.to_csv(out / "rag_eval_summary.csv")
        print(summary.to_string(),flush=True)


if __name__ == "__main__":
    main()
