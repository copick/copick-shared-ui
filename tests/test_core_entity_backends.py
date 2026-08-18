"""Deterministic thumbnail reads through real copick backend entities."""

import json
import socket

import boto3
import copick
import numpy as np
import pytest
from copick.impl.filesystem import CopickConfigFSSpec, CopickRootFSSpec
from copick.ops.croissant import export_croissant
from moto.server import ThreadedMotoServer

from copick_shared_ui.workers.unified_workers import UnifiedThumbnailWorker, is_threading_available
from tests.helpers import ArrayThumbnailWorker


def _write_project(overlay_root, overlay_fs_args=None):
    root = CopickRootFSSpec(
        CopickConfigFSSpec(
            name="shared-ui-backend",
            description="Shared UI backend fixture",
            version="1.0.0",
            pickable_objects=[],
            overlay_root=overlay_root,
            overlay_fs_args=overlay_fs_args or {"auto_mkdir": True},
        ),
    )
    run = root.new_run("run-1")
    voxel_spacing = run.new_voxel_spacing(10.0)
    tomogram = voxel_spacing.new_tomogram("denoised")
    tomogram.from_numpy(np.arange(3 * 64 * 96, dtype=np.float32).reshape(3, 64, 96))
    return root


def _assert_thumbnail(root):
    worker = ArrayThumbnailWorker(root.get_run("run-1"))
    thumbnail, error = worker.generate_thumbnail_pixmap()

    assert error is None
    assert thumbnail.ndim == 2
    assert thumbnail.size > 0
    assert thumbnail.dtype == np.uint8
    assert (int(thumbnail.min()), int(thumbnail.max())) == (0, 255)


def test_local_copick_entity_thumbnail(tmp_path):
    root = _write_project(f"local://{tmp_path / 'local-project'}")

    _assert_thumbnail(root)


@pytest.mark.skipif(not is_threading_available(), reason="Qt threading is unavailable")
def test_local_concurrent_workers_emit_one_terminal_callback_each(tmp_path, qtbot):
    root = _write_project(f"local://{tmp_path / 'local-concurrent-project'}")
    run = root.get_run("run-1")
    callbacks = []
    workers = [
        UnifiedThumbnailWorker(run, f"thumbnail-{index}", lambda *result: callbacks.append(result), True)
        for index in range(4)
    ]
    for worker in workers:
        worker._cache = None
        worker.start()

    qtbot.waitUntil(lambda: len(callbacks) >= len(workers), timeout=30000)
    qtbot.wait(100)

    assert len(callbacks) == len(workers)
    assert {result[0] for result in callbacks} == {f"thumbnail-{index}" for index in range(4)}
    assert all(result[1] is not None and result[2] is None for result in callbacks)


def test_mlcroissant_copick_entity_thumbnail(tmp_path):
    project_path = tmp_path / "mlcroissant-project"
    source_root = _write_project(f"local://{project_path}")
    export_croissant(
        source_root,
        project_root=str(project_path),
        base_url=f"file://{project_path}",
        dataset_name="shared-ui-backend",
        force=True,
    )
    config_path = tmp_path / "mlcroissant.json"
    config_path.write_text(
        json.dumps(
            {
                "config_type": "mlcroissant",
                "pickable_objects": [],
                "croissant_url": str(project_path / "Croissant" / "metadata.json"),
            },
        ),
        encoding="utf-8",
    )

    _assert_thumbnail(copick.from_file(str(config_path)))


def test_s3_compatible_copick_entity_thumbnail():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=port, verbose=False)
    server.start()
    endpoint = f"http://127.0.0.1:{port}"
    try:
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id="test",
            aws_secret_access_key="test",
            region_name="us-west-2",
        )
        client.create_bucket(
            Bucket="shared-ui",
            CreateBucketConfiguration={"LocationConstraint": "us-west-2"},
        )
        options = {
            "key": "test",
            "secret": "test",
            "endpoint_url": endpoint,
            "client_kwargs": {"region_name": "us-west-2"},
        }

        root = _write_project("s3://shared-ui/project", options)

        _assert_thumbnail(root)
    finally:
        server.stop()
