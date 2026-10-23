# NET-UPDATE — install and upgrade os8088 over the network

**IN PROGRESS.** SPEC.md 26.10.7 (a link's parameter) and 117.10 (INSTALL over
the network) are the contract; this file is the story list and the design
record behind them. It follows `docs/plans/HTTP-MOUNT-PLAN.md`, whose drive is
the transport, and `docs/plans/INSTALL-PLAN.md`, whose wizard and engine do
the install.

The ask, in the owner's words:

- *Have install.o88 check the remote version against the installed os version
  on startup, if and only if an ethernet driver is mounted.*
- *Have the first screen select between network install and disk install
  (instead of the intro it shows today). If the network version is newer,
  show the newer version.*
- *We may add some text, downloaded with the version, that shows what is new,
  if we have room on cga for two radio lines, one or two help lines, and a few
  lines of what is new.*
- *Potential: add a startup link as an option at the end. On startup, check
  for a new version, and if one exists show the window.*
- *Actual install would be something like: mount a hardcoded web address for
  a combined os/apps disk, and then run the normal install.*

and the decisions taken while costing it:

- **A release number, bumped by the release skill**, not the build number: the
  build number is a commit count, and `main` squash-merges while `elendilon`
  does not, so a newer `main` release can carry a smaller count. Only real
  releases matter, so the release's own date is the number.
- **Put the user's own HTTP drive back** after the check, if it is cheap.
- **No once-a-day throttle**: the check at startup is one the user asked for.
- **A link carries a PARAMETER** rather than INSTALL declaring a file type to
  tell a startup launch apart: the association table is a shared, bounded
  resource (16 programs / 32 extensions) and an extension that names no real
  document would spend a slot of it. Raising that table is a separate
  decision the owner is taking elsewhere.
- **The install log stays**; INSTALL's text is trimmed instead.

## 1. What already exists, and what it decides

| need | what does it today |
|---|---|
| a drive over HTTP | `HTTPFS.DRV` (SPEC.md 120), and its package door `HFV_*` (120.4) |
| bringing a driver up from a package | `OSAPI_DRV_USE`'s `DRVU_UP` (117.3) - the Drivers page's tick |
| is an Ethernet card up | `OSAPI_DRV_CLASSK` with `DRVC_NET` |
| the install | `HDDTOOL.DRV`'s engine through `HDI_GO` (117.4). Its source is **the volume the bank left the machine on** if it carries `KERNEL.SYS` (`hd_isrc_ck`), so standing on the HTTP drive's root is the whole of choosing it |
| apps on the same volume as the system | the SYSTEM phase walks the whole source tree (52.10.13), so a combined tree is copied in one phase |
| `ASSOC.DAT` on the installed volume | built from the destination after the install (52.10.14) - on a run whose apps phase was declined too |
| a quiet refusal from an entry proc | a toast the entry raised survives the abort and `Load failed` is not said (20.12.4) |
| a program started at boot | `\AUTOSTRT\*.LNK` (26.10.5), written by `apps/os88link.inc` (26.10.6) |

So the network install is the ordinary install with a different source
volume, and its apps phase is skipped because there is nothing left to copy.

## 2. Stories

### Wave 1 - a link carries a parameter (kernel + SDK)

- [ ] **A link whose target is a program may carry a parameter**: text after
      the path's NUL, inside the same 45-byte field. `LNK_V` stays 1: a kernel
      that predates it ends the path at the NUL and never reads the rest.
- [ ] **`OSAPI_ARG_TEXT`** (cell `0x04D5`, a rare cell): the program reads it
      from its entry proc, read-and-clear, `OSAPI_ARG_FILE`'s shape. It points
      into the link's record on task 0's stack, which is alive for the whole
      launch, so no buffer is spent. kern_small refuses (it has no links).
- [ ] `apps/os88link.inc`'s `OS88_LINK` takes an optional fifth argument, the
      parameter; `tools/os88lnk.py` writes and reads one (`--arg`).
- [ ] Gate: a link with a parameter starts a probe package that reports what
      `OSAPI_ARG_TEXT` answered; the same link without one answers CF = 1; a
      plain double-click answers CF = 1. Break on purpose: drop the disarm
      after the launch and a second, plain launch inherits the text.

### Wave 2 - the release number and the published tree (host)

