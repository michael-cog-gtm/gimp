#!/usr/bin/env python3
"""
Checks that PSD Exposure, Photo Filter and Gradient Map adjustment layers
import as non-destructive filters. Generate the input files first with
make-adjustment-layer-psds.py, then run inside GIMP:

  PSD_ADJ_DIR=/path/to/psds gimp-console-3.3 -nidf \
    --batch-interpreter python-fu-eval \
    -b "exec(open('test-adjustment-layers.py').read())" --quit

Prints one PASS/FAIL line per file and exits non-zero on failure.
"""

import os
import sys

from gi.repository import Gimp, Gio

EXPECTED = {
    'adjustment-exposure.psd':
        {'Exposure +1': ['gegl:exposure']},
    'adjustment-exposure-offset-gamma.psd':
        {'Exposure offset gamma': ['gimp:levels', 'gegl:levels', 'gegl:exposure']},
    'adjustment-photo-filter-v2.psd':
        {'Warming Filter': ['gegl:color-overlay']},
    'adjustment-photo-filter-v3.psd':
        {'Cooling Filter': ['gegl:color-overlay']},
    'adjustment-gradient-map.psd':
        {'Gradient Map': ['gimp:curves', 'gimp:desaturate']},
    'adjustment-gradient-map-reversed.psd':
        {'Gradient Map reversed': ['gimp:curves', 'gimp:desaturate']},
    'adjustment-all.psd':
        {'Exposure +1':    ['gegl:exposure'],
         'Warming Filter': ['gegl:color-overlay'],
         'Gradient Map':   ['gimp:curves', 'gimp:desaturate'],
         'Background':     []},
}

folder   = os.environ.get('PSD_ADJ_DIR', '.')
failures = 0

for filename, layers in EXPECTED.items():
    path  = os.path.join(folder, filename)
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(path))
    found = {layer.get_name(): [f.get_operation_name() for f in (layer.get_filters() or [])]
             for layer in image.get_layers()}
    image.delete()

    problems = ['%s: expected %s, got %s' % (name, ops, found.get(name))
                for name, ops in layers.items() if found.get(name) != ops]
    if problems:
        failures += 1
        print('FAIL %s: %s' % (filename, '; '.join(problems)))
    else:
        print('PASS %s' % filename)

print('%d/%d files passed' % (len(EXPECTED) - failures, len(EXPECTED)))
if failures:
    sys.exit(1)
