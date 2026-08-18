# Local thumbnail I/O alpha baseline

Recorded on 2026-08-18 with Python 3.12.10, copick 2.0.0-alpha.1, NumPy 2.5.1, and Zarr 3.3.0.
The fixture is a two-level canonical OME-Zarr 0.5 / Zarr v3 pyramid written through the released core helper. Each
sample opens the store read-only, selects the final metadata dataset, and materializes only the strided middle slice.

```bash
python -m benchmarks.thumbnail_io \
  --store /private/tmp/copick-shared-ui-thumbnail-benchmark.zarr \
  --build-fixture \
  --repeats 5 \
  --output-json /private/tmp/copick-shared-ui-thumbnail-benchmark.json \
  --output-markdown /private/tmp/copick-shared-ui-thumbnail-benchmark.md
```

| Sample | Seconds | Read requests | Read bytes | Peak RSS bytes |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.005875042 | 6 | 27,609 | 274,219,008 |
| 2 | 0.005237000 | 6 | 27,609 | 274,317,312 |
| 3 | 0.005245667 | 6 | 27,609 | 274,415,616 |
| 4 | 0.006067583 | 6 | 27,609 | 274,464,768 |
| 5 | 0.005083875 | 6 | 27,609 | 274,497,536 |

| Metric | Median | Minimum | Maximum |
| --- | ---: | ---: | ---: |
| Seconds | 0.005245667 | 0.005083875 | 0.006067583 |
| Read requests | 6 | 6 | 6 |
| Read bytes | 27,609 | 27,609 | 27,609 |
| Peak RSS bytes | 274,415,616 | 274,219,008 | 274,497,536 |

All five thumbnails were `(128, 128)` and had the same decoded SHA-256 digest,
`47a9ab890d65e7ff1e7b93b6666d58ef74ba017ecdced365c51fa6e8886173ad`. These values are diagnostic evidence,
not a release threshold.
