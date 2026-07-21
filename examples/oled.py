# Minimal OLED example: a 128x64 monochrome framebuffer, as you'd use with an
# SSD1306 or similar. PPFFont.text() takes the same (fb, string, x, y, col)
# arguments as framebuf's own text(), so it drops straight into display code.
#
# On a device, replace the framebuf here with your driver's framebuffer and call
# display.show() to push it. This desktop version prints the buffer as ASCII.
#
# Run from this directory:  micropython oled.py [path/to/font.ppf]

import sys

# Allow running from the examples directory before installing the package.
sys.path.insert(0, "..")

import framebuf
from ppf import PPFFont

FONT = sys.argv[1] if len(sys.argv) > 1 else "petme128.ppf"

WIDTH = 128
HEIGHT = 64


def show(fb):
    # Stand-in for display.show(): dump the 1-bpp buffer to the terminal.
    for y in range(HEIGHT):
        print("".join("#" if fb.pixel(x, y) else " " for x in range(WIDTH)))


def main():
    font = PPFFont(FONT)

    # A real driver owns this buffer; here we make our own in the same format.
    buf = bytearray(WIDTH * HEIGHT // 8)
    fb = framebuf.FrameBuffer(buf, WIDTH, HEIGHT, framebuf.MONO_VLSB)

    fb.fill(0)
    line = font.height + 2
    font.text(fb, "MicroPython", 0, 0, 1)
    font.text(fb, "PPF fonts on a", 0, line, 1)
    font.text(fb, "128x64 OLED", 0, line * 2, 1)

    # framebuf's own primitives share the buffer, so mix and match freely.
    fb.hline(0, line * 3 + 2, WIDTH, 1)
    fb.text("built-in 8x8", 0, line * 3 + 6, 1)

    show(fb)  # -> display.show() on hardware


main()
