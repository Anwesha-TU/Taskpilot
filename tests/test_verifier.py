from agent.state import AgentState
from agent.verifier import AgentVerifier


class TestAgentVerifier:

    def setup_method(self):
        self.verifier = AgentVerifier()

        self.valid_product = {
            "id": "P002",
            "name": "Peanut Protein Bar",
            "brand": "NutriFit",
            "category": "protein_bar",
            "price": 135,
            "protein_g": 21,
            "added_sugar_g": 3,
            "available": True
        }

        self.recommendation = {
            "product": self.valid_product,
            "score": 45.5,
            "rank": 1,
            "exact_match": True
        }

    def create_state(self, constraints=None):
        state = AgentState(
            goal="Find a protein bar",
            constraints=constraints or {}
        )

        state.add_observation(
            observation_type="recommendation",
            data=self.recommendation
        )

        return state

    def test_valid_recommendation_passes(self):
        state = self.create_state({
            "category": "protein_bar",
            "max_price": 150,
            "min_protein": 20,
            "max_added_sugar": 5
        })

        result = self.verifier.verify(state)

        assert result["valid"] is True
        assert result["best_product"]["id"] == "P002"
        assert result["meets_constraints"] is True
        assert state.verification_result == result

    def test_missing_recommendation_fails(self):
        state = AgentState(
            goal="Find a protein bar",
            constraints={
                "category": "protein_bar"
            }
        )

        result = self.verifier.verify(state)

        assert result["valid"] is False
        assert "No recommendation" in result["message"]
        assert state.verification_result == result

    def test_missing_product_fails(self):
        state = AgentState(
            goal="Find a protein bar",
            constraints={}
        )

        state.add_observation(
            observation_type="recommendation",
            data={
                "score": 30,
                "rank": 1
            }
        )

        result = self.verifier.verify(state)

        assert result["valid"] is False
        assert "does not contain a product" in result["message"]

    def test_category_violation_fails(self):
        state = self.create_state({
            "category": "protein_shake"
        })

        result = self.verifier.verify(state)

        assert result["valid"] is False
        assert result["meets_constraints"] is False
        assert result["exact_match"] is False
        assert len(result["violations"]) == 1

    def test_price_violation_fails(self):
        state = self.create_state({
            "max_price": 100
        })

        result = self.verifier.verify(state)

        assert result["valid"] is False
        assert any(
            "exceeds" in violation
            for violation in result["violations"]
        )

    def test_protein_violation_fails(self):
        state = self.create_state({
            "min_protein": 25
        })

        result = self.verifier.verify(state)

        assert result["valid"] is False
        assert any(
            "below the required minimum" in violation
            for violation in result["violations"]
        )

    def test_added_sugar_violation_fails(self):
        state = self.create_state({
            "max_added_sugar": 2
        })

        result = self.verifier.verify(state)

        assert result["valid"] is False
        assert any(
            "above the maximum allowed" in violation
            for violation in result["violations"]
        )

    def test_unavailable_product_fails(self):
        unavailable_product = {
            **self.valid_product,
            "available": False
        }

        state = AgentState(
            goal="Find a protein bar",
            constraints={}
        )

        state.add_observation(
            observation_type="recommendation",
            data={
                **self.recommendation,
                "product": unavailable_product
            }
        )

        result = self.verifier.verify(state)

        assert result["valid"] is False
        assert any(
            "currently unavailable" in violation
            for violation in result["violations"]
        )

    def test_multiple_violations_are_reported(self):
        state = self.create_state({
            "category": "protein_shake",
            "max_price": 100,
            "min_protein": 25,
            "max_added_sugar": 2
        })

        result = self.verifier.verify(state)

        assert result["valid"] is False
        assert len(result["violations"]) == 4

    def test_missing_price_information_fails(self):
        product = {
            **self.valid_product
        }
        del product["price"]

        state = AgentState(
            goal="Find a protein bar",
            constraints={
                "max_price": 150
            }
        )

        state.add_observation(
            observation_type="recommendation",
            data={
                **self.recommendation,
                "product": product
            }
        )

        result = self.verifier.verify(state)

        assert result["valid"] is False
        assert any(
            "price is unavailable" in violation
            for violation in result["violations"]
        )

    def test_missing_protein_information_fails(self):
        product = {
            **self.valid_product
        }
        del product["protein_g"]

        state = AgentState(
            goal="Find a protein bar",
            constraints={
                "min_protein": 20
            }
        )

        state.add_observation(
            observation_type="recommendation",
            data={
                **self.recommendation,
                "product": product
            }
        )

        result = self.verifier.verify(state)

        assert result["valid"] is False
        assert any(
            "protein information is unavailable" in violation
            for violation in result["violations"]
        )

    def test_missing_sugar_information_fails(self):
        product = {
            **self.valid_product
        }
        del product["added_sugar_g"]

        state = AgentState(
            goal="Find a protein bar",
            constraints={
                "max_added_sugar": 5
            }
        )

        state.add_observation(
            observation_type="recommendation",
            data={
                **self.recommendation,
                "product": product
            }
        )

        result = self.verifier.verify(state)

        assert result["valid"] is False
        assert any(
            "added-sugar information is unavailable" in violation
            for violation in result["violations"]
        )

    def test_latest_recommendation_is_verified(self):
        state = AgentState(
            goal="Find a protein bar",
            constraints={
                "max_price": 150
            }
        )

        older_product = {
            **self.valid_product,
            "price": 90
        }

        state.add_observation(
            observation_type="recommendation",
            data={
                "product": older_product,
                "score": 20,
                "rank": 2
            }
        )

        state.add_observation(
            observation_type="recommendation",
            data=self.recommendation
        )

        result = self.verifier.verify(state)

        assert result["valid"] is True
        assert result["best_product"]["id"] == "P002"
