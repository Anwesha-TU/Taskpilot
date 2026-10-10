from typing import Any, Dict

from agent.state import AgentState


class AgentVerifier:
    """
    Verifies the final recommendation produced by the agent.

    Verification checks:
        1. A recommendation exists.
        2. The recommended product satisfies the extracted constraints.
        3. The product is available.
        4. The recommendation came from the comparison/ranking stage.
    """

    def verify(
        self,
        state: AgentState
    ) -> Dict[str, Any]:

        
        # Find the latest recommendation
        

        recommendation = None

        for observation in reversed(state.observations):

            if observation.get("type") == "recommendation":

                recommendation = observation.get("data")
                break

        if not recommendation:
            result = {
                "valid": False,
                "message": "No recommendation is available for verification."
            }

            state.verification_result = result
            return result

        
        # Extract product
        

        product = recommendation.get("product")

        if not product:

            result = {
                "valid": False,
                "message": "Recommendation does not contain a product."
            }

            state.verification_result = result
            return result

        
        # Extract constraints
        

        constraints = state.constraints or {}

        violations = []

        
        # Category
        

        requested_category = constraints.get("category")

        if (
            requested_category
            and product.get("category") != requested_category
        ):
            violations.append(
                f"Product category '{product.get('category')}' "
                f"does not match requested category "
                f"'{requested_category}'."
            )

        
        # Maximum price
        

        max_price = constraints.get("max_price")

        if max_price is not None:

            price = product.get("price")

            if price is None:

                violations.append(
                    "Product price is unavailable."
                )

            elif float(price) > float(max_price):

                violations.append(
                    f"Product price ₹{price} exceeds "
                    f"the maximum allowed price of ₹{max_price}."
                )

        
        # Minimum protein
        

        min_protein = constraints.get("min_protein")

        if min_protein is not None:

            protein = product.get("protein_g")

            if protein is None:

                violations.append(
                    "Product protein information is unavailable."
                )

            elif float(protein) < float(min_protein):

                violations.append(
                    f"Product provides {protein}g protein, "
                    f"below the required minimum of "
                    f"{min_protein}g."
                )

        
        # Maximum added sugar
        

        max_added_sugar = constraints.get("max_added_sugar")

        if max_added_sugar is not None:

            added_sugar = product.get("added_sugar_g")

            if added_sugar is None:

                violations.append(
                    "Product added-sugar information is unavailable."
                )

            elif float(added_sugar) > float(max_added_sugar):

                violations.append(
                    f"Product contains {added_sugar}g added sugar, "
                    f"above the maximum allowed "
                    f"{max_added_sugar}g."
                )

        
        # Availability
        

        if product.get("available") is False:

            violations.append(
                "Product is currently unavailable."
            )

        
        # Final verification result
        

        if violations:

            result = {
                "valid": False,
                "message": "The selected product failed verification.",
                "best_product": product,
                "score": recommendation.get("score"),
                "rank": recommendation.get("rank"),
                "meets_constraints": False,
                "exact_match": False,
                "violations": violations
            }

            state.verification_result = result

            return result

        
        # Successful verification
        

        result = {
            "valid": True,
            "message": (
                "The selected product passed "
                "constraint-based verification."
            ),
            "best_product": product,
            "score": recommendation.get("score"),
            "rank": recommendation.get("rank"),
            "meets_constraints": True,
            "exact_match": recommendation.get(
                "exact_match",
                True
            )
        }

        state.verification_result = result

        return result
