; =============================================================================
; os8088 - tests/titheband/titheband.asm
;
; TITHEBAND: WAVE 0 of docs/plans/TITHE-PLAN.md (its 3.7). Nothing in that
; plan's renderer is settled until these numbers exist, and it is the first
; thing built for exactly that reason - art drawn before it is art that may
; have to be redrawn. Nothing here ships: `make bench` builds it, `all` does
; not.
;
; THE QUESTION THE WHOLE PLAN HANGS ON is whether 23 animated features fit in
; 40% of a 54.925 ms frame on a 4.77 MHz 8088. TITHE-PLAN 1.3 answers yes from
; ONE derived constant - 6.15 us a band byte - and that constant comes from
; PERFORMANCE.md Set 77's measurement of a 128x128 band. A 128x128 band is
; SIXTEEN BYTES A ROW; a 56x56 sprite is SEVEN. If `gfx_blit1` charges anything
; per ROW, a figure derived per BYTE from the wide band is optimistic at the
; narrow one, and every budget downstream of it - the sprite size, the cell
; size, the art bill, whether `Rich` is worth building - moves.
;
; So the rows below are not a list of sizes. They are three experiments.
;
; --- 1. THE PER-ROW TERM, WHICH ONE MEASUREMENT CANNOT SEE -------------------
;
; The same 392 BYTES in three shapes - 56x56 (7 x 56), 112x28 (14 x 28) and
; 224x14 (28 x 14). Identical traffic, 56 rows against 14. The DIFFERENCE
; between those rows IS the per-row cost, and what is left over is the per-byte
; cost. That is Set 108's own method for `gfx_blitp` (64x64 against 256x16),
; applied to the primitive TITHE actually draws with.
;
; A single measurement cannot separate the two terms and will always report
; whichever mixture the shape it was taken at happens to be. Set 77 was taken
; at the widest shape in the system, which is the mixture most favourable to a
; per-byte reading - so if the plan is wrong, this is where it is wrong.
;
; --- 2. WHAT A COLOUR COSTS, WHICH IS NOT ONE NUMBER -------------------------
;
; SPEC.md 5.4.2.2 gives `gfx_blit1_pen` FOUR paths and the plan quotes one of
; them (the ~78 us short circuit for the default pair). The other three are
; not free and are not equal:
;
;   the default pair      CWHITE on CBLACK - recognised, short-circuited
;   B empty               any ink over BLACK paper - `rep movsw`, unchanged
;   A empty               black on white - the complementing HAND LOOP, 34
;                         clocks a word against the rep's 25
;   both non-empty        5.4.2.2.1's MAP MASK SPLIT - TWO passes over the band
;
; A faction colour on a black ground is the cheap arm. A faction colour on any
; other ground may be the split, and the split is a second trip through the
; emit. TITHE-PLAN 3.5's three detail arms are priced against the short circuit
; alone, so all four are measured here on the SAME band.
;
; --- 3. THE FOUR-PLANE FLOOR AT OUR SIZE -------------------------------------
;
; TITHE-PLAN 1.1 records `gfx_blitp` as an ESTIMATE of ~3.1 us a byte and says
; it is measured nowhere in the tree. **That is wrong and the plan is corrected
; by its own wave 0**: PERFORMANCE.md Set 108 measured it at two shapes on this
; exact machine, and the two-term fit is 114.1 us a ROW-PLANE plus 3.98 us a
; byte. At 56x56 that is 224 row-plane operations before a byte moves, which
; the per-byte reading does not see at all.
;
; The rows here take it at OUR sizes rather than re-deriving it from Set 108's,
; and 112x28 beside 56x56 is the same separation as experiment 1 - identical
; bytes, half the row-planes.
;
; --- WHAT IS DELIBERATELY NOT A ROW ------------------------------------------
;
; There is no row for `gfx_blit4`. Set 107 priced the planar decoder at 106.9
; cycles a pixel and one 56x56 sprite is 70 ms of it - two whole frames for one
; character. TITHE-PLAN 1.2 rules it out for anything that moves and a row here
; would only confirm an order of magnitude. It is the right slot for a picture
; drawn once, which is not what this bench is about.
;
; --- HOW TO READ IT ----------------------------------------------------------
;
; Click the window, or press R. Every row is benchlib's (tests/benchlib.inc),
; so the method, the lap detector and the overhead subtraction are the ones
; every other bench in this tree uses. Rows whose single iteration approaches
; the 55 ms PIT wrap are declared method T rather than left to be caught.
;
; RUN IT ON ALL THREE ADAPTERS. The 1bpp adapters are not a scaled VGA: the
; pen is NOT READ there (5.4.2.2), so the four pen rows must land on each other
; and a gap is a defect; and `gfx_blitp` REFUSES there outright, so those rows
; must report a refusal and not a fast time. Both are asserted on the glass by
; the CF lines at the end of the report rather than left to be inferred from a
; number that looks small.
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'TITHEBAND', tb_entry

; --- the four surfaces' sprite bands (TITHE-PLAN 3.2.1) ----------------------
TB_FW       equ 56                ; VGA fullscreen: 56x56, stride 7, 392 B
TB_FH       equ 56
TB_FS       equ TB_FW / 8
TB_WW       equ 48                ; VGA windowed: 48x44, stride 6, 264 B
TB_WH       equ 44
TB_WS       equ TB_WW / 8
TB_HW       equ 64                ; Hercules: 64x40, stride 8, 320 B
TB_HH       equ 40
TB_HS       equ TB_HW / 8
TB_CW       equ 48                ; CGA: 48x24, stride 6, 144 B
TB_CH       equ 24
TB_CS       equ TB_CW / 8

; --- the CELL, which is what TITHE-PLAN 3.4's 58% saving is measured against -
TB_LW       equ 104               ; 104x72, stride 13, 936 B
TB_LH       equ 72
TB_LS       equ TB_LW / 8

; --- the BAR: PERFORMANCE.md Set 77's own shape, so this harness can be read
;     against a number taken on a real 5150 rather than against itself alone.
;     bandbench's "row 1 is the bar" discipline - two harnesses that disagree
;     about the same primitive is the finding, and the rows below are not to be
;     believed until this one agrees with 12,588 us.
TB_BW       equ 128
TB_BH       equ 128
TB_BS       equ TB_BW / 8

; --- 392 bytes in three shapes: the per-ROW term -----------------------------
TB_MW       equ 112               ; 112x28: 14 bytes a row, 28 rows
TB_MH       equ 28
TB_MS       equ TB_MW / 8
TB_NW       equ 224               ; 224x14: 28 bytes a row, 14 rows
TB_NH       equ 14
TB_NS       equ TB_NW / 8

TB_BANDSZ   equ TB_BS * TB_BH     ; 2,048 - the largest band, and every other
                                  ; row is a prefix of it read at its own
                                  ; stride. Any bytes are a valid band, so one
                                  ; buffer serves them all

; --- the four-plane arm ------------------------------------------------------
TB_PLSZ     equ TB_LS * TB_LH     ; one plane of the biggest blitp row (936)
TB_PLANSZ   equ TB_PLSZ * 4       ; ...and all four of it (3,744)

; --- TITHE-PLAN 4.2.1's layers, and 3.9.1's projectile -----------------------
TB_ITW      equ 40                ; the held item: 40x48, stride 5, 240 B
TB_ITH      equ 48
TB_ITS      equ TB_ITW / 8
TB_ITSZ     equ TB_ITS * TB_ITH

TB_PJW      equ 48                ; the projectile band: union(old, new), 48x32
TB_PJH      equ 32
TB_PJS      equ TB_PJW / 8
TB_PJSZ     equ TB_PJS * TB_PJH   ; 192 B

TB_BGS      equ 52                ; the board picture in RAM: 416 px / 8 = 52
TB_BGH      equ 64                ; bytes a row. TITHE-PLAN 3.9.1 claims 416 x
TB_BGSZ     equ TB_BGS * TB_BGH   ; 420 = 21.8 KB; 64 rows is all a 32-row band
                                  ; can be copied out of, and the COST is per
                                  ; row copied, not per row held

TB_FEATURES equ 23                ; the brief's own number: 20 characters, 2
                                  ; player bases, 1 moused-over card
TB_LANES    equ 4                 ; projectiles in one lane at 3.9.1's worst
                                  ; case - two a side

; --- the LEVERS (blocks 9 and 10), which is what a second wave 0 asked ------
TB_SHW      equ 56                ; a SHORTER sprite: 1.3's first lever, where
TB_SHH      equ 40                ; height is worth ~3x width
TB_SHS      equ TB_SHW / 8

TB_D7H      equ 39                ; the DIRTY-RECT arm: a pose that differs
TB_D5H      equ 28                ; from its neighbour in 70% / 50% / 35% of
TB_D3H      equ 20                ; its rows blits only those rows

TB_PVW      equ 56                ; the user's PAIR-V: two 56x56 figures
TB_PVH      equ 56 * 2 + 6        ; stacked with a 6 px gap, in ONE blit
TB_PVS      equ TB_PVW / 8

TB_PIW      equ 160               ; ...and the PAIR-ISO, which is what the
TB_PIH      equ 76                ; SHEARED grid actually puts side by side:
TB_PIS      equ TB_PIW / 8        ; two cells of one lane, x apart by CW=104
                                  ; and y by RISE=20, so the union is
                                  ; 104+56 wide by 56+20 tall

TB_OWNSTEP  equ 0                 ; block 10's band step: stride - row width
                                  ; (see tb_b_own). 7 - 7 on this band

TB_PAIRS    equ 10                ; 20 characters as 10 pairs...
TB_SINGLES  equ 3                 ; ...plus the two bases and the hovered card

; --- the VGA's own two index ports, for the multi-plane arm (SPEC.md 5.4.2.2)
TB_VGA_SEQ  equ 0x3C4
TB_VGA_GC   equ 0x3CE

TB_FRAMEUS  equ 54925             ; one system tick in MICROSECONDS. Every
                                  ; "% of a frame" line below is against this

; --- iteration counts --------------------------------------------------------
; Sized so a method-P row stays well under benchlib's BL_SUSPECT (40,000 counts
; = 33 ms) and a method-T row runs for seconds. A row that would straddle the
; two is DECLARED method T rather than left for the lap detector to catch: the
; detector re-runs the row, which is a second helping of an already slow row.
;
; **AND THEY ARE SIZED AGAINST THE MEASUREMENT, NOT AGAINST THE PLAN**, which
; is the whole trap this bench exists inside. The first cut of this file took
; its counts from TITHE-PLAN 1.3's 2.41 ms a band - the number under test - and
; the run took SEVEN MINUTES of guest time instead of thirty seconds, because
; the thing being measured is slower than the figure the counts were derived
; from. A bench whose own runtime is computed from its hypothesis takes as long
; as the hypothesis is wrong, and it is wrong in the direction that hurts.
;
; So `-DTBQUICK` exists: the same rows, a handful of iterations each, a couple
; of guest seconds in all. The numbers it gives are too coarse to quote and
; exactly good enough to SIZE the real run - and to prove the whole path works
; before anybody waits on it.
%ifdef TBQUICK
TB_N        equ 8
TB_NBAR     equ 4
TB_NRAM     equ 8
TB_NPLANE   equ 4
TB_NWHEEL   equ 4
TB_NSND     equ 16
%else
TB_N        equ 64                ; the small bands
TB_NBAR     equ 24                ; 128x128 - the most expensive single blit
TB_NRAM     equ 48                ; the RAM-only rows
TB_NPLANE   equ 72                ; method T: four planes
TB_NWHEEL   equ 48                ; method T: 23 features at once, and combat
TB_NSND     equ 64                ; a note-on
%endif

