; =============================================================================
; os8088 - apps/realboy/rwlog.inc
;
; RealBoy's LOG TO FILE (docs/REALBOY-SPEC.md section 14.1): Machine > Log
; keeps a record a second - the game's speed, the frames run and drawn, the
; lines composed and changed, the drawing's time and its longest draw, how
; far behind the machine got, and where it was - and writes them as text to
; SYSTEM\APPDATA\REALBOY.LOG on the program's own disk when the log is turned
; off or the window closes. It is for a machine with no debugger: the F1
; line says how a game runs this second, and this says how it ran for five
; minutes, which is what a field run needs to bring back. Included by
; realboy.asm.
;
; The worker and the bracket record (rw_stat, a second at a time); only the
; UI task writes (SPEC.md 20.6 rule 7), from the menu or the close.
; =============================================================================

RW_LOGN         equ 256             ; records kept, the latest: four minutes
RW_LOGSZ        equ 16
RW_LOGKB        equ 16              ; the text's claim at the write
; a record: the ticks since the log began (at its end), the ticks it spans,
; frames run, frames drawn, lines composed, lines changed, the drawing's
; milliseconds, the longest draw (ms, at most 255), flags: bits 0-5 the most
; frames owed (at most 63), bit 6 full screen, bit 7 the recompiler on
RL_TICK         equ 0
RL_SPAN         equ 2
RL_RUN          equ 4
RL_DRAWN        equ 6
RL_COMP         equ 8
RL_CHG          equ 10
RL_MS           equ 12
RL_MAX          equ 14
RL_FLAGS        equ 15

; rw_clk - DX:AX = now, in 8253 counts of 838 ns. In a rate bracket the
; counter runs at the bracket's divisor and the hook counts its periods, so
; the clock is those; anywhere else it is os88pit.inc's.
rw_clk:
    cmp byte [rw_infsx], 0
    je .pit
    cmp byte [rw_fsrate], 0
    je .pit
    push bx
    pushf
    cli
    xor al, al                      ; latch counter 0
    out 43h, al
    in al, 40h
    mov ah, al
    in al, 40h
    xchg al, ah                     ; AX = the count left in this period
    mov bx, [rw_fsper]
    popf
    cmp ax, RW_FSDIV
    jbe .c
    mov ax, RW_FSDIV
.c:
    neg ax
    add ax, RW_FSDIV                ; counts into the period
    push ax
    mov ax, RW_FSDIV
    mul bx                          ; DX:AX = the periods before it
    pop bx
    add ax, bx
    adc dx, 0
    pop bx
    ret
.pit:
    jmp pit_now

; rw_logdraw - DX:AX = a draw's counts: into the second's total and maximum
rw_logdraw:
    mov bx, 1193                    ; counts a millisecond
    cmp dx, bx
    jb .d
    mov ax, 0FFFFh                  ; (over a minute: as a minute)
    jmp short .ms
.d:
    div bx
.ms:
    add [rw_ams], ax
    jnc .m
    mov word [rw_ams], 0FFFFh
.m:
    cmp ax, 255
    jbe .x
    mov ax, 255
.x:
    cmp al, [rw_amax]
    jbe .r
    mov [rw_amax], al
.r:
    ret

; rw_logowed - AL = frames owed now: the second's most
rw_logowed:
    cmp al, 63
    jbe .o
    mov al, 63
.o:
    cmp al, [rw_aowed]
    jbe .r
    mov [rw_aowed], al
.r:
    ret

; rw_logsec - from rw_stat, CX = the ticks it counted: the second's record,
; and its counts back to zero. Any context.
rw_logsec:
    cmp byte [rw_logon], 0
    je .zero
    mov bx, [rw_logn]
    and bx, RW_LOGN - 1
    shl bx, 1
    shl bx, 1
    shl bx, 1
    shl bx, 1
    add bx, rw_log
    add [rw_ltick], cx
    mov ax, [rw_ltick]
    mov [bx + RL_TICK], ax
    mov [bx + RL_SPAN], cx
    mov ax, [rw_nrun]
    mov [bx + RL_RUN], ax
    mov ax, [rw_ndrawn]
    mov [bx + RL_DRAWN], ax
    mov ax, [rw_acomp]
    mov [bx + RL_COMP], ax
    mov ax, [rw_achg]
    mov [bx + RL_CHG], ax
    mov ax, [rw_ams]
    mov [bx + RL_MS], ax
    mov al, [rw_amax]
    mov [bx + RL_MAX], al
    mov al, [rw_aowed]
    cmp byte [rw_infsx], 0
    je .w
    or al, 40h
.w:
    push ds
    mov ds, [cs:rb_viewseg]
    cmp byte [S_JITON], 0
    pop ds
    je .j
    or al, 80h
.j:
    mov [bx + RL_FLAGS], al
    inc word [rw_logn]
.zero:
    xor ax, ax
    mov [rw_acomp], ax
    mov [rw_achg], ax
    mov [rw_ams], ax
    mov [rw_amax], al
    mov [rw_aowed], al
    ret

; rw_logtoggle - Machine > Log, on the UI task: on from nothing, or off and
; written
rw_logtoggle:
    cmp byte [rw_logon], 0
    jne .off
    xor ax, ax
    mov [rw_logn], ax
    mov [rw_ltick], ax
    mov byte [rw_logon], 1
    mov si, rw_s_logon
    jmp rw_toast
