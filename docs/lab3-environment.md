# Lab 3 local Python environment

This environment supports Track A and Track B. It uses Python 3.12 and the
project's `.venv/` directory on D:. The existing Python 3.12 interpreter is
reused; no new system interpreter is installed.

The course skeleton requires SageMaker 2.x because SageMaker 3 removed its
Feature Store interface. The guide specifies RAGAS 0.4.3 with
langchain-community 0.3.31 to retain the imports used by its evaluation harness.
XGBoost 3.2.0 matches the guide's local reference version.

Verified locally on 2026-10-17: Python 3.12.14; all 19 direct dependency imports,
both course skeleton imports, the Feature Store/RAGAS interfaces, FAISS lookup,
and XGBoost native-library check passed. `pip check` reported no broken
requirements. The full exact environment is recorded in `requirements-lab3.txt`.
SageMaker v2 and the course's RAGAS metric imports emit deprecation warnings;
they are retained to match the provided skeleton interfaces.

## Use the environment

Run from the repository root in PowerShell. Calling the interpreter directly
does not require changing PowerShell's execution policy or activating a shell.

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe scripts\check-lab3-env.py
```

Select `.venv\Scripts\python.exe` as the Python interpreter/kernel when opening
the later demo notebook. Do not select a global Python environment.

## Recreate the environment

Use an available Python 3.12 interpreter to create `.venv/`, then install the
exact versions in `requirements-lab3.txt`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lab3.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\check-lab3-env.py
```

The first command assumes `python --version` reports Python 3.12. Otherwise use
the full path to a Python 3.12 interpreter. Keep the environment and pip's cache
on D:; for this workspace the cache is `../.tools/lab3/pip-cache/`.

`requirements-lab3.in` records the direct dependencies and compatibility bounds.
`requirements-lab3.txt` records all exact installed dependency versions after
the import checks pass. `.venv/` is ignored by Git and must not be committed.

## What the local check proves

The check imports the dependencies and both teacher skeletons, checks the
Feature Store and RAGAS wrapper interfaces, runs a two-vector FAISS lookup, and
creates an XGBoost DMatrix. It does not train the coursework model, build a
policy index, execute the evaluation harness, or make AWS API calls. Successful
local checks do not establish that AWS credentials, model access or Lab 2 data
are currently available.

References: the local course guide's Experiment tracking and Track B sections;
[RAGAS 0.4.3](https://pypi.org/project/ragas/0.4.3/),
[langchain-community 0.3.31](https://pypi.org/project/langchain-community/0.3.31/).
