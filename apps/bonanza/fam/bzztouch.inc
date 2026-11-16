; =============================================================================
; apps/bonanza/fam/bzztouch.inc - the TOUCH TEST (SPEC.md 128.12.6.1 - 128.12.6.2),
; ONE source: the tube's drain and the windmill's doorway ask it.  Included by
; bzphys.inc with BZ_TUBE_RESIDENT, by the TUBE family's part and by the ROTOR
; family's (SPEC.md 128.25.20).  bz_h4 is the includer's (the package's, or a
; part's copy, fam/bzfcopy.inc).
; =============================================================================
%ifnmacro BZ_Q64
%macro BZ_Q64 0                 ; (bzphys.inc's: DX:AX -> AX = floor(DX:AX / 64))
    mov dh, dl
    mov dl, ah
    shl dx, 1
    shl dx, 1
    rol al, 1
    rol al, 1
    and ax, 3
    or ax, dx
%endmacro
%endif

; bz_ztouch - CF = 1 when the ball's z is at most the centre cell's floor at
; its point plus BZ_CLIMB (a drain's capture, a doorway's touch: 128.12.6.1,
; 128.12.6.2), exactly: z <= 64 (h4 + 16) <=> floor((z - 1) / 64) < h4 + 16.
; bz_ztouchp: at the point DL = u, DH = v.  Clobbers AX, BX, CX, DX, SI.
bz_ztouch:
    mov dl, [bz_gx + 1]
    and dl, 15
    mov dh, [bz_gy + 1]
    and dh, 15
bz_ztouchp:
    mov si, bz_nbr + BZN_C
    call bz_h4
    add ax, BZ_CLIMB * 4
    xchg ax, bx
    mov ax, [bz_gz]
    mov dx, [bz_gz + 2]
    sub ax, 1
    sbb dx, 0
    BZ_Q64
    cmp ax, bx
    jl .y
    clc
    ret
.y:
    stc
    ret

