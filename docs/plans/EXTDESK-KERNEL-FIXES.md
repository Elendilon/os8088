# Extended-desktop kernel fixes: what is done, and what needs the owner

This plan covers the kernel half of the extended-desktop audit
(docs/reports/EXTENDED-DESKTOP-AUDIT-2026-11-27.md; finding IDs are the
report's). **The owner's limit:** across the whole effort the kernels may grow
by about 150 bytes in total, and any change that grows a kernel comes to the
owner first. So this file has two parts. Part 1 lists what has already landed,
none of which grows a kernel. Part 2 is everything that would, with a design
and a byte cost for each. Byte figures marked *measured* come from `kernsize`'s
sum after a build. Figures marked *est.* are instruction counts from the
design and have not been built. **"Resident" means `KERN_BUDGET`'s bytes.**
`EXTD.DRV` is an on-demand module (SPEC.md 2.8), so its bytes sit on the
system disk and in a heap claim while two displays are up, not in any
kernel's footprint. They are listed separately so the owner can count them
either way.

## Part 0: the owner's answers, and round 2 (2026-11-27)

**P1 is rejected, and the split it would have removed is the design.** In
the owner's words: *"for when they want to go fullscreen, the target screen
is not the more restrictive screen, it's the one they are mostly on. Same
for zoom: which screen do I maximize on? The one I am more on. On the other
hand, a window can't draw in two modes at once, so inside its window it
draws in the more restrictive mode or height."* So two questions keep two
answers:

- *Where do I go fullscreen or maximize?* `wm_disp_of`, the centre.
- *How do I size and draw at this position?* `wm_disp_now`, the
  restrictive display while straddling.

SPEC.md 39.17.2.1 has the table. Pixelstein, Lemmings and Missile are
fixed APP-side, by another agent.

A second owner rule came with it: *"Nothing should size wrong on a
maximize. If the window is straddling and they zoom it, when it finishes
zooming it's fully on one screen, and that is its answer for where it is,
what mode it should now be drawing in, and at what size."* P3 grew to carry
that.

**K2 under the owner's model** replaces P1's extra rule. A straddler is
sized for the restrictive display on BOTH axes, so on the free axis it is
never larger than the smaller display. Returning to one display restores
that display's size (SPEC.md 39.16.3.6). It also closes K2(a), P8's first
half.

**The 1px question.** Is P2's `vx - 1` a defect, or the effect of "zoomed
windows take up the full width" (SPEC.md 11.95.2)? It is **a defect, and it
breaks that rule rather than coming from it.**
- 11.95.2.1 already makes `wm_flush_ck` answer "spans its display" for a
  frame at display 1's `VX` with display 1's width, and wm_zoom commits
  exactly that rect.
- `wm_snap_ax` then rounded x = `VX` down to `VX - 1`. Measured,
  vgaherc-vga-right: a zoom on d1 gave (639,…), which neither spans its
  display nor sits on it.
- With the fix it gives (640,20) 720x347 with no left border, which is the
  full-width rule working on display 1. A drag to x = 643 now lands at 647
  wholly on d1 (it was 639).

### Round 2 status

The figures are `.text`+`.bss`+`.cold`+`.vga`+`.lowbss`+`.vgabuf`, measured
by `kernsize --json` per kernel, each against the commit before it.

| commit | item | kern_big | kern_small | kern_emu | kern_mega | EXTD.DRV image |
|---|---|---:|---:|---:|---:|---:|
| 1a2eb39a8 | **P2** (K4, K5 Right): display 1's left edge snaps like x = 0 | +16 | 0 | +16 | +16 | 0 |
| 900ea513e | **P3** + the owner's zoom rule (K5): `wm_box`, plus the zoom latch armed and spent through `EXT_SPAN` | +16 | **-2** | +16 | +16 | +52 (WIN95.DRV +1) |
| eb32a4453 | **K2** (owner's model; K2(a), K2(b)): straddle cap on both axes, `W_PKIND` bit 7 | 0 | 0 | 0 | 0 | +97 |
| 9de7632c5 | **OSAPI_WM_DORIGIN**, new JCELL 0x0244 (for L1 and DeskClok) | +24 | +8 | +24 | +28 | +12 |
| 13f26df0f | **OSAPI_GFX_SCROLL preserves ES** (SPEC.md 5.5) | +2 | +2 | +2 | +2 | 0 |
| ba274c422 | **P4** (K7): repaint the other card, and no refit of a straddle on exit | +6 | 0 | +6 | +6 | +62 |
| **round 2** | | **+64** | **+8** | **+64** | **+68** | **+223** |
| **whole effort** (round 1's -6 included) | | **+58** | **+2** | **+58** | **+62** | +231 |

Notes on the table:
- P3 on kern_small is -2: `wm_box` is one byte shorter there, and the
  PARITY byte in blank.inc that it made unnecessary went too.
- `make mega`'s megaseg allowance moved 3,787 -> 3,791. kern_mega's `KDS`
  in OSAPI_WM_DORIGIN is 3 bytes longer than kern_big's, plus 1 byte of
  layout. It is a dated line in tests/megaseg.txt (7230aa8e0).

**Stopped, for the owner:**

- **P5 (K8, the pointer homes to the primary's centre).** It was measured at
  **EXTD.DRV +72** against an estimate of +20, so it is stopped by the rule
  for items that come in over (resident 0). The design is unchanged:
  `vid_fsx_leave` and `ext_extend_b` bank `[mouse_x]`/`[mouse_y]` before
  their `vid_apply`s and put them back through one `ext_mput` (clamp with
  `vid_pt_clamp`, store under `cli`, set `[cur_disp]`). The bracket's
  point is local and gets the bracket display's `VX`/`VY` added. Two
  thirds of the bytes are the bank-and-restore plumbing. Dropping the
  Extend half saves about 19.
- **P7 (D3, a VGA as the CGA stays lit under a Hercules bracket).** The
  SR01-bit-5 design measured **EXTD.DRV +47** against +18. MartyPC's VGA
  parses SR01's screen-off bit and does not render it, so the fix cannot be
  seen there: the card stayed at 181,162 lit pixels with the fix in. The
  alternative reuses `vid_bk`'s planar arm (the Attribute Controller's
  Colour Plane Enable, which MartyPC does model). That is `test byte
  [vid_avail], VID_A_VGA / jnz .planar` in vid_bk's CGA arm, **+7 resident**
  on kern_big's three kernels. But its unblank writes 0Fh, and BIOS mode 6
  wants 01h: planes 1-3, plane 2's font among them, would show. So that arm
  needs its unblank value per mode before it is right. The owner chooses:
  SR01 (correct on hardware, invisible in MartyPC) or the AC route (needs
  the 01h case).
- **P6 (D1, kern_mega).** Not attempted this round, and the design needs one
  correction first. `cur_move_multi` copies each display's `vid_ctx`
  record into the live block through `vid_ctx_act`, so BOTH records'
  `vid_seg` words have to be made real segments too, not only display 1's.
  That makes `mega_vsw` four words (live, `k_vsa`, record 0, record 1).
  `mega_svc_back`, fsx.inc's restore and the reader at mega.inc ~8270 each
  put back two more. Estimate: conventional +4, `.mega` about +30. It needs
  86Box to verify (the D1 measurement was there).
- **gfx_scroll cut at the seam (optional).** Not done. The design follows
  the blit's (39.14.7.2): an `EXT_SCUT` slot reached from gfx_scroll's
  refusal when `[vid_ndisp]` > 1, splitting a RIGHT-layout rect at the
  seam into two same-row scrolls. A Below-layout rect has to keep refusing,
  because its rows cross cards. Resident is about 17 (an EXTCALL behind the
  gate, plus the slot's 4 of `.bss`), and the cut itself goes in EXTD.DRV.
  The cut has to happen before `GFXDENTERR` localises the rect. That is
  under the ~30 the owner allowed, but it touches the scroll's whole-shape
  clip contract (`wm_clip_test`), so it should land as its own reviewed
  item.

**P8's second half (K3)** stays as written: it is each package's own fix.
TeXPad, Word and SysCheck "keeping the other display's shape" should be
rechecked now that K2's landing gives the natural size back.

## Part 1: landed (no kernel grows)

| commit | finding | kern_big | kern_small | kern_emu | kern_mega | elsewhere |
|---|---|---:|---:|---:|---:|---|
| 1148edf60 | **K1**: a drag's y bound is the desktop's `[vid_h]`, not the primary's `[vid_ymax]` (SPEC.md 39.16.1.1) | -6 | -6 | -6 | -6 (`.text` +0) | EXTD.DRV +8 (EXT_DEAD checks the title bar's last row first) |
| 573a725b7 | **K2/K3 for Paint, the REGRESSION** (SPEC.md 42.9.2) | 0 | 0 | 0 | 0 | Paint +11 |

All six kernel figures are *measured*, as `kernsize` sums. Each comes from
`.boot2` -6. `.text` is +0 on every kernel: the y clamp's +3 is paid for by
the dropped word and an `xchg` in the x clamp.

**The regression's origin.** Paint was not broken by a size or speed pass. It
was broken by #365 (50968828b, 2026-11-16), which made Paint `WF_KEEPH`
(SPEC.md 42.9.1) so that its own grow box could reach the bottom row:
- `WF_KEEPH` tells the kernel never to take a height in.
- From then on, on a landing on another adapter, the only cut was Paint's
  negotiator, `pt_onsize`.
- `pt_onsize` capped the proposal at the previous display's `[pt_chmax]`,
  because the kernel asks (SPEC.md 11.1) before it notifies (11.98).
- Measured on cgaherc-herc-right, before → after the fix:
  - before: 300, 300, 300, 300, 200, 300, 200
  - after: 300, 200, 200, 200, 300, 200, 300

  (the walk is d0, straddle, d1, straddle, d0, d1, d0).

The kernel had already provided what the fix needed: `OSAPI_WM_DISPLAY`
answers the display the landing latched (39.16.4.2).

**Missile** is a different case, and it is not a regression. Its "back and
forth" between displays still works in the Right layouts it was designed on
(WINDOW-SIZING-PLAN 12). What fails is the Below layouts and the VGA pairing,
which arrived later. Its defects there are K2(b), K4 and K6 below.

**`make mega`'s megaseg gate.** It read 3,789 against an allowance of 3,787.
- f19793d (keypad 5) is **not** the cause, contrary to the audit.
- Built from clean trees, f4688f37e (the commit that wrote 3,787) and
  d6fb02f both read 3,789. Between them the only kernel change is a comment,
  and `kbm_isr` is 173 bytes on both kern_big and kern_mega.
- After K1 the tree reads **3,787** again: K1 moves the two kernels'
  `.text` + `.bss` by different amounts, and the gate measures that
  difference. So `make mega` passes again with `tests/megaseg.txt` untouched.
- The figure is clearly sensitive to layout. If it drifts again, the right
  fix is a dated correction line, not a hunt for 2 bytes: nothing grew.

## Part 2: for the owner

The costs in this part are mostly *estimates*. Each item says which audit
findings it closes. The totals at the end assume the recommended option
everywhere.

### P1. One answer to "which display is this window on" (K6, and it carries K2(b)) - REJECTED by the owner (Part 0)

There are two answers today:
- `wm_disp_of` uses the **centre**. It is resident in wm.inc and is used by
  fullscreen, `FSX_RUN`'s bracket, `wm_disp_xw` (snap, flush, zoom x) and the
  chrome test.
- `wm_disp_now` uses the **more restrictive display while straddling**. It
  lives in EXTD.DRV and is used by sizing, `OSAPI_WM_DISPLAY` and onresize.

SPEC.md 39.16.4.1 already calls the disagreement a defect. It is how
Pixelstein and Lemmings get refused, and how Missile ends up with one
display's depth and the other's frame.

- **Option A (recommended): everything asks `wm_disp_now`.**
  - `wm_disp_of`'s body (centre, origin, primary) becomes a gate: AL = 0 for
    one display, else an `EXTCALL` to a new slot whose arm is
    `call wm_disp_now / retf`.
  - Behaviour: a straddling window goes fullscreen on the display it was
    sized for, and every package sees one display.
  - Resident *est.*: about **-24** on kern_big, kern_emu and kern_mega (a
    40-byte body becomes 12, plus the slot's 4 bytes of `.bss`). kern_small
    0: it has no `wm_disp_of`. EXTD.DRV about +6.
  - **This pays for P2 to P4.**
- **Option B: everything asks the centre.** EXTD.DRV changes only, so 0
  resident. But it reverses WINDOW-SIZING-PLAN 12.2. A window sized for the
  taller display that straddles with its centre there hangs into the shorter
  one's dead zone unless it reflows, which is the letterbox trade 12.5
  settled. Not recommended without a new decision on 12.5.
- **K2(b) under either option.** A window sized for the VGA in a Below layout
  is too tall to sit wholly on the Hercules. Dragging it "onto" the
  Hercules leaves it straddling, so its kind never changes back. Under A the
  straddle's kind is still the narrower display's, so the loop remains.
  Breaking it is one more EXTD.DRV rule in `ui_drag_size`, 0 resident (*est.*
  +12 EXTD.DRV): **when the window's CENTRE is on a display whose kind
  differs from the straddle's, size for the centre's kind and snap the
  origin onto that display.** It needs the owner's word, because it is a
  third rule beside 12.2's two.

### P2. A snapped window can sit wholly on display 1 (K4)

`wm_snap_ax` moves x LEFT to the nearest x with x+1 a multiple of 8. For
x in [vx, vx+6] on a display whose vx is a multiple of 8 (every vx is), that
is **vx - 1**, one pixel onto the display to its left. Every `WF_SNAP` window
(Missile, isoTron, most of the tree) dragged or zoomed to the left edge of
display 1 therefore ends up straddling by 1px. The straddle then sizes it
for the restrictive kind (K4's 634x303 on a VGA). The existing x = 0..6
exception is this same rule for display 0.

- **Design:** after the round-down, when (CX+1) equals display 1's VX, add 8
  as the 0..6 arm does. Gate on `[vid_ndisp]` > 1, because a collapsed
  desktop leaves `vid_ctx[1]` stale.
- **Cost:** resident *est.* **+13** on kern_big, kern_emu and kern_mega
  (`cmp byte`, `jbe`, `mov`, `inc`, `cmp`, `jne`, the shared `add`).
  kern_small 0, under `%ifdef KERN_BIG`.
- **Variant:** an `EXTCALL` arm costs +8 resident (4 `.text`, 4 `.bss`) and
  +8 EXTD.DRV, and pays a far call to `mod_gone` on every snap on a one-display
  machine.
- Also closes K5's Right-layout "lands at vx - 1".

### P3. `wm_resize` (and so zoom) clamps into the window's own display (K5)

`wm_resize_nb` caps the height at the **primary's** band, floors y at
`MBAR_H` and holds `y + h` to the **primary's** dock row. Zoom commits
through it. So in Below, a window zoomed on display 1 is pulled up onto
display 0 at display 0's width, and a second zoom zooms again, because the
standard-state compare no longer matches.

- **Design:**
  - Factor `wm_fit`'s box load into `wm_box`: AX/CX x0 and xe, SI/DI y0 and
    ye, DX the floor, and `EXTCALL EXT_FITBOX` for the origin's display.
  - `wm_fit` and `wm_resize_nb` both call it.
  - In `wm_resize_nb`, read the registers in place of `[vid_dock_y0]`,
    `[vid_ph]` and `MBAR_H`.
  - Keep the union `[vid_w]` for the x bound. A straddler that resizes
    itself must not be pulled off the seam the user dropped it on, and
    pulling it is what an origin-display x clamp would do.
- **Cost:** resident *est.* **+6** on kern_big, kern_emu and kern_mega: the
  call and ret overhead, less the shorter register operands. kern_small 0,
  keeping its arm by `%ifdef`.
- Closes K5 with P2. The second zoom restores once the first lands where
  zoom put it.

### P4. Fullscreen from a straddle (K7)

- **(a) Stale pixels on the card that does not take the bracket, and the
  stale title bar over the dock.**
  - `ext_e_fsrect`, the 2-display arm of `wm_fs_setrect`, damages the saved
    rect clipped to the OTHER display: `wm_paint_dmg` over the intersection
    with that display's `vid_ctx` rect.
  - Resident 0. EXTD.DRV *est.* +30.
- **(b) The window is moved on exit.**
  - `wm_fs_drop` runs `wm_fit` on the saved rect, and `wm_fit` clamps into
    the **origin's** display. That is right after an adapter change and
    wrong for a rect that was legally straddling.
  - Fix: `EXTCALL EXT_STRADS` / `jnc` round the `wm_fit`. On one display
    `mod_gone` answers CF = 1, so the fit still runs and 39.11.2.1's case
    is kept.
  - Resident *est.* **+6** on kern_big, kern_emu and kern_mega. kern_small 0.

### P5. The pointer comes back to the primary's centre (K8)

`vid_apply` homes the pointer to `[vid_w]/2, [vid_h]/2` (viddet.inc,
`.boot2`). On an extended desktop it runs inside `ext_kapply` (bracket entry,
Extend) and `ext_two` (bracket exit), before the union. So every fullscreen
session and every Extend puts the pointer at the primary's centre.

- **Design:** `ext_two` and `ext_extend_b` save `[mouse_x]`, `[mouse_y]` and
  `[cur_disp]` before they apply, put them back after the union, and run
  the point through `vid_pt_clamp`.
- **Cost:** resident 0. EXTD.DRV *est.* +20.
- Seen on kern_mega (86Box). kern_big runs the same code.

### P6. kern_mega: the pointer during disk I/O with two displays (D1)

`mega_vrm` refuses whenever `[vid_ndisp]` > 1, because `cur_move_multi`
loads each display's `vid_seg` from its `vid_ctx` record, and those are
selectors. A refusal keeps IRQ4/IRQ12 masked for the whole reflected
int 13h: a 1.2 s freeze, and 25-29% of the motion lost.

- **Design:** convert and bank display 1's `vid_seg` word too:
  - offset `VID_CTX`'s `vid_seg` word index in record 1;
  - `mega_vsw` grows from 2 words to 3;
  - `mega_svc_back` and fsx.inc's restore put the third word back.
- **Cost:** kern_mega only.
  - Conventional *est.* **+2** (the `mega_vsw` word, counted by megaseg too).
  - `.mega` *est.* +24 (above 1MB).
  - The other three kernels 0.

### P7. DOS and the adapters under a bracket (D2-D5)

- **D3. A VGA running as a CGA (mode 6) is not blanked during a Hercules
  bracket.**
  - Cause: `vid_bk` blanks kind CGA through 3D8h, and a VGA ignores that.
  - Fix in EXTD.DRV's `vid_fsx_enter` and `vid_fsx_unblank`: when the
    other display is kind CGA and the machine's CGA is the VGA's own mode,
    set or clear the sequencer's screen-off bit (3C4h index 1, bit 5) as
    well.
  - Cost: resident 0. EXTD.DRV *est.* +18.
- **D2. A DOS mode set inside the Hercules bracket reaches the VGA.**
  - Cause: int 10h on that machine IS the VGA's BIOS.
  - The fix belongs to DOS (`apps/dos`, kerndos): its int 10h hook refuses
    AH=0 inside a bracket that is not on the BIOS's card, or emulates
    mode 7.
  - Kernel 0.
- **D4. A CGA-mode DOS program on a Hercules primary shows nothing on
  either card.**
  - Fix, also DOS's: take the bracket on the CGA (`FSX_RUN`'s CH = n,
    SPEC.md 53.1.2) when the program's mode is a CGA one.
  - Its 642 width is P8.
  - Kernel 0.
- **D5. kern_mega, Hercules primary: Video's fullscreen on the VGA is
  360x144.** Unconfirmed. 360 is half of 720 and 144 is not a VGA figure,
  so the guess is that `FSX_SURF`/`FSI_*` is read from the primary's
  geometry before `ext_kapply`.
  - Needs a reproduction on 86Box before it has a design. Cost unknown.

### P8. A straddle widens a window by 2 (K2(a)) and K3

- **K2(a): 640 → 642 and 720 → 722 in Right layouts.**
  - Cause: `wm_strad_fit` snaps the width UP (SPEC.md 11.94.5.1), and a
    straddler is allowed past its display's edge (39.16.3.4).
  - So a 640 frame (638 content) becomes 642 and can never sit wholly on a
    640 display again. That is DOS's 642 (D4), Telnet, Weave and the rest.
  - Fix in EXTD.DRV: inside the straddle, snap DOWN only (content rounded
    down, floored at the minimum).
  - Cost: resident 0. EXTD.DRV *est.* +4.
- **K3: on a 200-row CGA, Fractal 199, Audio 232, Video 219, Artful 300,
  Cyclone 219, TameGram 303, C64 245, Apple II, PaccMan 307 and RunCPM 219.**
  - None of these windows is sizable or declares a preference.
    WINDOW-SIZING-PLAN 12.5's third row says such a window "keeps its size
    and may hang". So this is the design working, on a display shorter than
    the window.
  - The fix is **each package's**: an `OSAPI_WM_PREFER` table per kind, or
    re-laying out on 11.98, which is what Paint's 42.9.2 and Missile do.
  - Kernel 0. A kernel rule that shrinks undeclared windows would bring back
    12.5's cropped-layout defect.
- **TeXPad, Word and SysCheck "keep the other display's shape on return".**
  - These reflow (sizable), and the straddle clamp is applied without a
    later landing restoring the natural size.
  - Expected to be closed by P1-A plus K2(a). Recheck after those land
    before designing anything further.

### Totals (resident, recommended options, estimates)

| | kern_big | kern_small | kern_emu | kern_mega | EXTD.DRV |
|---|---:|---:|---:|---:|---:|
| landed (Part 1, measured) | -6 | -6 | -6 | -6 | +8 |
| P1-A | -24 | 0 | -24 | -24 | +6 (+12 with the K2(b) rule) |
| P2 | +13 | 0 | +13 | +13 | |
| P3 | +6 | 0 | +6 | +6 | |
| P4 | +6 | 0 | +6 | +6 | +30 |
| P5 | 0 | 0 | 0 | 0 | +20 |
| P6 | 0 | 0 | 0 | +2 (`.mega` +24) | |
| P7 (D3) | 0 | 0 | 0 | 0 | +18 |
| P8 (K2(a)) | 0 | 0 | 0 | 0 | +4 |
| **total** | **-5** | **-6** | **-5** | **-3** | **+92** |

With P1-A, the whole kernel side fits inside the 150-byte limit with room to
spare, and kern_small never moves. Without P1-A, P2-P4 cost +25 on the three
big kernels.

**Decisions wanted:**
1. P1 option A or B.
2. The K2(b) centre rule.
3. Whether EXTD.DRV's ~+90 bytes count against the 150. They are not
   resident on any kernel.

**Suite rows** to name in the final pass: dispdrag, dispseam, dispvy,
dispcorner, dispfit, dispzoom, dispsize, dispprefer, dispstrad, dispfsx,
dispfsxcga, dispfsxherc, dispmcfs, extdmod, extent, drag, dragui,
paintsize, paintrz, mega-kdkbd (P6), and megaseg.

**Regression rows worth writing** (docs/WRITING-TESTS.md, soak):
- Paint's walk on `os8088_5150_both_gla`, Hercules primary, Right: it is red
  at #365..0ff2e7b4e and green after.
- A Below drag wholly onto display 1: red before K1.
