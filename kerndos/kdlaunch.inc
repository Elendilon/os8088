; =============================================================================
; kerndos/kdlaunch.inc - THE LAUNCH BLOCK (docs/plans/KERN-DOS-PLAN.md §7 step 4)
;
; What the running os8088 tells `kern_dos` about the program it is handing
; over, staged in the text framebuffer by the box and copied into `kern_dos`'s
; own image by the stub (§7 step 7).
;
; **IT IS A GATHER/SCATTER OF THE BOX'S OWN BSS, and that is the whole trick.**
; Both sides `%include "dos.asm"`, so `dos_name`, `dos_args`, `dos_ebuf` and
; the rest are the same offsets FROM `DOS_CBASE` in the box and in
; `kern_dos` - the images differ, the DBSS layout cannot. So the block is a
; list of (offset, length) rows that one side gathers from and the other
; scatters to, and adding a field is one line HERE rather than two copies of
; marshalling code that drift.
;
; The two sides emit the list separately and neither trusts the other's: the
; block carries the payload length, each side sums its own, and a mismatch is
; refused at the entry rather than scattered into the wrong fields. That is
; eight bytes against a machine where a DOS program starts with somebody
; else's environment in its PSP and no way to notice.
;
; **THE MAGIC IS NOT DECORATION EITHER.** The block lands in a segment the
; stub chose, and on the arm this wave builds there is nothing to come back
; to: a `kern_dos` that ran on a block nobody staged would build a PSP out of
; whatever the adapter's RAM held and hand it to a program. `KDL_MAGIC` is
; the one cheap thing that cannot happen by accident.
; =============================================================================

KDL_MAGIC   equ 0               ; dd 'KDL1'
KDL_VER     equ 4               ; dw  KDL_VER_NOW - bumped when a ROW MOVES, not
                                ;     one is added at the end
KDL_FLAGS   equ 6               ; dw  KDLF_*
KDL_TLEN    equ 8               ; dw  the payload's bytes, as the SENDER
                                ;     counted them
KDL_CAP     equ 10              ; dw  KB the machine has (the BDA's, banked by
                                ;     the box because kern_dos's own int 12h
                                ;     would answer the same and this is the
                                ;     one place a cap can be imposed)
KDL_UNIT    equ 12              ; dw  THE UNIT `int 19h` IS TO BOOT FROM, and
                                ;     like KDL_DPT it is the KERNEL's field:
                                ;     `hbm_dosrun` patches the boot volume's
                                ;     own int 13h unit into the staged block.
                                ;     The bootstrap takes no documented input
                                ;     and GLaBIOS reads the drive out of DL as
                                ;     it finds it (SPEC.md 96.40.2), so a 0
                                ;     here is drive A: - which is right on the
                                ;     machine 9 of docs/plans/KERN-DOS-PLAN.md
                                ;     is about and is an EMPTY DRIVE on the one
                                ;     8 is about. It read as the ROM's boot
                                ;     menu waiting for a key
KDL_MOUBASE equ 14              ; dw  THE SERIAL MOUSE'S UART BASE, 0 = this
                                ;     machine has none that `kern_dos` can
                                ;     drive (SPEC.md 96.45). KDL_UNIT's field
                                ;     and not the box's: `mouse_init` spends
                                ;     596 ms at boot deciding which port has a
                                ;     mouse and which LINE it actually fires,
                                ;     against a modem on the other one
                                ;     (SPEC.md 9.5), and that contest is not
                                ;     reconstructible from anything a package
                                ;     can see - so `hbm_dosrun` patches the
                                ;     answer into the STAGED block beside the
                                ;     boot unit and the DPT.
                                ;     **IT WAS `KDL_RSVD` AND THE SPARE IS
                                ;     WHY NO VERSION BUMP IS OWED**: KDL_VER
                                ;     moves when a ROW MOVES, and filling a
                                ;     reserved word in the header moves none.
                                ;     KDL_TLEN covers the gathered BODY alone,
                                ;     so both sides still sum the same list
KDL_MOULINE equ 27              ; db  ...and its bit in the master 8259's mask -
                                ;     `mouse.inc`'s MOU_L4 (0x10) or MOU_L3
                                ;     (0x08). **AT 27 AND NOT 15**, which is
                                ;     the free byte the DPT leaves (16..26)
                                ;     rather than the base's OWN HIGH BYTE:
                                ;     a word at 14 occupies 14 AND 15, so a
                                ;     line mask at 15 wrote 0x10 over the top
                                ;     of 0x03F8 and kern_dos drove a UART at
                                ;     0x10F8. The low byte still looked right,
                                ;     which is what made it read as a mouse
                                ;     that was simply never there.
                                ;     CARRIED RATHER THAN DERIVED from
                                ;     the base, because a card at 2F8 jumpered
                                ;     to IRQ4 is a machine this project has
                                ;     met (SPEC.md 9.5.2.1) and the kernel
                                ;     learned which line fires by watching
                                ;     packets arrive on it
