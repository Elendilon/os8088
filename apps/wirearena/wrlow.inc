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


; a corner's record in wl_c (WL_REC bytes, x 16 its index): its vertex x 2,
; its top's (product, shift) pair, and - projected, in the view - its column
; x 16, top row, inverse depth and floor row, in wl_e1c's order
WL_CV       equ 0
WL_CN       equ 2
WL_CS       equ 4
WL_KC       equ 6
WL_KT       equ 8
WL_KI       equ 10
WL_KF       equ 12
WL_REC      equ 16

%macro WL_BSS 0
WA_VAR wl_box, 2                ; the box (x0, y0, x1, y1)
WA_VAR wl_h, 2                  ; its height (a flight's, its top tread's)
WA_VAR wl_kind, 1               ; its kind byte and faces byte (wa_bxh)
WA_VAR wl_faces, 1
WA_VAR wl_seen, 1               ; the faces the player is outside of: bits
WA_VAR wl_front, 1              ; ...of them, those drawn (posts, floors)
WA_VAR wl_topb, 1               ; the faces' top bits
WA_VAR wl_need, 1               ; the corners projected: bits
WA_VAR wl_fneed, 1              ; ...of them, those with a floor row
WA_VAR wl_m, 1                  ; a mask being walked
WA_VAR wl_c, 4*WL_REC           ; its corners (WL_*)
WA_VAR wl_fn, 2                 ; the floor's pair (made in the frame
WA_VAR wl_fs, 1                 ; wl_ffr)
WA_VAR wl_ffr, 1
WA_VAR wl_hn, 2                 ; the box's height's
WA_VAR wl_hs, 1
WA_VAR wl_zm, 2                 ; wl_hidden: 0, or -1 for the nearest corner
WA_VAR wl_vis0, 2               ; ...the first column x 2 it found showing
WA_VAR wl_wx2, 2                ; the last column x 2 (made with wl_fn)
WA_VAR wl_upd, 1                ; this pass raises the clip
WA_VAR wl_two, 1                ; ...and draws a floor edge with its top
WA_VAR wl_n1, 2                 ; a clipped edge's ends' pairs
WA_VAR wl_s1, 1
WA_VAR wl_n2, 2
WA_VAR wl_s2, 1
WA_VAR wl_e1c, 2                ; a pass's ends: column x 16, top row,
WA_VAR wl_e1r, 2                ; inverse depth, floor row - adjacent, in
WA_VAR wl_e1i, 2                ; this order (wl_face, wl_proj, wl_draw)
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
WA_VAR wl_k, 2                  ; a flight: the treads left, the count, the
WA_VAR wl_nt, 2                 ; rise, the low and high faces, and a
WA_VAR wl_rise, 2               ; tread's step along each side, camera
WA_VAR wl_lo, 1                 ; space
WA_VAR wl_hi, 1
WA_VAR wl_dxa, 2
WA_VAR wl_dza, 2
WA_VAR wl_dxb, 2
WA_VAR wl_dzb, 2
WA_VAR wl_ca, 2                 ; ...its low end's two corners (records)
WA_VAR wl_cb, 2
WA_VAR wl_tx1, 2                ; ...and the tread being drawn: its ends,
WA_VAR wl_tz1, 2                ; its height, the height's step, and 1
WA_VAR wl_tx2, 2                ; walking down from the top
WA_VAR wl_tz2, 2
WA_VAR wl_th, 2
WA_VAR wl_hst, 2
WA_VAR wl_back, 1
%endmacro

; wl_crn - per set of faces (S 1, E 2, N 4, W 8): the corners they run
; between, face f from corner f to f + 1; wl_bit - a face's bit, and the
; next one round's
wl_crn:
%assign wl_i 0
%rep 16
    db (wl_i | (wl_i << 1) | (wl_i >> 3)) & 15
%assign wl_i wl_i+1
%endrep
wl_bit:     db 1, 2, 4, 8, 1

