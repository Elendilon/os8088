; =============================================================================
; apps/bonanza/bzshell.asm - BONANZA's SHELL PART (SPEC.md 128.19.2, wave 8a)
;
; The desktop code a play never needs - today the FACE (bzface.inc) - out of
; the resident image and into a lazy, compressed OP_SEG part of BONANZA.O88,
; fetched on the desktop and DROPPED before any course is fetched, so it never
; shares memory with a course. PiXEL's linked part (SPEC.md 106.20,
; apps/pixel/pxpart.inc), taken whole:
;   1. ITS OWN TABLES THROUGH CS: the face's strings and the course titles are
;      read `[cs:...]` (bz_lcat); nothing here is ever WRITTEN through CS, so on
;      kern_mega, where CS is the claim's code alias (op_cseg), it is plain.
;   2. THE PACKAGE THROUGH DS: every vector is entered with DS = ES = the
;      package, and its bss is named by build/bonanza-art/bzlink.inc, which
;      names NO code label - a `call` into the package cannot assemble.
;   3. IT NEVER CLAIMS: no OSAPI_MEM_*, no fetch, no task (SPEC.md 20.12.5).
; The three helpers the face calls are copied below rather than called back.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"         ; the course tables' macros (identical equates)
%include "bzlink.inc"           ; the package's constants and bss (pxlink)
%include "bzshell.inc"

    dw BZH_SIG0, BZH_SIG1
    dw BZL_IMAGE, BZL_BSS
    times BZH_VEC - ($ - $$) db 0   ; (a negative count fails: the head is BZH_VEC bytes)
    times ($ - $$) - BZH_VEC db 0
bzh_v0: jmp near bzh_face      ; BZH_FACE (each vector labelled: entered from
bzh_v1: jmp near bzh_redraw     ; BZH_REDRAW            outside, by far call)
bzh_v2: jmp near bzh_line       ; BZH_LINE
    times BZH_VEC + BZH_VECB * BZH_NVEC - ($ - $$) db 0 ; (each vector BZH_VECB bytes)
    times ($ - $$) - BZH_VEC - BZH_VECB * BZH_NVEC db 0

bzh_face:                       ; the PLAYER's face, or with the harness byte
    cmp byte [bz_dev], 0        ; set the instruments' (SPEC.md 128.26.6)
    jne .dev
    call bz_wface
    retf
.dev:
    call bz_face
    retf
bzh_redraw:                     ; (a line of the instruments' face: the player's
    cmp byte [bz_dev], 0        ; has none)
    je .out
    call bz_redraw
.out:
    retf
bzh_line:                       ; AH = the line
    cmp byte [bz_dev], 0
    je .out
    call bz_fclip
    jc .out
    mov al, ah
    call bz_fline
.out:
    retf

; --- the package's helpers the face reads, copied (SPEC.md 128.19.2) ---------
; CF = 1 while a tour's course is next or playing (bonanza.asm's bz_intour)
bz_intour:
    push ax
    mov al, [bz_tour]
    dec al
    cmp al, BZ_NTOUR
    pop ax
    ret

; ZF = 1 when [bz_rlog] holds a log (bonanza.asm's bz_rhave)
bz_rhave:
    cmp word [bz_rlog], 'BZ'
    jne .out
    cmp word [bz_rlog + 2], 'R1'
.out:
    ret

; AL = 1 CGA, 2 Hercules, 3 VGA, 0 none (bonanza.asm's bz_adapter, 128.45.2)
bz_adapter:
    push bx
    push dx
    mov bx, [bz_win]
    call OSAPI_FSX_CAPS
    jc .none
    cmp dl, VID_CGA
    jne .herc
    test ax, 1 << FSXM_CGA320
    jz .none
    mov al, 1
    jmp .out
.herc:
    cmp dl, VID_HERC
    jne .vga
    test ax, 1 << FSXM_HERC
    jz .none
    mov al, 2
    jmp .out
.vga:
    cmp dl, VID_VGA
    jne .none
    test ax, 1 << FSXM_VGA0D
    jz .none
    mov al, 3
    jmp .out
.none:
    xor al, al
.out:
    pop dx
    pop bx
    ret

%include "bzwin.inc"            ; the window's art (tools/bzwinart.py, SPEC.md 128.26.2)
%include "bzface.inc"
%include "bzwface.inc"
