import os
import pytest
import pandas as pd
from PIL import Image
from prepare_submission import predict_labels


@pytest.fixture
def mock_inference_env(tmp_path):
    input_dir = tmp_path / "data_mock"
    input_dir.mkdir()

    # Create two dummy images
    img1 = Image.new("RGB", (100, 100), color="red")
    img1.save(input_dir / "doc_red.jpeg")

    img2 = Image.new("RGB", (150, 150), color="blue")
    img2.save(input_dir / "doc_blue.png")

    output_csv = tmp_path / "submissions_mock" / "submission.csv"

    return {"input_dir": str(input_dir), "output_csv": str(output_csv)}


def test_predict_labels_generation(mock_inference_env):
    env = mock_inference_env

    # Run prediction using default convnextv2_base model (random weights verify mode)
    predict_labels(
        input_dir=env["input_dir"],
        output_csv=env["output_csv"],
        model_name="convnextv2_base",
        checkpoint_path=None,
    )

    # Verify file is written
    assert os.path.exists(env["output_csv"])

    # Verify CSV content structure
    df = pd.read_csv(env["output_csv"])
    assert list(df.columns) == ["id", "label"]
    assert len(df) == 2

    # Extract IDs and sort to match
    ids = sorted(list(df["id"]))
    assert ids == ["doc_blue", "doc_red"]

    # Verify float properties of label column
    assert all(0.0 <= val <= 1.0 for val in df["label"])
