#!/usr/bin/env python3
"""bbedproj - THE COURSE BUILDER'S MODEL (SPEC.md 130.55.2, 130.55.3).

    python3 tools/bbedproj.py check COURSE.bbc [--strict] [--json]
    python3 tools/bbedproj.py show  COURSE.bbc [--json]          # the statements, their lines and kinds
    python3 tools/bbedproj.py add   COURSE.bbc 'prop bumper 14 19' [--after LINE]
    python3 tools/bbedproj.py set   COURSE.bbc LINE 'floor rect 6 9 11 14 flat 16'
    python3 tools/bbedproj.py move  COURSE.bbc LINE DX DY
    python3 tools/bbedproj.py remove COURSE.bbc LINE

A `.bbc` course is its TEXT. Every edit rewrites only the lines it is about:
a changed statement keeps its indentation and its trailing comment, a new one
is inserted after the last statement of its kind, and every other byte -
comments, blank lines, order, line endings - is what was read. tools/bbcourse.py
stays the only judge of a course: this module reads statements with its
tokenizer and asks its parser, and never decides what is legal itself.

Nothing here needs Tk; tools/bbedit.py (the window) is a view of a Document
and does every edit through its methods, so a script or a test can do
anything the window can.
"""

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bbcourse as B  # noqa: E402

# The statements whose first operand is a SHAPE (SPEC.md 130.10.3, 130.24.4).
SHAPED = ("floor", "wall", "goal", "hole", "surface", "float", "guard", "water", "noocclude", "archway")
MATERIALS = ("rubber", "steel", "glass")
# prop kinds that take a rectangle, not a cell (SPEC.md 130.38, 130.41)
RECT_PROPS = ("spikes", "membrane", "bridge")


class EditError(Exception):
    pass


# ----------------------------------------------------------------------------
# lines: indent, code, comment
# ----------------------------------------------------------------------------

def split_line(line):
    """-> (indent, code, comment): the comment from the first '#' outside a
    quoted string (with the spaces before it), the code without trailing
    spaces. Joined back they are the line."""
    n = len(line)
    i = 0
    while i < n and line[i] in " \t":
        i += 1
    indent = line[:i]
    j = i
    inq = False
    while j < n:
        c = line[j]
        if c == '"':
            inq = not inq
        elif c == "#" and not inq:
            break
        j += 1
    code = line[i:j]
    stripped = code.rstrip(" \t\r")
    comment = code[len(stripped):] + line[j:]
    return indent, stripped, comment


def tokens(code):
    """the statement's tokens as written: words and "quoted strings" (with
    their quotes), via bbcourse's own tokenizer"""
    return [('"%s"' % v) if k == '"' else v for k, v in B._tokens(code, "<line>")]


def join_tokens(toks):
    return " ".join(toks)


# ----------------------------------------------------------------------------
# coordinates: which tokens of a statement are world positions
# ----------------------------------------------------------------------------

def _isnum(t):
    try:
        float(t)
        return True
    except ValueError:
        return False


