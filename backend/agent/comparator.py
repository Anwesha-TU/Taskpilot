from typing import Any, Dict, List


class ProductComparator:
    """
    Compares and ranks products against the user's requirements.

    The comparator performs two levels of evaluation:

    1. Hard constraints
       - category
       - maximum/minimum price
       - minimum/maximum protein
       - maximum added sugar
       - availability

    2. Soft preferences
       - higher protein
       - lower added sugar
       - lower price

    This allows the agent to distinguish between:
        - products that satisfy the requirements
        - products that are better choices among those valid products
        - products that are close matches when no exact match exists
    """

    def compare(
        self,
        products: List[Dict[str, Any]],
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:

        if not products:
            return {
                "success": False,
                "message": "No products available for comparison.",
                "total_products": 0,
                "valid_products": 0,
                "ranked_products": [],
                "best_product": None,
                "exact_match": False
            }

        evaluated_products = []

        for product in products:

            evaluation = self._evaluate_product(
                product,
                constraints
            )

            evaluated_products.append(evaluation)

        
        # Separate exact matches from approximate matches
        

        valid_products = [
            item
            for item in evaluated_products
            if item["meets_constraints"]
        ]

        if valid_products:

            candidates = valid_products
            exact_match = True

        else:

            # If no exact match exists, rank the closest
            # alternatives instead of returning nothing.

            candidates = evaluated_products
            exact_match = False

        
        # Sort by score
        

        candidates.sort(
            key=lambda item: item["score"],
            reverse=True
        )

        
        # Assign ranking
        

        for index, item in enumerate(
            candidates,
            start=1
        ):

            item["rank"] = index

        best_product = (
            candidates[0]
            if candidates
            else None
        )

        return {
            "success": True,
            "message": (
                "Products compared successfully."
            ),
            "total_products": len(products),
            "valid_products": len(valid_products),
            "ranked_products": candidates,
            "best_product": best_product,
            "exact_match": exact_match
        }

    
    # PRODUCT EVALUATION
    

    def _evaluate_product(
        self,
        product: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:

        hard_score = 0.0
        preference_score = 0.0

        reasons: List[str] = []
        violations: List[str] = []

        
        # CATEGORY
        

        category = constraints.get(
            "category"
        )

        if category:

            if product.get("category") == category:

                hard_score += 20

                reasons.append(
                    "Matches the requested category."
                )

            else:

                violations.append(
                    "Does not match the requested category."
                )

        
        # PRICE
        

        price = product.get("price")

        max_price = constraints.get(
            "max_price"
        )

        min_price = constraints.get(
            "min_price"
        )

        if price is not None:

            # ----------------------------------------------
            # Maximum price
            # ----------------------------------------------

            if max_price is not None:

                if price <= max_price:

                    hard_score += 25

                    reasons.append(
                        f"Price ₹{price} is within "
                        f"the ₹{max_price} limit."
                    )

                    # Lower price is a soft preference.
                    #
                    # A product close to the budget gets
                    # slightly less preference than a cheaper
                    # product, without making price dominate
                    # the nutritional requirements.

                    if max_price > 0:

                        price_ratio = (
                            price / max_price
                        )

                        preference_score += max(
                            0,
                            5 * (1 - price_ratio)
                        )

                else:

                    violations.append(
                        f"Price ₹{price} exceeds "
                        f"the ₹{max_price} limit."
                    )

            # ----------------------------------------------
            # Minimum price
            # ----------------------------------------------

            if min_price is not None:

                if price >= min_price:

                    hard_score += 10

                    reasons.append(
                        f"Price ₹{price} meets "
                        f"the ₹{min_price} minimum."
                    )

                else:

                    violations.append(
                        f"Price ₹{price} is below "
                        f"the ₹{min_price} minimum."
                    )

        
        # PROTEIN
        

        protein = product.get(
            "protein_g"
        )

        min_protein = constraints.get(
            "min_protein"
        )

        max_protein = constraints.get(
            "max_protein"
        )

        if protein is not None:

            # ----------------------------------------------
            # Minimum protein
            # ----------------------------------------------

            if min_protein is not None:

                if protein >= min_protein:

                    hard_score += 25

                    reasons.append(
                        f"Provides {protein}g protein, "
                        f"meeting the {min_protein}g minimum."
                    )

                    # Higher protein is a soft preference.

                    protein_bonus = min(
                        protein,
                        30
                    ) * 0.5

                    preference_score += protein_bonus

                else:

                    violations.append(
                        f"Provides only {protein}g protein; "
                        f"minimum is {min_protein}g."
                    )

            # ----------------------------------------------
            # Maximum protein
            # ----------------------------------------------

            if max_protein is not None:

                if protein <= max_protein:

                    hard_score += 10

                    reasons.append(
                        f"Protein content of {protein}g "
                        f"is within the {max_protein}g maximum."
                    )

                else:

                    violations.append(
                        f"Protein content of {protein}g "
                        f"exceeds the {max_protein}g maximum."
                    )

        
        # ADDED SUGAR
        

        added_sugar = product.get(
            "added_sugar_g"
        )

        max_added_sugar = constraints.get(
            "max_added_sugar"
        )

        if added_sugar is not None:

            # ----------------------------------------------
            # Explicit sugar constraint
            # ----------------------------------------------

            if max_added_sugar is not None:

                if added_sugar <= max_added_sugar:

                    hard_score += 20

                    reasons.append(
                        f"Added sugar is {added_sugar}g, "
                        f"within the {max_added_sugar}g limit."
                    )

                else:

                    violations.append(
                        f"Added sugar is {added_sugar}g, "
                        f"above the {max_added_sugar}g limit."
                    )

            # ----------------------------------------------
            # Soft sugar preference
            # ----------------------------------------------

            # Lower added sugar is generally preferred,
            # even when the user did not explicitly provide
            # a sugar constraint.

            sugar_bonus = max(
                0,
                10 - min(
                    float(added_sugar),
                    10
                )
            )

            preference_score += sugar_bonus

            if max_added_sugar is None:

                if added_sugar <= 5:

                    reasons.append(
                        f"Has relatively low added sugar "
                        f"({added_sugar}g)."
                    )

                elif added_sugar > 10:

                    reasons.append(
                        f"Has relatively high added sugar "
                        f"({added_sugar}g)."
                    )

        
        # AVAILABILITY
        

        if product.get("available") is True:

            hard_score += 10

            reasons.append(
                "Product is currently available."
            )

        else:

            violations.append(
                "Product is not currently available."
            )

        
        # CONSTRAINT STATUS
        

        meets_constraints = (
            len(violations) == 0
        )

        
        # Penalize violations
        

        violation_penalty = (
            len(violations) * 30
        )

        final_score = (
            hard_score
            + preference_score
            - violation_penalty
        )

        
        # Add ranking explanation
        

        if meets_constraints:

            if preference_score > 0:

                reasons.append(
                    "Ranked using nutritional and "
                    "value preferences among valid products."
                )

        else:

            reasons.append(
                "Ranked as an approximate match because "
                "one or more constraints were not satisfied."
            )

        return {
            "product": product,
            "score": round(
                final_score,
                2
            ),
            "hard_score": round(
                hard_score,
                2
            ),
            "preference_score": round(
                preference_score,
                2
            ),
            "meets_constraints": meets_constraints,
            "reasons": reasons,
            "violations": violations,
            "rank": None
        }
