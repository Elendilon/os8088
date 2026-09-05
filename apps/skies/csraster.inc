; =============================================================================
; os8088 - apps/skies/csraster.inc
;
; THE RASTER (SPEC.md 88.4). Three backends behind five entries - cs_r_setup,
; cs_r_begin, cs_poly, cs_seg, cs_r_end - and NOT ONE kernel drawing slot
; among them, because SPEC.md 53.7 makes every one of them illegal the moment
; fsx_mode returns. It is TANK ATTACK's raster (SPEC.md 85.3) with the
; dirty-span machinery taken OUT of the view and a polygon filler put in:
;
;   * the VIEW is written whole every frame - the sky/ground pass covers every
;     byte of it (88.4.1), the polygons and lines go over that, and the blit
;     copies the view rows whole. Its span pairs are set once at entry and
;     never touched again;
;   * the PANEL rows below it keep one span set (88.3): an instrument is an
;     opaque rectangle, drawn only when its value changed and marked into the
;     span so the blit carries it; the blit empties the panel spans behind it;
;   * a POLYGON is two bounds a row (88.4.2): every edge is traced once per
;     row with Bresenham's integer step into cs_xl/cs_xr, and every row is one
;     masked run. The horizon is the same tracer on one edge.
;
; ONE STRIDE FOR ALL THREE, Tank's coincidence: a CGA 320x200x4 row, a
; Hercules 640-pixel 1bpp row and a Mode X plane row are each 80 bytes.
;
; SS != DS (CLAUDE.md): nothing here indexes a table with BP.
; =============================================================================

; --- per-backend geometry, indexed by CSB_* - 1 -------------------------------
; The nine words land on nine contiguous bss words in this order.
;      vx,  vy,  vw,  vh,  wx0,  ww,  wh, sclx, scly
cs_vptab:
    dw   0,   0, 320, 240,    0, 320, 144,  277,  277   ; MODEX: square pixels
    dw   0,   0, 320, 200,    0, 320, 112,  277,  231   ; CGA:   4:3 in 320x200
    dw  40,  74, 640, 200,  120, 400, 112,  443,  285   ; HERC:  a 400-wide view
                                                        ; in a 640x200 box
; scly = sclx x the pixel aspect, so a square is square on all three. sclx is
; 60 degrees of horizontal field on CGA and Mode X (the view's half-width over
; it is 0.578); Hercules keeps the same pixel scale in a 400-pixel view, so
; its field is 49 degrees (0.451) - the width came down from 512 for the
; frame's sake and the picture's (88.3.4), and what it lost is the edges of
; the field, not the size of anything in it.

; -----------------------------------------------------------------------------
; cs_r_setup - adopt a backend for the length of one bracket
; in:  [cs_back] set, [cs_fsi] filled by OSAPI_FSX_MODE
; out: CF=1 if the raster cannot be had (no shadow); every register clobbered
; -----------------------------------------------------------------------------
cs_r_setup:
    mov al, [cs_back]
    dec al
    mov ah, 18
    mul ah
    mov si, cs_vptab
    add si, ax
    mov di, cs_vx
    push ds
    pop es
    mov cx, 9
    cld
    rep movsw
    mov ax, [cs_wx0]
    add ax, [cs_ww]
    dec ax
    mov [cs_wx1], ax                ; the view's last x
    mov ax, [cs_ww]
    shr ax, 1
    add ax, [cs_wx0]
    mov [cs_vcx], ax                ; the projection centre
    mov ax, [cs_wh]
    shr ax, 1
    mov [cs_vcy], ax
    mov ax, [cs_wh]
    mov [cs_pany], ax               ; the panel's first row

    ; --- the backend's own procs ------------------------------------------
    mov byte [cs_ink], 0xFF         ; no ink set yet (cs_setink's cache)
    mov byte [cs_conebase], 1       ; the cull's cone: 0.75 of the depth...
    cmp byte [cs_back], CSB_HERC
    jne .cb
    mov byte [cs_conebase], 0       ; ...0.5 for the narrower Hercules field
.cb:
    mov byte [cs_kshift], 2
    mov byte [cs_pbg8], CSI_PBG     ; the panel's ground, as the glyph stores
    mov word [cs_inktab], cs_inkmodex ; want it (a Mode X index...)
    mov word [cs_hrunproc], cs_hrun_modex
    mov word [cs_rowsproc], cs_polyrows
    mov word [cs_hzproc], cs_hzrow_modex
    mov word [cs_glyphproc], cs_glyph_modex
    mov si, cs_lp_modex
    cmp byte [cs_back], CSB_MODEX
    je .procs
    mov byte [cs_pbg8], 0xFF        ; ...four pixels of CGA brown...
    mov word [cs_inktab], cs_inkcga
    mov word [cs_hrunproc], cs_hrun_cga
    mov word [cs_lrunproc], cs_hrun_cga
    mov word [cs_hzproc], cs_hzrow_sh
    mov word [cs_glyphproc], cs_glyph_cga
    mov si, cs_lp_cga
    cmp byte [cs_back], CSB_CGA
    je .procs
    mov byte [cs_pbg8], 0           ; ...or nothing at all)
    mov byte [cs_kshift], 3
    mov word [cs_inktab], cs_inkherc
    mov word [cs_hrunproc], cs_hrun_herc
    mov word [cs_rowsproc], cs_polyrows_herc
    mov word [cs_lrunproc], cs_lrun_herc
    mov word [cs_hzproc], cs_hzrow_sh
    mov word [cs_glyphproc], cs_glyph_herc
    mov si, cs_lp_herc
.procs:
    mov ax, [si]
    mov [cs_lsh], ax
    mov ax, [si+2]
    mov [cs_lst], ax
    mov ax, [si+4]
    mov [cs_lvt], ax

    mov ax, [cs_wx0]                ; the view's bytes: first, and how many
    mov cl, [cs_kshift]
    shr ax, cl
    mov [cs_wb0], ax
    mov ax, [cs_ww]
    shr ax, cl
    mov [cs_wbn], ax

    call cs_devrows
    call cs_ktabs                   ; the projection tables for these scales

    ; --- the target: two VRAM pages, or one RAM shadow --------------------
    cmp byte [cs_back], CSB_MODEX
    jne .shadow
    mov ax, [cs_fsi+FSI_SEG]
    mov [cs_tseg], ax
    mov word [cs_page0], 0
    mov word [cs_page1], 19200      ; 240 rows x 80 bytes a plane
    call cs_modex_pal
    jmp short .spans
