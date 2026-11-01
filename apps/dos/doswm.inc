; =============================================================================
; os8088 - apps/dos/doswm.inc
;
; **INT 33h IN A WINDOW** (SPEC.md 96.54.4, docs/plans/DOS-WINDOWED-PLAN.md
; wave 5). A program running live in its window (dosw.inc) sees a virtual
; 80x25 text screen that is the window's console band. Its mouse has to be on
; THAT screen: column * 8 and row * 8 over INT 33h's 640x200, measured from the
; band's top-left and the first buffer row the band shows - not the desktop's
; pointer scaled as if the program owned the glass, which is what the
; bracket's translation (96.10) answers and what a window got until this file.
;
; **THE WHOLE OF IT IS TWO HOST HOOKS** (96.44.3). Every INT 33h answer the
; core gives - 03h, 05h/06h, 0Bh's derived mickeys, the 07h/08h window, the
; 0Ch event handler off the tick - is computed downstream of `DHK_MOUSE`, so
; translating the one read translates every function, and the core does not
; change by a byte. `dwm_start` binds both hooks for the run and `dwm_stop`
; puts the bracket's back; each hook also tests `[dvw_run]`/`[dvw_fs]` itself,
; so the full screen of 96.54.1 gets the bracket's whole-screen translation
; unchanged (`dos_vw`/`dos_vh` are set for the run in `dvw_runprog`).
;
; **THE BUTTONS ARE THE WINDOW'S ONLY WHEN THE PRESS WAS** - DESQview's rule
; for the foreground window, made exact: a button is reported down iff its
; DOWN EDGE was read while the pointer was over the band and the window was
; frontmost at this read AND at the one before it, and then it stays down
; until it is released wherever the pointer has gone (a drag clamps, it does
; not let go). So the click that RAISES a window behind another is the
; desktop's and never the program's, whichever side of the raise the program
; happened to poll on; a press begun on the title bar and dragged in is not a
; press; and a position outside the band is clamped to its edge, as a driver
; clamps to the screen.
;
; **THE BAND IS ASKED FOR, NOT REMEMBERED.** `[dos_conx]`/`[dos_cony]` are
; written at a PAINT, and a moved window calls no paint proc (SPEC.md
; 11.96.12) - so a quiet program whose window was dragged would be handed the
; old origin for ever. The origin is `OSAPI_WM_CONTENT` plus dos_con_geom's
; own margin, recomputed from `OSAPI_WM_GEOM` once a BIOS tick (dwm_sample,
; and dwm_mouse's head says why not every read); the COLUMN
; and ROW counts are the paint's, which only a resize changes and a resize
; repaints. THE TWO MUST AGREE: this is dos_con_geom's arithmetic, kept beside
; it in words rather than shared, because that routine also tells the console
; (`dos_con_pub`) and may not run from an interrupt.
;
; **NO TEXT CURSOR.** In the window the pointer is the desktop's own arrow,
; so `DHK_TXT` refuses (96.10.5.1's windowed case) - and FORGETS any cell the
; core believes it drew: `dos_fsi` outlives the bracket that set it, so a
; window run after a bracketed one would otherwise have the core wipe a stale
; B800 cell, which on a CGA desktop is the desktop's own framebuffer.
; =============================================================================

%ifdef DVW

dwm_own     equ dos_hbss + DOS_B_DWM + 0    ; the buttons the program has
dwm_last    equ dwm_own + 1                 ; the live mask at the last read
dwm_wasf    equ dwm_own + 2                 ; 1 = in front at the sample before
dwm_frnt    equ dwm_own + 3                 ; 1 = in front (and shown) now
dwm_tick    equ dwm_own + 4                 ; word: the tick of that sample
dwm_bx      equ dwm_own + 6                 ; word: the band's left...
dwm_by      equ dwm_own + 8                 ; word: ...and top, on the screen

; -----------------------------------------------------------------------------
; dwm_start - bind the window's two mouse hooks (dvw_runprog, worker)
; dwm_stop  - ...and give the bracket's back (dvw_fin)
; clobbers: nothing
;
; dwm_start runs BEFORE dos_hook_vectors, whose dos_m33_hidden wipes: the
; cell [dos_m33dv] names is on a screen this run does not have. It also
; clears [dos_m33hk] (dos_m33_arm's hook-once flag), which nothing else
; clears.
; -----------------------------------------------------------------------------
dwm_start:
    mov word [dwm_own], 0           ; dwm_own and dwm_last...
    mov word [dwm_wasf], 0          ; ...and both samples "behind"
    push es
    push ax
    mov ax, 0x40
    mov es, ax
    mov ax, [es:0x6C]
    dec ax                          ; a tick that is not now: the first read
    mov [dwm_tick], ax              ; samples
    pop ax
    pop es
    mov word [dos_m33dv], 0
    mov byte [dos_m33hk], 0         ; IRQ0 is NOT hooked in this run's table:
                                    ; the flag outlives the run that set it,
                                    ; and the program's block is primed from
                                    ; the desktop's, so a handler installed
                                    ; after an earlier run's was never called
    mov word [dos_hkv + DHK_MOUSE], dwm_mouse
    mov word [dos_hkv + DHK_TXT], dwm_txt
    ret

dwm_stop:
    mov word [dos_hkv + DHK_MOUSE], dos_hk_mouse
    mov word [dos_hkv + DHK_TXT], dos_hk_txt
    ret

; -----------------------------------------------------------------------------
; dwm_kick - the event handler, as the worker wakes (dvw_nap, world in)
; in:  the caller's stack, IF = 0; out: every register preserved
;
; A program waiting on a key in its window sleeps through its ticks with its
; world OUT, so IRQ0 lands on the desktop's vector and the core's
; `dos_m33_tick` - which is in the PROGRAM's table - never runs: an `0Ch`
; handler installed by a program that then waits for input (Microsoft Works'
; whole mouse) was never called. Every wake is where that tick would have
; been, so the dispatch runs here instead, with the tick's own state: what
; it already reported it does not report twice.
; -----------------------------------------------------------------------------
dwm_kick:
    push ds
    push cs
    pop ds
    call dos_m33_evt
    pop ds
    ret

; -----------------------------------------------------------------------------
; dwm_txt - DHK_TXT for a run in the window: none, and nothing left drawn
; -----------------------------------------------------------------------------
dwm_txt:
    cmp byte [dvw_run], 0
    je .desk
    cmp byte [dvw_fs], 0
    jne .desk                       ; the full screen has the bracket's text
    mov word [dos_m33dv], 0         ; screen, and the bracket's hook
    stc
    ret
.desk:
    jmp dos_hk_txt

; -----------------------------------------------------------------------------
; dwm_mouse - DHK_MOUSE for a run in the window
; out: BX = the buttons the program may see, CX = x, DX = y on the virtual
;      640x200 text screen; every other register preserved
;
; Reached from INT 33h on the program's stack, from `dos_getkey`'s poll and
; from `dos_m33_tick` inside IRQ0. The kernel calls are readers that take no
; lock (OSAPI_MOUSE, WM_GEOM, WM_CONTENT, WM_TOP), so all three paths may
; make them.
;
; **THE WINDOW IS SAMPLED ONCE A TICK, NOT ONCE A READ.** GEOM, CONTENT and
; TOP together measured ~10,000 cycles on the 8088 - a poll loop of `03h` and
; `05h` ran 143 times a second against 428 with the bracket's hooks - so the
; band's origin and "am I in front" are refreshed when the BIOS tick at
; 0040:006C has moved since the last read, and a read inside the same tick
; costs OSAPI_MOUSE and arithmetic. A dragged window's origin is therefore up
; to one tick late, which the pointer is too.
;
; "In front at the read before" is the PREVIOUS SAMPLE, and samples are taken
; only by reads - so the first read after a press always has, as its previous
; sample, one taken before the press: the click that raised the window from
; behind is never the program's, however long the program went without
; asking. (The price: a window brought forward by other means while the
; program read nothing has its first click after that swallowed too.)
; -----------------------------------------------------------------------------
dwm_mouse:
    cmp byte [dvw_run], 0
    je .desk
    cmp byte [dvw_fs], 0
    je .win
.desk:
    jmp dos_hk_mouse                ; the full screen: the bracket's scale
.win:
    push ax
    push si
    push di
    push bp
    push es
    mov ax, 0x40
    mov es, ax
    mov ax, [es:0x6C]               ; the BIOS tick, low word
    cmp ax, [dwm_tick]
    je .cached
    mov [dwm_tick], ax
    call dwm_sample
.cached:
    call OSAPI_MOUSE                ; CX = x, DX = y, AL = the buttons
    and ax, 3
    mov bp, ax                      ; BP = the live mask; bit 7 = NOT OURS
    mov al, [dwm_frnt]              ; in front at this sample AND the one
    and al, [dwm_wasf]              ; before; not hidden (dwm_sample folds
    jnz .elig                       ; that into dwm_frnt)
    or bp, 0x80
.elig:
    mov si, cx
    mov di, dx
    sub si, [dwm_bx]                ; SI/DI = the pointer IN the band
    sub di, [dwm_by]
    mov cx, [dos_concols]
    shl cx, 1
    shl cx, 1
    shl cx, 1
    call dwm_clamp                  ; SI into 0..cols*8-1
    xchg si, di
    mov cx, [dos_conrows]
    shl cx, 1
    shl cx, 1
    shl cx, 1
    call dwm_clamp                  ; ...and the y into the rows shown
    xchg si, di
    mov ax, [con_vtop]              ; ...from the first buffer row shown
    shl ax, 1
    shl ax, 1
    shl ax, 1
    add di, ax
    cmp di, M33_VH - 1
    jbe .ycap
    mov di, M33_VH - 1
.ycap:
    cmp si, M33_VW - 1
    jbe .xcap
    mov si, M33_VW - 1
.xcap:
    mov ax, bp
    mov bl, al
    and bl, 3                       ; BL = the live mask
    mov ah, [dwm_last]
    mov [dwm_last], bl
    not ah
    and ah, bl                      ; AH = the buttons gone DOWN since then
    test al, 0x80
    jz .ours
    xor ah, ah                      ; a press that is not the window's
.ours:
    mov al, [dwm_own]
    and al, bl                      ; a release lets go wherever it happens
    or al, ah
    mov [dwm_own], al
    xor ah, ah
    mov bx, ax
    mov cx, si
    mov dx, di
    pop es
    pop bp
    pop di
    pop si
    pop ax
    ret

; -----------------------------------------------------------------------------
; dwm_sample - the window, once a tick: the band's origin and "in front"
; out: [dwm_bx]/[dwm_by], [dwm_frnt] (0 when hidden or behind), [dwm_wasf] =
;      the sample before; clobbers AX, BX, CX, DX
;
; The origin is dos_con_geom's (see the file's head): content origin plus the
; centring margin over [dos_concols] cells, and DOS_BARH down.
; -----------------------------------------------------------------------------
dwm_sample:
    mov al, [dwm_frnt]
    mov [dwm_wasf], al
    mov bx, [dos_win]
    call OSAPI_WM_GEOM              ; CX = the content width; CF = hidden
    sbb al, al
    inc al                          ; AL = 1 visible, 0 hidden
    mov [dwm_frnt], al
    mov ax, [dos_concols]
    shl ax, 1
    shl ax, 1
    shl ax, 1                       ; AX = the band's width in pixels
    sub cx, ax
    jnc .slack                      ; a window shrunk since the paint: no
    xor cx, cx                      ; margin, until the repaint says otherwise
.slack:
    shr cx, 1
    and cx, 0xFFF8
    call OSAPI_WM_CONTENT           ; AX = content left, DX = its top
    add ax, cx
    mov [dwm_bx], ax
    add dx, DOS_BARH
    mov [dwm_by], dx
    call OSAPI_WM_TOP               ; BX = the frontmost window
    cmp bx, [dos_win]
    je .front
    mov byte [dwm_frnt], 0
.front:
    ret

; -----------------------------------------------------------------------------
; dwm_clamp - SI (signed) into 0..CX-1; BP |= 80h when it had to move
; -----------------------------------------------------------------------------
dwm_clamp:
    or si, si
    jns .lo
    xor si, si
    or bp, 0x80
.lo:
    cmp si, cx
    jb .out
    mov si, cx
    or bp, 0x80
    dec si
    jns .out
    xor si, si                      ; no cells at all: the origin
.out:
    ret

%endif                              ; DVW
