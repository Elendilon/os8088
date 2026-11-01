# System Check

System Check looks over the disk your machine starts from and tells you
whether everything on it belongs to the same release of os8088. It is
meant for a machine that has been upgraded in place, where the new
release was installed over the old one and the old one's leftovers are
still there.

## Starting System Check

System Check lives in the `SYSTEM` folder of the system disk, and an
install copies it there on the hard disk too. Open `C:` (or the system
floppy), then `SYSTEM`, and double-click **SYSCHECK.O88**.

## Choosing the drive, and what to do

System Check first asks which drive to check, listing every drive the
machine has. Your hard disk is already selected, so most of the time you
just click **Scan** or press Enter. To check another drive, click it (or
use the arrow keys) first; double-clicking a drive checks it at once.

Beside the drives it asks what to do. Click a line, press Tab, or press
1 to 4:

| Task | What it does |
|---|---|
| Release files | Checks that everything on the disk belongs to this release (below) |
| Check the disk | Looks over the disk's file allocation table and every folder, like CHKDSK. Changes nothing |
| Check and repair the disk | The same, and repairs what it safely can |
| Defragment the disk | After a clean check, puts every file in one piece and moves files towards the start of the disk |

The three disk tasks need **FSCHECK.DRV**, which sits beside
`SYSCHECK.O88`. On the 360KB utilities disk both are at the root; on
the larger disks both are in `SYSTEM`.

The check then runs on its own, and the desktop stays usable while it
does. To check another drive afterwards, click **Scan** again.

## What it checks

Each check has a row and a lamp. On a colour screen the lamp is green
for OK, brown for a warning and red for something broken. On a black and
white screen it is a tick, a checkerboard or a solid square instead.

| Check | What it looks for |
|---|---|
| Kernel and boot files | `KERNEL.SYS` and the boot sector file are this release's, and the kernel is not empty |
| Drivers | Every driver and kernel module is one this kernel will load |
| Packages | Every program on the disk is built for this version of os8088 |
| Install leftovers | Files an interrupted install left, and the same program in two folders |
| Retired programs | Programs and drivers that an earlier release shipped and this one dropped |
| Release files | Files this release ships that are missing |
| Settings | The settings file does not ask for a driver that is not on the disk |
| File associations | Every program the associations name is where they say |
| Hibernation image | A saved session that will never be resumed |

Click a row to see what it found in the list below. **Details** gives
that list the whole window, which helps on a small screen.

## The buttons

| Button | What it does |
|---|---|
| Scan | Asks which drive, then checks it. While a check is running it reads Stop |
| Details | Gives the findings list more room, or puts the checks back |
| Save Report | Writes `SYSCHECK.TXT`, naming every finding, to the disk it checked |
| Clean Up... | Removes the leftovers it is safe to remove, after asking |
| Quit | Closes System Check |

Keys: **S** scans or stops, **D** is Details, **R** saves the report,
**Esc** stops a scan, the up and down arrows choose a check, and Page Up
and Page Down scroll its findings.

## What the disk tasks check

| Check | What it looks for |
|---|---|
| File allocation table | The disk keeps two copies of it, and they should match |
| Folders | Each folder's `.` and `..` entries, and entries that are garbage |
| File chains | A file's clusters that run off the disk, into free or bad space, or do not match the file's size |
| Cross-linked files | Two files claiming the same cluster |
| Lost clusters | Space marked in use that no file owns |
| Free space | How much is free, and any clusters marked bad |
| Fragmentation | How many files are in more than one piece |
| Defragment | What the defragmenter did |
| Repairs | How many repairs were made |

**Check and repair** fixes all of these except a cross-link: it ends a
broken chain at its last good cluster, cuts a file's size or its chain so
the two agree, rewrites a wrong `.` or `..`, copies the first FAT over the
second, and saves lost space as `FILE0000.CHK`, `FILE0001.CHK` and so on
in the root folder, so you can look at what was in it. A repaired finding
ends in *(fixed)*. For a cross-link, copy both files somewhere else,
delete them from this disk, and check it again.

**Defragment the disk** only runs on a disk with nothing broken, so run
*Check and repair* first if it says so. It never moves folders, hidden or
system files (the kernel and the drivers among them), or disk images
(`*.IMG`). If you save anything onto the disk while a disk task is running,
it stops and asks you to scan again rather than work from an out-of-date
picture.

## What Clean Up removes

Clean Up only removes files that are plainly left over: an install's
`KPAD.TMP`, a hibernation image nothing will resume, and programs this
release retired. It rebuilds the file associations when they point at
programs that are gone. Then it checks the disk again.

It leaves alone a program found in two folders (only you know which copy
you want) and a program built for another version (it may be your own,
waiting for an update). It cannot change the system's own hidden files.
For a wrong kernel or driver, the finding tells you to install again
from the release disks, keeping your files.

## Good to know

- System Check judges the disk against the release it came with. Use the
  copy in `SYSTEM` on the disk you are checking.
- On a 4.77 MHz PC it takes under a minute on a system floppy. Checking
  a 360KB floppy's file system takes about 5 seconds, and defragmenting
  one a few seconds per file moved.
