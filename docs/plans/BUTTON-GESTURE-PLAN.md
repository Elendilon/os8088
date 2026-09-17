# BUTTON-GESTURE-PLAN.md — the button is the one control the SDK never composed

**STATUS: PROPOSED. Nothing here is built.** Measured on `elendilon-next` at
`4eaabc3e`, 2026-09-17. Every byte figure below that is marked MEASURED comes
off a `nasm -l` listing of the shipped source; every figure marked PREDICTED is
an estimate against a measured comparable and is flagged as such at the point
of use. BUTTON-GESTURE-PLAN §7.3 is the list of what must be measured before
this is taken.

## 0. The report, and what it turned out to be

> *"a bug in dos.o88. None of the buttons are responding properly (action on
> mouse up, with held mouse down showing them inverted)."*

Confirmed, and it is not one package. DOS fires every button on the **press**
and draws no pressed state at all. Nine other shipped packages do the same
thing, for 25 of the tree's 51 `os88ui_btn` call sites.

**The finding is not that ten authors were careless.** It is that
`apps/os88ui.inc` composes the check box, the radio button and the drop-down —
the library owns their whole gesture — and does **not** compose the button,
which is the oldest and by far the most-used control in the system. DOS is the
proof in a single file: it drives `os88ui_rad`, `os88ui_chk` and
`os88ui_drpress` **correctly**, in the same source, a few hundred lines from
the four buttons it gets wrong. The author did not know less about buttons than
about radios. The library asked less of them about radios.

## 1. What DOS actually does

| | |
|---|---|
| draws with the standard control | **yes** — four `call os88ui_btn`, correct rects, correct flags |
| radios / checks / drop-downs | **correct** — `os88ui_rad`, `os88ui_chk`, `os88ui_drpress`/`drdrag`/`drup` |
| fires on | **the PRESS** — `dos.asm:10092` puts `dos_click` in the template's `W_ONCLICK` word; `dos_click` calls `os88ui_bhit` inline four times and acts immediately (`dos_go`, `dos_sav_go`, and the two page swaps) |
| `OSAPI_WM_ONMOUSEUP` | **never installed** |
| `OSAPI_WM_ONDRAG` | **never installed** |
| `OS88UI_DOWN` | **never passed** — so no pressed look, and no slide-off cancel |

`W_ONCLICK` is a template word and `W_ONMOUSEUP` deliberately is not (§13.7),
so omitting the release half is **silence, not an error**. Nothing warns,
nothing fails to assemble, and the result looks complete.

MEASURED — the press path that would convert: `dos_click` **173** bytes,
`dos_click_mem` **187**, `dos_place` **43**; 403 together, in a 36,772-byte
image.

## 2. THE SURVEY — all 51 caller sites

51 `call os88ui_btn` sites in 30 files, plus 2 inside `os88ui.inc` itself (the
About card's row, which is correct and is the library's own).

### 2.1 Release-fired — correct

