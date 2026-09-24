; =============================================================================
; os8088 - apps/tithe/tithe.asm
;
; TITHE (SPEC.md 97) - a two-player turn-based card duel.
; docs/plans/TITHE-PLAN.md is the design record; SPEC.md 97 is the contract.
;
; **THIS IS WAVE 1a: THE RENDERER WITH NO GAME BEHIND IT.** The layout table,
; the board, the band composer and the pacing wheel, driven by a fixed board
; and a few keys. There are no rules, no cards, no AI and no network, and
; SPEC.md 97.9 lists what each later wave adds so a reader can tell a gap from
; a defect. It is on tests/unit/t_livefull.py's exemption list until wave 6,
; because a package that cannot be launched from a menu is not something to
; put on the live media.
;
; WHAT WAVE 1a IS FOR is the LAYOUT and the RATE - whether twenty figures at
; this size on this grid read as a crowd, and whether the wheel holds its rate
; while they do. Both are questions only eyes can answer, which is why the art
; here is procedural and the concept art is the owner's (TITHE-PLAN 16.1).
;
; --- THE THREE THINGS THAT DECIDE THE REST -----------------------------------
;
;  1. **ONE OPAQUE BLIT A FEATURE, GROUND BAKED IN** (SPEC.md 97.4). Drawing a
;     sprite where it was IS the erase; there is no erase pass and no instant
;     at which it is off the glass. SPEC.md 79.5.1 and 93.5.1 both paid for
;     that lesson and this package does not get to relearn it.
;
;  2. **ISOMETRIC IS A SHEAR** (SPEC.md 97.3). The cell grid is sheared rather
;     than projected, so the rectangles tile exactly: non-overlap is a
;     property of the layout, not a promise the art has to keep, and no
;     painter's order exists. CW is a multiple of 8, so every cell's x
;     satisfies gfx_blit1's one alignment rule for free.
;
;  3. **THE WHEEL'S CREDIT IS TIME AND IT IS CALIBRATED** (SPEC.md 97.5). A
;     band costs `arrival + rows x R + bytes x B`, so a byte credit
;     over-spends on tall bands; and the constants belong to THIS machine, so
;     they are measured at load off the PIT rather than read out of a table.
;
; Keys: F fullscreen, D detail, S sprite size, R recalibrate, P pause,
;       +/- the animation share, Esc leaves fullscreen or closes.
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'TITHE', ti_entry, 1 | OS88_F_PARTS, OS88_STACK_256
                                ; the worker's stack class (SPEC.md 8.7):
                                ; ti_worker's chain is 4 deep and its deepest
                                ; leaf is the band blit, which pushes eight
                                ; registers in front of a far call. Measured
                                ; static 88 over the 64-byte interrupt floor
                                ; is 152; 256 gives 1.7x

    OS88_ICON16
    dw 0x0000                   ; a shield over a coin: the tithe
    dw 0x0FF0
    dw 0x1FF8
    dw 0x3FFC
    dw 0x3FFC
    dw 0x3FFC
    dw 0x3FFC
    dw 0x1FF8
    dw 0x1FF8
    dw 0x0FF0
    dw 0x07E0
    dw 0x03C0
    dw 0x0180
    dw 0x0000
    dw 0x0000
    dw 0x0000
    dw 0x0000                   ; 16 data rows
    dw 0x0FF0
    dw 0x1008
    dw 0x2004
    dw 0x2664
    dw 0x2994
    dw 0x2994
    dw 0x2664
    dw 0x1008
    dw 0x1008
    dw 0x0810
    dw 0x0420
    dw 0x0240
    dw 0x0180
    dw 0x0000
    dw 0x0000
    OS88_ICON16_END

TI_HUDMAX   equ 92                ; the widest HUD row any surface asks for -
                                  ; a Hercules' 720 columns is 90 cells - plus
                                  ; the NUL and one to spare
TI_HUDRIGHT equ 18                ; cells the right-hand field occupies
TI_HUDMID   equ 8                 ; ...and half the middle one's
TI_FEATURES equ 21                ; WHAT THE IDLE WHEEL WALKS: 20 characters and
                                  ; the moused-over card. The brief's own
                                  ; number is 23 and the two BASES have come
                                  ; out of it - they are a lane of their own
                                  ; below, on their own clock
TI_IDLEFPS10 equ 44               ; THE IDLE'S TARGET RATE, in tenths of a pose
                                  ; a second a feature (SPEC.md 97.5.2): the
                                  ; rate the XT's VGA and Hercules arms were
                                  ; signed off at. A CAP and not a promise -
                                  ; a machine with less room draws what its
                                  ; credit buys, one with more draws this
TI_SHARE    equ 20                ; per cent of a frame the IDLE may take.
                                  ; TITHE-PLAN 16.1 asks whether twenty figures
                                  ; breathing at 3.6 fps reads as a crowd or as
                                  ; a slideshow, and the field answered it the
                                  ; OTHER WAY: at 40% the built renderer runs
                                  ; the pose cycle at 6.4 fps a feature and the
                                  ; motion is TOO FAST - `-` had to be pressed
                                  ; repeatedly before it looked right. Keeping
                                  ; 40% would mean doubling the pose count to
                                  ; make each step smaller, which is art nobody
                                  ; has room for; halving the share costs
                                  ; nothing and spends the surplus below
TI_TRIMMIN  equ 30                ; the credit's floor, as a per cent of what
                                  ; the share asks for (SPEC.md 97.5)

; THREE LANES AND THREE CLOCKS (SPEC.md 97.5.1). The share above is the IDLE's
; and nothing else draws on it. A bolt and a base each have a budget of their
; own, accrued every frame and spent when a commit fits, so each runs at a rate
; the other two cannot move.
;
; IT WAS ONE CREDIT AND THE FIELD FOUND IT. The combat allowance used to be
; ADDED to the share, which meant the wheel let more IDLE commits through while
; a bolt was flying - press A and all twenty figures speed up, measured at 3.5
; to 5.4 fps a feature. The bolt's own speed was never the thing that changed.
TI_COMBAT   equ 25                ; per cent of a frame the COMBAT lane may
                                  ; take - a bolt's step, a clash's tier B.
                                  ; TITHE-PLAN 3.8's concession (the other
                                  ; lanes stop idling to pay for an attack) was
                                  ; written against a frame that was full, and
                                  ; it is not: an idle at 20% leaves room for
                                  ; an attack BESIDE it rather than instead
TI_BASESHARE equ 12               ; ...and per cent the BASE lane may take.
                                  ; There are only ever THREE bases in the
                                  ; game against twenty characters, so frames
                                  ; for one are art nobody has to draw twenty
                                  ; times: TI_BASEPOSES is four times
                                  ; TI_POSES and this lane plays them at two
                                  ; and a half times the wheel's rate, which
                                  ; is what "smoother" costs
TI_BTN      equ 7                 ; base 1's share of the base lane's commits
TI_BTD      equ 15                ; ...out of this many. 7/15 gives the two
                                  ; bases constant rates 1.14x apart with
                                  ; NEITHER ever repeating a pose (SPEC.md
                                  ; 97.5.1) - the whole cadence difference is
                                  ; in how often each is visited, never in a
                                  ; visit that draws the same picture again
TI_FRAMEUS  equ 54925             ; one system tick, in microseconds
TI_FRAMEMAX equ 75                ; per cent of a tick the lanes may plan to
                                  ; use between them - the rest is the frame's
                                  ; own overhead and the model's error. A
                                  ; reveal spends the gap between this and the
                                  ; lanes' shares before it slows the idle
                                  ; (tirv.inc)
TI_COMBATUS equ TI_FRAMEUS * TI_COMBAT / 100
TI_BASEUS   equ TI_FRAMEUS * TI_BASESHARE / 100
TI_CALN     equ 8                 ; samples the calibration takes, ONE BLIT
                                  ; EACH (SPEC.md 97.5)

; =============================================================================
; ti_entry - package entry (SPEC.md 20.2)
; in:  DS=ES=KERNEL_SEG, IF=1, gfx lock NOT held
; out: BX = window ptr, CF set = refused
;
; NOTHING IS LAID OUT OR SPAWNED HERE, and it cost a session to learn why the
; obvious spelling does not work. The window exists the instant wm_create
; returns and is not VISIBLE until the LOADER shows it, which is after this
; proc has returned - so OSAPI_WM_GEOM answers CF=1 here, and OSAPI_TASK_SPAWN
; refuses outright because the loader has not published this instance yet.
; Both wait for the first paint, which is where ti_relayout_ck and ti_spawn_ck
; are. `apps/dotdel/dotdel.asm`'s entry proc is the same three sentences one
; game along, and the symptom of ignoring them is a window that opens as a
; sliver saying it is too small for a board.
; =============================================================================
ti_entry:
    call op_load                    ; THE ART PART, FIRST: SI is the kernel's
    jc .refused                     ; name buffer and nothing later can read
                                    ; it (SPEC.md 20.12, os88parts.inc rule 1).
                                    ; A refusal has already said why
    push si
    call tg_new                     ; THE MATCH: every view the renderer draws
                                    ; is the engine's (tigame.inc), so it is
                                    ; dealt before anything is built from them
    call ti_arena_claim             ; THE ARENA NEXT (tiplace.inc): a machine
    jc .out                         ; that cannot hold the board is refused
                                    ; before a window exists to be empty
    mov si, ti_tpl
    call OSAPI_WM_CREATE
    jc .out
    mov [ti_win], bx
    OS88_REGION_MOVABLE             ; SPEC.md 66.6.1, here where the window
                                    ; exists: a package with no worker is the
                                    ; case that moves most easily, and putting
                                    ; this at the spawn leaves exactly those
                                    ; runs declaring nothing
    mov bx, [ti_win]
    mov al, 1
    call OSAPI_WM_SNAP              ; the content origin onto a multiple of 8
                                    ; (SPEC.md 11.94), which is what lets every
                                    ; cell's x be aligned without rounding
    mov si, ti_pref
    call OSAPI_WM_PREFER            ; preserves the flags, so the CF we owe the
                                    ; loader is still wm_create's
    mov bx, [ti_win]
    mov al, 1
    call OSAPI_WM_OWNBG             ; every pixel of the content is ours: the
                                    ; kernel's white fill would be one whole
                                    ; board of flash before the first frame
    mov bx, [ti_win]
    mov al, 1
    call OSAPI_WM_NOANIM            ; a zoom-open on a 450-pixel window is a
                                    ; second of nothing
    mov bx, [ti_win]
    mov ax, ti_onresize
    call OSAPI_WM_ONRESIZE          ; the box moved under us - a drag across a
                                    ; display seam is the case that matters
    mov si, ti_about
    call OSAPI_ABOUT_SET            ; SPEC.md 12.2, which SHEET and CHART both
                                    ; shipped without
    mov bx, [ti_win]
    clc
