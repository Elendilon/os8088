# Desktop shortcuts: drag an entry out of a Disk window, keep it across a reboot

**OPEN. Nothing here is built.** Written on branch `desktop-shortcuts`, cut
from `elendilon` at `fb544b1`. Every figure for existing code is read out of
that tree or out of its build. Every figure for code that does not exist yet
is marked ESTIMATED. §9 lists the questions that change what gets built,
and the build waits on their answers.

The ask:

- Drag any file or folder from a Disk window onto the desktop and get a
  shortcut there.
- The shortcut snaps to a grid and survives a reboot.
- Click selects it, by inversion, exactly like a drive zone. Double-click
  does what a double-click on the same entry in its Disk window does. A
  target that is not reachable gives a toast.
- It persists in `SYSTEM.CFG` and costs nothing there when there is no
  shortcut.
- Its icon comes from the machine-wide icon store, with a tiny "shortcut"
  picture when no icon is available.
- **At most 1 KB of kernel.**

---

## 1. What the tree already has, and what it does not

Each row was read out of the tree. The surprises are in bold.

| need | what exists | where |
|---|---|---|
| a desktop zone that is not a volume | the Wire's SERVICE zone: one record, five one-compare arms in `desk.inc`, damage mask bit 8 | SPEC.md 26.7, `desk.inc:1431` |
| selection by inversion | `desk_sel` + `desk_zone_hilite` (XOR of the hit rect) + `desk_zone_redraw`'s four clip cases | SPEC.md 26.2, `desk.inc:1174-1217` |
| double-click on the desktop | `desk_click_x`, `DESK_DBLT` = 9 ticks | `desk.inc:1038` |
| a drag out of a Disk window | `fm_drag` → `fm_dgdrop`; **a drop where `wm_hit` finds no window is `ret`, a silent no-op** | `files.inc:6456`, `6623` |
| the dragged entry's identity | the clipboard record `fcp_arm` writes at drag BEGIN: drive, parent cluster, type, 8.3 name | `filecp.inc:2033` |
| open a folder in a Disk window | `fm_choose` (AL = vol, DX = cluster, SI = name): fronts, creates, or moves one at the cap | `files.inc:2532` |
| run a package by name | `ld_run_name_x` in the current folder; `ui_sys_open` is the bank → chdir → run → toast → back wrapper | `loader.inc:722`, `ui.inc:2449` |
| open a document by name | `ld_pkg_byname` → `assoc_run_x` (the by-name arm of `OSAPI_PKG_START`) | `loader.inc:1644` |
| a 16×16 icon for an entry | the machine-wide store, SPEC.md 25.9: keyed by (stem, size), **PURGEABLE** (`MEM_P_ICO`, the cheapest rank), dropped all at once | `disk.inc:7533-8300` |
| a toast | `toast_show`, at most 24 characters; `ld_say_status` for `LD_*` codes | SPEC.md 59 |
| persist a setting | SYSTEM.CFG, SPEC.md 51.5 | `driver.inc:564-4810` |

Seven facts shape the design. Four of them contradict a premise of the ask.

1. **SYSTEM.CFG is not sparse on write.** The reader tolerates a sparse
   file. The writer (`CFG_SAVE cpc`, in `CTRL.DRV`) rewrites EVERY key, every
   time, from resident state. Every key also has a FIXED length, and the
   reader refuses a record whose length is wrong. There is no
   variable-length record of any kind. So "costs nothing when absent" is not
   inherited from the format; this design has to provide it (§3).
2. **The read buffer is the file's size cap.** `ovl_cfg_load` calls
   `dskw_read` with `CX = CFG_FBUF` (131 bytes on kern_big), and a file
   larger than that fails with `FERR_BIG` before any I/O. So an OLDER kernel
   handed a SYSTEM.CFG that carries shortcuts loses EVERY setting, not just
   the shortcuts. That only bites on a downgrade: the file sits beside
   `KERNEL.SYS` on the same boot volume. It cannot be fixed from this side,
   and it gets written down in SPEC.md 51.5.
3. **`kern_small` does not read SYSTEM.CFG at all.** `drv_boot_x` is a
   `retf` there and `cp_cfg_save` is a `ret`.
4. **The icon store is 16×16, and it is a cache.** Bodies are 64 bytes,
   16 mask words and 16 data words, drawn by `icon_draw16`. The desktop's
   drive pictures are 32×32 in a different, kernel-internal format. Under
   heap pressure the store is shed WHOLE (`ico_demote`), and only open Disk
   windows re-harvest what they list (`fmv_icorefs`). **Nothing would
   re-harvest a shortcut.**
