import logging

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CSV_PATH = "combined_dataset.csv"


def main() -> None:
    """Deep data analysis of combined_dataset.csv."""
    logger.info("Loading %s ...", CSV_PATH)
    df = pd.read_csv(CSV_PATH)

    print("=" * 60)
    print("1. SHAPE, DTYPES, MEMORY USAGE")
    print("=" * 60)
    print(f"Shape: {df.shape[0]:,} rows x {df.shape[1]} columns")
    print(f"\nColumn dtypes:\n{df.dtypes}")
    print(f"\nMemory usage: {df.memory_usage(deep=True).sum() / 1e6:.2f} MB")

    print("\n" + "=" * 60)
    print("2. LABEL DISTRIBUTION")
    print("=" * 60)
    for col in ["is_suicide", "is_toxicity"]:
        counts = df[col].value_counts()
        pcts = df[col].value_counts(normalize=True) * 100
        print(f"\n{col}:")
        for val in counts.index:
            print(f"  {val}: {counts[val]:,} ({pcts[val]:.2f}%)")

    print("\n" + "=" * 60)
    print("3. MISSING / NULL VALUES")
    print("=" * 60)
    nulls = df.isnull().sum()
    if nulls.any():
        print(f"\nMissing values:\n{nulls[nulls > 0]}")
    else:
        print("\nNo missing values")

    print("\n" + "=" * 60)
    print("4. TEXT LENGTH STATISTICS")
    print("=" * 60)
    lengths = df["text"].astype(str).str.len()
    print(f"\nText length stats:")
    print(
        f"  min={lengths.min()}, max={lengths.max()}, "
        f"mean={lengths.mean():.1f}, median={lengths.median():.1f}, "
        f"std={lengths.std():.1f}"
    )
    print(
        f"  P25={lengths.quantile(0.25):.0f}, "
        f"P75={lengths.quantile(0.75):.0f}, "
        f"P95={lengths.quantile(0.95):.0f}, "
        f"P99={lengths.quantile(0.99):.0f}"
    )

    print("\n" + "=" * 60)
    print("5. CLASS IMBALANCE RATIO")
    print("=" * 60)
    for col in ["is_suicide", "is_toxicity"]:
        vc = df[col].value_counts()
        ratio = vc.max() / vc.min()
        print(f"\n{col} imbalance ratio (majority/minority): {ratio:.2f}x")

    print("\n" + "=" * 60)
    print("6. TEXT LENGTH DISTRIBUTION BY LABEL")
    print("=" * 60)
    for col in ["is_suicide", "is_toxicity"]:
        print(f"\nText length by {col}:")
        for val in sorted(df[col].unique()):
            sub = lengths[df[col] == val]
            print(
                f"  {val}: mean={sub.mean():.1f}, "
                f"median={sub.median():.1f}, "
                f"std={sub.std():.1f}, n={len(sub):,}"
            )

    print("\n" + "=" * 60)
    print("7. EXTREME CASES (SHORTEST / LONGEST 5)")
    print("=" * 60)
    df["_len"] = lengths
    print("\nShortest 5 texts:")
    for _, r in df.nsmallest(5, "_len").iterrows():
        print(f"  len={r['_len']} | {r['text'][:120]}")
    print("\nLongest 5 texts:")
    for _, r in df.nlargest(5, "_len").iterrows():
        print(f"  len={r['_len']} | {r['text'][:120]}")
    df.drop(columns=["_len"], inplace=True)

    print("\n" + "=" * 60)
    print("8. CHARACTER ENCODING ANOMALIES")
    print("=" * 60)
    # Vectorized: count non-ASCII chars across all text
    text_series = df["text"].astype(str)
    # Sample 50k rows for expensive per-char checks on large dataset
    sample_size = min(50_000, len(df))
    text_sample = text_series.sample(n=sample_size, random_state=42)
    non_ascii_count = text_sample.str.count(r"[^\x00-\x7F]").sum()
    sample_chars = text_sample.str.len().sum()
    total_chars = lengths.sum()
    # Scale sample estimate to full dataset
    est_non_ascii = int(non_ascii_count * (total_chars / sample_chars))
    print(
        f"\nNon-ASCII characters (est. from {sample_size:,} sample): "
        f"~{est_non_ascii:,} / {total_chars:,} "
        f"({est_non_ascii / total_chars * 100:.4f}%)"
    )
    null_bytes = text_series.str.contains("\x00", regex=False).sum()
    print(f"Rows with null bytes: {null_bytes:,}")
    ctrl_count = text_sample.str.count(r"[\x00-\x08\x0b\x0c\x0e-\x1f]").sum()
    est_ctrl = int(ctrl_count * (total_chars / sample_chars))
    print(f"Control characters (est., excl newline/tab): ~{est_ctrl:,}")

    print("\n" + "=" * 60)
    print("9. DUPLICATE DETECTION")
    print("=" * 60)
    dupes = df.duplicated(subset=["text"], keep=False)
    n_dupes = dupes.sum()
    print(f"\nDuplicate rows (same text): {n_dupes:,} ({n_dupes / len(df) * 100:.2f}%)")
    if n_dupes > 0:
        print("Sample duplicates:")
        for _, r in df[dupes].head(5).iterrows():
            print(f"  {r['text'][:100]}")

    print("\n" + "=" * 60)
    print("10. CROSS-TAB: IS_SUICIDE VS IS_TOXICITY")
    print("=" * 60)
    ct = pd.crosstab(df["is_suicide"], df["is_toxicity"], margins=True)
    print(f"\n{ct}")
    both = ((df["is_suicide"] == True) & (df["is_toxicity"] == True)).sum()  # noqa: E712
    print(f"\nRows where both labels are True: {both:,}")


if __name__ == "__main__":
    main()