; -----------------------------------------------------------------------------
; tb_entry - package entry (SPEC.md 20.2)
; in:  CS=DS=ES = our own segment; gfx lock NOT held
; out: BX = window ptr, CF set = refused
; -----------------------------------------------------------------------------
tb_entry:
    push si
    call tb_build                   ; the bands, once
    call tb_frame                   ; ...and the window sized to THIS screen
    call tb_hint
    mov si, tb_tpl
    call OSAPI_WM_CREATE
    jc .out
    mov [tb_win], bx
    mov al, 1
    call OSAPI_WM_SNAP              ; the content origin onto a multiple of 8,
                                    ; so `gfx_blit1`'s one alignment rule is
                                    ; satisfied by the content left itself
                                    ; (SPEC.md 11.94). Preserves flags, so the
                                    ; CF this proc owes the loader survives
    clc
.out:
    pop si
    ret

; -----------------------------------------------------------------------------
; tb_frame - size the template to the live screen before wm_create reads it
;
; `wm_create` clamps an oversized frame rather than losing it, so a window is
; never the problem - but a CLAMPED window has less content than the template
; asked for, and every band below has to land WHOLLY INSIDE the content or it
; is measuring the clip region (tb_geom says why). CGA is 640x200 against VGA's
; 640x480 and the 128x128 bar row is the one that would not fit.
;
; So the frame is cut from OSAPI_VIDEO's answer: the usable desktop is rows
; MBAR_H .. CX-1, and CX is the first row the dock owns.
; -----------------------------------------------------------------------------
tb_frame:
    push ax
    push bx
    push cx
    push dx
    call OSAPI_VIDEO                ; AX = w, BX = h, CX = the dock's first row
    sub ax, 14                      ; a frame's own chrome each side
    cmp ax, 624
    jbe .w
    mov ax, 624
.w:
    mov [tb_tpl + 4], ax
    sub cx, 22 + 4                  ; the template's y, and the bottom border
    cmp cx, 440
    jbe .h
    mov cx, 440
.h:
    mov [tb_tpl + 6], cx
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tb_build - fill every source buffer with plausible texture
; in:  -
; out: tb_band, tb_planar, tb_item, tb_imask, tb_bg filled
;      preserves all registers
;
; NOT ZEROS AND NOT ONES. `gfx_blit1` is a `rep movsw` and does not care what
; the bits are - unlike `gfx_blit4`, whose run coalescer makes a flat block the
; cheapest possible input and a dithered one the most expensive (Set 107). But
; the SCREEN is the only check this harness has that a band landed where it was
; sent, and a buffer of 0x00 or 0xFF draws a rectangle that says nothing about
; whether the stride was right. A figure-shaped pattern shows a wrong stride as
; a shear, which is what the three bugs in Set 108 all looked like.
; -----------------------------------------------------------------------------
tb_build:
    push ax
    push bx
    push cx
    push dx
    push di

    mov di, tb_band                 ; a cheap hash of the offset: it has runs,
    mov cx, TB_BANDSZ               ; edges and no period that lines up with
    call tb_fill                    ; any of the strides measured below
    mov di, tb_planar
    mov cx, TB_PLANSZ
    call tb_fill
    mov di, tb_item
    mov cx, TB_ITSZ
    call tb_fill
    mov di, tb_bg
    mov cx, TB_BGSZ
    call tb_fill

    mov di, tb_imask                ; the item's MASK: which pixels are the
    mov cx, TB_ITSZ                 ; item rather than the body showing
    call tb_fill                    ; through. Roughly half set, which is what
                                    ; an arm-and-weapon cut out of a 40x48 box
                                    ; comes to

    mov di, tb_ilv                  ; ...and the SAME two, interleaved
    mov cx, TB_ITSZ * 2             ; data,mask,data,mask - see tb_b_maskorl
    call tb_fill

    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tb_fill - DI = dest, CX = bytes. Preserves all registers but the ones above.
tb_fill:
    push cx
    push di
    mov bx, di
.b:
    mov ax, di
    xor ax, bx
    add ax, di
    mov dl, ah
    xor dl, al
    add dl, 0x5B
    rol dl, 1
    mov [di], dl
    inc di
    loop .b
    pop di
    pop cx
    ret

; -----------------------------------------------------------------------------
; tb_hint - the first page, before anything has been measured
; -----------------------------------------------------------------------------
tb_hint:
    push si
    call bl_blank
    mov si, tb_s_title
    call bl_sline
    mov si, tb_s_sub
    call bl_sline
    call bl_head
    mov si, tb_s_hint
    call bl_sline
    pop si
    ret

tb_paint:
    call bl_paint
    ret

; -----------------------------------------------------------------------------
; tb_onkey - W_ONKEY: R runs, everything else pages the report
; -----------------------------------------------------------------------------
tb_onkey:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov [tb_win], si
    mov bl, al
    or bl, 0x20
    cmp bl, 'r'
    je .run
    cmp bl, 's'                     ; ...and a re-save by hand, for a run whose
    je .save                        ; floppy was swapped after the fact
    call bl_key
    jc .out
    call bl_paint
    jmp short .out
.run:
    call tb_run
    call tb_repaint
    jmp short .out
.save:
    call tb_save
    call bl_paint
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tb_onclick - a click runs it, so the harness can be driven by the scripted
;              mouse alone (tools/os88mouse.py)
; -----------------------------------------------------------------------------
tb_onclick:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov [tb_win], si
    call tb_run
    call tb_repaint
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tb_repaint - the measured bands scribbled over the page; put it back
tb_repaint:
    push ax
    push bx
    push cx
    push dx
    push si
    mov bx, [tb_win]
    call OSAPI_WM_CONTENT
    mov [tb_cx], ax
    mov [tb_cy], dx
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov ax, [tb_cx]
    mov bx, [tb_cy]
    mov cx, ax
    add cx, [tb_cw]
    dec cx
    mov dx, bx
    add dx, [tb_ch]
    dec dx
    call OSAPI_GFX_FILL
    mov si, [tb_win]
    call bl_paint
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; the measured bodies
;
; Each is called [bl_n] times inside one cli window. Every band is drawn at
; ([tb_bx], [tb_by]) - the content's TOP-LEFT - for two reasons that are not
; cosmetic:
;
;   THE X IS A MULTIPLE OF 8 BY CONSTRUCTION. WF_SNAP put the content origin
;   there (SPEC.md 11.94), so no row has to round its own x and none of them
;   is measuring a different alignment from its neighbours.
;
;   NOTHING IS CLIPPED. `gfx_blit1` honours the clip region to the exact pixel
;   row, and a band hanging off the content would be measuring the clip rather
;   than the band - differently per adapter, which is the one thing this bench
;   must not do. tb_run refuses the rows that do not fit rather than reporting
;   a clipped one (tb_fits).
;
; They all draw over each other and over the report. bl_lcommit writes to a RAM
; arena and draws nothing, so no result can be scribbled; tb_repaint puts the
; page back when the run is done.
; =============================================================================

; -----------------------------------------------------------------------------
; tb_blit - ONE band. CX = width px, DX = rows, BP = stride
; Every BLIT1 row below is this with three constants, so a row cannot
; accidentally measure a different code path from its neighbour.
; -----------------------------------------------------------------------------
tb_blit:
    push es
    push ds
    pop es
    mov si, tb_band
    mov ax, [tb_bx]
    mov bx, [tb_by]
    call OSAPI_GFX_BLIT1
    pop es
    ret

tb_b_bar:                           ; 128x128 = 2,048 B: Set 77's own shape
    mov cx, TB_BW
    mov dx, TB_BH
    mov bp, TB_BS
    jmp tb_blit

tb_b_cell:                          ; 104x72 = 936 B: the whole CELL
    mov cx, TB_LW
    mov dx, TB_LH
    mov bp, TB_LS
    jmp tb_blit

tb_b_herc:                          ; 64x40 = 320 B
    mov cx, TB_HW
    mov dx, TB_HH
    mov bp, TB_HS
    jmp tb_blit

tb_b_full:                          ; 56x56 = 392 B: the design target
    mov cx, TB_FW
    mov dx, TB_FH
    mov bp, TB_FS
    jmp tb_blit

tb_b_win:                           ; 48x44 = 264 B
    mov cx, TB_WW
    mov dx, TB_WH
    mov bp, TB_WS
    jmp tb_blit

tb_b_cga:                           ; 48x24 = 144 B
    mov cx, TB_CW
    mov dx, TB_CH
    mov bp, TB_CS
    jmp tb_blit

; --- the same 392 bytes, a quarter and an eighth of the rows -----------------
tb_b_mid:                           ; 112x28
    mov cx, TB_MW
    mov dx, TB_MH
    mov bp, TB_MS
    jmp tb_blit

tb_b_wide:                          ; 224x14
    mov cx, TB_NW
    mov dx, TB_NH
    mov bp, TB_NS
    jmp tb_blit

; --- block 9: THE LEVERS ----------------------------------------------------
; Every one of these is an ordinary `gfx_blit1` at a different rectangle, which
; is the point: they are not new mechanisms, they are the SAME primitive asked
; a different question, so the answers are comparable to the rows above without
; any modelling in between.

tb_b_min:                           ; 8x1 - the smallest legal band. This IS
    mov cx, 8                       ; the arrival, measured rather than fitted
    mov dx, 1                       ; out of the three-shape fit above
    mov bp, 1
    jmp tb_blit

tb_b_short:                         ; 56x40 - 1.3's lever 1, and the cheapest
    mov cx, TB_SHW                  ; 16 rows off a 56-row figure
    mov dx, TB_SHH
    mov bp, TB_SHS
    jmp tb_blit

tb_b_d7:                            ; ...and the DIRTY RECT: the rows that
    mov cx, TB_FW                   ; actually differ between two idle poses
    mov dx, TB_D7H
    mov bp, TB_FS
    jmp tb_blit

tb_b_d5:
    mov cx, TB_FW
    mov dx, TB_D5H
    mov bp, TB_FS
    jmp tb_blit

tb_b_d3:
    mov cx, TB_FW
    mov dx, TB_D3H
    mov bp, TB_FS
    jmp tb_blit

; --- the PAIR: two figures in one blit, two ways, against the control -------
tb_b_two56:                         ; THE CONTROL: the same two figures as two
    call tb_b_wadapt1               ; separate bands, at this adapter's size
    jmp tb_b_wadapt1

tb_b_wadapt1:                       ; one band, this adapter's own geometry
    mov cx, [tb_aw]
    mov dx, [tb_ah]
    mov bp, [tb_as]
    jmp tb_blit

tb_b_pairv:                         ; stacked, 6 px apart - and in the SHEARED
    mov cx, TB_PVW                  ; grid this is NOT where two characters
    mov dx, TB_PVH                  ; are: two cells of one column are CH=72
    mov bp, TB_PVS                  ; apart, not 6. It is measured anyway
    jmp tb_blit                     ; because it is the shape that was asked
                                    ; about, and because it is the cheapest
                                    ; possible version of the idea - if the
                                    ; BEST case does not pay, the real one
                                    ; cannot

; ...and the pair the geometry really has: one lane's two cells, CW apart in x
; and RISE in y, so the union is (CW + w) x (h + RISE).
;
; **CUT FROM THIS ADAPTER'S OWN CELL PITCH** (3.2.1), which the first run of
; this row did not do - it used the VGA union on all three and so compared a
; 160x76 band against Hercules' 64x40 native one, which is not a comparison. A
; pair's saving is ONE arrival, fixed; its cost is the EMPTY area inside the
; union, which scales with the cell pitch. Those two only meet per adapter.
tb_b_pairi:
    mov cx, [tb_pw]
    mov dx, [tb_ph]
    mov bp, [tb_ps]
    jmp tb_blit

