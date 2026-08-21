; =============================================================================
; os8088 - apps/wire/wire.asm
;
; WIREFRAME (SPEC.md 78): a rotating wireframe solid, drawn with nothing but
; OSAPI_GFX_LINE, one frame a tick.
;
; IT EXISTS TO BE THE THING SPEC.md 5.6.4.1 WAS BUILT FOR, and to say out loud
; whether it worked: the status strip reports the measured frame rate and how
; many line calls each frame costs, so the answer is on the glass rather than
; in a document. On the 4.77MHz 8088 this targets, the same twelve edges drawn
; and erased through 5.6.4's general walk are about 7 frames a second and
; through 5.6.4.1's about 18 - which is the tick, and therefore the ceiling.
;
; WHY IT ERASES WITH LINES AND NOT WITH A FILL. A fill of the object's box is
; cheaper - about 10ms against 23 - and it would make this a benchmark of
; gfx_fill. The point here is the line primitive, and erasing the way SPEC.md
; 48's missile trails erase is also the honest shape: only the pixels that
; were drawn are touched, which is PERFORMANCE.md rule 1 and is what keeps the
; flicker to the figure rather than the whole box.
;
; NO DILATION on the erase (SPEC.md 5.6.5). A trail is drawn in per-frame
; SEGMENTS and erased as one long line, so the two rasterisations differ; here
; every edge is drawn whole and erased whole from the same endpoint pair, so
; 5.6.2's contract makes the pixel sets identical and SI = 0 is correct. That
; is worth stating because passing 1 would cost three walks for nothing.
;
; The maths is integer and the projection is ORTHOGRAPHIC on purpose: a
; perspective divide is affordable (16 idivs a frame, ~0.6ms) but it makes the
; near corner of a rotating cube swing outside any box you size for it, and a
; cube with its corners clipped off looks broken rather than fast.
;
; Every proc is a near proc with a near ret: the kernel reaches a callback
; through the dispatcher in the package's own header (SPEC.md 20.1).
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'WIRE', wr_entry

WR_W        equ 162                 ; window, outer - near enough square,
WR_H        equ 150                 ; because the figure is sized off the
                                    ; SHORTER side and a wide box wastes the
                                    ; rest
WR_STRIP    equ 11                  ; the status strip along the bottom
WR_MARGIN   equ 2                   ; ...and the slack the object keeps from
                                    ; every edge of what is left
WR_MAXV     equ 8                   ; the biggest shape here
WR_MAXE     equ 12
WR_ASTEP    equ 3                   ; angle steps a frame, of 256 to the turn:
WR_BSTEP    equ 2                   ; coprime, so the tumble does not repeat
                                    ; every few seconds
WR_LAGMAX   equ 4                   ; ticks behind before the deadline is
                                    ; re-anchored rather than caught up
WR_FPSTICK  equ 18                  ; ...and how often the strip is re-lettered

; -----------------------------------------------------------------------------
; wr_entry - package entry point (SPEC.md 20.2)
; in:  CS=DS=ES = our own segment, IF=1, gfx lock NOT held
; out: BX = window ptr, CF clear (CF set = abort, from wm_create)
;
; The worker is NOT hired here: OSAPI_TASK_SPAWN wants the gfx lock held and
; this runs without it, and the instance is not published yet either. The
; first paint hires it, which is arkanoid's shape (SPEC.md 44).
; -----------------------------------------------------------------------------
wr_entry:
    push si
    mov si, wr_tpl
    call OSAPI_WM_CREATE
    jc .out
    mov [wr_win], bx
    mov byte [wr_size], 4           ; Medium, and the only bss byte whose zero
    call wr_pick                    ; is not the state we want
    mov si, wr_menus
    call OSAPI_MENU_SET
.out:
    pop si
    ret