.out:
    pop si
    ret
.refused:
    stc
    ret

; -----------------------------------------------------------------------------
; ti_relayout - the layout and the art, together, because one decides the other
; Preserves every register. [ti_ok] says whether the box could hold a board.
; -----------------------------------------------------------------------------
ti_relayout:
    push ax
    mov byte [ti_rv], 0             ; a reveal's geometry is the layout's: it
    mov word [ti_rvn], 0            ; ends here, its card already in the cell,
    mov byte [ti_rvfull], 0         ; and the whole-window paint that follows
                                    ; leaves no spark behind
    mov word [ti_pjon], 0           ; ...and so do the BOLTS, whose positions
                                    ; are the old layout's
    mov word [ti_atkcell], -1       ; ...and no attack frame is owed: every
                                    ; cell is about to be built whole
    push cx                         ; ...and what every cell SHOWS, and its
    push di                         ; numbers, are the old layout's too: the
    push es                         ; paint after this records them again
    push ds
    pop es
    xor ax, ax
    mov di, ti_shseg
    mov cx, TI_CELLS
    cld
    rep stosw
    mov di, ti_stok
    mov cx, TI_CELLS
    rep stosb
    pop es
    pop di
    pop cx
    call ti_layout
    jc .no
    mov ax, [ti_face]               ; ...the face's shape, which the card
    call ti_face_set                ; composer reads on every row
    call ti_art_build
    call tm_run                     ; THE RELAYOUT IS SECONDS ON THE UI TASK
                                    ; with the gfx lock held, and the worker
                                    ; is blocked on that lock - so the music
                                    ; is stepped from HERE (timus.inc)
    call ti_phase_seed              ; ...and spread the clocks, so neighbours
                                    ; do not breathe together
    call ti_cal_card                ; ...and what a card costs to COMPOSE, which
                                    ; nothing else on the machine can see
    call tm_run
    mov byte [ti_ok], 1
    call ti_calibrate               ; ...AND WHAT A BAND COSTS AT THIS SIZE.
                                    ; It was the `R` key's alone, so the wheel
                                    ; ran on the GUESS for ever - 3,340 us
                                    ; against a real 4,000-plus - and a frame
                                    ; that believes it is inside its tick and
                                    ; is not overruns silently. The cost moves
                                    ; with the sprite arm, so it is re-taken
                                    ; wherever the layout is. Its scribble
                                    ; lands on the board, which W_PAINT draws
                                    ; immediately after
    jmp short .out
.no:
    mov byte [ti_ok], 0             ; a refusal is a normal path
                                    ; (PERFORMANCE.md rule 6): the window says
                                    ; so in words rather than drawing nothing
.out:
    mov byte [ti_dirty], 1
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_relayout_ck - cut the layout IF anything it depends on has moved
; in:  [ti_win]; called from W_PAINT with the lock held
; out: nothing; preserves every register
;
; THE GEOMETRY READ IS THE GATE, not a flag we set ourselves: a window that is
; not visible answers CF=1 and there is nothing to lay out against, which is
; exactly the state the entry proc is in. Two things move the answer and the
; box is only one of them - an adapter change re-rows the table without moving
; the content box at all - so both are compared.
; -----------------------------------------------------------------------------
ti_relayout_ck:
    push ax
    push bx
    push cx
    push dx
    push si
    call ti_georow                  ; SI = the row this machine wants; asked
                                    ; FIRST because it eats CX and DX
    mov bx, [ti_win]
    call OSAPI_WM_GEOM              ; CX = content w, DX = content h
    jc .out                         ; not visible: nothing to size against
    cmp byte [ti_laid], 0
    je .cut
    cmp si, [ti_geo]
    jne .cut
    cmp cx, [ti_cw_box]
    jne .cut
    cmp dx, [ti_ch_box]
    je .out
.cut:
    call ti_relayout                ; ti_layout banks the box it read, so a
    inc word [ti_nlay]              ; (a test WAITS on this: a relayout is
                                    ; over a second of an 8088 now, and a
                                    ; fixed sleep after `B` read the clocks
                                    ; before they were re-seeded)
    mov byte [ti_laid], 1           ; REFUSAL caches too - a box too small for
                                    ; a board is re-tested when it changes and
                                    ; not once a frame
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; the window callbacks
; =============================================================================

; ti_paint - W_PAINT: the board, then every feature at its current pose
ti_paint:
    push ax
    push bx
    push si
    mov [ti_win], si
    call ti_rv_lost                 ; a paint outside the worker's frame lands
                                    ; on the reveal's sparks (tirv.inc)
    call ti_relayout_ck             ; the box may have moved, or the adapter
    call ti_spawn_ck                ; changed under us - and on the FIRST paint
                                    ; this is where the layout happens at all
    cmp byte [ti_ok], 0
    je .refuse
    cmp byte [tg_ph], TG_PH_PLAN    ; BETWEEN TWO PLANNERS the window shows
    je .board                       ; the pass screen and nothing of either
    call tg_screen                  ; plan (tigame.inc)
    jmp short .out
.board:
    call ti_ground                  ; WF_OWNBG's other half, and only on a
                                    ; W_PAINT: the worker's frames touch the
                                    ; features and nothing around them
    call ti_board
    call ti_all
    jmp short .out
.refuse:
    mov si, ti_s_small
    call ti_say
.out:
    pop si
    pop bx
    pop ax
    ret

; ti_onresize - the box changed and we did not ask
ti_onresize:
    push si
    mov [ti_win], si
    mov byte [ti_laid], 0           ; MUST NOT DRAW here, and a full repaint
    pop si                          ; follows immediately - so the cheapest
    ret                             ; correct thing is to drop the cache and
                                    ; let ti_relayout_ck cut against the box
                                    ; the kernel has finished settling

; ti_onclick - the HUD's FRONT/REAR toggle, and otherwise one wheel pass
;
; THE TOGGLE IS THE ONLY CONTROL THE PROTOTYPE HAS A CLICK FOR, which is why
; this is a hit test and not a dispatcher: everything else on the surface is
; still a key (SPEC.md 97.7). Its arms are laid out from the RIGHT of the HUD
; and their x therefore depends on the two words' widths in whichever face is
; current, so `ti_hud_toggle` banks the boxes rather than letting this
; re-derive them.
ti_onclick:
    push ax
    push bx
    push cx
    push dx
    push si
    mov [ti_win], si
    cmp byte [ti_rv], 0             ; the toggle redraws the hand, which a
    je .norv                        ; reveal's sparks may be over
    jmp .out
.norv:
    cmp byte [ti_ok], 0
    jne .ok
    jmp .step
.ok:
    cmp byte [tg_ph], TG_PH_PLAN    ; the PASS screen: a click is the next
    je .plan                        ; player sitting down
    call tg_resume
    jmp .out
.plan:
    call OSAPI_MOUSE                ; CX = x, DX = y
    cmp byte [tg_list], 0           ; THE PLAN LIST where the hand was: a row
    je .hand                        ; clicked is an entry removed (tigame.inc)
    call tg_list_hit
    cmp al, 0FFh
    je .btn
    call tg_list_click
    jmp .out
.hand:
    call ti_card_hit                ; A CARD CLICKED IS A CARD PLAYED
    cmp ax, -1                      ; (SPEC.md 97.4.11) - the hovered one,
    je .btn                         ; which is the one the pointer is on - or
    call tg_card_click              ; an ORDER armed
    jmp .out
.btn:
    call tg_btn_hit                 ; PLAN/HAND and COMMIT (tigame.inc)
    cmp al, 1
    jne .ncommit
    call tg_list_toggle
    jmp .out
.ncommit:
    cmp al, 2
    jne .cell
    call tg_commit
    jmp .out
.cell:
    call ti_cell_hit                ; A CELL: an order's target, a stance, or
    cmp ax, -1                      ; one end of a swap
    je .hud
    call tg_cell_click
    jmp .out
.hud:
    mov ax, [ti_oy]
    cmp dx, ax
    jb .step
    add ax, [ti_hud]
    cmp dx, ax
    jae .step
    mov ax, [ti_hx]                 ; the band's own ALIGNED x, not ti_ox
    add ax, [ti_tg0x]
    cmp cx, ax
    jb .step
    mov bx, [ti_hx]
    add bx, [ti_tg1x]
    cmp cx, bx
    jb .front
    mov word [ti_row], TI_ROW_REAR
    jmp short .apply
.front:
    mov word [ti_row], TI_ROW_FRONT
.apply:
    call ti_row_apply
    jmp short .out
.step:
    call ti_spawn_ck
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_row_apply - the toggle moved, so the HUD and every card say so
; Preserves every register.
;
; EVERY CARD AND NOT ONLY THE HOVERED ONE: the row decides which pair of
; variable stats a card shows (97.4.8), so a toggle that redrew one card would
; leave six saying what they would have been in the other row. Seven blits and
; a HUD, once, on a control nobody clicks in a frame.
ti_row_apply:
    push ax
    cmp byte [ti_ok], 0
    je .out
    call ti_units_build             ; ...and which ITEM every card's unit
                                    ; holds (SPEC.md 97.4.9)
    call ti_hud_draw
    xor ax, ax
