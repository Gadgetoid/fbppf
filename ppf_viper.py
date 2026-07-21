# Viper glyph blitters for PPFFont, one per supported framebuf pixel format.
#
# Each blitter writes a whole glyph directly into the target buffer in a single
# native call, avoiding the per-run Python method-call overhead of the portable
# framebuf.fill_rect path. Only linear layouts with a cheap index-from-(x, y)
# are worth accelerating this way: RGB565, GS8 and MONO_VLSB.
#
# This module is imported behind a try/except by ppf; on a build without a
# native emitter its @micropython.viper defs fail to compile and the portable
# path is used. It is never imported on such a build after the first failure.
#
# Clipping trick: a coordinate compared as uint is out of range whenever it is
# negative (wraps high) or past the edge, so `uint(xx) < uint(w)` is the whole
# horizontal clip test, and likewise for y.

import micropython
from array import array
import framebuf

# params layout shared by every blitter (array('i'), read through ptr32).
_STRIDE = micropython.const(0)
_BPR = micropython.const(1)
_GW = micropython.const(2)
_GH = micropython.const(3)
_DX = micropython.const(4)
_DY = micropython.const(5)
_SCALE = micropython.const(6)
_FBW = micropython.const(7)
_FBH = micropython.const(8)
_OFFSET = micropython.const(9)
_COL = micropython.const(10)


@micropython.viper
def _blit_rgb565(buf_in, data_in, params_in):
    buf = ptr16(buf_in)
    data = ptr8(data_in)
    p = ptr32(params_in)
    stride = int(p[0])
    bpr = int(p[1])
    gw = int(p[2])
    gh = int(p[3])
    dx = int(p[4])
    dy = int(p[5])
    scale = int(p[6])
    fbw = int(p[7])
    fbh = int(p[8])
    offset = int(p[9])
    col = int(p[10])

    gy = 0
    while gy < gh:
        row = offset + gy * bpr
        base_y = dy + gy * scale
        gx = 0
        while gx < gw:
            if data[row + (gx >> 3)] & (0x80 >> (gx & 7)):
                px0 = dx + gx * scale
                ry = 0
                while ry < scale:
                    yy = base_y + ry
                    if uint(yy) < uint(fbh):
                        rx = 0
                        while rx < scale:
                            xx = px0 + rx
                            if uint(xx) < uint(fbw):
                                buf[yy * stride + xx] = col
                            rx += 1
                    ry += 1
            gx += 1
        gy += 1


@micropython.viper
def _blit_gs8(buf_in, data_in, params_in):
    buf = ptr8(buf_in)
    data = ptr8(data_in)
    p = ptr32(params_in)
    stride = int(p[0])
    bpr = int(p[1])
    gw = int(p[2])
    gh = int(p[3])
    dx = int(p[4])
    dy = int(p[5])
    scale = int(p[6])
    fbw = int(p[7])
    fbh = int(p[8])
    offset = int(p[9])
    col = int(p[10]) & 0xFF

    gy = 0
    while gy < gh:
        row = offset + gy * bpr
        base_y = dy + gy * scale
        gx = 0
        while gx < gw:
            if data[row + (gx >> 3)] & (0x80 >> (gx & 7)):
                px0 = dx + gx * scale
                ry = 0
                while ry < scale:
                    yy = base_y + ry
                    if uint(yy) < uint(fbh):
                        rx = 0
                        while rx < scale:
                            xx = px0 + rx
                            if uint(xx) < uint(fbw):
                                buf[yy * stride + xx] = col
                            rx += 1
                    ry += 1
            gx += 1
        gy += 1


@micropython.viper
def _blit_mvlsb(buf_in, data_in, params_in):
    buf = ptr8(buf_in)
    data = ptr8(data_in)
    p = ptr32(params_in)
    stride = int(p[0])
    bpr = int(p[1])
    gw = int(p[2])
    gh = int(p[3])
    dx = int(p[4])
    dy = int(p[5])
    scale = int(p[6])
    fbw = int(p[7])
    fbh = int(p[8])
    offset = int(p[9])
    col = int(p[10])

    gy = 0
    while gy < gh:
        row = offset + gy * bpr
        base_y = dy + gy * scale
        gx = 0
        while gx < gw:
            if data[row + (gx >> 3)] & (0x80 >> (gx & 7)):
                px0 = dx + gx * scale
                ry = 0
                while ry < scale:
                    yy = base_y + ry
                    if uint(yy) < uint(fbh):
                        rx = 0
                        while rx < scale:
                            xx = px0 + rx
                            if uint(xx) < uint(fbw):
                                idx = (yy >> 3) * stride + xx
                                bit = 1 << (yy & 7)
                                v = int(buf[idx])
                                if col != 0:
                                    buf[idx] = v | bit
                                else:
                                    buf[idx] = v & (0xFF ^ bit)
                            rx += 1
                    ry += 1
            gx += 1
        gy += 1


_BLITTERS = {
    framebuf.RGB565: _blit_rgb565,
    framebuf.GS8: _blit_gs8,
    framebuf.MONO_VLSB: _blit_mvlsb,
}


def blitter(format):
    # Return a factory for the given framebuf format, or None if unsupported.
    fn = _BLITTERS.get(format)
    if fn is None:
        return None

    def factory(buffer, stride, width, height, col, scale):
        params = array("i", bytes(4 * 11))
        params[_STRIDE] = stride
        params[_SCALE] = scale
        params[_FBW] = width
        params[_FBH] = height
        params[_COL] = col

        def blit(data, offset, bpr, gw, gh, dx, dy):
            params[_BPR] = bpr
            params[_GW] = gw
            params[_GH] = gh
            params[_DX] = dx
            params[_DY] = dy
            params[_OFFSET] = offset
            fn(buffer, data, params)

        return blit

    return factory
