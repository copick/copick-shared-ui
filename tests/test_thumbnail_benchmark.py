"""Focused tests for the diagnostic thumbnail benchmark."""

import json

import pytest

from benchmarks import thumbnail_io


def test_benchmark_retains_five_raw_samples_and_summary(tmp_path):
    store_path = tmp_path / "fixture.zarr"
    thumbnail_io.build_fixture(store_path)

    report = thumbnail_io.run_benchmark(store_path, repeats=5)

    assert report["repeats"] == 5
    assert len(report["samples"]) == 5
    assert len({sample["thumbnail_sha256"] for sample in report["samples"]}) == 1
    assert all(sample["thumbnail_shape"] == [128, 128] for sample in report["samples"])
    assert all(sample["read_requests"] > 0 for sample in report["samples"])
    assert all(sample["read_bytes"] > 0 for sample in report["samples"])
    assert set(report["summary"]) == {"elapsed_seconds", "read_requests", "read_bytes", "peak_rss_bytes"}


def test_benchmark_rejects_too_few_repetitions(tmp_path):
    with pytest.raises(ValueError, match="at least five"):
        thumbnail_io.run_benchmark(tmp_path / "unused.zarr", repeats=4)


def test_benchmark_cli_writes_machine_and_human_reports(tmp_path, monkeypatch):
    report = {
        "schema_version": 1,
        "measurement": "test",
        "repeats": 5,
        "samples": [],
        "summary": {
            "elapsed_seconds": {"median": 1, "minimum": 1, "maximum": 1},
        },
    }
    monkeypatch.setattr(thumbnail_io, "run_benchmark", lambda *_args: report)
    json_path = tmp_path / "results" / "thumbnail.json"
    markdown_path = tmp_path / "results" / "thumbnail.md"

    result = thumbnail_io.main(
        [
            "--store",
            str(tmp_path / "store.zarr"),
            "--output-json",
            str(json_path),
            "--output-markdown",
            str(markdown_path),
        ],
    )

    assert result == 0
    assert json.loads(json_path.read_text(encoding="utf-8")) == report
    assert "Raw samples" in markdown_path.read_text(encoding="utf-8")