.off:
    mov byte [rw_logon], 0
    jmp rw_logwrite

; rw_logwrite - the records as text into SYSTEM\APPDATA\REALBOY.LOG, on the
; UI task. Nothing recorded, nothing written.
rw_logwrite:
    cmp word [rw_logn], 0
    je .r
    mov ax, RW_LOGKB
    call OSAPI_MEM_CLAIM            ; DX = the text's segment
    jc .fail
    push dx
    mov es, dx
    xor di, di
    mov si, rw_s_loghd              ; REALBOY LOG - GAME.GB - CPU n
    call rw_lstr
    mov si, rw_name
    call rw_lstr
    mov si, rw_s_logcpu
    call rw_lstr
    call OSAPI_CPU_INFO             ; AL = the tier
    xor ah, ah
    mov cl, 1
    call rw_lnum
    mov si, rw_s_logcol
    call rw_lstr
    mov cx, [rw_logn]               ; the latest RW_LOGN, oldest first
    xor bx, bx
    cmp cx, RW_LOGN
    jbe .n
    mov bx, cx
    sub bx, RW_LOGN
    mov cx, RW_LOGN
.n:
    push cx
    push bx
    and bx, RW_LOGN - 1
    shl bx, 1
    shl bx, 1
    shl bx, 1
    shl bx, 1
    add bx, rw_log
    call rw_lline
    pop bx
    pop cx
    inc bx
    loop .n
    mov cx, di                      ; CX = the text's length
    pop dx
    push dx
    mov es, dx
    xor bx, bx
    mov si, rw_s_logname
    mov di, rw_logst
    call od_write
    pop dx
    pushf
    call OSAPI_MEM_FREE
    popf
    jc .fail
    mov si, rw_s_logok
    jmp rw_toast
.fail:
    mov si, rw_s_logno
    jmp rw_toast
.r:
    ret

; rw_lline - the record at BX as one line at ES:DI:
;   seconds  speed  run drawn  comp   chg  draw   max owed where
rw_lline:
    mov ax, [bx + RL_TICK]          ; seconds, to a tenth: ticks x 10 / 18.2
    mov dx, 100
    mul dx
    mov si, 182
    div si                          ; AX = tenths
    xor dx, dx
    mov si, 10
    div si
    push dx
    mov cl, 5
    call rw_lnum
    mov al, '.'
    stosb
    pop ax
    add al, '0'
    stosb
    mov ax, [bx + RL_SPAN]          ; speed: as rw_stat's
    or ax, ax
    jz .sp0
    mov cx, 100
    mul cx
    mov si, ax
    mov ax, [bx + RL_RUN]
    mov dx, 3048
    mul dx
    cmp dx, si
    jae .sp0                        ; (would not fit: as 0)
    div si
    jmp short .sp
.sp0:
    xor ax, ax
.sp:
    mov cl, 6
    call rw_lnum
    mov al, '%'
    stosb
    mov ax, [bx + RL_RUN]
    mov cl, 5
    call rw_lnum
    mov ax, [bx + RL_DRAWN]
    mov cl, 6
    call rw_lnum
    mov ax, [bx + RL_COMP]
    mov cl, 6
    call rw_lnum
    mov ax, [bx + RL_CHG]
    mov cl, 6
    call rw_lnum
    mov ax, [bx + RL_MS]
    mov cl, 6
    call rw_lnum
    mov al, [bx + RL_MAX]
    xor ah, ah
    mov cl, 5
    call rw_lnum
    mov al, [bx + RL_FLAGS]
    and ax, 3Fh
    mov cl, 5
    call rw_lnum
    mov al, ' '
    stosb
    mov al, 'W'
    test byte [bx + RL_FLAGS], 40h
    jz .w
    mov al, 'F'
.w:
    stosb
    test byte [bx + RL_FLAGS], 80h
    jz .e
    mov al, ' '
    stosb
    mov al, 'J'
    stosb
.e:
    mov ax, 0A0Dh
    stosw
    ret

; rw_lnum - AX as decimal at ES:DI, right-aligned in CL columns
rw_lnum:
    ; STKBALANCE-LOOP: one digit pushed a turn and the second loop pops them; the count is in CH
    push bx
    push dx
    mov bx, 10
    xor ch, ch
.d:
    xor dx, dx
    div bx
    push dx
    inc ch
    or ax, ax
    jnz .d
    sub cl, ch                      ; the padding first
    jbe .o
.p:
    mov al, ' '
    stosb
    dec cl
    jnz .p
.o:
    pop ax
    add al, '0'
    stosb
    dec ch
    jnz .o
    pop dx
    pop bx
    ret

; rw_lstr - the NUL-ended string at DS:SI to ES:DI
rw_lstr:
    lodsb
    or al, al
    jz .r
    stosb
    jmp short rw_lstr
.r:
    ret

rw_s_logname:   db 'REALBOY.LOG', 0
rw_s_loghd:     db 'REALBOY LOG - ', 0
rw_s_logcpu:    db ' - CPU tier ', 0
rw_s_logcol:    db 13, 10, ' seconds  speed  run drawn  comp   chg  draw  max owed', 13, 10
                db '                     (lines a second)  (ms a second, longest)', 13, 10, 0
rw_s_logon:     db 'Log on: written at close', 0
rw_s_logok:     db 'REALBOY.LOG written', 0
rw_s_logno:     db 'REALBOY: log not written', 0
