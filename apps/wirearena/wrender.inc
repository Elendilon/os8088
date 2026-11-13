; WireArena's renderer (docs/plans/MULTIPLAYER-FPS-PLAN.md sections 4, 16).
;
; 1. The arena's walls are one-sided segments in a host-built BSP
;    (tools/arenagen.py), walked FRONT TO BACK: the near side of a node, its
;    own segments, the far side. A segment facing away is dropped by one
;    compare; one facing us has its two vertices transformed (two 32-bit adds
;    each, off per-coordinate products made once a frame - the walls are
;    axis-aligned) and projected (cached per vertex), is clipped only when a
;    vertex is outside the view, and is then STEPPED across its columns.
; 2. A column a nearer wall already drew is CLOSED (wa_cov): a wall is full
;    height, so nothing behind it can show there. An open column is drawn on
;    the spot - its inverse depth into wa_colz for the figures, the top and
;    bottom edge glyphs at half-row precision (`─` upper half, `_` lower),
;    `/` or `\` where an edge steps two half-rows or more, `│` at a segment's
;    real corners - and closed. The walk stops when no column is open.
; 3. Figures, far to near, as limb lines at 2x2 SUB-CELL precision, each
;    sub-pixel depth-tested against its column's wall; a cell's four bits
;    pick a solid block glyph. A figure cell replaces a wall cell.
; 4. The crosshair.
; Every cell drawn this frame is stamped and listed; wa_present writes the
; ones that differ from what the glass holds and blanks last frame's cells
; nobody drew this time. Nothing else is touched, so a still view costs no
; video writes at all.
;
; Wave 0's first renderer rasterised every face into a per-column depth
; buffer and drew edges from it in a second pass: 13.0 fps at 80 columns on
; the bench. This one does both in one pass, over the visible walls only.

WA_MAXSP equ 96                 ; spans a frame the table holds
%macro WR_BSS 0
WA_VAR wa_colz, WA_MAXW*2       ; nearest face's inverse depth (0 = none)
WA_VAR wa_colt, WA_MAXW*2       ; its top, quarter half-rows
WA_VAR wa_colb, WA_MAXW*2       ; its bottom
WA_VAR wa_covpad, 2             ; (0: what column -1 reads in a steep test)
WA_VAR wa_cov, WA_MAXW*2        ; the tag of the span that drew a column
WA_VAR wa_tag, 2                ; this frame's last span tag (x 2)
WA_VAR wa_spcs, WA_MAXSP*2      ; per span: c1 (x16), inverse depth there,
WA_VAR wa_spih, WA_MAXSP*2      ; c2 - c1 and i2 - i1: wa_wallz's line
WA_VAR wa_spsh, WA_MAXSP*2
WA_VAR wa_spsl, WA_MAXSP*2
WA_VAR wa_wcol, 1               ; the colour of the walls being drawn
WA_VAR wa_pt32, WA_MAXW*2       ; per column, the held top and bottom
WA_VAR wa_pb32, WA_MAXW*2       ; half-rows (wa_hyst)
WA_VAR wa_dxc, 9*4              ; the floor grid's products (wa_dots)
WA_VAR wa_dxs, 9*4
WA_VAR wa_dyc, 9*4
WA_VAR wa_dys, 9*4
WA_VAR wa_dnx, 2
WA_VAR wa_diz, 2
WA_VAR wa_dny, 2
WA_VAR wa_dix, 2
WA_VAR wa_diy, 2
WA_VAR wa_vt0, 2
WA_VAR wa_stl, 2
WA_VAR wa_sbl, 2
WA_VAR wa_vbl, 2
WA_VAR wa_vb0, 2
WA_VAR wa_afix, 1               ; the span's shade is one band
WA_VAR wa_left, 2               ; columns still open
WA_VAR wa_lp, 2                 ; the list's write pointer across spans
WA_VAR wa_xc, WA_MXV*4          ; per frame: (x - px) cos and sin, 32 bits,
WA_VAR wa_xs, WA_MXV*4          ; one per distinct x of the arena...
WA_VAR wa_yc, WA_MYV*4          ; ...and per distinct y: a vertex is two
WA_VAR wa_ys, WA_MYV*4          ; 32-bit adds, not four multiplies
WA_VAR wa_vst, WA_MVTX*2        ; a vertex's cache stamp (the frame number)
WA_VAR wa_vok, WA_MVTX*2        ; 1: inside the view, projected below
WA_VAR wa_vx, WA_MVTX*2         ; camera space
WA_VAR wa_vz, WA_MVTX*2
WA_VAR wa_vpc, WA_MVTX*2        ; projected: column x16, top, bottom,
WA_VAR wa_vpt, WA_MVTX*2        ; inverse depth
WA_VAR wa_vpb, WA_MVTX*2
WA_VAR wa_vpi, WA_MVTX*2
WA_VAR wa_fv, 2
WA_VAR wa_bvis, 1
WA_VAR wa_endok, 1
WA_VAR wa_mbot, 2
WA_VAR wa_e1, 1                 ; this span's ends are REAL corners (not
WA_VAR wa_e2, 1                 ; cut by the frustum): a vertical edge each
WA_VAR wa_pdrawn, 1             ; the last column of this span was drawn
WA_VAR wa_cs0, 2
WA_VAR wa_steep, 1              ; the span's edges can step >= 2 half-rows
WA_VAR wa_cht, WA_MAXW*2        ; an opened column's edges, half-rows
WA_VAR wa_chb, WA_MAXW*2
WA_VAR wa_crow, 2               ; this box's corner row (wa_corn)
WA_VAR wa_ce0, 2
WA_VAR wa_at, 6                 ; this frame's attributes (A_*)
WA_VAR wa_cos, 2
WA_VAR wa_sinv, 2
WA_VAR wa_cang, 2
WA_VAR wa_hq, 2                 ; horizon, quarter half-rows
WA_VAR wa_hh, 2                 ; horizon, half-rows
WA_VAR wa_numt, 2
WA_VAR wa_numb, 2
WA_VAR wa_x1, 2
WA_VAR wa_z1, 2
WA_VAR wa_x2, 2
WA_VAR wa_z2, 2
WA_VAR wa_d1, 2
WA_VAR wa_d2, 2
WA_VAR wa_c1, 2
WA_VAR wa_t1, 2
WA_VAR wa_b1, 2
WA_VAR wa_i1, 2
WA_VAR wa_c2, 2
WA_VAR wa_t2, 2
WA_VAR wa_b2, 2
WA_VAR wa_i2, 2
WA_VAR wa_pht, 2
WA_VAR wa_phb, 2
WA_VAR wa_eatt, 1               ; the edge glyphs' attribute this column
WA_VAR wa_ht, 2
WA_VAR wa_hroff, WA_HR*2         ; a half-row's cell row offset
WA_VAR wa_hb, 2
WA_VAR wa_cs, 2
WA_VAR wa_end, 2                ; the span loop's end, column x 2
WA_VAR wa_ncl, 2                ; ...and the columns it found shut
WA_VAR wa_fs, 2
WA_VAR wa_dc, 2
WA_VAR wa_st, 2
WA_VAR wa_sb, 2
WA_VAR wa_slo, 2
WA_VAR wa_shi, 2
WA_VAR wa_vb, 2
WA_VAR wa_vil, 2
WA_VAR wa_vih, 2
WA_VAR wa_fiz, 2                ; the figure being drawn: inverse depth
WA_VAR wa_fatt, 1               ;   its attribute
WA_VAR wa_fsub, 1               ;   keyframe blend, quarters
WA_VAR wa_fs8, 2                ;   sub-columns a unit, 8.8
WA_VAR wa_fv8, 2                ;   half-rows a unit, 8.8
WA_VAR wa_fcx, 2                ;   its centre, camera x
WA_VAR wa_pa, 2                 ;   keyframe pointers
WA_VAR wa_pb, 2
WA_VAR wa_jsx, WA_NJ*2
WA_VAR wa_jsy, WA_NJ*2
WA_VAR wa_fxs, WA_NFIG*2        ; camera x and z per figure this frame
WA_VAR wa_fzs, WA_NFIG*2
WA_VAR wa_ford, WA_NFIG*2       ; those in view, far to near (x 2)
WA_VAR wa_frec, WA_NFIG*2       ; ...and each one's record
WA_VAR wa_lx1, 2
WA_VAR wa_ly1, 2
WA_VAR wa_ldx, 2
WA_VAR wa_ldy, 2
WA_VAR wa_lsx, 2
WA_VAR wa_lsy, 2
WA_VAR wa_fbw, 2                ; wa_figure's box: width in cells,
WA_VAR wa_fbc, 2                ;   left column x 2, last row x 2
WA_VAR wa_fbr, 2
WA_VAR wa_frow, 2
WA_VAR wa_fnr, 2                ;   rows left to sweep
WA_VAR wa_flp, 2                ;   the cell list's end, while sweeping
WA_VAR wa_flfn, 2               ;   wa_fline or wa_flinef
WA_VAR wa_fon, 1                ;   1: every joint on the screen
WA_VAR wa_fk, 2                 ; wa_fjl's narrow sums: Klo (fcx fs8 + 256 W),
WA_VAR wa_fe, 2                 ;   eye fv8 + 256 hh + 255
WA_VAR wa_fbuf, WA_CELLS*2      ; a figure's sub-pixels by cell offset (0
                                ; between figures: wa_figure clears its own)
WA_VAR wa_nwr, 2                ; video writes this frame
WA_VAR wa_rcp, (WA_ZMAX-WA_NEAR)*2 ; 0x7FFF0 / z, z = NEAR.. (wa_ptbi)
WA_VAR wa_xk, WA_MXV+1          ; per coordinate: the step from the one
WA_VAR wa_yk, WA_MYV+1          ; before, as a slot x 8 (wa_products)
WA_VAR wa_nk, 2                 ; the last slot used, x 8
WA_VAR wa_sel, 6                ; the cone test's bounds bytes (wa_products)
WA_VAR wa_kv, (WA_MAXKS+1)*8    ; per slot: the step x 4...
WA_VAR wa_mk, (WA_MAXKS+1)*8    ; ...and its products, cos and sin, 32 bits
%endmacro

; --- the frame --------------------------------------------------------------
wa_render:
    push ds
    pop es
    inc byte [wa_frame]         ; 1..127: bit 7 of a stamp marks a FIGURE
    jns .stamped                ; cell, so a wall cell needs no mask store
    mov di, wa_stamp            ; the stamp lapped: start them again
    xor ax, ax
    mov cx, WA_CELLS
    rep stosw
    mov di, wa_vst              ; ...and the vertex cache's with them
    mov cx, WA_MVTX
    rep stosw
    mov byte [wa_frame], 1
.stamped:
    mov word [wa_newn], 0
    mov ax, [wa_newp]
    mov [wa_lp], ax
    mov si, wa_attrc
    cmp byte [wa_mono], 0
    je .attr
    mov si, wa_attrm
.attr:
    mov di, wa_at
    movsw
    movsw
    movsw
    mov ax, [wa_ang]
    mov cl, 6
    shr ax, cl
    mov [wa_cang], ax
    call wa_sincos
    mov [wa_sinv], ax
    mov [wa_cos], dx
    mov ax, [wa_pitch]
    add ax, WA_HR*2
    mov [wa_hq], ax
    add ax, 2
    sar ax, 1
    sar ax, 1
    mov [wa_hh], ax
    mov ax, WA_HTOP
    sub ax, [wa_eye]
    mov cx, [wa_kyq]            ; (the field of view's vertical scale)
    imul cx
    mov [wa_numt], ax
    mov ax, [wa_eye]
    imul cx
    mov [wa_numb], ax
    mov di, wa_colz             ; wall depth: not yet asked (wa_wallz)
    mov ax, 0xFFFF
    mov cx, [wa_w]
    rep stosw
    mov di, wa_cov
    xor ax, ax
    mov [wa_tag], ax
    mov cx, [wa_w]
    mov [wa_left], cx
    rep stosw
    call wa_products
    mov bx, [wa_root]
    call wa_node
    cmp word [wa_left], 0       ; the room, last: it encloses everything
    je .roomless
    mov word [wa_crow], wa_corn
    mov al, [wa_bcol]           ; the room's colour
    xor ah, ah
    mov si, ax
    mov al, [wa_at+si]
    mov [wa_wcol], al
    mov byte [wa_endok], 0      ; (each room corner is some face's START)
    mov ax, (6 << 8) | 0        ; its faces run the other way: c0->c3,
    call wa_face                ; c3->c2, c2->c1, c1->c0 (vertex x 2)
    mov ax, (4 << 8) | 6
    call wa_face
    mov ax, (2 << 8) | 4
    call wa_face
    mov ax, (0 << 8) | 2
    call wa_face
.roomless:
    call wa_dots
    mov ax, [wa_lp]
    sub ax, [wa_newp]
    mov [wa_newn], ax
    call wa_figures
    call wa_cross
    ret

; wa_geominit - once an arena is loaded (wa_main): the reciprocal table
; wa_ptbi reads in place of a divide, and each axis's coordinate steps for
; wa_products. ~2,900 divides, about a tenth of a second on the XT.
wa_geominit:
    push ds
    pop es
    mov di, wa_rcp              ; 0x7FFF0 / z for every z a point can have:
    mov bx, WA_NEAR             ; exactly what the divide gave
.r:
    mov ax, 0xFFF0
    mov dx, 0x0007
    div bx
    stosw
    inc bx
    cmp bx, WA_ZMAX
    jb .r
    mov word [wa_nk], 0
    mov si, wa_xv
    mov di, wa_xk
    mov cx, [wa_nxv2]
    call .steps
    mov si, wa_yv
    mov di, wa_yk
    mov cx, [wa_nyv2]
.steps:                         ; SI = values, CX = their count x 2, DI = the
    shr cx, 1                   ; axis's steps: per value after the first,
    dec cx                      ; its step's slot x 8 (from 8), then 0
.s:
    inc di
    mov ax, [si+2]
    sub ax, [si]
    shl ax, 1
    shl ax, 1                   ; the step x 4
    mov bx, 8
.f:
    cmp bx, [wa_nk]
    ja .new
    cmp ax, [wa_kv+bx]
    je .have
    add bx, 8
    jmp .f
.new:
    mov [wa_kv+bx], ax          ; (arenagen refuses more than WA_MAXKS)
    mov [wa_nk], bx
.have:
    mov [di], bl
    inc si
    inc si
    loop .s
    mov byte [di+1], 0
    ret

; WA_AXIS values, the player's coordinate, steps, cos products, sin products
%macro WA_AXIS 5
    mov ax, [%1]
    sub ax, [%2]
    shl ax, 1
    shl ax, 1
    mov bx, ax
    imul word [wa_sinv]
    mov bp, ax
    mov cx, dx
    mov ax, bx
    imul word [wa_cos]          ; DX:AX, CX:BP = the first value's products
    mov di, %4
    mov si, %3
    xor bx, bx
    jmp %%put
%%next:
    add ax, [wa_mk+bx]          ; ...and each after it, the step's added
    adc dx, [wa_mk+bx+2]
    add bp, [wa_mk+bx+4]
    adc cx, [wa_mk+bx+6]
%%put:
    mov [di], ax
    mov [di+2], dx
    mov [di+%5-%4], bp
    mov [di+%5-%4+2], cx
    add di, 4
    inc si
    mov bl, [si]
    or bl, bl
    jnz %%next
%endmacro

; wa_products - per distinct coordinate, (v - p) x 4 cos and (v - p) x 4 sin:
; x 4 so a vertex's camera z and x are the HIGH words of two 32-bit sums,
; with no shifts (wa_vert). All of them, every frame: doing it lazily per
; coordinate was measured SLOWER (19.5 -> 19.0 fps at 40 columns) - nearly
; every coordinate is used, so the stamp tests were pure cost. But not by a
; multiply each: the first value of an axis is multiplied, and each after it
; is the one before plus the products of the STEP between them - an arena
; has few distinct steps (wa_geominit, at most WA_MAXKS), multiplied here
; once a frame. 12 multiplies in the full arena, where there were 52; the
; sums are exact, so every product is the same bits as before
wa_products:
    mov si, 8                   ; the steps: slot x 8, from 8
.k:
    cmp si, [wa_nk]
    ja .kd
    mov ax, [wa_kv+si]          ; the step x 4
    imul word [wa_cos]
    mov [wa_mk+si], ax
    mov [wa_mk+si+2], dx
    mov ax, [wa_kv+si]
    imul word [wa_sinv]
    mov [wa_mk+si+4], ax
    mov [wa_mk+si+6], dx
    add si, 8
    jmp .k
.kd:
    WA_AXIS wa_xv, wa_px, wa_xk, wa_xc, wa_xs
    WA_AXIS wa_yv, wa_py, wa_yk, wa_yc, wa_ys
    mov cx, [wa_sinv]           ; the cone test's corners (wa_node): which end
    mov dx, [wa_cos]            ; of a node's bounds is the extreme of each
    mov ax, (9 << 8) | 10       ; sum - the sums are linear in the coordinate
    cmp cx, dx
    jl .p
    mov ax, (11 << 8) | 8
.p:
    mov [wa_sel], al            ; right: min x - z over x...
    mov [wa_sel+3], ah          ; left: max x + z over y
    mov ax, (8 << 8) | 9
    mov bx, cx
    add bx, dx
    js .q
    mov ax, (10 << 8) | 11
.q:
    mov [wa_sel+1], al          ; right: ...and max over y
    mov [wa_sel+2], ah          ; left: max over x
    mov al, 8
    or dx, dx
    js .c
    mov al, 10
.c:
    mov [wa_sel+4], al          ; behind: max z over x...
    mov al, 9
    or cx, cx
    js .s
    mov al, 11
.s:
    mov [wa_sel+5], al          ; ...and over y
    ret

; wa_node - BX = a node of the box tree (0 = none): front to back, while any
; column is open. A leaf is one box.
wa_node:
    or bx, bx
    jz .out
    cmp word [wa_left], 0
    je .out
    ; THE VIEW CONE: a node whose bounds lie wholly right of x = z, left of
    ; x = -z or behind the near plane holds nothing that could reach the
    ; screen (90 degrees, the widest view), so neither do its boxes. Each is
    ; a sum of the products' high words (wa_products) at the bounds' extreme
    ; corner (wa_sel); the margins cover the four truncated words, so a node
    ; is dropped only when the exact walk would have drawn none of it.
    ; (Storing the per-coordinate sums with the products measured slower:
    ; most coordinates' are never read)
    mov si, wa_sel
    xor ah, ah
    lodsb
    xlatb
    mov di, ax
    mov dx, [wa_xs+di+2]        ; x - z = (Xs - Xc) - (Yc + Ys) > 1
    sub dx, [wa_xc+di+2]
    lodsb
    xlatb
    mov di, ax
    sub dx, [wa_yc+di+2]
    sub dx, [wa_ys+di+2]
    cmp dx, 4
    jge .out
    lodsb
    xlatb
    mov di, ax
    mov dx, [wa_xs+di+2]        ; x + z = (Xs + Xc) + (Ys - Yc) < -1
    add dx, [wa_xc+di+2]
    lodsb
    xlatb
    mov di, ax
    add dx, [wa_ys+di+2]
    sub dx, [wa_yc+di+2]
    cmp dx, -5
    jle .out
    lodsb
    xlatb
    mov di, ax
    mov dx, [wa_xc+di+2]        ; z = Xc + Ys < NEAR
    lodsb
    xlatb
    mov di, ax
    add dx, [wa_ys+di+2]
    cmp dx, WA_NEAR-2
    jle .out
    mov al, [bx]
    cmp al, 2
    je .leaf
    mov si, [bx+4]              ; near = low, far = high...
    mov di, [bx+6]
    mov cx, [wa_px]
    or al, al
    jz .axis
    mov cx, [wa_py]
.axis:
    cmp cx, [bx+2]
    jl .order
    xchg si, di                 ; ...or the other way about
.order:
    push di
    mov bx, si
    call wa_node
    pop bx
    jmp wa_node                 ; (a tail call: the far side)
.leaf:
    mov al, [bx+1]              ; box x 8
    xor ah, ah
    mov si, ax
    mov cl, 3
    shr si, cl
    mov al, [wa_bcol+si+1]      ; its colour (the room's is first)
    mov si, ax
    mov al, [wa_at+si]
    mov [wa_wcol], al
    mov al, [bx+1]
    mov si, ax
    add si, wa_boxes
    shr ax, 1
    add ax, wa_corn+4           ; (the room's row is first)
    mov [wa_crow], ax
    jmp wa_box
.out:
    ret

; wa_box - SI = a box (x0, y0, x1, y1), [wa_crow] its corners: the faces
; the player is outside of - at most two, out of wa_boxf
wa_box:
    xor bx, bx                  ; BX = the faces we see, x 8: S 8, E 16,
    mov ax, [wa_py]             ; N 32, W 64
    cmp ax, [si+2]
    jge .s1
    mov bl, 8
    jmp .ew
.s1:
    cmp ax, [si+6]
    jle .ew
    mov bl, 32
.ew:
    mov ax, [wa_px]
    cmp ax, [si+4]
    jle .w1
    or bl, 16
    jmp .go
.w1:
    cmp ax, [si]
    jge .go
    or bl, 64
.go:
    add bx, wa_boxf
    push bx
    call .face
    pop bx
    add bx, 4
.face:                          ; BX = a slot: from, to (corners), endok
    mov al, [bx+2]              ; (0xFF: no face)
    or al, al
    js .out
    mov [wa_endok], al
    mov ax, [bx]
    mov bx, [wa_crow]           ; corner numbers -> vertex x 2
    xlatb
    xchg al, ah
    xlatb
    xchg al, ah
    jmp wa_face
.out:
    ret

; wa_boxf - per set of faces seen (S 1, E 2, N 4, W 8), two slots, in the
; order S E N W: the face's corners and whether its END corner is drawn -
; only when the next face round is NOT seen, since a corner two faces share
; is the second one's START, and drawing both put `││` there
wa_boxf:
%assign wbf_m 0
%rep 16
 %assign wbf_n 0
 %assign wbf_f 0
 %rep 4
  %if ((wbf_m >> wbf_f) & 1) && wbf_n < 2
   %assign wbf_g (wbf_f + 1) & 3
    db wbf_f, wbf_g, ((wbf_m >> wbf_g) & 1) ^ 1, 0
   %assign wbf_n wbf_n + 1
  %endif
  %assign wbf_f wbf_f + 1
 %endrep
 %rep 2 - wbf_n
    db 0, 0, 0xFF, 0
 %endrep
 %assign wbf_m wbf_m + 1
%endrep

; wa_face - AL = from vertex x 2, AH = to vertex x 2 (a face we see the front
; of): transform, and unless every column it could reach is already closed,
; project (clipping only when a vertex is outside the view) and step it.
; A vertex's column is made with its transform (wa_vert); its top, bottom
; and inverse depth only here, past the occlusion test, once a frame - a
; face wholly behind nearer walls never pays for them.
wa_face:
    mov [wa_fv], ax
    mov bl, al
    xor bh, bh
    call wa_vert
    mov bl, [wa_fv+1]
    xor bh, bh
    call wa_vert
    mov cl, 4                   ; THE PRE-CHECK: the columns it could reach,
    xor bh, bh                  ; from the columns (a vertex in view is its
    mov bl, [wa_fv+1]           ; own, one beside the view is beyond that
    call .reach                 ; edge, one behind is anywhere)
    mov dx, ax
    mov bl, [wa_fv]
    call .reach
    cmp ax, dx
    jle .lohi
    xchg ax, dx
.lohi:
    cmp ax, 0x8000              ; (behind: anywhere)
    je .open
    or dx, dx                   ; wholly left of the screen, or right: off
    js .shut                    ; it, whatever is open
    cmp ax, [wa_w]
    jge .shut
    or ax, ax
    jns .lo
    xor ax, ax
.lo:
    cmp dx, [wa_w]
    jl .hi
    mov dx, [wa_w]
    dec dx
.hi:
    mov cx, dx
    sub cx, ax
    inc cx
    mov di, ax
    shl di, 1
    add di, wa_cov
    xor ax, ax
    repne scasw
    je .open                    ; an open column: carry on
.shut:
    ret                         ; every one closed: nothing more
.open:
    mov bl, [wa_fv]
    mov di, bx                  ; DI = v1 x 2, BX = v2 x 2
    mov bl, [wa_fv+1]
    mov al, [wa_vok+di]
    mov [wa_e1], al
    mov ah, [wa_vok+bx]
    and ah, [wa_endok]          ; (the end corner, only on a silhouette)
    mov [wa_e2], ah
    and al, [wa_vok+bx]
    jz .clip
    mov si, di                  ; both inside the view: the cache
    mov di, wa_c1
    push bx
    call .put
    pop si
    call .put                   ; (DI has run on to wa_c2)
    jmp wa_span
.clip:
    mov ax, [wa_vx+di]
    mov [wa_x1], ax
    mov ax, [wa_vz+di]
    mov [wa_z1], ax
    mov ax, [wa_vx+bx]
    mov [wa_x2], ax
    mov ax, [wa_vz+bx]
    mov [wa_z2], ax
    push bx
    push di
    call wa_clip                ; (it never moves an end inside the view)
    pop si
    jc .gone
    mov di, wa_c1
    mov bx, wa_x1
    call .end
    pop si
    mov bx, wa_x2
    call .end
    jmp wa_span
.gone:
    pop bx
    ret
.end:                           ; SI = a vertex, BX = its clipped (x, z),
    test byte [wa_vok+si], 1    ; DI = wa_c1 or wa_c2: projected
    jnz .put
    mov ax, [bx]
    mov bx, [bx+2]
    call wa_proj
    stosw
    xchg ax, bx
    stosw
    xchg ax, cx
    stosw
    xchg ax, dx
    stosw
    ret
.put:                           ; SI = a vertex in view, DI = wa_c1 or wa_c2:
    test byte [wa_vok+si], 2    ; its column, top, bottom, inverse depth -
    jnz .have                   ; the last three made the first time a face
    or byte [wa_vok+si], 2      ; of it gets this far in a frame
    mov bx, [wa_vz+si]
    call wa_ptbi
    mov [wa_vpt+si], bx
    mov [wa_vpb+si], cx
    mov [wa_vpi+si], dx
.have:
    mov ax, [wa_vpc+si]
    stosw
    mov ax, [wa_vpt+si]
    stosw
    mov ax, [wa_vpb+si]
    stosw
    mov ax, [wa_vpi+si]
    stosw
    ret
.reach:                         ; BX = vertex x 2, CL = 4 -> AX = its column
    test byte [wa_vok+bx], 1    ; (on the screen or off it), -32767 or 32767
    jz .rout                    ; beside the view, 0x8000 behind it
    mov ax, [wa_vpc+bx]
    sar ax, cl
    ret
.rout:
    mov ax, 0x8000
    cmp word [wa_vz+bx], WA_NEAR
    jl .rret                    ; behind: anywhere
    mov ax, -32767
    cmp word [wa_vx+bx], 0
    jl .rret                    ; beside the view, left
    mov ax, 32767               ; ...or right
.rret:
    ret

; wa_vert - BX = a vertex x 2: into camera space and, inside the view (the
; guard band), its column - once a frame (wa_vst). [wa_vok]: 0 outside,
; 1 the column made, 3 the rest too (wa_face). Clobbers AX, BX, CX, DX, SI,
; DI.
wa_vert:
    mov al, [wa_frame]
    cmp [wa_vst+bx], al
    je .out
    mov [wa_vst+bx], al
    mov di, bx                  ; DI = vertex x 2
    mov ax, [wa_vtx+bx]         ; AL = x index x 4, AH = y index x 4
    mov bl, ah
    xor bh, bh
    xor ah, ah
    mov si, ax
    mov ax, [wa_xc+si]          ; z = ((x-px) 4 cos + (y-py) 4 sin) >> 16
    add ax, [wa_ys+bx]
    mov cx, [wa_xc+si+2]
    adc cx, [wa_ys+bx+2]
    mov ax, [wa_xs+si]          ; x = ((x-px) 4 sin - (y-py) 4 cos) >> 16
    sub ax, [wa_yc+bx]
    mov ax, [wa_xs+si+2]
    sbb ax, [wa_yc+bx+2]
    mov [wa_vz+di], cx
    mov [wa_vx+di], ax
    mov byte [wa_vok+di], 0
    cmp cx, WA_NEAR             ; projectable: z >= NEAR, |x| <= 8z (the
    jl .out                     ; guard band - the screen is |x| <= z)
    mov bx, cx
    shl bx, 1
    shl bx, 1
    shl bx, 1
    cmp ax, bx
    jg .out
    neg bx
    cmp ax, bx
    jl .out
    mov byte [wa_vok+di], 1
    imul word [wa_k16]          ; the column, x16 (wa_proj)
    idiv cx
    add ax, [wa_c16]
    mov [wa_vpc+di], ax
.out:
    ret

; wa_xform - AX, BX = a world point -> AX = camera x (right), DX = z
; (ahead). Clobbers BX, CX, SI, DI.
wa_xform:
    sub ax, [wa_px]
    sub bx, [wa_py]
    push ax
    push bx
    imul word [wa_cos]          ; z = (dx cos + dy sin) >> 14
    mov cx, ax
    mov si, dx
    mov ax, bx
    imul word [wa_sinv]
    add ax, cx
    adc dx, si
    shl ax, 1
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    mov di, dx
    pop bx
    pop ax
    imul word [wa_sinv]         ; x = (dx sin - dy cos) >> 14
    mov cx, ax
    mov si, dx
    mov ax, bx
    imul word [wa_cos]
    sub cx, ax
    sbb si, dx
    shl cx, 1
    rcl si, 1
    shl cx, 1
    rcl si, 1
    mov ax, si
    mov dx, di
    ret

; wa_clip - the segment (x1,z1)-(x2,z2) against z >= NEAR and the guard
; band x >= -8z, x <= 8z. CF = 1: nothing left. An end inside all three is
; never moved. A cut at the near plane sets z to NEAR (the interpolation
; gave exactly that) and interpolates x alone. Clobbers AX, BX, CX, DX, SI,
; DI, BP.
wa_clip:
    mov ax, [wa_z1]
    sub ax, WA_NEAR
    mov dx, [wa_z2]
    sub dx, WA_NEAR
    call .order
    jc .rej
    jz .left
    xor bx, bx
    call .lerp
    add [si], ax
    mov word [si+2], WA_NEAR
.left:                          ; the GUARD BAND, |x| <= 8z, not the view
    mov cl, 3                   ; (|x| <= z): a vertex beside the view projects
    mov ax, [wa_z1]             ; to a column off the screen and the span
    shl ax, cl                  ; clamps it, so only a vertex far outside -
    add ax, [wa_x1]             ; whose column would overflow - is clipped
    mov dx, [wa_z2]
    shl dx, cl
    add dx, [wa_x2]
    call .order
    jc .rej
    jz .right
    call .side
.right:
    mov cl, 3
    mov ax, [wa_z1]
    shl ax, cl
    sub ax, [wa_x1]
    mov dx, [wa_z2]
    shl dx, cl
    sub dx, [wa_x2]
    call .order
    jc .rej
    jz .ok
    call .side
.ok:
    clc
.rej:
    ret
.order:                         ; AX = d1, DX = d2 -> CF: both outside; else
    or ax, ax                   ; ZF: neither; else SI = the end outside,
    js .o1                      ; DI = the one inside, BP = -d(out),
    or dx, dx                   ; CX = d(in) - d(out)
    jns .none
    mov si, wa_x2
    mov di, wa_x1
    neg dx
    mov bp, dx
    add ax, dx
    mov cx, ax
    or si, si                   ; (NZ, NC)
    ret
.o1:
    or dx, dx
    js .both
    mov si, wa_x1
    mov di, wa_x2
    neg ax
    mov bp, ax
    add dx, ax
    mov cx, dx
    or si, si
    ret
.both:
    stc
    ret
.none:
    xor si, si                  ; (ZF, NC)
    ret
.side:                          ; a cut at a side plane: x and z
    xor bx, bx
    call .lerp
    push ax
    mov bx, 2
    call .lerp
    add [si+2], ax
    pop ax
    add [si], ax
    ret
.lerp:                          ; BX = 0 (x) or 2 (z) -> AX = the change:
    mov ax, [di+bx]             ; (in - out) d(out) / (d(out) - d(in))
    sub ax, [si+bx]
    imul bp
    idiv cx
    ret

; wa_proj - AX = x, BX = z (>= NEAR, |x| <= 8z) -> AX = column x16,
; BX = top and CX = bottom (quarter half-rows), DX = inverse depth
wa_proj:
    imul word [wa_k16]          ; the column, x16: NOT clamped - a vertex in
    idiv bx                     ; the guard band lands off the screen and
    add ax, [wa_c16]            ; the span clamps to it. (The CENTRE, 8W -
    push ax                     ; not the scale, 8Wf: at 90 degrees they are
    call wa_ptbi                ; one number, and using the scale for both put
    pop ax                      ; every wall six columns right at 75)
    ret

; wa_ptbi - BX = z (>= NEAR) -> BX = top, CX = bottom (quarter half-rows),
; DX = inverse depth, 0x7FFF0 / z (32767 at the near plane) - out of
; wa_rcp, the same bits the divide gave. Clobbers AX
wa_ptbi:
    cmp bx, WA_ZMAX
    jae .div
    shl bx, 1
    mov bx, [wa_rcp+bx-WA_NEAR*2]
.iz:
    mov ax, [wa_numt]           ; top = hq - numt / z = hq - (numt x iz) >> 19:
    imul bx                     ; a multiply where a divide was
    sar dx, 1
    sar dx, 1
    sar dx, 1
    mov cx, [wa_hq]
    sub cx, dx
    mov ax, [wa_numb]
    imul bx
    sar dx, 1
    sar dx, 1
    sar dx, 1
    add dx, [wa_hq]
    xchg bx, cx                 ; BX = top, CX = iz
    xchg cx, dx                 ; CX = bottom, DX = iz
    ret
.div:                           ; (deeper than the room: never, but exact)
    mov ax, 0xFFF0
    mov dx, 0x0007
    div bx
    mov bx, ax
    jmp .iz

; --- spans --------------------------------------------------------------
; The hot loop of a frame. Plotting is INLINE (WPLOT): DL = the frame's
; stamp and DI = the list's write pointer stay in registers for a whole
; span.
%macro WPLOT 0                  ; BX = cell, AX = char|attr; first one wins
    cmp [wa_stamp+bx], dl
    je %%skip
    mov [wa_stamp+bx], dl
    mov [wa_cur+bx], ax
    xchg ax, bx                 ; onto the list (ES = DS through wa_render)
    stosw
    xchg ax, bx
%%skip:
%endmacro

; wa_span - the projected segment (c1,t1,b1,i1)-(c2,t2,b2,i2): stepped
; across its columns, drawn into the open ones, which it then closes.
wa_span:
    mov ax, [wa_c1]
    mov bx, [wa_c2]
    cmp ax, bx
    jl .front
    ret
.front:
    mov cl, 4
    mov dx, ax                  ; first column whose centre (16c+8) >= c1
    add dx, 7
    sar dx, cl
    mov si, bx                  ; last whose centre < c2
    add si, 7
    sar si, cl
    dec si
    mov ax, dx                  ; (the segment's own ends, for its corners,
    shl ax, 1                   ; before the screen clamps them)
    mov [wa_cs0], ax
    mov ax, si
    shl ax, 1
    mov [wa_ce0], ax
    or dx, dx                   ; ...and the screen
    jns .lok
    xor dx, dx
.lok:
    mov ax, [wa_w]
    dec ax
    cmp si, ax
    jle .rok
    mov si, ax
.rok:
    cmp dx, si
    jle .some
    ret
.some:
    mov cx, si                  ; ANY OPEN COLUMN? One scan of wa_cov, before
    sub cx, dx                  ; a single divide: a wall wholly behind
    inc cx                      ; nearer ones costs this and nothing more
    shl dx, 1                   ; (ES = DS through wa_render)
    shl si, 1
    mov di, dx
    add di, wa_cov
    xor ax, ax
    repne scasw
    je .open1
    ret
.open1:
    lea dx, [di-2-wa_cov]       ; DX = the first open column x 2...
    mov [wa_cs], dx
    mov cx, si
    sub cx, dx
    shr cx, 1
    inc cx
    lea di, [si+wa_cov]
    std
    repne scasw                 ; ...and, from the right, the last
    cld
    lea si, [di+4-wa_cov]       ; one past it, x 2
    mov [wa_end], si
    shr dx, 1                   ; DX = the first open column
    mov ax, dx
    mov cl, 4
    shl ax, cl
    add ax, 8
    sub ax, [wa_c1]
    mov [wa_fs], ax             ; first open centre past c1, x16
    mov ax, bx
    sub ax, [wa_c1]
    mov [wa_dc], ax
    ; THE EDGES' START AND STEP, EXACT (docs/plans/MULTIPLAYER-FPS-PLAN.md
    ; 16.5). The start used to be STEPPED from the segment's own first
    ; column - for a wall clipped at the guard band, ~150 columns off the
    ; screen - with a step truncated to a whole 13.3 unit: up to 0.99 of a
    ; unit lost a column, two and more half-rows by the first visible one.
    ; That was the far wall the owner saw drawn in front of a nearer pillar.
    ; Now the first open column's value is interpolated exactly, and the
    ; step is in HALF-ROWS with a 16-bit fraction (the loop keeps the edge as
    ; whole.fraction, the whole part being the ROUNDED half-row itself: no
    ; column shifts or rounds). See .edge.
    mov byte [wa_steep], 0
    mov ax, [wa_t1]
    mov bx, [wa_t2]
    call .edge
    mov [wa_st], dx
    mov [wa_stl], ax
    mov [wa_vt0], bx            ; (the first column's, for its corner)
    push cx
    mov ax, [wa_b1]
    mov bx, [wa_b2]
    call .edge
    mov [wa_sb], dx
    mov [wa_sbl], ax
    mov [wa_vb], bx             ; the bottom: half-row and fraction
    mov [wa_vbl], cx
    mov [wa_vb0], bx
    pop bp                      ; the top: CX.BP in the loop
    mov cx, [wa_vt0]
    ; REGISTER THE SPAN: wa_cov holds its tag (x 2, from 2: a byte, the
    ; word's high byte staying 0) in every column it opens, and the table
    ; its ends.
    mov bx, [wa_tag]
    add bx, 2
    cmp bx, WA_MAXSP*2
    jb .tagok
    mov word [wa_left], 0       ; (more spans than the table holds: stop
    ret                         ; drawing this frame - never seen)
.tagok:
    mov [wa_tag], bx
    mov ax, [wa_c1]             ; its projected ends - inverse depth is linear
    mov [wa_spcs+bx], ax        ; in the column, and wa_wallz interpolates
    mov ax, [wa_dc]             ; it for the few columns asked about, where
    mov [wa_spsh+bx], ax        ; every span used to step it
    mov ax, [wa_i1]
    mov [wa_spih+bx], ax
    mov ax, [wa_i2]
    sub ax, [wa_i1]
    mov [wa_spsl+bx], ax
    mov word [wa_ncl], 0
    mov si, [wa_cs]
    mov di, [wa_lp]
    mov dl, [wa_frame]
    mov dh, bl                  ; DH = the tag
    mov ah, [wa_wcol]           ; the wall's colour: its ITEM's, not its depth
    mov [wa_eatt], ah           ; (the slope fill and the corners read it)
    xor bx, bx                  ; which of the eight loops
    cmp byte [wa_sparse], 0
    je .v1
    or bl, 8
.v1:
    cmp byte [wa_steep], 0
    je .v2
    or bl, 4
.v2:
    cmp byte [wa_hyst], 0
    je .v3
    or bl, 2
.v3:
    call [wa_loops+bx]
    mov [wa_lp], di
    mov ax, [wa_end]            ; opened: the range less the shut ones
    sub ax, [wa_cs]
    shr ax, 1
    sub ax, [wa_ncl]
    sub [wa_left], ax
    mov si, [wa_cs]             ; the corners, at the segment's own ends,
    cmp si, [wa_cs0]            ; when this span opened them: a `│` each
    jne .c2
    cmp byte [wa_e1], 0
    je .c2
    mov bx, [wa_vt0]
    mov ax, [wa_vb0]
    push cx
    mov cl, [wa_hyst]           ; (nothing else is in this column yet - but
    call wa_corner              ; a HELD edge can be inside the post)
    pop cx
.c2:
    mov si, [wa_end]
    dec si
    dec si
    cmp si, [wa_ce0]
    jne .cdone
    cmp byte [wa_e2], 0
    je .cdone
    sub bp, [wa_stl]            ; the last column's edges: the accumulators
    sbb cx, [wa_st]             ; are one column past it
    mov bx, cx
    mov ax, [wa_vbl]
    sub ax, [wa_sbl]
    mov ax, [wa_vb]
    sbb ax, [wa_sb]
    mov cl, [wa_hyst]           ; (a steep step's fill can be in this column
    or cl, [wa_steep]           ; too, and wins)
    call wa_corner
.cdone:
    mov [wa_lp], di
    ret

; .edge - AX = t1, BX = t2 (an edge's ends, quarter half-rows) -> DX:AX =
; its step a column, BX.CX = its value at the first open column: half-rows,
; 16.16, the whole part ROUNDED (half a row added). Marks wa_steep when the
; step is a half-row or more. Clobbers SI, DI, BP.
; The step is change x 4 x 65536 / dc: ONE divide when it is under a
; half-row (the usual far wall), two otherwise. The start is t1 + the step x
; off / 16 - the step's 16-bit fraction makes that exact to a few
; thousandths of a half-row even ~300 columns from the segment's start (a
; guard-band clip), and it is one MULTIPLY (two on a steep edge) where an
; IMUL and an IDIV were.
.edge:
    push ax                     ; t1
    sub bx, ax
    mov ax, bx
    cwd
    push dx                     ; the change's sign
    xor ax, dx
    sub ax, dx                  ; |change|
    xor cx, cx                  ; CX = the step's whole part
    xor dx, dx
    cmp word [wa_dc], 16        ; whenever the SEGMENT spans more than a
    ja .e1                      ; column (not the trimmed count)
    xor ax, ax
    jmp .e2
.e1:
    shl ax, 1
    rcl dx, 1
    shl ax, 1
    rcl dx, 1                   ; DX:AX = |change| x 4
    or dx, dx
    jnz .ew
    cmp ax, [wa_dc]
    jb .ef
.ew:
    div word [wa_dc]
    mov cx, ax
    mov byte [wa_steep], 1
    xor ax, ax
    jmp .ed
.ef:
    xchg ax, dx                 ; (under a half-row: the fraction alone)
.ed:
    div word [wa_dc]
.e2:
    mov bp, cx                  ; BP.SI = |step|
    mov si, ax
    mul word [wa_fs]            ; x off: DI:CX (and DX above it, steep)
    mov cx, ax
    mov di, dx
    or bp, bp
    jz .e3
    mov ax, bp
    mul word [wa_fs]
    add di, ax
    adc dx, 0
    shr dx, 1                   ; / 16
    rcr di, 1
    rcr cx, 1
    shr dx, 1
    rcr di, 1
    rcr cx, 1
    shr dx, 1
    rcr di, 1
    rcr cx, 1
    shr dx, 1
    rcr di, 1
    rcr cx, 1
    jmp .e4
.e3:
    shr di, 1
    rcr cx, 1
    shr di, 1
    rcr cx, 1
    shr di, 1
    rcr cx, 1
    shr di, 1
    rcr cx, 1
.e4:
    pop ax                      ; the sign onto both
    or ax, ax
    jz .e5
    neg di
    neg cx
    sbb di, 0
    neg bp
    neg si
    sbb bp, 0
.e5:
    pop ax                      ; + t1 (x 16384) + a half
    mov dx, ax
    sar dx, 1
    sar dx, 1
    ror ax, 1
    ror ax, 1
    and ax, 0xC000
    add ax, cx
    adc dx, di
    add ax, 0x8000
    adc dx, 0
    mov cx, ax
    mov bx, dx
    mov dx, bp
    mov ax, si
    ret

; --- the column loops ---------------------------------------------------------
; The hot path of a frame, generated eight ways so no column tests a mode:
; %1 = 1 draws the TOP edge (the full detail level; 0 is the sparse one,
; floor lines and corner posts), %2 = 1 fills steep steps (a span whose
; edge can move two half-rows a column), %3 = 1 holds edges (EDGE).
; In: SI = first column x 2, [wa_end] = one past the last x 2 (the first
; and last are open), CX.BP = the top (whole half-row, rounded, and a
; 16-bit fraction), wa_vb.wa_vbl the bottom alike, DL = the stamp, DH = the
; span's tag, AH = the wall's attribute, DI = the list. Out: DI, the two
; accumulators one column past the end, wa_ncl = the columns found shut.
; The top lives in registers, so neither edge shifts or rounds: an opened
; column at full detail is ~105 bytes of code (round 2's was ~142, the
; first renderer's ~260). The top is the first cell its column draws, so it
; needs no stamp test.
; EDGE - BX = an edge's half-row from the accumulator %1.%2 (%3 = 0); or
; (%3 = 1) held at last frame's half-row (%4, per column) until the true
; position is a QUARTER half-row past the boundary - so a far edge on a
; slow turn steps once instead of flickering between two. Clobbers AX
%macro EDGE 4
%if %3
    mov bx, %1
    sub bx, [%4+si]             ; x - held + a quarter: [0, 1.5) keeps
    mov ax, %2
    add ax, 0x4000
    adc bx, 0
    jz %%keep
    dec bx
    jnz %%move
    cmp ax, 0x8000
    jb %%keep
%%move:
    mov bx, %1
    mov [%4+si], bx
    jmp %%have
%%keep:
    mov bx, [%4+si]
%%have:
    mov ah, [wa_eatt]
%else
    mov bx, %1
%endif
%endmacro

%macro SPANLOOP 3
%%col:
    cmp word [wa_cov+si], 0
    jne %%shut
    mov [wa_cov+si], dh
%if %1
    EDGE cx, bp, %3, wa_pt32
  %if %2
    mov [wa_cht+si], bx
  %endif
    cmp bx, WA_HR
    jae %%t
    mov al, [wa_hgl+bx]
    shl bx, 1
    mov bx, [wa_hroff+bx]
    add bx, si
    mov [wa_stamp+bx], dl       ; the first cell of its column: no test
    mov [wa_cur+bx], ax
    xchg ax, bx
    stosw
    xchg ax, bx
%%t:
%endif
    EDGE [wa_vb], [wa_vbl], %3, wa_pb32
%if %2
    mov [wa_chb+si], bx
%endif
    cmp bx, WA_HR
    jae %%b
    mov al, [wa_hgl+bx]
    shl bx, 1
    mov bx, [wa_hroff+bx]
    add bx, si
%if %1
    WPLOT                       ; (the top's cell, a wall under a row tall)
%else
    mov [wa_stamp+bx], dl
    mov [wa_cur+bx], ax
    xchg ax, bx
    stosw
    xchg ax, bx
%endif
%%b:
%if %2
    cmp [wa_cov+si-2], dh       ; the column before was ours: fill a steep
    jne %%step                  ; step (wa_covpad stands before column 0)
    push cx
  %if %1
    mov ax, [wa_cht+si]
    mov cx, [wa_cht+si-2]
    call wa_stepfill
  %endif
    mov ax, [wa_chb+si]
    mov cx, [wa_chb+si-2]
    call wa_stepfill
    pop cx
    mov ah, [wa_eatt]
%endif
%%step:
    add bp, [wa_stl]            ; 16.16: the fraction carries
    adc cx, [wa_st]
    mov bx, [wa_sbl]
    add [wa_vbl], bx
    mov bx, [wa_sb]
    adc [wa_vb], bx
    inc si
    inc si
    cmp si, [wa_end]
    jb %%col
    ret
%%shut:                         ; (a nearer wall: wa_gap jumps the run)
    call wa_gap
    jmp %%col
%endmacro
wa_l000:    SPANLOOP 1, 0, 0     ; full, flat
wa_l001:    SPANLOOP 1, 0, 1     ; ...held edges
wa_l010:    SPANLOOP 1, 1, 0     ; full, steep
wa_l011:    SPANLOOP 1, 1, 1
wa_l100:    SPANLOOP 0, 0, 0     ; sparse
wa_l101:    SPANLOOP 0, 0, 1
wa_l110:    SPANLOOP 0, 1, 0
wa_l111:    SPANLOOP 0, 1, 1
wa_loops:   dw wa_l000, wa_l001, wa_l010, wa_l011
            dw wa_l100, wa_l101, wa_l110, wa_l111

; wa_gap - SI = a shut column x 2 inside a span's loop: on to the next open
; one (the span's last column is open, so there is one), the accumulators
; jumped across the run by MULTIPLYING - a gap behind a nearer box averages
; eight columns, each of which used to be stepped through the loop - and
; wa_ncl counted. Keeps everything else the loop holds.
wa_gap:
    push ax
    push dx
    push di
    push cx
    lea di, [si+wa_cov+2]
    mov cx, [wa_end]
    sub cx, si
    shr cx, 1
    dec cx                      ; the columns after this one (one is open)
    xor ax, ax
    repne scasw
    lea ax, [di-2-wa_cov]
    mov cx, ax
    sub cx, si
    mov si, ax                  ; SI = the next open column
    shr cx, 1                   ; CX = the shut ones, k
    add [wa_ncl], cx
    mov ax, [wa_stl]            ; the top: + k x the step, whole.fraction
    mul cx
    add bp, ax
    adc dx, 0
    mov bx, dx
    mov ax, [wa_st]
    imul cx                     ; (k x the whole part: its low word)
    add bx, ax
    pop ax
    add ax, bx
    push ax
    mov ax, [wa_sbl]            ; the bottom alike
    mul cx
    add [wa_vbl], ax
    adc dx, 0
    mov bx, dx
    mov ax, [wa_sb]
    imul cx
    add ax, bx
    add [wa_vb], ax
    pop cx
    pop di
    pop dx
    pop ax
    ret

; wa_stepfill - AX = this column's edge, CX = the last one's (half-rows):
; two half-rows or more apart is a step to fill (wa_slope); less is not
wa_stepfill:
    mov bx, ax
    sub bx, cx
    inc bx                      ; -1..+1 -> 0..2: no fill
    cmp bx, 3
    jb .no
    jmp wa_slope
.no:
    ret

; wa_wallz - BX = column x 2: the inverse depth of the wall drawn there
; (0 none) into wa_colz[BX], from the span that opened it - once a frame,
; and only for the columns that are asked about. Keeps every register.
wa_wallz:
    cmp word [wa_colz+bx], 0xFFFF
    jne .out
    push ax
    push cx
    push dx
    push si
    mov si, [wa_cov+bx]
    xor ax, ax
    or si, si
    jz .put
    mov ax, bx                  ; iz = i1 + (i2 - i1)(16c + 8 - c1) / (c2 - c1)
    shl ax, 1
    shl ax, 1
    shl ax, 1
    add ax, 8
    sub ax, [wa_spcs+si]
    imul word [wa_spsl+si]
    idiv word [wa_spsh+si]
    add ax, [wa_spih+si]
.put:
    mov [wa_colz+bx], ax
    pop si
    pop dx
    pop cx
    pop ax
.out:
    ret

; wa_slope - AX = this column's edge, CX = the last column's (half-rows),
; SI = column x 2: a step of two half-rows or more is filled down it,
; `\` falling to the right and `/` rising - one cell a row, the cell
; stepped by a row rather than looked up. Keeps SI, DI's list pointer and
; DL; clobbers AX, BX, CX.
wa_slope:
    push bp
    mov bp, '\'
    cmp ax, cx
    jg .fall
    mov bp, '/'
    xchg ax, cx                 ; AX = the lower edge, CX = the higher
.fall:
    inc cx                      ; half-rows CX+1 .. AX-1, as rows
    sar cx, 1
    jns .c0
    xor cx, cx
.c0:
    dec ax
    sar ax, 1
    cmp ax, WA_ROWS-1
    jle .c1
    mov ax, WA_ROWS-1
.c1:
    sub ax, cx
    jl .out
    inc ax
    mov bx, cx
    shl bx, 1
    mov bx, [wa_rowo2+bx]
    add bx, si
    mov cx, ax
    mov ax, bp
    mov ah, [wa_eatt]
.row:
    WPLOT
    add bx, [wa_rowo2+2]        ; (a row's offset: row 1's)
    loop .row
.out:
    pop bp
    ret

; wa_corner - BX = top, AX = bottom (half-rows), SI = column x 2, CL = 0
; when no cell between them can have been drawn this frame: `│` between
; them, the cell stepped by a row; CL = 0 skips the stamp tests. Keeps SI,
; DI and DL; clobbers AX, BX, CX.
wa_corner:
    or cl, cl
    jnz wa_vedge
    call wa_vrows
    jcxz .out
    push bp
    mov bp, [wa_rowo2+2]        ; (a row's offset: row 1's)
.row:
    mov [wa_stamp+bx], dl
    mov [wa_cur+bx], ax
    xchg ax, bx
    stosw
    xchg ax, bx
    add bx, bp
    loop .row
    pop bp
.out:
    ret
; wa_vedge - the same, every cell tested (first one wins)
wa_vedge:
    call wa_vrows
    jcxz .out
    push bp
    mov bp, [wa_rowo2+2]
.row:
    WPLOT
    add bx, bp
    loop .row
    pop bp
.out:
    ret
wa_vrows:                       ; -> BX = the first cell, CX = rows (0:
    sar ax, 1                   ; none), AX = the glyph. The bottom's row:
    cmp ax, WA_ROWS             ; stop before it
    jle .bok
    mov ax, WA_ROWS
.bok:
    sar bx, 1
    inc bx                      ; the row under the top's
    jns .tok
    xor bx, bx
.tok:
    mov cx, ax
    sub cx, bx
    jg .some
    xor cx, cx
    ret
.some:
    shl bx, 1
    mov bx, [wa_rowo2+bx]
    add bx, si
    mov al, 0xB3
    mov ah, [wa_eatt]
    ret

wa_list:                        ; BX = cell, onto this frame's list
    push di
    mov di, [wa_newp]
    add di, [wa_newn]
    mov [di], bx
    add word [wa_newn], 2
    pop di
    ret

; wa_plotf - BX = cell offset, DL = sub-cell bit(s), AH = attribute: a figure's
; sub-pixels, OR'd into whatever of the figure layer the cell has, over any
; wall glyph. Clobbers AX, DX.
wa_plotf:
    mov al, [wa_frame]
    or al, 0x80
    cmp [wa_stamp+bx], al
    je .have                    ; a figure cell already: add the bit
    and al, 0x7F
    cmp [wa_stamp+bx], al
    je .listed                  ; a wall cell this frame: already listed
    call wa_list
.listed:
    or al, 0x80
    mov [wa_stamp+bx], al
    jmp .put
.have:
    or dl, [wa_fmask+bx]
.put:
    mov [wa_fmask+bx], dl
    push bx
    mov bl, dl
    and bx, 15
    mov al, [wa_fglyph+bx]
    pop bx
    mov [wa_cur+bx], ax
    ret

; --- the floor grid (G) -------------------------------------------------------
; A dim dot every 2 m, (64 + 128i, 64 + 128j), within ~6 m on each axis: a
; depth cue that does not depend on a wall's height. Behind walls (wa_wallz)
; and under figures (drawn after). Off by default: the owner's question is
; whether it costs the black ground's readability.
WA_DOTSP    equ 128
wa_dots:
    cmp byte [wa_grid], 0
    jne .on
    ret
.on:
    mov ax, [wa_px]             ; the lines within 4 of the player's
    mov si, wa_dxc
    mov di, wa_dxs
    call .lines
    mov [wa_dnx], cx
    mov ax, [wa_py]
    mov si, wa_dyc
    mov di, wa_dys
    call .lines
    mov [wa_dny], cx
    mov word [wa_dix], 0
.ix:
    mov word [wa_diy], 0
.iy:
    mov si, [wa_dix]
    mov bp, [wa_diy]
    mov ax, [wa_dxc+si]         ; z = (Xc + Ys) >> 14
    mov dx, [wa_dxc+si+2]
    add ax, [ds:wa_dys+bp]
    adc dx, [ds:wa_dys+bp+2]
    shl ax, 1
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    cmp dx, 48
    jl .next                    ; behind, or at our feet
    mov cx, dx                  ; CX = z
    mov ax, [wa_dxs+si]         ; x = (Xs - Yc) >> 14
    mov dx, [wa_dxs+si+2]
    sub ax, [ds:wa_dyc+bp]
    sbb dx, [ds:wa_dyc+bp+2]
    shl ax, 1
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    mov ax, dx                  ; AX = x
    mov bx, ax
    or bx, bx
    jns .xa
    neg bx
.xa:
    cmp bx, cx
    jg .next                    ; outside even the widest view
    push ax                     ; ONE divide a dot: 1/z, then multiplies
    mov dx, 0x0007
    mov ax, 0xFFF0
    div cx
    mov [wa_diz], ax            ; (2^19 / z)
    pop ax
    imul word [wa_diz]          ; x / z x 2^19 - |x| <= z, so 20 bits: >> 3
    sar dx, 1                   ; is x/z x 65536 in 16
    rcr ax, 1
    sar dx, 1
    rcr ax, 1
    sar dx, 1
    rcr ax, 1
    imul word [wa_k16]          ; x 8Wf / 65536: the column's offset, x16
    mov bx, dx
    add bx, [wa_c16]            ; the centre, not the scale
    push cx
    mov cl, 4
    sar bx, cl
    pop cx
    cmp bx, [wa_w]
    jae .next                   ; (negative is huge, unsigned)
    shl bx, 1
    call wa_wallz
    mov ax, [wa_diz]
    cmp [wa_colz+bx], ax
    ja .next                    ; a wall is nearer
    mov ax, [wa_numb]           ; the floor's half-row: hh + numb/z/4 =
    imul word [wa_diz]          ; hh + (numb x 2^19/z) >> 21
    push cx
    mov cl, 5
    sar dx, cl
    pop cx
    mov ax, dx
    add ax, [wa_hh]
    cmp ax, WA_HR
    jae .next
    mov si, ax
    shl si, 1
    add bx, [wa_hroff+si]       ; BX = the cell
    mov ah, [wa_at+A_DOT]
    mov al, 0xFA                ; upper half: the middle dot...
    test si, 2
    jz .gl
    mov al, '.'                 ; ...lower: the full stop
.gl:
    mov dl, [wa_frame]
    mov di, [wa_lp]
    WPLOT
    mov [wa_lp], di
.next:
    add word [wa_diy], 4
    mov ax, [wa_diy]
    cmp ax, [wa_dny]
    jb .iy
    add word [wa_dix], 4
    mov ax, [wa_dix]
    cmp ax, [wa_dnx]
    jb .ix
    ret
; .lines - AX = the player's coordinate, SI/DI = cos/sin product tables: the
; grid lines within three of it, (v - p) cos and (v - p) sin each. CX = their
; count x 4.
.lines:
    mov bx, ax
    mov cl, 7
    shr bx, cl                  ; the line nearest below, roughly
    sub bx, 3
    jns .l0
    xor bx, bx
.l0:
    mov dx, bx
    add dx, 7
    cmp dx, 16
    jbe .l1
    mov dx, 16
.l1:
    xor cx, cx
.l2:
    push ax
    push dx
    mov dx, bx                  ; the line's coordinate: 64 + 128 k
    push cx
    mov cl, 7
    shl dx, cl
    pop cx
    add dx, 64
    sub dx, ax
    push dx
    mov ax, dx
    imul word [wa_cos]
    push bx
    mov bx, cx
    mov [si+bx], ax
    mov [si+bx+2], dx
    pop bx
    pop ax
    imul word [wa_sinv]
    push bx
    mov bx, cx
    mov [di+bx], ax
    mov [di+bx+2], dx
    pop bx
    pop dx
    pop ax
    add cx, 4
    inc bx
    cmp bx, dx
    jb .l2
    ret

; --- figures ----------------------------------------------------------------
wa_figures:
    push bp
    mov di, wa_figs
    xor bx, bx                  ; BX = the figure x 2
    xor bp, bp                  ; BP = how many are in view, x 2
.proj:
    mov word [di+F_PZ], 0
    push bx
    push di
    mov ax, [di+F_X]
    mov bx, [di+F_Y]
    call wa_xform
    pop di
    pop bx
    mov [wa_fxs+bx], ax
    mov [wa_fzs+bx], dx
    mov [wa_frec+bx], di
    cmp dx, 32                  ; half a metre: too close to draw
    jl .nxt
    mov cx, dx
    add cx, 64
    or ax, ax
    jns .ax
    neg ax
.ax:
    cmp ax, cx
    jg .nxt                     ; outside the view, with a body's margin
    mov si, bp                  ; in view: into wa_ford, far to near - an
.ins:                           ; insertion, so the first of equal depths
    or si, si                   ; stays first, as the old pick had it
    jz .put
    mov ax, [wa_ford-2+si]
    xchg ax, bx
    cmp dx, [wa_fzs+bx]
    xchg ax, bx
    jle .put
    mov [wa_ford+si], ax
    dec si
    dec si
    jmp .ins
.put:
    mov [wa_ford+si], bx
    inc bp
    inc bp
.nxt:
    add di, F_SIZE
    inc bx
    inc bx
    cmp bx, WA_NFIG*2
    jb .proj
    xor si, si
.draw:                          ; far to near
    cmp si, bp
    jae .done
    mov bx, [wa_ford+si]
    push si
    push bp
    mov di, [wa_frec+bx]
    mov ax, [wa_fxs+bx]
    mov dx, [wa_fzs+bx]
    call wa_figure
    pop bp
    pop si
    inc si
    inc si
    jmp .draw
.done:
    pop bp
    ret
; WA_MINMAX t - BX, DX = the least and the most of the eleven words at t
; (unrolled for WA_NJ = 11, which tools/arenagen.py asserts)
%macro WA_MINMAX 1
    mov bx, [%1]
    mov dx, bx
  %assign %%j 2
  %rep 10
    mov ax, [%1+%%j]
    cmp ax, bx
    jge $+4                     ; (over the two-byte move)
    mov bx, ax
    cmp ax, dx
    jle $+4
    mov dx, ax
    %assign %%j %%j+2
  %endrep
%endmacro
; WA_LIMB a, b - a limb, joint a x 2 to joint b x 2, into wa_fbuf
%macro WA_LIMB 2
    mov cx, [wa_jsx+%1]
    mov dx, [wa_jsy+%1]
    mov ax, [wa_jsx+%2]
    mov bx, [wa_jsy+%2]
    call word [wa_flfn]         ; wa_fline, or wa_flinef: all on the screen
%endmacro

; wa_figure - DI = a figure, AX = its camera x, DX = its z. Clobbers every
; register but DI.
;
; A near figure is drawn in three passes, each priced for the 8088:
;  1. its eleven joints, blended and projected - the blend specialised per
;     quarter (wa_fjl), the scale in a register;
;  2. its nine limbs and head rasterised into wa_fbuf, a cell-mask scratch
;     laid out like the screen, by a Bresenham whose state is its POSITION
;     IN THE CODE (wa_fline: one block per sub-cell quadrant, so a sub-pixel
;     is one `or byte [bx], imm` and a pointer step) - ~70 clk a sub-pixel
;     against ~700 for the per-sub-pixel clip, depth test and plot it was;
;  3. the box the joints span, swept with `repe scasw`: each cell the figure
;     touched is cleared out of wa_fbuf, depth-tested ONCE against its
;     column's wall (wa_wallz, on demand) and handed to wa_plotf once,
;     however many of its four sub-pixels the limbs set.
; wa_fbuf is all zeros between figures: pass 3 clears exactly what pass 2
; set, because every sub-pixel pass 2 plots is on the screen and inside the
; joints' box (a line stays inside its endpoints' box; the head's 2x2 reaches
; one up and one right, which the box allows for).
wa_figure:
    mov [wa_fcx], ax
    mov [di+F_PZ], dx
    mov si, dx
    mov dx, 0x0007
    mov ax, 0xFFF0
    div si
    mov [wa_fiz], ax
    mov [di+F_PIZ], ax
    mov ax, [wa_wf]             ; sub-columns a unit: W x f / z (f the field
    xor dx, dx                  ; of view's scale, 8.8)
    div si
    mov [wa_fs8], ax
    mov ax, [wa_kyh]
    xor dx, dx
    div si
    mov [wa_fv8], ax
    cmp ax, 9                   ; FAR: under ~4 half-rows tall. Nine limbs of
    jae .near                   ; a sub-pixel or two each read as a blob
    jmp wa_marker               ; anyway - draw that blob directly
.near:
    mov bl, A_FIG
    cmp byte [di+F_FLASH], 0
    je .att
    mov bl, A_FLASH
.att:
    xor bh, bh
    mov al, [wa_at+bx]
    mov [wa_fatt], al
    mov ax, [di+F_ANG]          ; facing, relative to the view, of 16
    sub ax, [wa_cang]
    add ax, 32
    mov cl, 6
    shr ax, cl
    and ax, 15
    mov cl, WA_NJ*2
    mul cl
    mov bx, ax                  ; BX = facing's offset in a frame
    mov ax, [di+F_PH]
    mov cl, al
    and cl, 3
    mov [wa_fsub], cl
    shr ax, 1
    shr ax, 1                   ; AX = keyframe
    mov cx, ax
    inc cx                      ; CX = the next one
    mov dl, [di+F_NFR]
    xor dh, dh
    cmp cx, dx
    jb .nx
    xor cx, cx
    cmp byte [di+F_LOOP], 0
    jne .nx
    mov cx, dx
    dec cx
.nx:
    mov dl, [di+F_ANIM]
    add ax, dx
    add cx, dx
    push di
    mov dx, WA_FRAMESZ
    mul dx
    add ax, wa_pose
    add ax, bx
    mov si, ax                  ; SI = keyframe A at this facing
    mov ax, WA_FRAMESZ
    mul cx
    add ax, wa_pose
    add ax, bx
    mov di, ax                  ; DI = keyframe B
    jmp wa_fjl                  ; the joints (and back to wa_fjdone)
wa_fjdone:                      ; (wa_fjl comes back here)
    pop di
    mov ax, [wa_jsx+4]          ; for the trigger: centre, extent, width
    mov [di+F_PCX], ax
    mov ax, [wa_jsy]
    dec ax
    mov [di+F_PTOP], ax
    mov ax, [wa_jsy+16]
    cmp ax, [wa_jsy+20]
    jge .b
    mov ax, [wa_jsy+20]
.b:
    mov [di+F_PBOT], ax
    mov ax, [wa_fs8]
    mov cx, 20
    mul cx
    mov al, ah
    mov ah, dl
    or ax, ax
    jnz .w
    inc ax
.w:
    mov [di+F_PWH], ax
    push di
    mov byte [wa_fon], 1        ; the joints' box FIRST: whether the limbs
    WA_MINMAX wa_jsx            ; may skip their clip tests, and whether any
    mov ax, [wa_w2]             ; of it is in front of the walls at all.
    or bx, bx                   ; BX = min, DX = max sub-column
    js .xoff
    cmp dx, ax
    jl .xon
.xoff:
    mov byte [wa_fon], 0        ; a joint off the side: limbs clip
.xon:
    inc dx                      ; (the 2x2 head reaches one further)
    or bx, bx
    jns .cl
    xor bx, bx
.cl:
    dec ax
    cmp dx, ax
    jle .cr
    mov dx, ax
.cr:
    sar bx, 1                   ; columns
    sar dx, 1
    sub dx, bx
    jl .out                     ; all off the screen
    inc dx
    mov [wa_fbw], dx            ; the box's width, cells
    shl bx, 1
    mov [wa_fbc], bx            ; ...and its left column x 2
    WA_MINMAX wa_jsy
    or bx, bx
    js .yoff
    cmp dx, WA_HR
    jl .yon
.yoff:
    mov byte [wa_fon], 0        ; above or below: limbs clip
.yon:
    dec bx                      ; (and one higher)
    jns .ct
    xor bx, bx
.ct:
    cmp dx, WA_HR-1
    jle .cb
    mov dx, WA_HR-1
.cb:
    and bl, 0xFE                ; half-rows -> row x 2 (wa_rowo2's index)
    and dl, 0xFE
    cmp bx, dx
    jg .out
    mov [wa_fbr], dx            ; the last row x 2
    mov [wa_frow], bx           ; ...and the first
    mov si, [wa_fiz]            ; the box's columns' walls, asked for once
    mov bx, [wa_fbc]            ; here rather than per cell - and if every
    mov cx, [wa_fbw]            ; one is nearer than the figure, nothing of
    xor dl, dl                  ; it shows: no limbs, no sweep
.rc:
    mov ax, [wa_colz+bx]
    cmp ax, 0xFFFF
    jne .rz
    call wa_wallz
    mov ax, [wa_colz+bx]
.rz:
    cmp ax, si
    ja .rh
    inc dx
.rh:
    inc bx
    inc bx
    loop .rc
    or dl, dl
    jz .out
    mov word [wa_flfn], wa_fline
    cmp byte [wa_fon], 0
    je .limbs
    mov word [wa_flfn], wa_flinef
.limbs:
    WA_LIMB 2, 4                ; pass 2: the limbs into wa_fbuf (joint x 2
    WA_LIMB 2, 6                ; at each end: neck-pelvis, the arms, the
    WA_LIMB 6, 8                ; legs)
    WA_LIMB 2, 10
    WA_LIMB 10, 12
    WA_LIMB 4, 14
    WA_LIMB 14, 16
    WA_LIMB 4, 18
    WA_LIMB 18, 20
    mov si, [wa_jsx]            ; the head
    mov di, [wa_jsy]
    call wa_fpix
    cmp word [wa_fv8], 40       ; big enough for a 2x2 head
    jb wa_femit
    inc si
    call wa_fpix
    dec di
    call wa_fpix
    dec si
    call wa_fpix
    jmp wa_femit
.out:
    pop di
    ret
; wa_femit - pass 3: the box swept with `repe scasw`, a row at a time. Each
; cell the limbs touched is cleared out of wa_fbuf, depth-tested once
; against its column's wall (resolved above) and plotted - the old
; wa_plotf inline, every array addressed off DI (the cell's place in
; wa_fbuf, + 2) by a constant displacement, the stamp to match held in DH,
; the inverse depth in SI, and the list's end in [wa_flp].
WA_FSTO equ wa_stamp - wa_fbuf - 2
WA_FMSO equ wa_fmask - wa_fbuf - 2
WA_FCUO equ wa_cur - wa_fbuf - 2
wa_femit:
    mov si, [wa_fiz]
    mov dh, [wa_frame]
    or dh, 0x80                 ; DH = a figure cell's stamp this frame
    mov ax, [wa_newp]
    add ax, [wa_newn]
    mov [wa_flp], ax
    mov bx, [wa_frow]
    mov bp, [wa_rowo2+bx]
    add bp, wa_fbuf             ; BP = the row's first cell in wa_fbuf
    mov ax, [wa_fbr]
    sub ax, bx
    shr ax, 1
    inc ax
    mov [wa_fnr], ax            ; rows
.row:
    mov di, bp
    add di, [wa_fbc]
    mov cx, [wa_fbw]
    xor ax, ax
    repe scasw                  ; (only a cell's even byte is ever set)
    jne .found
.nrow:
    add bp, [wa_w2]             ; (2W bytes: a row)
    dec word [wa_fnr]
    jnz .row
    mov ax, [wa_flp]
    sub ax, [wa_newp]
    mov [wa_newn], ax
    pop di
    ret
.found:                         ; DI = the cell's offset in wa_fbuf, + 2
    mov dl, [di-2]              ; DL = its sub-pixels, taken out of the
    mov byte [di-2], 0          ; scratch
    mov bx, di
    sub bx, bp                  ; BX = its column x 2, + 2
    cmp [wa_colz-2+bx], si
    ja .hid                     ; the wall there is nearer
    mov al, [di+WA_FSTO]
    cmp al, dh
    je .have                    ; a figure cell already: add the bits
    xor al, dh
    cmp al, 0x80
    je .listed                  ; a wall cell this frame: already listed
    lea ax, [di-2-wa_fbuf]      ; the cell, onto this frame's list
    mov bx, [wa_flp]
    mov [bx], ax
    inc bx
    inc bx
    mov [wa_flp], bx
    xor bx, bx
.listed:
    mov [di+WA_FSTO], dh
    jmp .put
.have:
    or dl, [di+WA_FMSO]
.put:
    mov [di+WA_FMSO], dl
    mov bl, dl                  ; (BH is 0: a column, or cleared)
    mov al, [wa_fglyph+bx]
    mov ah, [wa_fatt]
    mov [di+WA_FCUO], ax
.hid:
    xor ax, ax
    jcxz .nrow
    repe scasw
    jne .found
    jmp .nrow

; wa_fjl - wa_figure's joints: SI, DI = keyframes A and B at this facing.
; Each is A + (B - A) x q / 4 (q = [wa_fsub], rounded down as wa_blend's
; was; q = 3 is worked as B + (A - B) / 4, the same number), projected:
; x = ((lateral + fcx) fs8 >> 8) + W, y = hh - ((height - eye) fv8 >> 8).
; Eight loops, one per quarter and per multiply:
; - NARROW (fs8 and fv8 under 128: past ~1.6 m at 40 columns, most of the
;   time): 8-bit multiplies on sums regrouped so they stay in 16 bits -
;   K = fcx fs8 + 256 W split as 256 Khi + Klo, so x = ((lateral fs8 + Klo)
;   >> 8) + Khi; and E = eye fv8 + 256 hh + 255, so y = (E - height fv8)
;   >> 8. The same numbers, so the same pixels;
; - WIDE: the 16-bit multiplies, as before.
; Returns to wa_fjdone. Clobbers AX, BX, CX, DX, BP.
%macro WA_FBLEND 2              ; %1 = q, %2 = 0 lateral, 1 height
  %if %1 == 3
    mov al, [di+bx+%2]          ; (B + (A - B) / 4)
  %else
    mov al, [si+bx+%2]
  %endif
    cbw
  %if %1
    mov dx, ax
    %if %1 == 3
    mov al, [si+bx+%2]
    %else
    mov al, [di+bx+%2]
    %endif
    cbw
    sub ax, dx
    %if %1 != 2
    sar ax, 1
    %endif
    sar ax, 1
    add ax, dx
  %endif
%endmacro
%macro WA_FJ 2                  ; %1 = q, %2 = 1 narrow
.j%2%1:
    WA_FBLEND %1, 0             ; lateral
  %if %2
    imul cl
    add ax, [wa_fk]
    mov al, ah
    cbw
    add ax, bp
  %else
    add ax, [wa_fcx]
    imul word [wa_fs8]
    mov al, ah
    mov ah, dl
    add ax, [wa_w]
  %endif
    mov [wa_jsx+bx], ax
    WA_FBLEND %1, 1             ; height
  %if %2
    mul ch
    neg ax
    add ax, [wa_fe]
    mov al, ah
    cbw
  %else
    sub ax, [wa_eye]
    imul word [wa_fv8]
    mov al, ah
    mov ah, dl
    neg ax
    add ax, [wa_hh]
  %endif
    mov [wa_jsy+bx], ax
    inc bx
    inc bx
    cmp bx, WA_NJ*2
    jb .j%2%1
    jmp wa_fjdone
%endmacro
wa_fjl:
    ; STKBALANCE-OK: never called - wa_figure's continuation, JMPed to with
    ; wa_figure's DI on the stack; its table dispatch (`jmp ax`) and every
    ; joint block leave by `jmp wa_fjdone`, which pops it
    xor bx, bx
    mov bl, [wa_fsub]
    shl bx, 1
    mov ax, [wa_fs8]
    cmp ax, 128
    jae .wide
    mov dx, [wa_fv8]
    cmp dx, 128
    jae .wide
    mov cl, al
    mov ch, dl
    imul word [wa_fcx]          ; K = fcx fs8 + 256 W...
    mov bp, [wa_w]
    xchg bp, ax
    mov ah, al
    mov al, 0
    xchg bp, ax
    add ax, bp
    adc dx, 0
    mov [wa_fk], al             ; ...Klo
    mov byte [wa_fk+1], 0
    mov al, ah
    mov ah, dl
    mov bp, ax                  ; ...and Khi
    mov al, ch                  ; E = eye fv8 + 256 hh + 255 (mod 2^16: the
    xor ah, ah                  ; difference it ends in fits)
    mul word [wa_eye]
    mov dh, [wa_hh]
    mov dl, 255
    add ax, dx
    mov [wa_fe], ax
    add bx, 8
.wide:
    mov bx, [.tab+bx]
    xchg ax, bx
    xor bx, bx                  ; (BX: the joint x 2)
    jmp ax
.tab:
    dw .j00, .j01, .j02, .j03, .j10, .j11, .j12, .j13
    WA_FJ 0, 0
    WA_FJ 1, 0
    WA_FJ 2, 0
    WA_FJ 3, 0
    WA_FJ 0, 1
    WA_FJ 1, 1
    WA_FJ 2, 1
    WA_FJ 3, 1

; WA_FPIXI - SI = sub-column, DI = half-row: one sub-pixel into wa_fbuf,
; clipped (wa_fpix inline, for the clipped walk). Clobbers AX, BX, DX.
%macro WA_FPIXI 0
    cmp si, [wa_w2]
    jae %%out
    cmp di, WA_HR
    jae %%out
    mov bx, si
    shr bx, 1                   ; CF = the column's half
    mov bx, di
    rcl bx, 1
    and bx, 3                   ; BX = the quadrant
    mov dl, [wa_qbit+bx]
    mov bx, di
    shl bx, 1
    mov bx, [wa_hroff+bx]
    mov ax, si
    and al, 0xFE
    add bx, ax
    or [wa_fbuf+bx], dl
%%out:
%endmacro
wa_qbit:    db 1, 2, 4, 8

; wa_fpix - SI = sub-column, DI = half-row: one sub-pixel into wa_fbuf,
; clipped to the view (the head). Keeps SI and DI; clobbers AX, BX, DX.
wa_fpix:
    WA_FPIXI
    ret

; wa_fline - (CX,DX) to (AX,BX), sub-pixels: a limb into wa_fbuf. Clobbers
; AX, BX, CX, DX, SI, DI, BP.
;
; Drawn downward. On the FAST path - both ends' columns on the screen, the
; top end inside it, and the bottom end too unless the line is steep - the
; walk is a state machine: a block per quadrant of the cell the pen is in
; (row parity r, column parity c), each plotting its own bit, so no sub-pixel
; computes an address, a bit or a clip. A steep line running off the bottom
; is cut by its count. Anything else (a limb off the side or the top, or
; shallow and off the bottom: a figure at your shoulder) takes the slow walk,
; which clips each sub-pixel (wa_fpix).
wa_fline:
    cmp bx, dx
    jge .down
    xchg ax, cx
    xchg bx, dx
.down:                          ; (CX,DX) the top end, (AX,BX) the bottom
    mov si, [wa_w2]
    cmp cx, si                  ; (unsigned: a negative one is huge)
    jae .slow
    cmp ax, si
    jae .slow
    cmp dx, WA_HR
    jae .slow
    cmp bx, WA_HR
    jb .fast
    mov si, ax                  ; the bottom end is off the screen: fast
    sub si, cx                  ; only when steep, where the count cuts it
    jns .ab
    neg si
.ab:
    mov bp, bx
    sub bp, dx
    cmp si, bp
    jbe .fast
.slow:                          ; the same walk, each sub-pixel clipped
    mov si, cx                  ; SI, DI = the pen
    mov di, dx
    sub ax, cx                  ; AX = |dx|, [wa_lsx] its sign
    mov word [wa_lsx], 1
    jns .sxp
    neg ax
    mov word [wa_lsx], -1
.sxp:
    sub bx, dx                  ; BX = dy, >= 0
    cmp ax, bx
    jg .sx
    mov [wa_ldx], ax            ; steep: [wa_ldx] the minor, [wa_ldy] the
    mov [wa_ldy], bx            ; major
    mov cx, bx
    inc cx
    mov bp, bx
    shr bp, 1
.sy:
    WA_FPIXI
    dec cx
    jz .ret
    inc di
    cmp di, WA_HR
    jge .ret                    ; (below the view: nothing more to see)
    sub bp, [wa_ldx]
    jns .sy
    add bp, [wa_ldy]
    add si, [wa_lsx]
    jmp .sy
.sx:
    mov [wa_ldx], ax            ; shallow: [wa_ldx] the major, [wa_ldy] the
    mov [wa_ldy], bx            ; minor
    mov cx, ax
    inc cx
    mov bp, ax
    shr bp, 1
.sxl:
    WA_FPIXI
    dec cx
    jz .ret
    add si, [wa_lsx]
    sub bp, [wa_ldy]
    jns .sxl
    add bp, [wa_ldx]
    inc di
    cmp di, WA_HR
    jl .sxl
.ret:
    ret

.fast:
    mov bp, WA_HR-1
    sub bp, dx                  ; BP = the most half-rows a steep one steps
    jmp wa_flgo

; wa_flinef - wa_fline for a figure whose joints are ALL on the screen
; (wa_figure decides, once): every limb would take the fast walk, so its
; clip tests are skipped, and a steep one cannot run off the bottom - the
; cut is set out of reach. The same sub-pixels.
wa_flinef:
    cmp bx, dx
    jge .down
    xchg ax, cx
    xchg bx, dx
.down:
    mov bp, 0xFFFF              ; (no cut)
wa_flgo:
    sub ax, cx                  ; AX = x1 - x0
    sub bx, dx                  ; BX = y1 - y0, >= 0
    mov di, dx
    shl di, 1
    mov di, [wa_hroff+di]
    add di, wa_fbuf
    and dx, 1                   ; DX = (r x 2 + c) x 2, the state's entry
    shr cx, 1
    rcl dx, 1
    shl dx, 1
    shl cx, 1
    add di, cx                  ; DI = the start's cell in wa_fbuf
    or ax, ax
    jns .r
    neg ax                      ; leftward: the second half of each table
    add dx, 8
.r:
    mov si, dx
    cmp ax, bx
    jg .shallow
    mov dx, [wa_fl_ytab+si]     ; steep: a sub-pixel every half-row
    mov cx, bx
    cmp cx, bp
    jbe .yc
    mov cx, bp                  ; (off the bottom: stop at the edge)
.yc:
    inc cx                      ; CX = sub-pixels
    mov si, ax                  ; SI = the minor step...
    mov bp, bx
    shr bp, 1                   ; BP = the error, half the major...
    xchg bx, di                 ; BX = the cell, DI = the major
    mov ax, [wa_w2]             ; AX = a row's bytes (2W)
    jmp dx
.shallow:
    mov dx, [wa_fl_xtab+si]     ; shallow: a sub-pixel every sub-column
    mov cx, ax
    inc cx
    mov si, bx                  ; SI = the minor step (dy)
    mov bp, ax
    shr bp, 1
    xchg ax, di                 ; DI = the major (dx), AX = the cell
    xchg ax, bx                 ; BX = the cell
    mov ax, [wa_w2]
    jmp dx
; The fast walk's states. Registers: BX = the cell in wa_fbuf, CX =
; sub-pixels left, BP = the error, SI = the minor step, DI = the major, AX =
; a row's bytes. A block plots its quadrant's bit and moves the pen: a
; half-row down from a bottom quadrant is the next row's top (BX += AX), a
; sub-column right from a right quadrant is the next cell's left (BX += 2).
%macro WA_FYS 5                 ; steep: %1 R/L, %2 r, %3 c, %4 the state
wa_fy%1%2%3:                    ; after a sideways step too, %5 without
    or byte [bx], 1 << (%3 + 2*%2)
    dec cx
    jz wa_fy%1ret
    sub bp, si
  %if %2 == 0
    jns %5
  %else
    jns %%down
  %endif
    add bp, di
  %ifidn %1, R
    %if %3 == 1
    inc bx
    inc bx
    %endif
  %else
    %if %3 == 0
    dec bx
    dec bx
    %endif
  %endif
  %if %2 == 1
    add bx, ax
  %endif
    jmp %4
  %if %2 == 1
%%down:
    add bx, ax
    jmp %5
  %endif
%endmacro
%macro WA_FXS 5                 ; shallow: %4 the state after a step down
wa_fx%1%2%3:                    ; too, %5 without
    or byte [bx], 1 << (%3 + 2*%2)
    dec cx
    jz wa_fx%1ret
  %ifidn %1, R
    %if %3 == 1
    inc bx
    inc bx
    %endif
  %else
    %if %3 == 0
    dec bx
    dec bx
    %endif
  %endif
    sub bp, si
    jns %5
    add bp, di
  %if %2 == 1
    add bx, ax
  %endif
    jmp %4
%endmacro
wa_fyRret:
    ret
    WA_FYS R, 0, 0, wa_fyR11, wa_fyR10
    WA_FYS R, 0, 1, wa_fyR10, wa_fyR11
    WA_FYS R, 1, 0, wa_fyR01, wa_fyR00
    WA_FYS R, 1, 1, wa_fyR00, wa_fyR01
wa_fyLret:
    ret
    WA_FYS L, 0, 0, wa_fyL11, wa_fyL10
    WA_FYS L, 0, 1, wa_fyL10, wa_fyL11
    WA_FYS L, 1, 0, wa_fyL01, wa_fyL00
    WA_FYS L, 1, 1, wa_fyL00, wa_fyL01
wa_fxRret:
    ret
    WA_FXS R, 0, 0, wa_fxR11, wa_fxR01
    WA_FXS R, 0, 1, wa_fxR10, wa_fxR00
    WA_FXS R, 1, 0, wa_fxR01, wa_fxR11
    WA_FXS R, 1, 1, wa_fxR00, wa_fxR10
wa_fxLret:
    ret
    WA_FXS L, 0, 0, wa_fxL11, wa_fxL01
    WA_FXS L, 0, 1, wa_fxL10, wa_fxL00
    WA_FXS L, 1, 0, wa_fxL01, wa_fxL11
    WA_FXS L, 1, 1, wa_fxL00, wa_fxL10
wa_fl_ytab:                     ; by (r x 2 + c) x 2, leftward + 8
    dw wa_fyR00, wa_fyR01, wa_fyR10, wa_fyR11
    dw wa_fyL00, wa_fyL01, wa_fyL10, wa_fyL11
wa_fl_xtab:
    dw wa_fxR00, wa_fxR01, wa_fxR10, wa_fxR11
    dw wa_fxL00, wa_fxL01, wa_fxL10, wa_fxL11

; wa_marker - DI = a figure too far for limbs: a one-sub-column bar from
; head to feet, its attribute already chosen. The trigger's extents too.
wa_marker:
    mov ax, [wa_fcx]
    imul word [wa_fs8]
    mov al, ah
    mov ah, dl
    add ax, [wa_w]
    mov [di+F_PCX], ax
    mov si, ax                  ; SI = the sub-column
    mov ax, 112                 ; the head, 1.75 m
    sub ax, [wa_eye]
    imul word [wa_fv8]
    mov al, ah
    mov ah, dl
    neg ax
    add ax, [wa_hh]
    mov [di+F_PTOP], ax
    mov cx, ax                  ; CX = top half-row
    mov ax, [wa_eye]            ; the feet, the floor
    imul word [wa_fv8]
    mov al, ah
    mov ah, dl
    add ax, [wa_hh]
    mov [di+F_PBOT], ax
    mov [wa_mbot], ax
    mov word [di+F_PWH], 1
    cmp si, [wa_w2]
    jae .out                    ; (unsigned: off either side)
    mov bx, si
    and bx, 0xFFFE              ; BX = its column x 2: ONE wall depth for
    call wa_wallz               ; the whole bar
    mov ax, [wa_colz+bx]
    cmp ax, [wa_fiz]
    ja .out                     ; the wall there is nearer
    mov ax, [wa_mbot]
    cmp ax, WA_HR-1
    jle .bot
    mov ax, WA_HR-1
.bot:
    mov [wa_mbot], ax           ; the last half-row, clipped
    or cx, cx
    jns .top
    xor cx, cx
.top:
    and si, 1                   ; SI = the sub-column's half of the cell
    push di
    mov di, bx                  ; DI = the column x 2
.cell:                          ; a cell at a time, both of its half-rows
    cmp cx, [wa_mbot]           ; at once if both are in the bar
    jg .done
    mov bx, cx
    shl bx, 1
    mov bx, [wa_hroff+bx]
    add bx, di                  ; BX = the cell
    mov dl, 4                   ; a lower half-row: its lower quadrant
    inc cx
    test cl, 1
    jz .half                    ; (it was odd)
    mov dl, 1                   ; an upper one: and the lower too, if the
    cmp cx, [wa_mbot]           ; bar goes on
    jg .half
    mov dl, 5
    inc cx
.half:
    or si, si
    jz .put
    shl dl, 1                   ; the right-hand quadrants
.put:
    mov ah, [wa_fatt]
    call wa_plotf
    jmp .cell
.done:
    pop di
.out:
    ret

; --- the crosshair ----------------------------------------------------------
wa_cross:
    mov bx, [wa_w]              ; column W/2, as an offset: W
    add bx, [wa_rowo2+WA_ROWS]  ; row 12 (WA_ROWS/2 rows x 2 bytes in)
    mov al, '+'
    mov ah, [wa_at+A_CROSS]
    cmp byte [wa_mflash], 0
    je .put
    mov al, '*'
    mov ah, [wa_at+A_FLASH]
.put:
    mov dl, [wa_stamp+bx]
    and dl, 0x7F
    cmp dl, [wa_frame]
    je .over
    mov dl, [wa_frame]
    mov [wa_stamp+bx], dl
    call wa_list
.over:
    mov [wa_cur+bx], ax
    ret

; --- present ----------------------------------------------------------------
; Write this frame's cells that differ from the glass; blank last frame's
; cells this frame did not draw. Nothing else. Each list is walked two cells
; an iteration (the odd one first), which halves the loop's own cost.
%macro PNEW 0                   ; this frame's cell: written if it differs
    lodsw
    xchg bx, ax
    mov ax, [wa_cur+bx]
    cmp ax, [wa_vis+bx]
    je %%same
    mov [wa_vis+bx], ax
    mov [es:bx], ax
    inc bp
%%same:
%endmacro
%macro POLD 0                   ; last frame's: blanked unless drawn again
    lodsw
    xchg bx, ax
    mov al, [wa_stamp+bx]
    and al, 0x7F
    cmp al, dl
    je %%kept
    cmp word [wa_vis+bx], WA_BLANK
    je %%kept
    mov word [wa_vis+bx], WA_BLANK
    mov word [es:bx], WA_BLANK
    inc bp
%%kept:
%endmacro
wa_present:
    push es
    mov es, [wa_vseg]
    xor bp, bp                  ; writes, for the meter
    mov si, [wa_newp]
    mov cx, [wa_newn]
    shr cx, 1
    shr cx, 1                   ; pairs; CF = an odd one
    jnc .np
    PNEW
.np:
    jcxz .old
.new:
    PNEW
    PNEW
    loop .new
.old:
    mov si, [wa_oldp]
    mov cx, [wa_oldn]
    mov dl, [wa_frame]
    shr cx, 1
    shr cx, 1
    jnc .op
    POLD
.op:
    jcxz .swap
.o:
    POLD
    POLD
    loop .o
.swap:
    mov [wa_nwr], bp
    mov ax, [wa_newp]
    xchg ax, [wa_oldp]
    mov [wa_newp], ax
    mov ax, [wa_newn]
    mov [wa_oldn], ax
    pop es
    ret
