; =============================================================================
; os8088 - tests/gfxbench/gfxbench.asm
;
; GFXBENCH: every drawing primitive the OS publishes, priced on the adapter it
; is booted on, plus the raw memory and framebuffer bandwidth underneath them.
; It is the harness PERFORMANCE.md Part 2's calibration table wants and did not
; have: two of its fifteen figures are measured (a glyph cell, and a
; framebuffer read-modify-write quoted at "~30 cycles") and the rest are
; estimated from them.
;
; ONE package for Hercules AND CGA, deliberately. Both are 1bpp banked
; framebuffers driven by the same software renderer (SPEC.md 39.3); what
; differs is four numbers, and those come from OSAPI_VIDEO at run time. Two
; sources would be two chances to drift, and the whole value of the exercise is
; that the Hercules column and the CGA column are the SAME measurement. It runs
; on VGA too, where it prices the planar path for contrast.
;
;   make bench
;   make test VIDEO=herc HERCSEG=0x7000 TESTAPPS=build/bench.img
;   make test VIDEO=cga                 TESTAPPS=build/bench.img
;
; ...but see PERFORMANCE.md Part 3 and Part 4 before quoting anything from a
; QEMU run: the microsecond column there is the HOST's speed. Under
; `-icount shift=3,sleep=off` the counts column is guest INSTRUCTIONS, which is
; reproducible and machine-independent and is not time. build/bench360.img on a
; real 4.77 MHz 8088 is where these numbers mean what they say.
;
; --- what it measures, and why in that shape ---------------------------------
;
; RAW BANDWIDTH comes first because everything above it is explained by it. The
; same loop shape - 32 rows of 64 bytes, 2,048 bytes an iteration - runs
; against plain RAM and against the framebuffer, so the ratio between the two
; rows IS the bus penalty, with the loop, the segment override and the
; addressing identical on both sides. Four accesses are priced (word write,
; byte write, word read, byte read-modify-write) because the kernel's inner
; loops use all four and on an 8-bit bus they are not proportional.
;
; PRIMITIVES are measured AT TWO SIZES wherever the cost has a per-call part
; and a per-pixel part - 8x8 against 64x64, 8 px against 256 px. One size
; cannot separate them, and pricing a rect this harness never drew needs both
; terms. The DERIVED block does that subtraction so the reader does not have
; to, and prints its inputs beside it so the reader can check that it did.
;
; TEXT is measured at the same ten characters as tests/fontbench, on purpose:
; fontbench's published figures (SPEC.md 6.1.1) are then a free cross-check on
; this harness, and PERFORMANCE.md Part 6 rule 7 is that a harness reporting
; one number per run is one you have to trust.
;
; --- what it will NOT do -----------------------------------------------------
;
; It never calls OSAPI_WM_SHOW/HIDE/FRONT or OSAPI_GFX_LOCK. Everything here
; runs inside a window callback, which already holds the gfx lock (SPEC.md
; 12.3), and the lock is not reentrant - so those are a deadlock, not a slow
; row. The composite costs they would have measured (SPEC.md 11.90/11.91) are
; the kernel's own and belong to a counter in the kernel, not to a package.
;
; It draws only inside its own content rect and repaints it afterwards. The raw
; framebuffer rows write to the byte columns their own content occupies,
; computed with the same banked arithmetic gfx_rowbase uses - so a wrong
; adapter record scribbles this window and nothing else.
;
; Prefix gb_.
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'GFXBENCH', gb_entry

GB_BOXW     equ 256               ; the drawing sandbox, in pixels. Fixed and
GB_BOXH     equ 128               ; not derived from the window, so the same
                                  ; row on two adapters is the same work. It
                                  ; fits the CGA content (622 x 136), which is
                                  ; the smallest of the three
GB_BWROWS   equ 32                ; bandwidth: rows per iteration...
GB_BWCOLS   equ 64                ; ...and bytes per row. 2,048 bytes, which is
                                  ; a few milliseconds on the target and so
                                  ; nowhere near the 55 ms PIT wrap
GB_BWBYTES  equ GB_BWROWS * GB_BWCOLS
GB_BLITW    equ 64                ; the blit source, 4bpp packed
GB_BLITH    equ 64
GB_BLITS    equ GB_BLITW / 2      ; ...its stride in bytes
GB_BLITSZ   equ GB_BLITS * GB_BLITH

GB_VSMAX    equ 60000             ; retrace-poll bound. A dead status port must
                                  ; time out, never hang: the Linux-RTC bug
                                  ; SPEC.md 37.90 records, in miniature

; -----------------------------------------------------------------------------
; gb_entry - package entry (SPEC.md 20.2)
; in:  CS=DS=ES = our own segment; gfx lock NOT held
; out: BX = window ptr, CF set = refused
; -----------------------------------------------------------------------------
gb_entry:
    push si
    call gb_facts                   ; the machine's own numbers, before there
    mov si, gb_tpl                  ; is a window to draw them in
    call OSAPI_WM_CREATE
    jc .out
    mov [gb_win], bx
    mov al, 1
    call OSAPI_WM_SNAP              ; mono only, a no-op on VGA - and it
                                    ; PRESERVES FLAGS, so the CF this proc
                                    ; owes the loader survives it
    mov si, gb_menus
    call OSAPI_MENU_SET
    mov si, gb_onabout
    call OSAPI_ABOUT_SET
    clc
.out:
    pop si
    ret                             ; NEAR: the kernel reaches every proc here
                                    ; through our own dispatcher (SPEC.md 20.1)

; -----------------------------------------------------------------------------
; gb_paint - W_PAINT: the report page. The content arrives white.
; in:  SI = window ptr; gfx lock held
; -----------------------------------------------------------------------------
gb_paint:
    call bl_paint
    ret

; -----------------------------------------------------------------------------
; gb_onkey - W_ONKEY: R runs, S saves, everything else pages
; in:  AL = ascii, AH = scan, SI = window ptr; gfx lock held
; -----------------------------------------------------------------------------
gb_onkey:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov [gb_win], si
    mov bl, al
    or bl, 0x20                     ; fold the case; a cursor key has AL = 0
    cmp bl, 'r'                     ; and matches neither of these
    je .run
    cmp bl, 's'
    je .save
    call bl_key                     ; AL/AH still as they arrived
    jc .out
    call bl_paint
    jmp short .out
.run:
    call gb_run
    call gb_repaint
    jmp short .out
.save:
    call gb_save
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
; gb_onclick - W_ONCLICK: a click pages down, so the harness can be driven
;              without a keyboard (the QMP mouse is the scripted path)
; in:  CX = x, DX = y, SI = window ptr; gfx lock held
; -----------------------------------------------------------------------------
gb_onclick:
    push ax
    push si
    mov [gb_win], si
    mov al, ' '
    xor ah, ah
    call bl_key
    jc .out
    call bl_paint
.out:
    pop si
    pop ax
    ret

; -----------------------------------------------------------------------------
; gb_oncmd - the menu handler (SPEC.md 12.2): AL = item, AH = menu, SI = window
; -----------------------------------------------------------------------------
gb_oncmd:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov [gb_win], si
    or ah, ah
    jnz .out
    cmp al, 0
    je .run
    cmp al, 1
    je .save
    cmp al, 2
    je .top
    jmp short .out
.run:
    call gb_run
    call gb_repaint
    jmp short .out
.save:
    call gb_save
    call bl_paint
    jmp short .out
