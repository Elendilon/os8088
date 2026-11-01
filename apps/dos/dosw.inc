; =============================================================================
; os8088 - apps/dos/dosw.inc
;
; **A DOS PROGRAM IN ITS WINDOW, LIVE** (docs/plans/DOS-WINDOWED-PLAN.md wave 1,
; SPEC.md 96.54). The bracket (96.2) hands a program the whole machine and the
; desktop stands still behind it. This runs the program on the instance's own
; WORKER instead, so the scheduler pre-empts it like any other task: its INT
; 21h output lands in the console band as it is printed, and the rest of the
; desktop - and other DOS windows - go on running.
;
; **NOT ONE KERNEL BYTE.** Everything a pre-empted DOS program needs that the
; kernel does not give a worker is here, and it rests on one kernel fact,
; SPEC.md 8.1.2.2: ONLY IRQ0 FALLS INTO `sch_switch`. So while this instance's
; task holds the CPU - and only then - its own world is in the interrupt table:
;
;   * the INT 21h family, a virtual video BIOS (10h), a virtual keyboard
;     BIOS (16h) fed from the window's keys, a refusing 13h - and IVT 08h, so
;     the timer interrupt arrives HERE first (`dvw_irq0`);
;   * the BDA's video block, so a C runtime reading 0040:0049 sees mode 3 and
;     80 columns and not the desktop's graphics mode.
;
; `dvw_irq0` moves a foreign SS (the program's stack, or the core's) onto the
; worker's own LOW_SEG slice, EXCHANGES the instance's world OUT, and calls
; the kernel's own int 08h - which may switch tasks. The switch saves the
; whole frame, including this stub's return, so when this task is resumed it
; comes back through the stub, which exchanges the world IN again. Every
; VOLUNTARY way off the CPU is a call this file makes (`dvw_nap`), and it
; exchanges out first. So the invariant is exact: **an instance's vectors are
; in the IVT exactly while its own task runs**, every other task sees the
; desktop's, and a teardown at any moment needs no cleanup at all.
;
; **IVT 08h AND 09h ARE EXCHANGED, NOT REFUSED.** A program that hooks the
; timer or the keyboard through AH=25h and chains - Microsoft Works does both
; - then sees its own handler run on every IRQ during its own slices and
; never during anyone else's. One that does NOT chain 08h stops the machine,
; exactly as it would wedge any other multitasker of the period.
;
; A worker may not touch a file (SPEC.md 20.6 rule 7), so every `dos_be` door
; that reaches the disk is POSTED to the UI task (`dvw_post`), which runs it
; through the very routine the bracket uses, on its own stack. 96.4.1.1's
; test decides which: `DBE_HERE` and `DBE_VKIND` are table reads and stay.
;
; WHAT IS NOT HERE: a lone Hercules's second page is never switched on for a
; capture (96.54.6); a program that reprograms the desktop card's 6845 itself
; is not repaired (96.54.7); and the vector set is not narrowed, so a window
; costs a CPU-bound program ~12% (96.54.3). The mouse is doswm.inc's
; (96.54.4), Alt+Enter and the shunt dvw_fsmain's (96.54.1), captures and
; TopView dvw_capt's (96.54.5-6).
; =============================================================================

%ifdef DVW

DVWC_TV     equ 1               ; [dvw_cmode]: TopView's buffer is con_scr
DVWC_SEG    equ 2               ; ...the other card's text RAM is captured
DVWC_HP     equ 3               ; ...a lone Hercules's page 1 is WATCHED
DVWC_EVERY  equ 3               ; a capture pass every 4th tick (mask)

DVW_GAP     equ 96              ; the IRQ0 stub's frames go this far below the
                                ; gate's own frame top ([dos_dstk]), so a
                                ; program-side tick never lands on a gate
                                ; frame. Only a CALLBACK (INT 33h's event
                                ; handler, wave 5) can have both live at once

; --- the exchange block's layout (`dvw_walk` writes it in this order) -------
DVW_XB_V10  equ 12              ; vector 10h's slot: 00h (4), 08h (4), 09h (4)
DVW_XB_V16  equ DVW_XB_V10 + (0x16 - 0x10) * 4
DVW_XB_BDA  equ (2 + 4 + 0x30 * 2) * 2  ; 204: 0040:0013's word, then...
DVW_XB_VID  equ DVW_XB_BDA + 2  ; ...0040:0049..0066 (30), 0040:0084..0089 (6)
DVW_XB_SIZE equ DVW_XB_VID + 36

; -----------------------------------------------------------------------------
; dvw_copy - one direction of one world: the runs, as `rep movsw`
; in:  BX = a block (dvw_xblk, the program's; dvw_xdsk, the desktop's)
;      DL = 0 GET (live -> block), 1 PUT (block -> live); IF = 0
; out: nothing; every register preserved
;
; Six runs, and the list is the contract: IVT 00h (divide - a C runtime hooks
; it), 08h-09h (the two IRQs a program may chain), 10h-3Fh (the BIOS services
; it is given virtual ones of, and the whole DOS block); then the BDA's memory
; size word, its video block and its EGA rows (0040:008Ah on is the AT's
; floppy state, which is the kernel's).
;
; **TWO BLOCKS AND COPIES, NOT ONE BLOCK AND AN EXCHANGE** (SPEC.md 96.54.3).
; It was one routine walking a word at a time - read, `xchg`, store, and a
; test of a mode byte on every word - which an exchange needs, being its own
; inverse. MEASURED: 15.3% of every sample of a windowed CPU-bound program
; landed in that loop, and the program ran at 81.1% of its bracketed speed.
; Two `rep movsw` per direction is the same 121 words at a fraction of the
; clocks, for one more block of bss; IN takes the desktop's copy first and
; OUT puts it back, so nothing the desktop holds can drift in between - no
; desktop code runs while the world is in.
; -----------------------------------------------------------------------------
dvw_runs:
    dw 0x0000, 0x00 * 4, 2          ; 00h
    dw 0x0000, 0x08 * 4, 4          ; 08h, 09h
    dw 0x0000, 0x10 * 4, 0x30 * 2   ; 10h..3Fh
    dw 0x0040, 0x0013, 1            ; INT 12h's source (dos_hook_vectors')
    dw 0x0040, 0x0049, 15           ; mode .. palette
    dw 0x0040, 0x0084, 3            ; rows-1, char height, EGA info
    dw 0, 0, 0
dvw_copy:
    push ax
    push bx
    push cx
    push si
    push di
    push bp
    push ds
    push es
    cld
    mov bp, dvw_runs
.r:
    mov cx, [cs:bp + 4]
    jcxz .done
    mov ax, [cs:bp]
    or dl, dl
    jnz .put
    mov ds, ax                      ; GET: DS:SI the live run, ES:DI ours
    mov si, [cs:bp + 2]
    push cs
    pop es
    mov di, bx
    jmp short .mv
.put:
    mov es, ax                      ; PUT: DS:SI ours, ES:DI the live run
    mov di, [cs:bp + 2]
    push cs
    pop ds
    mov si, bx
.mv:
    add bx, cx
    add bx, cx
    rep movsw
    add bp, 6
    jmp short .r
.done:
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

dvw_xin:                        ; IF = 0; preserves everything
    cmp byte [cs:dvw_in], 0
    jne .r
    push bx
    push dx
    mov bx, dvw_xdsk            ; the desktop's world, kept...
    xor dl, dl
    call dvw_copy
    mov bx, dvw_xblk            ; ...and the program's, put
    inc dx
    call dvw_copy
    pop dx
    pop bx
    mov byte [cs:dvw_in], 1
    cmp byte [cs:dvw_fs], 0     ; (not on the full screen: the card is in
    jne .r                      ; TEXT there, and 3B8h = 0Ah is graphics)
    cmp byte [cs:dvw_chp], 0    ; A LONE HERCULES'S PAGE 1 (96.54.6.1): its
    je .r                       ; decode allowed again, a mode set or an
    push ax                     ; unblank having put 3BFh back to 1 while
    mov al, 3                   ; the world was out
    call dvw_hpage
    pop ax
.r:
    ret

