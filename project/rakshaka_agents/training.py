"""Train every learned component and build the agent team.

Learned parts: language model, content model, campaign index, drift threshold, arbiter stacker.
The stacker is trained on out-of-fold specialist outputs (GroupKFold by template), so it learns
how far to trust each agent on wording it has not seen, not on its own training data.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import normalize as l2

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parent
sys.path.insert(0, str(ROOT))
from rakshaka.modeling import char_ngram_oov_ratio, make_classifier, preprocess_text  # noqa: E402  (pre-existing)

from .agents import (CampaignAgent, ContentAgent, DriftAgent, IntakeAgent, LanguageAgent,  # noqa: E402
                     LinkSenderAgent, TacticsAgent)
from .blackboard import Blackboard  # noqa: E402
from .decision import ArbiterAgent, ExplainerAgent, feature_vector  # noqa: E402

DATA, MODELS = ROOT / "data", PROJECT / "models"
BLOCKLIST = PROJECT / "runtime" / "blocklist.txt"


def load_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("text") and r.get("label")]
    for i, row in enumerate(rows):
        row.setdefault("group_id", f"{path.stem}-{i}")
        row["group_id"] = row.get("group_id") or f"{path.stem}-{i}"
        row["language"] = row.get("language") or "unknown"
    return rows


def ensure_data() -> None:
    if not (DATA / "train.csv").exists():
        subprocess.run([sys.executable, str(ROOT / "src" / "make_data.py")], check=True, cwd=ROOT)


def fit_language(rows):
    latin = [r for r in rows if r["language"] in ("english", "singlish", "tanglish")]
    model = make_pipeline(TfidfVectorizer(analyzer="char_wb", ngram_range=(1, 4), sublinear_tf=True, min_df=2),
                          LogisticRegression(max_iter=2000, class_weight="balanced"))
    return model.fit([r["text"].casefold() for r in latin], [r["language"] for r in latin])


def fit_content(rows):
    return make_classifier(class_weight="balanced").fit([preprocess_text(r["text"]) for r in rows],
                                                        [r["label"] for r in rows])


def fit_campaign(rows):
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=2)
    X = vec.fit_transform([r["text"].casefold() for r in rows])
    centroids, names = {"scam": [], "legitimate": []}, []
    groups = sorted({(r["label"], r["group_id"]) for r in rows})
    for label, group in groups:
        idx = [i for i, r in enumerate(rows) if r["group_id"] == group]
        centroids[label].append(np.asarray(X[idx].mean(axis=0)).ravel())
        if label == "scam":
            names.append(group)
    return vec, l2(np.vstack(centroids["scam"])), names, l2(np.vstack(centroids["legitimate"]))


def specialists(content_model, campaign_parts, language_model, drift_threshold=0.3):
    return {
        "intake": IntakeAgent(),
        "language": LanguageAgent(language_model),
        "content": ContentAgent(content_model, preprocess_text),
        "tactics": TacticsAgent(),
        "link_sender": LinkSenderAgent(load_blocklist()),
        "campaign": CampaignAgent(*campaign_parts),
        "drift": DriftAgent(char_ngram_oov_ratio, content_model, drift_threshold),
    }


def run_specialists(team, text, sender=None):
    board = Blackboard(text, sender=sender)
    board.post(team["intake"].run(board))
    board.post(team["language"].run(board))
    for name in ("content", "tactics", "link_sender", "campaign", "drift"):
        board.post(team[name].run(board))
    return board


def load_blocklist() -> set[str]:
    if BLOCKLIST.exists():
        return {line.strip().lower() for line in BLOCKLIST.read_text(encoding="utf-8").splitlines() if line.strip()}
    return set()


REVIEWED = PROJECT / "runtime" / "reviewed.csv"


def train(seed: int = 42, out_dir: Path | None = None, use_reviewed: bool = True) -> dict:
    """Train every learned agent. Human-reviewed labels (runtime/reviewed.csv) join the training set."""
    ensure_data()
    out_dir = out_dir or MODELS
    train_rows = load_rows(DATA / "train.csv")
    n_reviewed = 0
    if use_reviewed and REVIEWED.exists():
        reviewed = load_rows(REVIEWED)
        for i, row in enumerate(reviewed):
            row["group_id"] = f"reviewed-{i}"
        n_reviewed = len(reviewed)
        train_rows += reviewed
    val_rows = load_rows(DATA / "val.csv")
    language_model = fit_language(train_rows)
    content_model = fit_content(train_rows)
    campaign_parts = fit_campaign(train_rows)

    oov_val = [char_ngram_oov_ratio(content_model, r["text"]) for r in val_rows]
    drift_threshold = float(np.percentile(oov_val, 90))

    # out-of-fold specialist outputs for the stacker
    X, y = [], []
    groups = [r["group_id"] for r in train_rows]
    for fold_train, fold_test in GroupKFold(n_splits=5).split(train_rows, groups=groups):
        part = [train_rows[i] for i in fold_train]
        team = specialists(fit_content(part), fit_campaign(part), language_model, drift_threshold)
        for i in fold_test:
            X.append(feature_vector(run_specialists(team, train_rows[i]["text"])))
            y.append(int(train_rows[i]["label"] == "scam"))
    full_team = specialists(content_model, campaign_parts, language_model, drift_threshold)
    for r in val_rows:
        X.append(feature_vector(run_specialists(full_team, r["text"])))
        y.append(int(r["label"] == "scam"))
    stacker = LogisticRegression(max_iter=2000, class_weight="balanced").fit(X, y)

    out_dir.mkdir(parents=True, exist_ok=True)
    old = MODELS / "meta.json"
    previous = json.loads(old.read_text(encoding="utf-8")).get("version", "v0") if old.exists() else "v0"
    meta = {"version": f"v{int(previous[1:]) + 1}",
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_train": len(train_rows), "n_reviewed": n_reviewed, "n_val": len(val_rows), "n_stacker_rows": len(X),
            "drift_threshold": drift_threshold,
            "stacker_coef": dict(zip(["content", "content_missing", "tactics", "tactics_missing", "campaign", "campaign_missing", "oov"],
                                     [round(float(c), 3) for c in stacker.coef_[0]]))}
    joblib.dump({"language": language_model, "content": content_model, "campaign": campaign_parts,
                 "stacker": stacker, "meta": meta}, out_dir / "agents.joblib")
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def build_team(llm=None) -> dict:
    path = MODELS / "agents.joblib"
    if not path.exists():
        train()
    bundle = joblib.load(path)
    team = specialists(bundle["content"], bundle["campaign"], bundle["language"], bundle["meta"]["drift_threshold"])
    team["arbiter"] = ArbiterAgent(bundle["stacker"])
    team["explainer"] = ExplainerAgent(llm=llm)
    return team


def load_content_model():
    path = MODELS / "agents.joblib"
    if not path.exists():
        train()
    return joblib.load(path)["content"]
