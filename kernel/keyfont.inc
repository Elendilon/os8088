; Optional CP850 face, SPEC.md 6.7 / 9.16.3. Included in KEYBOARD.DRV.
; Entry DS = kernel, ES = the module's writable data alias (also on mega).
; All state/data stays in this module. No memory claim or file read here.

section .modq
klf_enable:
    push ax
    push bx
    push cx
    push si
    push di
    call klf_lock
    cmp byte [es:klf_active], 0
    jne .done
    mov ax, [font_seg]
    mov [es:klf_saved_seg], ax
    mov si, [font_base]
    mov [es:klf_saved_base], si
    push ds                         ; the kernel's, needed below
    mov ds, ax
    mov di, klf_table
    mov cx, FONT_BYTES / 2
    cld
    rep movsw                       ; retain the selected ASCII face
    pop ds
    pushf
    cli
    mov ax, es
    mov [font_seg], ax
    mov word [font_base], klf_table
    mov word [font_last], (223 << 8) | 255
    mov byte [es:klf_active], 1       ; publish only a complete table
    popf
.done:
    call klf_unlock
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    clc
    ret

; No caller reads CF from klf_disable, klf_suspend or klf_rearm: klm_status
; ends every control call with its own, and kl_drop_x answers AX = 0.
klf_disable:
    push ax
    push bx
    call klf_lock
    mov al, [es:klf_active]
    or al, al
    jz .done
    cmp al, 2
    je .off                     ; suspended: the original face is in place
    pushf
    cli
    mov ax, [es:klf_saved_seg]
    mov [font_seg], ax
    mov ax, [es:klf_saved_base]
    mov [font_base], ax
    mov word [font_last], ((FONT_LAST-FONT_FIRST) << 8) | FONT_LAST
    popf
.off:                           ; (the active byte is read only under the
    mov byte [es:klf_active], 0 ; drawing lock this holds, never by an IRQ)
.done:
    call klf_unlock
    pop bx
    pop ax
    ret

; Private wake bracket: 2 means a live provider temporarily unbound. The
; existing byte retains this fact; layout/client pins belong to keyboard.inc.
klf_suspend:
    cmp byte [es:klf_active], 1
    jne .done
    call klf_disable
    mov byte [es:klf_active], 2
.done:
    ret
klf_rearm:
    cmp byte [es:klf_active], 2
    jne klf_suspend.done
    mov byte [es:klf_active], 0
    jmp klf_enable              ; sample the repaired original pointer afresh

; A worker can be paused between reading font_base and font_seg. Publishing
; the pair with IF=0 is not enough: serialize with the whole drawing burst.
; Calls from a window callback already own this non-reentrant mutex.
; BX = whether THIS helper acquired it; outer helpers save the caller's BX.
klf_lock:
    xor bx, bx
    cmp byte [gfx_lock_flag], 0
    je .take
    mov bl, [sch_cur]
    cmp bl, [gfx_lock_own]
    mov bl, 0                   ; (flags kept)
    je .owned
.take:
    call KERNEL_SEG:cw_gfx_lock
    inc bx                      ; BX = 1
.owned:
    ret
klf_unlock:
    or bl, bl
    jz .done
    call KERNEL_SEG:cw_gfx_unlock
.done:
    ret

; One writable table in the module image: ASCII is initialized on first
; use; the generated extended bytes already occupy their final positions.
; Keeping a second immutable 1KB copy would spend a second KB of active RAM.
klf_table:
    times FONT_BYTES db 0
    times 8 db 0                    ; DEL is never a printable glyph
%include "keyfont-data.inc"
%if klf_cp850 - klf_table != (128 - FONT_FIRST) * 8
  %error "CP850 rows must follow the ASCII face and DEL"
%endif

section .modqb
klf_active:     resb 1
klf_saved_seg:  resw 1
klf_saved_base: resw 1
section .text