; -----------------------------------------------------------------------------
; wr_geom - the content rect and where the figure sits in it
; in:  BX = window ptr, ES = KERNEL_SEG
; out: [wr_ox0]/[wr_oy0]/[wr_ow]/[wr_oh] the OBJECT area, [wr_ccx]/[wr_ccy] its
;      centre, [wr_scale] the projection scale, [wr_sy] the strip's text row
; clobbers: AX, DX, flags
;
; Re-derived every frame rather than cached, because a window can be dragged
; and SPEC.md 11.98 is the class of bug that comes from deciding once. It is
; four adds and two shifts.
;
; The scale is 1.75 x the half-extent, and that constant is the shapes'
; rather than a taste: a vertex at (48,48,48) reaches |x'| = 68 after any
; rotation, and 68 * 1.75 / 128 is 0.93 - so the figure fills the area and its
; corners stay inside it. Change the vertex magnitude and this changes with it.
; -----------------------------------------------------------------------------
wr_geom:
    push bx
    push cx
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top
    mov [wr_ox0], ax
    mov [wr_oy0], dx
    mov ax, [es:bx + W_W]
    sub ax, 2
    mov [wr_ow], ax
    mov ax, [es:bx + W_H]
    sub ax, TITLE_H + 1
    mov dx, [wr_oy0]
    add dx, ax
    sub dx, WR_STRIP - 2            ; the strip's text baseline
    mov [wr_sy], dx
    sub ax, WR_STRIP
    mov [wr_oh], ax

    mov ax, [wr_ow]                 ; the centre
    shr ax, 1
    add ax, [wr_ox0]
    mov [wr_ccx], ax
    mov ax, [wr_oh]
    shr ax, 1
    add ax, [wr_oy0]
    mov [wr_ccy], ax

    mov ax, [wr_ow]                 ; r = min(w,h)/2 - margin
    mov cx, [wr_oh]
    cmp ax, cx
    jbe .min
    mov ax, cx
.min:
    shr ax, 1
    sub ax, WR_MARGIN
    jns .rok
    xor ax, ax
.rok:
    mov cx, ax                      ; scale = 1.75r, then the View menu's
    shr ax, 1                       ; quarter: 2, 3 or 4
    add cx, ax
    shr ax, 1
    add cx, ax
    mov al, [wr_size]               ; ...and the View menu's EIGHTHS of it
    xor ah, ah
    mul cx
    shr ax, 1
    shr ax, 1
    shr ax, 1
    cmp ax, 127                     ; the projection multiplies by a BYTE
    jbe .sok
    mov ax, 127
.sok:
    mov [wr_scale], al
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; wr_sh7 - AL = DI >> 7, signed
; in:  DI = a signed 16-bit product sum, |DI| < 16384
; out: AL; AH is scratch. clobbers AX, flags
;
; `sar di,7` is 8 + 4*7 = 36 clocks on an 8088 and this is 5: one doubling
; leaves the wanted bits in AH. The bound holds because every caller sums two
; products of a +-127 byte with a +-64 one.
; -----------------------------------------------------------------------------
wr_sh7:
    mov ax, di
    add ax, ax
    mov al, ah
    ret

; -----------------------------------------------------------------------------
; wr_project - every vertex of the current shape, into wr_px / wr_py
; in:  the angles in [wr_a]/[wr_b], the geometry from wr_geom
; out: wr_px[i], wr_py[i] - screen words. clobbers everything but the segments
;
; Two rotations and an orthographic projection, all in signed bytes, with the
; two products of each term summed at 16 bits BEFORE the shift - which is
; where the precision is, and costs nothing.
; -----------------------------------------------------------------------------
wr_project:
    mov al, [wr_a]                  ; the four sines this frame needs, fetched
    xor ah, ah                      ; once rather than per vertex
    mov bx, ax
    mov al, [wr_sintab + bx]
    mov [wr_sina], al
    add bl, 64
    adc bh, 0
    and bx, 255
    mov al, [wr_sintab + bx]
    mov [wr_cosa], al
    mov al, [wr_b]
    xor ah, ah
    mov bx, ax
    mov al, [wr_sintab + bx]
    mov [wr_sinb], al
    add bl, 64
    adc bh, 0
    and bx, 255
    mov al, [wr_sintab + bx]
    mov [wr_cosb], al

    mov si, [wr_vp]                 ; the shape's vertex list
    mov di, 0                       ; ...and our index into wr_px / wr_py
    mov cl, [wr_nv]
    xor ch, ch
