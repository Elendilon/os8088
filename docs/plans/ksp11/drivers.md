# Kernel size pass 11 - drivers: EMS.DRV and HDD.DRV's incoming code

Branch `ksp11-drivers`, cut from `elendilon` at `2a05e31f`. The concept is
the LOADABLE driver code that came in since the squash and is resident
whenever its driver is mounted: all of `EMS.DRV` (SPEC.md 107, new since the
squash, so every verb and table in it was free to change) and `HDD.DRV`'s
incoming changes (SPEC.md 52.1.1 - 52.1.3: rung 1 takes a drive the BIOS also
knows, `OSAPI_VOL_TAKE`, `rep insw`, the seconds-long wait).

**A driver is claimed in whole KB** (`drv_load` claims `ceil(image / 1024)`,
`DRVR_KB`; `os88drv.py` strips trailing zeros only down to that rung), so a
driver byte buys RAM only when a KB boundary is crossed. Bytes are still the
currency - every figure below is the assembled image - and the KB claim is
quoted beside it.

## Base and tip

| | base `2a05e31f` | tip | delta |
|---|---:|---:|---:|
| `EMS.DRV` image (`build/ems.bin`) | 1,208 | 704 | **-504** |
| `EMS.DRV` claim | 2 KB | **1 KB** | **-1 KB** |
| `EMS.DRV` file (LZ4) | 815 | 675 | -140 |

The kernel is unchanged in size on both builds by the EMS half (one
constant's VALUE, `DRVM_IMG_EMS` 2 -> 1, in `kernel/driver.inc`'s table:
`tests/unit/t_drvmem.py` checks it against the built image).

## TAKEN

### EMS.DRV (all of it new since the squash)

| item | bytes |
|---|---:|
| `em_pown`, the 256-byte per-page owner table, DELETED: a handle is one contiguous run, so first fit (`em_alloc`) asks the eight handles - the run's END starts at the request, and a live handle that overlaps it moves the start to that handle's end and restarts. Proved equal to the page scan in a Python model, 20,000 random alloc/free sequences on boards of 4..256 pages. CAPS's free count is the board less every handle's length | -256 state, and `em_drop`'s page loop |
| handle tables 1..8 indexed `2 x (h - 1)`, the unused slot 0 gone; base (a page fits a byte) and owner packed in one word, `em_hbo` | -9 state |
| owners kept as `slot XOR 0FEh`, so 0 is "nobody": no quarter init at attach, a free test is `cmp x, 1` / `rcl` | -9 attach, smaller tests |
| THE SERVICE TABLE IS THE HANDLE TABLE: the kernel copies a driver's service table once, at attach (`drv_publish`), and an attach only ever meets a fresh image (`drv_load_row`'s `.already`) - so the 34 cells below `DSV_PKGCALL` are `em_hlen`/`em_hbo` while still zero (HDD.DRV's hd_mbr rests on the same fact) | -34 |
| DI saved once in `em_pkg`, the eight per-verb `push di`/`pop di` pairs gone; the verb's CF carried across `popf` in BH's low bit (`rcl`/`rcr`) where `jc`/`popf`/`clc`/`jmp`/`popf`/`stc` was; an unknown verb is a table cell (`em_bad`) | ~-25 |
| attach inlined (one caller each for `em_find`, `em_try`, `em_size`); the frames are `ES - 1000h` from F000h rather than a table; the bases walked by `lodsw`; quarter 0's and 1's probe bytes through `[es:di]`/`[es:bx]` (DI = 0, BX = 4000h, BX banked) instead of `[es:0]`/`[es:4000h]`; `em_ok260` became one store over the list's 260h | ~-60 |
| `em_hnd` falls into `em_bad`, which every verb's refusal shares; `em_free`/`em_gone` share `em_zap`; GONE falls into UNFRAME's walk with every quarter asked | ~-40 |

Every verb keeps every register it kept before except one: FREE's AX was
the handle on success and is 0 now (no caller reads it: `apps/video`'s two
FREE sites and `tests/emstest`'s one). MAP still keeps CX and DX, which
`vp_emap` steps through.

## REFUSED

## Defects found

## Cross-file list (for the coordinator)

* `kernel/driver.inc` `DRVM_IMG_EMS equ 2` -> `1` (voltake's file, a value
  in `drv_memk`'s table, no size change): the image is 1 KB now and
  `t_drvmem` fails without it.

## Rows run

* `ems`, `emspico`, `videms`, `videmshyb` - ok (MartyPC, 4/4).
