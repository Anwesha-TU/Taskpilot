from agent.requirement_extractor import RequirementExtractor


class TestRequirementExtractor:

    def setup_method(self):
        self.extractor = RequirementExtractor()

    def test_extract_category(self):
        result = self.extractor.extract(
            "Find a protein bar"
        )

        assert result["category"] == "protein_bar"

    def test_extract_max_price(self):
        result = self.extractor.extract(
            "Find a protein bar under ₹150"
        )

        assert result["category"] == "protein_bar"
        assert result["max_price"] == 150.0

    def test_extract_min_protein(self):
        result = self.extractor.extract(
            "Find a protein bar under ₹150 "
            "with at least 20g protein"
        )

        assert result["category"] == "protein_bar"
        assert result["max_price"] == 150.0
        assert result["min_protein"] == 20.0

    def test_extract_max_added_sugar(self):
        result = self.extractor.extract(
            "Find a protein bar under ₹150 "
            "with at least 20g protein "
            "and less than 5g added sugar"
        )

        assert result["category"] == "protein_bar"
        assert result["max_price"] == 150.0
        assert result["min_protein"] == 20.0
        assert result["max_added_sugar"] == 5.0

    def test_extract_below_price(self):
        result = self.extractor.extract(
            "Recommend a protein bar below ₹200"
        )

        assert result["category"] == "protein_bar"
        assert result["max_price"] == 200.0

    def test_extract_minimum_protein(self):
        result = self.extractor.extract(
            "Recommend a protein bar "
            "with minimum 25g protein"
        )

        assert result["category"] == "protein_bar"
        assert result["min_protein"] == 25.0

    def test_extract_complete_requirement(self):
        result = self.extractor.extract(
            "Find a protein bar under ₹150 "
            "with at least 20g protein "
            "and less than 5g added sugar"
        )

        expected = {
            "category": "protein_bar",
            "max_price": 150.0,
            "min_protein": 20.0,
            "max_added_sugar": 5.0,
        }

        assert result == expected

    def test_no_constraints_for_unknown_goal(self):
        result = self.extractor.extract(
            "Tell me something interesting"
        )

        assert isinstance(result, dict)

    def test_extract_case_insensitive(self):
        result = self.extractor.extract(
            "FIND A PROTEIN BAR UNDER ₹150"
        )

        assert result["category"] == "protein_bar"
        assert result["max_price"] == 150.0


if __name__ == "__main__":
    import pytest

    pytest.main()
