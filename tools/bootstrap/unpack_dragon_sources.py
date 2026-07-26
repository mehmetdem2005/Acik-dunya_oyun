from __future__ import annotations

import base64
import hashlib
from pathlib import Path

EXPECTED_SHA256 = "8eb9c8615e691635d6e378ce25693da19014dd736a0e2efafb6698eb5398be1d"
PART_PATTERN = "dragon_production_sources.tar.gz.b64.part*"
OUTPUT_PATH = Path("/tmp/dragon_production_sources.tar.gz")


def main() -> None:
    bootstrap_dir = Path(__file__).resolve().parent
    parts = sorted(bootstrap_dir.glob(PART_PATTERN))
    print(f"bootstrap_dir={bootstrap_dir}")
    print(f"parts={[p.name for p in parts]}")
    print(f"part_sizes={[p.stat().st_size for p in parts]}")
    if len(parts) != 6:
        raise RuntimeError(f"Expected 6 source parts, found {len(parts)}")

    encoded = b"".join(part.read_bytes().strip() for part in parts)
    print(f"encoded_bytes={len(encoded)}")
    archive = base64.b64decode(encoded, validate=True)
    actual_sha256 = hashlib.sha256(archive).hexdigest()
    print(f"archive_bytes={len(archive)} sha256={actual_sha256}")
    if actual_sha256 != EXPECTED_SHA256:
        raise RuntimeError(
            f"Bootstrap checksum mismatch: expected {EXPECTED_SHA256}, got {actual_sha256}"
        )
    OUTPUT_PATH.write_bytes(archive)
    print(f"wrote={OUTPUT_PATH}")


if __name__ == "__main__":
    main()
