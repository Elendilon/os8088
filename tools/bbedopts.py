"""bbedopts.py - every clause a course statement may take, as data, for the builder's inspector (SPEC.md 130.58.36)

The Bounce Bonanza course builder (tools/bbedit.py) shows a control for EVERY option a statement has, written or
not: an optional clause the author has not typed is still a spinbox, a choice or a tick box, and setting it writes
the clause (clearing it takes it out again). This file is the table of those options - one row per clause word of
one statement kind, what kind of value it takes, its legal values or range, the default it starts at, its label
and a one-line hint - and the three pure functions the window calls: `options_for` (the rows for a statement),
`value` (a row's value as written, or None) and `apply` (the statement's tokens with a row set or cleared).
Nothing here imports Tk, so tests/unit/t_bbedit.py checks it on the host.

The see-saw's size and timer, the slope of a floor, a route point's list and the shape editor's tube, chute, pit
and hump keep their own sections in the inspector; their clauses are not repeated here (DEDICATED lists them, and
docs/plans/BONANZA-BUILDER-OPTIONS.md is the audit this table came from)."""

import os

import bbcourse as B

# the statements whose options have a dedicated inspector section of their own (and why), not rows here
DEDICATED = {
    ("floor", None): "Slope (flat / ramp) and Surface: _slope_rows, set_surface",
    ("wall", None): "Slope (flat / ramp) and Surface: _slope_rows, set_surface",
    ("tube", None): "the shape editor's tube form (bbedshape.py): kind, exit, speed, mouth height, pipe height",
    ("chute", None): "the shape editor (bbedshape.py): width, cross-section, depth, ways and lips",
    ("pit", None): "the shape editor (bbedshape.py): lip height, radius, depth, hole",
    ("hump", None): "the shape editor (bbedshape.py): dome or ridge, its run, open ends, base and height",
    ("seesaw", None): "_seesaw_rows: length, width, axis, tipped by weight or a timer, period, flat, seed",
    ("way", None): "_route_rows: the route listed, insert, earlier / later",
}


def _ga_names(kind):
    """the art a gate (KIND B.GT_KG) or a bridge (B.GT_KB) may name (`art <name>`: SPEC.md 130.41.12): the .bba
    files there drawn for it"""
    out = []
    try:
        names = sorted(f[:-4] for f in os.listdir(B.GT_ADIR) if f.endswith(".bba"))
    except OSError:
        return ()
    for n in names:
        try:
            B.ga_load(n, "<art>", kind)
            out.append(n)
        except B.CourseError:
            pass
    return tuple(out)


def _num(t, d=0.0):
    try:
        return float(t)
    except (TypeError, ValueError):
        return d


def _has(w):
    return lambda t: w in t[1:]


def O(w, t, label, hint="", **kw):
    """one option: W the clause word (None for a positional value at `pos`), T its type -
    num   a number (lo, hi, inc; d the default it is written with)
    choice one of `vals` (shown as radio buttons when there are few; `blank` names the state with no clause)
    flag  the bare word, on or off
    pair  two numbers (d "a b")
    name  a word matching `pattern`
    sides guard's `side` edges: any of +x -x +y -y (none ticked: the clause out, the floor's open edges)
    bare  one of `vals` written alone (gap's sw | se)
    mode  one of `modes`: (value, label, clauses [(word, default)], words it takes out)
    `at` where a new clause goes: None the end (before a trailing `hidden`), an index, or (word, k) k past that
    word; `need` a test of the statement's tokens for when the row applies; `req` no way to clear it; `skip`
    words between the clause word and its value (magnet's `face down <way>`)"""
    o = {"w": w, "t": t, "label": label, "hint": hint, "at": None, "need": None, "req": False, "skip": (),
         "vals": (), "blank": None, "lo": None, "hi": None, "inc": 1, "d": None, "pos": None, "pattern": None,
         "modes": ()}
    o.update(kw)
    o["n"] = {"num": 1, "choice": 1, "name": 1, "pair": 2}.get(t, 0)
    return o


CHANNELS = tuple(B.GT_CHANNELS)
DIRS4 = ("+x", "-x", "+y", "-y")

