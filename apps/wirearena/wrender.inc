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
WA_VAR wa_fdone, WA_NFIG
WA_VAR wa_lx1, 2
WA_VAR wa_ly1, 2
WA_VAR wa_ldx, 2
WA_VAR wa_ldy, 2
WA_VAR wa_lsx, 2
WA_VAR wa_lsy, 2
WA_VAR wa_nwr, 2                ; video writes this frame
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

; wa_products - per distinct coordinate, (v - p) cos and (v - p) sin. All of
; them, every frame: doing it lazily per coordinate was measured SLOWER (19.5
; -> 19.0 fps at 40 columns) - nearly every coordinate is used, so the stamp
; tests were pure cost
wa_products:
    xor si, si                  ; value x 2
    xor di, di                  ; product x 4
.x:
    mov ax, [wa_xv+si]
    sub ax, [wa_px]
    push ax
    imul word [wa_cos]
    mov [wa_xc+di], ax
    mov [wa_xc+di+2], dx
    pop ax
    imul word [wa_sinv]
    mov [wa_xs+di], ax
    mov [wa_xs+di+2], dx
    add si, 2
    add di, 4
    cmp si, [wa_nxv2]
    jb .x
    xor si, si
    xor di, di
.y:
    mov ax, [wa_yv+si]
    sub ax, [wa_py]
    push ax
    imul word [wa_cos]
    mov [wa_yc+di], ax
    mov [wa_yc+di+2], dx
    pop ax
    imul word [wa_sinv]
    mov [wa_ys+di], ax
    mov [wa_ys+di+2], dx
    add si, 2
    add di, 4
    cmp si, [wa_nyv2]
    jb .y
    ret

; wa_node - BX = a node of the box tree (0 = none): front to back, while any
; column is open. A leaf is one box.
wa_node:
    or bx, bx
    jz .out
    cmp word [wa_left], 0
    je .out
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
; the player is outside of - at most two
wa_box:
    xor cl, cl                  ; CL = the faces we see: 1 S, 2 E, 4 N, 8 W
    mov ax, [wa_py]
    cmp ax, [si+2]
    jge .e
    or cl, 1
.e:
    mov ax, [wa_px]
    cmp ax, [si+4]
    jle .n
    or cl, 2
.n:
    mov ax, [wa_py]
    cmp ax, [si+6]
    jle .w
    or cl, 4
.w:
    mov ax, [wa_px]
    cmp ax, [si]
    jge .go
    or cl, 8
.go:
    mov [wa_bvis], cl           ; a face's END corner is drawn only when the
    mov ax, (1 << 8) | 0        ; next face round (S E N W) is NOT seen: a
    mov ch, 1                   ; corner two faces share is the second one's
    call .face                  ; START, and drawing both put `││` there
    mov ax, (2 << 8) | 1
    mov ch, 2
    call .face
    mov ax, (3 << 8) | 2
    mov ch, 4
    call .face
    mov ax, (0 << 8) | 3
    mov ch, 8
.face:                          ; AL/AH = corners, CH = this face's bit
    test [wa_bvis], ch
    jz .out
    mov byte [wa_endok], 1
    shl ch, 1                   ; the next face's bit (W wraps to S)
    test ch, 15
    jnz .nb
    mov ch, 1
.nb:
    test [wa_bvis], ch
    jz .last
    mov byte [wa_endok], 0
.last:
    mov bx, [wa_crow]           ; corner numbers -> vertex x 2
    xlatb
    xchg al, ah
    xlatb
    xchg al, ah
    jmp wa_face
.out:
    ret

; wa_face - AL = from vertex x 2, AH = to vertex x 2 (a face we see the front
; of): transform, and unless every column it could reach is already closed,
; project (clipping only when a vertex is outside the view) and step it.
wa_face:
    mov [wa_fv], ax
    mov bl, al
    xor bh, bh
    call wa_vert
    mov bl, [wa_fv+1]
    xor bh, bh
    call wa_vert
    mov bl, [wa_fv]
    xor bh, bh
    mov di, bx                  ; DI = v1 x 2, BX = v2 x 2
    mov bl, [wa_fv+1]
    mov al, [wa_vok+di]
    mov [wa_e1], al
    mov ah, [wa_vok+bx]
    and ah, [wa_endok]          ; (the end corner, only on a silhouette)
    mov [wa_e2], ah
    mov ah, [wa_vok+bx]
    and al, ah
    jz .clip
    mov ax, [wa_vpc+di]         ; both inside the view: the cache
    mov [wa_c1], ax
    mov ax, [wa_vpt+di]
    mov [wa_t1], ax
    mov ax, [wa_vpb+di]
    mov [wa_b1], ax
    mov ax, [wa_vpi+di]
    mov [wa_i1], ax
    mov ax, [wa_vpc+bx]
    mov [wa_c2], ax
    mov ax, [wa_vpt+bx]
    mov [wa_t2], ax
    mov ax, [wa_vpb+bx]
    mov [wa_b2], ax
    mov ax, [wa_vpi+bx]
    mov [wa_i2], ax
    jmp wa_span
