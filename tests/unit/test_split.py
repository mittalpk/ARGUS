import os
import tempfile
import pytest
import pandas as pd
from src.data.split import create_stratified_splits, save_splits


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname


def test_create_stratified_splits_balanced():
    # 20 records (10 genuine, 10 fraudulent)
    df = pd.DataFrame(
        {"image_id": [f"img_{i}.jpg" for i in range(20)], "label": [0] * 10 + [1] * 10}
    )

    train_df, val_df, test_df = create_stratified_splits(
        df, test_size=0.15, val_size=0.15
    )

    # 15% of 20 is 3. Due to stratification/train_test_split behavior:
    # Test set gets 3 records (or rounded depending on random state)
    # Let's assert the splits partition the data completely
    total_records = len(train_df) + len(val_df) + len(test_df)
    assert total_records == 20

    # Check that splits are disjoint
    train_set = set(train_df["image_id"])
    val_set = set(val_df["image_id"])
    test_set = set(test_df["image_id"])

    assert train_set.isdisjoint(val_set)
    assert train_set.isdisjoint(test_set)
    assert val_set.isdisjoint(test_set)

    # Check stratification (genuine/fraud ratio roughly preserved)
    # Genuine ratio in original is 0.5
    train_ratio = train_df["label"].mean()
    val_ratio = val_df["label"].mean()
    test_ratio = test_df["label"].mean()

    # They should be close to 0.5
    assert abs(train_ratio - 0.5) <= 0.15
    assert abs(val_ratio - 0.5) <= 0.25
    assert abs(test_ratio - 0.5) <= 0.25


def test_save_splits(temp_dir):
    processed_dir = os.path.join(temp_dir, "processed")
    output_dir = os.path.join(temp_dir, "splits")
    os.makedirs(processed_dir, exist_ok=True)

    # Create mock processed images
    image_names = ["img_1.jpg", "img_2.jpg", "img_3.jpg"]
    for img_name in image_names:
        with open(os.path.join(processed_dir, img_name), "w") as f:
            f.write("mock image bytes")

    train_df = pd.DataFrame({"image_id": ["img_1.jpg"], "label": [0]})
    val_df = pd.DataFrame({"image_id": ["img_2.jpg"], "label": [1]})
    test_df = pd.DataFrame({"image_id": ["img_3.jpg"], "label": [0]})

    save_splits(train_df, val_df, test_df, processed_dir, output_dir)

    # Verify split metadata CSV exists
    assert os.path.exists(os.path.join(output_dir, "train_labels.csv"))
    assert os.path.exists(os.path.join(output_dir, "val_labels.csv"))
    assert os.path.exists(os.path.join(output_dir, "test_labels.csv"))

    # Verify split image directories exist and copy was successful
    assert os.path.exists(os.path.join(output_dir, "train", "img_1.jpg"))
    assert os.path.exists(os.path.join(output_dir, "val", "img_2.jpg"))
    assert os.path.exists(os.path.join(output_dir, "test", "img_3.jpg"))
