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
RW_PGBUD        equ 250             ; PAGES: the core's budget when a flip's
                                    ;   window is near (x2 recompiled)
RW_PGPER        equ 19982           ; ...the refresh's period, 527 lines of
                                    ;   31.78 us, in 838 ns counts, until it
                                    ;   is measured (rw_pgsync)
RW_PGW1         equ 3700            ; ...its window, in counts BEFORE the
RW_PGW0         equ 1000            ;   retrace (410): from line 312, under
                                    ;   the speed line (287 to 308, where
                                    ;   rw_pgtry's look would see a display),
                                    ;   to line 383 (the blanking at 400)
RW_PGSPIN       equ 1800            ; ...spun for when it is that near and
                                    ;   nothing else is to do
RW_PGTGT        equ 2800            ; ...a sized run's END aimed this many
                                    ;   counts before the retrace: 900 into
                                    ;   the window, 1,800 to spare
RW_PGRATE0      equ 107             ; ...the core's M-cycles in 256 counts
                                    ;   until measured: ~500 a millisecond
RW_PGRC         equ 60              ; ...and the retrace timed again after
                                    ;   that many flips
RW_FSTXTP       equ 2               ; PAGES: the speed line's row in the
                                    ;   split's region (slot 0, rw_pgcrtc)
RW_TOFF         equ 6528            ; PAGES: the canvas's state in [rw_pseg]
                                    ;   (rb_tseg), past the 42-byte lines and
                                    ;   the pages' owed bytes
RW_FSSKIP       equ 4               ; frames run undrawn at most, behind
RW_FSX          equ 0               ; the picture's byte column and first row:
RW_FSY          equ 0               ;   the top left of the CRTC's window
RW_FSTXT        equ 146             ; the speed line's row, inside the window
RW_FSVGA        equ 0               ; rw_fskind: the writers
RW_FSHERC       equ 1
RW_FSCGA        equ 2
RW_HX           equ 25              ; Hercules: the picture's byte column
RW_HY           equ 26              ;   (x = 200, 320 wide) and first row
RW_HTXT         equ 322             ;   (288 tall), and the speed line's
RW_CY           equ 28              ; CGA: the picture's first row (320 by
RW_CTXT         equ 182             ;   144), and the speed line's
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
    mov si, rw_it_sv0               ; Save and Load State: a game running
    mov dx, rw_it_ld0
    cmp byte [rw_state], 1
    jne .st
    mov si, rw_it_sv
    mov dx, rw_it_ld
.st:
    mov [rw_i_file + 2], si
    mov [rw_i_file + 4], dx
    mov si, rw_it_rec0              ; Record and Play Replay: a game, and
    mov dx, rw_it_ply0              ;   the other not running
    cmp byte [rw_state], 1
    jne .rp
    cmp byte [rw_rpmode], RPM_PLAY
    je .rpp
    mov si, rw_it_recs
    cmp byte [rw_rpmode], RPM_REC
    je .rp
    mov si, rw_it_rec
    mov dx, rw_it_ply
    jmp short .rp
.rpp:
    mov dx, rw_it_plys
.rp:
    mov [rw_i_file + 6], si
    mov [rw_i_file + 8], dx
    mov si, rw_it_fs0
    cmp byte [rw_state], 1
    jne .set
    call rw_fspick                  ; CF = 1: no mode we have a writer for
    jc .set
    mov si, rw_it_fs
.set:
    mov [rw_i_mach + 4], si
    mov si, rw_it_jit0              ; Recompiler: what it is now
    cmp word [rw_jitseg], 0
    je .j
    mov si, rw_it_jauto
    cmp byte [rw_jitmode], 0
    je .j
    mov si, rw_it_jon
    cmp byte [rw_jitmode], 1
    je .j
    mov si, rw_it_jst
    cmp byte [rw_jitmode], 3
    je .j
    mov si, rw_it_joff
.j:
    mov [rw_i_mach + 6], si
    mov si, rw_it_log0              ; Log: what it is now
    cmp byte [rw_logon], 0
    je .l
    mov si, rw_it_log1
.l:
    mov [rw_i_mach + 8], si
    mov si, rw_it_il0               ; Interlace: what it is now
    cmp byte [rb_ilace], 1
    jb .i
    mov si, rw_it_il1
    je .i
    mov si, rw_it_il2
    cmp byte [rb_ilace], 3
    jb .i
    mov si, rw_it_il3
.i:
    mov [rw_i_mach + 10], si
    mov si, rw_it_prfd              ; Profile: what it is now
    cmp byte [rw_286], 0
    je .p
    mov si, rw_it_prf0
    cmp byte [rw_prfon], 0
    je .p
    mov si, rw_it_prf1
.p:
    mov [rw_i_mach + 12], si
    mov si, rw_it_bigd              ; Cache: what it is now (a setting,
    cmp byte [rw_286], 0            ;   so before a game too)
    je .b
    mov si, rw_it_big0
    cmp byte [rw_big], 0
    je .b
    mov si, rw_it_big1
.b:
    mov [rw_i_mach + 14], si
    mov bl, [rw_speed]              ; Speed and Sound: what they are now
    xor bh, bh
    shl bx, 1
    mov si, [rw_spdit + bx]
    mov [rw_i_mach + 16], si
    mov bl, [rw_sndm]
    shl bx, 1
    mov si, [rw_sndit + bx]
    mov [rw_i_mach + 18], si
    pop si
    pop dx
    pop bx
    pop ax
    ret

; rw_fsenter - Machine > Full Screen, on the UI task with the lock held
rw_fsenter:
    cmp byte [rw_state], 1
    jne .r
    call rw_fspick                  ; AL = the writer
    jc .r                           ; greyed; a shortcut gets nothing either
    mov [rw_fskind], al
    call OSAPI_FONT_GLYPHS          ; DX:SI, AL first, AH last: copied now,
    call rw_fscopy                  ;   before the mode leaves the desktop's
    mov byte [rw_fsq], 1
.wait:
    cmp byte [rw_incore], 0         ; the worker out of the machine first
    je .go
    call rw_bserve                  ; (it may be waiting on us for a bank)
    call OSAPI_TASK_YIELD
    jmp short .wait