OPTIONS = {
    # -- ground ------------------------------------------------------------------------------------------------
    ("goal", None): [
        O("exit", "num", "Exit", "the pathway's exit, 0 - 3 (blank 0)", lo=0, hi=B.EXIT_MAX, d="1"),
        O("hidden", "flag", "Secret finish (hidden until found)"),
    ],
    ("water", None): [
        O("top", "num", "Water top", "units", lo=-8, hi=60, inc=0.5, req=True, d="4"),
        O("bed", "num", "Water bed", "units, over a climb under the top", lo=-8, hi=60, inc=0.5, req=True,
          d="0"),
        O("open", "flag", "Open: unsealed (no steel ball can reach it)", at=("bed", 2)),
    ],
    ("arch", None): [
        O(None, "choice", "Opens in its", "a water column's FRONT face, where the ball leaves", pos=3,
          vals=("+x", "+y"), req=True),
        O("guard", "flag", "A guard rail along the face's top"),
        O("height", "num", "Rail height", "units over the floor (blank 2)", lo=1.5, hi=3, inc=0.5, d="2",
          at=("guard", 1), need=_has("guard")),
    ],
    ("float", None): [
        O("thick", "num", "Slab thickness", "units, 0.25 - 3 (blank: faces hang 3 units)", lo=0.25, hi=3,
          inc=0.25, d="1"),
    ],
    ("gap", None): [
        O(None, "bare", "Gap band on", "which faces show the gap band", vals=("sw", "se"), blank="both faces"),
    ],
    ("guard", None): [
        O("side", "sides", "Rails on", "none ticked: every edge open to the void or a drop"),
        O("height", "num", "Rail height", "units over the floor (blank 2)", lo=1.5, hi=3, inc=0.5, d="2"),
    ],
    ("seesaw", None): [                             # (its size and timer are _seesaw_rows')
        O("rest", "choice", "At rest", "the end down while nothing tips it (- the -x / -y end)",
          vals=("-", "+"), blank="-", at=("pivot", 2)),
    ],
    ("archway", None): [
        O("along", "choice", "Runs along", req=True, vals=("x", "y")),
        O("under", "num", "Clearance", "units over the floor, 2 - 4 (blank 2)", lo=2, hi=4, inc=0.5, d="2.5"),
    ],
    # -- game --------------------------------------------------------------------------------------------------
    ("cup", None): [
        O("capture", "num", "Captures under", "speed, %d - %d (blank %d)" % (B.CAPTURE_LO, B.CAPTURE_HI, B.CAPTURE),
          lo=B.CAPTURE_LO, hi=B.CAPTURE_HI, inc=8, d=str(B.CAPTURE), at=3),
        O("exit", "num", "Exit", "the pathway's exit, 0 - 3 (blank 0)", lo=0, hi=B.EXIT_MAX, d="1"),
        O("hidden", "flag", "Secret finish (hidden until found)"),
    ],
    ("checkpoint", None): [
        O("ball", "choice", "Ball here", "a fall returns as this ball", vals=tuple(B.MAT_NAMES),
          blank="the ball it had"),
    ],
    ("clock", None): [
        O("frame", "choice", "Frame", vals=tuple(B.CLOCK_STYLES), blank="crystal", at=3),
        O("digits", "pair", "Digits moved", "dx dy, px from the frame's own place", lo=-64, hi=64, d="0 0"),
    ],
    ("spring", None): [
        O(None, "num", "Launch (gvz)", "upward speed, %d - %d" % (B.SPRING_LO, B.VZMAX), pos=3, lo=B.SPRING_LO,
          hi=B.VZMAX, inc=16, req=True),
    ],
    ("pad", None): [
        O(None, "choice", "Ball", pos=1, vals=tuple(B.MAT_NAMES), req=True),
    ],
    ("label", None): [
        O("ink", "num", "Ink", "0 - 3 (blank 3)", lo=0, hi=3, d="2"),
    ],
    ("way", None): [
        O("branch", "name", "Branch", "1 - 5 of A-Z 0-9; blank: the main route", pattern=r"^[A-Z0-9]{1,5}$",
          d="B"),
    ],
    # -- movers (SPEC.md 130.12.3.3, 130.43) -----------------------------------------------------------------
    ("prop", "windmill"): [
        O("period", "choice", "Turns every", "steps, a blade's turn", vals=tuple(map(str, B.WM_PERIODS)),
          blank="64"),
        O("closed", "pair", "Gate closed", "steps c0 c1 of the period, on pose boundaries (blank: 3/8 - 5/8)",
          lo=0, hi=255, d="24 40"),
        O("seed", "num", "Starts at", "step (staggers two)", lo=0, hi=255, d="0"),
    ],
    ("prop", "bumper"): [
        O("kick", "num", "Kick", "the least speed out, 1 - %d (blank %d)" % (B.VMAXG, B.KICK_K), lo=1,
          hi=B.VMAXG, inc=16, d=str(B.KICK_K)),
    ],
    ("prop", "platform"): [
        O(None, "num", "Rises", "units, 1 - %d" % B.PL_LMAX, pos=4, lo=1, hi=B.PL_LMAX, req=True),
        O("period", "choice", "Round trip", "steps", vals=tuple(map(str, B.PL_PERIODS)), blank="256"),
        O("dwell", "num", "Wait at each end", "steps, under a quarter period (blank an eighth)", lo=0, hi=63,
          d="16"),
        O("seed", "num", "Starts at", "step (staggers two)", lo=0, hi=255, d="0"),
    ],
    ("prop", "turntable"): [
        O("size", "choice", "Size", "an N x N table", vals=("2", "3"), req=True),
        O("fill", "name", "Fill", "rows from the back, o a floor . a gap, half of them floors",
          pattern=r"^[o./]+$", req=True),
        O("quarter", "choice", "Quarter turn", "steps", vals=tuple(map(str, B.TT_QUARTERS)),
          blank=str(B.TT_QDEF)),
        O("turn", "choice", "Turns", vals=("cw", "ccw"), blank="cw"),
        O("seed", "num", "Starts at", "step, under four quarters", lo=0, hi=255, d="0"),
        O("warn", "num", "Warns", "steps before a turn (0 none; blank %d)" % B.TT_WDEF, lo=0, hi=63,
          d=str(B.TT_WDEF)),
    ],
    ("prop", "bridge"): [
        O(None, "mode", "Opened by", modes=(
            ("channel", "a channel", [("channel", "ring")], ("period", "on", "seed")),
            ("timer", "a timer", [("period", "128"), ("on", "64")], ("channel", "art")))),
        O("channel", "choice", "Channel", "its plate or key", vals=CHANNELS, req=True, need=_has("channel")),
        O("period", "choice", "Period", "steps", vals=tuple(map(str, B.GT_PERIODS)), req=True,
          need=_has("period")),
        O("on", "num", "Down for", "steps of the period", lo=1, hi=255, req=True, need=_has("period")),
        O("seed", "num", "Starts at", "step (a rect's cells follow one a step)", lo=0, hi=255, d="0",
          need=_has("period")),
        O("style", "choice", "Style", vals=tuple(B.GT_STYLES), blank="the course's"),
        O("art", "choice", "Designer art", "gates/<name>.bba; instead of a style", vals=_ga_names(B.GT_KB),
          blank="none", need=lambda t: "period" not in t),
    ],
    # -- launch --------------------------------------------------------------------------------------------------
    ("prop", "boost"): [
        O("face", "choice", "Pushes", vals=DIRS4, req=True),
        O("strength", "num", "Strength", "1 - %d (blank %d)" % (B.BP_SMAX, B.BP_SDEF), lo=1, hi=B.BP_SMAX,
          d=str(B.BP_SDEF)),
        O("flat", "flag", "Same push for every ball (not weighted)"),
    ],
    ("prop", "magnet"): [
        O("face", "choice", "Field toward", "its field's way (a hanging one: its arm's)", vals=DIRS4, req=True,
          skip=("down",)),
        O("down", "flag", "Hangs over one cell, lifting airborne steel", at=("face", 1)),
        O("range", "num", "Range", "cells, 1 - %d (a hanging one: 1)" % B.MG_RMAX, lo=1, hi=B.MG_RMAX, d="2",
          need=lambda t: "down" not in t),
        O("strength", "num", "Strength", "1 - %d" % B.MG_SMAX, lo=1, hi=B.MG_SMAX, d="48"),
    ],
    ("prop", "blower"): [
        O("face", "choice", "Blows", "up: an updraft", vals=tuple(B.WD_DIRS), req=True),
        O("strength", "num", "Strength", "1 - 127 (blank %d)" % B.WD_SDEF, lo=1, hi=127, d=str(B.WD_SDEF)),
        O("top", "num", "Updraft top", "units over its floor, 1 - 24", lo=1, hi=24, req=True,
          need=lambda t: _clause(t, "face", 1) == ["up"]),
        O("lift", "flag", "Lifts a grounded ball", need=lambda t: _clause(t, "face", 1) == ["up"]),
        O("gust", "pair", "Gusts", "steps on, off: on + off a power of two, 32 - 1024", lo=1, hi=1023,
          d="32 32"),
        O("seed", "num", "Gust starts at", "step", lo=0, hi=1023, d="0", need=_has("gust")),
        O("flag", "flag", "A pennant instead of the fan"),
    ],
    # -- hazards and pickups -----------------------------------------------------------------------------------
    ("prop", "popspikes"): [
        O("period", "choice", "Period", "steps", vals=tuple(map(str, B.SP_PERIODS)), req=True),
        O("on", "num", "Up for", "steps of the period", lo=1, hi=255, req=True),
        O("seed", "num", "Starts at", "step (staggers two)", lo=0, hi=255, d="0"),
    ],
    ("prop", "crack"): [
        O("hole", "choice", "Hole", "how much of the top breaks", vals=tuple(B.CRACK_HOLES), blank="small", at=4),
    ],
    ("prop", "gate"): [
        O("channel", "choice", "Channel", "its plate or key", vals=CHANNELS, req=True),
        O("along", "choice", "Path runs along", "its bars stand across it", vals=("x", "y"), blank="x"),
        O("style", "choice", "Style", vals=tuple(B.GT_STYLES), blank="the course's"),
        O("art", "choice", "Designer art", "gates/<name>.bba; instead of a style", vals=_ga_names(B.GT_KG),
          blank="none"),
    ],
    ("prop", "plate"): [O("channel", "choice", "Channel", "opens its gates while pressed", vals=CHANNELS,
                          req=True)],
    ("prop", "key"): [O("channel", "choice", "Channel", "opens its gates for good", vals=CHANNELS, req=True)],
    ("prop", "speed"): [
        O("for", "num", "Lasts", "seconds (blank 10)", lo=0.25, hi=18, inc=0.25, d="10"),
        O("overwrite", "flag", "Ends the other timed effect"),
        O("respawn", "flag", "Comes back when its effect ends"),
    ],
    ("prop", "life"): [O("once", "flag", "Once: taken for good (one a course)")],
}
OPTIONS[("prop", "jump")] = OPTIONS[("prop", "speed")]

