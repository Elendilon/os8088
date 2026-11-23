#!/usr/bin/env python3
"""bbedjob - THE COURSE BUILDER'S JOBS (SPEC.md 130.58.8), each run as a process
by tools/bbedit.py, reporting JSON lines on stdout and killed by Cancel or by
the next edit:

    python3 tools/bbedjob.py picture COURSE.bbc OUTDIR [--name PATH] [--gaps] [--occ]   # the Iso view's picture
    python3 tools/bbedjob.py check   COURSE.bbc [--strict] [--trap] [--name PATH]   # the full check
    python3 tools/bbedjob.py ride    COURSE.bbc LINE [--name PATH]     # how each ball rides a shape

Each line is a JSON object: {"stage": ..., "what": ...} while it works, then
{"stage": "done", "ok": true|false, ...}.

PICTURE compiles WITHOUT the occluder pass (fast) and with the part's block
limit lifted, because the picture is all it keeps: a course over the limit
still gets a picture to look at, and the CHECK says what is over. It writes
OUTDIR/cga.png, OUTDIR/herc.png, OUTDIR/owners.bin (the cell that drew each
pixel, 256 wx + wy or -1, int32 rows) and OUTDIR/meta.json (the size, the
origin, every mark the visibility audit weighs with its seen and hidden
pixels; with --gaps, the gap band's candidate faces, SPEC.md 130.57.4). With
--occ it also compiles WITH the occluders and writes OUTDIR/occ.json: every
record the rule cuts, the cells it hides, the OCC/OCCG cells and why a
windmill's doorway is in the shade (SPEC.md 130.58.32).

CHECK is bbcourse's compile_course: the errors that refuse the course and
the warnings that do not (SPEC.md 130.58.4); a blend warning carries its two
regions' cells and the seam's pixels (130.58.18); and the ROUTE's warnings
(bbcourse.route_lint, SPEC.md 130.58.49), the builder's own, each naming the
`way` line to move or add beside.  Its `done` line carries the course's STATS
(course_stats, SPEC.md 130.58.51): each figure against its bound, the bytes on
the floppy, and every option the course uses to go past a usual bound.

RIDE (SPEC.md 130.58.19) rolls each ball over the shape on line LINE - a
chute, a pit or a hump - on the play-only compile, and answers in words.
"""

import json
import os
import re
import sys
import time
from array import array

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bbcourse as B  # noqa: E402
import bbedmap as M  # noqa: E402


def emit(**kw):
    sys.stdout.write(json.dumps(kw) + "\n")
    sys.stdout.flush()


def refusal(e):
    """a refusal's extra keys for the window: a MOUTH that does not fit (SPEC.md 130.58.41) names its tube's line
    and the largest height in half units that does (None: none does) -> {"mouth": [line, h2 | None]} or {}"""
    return {"mouth": [e.line, e.fit]} if isinstance(e, B.MouthFit) else {}


def palette(src):
    """the course's CGA colours (SPEC.md 130.16.6): its `palette` byte, else palette 1 bright"""
    b = src.palette[0] if src.palette else 0x30
    bright = bool(b & 0x10)
    if b & 0x20:
        cols = [(85, 255, 255), (255, 85, 255), (255, 255, 255)] if bright else \
               [(0, 170, 170), (170, 0, 170), (170, 170, 170)]
    else:
        cols = [(85, 255, 85), (255, 85, 85), (255, 255, 85)] if bright else \
               [(0, 170, 0), (170, 0, 0), (170, 85, 0)]
    return [(0, 0, 0)] + cols


BLEND_KEYS = ("regions", "lines", "seam", "px", "cards", "x0", "y0")


def warning(w):
    """a warning as JSON: its kind, message, line, cell and whether accepted - and a blend's two regions' cells,
    lines and seam pixels with the picture's origin they were measured at (SPEC.md 130.58.18), for the window"""
    out = {k: w[k] for k in ("kind", "msg", "line", "cell", "accepted")}
    out.update({k: w[k] for k in BLEND_KEYS if k in w})
    return out