.go:
    mov byte [rw_pfmt], 0           ; the window's planes will not match the
                                    ;   frame the bracket leaves: the
                                    ;   restore's repaint paints white, and
                                    ;   the next draw starts from every line
    mov byte [rw_fsrate], 1
    mov byte [rw_fspan], 0          ; PAGES (rw_pgcrtc): VGA, a 286 or
    cmp byte [rw_fskind], RW_FSVGA  ;   better and the damage memory -
    jne .np                         ;   the composer's 42-byte lines
    cmp byte [rw_286], 0            ;   need it
    je .np
    cmp word [rb_dmgseg], 0
    je .np
    mov byte [rw_fspan], 1
.np:
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
    call rw_drawnow                 ; (on the window's clock again)
    mov al, RLE_FSOUT
    call rw_logevt
    mov byte [rw_fsq], 0
    cmp byte [rw_lflq], 0           ; F12 in the bracket: the log written
    je .r                           ;   now that a toast can be read
    mov byte [rw_lflq], 0
    jmp rw_logflush
.r:
    ret

; rw_fspick - the writer for this window's display: VGA mode 0Dh, else the
; Hercules page at 2x2, else CGA's 320x200 in four colours. AL = RW_FS*, or
; CF = 1 for none.
rw_fspick:
    push bx
    mov bx, [rw_win]
    call OSAPI_FSX_CAPS             ; AX = the modes this display can set
    pop bx
    test ax, 1 << FSXM_VGA0D
    jz .h
    mov al, RW_FSVGA
    clc
    ret
.h:
    test ax, 1 << FSXM_HERC
    jz .c
    mov al, RW_FSHERC
    clc
    ret
.c:
    test ax, 1 << FSXM_CGA320
    jz .no
    mov al, RW_FSCGA
    clc
    ret
.no:
    stc
    ret

; rw_fscopy - the kernel's glyph table kept for the bracket's text, which
; reads it where it is (a far pointer, not a 768-byte copy: memory is not a
; drawing slot). DX:SI = the table, AL = its first code. Our lines are
; ASCII, which every table the kernel answers holds.
rw_fscopy:
    mov [rw_fontp], si
    mov [rw_fontp + 2], dx
    mov [rw_font0], al
    ret

; rw_fshook - every rate period: a frame owed. AX = periods since the last.
rw_fshook:
    add [rw_fowed], ax
    add [rw_fsper], ax              ; (rw_clk's, for the log)
    ret

; rw_pgtry - PAGES: a flip that waits is written when the BEAM is in its
; window - after the page's last line (the split at 287) and before the
; blanking, where every card takes the start address and the pel panning
; together for the next frame (REALBOY-SPEC 15.4). Where the beam is comes
; from the CLOCK: a vertical retrace's start, timed once (rw_pgsync), and the
; refresh's period, measured - so a look costs a clock read, not a port
; read. It is the foreground's: between two runs of the core (rw_frame,
; which ends the run that reaches the window - rw_pgbud), during a draw
; (rb_lhook) and while it waits. The core runs with interrupts off, so no
; hook could. The window near: spun to. Kept: all
rw_pgtry:
    cmp byte [rw_pgpend], 0
    jne .go
    cmp byte [rw_pgrc], RW_PGRC     ; no flip waiting: the retrace timed
    jb .r                           ;   again when it is due and near
    push ax
    push bx
    push cx
    push dx
    call rw_pgph
    jc .x0
    mov bx, [rw_pgper]
    sub bx, ax
    cmp bx, 2400
    jae .x0
    call rw_pgsync
.x0:
    jmp .x
.go:
    push ax
    push bx
    push cx
    push dx
    call rw_pgph                    ; AX = the phase, after a retrace
    jc .cal
    mov bx, [rw_pgper]
    sub bx, ax                      ; BX = counts to the next one
    cmp bx, RW_PGW1
    ja .before
    cmp bx, RW_PGW0
    jae .look
    cmp byte [rw_pgrc], RW_PGRC     ; just past it, the retrace near: timed
    jb .x                           ;   again when it is due
    call rw_pgsync
    jmp .x
.before:
    cmp byte [rw_pgns], 0           ; (between two of rw_frame's runs: the
    jne .x                          ;   next is sized to end in it instead)
    sub bx, RW_PGW1                 ; near the window: to it
    cmp bx, RW_PGSPIN
    ja .x
.sp:
    call rw_pgph
    jc .cal
    mov bx, [rw_pgper]
    sub bx, ax
    cmp bx, RW_PGW1
    ja .sp
.look:
    mov dx, 3DAh                    ; the model checked on the port: the
    mov cx, 16                      ;   border is no display all line long,
.lk:                                ;   where a picture line shows it again
    in al, dx                       ;   inside 16 reads (its blanking is ~6
    test al, 1                      ;   us of 32)
    loopnz .lk
    jnz .flip
    cmp byte [rw_pgrc], 0           ; it disagrees: the model timed again -
    je .flip                        ;   unless it just was, and then the port
    call rw_pgsync                  ;   is the one wrong
    jmp short .x
.flip:
    mov dx, 3D4h
    mov bx, [rw_pgstart]
    mov al, 0Ch
    mov ah, bh
    out dx, ax
    mov al, 0Dh
    mov ah, bl
    out dx, ax
    mov dx, 3DAh
    in al, dx
    mov dx, 3C0h
    mov al, 33h                     ; AR13, the display left on
    out dx, al
    mov al, [rw_pgpan]
    out dx, al
    mov al, [rw_pgss]               ; THE STRIP: the line compare the page's
    cmp al, [rw_pglc]               ;   (REALBOY-SPEC 15.5.1), 2 x S - 1
    je .lc
    call rw_pglcw
.lc:
    mov al, [rw_pgnext]
    mov [rw_pgshow], al
    mov byte [rw_pgpend], 0
    cmp byte [rw_pgrc], 0FFh
    je .x
    inc byte [rw_pgrc]
    jmp short .x
.cal:
    call rw_pgsync                  ; no beam to go by: timed now (a
    jc .flip                        ;   frame at most, once) - and none at
.x:                                 ;   all, written anyway
    pop dx
    pop cx
    pop bx
    pop ax
.r:
    ret

; rw_pgtryd - rw_pgtry for the composer's line hook (rb_lhook): a flip that
; waits is written only when the beam is ALREADY in its window and the port
; agrees - never spun to, never timed again, so a draw spends nothing
; waiting on the beam. The field's log priced the spin at about 1.5 ms a
; flip when it was taken inside a draw. Kept: all
rw_pgtryd:
    cmp byte [rw_pgpend], 0
    je .r
    push ax
    push bx
    push cx
    push dx
    call rw_pgph
    jc .x
    mov bx, [rw_pgper]
    sub bx, ax
    cmp bx, RW_PGW1
    ja .x
    cmp bx, RW_PGW0
    jb .x
    mov dx, 3DAh                    ; (rw_pgtry's look, and on a
    mov cx, 16                      ;   disagreement nothing: the next look
.lk:                                ;   between two core runs times it)
    in al, dx
    test al, 1
    loopnz .lk
    jz .x
    jmp rw_pgtry.flip               ; (its tail pops the four)
.x:
    pop dx
    pop cx
    pop bx
    pop ax
.r:
    ret

; rw_pgph - AX = rw_clk's counts since the last vertical retrace began, on
; the beam's model; CF = 1: there is none. Clobbers DX
rw_pgph:
    cmp byte [rw_pgok], 0
    je .no
    call rw_clk
    sub ax, [rw_pgvs]
    sbb dx, [rw_pgvs + 2]
    cmp dx, [rw_pgper]
    jae .old
    div word [rw_pgper]
    mov ax, dx
    clc
    ret
.old:
    mov byte [rw_pgok], 0
.no:
    stc
    ret

; rw_pgsync - the beam's model: spun until a vertical retrace begins (port
; 3DAh bit 3, two lines long), its time kept, and the refresh's period taken
; from the one before, averaged; CF = 1 none seen in ~65,000 reads
rw_pgsync:
    push ax
    push bx
    push cx
    push dx
    mov dx, 3DAh
    mov cx, 0FFFFh
