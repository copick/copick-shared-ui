"""Validation against the exact artifact published by the copick core alpha."""

import hashlib
import json
import os
import zipfile
from pathlib import Path

import pytest

from copick_shared_ui.storage import open_coarsest_tomogram_array
from tests.helpers import ArrayThumbnailWorker, DummyTomogram

CORE_ALPHA_REVISION = "5b3aff2ae4bf9bcf85b4a1d4132205640171f85b"
CORE_FIXTURE_SHA256 = "c6f8e58c9d89c4d4d76208c08563ad34ed9838952666c49f43b5c0c68652f51b"


@pytest.mark.integration
def test_published_core_alpha_direct_reader_fixture(tmp_path):
    configured_path = os.environ.get("COPICK_DIRECT_READER_FIXTURE")
    if configured_path is None:
        pytest.skip("COPICK_DIRECT_READER_FIXTURE does not name the published core artifact")

    archive_path = Path(configured_path)
    assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == CORE_FIXTURE_SHA256
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(tmp_path)

    fixture_root = tmp_path / "copick-v3-direct-reader-fixture"
    manifest = json.loads((fixture_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["producer"]["source_revision"] == CORE_ALPHA_REVISION

    for case in ("boolean", "floating", "integer"):
        store_path = fixture_root / manifest["stores"][case]["path"]
        tomogram = DummyTomogram(str(store_path))

        array = open_coarsest_tomogram_array(tomogram)
        thumbnail = ArrayThumbnailWorker(tomogram)._generate_thumbnail_array(tomogram)

        assert array.path == manifest["stores"][case]["multiscale"]["datasets"][-1]["path"]
        assert thumbnail.ndim == 2
        assert thumbnail.size > 0
