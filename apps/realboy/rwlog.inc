; =============================================================================
; os8088 - apps/realboy/rwlog.inc
;
; RealBoy's LOG TO FILE (docs/REALBOY-SPEC.md section 14.1): Machine > Log
; keeps a record a second - the game's speed, the frames run and drawn, the
; lines composed and changed, the drawing's time and its longest draw, how
; far behind the machine got, where it was and what the user did - and writes
; them as text beside REALBOY.O88, under a name of its own each time (the
; game's first six letters and a number: SUPER-00.LOG, SUPER-01.LOG), when
; the log is turned off or the window closes. It is for a machine with no
; debugger: the F1
; line says how a game runs this second, and this says how it ran for five
; minutes, which is what a field run needs to bring back. Included by
; realboy.asm.
;
; The worker and the bracket record (rw_stat, a second at a time); only the
; UI task writes (SPEC.md 20.6 rule 7), from the menu or the close.
; =============================================================================

RW_LOGN         equ 256             ; records kept, the latest: four minutes
RW_LOGSZ        equ 32
RW_LOGKB        equ 48              ; the text's claim at the write: 256 lines of
                                    ;   at most ~150 characters and the head
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
RL_EVT          equ 16              ; byte: what the user did in the second
RL_SMS          equ 18              ; word: ms comparing VRAM and OAM (scan)
RL_CMS          equ 20              ; word: ms composing the lines
RL_GMS          equ 22              ; word: ms running the Game Boy (rb_run)
RL_EVN          equ 24              ; word: the core's event entries
RL_BLK          equ 26              ; word: blocks the recompiler translated
RL_FL           equ 28              ; byte: its flushes (at most 255)
RL_BK           equ 29              ; byte: banks the bank cache fetched
RLE_RESET       equ 01h             ;   Machine > Reset
RLE_PAUSE       equ 02h             ;   Pause on
RLE_GO          equ 04h             ;   ...and off
RLE_FSIN        equ 08h             ;   into full screen
RLE_FSOUT       equ 10h             ;   ...and out
RLE_JITON       equ 20h             ;   the recompiler on
RLE_JITOFF      equ 40h             ;   ...and off
RLE_F1          equ 80h             ;   F1's line

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

; rw_logacc - CX:BX = a phase's start, DX:AX = its end, SI = a dword of
; counts this second: the length added. Keeps every register but SI.
rw_logacc:
    push ax
    push dx
    sub ax, bx
    sbb dx, cx
    add [si], ax
    adc [si + 2], dx
    pop dx
    pop ax
    ret

; rw_logdelta - AX = event entries, CX = blocks translated, DL = flushes
; and DH = banks fetched since the last call (each byte at most 255)
rw_logdelta:
    push bx
    push si
    push ds
    mov si, rw_lstat
    mov bx, [rw_nmiss]
    mov ds, [cs:rb_viewseg]
    mov ax, [S_EVCOUNT]
    mov cx, [S_JITNB]
    mov dx, [S_JITFL]
    pop ds
    sub ax, [si]
    add [si], ax
    sub cx, [si + 2]
    add [si + 2], cx
    sub dx, [si + 4]
    add [si + 4], dx
    or dh, dh
    jz .f
    mov dl, 255
.f:
    sub bx, [si + 6]
    add [si + 6], bx
    or bh, bh
    jz .b
    mov bl, 255
.b:
    mov dh, bl
    pop si
    pop bx
    ret

; rw_gameacc - the frame's run since rw_frame began, into the second's
rw_gameacc:
    push ax
    push bx
    push cx
    push dx
    push si
    call rw_clk
    mov bx, [rw_tgame]
    mov cx, [rw_tgame + 2]
    mov si, rw_agms
    call rw_logacc
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rw_logms - SI = a dword of counts: AX = it in ms (at most 65,535), and the
; dword back to 0
rw_logms:
    mov ax, [si]
    mov dx, [si + 2]
    xor bx, bx
    mov [si], bx
    mov [si + 2], bx
    mov bx, 1193
    cmp dx, bx
    jb .d
    mov ax, 0FFFFh
    ret
.d:
    div bx
    ret

; rw_dscanhk - rb_renderd's rb_dhook: the scan is done (DS = the view)
rw_dscanhk:
    push ax
    push dx
    push ds
    push cs
    pop ds
    call rw_clk
    mov [rw_tscan], ax
    mov [rw_tscan + 2], dx
    pop ds
    pop dx
    pop ax
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
    mov [rw_stspan], cx
    cmp byte [rw_logon], 0
    je .zero
    mov bx, [rw_logn]
    and bx, RW_LOGN - 1
    mov cl, 5                       ; x RW_LOGSZ
    shl bx, cl
    mov cx, [rw_stspan]
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
    mov al, [rw_aevt]
    mov [bx + RL_EVT], al
    call rw_logdelta                ; the counters' seconds
    mov [bx + RL_EVN], ax
    mov [bx + RL_BLK], cx
    mov [bx + RL_FL], dl
    mov [bx + RL_BK], dh
    push bx
    mov si, rw_asms
    call rw_logms
    pop bx
    mov [bx + RL_SMS], ax
    push bx
    mov si, rw_acms
    call rw_logms
    pop bx
    mov [bx + RL_CMS], ax
    push bx
    mov si, rw_agms
    call rw_logms
    pop bx
    mov [bx + RL_GMS], ax
    inc word [rw_logn]
    jmp short .z2
.zero:
    call rw_logdelta                ; (the counters move on, unlogged)
    xor ax, ax                      ; (the phases' counts too)
    mov [rw_asms], ax
    mov [rw_asms + 2], ax
    mov [rw_acms], ax
    mov [rw_acms + 2], ax
    mov [rw_agms], ax
    mov [rw_agms + 2], ax
.z2:
    xor ax, ax
    mov [rw_acomp], ax
    mov [rw_achg], ax
    mov [rw_ams], ax
    mov [rw_amax], al
    mov [rw_aowed], al
    mov [rw_aevt], al
    ret

; rw_logevt - AL = RLE_* bits: something the user did, into this second's
; record. Any context.
rw_logevt:
    or [rw_aevt], al
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
    call rw_mgrey                   ; the item says what it is now
    mov si, rw_s_logon
    jmp rw_toast
.off:
    mov byte [rw_logon], 0
    call rw_mgrey
    jmp rw_logwrite

; rw_logwrite - the records as text beside REALBOY.O88, on the UI task,
; under the first name free of GAMEnn.LOG. Nothing recorded, nothing written.
rw_logwrite:
    cmp word [rw_logn], 0
    je .r
    mov ax, RW_LOGKB
    call OSAPI_MEM_CLAIM            ; DX = the text's segment
    jc .fail
    push dx
    mov es, dx
    xor di, di
    call rw_lhead
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
    mov cl, 5
    shl bx, cl
    add bx, rw_log
    call rw_lline
    pop bx
    pop cx
    inc bx
    loop .n
    mov [rw_llen], di               ; the text's length
    mov dx, [rw_pkgdir]             ; where the program is
    mov bl, [rw_pkgvol]
    call rw_fgo
    jc .back
    call rw_lname                   ; SI = the first free name
    pop dx
    push dx
    mov es, dx
    xor bx, bx
    mov cx, [rw_llen]
    push dx
    xor dx, dx
    call OSAPI_FILE_WRITE
    pop dx
.back:
    call rw_fback                   ; (CF kept)
    pop dx
    pushf
    call OSAPI_MEM_FREE
    popf
    jc .fail
    mov si, rw_s_logok              ; "Log: SUPER-00.LOG"
    mov di, rw_s_logok + 5
    push ds
    pop es
    push si
    mov si, rw_lfile
    call rw_lstr
    stosb                           ; (the NUL)
    pop si
    jmp rw_toast
.fail:
    mov si, rw_s_logno
    jmp rw_toast
.r:
    ret

; rw_lname - rw_lfile = the game's first six letters, two digits and .LOG,
; the first such name not in the current folder (00-99; at 99, 99 again).
; SI = rw_lfile.
rw_lname:
    push ds
    pop es
    mov si, rw_name
    mov di, rw_lfile
    mov cx, 6
.c:
    lodsb
    or al, al
    jz .s
    cmp al, '.'
    je .s
    stosb
    loop .c
.s:
    mov [rw_ldig], di
    mov word [di], '00'
    mov word [di + 2], '.L'
    mov word [di + 4], 'OG'
    mov byte [di + 6], 0
    xor dx, dx                      ; DL = the number
.try:
    mov al, dl
    aam                             ; AH = tens, AL = ones
    add ax, '00'
    xchg al, ah
    mov di, [rw_ldig]
    mov [di], ax
    push dx
    mov si, rw_lfile
    push ds
    pop es
    xor bx, bx
    xor cx, cx
    xor dx, dx
    call OSAPI_FILE_READ            ; with no room: is it there?
    pop dx
    jnc .next                       ; (an empty one is)
    cmp ax, FERR_NOENT
    je .got
.next:
    inc dl
    cmp dl, 100
    jb .try
.got:
    mov si, rw_lfile
    ret

; rw_lhead - the log's two head lines and the columns at ES:DI:
;   REALBOY LOG - SUPER-~1.GB - 64K MBC1 - RAM none
;   CPU tier 1 - display 4 bpp - full screen VGA - recompiler yes
rw_lhead:
    mov si, rw_s_loghd
    call rw_lstr
    mov si, rw_name
    call rw_lstr
    mov si, rw_s_lsep
    call rw_lstr
    mov ax, [rw_banks]              ; the ROM, KB
    mov cl, 4
    shl ax, cl
    mov cl, 1
    call rw_lnum
    mov si, rw_s_lkmbc
    call rw_lstr
    push ds
    mov ds, [cs:rb_viewseg]
    mov al, [S_MBC]
    pop ds
    xor ah, ah
    mov cl, 1
    call rw_lnum
    mov si, rw_s_lram
    call rw_lstr
    mov al, [rw_rambanks]
    xor ah, ah
    mov cl, 1
    call rw_lnum
    mov si, rw_s_lbanks
    call rw_lstr
    mov si, rw_s_lbatt
    cmp byte [rw_batt], 0
    je .nb
    call rw_lstr
.nb:
    mov si, rw_s_lrtc
    cmp byte [rw_rtc], 0
    je .nr
    call rw_lstr
.nr:
    mov si, rw_s_lcpu               ; the machine
    call rw_lstr
    call OSAPI_CPU_INFO             ; AL = the tier
    xor ah, ah
    mov cl, 1
    call rw_lnum
    mov si, rw_s_ldisp
    call rw_lstr
    push di
    mov bx, [rw_win]
    call OSAPI_WM_DISPLAY           ; DH = bits per pixel
    pop di
    mov al, dh
    xor ah, ah
    mov cl, 1
    call rw_lnum
    mov si, rw_s_lfs
    call rw_lstr
    call rw_fspick                  ; AL = the full screen's writer
    mov si, rw_s_lnone
    jc .fs
    mov si, rw_s_lvga
    cmp al, RW_FSVGA
    je .fs
    mov si, rw_s_lherc
    cmp al, RW_FSHERC
    je .fs
    mov si, rw_s_lcga
.fs:
    call rw_lstr
    mov si, rw_s_ljit
    call rw_lstr
    mov si, rw_s_lno
    cmp word [rw_jitseg], 0
    je .j
    mov si, rw_s_lyes
.j:
    call rw_lstr
    mov si, rw_s_lheap              ; the heap the load found (why there is
    call rw_lstr                    ;   no recompiler, when there is not)
    mov ax, [rw_pavail]
    mov cl, 1
    call rw_lnum
    mov al, 'K'
    stosb
    cmp byte [rw_bcache], 0         ; the bank cache: its slots, and the
    je .nc                          ;   banks it has fetched so far
    mov si, rw_s_lcache
    call rw_lstr
    mov ax, [rw_nslot]
    mov cl, 1
    call rw_lnum
    mov si, rw_s_lslots
    call rw_lstr
    mov ax, [rw_nmiss]
    mov cl, 1
    call rw_lnum
    mov si, rw_s_lfetch
    call rw_lstr
.nc:
    mov si, rw_s_logcol
    jmp rw_lstr

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
    mov ax, [bx + RL_SMS]
    mov cl, 5
    call rw_lnum
    mov ax, [bx + RL_CMS]
    mov cl, 5
    call rw_lnum
    mov ax, [bx + RL_GMS]
    mov cl, 5
    call rw_lnum
    mov al, [bx + RL_MAX]
    xor ah, ah
    mov cl, 5
    call rw_lnum
    mov al, [bx + RL_FLAGS]
    and ax, 3Fh
    mov cl, 5
    call rw_lnum
    mov ax, [bx + RL_EVN]           ; the counters
    mov cl, 6
    call rw_lnum
    mov ax, [bx + RL_BLK]
    mov cl, 5
    call rw_lnum
    mov al, [bx + RL_FL]
    xor ah, ah
    mov cl, 3
    call rw_lnum
    mov al, [bx + RL_BK]
    xor ah, ah
    mov cl, 3
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
    mov dl, [bx + RL_EVT]           ; what the user did, by name
    mov si, rw_s_levts
.ev:
    or dl, dl
    jz .ee
    shr dl, 1
    jnc .evn
    push si
    call rw_lstr
    pop si
.evn:
    add si, 7
    jmp short .ev
.ee:
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

rw_s_loghd:     db 'REALBOY LOG - ', 0
rw_s_lsep:      db ' - ', 0
rw_s_lkmbc:     db 'K, MBC ', 0
rw_s_lram:      db ', RAM ', 0
rw_s_lbanks:    db ' x 8K', 0
rw_s_lbatt:     db ', battery', 0
rw_s_lrtc:      db ', clock', 0
rw_s_lcpu:      db 13, 10, 'CPU tier ', 0
rw_s_ldisp:     db ', display ', 0
rw_s_lfs:       db ' bpp, full screen ', 0
rw_s_lnone:     db 'none', 0
rw_s_lvga:      db 'VGA', 0
rw_s_lherc:     db 'Hercules', 0
rw_s_lcga:      db 'CGA', 0
rw_s_ljit:      db ', recompiler ', 0
rw_s_lyes:      db 'yes', 0
rw_s_lno:       db 'no', 0
rw_s_lheap:     db ', heap ', 0
rw_s_lcache:    db ', bank cache ', 0
rw_s_lslots:    db ' x 16K over XMS, ', 0
rw_s_lfetch:    db ' fetched', 0
rw_s_logcol:    db 13, 10, ' seconds  speed  run drawn  comp   chg  draw scan  cmp  cpu  max owed  evts  blk fl bk', 13, 10
                db '                     (lines a second)  (ms a second: drawing, of it the', 13, 10
                db '                      scan and the lines; the Game Boy)  (core events, blocks', 13, 10
                db '                      translated, cache flushes, banks fetched, a second)', 13, 10, 0
; the RLE_* bits' names, a bit at a time from bit 0, seven bytes each
rw_s_levts:     db ' RESET', 0
                db ' PAUSE', 0
                db ' GO', 0, 0, 0, 0
                db ' FS+', 0, 0, 0
                db ' FS-', 0, 0, 0
                db ' JIT+', 0, 0
                db ' JIT-', 0, 0
                db ' F1', 0, 0, 0, 0
rw_s_logon:     db 'Log on: written at close', 0
rw_s_logok:     db 'Log: ', 0, '           ', 0
rw_s_logno:     db 'REALBOY: log not written', 0