.w0:
    in al, dx                       ; out of one...
    test al, 8
    loopnz .w0
    jnz .no
    mov cx, 0FFFFh
.w1:
    in al, dx                       ; ...into the next
    test al, 8
    loopz .w1
    jz .no
    call rw_clk                     ; DX:AX = its start
    cmp byte [rw_pgok], 0
    je .first
    push ax
    push dx
    sub ax, [rw_pgvs]               ; since the one before: n periods
    sbb dx, [rw_pgvs + 2]
    cmp dx, [rw_pgper]
    jae .skip
    mov bx, ax
    mov cx, dx
    div word [rw_pgper]             ; AX = whole periods, DX = the rest
    mov bx, [rw_pgper]
    shr bx, 1
    cmp dx, bx
    jb .n
    inc ax                          ; (rounded)
.n:
    cmp ax, 1
    jb .skip
    cmp ax, 255
    ja .skip
    mov bx, ax                      ; the span / n...
    pop dx
    pop ax
    push ax
    push dx
    sub ax, [rw_pgvs]
    sbb dx, [rw_pgvs + 2]
    div bx
    cmp ax, RW_PGPER - 200          ; (a plausible one only)
    jb .skip
    cmp ax, RW_PGPER + 200
    ja .skip
    sub ax, [rw_pgper]              ; ...averaged, a quarter of the
    sar ax, 1                       ;   difference at a time (three of the
    sar ax, 1                       ;   old and one new is past 16 bits)
    add [rw_pgper], ax
.skip:
    pop dx
    pop ax
.first:
    mov [rw_pgvs], ax
    mov [rw_pgvs + 2], dx
    mov byte [rw_pgok], 1
    mov byte [rw_pgrc], 0
    clc
    jmp short .r
.no:
    stc
.r:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rw_budx - AX = a run's budget, [rw_budget] - twice it with the recompiler
; on: it is the IRQ latency, and recompiled 2000 M-cycles are ~2 ms on a 286,
; so 4000 are still inside a 1200-baud mouse's 8 ms; half the runs, and of
; rb_run's rb_sched and event exit
rw_budx:
    mov ax, [rw_budget]
    push es
    mov es, [rb_viewseg]
    cmp byte [es:S_JITON], 0
    pop es
    je .r
    shl ax, 1
.r:
    ret

