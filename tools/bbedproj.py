#!/usr/bin/env python3
"""bbedproj - THE COURSE BUILDER'S MODEL (SPEC.md 130.58.2, 130.58.3).

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
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bbcourse as B  # noqa: E402

# The statements whose first operand is a SHAPE (SPEC.md 130.10.3, 130.24.4).
SHAPED = ("floor", "wall", "goal", "hole", "surface", "float", "guard", "water", "noocclude", "archway", "gap")
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
        """True when the file is not what was loaded or last saved (SPEC.md 130.58.3)"""
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

    def group(self, label):
        """`with doc.group("label"):` - every edit inside is ONE undo step"""
        doc = self

        class _G(object):
            def __enter__(self_):
                self_.n = len(doc.undo_stack)
                return doc

            def __exit__(self_, et, ev, tb):
                if len(doc.undo_stack) > self_.n + 1:
                    first = doc.undo_stack[self_.n]
                    del doc.undo_stack[self_.n:]
                    doc.undo_stack.append((label, first[1]))
                return False
        return _G()

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

    # -- the ground as ONE LAYER of cells (SPEC.md 130.58.13) ---------------------
    def _ground_shape(self, st):
        """(index, (x0, y0, x1, y1) end-exclusive) of a statement's `tile` or `rect` shape - one a piece can be
        cut out of - or None (a band, a box, a half or a quarter: never split)"""
        t = st.toks
        i = 2 if st.kind == "surface" else 1
        if i < len(t) and t[i] in ("half", "quarter"):
            return None
        try:
            if i < len(t) and t[i] == "tile":
                x, y = int(t[i + 1]), int(t[i + 2])
                return i, (x, y, x + 1, y + 1), 3
            if i < len(t) and t[i] == "rect":
                return i, tuple(int(t[i + k]) for k in range(1, 5)), 5
        except (ValueError, IndexError):
            return None
        return None

    def replace_area(self, area, ground=(), then=(), kinds=("floor", "wall", "goal", "hole"),
                     surfaces=False, label=None):
        """ONE edit: cut the AREA (x0, y0, x1, y1, cells inclusive) out of every `tile`/`rect` statement of
        KINDS (and of `surface`s when SURFACES) - each keeps its own clauses, so a ramp's pieces keep its
        plane - then add the GROUND statements after the course's last ground statement and the THEN
        statements after the last of their own kind. A shape that cannot be cut (band, box, half,
        quarter) is left, and the new ground, coming later, lies over it. -> the line of the first added"""
        areas = list(area) if area and isinstance(area[0], (tuple, list)) else ([area] if area else [])
        cut_kinds = tuple(kinds) + (("surface",) if surfaces else ())
        lines = list(self.lines)
        for ar in areas:
            lines, last_ground = self._cut(lines, ar, cut_kinds)
        if not areas:
            last_ground = max([j + 1 for j, raw in enumerate(lines) if Statement(j + 1, raw).kind in
                               ("floor", "wall", "goal", "hole", "surface", "float")] or [len(lines)])
        new = lines
        for code in ground:
            new.insert(last_ground, code)
            last_ground += 1
        first = last_ground - len(ground) + 1 if ground else None
        for code in then:
            kind = code.split()[0]
            same = [j for j, raw in enumerate(new) if Statement(j + 1, raw).kind == kind]
            at = same[-1] + 1 if same else len(new)
            while at > 0 and at == len(new) and not new[at - 1].strip():
                at -= 1
            new.insert(at, code)
            if first is None:
                first = at + 1
        self._commit(label or "change the area", new)
        return first

    def _cut(self, lines, area, cut_kinds):
        """LINES with AREA cut out of every statement of CUT_KINDS; -> (lines, the index after the last
        ground statement)"""
        ax0, ay0, ax1, ay1 = area[0], area[1], area[2] + 1, area[3] + 1
        new = []
        last_ground = 0
        for i, raw in enumerate(lines, 1):
            st = Statement(i, raw)
            if st.kind not in cut_kinds:
                new.append(raw)
                if st.kind in ("floor", "wall", "goal", "hole", "surface", "float"):
                    last_ground = len(new)
                continue
            sh = self._ground_shape(st)
            if not sh:
                new.append(raw)
                last_ground = len(new)
                continue
            k, (x0, y0, x1, y1), n = sh
            ix0, iy0, ix1, iy1 = max(x0, ax0), max(y0, ay0), min(x1, ax1), min(y1, ay1)
            if ix0 >= ix1 or iy0 >= iy1:            # untouched
                new.append(raw)
                last_ground = len(new)
                continue
            pieces = []
            if iy0 > y0:
                pieces.append((x0, y0, x1, iy0))
            if iy1 < y1:
                pieces.append((x0, iy1, x1, y1))
            if ix0 > x0:
                pieces.append((x0, iy0, ix0, iy1))
            if ix1 < x1:
                pieces.append((ix1, iy0, x1, iy1))
            for j, (p0, q0, p1, q1) in enumerate(pieces):
                shape = ["tile", str(p0), str(q0)] if (p1 - p0, q1 - q0) == (1, 1) else \
                    ["rect", str(p0), str(q0), str(p1), str(q1)]
                code = join_tokens(st.toks[:k] + shape + st.toks[k + n:])
                new.append(st.indent + code + (st.comment if j == 0 else ""))
                last_ground = len(new)
        return new, last_ground

    def auto_band(self):
        """SPEC.md 130.58.13: a course whose floors (and the flight past their edges) leave its picture - the
        diagonal band its `width` (word columns, 64 - 160 in 8s) and `origin` draw - gets the `origin` that
        centres them; failing that the SMALLEST wider `width` that holds them, centred. Never past 160 (1,280
        px): then it is left refused, for the author. Folded into the edit that needed it. -> what was done,
        in words, or None"""
        a = analyse(self.text(), self.path or "<course>")
        b = a.get("band")
        if not b or not b["out"]:
            return None
        lo, hi = b["span"]
        sts = {st.kind: st for st in self.statements()}
        for width in range(b["width"], B.COLS_MAX + 1, 8):
            W = width * 8
            xmin, xmax = 24 - 16 * lo, W - 24 - 16 * hi - 1       # 16 lo + x0 - 24 >= 0, 16 hi + x0 + 23 < W
            if xmin > xmax:
                continue
            x0 = 16 * int(round(((xmin + xmax) / 2.0) / 16))
            while x0 < xmin:
                x0 += 16
            while x0 > xmax:
                x0 -= 16
            if not xmin <= x0 <= xmax:
                continue
            saved = list(self.lines)
            new = list(self.lines)
            done = []
            if width != b["width"]:
                if "width" in sts:
                    st = sts["width"]
                    new[st.line - 1] = st.indent + "width %d" % width + st.comment
                done.append("widened the picture to %d columns (%d px)" % (width, 8 * width))
            org = None if x0 == width * 4 else "origin %d" % x0
            if "origin" in sts:
                st = sts["origin"]
                if org:
                    new[st.line - 1] = st.indent + org + st.comment
                else:
                    del new[st.line - 1]
            elif org:
                new.insert(sts["width"].line if "width" in sts else 1, org)
            if org and width == b["width"]:
                done.append("moved the picture across (origin %d)" % x0)
            self.lines = new
            self._analysis = None
            if analyse(self.text(), self.path or "<course>").get("band", {}).get("out"):
                self.lines = saved
                self._analysis = None
                continue
            self._notify("band")
            return " and ".join(done) or None
        return None

    def tidy(self, near=None, label=None):
        """SPEC.md 130.58.14: rejoin ground statements of ONE kind and the SAME clauses (a ramp's are its
        plane, so its pieces rejoin too) into the fewest rectangles. Only statements with no comment of their
        own, laid by `tile` or `rect`, touching NEAR (cells x0, y0, x1, y1 inclusive, grown by one) when given,
        and whose cells no other ground statement covers. -> True when something was rejoined"""
        groups = {}
        sts = [st for st in self.statements() if st.kind in ("floor", "wall", "goal", "hole", "surface", "float")]
        cover = {}
        for st in sts:
            sh = self._ground_shape(st)
            if not sh:
                continue
            k, (x0, y0, x1, y1), n = sh
            for x in range(x0, x1):
                for y in range(y0, y1):
                    cover.setdefault((st.kind == "surface" or st.kind == "float", x, y), []).append(st.line)
        for st in sts:
            sh = self._ground_shape(st)
            if not sh or st.comment.strip():
                continue
            k, (x0, y0, x1, y1), n = sh
            key = (st.kind, tuple(st.toks[:k]), tuple(st.toks[k + n:]), st.indent)
            groups.setdefault(key, []).append((st, (x0, y0, x1, y1)))
        new = list(self.lines)
        drop = set()
        changed = False
        for key, members in groups.items():
            if len(members) < 2:
                continue
            if near:
                nx0, ny0, nx1, ny1 = near[0] - 1, near[1] - 1, near[2] + 2, near[3] + 2
                if not any(r[0] < nx1 and r[2] > nx0 and r[1] < ny1 and r[3] > ny0 for _s, r in members):
                    continue
            mine = {m[0].line for m in members}
            lo_l, hi_l = min(mine), max(mine)
            cells = set()
            clash = False
            lay = key[0] in ("surface", "float")
            for st, (x0, y0, x1, y1) in members:
                for x in range(x0, x1):
                    for y in range(y0, y1):
                        cells.add((x, y))
                        # the rejoined statement takes the FIRST member's place: a statement over this cell
                        # that a LATER member overrode would then win the cell - a different course
                        if any(l_ not in mine and lo_l < l_ < st.line for l_ in cover.get((lay, x, y), [])):
                            clash = True
            if clash:
                continue
            rects = _rects(cells)
            if len(rects) >= len(members):
                continue
            st0, _r = members[0]
            k = self._ground_shape(st0)[0]
            head, tail = list(key[1]), list(key[2])
            codes = [join_tokens(head + (["tile", str(a), str(b)] if (c - a, d - b) == (1, 1) else
                                         ["rect", str(a), str(b), str(c), str(d)]) + tail) for a, b, c, d in rects]
            new[st0.line - 1] = "\n".join(key[3] + cd for cd in codes)
            drop |= {m[0].line for m in members[1:]}
            changed = True
        if not changed:
            return False
        out = []
        for i, l_ in enumerate(new, 1):
            if i not in drop:
                out.extend(l_.split("\n"))
        self._commit(label or "rejoin the floor", out)
        return True

    def toggle_gap(self, cell, side, faces):
        """SPEC.md 130.58.21, 130.57: mark or unmark ONE face (cell, side 'sw'|'se') for the gap band, as one undo
        step. FACES is every face the detector found (c.gap_faces as {((wx, wy), side)}): a statement naming the
        face loses it - rewritten as the fewest `gap rect` / `gap tile` lines that still name what it marked
        and that a face of FACES is in (a piece that would band nothing is dropped), deleted when nothing is
        left - and an unmarked face gains a `gap tile X Y side`, folded into a same-side statement it squares
        off. -> 'marked' or 'unmarked'"""
        cell = tuple(cell)
        src = self.analysis()["src"]
        if src is None:
            raise EditError("the course does not lay out, so no gap can be marked")
        faces = {(tuple(c), sd) for c, sd in faces}
        naming = [(tiles, sides, ln) for tiles, sides, ln in src.gaps if cell in tiles and side in sides]

        def codes(marks):
            """{(cell, side)} -> the fewest gap lines: cells marked on both sides with no side, the rest per side"""
            both = {c for c, sd in marks if sd == "sw" and (c, "se") in marks}
            out = []
            for sd, cs in ((None, both), ("sw", {c for c, s_ in marks if s_ == "sw"} - both),
                           ("se", {c for c, s_ in marks if s_ == "se"} - both)):
                for x0, y0, x1, y1 in _rects(cs):
                    if not any(((x, y), s_) in faces for x in range(x0, x1) for y in range(y0, y1)
                               for s_ in ((sd,) if sd else ("sw", "se"))):
                        continue
                    shp = ("tile %d %d" % (x0, y0) if (x1 - x0, y1 - y0) == (1, 1)
                           else "rect %d %d %d %d" % (x0, y0, x1, y1))
                    out.append("gap %s%s" % (shp, " " + sd if sd else ""))
            return out
        with self.group("unmark a gap band" if naming else "mark a gap band"):
            if naming:
                for tiles, sides, ln in sorted(naming, key=lambda g: -g[2]):     # (bottom first: lines stay put)
                    rest = codes({(c, sd) for c in tiles for sd in sides} - {(cell, side)})
                    if not rest:
                        self.remove(ln)
                        continue
                    self.set_statement(ln, rest[0])
                    for k, code in enumerate(rest[1:]):
                        self.insert(code, after=ln + k)
                return "unmarked"
            for tiles, sides, ln in src.gaps:            # folded into a same-side statement it squares off
                if sides == (side,) and len(_rects(set(tiles) | {cell})) == 1:
                    self.set_statement(ln, codes({(c, side) for c in set(tiles) | {cell}})[0])
                    return "marked"
            self.insert("gap tile %d %d %s" % (cell[0], cell[1], side))
            return "marked"

    WAY_ERR = re.compile(r"way \((-?\d+), (-?\d+)\) is on a (WALL|VOID) tile")

    def relocate_ways(self, reach=4, tries=40):
        """SPEC.md 130.58.22: every route point an edit left on a WALL or on VOID moved to the nearest cell it may
        stand on (a floor, goal or shaped floor, the nearest first, then the one nearest the route's next point),
        each a commit of its own - the caller folds them into its edit's undo step (merge_since). -> [(line,
        (x, y), (nx, ny))] moved; a point with no such cell within REACH cells is left (its edit is refused)"""
        moved = []
        for _ in range(tries):
            a = self.analysis()
            m = self.WAY_ERR.search(a["error"] or "")
            if not m or not a.get("error_line"):
                break
            ln, wx, wy = a["error_line"], int(m.group(1)), int(m.group(2))
            ok = {c for c, d in a["cells"].items() if d["kind"] in ("floor", "goal", "field") and not d.get("pieces")}
            ways = [w for w, _l in a["src"].ways] if a["src"] else []
            nxt = next((ways[i + 1] for i, (w, l_) in enumerate(a["src"].ways) if l_ == ln and i + 1 < len(ways)),
                       None)
            best = None
            for r in range(1, reach + 1):
                ring = [(wx + dx, wy + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1)
                        if max(abs(dx), abs(dy)) == r and (wx + dx, wy + dy) in ok]
                if ring:
                    best = min(ring, key=lambda c: ((c[0] - wx) ** 2 + (c[1] - wy) ** 2,
                                                    (abs(c[0] - nxt[0]) + abs(c[1] - nxt[1])) if nxt else 0))
                    break
            if best is None:
                break
            self.set_statement(ln, self.moved_code(ln, best[0] - wx, best[1] - wy), label="move a route point")
            moved.append((ln, (wx, wy), best))
        return moved

    def merge_since(self, n, label=None):
        """the undo steps from N on folded into one (the first's label, or LABEL)"""
        if len(self.undo_stack) > n + 1:
            first = self.undo_stack[n]
            del self.undo_stack[n:]
            self.undo_stack.append((label or first[0], first[1]))

    def ways_in(self, rect, kinds=("way",)):
        """the KINDS statements (a cell first: `way`, `start`, `checkpoint`) standing in RECT (x0, y0, x1, y1
        end-exclusive): [(line, code)]"""
        out = []
        for st in self.statements():
            if st.kind in kinds and len(st.toks) >= 3:
                try:
                    x, y = int(st.toks[1]), int(st.toks[2])
                except ValueError:
                    continue
                if rect[0] <= x < rect[2] and rect[1] <= y < rect[3]:
                    out.append((st.line, st.code))
        return out

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

# a split cell's pieces in the plan (u right, v down, the cell's corner T at (0, 0)): SPEC.md 130.24.3's halves -
# TB along T-B (A left, B right), LR along L-R (A up, B down) - and quarters N, E, S, W round the centre
PIECE_POLY = {(B.KIND_TB, 0): ((0, 0), (0, 1), (1, 1)), (B.KIND_TB, 1): ((0, 0), (1, 0), (1, 1)),
              (B.KIND_LR, 0): ((0, 0), (1, 0), (0, 1)), (B.KIND_LR, 1): ((1, 0), (1, 1), (0, 1)),
              (B.KIND_Q, 0): ((0, 0), (1, 0), (.5, .5)), (B.KIND_Q, 1): ((1, 0), (1, 1), (.5, .5)),
              (B.KIND_Q, 2): ((1, 1), (0, 1), (.5, .5)), (B.KIND_Q, 3): ((0, 1), (0, 0), (.5, .5))}
FLY = 4                         # diagonals a ball's flight reaches past a floor's edge (SPEC.md 130.58.13)
KIND_NAMES = {B.KIND_FLOOR: "floor", B.KIND_WALL: "wall", B.KIND_GOAL: "goal", B.KIND_FIELD: "field"}


def reshape(toks, si, n, rect):
    """SPEC.md 130.58.22: a statement's shape (its tokens SI .. SI + N) laid over RECT (x0, y0, x1, y1 end-exclusive)
    instead - `tile` for one cell - and a ramp along x or y keeping its SLOPE: its span is the new extent along its
    run and its end heights follow at the same rate. -> the code"""
    x0, y0, x1, y1 = rect
    shape = ["tile", str(x0), str(y0)] if (x1 - x0, y1 - y0) == (1, 1) else ["rect"] + [str(v) for v in rect]
    t = list(toks[:si]) + shape + list(toks[si + n:])
    if "ramp" in t:
        j = t.index("ramp")
        if j + 5 < len(t) + 1 and t[j + 1] in ("x", "y"):
            a0, a1, h0, h1 = int(t[j + 2]), int(t[j + 3]), float(t[j + 4]), float(t[j + 5])
            rate = (h1 - h0) / float(a1 - a0) if a1 != a0 else 0.0
            n0, n1 = (x0, x1) if t[j + 1] == "x" else (y0, y1)
            t[j + 2], t[j + 3] = str(n0), str(n1)
            t[j + 4], t[j + 5] = "%g" % (h0 + rate * (n0 - a0)), "%g" % (h0 + rate * (n1 - a0))
    return join_tokens(t)


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
            edges = {k: hmax for k in ("+x", "-x", "+y", "-y")}
        else:
            h = _rec_height(top) / 2.0 + zb
            hs = [top.corner(dx, dy) / 2.0 + zb for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1))]
            hmin, hmax = min(hs), max(hs)
            slope = (getattr(top, "sx", 0), getattr(top, "sy", 0))
            edges = {k: top.corner(dx, dy) / 2.0 + zb for k, (dx, dy) in
                     (("+x", (1, .5)), ("-x", (0, .5)), ("+y", (.5, 1)), ("-y", (.5, 0)))}
        out["cells"][cell] = {
            "kind": KIND_NAMES.get(top.kind, "floor"), "h": h, "hmin": hmin, "hmax": hmax, "slope": slope,
            "surf": B.SURFACES[t.surf] if 0 <= t.surf < len(B.SURFACES) else "normal",
            "line": getattr(top, "line", None) or t.line, "split": isinstance(t, B.Split),
            "water": getattr(top, "wbed", None) is not None, "guard": getattr(top, "guard", None) is not None,
            "edges": edges}
        if isinstance(t, B.Split):              # its pieces, drawn and picked as triangles
            ps = []
            for i, r in enumerate(t.halves):
                poly = PIECE_POLY.get((t.diag, i))
                if poly is None or r is None:
                    continue
                ps.append({"poly": poly, "kind": KIND_NAMES.get(r.kind, "floor"), "h": _rec_height(r) / 2.0 + zb,
                           "line": getattr(r, "line", None) or t.line})
            out["cells"][cell]["pieces"] = ps
    # the start and the route on the ground (the compiler's own rules, cheap enough for every edit)
    if out["cells"] and not out["error"] and src.start and src.pathway is None:
        (sx, sy), sln = src.start
        d = out["cells"].get((sx, sy))
        if d is None or d["kind"] != "floor" or d["slope"] != (0, 0) or d.get("pieces"):
            out["error"] = "%s:%d: start (%d, %d) is not a flat FLOOR" % (fname, sln, sx, sy)
            out["error_line"] = sln
    if out["cells"] and not out["error"]:
        for (wx, wy), ln in src.ways:
            d = out["cells"].get((wx, wy))
            if d is None or d["kind"] == "wall":
                out["error"] = "%s:%d: way (%d, %d) is on a %s tile" % (fname, ln, wx, wy, "WALL" if d else "VOID")
                out["error_line"] = ln
                break
    # the picture's band (SPEC.md 130.58.13): a cell is drawn when 16 (wx - wy) + x0 - 24 >= 0 and
    # 16 (wx - wy) + x0 + 23 < 8 width (bbcourse.foot_x); the floors must lie inside it
    width = src.width or 64
    x0 = src.origin[0] if src.origin else width * 4
    amin = -((x0 - 24) // 16)
    amax = (8 * width - 24 - x0 - 1) // 16
    # the compiler holds every cell the ball can REACH to it - a flight carries it about 4 diagonals past an
    # edge (MEASURED on the shipped courses: 4 to 6, the extra clipped by the band), so a floor needs FLY
    # diagonals of room on either side
    fl = [x - y for (x, y), d in out["cells"].items() if d["kind"] in ("floor", "goal", "field")]
    outs = sorted(c for c, d in out["cells"].items() if d["kind"] in ("floor", "goal", "field")
                  and not amin + FLY <= c[0] - c[1] <= amax - FLY)
    out["band"] = {"width": width, "x0": x0, "amin": amin, "amax": amax,
                   "span": (min(fl) - FLY, max(fl) + FLY) if fl else (0, 0), "out": outs}
    if outs and not out["error"]:
        out["error"] = ("%s: the floor at (%d, %d) is too near the edge of the course's picture: %d columns "
                        "(%d px) draw the cells whose x - y runs from %d to %d, and a ball flies about %d past a "
                        "floor's edge" % (fname, outs[0][0], outs[0][1], width, 8 * width, amin, amax, FLY))
        out["error_kind"] = "band"
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


def _rects(cells):
    """CELLS as few rectangles (x0, y0, x1, y1 end-exclusive) as a greedy cover finds, rows first or columns
    first, whichever is fewer"""
    def cover(cs, swap):
        cs = {(y, x) for x, y in cs} if swap else set(cs)
        out = []
        while cs:
            x0, y0 = min(cs, key=lambda c: (c[1], c[0]))
            x1 = x0
            while (x1 + 1, y0) in cs:
                x1 += 1
            y1 = y0
            while all((x, y1 + 1) in cs for x in range(x0, x1 + 1)):
                y1 += 1
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    cs.discard((x, y))
            out.append((y0, x0, y1 + 1, x1 + 1) if swap else (x0, y0, x1 + 1, y1 + 1))
        return out
    a, b = cover(cells, False), cover(cells, True)
    return sorted(a if len(a) <= len(b) else b, key=lambda r: (r[1], r[0]))


def _plain(fam):
    return {"platform": "Lift", "windmill": "Windmill", "bumper": "Bumper", "popspikes": "Pop-up spikes",
            "crack": "Cracked floor", "glass": "Glass path", "plate": "Pressure plate", "blower": "Blower",
            "seesawlane": "Seesaw"}.get(fam, fam[:1].upper() + fam[1:])


def _line_of(msg):
    import re
    m = re.search(r":(\d+): ", msg)
    return int(m.group(1)) if m else None


def _inside(pt, poly):
    x, y = pt
    n = len(poly)
    sgn = None
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        c = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        if abs(c) < 1e-9:
            continue
        if sgn is None:
            sgn = c > 0
        elif (c > 0) != sgn:
            return False
    return True


def at_cell(analysis, cell, frac=None):
    """-> the line numbers whose element covers CELL, the topmost first: items
    (props, flags, ...) before the tile's own statement; in a SPLIT cell, the piece under FRAC (the point in
    the cell, 0 - 1 each way) first"""
    lines = [it["line"] for it in analysis["items"] if cell in it["cells"] and it["kind"] != "way"]
    c = analysis["cells"].get(cell)
    if c and c.get("pieces") and frac is not None:
        for p in c["pieces"]:
            if _inside(frac, p["poly"]) and p["line"] not in lines:
                lines.append(p["line"])
    if c and c["line"] and c["line"] not in lines:
        lines.append(c["line"])
    # a route point is never drawn in the game: it is last, under the ground it marks (Shift-click reaches it)
    lines += [it["line"] for it in analysis["items"] if cell in it["cells"] and it["kind"] == "way"
              and it["line"] not in lines]
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