.top:
    mov word [bl_top], 0
    call bl_paint
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; gb_onabout - the About item just returns to the top of the report, which is
; where the provenance lines are. A callback must repaint itself.
gb_onabout:
    push si
    mov word [bl_top], 0
    call bl_paint
    pop si
    ret

; -----------------------------------------------------------------------------
; gb_save - write the report, under a name that says which adapter made it
; -----------------------------------------------------------------------------
gb_save:
    push ax
    push si
    mov si, gb_f_vga
    cmp byte [gb_kind], VID_HERC
    jne .cga
    mov si, gb_f_herc
    jmp short .go
.cga:
    cmp byte [gb_kind], VID_CGA
    jne .go
    mov si, gb_f_cga
.go:
    call bl_save
    pop si
    pop ax
    ret

; -----------------------------------------------------------------------------
; gb_repaint - erase what the run scribbled, then redraw the page
; in:  [gb_win]; gfx lock held
; -----------------------------------------------------------------------------
gb_repaint:
    push ax
    push bx
    push cx
    push dx
    push si
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov bx, [gb_win]
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top
    mov bx, dx
    mov cx, ax
    add cx, [gb_cw]
    dec cx
    add dx, [gb_ch]
    dec dx
    call OSAPI_GFX_FILL
    mov si, [gb_win]
    call bl_paint
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; gb_facts - the machine's own numbers, banked at entry
; =============================================================================
gb_facts:
    push ax
    push bx
    push cx
    push dx
    push di
    push es
    call OSAPI_VIDEO                ; AX = w, BX = h, CX = first dock row,
    mov [gb_vw], ax                 ; DL = kind, DH = bpp
    mov [gb_vh], bx
    mov [gb_dock], cx
    mov [gb_kind], dl
    mov [gb_bpp], dh
    call OSAPI_CPU_INFO             ; AL = tier, AH = feature bits
    mov [gb_cpu], ax
    call OSAPI_MEM_AVAIL            ; AX = largest run KB, BX = total free KB
    mov [gb_mlarge], ax
    mov [gb_mtotal], bx
    push ds
    pop es
    mov di, gb_syskb
    call OSAPI_SYS_KB
    pop es
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; gb_run - the whole suite
; in:  [gb_win]; gfx lock HELD (this is a callback)
; =============================================================================
gb_run:
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    mov word [bl_nrow], 0           ; a re-run replaces the report rather than
    mov word [bl_used], 0           ; appending to it
    mov word [bl_top], 0
    mov byte [bl_full], 0

    call gb_geom                    ; the sandbox, from the LIVE window
    call gb_mktab                   ; the adapter record and the row tables
    call gb_mkblit                  ; the two blit sources
    call bl_baseline                ; ...and the loop overhead every P row is
    mov [gb_bcnt], ax               ; reported net of
    mov [gb_bcnt+2], dx

    call gb_header
%ifndef GB_ONLYHEAD
    call gb_bw
    call gb_prims
    call gb_text
    call gb_api
    call gb_composite
    call gb_derived
%endif
    call gb_trailer

    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; gb_geom - the sandbox rect, from the live window (SPEC.md 39.7: wm_fit has
;           already clamped the template onto whatever screen this is)
; -----------------------------------------------------------------------------
gb_geom:
    push ax
    push bx
    push cx
    push dx
    mov bx, [gb_win]
    call OSAPI_WM_GEOM              ; CX = content w, DX = content h
    mov [gb_cw], cx
    mov [gb_ch], dx
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top
    mov [gb_cx], ax
    mov [gb_cy], dx
    add ax, 7                       ; the aligned x: content left rounded UP,
    and ax, 0xFFF8                  ; so font_run's fast path and the byte
    mov [gb_x], ax                  ; column of the raw rows agree
    mov [gb_tx], ax
    mov [gb_y], dx
    mov ax, [gb_cw]                 ; the page geometry bl_paint would compute -
    mov cl, 3                       ; done here too, so the header block can
    shr ax, cl                      ; report it before the first repaint
    cmp ax, BL_MAXLINE
    jbe .c
    mov ax, BL_MAXLINE
.c:
    mov [bl_vcols], ax
    mov ax, [gb_ch]
    shr ax, cl
    mov [bl_vrows], ax
    or ax, ax
    jz .r
    dec ax
.r:
    mov [bl_prows], ax
    call gb_boxfull
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; gb_rowbase - the framebuffer offset of scan line AX (SPEC.md 39.3)
; in:       AX = y
; out:      AX = byte offset
; clobbers: AX, CX, DX, flags
;
; gfx_rowbase's arithmetic, in the package: bank = y & bmask, and the row
; within that bank is y >> bshift. The kernel's copy is not reachable through
; the API and there is no slot that answers "where is scan line y", so a
; package that wants to touch the framebuffer has to carry this - which is
; exactly why the rows built from it are confined to this window's own columns.
; -----------------------------------------------------------------------------
gb_rowbase:
    push bx
    mov bx, ax
    and bx, [gb_bmask]              ; BX = the bank
    mov cl, 13
    shl bx, cl                      ; ...times 0x2000
    mov cl, [gb_bshift]
    shr ax, cl                      ; AX = the row inside it
    mul word [gb_stride]            ; DX:AX; DX is 0 at every geometry here
    add ax, bx
    pop bx
    ret

; -----------------------------------------------------------------------------
; gb_mktab - pick the adapter record and fill the two bandwidth row tables
; -----------------------------------------------------------------------------
gb_mktab:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov al, [gb_kind]               ; the adapter record: seg, stride, bmask,
    xor ah, ah                      ; bshift - vid_tab's four numbers, which a
    mov bx, 8                       ; package has no other way to learn
    mul bx
    mov si, gb_vtab
    add si, ax
    mov bx, [si]
    mov [gb_fbseg], bx
    mov bx, [si+2]
    mov [gb_stride], bx
    mov bx, [si+4]
    mov [gb_bmask], bx
    mov bx, [si+6]
    mov [gb_bshift], bx
    shr ax, 1                       ; the status-port record is 4 bytes
    mov si, gb_ptab
    add si, ax
    mov bx, [si]
    mov [gb_stat], bx
    mov bx, [si+2]
    mov [gb_vsbit], bx

    mov ax, [gb_x]                  ; the byte column our content starts at
    mov cl, 3
    shr ax, cl
    mov [gb_xbyte], ax

    mov di, gb_vrow                 ; --- the framebuffer table. SI is the row
    mov si, GB_BWROWS               ; counter and NOT cx, because gb_rowbase
    mov bx, [gb_y]                  ; loads two shift counts into CL: a `loop`
.v:                                 ; here ran 65,536 times and wrote a word
    mov ax, bx                      ; every two bytes across the whole segment
    call gb_rowbase
    add ax, [gb_xbyte]
    mov [di], ax
    add di, 2
    inc bx
    dec si
    jnz .v

    mov di, gb_rrow                 ; --- and the RAM one, the same shape so
    mov cx, GB_BWROWS               ; the two only differ in the segment
    mov ax, gb_ram
.r:
    mov [di], ax
    add di, 2
    add ax, GB_BWCOLS
    loop .r
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; gb_mkblit - build the two 4bpp blit sources (SPEC.md 5.4)
;
; SOLID is one run per row: the best case gfx_blit4's run coalescing was
; written for. STRIPE is a new colour every four pixels - sixteen runs a row,
; which is what a picture costs. The PAIR is the point: PERFORMANCE.md Part 3
; item 4 is a version of this primitive that kept its shape and lost its
; substance, and one number cannot show that. Two can.
; -----------------------------------------------------------------------------
gb_mkblit:
    push ax
    push bx
    push cx
    push dx
    push di
    push es
    push ds
    pop es
    cld
    mov di, gb_bsolid
    mov cx, GB_BLITSZ
    mov al, 0xFF                    ; two pixels of colour 15 per byte
    rep stosb
    mov di, gb_bstripe
    mov cx, GB_BLITSZ
    xor bx, bx                      ; BX = the byte index