.card:
    cmp ax, [ti_cardn]
    jae .out
    push ax
    call ti_card_draw
    pop ax
    inc ax
    jmp short .card
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_onkey - W_ONKEY. SPEC.md 97.7 is the table.
; -----------------------------------------------------------------------------
ti_onkey:
    push ax
    push bx
    push si
    mov [ti_win], si
    cmp byte [ti_rv], 0             ; A REVEAL IS HALF A SECOND and every key
    je .keys                        ; that draws would land between its sparks
    jmp .out                        ; and their erase (tirv.inc)
.keys:
    mov bl, al
    or bl, 0x20
    cmp bl, 'p'
    jne .n_pause
    jmp .pause
.n_pause:
    cmp bl, 'f'
    jne .n_fs
    jmp .fs
.n_fs:
    cmp byte [tg_ph], TG_PH_PLAN    ; THE PASS SCREEN takes Enter or Space as
    je .plankeys                    ; the next player sitting down, and gives
    cmp al, 13                      ; nothing else away
    je .resume
    cmp al, ' '
    je .resume
    cmp bl, 'm'
    je .music
    cmp bl, 's'
    je .arm
    jmp .out
.resume:
    call tg_resume
    jmp .out
.plankeys:
    cmp bl, 'a'
    jne .n_fire
    jmp .fire
.n_fire:
    cmp bl, 'c'
    jne .n_clash
    jmp .clash
.n_clash:
    cmp bl, 'v'
    jne .n_reveal
    jmp .reveal
.n_reveal:
    cmp bl, 'b'
    jne .n_bart
    jmp .bart
.n_bart:
    cmp bl, 'g'
    jne .n_terr
    jmp .terr
.n_terr:
    cmp bl, 'm'
    jne .n_mus
    jmp .music
.n_mus:
    cmp bl, 'u'                     ; SPEC.md 97.7's `U`: the last action back
    jne .n_undo
    call tg_undo
    jmp .out
.n_undo:
    cmp bl, 'l'                     ; ...`L`: the plan as a list, or the hand
    jne .n_list
    call tg_list_toggle
    jmp .out
.n_list:
    cmp al, 13                      ; ...and Enter commits
    jne .n_commit
    call tg_commit
    jmp .out
.n_commit:
    cmp bl, 's'
    jne .n_arm
    jmp .arm
.n_arm:
    cmp bl, 'e'
    jne .n_rsel
    jmp .rsel
.n_rsel:
    cmp bl, 'r'
    jne .n_res
    jmp .res
.n_res:
    jmp .out
.rsel:                              ; SPEC.md 97.7's `E`: which RESOLUTION `R`
    mov al, [tm_rsel]               ; cuts in, named in the title
    inc al
    cmp al, TM_NRES
    jb .rs
    xor al, al
.rs:
    mov [tm_rsel], al
    add al, TM_NSONG
    call tm_title
    jmp .out
.res:                               ; SPEC.md 97.7's `R`: a fake ROUND - the
    cmp byte [tm_resing], 0         ; resolution cuts into whatever plays, and
    jne .rend                       ; the second press ends it: its tail, then
    mov al, TM_RQ_RES               ; the theme back where it was cut
    call tm_post
    mov al, [tm_rsel]
    add al, TM_NSONG
    call tm_title
    jmp .out
.rend:
    mov al, TM_RQ_END
    call tm_post
    mov al, [tm_sel]
    call tm_title
    jmp .out
.music:                             ; SPEC.md 97.7's `M`: the next title theme,
    mov al, [tm_sel]                ; and after the last of them, silence. The
    inc al                          ; worker starts it (timus.inc): the UI task
    cmp al, TM_NSONG                ; only posts
    jb .mset
    mov al, TM_OFF
.mset:
    mov [tm_sel], al
    call tm_post
    call tm_title
    jmp .out
.arm:                               ; SPEC.md 97.7's `S`: the SPEAKER even where
    xor byte [tm_spkonly], 1        ; FM is there - the one arm every machine
    mov al, [tm_sel]                ; has - and the song starts again on it
    call tm_post
    call tm_title
    jmp .out
.pause:
    xor byte [ti_paused], 1
    jmp .out
.fs:
    ; SPEC.md 97.7's `F`, and it is a REAL FULLSCREEN WINDOW (SPEC.md 11.2)
    ; rather than a geometry step inside an ordinary one. It used to be the
    ; latter because the fullscreen RENDERER (97.6) did not exist, and stepping
    ; the surface row inside a 640x355 content box mostly REFUSED - the
    ; fullscreen board of its day was 326 rows and its HUD another 36.
    ;
    ; WM_FULLSCREEN IS THE THIRD OPTION AND NOBODY HAD PRICED IT. A fullscreen
    ; surface IS a window (SPEC.md 11.2), so this keeps every kernel drawing
    ; slot: the whole 640x480 with no chrome and no 53.7 bracket, which is the
    ; PIXELS of fullscreen without the second renderer.
    mov al, [ti_full]
    xor al, 1
    mov bx, [ti_win]
    or al, al
    jz .fsoff
    mov al, 1
    call OSAPI_FULLSCREEN
    jc .out                         ; ...somebody else owns the screen
    mov byte [ti_full], 1
    jmp short .fsdone
.fsoff:
    mov byte [ti_full], 0           ; ...cleared BEFORE the call, so the repaint
    xor al, al                      ; the exit triggers sizes the windowed row
    call OSAPI_FULLSCREEN
.fsdone:
    mov byte [ti_laid], 0
    call ti_relayout_ck
    cmp byte [ti_ok], 0             ; THE LAYOUT MOVED, so the ground goes down
    je .fsp                         ; first: the fullscreen hand centres the
    call ti_ground                  ; board, and a strip's cards and a base
.fsp:                               ; left where they were read as two boards
    call ti_paint_now
    jmp .out
.clash:
    call ti_cl_fire                 ; SPEC.md 97.7's `C`: a melee clash in the
    jmp .out                        ; front line of one lane
.reveal:
    call ti_rv_key                  ; SPEC.md 97.7's `V`: play a card into its
    jmp .out                        ; cell (SPEC.md 97.4.11)
.fire:
    xor byte [ti_pjrep], 1          ; SPEC.md 97.7's `A`: bolts across a lane,
    cmp byte [ti_pjrep], 0          ; at the real cost, over a real board. It
    je .out                         ; SUSTAINS rather than firing one, because
    call ti_pj_fire                 ; the number wave 1a wants is the COMBAT
    jmp .out                  ; FRAME's - one bolt is a photograph
.terr:                              ; SPEC.md 97.7's `G`: the next BOARD. The
    mov ax, [ti_terr]               ; terrain is composed at ROUND LOAD, which
    inc ax                          ; for wave 1a is the layout - so this forces
    cmp ax, TI_TERRAINS             ; one, the same way `B` does for the bases
    jb .terrset
    xor ax, ax
.terrset:
    mov [ti_terr], ax
    mov bx, ax                      ; each board has its own RESOLUTION
    mov al, [ti_terr_res + bx]      ; (SPEC.md 97.10.7): the next `R` cuts
    mov [tm_rsel], al               ; in the new board's, and `E` still steps
    mov byte [ti_laid], 0
    call ti_relayout_ck
    call ti_paint_now
    jmp .out
.bart:                              ; SPEC.md 97.2.1's `B`: the next base
    mov ax, [ti_bart]               ; candidate. It relayouts because the art
    inc ax                          ; is built at layout, and it forces the
    cmp ax, TI_BART_N               ; layout because nothing it depends on has
    jb .bartset                     ; moved - the box and the surface are the
    xor ax, ax                      ; same, so ti_relayout_ck would skip
.bartset:
    mov [ti_bart], ax
    mov byte [ti_laid], 0
    call ti_relayout_ck
    call ti_paint_now
    jmp .out
.out:
    pop si
    pop bx
    pop ax
    ret

; ti_paint_now - repaint from a key handler, which already holds the lock
ti_paint_now:
    push si
    cmp byte [ti_ok], 0
    je .out
    cmp byte [tg_ph], TG_PH_PLAN
    je .board
    call tg_screen
    jmp short .out
.board:
    call ti_board
    call ti_all
.out:
    pop si
    ret

; ti_say - SI = a NUL string, drawn where a refusal can be read
ti_say:
    push ax
    push bx
    push cx
    push dx
    mov bx, [ti_win]
    call OSAPI_WM_CONTENT
    mov cx, ax
    mov dx, dx
    add cx, 8
    add dx, 8
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_spawn_ck - start the worker, once, from a window callback with the lock
;               held - which is what OSAPI_TASK_SPAWN requires and what an
;               entry proc is not
; Preserves every register. A refusal is TRANSIENT (the task table is full),
; so the flag is set only on success and the next paint tries again.
; -----------------------------------------------------------------------------
ti_spawn_ck:
    cmp byte [ti_spawned], 0
    jne .out
    push ax
    push bx
    mov ax, ti_worker
    mov bx, [ti_win]
    call OSAPI_TASK_SPAWN
    jc .no
    mov byte [ti_spawned], 1
    OS88_WORKER_RESTARTABLE ti_worker
                                    ; ...AND THE REGION CANNOT MOVE WITHOUT
                                    ; THIS (SPEC.md 66.6.2): the kernel wrote
                                    ; our segment into this worker's frame
                                    ; before its first instruction, so a
                                    ; region with an undeclared worker is
                                    ; pinned however the region is declared.
                                    ; The park is at OSAPI_TASK_ALIVE, which
                                    ; is the TOP of the loop, and every byte
                                    ; that outlives a pass is a static
.no:
    pop bx
    pop ax
.out:
    ret

; =============================================================================
; ti_worker - the frame
;
; The render runs once a tick - 18.2 Hz, flat, on every adapter - because that
; is the fastest clock this machine has that costs nothing to read. What the
; wheel does inside a tick is SPEC.md 97.5's, and the credit it spends was
; measured on this machine by ti_calibrate rather than modelled.
; =============================================================================
ti_worker:
    call OSAPI_GET_TICKS
    mov [ti_last], ax
