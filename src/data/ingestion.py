import os
import logging
import pandas as pd
from PIL import Image

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def verify_labels_schema(csv_path: str) -> pd.DataFrame:
    """
    Validates the labels CSV file schema.
    Must contain 'image_id' (or 'id') and 'label' columns.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Labels file not found: {csv_path}")
    
    df = pd.read_csv(csv_path)
    
    # Map 'id' to 'image_id' if present
    if 'id' in df.columns and 'image_id' not in df.columns:
        df = df.rename(columns={'id': 'image_id'})
    
    required_cols = {'image_id', 'label'}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Schema validation failed. Missing required columns: {required_cols - set(df.columns)}")
    
    # Check for empty labels
    if df['image_id'].isnull().any() or df['label'].isnull().any():
        raise ValueError("Schema validation failed: Found null values in 'image_id' or 'label'.")
        
    return df

def strip_exif_and_validate_image(src_path: str, dest_path: str) -> bool:
    """
    Verifies image file integrity and saves a clean copy stripped of all EXIF metadata.
    Handles color conversions (e.g. RGBA/P palette) and transparency checks.
    Returns True if successful, False if image is corrupt or unreadable.
    """
    try:
        if not os.path.exists(src_path):
            return False
            
        # Try to open and verify the image structure
        with Image.open(src_path) as img:
            img.verify()
            
        # Re-open for writing (verify() closes the file pointer)
        with Image.open(src_path) as img:
            mode = img.mode
            # Handle transparent or palette-based modes
            if mode in ('RGBA', 'LA') or (mode == 'P' and 'transparency' in img.info):
                img_conv = img.convert('RGBA')
                clean_img = Image.new('RGBA', img_conv.size)
                clean_img.paste(img_conv)
                dest_format = "PNG"
            else:
                img_conv = img.convert('RGB')
                clean_img = Image.new('RGB', img_conv.size)
                clean_img.paste(img_conv)
                dest_format = "JPEG"
            
            # Save the clean copy
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            clean_img.save(dest_path, format=dest_format, quality=95)
            
        return True
    except Exception as e:
        logger.error(f"Failed to process image {src_path}: {e}")
        return False

def run_ingestion(raw_dir: str, processed_dir: str, labels_csv: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Orchestrates metadata stripping and validation across raw image directory.
    """
    df = verify_labels_schema(labels_csv)
    
    processed_records = []
    failed_images = []
    
    for idx, row in df.iterrows():
        image_name = row['image_id']
        
        # If 'image_path' column is in original CSV, resolve relative paths robustly
        if 'image_path' in df.columns:
            rel_path = row['image_path']
            candidate_paths = [
                os.path.join(raw_dir, rel_path),
                os.path.join(raw_dir, os.path.basename(rel_path))
            ]
            src_image_path = None
            for p in candidate_paths:
                if os.path.exists(p):
                    src_image_path = p
                    break
            if src_image_path is None:
                src_image_path = candidate_paths[0] # Default fallback
            image_name = rel_path
        else:
            # Handle case where file extension is missing from image_id
            if not image_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                image_name += ".jpg"
            src_image_path = os.path.join(raw_dir, image_name)
            
        dest_image_path = os.path.join(processed_dir, image_name)
        
        success = strip_exif_and_validate_image(src_image_path, dest_image_path)
        if success:
            processed_records.append({
                'image_id': image_name,
                'label': row['label']
            })
        else:
            failed_images.append(image_name)
            
    processed_df = pd.DataFrame(processed_records)
    
    # Save clean labels matching only valid images
    processed_labels_path = os.path.join(processed_dir, "labels.csv")
    processed_df.to_csv(processed_labels_path, index=False)
    
    return processed_df, failed_images

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        logger.error("Usage: python ingestion.py <raw_dir> <processed_dir> <labels_csv>")
        sys.exit(1)
    
    raw, proc, csv = sys.argv[1], sys.argv[2], sys.argv[3]
    df, fails = run_ingestion(raw, proc, csv)
    logger.info(f"Ingestion complete. Successfully processed: {len(df)} images. Failed/Corrupt: {len(fails)}")