- [ ] **`apps/install/OS88VER.TXT`** is the release's version file, tracked:
      line 1 the release as `YYYYMMDD`, then up to four lines of what is new.
      The release skill writes it (the date it already puts in
      `v1.0.YYYYMMDD`) and commits it before it builds.
- [ ] INSTALL is assembled with that first line as its own release
      (`IN_REL`), so the wizard on a disk knows the release it came from - and,
      being copied with the system (117.6), the release INSTALLED on a hard
      disk.
- [ ] **`make nettree`** writes `build/nettree/`: the 1.44MB system disk's
      files and the 1.44MB apps disk's files as ONE tree, minus `ASSOC.DAT`
      (the engine builds the volume's own, 52.10.14), plus `OS88VER.TXT`, plus
      the `OS88.IDX` `tools/os88httpdrv.py` writes. The release skill copies it
      to the website as `/net/`.

### Wave 3 - INSTALL checks the network

- [ ] On start, **only if a `DRVC_NET` driver is loaded**: bring `HTTPFS.DRV`
      up, remember the drive's current address, mount
      `http://os8088.com/net/`, read `OS88VER.TXT`, and compare its release
      with INSTALL's own. Afterwards the user's own address is mounted again,
      or the drive unmounted if there was none. `HTTPDRV.CFG` is never
      written.
- [ ] The window is up first and says `Looking for a newer os8088 on the
      network...` while it asks, so a slow server is a sentence and not a
      frozen screen.

### Wave 4 - the first page chooses

- [ ] The Welcome page becomes the **source** page: two radio rows, *From the
      network* and *From floppy disks*, a help line, and up to four lines of
      what is new. The network row is greyed with the reason when there is no
      card, the server did not answer, or its release is not newer; when it
      is newer it names the release and is the default.
- [ ] Fits CGA's 344 x 136 content: 2 radio rows (24px), 1 help line, 4
      what's-new lines at the body pitch, above the buttons.

### Wave 5 - the install from the network

- [ ] Choosing the network mounts the address again, stands on its root, and
      runs the ordinary pages; `HDI_GO` copies from it. The apps phase is
      skipped by itself (`HDI_QUIT`): the tree carried the apps.
- [ ] The Confirm page says *copy os8088 from the network* instead of *copy
      both floppies*.

### Wave 6 - check at startup

- [ ] The Done page offers **Check for updates at startup**, a check box. Ticked,
      Restart writes `\AUTOSTRT\OSCHECK.LNK` naming `INSTALL.O88` with the
      parameter `CHECK`, on the installed volume; unticked, it deletes it.
- [ ] Started with `CHECK`, INSTALL asks the network before it opens a
      window. Nothing newer, or no network: one toast, and no window. Newer:
      the window, on the source page.

### Wave 7 - text trims, the gate, the final pass

- [ ] The upgrade page folds into the source page; Confirm, Apps and Done lose
      the lines the pages around them already say. The log stays.
- [ ] Gate `netinst` (QEMU by name: the card): a fixture tree served by
      `tools/os88httpdrv.py` with a newer `OS88VER.TXT`, the source page
      reads it, an install from it reaches Done, the volume holds the apps.
- [ ] The rows this work can reach, once, after the last wave: `httpmount`,
      `httpinstall`, `install`, `autostart`, `netinst`, the link gate; then
      `test-full` once.

## 3. Cost, estimated before the build

| where | bytes | note |
|---|---:|---|
| kernel, kern_big | ~50-60 resident | the parameter's arm in `lnk_open`, a word of `.bss`, the cell and its body |
| kernel, kern_small | 6 | the cell, refusing |
| `INSTALL.O88` | ~700-1,000 image, less the trims | the check, the source page, the network install, the startup option |
| `HTTPFS.DRV`, `ETHER.DRV`, `HDDTOOL.DRV` | 0 | used through their published verbs |

Measured figures replace these in SPEC.md 117.10.8 when the work lands.

## 4. Decided against

- **An association for the startup marker.** It worked, and it spent a slot
  of a table an everything-install already overflows (16 programs / 32
  extensions against 21 / 38) on an extension that names no document.
- **Comparing build numbers.** A commit count is per branch.
- **A once-a-day throttle.** INSTALL would still load to read the date, so it
  saves only the HTTP drive's load, and the check is one the user switched on.
- **Two addresses** (a small version tree beside the big one). One tree
  serves both: the check fetches its index once and the install reuses the
  mount.
