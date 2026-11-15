; =============================================================================
; apps/bonanza/bzshell.inc - the SHELL PART's ABI (SPEC.md 128.19.2), included
; by the package (bonanza.asm) and by the part (bzshell.asm), so the two cannot
; hold different opinions about where a vector is.
;
; The part is a flat binary at org 0, a lazy OP_SEG row of BONANZA.O88, LINKED
; against the package's bss (tools/pxlink.py --consts -> bzlink.inc). Its head:
;   +0  dw 'BZ', 'SH'          the signature
;   +4  dw BZL_IMAGE           the package's image size it was linked against
;   +6  dw BZL_BSS             ...and its bss: both checked against DS:8, DS:10
;   +8  the vectors, BZH_VECB bytes each (a `jmp near`), entered by `call far`
;       with DS = ES = the package, answering by `retf`
; =============================================================================
%ifndef BZSHELL_INC
%define BZSHELL_INC
BZH_SIG0    equ 'BZ'
BZH_SIG1    equ 'SH'
BZH_IMAGE   equ 4
BZH_BSSW    equ 6
BZH_VEC     equ 8               ; vector 0's offset
BZH_VECB    equ 3               ; a vector's size
BZH_FACE    equ 0               ; paint the face (bz_face)
BZH_REDRAW  equ 1               ; SI = a 0FFh-ended line list in the PACKAGE (bz_redraw)
BZH_LINE    equ 2               ; AH = one of MAIN's lines (bz_redraw1)
BZH_NVEC    equ 3
%endif