def coord_slots(toks):
    """-> [(index, axis)], axis 'x' or 'y' (a world cell) or 'a' / 's' (the
    screen axes of `band` and `box`: a = wx - wy, s = wx + wy). A statement
    with none (course, width, music, ...) answers []."""
    if not toks:
        return []
    st = toks[0]
    out = []

    def pair(i):
        if i + 1 < len(toks) and _isnum(toks[i]) and _isnum(toks[i + 1]):
            out.extend([(i, "x"), (i + 1, "y")])

    def shape(i):
        if i + 1 < len(toks) and toks[i] in ("half", "quarter"):     # `half right tile ...` (130.24.4)
            i += 2
        if i >= len(toks):
            return i
        k = toks[i]
        if k == "tile":
            pair(i + 1)
            return i + 3
        if k == "rect":
            pair(i + 1)
            pair(i + 3)
            return i + 5
        if k in ("band", "box"):
            for j, ax in zip(range(i + 1, i + 5), "aass"):
                if j < len(toks) and _isnum(toks[j]):
                    out.append((j, ax))
            return i + 5
        return i

    if st in SHAPED:
        i = shape(2 if st == "surface" else 1)
        while i < len(toks):                # clauses: a ramp's positions run along its axis
            if toks[i] in ("always", "ripple") and i + 2 < len(toks):     # water's ripple cells
                pair(i + 1)
                i += 3
            elif toks[i] == "ramp" and i + 3 < len(toks):
                ax = {"x": "x", "y": "y", "s": "s"}.get(toks[i + 1])
                if ax:
                    out.extend([(i + 2, ax), (i + 3, ax)])
                i += 4
            else:
                i += 1
    elif st == "prop" and len(toks) > 2:
        if toks[1] in RECT_PROPS and len(toks) > 5 and all(_isnum(t) for t in toks[2:6]):
            pair(2)
            pair(4)
        else:
            pair(2)
        for i, t in enumerate(toks):
            if t == "region" and i + 4 < len(toks):
                pair(i + 1)
                pair(i + 3)
    elif st in ("start", "checkpoint", "cup", "clock", "spring", "hump", "arch", "lives", "pit"):
        pair(1)
    elif st == "way" and len(toks) >= 3:
        pair(1)
    elif st == "pad":
        pair(2 if toks[1:2] and toks[1] in MATERIALS else 3)
    elif st == "seesaw":
        pair(1)
        pair(3)
    elif st == "tube":
        pair(2)
        pair(4)
        for i, t in enumerate(toks):
            if t == "via":
                pair(i + 1)
    elif st == "chute":
        for i, t in enumerate(toks):
            if t == "way":
                pair(i + 1)
    return out


def _shift(tok, d):
    if "." in tok:
        v = float(tok) + d
        return ("%g" % v)
    return str(int(tok) + d)


# ----------------------------------------------------------------------------
# the document
# ----------------------------------------------------------------------------

class Statement(object):
    __slots__ = ("line", "indent", "code", "comment", "toks")

    def __init__(self, line, raw):
        self.line = line                    # 1-based, as bbcourse reports lines
        self.indent, self.code, self.comment = split_line(raw)
        self.toks = tokens(self.code) if self.code else []

    @property
    def kind(self):
        return self.toks[0] if self.toks else None

    @property
    def subkind(self):
        """'prop windmill', 'surface ice', 'tube launch', ... or the kind"""
        if self.kind in ("prop", "surface", "tube") and len(self.toks) > 1:
            return "%s %s" % (self.kind, self.toks[1])
        return self.kind

    def text(self):
        return self.indent + self.code + self.comment


def file_stamp(path):
    try:
        st = os.stat(path)
        with open(path, "rb") as f:
            h = hashlib.sha1(f.read()).hexdigest()
        return (st.st_size, h)
    except OSError:
        return None