; =============================================================================
; the PEN, four paths (SPEC.md 5.4.2.2)
;
; The pen is set INSIDE the timed body and put back after it, which is what a
; real caller does: it lives exactly one gfx-lock hold and `gfx_unlock` restores
; the default, so a package that set it once outside would lose it and draw
; white without knowing. gfxbench's rows do the same, for the same reason.
;
; RESTORING IS PART OF THE ROW, NOT AN AFTERTHOUGHT. A row that left a pen set
; would hand it to the next row, which would then measure a path it did not
; declare - benchlint catches a body that was never set and cannot catch a
; state that was never cleared.
; =============================================================================

; The pen calls ALONE, nothing drawn - so the four rows below can be read as
; the blit plus this, and the pen's own fixed cost does not have to be inferred
; from the difference between two rows that also differ in emit path.
tb_b_penonly:
    mov al, CLBLUE
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    mov al, CWHITE
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    ret

; (1) THE DEFAULT PAIR - CWHITE on CBLACK, recognised and short-circuited
;     before any port is touched. Set 77 measured this at +0.62% on a 128x128
;     band, a FIXED ~78 us - which dilutes on a big band and is most of what a
;     small one adds. 392 bytes is a small one.
tb_b_pendef:
    mov al, CWHITE
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    call tb_b_full
    ret

; (2) B EMPTY - any ink over BLACK paper. `rep movsw`, unchanged. This is the
;     coloured-sprite case and the one TITHE-PLAN 3.5(a) assumes throughout.
tb_b_penink:
    mov al, CLBLUE
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    call tb_b_full
    mov al, CWHITE
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    ret

; (3) A EMPTY - black on white. `rep movsw` cannot invert, so it is a hand loop
;     at 34 clocks a word against the rep's 25. Not exotic: it is what most
;     TEXT is, and a card face is mostly text.
tb_b_peninv:
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_GFX_BLIT1_PEN
    call tb_b_full
    mov al, CWHITE
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    ret

; (4) BOTH NON-EMPTY - 5.4.2.2.1's Map Mask split: TWO passes over the band,
;     the second complemented. CDGRAY on CLGRAY is the pair that used to be the
;     fourth refusal. If a faction's colours land here, TITHE-PLAN 3.5's
;     arithmetic is out by whatever this row says.
tb_b_pensplit:
    mov al, CDGRAY
    mov ah, CLGRAY
    call OSAPI_GFX_BLIT1_PEN
    call tb_b_full
    mov al, CWHITE
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    ret

; =============================================================================
; the BANDED arm (TITHE-PLAN 3.5(b)): the same figure as 2 and 3 stacked
; strips, each with its own pen. THE BYTES ARE IDENTICAL - what is added is one
; arrival per extra strip, which is the thing the plan says must be priced
; rather than estimated.
; =============================================================================
tb_strip:                           ; CX = width, DX = rows, BP = stride,
    push es                         ; SI = band offset, DI = y offset
    push ds
    pop es
    add si, tb_band
    mov ax, [tb_bx]
    mov bx, [tb_by]
    add bx, di
    call OSAPI_GFX_BLIT1
    pop es
    ret

tb_b_two:
    mov al, CLBLUE
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    mov cx, TB_FW
    mov dx, TB_FH / 2
    mov bp, TB_FS
    xor si, si
    xor di, di
    call tb_strip
    mov al, CRED
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    mov cx, TB_FW
    mov dx, TB_FH / 2
    mov bp, TB_FS
    mov si, TB_FS * (TB_FH / 2)
    mov di, TB_FH / 2
    call tb_strip
    mov al, CWHITE
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    ret

; Three strips of 19, 19 and 18 rows - 56 exactly, so this row moves the same
; 392 bytes as every other 56x56 row and the only difference is the arrivals.
tb_b_three:
    mov al, CLBLUE
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    mov cx, TB_FW
    mov dx, 19
    mov bp, TB_FS
    xor si, si
    xor di, di
    call tb_strip
    mov al, CRED
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    mov cx, TB_FW
    mov dx, 19
    mov bp, TB_FS
    mov si, TB_FS * 19
    mov di, 19
    call tb_strip
    mov al, CGREEN
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    mov cx, TB_FW
    mov dx, 18
    mov bp, TB_FS
    mov si, TB_FS * 38
    mov di, 38
    call tb_strip
    mov al, CWHITE
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    ret

; =============================================================================
; FOUR PLANES (SPEC.md 5.4.3) - TITHE-PLAN 3.5(c)'s `Rich` arm
;
; It REFUSES more than it accepts and CF must be read: a 1bpp adapter, an x off
; the byte grid, a block off the screen, an armed clip region, a straddle, and
; a kernel with no planes. On Hercules and CGA every row here is a refusal, and
; the report says so in words at the end rather than leaving a suspiciously
; small number to be read as a fast one.
;
; 112x28 beside 56x56 is experiment 1 again on this primitive: the SAME 1,568
; plane-bytes at 112 row-plane operations instead of 224.
; =============================================================================
tb_blitp:                           ; CX = width, DX = rows, DI = plane step,
    push es                         ; BP = stride inside one plane
    push ds
    pop es
    mov si, tb_planar
    mov ax, [tb_bx]
    mov bx, [tb_by]
    call OSAPI_GFX_BLITP            ; CF is READ once, outside the timed rows,
    pop es                          ; by tb_refusals - a row must not branch on
    ret                             ; it, or the two adapters measure different
                                    ; amounts of code

tb_b_pfull:                         ; 56x56, 4 planes: 1,568 B, 224 row-planes
    mov cx, TB_FW
    mov dx, TB_FH
    mov di, TB_FS * TB_FH
    mov bp, TB_FS
    jmp tb_blitp

tb_b_pmid:                          ; 112x28, 4 planes: 1,568 B, 112 row-planes
    mov cx, TB_MW
    mov dx, TB_MH
    mov di, TB_MS * TB_MH
    mov bp, TB_MS
    jmp tb_blitp

tb_b_pcell:                         ; 104x72, 4 planes: 3,744 B, 288 row-planes
    mov cx, TB_LW
    mov dx, TB_LH
    mov di, TB_LS * TB_LH
    mov bp, TB_LS
    jmp tb_blitp

; =============================================================================
; RAM: the composition (TITHE-PLAN 4.2.1) and the projectile (3.9.1)
;
; These are the two places the plan spends RAM cycles rather than drawing
; calls, and both are costed there from PERFORMANCE.md's 1.76 us a byte for
; `rep stosw` and 15.3 us a byte for a read-modify-write loop. Both figures are
; real; what is NOT measured is how they compose into the shapes below, where
; the copies are STRIDED - a 6-byte row out of a 52-byte-wide picture, 32 times
; - and a strided copy is 32 loop set-ups rather than one.
; =============================================================================

; A 392-byte body copied out of the sprite bank, row by row at its own stride.
; This is what 4.2.1's composition starts with, and it is the honest shape: the
; bank is a strip of frames, so a body is never a flat run.
tb_b_copy:
    push es
    push ds
    pop es
    mov si, tb_bg                   ; a wider picture than the body is: 52
    mov di, tb_dst                  ; bytes a row against the body's 7, so
    mov dx, TB_FH                   ; every row is its own loop set-up
    cld
.row:
    mov cx, TB_FS / 2
    rep movsw
    movsb                           ; stride 7 is odd: three words and a byte
    add si, TB_BGS - TB_FS
    dec dx
    jnz .row
    pop es
    ret

; The masked OR: 240 bytes of item over the body already in tb_dst. Read the
; item byte, read its mask, clear the body where the item is, OR the item in.
; This is the 15.3 us-a-byte path and it is the expensive half of 4.2.1.
tb_b_maskor:
    mov si, tb_item
    mov bx, tb_imask
    mov di, tb_dst
    mov cx, TB_ITSZ
.b:
    mov al, [si]                    ; the item's bits...
    inc si
    mov ah, [bx]                    ; ...and which of them are the item at all
    inc bx
    and al, ah                      ; the item only where its mask says so
    not ah
    mov dl, [di]
    and dl, ah                      ; clear the body where the item lands
    or  dl, al
    mov [di], dl
    inc di
    loop .b
    ret

; -----------------------------------------------------------------------------
; ...AND THE SAME COMPOSITE WITH THE ITEM STORED data,mask,data,mask
;
; The loop above is the OBVIOUS one and it is fetch-bound, not memory-bound: an
; 8088 charges max(clocks, 4.34 x instruction BYTES) (PERFORMANCE.md Part 2),
; the body is 26 bytes, and 26 x 4.34 = 113 clocks a byte is 23.7 us of the
; 25.2 it measures. **The bytes moved are not what it costs; the instructions
; fetched are.**
;
; Interleaving the item's data with its mask makes ONE `lodsw` do what two
; `mov`/`inc` pairs did, and the body falls to 17 bytes. That is the whole
; change: same memory, same result, fewer instruction bytes to fetch.
;
; IT IS HERE BECAUSE THE NAIVE ROW WOULD HAVE OVER-PRICED 4.2.1's LAYERS BY
; 60%, and the plan would have been corrected in the wrong direction on the
; strength of it. PERFORMANCE.md's own 15.3 us a byte is a FIVE-instruction
; loop; quoting it against a twelve-instruction one is comparing two different
; programs. The pair below is what makes that visible instead of arguable, and
; which one TITHE ships is a decision this row turns into arithmetic: the
; interleaved bank costs the same bytes on disk and is what os88tithe.py should
; emit.
; -----------------------------------------------------------------------------
tb_b_maskorl:
    mov si, tb_ilv
    mov di, tb_dst
    mov cx, TB_ITSZ
    push es
    push ds
    pop es                          ; lodsw is DS:SI, and the stores are plain
    cld                             ; [di] - ES is set only for symmetry with
.b:                                 ; the other RAM bodies
    lodsw                           ; AL = the item's bits, AH = its mask
    mov dl, [di]
    and al, ah
    not ah
    and dl, ah
    or  dl, al
    mov [di], dl
    inc di
    loop .b
    pop es
    ret

; ...and the two together, which is what ONE composed character costs at a
; round boundary (4.2.3). 90 body sets x 4 frames is the art bill; this is what
; turning one of them into a drawable sprite costs the machine.
tb_b_compose:
    call tb_b_copy
    call tb_b_maskor
    ret

tb_b_composel:                      ; ...the same character, lean composite
    call tb_b_copy
    call tb_b_maskorl
    ret

; -----------------------------------------------------------------------------
; ONE PROJECTILE FRAME - TITHE-PLAN 3.9.1's four steps, in order
;
;   1. copy the BOARD PICTURE for the band's region        strided RAM->RAM
;   2. copy in any CHARACTER SPRITE the band overlaps      strided RAM->RAM
;   3. mask-OR the projectile itself                       RMW
;   4. commit with one gfx_blit1                           to VRAM
;
; The plan bills this at ~5 ms and four of them in a lane at ~20 ms, over a
; third of the frame - which is why the other four lanes stop idling while it
; happens (3.8). It is the most expensive thing in the game and the only thing
; in the renderer that is not a self-erasing band, so it is the row most worth
; being right about.
; -----------------------------------------------------------------------------
tb_b_projn:                         ; the naive composite...
    mov byte [tb_lean], 0
    jmp short tb_b_proj
tb_b_projl:                         ; ...and the interleaved one
    mov byte [tb_lean], 1
tb_b_proj:
    push es
    push ds
    pop es
    cld
    ; 1. the board under the band
    mov si, tb_bg
    mov di, tb_dst
    mov dx, TB_PJH
.bgrow:
    mov cx, TB_PJS / 2
    rep movsw
    add si, TB_BGS - TB_PJS
    dec dx
    jnz .bgrow
    ; 2. a character sprite that overlaps it
    mov si, tb_band
    mov di, tb_dst
    mov dx, TB_PJH
