
import pytesseract
from PIL import Image, ImageOps, ImageEnhance

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def extract_text_from_image(image_path):
    """Extract invoice text after enhancing the image for OCR."""
    try:
        with Image.open(image_path) as source:
            image = source.convert("RGB")

        # Add a white border to help Tesseract detect the page.
        image = ImageOps.expand(image, border=30, fill="white")

        # Enlarge the image for better character recognition.
        image = image.resize(
            (image.width * 3, image.height * 3),
            Image.Resampling.LANCZOS,
        )

        # Improve text contrast.
        image = ImageEnhance.Contrast(image).enhance(1.5)

        # OCR with a page layout mode that works well for this invoice.
        text = pytesseract.image_to_string(
            image,
            config="--oem 3 --psm 6",
        )

        return text.strip()

    except Exception as exc:
        raise RuntimeError(f"Invoice OCR failed: {exc}") from exc