.vert:
    push cx
    push si
    push di
    call wr_rot                     ; -> [wr_rx], [wr_ry]
    pop di
    mov al, [wr_rx]
    imul byte [wr_scale]
    push di
    mov di, ax
    call wr_sh7
    pop di
    cbw
    add ax, [wr_ccx]
    mov [wr_px + di], ax
    mov al, [wr_ry]
    imul byte [wr_scale]
    push di
    mov di, ax
    call wr_sh7
    pop di
    cbw
    mov bx, [wr_ccy]
    sub bx, ax                      ; screen y grows DOWN and the model's up
    mov [wr_py + di], bx
    add di, 2
    pop si
    add si, 3
    pop cx
    dec cx
    jnz .vert
    ret

; -----------------------------------------------------------------------------
; wr_rot - one vertex through both rotations
; in:  SI -> three signed bytes (x, y, z)
; out: [wr_rx] = x after the Y rotation, [wr_ry] = y after the X one
; clobbers: AX, BX, DI, flags
;
; z is computed and then thrown away: an orthographic projection does not want
; it, and a depth sort is not what a wireframe is.
; -----------------------------------------------------------------------------
wr_rot:
    mov al, [si]                    ; x' = (x*cosA - z*sinA) >> 7
    imul byte [wr_cosa]
    mov di, ax
    mov al, [si+2]
    imul byte [wr_sina]
    sub di, ax
    call wr_sh7
    mov [wr_rx], al

    mov al, [si]                    ; z' = (x*sinA + z*cosA) >> 7
    imul byte [wr_sina]
    mov di, ax
    mov al, [si+2]
    imul byte [wr_cosa]
    add di, ax
    call wr_sh7
    mov bl, al

    mov al, [si+1]                  ; y' = (y*cosB - z'*sinB) >> 7
    imul byte [wr_cosb]
    mov di, ax
    mov al, bl
    imul byte [wr_sinb]
    sub di, ax
    call wr_sh7
    mov [wr_ry], al
    ret

; -----------------------------------------------------------------------------
; wr_edges - draw the shape's edges from one coordinate pair table
; in:  SI = the x table, DI = the y table, the pen already set
; out: nothing; clobbers everything but the segments
;
; ONE OSAPI_GFX_LINE PER EDGE and nothing else - which is the whole of this
; package's inner loop, and what the fps figure below is measuring.
; -----------------------------------------------------------------------------
wr_edges:
    mov bp, [wr_ep]                 ; the shape's edge list: index pairs
    mov cl, [wr_ne]
    xor ch, ch
.edge:
    push cx
    mov bx, bp
    mov al, [bx]                    ; the two vertex indices, as word offsets
    xor ah, ah
    add ax, ax
    mov bx, ax
    mov al, [bx + si]               ; ...and NOT [si+bx]: one is a base+index
    mov ah, [bx + si + 1]           ; addressing mode either way, and this is
    push ax                         ; the one NASM assembles without a warning
    mov ax, [bx + di]
    push ax
    mov bx, bp
    mov al, [bx+1]
    xor ah, ah
    add ax, ax
    mov bx, ax
    mov cx, [bx + si]
    mov dx, [bx + di]
    pop bx                          ; y1
    pop ax                          ; x1
    push si
    push di
    push bp
    xor si, si                      ; SPEC.md 5.6.5: thin, both ways - see the
    call OSAPI_GFX_LINE             ; header
    pop bp
    pop di
    pop si
    add bp, 2
    pop cx
    dec cx
    jnz .edge
    ret