.s:
    mov ax, bx
    shr ax, 1                       ; two bytes - four pixels - per colour
    and ax, 15
    mov dl, 0x11                    ; ...and both nibbles that colour
    mul dl                          ; AX = colour * 0x11, always under 256
    stosb
    inc bx
    loop .s
    pop es
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; the report blocks
; =============================================================================

gb_header:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov si, gb_s_ttl1
    call bl_sline
    mov si, gb_s_ttl2
    call bl_sline
    call bl_blank

    mov si, gb_l_adapter            ; the adapter, named
    mov di, gb_n_vga
    cmp byte [gb_kind], VID_HERC
    jne .c1
    mov di, gb_n_herc
.c1:
    cmp byte [gb_kind], VID_CGA
    jne .c2
    mov di, gb_n_cga
.c2:
    call bl_kvs
    mov si, gb_l_screen
    mov ax, [gb_vw]
    call gb_num
    mov si, gb_l_rows
    mov ax, [gb_vh]
    call gb_num
    mov si, gb_l_bpp
    mov al, [gb_bpp]
    xor ah, ah
    call gb_num
    mov si, gb_l_dock
    mov ax, [gb_dock]
    call gb_num
    mov si, gb_l_fbseg
    mov ax, [gb_fbseg]
    call gb_hex
    mov si, gb_l_stride
    mov ax, [gb_stride]
    call gb_num
    mov si, gb_l_banks
    mov ax, [gb_bmask]
    inc ax
    call gb_num
    mov si, gb_l_stat
    mov ax, [gb_stat]
    call gb_hex

    mov si, gb_l_conw               ; the window the numbers were taken in
    mov ax, [gb_cw]
    call gb_num
    mov si, gb_l_conh
    mov ax, [gb_ch]
    call gb_num
    mov si, gb_l_cells
    mov ax, [bl_vcols]
    call gb_num
    mov si, gb_l_crows
    mov ax, [bl_prows]
    call gb_num
    mov si, gb_l_boxx
    mov ax, [gb_x]
    call gb_num

    mov si, gb_l_cpu                ; and the machine
    mov al, [gb_cpu]
    xor ah, ah
    call gb_num
    mov si, gb_l_feat
    mov al, [gb_cpu+1]
    xor ah, ah
    call gb_hex
    mov si, gb_l_kern
    mov ax, [gb_syskb + SK_KERN]
    call gb_num
    mov si, gb_l_heap
    mov ax, [gb_syskb + SK_HEAP]
    call gb_num
    mov si, gb_l_mlarge
    mov ax, [gb_mlarge]
    call gb_num
    mov si, gb_l_mtotal
    mov ax, [gb_mtotal]
    call gb_num
    mov si, gb_l_xms
    mov ax, [gb_syskb + SK_XMS]
    call gb_num

    call bl_blank
    mov si, gb_s_pit1
    call bl_sline
    mov si, gb_s_pit2
    call bl_sline
    mov si, gb_l_ovh
    mov ax, [gb_bcnt]
    mov dx, [gb_bcnt+2]
    mov cx, 9
    call bl_kv
    mov ax, [gb_bcnt]
    mov dx, [gb_bcnt+2]
    mov cx, BL_BASE_N
    call bl_us100
    mov si, gb_l_ovh1
    mov cx, 9
    call bl_kv
    call bl_blank
    mov si, gb_s_warn1
    call bl_sline
    mov si, gb_s_warn2
    call bl_sline
    mov si, gb_s_warn3
    call bl_sline
    mov si, gb_s_warn4
    call bl_sline
    mov si, gb_s_warn5
    call bl_sline
    mov si, gb_s_warn6
    call bl_sline
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; gb_num - SI = label, AX = an unsigned word: one "label   N" line
gb_num:
    push cx
    push dx
    xor dx, dx
    mov cx, 9
    call bl_kv
    pop dx
    pop cx
    ret

; gb_hex - SI = label, AX = a word: one "label   NNNN" line
gb_hex:
    push di
    call bl_lclr
    xor di, di
    call bl_lput
    mov di, BL_C_N
    call bl_hex4
    call bl_lcommit
    pop di
    ret

