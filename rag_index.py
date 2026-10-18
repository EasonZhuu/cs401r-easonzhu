"""Prepare source-traceable policy sections and cached Titan V2 embeddings."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import boto3
from botocore.config import Config
import numpy as np

ROOT = Path(__file__).resolve().parent
MODEL_ID = "amazon.titan-embed-text-v2:0"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def chunk_documents(corpus_dir, max_words=250):
    """Keep each Markdown section whole, including its tables and qualifications.

    These four short documents fit within the word limit section by section.
    Zero overlap avoids duplicating complete sections. If a future section grows
    beyond the limit, fail explicitly rather than silently breaking its table.
    """
    if max_words <= 0:
        raise ValueError("max_words must be positive")
    files = sorted(Path(corpus_dir).glob("*.md"))
    if not files:
        raise ValueError("Policy corpus is empty")
    chunks, documents = [], []
    doc_ids = set()
    for path in files:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        title = re.search(r"(?m)^# ([^\r\n]+)", text).group(1)
        doc_id = re.search(r"\*\*Document ID:\*\* (\S+)", text).group(1)
        effective = re.search(r"\*\*Effective:\*\* (\S+)", text).group(1)
        if doc_id in doc_ids:
            raise ValueError(f"Duplicate policy document ID: {doc_id}")
        doc_ids.add(doc_id)
        headings = list(re.finditer(r"(?m)^(#{2,3}) ([^\r\n]+)", text))
        spans = [(0, headings[0].start() if headings else len(text), ["Document metadata"])]
        parent = None
        for index, heading in enumerate(headings):
            section = heading.group(2).strip()
            if heading.group(1) == "##":
                parent, breadcrumb = section, [section]
            else:
                breadcrumb = ([parent] if parent else []) + [section]
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            spans.append((heading.start(), end, breadcrumb))
        count = 0
        pending_start = None
        for start, end, breadcrumb in spans:
            if pending_start is not None:
                start = pending_start
            content = text[start:end]
            if not content.strip():
                continue
            body_without_headings = re.sub(r"(?m)^#{2,3} [^\r\n]*(?:\r?\n|$)", "", content)
            if not body_without_headings.strip():
                pending_start = start
                continue
            pending_start = None
            words = len(content.split())
            if words > max_words:
                raise ValueError(f"{path.name}: {' / '.join(breadcrumb)} has {words} words; "
                                 "review the section before changing max_words")
            count += 1
            content_sha = sha256(content.encode("utf-8"))
            section_path = " / ".join(breadcrumb)
            embedding_text = f"Document: {doc_id} | {title}\nSection: {section_path}\n\n{content}"
            if len(embedding_text) > 50000:
                raise ValueError("Section exceeds Titan's character limit")
            chunks.append({"chunk_id": f"{doc_id}:{count:03d}:{content_sha[:10]}",
                           "doc_id": doc_id, "source": path.name, "title": title,
                           "effective_date": effective, "section_path": section_path,
                           "source_sha256": sha256(raw), "content_sha256": content_sha,
                           "source_start_char": start, "source_end_char": end,
                           "word_count": words, "text": content,
                           "embedding_text": embedding_text})
        if pending_start is not None:
            raise ValueError(f"{path.name} ends with an empty policy heading")
        documents.append({"source": path.name, "doc_id": doc_id,
                          "source_sha256": sha256(raw), "chunks": count})
    return chunks, documents


class TitanEmbedder:
    """One reusable runtime client; every successful result is cached by input/config."""
    def __init__(self, cache_dir, region="us-east-1", dimensions=1024):
        if dimensions not in (256, 512, 1024):
            raise ValueError("Titan V2 dimensions must be 256, 512 or 1024")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.region, self.dimensions = region, dimensions
        self.model_id, self.normalize = MODEL_ID, True
        self.client = None

    def validate_vector(self, values):
        vector = np.asarray(values, dtype=np.float32)
        if vector.shape != (self.dimensions,) or not np.isfinite(vector).all():
            raise ValueError("Invalid Titan embedding shape or non-finite values")
        if not np.isclose(np.linalg.norm(vector), 1.0, atol=1e-4, rtol=0):
            raise ValueError("Titan did not return the requested unit-normalized vector")
        return vector

    def embed_text(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 50000:
            raise ValueError("Titan expects nonempty text of at most 50000 characters")
        identity = {"model_id": self.model_id, "region": self.region,
                    "dimensions": self.dimensions, "normalize": self.normalize,
                    "input_sha256": sha256(text.encode("utf-8"))}
        key = sha256(json.dumps(identity, sort_keys=True).encode("utf-8"))
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            if any(cached.get(name) != value for name, value in identity.items()):
                raise ValueError(f"Embedding cache identity mismatch: {path.name}")
            return self.validate_vector(cached["embedding"]), dict(cached, cache_hit=True)
        if self.client is None:
            session = boto3.Session(region_name=self.region)
            self.client = session.client("bedrock-runtime", config=Config(
                connect_timeout=5, read_timeout=60,
                retries={"total_max_attempts": 5, "mode": "adaptive"}))
        # Titan embeddings uses InvokeModel, not Converse, and accepts no
        # generation parameters such as maxTokens, temperature or topP.
        response = self.client.invoke_model(
            modelId=self.model_id, contentType="application/json", accept="application/json",
            body=json.dumps({"inputText": text, "dimensions": self.dimensions,
                             "normalize": self.normalize}))
        with closing(response["body"]) as body:
            result = json.loads(body.read())
        vector = self.validate_vector(result["embedding"])
        cached = dict(identity, embedding=vector.tolist(), input_tokens=result["inputTextTokenCount"],
                      request_id=response["ResponseMetadata"]["RequestId"],
                      created_at_utc=datetime.now(timezone.utc).isoformat())
        write_json(path, cached)
        return vector, dict(cached, cache_hit=False)


def build_embeddings(chunks, documents, output_dir, region, dimensions, max_words):
    output_dir = Path(output_dir)
    embedder = TitanEmbedder(output_dir / "cache", region, dimensions)
    vectors, requests = [], []
    started = datetime.now(timezone.utc)
    for index, chunk in enumerate(chunks):
        vector, receipt = embedder.embed_text(chunk["embedding_text"])
        vectors.append(vector)
        requests.append({"chunk_id": chunk["chunk_id"], "input_tokens": receipt["input_tokens"],
                         "request_id": receipt["request_id"], "cache_hit": receipt["cache_hit"]})
        print(f"[{index+1}/{len(chunks)}] {chunk['chunk_id']} "
              f"tokens={receipt['input_tokens']} cache_hit={receipt['cache_hit']}", flush=True)
    matrix = np.stack(vectors).astype(np.float32)
    serialized = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in chunks)
    chunks_path = output_dir / "chunks.jsonl"
    chunks_path.write_text(serialized, encoding="utf-8")
    array_path = output_dir / "embeddings.npy"
    with (output_dir / "embeddings.npy.tmp").open("wb") as stream:
        np.save(stream, matrix, allow_pickle=False)
    (output_dir / "embeddings.npy.tmp").replace(array_path)
    manifest = {"started_at_utc": started.isoformat(),
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "model_id": MODEL_ID, "region": region, "dimensions": dimensions, "normalize": True,
                "chunking": {"strategy": "markdown_sections", "max_words": max_words,
                             "size_unit": "whitespace-separated words, not Titan tokens",
                             "overlap_words": 0, "tables_split": False},
                "documents": documents, "chunks": len(chunks), "matrix_shape": list(matrix.shape),
                "matrix_dtype": str(matrix.dtype),
                "chunk_ids_in_row_order": [c["chunk_id"] for c in chunks],
                "chunks_sha256": sha256(chunks_path.read_bytes()),
                "embeddings_sha256": sha256(array_path.read_bytes()),
                "embedding_source_sha256": sha256(Path(__file__).read_bytes()),
                "new_invoke_model_calls": sum(not r["cache_hit"] for r in requests),
                "cache_hits": sum(r["cache_hit"] for r in requests),
                "input_tokens_all_chunks": sum(r["input_tokens"] for r in requests),
                "input_tokens_new_requests": sum(r["input_tokens"] for r in requests if not r["cache_hit"]),
                "requests": requests}
    write_json(output_dir / "manifest.json", manifest)
    return manifest


def verify_artifacts(corpus_dir, output_dir):
    output_dir = Path(output_dir)
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    chunks, documents = chunk_documents(corpus_dir, manifest["chunking"]["max_words"])
    saved = [json.loads(line) for line in (output_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    matrix = np.load(output_dir / "embeddings.npy", allow_pickle=False)
    if chunks != saved or documents != manifest["documents"]:
        raise ValueError("Saved chunks or source documents changed")
    if manifest["chunks_sha256"] != sha256((output_dir / "chunks.jsonl").read_bytes()):
        raise ValueError("Chunk file hash mismatch")
    if manifest["embeddings_sha256"] != sha256((output_dir / "embeddings.npy").read_bytes()):
        raise ValueError("Embedding file hash mismatch")
    if manifest["chunk_ids_in_row_order"] != [c["chunk_id"] for c in chunks]:
        raise ValueError("Embedding row mapping mismatch")
    if matrix.shape != (len(chunks), manifest["dimensions"]) or matrix.dtype != np.float32:
        raise ValueError("Embedding matrix shape or dtype mismatch")
    if not np.isfinite(matrix).all() or not np.allclose(np.linalg.norm(matrix, axis=1), 1, atol=1e-4, rtol=0):
        raise ValueError("Invalid embedding values or normalization")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=ROOT / "northstar-policy-docs")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/lab3-rag")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--dimensions", type=int, choices=(256, 512, 1024), default=1024)
    parser.add_argument("--max-words", type=int, default=250)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--embed", action="store_true", help="Invoke Titan for uncached chunks")
    modes.add_argument("--verify", action="store_true", help="Check saved outputs without network access")
    args = parser.parse_args()
    if args.verify:
        result = verify_artifacts(args.corpus_dir, args.output_dir)
        print(f"PASS saved chunks, hashes, row mapping and normalized vectors: {result['matrix_shape']}")
        return
    chunks, documents = chunk_documents(args.corpus_dir, args.max_words)
    print(json.dumps({"documents": documents, "chunks": len(chunks),
                      "word_range": [min(c['word_count'] for c in chunks), max(c['word_count'] for c in chunks)],
                      "overlap_words": 0}, indent=2))
    if args.embed:
        manifest = build_embeddings(chunks, documents, args.output_dir, args.region, args.dimensions, args.max_words)
        verify_artifacts(args.corpus_dir, args.output_dir)
        print(f"PASS embeddings saved and read back: {manifest['matrix_shape']}")


if __name__ == "__main__":
    main()
