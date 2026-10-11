
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.registry import registry


PRODUCT_FILE = (
    Path(__file__).resolve().parents[2]
    / "mock_environment"
    / "products.json"
)


def load_products() -> List[Dict[str, Any]]:
    if not PRODUCT_FILE.exists():
        raise FileNotFoundError(
            f"Product catalog not found: {PRODUCT_FILE}"
        )

    with PRODUCT_FILE.open("r", encoding="utf-8") as file:
        products = json.load(file)

    if not isinstance(products, list):
        raise ValueError("Product catalog must contain a JSON list.")

    return products


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", " ").replace("_", " ")


def _matches_query(product: Dict[str, Any], query: str) -> bool:
    if not query:
        return True

    searchable = " ".join(
        _normalise(value)
        for value in product.values()
        if not isinstance(value, (dict, list))
    )

    terms = _normalise(query).split()
    return all(term in searchable for term in terms)


@registry.register(
    "search_products",
    "Search the local product catalog by category, query, "
    "price, availability, and product attributes."
)
def search_products(
    category: Optional[str] = None,
    query: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    min_protein: Optional[float] = None,
    max_added_sugar: Optional[float] = None,
    available: Optional[bool] = None,
    min_ram_gb: Optional[float] = None,
    min_storage_gb: Optional[float] = None,
    brand: Optional[str] = None,
) -> Dict[str, Any]:
    products = load_products()
    results = []

    for product in products:
        product_category = _normalise(product.get("category"))
        requested_category = _normalise(category) if category else ""

        if requested_category and product_category != requested_category:
            continue

        if not _matches_query(product, query or ""):
            continue

        if brand and _normalise(brand) not in _normalise(product.get("brand")):
            continue

        if available is not None:
            if product.get("available") is not available:
                continue

        numeric_filters = [
            ("price", min_price, "min"),
            ("price", max_price, "max"),
            ("protein_g", min_protein, "min"),
            ("added_sugar_g", max_added_sugar, "max"),
            ("ram_gb", min_ram_gb, "min"),
            ("storage_gb", min_storage_gb, "min"),
        ]

        rejected = False

        for field, limit, direction in numeric_filters:
            if limit is None:
                continue

            value = product.get(field)

            # Missing specifications must not satisfy a hard constraint.
            if value is None:
                rejected = True
                break

            try:
                value = float(value)
                limit = float(limit)
            except (TypeError, ValueError):
                rejected = True
                break

            if direction == "min" and value < limit:
                rejected = True
                break

            if direction == "max" and value > limit:
                rejected = True
                break

        if rejected:
            continue

        results.append(product)

    return {
        "success": True,
        "count": len(results),
        "products": results,
        "message": (
            f"Found {len(results)} matching product(s)."
            if results
            else "No matching products exist in the local catalog."
        ),
    }
