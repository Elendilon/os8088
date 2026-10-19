; =============================================================================
; os8088 - apps/realboy/rwfsx.inc
;
; RealBoy's FULL SCREEN (docs/REALBOY-SPEC.md section 15): the machine run on
; the UI task inside an OSAPI_FSX_RUN bracket, with the screen its own.
; Included by realboy.asm.
;
; The worker is FROZEN in there, so it must not be frozen INSIDE the machine
; - in the core, or in rb_render, whose working memory is the view's. It
; holds [rw_incore] from its loop's top to the end of its render and backs
; off at the top when [rw_fsq] is set; rw_fsenter sets [rw_fsq] and yields
; until [rw_incore] is clear. The store order is what makes it exact: the
; worker raises its byte BEFORE it reads ours, so once we have seen it clear
; with ours set, every later entry of its sees ours and backs off.
;
; THE SCREEN is mode 0Dh, 320x200 planar, the picture at 1x in the middle.
; rb_render's two shade planes go to VGA planes 0 and 1 as they are, through
; a RAM shadow of the last frame: a word is written only when it changed.
; Plane 2 is set everywhere but the picture, so the border is DAC entry 4 and
; the speed line, planes 0 and 1 over it, entry 7. The DAC is ours in here;
; the restore's BIOS mode set puts the desktop's back (SPEC.md 53.6).
;
; THE CLOCK is FSXF_RATE at the Game Boy's own frame rate: a hook on every
; period counts frames owed and nothing else, and the loop runs the machine
; to the count. It draws a frame when it has caught up, or when RW_FSSKIP
; frames have gone by undrawn. kern_small refuses FSXF_RATE (and has no
; VGA): the bracket is retried without it and paces by the tick.
; =============================================================================

RW_FSDIV        equ 19977           ; 1,193,182 / 59.7275: a period a frame
RW_FSSKIP       equ 4               ; frames run undrawn at most, behind
RW_FSX          equ 10              ; the picture's byte column (x = 80)
RW_FSY          equ 28              ; ...and its first row
RW_FSTXT        equ 182             ; the speed line's row
RW_FSBUD        equ 6000            ; M-cycles a core run in here: no mouse
RW_FSBUD86      equ 1400            ;   to serve, so only IRQ0 bounds it - one
                                    ;   rate period is 16.7 ms, and a 286 at
                                    ;   ~35 clocks a busy M-cycle spends ~7 ms
                                    ;   on 6,000 of them all busy (an 8088 at
                                    ;   ~48, ~14 ms on 1,400)

; rw_mgrey - Machine > Full Screen, greyed with the reason when it cannot be
; had: no game, or a display with no mode 0Dh. Any context.
rw_mgrey:
    push ax
    push bx
    push dx
    push si
    mov si, rw_it_fs0
    cmp byte [rw_state], 1
    jne .set
    mov bx, [rw_win]
    call OSAPI_FSX_CAPS             ; AX = the modes this display can set
    mov si, rw_it_fsv
    test ax, 1 << FSXM_VGA0D
    jz .set
    mov si, rw_it_fs
.set:
    mov [rw_i_mach + 4], si
    mov si, rw_it_jit0              ; Recompiler: what it is now
    cmp word [rw_jitseg], 0
    je .j
    mov si, rw_it_joff
    cmp byte [rw_jitwant], 0
    je .j
    mov si, rw_it_jon
.j:
    mov [rw_i_mach + 6], si
    pop si
    pop dx
    pop bx
    pop ax
    ret

; rw_fsenter - Machine > Full Screen, on the UI task with the lock held
rw_fsenter:
    cmp byte [rw_state], 1
    jne .r
    mov bx, [rw_win]
    call OSAPI_FSX_CAPS
    test ax, 1 << FSXM_VGA0D
    jz .r                           ; greyed; a shortcut gets nothing either
    call OSAPI_FONT_GLYPHS          ; DX:SI, AL first, AH last: copied now,
    call rw_fscopy                  ;   before the mode leaves the desktop's
    mov byte [rw_fsq], 1
.wait:
    cmp byte [rw_incore], 0         ; the worker out of the machine first
    je .go
    call OSAPI_TASK_YIELD
    jmp short .wait
