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
; WHAT IS NOT HERE YET (the plan's waves 2-5): the virtual video BIOS
; answers the teletype, cursor, write, read, scroll and string calls and
; IGNORES a graphics mode set; Alt+Enter does not move a live program to the
; full screen; a program that writes B800 directly shows nothing in the
; window (DOS-WINDOWED-PLAN 4); INT 33h reports desktop coordinates.
; =============================================================================

%ifdef DVW

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
; dvw_walk - exchange (or, with [dvw_xop] = 1, COPY live -> block) the runs
; in:  IF = 0 (the caller's cli); out: nothing; every register preserved
;
; Five runs, and the list is the contract: IVT 00h (divide - a C runtime hooks
; it), 08h-09h (the two IRQs a program may chain), 10h-3Fh (the BIOS services
; it is given virtual ones of, and the whole DOS block); then the BDA's memory
; size word, its video block and its EGA rows. ONE routine for both directions
; is what makes them impossible to get out of step: an exchange is its own
; inverse.
; -----------------------------------------------------------------------------
dvw_walk:
    push ax
    push cx
    push si
    push di
    push ds
    push es
    push cs
    pop ds
    cld
    mov si, dvw_xblk
    xor ax, ax
    mov es, ax
    xor di, di                  ; 00h
    mov cx, 2
    call .run
    mov di, 0x08 * 4            ; 08h, 09h
    mov cx, 4
    call .run
    mov di, 0x10 * 4            ; 10h..3Fh
    mov cx, 0x30 * 2
    call .run
    mov ax, 0x40
    mov es, ax
    mov di, 0x13                ; INT 12h's source, which dos_hook_vectors
    mov cx, 1                   ; sets to the ARENA's top
    call .run
    mov di, 0x49                ; mode .. palette (30 bytes)
    mov cx, 15
    call .run
    mov di, 0x84                ; rows-1, char height, EGA info (6 bytes):
    mov cx, 3                   ; 008Ah onwards is the AT's floppy state
    call .run
    pop es
    pop ds
    pop di
    pop si
    pop cx
    pop ax
    ret
.run:
    mov ax, [es:di]
    cmp byte [dvw_xop], 0
    jne .cp
    xchg ax, [si]
    stosw
    jmp short .nx
.cp:
    mov [si], ax
    inc di
    inc di
.nx:
    inc si
    inc si
    loop .run
    ret

dvw_xin:                        ; IF = 0; preserves everything
    cmp byte [cs:dvw_in], 0
    jne .r
    call dvw_walk
    mov byte [cs:dvw_in], 1
.r:
    ret

dvw_xout:                       ; IF = 0; preserves everything
    cmp byte [cs:dvw_in], 0
    je .r
    call dvw_walk
    mov byte [cs:dvw_in], 0
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
    cli
    pop ds
    call dvw_xin
    pop ax
    or ax, ax
    jz .back
    mov ss, [cs:dvw_nss]
    mov sp, [cs:dvw_nsp]
.back:
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
    mov byte [dvw_kill], 0
    mov byte [dvw_closeq], 0
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
    mov byte [dvw_xop], 1
    call dvw_walk                   ; the block = the live table, so every
    mov byte [dvw_xop], 0           ; vector we do not own starts the same
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
    cli
    call dvw_xout
    sti
    mov word [dos_hkv + DHK_SNAP], dos_snap
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
 %error "dvw_bdat must be exactly the 36 bytes dvw_walk exchanges"
%endif

; -----------------------------------------------------------------------------
; dvw_int10 - the virtual video BIOS, onto con_scr (DOS-WINDOWED-PLAN 3.3)
; -----------------------------------------------------------------------------
dvw_int10:
    sti
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
    pop ax
    jmp .out

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
    jmp far [cs:dvw_xblk + DVW_XB_V16]  ; the shift state is the machine's
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
    call dvw_serve
    call OSAPI_GFX_LOCK
    call dos_con_draw
    call OSAPI_GFX_UNLOCK
    cmp byte [dvw_done], 0
    je .r
    mov byte [dvw_done], 0
    mov byte [dvw_run], 0
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