def picture(path, out, name=None, gaps=False, occ=False):
    from PIL import Image
    t0 = time.time()
    with open(path, "r", encoding="ascii", newline="") as f:
        text = f.read()
    path = name or path
    B.BLK_MAX = 1 << 30                         # the picture's alone: never a part that ships (130.58.8)
    B.GAP_DETECT = gaps                         # the gap band's candidates, only while the overlay shows (130.58.21)
    emit(stage="compile", what="laying the course")
    dropped = []                                # SPEC.md 130.58.21: a `gap` an edit left banding nothing is
    while True:                                 # dropped (the window removes it from the course) - never a
        try:                                    # picture refused for a mark that no longer fits
            if M.is_map(text):                  # a pathway: its pads' courses with the extra ones (130.58.20)
                c = M.compile_map(text, path)
            else:
                c = B.compile_course(text, path, occluders=False)
            break
        except B.CourseError as e:
            m = re.search(r":(\d+): gap bands nothing", str(e))
            lines = text.split("\n")
            if m and len(dropped) < 64 and 0 < int(m.group(1)) <= len(lines) and \
                    lines[int(m.group(1)) - 1].split()[:1] == ["gap"]:
                dropped.append(int(m.group(1)))
                lines[int(m.group(1)) - 1] = "#" + lines[int(m.group(1)) - 1]     # (the line numbers kept)
                text = "\n".join(lines)
                continue
            emit(stage="done", ok=False, error=str(e), secs=round(time.time() - t0, 2), **refusal(e))
            return 1
    emit(stage="render", what="drawing the picture")
    os.makedirs(out, exist_ok=True)
    pal = palette(c.src)
    img = Image.new("RGB", (c.width, c.lines))
    img.putdata([pal[v] for r in c.pic for v in r])
    img.save(os.path.join(out, "cga.png"))
    h = Image.new("L", (c.width * 2, c.lines))
    data = []
    for y, row in enumerate(c.pic):
        for x, v in enumerate(row):
            pr = B.herc_pair(v, y, x)
            data += [255 * (pr >> 1), 255 * (pr & 1)]
    h.putdata(data)
    h.save(os.path.join(out, "herc.png"))
    emit(stage="owners", what="who drew each pixel")
    ob = B.owners_canvas(c)
    a = array("i")
    for row in ob:
        a.extend(row)
    with open(os.path.join(out, "owners.bin"), "wb") as f:
        a.tofile(f)
    marks = []
    try:
        for m in B.vis_marks(c):
            pix = c.prop_pix[m["prop"]]
            key = m["what"].split()[-1] if m["what"].startswith("tube") else m["what"]
            pts = pix.get(key) or []
            own = 256 * m["cell"][0] + m["cell"][1]
            marks.append({"what": m["what"], "cell": list(m["cell"]), "pct": round(m["pct"], 1), "need": m["need"],
                          "below": m["below"], "accepted": m["accepted"], "line": c.props[m["prop"]].get("line"),
                          "cover": [[o >> 8, o & 255, n] for o, n in m["cover"] if o >= 0],
                          "seen": [[x, y] for (x, y) in pts if ob[y][x] == own],
                          "hidden": [[x, y] for (x, y) in pts if ob[y][x] != own]})
    except Exception as e:                      # (the audit wants more than a picture compile holds)
        emit(stage="log", what="no visibility marks: %s" % e)
    occm = None
    if occ:                                     # SPEC.md 130.58.32: the occluders, only while the overlay shows
        emit(stage="occluders", what="cutting the occluders (the full rules: a while on a big course)")
        tmp = os.path.join(out, "occ.bbc")
        with open(tmp, "w", encoding="ascii", newline="") as f:
            f.write(text)                       # (the text the picture drew: dropped gap marks commented out)
        t1 = time.time()
        ws, err = occluders(tmp, out, path)
        os.remove(tmp)
        occm = {"error": err, "secs": round(time.time() - t1, 2),
                "partial": bool(err) and os.path.exists(os.path.join(out, "occ.json")),   # (130.58.46)
                "warnings": [w for w in ws if w["kind"] == "shade"] if ws else []}
    meta = {"width": c.width, "lines": c.lines, "x0": c.x0, "y0": c.y0, "name": c.name, "marks": marks,
            "warnings": [warning(w) for w in c.warnings] + (occm["warnings"] if occm else []), "occ": occm,
            "gaps": c.gap_faces if gaps else None, "dropped_gaps": dropped, "secs": round(time.time() - t0, 2)}
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f)
    emit(stage="done", ok=True, out=out, secs=meta["secs"])
    return 0


def _runs(pix):
    """a pixel set -> [[y, x0, x1], ...]: its horizontal runs, x1 inclusive"""
    out = []
    for (x, y) in sorted(pix, key=lambda p: (p[1], p[0])):
        if out and out[-1][0] == y and out[-1][2] == x - 1:
            out[-1][2] = x
        else:
            out.append([y, x, x])
    return out


def _flag_recs(c, rc, margin, lo, hi):
    """the rule's records a ball in reach position RC at whole heights LO .. HI meets, margin MARGIN - what sets its
    cell's OCC (margin 0, the reach's heights) or OCCG (BZ_CLIMB, its floor's): _laid's test, a record of a block
    of the footprint's at height z when its s is over the cell's and its top over z + margin (to the line: a
    whole height's fraction taken at every height, so a record a line from the edge may be listed that the
    compiler's count leaves out - the flag is the compiler's)"""
    out = set()
    x0, y0 = c.x0, c.y0
    xl, xh = B.foot_x(rc, x0)
    k = 8 * rc.s - 13 + y0
    for br in range((k - hi - 1) >> 3, ((k - lo + 30) >> 3) + 1):
        zmin, zmax = max(lo, k - 8 * br - 8), min(hi, k + 30 - 8 * br)
        if zmin > zmax:
            continue
        for bc in range(xl >> 3, (xh >> 3) + 1):
            for r in c.rule_by_block.get((br, bc), ()):
                if r["s"] > rc.s and r["top"] > zmin + margin:
                    out.add(id(r))
    return out


def _floor_range(c, rc):
    """a FLOOR or GOAL reach cell's grounded heights, px (as _occg takes them), or None"""
    rs = [t for t in B.tile_recs(c.tiles.get((rc.wx, rc.wy))) if t.kind in (B.KIND_FLOOR, B.KIND_GOAL)]
    if not rs or isinstance(c.tiles.get((rc.wx, rc.wy)), B.FieldTile):
        return None
    lo = 4 * min(min(t.wbed if getattr(t, "wbed", None) is not None else t.z0, min(t.corners())) for t in rs)
    return lo, 4 * max(max(t.corners()) for t in rs)


