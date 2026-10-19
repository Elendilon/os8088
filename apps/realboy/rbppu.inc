; =============================================================================
; os8088 - apps/realboy/rbppu.inc
;
; RealBoy's PICTURE: the frame the core just finished, composed line by line
; into two SHADE PLANES a line (docs/REALBOY-SPEC.md section 13). Included by
; every host, after rbsys.inc; the writers that take the planes to a screen
; are the host's.
;
;   rb_render   DS = anything, ES:DI = a 5,760-byte buffer. Composes the
;               frame that ended at the last RBX_FRAME: 144 lines of 40
;               bytes, the shade's bit 0 for pixels 0-159 (20 bytes, the
;               leftmost pixel in bit 7) and then its bit 1. Shade 0 is the
;               lightest. Every register is preserved.
;
;   rb_render4  the same frame as the four planes OSAPI_GFX_BLITP takes for
;               the desktop's greys, into an 11,520-byte buffer: 80 bytes a
;               line, NOT bit 1 three times (planes 0-2) then NOT bit 0
;               (plane 3) - 15, 7, 8 and 0 for shades 0-3. Written as each
;               line is finished, so a colour window needs no second pass.
;
; The state each line is drawn with is the frame's own: rbsys's snapshot of
; the eight registers as the frame began (RB_SNAP) with the raster log
; (RB_RLOG) applied at the lines its writes took effect on, or - a frame with
; no mid-frame write - the registers as they stand. VRAM and OAM are read as
; they stand: the frame is composed at VBlank's start, before the game's
; VBlank handler has touched either.
;
; It works a BYTE - eight pixels - at a time, never a pixel: a tile row is
; already two bit-planes, so the background is fetched, shifted for the fine
; scroll and masked; the palettes are four minterm masks; a sprite is two
; bytes shifted into place. Sprites keep the DMG's priority - the lowest X,
; then the lowest OAM index - through a CLAIMED mask, so a sprite hidden
; behind the background still hides the sprites under it.
; =============================================================================

; --- the renderer's working memory, in the view's rbsys half ----------------
PPU_REV         equ 0x4900          ; 256: each byte bit-reversed (X flip)
PPU_BL          equ 0x4A00          ; 24: the line's colour index, bit 0
PPU_BH          equ 0x4A20          ; 24: ...bit 1
PPU_WL          equ 0x4A40          ; 24: the window's, before it is placed
PPU_WH          equ 0x4A60          ; 24
PPU_CL          equ 0x4AA0          ; 24: pixels a sprite has claimed
PPU_OL          equ 0x4AC0          ; 24: the shade, bit 0
PPU_OH          equ 0x4AE0          ; 24: ...bit 1
PPU_SPR         equ 0x4B00          ; 10 x 4: X, row's low byte, high byte, attr
PPU_NSPR        equ 0x4B28          ; byte
PPU_REGS        equ 0x4B30          ; 8: LCDC SCY SCX BGP OBP0 OBP1 WY WX now
PPU_PALM        equ 0x4B38          ; 3 x 8: per palette, the shade bit 0 and
                                    ;   bit 1 masks of colours 0-3
PPU_LY          equ 0x4B50          ; byte: the line being composed
PPU_WLINE       equ 0x4B51          ; byte: the window's own line counter
PPU_LOGI        equ 0x4B52          ; byte: the next raster log entry
PPU_LOGN        equ 0x4B53          ; byte: entries that are this frame's
PPU_REVOK       equ 0x4B54          ; byte: PPU_REV is built
PPU_TMODE       equ 0x4B55          ; byte: LCDC bit 4 PPU_TADDR was built for
PPU_TMP         equ 0x4B56          ; word
PPU_ANF         equ 0x4B60          ; 16: BGP as words D A B C for the shade's
                                    ;   bit 0, then bit 1 (ppu_pal)
PPU_TADDR       equ 0x4C00          ; 512: tile n's row 0, for LCDC bit 4
PPU_BLIST       equ 0x6600          ; 128: a map row's 32 tile addresses, twice,
PPU_WLIST       equ 0x6680          ; 128:   for the background and the window
PPU_OUT         equ 0x4B58          ; byte: rb_render4's layout, not rb_render's
PPU_BKEY        equ 0x4B5A          ; word: the map row PPU_BLIST holds (or 0)
PPU_WKEY        equ 0x4B5C          ; word: ...PPU_WLIST
PPU_LSPR        equ 0x4E00          ; 144 x 41: per line, the count and the
                                    ;   OAM indices of the sprites that MAY
                                    ;   cover it (16 tall), in OAM order

rb_render4:
    push ds
    mov ds,[cs:rb_viewseg]
    mov byte [PPU_OUT],1
    pop ds
    jmp short rb_render.go
rb_render:
    push ds
    mov ds,[cs:rb_viewseg]
    mov byte [PPU_OUT],0
    pop ds
.go:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    cld
    mov ds,[cs:rb_viewseg]
    cmp byte [PPU_REVOK],0
    jne .rev
    call ppu_mkrev
    mov byte [PPU_TMODE],0FFh
.rev:
    mov word [PPU_BKEY],0               ; the map may have changed since
    mov word [PPU_WKEY],0
    call ppu_oam
    ; the state as the frame began: the snapshot, if this frame logged a write
    mov byte [PPU_LOGN],0
    mov byte [PPU_LOGI],0
    mov al,[S_FRAMES]
    dec al                              ; the frame just finished
    cmp al,[S_SNAPTAG]
    jne .now
    mov si,RB_SNAP
    mov al,[S_RLOGN]
    mov [PPU_LOGN],al
    jmp short .st
.now:
    mov al,[0FF40h]                     ; LCDC SCY SCX BGP OBP0 OBP1 WY WX
    mov [PPU_REGS+0],al
    mov ax,[0FF42h]
    mov [PPU_REGS+1],ax
    mov ax,[0FF47h]
    mov [PPU_REGS+3],ax
    mov al,[0FF49h]
    mov [PPU_REGS+5],al
    mov ax,[0FF4Ah]
    mov [PPU_REGS+6],ax
    jmp short .st2
.st:
    push es
    push di
    push ds
    pop es
    mov di,PPU_REGS
    mov cx,8
    rep movsb
    pop di
    pop es
