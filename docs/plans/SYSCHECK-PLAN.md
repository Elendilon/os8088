# SYSCHECK — System Check

**Is the installed system all one release?**

System Check reads the volume a hard-disk install boots from and reports
what an in-place upgrade (SPEC.md 52.10.15) can leave broken or behind.
SPEC.md 118 is the binding contract; this file is the delivery record, and
an unchecked story here is not yet shipped behaviour. The build diary is
[docs/HOW-SYSCHECK-WAS-BUILT.md](../HOW-SYSCHECK-WAS-BUILT.md); the design
mockups are [docs/syscheck/design/](../syscheck/design/).

## Delivery stories

- [x] **Foundation:** as a maintainer I get a release manifest built from the
  system disk's own inputs (`tools/os88sysman.py`), held to every built
  system disk by a fast gate, and a `SYSCHECK.O88` that lands in `SYSTEM\`
  on the four kern_big system disks and the live media.
- [x] **Foundation:** as a user I can open `C:\SYSTEM\SYSCHECK.O88` and see
  the System Check window: the progress card, the This System card, the nine
  checks with their lamps, the findings card and the buttons, laid out for
  the adapter I have.
- [x] **Scan:** as a user the scan starts by itself, shows its progress in the
  bar and the path line, lights each check's lamp as it finishes, and leaves
  the desktop usable while it runs; Stop stops it at the next step.
- [x] **Scan:** as a user I am told about every program and driver that this
  kernel will refuse, with the format it was built for and the one the
  kernel takes.
- [x] **Scan:** as a user I am told about leftovers - `KPAD.TMP`, a program in
  two folders, a retired program or driver, a hibernation image from another
  build - and about release files that are missing, a `SYSTEM.CFG` that
  wants an absent driver, and file associations that point at nothing.
- [x] **Choose the drive:** as a user System Check asks which drive to
  check before it reads anything, with my hard disk already selected, and
  Scan asks again afterwards (SPEC.md 118.13).
- [x] **Report:** as a user Save Report writes `SYSCHECK.TXT` naming every
  finding, and a toast tells me where.
- [x] **Clean Up:** as a user Clean Up asks first, removes only the debris
  SPEC.md 118.8 lists, rebuilds a stale `ASSOC.DAT`, and scans again; what
  it cannot repair says how to (install again).
- [x] **Presentation:** as a user on Hercules or CGA the lamps are shapes
  rather than colours and the layout fits the screen; on VGA they are the
  mockup's colours.
- [ ] **Acceptance:** a hard-disk image with each kind of breakage planted is
  booted from C:, scanned, reported and cleaned up by a soak row, on every
  adapter the window claims. *Done on VGA (`syscheck`, QEMU); Hercules and
  CGA have been LOOKED AT on MartyPC (a clean system disk, every row OK) but
  no row drives a planted disk on them yet.*

### Disk tasks: check, repair, defragment (SPEC.md 118.14)

- [x] **Contract:** SPEC.md 118.14 pins the chooser's four tasks, the nine
  disk rows, `OSAPI_VOL_CHECK`, the workspace record, every finding's code
  and numbers, what repair repairs and in what write order, the
  defragmenter's rules, and the per-volume write generation.
- [x] **Engine:** as a maintainer I get `FSCHECK.DRV`, the checker and
  defragmenter as kernel code (`kernel/fsck.inc`), cut out by
  `tools/os88mod.py` and **loaded by the package from beside it**, not by
  `mod_need` - so it ships at util360's root next to `SYSCHECK.O88`, and in
  `SYSTEM\` on the larger kern_big disks, and never on the 360KB system disk.
  101 resident bytes, no rung crossed.
- [x] **Choose the task:** as a user the chooser asks what to do as well as
  which drive - Release files (the nine checks), Check the disk, Check and
  repair the disk, Defragment the disk - with Tab, 1-4 or a click, and it
  fits CGA's short card.
- [x] **Check the disk:** as a user I am told about FAT copies that differ,
  wrong `.`/`..` entries, entries that are not entries, chains that leave
  the disk or run into free or bad clusters, files whose chain and size
  disagree, cross-links and lost clusters, plus free space and
  fragmentation - and nothing is written.
- [x] **Repair it:** as a user *Check and repair* fixes all of those but a
  cross-link, in an order that never leaves a file naming a free cluster,
  saves lost chains as `FILEnnnn.CHK`, and shows each repaired finding as
  `(fixed)`.
- [x] **Defragment it:** as a user *Defragment the disk* (after a clean
  check) makes every movable file one piece and packs files towards the
  start, through free space only, leaving folders, hidden and system files
  and disk images where they are.
- [ ] **Safety:** as a user a save onto the disk mid-run, or a swapped
  floppy, ends the run with *The disk changed - scan again* instead of
  working from a stale picture. *Built (SPEC.md 118.14.6: the per-volume
  write generation, the volume signature); no row writes mid-run yet.*
- [x] **Acceptance:** `fsckdisk` (soak, MartyPC) plants seven faults on a
  copy of util360.img, checks, repairs and defragments it, and holds every
  result to an independent FAT reader. Looked at on CGA and VGA.
- [ ] **Hard disk:** a FAT16 hard-disk partition checked, repaired and
  defragmented on a period machine. *The engine's FAT16 arms are the
  kernel's own FAT routines and are assembled, but no row drives a FAT16
  volume yet.*

## Existing facilities and boundaries

- **The scan is wake slices on the UI task** (`OSAPI_WM_ONWAKE`, SPEC.md
  74.1): it is file work, and a worker may not touch a file (SPEC.md 20.6
  rule 7). REDLINE's look was the reference; its scheduling - one blocking
  call under the gfx lock - was not.
- **The standard controls** (`apps/os88ui.inc`): buttons, the scroll bar,
  the alert and the About card. Numbers through `apps/os88dec.inc`.
- **Reading by name, listing by `OSAPI_FILE_FIND`**: a package can read a
  hidden + system file and cannot list one (SPEC.md 19.7.1), which is why
  drivers are checked against a manifest and a retired list rather than
  discovered.
- **No new kernel facility for the release checks.** The one thing a slot
  would add - the running kernel's build - is answered by construction
  instead (SPEC.md 118.1.1), so those cost no resident byte. **The disk
  tasks are the exception, and have to be**: a package has no sector read or
  write and must not be given one (SPEC.md 96.5.2.2), so they add one cell,
  `OSAPI_VOL_CHECK`, and an engine image the package loads (SPEC.md
  118.14.1).

## Verification discipline

Each wave: `make` (which runs the fast tier, `t_sysman` among it), a boot to
look at the window, and the suite rows named. The soak union and
`test-full` run once, after the last wave (CLAUDE.md, Testing).
