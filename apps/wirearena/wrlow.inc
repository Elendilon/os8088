; WireArena's OUTLINE path: boxes lower than the arena's tallest
; (docs/plans/WIREARENA-HEIGHTS-PLAN.md 1.3, 7.3.3, 7.3.4). Included by the
; renderer part after wrender.inc, whose vertex cache, span table, column
; state and plotting it shares.
;
; A tall box is a wall: its faces shut their columns (wa_span). A LOW box
; leaves them open above its top, so what stands behind it still shows
; there, and from an eye above it its top shows too. It is drawn as its
; outline, each cell tested against the column's clip - the topmost
; half-row something nearer already covers - and the clip then raised to the
; box's own top, with an entry on the column's depth stack (its span tag,
; the row it covers from) for the figures, the floor grid and the pistol's
; ray (wa_occl):
;  1. the posts at the visible corners, against the clip as it stood;
;  2. the faces the player is outside of, a pass each: the floor edge drawn
;     against the clip as it stood, then the top edge, raising it;
;  3. with the eye above the box, its other faces' top edges - the far side
;     of its top - raising it again;
;  4. a FLIGHT (kind 1) is one object: its low end is a face as tall as the
;     first tread, its sides rise straight from there to its top (the
;     stringers), and its inner treads are lines across it at their heights,
;     drawn nearest first.
; A top edge at or above the screen's top shuts its column, wa_cov holding
; its tag as a wall's does. Each corner keeps its own height (wl_ch): a
; flight's low-end corners stand as tall as its first tread. A corner in
; the view is projected once a box (wl_kc..wl_kf); an edge with a corner out
; of it is clipped (wa_clip) and its ends projected on the spot.

%macro WL_BSS 0
WA_VAR wl_box, 2                ; the box (x0, y0, x1, y1)
WA_VAR wl_h, 2                  ; its height (a flight's, its top tread's)
WA_VAR wl_kind, 1               ; its kind byte and faces byte (wa_bxh)
WA_VAR wl_faces, 1
WA_VAR wl_seen, 1               ; the faces the player is outside of: bits
WA_VAR wl_cv, 8                 ; its corners: vertex x 2
WA_VAR wl_ch, 8                 ; ...their heights
WA_VAR wl_cn, 8                 ; ...their tops' (product, shift) pairs
WA_VAR wl_cs, 4
WA_VAR wl_kc, 8                 ; ...and, in the view, column x 16, inverse
WA_VAR wl_ki, 8                 ; depth, top and floor rows (quarter half-
WA_VAR wl_kt, 8                 ; rows)
WA_VAR wl_kf, 8
WA_VAR wl_fn, 2                 ; the floor's pair (made in the frame
WA_VAR wl_fs, 1                 ; wl_ffr)
WA_VAR wl_ffr, 1
WA_VAR wl_hn, 2                 ; the box's height's
WA_VAR wl_hs, 1
WA_VAR wl_upd, 1                ; this pass raises the clip
WA_VAR wl_two, 1                ; ...and draws a floor edge with its top
WA_VAR wl_n1, 2                 ; a clipped edge's ends' pairs
WA_VAR wl_s1, 1
WA_VAR wl_n2, 2
WA_VAR wl_s2, 1
WA_VAR wl_e1c, 2                ; a pass's ends: column x 16, top row,
WA_VAR wl_e1r, 2                ; inverse depth, floor row
WA_VAR wl_e1i, 2
WA_VAR wl_e1f, 2
WA_VAR wl_e2c, 2
WA_VAR wl_e2r, 2
WA_VAR wl_e2i, 2
WA_VAR wl_e2f, 2
WA_VAR wl_stw, 2                ; the top's step a column (its value: CX.BP)
WA_VAR wl_stf, 2
WA_VAR wl_bw, 2                 ; the floor edge: half-row, fraction, step
WA_VAR wl_bf, 2
WA_VAR wl_bsw, 2
WA_VAR wl_bsf, 2
WA_VAR wl_tst, 1                ; ...steep, each
WA_VAR wl_bst, 1
WA_VAR wl_end, 2                ; one past the last column, x 2
WA_VAR wl_prev, 2               ; the column before's half-rows (a steep
WA_VAR wl_bprev, 2              ; step), and whether there was one
WA_VAR wl_havep, 1
WA_VAR wl_tag, 1
WA_VAR wl_k, 2                  ; a flight: the tread, the count, the rise,
WA_VAR wl_nt, 2                 ; the low and high faces, and a tread's step
WA_VAR wl_rise, 2               ; along each side, camera space
WA_VAR wl_lo, 1
WA_VAR wl_hi, 1
WA_VAR wl_dxa, 2
WA_VAR wl_dza, 2
WA_VAR wl_dxb, 2
WA_VAR wl_dzb, 2
WA_VAR wl_ca, 2                 ; ...and its low end's two corners
WA_VAR wl_cb, 2
%endmacro

