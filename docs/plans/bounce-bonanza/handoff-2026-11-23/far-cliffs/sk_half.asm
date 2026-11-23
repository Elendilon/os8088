; bz_arange's extra-slot right half (.right's clip, then .rx) and bz_ahalf's column, copied to price them
cpu 8086
bits 16
org 0
bz_axw equ 1000h
bz_axw7 equ 1002h
bz_axb equ 1004h
bz_aE equ 1100h
setup:
    mov ax, [si]
    cmp ax, [1010h]
    jle e9
    mov dx, [si + 2]
    test byte [si + 7], 1
    jz r
r:
    mov cx, dx
    cmp cx, [bz_axw]
    jge r0
    mov cx, [bz_axw]
r0:
    mov bp, dx
    add bp, 15
    cmp bp, [bz_axw7]
    jle r1
    mov bp, [bz_axw7]
r1:
    sub bp, cx
    jl e9
    push dx
    mov di, cx
    sub di, [bz_axb]
    shl di, 1
    add di, bz_aE
    mov ax, cx
    sub ax, dx
    mov cx, bp
    inc cx
    test byte [si + 7], 8
    jnz rx                      ; TAKEN
rx:
    shl ax, 1
    inc ax
    mov bl, [si + 6]
    imul bl
    mov dl, bl
    xchg ax, dx
    cbw
    shl ax, 1
    xchg ax, dx
    mov bx, [si + 4]
    test byte [si + 7], 4
    jnz e9
    add ax, 4
    call half                   ; (call + ret + the shifts)
    pop dx
e9:
    ret
half:
    push cx
    mov cl, 5
    shl ax, cl
    shl dx, cl
    pop cx
    mov bp, ax
col:
    mov ax, bp
    mov al, ah
    cbw
    add ax, bx
    cmp ax, [di]
    jge k
    mov [di], ax
k:
    add bp, dx
    inc di
    inc di
    loop col                    ; TAKEN
colend:
    ret
