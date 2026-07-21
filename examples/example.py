# PPF font rendering example.
#
# Runs on a desktop MicroPython/CPython build (writes a PPM image you can open)
# and unchanged on a device (blit the Canvas framebuffer to a display). On a
# build with a native emitter and a supported format, a Canvas target uses the
# viper fast path automatically; otherwise it falls back to the portable path.
#
# Run from this directory:  micropython example.py [path/to/font.ppf]

import sys

# Allow running from the examples directory before installing the package.
sys.path.insert(0, "..")

import framebuf
from ppf import PPFFont, Canvas

# petme128.ppf is generated from MicroPython's built-in 8x8 font; see
# tools/petme128_to_ppf.py. Pass another .ppf on the command line to try it.
FONT = sys.argv[1] if len(sys.argv) > 1 else "petme128.ppf"

WIDTH = 240
HEIGHT = 90


def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def save_ppm(canvas, path):
    # Expand the RGB565 buffer to a binary PPM for easy viewing off-device.
    fb = canvas.fb
    with open(path, "wb") as f:
        f.write("P6\n{} {}\n255\n".format(canvas.width, canvas.height).encode())
        row = bytearray(canvas.width * 3)
        for y in range(canvas.height):
            o = 0
            for x in range(canvas.width):
                px = fb.pixel(x, y)
                row[o] = (px >> 8) & 0xF8
                row[o + 1] = (px >> 3) & 0xFC
                row[o + 2] = (px << 3) & 0xF8
                o += 3
            f.write(row)


def main():
    font = PPFFont(FONT)
    print("font '{}': {}x{}, {} glyphs".format(font.name, font.width, font.height, font._count))

    canvas = Canvas(WIDTH, HEIGHT, framebuf.RGB565)
    canvas.fb.fill(rgb565(16, 16, 32))

    font.text(canvas, "Hello, World!", 4, 4, rgb565(255, 255, 255))
    font.text(canvas, "PPF fonts", 4, 4 + font.height + 4, rgb565(120, 220, 255), 2)
    w, h = font.measure("PPF fonts", 2)
    print("'PPF fonts' at scale 2 measures {}x{}".format(w, h))
    font.text(canvas, "on framebuf", 4, 4 + font.height + 4 + h + 4, rgb565(255, 200, 80), 2)

    out = "example.ppm"
    save_ppm(canvas, out)
    print("wrote", out)

    # Same call works on a device; e.g. for an ST7789-class display:
    #     display.blit_buffer(canvas.buffer, ...)   # or driver-specific push
    #
    # A plain framebuf.FrameBuffer is also accepted (portable path, any format):
    mono = framebuf.FrameBuffer(bytearray(64 * ((font.height + 7) // 8)), 64, font.height, framebuf.MONO_VLSB)
    font.text(mono, "Hi", 0, 0, 1)
    print("\nMONO_VLSB 'Hi':")
    for y in range(font.height):
        print("".join("#" if mono.pixel(x, y) else " " for x in range(28)))


main()
