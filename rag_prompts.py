"""Render audited RAG prompt templates; retrieval and model calls are separate."""
from pathlib import Path
import re

TEMPLATES = Path(__file__).resolve().parent / "prompt_templates/offer_generation_prompts.md"
TIERS = {"Bronze", "Silver", "Gold", "Platinum"}


def template_block(number):
    source = TEMPLATES.read_text(encoding="utf-8")
    section = re.search(rf"^## Template {number}:.*?(?=^## Template \d+:|^## Evaluation Checklist|\Z)", source, re.M | re.S)
    if section is None:
        raise ValueError(f"Missing Template {number}")
    block = re.search(r"^```[^\n]*\n(.*?)^```", section.group(), re.M | re.S)
    if block is None:
        raise ValueError(f"Missing text block in Template {number}")
    return block.group(1).strip()


def profile_notes(customer):
    ratio = float(customer["online_to_store_ratio"])
    diversity = float(customer["category_diversity_score"])
    if not (0 <= ratio <= 1 and 0 <= diversity <= 1):
        raise ValueError("Profile ratios must lie between zero and one")
    channel = "mainly in-store" if ratio <= 0.30 else "mainly online" if ratio >= 0.70 else "mixed-channel"
    return (
        f"- Channel heuristic: {channel}; this is a suggestion, not a verified preference.\n"
        f"- Diversity indicates approximately {diversity * 8:g} of 8 observed categories; "
        "recommend only the supplied top_categories, not invented purchases.\n"
        "- Reported tier is approximate; lifetime value does not prove trailing "
        "12-month qualifying spend or an exact amount needed for upgrade.\n"
        "- Birthday eligibility, credit usage, points balance, destination and "
        "active promotions are not supplied; do not assume them."
    )


def build_prompts(customer, retrieved_context):
    """Return system/user text from source-labeled chunks and a supplied profile."""
    if customer["loyalty_tier"] not in TIERS:
        raise ValueError("Use a known reported tier; never invent membership")
    categories = customer["top_categories"]
    if not isinstance(categories, list) or not categories or any(not isinstance(c, str) or not c.strip() for c in categories):
        raise ValueError("Provide observed top_categories explicitly")
    if not isinstance(retrieved_context, str) or not retrieved_context.strip():
        raise ValueError("Provide source-labeled policy evidence before generation")
    values = dict(customer, top_categories=", ".join(categories),
                  profile_notes=profile_notes(customer), retrieved_context=retrieved_context)
    system = template_block(1).format_map(values) + "\n\n" + template_block(5)
    user = template_block(2).format_map(values)
    return {"system": system, "user": user}
