; =============================================================================
; apps/bonanza/bzvga.inc - the VGA part's ABI (SPEC.md 128.41.6), included by
; the package (bonanza.asm) and by the part (bzvga.asm), so the two cannot hold
; different opinions about where a vector is.
;
; BZVGA.BIN is a flat binary at org 0, a lazy OP_SEG row of BONANZA.O88 (the
; last, BZ_P_VGA), LINKED against the package's bss as the shell part is
; (bzlink.inc). Its head:
;   +0  dw 'BZ', 'VG'          the signature
;   +4  dw BZL_IMAGE           the package's image size it was linked against
;   +6  dw BZL_BSS             ...and its bss: both checked against DS:8, DS:10
;   +8  the vectors, BZV_VECB bytes each (a `jmp near`), entered by `call far`
;       with DS = ES = the package, answering by `retf`
; =============================================================================
%ifndef BZVGA_INC
%define BZVGA_INC
BZV_SIG0    equ 'BZ'
BZV_SIG1    equ 'VG'
BZV_IMAGE   equ 4
BZV_BSSW    equ 6
BZV_VEC     equ 8               ; vector 0's offset
BZV_VECB    equ 3               ; a vector's size
; the vectors.  Each keeps DS, SS and SP and names what else it clobbers
BZV_CONV    equ 0               ; convert the course's art in place and the three
                                ; balls into [bz_vbseg] (128.41.5); preserves nothing
BZV_INIT    equ 1               ; bz_vinit's VGA half (128.41.3); preserves nothing
BZV_FLIP    equ 2               ; AX = a start address (bytes) to CR0Ch/0Dh; all kept
BZV_PAN     equ 3               ; AL = the pel panning to AC 13h; all kept
BZV_ROW     equ 4               ; bz_row's: world line AX, columns BX .. BX+CX-1; all kept
BZV_COL     equ 5               ; [bz_ccol], every line of the new window; preserves nothing
BZV_BOXW    equ 6               ; box SI to the card (bz_boxw's); all kept
BZV_BLIT    equ 7               ; bz_blit's, its registers (128.41.5); keeps SI, DS, ES
BZV_WPRECT  equ 8               ; bz_wprect's, its registers; clobbers AX - DI, BP
BZV_CARD    equ 9               ; bzcard.inc's glyph cell (128.41.4); see bz_card's VGA arm
BZV_NVEC    equ 10
; a ball part's copy: its 16-byte head, then every 5-byte row as 6 (SPEC.md
; 128.41.5); copy 0 then copy 1 (four pixels further right), each material's
; pair from a paragraph, in bz_bsegs' order (rubber, steel, glass)
%define BZV_COPY(n) (((n) - 16) / 5 * 6 + 16)
BZV_CR      equ BZV_COPY(BZ_BAL_SIZER)
BZV_CS      equ BZV_COPY(BZ_BAL_SIZE)
BZV_CG      equ BZV_COPY(BZ_BAL_SIZEG)
BZV_PSIZE   equ 2 * (BZV_CR + BZV_CS + BZV_CG) ; [bz_vbseg]'s bytes
%if (BZV_CR | BZV_CS | BZV_CG) & 15 || BZV_PSIZE > 65536 - 16 || (BZ_BAL_SIZER - 16) % 5 || (BZ_BAL_SIZE - 16) % 5 || (BZ_BAL_SIZEG - 16) % 5
 %error "the balls' copies: whole 5-byte rows, a paragraph each, one segment (128.41.5)"
%endif

; BZ_VCALL n - vector n of the held part (bz_vprep set its segment)
%macro BZ_VCALL 1
    mov word [bz_vfp], BZV_VEC + BZV_VECB * (%1)
    call far [bz_vfp]
%endmacro
%endif