.chrow:
    mov cx, TB_PJS / 2
    rep movsw
    add si, TB_FS - TB_PJS
    dec dx
    jnz .chrow
    ; 3. the projectile, masked
    cmp byte [tb_lean], 0
    jne .lean
    mov si, tb_item
    mov bx, tb_imask
    mov di, tb_dst
    mov cx, TB_PJSZ
.b:
    mov al, [si]
    inc si
    mov ah, [bx]
    inc bx
    and al, ah
    not ah
    mov dl, [di]
    and dl, ah
    or  dl, al
    mov [di], dl
    inc di
    loop .b
    jmp short .commit
.lean:
    mov si, tb_ilv                  ; the interleaved bank - see tb_b_maskorl
    mov di, tb_dst
    mov cx, TB_PJSZ
.lb:
    lodsw
    mov dl, [di]
    and al, ah
    not ah
    and dl, ah
    or  dl, al
    mov [di], dl
    inc di
    loop .lb
.commit:
    ; 4. the commit
    mov si, tb_dst
    mov bp, TB_PJS
    mov ax, [tb_bx]
    mov bx, [tb_by]
    mov cx, TB_PJW
    mov dx, TB_PJH
    call OSAPI_GFX_BLIT1
    pop es
    ret

; =============================================================================
; THE WHEEL - the only row that answers the brief
;
; 23 features, one update each. Everything above is a component; this is the
; frame. It is declared method T: 23 bands is tens of milliseconds and the PIT
; wraps at 55, so method P would lap - and a lapped row reports
; `total mod 54.92` as a small plausible number with no flag, which is the
; failure PERFORMANCE.md Part 9 records a whole field set being taken through.
;
; Method T also INCLUDES interrupt and scheduler time, which for a whole-frame
; figure is the honest answer rather than a contaminant: a real frame pays the
; tick ISR and the mouse ISR too.
;
; EVERY BAND LANDS AT THE SAME PLACE. A blit's cost does not depend on where it
; goes - there is no cache on an 8088 and the row base is one multiply either
; way - and putting 23 bands on a real board grid would need 224 x 336 of
; content, which CGA's 200-row screen has not got. Spreading them would price
; the layout, not the blit.
; =============================================================================
tb_wheel:                           ; CX = width, DX = rows, BP = stride
    mov [tb_ww], cx                 ; banked, because tb_blit consumes all
    mov [tb_wh], dx                 ; three and a stack dance round the call
    mov [tb_ws], bp                 ; is a thing to get wrong 23 times
    mov word [tb_left], TB_FEATURES
.f:
    mov cx, [tb_ww]
    mov dx, [tb_wh]
    mov bp, [tb_ws]
    call tb_blit
    dec word [tb_left]
    jnz .f
    ret

tb_b_wfull:                         ; 23 x 56x56 - the cross-adapter reference
    mov cx, TB_FW
    mov dx, TB_FH
    mov bp, TB_FS
    jmp tb_wheel

tb_b_wadapt:                        ; 23 x THIS surface's own band (3.2.1)
    mov cx, [tb_aw]
    mov dx, [tb_ah]
    mov bp, [tb_as]
    jmp tb_wheel

; THE PAIRED WHEEL: the same 23 animated features as 13 blits - ten lane-pairs
; and three singles. This is the end-to-end form of the question, and it is the
; only form that answers it, because the saving (ten arrivals) and the cost
; (the gap rows and columns inside each union) only meet at the whole frame.
tb_b_wpair:
    mov word [tb_left], TB_PAIRS
.p:
    mov cx, [tb_pw]
    mov dx, [tb_ph]
    mov bp, [tb_ps]
    call tb_blit
    dec word [tb_left]
    jnz .p
    mov word [tb_left], TB_SINGLES
.s:
    mov cx, [tb_aw]                 ; the three singles are this adapter's own
    mov dx, [tb_ah]                 ; band, like the unpaired wheel's
    mov bp, [tb_as]
    call tb_blit
    dec word [tb_left]
    jnz .s
    ret

tb_b_wpen:                          ; ...and with a pen set per feature, which
    mov word [tb_left], TB_FEATURES ; is what a board of coloured figures on
.f:                                 ; VGA actually costs
    mov al, CLBLUE
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    mov cx, [tb_aw]
    mov dx, [tb_ah]
    mov bp, [tb_as]
    call tb_blit
    dec word [tb_left]
    jnz .f
    mov al, CWHITE                  ; ...and back, so the next row is not
    mov ah, CBLACK                  ; measuring a pen it did not set
    call OSAPI_GFX_BLIT1_PEN
    ret

; THE COMBAT FRAME (3.9.1): four projectiles in one lane, plus the acting
; lane's own figures still idling. The plan bills it at ~30 ms - 20 of
; projectiles and 10 of idles - which is 55% of the frame and the busiest the
; machine ever gets. If any row here is going to refuse the design, it is this
; one.
tb_b_combat:
    mov word [tb_left2], TB_LANES
.p:
    call tb_b_projl                 ; the LEAN one: a combat frame is the
                                    ; busiest the machine ever gets, so it is
                                    ; priced against the composite TITHE would
                                    ; actually ship and not against the first
                                    ; one anybody writes
    dec word [tb_left2]
    jnz .p
    mov word [tb_left2], TB_LANES
.i:
    call tb_b_full
    dec word [tb_left2]
    jnz .i
    ret

; =============================================================================
; SOUND - one note-on on each arm (TITHE-PLAN 13.5)
;
; The plan bills the sequencer at ~0.5% of the machine and says so as an
; ESTIMATE. A note-on is the expensive event in a tracker row - everything else
; is a table walk - so this is the figure that decides whether 13.6's sequencer
; can sit in the frame beside the wheel.
;
; --- AND THE FM ROW IS ASKED FOR PERMISSION FIRST, WHICH COST A DAY ---------
;
; The first version of this file ran the FM row unconditionally, on the
; reasoning that `OSAPI_SND_FM` "answers CF=1 with no sound driver loaded" and
; that pricing the REFUSAL was a legitimate row. **It is not, and the machine
; does not come back.** Called from inside benchlib's `cli` window on a machine
; with no sound driver, the guest wedges: it leaves the kernel entirely and
; spins with CS = 0, and ~98% of its samples land in the BIOS's own
; unexpected-interrupt handler at F000:FF23 - the one that masks the offending
; IRQ and stores it at 0040:006B.
;
; WHAT IT COST IS THE PART WORTH WRITING DOWN. The bench ran for SEVEN MINUTES
; of guest time and produced nothing, and the first reading of that was that
; `gfx_blit1` must be far slower than TITHE-PLAN 1.3 assumes - which is exactly
; the conclusion this bench was built to reach, so it looked like the finding
; rather than like a bug. It is not: reading `bl_nrow` out of the running
; package says every measurement row below completes in **under four guest
; seconds**, and the whole of the time was this one row, last in the list,
; never returning. A bench that hangs on its final row looks precisely like a
; bench whose rows are slow.
;
; So the rule this block now obeys: **ask OSAPI_SND_CAPS, outside the timed
; body, and do not call a sink that is not there.** SND_CAP_FM appears only
; while a sound driver is loaded (SPEC.md 34.2/51.4), which no machine in this
; tree boots with - so on an ordinary run the row is SKIPPED and says so in
; words. It is not a number that is missing: you cannot price a note-on on a
; machine that has no synthesiser, and a timed refusal would not be one anyway.
; =============================================================================
tb_b_tone:
    mov ax, 440
    mov cx, 1                       ; one tick, so nothing is left sounding
    mov dl, 0x40
    call OSAPI_SND_TONE
    ret

; ...and this body is reached ONLY when tb_caps says there is an FM sink.
tb_b_fm:
    mov al, 0                       ; verb 0: note-on
    mov cl, 0                       ; channel 0
    mov bx, 440
    call OSAPI_SND_FM
    ret

; =============================================================================
; BLOCK 10 - FULLSCREEN, AND OUR OWN ROW LOOP
;
; THE QUESTION: how much of a band's cost is the KERNEL'S, and would owning the
; framebuffer get it back?
;
; The rows above say a 56x56 band is 4,793 us on VGA and that **2,915 us of it
; is arrival and rows** - 709 of far call, nine refusals, the deferred cursor
; hide, the second-display span, the clip region, nine pushes, the display
; enter, the screen-extent clip, the pen and a rowbase multiply; then ~248
; clocks a row of which the payload is ~100. `gfx_blit1` is out of registers -
; all nine carry geometry - so its row loop reads FIVE SS-relative operands out
; of a stack frame, and on an 8088 each of those is ~22 clocks it would not
; spend if they were registers.
;
; **None of that work is wrong.** Every one of those tests is something a
; windowed program genuinely needs: it may be clipped, it may straddle two
; displays, the cursor may be over it, the pen may be set. A program that owns
; the whole screen needs none of them, and SPEC.md 53 is the door: inside an
; OSAPI_FSX_RUN bracket that has SET A MODE, the app owns every pixel,
; OSAPI_FSX_MODE hands back FSI_SEG, and no kernel drawing slot is legal
; anyway (53.7).
;
; So this block runs the SAME 56x56 band, into the SAME kind of framebuffer, by
; hand - and the difference between it and the row above is what a fullscreen
; TITHE would be buying.
;
; --- WHAT THE LOOP DELIBERATELY DOES AND DOES NOT DO ------------------------
;
; It does exactly what `gfx_blit1` does for a band that needs nothing: move the
; bytes, step the band by its stride, step the framebuffer by a row, and handle
; the BANK WRAP that both 1bpp adapters have (Hercules interleaves four banks,
; CGA two). It keeps all five of those in REGISTERS, which is the whole of the
; difference.
;
; It does NOT clip, resolve a display, hide a cursor, read a pen or validate an
; argument - because in a bracket there is nothing to clip against, one
; display, no cursor, and the caller is the only program running. Leaving those
; out is not cheating; it is the measurement.
;
; **WHITE ON BLACK NEEDS NO PORT WRITES ON ANY OF THE THREE.** On VGA 12h the
; resting state SPEC.md 5.4.2 pins - Map Mask 0Fh, Set/Reset disabled - puts a
; CPU write into all four planes, which is exactly a white-on-black band. So
; this loop is comparable to the DEFAULT-pen row above and not to a coloured
; one; a coloured band would add the two `out`s the kernel already measures at
; a fixed ~68 us.
;
; --- AND IT IS READ BACK, BECAUSE A FAST WRONG LOOP IS THE EASY MISTAKE -----
;
; The bracket restores the desktop whole on return, so nothing drawn here
; survives to be looked at. `tb_fs_check` reads the framebuffer back through
; the same geometry and compares it with the band; the report says MATCH or
; DIFFER in words. A read returns plane 0 on VGA (Read Map Select rests at 0)
; and the plain byte on both 1bpp adapters, and a white-on-black band is
; identical in every plane - so one compare covers all three.
; =============================================================================