| carrier | sites | how |
|---|---|---|
| `apps/calc` | 1 | `bfind`/`arm`/`armed`/`fire`, `cal_setdown`; the model implementation |
| `apps/recorder` | 1 | same shape |
| `apps/texpad` | 1 | same shape |
| `apps/paint` | 1 | same shape (§42.7's fullscreen path polls its own input and is separate) |
| `apps/piano` | 1 | the two buttons fire on the release; **the KEYS keep the press deliberately** — a note is §13.6's safe prefix action |
| `apps/skies` | 2 | same shape |
| `apps/ftpd` | 3 | same shape |
| `apps/weave` | 2 | correct, through the **C SDK** — `os88_wm_onmouseup()`, not `OSAPI_WM_ONMOUSEUP`. See BUTTON-GESTURE-PLAN §6.3: a gate that greps only the asm spelling reads Weave as broken |
| `drivers/hdd` | 4 | §13.8.4, through `cp_ctl`/`cp_pgprobe` |
| `drivers/ether` | 4 | as above |
| `drivers/net` | 1 | as above |
| `drivers/ramdisk` | 1 | as above |
| `drivers/saver` | 1 | as above |
| `kernel/fdlg.inc` | 1 | §13.8.3 |
| `kernel/files.inc` | 1 | §13.8.3 |
| `kernel/apps.inc` | 1 | §13.8.5 |

### 2.2 Press-fired — the defect, 25 sites in 10 packages

Ordered by how much a user meets them.

| carrier | sites | where it fires | note |
|---|---|---|---|
| `apps/sheet` | **10** | `sh_onclick` | the largest single carrier. It **does** install `W_ONMOUSEUP` — `sh_onmouseup` handles the scroll-bar thumb and nothing else, which is why a package-level grep reads it as converted |
| `apps/dos` | 4 | `dos_click` | the reported bug |
| `apps/word` | 2 | `wd_dgclick` → `wd_dgok`/`wd_dgcancel`/`wd_dgno` | dialog OK/Cancel/No. Keeps its own `wd_dghit` rather than `os88ui_bhit`. Menus legitimately use a polling loop (§13.7's "pick one") — the **dialogs** are the defect |
| `apps/scribe` | 2 | `sc_dgctl` / `sc_abopen` | Word's shape, same code lineage |
| `apps/thewire` | 2 | `wr_onclick` | |
| `apps/telnet` | 1 | `te_onclick` | |
| `apps/browser` | 1 | `br_btn1` | installs `W_ONMOUSEUP` for selection, not for the button |
| `apps/notepad` | 1 | the find panel | on UIHELPERS-PLAN §15.4's list since it was written |
| `apps/artful` | 1 | `at_btnhit` | its own x/y/width test — the two-descriptions drift §20.5.1's rect pointer exists to stop, still live |
| `apps/audio` | 1 | `apu_hit` in `W_ONCLICK` → `ap_dispatch_btn` | and it **does** pass `OS88UI_DOWN` — as a *toggle* indicator for Shuffle/Repeat, never as a press state. BUTTON-GESTURE-PLAN §9.2 |

### 2.3 The dates are the argument

`docs/plans/completed/UIHELPERS-PLAN.md` §15.4 is a survey table of exactly
this defect, and it names `word`, `notepad` and `artful`. **Every other package
in BUTTON-GESTURE-PLAN §2.2 landed after that table was written.** `dos`,
`sheet`, `scribe`, `thewire`, `telnet`, `browser` and `audio` are seven
packages that reintroduced a defect the tree had already surveyed, fixed in
eleven places, and written down.

## 3. Why it keeps happening

### 3.1 The button is the only major control the library does not COMPOSE

| control | the library gives you | who owns the gesture |
|---|---|---|
| drop-down | `os88ui_drop` / `drpress` / `drdrag` / `drup` over one record | **the library** |
| radio | `os88ui_rad` / `os88ui_radhit` over one record | **the library** |
| check box | `os88ui_chk` / `os88ui_chkhit` over one record | **the library** |
| **button** | a painter, a predicate, and three accessors over one word | **you**, every time |

`os88ui_btn` draws. `os88ui_bhit`/`os88ui_bfind` answer *is the point in it*.
`os88ui_arm`/`os88ui_fire`/`os88ui_armed` are three four-to-ten-byte accessors
over a single `dw 0`. **Nothing composes them**, so composing them is the
application author's job — and it is the same composition every time.

### 3.2 Wrong is one call; right is seven obligations across three callbacks

To get one button right an author must, in order:

1. install `OSAPI_WM_ONMOUSEUP` after `wm_create` — not a template word
   (§13.7);
2. install `OSAPI_WM_ONDRAG` — likewise, and **CF = 1 on `kern_small`**
(§13.8.2), so it needs a degraded arm as well;
3. in `W_ONCLICK`: recompute the layout from `OSAPI_WM_CONTENT`, `bfind`,
   `arm`,
draw down;
4. in `W_ONDRAG`: `armed` (**not** `fire`), `bfind`, compare, redraw **only on
   a
change** — a redraw per mouse packet is PERFORMANCE.md's input overrun;
5. in `W_ONMOUSEUP`: draw up **first and unconditionally**, then `fire`,
`bfind`, compare, and only then act;
6. write the one-control painter that (5) and (4) both call;
7. keep `W_PAINT` passing `OS88UI_DOWN` from the same state, or a repaint
mid-press disagrees with the glass (§13.8).

Miss any one and it still assembles. Miss (1) and the other six never run.
**The wrong version is `call os88ui_bhit` / `jc` / act — three instructions
that look finished.**

### 3.3 The correctness effort was a SURVEY, not a GATE — and the tree said so

SPEC.md §13.8.4 records the last recurrence and predicts this one in as many
words. The driver Control Panel pages were *"silently missed"* by §13.8.3's
conversion, and:

> **the same shape will recur at every ABI boundary this feature crosses.**

It has, seven times. A survey in a plan document ages the moment the next
package lands; it cannot fail a build. **The tree already owns the instrument
that can** — `tests/textsites.txt`, `movable.txt`, `ovlrefs.txt`,
`dosseam.txt`, `toastlong.txt` are five ratchet registries with fast-tier
tests. None of them points at buttons.

## 4. MEASURED — what a correct gesture costs today, three times over

Symbol spans from `nasm -l`, shipped source:

| package | `W_ONCLICK` | `W_ONDRAG` | `W_ONMOUSEUP` | painter/count | total |
|---|---|---|---|---|---|
| `apps/calc` | 45 | 52 | 92 | 47 | **236** |
| `apps/recorder` | 61 | 66 | 101 | — | **228** |
| `apps/piano` | 144 | 39 | 51 | — | **234** |
| `apps/texpad` | 334 | 113 | 89 | — | 536 |

Texpad's `W_ONCLICK` also places a caret, so its total is not comparable; the
other three are.

**The finding is the consistency: ~230 bytes, written three times, doing the
same thing.** That is `os88ui.inc`'s own scroll-bar argument (§13.10) arriving
one control over — *five private implementations of one widget* — except that
here the count is ten packages that did not write it at all plus eight that
did.

What the library already carries, MEASURED in the same listings:

| | bytes |
|---|---|
| `os88ui_btn` (painter) | 277 |
| `os88ui_bhit` | 23 |
| `os88ui_bfind` | 33 |
| `os88ui_arm` + `os88ui_fire` + `os88ui_armed` + the word | 20 |
| | **353** |

## 5. THE PROPOSAL — `os88ui_bpanel`, in the drop-down's shape

A record-based button panel, so the composition happens once in the library
instead of once per package. It is deliberately **not** a new look, a new
painter or a new policy: it is `os88ui_btn` plus the four calls every correct
caller already makes, with the state that sequences them moved into the
caller's record.

### 5.1 The record, in the caller's data

```
my_panel:
    dw  my_rects        ; OS88UI_BP_RECTS: an array of 4-word rects, SCREEN
                        ; coords, filled by YOUR painter from OSAPI_WM_CONTENT
    dw  my_labels       ; OS88UI_BP_LABELS: near ptrs to NUL strings
    dw  4               ; OS88UI_BP_N: how many are LIVE this pass
    dw  0               ; OS88UI_BP_FLAGS: near ptr to a per-button flag byte
                        ; array (OS88UI_DIS, OS88UI_DEF, OS88UI_INK), or 0
    dw  0               ; OS88UI_BP_WIN: your window ptr
    dw  0               ; OS88UI_BP_DOWN: which is drawn pressed, 0 = none.
                        ; THE LIBRARY'S - read it from W_PAINT, never write it
```

`OS88UI_BP_N` being a per-pass count is what lets one record serve a package
with pages: DOS points it at the main page's two rects or the setup page's two.
It is `cal_nrect`'s own device (calc already varies its count to hide the
history rows), promoted into the record.

### 5.2 The four entries

| call it from | entry | what it does |
|---|---|---|
| `W_PAINT` | `os88ui_bpaint` | draws all `N`, passing `OS88UI_DOWN` for `BP_DOWN` — so **a repaint agrees with the glass by construction**, which is §13.8's whole argument for a drawn state over an XOR |
| `W_ONCLICK` | `os88ui_bppress` | `bfind`, `arm`, draw down. Out: `AX` = index+1 spent here, 0 = not ours, hand the press on |
| `W_ONDRAG` | `os88ui_bpdrag` | `armed`, `bfind`, compare, **redraw only on a change**. Nothing to test |
| `W_ONMOUSEUP` | `os88ui_bpup` | draws up first, then `fire`, `bfind`, compare. Out: `AX` = the button that FIRED, 0 = cancelled |

An application's whole obligation becomes: declare the record, fill the rects
in the painter it already has, call four one-liners, and switch on `bpup`'s
answer. **Obligations 3 to 7 of BUTTON-GESTURE-PLAN §3.2 stop existing.**
Obligations 1 and 2 remain and are the subject of BUTTON-GESTURE-PLAN §5.4.

### 5.3 It is opt-in, like the scroll bar

Behind `OS88UI_BPANEL`, `OS88UI_SCROLL`'s gate exactly, so a package that draws
one decorative button pays nothing. Every package that does not define it must
assemble **byte-identical** — that is a gate, not an intention
(BUTTON-GESTURE-PLAN §10).

### 5.4 `kern_small` degrades, it does not refuse

`OSAPI_WM_ONDRAG` answers **CF = 1** on `kern_small` (§13.8.2). `os88ui_bpanel`
must therefore work with no drag edge at all: press arms and draws down,
release fires or cancels, and the control simply does not un-draw while the
pointer slides off. That is strictly better than today and matches what the
kernel's own dialogs do there. **The install is the library's job, not the
caller's** — a `os88ui_bpinit(BX = window)` that installs both slots and
ignores a CF from the drag one is what removes obligations 1 and 2, and it is
the single highest-value part of this proposal, because those two are the ones
whose omission is silent.

## 6. THE GATE — `tests/btnsites.txt`

`tests/textsites.txt`'s shape exactly, because that is the mechanism this tree
already trusts and BUTTON-GESTURE-PLAN §3.3 is the argument that a survey is
not one.

### 6.1 Format

```
# <count> <path>   # <verdict>: <reason>
4  apps/dos/dos.asm        # press: BACKLOG - fires in dos_click (SPEC.md 96.32.1)
1  apps/piano/piano.asm    # press: the KEYS are 13.6's safe prefix action
1  apps/calc/calc.asm      # release: bfind/arm/fire + cal_setdown
```

### 6.2 What it fails on

1. a file calling `os88ui_btn` that is **not in the registry** — the case that
matters, because it is what the next package hits;
2. a file **exceeding** its count;
3. a count that is now too **high**, so a conversion has to lower the number
and the diff says the work happened;
4. a `press:` verdict with no reason, or the reason `backlog:` with nothing
after it.

It starts at the tree's real numbers — 25 press-fired sites registered as
`backlog:` — because a rule that cannot be enforced from the day it is written
is not enforced at all. What it stops from day one is the count going **up**.

### 6.3 Three spellings it has to know, and each has already fooled a grep

- **the C SDK**: `os88_wm_onmouseup()`, not `OSAPI_WM_ONMOUSEUP`. Weave is
correct and a naive grep reads it as broken (BUTTON-GESTURE-PLAN §2.1).
- **the driver pages**: `cp_ctl`/`cp_pgprobe`, not `W_ONMOUSEUP` at all
(§13.8.4). Five drivers are correct by a mechanism the package rule does not
describe.
- **installed for something else**: Sheet and Browser both install
`W_ONMOUSEUP` for scroll thumbs and text selection while their buttons fire
on the press. **A package-level "does it install the slot" test passes both
and is worse than no test**, which is why the registry is per FILE with a
per-site count and a written verdict, and not a predicate.

## 7. COST

### 7.1 MEASURED

| | bytes |
|---|---|
| the library's existing button block | 353 |
| calc's private gesture | 236 |
| recorder's | 228 |
| piano's | 234 |
| DOS's press ladder (the conversion's working area) | 403 |

