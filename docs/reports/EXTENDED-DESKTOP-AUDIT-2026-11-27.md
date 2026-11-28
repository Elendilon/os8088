# Extended-desktop audit, 2026-11-27

A measurement of one tree: `elendilon` at `aa6b428`, kern_big on MartyPC and
kern_mega on 86Box. The audit was asked for as a sweep of every shipped
application across every supported two-display pairing (SPEC.md 39.11-39.20).
Each application was put on display 0, then straddling the seam, then on
display 1, and back. The checks covered drawing, sizing and reflow,
display-dependent menu items, which card fullscreen takes, and the machine's
health. **Nothing here is fixed yet.** This is the defect list, grouped by root
cause, with the evidence each finding rests on.

## What ran

| pairing (machine) | primary × layout | depth |
|---|---|---|
| CGA + Hercules (`os8088_5150_both_gla`) | Herc-Right | full sweep |
| | CGA-Right, CGA-Below, Herc-Below | lighter pass: open, three placements, health |
| VGA + Hercules (`os8088_xt_vga_herc`) | VGA-Right, Herc-Below | full sweep |
| | Herc-Right | full sweep for games and on-demand, lighter pass for media |
| | VGA-Below | lighter pass |
| | VGA running as a CGA (mode 6) + Hercules, Right | smoke |
| VGA + MDA (`os8088_xt_vga_mda`) | VGA-Right | smoke (it extends exactly as VGA + Hercules does) |
| kern_mega, Paradise VGA + Hercules (86Box `286-mega-multimon`) | VGA-Right, VGA-Below, Herc-Right | representative set |

All 14 MartyPC combinations extend: `vid_dual_ok` refused none of them. About
75 packages were covered, in four groups:
- **office**: the office apps, the desk widgets, the Disk window, the Control Panel and zoom.
- **games**: all 17 games, each in play.
- **media**: media, network, DOS and the system packages.
- **on-demand**: WIN16, the emulators and the on-demand floppies.

The harness and every screenshot are in the session's scratchpad
(`extaudit/`). That is ephemeral, so the evidence names below identify shots
that can be re-taken, not files kept in the tree.

**Emulator limits found on the way.** These are not os8088 defects:
- MartyPC's MDA/Hercules card never clears `mode_enable`, so a Hercules is never seen blanked on MartyPC. On 86Box it *is* blanked during a VGA bracket.
- Every MartyPC two-card machine has 360KB drives, so PAGEDESK with XTGUIDE.PDF fits no disk there.

## Severity 1: crashes and hangs

1. **Frotz crashes while straddling** (kern_big, Herc-Right and VGA-Right, both pairings).
   - It hit in 4 of about 7 straddling sessions: "[Frotz: unknown opcode] 0x1F at 0xE15 es=0000", and once a **STACK OVERFLOW panel** with a garbled task name and a dead machine.
   - It did not happen in 3 runs that moved only within d0.
   - A scrolled-text artefact appears just before.
   - Suspects: the story claim's relocation (`apps/frotz/zio.inc` ~1040, `zf_reloc`), or a scroll blit across the seam writing out of bounds.
2. **WIN16 hangs the desktop after a menu is used on a straddling window** (kern_mega, 86Box; seen in 3 boots of 3).
   - The Colour menu stays highlighted and task 0 keeps the drawing lock for more than 35 s. Nothing redraws.
   - Single display, and extended but wholly on d0, are both fine.
   - Not tried on kern_big.
3. **The UI was stuck for 180 guest seconds after Cyclone's fullscreen on a Hercules d1** (VGA-Right, the 7th game in a long session). Three re-runs on their own did not reproduce it.

## Severity 2: kernel window placement and sizing

These account for most of the visible breakage, and each is one kernel cause.

- **K1. A drag cannot take a window below the primary's last rows.**
  - `ui_drag` clamps y to `[vid_ymax]` (`kernel/ui.inc` ~1848). That is set as `vid_h - TITLE_H` for the primary (`viddet.inc` ~913) and is not grown by `vid_desk_union`. Measured on CGA-Right: `vid_h` 368, `vid_ymax` 182.
  - **Every Below layout:** no window can be dragged wholly onto display 1. It stops 18 rows short of the seam (kern_big and kern_mega).
  - **Right layout, CGA primary:** the lower ~168 rows of the Hercules are unreachable.
- **K2. A straddle sizes the window to a display's preferred size, larger than either display, and nothing refits it.**
  - `wm_strad_fit` (`kernel/extmod.inc` ~893-944) clamps only the axis both displays share.
  - Right: a 640 or 720 window becomes 642 or 722 wide (MIDIRack, Telnet, RunCPM, Weave, Loom, ByteOpoly, PageDesk, Pixel, isoTron, DOS 642). Scribe becomes 714.
  - Below: windows grow taller than the Hercules' 348 rows (Browser 392, WireChat 400, REDLINE 448, Frotz 396, CWord 384, Scribe 440, Missile 435, isoTron 420, DotDel's 546x520 request granted at y=197).
  - **It is not undone on return.** TeXPad, Word and SysCheck keep the other display's shape on their home display and hang across the seam. Notepad, CDRack and TaskMgr do grow back.
