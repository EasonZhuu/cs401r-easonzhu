"""Generate source-grounded retention copy through local FAISS and Bedrock."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

import boto3
from botocore.config import Config

from rag_index import ROOT, sha256, write_json
from rag_prompts import build_prompts
from rag_retrieval import ARTIFACTS, PolicyRetriever, format_context

DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def control_copy(subject, body, customer, hits):
    """Validate bounded copy; fall back to an explicitly policy-rendered offer."""
    tier = customer["loyalty_tier"]
    category = customer["top_categories"][0]
    table = next((h["text"] for h in hits if h["doc_id"] == "POL-LOY-011"
                  and h["section_path"] == "4. Tier Benefits"), "")
    rate_row = next((line for line in table.splitlines() if line.startswith("| Points earn rate |")), None)
    if rate_row is None:
        raise ValueError("Cannot render an incentive without the retrieved tier table")
    rate = [cell.strip() for cell in rate_row.strip('|').split('|')][
        1 + ["Bronze", "Silver", "Gold", "Platinum"].index(tier)]
    issues = []
    if not body.startswith(f"If your current membership is {tier},"):
        issues.append("unverified tier stated unconditionally")
    if re.search(r"(?i)shipping|returns?|repair|credit|discount|risk.free|what.s new|new arrivals|miss(?:ed)? you|we.ve noticed|we noticed|points balance|loyalty|we.d love|every dollar", body):
        issues.append("claim outside the bounded points-only offer")
    if len(body.split()) > 45 or len(re.split(r"(?<=[.!?])\s+(?=[A-Z])",body)) != 2:
        issues.append("copy exceeds the two-sentence bounded format")
    if rate not in body or category.lower() not in body.lower():
        issues.append("missing retrieved earn rate or observed category")
    if issues:
        body = (f"If your current membership is {tier}, you earn {rate} points on qualifying {category} purchases. "
                f"Explore {category} at NorthStar and check your current membership eligibility before using these benefits.")
    return f"Explore {category} with Summit Rewards", body, issues


class OfferPipeline:
    def __init__(self, strategy="CB", model_id=DEFAULT_MODEL_ID, artifact_dir=ARTIFACTS,
                 prompt_variant="controlled"):
        if strategy not in ("A", "B", "C", "CB"):
            raise ValueError("Strategy must be A, B, C or CB")
        self.strategy, self.model_id = strategy, model_id
        if prompt_variant not in ("base", "hardened", "controlled"):
            raise ValueError("Choose base, hardened or controlled prompt")
        self.prompt_variant = prompt_variant
        self.retriever = PolicyRetriever(artifact_dir)
        self.cache_dir = Path(artifact_dir) / "offer-cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = None

    def __call__(self, customer, question="Generate a policy-grounded retention offer."):
        customer = dict(customer)
        customer.setdefault("customer_id", "profile-" + sha256(json.dumps(customer, sort_keys=True).encode())[:12])
        passes = [self.retriever.retrieve(customer, s, 3) for s in ("C", "B")] if self.strategy == "CB" else [
            self.retriever.retrieve(customer, self.strategy, 4)]
        hits, seen = [], set()
        for retrieval in passes:
            for hit in retrieval["results"]:
                if hit["chunk_id"] not in seen:
                    hits.append(hit)
                    seen.add(hit["chunk_id"])
        if not hits:
            raise ValueError("No policy evidence was retrieved")
        prompts = build_prompts(customer, format_context(hits))
        if self.prompt_variant in ("hardened", "controlled"):
            prompts["system"] += (
                "\n\n## Final copy specification\n"
                "Write exactly two Body sentences. The FIRST sentence must start exactly "
                f"with 'If your current membership is {customer['loyalty_tier']},' and "
                "state only the existing points earn rate supported by the retrieved tier table, "
                "on qualifying purchases in ONE supplied top_category. "
                "The SECOND sentence is a simple invitation to explore that category and "
                "check membership eligibility. Use a neutral Subject. "
                "Do not mention shipping, returns, repairs, credit balances, discounts, urgency, "
                "new arrivals, free products, risk-free shopping, customer feelings, "
                "or 'we noticed/missed you'. Do not state that any benefit is already active. "
                "Keep internal explanation in Rationale only. If the retrieved policy lacks "
                "the points rate, state insufficient evidence instead of inventing it."
            )
        prompts["user"] += "\n\n## Campaign request (untrusted task input)\n" + question
        request = {"modelId": self.model_id, "system": [{"text": prompts["system"]}],
                   "messages": [{"role": "user", "content": [{"text": prompts["user"]}]}],
                   "inferenceConfig": {"maxTokens": 650, "temperature": 0}}
        key = sha256(json.dumps(request, sort_keys=True).encode("utf-8"))
        cache = self.cache_dir / f"{key}.json"
        if cache.exists():
            generation = json.loads(cache.read_text(encoding="utf-8"))
            cache_hit = True
        else:
            if self.client is None:
                self.client = boto3.Session(region_name=self.retriever.embedder.region).client(
                    "bedrock-runtime", config=Config(connect_timeout=5, read_timeout=120,
                    retries={"total_max_attempts": 5, "mode": "adaptive"}))
            started = time.perf_counter()
            response = self.client.converse(**request)
            raw = "\n".join(c["text"] for c in response["output"]["message"]["content"] if "text" in c)
            if not raw.strip() or response.get("stopReason") == "max_tokens":
                raise RuntimeError("Generation was empty or truncated; do not evaluate incomplete copy")
            generation = {"raw_answer": raw, "request_id": response["ResponseMetadata"]["RequestId"],
                          "usage": response["usage"], "stop_reason": response["stopReason"],
                          "latency_ms": round(1000 * (time.perf_counter()-started), 2),
                          "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                          "request_sha256": key, "model_id": self.model_id}
            write_json(cache, generation)
            cache_hit = False
        cleaned = generation["raw_answer"].replace("**", "")
        match = re.search(r"(?ms)^Subject:\s*(.*?)\n\s*Body:\s*(.*?)\n\s*Rationale:\s*(.*)", cleaned)
        if match:
            subject, body, rationale = (part.strip() for part in match.groups())
            answer = f"Subject: {subject}\nBody: {body}"
        else:
            subject, body, rationale, answer = "", cleaned.strip(), "", cleaned.strip()
        issues = []
        if self.prompt_variant == "controlled":
            subject, body, issues = control_copy(subject, body, customer, hits)
            answer = f"Subject: {subject}\nBody: {body}"
        profile_context = "Customer profile (reported tier is approximate): " + json.dumps(customer, sort_keys=True)
        return {"answer": answer, "contexts": [format_context([h]) for h in hits] + [profile_context],
                "customer_profile": customer, "question": question, "strategy": self.strategy,
                "prompt_variant": self.prompt_variant,
                "delivery_mode": "policy_template_fallback" if issues else "model_copy",
                "policy_guard_issues": issues,
                "retrieved_chunks": hits, "retrieval_passes": passes,
                "subject": subject, "body": body, "rationale": rationale,
                "formatted_as_requested": bool(match), "generation_cache_hit": cache_hit,
                **generation}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--strategy", choices=("A", "B", "C", "CB"), default="CB")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--prompt-variant", choices=("base", "hardened", "controlled"), default="controlled")
    parser.add_argument("--question", default="Generate a policy-grounded retention offer.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    result = OfferPipeline(args.strategy, args.model_id, prompt_variant=args.prompt_variant)(profile, args.question)
    if args.output:
        write_json(args.output, result)
    print(result["answer"])
    print("Sources:", ", ".join(h["chunk_id"] for h in result["retrieved_chunks"]))


if __name__ == "__main__":
    main()