; rw_pgbud - AX = the core's budget while a flip waits: sized to END in the
; flip's window - RW_PGTGT counts before the retrace - at the rate the core
; has been running ([rw_pgrate], M-cycles in 256 counts, measured on these
; runs by rw_pgrun), at most rw_budx's. So the foreground never spins for
; the beam: a run that ends early is followed by a shorter one, and one that
; ends late shows its frame a refresh later and spent nothing. The beam not
; known, RW_PGBUD. The run's start and budget kept for rw_pgrun
rw_pgbud:
    push bx
    push cx
    push dx
    mov word [rw_pgbn], 0
    call rw_pgph
    jc .near
    mov bx, [rw_pgper]
    sub bx, ax                      ; BX = counts to the retrace
    sub bx, RW_PGTGT                ; ...to the run's end
    ja .k
    add bx, [rw_pgper]              ; (past it: the next one's)
.k:
    mov ax, [rw_pgrate]
    or ax, ax
    jnz .m
    call rw_budx                    ; (not measured: the old rate, twice
    mov cx, ax                      ;   recompiled)
    mov ax, RW_PGRATE0
    cmp cx, [rw_budget]
    je .m
    shl ax, 1
.m:
    mul bx                          ; DX:AX = M-cycles x 256
    mov al, ah                      ; / 256
    mov ah, dl
    or dh, dh
    jnz .cap
    mov cx, ax
    call rw_budx                    ; at most a run's own
    cmp cx, ax
    jae .bn
    mov ax, cx
    cmp ax, 32
    jae .bn
    mov ax, 32
    jmp short .bn
.cap:
    call rw_budx
.bn:
    mov [rw_pgbn], ax
    push ax
    call rw_clk
    mov [rw_pgbt0], ax
    mov [rw_pgbt0 + 2], dx
    pop ax
    jmp short .r
.near:
    call rw_budx
    cmp ax, RW_PGBUD
    jbe .r
    mov ax, RW_PGBUD
.r:
    pop dx
    pop cx
    pop bx
    ret

; rw_pgrun - after rb_run, AL = how it ended: a run rw_pgbud sized that ran
; its whole budget gives the core's rate, a quarter of the way at a time
; ([rw_pgrate]). Kept: all
rw_pgrun:
    cmp word [rw_pgbn], 0
    je .r
    cmp al, RBX_BUDGET
    jne .z
    push ax
    push bx
    push cx
    push dx
    call rw_clk
    sub ax, [rw_pgbt0]
    sbb dx, [rw_pgbt0 + 2]
    or dx, dx
    jnz .x
    cmp ax, 128                     ; (too short to time)
    jb .x
    mov bx, ax                      ; BX = the run's counts
    mov ax, [rw_pgbn]
    mov dl, ah                      ; DX:AX = its budget x 256
    xor dh, dh
    mov ah, al
    xor al, al
    cmp dx, bx                      ; (the quotient past 16 bits: no)
    jae .x
    div bx                          ; AX = M-cycles in 256 counts
    mov bx, [rw_pgrate]
    or bx, bx
    jz .set
    sub ax, bx
    sar ax, 1
    sar ax, 1
    add ax, bx
.set:
    mov [rw_pgrate], ax
.x:
    pop dx
    pop cx
    pop bx
    pop ax
.z:
    mov word [rw_pgbn], 0
.r:
    ret

; rw_fsmain - the bracket. DS = CS = ours, ES = KERNEL_SEG, SI = the window.
rw_fsmain:
    OS88_ALTENTER_SEED              ; the Alt+Enter that got us here is held
    push ds
    pop es
    mov bl, [rw_fskind]
    xor bh, bh
    mov al, [rw_fsmodes + bx]
    mov di, rw_fsi
    call OSAPI_FSX_MODE
    jc .r
    cmp byte [rw_fskind], RW_FSVGA
    jne .mono
    call rw_fsdac
    call rw_fscrtc
    mov word [rw_fstxto], RW_FSTXT * 40 + RW_FSX
    mov word [rw_fsstr], 40
    cmp byte [rw_fspan], 0
    jne .pg
    call rw_fsframe
    call rw_dmgfull                 ; every line of the first frame
    jmp short .in
.pg:
    call rw_pgcrtc                  ; PAGES: the split, the timing, page 0
    mov word [rw_pgdebt], 0
    mov word [rw_pgrate], 0         ; (the rate measured afresh)
    mov word [rw_fstxto], RW_FSTXTP * 256
    mov word [rw_fsstr], 256
    mov byte [rb_panon], 1
    mov byte [rb_torus], 1          ; THE CANVAS (REALBOY-SPEC 15.5)
    mov word [rb_lhook], rw_pgtryd  ; (looked for during a draw too, and
                                    ;   never waited for there)
    call rw_dmgfull
    jmp short .in
.mono:
    call rw_fsclear                 ; Hercules or CGA: the screen black,
    call rw_fstab                   ;   the writer's table, and every line
    call rw_dmgfull                 ;   of the first frame
.in:
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
    mov byte [rw_fsfrac], 0
    mov byte [rw_fsrun], 0
    call OSAPI_GET_TICKS
    mov [rw_last], ax
    mov byte [rw_infsx], 1          ; (rw_clk: the bracket's clock now)
    mov al, RLE_FSIN
    call rw_logevt
    call rw_drawnow                 ; the first draws now
.loop:
    call rw_fsdrain                 ; ZF = 0: Esc
    jnz .out
    call rw_fsowed                  ; AX = frames owed now (taken)
    or ax, ax
    jnz .run
    cmp byte [rw_undrawn], 0        ; caught up: what has not been drawn,
    jne .idle                       ;   rather than wait (the window's .idle)
    call rw_pglock                  ; PAGES: the next frame on the display's
    jnz .run                        ;   word (AX = 1)
    cmp byte [rw_pgpend], 0         ; (a flip waiting: the beam, not the
    je .wt                          ;   clock - it is a frame of 14 ms)
    call rw_pgtry
    jmp .loop
.wt:
    mov al, FSXW_FRAME
    cmp byte [rw_fsrate], 0
    jne .w
    mov al, FSXW_TICK
.w:
    call OSAPI_FSX_WAIT
    jmp short .loop
.run:
    cmp ax, RW_BEHIND               ; behind by more than that: run on
    jbe .n                          ;   from here rather than race
    mov ax, RW_BEHIND
.n:
    mov [rw_fsleft], ax
    call rw_logowed                 ; (AL = frames owed, for the log)
.f:
    call rw_keys
    call rw_frame
    jc .out                         ; it stopped
    call rw_sound
    inc word [rw_nrun]
    call rw_stat
    inc byte [rw_fsrun]
    xor bx, bx
    dec word [rw_fsleft]
    jz .due                         ; caught up: draw this one, when due
    cmp byte [rw_fsrun], RW_FSSKIP  ; (rw_drawdue, as the window's)...
    jb .f
    mov bx, [rw_fsleft]             ; ...or behind (rw_drawdue), by more
    call rw_behind                  ;   the further behind
.due:
    call rw_drawdue
    jc .draw
    mov byte [rw_fsrun], 0
    cmp word [rw_fsleft], 0
    jne .f
    jmp .loop
.idle:
    mov word [rw_fsleft], 0         ; (none to run after it)
.draw:
    mov byte [rw_fsrun], 0
    mov si, rw_fsdraw
    call rw_timed
    call rw_fsdrain                 ; Esc between two draws too: on an 8088
    jnz .out                        ;   a turn of frames is longer than a press
    cmp word [rw_fsleft], 0
    jne .f
    jmp .loop
.out:
    pop word [rw_budget]
    mov byte [rw_infsx], 0
    cmp byte [rb_panon], 0          ; PAGES: the window's frame, [rw_fseg],
    je .r                           ;   which the bracket left behind
    mov byte [rb_panon], 0
    mov byte [rb_torus], 0
    mov word [rb_lhook], 0
    mov byte [rw_pgpend], 0
    call rw_dmgfull
.r:
    ret

; rw_pglock - PAGES, caught up and every frame drawn: the next frame runs
; the moment the last one is on the glass, borrowed from the clock (at most
; one: [rw_pgdebt], which rw_fsowed takes back). The card's refresh is the
; Game Boy's (rw_pgcrtc: 59.71 Hz, the clock's 59.73), so each frame is
; shown once, a refresh after the one before - where taking them on the
; clock's word lands each at whatever refresh follows it, two of them in
; one now and then, and the picture judders. The clock runs 0.02% faster,
; which is a frame run undrawn every ~74 s. At 100% only (Machine > Speed).
; ZF = 0 and AX = 1: run one
rw_pglock:
    cmp byte [rw_fspan], 0
    je .no
    cmp byte [rw_pgpend], 0         ; (the last one still waits for its
    jne .no                         ;   refresh)
    cmp word [rw_pgdebt], 0
    jne .no
    cmp byte [rw_speed], 0
    jne .no
    mov word [rw_pgdebt], 1
    mov ax, 1
    or ax, ax
    ret
.no:
    xor ax, ax
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
    cmp byte [rw_speed], 0          ; Machine > Speed under 100%: periods x
    je .r                           ;   its 256ths, the fraction kept
    push dx
    mul word [rw_spdk]
    add al, [rw_fsfrac]
    adc ah, 0
    adc dl, 0
    mov [rw_fsfrac], al
    mov al, ah
    mov ah, dl
    pop dx
.r:
    cmp word [rw_pgdebt], 0         ; (PAGES: a frame rw_pglock ran early is
    je .rr                          ;   not owed again)
    cmp ax, [rw_pgdebt]
    jae .all
    sub [rw_pgdebt], ax
    xor ax, ax
    ret
.all:
    sub ax, [rw_pgdebt]
    mov word [rw_pgdebt], 0
.rr:
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
    mul word [rw_pertick]           ; (RW_PERTICK at 100%: Machine > Speed)
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
    call rw_klat                    ; a press a draw would hide (rw_keys)
    jmp short .k
.e:
    mov al, 1                       ; Esc
    call OSAPI_KEY_DOWN             ; CF = 1: held
    jc .out
    call os88alt_edge               ; ...or a fresh Alt+Enter
    jc .out
    xor al, al                      ; (ZF = 1: stay)
    ret
.out:
    or al, 1                        ; (ZF = 0: leave)
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

; rw_fscrtc - mode 0Dh's DISPLAY cut to the picture (REALBOY-SPEC 15): 160
; pixels by 154 rows - the 144 of the picture, a gap and the speed line's 8 -
; from VRAM offset 0, centred by moving the blanking and the retraces, the
; border around it the card's OVERSCAN in the border's grey (index 4). The
; total, the sync widths and so every frequency are mode 0Dh's own: only
; where the sync falls against the picture moves. It is what lets the
; picture move in VRAM under a fixed window (the start address and the pel
; panning, SPEC.md 53.7: the bracket's mode is the app's to program); the
; exit's mode set puts back all of it.
rw_fscrtc:
    mov dx, 3D4h
    mov al, 11h                     ; CR11: unlock CR0-CR7 (bit 7)
    out dx, al
    inc dx
    in al, dx
    and al, 7Fh
    out dx, al
    dec dx
    mov si, rw_fscrv
    mov cx, (rw_fscrve - rw_fscrv) / 2
.c:
    lodsw                           ; AL = the index, AH = the value
    out dx, ax
    loop .c
    mov dx, 3DAh                    ; the attribute controller's flip-flop
    in al, dx
    mov dx, 3C0h
    mov al, 31h                     ; AR11, the overscan (with the display
    out dx, al                      ;   left on, bit 5)
    mov al, 4                       ; ...the border's grey
    out dx, al
    ret
rw_fscrv:   db 01h, 13h             ; horizontal display end: 20 chars
            db 02h, 1Fh             ; start blank, 9 chars earlier
            db 03h, 87h             ; end blank (39: bit 5 in CR05)
            db 04h, 22h             ; start retrace, 9 earlier
            db 05h, 89h             ; end retrace (41), end blank bit 5
            db 12h, 33h             ; vertical display end: 307 (154 x 2)
            db 15h, 68h             ; start blank 360, 46 lines earlier
            db 16h, 8Bh             ; end blank 395
            db 10h, 6Eh             ; start retrace 366
            db 11h, 80h             ; end retrace (368), CR0-CR7 locked again
rw_fscrve:

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
    cmp byte [rw_fskind], RW_FSVGA
    je .vga
    jmp rw_fsdrawd
.vga:
    cmp byte [rw_fspan], 0
    je .cp
    call rw_pgdraw
    jmp short .tx
.cp:
    mov ax, [rw_fsi + FSI_SEG]      ; the changed lines, by damage - each to
    mov [rb_dvga], ax               ;   VRAM as rb_renderd decides it changed
    call rw_render                  ;   (ppu_dvga), not by a second pass over
    mov word [rb_dvga], 0           ;   the buffer
.tx:
    call rw_fsline                  ; ZF = 0: the speed line to draw
    jz .r
    call rw_fstext
.r:
    ret
%if RW_FSY * 40 + RW_FSX != 0
%error "ppu_dvga writes line n at 40 n: the picture's corner must be VRAM 0"
%endif

; rw_pgdraw - PAGES: the frame's overlay lines composed PAN-ALIGNED into
; [rw_pseg] (rb_panon, rb_torus: 42 bytes a line), the canvas of the page
; neither shown nor waiting to be put right (rb_tpage, REALBOY-SPEC 15.5),
; and its flip posted. The card is never drawn on where it shows, and
; nothing waits for the beam
rw_pgdraw:
    pushf
    cli
    mov al, [rw_pgshow]
    mov ah, 0FFh
    cmp byte [rw_pgpend], 0
    je .c
    mov ah, [rw_pgnext]
.c:
    popf
    xor bx, bx
.f:
    cmp bl, al
    je .x
    cmp bl, ah
    jne .got
.x:
    inc bx
    jmp short .f
.got:
    push bx
    call rw_render
    pop dx                          ; DL = the page
    mov al, dl
    mov es, [rw_fsi + FSI_SEG]
    call rb_tpage                   ; BX = where it shows from
    mov di, bx
    mov bl, dl
    mov al, [rb_panv]
    mov ah, [rb_tss]                ; (the strip it was drawn with)
    pushf
    cli
    mov [rw_pgstart], di
    mov [rw_pgpan], al
    mov [rw_pgss], ah
    mov [rw_pgnext], bl
    mov byte [rw_pgpend], 1
    popf
    jmp rw_pgtry

; rw_pgcrtc - PAGES (REALBOY-SPEC 15.4, 15.5): THE CANVAS - a row stride of
; 256 bytes (CR13), so 256 rows are a plane's 64KB and its wrap the Game
; Boy's background's; slot 0 of each row the split's region, the speed line
; under the picture (the LINE COMPARE at scanline 287, with AR10's pixel
; panning mode so it never pans), and slots 1-3 the three pages' canvases.
; A frame of 527 scanlines where mode 0Dh's is 449: the line rate is its
; own, 31.47 kHz, and the REFRESH the Game Boy's, 59.71 Hz (rw_pglock),
; with the sync polarity a 480-line mode has at that rate. The display's end
; (308) to the blanking (400) is ~2.9 ms of border, rw_pgtry's window
; inside it (RW_PGW1, RW_PGW0); the picture sits in the middle of the frame.
; Plane 2 is the border's and the speed line's ground in the split's region,
; clear on the canvases. The canvas's state from nothing (rb_tseg): every
; cell owed, every line stale; page 0 shown, pan 0
rw_pgcrtc:
    mov es, [rw_fsi + FSI_SEG]
    mov dx, 3C4h
    mov ax, 0F02h                   ; every plane cleared, the whole 64KB
    out dx, ax
    xor di, di
    mov cx, 8000h
    xor ax, ax
    rep stosw
    mov ax, 0402h                   ; ...and plane 2 set in the split's
    out dx, ax                      ;   region: slot 0 of rows 0-9
    xor di, di
    mov bx, 10
.sp:
    mov cx, 64 / 2
    mov ax, 0FFFFh
    rep stosw
    add di, 256 - 64
    dec bx
    jnz .sp
    push ds                         ; no line owed to any page
    mov es, [rw_pseg]
    mov di, RB_PGMSK
    mov cx, 3 * 144 / 2
    xor ax, ax
    rep stosw
    pop ds
    mov ax, [rw_pseg]               ; the canvas's state, from nothing
    add ax, RW_TOFF / 16
    mov [rb_tseg], ax
    call rb_tinit
    mov word [rb_shook], rw_pgstrip ; (the strip's region, laid out by us)
    mov byte [rw_pglc], 144
    mov byte [rw_pgss], 144
    mov dx, 3D4h
    mov al, 11h                     ; CR0-CR7 unlocked
    out dx, al
    inc dx
    in al, dx
    and al, 7Fh
    out dx, al
    dec dx
    mov al, 09h                     ; CR09 bit 6: the line compare's bit 9
    out dx, al
    inc dx
    in al, dx
    and al, 0BFh
    out dx, al
    dec dx
    mov si, rw_pgcrv
    mov cx, (rw_pgcrve - rw_pgcrv) / 2
.c:
    lodsw
    out dx, ax
    loop .c
    mov dx, 3CCh                    ; the sync polarity: 480 lines' (both
    in al, dx                       ;   negative), for a monitor to take the
    or al, 0C0h                     ;   refresh as the 60 Hz one it is
    mov dx, 3C2h
    out dx, al
    mov dx, 3DAh                    ; AR10 bit 5: the pixel panning mode
    in al, dx
    mov dx, 3C0h
    mov al, 30h
    out dx, al
    inc dx
    in al, dx
    or al, 20h
    dec dx
    out dx, al
    mov al, 33h
    out dx, al
    xor al, al
    out dx, al
    mov byte [rw_pgshow], 0
    mov byte [rw_pgpend], 0
    mov byte [rw_pgok], 0           ; (the beam timed at the first flip)
    mov word [rw_pgper], RW_PGPER
    ret
rw_pgcrv:   db 0Ch, 00h             ; page 0's slot, row 0
            db 0Dh, 40h
            db 13h, 80h             ; the row stride: 256 bytes
            db 06h, 0Dh             ; vertical total 527 (525: bit 9 in CR07)
            db 07h, 3Eh             ; the overflow: VT 9, LC, VBS, VRS, VDE 8
            db 18h, 1Fh             ; line compare 287
            db 15h, 90h             ; start blank 400
            db 16h, 08h             ; end blank 520
            db 10h, 9Ah             ; start retrace 410
            db 11h, 8Ch             ; end retrace 412, CR0-CR7 locked again
rw_pgcrve:
%if RW_TOFF < RB_PGMSK + 3 * 144 || RW_TOFF + RB_TSIZE > RW_PBUF || RW_TOFF % 16
%error "the canvas's state must sit past the owed bytes, inside [rw_pseg]"
%endif

; rw_pglcw - AL = a strip's first line (144 none): the LINE COMPARE at
; scanline 2 x AL - 1, where the split's region begins to show - the strip's
; rows and the speed line under them (REALBOY-SPEC 15.5.1). Bit 8 is CR07's
; bit 4, which CR11's lock leaves writable. Kept: all but AX
rw_pglcw:
    push dx
    mov [rw_pglc], al
    xor ah, ah
    shl ax, 1
    dec ax
    mov dx, 3D4h
    push ax
    mov ah, al
    mov al, 18h
    out dx, ax
    pop ax
    mov al, 2Eh                     ; (rw_pgcrv's CR07, bit 4 the compare's)
    test ah, 1
    jz .b
    or al, 10h
.b:
    mov ah, al
    mov al, 07h
    out dx, ax
    pop dx
    ret

; rw_pgstrip - rb_tpage's hook (rb_shook), DS = CS = ours: the split's region
; laid out for a strip at AL (144 none) - its rows clear, 0 to H - 1 (H =
; 144 - AL), for rb_tpage to write; the speed line's ground (plane 2) on the
; ten rows under them and its text moved there; every other row of slot 0
; that a strip could have held, clear. Kept: all
rw_pgstrip:
    push ax
    push bx
    push cx
    push dx
    push di
    push es
    mov bl, 144
    sub bl, al                      ; BL = H
    mov es, [rw_fsi + FSI_SEG]
    mov dx, 3C4h
    mov ax, 0F02h                   ; every plane, rows 0-153: clear
    out dx, ax
    xor di, di
    mov cx, 154
    xor ax, ax
.c:
    push cx
    mov cx, 64 / 2
    rep stosw
    pop cx
    add di, 256 - 64
    loop .c
    mov ax, 0402h                   ; ...plane 2 set on rows H to H + 9
    out dx, ax
    mov ah, bl
    xor al, al
    mov di, ax
    mov cx, 10
.g:
    push cx
    mov cx, 64 / 2
    mov ax, 0FFFFh
    rep stosw
    pop cx
    add di, 256 - 64
    loop .g
    mov bh, bl                      ; the speed line's text: row H + 2
    add bh, RW_FSTXTP
    xor bl, bl
    mov [rw_fstxto], bx
    mov byte [rw_ovlnew], 1         ; (drawn again there, a note or F1's)
    pop es
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rw_fstext - rw_ovltxt on the border under the picture, 16 cells wide
rw_fstext:                          ; (SI = the line, rw_fsline's)
    push bp
    mov bp, [rw_fsstr]              ; BP = a glyph row to the next
    dec bp
    mov es, [rw_fsi + FSI_SEG]      ; (its own: the writer before it no
    mov dx, 3C4h                    ;   longer leaves ES on the card)
    mov ax, 0302h                   ; planes 0 and 1: the glyph's set bits
    out dx, ax                      ;   read 7, its clear ones 4
    mov di, [rw_fstxto]
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
    sub al, [rw_font0]
    xor ah, ah
    shl ax, 1
    shl ax, 1
    shl ax, 1
    mov si, [rw_fontp]
    add si, ax
    mov cx, 8
    push di
    push ds
    mov ds, [rw_fontp + 2]          ; (the kernel's table, where it is)
.row:
    movsb
    add di, bp
    loop .row
    pop ds
    pop di
    inc di
    pop cx
    pop si
    loop .c
    pop bp
    ret

; DAC 0-7, six bits a gun: the shades (0 lightest), the border, -, -, text
rw_fsgreys:
    db 63, 63, 63,  42, 42, 42,  21, 21, 21,  0, 0, 0
    db 4, 4, 8,  0, 0, 0,  0, 0, 0,  48, 48, 52

rw_fsmodes:     db FSXM_VGA0D, FSXM_HERC, FSXM_CGA320

; =============================================================================
; The Hercules and CGA writers (REALBOY-SPEC section 15.1): rb_renderd's
; changed lines, through a table, straight to the page. A Game Boy byte -
; eight pixels, two shade bits each - is two NIBBLE indices, (bit 0's four
; pixels << 4) | bit 1's, and each index is a table entry: on a Hercules two
; bytes, the 2x2 dither's top and bottom rows of those four pixels doubled;
; on a CGA a word, the four pixels doubled in four colours.
; =============================================================================

; rw_fsclear - the page black. ES:DI from rw_fsi.
rw_fsclear:
    mov es, [rw_fsi + FSI_SEG]
    xor di, di
    mov cx, 8000h / 2               ; Hercules' 32KB (CGA's 16KB, twice)
    cmp byte [rw_fskind], RW_FSHERC
    je .c
    mov cx, 4000h / 2
.c:
    xor ax, ax
    rep stosw
    ret

; rw_fstab - rw_htab for the writer: 256 x (row a, row b) bytes for a
; Hercules, 256 words for a CGA
rw_fstab:
    xor bx, bx                      ; BL = the index
.i:
    xor dx, dx                      ; the entry, a pixel at a time
    mov ch, 3                       ; CH = the pixel's bit in each nibble,
.p:                                 ;   the leftmost (3) first
    mov cl, ch
    mov al, bl
    shr al, cl                      ; bit 1's: the low nibble
    and al, 1
    shl al, 1
    mov ah, bl
    add cl, 4
    shr ah, cl                      ; bit 0's: the high nibble
    and ah, 1
    or al, ah                       ; AL = the shade, 0-3
    push bx
    mov bl, al
    xor bh, bh
    cmp byte [rw_fskind], RW_FSHERC
    jne .cga
    shl dl, 1                       ; Hercules: two pixels on each row
    shl dl, 1
    shl dh, 1
    shl dh, 1
    or dl, [rw_hdita + bx]
    or dh, [rw_hditb + bx]
    jmp short .nx
.cga:
    mov cl, 4                       ; CGA: the colour twice, four bits
    shl dx, cl
    or dl, [rw_cgac + bx]
.nx:
    pop bx
    dec ch
    jns .p
    push bx
    xor bh, bh
    shl bx, 1
    cmp byte [rw_fskind], RW_FSHERC
    jne .w
    mov [rw_htab + bx], dl          ; Hercules: row a, then row b
    mov [rw_htab + bx + 1], dh
    jmp short .wd
.w:
    xchg dl, dh                     ; CGA: the left pixels' byte first
    mov [rw_htab + bx], dx
.wd:
    pop bx
    inc bl
    jnz .i
    ret

rw_hdita:       db 3, 3, 2, 0       ; the 2x2 dither, a shade's two pixels
rw_hditb:       db 3, 2, 1, 0       ;   on the top row and on the bottom
rw_cgac:        db 0Fh, 05h, 0Ah, 00h ; shade -> CGA colour, doubled: white,
                                    ;   cyan, magenta, black

; rw_fsdrawd - a frame by damage onto the Hercules or CGA page, and the speed
; line when it changed
rw_fsdrawd:
    call rw_render                  ; AX = the lines that changed
    mov es, [rw_fsi + FSI_SEG]
    or ax, ax
    jz .txt
    xor dl, dl                      ; DL = the line
.l:
    call rw_dchg
    jz .n
    push dx
    mov al, dl
    mov ah, 40
    mul ah
    push es                         ; the line's two planes into rw_lbuf:
    push ds                         ;   the writers read our table (rw_htab)
    pop es                          ;   beside it
    mov si, ax
    mov di, rw_lbuf
    mov ax, [rw_fseg]
    push ds
    mov ds, ax
    mov cx, 20
    rep movsw
    pop ds
    pop es
    mov si, rw_lbuf                 ; SI = the line's two planes
    xor dh, dh
    cmp byte [rw_fskind], RW_FSHERC
    jne .cga
    call rw_hline
    jmp short .p
.cga:
    call rw_cline
.p:
    pop dx
.n:
    inc dl
    cmp dl, 144
    jb .l
.txt:
    call rw_fsline
    jz .r
    call rw_fstext1
.r:
    ret

; rw_fsline - the speed line's turn: a note (rw_note) that has had its time
; comes down, and ZF = 0 when the line is to be drawn again - changed, and
; F1's or a note's or blank where one just was. SI = what it says
rw_fsline:
    cmp byte [rw_msgt], 0
    je .t
    call OSAPI_GET_TICKS
    sub ax, [rw_msgend]
    js .t
    mov byte [rw_msgt], 0           ; its time is up: blank, or F1's again
    mov byte [rw_msgclr], 1
    mov byte [rw_ovlnew], 1
.t:
    cmp byte [rw_ovlnew], 0
    je .r
    mov si, rw_msg
    cmp byte [rw_msgt], 0
    jne .y
    mov si, rw_ovltxt
    cmp byte [rw_ovl], 0
    jne .y
    mov si, rw_s_none               ; blank - when something is up
    cmp byte [rw_msgclr], 0         ;   (F1 off left its line standing: the
    jne .y                          ;   flag said only "a note came down")
    cmp al, al                      ; (ZF = 1: nothing to say)
.r:
    ret
.y:
    mov byte [rw_ovlnew], 0
    mov byte [rw_msgclr], 0         ; [rw_msgclr]: the line has text on it
    cmp si, rw_s_none
    je .z
    mov byte [rw_msgclr], 1
.z:
    or si, si                       ; (ZF = 0)
    ret
rw_s_none:  db 0

; rw_hrow - AX = a Hercules row: DI = its first byte at the picture's column
rw_hrow:
    push ax
    push cx
    push dx
    mov di, ax
    and di, 3
    mov cl, 13
    shl di, cl                      ; the bank: (row AND 3) x 2000h
    mov cl, 2
    shr ax, cl
    mov cx, 90
    mul cx
    add di, ax
    add di, RW_HX
    pop dx
    pop cx
    pop ax
    ret

; rw_hline - DX = a Game Boy line, SI = its planes: Hercules rows HY + 2 x
; line and the one under it, 40 bytes each
rw_hline:
    mov ax, dx
    shl ax, 1
    add ax, RW_HY
    call rw_hrow
    mov bp, di                      ; BP = row a
    inc ax
    call rw_hrow                    ; DI = row b
    xchg bp, di
    mov bx, rw_htab
    mov ch, 20
    mov cl, 4
.b:
    mov al, [si]                    ; bit 0's eight pixels
    mov ah, [si + 20]               ; bit 1's
    inc si
    mov dl, al
    and dl, 0F0h
    mov dh, ah
    shr dh, cl
    or dl, dh                       ; DL = the left four's index
    shl al, cl
    and ah, 0Fh
    or ah, al                       ; AH = the right four's
    mov al, dl
    xor dh, dh
    mov dl, ah                      ; (DL kept: the right index)
    xor ah, ah
    shl ax, 1
    xchg ax, bx
    mov ax, [rw_htab + bx]          ; AL = row a, AH = row b, left four
    xchg ax, bx
    mov [es:di], bl
    mov [es:bp], bh
    mov bl, dl
    xor bh, bh
    shl bx, 1
    mov ax, [rw_htab + bx]          ; ...the right four
    mov [es:di + 1], al
    mov [es:bp + 1], ah
    add di, 2
    add bp, 2
    dec ch
    jnz .b
    ret

; rw_cline - DX = a Game Boy line, SI = its planes: CGA row CY + line, 80
; bytes (even rows at 0, odd at 2000h)
rw_cline:
    mov ax, dx
    add ax, RW_CY
    mov di, ax
    and di, 1
    mov cl, 13
    shl di, cl
    shr ax, 1
    mov cx, 80
    push dx
    mul cx
    pop dx
    add di, ax
    mov ch, 20
    mov cl, 4
.b:
    mov al, [si]
    mov ah, [si + 20]
    inc si
    mov dl, al
    and dl, 0F0h
    mov dh, ah
    shr dh, cl
    or dl, dh                       ; DL = the left four's index
    shl al, cl
    and ah, 0Fh
    or ah, al                       ; AH = the right four's
    mov bl, dl
    xor bh, bh
    shl bx, 1
    mov dx, [rw_htab + bx]
    mov [es:di], dx
    mov bl, ah
    xor bh, bh
    shl bx, 1
    mov dx, [rw_htab + bx]
    mov [es:di + 2], dx
    add di, 4
    dec ch
    jnz .b
    ret

; rw_fstext1 - rw_ovltxt under the picture on a Hercules or CGA page, the
; glyph's set bits lit (a CGA's in colour 3)
rw_fstext1:                         ; (SI = the line, rw_fsline's)
    xor bx, bx                      ; BX = the cell
.c:
    mov al, [si]
    or al, al
    jnz .g
    mov al, ' '
    dec si
.g:
    inc si
    sub al, [rw_font0]
    xor ah, ah
    shl ax, 1
    shl ax, 1
    shl ax, 1
    push si
    mov si, [rw_fontp]
    add si, ax                      ; SI = its eight rows
    xor cx, cx                      ; CX = the row
.r:
    push ds
    mov ds, [cs:rw_fontp + 2]       ; (the kernel's table, where it is)
    lodsb
    pop ds
    push cx
    push bx
    cmp byte [rw_fskind], RW_FSHERC
    jne .cg
    mov dl, al
    mov ax, RW_HTXT
    add ax, cx
    call rw_hrow
    add di, bx
    mov [es:di], dl
    jmp short .rn
.cg:
    mov dl, al                      ; eight pixels in colour 3: a word
    xor ax, ax
    mov cx, 8
.x:
    shl ax, 1
    shl ax, 1
    shl dl, 1
    jnc .x0
    or al, 3
.x0:
    loop .x
    xchg al, ah                     ; the left pixels' byte first
    pop bx
    pop cx
    push cx
    push bx
    push ax
    mov ax, RW_CTXT
    add ax, cx
    mov di, ax
    and di, 1
    mov cl, 13
    shl di, cl
    shr ax, 1
    mov cx, 80
    mul cx
    add di, ax
    shl bx, 1
    add di, bx
    add di, 10                      ; the line starts 20 pixels in... x 4
    pop ax
    mov [es:di], ax
.rn:
    pop bx
    pop cx
    inc cx
    cmp cx, 8
    jb .r
    pop si
    inc bx
    cmp bx, 16
    jb .c
    ret