# what the grammar accepts, kind by kind, that the builder sets in place of typing it: the audit's list
# (docs/plans/BONANZA-BUILDER-OPTIONS.md), held against OPTIONS + DEDICATED by tests/unit/t_bbedit.py
GRAMMAR = {
    ("goal", None): ("exit", "hidden"), ("water", None): ("top", "bed", "open"),
    ("arch", None): ("#3", "guard", "height"), ("float", None): ("thick",), ("gap", None): ("sw|se",),
    ("guard", None): ("side", "height"), ("archway", None): ("along", "under"), ("seesaw", None): ("rest",),
    ("cup", None): ("capture", "exit", "hidden"), ("checkpoint", None): ("ball",),
    ("clock", None): ("frame", "digits"), ("spring", None): ("#3",), ("pad", None): ("#1",),
    ("label", None): ("ink",), ("way", None): ("branch",),
    ("prop", "windmill"): ("period", "closed", "seed"), ("prop", "bumper"): ("kick",),
    ("prop", "platform"): ("#4", "period", "dwell", "seed"),
    ("prop", "turntable"): ("size", "fill", "quarter", "turn", "seed", "warn"),
    ("prop", "bridge"): ("channel|timer", "channel", "period", "on", "seed", "style", "art"),
    ("prop", "boost"): ("face", "strength", "flat"), ("prop", "magnet"): ("face", "down", "range", "strength"),
    ("prop", "blower"): ("face", "strength", "top", "lift", "gust", "seed", "flag"),
    ("prop", "popspikes"): ("period", "on", "seed"), ("prop", "crack"): ("hole",),
    ("prop", "gate"): ("channel", "along", "style", "art"), ("prop", "plate"): ("channel",),
    ("prop", "key"): ("channel",), ("prop", "speed"): ("for", "overwrite", "respawn"),
    ("prop", "jump"): ("for", "overwrite", "respawn"), ("prop", "life"): ("once",),
}


