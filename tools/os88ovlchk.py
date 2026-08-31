#!/usr/bin/env python3
"""Prove no call crosses a segment boundary inside the kernel as a NEAR call.

`.ovl` and `.cold` each have their own `vstart`, so a near call between one
of them and `.text` assembles
without complaint and emits a displacement computed between two different
address spaces.  Nothing catches that: not NASM, not the linker (there isn't
one), and not a boot on the one machine whose rung QEMU can emulate.  This
walks every `section` block in kernel/ and refuses any near control transfer
whose target label lives in a different address space: call, jmp (near and
short spellings included - `short` was once swallowed by the regex as if it
were the label, which silently exempted every `jmp short`), and the
conditional branches and loops.  Local labels (.foo) bind to their parent
and cannot cross, so they fall out of the label map untested, which is
correct.

It also knows the `OSAPI_*` cell macros, whose argument IS a call site: the
`call` lives in the macro body as `call %1`, so a plain scan of the source
sees `OSAPI_SLOT dskw_dfree` as no call at all.  Six of those pointed into
the file modules the day they went cold and not one would have been
reported.  A new cell macro that near-calls its argument belongs in CELL
below.

What it CANNOT see, by construction: an indirect transfer (`call bx`,
`jmp [table]`) and a code pointer stored in data.  Those stay a review rule:
a table of `.cold` pointers may live in `.text` only if cold code alone
dispatches through it.  There are four - ctrl.inc's page table, and
files.inc's `fm_jmp` plus the two `fm_ctx_*` descriptor sets, all three
reached only from `fm_docmd` / `fm_rclick`, which are themselves cold.  The
mirror of that rule is what a build cannot catch either: a table in `.text`
that `.text` DOES dispatch through must name the resident thunk and not the
`_x` body, which is how `fm_tpl` and `fm_menus` are written.

Run it from `make`; it is worth more than any amount of reading.
"""
import re, sys, glob, os

CALL = re.compile(r'\b(?:call|jmp|j[a-z]{1,3}|loop[a-z]{0,2})\s+'
                  r'(?:(?:near|short)\s+)?(?:(\w+):)?([A-Za-z_]\w*)\b')
# an API cell macro whose body near-calls its LAST argument
CELL = re.compile(r'^\s*OSAPI_(?:SLOT|JSLOT|NSTUB|XSTUB)\s+(?:\w+\s*,\s*)?'
                  r'([A-Za-z_]\w*)\s*(?:,\s*\d+\s*)?$')
# ...and the two-or-three-argument cells DEFINE their first argument, as `%1:`
# inside the macro body.  A `name:` scan cannot see that, so the 45 OSAPI_JSLOT
# targets were not merely untested above - they were not in the label map at
# all, which is how adding JSLOT alone would have bought nothing.
CELLDEF = re.compile(r'^\s*OSAPI_(?:NSTUB|XSTUB)\s+([A-Za-z_]\w*)\s*,')
MODS = ('.modc', '.modf', '.modl')   # on-demand module images (SPEC.md 2.8).
# **A section added here and nowhere else is a section NOTHING below checks**,
# which is how `.modl` shipped once with the near-call check blind to it - the
# clone module's every `call COLD_SEG:` was correct, and would not have been
# reported had one been near.
FAR = ('.boot2', '.ovl', '.ovlw', '.cold') + MODS  # sections with a vstart
# `.ovlw` is the boot overlay's OTHER half (SPEC.md 2.5.3): the bodies that are
# dead at the first mount rather than at spl_finish, landing on FAT_SEG off the
# kernel's own read.  It has a vstart of its own for `.ovl`'s reason and every
# rule below that names one names both.


# A file the kernel %includes from OUTSIDE kernel/, and the section its
# contents therefore land in.  apps/os88ui.inc is the shared button and glyph
# (SPEC.md 20.5.1): one source for two worlds, %included by fdlg.inc from
# inside a `.cold` block, so every label in it is cold - and a NEAR call to
# one from another address space is the exact bug this file exists to refuse.
#
# It was not scanned at all until an on-demand module (SPEC.md 2.8) near-called
# os88ui_glyph from `.modc`.  The label was not in the map, so the call was
# untested rather than reported, and the Control Panel painted itself and then
# ran off the end of its own image into whatever was above it.  A file that
# emits code into the kernel belongs here whatever directory it is in.
EXTRA = {'apps/os88ui.inc': '.cold',
         # ...and SPEC.md 2.9's stage 2, which is %included into `.boot2` from
         # kernel.asm and lives in boot/. It carries no `section` of its own -
         # one would displace it from file offset 0 - so without this line
         # every label in it would be filed as `.text` and a near call out of
         # it would go unreported, which is the exact bug this file exists for.
         'boot/boot2.asm': '.boot2',
         # ...and the loading screen, which joined it (SPEC.md 2.9.4). Like
         # clockw.inc below it carries no `section` of its own - kernel.asm
         # wraps the %include - so without this line every label in it files
         # as `.text` and stage 2's own near calls into it are reported as
         # crossings that are not, while a real crossing OUT of it would not
         # be reported at all.
         'kernel/splash.inc': '.boot2',
         # ...and one that IS under kernel/, so the glob below finds it too:
         # clockw.inc is SPEC.md 37.94's RTC write half, %included from
         # ctrl.inc's `.modc`. It carries no `section` of its own (one would
         # push modc_hdr off offset 0), so without this line every label in it
         # would be filed as `.text` and every far call out of it reported as
         # a crossing that is not one - and, worse, a NEAR call out of it
         # would not be reported at all.
         'kernel/clockw.inc': '.modc'}