; -----------------------------------------------------------------------------
; tb_own - the hand-rolled band emit. DX = rows; everything else from the
;          adapter's own geometry (3.2.1) and the FSI block.
;
; **THIS ADAPTER'S BAND, NOT A FIXED 56x56**, which the first cut of this block
; got wrong in the same way the pair row did: it drew the VGA sprite on all
; three, so CGA's "fullscreen" row was 56x56 against a windowed 48x24 and read
; as fullscreen being SLOWER. A lever has to be measured against the thing it
; is a lever on.
;
; EVERY PER-ROW VALUE IS IN A REGISTER, and that is the whole experiment:
; BX = the framebuffer row step, AX = the bank-wrap bit, BP = whole words a
; row, DX = rows left, SI/DI the two pointers. `gfx_blit1` reads five of those
; out of an SS-relative stack frame because all nine of its registers carry
; geometry it needs and this loop does not - ~22 clocks each on an 8088, every
; row. Only the wrap FIX stays in memory, and it is read on one row in four at
; the worst.
;
; Two bodies rather than a test in the loop: a stride is odd or even for the
; whole band, so the `movsb` tail is decided ONCE. That is what the kernel's
; `jnc .even` costs per row and what this does not.
; -----------------------------------------------------------------------------
tb_own:
    push es
    mov es, [tb_fseg]
    mov di, [tb_fsoff]
    mov si, tb_band
    mov bx, [tb_fsrowadd]
    mov ax, [tb_fswrapbit]          ; 0 on a linear surface, so the test below
    mov bp, [tb_as]                 ; can never fire there
    shr bp, 1                       ; BP = whole words a row
    cld
    test byte [tb_as], 1
    jnz .rodd
.reven:
    push di
    mov cx, bp
    rep movsw
    pop di
    add di, bx
    test di, ax
    jz .enw
    add di, [tb_fswrapfix]
.enw:
    dec dx
    jnz .reven
    pop es
    ret
.rodd:
    push di
    mov cx, bp
    rep movsw
    movsb                           ; the odd byte of an odd stride - 56 px is
    pop di                          ; seven bytes, which is VGA's
    add di, bx
    test di, ax
    jz .onw
    add di, [tb_fswrapfix]
.onw:
    dec dx
    jnz .rodd
    pop es
    ret

tb_b_own:                           ; one whole band
    mov dx, [tb_ah]
    jmp tb_own

tb_b_owndirty:                      ; ...and the two levers TOGETHER: our own
    mov dx, [tb_adirty]             ; loop AND only the rows that changed
    jmp tb_own

; -----------------------------------------------------------------------------
; tb_own_pl - the same band in N PLANES, our own loop, inside the bracket
; in:  CL = planes to write (2 = four colours, 4 = sixteen)
;
; **THIS IS WHAT "WE KNOW THE ADAPTER, SO COMPOSE IN NATIVE FORMAT" IS WORTH
; FOR COLOUR**, and it is the one place that phrase buys anything: a two-colour
; band is ALREADY native - `rep movsw` straight into mode 12h with the resting
; Map Mask puts the byte in all four planes - so there is no translation left
; to remove. Colour is different.
;
; `gfx_blitp` (SPEC.md 5.4.3) costs ~122 us a ROW-PLANE, because it sets the
; Map Mask and runs a `rep movsb` per plane PER ROW: 56 rows of four planes is
; 224 of those before a byte moves. Owning the card, the mask is set once per
; PLANE and the pass is a whole band - **four passes, not 224 row-plane
; operations.**
;
; AND THE PLANE COUNT IS log2(COLOURS), NOT FOUR. Set/Reset supplies every
; plane the sprite's palette agrees on, so a FOUR-colour figure varies two
; planes and takes two passes; sixteen colours takes four. That is SPEC.md
; 5.4.2.2's own plane arithmetic, one level up from a pen.
; -----------------------------------------------------------------------------
tb_own_pl:
    push es
    mov ch, cl                      ; CH = passes left
    mov byte [tb_plmask], 1         ; ...and the Map Mask walks the planes
.pass:
    push cx
    mov dx, TB_VGA_SEQ              ; SEQ index 2 = the Map Mask: which planes
    mov al, 2                       ; a CPU write lands in
    mov ah, [tb_plmask]
    out dx, ax
    mov es, [tb_fseg]
    mov di, [tb_fsoff]
    mov si, tb_planar               ; this plane's own image
    mov bx, [tb_fsrowadd]
    mov ax, [tb_fswrapbit]
    mov bp, [tb_as]
    shr bp, 1
    mov dx, [tb_ah]
    cld
    test byte [tb_as], 1
    jnz .rodd
.reven:
    push di
    mov cx, bp
    rep movsw
    pop di
    add di, bx
    test di, ax
    jz .e1
    add di, [tb_fswrapfix]
.e1:
    dec dx
    jnz .reven
    jmp short .next
.rodd:
    push di
    mov cx, bp
    rep movsw
    movsb
    pop di
    add di, bx
    test di, ax
    jz .o1
    add di, [tb_fswrapfix]
.o1:
    dec dx
    jnz .rodd
.next:
    shl byte [tb_plmask], 1         ; the next plane
    pop cx
    dec ch
    jnz .pass
    mov dx, TB_VGA_SEQ              ; ...and the Map Mask back to all four,
    mov ax, 0x0F02                  ; which is SPEC.md 5.4.2's resting state
    out dx, ax
    pop es
    ret

tb_b_own2pl:                        ; FOUR colours: two varying planes
    mov cl, 2
    jmp tb_own_pl

tb_b_own4pl:                        ; SIXTEEN colours: all four
    mov cl, 4
    jmp tb_own_pl

; -----------------------------------------------------------------------------
; tb_b_pit - what READING THE CLOCK costs, which is what a self-tuning wheel
;            would pay to know how it is doing
;
; Counter 0 of the 8253, latched and read - benchlib's own `bl_pit`, timed
; rather than used. A latch is a READ command and disturbs nothing; the
; question is only whether a renderer can afford to ask.
; -----------------------------------------------------------------------------
tb_b_pit:
    mov al, 0
    out 0x43, al
    jmp short $+2
    in al, 0x40
    mov ah, al
    jmp short $+2
    in al, 0x40
    ret

tb_b_ticks:                         ; ...and the API's own answer, for a
    call OSAPI_GET_TICKS            ; renderer that only needs whole frames
    ret

tb_b_ownwheel:                      ; 23 whole bands: the frame
    mov word [tb_left], TB_FEATURES
.f:
    call tb_b_own
    dec word [tb_left]
    jnz .f
    ret

tb_b_ownwdirty:                     ; THE COMBINED FRAME, which is the only
    mov word [tb_left], TB_FEATURES ; row that answers "can both levers
.f:                                 ; together put the rate back?"
    call tb_b_owndirty
    dec word [tb_left]
    jnz .f
    ret

; -----------------------------------------------------------------------------
; tb_fs_check - read the framebuffer back and compare it with the band
; out: [tb_fsok] = 1 match / 0 differ
; -----------------------------------------------------------------------------
tb_fs_check:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push ds
    push es
    push ds
    pop es                          ; ES = ours, explicitly: this routine is
                                    ; reached after a bracket call and an
                                    ; inherited ES is a thing to assume
    mov byte [tb_fsok], 1
    mov si, [tb_fsoff]
    mov bx, [tb_fsrowadd]
    mov dx, [tb_ah]
    mov di, tb_band                 ; ES:DI = the band (ES is ours on entry)
.row:
    push si
    mov cx, [cs:tb_as]
    push ds
    mov ds, [cs:tb_fseg]            ; DS:SI = the framebuffer
.b:
    mov al, [si]
    inc si
    cmp al, [es:di]
    je .same
    mov byte [es:tb_fsok], 0
.same:
    inc di
    loop .b
    pop ds
    pop si
    add si, bx
    test si, [tb_fswrapbit]
    jz .nowrap
    add si, [tb_fswrapfix]
.nowrap:
    dec dx
    jnz .row
    pop es
    pop ds
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tb_fs_proc - the bracket's body (SPEC.md 53.1)
; in:  SI = our window, ES = KERNEL_SEG, DS = CS = our segment. NEAR ret.
;
; Inside here every other task is frozen and the desktop is gone. benchlib's
; PIT reads are still legal - 53.1's "never touch PIT channel 0" forbids
; REPROGRAMMING it, and `bl_pit` issues control word 00h, which is a LATCH: it
; freezes a copy for reading and changes neither the mode nor the reload value
; (tests/benchlib.inc says so at the routine). The tick keeps time throughout.
; -----------------------------------------------------------------------------
tb_fs_proc:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es

    push ds
    pop es                          ; ES:DI = our own FSI block
    mov di, tb_fsi
    mov al, [tb_fsmode]
    call OSAPI_FSX_MODE
    jc .nomode

    mov ax, [tb_fsi + FSI_SEG]      ; ...and the framebuffer it answers with
    mov [tb_fseg], ax
    mov word [tb_fsoff], 0          ; the top-left: nothing else is on screen
    mov word [tb_fswrapbit], 0      ; a LINEAR surface has no wrap, and a zero
    mov word [tb_fswrapfix], 0      ; mask makes the test above never fire
    mov ax, [tb_fsi + FSI_STRIDE]
    mov [tb_fsrowadd], ax
    mov al, [tb_fsi + FSI_BANKS]
    cmp al, 2                       ; INTERLEAVED BANKS (SPEC.md 39.3): row y
    jb .linear                      ; lives at (y mod banks) * bstep +
    xor ah, ah                      ; (y / banks) * stride, so a row step is
    mov bx, [tb_fsi + FSI_BSTEP]    ; one bstep and every `banks`-th row steps
    mov [tb_fsrowadd], bx           ; back down and along
    mul bx                          ; AX = banks * bstep, a power of two on
    mov [tb_fswrapbit], ax          ; both adapters that have banks - so it is
    mov bx, [tb_fsi + FSI_STRIDE]   ; the bit a row step sets on the wrap, and
    sub bx, ax                      ; the fix is stride - banks * bstep. This
    mov [tb_fswrapfix], bx          ; is `gfx_blit1`'s own wrapbit/wrapfix
.linear:                            ; trick, which is why it is spelled the
                                    ; same way
    mov si, tb_s_fs1
    call bl_sline
    call bl_head

    mov word [bl_n], TB_N
    mov word [bl_body], tb_b_own
    mov si, tb_r_own
    xor al, al
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_town], ax
    mov [tb_town+2], dx

    call tb_fs_check                ; ...and is it the RIGHT picture?

    cmp byte [tb_planes], 0         ; the multi-plane arm is a VGA question:
    je .noplanes                    ; a 1bpp adapter has one plane and this
    mov word [bl_n], TB_N           ; whole block is meaningless there
    mov word [bl_body], tb_b_own2pl
    mov si, tb_r_own2pl
    xor al, al
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_town2], ax
    mov [tb_town2+2], dx

    mov word [bl_body], tb_b_own4pl
    mov si, tb_r_own4pl
    xor al, al
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_town4], ax
    mov [tb_town4+2], dx
.noplanes:

    mov word [bl_n], TB_N
    mov word [bl_body], tb_b_owndirty
    mov si, tb_r_owndirty
    xor al, al
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_townd], ax
    mov [tb_townd+2], dx

    mov word [bl_n], TB_NWHEEL
    mov word [bl_body], tb_b_ownwheel
    mov si, tb_r_ownwheel
    mov al, 1
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_townw], ax
    mov [tb_townw+2], dx

    mov word [bl_body], tb_b_ownwdirty
    mov si, tb_r_ownwdirty
    mov al, 1
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_townwd], ax
    mov [tb_townwd+2], dx

    mov byte [tb_fsran], 1
    jmp short .out
.nomode:
    mov byte [tb_fsran], 0
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tb_fs - enter the bracket. UI-task window callback only, lock held.
; -----------------------------------------------------------------------------
tb_fs:
    push ax
    push bx
    push cx
    push si
    call OSAPI_VIDEO                ; which mode is THIS adapter's own?
    mov byte [tb_fsmode], FSXM_VGA12
    cmp dh, 1
    ja .have
    mov byte [tb_fsmode], FSXM_HERC
    cmp dl, VID_CGA
    jne .have
    mov byte [tb_fsmode], FSXM_CGA640
.have:
    call bl_blank
    mov si, tb_s_h10
    call bl_sline
    mov ax, tb_fs_proc
    mov bx, [tb_win]
    xor cx, cx
    call OSAPI_FSX_RUN
    jnc .ok
    mov byte [tb_fsran], 0