.clip:
    push bx                     ; THE PRE-CHECK: the columns it could reach,
    call .reach                 ; from camera space alone - a vertex in view
    mov cx, ax                  ; is its own column, one beside the view is
    mov bx, di                  ; that edge, one behind is anywhere
    call .reach
    pop bx
    cmp ax, cx
    jle .lohi
    xchg ax, cx
.lohi:
    or ax, ax                   ; (-1: behind - anywhere)
    js .reachall
    or cx, cx
    js .reachall
    push di
    mov di, ax
    sub cx, ax
    inc cx
    shl di, 1
    add di, wa_cov
    xor ax, ax
    repne scasw
    pop di
    je .reachall                ; an open column: carry on
    ret                         ; every one closed: never clipped, never cut
.reachall:
    mov ax, [wa_vx+di]
    mov [wa_x1], ax
    mov ax, [wa_vz+di]
    mov [wa_z1], ax
    mov ax, [wa_vx+bx]
    mov [wa_x2], ax
    mov ax, [wa_vz+bx]
    mov [wa_z2], ax
    call wa_clip
    jc .gone
    mov ax, [wa_x1]
    mov bx, [wa_z1]
    call wa_proj
    mov [wa_c1], ax
    mov [wa_t1], bx
    mov [wa_b1], cx
    mov [wa_i1], dx
    mov ax, [wa_x2]
    mov bx, [wa_z2]
    call wa_proj
    mov [wa_c2], ax
    mov [wa_t2], bx
    mov [wa_b2], cx
    mov [wa_i2], dx
    jmp wa_span
.gone:
    ret
.reach:                         ; BX = vertex x 2 -> AX = a column, or -1
    cmp byte [wa_vok+bx], 0
    je .rout
    mov ax, [wa_vpc+bx]
    push cx
    mov cl, 4
    sar ax, cl
    pop cx
    or ax, ax
    jns .rpos
    xor ax, ax
.rpos:
    cmp ax, [wa_w]
    jl .rret
    mov ax, [wa_w]
    dec ax
.rret:
    ret
.rout:
    mov ax, -1
    cmp word [wa_vz+bx], WA_NEAR
    jl .rret                    ; behind: anywhere
    xor ax, ax
    cmp word [wa_vx+bx], 0
    jl .rret                    ; beside the view, left
    mov ax, [wa_w]
    dec ax                      ; ...or right
    ret

; wa_vert - BX = a vertex x 2: into camera space and, inside the view,
; projected - once a frame (wa_vst). Clobbers AX, BX, CX, DX, SI, DI.
wa_vert:
    mov al, [wa_frame]
    cmp [wa_vst+bx], al
    je .out
    mov [wa_vst+bx], al
    mov di, bx                  ; DI = vertex x 2
    mov al, [wa_vtx+bx]         ; x index x 4
    xor ah, ah
    mov si, ax
    mov al, [wa_vtx+bx+1]       ; y index x 4
    mov bp, ax
    mov ax, [wa_xc+si]          ; z = ((x-px) cos + (y-py) sin) >> 14
    mov dx, [wa_xc+si+2]
    add ax, [ds:wa_ys+bp]
    adc dx, [ds:wa_ys+bp+2]
    shl ax, 1
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    mov [wa_vz+di], dx
    mov cx, dx
    mov ax, [wa_xs+si]          ; x = ((x-px) sin - (y-py) cos) >> 14
    mov dx, [wa_xs+si+2]
    sub ax, [ds:wa_yc+bp]
    sbb dx, [ds:wa_yc+bp+2]
    shl ax, 1
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    mov [wa_vx+di], dx
    mov byte [wa_vok+di], 0
    cmp cx, WA_NEAR             ; projectable: z >= NEAR, |x| <= 8z (the
    jl .out                     ; guard band - the screen is |x| <= z)
    mov ax, dx
    or ax, ax
    jns .abs
    neg ax
