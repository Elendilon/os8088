; SPEC.md 137.29.12 research SKETCH (not built): A, the far list, read at a NEW V into the extra slots
; (DS = the world part, ES = ours; BX = BZG1).  Each entry (i << 4 | j) is a WHOLE, readable, non-float cell
; the tool picked, so no kind/OBS/float test is made.  Two extra slots (right then left), as bz_axcell's.
cpu 8086
bits 16
org 0
BZG_ROWTAB equ 14
BZG_AMIN equ 8
BZG_FARL equ 30
bz_avp equ 1000h
bz_goff equ 1002h
bz_ar equ 1004h
bz_aa equ 1006h
bz_ayb0 equ 1008h
bz_aan0 equ 100ah
bz_axe equ 100ch
bz_akq equ 100eh
bz_amaxnc equ 1010h
bz_aminc equ 1012h
bz_fn equ 1014h

; ---- HEAD: once a new V (priced apart: H) ----
head:
    mov si, [es:bz_avp]
    mov al, [si + 1]            ; V's byte +1: 0 none, else 1 + the list's offset
    or al, al
    jnz h0
    jmp done
h0:
    xor ah, ah
    add ax, [bx + BZG_FARL]
    mov si, ax
    lodsb
    mov [es:bz_fn], al
    mov di, [es:bz_axe]
; ---- ENTRY: each far cell (priced apart: E) ----
entry:
    lodsb                       ; i << 4 | j
    push si
    mov ah, al
    and ah, 0fh                 ; AH = j
    mov cl, 4
    shr al, cl                  ; AL = i
    mov dl, al
    sub dl, ah                  ; DL = i - j
    add al, ah                  ; AL = d
    xor ah, ah
    mov cx, ax                  ; CX = d
    add ax, [es:bz_ar]
    shl ax, 1
    mov si, ax
    add si, [bx + BZG_ROWTAB]
    mov si, [si]                ; the row's first cell
    mov ax, [es:bz_aa]
    sub ax, cx
    sub ax, [bx + BZG_AMIN]
    sar ax, 1                   ; k0(d)
    mov dh, 0
    push dx
    mov dl, [es:bz_fn + 1]      ; (i, kept)
    add ax, dx                  ; + i
    pop dx
    shl ax, 1
    shl ax, 1
    add si, ax                  ; SI = its four bytes
    mov al, dl
    cbw
    push cx
    mov cl, 4
    shl ax, cl
    pop cx
    add ax, [es:bz_aan0]        ; X = Xv + 16 (i - j)
    mov [es:di + 2], ax
    mov [es:di + 10], ax
    mov al, [si + 1]            ; the slopes
    mov ah, al                  ; H / 2 = z0 + 2 max(sx, 0) + 2 max(sy, 0)
    and al, 0fh
    cmp al, 8
    jb h1
    xor al, al
h1:
    push cx
    mov cl, 4
    shr ah, cl
    pop cx
    cmp ah, 8
    jb h2
    xor ah, ah
h2:
    add al, ah
    xor ah, ah
    shl ax, 1
    mov dx, ax
    mov al, [si]
    cbw
    add dx, ax                  ; DX = H / 2
    mov [es:di], dx
    mov [es:di + 8], dx
    shl ax, 1
    neg ax
    shl cx, 1
    shl cx, 1
    shl cx, 1
    add ax, cx
    add ax, [es:bz_ayb0]        ; Y = 8 (s + d) + Y0 - 2 z0
    mov [es:di + 4], ax
    mov [es:di + 12], ax
    mov al, [si + 1]            ; k: right 2 - sx, left 2 - sy; flags 0Ah, 09h
    mov ah, al
    mov cl, 4
    shl al, cl
    sar al, cl
    neg al
    add al, 2
    mov [es:di + 6], al
    mov byte [es:di + 7], 0ah
    sar ah, cl
    neg ah
    add ah, 2
    mov [es:di + 14], ah
    mov byte [es:di + 15], 09h
    cmp dx, [es:bz_akq]         ; the count set's interval
    jg gt
    cmp dx, [es:bz_amaxnc]
    jle nx
    mov [es:bz_amaxnc], dx
    jmp short nx
gt:
    cmp dx, [es:bz_aminc]
    jge nx
    mov [es:bz_aminc], dx
nx:
    add di, 16
    pop si
    dec byte [es:bz_fn]
    jz edone
    jmp entry
edone:
    mov [es:bz_axe], di
done:
    ret
