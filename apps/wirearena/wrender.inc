; WireArena's renderer (docs/plans/MULTIPLAYER-FPS-PLAN.md section 4).
;
; 1. Every visible wall face is transformed, clipped to the near plane and
;    the 90-degree frustum, projected, and rasterised into a PER-COLUMN
;    buffer: the nearest face's inverse depth, top and bottom. A face's top,
;    bottom and inverse depth are all linear in screen x, so a column is
;    three adds. Nearest wins, so the order faces arrive in does not matter.
; 2. From that buffer, wall EDGES only, in thin glyphs: a top and a bottom
;    per column at half-row precision (`─` upper half, `_` lower), `/` and
;    `\` where an edge steps more than a half-row between columns, `│`
;    where the nearest face changes. Black everywhere else.
; 3. Figures, far to near, as limb lines at 2x2 SUB-CELL precision, each
;    sub-pixel depth-tested against its column's wall; a cell's four bits
;    pick a solid block glyph. A figure cell replaces a wall cell.
; 4. The crosshair.
; Every cell drawn this frame is stamped and listed; wa_present writes the
; ones that differ from what the glass holds and blanks last frame's cells
; nobody drew this time. Nothing else is touched, so a still view costs no
; video writes at all.

%macro WR_BSS 0
WA_VAR wa_colz, WA_MAXW*2       ; nearest face's inverse depth (0 = none)
WA_VAR wa_colt, WA_MAXW*2       ; its top, quarter half-rows
WA_VAR wa_colb, WA_MAXW*2       ; its bottom
WA_VAR wa_colsg, WA_MAXW        ; which face
WA_VAR wa_at, 6                 ; this frame's attributes (A_*)
WA_VAR wa_cos, 2
WA_VAR wa_sinv, 2
WA_VAR wa_cang, 2
WA_VAR wa_hq, 2                 ; horizon, quarter half-rows
WA_VAR wa_hh, 2                 ; horizon, half-rows
WA_VAR wa_numt, 2
WA_VAR wa_numb, 2
WA_VAR wa_cvx, 8                ; a box's four corners, camera space
WA_VAR wa_cvz, 8
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
WA_VAR wa_segid, 1
WA_VAR wa_bfaces, 1
WA_VAR wa_cmask, 1
WA_VAR wa_pseg, 1
WA_VAR wa_pht, 2
WA_VAR wa_phb, 2
WA_VAR wa_eatt, 1               ; the edge glyphs' attribute this column
WA_VAR wa_ht, 2
WA_VAR wa_hroff, WA_HR*2         ; a half-row's cell row offset
WA_VAR wa_hb, 2
WA_VAR wa_cs, 2
WA_VAR wa_n, 2
WA_VAR wa_fs, 2
WA_VAR wa_dc, 2
WA_VAR wa_st, 2
WA_VAR wa_sb, 2
WA_VAR wa_slo, 2
WA_VAR wa_shi, 2
WA_VAR wa_vt, 2
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
    mov cx, WA_CELLS/2
    rep stosw
    mov byte [wa_frame], 1
.stamped:
    mov word [wa_newn], 0
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
    mov cx, WA_KYQ
    imul cx
    mov [wa_numt], ax
    mov ax, [wa_eye]
    imul cx
    mov [wa_numb], ax
    mov di, wa_colz
    xor ax, ax
    mov cx, [wa_w]
    rep stosw
    mov [wa_segid], al
    mov si, wa_room
    mov al, 15
    call wa_corners
    mov bx, (3 << 8) | 0        ; the room's walls face IN: clockwise
    call wa_face
    mov bx, (2 << 8) | 3
    call wa_face
    mov bx, (1 << 8) | 2
    call wa_face
    mov bx, (0 << 8) | 1
    call wa_face
    mov si, wa_boxes
    mov cx, WA_NBOX
.box:
    push cx
    call wa_box
    pop cx
    add si, 8
    loop .box
    call wa_edges
    call wa_figures
    call wa_cross
    ret

wa_room:    dw WA_ROOM_X0, WA_ROOM_Y0, WA_ROOM_X1, WA_ROOM_Y1

; wa_box - SI = a box: its faces the player is outside of - at most two -
; and only the corners those faces use are transformed. Keeps SI.
wa_box:
    xor al, al                  ; AL = faces: 1 S, 2 E, 4 N, 8 W
    mov dx, [wa_py]
    cmp dx, [si+2]
    jge .e
    or al, 1
.e:
    mov dx, [wa_px]
    cmp dx, [si+4]
    jle .n
    or al, 2
.n:
    mov dx, [wa_py]
    cmp dx, [si+6]
    jle .w
    or al, 4
.w:
    mov dx, [wa_px]
    cmp dx, [si]
    jge .faces
    or al, 8
.faces:
    mov [wa_bfaces], al
    mov bl, al                  ; corners: S = 0,1  E = 1,2  N = 2,3  W = 3,0
    mov ah, al                  ; = faces | faces rotated left by one
    shl ah, 1
    test ah, 16
    jz .rot
    or ah, 1
.rot:
    or al, ah
    and al, 15
    call wa_corners
    test byte [wa_bfaces], 1
    jz .fe
    mov bx, (1 << 8) | 0        ; south, west to east
    call wa_face
.fe:
    test byte [wa_bfaces], 2
    jz .fn
    mov bx, (2 << 8) | 1        ; east
    call wa_face
.fn:
    test byte [wa_bfaces], 4
    jz .fw
    mov bx, (3 << 8) | 2        ; north
    call wa_face
.fw:
    test byte [wa_bfaces], 8
    jz .out
    mov bx, (0 << 8) | 3        ; west
    call wa_face
.out:
    ret

; wa_corners - SI = x0, y0, x1, y1, AL = which corners (bit n = corner n,
; counter-clockwise from (x0, y0)): those into camera space. Keeps SI.
wa_corners:
    mov [wa_cmask], al
    xor bp, bp                  ; corner x 2
.c:
    shr byte [wa_cmask], 1
    jnc .skip
    mov ax, [si]                ; x: x0 for corners 0 and 3, else x1
    cmp bp, 2
    je .x1
    cmp bp, 4
    jne .xy
.x1:
    mov ax, [si+4]
.xy:
    mov bx, [si+2]              ; y: y0 for corners 0 and 1, else y1
    cmp bp, 4
    jb .cv
    mov bx, [si+6]
.cv:
    push si
    push bp
    call wa_xform
    pop bp
    pop si
    mov [ds:wa_cvx+bp], ax      ; (BP addresses SS by default: SS != DS)
    mov [ds:wa_cvz+bp], dx
.skip:
    inc bp
    inc bp
    cmp bp, 8
    jb .c
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

; wa_face - BL = from corner, BH = to corner: clip, project, rasterise.
; Keeps SI. The face's id advances whether it was drawn or not.
wa_face:
    push si
    mov al, bl
    xor ah, ah
    shl ax, 1
    mov di, ax
    mov ax, [wa_cvx+di]
    mov [wa_x1], ax
    mov ax, [wa_cvz+di]
    mov [wa_z1], ax
    mov al, bh
    xor ah, ah
    shl ax, 1
    mov di, ax
    mov ax, [wa_cvx+di]
    mov [wa_x2], ax
    mov ax, [wa_cvz+di]
    mov [wa_z2], ax
    call wa_clip
    jc .out
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
    call wa_raster
.out:
    inc byte [wa_segid]
    pop si
    ret

; wa_clip - the segment (x1,z1)-(x2,z2) against z >= NEAR, x >= -z and
; x <= z. CF = 1: nothing left. Clobbers AX, BX, CX, DX, BP.
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
.lr:
    cmp bp, 1
    jne .r
    add ax, bx
    ret
.r:
    neg ax
    add ax, bx
    ret

; wa_proj - AX = x, BX = z (>= NEAR, |x| <= z) -> AX = column x16,
; BX = top and CX = bottom (quarter half-rows), DX = inverse depth
wa_proj:
    push si
    mov si, bx
    imul word [wa_k16]
    idiv si
    add ax, [wa_k16]
    jns .lo
    xor ax, ax
.lo:
    mov dx, [wa_k16]
    shl dx, 1
    cmp ax, dx
    jle .hi
    mov ax, dx
.hi:
    push ax
    mov ax, [wa_numt]
    cwd
    idiv si
    mov bx, [wa_hq]
    sub bx, ax
    mov ax, [wa_numb]
    cwd
    idiv si
    mov cx, [wa_hq]
    add cx, ax
    mov dx, 0x0007              ; 0x7FFF0 / z: 32767 at the near plane
    mov ax, 0xFFF0
    div si
    mov dx, ax
    pop ax
    pop si
    ret

; wa_raster - the projected face (c1,t1,b1,i1)-(c2,t2,b2,i2) into the
; column buffer, nearest wins. c1 >= c2 is a face seen from behind.
wa_raster:
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
    cmp dx, si
    jle .some
    ret
.some:
    mov [wa_cs], dx
    sub si, dx
    inc si
    mov [wa_n], si
    mov ax, dx
    shl ax, cl
    add ax, 8
    sub ax, [wa_c1]
    mov [wa_fs], ax             ; 0..15: first centre past c1, x16
    mov ax, bx
    sub ax, [wa_c1]
    mov [wa_dc], ax
    xor ax, ax
    mov [wa_st], ax
    mov [wa_sb], ax
    mov [wa_slo], ax
    mov [wa_shi], ax
    cmp word [wa_n], 1
    je .start
    mov ax, [wa_t2]             ; per-column steps: top and bottom 13.3
    sub ax, [wa_t1]             ; (x8, not x16: a wall at the near plane
    mov cx, 128                 ; spans ~2,300 and the step must fit 16 bits
                                ; over the 17 col16 units a 2-column face has)
    imul cx
    idiv word [wa_dc]
    mov [wa_st], ax
    mov ax, [wa_b2]
    sub ax, [wa_b1]
    imul cx
    idiv word [wa_dc]
    mov [wa_sb], ax
    mov ax, [wa_i2]             ; ...and inverse depth, 16.16
    sub ax, [wa_i1]
    pushf
    jns .pos
    neg ax
.pos:
    mov cx, 16
    mul cx
    div word [wa_dc]
    mov bx, ax
    xor ax, ax
    div word [wa_dc]
    popf
    jns .stp
    neg ax
    adc bx, 0
    neg bx
.stp:
    mov [wa_slo], ax
    mov [wa_shi], bx
.start:
    mov cl, 3
    mov ax, [wa_st]             ; start values at the first column's centre
    imul word [wa_fs]
    call .sar4
    mov bx, [wa_t1]
    shl bx, cl
    add ax, bx
    mov [wa_vt], ax
    mov ax, [wa_sb]
    imul word [wa_fs]
    call .sar4
    mov bx, [wa_b1]
    shl bx, cl
    add ax, bx
    mov [wa_vb], ax
    mov ax, [wa_shi]
    imul word [wa_fs]
    call .sar4
    add ax, [wa_i1]
    mov dx, ax                  ; DX = inverse depth, integer half
    mov word [wa_vil], 0x8000   ; ...and its fraction
    mov bx, [wa_vt]             ; BX = top, CX = bottom (13.3, stored raw:
    mov cx, [wa_vb]             ; wa_edges rounds them)
    mov di, [wa_cs]
    mov si, di
    shl si, 1
    mov bp, [wa_n]
.col:
    cmp dx, [wa_colz+si]
    jbe .behind
    mov [wa_colz+si], dx
    mov [wa_colt+si], bx
    mov [wa_colb+si], cx
    mov al, [wa_segid]
    mov [wa_colsg+di], al
.behind:
    add bx, [wa_st]
    add cx, [wa_sb]
    mov ax, [wa_slo]
    add [wa_vil], ax
    adc dx, [wa_shi]
    inc si
    inc si
    inc di
    dec bp
    jnz .col
    ret
.sar4:                          ; DX:AX >>= 4 (signed) -> AX
    sar dx, 1
    rcr ax, 1
    sar dx, 1
    rcr ax, 1
    sar dx, 1
    rcr ax, 1
    sar dx, 1
    rcr ax, 1
    ret

; --- edges ------------------------------------------------------------------
; The hot loop of a frame: two glyphs a column, more where an edge steps or
; a face changes. Plotting is INLINE (WPLOT): DL = the frame's stamp and DI
; = the list's write pointer stay in registers for the whole pass - the
; first version called four levels deep for every cell and spent 42% of the
; frame doing it.
%macro WPLOT 0                  ; BX = cell, AX = char|attr; first one wins
    cmp [wa_stamp+bx], dl
    je %%skip
    mov [wa_stamp+bx], dl
    mov [di], bx
    inc di
    inc di
    shl bx, 1
    mov [wa_cur+bx], ax
%%skip:
%endmacro

wa_edges:
    mov dl, [wa_frame]
    mov di, [wa_newp]
    xor si, si                  ; column x 2
    mov byte [wa_pseg], 0xFF
.col:
    mov ax, [wa_colz+si]
    or ax, ax
    jnz .wall
    mov byte [wa_pseg], 0xFF
    jmp .next
.wall:
    mov bl, [wa_at+A_FAR]       ; dimmer with distance
    cmp ax, 682                 ; nearer than 12 m
    jb .att
    mov bl, [wa_at+A_MID]
    cmp ax, 2048                ; nearer than 4 m
    jb .att
    mov bl, [wa_at+A_NEAR]
.att:
    mov [wa_eatt], bl
    mov ah, bl
    mov cl, 5
    mov bp, si
    shr bp, 1                   ; BP = column
    mov bx, [wa_colt+si]        ; 13.3 quarter half-rows -> half-rows
    add bx, 16
    sar bx, cl
    mov [wa_ht], bx
    cmp bx, WA_HR
    jae .tdone                  ; (negative is huge, unsigned: off too)
    mov al, 0xC4                ; upper half: the middle line
    test bl, 1
    jz .tg
    mov al, '_'                 ; lower half: the bottom line
.tg:
    shl bx, 1
    mov bx, [wa_hroff+bx]
    add bx, bp
    WPLOT
.tdone:
    mov ah, [wa_eatt]
    mov bx, [wa_colb+si]
    add bx, 16
    sar bx, cl
    mov [wa_hb], bx
    cmp bx, WA_HR
    jae .bdone
    mov al, 0xC4
    test bl, 1
    jz .bg
    mov al, '_'
.bg:
    shl bx, 1
    mov bx, [wa_hroff+bx]
    add bx, bp
    WPLOT
.bdone:
    mov bx, si
    shr bx, 1
    mov al, [wa_colsg+bx]
    cmp al, [wa_pseg]
    jne .corner
    mov ax, [wa_ht]             ; the same face: fill a steep step
    mov cx, [wa_pht]
    mov bx, ax
    sub bx, cx
    inc bx                      ; -1..+1 -> 0..2: no fill
    cmp bx, 3
    jb .bslope
    call .slope
.bslope:
    mov ax, [wa_hb]
    mov cx, [wa_phb]
    mov bx, ax
    sub bx, cx
    inc bx
    cmp bx, 3
    jb .keep
    call .slope
    jmp .keep
.corner:
    cmp byte [wa_pseg], 0xFF
    je .keep
    mov ax, [wa_colz+si]        ; the face changed: a vertical edge on the
    cmp ax, [wa_colz+si-2]      ; NEARER of the two columns
    jae .here
    dec si
    dec si
    mov cl, 5
    mov ax, [wa_colt+si]
    add ax, 16
    sar ax, cl
    mov bx, ax
    mov ax, [wa_colb+si]
    add ax, 16
    sar ax, cl
    call .vedge
    inc si
    inc si
    jmp .keep
.here:
    mov bx, [wa_ht]
    mov ax, [wa_hb]
    call .vedge
.keep:
    mov ax, [wa_ht]
    mov [wa_pht], ax
    mov ax, [wa_hb]
    mov [wa_phb], ax
    mov bx, si
    shr bx, 1
    mov al, [wa_colsg+bx]
    mov [wa_pseg], al
.next:
    inc si
    inc si
    mov ax, si
    shr ax, 1
    cmp ax, [wa_w]
    jb .col
    sub di, [wa_newp]
    mov [wa_newn], di
    ret

; AX = this column's edge, CX = the last column's (half-rows): a step of
; two half-rows or more is filled down this column, `\` falling to the
; right and `/` rising. Clobbers AX, BX, CX, BP.
.slope:
    mov bx, ax
    sub bx, cx
    jns .sabs
    neg bx
.sabs:
    cmp bx, 2
    jb .sout
    mov bp, ('\' << 8)
    cmp ax, cx
    jg .fall
    mov bp, ('/' << 8)
    xchg ax, cx                 ; AX = the lower edge, CX = the higher
.fall:
    inc cx                      ; half-rows CX+1 .. AX-1, as rows
    sar cx, 1
    dec ax
    sar ax, 1
    jns .srow
    ret
.srow:
    cmp cx, ax
    jg .sout
    cmp cx, WA_ROWS
    jae .snext                  ; (negative rows skipped too)
    push ax
    push cx
    mov bx, cx
    shl bx, 1
    mov bx, [wa_rowoff+bx]
    mov cx, si
    shr cx, 1
    add bx, cx
    mov ax, bp
    mov al, ah
    mov ah, [wa_eatt]
    WPLOT
    pop cx
    pop ax
.snext:
    inc cx
    jmp .srow
.sout:
    ret

; BX = top, AX = bottom (half-rows), SI = column x 2: `│` between them.
; Clobbers AX, BX, CX, BP.
.vedge:
    mov bp, ax
    sar bp, 1                   ; BP = the bottom's row (stop before it)
    mov cx, bx
    sar cx, 1
    inc cx                      ; CX = the row under the top's
    jns .vrow
    xor cx, cx
.vrow:
    cmp cx, bp
    jge .vout
    cmp cx, WA_ROWS
    jge .vout
    mov bx, cx
    shl bx, 1
    mov bx, [wa_rowoff+bx]
    mov ax, si
    shr ax, 1
    add bx, ax
    mov al, 0xB3
    mov ah, [wa_eatt]
    WPLOT
    inc cx
    jmp .vrow
.vout:
    ret

wa_list:                        ; BX = cell, onto this frame's list
    push di
    mov di, [wa_newp]
    add di, [wa_newn]
    mov [di], bx
    add word [wa_newn], 2
    pop di
    ret

; wa_plotf - BX = cell, DL = sub-cell bit(s), AH = attribute: a figure's
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
    push bx
    shl bx, 1
    mov [wa_cur+bx], ax
    pop bx
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
    mov ax, [wa_w]              ; sub-columns a unit: W x 256 / z
    mov ah, al
    xor al, al
    xor dx, dx
    div si
    mov [wa_fs8], ax
    mov ax, WA_KYH256
    xor dx, dx
    div si
    mov [wa_fv8], ax
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

; wa_line - (CX,DX) to (AX,BX), sub-pixels: Bresenham through wa_fplot
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
    call wa_fplot
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
    mov bx, si
    and bx, 0xFFFE              ; the column's word
    mov ax, [wa_colz+bx]
    cmp ax, [wa_fiz]
    ja .out                     ; the wall is nearer
    shr bx, 1
    mov ax, bx                  ; AX = column
    mov bx, di
    and bx, 0xFFFE              ; row x 2
    add ax, [wa_rowoff+bx]
    mov bx, ax                  ; BX = cell
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
    mov ax, [wa_w]
    shr ax, 1
    add ax, [wa_rowoff+WA_ROWS]  ; row 12's offset: (WA_ROWS/2) x 2 bytes
    mov bx, ax
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
    shl bx, 1
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
    mov bx, ax
    shl bx, 1
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
    mov bx, ax
    mov al, [wa_stamp+bx]
    and al, 0x7F
    cmp al, dl
    je .kept
    shl bx, 1
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