.abs:
    mov bx, cx
    shl bx, 1
    shl bx, 1
    shl bx, 1
    cmp ax, bx
    jg .out
    mov byte [wa_vok+di], 1
    push di
    mov ax, dx
    mov bx, cx
    call wa_proj
    pop di
    mov [wa_vpc+di], ax
    mov [wa_vpt+di], bx
    mov [wa_vpb+di], cx
    mov [wa_vpi+di], dx
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
; band x >= -8z, x <= 8z. CF = 1: nothing left. Clobbers AX, BX, CX, DX, BP.
wa_clip:
    xor bp, bp
.plane:
    mov ax, [wa_x1]
    mov bx, [wa_z1]
    call .d
    mov [wa_d1], ax
    mov ax, [wa_x2]
    mov bx, [wa_z2]
    call .d
    mov [wa_d2], ax
    cmp word [wa_d1], 0
    jge .in1
    or ax, ax
    js .rej                     ; both outside
    mov cx, [wa_d1]             ; p1 += (p2 - p1) d1 / (d1 - d2)
    sub cx, ax
    mov ax, [wa_x2]
    sub ax, [wa_x1]
    imul word [wa_d1]
    idiv cx
    add [wa_x1], ax
    mov ax, [wa_z2]
    sub ax, [wa_z1]
    imul word [wa_d1]
    idiv cx
    add [wa_z1], ax
    jmp .next
.in1:
    or ax, ax
    jns .next
    mov cx, ax                  ; p2 += (p1 - p2) d2 / (d2 - d1)
    sub cx, [wa_d1]
    mov ax, [wa_x1]
    sub ax, [wa_x2]
    imul word [wa_d2]
    idiv cx
    add [wa_x2], ax
    mov ax, [wa_z1]
    sub ax, [wa_z2]
    imul word [wa_d2]
    idiv cx
    add [wa_z2], ax
.next:
    inc bp
    cmp bp, 3
    jb .plane
    cmp word [wa_z1], WA_NEAR   ; rounding can leave a unit short
    jge .z2
    mov word [wa_z1], WA_NEAR
.z2:
    cmp word [wa_z2], WA_NEAR
    jge .ok
    mov word [wa_z2], WA_NEAR
.ok:
    clc
    ret
.rej:
    stc
    ret
.d:                             ; AX = x, BX = z, BP = plane -> AX = d
    or bp, bp
    jnz .lr
    mov ax, bx
    sub ax, WA_NEAR
    ret
.lr:                            ; the GUARD BAND, |x| <= 8z, not the view
    push bx                     ; (|x| <= z): a vertex beside the view projects
    shl bx, 1                   ; to a column off the screen and the span
    shl bx, 1                   ; clamps it, so only a vertex far outside -
    shl bx, 1                   ; whose column would overflow - is clipped
    cmp bp, 1
    jne .r
    add ax, bx
    pop bx
    ret
.r:
    neg ax
    add ax, bx
    pop bx
    ret

; wa_proj - AX = x, BX = z (>= NEAR, |x| <= 8z) -> AX = column x16,
; BX = top and CX = bottom (quarter half-rows), DX = inverse depth
wa_proj:
    push si
    mov si, bx
    imul word [wa_k16]          ; the column, x16: NOT clamped - a vertex in
    idiv si                     ; the guard band lands off the screen and
    add ax, [wa_c16]            ; the span clamps to it. (The CENTRE, 8W -
                                ; not the scale, 8Wf: at 90 degrees they are
                                ; one number, and using the scale for both put
                                ; every wall six columns right at 75)
    push ax
    mov dx, 0x0007              ; 0x7FFF0 / z: 32767 at the near plane
    mov ax, 0xFFF0
    div si
    mov si, ax                  ; SI = inverse depth (2^19 / z)
    mov ax, [wa_numt]           ; top = hq - numt / z = hq - (numt x iz) >> 19:
    imul si                     ; a multiply where a divide was
    push cx
    mov cl, 3
    sar dx, cl
    mov bx, [wa_hq]
    sub bx, dx
    mov ax, [wa_numb]
    imul si
    sar dx, cl
    pop cx
    mov cx, [wa_hq]
    add cx, dx
    mov dx, si
    pop ax
    pop si
    ret