; -----------------------------------------------------------------------------
; wr_draw - erase the frame on the glass, then draw the new one
; in:  ES = KERNEL_SEG, the gfx lock held, the clip armed, wr_px/wr_py current
; out: nothing; clobbers everything but the segments
;
; The order is erase-then-draw and the two are the SAME pixel set at the same
; endpoints, so a pixel the new frame keeps is written twice - which is
; PERFORMANCE.md rule 2's violation, and is the price of not keeping a second
; buffer on a machine with 640KB and no blitter. It is what SPEC.md 48's
; trails do for the same reason.
; -----------------------------------------------------------------------------
wr_draw:
    cmp byte [wr_shown], 0
    je .fresh
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov si, wr_ex
    mov di, wr_ey
    call wr_edges
.fresh:
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov si, wr_px
    mov di, wr_py
    call wr_edges
    call wr_keep
    ret

; wr_keep - the frame now on the glass is the one to erase next time
wr_keep:
    push cx
    push si
    push di
    mov si, wr_px
    mov di, wr_ex
    mov cx, WR_MAXV * 2
    call wr_copy
    mov si, wr_py
    mov di, wr_ey
    mov cx, WR_MAXV * 2
    call wr_copy
    mov byte [wr_shown], 1
    pop di
    pop si
    pop cx
    ret

; wr_copy - CX bytes from SI to DI, both in our own segment
; movsb IS NOT AVAILABLE: ES is the kernel's on every callback (SPEC.md 20.1)
wr_copy:
    push ax
.b:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    dec cx
    jnz .b
    pop ax
    ret

; -----------------------------------------------------------------------------
; wr_strip - the status line: how many lines a frame, and how fast
; in:  the gfx lock held, the geometry derived
; out: nothing; preserves nothing but the segments
; -----------------------------------------------------------------------------
wr_strip:
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov ax, [wr_ox0]
    mov bx, [wr_sy]
    dec bx
    mov cx, ax
    add cx, [wr_ow]
    dec cx
    mov dx, bx
    add dx, 9
    call OSAPI_GFX_FILL
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov di, wr_line                 ; "NN lines  NN.N fps"
    mov al, [wr_ne]
    xor ah, ah
    call wr_dec
    mov si, wr_s_lines
    call wr_cat
    mov ax, [wr_fps]
    push ax
    mov bx, 10
    xor dx, dx
    div bx
    call wr_dec                     ; the whole part
    mov byte [di], '.'
    inc di
    pop ax
    mov bx, 10
    xor dx, dx
    div bx
    mov al, dl                      ; ...and the tenth
    xor ah, ah
    call wr_dec
    mov si, wr_s_fps
    call wr_cat
    mov byte [di], 0
    mov cx, [wr_ox0]
    mov dx, [wr_sy]
    mov si, wr_line
    call OSAPI_FONT_STR
    ret

; wr_dec - AX (0..65535) as decimal at DI, no padding. DI advances.
wr_dec:
    push bx
    push cx
    push dx
    mov cx, 0
    mov bx, 10
.split:
    xor dx, dx
    div bx
    push dx
    inc cx
    or ax, ax
    jnz .split
.emit:
    pop ax
    add al, '0'
    mov [di], al
    inc di
    dec cx
    jnz .emit
    pop dx
    pop cx
    pop bx
    ret

; wr_cat - the NUL string at SI onto DI (the NUL is not copied). DI advances.
wr_cat:
    push ax
