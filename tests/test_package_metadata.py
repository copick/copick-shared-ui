"""Runtime metadata gates for the shared-UI 2.0 alpha line."""

import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]


def test_alpha_runtime_contract_is_explicit():
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert project["requires-python"] == ">=3.11"
    assert set(project["dependencies"]) >= {
        "copick>=2.0.0a1,<3",
        "numpy>=2.0.2",
        "zarr>=3.1.6,<4",
    }
    assert all("copick[all]" not in requirement for requirement in project["dependencies"])
    assert "Programming Language :: Python :: 3.10" not in project["classifiers"]
    assert "Programming Language :: Python :: 3.14" in project["classifiers"]
