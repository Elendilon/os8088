; WireArena's angle lookup, shared by both halves as SOURCE (each carries
; its own copy of wa_sin, from build/watab.inc).

; wa_sincos - AX = an angle (any; taken mod 1024) -> AX = sin, DX = cos, Q14
wa_sincos:
    push bx
    and ax, 1023
    mov bx, ax
    shl bx, 1
    mov ax, [wa_sin+bx]
    add bx, 512
    and bx, 2047
    mov dx, [wa_sin+bx]
    pop bx
    ret

