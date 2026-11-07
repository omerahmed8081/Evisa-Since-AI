"""
Train the pre-filter's small local classifier (seconds, no GPU, no API calls).

  python scripts/train_prefilter.py

- Labels: Gemini's past useful/noise decisions from cache/extract (distillation) + template noise
  (data/noise_threads, create with: python data/generator/noise.py).
- Model: TF-IDF over 2-4 character snippets + logistic regression (scikit-learn), C=10
  (chosen by cross-validation; the default C=1 squeezes all probabilities together on small data).
- Threshold: 5-fold cross-validation repeated with 5 different splits; take the LOWEST probability
  any useful conversation got in any split, and use 80% of it. So no useful conversation would have
  been skipped even in the worst split. Saved to models/prefilter.joblib together with the model.
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # make "pipeline" importable

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline

from pipeline.prefilter import MODEL_PATH, Prefilter
from pipeline.prefilter_data import load_examples

SAFETY_MARGIN = 0.8      # threshold = margin x lowest cross-validated probability of a useful conversation
MAX_THRESHOLD = 0.5
CV_REPEATS = 5


def make_model():
    return make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True, min_df=1),
        LogisticRegression(class_weight="balanced", max_iter=3000, C=10.0),
    )


def cross_validated_probabilities(texts, labels, repeats: int = CV_REPEATS):
    """Out-of-fold probabilities for several different splits: array (repeats, n).
    Every conversation is scored by a model that never saw it during training."""
    runs = []
    for seed in range(repeats):
        folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
        runs.append(cross_val_predict(make_model(), texts, labels, cv=folds, method="predict_proba")[:, 1])
    return np.array(runs)


def choose_threshold(texts, labels) -> float:
    """80% of the lowest probability any useful conversation got in repeated cross-validation."""
    runs = cross_validated_probabilities(texts, labels)
    return round(min(MAX_THRESHOLD, SAFETY_MARGIN * float(runs[:, labels == 1].min())), 3)


def main():
    examples, missing = load_examples()
    if missing:
        print(f"No cached Gemini decision for {missing} (run ingest first); they are left out.")
    texts = [Prefilter.model_text(t) for t, _, _ in examples]
    labels = np.array([y for _, y, _ in examples])
    n_gemini = sum(1 for _, _, s in examples if s == "gemini")
    print(f"Training examples: {len(examples)} ({n_gemini} with Gemini labels, "
          f"{len(examples) - n_gemini} template noise) -> {labels.sum()} useful, {len(labels) - labels.sum()} noise")

    runs = cross_validated_probabilities(texts, labels)
    lowest_useful = float(runs[:, labels == 1].min())
    threshold = round(min(MAX_THRESHOLD, SAFETY_MARGIN * lowest_useful), 3)
    worst_noise = runs.max(axis=0)   # noise counted as skipped only if skipped in EVERY split
    print(f"Cross-validated ({CV_REPEATS} splits): lowest probability of a useful conversation = {lowest_useful:.3f}")
    print(f"Threshold = {threshold} -> useful wrongly skipped: 0, "
          f"noise skipped in every split: {int(((worst_noise < threshold) & (labels == 0)).sum())}/{int((labels == 0).sum())}")

    model = make_model().fit(texts, labels)
    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump({"pipeline": model, "threshold": threshold, "trained_at": datetime.now().isoformat(timespec="seconds"),
                 "n_examples": len(examples), "n_useful": int(labels.sum())}, MODEL_PATH)
    print(f"Saved {MODEL_PATH} ({MODEL_PATH.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