KDL_DPT     equ 16              ; db[11] THE DISKETTE PARAMETER TABLE, and it
KDL_DPT_LEN equ 11              ;     is the KERNEL's rather than the box's -
                                ;     the one field below that no package can
                                ;     fill, so `hbm_dosrun` patches it into the
                                ;     STAGED copy after the box has gathered
                                ;     the rest. SPEC.md 18.92: `int 1Eh` is a
                                ;     POINTER the BIOS re-reads on every floppy
                                ;     operation, os8088 points it at its own
                                ;     patched copy at boot, and `kern_dos`
                                ;     lands on the same segment with that copy
                                ;     at a DIFFERENT offset - so a handover
                                ;     that does not carry these eleven bytes
                                ;     leaves the ROM reading whatever kern_dos
                                ;     happens to have there. It reads as "the
                                ;     disk could not be mounted", which is a
                                ;     true sentence about the wrong thing.
                                ;     ZERO = leave the vector alone, which is
                                ;     the W4 gate's case: it boots through a
                                ;     loader that never touched it
; **THESE TWO ARE `%assign` AND THE REST ARE `equ`**, which is not a style
; slip: the fit assert below runs at PREPROCESSOR time and `%if` cannot see an
; assembler symbol. A `%assign` reads the same everywhere an `equ` does and
; loses only its line in the map file.
%assign KDL_BODY 28             ; ...and the gathered fields from here
%assign KDL_SIZE 512            ; one sector, which is what the stub moves and
                                ; what `kern_dos` reserves in its own image.
                                ; The payload is 377 bytes today; the assert
                                ; each side writes is what keeps it true

KDL_SIG     equ 0x314C444B      ; 'KDL1', little-endian
KDL_VER_NOW equ 2               ; what this tree writes and checks. It is a
                                ; CONSTANT and not a literal at three sites,
                                ; because a version that has to be bumped in
                                ; three files is a version that gets bumped in
                                ; two. 1 -> 2 is KDL_DPT moving the body

KDLF_REBOOT equ 1               ; bit 0: `int 19h` when the program exits.
                                ; docs/plans/KERN-DOS-PLAN.md §9 - there is no
                                ; hibernate image to come back to, so the
                                ; machine restarts. W6 is the other arm and
                                ; this bit is where it hangs
KDLF_HIBER  equ 4               ; bit 2: THE KERNEL HAS WRITTEN A HIBERNATION
                                ; IMAGE, so the exit code has somewhere to go
                                ; (docs/plans/KERN-DOS-PLAN.md 8). It is not
                                ; the box's to set and never arrives from it:
                                ; `hbm_dosrun` patches it into the STAGED
                                ; block, because whether there is a fixed disk
                                ; to come back to is `hb_pick`'s question and
                                ; the kernel is the only side that can ask it
KDLF_EXE    equ 2               ; bit 1: the box already knows it is an .EXE.
                                ; A HINT and not an instruction - kern_dos
                                ; still asks `dos_is_exe`, which reads the
                                ; FILE (SPEC.md 96.8) - carried so the two
                                ; answers can be compared on the glass

; -----------------------------------------------------------------------------
; KDL_FIELDS - the list, ONCE.
;
; ORDER IS THE WIRE FORMAT. Append, never insert, and bump KDL_VER if you must
; move one.
; -----------------------------------------------------------------------------
%macro KDL_FIELDS 0
    KDL_F dos_name,    16                       ; the program's 8.3 name
    KDL_F dos_args,    DOS_ARGSZ                ; ...and its command tail
    KDL_F dos_ebuf,    DOS_ENVN * DOS_ENVBUF    ; the user's environment rows
    KDL_F dos_blaster, 32                       ; and the machine's own row
                                                ; (SPEC.md 96.17) - the sound
                                                ; driver is unloaded by the
                                                ; time this is read, so this
                                                ; string is the ONLY record
                                                ; left of where the card was
    KDL_F dos_dir,     2                        ; the folder it was launched
    KDL_F dos_vol,     1                        ; from, and that folder's drive
    KDL_F dos_memkb,   2                        ; the arena cap, 0 = all of it
%endmacro

; -----------------------------------------------------------------------------
; **A CONSUMER DEFINES `KDL_F` AND INVOKES `KDL_FIELDS`.** Two of them do, and
; neither is a macro that writes a macro: nasm cannot nest those without
; escaping every parameter, and the five lines each side writes read better
; than the escape would.
;
;   ; the table, for the walk
;   %macro KDL_F 2
;       dw (%1 - DOS_CBASE), %2
;   %endmacro
;   kd_lbtab:
;       KDL_FIELDS
;       dw 0, 0
;   %unmacro KDL_F 2
;
;   ; ...and this side's own idea of the payload's length
;   %assign KDL_ACC 0
;   %macro KDL_F 2
;       %assign KDL_ACC KDL_ACC + %2
;   %endmacro
;   KDL_FIELDS
;   %unmacro KDL_F 2
;   KDL_MINE equ KDL_ACC
;
; `KDL_ACC` is `%assign` and not `%define` because the sum is arithmetic: a
; `%define` of itself plus a term is a recursive expansion, not an addition.
; -----------------------------------------------------------------------------