def sections(path):
    """yield (section, line-number, source-line) with comments stripped"""
    cur = EXTRA.get(path, '.text')
    for n, raw in enumerate(open(path), 1):
        line = raw.split(';')[0]
        m = re.match(r'^\s*section\s+(\.\w+)', line)
        if m:
            cur = m.group(1)
            continue
        yield cur, n, line


def sections_raw(path):
    """...and the same walk with the RAW line beside the stripped one.

    The `; ovlchk: DS = ...` markers below live in COMMENTS, which sections()
    throws away before anything can see them - so the check that needs both
    halves gets its own walk rather than a flag on the shared one.
    """
    cur = EXTRA.get(path, '.text')
    for n, raw in enumerate(open(path), 1):
        line = raw.split(';')[0]
        m = re.match(r'^\s*section\s+(\.\w+)', line)
        if m:
            cur = m.group(1)
            continue
        yield cur, n, line, raw


def main():
    kfiles = sorted(glob.glob('kernel/*.inc')) + ['kernel/kernel.asm']
    # dedup: an EXTRA under kernel/ is already in the glob, and scanning it
    # twice reports every finding in it twice.
    files = kfiles + [f for f in sorted(EXTRA) if f not in kfiles]
    where = {}                       # label -> section it is defined in
    mbody = {}                       # %macro -> the labels its body near-calls
    for f in files:
        macro = None
        for sect, n, line in sections(f):
            m = re.match(r'^\s*%macro\s+(\w+)', line)
            if m:
                macro = m.group(1)
                mbody.setdefault(macro, set())
                continue
            if re.match(r'^\s*%endmacro', line):
                macro = None
            elif macro:
                for mm in CALL.finditer(line):
                    if mm.group(1) is None:
                        mbody[macro].add(mm.group(2))
            m = re.match(r'^([A-Za-z_]\w*):', line)
            if m:
                where[m.group(1)] = sect
            m = CELLDEF.match(line)
            if m:
                where[m.group(1)] = sect
    # ...and a %macro whose BODY holds a near transfer to a fixed label makes
    # every expansion site a call site that no textual scan can see.  `MARK 42`
    # is not a call; `call mark_here` is, three thousand lines away in the
    # macro.  Eight MARK sites sit inside mouse_init, so a section move that
    # takes mouse_init cold takes eight invisible near calls with it - and
    # `bootmark` being in the build matrix does NOT cover it, because a near
    # call between two vstart=0 sections assembles perfectly.  Collected from
    # the source above rather than hand-listed, so a new macro is covered the
    # day it is written; %%local labels start with `%` and fall out by
    # themselves, and anything that is not a known label is dropped here.
    mbody = {k: (v & set(where)) for k, v in mbody.items()}
    mbody = {k: v for k, v in mbody.items() if v}
    MEXP = re.compile(r'^\s*(\w+)\b')

    bad = []
    for f in files:
        for sect, n, line in sections(f):
            hits = [(m.group(1), m.group(2)) for m in CALL.finditer(line)]
            m = MEXP.match(line)
            if m and m.group(1) in mbody:
                hits += [(None, t) for t in mbody[m.group(1)]]
            m = CELL.match(line)
            if m:
                hits.append((None, m.group(1)))
            for seg, tgt in hits:
                tsect = where.get(tgt)
                if tsect is None:
                    continue
                a = sect if sect in FAR else '.text'
                b = tsect if tsect in FAR else '.text'
                if a != b and seg is None:
                    bad.append((f, n, '%s -> %s, near' % (a, b), tgt))
    for f, n, why, tgt in bad:
        print("%s:%d: %s: %s" % (f, n, why, tgt), file=sys.stderr)
    if bad:
        sys.exit("os88ovlchk: %d call(s) cross a segment boundary near" % len(bad))
    print("os88ovlchk: no near call crosses a segment boundary")

    # --- and the OTHER half of SPEC.md 2.6: nothing may assume CS ------------
    # Rule 1 puts cold code's DATA in .text, so cold code has no data of its
    # own to reach - which makes "CS is mentioned in .cold" a clean invariant
    # rather than a heuristic, and the whole kernel satisfies it.
    #
    # It is worth a refusal because the failure is silent in a way the check
    # above is not: `mov ax, cs` meaning "the kernel segment" assembles, and
    # the loop that breaks it is a segment LOAD rather than a control
    # transfer, so nothing here saw it. Cold, CS is COLD_SEG - dsk_copy_in
    # staged a boot sector into the middle of the cold segment and every BPB
    # field stayed 0, which surfaced as "No os8088 disk (A:)" on a good
    # floppy. Name the segment (`mov ax, KERNEL_SEG`) and this stays quiet.
    #
    # .ovl is deliberately NOT checked: the overlay's data rides WITH it, so
    # reaching it through CS is the correct idiom there and two places use it
    # (font.inc's glyph copy does `push cs / pop ds`, drv_snd_sniff uses
    # `cs lodsw`).
    #
    # **AND NEITHER ARE THE MODULE SECTIONS, SINCE SPEC.md 2.8.6.** They used
    # to be, on rule 1's premise that a module carries no data - and when that
    # premise was true the check was exact. A module may now carry its own
    # STRINGS and read them through CS, which is what took the cloner's and
    # the formatter's prompts out of the kernel entirely, so `[cs:si]` in a
    # `.mod*` section is the correct idiom exactly as it is in `.ovl`. What is
    # lost with it is the guard against `mov ax, cs` meaning KERNEL_SEG inside
    # a module; that is now a review rule, and the cheap half of it is the
    # `lods` refusal further down.
    CS = re.compile(r'\b(?:push\s+cs'
                    r'|mov\s+(?:\w+|(?:(?:byte|word|dword)\s+)?\[[^\]]*\])'
                    r'\s*,\s*cs'
                    r'|cs\s*:'
                    r'|cs\s+(?:lods|movs|stos|scas))', re.I)
    # SCOPED TO kernel/, and EXTRA's files are deliberately left out. A
    # one-source-two-worlds include (apps/os88ui.inc, SPEC.md 20.5.1) is half
    # package and half kernel behind `%ifdef OS88UI_KERNEL`, and this scanner
    # does not evaluate the preprocessor - so the PACKAGE half's `os88ui_armw:
    # dw 0`, which never reaches the kernel at all, reads here as data in
    # .cold. The near-call check above still needs the file, and needs it
    # badly: it is where eleven real crossings hid (SPEC.md 2.8). What these
    # two checks ask - where does THIS file's code land - is the question a
    # dual-world include does not have one answer to.
    cs_bad = []
    for f in kfiles:
        for sect, n, line in sections(f):
            if sect == '.cold' and CS.search(line):
                cs_bad.append((f, n, line.strip()[:60]))
    for f, n, src in cs_bad:
        print("%s:%d: .cold assumes CS: %s" % (f, n, src), file=sys.stderr)
    if cs_bad:
        sys.exit("os88ovlchk: %d CS assumption(s) in .cold - SPEC.md 2.6 "
                 "rule 2 (name the segment)" % len(cs_bad))
    print("os88ovlchk: no .cold code assumes CS")

    # --- rule 2b: `.ovl` code may not STORE CS ------------------------------
    # `.ovl` rides inside the boot blob and is GIVEN BACK TO THE HEAP at
    # spl_finish (kernel.asm, "It costs no RAM after that at all"). That is the
    # whole reason boot-only code is worth putting there - it stops costing
    # anything the moment the desktop is up - and it is also the trap.
    #
    # READING through CS in `.ovl` is correct and stays allowed, for the reason
    # the block above gives: the overlay's data rides with it. What can never be
    # right is WRITING CS somewhere - an interrupt vector, a far pointer, a saved
    # segment word. The value stored is the blob's segment, and the blob is
    # about to be handed to the heap and written over by the first claim. The
    # store succeeds, the boot finishes, and the machine dies later at a vector
    # that now points into somebody's buffer.
    #
    # This is not hypothetical. mouse_init installs the mouse and int 09h
    # vectors with `mov [es:si+2], cs`, and moving its boot half into `.ovl` is
    # exactly what SPEC.md 9.4's overlay move does. Three such sites are inside
    # the moved range. Before this rule they were guarded by NOTHING: the CS
    # check above is scoped to `.cold`, `.ovl` was deliberately exempt from it,
    # and nasm is happy - so the reviewer's own note that "the gate refuses it"
    # was false, and was demonstrated false by reverting the fix and watching
    # both the stock and the patched gate pass in silence.
    #
    # WHAT THIS CANNOT SEE, stated so nobody trusts it further than it goes: a
    # store laundered through a register (`mov ax, cs` ... `mov [foo], ax`) is
    # invisible here, and so is a `push cs` whose value is popped into a far
    # frame. Those stay a review rule. What is caught is the direct form, which
    # is the one that is written by hand and the one that has actually shipped.
    OVLCS = re.compile(r'\bmov\s+(?:(?:byte|word|dword)\s+)?\[[^\]]*\]'
                       r'\s*,\s*cs\b', re.I)
    ovlcs_bad = []
    for f in kfiles:
        for sect, n, line in sections(f):
            if sect in ('.ovl', '.ovlw') and OVLCS.search(line):
                ovlcs_bad.append((f, n, sect, line.strip()[:60]))
    for f, n, sect, src_ in ovlcs_bad:
        print("%s:%d: %s stores CS: %s" % (f, n, sect, src_), file=sys.stderr)
    if ovlcs_bad:
        sys.exit("os88ovlchk: %d CS store(s) in the boot overlay - both halves "
                 "are given back (.ovl at spl_finish, .ovlw at the first "
                 "mount), so the stored segment becomes somebody else's memory "
                 "(name the segment instead)" % len(ovlcs_bad))
    print("os88ovlchk: no boot-overlay code stores CS")

    # --- rule 2c: every reference INTO `.ovl` is registered ------------------
    # The rule above stops `.ovl` publishing its own segment. This one stops the
    # opposite mistake, which is quieter and which nothing in this tree caught
    # before: somebody adds a call to a body that lives in the overlay, from
    # code that runs AFTER the overlay is gone.
    #
    # `.ovl` is released at spl_finish. A body there is correct exactly as long
    # as every path that reaches it runs during boot. That is not a property the
    # assembler can check, it is not a property a screenshot shows, and the
    # failure is silent: the call lands in whatever the heap handed out, so the
    # routine "works" until the machine is busy enough for the claim underneath
    # it to be something else.
    #
    # `dispcold` byte-compares `.cold` and has no `.ovl` counterpart. This is it,
    # in the only form that is cheap and exact: a REGISTRY, the way SPEC.md
    # 6.6's transparent-text sites are a registry. Every reference into `.ovl`
    # from outside it is listed in tests/ovlrefs.txt with the reason it is
    # boot-only. A new one fails the build until somebody writes that reason
    # down, and the list can be read in one sitting to audit the whole surface.
    #
    # The list may shrink freely. It grows only by a deliberate edit, and the
    # question that edit has to answer is the only question that matters here:
    # WHAT GUARANTEES THIS RUNS BEFORE spl_finish?
    #
    # ...OR BEFORE THE FIRST MOUNT, which is the other half of it since SPEC.md
    # 2.5.3 split the overlay by lifetime. `.ovl` rides in the blob and lives to
    # spl_finish; `.ovlw` lands on FAT_SEG and is forfeit the moment drv_boot
    # mounts a volume, which is EARLIER. So a symbol's deadline depends on which
    # half it is in, and the error below says which - "it looks like boot code"
    # was never an answer and is now not even a well-formed one.
    #
    # THE DIRECTION MATTERS, and it is the new way to get this wrong.
    #
    #   .ovlw -> .ovl    always safe: the callee outlives the caller.
    #   .ovl  -> .ovlw   NOT safe by construction. The blob half is still there
    #                    after the mount and the window half is not, so a call
    #                    the other way is exactly the silent failure this rule
    #                    exists for - and it is INSIDE the overlay, which is
    #                    where the old rule stopped looking.
    #
    # So `.ovlw` is exempt as a SOURCE only when the target is `.ovl`, and every
    # other crossing is registered.
    OVLREG = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'tests', 'ovlrefs.txt')
    registered = set()
    if os.path.exists(OVLREG):
        for line in open(OVLREG):
            line = line.split('#', 1)[0].strip()
            if line:
                registered.add(line.split()[0])

    half = {}                       # label -> '.ovl' | '.ovlw'
    for f in kfiles:
        for sect, n, line in sections(f):
            if sect in ('.ovl', '.ovlw'):
                m = re.match(r'^([A-Za-z_][\w]*):', line)
                if m:
                    half[m.group(1)] = sect

    DEADLINE = {'.ovl': 'spl_finish', '.ovlw': "drv_boot's FIRST MOUNT"}
    ovl_refs, unregistered = set(), []
    if half:
        pat = re.compile(r'\b(' + '|'.join(sorted(map(re.escape, half))) + r')\b')
        for f in kfiles:
            for sect, n, line in sections(f):
                code = line.split(';', 1)[0]
                for m in pat.finditer(code):
                    sym = m.group(1)
                    tgt = half[sym]
                    if sect == tgt:
                        continue            # within one half: near, and fine
                    if sect == '.ovlw' and tgt == '.ovl':
                        continue            # the callee outlives the caller
                    ovl_refs.add(sym)
                    if sym not in registered:
                        unregistered.append((f, n, sect, sym, tgt,
                                             code.strip()[:52]))
    for f, n, sect, sym, tgt, src_ in unregistered:
        print("%s:%d: unregistered reference from %s into %s: %s   %s"
              % (f, n, sect or '(resident)', tgt, sym, src_), file=sys.stderr)
    if unregistered:
        deadlines = sorted({DEADLINE[t] for _, _, _, _, t, _ in unregistered})
        sys.exit("os88ovlchk: %d reference(s) into the boot overlay are not in "
                 "tests/ovlrefs.txt - each one must say what guarantees it runs "
                 "before %s" % (len(unregistered), ' / '.join(deadlines)))
    stale = sorted(registered - ovl_refs)
    if stale:
        sys.exit("os88ovlchk: tests/ovlrefs.txt lists %d reference(s) that no "
                 "longer exist (%s) - the registry may only shrink by deleting "
                 "the row with the code" % (len(stale), ', '.join(stale[:4])))
    nw = sum(1 for v in half.values() if v == '.ovlw')
    print("os88ovlchk: every reference into the boot overlay is registered "
          "(%d of %d labels; %d in .ovl to spl_finish, %d in .ovlw to the "
          "first mount)" % (len(ovl_refs), len(half), len(half) - nw, nw))

    # --- rule 2d: the CALL MACRO has to match the HALF ----------------------
    # Rule 2c asks whether a reference is registered. It does not ask whether
    # the call will ARRIVE, and after SPEC.md 2.5.3 those are different
    # questions: the blob half is reached through [spl_fseg], the window half
    # by `call FAT_SEG:`, and a body registered perfectly well can still be
    # called through the wrong one.
    #
    # What that does is not a refusal, it is a far call to the BLOB's segment
    # carrying a WINDOW offset - so the machine lands wherever that offset
    # falls inside the loading screen, executes it, and returns through a
    # stack it has already ruined. Measured, the first time it happened: a
    # spin at HEAP_SEG:36D2 with SP 53,482 bytes past task 0's stack, a screen
    # of garbage, and no message from anything.
    #
    # It is a one-line mistake to make - `dsk_flop_add: OVLGATE1 dsk_flop_add_x`
    # survived the sweep that converted the other twenty-three sites because
    # the macro shared its line with a label - so it is checked rather than
    # reviewed.
    MACHALF = {'SPLCALL': '.ovl', 'OVLCALL': '.ovl', 'OVLCALLC': '.ovl',
               'OVLGATE': '.ovl', 'OVLGATE1': '.ovl', 'SPLSTUB': '.ovl',
               'SPLGATE': '.ovl', 'SPLGATE1': '.ovl', 'OVWCALL': '.ovlw'}
    MACPAT = re.compile(r'\b(' + '|'.join(MACHALF) + r')\s+(\w+)')
    REACH = {'.ovl': 'the blob, through [spl_fseg]',
             '.ovlw': 'the FAT window, by `call FAT_SEG:`'}
    macbad = []
    for f in kfiles:
        for sect, n, line in sections(f):
            m = MACPAT.search(line.split(';', 1)[0])
            if not m:
                continue
            macro, tgt = m.group(1), m.group(2)
            want, got = MACHALF[macro], half.get(tgt)
            if got and got != want:
                macbad.append((f, n, macro, tgt, want, got))
    for f, n, macro, tgt, want, got in macbad:
        print("%s:%d: %s reaches %s, but %s is in %s"
              % (f, n, macro, REACH[want], tgt, got), file=sys.stderr)
    if macbad:
        sys.exit("os88ovlchk: %d call(s) into the boot overlay use the wrong "
                 "half's entry - the segment and the offset would come from "
                 "different sections (SPEC.md 2.5.3)" % len(macbad))
    print("os88ovlchk: every overlay call matches its target's half")

    # --- rule 2e: nothing in the WINDOW half is called after the mount ------
    # Rule 2d asks whether a call arrives. This asks whether it arrives IN
    # TIME, for the one ordering the tree actually writes down: `kmain` calls
    # `drv_boot_x`, which mounts a volume, and the mount takes the FAT window
    # and the buffers above it - so every `.ovlw` byte is gone from that line
    # onward. Any OVWCALL below it is a call into a FAT table.
    #
    # THIS IS THE ONE THAT COST A BOOT. `xm_boot_x` is boot-only and was
    # registered as such, correctly, for the deadline the registry used to
    # have: it runs before spl_finish. It runs AFTER drv_boot, though - kmain
    # calls it on the next line - so the split put it in the half that is
    # already overwritten, and the machine mounted A:, far-called into the FAT
    # table, executed it, and unwound its own stack until sch_switch's canary
    # caught the wreckage several thousand instructions later. Nothing named
    # the overlay.
    #
    # Only kmain is scanned, and that is deliberate rather than a shortcut:
    # kmain is where the boot's ORDER is written, one call per line, and a
    # reachability answer for anything else is what tests/ovlrefs.txt's reason
    # column is for. A body reached from a runtime path is rule 2c's business.
    kfile = [f for f in kfiles if f.endswith('kernel.asm')]
    late = []
    for f in kfile:
        lines = open(f, errors='replace').read().split('\n')
        try:
            kstart = next(i for i, l in enumerate(lines) if l.startswith('kmain:'))
            mount = next(i for i, l in enumerate(lines)
                         if i > kstart and re.search(r'^\s*OVL(?:GATE1?|CALL)\s+drv_boot_x\b', l))
        except StopIteration:
            continue
        # ...and STOP at kmain's own end, which is the next label in column 0.
        # Scanning to the end of the file instead reads the resident
        # trampolines below it - `dsk_flop_add: OVWCALL dsk_flop_add_x` is one,
        # and it is called from desk_init at MARK 20, long before the mount.
        # A rule about ORDER has to stop where the ordered code does.
        for i in range(mount + 1, len(lines)):
            if re.match(r'^[A-Za-z_.]\w*:', lines[i]):
                break
            m = re.search(r'\bOVWCALL\s+(\w+)', lines[i].split(';', 1)[0])
            if m:
                late.append((f, i + 1, m.group(1)))
    for f, n, sym in late:
        print("%s:%d: OVWCALL %s is AFTER drv_boot_x - the first mount has "
              "already taken the FAT window those bytes are in"
              % (f, n, sym), file=sys.stderr)
    if late:
        sys.exit("os88ovlchk: %d call(s) into .ovlw run after the mount - move "
                 "the body to .ovl, which lives until spl_finish (SPEC.md "
                 "2.5.3)" % len(late))
    print("os88ovlchk: no .ovlw body is called after the first mount")

    # --- rule 1: cold code's DATA lives in .text ----------------------------
    # Same argument as the CS check and the same kind of invariant: DS still
    # names KERNEL_SEG in cold code, so a `db`/`dw` inside .cold is addressed
    # at the wrong segment by every reader of it.  The whole kernel satisfies
    # this (0 across seven cold modules), which is what makes it a refusal.
    #
    # It is worth checking mechanically because the tell is easy to miss BY
    # EYE: NASM does not require a colon on a label, so `desk_pdisk dw
    # ico_disk32` does not look like a label at a glance and a scan keyed on
    # `name:` walks straight past it.  Moving desk.inc cold took seven such
    # lines with it; DS then read the icon pointers out of .text at the cold
    # offsets, and the machine jumped into the weeds on the first click on a
    # drive zone - with the gfx lock held, so it froze rather than faulting.
    # The comment sitting above those very lines had predicted it: "a zero
    # [desk_pdisk] draws the interrupt vector table as an icon".
    #
    # .ovl is again exempt, and for the same reason: the overlay's data rides
    # WITH it, so fdd_mbit, drvp_sbbase and ovl_font_bits all belong there.
    DATA = re.compile(r'^\s*(?:[A-Za-z_]\w*:?\s+)?(?:d[bwdq]|times|res[bwdqt])\b',
                      re.I)
    d_bad = []
    for f in kfiles:                     # kernel/ only - see the note above
        for sect, n, line in sections(f):
            if sect == '.cold' and DATA.match(line):
                # ...and a MODULE's data is its header and nothing else
                # (SPEC.md 2.8): that block is read through ES by the loader,
                # never through DS by the module, so it is the one legitimate
                # `dw` on the far side of a boundary. mod_hdr_ok below is what
                # proves it stops there.
                d_bad.append((f, n, line.strip()[:60]))
    for f, n, src in d_bad:
        print("%s:%d: data in .cold: %s" % (f, n, src), file=sys.stderr)
    if d_bad:
        sys.exit("os88ovlchk: %d data directive(s) in .cold - SPEC.md 2.6 "
                 "rule 1 (data stays in .text)" % len(d_bad))
    print("os88ovlchk: no data in .cold")

    # --- and a module's data is its HEADER, at its head, and nothing else ---
    # A module (SPEC.md 2.8) runs with CS = a heap claim and DS = KERNEL_SEG,
    # so rule 1 binds it exactly as it binds .cold - with ONE exception, which
    # is the 12-byte header plus its entry table: those bytes are read through
    # ES by mod_need, never through DS by the module, and they have to be at
    # offset 0 because that is where the loader looks.
    #
    # So the check is positional rather than absolute: data before the first
    # instruction is the header, and data after it is the bug rule 1 describes.
    # Without this the module sections would be the one place in the kernel
    # where a stray `dw` is not refused by anything.
    # **THIS CHECK IS GONE, and SPEC.md 2.8.6 is why.** A module may now carry
    # its own strings, so `db` past the header is the new normal rather than
    # the bug it was - and the paragraph above describes what that costs. What
    # replaces it is narrower and still catches the thing that actually goes
    # wrong: **`lodsb` in a module image**.
    #
    # The failure a module's data can produce is one-sided. Nothing can read
    # module data too EARLY (the image is loaded before anything far-calls
    # into it) and nothing can read it from the wrong OFFSET (one assembly
    # fixes both ends). What is left is reading it through the wrong SEGMENT -
    # DS, which is KERNEL_SEG - and the one instruction that does that without
    # naming a segment is `lods`. It is also exactly the instruction somebody
    # reaches for when writing a string copier, which is what a module's data
    # is for. `mov al, [cs:si]` is the spelling that works.
    #
    # `movs`, `stos`, `cmps` and `scas` are NOT refused: all four take an
    # explicit pointer setup that a module already has to get right for other
    # reasons, and every use of them in the tree's modules is over a heap
    # claim or LOW_SEG rather than over the image (clo_keepboot, clo_fin,
    # clo_issrc, clo_zerohdr). Refusing them would refuse correct code.
    LODS = re.compile(r'^\s*(?:[A-Za-z_]\w*:\s*)?(?:rep\w*\s+)?lods[bwd]?\b',
                      re.I)
    m_bad = []
    for f in kfiles:
        for sect, n, line in sections(f):
            if sect in MODS and LODS.match(line):
                m_bad.append((f, n, sect, line.strip()[:50]))
    for f, n, sect, src in m_bad:
        print("%s:%d: lods in %s reads DS:SI, which is the KERNEL: %s"
              % (f, n, sect, src), file=sys.stderr)
    if m_bad:
        sys.exit("os88ovlchk: %d lods in a module image - SPEC.md 2.8.6 (a "
                 "module's own data is CS-relative: mov al, [cs:si])"
                 % len(m_bad))
    print("os88ovlchk: no module image reads its data through DS")

    # --- and no TAIL CALL to a cw_ shim -------------------------------------
    # A cw_ shim is `call <target>` / `retf`: it exists to turn a far CALL
    # from cold code into a near call plus a far return.  Reaching it with a
    # `jmp` instead leaves no far frame, so the shim's `retf` pops the
    # JUMPING routine's near return address as CS:IP - a wild jump into
    # whatever segment that word happens to name.
    #
    # It is easy to write by accident, because a near tail call
    # (`jmp gfx_xor_fill`) is an ordinary idiom in this kernel and the
    # conversion to a shim looks mechanical.  desk_zone_hilite ended that way
    # and froze the machine on the first click on a drive zone, with the gfx
    # lock held; and drv_task's `.die` did the same and got away with it only
    # because task_exit never comes back.  Neither is visible to the near-call
    # check above: both ARE far transfers, which is exactly what it wants.
    JSHIM = re.compile(r'\bjmp\s+(?:far\s+)?\w+\s*:\s*cw_(\w+)')
    j_bad = []
    for f in files:
        for sect, n, line in sections(f):
            m = JSHIM.search(line)
            if m:
                j_bad.append((f, n, m.group(1)))
    for f, n, tgt in j_bad:
        print("%s:%d: jmp to cw_%s - a shim ends in retf, so this pops a near "
              "frame as CS:IP" % (f, n, tgt), file=sys.stderr)
    if j_bad:
        sys.exit("os88ovlchk: %d tail call(s) to a cw_ shim - use call + ret"
                 % len(j_bad))
    print("os88ovlchk: no tail call reaches a cw_ shim")

    # --- and .lowbss / .vgabuf are reached through SS or ES, never DS -------
    # SPEC.md 2.1: those two sections are in LOW_SEG and VGABUF_SEG and DS is
    # KERNEL_SEG for all kernel code, so a BARE reference to a symbol declared
    # in either reads the kernel's own image at that offset.  It assembles
    # cleanly and runs wrong, which is the whole family this file exists for.
    #
    # `.vgabuf` is here for SPEC.md 39.22's reason and is not a special case:
    # it is a rung of its own above `.lowbss` and is just as unreachable
    # through DS, so the same rule binds it.
    #
    # THE EXEMPTION IS A BANK, AND IT NAMES ITS SEGMENT - which is the whole
    # of why it names one.  A routine may point DS at one of these segments
    # for a hot loop (vga_blit_prow does, so its table costs no override byte
    # a pixel), and inside such a bank the bare reference is the correct one
    # FOR THAT SEGMENT ONLY.  `; ovlchk: DS = VGABUF_SEG` opens one and
    # `; ovlchk: DS restored` closes it.
    #
    # A bank that exempted EVERYTHING would be blind in precisely the place
    # the hazard is: SPEC.md 39.22 moved two buffers out of `.lowbss` into
    # `.vgabuf` and left three `.lowbss` words being read inside the decoder's
    # bank, each of which needed an `ss:` it had never needed before.  So the
    # symbol carries the segment its section lives in and the bank is checked
    # against it - inside a VGABUF_SEG bank a bare `.vgabuf` word is right and
    # a bare `.lowbss` word is the bug.
    SECT_SEG = {'.lowbss': 'LOW_SEG', '.vgabuf': 'VGABUF_SEG'}
    lb = {}
    for f in kfiles:
        for sect, n, line in sections(f):
            if sect not in SECT_SEG:
                continue
            m = re.match(r'^\s*([A-Za-z_]\w*)\s*:?\s*(?:res[bwdqt])\b', line)
            if m:
                lb[m.group(1)] = SECT_SEG[sect]
    # `\b` on both sides so `vid_rowtab` does not match `vid_rowtab2` and
    # `font_zero` does not match inside `xfont_zero`.
    MEMREF = re.compile(r'\[\s*(?:(\w\w)\s*:)?([^\]]*)\]')
    OPEN = re.compile(r';\s*ovlchk:\s*DS\s*=\s*(\w+_SEG)\b', re.I)
    SHUT = re.compile(r';\s*ovlchk:\s*DS\s+restored\b', re.I)
    l_bad = []
    for f in files:
        low, opened_at = False, 0
        for n, raw in enumerate(open(f), 1):
            if OPEN.search(raw):
                if low:
                    l_bad.append((f, n, '(nested)', 'a DS bank inside a DS bank'))
                low, opened_at = True, n
            elif SHUT.search(raw):
                if not low:
                    l_bad.append((f, n, '(unopened)', 'DS restored, never banked'))
                low = False
        if low:
            l_bad.append((f, opened_at, '(unclosed)',
                          'a DS bank with no "DS restored"'))
    for f in files:
        bank = None                  # the segment DS is banked to, if any
        for sect, n, line, raw in sections_raw(f):
            m = OPEN.search(raw)
            if m:
                bank = m.group(1).upper()
            elif SHUT.search(raw):
                bank = None
            if sect in SECT_SEG:
                continue             # the declarations themselves
            for m in MEMREF.finditer(line):
                seg = (m.group(1) or '').lower()
                if seg in ('ss', 'es', 'cs'):
                    continue
                for w in re.findall(r'\b\w+\b', m.group(2)):
                    if w not in lb or lb[w] == bank:
                        continue
                    l_bad.append((f, n, w, 'reached without ss: or es:'
                                  if bank is None else
                                  'is %s, but DS is banked to %s here'
                                  % (lb[w], bank)))
    for f, n, sym, why in l_bad:
        print("%s:%d: %s - %s (SPEC.md 2.1/39.22)" % (f, n, sym, why),
              file=sys.stderr)
    if l_bad:
        sys.exit("os88ovlchk: %d .lowbss/.vgabuf finding(s) - SPEC.md 2.1 "
                 "(LOW_SEG and VGABUF_SEG are reached through SS or ES)"
                 % len(l_bad))
    print("os88ovlchk: every .lowbss/.vgabuf reference names SS or ES "
          "(%d symbols)" % len(lb))

    # --- and a routine's RETURN KIND matches how it is called ---------------
    # `ret` pops two bytes and `retf` pops four.  Get it the wrong way round
    # and the machine does not fault: it resumes at whatever the next word on
    # the stack happens to name, which on a task stack is live data.  Nothing
    # else here can see it - the near-call check above is about the CALL's
    # displacement and says nothing about the RETURN.
    #
    # It became checkable, and necessary, when SPEC.md 2.6.1 deleted 84 of the
    # `Xf_: call Y_x / retf` thunks by giving the body a `retf` of its own.
    # That is a 340-byte saving and one keystroke away from a wild jump: a
    # future near `call Y_x` from inside the same segment assembles perfectly
    # and returns into nowhere.  This is the rule that refuses it, and it
    # caught two real ones the first time it ran (two bodies had a SECOND
    # thunk nobody had noticed).
    #
    # A proc is classified by the return instructions inside its extent - from
    # its label to the next top-level one.  Anything mixed, or holding an
    # `iret`, is not classified and not judged: an interrupt handler and a
    # dual-entry routine are both legitimate and neither is this rule's
    # business.  An INDIRECT call (`call bx`, a `dw` table) is invisible here
    # exactly as it is to the near-call check, and stays a review rule.
    RETI = re.compile(r'^\s*(?:[A-Za-z_.]\w*:\s*)?(ret|retf|retn|iret)\b', re.I)
    TOPL = re.compile(r'^([A-Za-z_]\w*):')
    FARC = re.compile(r'\bcall\s+(?:far\s+)?\w+\s*:\s*([A-Za-z_]\w*)')
    NRC  = re.compile(r'\bcall\s+(?:near\s+)?([A-Za-z_]\w*)\s*$')
    #
    # A LABEL IS COLLECTED AS A LIST OF EXTENTS, NOT AS ONE.  `%ifdef
    # KERN_BIG` / `%else` is the ordinary shape for a routine whose small-
    # kernel answer is a refusing stub, so `X_x` is TWO extents in one file -
    # and this used to keep one entry per label, `rets[cur] = seen`, so
    # whichever arm came last in the file classified the label and the other
    # arm was never looked at.  osapi_drv_dlg_x is exactly that: `ret` in the
    # KERN_BIG body, `retf` in the stub, far-called from the resident
    # trampoline - and the stub's retf waved the shipped kernel's near return
    # through.  Merging the arms into one set is the WRONG repair and was
    # tried: kindof() already declines to judge a mixed extent, so merging
    # turns a reported defect into an unreported one.  Each definition is
    # classified on its own and a call is refused if ANY of them disagrees.
    rets = {}
    for f in files:
        cur, seen = None, set()
        for sect, n, line in sections(f):
            m = TOPL.match(line)
            if m:
                if cur:
                    rets.setdefault(cur, []).append(seen)
                cur, seen = m.group(1), set()
            r = RETI.match(line)
            if r and cur:
                seen.add(r.group(1).lower())
        if cur:
            rets.setdefault(cur, []).append(seen)

    def kind1(r):
        if not r or 'iret' in r:
            return None
        if r == {'retf'}:
            return 'far'
        if r <= {'ret', 'retn'}:
            return 'near'
        return None                  # mixed: not this rule's business

    def kinds(lab):
        # every definition's classification, the unjudgeable ones dropped
        return set(k for k in map(kind1, rets.get(lab, ())) if k)

    r_bad = []
    for f in files:
        for sect, n, line in sections(f):
            for lab in FARC.findall(line):
                if 'near' in kinds(lab):
                    r_bad.append((f, n, lab, 'far-called, ends in a NEAR ret'))
            m = NRC.search(line)
            if m and 'far' in kinds(m.group(1)):
                r_bad.append((f, n, m.group(1), 'near-called, ends in RETF'))
    for f, n, lab, why in r_bad:
        print("%s:%d: %s is %s" % (f, n, lab, why), file=sys.stderr)
    if r_bad:
        sys.exit("os88ovlchk: %d return-kind mismatch(es) - SPEC.md 2.6.1 (a "
                 "far entry ends in retf and is never near-called)" % len(r_bad))
    print("os88ovlchk: every return kind matches how the routine is called")

    # --- and no far TAIL JUMP into a far entry either -----------------------
    # The cw_ rule above covers ONE direction of two.  A cw_ shim is
    # `call X / retf` in `.text`, reached from `.cold`; the `.text` -> `.cold`
    # far entries (cpf_, fmf_, dwf_, dkf_, ldf_, drvf_, uif_, ...) are the
    # SAME two instructions pointing the other way, and reaching one with
    # `jmp SEG:entry` has the identical failure: the jump pushes nothing, so
    # the entry's `retf` pops the JUMPING routine's near return address as IP
    # and whatever sits above it on the stack as CS.  A wild jump, and the
    # JSHIM regex above never named these labels because it matches `cw_` only.
    #
    # A far tail jump IS correct from a routine that was itself far-entered:
    # then the far frame the `retf` consumes is the one its own caller pushed.
    # That is the whole exemption, and it is decided by the same `kinds()` map
    # the return-kind rule already builds - so a body must PROVE it is far
    # (`retf` and nothing else) to be allowed one.
    JFAR = re.compile(r'\bjmp\s+(?:far\s+)?\w+\s*:\s*([A-Za-z_]\w*)')
    t_bad = []
    for f in files:
        cur = None
        for sect, n, line in sections(f):
            m = TOPL.match(line)
            if m:
                cur = m.group(1)
            m = JFAR.search(line)
            if m and 'far' in kinds(m.group(1)) and kinds(cur) != {'far'}:
                t_bad.append((f, n, m.group(1), cur or '(file head)'))
    for f, n, tgt, cur in t_bad:
        print("%s:%d: jmp to %s - it ends in retf, and %s does not, so the "
              "retf pops a near frame as CS:IP" % (f, n, tgt, cur),
              file=sys.stderr)
    if t_bad:
        sys.exit("os88ovlchk: %d far tail call(s) into a retf entry from a "
                 "near-returning body - use call + ret" % len(t_bad))
    print("os88ovlchk: no far tail jump enters a retf body without a far frame")

    # --- and a BLOB entry ends in retf, whichever macro names it ------------
    # The rule above judges a call it can SEE. The blob's entries are reached
    # by an indirect far call - `mov word [spl_fp], X` / `call far [spl_fp]`,
    # inside SPLCALL / OVLCALL / OVLCALLC / SPLGATE1 / OVLGATE1 / SPLSTUB - and
    # the only textual trace of X at the site is an operand of a `mov`. So
    # FARC never matched one, and an entry that kept its near `ret` popped IP,
    # left CS on the stack, and returned into whatever the word above it named.
    #
    # Every entry in the tree happened to be a `call body / retf` trampoline,
    # so the hole was invisible until SPEC.md 2.5.3 started moving BODIES into
    # `.ovl` and naming them directly - which is the right shape (SPEC.md
    # 2.6.1: the body owns the far return and the thunk in the middle is
    # deleted) and is one keystroke from a wild return. It was written wrong
    # here first, twice, and neither nasm nor any other check in this file said
    # anything.
    #
    # The macro name is the whole signal and that is deliberate: a site says
    # `OVLGATE1 sched_init` and nothing else in the line is a call, so this is
    # the one place the target can be read at all.
    # OVWCALL is in here for the same reason as the rest: it is a FAR call, so
    # its target owes a `retf` exactly as a blob entry does. Leaving it out was
    # not hypothetical - the sweep that created `.ovlw` moved 78 bodies and
    # this check stopped looking at every one of them.
    BLOBCALL = re.compile(r'^\s*(?:(?:SPL|OVL)(?:CALL|CALLC|GATE|GATE1|STUB)'
                          r'|OVWCALL)\s+([A-Za-z_]\w*)\s*$')
    b_bad = []
    for f in files:
        for sect, n, line in sections(f):
            m = BLOBCALL.match(line)
            if not m:
                continue
            if 'near' in kinds(m.group(1)):
                b_bad.append((f, n, m.group(1)))
    for f, n, lab in b_bad:
        print("%s:%d: %s is reached through `call far [spl_fp]` and ends in a "
              "NEAR ret" % (f, n, lab), file=sys.stderr)
    if b_bad:
        sys.exit("os88ovlchk: %d blob entry(ies) end in a near ret - every "
                 "SPLCALL/OVLCALL/OVLGATE target is entered with a FAR call, "
                 "so it ends in retf (SPEC.md 2.5.3, 2.6.1)" % len(b_bad))
    print("os88ovlchk: every blob entry ends in retf")



if __name__ == '__main__':
    main()