- **K3. A window moved to a shorter display is not refitted.**
  - On a 200-row CGA: Fractal 199 (then over the dock back on a CGA primary), Audio 232, Video 219, Artful 300, Cyclone 219, TameGram 303, C64 245, Apple II, PaccMan 307, RunCPM 219.
  - Paint gets it backwards: it keeps 300 rows on the CGA and drops to 200 on the Hercules (canvas 258 → 158).
  - A fullscreen round trip on d1 does refit the C64.
- **K4. Moving onto display 1 lands at `vx - 1`.** The window keeps a 1px straddle and never sits wholly on d1 (Missile, isoTron; x = 719 or 639).
- **K5. Zoom on display 1.**
  - Right: the frame lands at `vx - 1`, and the second zoom does not restore it.
  - Below: a straddling window zooms onto d0 keeping the other display's width, and a second zoom zooms again.
  - Static reading: `wm_resize_nb` (`kernel/wm.inc` ~2419-2470) caps width at `[vid_w]` and height at the primary's `[vid_dock_y0]`/`[vid_ph]`, and floors y at the primary's bar.
- **K6. Two answers to "which display is this window on".**
  - `wm_disp_of` (the centre, used by FSX_CAPS, FSX_RUN, zoom and fullscreen) disagrees with `wm_disp_now` (the more restrictive display, used by `OSAPI_WM_DISPLAY` and onresize) — the disagreement SPEC.md 39.16.4.1 itself calls the defect.
  - **Pixelstein** and **Lemmings**: when straddling with the centre on the VGA, the Mode row says Hercules and Play/Full Screen is silently refused.
  - **Missile**: picks depth from one display and frame size from the other.
- **K7. Fullscreen from a straddle.**
  - The card that does not take the bracket keeps a stale image of its part of the window (C64, Apple II, Missile, WireFleet).
  - On exit the window is put somewhere else: Missile goes to (7,40) on d0, 359 → 6, or onto the other card; C64 (551,20) → (375,20).
  - A stale title bar was once left on the Hercules over the dock.
  - Suspects: `wm_fs_drop` refitting the saved rectangle through `wm_fit`/`EXT_FITBOX` (`kernel/wm.inc` ~3646), and the enter path not repainting the rectangle the window left.
- **K8.** After Extend, and after every fullscreen session, the pointer jumps to the primary's centre even when the window is on d1 (kern_mega).

## Severity 2: kernel display handling

- **D1. kern_mega: mouse movement is lost during disk I/O when the desktop is extended** (86Box).
  - `mega_vrm` refuses whenever there is more than one display (`kernel/mega.inc` ~5927), so the whole real-mode int 13h call runs with the pointer interrupt masked.
  - Measured: on a single display the longest stall is 25 ms. Extended, the pointer is frozen 1175-1250 ms through spin-up and 25-29% of the motion is **lost**.
- **D2. DOS: a mode set inside the Hercules bracket reaches the blanked VGA.** VGA-Right, DOS window on d1, Alt+Enter, then a program sets mode 4: the VGA primary switches to mode 4 and shows the graphics, while the Hercules keeps the text.
- **D3. A VGA running as a CGA (mode 6) is not blanked** while Tank's mode-setting bracket runs on the Hercules. A 3D8h blank does nothing on a VGA.
- **D4. DOS on a Hercules primary:** a CGA-mode program in the Hercules bracket shows nothing on either card, though a CGA is present. The DOS window is also 642 wide, so it can never sit wholly on a 640 CGA (K2).
- **D5. kern_mega, Hercules primary:** Video's fullscreen on the VGA comes out 360×144 at (136,168), against 320×200 with the VGA primary. Unconfirmed.

## Severity 3: SDK and widget library

- **L1. Sticky widgets (`apps/os88stik.inc`) compare desktop positions with a display's own size.**
  - `stik_refit` (~1658) runs every beat. Confirmed live in VGA-Herc Below: DeskCal dropped at y=330 is lifted to y=238 at the next beat.
  - `stik_resize` (~2312) and the restore at ~995 have the same mix-up (read in the code, not seen live).
  - This reaches DeskCal, DeskClok and StikNote.
- **L2. Sheet's menu save-under leaves dropdown rows behind** in both Below layouts (stale pixels at y≈477-522, and a frame line at the seam).
  - `sh_mbank` (`apps/sheet/sheet.asm` ~9024) clamps the dropdown's virtual bottom against the local height from `OSAPI_WM_DISPLAY`, and takes the plane count from the same answer.
  - The same plane-count pattern is in `os88ui.inc` ~5026 and ~6271 and `win16/w16menu.inc` ~2315. That is a possible heap overrun when the buffer is sized for 1 plane and the popup opens on the VGA. No corruption was seen in 8 straddled Sheet menus on kern_mega.
- **L3. A straddling window draws one face across two depths.**
  - Right layout, VGA + Hercules: the mono face's grey roles land on the VGA half. CDRack shows a smeared logo and inverted panels; WaveRack's TRIM button is half black and its VOLUME row is garbled; XTMP3 is similar.
  - Below layout: the colour face lands on the Hercules half, garbling labels.
  - Gorillas draws its mono sky onto the VGA half.
  - Partly a design question: one window, one face.
