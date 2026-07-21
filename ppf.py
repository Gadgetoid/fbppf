# Picovector PPF (pixel) font loader and framebuf renderer.
#
# PPF is the pixel-font container used by Picovector/Badgeware. This is a pure
# MicroPython reader and renderer that draws onto any framebuf.FrameBuffer,
# regardless of pixel format. A Canvas helper unlocks per-format viper blitters
# (see ppf_viper) for the common linear buffer layouts.
#
# File format (all multi-byte fields big-endian):
#   0   char[4]   "ppf!" marker
#   4   u16       flags (unused)
#   6   u32       glyph_count
#   10  u16       width   (maximum glyph width; sets the bitmap row stride)
#   12  u16       height
#   14  char[32]  name (nul-padded)
#   46  glyph[]   glyph_count records, sorted by codepoint: u32 codepoint, u16 width
#   ..  u8[]      glyph_count bitmaps, each ((width + 7) // 8) * height bytes,
#                 rows packed MSB-first at the font's maximum-width stride

from array import array
import struct

try:
    import ppf_viper
except (ImportError, SyntaxError):
    # No native emitter on this build; portable framebuf path is used instead.
    ppf_viper = None

_HEADER = ">4sHIHH32s"


class PPFFont:
    def __init__(self, path):
        with open(path, "rb") as f:
            header = f.read(struct.calcsize(_HEADER))
            marker, flags, count, width, height, name = struct.unpack(_HEADER, header)
            if marker != b"ppf!":
                raise ValueError("missing PPF header")

            self.width = width
            self.height = height
            self.name = name.split(b"\x00", 1)[0].decode()
            self._count = count
            self._bpr = (width + 7) >> 3
            self._glyph_size = self._bpr * height

            codepoints = array("I", bytes(4 * count))
            widths = array("H", bytes(2 * count))
            table = f.read(6 * count)
            for i in range(count):
                cp, w = struct.unpack_from(">IH", table, i * 6)
                codepoints[i] = cp
                widths[i] = w
            self._codepoints = codepoints
            self._widths = widths

            self._data = f.read(self._glyph_size * count)

    def _index(self, codepoint):
        # Binary search the codepoint-sorted glyph table.
        codepoints = self._codepoints
        low = 0
        high = self._count
        while low < high:
            mid = (low + high) >> 1
            cp = codepoints[mid]
            if cp == codepoint:
                return mid
            if cp < codepoint:
                low = mid + 1
            else:
                high = mid
        return -1

    def measure(self, string, scale=1):
        if scale < 1:
            scale = 1
        space = (self.width // 3) * scale
        x = 0
        max_w = 0
        lines = 1
        for ch in string:
            if ch == "\n":
                if x > max_w:
                    max_w = x
                x = 0
                lines += 1
                continue
            if ch == "\r":
                continue
            if ch == " ":
                x += space
                continue
            i = self._index(ord(ch))
            if i != -1:
                x += (self._widths[i] + 1) * scale
        if x > max_w:
            max_w = x
        return max_w, self.height * scale * lines

    def text(self, target, string, x, y, col=1, scale=1):
        # Draw `string` onto `target` at (x, y). `target` may be a
        # framebuf.FrameBuffer (portable path) or a Canvas (viper fast path
        # where the pixel format is supported). Newlines return to the start
        # column and drop one line; carriage returns are ignored.
        if scale < 1:
            scale = 1

        fb, blit = self._resolve(target, col, scale)

        origin_x = x
        line_step = self.height * scale
        space = (self.width // 3) * scale
        data = self._data
        widths = self._widths
        bpr = self._bpr
        glyph_size = self._glyph_size

        for ch in string:
            if ch == "\n":
                x = origin_x
                y += line_step
                continue
            if ch == "\r":
                continue
            if ch == " ":
                x += space
                continue
            i = self._index(ord(ch))
            if i == -1:
                continue
            w = widths[i]
            blit(data, i * glyph_size, bpr, w, self.height, x, y)
            x += (w + 1) * scale
        return x

    def _resolve(self, target, col, scale):
        # Select a per-glyph blit callable for the target. Canvas targets with a
        # supported format and an available native module use viper; everything
        # else uses the portable framebuf.fill_rect path.
        fb = getattr(target, "fb", target)
        if ppf_viper is not None and hasattr(target, "format"):
            factory = ppf_viper.blitter(target.format)
            if factory is not None:
                return fb, factory(
                    target.buffer, target.stride, target.width, target.height, col, scale
                )
        return fb, _portable_blitter(fb, col, scale)


def _portable_blitter(fb, col, scale):
    fill_rect = fb.fill_rect

    def blit(data, offset, bpr, gw, gh, dx, dy):
        # Walk source pixels, coalescing horizontal runs of set bits into one
        # scale-wide fill_rect per run. fill_rect clips to the framebuffer.
        for gy in range(gh):
            row = offset + gy * bpr
            ry = dy + gy * scale
            gx = 0
            while gx < gw:
                if data[row + (gx >> 3)] & (0x80 >> (gx & 7)):
                    run = 1
                    while gx + run < gw and (
                        data[row + ((gx + run) >> 3)] & (0x80 >> ((gx + run) & 7))
                    ):
                        run += 1
                    fill_rect(dx + gx * scale, ry, run * scale, scale, col)
                    gx += run
                else:
                    gx += 1

    return blit


class Canvas:
    # Owns a pixel buffer and a matching framebuf.FrameBuffer, exposing the
    # geometry (buffer, format, stride) that PPFFont.text needs to select a
    # viper fast path. Pass a Canvas to PPFFont.text for accelerated rendering;
    # use .fb directly for other framebuf drawing.
    def __init__(self, width, height, format, buffer=None, stride=None):
        import framebuf

        if stride is None:
            stride = width
        if buffer is None:
            buffer = bytearray(_buffer_size(format, stride, height))
        self.width = width
        self.height = height
        self.format = format
        self.stride = stride
        self.buffer = buffer
        self.fb = framebuf.FrameBuffer(buffer, width, height, format, stride)


def _buffer_size(format, stride, height):
    import framebuf

    if format == framebuf.RGB565:
        return stride * height * 2
    if format == framebuf.GS8:
        return stride * height
    if format == framebuf.GS4_HMSB:
        return (stride * height + 1) >> 1
    if format == framebuf.GS2_HMSB:
        return (stride * height + 3) >> 2
    if format in (framebuf.MONO_VLSB, framebuf.MONO_HLSB, framebuf.MONO_HMSB):
        # MONO_VLSB packs 8 rows per byte column; the others 8 columns per byte.
        if format == framebuf.MONO_VLSB:
            return stride * ((height + 7) >> 3)
        return ((stride + 7) >> 3) * height
    raise ValueError("unsupported format")
