; =============================================================================
; os8088 - apps/realboy/realboy.asm
;
; REALBOY: a Game Boy in a window (docs/REALBOY-SPEC.md section 14). The
; core is parts 0 and 1 of this file - 64KB of generated SM83 handlers,
; apps/realboy/rbgen.py's, in two halves one segment apart - and the view the
; Game Boy's memory lives in is part 2, a zeroed 64KB carve; the cartridge is
; a claim of its own size.
; rbsys.inc runs the machine, rbppu.inc composes its frame, and this file is
; the window round them: open a .GB, run it to the wall clock in a worker,
; and put each frame it has time for on the glass.
;
; THE WORKER owns the machine. It counts BIOS ticks into Game Boy frames
; owed (59.7275 Hz against 18.2065: 840/256 of a frame a tick), runs the core
; in budgets of RW_BUDGET M-cycles - the core runs with interrupts off
; (REALBOY-SPEC section 5.2), so the budget is the IRQ latency - and yields
; between them. It composes and blits a frame only when it has caught up, or
; every RW_SKIPMAX frames whatever happens, so the game keeps its speed and
; the picture takes what is left (docs/plans/REALBOY-PLAN.md section 4.5).
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'REALBOY', rw_entry, OS88_F_ICON | OS88_F_ASSOC | OS88_F_PARTS, OS88_STACK_384

; --- embedded 16x16 icon: a Game Boy, the screen and the cross --------------
    OS88_ICON16
    dw 0x0000, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8
    dw 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x0000
    dw 0x0000, 0x3FF8, 0x2008, 0x2FE8, 0x2FE8, 0x2FE8, 0x2FE8, 0x2008
    dw 0x2008, 0x2468, 0x2E08, 0x2468, 0x2008, 0x2008, 0x3FF8, 0x0000
    OS88_ICON16_END

; --- the extension this program opens ---------------------------------------
    OS88_ASSOC16
    db 1
    OS88_ASSOC_EXT 'GB'
    OS88_ASSOC16_END

%include "os88parts.inc"

RW_CONT_W       equ 160
RW_CONT_H       equ 144
RW_BUDGET       equ 2000            ; M-cycles a core run: ~5.6 ms on a 286
RW_PERTICK      equ 840             ; frames a BIOS tick, x 256
RW_OWEDMAX      equ 8 * 256         ; a machine that was away catches up 8
RW_SKIPMAX      equ 15              ; a frame drawn at least every 15
RW_ROMMAX_KB    equ 256

; --- the bss: the standard's words first, then ours --------------------------
rw_win          equ os88_image_end + OP_BSS
rw_state        equ rw_win + 2      ; 0 no game, 1 running, 2 stopped
rw_pause        equ rw_state + 1
rw_resetq       equ rw_pause + 1    ; Reset asked; the worker does it
rw_abon         equ rw_resetq + 1   ; the About card is up
rw_shown        equ rw_abon + 1     ; rw_fbuf holds a frame
rw_since        equ rw_shown + 1    ; frames since one was drawn
rw_argpend      equ rw_since + 1
rw_argvol       equ rw_argpend + 1
rw_last         equ rw_argvol + 1   ; word: the tick last counted
rw_owed         equ rw_last + 2     ; word: frames owed, x 256
rw_romseg       equ rw_owed + 2
rw_romkb        equ rw_romseg + 2
rw_banks        equ rw_romkb + 2
rw_argdir       equ rw_banks + 2
rw_spawned      equ rw_argdir + 2
rw_name         equ rw_spawned + 2  ; 16: the game's file name
rw_ovl          equ rw_name + 16    ; the F1 overlay is up
rw_f1was        equ rw_ovl + 1      ; F1 was held at the last look
rw_nrun         equ rw_f1was + 1    ; word: frames run since the last count
rw_ndrawn       equ rw_nrun + 2     ; word: ...and drawn
rw_tstat        equ rw_ndrawn + 2   ; word: the tick that count began
rw_ovltxt       equ rw_tstat + 2    ; 16: 'NNN% NNfps', composed once a second
rw_fbuf         equ rw_ovltxt + 16  ; 5,760: rb_render's frame
rw_pbuf         equ rw_fbuf + 5760  ; 11,520: the frame as the screen takes it
RW_BSS          equ 2 + 10 + 2 + 2 + 2 + 2 + 2 + 2 + 2 + 16 + 2 + 6 + 16 + 5760 + 11520

