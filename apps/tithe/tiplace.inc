; =============================================================================
; os8088 - apps/tithe/tiplace.inc
;
; THE BOARD AS A PLACE (SPEC.md 97.4.10) and the figures that stand on it
; (SPEC.md 97.4.9). Four things live here:
;
;   THE ARENA    one heap claim holding every composed picture: a STRIP per
;                column - its ground, fences, wall and cliff, top to bottom -
;                and four composed poses for every one of the twenty cells.
;   THE STRIPS   composed at layout from tiground.inc's tables, and the board
;                is then four blits rather than twenty.
;   THE CELLS    a figure's band is cut from its cell's rows of its column's
;                strip and the figure MASKED over it, so a detailed figure
;                keeps its black detail over a lit ground and every cell stands
;                on its own column's texture.
;   THE READER   `ti_pic_band` / `ti_pic_stat`: the board AS THE GLASS SHOWS
;                IT under any band at an 8-aligned x - the strips, every
;                cell's figure as last committed, and its numbers - for what
;                crosses cells it does not own: a projectile.
;
; WHY A HEAP CLAIM. The poses used to be three - one per character, composed
; once over one tile every cell shared - and lived in the package's own bss.
; A column's texture is not its neighbour's, so a figure composed over its
; column's ground stands in that column only, and the poses are per CELL now:
; 80 of them, 30,720 bytes on a fullscreen VGA, with the strips another 14,400.
; That is not a segment's worth of bss; it is TITHE-PLAN 1.5's "composed idle
; sprites" line arriving, and it is where the final game keeps them anyway.
; =============================================================================

TI_ARENAKB  equ 41                ; 28,160 of poses + 13,200 of strips on the
                                  ; biggest surface (VGA, 64 x 44 bands and a
                                  ; 275-row strip), and ti_place_lay refuses
                                  ; a layout that would not fit rather than
                                  ; trusting this arithmetic
TI_STATBANK equ TI_CELLS * TI_POSES * TI_RVMAX ; the NUMBERS, after the
                                  ; attack frames in their claim: a cell's
TI_STATREC  equ 2 * TI_CELLBANDMAX ; halo then its digits, for a bolt to go
                                  ; under (ti_pic_stat)
TI_FIGKB    equ 10                ; the hand's portraits: 7 cards x 4 poses
                                  ; x the biggest band, 352 bytes on a VGA -
                                  ; 9,856, and ti_layout refuses the hand on
                                  ; a surface that would not fit
TI_ATTACKKB equ 37                ; 20 cells x 4 attack frames x the biggest
                                  ; band, 352 bytes on a VGA - and then the
                                  ; twenty cells' numbers at 480

