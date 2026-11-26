#!/usr/bin/env python3
"""Actual Breadboard XT UI callbacks vs a clipped host glass/SDK model.

This is host behavior/cost evidence, not target rendering/ABI validation.
Builds inside TemporaryDirectory and never touches target build products.
"""
from pathlib import Path
import os
import re
import sys
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent


def main():
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='breadxt-ui-host-') as folder:
        folder = Path(folder)
        # Use the actual SDK declarations, removing only three target-layout
        # assertions that cannot hold for host pointers/ints. No second ABI list.
        header = (ROOT/'apps/cc/os88.h').read_text()
        header = re.sub(r'^typedef char os88__sz_.*\n','',header,flags=re.M)
        (folder/'sdk-host.h').write_text(header)
        # The face's art, built privately rather than read out of build/:
        # without it every family would run the PLAIN face (SPEC.md
        # 130.6.3), which the art-face checks are not about.
        art = folder/'BBART.BIN'
        subprocess.run([sys.executable,str(ROOT/'tools/os88bbart.py'),'build','-o',str(art)],
                       check=True,cwd=ROOT,stdout=subprocess.DEVNULL)
        env = dict(os.environ,BB_ART=str(art))
        binary = folder/'uiglasstest'
        subprocess.run([os.environ.get('CC','cc'),'-std=c99','-Wall','-Wextra','-Werror',
                        '-Wno-comment','-Wno-logical-op-parentheses',
                        # gcc's names for what the clang flag above
                        # silences, and its maybe-uninitialized on a
                        # value set and read under one test (face.c lvl)
                        '-Wno-misleading-indentation','-Wno-parentheses',
                        '-Wno-maybe-uninitialized','-Wno-unknown-warning-option',
                        '-Wno-unused-variable','-Wno-unused-but-set-variable',
                        '-O1','-g','-fsanitize=address,undefined','-I',str(folder),
                        str(ROOT/'apps/breadxt/hosttest/uiglasstest.c'),
                        '-lm','-o',str(binary)],check=True,cwd=ROOT)
        failed = []
        for mode in ('queue','modal','damage','wide','wide-dismiss','locate-help','locate-scope','locate-offscreen','locate-none','stale','scope-hold','replace-led','sections','sections-plain'):
            positive = subprocess.run([str(binary),mode],cwd=ROOT,env=env)
            if positive.returncode:
                failed.append(mode)
            # Each hook deliberately reintroduces the class of defect under
            # test: bypass a callback guard, repaint the whole face for one
            # keystroke, drop damage, or draw outside a section's rect.
            if mode.startswith('locate-'):
                continue
            negative = subprocess.run([str(binary),mode,'negative'],text=True,
                                      capture_output=True,cwd=ROOT,env=env)
            assert negative.returncode == 1 and 'FAIL ui:' in negative.stderr, (mode,negative.stdout,negative.stderr)
            print(f'breadxt UI {mode}: injected defect fails as intended',flush=True)
        assert not failed, f'positive UI families failed: {failed}'
    print(f'breadxt UI host elapsed: {time.monotonic()-started:.2f}s')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
