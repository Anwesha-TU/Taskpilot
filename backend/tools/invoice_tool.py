
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from tools.registry import registry
from model.ocr import extract_text_from_image


@registry.register(
    "ocr_invoice",
    "Extract text from an invoice image for processing."
)
def ocr_invoice(file_path: str):
    path = Path(file_path)

    if not path.is_file():
        return {
            "success": False,
            "error": f"Invoice file does not exist: {file_path}"
        }

    try:
        text = extract_text_from_image(str(path))

        if not text or not text.strip():
            return {
                "success": False,
                "error": "No readable text was detected in the invoice."
            }

        return {
            "success": True,
            "text": text.strip(),
            "source_file": path.name
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc)
        }


@registry.register(
    "extract_invoice_fields",
    "Extract and validate basic fields from OCR text of an invoice."
)
def extract_invoice_fields(text: str):
    if not text or not text.strip():
        return {
            "success": False,
            "error": "Invoice text is empty."
        }

    patterns = {
        "invoice_number": [
            r"(?im)\binvoice\s*(?:number|no\.?|#|id)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]*)",
            r"(?im)\bbill\s*(?:number|no\.?)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]*)",
        ],
        "date": [
            r"(?im)\b(?:invoice\s+date|date)\s*[:#-]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
        ],
        "total": [
            r"(?im)\b(?:grand\s+total|total\s+due|amount\s+due|invoice\s+total|total)\s*[:\-]?\s*(?:INR|Rs\.?|₹|\$|USD|EUR)?\s*([0-9,]+(?:\.\d{1,2})?)"
        ],
        "currency": [
            r"(?i)\b(INR|USD|EUR|GBP)\b",
            r"₹",
            r"\$",
            r"€",
            r"£",
            r"(?i)\bRs\.?\b",
        ],
    }

    fields = {}

    for field, candidates in patterns.items():
        fields[field] = None

        for pattern in candidates:
            match = re.search(pattern, text)
            if match:
                fields[field] = (
                    match.group(1).strip()
                    if field != "currency" and match.lastindex
                    else match.group(0).strip()
                )
                break

    vendor_match = re.search(
        r"(?im)^\s*(?:vendor|supplier|seller)\s*:\s*(.+?)\s*$",
        text
    )
    fields["vendor"] = vendor_match.group(1).strip() if vendor_match else None

    missing_fields = [
        field for field in ("invoice_number", "date", "total")
        if not fields.get(field)
    ]

    amount_valid = False
    if fields.get("total"):
        try:
            amount = Decimal(fields["total"].replace(",", ""))
            amount_valid = amount >= 0
            fields["total"] = str(amount)
        except InvalidOperation:
            fields["total"] = None
            if "total" not in missing_fields:
                missing_fields.append("total")

    return {
        "success": True,
        "fields": fields,
        "missing_fields": missing_fields,
        "amount_valid": amount_valid,
        "needs_review": bool(missing_fields) or not amount_valid,
        "source_text": text,
        "warning": (
            "OCR and rule-based extraction can be inaccurate. "
            "Review the original invoice before relying on these fields."
        )
    }
