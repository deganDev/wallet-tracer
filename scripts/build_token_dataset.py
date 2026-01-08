from __future__ import annotations

import argparse
from tracer.ml.training import build_token_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="CSV with token_address,label")
    parser.add_argument("--output", required=True, help="Output CSV with features")
    args = parser.parse_args()
    build_token_dataset(args.input, args.output)


if __name__ == "__main__":
    main()
