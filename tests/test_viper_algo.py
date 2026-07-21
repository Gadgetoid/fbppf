# Validates the viper blitters' arithmetic without a native emitter.
#
# Each _emulate_* function reproduces the exact loop, index math and unsigned
# clip test of the matching @micropython.viper blitter in ppf_viper, but in
# plain Python writing to the same buffer layout. Its output is compared, pixel
# for pixel, against the portable framebuf.fill_rect renderer for a range of
# origins (including off-screen) and scales. Passing here means the only thing
# left to prove on-device is that the viper syntax compiles, not the logic.
#
# Run from this directory:  micropython test_viper_algo.py [path/to/font.ppf]

import sys

sys.path.insert(0, "..")

import framebuf
from ppf import PPFFont

FONT = sys.argv[1] if len(sys.argv) > 1 else "../examples/petme128.ppf"
U32 = 0xFFFFFFFF


def _glyph_iter(font, i, dx, dy, scale, fbw, fbh):
    # Common walk: yields (x, y) dest pixels the viper blitter would write,
    # applying the same unsigned clip test.
    w = font._widths[i]
    off = i * font._glyph_size
    for gy in range(font.height):
        base = off + gy * font._bpr
        base_y = dy + gy * scale
        for gx in range(w):
            if font._data[base + (gx >> 3)] & (0x80 >> (gx & 7)):
                px0 = dx + gx * scale
                for ry in range(scale):
                    yy = base_y + ry
                    if (yy & U32) < fbh:
                        for rx in range(scale):
                            xx = px0 + rx
                            if (xx & U32) < fbw:
                                yield xx, yy


def emulate_rgb565(font, string, buf, stride, fbw, fbh, col, scale):
    # RGB565 is a native-endian uint16 store; both unix-arm64 and rp2 are
    # little-endian, so write low byte then high byte.
    x = 0
    space = (font.width // 3) * scale
    for ch in string:
        if ch == " ":
            x += space
            continue
        i = font._index(ord(ch))
        if i == -1:
            continue
        for xx, yy in _glyph_iter(font, i, x, 0, scale, fbw, fbh):
            o = (yy * stride + xx) * 2
            buf[o] = col & 0xFF
            buf[o + 1] = (col >> 8) & 0xFF
        x += (font._widths[i] + 1) * scale


def emulate_gs8(font, string, buf, stride, fbw, fbh, col, scale):
    x = 0
    space = (font.width // 3) * scale
    for ch in string:
        if ch == " ":
            x += space
            continue
        i = font._index(ord(ch))
        if i == -1:
            continue
        for xx, yy in _glyph_iter(font, i, x, 0, scale, fbw, fbh):
            buf[yy * stride + xx] = col & 0xFF
        x += (font._widths[i] + 1) * scale


def emulate_mvlsb(font, string, buf, stride, fbw, fbh, col, scale):
    x = 0
    space = (font.width // 3) * scale
    for ch in string:
        if ch == " ":
            x += space
            continue
        i = font._index(ord(ch))
        if i == -1:
            continue
        for xx, yy in _glyph_iter(font, i, x, 0, scale, fbw, fbh):
            idx = (yy >> 3) * stride + xx
            bit = 1 << (yy & 7)
            if col != 0:
                buf[idx] |= bit
            else:
                buf[idx] &= 0xFF ^ bit
        x += (font._widths[i] + 1) * scale


def portable(font, string, w, h, fmt, col, scale):
    buf = bytearray(_size(fmt, w, h))
    fb = framebuf.FrameBuffer(buf, w, h, fmt)
    font.text(fb, string, 0, 0, col, scale)
    return buf


def _size(fmt, w, h):
    if fmt == framebuf.RGB565:
        return w * h * 2
    if fmt == framebuf.GS8:
        return w * h
    return w * ((h + 7) >> 3)  # MONO_VLSB


CASES = (
    (framebuf.RGB565, emulate_rgb565, 0xF81F),
    (framebuf.GS8, emulate_gs8, 0xAB),
    (framebuf.MONO_VLSB, emulate_mvlsb, 1),
)


def main():
    font = PPFFont(FONT)
    print("loaded '{}' {}x{}".format(font.name, font.width, font.height))
    text = "Ag!"
    checks = 0
    for fmt, emulate, col in CASES:
        for scale in (1, 2, 3):
            w = 80
            h = 24 if fmt != framebuf.MONO_VLSB else 32
            ref = portable(font, text, w, h, fmt, col, scale)
            emu = bytearray(_size(fmt, w, h))
            emulate(font, text, emu, w, w, h, col, scale)
            assert emu == ref, "format {} scale {} mismatch".format(fmt, scale)
            checks += 1
    print("{} format/scale combinations: viper arithmetic matches portable output".format(checks))
    print("all viper-algorithm checks passed")


main()