; =============================================================================
; rw_entry - the loader calls this once; the window appears afterwards
; =============================================================================
rw_entry:
    push es                         ; op_load spends ES, and OSAPI_ARG_FILE
    call op_load                    ;   reads through the kernel's
    pop es
    jc .refused                     ; no room for the core and view: it said
    mov al, KSC_UP                  ; arm the key map (the first call only
    call OSAPI_KEY_DOWN             ;   arms it)
    call OSAPI_ARG_FILE             ; CF = 1: launched empty
    jc .nodoc
    mov di, rw_name
    mov cx, 13
.cpn:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    or al, al
    jz .cpd
    loop .cpn
.cpd:
    mov byte [rw_name+13], 0
    mov [rw_argdir], dx
    mov [rw_argvol], bl
    mov byte [rw_argpend], 1
.nodoc:
    mov si, rw_tpl
    call OSAPI_WM_CREATE            ; BX = the window
    jc .refused
    mov [rw_win], bx
    mov al, 1
    call OSAPI_WM_SNAP              ; content on the byte grid, for BLITP
    call OSAPI_WM_OWNBG             ; we paint every pixel of it
    OS88_REGION_MOVABLE rw_reloc
    mov si, rw_menus
    call OSAPI_MENU_SET
    mov si, rw_about
    call OSAPI_ABOUT_SET
    mov ax, rw_onwake
    call OSAPI_WM_ONWAKE
    cmp byte [rw_argpend], 0
    je .ok
    call OSAPI_WM_WAKE              ; the document, once the window is up
.ok:
    clc
    ret
.refused:
    stc
    ret

; rw_reloc - OUR REGION MOVED (SPEC.md 66.6.1): BX = where it was, DX = where
; it is. rbsys's own words moved with it; the state block in the view, which
; did not, names our code segment in five vectors. The worker is parked at
; OSAPI_TASK_ALIVE whenever this runs, never in the core.
rw_reloc:
    push ax
    push ds
    mov ax, [cs:rb_viewseg]
    or ax, ax
    jz .r
    mov ds, ax
    cmp [S_EVVEC+2], bx
    jne .1
    mov [S_EVVEC+2], dx
.1:
    cmp [S_IORVEC+2], bx
    jne .2
    mov [S_IORVEC+2], dx
.2:
    cmp [S_IOWVEC+2], bx
    jne .3
    mov [S_IOWVEC+2], dx
.3:
    cmp [S_MBCVEC+2], bx
    jne .4
    mov [S_MBCVEC+2], dx
.4:
    cmp [S_TRACEVEC+2], bx
    jne .r
    mov [S_TRACEVEC+2], dx
.r:
    pop ds
    pop ax
    ret

; rbsys asks its host for these: the link port's bytes go nowhere, and this
; core is not a trace build
rb_putc:
rb_trbyte:
    ret

; =============================================================================
; Loading a game
; =============================================================================

; rw_onwake - on the UI task, no lock held: a document we were launched with,
; or the core having stopped
rw_onwake:
    cmp byte [rw_argpend], 0
    je .stopped
    mov byte [rw_argpend], 0
    call OSAPI_GFX_LOCK
    mov dx, [rw_argdir]
    mov bl, [rw_argvol]
    call OSAPI_FILE_GOTO_QM
    jc .unlock
    mov si, [rw_win]
    call rw_load
.unlock:
    call OSAPI_GFX_UNLOCK
    ret
.stopped:
    cmp byte [rw_state], 2
    jne .r
    call OSAPI_GFX_LOCK
    mov si, [rw_win]
    call rw_repaint
    call OSAPI_GFX_UNLOCK
.r:
    ret

; rw_open - File > Open: the Standard File dialog, then rw_opened
rw_open:
    cmp byte [rw_state], 0
    jne .one
    mov al, FDLG_OPEN
    mov bx, si
    mov di, rw_opened
    xor si, si
    call OSAPI_FILE_DLG
    ret
