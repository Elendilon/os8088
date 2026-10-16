; =============================================================================
; os8088 - apps/video/vidload.asm
;
; THE VIDEO PLAYER'S LOADER - the IMAGE of VIDEO.O88, and the whole of what
; the kernel launches (SPEC.md 98.3.23, 20.12.10). apps/word/wdload.asm one
; package along, and for the same reason.
;
; It reads the two parts and asks the kernel to treat part 0 as the program.
; Then its region is freed and it is gone: what runs is apps/video/video.asm,
; at part 0 of the parts carve, with an instance and a window and a name of
; its own and no idea any of this happened.
;
; WHY IT EXISTS IS A NUMBER. `image + bss` is bounded by APP_MAX_SIZE -
; 61,440 bytes, the REGION - and the player stood at 60,841 of it, with its
; VPDIAG arm already past it. The segment is 65,536, and the carve a parted
; package is read into may run to 65,024 (127 sectors, op_size's bound), so
; part 1 is the difference: code assembled at VP_P1ORG in video.asm's own
; segment, which op_load lays down exactly there because part 0 is exactly
; VP_P1ORG long. video.asm's comment at VP_P1ORG says what may live there.
;
; BOTH PARTS ARE EAGER, and that is a requirement and not a style: a player
; is launched off one floppy and pointed at a video on ANOTHER, and on a
; one-drive machine the disk it came from is gone by then. Everything is read
; here, at the launch, while VIDEO.O88's own disk is in the drive.
;
; THE DOCUMENT IS NOT OURS TO TOUCH. A .V88 double-clicked on the desktop
; launches this image with the name in OSAPI_ARG_FILE, which is
; READ-AND-CLEAR - so the loader never asks, and the player's own vp_entry
; finds it where the launch left it.
;
; IT MUST NOT CREATE A WINDOW (SPEC.md 20.12.10.6): its region is about to be
; freed, so a window whose W_SEG named it would far-call a dead claim on its
; first repaint. The player's window is the one the user sees.
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'Video Player', vdl_entry, 0x23 | OS88_F_PARTS
                                ; icon, the .V88 association and the
                                ; document glyph - this header is the one the
                                ; mount reads, so it carries all three, as the
                                ; player's does. The stack class is the
                                ; player's: the default

%include "video/vpicon.inc"     ; ...and the SAME face the player wears

%include "os88parts.inc"

VDL_PART_PROG equ 0             ; the player - video.asm's image + its bss
VDL_PART_TOP  equ 1             ; ...and the top of its segment (98.3.23)

LD_H_IMG   equ 8                ; the two header fields the kernel bounds the
LD_H_BSS   equ 10               ; hand-over by, which are the FORMAT's

; -----------------------------------------------------------------------------
; vdl_entry - the loader's entry proc (SPEC.md 20.2)
; in:  DS = CS = our segment, ES = KERNEL_SEG, SI = the name of the file we
;      came out of, gfx lock NOT held
; out: BX = 0, CF clear - and the kernel re-homes instead of publishing us
; -----------------------------------------------------------------------------
vdl_entry:
    call op_load                    ; FIRST, for SPEC.md 20.2's reason: SI is
    jc .no                          ; an offset into the KERNEL's segment at a
                                    ; buffer the loader reuses on the next
                                    ; launch
    mov al, VDL_PART_PROG
    call op_seg
    or ax, ax
    jz .no
    mov dx, ax                      ; DX = where the player is
    mov es, ax
    mov ax, [es:LD_H_IMG]           ; AX = image + bss, the player's word for
    add ax, [es:LD_H_BSS]           ; its region - and where it ASSEMBLED part 1

    ; --- part 1 must be where part 0's code will look for it ----------------
    ; op_load lays the run out at roundup512(len) a part, and part 0 is image
    ; + bss long, so this holds by construction. It is checked anyway because
    ; the failure is not a refusal but a jump into whatever the carve has at
    ; that offset - and it costs a few bytes of an image that is freed at once.
    push ax
    mov cl, 4
    shr ax, cl                      ; the region in paragraphs...
    add ax, dx                      ; ...past the player is where part 1 goes
    mov bx, ax
    mov al, VDL_PART_TOP
    call op_seg
    cmp ax, bx
    pop ax
    jne .no

    OS88_REHOME                     ; DX = the player; the KEEP form, so the
                                    ; carve is cut where PART 1 ends and not
                                    ; where the region does (SPEC.md
                                    ; 20.12.10.5)
    jc .no
    xor bx, bx                      ; NO WINDOW: ours is the region that is
    clc                             ; about to be freed (SPEC.md 20.12.10.6)
    ret
.no:
    stc                             ; ...and the kernel tears down what exists.
    ret                             ; op_load has already said why in a toast

; --- the table, and the standard's own code after it (SPEC.md 20.12.3) ------
    OS88_PARTS_BEGIN 2
      OS88_PART OP_SEG, OP_COMP     ; 0 THE PLAYER: video.asm's image, its bss
                                    ;   shipped inside it because the kernel
                                    ;   does not zero a part (20.12.10). The
                                    ;   bss is zeros and LZ4 is best at those
      OS88_PART OP_SEG, OP_COMP     ; 1 THE TOP OF ITS SEGMENT: `.modc`,
                                    ;   assembled at VP_P1ORG. Eager, so it is
                                    ;   in the carve and lands right above part
                                    ;   0 - that adjacency is the whole design
    OS88_PARTS_END

    OS88_BSS OP_BSS
    OS88_IMAGE_END
