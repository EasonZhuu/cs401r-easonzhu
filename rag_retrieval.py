"""Exact local FAISS retrieval for the three policy queries in Template 4."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import faiss
import numpy as np

from rag_index import ROOT, TitanEmbedder, sha256, verify_artifacts, write_json

ARTIFACTS = ROOT / "artifacts/lab3-rag"


def build_faiss_index(artifact_dir=ARTIFACTS, corpus_dir=ROOT / "northstar-policy-docs"):
    artifact_dir = Path(artifact_dir)
    manifest = verify_artifacts(corpus_dir, artifact_dir)
    matrix = np.load(artifact_dir / "embeddings.npy", allow_pickle=False)
    index = faiss.IndexFlatIP(manifest["dimensions"])
    index.add(np.ascontiguousarray(matrix))
    target = artifact_dir / "policy.faiss"
    temporary = artifact_dir / "policy.faiss.tmp"
    faiss.write_index(index, str(temporary))
    temporary.replace(target)
    metadata = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                "index_type": "IndexFlatIP", "faiss_version": faiss.__version__,
                "metric": "inner product on unit vectors (cosine similarity)",
                "dimensions": index.d, "vectors": index.ntotal,
                "index_sha256": sha256(target.read_bytes()),
                "chunks_sha256": manifest["chunks_sha256"],
                "embeddings_sha256": manifest["embeddings_sha256"],
                "model_id": manifest["model_id"], "region": manifest["region"],
                "normalize": manifest["normalize"],
                "chunk_ids_in_row_order": manifest["chunk_ids_in_row_order"],
                "retrieval_source_sha256": sha256(Path(__file__).read_bytes())}
    write_json(artifact_dir / "faiss-manifest.json", metadata)
    return metadata


def query_spec(customer, strategy):
    """Port the teacher's A/B/C query strings and C's document filter unchanged."""
    if strategy == "B":
        return ("final sale non-returnable exclusions expired offers cannot be reinstated "
                "retention offer validity single use combinability"), None
    tier = customer["loyalty_tier"]
    if tier not in {"Bronze", "Silver", "Gold", "Platinum"}:
        raise ValueError("A known reported loyalty tier is required")
    if strategy == "A":
        return (f"loyalty tier {tier} benefits points earn rate "
                "free shipping threshold return window birthday reward"), None
    if strategy == "C":
        ratio = float(customer["online_to_store_ratio"])
        if not 0 <= ratio <= 1:
            raise ValueError("online_to_store_ratio must lie between zero and one")
        channel = "online" if ratio > 0.5 else "in store"
        return (f"tier {tier} entitlements and shipping thresholds "
                f"for a customer who shops {channel}"), ["POL-LOY-011", "POL-SHP-007"]
    raise ValueError("Choose retrieval strategy A, B or C")


def format_context(results):
    """Carry actual chunk IDs and policy provenance into the later prompt."""
    return "\n\n".join(
        f"[{row['chunk_id']} | {row['doc_id']} | {row['section_path']}]\n{row['text']}"
        for row in results)


class PolicyRetriever:
    def __init__(self, artifact_dir=ARTIFACTS, corpus_dir=ROOT / "northstar-policy-docs"):
        artifact_dir = Path(artifact_dir)
        manifest = verify_artifacts(corpus_dir, artifact_dir)
        metadata = json.loads((artifact_dir / "faiss-manifest.json").read_text(encoding="utf-8"))
        for key in ("chunks_sha256", "embeddings_sha256", "chunk_ids_in_row_order",
                    "model_id", "region", "dimensions", "normalize"):
            if metadata[key] != manifest[key]:
                raise ValueError(f"FAISS index refers to different embedding artifacts: {key}")
        path = artifact_dir / "policy.faiss"
        if sha256(path.read_bytes()) != metadata["index_sha256"]:
            raise ValueError("FAISS index file hash mismatch")
        self.index = faiss.read_index(str(path))
        matrix = np.load(artifact_dir / "embeddings.npy", allow_pickle=False)
        if self.index.d != manifest["dimensions"] or self.index.ntotal != len(matrix):
            raise ValueError("FAISS dimensions or row count differ from the embedding matrix")
        if self.index.metric_type != faiss.METRIC_INNER_PRODUCT:
            raise ValueError("Expected an inner-product FAISS index")
        if not np.array_equal(self.index.reconstruct_n(0, self.index.ntotal), matrix):
            raise ValueError("FAISS rows differ from the source embedding matrix")
        self.chunks = [json.loads(line) for line in
                       (artifact_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
        self.embedder = TitanEmbedder(artifact_dir / "cache", manifest["region"], manifest["dimensions"])

    def search_vector(self, vector, top_k=4, doc_ids=None):
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        query = np.asarray(vector, dtype=np.float32)
        if query.shape != (self.index.d,) or not np.isfinite(query).all():
            raise ValueError("Query vector has invalid dimensions or values")
        if not np.isclose(np.linalg.norm(query), 1.0, atol=1e-4, rtol=0):
            raise ValueError("Query vector must be unit-normalized like the policy vectors")
        # The corpus has only 48 rows: scan all scores, apply the document
        # filter, THEN take top_k. This equals exact search over the allowed
        # subset and avoids losing relevant rows by filtering only a short top_k.
        scores, rows = self.index.search(np.ascontiguousarray(query[None, :]), self.index.ntotal)
        allowed = None if doc_ids is None else set(doc_ids)
        candidates = [(float(score), int(row)) for score, row in zip(scores[0], rows[0])
                      if row >= 0 and (allowed is None or self.chunks[row]["doc_id"] in allowed)]
        candidates.sort(key=lambda pair: (-pair[0], pair[1]))
        results = []
        for rank, (score, row) in enumerate(candidates[:top_k], start=1):
            chunk = self.chunks[row]
            results.append({"rank": rank, "row_id": row, "score": score,
                            "chunk_id": chunk["chunk_id"], "doc_id": chunk["doc_id"],
                            "source": chunk["source"], "section_path": chunk["section_path"],
                            "text": chunk["text"]})
        return results

    def search(self, query, top_k=4, doc_ids=None):
        vector, receipt = self.embedder.embed_text(query)
        results = self.search_vector(vector, top_k, doc_ids)
        return {"query": query, "filter_doc_ids": doc_ids, "top_k": top_k,
                "embedding_request": {key: receipt[key] for key in
                                      ("request_id", "input_tokens", "cache_hit", "input_sha256")},
                "results": results}

    def retrieve(self, customer, strategy="A", top_k=4):
        query, doc_ids = query_spec(customer, strategy)
        return dict(self.search(query, top_k, doc_ids), strategy=strategy)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=ARTIFACTS)
    parser.add_argument("--corpus-dir", type=Path, default=ROOT / "northstar-policy-docs")
    parser.add_argument("--build-index", action="store_true")
    parser.add_argument("--query", help="Optional policy search; embeds uncached queries through Titan")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--doc-id", action="append", help="Restrict results to these document IDs")
    args = parser.parse_args()
    if args.build_index:
        metadata = build_faiss_index(args.artifact_dir, args.corpus_dir)
        print(json.dumps(metadata, indent=2))
    if args.query:
        result = PolicyRetriever(args.artifact_dir, args.corpus_dir).search(args.query, args.top_k, args.doc_id)
        print(json.dumps(result, indent=2))
    if not args.build_index and not args.query:
        parser.error("Choose --build-index and/or --query")


if __name__ == "__main__":
    main()
