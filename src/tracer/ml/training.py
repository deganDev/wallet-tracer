from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path
from typing import Dict, Tuple

from tracer.adapters.risk.dexscreener_adapter import DexScreenerAdapter
from tracer.core.models import Edge, Graph, Node
from tracer.core.enums import TokenRiskLabel
from tracer.ml.token_features import token_features_from_analysis, token_features_from_risk
from tracer.ml.wallet_features import wallet_features_from_graph


def _label_to_int(raw: str) -> int:
    val = (raw or "").strip().lower()
    if val in {"1", "true", "yes", "scam", "malicious"}:
        return 1
    return 0


def _dec(val: str | None) -> Decimal | None:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except Exception:
        return None


def _load_graph(path: str) -> Graph:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    nodes = {}
    for n in data.get("nodes", []):
        addr = (n.get("address") or "").lower()
        if not addr:
            continue
        nodes[addr] = Node(address=addr, is_contract=bool(n.get("is_contract")))

    edges = []
    for e in data.get("edges", []):
        edges.append(
            Edge(
                from_address=str(e.get("from") or "").lower(),
                to_address=str(e.get("to") or "").lower(),
                tx_hash=str(e.get("tx_hash") or ""),
                timestamp=int(e.get("timestamp") or 0),
                asset_type=str(e.get("asset_type") or ""),
                token_address=(str(e.get("token_address") or "").lower() or None),
                symbol=e.get("symbol"),
                amount=_dec(e.get("amount")) or Decimal("0"),
                usd_value=_dec(e.get("usd_value")),
            )
        )

    return Graph(nodes=nodes, edges=edges)


def build_token_dataset(input_csv: str, output_csv: str) -> None:
    adapter = DexScreenerAdapter()
    rows_out = []

    with open(input_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            token = (row.get("token_address") or "").strip()
            if not token:
                continue
            label = _label_to_int(row.get("label", "0"))
            analysis = adapter.analyze_token(token)
            features = token_features_from_analysis(analysis)
            features["label"] = label
            features["token_address"] = token.lower()
            rows_out.append(features)

    if not rows_out:
        raise SystemExit("No rows generated. Check input CSV.")

    fieldnames = list(rows_out[0].keys())
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)


def build_token_labels_from_graph(graph: Graph, output_csv: str) -> None:
    rows_out = []
    for token in graph.tokens.values():
        label = 1 if token.label in {TokenRiskLabel.SCAM_CONFIRMED, TokenRiskLabel.HIGH_RISK} else 0
        rows_out.append({"token_address": token.token_address, "label": label})

    if not rows_out:
        return
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["token_address", "label"])
        writer.writeheader()
        writer.writerows(rows_out)


def build_token_dataset_from_graph(graph: Graph, output_csv: str) -> None:
    rows_out = []
    for token in graph.tokens.values():
        label = 1 if token.label in {TokenRiskLabel.SCAM_CONFIRMED, TokenRiskLabel.HIGH_RISK} else 0
        features = token_features_from_risk(token)
        features["label"] = label
        features["token_address"] = token.token_address
        rows_out.append(features)

    if not rows_out:
        return
    fieldnames = list(rows_out[0].keys())
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)


def build_wallet_dataset(input_csv: str, output_csv: str) -> None:
    rows_out = []

    with open(input_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            graph_path = (row.get("graph_path") or "").strip()
            address = (row.get("address") or "").strip().lower()
            if not graph_path or not address:
                continue
            label = _label_to_int(row.get("label", "0"))
            graph = _load_graph(graph_path)
            features = wallet_features_from_graph(address, graph)
            features["label"] = label
            features["address"] = address
            features["graph_path"] = graph_path
            rows_out.append(features)

    if not rows_out:
        raise SystemExit("No rows generated. Check input CSV.")

    fieldnames = list(rows_out[0].keys())
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)


def _prepare_token_frame(input_csv: str) -> Tuple[object, object]:
    import pandas as pd

    df = pd.read_csv(input_csv)
    if "label" not in df.columns:
        raise SystemExit("Input CSV must include a label column.")
    y = df["label"].astype(int)
    X = df.drop(columns=["label", "token_address"], errors="ignore")
    return X, y


def _prepare_wallet_frame(input_csv: str) -> Tuple[object, object]:
    import pandas as pd

    df = pd.read_csv(input_csv)
    if "label" not in df.columns:
        raise SystemExit("Input CSV must include a label column.")
    y = df["label"].astype(int)
    X = df.drop(columns=["label", "address", "graph_path"], errors="ignore")
    return X, y


def train_token_model(input_csv: str, output_model: str) -> Dict[str, object]:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report, roc_auc_score
    from sklearn.model_selection import train_test_split
    import joblib

    X, y = _prepare_token_frame(input_csv)
    if len(y) < 2:
        X_train, y_train = X, y
        X_test, y_test = X, y
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if y.nunique() > 1 else None
        )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    probas = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else None

    report = classification_report(y_test, preds, output_dict=True)
    roc_auc = roc_auc_score(y_test, probas) if probas is not None and y_test.nunique() > 1 else None

    Path(output_model).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_model)

    return {"report": report, "roc_auc": roc_auc, "n_samples": len(y)}


def train_wallet_model(input_csv: str, output_model: str) -> Dict[str, object]:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report, roc_auc_score
    from sklearn.model_selection import train_test_split
    import joblib

    X, y = _prepare_wallet_frame(input_csv)
    if len(y) < 2:
        X_train, y_train = X, y
        X_test, y_test = X, y
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if y.nunique() > 1 else None
        )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    probas = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else None

    report = classification_report(y_test, preds, output_dict=True)
    roc_auc = roc_auc_score(y_test, probas) if probas is not None and y_test.nunique() > 1 else None

    Path(output_model).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_model)

    return {"report": report, "roc_auc": roc_auc, "n_samples": len(y)}


def eval_token_model(input_csv: str, model_path: str) -> Dict[str, object]:
    from sklearn.metrics import classification_report, roc_auc_score
    import joblib

    X, y = _prepare_token_frame(input_csv)
    model = joblib.load(model_path)
    preds = model.predict(X)
    probas = model.predict_proba(X)[:, 1] if hasattr(model, "predict_proba") else None
    report = classification_report(y, preds, output_dict=True)
    roc_auc = roc_auc_score(y, probas) if probas is not None and y.nunique() > 1 else None
    return {"report": report, "roc_auc": roc_auc}


def eval_wallet_model(input_csv: str, model_path: str) -> Dict[str, object]:
    from sklearn.metrics import classification_report, roc_auc_score
    import joblib

    X, y = _prepare_wallet_frame(input_csv)
    model = joblib.load(model_path)
    preds = model.predict(X)
    probas = model.predict_proba(X)[:, 1] if hasattr(model, "predict_proba") else None
    report = classification_report(y, preds, output_dict=True)
    roc_auc = roc_auc_score(y, probas) if probas is not None and y.nunique() > 1 else None
    return {"report": report, "roc_auc": roc_auc}


def load_graph_for_scoring(path: str) -> Graph:
    return _load_graph(path)
