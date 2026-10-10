from agent.comparator import ProductComparator


class TestProductComparator:

    def setup_method(self):
        self.comparator = ProductComparator()

        self.products = [
            {
                "id": "P001",
                "name": "Choco Protein Bar",
                "brand": "FitFuel",
                "category": "protein_bar",
                "price": 120,
                "protein_g": 20,
                "added_sugar_g": 12,
                "available": True
            },
            {
                "id": "P002",
                "name": "Peanut Protein Bar",
                "brand": "NutriFit",
                "category": "protein_bar",
                "price": 135,
                "protein_g": 21,
                "added_sugar_g": 3,
                "available": True
            }
        ]

    def test_best_product_is_selected(self):
        constraints = {
            "category": "protein_bar",
            "max_price": 150,
            "min_protein": 20,
            "max_added_sugar": 5
        }

        result = self.comparator.compare(
            self.products,
            constraints
        )

        assert result["success"] is True
        assert result["exact_match"] is True
        assert result["valid_products"] == 1
        assert result["best_product"]["product"]["id"] == "P002"

    def test_invalid_product_is_excluded_from_valid_products(self):
        constraints = {
            "category": "protein_bar",
            "max_price": 150,
            "min_protein": 20,
            "max_added_sugar": 5
        }

        result = self.comparator.compare(
            self.products,
            constraints
        )

        valid_ids = [
            item["product"]["id"]
            for item in result["ranked_products"]
            if item["meets_constraints"]
        ]

        assert "P002" in valid_ids
        assert "P001" not in valid_ids

    def test_category_constraint(self):
        constraints = {
            "category": "protein_bar"
        }

        products = [
            self.products[0],
            {
                "id": "P003",
                "name": "Protein Shake",
                "brand": "NutriFit",
                "category": "protein_shake",
                "price": 100,
                "protein_g": 25,
                "added_sugar_g": 2,
                "available": True
            }
        ]

        result = self.comparator.compare(
            products,
            constraints
        )

        assert result["valid_products"] == 1
        assert result["best_product"]["product"]["id"] == "P001"

    def test_price_constraint(self):
        constraints = {
            "max_price": 125
        }

        result = self.comparator.compare(
            self.products,
            constraints
        )

        assert result["valid_products"] == 1
        assert result["best_product"]["product"]["id"] == "P001"

    def test_protein_constraint(self):
        constraints = {
            "min_protein": 21
        }

        result = self.comparator.compare(
            self.products,
            constraints
        )

        assert result["valid_products"] == 1
        assert result["best_product"]["product"]["id"] == "P002"

    def test_sugar_constraint(self):
        constraints = {
            "max_added_sugar": 5
        }

        result = self.comparator.compare(
            self.products,
            constraints
        )

        assert result["valid_products"] == 1
        assert result["best_product"]["product"]["id"] == "P002"

    def test_unavailable_product_is_not_valid(self):
        products = [
            {
                **self.products[1],
                "available": False
            }
        ]

        result = self.comparator.compare(
            products,
            {}
        )

        assert result["valid_products"] == 0
        assert result["exact_match"] is False
        assert result["best_product"] is not None
        assert result["best_product"]["product"]["id"] == "P002"

    def test_no_products(self):
        result = self.comparator.compare(
            [],
            {}
        )

        assert result["success"] is False
        assert result["total_products"] == 0
        assert result["valid_products"] == 0
        assert result["ranked_products"] == []
        assert result["best_product"] is None
        assert result["exact_match"] is False

    def test_ranking_contains_scores(self):
        constraints = {
            "category": "protein_bar"
        }

        result = self.comparator.compare(
            self.products,
            constraints
        )

        for item in result["ranked_products"]:
            assert "score" in item
            assert "hard_score" in item
            assert "preference_score" in item
            assert "meets_constraints" in item
            assert "reasons" in item
            assert "violations" in item
            assert "rank" in item

    def test_lower_sugar_is_preferred(self):
        constraints = {
            "category": "protein_bar"
        }

        result = self.comparator.compare(
            self.products,
            constraints
        )

        assert result["best_product"]["product"]["id"] == "P002"