.c:
    mov al, [si]
    or al, al
    jz .out
    mov [di], al
    inc di
    inc si
    jmp short .c
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; wr_paint - W_PAINT: the whole content, from scratch
; in:  SI = window ptr; the gfx lock held, ES = KERNEL_SEG
; out: nothing; preserves all registers
; -----------------------------------------------------------------------------
wr_paint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov bx, si
    call wr_geom
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov ax, [wr_ox0]
    mov bx, [wr_oy0]
    mov cx, ax
    add cx, [wr_ow]
    dec cx
    mov dx, bx
    add dx, [wr_oh]
    add dx, WR_STRIP - 1
    call OSAPI_GFX_FILL
    call wr_project                 ; the window may have moved since the last
    mov byte [wr_shown], 0          ; frame, so the kept coordinates are stale
    call wr_draw
    call wr_strip
    call wr_hire
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; wr_hire - spawn the worker, once. The gfx lock must be held (SPEC.md 20.6).
; A refusal is transient - the task table holds twelve - so nothing is latched
; and the next paint tries again.
; -----------------------------------------------------------------------------
wr_hire:
    push ax
    push bx
    cmp byte [wr_hired], 0
    jne .out
    mov ax, wr_worker
    mov bx, [wr_win]
    call OSAPI_TASK_SPAWN
    jc .out
    mov byte [wr_hired], 1
.out:
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; wr_worker - THE background task (SPEC.md 20.6)
; in:  DX = our instance index, DS = ES = CS = our segment, IF = 1, gfx lock
;      free. Never returns: OSAPI_TASK_ALIVE not coming back is the way out.
;
; One frame a tick, arkanoid's deadline shape exactly - and on this machine the
; tick is also the ceiling, so a frame that fits it is a frame that shows.
; -----------------------------------------------------------------------------
wr_worker:
    call OSAPI_GET_TICKS
    mov [wr_due], ax
    mov [wr_ft0], ax
.loop:
    mov bx, [wr_win]
    call OSAPI_TASK_ALIVE           ; the lock must NOT be held here (rule 4)
    inc word [wr_due]
    call OSAPI_GET_TICKS
    mov bx, [wr_due]
    sub bx, ax                      ; signed, and wrap-safe by subtraction
    jle .behind
    mov ax, bx
    call OSAPI_TASK_SLEEP
    jmp short .frame
.behind:
    cmp bx, -WR_LAGMAX
    jg .frame
    mov [wr_due], ax                ; hopelessly late: re-anchor, or the
.frame:                             ; deadline runs away and this never sleeps
    add byte [wr_a], WR_ASTEP
    add byte [wr_b], WR_BSTEP
    call wr_render
    jmp .loop

; -----------------------------------------------------------------------------
; wr_render - one frame on the glass
; in:  nothing; the gfx lock free. Preserves all registers.
; -----------------------------------------------------------------------------
wr_render:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    call OSAPI_GFX_LOCK
    mov ax, KERNEL_SEG
    mov es, ax
    mov bx, [wr_win]
    test word [es:bx + W_FLAGS], 2  ; still visible?
    jz .unlock
    call wr_geom
    mov bx, [wr_win]
    call OSAPI_WM_CLIP_SET          ; over 16 fragments: skip the frame rather
    jc .unlock                      ; than draw over whatever is on top
    call wr_project
    call wr_draw
    inc word [wr_frames]
    call OSAPI_GET_TICKS
    mov bx, ax
    sub ax, [wr_ft0]
    cmp ax, WR_FPSTICK
    jb .done
    call wr_fpsup                   ; AX = ticks elapsed, BX = now
.done:
    call OSAPI_WM_CLIP_CLEAR
.unlock:
    call OSAPI_GFX_UNLOCK
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
; wr_fpsup - frames over ticks, as tenths, and re-letter the strip
; in:  AX = ticks elapsed (>= WR_FPSTICK), BX = the tick count now
; out: nothing; clobbers everything but the segments
;
; 18.2 ticks a second (SPEC.md 8), so tenths = frames * 182 / ticks. The
; multiply cannot overflow: a frame a tick is the ceiling, so frames <= ticks
; and the product is at most 182 * ticks with ticks small.
; -----------------------------------------------------------------------------
wr_fpsup:
    mov cx, ax
    mov [wr_ft0], bx
    mov ax, [wr_frames]
    mov word [wr_frames], 0
    mov bx, 182
    mul bx
    div cx
    mov [wr_fps], ax
    call wr_strip
    ret

