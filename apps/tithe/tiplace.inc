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
;   THE READER   `ti_gnd_prep` / `ti_gnd_row`: any row of the board's ground,
;                at any 8-aligned x, for the three things composed against it
;                at run time - a projectile, a tier-B clash and a cell's
;                numbers.
;
; WHY A HEAP CLAIM. The poses used to be three - one per character, composed
; once over one tile every cell shared - and lived in the package's own bss.
; A column's texture is not its neighbour's, so a figure composed over its
; column's ground stands in that column only, and the poses are per CELL now:
; 80 of them, 30,720 bytes on a fullscreen VGA, with the strips another 14,400.
; That is not a segment's worth of bss; it is TITHE-PLAN 1.5's "composed idle
; sprites" line arriving, and it is where the final game keeps them anyway.
; =============================================================================

TI_ARENAKB  equ 45                ; 30,720 of poses + 14,400 of strips on the
                                  ; biggest surface, and ti_place_lay refuses
                                  ; a layout that would not fit rather than
                                  ; trusting this arithmetic
TI_GBMAX    equ 32                ; bytes a ground READ may span: a tier-B
                                  ; clash is two cells, 26 at the widest

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
    clc                             ; [ti_aseg] - so the proc is one store. A
.out:                               ; refusal leaves it pinned, which is legal
    pop dx
    pop ax
    ret

; the relocation proc (OSAPI_MEM_MOVABLE): BX = where it was, DX = where it is
ti_arena_move:
    mov [ti_aseg], dx
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
; ti_cells_build - every cell's four poses: its ground, then its figure
; Preserves every register.
; -----------------------------------------------------------------------------
ti_cells_build:
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
    push word [ti_ci]
    push word [ti_pi]
    mov word [ti_ci], 0
.cell:
    cmp word [ti_ci], TI_CELLS
    jae .done
    mov ax, [ti_ci]
    call ti_ck_cell                 ; [ti_ck] = who stands here
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
    mov bx, [ti_insx]
    shr bx, 1
    shr bx, 1
    shr bx, 1
    add ax, bx
    mov [ti_gsrc], ax               ; the band's first ground byte
    mov word [ti_pi], 0
    call ti_cellpose_addr           ; DI = pose 0's slot
    push di
    mov si, [ti_gsrc]               ; --- the ground, row by row, out of the
    mov bx, [ti_sb]                 ;     strip and into pose 0's slot...
    mov dx, [ti_bs]
    mov bp, [ti_bh]
    push ds
    mov ax, es
    mov ds, ax
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
    pop si                          ; ...and REPLICATED into the other three:
    mov di, si                      ; DI trails SI by exactly one slot, so a
    add di, [ti_cslot]              ; forward copy of three slots' worth
    mov ax, [ti_cslot]              ; carries slot 0 into 1, 1 into 2 and 2
    mov cx, TI_POSES - 1            ; into 3. A slot is BS x BH, and BS is a
    mul cx                          ; whole number of bytes, so it is even
    mov cx, ax
    shr cx, 1
    push ds
    mov ax, es
    mov ds, ax
    rep movsw
    pop ds
.pose:
    cmp word [ti_pi], TI_POSES
    jae .cnext
    call ti_cellpose_addr           ; DI = this pose's slot
    call ti_fig_board               ; ...and its figure, MASKED over it
    inc word [ti_pi]
    jmp short .pose
.cnext:
    inc word [ti_ci]
    jmp .cell
.done:
    pop word [ti_pi]
    pop word [ti_ci]
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
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

; ti_crec_at - SI = the art record of character [ti_ck] at surface AX (0..7)
; Preserves every register bar SI.
ti_crec_at:
    push ax
    push bx
    push dx
    mov bx, ax
    mov ax, [ti_ck]
    mov dx, TI_CHAR_G
    mul dx
    add ax, bx
    shl ax, 1
    mov si, ax
    mov si, [ti_char_tab + si]
    pop dx
    pop bx
    pop ax
    ret

; ti_dirty_rows - AL = the first row, AH = how many, that the move INTO pose
; [ti_pi] of character [ti_ck] touches (SPEC.md 97.4.3). The TOOL's rows, cut
; from the figures alone, so they hold over whatever ground a cell composed.
; Preserves every register bar AX.
ti_dirty_rows:
    push bx
    push si
    mov ax, [ti_gidx]
    call ti_crec_at
    mov bx, [ti_pi]
    shl bx, 1
    mov ax, [bx + si + TI_CR_D]
    pop si
    pop bx
    ret