.st2:
    call ppu_pal
    mov byte [PPU_WLINE],0
    mov byte [PPU_LY],0
.line:
    call ppu_log
    call ppu_line
    cmp byte [PPU_OUT],0
    jne .out4
    mov si,PPU_OL                       ; out: the 20 bytes of each plane
    mov cx,10
    rep movsw
    mov si,PPU_OH
    mov cx,10
    rep movsw
    jmp short .nextl
.out4:
    mov si,PPU_OH                       ; out: NOT bit 1 to planes 0-2...
    mov cx,10
.o4:
    lodsw
    not ax
    mov [es:di+20],ax
    mov [es:di+40],ax
    stosw
    loop .o4
    add di,40                           ; ...and NOT bit 0 to plane 3
    mov si,PPU_OL
    mov cx,10
.o3:
    lodsw
    not ax
    stosw
    loop .o3
.nextl:
    inc byte [PPU_LY]
    cmp byte [PPU_LY],144
    jb .line
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; rb_renderd - rb_render, by DAMAGE (REALBOY-SPEC section 13.2): only the lines
; whose inputs changed since the last call are composed, and only the lines
; whose pixels then differ are written. ES:DI = the 5,760-byte buffer, which
; holds the last frame; [cs:rb_dmgseg] = RB_DMG_SIZE bytes of the host's. On
; return RB_DCHG in that segment holds a byte a line, 1 = the line changed,
; and AX = how many did. Every other register is preserved. With rb_dmgseg 0
; it is rb_render, every line changed.
;
; A line's inputs are its eight registers and the window's line counter, the
; map cells and tile rows of its background and window, and its sprites -
; their OAM entries and tiles. VRAM and OAM are compared against a shadow of
; what the last call saw, a whole tile or map word at a time (repe cmpsw); a
; changed tile or cell sets its byte, and a line looks its cells up in those.
; The comparison is ~20 ms of an 8088 a call and the composition it saves
; ~4 ms a line, which is what lets a mostly still screen draw on a 5150.
; RB_DFULL = 1 (the host's, after it cleared the screen) composes everything.
; =============================================================================
RB_DVRAM        equ 0x0000              ; 8,192: the shadow of 8000-9FFF
RB_DOAM         equ 0x2000              ; 160: of OAM
RB_DTD          equ 0x20A0              ; 384: a tile changed (tiles 0-383)
RB_DMD          equ 0x2220              ; 2,048: a map byte changed (9800+)
RB_DLREG        equ 0x2A20              ; 144 x 10: a line's registers + WLINE
RB_DLD          equ 0x3000              ; 144: a sprite moved over the line
RB_DCHG         equ 0x3090              ; 144: the line changed (out)
RB_DFULL        equ 0x3120              ; byte: compose every line
RB_DBKEY        equ 0x3122              ; word: the BG row last judged
RB_DBCOL        equ 0x3124              ; byte: ...its first column
RB_DBRES        equ 0x3125              ; byte: ...and the verdict
RB_DWKEY        equ 0x3126              ; word: the window row last judged
RB_DWRES        equ 0x3128              ; byte
RB_DMODE        equ 0x3129              ; byte: LCDC bit 4 the keys are for
RB_DCNT         equ 0x312A              ; word: lines changed
RB_DOUT         equ 0x312C              ; dword: the caller's ES:DI
RB_DTCH         equ 0x3130              ; byte: some tile changed
RB_DMCH         equ 0x3131              ; byte: some map byte changed
RB_DOCH         equ 0x3132              ; byte: some OAM entry changed
RB_DFAST        equ 0x3133              ; byte: no register changed anywhere
RB_DLLOG        equ 0x3134              ; byte: the last call's frame logged
RB_DREG0        equ 0x3138              ; 8: the last call's registers
RB_DMROW        equ 0x3140              ; 64: a map row changed (2 x 32)
RB_DMG_SIZE     equ 0x3180

rb_dmgseg       dw 0                    ; the host's damage segment, or 0

rb_renderd:
    cmp word [cs:rb_dmgseg],0
    jne .go
    call rb_render                      ; no damage memory: every line
    mov ax,144
    ret
.go:
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    cld
    mov ds,[cs:rb_viewseg]
    mov ax,es
    mov es,[cs:rb_dmgseg]
    mov [es:RB_DOUT],di
    mov [es:RB_DOUT+2],ax
    mov word [es:RB_DCNT],0
    cmp byte [PPU_REVOK],0
    jne .rev
    call ppu_mkrev
    mov byte [PPU_TMODE],0FFh
.rev:
    mov word [PPU_BKEY],0
    mov word [PPU_WKEY],0
    mov word [es:RB_DBKEY],0
    mov word [es:RB_DWKEY],0
    mov byte [es:RB_DMODE],0FFh
    call ppu_dscan                      ; the shadows, the changed bytes
    cmp byte [es:RB_DFULL],0            ; the sprites' line lists: kept while
    jne .oam                            ;   OAM is, as nothing else moves them
    cmp byte [es:RB_DOCH],0
    je .oamk
.oam:
    call ppu_oam
.oamk:
    mov byte [PPU_LOGN],0               ; the state as the frame began
    mov byte [PPU_LOGI],0
    mov al,[S_FRAMES]
    dec al
    cmp al,[S_SNAPTAG]
    jne .now
    mov si,RB_SNAP
    mov al,[S_RLOGN]
    mov [PPU_LOGN],al
    push es
    push ds
    pop es
    mov di,PPU_REGS
    mov cx,8
    rep movsb
    pop es
    jmp short .st2
.now:
    mov al,[0FF40h]
    mov [PPU_REGS+0],al
    mov ax,[0FF42h]
    mov [PPU_REGS+1],ax
    mov ax,[0FF47h]
    mov [PPU_REGS+3],ax
    mov al,[0FF49h]
    mov [PPU_REGS+5],al
    mov ax,[0FF4Ah]
    mov [PPU_REGS+6],ax
.st2:
    call ppu_pal
    ; FAST: no register write in this frame or the last, and the registers
    ; as they were - so every line's are, and the window's counter with them
    mov byte [es:RB_DFAST],0
    mov al,[PPU_LOGN]
    mov ah,al
    or ah,[es:RB_DLLOG]                 ; this frame logged, or the last did
    mov [es:RB_DLLOG],al                ;   (this one's kept for the next)
    or ah,ah
    jnz .slow
    cmp byte [es:RB_DFULL],0
    jne .slow
    mov si,PPU_REGS
    mov di,RB_DREG0
    mov cx,4
    repe cmpsw
    jne .slow
    mov byte [es:RB_DFAST],1
    mov al,[es:RB_DTCH]                 ; ...and nothing else changed either:
    or al,[es:RB_DMCH]                  ;   not a line to compose
    or al,[es:RB_DOCH]
    jz .done
    call ppu_dfast                      ; RB_DLD = every line to compose
.slow:
    mov si,PPU_REGS
    mov di,RB_DREG0
    mov cx,4
    rep movsw
    mov byte [PPU_WLINE],0
    mov byte [PPU_LY],0
.line:
    call ppu_log
    mov bl,[PPU_LY]
    xor bh,bh
    mov byte [es:RB_DCHG+bx],0
    cmp byte [es:RB_DFAST],0
    je .judge
    cmp byte [es:RB_DLD+bx],0           ; FAST: judged already, by rows
    je .skip
    jmp short .comp
.judge:
    call ppu_ldirty                     ; CF = 1: compose it
    jnc .skip
.comp:
    call ppu_line
    call ppu_dput                       ; into the buffer if it differs
    jmp short .next
.skip:
    call ppu_wstep                      ; the window's counter, as ppu_line
.next:
    inc byte [PPU_LY]
    cmp byte [PPU_LY],144
    jb .line
.done:
    ; every change seen: the bytes clear for the next call - only those a
    ; change set (the full first call cleared nothing and set nothing)
    xor ax,ax
    cmp byte [es:RB_DTCH],0
    je .ct
    mov di,RB_DTD
    mov cx,384 / 2
    rep stosw
.ct:
    cmp byte [es:RB_DMCH],0
    je .cm
    mov di,RB_DMD
    mov cx,2048 / 2
    rep stosw
    mov di,RB_DMROW
    mov cx,64 / 2
    rep stosw
.cm:
    mov di,RB_DLD
    mov cx,144 / 2
    rep stosw
    mov byte [es:RB_DFULL],0
    mov ax,[es:RB_DCNT]
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; ppu_dscan: VRAM and OAM against the shadows. DS = view, ES = damage.
ppu_dscan:
    mov word [es:RB_DTCH],0             ; (and RB_DMCH)
    mov byte [es:RB_DOCH],0
    cmp byte [es:RB_DFULL],0
    je .tiles
    mov si,8000h                        ; everything: the shadows taken whole
    xor di,di
    mov cx,4096
    rep movsw
    mov si,0FE00h
    mov di,RB_DOAM
    mov cx,80
    rep movsw
    xor ax,ax                           ; and the change bytes from nothing
    mov di,RB_DTD
    mov cx,(RB_DLREG - RB_DTD) / 2
    rep stosw
    mov di,RB_DMROW
    mov cx,64 / 2
    rep stosw
    ret
.tiles:
    mov si,8000h                        ; tile data, a tile at a time
    xor di,di
    mov cx,6144 / 2
.t:
    repe cmpsw
    je .maps                            ; the rest the same
    mov ax,di
    dec ax
    dec ax
    and ax,0FFF0h                       ; the tile's first byte
    mov di,ax
    mov si,ax
    add si,8000h
    mov bx,ax
    mov cl,4
    shr bx,cl
    mov byte [es:RB_DTD+bx],1
    mov byte [es:RB_DTCH],1
    mov cx,8
    rep movsw                           ; into the shadow
    mov cx,6144
    sub cx,di
    shr cx,1
    jnz .t
.maps:
    mov si,9800h                        ; both maps, a word at a time
    mov di,1800h
    mov cx,1024
.m:
    repe cmpsw
    je .oam
    mov ax,[si-2]
    mov [es:di-2],ax
    mov byte [es:RB_DMD-1802h+di],1
    mov byte [es:RB_DMD-1801h+di],1
    mov byte [es:RB_DMCH],1
    mov bx,di                           ; its row too: a quick no for the
    sub bx,1802h                        ;   rest (BX / 32 without CL, which
    shl bx,1                            ;   is the scan's count)
    shl bx,1
    shl bx,1
    mov bl,bh
    xor bh,bh
    mov byte [es:RB_DMROW+bx],1
    or cx,cx
    jnz .m
.oam:
    mov si,0FE00h                       ; a sprite that moved or changed:
    mov di,RB_DOAM                      ;   the lines it left and the lines
    mov dx,40                           ;   it covers now
.o:
    mov ax,[si]
    mov bx,[si+2]
    cmp ax,[es:di]
    jne .ch
    cmp bx,[es:di+2]
    je .on
.ch:
    mov byte [es:RB_DOCH],1
    push ax
    mov al,[es:di]
    call ppu_dlines
    pop ax
    call ppu_dlines
    mov [es:di],ax
    mov [es:di+2],bx
.on:
    add si,4
    add di,4
    dec dx
    jnz .o
    ret

; ppu_dfast: FAST (every line's registers the frame's own and the last
; call's): RB_DLD gains every line under a changed map row of the background
; or the window, and under a sprite whose tile changed - judged a map row or
; a sprite at a time instead of a line at a time
ppu_dfast:
    mov al,[es:RB_DTCH]
    or al,[es:RB_DMCH]
    jz .r
    mov al,[PPU_REGS+0]
    test al,80h
    jz .r
    test al,01h
    jz .spr
    mov byte [es:RB_DMODE],0FFh         ; the background, a map row at a time
    xor dx,dx                           ; DL = the line
.bg:
    mov al,dl
    add al,[PPU_REGS+1]                 ; y = LY + SCY
    mov ah,al
    and ah,7
    mov dh,8
    sub dh,ah                           ; DH = the row's lines from here
    mov [PPU_LY],dl
    push dx
    call ppu_bgdirty
    pop dx
    jnc .bn
    call .mark
.bn:
    add dl,dh
    cmp dl,144
    jb .bg
    mov al,[PPU_REGS+0]                 ; the window, from WY down
    test al,20h
    jz .spr
    cmp byte [PPU_REGS+7],166
    ja .spr
    mov dl,[PPU_REGS+6]
    cmp dl,144
    jae .spr
    mov byte [PPU_WLINE],0
.win:
    mov dh,8
    mov [PPU_LY],dl
    push dx
    call ppu_wdirty
    pop dx
    jnc .wn
    call .mark
.wn:
    add byte [PPU_WLINE],8
    add dl,8
    jc .spr
    cmp dl,144
    jb .win
.spr:
    test byte [PPU_REGS+0],02h          ; the sprites whose tiles changed
    jz .r
    cmp byte [es:RB_DTCH],0
    je .r
    mov si,0FE00h
    mov cx,40
.s:
    mov bl,[si+2]
    and bl,0FEh
    xor bh,bh
    mov al,[es:RB_DTD+bx]
    or al,[es:RB_DTD+1+bx]
    jz .sn
    mov al,[si]
    call ppu_dlines
.sn:
    add si,4
    loop .s
.r:
    mov byte [PPU_LY],0
    mov byte [PPU_WLINE],0
    ret
.mark:                                  ; DH lines from DL into RB_DLD
    push bx
    push cx
    mov bl,dl
    xor bh,bh
    mov cl,dh
    xor ch,ch
.m:
    cmp bx,144
    jae .mr
    mov byte [es:RB_DLD+bx],1
    inc bx
    loop .m
.mr:
    pop cx
    pop bx
    ret

; ppu_dlines: AL = a sprite's Y - its rows Y-16 .. Y-1 marked in RB_DLD
ppu_dlines:
    push ax
    push bx
    push cx
    sub al,16
    mov cx,16
.r:
    cmp al,144
    jae .n
    mov bl,al
    xor bh,bh
    mov byte [es:RB_DLD+bx],1
.n:
    inc al
    loop .r
    pop cx
    pop bx
    pop ax
    ret

; ppu_ldirty: CF = 1 if line PPU_LY must be composed. DS = view, ES = damage.
ppu_ldirty:
    push ax
    push bx
    push cx
    push si
    push di
    mov bl,[PPU_LY]
    xor bh,bh
    cmp byte [es:RB_DFULL],0
    jne .regs                           ; (the registers are still kept)
    cmp byte [es:RB_DLD+bx],0
    jne .regs
    cmp byte [es:RB_DFAST],0            ; FAST: the registers are the same
    jne .vram
    mov ax,bx                           ; its registers and window line
    mov cl,10                           ;   against the last call's
    mul cl
    mov di,ax
    add di,RB_DLREG
    mov si,PPU_REGS
    mov cx,4
    repe cmpsw
    jne .regs
    mov al,[PPU_WLINE]
    cmp al,[es:di]
    jne .regs
    ; the background's row, the window's, and the sprites' tiles
.vram:
    mov al,[es:RB_DTCH]
    or al,[es:RB_DMCH]
    jz .clean                           ; no cell and no tile changed
    mov al,[PPU_REGS+0]
    test al,80h
    jz .clean                           ; the LCD off: white, as before
    test al,01h
    jz .spr
    call ppu_bgdirty
    jc .dirty
    call ppu_wdirty
    jc .dirty
.spr:
    test byte [PPU_REGS+0],02h
    jz .clean
    cmp byte [es:RB_DTCH],0
    je .clean
    call ppu_sdirty
    jc .dirty
.clean:
    clc
    jmp short .r
.regs:
    mov ax,bx                           ; keep them, and compose
    mov cl,10
    mul cl
    mov di,ax
    add di,RB_DLREG
    mov si,PPU_REGS
    mov cx,4
    rep movsw
    mov al,[PPU_WLINE]
    stosb
.dirty:
    stc
.r:
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; ppu_bgdirty: CF = 1 if a map cell or tile under the line's background
; changed - judged once per map row and first column, and kept
ppu_bgdirty:
    mov al,[PPU_REGS+0]
    and al,10h
    cmp al,[es:RB_DMODE]
    je .m
    mov [es:RB_DMODE],al
    mov word [es:RB_DBKEY],0
    mov word [es:RB_DWKEY],0
.m:
    mov dl,[PPU_LY]
    add dl,[PPU_REGS+1]
    mov bl,dl
    xor bh,bh
    and bl,0F8h
    shl bx,1
    shl bx,1
    mov si,9800h
    test byte [PPU_REGS+0],08h
    jz .m1
    mov si,9C00h
.m1:
    add si,bx                           ; SI = the map row
    mov cl,[PPU_REGS+2]
    shr cl,1
    shr cl,1
    shr cl,1                            ; CL = the first column
    cmp si,[es:RB_DBKEY]
    jne .judge
    cmp cl,[es:RB_DBCOL]
    jne .judge
    cmp byte [es:RB_DBRES],1            ; the verdict kept: CF = it was 1
    cmc
    ret
.judge:
    mov [es:RB_DBKEY],si
    mov [es:RB_DBCOL],cl
    call ppu_rowdirty
    mov al,0
    adc al,0
    mov [es:RB_DBRES],al
    shr al,1
    ret

; ppu_wdirty: CF = 1 if the window shows on this line and a cell or tile
; under it changed
ppu_wdirty:
    test byte [PPU_REGS+0],20h
    jz .no
    mov al,[PPU_LY]
    cmp al,[PPU_REGS+6]
    jb .no
    cmp byte [PPU_REGS+7],166
    ja .no
    mov bl,[PPU_WLINE]
    xor bh,bh
    and bl,0F8h
    shl bx,1
    shl bx,1
    mov si,9800h
    test byte [PPU_REGS+0],40h
    jz .m2
    mov si,9C00h
.m2:
    add si,bx
    cmp si,[es:RB_DWKEY]
    jne .judge
    cmp byte [es:RB_DWRES],1
    cmc
    ret
.judge:
    mov [es:RB_DWKEY],si
    xor cl,cl
    call ppu_rowdirty
    mov al,0
    adc al,0
    mov [es:RB_DWRES],al
    shr al,1
    ret
.no:
    clc
    ret

; ppu_rowdirty: SI = a map row, CL = its first column: CF = 1 if any of the
; 21 cells from there (wrapping at 32) changed, or the tile it names did
ppu_rowdirty:
    push bx
    push cx
    push dx
    mov dx,si
    sub dx,9800h                        ; DX = the row's offset in the maps
    cmp byte [es:RB_DTCH],0
    jne .full
    mov bx,dx                           ; no tile changed: the row's own
    push cx                             ;   byte answers (a cell outside the
    mov cl,5                            ;   21 shown costs a needless line,
    shr bx,cl                           ;   never a missed one)
    pop cx
    cmp byte [es:RB_DMROW+bx],0
    jne .yes
    clc
    jmp short .r
.full:
    mov ch,21
.c:
    and cl,31
    mov bl,cl
    xor bh,bh
    add bx,dx
    cmp byte [es:RB_DMD+bx],0
    jne .yes
    mov bl,[9800h+bx]                   ; the tile number
    xor bh,bh
    cmp byte [es:RB_DMODE],0
    jne .t                              ; 8000 mode: 0-255 as they are
    test bl,80h
    jnz .t                              ; 9000 mode: 128-255 are 128-255,
    inc bh                              ;   0-127 are 256-383
.t:
    cmp byte [es:RB_DTD+bx],0
    jne .yes
    inc cl
    dec ch
    jnz .c
    clc
    jmp short .r
.yes:
    stc
.r:
    pop dx
    pop cx
    pop bx
    ret

; ppu_sdirty: CF = 1 if a sprite that may cover the line uses a changed tile
ppu_sdirty:
    mov al,[PPU_LY]
    mov bl,41
    mul bl
    mov bx,ax
    mov cl,[PPU_LSPR+bx]
    or cl,cl
    jz .no
    lea si,[PPU_LSPR+1+bx]
.s:
    mov bl,[si]
    xor bh,bh
    shl bx,1
    shl bx,1
    mov bl,[0FE02h+bx]                  ; its tile: both of an 8x16's pair
    and bl,0FEh
    xor bh,bh
    cmp byte [es:RB_DTD+bx],0
    jne .yes
    cmp byte [es:RB_DTD+1+bx],0
    jne .yes
    inc si
    dec cl
    jnz .s
.no:
    clc
    ret
.yes:
    stc
    ret

; ppu_wstep: a line not composed still moves the window's line counter, as
; ppu_line would have
ppu_wstep:
    mov al,[PPU_REGS+0]
    test al,80h
    jz .r
    test al,01h
    jz .r
    test al,20h
    jz .r
    mov ah,[PPU_LY]
    cmp ah,[PPU_REGS+6]
    jb .r
    cmp byte [PPU_REGS+7],166
    ja .r
    inc byte [PPU_WLINE]
.r:
    ret

; ppu_dput: the composed line into the caller's buffer, if it differs - and
; RB_DCHG says so. DS = view, ES = damage.
ppu_dput:
    push es
    mov bx,es
    mov ch,[es:RB_DFULL]                ; everything: the buffer is not what
    mov al,[PPU_LY]                     ;   the screen shows
    mov cl,40
    mul cl
    les di,[es:RB_DOUT]
    add di,ax                           ; ES:DI = the line in the buffer
    mov dx,di
    or ch,ch
    jnz .diff
    mov si,PPU_OL
    mov cx,10
    repe cmpsw
    jne .diff
    mov si,PPU_OH                       ; (DI is at the line's byte 20)
    mov cx,10
    repe cmpsw
    je .same
.diff:
    mov di,dx
    mov si,PPU_OL
    mov cx,10
    rep movsw
    mov si,PPU_OH
    mov cx,10
    rep movsw
    mov es,bx
    mov bl,[PPU_LY]
    xor bh,bh
    mov byte [es:RB_DCHG+bx],1
    inc word [es:RB_DCNT]
.same:
    pop es
    ret

; ppu_oam: PPU_LSPR from OAM - for each line, the sprites whose 16 rows
; from Y - 16 cover it, in OAM order. The real height is LCDC's at the line,
; which a mid-frame write may change, so ppu_sprites checks it there.
ppu_oam:
    push di
    push es
    push ds
    pop es
    mov di,PPU_LSPR                     ; every count to 0
    mov cx,144
    xor al,al
.c:
    stosb
    add di,40
    loop .c
    mov si,0FE00h
    xor dl,dl                           ; DL = the OAM index
.s:
    mov ch,[si]                         ; Y: rows Y-16 .. Y-1, the first of
    sub ch,16                           ;   which may be off the top (wraps)
    mov dh,16
.r:
    cmp ch,144
    jae .nr
    mov al,ch
    mov bl,41
    mul bl
    mov bx,ax                           ; BX = the line's entry
    mov al,[PPU_LSPR+bx]
    inc byte [PPU_LSPR+bx]
    xor ah,ah
    add bx,ax
    mov [PPU_LSPR+1+bx],dl
.nr:
    inc ch
    dec dh
    jnz .r
    add si,4
    inc dl
    cmp dl,40
    jb .s
    pop es
    pop di
    ret

; ppu_taddr: PPU_TADDR for LCDC bit 4 in AL: tile n's row 0 at 8000 + 16n,
; or 9000 + 16 x (n as signed)
ppu_taddr:
    push ax
    push bx
    push cx
    and al,10h
    mov [PPU_TMODE],al
    mov word [PPU_BKEY],0               ; the address lists were the old mode's
    mov word [PPU_WKEY],0
    xor bx,bx
.t:
    mov ax,bx
    shr ax,1                            ; the tile number
    test byte [PPU_TMODE],10h
    jz .sg
    mov cl,4
    shl ax,cl
    add ax,8000h
    jmp short .st
.sg:
    cbw
    mov cl,4
    shl ax,cl
    add ax,9000h
.st:
    mov [PPU_TADDR+bx],ax
    add bx,2
    cmp bx,512
    jb .t
    pop cx
    pop bx
    pop ax
    ret

; ppu_mkrev: PPU_REV[b] = b with its bits reversed
ppu_mkrev:
    xor bx,bx
.b:
    mov al,bl
    mov cx,8
.r:
    shr al,1
    rcl ah,1
    loop .r
    mov [PPU_REV+bx],ah
    inc bl
    jnz .b
    mov byte [PPU_REVOK],1
    ret

; ppu_log: apply every raster log entry that takes effect on line PPU_LY
ppu_log:
    mov al,[PPU_LOGI]
    cmp al,[PPU_LOGN]
    jae .r
    xor ah,ah
    shl ax,1
    shl ax,1
    mov si,ax
    mov al,[RB_RLOG+si]                 ; its line
    cmp al,[PPU_LY]
    ja .r
    mov bl,[RB_RLOG+si+1]               ; the register, 40-4B
    mov al,[RB_RLOG+si+2]
    inc byte [PPU_LOGI]
    xor bh,bh
    sub bl,40h
    mov si,.slot
    mov bl,[cs:si+bx]
    cmp bl,0FFh
    je ppu_log
    mov [PPU_REGS+bx],al
    cmp bl,3                            ; a palette: rebuild its masks
    jb ppu_log
    cmp bl,6
    jae ppu_log
    call ppu_pal
    jmp ppu_log
.r:
    ret
.slot:  db 0, 0FFh, 1, 2, 0FFh, 0FFh, 0FFh, 3, 4, 5, 6, 7

; ppu_pal: PPU_PALM from the three palettes in PPU_REGS - for each, colour
; k's shade as two masks, 00h or FFh, one per shade bit
ppu_pal:
    push si
    push di
    mov si,PPU_REGS+3
    mov di,PPU_PALM
    mov dx,3
.p:
    lodsb
    mov cx,4
.k:
    xor bx,bx
    shr al,1
    sbb bl,bl                           ; bit 0 of colour k's shade
    shr al,1
    sbb bh,bh                           ; bit 1
    mov [di],bl
    mov [di+4],bh
    inc di
    loop .k
    add di,4
    dec dx
    jnz .p
    ; and BGP in algebraic normal form, for the background's word loop: a
    ; shade bit = D xor (bit 0 and A) xor (bit 1 and B) xor (both and C)
    mov si,PPU_PALM
    mov di,PPU_ANF
    mov cx,2
.a:
    mov al,[si]                         ; colour 0's
    mov ah,al
    mov [di],ax                         ; D
    mov bl,[si+1]
    xor bl,al
    mov bh,bl
    mov [di+2],bx                       ; A: colour 1 differs
    mov bl,[si+2]
    xor bl,al
    mov bh,bl
    mov [di+4],bx                       ; B: colour 2 differs
    mov bl,[si+3]
    xor bl,[si+1]
    xor bl,[si+2]
    xor bl,al
    mov bh,bl
    mov [di+6],bx                       ; C
    add si,4
    add di,8
    loop .a
    pop di
    pop si
    ret

; ppu_line: compose line PPU_LY into PPU_OL/PPU_OH
ppu_line:
    push es
    push di
    push ds
    pop es
    mov al,[PPU_REGS+0]
    test al,80h
    jnz .on
    xor ax,ax                           ; the LCD is off: the line is white
    mov di,PPU_OL
    mov cx,10
    rep stosw
    mov di,PPU_OH
    mov cx,10
    rep stosw
    jmp .done
.on:
    test al,01h
    jnz .bg
    xor ax,ax                           ; BG and window off: colour 0, and
    mov di,PPU_BL                       ;   every sprite above it
    mov cx,12
    rep stosw
    mov di,PPU_BH
    mov cx,12
    rep stosw
    jmp .pal
.bg:
    mov ah,al
    and ah,10h
    cmp ah,[PPU_TMODE]
    je .tm
    call ppu_taddr
.tm:
    ; the background: 21 tile rows from the map, shifted SCX AND 7 left
    mov dl,[PPU_LY]
    add dl,[PPU_REGS+1]                 ; y = LY + SCY
    mov bl,dl
    xor bh,bh
    and bl,0F8h
    shl bx,1
    shl bx,1                            ; (y AND F8h) x 4 = the map row
    mov si,9800h
    test al,08h
    jz .m1
    mov si,9C00h
.m1:
    add si,bx
    and dl,7
    mov bp,PPU_BLIST
    mov di,PPU_BKEY
    call ppu_list                       ; BP = the row's tile addresses
    mov cl,[PPU_REGS+2]                 ; SCX
    mov al,cl
    shr al,1
    shr al,1
    shr al,1                            ; the first tile column
    xor ah,ah
    shl ax,1
    mov si,bp
    add si,ax
    and cl,7
    mov di,PPU_BL
    call ppu_fetch
.win:
    ; the window, over the background from X = WX - 7 on
    mov al,[PPU_REGS+0]
    test al,20h
    jz .pal
    mov ah,[PPU_LY]
    cmp ah,[PPU_REGS+6]                 ; WY
    jb .pal
    cmp byte [PPU_REGS+7],166           ; WX
    ja .pal
    mov dl,[PPU_WLINE]
    inc byte [PPU_WLINE]
    mov bl,dl
    xor bh,bh
    and bl,0F8h
    shl bx,1
    shl bx,1
    and dl,7
    mov si,9800h
    test al,40h
    jz .m2
    mov si,9C00h
.m2:
    add si,bx
    mov bp,PPU_WLIST
    mov di,PPU_WKEY
    call ppu_list
    mov si,bp                           ; from the window's own column 0
    xor cl,cl
    mov di,PPU_WL
    call ppu_fetch
    call ppu_wplace
.pal:
    ; the background's shades through BGP: a copy when BGP is E4h, the
    ; identity, else its ANF a word - sixteen pixels - at a time
    cmp byte [PPU_REGS+3],0E4h
    jne .anf
    mov si,PPU_BL
    mov di,PPU_OL
    mov cx,10
    rep movsw
    mov si,PPU_BH
    mov di,PPU_OH
    mov cx,10
    rep movsw
    jmp short .spr
.anf:
    mov bp,PPU_ANF
    mov di,PPU_OL
    call ppu_anf
    mov bp,PPU_ANF+8
    mov di,PPU_OH
    call ppu_anf
.spr:
    test byte [PPU_REGS+0],02h
    jz .done
    call ppu_sprites
.done:
    pop di
    pop es
    ret

; ppu_anf: one shade plane of the background into DI, through the ANF words
; at BP (D A B C): D xor (bit0 and A) xor (bit1 and B) xor (both and C)
ppu_anf:
    mov si,PPU_BL
    mov cx,10
.w:
    lodsw                               ; bit 0
    mov bx,[si+PPU_BH-PPU_BL-2]         ; bit 1
    mov dx,ax
    and dx,bx
    and ax,[ds:bp+2]
    and bx,[ds:bp+4]
    and dx,[ds:bp+6]
    xor ax,bx
    xor ax,dx
    xor ax,[ds:bp+0]
    stosw
    loop .w
    ret

; ppu_list: BP = a list of the map row at SI's 32 tile addresses, twice -
; built only when [DI] says the list at BP holds another row. Kept: DL.
ppu_list:
    cmp [di],si
    je .r
    mov [di],si
    push ax
    push bx
    push cx
    push di
    mov di,bp
    mov cx,32
.t:
    lodsb
    xor ah,ah
    shl ax,1
    mov bx,ax
    mov ax,[PPU_TADDR+bx]
    mov [di],ax
    mov [di+64],ax
    add di,2
    loop .t
    pop di
    pop cx
    pop bx
    pop ax
.r:
    ret

; ppu_fetch: 20 bytes of a line into DI (bit 0) and DI+20h (bit 1) from the
; tile addresses at SI (one word each, DL = the row in the tile), the
; picture CL bits (0-7) left of the first tile's edge - the fine scroll, done
; as the bytes are fetched: each is the previous tile row and this one, as
; one 16-bit string, CL bits left.
ppu_fetch:
    push bp
    xor bh,bh
    mov bl,dl
    shl bl,1
    mov bp,bx                           ; BP = the row's offset in a tile
    lodsw
    mov bx,ax
    add bx,bp
    mov dx,[bx]                         ; DL, DH = the first tile's row
    mov ch,20
    or cl,cl
    jz .copy0
.t:
    lodsw
    mov bx,ax
    add bx,bp
    mov ax,[bx]                         ; the next tile's row
    mov bh,dl
    mov bl,al
    shl bx,cl
    mov [di],bh
    mov bh,dh
    mov bl,ah
    shl bx,cl
    mov [di+20h],bh
    mov dx,ax
    inc di
    dec ch
    jnz .t
    pop bp
    ret
.copy0:
    inc ch                              ; no fine scroll: 21 rows as they are
.copy:                                  ;   (the window shifts its own left)
    mov [di],dl
    mov [di+20h],dh
    inc di
    lodsw
    mov bx,ax
    add bx,bp
    mov dx,[bx]
    dec ch
    jnz .copy
    pop bp
    ret

; ppu_shl: the 21 bytes at SI, as one bit string, CL bits left (CL < 8);
; the first 20 are the result. Kept: CL.
ppu_shl:
    or cl,cl
    jz .r
    push bx
    push si
    mov bx,20
.b:
    mov ah,[si]
    mov al,[si+1]
    shl ax,cl
    mov [si],ah
    inc si
    dec bx
    jnz .b
    pop si
    pop bx
.r:
    ret

; ppu_wplace: the window's 21 fetched bytes over the background from pixel
; X = WX - 7, which may be -7 to 159
ppu_wplace:
    mov al,[PPU_REGS+7]
    sub al,7                            ; signed: -7..159
    jns .right
    neg al                              ; starts left of the screen: shift it
    mov cl,al                           ;   left and cover every pixel
    mov [PPU_TMP],cl
    mov si,PPU_WL
    call ppu_shl
    mov si,PPU_WH
    call ppu_shl
    mov si,PPU_WL
    mov di,PPU_BL
    mov cx,10
    rep movsw
    mov si,PPU_WH
    mov di,PPU_BH
    mov cx,10
    rep movsw
    ret
.right:
    ; byte B = X / 8, shift S = X AND 7: the window's bits move right by S
    ; into bytes B.., the pixels left of X in byte B keep the background
    mov bl,al
    shr bl,1
    shr bl,1
    shr bl,1
    xor bh,bh                           ; BX = B
    mov cl,al
    and cl,7                            ; CL = S
    mov ch,0FFh
    shr ch,cl                           ; CH = byte B's window mask
    xor si,si                           ; SI = the window byte index
    mov dx,0                            ; DX: the bits carried from the left
.w:
    cmp bx,20
    jae .r
    mov al,[PPU_WL+si]
    xor ah,ah
    ror ax,cl                           ; AL = this byte's bits, AH = carry
    or al,dl                            ; with the previous byte's carry
    mov dl,ah
    mov ah,[PPU_BL+bx]
    not ch
    and ah,ch                           ; keep the background left of X
    not ch
    and al,ch
    or al,ah
    mov [PPU_BL+bx],al
    mov al,[PPU_WH+si]
    xor ah,ah
    ror ax,cl
    or al,dh
    mov dh,ah
    mov ah,[PPU_BH+bx]
    not ch
    and ah,ch
    not ch
    and al,ch
    or al,ah
    mov [PPU_BH+bx],al
    mov ch,0FFh                         ; every byte after B is all window
    inc bx
    inc si
    jmp .w
.r:
    ret

; ppu_shade: AL, AH = a byte's colour bits 0 and 1 -> AL, AH = its shade's,
; through the palette whose masks are at BX. Kept: BX, CX, DX, SI, DI.
ppu_shade:
    push cx
    push dx
    push si
    mov cl,al
    and cl,ah                           ; CL = colour 3
    mov ch,al
    xor ch,cl                           ; CH = colour 1
    mov dl,ah
    xor dl,cl                           ; DL = colour 2
    mov dh,al
    or dh,ah
    not dh                              ; DH = colour 0
    mov al,dh
    and al,[bx+0]
    mov ah,ch
    and ah,[bx+1]
    or al,ah
    mov ah,dl
    and ah,[bx+2]
    or al,ah
    mov ah,cl
    and ah,[bx+3]
    or al,ah
    xchg ax,si                          ; SI's low byte = shade bit 0
    mov al,dh
    and al,[bx+4]
    mov ah,ch
    and ah,[bx+5]
    or al,ah
    mov ah,dl
    and ah,[bx+6]
    or al,ah
    mov ah,cl
    and ah,[bx+7]
    or al,ah                            ; AL = shade bit 1
    xchg ax,si
    mov dx,si
    mov ah,dl
    pop si
    pop dx
    pop cx
    ret

; ppu_sprites: up to ten sprites on line PPU_LY, in priority order, over
; PPU_OL/PPU_OH
ppu_sprites:
    ; find them, in OAM order
    mov byte [PPU_NSPR],0
    mov dl,8
    test byte [PPU_REGS+0],04h
    jz .h8
    mov dl,16
.h8:
    mov al,[PPU_LY]                     ; the line's candidates, from ppu_oam
    mov bl,41
    mul bl
    mov bx,ax
    mov al,[PPU_LSPR+bx]
    or al,al
    jz .sorted0
    mov [PPU_TMP],al                    ; candidates left
    lea bp,[PPU_LSPR+1+bx]              ; BP = its OAM indices
    mov di,PPU_SPR
.f:
    mov al,[ds:bp]
    inc bp
    xor ah,ah
    shl ax,1
    shl ax,1
    add ax,0FE00h
    mov si,ax                           ; SI = the sprite's OAM entry
    mov al,[PPU_LY]
    add al,16
    sub al,[si]                         ; the row within the sprite
    cmp al,dl
    jae .nf
    mov ah,[si+3]                       ; attr
    test ah,40h                         ; Y flip
    jz .ny
    mov bl,dl
    dec bl
    sub bl,al
    mov al,bl
.ny:
    mov bl,[si+2]                       ; the tile
    cmp dl,16
    jne .t8
    and bl,0FEh
.t8:
    xor bh,bh
    shl bx,1
    shl bx,1
    shl bx,1
    shl bx,1
    push ax
    xor ah,ah
    shl ax,1
    add bx,ax
    pop ax
    add bx,8000h
    mov cl,[bx]
    mov ch,[bx+1]
    test ah,20h                         ; X flip
    jz .nx
    mov bl,cl
    xor bh,bh
    mov cl,[PPU_REV+bx]
    mov bl,ch
    mov ch,[PPU_REV+bx]
.nx:
    mov al,[si+1]
    mov [di],al                         ; X
    mov [di+1],cl
    mov [di+2],ch
    mov [di+3],ah
    add di,4
    inc byte [PPU_NSPR]
    cmp byte [PPU_NSPR],10
    jae .sorted0
.nf:
    dec byte [PPU_TMP]
    jnz .f
.sorted0:
    ; insertion sort by X, stable: equal X keeps OAM order
    mov cl,[PPU_NSPR]
    xor ch,ch
    cmp cx,2
    jb .draw
    mov si,PPU_SPR+4
    dec cx
.is:
    mov ax,[si]
    mov dx,[si+2]
    mov di,si
.isl:
    cmp di,PPU_SPR
    je .isp
    cmp al,[di-4]
    jae .isp
    mov bx,[di-4]
    mov [di],bx
    mov bx,[di-2]
    mov [di+2],bx
    sub di,4
    jmp .isl
.isp:
    mov [di],ax
    mov [di+2],dx
    add si,4
    loop .is
.draw:
    ; the claimed mask starts empty
    xor ax,ax
    mov di,PPU_CL
    mov cx,12
    rep stosw
    mov si,PPU_SPR
    mov cl,[PPU_NSPR]
    xor ch,ch
    jcxz .r
.d:
    push cx
    push si
    call ppu_sprite
    pop si
    pop cx
    add si,4
    loop .d
.r:
    ret

; ppu_sprite: one sprite, SI = its PPU_SPR entry, over the line
ppu_sprite:
    mov al,[si]                         ; X: the screen pixel is X - 8
    cmp al,168
    jae .r
    or al,al
    jz .r
    mov bx,PPU_PALM+8
    test byte [si+3],10h
    jz .p0
    mov bx,PPU_PALM+16
.p0:
    push ax
    mov al,[si+1]
    mov ah,[si+2]
    mov [PPU_TMP],ax
    call ppu_shade                      ; AL, AH = its shades
    mov cx,ax
    pop ax
    ; the 8 pixels start at screen X - 8: byte B = (X - 8) >> 3 (B may be -1)
    sub al,8
    mov dl,al
    mov dh,0
    jnb .pos
    mov dh,0FFh                         ; negative: DX = X - 8, signed
.pos:
    mov bx,dx
    sar bx,1
    sar bx,1
    sar bx,1                            ; BX = B
    and dl,7                            ; DL = the shift S
    ; the left byte (B), if B >= 0
    push cx
    mov cl,dl
    mov al,[PPU_TMP]
    or al,[PPU_TMP+1]                   ; opaque: colour not 0
    xor ah,ah
    ror ax,cl                           ; AL = byte B's part, AH = byte B+1's
    pop cx
    push ax
    mov al,cl
    xor ah,ah
    push cx
    mov cl,dl
    ror ax,cl
    pop cx
    mov [PPU_TMP],ax                    ; shade bit 0, both halves
    mov al,ch
    xor ah,ah
    push cx
    mov cl,dl
    ror ax,cl
    pop cx
    mov cx,ax                           ; shade bit 1, both halves
    pop dx                              ; DL, DH = opaque, both halves
    or bx,bx
    js .right
    cmp bx,20
    jae .r
    mov al,dl
    mov ah,[PPU_TMP]
    push cx
    mov ch,cl
    call ppu_put
    pop cx
.right:
    inc bx
    cmp bx,20
    jae .r
    mov al,dh
    mov ah,[PPU_TMP+1]
    call ppu_put
.r:
    ret

; ppu_put: one byte of a sprite at line byte BX: AL = opaque, AH = shade bit
; 0, CH = shade bit 1. A pixel another sprite claimed first stays theirs; a
; behind-the-background pixel shows only over colour 0.
ppu_put:
    mov dl,[PPU_CL+bx]
    not dl
    and al,dl                           ; not claimed already
    or [PPU_CL+bx],al
    test byte [si+3],80h
    jz .vis
    mov dl,[PPU_BL+bx]                  ; behind the background: only over
    or dl,[PPU_BH+bx]                   ;   its colour 0
    not dl
    and al,dl
.vis:
    and ah,al
    and ch,al
    not al
    and [PPU_OL+bx],al
    and [PPU_OH+bx],al
    or [PPU_OL+bx],ah
    or [PPU_OH+bx],ch
    ret
