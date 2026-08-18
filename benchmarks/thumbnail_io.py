"""Measure bounded thumbnail reads without imposing a performance threshold."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import psutil
from copick.util.ome import write_ome_zarr_3d
from zarr.abc.store import Store
from zarr.storage import LocalStore, WrapperStore

from copick_shared_ui.workers.base import AbstractThumbnailWorker


@dataclass
class ReadStats:
    requests: int = 0
    bytes: int = 0


class RecordingStore(WrapperStore):
    """Transparent store wrapper that records payloads returned by reads."""

    def __init__(self, store: Store):
        super().__init__(store)
        self._lock = threading.Lock()
        self._reads = ReadStats()

    def snapshot(self) -> ReadStats:
        with self._lock:
            return ReadStats(**asdict(self._reads))

    def _record(self, value: Any) -> None:
        with self._lock:
            self._reads.requests += 1
            self._reads.bytes += 0 if value is None else len(value)

    async def get(self, key, prototype, byte_range=None):
        value = await self._store.get(key, prototype, byte_range)
        self._record(value)
        return value

    async def get_partial_values(self, prototype, key_ranges):
        ranges = list(key_ranges)
        values = await self._store.get_partial_values(prototype, ranges)
        for value in values:
            self._record(value)
        return values

    async def get_ranges(self, key, byte_ranges, **kwargs):
        async for group in self._store.get_ranges(key, byte_ranges, **kwargs):
            for _index, value in group:
                self._record(value)
            yield group

    async def _get_many(self, requests):
        async for key, value in self._store._get_many(requests):
            self._record(value)
            yield key, value


class _Run:
    name = "benchmark"


class _VoxelSpacing:
    run = _Run()
    voxel_size = 10.0


class _Tomogram:
    tomo_type = "wbp"
    voxel_spacing = _VoxelSpacing()

    def __init__(self, store: Store):
        self._store = store

    def zarr(self) -> Store:
        return self._store


class _ArrayWorker(AbstractThumbnailWorker):
    def __init__(self, tomogram: _Tomogram):
        super().__init__(tomogram, "benchmark", lambda *_result: None, True)
        self._cache = None

    def _setup_cache(self) -> None:
        self._cache = None
        self._cache_key = None

    def start(self) -> None:
        pass

    def cancel(self) -> None:
        pass

    def _array_to_pixmap(self, array):
        return array


def build_fixture(path: Path) -> None:
    """Write a small canonical two-level core fixture for diagnostics."""
    fine = np.arange(48 * 256 * 256, dtype=np.float32).reshape(48, 256, 256)
    coarse = fine[::2, ::2, ::2]
    write_ome_zarr_3d(LocalStore(path), {10.0: fine, 20.0: coarse})


def _measure_once(path: Path) -> dict[str, Any]:
    store = RecordingStore(LocalStore(path, read_only=True))
    worker = _ArrayWorker(_Tomogram(store))
    process = psutil.Process()
    peak_rss = process.memory_info().rss
    stop = threading.Event()

    def sample_memory() -> None:
        nonlocal peak_rss
        while not stop.wait(0.001):
            peak_rss = max(peak_rss, process.memory_info().rss)

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    before = store.snapshot()
    started = time.perf_counter()
    thumbnail = worker._generate_thumbnail_array(worker.item)
    elapsed = time.perf_counter() - started
    after = store.snapshot()
    stop.set()
    sampler.join()

    return {
        "elapsed_seconds": elapsed,
        "read_requests": after.requests - before.requests,
        "read_bytes": after.bytes - before.bytes,
        "peak_rss_bytes": peak_rss,
        "thumbnail_shape": list(thumbnail.shape),
        "thumbnail_sha256": hashlib.sha256(thumbnail.tobytes()).hexdigest(),
    }


def _summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for field in ("elapsed_seconds", "read_requests", "read_bytes", "peak_rss_bytes"):
        values = [sample[field] for sample in samples]
        result[field] = {
            "median": statistics.median(values),
            "minimum": min(values),
            "maximum": max(values),
        }
    return result


def run_benchmark(path: Path, repeats: int = 5) -> dict[str, Any]:
    if repeats < 5:
        raise ValueError("Thumbnail benchmarks require at least five repetitions")
    samples = [_measure_once(path) for _ in range(repeats)]
    checksums = {sample["thumbnail_sha256"] for sample in samples}
    if len(checksums) != 1:
        raise AssertionError("Thumbnail output changed between benchmark repetitions")
    return {
        "schema_version": 1,
        "measurement": "coarsest metadata level, strided middle slice",
        "repeats": repeats,
        "samples": samples,
        "summary": _summary(samples),
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Thumbnail I/O diagnostic",
        "",
        f"Repetitions: {report['repeats']}",
        "",
        "| Metric | Median | Minimum | Maximum |",
        "| --- | ---: | ---: | ---: |",
    ]
    for metric, values in report["summary"].items():
        lines.append(f"| {metric} | {values['median']} | {values['minimum']} | {values['maximum']} |")
    lines.extend(["", "Raw samples are retained in the paired JSON report.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--build-fixture", action="store_true")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    arguments = parser.parse_args(argv)

    if arguments.build_fixture:
        build_fixture(arguments.store)
    report = run_benchmark(arguments.store, arguments.repeats)
    arguments.output_json.parent.mkdir(parents=True, exist_ok=True)
    arguments.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    arguments.output_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    arguments.output_markdown.write_text(_markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