def key_of(toks):
    if not toks:
        return None
    if toks[0] == "prop" and len(toks) > 1:
        return ("prop", toks[1])
    return (toks[0], None)


def options_for(toks):
    """the rows that apply to a statement now (a row's `need` met)"""
    return [o for o in OPTIONS.get(key_of(toks), []) if (o["need"] is None or o["need"](toks))
            and not (o["t"] == "choice" and not o["vals"])]    # (no art drawn for a bridge yet: no row)


def covered_words(toks):
    """the clause words this table answers for, so the inspector's generic rows leave them alone"""
    return {o["w"] for o in OPTIONS.get(key_of(toks), []) if o["w"]} | (
        {w for o in OPTIONS.get(key_of(toks), []) for m in o["modes"] for w, _d in m[2]})


def option_id(o):
    """the GRAMMAR spelling of a row: its word, `#N` a positional value, `a|b` a bare choice or a mode"""
    if o["t"] == "mode":
        return "|".join(m[0] for m in o["modes"])
    if o["t"] == "bare":
        return "|".join(o["vals"])
    return o["w"] if o["w"] else "#%d" % o["pos"]


def _clause(toks, w, n, skip=()):
    """the N values after clause word W (past any SKIP words), or None when W is not written"""
    if w not in toks[1:]:
        return None
    j = toks.index(w, 1) + 1
    while j < len(toks) and toks[j] in skip:
        j += 1
    return list(toks[j:j + n]) if j + n <= len(toks) else None