; -----------------------------------------------------------------------------
; wr_oncmd - AM_ONCMD: the Shape and View menus (SPEC.md 12.2)
; in:  AL = item, AH = menu (0 = Shape, 1 = View), SI = window, BX = menu set
; out: nothing
;
; On the UI task with the lock held, exactly like a click. Both menus end in a
; full repaint because the figure changes size or shape and the kept
; coordinates no longer describe what is on the glass.
; -----------------------------------------------------------------------------
wr_oncmd:
    push si
    or ah, ah
    jnz .view
    cmp al, WR_NSHAPE
    jae .out
    mov [wr_shape], al
    call wr_pick
    jmp short .redraw
.view:
    cmp al, 3
    jae .out                        ; item 3 is About, and does nothing yet
    xor ah, ah                      ; Small / Medium / Large, in eighths of
    mov bx, ax                      ; wr_geom's 1.75r. MEDIUM IS THE TICK: it
    mov al, [wr_eighths + bx]       ; is chosen so a frame fits 55ms on the
    mov [wr_size], al               ; 4.77MHz 8088 (SPEC.md 78), and Large is
                                    ; there to push past it and watch the
                                    ; number in the strip move
.redraw:
    call wr_paint                   ; SI is still the window
.out:
    pop si
    ret

; -----------------------------------------------------------------------------
; wr_pick - point wr_vp/wr_ep/wr_nv/wr_ne at [wr_shape]'s record
; preserves all registers
; -----------------------------------------------------------------------------
wr_pick:
    push ax
    push bx
    mov al, [wr_shape]
    xor ah, ah
    mov bx, ax
    add ax, ax
    add ax, ax
    add ax, bx
    add ax, bx                      ; 6 bytes a record
    mov bx, ax
    mov ax, [wr_shapes + bx]
    mov [wr_vp], ax
    mov ax, [wr_shapes + bx + 2]
    mov [wr_ep], ax
    mov al, [wr_shapes + bx + 4]
    mov [wr_nv], al
    mov al, [wr_shapes + bx + 5]
    mov [wr_ne], al
    pop bx
    pop ax
    ret

; --- window template (SPEC.md 11: 16 bytes, 8 words) --------------------------
wr_tpl:
    dw 96, 32, WR_W, WR_H
    dw wr_ttl, wr_paint, 0, 0       ; no onkey, no onclick: it just spins

; --- the app menu set (SPEC.md 12.2) ------------------------------------------
    OS88_MENUSET wr_menus, wr_name, wr_oncmd
        OS88_MENU wr_m_shape, wr_i_shape, WR_NSHAPE
        OS88_MENU wr_m_view,  wr_i_view,  4
    OS88_MENUSET_END wr_menus

wr_name:    db 'Wire', 0
wr_m_shape: db 'Shape', 0
wr_i_shape: dw wr_it_cube, wr_it_oct, wr_it_tet
wr_it_cube: db 'Cube', 0
wr_it_oct:  db 'Octahedron', 0
wr_it_tet:  db 'Tetrahedron', 0
wr_m_view:  db 'View', 0
wr_i_view:  dw wr_it_sm, wr_it_md, wr_it_lg, wr_it_abt
wr_it_sm:   db 'Small', 0
wr_it_md:   db 'Medium', 0
wr_it_lg:   db 'Large', 0
wr_it_abt:  db 'About', 0

wr_eighths: db 3, 4, 6          ; Small, Medium, Large
wr_ttl:     db 'Wireframe', 0
wr_s_lines: db ' lines  ', 0
wr_s_fps:   db ' fps', 0

; --- the shapes ----------------------------------------------------------------
; Vertices are three SIGNED BYTES each and every magnitude here is 48 or 64;
; wr_geom's 1.75 scale is derived from the 48, so a new shape wanting a bigger
; one has to say so there too.
WR_NSHAPE   equ 3