.ok:
    call tb_fs_report
    pop si
    pop cx
    pop bx
    pop ax
    ret

; tb_fs_report - what the bracket found, including whether it ran at all
tb_fs_report:
    push si
    push di
    cmp byte [tb_fsran], 0
    jne .ran
    mov si, tb_r_own
    mov di, tb_s_nofs
    call bl_kvs
    jmp short .out
.ran:
    mov si, tb_r_fschk              ; the read-back, in WORDS - a loop that is
    mov di, tb_s_match              ; fast and wrong is the easy mistake here
    cmp byte [tb_fsok], 0
    jne .say
    mov di, tb_s_differ
.say:
    call bl_kvs
    mov si, tb_d_own                ; ...and what it bought, x100 percent,
    mov bx, tb_town                 ; against THIS adapter's own windowed band
    mov di, tb_tadapt
    call tb_pct
    mov si, tb_d_ownw
    mov bx, tb_townw
    mov di, tb_twad
    call tb_pct
    mov si, tb_d_ownwd              ; ...and BOTH levers, against this
    mov bx, tb_townwd               ; adapter's own unpaired wheel
    mov di, tb_twad
    call tb_pct
.out:
    pop di
    pop si
    ret

; =============================================================================
; tb_run - the whole suite
; =============================================================================
tb_run:
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    call tb_geom                    ; where the bands go, and what fits
    call tb_adapter                 ; ...and which surface's band is ours
    call OSAPI_SND_CAPS             ; ...and what this machine can SOUND, asked
    mov [tb_caps], ax               ; once, here, outside every cli window

    call bl_blank
    mov si, tb_s_title
    call bl_sline
    mov si, [tb_sname]
    call bl_sline
    call bl_head
    call bl_baseline                ; the loop overhead every P row is net of

    ; --- 1. BLIT1 at every surface's sprite size --------------------------
    mov si, tb_s_h1
    call bl_sline

    mov word [bl_n], TB_NBAR
    mov word [bl_body], tb_b_bar
    mov si, tb_r_bar
    xor al, al
    call bl_run
    mov ax, [bl_lastus]             ; the BAR, banked: Set 77 says 12,588 us
    mov dx, [bl_lastus+2]           ; and if this harness disagrees, THAT is
    mov [tb_tbar], ax               ; the finding and nothing below is to be
    mov [tb_tbar+2], dx             ; believed

    mov word [bl_n], TB_N
    mov word [bl_body], tb_b_cell
    mov si, tb_r_cell
    xor al, al
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_tcell], ax
    mov [tb_tcell+2], dx

    mov word [bl_body], tb_b_herc
    mov si, tb_r_herc
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_full
    mov si, tb_r_full
    xor al, al
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_tfull], ax
    mov [tb_tfull+2], dx

    mov word [bl_body], tb_b_win
    mov si, tb_r_win
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_cga
    mov si, tb_r_cga
    xor al, al
    call bl_run

    ; --- 2. the same 392 bytes in three shapes: the per-ROW term -----------
    mov si, tb_s_h2
    call bl_sline

    mov word [bl_body], tb_b_mid
    mov si, tb_r_mid
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_wide
    mov si, tb_r_wide
    xor al, al
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_twide], ax
    mov [tb_twide+2], dx

    ; --- 3. the pen, four paths -------------------------------------------
    mov si, tb_s_h3
    call bl_sline

    mov word [bl_body], tb_b_penonly
    mov si, tb_r_penonly
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_pendef
    mov si, tb_r_pendef
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_penink
    mov si, tb_r_penink
    xor al, al
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_tink], ax
    mov [tb_tink+2], dx

    mov word [bl_body], tb_b_peninv
    mov si, tb_r_peninv
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_pensplit
    mov si, tb_r_pensplit
    xor al, al
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_tsplit], ax
    mov [tb_tsplit+2], dx

    ; --- 4. the banded arm ------------------------------------------------
    mov si, tb_s_h4
    call bl_sline

    mov word [bl_body], tb_b_two
    mov si, tb_r_two
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_three
    mov si, tb_r_three
    xor al, al
    call bl_run

    ; --- 5. four planes ---------------------------------------------------
    mov si, tb_s_h5
    call bl_sline

    mov word [bl_n], TB_NPLANE
    mov word [bl_body], tb_b_pfull
    mov si, tb_r_pfull
    mov al, 1
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_tpfull], ax
    mov [tb_tpfull+2], dx

    mov word [bl_body], tb_b_pmid
    mov si, tb_r_pmid
    mov al, 1
    call bl_run

    mov word [bl_body], tb_b_pcell
    mov si, tb_r_pcell
    mov al, 1
    call bl_run

    ; --- 6. RAM: composition and the projectile ---------------------------
    mov si, tb_s_h6
    call bl_sline

    mov word [bl_n], TB_NRAM
    mov word [bl_body], tb_b_copy
    mov si, tb_r_copy
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_maskor
    mov si, tb_r_maskor
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_maskorl
    mov si, tb_r_maskorl
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_compose
    mov si, tb_r_compose
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_composel
    mov si, tb_r_composel
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_projn
    mov si, tb_r_proj
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_projl
    mov si, tb_r_projl
    xor al, al
    call bl_run
    mov ax, [bl_lastus]             ; the LEAN figure is the one banked: it is
    mov dx, [bl_lastus+2]           ; the composite TITHE would actually ship,
    mov [tb_tproj], ax              ; and 3.9.1's budget should be costed
    mov [tb_tproj+2], dx            ; against that rather than against the
                                    ; first loop anybody writes

    ; --- 7. the wheel, which is the brief ---------------------------------
    mov si, tb_s_h7
    call bl_sline

    mov word [bl_n], TB_N
    mov word [bl_body], tb_b_wadapt1
    mov si, tb_r_adapt1
    xor al, al
    call bl_run
    mov ax, [bl_lastus]             ; THE CONTROL block 10 is measured against
    mov dx, [bl_lastus+2]
    mov [tb_tadapt], ax
    mov [tb_tadapt+2], dx

    mov word [bl_n], TB_NWHEEL
    mov word [bl_body], tb_b_wfull
    mov si, tb_r_wfull
    mov al, 1
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_twfull], ax
    mov [tb_twfull+2], dx

    mov word [bl_body], tb_b_wadapt
    mov si, tb_r_wadapt
    mov al, 1
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_twad], ax
    mov [tb_twad+2], dx

    mov word [bl_body], tb_b_wpen
    mov si, tb_r_wpen
    mov al, 1
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_twpen], ax
    mov [tb_twpen+2], dx

    mov word [bl_body], tb_b_combat
    mov si, tb_r_combat
    mov al, 1
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_tcomb], ax
    mov [tb_tcomb+2], dx

    ; --- 9. the levers ----------------------------------------------------
    mov si, tb_s_h9
    call bl_sline

    mov word [bl_n], TB_N
    mov word [bl_body], tb_b_min
    mov si, tb_r_min
    xor al, al
    call bl_run
    mov ax, [bl_lastus]             ; THE ARRIVAL, measured. Everything above
    mov dx, [bl_lastus+2]           ; is priced against a fitted one
    mov [tb_tmin], ax
    mov [tb_tmin+2], dx

    mov word [bl_body], tb_b_short
    mov si, tb_r_short
    xor al, al
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_tshort], ax
    mov [tb_tshort+2], dx

    mov word [bl_body], tb_b_d7
    mov si, tb_r_d7
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_d5
    mov si, tb_r_d5
    xor al, al
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_td5], ax
    mov [tb_td5+2], dx

    mov word [bl_body], tb_b_d3
    mov si, tb_r_d3
    xor al, al
    call bl_run

    mov word [bl_n], TB_N / 2       ; the pair rows are two figures' worth
    mov word [bl_body], tb_b_two56
    mov si, tb_r_two56
    xor al, al
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_ttwo], ax
    mov [tb_ttwo+2], dx

    mov word [bl_body], tb_b_pairv
    mov si, tb_r_pairv
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_pairi
    mov si, tb_r_pairi
    xor al, al
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_tpairi], ax
    mov [tb_tpairi+2], dx

    mov word [bl_n], TB_NWHEEL
    mov word [bl_body], tb_b_wpair
    mov si, tb_r_wpair
    mov al, 1
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_twpair], ax
    mov [tb_twpair+2], dx
    ; --- THE REPEAT, and it is not a filler row ---------------------------
    ; Every headline this bench produces is a RATIO between two rows, so what
    ; two identical rows far apart in the run disagree by is the bar under all
    ; of them. This is `BLIT1 56x56 vgafull` again, sixty rows later.
    ;
    ; It exists because `BLIT1 adapter band` - the same geometry as the VGA
    ; sprite row, reached through three memory loads instead of three
    ; immediates, so if anything SLOWER - measured 2% FASTER on all three
    ; adapters. That is systematic rather than noise, it is not explained, and
    ; a 2% floor under every ratio here is worth stating rather than arguing
    ; about. Nothing in section 9 or 10 turns on 2%.
    mov word [bl_n], TB_N
    mov word [bl_body], tb_b_full
    mov si, tb_r_rpt
    xor al, al
    call bl_run
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_trpt], ax
    mov [tb_trpt+2], dx
    mov ax, [bl_lastus]
    mov dx, [bl_lastus+2]
    mov [tb_twpair], ax
    mov [tb_twpair+2], dx

    ; --- 8. sound ---------------------------------------------------------
    mov si, tb_s_h8
    call bl_sline

    mov word [bl_n], TB_N
    mov word [bl_body], tb_b_pit
    mov si, tb_r_pit
    xor al, al
    call bl_run

    mov word [bl_body], tb_b_ticks
    mov si, tb_r_ticks
    xor al, al
    call bl_run

    mov word [bl_n], TB_NSND
    mov word [bl_body], tb_b_tone
    mov si, tb_r_tone
    xor al, al
    call bl_run
    xor ax, ax                      ; ...and silence, whatever the last one left
    xor cx, cx
    mov dl, 0x40
    call OSAPI_SND_TONE

    test byte [tb_caps], SND_CAP_FM ; **NEVER unasked** - see the block header.
    jz .nofm                        ; With no driver this call does not refuse,
    mov word [bl_body], tb_b_fm     ; it wedges the machine from inside the cli
    mov si, tb_r_fm                 ; window, and a wedge on the LAST row reads
    xor al, al                      ; exactly like rows that are merely slow
    call bl_run
    jmp short .sndone
.nofm:
    call bl_lclr
    mov si, tb_r_fm
    xor di, di
    call bl_lput
    mov si, tb_s_nofm
    mov di, BL_C_N
    call bl_lput
    call bl_lcommit
.sndone:

    call tb_fs                      ; ...and the FULLSCREEN arm, last, because
                                    ; it takes the screen away and gives it
                                    ; back: every windowed row above must be
                                    ; measured before the desktop goes
    call tb_derive
    call tb_refusals
    call tb_save                    ; ...and onto the floppy, because 60 rows
                                    ; do not fit a 640x200 screen and a number
                                    ; read off a photograph is a number
                                    ; somebody typed again

    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tb_pct - one derived line: numerator / denominator, as a x100 percentage
