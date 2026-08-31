; =============================================================================
; kernel/dskwin.inc - THE MOUNT-OWNED WINDOW, AT THE BOTTOM OF `.lowbss`
;
; Three buffers and the four constants that size them. They were the last
; thing in `disk.inc`'s `.lowbss` block, which put them at the TOP of the
; rung; they are here, in the FIRST file kernel.asm includes, so that they are
; the FIRST thing in `.lowbss` and therefore sit immediately above FAT_SEG.
;
; WHY THE ADDRESS MATTERS, when no other `.lowbss` byte's does (SPEC.md 2.1.2).
; The FAT window and these three come alive at the SAME MOMENT - the first
; mount - and are untouched before it. Adjacent, they are one contiguous
; 8,192-byte region that is dead for the whole of `kmain`:
;
;     FAT_SEG   4,608   the FAT snapshot, filled at mount
;     +         1,024   disk_dir    "ALWAYS exactly a mount snapshot"
;     +         2,048   disk_icons  "fully rewritten every mount"
;     +           512   dsk_secbuf  read by drv_boot's very first mount
;     =         8,192   512-aligned by construction, LOW_SEG being a rung base
;
; That is what the boot overlay is meant to land in and spill through
; (docs/BOOT-LADDER-PLAN.md stage B): `.ovl` is 6,688 bytes and the FAT window
; alone is 4,608, so the window alone stopped being enough when SPEC.md
; 2.9.12's register moved twenty bodies into the overlay.
;
; NOTHING ELSE MOVED, and that is the point of doing it this way. `.lowbss` is
; `nobits`, so this costs no byte on the disk and no byte of RAM - the rung is
; the same size and holds the same things in a different order. What it buys
; is that the dead bytes are TOGETHER.
;
; POSITION IS BOUND BY INCLUDE ORDER, not by anything declarative: `-f bin`
; lays a section out in the order its contributions appear, and `.lowbss` has
; twelve contributors across the tree. So this file being first in kernel.asm
; is the whole mechanism, and tests/unit/t_lowwin.py is what says so if it
; stops being true. A `section .mntwin` of its own was the obvious alternative
; and is wrong here: these are reached through SS with the rest of `.lowbss`,
; so a segment of their own would be a code change at every access.
; =============================================================================

DSK_DE_SIZE  equ 32              ; staged directory entry stride (SPEC.md 19)
DSK_ICO_SIZE equ 64              ; harvested icon slot stride (SPEC.md 19)

; How many entries a listing holds. DSK_NENT is the FLOOR - the .lowbss pair
; every floppy uses, and the fallback for a driver-backed volume whose driver
; could not fund a bigger one. DSK_VENT is what a hard disk gets: 96 bytes an
; entry (32 of directory + 64 of icon), so 64 entries is a 6KB claim, made by
; the driver at mount and mirrored per open Disk window by the file manager
; (SPEC.md 22.6). Both numbers are here so nothing can disagree about them.
DSK_NENT     equ 32
DSK_VENT     equ 64
DSK_VBYTES   equ DSK_VENT * (DSK_DE_SIZE + DSK_ICO_SIZE)    ; 6,144 = 6KB
DSK_VKB      equ 6

section .lowbss                 ; LOW_SEG: written by int 13h through ES:BX
                                ; (or rep movsw/stosw from the mount), read
                                ; only through disk.inc's dsk_get_*
dsk_win_base:
disk_dir:   resb DSK_NENT*DSK_DE_SIZE      ; DSK_NENT SYNTHESIZED entries,
                                ; built by disk_mount from the FAT directory
                                ; (SPEC.md 19) - never a raw on-disk image.
                                ; The FLOOR listing: a driver-backed volume
                                ; lists into its driver's claim instead, and
                                ; [dsk_dseg]/[dsk_doff] say which is in use
disk_icons: resb DSK_NENT*DSK_ICO_SIZE     ; harvested icon slots; slot i
                                ; belongs to directory entry i, all-zero =
                                ; no icon; fully rewritten every mount
dsk_secbuf: resb 512            ; sector scratch: BPB read, root-dir scan,
                                ; icon harvest, and the loader's header peek
dsk_win_end:
DSK_WIN_BYTES equ dsk_win_end - dsk_win_base

section .text