### 7.2 PREDICTED — and this is an estimate, not a measurement

`os88ui_bpanel`'s four entries plus `bpinit`, against the three ~230-byte
private gestures they replace: **~260–300 bytes**, PREDICTED. The basis is that
the three private versions agree to within 8 bytes of each other, and that the
library version does strictly less than any of them — it has no application
dispatch in it, which is 40–90 bytes of each of the three measured totals — but
must carry the record indirection they do not, and `bpinit`.

Per package, PREDICTED: a converted carrier that already has a private gesture
gives back ~230 and spends ~280, so **the eight correct packages cost ~50 bytes
each** and the ten broken ones spend ~280 to gain a correct gesture they do not
have. On DOS's 36,772-byte image that is 0.8%.

**Do not quote either number as decided.** GFX-EMBEDDABLE-PLAN §9.1.1 is the
standing warning and it applies squarely here: wave 5 of that plan came out a
**fifth** of its costed size because the costing priced capabilities the shared
routine turned out not to need.

### 7.3 What must be MEASURED before this is taken

1. `os88ui_bpanel` built and its symbol span read — not `kernel.bin`'s size and
not a padded artefact (CLAUDE.md's rungs banner; the `gfx_points` worked
example is 472 against 215 where the file said 0).
2. The **disk** figure, not just RAM: a package image is compressed (§20.13),
and code does not compress like the bitmaps CTRL-GLYPH-PLAN measured. The
360KB geometry is at 346 of 354 clusters, so this is the binding number.
3. `kern_small`'s arm, because `SMALLAPPS` builds five of these packages
smaller and the panel must not be what puts one over.
4. The **byte-identical** check on every package that does not opt in.

