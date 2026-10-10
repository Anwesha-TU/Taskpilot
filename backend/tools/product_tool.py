from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.registry import registry


PRODUCT_FILE = (
    Path(__file__).resolve().parents[2]
    / "mock_environment"
    / "products.json"
)


def load_products() -> List[Dict[str, Any]]:
    """
    Load products from the mock product environment.
    """

    import json

    with open(PRODUCT_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


@registry.register(
    "search_products",
    "Search the product environment for suitable food alternatives."
)
def search_products(
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    min_protein: Optional[float] = None,
    max_added_sugar: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Search products using nutritional and price constraints.

    Supported constraints:

        category
        max_price
        min_protein
        max_added_sugar
    """

    products = load_products()

    filtered_products = []

    for product in products:

        # Category

        if category is not None:

            if product.get("category") != category:
                continue

        # Maximum price

        if max_price is not None:

            price = product.get("price")

            if price is None:
                continue

            if float(price) > float(max_price):
                continue

        # Minimum protein

        if min_protein is not None:

            protein = product.get("protein_g")

            if protein is None:
                continue

            if float(protein) < float(min_protein):
                continue

        # Maximum added sugar

        if max_added_sugar is not None:

            added_sugar = product.get("added_sugar_g")

            if added_sugar is None:
                continue

            if float(added_sugar) > float(max_added_sugar):
                continue

        # Product passed all constraints

        filtered_products.append(product)

    return {
        "success": True,
        "count": len(filtered_products),
        "products": filtered_products,
    }
