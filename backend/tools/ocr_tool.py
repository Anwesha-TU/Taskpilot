
import pytesseract
from PIL import Image, ImageOps, ImageEnhance

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def extract_text_from_image(image_path):
    """Extract text from an invoice using enhanced image preprocessing."""
    try:
        with Image.open(image_path) as source:
            image = source.convert("RGB")

        # Add a white border to improve text detection.
        image = ImageOps.expand(image, border=30, fill="white")

        # Enlarge the image for improved character recognition.
        image = image.resize(
            (image.width * 3, image.height * 3),
            Image.Resampling.LANCZOS,
        )

        # Improve contrast.
        image = ImageEnhance.Contrast(image).enhance(1.5)

        # Preserve line and table structure.
        config = "--oem 3 --psm 6"

        text = pytesseract.image_to_string(image, config=config)
        return text.strip()

    except Exception as exc:
        raise RuntimeError(f"Invoice OCR failed: {exc}") from exc
