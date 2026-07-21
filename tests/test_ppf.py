# Self-checking test for ppf.PPFFont. Renders onto framebuf targets and
# verifies the output against an independent glyph decode, so the renderer is
# validated even on builds where viper is unavailable (the portable path).
#
# Run from this directory:  micropython test_ppf.py [path/to/font.ppf]

import sys

sys.path.insert(0, "..")

import framebuf
from ppf import PPFFont, Canvas

FONT = sys.argv[1] if len(sys.argv) > 1 else "../examples/petme128.ppf"


def decode_glyph(font, ch):
    # Independent reference: unpack one glyph to a list of (col, row) set pixels.
    i = font._index(ord(ch))
    if i == -1:
        return None, 0
    w = font._widths[i]
    off = i * font._glyph_size
    pixels = set()
    for row in range(font.height):
        base = off + row * font._bpr
        for col in range(w):
            if font._data[base + (col >> 3)] & (0x80 >> (col & 7)):
                pixels.add((col, row))
    return pixels, w


def ascii_art(fb, w, h):
    out = []
    for y in range(h):
        out.append("".join("#" if fb.pixel(x, y) else "." for x in range(w)))
    return "\n".join(out)


def test_single_glyph(font):
    # Render 'A' at origin and compare set pixels to the reference decode.
    ref, w = decode_glyph(font, "A")
    buf = bytearray(64 * font.height)
    fb = framebuf.FrameBuffer(buf, 64, font.height, framebuf.MONO_HLSB)
    font.text(fb, "A", 0, 0, 1)
    got = {(x, y) for y in range(font.height) for x in range(w + 2) if fb.pixel(x, y)}
    assert got == ref, "glyph A mismatch:\ngot {}\nref {}".format(got, ref)
    print("glyph 'A' matches reference decode")
    print(ascii_art(fb, w + 1, font.height))


def test_scale(font):
    # At scale 2 every set source pixel becomes a 2x2 block.
    ref, w = decode_glyph(font, "A")
    scale = 2
    buf = bytearray(128 * font.height * scale)
    fb = framebuf.FrameBuffer(buf, 128, font.height * scale, framebuf.MONO_HLSB)
    font.text(fb, "A", 0, 0, 1, scale)
    for (col, row) in ref:
        for dy in range(scale):
            for dx in range(scale):
                x = col * scale + dx
                y = row * scale + dy
                assert fb.pixel(x, y), "scaled pixel {} missing".format((x, y))
    print("scale=2 expands every pixel to a 2x2 block")


def test_clipping(font):
    # Negative origin must not corrupt memory or wrap; only on-screen pixels set.
    buf = bytearray(16 * 16 * 2)
    fb = framebuf.FrameBuffer(buf, 16, 16, framebuf.RGB565)
    font.text(fb, "A", -3, -3, 0xF800)
    ref, w = decode_glyph(font, "A")
    for y in range(16):
        for x in range(16):
            on = fb.pixel(x, y) != 0
            expect = (x + 3, y + 3) in ref
            assert on == expect, "clip mismatch at {}".format((x, y))
    print("clipping at negative origin is correct")


def test_measure(font):
    w1, h1 = font.measure("A")
    assert w1 == font._widths[font._index(ord("A"))] + 1
    assert h1 == font.height
    w2, h2 = font.measure("A\nBB")
    assert h2 == font.height * 2, "two lines -> double height"
    print("measure: 'A' -> {}x{}, two lines -> height {}".format(w1, h1, h2))


def test_canvas_fallback(font):
    # Without a native emitter Canvas must still render via the portable path.
    c = Canvas(96, font.height, framebuf.RGB565)
    end = font.text(c, "Hi", 0, 0, 0xFFFF)
    assert end > 0
    lit = sum(c.fb.pixel(x, y) != 0 for y in range(font.height) for x in range(96))
    assert lit > 0, "Canvas rendered nothing"
    print("Canvas('Hi') lit {} pixels, cursor advanced to x={}".format(lit, end))


def main():
    font = PPFFont(FONT)
    print("loaded '{}' {}x{}, {} glyphs\n".format(font.name, font.width, font.height, font._count))
    test_single_glyph(font)
    print()
    test_scale(font)
    test_clipping(font)
    test_measure(font)
    test_canvas_fallback(font)
    print("\nall tests passed")


main()
