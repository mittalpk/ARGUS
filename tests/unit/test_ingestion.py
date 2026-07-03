import os
import tempfile
import pytest
import pandas as pd
from PIL import Image
from src.data.ingestion import verify_labels_schema, strip_exif_and_validate_image, run_ingestion

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname

def test_verify_labels_schema_success(temp_dir):
    csv_path = os.path.join(temp_dir, "valid.csv")
    df = pd.DataFrame({
        "image_id": ["img1.jpg", "img2.jpg"],
        "label": [0, 1]
    })
    df.to_csv(csv_path, index=False)
    
    result_df = verify_labels_schema(csv_path)
    assert len(result_df) == 2
    assert list(result_df.columns) == ["image_id", "label"]

def test_verify_labels_schema_missing_column(temp_dir):
    csv_path = os.path.join(temp_dir, "invalid_cols.csv")
    df = pd.DataFrame({
        "image_id": ["img1.jpg"],
        "wrong_label_col": [0]
    })
    df.to_csv(csv_path, index=False)
    
    with pytest.raises(ValueError, match="Missing required columns"):
        verify_labels_schema(csv_path)

def test_verify_labels_schema_null_values(temp_dir):
    csv_path = os.path.join(temp_dir, "nulls.csv")
    df = pd.DataFrame({
        "image_id": ["img1.jpg", None],
        "label": [0, 1]
    })
    df.to_csv(csv_path, index=False)
    
    with pytest.raises(ValueError, match="Found null values"):
        verify_labels_schema(csv_path)

def test_strip_exif_and_validate_image(temp_dir):
    src_path = os.path.join(temp_dir, "raw_with_exif.jpg")
    dest_path = os.path.join(temp_dir, "processed_no_exif.jpg")
    
    # 1. Create a dummy image with EXIF metadata
    img = Image.new("RGB", (50, 50), color="blue")
    exif = img.getexif()
    exif[271] = "ArgusCameraMaker" # Tag 271 is Make
    img.save(src_path, exif=exif)
    
    # Verify raw image has EXIF Make tag
    with Image.open(src_path) as raw_img:
        raw_exif = raw_img.getexif()
        assert 271 in raw_exif
        assert raw_exif[271] == "ArgusCameraMaker"
        
    # 2. Run stripping function
    success = strip_exif_and_validate_image(src_path, dest_path)
    assert success is True
    
    # 3. Verify processed image does NOT have any EXIF
    with Image.open(dest_path) as processed_img:
        processed_exif = processed_img.getexif()
        assert 271 not in processed_exif
        assert len(processed_exif) == 0

def test_strip_exif_corrupt_image(temp_dir):
    src_path = os.path.join(temp_dir, "corrupt.jpg")
    dest_path = os.path.join(temp_dir, "dest.jpg")
    
    # Create zero-byte corrupt file
    with open(src_path, "wb") as f:
        f.write(b"")
        
    success = strip_exif_and_validate_image(src_path, dest_path)
    assert success is False
    assert not os.path.exists(dest_path)
