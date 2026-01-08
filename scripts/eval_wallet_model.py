from __future__ import annotations

import argparse

from tracer.ml.training import eval_wallet_model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Feature CSV")
    parser.add_argument("--model", required=True, help="Model path (pkl)")
    args = parser.parse_args()

    metrics = eval_wallet_model(args.input, args.model)
    roc_auc = metrics.get("roc_auc")
    if roc_auc is not None:
        print("ROC AUC:", roc_auc)


if __name__ == "__main__":
    main()
