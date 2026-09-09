; =============================================================================
; os8088 - apps/skies/csload.asm
;
; CLEAR SKIES' LOADER - the IMAGE of SKIES.O88, and the whole of what the
; kernel launches (SPEC.md 88.10.4, 20.12.10).
;
; It reads the two parts, tells the program where the art went, and asks the
; kernel to treat the program as the program. Then its region is freed and it
; is gone: what runs is apps/skies/skies.asm, at PART 0, in the parts carve,
; with an instance and a window and a name of its own and no idea any of this
; happened.
;
; WHY IT EXISTS IS A NUMBER. `image + bss` is bounded by APP_MAX_SIZE - 61,440
; bytes, and it bounds ONE segment because a package addresses itself with
; 16-bit offsets. Clear Skies was at 61,100 of it, with the DIAGNOSTIC and
; PROBE builds 436 and 585 bytes OVER, so `make skiesdiag` did not assemble
; and two registered rows were skipping. §88.10.3 took the title art out of
; the image and bought 3,268; this takes the READER out too, and buys the
; disk back (88.10.3.1) - a parted image cannot be compressed, so with the
; body inside it SKIES.O88 went 37,534 -> 49,031 bytes on a 360KB apps disk
; with 8 clusters spare. As a PART the body is OP_COMP like everything else.
;
; IT MUST NOT CREATE A WINDOW (SPEC.md 20.12.10.6): its region is about to be
; freed, so a window whose W_SEG named it would far-call a dead claim on its
; first repaint. The program's window is the one the user sees.
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'SKIES', csl_entry, 1 | OS88_F_PARTS, OS88_STACK_DEFAULT

%include "csicon.inc"           ; ...and the SAME icon the program carries: the
                                ; Disk window draws this one before the launch
                                ; and the dock draws the program's after it

%include "csart.inc"            ; ...and the art's own numbers - the offsets
                                ; the PROGRAM reads, and the two lengths this
                                ; file needs to expand the stream. One
                                ; generated include, read by both halves
%include "os88parts.inc"

CS_PART_BODY equ 0              ; the program - a whole .o88 image (20.12.10)
CS_PART_ART  equ 1              ; the title bands (88.10.3)
CS_NPARTS    equ 2

; --- the handoff, at the head of the PROGRAM's bss (SPEC.md 20.12.10.2) ------
; ONE PACKAGE, TWO SOURCES: apps/skies/skies.asm declares these and this file
; is the other end of them. The kernel is not involved and has no opinion; it
; does not zero a part, which is the whole of what makes this work.
CSH_MAGIC  equ 0                ; word: 'CS' - the loader ran
CSH_ART    equ 2                ; word: where it put the title bands
CSH_SIZE   equ 4

LD_H_IMG   equ 8                ; ...and the two header fields it reads them
LD_H_BSS   equ 10               ; at, which are the FORMAT's and not ours

; -----------------------------------------------------------------------------
; csl_art - fetch the title bands and expand them (SPEC.md 88.10.4)
; out: AX = the segment holding CS_ART_SIZE bytes of bands, or 0
; clobbers: BX, CX, DX, SI, DI, ES, flags
;
; THE STREAM IS A LAZY PART and the bands are a claim, so this holds two of
; MEM_OWNER_MAX's eight for as long as it takes to decode - and gives one
; straight back. op_drop is what makes lazy a saving rather than a
; postponement (SPEC.md 20.12.4), and it matters here for a second reason:
; this image is about to stop existing, so a slot it did not release would be
; released by the kernel at teardown and held for the whole session.
;
; EVERY REFUSAL IS SURVIVABLE and answers 0, which is the plainer title page
; the program has always been able to draw - the title lettered in the 8x8
; face and no aeroplane (SPEC.md 88.10.2). A machine too full for 11KB still
; flies, and op_fetch has already said why in a toast.
; -----------------------------------------------------------------------------
csl_art:
    mov al, CS_PART_ART
    call op_fetch                   ; claims and reads the stream (20.12.4)
    jc .none
    mov al, CS_PART_ART
    call op_seg                     ; AX = where it landed
    or ax, ax
    jz .none
    mov [csl_zseg], ax
    mov ax, CS_ART_KB
    call OSAPI_MEM_CLAIM            ; DX = the bands' own claim
    jc .drop
    mov [csl_aseg], dx
    push ds
    mov es, dx
    mov ds, [csl_zseg]              ; DS:SI the stream, T word first...
    xor si, si
    mov cx, CS_ART_ZLEN
    xor di, di                      ; ...ES:0 where it goes, and DI = 0 is the
    xor bx, bx                      ; contract (SPEC.md 20.13.3). BX:DX is the
    mov dx, CS_ART_SIZE             ; EXACT output, 32 bits, and ours is one
    mov al, OSAPI_LZ_LZ4            ; word - so BX is zero and DX the size
    call OSAPI_DECOMP
    pop ds
    jc .free
    mov al, CS_PART_ART             ; the STREAM's claim goes back: the bands
    call op_drop                    ; are what we hand over, not the bytes they
    mov ax, [csl_aseg]              ; came out of
    ret