; -----------------------------------------------------------------------------
; ti_arena_claim - claim the arena. out: CF=1 refused. Preserves registers.
;
; FROM THE ENTRY PROC, where an app sizes itself (OSAPI_MEM_CLAIM's own note):
; a machine that cannot hold the board refuses the launch rather than opening
; a window it can draw nothing in.
; -----------------------------------------------------------------------------
ti_arena_claim:
    push ax
    push dx
    mov ax, TI_ARENAKB
    call OSAPI_MEM_CLAIM
    jc .out
    mov [ti_aseg], dx
    mov ax, ti_arena_move           ; ONE WORD NAMES IT and nothing is derived
    call OSAPI_MEM_MOVABLE          ; from it - every reader loads ES from
                                    ; [ti_aseg] - so the proc is one store. A
                                    ; refusal leaves it pinned, which is legal
    mov ax, TI_ATTACKKB             ; ...and THE ATTACK FRAMES: every cell's
    call OSAPI_MEM_CLAIM            ; four, composed ahead as TITHE-PLAN 4.2.3
    jc .out                         ; says and never inside a frame
    mov [ti_kseg], dx
    mov ax, ti_attack_move
    call OSAPI_MEM_MOVABLE
    mov ax, TI_FIGKB                ; ...and THE HAND'S PORTRAITS: every card's
    call OSAPI_MEM_CLAIM            ; figure at the BOARD's size on black, four
    jc .out                         ; poses each, for the fullscreen hand
    mov [ti_fseg], dx               ; (SPEC.md 97.4.12). Claimed with the rest
    mov ax, ti_fig_move             ; rather than at the F key: a key that
    call OSAPI_MEM_MOVABLE          ; could fail for memory is a refusal the
    clc                             ; player meets mid-game
.out:
    pop dx
    pop ax
    ret

; the relocation proc (OSAPI_MEM_MOVABLE): BX = where it was, DX = where it is
ti_arena_move:
    mov [ti_aseg], dx
    ret

ti_attack_move:
    mov [ti_kseg], dx
    ret

ti_fig_move:
    mov [ti_fseg], dx
    ret

; -----------------------------------------------------------------------------
; ti_place_lay - the arena's layout and the board's growth, for this surface
; in:  ti_layout has set the cell, the band and [ti_boardh]
; out: CF=1 the arena cannot hold it. Preserves every register.
;
; THE BOARD GROWS BY E under column 0: the front lane's ground runs on past its
; cells' floor to the lip, which sits on the same slope as every fence, and
; the cliff hangs under that. E is RISE + FH + 1 + D, a table row per surface -
; and on a CGA it is exactly the eight rows the window has spare.
; -----------------------------------------------------------------------------
ti_place_lay:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov si, [ti_gidx]
    shl si, 1
    shl si, 1
    shl si, 1
    add si, ti_gsz                  ; FH, WH, D, E
    mov ax, [si]
    mov [ti_fenh], ax
    mov ax, [si + 2]
    mov [ti_wh], ax
    mov ax, [si + 4]
    mov [ti_dd], ax
    mov ax, [si + 6]
    mov [ti_ext], ax
    add [ti_boardh], ax

    mov ax, [ti_cw]                 ; a strip is one column, whole
    shr ax, 1
    shr ax, 1
    shr ax, 1
    mov [ti_sb], ax
    mov ax, [ti_ch]
    mov cx, TI_ROWS
    mul cx
    add ax, [ti_ext]
    mov [ti_sh], ax
    mul word [ti_sb]
    mov [ti_spitch], ax
    mov ax, [ti_bs]                 ; ...and a pose is one band
    mul word [ti_bh]
    mov [ti_cslot], ax
    mov cx, TI_CELLS * TI_POSES
    mul cx
    jc .no
    mov [ti_sbase], ax              ; the strips sit after the eighty poses
    mov bx, ax
    mov ax, [ti_spitch]
    shl ax, 1
    shl ax, 1
    add ax, bx
    jc .no
    cmp ax, TI_ARENAKB * 1024
    ja .no

    ; --- THE SLOPE, once: yoff[lx] = RISE * (CW - lx) / CW ---------------
    ; Every fence, the wall and the lip sit on it, and it is what makes a
    ; column's line meet its neighbour's: column c+1 stands RISE higher, and
    ; yoff runs from RISE at its left to ~0 at its right.
    xor di, di
.y:
    cmp di, [ti_cw]
    jae .ydone
    mov ax, [ti_cw]
    sub ax, di
    mul word [ti_rise]
    div word [ti_cw]
    mov [ti_yoff + di], al
    inc di
    jmp short .y
.ydone:
    clc
    jmp short .out
.no:
    stc
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_strips_build - compose the four column strips into the arena
; Preserves every register.
;
; tools/os88tithebg.py's algorithm, step for step, and its model is what the
; mock-ups and tests/titheterr.py compare against:
;   1. every row is the column's texture row (ly mod n), 4 bytes repeated;
;   2. then per PIXEL COLUMN lx, with y0 = yoff[lx]: black above the wall, the
;      wall, a fence at the top of lanes 1..4, the lit lip, the cliff, black
;      below - and the board's two outside edges lit down their length.
; A pattern row is four bytes, (ink, mask) as two big-endian words over 16
; pixels, so pixel lx is bit (lx AND 7) of byte ((lx SHR 3) AND 1).
; -----------------------------------------------------------------------------
ti_strips_build:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    mov es, [ti_aseg]
    cld
    mov word [ti_sc], 0
.col:
    mov ax, [ti_gidx]               ; this surface's and terrain's row of
    mov cx, TI_TERRAINS             ; ti_gtex: four textures and the divide
    mul cx
    add ax, [ti_terr]
    mov cx, 5
    mul cx
    shl ax, 1
    mov si, ax
    mov ax, [ti_gtex + si + 8]
    mov [ti_fence], ax
    mov ax, [ti_sc]
    shl ax, 1
    add si, ax
    mov ax, [ti_gtex + si]
    mov [ti_tex], ax
    mov ax, [ti_sc]
    mul word [ti_spitch]
    add ax, [ti_sbase]
    mov [ti_sp], ax

    ; --- 1. THE TEXTURE -------------------------------------------------
    mov di, ax                      ; a row is its four texture bytes and
    mov si, [ti_tex]                ; then itself again: `movsb` from the row's
    mov bl, [si]                    ; own start, four behind, replicates them
    xor bh, bh                      ; across the rest in one instruction
    inc si
    xor dx, dx                      ; DX = the texture row, running
    mov bp, [ti_sh]
    push ds
.trow:
    or bp, bp
    jz .tdone
    push si
    mov ax, dx
    shl ax, 1
    shl ax, 1
    add si, ax
    movsw
    movsw
    pop si
    mov cx, [ti_sb]
    sub cx, 4
    push si
    push ds
    mov ax, es
    mov ds, ax
    mov si, di
    sub si, 4
    rep movsb
    pop ds
    pop si
    inc dx
    cmp dx, bx
    jb .tr1
    xor dx, dx
.tr1:
    dec bp
    jmp short .trow
.tdone:
    pop ds

    ; --- 2. PER PIXEL COLUMN: the wall, the fences, the lip, the cliff ----
    ; ONE POINTER WALKS DOWN THE COLUMN, and every stretch it passes is in
    ; row order - clear, wall, gap, fence, gap, ..., lip, cliff, clear - so a
    ; stretch it does not touch is one ADD of rows x stride, taken from the
    ; table below. It was a multiply a stretch and a call a row, and a board
    ; took a second and a half of an 8088 to compose.
    mov ax, [ti_ch]                 ; the three gaps, in bytes
    sub ax, [ti_wh]
    mul word [ti_sb]
    mov [ti_gapw], ax               ; after the wall, to fence 1
    mov ax, [ti_ch]
    sub ax, [ti_fenh]
    mul word [ti_sb]
    mov [ti_gapf], ax               ; after a fence, to the next
    mov ax, [ti_ch]
    mul word [ti_sb]
    mov [ti_gapl], ax               ; after fence 4, to the lip
    mov word [ti_lx], 0
.px:
    mov ax, [ti_lx]
    cmp ax, [ti_cw]
    jb .pgo
    jmp .pdone
.pgo:
    mov cl, al
    and cl, 7
    mov ah, 80h
    shr ah, cl                      ; AH = this pixel's bit
    mov al, ah
    not al                          ; AL = everything else
    mov bx, [ti_lx]
    mov cl, [ti_yoff + bx]
    xor ch, ch
    mov [ti_y0], cx
    shr bx, 1
    shr bx, 1
    shr bx, 1
    mov si, [ti_lx]                 ; the pattern byte: (lx SHR 3) AND 1
    shr si, 1
    shr si, 1
    shr si, 1
    and si, 1
    mov [ti_pbyte], si
    add bx, [ti_sp]                 ; BX = row 0 of this pixel column
    mov dx, [ti_sb]                 ; DX = the stride, for every stretch

    call .clr                       ; a. black above the wall (CX = y0)
    push bx                         ; b. the WALL
    mov bx, [ti_gidx]
    shl bx, 1
    mov si, [ti_gwall + bx]
    pop bx
    mov cx, [ti_wh]
    call .pat
    add bx, [ti_gapw]
    mov di, TI_ROWS - 1             ; c. the four FENCES
.fk:
    mov si, [ti_fence]
    mov cx, [ti_fenh]
    call .pat
    dec di
    jz .lip
    add bx, [ti_gapf]
    jmp short .fk
.lip:
    add bx, [ti_gapl]               ; d. the LIP, lit...
    or [es:bx], ah
    add bx, dx
    push bx                         ; ...and the CLIFF under it
    mov bx, [ti_gidx]
    shl bx, 1
    mov si, [ti_gcliff + bx]
    pop bx
    mov cx, [ti_dd]
    call .pat
    mov cx, [ti_sh]                 ; e. and black below it
    sub cx, [ti_y0]
    sub cx, [ti_fenh]
    sub cx, [ti_dd]
    dec cx
    push ax
    push dx
    mov ax, [ti_ch]
    mov dx, TI_ROWS
    mul dx
    sub cx, ax
    pop dx
    pop ax
    jle .edge
    call .clr

.edge:                              ; f. THE BOARD'S TWO SIDES, lit down
    mov cx, [ti_sc]                 ;    their length - two pixel columns
    or cx, cx                       ;    in the whole board, so they take the
    jnz .e3                         ;    slow road
    cmp word [ti_lx], 0
    jne .pnext
    jmp short .eset
.e3:
    cmp cx, TI_COLS - 1
    jne .pnext
    mov cx, [ti_cw]
    dec cx
    cmp cx, [ti_lx]
    jne .pnext
.eset:
    mov bx, [ti_lx]
    mov cl, bl
    and cl, 7
    mov al, 80h
    shr al, cl
    mov [ti_pbit], al
    shr bx, 1
    shr bx, 1
    shr bx, 1
    mov [ti_pcol], bx
    mov ax, [ti_ch]
    mov cx, TI_ROWS
    mul cx
    add ax, [ti_fenh]
    add ax, [ti_dd]
    inc ax
    mov cx, ax                      ; from y0 to the cliff's foot
    mov dx, [ti_y0]
    call ti_sp_set
.pnext:
    test byte [ti_lx], 7            ; the music every eight columns: a strip
    jnz .pn8                        ; is ~200 ms of this on a VGA (timus.inc)
    call tm_run
.pn8:
    inc word [ti_lx]
    jmp .px

; the two stretch writers: BX walks down by DX a row, CX rows, AH the bit
.clr:
    jcxz .cret
.cl:
    and [es:bx], al
    add bx, dx
    loop .cl
.cret:
    ret
.pat:                               ; SI = the pattern, four bytes a row
    jcxz .pret
    push si
    add si, [ti_pbyte]
.pr:
    test [si + 2], ah
    jz .pn                          ; mask 0: the ground shows through
    test [si], ah
    jz .pd
    or [es:bx], ah
    jmp short .pn
.pd:
    and [es:bx], al
.pn:
    add si, 4
    add bx, dx
    loop .pr
    pop si
.pret:
    ret
.pdone:
    call tm_run                     ; ...and between strips
    inc word [ti_sc]
    cmp word [ti_sc], TI_COLS
    jae .out
    jmp .col
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

; --- the per-pixel-column writers. DX = the first strip row, CX = how many.
; They walk the column a row at a time by ADDING the strip's stride, so a run
; costs one multiply and not one a row. Rows past the strip are dropped.
; Preserve every register bar the flags.
ti_sp_run:                          ; BX = the address of row DX, CX clipped
    push ax
    push dx
    mov ax, [ti_sh]
    sub ax, dx
    jbe .none
    cmp cx, ax
    jbe .n
    mov cx, ax
.n:
    mov ax, dx
    mul word [ti_sb]
    add ax, [ti_sp]
    add ax, [ti_pcol]
    mov bx, ax
    pop dx
    pop ax
    ret
.none:
    xor cx, cx
    pop dx
    pop ax
    ret

ti_sp_set:
    push ax
    push bx
    push cx
    call ti_sp_run
    jcxz .out
    mov al, [ti_pbit]
.r:
    or [es:bx], al
    add bx, [ti_sb]
    loop .r
.out:
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_cells_build - every cell's eight frames: its ground, then its character
; Preserves every register.
; -----------------------------------------------------------------------------
ti_cells_build:
    push word [ti_ci]
    mov word [ti_cfbeg], 0          ; all eight frames of every cell
    mov word [ti_cfend], 2 * TI_POSES
    mov word [ti_ci], 0
.cell:
    cmp word [ti_ci], TI_CELLS
    jae .done
    call tm_run                     ; the music between cells (timus.inc): a
    call ti_cell_build              ; relayout composes twenty of them
    inc word [ti_ci]
    jmp short .cell
.done:
    pop word [ti_ci]
    ret

; -----------------------------------------------------------------------------
; ti_cell_gsrc - [ti_gsrc] = the arena offset of cell [ti_ci]'s first GROUND
; byte: its column's strip, at the cell's row and figure inset. A row below it
; is [ti_sb] further on. Preserves every register.
; -----------------------------------------------------------------------------
ti_cell_gsrc:
    push ax
    push bx
    push cx
    push dx
    mov ax, [ti_ci]
    xor dx, dx
    mov cx, TI_ROWS
    div cx                          ; AX = column, DX = row
    push dx
    mul word [ti_spitch]
    add ax, [ti_sbase]
    mov bx, ax                      ; BX = the column's strip
    pop ax
    mul word [ti_ch]
    add ax, [ti_insy]
    mul word [ti_sb]
    add ax, bx
    push ax
    mov ax, [ti_ci]
    xor dx, dx
    mov cx, TI_ROWS
    div cx
    call ti_col_insx                ; this column's inset: P2's is mirrored
    shr ax, 1
    shr ax, 1
    shr ax, 1
    pop bx
    add ax, bx
    mov [ti_gsrc], ax
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_cell_ground - cell [ti_ci]'s ground into its four slots in the claim at ES
; - the arena's idle poses or the attack claim's frames, which share offsets -
; out of its column's strip, and REPLICATED: slot 0 row by row, then one
; overlapping `rep movsw` carries slot 0 into 1, 1 into 2 and 2 into 3.
; in:  [ti_gsrc] set (ti_cell_gsrc). Preserves every register.
; -----------------------------------------------------------------------------
ti_cell_ground:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push word [ti_pi]
    cld
    mov word [ti_pi], 0
    call ti_cellpose_addr           ; DI = slot 0
    push di
    mov si, [ti_gsrc]
    mov bx, [ti_sb]
    mov dx, [ti_bs]
    mov bp, [ti_bh]
    push ds
    mov ds, [ti_aseg]               ; the strips are the arena's
.gr:
    or bp, bp
    jz .grd
    push si
    mov cx, dx
    rep movsb
    pop si
    add si, bx
    dec bp
    jmp short .gr
.grd:
    pop ds
    pop si
    mov di, si                      ; DI trails SI by exactly one slot. A slot
    add di, [ti_cslot]              ; is BS x BH and BS is a whole number of
    mov ax, [ti_cslot]              ; bytes, so it is even
    mov cx, TI_POSES - 1
    mul cx
    mov cx, ax
    shr cx, 1
    push ds
    push es
    pop ds
    rep movsw
    pop ds
    pop word [ti_pi]
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_cell_build - cell [ti_ci]'s frames [ti_cfbeg] to [ti_cfend] - 1, for
; whoever stands there now: 0-3 the idle poses, 4-7 the attack frames.
; Preserves every register.
;
; ONE CELL IS A UNIT OF WORK because a REVEAL changes one cell (tirv.inc):
; the card played is composed into its cell and nothing else is touched.
; -----------------------------------------------------------------------------
ti_cell_build:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    mov es, [ti_aseg]
    cld
    push word [ti_pi]
    mov ax, [ti_ci]
    call ti_ck_cell                 ; [ti_ck] = who stands here
    call ti_cell_gsrc               ; [ti_gsrc] = the band's first ground byte
    ; --- THE GROUND under every slot the range covers ----------------------
    cmp word [ti_cfbeg], TI_POSES
    jae .kground
    mov es, [ti_aseg]               ; the idle poses' four slots...
    call ti_cell_ground
    cmp word [ti_cfend], TI_POSES
    jbe .grounded
    ; ...AND THE FOUR ATTACK SLOTS, in their own claim: the same ground under
    ; the same cell, copied from the four the arena has just had
    mov word [ti_pi], 0
    call ti_cellpose_addr
    mov si, di                      ; SI = the arena's slot 0, a fresh ground
    push es                         ; still
    push ds
    mov ax, [ti_kseg]
    mov bx, es
    mov es, ax
    mov ds, bx
    mov cx, [cs:ti_cslot]           ; CS = our segment: DS is the arena here
    shl cx, 1
    shl cx, 1
    shr cx, 1                       ; four slots, in words
    rep movsw
    pop ds
    pop es
    jmp short .grounded
.kground:
    cmp word [ti_cfbeg], TI_POSES   ; THE ATTACK FRAMES ALONE, later than the
    jne .grounded                   ; poses (ti_rv_atk): their ground goes down
    mov es, [ti_kseg]               ; ONCE, with the first of them - a frame
    call ti_cell_ground             ; at a time, grounding all four again
.grounded:                          ; each call wiped the ones already built
    mov es, [ti_aseg]

    ; --- THE CHARACTER: its body, then the item in its near hand -----------
    mov ax, [ti_bs]                 ; the window every pose goes into
    mov [ti_fa_stride], ax
    mov [ti_fa_wb], ax
    mov ax, [ti_bh]
    mov [ti_fa_h], ax
    mov [ti_cbh], ax
    mov word [ti_cdx], 0
    mov word [ti_cdy], 0
    mov ax, [ti_gidx]
    mov [ti_csurf], ax
    mov ax, [ti_ci]
    call ti_cell_side               ; which item, and which way it faces

    ; --- THE EIGHT FRAMES: four idle into the arena, four attack into their
    ; own claim - and a frame the tool says is the SAME PICTURE as an earlier
    ; one is copied from it rather than composed again (a quarter of them)
    mov al, 0
    call op_seg
    push es
    mov es, ax
    mov ax, [ti_ck]
    shl ax, 1
    add ax, [ti_cst]
    push dx                         ; x the THREE board surfaces
    mov dx, ax
    shl ax, 1
    add ax, dx
    pop dx
%if TI_CHAR_BG != 3
%error "ti_csame multiplies by three board surfaces: TI_CHAR_BG moved"
%endif
    add ax, [ti_gidx]
    shl ax, 1
    shl ax, 1
    shl ax, 1
    add ax, TI_P_SAME
    mov [ti_csame], ax              ; this cell's row of the same-as table
    pop es
    mov ax, [ti_cfbeg]
    mov [ti_cfr], ax
.frame:
    mov ax, [ti_cfr]
    cmp ax, [ti_cfend]
    jb .fgo
    jmp .fdone
.fgo:
    mov ax, [ti_cfr]
    call ti_frame_slot              ; ES:DI = where frame AX goes
    push es
    mov al, 0
    call op_seg
    mov es, ax
    mov bx, [ti_csame]
    add bx, [ti_cfr]
    mov al, [es:bx]
    xor ah, ah
    pop es
    cmp ax, [ti_cfr]
    je .compose
    push ds                         ; --- A COPY of frame AX, already built
    push es
    push di
    call ti_frame_slot              ; ES:DI = the frame it is a copy of
    mov si, di
    mov ax, es
    pop di
    pop es
    mov cx, [ti_cslot]
    shr cx, 1
    mov ds, ax
    rep movsw
    pop ds
    jmp short .fnext
.compose:
    push word [ti_cdx]
    xor bx, bx
    mov ax, [ti_cfr]
    cmp ax, TI_POSES
    jb .nolunge
    sub ax, TI_POSES
    call ti_cl_lunge                ; an attack's strike steps in
    mov bx, [ti_cdx]
.nolunge:
    pop word [ti_cdx]
    add [ti_cdx], bx
    call ti_char_put
    sub [ti_cdx], bx
.fnext:
    inc word [ti_cfr]
    jmp .frame
.fdone:
    mov byte [ti_fa_mir], 0
    pop word [ti_pi]
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_frame_slot - ES:DI = where cell [ti_ci]'s frame AX lives: 0-3 in the
; arena, 4-7 in the attack claim. Preserves every register bar ES and DI.
ti_frame_slot:
    push ax
    push word [ti_pi]
    mov es, [ti_aseg]
    cmp ax, TI_POSES
    jb .have
    sub ax, TI_POSES
    mov es, [ti_kseg]
.have:
    mov [ti_pi], ax
    call ti_cellpose_addr
    pop word [ti_pi]
    pop ax
    ret

; ti_cellpose_addr - DI = the arena offset of cell [ti_ci]'s pose [ti_pi]
; Preserves every register bar DI.
ti_cellpose_addr:
    push ax
    push dx
    mov ax, [ti_ci]
    shl ax, 1
    shl ax, 1                       ; TI_POSES is four
    add ax, [ti_pi]
    mul word [ti_cslot]
    mov di, ax
    pop dx
    pop ax
    ret

; ti_cell_side - for cell AX: [ti_cst] = the item it carries - FRONT in
; columns 1 and 2, REAR in 0 and 3 (TITHE-PLAN 5.2, and wave 1a's fiction for
; where a card stands) - and [ti_fa_mir] = 1 in P2's columns, which face the
; other way (SPEC.md 97.4.9). Preserves every register.
ti_cell_side:
    push ax
    call ti_cell_stance
    xor ah, ah
    cmp al, TI_COLS / 2
    cmc
    sbb al, al
    and al, 1
    mov [ti_fa_mir], al
    pop ax
    ret

; ti_cell_stance - [ti_cst] for cell AX; out AL = its column. Preserves the
; rest.
ti_cell_stance:
    push dx
    push cx
    xor dx, dx
    mov cx, TI_ROWS
    div cx                          ; AX = the column
    mov word [ti_cst], TI_ROW_REAR
    cmp al, 1
    je .front
    cmp al, 2
    jne .out
.front:
    mov word [ti_cst], TI_ROW_FRONT
.out:
    pop cx
    pop dx
    ret

; ti_dirty_rows - AL = the first row, AH = how many, that the move INTO pose
; [ti_pi] of card [ti_ck] in stance [ti_cst] touches, on this surface (SPEC.md
; 97.4.3). The TOOL's rows, from the composed characters alone, so they hold
; over whatever ground a cell composed. Preserves every register bar AX.
ti_dirty_rows:
    push bx
    push es
    mov al, 0
    call op_seg
    mov es, ax
    mov ax, [ti_ck]
    shl ax, 1
    add ax, [ti_cst]
    mov bx, ax                      ; x the three board surfaces (BX is
    shl ax, 1                       ; loaded again below)
    add ax, bx
    add ax, [ti_gidx]
    shl ax, 1
    shl ax, 1
    shl ax, 1                       ; x four (dy, dh) pairs
    mov bx, [ti_pi]
    shl bx, 1
    add bx, ax
    mov ax, [es:bx + TI_P_DIRTY]
    pop es
    pop bx
    ret

; -----------------------------------------------------------------------------
; ti_char_put - card [ti_ck], stance [ti_cst], frame [ti_cfr] (0..3 idle,
; 4..7 attack), surface [ti_csurf], into the window at ES:DI
; in:  [ti_fa_stride] [ti_fa_wb] [ti_fa_h] [ti_fa_mir] - the window, as
;      ti_fig_apply takes it; [ti_cbh] the band height it stands for,
;      [ti_cdx] bytes and [ti_cdy] rows to move the whole character by
; Preserves every register.
;
; THE LAYER MODEL, and the whole of it on the machine (TITHE-PLAN 4.2.1): the
; card names a body and two items; the BODY's pose goes down, and then the
; ITEM's frame at the body's anchor for that pose. An attack is the item's
; frames 4-7 over the body's pose 0. Both are masked, so the item's own ring
; parts it from the torso and the body's halo parts it from the ground.
; -----------------------------------------------------------------------------
ti_char_put:
    push ax
    push bx
    push cx
    push dx
    push si
    push es                         ; [sp] = the window's segment
    mov al, 0
    call op_seg                     ; read at the point of use: a part's
    mov [ti_pseg], ax               ; segment is not a thing to cache
    mov es, ax
    mov bx, [ti_ck]                 ; the card: body, front item, rear item
    mov ax, bx
    shl bx, 1
    add bx, ax
    add bx, TI_P_CARDS
    mov al, [es:bx]
    xor ah, ah
    mov [ti_cbody], ax
    mov si, [ti_cst]
    mov al, [es:bx + si + 1]
    mov [ti_citem], ax

    mov ax, [ti_cbody]              ; --- THE BODY ---------------------------
    mov cx, TI_CHAR_G
    mul cx
    add ax, [ti_csurf]
    shl ax, 1
    mov bx, ax
    mov bx, [es:bx + TI_P_BODYTAB]
    mov si, [ti_cfr]
    cmp si, TI_POSES                ; an attack stands on the body's pose 0
    jb .bp
    xor si, si
.bp:
    mov al, [es:bx + TI_BR_BH]      ; the band it was cut for, against the one
    xor ah, ah                      ; it goes into: a shorter one keeps the
    neg ax                          ; FLOOR
    add ax, [ti_cbh]
    add ax, [ti_cdy]
    mov [ti_cyy], ax
    mov al, [es:bx + si + TI_BR_BX]
    xor ah, ah
    add ax, [ti_cdx]
    mov [ti_fa_dx], ax
    mov al, [es:bx + si + TI_BR_BY]
    xor ah, ah
    add ax, [ti_cyy]
    mov [ti_fa_dy], ax
    mov al, [es:bx + si + TI_BR_AX]
    xor ah, ah
    mov [ti_cax], ax
    mov al, [es:bx + si + TI_BR_AY]
    xor ah, ah
    mov [ti_cay], ax
    shl si, 1
    mov ax, [es:bx + si]            ; ...its figure
    pop es
    push es
    call ti_fig_fetch
    call ti_fig_apply

    mov es, [ti_pseg]               ; --- THE ITEM, at the anchor ------------
    mov ax, [ti_citem]
    mov cx, TI_CHAR_G
    mul cx
    add ax, [ti_csurf]
    shl ax, 1
    mov bx, ax
    mov bx, [es:bx + TI_P_ITEMTAB]
    mov si, [ti_cfr]
    mov al, [es:bx + si + TI_IR_DX]
    cbw
    add ax, [ti_cax]
    add ax, [ti_cdx]
    mov [ti_fa_dx], ax
    mov al, [es:bx + si + TI_IR_DY]
    cbw
    add ax, [ti_cay]
    add ax, [ti_cyy]
    mov [ti_fa_dy], ax
    shl si, 1
    mov ax, [es:bx + si]
    pop es
    push es
    call ti_fig_fetch
    call ti_fig_apply
    pop es
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_fig_fetch - AX = a figure's offset in the art part: copy it into
; ti_figbuf and answer SI = ti_figbuf. Preserves every register bar SI.
;
; A COPY, because ti_fig_apply reads its figure through DS and keeps its own
; state and its bit-reverse table there too. A figure is a few hundred bytes,
; and the copy is one `rep movsb` against a masked loop over the same bytes.
ti_fig_fetch:
    push ax
    push cx
    push di
    push es
    push ds
    pop es                          ; ES = here
    mov di, ti_figbuf
    mov si, ax
    mov ax, [ti_pseg]
    push ds
    mov ds, ax                      ; DS = the part
    mov al, [si]
    mul byte [si + 1]               ; wb x rows
    shl ax, 1
    add ax, 2
    mov cx, ax
    cld
    rep movsb
    pop ds
    pop es
    pop di
    pop cx
    pop ax
    mov si, ti_figbuf
    ret

; -----------------------------------------------------------------------------
; ti_fig_apply - put figure SI into the band at ES:DI
; in:  [ti_fa_dx] bytes and [ti_fa_dy] rows to shift it by (signed),
;      [ti_fa_stride], [ti_fa_wb] bytes and [ti_fa_h] rows the band has,
;      and [ti_fa_mir] = 1 to put it down mirrored
; Preserves every register.
;
; `band = (band AND NOT mask) OR ink`, a byte at a time, one `lodsw` fetching
; the pair - TITHE-PLAN 4.2.1's interleaved order, measured 14% faster than
; two buffers. Anything outside the band is skipped rather than written.
; -----------------------------------------------------------------------------
ti_fig_apply:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    cld
    mov ax, [ti_fa_dx]              ; the figure's first byte column, which
    mov [ti_fa_x0], ax              ; the caller placed
    mov al, [si]
    xor ah, ah
    mov [ti_fa_n], ax               ; bytes a row
    mov al, [si + 1]
    xor ah, ah
    mov bp, ax                      ; rows
    add si, 2

    ; THE COLUMNS ARE CLIPPED ONCE, not per byte: [lo, hi) of each row's
    ; bytes land inside the band, and the rest are stepped over
    xor cx, cx                      ; CX = lo
    mov ax, [ti_fa_x0]
    or ax, ax
    jns .lo
    neg ax
    mov cx, ax
.lo:
    mov ax, [ti_fa_wb]              ; hi = min(n, wb - x0)
    sub ax, [ti_fa_x0]
    cmp ax, [ti_fa_n]
    jle .hi
    mov ax, [ti_fa_n]
.hi:
    cmp ax, cx
    jg .cols
    jmp .out                        ; nothing of it is inside the band
.cols:
    mov [ti_fa_hi], ax
    mov [ti_fa_lo], cx
    mov ax, [ti_fa_x0]
    add ax, cx
    cmp byte [ti_fa_mir], 0         ; MIRRORED, byte c lands at WB-1-c: the
    je .unm                         ; same bytes clip, from the other end
    neg ax
    add ax, [ti_fa_wb]
    dec ax
.unm:
    add di, ax                      ; DI = the band's row 0, at the first byte
    mov dx, [ti_fa_dy]
    mov ax, dx
    or ax, ax
    jns .d0
    xor ax, ax
.d0:
    push dx
    mul word [ti_fa_stride]
    pop dx
    add di, ax                      ; ...at the first row that can land
.row:
    or bp, bp
    jz .out
    or dx, dx
    js .skip
    cmp dx, [ti_fa_h]
    jge .out                        ; below the band: nothing more lands
    push si
    mov ax, [ti_fa_lo]
    shl ax, 1
    add si, ax
    mov bx, di                      ; BX keeps the row; DI walks it
    mov cx, [ti_fa_hi]
    sub cx, [ti_fa_lo]
    cmp byte [ti_fa_mir], 0
    jne .mir
.mb:                                ; ONE READ AND ONE WRITE a byte: the band
    lodsw                           ; byte is fetched into a register, masked
    not ah                          ; and inked there, and stored with stosb -
    and ah, [es:di]                 ; half the bus traffic of two read-modify-
    or al, ah                       ; writes on memory, which is the whole of
    stosb                           ; the cost on an 8088
    loop .mb
    jmp short .rdone
.mir:                               ; MIRRORED: each byte's bits reversed by
    push bx                         ; table, written right to left
    mov bx, ti_rev
.mb2:
    lodsw                           ; AL = ink, AH = mask
    xlat
    xchg al, ah
    xlat                            ; AL = the mask, AH = the ink, reversed
    not al
    and al, [es:di]
    or al, ah
    mov [es:di], al
    dec di
    loop .mb2
    pop bx
.rdone:
    mov di, bx
    pop si
    add di, [ti_fa_stride]
.skip:
    mov ax, [ti_fa_n]
    shl ax, 1
    add si, ax
    inc dx
    dec bp
    jmp short .row
.out:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_board_strips - the board's ground: the four strips, and black in the two
; corners the shear leaves above and below each one. Preserves registers.
;
; NO FILL UNDER A STRIP. A fill of the board's box followed by the strips is
; the ground drawn twice, the first time black (PERFORMANCE.md rule 2): each
; column's strip IS its ground, so only what no strip covers is filled.
; -----------------------------------------------------------------------------
ti_board_strips:
    push ax
    push bx
    push cx
    push dx
    push si
    push bp
    push es
    mov word [ti_sc], 0
.col:
    cmp word [ti_sc], TI_COLS
    jb .go
    jmp .out
.go:
    mov ax, [ti_sc]
    mul word [ti_cw]
    add ax, [ti_bx]
    mov [ti_sx], ax
    mov ax, TI_COLS - 1             ; the strip's top: this column's lift
    sub ax, [ti_sc]
    mul word [ti_rise]
    add ax, [ti_by]
    mov [ti_sy], ax

    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, [ti_sx]                 ; the corner ABOVE it
    mov bx, [ti_by]
    mov cx, ax
    add cx, [ti_cw]
    dec cx
    mov dx, [ti_sy]
    dec dx
    cmp dx, bx
    jl .nabove
    call OSAPI_GFX_FILL
.nabove:
    mov bx, [ti_sy]                 ; ...and BELOW it
    add bx, [ti_sh]
    mov dx, [ti_by]
    add dx, [ti_boardh]
    dec dx
    cmp dx, bx
    jl .nbelow
    call OSAPI_GFX_FILL
.nbelow:

    mov ax, [ti_sc]                 ; the strip, in blits of at most 200 rows:
    mul word [ti_spitch]            ; gfx_blit1 takes 255, and a fullscreen
    add ax, [ti_sbase]              ; strip is 300
    mov si, ax
    mov es, [ti_aseg]
    mov bx, [ti_sy]
    mov ax, [ti_sh]
    mov [ti_sr], ax
.chunk:
    mov dx, [ti_sr]
    or dx, dx
    jz .next
    cmp dx, 200
    jbe .last
    mov dx, 200
.last:
    sub [ti_sr], dx
    mov ax, [ti_sx]
    mov cx, [ti_cw]
    mov bp, [ti_sb]
    call OSAPI_GFX_BLIT1
    call tm_run                     ; ...and between a strip's blits
    push dx
    mov ax, dx
    mul word [ti_sb]
    add si, ax
    pop dx
    add bx, dx
    jmp short .chunk
.next:
    inc word [ti_sc]
    jmp .col
.out:
    pop es
    pop bp
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_gnd_prep - the RUNS under CX bytes from screen x AX: one per board column
; the band crosses, each with its strip, its column and where in it the run
; starts (ti_pic_band reads them). Preserves every register.
; -----------------------------------------------------------------------------
ti_gnd_prep:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    ; THE BAND IS RUNS, ONE PER COLUMN IT CROSSES - at most three for a band
    ; narrower than a column - and a run is made WHOLE: one divide finds where
    ; it starts, and its length is what is left of its column. It walked the
    ; band a byte at a time, a push, a divide and a test in each, and that
    ; was 1.3 ms of every bolt band.
    mov word [ti_grk], 0
    xor si, si                      ; SI = the run in hand, x 2
    mov dx, ax
    sub dx, [ti_bx]                 ; DX = x on the board, signed
    jns .on
    neg dx                          ; --- the bytes LEFT of the board
    shr dx, 1
    shr dx, 1
    shr dx, 1
    cmp dx, cx
    jbe .lft
    mov dx, cx
.lft:
    call .off
    sub cx, dx
    shl dx, 1
    shl dx, 1
    shl dx, 1
    add ax, dx
.on:
    or cx, cx
    jz .out
    mov dx, ax
    sub dx, [ti_bx]
    cmp dx, [ti_boardw]
    jb .col
    mov dx, cx                      ; --- the bytes RIGHT of it
    call .off
    jmp short .out
.col:
    push ax
    push cx
    mov ax, dx
    xor dx, dx
    div word [ti_cw]                ; AX = the column, DX = x inside it
    mov [ti_grc + si], ax
    mov [ti_grlx + si], dx
    mov bx, [ti_cw]                 ; its length: the rest of the column,
    sub bx, dx                      ; or the rest of the band
    shr bx, 1
    shr bx, 1
    shr bx, 1
    pop cx
    cmp bx, cx
    jbe .len
    mov bx, cx
.len:
    mov [ti_grn + si], bx
    push bx
    push dx
    mov di, ax                      ; DI = the column
    mul word [ti_spitch]
    add ax, [ti_sbase]
    pop dx
    shr dx, 1
    shr dx, 1
    shr dx, 1
    add ax, dx                      ; AX = the run's first byte, strip row 0
    mov [ti_grbase + si], ax
    mov ax, TI_COLS - 1
    sub ax, di
    mul word [ti_rise]
    add ax, [ti_by]
    mov [ti_grtop + si], ax         ; the strip's top on the screen
    mul word [ti_sb]
    sub [ti_grbase + si], ax        ; ...so screen row y is base + y * SB
    pop bx
    pop ax
    sub cx, bx
    shl bx, 1
    shl bx, 1
    shl bx, 1
    add ax, bx
    add si, 2
    inc word [ti_grk]
    jmp .on
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
; .off - an OFF-BOARD run of DX bytes at SI, which reads black. Advances SI.
.off:
    or dx, dx
    jz .offx
    mov [ti_grn + si], dx
    mov word [ti_grtop + si], 0FFFFh
    mov word [ti_grc + si], 0FFFFh
    add si, 2
    inc word [ti_grk]
.offx:
    ret

; -----------------------------------------------------------------------------
; ti_pic_band - THE BOARD AS IT IS ON THE GLASS, under a band that crosses cells
; it does not own: the columns' ground, then every cell's figure band as it was
; last committed (ti_shseg/ti_shoff). The NUMBERS are a second call, after the
; caller has put down whatever it carries (ti_pic_stat) - so a bolt goes OVER
; the characters and UNDER the digits.
; in:  AX = x (a multiple of 8), BX = the first row, CX = bytes, DX = rows,
;      DI = the band (in this segment, stride CX)
; Preserves every register.
;
; THE BOLT'S BAND WAS GROUND ALONE, so a bolt crossing a cell painted the
; ground over the figure standing in it and left it that way until the wheel
; came round. Everything the glass holds under a board band is already in RAM:
; the strips, and the band each cell was last committed from - the idle pose,
; a clash's attack frame, a reveal's dissolve - which ti_feature and the reveal
; RECORD as they commit it, so this reads what the glass shows and never
; re-derives it.
; -----------------------------------------------------------------------------
ti_pic_band:
    push ax
    push bx
    push cx
    push dx
    push di
    push es
    mov [ti_pbx], ax
    mov [ti_pby], bx
    mov [ti_pbh], dx
    mov [ti_pbw], cx
    mov [ti_pbd], di
    call ti_gnd_prep                ; the band's runs, a column each
    push ds                         ; a clean band: off the board is black
    pop es
    cld
    mov ax, cx
    mul dx
    mov cx, ax
    xor al, al
    rep stosb
    mov byte [ti_pmode], 2          ; the ground...
    call ti_pic_pass
    mov byte [ti_pmode], 0          ; ...and the figures over it
    call ti_pic_pass
    pop es
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_pic_stat - the NUMBERS over the band ti_pic_band last composed: each
; byte (byte AND NOT halo) OR digits, out of the stat bank ti_cellnum keeps.
; Preserves every register.
ti_pic_stat:
    mov byte [ti_pmode], 1
    call ti_pic_pass
    ret

; ti_pic_pass - one layer, [ti_pmode]'s - 2 the ground, 0 the figures, 1 the
; numbers - over every run of the band. Preserves every register.
;
; A LAYER IS A FEW RECTANGLES, NOT A ROW LOOP. The first cut asked every row
; which lane it was in and multiplied its way to the source, and a 6 x 24 band
; cost 14 ms of it. A run is one column of the board, so its ground is ONE
; block of the strip and its figures and numbers are at most two blocks of two
; cells: each is sized here, once, and copied with a row loop that holds
; everything in registers.
ti_pic_pass:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    cld
    mov word [ti_prun], 0
    mov word [ti_pj0], 0
.run:
    mov bx, [ti_prun]
    mov ax, bx
    shr ax, 1
    cmp ax, [ti_grk]
    jb .rgo
    jmp .out
.rgo:
    cmp word [ti_grtop + bx], 0FFFFh
    jne .rcol
    jmp .rnext
.rcol:
    cmp byte [ti_pmode], 2
    jne .over
    ; --- THE GROUND: one block of the strip, the rows of it the band holds -
    mov ax, [ti_grtop + bx]         ; ra = max(0, top - y0)
    sub ax, [ti_pby]
    jns .gra
    xor ax, ax
.gra:
    mov [ti_pra], ax
    mov ax, [ti_grtop + bx]         ; rb = min(h, top + SH - y0)
    add ax, [ti_sh]
    sub ax, [ti_pby]
    cmp ax, [ti_pbh]
    jle .grb
    mov ax, [ti_pbh]
.grb:
    sub ax, [ti_pra]
    jg .grows
    jmp .rnext
.grows:
    mov bp, ax                      ; BP = rows
    mov ax, [ti_pby]
    add ax, [ti_pra]
    mul word [ti_sb]
    add ax, [ti_grbase + bx]
    mov si, ax                      ; SI = the strip, at the first of them
    mov ax, [ti_pra]
    mul word [ti_pbw]
    add ax, [ti_pbd]
    add ax, [ti_pj0]
    mov di, ax
    mov ax, [ti_grn + bx]           ; AX = bytes a row
    mov dx, [ti_sb]
    mov bx, [ti_pbw]
    push ds
    pop es
    push ds
    mov ds, [ti_aseg]
.gl:
    push si
    push di
    mov cx, ax
    rep movsb
    pop di
    pop si
    add si, dx
    add di, bx
    dec bp
    jnz .gl
    pop ds
    jmp .rnext

.over:
    ; --- the overlap of this run with the column's figure band or numbers,
    ;     in the column's own bytes: [a, b) against the run's [r0, r0 + n)
    mov ax, [ti_grc + bx]
    mov [ti_pkcol], ax
    mov dx, ax
    call ti_col_insx                ; AX = the figure band's inset
    mov si, [ti_bw]
    cmp byte [ti_pmode], 0
    je .have
    cmp dx, TI_COLS / 2
    jae .p2s
    xor ax, ax                      ; P1's numbers are the column's first
    jmp short .ss                   ; INSX pixels...
.p2s:
    add ax, [ti_bw]                 ; ...P2's the ones past its figure band
.ss:
    mov si, [ti_insx]
.have:
    mov cl, 3
    shr ax, cl                      ; AX = a, in bytes
    shr si, cl
    add si, ax                      ; SI = b
    mov dx, [ti_grlx + bx]
    shr dx, cl                      ; DX = r0
    mov di, dx
    add di, [ti_grn + bx]           ; DI = r0 + n
    mov bp, ax                      ; BP = a, which the source counts from
    cmp ax, dx
    jae .lo
    mov ax, dx                      ; lo = max(a, r0)
.lo:
    cmp si, di
    jbe .hi
    mov si, di                      ; hi = min(b, r0 + n)
.hi:
    cmp ax, si
    jb .some
    jmp .rnext
.some:
    sub si, ax
    mov [ti_pcnt], si
    push ax
    sub ax, bp
    mov [ti_psrc], ax               ; where in the source's row
    pop ax
    sub ax, dx
    add ax, [ti_pj0]
    mov [ti_pdst], ax               ; where in the band's row

    ; --- and the lanes: each cell's block is at most one rectangle ---------
    ; The first lane whose block reaches the band is found with ONE divide:
    ; lane L's block is [YS_L, YS_L + H), YS_L = top + INSY + L x CH, and it
    ; reaches row y0 when L > (y0 - top - INSY - H) / CH. Walking there from
    ; lane 0 cost up to four empty rounds a run, in two passes, per bolt.
    mov cx, [ti_bh]
    cmp byte [ti_pmode], 0
    je .h0
    mov cx, [ti_nh]
.h0:
    mov ax, [ti_pby]
    sub ax, [ti_grtop + bx]
    sub ax, [ti_insy]
    sub ax, cx
    mov word [ti_plane], 0
    js .l0
    xor dx, dx
    div word [ti_ch]
    inc ax
    mov [ti_plane], ax
.l0:
    mov ax, [ti_plane]              ; YS = top + lane x CH + INSY, the block's
    mul word [ti_ch]                ; first row on the screen - then stepped a
    add ax, [ti_grtop + bx]         ; CH at a time
    add ax, [ti_insy]
    mov [ti_pys], ax
.lane:
    cmp word [ti_plane], TI_ROWS
    jb .lgo
    jmp .rnext
.lgo:
    mov ax, [ti_pys]
    mov cx, ax
    sub cx, [ti_pby]
    cmp cx, [ti_pbh]                ; a lane below the band, and so is every
    jl .lin                         ; lane after it
    jmp .rnext
.lin:
    mov cx, [ti_bh]                 ; ...and its height
    cmp byte [ti_pmode], 0
    je .hgt
    mov cx, [ti_nh]
.hgt:
    sub ax, [ti_pby]                ; ra = max(0, YS - y0)
    mov dx, ax
    add dx, cx                      ; rb = min(h, YS + H - y0)
    or ax, ax
    jns .lra
    xor ax, ax
.lra:
    cmp dx, [ti_pbh]
    jle .lrb
    mov dx, [ti_pbh]
.lrb:
    sub dx, ax
    jg .lrows
    jmp .lnext
.lrows:
    mov [ti_pra], ax
    mov bp, dx                      ; BP = rows
    mov ax, [ti_pkcol]              ; BX = the cell
    mov bx, TI_ROWS
    mul bx
    add ax, [ti_plane]
    mov bx, ax
    mov ax, [ti_pby]                ; the block's first row that lands
    add ax, [ti_pra]
    sub ax, [ti_pys]
    mov [ti_psr], ax
    mov ax, [ti_pra]                ; DI = where in the band
    mul word [ti_pbw]
    add ax, [ti_pbd]
    add ax, [ti_pdst]
    mov di, ax
    cmp byte [ti_pmode], 0
    jne .stat
    ; --- a FIGURE: what the cell last showed, copied a row at a time -------
    shl bx, 1
    cmp word [ti_shseg + bx], 0
    jne .fig
    jmp .lnext                      ; never committed: the ground stands
.fig:
    mov ax, [ti_psr]
    mul word [ti_bs]
    add ax, [ti_shoff + bx]
    add ax, [ti_psrc]
    mov si, ax
    mov es, [ti_shseg + bx]
    mov ax, [ti_pcnt]
    mov dx, [ti_bs]
    mov bx, [ti_pbw]
    push ds
    push ds
    push es
    pop ds                          ; DS = the cell's source
    pop es                          ; ES = here, the band
.fl:
    push si
    push di
    mov cx, ax
    rep movsb
    pop di
    pop si
    add si, dx
    add di, bx
    dec bp
    jnz .fl
    pop ds
    jmp .lnext
    ; --- the NUMBERS: (byte AND NOT halo) OR digits ------------------------
.stat:
    cmp byte [ti_stok + bx], 0
    jne .num
    jmp .lnext                      ; none banked: the ground stands
.num:
    mov ax, bx
    mov cx, TI_STATREC
    mul cx
    add ax, TI_STATBANK
    add ax, [ti_psrc]
    mov si, ax
    mov ax, [ti_psr]
    mul word [ti_nbs]
    add si, ax                      ; SI = the halo, SI + TI_CELLBANDMAX the
    mov es, [ti_kseg]               ; digits, in the attack claim
    mov dx, [ti_nbs]
    mov bx, [ti_pbw]
.nl:
    push si
    push di
    mov cx, [ti_pcnt]
.nb:
    mov al, [es:si]
    not al
    and [di], al
    mov al, [es:si + TI_CELLBANDMAX]
    or [di], al
    inc si
    inc di
    loop .nb
    pop di
    pop si
    add si, dx
    add di, bx
    dec bp
    jnz .nl
.lnext:
    mov ax, [ti_ch]
    add [ti_pys], ax
    inc word [ti_plane]
    jmp .lane
.rnext:
    mov bx, [ti_prun]
    mov ax, [ti_grn + bx]
    add [ti_pj0], ax
    add word [ti_prun], 2
    jmp .run
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

; ti_stat_bank - bank cell [ti_ci]'s numbers as ti_stat_compose left them:
; the halo, then the digits, [ti_nh] rows at [ti_nbs] a row. Preserves every
; register.
ti_stat_bank:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    cld
    mov ax, [ti_ci]
    mov bx, TI_STATREC
    mul bx
    add ax, TI_STATBANK
    mov di, ax
    mov es, [ti_kseg]
    mov ax, [ti_nh]
    mul word [ti_nbs]
    mov bx, ax                      ; BX = the bytes in the block
    mov si, ti_stmask
    mov cx, bx
    push di
    rep movsb
    pop di
    add di, TI_CELLBANDMAX
    mov si, ti_cellband
    mov cx, bx
    rep movsb
    mov bx, [ti_ci]
    mov byte [ti_stok + bx], 1
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_shown_set - cell [ti_ci] now shows the band at ES:SI. Preserves every
; register.
ti_shown_set:
    push bx
    mov bx, [ti_ci]
    shl bx, 1
    mov [ti_shoff + bx], si
    mov [ti_shseg + bx], es
    pop bx
    ret

; -----------------------------------------------------------------------------
; ti_stat_compose - a cell's numbers OVER ITS GROUND, with a black halo
; in:  ti_cellband holds the lettered rows ([ti_nbs] bytes by [ti_nh]), the
;      cell's top-left at ([ti_nx], [ti_ny])
; out: ti_cellout holds what to blit. Preserves every register.
;
; THE STAT COLUMN WAS A BLACK BOX, which on a diamond with black corners was
; invisible and on a board with fences through it is a hole every 96 pixels.
; So the ground is read under it, every glyph gets a one-pixel black halo, and
; the fence runs on behind the numbers. The halo is what keeps a digit legible
; over a lit texture on a one-bit screen - the figures carry the same.
; -----------------------------------------------------------------------------
ti_stat_compose:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp

    ; 1. EACH ROW ORed WITH ITS NEIGHBOURS ABOVE AND BELOW, once, so the halo
    ;    below is one read a byte and not three
    mov bp, [ti_nbs]
    mov ax, [ti_nh]
    mul bp
    mov cx, ax                      ; CX = the bytes in the lettered block
    xor bx, bx
.v:
    cmp bx, cx
    jae .vdone
    mov al, [ti_cellband + bx]
    cmp bx, bp
    jb .noup
    mov si, bx
    sub si, bp
    or al, [ti_cellband + si]
.noup:
    mov si, bx
    add si, bp
    cmp si, cx
    jae .nodn
    or al, [ti_cellband + si]
.nodn:
    mov [ti_vbuf + bx], al
    inc bx
    jmp short .v
.vdone:

    ; 2. THE GROUND UNDER IT, straight out of the cell's own column strip: the
    ;    stat column is the cell's first bytes, so it is a strided copy and
    ;    needs none of the general reader
    mov ax, [ti_ci]
    xor dx, dx
    mov cx, TI_ROWS
    div cx                          ; AX = column, DX = row
    push dx
    mul word [ti_spitch]
    add ax, [ti_sbase]
    mov si, ax
    pop ax
    mul word [ti_ch]
    add ax, [ti_insy]
    mul word [ti_sb]
    add si, ax                      ; SI = the strip, at the block's first row
    mov ax, [ti_nstat]              ; ...and its first byte, which on P2's
    shr ax, 1                       ; mirrored cells is past the band
    shr ax, 1
    shr ax, 1
    add si, ax
    mov di, ti_cellout
    mov dx, [ti_sb]
    mov bx, [ti_nh]
    push es
    push ds
    pop es                          ; ES = here, DS = the arena
    push ds
    mov ds, [ti_aseg]
.gr:
    or bx, bx
    jz .grd
    push si
    mov cx, bp
    rep movsb
    pop si
    add si, dx
    dec bx
    jmp short .gr
.grd:
    pop ds
    pop es

    ; 3. PER ROW: the halo punched and the letters put down - a byte at a
    ;    time, the neighbours' edge pixels carried across the byte boundaries
    mov word [ti_nr], 0
.row:
    mov ax, [ti_nr]
    cmp ax, [ti_nh]
    jae .out
    mul word [ti_nbs]
    mov si, ax                      ; SI = this row's offset in every buffer
    mov di, ti_cellout
    add di, si
    xor bx, bx
    xor dl, dl                      ; DL = the byte to the left's v
.b:
    mov al, [ti_vbuf + bx + si]     ; AL = v
    mov ah, al
    mov dh, al
    shl dh, 1
    or ah, dh
    mov dh, al
    shr dh, 1
    or ah, dh                       ; AH = v spread a pixel either way
    mov dh, dl
    and dh, 1
    ror dh, 1
    or ah, dh                       ; ...and the left neighbour's last pixel
    inc bx
    cmp bx, [ti_nbs]
    jae .nn
    mov dh, [ti_vbuf + bx + si]
    and dh, 80h
    rol dh, 1
    or ah, dh                       ; ...and the right neighbour's first
.nn:
    dec bx
    mov dl, al
    mov [ti_stmask + bx + si], ah   ; (the halo, kept for a bolt to go under)
    not ah
    and [di + bx], ah               ; the ground under the halo goes dark...
    mov al, [ti_cellband + bx + si]
    or [di + bx], al                ; ...and the letters go down lit
    inc bx
    cmp bx, [ti_nbs]
    jb .b
    inc word [ti_nr]
    jmp short .row
.out:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_col_insx - AX = the band's inset for column AX, and CF=1 if that column is
; P2's, whose cells are MIRRORED: figure then numbers, the figure facing its
; enemy (SPEC.md 97.4.9). Preserves every other register.
; -----------------------------------------------------------------------------
ti_col_insx:
    cmp ax, TI_COLS / 2
    jae .p2
    mov ax, [ti_insx]
    clc
    ret
.p2:
    mov ax, [ti_insx2]
    stc
    ret

; ti_rev - a byte with its bits the other way round, for `xlat`. A mirrored
; figure is its bytes in reverse order AND each byte reversed, and a table is
; one instruction where a shift loop is sixteen.
ti_rev:
%assign ti_rvb 0
%rep 256
    db ((ti_rvb & 1) << 7) | ((ti_rvb & 2) << 5) | ((ti_rvb & 4) << 3) | ((ti_rvb & 8) << 1) | ((ti_rvb & 16) >> 1) | ((ti_rvb & 32) >> 3) | ((ti_rvb & 64) >> 5) | ((ti_rvb & 128) >> 7)
%assign ti_rvb ti_rvb + 1
%endrep

; --- the state ---------------------------------------------------------------
ti_aseg:    dw 0                  ; the ARENA's segment - the one word the
                                  ; relocation proc updates
ti_fenh:      dw 0                  ; this surface's fence, wall and cliff rows,
ti_wh:      dw 0                  ; and E, what the board grows by under
ti_dd:      dw 0                  ; column 0
ti_ext:     dw 0
ti_sb:      dw 0                  ; a strip's stride, rows and size
ti_sh:      dw 0
ti_spitch:  dw 0
ti_sbase:   dw 0                  ; ...and where the strips start
ti_cslot:   dw 0                  ; one composed pose
ti_sp:      dw 0                  ; the strip being composed
ti_sc:      dw 0
ti_sx:      dw 0
ti_sy:      dw 0
ti_sr:      dw 0
ti_tex:     dw 0
ti_fence:   dw 0
ti_lx:      dw 0
ti_y0:      dw 0
ti_gapw:    dw 0
ti_gapf:    dw 0
ti_gapl:    dw 0
ti_pcol:    dw 0
ti_pbyte:   dw 0
ti_pbit:    db 0
ti_gsrc:    dw 0
ti_fa_dx:   dw 0
ti_fa_dy:   dw 0
ti_fa_stride: dw 0
ti_fa_wb:   dw 0
ti_fa_h:    dw 0
ti_fa_x0:   dw 0
ti_fa_n:    dw 0
ti_fa_lo:   dw 0
ti_fa_hi:   dw 0
ti_kseg:    dw 0                  ; the ATTACK frames' claim
ti_fseg:    dw 0                  ; the hand's portraits (SPEC.md 97.4.12)
ti_pseg:    dw 0                  ; the art part, as op_seg last answered
ti_cst:     dw 0                  ; the stance: TI_ROW_FRONT or TI_ROW_REAR
ti_cfr:     dw 0                  ; the frame: 0-3 idle, 4-7 attack
ti_csurf:   dw 0                  ; the surface a record is read for
ti_cbh:     dw 0                  ; ...and the band height it stands for
ti_cdx:     dw 0                  ; a whole character's shift, bytes
ti_cdy:     dw 0                  ; ...and rows
ti_cyy:     dw 0
ti_cax:     dw 0                  ; the body's anchor for this pose
ti_cay:     dw 0
ti_cbody:   dw 0
ti_citem:   dw 0
ti_csame:   dw 0                  ; this cell's row of the same-as table
ti_figbuf:  times TI_P_FIGMAX db 0
ti_fa_mir:  db 0                  ; ...and 1 to put it down MIRRORED
ti_nstat:   dw 0                  ; the stat column's x in its cell
ti_insx2:   dw 0                  ; P2's band inset: CW - INSX - BW
ti_cfbeg:   dw 0                  ; ti_cell_build's range of frames
ti_cfend:   dw 2 * TI_POSES
ti_grk:     dw 0                  ; the ground reader's runs: how many,
ti_nr:      dw 0
ti_grtop:   times 8 dw 0          ; ...each one's strip top on the screen
ti_grbase:  times 8 dw 0          ; ...its first byte less top x SB
ti_grn:     times 8 dw 0          ; ...and its length in bytes
ti_grc:     times 8 dw 0          ; ...its column, or 0FFFFh off the board
ti_grlx:    times 8 dw 0          ; ...and its first byte's x inside it
ti_shseg:   times TI_CELLS dw 0   ; WHAT EACH CELL SHOWS: the band ti_feature
ti_shoff:   times TI_CELLS dw 0   ; (or a reveal) last put on the glass there
ti_stok:    times TI_CELLS db 0   ; ...and whether its numbers are banked
ti_pbx:     dw 0                  ; ti_pic_band's band: x, first row, rows,
ti_pby:     dw 0                  ; stride, where it is
ti_pbh:     dw 0
ti_pbw:     dw 0
ti_pbd:     dw 0
ti_pmode:   db 0                  ; 0 the figures, 1 the numbers
ti_pcnt:    dw 0                  ; ...and a run's overlap: bytes, where in
ti_pdst:    dw 0                  ; the band, where in the source, the lane
ti_psrc:    dw 0                  ; and the row inside it
ti_plane:   dw 0
ti_pra:     dw 0
ti_pys:     dw 0
ti_psr:     dw 0
ti_pkcol:   dw 0
ti_prun:    dw 0
ti_pj0:     dw 0
ti_vbuf:    times 6 * 40 db 0      ; the letters, ORed a row up and down
ti_yoff:    times 128 db 0        ; the slope, a byte a pixel column
