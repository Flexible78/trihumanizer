"""Generate PWA icons (192 and 512 px) using only the standard library.

Outputs static/icon-192.png and static/icon-512.png: a rounded-square
gradient with a bold white "T".
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "static"

# "T" drawn as rectangles on a 32x32 grid (1 = filled).
T_GLYPH = [
    "11111111111111111111111111111111",
    "11111111111111111111111111111111",
    "11111111111111111111111111111111",
    "11111111111111111111111111111111",
    "11111111111111111111111111111111",
    "11111111111111111111111111111111",
    "11111111111111111111111111111111",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
    "00000000000011111111111100000000",
]

GRID = 32
TOP = (0x69, 0x56, 0xE8)  # --accent
BOTTOM = (0xFF, 0x6B, 0x5E)  # --coral


def rounded_radius(size: int) -> int:
    return max(8, int(size * 0.22))


def inside_rounded_square(x: int, y: int, size: int, radius: int) -> bool:
    if x < 0 or y < 0 or x >= size or y >= size:
        return False
    if x < radius and y < radius:
        return (x - radius) ** 2 + (y - radius) ** 2 <= radius ** 2
    if x >= size - radius and y < radius:
        return (x - (size - radius)) ** 2 + (y - radius) ** 2 <= radius ** 2
    if x < radius and y >= size - radius:
        return (x - radius) ** 2 + (y - (size - radius)) ** 2 <= radius ** 2
    if x >= size - radius and y >= size - radius:
        return (x - (size - radius)) ** 2 + (y - (size - radius)) ** 2 <= radius ** 2
    return True


def glyph_hit(px: float, py: float, size: int) -> bool:
    """Map pixel coordinates to the 32x32 glyph grid with antialiased edges."""
    cell = size / GRID
    col = int(px // cell)
    row = int(py // cell)
    if 0 <= row < GRID and 0 <= col < GRID:
        return T_GLYPH[row][col] == "1"
    return False


def render(size: int) -> bytes:
    rows = []
    radius = rounded_radius(size)
    for y in range(size):
        row = bytearray()
        for x in range(size):
            if not inside_rounded_square(x, y, size, radius):
                row.extend((0, 0, 0, 0))
                continue
            t = y / max(1, size - 1)
            r = int(TOP[0] + (BOTTOM[0] - TOP[0]) * t)
            g = int(TOP[1] + (BOTTOM[1] - TOP[1]) * t)
            b = int(TOP[2] + (BOTTOM[2] - TOP[2]) * t)
            # Letter occupies the central 60% area.
            margin = size * 0.20
            glyph_x = (x - margin) / (size - 2 * margin) * GRID
            glyph_y = (y - margin) / (size - 2 * margin) * GRID
            if 0 <= glyph_x < GRID and 0 <= glyph_y < GRID and glyph_hit(glyph_x, glyph_y, size):
                row.extend((255, 255, 255, 255))
            else:
                row.extend((r, g, b, 255))
        rows.append(bytes(row))

    raw = b"".join(b"\x00" + row for row in rows)
    return _png(size, size, raw)


def _png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    for size in (192, 512):
        path = OUT_DIR / f"icon-{size}.png"
        path.write_bytes(render(size))
        print(f"wrote {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
