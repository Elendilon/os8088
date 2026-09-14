; =============================================================================
; os8088 - apps/dos/dosload.asm
;
; **THE DOS BOX'S LOADER - the IMAGE of DOS.O88, and the whole of what the
; kernel launches** (SPEC.md 96.44.4, 20.12.10). It reads the box out of part
; 0, tells it where `kern_dos` sits in the file, and asks the kernel to treat
; the box as the program. Then its region is freed and it is gone: what runs
; is `apps/dos/dos.asm`, at part 0, with a window and an instance and no idea
; any of this happened.
;
; **WHY IT EXISTS IS A NUMBER AND THE NUMBER IS A LAUNCH TIME.**
; `tools/os88pkg.py` refuses `--compress` beside parts - a part's offset is
; measured from the start of the file and the table that holds it is INSIDE
; the image, so compressing the image and laying out its parts are circular -
; and 96.40.3 measured what that cost when arm 3 first shipped: the image went
; RAW, `DOS.O88` 26,723 -> 57,272 bytes, and the same click took **+932 ms
; (35%)** because the launch read 21 more sectors. Twelve soak rows went red
; at once, none of them for a reason of its own.
;
; The four-piece shape (docs/plans/KERN-DOS-PLAN.md 4.1.3.1) is the way out and
; it is not a workaround: **only the IMAGE has to be raw, and the image can be
; a kilobyte.** Everything heavy becomes a part, and a part may be `OP_COMP`.
;
; **PART 1 IS LAZY, AND IT HAS TO BE** - it is not a style choice.  `op_load`
; claims and reads every EAGER part into one carve, and `op_size` refuses a
; carve of 64KB or more; part 0 unpacks to ~45KB and `kern_dos` to ~29KB, so
; an eager pair would be refused outright before a sector was read. It is also
; the wrong thing to want: nothing ever `op_fetch`es this row, because 4.1.1's
; whole argument is that the handoff walks the part's bytes into EXTENTS while
; the file layer is alive and a stub reads them with `int 13h` - by then the
; heap has been given away and there is nowhere to `op_load` to. So what the
; box needs off this row is three numbers, and the loader copies them into the
; box's own bss before it disappears.
;
; **`OP_LAZY` COSTS THE ROW ITS `zkb` WORD**, which on an `OP_COMP` row is the
; packed length (20.12.7) - so the stream is packed by `tools/os88lz.py --raw`
; in the Makefile instead and the FILE is the packed stream, which makes
; `OP_R_LEN` the packed length directly. The stub needs no other figure:
; `kds_expand` takes a byte count and runs to the end of the stream, and
; `KDS_ULEN` is carried and never read.
;
; IT MUST NOT CREATE A WINDOW (SPEC.md 20.12.10.6): its region is about to be
; freed, so a window whose `W_SEG` named it would far-call a dead claim on its
; first repaint. The box's window is the one the user sees.
; =============================================================================
cpu 8086
bits 16

%include "os88api.inc"

    OS88_HEADER 'DOS', dsl_entry, 3 | OS88_F_PARTS

%include "dosicon.inc"          ; ...and the SAME icon and association block
                                ; the box carries, because both are read out
                                ; of the IMAGE - the Disk window draws this
                                ; one before the launch, and `assoc.inc` reads
                                ; the three extensions off it to decide that a
                                ; .COM is ours at all

%include "os88parts.inc"

DOS_PART_BOX equ 0              ; the box - a whole .o88 image (20.12.10)
DOS_PART_KD  equ 1              ; ...and kern_dos, which nothing here reads

; --- the handoff, at the head of the BOX's bss (SPEC.md 20.12.10.2) ---------
; ONE PACKAGE, TWO SOURCES: `apps/dos/dos.asm` declares these and this file is
; the other end of them. The kernel is not involved and has no opinion; it
; does not zero a part, which is the whole of what makes this work.
;
; IT IS AN `OP_ROW` AND NOT A STRUCT OF OUR OWN, deliberately: the box already
; read `[dos_kdrow + OP_R_OFF]` out of the part table when the table was in
; its own image, so copying the row VERBATIM leaves all four of its read sites
; spelled exactly as they were and moves only the base.
DSLH_KDROW  equ 0               ; OP_ROW bytes, copied as they lie
DSLH_SIZE   equ OP_ROW

LD_H_IMG    equ 8               ; ...and the two header fields this file reads
LD_H_BSS    equ 10              ; them at, which are the FORMAT's and not ours

; -----------------------------------------------------------------------------
; dsl_entry - the package entry proc (SPEC.md 20.2)
; in:  SI = the launched file's name in KERNEL_SEG, ES = KERNEL_SEG
; out: CF=0 and BX = 0 (no window of ours); CF=1 = the launch is torn down
; -----------------------------------------------------------------------------
dsl_entry:
    call op_load                    ; sizes first and reads nothing if it will
    jc .no                          ; not fit (20.12); a toast has said why

    mov al, DOS_PART_BOX
    call op_seg
    or ax, ax
    jz .no
    mov dx, ax                      ; DX = where the box is

    ; --- the row, into the head of the box's bss ---------------------------
    mov es, dx
    mov di, [es:LD_H_IMG]           ; the bss begins here, which the part's own
    add di, DSLH_KDROW              ; header says
    mov al, DOS_PART_KD
    call op_row                     ; SI -> the table row, AX preserved
    mov cx, OP_ROW
.row:
    mov al, [si]
    mov [es:di], al
    inc si
    inc di
    dec cx
    jnz .row

    ; --- and the hand-over --------------------------------------------------
    ; AX is what the kernel bounds the part's image + bss against, so it is OUR
    ; word for what is actually there (SPEC.md 20.12.10.4). The part is padded
    ; to image + bss, so its own two header fields ARE that length - said by
    ; adding them rather than by a constant this file would have to keep in
    ; step with the other one.
    mov ax, [es:LD_H_IMG]
    add ax, [es:LD_H_BSS]
    call OSAPI_PKG_REHOME
    jc .no
    xor bx, bx                      ; NO WINDOW: ours is the region that is
    clc                             ; about to be freed (SPEC.md 20.12.10.6)
    ret
.no:
    stc                             ; ...and the kernel tears down what exists.
    ret                             ; op_load has already said why in a toast

; --- the table, and the standard's own code after it (SPEC.md 20.12.3) ------
    OS88_PARTS_BEGIN 2
      OS88_PART OP_SEG,   OP_COMP   ; 0 THE BOX: a whole .o88 image, its bss
                                    ;   shipped inside it because the kernel
                                    ;   does not zero a part (20.12.10).
                                    ;   OP_COMP is the whole point of this
                                    ;   file - 11,839 of those bytes are the
                                    ;   bss, and a run of zeros is what LZ4 is
                                    ;   best at
      OS88_PART OP_ASSET, OP_LAZY   ; 1 kern_dos, PACKED BY THE MAKEFILE. Lazy
                                    ;   because op_size would refuse the pair
                                    ;   eagerly (the header above), and never
                                    ;   fetched because the handoff reads it by
                                    ;   extent list with the heap already gone
    OS88_PARTS_END

    OS88_BSS OP_BSS
    OS88_IMAGE_END
