import logging

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CSV_PATH = "combined_dataset.csv"


def main() -> None:
    """Load combined_dataset.csv and print 20 random rows."""
    df = pd.read_csv(CSV_PATH)
    logger.info("Loaded %d rows from %s", len(df), CSV_PATH)
    logger.info("Columns: %s", list(df.columns))

    sample = df.sample(n=20, random_state=None)
    for i, (_, row) in enumerate(sample.iterrows(), 1):
        print(f"--- Row {i} ---")
        print(f"  is_suicide: {row['is_suicide']}")
        print(f"  is_toxicity: {row['is_toxicity']}")
        text_preview = str(row["text"])[:200]
        print(f"  text: {text_preview}")
        print()


if __name__ == "__main__":
    main()
