; =============================================================================
; os8088 - apps/realboy/rwhw.inc
;
; VGA full screen's writer by HARDWARE SCROLL (REALBOY-SPEC 15.3). The
; picture's 144 rows are at an ORIGIN in VRAM that moves with the game's
; scroll - the CRTC's start address in bytes and the attribute controller's
; pel panning for the 0-7 pixels below that (SPEC.md 53.7: the bracket's own
; mode is the app's to program) - so a line that only moved is not composed
; again: what scrolled into view is written, a byte or two. The gap and the
; speed line under the picture are the line compare's (VRAM 0, unpanned),
; and do not move.
;
; A line IS composed when it is not plain background at the main scroll
; (line 100's): a sprite on it, the window, a scroll of its own (Super Mario
; Land's status bar), another LCDC - and when it is not VALID: a line that
; had a sprite, a row that scrolled in from below or above, a tile or map
; cell under it that changed (ppu_bgdirty, off the VRAM scan, which runs on
; every call here). Composed, it is written whole at the origin, shifted by
; the panning; valid only if it was plain.
;
; A scroll of more than RW_HWMAX pixels, another LCDC or BGP at the main
; line, the host's whole frame (RB_DFULL) or an origin that has run to an end
; of VRAM put the origin back at RW_HWBASE and compose every line: a redraw,
; and never a wrong picture.
; =============================================================================

RW_HWMST        equ 65536 - 144 * 168   ; the copies a still line keeps, 8 of
                                    ;   21 bytes a line, one for each panning
RW_HWBASE       equ 18000           ; the origin's home, bytes
RW_HWLO         equ 1024            ; ...and how far it may wander: above the
RW_HWHI         equ RW_HWMST - 144 * 40 - 64    ; line compare's rows, under
                                    ;   the copies
RW_HWMAX        equ 32              ; pixels: a scroll beyond is a redraw

; rw_hwdraw - the frame onto VRAM by hardware scroll. DS = the package. Out:
; AX = the lines composed
rw_hwdraw:
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    cld
    mov es, [rb_dmgseg]
    mov ds, [cs:rb_viewseg]
    mov word [cs:hw_ncomp], 0
    mov byte [cs:hw_mm], 0FFh       ; (the map mask: not known)
    call ppu_dhead
    mov byte [es:RB_DFAST], 0
    cmp byte [es:RB_DFULL], 0
    je .sc
    mov byte [cs:hw_ok], 0          ; the host's whole: a redraw
.sc:
    call ppu_dscan                  ; the shadows, every call (RB_DSTALE is
    cmp byte [es:RB_DFULL], 0       ;   rb_renderd's, not ours)
    jne .oam
    cmp byte [es:RB_DOCH], 0
    je .oamk
.oam:
    call ppu_oam
.oamk:
    ; SAME: the raster log and the frame's first registers as the last
    ; call's (rb_renderd's FAST, section 13.2)
    mov byte [cs:hw_same], 0
    call ppu_logsame                ; ZF = 1: the same log
    jnz .ls
    mov si, PPU_REGS
    mov di, RB_DREG0
    mov cx, 4
    repe cmpsw
    jne .ls
    mov byte [cs:hw_same], 1
.ls:
    mov si, PPU_REGS
    mov di, RB_DREG0
    mov cx, 4
    rep movsw
    mov al, [es:RB_DTCH]            ; (a tile or a map cell changed)
    or al, [es:RB_DMCH]
    mov [cs:hw_vch], al
    ; the main line's registers: the raster log run to line 100, and then
    ; back to the frame's start for the lines
    mov ax, [PPU_REGS + 0]
    mov [cs:hw_r0 + 0], ax
    mov ax, [PPU_REGS + 2]
    mov [cs:hw_r0 + 2], ax
    mov ax, [PPU_REGS + 4]
    mov [cs:hw_r0 + 4], ax
    mov ax, [PPU_REGS + 6]
    mov [cs:hw_r0 + 6], ax
    mov byte [PPU_LY], 100
    call ppu_log
    mov al, [PPU_REGS + 0]
    mov [cs:hw_nlcdc], al
    mov ax, [PPU_REGS + 1]          ; AL = SCY, AH = SCX
    mov [cs:hw_nscy], ax
    mov al, [PPU_REGS + 3]
    mov [cs:hw_nbgp], al
    cmp byte [PPU_LOGI], 0          ; (no write before it: as it was)
    je .r0
    mov ax, [cs:hw_r0 + 0]
    mov [PPU_REGS + 0], ax
    mov ax, [cs:hw_r0 + 2]
    mov [PPU_REGS + 2], ax
    mov ax, [cs:hw_r0 + 4]
    mov [PPU_REGS + 4], ax
    mov ax, [cs:hw_r0 + 6]
    mov [PPU_REGS + 6], ax
    mov byte [PPU_LOGI], 0
    call ppu_pal
.r0:
    mov byte [cs:hw_mv], 1          ; (the origin moves, or goes home)
    mov al, [cs:hw_nlcdc]           ; the LCD or the background off: nothing
    and al, 81h                     ;   that scrolls - every line composed
    cmp al, 81h
    jne .reset
    cmp byte [cs:hw_ok], 0
    je .reset
    mov al, [cs:hw_nlcdc]
    cmp al, [cs:hw_lcdc]
    jne .reset
    mov al, [cs:hw_nbgp]
    cmp al, [cs:hw_bgp]
    jne .reset
    mov ax, [cs:hw_nscy]
    sub al, [cs:hw_scy]             ; DL = dy, DH = dx, signed
    sub ah, [cs:hw_scx]
    mov dx, ax
    or ax, ax
    jnz .mv
    mov byte [cs:hw_mv], 0          ; still: the lines judged as rb_renderd
    mov [cs:hw_dx], al              ;   does (ppu_ldirty)
    jmp .keep
.mv:
    mov al, dl
    add al, RW_HWMAX
    cmp al, 2 * RW_HWMAX
    ja .reset
    mov al, dh
    add al, RW_HWMAX
    cmp al, 2 * RW_HWMAX
    ja .reset
    mov al, dh                      ; the panning takes dx, the start address
    cbw                             ;   its whole bytes
    mov bl, [cs:hw_p]
    xor bh, bh
    add ax, bx                      ; AX = p + dx, -32..39
    mov bl, al
    and bl, 7
    mov [cs:hw_p], bl
    sar ax, 1
    sar ax, 1
    sar ax, 1
    add [cs:hw_ob], ax
    mov al, dl                      ; ...and dy rows of 40
    cbw
    mov bx, ax
    shl ax, 1
    shl ax, 1
    shl ax, 1
    mov cl, 5
    shl bx, cl
    add ax, bx
    add [cs:hw_ob], ax
    cmp word [cs:hw_ob], RW_HWLO
    jb .reset
    cmp word [cs:hw_ob], RW_HWHI
    ja .reset
    mov [cs:hw_dx], dh
    call hw_vshift                  ; DL = dy: the rows moved with it
    jmp short .keep
.reset:
    mov word [cs:hw_ob], RW_HWBASE
    mov byte [cs:hw_p], 0
    mov byte [cs:hw_dx], 0
    push es
    push cs
    pop es
    mov di, hw_valid
    mov cx, 144 / 2
    xor ax, ax
    rep stosw
    push ds
    pop es
    mov di, RB_HWMST
    mov cx, 144 / 2
    rep stosw
    pop es
.keep:
    mov ax, [cs:hw_nscy]
    mov [cs:hw_scy], ax
    mov al, [cs:hw_nlcdc]
    mov [cs:hw_lcdc], al
    mov al, [cs:hw_nbgp]
    mov [cs:hw_bgp], al
    mov byte [cs:hw_ok], 1
    ; STILL: the origin did not move and nothing under any line changed -
    ; not a line to visit
    cmp byte [cs:hw_mv], 0
    jne .lines
    cmp byte [cs:hw_same], 0
    je .lines
    mov al, [cs:hw_vch]
    or al, [es:RB_DOCH]
    jnz .lines
    jmp .done
.lines:
    ; the lines: each composed, or marked for its new bytes (hw_edges), or
    ; left. A plain line's registers are the main line's, so they are looked
    ; at only where the raster log changes them (hw_regs)
    push es
    push ds
    pop es
    mov di, RB_HWACT
    mov cx, 144 / 2
    xor ax, ax
    rep stosw
    pop es
    mov ax, [cs:hw_ob]
    mov [cs:hw_row], ax
    mov word [cs:hw_spr], PPU_LSPR
    mov byte [cs:hw_next], 0
    mov byte [PPU_WLINE], 0
    mov byte [PPU_LY], 0
.l2:
    mov bl, [PPU_LY]
    cmp bl, [cs:hw_next]
    jb .rk
    call hw_regs
    mov bl, [PPU_LY]
.rk:
    xor bh, bh
    cmp byte [cs:hw_rmain], 0       ; PLAIN: the main line's registers, the
    je .np                          ;   window not on it, no sprite
    cmp bl, [cs:hw_wy]
    jae .np
    test byte [cs:hw_lcdc], 02h
    jz .pl
    mov si, [cs:hw_spr]
    cmp byte [si], 0
    jne .np
.pl:
    mov byte [RB_HWMST + bx], 0     ; (a copy kept is not a plain line's)
    mov byte [cs:hw_plain], 1       ; plain: VALID, and nothing under it
    cmp byte [cs:hw_valid + bx], 1  ;   changed, is a line that only moved
    jne .comp
    cmp byte [cs:hw_vch], 0
    je .ed
    call ppu_bgdirty
    jc .comp
    mov bl, [PPU_LY]
    xor bh, bh
.ed:
    mov byte [RB_HWACT + bx], 1    ; (its new bytes: hw_edges)
    jmp short .next
.np:
    mov byte [cs:hw_plain], 0
    call ppu_ldirty                 ; not plain: its inputs as they were (and
    jc .npd                         ;   its registers kept, for next time),
    cmp byte [cs:hw_mv], 0          ;   the origin still and the row the
    jne .npm                        ;   line's: left as it is
    cmp byte [cs:hw_valid + bx], 2
    jne .comp
.npw:
    call ppu_wstep                  ; (the window's counter, as ppu_line)
    jmp short .next
.npd:
    mov byte [RB_HWMST + bx], 0     ; changed: its copies are not it
    jmp short .comp
.npm:
    mov al, [RB_HWMST + bx]         ; the same, and the origin moved: its
    cmp al, 80h                     ;   copy at this panning, a byte copy
    jne .nps                        ;   of VRAM (hw_latch) - once it has been
    call hw_latch                   ;   the same for two moves, so a line
    jmp short .npw                  ;   that changes every other frame is
.nps:                               ;   not copied 8 times for nothing
    inc ax
    mov [RB_HWMST + bx], al
    cmp al, 2
    jb .comp
    mov byte [RB_HWMST + bx], 80h
    mov byte [cs:hw_mstr], 1
.comp:
    call hw_line
    mov byte [cs:hw_mstr], 0
.next:
    add word [cs:hw_row], 40
    add word [cs:hw_spr], 41
    inc byte [PPU_LY]
    cmp byte [PPU_LY], 144
    jae .eds
    jmp .l2
.eds:
    call hw_edges
.done:
    ; The start address is latched by the card as the vertical retrace
    ; begins and the panning is taken on the next scan line, so the two
    ; changed together would show a refresh with one and not the other: the
    ; picture 8 pixels out under the beam. Then the start goes in out of the
    ; retrace and the panning as it begins - a wait of up to a refresh, once
    ; in 8 pixels of a sideways scroll. Alone, either goes in at once
    mov bx, [cs:hw_ob]
    mov al, [cs:hw_p]
    cmp bx, [cs:hw_wob]
    je .pan
    cmp al, [cs:hw_wp]
    je .sa
    mov dx, 3DAh
    xor cx, cx                      ; (a bound, should the bit never move)
.w0:
    in al, dx
    test al, 8
    loopnz .w0
    call hw_sa
    xor cx, cx
.w1:
    in al, dx
    test al, 8
    loopz .w1
    mov al, [cs:hw_p]
    jmp short .pan
.sa:
    call hw_sa
.pan:
    cmp al, [cs:hw_wp]
    je .pk
    call hw_pan
.pk:
    call ppu_dclear
    mov ax, [cs:hw_ncomp]
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; hw_home - the origin home and the panning 0, for the writer that does not
; scroll (rw_fsplane, under interlace): its next call starts again
hw_home:
    push ax
    push bx
    mov byte [cs:hw_ok], 0
    mov bx, RW_HWBASE
    call hw_sa
    xor al, al
    call hw_pan
    pop bx
    pop ax
    ret

; hw_sa - BX = the start address, to the CRTC (and hw_wob). Kept: all
hw_sa:
    push ax
    push dx
    mov [cs:hw_wob], bx
    mov dx, 3D4h
    mov al, 0Ch
    mov ah, bh
    out dx, ax
    mov al, 0Dh
    mov ah, bl
    out dx, ax
    pop dx
    pop ax
    ret

; hw_pan - AL = the pel panning, 0-7, to AR13 (and hw_wp). Kept: all
hw_pan:
    push ax
    push dx
    mov [cs:hw_wp], al
    mov ah, al
    mov dx, 3DAh                    ; (the attribute flip-flop to its index)
    in al, dx
    mov dx, 3C0h
    mov al, 33h                     ; AR13, the display left on
    out dx, al
    mov al, ah
    out dx, al
    pop dx
    pop ax
    ret

; hw_mask - the map mask to plane AL (0 or 1), unless it holds it. Kept: all
; but AX
hw_mask:
    cmp al, [cs:hw_mm]
    je .r
    mov [cs:hw_mm], al
    push dx
    mov ah, 1
    or al, al
    jz .s
    mov ah, 2
.s:
    mov al, 02h
    mov dx, 3C4h
    out dx, ax
    pop dx
.r:
    ret

; hw_line - line PPU_LY composed and written whole at the origin: VALID 1 if
; it was plain, 2 if not - and with hw_mstr, its 8 copies too (hw_latch).
; DS = view, ES = damage
hw_line:
    inc word [cs:hw_ncomp]
    call ppu_line
    push es
    mov es, [cs:rw_fsi + FSI_SEG]
    mov ax, [cs:hw_row]
    mov [cs:hw_dst], ax
    mov al, [cs:hw_p]
    mov [cs:hw_sh], al
    call hw_both
    cmp byte [cs:hw_mstr], 0
    je .v
    mov al, [PPU_LY]
    mov ah, 168
    mul ah
    add ax, RW_HWMST
    mov [cs:hw_dst], ax
    mov byte [cs:hw_sh], 0
.mp:
    call hw_both
    add word [cs:hw_dst], 21
    inc byte [cs:hw_sh]
    cmp byte [cs:hw_sh], 8
    jb .mp
.v:
    pop es
    mov bl, [PPU_LY]
    xor bh, bh
    mov al, 2
    sub al, [cs:hw_plain]
    mov [cs:hw_valid + bx], al
    ret

; hw_both - the composed line's two planes to ES:[hw_dst], shifted right
; [hw_sh] pixels; the plane the map mask holds goes first, so a line turns
; it once. DS = view
hw_both:
    mov al, [cs:hw_mm]
    cmp al, 1
    je .one
    xor al, al                      ; plane 0 (the shade's bit 0), then 1
    call hw_mask
    mov si, [PPU_OSRC]
    call .row
    mov al, 1
    call hw_mask
    mov si, [PPU_OSRC]
    add si, 20h
    jmp short .row
.one:
    mov si, [PPU_OSRC]              ; plane 1, then 0
    add si, 20h
    call .row
    xor al, al
    call hw_mask
    mov si, [PPU_OSRC]
.row:
    mov di, [cs:hw_dst]
    mov cl, [cs:hw_sh]
    jmp hw_row20

; hw_latch - line BX's copy at this panning to its row at the origin: write
; mode 1, each byte read into the card's latches and written from them, the
; two planes at once. DS = view
hw_latch:
    push ds
    push es
    push cx
    push si
    push di
    mov al, bl
    mov ah, 168
    mul ah
    add ax, RW_HWMST
    mov si, ax
    mov al, [cs:hw_p]
    mov ah, 21
    mul ah
    add si, ax
    mov di, [cs:hw_row]
    mov dx, 3CEh
    mov ax, 0105h                   ; GC5: write mode 1
    out dx, ax
    mov dx, 3C4h
    mov ax, 0302h                   ; map mask: planes 0 and 1
    out dx, ax
    mov byte [cs:hw_mm], 0FFh
    mov ax, [cs:rw_fsi + FSI_SEG]
    mov ds, ax
    mov es, ax
    mov cx, 21
    rep movsb
    mov dx, 3CEh
    mov ax, 0005h                   ; write mode 0 again
    out dx, ax
    pop di
    pop si
    pop cx
    pop es
    pop ds
    mov byte [cs:hw_valid + bx], 2
    ret

; hw_row20 - 20 bytes at DS:SI to ES:DI, the picture CL (0-7) pixels right
; of the byte grid: 21 bytes, the first's leading and the last's trailing
; pixels outside the window. Two bytes a turn, written as a word to an even
; address, as VRAM is the slow end
hw_row20:
    or cl, cl
    jnz .sh
    mov cx, 20
    jmp hw_put
.sh:
    xor bl, bl                      ; BL = the byte before
    test di, 1
    jz .even
    lodsb                           ; odd: byte 0 alone, then 1-2 .. 17-18
    mov ah, bl
    mov bl, al
    shr ax, cl
    stosb
    mov ch, 9
    call .pairs
    lodsb                           ; ...and 19-20, of byte 19 and nothing
    xor ah, ah
    mov ch, 1
    jmp short .pair
.even:
    mov ch, 10                      ; even: 0-1 .. 18-19, then 20 alone
    call .pairs
    mov ah, bl
    xor al, al
    shr ax, cl
    stosb
    ret
.pairs:
    lodsw                           ; AL = byte k, AH = byte k + 1
.pair:
    mov dx, ax
    mov ah, bl                      ; (the one before, and k): k's out
    shr ax, cl
    mov bl, dh
    xchg dl, dh                     ; (k and k + 1): k + 1's
    shr dx, cl
    mov ah, dl
    stosw
    dec ch
    jnz .pairs
    ret

; hw_put - CX bytes from DS:SI to ES:DI, in words where DI is even
hw_put:
    test di, 1
    jz .w
    movsb
    dec cx
.w:
    shr cx, 1
    rep movsw
    jnc .r
    movsb
.r:
    ret

; hw_regs - the raster log to line PPU_LY, and what the lines from here to
; its next write are: hw_rmain (the main line's registers), hw_wy (the
; first line the window covers, FFh none) and hw_next. DS = view
hw_regs:
    call ppu_log
    mov al, [PPU_LOGI]
    mov ah, 0FFh
    cmp al, [PPU_LOGN]
    jae .n
    xor ah, ah
    shl ax, 1
    shl ax, 1
    mov si, ax
    mov ah, [RB_RLOG + si]          ; (its line, after this one)
.n:
    mov [cs:hw_next], ah
    mov byte [cs:hw_rmain], 0
    mov al, [PPU_REGS + 0]
    cmp al, [cs:hw_lcdc]
    jne .r
    mov ax, [PPU_REGS + 1]
    cmp ax, [cs:hw_scy]
    jne .r
    mov al, [PPU_REGS + 3]
    cmp al, [cs:hw_bgp]
    jne .r
    mov byte [cs:hw_rmain], 1
    mov al, 0FFh
    test byte [PPU_REGS + 0], 20h
    jz .w
    cmp byte [PPU_REGS + 7], 166
    ja .w
    mov al, [PPU_REGS + 6]
.w:
    mov [cs:hw_wy], al
.r:
    ret

; hw_edges - the bytes that scrolled into view on every line RB_HWACT marks
; (plain and valid), from the main line's map and tiles through its BGP:
; composed a map row at a time into RB_HWCOL (16 a line, plane 1 at +8), then
; written a plane at a time, the one the map mask holds first. DS = view,
; ES = damage
hw_edges:
    mov al, [cs:hw_dx]
    or al, al
    jnz .go
    ret
.go:
    cbw
    mov bl, [cs:hw_p]
    xor bh, bh
    or ax, ax
    js .left
    neg ax                          ; f1 = p + 160 - dx, f2 = p + 159
    add ax, 160
    add ax, bx
    add bx, 159
    jmp short .k
.left:
    neg ax                          ; f1 = p, f2 = p - dx - 1
    add ax, bx
    dec ax
    xchg ax, bx                     ; AX = p, BX = p - dx - 1
.k:
    mov cl, 3
    shr ax, cl
    shr bx, cl
    mov [cs:hw_k1], al
    sub bl, al
    inc bl
    mov [cs:hw_n], bl
    mov cl, 3                       ; the first byte's first pixel on the
    shl al, cl                      ;   screen, and in the map (SCX on)
    sub al, [cs:hw_p]
    add al, [cs:hw_scx]
    mov ah, al
    and ah, 7
    mov [cs:hw_fine], ah
    shr al, cl
    mov [cs:hw_x], al               ; (its map column)
    mov al, [cs:hw_lcdc]            ; the main line's tiles...
    mov ah, al
    and ah, 10h
    cmp ah, [PPU_TMODE]
    je .tm
    call ppu_taddr
.tm:
    mov al, [cs:hw_bgp]             ; ...and its palette
    cmp al, [PPU_REGS + 3]
    je .pm
    mov [PPU_REGS + 3], al
    call ppu_pal
.pm:
    mov ax, 9800h
    test byte [cs:hw_lcdc], 08h
    jz .mb
    mov ax, 9C00h
.mb:
    mov [cs:hw_mapb], ax
    mov byte [cs:hw_mrow], 0FFh
    xor bx, bx                      ; BX = the line
.y:
    cmp byte [RB_HWACT + bx], 0
    jne .yc
    jmp .yn
.yc:
    mov dl, bl
    add dl, [cs:hw_scy]             ; DL = its row in the map
    mov al, dl
    shr al, 1
    shr al, 1
    shr al, 1
    cmp al, [cs:hw_mrow]
    je .tr
    mov [cs:hw_mrow], al            ; a map row: its cells' tiles, the
    push bx                         ;   bytes' and the one past them
    xor ah, ah
    mov cl, 5
    shl ax, cl
    add ax, [cs:hw_mapb]
    mov si, ax                      ; SI = the map row
    mov ch, [cs:hw_n]
    inc ch
    mov cl, [cs:hw_x]
    mov di, hw_ta
.c:
    mov bl, cl
    and bl, 31
    xor bh, bh
    mov al, [si + bx]
    cbw
    shl ax, 1
    mov bx, ax
    mov ax, [PPU_TADDRC + bx]
    mov [cs:di], ax
    inc di
    inc di
    inc cl
    dec ch
    jnz .c
    pop bx
.tr:
    and dl, 7
    xor dh, dh
    shl dx, 1
    mov di, dx                      ; DI = the row in a tile
    mov bp, bx                      ; BP = the line's bytes in RB_HWCOL
    mov cl, 4
    shl bp, cl
    add bp, RB_HWCOL
    mov si, hw_ta
    mov cl, [cs:hw_fine]
    mov ch, [cs:hw_n]
    push bx
.b:
    mov bx, [cs:si]
    mov ax, [bx + di]               ; this tile's row
    mov bx, [cs:si + 2]
    mov dx, [bx + di]               ; ...and the next's
    mov bh, al
    mov bl, dl
    shl bx, cl
    mov al, bh                      ; AL = colour bit 0
    mov bh, ah
    mov bl, dh
    shl bx, cl
    mov ah, bh                      ; AH = colour bit 1
    cmp byte [cs:hw_bgp], 0E4h      ; BGP the identity: the colours are the
    je .id                          ;   shades
    call hw_anf
.id:
    mov [ds:bp], al
    mov [ds:bp + 8], ah
    inc bp
    inc si
    inc si
    dec ch
    jnz .b
    pop bx
.yn:
    inc bx
    cmp bx, 144
    jae .w
    jmp .y
.w:
    push es
    mov es, [cs:rw_fsi + FSI_SEG]
    mov al, [cs:hw_mm]
    cmp al, 1
    je .one
    xor al, al
    call hw_mask
    xor dx, dx
    call .plane
    mov al, 1
    call hw_mask
    mov dx, 8
    call .plane
    jmp short .x
.one:
    mov dx, 8
    call .plane
    xor al, al
    call hw_mask
    xor dx, dx
    call .plane
.x:
    pop es
    ret
.plane:                             ; DX = the plane's offset in RB_HWCOL
    mov bx, [cs:hw_ob]
    mov al, [cs:hw_k1]
    xor ah, ah
    add bx, ax                      ; BX = line 0's first byte at the origin
    mov si, RB_HWCOL
    add si, dx
    xor dx, dx                      ; DX = the line
    mov al, [cs:hw_n]
    xor ah, ah
    mov bp, ax                      ; BP = the bytes a line
.pl:
    mov di, dx
    cmp byte [RB_HWACT + di], 0
    je .pn
    mov di, bx                      ; (a byte or two: movsb, and no word's
    mov cx, bp                      ;   alignment to look at)
    rep movsb
    sub si, bp
.pn:
    add si, 16
    add bx, 40
    inc dx
    cmp dx, 144
    jb .pl
    ret

; hw_anf - AL, AH = a byte's colour bits 0 and 1: through BGP (PPU_ANF, D
; xor (bit 0 and A) xor (bit 1 and B) xor (both and C), a plane each) to the
; shades' bits. Kept: all but AX
hw_anf:
    push bx
    push dx
    mov bl, al
    and bl, ah                      ; BL = both
    mov dl, [PPU_ANF + 0]
    mov bh, al
    and bh, [PPU_ANF + 2]
    xor dl, bh
    mov bh, ah
    and bh, [PPU_ANF + 4]
    xor dl, bh
    mov bh, bl
    and bh, [PPU_ANF + 6]
    xor dl, bh
    mov dh, [PPU_ANF + 8]
    mov bh, al
    and bh, [PPU_ANF + 10]
    xor dh, bh
    mov bh, ah
    and bh, [PPU_ANF + 12]
    xor dh, bh
    mov bh, bl
    and bh, [PPU_ANF + 14]
    xor dh, bh
    mov ax, dx
    pop dx
    pop bx
    ret

; hw_vshift - DL = dy, signed: the VALID flags follow the rows the origin
; moved, and a row that came in is not valid
hw_vshift:
    or dl, dl
    jz .r
    push ax
    push bx
    push cx
    mov al, dl
    cbw
    mov cx, ax                      ; CX = dy
    js .up
    xor bx, bx                      ; dy > 0: row y takes row y + dy's
.d:
    mov al, 0
    mov si, bx
    add si, cx
    cmp si, 144
    jae .d1
    mov al, [cs:hw_valid + si]
.d1:
    mov [cs:hw_valid + bx], al
    inc bx
    cmp bx, 144
    jb .d
    jmp short .x
.up:
    mov bx, 143                     ; dy < 0: from the bottom up
.u:
    mov al, 0
    mov si, bx
    add si, cx
    js .u1
    mov al, [cs:hw_valid + si]
.u1:
    mov [cs:hw_valid + bx], al
    dec bx
    jns .u
.x:
    pop cx
    pop bx
    pop ax
.r:
    ret
