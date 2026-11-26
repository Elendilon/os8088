# INPUTCHK — Input Check and the input debug disk

**Status: built; awaiting the field report.** Contract: SPEC.md §136 (the
package) and §127.5 (the disk). This file is the plan, the stories and the
diary in one, because the work was one round.

## The ask (the owner, 2026-11-17)

> Lets modify upstream's mousechk into inputchk, and log everything we need
> for the keyboard data as well. We can then put it on a disk that autostarts
> it, runs the report, and saves (using a lnk's argument so the program only
> does that when started with the argument). This is close to the kernel debug
> builds, but upstream wanted to start a diag disk with apps instead of having
> a dozen custom kernels that dump the desktop.

The field case: one reporter, an Advantech-class STPC 486 SBC (Phoenix D486
BIOS, Winbond W83977AF super I/O with AMI MEGAKEY keyboard firmware, a
DiskOnChip boot, one combined keyboard/mouse mini-DIN). Its PS/2 mouse is
found only with one particular mouse; its PS/2 keyboard is "sometimes not
recognised" under os8088 alone - BIOS, DOS and Windows are fine - with no
change of hardware between a good day and a bad one. The board carries two
8042s (the STPC's and the Winbond's) that conflict by default. The working
theory is that both symptoms are one controller's, and that §9.9.1's PS/2
probe - the one thing os8088 does to that controller that the BIOS, DOS and
Windows do not - is what differs.

## Decisions

| # | decision | why |
|---|---|---|
| D1 | **Port upstream's MOUSECHK (jggonz/os8088 PR 340, unmerged) rather than write anew**, renamed INPUTCHK, labels kept (`mc_`, `p2_`, ...) | its PS/2 boot record and live probe are exactly the mouse half of the question, already reviewed upstream; the label prefixes stay so a later merge of upstream's package reads as a diff, not a rewrite |
| D2 | **Ported to this tree's SDK** (the ABI flag day): handlers in `OS88_CLASS` (`ABOUT`, `ONTIMER`, `ONMOUSEUP`, `ONDRAG`), `os88ui_btninit`'s three-argument form, `OSAPI_MEM_P`/`MEMP_CLAIM` for the report's claim, the content-origin snap by default | upstream's PR predates the flag day; `OSAPI_ABOUT_SET`, `OSAPI_WM_ONTIMER`, `OSAPI_WM_SNAP` and `OSAPI_MEM_CLAIM` are gone here |
| D3 | **The keyboard is a section of the same program** (`kbd.inc`, §136.11): passive every refresh, active only on K or in the automatic run | one controller, one report; the passive half never writes a keyboard port, the active half keeps §9.9.1's discipline step for step |
| D4 | **A link parameter, `AUTO`, starts the script** (§26.10.7 `OSAPI_ARG_TEXT`); any other launch is the interactive program and writes nothing by itself | the owner's ask; INSTALL's `CHECK` and SYSCHECK's `REPORT` are the precedents |
| D5 | **Two writes, a numbered file per boot** (`INPUTnn.TXT`) | the first write is before anything touches the controller, so a hang still leaves a report; per-boot files keep the good boot and the bad one side by side |
| D6 | **The disk is the shipped system disk plus three files** - no driver swap, no `SYSTEM.CFG` (§127.5) | the keyboard and mouse are the kernel's own; the point is the SHIPPED boot path, unchanged |
| D7 | **kern_big only, debug disks only, for now** | INPUTCHK decodes `'MO'` against one kernel's fingerprint; upstream's second (kern_mega) build and its SYSTOOLS placement are the change that lifts this, and `t_livefull`'s exemption says so |
| D8 | **The fingerprint tool keeps upstream's name** (`tools/os88mousekid.py`, byte-identical) | a later merge of upstream meets the same file |

## Stories

- [x] **S1. The port builds.** `apps/inputchk/` from PR 340's head, renamed,
  on this tree's SDK; `build/inputchk.o88`. *Seen:* `make` green.
- [x] **S2. The keyboard section, passive.** Keys the BIOS stored (buffer
  tail), keys that reached the window, 40:17/18/96/97, int 09h/15h/16h and
  which kernel hook is in, IRQ 1 mask and request, port 64h, a keyboard byte
  left waiting, and - under the fingerprint - the boot's command byte, whether
  the boot's probe sent `D4 FF`, and the mask it found. *Seen on QEMU:* keys
  counted, Num/Caps Lock in 40:17 and the LED bits in 40:97, int 15h in the
  kernel (the `kbm_i15` hook), the boot's `61`.
- [x] **S3. The controller check.** K, and stage 3 of the run: a waiting byte
  taken and shown, the command byte now and the bits changed since boot, the
  output port, `0xAB`, `0xEE` to the keyboard. *Seen on QEMU:* `AB` 00, echo
  `EE`, bits 1/5 reported as the aux port's (the PS/2 mouse is live there),
  the keyboard still typing afterwards.