; --- block 1: raw memory and framebuffer bandwidth ---------------------------
gb_bw:
    push ax
    push bx
    push cx
    push dx
    push si
    call bl_blank
    mov si, gb_s_h_bw
    call bl_sline
    call bl_head

    mov ax, ds                      ; --- RAM, through the loop below
    mov [gb_seg], ax
    mov word [gb_tab], gb_rrow
    mov word [bl_n], 8
    mov word [bl_body], gb_b_stosw
    mov si, gb_r_rw
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_tram_w], ax
    mov [gb_tram_w+2], dx
    mov word [bl_body], gb_b_stosb
    mov si, gb_r_rb
    xor al, al
    call bl_run
    mov word [bl_body], gb_b_read
    mov si, gb_r_rr
    xor al, al
    call bl_run
    mov word [bl_n], 4
    mov word [bl_body], gb_b_rmw
    mov si, gb_r_rm
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_tram_m], ax
    mov [gb_tram_m+2], dx

    mov ax, [gb_fbseg]              ; --- and the framebuffer, through the same
    mov [gb_seg], ax
    mov word [gb_tab], gb_vrow
    mov word [bl_n], 8
    mov word [bl_body], gb_b_stosw
    mov si, gb_r_vw
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_tvid_w], ax
    mov [gb_tvid_w+2], dx
    mov word [bl_body], gb_b_stosb
    mov si, gb_r_vb
    xor al, al
    call bl_run
    mov word [bl_body], gb_b_read
    mov si, gb_r_vr
    xor al, al
    call bl_run
    mov word [bl_n], 4
    mov word [bl_body], gb_b_rmw
    mov si, gb_r_vm
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_tvid_m], ax
    mov [gb_tvid_m+2], dx

    mov word [bl_n], 200            ; the ISA I/O cost itself, which is what
    mov word [bl_body], gb_b_inport ; makes a status-port poll expensive
    mov si, gb_r_in
    xor al, al
    call bl_run
    mov word [bl_n], 4              ; ...and one whole vertical retrace period:
    mov word [bl_body], gb_b_vsync  ; the refresh rate, measured
    mov si, gb_r_vs
    xor al, al
    call bl_run
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- block 2: the drawing primitives -----------------------------------------
gb_prims:
    push ax
    push bx
    push cx
    push dx
    push si
    call bl_blank
    mov si, gb_s_h_prim
    call bl_sline
    call bl_head
    mov al, CBLACK
    call OSAPI_SET_COLOR

    mov word [bl_n], 300
    mov word [bl_body], gb_b_pixel
    mov si, gb_r_px
    xor al, al
    call bl_run

    call gb_box8                    ; hline at 8 px, then at GB_BOXW
    mov word [bl_n], 200
    mov word [bl_body], gb_b_hline
    mov si, gb_r_hl8
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_thl8], ax
    mov [gb_thl8+2], dx
    call gb_boxfull
    mov word [bl_n], 60
    mov si, gb_r_hlw
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_thlw], ax
    mov [gb_thlw+2], dx

    call gb_box8                    ; vline at 8 px, then at GB_BOXH
    mov word [bl_n], 200
    mov word [bl_body], gb_b_vline
    mov si, gb_r_vl8
    xor al, al
    call bl_run
    call gb_boxfull
    mov word [bl_n], 40
    mov si, gb_r_vlh
    xor al, al
    call bl_run

    call gb_box8                    ; fill: 8x8, 64x64, then the whole sandbox
    mov word [bl_n], 200
    mov word [bl_body], gb_b_fill
    mov si, gb_r_f8
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_tf8], ax
    mov [gb_tf8+2], dx
    call gb_box64
    mov word [bl_n], 24
    mov si, gb_r_f64
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_tf64], ax
    mov [gb_tf64+2], dx
    call gb_boxfull
    mov word [bl_n], 6
    mov si, gb_r_fbox
    xor al, al
    call bl_run

    call gb_box64                   ; the rest of the rect family, all 64x64,
    mov word [bl_n], 24             ; so the column compares like for like
    mov word [bl_body], gb_b_frame
    mov si, gb_r_fr
    xor al, al
    call bl_run
    mov word [bl_body], gb_b_gray
    mov si, gb_r_gy
    xor al, al
    call bl_run
    mov word [bl_body], gb_b_pat
    mov si, gb_r_pt
    xor al, al
    call bl_run
    mov word [bl_body], gb_b_xfill
    mov si, gb_r_xf
    xor al, al
    call bl_run
    mov word [bl_body], gb_b_xrect
    mov si, gb_r_xr
    xor al, al
    call bl_run

    mov word [gb_src], gb_bsolid    ; the blit, both ways round
    mov word [bl_n], 12
    mov word [bl_body], gb_b_blit
    mov si, gb_r_bs
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_tbs], ax
    mov [gb_tbs+2], dx
    mov word [gb_src], gb_bstripe
    mov word [bl_n], 6
    mov si, gb_r_bn
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_tbn], ax
    mov [gb_tbn+2], dx

    call gb_boxfull                 ; the blit's alternative: move the pixels
    mov word [bl_n], 16             ; you already have (SPEC.md 5.5)
    mov word [bl_body], gb_b_scroll
    mov si, gb_r_sc
    xor al, al
    call bl_run
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- block 3: text -----------------------------------------------------------
gb_text:
    push ax
    push bx
    push cx
    push dx
    push si
    call bl_blank
    mov si, gb_s_h_text
    call bl_sline
    mov si, gb_s_h_text2
    call bl_sline
    call bl_head
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, [gb_x]
    mov [gb_tx], ax

    mov word [bl_n], 40
    mov word [bl_body], gb_b_fchar
    mov si, gb_r_ch
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_tcell], ax
    mov [gb_tcell+2], dx

    mov word [bl_n], 12
    mov word [bl_body], gb_b_fstr
    mov si, gb_r_st
    xor al, al
    call bl_run
    mov word [bl_body], gb_b_pair
    mov si, gb_r_pa
    xor al, al
    call bl_run
    mov word [bl_body], gb_b_frun
    mov si, gb_r_ru
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_trun], ax
    mov [gb_trun+2], dx

    mov ax, [gb_x]                  ; ...and the same two five pixels right.
    add ax, 5                       ; NOT one pixel: the ROM font's rightmost
    mov [gb_tx], ax                 ; column is blank in every glyph, so a
                                    ; one-pixel shift spills nothing into the
                                    ; second byte and flatters the status quo
                                    ; (tests/fontbench, FB_SKEW). A dragged
                                    ; window lands here seven times in eight
    mov word [bl_body], gb_b_pair
    mov si, gb_r_pa5
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_tpair5], ax
    mov [gb_tpair5+2], dx
    mov word [bl_body], gb_b_frun
    mov si, gb_r_ru5
    xor al, al
    call bl_run

    mov ax, [gb_x]
    mov [gb_tx], ax
    mov word [bl_n], 200
    mov word [bl_body], gb_b_fwidth
    mov si, gb_r_fw
    xor al, al
    call bl_run
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- block 4: the API cells that draw nothing --------------------------------
gb_api:
    push ax
    push bx
    push cx
    push dx
    push si
    call bl_blank
    mov si, gb_s_h_api
    call bl_sline
    call bl_head
    mov word [bl_n], 300
    mov word [bl_body], gb_b_ticks
    mov si, gb_r_gt
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_tapi], ax
    mov [gb_tapi+2], dx
    mov word [bl_body], gb_b_color
    mov si, gb_r_sc2
    xor al, al
    call bl_run
    mov word [bl_body], gb_b_cont
    mov si, gb_r_wc
    xor al, al
    call bl_run
    mov word [bl_body], gb_b_geom
    mov si, gb_r_wg
    xor al, al
    call bl_run
    mov word [bl_body], gb_b_obsc
    mov si, gb_r_wo
    xor al, al
    call bl_run
    mov word [bl_body], gb_b_cliptest
    mov si, gb_r_ct
    xor al, al
    call bl_run
    mov word [bl_n], 100
    mov word [bl_body], gb_b_clip
    mov si, gb_r_cs
    xor al, al
    call bl_run
    mov word [bl_n], 200
    mov word [bl_body], gb_b_mouse
    mov si, gb_r_mo
    xor al, al
    call bl_run
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- block 5: composite window work ------------------------------------------
gb_composite:
    push ax
    push bx
    push cx
    push dx
    push si
    call bl_blank
    mov si, gb_s_h_comp
    call bl_sline
    call bl_head
    mov word [bl_n], 4              ; one TITLE_H strip (SPEC.md 11.92)
    mov word [bl_body], gb_b_title
    xor al, al
    mov si, gb_r_ti
    call bl_run
    mov word [bl_n], 12             ; one full-width opaque text row
    mov word [bl_body], gb_b_row
    mov si, gb_r_rowdraw
    xor al, al
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_trow], ax
    mov [gb_trow+2], dx
    mov word [bl_n], 2              ; ...and the whole page of them. Method T:
    mov word [bl_body], gb_b_page   ; this is seconds on the target machine,
    mov si, gb_r_page               ; which IS the finding
    mov al, 1
    call bl_run
    mov ax, [bl_last]
    mov dx, [bl_last+2]
    mov [gb_tpage], ax
    mov [gb_tpage+2], dx
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- block 6: what the two-size rows imply -----------------------------------
;
; Every figure here is a subtraction or a division of rows printed above, so a
; wrong one is visible beside its inputs (PERFORMANCE.md Part 6 rule 7). The
; page prediction and the measured page are the deliberate redundancy: they are
; computed from different rows and must agree.
gb_derived:
    push ax
    push bx
    push cx
    push dx
    push si
    call bl_blank
    mov si, gb_s_h_der
    call bl_sline

    mov ax, [gb_tf64]               ; fill: (64x64 - 8x8) over the pixels
    mov dx, [gb_tf64+2]             ; between them. Both rows are scaled to one
    mov cx, 24                      ; call first, or the different N's dominate
    call gb_percall
    call gb_stash
    mov ax, [gb_tf8]
    mov dx, [gb_tf8+2]
    mov cx, 200
    call gb_percall
    call gb_sub                     ; DX:AX = stash - this
    mov cx, 4096 - 64
    call gb_nsper
    mov si, gb_d_fillpx
    call gb_num32

    mov ax, [gb_thlw]               ; hline: the same, over 248 pixels
    mov dx, [gb_thlw+2]
    mov cx, 60
    call gb_percall
    call gb_stash
    mov ax, [gb_thl8]
    mov dx, [gb_thl8+2]
    mov cx, 200
    call gb_percall
    call gb_sub
    mov cx, GB_BOXW - 8
    call gb_nsper
    mov si, gb_d_hlpx
    call gb_num32

    mov ax, [gb_tcell]              ; one glyph cell - PERFORMANCE.md Part 2's
    mov dx, [gb_tcell+2]            ; anchor number, and the one figure in that
    mov cx, 40                      ; table everything else is estimated from
    call bl_us100
    mov si, gb_d_cell
    call gb_num32

    mov ax, [gb_trun]               ; ...and one cell of a ten-cell run
    mov dx, [gb_trun+2]
    mov cx, 120
    call bl_us100
    mov si, gb_d_runcell
    call gb_num32

    mov ax, [gb_tpair5]             ; the fontbench ratio: the status quo (a
    mov dx, [gb_tpair5+2]           ; dragged window, so unaligned) over an
    mov bx, [gb_trun]               ; aligned run. SPEC.md 6.1.1 says 130 on a
    mov cx, [gb_trun+2]             ; real XT with a Hercules card
    call gb_ratio
    mov si, gb_d_runwin
    call gb_num32

    mov ax, [gb_tvid_w]             ; the bus penalty: framebuffer over RAM,
    mov dx, [gb_tvid_w+2]           ; through byte-identical loops
    mov bx, [gb_tram_w]
    mov cx, [gb_tram_w+2]
    call gb_ratio
    mov si, gb_d_busw
    call gb_num32
    mov ax, [gb_tvid_m]
    mov dx, [gb_tvid_m+2]
    mov bx, [gb_tram_m]
    mov cx, [gb_tram_m+2]
    call gb_ratio
    mov si, gb_d_busm
    call gb_num32

    mov ax, [gb_tvid_m]             ; ...and the read-modify-write in 8088
    mov dx, [gb_tvid_m+2]           ; CLOCKS, which is the "~30 cycles" SPEC.md
    mov cx, 4                       ; 39.5 quotes and nothing has re-measured
    call gb_percall
    mov cx, GB_BWBYTES
    call gb_clocks
    mov si, gb_d_rmwclk
    call gb_num32

    mov ax, [gb_tbn]                ; blit: striped over solid. A big ratio is
    mov dx, [gb_tbn+2]              ; the run coalescer earning its keep; near
    mov bx, [gb_tbs]                ; 100 would mean it is not coalescing at
    mov cx, [gb_tbs+2]              ; all, which is the Part 3 item 4 failure
    call gb_ratio
    mov si, gb_d_blit
    call gb_num32

    mov ax, [gb_trow]               ; the whole page predicted from one row.
    mov dx, [gb_trow+2]             ; Print it beside the measured page: the
    mov cx, 12                      ; two come from different rows and must
    call gb_percall                 ; agree, which is the harness checking
    mov cx, [bl_prows]              ; itself
    call gb_mul
    mov cx, 1
    call bl_us100
    mov si, gb_d_pagepred
    call gb_num32
    mov ax, [gb_tpage]
    mov dx, [gb_tpage+2]
    mov cx, 2
    call bl_us100
    mov si, gb_d_pagereal
    call gb_num32

    mov ax, [gb_tf64]               ; a whole-screen fill from the same slope:
    mov dx, [gb_tf64+2]             ; where a wm_paint_all starts from
    mov cx, 24
    call gb_percall
    mov cx, [gb_vw]                 ; MULTIPLY BEFORE DIVIDING, and split the
    call gb_mul                     ; /4096 into two /64s: dividing first
    mov cx, 64                      ; truncated a 212-count fill to zero, and
    call gb_div                     ; doing it all at the end overflows the
    mov cx, [gb_vh]                 ; 32-bit accumulator on a slow machine,
    call gb_mul                     ; where the same fill is 3,800 counts
    mov cx, 64
    call gb_div
    mov cx, 1
    call bl_us100
    mov si, gb_d_scrfill
    call gb_num32
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

