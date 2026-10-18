"""SageMaker framework handler for the locally trained XGBoost model."""
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import xgboost as xgb


def model_fn(model_dir):
    root = Path(model_dir)
    lineage = json.loads((root / "training-lineage.json").read_text(encoding="utf-8"))
    model_path = root / "model.xgb"
    if hashlib.sha256(model_path.read_bytes()).hexdigest() != lineage["model_sha256"]:
        raise ValueError("Model hash differs from the evaluated model")
    if xgb.__version__ != lineage["xgboost_version"]:
        raise ValueError(f"Expected XGBoost {lineage['xgboost_version']}, got {xgb.__version__}")
    model = xgb.Booster()
    model.load_model(model_path)
    if model.feature_names != lineage["feature_columns"]:
        raise ValueError("Model feature order differs from the training lineage")
    return model


def transform_fn(model, input_data, content_type, accept="application/json"):
    """Accept ordered rows, or explicitly named feature records, and return probabilities."""
    if accept.split(";", 1)[0] != "application/json":
        raise ValueError("Accept must be application/json")
    content_type = content_type.split(";", 1)[0]
    if content_type == "application/json":
        payload = json.loads(input_data)
        rows = payload["instances"] if isinstance(payload, dict) else payload
        if rows and isinstance(rows[0], dict):
            expected = set(model.feature_names)
            if any(set(row) != expected for row in rows):
                raise ValueError("Each record must contain exactly the 11 model features")
            rows = [[row[name] for name in model.feature_names] for row in rows]
        values = np.asarray(rows, dtype=np.float64)
    elif content_type == "text/csv":
        body = input_data.decode("utf-8") if isinstance(input_data, bytes) else input_data
        values = np.loadtxt(io.StringIO(body), delimiter=",", ndmin=2)
    else:
        raise ValueError("Content-Type must be application/json or text/csv")
    if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] != len(model.feature_names):
        raise ValueError("Expected a nonempty matrix with 11 features per row")
    if np.isinf(values).any():
        raise ValueError("Infinite feature values are invalid")
    matrix = xgb.DMatrix(values, feature_names=model.feature_names)
    probabilities = model.predict(matrix)
    return json.dumps({"probabilities": probabilities.tolist()}, allow_nan=False)