- [x] **S4. The automatic run.** `AUTO` from the link: ~20 s for keys, write
  `INPUTnn.TXT`, check (and Probe PS/2 where the kernel found no mouse), ~10 s
  for keys, write again; commands ignored meanwhile. *Seen on QEMU:* both
  writes, the file read back off the image on the host.
- [x] **S5. The disk.** `debug-input{,-120,-720,-360}.img` in `$(DEBUGIMGS)`
  (so in `$(SHIPIMGS)` and the release zip), `make debugdisks` builds all
  eight debug images, and every per-image gate lists them. *Seen:*
  `t_debugdisk` 54 checks, red with the parameter removed from the link.
- [x] **S5b. Every debug disk carries the other diagnostics** (the owner,
  2026-11-17; SPEC.md 127.1 rule 6): `APPS\` holds REDLINE.O88 and the other
  debug disk's program, started by hand; only the disk's own program
  autostarts. 360KB: 29 and 30 clusters left. *Seen:* `t_debugdisk` 78
  checks, red with REDLINE removed from one image.
- [ ] **S6. Upstream's soak row ported** (`tests/mousechk.py` →
  `tests/inputchk.py`, its `EXPECT` table extended with the keyboard rows and
  an `AUTO` leg). Not done: this round's evidence is the QEMU boot below.
- [ ] **S7. On a system disk**, with a kern_mega build, as upstream ships
  MOUSECHK. Waits on upstream merging PR 340, so the two do not ship side by
  side.
- [ ] **S8. The field run** - the reporter's INPUT??.TXT files from a good
  boot and a bad one. That answers whether §9.9.1's probe is what kills the
  keyboard on this board, and decides the kernel change (most likely: skip
  the probe where the BIOS's equipment word says no pointing device at POST,
  DOS's rule).

## Diary

**2026-11-17.** Fetched PR 340's head (`pull/340/head`, not in this fork and
unmerged upstream). Its package would not assemble here: four slots it calls
were withdrawn at the ABI flag day. The port to `OS88_CLASS` was mechanical;
the one non-obvious line is the report claim, which moved from a KB count to
paragraphs and keeps `MEMP_CLAIM` without `MEMP_CPU`, because Save Report
writes out of it with `int 13h`.

The fast tier found the other upstream change the PR carried for a reason:
Pixel's `mc_head` label (pxextra.asm) shares the name of the row API's
`mc_head`, and the stack-balance walker (`stkapps`) cannot tell two
same-named labels apart. Upstream renamed Pixel's to `ex_mchead`; so did this
round. No byte of PIXEL.O88 moves.

The first QEMU boot (`debug-input.img`, `-serial none`, so QEMU's PS/2 mouse
is live) showed three things that are now fixed: a 22-character label cut by
the value column; 40:97's bits decoded from the space character rather than
the byte; and the controller check calling the command byte CHANGED when only
bits 1 and 5 had moved - which is the kernel arming the aux port, by design.
The comparison now names the bits and raises a PROBLEM only for bit 0 or 6.
The first write also captured the stage it was leaving rather than the one it
had reached; each write now advances the stage first.

**A finding on the first day, by the tool's own rows: on QEMU, ONE CAPS LOCK
KILLS os8088's PS/2 MOUSE.** The second boot read the command byte as `61`
(aux clock off, IRQ 12 off) while the kernel's record said step 9, armed - the
first had read `43`. The difference was a Caps Lock pressed before the check.
SeaBIOS sends a keyboard command (the LED update) by writing the 8042 command
byte to disable both ports and then writing back its OWN CACHED copy
(`Ps2ctr`, `ps2_command` in its `ps2port.c`), which it updates only through
its own `int 15h` C2xx mouse services. §9.9.1 enables the aux port behind the
BIOS's back, so the first LED update reverts the controller to the BIOS's
POST value. Measured with Input Check's own Position row on
`debug-input.img`: a relative move took the pointer 320,240 -> 420,290; Caps
Lock; the next move left it at 420,290. Control, same boot sequence with `a`
instead of Caps Lock: the second move took it 420,290 -> 270,190. Whether a
real BIOS does the same is per BIOS (an AMI or Phoenix ROM may bracket the LED
update with `0xAD`/`0xAE` and leave the aux bits alone, or may not); it is
exactly the class of fault a driver that goes through `int 15h` C2xx, as
CuteMouse and Windows 3.x's do, cannot have. Not fixed here: it is a kernel
change (re-arm on IRQ 12 silence, or own the LED update), and it is now a
row any field report shows - `Command byte now` against the record.

What QEMU cannot say: its i8042 answers every command, so every row here was
seen on a controller that cooperates. The machine this is for is the only
evidence of one that does not - which is what the disk is for.