.one:
    mov si, rw_s_one                ; one game a window: another opens in
    jmp rw_toast                    ;   another window

; rw_opened - the dialog's completion: DI = the name, DX:CX = its size
rw_opened:
    push si
    mov si, di                      ; copy the kernel's name now
    mov di, rw_name
    mov bx, 13
.c:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    or al, al
    jz .cd
    dec bx
    jnz .c
.cd:
    mov byte [rw_name+13], 0
    pop si
    ; (the size the dialog read out of the listing is not used: rw_load asks
    ; the file itself, which knows its size unpacked)
; rw_load - rw_name in the current folder, SI = our window, the gfx lock
; held. THE SIZE PROBE first - a read with no room answers FERR_BIG with the
; KB the read needs, from the directory and unpacked, with some slack for a
; compressed file's expansion - then a claim that size, the read, and the
; check on the bytes that actually came in: whole 16KB banks, 32 to 256KB.
rw_load:
    push si
    push ds
    pop es
    xor bx, bx
    xor cx, cx
    xor dx, dx
    mov si, rw_name
    call OSAPI_FILE_READ
    jnc .notrom                     ; an empty file
    cmp ax, FERR_BIG
    jne .rdfail0
    cmp dx, 32
    jb .notrom
    cmp dx, RW_ROMMAX_KB + 2        ; (the slack)
    ja .big
    mov [rw_romkb], dx
    call OSAPI_MEM_AVAIL            ; AX = the largest run, in KB
    cmp ax, [rw_romkb]
    jb .room
    mov ax, [rw_romkb]
    call OSAPI_MEM_CLAIM            ; DX = its segment
    jc .room
    mov [rw_romseg], dx
    mov es, dx
    xor bx, bx
    mov ax, [rw_romkb]
    mov cx, 1024
    mul cx
    mov cx, ax                      ; DX:CX = the claim's capacity
    mov si, rw_name
    call OSAPI_FILE_READ            ; DX:AX = the bytes read
    jc .rdfail
    ; the ROM itself: whole 16KB banks, 2 to 16 of them
    test ax, 3FFFh
    jnz .notrom1
    mov cx, 14
.sh:
    shr dx, 1
    rcr ax, 1
    loop .sh                        ; AX = banks
    cmp ax, 2
    jb .notrom1
    cmp ax, RW_ROMMAX_KB / 16
    ja .notrom1
    mov [rw_banks], ax
    call rw_start
    mov byte [rw_state], 1
    pop si
    call rw_hire
    call rw_repaint
    ret
.notrom1:
    mov dx, [rw_romseg]             ; the claim back
    call OSAPI_MEM_FREE
.notrom:
    mov si, rw_s_notrom
    jmp short .say
.rdfail:
    mov dx, [rw_romseg]
    call OSAPI_MEM_FREE
.rdfail0:
    mov si, rw_s_read
    jmp short .say
.big:
    mov si, rw_s_big
    jmp short .say
.room:
    mov si, rw_s_room
.say:
    pop bx                          ; (the window, banked)
    jmp rw_toast

; rw_start - rb_init: the view, the core, the ROM, its banks
rw_start:
    mov al, 2                       ; the view
    call op_seg
    push ax
    xor al, al                      ; the core, both halves from here
    call op_seg
    mov bx, ax
    pop ax
    mov cx, [rw_romseg]
    mov dx, [rw_banks]
    jmp rb_init

; rw_hire - the worker, once (the lock is held: paint, a menu or a dialog)
rw_hire:
    cmp byte [rw_spawned], 0
    jne .r
    mov ax, rw_worker
    mov bx, [rw_win]
    call OSAPI_TASK_SPAWN
    jc .r                           ; refused for now: the next paint asks
    OS88_WORKER_RESTARTABLE rw_worker_rs
    mov byte [rw_spawned], 1
.r:
    ret

; rw_toast - SI = a line of our own, 24 characters at most
rw_toast:
    push ds
    pop es
    xor cx, cx
    call OSAPI_TOAST
    ret