5. **There is no volume identity.** `BS_VolID` is pinned to `0x88000888` on
   every image and every formatted disk. A shortcut can name a drive LETTER
   and a location on it, and it has to re-check by NAME every time it is
   opened.
6. **There is no shortcut or alias glyph anywhere in the tree.** The
   fallback picture is new.
7. **A drag ARMS A CUT before it knows where it will land.** `fm_drag`
   calls `fcp_arm FCP_CUT` at `.begin`. A drop on the desktop today leaves
   the user's clipboard REPLACED by a Cut of the dragged file. A later Paste
   in another folder would then MOVE the original. That is a latent defect
   in today's tree. It becomes a live one the moment the desktop drop means
   something, so the create path disarms the clipboard (§5.1).

---

## 2. The resident shape

**The bulky state is not resident.** A shortcut table lives in a HEAP
claim, made at boot when the file carries shortcuts or at the first drop.
It is freed when the last shortcut is removed, so a machine with no
shortcuts pays `.bss` and code and no table.

```
SC_MAX   equ 7          ; see 6: the zone damage mask is one word, 9 bits taken
SC_REC   equ 48         ; ESTIMATED, the record below
claim    = SC_MAX * SC_REC = 336 bytes -> 1 KB claim (mem rounds to KB)
           (+ 64 a record if the bodies live here, 4.2 option I -> 784, still 1 KB)
```

### 2.1 The record