.go:
    mov byte [rw_pfmt], 0           ; rw_pbuf is our shadow in there: the
                                    ;   restore's repaint paints white
    mov byte [rw_fsrate], 1
    mov ax, rw_fsmain
    mov bx, [rw_win]
    mov cx, FSXF_RATE
    mov dx, RW_FSDIV
    mov di, rw_fshook
    call OSAPI_FSX_RUN
    jnc .out
    mov byte [rw_fsrate], 0         ; kern_small: no rate, the tick paces
    mov ax, rw_fsmain
    mov bx, [rw_win]
    xor cx, cx
    call OSAPI_FSX_RUN
.out:
    call OSAPI_GET_TICKS            ; the window takes up from now
    mov [rw_last], ax
    mov word [rw_owed], 0
    mov byte [rw_fsq], 0
.r:
    ret

; rw_fscopy - the glyphs for 32-127 into rw_font, blanks where the table
; stops. DX:SI = the table, AL = its first code, AH = its last.
rw_fscopy:
    push ds
    push ds
    pop es
    mov di, rw_font
    mov bl, 32
    mov ds, dx
.c:
    cmp bl, al
    jb .blank
    cmp bl, ah
    ja .blank
    push si
    mov cl, bl
    sub cl, al
    xor ch, ch
    shl cx, 1
    shl cx, 1
    shl cx, 1
    add si, cx                      ; SI = this code's 8 rows
    mov cx, 8
    rep movsb
    pop si
    jmp short .next
.blank:
    push ax
    xor al, al
    mov cx, 8
    rep stosb
    pop ax
.next:
    inc bl
    cmp bl, 128
    jb .c
    pop ds
    ret

; rw_fshook - every rate period: a frame owed. AX = periods since the last.
rw_fshook:
    add [rw_fowed], ax
    ret

; rw_fsmain - the bracket. DS = CS = ours, ES = KERNEL_SEG, SI = the window.
rw_fsmain:
    push ds
    pop es
    mov al, FSXM_VGA0D
    mov di, rw_fsi
    call OSAPI_FSX_MODE
    jc .r
    call rw_fsdac
    call rw_fsframe
    push ds
    pop es
    mov di, rw_pbuf                 ; the shadow: the mode set cleared the
    mov cx, 5760 / 2                ;   screen to zero, and so is it
    xor ax, ax
    rep stosw
    mov byte [rw_infsx], 1
    push word [rw_budget]           ; the window's budget, back at the end
    mov ax, RW_FSBUD
    cmp word [rw_budget], RW_BUDGET86
    jne .bud
    mov ax, RW_FSBUD86
.bud:
    mov [rw_budget], ax
    mov byte [rw_ovlnew], 1
    mov word [rw_fowed], 0
    mov byte [rw_fsrun], 0
    call OSAPI_GET_TICKS
    mov [rw_last], ax
.loop:
    call rw_fsdrain                 ; ZF = 0: Esc
    jnz .out
    call rw_fsowed                  ; AX = frames owed now (taken)
    or ax, ax
    jnz .run
    mov al, FSXW_FRAME
    cmp byte [rw_fsrate], 0
    jne .w
    mov al, FSXW_TICK
.w:
    call OSAPI_FSX_WAIT
    jmp short .loop
.run:
    cmp ax, 8                       ; behind by more than eight: run on
    jbe .n                          ;   from here rather than race
    mov ax, 8
.n:
    mov [rw_fsleft], ax
.f:
    call rw_keys
    call rw_frame
    jc .out                         ; it stopped
    call rw_sound
    inc word [rw_nrun]
    call rw_stat
    inc byte [rw_fsrun]
    dec word [rw_fsleft]
    jz .draw                        ; caught up: draw this one
    cmp byte [rw_fsrun], RW_FSSKIP
    jb .f
.draw:
    mov byte [rw_fsrun], 0
    inc word [rw_ndrawn]
    call rw_fsdraw
    cmp word [rw_fsleft], 0
    jne .f
    jmp short .loop
.out:
    pop word [rw_budget]
    mov byte [rw_infsx], 0
.r:
    ret

; rw_fsowed - AX = the frames owed since the last call, and none left owed
rw_fsowed:
    cmp byte [rw_fsrate], 0
    je .tick
    pushf
    cli
    mov ax, [rw_fowed]
    mov word [rw_fowed], 0
    popf
    ret
.tick:
    push bx
    push dx
    call OSAPI_GET_TICKS
    mov bx, ax
    xchg bx, [rw_last]
    sub ax, bx
    cmp ax, 10                      ; away longer than that: start over
    jbe .t
    mov ax, 10