gb_trailer:
    push si
    call bl_blank
    mov si, gb_s_end1
    call bl_sline
    mov si, gb_s_end2
    call bl_sline
    mov si, gb_s_end3
    call bl_sline
    pop si
    ret

; =============================================================================
; derived-figure arithmetic. Every one of these is 32-bit in and 32-bit out,
; because a row on a 4.77 MHz machine is millions of counts and a 16-bit
; intermediate is PERFORMANCE.md Part 6 rule 3's whole subject.
; =============================================================================

; gb_num32 - SI = label, DX:AX = a 32-bit value: one report line
gb_num32:
    push cx
    mov cx, 12
    call bl_kv
    pop cx
    ret

; gb_stash / gb_sub - park DX:AX, then subtract the next value from it
gb_stash:
    mov [gb_ta], ax
    mov [gb_ta+2], dx
    ret
gb_sub:
    push bx
    mov bx, ax
    mov ax, [gb_ta]
    sub ax, bx
    mov bx, dx
    mov dx, [gb_ta+2]
    sbb dx, bx
    jnc .out
    xor ax, ax                      ; the bigger row measured smaller: noise
    xor dx, dx
.out:
    pop bx
    ret

; gb_mul / gb_div - DX:AX scaled by CX, saturating
gb_mul:
    call bl_mul48
    call bl_get32
    ret
gb_div:
    push cx
    push si
    mov si, cx
    mov cx, 1
    call bl_mul48                   ; load DX:AX into the 48-bit accumulator
    mov cx, si
    or cx, cx
    jnz .d
    mov cx, 1
.d:
    call bl_div48
    call bl_get32
    pop si
    pop cx
    ret

; gb_percall - DX:AX total counts over CX iterations -> counts per call
gb_percall:
    call gb_div
    ret

; gb_nsper - DX:AX counts over CX units -> nanoseconds per unit
gb_nsper:
    push cx
    push si
    mov si, cx
    mov cx, 838                     ; one PIT count is 838 ns
    call bl_mul48
    mov cx, si
    or cx, cx
    jnz .d
    mov cx, 1
.d:
    call bl_div48
    call bl_get32
    pop si
    pop cx
    ret

; gb_clocks - DX:AX counts over CX units -> 4.77 MHz CPU clocks per unit, x100
;
; One PIT count is EXACTLY four CPU clocks on a period machine: both divide the
; same 14.31818 MHz crystal, the PIT by 12 and the 8088 by 3. So this is not an
; approximation on the target - and on a turbo clone it is the ratio the
; sysbench CPU block reports, which is why that block exists.
gb_clocks:
    push cx
    push si
    mov si, cx
    mov cx, 400                     ; 4 clocks a count, x100 for two decimals
    call bl_mul48
    mov cx, si
    or cx, cx
    jnz .d
    mov cx, 1
.d:
    call bl_div48
    call bl_get32
    pop si
    pop cx
    ret

; gb_ratio - (DX:AX / CX:BX) * 100, both 32-bit
; Both are shifted right together until the denominator fits a word, which
; costs at most a bit of the ratio's last digit and cannot overflow.
gb_ratio:
    push bx
    push cx
    push si
.shift:
    or cx, cx
    jz .have
    shr cx, 1
    rcr bx, 1
    shr dx, 1
    rcr ax, 1
    jmp short .shift
.have:
    or bx, bx
    jnz .div
    mov bx, 1
