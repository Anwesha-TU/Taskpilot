from tools.registry import registry
from model.rag_service import run_model


@registry.register(
    "analyze_ingredients",
    "Analyze food ingredients using the NutriCoach knowledge base."
)
def analyze_ingredients(
    ingredient_text: str,
    parent_query: str | None = None
):

    try:

        if not ingredient_text.strip():
            return {
                "success": False,
                "error": "Ingredient text is empty."
            }

        result = run_model(
            ingredient_text,
            parent_query=parent_query
        )

        return {
            "success": True,
            "analysis": result
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }
