#!/usr/bin/env python3
"""The BOOT LADDER page: every discrete move of memory from reset to the first
desktop frame, walkable, with the timeline each one costs on a 4.77MHz 8088.

    python3 tools/os88ladder.py                     # -> build/bootladder.html
    python3 tools/os88ladder.py --selfcheck         # ...does this still WORK?
    python3 tools/os88ladder.py --no-measure        # structure only, no emulator

**ON DEMAND. NOTHING IN `make` RUNS THIS AND NOTHING SHOULD.** It boots the
tree under MartyPC and single-steps a whole boot through forty-odd
breakpoints, which is minutes - `make test-fast`'s whole budget is 30 seconds
and a row that wanted 4 would already be the most expensive thing in it.

**SO THE PAGE GOES STALE, AND THAT IS THE DESIGN.** Nothing rebuilds it when
`kmain` gains a call, when a section moves in the ladder, when a constant is
retuned or when somebody makes the disk faster. The page it wrote last time
will still open, still animate, and still be confidently wrong.

**THE FIRST THING TO DO WHEN SOMEONE ASKS FOR THIS PAGE IS TO RUN
`--selfcheck` AND FIX WHAT IT SAYS - before regenerating, and before
believing a number on the page you already have.** The check is not a
formality: this tool reads eleven constants out of five source files by
name, resolves nine symbols, and maps a measured phase list onto a fixed
model of the boot. Every one of those is a thing the tree is allowed to
change without telling anybody, and each has its own refusal below naming
the file to go and look at. A rename fails the check; it does not quietly
produce a page with a hole in it.

WHAT IS MEASURED AND WHAT IS DERIVED, because the page says so per number
and this is where the rule comes from:

  * MEASURED - every millisecond on the timeline, off MartyPC's own cycle
    counter at 4.772727MHz with the floppy's mechanics modelled
    (docs/MARTYPC-DEBUG.md). Also the loading bar's real numerator and
    denominator, read out of `[spl_done]`/`[spl_total]` in the blob at each
    stop, and the heap's arena and claim table, read out of `mem_base`,
    `mem_top` and `mem_tab`.
  * DERIVED - the memory addresses, which come from the ladder
    `tools/kernsize.py` measures out of the built kernel, and the handful of
    sub-millisecond costs inside the boot sector that are arithmetic on the
    8088's own instruction timings rather than a bracket of their own. The
    page marks these.

**A DISK FIGURE OFF A GLaBIOS MACHINE IS NOT A FIELD FIGURE**
(docs/MARTYPC-DEBUG.md). The IBM 5150 ROM is not in this tree and cannot be,
so `--machine` defaults to the IBM-ROM 5150 and FALLS BACK to its GLaBIOS
twin when the ROM is absent - and the page is stamped with which one ran and
what that costs. What does NOT move with the ROM is the mechanical column,
which is the FDC model PERFORMANCE.md Set 37 calibrated against the real
5150; what does is the ROM's own code, which is two of the four things a
boot spends time on.
"""

import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

HZ = 4772727.0                  # the 5150's dot clock / 3, MartyPC's own rate
TICK_HZ = 18.2065               # the BIOS tick SPEC.md 15.4's timer counts
KERNEL_SEG = 0x0060


class Stale(SystemExit):
    """The tree moved under the tool. Always names the file to go and look at."""

    def __init__(self, what, where, fix):
        SystemExit.__init__(
            self, "os88ladder: %s\n"
                  "  it lived in: %s\n"
                  "  what to do : %s\n"
                  "  (this is the staleness this tool's header warns about - "
                  "the page is NOT rebuilt by `make`)" % (what, where, fix))


# -----------------------------------------------------------------------------
# 1. What the TREE says - constants, the ladder, the volume. No emulator.
# -----------------------------------------------------------------------------

def grab(path, pattern, what, fix):
    """One constant out of one source file, or a refusal that names both.

    Every scrape in this file goes through here on purpose. A `%s` that no
    longer matches is the single commonest way a generator like this rots,
    and the difference between a tool that says which line of which file to
    open and one that says `NoneType has no group` is most of what makes it
    worth running a year later.
    """
    src = open(os.path.join(ROOT, path), errors="replace").read()
    m = re.search(pattern, src, re.M)
    if not m:
        raise Stale("%s is gone" % what, "%s  /%s/" % (path, pattern), fix)
    return int(m.group(1), 0)


def constants():
    """The dozen numbers the boot is shaped by, read where they are defined."""
    c = {}
    c["BOOT2_SECS"] = grab("kernel/kernel.asm", r"^BOOT2_SECS\s+equ\s+(\d+)",
                           "BOOT2_SECS - the blob's length in sectors",
                           "find its new name in kernel/kernel.asm and update "
                           "constants(); the Makefile scrapes the same line")
    c["SPL_RESIDENT"] = grab("kernel/splash.inc", r"^SPL_RESIDENT\s+equ\s+(\d+)",
                             "SPL_RESIDENT - sectors before the bar can draw",
                             "kernel/splash.inc; it decides which stage the "
                             "loading screen first appears in")
    c["SPL_POST"] = grab("kernel/splash.inc", r"^SPL_POST\s+equ\s+(\d+)",
                         "SPL_POST - notches added to the bar's DENOMINATOR",
                         "kernel/splash.inc; the bar's arithmetic on the page "
                         "is done/(sectors+SPL_POST)")
    c["SPL_BAR_PX"] = grab("kernel/splash.inc", r"^SPL_BAR_PX\s+equ\s+(\d+)",
                           "SPL_BAR_PX - the bar's interior width",
                           "kernel/splash.inc; the page draws the bar to scale")
    c["SPL_BAR_H"] = grab("kernel/splash.inc", r"^SPL_BAR_H\s+equ\s+(\d+)",
                          "SPL_BAR_H", "kernel/splash.inc")
    c["SPL_TTLC"] = grab("kernel/splash.inc", r"^SPL_TTLC\s+equ\s+(\d+)",
                         "SPL_TTLC - the caption field, in cells",
                         "kernel/splash.inc")
    c["RELOC_ADJ"] = grab("boot/boot.asm", r"^RELOC_ADJ\s+equ\s+(0x[0-9A-Fa-f]+)",
                          "RELOC_ADJ - where stage 1 relocates to",
                          "boot/boot.asm; the page places the sector at "
                          "int12h*64 - RELOC_ADJ")
    c["BOOT_SECT"] = grab("boot/boot.asm", r"^BOOT_SECT\s+equ\s+(\d+)",
                          "BOOT_SECT", "boot/boot.asm")
    c["BOOT_STACK"] = grab("boot/boot.asm", r"^BOOT_STACK\s+equ\s+(\d+)",
                           "BOOT_STACK - stage 1's stack, under its own body",
                           "boot/boot.asm")
    c["DPT_AT"] = grab("boot/boot.asm", r"^DPT_AT\s+equ\s+(0x[0-9A-Fa-f]+)",
                       "DPT_AT - where the diskette parameter table is copied",
                       "boot/boot.asm and boot/boot2.asm, which must agree")
    c["KSIG_OFF"] = grab("boot/boot2.asm", r"^KSIG_OFF\s+equ\s+(\d+)",
                         "KSIG_OFF - SPEC.md 18.93.1's canary probe",
                         "boot/boot2.asm; the Makefile types the same number")
    c["STK0_SIZE"] = grab("kernel/kernel.asm", r"^STK0_SIZE\s+equ\s+(\d+)",
                          "STK0_SIZE - task 0's stack",
                          "kernel/kernel.asm's ladder")
    c["MEM_MAX"] = grab("kernel/memory.inc", r"^MEM_MAX\s+equ\s+(\d+)",
                        "MEM_MAX - heap claim records",
                        "kernel/memory.inc; the page walks mem_tab")
    c["MC_SIZE"] = grab("kernel/memory.inc", r"^MC_SIZE\s+equ\s+(\d+)",
                        "MC_SIZE - one claim record",
                        "kernel/memory.inc; if the record grew, the walk in "
                        "heap_now() below reads the wrong words")
    # MIN_RAM_KB is NOT scraped: kernel.asm defines it twice, once per build,
    # and a regex picks whichever it happens to reach. tools/kernsize.py is
    # told which build it is measuring and reports the one that applies.
    return c


def ladder(build="build", defines=()):
    """The segment ladder, out of the tool that MEASURES the built kernel.

    Never re-derived here. `tools/kernsize.py --json` assembles the kernel and
    reports the sizes the ladder falls out of, so the page cannot describe a
    layout the tree does not have - which is exactly what a hand-kept copy of
    these numbers does, and docs/BOOT-LADDER-PLAN.md's own tables are the
    worked example: they quote a ladder three changes old.
    """
    cmd = ["python3", os.path.join(ROOT, "tools", "kernsize.py"),
           "--json", "--build", build] + ["-D" + d for d in defines]
    try:
        out = subprocess.check_output(cmd, cwd=ROOT)
    except (subprocess.CalledProcessError, OSError) as e:
        raise Stale("tools/kernsize.py would not answer (%s)" % e,
                    "tools/kernsize.py --json",
                    "run `make` first - kernsize measures build/kernel.bin")
    k = json.loads(out)
    for want in ("kseg", "imgpara", "coldpara", "fatpara", "lowpara",
                 "vgabufpara", "kend", "ksize", "text", "bss", "cold",
                 "lowbss", "ovlw", "ovl", "boot2", "stk0"):
        if want not in k:
            raise Stale("tools/kernsize.py no longer reports `%s`" % want,
                        "tools/kernsize.py --json",
                        "its JSON keys changed; re-map them in ladder()")
    p = k["kseg"]
    k["cold_seg"] = p = p + k["imgpara"]
    k["fat_seg"] = p = p + k["coldpara"]
    k["low_seg"] = p = p + k["fatpara"]
    k["vgabuf_seg"] = p = p + k["lowpara"]
    if p + k["vgabufpara"] != k["kend"]:
        raise Stale("the ladder does not add up: %#x + %d != kend %#x"
                    % (p, k["vgabufpara"], k["kend"]),
                    "kernel/kernel.asm's ladder / tools/kernsize.py",
                    "a rung was inserted or removed - teach ladder() the new "
                    "one, in kernel.asm's own order")
    return k


def volume(path):
    """The BPB and the root directory of a built image - the boot's own view.

    Where KERNEL.SYS starts is not a constant anywhere: boot/boot.asm derives
    it from the four BPB fields below, exactly as done here, so that a change
    to the disk layout moves the page and the sector together.
    """
    if not os.path.exists(path):
        raise Stale("no image at %s" % path, path,
                    "run `make` - the page describes a disk that exists")
    d = open(path, "rb").read()
    v = {}
    v["bps"], v["spc"] = struct.unpack_from("<HB", d, 11)
    v["rsvd"], = struct.unpack_from("<H", d, 14)
    v["nfat"] = d[16]
    v["rootent"], = struct.unpack_from("<H", d, 17)
    v["tot16"], = struct.unpack_from("<H", d, 19)
    v["media"] = d[21]
    v["fatsz"], = struct.unpack_from("<H", d, 22)
    v["spt"], = struct.unpack_from("<H", d, 24)
    v["heads"], = struct.unpack_from("<H", d, 26)
    if v["bps"] != 512 or not v["spt"] or not v["heads"]:
        raise Stale("the BPB in %s is not one this page understands" % path,
                    "tools/os88disk.py writes it", "check the image built")
    v["data_lba"] = (v["rsvd"] + v["nfat"] * v["fatsz"]
                     + (v["rootent"] * 32 + v["bps"] - 1) // v["bps"])
    # KERNEL.SYS is allocated first and contiguously, which is the whole
    # reason a 512-byte sector can read it with flat arithmetic.
    off = (v["rsvd"] + v["nfat"] * v["fatsz"]) * v["bps"]
    v["kernel"] = None
    for i in range(v["rootent"]):
        e = d[off + i * 32:off + i * 32 + 32]
        if not e or e[0] in (0, 0xE5) or e[11] & 0x08:
            continue
        if e[:11] == b"KERNEL  SYS":
            clus, = struct.unpack_from("<H", e, 26)
            size, = struct.unpack_from("<I", e, 28)
            v["kernel"] = {"lba": v["data_lba"] + (clus - 2) * v["spc"],
                           "size": size,
                           "sectors": (size + v["bps"] - 1) // v["bps"]}
            break
    if not v["kernel"]:
        raise Stale("KERNEL.SYS is not in %s's root directory" % path, path,
                    "the boot sector looks for the FIRST file in the data "
                    "area; if the image layout changed, so has the boot")
    v["md5"] = hashlib.md5(d).hexdigest()
    return v


# -----------------------------------------------------------------------------
# 2. What the MACHINE says - one boot, walked. Needs MartyPC.
# -----------------------------------------------------------------------------

# The IBM 5150 ROM is IBM's and is not in this tree (tools/martypc/build.sh).
# The GLaBIOS twin of the same machine boots without it and is FASTER than any
# 5150 ever was, so the page is stamped with which one ran.
FIELD_MACHINE = "os8088_5150_cga"
TWIN_MACHINE = "os8088_5150_cga_gla"


def machine_available(name):
    """Is this MartyPC config's ROM set actually present?"""
    run = os.path.join(ROOT, "build", "martypc", "run")
    cfg = os.path.join(ROOT, "tools", "martypc", "configs", "os8088_machines.toml")
    if not (os.path.isdir(run) and os.path.exists(cfg)):
        return False
    src = open(cfg, errors="replace").read()
    m = re.search(r'name\s*=\s*"%s"(.*?)(?=\n\[\[machine\]\]|\Z)' % re.escape(name),
                  src, re.S)
    if not m:
        return False
    r = re.search(r'rom_set\s*=\s*"([^"]+)"', m.group(1))
    if not r:
        return False
    if not r.group(1).startswith("ibm"):
        return True                     # GLaBIOS ships with the emulator
    roms = os.path.join(run, "media", "roms")
    return os.path.isdir(roms) and any(f.upper().endswith(".BIN")
                                       for f in os.listdir(roms))


def u16(b, i=0):
    return b[i] | (b[i + 1] << 8)


class Probe(object):
    """One live guest, with the four questions this page asks of it."""

    def __init__(self, m, lad, defines):
        import os88sym
        self.m, self.lad = m, lad
        self.blob = lad["kend"] * 16
        self.sym = os88sym.syms(defines)
        for want in ("spl_done", "spl_total", "kmain", "spl_tick"):
            if want not in self.sym:
                raise Stale("the kernel has no symbol `%s`" % want,
                            "kernel/splash.inc, kernel/kernel.asm",
                            "the page reads it to draw the loading bar; find "
                            "what replaced it")
        import os88sym as _s
        self.mem_base = _s.linear("mem_base", defines)
        self.mem_top = _s.linear("mem_top", defines)
        self.mem_tab = _s.linear("mem_tab", defines)

    # `.boot2` has no fixed segment (os88sym refuses to place it), and it does
    # not need one here: stage 1 reads the blob to the heap's floor, so the
    # segment is the ladder's own `kend`.
    def blobaddr(self, name):
        return self.blob + self.sym[name]

    def bar(self):
        """The loading bar's REAL numerator and denominator, from the blob."""
        done = u16(self.m.read(self.blobaddr("spl_done"), 2))
        total = u16(self.m.read(self.blobaddr("spl_total"), 2))
        return {"done": done, "total": total}

    def heap(self, mc_size, mem_max):
        """The arena's ends and every live claim, out of the kernel's own table.

        Before mem_init these words are whatever was in RAM, so the caller
        decides when to start believing them - `base` below zero-lengths the
        arena and the model treats that as "the heap does not exist yet".
        """
        base = u16(self.m.read(self.mem_base, 2))
        top = u16(self.m.read(self.mem_top, 2))
        claims = []
        raw = self.m.read(self.mem_tab, mc_size * mem_max)
        for i in range(mem_max):
            r = raw[i * mc_size:(i + 1) * mc_size]
            seg, para = u16(r, 0), u16(r, 2)
            if seg and para:
                claims.append({"seg": seg, "para": para, "own": u16(r, 4)})
        return {"base": base, "top": top, "claims": claims}


def walk(image, machine, defines, lad, cons, limit=240.0, verbose=True):
    """Boot once, stopping wherever the page has something to say.

    THE BOUNDARIES ARE THE PAGE'S OWN, which is why this does not simply call
    tools/os88boot.py: that tool charges the whole boot sector as three rows,
    and this page's stages cut it at the two places a discrete thing MOVES -
    the far jump into stage 2, and the sector at which the loading screen
    first has enough of itself in RAM to draw. Both are addresses, so both are
    breakpoints; neither is a phase os88boot has a name for.

    `kmain`'s rows ARE os88boot's, imported rather than re-derived, so the two
    instruments cannot drift apart about what a phase is called.
    """
    import os88marty
    import os88boot

    sites = os88boot.collapse(os88boot.callsites(defines))
    if len(sites) < 20:
        raise Stale("os88boot.callsites() found only %d calls in kmain"
                    % len(sites),
                    "tools/os88boot.py callsites()",
                    "kmain has ~30; the listing parser has lost the macro "
                    "expansions again - OVWCALL and friends list as `%1`")

    ev = []                             # the timeline, in cycle order
    t = {"prev": 0, "pdisk": None}

    def close(kind, name, cyc, disk, extra=None):
        row = {"kind": kind, "name": name,
               "t0": t["prev"] * 1000.0 / HZ, "t1": cyc * 1000.0 / HZ,
               "ms": (cyc - t["prev"]) * 1000.0 / HZ}
        for k in ("reads", "read_sectors", "seeks", "seek_cylinders",
                  "transfer_ms", "seek_ms"):
            row[k] = disk.get(k, 0) - (t["pdisk"] or {}).get(k, 0)
        if extra:
            row.update(extra)
        ev.append(row)
        t["prev"], t["pdisk"] = cyc, disk
        return row

    with os88marty.launch(image, machine=machine, boot=False) as m:
        p = Probe(m, lad, defines)
        kmain = KERNEL_SEG * 16 + p.sym["kmain"]
        spl_tick = p.blobaddr("spl_tick")
        stage2 = p.blob                 # `.boot2` offset 0 is `jmp boot2_entry`

        # --- the machine's own ROM, which os8088 does not write --------------
        m.bp_exec(0x7C00)
        m.run()
        if m.wait_stop(limit) is None:
            raise Stale("the machine never reached 0000:7C00", machine,
                        "the image is not bootable on this config, or the "
                        "emulator is not the one this tool expects")
        close("rom", "post", m.status()["cycles"], m.disk())
        ramkb = u16(m.read(0x413, 2))   # the BDA's own answer to int 12h

        vec = m.read(0x13 * 4, 4)
        rom13 = (u16(vec, 2) << 4) + u16(vec, 0)

        # --- stage 1 and stage 2, bracketed at every call that costs ---------
        # int 13h is entered through the vector and returns through an IRET
        # frame; spl_tick is a NEAR call from inside the blob and returns
        # through two bytes. GETTING THAT WRONG IS A HANG, NOT AN ERROR: the
        # bracket runs to an address the boot never reaches and the walk sits
        # there until the timeout. tools/os88boot.py still brackets the splash
        # as a FAR call at the pinned 0060:0008 entry SPEC.md 2.9.4 deleted,
        # which is why it reports `boot: splash x0` on this tree.
        #
        # THE ONE `mem` BREAKPOINT IS WHAT SEPARATES TWO STAGES: relocating
        # the sector and taking over the diskette parameter table are one
        # unbroken run of code with no call between them, so the only edge to
        # stop on is the first touch of DPT_AT itself. It is DISARMED the
        # moment it fires - the vector points there afterwards, so the BIOS
        # reads those eleven bytes on every floppy operation for the rest of
        # the boot and the walk would spend the whole load stopping on them.
        seen2 = False
        dptbp = {"type": "mem", "addr": cons["DPT_AT"]}
        while True:
            bps = [{"type": "exec", "addr": a}
                   for a in (rom13, spl_tick, stage2, kmain)]
            if dptbp:
                bps.append(dptbp)
            m.breakpoints(bps)
            m.run()
            if m.wait_stop(limit) is None:
                raise Stale("the boot never reached kmain", machine,
                            "a breakpoint address is wrong, or the boot "
                            "stopped - run the image by hand and look")
            st = m.status()
            ip, cyc = st["flat_ip"], st["cycles"]
            if ip == kmain:
                close("kernel", "stage 2: loop", cyc, m.disk())
                break
            if ip == stage2:
                close("kernel", "stage 1: sector code", cyc, m.disk())
                seen2 = True
                continue
            if dptbp and ip not in (rom13, spl_tick):
                # Not one of ours: the DPT write, which is the only other
                # thing armed. Close the relocation here and stop watching.
                close("kernel", "relocate", cyc, m.disk())
                dptbp = None
                continue
            r = m.regs()
            near = (ip == spl_tick)
            name = "splash tick" if near else "int 13h"
            close("kernel", "stage %d: %s code" % (2 if seen2 else 1,
                                                  "loader" if seen2 else "sector"),
                  cyc, m.disk())
            frame = m.read((r["ss"] << 4) + r["sp"], 2 if near else 4)
            back = ((r["cs"] << 4) + u16(frame) if near
                    else (u16(frame, 2) << 4) + u16(frame, 0))
            if near:
                # AX = sectors loaded, DX = total; the bar's own arguments.
                extra = {"arg_done": r["ax"], "arg_total": r["dx"]}
            else:
                # AH is the function and AL the sectors asked for, so the page
                # can say "reset the controller" where it means that rather
                # than calling every int 13h a read.
                extra = {"fn": (r["ax"] >> 8) & 0xFF, "want": r["ax"] & 0xFF,
                         "cyl": ((r["cx"] >> 8) & 0xFF)
                                | ((r["cx"] & 0xC0) << 2),
                         "sec": r["cx"] & 0x3F, "head": (r["dx"] >> 8) & 0xFF,
                         "drive": r["dx"] & 0xFF, "dest": r["es"]}
                name = ("int 13h reset" if extra["fn"] == 0
                        else "int 13h read %d" % extra["want"])
            m.bp_exec(back)
            m.run()
            if m.wait_stop(limit) is None:
                raise Stale("a %s never returned to %05X" % (name, back),
                            "the bracket in walk()",
                            "spl_tick is a NEAR call and int 13h an IRET - if "
                            "either changed shape, so must this")
            close("disk" if not near else "draw", name,
                  m.status()["cycles"], m.disk(), extra)
            if verbose:
                sys.stderr.write("  %-16s %8.1f ms\n" % (name, ev[-1]["ms"]))

        # --- kmain, one row per call, os88boot's own list -------------------
        for addr, name, n in sites:
            m.bp_exec(KERNEL_SEG * 16 + addr)
            m.run()
            if m.wait_stop(limit) is None:
                raise Stale("kmain never returned from %s" % name,
                            "kernel/kernel.asm's kmain",
                            "the call list and the boot disagree - regenerate "
                            "after `make`, and see os88boot.callsites()")
            row = close("kernel", name if n == 1 else "%s x%d" % (name, n),
                        m.status()["cycles"], m.disk())
            row["bar"] = p.bar()
            row["heap"] = p.heap(cons["MC_SIZE"], cons["MEM_MAX"])
            # WATCH THE FAT WINDOW. `.ovlw` is boot-overlay CODE that rides
            # the kernel's own read onto FAT_SEG and is forfeit at the first
            # mount (SPEC.md 2.5.3) - so somewhere in this walk those bytes
            # stop being the code that is running and become a FAT snapshot.
            # Digesting them at every stop finds the phase it happened in
            # WITHOUT the page having to assert which one, and proves the
            # claim rather than repeating it.
            row["fatw"] = hashlib.md5(
                m.read(lad["fat_seg"] * 16, 256)).hexdigest()[:8]
            if verbose:
                sys.stderr.write("  %-22s %8.1f ms  bar %d/%d\n"
                                 % (row["name"], row["ms"],
                                    row["bar"]["done"], row["bar"]["total"]))

        total = t["prev"]
        longest = (t["pdisk"] or {}).get("longest_run", 0)
        m.bp_exec()
        ticks = u16(m.read(KERNEL_SEG * 16 + 0x000C, 2))

    return {"machine": machine, "image": os.path.basename(image),
            "ram_kb": ramkb, "events": ev,
            "total_ms": total * 1000.0 / HZ, "longest_run": longest,
            "boot_ticks": ticks, "boot_ticks_ms": ticks * 1000.0 / TICK_HZ,
            "taken": time.strftime("%Y-%m-%d %H:%M:%S")}


# -----------------------------------------------------------------------------
# 3. The MODEL - which measured phase belongs to which stage, and what memory
#    looks like once that stage has happened.
# -----------------------------------------------------------------------------
#
# A STAGE IS ONE DISCRETE MOVE OF MEMORY, which is the whole organising idea of
# the page: the boot is not a list of routines, it is a sequence of things
# arriving at, and leaving, addresses. `phases` is the measured work that
# happens between one arrival and the next, named exactly as the instruments
# name it so that a phase which vanishes or appears cannot be absorbed
# silently - assign() refuses on either.
STAGES = [
    dict(id="post", short="ROM + sector", title="The ROM, and one sector at 0000:7C00",
         moved="512 bytes: the volume boot record",
         take=dict(until="post")),
    dict(id="reloc", short="relocate", title="The sector copies itself to the top of RAM",
         moved="those 512 bytes again, at the machine's last address",
         take=dict(until="relocate")),
    dict(id="dpt", short="int 1Eh", title="The diskette parameter table becomes ours",
         moved="11 bytes to 0000:0580",
         take=dict(count=1)),
    dict(id="blob", short="loader", title="Stage 2 lands on the heap's floor",
         moved="the loader, the loading screen and the boot overlay",
         take=dict(before="stage 2: loader code")),
    dict(id="splash", short="splash up", title="The loading screen appears",
         moved="the first sectors of the kernel, and the framebuffer",
         take=dict(until="splash tick")),
    dict(id="kernel", short="kernel load", title="The rest of KERNEL.SYS arrives",
         moved="everything from .text to the boot overlay's other half",
         take=dict(until="stage 2: loop")),
    dict(id="kmain", short="kmain", title="Into kmain - the stack moves to LOW_SEG",
         moved="task 0's stack, and the clock, adapter and CPU tier",
         take=dict(phases=["dsk_boot_from_x", "cpu_detect", "xm_sniff",
                           "dsk_dpt_init_x", "sched_init", "sch_idle_start",
                           "evq_init", "clk_init", "vid_init", "vid_ctx_init",
                           "vid_probe_avail", "vid_disp_init"])),
    dict(id="heap", short="heap", title="The claim heap opens above the blob",
         moved="the arena: everything from the loader's last byte to the top",
         take=dict(phases=["mem_init_x", "mod_init_x"])),
    dict(id="ui", short="font + WM", title="The typeface, the window manager and the bar",
         moved="font glyphs into .lowbss, and the first heap claims",
         take=dict(phases=["font_init", "ovl_font_init", "wm_init",
                           "band_init", "menu_init", "inst_init",
                           "splf_step"])),
    dict(id="mouse", short="mouse", title="mouse_init - the identify window",
         moved="nothing: the longest phase of the boot that is not the disk",
         take=dict(phases=["ovl_spl_msg_mouse", "mouse_init", "splf_step"])),
    dict(id="desk", short="desktop", title="Volumes, the dock, the drivers table",
         moved="desktop zones and the driver table, in .bss and the heap",
         take=dict(phases=["ovl_spl_msg_fdd", "desk_init", "dock_init",
                           "files_init_x", "loader_init_x", "drv_init_x",
                           "drv_snd_sniff", "snd_init", "splf_step"])),
    dict(id="drvboot", short="mount A:", title="A: is mounted - and the mount eats the overlay",
         moved="the FAT snapshot, over 5KB of code that was still running",
         take=dict(phases=["drv_boot_x", "xm_boot_x", "thm_set"])),
    dict(id="unblob", short="blob back", title="The loader's 4KB go back to the heap",
         moved="the blob's rung, released and compacted away",
         take=dict(phases=["spl_finish", "mem_unblob_x"])),
    dict(id="paint", short="first frame", title="The first desktop frame",
         moved="nothing new - the screen, at last",
         take=dict(phases=["gfx_lock", "wm_paint_all", "gfx_unlock",
                           "cursor_show", "drv_notice_x"])),
]


def basename(name):
    """A measured phase's name with the walk's own decorations taken off."""
    n = re.sub(r" x\d+$", "", name)
    return re.sub(r"^(int 13h read) \d+$", r"\1", n)


def check_coverage(defines):
    """Does the STAGES table still describe the kmain that is in the tree?

    THE ONE CHECK THAT MATTERS, and the reason it is a check rather than a
    comment: the boot-sector stages are cut at addresses this tool chooses, so
    they cannot drift - but kmain's is a list of calls that somebody edits, and
    a call added between two of them would otherwise be absorbed into whichever
    stage happened to be adjacent, with its milliseconds and its story silently
    charged to the wrong picture.
    """
    import os88boot
    live = [n for _, n, _ in os88boot.collapse(os88boot.callsites(defines))]
    named = set()
    for st in STAGES:
        named |= set(st["take"].get("phases", []))
    missing = [n for n in live if n not in named]
    if missing:
        raise Stale("kmain calls nothing on the page knows about: %s"
                    % ", ".join(sorted(set(missing))),
                    "kernel/kernel.asm's kmain, against STAGES here",
                    "add each to the stage whose STORY it belongs to - and if "
                    "it is a new discrete move of memory, it wants a stage of "
                    "its own, which is what this page is a ladder OF")
    # The other direction is a warning rather than a refusal: a phase this
    # table names and the tree no longer has costs the page nothing (the stage
    # simply gets fewer rows), and both `font_init`/`ovl_font_init` and
    # `band_init` are legitimately absent depending on how the kernel is built.
    return [n for n in sorted(named) if n not in live]


def assign(events, defines=("KERN_BIG",)):
    """Hand every measured event to the stage that wants it, in order.

    Two kinds of boundary, because the boot has two kinds. Down in the boot
    sector a stage ends at an ADDRESS the walk stopped on, so the rule is
    positional - `until` this event, or `before` that one. In kmain a stage
    ends where a NAMED call does, so the rule is the phase list, and an
    unnamed phase is a refusal.
    """
    check_coverage(defines)
    out = [dict(st, events=[]) for st in STAGES]
    i = 0
    for s, st in enumerate(out):
        t = st["take"]
        last = (s == len(out) - 1)
        while i < len(events):
            e = events[i]
            n = basename(e["name"])
            if "phases" in t:
                if n not in t["phases"]:
                    break
                st["events"].append(e); i += 1
            elif "before" in t:
                if n == t["before"]:
                    break
                st["events"].append(e); i += 1
            elif "count" in t:
                st["events"].append(e); i += 1
                if len(st["events"]) >= t["count"]:
                    break
            else:                                   # `until`, inclusive
                st["events"].append(e); i += 1
                if n == t["until"]:
                    break
        if not st["events"] and not last:
            raise Stale("stage `%s` got no measured phase at all" % st["id"],
                        "STAGES in tools/os88ladder.py",
                        "the work it names has moved or gone; either the "
                        "stage should go too, or its `take` is out of date")
    if i < len(events):
        raise Stale("%d measured phases fell off the end, starting at `%s`"
                    % (len(events) - i, events[i]["name"]),
                    "STAGES in tools/os88ladder.py",
                    "the last stage stopped taking events before the boot "
                    "did - check what kmain does after wm_paint_all")
    return out


def owner_tags():
    """{value: name} for every kernel/purgeable claim tag, out of memory.inc.

    Scraped so a claim on the map is named by the constant that made it. A tag
    this does not know still renders - as its number - which is the right
    failure for a page: a claim nobody can name is more interesting than none.
    """
    src = open(os.path.join(ROOT, "kernel", "memory.inc"), errors="replace").read()
    out = {}
    for m in re.finditer(r"^(MEM_K_\w+)\s+equ\s+(0x[0-9A-Fa-f]+)", src, re.M):
        out[int(m.group(2), 0)] = m.group(1)
    for m in re.finditer(r"^(MEM_P_\w+)\s+equ\s+MEM_PG_(\w+)\s*<<\s*8\s*\|\s*(0x[0-9A-Fa-f]+)",
                         src, re.M):
        # The purge LEVEL is written in hex (MEM_PG_HIGH equ 0xFE), so the
        # value has to be parsed base-agnostically - reading it as decimal
        # matches the leading `0` and files every purgeable claim under 0x00.
        lvl = re.search(r"^MEM_PG_%s\s+equ\s+(0x[0-9A-Fa-f]+|\d+)"
                        % m.group(2), src, re.M)
        if lvl:
            out[(int(lvl.group(1), 0) << 8) | int(m.group(3), 0)] = m.group(1)
    if not out:
        raise Stale("no MEM_K_* claim tags in kernel/memory.inc",
                    "kernel/memory.inc",
                    "the page names heap claims by their tag; find the new "
                    "spelling")
    return out


def regions(stage_id, lad, cons, vol, ram_kb, heap, loaded_sectors, spl_first):
    """The memory map AFTER this stage - a list of spans over 640KB.

    Everything here is an address the tree computes for itself: the ladder
    from tools/kernsize.py, the blob from BOOT2_SECS, the relocation from
    int 12h and RELOC_ADJ. The one thing that is not is the heap, which is
    READ OUT OF THE RUNNING MACHINE at each stop - so the arena and its claims
    are what the kernel actually had, not what it ought to have had.
    """
    top = ram_kb * 1024
    ovl_at = grab("kernel/kernel.asm",
                  r"^OVL_AT\s+equ\s+(\d+)\s*;.*shipped split",
                  "OVL_AT - where `.ovl` sits inside the blob",
                  "kernel/kernel.asm; the shipped arm is the one with "
                  "\"the shipped split\" on it, the other being SPLSTARS=1's")
    order = [st["id"] for st in STAGES]
    at = order.index(stage_id)

    def since(i):
        return at >= order.index(i)

    R = []

    # THE FLOOR IS READ, NOT ASSUMED. SPEC.md 39.22 gives the heap the
    # `.vgabuf` rung back on a machine with no VGA - this 5150 is a CGA - so
    # the kernel's last rung stops existing partway through the boot. Clipping
    # every ladder region at the live floor is what shows that happening
    # instead of drawing a decoder buffer the machine gave away.
    floor = heap["base"] * 16 if (heap and heap.get("base")) else None

    # The magnified strip writes INSIDE a block, and a block there can be
    # sixty pixels wide - so every region carries a short form as well. A
    # label that does not fit is dropped rather than clipped (a clipped one
    # reads as a different, shorter name), which is why the long one alone is
    # not enough.
    SHORT = {"ivt": "IVT", "bda": "BDA", "dpt": "DPT", "vbr": "boot sector",
             "vbrtop": "boot sector", "vbrstk": "stage 1 stack",
             "ktext": ".text + .bss", "kcold": ".cold", "ovlw": ".ovlw",
             "ovl": ".ovl", "fatwin": "FAT", "fatw": "FAT snapshot",
             "lowbss": ".lowbss", "vgabuf": ".vgabuf", "blob": "stage 2",
             "pending": "not landed yet", "unclaimed": "free"}

    def add(a, b, rid, label, cls, note="", layer=0, sl=None):
        if floor is not None and rid not in ("heap", "claim", "free"):
            if not rid.startswith(("free", "claim")):
                b = min(b, floor)
        if b > a:
            R.append({"a": a, "b": b, "id": rid, "label": label,
                      "sl": sl or SHORT.get(rid)
                      or ("free" if rid.startswith("free") else label),
                      "cls": cls, "note": note, "layer": layer})

    add(0, 0x400, "ivt", "Interrupt vectors", "bios",
        "1,024 bytes: 256 far pointers. int 1Eh is one of them, and stage 1 "
        "repoints it.")
    add(0x400, 0x500, "bda", "BIOS data area", "bios",
        "The tick at 0040:006C is SPEC.md 15.4's t=0, read by the boot sector "
        "before it does anything expensive.")
    if since("dpt"):
        add(cons["DPT_AT"], cons["DPT_AT"] + 11, "dpt",
            "Diskette parameter table", "ours",
            "Eleven bytes copied out of the ROM's own table with byte 4 - EOT "
            "- patched to this disk's %d sectors per track. The IBM PC and XT "
            "ROMs say 8." % vol["spt"])
    # The BIOS's copy survives only until the load reaches it - which is a
    # thing to WATCH rather than assert, so it is computed from how many
    # sectors have actually landed.
    kload_end = lad["kseg"] * 16 + loaded_sectors * vol["bps"]
    if not (since("splash") and kload_end > 0x7C00):
        add(0x7C00, 0x7E00, "vbr", "Boot sector (where the BIOS put it)",
            "dead" if since("reloc") else "ours",
            "The BIOS reads exactly one sector here and jumps to it. From the "
            "relocation onward these bytes are only waiting to be overwritten "
            "- the kernel's own image runs straight through this address.")

    # ...and stage 1's sector and stack are live until kmain takes SS away,
    # then simply part of the arena. They are DROPPED rather than drawn dead
    # once the heap exists, because a claim can land on them.
    if since("reloc") and not since("heap"):
        seg = ram_kb * 64 - cons["RELOC_ADJ"]
        base = seg * 16 + 0x7C00
        add(base, base + cons["BOOT_SECT"], "vbrtop",
            "Boot sector (relocated)", "dead" if since("kmain") else "ours",
            "The same 512 bytes at the machine's LAST address, copied with "
            "`rep movsw` at the SAME OFFSET - so every org 0x7C00 label still "
            "resolves and only the segment register changes.")
        add(base - cons["BOOT_STACK"], base, "vbrstk",
            "Stage 1 stack", "dead" if since("kmain") else "ours",
            "%d bytes under the sector's own body. kmain gives it up the "
            "moment SS becomes LOW_SEG." % cons["BOOT_STACK"])

    # --- the kernel image, as much of it as has arrived ----------------------
    kstart = lad["kseg"] * 16
    if since("splash"):
        img_end = min(kstart + loaded_sectors * vol["bps"], lad["kend"] * 16)
        parts = [
            (kstart, lad["cold_seg"] * 16, "ktext", ".text + .bss",
             "kern", "%s bytes of code and %s of scratch, in ONE 64KB window "
             "because every kernel offset is 16 bits."
             % ("{:,}".format(lad["text"]), "{:,}".format(lad["bss"]))),
            (lad["cold_seg"] * 16, lad["fat_seg"] * 16, "kcold", ".cold",
             "kern", "%s bytes of code with a CS of its own - resident, but "
             "reached far, so it costs the kernel's own segment nothing."
             % "{:,}".format(lad["cold"])),
        ]
        if since("drvboot"):
            parts.append((lad["fat_seg"] * 16, lad["low_seg"] * 16, "fatw",
                          "FAT snapshot", "data",
                          "The mounted volume's FAT, read here at drv_boot. "
                          "These are the bytes .ovlw was in."))
        else:
            parts.append((lad["fat_seg"] * 16, lad["low_seg"] * 16, "fatwin",
                          "FAT window (empty until the mount)", "free",
                          "%s bytes reserved for a mounted volume's FAT. "
                          "Nothing has mounted anything yet, so what is "
                          "actually in it is the boot overlay."
                          % "{:,}".format((lad["low_seg"] - lad["fat_seg"]) * 16)))
        parts.append((lad["low_seg"] * 16, lad["vgabuf_seg"] * 16, "lowbss",
                      ".lowbss - task stacks, disk buffers", "kern",
                      "Reached through SS, not DS. The mount-owned buffers sit "
                      "at the BOTTOM of it so the boot overlay's window can "
                      "run on into them (SPEC.md 2.1.2)."))
        parts.append((lad["vgabuf_seg"] * 16, lad["kend"] * 16, "vgabuf",
                      ".vgabuf - planar decoder", "kern",
                      "%s bytes the VGA blit decoder writes rows into."
                      % "{:,}".format(lad["vgabuf"])))
        for a, b, rid, lab, cls, note in parts:
            if a >= img_end and not since("kernel"):
                continue
            add(a, min(b, img_end) if not since("kernel") else b,
                rid, lab, cls, note)
        # ...AND THE OVERLAY, ON A LAYER OF ITS OWN. `.ovlw` is 5,215 bytes
        # against the FAT window's 4,608, so it does not fit the block it is
        # drawn over: it runs on into the bottom of `.lowbss`, where SPEC.md
        # 2.1.2 deliberately put the three MOUNT-OWNED buffers so that it
        # could. Drawing it as a raised band that spans both is the only
        # honest picture - it is not a region of the map, it is code lying
        # ACROSS two of them until the mount takes the ground back.
        if not since("drvboot") and lad["ovlw"]:
            ov_a = lad["fat_seg"] * 16
            ov_b = ov_a + lad["ovlw"]
            if since("kernel") or img_end > ov_a:
                add(ov_a, min(ov_b, img_end) if not since("kernel") else ov_b,
                    "ovlw", ".ovlw - the boot overlay, running", "ovl",
                    "%s bytes of code that ride the kernel's own contiguous "
                    "read onto FAT_SEG and are FORFEIT at the first mount "
                    "(SPEC.md 2.5.3). It is LONGER than the FAT window, so it "
                    "lies across the mount-owned buffers at the bottom of "
                    ".lowbss as well - which is why those three were moved "
                    "there (SPEC.md 2.1.2). Most of kmain's init runs from "
                    "here, and drv_boot is the one call that does NOT, "
                    "because it is the call that overwrites it."
                    % "{:,}".format(lad["ovlw"]), layer=1)
        # `.ovl`, the other half, is a band inside the blob for the same
        # reason: it is a passenger, not a region.
        if since("blob") and not since("unblob") and lad["ovl"]:
            ova = lad["kend"] * 16 + ovl_at
            add(ova, ova + lad["ovl"], "ovl",
                ".ovl - boot overlay, in the blob", "ovl",
                "%s bytes at offset %d of the loader's %d, and the half that "
                "has to OUTLIVE the mount: drv_boot and the two splash "
                "captions live here. It goes back to the heap with the rest "
                "of the blob at spl_finish."
                % ("{:,}".format(lad["ovl"]), ovl_at,
                   cons["BOOT2_SECS"] * vol["bps"]), layer=1)
        if not since("kernel") and img_end < lad["kend"] * 16:
            add(img_end, lad["kend"] * 16, "pending",
                "still on the floppy", "free",
                "%d of %d sectors have landed. The bar's numerator is this "
                "number." % (loaded_sectors, vol["kernel"]["sectors"]))

    # --- stage 2's blob, on the heap's floor ---------------------------------
    blob_a = lad["kend"] * 16
    blob_b = blob_a + cons["BOOT2_SECS"] * vol["bps"]
    if since("blob") and not since("unblob"):
        add(blob_a, blob_b, "blob",
            "Stage 2: loader + loading screen + .ovl", "ovl",
            "%d sectors read straight to the heap's FLOOR, so the bytes "
            "rejoin the arena when kmain gives them back rather than "
            "stranding everything above them (SPEC.md 2.9.5)."
            % cons["BOOT2_SECS"])

    # --- the heap, as the machine reported it --------------------------------
    if since("heap") and heap and heap.get("base") and heap.get("top"):
        base, htop = heap["base"] * 16, heap["top"] * 16
        tags = owner_tags()
        # The free space is the arena MINUS the claims, emitted as the runs
        # between them - so the map shows fragmentation rather than drawing a
        # single "free" band with claims sitting on top of it.
        cl = sorted(((c["seg"] * 16, (c["seg"] + c["para"]) * 16, c)
                     for c in heap["claims"] if c["seg"] * 16 >= base),
                    key=lambda x: x[0])
        at = base
        for ca, cb, c in cl:
            add(at, min(ca, htop), "free%06x" % at, "arena - free", "free",
                "Unclaimed. [mem_base] is %04X and [mem_top] %04X, both read "
                "live out of the running kernel." % (heap["base"], heap["top"]))
            add(ca, cb, "claim%04x" % c["seg"],
                tags.get(c["own"], "heap claim"), "claim",
                "%s bytes at %04X:0000, owner %s - read out of `mem_tab` at "
                "this exact moment, not inferred."
                % ("{:,}".format(cb - ca), c["seg"],
                   tags.get(c["own"], "%04X" % c["own"])))
            at = max(at, cb)
        add(at, htop, "free%06x" % at, "arena - free", "free",
            "%s bytes unclaimed at the top of the arena."
            % "{:,}".format(max(0, htop - at)))
    else:
        # Before mem_init there is no arena, only what nobody has taken. It
        # stops UNDER stage 1's stack, which is real memory in use.
        lo = blob_b if since("blob") else 0x7E00
        hi = (ram_kb * 64 - cons["RELOC_ADJ"]) * 16 + 0x7C00 - cons["BOOT_STACK"] \
            if since("reloc") else top
        add(lo, hi, "unclaimed", "not spoken for", "free",
            "Nothing has asked for any of this yet - mem_init has not run, so "
            "there is no arena, only memory nobody is using.")

    R.sort(key=lambda r: (r["a"], r["b"]))
    return R


# -----------------------------------------------------------------------------
# 4. The PAGE's words.
# -----------------------------------------------------------------------------

def strings():
    """The loading screen's own text, out of the kernel that draws it.

    Scraped rather than typed, so the mimic at the top right of the page says
    what the machine says. If one of these is renamed the page refuses instead
    of quietly showing last year's caption.
    """
    def s(path, label, what):
        src = open(os.path.join(ROOT, path), errors="replace").read()
        # The colon is optional: splash.inc writes `spl_s_welcome db '..'`
        # and vidsel.inc writes `spl_s_mouse: db '..'`, and both are labels.
        m = re.search(r"^%s:?\s+db\s+'([^']*)'" % re.escape(label), src, re.M)
        if not m:
            raise Stale("the loading screen's %s (`%s`) is gone"
                        % (what, label), path,
                        "the page draws a mimic of the real bar; find the "
                        "string's new name")
        return m.group(1)
    return {
        "welcome": s("kernel/splash.inc", "spl_s_welcome", "caption"),
        "kern": s("kernel/splash.inc", "spl_s_kern", "load message"),
        "mouse": s("kernel/vidsel.inc", "spl_s_mouse", "mouse message"),
        "fdd": s("kernel/vidsel.inc", "spl_s_fdd", "drives message"),
        "boot": s("kernel/vidsel.inc", "spl_s_boot", "hand-over message"),
    }


# What each measured phase is DOING. Keyed by the phase's own name, so a note
# cannot outlive the thing it describes: a phase that goes takes its note with
# it, and one that arrives shows up in check_coverage() before it ever renders.
NOTES = {
    "post": "The machine's own ROM: the self test, the interrupt table, the "
            "equipment word, and then INT 19h - which reads ONE sector from "
            "the first drive to 0000:7C00, checks it ends AA55, and jumps to "
            "it. Everything on this row is the ROM's; os8088 has not executed "
            "an instruction yet. The mechanical figure beside it is the "
            "drive's - a full-stroke recalibrate and one sector.",
    "relocate": "cli, then the BIOS tick at 0040:006C into BP as SPEC.md "
                "15.4's t=0 - read here because everything expensive is below "
                "it. Then INT 12h for the memory size, the refusal for a "
                "machine too small (SPEC.md 2.7.1), and `rep movsw` of 256 "
                "words to the top of RAM. THE COPY KEEPS THE SAME OFFSET, so "
                "every `org 0x7C00` label still resolves and only the segment "
                "register changes; a computed far return lands in the copy.",
    "stage 1: sector code": "The sector's own arithmetic between disk calls: "
                            "the DL range check (SPEC.md 2.9.11 - a Packard "
                            "Bell 286 hands over 0x61, which is not a drive), "
                            "the diskette parameter table copy, the data "
                            "area's LBA out of the four BPB fields, the run "
                            "bounds - and, at the end, SPEC.md 2.9.7's word "
                            "sum over everything it just read.",
    "int 13h reset": "AH=00: recalibrate the drive before trusting it. Cheap, "
                     "and the one call here that moves no data.",
    "int 13h read": "AH=02, a multi-sector read. COST A DISK CALL IN CALLS, "
                    "NOT SECTORS: the head is where the head is, and one call "
                    "that moves eighteen sectors costs about what one moving "
                    "six does. CF=0 is the BIOS saying the whole request "
                    "completed - and AL is NOT (SPEC.md 18.91): trusting AL "
                    "took a 16KB read from 8.29s to 2.09 when it was fixed.",
    "stage 2: loader code": "Stage 2's own code between calls: the text mode "
                            "set, the parameter table again, and the run "
                            "bound - which `push sp` widens from the TRACK to "
                            "the CYLINDER on an 8086 or 8088 (SPEC.md "
                            "18.93.2), because the FDC's multi-track bit "
                            "carries a read onto the other head at EOT. That "
                            "one test halves the number of disk calls.",
    "stage 2: loop": "The last of the load, plus the hand-over: t=0 into "
                     "0060:000C, the blob's own segment into [spl_fseg] so "
                     "the kernel can still reach the loading screen, SPEC.md "
                     "18.93.1's canary, and int 08h given back before the "
                     "far jump into kmain.",
    "splash tick": "One notch of the loading bar. The FIRST one is the "
                   "expensive one - it sets the video mode, draws the dialog, "
                   "the trough and the caption; the rest redraw a few pixels "
                   "of fill and four digits. Both are BLITTED: a mode 12h "
                   "BIOS teletype character costs 40 ms on this machine, and "
                   "not calling it took a floppy boot from 21,959 ms to "
                   "16,084 (SPEC.md 15.3.2).",
    "dsk_boot_from_x": "Which volume did we come off (SPEC.md 52.10.3)? On a "
                       "floppy this stores one byte.",
    "cpu_detect": "The CPU tier (SPEC.md 41). BEFORE sched_init, because this "
                  "is the last moment at which no kernel ISR is installed.",
    "xm_sniff": "One INT 15h AH=88h: is there memory above 1MB? Exact rather "
                "than heuristic, and it needs no A20 gate to ask.",
    "dsk_dpt_init_x": "INT 1Eh becomes the kernel's, at the same address and "
                      "for the same reason as stage 1's copy - idempotent now "
                      "rather than necessary.",
    "sched_init": "Pre-emption is live from here: int 08h is hooked and the "
                  "task table cleared.",
    "sch_idle_start": "The idle task (SPEC.md 8.1.1). Inert until ui_task "
                      "starts sleeping - which is what makes a finished "
                      "desktop 96.9% HALTED instead of spinning.",
    "evq_init": "The event queue: one ring of 128 bytes in .lowbss, which "
                "every mouse and key event will pass through for the rest of "
                "the session.",
    "clk_init": "Probe the RTC, or fall back to the fixed date - before the "
                "mode set, so the first menu bar already carries a clock.",
    "vid_init": "Probe the adapter and publish the live geometry (SPEC.md "
                "39). This re-runs what the splash already did EXCEPT the "
                "mode set: the loading screen stays up and keeps ticking.",
    "vid_ctx_init": "Bank that geometry as display 0's (SPEC.md 39.12).",
    "vid_probe_avail": "Which OTHER adapters this machine has - AFTER the "
                       "mode set, which is the whole correctness argument: a "
                       "VGA in mode 12h decodes A000 only, so B000 and B800 "
                       "are free for a second card to answer at.",
    "vid_disp_init": "If the machine has both mono cards, programme the "
                     "second one too (SPEC.md 39.13).",
    "mem_init_x": "INT 12h, and the empty claim map. [mem_base] is raised "
                  "OVER the blob for the duration, which is why stage 2 was "
                  "read to the heap's FLOOR: the bytes rejoin the long run "
                  "when they are given back, rather than stranding every "
                  "claim above them (SPEC.md 50.6.3).",
    "mod_init_x": "Point every on-demand module slot at mod_gone. `-f bin` "
                  "zeroes no .bss, so until this runs those slots hold "
                  "whatever was in memory - and they are far-call targets.",
    "font_init": "The typeface (SPEC.md 6.2) into font_glyphs, in .lowbss.",
    "ovl_font_init": "The typeface this BUILD carries, out of the overlay - "
                     "so it needs no INT 10h and the machine's own ROM font "
                     "is never consulted.",
    "wm_init": "The window manager's state: no windows, one clip region.",
    "band_init": "The 1bpp band composer's 2KB claim (SPEC.md 5.9.2). A "
                 "refusal is survivable - the fifteen-call title bar is what "
                 "runs then.",
    "menu_init": "The menu bar owner, so the first wm_paint_all already has "
                 "a bar to draw.",
    "inst_init": "The instance table: no app instances exist until launched.",
    "splf_step": "A notch of the bar spent by hand, at a point where kmain "
                 "knows something finished. There are three, and the bar's "
                 "denominator has SPL_POST reserved for them.",
    "ovl_spl_msg_mouse": "Write the caption for the wait that is about to "
                         "happen. Composed AFTER the notch that precedes it: "
                         "spl_mdraw refuses while the screen is not the "
                         "splash's, so a line composed before it is composed, "
                         "never drawn (SPEC.md 15.6.4).",
    "mouse_init": "SPEC.md 9.4.1's identify window. The serial reset holds "
                  "DTR/RTS low, then the port is listened to for a mouse's "
                  "'M'. THE LONGEST PHASE OF THE BOOT THAT IS NOT THE DISK - "
                  "585-619 ms with a mouse on the other end and about 1,190 "
                  "without, and it charges the bar a notch a TICK rather than "
                  "sitting still (SPEC.md 15.3.3).",
    "ovl_spl_msg_fdd": "...and the caption for the second stall: SPEC.md "
                       "18.97's TRACK 0 question about unit 1.",
    "desk_init": "Volume zones for the desktop (SPEC.md 26.1) - which asks "
                 "each floppy unit whether it is there. On a machine whose "
                 "second drive is absent this is the longest single wait in "
                 "the whole boot; here it is one drive answering quickly.",
    "dock_init": "The dock strip's scratch (SPEC.md 30).",
    "files_init_x": "The Disk module's state. No window is open at boot.",
    "loader_init_x": "The package loader's state.",
    "drv_init_x": "The driver table (SPEC.md 51) - BEFORE snd_init, whose "
                  "tone route reads the published service table on its first "
                  "tick.",
    "drv_snd_sniff": "Is there an FM chip at 388h? If so row 0 becomes WANTED "
                     "by default - which a SYSTEM.CFG that says otherwise "
                     "then overwrites.",
    "snd_init": "The sound layer publishes snd_live last; snd_tick has been "
                "running gated since sched_init hooked int 08h.",
    "drv_boot_x": "MOUNT A:, READ SYSTEM.CFG, AND LOAD WHAT IT ASKS FOR "
                  "(SPEC.md 51.3). The mount is what takes the FAT window and "
                  "the buffers above it - so this is the call that overwrites "
                  ".ovlw, the boot overlay half that has been running kmain's "
                  "init for the last dozen phases. That is exactly why THIS "
                  "body lives in the blob and not in that window: a routine "
                  "cannot be the one that overwrites itself.",
    "xm_boot_x": "The store above 1MB, if xm_sniff found any - an OVERLAY "
                 "rather than a driver, so no table row and nothing to decide.",
    "thm_set": "Resolve the palette from the theme kind, once, before "
               "anything is drawn.",
    "spl_finish": "The bar to 100% and the screen handed back. The paint "
                  "below covers every pixel of it, so the loading screen "
                  "needs no erase.",
    "mem_unblob_x": "...AND STAGE 2 GOES BACK TO THE HEAP. There is nothing "
                    "to free: the loader is at the arena's floor, so putting "
                    "[mem_base] back on that floor and compacting turns the "
                    "release into part of the long run instead of a hole.",
    "gfx_lock": "Take the drawing lock: one frame, not a race with a tick.",
    "wm_paint_all": "THE FIRST DESKTOP FRAME - the pattern, the menu bar, the "
                    "volume icons, the dock. Nothing repaints more of the "
                    "screen than it changed after this; a full repaint is a "
                    "regression against a documented number, not a neutral "
                    "refactor.",
    "gfx_unlock": "The frame is on the glass, and SPEC.md 15.4's boot timer "
                  "stops HERE - not after the cursor. The question is when "
                  "the first desktop FRAME is finished, and the cursor is not "
                  "the desktop.",
    "cursor_show": "The arrow, drawn by the mouse ISR from here on.",
    "drv_notice_x": "...and only NOW say what did not load: a window needs a "
                    "screen that has been painted.",
}


# Where a phase's CODE lives, and therefore which block of the memory map to
# light up when its step is selected. The section comes out of nasm's own map
# (tools/os88sym.py), so this is the tree's answer rather than the page's -
# which is the whole point of showing it: most of kmain's init runs from
# `.ovlw`, a block that is about to become a FAT snapshot, and nothing in the
# source of any one routine says so.
SECTION_REGION = {
    ".text": "ktext", ".bss": "ktext", ".cold": "kcold",
    ".ovlw": "ovlw", ".ovl": "blob", ".boot2": "blob",
    ".lowbss": "lowbss", ".vgabuf": "vgabuf",
}


def region_at(regs, seg):
    """Which drawn region a segment falls in - for a read's DESTINATION."""
    a = seg * 16
    for r in regs:
        if r["a"] <= a < r["b"]:
            return r["id"]
    return None


def build_page(walkdata, lad, cons, vol, defines, strs, notes=NOTES):
    """Everything the page needs, as one JSON-able object."""
    import os88sym
    sect = os88sym.sections(defines)
    stages = assign(walkdata["events"], defines)
    ram = walkdata["ram_kb"] * 1024
    ksecs = vol["kernel"]["sectors"] - cons["BOOT2_SECS"]

    # The bar's message, per stage. Every string is scraped, and the point at
    # which each is written is a call in kmain that the stage OWNS - so this
    # says which stage, not which line, and cannot drift into a lie about
    # wording.
    MSG = {"splash": "kern", "kernel": "kern", "kmain": "kern", "heap": "kern",
           "ui": "kern", "mouse": "mouse", "desk": "fdd", "drvboot": "boot",
           "unblob": "boot"}

    heap, loaded, out, t0 = None, 0, [], 0.0
    for st in stages:
        ev = st["events"]
        # --- how much of the kernel has landed, and what the bar reads ------
        for e in ev:
            if "arg_done" in e:
                loaded = e["arg_done"]
            if e.get("heap", {}).get("base"):
                heap = e["heap"]
        if st["id"] not in ("post", "reloc", "dpt", "blob", "splash"):
            loaded = ksecs
        bar = None
        for e in ev:
            if "bar" in e and e["bar"]["total"]:
                bar = dict(e["bar"])
            elif "arg_done" in e:
                bar = {"done": e["arg_done"],
                       "total": e["arg_total"] + cons["SPL_POST"]}
        if st["id"] in ("post", "reloc", "dpt", "blob"):
            bar = None                          # the splash is not up yet
        if st["id"] == "paint":
            bar = None                          # ...and it has been handed back
        regs = regions(st["id"], lad, cons, vol, walkdata["ram_kb"], heap,
                       loaded, None)

        steps = []
        for e in ev:
            base = basename(e["name"])
            mem = []
            s = sect.get(base)
            if s in SECTION_REGION:
                rid = SECTION_REGION[s]
                # `.ovlw` is gone once the mount has been through it.
                if rid == "ovlw" and not any(r["id"] == "ovlw" for r in regs):
                    rid = "fatw"
                mem.append(rid)
            elif e["kind"] == "rom":
                mem.append("vbr")
            elif st["id"] in ("reloc", "dpt"):
                mem.append("vbrtop" if any(r["id"] == "vbrtop" for r in regs)
                           else "vbr")
                if st["id"] == "dpt":
                    mem.append("dpt")
            elif base.startswith("stage 1"):
                mem.append("vbrtop")
            elif base.startswith("stage 2") or base == "splash tick":
                mem.append("blob")
            if e["kind"] == "disk":
                mem.append("vbrtop" if st["id"] == "blob" else "blob")
                if e.get("dest"):
                    d = region_at(regs, e["dest"])
                    if d:
                        mem.append(d)
            label = base
            if e.get("fn") == 2:
                label = "int 13h: read %d sector%s to %04X:0000" % (
                    e["want"], "" if e["want"] == 1 else "s", e["dest"])
            elif e.get("fn") == 0:
                label = "int 13h: reset drive %d" % e.get("drive", 0)
            elif "arg_done" in e:
                label = "splash tick - %d of %d sectors" % (e["arg_done"],
                                                            e["arg_total"])
            note = notes.get(base, "")
            if base == "int 13h read" and e["want"] == 1:
                note += (" This one is ONE sector because the destination was "
                         "about to cross a 64KB DMA page, which the controller "
                         "answers with error 09h - the third of read_run's "
                         "three bounds.")
            steps.append({
                "label": label, "phase": base, "kind": e["kind"],
                "ms": e["ms"], "t0": e["t0"], "note": note,
                "sect": s or "", "mem": sorted(set(x for x in mem if x)),
                "sectors": e["read_sectors"], "reads": e["reads"],
                "cyl": e["seek_cylinders"],
                "mech": e["transfer_ms"] + e["seek_ms"],
            })

        ms = sum(e["ms"] for e in ev)
        out.append({
            "id": st["id"], "short": st.get("short", st["id"]),
            "title": st["title"], "moved": st["moved"],
            "ms": ms, "t0": t0, "regions": regs, "steps": steps,
            "bar": None if bar is None else {
                "done": bar["done"], "total": bar["total"],
                "pct": 100.0 * bar["done"] / max(1, bar["total"]),
                "msg": strs[MSG.get(st["id"], "kern")]},
        })
        t0 += ms

    return {
        "meta": {
            "machine": walkdata["machine"],
            "field": walkdata["machine"] == FIELD_MACHINE,
            "image": walkdata["image"], "ram_kb": walkdata["ram_kb"],
            "taken": walkdata["taken"], "total_ms": walkdata["total_ms"],
            "boot_ticks": walkdata["boot_ticks"],
            "boot_ticks_ms": walkdata["boot_ticks_ms"],
            "longest_run": walkdata["longest_run"],
            "kernel_md5": hashlib.md5(
                open(os.path.join(ROOT, "build", "kernel.bin"), "rb").read()
            ).hexdigest() if os.path.exists(
                os.path.join(ROOT, "build", "kernel.bin")) else "",
            "image_md5": vol["md5"],
            "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                     cwd=ROOT, capture_output=True,
                                     text=True).stdout.strip(),
            "defines": list(defines),
        },
        # THE WALK RIDES IN THE MODEL. Re-rendering is seconds and re-booting
        # is minutes, so the expensive half has to be something you can keep -
        # and one file that `--measure` will take back is a better answer than
        # two that have to be kept in step.
        "walk": walkdata,
        "ram": ram,
        # The magnified strip's span: the top of the loader's blob, rounded up
        # to a whole 4KB so the frame is a round number and does not move when
        # the kernel changes size by a rung.
        "zoom": ((lad["kend"] * 16 + cons["BOOT2_SECS"] * vol["bps"]
                  + 4095) // 4096) * 4096,
        "cons": cons, "vol": vol, "strings": strs,
        "ladder": {k: lad[k] for k in
                   ("kseg", "cold_seg", "fat_seg", "low_seg", "vgabuf_seg",
                    "kend", "text", "bss", "cold", "lowbss", "vgabuf", "ovlw",
                    "ovl", "boot2", "ksize", "minramkb")},
        "ksecs": ksecs,
        "stages": out,
    }


# -----------------------------------------------------------------------------
# 5. The PAGE. One stylesheet, one script, and the whole model as
#    JSON - so the file WORKS with no network at all, which a page about a
#    machine that boots from a floppy ought to manage. The single exception
#    is the webfont link, and every rule that uses it names a real fallback:
#    offline, the page renders correctly in the system's own faces.
# -----------------------------------------------------------------------------

CSS = r''':root{
  --bg:#e9ecef; --panel:#fbfcfd; --ink:#12161a; --dim:#5d656e; --rule:#c8cfd6;
  --rule2:#e0e5ea; --accent:#15497f; --sel:#b8560a;
  --c-bios:#8b939c; --c-ours:#15497f; --c-kern:#1f7a58; --c-ovl:#b8560a;
  --c-data:#6a37bd; --c-claim:#0c6f86; --c-free:#dde2e7; --c-dead:#bcc4cc;
  --on-free:#5d656e;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0f1216; --panel:#181c21; --ink:#e4e9ee; --dim:#8a929c; --rule:#2b313a;
  --rule2:#20252b; --accent:#79aef2; --sel:#f2a552;
  --c-bios:#767e88; --c-ours:#5a9bef; --c-kern:#42bf95; --c-ovl:#f2a552;
  --c-data:#ab8cf7; --c-claim:#2fbdd4; --c-free:#232830; --c-dead:#3c434c;
  --on-free:#8a929c;
}}
:root[data-theme="dark"]{
  --bg:#0f1216; --panel:#181c21; --ink:#e4e9ee; --dim:#8a929c; --rule:#2b313a;
  --rule2:#20252b; --accent:#79aef2; --sel:#f2a552;
  --c-bios:#767e88; --c-ours:#5a9bef; --c-kern:#42bf95; --c-ovl:#f2a552;
  --c-data:#ab8cf7; --c-claim:#2fbdd4; --c-free:#232830; --c-dead:#3c434c;
  --on-free:#8a929c;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.55 "IBM Plex Sans",ui-sans-serif,-apple-system,"Segoe UI",Roboto,
       Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
.mono,code{font-family:"IBM Plex Mono",ui-monospace,"SF Mono",Menlo,Consolas,
  "DejaVu Sans Mono",monospace}
.wrap{max-width:1400px;margin:0 auto;padding:20px 22px 60px}

/* ---- header ---------------------------------------------------------- */
.top{display:flex;gap:24px;align-items:flex-start;justify-content:space-between;
  flex-wrap:wrap;border-bottom:1px solid var(--rule);padding-bottom:16px}
h1{font-family:"IBM Plex Sans Condensed","IBM Plex Sans",ui-sans-serif,
     Helvetica,Arial,sans-serif;
  font-size:29px;margin:0 0 5px;letter-spacing:-.005em;font-weight:700;
  text-wrap:balance}
h1 .sub{color:var(--dim);font-weight:400}
.lede{margin:6px 0 0;max-width:60ch;color:var(--dim);font-size:13px}
.stamp{margin-top:10px;font-size:11.5px;color:var(--dim);display:flex;
  flex-wrap:wrap;gap:4px 14px}
.stamp b{font-weight:600;color:var(--ink)}

/* ---- the loading-screen mimic ---------------------------------------- */
.splash{width:300px;height:196px;flex:0 0 auto;background:#000;color:#fff;
  padding:10px 12px;border:1px solid var(--rule);border-radius:2px;position:relative;
  display:flex;flex-direction:column;justify-content:center}
.splash .logo{text-align:center;font-weight:800;letter-spacing:.22em;font-size:16px;
  padding:0 0 9px;perspective:420px}
.splash .logo span{display:inline-block;animation:flip8088 3.52s steps(16,end) infinite}
@keyframes flip8088{to{transform:rotateY(360deg)}}
.splash .dlg{border:1px solid #fff;padding:7px}
.splash .dlg2{border:1px solid #fff;padding:11px 10px 9px;text-align:center}
.splash .cap{font-size:12px;letter-spacing:.04em;margin-bottom:9px;
  font-family:"IBM Plex Sans",ui-sans-serif,Helvetica,sans-serif}
.splash .trough{border:1px solid #fff;height:14px;padding:1px}
.splash .fill{height:100%;background:#fff;width:0;transition:width .5s cubic-bezier(.4,0,.2,1)}
.splash .pct{font-size:12px;margin-top:7px}
.splash .msg{font-size:11.5px;margin-top:9px;color:#fff;min-height:1.3em;opacity:.92}
.splash.off{color:#3a3a3a}
.splash.off .dlg,.splash.off .dlg2{border-color:#000}
.splash.off .logo,.splash.off .cap,.splash.off .trough,.splash.off .pct{visibility:hidden}
.splash.off .dlg{border:none;padding:0}
.splash.off .msg{visibility:visible;color:#54514a;text-align:center;padding:0 10px;
  font-style:italic}
.splash .note{font-size:10.5px;color:var(--dim);margin-top:8px;text-align:center}
.splash-outer{flex:0 0 auto}
.splash-outer .cabin{font-size:11px;color:var(--dim);margin-top:6px;text-align:center;
  max-width:300px;min-height:2.6em}

/* ---- stage strip ------------------------------------------------------ */
.stages{display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin:18px 0 6px}
.st{appearance:none;border:1px solid var(--rule);background:var(--panel);color:var(--dim);
  font:inherit;font-size:11.5px;padding:5px 9px;border-radius:2px;cursor:pointer;
  display:flex;gap:6px;align-items:baseline;transition:.13s}
.st:hover{border-color:var(--accent);color:var(--ink)}
.st .n{font-weight:700;font-variant-numeric:tabular-nums}
.st .ms{font-size:10.5px;opacity:.75;font-family:ui-monospace,monospace}
.st[aria-current="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
.st[aria-current="true"] .ms{opacity:.85}
.nav{display:inline-flex;gap:4px;margin-left:8px}
.nav button{appearance:none;border:1px solid var(--rule);background:var(--panel);
  color:var(--ink);width:32px;height:29px;border-radius:2px;cursor:pointer;font-size:14px;
  line-height:1}
.nav button:hover{border-color:var(--accent)}
.nav button:disabled{opacity:.35;cursor:default}
.stitle{font-family:"IBM Plex Sans Condensed","IBM Plex Sans",ui-sans-serif,
     Helvetica,Arial,sans-serif;
  margin:15px 0 2px;font-size:22px;font-weight:700;letter-spacing:-.005em;
  text-wrap:balance}
.smoved{color:var(--dim);font-size:13px;margin-bottom:2px}
.smoved b{color:var(--sel);font-weight:600}

/* ---- section frames --------------------------------------------------- */
.panel{background:var(--panel);border:1px solid var(--rule);border-radius:3px;
  padding:14px 16px 12px;margin-top:16px}
.ph{font-size:10.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--dim);
  font-weight:600;
  margin:0 0 2px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.ph .hint{text-transform:none;letter-spacing:0;font-size:11px}

/* ---- memory map ------------------------------------------------------- */
.mlab{position:relative;transition:height .35s}
.mlab .lb{position:absolute;font-size:10.5px;line-height:1.25;white-space:nowrap;
  padding:1px 4px;border:1px solid transparent;border-radius:2px;
  cursor:pointer;transition:left .45s cubic-bezier(.4,0,.2,1),top .3s,opacity .3s,
  background .13s,border-color .13s;background:var(--panel)}
.mlab .lb .sz{color:var(--dim);font-family:ui-monospace,monospace;font-size:9.5px}
.mlab .lb:hover{border-color:var(--rule)}
.mlab .lb.hot{border-color:var(--sel);background:var(--sel);color:#fff}
.mlab .lb.hot .sz{color:rgba(255,255,255,.82)}
.mlab .rz{position:absolute;width:1px;background:var(--rule);
  transition:left .45s cubic-bezier(.4,0,.2,1),top .3s,height .3s,opacity .3s}
.mlab .rz.hot{background:var(--sel);width:1.5px;z-index:2}
.mlab .jg{position:absolute;height:1px;background:var(--rule);
  transition:left .45s cubic-bezier(.4,0,.2,1),top .3s,width .3s,opacity .3s}
.mlab .jg.hot{background:var(--sel);height:1.5px;z-index:2}
.mlab .dt{position:absolute;width:5px;height:5px;border-radius:50%;
  background:var(--rule);transition:left .45s cubic-bezier(.4,0,.2,1),top .3s,opacity .3s}
.mlab .dt.hot{background:var(--sel);box-shadow:0 0 0 2px var(--panel);z-index:3}
.mbar{position:relative;height:38px;margin-top:2px;border:1px solid var(--rule);
  background:var(--c-free);border-radius:2px;overflow:hidden}
.mbar .rg{position:absolute;top:0;height:100%;
  transition:left .45s cubic-bezier(.4,0,.2,1),width .45s cubic-bezier(.4,0,.2,1),
  opacity .3s,background .25s;cursor:pointer}
.mbar .rg.dim{opacity:.24}
.movl{position:relative;height:15px;margin-top:-15px;pointer-events:none;z-index:3}
.movl .ov{position:absolute;height:15px;top:0;border:1.5px solid var(--c-ovl);
  background:repeating-linear-gradient(135deg,var(--c-ovl) 0 3px,transparent 3px 7px);
  border-radius:2px;pointer-events:auto;cursor:pointer;
  transition:left .45s cubic-bezier(.4,0,.2,1),width .45s cubic-bezier(.4,0,.2,1),opacity .3s}
.movl .ov.hot{box-shadow:0 0 0 2px var(--sel);background:var(--c-ovl)}
.mrule{position:relative;height:15px;margin-top:3px}
.mrule span{position:absolute;font-size:10px;color:var(--dim);transform:translateX(-50%);
  font-family:ui-monospace,monospace}
.mrule span.e0{transform:translateX(0)}
.mrule span.e1{transform:translateX(-100%)}

/* ---- timeline --------------------------------------------------------- */
.tbar{position:relative;height:30px;border:1px solid var(--rule);border-radius:2px;
  overflow:hidden;background:var(--c-free)}
.tbar .sg{position:absolute;top:0;height:100%;cursor:pointer;
  border-right:1px solid var(--panel);
  transition:left .4s cubic-bezier(.4,0,.2,1),width .4s cubic-bezier(.4,0,.2,1),
  opacity .25s,filter .13s}
.tbar .sg:hover{filter:brightness(1.18)}
.tbar .sg.sel{box-shadow:inset 0 0 0 2px var(--ink)}
.tlab{position:relative;transition:height .3s}
.tlab .rz{position:absolute;width:1px;background:var(--rule)}
.tlab .rz.sel{background:var(--ink);width:1.5px;z-index:2}
.tlab .jg{position:absolute;height:1px;background:var(--rule)}
.tlab .jg.sel{background:var(--ink);height:1.5px;z-index:2}
.tlab .dt{position:absolute;width:5px;height:5px;border-radius:50%;background:var(--rule)}
.tlab .dt.sel{background:var(--ink);box-shadow:0 0 0 2px var(--panel);z-index:3}
.tlab .lb{position:absolute;font-size:10.5px;white-space:nowrap;
  padding:1px 4px;cursor:pointer;border:1px solid transparent;border-radius:2px;
  background:var(--panel)}
.tlab .lb:hover{border-color:var(--rule)}
.tlab .lb.sel{border-color:var(--ink);font-weight:600}
.tlab .lb .ms{font-family:ui-monospace,monospace;color:var(--dim);font-size:9.5px}
.tlab .lb.sel .ms{color:var(--ink)}

/* ---- detail ----------------------------------------------------------- */
.detail{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(0,1fr);gap:22px}
@media(max-width:820px){.detail{grid-template-columns:1fr}}
.detail h3{margin:0 0 6px;font-size:15px;font-weight:620}
.detail p{margin:0 0 10px;font-size:13.5px;max-width:70ch}
.facts{border-top:1px solid var(--rule2);font-size:12px}
.facts div{display:flex;justify-content:space-between;gap:14px;padding:4px 0;
  border-bottom:1px solid var(--rule2)}
.facts .k{color:var(--dim)}
.facts .v{font-family:ui-monospace,monospace;text-align:right}
.tag{display:inline-block;font-size:10px;letter-spacing:.06em;text-transform:uppercase;
  padding:1px 6px;border-radius:2px;border:1px solid var(--rule);color:var(--dim);
  margin-right:6px;vertical-align:1px}
.tag.meas{border-color:var(--c-kern);color:var(--c-kern)}
.tag.deriv{border-color:var(--c-ovl);color:var(--c-ovl)}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:11px;color:var(--dim);margin-top:9px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;
  vertical-align:-1px}
.kbd{font-family:ui-monospace,monospace;font-size:10.5px;border:1px solid var(--rule);
  border-bottom-width:2px;border-radius:3px;padding:0 4px;color:var(--dim)}
footer{margin-top:28px;padding-top:14px;border-top:1px solid var(--rule);
  font-size:11.5px;color:var(--dim);max-width:88ch}
footer code{font-size:11px}

/* ---- magnified strip: the low region, where everything of ours is -------- */
.zoomhead{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;
  font-size:11px;color:var(--dim);margin:14px 0 3px;padding-top:11px;
  border-top:1px dashed var(--rule)}
.zoomhead b{color:var(--ink);font-weight:600}
.zbar{position:relative;height:34px;border:1px solid var(--rule);border-radius:2px;
  overflow:hidden;background:var(--c-free)}
.zbar .rg{position:absolute;top:0;height:100%;cursor:pointer;overflow:hidden;
  transition:left .45s cubic-bezier(.4,0,.2,1),width .45s cubic-bezier(.4,0,.2,1),
  opacity .3s,background .25s}
.zbar .rg.dim{opacity:.24}
.zbar .rg span{position:absolute;left:4px;top:50%;transform:translateY(-50%);
  font-size:10px;white-space:nowrap;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.45);
  pointer-events:none}
.zbar .rg.pale span{color:var(--on-free);text-shadow:none}
.zovl{position:relative;height:17px;margin-top:-9px;z-index:4;pointer-events:none}
.zovl .ov{position:absolute;height:17px;top:0;border:1.5px solid var(--c-ovl);
  border-radius:2px;pointer-events:auto;cursor:pointer;
  background:repeating-linear-gradient(135deg,var(--c-ovl) 0 4px,transparent 4px 9px);
  transition:left .45s cubic-bezier(.4,0,.2,1),width .45s cubic-bezier(.4,0,.2,1),opacity .3s}
.zovl .ov span{position:absolute;left:5px;top:50%;transform:translateY(-50%);font-size:9.5px;
  white-space:nowrap;color:var(--ink);font-weight:600;background:var(--panel);
  padding:0 3px;border-radius:2px}
.zovl .ov.hot{box-shadow:0 0 0 2px var(--sel)}
.zspan{position:absolute;top:0;height:100%;border-left:1px solid var(--sel);
  border-right:1px solid var(--sel);background:rgba(194,96,12,.10);pointer-events:none;z-index:2}

a:focus-visible,button:focus-visible,.st:focus-visible{outline:2px solid var(--accent);
  outline-offset:2px}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{transition-duration:.001ms!important;animation-duration:.001ms!important;
    animation-iteration-count:1!important}
}
'''

JS = r'''(function(){
"use strict";
var D = window.LADDER, S = D.stages;
var stage = 0, step = -1;          // step -1 = "the stage itself"
var CLS = {bios:"--c-bios", ours:"--c-ours", kern:"--c-kern", ovl:"--c-ovl",
           data:"--c-data", claim:"--c-claim", free:"--c-free", dead:"--c-dead"};
var KIND = {rom:"bios", disk:"ours", kernel:"kern", draw:"data"};
var $ = function(id){ return document.getElementById(id); };
function col(c){ return "var(" + (CLS[c] || "--c-free") + ")"; }
function bytes(n){
  if (n >= 1024*1024) return (n/1048576).toFixed(1) + " MB";
  if (n >= 1024) return (n/1024 >= 100 ? Math.round(n/1024) : (n/1024).toFixed(1)) + " KB";
  return n + " B";
}
function hex(n, w){ var s = n.toString(16).toUpperCase(); while (s.length < (w||5)) s = "0"+s; return s; }
function ms(v){
  if (v >= 1000) return (v/1000).toFixed(2) + " s";
  if (v >= 10) return v.toFixed(0) + " ms";
  if (v >= 1) return v.toFixed(1) + " ms";
  return v.toFixed(2) + " ms";
}

/* --------------------------------------------------------------------------
   Labels with risers. Two passes, because a label's width is not knowable
   until it is in the document: place them all on one row, measure, then drop
   each into the lowest row where it does not touch its neighbour. The riser
   is drawn from the bar's edge to whatever row the label landed on, which is
   what makes a narrow region legible without widening it and lying about it.
   -------------------------------------------------------------------------- */
function layout(host, items, W, up){
  var ROW = 18, PAD = 6, GAP = 9, FAN = 260;
  /* THE WHOLE CONSTRUCTION IS MIRRORED FOR LABELS BELOW THE BAR, and doing it
     by flipping x into W - x, running the identical packer and flipping back
     is what keeps this one piece of code with one argument behind it.

     Above the bar a label extends RIGHT of its anchor and the leftmost sits
     farthest away; below it a label extends LEFT and the leftmost sits
     NEAREST - which is both what the no-crossing argument needs and what
     reads correctly, step one's label being the one closest to the timeline.

     The argument itself, in three lines. A riser only passes rows between its
     own and the bar. Rows are ordered so those rows all belong to anchors on
     the side the labels grow AWAY from, so none of their labels can cover it.
     And every jog that has any length at all gets a row to itself, so no two
     horizontals share a y. Two labels share a row only when the second needs
     no jog and clears the first. */
  var flip = !up;
  var seq = items.map(function(it){
    return {it: it, u: flip ? (W - it.x) : it.x};
  }).sort(function(a, b){ return a.u - b.u; });

  var row = -1, cur = -1e9, prev = -1e9;
  seq.forEach(function(s){
    var w = s.it.el.getBoundingClientRect().width;
    /* Three floors, and the label takes the highest. `prev + GAP` (the
       previous ANCHOR) is the one the argument above rests on; clearing the
       previous LABEL as well is what fans a crowd out, and FAN stops that
       running off the end of a 640KB bar whose first eighth holds nine
       regions. */
    var u = Math.max(s.u, prev + GAP, Math.min(cur + GAP, s.u + FAN));
    if (u + w > W) u = Math.max(0, W - w);
    if (u < s.u) u = Math.min(s.u, Math.max(0, W - w));
    var jog = u > s.u + 0.5;
    if (row < 0 || jog || u < cur + GAP) row++;
    s.row = row; s.u0 = u; s.w = w;
    cur = u + w; prev = s.u;
  });

  var n = row + 1, H = PAD + n * ROW + 4;
  seq.forEach(function(s){
    var it = s.it;
    var top = PAD + (up ? s.row : (n - 1 - s.row)) * ROW;
    it.el.style.left = (flip ? (W - s.u0 - s.w) : s.u0) + "px";
    it.el.style.top = top + "px";
    /* The jog sits just clear of the label, on the side the bar is on, and
       meets the label edge NEAREST the anchor. */
    var hy = up ? (top + ROW - 4) : (top - 4);
    var lx = flip ? (W - s.u0) : s.u0;
    var l0 = flip ? (W - s.u0 - s.w) : s.u0;
    var a = Math.min(it.x, lx), b = Math.max(it.x, lx);
    it.jg.style.left = a + "px";
    it.jg.style.width = Math.max(0, b - a) + "px";
    it.jg.style.top = hy + "px";
    /* No jog where the label already SITS over its anchor. That happens at
       the container edge, where a label wider than the room to its side has
       to overhang - and a horizontal drawn under its own label reads as a
       leader pointing somewhere else. */
    var covers = it.x >= l0 - 2 && it.x <= l0 + s.w + 2;
    it.jg.style.opacity = (!covers && (b - a) > 1) ? "1" : "0";
    it.rz.style.left = it.x + "px";
    it.rz.style.top = up ? hy + "px" : "0px";
    it.rz.style.height = Math.max(2, up ? (H - hy) : hy) + "px";
    if (it.dt){
      it.dt.style.left = (it.x - 2.5) + "px";
      it.dt.style.top = (up ? H - 5 : 0) + "px";
    }
  });
  host.style.height = H + "px";
}

/* --------------------------------------------------------------------------
   The memory map. Blocks are keyed by region id and reused across stages, so
   a block that survives a stage change SLIDES to its new place instead of
   being torn down and rebuilt - which is the whole reason the page animates:
   the thing you are watching is memory moving, and a cut hides the move.
   -------------------------------------------------------------------------- */
var mblocks = {}, mlabels = {};
function drawMap(){
  var st = S[stage], bar = $("mbar"), lab = $("mlab"), ovh = $("movl");
  var W = bar.clientWidth || 1, ram = D.ram;
  var hot = {};
  if (step >= 0) (st.steps[step].mem || []).forEach(function(id){ hot[id] = 1; });
  var seen = {}, items = [];
  st.regions.forEach(function(r){
    seen[r.id] = 1;
    var host = r.layer ? ovh : bar;
    var b = mblocks[r.id];
    if (!b){
      b = document.createElement("div");
      b.className = r.layer ? "ov" : "rg";
      b.style.opacity = "0";
      b.style.left = (100 * r.a / ram) + "%";
      b.style.width = (100 * Math.max(r.b - r.a, ram/900) / ram) + "%";
      host.appendChild(b);
      mblocks[r.id] = b;
      b.addEventListener("click", function(){ pickRegion(r.id); });
      requestAnimationFrame(function(){ b.style.opacity = "1"; });
    }
    if (b.parentNode !== host) host.appendChild(b);
    b.style.opacity = "1";
    b.style.left = (100 * r.a / ram) + "%";
    b.style.width = (100 * Math.max(r.b - r.a, ram/900) / ram) + "%";
    if (!r.layer) b.style.background = col(r.cls);
    b.title = r.label + "  " + hex(r.a) + "-" + hex(r.b) + "  " + bytes(r.b - r.a);
    var anyHot = step >= 0 && Object.keys(hot).length;
    b.classList.toggle("dim", !!(anyHot && !hot[r.id] && r.cls !== "free"));
    b.classList.toggle("hot", !!hot[r.id]);

    /* label it if it is worth a label: everything but the anonymous free runs */
    /* Label everything with a name. The only things that go unlabelled are
       the anonymous runs of arena between claims, and only when they are too
       small to be worth a leader - keyed off the ID and not the colour, so a
       named region that happens to be empty ground (the FAT window before the
       mount) keeps its label. */
    var anon = r.id.indexOf("free") === 0 || r.id === "unclaimed";
    var wantLabel = !anon || (r.b - r.a) > ram * 0.10;
    var L = mlabels[r.id];
    if (wantLabel){
      if (!L){
        L = document.createElement("div"); L.className = "lb";
        var rz = document.createElement("div"); rz.className = "rz";
        var jg = document.createElement("div"); jg.className = "jg";
        var dt = document.createElement("div"); dt.className = "dt";
        lab.appendChild(rz); lab.appendChild(jg); lab.appendChild(dt);
        lab.appendChild(L);
        mlabels[r.id] = L; L._rz = rz; L._jg = jg; L._dt = dt;
        L.addEventListener("click", function(){ pickRegion(r.id); });
      }
      L.innerHTML = "";
      L.appendChild(document.createTextNode(r.label + " "));
      var sz = document.createElement("span"); sz.className = "sz";
      sz.textContent = bytes(r.b - r.a);
      L.appendChild(sz);
      L.style.opacity = "1"; L._rz.style.opacity = "1";
      L.classList.toggle("hot", !!hot[r.id]);
      L._rz.classList.toggle("hot", !!hot[r.id]);
      L._jg.classList.toggle("hot", !!hot[r.id]);
      L._dt.classList.toggle("hot", !!hot[r.id]);
      L._dt.style.opacity = "1";
      items.push({el: L, rz: L._rz, jg: L._jg, dt: L._dt,
                  x: W * (r.a + r.b) / 2 / ram, id: r.id});
    } else if (L){
      L.style.opacity = "0"; L._rz.style.opacity = "0"; L._jg.style.opacity = "0";
    }
  });
  Object.keys(mblocks).forEach(function(id){
    if (!seen[id]){
      mblocks[id].style.opacity = "0";
      if (mlabels[id]){
        mlabels[id].style.opacity = "0";
        mlabels[id]._rz.style.opacity = "0";
        mlabels[id]._jg.style.opacity = "0";
        mlabels[id]._dt.style.opacity = "0";
      }
    }
  });
  layout(lab, items, W, true);

  drawZoom(hot);

  var ru = $("mrule");
  if (!ru.childNodes.length){
    for (var k = 0; k <= 640; k += 128){
      var s = document.createElement("span");
      s.textContent = k ? k + "K" : "0";
      s.style.left = (100 * k / 640) + "%";
      if (k === 0) s.className = "e0";
      if (k === 640) s.className = "e1";
      ru.appendChild(s);
    }
  }
}
function pickRegion(id){
  var st = S[stage];
  for (var i = 0; i < st.steps.length; i++)
    if ((st.steps[i].mem || []).indexOf(id) >= 0){ setStep(i); return; }
  var r = st.regions.filter(function(x){ return x.id === id; })[0];
  if (r) showRegion(r);
}


/* --------------------------------------------------------------------------
   THE MAGNIFIED STRIP. At 640KB to scale, `.ovlw` is 5,215 bytes - four fifths
   of one per cent, a sliver you cannot see and certainly cannot see LYING
   ACROSS two blocks. The point it is making is a shape, so it needs a scale
   that shows the shape. The span is FIXED for every stage - the top of the
   loader's blob, rounded up - so blocks slide within a frame that does not
   move under them, and the bracket on the full map says which slice this is.
   -------------------------------------------------------------------------- */
var zblocks = {};
function drawZoom(hot){
  var st = S[stage], bar = $("zbar"), ovh = $("zovl");
  var lim = D.zoom, W = bar.clientWidth || 1;
  var anyHot = step >= 0 && hot && Object.keys(hot).length;
  var seen = {};
  st.regions.forEach(function(r){
    if (r.a >= lim) return;
    seen[r.id] = 1;
    var host = r.layer ? ovh : bar;
    var b = zblocks[r.id];
    if (!b){
      b = document.createElement("div");
      b.className = r.layer ? "ov" : "rg";
      b.style.opacity = "0";
      b.appendChild(document.createElement("span"));
      host.appendChild(b);
      zblocks[r.id] = b;
      b.addEventListener("click", function(){ pickRegion(r.id); });
      requestAnimationFrame(function(){ b.style.opacity = "1"; });
    }
    if (b.parentNode !== host) host.appendChild(b);
    var w = 100 * (Math.min(r.b, lim) - r.a) / lim;
    b.style.opacity = "1";
    b.style.left = (100 * r.a / lim) + "%";
    b.style.width = Math.max(w, 0.25) + "%";
    if (!r.layer){
      b.style.background = col(r.cls);
      b.classList.toggle("pale", r.cls === "free" || r.cls === "dead");
    }
    b.title = r.label + "  " + hex(r.a) + "-" + hex(r.b) + "  " + bytes(r.b - r.a);
    b.classList.toggle("dim", !!(anyHot && !hot[r.id] && r.cls !== "free"));
    b.classList.toggle("hot", !!hot[r.id]);
    /* Write inside the block - then TAKE IT BACK if it does not fit. A
       clipped label reads as a different, shorter name (".lowbss - task
       stacks, dis"), which is worse than no label at all. */
    var t = b.firstChild;
    t.textContent = r.sl || r.label;
    t.style.visibility = "hidden";
    if (t.scrollWidth + 10 > b.clientWidth) t.textContent = "";
    t.style.visibility = "";
  });
  Object.keys(zblocks).forEach(function(id){
    if (!seen[id]) zblocks[id].style.opacity = "0";
  });
  var sp = $("zspan");
  sp.style.left = "0%";
  sp.style.width = (100 * lim / D.ram) + "%";
  $("zcap").textContent = "0 – " + bytes(lim) + " at " +
    (D.ram / lim).toFixed(0) + "×";
}

/* -------------------------------------------------------------------------- */
var tblocks = {}, tlabels = {};
function drawTime(){
  var st = S[stage], bar = $("tbar"), lab = $("tlab");
  var W = bar.clientWidth || 1;
  var n = st.steps.length, tot = 0, i;
  for (i = 0; i < n; i++) tot += st.steps[i].ms;
  /* A SOFT FLOOR, not a hard one: every segment gets the same small constant
     added before normalising, so ordering and ratios survive and a 0.03 ms
     call is still something you can hit with a mouse. The label carries the
     exact figure, which is the number to read. */
  var pad = 0.35 / n, sum = 0, w = [];
  for (i = 0; i < n; i++){ w[i] = (tot ? st.steps[i].ms / tot : 1/n) + pad; sum += w[i]; }
  bar.innerHTML = ""; lab.innerHTML = "";
  var at = 0, items = [];
  for (i = 0; i < n; i++){
    var sp = st.steps[i], fw = w[i] / sum;
    var el = document.createElement("div");
    el.className = "sg" + (i === step ? " sel" : "");
    el.style.left = (100 * at) + "%";
    el.style.width = (100 * fw) + "%";
    el.style.background = col(KIND[sp.kind] || "kern");
    el.title = sp.label + " - " + ms(sp.ms);
    (function(j){ el.addEventListener("click", function(){ setStep(j); }); })(i);
    bar.appendChild(el);
    var big = n <= 16 || sp.ms >= tot * 0.028 || i === step;
    if (big){
      var L = document.createElement("div");
      L.className = "lb" + (i === step ? " sel" : "");
      L.appendChild(document.createTextNode(short(sp.label) + " "));
      var m = document.createElement("span"); m.className = "ms"; m.textContent = ms(sp.ms);
      L.appendChild(m);
      (function(j){ L.addEventListener("click", function(){ setStep(j); }); })(i);
      var rz = document.createElement("div"); rz.className = "rz" + (i === step ? " sel" : "");
      var jg = document.createElement("div"); jg.className = "jg" + (i === step ? " sel" : "");
      var dt = document.createElement("div"); dt.className = "dt" + (i === step ? " sel" : "");
      lab.appendChild(rz); lab.appendChild(jg); lab.appendChild(dt); lab.appendChild(L);
      items.push({el: L, rz: rz, jg: jg, dt: dt, x: W * (at + fw/2)});
    }
    at += fw;
  }
  layout(lab, items, W, false);
}
function short(s){ return s.length > 44 ? s.slice(0, 43) + "…" : s; }

/* -------------------------------------------------------------------------- */
function showRegion(r){
  $("dtitle").textContent = r.label;
  $("dbody").innerHTML = "";
  var p = document.createElement("p"); p.textContent = r.note; $("dbody").appendChild(p);
  facts([["address", hex(r.a) + " – " + hex(r.b)],
         ["size", bytes(r.b - r.a) + " (" + (r.b - r.a).toLocaleString() + " bytes)"],
         ["segment", hex(r.a >> 4, 4) + ":0000"],
         ["share of 640K", (100 * (r.b - r.a) / D.ram).toFixed(2) + "%"]]);
}
function facts(rows){
  var f = $("dfacts"); f.innerHTML = "";
  rows.forEach(function(kv){
    if (kv[1] === null || kv[1] === undefined || kv[1] === "") return;
    var d = document.createElement("div");
    var a = document.createElement("span"); a.className = "k"; a.textContent = kv[0];
    var b = document.createElement("span"); b.className = "v"; b.textContent = kv[1];
    d.appendChild(a); d.appendChild(b); f.appendChild(d);
  });
}
function drawDetail(){
  var st = S[stage];
  if (step < 0){
    $("dtitle").textContent = st.title;
    $("dbody").innerHTML = "";
    var p = document.createElement("p");
    p.innerHTML = "<span class='tag meas'>measured</span>" +
      "This stage is " + ms(st.ms) + " of the boot. Click a segment of the " +
      "timeline above, or a label on it, to see what that step does — the " +
      "memory it runs from lights up on the map.";
    $("dbody").appendChild(p);
    facts([["stage", (stage + 1) + " of " + S.length],
           ["what moves", st.moved],
           ["time in this stage", ms(st.ms)],
           ["at, from reset", ms(st.t0) + " → " + ms(st.t0 + st.ms)],
           ["steps measured", String(st.steps.length)],
           ["loading bar", st.bar ? (st.bar.done + " / " + st.bar.total +
              "  (" + st.bar.pct.toFixed(1) + "%)") : "not up yet"]]);
    return;
  }
  var sp = st.steps[step];
  $("dtitle").textContent = sp.label;
  $("dbody").innerHTML = "";
  var p = document.createElement("p");
  p.innerHTML = "<span class='tag meas'>measured</span>" + esc(sp.note || "");
  $("dbody").appendChild(p);
  if (sp.mem && sp.mem.length){
    var names = sp.mem.map(function(id){
      var r = st.regions.filter(function(x){ return x.id === id; })[0];
      return r ? r.label : id;
    });
    var q = document.createElement("p");
    q.innerHTML = "<b>Lit up on the map:</b> " + esc(names.join(" · ")) +
      (sp.sect ? " — the code's own section is <code>" + esc(sp.sect) +
                 "</code>, read out of nasm's map." : "");
    $("dbody").appendChild(q);
  }
  var rows = [["time", ms(sp.ms)],
              ["at, from reset", ms(sp.t0)],
              ["share of stage", (100 * sp.ms / Math.max(st.ms, 1e-9)).toFixed(1) + "%"],
              ["phase", sp.phase]];
  if (sp.sectors) rows.push(["sectors moved", String(sp.sectors)]);
  if (sp.reads) rows.push(["int 13h reads", String(sp.reads)]);
  if (sp.cyl) rows.push(["cylinders seeked", String(sp.cyl)]);
  if (sp.mech) rows.push(["of which mechanical", ms(sp.mech)]);
  facts(rows);
}
function esc(s){ var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

/* -------------------------------------------------------------------------- */
function drawSplash(){
  var st = S[stage], box = $("splash");
  var on = !!st.bar;
  box.classList.toggle("off", !on);
  if (on){
    $("sfill").style.width = st.bar.pct.toFixed(2) + "%";
    $("spct").textContent = Math.round(st.bar.pct) + "%";
    $("smsg").textContent = st.bar.msg;
  } else {
    $("sfill").style.width = "0%";
    $("smsg").textContent = stage >= S.length - 1
      ? "the screen has been handed to the desktop"
      : "nothing can draw yet — the code that draws this is still on the floppy";
  }
  $("scab").textContent = on
    ? "The real bar: [spl_done] " + st.bar.done + " of [spl_total] " + st.bar.total +
      ", read out of the running machine at this exact point."
    : "";
}
function drawStages(){
  var s = $("stages"); 
  if (!s.dataset.built){
    S.forEach(function(st, i){
      var b = document.createElement("button");
      b.className = "st"; b.type = "button";
      var n = document.createElement("span"); n.className = "n"; n.textContent = String(i+1);
      var t = document.createElement("span"); t.textContent = st.short || st.id;
      var m = document.createElement("span"); m.className = "ms"; m.textContent = ms(st.ms);
      b.appendChild(n); b.appendChild(t); b.appendChild(m);
      b.addEventListener("click", function(){ setStage(i); });
      s.insertBefore(b, $("navbtns"));
    });
    s.dataset.built = "1";
  }
  Array.prototype.forEach.call(s.querySelectorAll(".st"), function(b, i){
    b.setAttribute("aria-current", i === stage ? "true" : "false");
  });
  $("prev").disabled = stage === 0;
  $("next").disabled = stage === S.length - 1;
  $("stitle").textContent = (stage + 1) + ". " + S[stage].title;
  $("smovedt").innerHTML = "What moves: <b>" + esc(S[stage].moved) + "</b>";
}
function setStage(i){
  if (i < 0 || i >= S.length) return;
  stage = i; step = -1;
  drawStages(); drawSplash(); drawMap(); drawTime(); drawDetail();
}
function setStep(i){
  step = (step === i ? -1 : i);
  drawMap(); drawTime(); drawDetail();
}
$("prev").addEventListener("click", function(){ setStage(stage - 1); });
$("next").addEventListener("click", function(){ setStage(stage + 1); });
document.addEventListener("keydown", function(e){
  if (e.target && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
  if (e.key === "ArrowRight" || e.key === "ArrowDown"){ setStage(stage + 1); e.preventDefault(); }
  else if (e.key === "ArrowLeft" || e.key === "ArrowUp"){ setStage(stage - 1); e.preventDefault(); }
  else if (e.key === "Escape"){ setStep(-1); }
  else if (e.key === "Home"){ setStage(0); e.preventDefault(); }
  else if (e.key === "End"){ setStage(S.length - 1); e.preventDefault(); }
});
var rt;
window.addEventListener("resize", function(){
  clearTimeout(rt); rt = setTimeout(function(){ drawMap(); drawTime(); }, 90);
});
setStage(0);
})();
'''


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# IBM's own typeface, on a page about an IBM 5150 - and the ONE thing here
# that is not in the file. Every rule names a real fallback stack, so a
# machine with no network renders the page correctly in system faces; nothing
# but the lettering depends on it.
FONTS = ('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=IBM+Plex+Mono:wght@400;500&'
         'family=IBM+Plex+Sans:wght@400;500;600&'
         'family=IBM+Plex+Sans+Condensed:wght@600;700&display=swap">')


def render(p, fragment=False):
    """The whole page as one string.

    `fragment` drops <!doctype>, <html>, <head> and <body> for a host that
    supplies its own skeleton (the Artifact wrapper does). Everything else is
    identical, so there is one page and not two.
    """
    m, lad, cons, vol = p["meta"], p["ladder"], p["cons"], p["vol"]
    title = "os8088 Boot Ladder"
    prov = " · ".join(filter(None, [
        "MartyPC <b>%s</b>" % esc(m["machine"]),
        "%s, %d KB" % (esc(m["image"]), m["ram_kb"]),
        "kernel <b>%s</b>" % esc(m["kernel_md5"][:10]),
        ("commit <b>%s</b>" % esc(m["commit"])) if m["commit"] else "",
        "measured <b>%s</b>" % esc(m["taken"]),
    ]))
    rom = ("the real <b>IBM 5150 27 OCT 82</b> ROM, which is the field "
           "machine's own" if m["field"] else
           "the <b>GLaBIOS</b> twin, because the IBM 5150 ROM is not in this "
           "tree — it boots faster than any 5150 ever did, so <b>the ROM's "
           "own time is not a field figure</b>. The FDC's mechanical column "
           "is, being the model PERFORMANCE.md Set 37 calibrated")

    legend = "".join(
        "<span><i style='background:var(--c-%s)'></i>%s</span>" % (k, v)
        for k, v in (("bios", "BIOS"), ("ours", "boot sector / disk"),
                     ("kern", "kernel image"), ("ovl", "boot overlay"),
                     ("data", "mount data"), ("claim", "heap claim"),
                     ("free", "unclaimed")))

    body = """
<div class="wrap">
 <div class="top">
  <div>
   <h1>os8088 <span class="sub">Boot Ladder</span></h1>
   <p class="lede">Every discrete move of memory from power-on to the first
    desktop frame, on a 4.77&nbsp;MHz 8088 booting a 360&nbsp;KB floppy.
    <b>%(nst)d stages.</b> Click one, or use
    <span class="kbd">&larr;</span> <span class="kbd">&rarr;</span>.
    Then click a step on the timeline to light up the RAM it runs from.</p>
   <div class="stamp"><span>%(prov)s</span></div>
  </div>
  <div class="splash-outer">
   <div class="splash off" id="splash">
    <div class="logo" title="The loading screen's own logo. SPL_SPINSH sets the rate: sixteen positions, four ticks each, 3.52 s a revolution. It reads 8808 halfway round because the real one is a coin flip of the whole word - spl_flip scales x about the box centre, so at 180 degrees the first 8 is on the right."><span>8088</span></div>
    <div class="dlg"><div class="dlg2">
      <div class="cap">%(welcome)s</div>
      <div class="trough"><div class="fill" id="sfill"></div></div>
      <div class="pct" id="spct">0%%</div>
      <div class="msg" id="smsg"></div>
    </div></div>
   </div>
   <div class="cabin" id="scab"></div>
  </div>
 </div>

 <div class="stages" id="stages"><span class="nav" id="navbtns">
   <button id="prev" type="button" title="previous stage (left arrow)">&larr;</button>
   <button id="next" type="button" title="next stage (right arrow)">&rarr;</button>
 </span></div>
 <div class="stitle" id="stitle"></div>
 <div class="smoved" id="smovedt"></div>

 <div class="panel">
  <p class="ph"><span>Conventional memory — 640&nbsp;KB, drawn to scale</span>
   <span class="hint">labels rise from the block they name · the hatched band
   is code lying <i>across</i> the map, not a region of it</span></p>
  <div class="mlab" id="mlab"></div>
  <div class="mbar" id="mbar"><div class="zspan" id="zspan"></div></div>
  <div class="movl" id="movl"></div>
  <div class="mrule" id="mrule"></div>
  <div class="zoomhead">
    <span>The busy end, magnified — <b id="zcap"></b>. Everything os8088 puts
     in memory lives here; the bracket above shows the slice.</span>
    <span>the hatched band is <b>the boot overlay</b>, drawn raised because it
     is not a region of the map — it is code lying across two of them</span>
  </div>
  <div class="zbar" id="zbar"></div>
  <div class="zovl" id="zovl"></div>
  <div class="legend">%(legend)s</div>
 </div>

 <div class="panel">
  <p class="ph"><span>What this stage spends its time on</span>
   <span class="hint">widths are proportional, with a small constant added to
   every segment so a 0.03&nbsp;ms call is still clickable — read the figure,
   not the width</span></p>
  <div class="tbar" id="tbar"></div>
  <div class="tlab" id="tlab"></div>
 </div>

 <div class="panel detail">
  <div><h3 id="dtitle"></h3><div id="dbody"></div></div>
  <div class="facts" id="dfacts"></div>
 </div>

 <footer>
  <p><b>Where the numbers come from.</b> Every millisecond is measured on
  MartyPC's own cycle counter at 4.772727&nbsp;MHz with the drive's mechanics
  modelled, running %(rom)s. The loading bar is not a mock-up of the
  arithmetic: <code>[spl_done]</code> and <code>[spl_total]</code> are read out
  of the running kernel at each stop. So is the heap — <code>mem_base</code>,
  <code>mem_top</code> and every record of <code>mem_tab</code>. The addresses
  come from <code>tools/kernsize.py</code>, which measures the kernel this page
  was generated beside.</p>
  <p><b>This page is generated and is not rebuilt by <code>make</code>.</b>
  It goes stale the moment <code>kmain</code> gains a call or a section moves.
  Regenerate it with <code>python3 tools/os88ladder.py</code>, and check it
  still describes the tree with <code>--selfcheck</code> before believing
  anything on it.</p>
  <p class="mono" style="opacity:.75">%(sums)s</p>
 </footer>
</div>
<script>window.LADDER = %(data)s;</script>
<script>%(js)s</script>
""" % {
        "nst": len(p["stages"]),
        "prov": prov, "rom": rom, "legend": legend,
        "welcome": esc(p["strings"]["welcome"]),
        "data": json.dumps(p, separators=(",", ":")),
        "js": JS,
        "sums": esc(
            "KERNEL.SYS %s bytes / %d sectors · blob %d sectors (%s bytes) at "
            "%04X:0000 · kernel image %s bytes ending %04X:0000 · .ovlw %s "
            "bytes over a %s-byte FAT window · total from reset %s · the "
            "kernel's own boot_ticks %d = %.0f ms"
            % ("{:,}".format(vol["kernel"]["size"]), vol["kernel"]["sectors"],
               cons["BOOT2_SECS"],
               "{:,}".format(cons["BOOT2_SECS"] * vol["bps"]), lad["kend"],
               "{:,}".format(lad["ksize"]), lad["kend"],
               "{:,}".format(lad["ovlw"]),
               "{:,}".format((lad["low_seg"] - lad["fat_seg"]) * 16),
               "%.2f s" % (m["total_ms"] / 1000.0),
               m["boot_ticks"], m["boot_ticks_ms"])),
    }
    if fragment:
        return ("<title>%s</title>\n%s\n<style>%s</style>\n%s"
                % (title, FONTS, CSS, body))
    return ("<!doctype html>\n<html lang=\"en\"><head>"
            "<meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,"
            "initial-scale=1\">"
            "<title>%s</title>%s\n<style>%s</style></head><body>%s</body></html>"
            % (title, FONTS, CSS, body))


# -----------------------------------------------------------------------------
# 6. --selfcheck: DOES THIS STILL DESCRIBE THE TREE?
# -----------------------------------------------------------------------------

def selfcheck(image, defines, build="build"):
    """Every assumption this tool makes, tried against the tree, out loud.

    Run this FIRST, always. It needs no emulator and takes about a second, so
    there is no reason not to - and it is the difference between finding out
    that the page is wrong and publishing a page that is wrong.
    """
    ok, bad = [], []

    def try_(what, fn):
        try:
            v = fn()
            ok.append((what, v if isinstance(v, str) else "ok"))
        except SystemExit as e:
            bad.append((what, str(e).splitlines()[0]))
        except Exception as e:                       # noqa: BLE001
            bad.append((what, "%s: %s" % (type(e).__name__, e)))

    try_("constants scraped from source",
         lambda: "%d found" % len(constants()))
    try_("the ladder, out of tools/kernsize.py",
         lambda: "KERNEL %04X  COLD %04X  FAT %04X  LOW %04X  VGABUF %04X  "
                 "HEAP %04X" % tuple(ladder(build, defines)[k] for k in
                                     ("kseg", "cold_seg", "fat_seg", "low_seg",
                                      "vgabuf_seg", "kend")))
    try_("the image's BPB and KERNEL.SYS",
         lambda: "%d sectors at LBA %d, %d SPT x %d heads"
                 % (volume(image)["kernel"]["sectors"],
                    volume(image)["kernel"]["lba"], volume(image)["spt"],
                    volume(image)["heads"]))
    try_("the loading screen's own strings",
         lambda: " / ".join(strings().values()))
    try_("heap claim tags in kernel/memory.inc",
         lambda: "%d tags" % len(owner_tags()))

    def cover():
        unused = check_coverage(defines)
        out = "every kmain call is in a stage"
        if unused:
            out += "; not built in this configuration: " + ", ".join(unused)
        return out
    try_("kmain's calls, against the STAGES table", cover)

    def phases_have_notes():
        import os88boot
        live = [n for _, n, _ in os88boot.collapse(os88boot.callsites(defines))]
        gap = [n for n in live if n not in NOTES]
        if gap:
            raise SystemExit("os88ladder: no note written for: %s"
                             % ", ".join(sorted(set(gap))))
        return "%d phases, all with a note" % len(set(live))
    try_("a note for every phase the page will show", phases_have_notes)

    try_("MartyPC, and a machine to run it on",
         lambda: ("IBM-ROM %s - field figures" % FIELD_MACHINE)
                 if machine_available(FIELD_MACHINE)
                 else (("GLaBIOS %s only - the IBM 5150 ROM is not in "
                        "tools/martypc/roms/, so the ROM's own time will not "
                        "be a field figure" % TWIN_MACHINE)
                       if machine_available(TWIN_MACHINE)
                       else _no_marty()))

    w = max(len(k) for k, _ in ok + bad) if (ok or bad) else 0
    for k, v in ok:
        sys.stdout.write("  ok   %-*s  %s\n" % (w, k, v))
    for k, v in bad:
        sys.stdout.write("  FAIL %-*s  %s\n" % (w, k, v))
    if bad:
        sys.stdout.write(
            "\nos88ladder: %d check(s) failed. THE PAGE IS OUT OF DATE WITH "
            "THE TREE.\nFix these before regenerating - each line above names "
            "the file to open.\n" % len(bad))
        return 1
    sys.stdout.write("\nos88ladder: the model still describes this tree.\n")
    return 0


def _no_marty():
    raise SystemExit("os88ladder: no MartyPC to measure with - `make marty` "
                     "(needs cargo, libudev-dev and pkg-config)")


# -----------------------------------------------------------------------------
# 7. The command line.
# -----------------------------------------------------------------------------

USAGE = """os88ladder - the interactive Boot Ladder page (ON DEMAND, never in `make`)

  python3 tools/os88ladder.py [options]

  --selfcheck        does the model still describe this tree? RUN THIS FIRST.
                     No emulator, about a second, and it names the file to open
                     for anything that has moved.
  -o, --out PATH     where to write (default build/bootladder.html)
  --fragment         emit without <html>/<head>/<body>, for a host that has its
                     own skeleton (the Artifact wrapper)
  --image PATH       the floppy to boot (default build/os8088-360.img)
  --machine NAME     a MartyPC machine (default: the IBM-ROM 5150, falling back
                     to its GLaBIOS twin when the ROM is not in the tree)
  --define SYM       an extra -D for the kernel this describes (repeatable)
  --build DIR        where the built kernel is (default build)
  --json PATH        where to keep the model (default: beside the page). It
                     carries the WALK it was built from, so `--measure` on it
                     re-renders in seconds without booting anything
  --measure PATH     re-use a walk taken earlier instead of booting again
  --no-measure       refuse to boot anything; only legal with --measure
"""


def main(argv):
    image = os.path.join(ROOT, "build", "os8088-360.img")
    out = os.path.join(ROOT, "build", "bootladder.html")
    machine, defines, build = None, ["KERN_BIG"], "build"
    jsonout, reuse, frag, check, nomeas = None, None, False, False, False
    it = iter(argv)
    for a in it:
        if a == "--selfcheck":
            check = True
        elif a in ("-o", "--out"):
            out = next(it)
        elif a == "--fragment":
            frag = True
        elif a == "--image":
            image = next(it)
        elif a == "--machine":
            machine = next(it)
        elif a == "--define":
            defines.append(next(it))
        elif a == "--build":
            build = next(it)
        elif a == "--json":
            jsonout = next(it)
        elif a == "--measure":
            reuse = next(it)
        elif a == "--no-measure":
            nomeas = True
        else:
            raise SystemExit(USAGE)
    defines = tuple(defines)

    if check:
        return selfcheck(image, defines, build)

    # THE SELF-CHECK RUNS ANYWAY, because a page generated off a stale model is
    # worse than no page: it looks exactly like a good one.
    sys.stderr.write("os88ladder: checking the model against the tree...\n")
    if selfcheck(image, defines, build):
        sys.stderr.write("os88ladder: refusing to generate a page from a model "
                         "the tree has moved out from under.\n")
        return 1

    lad, cons, vol, strs = ladder(build, defines), constants(), volume(image), strings()
    if reuse:
        w = json.load(open(reuse))
        if "events" not in w and isinstance(w.get("walk"), dict):
            w = w["walk"]                   # a MODEL: take the walk out of it
        if "events" not in w or "machine" not in w:
            raise SystemExit(
                "os88ladder: %s is not a walk and has no walk in it.\n"
                "  --measure takes what a previous run MEASURED - either the "
                "file --json wrote, or a bare walk.\n"
                "  If this is neither, drop --measure and let it boot." % reuse)
        sys.stderr.write("os88ladder: re-using the walk in %s (%s, %s)\n"
                         % (reuse, w["machine"], w["taken"]))
    elif nomeas:
        raise SystemExit("os88ladder: --no-measure needs --measure PATH - "
                         "there is nothing to draw a timeline from")
    else:
        if machine is None:
            machine = (FIELD_MACHINE if machine_available(FIELD_MACHINE)
                       else TWIN_MACHINE)
            if machine == TWIN_MACHINE:
                sys.stderr.write(
                    "os88ladder: the IBM 5150 ROM is not in tools/martypc/"
                    "roms/, so this measures the GLaBIOS twin. The page will "
                    "say so.\n")
        sys.stderr.write("os88ladder: booting %s on %s - this is minutes, "
                         "not seconds\n" % (os.path.basename(image), machine))
        t0 = time.time()
        w = walk(image, machine, defines, lad, cons)
        sys.stderr.write("os88ladder: walked %d phases in %.0f s of host time\n"
                         % (len(w["events"]), time.time() - t0))

    p = build_page(w, lad, cons, vol, defines, strs)
    # The walk rides in the JSON so a re-render needs no boot; it does NOT ride
    # in the page, which would put 26KB of raw cycle counts into every reader's
    # download to say nothing the page does not already draw.
    html = render(dict((k, v) for k, v in p.items() if k != "walk"),
                  fragment=frag)
    d = os.path.dirname(os.path.abspath(out))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    open(out, "w", encoding="utf-8").write(html)
    json.dump(p, open(jsonout or (os.path.splitext(out)[0] + ".json"), "w"),
              indent=1)
    sys.stderr.write(
        "os88ladder: %s  (%s, %d stages, %d measured phases)\n"
        % (out, "{:,}".format(len(html)), len(p["stages"]),
           sum(len(s["steps"]) for s in p["stages"])))
    # The one line worth reading back: the two clocks that should agree.
    below = w["total_ms"] - w["events"][0]["ms"]
    sys.stderr.write(
        "os88ladder: cross-check - the kernel's own boot_ticks is %d = %.0f ms "
        "against %.0f ms of measured phases below `post` (%+.0f ms, one tick "
        "is 54.9)\n" % (w["boot_ticks"], w["boot_ticks_ms"], below,
                        w["boot_ticks_ms"] - below))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
