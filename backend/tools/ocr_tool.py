from tools.registry import registry
from model.ocr import extract_text_from_image


@registry.register(
    "ocr_product_label",
    "Extract text from a food product label image."
)
def ocr_product_label(image_path: str):

    try:
        text = extract_text_from_image(image_path)

        if not text or not text.strip():
            return {
                "success": False,
                "error": "No readable text was detected."
            }

        return {
            "success": True,
            "text": text.strip()
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
