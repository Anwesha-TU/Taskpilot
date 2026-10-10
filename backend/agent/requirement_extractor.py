import re
from typing import Any, Dict


class RequirementExtractor:
    """
    Extract structured requirements from a natural-language user goal.

    Example:

        "Find a protein bar under ₹150 with at least 20g
        protein and less than 5g added sugar"

    becomes:

        {
            "category": "protein_bar",
            "max_price": 150,
            "min_protein": 20,
            "max_added_sugar": 5
        }

    This deterministic implementation is intentionally simple.
    It can later be replaced or augmented with an LLM-based
    requirement extraction layer.
    """

    CATEGORY_KEYWORDS = {
        "protein_bar": [
            "protein bar",
            "protein bars",
        ],
        "snack": [
            "snack",
            "snacks",
        ],
        "beverage": [
            "beverage",
            "drink",
            "drinks",
        ],
        "meal": [
            "meal",
            "meals",
        ],
    }

    def extract(self, goal: str) -> Dict[str, Any]:
        """
        Extract structured constraints from the user's goal.
        """

        if not isinstance(goal, str):
            return {}

        text = goal.lower().strip()

        constraints: Dict[str, Any] = {}

        
        # CATEGORY
        

        category = self._extract_category(text)

        if category:
            constraints["category"] = category

        
        # PRICE
        

        max_price = self._extract_max_price(text)

        if max_price is not None:
            constraints["max_price"] = max_price

        
        # MINIMUM PROTEIN
        

        min_protein = self._extract_min_protein(text)

        if min_protein is not None:
            constraints["min_protein"] = min_protein

        
        # MAXIMUM ADDED SUGAR
        

        max_added_sugar = self._extract_max_added_sugar(text)

        if max_added_sugar is not None:
            constraints["max_added_sugar"] = max_added_sugar

        
        # AVAILABILITY
        

        if any(
            phrase in text
            for phrase in [
                "available",
                "in stock",
                "currently available",
            ]
        ):
            constraints["available"] = True

        return constraints

    
    # CATEGORY
    

    def _extract_category(self, text: str):
        for category, keywords in self.CATEGORY_KEYWORDS.items():

            for keyword in keywords:

                if keyword in text:
                    return category

        return None

    
    # PRICE
    

    def _extract_max_price(self, text: str):
        """
        Detect expressions such as:

            under ₹150
            below ₹150
            less than ₹150
            max ₹150
            maximum ₹150
            within ₹150
            under 150 rupees
        """

        patterns = [
            r"(?:under|below|less than|maximum|max|within)\s*₹?\s*(\d+(?:\.\d+)?)",
            r"₹?\s*(\d+(?:\.\d+)?)\s*(?:or less|maximum|max)",
            r"(?:under|below|less than|maximum|max|within)\s*(\d+(?:\.\d+)?)\s*(?:rupees|rs)",
        ]

        for pattern in patterns:

            match = re.search(pattern, text)

            if match:
                return float(match.group(1))

        return None

    
    # MINIMUM PROTEIN
    

    def _extract_min_protein(self, text: str):
        """
        Detect expressions such as:

            at least 20g protein
            minimum 20g protein
            20g or more protein
            protein at least 20g
        """

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

    
    # MAXIMUM ADDED SUGAR
    

    def _extract_max_added_sugar(self, text: str):
        """
        Detect expressions such as:

            less than 5g added sugar
            below 5g added sugar
            maximum 5g added sugar
            no more than 5g added sugar
        """

        patterns = [
            r"(?:less than|below|under|maximum|max|no more than)\s*(\d+(?:\.\d+)?)\s*g?\s*added\s*sugar",
            r"added\s*sugar\s*(?:below|under|less than|maximum|max)\s*(\d+(?:\.\d+)?)\s*g?",
        ]

        for pattern in patterns:

            match = re.search(pattern, text)

            if match:
                return float(match.group(1))

        return None