; wa_lowbox - from wa_leaf: SI = a low box, DI = its record x 4 in wa_bxh,
; [wa_crow] its corners, [wa_wcol] its colour
wa_lowbox:
    mov [wl_box], si
    mov ax, [wa_bxh+di]
    mov [wl_h], ax
    mov ax, [wa_bxh+di+2]
    mov [wl_faces], ah
    mov ah, al                  ; the kind: only a FLIGHT (kind 1) keeps it -
    and ah, 3                   ; every flight test below is "kind & 3 is
    cmp ah, 1                   ; not 0", and a LIFT (kind 2, its index in
    je .kind                    ; bits 4-7) taken for one divided its height
    xor al, al                  ; by that index as a tread count: lift 0's
.kind:                          ; divide fault, every frame it was in view
    mov [wl_kind], al           ; (HEIGHTS-PLAN 9.5). A lift draws as the
                                ; solid low box it rests as, until wave 4
    xor bl, bl                  ; the faces seen, as wa_box chooses them
    mov ax, [wa_py]             ; (S 1, E 2, N 4, W 8)
    cmp ax, [si+2]
    jge .s1
    or bl, 1
    jmp .ew
.s1:
    cmp ax, [si+6]
    jle .ew
    or bl, 4
.ew:
    mov ax, [wa_px]
    cmp ax, [si+4]
    jle .w1
    or bl, 2
    jmp .sd
.w1:
    cmp ax, [si]
    jge .sd
    or bl, 8
.sd:
    mov [wl_seen], bl
    mov bx, [wa_crow]           ; the corners, transformed
    xor si, si
.cv:
    xor ah, ah
    mov al, [bx+si]
    mov di, si
    shl di, 1
    mov [wl_cv+di], ax
    push bx
    push si
    mov bx, ax
    mov al, [wa_frame]
    cmp [wa_vst+bx], al
    je .cached
    call wa_vert
.cached:
    pop si
    pop bx
    inc si
    cmp si, 4
    jb .cv
    mov ax, [wl_h]              ; their heights: the box's, or for a flight
    mov cx, 4                   ; its first tread's at the low end
    mov di, wl_ch
    push ds
    pop es
    rep stosw
    test byte [wl_kind], 3
    jz .heights
    call wl_flight0
.heights:
    mov al, [wa_frame]          ; the floor's pair, once a frame
    cmp al, [wl_ffr]
    je .fpair
    mov [wl_ffr], al
    xor ax, ax
    call wa_hnum
    mov [wl_fn], ax
    mov [wl_fs], bl
.fpair:
    mov ax, [wl_h]              ; the box's own height's, once
    call wa_hnum
    mov [wl_hn], ax
    mov [wl_hs], bl
    xor si, si                  ; each corner: its pair, and in the view its
.hn:                            ; column, inverse depth, top and floor rows
    mov ax, [wl_ch+si]
    cmp ax, [wl_h]
    jne .hnown
    mov ax, [wl_hn]
    mov bl, [wl_hs]
    jmp .hnset
.hnown:
    call wa_hnum
.hnset:
    mov [wl_cn+si], ax
    shr si, 1
    mov [wl_cs+si], bl
    shl si, 1
    mov bx, [wl_cv+si]
    test byte [wa_vok+bx], 1
    jz .hnn
    mov ax, [wa_vpc+bx]
    mov [wl_kc+si], ax
    mov bx, [wa_vz+bx]
    call wl_iz
    mov [wl_ki+si], bx
    mov ax, [wl_cn+si]
    shr si, 1
    mov cl, [wl_cs+si]
    shl si, 1
    call wl_row
    mov [wl_kt+si], ax
    mov ax, [wl_fn]
    mov cl, [wl_fs]
    call wl_row
    mov [wl_kf+si], ax
