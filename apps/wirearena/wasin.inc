; WireArena's angle lookup: the game's alone. The renderer part takes the
; camera's sin and cos in the frame block (wa_fsn, wa_fcs: wafb.inc), so the
; table is not in it.

; wa_sincos - AX = an angle (any; taken mod 1024) -> AX = sin, DX = cos, Q14.
; wa_sin is a QUARTER wave, sin(0..256): the other three are its mirror
; (256 - i in the odd quadrants) and its negative (the lower half). Every
; angle comes out exactly as the whole table's entry (arenagen checks the
; mirror; 1,536 bytes fewer). A few calls a tick, so the ~60 clk the
; mirror costs are nothing.
wa_sincos:
    push bx
    push cx
    and ax, 1023
    mov cx, ax
    call .s                     ; AX = sin
    xchg ax, cx                 ; CX = sin, AX = the angle
    add ax, 256                 ; cos(a) = sin(a + 256)
    and ax, 1023
    call .s
    mov dx, ax
    mov ax, cx
    pop cx
    pop bx
    ret
.s:                             ; AX = an angle 0..1023 -> AX = its sin
    mov bx, ax
    and bx, 255
    test ah, 1                  ; the second and fourth quadrants: 256 - i
    jz .e
    neg bx
    add bx, 256
.e:
    shl bx, 1
    mov bx, [wa_sin+bx]
    test ah, 2                  ; the lower half: negative
    jz .p
    neg bx
.p:
    mov ax, bx
    ret