; in:  SI = label, BX -> the numerator dword, DI -> the denominator dword -
;      both in benchlib's HUNDREDTHS of a microsecond ([bl_lastus]'s unit)
;
; **BOTH ARE DIVIDED BY 100 FIRST, AND THAT IS THE WHOLE POINT OF THE ROUTINE.**
; `bl_ratio` computes DX:AX * 100 / CX and CX is SIXTEEN BITS, so a denominator
; of 4,793.49 us - 479,349 hundredths - does not fit and the routine divides by
; its low word instead. It does not refuse and it does not wrap visibly: 479,349
; truncates to 4,317 and the line prints a plausible number 111x too big. Three
; of the derived lines below were printed that way before this existed, and the
; only reason it was caught is that the host script's own table disagrees -
; which a field run on a 5150 does not have.
;
; In whole microseconds every figure this bench produces fits a word with room
; to spare, and a percentage loses nothing to the rounding.
; -----------------------------------------------------------------------------
tb_pct:
    push ax
    push bx
    push cx
    push dx
    push di
    mov [tb_pnum], bx               ; bl_div32's remainder comes back in BX, so
                                    ; the numerator's pointer cannot live there
    mov byte [tb_pscale], 0
    mov ax, [di]                    ; the DENOMINATOR, in whole microseconds
    mov dx, [di+2]
    mov cx, 100
    call bl_div32
.fit:
    or dx, dx                       ; **AND KEEP DIVIDING UNTIL IT FITS A
    jz .have                        ; WORD.** Dividing by 100 once is enough
    inc byte [tb_pscale]            ; for a band (4,793 us) and is NOT enough
    mov cx, 10                      ; for a wheel (111,000), which is the
    call bl_div32                   ; second time this bench has been bitten
    jmp short .fit                  ; by bl_ratio's 16-bit CX. The first time
.have:                              ; three derived lines printed 111x too big
    mov [tb_den], ax                ; and the host table is what caught it;
    mov bx, [tb_pnum]               ; this time it was a ratio of 152% for
    mov ax, [bx]                    ; something the same table said was 53%.
    mov dx, [bx+2]                  ; A percentage loses nothing to the
    mov cx, 100                     ; rounding, so the scaling is free
    call bl_div32
    mov cl, [tb_pscale]
.sc:
    or cl, cl                       ; ...and the NUMERATOR is scaled by exactly
    jz .done                        ; the same amount, or the ratio is wrong by
    push cx                         ; a power of ten - which is the failure
    mov cx, 10                      ; this whole routine exists to stop
    call bl_div32
    pop cx
    dec cl
    jmp short .sc
.done:
    mov cx, [tb_den]
    or cx, cx
    jnz .ok
    inc cx                          ; a row that measured zero: print 0 rather
.ok:                                ; than divide by it
    call bl_ratio
    mov cx, 9
    call bl_kv
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tb_derive - the lines nobody should have to work out off the page
; -----------------------------------------------------------------------------
tb_derive:
    push ax
    push bx
    push cx
    push dx
    push si

    call bl_blank
    mov si, tb_s_d
    call bl_sline

    ; The per-ROW cost, in hundredths of a us: (56 rows - 14 rows) of the same
    ; 392 bytes is 42 rows of pure row overhead. THIS IS THE NUMBER THE PLAN
    ; DOES NOT HAVE - every budget in it is derived from a per-byte reading.
    mov ax, [tb_tfull]
    mov dx, [tb_tfull+2]
    sub ax, [tb_twide]
    sbb dx, [tb_twide+2]
    jnc .haverow
    xor ax, ax                      ; the wide row measured slower: no per-row
    xor dx, dx                      ; term visible above the noise
.haverow:
    mov cx, TB_FH - TB_NH
    call bl_div32
    mov si, tb_d_perrow
    mov cx, 9
    call bl_kv

    ; ...and what a 56x56 band is as a share of ONE FEATURE'S budget. 23
    ; features in 40% of a frame is 955 us each (TITHE-PLAN 1.3), so this is
    ; x100 percent of that.
    mov ax, [tb_tfull]
    mov dx, [tb_tfull+2]
    mov cx, TB_FRAMEUS * 4 / 10 / TB_FEATURES
    call bl_ratio
    mov si, tb_d_share
    mov cx, 9
    call bl_kv

    ; The CELL against the BAND - TITHE-PLAN 3.4 claims 58% off every commit
    ; for drawing the figure's own box instead of the whole cell. x100 percent.
    mov si, tb_d_cell
    mov bx, tb_tfull
    mov di, tb_tcell
    call tb_pct

    ; The SPLIT pen against the cheap one - 5.4.2.2.1's second pass, x100
    mov si, tb_d_split
    mov bx, tb_tsplit
    mov di, tb_tink
    call tb_pct

    ; FOUR PLANES against one bit, x100. TITHE-PLAN 1.2 says 4x the bytes and
    ; therefore 4x the cost; Set 108's two-term model says far worse, because
    ; 56 rows becomes 224 row-plane operations before a byte moves.
    mov si, tb_d_plane
    mov bx, tb_tpfull
    mov di, tb_tfull
    call tb_pct

    ; ...and the PROJECTILE against one idle band, which is the number 3.9.1's
    ; whole budget turns on: four of these plus the acting lane's idles is the
    ; busiest frame in the game.
    mov si, tb_d_proj
    mov bx, tb_tproj
    mov di, tb_tfull
    call tb_pct

    ; ...and the harness's own repeatability, which bounds every line above
    mov si, tb_d_rpt
    mov bx, tb_trpt
    mov di, tb_tfull
    call tb_pct

    call bl_blank
    mov si, tb_s_d2
    call bl_sline

    ; --- and the four that answer the brief, as x100 PERCENT OF A FRAME ----
    mov ax, [tb_twfull]
    mov dx, [tb_twfull+2]
    mov cx, TB_FRAMEUS
    call bl_ratio
    mov si, tb_d_wfull
    mov cx, 9
    call bl_kv

    mov ax, [tb_twad]
    mov dx, [tb_twad+2]
    mov cx, TB_FRAMEUS
    call bl_ratio
    mov si, tb_d_wadapt
    mov cx, 9
    call bl_kv

    mov ax, [tb_twpen]
    mov dx, [tb_twpen+2]
    mov cx, TB_FRAMEUS
    call bl_ratio
    mov si, tb_d_wpen
    mov cx, 9
    call bl_kv

    mov ax, [tb_tcomb]
    mov dx, [tb_tcomb+2]
    mov cx, TB_FRAMEUS
    call bl_ratio
    mov si, tb_d_comb
    mov cx, 9
    call bl_kv

    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tb_refusals - what answered CF=1, in words
;
; A refusal is a NORMAL PATH here and the whole point of running this on three
; adapters. `gfx_blitp` refuses on 1bpp and `snd_fm` refuses with no driver;
; both then cost almost nothing, and a fast row is exactly what a refusal looks
; like from the numbers alone. So the state is READ and printed rather than
; inferred - which is also the only way a VGA run can prove the planes really
; were drawn.
; -----------------------------------------------------------------------------
tb_refusals:
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    call bl_blank
    mov si, tb_s_cf
    call bl_sline

    push es                         ; BLITP, asked once outside any timed row
    push ds
    pop es
    mov si, tb_planar
    mov cx, TB_FW
    mov dx, TB_FH
    mov di, TB_FS * TB_FH
    mov bp, TB_FS
    mov ax, [tb_bx]
    mov bx, [tb_by]
    call OSAPI_GFX_BLITP
    pop es
    mov di, tb_s_drawn
    jnc .p0
    mov di, tb_s_refused
.p0:
    mov si, tb_r_cfp
    call bl_kvs

    mov di, tb_s_nodrv              ; ...and FM, which is asked of the CAPS and
    test byte [tb_caps], SND_CAP_FM ; not of the slot: see the sound block's
    jz .f0                          ; header for what asking the slot costs
    mov di, tb_s_ok
.f0:
    mov si, tb_r_cff
    call bl_kvs

    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tb_save - write the report under a name that says which adapter made it