.hnn:
    inc si
    inc si
    cmp si, 8
    jb .hn
    ; 1. POSTS, against the clip as it stood: a seen face's start corner,
    ; and its end where the next face round is not seen (wa_boxf's rule)
    xor bx, bx
.p1:
    call wl_isfront
    jz .p1n
    call wl_post0
    call wl_nextseen
    jnz .p1n
    call wl_post1
.p1n:
    inc bx
    cmp bx, 4
    jb .p1
    ; 2. THE SEEN FACES, a pass each: the floor edge, then the top raising
    ; the clip - and a seen face hidden against a taller neighbour still
    ; shows its top's crease where its top bit says
    xor bx, bx
.p2:
    mov al, [wl_seen]
    mov cl, bl
    shr al, cl
    test al, 1
    jz .p2n
    call wl_isfront
    mov byte [wl_two], 1
    jnz .p2f
    call wl_topbit
    jz .p2n
    mov byte [wl_two], 0
.p2f:
    call wl_face
.p2n:
    inc bx
    cmp bx, 4
    jb .p2
    ; (a flight seen from its low end: its inner treads are nearer than the
    ; far side of its top, and the depth stack keeps its entries in order)
    call wl_lowseen
    jz .p3s
    call wl_treads
.p3s:
    ; 3. THE FAR SIDE OF ITS TOP, with the eye above the box
    mov ax, [wa_eye]
    cmp ax, [wl_h]
    jle .p3d
    xor bx, bx
.p3:
    mov al, [wl_seen]
    mov cl, bl
    shr al, cl
    test al, 1
    jnz .p3n
    call wl_topbit
    jz .p3n
    mov byte [wl_two], 0
    call wl_face
.p3n:
    inc bx
    cmp bx, 4
    jb .p3
.p3d:
    ; 4. A FLIGHT'S INNER TREADS, seen from anywhere but its low end
    test byte [wl_kind], 3
    jz .done
    call wl_lowseen
    jnz .done
    call wl_treads
.done:
    ret

; wl_lowseen - ZF = 0 when the box is a flight and the player stands past
; its low end. Clobbers AL, CL
wl_lowseen:
    test byte [wl_kind], 3
    jz .out
    mov al, [wl_seen]
    mov cl, [wl_lo]
    shr al, cl
    test al, 1
.out:
    ret

; wl_isfront - BX = a face (0 S, 1 E, 2 N, 3 W): ZF = 0 when it is seen and
; drawn (its face bit). Keeps every register but AL, CL
wl_isfront:
    mov al, [wl_seen]
    and al, [wl_faces]
    mov cl, bl
    shr al, cl
    test al, 1
    ret

; wl_nextseen - BX = a face: ZF = 0 when the face after it round is seen
wl_nextseen:
    mov al, [wl_seen]
    mov cl, bl
    inc cl
    and cl, 3
    shr al, cl
    test al, 1
    ret

; wl_topbit - BX = a face: ZF = 0 when its top edge is drawn
wl_topbit:
    mov al, [wl_faces]
    mov cl, bl
    add cl, 4
    shr al, cl
    test al, 1
    ret

; wl_ends - BX = a face: SI, DI = its start and end corners x 2 (indices
; into the wl_c* and wl_k* words). Keeps BX
wl_ends:
    mov si, bx
    shl si, 1
    lea di, [bx+1]
    and di, 3
    shl di, 1
    ret

; wl_face - BX = a face, [wl_two] 1 its floor edge too: its pass, raising
; the clip. Keeps BX
wl_face:
    push bx
    call wl_ends
    mov byte [wl_upd], 1
    mov bx, [wl_cv+si]
    test byte [wa_vok+bx], 1
    jz .clip
    mov bx, [wl_cv+di]
    test byte [wa_vok+bx], 1
    jz .clip
    mov ax, [wl_kc+si]          ; both corners in the view: as projected
    mov [wl_e1c], ax
    mov ax, [wl_kt+si]
    mov [wl_e1r], ax
    mov ax, [wl_ki+si]
    mov [wl_e1i], ax
    mov ax, [wl_kf+si]
    mov [wl_e1f], ax
    mov ax, [wl_kc+di]
    mov [wl_e2c], ax
    mov ax, [wl_kt+di]
    mov [wl_e2r], ax
    mov ax, [wl_ki+di]
    mov [wl_e2i], ax
    mov ax, [wl_kf+di]
    mov [wl_e2f], ax
    call wl_draw
    pop bx
    ret
.clip:
    mov ax, [wl_cn+si]          ; a corner out of the view: the edge clipped,
    mov [wl_n1], ax             ; its ends projected at their corners'
    mov ax, [wl_cn+di]          ; heights
    mov [wl_n2], ax
    shr si, 1
    shr di, 1
    mov al, [wl_cs+si]
    mov [wl_s1], al
    mov al, [wl_cs+di]
    mov [wl_s2], al
    shl si, 1
    shl di, 1
    mov bx, [wl_cv+si]
    mov si, [wl_cv+di]
    mov ax, [wa_vx+bx]
    mov [wa_x1], ax
    mov ax, [wa_vz+bx]
    mov [wa_z1], ax
    mov ax, [wa_vx+si]
    mov [wa_x2], ax
    mov ax, [wa_vz+si]
    mov [wa_z2], ax
    call wl_xedge
    pop bx
    ret

; wl_post0, wl_post1 - BX = a face: the post at its start corner (the
; first column whose centre is past it) or its end (the last short of it):
; `│` from the top to the floor, against the clip. Keeps BX
wl_post0:
    push bx
    call wl_ends
    xor cx, cx
    jmp wl_post
wl_post1:
    push bx
    call wl_ends
    mov si, di
    mov cx, 1
wl_post:                        ; SI = the corner x 2, CX = 1 the end's rule
    mov bx, [wl_cv+si]
    test byte [wa_vok+bx], 1
    jz .out                     ; (not in the view: off the screen, or behind)
    mov ax, [wl_kc+si]          ; its column: as wa_span's corners
    add ax, 7
    push cx
    mov cl, 4
    sar ax, cl
    pop cx
    sub ax, cx
    js .out
    cmp ax, [wa_w]
    jge .out
    shl ax, 1
    mov di, ax                  ; DI = the column x 2
    cmp word [wa_cov+di], 0
    jne .out                    ; (shut)
    mov bx, [wl_kt+si]          ; top and floor, half-rows, rounded
    add bx, 2
    sar bx, 1
    sar bx, 1
    mov ax, [wl_kf+si]
    add ax, 2
    sar ax, 1
    sar ax, 1
    mov si, di                  ; SI = the column x 2
    cmp ax, [wa_cclip+si]
    jle .clp
    mov ax, [wa_cclip+si]
.clp:
    mov di, [wa_lp]
    mov dl, [wa_frame]
    mov cl, 1
    call wa_corner              ; (wa_vedge: every cell tested)
    mov [wa_lp], di
.out:
    pop bx
    ret

; wl_iz - BX = z (>= NEAR) -> BX = the inverse depth (wa_rcp's). Clobbers
; AX, DX
wl_iz:
    cmp bx, WA_ZMAX
    jae .div
    shl bx, 1
    mov bx, [wa_rcp+bx-WA_NEAR*2]
    ret
.div:
    mov ax, 0xFFF0
    mov dx, 0x0007
    div bx
    mov bx, ax
    ret

; wl_row - BX = an inverse depth, AX, CL = a height's (product, shift)
; pair -> AX = its row, quarter half-rows: hq - (product x iz) >> 16 >> CL.
; Clobbers DX
wl_row:
    imul bx
    sar dx, cl
    mov ax, [wa_hq]
    sub ax, dx
    ret

; wl_xedge - [wa_x1],[wa_z1] - [wa_x2],[wa_z2] in camera space, [wl_n1]/
; [wl_s1] and [wl_n2]/[wl_s2] the ends' heights' pairs, [wl_upd], [wl_two]:
; clipped (the near plane, the guard band), projected and drawn
wl_xedge:
    call wa_clip
    jc .out
    mov ax, [wa_x1]
    mov bx, [wa_z1]
    mov cx, [wl_n1]
    mov dl, [wl_s1]
    call wl_proj
    mov [wl_e1c], ax
    mov [wl_e1r], bx
    mov [wl_e1i], dx
    mov [wl_e1f], si
    mov ax, [wa_x2]
    mov bx, [wa_z2]
    mov cx, [wl_n2]
    mov dl, [wl_s2]
    call wl_proj
    mov [wl_e2c], ax
    mov [wl_e2r], bx
    mov [wl_e2i], dx
    mov [wl_e2f], si
    jmp wl_draw
.out:
    ret

; wl_proj - AX = x, BX = z (z >= NEAR, |x| <= 8z), CX, DL = a height's
; pair -> AX = column x 16, BX = that height's row, SI = the floor's (quarter
; half-rows), DX = inverse depth
wl_proj:
    push cx
    push dx
    imul word [wa_k16]
    idiv bx
    add ax, [wa_c16]
    push ax
    call wl_iz
    mov ax, [wl_fn]
    mov cl, [wl_fs]
    push bx
    call wl_row
    pop bx
    mov si, ax                  ; SI = the floor's row
    pop di                      ; DI = the column
    pop cx                      ; CL = the shift
    pop ax                      ; AX = the product
    push bx
    call wl_row
    pop dx                      ; DX = the inverse depth
    mov bx, ax
    mov ax, di
    ret

; wl_draw - a pass over the columns between [wl_e1*] and [wl_e2*]: from the
; first whose centre is past the left end to the last short of the right,
; in each the top edge plotted where it is above the column's clip (and the
; column not shut), with [wl_two] the floor edge too, a steep step between
; two columns filled; with [wl_upd] the clip raised to the top and a stack
; entry pushed (a top at or above the screen's shuts the column)
wl_draw:
    mov ax, [wl_e1c]
    cmp ax, [wl_e2c]
    jle .ord
    mov si, wl_e1c              ; (left to right)
    mov di, wl_e2c
    mov cx, 4
.sw:
    mov ax, [si]
    xchg ax, [di]
    mov [si], ax
    inc si
    inc si
    inc di
    inc di
    loop .sw
.ord:
    mov bx, [wl_e1c]
    mov cl, 4
    add bx, 7
    sar bx, cl                  ; the first column
    mov si, [wl_e2c]
    add si, 7
    sar si, cl
    dec si                      ; the last
    or bx, bx
    jns .lok
    xor bx, bx
.lok:
    mov ax, [wa_w]
    dec ax
    cmp si, ax
    jle .rok
    mov si, ax
.rok:
    cmp bx, si
    jg .none
    shl bx, 1
    shl si, 1
    inc si
    inc si
    mov [wl_end], si
    mov [wa_cs], bx
    mov ax, bx                  ; the first centre past the left end, x 16
    shl ax, 1
    shl ax, 1
    shl ax, 1
    add ax, 8
    mov cx, [wl_e1c]
    sub ax, cx
    mov [wa_fs], ax
    mov ax, [wl_e2c]
    sub ax, cx
    mov [wa_dc], ax
    mov [wa_c1], cx
    cmp byte [wl_two], 0        ; the floor edge's start and step: wa_span's
    je .nob                     ; own (exact at the first column; half-rows
    mov byte [wa_steep], 0      ; with a 16-bit fraction, the whole part
    mov ax, [wl_e1f]            ; rounded)
    mov bx, [wl_e2f]
    call wa_span.edge
    mov [wl_bsw], dx
    mov [wl_bsf], ax
    mov [wl_bw], bx
    mov [wl_bf], cx
    mov al, [wa_steep]
    mov [wl_bst], al
.nob:
    mov byte [wa_steep], 0      ; ...and the top's
    mov ax, [wl_e1r]
    mov bx, [wl_e2r]
    call wa_span.edge
    mov [wl_stw], dx
    mov [wl_stf], ax
    push bx
    push cx
    mov al, [wa_steep]
    mov [wl_tst], al
    mov byte [wl_tag], 0
    cmp byte [wl_upd], 0
    je .notag
    mov ax, [wl_e1i]            ; its tag: its inverse depth's line
    mov [wa_i1], ax
    mov ax, [wl_e2i]
    mov [wa_i2], ax
    call wa_span.reg
    jc .full
    mov [wl_tag], bl
.notag:
    pop bp                      ; the top: CX.BP
    pop cx
    mov byte [wl_havep], 0
    mov si, [wa_cs]
    mov di, [wa_lp]
    mov dl, [wa_frame]
    mov al, [wl_tst]            ; which of the four loops: the floor edge
    or al, [wl_bst]             ; too, a step to fill
    mov bl, [wl_two]
    shl bl, 1
    or bl, al
    xor bh, bh
    shl bx, 1
    call [wl_loops+bx]
    mov [wa_lp], di
.none:
    ret
.full:
    pop cx
    pop bp
    ret
wl_loops:   dw wl_l00, wl_l01, wl_l10, wl_l11

; WLLOOP %1 = 1 the floor edge too, %2 = 1 a steep step may need filling:
; wl_draw's columns (SI from the first x 2 to [wl_end]; CX.BP the top; DL
; the stamp, DI the list)
%macro WLLOOP 2
%%col:
    cmp word [wa_cov+si], 0
    jne %%shut
%if %1
    mov ax, [wl_bw]             ; the floor edge, against the clip as it was
  %if %2
    cmp byte [wl_bst], 0
    je %%bplot
    cmp byte [wl_havep], 0
    je %%bplot
    push cx
    push ax
    mov cx, [wl_bprev]
    call wa_stepfill
    pop ax
    pop cx
%%bplot:
    mov [wl_bprev], ax
  %endif
    cmp ax, WA_HR
    jae %%top
    cmp ax, [wa_cclip+si]
    jae %%top
    mov bx, ax
    mov al, [wa_hgl+bx]
    mov ah, [wa_wcol]
    shl bx, 1
    mov bx, [wa_hroff+bx]
    add bx, si
    WPLOT
%%top:
%endif
    mov ax, cx                  ; the top
%if %2
    cmp byte [wl_tst], 0
    je %%tplot
    cmp byte [wl_havep], 0
    je %%tplot
    push cx
    push ax
    mov cx, [wl_prev]
    call wa_stepfill
    pop ax
    pop cx
%%tplot:
    mov [wl_prev], ax
    mov byte [wl_havep], 1
%endif
    cmp ax, WA_HR
    jae %%upd                   ; (off the screen, either side)
    cmp ax, [wa_cclip+si]
    jae %%next                  ; under something nearer: nor any update
    mov bx, ax
    mov al, [wa_hgl+bx]
    mov ah, [wa_wcol]
    shl bx, 1
    mov bx, [wa_hroff+bx]
    add bx, si
    WPLOT
%%upd:
    mov ax, cx
    cmp ax, [wa_cclip+si]
    jge %%next                  ; (lower than the clip, or below the screen)
    or ax, ax
    jg %%push
    xor ax, ax                  ; at or over the screen's top: the column is
    mov bl, [wl_tag]            ; covered from top to bottom - shut, as a
    xor bh, bh                  ; wall shuts it
    mov [wa_cov+si], bx
    dec word [wa_left]
%%push:
    mov [wa_cclip+si], ax
    mov bx, [wa_cstn+si]        ; the depth stack: (tag, row) on top, or,
    cmp bx, WA_CSTK             ; full, merged into the deepest - the
    jb %%room                   ; nearer tag kept, so a figure between the
    dec bx                      ; two can only be hidden a frame too soon
    shl bx, 1
    mov bx, [wl_k160+bx]
    mov [wa_cst+bx+si+1], al
    jmp %%next
%%room:
    inc word [wa_cstn+si]
    shl bx, 1
    mov bx, [wl_k160+bx]
    mov ah, al
    mov al, [wl_tag]
    mov [wa_cst+bx+si], ax
    jmp %%next
%%shut:
%if %2
    mov byte [wl_havep], 0
%endif
%%next:
    add bp, [wl_stf]
    adc cx, [wl_stw]
%if %1
    mov ax, [wl_bsf]
    add [wl_bf], ax
    mov ax, [wl_bsw]
    adc [wl_bw], ax
%endif
    inc si
    inc si
    cmp si, [wl_end]
    jb %%col
    ret
%endmacro
wl_l00:     WLLOOP 0, 0
wl_l01:     WLLOOP 0, 1
wl_l10:     WLLOOP 1, 0
wl_l11:     WLLOOP 1, 1
wl_k160:    dw 0, 2*WA_MAXW, 4*WA_MAXW, 6*WA_MAXW

; --- flights --------------------------------------------------------------
; wl_flight0 - a flight's corners: the low end's two stand as tall as its
; first tread (wl_ch), its high end's as its top. [wl_lo], [wl_hi] the two
; ends' faces; [wl_nt], [wl_rise] its treads and their rise
wl_flight0:
    mov al, [wl_kind]
    mov cl, 2
    shr al, cl
    and al, 3                   ; the face it rises TOWARD
    mov [wl_hi], al
    xor al, 2
    mov [wl_lo], al
    mov al, [wl_kind]
    mov cl, 4
    shr al, cl
    xor ah, ah
    mov [wl_nt], ax
    mov cx, ax
    mov ax, [wl_h]
    xor dx, dx
    div cx
    mov [wl_rise], ax
    xor bh, bh                  ; the low face's two corners
    mov bl, [wl_lo]
    call wl_ends
    mov [wl_ch+si], ax
    mov [wl_ch+di], ax
    ret

; wl_treads - a flight's inner treads, 2..N: each a line across it at its
; height, between points on its two sides - a tread's going along each, in
; camera space, made once - nearest first, from whichever end the player
; stands at. The low face runs corner A to B; A's side goes to the corner
; before A, B's to the corner after B (the high face's two)
wl_treads:
    cmp word [wl_nt], 2
    jb .out
    xor bh, bh
    mov bl, [wl_lo]
    call wl_ends                ; SI = A, DI = B (x 2)
    mov [wl_ca], si
    mov [wl_cb], di
    mov ax, si
    sub ax, 2
    and ax, 6                   ; A's side's far corner
    mov bx, [wl_cv+si]
    mov si, ax
    mov si, [wl_cv+si]
    call wl_going
    mov [wl_dxa], ax
    mov [wl_dza], dx
    mov si, [wl_cb]
    mov ax, si
    add ax, 2
    and ax, 6                   ; B's side's
    mov bx, [wl_cv+si]
    mov si, ax
    mov si, [wl_cv+si]
    call wl_going
    mov [wl_dxb], ax
    mov [wl_dzb], dx
    mov byte [wl_upd], 1
    mov byte [wl_two], 0
    mov word [wl_k], 2
