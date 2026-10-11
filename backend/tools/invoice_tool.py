"""Invoice OCR and field extraction tools.

Extracts all supported fields without inventing missing values. OCR results and
amount checks are kept separate so a completed extraction can still require review.
"""

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Optional

from tools.registry import registry
from model.ocr import extract_text_from_image


_CURRENCY = r"(?:INR|Rs\.?|₹|USD|EUR|GBP|\$|€|£)"
_NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?"
_AMOUNT = rf"(?:{_CURRENCY}\s*)?({_NUMBER})"


def _clean_text(value: str) -> str:
    value = value.replace("\u00a0", " ").replace("\u200b", "")
    value = value.replace("—", "-").replace("–", "-")
    return value


def _first_match(patterns, text: str) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def _parse_amount(raw: Optional[str]):
    if raw is None:
        return None
    try:
        amount = Decimal(raw.strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount


def _extract_line_items(lines):
    """Extract rows shaped like: number, description, qty, unit price, amount."""
    items = []
    pattern = re.compile(
        r"^\s*(\d{1,3})\s+(.+?)\s+(\d{1,5})\s+"
        r"([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$"
    )
    for line in lines:
        match = pattern.match(line)
        if not match:
            continue
        number, description, quantity, unit_price, amount = match.groups()
        items.append({
            "item_number": int(number),
            "description": description.strip(),
            "quantity": int(quantity),
            "unit_price": str(_parse_amount(unit_price)),
            "amount": str(_parse_amount(amount)),
        })
    return items


@registry.register("ocr_invoice", "Extract text from an invoice image for processing.")
def ocr_invoice(file_path: str) -> Dict[str, Any]:
    path = Path(file_path).expanduser()
    if not path.is_file():
        return {"success": False, "error": f"Invoice file does not exist: {file_path}"}
    try:
        text = extract_text_from_image(str(path))
        print("\n========== INVOICE OCR TEXT ==========")
        print(text)
        print("========== END OCR TEXT =============\n")
        if not text or not text.strip():
            return {"success": False, "error": "No readable text was detected in the invoice."}
        return {"success": True, "text": _clean_text(text).strip(), "source_file": path.name}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@registry.register("extract_invoice_fields", "Extract and validate fields from OCR text of an invoice.")
def extract_invoice_fields(text: str) -> Dict[str, Any]:
    if not text or not text.strip():
        return {"success": False, "error": "Invoice text is empty."}

    text = _clean_text(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    invoice_number = _first_match([
        r"\binvoice\s*(?:number|no\.?|#|id)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]*)",
        r"\bbill\s*(?:number|no\.?|#)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]*)",
    ], text)
    invoice_date = _first_match([
        r"\binvoice\s+date\s*[:#-]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
        r"\binvoice\s+date\s*[:#-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        r"\bdate\s*[:#-]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
    ], text)
    due_date = _first_match([
        r"\bdue\s+date\s*[:#-]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
        r"\bdue\s+date\s*[:#-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
    ], text)
    email = _first_match([r"\bemail\s*:\s*([\w.+%-]+@[\w.-]+\.[A-Za-z]{2,})", r"\b([\w.+%-]+@[\w.-]+\.[A-Za-z]{2,})\b"], text)
    phone = _first_match([r"\bphone\s*:\s*([+()\d][+()\d\s.-]{6,})"], text)
    payment_terms = _first_match([r"\bpayment\s+terms\s*:\s*([^\n]+)"], text)

    vendor = _first_match([
        r"^\s*(?:vendor|supplier|seller|from)\s*:\s*(.+?)\s*$",
        r"^\s*(?:vendor|supplier|seller|from)\s+(.+?)\s*$",
    ], text)
    if not vendor:
        excluded = re.compile(
            r"^(invoice|tax invoice|bill|receipt|purchase order|quotation|date\b|"
            r"invoice number\b|invoice date\b|bill to\b|ship to\b|remarks\b|"
            r"office\s*&\s*stationery products\b|stationery products\b|"
            r"products?\b|services?\b|w\s*w\b)",
            re.IGNORECASE,
        )
        for line in lines[:8]:
            candidate = re.sub(r"\s+", " ", line).strip(" :-")
            if (candidate and len(candidate) <= 100 and not excluded.search(candidate)
                    and not re.search(r"\b(?:subtotal|total|gst|tax)\b", candidate, re.I)
                    and not re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", candidate)
                    and not re.search(r"\binvoice\s*(?:number|no\.?|#|id)\b", candidate, re.I)
                    and not re.match(r"^(phone|email|address|gstin|www\.)\b", candidate, re.I)):
                vendor = candidate
                break

    # The first GSTIN usually belongs to the supplier; the next one may belong
    # to the billed customer. Preserve the OCR strings exactly for review.
    gstins = re.findall(r"\bGSTIN\s*:\s*([^\n,;]+)", text, flags=re.IGNORECASE)
    supplier_gstin = gstins[0].strip() if gstins else None
    bill_to_gstin = gstins[1].strip() if len(gstins) > 1 else None

    bill_to = None
    for i, line in enumerate(lines):
        if re.match(r"^bill\s+to\s*:?\s*$", line, re.I):
            for candidate in lines[i + 1:i + 4]:
                if not re.match(r"^(GSTIN|address|phone|email)\b", candidate, re.I):
                    bill_to = candidate
                    break
            break

    subtotal_raw = _first_match([
        rf"^\s*(?:remarks\s*:\s*)?(?:sub\s*total|subtotal)\s*(?:\([^\n)]*\))?\s*[:=-]?\s*{_AMOUNT}",
        rf"\b(?:sub\s*total|subtotal)\s*(?:\([^\n)]*\))?\s*[:=-]?\s*{_AMOUNT}",
    ], text)
    tax_raw = _first_match([
        rf"^\s*(?:total\s+tax|sales\s+tax|tax|gst|igst|cgst|sgst|vat)\s*(?:\([^\n)]*\))?\s*[:=-]?\s*{_AMOUNT}",
        rf"\b(?:tax|gst|igst|cgst|sgst|vat)\s*(?:\([^\n)]*\))?\s*[:=-]?\s*{_AMOUNT}",
    ], text)
    total_raw = _first_match([
        rf"^\s*(?:grand\s+total|total\s+due|amount\s+due|invoice\s+total|total)\s*(?:\([^\n)]*\))?\s*[:=-]?\s*{_AMOUNT}",
    ], text)

    subtotal = _parse_amount(subtotal_raw)
    tax = _parse_amount(tax_raw)
    total = _parse_amount(total_raw)
    currency_match = re.search(r"\b(INR|USD|EUR|GBP)\b|₹|\$|€|£|\bRs\.?\b", text, re.I)
    currency = currency_match.group(0).strip() if currency_match else None
    line_items = _extract_line_items(lines)

    fields = {
        "invoice_number": invoice_number,
        "date": invoice_date,
        "due_date": due_date,
        "vendor": vendor,
        "vendor_gstin": supplier_gstin,
        "bill_to": bill_to,
        "bill_to_gstin": bill_to_gstin,
        "phone": phone,
        "email": email,
        "payment_terms": payment_terms,
        "subtotal": str(subtotal) if subtotal is not None else None,
        "tax": str(tax) if tax is not None else None,
        "total": str(total) if total is not None else None,
        "currency": currency,
    }

    required_fields = ("invoice_number", "date", "vendor", "subtotal", "tax", "total")
    missing_fields = [name for name in required_fields if fields.get(name) is None]
    invalid_amount_fields = []
    for name, raw, parsed in (("subtotal", subtotal_raw, subtotal), ("tax", tax_raw, tax), ("total", total_raw, total)):
        if raw is not None and parsed is None:
            invalid_amount_fields.append(name)
            if name not in missing_fields:
                missing_fields.append(name)

    amounts_complete = all(v is not None for v in (subtotal, tax, total))
    reconciliation = None
    if amounts_complete:
        reconciliation = {
            "expected_total": str(subtotal + tax),
            "extracted_total": str(total),
            "matches": subtotal + tax == total,
        }

    line_items_sum = sum((_parse_amount(item.get("amount")) or Decimal("0") for item in line_items), Decimal("0"))
    line_items_reconciliation = None
    if line_items and subtotal is not None:
        line_items_reconciliation = {
            "line_items_sum": str(line_items_sum),
            "extracted_subtotal": str(subtotal),
            "matches": line_items_sum == subtotal,
        }

    # Suggest a subtotal only if line items and total-minus-tax independently agree.
    # Never overwrite the amount read from the invoice; preserve it for review.
    suggested_subtotal = None
    if line_items and tax is not None and total is not None:
        implied_subtotal = total - tax
        if implied_subtotal >= 0 and implied_subtotal == line_items_sum:
            suggested_subtotal = str(implied_subtotal)

    # Email-domain inference is only a hint, not a verified vendor field.
    vendor_suggestion = None
    if not vendor and email:
        domain = email.rsplit("@", 1)[-1].split(".", 1)[0]
        domain = re.sub(r"[^A-Za-z0-9]+", " ", domain).strip()
        if domain and domain.lower() not in {"gmail", "outlook", "yahoo", "hotmail", "icloud"}:
            vendor_suggestion = domain.title()

    amount_valid = bool(amounts_complete and not invalid_amount_fields and reconciliation["matches"])
    review_reasons = []
    if missing_fields:
        review_reasons.append("Missing or unreadable fields: " + ", ".join(missing_fields) + ".")
    if invalid_amount_fields:
        review_reasons.append("Invalid monetary values: " + ", ".join(invalid_amount_fields) + ".")
    if not amounts_complete:
        review_reasons.append("The subtotal, tax, and total cannot all be verified because one or more amounts are missing.")
    elif not reconciliation["matches"]:
        review_reasons.append("Subtotal plus tax does not equal total. Check for discounts, additional charges, rounding, or extraction errors.")
    if line_items_reconciliation and not line_items_reconciliation["matches"]:
        review_reasons.append("The sum of extracted line items does not match the extracted subtotal.")
    if suggested_subtotal is not None and subtotal is not None and suggested_subtotal != str(subtotal):
        review_reasons.append(
            f"Possible subtotal correction: line items and total-minus-tax both imply {suggested_subtotal}, "
            f"but OCR read {subtotal}. The original extracted value is preserved; verify against the invoice."
        )
    if vendor_suggestion:
        review_reasons.append(
            f"Possible vendor name inferred from email domain: {vendor_suggestion}. "
            "This is unverified; confirm from the invoice."
        )

    needs_review = bool(missing_fields or invalid_amount_fields or not amount_valid or (line_items_reconciliation and not line_items_reconciliation["matches"]))
    status_message = "Invoice needs review: " + " ".join(review_reasons) if needs_review else "Required fields were extracted and the subtotal-plus-tax check passed."

    return {
        "success": True,
        "fields": fields,
        "line_items": line_items,
        "missing_fields": missing_fields,
        "invalid_amount_fields": invalid_amount_fields,
        "amount_valid": amount_valid,
        "amount_reconciliation": reconciliation,
        "line_items_reconciliation": line_items_reconciliation,
        "suggested_subtotal": suggested_subtotal,
        "vendor_suggestion": vendor_suggestion,
        "needs_review": needs_review,
        "review_reasons": review_reasons,
        "verification_message": status_message,
        "source_text": text,
        "warning": status_message + " OCR and rule-based extraction can be inaccurate; review the original invoice before relying on the result.",
    }
