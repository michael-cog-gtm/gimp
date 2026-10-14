#!/usr/bin/env python3
"""
Writes small RGB PSD files that each contain one pixel layer and one
adjustment layer (Exposure, Photo Filter or Gradient Map), for testing the
PSD import plug-in. Only the Python standard library is used.

Usage: make-adjustment-layer-psds.py OUTPUT_DIR
"""

import colorsys
import os
import struct
import sys

WIDTH  = 256
HEIGHT = 64


def base_pixels():
    """Top half: gray ramp. Bottom half: hue sweep."""
    r, g, b = bytearray(), bytearray(), bytearray()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if y < HEIGHT // 2:
                v = (x, x, x)
            else:
                v = tuple(int(c * 255 + 0.5) for c in colorsys.hsv_to_rgb(x / WIDTH, 1.0, 1.0))
            r.append(v[0]); g.append(v[1]); b.append(v[2])
    return [bytes(r), bytes(g), bytes(b)]


def pad(data, n):
    return data + b'\0' * (-len(data) % n)


def pascal_name(name):
    raw = name.encode('ascii')
    return pad(bytes([len(raw)]) + raw, 4)


def unicode_string(s):
    return struct.pack('>I', len(s)) + s.encode('utf-16-be')


def tagged_block(key, data):
    data = pad(data, 2)
    return b'8BIM' + key + struct.pack('>I', len(data)) + data


def color16(r, g, b):
    """PSD color structure: RGB color space + four 16-bit components."""
    return struct.pack('>5H', 0, r * 257, g * 257, b * 257, 0)


def layer_record(name, bounds, channels, blocks, visible=True):
    top, left, bottom, right = bounds
    rec = struct.pack('>4i', top, left, bottom, right)
    rec += struct.pack('>H', len(channels))
    for cid, data in channels:
        rec += struct.pack('>hI', cid, len(data) + 2)
    flags = 0 if visible else 2
    rec += b'8BIM' + b'norm' + struct.pack('>BBBB', 255, 0, flags, 0)
    extra = struct.pack('>I', 0) + struct.pack('>I', 0) + pascal_name(name)
    extra += tagged_block(b'luni', unicode_string(name))
    for key, data in blocks:
        extra += tagged_block(key, data)
    rec += struct.pack('>I', len(extra)) + extra
    return rec


def write_psd(path, adjustments):
    """adjustments: list of (layer name, key, data, visible)."""
    pixels = base_pixels()
    alpha  = b'\xff' * (WIDTH * HEIGHT)
    layers = [('Background', (0, 0, HEIGHT, WIDTH),
               [(-1, alpha), (0, pixels[0]), (1, pixels[1]), (2, pixels[2])], [], True)]
    for name, key, data, visible in adjustments:
        layers.append((name, (0, 0, 0, 0),
                       [(-1, b''), (0, b''), (1, b''), (2, b'')], [(key, data)], visible))

    info = struct.pack('>h', len(layers))
    for name, bounds, channels, blocks, visible in layers:
        info += layer_record(name, bounds, channels, blocks, visible)
    for _, _, channels, _, _ in layers:
        for _, data in channels:
            info += struct.pack('>H', 0) + data
    info = pad(info, 2)
    layer_and_mask = struct.pack('>I', len(info)) + info + struct.pack('>I', 0)

    with open(path, 'wb') as f:
        f.write(b'8BPS' + struct.pack('>H6xHIIHH', 1, 3, HEIGHT, WIDTH, 8, 3))
        f.write(struct.pack('>I', 0))                      # color mode data
        f.write(struct.pack('>I', 0))                      # image resources
        f.write(struct.pack('>I', len(layer_and_mask)) + layer_and_mask)
        f.write(struct.pack('>H', 0) + b''.join(pixels))   # composite, raw


def exposure(exp, offset, gamma):
    return struct.pack('>H3f', 1, exp, offset, gamma)


def photo_filter_v2(rgb, density, preserve):
    return struct.pack('>H', 2) + color16(*rgb) + struct.pack('>IB', density, preserve)


def photo_filter_v3(lab, density, preserve):
    return struct.pack('>H3i', 3, *(int(round(c * 100)) for c in lab)) + \
           struct.pack('>IB', density, preserve)


def gradient_map(stops, reversed_=False):
    data = struct.pack('>HBB', 1, int(reversed_), 0) + unicode_string('Demo Gradient')
    data += struct.pack('>H', len(stops))
    for location, rgb in stops:
        data += struct.pack('>II', int(location * 4096), 50) + color16(*rgb) + b'\0\0'
    data += struct.pack('>H', 2) + struct.pack('>IIH', 0, 50, 100) + struct.pack('>IIH', 4096, 50, 100)
    data += struct.pack('>4HI2HIH', 2, 4096, 32, 0, 0, 0, 1, 2048, 3)
    data += struct.pack('>4H', 0, 0, 0, 0) + struct.pack('>4H', 65535, 65535, 65535, 65535)
    data += b'\0\0'
    return data


FIXTURES = {
    'adjustment-exposure.psd':
        [('Exposure +1', b'expA', exposure(1.0, 0.0, 1.0), True)],
    'adjustment-exposure-offset-gamma.psd':
        [('Exposure offset gamma', b'expA', exposure(0.0, 0.05, 2.0), True)],
    'adjustment-photo-filter-v2.psd':
        [('Warming Filter', b'phfl', photo_filter_v2((236, 138, 0), 50, 1), True)],
    'adjustment-photo-filter-v3.psd':
        [('Cooling Filter', b'phfl', photo_filter_v3((60.0, 0.0, -60.0), 50, 0), True)],
    'adjustment-gradient-map.psd':
        [('Gradient Map', b'grdm',
          gradient_map([(0.0, (0, 0, 255)), (0.5, (255, 0, 0)), (1.0, (255, 255, 0))]), True)],
    'adjustment-gradient-map-reversed.psd':
        [('Gradient Map reversed', b'grdm',
          gradient_map([(0.0, (0, 0, 0)), (1.0, (255, 255, 255))], reversed_=True), True)],
    'adjustment-all.psd':
        [('Exposure +1', b'expA', exposure(1.0, 0.0, 1.0), False),
         ('Warming Filter', b'phfl', photo_filter_v2((236, 138, 0), 50, 1), False),
         ('Gradient Map', b'grdm',
          gradient_map([(0.0, (0, 0, 255)), (0.5, (255, 0, 0)), (1.0, (255, 255, 0))]), True)],
}


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else '.'
    os.makedirs(out, exist_ok=True)
    for filename, adjustments in FIXTURES.items():
        write_psd(os.path.join(out, filename), adjustments)
        print(os.path.join(out, filename))