; --- spans --------------------------------------------------------------
; The hot loop of a frame. Plotting is INLINE (WPLOT): DL = the frame's
; stamp and DI = the list's write pointer stay in registers for a whole
; span.
%macro WPLOT 0                  ; BX = cell, AX = char|attr; first one wins
    cmp [wa_stamp+bx], dl
    je %%skip
    mov [wa_stamp+bx], dl
    mov [di], bx
    inc di
    inc di
    mov [wa_cur+bx], ax
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
    call wa_vedge
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
    call wa_vedge
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
    mul word [wa_fs]            ; x off: BX:DI:CX
    mov cx, ax
    mov di, dx
    xor bx, bx
    or bp, bp
    jz .e3
    mov ax, bp
    mul word [wa_fs]
    add di, ax
    adc bx, dx
.e3:
    shr bx, 1                   ; / 16
    rcr di, 1
    rcr cx, 1
    shr bx, 1
    rcr di, 1
    rcr cx, 1
    shr bx, 1
    rcr di, 1
    rcr cx, 1
    shr bx, 1
    rcr di, 1
    rcr cx, 1
    pop ax                      ; the sign onto both
    xor cx, ax
    xor di, ax
    sub cx, ax
    sbb di, ax
    xor si, ax
    xor bp, ax
    sub si, ax
    sbb bp, ax
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
    mov [di], bx
    inc di
    inc di
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
    mov [di], bx
    inc di
    inc di
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
%%shut:
    inc word [wa_ncl]
    jmp %%step
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

; wa_vedge - BX = top, AX = bottom (half-rows), SI = column x 2: `│` between
; them, the cell stepped by a row. Keeps SI, DI and DL; clobbers AX, BX, CX.
wa_vedge:
    sar ax, 1                   ; the bottom's row: stop before it
    cmp ax, WA_ROWS
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
    jle .out
    shl bx, 1
    mov bx, [wa_rowo2+bx]
    add bx, si
    mov al, 0xB3
    mov ah, [wa_eatt]
.row:
    WPLOT
    add bx, [wa_rowo2+2]
    loop .row
.out:
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
    mov di, wa_figs
    xor bx, bx
.proj:
    mov word [di+F_PZ], 0
    mov byte [wa_fdone+bx], 1
    push bx
    push di
    mov ax, [di+F_X]
    mov bx, [di+F_Y]
    call wa_xform
    pop di
    pop bx
    push bx
    shl bx, 1
    mov [wa_fxs+bx], ax
    mov [wa_fzs+bx], dx
    pop bx
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
    mov byte [wa_fdone+bx], 0
.nxt:
    add di, F_SIZE
    inc bx
    cmp bx, WA_NFIG
    jb .proj
.pick:                          ; far to near: the largest z not yet drawn
    xor dx, dx
    mov cx, -1
    xor bx, bx
.scan:
    cmp byte [wa_fdone+bx], 0
    jne .sn
    push bx
    shl bx, 1
    mov ax, [wa_fzs+bx]
    pop bx
    cmp ax, dx
    jle .sn
    mov dx, ax
    mov cx, bx
.sn:
    inc bx
    cmp bx, WA_NFIG
    jb .scan
    cmp cx, -1
    je .done
    mov bx, cx
    mov byte [wa_fdone+bx], 1
    mov ax, F_SIZE
    mul cx
    add ax, wa_figs
    mov di, ax
    shl bx, 1
    mov ax, [wa_fxs+bx]
    mov dx, [wa_fzs+bx]
    call wa_figure
    jmp .pick
.done:
    ret

; wa_figure - DI = a figure, AX = its camera x, DX = its z
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
    mov cx, WA_NJ*2
    mul cx
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
    push cx
    mov cl, [di+F_ANIM]
    xor ch, ch
    add ax, cx
    mov cx, WA_FRAMESZ
    mul cx
    add ax, wa_pose
    add ax, bx
    mov [wa_pa], ax
    pop ax
    mov cl, [di+F_ANIM]
    xor ch, ch
    add ax, cx
    mov cx, WA_FRAMESZ
    mul cx
    add ax, wa_pose
    add ax, bx
    mov [wa_pb], ax
    push di
    xor bx, bx                  ; joints
.joint:
    mov si, [wa_pa]
    mov di, [wa_pb]
    mov al, [si+bx]             ; lateral, blended
    cbw
    mov cx, ax
    mov al, [di+bx]
    cbw
    call wa_blend
    add ax, [wa_fcx]
    imul word [wa_fs8]
    mov al, ah
    mov ah, dl
    add ax, [wa_w]
    mov [wa_jsx+bx], ax
    mov al, [si+bx+1]           ; height, blended
    cbw
    mov cx, ax
    mov al, [di+bx+1]
    cbw
    call wa_blend
    sub ax, [wa_eye]
    imul word [wa_fv8]
    mov al, ah
    mov ah, dl
    neg ax
    add ax, [wa_hh]
    mov [wa_jsy+bx], ax
    add bx, 2
    cmp bx, WA_NJ*2
    jb .joint
    pop di
    call wa_figcols             ; the walls' depth under the figure
    mov si, wa_limbs
.limb:
    lodsw
    cmp al, 0xFF
    je .head
    xor bx, bx
    mov bl, al
    mov cx, [wa_jsx+bx]
    mov dx, [wa_jsy+bx]
    mov bl, ah
    mov ax, [wa_jsx+bx]
    mov bx, [wa_jsy+bx]
    push si
    call wa_line
    pop si
    jmp .limb
.head:
    push di
    mov si, [wa_jsx]
    mov di, [wa_jsy]
    call wa_fplot
    cmp word [wa_fv8], 40       ; big enough for a 2x2 head
    jb .rec
    inc si
    call wa_fplot
    dec di
    call wa_fplot
    dec si
    call wa_fplot
.rec:
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
    ret

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
    push cx
    mov bx, si
    mov dx, si
    call wa_colsz               ; the wall's depth in its one column
    pop cx
    push di
    mov di, cx
.bar:
    call wa_fplot               ; one sub-column: a thin mark, as a stick
    inc di                      ; figure that far would be
    cmp di, [wa_mbot]
    jle .bar
    pop di
    ret

; wa_figcols - the columns the figure's joints span (sub-columns / 2,
; clamped to the screen): their wall depth, before any limb is plotted
wa_figcols:
    push di
    mov si, wa_jsx
    mov cx, WA_NJ
    mov bx, 0x7FFF              ; BX = min, DX = max sub-column
    mov dx, 0x8000
.mm:
    lodsw
    cmp ax, bx
    jge .a
    mov bx, ax
.a:
    cmp ax, dx
    jle .b
    mov dx, ax
.b:
    loop .mm
    inc dx                      ; (the 2x2 head reaches one further)
    call wa_colsz
    pop di
    ret

; wa_colsz - BX..DX = sub-columns: wall depth for their columns
wa_colsz:
    sar bx, 1
    sar dx, 1
    or bx, bx
    jns .l
    xor bx, bx
.l:
    mov ax, [wa_w]
    dec ax
    cmp dx, ax
    jle .r
    mov dx, ax
.r:
    cmp bx, dx
    jg .out
    shl bx, 1
    shl dx, 1
.c:
    call wa_wallz
    inc bx
    inc bx
    cmp bx, dx
    jbe .c
.out:
    ret

; the limbs, as byte offsets into wa_jsx/wa_jsy (joint x 2)
wa_limbs:
    db 2, 4,  2, 6,  6, 8,  2, 10,  10, 12
    db 4, 14,  14, 16,  4, 18,  18, 20
    db 0xFF, 0xFF

; wa_blend - CX = keyframe A's value, AX = B's -> AX = A + (B - A) sub / 4
wa_blend:
    sub ax, cx
    push dx
    xor dx, dx
    test byte [wa_fsub], 1
    jz .two
    add dx, ax
.two:
    test byte [wa_fsub], 2
    jz .sum
    add dx, ax
    add dx, ax
.sum:
    sar dx, 1
    sar dx, 1
    mov ax, dx
    add ax, cx
    pop dx
    ret