.loop:
    mov bx, [ti_win]
    call OSAPI_TASK_ALIVE           ; the lock must NOT be held here; a clicked
                                    ; close box never returns
    call tm_run                     ; THE MUSIC FIRST, and outside the lock
                                    ; (timus.inc): a frame waiting on the gfx
                                    ; lock must never hold a note up
    cmp byte [ti_rpq], 0            ; A WHOLE REPAINT, asked for from OUTSIDE:
    je .norp                        ; the tests write this byte to compare the
    cmp byte [ti_ok], 0             ; glass a frame left against the board
    je .norp                        ; drawn from nothing. It was `D` pressed
    call OSAPI_GFX_LOCK             ; twice, and `D` is gone with the detail
    mov bx, [ti_win]                ; arm; a key is a player's, a byte is not
    call OSAPI_WM_CLIP_SET
    jc .rpun
    call ti_paint_now
    call OSAPI_WM_CLIP_CLEAR
.rpun:
    mov byte [ti_rpq], 0
    call OSAPI_GFX_UNLOCK
.norp:
    cmp byte [tg_fillq], 0          ; THE TESTS' FULL BOARD (tigame.inc's
    je .nofill                      ; tg_fill), the same way
    cmp byte [ti_ok], 0
    je .nofill
    call OSAPI_GFX_LOCK
    mov bx, [ti_win]
    call OSAPI_WM_CLIP_SET
    jc .flun
    call tg_fill
    call OSAPI_WM_CLIP_CLEAR
.flun:
    mov byte [tg_fillq], 0
    call OSAPI_GFX_UNLOCK
.nofill:
    cmp byte [ti_paused], 0
    jne .sleep
    cmp byte [ti_ok], 0
    je .sleep
    cmp byte [tg_ph], TG_PH_PASS    ; the pass screen has no frame to draw
    je .sleep
    cmp byte [tg_ph], TG_PH_OVER
    je .sleep
    call OSAPI_GET_TICKS
    cmp ax, [ti_last]
    je .sleep                       ; the tick has not turned over: nothing is
    mov [ti_last], ax               ; due, and a frame that draws nothing is a
                                    ; frame that costs nothing
    call OSAPI_GFX_LOCK
    mov bx, [ti_win]
    call OSAPI_WM_CLIP_SET          ; A WORKER ARRIVES WITH NO REGION ARMED
    jc .unlk                        ; (SPEC.md 11.3) - only W_PAINT is handed
                                    ; one, so without this the frame draws
                                    ; straight over whatever is on top of us,
                                    ; and CF=1 means the window has gone
    cmp byte [tg_ph], TG_PH_PLAN    ; ...AND ASKED AGAIN UNDER THE LOCK: a
    je .fr                          ; commit that landed while this task waited
    cmp byte [tg_ph], TG_PH_RES     ; for it has put the pass screen up, and a
    jne .nofr                       ; frame now would draw a base over it
.fr:
    call ti_frame
    call tg_res_step                ; ...and a round being fought, a step of
.nofr:                              ; it a frame (tigame.inc)
    call OSAPI_WM_CLIP_CLEAR
.unlk:
    call OSAPI_GFX_UNLOCK
.sleep:
    mov ax, 1
    call OSAPI_TASK_SLEEP
    jmp .loop

; -----------------------------------------------------------------------------
; ti_frame - ONE PASS OF THE PACING WHEEL (SPEC.md 97.5)
; in:  the gfx lock is held
;
; Walk from where it stopped, commit every feature whose clock is due,
; subtract that band's own cost, stop when the credit is spent, and REMEMBER
; THE POSITION. A feature that misses its slot is late by one frame and never
; slowed: its clock advances on the tick and not on how many neighbours drew.
; -----------------------------------------------------------------------------
ti_frame:
    push ax
    push bx
    push cx
    push dx
    call ti_rv_erase                ; THE REVEAL'S SPARKS COME OFF FIRST and go
                                    ; back on LAST, so every band between lands
                                    ; on a clean glass (tirv.inc)
    call ti_hover_ck                ; the pointer moved between cards, so BOTH
    jnc .credit                     ; of them are redrawn - the one it left
    call ti_hud_status              ; ...and the STATUS LINE either way, the
                                    ; board's own hover changing nothing else
                                    ; (SPEC.md 97.4.8). THE BLOCK AND NOT THE
                                    ; STRIP: the round, the phase and the
                                    ; toggle have not moved, and blitting them
                                    ; again was three quarters of a hover's
                                    ; work - 4.9 frames a second down the card
                                    ; list against 18.7 parked
    cmp word [ti_hovold], -1        ; and the one it arrived on. Only the first
    je .gain                        ; was, and the second was left to feature
    mov ax, [ti_hovold]             ; 22 - which draws the UNIT ALONE, at a box
    call ti_card_draw               ; ti_card_draw banks and nothing had banked
    call tm_run                     ; (a card is the frame's longest single
                                    ; draw: the music is stepped after each)
.gain:                              ; for the new card. So a hover animated
    cmp word [ti_hover], -1         ; only while a full repaint happened to
    je .credit                      ; have set the box up, which on the glass
    mov ax, [ti_hover]              ; is "it worked for one frame"
    call ti_card_draw
    call tm_run
.credit:
    call OSAPI_GET_TICKS            ; THE FRAME IS TIMED, because the model
    mov [ti_ft0], ax                ; under-prices what a commit really costs -
    inc word [ti_nframe]            ; commits ALONE cannot say whether the
                                    ; wheel is credit-limited or work-limited,
                                    ; and the two want opposite fixes
    mov bx, ti_cacc                 ; every lane accrues ONCE a frame, before
    mov dx, TI_COMBATUS             ; any of them spends (SPEC.md 97.5.1)
    call ti_lane_fill
    mov bx, ti_bacc
    mov dx, TI_BASEUS
    call ti_lane_fill

    ; --- THE COMBAT LANE ----------------------------------------------------
    cmp byte [ti_clash], 0          ; the clash is both fighters' bands, on
    je .nocl                        ; the combat lane's credit
    mov ax, [ti_bh]                 ; both fighters' bands, every frame
    mul word [ti_rowus]             ; of it, so the swing plays at the frame
    add ax, [ti_arrus]              ; rate and not the idle wheel's
    shl ax, 1
    mov bx, ti_cacc
    call ti_lane
    jc .cla
    call ti_cl_tiera
.cla:
    dec byte [ti_clash]             ; ...the TIMER runs whether or not the band
    jnz .nocl                       ; fitted, so a starved clash drops frames
    call ti_cl_tiera                ; ...and at its END both fighters go back
.nocl:                              ; fitted, so a starved clash drops frames
    mov byte [ti_pjgo], 0           ; rather than outstaying its animation
    call ti_pj_live                 ; --- THE BOLTS: paid for now, drawn after
    or ax, ax                       ; the wheel (ti_pj_frame)
    jnz .pj
    cmp byte [ti_pjrep], 0          ; ...and fired again while the arm is on
    je .nopj
    call ti_pj_fire
    mov ax, TI_PJN
.pj:
    call ti_pj_cost                 ; a band each, at what they really cost
    mov bx, ti_cacc
    call ti_lane
    jc .nopj
    mov byte [ti_pjgo], 1
.nopj:
    call ti_base_frame              ; --- THE BASE LANE, on its own clock -----

    call ti_credit                  ; --- THE IDLE WHEEL ----------------------
    mov ax, [ti_creditus]
    call ti_rv_cost_sub             ; ...less what the reveal owes this frame
    mov [ti_left], ax
    mov ax, [ti_racc]               ; THE RATE CAP (SPEC.md 97.5.2): the wheel
    add ax, [ti_rstep]              ; banks ti_rstep/256 steps a frame, so a
    mov dx, [ti_rstep]              ; machine with time to spare - a 286, or an
    shl dx, 1                       ; XT with a cheap adapter - draws the
    cmp ax, dx                      ; target rate and not the rate its credit
    jbe .rbank                      ; could buy. At most two frames banked, so
    mov ax, dx                      ; a frame the credit cut short is made up
.rbank:                             ; and a long stall is not burst through
    mov [ti_racc], ax
    mov cx, TI_FEATURES
.walk:
    or cx, cx
    jz .out
    cmp word [ti_racc], 256         ; ...and a step not yet due is not taken,
    jb .out                         ; whatever the credit says
    mov ax, [ti_wpos]
    inc ax
    cmp ax, TI_FEATURES
    jb .keep
    xor ax, ax
.keep:
    mov [ti_wpos], ax
    mov byte [ti_dok], 1            ; ...and a wheel pass is exactly a
    mov bx, ax                      ; transition, which is what the rect is a
    add bx, ti_clock                ; property of
    mov al, [bx]                    ; this feature's own phase counter
    inc al
    cmp al, TI_POSES
    jb .store
    xor al, al
.store:
    mov [bx], al
    mov ax, [ti_wpos]
    call ti_feature                 ; ...and the commit
    sub word [ti_racc], 256         ; ...a step spent
    call ti_cost                    ; ...charged at what THAT commit cost, not
                                    ; at a whole band's price (SPEC.md 97.5)
    cmp [ti_left], ax
    jbe .out                        ; the credit is the contract: overrun is
    sub [ti_left], ax               ; impossible by construction
    call tm_run                     ; THE MUSIC BETWEEN COMMITS: a frame that
                                    ; runs past its tick holds no note up
    dec cx
    jmp short .walk
.out:
    cmp byte [ti_pjgo], 0           ; ...the bolts, over what the wheel left
    je .nopjf
    call ti_pj_frame
    inc word [ti_npj]
    call tm_run