| off | len | field |
|---|---|---|
| 0 | 1 | volume index (0 = A:). 0xFF = a free row |
| 1 | 1 | grid cell: column in the high nibble, row in the low nibble |
| 2 | 1 | kind: 0 document, 1 package, 2 folder (the §19.1 type word's low byte) |
| 3 | 1 | flags (reserved; 0) |
| 4 | 32 | the PATH of the parent folder, `\APPS` style, NUL. 32 is `PTH_MAX`, the same cap as `FS_PATH` |
| 36 | 12 | the entry's 8.3 name, NUL-padded |
| (48) | (64) | the icon body, option I only (§4.2) |

**A path and not a cluster, and that is a deliberate choice.** A
(volume, cluster) pair is cheaper to resolve: one `dsk_chdir_q` and no
walk. But it means *this exact copy of this disk*. The six shipped 360 KB
disks and their 1.44 MB twins all carry `APPS\` with different clusters
under it, so a cluster shortcut to `B:\APPS\CALC.O88` breaks the first time
the user puts a different apps disk in B:. With no volume identity (fact 5),
the path is the only name for "the same file" that a floppy machine has. It
costs:

- ~40 bytes of resolver: walk components with `dskw_stat_x` and step in with
  `dsk_chdir_q_x`;
- one directory read per component, which only happens on a double-click.

The cluster form is the fallback if the bytes are needed elsewhere; it is
listed in §9.

The path has a cap: an entry whose folder path exceeds 31 characters is
refused at the drop with a toast, `Path too long`. A drive ROOT is the
empty path.

---

## 3. Persistence: a TRAILER after SYSTEM.CFG's terminator

The settings records are unchanged. **The shortcut block follows the
`dw 0` terminator** and exists only when there is at least one shortcut,
which is the "zero bytes when absent" property this format does not
otherwise have:

```
+0    'O88CFG',0,0  dw 3            ; unchanged
+10   records ... dw 0              ; unchanged - every existing reader stops here
+T    dw 'SC'  db ver  db count     ; ONLY when count > 0
+T+4  count * SC_REC                ; the resident table's own rows, verbatim
```

**Verbatim rows are the whole trick.** The reader does not parse a
shortcut. It copies `count * SC_REC` bytes into the claim, and the writer
copies them back out. A key/len record per shortcut was considered and
refused: it would need a second reader arm for repeated keys and buys
nothing. `ver` guards the row layout, the way a settings key's `ver` does
(SPEC.md 51.5). A wrong `ver`, a wrong signature or a short read
means no shortcuts, never an error.

### 3.1 The reader: in `.ovl`, which costs nothing on disk

`.ovl` rides the stage-2 blob, which is a fixed 10 plain sectors read in 2
calls on every geometry (`t_blobruns`). It has **308 bytes spare on
kern_big**, and bytes added there change no read at all. The reader's
addition is ESTIMATED at ~70 bytes:

1. Before reading, `dskw_stat_x SYSTEM.CFG`: DX:CX = its size, from a
   directory the mount already holds, so no I/O.
2. If size ≤ `CFG_FBUF`, take today's path exactly.
3. Otherwise:
   - `mem_claim` the shortcut table (1 KB);
   - `dskw_read_x` the WHOLE file into it, with capacity = the claim. That
     is ONE read, and for a ≤ 1 KB file it is the same `int 13h` count as
     today: one cluster on 360 KB, and two contiguous sectors on 1.44 MB,
     because `dskw_write_sys` writes the file in one allocation;
   - `rep movsb` the first `CFG_FBUF` bytes into `ovc_buf`;
   - run today's deserialiser;
   - walk to the terminator (the deserialiser already finds it), check
     `'SC'`/`ver`/`count`, and move the rows down to the claim's base.
4. `mem_movable` the claim with a relocation proc that stores the new
   segment in `[sc_seg]`. That is `ico_reloc`'s shape, ~8 bytes of `.text`,
   and HEAP-UNPIN's rule: a boot claim is a wall otherwise.

**No new `int 13h` comes from the reader.** A boot WITHOUT shortcuts runs
exactly today's path plus one `dskw_stat` that touches no disk.

### 3.2 The writer: in `CTRL.DRV`, which is not resident

`cpc_save` already rebuilds the file whole from resident state. It gains:

- after `cpc_ser`'s terminator, `if [sc_seg]`, emit the 4-byte header and a
  `rep movsb` of the live rows, compacted;
- `cpc_buf` grows by `SC_MAX * SC_REC` in the module's own `.modcb`.

ESTIMATED ~40 bytes of module code and ~340 of module bss: **zero resident
bytes**, paid only while `CTRL.DRV` is loaded.

### 3.3 When it writes

A shortcut must survive a power-off, so "at the next panel close" is not
good enough. Every create, move and remove ends in an immediate write
through the resident `cpf_cp_flush_close` thunk, after setting
`[cp_wdirty]`. Two cases change that, and both already have the shape that
handles them:

- **The Control Panel is open.** `cpf_cp_flush_close` ends in an
  unconditional `mod_drop MOD_CTRL`, and that would free a live panel's code
  (`mod.inc:550`). So the shortcut path tests for a live panel and only sets
  `[cp_wdirty]`; the panel's own close writes. ~8 bytes.
- **The boot disk is not in its drive.** `cpf_need` fails, the existing
  toast says `Not Saved: No Sys in A:`, and `[cp_wdirty]` stays set. The
  next panel close, Restart or hibernate retries it. The shortcut is live
  for the session either way.

The write costs ~5 `int 13h` (directory, FAT, data, directory, FAT), which
is ~2 s on a 4.77 MHz XT. It is paid only at a gesture the user just made,
never at boot or at paint.

---

## 4. Icons

### 4.1 Where the picture comes from at the DROP

The dragged entry already has its body in the window: `fmv_get_icon` on
its listing index returns the 64-byte body or all-zero.

- A **folder** is `dsk_folder_ico`, resident, by kind. It needs no body.
- A **document** is the composed page + 8×8 glyph (SPEC.md 54.3). It is
  already a 64-byte body in that window's store row.
- A **package** is its harvested icon, or zero.

### 4.2 Where it lives AFTER the drop: the one real fork

The ask says to reuse the global icon store. The store is a CACHE (fact
4), and the two readings of "reuse" have different failure modes:

| | **I. the body travels with the shortcut** (recommended) | II. the shortcut keys the store | III. II, with the store made a HELD claim |
|---|---|---|---|
| what the record holds | 64-byte body | (stem, size) key, 10 bytes | (stem, size) key |
| boot | rows land in the claim; done | `ico_need` + `ico_put` per shortcut: **a 4 KB claim at every boot that has a shortcut**, today made lazily | as II |
| after the heap sheds the store | unaffected | **every shortcut falls back to the tiny glyph** until reboot, or until a Disk window happens to list that package again | cannot happen |
| heap | +64 a shortcut, inside the same 1 KB claim | -54 a shortcut, +4 KB store pinned live from boot | **4 KB NEVER purgeable** on every machine with one shortcut; docs/reports/DOS-GAMES-2026-09-16.md lost a game by 3 KB |
| resident code | `icon_draw16` from a staged copy: ~15 | key match + `ico_find` per paint + boot seeding: ~45 | II + a purge-rank switch: ~60 |
| what is reused | the store as the SOURCE at the drop; the format and the draw routine always | the store as the only home | as II |

**I is recommended.** The shortcut persists its own picture, which is what
"embedded icon data" in the ask already implies. It never degrades. It costs
no kernel bytes beyond the draw, and its heap cost sits inside a claim that
exists anyway. II re-introduces exactly the degradation I avoids, and III
spends 4 KB of every shortcut user's heap to prevent it.

### 4.3 The fallback picture

The fallback is for a body that is all zero at the drop: a package with no
icon, or a store that had been shed. The tiny shortcut picture is an 8×8
curved arrow drawn into the 16×16 cell's lower left. It is staged into
`dsk_ico`'s scratch and drawn with `icon_draw16`. ESTIMATED 8 bytes of glyph
+ ~18 to expand it. Whether the arrow also OVERLAYS every shortcut, as a
Windows or System 7 alias badge does, is §9 Q5.

### 4.4 Size on the desktop

A shortcut draws its 16×16 icon centred in a cell, with its caption below,
like a drive zone. **It is not pixel-doubled to 32×32.** A doubler is a
256-byte stage and ~40 bytes of code, and on the CGA, whose drive pictures
are 14 rows tall (SPEC.md 26.4), a doubled 16-row picture is 32 tall in a
34-row step. The Disk window's own icon view is 16×16, so the desktop
matches what the user dragged. This is §9 Q4.

---

## 5. Gestures

### 5.1 Create: a drop on empty desktop

`fm_dgdrop`'s `jz .out` (no window under the point) becomes `jz .desk`:

1. **Refuse** silently, as a drop on nothing does today, if the point is:
   - on the menu bar or the dock, or
   - inside a drive or service zone's rect, or
   - not on the primary display: the extended desktop gets no shortcuts.
2. **Snap**: cell = ((x − origin) / pitch, (y − `MBAR_H`) / step), rounded
   to the nearest cell. If that cell is taken, toast `No room there`. The
   alternative, searching for the nearest free cell, is ~30 bytes more and
   is §9 Q7.
3. **Fill a free row**:
   - volume = `[fcp_cbdrv]`;
   - parent path = the source window's `FS_PATH`;
   - name and kind = the clipboard record;
   - body = `fmv_get_icon`.

   If there is no free row (`SC_MAX` reached), toast `Too many shortcuts`.
   If no claim exists yet, `mem_claim` one first.
4. **Disarm the clipboard**: `[fcp_cbop]` = none (fact 7). It is one store,
   and it fixes today's latent defect as well.
5. `desk_zmark` the new zone and write (§3.3).

### 5.2 Select and open: `desk_click_x`

A shortcut is zone index `DESK_SC0 + i`, where `DESK_SC0` = `DESK_NZ`
(9 on kern_big). Every routine in `desk.inc` is already asked about an
INDEX, which is what let the Wire's zone cost five one-compare arms. A
shortcut zone gets the same arms in:

- `desk_zone_rect`: from its grid cell, not from `desk_ord_xy`;
- `desk_draw_zone`: an icon16 and a caption;
- `desk_zone_label`: the 8.3 name, or the stem, §9 Q6;
- `desk_click_x`: hit rect and double-click dispatch;
- `desk_dmg_zones`: its mask bits.

`desk_sel` and `desk_zone_hilite` serve it unchanged, so selection inverts
exactly as a drive's does, with §26.2's flip-not-repaint under a covering
window. **A shortcut does not move when a volume mounts**, so it is outside
`desk_zones_dmg`'s ordinal extent; its arm is a fixed rect.

**Double-click → `sc_open`**, `.cold`, no gfx lock held: the same context
`desk_click_x` gives `files_open_drive` and `ui_svc_open`. It runs these
steps:

1. Bank the user's place (`osapi_file_here`), as `ui_sys_open` does.
2. Volume row free (`DVK_FREE`, no such drive) → toast `No drive B:`.
3. Quiet-mount that volume at its root. Failure, which is no disk → toast
   `No disk in B:` through the mount's own `FERR_NODISK` path.
4. Walk the path: `dskw_stat_x` each component, require the directory
   attribute, step in. A miss → toast `Not found`.
5. `dskw_stat_x` the name. A miss → `Not found`. The kind must still agree,
   so a folder replaced by a file is `Not found`.
6. Dispatch on kind. **This is what the Disk window does, by name, through
   the doors it already has:**

   | kind | action | why that door |
   |---|---|---|
   | folder | `fm_choose` (AL = vol, DX = the folder's cluster from step 5, SI = name) | fronts a window already showing it, opens one, or moves the frontmost at `FM_MAXWIN` |
   | package | `ld_run_name_x`, then `ld_say_status` on failure | `ui_sys_open`'s own pair |
   | document | `ld_pkg_byname` with the staged 16-byte locator | `OSAPI_PKG_START`'s by-name arm, which `assoc_run_x` drains: the association lookup, `Needs X.O88` and the hand-over. `[assoc_pwin]` = 0, so it reads the home from the globals step 4 just set |

7. Put the user's place back (`ui_tm_back`).

**Nothing is extracted from the file manager.** `fm_open_sel` is welded to
a listing INDEX and its window's cache. Every arm it reaches already has a
by-name twin, and those twins are what other desktop launchers use. So
`sc_open` is a resolver in front of three existing calls.

### 5.3 Move: drag a shortcut

This is in the ask ("snapped to a grid"), and it is §9 Q2. `desk_click_x`
sees the button still down after `FM_DRAGMIN` pixels and runs a drag loop.
The loop is `fm_drag`'s shape with its outline routine:

- `fm_dgxor` draws the 96×16 XOR bar. Called with the zone's own rect
  instead, it is a one-register change.
- Drop → snap (§5.1 step 2) → store the cell → `desk_zmark` old and new →
  write.

A drop on the dock or a drive refuses and leaves the shortcut where it was.

### 5.4 Remove

**The ask does not say how a shortcut goes away**, and there is no Trash.
§9 Q3 offers three ways.

---

## 6. Limits that fall out

- **`SC_MAX` = 7 on kern_big.** The damage mask is ONE word (`wm_dmg_zn`;
  `desk.inc:950` asserts at most 16 zones). The 8 volume zones and the Wire
  take 9 bits, which leaves 7. Eight or more costs a second mask word through
  `wm_paint_dmg`, ESTIMATED +25 bytes. §9 Q8.
- **The grid** shares the drive column's pitch so the two line up:
  - row step = `[desk_zstep]`: 60 on VGA and Hercules, 34 on the CGA;
  - column pitch = `DESK_COLW` (44) is too narrow for a caption. An 8-letter
    stem is 64 px, so the pitch is 72.
  - At 72 × 60: VGA has 7 columns × 7 rows left of the drive column,
    Hercules 8 × 4, and CGA 7 × 4.
  - 4 bits a coordinate suffices on every adapter. The cells under the drive
    columns are refused (§5.1).
- **The extended desktop is out.** A shortcut lives on the primary display.
- **`kern_small` is out unless §9 Q1 says otherwise.** It reads no
  SYSTEM.CFG at all (fact 3), so persistence there is a reader and a writer
  that do not exist, rather than a trailer. The `desk.inc` arms would be
  `%ifndef KERN_SMALL`, as the Wire's are. `kern_emu` inherits kern_big's.

---

## 7. The bill against 1 KB

Every figure in this section is ESTIMATED.

### 7.1 Two placements

`CTRL.DRV` is ALREADY loaded at the end of every create, move and remove,
because that is where the writer lives. So the bodies of those three
gestures can be module entries in it, and their resident cost falls to a
thunk each. ONDEMAND-PLAN's test is met: the gesture is only worth making
if it can be persisted, and persisting needs the system disk.

| piece | where | A: all resident | **B: gestures in `CTRL.DRV`** (recommended) |
|---|---|---:|---:|
| zone arms: rect, draw, label, click, damage | `.cold` | 220 | 220 |
| `sc_open`: resolver + 3-way dispatch + toasts | `.cold` | 180 | 180 |
| fallback arrow glyph + expand | `.cold` | 26 | 26 |
| drop → create: snap, refuse, fill, disarm | `.cold` / module | 200 | 30 |
| move: drag loop + snap | `.cold` / module | 110 | 70 (the loop stays; the commit moves) |
| remove (§9 Q3) | `.cold` / module | 60-90 | 25 |
| write trigger + live-panel guard | `.cold` | 30 | 15 (folded into the module call) |
| module entries: 4 `.bss` + thunk each, x3 | `.bss`/`.cold` | - | 50 |
| `.bss`: `sc_seg`, `sc_n` | `.bss` | 3 | 3 |
| claim relocation proc | `.text` | 8 | 8 |
| toast strings not already in the tree (~5) | `.text` | 60 | 60 |
| **resident total** | | **~900-930** | **~690** |
| boot reader | `.ovl` (308 spare, no disk cost) | 70 | 70 |
| writer + gesture bodies | `CTRL.DRV` (not resident) | 40 | 330 |

**B fits with ~330 bytes of headroom. A fits only if the estimates hold.**
Neither touches `.lowbss`, which has 34 bytes left and is not needed. The
cold rung currently has 497 bytes before its next crossing, so either option
crosses it. Per CLAUDE.md, that is the bytes' business and not the rung's.

### 7.2 The one `int 13h` this cannot avoid

The question asked was whether the BOOT PARSING costs another `int 13h`.
It does not (§3.1). **The resident code does, on the 360 KB disk.**

- `KERNEL.SYS` on `os8088-360.img` ends on the LAST sector of cylinder 9,
  with 48 bytes free in that sector.
- Resident bytes grow the packed tail at about 0.8×. So past ~60 resident
  bytes, every 360 KB boot reads one more cylinder run: one more `int 13h`,
  ~400 ms on an XT, on every CPU.
- The 720 KB, 1.2 MB and 1.44 MB disks have 7 to 16 sectors of headroom in
  the run and pay nothing.

This is not specific to shortcuts; any resident feature over ~60 bytes pays
it next. It is named here so that it is decided rather than discovered. The
options are in §9 Q9.

---

## 8. Gates (to write with the code; docs/WRITING-TESTS.md)

Each gate is to be broken on purpose and watched go red before it counts.

| row | asserts | how it goes red |
|---|---|---|
| `scdrop` (soak) | drag `B:/APPS/CALC.O88` onto the desktop: the zone appears at the snapped cell; `[fcp_cbop]` is disarmed; SYSTEM.CFG on A: carries the trailer | omit the disarm; omit the write |
| `screboot` (soak) | `system_reset`; the zone comes back at the same cell with the same body; settings are untouched | read the trailer with the wrong `ver` |
| `scopen` (soak) | double-click each kind: a folder fronts or opens a Disk window on it; a package runs; a document opens in its program | swap two dispatch arms |
| `scmiss` (soak) | B: empty → `No disk in B:`; file renamed → `Not found`; volume row free → `No drive` | read the toast cell out of guest memory |
| `t_sccfg` (fast, host-side) | `tools/` round-trips the trailer format against the SPEC.md table; a file with no shortcuts is byte-identical to today's | change `SC_REC` in one place only |

All of these run on MartyPC, `os88ui` driven, `os8088_xt_vga` and a 1bpp
twin. A drawing change is not done until it has been looked at on the CGA
(SPEC.md 26.1).

---

## 9. Questions

| # | question | recommendation | what changes |
|---|---|---|---|
| Q1 | `kern_small` too, or `kern_big` (and `kern_emu`) only? | big only; small has no SYSTEM.CFG to persist into | small needs a reader and writer from scratch, +~300 |
| Q2 | can a shortcut be dragged to a new cell after creation? | yes, §5.3 | -110 / -70 if not |
| Q3 | how is a shortcut REMOVED? (a) drag it back into any Disk window; (b) select it, Locator `File` → `Remove Shortcut`; (c) select it + Delete key | (a): no menu item, no predicate, no keyboard route; the gesture undoes the gesture | (b) is a menu row + greying predicate, +~60 |
| Q4 | 16×16 centred, or doubled to 32×32 to match the drives? | 16×16 (§4.4) | doubling +~40 code and a 256-byte stage |
| Q5 | arrow badge on EVERY shortcut, or only as the no-icon fallback? | fallback only, as asked | always: +~10, and the badge covers part of a 16×16 picture |
| Q6 | caption: full 8.3 (`CALC.O88`), stem (`CALC`), or the package's header name (`Calculator`)? | stem for packages, full 8.3 otherwise | header name needs a read at the drop and 12 more record bytes |
| Q7 | drop on an occupied cell: refuse with a toast, or take the nearest free cell? | refuse | nearest-free +~30 |
| Q8 | is 7 shortcuts enough? | yes for now; the record and trailer allow more | 8+ costs a second damage word, +~25 |
| Q9 | the 360 KB boot's extra `int 13h` (§7.2): accept it, find an offsetting ~60 packed bytes elsewhere first, or something else? | accept, and say so in the commit | an offset is its own size pass |
| Q10 | path (§2.1) or (volume, cluster)? | path: survives a different copy of the same disk | cluster saves ~40 resident and 20 bytes a record, and breaks on any other copy |
| Q11 | the store fork (§4.2): I, II or III? | I | II/III as tabled |