; -----------------------------------------------------------------------------
; ti_fig_board - pose [ti_pi] of character [ti_ck], MASKED into the band at
; ES:DI. Preserves every register.
;
; THE SPRITE-SIZE ARM (SPEC.md 97.7's `S`) is a CROP now and not a scale: the
; art is drawn for the table's band, so a smaller arm keeps its floor and its
; centre and loses what falls outside - which is still an honest answer to
; "what does a shorter band cost", and the only one a drawing can give.
; -----------------------------------------------------------------------------
ti_fig_board:
    push ax
    push bx
    push cx
    push dx
    push si
    push bp
    mov ax, [ti_gidx]
    call ti_crec_at
    mov bx, [ti_pi]
    mov al, [si + TI_CR_Y + bx]
    xor ah, ah
    mov cx, ax                      ; CX = the figure's band row
    shl bx, 1
    mov si, [si + bx]               ; SI = the figure
    mov bx, [ti_geo]                ; ...less what a smaller arm cut off the
    mov ax, [bx + TI_G_BH]          ; top: the floor is where it stands
    sub ax, [ti_bh]
    sub cx, ax
    mov [ti_fa_dy], cx
    mov ax, [ti_bwfull]
    sub ax, [ti_bw]
    shr ax, 1
    shr ax, 1
    shr ax, 1
    shr ax, 1
    neg ax
    mov [ti_fa_dx], ax
    mov ax, [ti_bs]
    mov [ti_fa_stride], ax
    mov [ti_fa_wb], ax
    mov ax, [ti_bh]
    mov [ti_fa_h], ax
    mov byte [ti_fa_or], 0
    call ti_fig_apply
    pop bp
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_fig_apply - put figure SI into the band at ES:DI
; in:  [ti_fa_dx] bytes and [ti_fa_dy] rows to shift it by (signed),
;      [ti_fa_stride], [ti_fa_wb] bytes and [ti_fa_h] rows the band has,
;      [ti_fa_or] = 1 to OR the INK alone (a figure on a black card, where the
;      mask has nothing to punch), 0 to MASK it
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
    mov al, [si]                    ; the figure's first byte column, moved
    xor ah, ah
    add ax, [ti_fa_dx]
    mov [ti_fa_x0], ax
    mov al, [si + 1]
    xor ah, ah
    mov [ti_fa_n], ax               ; bytes a row
    mov al, [si + 2]
    xor ah, ah
    mov bp, ax                      ; rows
    add si, 3

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
    cmp byte [ti_fa_or], 0
    jne .orb
.mb:                                ; ONE READ AND ONE WRITE a byte: the band
    lodsw                           ; byte is fetched into a register, masked
    not ah                          ; and inked there, and stored with stosb -
    and ah, [es:di]                 ; half the bus traffic of two read-modify-
    or al, ah                       ; writes on memory, which is the whole of
    stosb                           ; the cost on an 8088
    loop .mb
    jmp short .rdone
.orb:
    lodsw
    or al, [es:di]
    stosb
    loop .orb
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
; ti_gnd_prep - get ready to read the ground under CX bytes from screen x AX
; ti_gnd_row  - ...and read row BX of it (a screen y) into DI
; Both preserve every register.
;
; WHAT A RUN-TIME COMPOSITION STANDS ON. A projectile crosses cells it does
; not own, a tier-B clash spans two columns and a cell's numbers sit in the
; stat column - and none of those grounds is one tile any more. So the ground
; is read out of the strips: `prep` resolves each byte's column and strip ONCE
; for a band, and a row is then one multiply and a load a byte, which is what
; the old read modulo one shared tile cost too.
; -----------------------------------------------------------------------------
ti_gnd_prep:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    cmp cx, TI_GBMAX
    jbe .n
    mov cx, TI_GBMAX
.n:
    mov [ti_gbn], cx
    xor si, si                      ; SI indexes WORDS
    mov di, cx                      ; DI = bytes still to resolve
.b:
    or di, di
    jz .out
    push ax
    mov word [ti_gbtop + si], 0FFFFh
    sub ax, [ti_bx]
    jb .off
    cmp ax, [ti_boardw]
    jae .off
    xor dx, dx
    div word [ti_cw]                ; AX = column, DX = x inside it
    shr dx, 1
    shr dx, 1
    shr dx, 1
    mov bx, dx                      ; BX = the byte inside the column
    push ax
    mul word [ti_spitch]
    add ax, [ti_sbase]
    add bx, ax                      ; BX = that byte of the strip's row 0
    pop ax
    mov cx, TI_COLS - 1
    sub cx, ax
    mov ax, cx
    mul word [ti_rise]
    add ax, [ti_by]                 ; AX = the strip's top on the screen
    mov [ti_gbtop + si], ax
    mul word [ti_sb]
    sub bx, ax                      ; ...so screen row y is BX + y * SB
    mov [ti_gbbase + si], bx
.off:
    pop ax
    add ax, 8
    add si, 2
    dec di
    jmp short .b
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

ti_gnd_row:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov es, [ti_aseg]
    mov ax, bx
    mul word [ti_sb]
    mov dx, ax                      ; DX = y * SB, for every byte
    xor si, si
    mov cx, [ti_gbn]
.b:
    jcxz .out
    mov ax, [ti_gbtop + si]
    cmp ax, 0FFFFh
    je .zero
    neg ax
    add ax, bx                      ; AX = the strip row
    js .zero
    cmp ax, [ti_sh]
    jae .zero
    push bx
    mov bx, [ti_gbbase + si]
    add bx, dx
    mov al, [es:bx]
    pop bx
    jmp short .put
.zero:
    xor al, al
.put:
    mov [di], al
    inc di
    add si, 2
    dec cx
    jmp short .b
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
ti_fa_or:   db 0
ti_gbn:     dw 0
ti_nr:      dw 0
ti_ushift:  dw 0                  ; rows a unit's art is cut above its band
ti_gbtop:   times TI_GBMAX dw 0
ti_gbbase:  times TI_GBMAX dw 0
ti_vbuf:    times 6 * 40 db 0      ; the letters, ORed a row up and down
ti_yoff:    times 128 db 0        ; the slope, a byte a pixel column