.nopjf:
    call ti_rv_atk                  ; ...a played cell's owed attack frame -
                                    ; BEFORE the reveal's step, so the frame a
                                    ; reveal ends in does not take one too
    call ti_rv_step                 ; ...and the reveal's frame, on top of it all
    call tm_run
    call ti_overran                 ; SPEC.md 97.5's own promise, and it was
    pop dx                          ; never built: the credit is trimmed when
    pop cx                          ; the frame missed its tick
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_overran - did this frame miss its tick, and trim the credit if it did
; Preserves every register.
;
; SPEC.md 97.5 says the credit is CALIBRATED and then WATCHED - one
; OSAPI_GET_TICKS a frame, 46.7 us, saying whether the frame overran. The
; watching half was never built, and it is what the model needs: `arrival +
; rows x R` prices the BLIT and not the commit around it, so a frame that
; fits on paper can take two ticks on the glass. It showed up the moment the
; idle's share came down and left room for a projectile beside it - the wheel
; let through ten cheap commits and a bolt, and the frame rate fell to 12.9
; from 18.6 while every number in the model said it fitted.
;
; A MULTIPLIER AND NOT A NEW MODEL. The shape of the cost is right - a shorter
; band really is cheaper, and both levers measure - so what is wrong is a
; scale, and one number carries it. It falls fast and recovers slowly, which
; is the way round that does not oscillate.
; -----------------------------------------------------------------------------
ti_overran:
    push ax
    push bx
    call OSAPI_GET_TICKS
    sub ax, [ti_ft0]                ; A CHANGED TICK IS AN OVERRUN, not one
    or ax, ax                       ; tick of slack. The worker only runs when
    jz .fit                         ; the tick has ALREADY turned over, so a
                                    ; frame starts at the top of one - and a
                                    ; frame still going when the next arrives
                                    ; has spent the whole tick, whatever the
                                    ; model thought it was spending. Read as
                                    ; `<= 1 is fine` the trim never fired at
                                    ; all and the frame sat at 12.8 passes a
                                    ; second against 18.6
    mov ax, [ti_trim]               ; missed: come down hard
    cmp ax, TI_TRIMMIN + 12
    jb .floor
    sub ax, 12
    jmp short .set
.floor:
    mov ax, TI_TRIMMIN
    jmp short .set
.fit:
    mov ax, [ti_trim]               ; fitted: creep back up, so a frame that
    cmp ax, 100                     ; overran once does not cost the rest of
    jae .out                        ; the session
    inc ax
.set:
    mov [ti_trim], ax
    call ti_credit
.out:
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_all - every feature, once: what a full repaint owes
; -----------------------------------------------------------------------------
ti_all:
    push ax
    push cx
    mov byte [ti_dok], 0            ; a full board owes WHOLE bands: there is
    xor ax, ax                      ; no transition behind a repaint
.f:
    cmp ax, TI_FEATURES
    jae .out
    push ax
    call ti_feature
    pop ax
    call tm_run                     ; a whole board is a second or two of
    inc ax                          ; blits, on whichever task asked for it
    jmp short .f
.out:
    call ti_base_all                ; the bases are off the wheel, so a full
    pop cx                          ; board has to ask for them
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_feature - commit feature AX: ONE opaque band, ground baked in
; Preserves every register.
; -----------------------------------------------------------------------------
ti_feature:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    cmp ax, TI_CELLS                ; 0..19 are the characters and 20 is the
    jb .cell                        ; moused-over card. THE TWO BASES ARE NOT
.hand:                              ; HERE: they are a lane of their own
    cmp word [ti_hover], -1         ; 22 is the MOUSED-OVER CARD, the one
    jne .hov
    jmp .out
.hov:                               ; feature that is not a character - and
    mov bl, [ti_clock + TI_CELLS]   ; what animates on it is the UNIT, not the
    xor bh, bh                      ; card, on THIS FEATURE's clock - the one
                                    ; the wheel just stepped. It read the
                                    ; clock of the board CELL with the card's
                                    ; index, which steps when that cell does,
                                    ; so a pause could hold a pose a repaint
                                    ; of the same card would not draw
    mov [ti_pi], bx
    mov ax, [ti_hover]              ; ...and the character it plays (97.4.9)
    call ti_ck_card
    mov ax, [ti_hovbx]
    mov [ti_cbx], ax
    mov ax, [ti_hovbw]
    mov [ti_cbw], ax
    mov ax, [ti_hovy]
    mov [ti_cardy], ax
    mov ax, (CBLACK << 8) | CWHITE  ; A HOVERED CARD IS WHITE INK ON BLACK
    call OSAPI_GFX_BLIT1_PEN        ; PAPER, and this said the opposite - so
    call ti_unit_draw               ; the composition put the figure down
                                    ; right and the very next frame put it
                                    ; down inverted, which on the glass is a
                                    ; figure that goes black part of the way
                                    ; round its cycle
    mov ax, (CBLACK << 8) | CWHITE
    call OSAPI_GFX_BLIT1_PEN
    jmp .out
.cell:
    cmp byte [ti_rv], 0             ; THE REVEAL OWNS ITS TARGET CELL until the
    je .cown                        ; character has dissolved in (tirv.inc),
    cmp ax, [ti_rvcell]             ; and a paint in the meantime shows the
    jne .cown                       ; ground the board strip already drew
    jmp .out
.cown:
    mov [ti_ci], ax
    mov bx, ax
    add bx, ti_clock
    mov al, [bx]
    xor ah, ah
    mov [ti_pi], ax
    mov ax, [ti_ci]                 ; ...and WHICH CHARACTER stands here
    call ti_ck_cell                 ; (SPEC.md 97.4.9)
    cmp word [ti_ck], 0FFh          ; AN EMPTY CELL IS NOT A FEATURE on the
    jne .occ                        ; wheel - its bands are ground and nothing
    cmp byte [ti_dok], 0            ; moves on them - but a whole repaint owes
    je .occ                         ; its ground like any other
    jmp .out
.occ:
    call ti_cellpose_addr           ; DI = THIS CELL's pose, in the arena -
    mov si, di                      ; composed over its own column's ground
    mov ax, [ti_ci]                 ; ...which item it holds, for its rows
    call ti_cell_stance
    mov ax, [ti_ci]
    call ti_cell_xy                 ; AX = the cell's x, BX = its y
    push ax                         ; ...and the figure's own inset inside it,
    mov ax, [ti_ci]                 ; which is P2's MIRROR in columns 2 and 3
    xor dx, dx                      ; (SPEC.md 97.4.9)
    mov cx, TI_ROWS
    div cx
    call ti_col_insx
    mov cx, ax
    pop ax
    add ax, cx
    add bx, [ti_insy]
    mov es, [ti_aseg]
    mov dx, [ti_bh]
    push ax                         ; A FIGHTER IN A CLASH SWINGS: its band is
    mov ax, [ti_ci]                 ; the ATTACK frame the clash is on, out of
    call ti_cl_mine                 ; the attack claim, and it owes the whole
    jnc .idle                       ; band - an attack is not a transition
    push di                         ; the idle's rows describe
    push word [ti_pi]
    call ti_cl_frame
    mov [ti_pi], ax
    call ti_cellpose_addr
    mov si, di
    pop word [ti_pi]
    pop di
    mov es, [ti_kseg]
    pop ax
    call ti_shown_set               ; WHAT THE CELL SHOWS, for a band that
    jmp short .rows                 ; crosses it (ti_pic_band)
.idle:
    pop ax
    call ti_shown_set
                                    ; THE DIRTY RECT (SPEC.md 97.4.3): commit
                                    ; the rows this TRANSITION moved and not
    cmp byte [ti_dok], 0            ; the whole figure. Only the WHEEL may use
    je .rows                        ; it - a board repaint has no transition
                                    ; behind it and owes the whole band
    push ax
    call ti_dirty_rows              ; ...and they are THIS CHARACTER's. They
    mov cl, al                      ; were read at the pose alone, which was
    mov dl, ah                      ; the first character's rows for all three
    xor dh, dh                      ; - so a censer that swung wider than a
    pop ax                          ; shield left its tip on the glass
    or dx, dx
    jz .out                         ; this transition moved nothing at all
    push ax
    push dx
    mov al, cl
    xor ah, ah
    add bx, ax
    mul word [ti_bs]
    add si, ax
    pop dx
    pop ax
.rows:
    mov cx, [ti_bw]
    mov bp, [ti_bs]
    call OSAPI_GFX_BLIT1            ; one pen a character and one blit
    inc word [ti_ncommit]           ; WHAT THE WHEEL ACTUALLY ACHIEVES, counted
                                    ; rather than modelled: commits a guest
                                    ; second is the number TITHE-PLAN 1.3 is in
                                    ; and the number wave 1a's gate is against
.out:
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; ti_calibrate - what a band costs ON THIS MACHINE (SPEC.md 97.5)
;
; TWO HEIGHTS, because a band's cost is NOT flat in its height. The model is
; `arrival + rows x R`, and calibrating only the full band collapses it to a
; constant - which is exactly what made the dirty rect and the sprite arms
; measure as worth NOTHING: the wheel charged a whole band's price for a
; half-height commit, drew the same twenty-three features and finished its
; frame earlier. Timing ONE row and BH rows separates the two terms, and the
; wheel then charges what a commit actually cost.
;
; ONE BLIT PER PIT SPAN. Counter 0 counts down and reloads every 54.9 ms, so a
; span holding sixteen 4 ms blits wraps and its subtraction means nothing - the
; first version of this read 0 us a band, the credit became a number the wheel
; could not divide by, and the frame overran its tick in silence. Eight
; single-blit samples accumulate to well under 65,535 counts.
;
; THE PIT IS LATCHED AND NOT REPROGRAMMED. Control word 00h freezes a copy for
; reading and changes neither the mode nor the reload value, so the system
; tick is undisturbed; tests/benchlib.inc's bl_pit is the same read.
;
; It is re-taken wherever the LAYOUT is, because the cost moves with the
; sprite arm. Its scribble lands on the board, which W_PAINT draws immediately
; after.
; =============================================================================
ti_calibrate:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    cmp byte [ti_ok], 0
    je .out

    mov ax, [ti_bh]
    call ti_cal_one                 ; AX = us for a whole band
    mov [ti_calfull], ax
    mov ax, 1
    call ti_cal_one                 ; ...and for a single row of it
    mov [ti_calone], ax

    mov ax, [ti_calfull]            ; the per-ROW term
    sub ax, [ti_calone]
    jnc .pos
    xor ax, ax
