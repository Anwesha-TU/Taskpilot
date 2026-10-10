import re
from typing import Any, Dict


class RequirementExtractor:
    """
    Extracts structured constraints from a user's natural-language goal.

    This is the deterministic version of the requirement extractor.
    It can later be augmented with an LLM-based extractor.
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
        "cereal": [
            "cereal",
            "cereals",
        ],
        "drink": [
            "drink",
            "drinks",
            "beverage",
            "beverages",
        ],
    }

    def extract(self, goal: str) -> Dict[str, Any]:
        """
        Extract structured requirements from a natural-language goal.
        """

        goal_lower = goal.lower().strip()

        constraints: Dict[str, Any] = {}

         
        # Category
         

        category = self._extract_category(
            goal_lower
        )

        if category:
            constraints["category"] = category

         
        # Maximum price
         

        max_price = self._extract_max_price(
            goal_lower
        )

        if max_price is not None:
            constraints["max_price"] = max_price

         
        # Minimum price
         

        min_price = self._extract_min_price(
            goal_lower
        )

        if min_price is not None:
            constraints["min_price"] = min_price

         
        # Minimum protein
         

        min_protein = self._extract_min_protein(
            goal_lower
        )

        if min_protein is not None:
            constraints["min_protein"] = min_protein

         
        # Maximum protein
         

        max_protein = self._extract_max_protein(
            goal_lower
        )

        if max_protein is not None:
            constraints["max_protein"] = max_protein

         
        # Maximum added sugar
         

        max_sugar = self._extract_max_sugar(
            goal_lower
        )

        if max_sugar is not None:
            constraints["max_added_sugar"] = max_sugar

        return constraints

     
    # CATEGORY
     

    def _extract_category(
        self,
        text: str
    ) -> str | None:

        for category, keywords in self.CATEGORY_KEYWORDS.items():

            for keyword in keywords:

                if keyword in text:
                    return category

        return None

     
    # PRICE
     

    def _extract_max_price(
        self,
        text: str
    ) -> float | None:

        patterns = [
            r"(?:under|below|less than|maximum|max|upto|up to)\s*₹?\s*(\d+(?:\.\d+)?)",
            r"₹\s*(\d+(?:\.\d+)?)\s*(?:or less|and below|maximum)",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text
            )

            if match:
                return float(match.group(1))

        return None

    def _extract_min_price(
        self,
        text: str
    ) -> float | None:

        patterns = [
            r"(?:above|over|more than|minimum|min)\s*₹?\s*(\d+(?:\.\d+)?)",
            r"₹\s*(\d+(?:\.\d+)?)\s*(?:or more|and above|minimum)",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text
            )

            if match:
                return float(match.group(1))

        return None

     
    # PROTEIN
     

    def _extract_min_protein(
        self,
        text: str
    ) -> float | None:

        patterns = [
            r"(?:at least|minimum|min|more than|over)\s*(\d+(?:\.\d+)?)\s*g?\s*(?:of\s*)?protein",
            r"protein\s*(?:at least|minimum|min)\s*(\d+(?:\.\d+)?)\s*g?",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text
            )

            if match:
                return float(match.group(1))

        return None

    def _extract_max_protein(
        self,
        text: str
    ) -> float | None:

        patterns = [
            r"(?:less than|below|max|maximum|at most)\s*(\d+(?:\.\d+)?)\s*g?\s*(?:of\s*)?protein",
            r"protein\s*(?:less than|below|max|maximum)\s*(\d+(?:\.\d+)?)\s*g?",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text
            )

            if match:
                return float(match.group(1))

        return None

     
    # SUGAR
     

    def _extract_max_sugar(
        self,
        text: str
    ) -> float | None:

        patterns = [
            r"(?:less than|below|max|maximum|at most)\s*(\d+(?:\.\d+)?)\s*g?\s*(?:of\s*)?(?:added\s*)?sugar",
            r"(?:low|low in)\s*(?:added\s*)?sugar",
        ]

        # Explicit numeric sugar constraint
        for pattern in patterns[:1]:

            match = re.search(
                pattern,
                text
            )

            if match:
                return float(match.group(1))

        # "low sugar" is a semantic requirement.
        # We don't invent a numeric threshold here.
        if re.search(patterns[1], text):
            return None

        return None
