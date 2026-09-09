#!/usr/bin/env python3
"""Generate the CYBERPULSE AI synthetic dataset into data/raw/."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ml.data_generation.generate import generate_dataset  # noqa: E402

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "raw"))
    args = ap.parse_args()
    ds = generate_dataset(seed=args.seed, out_dir=args.out)
    print(f"[generate] complaints={len(ds.complaints)} transactions={len(ds.transactions)} "
          f"atms={len(ds.atms)} accounts={len(ds.accounts)} entities={len(ds.entities)} "
          f"relationships={len(ds.relationships)}")
    print(f"[generate] fraud rings: {len(ds.meta['fraud_rings'])}")
    print(f"[generate] written to {args.out}")