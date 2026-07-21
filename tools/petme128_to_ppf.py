#!/usr/bin/env python3
# Convert MicroPython's built-in font_petme128_8x8.h into a PPF pixel font.
#
# The source font is column-major: 8 bytes per glyph, one byte per column, with
# the least-significant bit at the top row. PPF is row-major, MSB-first, packed
# at the font's maximum-width stride. Trailing blank columns are trimmed so each
# glyph carries its own width (advance is width + 1), matching the proportional
# style of other PPF fonts; leading columns are kept as left bearing.
#
# Run:  python3 tools/petme128_to_ppf.py <font_petme128_8x8.h> <out.ppf>

import re
import struct
import sys

HEIGHT = 8
NAME = "petme128"


def parse(header_path):
    # Yield (codepoint, [8 column bytes]) using the trailing "// NN" comment on
    # each data line as the authoritative codepoint.
    glyphs = []
    line_re = re.compile(r"((?:0x[0-9a-fA-F]{2},\s*){8}).*//\s*(\d+)")
    for line in open(header_path):
        m = line_re.search(line)
        if not m:
            continue
        cols = [int(b, 16) for b in re.findall(r"0x([0-9a-fA-F]{2})", m.group(1))]
        glyphs.append((int(m.group(2)), cols))
    return glyphs


def transpose(cols):
    # Column-major LSB-top -> list of `width` row bytes, MSB-left. Returns the
    # trimmed width (trailing blank columns removed).
    width = 0
    for c in range(8):
        if cols[c]:
            width = c + 1
    rows = bytearray(HEIGHT)
    for c in range(width):
        column = cols[c]
        bit = 0x80 >> c
        for r in range(HEIGHT):
            if column & (1 << r):
                rows[r] |= bit
    return width, rows


def build(glyphs):
    glyphs = sorted(glyphs)
    max_width = max((transpose(c)[0] for _, c in glyphs), default=0)
    bpr = (max_width + 7) >> 3

    out = bytearray()
    out += b"ppf!"
    out += struct.pack(">H", 0)  # flags
    out += struct.pack(">I", len(glyphs))
    out += struct.pack(">H", max_width)
    out += struct.pack(">H", HEIGHT)
    out += NAME.encode()[:32].ljust(32, b"\x00")

    data = bytearray()
    for cp, cols in glyphs:
        width, rows = transpose(cols)
        out += struct.pack(">IH", cp, width)
        for r in range(HEIGHT):
            data.append(rows[r])
            data += bytes(bpr - 1)  # pad to the max-width stride
    return out + data


def main():
    if len(sys.argv) != 3:
        print(__doc__.strip())
        sys.exit(1)
    glyphs = parse(sys.argv[1])
    ppf = build(glyphs)
    with open(sys.argv[2], "wb") as f:
        f.write(ppf)
    print("wrote {} ({} glyphs, {} bytes)".format(sys.argv[2], len(glyphs), len(ppf)))


if __name__ == "__main__":
    main()