.pos:
    mov bx, [ti_bh]
    dec bx
    or bx, bx
    jnz .div
    inc bx
.div:
    xor dx, dx
    div bx
    or ax, ax
    jnz .rok
    inc ax
.rok:
    mov [ti_rowus], ax

    mov bx, ax                      ; ...and what is left of one row is the
    mov ax, [ti_calone]             ; ARRIVAL
    sub ax, bx
    jnc .arr
    xor ax, ax
.arr:
    mov [ti_arrus], ax

    mov ax, [ti_calfull]
    or ax, ax
    jnz .have
    inc ax                          ; a machine too fast to measure this way
.have:                              ; still gets a credit it can divide by
    mov [ti_bandus], ax
    call ti_credit
.out:
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_cal_one - microseconds for ONE blit of AX rows of the pose band
; out: AX = us; every other register preserved
; -----------------------------------------------------------------------------
ti_cal_one:
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    mov [ti_calrows], ax
    mov word [ti_calacc], 0
    mov cx, TI_CALN
.b:
    push cx
    pushf
    cli                             ; the span must not have a tick ISR in it
    call ti_pit
    mov [ti_t0], ax
    mov word [ti_pi], 0
    mov word [ti_ci], 0
    call ti_cellpose_addr           ; any pose will do: it is the SHAPE that
    mov si, di                      ; is being priced
    mov es, [ti_aseg]
    mov ax, [ti_bx]
    mov bx, [ti_by]
    mov cx, [ti_bw]
    mov dx, [ti_calrows]
    mov bp, [ti_bs]
    call OSAPI_GFX_BLIT1
    call ti_pit
    mov bx, [ti_t0]
    sub bx, ax                      ; counter 0 counts DOWN: start - end, and
    popf                            ; modular, over ONE blit which cannot wrap
    add [ti_calacc], bx
    pop cx
    call tm_run                     ; BETWEEN samples, never inside one: a
    loop .b                         ; span is one blit, read either side

    mov ax, [ti_calacc]             ; counts -> microseconds: one count is
    xor dx, dx                      ; 0.8381 us, so us = counts * 8381 / 10000
    mov cx, 8381
    mul cx
    mov cx, 10000
    div cx
    xor dx, dx
    mov cx, TI_CALN
    div cx
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; ti_credit - the IDLE WHEEL's credit, from its share and the measured band
; Preserves every register.
;
; THE SHARE IS THE IDLE'S AND NOTHING ELSE DRAWS ON IT (SPEC.md 97.5.1). The
; combat allowance used to be added here while a bolt or a clash was in
; flight, which is what made pressing A speed the whole BOARD up: the wheel
; had more credit, so it reached more figures, so twenty idles that were never
; part of the attack ran half as fast again. What an attack needs is a budget
; beside this one, not a bigger one of this.
; -----------------------------------------------------------------------------
ti_credit:
    push ax
    push dx
    push cx
    mov ax, TI_FRAMEUS
    xor dx, dx
    mov cx, 100
    div cx
    mov cx, [ti_share]
    mul cx                          ; AX = the share of one frame, in us
    mov cx, [ti_trim]               ; ...less what the last overrun taught us
    mul cx
    mov cx, 100
    div cx
    or ax, ax
    jnz .have
    inc ax
.have:
    mov [ti_creditus], ax
    mov ax, [ti_fps10]              ; ...and the RATE's allowance: steps a
    mov dx, TI_FEATURES             ; frame x 256 = FEATURES x fps / 18.2065,
    mul dx                          ; the fps in tenths, so x 25,600 / 18,207
    mov cx, 25600
    mul cx
    mov cx, 18207
    div cx
    mov [ti_rstep], ax
    pop cx
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_lane_fill - accrue DX into the lane at BX, once a frame
; in:  BX -> the lane's accumulator word, DX = what it accrues each frame
; Preserves every register.
;
; A LANE'S OWN CLOCK, IN ONE PROC (SPEC.md 97.5.1). A lane accrues its
; allowance every frame and spends it when a commit fits, so its rate is
; `allowance / cost` commits a frame and nothing outside the lane can move it -
; which is the whole of what the field asked for twice over: the bolt keeps
; its speed while the board idles at its own, and a base plays four times the
; frames at two and a half times the rate.
;
; IT BANKS AT MOST TWO FRAMES. A lane that has been quiet for a second would
; otherwise wake with a second's allowance in hand and burst through it, which
; on the glass is the thing it exists to prevent.
; -----------------------------------------------------------------------------
ti_lane_fill:
    push ax
    push cx
    mov ax, [bx]
    add ax, dx
    mov cx, dx
    add cx, dx
    cmp ax, cx
    jbe .keep
    mov ax, cx
.keep:
    mov [bx], ax
    pop cx
    pop ax
    ret

; ti_lane - spend AX from the lane at BX. CF=1 it does not fit this frame.
; Preserves every register bar the flags.
ti_lane:
    push cx
    mov cx, [bx]
    cmp cx, ax
    jb .no
    sub cx, ax
    mov [bx], cx
    clc
    jmp short .out
.no:
    stc
.out:
    pop cx                          ; `pop` writes no flag
    ret

; -----------------------------------------------------------------------------
; ti_cost - what the commit just made cost, in microseconds
; out: AX; preserves every other register
;
; SPEC.md 97.5: `arrival + rows x R`, and the ROWS are the ones actually put
; down - which is the whole of why the dirty rect and the sprite arms show up
; in the rate at all. Charging a constant made a half-height commit cost what a
; full one did, so the wheel drew the same twenty-three features and finished
; its frame earlier, and both levers measured at ZERO.
; -----------------------------------------------------------------------------
ti_cost:
    push bx
    push dx
    cmp word [ti_wpos], TI_CELLS    ; an empty cell committed nothing
    jae .occ
    mov ax, [ti_wpos]
    call ti_ck_cell
    mov ax, 1
    cmp word [ti_ck], 0FFh
    je .out
.occ:
    mov ax, [ti_bh]                 ; WHAT THE COMMIT PUT DOWN, and the dirty
                                    ; rect is always on (SPEC.md 97.4.3) - bar
    push ax                         ; a fighter's swing, which is the band
    mov ax, [ti_ci]
    call ti_cl_mine
    pop ax
    jc .rows
    call ti_dirty_rows              ; AH = this character's rows for this move
    mov al, ah                      ; - charged honestly, because the RATE is
    xor ah, ah                      ; capped by ti_fps10 and not by the credit
.rows:                              ; (SPEC.md 97.5.2): a cheaper commit is
    mul word [ti_rowus]             ; room to reach the target, never a faster
                                    ; idle than it
    add ax, [ti_arrus]
    or ax, ax
    jnz .out
    inc ax                          ; never zero: a credit it cannot divide by
.out:                               ; is a wheel that never stops
    pop dx
    pop bx
    ret

; ti_pit - latch and read counter 0 of the 8253 (a READ, not a reprogram)
; out: AX = the counter. Every caller has IF = 0: a latch interrupted between
;      the two byte reads returns a torn count.
ti_pit:
    push dx
    mov al, 0
    out 0x43, al
    jmp short $+2                   ; I/O settling, the period-hardware idiom
    in al, 0x40
    mov dl, al
    jmp short $+2
    in al, 0x40
    mov ah, al
    mov al, dl
    pop dx
    ret

%include "tifaces.inc"
%include "titxt.inc"
%include "tibases.inc"
%include "tiart.inc"
%include "tiground.inc"
%include "tilay.inc"
%include "tirend.inc"
%include "ticard.inc"
%include "tipj.inc"
%include "ticl.inc"
%include "tirv.inc"
%include "ticards.inc"
%include "tirule.inc"
%include "tigame.inc"
%include "tiplace.inc"
%include "tisong.inc"
%include "timus.inc"
%include "os88parts.inc"

; THE ART IS A PART (SPEC.md 20.12, TITHE-PLAN 4.3): the bodies, the items, the
; card manifest and the dirty rows, out of tools/os88tithechar.py. It left the
; image the moment characters became layers - a package's image and bss cap at
; 60KB together, and the program was 59KB of it with three figures. OP_COMP,
; because pixel art packs 2.4 to 1 and it expands into the claim at load.
; THE MUSIC IS A PART TOO (TITHE-PLAN 13.6, SPEC.md 97.10): the score lives
; with what it belongs to rather than in the image, and tools/os88tithemus.py
; builds it. Every song in it is sequenced out of the part where it lies.
    OS88_PARTS_BEGIN 2
      OS88_PART OP_ASSET, OP_COMP     ; 0 the characters
      OS88_PART OP_ASSET, OP_COMP     ; 1 the music (TM_PART)
    OS88_PARTS_END

; =============================================================================
; data
; =============================================================================

ti_tpl:
    dw 0, 30, 640, 355
    dw ti_ttl, ti_paint, ti_onkey, ti_onclick

; --- the preferred frame, PER ADAPTER ---------------------------------------
; THE WIDTH IS THE WHOLE DISPLAY, ON PURPOSE (SPEC.md 11.95.2). A window whose
; x is its display's first column and whose width spans it loses BOTH side
; borders - `wm_flush_ck` - so its content starts at W_X, which is 0, and is
; 8-ALIGNED BY CONSTRUCTION. That matters here far more than it does for text:
; OSAPI_FONT_RUN on an unaligned origin is merely slower, while
; OSAPI_GFX_BLIT1 REFUSES an x off the byte grid outright, so an unaligned
; content origin is not a slow board, it is NO BOARD AT ALL.
;
; ASKING FOR *NEARLY* THE SCREEN IS THE WORST OF BOTH and is what this asked
; for first: 634 of 640 is not flush, so the window keeps its borders AND the
; snap that would align them is refused, because wm_snap_ax may only move a
; window LEFT except from x = 0..6, where moving right to 7 would push a
; 634-wide window off the edge. The content came out at x = 7 and every blit
; on the board refused in silence. Anything at or under 633 would have snapped;
; the whole display is better still, because it also hands back the two columns
; the borders were eating.
;
; The height is what the board NEEDS and no more. SPEC.md 11.100.1's advice to
; ask for a real width and a GENEROUS height is for a window whose content
; grows into whatever it is given, and this one's does not - the board's size
; is fixed by the table above, so a generous ask buys dead pixels. It bought
; 176 dead columns and 60 dead rows on a VGA.
ti_pref:                            ; VGA / Hercules / CGA (SPEC.md 11.100.1)
    dw 640, 390                     ; 624x363 of content needed - the board,
    dw 720, 293                     ; 712x266  and E rows of the front lane's
    dw 640, 163                     ; 632x136  lip and cliff under it
                                    ;          (SPEC.md 97.4.10)

