from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).parents[1]
BRAND = ROOT / "custom_components" / "iotrix" / "brand"


def _png_header(path: Path) -> tuple[int, int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    width, height, _depth, color_type = struct.unpack(">IIBB", data[16:26])
    return width, height, color_type


def test_brand_icons_are_square_rgba_pngs() -> None:
    assert _png_header(BRAND / "icon.png") == (256, 256, 6)
    assert _png_header(BRAND / "icon@2x.png") == (512, 512, 6)
