# HTTP-MOUNT — a read-only drive served over HTTP

**PLAN, nothing built.** The ask: *"We currently mount drives from images and
over parallel. To prepare for network system upgrades and to use in general,
make a plan for read only http drive mounting. An address would be given, and
the drive would be usable, read only, no icon harvesting same as parallel
mounted drives."*

**Verdict: feasible, and cheap where it counts.** The kernel already has every
piece but one. A drive whose contents somebody else describes is §62.9's file
redirector, a read-only one is exactly what `CDROM.DRV` built (§119.3.4), and
"no icon harvest" is what a file-class volume whose `DSV_CAPS` is 0 already
gets (§62.9.2.1). The socket surface is ETHER.DRV's, reached through
`OSAPI_DRV_CALL` (§20.11), and the parallel cable serves the same verbs
(§62.11), so a drive over HTTP works over either transport for free.

| where | bytes | resident? |
|---|---|---|
| **kernel, `kern_big` / `kern_emu`** | **~76-80**: a fourth file class, `DRVC_HTTP` = 10 (row, label, far-pointer pair, `drv_svcix` byte, owner word, the class's 36-byte service-table copy) - `DRVC_CD`'s measured 76 (§119.5) is the comparable, and nothing else in the kernel moves | yes, every `kern_big` machine, card or none |
| kernel, `kern_small` / `kern_dos` | **0** - no driver layer (§62.9.19) | - |
| **`HTTPFS.DRV`** (new driver) | **~3.5-4.5 KB image + ~1.3 KB bss, ESTIMATED**; a 5-6 KB claim while attached; **~2.5 KB on the floppy** packed (CDROM.DRV's 57% ratio) | only while ticked |
| the **index** claim | 18 bytes a record + a 16-byte header: a system disk's tree ~1.5 KB, the whole live payload (420 files) ~7.6 KB | only while mounted, movable |
| ETHER.DRV | **0** for the plan as written; ~120 bytes (ESTIMATE) if the optional `NETV_RESOLVE` is built (§6) | only while ticked |
| host | `tools/os88httpdrv.py` - writes the published tree and its index; no guest byte | - |

Every byte figure for the driver is an ESTIMATE against named comparables;
the kernel figure is CD-ROM's MEASURED cost for the same shape of change and
will be re-measured with `tools/kernsize.py` at one commit when built.

## 1. What the user sees

- **Control Panel > Drivers > HTTP Drive**, a row like CD-ROM's: not wanted
  by default, a SYSTEM.CFG bit, `kern_big` and `kern_emu` only. Its page
  (the driver's own `DSV_CP*` procs, so no kernel bytes) holds one field -
  `http://host[:port]/prefix/` - a **Mount** / **Unmount** button and a
  status line: `Mounted as E:  214 files`, or what went wrong in words
  (`No network driver`, `Server answered 404`, `Not an os8088 index`).
- The address is remembered in `SYSTEM\APPDATA\HTTPDRV.CFG` (§19.9's place,
  `apps/os88data.inc`'s shape), so a ticked row with an address puts the
  drive on the desktop at the next boot.
- **The drive is lazy.** Attach registers the volume and fetches NOTHING; the
  index is fetched the first time the drive is opened. A dead server or a
  missing cable therefore costs the boot no time at all and fails the first
  open with the reason, which is the CD-ROM's empty-drive behaviour.
- **Read-only, and it says so.** Every write verb answers `FERR_WPROT`, so
  copy, delete, rename, New Folder and save all say *Write protected* through
  paths that already exist. Copy OFF the drive, launching a package from it,
  opening a document from it and the file dialog all work unchanged.
- **No icon harvest.** `DSV_CAPS` = 0 sends the mount down §62.9.2.1's
  cache-only pass: a package this machine has seen shows its icon, everything
  else the generic one, folders their folder glyph. Not one byte is fetched
  to draw a listing.
- **A package can mount one too** (`OSAPI_DRV_CALL`, BH = `DRVC_HTTP`), so a
  future upgrade tool or The Wire can point the drive at an address itself:

  | BL | verb | in | out |
  |---|---|---|---|
  | 0 | `HFV_IDENT` | | AX = `'HF'`, CX = the ABI |
  | 1 | `HFV_STATE` | | AL = the volume index (0xFF none), AH = state (idle / indexed / failed), CX = records, DX = the last HTTP status |
  | 2 | `HFV_MOUNT` | ES:SI = a NUL address | CF=0 and AL = the volume index; nothing is fetched (lazy) |
  | 3 | `HFV_UNMOUNT` | | CF=0; the volume row and the index claim go back |
  | 4 | `HFV_FETCH` | | fetch the index NOW: CF=0 and CX = records, or CF=1 and AX = an `HFE_*` - so an upgrader learns *before* it shows anything that the server answers |

  UI task only, every verb, §62.9.16's rule and reason.

## 2. Why a REDIRECTOR and not an image over HTTP

There were two shapes and the obvious one is the wrong one here.

**(A) An image over HTTP** - give it the URL of a `.IMG`, satisfy each sector
run with a `Range:` GET, and let the FAT layer do the rest, as §18.101 does
for an image on a local disk. Its one real attraction is large: the release
images are already published, so an upgrade source would need nothing new on
the server. Against it, and every item is decisive alone:

1. **It needs kernel bytes beyond the class.** A `DVK_DRV` row is served by
   `DSV_BLK`, which is `DRVC_DISK`'s slot (HDD.DRV's), so either a second
   block class and its dispatch in `dsk_xfer`, or a pseudo-class with a
   driver hook in the transfer: ~150-250 bytes ESTIMATED against ~76.
2. **It harvests.** A `DVK_DRV` mount runs the real icon pass, one sector a
   package - one HTTP request a package, which is precisely what the ask
   rules out - so it needs a further kernel flag to turn it off.
3. **Every read needs `Range:`**, and the commonest throwaway server
   (`python3 -m http.server`) ignores it. The redirector needs it only for
   `FSV_READAT` and has a correct fallback when it is ignored (§4.3).
4. **It is a request per sector RUN.** A mount is the BPB, the FAT and the
   root directory - three or more requests before a single row is drawn - and
   a package load is one per run of its chain. The redirector's listing is
   zero requests (the index is in RAM) and a file read is ONE.

**(B) A redirector over an index** - what this plan is. HTTP has no directory
listing, so the server carries one file the host tool writes, and the rest is
a plain static tree of 8.3 names. The index is fetched once into a claim;
`FSV_LIST`, `FSV_CHDIR`, `FSV_STAT`, `FSV_ENUM` and `FSV_DFREE` are answered
from RAM; `FSV_READ` is one `GET`; `FSV_READAT` is one `GET` with `Range:`.
Upgrades want a tree published beside each release - one more step in the
release skill, written by `tools/os88httpdrv.py`.

Three further shapes were considered and refused:

- **Parse the server's own autoindex HTML** (Apache's, nginx's). No standard,
  no sizes on some servers, a parser per server, and hostile input of the
  worst kind. The index is 18 bytes a record.
- **Put the redirector inside ETHER.DRV.** A driver has one class, every
  ETHER.DRV user would carry the bytes, and the cable could not serve it.
- **A package rather than a driver.** A volume is something a driver adds
  (`OSAPI_VOL_ADD`'s fence); a package can only add a link.

## 3. The class, and what the kernel does NOT need

`DRVC_HTTP` = 10, appended after `DRVC_CD` because a class number is ABI
(`apps/os88api.inc`, `kernel/driver.inc`, `DRVC_MAX` 9 -> 10). It is a FILE
class, so its volumes are `DVK_FILE`; `dsk_vol_add` derives that for every
class from `DRVC_FILE2` up with the `jae` §119.1 put there, so the kind test
costs nothing. Why a NEW class and not `DRVC_FILE`: class 5 is `NET.DRV`, and
the cable is one of the two transports this drive runs over - a class is one
publication slot (§51.2.1), so sharing it would make *HTTP over the cable*
the one combination that cannot exist.

**Checked and needing nothing**: the icon pass reads `DSV_CAPS` off the
volume's own class (§62.9.19's table); `drv_fs_call` resolves the verb
through the mounted volume's class; `FSV_*` refusals at or past the table
length (§62.9.1.1); `OSAPI_FS_PROG` for the progress bar; `OSAPI_FS_ENT` for
the listing; the copy engine's `FSV_READAT` stream when `FSV_COPY` is 0.

**Hibernate and the DOS box.** Class 10, like 8 and 9, is past what a byte
mask can name, so `hbm_sweep` never asks it to leave. That is right here for
a better reason than CD-ROM's: the drive is STATELESS on the wire - no socket
outlives a verb (§4.1) - so it survives a hibernate untouched, and while
ETHER.DRV is suspended its verbs answer `FERR_IO` and the next one after the
card returns simply works.

**ABI.** A class appended at the end runs everything built before, so it is
`tools/abilock.py --update` without a `DRV_VER`/`PKG_FMT` bump - unless §119's
own landing says otherwise; read its commit before deciding.

## 4. The driver

### 4.1 The HTTP profile - §92.4's, plus `Range:`

```
GET /<prefix>/<path> HTTP/1.0\r\n
Host: <host>\r\n
User-Agent: os8088 HttpDrive 1.0\r\n
[Range: bytes=<from>-<to>\r\n]      FSV_READAT only
Connection: close\r\n
\r\n
```

One connection a request, closed by the server: no keep-alive, no chunked
decoding, no redirects (3xx is `Server answered 301`), `https://` refused by
name as the browser refuses it (§71.2) - a TLS source goes through the host
proxy (docs/plans/completed/PROXY-PLAN.md). **`Content-Length` is required**
and must equal the index's size for a whole-file read - which is the
integrity check that catches a tree replaced under a mounted index - and a
206 must carry a `Content-Range` that starts where it was asked. The header
reader is the Wire's line buffer, not the browser's state machine, for the
Wire's reason: a header's contents have to be read.

**Zero-copy.** `OSAPI_DRV_CALL` is an X stub that puts the CALLER'S DS in ES
for the socket verb's buffer. A driver can therefore point DS at the
destination segment the kernel handed it (`DX:BX`), call `NETV_RECV`, and the
body lands where the kernel wanted it with no staging copy - the same way a
package's own buffer does. The staging buffer (512 bytes) is for the header
lines only.

**Every wait is bounded by `OSAPI_GET_TICKS`** (CD-ROM's rule, §119.2):
connect 10 s, then 10 s without a byte. A file verb runs on the UI task with
the gfx lock held, so a stalled server freezes the machine exactly as long as
a stalled floppy would - the timeout IS the freeze's ceiling and must be
short. `NETE_BUSY` (another task inside the stack) is retried, never failed.

### 4.2 The index - `OS88.IDX`

Fetched once into a heap claim, **declared movable** (§66: the proc rewrites
the driver's one segment word for it). All of it is hostile and validated
before the first record is used.

```
header, 16 bytes
 +0  'OS88IDX', 0         magic and version 0
 +8  dw  record count     <= HF_MAXREC (896: one 16 KB claim)
 +10 dw  reserved, 0
 +12 dd  serial           the tree's, shown on the page; an upgrader's
                          "is this the release I think it is"
records, 18 bytes each, record 0 = the root
 +0  db[11] name          8.3, space-padded, FAT form - so §19.1's
                          sanitizer and the listing need no conversion
 +11 db  attr             FAT attribute byte: 0x10 = folder (FSV_STAT's BL,
                          §62.9.1, verbatim)
 +12 dw  parent           a record index; < this record's own
 +14 dd  size             a file's; a folder's is (first child, count) - its
                          children are CONTIGUOUS, which is what makes
                          FSV_LIST and FSV_ENUM a slice and the ordinal
                          stable by construction (§62.9.1's demand)
```

The handle §62.9.1 asks for **is the record index + 1** (0 being the root's
"no handle"). It never changes while the index is held, so the copy engine's
re-walk to an ordinal is exact. The URL of a record is the prefix plus its
parents' names joined by `/` - a walk of at most the tree's depth, and the
composed path is checked against a 128-byte cap.

**Validation** (refuse the whole index on any failure, `Not an os8088
index`): magic; count within cap and within the bytes delivered; every
parent below its child; every folder's child run inside the table and its
children naming it as parent; no folder's run larger than `DSK_NENT`, which
the host tool already refuses; names in the FAT character set. A CRC per
record was considered for upgrades and LEFT OUT of the mount: verifying a
system upgrade is the upgrader's job and wants a signed manifest, not a
checksum the same server wrote; `+10`'s reserved word is where a version 1
would say so.

### 4.3 The verbs

| verb | answer |
|---|---|
| `FSV_LIST` | the current folder's slice, through `OSAPI_FS_ENT`. **The first call fetches the index** (§1's laziness) |
| `FSV_CHDIR` | AX = a folder's handle, or 0; DX = its parent's handle |
| `FSV_STAT` | a name in the current folder: the handle, the size, BL = the attr byte |
| `FSV_READ` | one `GET`, into the caller's buffer; `FERR_BIG` past the capacity, before the request |
| `FSV_READAT` | one `GET` with `Range:`. A server that answers 200 instead of 206 has IGNORED it: the body is drained up to the offset and the rest delivered - correct on any server, slow only on one that will not range |
| `FSV_ENUM` | the *n*th of a named folder's slice |
| `FSV_DFREE` | 0 bytes free |
| `FSV_WRITE` `APPEND` `DELETE` `RENAME` `MKDIR` `RMDIR` | `FERR_WPROT` |
| `FSV_COPY` `FSV_RMTREE` | not published (0): the kernel's fallbacks |

`OSAPI_FS_PROG` after every `NETV_RECV`, so the progress bar moves for a
package launch off the drive, which no other caller would report.

### 4.4 Size, item by item (ESTIMATES)

| piece | bytes | comparable |
|---|---|---|
| header, verb table, refusals, `FSV_*` from the index | ~700 | CDROM.DRV's `cdiso.inc` verbs, less the ISO 9660 walk |
| index fetch, validation, path composer | ~450 | |
| HTTP: request, status line, header lines, body loop with deadline and progress, the 200-for-206 drain | ~750 | The Wire's fetch (§92.4), less its worker handshake |
| socket glue (`net_find`, open/send/recv/close loops) | ~250 | `apps/os88sock.inc` + `netpkg.inc` |
| Control Panel page: address field, Mount, status | ~1,000 | ETHER.DRV's address page (`ethcfg.inc`) |
| `HTTPDRV.CFG` read/write, package verbs | ~350 | `os88data.inc`, RAMDISK.DRV's two verbs at 118 (§62.9.16) |
| strings | ~400 | |
| **image** | **~3.9 KB** | |
| bss: staging 512, address 96, path 128, header line 32, state | ~0.8-1.3 KB | |

A `DRVM_IMG_*` ceiling row goes in `kernel/driver.inc` and `t_drvmem` holds
it, as every driver's does.

### 4.5 `kern_mega`

The driver touches no port and no selector arithmetic of its own: the one
thing to keep is §119.3.4's rule that a destination offset is walked and
never folded into its segment, so the buffer stays an identity selector
under protected mode. No `PKG_MEGA` arm is expected.

## 5. Where the files go

- **System disks**: `HTTPFS.DRV` in `SYSTEM\` on 720 KB, 1.2 MB and 1.44 MB,
  `kern_big` only (`$(DRIVERS)`; `kern_small`'s list never holds it). **The
  360 KB system disk is the owner's decision**: ~2.5 KB packed is five of
  its **11 free 512-byte clusters** (§9), and every 360 KB machine is an XT, where the
  drive works (ETHER.DRV and the cable both run on an 8088) but an XT with a
  card is the rare case. Options are on it, or `network360.img` carries it
  for a machine to copy into `SYSTEM\` - see the measured headroom in §9.
- **Live media and the everything set**: yes, on the system volume.
- **The server**: `tools/os88httpdrv.py export <src> <out>` writes the 8.3
  tree and `OS88.IDX` (`<src>` a directory, or a built `.img` read with
  `tools/os88fat.py`); `check <out>` is its own validator and a second reader
  of the format, `t_wab.py`'s role for WEAVE. The release skill gains one
  step: export the system disk's tree beside the images.

## 6. Open questions, in the order to settle them

1. **A driver has never called another driver's `OSAPI_DRV_CALL`.** The X
   stub and `drv_pkg_call_x` were written for packages: `wm_nest_pushd_x`
   pushes the caller's ES (here a driver segment) onto the frame-nest stack
   that `mem_in_nest` reads, which should only PIN the driver image during the
   call - harmless, possibly even right - and nothing else names "the caller".
   This is wave 0, a spike, before anything else is built: a ten-line test
   driver that opens a socket from inside an `FSV_LIST`.
2. **The cost of a request on the XT.** TCP is stop-and-wait (§72.4) and the
   name is resolved inside every `NETV_OPEN` (`netpkg.inc`), so each `GET`
   is a lookup, a handshake, the request and a close before its first body
   byte. Bulk throughput is known - 7 to 30 KB/s (FTP-PERF) - and the
   per-request floor is NOT: wave 0 measures it on `make xt-wire` and asks the
   5150 for a field number. If the floor is large, two remedies in order:
   build ETHER.DRV's reserved `NETV_RESOLVE` (~120 bytes of ETHER.DRV,
   resident in nobody's kernel) and open by dotted quad after the first
   lookup; then HTTP/1.1 keep-alive, which costs the parser `Content-Length`
   discipline it already has plus a socket held between verbs.
3. **The freeze.** Mitigated by the timeouts, not removed: a network read is
   a gfx-lock hold like a disk read (docs/plans/completed/UI-FREEZE-PLAN.md).
   SPEC.md 7.4's pointer tracking is an `int 13h` bracket and does not reach
   here - whether the arrow should track during a network read is a separate
   decision with its own trap (7.4's own history), and out of this plan.
4. **More than one drive.** One volume per driver in v1, as CD-ROM. Two
   addresses at once is one more volume handle and a second index claim, and
   no kernel byte.
5. **The 360 KB system disk** (§5).

## 7. Waves

- [ ] **W0 - spike and price**: driver-to-driver `OSAPI_DRV_CALL` from inside
  a file verb; a single `GET` timed on `xt-wire` (MartyPC has no NIC, so this
  is 86Box's figure, labelled as such, and the 5150's when it comes).
- [ ] **W1 - the class**: `DRVC_HTTP` = 10, the row, SYSTEM.CFG bit, `abilock`
  update; `tools/kernsize.py` on both kernels at one commit - `kern_small`
  must be byte-identical.
- [ ] **W2 - the host tool and the index**: `tools/os88httpdrv.py export` /
  `check`, the format pinned in SPEC.md first (a new top-level section, "the HTTP drive"), and
  a host-side hostile-index unit test feeding the driver's validator rules.
- [ ] **W3 - the driver, read path**: lazy mount, listing, chdir, stat, read,
  read-at with the 206 and the 200 arms, write refusals, progress, timeouts.
- [ ] **W4 - the page and the package verbs**: address field, Mount/Unmount,
  `HTTPDRV.CFG`, `HFV_*`.
- [ ] **W5 - the gate**: `tests/httpmount.py`, QEMU by name (MartyPC has no
  NIC, docs/TESTING.md's list item 5), serving a fixture tree from the host:
  list, walk, copy off byte for byte, launch a package, a write refused, a
  404, a server that ignores `Range:`, a truncated body, a hostile index.
  **Break it on purpose** (docs/WRITING-TESTS.md §1): a driver that skips the
  `Content-Length` check must turn the truncated-body leg red. Soak tier,
  `wants=` its own disk (`make httpmounttest`, `ethertest`'s shape).

## 8. What this is not

Not an upgrade mechanism: it is the transport one would read from. An
upgrader on top of it decides what to copy, verifies it, and survives being
interrupted mid-copy onto the system disk - none of which a read-only drive
can or should know. Not writable, not TLS, and not a cache: nothing fetched
is kept beyond the verb that fetched it except the index.

## 9. Measured on this tree

Read off `origin/elendilon` at 1b9bc77 (this plan's base), `make -j4`,
2026-10-22. Re-take every row at landing; these say what the plan was costed
against, not what the feature costs.

| quantity | value |
|---|---|
| `kern_big` footprint | `KERN_SIZE` 98,304 of `KERN_BUDGET` 100,864 - 2,560 spare. The class's ~76-80 bytes are `.text` + `.bss`, and the image rung has 409 left, so it crosses none - which is not the point (a byte costs a byte), but it means nothing has to be argued with the owner |
| `.text`+`.bss` | 48,743 of `KERN_CODE_MAX` 65,536 |
| `CDROM.DRV` packed, the nearest comparable | 5,381 bytes on the floppy today (§119.5 recorded 4,774 at landing) |
| `os8088-360.img` | 706 clusters of 512 bytes, **11 free** |
| `os8088-720.img` | 713 clusters of 1,024, 118 free |
| `os8088-120.img` / `os8088.img` | 1,215 / 1,691 free clusters of 512 |
| `network360.img` | 354 clusters of 1,024, 268 free |

The fast tier failed at this base on `volsig` (`network360.img` and
`os8088-720.img` sign as one volume, SPEC.md 18.8.2) - present before this
plan, which changes no shipped byte, and a defect to fix on its own whatever
is decided here.
