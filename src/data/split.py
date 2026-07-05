import os
import shutil
import logging
import pandas as pd
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def create_stratified_splits(
    df: pd.DataFrame, seed: int = 42, test_size: float = 0.15, val_size: float = 0.15
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Splits labels dataframe into train, val, and test partitions deterministically,
    ensuring class distributions are preserved (stratification).
    """
    if len(df) < 3:
        # For ultra-small datasets (e.g. 1 or 2 items), train_test_split will fail completely.
        # We manually split: first item goes to train, second to val, third to test.
        # This prevents any crash on small datasets.
        if len(df) == 1:
            return (
                df,
                pd.DataFrame(columns=df.columns),
                pd.DataFrame(columns=df.columns),
            )
        elif len(df) == 2:
            return df.iloc[[0]], df.iloc[[1]], pd.DataFrame(columns=df.columns)

    if len(df) < 10:
        # Fallback for small datasets (e.g. tests) where stratification might fail due to class size
        # We perform simple splits without stratification
        train_df, temp_df = train_test_split(
            df, test_size=(test_size + val_size), random_state=seed
        )
        if len(temp_df) < 2:
            return train_df, temp_df, pd.DataFrame(columns=df.columns)
        val_df, test_df = train_test_split(temp_df, test_size=0.5, random_state=seed)
        return train_df, val_df, test_df

    # First split off the test set
    train_val_df, test_df = train_test_split(
        df, test_size=test_size, random_state=seed, stratify=df["label"]
    )

    # Adjust val_size to fit the remaining train_val subset ratio
    relative_val_size = val_size / (1.0 - test_size)

    # Split train and validation
    train_df, val_df = train_test_split(
        train_val_df,
        test_size=relative_val_size,
        random_state=seed,
        stratify=train_val_df["label"],
    )

    return train_df, val_df, test_df


def save_splits(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    processed_dir: str,
    output_dir: str,
):
    """
    Saves split metadata and copies corresponding images to separate partitions.
    """
    partitions = {"train": train_df, "val": val_df, "test": test_df}

    for part_name, part_df in partitions.items():
        part_dir = os.path.join(output_dir, part_name)
        os.makedirs(part_dir, exist_ok=True)

        # Save split labels CSV
        part_labels_path = os.path.join(output_dir, f"{part_name}_labels.csv")
        part_df.to_csv(part_labels_path, index=False)

        # Copy images
        for _, row in part_df.iterrows():
            image_name = row["image_id"]
            src_path = os.path.join(processed_dir, image_name)
            dest_path = os.path.join(part_dir, image_name)

            if os.path.exists(src_path):
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(src_path, dest_path)
            else:
                logger.warning(
                    f"Warning: Image {src_path} listed in labels but not found."
                )


def run_splitting(
    processed_dir: str, output_dir: str, seed: int = 42
) -> tuple[int, int, int]:
    labels_path = os.path.join(processed_dir, "labels.csv")
    if not os.path.exists(labels_path):
        raise FileNotFoundError(f"Processed labels file not found: {labels_path}")

    df = pd.read_csv(labels_path)

    train_df, val_df, test_df = create_stratified_splits(df, seed=seed)

    save_splits(train_df, val_df, test_df, processed_dir, output_dir)

    return len(train_df), len(val_df), len(test_df)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        logger.error("Usage: python split.py <processed_dir> <output_dir>")
        sys.exit(1)

    proc, out = sys.argv[1], sys.argv[2]
    tr, va, te = run_splitting(proc, out)
    logger.info(f"Splitting complete. Train: {tr}, Val: {va}, Test: {te}")