wr_shapes:
    dw wr_cube_v, wr_cube_e
    db 8, 12
    dw wr_oct_v,  wr_oct_e
    db 6, 12
    dw wr_tet_v,  wr_tet_e
    db 4, 6

wr_cube_v:
    db -48,-48,-48
    db  48,-48,-48
    db  48, 48,-48
    db -48, 48,-48
    db -48,-48, 48
    db  48,-48, 48
    db  48, 48, 48
    db -48, 48, 48
wr_cube_e:
    db 0,1, 1,2, 2,3, 3,0
    db 4,5, 5,6, 6,7, 7,4
    db 0,4, 1,5, 2,6, 3,7

wr_oct_v:
    db  64,  0,  0
    db -64,  0,  0
    db   0, 64,  0
    db   0,-64,  0
    db   0,  0, 64
    db   0,  0,-64
wr_oct_e:
    db 0,2, 0,3, 0,4, 0,5
    db 1,2, 1,3, 1,4, 1,5
    db 2,4, 4,3, 3,5, 5,2

wr_tet_v:
    db  48, 48, 48
    db  48,-48,-48
    db -48, 48,-48
    db -48,-48, 48
wr_tet_e:
    db 0,1, 0,2, 0,3, 1,2, 1,3, 2,3

; --- sin(2*pi*i/256) * 127, signed. cos(a) is sin(a+64). ----------------------
wr_sintab:
%include "wiresin.inc"

    OS88_BSS 144
    OS88_IMAGE_END

; --- loader-zeroed bss (SPEC.md 21 step 5) ------------------------------------
; ZERO IS A WORKING STATE for all of it but the shape pointers and the size,
; which wr_first fixes before anything reads them.
wr_win      equ os88_image_end + 0    ; word
wr_hired    equ os88_image_end + 2    ; byte
wr_shown    equ os88_image_end + 3    ; byte: is there a frame to erase?
wr_shape    equ os88_image_end + 4    ; byte
wr_size     equ os88_image_end + 5    ; byte: quarters, 2..4
wr_a        equ os88_image_end + 6    ; byte: the two angles, 256 to the turn
wr_b        equ os88_image_end + 7    ; byte
wr_due      equ os88_image_end + 8    ; word
wr_ft0      equ os88_image_end + 10   ; word: the fps window's start tick
wr_frames   equ os88_image_end + 12   ; word
wr_fps      equ os88_image_end + 14   ; word: TENTHS
wr_ox0      equ os88_image_end + 16   ; word: the object area
wr_oy0      equ os88_image_end + 18
wr_ow       equ os88_image_end + 20
wr_oh       equ os88_image_end + 22
wr_ccx      equ os88_image_end + 24   ; word: its centre
wr_ccy      equ os88_image_end + 26
wr_sy       equ os88_image_end + 28   ; word: the strip's text row
wr_scale    equ os88_image_end + 30   ; byte
wr_rx       equ os88_image_end + 31   ; byte: wr_rot's two outputs
wr_ry       equ os88_image_end + 32
wr_sina     equ os88_image_end + 33   ; byte: this frame's four sines
wr_cosa     equ os88_image_end + 34
wr_sinb     equ os88_image_end + 35
wr_cosb     equ os88_image_end + 36
wr_nv       equ os88_image_end + 37   ; byte
wr_ne       equ os88_image_end + 38   ; byte
wr_vp       equ os88_image_end + 40   ; word
wr_ep       equ os88_image_end + 42   ; word
wr_px       equ os88_image_end + 44   ; WR_MAXV words: this frame
wr_py       equ os88_image_end + 60
wr_ex       equ os88_image_end + 76   ; ...and the one on the glass
wr_ey       equ os88_image_end + 92
wr_line     equ os88_image_end + 108  ; the strip's composed text, 32 bytes
