
import re
from typing import Any, Dict, Optional


class RequirementExtractor:
    """Extract structured constraints from natural-language task goals."""

    CATEGORY_KEYWORDS = {
        "laptop": ["laptop", "laptops", "notebook computer", "notebook computers"],
        "protein_bar": ["protein bar", "protein bars"],
        "snack": ["snack", "snacks"],
        "beverage": ["beverage", "beverages", "drink", "drinks"],
        "meal": ["meal", "meals"],
    }

    def extract(self, goal: str) -> Dict[str, Any]:
        if not isinstance(goal, str):
            return {}

        text = goal.lower().strip()
        constraints: Dict[str, Any] = {}

        category = self._extract_category(text)
        if category:
            constraints["category"] = category

        max_price = self._extract_max_price(text)
        if max_price is not None:
            constraints["max_price"] = max_price

        min_price = self._extract_min_price(text)
        if min_price is not None:
            constraints["min_price"] = min_price

        min_protein = self._extract_min_protein(text)
        if min_protein is not None:
            constraints["min_protein"] = min_protein

        max_added_sugar = self._extract_max_added_sugar(text)
        if max_added_sugar is not None:
            constraints["max_added_sugar"] = max_added_sugar

        min_ram = self._extract_min_ram(text)
        if min_ram is not None:
            constraints["min_ram_gb"] = min_ram

        min_storage = self._extract_min_storage(text)
        if min_storage is not None:
            constraints["min_storage_gb"] = min_storage

        if any(
            phrase in text
            for phrase in (
                "available",
                "in stock",
                "currently available",
            )
        ):
            constraints["available"] = True

        return constraints

    def _extract_category(self, text: str) -> Optional[str]:
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return category
        return None

    @staticmethod
    def _number_pattern() -> str:
        """Match integers with optional thousands separators or decimals."""
        return r"\d+(?:,\d{3})*(?:\.\d+)?"

    @classmethod
    def _parse_number(cls, value: str) -> float:
        return float(value.replace(",", ""))

    def _extract_max_price(self, text: str) -> Optional[float]:
        number = self._number_pattern()

        patterns = [
            rf"\b(?:under|below|less than|maximum|max|within|up to|upto)\s*₹?\s*({number})",
            rf"₹\s*({number})\s*(?:or less|maximum|max)",
            rf"\b({number})\s*(?:rupees|rs\.?)\s*(?:or less|maximum|max)?",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue

            value = self._parse_number(match.group(1))

            if any(
                phrase in text
                for phrase in (
                    "under",
                    "below",
                    "less than",
                    "maximum",
                    "max",
                    "within",
                    "up to",
                    "upto",
                    "or less",
                )
            ) or "₹" in text or "rupee" in text or " rs" in text:
                return value

        return None

    def _extract_min_price(self, text: str) -> Optional[float]:
        number = self._number_pattern()
        patterns = [
            rf"\b(?:above|over|more than|at least|minimum|min)\s*₹?\s*({number})",
            rf"₹\s*({number})\s*(?:or more|and above)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return self._parse_number(match.group(1))

        return None

    def _extract_min_protein(self, text: str) -> Optional[float]:
        patterns = [
            r"(?:at least|minimum|min)\s*(\d+(?:\.\d+)?)\s*g?\s*protein",
            r"(\d+(?:\.\d+)?)\s*g?\s*(?:or more)\s*protein",
            r"protein\s*(?:of|at least|minimum|min)\s*(\d+(?:\.\d+)?)\s*g?",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1))

        return None

    def _extract_max_added_sugar(self, text: str) -> Optional[float]:
        patterns = [
            r"(?:less than|below|under|maximum|max|no more than)\s*(\d+(?:\.\d+)?)\s*g?\s*added\s*sugar",
            r"added\s*sugar\s*(?:below|under|less than|maximum|max)\s*(\d+(?:\.\d+)?)\s*g?",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1))

        return None

    def _extract_min_ram(self, text: str) -> Optional[float]:
        patterns = [
            r"(?:at least|minimum|min)\s*(\d+(?:\.\d+)?)\s*gb\s*(?:of\s*)?ram\b",
            r"(\d+(?:\.\d+)?)\s*gb\s*ram\b",
            r"ram\s*(?:of|at least|minimum|min)\s*(\d+(?:\.\d+)?)\s*gb\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1))

        return None

    def _extract_min_storage(self, text: str) -> Optional[float]:
        patterns = [
            r"(?:at least|minimum|min)\s*(\d+(?:\.\d+)?)\s*gb\s*(?:ssd|storage)\b",
            r"(\d+(?:\.\d+)?)\s*gb\s*(?:ssd|storage)\b",
            r"(?:ssd|storage)\s*(?:of|at least|minimum|min)\s*(\d+(?:\.\d+)?)\s*gb\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1))

        return None