.t:
    mov dx, RW_PERTICK
    mul dx
    add ax, [rw_owed]
    mov dl, al                      ; the fraction stays owed
    xor dh, dh
    mov [rw_owed], dx
    mov al, ah
    xor ah, ah
    pop dx
    pop bx
    ret

; rw_fsdrain - the BIOS key buffer emptied (a full one beeps); ZF = 0 when
; Esc is held
rw_fsdrain:
.k:
    mov ah, 1
    int 16h
    jz .e
    xor ah, ah
    int 16h
    jmp short .k
.e:
    mov al, 1                       ; Esc
    call OSAPI_KEY_DOWN             ; CF = 1: held
    sbb al, al                      ; ZF = 0 when it was
    ret

; rw_fsdac - shades 0-3 as greys at DAC 0-3, the border at 4, the text at 7
rw_fsdac:
    mov dx, 3C8h
    xor al, al
    out dx, al
    inc dx
    mov si, rw_fsgreys
    mov cx, 8 * 3
.d:
    lodsb
    out dx, al
    loop .d
    ret

; rw_fsframe - plane 2 set everywhere but the picture: the border
rw_fsframe:
    mov es, [rw_fsi + FSI_SEG]
    mov dx, 3C4h
    mov ax, 0402h                   ; map mask: plane 2
    out dx, ax
    xor di, di
    mov cx, 40 * 200 / 2
    mov ax, 0FFFFh
    rep stosw
    mov di, RW_FSY * 40 + RW_FSX
    mov bx, 144
    xor ax, ax
.r:
    mov cx, 10
    rep stosw
    add di, 40 - 20
    dec bx
    jnz .r
    ret

; rw_fsdraw - the frame onto VRAM through the shadow, and the speed line
; when F1 has it up and it changed
rw_fsdraw:
    push ds
    pop es
    mov di, rw_fbuf
    call rb_render
    mov es, [rw_fsi + FSI_SEG]
    mov dx, 3C4h
    mov ax, 0102h                   ; plane 0: the shade's bit 0
    out dx, ax
    mov si, rw_fbuf
    call rw_fsplane
    mov ax, 0202h                   ; plane 1: bit 1
    out dx, ax
    mov si, rw_fbuf + 20
    call rw_fsplane
    cmp byte [rw_ovl], 0
    je .r
    cmp byte [rw_ovlnew], 0
    je .r
    mov byte [rw_ovlnew], 0
    call rw_fstext
.r:
    ret

; rw_fsplane - one plane of rw_fbuf (SI = its line 0) against the shadow
; beside it in rw_pbuf, the changed words to VRAM. ES = VRAM.
rw_fsplane:
    push dx
    mov bx, si
    add bx, rw_pbuf - rw_fbuf       ; BX = the shadow of the same bytes
    mov di, RW_FSY * 40 + RW_FSX
    mov dx, 144
.l:
    mov cx, 10
.w:
    lodsw
    cmp ax, [bx]
    je .s
    mov [bx], ax
    mov [es:di], ax
.s:
    inc bx
    inc bx
    inc di
    inc di
    loop .w
    add si, 20
    add bx, 20
    add di, 40 - 20
    dec dx
    jnz .l
    pop dx
    ret

; rw_fstext - rw_ovltxt on the border under the picture, 16 cells wide
rw_fstext:
    mov dx, 3C4h
    mov ax, 0302h                   ; planes 0 and 1: the glyph's set bits
    out dx, ax                      ;   read 7, its clear ones 4
    mov si, rw_ovltxt
    mov di, RW_FSTXT * 40 + RW_FSX
    mov cx, 20
.c:
    lodsb
    or al, al
    jnz .g
    dec si                          ; past the end: blanks
    mov al, ' '
.g:
    push si
    push cx
    sub al, 32
    xor ah, ah
    shl ax, 1
    shl ax, 1
    shl ax, 1
    mov si, rw_font
    add si, ax
    mov cx, 8
    push di
.row:
    movsb
    add di, 40 - 1
    loop .row
    pop di
    inc di
    pop cx
    pop si
    loop .c
    ret

; DAC 0-7, six bits a gun: the shades (0 lightest), the border, -, -, text
rw_fsgreys:
    db 63, 63, 63,  42, 42, 42,  21, 21, 21,  0, 0, 0
    db 4, 4, 8,  0, 0, 0,  0, 0, 0,  48, 48, 52