class Document(object):
    """one course: its lines, undo and redo, and the file it came from"""

    UNDO_MAX = 500

    def __init__(self, text="", path=None):
        self.path = path
        self.eol = "\r\n" if "\r\n" in text else "\n"
        self.final_eol = text.endswith("\n")
        body = text[:-len(self.eol)] if self.final_eol and text.endswith(self.eol) else text
        self.lines = body.split(self.eol) if body else []
        self.undo_stack = []
        self.redo_stack = []
        self.stamp = None
        self.saved_text = text
        self.listeners = []
        self._analysis = None

    # -- files --------------------------------------------------------------
    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="ascii", newline="") as f:
            text = f.read()
        d = cls(text, path)
        d.stamp = file_stamp(path)
        return d

    def text(self):
        t = self.eol.join(self.lines)
        return t + self.eol if self.final_eol else t

    def changed_on_disk(self):
        """True when the file is not what was loaded or last saved (SPEC.md 130.55.3)"""
        return self.path is not None and self.stamp is not None and file_stamp(self.path) != self.stamp

    def save(self, path=None, force=False):
        path = path or self.path
        if path is None:
            raise EditError("no file to save to")
        if not force and path == self.path and self.changed_on_disk():
            raise EditError("%s changed on disk since it was opened; save again to overwrite it" % path)
        with open(path, "w", encoding="ascii", newline="") as f:
            f.write(self.text())
        self.path = path
        self.stamp = file_stamp(path)
        self.saved_text = self.text()
        self._notify("save")

    @property
    def dirty(self):
        return self.text() != self.saved_text

    # -- reading ------------------------------------------------------------
    def statements(self):
        out = []
        for i, raw in enumerate(self.lines, 1):
            s = Statement(i, raw)
            if s.toks:
                out.append(s)
        return out

    def statement(self, line):
        if not 1 <= line <= len(self.lines):
            raise EditError("there is no line %d" % line)
        s = Statement(line, self.lines[line - 1])
        if not s.toks:
            raise EditError("line %d is not a statement" % line)
        return s

    def analysis(self):
        """the course as bbcourse reads it, cached until the next edit"""
        if self._analysis is None:
            self._analysis = analyse(self.text(), self.path or "<course>")
        return self._analysis

    # -- editing (every edit goes through _commit) ----------------------------
    def _commit(self, label, newlines):
        if newlines == self.lines:
            return False
        self.undo_stack.append((label, self.lines))
        del self.undo_stack[:-self.UNDO_MAX]
        self.redo_stack = []
        self.lines = newlines
        self._analysis = None
        self._notify(label)
        return True

    def undo(self):
        if not self.undo_stack:
            return None
        label, lines = self.undo_stack.pop()
        self.redo_stack.append((label, self.lines))
        self.lines = lines
        self._analysis = None
        self._notify("undo " + label)
        return label

    def redo(self):
        if not self.redo_stack:
            return None
        label, lines = self.redo_stack.pop()
        self.undo_stack.append((label, self.lines))
        self.lines = lines
        self._analysis = None
        self._notify("redo " + label)
        return label

    def _notify(self, what):
        for fn in list(self.listeners):
            fn(what)

    def set_statement(self, line, code, label=None):
        """replace line LINE's statement with CODE, keeping its indentation and
        comment (the comment keeps its column when the new code fits)"""
        s = self.statement(line)
        code = code.strip()
        if not code:
            raise EditError("an empty statement; use remove")
        comment = s.comment
        if comment.strip():
            col = len(s.indent) + len(s.code) + (len(comment) - len(comment.lstrip(" \t")))
            pad = max(1, col - len(s.indent) - len(code))
            comment = " " * pad + comment.lstrip(" \t")
        new = list(self.lines)
        new[line - 1] = s.indent + code + comment
        return self._commit(label or "edit line %d" % line, new)

    def set_many(self, codes, label=None):
        """replace several statements in ONE edit (one undo step): {line: code}"""
        new = list(self.lines)
        for line, code in codes.items():
            st = self.statement(line)
            comment = st.comment
            if comment.strip():
                col = len(st.indent) + len(st.code) + (len(comment) - len(comment.lstrip(" \t")))
                comment = " " * max(1, col - len(st.indent) - len(code)) + comment.lstrip(" \t")
            new[line - 1] = st.indent + code.strip() + comment
        return self._commit(label or "edit %d lines" % len(codes), new)

    def moved_code(self, line, dx, dy):
        """line LINE's statement moved by (DX, DY), as code (no edit)"""
        st = self.statement(line)
        slots = coord_slots(st.toks)
        if not slots:
            raise EditError("line %d (%s) has no position to move" % (line, st.kind))
        toks = list(st.toks)
        d = {"x": dx, "y": dy, "a": dx - dy, "s": dx + dy}
        for i, ax in slots:
            toks[i] = _shift(toks[i], d[ax])
        return join_tokens(toks)

    def move_many(self, lines, dx, dy, label=None):
        """move several statements in ONE edit"""
        return self.set_many({ln: self.moved_code(ln, dx, dy) for ln in lines}, label or "move")

    def set_tokens(self, line, toks, label=None):
        return self.set_statement(line, join_tokens(toks), label)

    def insert(self, code, after=None, label=None):
        """add statement CODE after line AFTER (default: after the last
        statement of its kind, else at the end). -> its line number"""
        code = code.strip()
        kind = code.split()[0] if code else None
        if not kind:
            raise EditError("an empty statement")
        if after is None:
            same = [s.line for s in self.statements() if s.kind == kind]
            after = same[-1] if same else len(self.lines)
            while after > 0 and after == len(self.lines) and not self.lines[after - 1].strip():
                after -= 1
        new = list(self.lines)
        new.insert(after, code)
        self._commit(label or "add %s" % kind, new)
        return after + 1

    def auto_uses(self):
        """add the family a refusal names (`uses NAME`, SPEC.md 130.25.6.4) to the course's `uses` line, as
        often as the refusals name one; part of the edit that needed it (one undo step). -> names added"""
        import re
        added = []
        for _ in range(8):
            err = analyse(self.text(), self.path or "<course>")["error"] or ""
            m = re.search(r"`uses (\w+)`", err)
            if not m or m.group(1) in added:
                break
            fam = m.group(1)
            us = [st for st in self.statements() if st.kind == "uses"]
            new = list(self.lines)
            if us:
                st = us[0]
                new[st.line - 1] = st.indent + join_tokens(st.toks + [fam]) + st.comment
            else:
                anchor = [st.line for st in self.statements() if st.kind in ("ball", "width", "course")]
                new.insert(anchor[-1] if anchor else 0, "uses %s" % fam)
            self.lines = new                # (folded into the edit that needed it: no undo step of its own)
            self._analysis = None
            added.append(fam)
        if added:
            self._notify("uses " + " ".join(added))
        return added

    def remove(self, line, label=None):
        self.statement(line)
        new = list(self.lines)
        del new[line - 1]
        return self._commit(label or "remove line %d" % line, new)

    def move(self, line, dx, dy, label=None):
        """shift every world position of line LINE's statement by (DX, DY)
        cells (the screen axes of band and box by dx - dy and dx + dy)"""
        s = self.statement(line)
        slots = coord_slots(s.toks)
        if not slots:
            raise EditError("line %d (%s) has no position to move" % (line, s.kind))
        toks = list(s.toks)
        d = {"x": dx, "y": dy, "a": dx - dy, "s": dx + dy}
        for i, ax in slots:
            toks[i] = _shift(toks[i], d[ax])
        return self.set_tokens(line, toks, label or "move %s" % s.subkind)

    def set_word(self, line, index, value, label=None):
        """set token INDEX of line LINE (append when INDEX is its length)"""
        s = self.statement(line)
        toks = list(s.toks)
        if index == len(toks):
            toks.append(str(value))
        else:
            toks[index] = str(value)
        return self.set_tokens(line, toks, label)

    def set_clause(self, line, word, values, label=None):
        """set (or add) the clause WORD v1 v2 ... of line LINE; VALUES None
        removes it. A clause is the word and the len(VALUES) tokens after it"""
        s = self.statement(line)
        toks = list(s.toks)
        n = None
        if word in toks[1:]:
            i = toks.index(word, 1)
            n = i
            j = i + 1
            while j < len(toks) and (_isnum(toks[j]) or j - i <= (len(values) if values else 0)):
                if values is not None and j - i > len(values):
                    break
                j += 1
            del toks[i:j]
        if values is not None:
            ins = [word] + [str(v) for v in values]
            pos = n if n is not None else len(toks)
            toks[pos:pos] = ins
        return self.set_tokens(line, toks, label)

    def set_flag(self, line, word, on, label=None):
        """a trailing bare word (`hidden`, `open`, ...) on or off"""
        s = self.statement(line)
        toks = [t for t in s.toks if t != word]
        if on:
            toks.append(word)
        return self.set_tokens(line, toks, label)


