
from pathlib import Path
import re

path = Path(__file__).resolve().parent / "frontend.py"

if not path.is_file():
    raise SystemExit(f"ERROR: frontend.py not found at {path}")

source = path.read_text(encoding="utf-8-sig")

old_call = "self.result_view.setPlainText(self.pretty(final_result))"
new_call = "self.result_view.setPlainText(self.human_readable_result(final_result))"

if new_call not in source:
    if old_call not in source:
        raise SystemExit(
            "ERROR: Could not find the Final result display line. "
            "No changes were made."
        )
    source = source.replace(old_call, new_call, 1)

if "def human_readable_result(value):" not in source:
    pretty_match = re.search(
        r"(?m)^    def pretty\(value\):",
        source
    )

    if not pretty_match:
        raise SystemExit(
            "ERROR: Could not locate def pretty(value):. "
            "No changes were written."
        )

    # Include the existing @staticmethod decorator and blank lines
    # when finding the insertion point.
    decorator_match = list(
        re.finditer(
            r"(?m)^    @staticmethod[ \t]*(?:\r?\n[ \t]*)*"
            r"(?=    def pretty\(value\):)",
            source[:pretty_match.start()] + "    def pretty(value):"
        )
    )

    if not decorator_match:
        # The decorator may be separated by blank lines or may be absent.
        insertion_point = pretty_match.start()
    else:
        insertion_point = decorator_match[-1].start()

    method = '''    @staticmethod
    def human_readable_result(value):
        """Render nested task results as readable text."""

        labels = {
            "success": "Operation status",
            "needs_review": "Manual review required",
            "amount_valid": "Financial validation",
            "matches": "Values match",
            "suggested_subtotal": "Suggested subtotal (verify)",
            "vendor_suggestion": "Possible vendor (unverified)",
            "review_reasons": "Reasons for review",
            "missing_fields": "Missing fields",
            "invalid_amount_fields": "Invalid amount fields",
            "line_items": "Line items",
            "verification_message": "Verification summary",
            "amount_reconciliation": "Subtotal and tax check",
            "line_items_reconciliation": "Line-item subtotal check",
            "invoice_number": "Invoice number",
            "due_date": "Due date",
            "vendor_gstin": "Supplier GSTIN",
            "bill_to_gstin": "Customer GSTIN",
            "bill_to": "Billed to",
            "date": "Invoice date",
            "tax": "Tax / GST",
            "total": "Total",
            "subtotal": "Subtotal",
            "vendor": "Vendor",
            "email": "Email",
            "phone": "Phone",
            "currency": "Currency",
            "quantity": "Quantity",
            "unit_price": "Unit price",
            "amount": "Amount",
            "description": "Description",
            "item_number": "Item number",
            "expected_total": "Expected total",
            "extracted_total": "Extracted total",
            "line_items_sum": "Line-item sum",
            "extracted_subtotal": "Extracted subtotal",
            "status": "Status",
            "message": "Message",
            "error": "Error",
            "warning": "Warning",
            "final": "Final response",
            "output": "Output",
            "products": "Products",
            "name": "Name",
            "price": "Price",
            "ingredients": "Ingredients",
            "available": "Available",
            "protein_g": "Protein (g)",
            "added_sugar_g": "Added sugar (g)",
            "count": "Number of results",
        }

        def readable_label(key):
            key = str(key)
            return labels.get(
                key, key.replace("_", " ").strip().capitalize()
            )

        def readable_value(key, item):
            if item is None or item == "":
                return "Couldn't fetch"

            if isinstance(item, bool):
                if key == "success":
                    return "Succeeded" if item else "Failed"
                if key == "needs_review":
                    return "Yes — please review" if item else "No"
                if key in ("amount_valid", "matches", "valid"):
                    return "Passed" if item else "Failed"
                if key == "available":
                    return "Yes" if item else "No"
                return "Yes" if item else "No"

            return str(item)

        def render(item, level=0, key=None):
            pad = " " * level

            if isinstance(item, dict):
                if not item:
                    return pad + "No details available."

                output = []
                for child_key, child_value in item.items():
                    title = readable_label(child_key)

                    if isinstance(child_value, dict):
                        output.append(f"{pad}{title}:")
                        output.append(
                            render(child_value, level + 2, child_key)
                        )
                    elif isinstance(child_value, list):
                        output.append(f"{pad}{title}:")
                        if not child_value:
                            output.append(f"{pad}  None")
                        else:
                            for index, entry in enumerate(child_value, 1):
                                if isinstance(entry, (dict, list)):
                                    output.append(
                                        f"{pad}  Item {index}:"
                                    )
                                    output.append(
                                        render(entry, level + 4, child_key)
                                    )
                                else:
                                    output.append(
                                        f"{pad}  • "
                                        f"{readable_value(child_key, entry)}"
                                    )
                    else:
                        output.append(
                            f"{pad}{title}: "
                            f"{readable_value(child_key, child_value)}"
                        )

                return "\\n".join(output)

            if isinstance(item, list):
                if not item:
                    return pad + "None"

                output = []
                for index, entry in enumerate(item, 1):
                    if isinstance(entry, (dict, list)):
                        output.append(f"{pad}Item {index}:")
                        output.append(render(entry, level + 2, key))
                    else:
                        output.append(
                            f"{pad}• {readable_value(key, entry)}"
                        )
                return "\\n".join(output)

            return pad + readable_value(key, item)

        return render(value)

'''

    source = source[:insertion_point] + method + source[insertion_point:]

# Verify the patched source before overwriting the original.
try:
    compile(source, str(path), "exec")
except SyntaxError as exc:
    raise SystemExit(
        f"SYNTAX ERROR: {exc}. Original frontend.py was not changed."
    )

# Keep a backup before writing.
backup = path.with_name("frontend.py.before_readable_result.bak")
if not backup.exists():
    backup.write_text(
        path.read_text(encoding="utf-8-sig"),
        encoding="utf-8"
    )

path.write_text(source, encoding="utf-8")

print("PATCH APPLIED.")
print(f"Backup saved to: {backup}")
print("Python syntax check passed.")
print("Run: python frontend.py")
