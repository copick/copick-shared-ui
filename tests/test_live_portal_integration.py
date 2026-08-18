"""Opt-in bounded smoke test for the public CryoET Data Portal route."""

import os

import numpy as np
import pytest
from copick.impl.cryoet_data_portal import CopickConfigCDP, CopickRootCDP

from tests.helpers import ArrayThumbnailWorker

pytestmark = pytest.mark.integration


def test_public_portal_thumbnail(tmp_path):
    if os.environ.get("COPICK_SHARED_UI_RUN_LIVE_PORTAL") != "1":
        pytest.skip("live portal validation is opt-in")

    root = CopickRootCDP(
        CopickConfigCDP(
            name="shared-ui-portal",
            description="Bounded shared UI portal smoke",
            version="1.0.0",
            pickable_objects=[],
            overlay_root=f"local://{tmp_path / 'overlay'}",
            overlay_fs_args={"auto_mkdir": True},
            dataset_ids=[10301],
        ),
    )
    worker = ArrayThumbnailWorker(root.get_run("14077"))

    thumbnail, error = worker.generate_thumbnail_pixmap()

    assert error is None
    assert thumbnail.shape == (256, 256)
    assert thumbnail.dtype == np.uint8
    assert (int(thumbnail.min()), int(thumbnail.max())) == (0, 255)
