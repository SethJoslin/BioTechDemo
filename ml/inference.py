#!/usr/bin/env python3
"""
inference.py — Produce embeddings from trained ContrastiveEncoder.

This is a CLI wrapper around openbioops.models.inference.

Usage: Run from project root with PYTHONPATH set or after installing in dev mode.
"""
import argparse

from openbioops.models import load_encoder, embed_features


def main():
    parser = argparse.ArgumentParser(
        description="Run embedding inference on a parquet input"
    )
    parser.add_argument("--input", required=True, help="Input features parquet")
    parser.add_argument("--checkpoint", required=True, help="Path to model .pt file")
    parser.add_argument("--out", required=True, help="Output embeddings parquet")
    parser.add_argument("--batch-size", type=int, default=512)
    args = parser.parse_args()

    # Load model
    model = load_encoder(args.checkpoint)

    # Run inference
    embeddings_df = embed_features(model, args.input, batch_size=args.batch_size)

    # Save results
    embeddings_df.to_parquet(args.out)
    print(f"Wrote embeddings {embeddings_df.shape} -> {args.out}")


if __name__ == "__main__":
    main()