## 8. CONVERSION ORDER

By how much a user meets the control, which is UIHELPERS-PLAN §15.4's own
ordering rule.

1. **`apps/dos`** — the reported bug, 4 sites, and the proving conversion: it
already drives three composed controls correctly, so it is the cleanest test
of whether the fourth reads the same way.
2. **`apps/sheet`** — 10 sites, the largest carrier.
3. **`apps/word` + `apps/scribe`** — 4 sites, one shape, shared lineage; the
dialog OK/Cancel/No are the most-pressed buttons in either program.
4. **`apps/thewire`, `apps/telnet`, `apps/browser`, `apps/notepad`** — 5 sites.
5. **`apps/artful`** — 1 site, and it converts `at_btnhit` away at the same
time, which is the §20.5.1 drift.
6. **`apps/audio`** — 1 site, and it is the only one with a design question in
it (BUTTON-GESTURE-PLAN §9.2).
7. **The eight correct packages** — optional, and last. They work. Converting
them is a size and consistency question, not a defect one, and
BUTTON-GESTURE-PLAN §7.2 says it
may cost ~50 bytes each.

The gate (BUTTON-GESTURE-PLAN §6) lands with step 1, not at the end. That is
the whole point: it is what makes steps 2–7 optional rather than urgent, and
what stops an eleventh package joining the list while they are being done.