;
; THE THREE FILES ARE THE DELIVERABLE. This bench's whole purpose is a
; comparison ACROSS adapters - the pen rows must land on each other on 1bpp and
; separate on VGA, the blitp rows must refuse on 1bpp and draw on VGA - and a
; comparison wants three files a diff can be run over, not three photographs.
;
; MartyPC keeps the guest's writes in RAM, so nothing lands on the image until
; something spends them: `tools/os88flush.py` is how these reach the host, and
; tests/titheband.py does it per adapter.
; -----------------------------------------------------------------------------
tb_save:
    push ax
    push bx
    push cx
    push dx
    push si
    call OSAPI_VIDEO
    mov si, tb_f_vga
    cmp dh, 1                       ; depth first, adapter only to tell the two
    ja .go                          ; 1bpp ones apart (SPEC.md's own rule)
    mov si, tb_f_herc
    cmp dl, VID_CGA
    jne .go
    mov si, tb_f_cga
.go:
    call bl_save
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tb_geom - where a band may be put down without being clipped
;
; `gfx_blit1` honours the clip region to the exact pixel row, so a band that
; hangs off the content measures the clip and not the band - and it would do so
; by a different amount on each adapter, which is precisely the comparison this
; bench exists to make. The origin is the content's own top-left, which WF_SNAP
; has already put on a multiple of 8.
; -----------------------------------------------------------------------------
tb_geom:
    push ax
    push bx
    push cx
    push dx
    mov bx, [tb_win]
    call OSAPI_WM_GEOM              ; CX = content w, DX = content h
    mov [tb_cw], cx
    mov [tb_ch], dx
    mov bx, [tb_win]
    call OSAPI_WM_CONTENT           ; AX = content left, DX = top
    mov [tb_bx], ax
    mov [tb_by], dx
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tb_adapter - which of TITHE-PLAN 3.2.1's four bands is THIS surface's
;
; The wheel is run twice on purpose: once at 56x56 so the three adapters can be
; read against each other at one size, and once at the band the plan actually
; gives this surface, which is the question that decides whether the design
; holds HERE. A single size would answer only one of the two.
; -----------------------------------------------------------------------------
tb_adapter:
    push ax
    push bx
    push cx
    push dx
    call OSAPI_VIDEO                ; AX = w, BX = h, DL = adapter, DH = bpp
    mov word [tb_aw], TB_FW         ; VGA fullscreen: cell 104x72, RISE 20
    mov word [tb_ah], TB_FH
    mov word [tb_as], TB_FS
    mov word [tb_pw], 104 + TB_FW
    mov word [tb_ph], TB_FH + 20
    mov word [tb_ps], (104 + TB_FW) / 8
    mov word [tb_adirty], TB_FH / 2
    mov byte [tb_planes], 1         ; ...and this surface HAS planes
    mov word [tb_sname], tb_s_vga
    cmp dh, 1                       ; SPEC.md's own rule: branch on DEPTH, and
    ja .out                         ; on the adapter only to tell the two 1bpp
    cmp dl, VID_CGA                 ; ones apart
    je .cga
    mov word [tb_aw], TB_HW         ; Hercules: cell 120x52, RISE 16
    mov word [tb_ah], TB_HH
    mov word [tb_as], TB_HS
    mov word [tb_pw], 120 + TB_HW
    mov word [tb_ph], TB_HH + 16
    mov word [tb_ps], (120 + TB_HW) / 8
    mov word [tb_adirty], TB_HH / 2
    mov byte [tb_planes], 0
    mov word [tb_sname], tb_s_herc
    jmp short .out
.cga:
    mov word [tb_aw], TB_CW         ; CGA: cell 80x30, RISE 8
    mov word [tb_ah], TB_CH
    mov word [tb_as], TB_CS
    mov word [tb_pw], 80 + TB_CW
    mov word [tb_ph], TB_CH + 8
    mov word [tb_ps], (80 + TB_CW) / 8
    mov word [tb_adirty], TB_CH / 2
    mov byte [tb_planes], 0
    mov word [tb_sname], tb_s_cga
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

%include "benchlib.inc"

; =============================================================================
; data
; =============================================================================

tb_tpl:
    dw 7, 22, 624, 440              ; x = 7 so WF_SNAP wants W_X + 1 on a
    dw tb_ttl, tb_paint, tb_onkey, tb_onclick   ; multiple of 8. wm_create
                                    ; clamps an oversized frame onto the live
                                    ; screen, so this is the VGA shape and CGA
                                    ; gets what fits

tb_ttl:     db 'Tithe Band Bench', 0

tb_s_title: db 'TITHEBAND - wave 0 of docs/plans/TITHE-PLAN.md (3.7)', 0
tb_s_sub:   db 'Does a 56x56 band cost what a 128x128 one says it does?', 0
tb_s_hint:  db 'Click the window, or press R, to run. S re-saves the file.', 0
tb_f_vga:   db 'TITHVGA.TXT', 0
tb_f_herc:  db 'TITHHERC.TXT', 0
tb_f_cga:   db 'TITHCGA.TXT', 0
tb_s_vga:   db 'surface: VGA / EGA - 4bpp, the pen is READ, planes exist', 0
tb_s_herc:  db 'surface: HERCULES - 1bpp, the pen is NOT read, no planes', 0
tb_s_cga:   db 'surface: CGA - 1bpp, the pen is NOT read, no planes', 0

tb_s_h1:    db '-- 1. BLIT1 at each surface sprite size (3.2.1) --', 0
tb_s_h2:    db '-- 2. the SAME 392 bytes, fewer rows: the per-ROW term --', 0
tb_s_h3:    db '-- 3. the PEN, all four paths (SPEC.md 5.4.2.2) --', 0
tb_s_h4:    db '-- 4. the BANDED arm: same bytes, more arrivals (3.5b) --', 0
tb_s_h5:    db '-- 5. FOUR PLANES: the Rich arm (3.5c). 1bpp REFUSES --', 0
tb_s_h6:    db '-- 6. RAM: composition (4.2.1) and the projectile (3.9.1) --', 0
tb_s_h7:    db '-- 7. THE WHEEL: 23 features, one update each --', 0
tb_s_h8:    db '-- 8. a note-on on each sound arm (13.5) --', 0
tb_s_h9:    db '-- 9. THE LEVERS: what would buy the rate back --', 0
tb_s_h10:   db '-- 10. FULLSCREEN: our own row loop, no kernel call --', 0
tb_s_d:     db '-- derived: x100, so 250 means 2.50 --', 0
tb_s_d2:    db '-- and these four are x100 PERCENT OF ONE 54.925ms FRAME --', 0
tb_s_cf:    db '-- what REFUSED, in words rather than in a small number --', 0

tb_r_bar:   db 'BLIT1 128x128 bar', 0
tb_r_cell:  db 'BLIT1 104x72 cell', 0
tb_r_herc:  db 'BLIT1 64x40 herc', 0
tb_r_full:  db 'BLIT1 56x56 vgafull', 0
tb_r_win:   db 'BLIT1 48x44 vgawin', 0
tb_r_cga:   db 'BLIT1 48x24 cga', 0
tb_r_mid:   db 'BLIT1 112x28 =392B', 0
tb_r_wide:  db 'BLIT1 224x14 =392B', 0
tb_r_penonly: db 'PEN set+restore', 0
tb_r_pendef: db 'BLIT1 pen default', 0
tb_r_penink: db 'BLIT1 pen ink/black', 0
tb_r_peninv: db 'BLIT1 pen black/white', 0
tb_r_pensplit: db 'BLIT1 pen split 8on7', 0
tb_r_two:   db 'BLIT1 56x56 2 strips', 0
tb_r_three: db 'BLIT1 56x56 3 strips', 0
tb_r_pfull: db 'BLITP 56x56 4plane', 0
tb_r_pmid:  db 'BLITP 112x28 4plane', 0
tb_r_pcell: db 'BLITP 104x72 4plane', 0
tb_r_copy:  db 'COPY 392B strided', 0
tb_r_maskor: db 'MASKOR 240B naive', 0
tb_r_maskorl: db 'MASKOR 240B interleavd', 0
tb_r_composel: db 'COMPOSE lean', 0
tb_r_projl: db 'PROJECTILE lean', 0
tb_r_compose: db 'COMPOSE body+item', 0
tb_r_proj:  db 'PROJECTILE 1 frame', 0
tb_r_wfull: db 'WHEEL 23x 56x56', 0
tb_r_wadapt: db 'WHEEL 23x adapter', 0
tb_r_wpen:  db 'WHEEL 23x pen+adapt', 0
tb_r_combat: db 'COMBAT 4proj+4idle', 0
tb_r_min:   db 'BLIT1 8x1 THE ARRIVAL', 0
tb_r_short: db 'BLIT1 56x40 shorter', 0
tb_r_d7:    db 'BLIT1 56x39 dirty 70%', 0
tb_r_d5:    db 'BLIT1 56x28 dirty 50%', 0
tb_r_d3:    db 'BLIT1 56x20 dirty 35%', 0
tb_r_two56: db 'PAIR 2 x 56x56 apart', 0
tb_r_pairv: db 'PAIR 56x118 stacked', 0
tb_r_pairi: db 'PAIR 160x76 one lane', 0
tb_r_wpair: db 'WHEEL 13x paired', 0
tb_r_rpt:   db 'BLIT1 56x56 REPEAT', 0
tb_r_adapt1: db 'BLIT1 adapter band', 0
tb_r_own:   db 'FSX own loop 1 band', 0
tb_r_ownwheel: db 'FSX own loop 23x', 0
tb_r_owndirty: db 'FSX own 1 band dirty', 0
tb_r_own2pl: db 'FSX own 2 planes 4col', 0
tb_r_own4pl: db 'FSX own 4 planes 16c', 0
tb_r_pit:   db 'PIT latch + read', 0
tb_r_ticks: db 'OSAPI_GET_TICKS', 0
tb_r_ownwdirty: db 'FSX own 23x dirty', 0
tb_r_fschk: db 'FSX read-back says', 0
tb_s_fs1:   db 'the framebuffer is ours; no clip, no cursor, no pen', 0
tb_s_match: db 'MATCH - the right pixels', 0
tb_s_differ: db 'DIFFER - the loop is WRONG, ignore its time', 0
tb_s_nofs:  db 'NOT RUN - the bracket or the mode was refused', 0
tb_d_own:   db 'own loop vs BLIT1', 0
tb_d_dirty: db 'dirty rect vs whole', 0
tb_d_ownw:  db 'own wheel vs BLIT1', 0
tb_d_ownwd: db 'own+dirty vs BLIT1', 0
tb_r_tone:  db 'SND_TONE note-on', 0
tb_r_fm:    db 'SND_FM note-on', 0

tb_d_perrow: db 'BLIT1 us/row x100', 0
tb_d_share: db 'band vs 955us budget', 0
tb_d_cell:  db 'band vs whole cell', 0
tb_d_split: db 'split pen vs cheap', 0
tb_d_plane: db '4 planes vs 1 bit', 0
tb_d_proj:  db 'projectile vs a band', 0
tb_d_rpt:   db 'repeat vs first x100', 0
tb_d_wfull: db 'wheel 56x56', 0
tb_d_wadapt: db 'wheel adapter band', 0
tb_d_wpen:  db 'wheel with pen', 0
tb_d_comb:  db 'combat frame', 0

tb_r_cfp:   db 'GFX_BLITP 56x56', 0
tb_r_cff:   db 'SND_FM note-on', 0
tb_s_drawn: db 'DRAWN (CF=0)', 0
tb_s_refused: db 'REFUSED (CF=1)', 0
tb_s_ok:    db 'SND_CAP_FM - a driver is loaded', 0
tb_s_nodrv: db 'no SND_CAP_FM - no sound driver', 0
tb_s_nofm:  db 'SKIPPED - no FM sink on this machine', 0

tb_win:     dw 0
tb_cx:      dw 0
tb_cy:      dw 0
tb_cw:      dw 0
tb_ch:      dw 0
tb_bx:      dw 0
tb_by:      dw 0
tb_aw:      dw TB_FW
tb_ah:      dw TB_FH
tb_as:      dw TB_FS
tb_pw:      dw 104 + TB_FW
tb_ph:      dw TB_FH + 20
tb_ps:      dw (104 + TB_FW) / 8
tb_adirty:  dw TB_FH / 2
tb_planes:  db 1
tb_plmask:  db 1
tb_sname:   dw tb_s_vga
tb_caps:    dw 0
tb_lean:    db 0
tb_den:     dw 0
tb_pnum:    dw 0
tb_pscale:  db 0
tb_left:    dw 0
tb_left2:   dw 0
tb_ww:      dw 0
tb_wh:      dw 0
tb_ws:      dw 0

tb_tbar:    dw 0, 0
tb_tcell:   dw 0, 0
tb_tfull:   dw 0, 0
tb_twide:   dw 0, 0
tb_tink:    dw 0, 0
tb_tsplit:  dw 0, 0
tb_tpfull:  dw 0, 0
tb_tproj:   dw 0, 0
tb_twfull:  dw 0, 0
tb_twad:    dw 0, 0
tb_twpen:   dw 0, 0
tb_tcomb:   dw 0, 0
tb_tmin:    dw 0, 0
tb_tshort:  dw 0, 0
tb_td5:     dw 0, 0
tb_ttwo:    dw 0, 0
tb_tpairi:  dw 0, 0
tb_twpair:  dw 0, 0
tb_town:    dw 0, 0
tb_townw:   dw 0, 0
tb_townd:   dw 0, 0
tb_townwd:  dw 0, 0
tb_tadapt:  dw 0, 0
tb_trpt:    dw 0, 0
tb_town2:   dw 0, 0
tb_town4:   dw 0, 0
tb_fseg:    dw 0
tb_fsoff:   dw 0
tb_fsrowadd: dw 0
tb_fswrapbit: dw 0
tb_fswrapfix: dw 0
tb_fsmode:  db 0
tb_fsran:   db 0
tb_fsok:    db 0
tb_fsi:     times FSI_SIZE db 0

; ROUNDED TO 512, AND `align 512` BELOW, AND NEITHER IS TIDINESS. `bl_save`
; hands OSAPI_FILE_WRITE a pointer into `bl_out`, and dsk_xfer issues int 13h
; DIRECTLY to it - the floppy controller's DMA reads these very bytes. An ISA
; bus master cannot carry into the 8237's page port, so a transfer crossing a
; 64KB physical boundary wraps to the start of its page and moves the wrong
; memory instead. A 512-aligned base plus 512 bytes cannot cross one, which is
; why every disk-visible base in this system is aligned and why BL_BSS puts
; bl_out first. **QEMU MODELS NONE OF THIS** - its floppy DMA has no page wrap
; - so the failure is invisible here and is a report full of somebody else's
; memory on a real XT.
TB_BSS_RAW  equ TB_BANDSZ + TB_PLANSZ + TB_ITSZ * 4 + 512 + TB_BGSZ
TB_BSS_OWN  equ ((TB_BSS_RAW + 511) / 512) * 512

    align 512                       ; ...so os88_image_end is a multiple of 512
    OS88_BSS TB_BSS_OWN + BL_BSS_SIZE
    OS88_IMAGE_END

tb_band     equ os88_image_end + 0
tb_planar   equ os88_image_end + TB_BANDSZ
tb_item     equ os88_image_end + TB_BANDSZ + TB_PLANSZ
tb_imask    equ os88_image_end + TB_BANDSZ + TB_PLANSZ + TB_ITSZ
tb_dst      equ os88_image_end + TB_BANDSZ + TB_PLANSZ + TB_ITSZ * 4
tb_ilv      equ os88_image_end + TB_BANDSZ + TB_PLANSZ + TB_ITSZ * 2
tb_bg       equ os88_image_end + TB_BANDSZ + TB_PLANSZ + TB_ITSZ * 4 + 512

    BL_BSS os88_image_end + TB_BSS_OWN
