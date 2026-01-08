from __future__ import annotations

import argparse
from tracer.ml.training import train_wallet_model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Feature CSV from build_wallet_dataset.py")
    parser.add_argument("--output", required=True, help="Output model path (pkl)")
    args = parser.parse_args()
    metrics = train_wallet_model(args.input, args.output)
    roc_auc = metrics.get("roc_auc")
    if roc_auc is not None:
        print("ROC AUC:", roc_auc)


if __name__ == "__main__":
    main()
