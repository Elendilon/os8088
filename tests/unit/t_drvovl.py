#!/usr/bin/env python3
"""A driver-loaded OVERLAY may not be COMPRESSED (SPEC.md 20.13, 62.9.9).

    python3 tests/unit/t_drvovl.py

TWO `.drv` FILES ARE NOT LOADED BY THE KERNEL. `RAMPAGE.DRV` is read by
RAMDISK.DRV and `HDDTOOL.DRV` by HDD.DRV, each with `OSAPI_FILE_READ` and its
own header check - never through `drv_load`. That matters because the two
compressions are different things:

  * a compressed FILE is a 'CZ' wrapper and `OSAPI_FILE_READ` expands it
    transparently (SPEC.md 20.14.3);
  * a compressed DRIVER is a v4 container whose file is SHORTER than the
    `image` field at +8, and the only thing that expands one is `drv_expand`,
    inside `drv_load` (SPEC.md 20.13).

So a compressed overlay arrives at its loader as its own compressed bytes, the
loader's header check refuses it, and what the user sees is not a decode error
- it is `Ram Disk needs the system disk`, with the driver loaded, its Control
Panel cells published, and every control on the page inert. That shipped: the
compression pass gave `$(BUILD)/rampage.drv` the `$(OS88DRV)` recipe, which
carries `$(PKGZARG)`, where `hddtool.drv` had always spelled the tool out
without it. `tests/rdup.py` reported it as three UI failures and the reason
took a screenshot to see.

The saving was 646 bytes of a 360KB disk. What it cost was the RAM disk.

**THIS GATE IS THE RULE, not the two names.** It reads the drivers' own source
for the file names they load and checks each one on every shipped image, so a
third overlay is covered the day it is written rather than the day somebody
notices its page is dead.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from harness import check, done                           # noqa: E402
import os88drv                                            # noqa: E402
import os88build                                          # noqa: E402

# A driver naming another driver's FILE is the marker: `db 'HDDTOOL.DRV', 0`.
NAMED = re.compile(rb"db\s+'([A-Z0-9_]{1,8}\.DRV)'\s*,\s*0")


def overlays():
    """Every `.DRV` a DRIVER loads by name, out of the drivers' own source."""
    out = {}
    for dirpath, _, names in os.walk(os.path.join(ROOT, "drivers")):
        for n in names:
            if not n.endswith((".asm", ".inc")):
                continue
            p = os.path.join(dirpath, n)
            with open(p, "rb") as f:
                for m in NAMED.finditer(f.read()):
                    out.setdefault(m.group(1).decode(),
                                   os.path.relpath(p, ROOT))
    return out


def main():
    found = overlays()
    check(bool(found),
          "the driver sources still name their overlays",
          "an empty read means the `db 'X.DRV', 0` idiom has changed and this "
          "gate would pass by testing nothing - the failure dispcp.py and "
          "mkclick.py were both in (docs/WRITING-TESTS.md 1)")
    for name in sorted(found):
        stem = name.split(".")[0].lower()
        p = os88build.at("build/%s.drv" % stem)
        if not os.path.isabs(p):
            p = os.path.join(ROOT, p)
        if not os.path.exists(p):
            continue                    # not built in this tree; t_image covers
        with open(p, "rb") as f:        # whether it should have been
            raw = f.read()
        img = os88drv.image_unwrap(raw)
        check(len(img) == len(raw),
              "%s is not compressed" % name,
              "%s loads it with OSAPI_FILE_READ, which expands a 'CZ' FILE "
              "and not a v4 DRIVER container - so a compressed one is refused "
              "by that loader's own header check and the feature is silently "
              "dead. Build it with `python3 tools/os88drv.py` and NOT "
              "$(OS88DRV), which carries $(PKGZARG)." % found[name],
              got="file %d, image %d" % (len(raw), len(img)),
              want="file == image")
    return done("t_drvovl")


if __name__ == "__main__":
    sys.exit(main())