; --- the stat icons (SPEC.md 97.4.1) ----------------------------------------
; 8x8 1bpp bands, bit 7 leftmost, a set bit LIT. One cell each, which is what
; makes an icon cost exactly as much room as the digit it labels.
ti_ic_cost: db 03Ch, 066h, 0DBh, 0DBh, 0DBh, 0DBh, 066h, 03Ch   ; a coin
ti_ic_atk:  db 018h, 018h, 018h, 018h, 07Eh, 018h, 018h, 03Ch   ; a sword
ti_ic_def:  db 0FFh, 0C3h, 0C3h, 066h, 066h, 03Ch, 018h, 000h   ; a shield
ti_ic_hp:   db 066h, 0FFh, 0FFh, 0FFh, 07Eh, 03Ch, 018h, 000h   ; a heart
ti_ic_soul: db 03Ch, 07Eh, 0DBh, 0FFh, 0E7h, 07Eh, 03Ch, 018h   ; a soul

ti_s_commit: db 'COMMIT', 0

ti_s_p1:    db 'P1', 0
ti_s_p2:    db 'P2', 0
ti_s_round: db 'ROUND ', 0
ti_s_front: db 'FRONT', 0
ti_s_rear:  db 'REAR', 0
ti_s_swap:  db 'SWAP ', 0

ti_p1hp:    db 0                   ; what the HUD shows, written by tigame.inc
ti_p1gold:  db 0                   ; off the engine's state at every edit
ti_p1soul:  db 0
ti_p2hp:    db 0
ti_p2gold:  db 0
ti_p2soul:  db 0
ti_round:   db 0

ti_ttl:     db 'Tithe', 0
ti_about:   db 'TITHE - wave 3, the round loop: hot-seat. SPEC.md 97.', 0
ti_s_small: db 'This window is too small for a board.', 0

ti_win:     dw 0
ti_nlay:    dw 0                  ; relayouts done, for tests/titheframe.py
ti_laid:    db 0                  ; ti_relayout_ck has cut against ti_geo +
                                  ; ti_cw_box/ti_ch_box as they stand
ti_ok:      db 0
ti_full:    db 0
ti_rpq:     db 0                    ; a whole repaint, requested (ti_worker)
ti_paused:  db 0
ti_spawned: db 0
ti_dirty:   db 0
ti_last:    dw 0
ti_t0:      dw 0
ti_wpos:    dw 0
ti_left:    dw 0
ti_creditus: dw 21970
ti_bandus:  dw 4800                 ; a starting guess, replaced by the first
                                    ; ti_calibrate - and it is only ever a
                                    ; guess until then (SPEC.md 97.5)
ti_share:   dw TI_SHARE
ti_fps10:   dw TI_IDLEFPS10         ; the idle's TARGET rate, a feature, tenths
ti_rstep:   dw 0                    ; ...as wheel steps a frame, x 256
ti_racc:    dw 0                    ; ...and banked, x 256
ti_geo:     dw 0
ti_ci:      dw 0
ti_pi:      dw 0
ti_ry:      dw 0

; --- the layout, filled by ti_layout ----------------------------------------
ti_cw:      dw 0
ti_ch:      dw 0
ti_rise:    dw 0
ti_bw:      dw 0
ti_bh:      dw 0
ti_bs:      dw 0
ti_hud:     dw 0
ti_pan:     dw 0
ti_panx:    dw 0
ti_basew:   dw 0                    ; a base zone's columns, each side
ti_baseh:   dw 0                    ; ...and its rows: three lanes
ti_bas:     dw 0                    ; ...and its band's stride in bytes
ti_b1x:     dw 0                    ; P1's base x, behind column 0
ti_b2x:     dw 0                    ; P2's, behind column 3
ti_bgap:    dw 0                    ; fullscreen: each base's gap to the board
ti_basey:   dw 0                    ; P1's base, a whole LIFT lower...
ti_basey2:  dw 0                    ; ...and P2's, at the board's top edge
ti_p1x:     dw 0                    ; the shear's empty corners, where each
ti_p1y:     dw 0                    ; player's gold and souls live
ti_p2x:     dw 0
ti_p2y:     dw 0
ti_cardh:   dw 0                    ; a hand row's height
ti_cardx:   dw 0
ti_cardw:   dw 0
ti_cardn:   dw 0
ti_cardpitch: dw 0
ti_cardi:   dw 0
ti_cardy:   dw 0
ti_cardp:   dw 0
ti_cardl2:  dw 0
ti_cgap:    dw 0                    ; the button row's offset from the hand
ti_unith:   dw 0                    ; the mini unit on a card
; --- THE FULLSCREEN HAND (SPEC.md 97.4.12): seven portrait cards along the
; bottom, the board centred above. ti_panx is card 0's x and ti_cardpitch the
; step ACROSS; a hovered card RISES by TI_HLIFT rather than widening, so every
; card's band is TI_HLIFT rows taller than the card and a resting card sits
; at the bottom of it.
ti_horiz:   db 0                    ; 1 = the hand is along the bottom
ti_hy:      dw 0                    ; the hand's band top
ti_cbrows:  dw 0                    ; rows of a card's BAND (card + lift)
ti_cbase:   dw ti_cardband          ; where the CARD's row 0 is in the band
ti_cmx:     dw 0                    ; the COMMIT column's box
ti_cmw:     dw 0
ti_picy:    dw 0                    ; the portrait's picture: its first card
ti_picb:    dw 0                    ; row, its first band byte and the bit
ti_cposx:   dw 0                    ; the card being drawn: its band's x
ti_cmsplit: dw 0                    ; the COMMIT column's UNDO/COMMIT row
ti_picsh:   dw 0                    ; shift that centres a figure the width
                                    ; of the board's in a card that is not
TI_CARDBANDMAX equ 12 * 128
; THE HUD IS A BAND TOO (97.4.8): the widest strip is Hercules' 712 pixels,
; which is 90 bytes and a pad, and the deepest is 28 rows.
TI_HUDBANDMAX equ 92 * 28
; ...and a CELL's stat column is 24 pixels wide (4 bytes with the pad) by at
; most four rows of the tallest face.
TI_CELLBANDMAX equ 6 * 40
ti_cardband: times TI_CARDBANDMAX db 0
ti_cbsrc:   dw ti_cardband          ; what ti_card_draw puts down
ti_cfband:  times TI_CARDBANDMAX db 0 ; a card the reveal is fading, composed
                                    ; once (tirv.inc)
ti_hudband: times TI_HUDBANDMAX db 0
ti_cellband: times TI_CELLBANDMAX db 0
ti_cellout: times TI_CELLBANDMAX db 0 ; ...and the same rows over their ground
ti_stmask:  times TI_CELLBANDMAX db 0 ; ...and their halo, which the stat bank
                                    ; keeps for a bolt to go under
%if TI_STATBANK + TI_CELLS * TI_STATREC > TI_ATTACKKB * 1024
    %error "the attack claim cannot hold the numbers' bank after its frames"
%endif
ti_cbs:     dw 0                    ; the band's stride, pad included
ti_crows:   dw 0                    ; rows of the chosen face that fit
ti_tw:      dw 0                    ; the flow's right margin - the card's
                                    ; width LESS the figure's own column
ti_tx:      dw 0                    ; the flow's pen
ti_ty:      dw 0
ti_tfull:   dw 0                    ; set when it has run out of rows
ti_cl:      dw 0                    ; the CARD's left edge inside the band,
                                    ; which is the panel's width: 0 for an
                                    ; expanded card and the margin for the rest
ti_cwd:     dw 0                    ; ...and the card's own width in it
ti_spx0:    dw 0                    ; ti_cb_span / ti_cb_vline's own ends,
ti_spx1:    dw 0                    ; in memory because the 8086 has not got
ti_spy1:    dw 0                    ; the registers for a masked byte run
ti_calc0:   dw 0                    ; ti_cal_card's PIT start...
ti_calconly: dw 0                   ; ...its compose-but-do-not-blit flag
ti_ccardus: dw 0                    ; ...and what one card costs to compose
ti_nbs:     dw 0                    ; the cell column's band stride,
ti_nrows:   dw 0                    ; how many rows of it are used,
ti_nh:      dw 0                    ; how tall that is,
ti_nrec:    dw 0                    ; the card behind the cell,
ti_nrow:    dw 0                    ; and which of its two stat pairs
ti_uk:      dw 0                    ; the hand slot whose unit and portrait
                                    ; cache a card view draws from
ti_ck:      dw 0                    ; the CHARACTER a band is being built
                                    ; for (SPEC.md 97.4.9)
ti_uslot:   dw 0                    ; ...and the mini unit's slot pitch
ti_terr:    dw 0                    ; which BOARD we are fighting on
ti_terr_res:                        ; ...and the resolution each one cuts in
    db TM_R_RESCHARGE               ; THE MARCH: the gallop across open ground
    db TM_R_RESTOLL                 ; THE CLOISTER: the bell over the stones
%if $ - ti_terr_res != TI_TERRAINS
%error "a board without a resolution: ti_terr_res wants a row per terrain"
%endif
                                    ; (SPEC.md 97.4.10)
