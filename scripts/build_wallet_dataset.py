from __future__ import annotations

import argparse
from tracer.ml.training import build_wallet_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="CSV with graph_path,address,label")
    parser.add_argument("--output", required=True, help="Output CSV with features")
    args = parser.parse_args()
    build_wallet_dataset(args.input, args.output)


if __name__ == "__main__":
    main()