; dvw_hpage - 3BFh = AL, then 3B8h = the desktop's own 0Ah (96.54.6.1).
; The mode register is written again because a card may latch its decode
; there (MartyPC's re-derives its memory mask on 3B8h and nowhere else), and
; 0Ah is what dvw_vguard writes anyway: graphics, page 0 SHOWN, video on.
; Preserves all but AL and flags
dvw_hpage:
    push dx
    mov dx, 0x3BF
    out dx, al
    mov dl, 0xB8
    mov al, 0x0A
    out dx, al
    pop dx
    ret

dvw_xout:                       ; IF = 0; preserves everything
    cmp byte [cs:dvw_in], 0
    je .r
    push bx
    push dx
    mov bx, dvw_xblk            ; the program's world, kept...
    xor dl, dl
    call dvw_copy
    mov bx, dvw_xdsk            ; ...and the desktop's, put back
    inc dx
    call dvw_copy
    pop dx
    pop bx
    mov byte [cs:dvw_in], 0
    call dvw_vguard
.r:
    ret

; -----------------------------------------------------------------------------
; dvw_vguard - put the DESKTOP card's mode register back (SPEC.md 96.54.7)
; in:  IF = 0, the world out; out: every register preserved
;
; **A PROGRAM MAY WRITE A CARD'S PORTS, AND AN 8086 CANNOT STOP IT.** Measured
; with Microsoft Works: its blink setting writes the same byte to BOTH mode
; registers, 3B8h and 3D8h, and to the attribute controller at 3C0h - so on
; a Hercules desktop bit 1 drops, the card falls to TEXT, and the desktop's
; graphics framebuffer is shown as characters until something sets a mode.
; Works touches no 6845 register, so the mode register is the whole repair,
; and it is written each time the world goes out: one OUT on a Hercules or a
; CGA, three on a planar card, against a register the program may have
; written in the slice that just ended. A clobber shows for at most a tick.
; Never on the full screen, where the card is the program's.
; -----------------------------------------------------------------------------
dvw_vguard:
    cmp byte [cs:dvw_fs], 0
    jne .r
    push ax
    push dx
    mov al, [cs:dvw_dkind]
    cmp al, VID_HERC
    je .herc
    cmp al, VID_CGA
    je .cga
    cmp al, VID_VGA
    je .planar
    cmp al, VID_EGA
    jne .out                        ; VESA: its own driver's business
.planar:
    mov dx, 0x3DA                   ; reset the AC's flip-flop to INDEX
    in al, dx
    mov dx, 0x3C0
    mov al, 0x30                    ; register 10h, palette address source on
    out dx, al
    mov al, 0x01                    ; mode control: graphics, no blink - mode
    out dx, al                      ; 12h's and mode 10h's alike
    jmp short .out
.herc:
    mov dx, 0x3B8
    mov al, 0x0A                    ; graphics, page 0, video on: what
    out dx, al                      ; vid_unblank_kind writes
    jmp short .out
.cga:
    mov dx, 0x3D8
    mov al, [cs:dvw_xdsk + DVW_XB_VID + 0x1C]  ; 0040:0065, the DESKTOP'S
    out dx, al                      ; 3D8h as its mode set left it
.out:
    pop dx
    pop ax
.r:
    ret

; -----------------------------------------------------------------------------
; dvw_irq0 - IVT 08h while this instance runs (the file header's whole design)
; -----------------------------------------------------------------------------
dvw_irq0:
    mov [cs:dvw_tax], ax
    mov ax, ss
    cmp ax, [cs:dvw_lss]
    je .low
    mov [cs:dvw_fss], ax        ; a FOREIGN stack - the program's, or a
    mov [cs:dvw_fsp], sp        ; child's: onto the worker's own slice, below
    mov ax, [cs:dvw_lss]        ; the gate's frame top, where the kernel's
    mov ss, ax                  ; scheduler can park it. IF is 0 from the
    mov sp, [cs:dos_dstk]       ; gate to the iret, so SS and SP move as a
    sub sp, DVW_GAP             ; pair with nothing able to land between
    mov ax, 1
    jmp short .go
.low:
    xor ax, ax
.go:
    push ax                     ; 1 = this frame moved off a foreign stack
    mov ax, [cs:dvw_tax]
    call dvw_xout               ; the desktop's world, sch_isr back at 08h
    call dvw_cpace              ; a capture is owed its pass (96.54.6)
    cmp byte [cs:dvw_dirty], 0
    je .clean
    mov byte [cs:dvw_dirty], 0  ; **THE PAINT IS POSTED FROM HERE**: once a
    push bx                     ; tick, whatever the program printed, so a
    push ds                     ; chatty program costs the band 18 repaints
    push cs                     ; a second at most and a quiet one none.
    pop ds                      ; OSAPI_WM_WAKE is ISR-safe and coalesces
    mov bx, [dos_win]
    call OSAPI_WM_WAKE
    pop ds
    pop bx
.clean:
    pushf
    call far [cs:dvw_k08]       ; the kernel's own tick: it may switch away,
                                ; and resuming this task irets HERE (IF = 0)
    cmp byte [cs:dvw_frz], 0    ; **FROZEN** (SPEC.md 96.54.1): the world
    je .live                    ; stays out and the task sleeps here until
    call dvw_park               ; Alt+Enter thaws it or a close kills it
.live:
    call dvw_xin
    mov [cs:dvw_tax], ax
    pop ax
    or ax, ax
    jz .ret
    mov ss, [cs:dvw_fss]
    mov sp, [cs:dvw_fsp]
    cmp byte [cs:dvw_kill], 0   ; **THE WINDOW IS CLOSING**: the program
    je .ret                     ; leaves through DOS's own terminate, so its
    push bp                     ; files are swept and closed (96.52) - the
    mov bp, sp                  ; interrupted CS:IP becomes dvw_kexit's.
    mov word [bp+2], dvw_kexit  ; Only from program code: in a handler the
    mov [bp+4], cs              ; next tick out of it does this
    pop bp
.ret:
    mov ax, [cs:dvw_tax]
    iret

dvw_kexit:
    mov ax, 0x4CFF
    int 0x21

; -----------------------------------------------------------------------------
; dvw_nap - give up the CPU with the instance's world OUT
; in:  AX = 0 to yield, else ticks to sleep; any stack; out: every register
; and the flags preserved
; -----------------------------------------------------------------------------
dvw_nap:
    pushf
    cli
    push ax                     ; the argument, on the CALLER's stack
    mov ax, ss
    cmp ax, [cs:dvw_lss]
    je .low
    mov [cs:dvw_nss], ax        ; foreign: the scheduler wants LOW_SEG, and so
    mov [cs:dvw_nsp], sp        ; does every OSAPI cell (os88api.inc's head)
    mov ax, [cs:dvw_lss]
    mov ss, ax
    mov sp, [cs:dos_dstk]
    sub sp, DVW_GAP
    mov ax, 1
    jmp short .go
.low:
    xor ax, ax
.go:
    push ax
    call dvw_xout
    call dvw_cpace
    push ds
    push cs
    pop ds
    cmp byte [dvw_dirty], 0         ; **AND THE PAINT IS POSTED HERE TOO**:
    je .clean                       ; dvw_irq0 posts it only when a tick lands
    mov byte [dvw_dirty], 0         ; on the program, and a program that
    push bx                         ; prints its question and then waits for
    mov bx, [dos_win]               ; the answer spends every tick asleep in
    call OSAPI_WM_WAKE              ; here - so its question reached the band
    pop bx                          ; only when something else repainted the
.clean:                             ; window (reported off Prince of Persia's
    sti                             ; installer: "it updates after a drag")
    cmp word [dvw_narg], 0      ; read back through our own cell: the
    je .yield                   ; argument is on the other stack now
    mov ax, [dvw_narg]
    call OSAPI_TASK_SLEEP
    jmp short .woke
.yield:
    call OSAPI_TASK_YIELD
.woke:
    cmp byte [dvw_frz], 0       ; the other way off the CPU parks too, so a
    je .nofrz                   ; program frozen inside a key wait or a
    call dvw_park               ; posted door is held as surely as one in
.nofrz:                         ; its own code
    cli
    pop ds
    call dvw_xin
    pop ax
    or ax, ax
    jz .back
    mov ss, [cs:dvw_nss]
    mov sp, [cs:dvw_nsp]
.back:
    call dwm_kick               ; the mouse ticks it slept through (96.54.4)
    pop ax
    popf
    ret

dvw_nap0:                       ; the two shapes every caller wants
    mov word [cs:dvw_narg], 0
    jmp dvw_nap
dvw_nap1:
    mov word [cs:dvw_narg], 1
    jmp dvw_nap

; -----------------------------------------------------------------------------
; dvw_park - sleep, world OUT, while [dvw_frz] stands (SPEC.md 96.54.1)
; in:  LOW_SEG stack, the world out; out: IF = 0, every register preserved
; [dvw_parked] is what the UI task waits on before it reads the program's
; screen, so nothing the program does can land between the read and the thaw.
; -----------------------------------------------------------------------------
dvw_park:
    push ax
    push ds
    push cs
    pop ds
    mov byte [dvw_parked], 1
    sti
.p:
    cmp byte [dvw_kill], 0          ; a close thaws it: the kill is heard on
    jne .go                         ; the way back to the program
    cmp byte [dvw_frz], 0
    je .go
    mov ax, 1
    call OSAPI_TASK_SLEEP
    jmp short .p
.go:
    cli
    mov byte [dvw_parked], 0
    pop ds
    pop ax
    ret

; -----------------------------------------------------------------------------
; dvw_post - a door, run by the UI task (SPEC.md 20.6 rule 7)
; reached as `call dvw_post / dw dos_k_xxx` from dvw_betab's stubs, with the
; door's own registers; out: the door's registers and flags
;
; **THREE STATES AND NOT TWO**: 1 posted, 2 being served, 0 done. A window
; closing while a request stands may only CANCEL one the UI task has not
; started - a served door is running OUR code on the UI task, and the
; instance teardown that follows a kill would free it under that task.
; -----------------------------------------------------------------------------
dvw_post:
    ; STKBALANCE-OK: the `pop ax` below takes the STUB's return - the address
    ; of the `dw` after its `call dvw_post` - as data, so both `ret`s return
    ; to whoever called the stub, one word above this routine's entry
    mov [cs:dvw_r_ax], ax
    pop ax                      ; the stub's return IS the address of its word
    push bx
    mov bx, ax
    mov ax, [cs:bx]
    mov [cs:dvw_rtgt], ax
    pop bx
    mov [cs:dvw_r_bx], bx
    mov [cs:dvw_r_cx], cx
    mov [cs:dvw_r_dx], dx
    mov [cs:dvw_r_si], si
    mov [cs:dvw_r_di], di
    mov [cs:dvw_r_bp], bp
    mov [cs:dvw_r_es], es
    mov [cs:dvw_r_ds], ds
    mov byte [cs:dvw_rq], 1
.wait:
    push ds
    push cs
    pop ds
    mov bx, [dos_win]
    call OSAPI_WM_WAKE          ; every pass: a full ring refuses one
    pop ds
    call dvw_nap0
    cmp byte [cs:dvw_rq], 0
    je .done
    cmp byte [cs:dvw_kill], 0
    je .wait
    pushf
    cli
    cmp byte [cs:dvw_rq], 1
    jne .busy
    mov byte [cs:dvw_rq], 0     ; cancelled before it started
    popf
    mov bx, [cs:dvw_r_bx]
    mov ax, 5                   ; DOS's ACCESS DENIED, as good as any:
    stc                         ; the program is about to be stopped
    ret
.busy:
    popf
    jmp short .wait
.done:
    mov ax, [cs:dvw_r_ax]
    mov bx, [cs:dvw_r_bx]
    mov cx, [cs:dvw_r_cx]
    mov dx, [cs:dvw_r_dx]
    mov si, [cs:dvw_r_si]
    mov di, [cs:dvw_r_di]
    mov bp, [cs:dvw_r_bp]
    mov es, [cs:dvw_r_es]
    mov ds, [cs:dvw_r_ds]
    push word [cs:dvw_r_fl]
    popf
    ret

; --- the windowed door table: dos_betab's order, posting all but two --------
%macro DVWP 1
    call dvw_post
    dw %1
%endmacro
dvw_betab:
    dw .goto, .read, .find, .rdat, .write
    dw .append, .delete, .dfree, .mkdir, .rmdir
    dw .xcaps, .xalloc, .xfree, .xcopy, .rename
    dw .copy, .move, .path, .vstat, .wrat
    dw dos_k_here, dos_k_vkind, .rseq, .wseq
.goto:   DVWP dos_k_goto
.read:   DVWP dos_k_read
.find:   DVWP dos_k_find
.rdat:   DVWP dos_k_rdat
.write:  DVWP dos_k_write
.append: DVWP dos_k_append
.delete: DVWP dos_k_delete
.dfree:  DVWP dos_k_dfree
.mkdir:  DVWP dos_k_mkdir
.rmdir:  DVWP dos_k_rmdir
.xcaps:  DVWP dos_k_xcaps
.xalloc: DVWP dos_k_xalloc
.xfree:  DVWP dos_k_xfree
.xcopy:  DVWP dos_k_xcopy
.rename: DVWP dos_k_rename
.copy:   DVWP dos_k_copy
.move:   DVWP dos_k_move
.path:   DVWP dos_k_path
.vstat:  DVWP dos_k_vstat
.wrat:   DVWP dos_k_wrat
.rseq:   DVWP dos_k_rseq
.wseq:   DVWP dos_k_wseq
%if ($ - dvw_betab) != DBE_NENT * 2 + 22 * 5
 %error "dvw_betab has drifted from DBE_NENT: every door in dos_betab needs a slot here, in the same order"
%endif

; -----------------------------------------------------------------------------
; dvw_serve - the UI task's half of dvw_post (from dos_wake, lock FREE)
; -----------------------------------------------------------------------------
dvw_serve:
    pushf
    cli
    cmp byte [dvw_rq], 1
    jne .no
    mov byte [dvw_rq], 2
    popf
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    mov ax, [dvw_r_ax]
    mov bx, [dvw_r_bx]
    mov cx, [dvw_r_cx]
    mov dx, [dvw_r_dx]
    mov si, [dvw_r_si]
    mov di, [dvw_r_di]
    mov bp, [dvw_r_bp]
    mov es, [dvw_r_es]
    mov ds, [dvw_r_ds]
    call word [cs:dvw_rtgt]
    pushf
    pop word [cs:dvw_r_fl]
    mov [cs:dvw_r_ax], ax
    mov [cs:dvw_r_bx], bx
    mov [cs:dvw_r_cx], cx
    mov [cs:dvw_r_dx], dx
    mov [cs:dvw_r_si], si
    mov [cs:dvw_r_di], di
    mov [cs:dvw_r_bp], bp
    mov [cs:dvw_r_es], es
    mov [cs:dvw_r_ds], ds
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    mov byte [dvw_rq], 0        ; LAST, after every answer is in place
    ret
.no:
    popf
    ret

; -----------------------------------------------------------------------------
; dvw_start - post the program to the worker (dos_run, UI task, lock FREE)
; out: CF=1 no worker could be had, and the caller takes the bracket instead
; -----------------------------------------------------------------------------
dvw_start:
    push ax
    push bx
    call OSAPI_GFX_LOCK             ; OSAPI_TASK_SPAWN wants it held
    cmp byte [dvw_spawn], 0
    jne .have
    mov ax, dvw_worker
    mov bx, [dos_win]
    call OSAPI_TASK_SPAWN
    jc .no
    mov byte [dvw_spawn], 1
    OS88_WORKER_RESTARTABLE_NOKEEP dvw_worker   ; its loop's top is a clean
.have:                              ; place to begin again: the state is here
    cmp byte [dos_page], DOS_PAGE_MAIN  ; **THE BAND IS THE MAIN PAGE'S**:
    je .onmain                      ; a run started from Setup (the Memory
    mov byte [dos_page], DOS_PAGE_MAIN  ; limit is there) would draw it over
    mov bx, [dos_win]               ; that page's fields. dos_swap wants the
    call dos_swap                   ; lock, which is held here
.onmain:
    mov byte [dvw_kill], 0
    mov byte [dvw_closeq], 0
    mov byte [dvw_fs], 0
    mov byte [dvw_fsreq], 0
    mov byte [dvw_frz], 0
    mov byte [dvw_gfx], 0
    mov byte [dvw_done], 0
    mov byte [dvw_kh], 0
    mov byte [dvw_kt], 0
    mov byte [dvw_run], 1
    mov byte [dvw_go], 1            ; LAST: the worker reads it lock-free
    call OSAPI_GFX_UNLOCK
    pop bx
    pop ax
    clc
    ret
.no:
    call OSAPI_GFX_UNLOCK
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; dvw_worker - the instance's one worker (SPEC.md 20.6): never returns
; -----------------------------------------------------------------------------
dvw_worker:
.loop:
    mov bx, [dos_win]
    call OSAPI_TASK_ALIVE
    cmp byte [dvw_go], 0
    je .idle
    mov byte [dvw_go], 0
    call dvw_runprog
    mov byte [dvw_done], 1
    mov bx, [dos_win]
    call OSAPI_WM_WAKE
    jmp short .loop
.idle:
    mov ax, 1
    call OSAPI_TASK_SLEEP
    jmp short .loop

; -----------------------------------------------------------------------------
; dvw_runprog - dos_fsx_main without the full screen, on the worker
;
; **NOTHING IS PUSHED BEFORE [dos_sv_sp] IS BANKED, AND THAT IS THE RETURN.**
; dos_terminate puts SP back to that bank and jumps to dos_prog_done, whose
; DHK_SNAP hook is dvw_fin below: it drops its own return into the core and
; `ret`s - which, with nothing pushed here, lands on this routine's caller.
; That is how the windowed run skips dos_restore_machine (a whole-IVT and
; BDA restore that is right for a bracket and would rewind a live desktop)
; without one byte of the core changing.
; -----------------------------------------------------------------------------
dvw_runprog:
    mov ax, ss
    mov [dvw_lss], ax
    call OSAPI_VIDEO                ; INT 33h's scale (dos_fsx_main's reason)
    mov [dos_vw], ax
    mov [dos_vh], bx
    call dos_m33_wall
    call dwm_start                  ; ...and the window's own (96.54.4)
    call dos_build_psp
    push ds                         ; the posting doors
    pop es
    mov si, dvw_betab
    mov di, dos_bevec
    mov cx, DBE_NENT
    cld
    rep movsw
    mov word [dos_hkv + DHK_SNAP], dvw_fin
    ; --- THE PROGRAM'S WORLD, PRIMED FROM THE DESKTOP'S ------------------------
    cli
    push bx
    push dx
    mov bx, dvw_xblk                ; the program's block = the live table,
    xor dl, dl                      ; so every vector we do not own starts
    call dvw_copy                   ; the same
    pop dx
    pop bx
    push ds
    pop es
    mov si, dvw_bdat                ; ...and the video block a text mode's
    mov di, dvw_xblk + DVW_XB_VID
    mov cx, 18
    rep movsw
    mov ax, [con_cy]                ; the cursor is the console's
    mov ah, al
    mov al, [con_cx]
    mov [dvw_xblk + DVW_XB_VID + 7], ax     ; 0040:0050, page 0
    mov [dvw_csview], cs            ; TopView's answer, and its update's test
    push ax
    push bx
    push cx
    push dx
    call OSAPI_VIDEO                ; DL = the desktop's kind, for dvw_vguard
    mov [dvw_dkind], dl
    pop dx
    pop cx
    pop bx
    pop ax
    mov byte [dvw_cmode], 0
    call dvw_cdetect                ; **A SCREEN THE WINDOW CAN READ**
    jc .nocap                       ; (96.54.6): the other card's text RAM
    mov al, DVWC_HP                 ; A LONE HERCULES'S PAGE 1 (96.54.6.1) is
    cmp byte [dvw_chp], 0           ; WATCHED, int 10h staying ours: mode 3
    jne .crtc                       ; at B800, the status port its own 3BAh
    mov al, DVWC_SEG                ; (a CGA's 3DAh reads FFh there)
    mov byte [dos_inbr], 1          ; DOS's teletype is the ROM's: one truth
    cmp word [dvw_cseg], 0xB000
    jne .seed
    mov byte [dvw_xblk + DVW_XB_VID], 7         ; mode 7 at B000, its CRTC
.crtc:
    mov word [dvw_xblk + DVW_XB_VID + 0x1A], 0x03B4
    cmp al, DVWC_HP
    je .copy
.seed:
    call dvw_cprog                  ; its 6845 RUNNING, or a snow-avoiding
.copy:                              ; writer waits for a retrace for ever
    mov [dvw_cmode], al
    push ds                         ; the console onto it, so the program's
    push es                         ; screen continues the session the way
    mov es, [dvw_cseg]              ; the bracket's seed does (96.34.4)
    mov si, con_scr
    xor di, di
    mov cx, CON_SCRSZ / 2
    rep movsw
    pop es
    pop ds
    cmp byte [dvw_cmode], DVWC_HP   ; ...and the page's row sums taken, so
    jne .nocap                      ; the probe knows what it seeded
    mov byte [dvw_hprow], 0
    xor bx, bx
.hsum:
    call dvw_hpsum
    push bx
    shl bx, 1
    mov [dvw_sums + bx], dx
    pop bx
    inc bx
    cmp bx, CON_ROWS
    jb .hsum
.nocap:
    xor ax, ax
    mov es, ax
    mov ax, [es:0x08 * 4]
    mov [dvw_k08], ax
    mov ax, [es:0x08 * 4 + 2]
    mov [dvw_k08 + 2], ax
    call dvw_xin
    mov word [es:0x08 * 4], dvw_irq0    ; ...and OURS, before anything below
    mov [es:0x08 * 4 + 2], cs           ; can `sti`: a tick with the DOS
    mov word [es:0x10 * 4], dvw_int10   ; block in and sch_isr still at 08h
    mov [es:0x10 * 4 + 2], cs           ; would leave it in for whoever ran
    mov word [es:0x13 * 4], dvw_int13   ; next
    mov [es:0x13 * 4 + 2], cs
    mov word [es:0x16 * 4], dvw_int16
    mov [es:0x16 * 4 + 2], cs
    call dos_hook_vectors           ; the DOS block, into the PROGRAM's table
    mov ax, [dos_arena]
    add ax, DOS_PSPP
    mov [dos_dtaseg], ax
    mov word [dos_dta], 0x80
    mov ax, [dos_dir]
    mov [dos_curdir], ax
    mov al, [dos_vol]
    call dos_drv_bank
    call dos_date_init
    mov ax, ss
    mov [dos_sv_ss], ax
    mov [dos_sv_sp], sp
    mov [dos_dstk], sp
    call dos_prog_enter             ; ...and away; back through dvw_fin

dvw_fin:                            ; DHK_SNAP, from dos_prog_done
    ; STKBALANCE-OK: dvw_runprog's header - the `add` drops the return into
    ; the core, so the `ret` is dvw_runprog's own, at [dos_sv_sp]
    add sp, 2                       ; not back into the core (dvw_runprog)
    cmp byte [dvw_fs], 0            ; ENDED ON THE FULL SCREEN: its last
    je .notfs                       ; screen is the console's, exactly as a
    call dos_snap                   ; bracketed run's (96.34) - with the world
    mov byte [dvw_cmode], 0         ; still in, the BDA is the program's - and
.notfs:                             ; NO capture pass may copy a stale card
                                    ; over it (the card's is torn down by
                                    ; dvw_wake, after the run's LAST pass)
    cli
    call dvw_xout
    sti
    mov word [dos_hkv + DHK_SNAP], dos_snap
    call dwm_stop                   ; the bracket's INT 33h hooks (96.54.4)
    call dos_be_bind

    ret

; the video block a mode-3 screen leaves in 0040:0049..0066, then 0084..0089
dvw_bdat:
    db 3                            ; 49 mode
    dw 80                           ; 4A columns
    dw 4096                         ; 4C page size
    dw 0                            ; 4E page offset
    times 8 dw 0                    ; 50 the eight cursors (page 0 patched)
    dw 0x0607                       ; 60 cursor shape
    db 0                            ; 62 active page
    dw 0x03D4                       ; 63 CRTC base
    db 0x29                         ; 65 mode register
    db 0x30                         ; 66 palette
    db 24                           ; 84 rows - 1
    dw 8                            ; 85 character height
    db 0, 0, 0                      ; 87..89 no EGA
%if ($ - dvw_bdat) != 36
 %error "dvw_bdat must be exactly the 36 bytes dvw_copy moves"
%endif

; -----------------------------------------------------------------------------
; dvw_int10 - the virtual video BIOS, onto con_scr (DOS-WINDOWED-PLAN 3.3)
; -----------------------------------------------------------------------------
dvw_int10:
    sti
    cmp ah, 0xFE                    ; **TOPVIEW'S PAIR** (SPEC.md 96.54.5),
    jae .tv                         ; in every mode: a program asks once
    cmp byte [cs:dvw_fs], 0         ; **FULL SCREEN** (SPEC.md 96.54.1): the
    jne .pass                       ; machine's own BIOS, on the machine's
    cmp byte [cs:dvw_cmode], DVWC_SEG   ; ...and the CAPTURE's (96.54.6): the
    jne .virt                       ; ROM writes the other card's text RAM,
    or ah, ah                       ; which the window copies - all but a mode
    jnz .pass                       ; set, which on a mono primary programs
    call dvw_cmset                  ; the WRONG CARD (39.19.4)
    jnc .cmdone
    jmp .shunt
.cmdone:
    iret
.virt:
    push ds
    push cs
    pop ds
    cmp ah, 0x0E
    je .tty
    cmp ah, 0x02
    je .setcur
    cmp ah, 0x03
    je .getcur
    cmp ah, 0x0F
    je .mode
    cmp ah, 0x09
    je .wca
    cmp ah, 0x0A
    je .wca
    cmp ah, 0x08
    je .rca
    cmp ah, 0x06
    je .scroll
    cmp ah, 0x07
    je .scroll
    cmp ah, 0x00
    je .setmode
    cmp ah, 0x13
    je .str
.out:
    pop ds
    iret

.tty:
    call con_write
    call dvw_cdone
    jmp short .out

.setcur:
    call dvw_setcur
    jmp short .out

.getcur:
    mov dh, [con_cy]
    mov dl, [con_cx]
    cmp dl, CON_COLS - 1
    jbe .gc
    mov dl, CON_COLS - 1
.gc:
    mov cx, 0x0607
    jmp short .out

.mode:
    mov ax, 0x5003                  ; 80 columns, mode 3
    xor bh, bh
    jmp short .out

.rca:
    push bx
    call con_celloff
    mov bx, ax
    mov ax, [con_scr + bx]
    pop bx
    jmp short .out

.wca:                               ; AH 09h = char + BL attribute, 0Ah = char
    push ax                         ; alone; CX of them, the cursor stays
    push bx
    push cx
    push dx
    push di
    jcxz .wdone
    mov dh, ah
    mov dl, bl
    push ax
    call con_celloff
    mov di, ax
    pop ax
.wnext:
    cmp di, CON_SCRSZ
    jae .wmark
    mov [con_scr + di], al
    cmp dh, 0x09
    jne .wskip
    mov [con_scr + di + 1], dl
.wskip:
    inc di
    inc di
    loop .wnext
.wmark:
    call con_celloff
    shr ax, 1                       ; the first cell...
    shr di, 1
    dec di                          ; ...and the last one written
    mov bx, di
    cmp bx, ax
    jb .wdone                       ; the cursor was past the last cell
    call con_markcells
    mov byte [dvw_dirty], 1
.wdone:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    jmp .out

.scroll:
    call dvw_scroll
    jmp .out

.setmode:
    push ax
    and al, 0x7F
    cmp al, 3
    jbe .text
    cmp al, 7
    jne .gfx                        ; a graphics mode: wave 3's full screen
.text:
    mov byte [con_attr], 0x07
    call con_clear
    mov byte [dvw_dirty], 1
    call dvw_bcur
.gfx:
    pop ax                          ; **A GRAPHICS MODE IS THE ONE THING THE
    pop ds                          ; WINDOW CAN SEE COMING** (SPEC.md
.shunt:
    call dvw_shunt                  ; 96.54.1): to the full screen first, then
    jnc .pass                       ; the mode set, so not a pixel of it lands
    iret                            ; anywhere else. Refused: no mode set
.pass:
    or ah, ah                       ; a mode set is remembered: a GRAPHICS
    jnz .rom                        ; program may not come back to the window
    push ax                         ; (there is no text to bring)
    and al, 0x7F
    mov ah, 1
    cmp al, 3
    jbe .txt
    cmp al, 7
    je .txt
    jmp short .setg
.txt:
    xor ah, ah
.setg:
    mov [cs:dvw_gfx], ah
    pop ax
.rom:
    jmp far [cs:dvw_xdsk + DVW_XB_V10]  ; the ROM's, the world being in

.tv:                                ; FEh: ES:DI = the buffer the program
    jne .tvupd                      ; meant to write -> the one it SHOULD.
    cmp byte [cs:dvw_fs], 0         ; On the full screen and in a capture
    jne .tvsame                     ; that IS the screen, so ES:DI comes back
    cmp byte [cs:dvw_cmode], DVWC_SEG   ; as it went, which is also what it
    je .tvsame                      ; reads with no multitasker at all
    mov byte [cs:dvw_cmode], DVWC_TV
    push cs                         ; ...in the window it is the console's
    pop es                          ; own cells, already text VRAM's layout
    mov di, con_scr                 ; (96.34): writes land where the band
.tvsame:                            ; is drawn from, and the row sums find
    iret                            ; them
.tvupd:                             ; FFh: ES:DI, CX cells changed
    cmp byte [cs:dvw_cmode], DVWC_TV
    jne .tvsame
    push ax
    mov ax, es
    cmp ax, [cs:dvw_csview]         ; ...ours: CS, banked at the run's start
    pop ax
    jne .tvsame
    call dvw_tvmark
    iret

.str:
    call dvw_str
    jmp .out

; --- dvw_cdone - a cursor that moved: the BDA hears, the band is owed -------
dvw_cdone:
    mov byte [dvw_dirty], 1
    ; fall through
dvw_bcur:                           ; 0040:0050 = the console's cursor
    push ax
    push es
    mov ax, 0x40
    mov es, ax
    mov ah, [con_cy]
    mov al, [con_cx]
    cmp al, CON_COLS - 1
    jbe .c
    mov al, CON_COLS - 1
.c:
    mov [es:0x50], ax
    pop es
    pop ax
    ret

; --- dvw_setcur - DH = row, DL = column, clamped -----------------------------
dvw_setcur:
    push ax
    call con_markcur                ; the row it LEFT (con_markcur's rule)
    mov al, dl
    xor ah, ah
    cmp al, CON_COLS - 1
    jbe .x
    mov al, CON_COLS - 1
.x:
    mov [con_cx], ax
    mov al, dh
    cmp al, CON_ROWS - 1
    jbe .y
    mov al, CON_ROWS - 1
.y:
    mov [con_cy], ax
    mov byte [con_pwrap], 0
    call con_markcur
    call dvw_cdone
    pop ax
    ret

; -----------------------------------------------------------------------------
; dvw_scroll - AH 06h up / 07h down, AL lines (0 = clear), BH the fill
; attribute, CH,CL the top left, DH,DL the bottom right
; -----------------------------------------------------------------------------
dvw_scroll:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    cmp dh, CON_ROWS - 1
    jbe .h
    mov dh, CON_ROWS - 1
.h:
    cmp dl, CON_COLS - 1
    jbe .w
    mov dl, CON_COLS - 1
.w:
    cmp ch, dh
    ja .out
    cmp cl, dl
    ja .out
    mov [dvw_sc_t], cx              ; CL left, CH top
    mov [dvw_sc_b], dx              ; DL right, DH bottom
    mov [dvw_sc_a], bh
    mov [dvw_sc_up], ah
    mov bl, dh
    sub bl, ch
    inc bl                          ; BL = the window's height
    or al, al
    jz .all
    cmp al, bl
    jbe .n
.all:
    mov al, bl
.n:
    mov [dvw_sc_n], al
    cld
    xor bx, bx
.row:                               ; BL = 0..height-1, the row's ORDER
    mov al, [dvw_sc_t + 1]          ; top
    cmp byte [dvw_sc_up], 0x06
    je .uprow
    mov al, [dvw_sc_b + 1]          ; down: bottom upwards
    sub al, bl
    mov ah, al
    sub ah, [dvw_sc_n]              ; the source row, above
    jmp short .have
.uprow:
    add al, bl
    mov ah, al
    add ah, [dvw_sc_n]              ; the source row, below
.have:                              ; AL = the destination row, AH = source
    push bx
    mov dl, al
    call .addr                      ; DI = the destination
    mov di, si
    mov cl, [dvw_sc_b]
    sub cl, [dvw_sc_t]
    inc cl
    xor ch, ch                      ; CX = the window's width
    mov al, ah
    cmp byte [dvw_sc_up], 0x06
    je .srcup
    cmp al, [dvw_sc_t + 1]
    jl .blank                       ; above the window: no source
    jmp short .copy
.srcup:
    cmp al, [dvw_sc_b + 1]
    jg .blank                       ; below the window: no source
.copy:
    call .addr                      ; SI = the source
    rep movsw
    jmp short .marked
.blank:
    mov al, ' '
    mov ah, [dvw_sc_a]
    rep stosw
.marked:
    mov bl, dl
    xor bh, bh
    call con_mark
    pop bx
    inc bl
    mov al, [dvw_sc_b + 1]
    sub al, [dvw_sc_t + 1]
    inc al
    cmp bl, al
    jb .row
    mov byte [dvw_dirty], 1
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.addr:                              ; AL = a row -> SI = its window's left cell
    push ax
    push dx
    xor ah, ah
    mov dx, CON_COLS * 2
    mul dx
    mov dl, [dvw_sc_t]
    xor dh, dh
    add ax, dx
    add ax, dx
    add ax, con_scr
    mov si, ax
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dvw_str - AH 13h: AL bit 0 = move the cursor, bit 1 = the string carries
; its attributes; BL the attribute, CX the length, DH,DL where, ES:BP it
; -----------------------------------------------------------------------------
dvw_str:
    push ax
    push bx
    push cx
    push dx
    push si
    push bp
    mov si, [con_cx]
    push si
    mov si, [con_cy]
    push si
    mov ah, [con_attr]
    push ax
    call dvw_setcur
    jcxz .done
.next:
    mov ah, al                      ; AH = the mode, kept
    mov al, [es:bp]
    inc bp
    test ah, 2
    jz .plain
    mov bl, [es:bp]
    inc bp
.plain:
    mov [con_attr], bl
    push ax
    call con_write
    pop ax
    mov al, ah
    loop .next
.done:
    pop ax
    mov [con_attr], ah              ; the current attribute is the console's
    pop si                          ; cy
    pop dx                          ; cx (DX: it is spent)
    test al, 1
    jnz .keep
    mov [con_cy], si                ; bit 0 clear: the cursor goes back
    mov [con_cx], dx
.keep:
    call dvw_cdone
    pop bp
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dvw_int13 - a program's own disk BIOS call, refused (DOS-WINDOWED-PLAN 3.4):
; a raw transfer may not share the drive with the file layer mid-operation
; -----------------------------------------------------------------------------
dvw_int13:
    sti
    mov ah, 0x80                    ; TIMEOUT - no drive answered
    stc
    retf 2

; -----------------------------------------------------------------------------
; dvw_int16 - the virtual keyboard BIOS, off the window's keys
;
; **A WAIT SLEEPS AND SO DOES A POLL** (DOS-WINDOWED-PLAN 3.6): AH=00h with
; nothing typed costs the machine a tick of sleep, and every eighth empty
; AH=01h sleeps one too - a program spinning on "key ready?" is the
; commonest way one DOS program would otherwise eat the desktop's whole time.
; It was a YIELD and that was measured wrong: with nothing else ready a yield
; returns at once, so a waiting program spent its whole slice exchanging its
; world in and out.
; -----------------------------------------------------------------------------
dvw_int16:
    sti
    cmp ah, 0x10                    ; the enhanced three are the plain three
    jb .fn
    cmp ah, 0x12
    ja .none
    sub ah, 0x10
.fn:
    or ah, ah
    jz .get
    cmp ah, 1
    je .peek
    cmp ah, 2
    je .rom
.none:
    iret
.rom:
    jmp far [cs:dvw_xdsk + DVW_XB_V16]  ; the shift state is the machine's
.get:
    call dvw_kpop
    jnz .got
    cmp byte [cs:dvw_kill], 0
    jne .kill
    call dvw_nap1
    jmp short .get
.got:
    iret
.kill:
    jmp dvw_kexit                   ; from the program's own int: its frame
.peek:                              ; is the one terminate unwinds
    push bp
    mov bp, sp
    call dvw_kpeek
    jnz .pk
    cmp byte [cs:dvw_kill], 0       ; **THE CLOSE IS HEARD HERE TOO**: a
    jne .pkill                      ; program waiting in INT 21h's own key
    inc byte [cs:dvw_poll]          ; read polls from the GATE's stack, where
    test byte [cs:dvw_poll], 7      ; dvw_irq0 never sees a foreign SS
    jnz .pz
    call dvw_nap1                   ; A TICK, NOT A YIELD: a yield with
.pz:                                ; nothing else ready comes straight back,
                                    ; and the poll became a loop of exchanges
                                    ; - measured, the CPU was in dvw_walk at
                                    ; every sample of a program waiting for
                                    ; a key
    or byte [bp+6], 0x40            ; ZF = 1: nothing waiting
    pop bp
    iret
.pk:
    and byte [bp+6], 0xBF           ; ZF = 0, AX = the key, not consumed
    pop bp
    iret
.pkill:
    pop bp
    jmp dvw_kexit                   ; INT 21h AH=4Ch from inside the gate is
                                    ; a nested call; terminate puts SS:SP
                                    ; back to [dos_sv_sp] and drops them all

; --- the ring: 16 keys, filled by dos_key (UI task) and drained here --------
dvw_kput:                           ; AX = a key; a full ring drops it
    push bx
    pushf
    cli
    mov bl, [cs:dvw_kt]
    mov bh, bl
    inc bh
    and bh, 15
    cmp bh, [cs:dvw_kh]
    je .full
    xor bh, bh
    shl bx, 1
    mov [cs:dvw_kq + bx], ax
    mov bl, [cs:dvw_kt]
    inc bl
    and bl, 15
    mov [cs:dvw_kt], bl
.full:
    popf
    pop bx
    ret

dvw_kpeek:                          ; ZF = 1 empty, else AX = the next key
    push bx
    mov bl, [cs:dvw_kh]
    cmp bl, [cs:dvw_kt]
    je .r
    xor bh, bh
    shl bx, 1
    mov ax, [cs:dvw_kq + bx]
    or bx, 1                        ; ZF = 0
.r:
    pop bx
    ret

dvw_kpop:                           ; ZF = 1 empty, else AX = it, taken
    push bx
    pushf
    cli
    call dvw_kpeek
    jz .e
    mov bl, [cs:dvw_kh]
    inc bl
    and bl, 15
    mov [cs:dvw_kh], bl
    popf
    or bl, 0x80                     ; ZF = 0
    pop bx
    ret
.e:
    popf
    xor bx, bx                      ; ZF = 1
    pop bx
    ret

; -----------------------------------------------------------------------------
; dvw_wake - dos_wake's windowed arm: serve, paint, and finish
; -----------------------------------------------------------------------------
dvw_wake:
    cmp byte [dvw_fsreq], 0         ; Alt+Enter, or a graphics mode set
    je .nofs
    call dvw_fsenter
.nofs:
    call dvw_serve
    call dvw_capt                   ; what the program wrote itself (96.54.5-6)
    call OSAPI_GFX_LOCK
    call dos_con_draw
    call OSAPI_GFX_UNLOCK
    cmp byte [dvw_done], 0
    je .r
    mov byte [dvw_done], 0
    mov byte [dvw_run], 0
    cmp byte [dvw_chp], 0           ; THE CAPTURE TORN DOWN, its last pass
    je .nopage                      ; taken above: a Hercules's page 1 has
    mov al, 1                       ; its decode off again, as vid_setmode
    call dvw_hpage                  ; leaves it (the page was never shown)...
    mov byte [dvw_chp], 0
.nopage:
    cmp word [dvw_cseg], 0          ; ...the other card dark again, as the
    je .nocard                      ; kernel's Single mode leaves it
    call dvw_cblank
    mov word [dvw_cseg], 0
.nocard:
    mov byte [dvw_cmode], 0
    mov byte [dos_inbr], 0          ; a capture's teletype was the ROM's
    mov byte [dos_state], DST_RAN   ; the bracket's own tail (dos_run .ran
    mov dx, [dos_arena]             ; through .out), which the post skipped
    or dx, dx
    jz .na
    call OSAPI_MEM_FREE
    mov word [dos_arena], 0
.na:
    mov byte [dos_cpw], 0
    call dn_shut
    call dos_pkt_shut
    call dos_drv_back
    call dos_cache_free
    cmp byte [dvw_closeq], 0        ; the close dvw_onclose refused, now
    je .said                        ; that nothing of the run is left
    mov byte [dvw_closeq], 0
    mov bx, [dos_win]
    call OSAPI_WM_CLOSE             ; deferred to the next UI pass: return
    ret
.said:
    call dos_con_ended
    call dos_repaint
.r:
    ret

; -----------------------------------------------------------------------------
; dvw_shunt - ask for the full screen, and wait until it is up (worker side)
; out: CF=0 the program is on the full screen; CF=1 it was refused, or the
; window is closing. Any stack; every register preserved
; -----------------------------------------------------------------------------
dvw_shunt:
    push bx
    push ds
    push cs
    pop ds
    mov byte [dvw_fsreq], 1
.w:
    mov bx, [dos_win]
    call OSAPI_WM_WAKE              ; every pass, as dvw_post does
    call dvw_nap1
    cmp byte [dvw_fs], 0
    jne .up
    cmp byte [dvw_kill], 0
    jne .no
    cmp byte [dvw_fsreq], 0
    jne .w
.no:
    pop ds
    pop bx
    stc
    ret
.up:
    pop ds
    pop bx
    clc
    ret

; -----------------------------------------------------------------------------
; dvw_fsenter - the full screen, with the worker KEPT (dvw_wake, lock FREE)
; -----------------------------------------------------------------------------
dvw_fsenter:
    push ax
    push bx
    push cx
    call OSAPI_GFX_LOCK
    mov ax, dvw_fsmain
    mov bx, [dos_win]
    mov cx, FSXF_KEEPWORKER         ; the program goes on running in here
    call OSAPI_FSX_RUN
    pushf
    call OSAPI_GFX_UNLOCK
    popf
    jnc .ok
    mov byte [dvw_fsreq], 0         ; refused: dvw_shunt hears no
.ok:
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dvw_fsmain - the bracket's proc: the UI task's half of a live full screen
;
; **THE PROGRAM IS NOT STOPPED TO GET HERE.** The worker is FSXF_KEEPWORKER's,
; so it runs straight through the mode set; the virtual video BIOS passes to
; the ROM from the moment [dvw_fs] is set, and its keys come from the ROM's
; buffer through this loop into the same ring the window fills. The doors are
; served from here too - the UI task is inside this proc for the whole
; bracket, so nothing else would.
;
; ALT+ENTER BACK is text modes only: a program that set a graphics mode has no
; text to bring. Going back PARKS the program first ([dvw_frz], and waits for
; [dvw_parked]), so its screen is read with nothing able to write it, and
; leaves it frozen in the window on the screen it last drew - DESQview's
; shape for a program that draws its own screen, which on an 8088 is the only
; honest one (docs/plans/DOS-WINDOWED-PLAN.md 4).
; -----------------------------------------------------------------------------
dvw_fsmain:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov bx, [dos_win]
    call OSAPI_FSX_CAPS             ; the DISPLAY's kind (dos_fsx's reason)
    mov [con_tkind], dl
    push ds
    pop es
    mov di, dos_fsi
    mov al, FSXM_TEXT80
    call OSAPI_FSX_MODE
    jc .refused
    mov ax, [dos_fsi + FSI_SEG]     ; ...and the window's screen onto it:
    mov [con_tseg], ax              ; dos_fsx_con's seed
    mov byte [con_tcur], 0xFF
    call con_tx_ice
    mov byte [con_thint], 0xFF
    call con_markall
    call dos_fsx_owed
    mov dh, [con_cy]                ; the ROM's cursor where the window's is,
    mov dl, [con_cx]                ; so the program's next teletype lands
    cmp dl, CON_COLS - 1            ; under what it already wrote
    jbe .cx
    mov dl, CON_COLS - 1
.cx:
    xor bh, bh
    mov ah, 0x02
    int 0x10
    cli                             ; **THE PROGRAM'S VIDEO BLOCK BECOMES THE
    push ds                         ; MACHINE'S**: its ROM calls read the BDA,
    push ds                         ; and the window's mode-3 story is wrong
    pop es                          ; on a Hercules (mode 7 at B000). The
    mov ax, 0x40                    ; world is out, so the block holds the
    mov ds, ax                      ; program's half
    mov si, 0x49
    mov di, dvw_xblk + DVW_XB_VID
    mov cx, 15
    cld
    rep movsw
    mov si, 0x84
    mov cx, 3
    rep movsw
    pop ds
    mov byte [dos_aedn], 1          ; the Alt+Enter that brought us here is
    mov byte [dos_inbr], 1          ; still held: SEEDED DOWN (96.33.5.1). And
    mov byte [dvw_fs], 1            ; DOS's teletype goes to the ROM now
    mov byte [dvw_fsreq], 0
    mov byte [dvw_frz], 0           ; ...and a FROZEN program thaws onto it
    sti
.loop:
    call dvw_serve
    cmp byte [dvw_done], 0
    jne .out                        ; it ended: dvw_fin has the screen
    call dos_fsx_ae
    jc .back
.key:
    mov ah, 1                       ; the ROM's keys, the world being out on
    int 0x16                        ; this task, into the program's ring
    jz .idle
    xor ah, ah
    int 0x16
    call dvw_kput
    jmp short .key
.idle:
    mov al, FSXW_TICK
    call OSAPI_FSX_WAIT
    jmp short .loop
.back:
    cmp byte [dvw_gfx], 0
    jne .loop                       ; graphics: there is no text to bring back
    mov byte [dvw_frz], 1
.park:
    call dvw_serve                  ; it may be waiting on a door to get there
    cmp byte [dvw_done], 0
    jne .out
    cmp byte [dvw_parked], 0
    jne .parked
    mov al, FSXW_TICK
    call OSAPI_FSX_WAIT
    jmp short .park
.parked:
    cli                             ; the PROGRAM's BDA and screen, read with
    call dvw_xin                    ; its world swapped in for one copy and
    call dos_snap                   ; out again - dos_snap is memory only, so
    call dvw_xout                   ; nothing can take an interrupt through a
    sti                             ; half-swapped table
.out:
    mov byte [dos_inbr], 0          ; ...the console's teletype again, unless
    cmp byte [dvw_cmode], DVWC_SEG  ; the window is a capture, where the ROM's
    jne .inbr                       ; is the only one (96.54.6)
    mov byte [dos_inbr], 1
.inbr:
    mov byte [dvw_fs], 0
    call con_markall                ; the band is owed whole on the way back
    jmp short .ret
.refused:
    mov byte [dvw_fsreq], 0
.ret:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

;
; =============================================================================
; WHAT THE PROGRAM WRITES ITSELF (SPEC.md 96.54.5, 96.54.6)
; =============================================================================
; Two ways a window can see a screen it did not draw through its own BIOS:
;
;   DVWC_TV   TopView's int 10h AH=FEh - the program ASKS where to write, and
;             is told con_scr. Its writes land in the band's own cells; a
;             row sum per row finds the ones that changed, and AH=FFh marks
;             them at once for a program that says so.
;   DVWC_SEG  the OTHER CARD'S text RAM: on a desktop with a second card that
;             is not part of it, that card's B800 or B000 is RAM nobody
;             shows. The program is told mode 3 or 7 to match and writes
;             there - directly or through the ROM - and the window copies
;             the rows that differ. Microsoft Works is the program this is
;             for: it asks the mode and then writes the screen itself.
;
; A pass runs on the UI task from dvw_wake, every fourth tick the program
; holds the CPU or sleeps (dvw_cpace), and never on the full screen or a
; frozen program, whose console is the captured glass.

; --- dvw_cpace - post the pass, every DVWC_EVERY+1 ticks (any context) -------
dvw_cpace:
    cmp byte [cs:dvw_cmode], 0
    je .r
    inc byte [cs:dvw_ctick]
    test byte [cs:dvw_ctick], DVWC_EVERY
    jnz .r
    cmp byte [cs:dvw_cmode], DVWC_HP    ; **A PAGE NOBODY HAS WRITTEN IS
    jne .post                       ; PROBED HERE** (96.54.6.1), one row, and
    cmp byte [cs:dvw_hprow], 0xFF   ; the UI task is woken only when it moved
    je .post                        ; - posting the pass to look was 1.9 of a
    cmp byte [cs:dvw_fs], 0         ; (and not while the full screen or a
    jne .r                          ; freeze owns the console: dvw_capt
    cmp byte [cs:dvw_frz], 0        ; would not look either)
    jne .r
    push ax                         ; spinning program's 88 points
    push bx
    push cx
    push dx
    push si
    pushf
    cld
    mov bl, [cs:dvw_hprow]
    xor bh, bh
    call dvw_hpsum
    shl bx, 1
    cmp [cs:dvw_sums + bx], dx
    jne .moved
    shr bx, 1                       ; unmoved: the next row, next time
    inc bx
    cmp bl, CON_ROWS
    jb .nx
    xor bl, bl
.nx:
    mov [cs:dvw_hprow], bl
    jmp short .pend
.moved:
    mov byte [cs:dvw_dirty], 1      ; (popf below is the CALLER's flags)
.pend:
    popf
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
.r:
    ret
.post:
    mov byte [cs:dvw_dirty], 1      ; the paint post below is the pass's door
    ret

; -----------------------------------------------------------------------------
; dvw_cdetect - is there a screen to capture? (worker, IF = 0, world OUT)
; out: CF=0 and [dvw_cseg] = B800h or B000h; CF=1 none. Every register kept
;
; THE CANDIDATE is the card the desktop is NOT on: B800 under a Hercules,
; B000 under anything else. It must be RAM (a pattern reads back), it must not
; be the desktop's own framebuffer seen twice (the pattern leaves the other
; segment's word alone - MartyPC's lone Hercules decodes B800 onto B000, and a
; capture there would read the desktop's pixels and let the program write
; them), and the desktop must not be EXTENDED onto that card (OSAPI_FSX_CAPS
; with BX = 2 asks about display 1, and CF = 1 is "there is none", SPEC.md
; 53.1.2) - in Extend, that RAM is the second monitor's desktop.
; -----------------------------------------------------------------------------
dvw_cdetect:
    push ax
    push bx
    push cx
    push dx
    push si
    push ds
    call OSAPI_VIDEO                ; DL = the primary's kind
    mov si, 0xB800                  ; under a Hercules, the CGA's
    mov cx, 0xB000
    cmp dl, VID_HERC
    je .cand
    xchg si, cx                     ; under the rest, the mono card's
.cand:
    mov byte [dvw_chp], 0
    mov bx, 2
    call OSAPI_FSX_CAPS             ; CF = 0: a second display IS desktop
    jnc .no
.try:
    mov ds, cx                      ; the OTHER segment's word, which a
    mov dx, [0]                     ; mirror would move
    mov ds, si
    mov bx, [0]                     ; ...and the candidate's own, kept
    mov word [0], 0x5AA5
    cmp word [0], 0x5AA5
    jne .back
    mov word [0], 0xA55A
    cmp word [0], 0xA55A
    jne .back
    mov ds, cx
    cmp [0], dx                     ; unmoved: two memories, not one
    mov ds, si
    mov [0], bx
    jne .miss
    push cs
    pop ds
    mov [dvw_cseg], si
    pop ds
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.back:
    mov [0], bx
.miss:
    push cs                         ; **NO CGA AT B800 UNDER A HERCULES: ITS
    pop ds                          ; OWN PAGE 1 IS** (96.54.6.1). 3BFh bit 1
    cmp si, 0xB800                  ; turns the second 32KB's decode on, which
    jne .no                         ; vid_setmode leaves off only because a
    mov al, 3                       ; CGA would answer there too - and the
    xor byte [dvw_chp], 1           ; test above says none does. Page 0 stays
    jnz .page                       ; what is SHOWN; the same test then
    mov al, 1                       ; decides, so a card that mirrors (or
.page:                              ; lacks the page) is refused, the decode
    pushf                           ; put back
    call dvw_hpage
    popf
    jnz .try
.no:
    pop ds
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; dvw_cprog / dvw_cblank - the capture card's 6845, up for text and back dark
;
; **A CARD NOBODY PROGRAMMED HAS NO RETRACE** - MEASURED with Microsoft Works:
; its screen writer waits for the CGA's status port (3DAh) to show a retrace
; before EVERY character, the snow-avoidance loop of the period, and on a
; second card that Single mode only BLANKS (vid_blank_kind writes the mode
; register and nothing else, SPEC.md 39.19) the 6845 was never given a
; timing: the bits never move and Works waited for ever with nothing drawn.
; So the capture programs the card for 80x25 text and turns its video on -
; the second monitor shows the program too, which is the period's own look -
; and dvw_cblank turns the video off again at the run's end, the one bit the
; kernel's blank writes. Its 6845 is left timed for text: Extend's bring-up is
; a full mode set (vid_disp_init), so nothing reads the old timing again.
; -----------------------------------------------------------------------------
dvw_crtc_cga:   db 0x71, 0x50, 0x5A, 0x0A, 0x1F, 0x06, 0x19, 0x1C
                db 0x02, 0x07, 0x06, 0x07, 0x00, 0x00, 0x00, 0x00
dvw_crtc_mono:  db 0x61, 0x50, 0x52, 0x0F, 0x19, 0x06, 0x19, 0x19
                db 0x02, 0x0D, 0x0B, 0x0C, 0x00, 0x00, 0x00, 0x00
dvw_cprog:
    push ax
    push cx
    push dx
    push si
    mov si, dvw_crtc_cga
    mov dx, 0x3D8
    mov al, 0x21                    ; text, 80 columns, video OFF while timed
    cmp word [cs:dvw_cseg], 0xB000
    jne .mode
    mov si, dvw_crtc_mono
    mov dx, 0x3B8
    mov al, 0x20                    ; mono text, video off (3BFh stays 1:
.mode:                              ; graphics ALLOWED is not graphics ON)
    out dx, al
    push ax
    sub dx, 4                       ; 3D4h / 3B4h
    xor ah, ah                      ; AH = the register
    mov cx, 16
.reg:
    mov al, ah
    out dx, al
    inc dx
    mov al, [cs:si]
    out dx, al
    dec dx
    inc si
    inc ah
    loop .reg
    pop ax
    add dx, 4
    or al, 0x08                     ; ...and the video ON
    out dx, al
    pop si
    pop dx
    pop cx
    pop ax
    ret

dvw_cblank:
    push ax
    push dx
    mov dx, 0x3D8
    mov al, 0x21
    cmp word [cs:dvw_cseg], 0xB000
    jne .out
    mov dx, 0x3B8
    mov al, 0x20
.out:
    out dx, al                      ; video OFF, the one bit vid_blank_kind's
    pop dx                          ; own blank clears
    pop ax
    ret

; --- dvw_cmset - int 10h AH=00h inside a capture (program context, world in) -
; A TEXT mode clears the captured screen and homes the cursor, and is NOT
; passed to the ROM: on a mono primary the ROM's mode set is equipment-driven
; and programs the desktop's own card (SPEC.md 39.19.4). CF=1 a graphics mode,
; which the caller shunts to the full screen like any other.
dvw_cmset:
    push ax
    and al, 0x7F
    cmp al, 3
    jbe .text
    cmp al, 7
    je .text
    pop ax
    stc
    ret
.text:
    push cx
    push di
    push es
    mov es, [cs:dvw_cseg]
    xor di, di
    mov ax, 0x0720
    mov cx, CON_SCRSZ / 2
    cld
    rep stosw
    mov ax, 0x40
    mov es, ax
    mov word [es:0x50], 0           ; page 0's cursor home
    pop es
    pop di
    pop cx
    pop ax
    clc
    ret

; --- dvw_tvmark - TopView AH=FFh: ES:DI, CX cells changed in con_scr ---------
dvw_tvmark:
    push ax
    push bx
    push cx
    push dx
    push ds
    push cs
    pop ds
    mov ax, di
    sub ax, con_scr
    jb .out
    shr ax, 1                       ; the first cell
    jcxz .out
    mov bx, ax
    add bx, cx
    dec bx                          ; ...and the last
    cmp bx, CON_SCRSZ / 2 - 1
    jbe .have
    mov bx, CON_SCRSZ / 2 - 1
.have:
    cmp ax, bx
    ja .out
    call con_markcells
    mov byte [dvw_dirty], 1
.out:
    pop ds
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dvw_capt - one capture pass (dvw_wake: UI task, lock free)
; -----------------------------------------------------------------------------
dvw_capt:
    cmp byte [dvw_cmode], 0
    je .r
    cmp byte [dvw_fs], 0            ; the full screen owns the glass, and a
    jne .r                          ; FROZEN program's console is its capture
    cmp byte [dvw_frz], 0
    jne .r
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    cld
    push ds
    pop es
    xor bx, bx                      ; BX = the row
    cmp byte [dvw_cmode], DVWC_SEG
    je .seg
    cmp byte [dvw_cmode], DVWC_HP
    je .hp
.sum:                               ; --- TopView: a sum per row -----------
    mov si, bx
    mov ax, CON_COLS * 2
    mul si
    mov si, ax
    add si, con_scr
    call dvw_rsum
    mov si, bx
    shl si, 1
    cmp [dvw_sums + si], dx
    je .snext
    mov [dvw_sums + si], dx
    call con_mark
.snext:
    inc bx
    cmp bx, CON_ROWS
    jb .sum
    jmp .hpend
.hp:                                ; --- a lone Hercules's page 1 --------
    mov al, [dvw_hprow]             ; (96.54.6.1): ONE row a pass while
    cmp al, 0xFF                    ; nothing has written it - int 10h is
    je .hpall                       ; ours, so only a DIRECT writer can -
    mov bl, al                      ; and every row once one has (the
    call dvw_hprw                   ; tick's probe has already advanced
    ; past every unmoved row, so the one it stopped on is the one that moved)
    jnc .hpend
    mov byte [dvw_hprow], 0xFF
    jmp short .hpend
.hpall:
    call dvw_hprw
    inc bx
    cmp bx, CON_ROWS
    jb .hpall
.hpend:
    jmp .done
.seg:                               ; --- the other card: copy what moved --
    push ds
    mov ax, CON_COLS * 2
    mul bx
    mov si, ax                      ; DS:SI the card's row...
    mov di, ax
    add di, con_scr                 ; ...ES:DI ours
    mov ds, [cs:dvw_cseg]
    mov cx, CON_COLS
    push si
    push di
    repe cmpsw
    pop di
    pop si
    je .same
    mov cx, CON_COLS
    rep movsw
    pop ds
    call con_mark
    jmp short .gnext
.same:
    pop ds
.gnext:
    inc bx
    cmp bx, CON_ROWS
    jb .seg
    mov ax, [dvw_xblk + DVW_XB_VID + 7]     ; the program's cursor, its BDA
    xor dh, dh                              ; being in the block while the
    mov dl, al                              ; world is out
    cmp dl, CON_COLS - 1
    jbe .cx
    mov dl, CON_COLS - 1
.cx:
    mov al, ah
    xor ah, ah
    cmp al, CON_ROWS - 1
    jbe .cy
    mov al, CON_ROWS - 1
.cy:
    cmp dx, [con_cx]
    jne .mv
    cmp ax, [con_cy]
    je .done
.mv:
    call con_markcur
    mov [con_cx], dx
    mov [con_cy], ax
    mov byte [con_pwrap], 0
    call con_markcur
.done:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
.r:
    ret

; dvw_rsum - DX = the sum of the row at DS:SI, order-sensitive (a swap is a
; change); SI past it. Clobbers AX, CX
dvw_rsum:
    xor dx, dx
    mov cx, CON_COLS
.add:
    lodsw
    add dx, ax
    rol dx, 1
    loop .add
    ret

; dvw_hpsum - DX = the sum of page 1's row BX, SI its offset there.
; Clobbers AX, CX
dvw_hpsum:
    push ds
    mov ax, CON_COLS * 2
    mul bx
    mov si, ax
    mov ds, [cs:dvw_cseg]
    call dvw_rsum
    pop ds
    sub si, CON_COLS * 2
    ret

; dvw_hprw - page 1's row BX: CF=1 it moved, and it is copied into the
; console and marked. Keeps BX; clobbers AX, CX, DX, SI, DI
dvw_hprw:
    call dvw_hpsum
    mov di, bx
    shl di, 1
    cmp [dvw_sums + di], dx
    je .same                        ; (CF = 0)
    mov [dvw_sums + di], dx
    mov di, si
    add di, con_scr
    push ds
    mov ds, [cs:dvw_cseg]
    mov cx, CON_COLS
    rep movsw
    pop ds
    call con_mark
    stc
.same:
    ret

; --- dvw_onclose - OSAPI_WM_ONCLOSE: a running program is stopped, not kept --
; **THE CLOSE IS REFUSED, AND FINISHED BY US** (SPEC.md 75.1's own pattern).
; Letting it through hides the window and leaves the worker to free the region
; at its next OSAPI_TASK_ALIVE - which it reaches the moment the stopped
; program has gone, while the UI task may still be INSIDE dvw_wake finishing
; the run. Measured: the region was freed under it and the machine ran off
; into the heap. So the program is stopped, dvw_wake ends the run on the UI
; task as it ends any run, and only then asks for the close it owes - after
; which the worker dies from its idle loop, where nothing of ours is running
; anywhere else.
dvw_onclose:
    cmp byte [dvw_run], 0
    je .ok
    mov byte [dvw_kill], 1          ; the worker's next tick terminates it...
    mov byte [dvw_closeq], 1        ; ...and dvw_wake closes us afterwards
    stc
    ret
.ok:
    clc
    ret

%endif                              ; DVW