def _sides(toks):
    if "side" not in toks[1:]:
        return set()
    j, out = toks.index("side", 1) + 1, set()
    while j < len(toks) and toks[j] in DIRS4 + ("all",):
        out |= set(DIRS4) if toks[j] == "all" else {toks[j]}
        j += 1
    return out


def value(toks, o):
    """a row's value as the statement writes it: a string (two joined by a space for a pair), True / False for a
    flag, a set for sides; None when the clause is not written"""
    t = o["t"]
    if o["w"] is None and t not in ("bare", "mode"):
        return toks[o["pos"]] if o["pos"] < len(toks) else None
    if t == "flag":
        return o["w"] in toks[1:]
    if t == "bare":
        return next((x for x in reversed(toks[1:]) if x in o["vals"]), None)
    if t == "sides":
        return _sides(toks)
    if t == "mode":
        return next((m[0] for m in o["modes"] if any(w in toks[1:] for w, _d in m[2])), o["modes"][0][0])
    v = _clause(toks, o["w"], o["n"], o["skip"])
    return " ".join(v) if v is not None else None


def _insert_at(toks, o):
    at = o["at"]
    if isinstance(at, int):
        return min(at, len(toks))
    if isinstance(at, tuple) and at[0] in toks[1:]:
        return min(toks.index(at[0], 1) + at[1], len(toks))
    return len(toks) - 1 if toks and toks[-1] == "hidden" else len(toks)


def _drop(toks, w, n):
    """TOKS without clause word W and its N values"""
    if w not in toks[1:]:
        return list(toks)
    i = toks.index(w, 1)
    return toks[:i] + toks[i + 1 + n:]