- **L4.** os88ui picture buttons that are partly covered use the PRIMARY's mono rule (`UI_ISMONO`, `os88ui.inc` ~239). Found by reading; not isolated live.

## Severity 3: packages that decide the display once, at launch, from the primary

The fix pattern is to ask `OSAPI_WM_DISPLAY` / `OSAPI_FSX_CAPS` for the
window's own display and ask again on onresize.

| package | what goes wrong | where |
|---|---|---|
| DrMarco | refuses to play ("VGA/CGA TO PLAY", Enter does nothing) on a Hercules window **when the other card is colour**, including the owner's 5150 arrangement. It should take the colour display with FSX_RUN's CH=n (SPEC.md 53.1.2) | `drmario.asm` ~241 |
| Arcade | cabinet and theme decided at launch. Q*bert launched on the Hercules and moved to the VGA still says NEEDS VGA and refuses Play; the reverse says READY and silently refuses | `arcface.inc` 173, 715 |
| WIN16 | moved to the other display, every opaque text run is inverted, and GetDeviceCaps and system metrics still report the launch display. On kern_mega's Hercules the menu bar is black and the straddled half is empty | `w16gdi.inc` ~998 (`w16_dispinit`, no onresize) |
| Telnet | iCE Colours stays enabled on a Hercules d1, and stays greyed on a VGA d1 under a Hercules primary | `telnet.asm` ~274 (`OSAPI_VIDEO`) |
| DeskClok | the face aspect follows the primary (an oval on the wrong glass), and all 9 faces, colour ones included, are offered on mono. Straddling in Below, the dial ring is missing above the seam | `deskclok.asm` ~399 |
| StikNote | the Color menu is enabled on a mono d1 under a VGA primary | `stiknote.asm` ~225 |
| TameGram | status-bar colours from the primary (a dithered ground on the Hercules; mono on a VGA d1) | `tamegram.asm` ~248 |
| ByteOpoly | colour art dithers unreadably on the Hercules; the Buy/Auction dialog rows are duplicated after a straddle resize | `bp_app.c` ~543 |
| 2BASIC | `SCREENW/SCREENH/SCREENBPP` give the primary's figures on d1 | `2basic.asm` ~7970 |
| VBattle | says "Needs CGA, EGA or VGA" on a VGA d1, where Enter in fact plays | `vbattle.asm` ~518 |
| C64 | window sized from `os88_video()` at launch | `c64.c` ~2238 |
| DOS console, Fractal, MIDIRack, XTMP3, WaveRack | the `OSAPI_VIDEO` (primary) pattern, at launch | `dos.asm` ~7673, `fractal.asm` ~318, `midirack.asm` ~564, `xtmp3.asm` ~259, `waverack.asm` ~159 |

Dialogs and alerts are centred on the primary, not on the window's display.
Found by reading (`os88ui.inc` ~3268; Sheet has 7 sites) and not reached live.

## Other findings

- **Audio Player:** the progress bar vanishes after any move across displays and does not come back. Guess: `apu_draw_time_full` (`apps/audio/apui.inc` ~796) frames without setting the pen.
- **Loom:** the close alert's title is garbage ("^[ PSQRVW N `"). Not checked on a single display, so it may not be extended-specific.
- **TeXPad:** once, after K2, the save prompt did not come up on top, so the close failed.

## Not extended-desktop, found along the way

- **`make mega` fails at `aa6b428`.** os88megaseg reads 3,789 against the 3,787 `tests/megaseg.txt` allows. f19793d (keypad 5) moved kern_mega's low segment by 2 bytes. The audit's kern_mega disks were built with the allowance raised temporarily and then restored. Nothing was committed.
- **RLAPPLY** refuses its own launch (`LD_EABORT`) on every combination.
- **Mixer's "Master"** label is invisible on mono, single display too.

## Checked and fine

- **Notepad, Calc, Paint's drawing and menus, FontView, TaskMgr, Timer, Chart (empty), Disk window, Control Panel, FTPD, TheWire, Install, Piano:** draw correctly on each display and straddling. Notepad and TaskMgr reflow and grow back.
- **WireBall, Arkanoid, Mines, Solitaire, Tank, Skies, WireArena, Bounce:** correct on every placement.
- **Fractal's worker** renders correctly across the seam. **Paint's stroke across the seam** is correct (kern_mega).
- **Fullscreen target policy:** every package goes to the window's display, taken from its centre, with CH=0, per SPEC.md 53.1.2. Only the Video Player enumerates displays and chooses one. None picks "the better card for colour content". With K6 fixed this is a sensible rule (the user picks the monitor by dragging); DrMarco's refusal is the case where it is not.
- **Fullscreen cleanup:** on exit, card modes always matched what they were before entry, and every close gave its heap back.
- **Apple II's Color NTSC item** greys correctly by display. **C64's** VGA13 bracket goes to the VGA d1 correctly.
- **kern_mega:** DOS fullscreen and Video fullscreen take the right card and blank the other; Sheet's menus straddling erase cleanly.