.div:
    mov si, bx
    mov cx, 100
    call bl_mul48
    mov cx, si
    call bl_div48
    call bl_get32
    pop si
    pop cx
    pop bx
    ret

; =============================================================================
; the measured bodies. Each reads its parameters from memory, so bl_time's loop
; passes nothing and no setup is inside the measured span.
; =============================================================================

gb_box8:
    push ax
    mov ax, [gb_x]
    add ax, 7
    mov [gb_x2], ax
    mov ax, [gb_y]
    add ax, 7
    mov [gb_y2], ax
    pop ax
    ret

gb_box64:
    push ax
    mov ax, [gb_x]
    add ax, 63
    mov [gb_x2], ax
    mov ax, [gb_y]
    add ax, 63
    mov [gb_y2], ax
    pop ax
    ret

gb_boxfull:
    push ax
    mov ax, [gb_x]
    add ax, GB_BOXW - 1
    mov [gb_x2], ax
    mov ax, [gb_y]
    add ax, GB_BOXH - 1
    mov [gb_y2], ax
    pop ax
    ret

gb_b_pixel:
    mov cx, [gb_x]
    mov dx, [gb_y]
    call OSAPI_GFX_PIXEL
    ret

gb_b_hline:
    mov ax, [gb_x]
    mov bx, [gb_x2]
    mov dx, [gb_y]
    call OSAPI_GFX_HLINE
    ret

gb_b_vline:
    mov ax, [gb_x]
    mov bx, [gb_y]
    mov dx, [gb_y2]
    call OSAPI_GFX_VLINE
    ret

gb_b_fill:
    mov ax, [gb_x]
    mov bx, [gb_y]
    mov cx, [gb_x2]
    mov dx, [gb_y2]
    call OSAPI_GFX_FILL
    ret

gb_b_frame:
    mov ax, [gb_x]
    mov bx, [gb_y]
    mov cx, [gb_x2]
    mov dx, [gb_y2]
    call OSAPI_GFX_FRAME
    ret

gb_b_gray:
    mov ax, [gb_x]
    mov bx, [gb_y]
    mov cx, [gb_x2]
    mov dx, [gb_y2]
    call OSAPI_GFX_FILL_GRAY
    ret

gb_b_pat:
    mov ax, [gb_x]
    mov bx, [gb_y]
    mov cx, [gb_x2]
    mov dx, [gb_y2]
    mov si, gb_pattern
    call OSAPI_GFX_FILL_PAT
    ret

gb_b_xfill:
    mov ax, [gb_x]
    mov bx, [gb_y]
    mov cx, [gb_x2]
    mov dx, [gb_y2]
    call OSAPI_GFX_XOR_FILL
    ret

gb_b_xrect:
    mov ax, [gb_x]
    mov bx, [gb_y]
    mov cx, [gb_x2]
    mov dx, [gb_y2]
    call OSAPI_GFX_XOR_RECT
    ret

gb_b_blit:
    push bp
    push es
    push ds
    pop es                          ; ES is OURS here: no stub is involved
    mov si, [gb_src]
    mov bp, GB_BLITS
    mov ax, [gb_x]
    mov bx, [gb_y]
    mov cx, GB_BLITW
    mov dx, GB_BLITH
    call OSAPI_GFX_BLIT4
    pop es
    pop bp
    ret

gb_b_scroll:
    mov ax, [gb_x]                  ; x1 and x2+1 are multiples of 8 by
    mov bx, [gb_y]                  ; construction - the blit is byte-column
    mov cx, [gb_x2]                 ; granular on every adapter
    mov dx, [gb_y2]
    mov si, 8
    call OSAPI_GFX_SCROLL
    ret

gb_b_fchar:
    mov cx, [gb_tx]
    mov dx, [gb_y]
    mov al, 'W'
    call OSAPI_FONT_CHAR
    ret

gb_b_fstr:
    mov cx, [gb_tx]
    mov dx, [gb_y]
    mov si, gb_s_test
    call OSAPI_FONT_STR
    ret

; The erase-and-letter PAIR: what every text element in this system wrote by
; hand before SPEC.md 6.1, and what the RUN row below it replaced.
gb_b_pair:
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov ax, [gb_tx]
    mov bx, [gb_y]
    mov cx, ax
    add cx, 79
    mov dx, bx
    add dx, 7
    call OSAPI_GFX_FILL
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov cx, [gb_tx]
    mov dx, [gb_y]
    mov si, gb_s_test
    call OSAPI_FONT_STR
    ret

gb_b_frun:
    mov cx, [gb_tx]
    mov dx, [gb_y]
    mov si, gb_s_test
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    ret

gb_b_fwidth:
    mov si, gb_s_test
    call OSAPI_FONT_WIDTH
    ret

gb_b_ticks:
    call OSAPI_GET_TICKS
    ret

gb_b_color:
    mov al, CBLACK
    call OSAPI_SET_COLOR
    ret

gb_b_mouse:
    call OSAPI_MOUSE
    ret

gb_b_cont:
    mov bx, [gb_win]
    call OSAPI_WM_CONTENT
    ret

gb_b_geom:
    mov bx, [gb_win]
    call OSAPI_WM_GEOM
    ret

gb_b_obsc:
    mov bx, [gb_win]
    call OSAPI_WM_OBSCURED
    ret

gb_b_cliptest:
    mov ax, [gb_x]
    mov bx, [gb_y]
    mov cx, [gb_x2]
    mov dx, [gb_y2]
    call OSAPI_WM_CLIP_TEST
    ret

gb_b_clip:
    mov bx, [gb_win]
    call OSAPI_WM_CLIP_SET
    call OSAPI_WM_CLIP_CLEAR
    ret

gb_b_title:
    mov bx, [gb_win]
    xor ax, ax                      ; 0 = "the bytes W_TITLE names changed"
    call OSAPI_WM_TITLE
    ret

gb_b_row:
    mov si, gb_s_test               ; one full-width opaque row: the unit the
    call bl_pad                     ; page below is built out of
    mov cx, [gb_cx]
    mov dx, [gb_y]
    mov si, bl_draw
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    ret

gb_b_page:
    mov si, [gb_win]
    call bl_paint
    ret

; --- the raw bandwidth bodies ------------------------------------------------
; GB_BWROWS rows of GB_BWCOLS bytes, walked through a table of row offsets, so
; the framebuffer's banked interleave and plain RAM go through the identical
; loop and the difference between the two rows is the bus and nothing else.

gb_b_stosw:
    push es
    mov es, [gb_seg]
    mov bx, [gb_tab]
    mov si, GB_BWROWS
    xor ax, ax
    cld
.r:
    mov di, [bx]
    mov cx, GB_BWCOLS / 2
    rep stosw
    add bx, 2
    dec si
    jnz .r
    pop es
    ret

gb_b_stosb:
    push es
    mov es, [gb_seg]
    mov bx, [gb_tab]
    mov si, GB_BWROWS
    xor al, al
    cld
.r:
    mov di, [bx]
    mov cx, GB_BWCOLS
    rep stosb
    add bx, 2
    dec si
    jnz .r
    pop es
    ret

; Read through ES rather than DS so that neither side has to juggle DS - the
; segment override is one byte and two clocks on both sides, so the RAM/VRAM
; comparison is unaffected.
gb_b_read:
    push es
    mov es, [gb_seg]
    mov bx, [gb_tab]
    mov si, GB_BWROWS
.r:
    mov di, [bx]
    mov cx, GB_BWCOLS / 2