## 9. REFUSALS AND DELIBERATE EXCLUSIONS

### 9.1 The controls that keep the press

§13.6's safe-prefix-action rule stands and is not weakened here: **Piano's
keys** (a note is the action and is safe), **Sheet's grid cells**, **Paint's
canvas**, a text caret, and a list-row *selection*. These are not buttons and
must not be registered as ones. `os88ui_bpanel` covers the standard button and
nothing else.

### 9.2 Audio's `OS88UI_DOWN` is a TOGGLE, and that is a real question

`apu_btn` passes `OS88UI_DOWN` for Shuffle and Repeat when the setting is
**on** — a latched state, not a press state. A converted panel drives
`OS88UI_DOWN` from `BP_DOWN`, so the two meanings collide on one flag.
**Unresolved.** The options are a second flag (`OS88UI_LATCH`, drawn
identically, OR-ed by the caller), or Audio keeping its own painter for those
two. It is one package and one pair of buttons, and it should not hold up the
other nine.

### 9.3 Not converting the bevelled transports

UIHELPERS-PLAN §15.4 row D is unchanged: ModPlug's LED transport (§56),
Tracker's FT2 bevel (§45), Minesweeper's cell (§23). They are not `os88ui_btn`
callers and converting them undoes intended design.

### 9.4 A polling tracking loop stays legal