; =============================================================================
; The worker
; =============================================================================
rw_worker_rs:                       ; THE RESTART POINT: our region moved with
    mov byte [rw_since], RW_SKIPMAX ;   the worker parked at the top of its
rw_worker:                          ;   loop; draw the next frame whole
    call OSAPI_GET_TICKS
    mov [rw_last], ax
.loop:
    mov bx, [rw_win]
    call OSAPI_TASK_ALIVE           ; no lock held; a closed window ends here
    cmp byte [rw_resetq], 0
    je .noreset
    mov byte [rw_resetq], 0
    call rw_reset
.noreset:
    cmp byte [rw_state], 1
    jne .sleep
    cmp byte [rw_pause], 0
    jne .sleep
    call OSAPI_GET_TICKS
    mov bx, ax
    sub bx, [rw_last]
    js .resync
    mov [rw_last], ax
    cmp bx, 10
    jbe .acc
    mov bx, 10
.acc:
    mov ax, RW_PERTICK
    mul bx
    add ax, [rw_owed]
    cmp ax, RW_OWEDMAX              ; a machine that fell behind runs on from
    jbe .owe                        ;   here rather than racing to catch up
    mov ax, RW_OWEDMAX
.owe:
    mov [rw_owed], ax
    cmp ax, 256                     ; nothing owed yet: sleep to the tick
    jb .sleep
    call rw_keys
    call rw_frame
    jc .loop                        ; it stopped
    inc word [rw_nrun]
    call rw_stat
    sub word [rw_owed], 256
    inc byte [rw_since]
    cmp word [rw_owed], 256         ; caught up: draw this one
    jb .draw
    cmp byte [rw_since], RW_SKIPMAX ; ...or it has been too long
    jb .loop
.draw:
    mov byte [rw_since], 0
    inc word [rw_ndrawn]
    call rw_present
    jmp .loop                       ; the clock is read again after EVERY
                                    ;   frame: a worker that spent what it
                                    ;   was owed before looking slept a tick
                                    ;   it did not have whenever it was behind
.resync:
    mov [rw_last], ax
.sleep:
    mov ax, 1
    call OSAPI_TASK_SLEEP
    jmp .loop

; rw_frame - run the machine to its next frame, yielding between budgets.
; CF = 1: the core stopped (a bad opcode), and the UI task is told.
rw_frame:
    mov cx, 12                      ; with the LCD off no frame ever ends:
.run:                               ;   a frame's worth of budgets is one
    push cx
    mov ax, RW_BUDGET
    call rb_run
    pop cx
    cmp al, RBX_FRAME
    je .done
    cmp al, RBX_BADOP
    je .bad
    call OSAPI_TASK_YIELD
    loop .run
.done:
    clc
    ret
.bad:
    mov byte [rw_state], 2
    mov bx, [rw_win]
    call OSAPI_WM_WAKE
    stc
    ret

; rw_reset - Machine > Reset, on the worker: rb_init again from the ROM
rw_reset:
    cmp byte [rw_state], 0
    je .r
    call rw_start
    mov byte [rw_state], 1
    mov word [rw_owed], 0
.r:
    ret

; rw_stat - once a second, the overlay's line: the game's speed, frames run
; against the 59.7275 a second the cartridge expects, and the frames drawn
rw_stat:
    call OSAPI_GET_TICKS
    mov cx, ax
    sub cx, [rw_tstat]              ; CX = ticks counted
    cmp cx, 18
    jb .r
    mov [rw_tstat], ax
    cmp cx, 600                     ; a pause, or the first look: start over
    ja .zero
    ; speed = run x 100 x 18.2065 / (59.7275 x ticks) = run x 3048 / (ticks x 100)
    mov ax, 100
    mul cx
    mov bx, ax                      ; BX = ticks x 100
    mov ax, [rw_nrun]
    mov dx, 3048
    mul dx                          ; DX:AX = run x 3048
    div bx                          ; AX = speed, %
    push ds
    pop es
    mov di, rw_ovltxt
    call rw_dec
    mov al, '%'
    stosb
    mov al, ' '
    stosb
    ; fps = drawn x 18.2065 / ticks ~ drawn x 182 / (ticks x 10)
    mov ax, 10
    mul cx
    mov bx, ax                      ; BX = ticks x 10
    mov ax, [rw_ndrawn]
    mov dx, 182
    mul dx
    div bx
    call rw_dec
    mov si, rw_s_fps