.w:
    mov ax, [es:di]
    inc di
    inc di
    loop .w
    add bx, 2
    dec si
    jnz .r
    pop es
    ret

gb_b_rmw:
    push es
    mov es, [gb_seg]
    mov bx, [gb_tab]
    mov si, GB_BWROWS
.r:
    mov di, [bx]
    mov cx, GB_BWCOLS
.b:
    mov al, [es:di]                 ; the read-modify-write SPEC.md 39.5 prices
    or al, 0                        ; at ~30 clocks whether or not it changes a
    mov [es:di], al                 ; pixel - the mono renderer's inner step
    inc di
    loop .b
    add bx, 2
    dec si
    jnz .r
    pop es
    ret

gb_b_inport:
    mov dx, [gb_stat]
    in al, dx
    ret

; gb_b_vsync - one whole vertical retrace period, bounded
; The bit is high during retrace, so this waits for it to fall and then to rise
; again: one full frame, which is the refresh rate. A dead or absent status
; port exhausts GB_VSMAX and returns - a wrong number, never a hung machine.
gb_b_vsync:
    mov dx, [gb_stat]
    mov ah, [gb_vsbit]
    mov cx, GB_VSMAX
.low:
    in al, dx
    test al, ah
    jz .high
    loop .low
    ret
.high:
    mov cx, GB_VSMAX
.h:
    in al, dx
    test al, ah
    jnz .done
    loop .h
.done:
    ret

%include "benchlib.inc"

; =============================================================================
; data
; =============================================================================

; A window as big as the adapter allows: wm_fit clamps the template onto the
; live screen (SPEC.md 39.7), so ONE template gives 52 text rows on VGA, 35 on
; Hercules and 17 on CGA without this source knowing which it is on. The x is
; 7 because WF_SNAP wants the CONTENT origin - W_X + 1 - on a multiple of 8.
gb_tpl:
    dw 7, 22, 632, 448
    dw gb_ttl, gb_paint, gb_onkey, gb_onclick

gb_ttl:     db 'Gfx Bench', 0

; The measured string is tests/fontbench's, character for character, so its
; published figures (SPEC.md 6.1.1) cross-check this harness for free.
gb_s_test:  db 'C-2 01 A0F', 0

gb_pattern: db 0xAA, 0x55, 0xAA, 0x55, 0xAA, 0x55, 0xAA, 0x55

; seg, stride, bmask, bshift - vid_tab's four numbers, in VID_* order
gb_vtab:
    dw 0xA000, 80, 0, 0
    dw 0xB000, 90, 3, 2
    dw 0xB800, 80, 1, 1

; status port and its retrace bit: 3DAh bit 3 on VGA and CGA, 3BAh bit 7 on
; Hercules
gb_ptab:
    dw 0x03DA, 0x0008
    dw 0x03BA, 0x0080
    dw 0x03DA, 0x0008

gb_f_vga:   db 'GFXVGA.TXT', 0
gb_f_herc:  db 'GFXHERC.TXT', 0
gb_f_cga:   db 'GFXCGA.TXT', 0

gb_n_vga:   db 'VGA 640x480 planar', 0
gb_n_herc:  db 'HERCULES 720x348 mono', 0
gb_n_cga:   db 'CGA 640x200 mono', 0

gb_s_ttl1:  db 'os8088 GFXBENCH - drawing primitives priced on this adapter', 0
gb_s_ttl2:  db '===========================================================', 0

gb_l_adapter: db 'adapter', 0
gb_l_screen:  db 'screen width px', 0
gb_l_rows:    db 'screen height px', 0
gb_l_bpp:     db 'bits per pixel', 0
gb_l_dock:    db 'first dock row', 0
gb_l_fbseg:   db 'framebuffer seg', 0
gb_l_stride:  db 'bytes per row', 0
gb_l_banks:   db 'framebuffer banks', 0
gb_l_stat:    db 'status port', 0
gb_l_conw:    db 'content width px', 0
gb_l_conh:    db 'content height px', 0
gb_l_cells:   db 'content cells wide', 0
gb_l_crows:   db 'content cells tall', 0
gb_l_boxx:    db 'sandbox x (aligned)', 0
gb_l_cpu:     db 'cpu tier 0/1/2', 0
gb_l_feat:    db 'cpu feature bits', 0
gb_l_kern:    db 'kernel span KB', 0
gb_l_heap:    db 'claim heap KB', 0
gb_l_mlarge:  db 'largest free run KB', 0
gb_l_mtotal:  db 'total free KB', 0
gb_l_xms:     db 'pool above 1MB KB', 0
gb_l_ovh:     db 'loop overhead counts', 0
gb_l_ovh1:    db 'loop overhead usx100', 0

gb_s_pit1:  db 'One PIT count is 838 ns and four 4.77MHz CPU clocks. us/op is PER', 0
gb_s_pit2:  db 'ITERATION, net of the loop overhead. t = tick-timed, ! = near the wrap.', 0
gb_s_warn1: db 'CAUTION: under QEMU the us column is the HOST speed and means nothing.', 0
gb_s_warn2: db 'Boot -icount shift=3,sleep=off and read counts as guest INSTRUCTIONS.', 0
gb_s_warn3: db 'The VRAM rows assume the real framebuffer address, so a kernel built', 0
gb_s_warn4: db 'with HERCSEG= measures plain RAM in them and the bus ratio reads 100.', 0
gb_s_warn5: db 'The retrace row is meaningless on QEMU too - its status port toggles', 0
gb_s_warn6: db 'on every read so a poll always terminates. On iron it is the refresh.', 0

gb_s_h_bw:    db '-- raw bandwidth: 32 rows x 64 bytes = 2048 bytes an iteration --', 0
gb_s_h_prim:  db '-- primitives (two sizes wherever the cost has two terms) --', 0
gb_s_h_text:  db '-- text: the same 10 characters, aligned and skewed 5 px --', 0
gb_s_h_text2: db '   (tests/fontbench uses this string too, so the two harnesses check)', 0
gb_s_h_api:   db '-- API cells that draw nothing: the far-call floor --', 0
gb_s_h_comp:  db '-- composite: what a window operation costs --', 0
gb_s_h_der:   db '-- derived: subtractions of the rows above, printed to be checked --', 0

gb_r_rw:   db 'RAM  write word', 0
gb_r_rb:   db 'RAM  write byte', 0
gb_r_rr:   db 'RAM  read word', 0
gb_r_rm:   db 'RAM  read-mod-write', 0
gb_r_vw:   db 'VRAM write word', 0
gb_r_vb:   db 'VRAM write byte', 0
gb_r_vr:   db 'VRAM read word', 0
gb_r_vm:   db 'VRAM read-mod-write', 0
gb_r_in:   db 'ISA status port in', 0
gb_r_vs:   db 'one retrace period', 0

gb_r_px:   db 'GFX_PIXEL', 0
gb_r_hl8:  db 'GFX_HLINE 8px', 0
gb_r_hlw:  db 'GFX_HLINE 256px', 0
gb_r_vl8:  db 'GFX_VLINE 8px', 0
gb_r_vlh:  db 'GFX_VLINE 128px', 0
gb_r_f8:   db 'GFX_FILL 8x8', 0
gb_r_f64:  db 'GFX_FILL 64x64', 0
gb_r_fbox: db 'GFX_FILL 256x128', 0
gb_r_fr:   db 'GFX_FRAME 64x64', 0
gb_r_gy:   db 'GFX_FILL_GRAY 64x64', 0
gb_r_pt:   db 'GFX_FILL_PAT 64x64', 0
gb_r_xf:   db 'GFX_XOR_FILL 64x64', 0
gb_r_xr:   db 'GFX_XOR_RECT 64x64', 0
gb_r_bs:   db 'GFX_BLIT4 solid', 0
gb_r_bn:   db 'GFX_BLIT4 4px runs', 0
gb_r_sc:   db 'GFX_SCROLL 256x128', 0

