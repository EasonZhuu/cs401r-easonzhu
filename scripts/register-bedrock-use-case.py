"""Register the approved course use case, then verify Anthropic model access."""

import argparse
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import boto3
from botocore.config import Config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submit", action="store_true",
                        help="Submit only if no use-case form is already registered")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    backend = (root / "infrastructure/environments/dev/backend.tf").read_text()
    match = re.search(r'northstar-tfstate-(\d{12})', backend)
    if not match:
        raise ValueError("Course account not found in Terraform backend")
    session = boto3.Session(region_name="us-east-1")
    config = Config(connect_timeout=5, read_timeout=30,
                    retries={"total_max_attempts": 1, "mode": "standard"})
    identity = session.client("sts", config=config).get_caller_identity()
    if identity["Account"] != match.group(1):
        raise RuntimeError("AWS account differs from the course Terraform backend")
    control = session.client("bedrock", config=config)
    runtime = session.client("bedrock-runtime", config=config)
    form = {
        "companyName": "Brigham Young University",
        "companyWebsite": "https://cs.byu.edu",
        "intendedUsers": "0",
        "industryOption": "Education",
        "otherIndustryOption": "Higher Education",
        "useCases": (
            "University coursework: retrieval-augmented retention offer generation "
            "over synthetic retail data. Internal educational use only. "
            "No production traffic and no real personal data."
        ),
    }
    submitted = False
    try:
        saved = control.get_use_case_for_model_access()
    except control.exceptions.ResourceNotFoundException:
        if not args.submit:
            print(json.dumps(form, indent=2))
            print("No existing form. Submission requires --submit.")
            return 2
        control.put_use_case_for_model_access(formData=json.dumps(form).encode())
        submitted = True
        print("PASS use-case form submitted", flush=True)
        saved = control.get_use_case_for_model_access()
    payload = saved["formData"]
    try:
        saved_form = json.loads(payload)
    except json.JSONDecodeError:
        # This account's GetUseCaseForModelAccess returns Base64 inside the blob.
        saved_form = json.loads(base64.b64decode(payload, validate=True))
    matches = saved_form == form
    if submitted and not matches:
        raise RuntimeError("AWS form read-back differs from submitted content")
    print("PASS AWS confirms a registered use-case form", flush=True)
    print(f"Course form fields match: {matches}", flush=True)

    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "account": identity["Account"],
        "region": "us-east-1",
        "submitted_this_run": submitted,
        "form_registered": True,
        "form_readback_matches_course_template": matches,
    }
    if submitted:
        report["submitted_form"] = form
    try:
        response = runtime.converse(
            modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            messages=[{"role": "user", "content": [{"text": "Reply with OK"}]}],
            inferenceConfig={"maxTokens": 10},
        )
    except runtime.exceptions.ResourceNotFoundException as error:
        report["haiku"] = {"status": "PENDING", "error": error.response["Error"]}
        print("PENDING Haiku access: form registered; propagation may take 15 minutes",
              flush=True)
    else:
        answer = "".join(part.get("text", "")
                         for part in response["output"]["message"]["content"]).strip()
        if not answer:
            raise ValueError("Haiku returned no text")
        report["haiku"] = {"status": "PASS", "response": answer,
                           "usage": response.get("usage", {})}
        print(f"PASS Haiku actual invocation: {answer!r}", flush=True)
    output = root / "docs/lab3-bedrock-registration.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {output}", flush=True)
    return 0 if report["haiku"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