; wa_lowbox - from wa_leaf: SI = a low box, DI = its record x 4 in wa_bxh,
; [wa_crow] its corners, [wa_wcol] its colour (ES = DS, as all through the
; frame)
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
    mov al, bl
    and al, [wl_faces]
    mov [wl_front], al          ; the faces drawn: their posts, floor edges
    mov bx, wl_crn
    xlatb
    mov [wl_fneed], al          ; ...and the corners that need a floor row
    mov al, [wl_faces]
    mov cl, 4
    shr al, cl
    mov [wl_topb], al
    mov al, 15                  ; THE CORNERS WANTED: all four with the eye
    mov cx, [wa_eye]            ; above the top (its far side is drawn) or
    cmp cx, [wl_h]              ; for a flight (its treads span it), else
    jg .need                    ; only the seen faces'
    test byte [wl_kind], 3
    jnz .need
    mov al, [wl_seen]
    xlatb
.need:
    mov [wl_need], al
    mov [wl_m], al              ; ...transformed (the shared vertex cache)
    mov si, [wa_crow]
    xor bp, bp                  ; BP = the corner's record (wa_vert keeps BP
    xor bh, bh                  ; and BX)
.cv:
    shr byte [wl_m], 1
    jnc .cvn
    mov bl, [si]
    mov [ds:bp+wl_c+WL_CV], bx
    mov al, [wa_frame]
    cmp [wa_vst+bx], al
    je .cvn
    push si
    call wa_vert
    pop si
.cvn:
    inc si
    add bp, WL_REC
    cmp bp, 4*WL_REC
    jb .cv
    mov al, [wa_frame]          ; the floor's pair, once a frame (wa_render
    cmp al, [wl_ffr]            ; clears wl_ffr)
    je .hpair
    mov [wl_ffr], al
    xor ax, ax
    call wa_hnum
    mov [wl_fn], ax
    mov [wl_fs], bl
    mov ax, [wa_w]              ; (and the last column, x 2)
    dec ax
    shl ax, 1
    mov [wl_wx2], ax
.hpair:
    mov ax, [wl_h]              ; the box's own height's, every corner's -
    call wa_hnum                ; but a flight's low end's (wl_flight0)
    mov [wl_hn], ax
    mov [wl_hs], bl
    mov [wl_c+0*WL_REC+WL_CN], ax
    mov [wl_c+1*WL_REC+WL_CN], ax
    mov [wl_c+2*WL_REC+WL_CN], ax
    mov [wl_c+3*WL_REC+WL_CN], ax
    mov [wl_c+0*WL_REC+WL_CS], bl
    mov [wl_c+1*WL_REC+WL_CS], bl
    mov [wl_c+2*WL_REC+WL_CS], bl
    mov [wl_c+3*WL_REC+WL_CS], bl
    test byte [wl_kind], 3
    jz .hid
    call wl_flight0
.hid:
    call wl_hidden              ; nothing of it can show: done
    jnc .shows
    ret
.shows:
    mov si, wl_c                ; each corner wanted and in the view: its
    mov ch, 1                   ; column, inverse depth and top row, and for
.k:                             ; a drawn face's its floor row (wa_ptbi's
    test [wl_need], ch          ; arithmetic, the pairs scaled by 4 where
    jz .kn                      ; they would pass 16 bits)
    mov bx, [si+WL_CV]
    test byte [wa_vok+bx], 1
    jz .kn
    mov ax, [wa_vpc+bx]
    mov [si+WL_KC], ax
    mov bx, [wa_vz+bx]
    call wl_iz
    mov [si+WL_KI], bx
    mov ax, [si+WL_CN]
    mov cl, [si+WL_CS]
    imul bx
    sar dx, cl
    mov ax, [wa_hq]
    sub ax, dx
    mov [si+WL_KT], ax
    test [wl_fneed], ch
    jz .kn
    mov ax, [wl_fn]
    mov cl, [wl_fs]
    imul bx
    sar dx, cl
    mov ax, [wa_hq]
    sub ax, dx
    mov [si+WL_KF], ax