def occ_data(c):
    """SPEC.md 130.58.32: the occluder view's data, in the picture's pixels - every record the RULE cuts (the
    records the cells' OCC and OCCG flags are counted on: c.rule_records), its pixels as runs, s, top, the cells
    that drew them, the cells whose ball positions NEED it (the cutter's test, pixel by pixel: a `noocclude` over
    all of them and it is not cut) and the cells whose flags it sets; every flagged cell; and for each windmill
    whose doorway is in the shade (130.12.4.6) its IN 3 x 3, the flagged cells and the records that flag them;
    and (SPEC.md 130.58.44) `shipped`, the same rows for the records the PART ships (c.records, after AV and the
    merge), each with `rule`, the rule's records that share its pixels"""
    ob = B.owners_canvas(c)
    y0 = c.y0
    recs = c.rule_records
    rid = {id(r): i for i, r in enumerate(recs)}
    rails = {}
    if c.redges:                                # (each rail's pixels, as rail_pixels lays them, by its line)
        bases = {}
        for key in c.redges:
            bases.setdefault(B.rail_key(key, c.tiles), set()).add(B.rail_base(key, c.tiles))
        for key in c.redges:
            two = len(bases[B.rail_key(key, c.tiles)]) > 1
            for (x, y) in B.rail_pix(key, c.redges[key], c.tiles, c.x0, two):
                rails[(x, y + y0)] = c.redges[key].get("line")
    out = _rec_rows(c, recs, ob, rails)
    _needs(c, recs, out, c.rule_by_block)
    # the flags, and which records set them
    fl = {}
    for rc in c.reach:
        cell = (rc.wx, rc.wy)
        f = c.cells.get(cell, (0, 0, 0, 0))[3] & (B.FL_OCC | B.FL_OCCG)
        if not f:
            continue
        fl[cell] = f
        ids = _flag_recs(c, rc, 0, rc.zlo, rc.zhi)
        if f & B.FL_OCCG:
            zr = _floor_range(c, rc)
            ids |= _flag_recs(c, rc, B.CLIMB, *(zr or (rc.zlo, rc.zhi)))
        for k in ids:
            out[rid[k]]["flags"].add(cell)
    by_cell = {}
    for o in out:
        for cl in o["flags"]:
            by_cell.setdefault(cl, []).append(o["id"])
    shade = []
    for p in c.props:
        if p["kind"] != B.PK_WINDMILL:
            continue
        ix, iy = p["inn"]
        box = [(ix + dx, iy + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
        hit = [cl for cl in box if cl in fl]
        if not hit:
            continue
        ids = sorted({k for cl in hit for k in by_cell.get(cl, ())})
        feet = {}
        for cl in hit:
            rc = next((q for q in c.reach if (q.wx, q.wy) == cl), None)
            if rc is not None:
                xl, xh = B.foot_x(rc, c.x0)
                zr = _floor_range(c, rc) if fl[cl] & B.FL_OCCG else None
                z = zr[0] if zr else rc.zlo
                t0 = B.foot_top(rc, z) + y0
                feet["%d,%d" % cl] = [xl, t0 - 1, xh, t0 + 30]   # the box a ball anywhere in the cell covers
        shade.append({"line": p.get("wline") or p.get("line"), "inn": [ix, iy], "box": [list(b) for b in box],
                      "flagged": [[cl[0], cl[1], "OCCG" if fl[cl] & B.FL_OCCG else "OCC"] for cl in hit],
                      "records": ids, "feet": feet, "why": _shade_why(c, hit, fl, ids, out)})
    # SPEC.md 130.58.44: the records the PART ships (c.records: AV's residual and today's records, merged) - the
    # same rows, their `needs` by the same test over their own blocks, and `rule`: the rule's records sharing
    # their pixels (what each shipped record was cut as)
    ship = _rec_rows(c, c.records, ob, rails)
    _needs(c, c.records, ship, c.by_block)
    at = {}
    for o in out:
        for y, x0_, x1_ in o["runs"]:
            for x in range(x0_, x1_ + 1):
                at.setdefault((x, y), []).append(o["id"])
    for o, r in zip(ship, c.records):
        o["rule"] = sorted({k for p in r["pix"] for k in at.get(p, ())})
    for o in out + ship:
        o["needs"] = sorted(o["needs"])
        o["flags"] = sorted(o["flags"])
    return {"records": out, "shipped": ship, "av": bool(c.av),
            "cells": [[x, y, f] for (x, y), f in sorted(fl.items())], "shade": shade,
            "noocc": sorted(getattr(c, "noocc", ()) or ())}


def _rec_rows(c, recs, ob, rails):
    """occ_data's row for each record of RECS: its pixels as runs, s, top, the cells that drew them, a rail's line"""
    out = []
    for i, r in enumerate(recs):
        own = {}
        rl = set()
        for p in r["pix"]:
            o = ob[p[1]][p[0]]
            own[o] = own.get(o, 0) + 1
            if p in rails:
                rl.add(rails[p])
        out.append({"id": i, "s": r["s"], "top": r["top"], "brow": r["brow"], "col": r["col"],
                    "own": [[o >> 8, o & 255, n] for o, n in sorted(own.items(), key=lambda kv: -kv[1]) if o >= 0],
                    "rails": sorted(l_ for l_ in rl if l_), "runs": _runs(r["pix"]), "needs": set(), "flags": set()})
    return out


def _needs(c, recs, out, by_block):
    """who NEEDS each record of RECS (OUT its rows, BY_BLOCK its blocks): _occluders' test over the reach (feet_real,
    the cutter's poses), pixel by pixel"""
    rid = {id(r): i for i, r in enumerate(recs)}
    hi = {id(r): (max(m["s"] for m in r.get("members") or (r,)), max(m["top"] for m in r.get("members") or (r,)))
          for r in recs}                        # (a merged record's s and top are its first member's: the test
    sb, tb, y0 = c.sbuf, c.tbuf, c.y0           # below skips on the highest of its members')
    dyn = getattr(c, "cutdyn", None)
    plane = dyn is not None and (len(dyn) < 3 or dyn[2])     # (SPEC.md 130.49.9, as the cutter)
    for rc, zlo, zhi, xl, xh, yt0, yb0, flo, _vd in B.feet_real(c.reach, c.tiles, c.x0, dyn):
        pl = B.ball_plane(c.tiles, rc, c.x0, y0) if plane and flo else None
        s = rc.s
        ytop, ybot = yt0 - zhi + y0, yb0 - zlo + y0
        cell = (rc.wx, rc.wy)
        for br in range(max(ytop, 0) >> 3, (ybot >> 3) + 1):
            for bc in range(max(xl, 0) >> 3, (xh >> 3) + 1):
                for r in by_block.get((br, bc), ()):
                    o = out[rid[id(r)]]
                    sh, th = hi[id(r)]
                    if sh <= s or th <= zlo or cell in o["needs"]:
                        continue
                    for (x, y) in r["pix"]:
                        if not (xl <= x <= xh and ytop <= y <= ybot):
                            continue
                        sp, tp = sb[y][x], tb[y][x]
                        if sp <= s:
                            continue
                        zmax = zhi if tp > zhi else tp - 1
                        if zmax < zlo or (flo and tp <= zlo + B.CLIMB) or (pl is not None and tp <= pl(x, y)):
                            continue
                        if y < yt0 - zmax + y0 - (1 if zmax < zhi else 0):
                            continue
                        o["needs"].add(cell)
                        break


def _shade_why(c, hit, fl, ids, out):
    """one plain sentence: what flags the doorway's cells - the cells that drew the records, a guard rail's
    line when its pixels are the record's, and how far over a resting ball they reach"""
    cells = " and ".join("(%d, %d)" % cl for cl in hit)
    if not ids:
        return "%s of the doorway's 3 x 3 can be hidden (no record found to show)" % cells
    owners, rails = {}, set()
    for k in ids:
        for x, y, n in out[k]["own"]:
            owners[(x, y)] = owners.get((x, y), 0) + n
        rails |= set(out[k]["rails"])
    own = ", ".join("(%d, %d)" % o for o in sorted(owners, key=lambda o: -owners[o])[:4])
    top = max(out[k]["top"] for k in ids)
    many = len(owners) > 1
    if rails:
        what = ("the guard rail on line%s %s, drawn with cell%s %s (a rail stands on the HIGHER floor of its edge, "
                "so a floor raised beside it lifts it)" % ("s" if len(rails) > 1 else "",
                                                          ", ".join(map(str, sorted(rails))), "s" if many else "", own))
    else:
        what = "what cell%s %s draw%s" % ("s" if many else "", own, "" if many else "s")
    rc = next((q for q in c.reach if (q.wx, q.wy) == hit[0]), None)
    zr = _floor_range(c, rc) if rc is not None else None
    over = (", %d px over the floor a ball rests on" % (top - zr[0])) if zr else ""
    return ("Not the windmill: it is the BALL. A ball anywhere in %s (the doorway's 3 x 3) has its box (dashed) "
            "reaching under %s; %s nearer the viewer, so it is drawn in front of the ball%s. While the rotor turns no "
            "occluder is laid, so such a ball would be drawn over it." % (
                cells, what, "those cells are" if many else "that cell is", over))


def occluders(path, out, name=None):
    """the --occ half of PICTURE: the course compiled WITH its occluders (the part's block limit lifted, as the
    picture's), written to OUTDIR/occ.json; -> the compile's warnings, or an error string"""
    t0 = time.time()
    with open(path, "r", encoding="ascii", newline="") as f:
        text = f.read()
    refused = None
    try:
        c = B.compile_course(text, name or path, occluders=True)
    except B.CourseError as e:
        c = partial_course(e)                   # SPEC.md 130.58.46: a refusal AFTER the cut still shows the cut
        if c is None:
            return None, str(e)
        refused = str(e)
    d = occ_data(c)
    d["secs"] = round(time.time() - t0, 2)
    d["refused"] = refused
    with open(os.path.join(out, "occ.json"), "w") as f:
        json.dump(d, f, separators=(",", ":"))
    return [warning(w) for w in getattr(c, "warnings", None) or []], refused


class _Partial(object):
    """the course as far as a refused compile cut it (partial_course)"""


def partial_course(e):
    """SPEC.md 130.58.46: a compile refused AFTER its occluder cut (a bound: the 256 masks, a band's 256, a block
    row's records, the occluder pass, the part's size) -> the course as cut, read off the refused compile's own frame
    (bbcourse._compile_course's locals: the rule's records and the part's, the flags, the picture's buffers), so the
    overlay can show what to `noocclude` to come under the bound; None for a refusal before the cut.  The compiler
    is untouched: nothing it writes can differ"""
    tb, frame = e.__traceback__, None
    while tb is not None:
        f = tb.tb_frame
        if f.f_code is B._compile_course.__code__ and "rule" in f.f_locals and "records" in f.f_locals:
            frame = f.f_locals                  # (the innermost: a re-cut's, 130.49.5, after the first's)
        tb = tb.tb_next
    if frame is None:
        return None
    g = frame.get
    c = _Partial()
    c.tiles, c.ops, c.x0, c.y0, c.width, c.lines = g("tiles"), g("ops"), g("x0"), g("y0"), g("width"), g("lines")
    cv = g("cv")
    c.sbuf, c.tbuf = cv.sbuf, cv.tbuf
    c.reach, c.cells, c.redges, c.props, c.src = g("reach"), g("cells"), dict(g("redges") or {}), g("props"), g("src")
    c.rule_raw, c.rule_records, c.rule_occpix, c.rule_by_block = g("rule")
    c.records, c.by_block = g("records"), g("by_block")
    c.av, c.av_rcs = bool(g("av_on")), g("av_rcs")
    c.noocc = g("noocc") or frozenset()
    c.cutdyn = g("dyn") if g("cutocc") else None
    c.warnings = []
    return c


def check(path, strict, name=None, trap=False):
    t0 = time.time()
    with open(path, "r", encoding="ascii", newline="") as f:
        text = f.read()
    path = name or path
    if M.is_map(text):                          # the pathway: its own compile and the map's PROOFS (130.58.20)
        emit(stage="compile", what="the map and every pad's course (its exits)")
        try:
            pr = M.proofs(text, path, log=lambda nm: emit(stage="compile", what="the map: %s's exits" % nm))
        except B.CourseError as e:
            emit(stage="done", ok=False, error=str(e), secs=round(time.time() - t0, 1), **refusal(e))
            return 1
        emit(stage="done", ok=True, warnings=[], proofs=str(pr)[:400], secs=round(time.time() - t0, 1))
        return 0
    B.TRAP_CHECK = trap                         # SPEC.md 130.58.24: NO TRAP only when asked
    emit(stage="compile", what="the full check (occluders, reach%s)" % (", softlocks" if trap else ""))
    try:
        c = B.compile_course(text, path, strict=strict)
    except B.CourseError as e:
        emit(stage="done", ok=False, error=str(e), secs=round(time.time() - t0, 1), **refusal(e))
        return 1
    if not c.test and c.src.title_ln is None:   # SPEC.md 130.58.23: what the GAME BUILD asks of every course (its
        emit(stage="compile", what="the game's rules: the finish clock, music, target")   # finishes' clocks, its
        try:                                    # song, its target), checked here too, so "Put in the game" never
            B.course_song(c)                    # refuses a course the full check passed
            B.check_budget(c)
            B.finish_reach_rule(c)
            B.finish_clock_rule(c)
        except B.CourseError as e:
            emit(stage="done", ok=False, error=str(e), secs=round(time.time() - t0, 1), **refusal(e))
            return 1
    warns = [warning(w) for w in c.warnings]
    if c.src.ways:                              # SPEC.md 130.58.49: the route's warnings, the builder's own (never
        emit(stage="compile", what="the route's ways")    # the compiler's: no refusal, under --strict either)
        warns += [warning(w) for w in B.route_lint(c)]
    emit(stage="compile", what="the course's stats (its song, packed as the game packs it)")
    st = course_stats(c)                        # SPEC.md 130.58.51: last - it re-encodes c with its song
    emit(stage="done", ok=True, warnings=warns, stats=st, secs=round(time.time() - t0, 1))
    return 0


NEAR = 0.9                      # SPEC.md 130.58.51: a figure at 90% of its bound or more is shown as near it


def _row(key, label, text, n=None, bound=None):
    """a stats row: N against BOUND (None: no bound) and TEXT, the words the window shows.  Its "state": "over"
    past the bound (only the size budget can be: it is reported, never refused), "near" at NEAR of it or more,
    else "ok" (and "near" True for either of the first two)"""
    st = "ok" if not bound or n is None else "over" if n > bound else "near" if n >= NEAR * bound else "ok"
    return {"key": key, "label": label, "text": text, "n": n, "max": bound, "state": st, "near": st != "ok"}


def _fmt(n):
    return format(n, ",")


def course_stats(c):
    """SPEC.md 130.58.51: course C's STATS, read off the compile the full check made (no second compile) ->
    {"rows": [row], "above": [{"key", "name", "spec", "detail"}], "summary": one line}.  The song is attached
    first (bbcourse.attach_song, as the game build does: its section S is in the part), so the part sizes and the
    bytes on the floppy are the shipped ones; the floppy's are os88pkg's - the part LZB-packed (BZPARTZF) with the
    near-call filter tried, bbcourse.packed_len"""
    rows, above = [], []
    song = None
    if c.src.music is not None:
        try:
            songs = B._music()[1]
            if songs:
                B.attach_song(c, songs[B.course_song(c)])
                song = True
        except B.CourseError as e:
            song = str(e)
    # THE PICTURE
    rows.append(_row("width", "Picture", "%s x %s px, %d x %d cells (COLS x BROWS)" % (
        _fmt(c.width), _fmt(c.lines), c.cols, c.brows), c.width, 8 * B.COLS_MAX))
    rows.append(_row("brows", "Block rows", "%d of %d" % (c.brows, B.BROWS_MAX), c.brows, B.BROWS_MAX))
    if c.cols > 128:
        above.append({"key": "wide", "name": "Wider than 1,024 px", "spec": "130.10.4.2",
                      "detail": "%s px (COLS %d): WIDTH 160, any multiple of 8 word columns up to 1,280 px" % (
                          _fmt(c.width), c.cols)})
    # BLOCKS
    nb = len(c.blocks)
    if nb > B.BLK_ROWP:
        rows.append(_row("blocks", "Blocks", "%s of %s (past 1,024: the map is form 9 ROWNIBS)" % (
            _fmt(nb), _fmt(B.BLK_MAX)), nb, B.BLK_MAX))
        above.append({"key": "rownibs", "name": "More than 1,024 blocks", "spec": "130.56",
                      "detail": "%s blocks: the map is stored as form 9 ROWNIBS (a 12-bit block index)" % _fmt(nb)})
    else:
        rows.append(_row("blocks", "Blocks", "%s of %s (form 1 ROWPLANES)" % (_fmt(nb), _fmt(B.BLK_ROWP)),
                         nb, B.BLK_ROWP))
    # OCCLUDER RECORDS AND MASKS
    ship = len(c.model["recs"])
    rows.append(_row("records", "Occluder records", "%s shipped; %s merged from %s cut by AV; the rule's %s "
                     "before AV (%s before its merge)" % (
                         _fmt(ship), _fmt(len(c.records)), _fmt(len(c.raw)), _fmt(len(c.rule_records)),
                         _fmt(len(c.rule_raw))), ship))
    prow = max(c.per_row.values()) if c.per_row else 0
    rows.append(_row("recrow", "Records a block row", "at most %d of %d" % (prow, B.REC_ROW_MAX), prow,
                     B.REC_ROW_MAX))
    rows.append(_row("pass", "Occluder pass", "at most %s of %s clocks" % (_fmt(c.wprice[0]), _fmt(B.OCC_PASS_MAX)),
                     c.wprice[0], B.OCC_PASS_MAX))
    nm = len(c.masks)
    if c.model.get("mband"):
        sl = B.band_slices(c.model)
        most = max(len(x) for x in sl) if sl else 0
        rows.append(_row("masks", "Masks", "%d in all; at most %d of 256 in a band (%d bands: %s)" % (
            nm, most, len(sl), ", ".join(str(len(x)) for x in sl)), most, 256))
        above.append({"key": "banded", "name": "masks banded", "spec": "130.52",
                      "detail": "a mask table a band of 16 block rows: %d masks in all, at most %d in a band" % (
                          nm, most)})
    else:
        rows.append(_row("masks", "Masks", "%d of 256 (%d as cut, %d merged, before the ghost dither)" % (
            nm, c.raw_masks, c.umasks), nm, 256))
    recut = getattr(c, "recut", None)
    if recut:
        above.append({"key": "recut", "name": "Real-pose re-cut", "spec": "130.49.5",
                      "detail": "over 256 masks at 4 ground units: cut again %s" % (
                          "at whole cells" if recut == "cell" else "in %d gu squares" % recut)})
    if getattr(c, "noshadow", False):
        above.append({"key": "noshadow", "name": "Shadows dropped", "spec": "130.47.5",
                      "detail": "over %s blocks with cast shadows: compiled again without them" % _fmt(B.BLK_MAX)})
    # THE PARTS
    sheets = B.sheets_of(c.cga)
    if sheets:
        for i, q in enumerate(sheets):
            rows.append(_row("sheet%d" % i, "Sheet %d" % i, "%s of %s bytes in RAM" % (
                _fmt(len(q)), _fmt(B.PARTMAX)), len(q), B.PARTMAX))
        above.append({"key": "sheets", "name": "Sheets", "spec": "130.30.12",
                      "detail": "the picture part cut into %d sheets of %d block rows (from rows %s), and a world "
                                "part" % (c.plan["k"], c.plan["n"], ", ".join(str(x["m0"]) for x in c.plan["sheets"]))})
    else:
        rows.append(_row("picture", "Picture part" if c.split else "The part", "%s of %s bytes in RAM" % (
            _fmt(len(c.cga)), _fmt(B.PARTMAX)), len(c.cga), B.PARTMAX))
    if c.split:
        rows.append(_row("world", "World part", "%s of %s bytes in RAM" % (_fmt(len(c.wcga)), _fmt(B.PARTMAX)),
                         len(c.wcga), B.PARTMAX))
        if not sheets:
            one = B.one_part_len(c.model, 4)
            above.append({"key": "two", "name": "Two parts", "spec": "130.30",
                          "detail": "a picture part and a world part, each its own segment (as one part it would be "
                                    "%s bytes, over %s)" % (_fmt(one), _fmt(B.PARTMAX))})
    stored = bytes(c.bstored or c.stored)
    lzb = B.packed_len(stored, "lzb")
    rows.append(_row("disk", "On the floppy", "%s bytes LZB (stored %s, %s in RAM)%s" % (
        _fmt(lzb), _fmt(len(stored)), _fmt(len(c.cga) * len(sheets or [0]) + len(c.wcga or b"")),
        "" if song is True else ", without its song (%s)" % (song if song else "no `music`")), lzb))
    if c.target:
        lz4 = B.check_budget(c)                 # (the game build's figure, after its song as there)
        cap = B.course_cap(c)
        rows.append(_row("budget", "Size budget", "LZ4 %s of %s for a %d s target (1.5x: %s; reported, never "
                         "refused)" % (_fmt(lz4), _fmt(B.budget(c.target)), c.target, _fmt(cap)), lz4,
                         B.budget(c.target)))
    # TIME
    if c.limit:
        t = "limit %d s" % c.limit
        if c.lroute:
            t = "route %.1f s, %s" % (c.lroute / float(B.SEC_STEPS), t)
        if c.target:
            t = "target %d s, %s" % (c.target, t)
        if c.medals and c.medals != (0, 0):
            t += ", gold %d s, silver %d s" % c.medals
        rows.append(_row("time", "Time", t))
    elif c.target:
        rows.append(_row("time", "Time", "target %d s" % c.target))
    near = [r["label"] for r in rows if r["near"]]
    summary = "%s records, %d masks, %s blocks; %s bytes in RAM, %s on the floppy%s%s" % (
        _fmt(ship), nm, _fmt(nb), _fmt(len(c.cga) * len(sheets or [0]) + len(c.wcga or b"")), _fmt(lzb),
        "; past: " + ", ".join(a["name"] for a in above) if above else "",
        "; near or over a bound: " + ", ".join(near) if near else "")
    return {"rows": rows, "above": above, "summary": summary}


SIDES = {(1, 0): "+x", (-1, 0): "-x", (0, 1): "+y", (0, -1): "-y"}


def _sg(v):
    return (v > 0) - (v < 0)


def shape_of(toks):
    """a shape statement's numbers: chute -> {"kind", "width", "ways": [(x, y, z or None)]}, pit -> {"kind",
    "at", "z", "radius", "depth", "hole"}, hump -> {"kind", "at", "z", "along", "n"}; None for anything else"""
    t, k = toks, toks[0] if toks else None
    try:
        if k == "chute":
            ways, i = [], 1
            while i < len(t):
                if t[i] == "way":
                    z = float(t[i + 3]) if i + 3 < len(t) and _num(t[i + 3]) else None
                    ways.append((int(t[i + 1]), int(t[i + 2]), z))
                    i += 4 if z is not None else 3
                else:
                    i += 1
            return {"kind": k, "width": int(t[1]), "ways": ways}
        if k == "pit":
            kw = {t[i]: t[i + 1] for i in range(4, len(t) - 1)}
            return {"kind": k, "at": (int(t[1]), int(t[2])), "z": float(t[3]), "radius": int(kw.get("radius", 2)),
                    "depth": int(kw.get("depth", 8)), "hole": int(kw.get("hole", 1))}
        if k == "hump":
            along, n = "x", 1
            if "along" in t:
                i = t.index("along")
                along, n = t[i + 1], int(t[i + 2])
            return {"kind": k, "at": (int(t[1]), int(t[2])), "z": float(t[3]) if len(t) > 3 and _num(t[3]) else 0,
                    "along": along, "n": n}
    except (ValueError, IndexError):
        return None
    return None


def _num(t):
    try:
        float(t)
        return True
    except ValueError:
        return False


def chute_route(ways):
    """the cells the autopilot steers through, a quarter and three quarters along each leg and the last way
    (never ON a corner: the tool lays it radial, and the autopilot cuts it as a player does)"""
    pts = []
    for (ax, ay, _), (bx, by, _) in zip(ways, ways[1:]):
        for f in (0.25, 0.75):
            q = (int(round(ax + (bx - ax) * f)), int(round(ay + (by - ay) * f)))
            if not pts or pts[-1] != q:
                pts.append(q)
    pts.append(tuple(ways[-1][:2]))
    return pts


def _roll(c, mat, at, v, route=None, secs=20.0, done=None):
    """one run: poke at AT with ground velocity V, steered by the autopilot along ROUTE (or no keys); ->
    (what happened, seconds, the cell it ended on, the top speed in tiles a second)"""
    p = B.Physics(c, play=True, mat=mat).poke(at[0], at[1], v[0], v[1])
    if route:
        p.route = [B._way_point(c, t) for t in route]
        p.wp = 0
    top, still = 0, 0
    for k in range(int(secs * B.STEP_HZ)):
        p.step(p.auto() if route else 0)
        cell = (p.gx >> 12, p.gy >> 12)
        sp = max(abs(p.gvx), abs(p.gvy))
        top = max(top, sp)
        if p.nfall:
            return "fell", k / B.STEP_HZ, cell, top
        if done and done(cell):
            return "through", k / B.STEP_HZ, cell, top
        still = still + 1 if sp < 8 and not p.air else 0
        if still > B.STEP_HZ:
            return "stopped", k / B.STEP_HZ, cell, top
    return "still rolling", secs, cell, top


def rides(c, toks):
    """SPEC.md 130.58.19: each ball over one shape, in words -> [{"ball", "test", "result", "words"}]"""
    sh = shape_of(toks)
    if not sh:
        return []
    tps = lambda v: v * B.STEP_HZ / 4096.0     # noqa: E731  (gu a step -> tiles a second)
    out = []
    for mat in (B.MAT_RUBBER, B.MAT_STEEL, B.MAT_GLASS):
        nm = B.MAT_NAMES[mat]
        if sh["kind"] == "chute":
            ws = sh["ways"]
            d = (_sg(ws[1][0] - ws[0][0]), _sg(ws[1][1] - ws[0][1]))
            end = ws[-1][:2]
            near = lambda cl: abs(cl[0] - end[0]) <= 1 and abs(cl[1] - end[1]) <= 1   # noqa: E731
            for test, v, route in (("steered along it", (B.VMAXG * d[0] // 2, B.VMAXG * d[1] // 2),
                                    chute_route(ws)),
                                   ("let go at the top", (B.VMAXG * d[0] // 2, B.VMAXG * d[1] // 2), None)):
                r, t, cl, top = _roll(c, mat, ws[0][:2], v, route, done=near)
                words = {"through": "reaches the far end in %.1f s" % t,
                         "fell": "falls off at %d, %d after %.1f s" % (cl[0], cl[1], t),
                         "stopped": "comes to rest at %d, %d after %.1f s" % (cl[0], cl[1], t),
                         "still rolling": "is still rolling after %.0f s (at %d, %d)" % (t, cl[0], cl[1])}[r]
                out.append({"ball": nm, "test": test, "result": r,
                            "words": "%s: %s, top speed %.1f tiles/s" % (test, words, tps(top))})
        elif sh["kind"] == "pit":
            x, y = sh["at"]
            rr = sh["radius"]
            for test, frac in (("round the lip at half speed", 2), ("round the lip at full speed", 1)):
                r, t, cl, top = _roll(c, mat, (x - rr, y), (0, B.VMAXG // frac), None, secs=10.0)
                words = {"fell": "drops into the hole after %.1f s" % t,
                         "stopped": "settles at %d, %d after %.1f s" % (cl[0], cl[1], t),
                         "still rolling": "is still circling after %.0f s" % t, "through": ""}[r]
                out.append({"ball": nm, "test": test, "result": r, "words": "%s: %s" % (test, words)})
        else:                                   # a hump: rolled across its axis at three speeds
            x, y = sh["at"]
            ax = (0, 1) if sh["along"] == "x" else (1, 0)      # (across the ridge)
            at = (x - 2 * ax[0], y - 2 * ax[1])
            over = lambda cl: (cl[0] - x) * ax[0] + (cl[1] - y) * ax[1] >= 1   # noqa: E731  (past its cells)
            for test, frac in (("rolled at it slowly", 4), ("at half speed", 2), ("at full speed", 1)):
                r, t, cl, top = _roll(c, mat, at, (B.VMAXG * ax[0] // frac, B.VMAXG * ax[1] // frac), None,
                                      secs=6.0, done=over)
                words = {"through": "gets over (%.1f s)" % t, "fell": "falls off at %d, %d" % cl,
                         "stopped": "stops at %d, %d" % cl, "still rolling": "rolls on"}[r]
                out.append({"ball": nm, "test": test, "result": r, "words": "%s: %s" % (test, words)})
    return out


def ride(path, line, name=None):
    t0 = time.time()
    with open(path, "r", encoding="ascii", newline="") as f:
        text = f.read()
    path = name or path
    lines = text.split("\n")
    toks = lines[line - 1].split("#")[0].split() if 0 < line <= len(lines) else []
    emit(stage="compile", what="laying the course to roll on")
    held = B.BLK_MAX
    B.BLK_MAX = 1 << 30
    try:
        c = B.compile_course(text, path, occluders=False)
    except B.CourseError as e:
        emit(stage="done", ok=False, error=str(e), secs=round(time.time() - t0, 2))
        return 1
    finally:
        B.BLK_MAX = held
    emit(stage="roll", what="rolling each ball")
    emit(stage="done", ok=True, line=line, rides=rides(c, toks), secs=round(time.time() - t0, 2))
    return 0


def main(argv):
    name = None
    if "--name" in argv:                        # the course's own path, for the messages (the text is a copy)
        i = argv.index("--name")
        name = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) >= 3 and argv[0] == "picture":
        return picture(argv[1], argv[2], name, "--gaps" in argv[3:], "--occ" in argv[3:])
    if len(argv) >= 3 and argv[0] == "ride":
        return ride(argv[1], int(argv[2]), name)
    if len(argv) >= 2 and argv[0] == "check":
        return check(argv[1], "--strict" in argv[2:], name, "--trap" in argv[2:])
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:                      # a crash is a result too: the window shows it
        emit(stage="done", ok=False, error="%s: %s" % (type(e).__name__, e))
        sys.exit(1)