# ----------------------------------------------------------------------------
# analysis: what the window draws (no compile: milliseconds)
# ----------------------------------------------------------------------------

KIND_NAMES = {B.KIND_FLOOR: "floor", B.KIND_WALL: "wall", B.KIND_GOAL: "goal", B.KIND_FIELD: "field"}


def _rec_height(r):
    """a record's centre height, half units"""
    try:
        return r.corner(0.5, 0.5)
    except Exception:
        return getattr(r, "z0", 0)


def analyse(text, fname="<course>"):
    """-> {ok, error, error_line, src, cells: {(wx, wy): {kind, h, hmin, hmax,
    slope, surf, line, split}}, items: [{what, kind, at, cells, line}], zbase}
    The course's tiles as bbcourse lays them; heights are in UNITS as written.
    A course that does not parse returns ok False and the message; one that
    parses but whose tiles are refused returns the src and no cells."""
    out = {"ok": False, "error": None, "error_line": None, "src": None, "cells": {}, "items": [], "zbase": 0}
    try:
        src = B.parse(text, fname)
    except B.CourseError as e:
        out["error"], out["error_line"] = str(e), _line_of(str(e))
        return out
    out["src"] = src
    zb = src.zbase
    out["zbase"] = zb
    try:
        tiles = B.build_tiles(src)
    except B.CourseError as e:
        out["error"], out["error_line"] = str(e), _line_of(str(e))
        tiles = {}
    except Exception as e:                  # a half-made statement the tool did not expect
        out["error"] = "%s: %s" % (type(e).__name__, e)
        tiles = {}
    if tiles and not out["error"]:
        try:                                # the props' own refusals (a family not named, a tube's body ...)
            B.build_props(src, tiles, fname)
        except B.CourseError as e:
            out["error"], out["error_line"] = str(e), _line_of(str(e))
        except Exception as e:
            out["error"] = "%s: %s" % (type(e).__name__, e)
    for cell, t in tiles.items():
        recs = B.tile_recs(t)
        if not recs:
            continue
        top = max(recs, key=_rec_height)
        if isinstance(top, B.FieldTile):
            hmin, hmax = top.hmin / 32.0 + zb, top.hmax / 32.0 + zb   # quarter px: 32 a unit
            h = (hmin + hmax) / 2.0
            slope = (0, 0)
        else:
            h = _rec_height(top) / 2.0 + zb
            hs = [top.corner(dx, dy) / 2.0 + zb for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1))]
            hmin, hmax = min(hs), max(hs)
            slope = (getattr(top, "sx", 0), getattr(top, "sy", 0))
        out["cells"][cell] = {
            "kind": KIND_NAMES.get(top.kind, "floor"), "h": h, "hmin": hmin, "hmax": hmax, "slope": slope,
            "surf": B.SURFACES[t.surf] if 0 <= t.surf < len(B.SURFACES) else "normal",
            "line": getattr(top, "line", None) or t.line, "split": isinstance(t, B.Split),
            "water": getattr(top, "wbed", None) is not None, "guard": getattr(top, "guard", None) is not None}
    items = out["items"]

    def item(what, kind, at, line, cells=None, **kw):
        d = {"what": what, "kind": kind, "at": tuple(at) if at else None, "line": line,
             "cells": sorted(cells) if cells else ([tuple(at)] if at else [])}
        d.update(kw)
        items.append(d)

    if src.start:
        item("Start", "start", src.start[0], src.start[1])
    for (at, ln) in src.ways:
        item("Route point", "way", at, ln)
    for p in src.props:
        fam = B.PK_NAMES.get(p.get("kind"))
        if p.get("fam"):                    # a family's element (SPEC.md 130.25.6.4): its kind's name
            fam = next((k["name"] for k in p["fam"]["kinds"] if k["kind"] == p["kind"]), p["fam"]["name"])
        fam = fam or "prop"
        at = p.get("at")
        cells = p.get("cells")
        item(_plain(fam), "prop", at if isinstance(at, tuple) else None, p["line"],
             cells=list(cells) if cells else None, fam=fam)
    for t in src.tubes:
        a, b, via = t.get("inn"), t.get("out"), t.get("via")
        via = [via] if isinstance(via, tuple) and via and isinstance(via[0], int) else list(via or [])
        item("Tube", "tube", a, t["line"], cells=[c for c in (a, b) if c], path=[c for c in [a] + via + [b] if c],
             sub=t.get("sub"))
    for q in src.ckpts:
        item("Flag", "checkpoint", q.get("at"), q["line"])
    for q in src.pads:
        item("Ball pad", "pad", q.get("at"), q["line"], mat=q.get("mat"))
    for q in src.cups:
        item("Cup", "cup", q.get("at"), q["line"])
    for q in src.springs:
        item("Spring", "spring", q.get("at"), q["line"])
    for q in src.clocks:
        item("Clock", "clock", q.get("at"), q["line"])
    return out