gb_r_ch:   db 'FONT_CHAR one cell', 0
gb_r_st:   db 'FONT_STR 10 aligned', 0
gb_r_pa:   db 'PAIR 10 aligned', 0
gb_r_ru:   db 'FONT_RUN 10 aligned', 0
gb_r_pa5:  db 'PAIR 10 skewed 5', 0
gb_r_ru5:  db 'FONT_RUN 10 skewed', 0
gb_r_fw:   db 'FONT_WIDTH 10', 0

gb_r_gt:   db 'GET_TICKS', 0
gb_r_sc2:  db 'SET_COLOR', 0
gb_r_wc:   db 'WM_CONTENT', 0
gb_r_wg:   db 'WM_GEOM', 0
gb_r_wo:   db 'WM_OBSCURED', 0
gb_r_ct:   db 'WM_CLIP_TEST', 0
gb_r_cs:   db 'WM_CLIP_SET+CLEAR', 0
gb_r_mo:   db 'MOUSE', 0

gb_r_ti:      db 'WM_TITLE strip', 0
gb_r_rowdraw: db 'one full-width row', 0
gb_r_page:    db 'whole page of rows', 0

gb_d_fillpx:   db 'fill ns per pixel', 0
gb_d_hlpx:     db 'hline ns per pixel', 0
gb_d_cell:     db 'FONT_CHAR us x100', 0
gb_d_runcell:  db 'RUN cell us x100', 0
gb_d_runwin:   db 'skewPAIR/RUN x100', 0
gb_d_busw:     db 'VRAM/RAM word x100', 0
gb_d_busm:     db 'VRAM/RAM rmw x100', 0
gb_d_rmwclk:   db 'VRAM rmw clocks x100', 0
gb_d_blit:     db 'blit runs/solid x100', 0
gb_d_pagepred: db 'page predicted usx100', 0
gb_d_pagereal: db 'page measured usx100', 0
gb_d_scrfill:  db 'screen fill us x100', 0

gb_s_end1:  db 'End of report. R re-runs it, S saves it, Bench menu does both.', 0
gb_s_end2:  db 'A saved file lands in the CURRENT directory of the CURRENT volume', 0
gb_s_end3:  db '(SPEC.md 19.2): open a Disk window on the disk you want it on first.', 0

gb_about:   db 'Gfx Bench', 0

    OS88_MENUSET gb_menus, gb_about, gb_oncmd
        OS88_MENU gb_m_bench, gb_i_bench, 3
    OS88_MENUSET_END gb_menus

gb_m_bench: db 'Bench', 0
gb_i_bench: dw gb_it_run, gb_it_save, gb_it_top
gb_it_run:  db 'Run', 0
gb_it_save: db 'Save Report', 0
gb_it_top:  db 'Top of Report', 0

; The bss offsets past the scalars are DERIVED, not written down twice: the
; equ block after OS88_IMAGE_END uses these, and GB_BSS_OWN falls out of them.
; A hand-totalled figure that is too small is a package writing over
; benchlib's arena, which assembles cleanly and produces a report full of
; plausible nonsense.
GB_O_SYSKB  equ 126
GB_O_VROW   equ GB_O_SYSKB + SYSKB_SIZE
GB_O_RROW   equ GB_O_VROW + GB_BWROWS * 2
GB_O_RAM    equ GB_O_RROW + GB_BWROWS * 2
GB_O_SOLID  equ GB_O_RAM + GB_BWBYTES
GB_O_STRIPE equ GB_O_SOLID + GB_BLITSZ
GB_BSS_OWN  equ GB_O_STRIPE + GB_BLITSZ

    OS88_BSS GB_BSS_OWN + BL_BSS_SIZE
    OS88_IMAGE_END

; --- loader-zeroed bss (SPEC.md 21 step 5) -----------------------------------
gb_win      equ os88_image_end + 0     ; word: our window
gb_vw       equ os88_image_end + 2     ; word: OSAPI_VIDEO's answers
gb_vh       equ os88_image_end + 4
gb_dock     equ os88_image_end + 6
gb_kind     equ os88_image_end + 8     ; byte
gb_bpp      equ os88_image_end + 9     ; byte
gb_cpu      equ os88_image_end + 10    ; word: AL tier, AH feature bits
gb_mlarge   equ os88_image_end + 12    ; word
gb_mtotal   equ os88_image_end + 14    ; word
gb_cx       equ os88_image_end + 16    ; word: content origin and size
gb_cy       equ os88_image_end + 18
gb_cw       equ os88_image_end + 20
gb_ch       equ os88_image_end + 22
gb_x        equ os88_image_end + 24    ; word: the sandbox rect
gb_y        equ os88_image_end + 26
gb_x2       equ os88_image_end + 28
gb_y2       equ os88_image_end + 30
gb_tx       equ os88_image_end + 32    ; word: the text x, aligned or skewed
gb_fbseg    equ os88_image_end + 34    ; word: the adapter record
gb_stride   equ os88_image_end + 36
gb_bmask    equ os88_image_end + 38
gb_bshift   equ os88_image_end + 40
gb_xbyte    equ os88_image_end + 42    ; word: the sandbox's byte column
gb_stat     equ os88_image_end + 44    ; word: the status port
gb_vsbit    equ os88_image_end + 46    ; word: ...and its retrace bit
gb_seg      equ os88_image_end + 48    ; word: the bandwidth target segment
gb_tab      equ os88_image_end + 50    ; word: ...and its row table
gb_src      equ os88_image_end + 52    ; word: the blit source in use
gb_bcnt     equ os88_image_end + 54    ; dword: the baseline row's raw counts
gb_ta       equ os88_image_end + 58    ; dword: gb_stash/gb_sub's scratch
gb_tram_w   equ os88_image_end + 62    ; dword: the rows the derived block
gb_tram_m   equ os88_image_end + 66    ; subtracts and divides
gb_tvid_w   equ os88_image_end + 70
gb_tvid_m   equ os88_image_end + 74
gb_tf8      equ os88_image_end + 78
gb_tf64     equ os88_image_end + 82
gb_thl8     equ os88_image_end + 86
gb_thlw     equ os88_image_end + 90
gb_tcell    equ os88_image_end + 94
gb_trun     equ os88_image_end + 98
gb_tpair5   equ os88_image_end + 102
gb_tbs      equ os88_image_end + 106
gb_tbn      equ os88_image_end + 110
gb_trow     equ os88_image_end + 114
gb_tpage    equ os88_image_end + 118
gb_tapi     equ os88_image_end + 122
gb_syskb    equ os88_image_end + GB_O_SYSKB    ; SYSKB_SIZE bytes
gb_vrow     equ os88_image_end + GB_O_VROW     ; GB_BWROWS words: fb offsets
gb_rrow     equ os88_image_end + GB_O_RROW     ; ...and the RAM ones
gb_ram      equ os88_image_end + GB_O_RAM      ; the RAM bandwidth target
gb_bsolid   equ os88_image_end + GB_O_SOLID    ; the two blit sources
gb_bstripe  equ os88_image_end + GB_O_STRIPE

    BL_BSS os88_image_end + GB_BSS_OWN