def apply(toks, o, val):
    """TOKS with row O set to VAL (a string, True / False, a set of sides); None, "" or False clears an
    optional clause. -> the new token list (FIX then keeps what depends on it legal)"""
    t = list(toks)
    k = o["t"]
    if isinstance(val, str):
        val = val.strip()
    if o["w"] is None and k not in ("bare", "mode"):
        if val:
            t[o["pos"]] = val
        return _fix(t, o)
    if k == "flag":
        t = [t[0]] + [x for x in t[1:] if x != o["w"]]
        if val:
            i = _insert_at(t, o)
            t[i:i] = [o["w"]]
        return _fix(t, o)
    if k == "bare":
        t = [t[0]] + [x for x in t[1:] if x not in o["vals"]]
        if val:
            i = _insert_at(t, o)
            t[i:i] = [val]
        return _fix(t, o)
    if k == "sides":
        if "side" in t[1:]:
            i = t.index("side", 1)
            j = i + 1
            while j < len(t) and t[j] in DIRS4 + ("all",):
                j += 1
            del t[i:j]
        if val:
            i = _insert_at(t, o)
            t[i:i] = ["side"] + [d for d in DIRS4 if d in val]
        return _fix(t, o)
    if k == "mode":
        for m in o["modes"]:
            for w, d in m[2]:
                t = _drop(t, w, len(d.split()))
        m = next(m for m in o["modes"] if m[0] == val)
        for w in m[3]:
            t = _drop(t, w, 1)
        for w, d in m[2]:
            i = _insert_at(t, o)
            t[i:i] = [w] + d.split()
        return _fix(t, o)
    vals = val.split() if val else []
    if vals and len(vals) != o["n"]:
        return list(toks)
    if o["w"] in t[1:]:
        i = t.index(o["w"], 1)
        j = i + 1
        while j < len(t) and t[j] in o["skip"]:
            j += 1
        if vals:
            t[j:j + o["n"]] = vals
        elif not o["req"]:
            del t[j:j + o["n"]]
            del t[i]
    elif vals:
        i = _insert_at(t, o)
        t[i:i] = [o["w"]] + vals
    return _fix(t, o)


TT_FILL = {"2": "oo/..", "3": "oo./.o./.oo"}       # the turntable a size starts with (half filled, it switches)


def _fix(t, o):
    """what an edit to row O makes illegal beside it, put right: the clauses that belong to another form"""
    kk = key_of(t)
    w = o["w"]
    if kk == ("prop", "blower"):
        up = _clause(t, "face", 1) == ["up"]
        if up and "top" not in t:
            t += ["top", "4"]
        if not up:
            t = [x for x in _drop(t, "top", 1) if x != "lift"]
        if "gust" not in t:
            t = _drop(t, "seed", 1)
    elif kk == ("prop", "magnet") and "down" in t:
        t = _drop(t, "range", 1)
    elif kk == ("arch", None) and "guard" not in t:
        t = _drop(t, "height", 1)
    elif kk == ("prop", "turntable") and w == "size":
        f = _clause(t, "fill", 1)
        n = int(t[t.index("size") + 1])
        if f is None or len(f[0].replace("/", "")) != n * n:
            t = _drop(t, "fill", 1)
            i = t.index("size") + 2
            t[i:i] = ["fill", TT_FILL[str(n)]]
    elif kk == ("prop", "turntable") and w == "quarter":     # (its seed is under four quarters, its warning one)
        q = int(_num((_clause(t, "quarter", 1) or [B.TT_QDEF])[0], B.TT_QDEF))
        for cw, lim in (("seed", 4 * q), ("warn", q)):
            c = _clause(t, cw, 1)
            if c and int(_num(c[0])) >= lim:
                t = _drop(t, cw, 1)
    elif kk in (("prop", "gate"), ("prop", "bridge")) and w in ("style", "art") and w in t:
        t = _drop(t, "art" if w == "style" else "style", 1)
    if w == "period" and "period" in t:             # a shorter period: what no longer fits under it goes
        P = int(_num(t[t.index("period") + 1], 256))
        for cw in ("seed", "dwell"):
            c = _clause(t, cw, 1)
            if c and (int(_num(c[0])) >= (P // 4 if cw == "dwell" else P)):
                t = _drop(t, cw, 1)
        c = _clause(t, "on", 1)
        if c and int(_num(c[0])) >= P:
            t[t.index("on") + 1] = str(P // 2)
        if kk == ("prop", "windmill") and "closed" in t:
            t = _drop(t, "closed", 2)
    return t


def statement_error(code):
    """the compiler's refusal of one statement on its own (SPEC.md 130's grammar), or None: what the tests hold a
    row's default to"""
    try:
        B._parse_text(code)
    except B.CourseError as e:
        if "no 'course' statement" in str(e):
            return None
        return str(e)
    return None