.c:
    lodsb
    stosb
    or al, al
    jnz .c
.zero:
    xor ax, ax
    mov [rw_nrun], ax
    mov [rw_ndrawn], ax
.r:
    ret

; rw_dec - AX (0-999) as decimal at ES:DI, no leading zeros
rw_dec:
    ; STKBALANCE-LOOP: one digit pushed a turn and the second loop pops them; the count is in CX
    push bx
    push cx
    push dx
    mov bx, 10
    xor cx, cx
.d:
    xor dx, dx
    div bx
    push dx
    inc cx
    or ax, ax
    jnz .d
.o:
    pop ax
    add al, '0'
    stosb
    loop .o
    pop dx
    pop cx
    pop bx
    ret

; rw_keys - the joypad, from the keys held - and nothing held while another
; window has the keyboard. F1 toggles the speed overlay.
rw_keys:
    xor dl, dl
    call OSAPI_WM_TOP
    cmp bx, [rw_win]
    jne .set
    call OSAPI_MENU_OWNER
    cmp bx, [rw_win]
    jne .set
    mov al, 3Bh                     ; F1, on its press
    call OSAPI_KEY_DOWN
    sbb al, al
    mov ah, al
    xchg al, [rw_f1was]
    not al
    and al, ah
    jz .nof1
    xor byte [rw_ovl], 1
.nof1:
    mov si, rw_keymap
    mov dh, 1
.k:
    lodsb
    or al, al
    jz .set
    call OSAPI_KEY_DOWN             ; CF = 1: held
    jnc .n
    or dl, dh
.n:
    shl dh, 1
    jnz .k
.set:
    push ds
    mov ds, [cs:rb_viewseg]
    mov [S_JOY], dl
    pop ds
    ret
; S_JOY's bits: Right, Left, Up, Down, A, B, Select, Start
rw_keymap:  db KSC_RIGHT, KSC_LEFT, KSC_UP, KSC_DOWN, 2Dh, 2Ch, 39h, KSC_ENTER, 0

