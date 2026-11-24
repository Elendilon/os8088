; =============================================================================
; bzsslog.inc - THE SEE-SAW LOG, a DIAGNOSTIC knob (make BZSSLOG=1, never
; shipped): every step whose ball is near MILL's plate (its cells, x 22 - 23,
; y 17 - 20) recorded after the families' STEP - the ball, the plate's
; state byte, the family slots and wakes and how many times each slot's STEP
; was dispatched - and SYSTEM\APPDATA\SSLOG.BIN written when the play ends
; (bz_play's .ret), when it holds any record.  A record is BZSS_RB bytes:
;   +0 n (low word)  +2 gx >> 8  +4 gy >> 8  +6 gz >> 8
;   +8 bz_air  +9 bz_mst  +10 bz_mat  +11 bz_fhk  +12 bz_fst[0]  +13 bz_fref
;   +14 STEP dispatches of slots 0 - 7 this step (8 bytes)
;   +22 bz_fsl slot 3, all 8 bytes (MILL's see-saw: rotor, tube, turntable,
;   SEESAW, archway, spring, life)   +30 bz_fwk slot 3 (a word)
; The file's head (BZSS_HD bytes): 'SSLG', the count, bz_crs, bz_mode,
; bz_fnf, the STEP hook list's bounds and its first 40 bytes.
; =============================================================================
%ifdef BZSSLOG
BZSS_N      equ 48
BZSS_RB     equ 32
BZSS_HD     equ 64
%macro BZ_SS_VARS 0              ; (expanded with the other VARs, bonanza.asm)
VAR bz_ssst,1                   ; od_write's state byte for SSLOG.BIN
VAR bz_ssc,8                    ; STEP dispatches of slots 0 - 7, this step
VAR bz_ssf,BZSS_HD + BZSS_N * BZSS_RB   ; the file: its head, then the records
%endmacro
bz_ssn equ bz_ssf + 4           ; (the count, in the head)

; a play's start (not a resumed one's): no records.  Preserves all.
bz_ssreset:
    mov word [bz_ssn], 0
    call bz_ssclr
    ret
bz_ssclr:
    mov word [bz_ssc], 0
    mov word [bz_ssc + 2], 0
    mov word [bz_ssc + 4], 0
    mov word [bz_ssc + 6], 0
    ret

; bz_step's end: the step recorded when the ball is near the plate (not on
; the pathway).  DS = ours.  Preserves all.
bz_ssrec:
    push ax
    push bx
    push cx
    push si
    push di
    push es
    cmp byte [bz_mode], 4
    je .x
    mov cl, 4
    mov ax, [bz_gx + 1]
    shr ax, cl
    cmp ax, 22
    jb .x
    cmp ax, 24
    jae .x
    mov ax, [bz_gy + 1]
    shr ax, cl
    cmp ax, 17
    jb .x
    cmp ax, 21
    jae .x
    mov di, [bz_ssn]
    cmp di, BZSS_N
    jae .x
    inc word [bz_ssn]
    mov cl, 5
    shl di, cl
    add di, bz_ssf + BZSS_HD
    push ds
    pop es
    cld
    mov ax, [bz_nstep]
    stosw
    mov ax, [bz_gx + 1]
    stosw
    mov ax, [bz_gy + 1]
    stosw
    mov ax, [bz_gz + 1]
    stosw
    mov al, [bz_air]
    stosb
    mov al, [bz_mst]
    stosb
    mov al, [bz_mat]
    stosb
    mov al, [bz_fhk]
    stosb
    mov al, [bz_fst]
    stosb
    mov al, [bz_fref]
    stosb
    mov si, bz_ssc
    mov cx, 4
    rep movsw
    mov si, bz_fsl + 3 * 8
    mov cx, 4
    rep movsw
    mov ax, [bz_fwk + 3 * 2]
    stosw
.x:
    call bz_ssclr
    pop es
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; bz_play's end: SSLOG.BIN written when it holds a record.  Preserves all.
bz_sswrite:
    cmp word [bz_ssn], 0
    je .r
    push ax
    push bx
    push cx
    push si
    push di
    push es
    push ds
    pop es
    cld
    mov di, bz_ssf
    mov ax, 'SS'
    stosw
    mov ax, 'LG'
    stosw
    add di, 2                   ; (the count, already there)
    mov al, [bz_crs]
    stosb
    mov al, [bz_mode]
    stosb
    mov al, [bz_fnf]
    stosb
    stosb                       ; (a pad byte)
    mov si, [bz_fhs + 2 * BZ_HK_STEP]
    mov ax, si
    stosw
    mov ax, [bz_fhs + 2 * BZ_HK_STEP + 2]
    stosw
    mov cx, 20                  ; the STEP list's first 40 bytes
    rep movsw
    mov cx, [bz_ssn]
    mov si, cx
    mov cl, 5
    shl si, cl
    lea cx, [si + BZSS_HD]
    mov si, bz_s_sslog
    mov bx, bz_ssf
    mov di, bz_ssst
    call od_write
    mov word [bz_ssn], 0        ; (written once: the next play starts empty)
    pop es
    pop di
    pop si
    pop cx
    pop bx
    pop ax
.r:
    ret
bz_s_sslog: db 'SSLOG.BIN', 0
%endif