§13.7 says pick one, and Word's **menus** correctly pick the loop. This plan
does not touch them. Only Word's dialog buttons are in BUTTON-GESTURE-PLAN
§2.2.

## 10. TESTING

- `tests/unit/t_btnrules.py`, fast tier — the BUTTON-GESTURE-PLAN §6 ratchet.
  `t_textrules.py` is
the model and most of it is reusable.
- **Byte-identical** assertion for every package that does not define
`OS88UI_BPANEL` (BUTTON-GESTURE-PLAN §5.3), in the shape
`tests/unit/t_appsmall.py` already uses
for the small-build arms.
- On the glass, per converted package, and it is the only thing that proves the
feature: press a button and **hold** — it inverts; slide off — it comes back
up; release outside — nothing happens; release on it — it fires. That is four
assertions and `tools/os88ui.py` has the verbs for all four.
- The soak rows the conversions can reach, scoped with `-k`, per
docs/TESTING.md. Not the tier.
- **Break it on purpose** (docs/WRITING-TESTS.md §1): delete the
`W_ONMOUSEUP` install from a converted package and watch the row go red. A
green row here is worth nothing otherwise, because press-fired and
release-fired buttons produce **identical screenshots** — which is
BUTTON-GESTURE-PLAN §11.

## 11. WHY NOBODY SAW IT

Worth recording, because it is why this survived ten packages and a survey.

A press-fired button and a release-fired button are **the same pixels** in
every still. The difference is visible only while a physical button is held
down, and no screenshot-driven test holds one down. PERFORMANCE.md names three
defects that are invisible in an emulator; this is a fourth, invisible in a
*screenshot* — and every gate in this tree that looks at a package's appearance
takes screenshots.

That is also why BUTTON-GESTURE-PLAN §6's gate is static analysis rather than a
driven test. The driven test is worth having (BUTTON-GESTURE-PLAN §10) and it
is not what will catch the eleventh package.

## 12. WHAT IS OPEN

1. **BUTTON-GESTURE-PLAN §9.2**, Audio's latched flag. One package, needs a
   decision.
2. Whether `bpinit` should install `W_ONDRAG` **and** `W_ONMOUSEUP`, or whether
a package that wants no drag edge should say so. Installing both
unconditionally is simpler and costs a slot write on `kern_big` and a
refused call on `kern_small`; it is probably right, and it is not measured.
3. Whether the eight correct packages convert at all (BUTTON-GESTURE-PLAN §8
   step 7). It is a size
question and BUTTON-GESTURE-PLAN §7.3 item 1 answers it.
4. Whether `os88ui_bpanel` should own the **glyph** controls' gesture too.
`os88ui_chkhit`/`os88ui_radhit` already exist, so the composition there is
half-done, and a panel that drove buttons, checks and radios from one record
is the obvious next shape. **Deliberately out of scope here** — it widens a
defect fix into a redesign, and the drop-down proves the per-control record
works.