.t:
    call wl_lowseen             ; from the low end when the player is past
    mov ax, [wl_k]              ; it, else from the top (AX after the test:
    jnz .fwd                    ; wl_lowseen takes AL and CL)
    mov ax, [wl_nt]
    add ax, 2
    sub ax, [wl_k]
.fwd:
    call wl_tread
    inc word [wl_k]
    mov ax, [wl_k]
    cmp ax, [wl_nt]
    jbe .t
.out:
    ret

; wl_going - BX, SI = the vertices x 2 at a side's two ends: AX, DX = a
; tread's going along it, camera x and z
wl_going:
    mov ax, [wa_vx+si]
    sub ax, [wa_vx+bx]
    cwd
    idiv word [wl_nt]
    push ax
    mov ax, [wa_vz+si]
    sub ax, [wa_vz+bx]
    cwd
    idiv word [wl_nt]
    mov dx, ax
    pop ax
    ret

; wl_tread - AX = a tread, 2..N: its nosing, (k - 1) goings from the low end
; at k risers' height, from one side to the other
wl_tread:
    push ax
    mul word [wl_rise]          ; its height's pair, both ends
    call wa_hnum
    mov [wl_n1], ax
    mov [wl_n2], ax
    mov [wl_s1], bl
    mov [wl_s2], bl
    pop cx
    dec cx                      ; k - 1 goings
    mov si, [wl_ca]
    mov si, [wl_cv+si]
    mov ax, [wl_dxa]
    imul cx
    add ax, [wa_vx+si]
    mov [wa_x1], ax
    mov ax, [wl_dza]
    imul cx
    add ax, [wa_vz+si]
    mov [wa_z1], ax
    mov si, [wl_cb]
    mov si, [wl_cv+si]
    mov ax, [wl_dxb]
    imul cx
    add ax, [wa_vx+si]
    mov [wa_x2], ax
    mov ax, [wl_dzb]
    imul cx
    add ax, [wa_vz+si]
    mov [wa_z2], ax
    jmp wl_xedge