def _plain(fam):
    return {"platform": "Lift", "windmill": "Windmill", "bumper": "Bumper", "popspikes": "Pop-up spikes",
            "crack": "Cracked floor", "glass": "Glass path", "plate": "Pressure plate", "blower": "Blower",
            "seesawlane": "Seesaw"}.get(fam, fam[:1].upper() + fam[1:])


def _line_of(msg):
    import re
    m = re.search(r":(\d+): ", msg)
    return int(m.group(1)) if m else None


def at_cell(analysis, cell):
    """-> the line numbers whose element covers CELL, the topmost first: items
    (props, flags, ...) before the tile's own statement"""
    lines = [it["line"] for it in analysis["items"] if cell in it["cells"]]
    c = analysis["cells"].get(cell)
    if c and c["line"] and c["line"] not in lines:
        lines.append(c["line"])
    return lines


# ----------------------------------------------------------------------------
# the command line (agents edit through the same methods as the window)
# ----------------------------------------------------------------------------

def _check(path, strict, as_json):
    with open(path, "r", encoding="ascii", newline="") as f:
        text = f.read()
    res = {"file": path, "ok": True, "errors": [], "warnings": []}
    try:
        c = B.compile_course(text, path, strict=strict)
        res["warnings"] = [{k: w[k] for k in ("kind", "msg", "line", "cell", "accepted")}
                           for w in c.warnings]
    except B.CourseError as e:
        res["ok"] = False
        res["errors"].append({"msg": str(e), "line": _line_of(str(e))})
    if as_json:
        print(json.dumps(res, default=list))
    else:
        for e in res["errors"]:
            print("ERROR   %s" % e["msg"])
        for w in res["warnings"]:
            print("WARNING %s%s" % (w["msg"], "  (accepted)" if w["accepted"] else ""))
        print("%s: %s, %d warning(s)" % (path, "builds" if res["ok"] else "REFUSED", len(res["warnings"])))
    return 0 if res["ok"] else 1


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check")
    p.add_argument("course")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("show")
    p.add_argument("course")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("add")
    p.add_argument("course")
    p.add_argument("code")
    p.add_argument("--after", type=int)
    p = sub.add_parser("set")
    p.add_argument("course")
    p.add_argument("line", type=int)
    p.add_argument("code")
    p = sub.add_parser("move")
    p.add_argument("course")
    p.add_argument("line", type=int)
    p.add_argument("dx", type=int)
    p.add_argument("dy", type=int)
    p = sub.add_parser("remove")
    p.add_argument("course")
    p.add_argument("line", type=int)
    a = ap.parse_args(argv)
    if a.cmd == "check":
        return _check(a.course, a.strict, a.json)
    d = Document.load(a.course)
    if a.cmd == "show":
        rows = [{"line": s.line, "kind": s.subkind, "code": s.code} for s in d.statements()]
        if a.json:
            print(json.dumps(rows))
        else:
            for r in rows:
                print("%5d  %-18s %s" % (r["line"], r["kind"], r["code"]))
        return 0
    try:
        if a.cmd == "add":
            n = d.insert(a.code, after=a.after)
            print("added at line %d" % n)
        elif a.cmd == "set":
            d.set_statement(a.line, a.code)
        elif a.cmd == "move":
            d.move(a.line, a.dx, a.dy)
        elif a.cmd == "remove":
            d.remove(a.line)
        an = analyse(d.text(), a.course)
        if an["error"] and not an["src"]:
            print("refused, nothing written: %s" % an["error"])
            return 1
        d.save()
    except EditError as e:
        print("bbedproj: %s" % e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
