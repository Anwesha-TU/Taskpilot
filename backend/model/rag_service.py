import json
import os

import google.generativeai as genai
import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from google.api_core.exceptions import ResourceExhausted

# ----------------------------
# ENV + CONFIG
# ----------------------------
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not found in environment")

genai.configure(api_key=API_KEY)

BASE_DIR = os.path.dirname(__file__)
EMBEDDINGS_PATH = os.path.join(BASE_DIR, "embeddings.json")

GEMINI_MODEL = "models/gemini-3.6-flash"

# ----------------------------
# LOAD MODELS + DATA
# ----------------------------
embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

with open(EMBEDDINGS_PATH, "r", encoding="utf-8") as f:
    INGREDIENTS = json.load(f)

# ----------------------------
# VECTOR SEARCH UTILS
# ----------------------------
def cosine_similarity(a, b):
    dot_prod = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_prod / (norm_a * norm_b)


def retrieve(query, ingredients, k=3):
    query_emb = embedder.encode(query)
    scores = []
    for ing in ingredients:
        score = cosine_similarity(query_emb, np.array(ing["embedding"]))
        scores.append((score, ing))
    scores.sort(key=lambda x: x[0], reverse=True)
    return [ing for _, ing in scores[:k]]


def build_context(retrieved):
    return "\n".join(
        f"{r['name']} → {r['evidence_strength']} evidence; "
        f"{', '.join(r['health_concern_type']).lower()}"
        for r in retrieved
    )

# ----------------------------
# MAIN ENTRY (CALLED BY DJANGO)
# ----------------------------
def run_model(query: str, parent_query: str | None = None):
    retrieval_query = parent_query or query
    answer_query=query

    if not retrieval_query:
        return {
            "summary": "There is very limited information available for these ingredients.",
            "details": "The ingredient label does not provide enough evidence-backed insights.",
            "uncertainty": "Effects may vary depending on formulation and consumption frequency.",
        }

    retrieved = retrieve(retrieval_query, INGREDIENTS, k=3)

    if not retrieved:
        return {
            "summary": "There is very limited information available for these ingredients.",
            "details": "The ingredient label does not provide enough evidence-backed insights.",
            "uncertainty": "Effects may vary depending on formulation and consumption frequency.",
        }

    context = build_context(retrieved)

    prompt = f"""
You are an expert AI health co-pilot helping consumers make sense of food ingredients.

Ingredient context:
{context}

User question:
"{query}"

Rules:
- Do not make absolute disease claims
- Do not repeat ingredient names
- Use simple English
- Explain tradeoffs
- Consider uncertainty
- Answer only using the context
- Keep it short

Ingredient insights:
{context}

Respond exactly in this format:

Summary:
Details:
Uncertainty:
"""

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        text = response.text.strip()

    except ResourceExhausted:
        return {
            "summary": "Usage limit reached.",
            "details": "The AI service is temporarily busy. Please retry in a few seconds.",
            "uncertainty": "Rate limits vary depending on usage and model availability.",
        }

    except Exception as e:
        return {
            "summary": "An unexpected error occurred.",
            "details": str(e),
            "uncertainty": "The response could not be generated reliably.",
        }

    # ----------------------------
    # PARSE STRUCTURED RESPONSE
    # ----------------------------
    sections = {"summary": "", "details": "", "uncertainty": ""}
    current = None

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Summary:"):
            current = "summary"
            sections[current] = line.replace("Summary:", "").strip()
        elif line.startswith("Details:"):
            current = "details"
            sections[current] = line.replace("Details:", "").strip()
        elif line.startswith("Uncertainty:"):
            current = "uncertainty"
            sections[current] = line.replace("Uncertainty:", "").strip()
        elif current:
            sections[current] += " " + line

    return sections
