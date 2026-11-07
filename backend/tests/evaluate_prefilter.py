"""
How well does the local pre-filter work? (no API calls, no Neo4j, ~1 minute)

  python tests/evaluate_prefilter.py
  python tests/evaluate_prefilter.py --show     # also list every decision with its reasons

Honest test: the classifier is never scored on a conversation it was trained on.
5-fold cross-validation, repeated with 5 different splits. In each fold the threshold is ALSO
chosen only from the training part (exactly what train_prefilter.py does), then applied to the
held-out conversations. Reported numbers are averages over the 5 splits, plus the worst split.

The one number that must stay 0: useful conversations skipped (that knowledge would be lost).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # make "pipeline" importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))  # reuse train_prefilter settings

import numpy as np
from sklearn.model_selection import StratifiedKFold

from pipeline.prefilter import MIN_SCORE, Prefilter
from pipeline.prefilter_data import load_examples
from train_prefilter import CV_REPEATS, choose_threshold, make_model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    examples, missing = load_examples()
    if missing:
        print(f"(No cached Gemini decision for {missing}; left out.)")
    pf = Prefilter(use_classifier=False)
    threads_ = [t for t, _, _ in examples]
    labels = np.array([y for _, y, _ in examples])
    texts = np.array([Prefilter.model_text(t) for t in threads_])
    scored = [pf.score(t) for t in threads_]
    rule_keep = np.array([s >= MIN_SCORE for s, _ in scored])
    n, n_useful = len(labels), int(labels.sum())
    n_noise = n - n_useful

    print(f"Conversations: {n}  ({n_useful} useful, {n_noise} noise; labels = Gemini's past decisions + template noise)\n")

    # ---- Layer 1: rules (deterministic) ----
    rule_lost = int((~rule_keep & (labels == 1)).sum())
    rule_skipped_noise = int((~rule_keep & (labels == 0)).sum())
    print("LAYER 1 - rule score (keep if score >= %d)" % MIN_SCORE)
    print(f"  noise skipped        : {rule_skipped_noise}/{n_noise}")
    print(f"  useful skipped (LOST): {rule_lost}/{n_useful}")
    low = sorted((scored[i][0], threads_[i]["thread_id"]) for i in range(n) if labels[i] == 1)[:3]
    print(f"  lowest-scoring useful conversations: {', '.join(f'{tid}={s}' for s, tid in low)}\n")

    # ---- Layer 2: classifier, honest cross-validation ----
    skipped_noise_runs, lost_runs, thresholds = [], [], []
    clf_skip_ids: dict[str, int] = {}
    for seed in range(CV_REPEATS):
        clf_skip = np.zeros(n, dtype=bool)
        folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=100 + seed)
        for train, test in folds.split(texts, labels):
            thr = choose_threshold(list(texts[train]), labels[train])
            thresholds.append(thr)
            model = make_model().fit(list(texts[train]), labels[train])
            p = model.predict_proba(list(texts[test]))[:, 1]
            clf_skip[test] = p < thr
        clf_skip &= rule_keep                      # the classifier only sees what the rules let through
        skipped_noise_runs.append(int((clf_skip & (labels == 0)).sum()))
        lost_runs.append(int((clf_skip & (labels == 1)).sum()))
        for i in np.where(clf_skip)[0]:
            clf_skip_ids[threads_[i]["thread_id"]] = clf_skip_ids.get(threads_[i]["thread_id"], 0) + 1

    passed_noise = int((rule_keep & (labels == 0)).sum())
    print(f"LAYER 2 - classifier on the {int(rule_keep.sum())} conversations the rules kept "
          f"({passed_noise} of them noise)")
    print(f"  thresholds chosen per fold: {min(thresholds):.3f} - {max(thresholds):.3f}")
    print(f"  noise skipped        : avg {np.mean(skipped_noise_runs):.1f}/{passed_noise}, "
          f"worst split {min(skipped_noise_runs)}/{passed_noise}")
    print(f"  useful skipped (LOST): avg {np.mean(lost_runs):.1f}/{n_useful}, worst split {max(lost_runs)}/{n_useful}\n")

    # ---- Funnel ----
    total_skipped = rule_skipped_noise + np.mean(skipped_noise_runs)
    sent = n - rule_lost - rule_skipped_noise - np.mean(skipped_noise_runs) - np.mean(lost_runs)
    print("FUNNEL (what would be sent to Gemini)")
    print(f"  without pre-filter : {n} Gemini calls, {n_noise} of them wasted on noise")
    print(f"  with pre-filter    : {sent:.0f} Gemini calls  ->  {total_skipped:.0f}/{n_noise} noise never sent "
          f"({100 * total_skipped / n_noise:.0f}%), {rule_lost + max(lost_runs)} useful lost (worst case)")
    print("\nCaveat: small dataset and template-generated noise, so this shows the mechanism works;\n"
          "the real accuracy has to be measured on real Elisa conversations (retrain with their labels).")

    if args.show:
        print("\nDecisions:")
        for i in range(n):
            s, reasons = scored[i]
            tid = threads_[i]["thread_id"]
            stage = "rules: skip" if not rule_keep[i] else (
                f"classifier: skip in {clf_skip_ids[tid]}/{CV_REPEATS} splits" if tid in clf_skip_ids else "sent to Gemini")
            print(f"  {tid:6} {'useful' if labels[i] else 'noise ':6} score={s:2}  {stage:32} {'; '.join(reasons)[:110]}")

    if rule_lost or max(lost_runs):
        print("\nWARNING: useful conversations would be skipped - lower MIN_SCORE or SAFETY_MARGIN.")
        sys.exit(1)


if __name__ == "__main__":
    main()