.kn:
    add si, WL_REC
    shl ch, 1
    test ch, 16
    jz .k
    ; 1. POSTS, against the clip as it stood: a drawn face's start corner,
    ; and its end where the next face round is not seen (wa_boxf's rule)
    xor bx, bx
.p1:
    mov al, [wl_bit+bx]
    test al, [wl_front]
    jz .p1n
    call wl_post0
    mov al, [wl_bit+bx+1]
    test al, [wl_seen]
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
    mov al, [wl_bit+bx]
    test al, [wl_seen]
    jz .p2n
    mov byte [wl_two], 1
    test al, [wl_front]
    jnz .p2f
    test al, [wl_topb]
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
    mov al, [wl_bit+bx]
    test al, [wl_seen]
    jnz .p3n
    test al, [wl_topb]
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

; wl_hidden - CF = 1 when nothing of the box can show, decided before its
; corners are projected: every corner wanted in the view, and in each column
; its outline could reach (one either side of those corners' columns, for
; the posts' rounding) the column shut, or its clip at or above the box's
; topmost row. That row is the top's at the corner its height makes the
; highest on the screen - the farthest with the eye above the top, the
; nearest with it below - since every edge, post and tread of a box is
; interpolated between its corners' rows, and a floor row is under its
; top's; less one half-row for the edges' rounding. A flight's inner treads
; stand above its stringers, so for one only shut columns count. Nothing it
; skips would have drawn a cell, raised a clip or pushed an entry.
wl_hidden:
    mov word [wl_vis0], 0
    cmp byte [wl_need], 0       ; (no corner wanted: inside it, under its top)
    je wl_scan.none
    xor ax, ax                  ; the corner wanted: the largest z, or with
    mov cx, [wa_eye]            ; the eye at or under the top the smallest
    cmp cx, [wl_h]              ; (z xor -1 its key)
    jg .zm
    dec ax
.zm:
    mov [wl_zm], ax
    mov al, [wl_need]
    mov [wl_m], al
    mov dx, 32767               ; DX, CX = the columns x 16, least and most
    mov cx, -32767
    mov di, -32768              ; DI = the best key, BP its vertex
    mov si, wl_c
.c:
    shr byte [wl_m], 1
    jnc .c3
    mov bx, [si+WL_CV]
    test byte [wa_vok+bx], 1
    jz .shows                   ; (a corner out of the view: no test)
    mov ax, [wa_vpc+bx]
    cmp ax, dx
    jge .c1
    mov dx, ax
.c1:
    cmp ax, cx
    jle .c2
    mov cx, ax
.c2:
    mov ax, [wa_vz+bx]
    xor ax, [wl_zm]
    cmp ax, di
    jle .c3
    mov di, ax
    mov bp, bx
.c3:
    add si, WL_REC
    cmp si, wl_c+4*WL_REC
    jb .c
    sub dx, 9                   ; the columns: wa_span's first past the
    add cx, 7+16                ; least, less one; its last short of the
    mov ax, -32768              ; most, plus one. A flight: any open column
    test byte [wl_kind], 3      ; shows
    jnz wl_scan
    push cx
    push dx
    mov bx, bp
    mov bx, [wa_vz+bx]
    call wl_iz                  ; (clobbers AX, DX)
    mov ax, [wl_hn]
    mov cl, [wl_hs]
    call wl_row
    sar ax, 1
    sar ax, 1
    dec ax                      ; AX = the topmost half-row, less one
    pop dx
    pop cx
    jmp wl_scan
.shows:
    clc
    ret

; wl_scan - DX, CX = an outline's least and most columns x 16, as (c + 7)
; >> 4 makes its first and last columns, AX = a half-row at or under its
; topmost less one: CF = 1 when each of those columns on the screen is shut,
; or its clip is at or above AX - so nothing of it would draw a cell, raise a
; clip or push an entry; else [wl_vis0] the first that is not, x 2.
; Clobbers CX, DX, SI, DI
wl_scan:
    push ax
    mov ax, cx
    mov cl, 4
    sar dx, cl
    sar ax, cl
    or dx, dx
    jns .lo
    xor dx, dx
.lo:
    mov cx, [wa_w]
    dec cx
    cmp ax, cx
    jle .hi
    mov ax, cx
.hi:
    shl dx, 1
    shl ax, 1
    mov si, dx
    mov di, ax
    pop ax
    cmp si, di
    jg .none                    ; (off the screen, or nothing wanted)
.scan:
    cmp word [wa_cov+si], 0
    jne .n
    cmp [wa_cclip+si], ax
    jg .shows
.n:
    inc si
    inc si
    cmp si, di
    jbe .scan
.none:
    stc
    ret
.shows:
    mov [wl_vis0], si           ; (the first that showed: wl_face's start)
    clc
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

; wl_ends - BX = a face (0 S, 1 E, 2 N, 3 W): SI, DI = its start and end
; corners' records (offsets into wl_c). Keeps BX; clobbers CL
wl_ends:
    mov si, bx
    mov cl, 4
    shl si, cl
    lea di, [si+WL_REC]
    and di, 3*WL_REC
    ret

; wl_face - BX = a face, [wl_two] 1 its floor edge too: its pass, raising
; the clip. Keeps BX
wl_face:
    push bx
    call wl_ends
    mov byte [wl_upd], 1
    mov bx, [wl_c+si+WL_CV]
    test byte [wa_vok+bx], 1
    jz .clip
    mov bx, [wl_c+di+WL_CV]
    test byte [wa_vok+bx], 1
    jz .clip
    mov bx, [wl_c+si+WL_KC]     ; both corners in the view: unless each
    mov dx, [wl_c+di+WL_KC]     ; column it spans, as wl_draw takes them,
    mov ax, [wl_c+si+WL_KT]     ; is shut or clipped at or above its higher
    cmp bx, dx                  ; top less a half-row (wl_scan's test), as
    jle .f1                     ; projected
    xchg bx, dx
.f1:
    cmp ax, [wl_c+di+WL_KT]
    jle .f2
    mov ax, [wl_c+di+WL_KT]
.f2:
    sar ax, 1
    sar ax, 1
    dec ax
    mov cl, 3
    add bx, 7                   ; BX = the first column x 2, DX the last:
    sar bx, cl                  ; (c + 7) >> 4, x 2
    and bl, 0xFE
    sub dx, 9
    sar dx, cl
    and dl, 0xFE
    cmp bx, [wl_vis0]           ; (none before the box's first that showed
    jge .f3                     ; can show now: clips only rise)
    mov bx, [wl_vis0]
.f3:
    cmp dx, [wl_wx2]
    jle .fs
    mov dx, [wl_wx2]
.fs:
    cmp bx, dx
    jg .hid
    cmp word [wa_cov+bx], 0
    jne .fn
    cmp [wa_cclip+bx], ax
    jg .shows
.fn:
    inc bx
    inc bx
    jmp .fs
.shows:
    mov bx, di
    lea si, [wl_c+si+WL_KC]
    mov di, wl_e1c
    movsw
    movsw
    movsw
    movsw
    lea si, [wl_c+bx+WL_KC]
    movsw                       ; (DI has run on to wl_e2c)
    movsw
    movsw
    movsw
    call wl_draw
.hid:
    pop bx
    ret
.clip:
    mov ax, [wl_c+si+WL_CN]     ; a corner out of the view: the edge clipped,
    mov [wl_n1], ax             ; its ends projected at their corners'
    mov ax, [wl_c+di+WL_CN]     ; heights
    mov [wl_n2], ax
    mov al, [wl_c+si+WL_CS]
    mov [wl_s1], al
    mov al, [wl_c+di+WL_CS]
    mov [wl_s2], al
    mov bx, [wl_c+si+WL_CV]
    mov si, [wl_c+di+WL_CV]
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
    mov cx, 7
    jmp wl_post
wl_post1:
    push bx
    call wl_ends
    mov si, di
    mov cx, 7-16
wl_post:                        ; SI = the corner's record, CX = 7 (or 7 - 16
    mov bx, [wl_c+si+WL_CV]     ; for the end's rule: one column less)
    test byte [wa_vok+bx], 1
    jz .out                     ; (not in the view: off the screen, or behind)
    mov ax, [wl_c+si+WL_KC]     ; its column: as wa_span's corners
    add ax, cx
    mov cl, 4
    sar ax, cl
    js .out
    cmp ax, [wa_w]
    jge .out
    shl ax, 1
    mov di, ax                  ; DI = the column x 2
    cmp word [wa_cov+di], 0
    jne .out                    ; (shut)
    mov bx, [wl_c+si+WL_KT]     ; top and floor, half-rows, rounded
    add bx, 2
    sar bx, 1
    sar bx, 1
    mov ax, [wl_c+si+WL_KF]
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
    mov ax, 0xFFF0              ; (BX >= WA_ZMAX > 7 = DX: no fault, and the
    mov dx, 0x0007              ; quotient fits)
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
    mov di, wl_e1c
    mov ax, [wa_x1]
    mov bx, [wa_z1]
    mov cx, [wl_n1]
    mov dl, [wl_s1]
    call wl_proj
    mov ax, [wa_x2]
    mov bx, [wa_z2]
    mov cx, [wl_n2]
    mov dl, [wl_s2]
    call wl_proj
    jmp wl_draw
.out:
    ret

; wl_proj - AX = x, BX = z (z >= NEAR, |x| <= 8z: wa_clip's), CX, DL = a
; height's pair, DI = wl_e1c or wl_e2c: its column x 16, that height's row,
; the inverse depth and, with [wl_two], the floor's row (quarter half-rows),
; DI past them. Clobbers AX, BX, CX, DX, SI
wl_proj:
    mov si, cx                  ; SI = the product, CH = the shift
    mov ch, dl
    imul word [wa_k16]
    idiv bx                     ; (z >= NEAR: no fault; |x| <= 8z: it fits)
    add ax, [wa_c16]
    stosw
    call wl_iz
    mov ax, si
    mov cl, ch
    imul bx
    sar dx, cl
    mov ax, [wa_hq]
    sub ax, dx
    stosw
    mov ax, bx
    stosw
    cmp byte [wl_two], 0
    je .nof                     ; (no floor edge: the word is not read)
    mov ax, [wl_fn]
    mov cl, [wl_fs]
    imul bx
    sar dx, cl
    mov ax, [wa_hq]
    sub ax, dx
.nof:
    stosw
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
; wl_flight0 - a flight's corners: the low end's two take its first tread's
; height's pair, its high end's its top's (wa_lowbox's). [wl_lo], [wl_hi]
; the two ends' faces; [wl_nt], [wl_rise] its treads and their rise
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
    mov cx, ax                  ; (1..15: arenagen refuses any other count,
    mov ax, [wl_h]              ; and only a flight keeps its kind)
    xor dx, dx
    div cx
    mov [wl_rise], ax
    xor bh, bh                  ; the low face's two corners
    mov bl, [wl_lo]
    call wl_ends
    mov ax, [wl_rise]
    call wa_hnum
    mov [wl_c+si+WL_CN], ax
    mov [wl_c+di+WL_CN], ax
    mov [wl_c+si+WL_CS], bl
    mov [wl_c+di+WL_CS], bl
    ret

; wl_treads - a flight's inner treads, 2..N: each a line across it at its
; height, between points on its two sides - a tread's going along each, in
; camera space, made once - nearest first, from whichever end the player
; stands at. The low face runs corner A to B; A's side goes to the corner
; before A, B's to the corner after B (the high face's two). Each tread's
; ends and height are the last's plus a step, the same bits as k - 1 goings
; and k rises made afresh
wl_treads:
    cmp word [wl_nt], 2
    jb .out
    xor bh, bh
    mov bl, [wl_lo]
    call wl_ends                ; SI = A, DI = B (records)
    mov [wl_ca], si
    mov [wl_cb], di
    mov bx, [wl_c+si+WL_CV]
    sub si, WL_REC
    and si, 3*WL_REC            ; A's side's far corner
    mov si, [wl_c+si+WL_CV]
    call wl_going
    mov [wl_dxa], ax
    mov [wl_dza], dx
    mov si, [wl_cb]
    mov bx, [wl_c+si+WL_CV]
    add si, WL_REC
    and si, 3*WL_REC            ; B's side's
    mov si, [wl_c+si+WL_CV]
    call wl_going
    mov [wl_dxb], ax
    mov [wl_dzb], dx
    mov byte [wl_upd], 1
    mov byte [wl_two], 0
    mov ax, [wl_nt]
    dec ax
    mov [wl_k], ax              ; N - 1 treads
    call wl_lowseen             ; from the low end when the player is past
    mov cx, 1                   ; it - tread 2, one going out - else from
    mov ax, [wl_rise]           ; the top, tread N, stepping back
    mov byte [wl_back], 0
    jnz .first
    mov cx, [wl_k]
    neg ax
    mov byte [wl_back], 1
.first:
    mov [wl_hst], ax
    mov ax, cx                  ; the first's height: k rises
    inc ax
    mul word [wl_rise]
    mov [wl_th], ax
    mov si, [wl_ca]             ; ...its ends: k - 1 goings along each side
    mov si, [wl_c+si+WL_CV]
    mov ax, [wl_dxa]
    imul cx
    add ax, [wa_vx+si]
    mov [wl_tx1], ax
    mov ax, [wl_dza]
    imul cx
    add ax, [wa_vz+si]
    mov [wl_tz1], ax
    mov si, [wl_cb]
    mov si, [wl_c+si+WL_CV]
    mov ax, [wl_dxb]
    imul cx
    add ax, [wa_vx+si]
    mov [wl_tx2], ax
    mov ax, [wl_dzb]
    imul cx
    add ax, [wa_vz+si]
    mov [wl_tz2], ax
    cmp byte [wl_back], 0       ; (stepping back: the goings turned round)
    je .t
    neg word [wl_dxa]
    neg word [wl_dza]
    neg word [wl_dxb]
    neg word [wl_dzb]
.t:
    mov ax, [wl_th]             ; its height's pair, both ends
    call wa_hnum
    mov [wl_n1], ax
    mov [wl_n2], ax
    mov [wl_s1], bl
    mov [wl_s2], bl
    mov si, wl_tx1              ; its ends, for wa_clip to cut (wa_x1, z1,
    mov di, wa_x1               ; x2, z2 adjacent, as ours)
    movsw
    movsw
    movsw
    movsw
    call wl_xedge
    mov ax, [wl_hst]            ; the next
    add [wl_th], ax
    mov ax, [wl_dxa]
    add [wl_tx1], ax
    mov ax, [wl_dza]
    add [wl_tz1], ax
    mov ax, [wl_dxb]
    add [wl_tx2], ax
    mov ax, [wl_dzb]
    add [wl_tz2], ax
    dec word [wl_k]
    jnz .t
.out:
    ret

; wl_going - BX, SI = the vertices x 2 at a side's two ends: AX, DX = a
; tread's going along it, camera x and z ([wl_nt] >= 2: no fault)
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