.shadow:
    mov dx, [cs_shseg]              ; ONCE FOR THE INSTANCE, not once a
    or dx, dx                       ; bracket (SPEC.md 85.3's lesson): the
    jnz .haveshadow                 ; claim is freed with the instance
    mov ax, CS_SHKB
    call OSAPI_MEM_CLAIM
    jc .noshadow
    mov [cs_shseg], dx
.haveshadow:
    mov [cs_tseg], dx
    mov word [cs_page0], 0
    mov word [cs_page1], 0
    cmp byte [cs_back], CSB_CGA
    jne .spans
    call cs_cga_pal
.spans:
    ; --- the span set: every row starts empty, and a view row is marked by
    ;     whatever touches it (SPEC.md 88.3); cs_fullspan is the pair a
    ;     touched view row takes, and every row kind starts DIRTY so the
    ;     first frame fills the whole view ---------------------------------
    mov al, [cs_wb0]                ; lo = the first byte...
    mov ah, al
    add ah, [cs_wbn]
    dec ah                          ; ...hi = the last
    mov [cs_fullspan], ax
    mov word [cs_spanp], cs_span0
    mov word [cs_spanp+2], cs_span1
    mov word [cs_spcur], cs_span0
    mov word [cs_spprv], cs_span1
    push ds
    pop es
    mov di, cs_span0
    mov cx, CS_MAXROW * 2           ; both sets empty
    mov ax, 0x00FF
    cld
    rep stosw
    mov di, cs_rowkind
    mov cx, CS_MAXROW
    mov al, 0x83                    ; every row: kind unknown, and dirty
    rep stosb
    clc
    ret
.noshadow:
    stc
    ret

; -----------------------------------------------------------------------------
; cs_cga_pal - CGA palette 0 at low intensity - green, red, brown - over a
;              LIGHT BLUE background: the sky is colour 0, which is the one
;              colour of the four a CGA lets an app choose freely (3D9h bits
;              0-3), and that is what makes a blue sky possible at all
; -----------------------------------------------------------------------------
cs_cga_pal:
    mov dx, 0x3D9
    mov al, 0x09                    ; bit 5 clear: palette 0; bit 4 clear:
    out dx, al                      ; low intensity; background 9 light blue
    ret

; -----------------------------------------------------------------------------
; cs_modex_pal - the DAC, one row per CSI_*
; -----------------------------------------------------------------------------
cs_modex_pal:
    push si
    mov si, cs_dactab
    mov cx, CSI_NINK
    xor bl, bl
.e:
    mov dx, 0x3C8
    mov al, bl
    out dx, al
    inc dx
    lodsb
    out dx, al
    lodsb
    out dx, al
    lodsb
    out dx, al
    inc bl
    loop .e
    pop si
    ret

cs_dactab:                          ; 6-bit DAC values, indexed by CSI_*
    db 22, 36, 60                   ;  0 sky
    db 14, 38, 14                   ;  1 ground
    db 20, 20, 20                   ;  2 runway
    db 14, 26, 54                   ;  3 river
    db 50, 47, 42                   ;  4 a wall toward us
    db 36, 33, 29                   ;  5 a side
    db 43, 40, 36                   ;  6 a roof
    db 18, 44, 18                   ;  7 a hill
    db 26, 20, 14                   ;  8 the tower and every line
    db 60, 60, 60                   ;  9 runway edges, roads
    db  6,  6, 10                   ; 10 the panel
    db 56, 56, 56                   ; 11 its ink
    db 63, 44, 10                   ; 12 its warning

; ...and what each MEANING is worth as FOUR ROW PATTERNS on the three
; adapters (SPEC.md 88.4.4). Indexed by CSI_* x 4.
cs_inkherc:
    db 0x00, 0x00, 0x00, 0x00       ; sky: black - what every Hercules flight
                                    ; simulator of the period showed, and the
                                    ; cheapest row there is
    db 0x88, 0x00, 0x22, 0x00       ; ground: 12.5% - two lit pixels in every
                                    ; 4x4. At 25% a view that is mostly ground
                                    ; reads as a grey wall the buildings sit
                                    ; on; at 12.5% it reads as ground
    db 0x00, 0x00, 0x00, 0x00       ; runway: black, with white edges
    db 0xFF, 0x00, 0xFF, 0x00       ; river: stripes
    db 0xFF, 0xFF, 0xFF, 0xFF       ; a wall toward us: white
    db 0xAA, 0x55, 0xAA, 0x55       ; a side: 50%
    db 0xEE, 0xBB, 0xEE, 0xBB       ; a roof: 75%
    db 0xCC, 0xCC, 0x33, 0x33       ; a hill: 50% in blocks
    db 0xFF, 0xFF, 0xFF, 0xFF       ; lines
    db 0xFF, 0xFF, 0xFF, 0xFF       ; marks
    db 0x00, 0x00, 0x00, 0x00       ; the panel
    db 0xFF, 0xFF, 0xFF, 0xFF       ; its ink
    db 0xFF, 0xFF, 0xFF, 0xFF       ; its warning
cs_inkcga:                          ; palette 0: 0 light blue, 1 green,
    db 0x00, 0x00, 0x00, 0x00       ;   2 red, 3 brown
    db 0x55, 0x55, 0x55, 0x55       ; ground: green
    db 0xFF, 0xFF, 0xFF, 0xFF       ; runway: brown
    db 0x00, 0x00, 0x00, 0x00       ; river: the sky's blue
    db 0xFF, 0xFF, 0xFF, 0xFF       ; a wall: brown
    db 0xAA, 0xAA, 0xAA, 0xAA       ; a side: red
    db 0xAA, 0xAA, 0xAA, 0xAA       ; a roof: red
    db 0xFF, 0xFF, 0xFF, 0xFF       ; a hill: brown
    db 0xAA, 0xAA, 0xAA, 0xAA       ; lines: red
    db 0x55, 0x55, 0x55, 0x55       ; marks: green
    db 0xFF, 0xFF, 0xFF, 0xFF       ; the panel: brown
    db 0x55, 0x55, 0x55, 0x55       ; its ink: green
    db 0xAA, 0xAA, 0xAA, 0xAA       ; its warning: red
cs_inkmodex:                        ; the DAC above, one for one
    db 0, 0, 0, 0
    db 1, 1, 1, 1
    db 2, 2, 2, 2
    db 3, 3, 3, 3
    db 4, 4, 4, 4
    db 5, 5, 5, 5
    db 6, 6, 6, 6
    db 7, 7, 7, 7
    db 8, 8, 8, 8
    db 9, 9, 9, 9
    db 10, 10, 10, 10
    db 11, 11, 11, 11
    db 12, 12, 12, 12

; The pixel value of an ink on the two colour adapters, for the WALKS and the
; glyphs: the 2-bit colour on CGA and the index on Mode X. Hercules is the one
; bit.
cs_inkval_cga:   db 0, 1, 3, 0, 3, 2, 2, 3, 2, 1, 3, 1, 2
cs_inkval_modex: db 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12

; -----------------------------------------------------------------------------
; cs_setink - adopt a logical ink (CSI_*) for the fills and walks that follow
; in:  AL = CSI_*.  preserves every register
; -----------------------------------------------------------------------------
cs_setink:
    cmp al, [cs_ink]                ; as it is: nothing to do
    je .same
    push ax
    push bx
    push si
    mov [cs_ink], al
    xor ah, ah
    mov si, ax
    shl si, 1
    shl si, 1
    add si, [cs_inktab]
    mov bx, [si]                    ; the four pattern bytes
    mov [cs_pat], bx
    mov bx, [si+2]
    mov [cs_pat+2], bx
    mov bl, al
    xor bh, bh
    mov al, 1
    cmp byte [cs_back], CSB_HERC
    je .have
    mov al, [cs_inkval_cga + bx]
    cmp byte [cs_back], CSB_CGA
    je .cga
    mov al, [cs_inkval_modex + bx]
    jmp short .have
.cga:
    push ax
    mov bl, al                      ; the glyph expander for this ink: three
    xor bh, bh                      ; 16-byte tables, one per 2bpp colour
    dec bx
    shl bx, 1
    shl bx, 1
    shl bx, 1
    shl bx, 1
    add bx, cs_nib1
    mov [cs_nibp], bx
    pop ax
.have:
    mov [cs_ink8], al
    pop si
    pop bx
    pop ax
.same:
    ret

; -----------------------------------------------------------------------------
; cs_devrows - the device offset of every box row, and 80 x row, once a
;              bracket (SPEC.md 85.3.4's tables)
; -----------------------------------------------------------------------------
cs_devrows:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov di, cs_devoff
    xor bx, bx                      ; BX = r
.row:
    mov ax, bx
    mov cx, 80
    mul cx
    mov si, bx
    shl si, 1
    mov [cs_rowoff + si], ax
    mov ax, bx
    add ax, [cs_vy]                 ; AX = the device row
    cmp byte [cs_back], CSB_HERC
    je .herc
    mov dx, ax                      ; CGA: bank = y & 1, 80 bytes a row
    and dx, 1
    push dx
    shr ax, 1
    mov cx, 80
    mul cx
    pop dx
    jmp short .bank
.herc:
    mov dx, ax                      ; HERC: bank = y & 3, 90 bytes a row
    and dx, 3
    push dx
    mov cl, 2
    shr ax, cl
    mov cx, 90
    mul cx
    pop dx
    add ax, 5                       ; ...and the box starts at x = 40
.bank:
    mov cl, 5
    shl dx, cl
    mov cl, 8
    shl dx, cl
    add ax, dx
    mov [di], ax
    add di, 2
    inc bx
    cmp bx, [cs_vh]
    jb .row
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; cs_r_begin - open a frame: pick the target page
; -----------------------------------------------------------------------------
cs_r_begin:
    mov al, [cs_par]                ; the frame's parity picks the span set
    and al, 1                       ; (SPEC.md 85.3.1's two sets)...
    xor ah, ah
    mov bx, ax
    shl bx, 1
    mov si, [cs_spanp + bx]
    mov [cs_spcur], si
    xor bx, 2
    mov si, [cs_spanp + bx]
    mov [cs_spprv], si
    push ds
    pop es
    mov di, [cs_spcur]              ; ...armed empty
    mov word [di - 4], 0x7FFF       ; ...and its row range with it: the two
    mov word [di - 2], -1           ; guard words before a set are the
    mov cx, [cs_vh]                 ; first and last row anything marked
    mov ax, 0x00FF                  ; (SPEC.md 88.3.3)
    cld
    rep stosw
    mov word [cs_tbase], 0
    cmp byte [cs_back], CSB_MODEX
    jne .out
    mov al, [cs_par]                ; ...and the page
    and al, 1
    mov cx, [cs_page0]
    jz .p0
    mov cx, [cs_page1]
.p0:
    mov [cs_tbase], cx
    mov di, cs_rowkind              ; two pages alternate, so a row is never
    mov cx, [cs_wh]                 ; "as it was": every row is refilled
    mov al, 0x83
    rep stosb
.out:
    ret

; -----------------------------------------------------------------------------
; cs_r_end - put the frame on the glass
; -----------------------------------------------------------------------------
cs_r_end:
    cmp byte [cs_back], CSB_MODEX
    je .flip
    call cs_blit
    inc byte [cs_par]
    ret
.flip:
    mov al, [cs_par]                ; ONE CALL, the kernel's (SPEC.md 53.10):
    and al, 1                       ; the page named is scanned when it returns
    call OSAPI_FSX_PAGE
    inc byte [cs_par]
    ret

; -----------------------------------------------------------------------------
; cs_blit - this frame's spans, shadow to VRAM (CGA and Hercules)
;
; The view rows carry the view's whole byte range and the panel rows carry
; what their items drew; one set, because nothing on the panel is ever
; erased - only redrawn (SPEC.md 88.3). DS stays ours (85.3.7).
; -----------------------------------------------------------------------------
cs_blit:
    mov si, [cs_spcur]              ; this frame's set...
    mov di, [cs_spprv]              ; ...and last frame's: a byte the last
    mov ax, [si - 4]                ; frame drew and this one refilled still
    cmp ax, [di - 4]                ; has to reach the glass (85.3.1).
    jle .y0                         ; The rows to look at are the union of
    mov ax, [di - 4]                ; the two sets' ranges, so the panel's
.y0:                                ; eighty-odd rows cost nothing on a
    mov bp, [si - 2]                ; frame that left them alone (88.3.3)
    cmp bp, [di - 2]
    jge .y1
    mov bp, [di - 2]
.y1:
    sub bp, ax
    jl .out
    inc bp                          ; BP = rows
    mov bx, ax
    shl bx, 1
    add si, bx
    add di, bx
    add bx, cs_devoff
    mov dx, ax
    shl dx, 1
    shl dx, 1
    add dx, ax
    mov cl, 4
    shl dx, cl                      ; DX = 80 y, the shadow row
    mov es, [cs_fsi+FSI_SEG]
    cld
.row:
    lodsw                           ; AL/AH = lo/hi
    mov cx, [di]                    ; CL/CH = lo'/hi'
    inc di
    inc di
    cmp ax, cx
    jne .work
    cmp ax, 0x00FF                  ; both empty: the common row
    je .next
.work:
    cmp al, cl                      ; AL = min(lo, lo')
    jbe .l1
    mov al, cl
.l1:
    cmp ah, ch                      ; AH = max(hi, hi')
    jae .h1
    mov ah, ch
.h1:
    cmp al, ah
    ja .next
    and al, 0xFE                    ; whole words
    or ah, 1
    sub ah, al
    shr ah, 1
    mov cl, ah
    xor ch, ch
    inc cx                          ; CX = words
    xor ah, ah                      ; AX = the first byte
    push si
    push di
    mov di, [bx]
    add di, ax                      ; ES:DI = the device row
    mov si, dx
    add si, ax                      ; DS:SI = the shadow row
    push ds
    mov ds, [cs_shseg]
    rep movsw
    pop ds
    pop di
    pop si
.next:
    inc bx
    inc bx
    add dx, 80
    dec bp
    jnz .row
.out:
    ret

; =============================================================================
; The sky and the ground (SPEC.md 88.4.1)
; =============================================================================

; -----------------------------------------------------------------------------
; cs_skyground - every row of the view, split at the horizon
; in:  [cs_nx]/[cs_ny]/[cs_nz] = the world's up vector in camera space, Q15
; clobbers everything
;
; With the pixel's ray r = (X/sclx, -Y/scly, 1) about the centre, sky is where
; r.n > 0. The line r.n = 0 is solved in whichever form is BOUNDED: steeper
; than a pixel a row it is x(row) with one clamped intercept; flatter it is
; row(x), and the rows where it meets the view's two side edges are found
; instead. Either way the crossing per row comes out of cs_edge, the same
; integer tracer every polygon edge uses, into cs_xl.
; -----------------------------------------------------------------------------
cs_skyground:
    push ds
    pop es
    mov di, cs_xl                   ; +big over the view rows: an untouched
    mov cx, [cs_wh]                 ; row is wholly one side
    mov ax, 0x7FFF
    cld
    rep stosw
    mov word [cs_hzy0], 0x7FFF      ; the rows the line runs between
    mov word [cs_hzy1], -1

    mov ax, [cs_nx]                 ; the up vector, quartered: keeps every
    sar ax, 1                       ; product below inside 2^31
    sar ax, 1
    mov [cs_hnx], ax
    mov ax, [cs_ny]
    sar ax, 1
    sar ax, 1
    mov [cs_hny], ax
    mov ax, [cs_nz]
    sar ax, 1
    sar ax, 1
    mov [cs_hnz], ax

    ; --- which form: |nx x scly| >= |ny x sclx| is the steep one ------------
    mov ax, [cs_hnx]
    imul word [cs_scly]
    call cs_abs32
    mov [cs_hza], ax
    mov [cs_hza+2], dx
    mov ax, [cs_hny]
    imul word [cs_sclx]
    call cs_abs32
    cmp dx, [cs_hza+2]
    ja .flat
    jb .steep
    cmp ax, [cs_hza]
    ja .flat

    ; ===== STEEP: x = X0 + Y x (ny sclx)/(nx scly), |slope| <= 1 ============
.steep:
    mov ax, [cs_hnz]                ; X0 = -nz sclx / nx, at the centre row
    imul word [cs_sclx]
    neg dx
    neg ax
    sbb dx, 0
    mov bx, [cs_hnx]
    call cs_cdiv
    jc .whole                       ; the line is off the view entirely, and
                                    ; every row is the centre's side
    mov [cs_hzx0], ax
    mov ax, [cs_vcy]
    neg ax                          ; Y at row 0
    call cs_hzsteep_t
    add ax, [cs_hzx0]
    add ax, [cs_vcx]
    mov [cs_hzxa], ax
    mov ax, [cs_wh]
    dec ax
    sub ax, [cs_vcy]                ; Y at the last row
    call cs_hzsteep_t
    add ax, [cs_hzx0]
    add ax, [cs_vcx]
    mov cx, ax
    mov dx, [cs_wh]
    dec dx
    mov ax, [cs_hzxa]
    xor bx, bx
    mov byte [cs_eside], 1          ; into cs_xl, one store a row
    call cs_edge                    ; cs_xl[row] = the crossing, every row
    mov word [cs_hzy0], 0
    mov ax, [cs_wh]
    dec ax
    mov [cs_hzy1], ax
    ; which side is which: as X -> -inf, r.n ~ nx X, so nx > 0 puts ground
    ; on the left. Above and below the band do not arise: it spans every row.
    mov al, CSI_GROUND
    mov ah, CSI_SKY
    cmp word [cs_hnx], 0
    jg .sides
    xchg al, ah
.sides:
    mov [cs_hzl], al
    mov [cs_hzr], ah
    mov [cs_hzab], ah
    mov [cs_hzbl], al
    jmp .rows

    ; ===== FLAT: row = Y0 + X x (nx scly)/(ny sclx), |slope| < 1 ============
.flat:
    mov ax, [cs_hnz]                ; Y0 = nz scly / ny, at the centre column
    imul word [cs_scly]
    mov bx, [cs_hny]
    call cs_cdiv
    jc .whole
    mov [cs_hzx0], ax
    mov ax, [cs_wx0]
    sub ax, [cs_vcx]                ; X at the left edge
    call cs_hzflat_t
    add ax, [cs_hzx0]
    add ax, [cs_vcy]
    mov [cs_hzya], ax               ; the row the line meets the left edge on
    mov ax, [cs_wx1]
    sub ax, [cs_vcx]
    call cs_hzflat_t
    add ax, [cs_hzx0]
    add ax, [cs_vcy]
    mov [cs_hzyb], ax               ; ...and the right edge
    mov bx, [cs_hzya]
    mov dx, ax
    cmp bx, dx
    jle .o1
    xchg bx, dx
.o1:
    mov [cs_hzy0], bx               ; the band, top row and bottom row
    mov [cs_hzy1], dx
    mov ax, [cs_wx0]
    mov bx, [cs_hzya]
    mov cx, [cs_wx1]
    mov dx, [cs_hzyb]
    mov byte [cs_eside], 1
    call cs_edge                    ; cs_xl[row] = the crossing inside it
    ; above the band is where -ny Y (Y -> -inf) is positive: ny > 0 means sky
    ; above. Inside the band the line descends to the right when the left row
    ; is the higher one, and then the LEFT of a row is below the line.
    mov al, CSI_SKY
    mov ah, CSI_GROUND
    cmp word [cs_hny], 0
    jg .ab
    xchg al, ah
.ab:
    mov [cs_hzab], al               ; above...
    mov [cs_hzbl], ah               ; ...and below
    mov bx, [cs_hzya]
    cmp bx, [cs_hzyb]
    jg .rises
    mov [cs_hzl], ah                ; left of the crossing is below the line
    mov [cs_hzr], al
    jmp short .rows
.rises:
    mov [cs_hzl], al
    mov [cs_hzr], ah
    jmp short .rows

    ; ===== the line is off the view: every row is the centre's side =======
.whole:
    mov al, CSI_SKY
    cmp word [cs_hnz], 0
    jg .w1
    mov al, CSI_GROUND
.w1:
    mov [cs_hzab], al
    mov [cs_hzbl], al

    ; ===== the rows =========================================================
    ; Three runs: the rows above the band, all of one kind; the band, split
    ; row by row; the rows below. A WHOLE row is refilled only when it is
    ; dirty or its kind changed, and marked for the blit only when its kind
    ; changed - a dirty row's old ink is in LAST frame's spans, and the blit
    ; carries the union (SPEC.md 88.3). That is most of the view in level
    ; flight, at a compare a row.
.rows:
    mov al, [cs_hzl]
    call cs_inkpat
    mov [cs_hzlt], si
    mov al, [cs_hzr]
    call cs_inkpat
    mov [cs_hzrt], si
    mov es, [cs_tseg]
    cmp byte [cs_back], CSB_MODEX
    jne .p0
    mov dx, 0x3C4                   ; every plane, once
    mov ax, 0x0F02
    out dx, ax
.p0:
    xor bx, bx                      ; BX = the row
    mov di, [cs_tbase]              ; DI = its first view byte
    add di, [cs_wb0]
    mov cx, [cs_hzy0]               ; the rows above the band...
    cmp cx, [cs_wh]
    jle .abv
    mov cx, [cs_wh]
.abv:
    mov al, [cs_hzab]
    call cs_hzrows
    mov cx, [cs_hzy1]               ; ...the band...
    inc cx
    cmp cx, [cs_wh]
    jle .bd
    mov cx, [cs_wh]
.bd:
    sub cx, bx
    jle .below
.b:
    push cx
    push bx
    push di
    mov byte [cs_rowkind + bx], 3   ; split: refilled and carried every frame
    mov si, bx
    shl si, 1
    mov cx, [cs_xl + si]
    cmp cx, 0x7FFF
    jne .split
    mov cx, [cs_wx1]                ; untouched inside the band: the crossing
    inc cx                          ; is off the right, so the row is the
                                    ; left side's
.split:
    mov ax, [cs_fullspan]           ; a split row goes over whole
    add si, [cs_spcur]
    mov [si], ax
    mov di, bx
    and di, 3                       ; DI = the row's phase in the pattern
    mov si, [cs_hzlt]
    add si, di
    mov al, [si]
    mov si, [cs_hzrt]
    add si, di
    mov ah, [si]
    call [cs_hzproc]                ; the row split at CX: AL left, AH right
    pop di
    pop bx
    pop cx
    add di, 80
    inc bx
    loop .b
.below:
    mov cx, [cs_wh]                 ; ...and the rows below it
    sub cx, bx
    mov al, [cs_hzbl]
    call cs_hzrows
    ret

; -----------------------------------------------------------------------------
; cs_hzrows - CX whole rows of kind AL (0 sky, 1 ground) from row BX, whose
;             first view byte is ES:DI. Advances BX and DI past them.
;             Clobbers AX, CX, SI.
; -----------------------------------------------------------------------------
cs_hzrows:
    or cx, cx
    jle .out
    mov dl, al                      ; DL = the kind (cs_inkpat zeroes AH: the
    call cs_inkpat                  ; first build kept it there and every row
    mov [cs_hzkt], si               ; was recorded as kind 0, so a row that
    mov al, dl                      ; went from ground to sky was "as it was"
                                    ; and never refilled - 88.3.1)
.r:
    mov ah, [cs_rowkind + bx]
    cmp al, ah
    je .next                        ; as it was, and clean: nothing to do
    push cx
    push di
    mov [cs_rowkind + bx], al
    and ah, 3
    cmp al, ah                      ; the same kind, only dirty: refill the
    je .part                        ; bytes that were drawn on, no more
    mov si, [cs_spcur]              ; a new kind: the whole row goes over,
    cmp bx, [si - 4]                ; and the set's row range takes it
    jge .y0
    mov [si - 4], bx
.y0:
    cmp bx, [si - 2]
    jle .y1
    mov [si - 2], bx
.y1:
    mov si, bx
    shl si, 1
    add si, [cs_spcur]
    mov cx, [cs_fullspan]
    mov [si], cx
    mov cx, [cs_wbn]
    jmp short .fill
.part:                              ; last frame's span IS the erase: the
    mov si, bx                      ; blit carries it (it is in the union)
    shl si, 1                       ; and nothing outside it changed
    add si, [cs_spprv]
    mov cx, [si]                    ; CL = its first byte, CH = its last
    sub ch, cl
    jb .done                        ; ...none: the mark was a kind change
    push ax
    mov al, cl
    xor ah, ah
    sub ax, [cs_wb0]                ; the span is absolute bytes of the row
    add di, ax                      ; and DI is the view's first: the first
    mov cl, ch                      ; build added them and refilled fifteen
    xor ch, ch                      ; bytes to the right of everything, which
    inc cx                          ; left the left of every object on the
    mov si, bx                      ; glass and a bar past the view's edge
    and si, 3                       ; (88.3.1)
    add si, [cs_hzkt]
    mov al, [si]
    mov ah, al
    shr cx, 1                       ; the 8088's bus is a byte wide: an odd
    rep stosw                       ; address costs a word store nothing
    jnc .part1
    stosb
.part1:
    pop ax
    jmp short .done
.fill:
    push ax
    mov si, bx
    and si, 3
    add si, [cs_hzkt]
    mov al, [si]
    mov ah, al
    shr cx, 1
    rep stosw
    pop ax
.done:
    pop di
    pop cx
.next:
    add di, 80
    inc bx
    LOOPF .r
.out:
    ret

; -----------------------------------------------------------------------------
; cs_markrows - rows SI..DI of the view had bytes [cs_mklo]..[cs_mkhi] drawn
;               on: the blit carries them, and the next frame's sky/ground
;               pass refills the rows
; preserves AX, BX, CX, DX; clobbers SI, DI
; -----------------------------------------------------------------------------
cs_markrows:
    push ax
    push bx
    push cx
    mov bx, [cs_spcur]
    cmp si, [bx - 4]                ; the set's row range takes them
    jge .y0
    mov [bx - 4], si
.y0:
    cmp di, [bx - 2]
    jle .y1
    mov [bx - 2], di
.y1:
    mov al, [cs_mklo]
    mov ah, [cs_mkhi]
    mov bx, si
    shl bx, 1
    add bx, [cs_spcur]
.m:
    or byte [cs_rowkind + si], 0x80
    cmp [bx], al
    jbe .lo
    mov [bx], al
.lo:
    cmp [bx+1], ah
    jae .hi
    mov [bx+1], ah
.hi:
    inc bx
    inc bx
    inc si
    cmp si, di
    jle .m
    pop cx
    pop bx
    pop ax
    ret

; cs_markacc - the same arguments, ACCUMULATED into the object's mark
;              instead: a polygon or a segment costs four compares, and the
;              per-row walk is paid once per object by cs_drawobj. A
;              wireframe tower is 32 segments over the same hundred rows,
;              and marking each was dearer than walking it (SPEC.md 88.3.2)
; preserves AX, BX, CX, DX
cs_markacc:
    cmp si, [cs_oby0]
    jge .y0
    mov [cs_oby0], si
.y0:
    cmp di, [cs_oby1]
    jle .y1
    mov [cs_oby1], di
.y1:
    push ax
    mov al, [cs_mklo]
    cmp al, [cs_oblo]
    jae .lo
    mov [cs_oblo], al
.lo:
    mov al, [cs_mkhi]
    cmp al, [cs_obhi]
    jbe .hi
    mov [cs_obhi], al
.hi:
    pop ax
    ret

; cs_inkpat - AL = an ink; out SI = its four pattern bytes
cs_inkpat:
    xor ah, ah
    mov si, ax
    shl si, 1
    shl si, 1
    add si, [cs_inktab]
    ret

; cs_hzsteep_t - AX = Y; out AX = ((ny Y)/scly x sclx)/nx, clamped
cs_hzsteep_t:
    imul word [cs_hny]
    idiv word [cs_scly]
    imul word [cs_sclx]
    mov bx, [cs_hnx]
    call cs_cdiv
    ret

; cs_hzflat_t - AX = X; out AX = ((nx X)/sclx x scly)/ny, clamped
cs_hzflat_t:
    imul word [cs_hnx]
    idiv word [cs_sclx]
    imul word [cs_scly]
    mov bx, [cs_hny]
    call cs_cdiv
    ret

; cs_cdiv - AX = DX:AX / BX, or CF=1 (and AX = +-30000) when the quotient
; would not fit a word: |DX| < |BX|/2 is sufficient (SPEC.md 85.5). Clobbers
; CX, DX.
cs_cdiv:
    mov cx, bx
    or cx, cx
    jns .p
    neg cx
.p:
    shr cx, 1
    push dx
    or dx, dx
    jns .q
    not dx
.q:
    cmp dx, cx
    pop dx
    jae .no
    idiv bx
    clc
    ret
.no:
    mov ax, 30000
    xor dx, bx                      ; the sign the quotient would have had
    jns .s
    neg ax
.s:
    stc
    ret

; cs_abs32 - DX:AX = |DX:AX|
cs_abs32:
    or dx, dx
    jns .o
    neg dx
    neg ax
    sbb dx, 0
.o:
    ret

; -----------------------------------------------------------------------------
; cs_hzwhole - one whole view row of one pattern
; in:  BX = the row, AL = AH = the pattern.  clobbers BX, CX, DX, DI, ES
; -----------------------------------------------------------------------------
cs_hzwhole:
    shl bx, 1
    mov di, [cs_rowoff + bx]
    add di, [cs_tbase]
    add di, [cs_wb0]
    mov cx, [cs_wbn]
    shr cx, 1
    mov es, [cs_tseg]
    cld
    cmp byte [cs_back], CSB_MODEX
    jne .go
    push ax
    mov dx, 0x3C4                   ; every plane
    mov ax, 0x0F02
    out dx, ax
    pop ax
.go:
    rep stosw
    ret

; -----------------------------------------------------------------------------
; cs_hzrow_sh - one view row split at a column (the two shadow backends)
; in:  BX = the row, CX = the crossing x (box coords, any value), AL = the
;      pattern left of it, AH = the pattern from it rightward
; clobbers everything
; -----------------------------------------------------------------------------
cs_hzrow_sh:
    cmp cx, [cs_wx0]
    jg .l1
    mov al, ah                      ; wholly the right pattern
    jmp cs_hzwhole
.l1:
    cmp cx, [cs_wx1]
    jle .split
    mov ah, al                      ; wholly the left pattern
    jmp cs_hzwhole
.split:
    mov dx, ax                      ; DL/DH = the two patterns
    shl bx, 1
    mov di, [cs_rowoff + bx]
    add di, [cs_tbase]
    mov es, [cs_tseg]
    mov bx, cx
    push cx
    mov cl, [cs_kshift]
    shr bx, cl                      ; BX = the crossing byte
    pop cx
    mov si, bx
    sub si, [cs_wb0]                ; SI = bytes wholly left of it
    push di
    add di, [cs_wb0]
    mov al, dl
    mov ah, dl
    push cx
    mov cx, si
    call cs_fillrun                 ; the left run
    pop cx
    pop di
    ; the crossing byte: pixels (cx & 7).. take the right pattern
    mov si, cx
    and si, 7
    mov al, [cs_hlm + si]           ; pixels i..7, 1bpp
    cmp byte [cs_kshift], 3
    je .m
    and si, 3
    mov al, [cs_clm + si]           ; pixels i..3, 2bpp
.m:
    mov ah, al
    not ah                          ; AL = the right's mask, AH = the left's
    and al, dh
    and ah, dl
    or al, ah
    mov [es:di+bx], al
    mov cx, [cs_wb0]                ; the right run: bytes after it
    add cx, [cs_wbn]
    sub cx, bx
    dec cx
    add di, bx
    inc di
    mov al, dh
    mov ah, dh
    call cs_fillrun
    ret

; cs_fillrun - CX bytes of AL (= AH) at ES:DI, words where it can. Advances
; DI past them. Clobbers CX. CX may be 0 or negative (nothing is stored).
cs_fillrun:
    or cx, cx
    jle .out
    cld
    test di, 1
    jz .even
    stosb
    dec cx
    jz .out
.even:
    shr cx, 1
    rep stosw
    jnc .out
    stosb
.out:
    ret

; -----------------------------------------------------------------------------
; cs_hzrow_modex - the same on Mode X: a byte is four pixels across planes
; -----------------------------------------------------------------------------
cs_hzrow_modex:
    cmp cx, [cs_wx0]
    jg .l1
    mov al, ah
    jmp cs_hzwhole
.l1:
    cmp cx, [cs_wx1]
    jle .split
    mov ah, al
    jmp cs_hzwhole
.split:
    mov [cs_hzpat], ax              ; the two patterns
    shl bx, 1
    mov di, [cs_rowoff + bx]
    add di, [cs_tbase]
    mov es, [cs_tseg]
    mov bx, cx
    shr bx, 1
    shr bx, 1                       ; BX = the crossing byte
    mov si, bx
    sub si, [cs_wb0]
    mov ax, 0x0F02
    mov dx, 0x3C4
    out dx, ax                      ; every plane for the runs
    push di
    add di, [cs_wb0]
    mov al, [cs_hzpat]
    mov ah, al
    push cx
    mov cx, si
    call cs_fillrun
    pop cx
    pop di
    and cx, 3
    jz .noleft
    mov si, cx
    mov ah, [cs_pmr + si - 1]       ; planes 0..i-1: the left pattern
    mov al, 2
    out dx, ax
    mov al, [cs_hzpat]
    mov [es:di+bx], al
.noleft:
    mov si, cx
    mov ah, [cs_pml + si]           ; planes i..3: the right pattern
    mov al, 2
    out dx, ax
    mov al, [cs_hzpat+1]
    mov [es:di+bx], al
    mov ax, 0x0F02
    out dx, ax
    mov cx, [cs_wb0]
    add cx, [cs_wbn]
    sub cx, bx
    dec cx
    add di, bx
    inc di
    mov al, [cs_hzpat+1]
    mov ah, al
    call cs_fillrun
    ret

; =============================================================================
; The polygon filler (SPEC.md 88.4.2)
; =============================================================================

; -----------------------------------------------------------------------------
; cs_edge - trace one edge into cs_xl or cs_xr, one x per row
; in:  AX = x1, BX = y1, CX = x2, DX = y2 (box coords, |x| <= 4000ish);
;      [cs_eside] = 1 the polygon's LEFT chain (stores into cs_xl), 2 its
;      right (cs_xr), 0 both by min/max (a horizontal edge, or a caller that
;      does not know the winding)
; clobbers everything
;
; Bresenham's integer step: q = floor(dx/dy), r = dx - q dy, and per row
; x += q; err += r; if err >= dy then x += 1, err -= dy. An edge that starts
; above the view is JUMPED to row 0 with one multiply and one divide, because
; a vertex a hand's breadth past the near plane projects thousands of rows
; away and stepping there would cost more than the face. A convex polygon's
; edges are one chain or the other, so a row costs ONE store and no compare.
; -----------------------------------------------------------------------------
cs_edge:
    cmp bx, dx
    jne .slope
    ; --- horizontal: one row, both ends -------------------------------------
    or bx, bx
    js .out
    cmp bx, [cs_wh]
    jge .out
    cmp ax, cx
    jle .ord
    xchg ax, cx
.ord:
    shl bx, 1
    cmp ax, [cs_xl + bx]
    jge .h1
    mov [cs_xl + bx], ax
.h1:
    cmp cx, [cs_xr + bx]
    jle .out
    mov [cs_xr + bx], cx
.out:
    ret
.slope:
    jl .down
    xchg ax, cx                     ; make (AX, BX) the upper end
    xchg bx, dx
.down:
    cmp bx, [cs_wh]                 ; wholly below the view
    jge .out
    or dx, dx                       ; wholly above it
    js .out
    mov [cs_ey2], dx                ; the lower end's row
    sub dx, bx                      ; DX = dy > 0
    mov [cs_edy], dx
    sub cx, ax                      ; CX = dx, signed
    mov si, ax                      ; SI = x
    mov ax, cx
    cwd
    idiv word [cs_edy]              ; AX = trunc(dx/dy), DX = the remainder
    or dx, dx
    jns .fl
    dec ax                          ; ...made a FLOOR: q down one, r up by dy
    add dx, [cs_edy]
.fl:
    mov [cs_eq], ax
    mov [cs_er], dx
    xor di, di                      ; DI = err
    or bx, bx
    jns .inview
    ; --- jump n = -y1 rows: x += n q + (n r) div dy, err = (n r) mod dy ------
    mov cx, bx
    neg cx                          ; CX = n
    mov ax, [cs_eq]
    imul cx
    add si, ax
    mov ax, [cs_er]
    mul cx                          ; DX:AX = n r (both non-negative)
    div word [cs_edy]
    add si, ax
    mov di, dx
    xor bx, bx
.inview:
    mov cx, [cs_ey2]                ; the last row to trace, clipped
    cmp cx, [cs_wh]
    jl .cl
    mov cx, [cs_wh]
    dec cx
.cl:
    sub cx, bx
    inc cx                          ; CX = rows to trace
    jle .out
    shl bx, 1                       ; BX = the row's table offset
    mov ax, [cs_eq]
    mov dx, [cs_er]
    mov bp, [cs_edy]
    cmp byte [cs_eside], 1
    je .left
    ja .right
.both:
    cmp si, [cs_xl + bx]
    jge .n1
    mov [cs_xl + bx], si
.n1:
    cmp si, [cs_xr + bx]
    jle .n2
    mov [cs_xr + bx], si
.n2:
    add si, ax
    add di, dx
    cmp di, bp
    jb .n3
    sub di, bp
    inc si
.n3:
    inc bx
    inc bx
    loop .both
    ret
    ; the two chains, two rows an iteration: the 8088 charges a `loop` and
    ; its refill about as much as the row's own work
.left:
    shr cx, 1
    jnc .l0
    mov [cs_xl + bx], si
    add si, ax
    add di, dx
    cmp di, bp
    jb .l1
    sub di, bp
    inc si
.l1:
    inc bx
    inc bx
.l0:
    jcxz .lend
.l2:
    mov [cs_xl + bx], si
    add si, ax
    add di, dx
    cmp di, bp
    jb .l3
    sub di, bp
    inc si
.l3:
    mov [cs_xl + bx + 2], si
    add si, ax
    add di, dx
    cmp di, bp
    jb .l4
    sub di, bp
    inc si
.l4:
    add bx, 4
    loop .l2
.lend:
    ret
.right:
    shr cx, 1
    jnc .r0
    mov [cs_xr + bx], si
    add si, ax
    add di, dx
    cmp di, bp
    jb .r1
    sub di, bp
    inc si
.r1:
    inc bx
    inc bx
.r0:
    jcxz .rend
.r2:
    mov [cs_xr + bx], si
    add si, ax
    add di, dx
    cmp di, bp
    jb .r3
    sub di, bp
    inc si
.r3:
    mov [cs_xr + bx + 2], si
    add si, ax
    add di, dx
    cmp di, bp
    jb .r4
    sub di, bp
    inc si
.r4:
    add bx, 4
    loop .r2
.rend:
    ret

; -----------------------------------------------------------------------------
; cs_poly - fill one convex polygon
; in:  SI = CX pairs of (x, y) words in box coords, [cs_ink] set via
;      cs_setink, [cs_pwind] = 0 when an edge whose y INCREASES along the
;      list is on the polygon's left (the winding a visible face has), 1 the
;      other way round
; clobbers everything
; -----------------------------------------------------------------------------
cs_poly:
    mov [cs_pn], cx
    mov [cs_pvp], si
    cld
    ; --- the row range, and a cheap reject ----------------------------------
    mov bx, 0x7FFF                  ; BX = ymin, DX = ymax
    mov dx, -32768
    mov bp, 0x7FFF                  ; BP = xmin, DI = xmax
    mov di, -32768
.mm:
    lodsw
    cmp ax, bp
    jge .x1
    mov bp, ax
.x1:
    cmp ax, di
    jle .x2
    mov di, ax
.x2:
    lodsw
    cmp ax, bx
    jge .y1
    mov bx, ax
.y1:
    cmp ax, dx
    jle .y2
    mov dx, ax
.y2:
    loop .mm
    or dx, dx                       ; wholly above the view
    js .out
    cmp bx, [cs_wh]                 ; ...or below it
    jge .out
    cmp di, [cs_wx0]                ; ...or left of it
    jl .out
    cmp bp, [cs_wx1]                ; ...or right
    jg .out
    or bx, bx
    jns .t
    xor bx, bx
.t:
    cmp dx, [cs_wh]
    jl .b
    mov dx, [cs_wh]
    dec dx
.b:
    mov [cs_py0], bx
    mov [cs_py1], dx
    ; --- its bytes on those rows go to the glass, and the rows are dirty:
    ;     once for the polygon, off its bounding box -------------------------
    mov ax, bp
    cmp ax, [cs_wx0]
    jge .mx1
    mov ax, [cs_wx0]
.mx1:
    mov cx, di
    cmp cx, [cs_wx1]
    jle .mx2
    mov cx, [cs_wx1]
.mx2:
    mov [cs_pbx0], ax
    mov [cs_pbx1], cx
    push bx
    push dx
    mov dx, cx
    mov cl, [cs_kshift]
    shr ax, cl
    shr dx, cl
    mov [cs_mklo], al
    mov [cs_mkhi], dl
    pop dx
    pop bx
    mov si, bx
    mov di, dx
    call cs_markacc
    ; --- one row or two: the box IS the polygon at that size, and four
    ;     edges traced for it would cost more than the fill (SPEC.md 88.4.5)
    mov ax, dx
    sub ax, bx
    cmp ax, 1
    ja .trace
    mov si, bx
    shl si, 1
    mov ax, [cs_pbx0]
    mov cx, [cs_pbx1]
    mov [cs_xl + si], ax
    mov [cs_xr + si], cx
    cmp bx, dx
    je .rows
    mov [cs_xl + si + 2], ax
    mov [cs_xr + si + 2], cx
    jmp .rows
.trace:
    ; --- init the bounds over the rows --------------------------------------
    push ds
    pop es
    mov cx, dx
    sub cx, bx
    inc cx
    shl bx, 1
    mov di, cs_xl
    add di, bx
    mov ax, 0x7FFF
    push cx
    rep stosw
    pop cx
    mov di, cs_xr
    add di, bx
    mov ax, -32768
    rep stosw
    ; --- every edge ---------------------------------------------------------
    mov si, [cs_pvp]
    mov cx, [cs_pn]
    mov [cs_pei], cx
.e:
    mov ax, [si]
    mov bx, [si+2]
    add si, 4
    cmp word [cs_pei], 1            ; the last edge closes on vertex 0
    jne .nx
    mov si, [cs_pvp]
.nx:
    mov cx, [si]
    mov dx, [si+2]
    push si
    mov byte [cs_eside], 0          ; a horizontal edge marks both ends...
    cmp bx, dx
    je .side
    mov byte [cs_eside], 1          ; ...a descending one is on the left
    jl .desc                        ; chain and an ascending one on the
    mov byte [cs_eside], 2          ; right, or the other way round when
.desc:                              ; the winding says so
    cmp byte [cs_pwind], 0
    je .side
    xor byte [cs_eside], 3
.side:
    call cs_edge
    pop si
    dec word [cs_pei]
    jnz .e
    ; --- the rows: the backend's loop (88.4.6) -------------------------------
.rows:
    jmp [cs_rowsproc]
.out:
    ret

; cs_polyrows - the general row loop: the row's bounds clamped, its pattern
;               by XLAT, and the backend's run called with the registers it
;               wants rather than through cs_hrun's dispatch, because the
;               8088 charges for every instruction byte (SPEC.md 85.3.4)
cs_polyrows:
    mov bx, [cs_py0]
    mov di, bx
    shl di, 1
    mov di, [cs_rowoff + di]
    add di, [cs_tbase]              ; DI = the row's base
    mov es, [cs_tseg]
.row:
    mov si, bx
    shl si, 1
    mov ax, [cs_xl + si]
    mov cx, [cs_xr + si]
    cmp ax, [cs_wx0]
    jge .c1
    mov ax, [cs_wx0]
.c1:
    cmp cx, [cs_wx1]
    jle .c2
    mov cx, [cs_wx1]
.c2:
    cmp ax, cx
    jg .nrow
    push bx
    push di
    mov si, cx                      ; SI = x2, BP = x1, DL = the pattern...
    mov bp, ax
    mov al, bl
    and al, 3
    mov bx, cs_pat
    xlat
    mov dl, al
    mov bx, di                      ; ...BX = the row base
    call [cs_hrunproc]
    pop di
    pop bx
.nrow:
    add di, 80
    inc bx
    cmp bx, [cs_py1]
    jle .row
    ret

; cs_polyrows_herc - the same on Hercules with the run INLINE: no dispatch,
;                    no second address computation, the ends blended by
;                    old ^ ((old ^ pattern) & mask), and the middle a
;                    `rep stosw` on whatever alignment - the 8088's bus is
;                    eight bits wide, so an odd address costs it nothing.
;                    Measured against the general loop: 2,000 cycles a
;                    full-width row to ~1,100 (88.4.6)
cs_polyrows_herc:
    mov bx, [cs_py0]
    mov di, bx
    shl di, 1
    mov di, [cs_rowoff + di]
    add di, [cs_tbase]              ; DI = the row's base
    mov es, [cs_tseg]
.row:
    mov si, bx
    shl si, 1
    mov ax, [cs_xl + si]
    mov cx, [cs_xr + si]
    cmp ax, [cs_wx0]
    jg .c1
    cmp cx, [cs_wx1]
    jl .c1a
    ; --- the whole view row: no masks, no ends, one store - the runway
    ;     under the wheels is forty of these a frame (88.5.5) ---------------
    push bx
    push di
    mov si, bx
    and si, 3
    mov al, [cs_pat + si]
    mov ah, al
    add di, [cs_wb0]
    mov cx, [cs_wbn]
    shr cx, 1
    rep stosw
    pop di
    pop bx
    jmp short .nrow
.c1a:
    mov ax, [cs_wx0]
.c1:
    cmp cx, [cs_wx1]
    jle .c2
    mov cx, [cs_wx1]
.c2:
    cmp ax, cx
    jg .nrow
    push bx
    mov si, bx
    and si, 3
    mov dl, [cs_pat + si]           ; DL = the row's pattern
    mov si, ax
    and si, 7
    shr ax, 1
    shr ax, 1
    shr ax, 1                       ; AL = the first byte...
    mov ah, [cs_hlm + si]           ; ...AH = its mask
    mov si, cx
    and si, 7
    shr cx, 1
    shr cx, 1
    shr cx, 1                       ; CX = the last byte
    mov dh, [cs_hrm + si]           ; DH = its mask
    mov bl, al
    xor bh, bh
    add bx, di                      ; BX = the first byte's address
    sub cl, al                      ; CX = bytes - 1
    jnz .multi
    and ah, dh                      ; one byte holds both ends
    mov al, [es:bx]
    xor al, dl
    and al, ah
    xor [es:bx], al
    pop bx
    jmp short .nrow
.multi:
    mov al, [es:bx]
    xor al, dl
    and al, ah
    xor [es:bx], al                 ; the first byte
    mov si, bx
    add si, cx
    mov al, [es:si]
    xor al, dl
    and al, dh
    xor [es:si], al                 ; the last
    dec cx
    jz .done
    push di
    mov di, bx
    inc di
    mov al, dl
    mov ah, dl
    shr cx, 1
    rep stosw
    jnc .even
    stosb
.even:
    pop di
.done:
    pop bx
.nrow:
    add di, 80
    inc bx
    cmp bx, [cs_py1]
    jle .row
    ret

; -----------------------------------------------------------------------------
; cs_hrun - one masked run of the current ink, opaque
; in:  AX = x1 <= CX = x2 (box coords, inside the row), BX = the row
; clobbers everything. The row's pattern is the ink's byte for row & 3.
; -----------------------------------------------------------------------------
cs_hrun:
    mov si, bx
    and si, 3
    mov dl, [cs_pat + si]           ; DL = this row's pattern
    mov bp, ax                      ; BP = x1
    mov si, cx                      ; SI = x2
    shl bx, 1
    mov bx, [cs_rowoff + bx]
    add bx, [cs_tbase]              ; BX = the row base
    mov es, [cs_tseg]
    jmp [cs_hrunproc]

; --- the sub-byte masks the run's two ends need -------------------------------
cs_hlm:  db 0xFF, 0x7F, 0x3F, 0x1F, 0x0F, 0x07, 0x03, 0x01   ; 1bpp, pixels i..7
cs_hrm:  db 0x80, 0xC0, 0xE0, 0xF0, 0xF8, 0xFC, 0xFE, 0xFF   ; 1bpp, pixels 0..i
cs_clm:  db 0xFF, 0x3F, 0x0F, 0x03                           ; 2bpp, pixels i..3
cs_crm:  db 0xC0, 0xF0, 0xFC, 0xFF                           ; 2bpp, pixels 0..i
cs_pml:  db 0x0F, 0x0E, 0x0C, 0x08                           ; planes i..3
cs_pmr:  db 0x01, 0x03, 0x07, 0x0F                           ; planes 0..i

; in: BX = the row base, BP = x1, SI = x2, DL = the pattern, ES = the target
; A MASKED STORE, not an OR: a fill is opaque, and a white wall over the
; ground's dither has to take the dither out.
%macro CS_HRUN_SH 1                 ; %1 = 3 (1bpp) or 2 (2bpp)
    mov di, si
    mov cl, %1
    shr di, cl                      ; DI = the last byte
    mov cx, bp
    shr cx, cl                      ; ...no: CL was spent. See below
%endmacro
; (the macro above is not used - the two bodies are written out, because the
; shift count register is also the count the body wants)

cs_hrun_herc:
    mov di, si
    mov cl, 3
    shr di, cl                      ; DI = the last byte
    mov cx, bp
    shr cx, 1
    shr cx, 1
    shr cx, 1                       ; CX = the first byte
    and si, 7
    mov ah, [cs_hrm + si]           ; AH = the last byte's mask
    mov si, bp
    and si, 7
    mov al, [cs_hlm + si]           ; AL = the first byte's mask
    jmp short cs_hrun_ends
cs_hrun_cga:
    mov di, si
    shr di, 1
    shr di, 1
    mov cx, bp
    shr cx, 1
    shr cx, 1
    and si, 3
    mov ah, [cs_crm + si]
    mov si, bp
    and si, 3
    mov al, [cs_clm + si]
    jmp short cs_hrun_ends          ; (the first build fell through into the
                                    ; Hercules OR run below, and every CGA
                                    ; polygon row was a 1bpp OR at the wrong
                                    ; bytes: tests/skies.py's stale-pixel
                                    ; check is what found it - 88.4.4)
; cs_lrun_herc - the same run as an OR: a LINE on Hercules is the lit bit, so
; nothing under it needs taking out, and an OR is a read less per end byte
; than the masked store. What the slice lays its runs with (SPEC.md 85.3.3).
cs_lrun_herc:
    mov di, si
    mov cl, 3
    shr di, cl
    mov cx, bp
    shr cx, 1
    shr cx, 1
    shr cx, 1
    and si, 7
    mov ah, [cs_hrm + si]
    mov si, bp
    and si, 7
    mov al, [cs_hlm + si]
    cmp cx, di
    jne .multi
    and al, ah
    mov si, bx
    add si, cx
    or [es:si], al
    ret
.multi:
    mov si, bx
    add si, cx
    or [es:si], al
    mov si, bx
    add si, di
    or [es:si], ah
    sub di, cx
    dec di
    jz .done
    push di
    mov di, bx
    add di, cx
    inc di
    pop cx
    mov ax, 0xFFFF
    call cs_fillrun
.done:
    ret

cs_hrun_ends:                       ; CX = first byte, DI = last, AL/AH masks
    cmp cx, di
    jne .multi
    and al, ah                      ; one byte carries both ends
    mov si, bx
    add si, cx
    mov ah, al
    not ah
    and ah, [es:si]
    and al, dl
    or al, ah
    mov [es:si], al
    ret
.multi:
    mov si, bx
    add si, cx
    mov dh, al
    not dh
    and dh, [es:si]                 ; what the first byte keeps
    and al, dl
    or al, dh
    mov [es:si], al
    mov si, bx
    add si, di
    mov dh, ah
    not dh
    and dh, [es:si]
    and ah, dl
    or ah, dh
    mov [es:si], ah
    sub di, cx
    dec di
    jz .done
    push di
    mov di, bx
    add di, cx
    inc di
    pop cx                          ; CX = whole bytes between
    mov al, dl
    mov ah, dl
    call cs_fillrun
.done:
    ret

; Mode X's "mask" is a set of PLANES: the two end bytes are a map-mask write
; and a store, the middle is 0x0F and a run.
cs_hrun_modex:
    mov di, si
    shr di, 1
    shr di, 1                       ; DI = the last byte
    mov cx, bp
    shr cx, 1
    shr cx, 1                       ; CX = the first byte
    and si, 3
    mov ah, [cs_pmr + si]           ; the last byte's planes
    mov si, bp
    and si, 3
    mov al, [cs_pml + si]           ; ...and the first's
    cmp cx, di
    jne .multi
    and al, ah
    call cs_mxmask
    mov si, bx
    add si, cx
    mov [es:si], dl
    ret
.multi:
    push ax
    call cs_mxmask
    mov si, bx
    add si, cx
    mov [es:si], dl
    pop ax
    mov al, ah
    call cs_mxmask
    mov si, bx
    add si, di
    mov [es:si], dl
    sub di, cx
    dec di
    jz .done
    mov al, 0x0F
    call cs_mxmask
    push di
    mov di, bx
    add di, cx
    inc di
    pop cx
    mov al, dl
    mov ah, dl
    call cs_fillrun
.done:
    ret

; cs_mxmask - AL = the plane mask to arm. Preserves everything but flags.
cs_mxmask:
    push ax
    push dx
    mov ah, al
    mov al, 2
    mov dx, 0x3C4
    out dx, ax
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; cs_prect - an opaque rectangle in the PANEL, marked into the span
; in:  AX = x1, BX = y1, CX = x2, DX = y2 (box coords, inclusive), [cs_ink]
; clobbers everything
; -----------------------------------------------------------------------------
cs_prect:
    mov [cs_rx1], ax
    mov [cs_rx2], cx
    mov [cs_ry2], dx
.row:
    push bx
    mov ax, [cs_rx1]
    mov cx, [cs_rx2]
    call cs_markspan
    call cs_hrun
    pop bx
    inc bx
    cmp bx, [cs_ry2]
    jle .row
    ret

; -----------------------------------------------------------------------------
; cs_rect - an opaque rectangle in the VIEW, clipped, marked through the
;           object's accumulator, and laid by the backend's row loop
; in:  AX = x0, BX = y0, CX = x1, DX = y1 (box coords, inclusive), [cs_ink]
; clobbers everything
; -----------------------------------------------------------------------------
cs_rect:
    or dx, dx
    js .out                         ; wholly above the view
    cmp bx, [cs_wh]
    jge .out                        ; ...or below it
    cmp cx, [cs_wx0]
    jl .out                         ; ...or left of it
    cmp ax, [cs_wx1]
    jg .out                         ; ...or right
    or bx, bx
    jns .t
    xor bx, bx
.t:
    cmp dx, [cs_wh]
    jl .b
    mov dx, [cs_wh]
    dec dx
.b:
    cmp ax, [cs_wx0]
    jge .l
    mov ax, [cs_wx0]
.l:
    cmp cx, [cs_wx1]
    jle .r
    mov cx, [cs_wx1]
.r:
    mov [cs_py0], bx
    mov [cs_py1], dx
    push ax
    push cx
    mov dx, cx
    mov cl, [cs_kshift]
    shr ax, cl
    shr dx, cl
    mov [cs_mklo], al
    mov [cs_mkhi], dl
    mov si, bx
    mov di, [cs_py1]
    call cs_markacc
    pop cx
    pop ax
    mov si, [cs_py0]
    shl si, 1
.row:
    mov [cs_xl + si], ax
    mov [cs_xr + si], cx
    inc si
    inc si
    inc bx
    cmp bx, [cs_py1]
    jle .row
    jmp [cs_rowsproc]
.out:
    ret

; cs_markspan - AX = x1, CX = x2, BX = the row: widen the row's span pair
; to cover them. Preserves AX, BX, CX; clobbers DX, SI.
cs_markspan:
    push ax
    push cx
    mov dx, cx
    mov cl, [cs_kshift]
    shr ax, cl                      ; AX = the first byte
    shr dx, cl                      ; DX = the last
    mov si, [cs_spcur]
    cmp bx, [si - 4]                ; the set's row range takes the row
    jge .y0
    mov [si - 4], bx
.y0:
    cmp bx, [si - 2]
    jle .y1
    mov [si - 2], bx
.y1:
    mov si, bx
    shl si, 1
    add si, [cs_spcur]
    cmp [si], al
    jbe .lo
    mov [si], al
.lo:
    cmp [si+1], dl
    jae .hi
    mov [si+1], dl
.hi:
    pop cx
    pop ax
    ret

; =============================================================================
; The walk (SPEC.md 88.4.3): Tank's, without the span marks
; =============================================================================

; -----------------------------------------------------------------------------
; cs_seg - one screen-space segment: clip it to the VIEW and walk it
; in:  AX = x1, BX = y1, CX = x2, DX = y2, box coords, any magnitude to
;      +-4000; [cs_ink] set.  CLOBBERS EVERY REGISTER (SPEC.md 85.3.4)
; -----------------------------------------------------------------------------
cs_seg:
    mov si, [cs_wx0]
    mov di, [cs_wh]
    cmp ax, si
    jl .slow
    cmp ax, [cs_wx1]
    jg .slow
    or bx, bx
    js .slow
    cmp bx, di
    jge .slow
    cmp cx, si
    jl .slow
    cmp cx, [cs_wx1]
    jg .slow
    or dx, dx
    js .slow
    cmp dx, di
    jl .accept
.slow:
    mov [cs_cx1], ax
    mov [cs_cy1], bx
    mov [cs_cx2], cx
    mov [cs_cy2], dx
    mov byte [cs_ctry], 8           ; the cap is load-bearing (SPEC.md 85.3)
.again:
    dec byte [cs_ctry]
    jz .out
    mov ax, [cs_cx1]
    mov bx, [cs_cy1]
    call cs_outcode
    mov cl, al
    mov ax, [cs_cx2]
    mov bx, [cs_cy2]
    call cs_outcode
    mov ch, al
    mov al, cl
    or al, ch
    jz .clipped
    mov al, cl
    and al, ch
    jnz .out
    xor si, si
    mov al, cl
    or al, al
    jnz .pick
    mov si, 4
    mov al, ch
.pick:
    test al, 8
    jnz .bot
    test al, 4
    jnz .top
    test al, 2
    jnz .right
    mov bp, [cs_wx0]
    call cs_clip_x
    jmp short .again
.right:
    mov bp, [cs_wx1]
    call cs_clip_x
    jmp short .again
.top:
    xor bp, bp
    call cs_clip_y
    jmp short .again
.bot:
    mov bp, [cs_wh]
    dec bp
    call cs_clip_y
    jmp short .again
.clipped:
    mov ax, [cs_cx1]
    mov bx, [cs_cy1]
    mov cx, [cs_cx2]
    mov dx, [cs_cy2]
.accept:
    push ax                         ; the rows it lies on, and the bytes its
    push cx                         ; ends span, go to the glass
    cmp ax, cx
    jle .xo
    xchg ax, cx
.xo:
    push cx
    mov cl, [cs_kshift]
    shr ax, cl
    mov [cs_mklo], al
    pop ax
    shr ax, cl
    mov [cs_mkhi], al
    pop cx
    pop ax
    mov si, bx
    mov di, dx
    cmp si, di
    jle .mk
    xchg si, di
.mk:
    cmp byte [cs_wire], 0           ; a wireframe marks each segment's own
    je .acc                         ; box: its object's box is mostly empty
    call cs_markrows                ; ground the blit would carry (88.3.2)
    jmp short .mk1
.acc:
    call cs_markacc
.mk1:
    mov si, cx                      ; SI = |dx|
    sub si, ax
    jge .dxp
    neg si
.dxp:
    mov di, dx                      ; DI = |dy|
    sub di, bx
    jge .dyp
    neg di
.dyp:
    cmp si, di
    jb .steep
    ; ---- shallow: x increasing --------------------------------------------
    cmp ax, cx
    jbe .nsw
    xchg ax, cx
    xchg bx, dx
.nsw:
    mov cx, 80
    cmp dx, bx
    jae .yd
    neg cx
.yd:
    mov [cs_ystep], cx
    mov bp, di                      ; BP = e1 = 2|dy|
    shl bp, 1
    mov cx, si                      ; CX = |dx| + 1 pixels
    inc cx
    mov dx, si
    shl dx, 1
    mov [cs_e2], dx
    neg si
    mov dx, si                      ; err = -|dx|
    mov si, bx
    shl si, 1
    mov di, [cs_rowoff + si]
    add di, [cs_tbase]
    mov bx, dx
    jmp [cs_lsh]
    ; ---- steep: y increasing ----------------------------------------------
.steep:
    cmp bx, dx
    jbe .nsw2
    xchg ax, cx
    xchg bx, dx
.nsw2:
    mov byte [cs_xdir], 0
    cmp cx, ax
    jae .xd
    mov byte [cs_xdir], 1
.xd:
    mov bp, si                      ; BP = e1 = 2|dx|
    shl bp, 1
    mov cx, di                      ; CX = |dy| + 1 rows
    inc cx
    mov dx, di
    shl dx, 1
    mov [cs_e2], dx
    neg di
    mov dx, di
    mov si, bx
    shl si, 1
    mov di, [cs_rowoff + si]
    add di, [cs_tbase]
    mov bx, dx
    or bp, bp
    jz .vert
    jmp [cs_lst]
.vert:
    jmp [cs_lvt]
.out:
    ret

; cs_outcode - in AX = x, BX = y; out AL = the code. Preserves BX, CX, DX.
cs_outcode:
    push dx
    xor dl, dl
    cmp ax, [cs_wx0]
    jge .r
    or dl, 1
    jmp short .v
.r:
    cmp ax, [cs_wx1]
    jle .v
    or dl, 2
.v:
    or bx, bx
    jns .b
    or dl, 4
    jmp short .d
.b:
    cmp bx, [cs_wh]
    jl .d
    or dl, 8
.d:
    mov al, dl
    pop dx
    ret

; cs_clip_x - move endpoint SI (0 or 4) onto the vertical line x = BP
cs_clip_x:
    push si
    mov ax, [cs_cy2]
    sub ax, [cs_cy1]
    mov bx, bp
    sub bx, [cs_cx1]
    imul bx
    mov bx, [cs_cx2]
    sub bx, [cs_cx1]
    idiv bx
    add ax, [cs_cy1]
    pop si
    mov [cs_cx1 + si], bp
    mov [cs_cy1 + si], ax
    ret

; cs_clip_y - move endpoint SI onto the horizontal line y = BP
cs_clip_y:
    push si
    mov ax, [cs_cx2]
    sub ax, [cs_cx1]
    mov bx, bp
    sub bx, [cs_cy1]
    imul bx
    mov bx, [cs_cy2]
    sub bx, [cs_cy1]
    idiv bx
    add ax, [cs_cx1]
    pop si
    mov [cs_cx1 + si], ax
    mov [cs_cy1 + si], bp
    ret

; --- the walk bodies ----------------------------------------------------------
; Entered by `jmp` from cs_seg with AX = lx, DI = the row's base, BX = err,
; CX = the pixel count, BP = e1, [cs_e2]/[cs_ystep]/[cs_xdir] set. Every one
; ends in `ret`, to cs_seg's caller. DX and SI are free here - Tank's walk
; spent them on the span pair - and the CGA plot uses DL for its mask.

; the entry every walk shares: DI = the pixel's byte, AL = the ink at its
; position (AH = the wrap value; DL/DH the same for the CGA mask)
%macro CS_LENTER 1
    mov dx, ax
    shr dx, 1
    shr dx, 1
  %if %1 == 1
    shr dx, 1
  %endif
    add di, dx
    push cx
  %if %1 == 1
    mov cl, al
    and cl, 7
    mov al, 0x80
    shr al, cl
    mov ah, 0x80
  %elif %1 == 2
    and al, 3
    mov cl, al
    shl cl, 1                       ; CL = 2p: pixel 0 is bits 7..6
    mov dl, 0xC0
    shr dl, cl                      ; the mask at p
    mov ah, [cs_ink8]
    push cx
    mov cl, 6
    shl ah, cl                      ; AH = the ink at pixel 0: the wrap value
    pop cx
    mov al, ah
    shr al, cl                      ; AL = the ink at p
    mov dh, 0xC0
  %else
    and al, 3
    mov cl, al
    mov ah, 1
    shl ah, cl
    mov al, [cs_ink8]
    mov dx, 0x3C4
  %endif
    pop cx
    mov es, [cs_tseg]
%endmacro

%macro CS_PLOT 1
  %if %1 == 1
    or [es:di], al
  %elif %1 == 2
    not dl
    and [es:di], dl
    not dl
    or [es:di], al
  %else
    mov si, ax
    mov al, 2
    out dx, ax
    mov ax, si
    mov [es:di], al
  %endif
%endmacro

; x + 1 along the row; at the byte boundary the pixel wraps to the next byte
%macro CS_XFWD 1
  %if %1 == 1
    shr al, 1
    jnz %%d
    mov al, 0x80
    inc di
  %elif %1 == 2
    shr al, 1
    shr al, 1
    shr dl, 1
    shr dl, 1
    jnz %%d
    mov al, ah
    mov dl, dh
    inc di
  %else
    shl ah, 1
    cmp ah, 16
    jne %%d
    mov ah, 1
    inc di
  %endif
%%d:
%endmacro

%macro CS_XBACK 1
  %if %1 == 1
    shl al, 1
    jnz %%d
    mov al, 0x01
    dec di
  %elif %1 == 2
    shl al, 1
    shl al, 1
    shl dl, 1
    shl dl, 1
    jnz %%d
    mov al, [cs_ink8]
    mov dl, 0x03
    dec di
  %else
    shr ah, 1
    jnz %%d
    mov ah, 8
    dec di
  %endif
%%d:
%endmacro

; ---- run-length slice: a shallow line as one RUN a row (SPEC.md 85.3.6) ----
; Taken when a line lays at least eight pixels a row. Bresenham's 1985 slice:
; one `div` gives the whole step q and its remainder, each row's run is q or
; q + 1 by an error term that moves once a ROW, and the run is laid the way
; cs_hrun lays one - the backend's own run routine, called rather than jumped
; to. The first and last runs are half runs, which keeps the ends on the
; endpoints. A road across the whole view is 64 runs instead of 512 pixels.
;
; in: AX = lx, DI = the row base, CX = |dx|+1, BP = 2|dy|, [cs_ystep]
%macro CS_SLICE 0
    mov es, [cs_tseg]
    mov [cs_slx], ax                ; X = the run's first pixel
    shr bp, 1                       ; BP = |dy|
    jz %%flat
    mov ax, cx
    dec ax                          ; AX = |dx|
    xor dx, dx
    div bp                          ; AX = q, DX = the remainder
    mov [cs_slq], ax
    mov [cs_slcnt], bp              ; runs after the first: |dy|
    mov bx, bp
    shl bx, 1
    mov [cs_e2], bx                 ; the adjust-down: 2|dy|
    mov cx, dx                      ; err = rem - 2|dy|, plus |dy| for an odd q
    sub cx, bx
    test al, 1
    jz %%even
    add cx, bp
%%even:
    mov [cs_slerr], cx
    shl dx, 1
    mov bp, dx                      ; BP = the adjust-up: 2 x rem
    shr ax, 1
    inc ax                          ; the half runs: q/2 + 1 ...
    mov [cs_slfin], ax
    or dx, dx                       ; ...and the first loses one when there is
    jnz %%go                        ; nothing fractional and q is even, so the
    test byte [cs_slq], 1           ; pixel count still comes to |dx|+1
    jnz %%go
    dec ax
%%go:
    mov dx, [cs_slx]
    jmp short %%row
%%flat:
    mov ax, cx                      ; dy = 0: one run of every pixel
    mov word [cs_slcnt], 0
%%row:                              ; AX = this row's run, DX = its first x
    push bp
    push di
    mov bx, di                      ; BX = the row base
    mov si, dx
    add si, ax
    dec si                          ; SI = the run's last x
    mov bp, dx                      ; BP = its first
    add dx, ax                      ; DX = the next row's first x
    push dx
    mov dl, [cs_pat]
    call [cs_lrunproc]              ; a jump target, called: it returns here
    pop dx
    pop di
    pop bp
    add di, [cs_ystep]
    dec word [cs_slcnt]             ; runs still to come after this one
    js %%done
    jz %%fin
    mov ax, [cs_slq]
    add [cs_slerr], bp
    jle %%torow
    inc ax
    mov bx, [cs_e2]
    sub [cs_slerr], bx
%%torow:
    jmp %%row
%%fin:
    mov ax, [cs_slfin]
    jmp %%row
%%done:
    ret
%endmacro

; ---- the Hercules walks, with the per-row constants in registers ----------
; The CGA walk spends DX on its pixel mask and Mode X's on the port, so the
; general body reads e2 and the y step from memory. Hercules - the machine
; this is built against - has DX and SI free: SI = e2, DX = the y step, and
; the steep body is two bodies, one per x direction, so the x step is a
; shift and a test with no direction compare and no second jump.
; cs_slice_herc - the slice on Hercules, the run inline (88.4.6's argument
;                 again): per row two masked ORs and a `rep stosb` between,
;                 the DDA in registers - DX = the error, BP = 2 x the
;                 remainder - and nothing pushed but the run's own x
; in: AX = x, CX = pixels, BP = 2|dy|, DI = the row base, [cs_ystep]
cs_slice_herc:
    mov es, [cs_tseg]
    mov si, ax                      ; SI = x
    mov bx, di                      ; BX = the row base
    shr bp, 1                       ; BP = |dy|
    jz .flat
    mov ax, cx
    dec ax                          ; AX = |dx|
    xor dx, dx
    div bp                          ; AX = q, DX = the remainder
    mov [cs_slq], ax
    mov [cs_slcnt], bp              ; runs after the first: |dy|
    mov di, bp
    shl di, 1
    mov [cs_e2], di                 ; the adjust-down: 2|dy|
    mov cx, dx                      ; err = rem - 2|dy|, plus |dy| for an odd q
    sub cx, di
    test al, 1
    jz .even
    add cx, bp
.even:
    mov bp, dx
    shl bp, 1                       ; BP = the adjust-up: 2 x rem
    mov dx, cx                      ; DX = err
    shr ax, 1
    inc ax                          ; the half runs: q/2 + 1 ...
    mov [cs_slfin], ax
    or bp, bp                       ; ...and the first loses one when there is
    jnz .row                        ; nothing fractional and q is even, so the
    test byte [cs_slq], 1           ; pixel count still comes to |dx|+1
    jnz .row
    dec ax
    jmp short .row
.flat:
    mov ax, cx                      ; dy = 0: one run of every pixel
    mov word [cs_slcnt], 0
.row:                               ; AX = this row's run, SI = its first x
    push si
    add si, ax
    push si                         ; the next row's first x
    dec si                          ; SI = the run's last x
    mov di, si
    and di, 7
    mov ch, [cs_hrm + di]           ; CH = the last byte's mask
    shr si, 1
    shr si, 1
    shr si, 1                       ; SI = the last byte
    pop di
    pop ax                          ; AX = the first x, DI = the next row's
    push di
    mov di, ax
    and di, 7
    mov cl, [cs_hlm + di]           ; CL = the first byte's mask
    shr ax, 1
    shr ax, 1
    shr ax, 1                       ; AX = the first byte
    mov di, ax
    add di, bx                      ; DI = its address
    sub si, ax                      ; SI = bytes - 1
    jnz .multi
    and cl, ch
    or [es:di], cl
    jmp short .step
.multi:
    or [es:di], cl
    mov ax, si
    add si, di
    or [es:si], ch                  ; the last byte
    mov cx, ax
    dec cx
    jz .step
    inc di
    mov al, 0xFF
    rep stosb                       ; the whole bytes between: one to nine
.step:
    pop si                          ; SI = the next row's first x
    add bx, [cs_ystep]
    dec word [cs_slcnt]             ; runs still to come after this one
    js .done
    jz .fin
    mov ax, [cs_slq]
    add dx, bp
    jle .row
    inc ax
    sub dx, [cs_e2]
    jmp short .row
.fin:
    mov ax, [cs_slfin]
    jmp short .row
.done:
    ret

%macro CS_HWALKS 1
%1_sh:
    mov dx, bp                      ; six or more pixels a row takes the slice
    shl dx, 1
    add dx, bp
    cmp cx, dx
    jbe %%walk
    jmp cs_slice_herc
%%walk:
    CS_LENTER 1
    mov si, [cs_e2]
    mov dx, [cs_ystep]
%%spx:
    or [es:di], al
    add bx, bp
    jg %%ys
%%cont:
    shr al, 1
    jz %%nb
    loop %%spx
    ret
%%nb:
    mov al, 0x80
    inc di
    loop %%spx
    ret
%%ys:
    add di, dx
    sub bx, si
    jmp short %%cont
%1_st:
    CS_LENTER 1
    mov si, [cs_e2]
    cmp byte [cs_xdir], 0
    jne %%back
%%fwd:
    or [es:di], al
    add di, 80
    add bx, bp
    jg %%fx
    loop %%fwd
    ret
%%fx:
    sub bx, si
    shr al, 1
    jnz %%f1
    mov al, 0x80
    inc di
%%f1:
    loop %%fwd
    ret
%%back:
    or [es:di], al
    add di, 80
    add bx, bp
    jg %%bx
    loop %%back
    ret
%%bx:
    sub bx, si
    shl al, 1
    jnz %%b1
    mov al, 0x01
    dec di
%%b1:
    loop %%back
    ret
%1_vt:
    CS_LENTER 1
    mov bp, 80
%%v:
    or [es:di], al
    add di, bp
    loop %%v
    ret
%endmacro

%macro CS_WALKS 2
%2_sh:
  %if %1 != 3
    mov dx, bp                      ; six or more pixels a row - |dx| >= 6|dy|,
    shl dx, 1                       ; which is CX-1 >= 3BP - takes the slice
    add dx, bp
    cmp cx, dx
    jbe %%walk
    CS_SLICE
%%walk:
  %endif
    CS_LENTER %1
%%spx:
    CS_PLOT %1
    add bx, bp
    jg %%ys
%%cont:
    CS_XFWD %1
    loop %%spx
    ret
%%ys:
    add di, [cs_ystep]
    sub bx, [cs_e2]
    jmp short %%cont
%2_st:
    CS_LENTER %1
%%st:
    CS_PLOT %1
    add di, 80
    add bx, bp
    jg %%xs
    loop %%st
    ret
%%xs:
    cmp byte [cs_xdir], 0
    jne %%back
    CS_XFWD %1
    jmp short %%xd
%%back:
    CS_XBACK %1
%%xd:
    sub bx, [cs_e2]
    loop %%st
    ret
%2_vt:
    CS_LENTER %1
    mov bp, 80
%%v:
    CS_PLOT %1
    add di, bp
    loop %%v
    ret
%endmacro

CS_HWALKS cs_line_herc
CS_WALKS 2, cs_line_cga
CS_WALKS 3, cs_line_modex

cs_lp_herc:  dw cs_line_herc_sh, cs_line_herc_st, cs_line_herc_vt
cs_lp_cga:   dw cs_line_cga_sh, cs_line_cga_st, cs_line_cga_vt
cs_lp_modex: dw cs_line_modex_sh, cs_line_modex_st, cs_line_modex_vt

; =============================================================================
; Text in a foreign mode (SPEC.md 85.7, taken as is): the kernel's 8x8 face
; through OSAPI_FONT_GLYPHS, every run on an 8-pixel boundary, every cell
; opaque, in the panel's inks. Marks the span (the panel is the only place
; text goes).
; =============================================================================
cs_glyphs:
    call OSAPI_FONT_GLYPHS          ; DX:SI = the table, AL/AH = its range
    mov [cs_gtab], si
    mov [cs_gseg], dx
    mov [cs_gfirst], al
    mov [cs_glast], ah
    ret

; cs_text - SI = a NUL string, CX = x, DX = y (box coords); [cs_ink] = the
; ink. Preserves every register.
cs_text:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    and cl, 0xF8
.ch:
    mov al, [si]
    or al, al
    jz .done
    inc si
    push si
    push cx
    push dx
    call cs_glyph
    pop dx
    pop cx
    pop si
    add cx, 8
    cmp cx, [cs_vw]
    jl .ch
.done:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; cs_glyph - AL = the character, CX = x, DX = y.  clobbers AX, BX, CX, SI, DI, BP
cs_glyph:
    cmp al, [cs_gfirst]
    jb .out
    cmp al, [cs_glast]
    ja .out
    or dx, dx
    js .out
    mov bx, dx
    add bx, 8
    cmp bx, [cs_vh]
    jg .out
    or cx, cx
    js .out

    push cx                         ; --- stage the glyph into our segment ---
    push dx
    sub al, [cs_gfirst]
    xor ah, ah
    mov bx, ax
    shl bx, 1
    shl bx, 1
    shl bx, 1
    add bx, [cs_gtab]
    mov ax, [cs_gseg]
    push ds
    push ds
    pop es
    mov si, bx
    mov ds, ax
    mov di, cs_gbuf
    mov cx, 8
    cld
    rep movsb
    pop ds
    pop dx
    pop cx

    push cx                         ; --- the span rows and the address -----
    push dx
    mov bx, cx
    mov cl, [cs_kshift]
    shr bx, cl
    mov [cs_gcol], bx               ; the first byte of every row
    mov al, 1
    cmp byte [cs_back], CSB_HERC
    je .w
    mov al, 2
.w:
    add bl, al
    dec bl
    mov [cs_gcol2], bx              ; ...and the last
    pop dx
    pop cx

    push cx
    mov bx, dx                      ; mark eight rows of span
    shl bx, 1
    add bx, [cs_spcur]
    mov cx, 8
    mov ax, [cs_gcol]
.sp:
    cmp [bx], al
    jbe .s1
    mov [bx], al
.s1:
    push ax
    mov ax, [cs_gcol2]
    cmp [bx+1], al
    jae .s2
    mov [bx+1], al
.s2:
    pop ax
    add bx, 2
    loop .sp
    pop cx

    mov bx, dx                      ; DI = tbase + the row's base + the byte
    shl bx, 1
    mov di, [cs_rowoff + bx]
    add di, [cs_tbase]
    add di, [cs_gcol]
    mov es, [cs_tseg]
    call [cs_glyphproc]
.out:
    ret

; The three glyph stores. A set bit is the ink and a clear one the PANEL's
; ground ([cs_pbg8]); every cell is opaque.
cs_glyph_herc:                      ; the ground is 0, so the row IS the cell
    mov si, cs_gbuf
    mov cx, 8
    cld
.r:
    lodsb
    mov [es:di], al
    add di, 80
    loop .r
    ret

cs_glyph_cga:
    mov si, cs_gbuf
    mov bp, 8
    cld
.r:
    lodsb
    mov dl, al
    mov cl, 4
    shr al, cl
    xor ah, ah
    mov bx, ax
    mov ah, [cs_nib3 + bx]          ; the pixels the glyph lights, both bits
    add bx, [cs_nibp]
    mov al, [bx]                    ; ...in the ink
    not ah
    and ah, [cs_pbg8]               ; ...and the ground under the others
    or al, ah
    mov [es:di], al
    mov al, dl
    and al, 0x0F
    xor ah, ah
    mov bx, ax
    mov ah, [cs_nib3 + bx]
    add bx, [cs_nibp]
    mov al, [bx]
    not ah
    and ah, [cs_pbg8]
    or al, ah
    mov [es:di+1], al
    add di, 80
    dec bp
    jnz .r
    ret

; Mode X letters PLANE BY PLANE: a glyph's eight rows touch every plane, so
; the other way is 32 map-mask writes instead of 4.
cs_glyph_modex:
    xor bl, bl
.pl:
    mov al, 1
    mov cl, bl
    shl al, cl
    call cs_mxmask
    push di
    mov si, cs_gbuf
    mov bp, 8
.r:
    mov al, [si]
    mov cl, 7
    sub cl, bl
    mov ah, al
    shr ah, cl
    and ah, 1
    neg ah                          ; 1 -> 0FFh, 0 -> 0
    mov ch, ah
    and ah, [cs_ink8]
    not ch
    and ch, [cs_pbg8]
    or ah, ch
    mov [es:di], ah
    mov cl, 3
    sub cl, bl
    mov ah, al
    shr ah, cl
    and ah, 1
    neg ah
    mov ch, ah
    and ah, [cs_ink8]
    not ch
    and ch, [cs_pbg8]
    or ah, ch
    mov [es:di+1], ah
    inc si
    add di, 80
    dec bp
    jnz .r
    pop di
    inc bl
    cmp bl, 4
    jb .pl
    ret

; The 2bpp glyph expanders: a nibble of glyph bits to a byte of four pixels
; in colour 1, 2 or 3 (a set bit is the colour, a clear one is 0).
cs_nib1: db 0x00, 0x01, 0x04, 0x05, 0x10, 0x11, 0x14, 0x15, 0x40, 0x41, 0x44, 0x45, 0x50, 0x51, 0x54, 0x55
cs_nib2: db 0x00, 0x02, 0x08, 0x0A, 0x20, 0x22, 0x28, 0x2A, 0x80, 0x82, 0x88, 0x8A, 0xA0, 0xA2, 0xA8, 0xAA
cs_nib3: db 0x00, 0x03, 0x0C, 0x0F, 0x30, 0x33, 0x3C, 0x3F, 0xC0, 0xC3, 0xCC, 0xCF, 0xF0, 0xF3, 0xFC, 0xFF

; -----------------------------------------------------------------------------
; cs_utoa - AX in decimal at DS:DI, NUL-terminated, zero-padded to CL digits
;           (CL = 0: none). Preserves every register.
; -----------------------------------------------------------------------------
cs_utoa:
    ; STKBALANCE-LOOP: one digit pushed a turn and the second loop pops them; the count is in BP
    push ax
    push bx
    push cx
    push dx
    push di
    push bp
    xor ch, ch
    xor bp, bp
    mov bx, 10
.d:
    xor dx, dx
    div bx
    push dx
    inc bp
    or ax, ax
    jnz .d
    xor ax, ax
.pad:
    cmp bp, cx
    jae .p
    push ax
    inc bp
    jmp short .pad
.p:
    pop ax
    add al, '0'
    mov [di], al
    inc di
    dec bp
    jnz .p
    mov byte [di], 0
    pop bp
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret
