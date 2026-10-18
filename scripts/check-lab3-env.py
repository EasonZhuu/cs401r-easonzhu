"""Check Lab 3's local dependencies without running coursework or calling AWS."""

import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import runpy
import sys


def main():
    os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
    os.environ["RAGAS_DO_NOT_TRACK"] = "true"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

    packages = {
        "boto3": "boto3",
        "botocore": "botocore",
        "numpy": "numpy",
        "pandas": "pandas",
        "scipy": "scipy",
        "scikit-learn": "sklearn",
        "xgboost": "xgboost",
        "matplotlib": "matplotlib",
        "sagemaker": "sagemaker",
        "mlflow": "mlflow",
        "sagemaker-mlflow": "sagemaker_mlflow",
        "ragas": "ragas",
        "langchain-community": "langchain_community",
        "langchain-aws": "langchain_aws",
        "datasets": "datasets",
        "faiss-cpu": "faiss",
        "ipykernel": "ipykernel",
        "nbformat": "nbformat",
        "nbclient": "nbclient",
    }
    versions = {}
    for distribution, module in packages.items():
        importlib.import_module(module)
        versions[distribution] = importlib.metadata.version(distribution)
        print(f"PASS import {distribution} {versions[distribution]}", flush=True)

    from sagemaker.feature_store.feature_group import FeatureGroup
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import answer_relevancy, context_recall, faithfulness
    from langchain_aws import BedrockEmbeddings, ChatBedrock

    assert all((FeatureGroup, LangchainEmbeddingsWrapper, LangchainLLMWrapper,
                answer_relevancy, context_recall, faithfulness,
                BedrockEmbeddings, ChatBedrock))
    print("PASS Feature Store and course RAGAS interfaces", flush=True)

    import faiss
    import numpy as np
    import xgboost as xgb

    vectors = np.array([[1, 0], [0, 1]], dtype=np.float32)
    index = faiss.IndexFlatL2(2)
    index.add(vectors)
    distances, positions = index.search(vectors[:1], 1)
    assert positions[0, 0] == 0 and distances[0, 0] == 0
    matrix = xgb.DMatrix(vectors, label=np.array([0, 1]))
    assert matrix.num_row() == 2 and matrix.num_col() == 2
    print("PASS FAISS search and XGBoost native libraries", flush=True)

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    training = runpy.run_path(str(root / "churn_training_skeleton.py"))
    evaluation = runpy.run_path(str(root / "evaluation_harness.py"))
    assert training["SAGEMAKER_AVAILABLE"]
    assert evaluation["RAGAS_AVAILABLE"]
    assert len(evaluation["OFFER_TEST_CASES"]) == 4
    print("PASS both course skeletons import; four RAG cases available", flush=True)
    print(json.dumps({"python": sys.version.split()[0],
                      "environment": sys.prefix,
                      "packages": versions,
                      "aws_access_tested": False}, indent=2))


if __name__ == "__main__":
    main()