; FPLOT - SI = sub-column, DI = half-row: one figure sub-pixel, inline (the
; call, four pushes and four pops it used to be were most of a limb's cost).
; Clobbers AX, BX, CX, DX.
%macro FPLOT 0
    cmp si, [wa_w2]             ; unsigned: a negative x is huge
    jae %%out
    cmp di, WA_HR
    jae %%out
    mov ax, si
    and ax, 0xFFFE              ; the column x 2
    mov bx, ax
    mov cx, [wa_fiz]
    cmp [wa_colz+bx], cx
    ja %%out                    ; the wall is nearer
    mov bx, di
    shl bx, 1
    add ax, [wa_hroff+bx]
    mov bx, ax                  ; BX = cell offset
    mov cx, si
    and cl, 1
    mov ax, di
    and al, 1
    shl al, 1
    or cl, al                   ; CL = the quadrant
    mov dl, 1
    shl dl, cl
    mov ah, [wa_fatt]
    call wa_plotf
%%out:
%endmacro

; wa_line - (CX,DX) to (AX,BX), sub-pixels: Bresenham, FPLOT inline
wa_line:
    push bp
    push di
    mov [wa_lx1], ax
    mov [wa_ly1], bx
    mov si, cx
    mov di, dx
    sub ax, cx                  ; dx = |x1 - x0|, sx
    mov word [wa_lsx], 1
    jns .xp
    neg ax
    mov word [wa_lsx], -1
.xp:
    mov [wa_ldx], ax
    sub bx, dx                  ; dy = -|y1 - y0|, sy
    mov word [wa_lsy], 1
    jns .yp
    neg bx
    mov word [wa_lsy], -1
.yp:
    neg bx
    mov [wa_ldy], bx
    mov bp, ax
    add bp, bx                  ; err
.step:
    FPLOT
    cmp si, [wa_lx1]
    jne .go
    cmp di, [wa_ly1]
    je .out
.go:
    mov ax, bp
    shl ax, 1
    cmp ax, [wa_ldy]
    jl .y
    add bp, [wa_ldy]
    add si, [wa_lsx]
.y:
    cmp ax, [wa_ldx]
    jg .step
    add bp, [wa_ldx]
    add di, [wa_lsy]
    jmp .step
.out:
    pop di
    pop bp
    ret

; wa_fplot - SI = sub-column, DI = half-row: one figure sub-pixel, clipped
; to the view and depth-tested against its column's wall. Keeps every
; register.
wa_fplot:
    push ax
    push bx
    push cx
    push dx
    or si, si
    js .out
    mov ax, [wa_w]
    shl ax, 1
    cmp si, ax
    jge .out
    or di, di
    js .out
    cmp di, WA_HR
    jge .out
    mov ax, si
    and ax, 0xFFFE              ; the column x 2: its wa_colz word, and its
    mov bx, ax                  ; share of the cell offset
    mov cx, [wa_colz+bx]
    cmp cx, [wa_fiz]
    ja .out                     ; the wall is nearer
    mov bx, di
    shl bx, 1
    add ax, [wa_hroff+bx]
    mov bx, ax                  ; BX = cell offset
    mov cx, si
    and cl, 1
    mov ax, di
    and al, 1
    shl al, 1
    or cl, al                   ; CL = 0..3, the quadrant
    mov dl, 1
    shl dl, cl
    mov ah, [wa_fatt]
    call wa_plotf
.out:
    pop dx
    pop cx
    pop bx
    pop ax
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
; cells this frame did not draw. Nothing else.
wa_present:
    push es
    mov es, [wa_vseg]
    xor bp, bp                  ; writes, for the meter
    mov si, [wa_newp]
    mov cx, [wa_newn]
    shr cx, 1
    jcxz .old
.new:
    lodsw
    xchg bx, ax
    mov ax, [wa_cur+bx]
    cmp ax, [wa_vis+bx]
    je .same
    mov [wa_vis+bx], ax
    mov [es:bx], ax
    inc bp
.same:
    loop .new
.old:
    mov si, [wa_oldp]
    mov cx, [wa_oldn]
    shr cx, 1
    jcxz .swap
    mov dl, [wa_frame]
    mov dh, 0                   ; (DX is not a word here; DL alone is read)
.o:
    lodsw
    xchg bx, ax
    mov al, [wa_stamp+bx]
    and al, 0x7F
    cmp al, dl
    je .kept
    cmp word [wa_vis+bx], WA_BLANK
    je .kept
    mov word [wa_vis+bx], WA_BLANK
    mov word [es:bx], WA_BLANK
    inc bp
.kept:
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