; rw_present - compose the frame and put it on the glass (the worker's)
rw_present:
    push ds
    pop es
    mov di, rw_fbuf
    call rb_render
    mov byte [rw_shown], 1
    cmp byte [rw_abon], 0           ; the About card is over us: keep it
    jne .r
    call OSAPI_GFX_LOCK
    mov ax, KERNEL_SEG              ; a worker loads ES itself
    mov es, ax
    mov bx, [rw_win]
    test word [es:bx + W_FLAGS], 2
    jz .un
    call OSAPI_WM_CLIP_SET          ; CF = 1: not a pixel of us shows
    jc .un
    call rw_blit
    call rw_overlay
.un:
    call OSAPI_GFX_UNLOCK
.r:
    ret

; rw_overlay - the speed line over the picture's top left, when F1 put it up
rw_overlay:
    cmp byte [rw_ovl], 0
    je .r
    cmp byte [rw_ovltxt], 0
    je .r
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    mov cx, ax
    mov si, rw_ovltxt
    mov ax, (CWHITE << 8) | CBLACK
    call OSAPI_FONT_RUN
.r:
    ret

; rw_blit - rw_fbuf onto the content, the lock held and the clip armed: four
; planes through BLITP on a colour display, a dithered band through BLIT1 on
; a monochrome one (or where BLITP refuses)
rw_blit:
    mov bx, [rw_win]
    call OSAPI_WM_DISPLAY           ; DH = bits per pixel
    cmp dh, 1
    jbe .mono
    call rw_planes
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    mov bx, dx
    push ds
    pop es
    mov si, rw_pbuf
    mov di, 4000h | 20              ; walk an armed clip; 20 bytes a plane
    mov bp, 80
    mov cx, RW_CONT_W
    mov dx, RW_CONT_H
    call OSAPI_GFX_BLITP
    jnc .r
    mov al, CWHITE                  ; refused (a straddle, kern_small): the
    mov ah, CBLACK                  ;   dithered picture, in two colours
    call OSAPI_GFX_BLIT1_PEN
.mono:
    call rw_dither
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT
    mov bx, dx
    push ds
    pop es
    mov si, rw_pbuf
    mov bp, 20
    mov cx, RW_CONT_W
    mov dx, RW_CONT_H
    call OSAPI_GFX_BLIT1
.r:
    ret

; rw_planes - rw_fbuf as the desktop's colours, row by row: 15 white, 7 light
; grey, 8 dark grey, 0 black for shades 0-3. Planes 0-2 are the shade's bit
; 1 inverted and plane 3 its bit 0 inverted, so it is no per-pixel work
rw_planes:
    push ds
    pop es
    mov si, rw_fbuf
    mov di, rw_pbuf
    mov dx, RW_CONT_H
.row:
    mov cx, 20
.b:
    mov al, [si+20]                 ; bit 1
    not al
    mov [di], al
    mov [di+20], al
    mov [di+40], al
    mov al, [si]                    ; bit 0
    not al
    mov [di+60], al
    inc si
    inc di
    loop .b
    add si, 20
    add di, 60
    dec dx
    jnz .row
    ret

; rw_dither - rw_fbuf as one bit a pixel, 1 = lit: shade 0 all lit, 1 a
; quarter dark, 2 half (a checkerboard), 3 all dark - a 2x2 ordered dither
rw_dither:
    push ds
    pop es
    mov si, rw_fbuf
    mov di, rw_pbuf
    xor dx, dx                      ; DL = the row's parity
.row:
    mov bl, 0AAh                    ; even rows: half on even columns, the
    mov bh, 0AAh                    ;   quarter on even columns
    test dl, 1
    jz .ev
    mov bl, 055h                    ; odd rows: the other half, no quarter
    xor bh, bh
.ev:
    mov cx, 20
.b:
    mov al, [si]                    ; bit 0
    mov ah, [si+20]                 ; bit 1
    mov dh, al
    and dh, ah                      ; shade 3: dark
    not al
    and al, ah                      ; shade 2: bit 1 alone
    and al, bl
    or dh, al
    mov al, [si]
    not ah
    and al, ah                      ; shade 1: bit 0 alone
    and al, bh
    or al, dh
    not al                          ; lit = not dark
    stosb
    inc si
    loop .b
    add si, 20
    inc dl
    cmp dl, RW_CONT_H
    jb .row
    ret

; =============================================================================
; The window
; =============================================================================

; rw_paint - SI = the window, the lock held, the clip armed
rw_paint:
    push si
    cmp byte [rw_shown], 0
    je .blank
    call rw_blit
    jmp short .about
.blank:
    call rw_fillwhite
    mov si, rw_s_open1
    cmp byte [rw_state], 2
    jne .t
    mov si, rw_s_stop1
.t:
    mov dx, 60
    call rw_line
    mov si, rw_s_open2
    cmp byte [rw_state], 2
    jne .t2
    mov si, rw_s_stop2
.t2:
    mov dx, 74
    call rw_line
.about:
    pop si
    cmp byte [rw_abon], 0
    je .r
    push si
    mov bx, si
    mov si, rw_ablines
    call os88ui_about_d
    pop si
    cmp byte [rw_spawned], 0        ; a refused hire is asked again here
    jne .r
    cmp byte [rw_state], 1
    jne .r
    call rw_hire
.r:
    ret

; rw_line - SI = a string, DX = its row in the content, centred
rw_line:
    push ax
    push bx
    push cx
    push dx
    mov cx, dx
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    add dx, cx                      ; DX = the row
    mov bx, ax
    call OSAPI_FONT_WIDTH           ; AX = the string's width
    mov cx, RW_CONT_W
    sub cx, ax
    sar cx, 1
    add cx, bx                      ; CX = x
    mov ax, (CWHITE << 8) | CBLACK
    call OSAPI_FONT_RUN
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rw_fillwhite - the content white
rw_fillwhite:
    push ax
    push bx
    push cx
    push dx
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT
    mov bx, dx
    mov cx, ax
    add cx, RW_CONT_W - 1
    add dx, RW_CONT_H - 1
    call OSAPI_GFX_FILL
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rw_repaint - SI = the window, the lock held: everything, ourselves
rw_repaint:
    push bx
    mov bx, si
    call OSAPI_WM_CLIP_SET
    pop bx
    jc .r
    jmp rw_paint
.r:
    ret

; rw_oncmd - AH = the menu, AL = the item, SI = the window, the lock held
rw_oncmd:
    push ax
    call rw_abdismiss
    pop ax
    cmp ah, 0
    jne .machine
    cmp al, 0
    je rw_open
    mov bx, si                      ; File > Close
    call OSAPI_WM_CLOSE
    ret
.machine:
    cmp al, 0
    jne .pause
    mov byte [rw_resetq], 1         ; Reset: the worker's to do
    ret
.pause:
    xor byte [rw_pause], 1
    ret

rw_about:
    mov byte [rw_abon], 1
    mov bx, si
    mov si, rw_ablines
    jmp os88ui_about

rw_abdismiss:
    mov bx, rw_abon
    mov ax, rw_repaint
    jmp os88ui_abdismiss

rw_tpl:
    dw 160, 60, RW_CONT_W + 2, RW_CONT_H + TITLE_H + 2
    dw rw_ttl, rw_paint, 0, rw_abdismiss

    OS88_MENUSET rw_menus, rw_ttl, rw_oncmd
        OS88_MENU rw_m_file, rw_i_file, 2
        OS88_MENU rw_m_mach, rw_i_mach, 2
    OS88_MENUSET_END rw_menus

rw_ttl:         db 'RealBoy', 0
rw_m_file:      db 'File', 0
rw_i_file:      dw rw_it_open, rw_it_close
rw_it_open:     db 'Open...', 0
rw_it_close:    db 'Close', 0
rw_m_mach:      db 'Machine', 0
rw_i_mach:      dw rw_it_reset, rw_it_pause
rw_it_reset:    db 'Reset', 0
rw_it_pause:    db 'Pause', 0

rw_s_fps:       db 'fps', 0
rw_s_open1:     db 'File > Open a', 0
rw_s_open2:     db 'Game Boy .GB', 0
rw_s_stop1:     db 'The game stopped:', 0
rw_s_stop2:     db 'an invalid opcode', 0
rw_s_one:       db 'REALBOY: one game each', 0
rw_s_big:       db 'REALBOY: ROM over 256K', 0
rw_s_notrom:    db 'REALBOY: not a GB ROM', 0
rw_s_room:      db 'REALBOY: no room for ROM', 0
rw_s_read:      db 'REALBOY: read failed', 0

rw_ablines:
    dw rw_ab1, rw_ab2, rw_ab3, rw_ab4, rw_ab5, rw_ab6, rw_ab7, 0
rw_ab1:         db 'RealBoy', 0
rw_ab2:         db 'a Game Boy for os8088', 0
rw_ab3:         db 0
rw_ab4:         db 'Arrows, X = A, Z = B', 0
rw_ab5:         db 'Enter = Start', 0
rw_ab6:         db 'Space = Select', 0
rw_ab7:         db 'F1 = speed', 0

%include "rbdefs.inc"
%include "rbsys.inc"
%include "rbppu.inc"

%define OS88UI_ABOUT
%define OS88UI_NOBTN
%define OS88UI_ABDISMISS
%include "os88ui.inc"

; THE PART TABLE (SPEC.md 20.12.3): the core, compressed on the disk, and the
; view, a zeroed carve that costs no disk at all
OS88_PARTS_BEGIN 3
    OS88_PART OP_SEG, OP_COMP                   ; 0  the core's first half
    OS88_PART OP_ASSET, OP_COMP                 ; 1  ...and its second: one
                                                ;    part is at most 65,024
                                                ;    bytes (SPEC.md 20.12.11)
    OS88_PART OP_ASSET, OP_ZERO, 64             ; 2  the view
OS88_PARTS_END
    align 2, db 0
    OS88_BSS OP_BSS + RW_BSS
    OS88_IMAGE_END