%ifdef TICARDPROF
; TICARDPROF - what each stage of ONE card costs, in PIT counts (0.8381 us
; each), for the last card drawn. It is a knob and not a counter because the
; thing it had to settle was WHICH STAGE: a hover was costing two frames and
; every whole-frame A/B said "the card draw", which is a routine and not an
; answer. These said `ti_cb_frame` was 36-44 ms of it - a rectangle - against
; 4.2 ms for the blit of the finished card.
ti_cp0:     dw 0
ti_ccomp:   dw 0                    ; the whole composition...
ti_cblit:   dw 0                    ; ...and the arrival that puts it down
ti_pclear:  dw 0                    ; ...then stage by stage
ti_pframe:  dw 0
ti_pframe2: dw 0
ti_ptext:   dw 0
ti_punit:   dw 0
ti_pinv:    dw 0
%endif
ti_row:     dw 0                    ; FRONT or REAR - which row a played card
                                    ; is going into, and so which pair of
                                    ; variable stats every card shows (97.4.8)
ti_hbs:     dw 0                    ; the HUD band's stride
ti_hx:      dw 0                    ; ...its own ALIGNED screen x, which
ti_hw:      dw 0                    ; ti_ox is not, and its width
ti_hty:     dw 0                    ; ...its one text line's row
ti_hleft:   dw 0                    ; ...where the left block ends
ti_hsx:     dw 0                    ; the STATUS block's own rectangle,
ti_hsw:     dw 0                    ; which is what a hover redraws
ti_hnx:     dw 0                    ; the status line's own box, and the
ti_hnr:     dw 0                    ; one it replaces - a hover covers
ti_hpx:     dw 0                    ; the UNION, the old line being what
ti_hpr:     dw 0                    ; would be left behind otherwise
ti_hright:  dw 0                    ; ...and where the toggle begins
ti_tg0x:    dw 0                    ; the toggle's two arms, banked in SCREEN
ti_tg1x:    dw 0                    ; x so a click can be resolved
ti_hovc:    dw -1                   ; the BOARD cell under the pointer
ti_hovc2:   dw -1                   ; ...as this poll found it
ti_face:    dw 0                    ; SPEC.md 97.4.1's `T`: which face
ti_fdata:   dw 0                    ; ...and its glyphs, width and height
ti_fw:      dw 8
ti_fh:      dw 8
ti_cpad:    dw 0                    ; 1 where a card has a row to spare at each
                                    ; end for the hovered card's inner frame
ti_unitb:   dw TI_UNITW / 8
ti_ury:     dw 0
ti_undow:   dw 48                   ; UNDO is cut to its own label
ti_hovbx:   dw 0                    ; the hovered card's box, banked so the
ti_hovbw:   dw 0                    ; wheel can redraw the UNIT alone
ti_hovy:    dw 0
ti_rx:      dw 0                    ; a resource block's own corner
ti_ry2:     dw 0
ti_rg:      db 0
ti_rs:      db 0
ti_rsw:     db 0
ti_pjon:    db 0, 0                 ; each bolt: 0 idle, 1 flying, 2 erasing
ti_pjlane:  db 2
ti_pjrep:   db 0                    ; keep firing, so the frame can be read
ti_clash:   db 0                    ; frames left in a clash
ti_stw:     dw 0
ti_stpen:   db CWHITE, CLGRAY, CDGRAY   ; head, body, base - each over BLACK
                                    ; paper, which is the cheap pen path
ti_pjx:     dw 0, 0
ti_pjy:     dw 0, 0
ti_pjbx:    dw 0                    ; the band in hand's x and y
ti_pjby:    dw 0
ti_pjgo:    db 0                    ; the combat lane paid for this frame's
ti_pjt0:    dw 0                    ; ...and the bolts' own timing: the PIT at
ti_pjus:    dw 0                    ; their start, and what the last frame of
                                    ; them cost in microseconds
ti_pjh:     dw 0
ti_pjb:     dw TI_PJB
ti_npj:     dw 0                    ; projectile frames committed
ti_pj_art:  db 000h, 018h, 03Ch, 07Eh, 0FFh, 07Eh, 03Ch, 018h   ; a bolt
ti_roff:    dw 0                    ; a shallow corner lays out sideways
ti_c1off:   dw 0                    ; does a card's line 1 carry a coin?
ti_statx:   dw 0
ti_statv:   db 0
ti_cx:      dw 0                    ; is this card the hovered one?
ti_cbx:     dw 0                    ; ...and the box it is actually drawn in
ti_cbw:     dw 0
ti_cink:    db 0
ti_cpap:    db 0
ti_hover:   dw -1                   ; the card under the pointer, -1 for none
ti_hovold:  dw -1                   ; ...and the one it just left
ti_swaps:   db 2
ti_dok:     db 0                    ; ...and is this draw a TRANSITION?
ti_calfull: dw 0                    ; us for a whole band...
ti_calone:  dw 0                    ; ...and for one row of it
ti_calrows: dw 0
ti_calacc:  dw 0
ti_arrus:   dw 700                  ; SPEC.md 97.5's two terms, replaced by the
ti_rowus:   dw 60                   ; first ti_calibrate - a guess until then
ti_ft0:     dw 0                    ; the tick this frame started on
ti_trim:    dw 100                  ; per cent of the share the wheel dares
                                    ; spend, taught by the frames that overran
ti_ncommit: dw 0                    ; feature commits since launch, wrapping
ti_bslot:   dw 0                    ; the base band's slot pitch, bas x rows
ti_bart:    dw 0                    ; WHICH BASE CANDIDATE (SPEC.md 97.2.1) -
                                    ; `B` cycles it, and it is a wave 1a knob:
                                    ; the owner picks one and the rest go
ti_gidx:    dw 0                    ; ...and which SURFACE's set of it, an
                                    ; index into ti_bart_tab's rows
ti_brec:    dw 0                    ; the record in play
ti_mx:      dw 0                    ; a move sub-band, unpacked from its four
ti_my:      dw 0                    ; header bytes
ti_mw:      dw 0
ti_mb:      dw 0
ti_mh:      dw 0
ti_nbase:   dw 0                    ; ...and BASE LANE commits (SPEC.md 97.5.1)
ti_nbadv:   dw 0                    ; ...of which this many ADVANCED a pose -
                                    ; equal, by construction and by gate
ti_nframe:  dw 0                    ; ...and wheel passes
ti_nx:      dw 0                    ; the cell whose numbers are being drawn
ti_ny:      dw 0
ti_ktop:    dw 0                    ; the keep's top row, banked because two
                                    ; `mul`s stand between it and its reader
ti_bx:      dw 0
ti_by:      dw 0
ti_ox:      dw 0
ti_oy:      dw 0
ti_cw_box:  dw 0
ti_ch_box:  dw 0
ti_boardw:  dw 0
ti_boardh:  dw 0
ti_lift:    dw 0
ti_insx:    dw 0
ti_insy:    dw 0

; --- SPEC.md 97.2's table: CW, CH, RISE, BW, BH, HUD, PAN ------------------
; THE PROPORTION IS THE CELL'S APPARENT ONE AND NOT ITS PIXEL ONE. A CGA pixel
; is about 2.4 times as tall as it is wide and a Hercules one 1.5, so 120x40 on
; a Hercules and 112x56 on a VGA are the same tile to look at. The first cut of
; the VGA rows was 80x56 - very nearly SQUARE on the one adapter with square
; pixels - and a diamond inscribed in a square cell is a tall lozenge that
; meets its neighbours at four points, which is the opposite of an isometric
; read. Every row is ~2:1 apparent now bar CGA's, whose height has 8 pixels of
; slack in the whole window.
;
; CUT AGAINST THE CONTENT BOXES THIS MACHINE ACTUALLY HANDS OUT, and the first
; three rows of it were not: the boxes are VGA 640x416, Hercules 680x284 and
; CGA 504x136, so the Hercules and CGA rows asked for a board 56 and 62 pixels
; taller than the window they had to live in and BOTH refused themselves on
; every machine. The short screens are short in HEIGHT and not in width - a
; CGA has 504 columns of content and 136 rows - which is why what came down
; is CH and RISE and not CW.
;            CW   CH  RISE  BW  BH  HUD  PAN  BASEW  CARDH  INSX
; CARDH ON CGA IS 11 AND NOT 10, and the one row is what stops the name
; eating the card's own bottom edge: a glyph is 8 tall and sat at +2, so it
; ended on row 9 - which at CARDH 10 IS the bottom frame, drawn first and
; overwritten across the text's width. Eleven puts the frame on row 10 with a
; clear row between. The hand is still SEVEN (SPEC.md 97.4.2): the board is 112
; rows, the pitch 13 and the button row's offset 5, which leaves 8 rows of
; which one is the button's.
ti_geo_vgaw: dw   96, 48, 20, 64, 44, 28, 128, 56, 32, 24
ti_geo_herc: dw  104, 36, 12, 64, 32, 28, 152, 72, 24, 24
ti_geo_cga:  dw   96, 20,  4, 64, 18, 16, 152, 48, 11, 24

ti_s_bsep:  db '   BASE ', 0
ti_clock:   times TI_FEATURES db 0
ti_cacc:    dw 0                    ; the COMBAT lane's accumulator, in us...
ti_bacc:    dw 0                    ; ...and the BASE lane's (SPEC.md 97.5.1)
ti_bclock:  times 2 db 0            ; each base's own phase counter...
ti_bturnacc: db 0                   ; the lane's Bresenham: which base this
                                    ; frame's one commit is for
ti_hudn:    dw 0
ti_hudbuf:  times TI_HUDMAX db 0
ti_numbuf:  times 4 db 0
ti_cardbuf: times 24 db 0
ti_unit:    times TI_UNITMAX * TI_POSES * TI_HAND db 0 ; one per HAND SLOT
ti_pjband:  times TI_PJMAX * TI_PJN db 0

; THE POSES AND THE BOARD'S GROUND ARE NOT HERE: they are per cell and per
; column now, and live in the ARENA, a heap claim (tiplace.inc). What stays in
; the segment is the bases' eight bands.
TI_BSS      equ 0                 ; the bases' bands went to a claim

    OS88_BSS OP_BSS + TI_BSS
    OS88_IMAGE_END