.free:
    mov dx, [csl_aseg]              ; a decode this build cannot do - a kernel
    call OSAPI_MEM_FREE             ; carrying only LZB would (SPEC.md 20.14.5)
.drop:
    mov al, CS_PART_ART
    call op_drop
.none:
    xor ax, ax
    ret

; -----------------------------------------------------------------------------
; csl_entry - the loader's entry proc (SPEC.md 20.2)
; in:  DS = CS = our segment, ES = KERNEL_SEG, SI = the name of the file we
;      came out of, gfx lock NOT held
; out: BX = 0, CF clear - and the kernel re-homes instead of publishing us
; -----------------------------------------------------------------------------
csl_entry:
    call op_load                    ; FIRST, for SPEC.md 20.2's reason: SI is
    jc .no                          ; an offset into the KERNEL's segment at a
                                    ; buffer the loader reuses on the next
                                    ; launch. A REFUSAL IS FATAL HERE and it
                                    ; was not in 88.10.3: a body that did not
                                    ; arrive is not a plainer title page

    mov al, CS_PART_BODY
    call op_seg
    or ax, ax
    jz .no
    mov dx, ax                      ; DX = where the program is

    push dx                         ; ...and the ART
    call csl_art                    ; AX = the expanded bands, or 0
    pop dx
    push ax

    ; --- the handoff, into the head of the program's bss --------------------
    mov es, dx
    mov di, [es:LD_H_IMG]           ; the bss begins here, which the part's own
    mov word [es:di+CSH_MAGIC], 'CS'
    pop ax
    mov [es:di+CSH_ART], ax         ; header says

    ; --- and the hand-over ---------------------------------------------------
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
    OS88_PARTS_BEGIN CS_NPARTS
      OS88_PART OP_SEG,   OP_COMP   ; 0 THE PROGRAM: a whole .o88 image, its
                                    ;   bss shipped inside it because the
                                    ;   kernel does not zero a part (20.12.10).
                                    ;   OP_COMP is what buys the disk back -
                                    ;   13,777 of those bytes are the bss, and
                                    ;   a run of zeros is what LZ4 is best at
      OS88_PART OP_ASSET, OP_LAZY   ; 1 the title bands as an LZ4 STREAM, and
                                    ;   two constraints put it in that shape.
                                    ;   LAZY because THE RUN IS BOUNDED AT 128
                                    ;   SECTORS (SPEC.md 20.12.7) - one
                                    ;   segment, op_read's own arithmetic - and
                                    ;   the program alone unpacks to 111 of
                                    ;   them, so eager bands would make 131 and
                                    ;   op_size would refuse the package.
                                    ;   NOT OP_COMP because a lazy row cannot
                                    ;   be: the two want the same zkb word, and
                                    ;   os88parts.inc refuses the pair. So
                                    ;   tools/csart.py packs the stream and
                                    ;   csl_art below expands it, which is what
                                    ;   the image did with the same bytes
                                    ;   before 88.10.3 moved them out
    OS88_PARTS_END

    OS88_BSS OP_BSS + CSL_BSS
    OS88_IMAGE_END

csl_zseg equ os88_image_end + OP_BSS + 0   ; the stream's claim, while it lasts
csl_aseg equ os88_image_end + OP_BSS + 2   ; ...and the bands', which is what
CSL_BSS  equ 4                             ; the program is handed
