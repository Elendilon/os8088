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
PPU_DWREG       equ 0x4B7C          ; word: rb_renderd's WHOLE loop, the line's
                                    ;   RB_DLREG record
PPU_ILC         equ 0x4B7E          ; byte: this call DEFERS a parity (rb_ilace
                                    ;   1, or 2 and a scroll's whole frame)
PPU_PANY        equ 0x4B7F          ; byte: the last call deferred a line...
PPU_PNEW        equ 0x4B80          ; byte: ...and this one has
PPU_SMASK       equ 0x4B81          ; byte: a sprite's tile, FFh, or FEh at
                                    ;   8x16 (ppu_sprites)
PPU_OSCR        equ 0x4B82          ; word: the line's SCY:SCX at the last
                                    ;   call (ppu_lscr)
PPU_OAMOK       equ 0x4B84          ; byte: PPU_LSPR is built (0 in a new view)
PPU_LOGL        equ 0x4B85          ; byte: the line the next raster log entry
                                    ;   takes effect on (FFh: none left) -
                                    ;   ppu_log is called only from it on
PPU_RCH         equ 0x4B86          ; byte: a register was written (ppu_log, or
                                    ;   a new frame) since ppu_line's last
                                    ;   background setup
PPU_BNEXT       equ 0x4B87          ; byte: the line after that setup's...
PPU_BROW        equ 0x4B88          ; byte: ...and its row in the tile
PPU_LCOK        equ 0x4B89          ; byte: ppu_blist may use RB_DLC (rb_renderd)
PPU_OAMH        equ 0x4B8A          ; byte: the height PPU_LSPR was built for,
                                    ;   8 or 16 (0: none)
PPU_OAMD        equ 0x4B8C          ; word: 16 - PPU_OAMH
PPU_SPAN        equ 0x4B8E          ; byte: PAN-ALIGNED (rb_panon), the line's
                                    ;   offset: the pan for a line composed at
                                    ;   SCX - pan (a background aligned to
                                    ;   it), else 0...
PPU_PSH         equ 0x4B8F          ; byte: ...and 1 when it is composed as
                                    ;   ever and shifted right by the pan
PPU_PANM        equ 0x4B90          ; byte: the frame's pan, FFh: not aligned
PPU_SPANL       equ 0x4B91          ; byte: the last line's PPU_SPAN
PPU_WN          equ 0x4B92          ; word: words a plane a line: 10, 11
                                    ;   when aligned (21 bytes)
PPU_LINEV       equ 0x4B94          ; word: rb_renderd's line, ppu_line or
PPU_DPUTV       equ 0x4B96          ;   ppu_linep, and its ppu_dput(p)
PPU_OAMY        equ 0x6520          ; 40: the sprites' Ys PPU_LSPR was built from
PPU_LSCR        equ 0x7000          ; 144 words: each line's SCY:SCX at the
                                    ;   last call, kept when DOUBLED
PPU_SANF        equ 0x4B70          ; 2 x 6: OBP0 and OBP1 as A0 B0 C0 A1
                                    ;   B1 C1, a shade bit being (bit 0 and
                                    ;   A) xor (bit 1 and B) xor (both and
                                    ;   C) - colour 0 a sprite does not draw
PPU_ANF         equ 0x4B60          ; 16: BGP as words D A B C for the shade's
                                    ;   bit 0, then bit 1 (ppu_pal)
PPU_TADDR       equ 0x4C00          ; 512: tile n's row 0, for LCDC bit 4,
PPU_TADDRC      equ 0x4D00          ;   at PPU_TADDRC + 2 x (n as signed)
PPU_BLIST       equ 0x6600          ; 42 + 1: the 21 tile addresses a line
                                    ;   reads, and 1 when they are one tile,
PPU_WLIST       equ 0x6680          ; 42 + 1: for the background and the window
PPU_BKEY        equ 0x4B5A          ; word: the map row PPU_BLIST holds (or 0)
PPU_WKEY        equ 0x4B5C          ; word: ...PPU_WLIST
PPU_OSRC        equ 0x4B5E          ; word: where ppu_line left the line's
                                    ;   shades - PPU_OL, or PPU_BL itself
                                    ;   when BGP is the identity and no
                                    ;   sprite may cover it (bit 1 at +20h)
PPU_LSPR        equ 0x4E00          ; 144 x 41: per line, the count and the
                                    ;   OAM indices of the sprites that MAY
                                    ;   cover it (16 tall), in OAM order

rb_render:
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
    mov byte [PPU_LCOK],0
    mov byte [PPU_PANM],0FFh            ; (20 bytes a plane: never aligned)
    mov word [PPU_WN],10
    mov word [PPU_SPAN],0
    mov word [PPU_BKEY],0               ; the map may have changed since
    mov word [PPU_WKEY],0
    ; the state as the frame began: the snapshot, if this frame logged a write
    mov byte [PPU_LOGN],0
    mov byte [PPU_LOGI],0
    mov byte [PPU_LOGL],0
    mov byte [PPU_RCH],1
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
    call ppu_oam                        ; (the frame's LCDC and log known)
    mov byte [PPU_WLINE],0
    mov byte [PPU_LY],0
.line:
    mov al,[PPU_LY]
    cmp al,[PPU_LOGL]
    jb .nolog
    call ppu_log
.nolog:
    call ppu_line
    mov si,[PPU_OSRC]                   ; out: the 20 bytes of each plane
    mov cx,10
    rep movsw
    add si,0Ch                          ; bit 1 is at +20h
    mov cl,10
    rep movsw
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
RB_DFULL        equ 0x3120              ; byte: compose every line - 1 the
                                        ;   host's (its screen cleared), 2 a
                                        ;   scroll's (rb_renderd, .scroll)
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
RB_DLLOG        equ 0x3134              ; byte: the last call's frame's log
                                        ;   entries (FFh: more than RB_DLOGMAX)
RB_DSAME        equ 0x3135              ; byte: ppu_logsame's answer, 1 = same
RB_DSTALE       equ 0x3136              ; byte: the last call scrolled
                                        ;   (rb_renderd, .full)
RB_DSCR         equ 0x3137              ; byte: ppu_dscan is a scroll's
RB_DREG0        equ 0x3138              ; 8: the last call's registers
RB_DMROW        equ 0x3140              ; 64: a map row changed (2 x 32)
RB_DCOMP        equ 0x3180              ; word: lines composed (the host's to
                                        ;   read and clear: its log)
RB_DLOG         equ 0x3182              ; 256: the last call's raster log (its
                                        ;   count is RB_DLLOG), 64 entries at most
RB_DLOGMAX      equ 64
RB_DPEND        equ 0x3282              ; 144: a changed line INTERLACE left
                                        ;   for the next call (rb_ilace)
RB_DPAR         equ 0x3312              ; byte: the parity this call composes
RB_DLC          equ 0x3314              ; 32 x 68: per map row (Y / 8), the
                                        ;   background's PPU_BLIST for it: the
                                        ;   key (PPU_BKEY's, 0 none), the 21
                                        ;   addresses and the one-tile byte
                                        ;   (+2, 44 bytes), and the 21 map
                                        ;   bytes they were built from (+46)
RB_DLCN         equ 68
RB_DLCMODE      equ 0x3B94              ; byte: the tile mode they are for
RB_DMG_SIZE     equ 0x3B96

rb_dmgseg       dw 0                    ; the host's damage segment, or 0
rb_ilace        db 0                    ; the host's (3: DOUBLED, as 2 with the
                                        ;   odd lines the even ones' copies
                                        ;   meanwhile); 1 = INTERLACE, each call
                                        ;   (2: only a scroll's whole frames;
                                        ;   a still one composes what both
                                        ;   parities owe),
                                        ;   composes the lines of one parity,
                                        ;   the other's changes kept for the
                                        ;   next (REALBOY-SPEC 13.2)
rb_dhook        dw 0                    ; the host's near proc, called when the
                                        ;   scan is done (its log's clock), or 0;
                                        ;   every register its to keep
rb_dvga         dw 0                    ; the host's: a changed line goes to VGA
                                        ;   too, its two shade planes to planes
                                        ;   0 and 1 of this segment at 40 a
                                        ;   line (ppu_dvga), or 0
rb_panon        db 0                    ; the host's: 1 = PAN-ALIGNED - each
                                        ;   line 42 bytes (21 a plane), composed
                                        ;   for the card's pel panning to show
                                        ;   from pixel rb_panv on, which it
                                        ;   sets (REALBOY-SPEC 15.4)
rb_panv         db 0
rb_lhook        dw 0                    ; the host's near proc, PAN-ALIGNED:
                                        ;   called every eighth line stored and
                                        ;   every sixteenth written to a page,
                                        ;   DS = CS, every register its to keep
                                        ;   - a draw is longer than the border
                                        ;   a page flips in (rw_pgtry), or 0
rb_dvmm         db 0                    ; ...the plane the map mask holds
rb_torus        db 0                    ; the host's, PAN-ALIGNED: 1 = the
                                        ;   CANVAS (REALBOY-SPEC 15.5) - only
                                        ;   the overlay lines composed, and
                                        ;   rb_tpage puts a page right
rb_tseg         dw 0                    ; ...its state, RB_TSIZE bytes at 0
rb_tss          db 144                  ; ...THE STRIP's first line in force,
                                        ;   144 none (REALBOY-SPEC 15.5.1): the
                                        ;   host's to show under the split
rb_shook        dw 0                    ; ...and its near proc that lays the
                                        ;   split's region out for a strip at
                                        ;   AL (144 none), DS = CS, all kept
rb_tilsv        db 0                    ; (rb_ilace, kept while the canvas has
                                        ;   it Off)

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
    mov byte [cs:rb_dvmm],0FFh          ; (the host's mask: not known)
%ifndef RB_NOPAN
    mov al,[cs:rb_ilace]                ; THE CANVAS: no parity to defer - a
    mov [cs:rb_tilsv],al                ;   frame composes its overlays only
    cmp byte [cs:rb_torus],0            ;   (REALBOY-SPEC 15.5)
    je .nt
    mov byte [cs:rb_ilace],0
.nt:
%endif
    mov ds,[cs:rb_viewseg]
    mov ax,es
    mov es,[cs:rb_dmgseg]
    mov [es:RB_DOUT],di
    mov [es:RB_DOUT+2],ax
    mov word [es:RB_DCNT],0
    mov byte [es:RB_DSCR],0             ; (the claim is not zeroed)
    cmp byte [cs:rb_ilace],0
    je .par
    xor byte [es:RB_DPAR],1             ; the other parity's turn - or with
    cmp byte [cs:rb_ilace],3            ;   DOUBLED, the even lines' always,
    jne .pa                             ;   each odd one their copy
    mov byte [es:RB_DPAR],0
.pa:
    mov al,[PPU_PNEW]                   ; (lines owed from the last call, or
    mov [PPU_PANY],al                   ;   a still frame need visit none)
    mov byte [PPU_PNEW],0
.par:
    cmp byte [PPU_REVOK],0
    jne .rev
    call ppu_mkrev
    mov byte [PPU_TMODE],0FFh
.rev:
    mov byte [PPU_LCOK],1
    mov word [PPU_BKEY],0
    mov word [PPU_WKEY],0
    mov word [es:RB_DBKEY],0
    mov word [es:RB_DWKEY],0
    mov byte [es:RB_DMODE],0FFh
    mov byte [PPU_LOGN],0               ; the state as the frame began
    mov byte [PPU_LOGI],0
    mov byte [PPU_LOGL],0
    mov byte [PPU_RCH],1
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
    mov byte [PPU_PANM],0FFh            ; PAN-ALIGNED (the host's): the
    mov word [PPU_WN],10                ;   frame's pan, its last SCX AND 7,
    mov word [PPU_SPAN],0               ;   for the card to scroll by
    mov word [PPU_LINEV],ppu_line
    mov word [PPU_DPUTV],ppu_dput
%ifndef RB_NOPAN
    cmp byte [cs:rb_panon],0
    je .np
    cmp byte [cs:rb_torus],0
    jne .tf
    call ppu_pan
    jmp short .tp
.tf:
    call ppu_tframe                     ; THE CANVAS: line RB_TMID's state
.tp:
    mov [PPU_PANM],al
    mov [cs:rb_panv],al
    mov byte [PPU_WN],11
    mov byte [PPU_SPANL],0FFh
    mov word [PPU_LINEV],ppu_linep
    mov word [PPU_DPUTV],ppu_dputp
.np:
%endif
    mov byte [es:RB_DFAST],0
    call ppu_logsame                    ; ZF = 1: the same log (and kept)
    mov byte [es:RB_DSAME],0
    jnz .scroll
    mov byte [es:RB_DSAME],1
.scroll:
%ifndef RB_NOPAN
    cmp byte [cs:rb_torus],0            ; THE CANVAS: a scroll moves the card,
    jne .scan                           ;   not the lines (REALBOY-SPEC 15.5)
%endif
    ; SCROLLED: SCY or SCX moved since the last call, as the frame began or
    ; in a raster write the last call's frame had not - every line under it
    ; changes, so the scan of VRAM would only say what is composed anyway.
    ; Composed whole instead (RB_DFULL: the shadows copied, not compared),
    ; which a scrolling Super Mario Land paid ~5 ms a frame of a 286 for
    mov ax,[PPU_REGS+1]
    cmp ax,[es:RB_DREG0+1]
    jne .full
    cmp byte [es:RB_DSAME],0
    jne .scan
    xor ch,ch
    mov cl,[PPU_LOGN]
    cmp cl,RB_DLOGMAX
    ja .full
    jcxz .scan
    mov si,RB_RLOG+1
.sl:
    mov al,[si]
    cmp al,42h
    je .full
    cmp al,43h
    je .full
    add si,4
    loop .sl
    jmp short .scan
.full:
    cmp byte [es:RB_DFULL],0            ; (the host's: as it asked)
    jne .scan
    mov byte [es:RB_DSCR],1             ; the shadows kept current by the
    call ppu_dscan                      ;   marks' scan - what the game wrote,
    mov byte [es:RB_DSCR],0             ;   ~a block a frame - so the still
    mov byte [es:RB_DFULL],2            ;   frame after compares one frame's
    mov byte [es:RB_DSTALE],1           ;   (2: the buffer is still the screen,
    jmp short .scanned                  ;   so ppu_dput compares as ever)
.scan:
    mov al,0                            ; the first still frame after one is
    xchg al,[es:RB_DSTALE]              ;   COMPARED, not composed whole: the
    or al,al                            ;   shadows the scroll left are only
    jz .sc                              ;   older than the buffer, so what they
    cmp byte [cs:rb_ilace],2            ;   find changed is a line too many and
    jne .sc                             ;   never one too few - and a game whose
    cmp byte [es:RB_DFULL],0            ;   camera moves every other frame paid
    jne .sc                             ;   a whole frame for every still one.
    mov byte [es:RB_DFULL],2            ;   But SCROLLING composes it whole and
.sc:                                    ;   half, as a scroll's: half of a
                                        ;   whole is less than half of what a
                                        ;   comparison finds and judges
    call ppu_dscan                      ; the shadows, the changed bytes
.scanned:
    cmp word [cs:rb_dhook],0
    je .nohk
    call [cs:rb_dhook]
.nohk:
    cmp byte [es:RB_DFULL],0            ; the sprites' line lists: kept while
    jne .oam                            ;   OAM is and their height, as
    cmp byte [es:RB_DOCH],0             ;   nothing else moves them
    jne .oam
    call ppu_oamh
    cmp al,[PPU_OAMH]
    je .oamk
.oam:
    call ppu_oam
.oamk:
    ; FAST: the registers as they were at the frame's start, and the same
    ; raster writes as the last call's frame at the same lines (none, or a
    ; status bar's split every frame) - so every line's are, and the
    ; window's counter with them
    cmp byte [es:RB_DSAME],0
    je .slow
    cmp byte [es:RB_DFULL],0
    jne .slow
    mov si,PPU_REGS
    mov di,RB_DREG0
    mov cx,4
    repe cmpsw
    jne .slow
    mov byte [es:RB_DFAST],1
    mov al,[es:RB_DTCH]                 ; ...and nothing else changed either:
    or al,[es:RB_DMCH]                  ;   not a line to compose (but those
    or al,[es:RB_DOCH]                  ;   INTERLACE left the last call)
    cmp byte [cs:rb_ilace],0
    je .nofp
    or al,[PPU_PANY]
.nofp:
    or al,al
    jz .done
    call ppu_dfast                      ; RB_DLD = every line to compose
.slow:
    mov si,PPU_REGS
    mov di,RB_DREG0
    mov cx,4
    rep movsw
    mov byte [PPU_WLINE],0
    mov byte [PPU_LY],0
    mov byte [PPU_ILC],0                ; a parity deferred this call?
    mov al,[cs:rb_ilace]
    cmp al,1
    je .ie
    cmp al,2
    jb .ic
    cmp byte [es:RB_DFULL],2            ; (Scrolling and Doubled: a scroll's
    jne .ic                             ;   frame - and Scrolling's still one
.ie:                                    ;   after it, made one above)
    mov byte [PPU_ILC],1
.ic:
%ifndef RB_NOPAN
    cmp byte [cs:rb_torus],0            ; THE CANVAS: a loop of its own
    je .ic2
    jmp .tline
.ic2:
%endif
    cmp byte [es:RB_DFULL],0            ; WHOLE (a scroll, or the host's):
    je .line                            ;   every line is composed, so none
    cmp byte [PPU_ILC],0                ;   is judged - the registers kept
    jne .line                           ;   for the next call as ppu_ldirty
    mov word [PPU_DWREG],RB_DLREG       ;   keeps them, and nothing else
    cmp byte [cs:rb_ilace],0
    jne .whole
    xor ax,ax                           ; (Off: the change bytes cleared, and
    mov di,RB_DCHG                      ;   the count kept, once a frame - not
    mov cx,144 / 2                      ;   a line at a time)
    rep stosw
    add word [es:RB_DCOMP],144
.w0:
    mov al,[PPU_LY]
    cmp al,[PPU_LOGL]
    jb .w0l
    call ppu_log
.w0l:
    mov di,[PPU_DWREG]
    mov si,PPU_REGS
    movsw
    movsw
    movsw
    movsw
    mov al,[PPU_WLINE]
    stosb
    inc di
    mov [PPU_DWREG],di
    call [PPU_LINEV]
    call [PPU_DPUTV]
    inc byte [PPU_LY]
    cmp byte [PPU_LY],144
    jb .w0
    jmp .done
.whole:
    mov al,[PPU_LY]
    cmp al,[PPU_LOGL]
    jb .wlog
    call ppu_log
.wlog:
    mov bl,[PPU_LY]
    xor bh,bh
    mov byte [es:RB_DCHG+bx],0
    cmp byte [cs:rb_ilace],0            ; (owed nothing now, whichever
    je .wn                              ;   parity it was)
    mov byte [es:RB_DPEND+bx],0
    cmp byte [cs:rb_ilace],3            ; (DOUBLED: the line's scroll kept)
    jne .wh
    call ppu_lscr
.wh:
.wn:
    mov di,[PPU_DWREG]
    mov si,PPU_REGS
    movsw
    movsw
    movsw
    movsw
    mov al,[PPU_WLINE]
    stosb
    inc di                              ; (a record is 10: ppu_ldirty's)
    mov [PPU_DWREG],di
    inc word [es:RB_DCOMP]
    call [PPU_LINEV]
    call [PPU_DPUTV]
    inc byte [PPU_LY]
    cmp byte [PPU_LY],144
    jb .whole
    jmp .done
.line:
    mov al,[PPU_LY]
    cmp al,[PPU_LOGL]
    jb .llog
    call ppu_log
.llog:
    mov bl,[PPU_LY]
    xor bh,bh
    mov byte [es:RB_DCHG+bx],0
    cmp byte [cs:rb_ilace],3            ; (DOUBLED: the line's scroll kept)
    jne .lh
    call ppu_lscr
.lh:
    cmp byte [cs:rb_ilace],0            ; INTERLACE: left by the last call
    je .nip
    cmp byte [es:RB_DPEND+bx],0
    jne .comp
.nip:
    cmp byte [es:RB_DFAST],0
    je .judge
    cmp byte [es:RB_DLD+bx],0           ; FAST: judged already, by rows
    je .skip
    jmp short .comp
.judge:
    call ppu_ldirty                     ; CF = 1: compose it
    jnc .skip
.comp:
    cmp byte [cs:rb_ilace],0
    je .comp2
    mov bl,[PPU_LY]                     ; (ppu_ldirty's BX is its own)
    xor bh,bh
    cmp byte [PPU_ILC],0                ; (Scrolling, still: every line, the
    je .ilc                             ;   ones a scroll left with them)
    cmp byte [es:RB_DFULL],1            ; (the host's whole: every line)
    je .ilc
    mov al,bl
    xor al,[es:RB_DPAR]
    test al,1
    jz .ilc
    cmp byte [cs:rb_ilace],3            ; DOUBLED: a line whose own scroll did
    jne .dfr                            ;   not move (a status bar) is composed
    mov ax,[PPU_REGS+1]                 ;   as ever - doubled it would lose its
    cmp ax,[PPU_OSCR]                   ;   detail, and left, a digit that
    je .ilc                             ;   changes would be half of two
.dfr:
    mov byte [es:RB_DPEND+bx],1         ; the other parity's: the next call's
    mov byte [PPU_PNEW],1
    cmp byte [cs:rb_ilace],3            ; DOUBLED: meanwhile the even line
    jne .skip                           ;   above, which was composed just now
    call [PPU_DPUTV]                    ;   ([PPU_OSRC]), in its place
    jmp short .skip
.ilc:
    mov byte [es:RB_DPEND+bx],0
.comp2:
    inc word [es:RB_DCOMP]
    call [PPU_LINEV]
    call [PPU_DPUTV]                    ; into the buffer if it differs
    jmp short .next
.skip:
    call ppu_wstep                      ; the window's counter, as ppu_line
.next:
    inc byte [PPU_LY]
    cmp byte [PPU_LY],144
    jb .line
%ifndef RB_NOPAN
.tline:
    ; THE CANVAS (REALBOY-SPEC 15.5): a clean line is not composed at all,
    ; and an overlay whose buffer line is stale is composed whatever the
    ; judges say (its registers kept for them); the frame's overlay lines
    ; listed (ppu_tcls) for rb_tpage. The host's whole is every line stale.
    ; FAST with no sprite moved: every line's verdict and bytes are the last
    ; call's, so only the overlays are visited - in Kirby's Dream Land, whose
    ; tiles change nearly every frame, that is most frames
    cmp byte [es:RB_DFAST],0
    je .tall
    cmp byte [es:RB_DOCH],0
    jne .tall
    mov word [cs:rb_tovi],0
.to:
    mov bx,[cs:rb_tovi]
    cmp bx,[cs:rb_tovn]
    jae .tod
    mov bl,[cs:rb_tovl+bx]
    xor bh,bh
    mov [PPU_LY],bl
    cmp bl,[PPU_LOGL]
    jb .to1
    call ppu_log
    mov bl,[PPU_LY]
    xor bh,bh
.to1:
    cmp byte [es:RB_DLD+bx],0
    je .tos
    inc word [es:RB_DCOMP]
    call [PPU_LINEV]
    call [PPU_DPUTV]
    jmp short .ton
.tos:
    test byte [PPU_REGS+0],20h
    jz .ton
    call ppu_wstep
.ton:
    inc word [cs:rb_tovi]
    jmp short .to
.tod:
    mov al,[cs:rb_tss]                  ; ...then the strip's lines, in order
    cmp al,144
    jae .tsd
    mov [PPU_LY],al
.ts1:
    mov bl,[PPU_LY]
    cmp bl,[PPU_LOGL]
    jb .ts2
    call ppu_log
    mov bl,[PPU_LY]
.ts2:
    xor bh,bh
    cmp byte [cs:rb_tsall],0
    jne .ts3
    cmp byte [es:RB_DLD+bx],0
    je .ts4
.ts3:
    inc word [es:RB_DCOMP]
    call [PPU_LINEV]
    call [PPU_DPUTV]
    jmp short .ts5
.ts4:
    test byte [PPU_REGS+0],20h
    jz .ts5
    call ppu_wstep
.ts5:
    inc byte [PPU_LY]
    cmp byte [PPU_LY],144
    jb .ts1
.tsd:
    jmp .done
.tall:
    mov word [cs:rb_tovn],0
    mov byte [cs:rb_tli],0FFh           ; (the registers judged at line 0)
    mov word [cs:rb_tlsp],PPU_LSPR
.tl:
    mov al,[PPU_LY]
    cmp al,[PPU_LOGL]
    jb .tl1
    call ppu_log
.tl1:
    mov bl,[PPU_LY]
    xor bh,bh
    cmp bl,[cs:rb_tss]                  ; THE STRIP's: never an overlay,
    jae .tsl                            ;   composed when it changed
    call ppu_tcls
    jnc .tsk
    or al,al
    jnz .tst
    cmp byte [es:RB_DFAST],0
    je .tj
    cmp byte [es:RB_DLD+bx],0
    je .tsk
    jmp short .tc
.tj:
    call ppu_ldirty
    jnc .tsk
    jmp short .tc
.tst:
    call ppu_ldirty
.tc:
    inc word [es:RB_DCOMP]
    call [PPU_LINEV]
    call [PPU_DPUTV]
    jmp short .tn
.tsk:
    test byte [PPU_REGS+0],20h          ; (the window's counter, as ppu_line)
    jz .tn
    call ppu_wstep
    jmp short .tn
.tsl:
    mov byte [cs:rb_tcls+bx],0
    mov byte [cs:rb_tstl+bx],1          ; (the canvas's, should it go off)
    cmp byte [cs:rb_tsall],0
    jne .tsc
    cmp byte [es:RB_DFAST],0
    je .tsj
    cmp byte [es:RB_DLD+bx],0
    je .tsk
    jmp short .tsc
.tsj:
    call ppu_sldirty
    jnc .tsk
.tsc:
    inc word [es:RB_DCOMP]
    call [PPU_LINEV]
    call [PPU_DPUTV]
.tn:
    add word [cs:rb_tlsp],41
    inc byte [PPU_LY]
    cmp byte [PPU_LY],144
    jb .tl
%endif
.done:
%ifndef RB_NOPAN
    cmp byte [cs:rb_torus],0            ; THE CANVAS: the cells the scan
    je .tdn                             ;   found changed, owed to the pages
    call ppu_tmark
    mov al,[cs:rb_tilsv]
    mov [cs:rb_ilace],al
.tdn:
%endif
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

; ppu_logsame: ZF = 1 if this frame's raster log (PPU_LOGN entries at
; RB_RLOG) is the one the last call's frame had, which is then this one's.
; DS = view, ES = damage. Kept: everything but AX, CX, SI, DI.
ppu_logsame:
    mov al,[PPU_LOGN]
    cmp al,RB_DLOGMAX
    jbe .fit
    mov al,0FFh                         ; too many to keep: never the same
.fit:
    mov ah,[es:RB_DLLOG]
    mov [es:RB_DLLOG],al
    cmp al,0FFh
    je .no
    xor ch,ch
    mov cl,al
    shl cx,1                            ; entries x 2 words
    cmp al,ah
    jne .keep
    jcxz .r                             ; none, as before: ZF = 1
    push cx
    mov si,RB_RLOG
    mov di,RB_DLOG
    repe cmpsw
    pop cx
    je .r
.keep:
    mov si,RB_RLOG                      ; another log: kept for the next call
    mov di,RB_DLOG
    rep movsw
.no:
    or al,1                             ; ZF = 0 (AL is not 0 here, or ...
    cmp al,0                            ;   ...it is 1 now): another log
.r:
    ret

; ppu_dscan: VRAM and OAM against the shadows. DS = view, ES = damage.
ppu_dscan:
    mov word [es:RB_DTCH],0             ; (and RB_DMCH)
    mov byte [es:RB_DOCH],0
    cmp byte [es:RB_DFULL],0
    je .marks
    call .unmark
    call ppu_lcflush                    ; (and the address lists kept)
    mov si,8000h
    xor di,di
    mov cx,4096
    rep movsw
    mov si,0FE00h
    mov di,RB_DOAM
    mov cx,80
    rep movsw
    xor ax,ax                           ; and the change bytes from nothing
    cmp byte [es:RB_DFULL],2            ; (a scroll's: the host's count kept)
    je .dc
    mov [es:RB_DCOMP],ax
.dc:
    mov di,RB_DTD
    mov cx,(RB_DLREG - RB_DTD) / 2
    rep stosw
    mov di,RB_DMROW
    mov cx,64 / 2
    rep stosw
    ret
.unmark:                                ; the marks and the copy idiom's
    push es                             ;   flag cleared (DS = the view)
    push ds
    pop es
    mov di,RB_VMARK
    mov cx,512 / 2
    xor ax,ax
    rep stosw
    mov [RB_VALL],al
    mov [RB_VLN],ax                     ; (and vr_new's list)
    pop es
    ret
.marks:
    ; only the 16-byte blocks the core marked as it wrote them (vr_wr,
    ; REALBOY-SPEC 13.2.2) - unless the copy idiom wrote VRAM, which marks
    ; none: then all of it, as before the marks
    cmp byte [RB_VALL],0
    jne .all
    mov dx,es                           ; DX = the damage memory
    mov cx,[RB_VLN]                     ; the pairs vr_new listed as it
    mov word [RB_VLN],0                 ;   marked them - in play about one
    cmp cx,RB_VLMAX                     ;   a frame - unless the list ran
    jae .sweep                          ;   out: then all 512 marks
    jcxz .vd
    mov si,RB_VLIST
.vl:
    lodsb                               ; a pair of blocks
    xor ah,ah
    mov bx,ax
    shl bx,1                            ; its first block, and its marks
    cmp word [RB_VMARK+bx],0
    je .vn                              ; (listed twice: done already)
    mov word [RB_VMARK+bx],0
    push cx
    push si
    call .blk
    inc bx
    call .blk
    pop si
    pop cx
.vn:
    loop .vl
.vd:
    jmp .oam
.sweep:
    push ds
    pop es
    mov di,RB_VMARK
    mov cx,512 / 2
    xor ax,ax
.f:
    repe scasw                          ; a word of marks: two blocks
    je .fd
    mov word [es:di-2],0
    mov bx,di
    sub bx,RB_VMARK + 2                 ; BX = the first block
    push cx
    push di
    mov es,dx
    call .blk
    inc bx
    call .blk
    pop di
    pop cx
    push ds
    pop es
    xor ax,ax
    or cx,cx
    jnz .f
.fd:
    mov es,dx
    jmp .oam
.blk:                                   ; block BX against its shadow
    mov si,bx
    mov cl,4
    shl si,cl
    mov di,si                           ; DI = its shadow, SI = VRAM
    add si,8000h
    mov cx,8
    cmp bx,180h
    jae .bm
    repe cmpsw                          ; a tile's: whole, as .t's
    je .br
    mov si,bx                           ; (from its start again)
    mov cl,4
    shl si,cl
    mov di,si
    add si,8000h
    mov cx,8
    rep movsw
    mov byte [es:RB_DTD+bx],1
    mov byte [es:RB_DTCH],1
.br:
    ret
.bm:                                    ; a map's: word by word, as .m's
    repe cmpsw
    je .br
    call .mword
    or cx,cx
    jnz .bm
    ret
.mword:                                 ; the map word before SI/DI changed
    mov ax,[si-2]
    mov [es:di-2],ax
    mov byte [es:RB_DMD-1802h+di],1
    mov byte [es:RB_DMD-1801h+di],1
    mov byte [es:RB_DMCH],1
    push bx
    mov bx,di                           ; its row too: a quick no for the
    sub bx,1802h                        ;   rest (BX / 32 without CL, which
    shl bx,1                            ;   is the scan's count)
    shl bx,1
    shl bx,1
    mov bl,bh
    xor bh,bh
    mov byte [es:RB_DMROW+bx],1
    pop bx
    ret
.all:
    call .unmark
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
    call .mword
    or cx,cx
    jnz .m
.oam:
    cmp byte [es:RB_DSCR],0             ; a scroll's: every line is composed,
    je .oam1                            ;   so no line is marked - OAM's
    mov si,0FE00h                       ;   shadow taken whole (a scroll
    mov di,RB_DOAM                      ;   moves every X: 1,280 marks a
    mov cx,80                           ;   frame nothing would read)
    rep movsw
    mov byte [es:RB_DOCH],1
    ret
.oam1:
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
ppu_dlines:                             ; (one clipped fill)
    push ax
    push cx
    push di
    xor ah,ah
    mov cx,ax                           ; CX = Y, the end (exclusive)
    sub al,16                           ; AX = Y - 16, the first
    jae .lo
    xor al,al                           ; (Y < 16: from row 0)
.lo:
    cmp cx,144
    jbe .h
    mov cx,144
.h:
    sub cx,ax
    jle .r                              ; (Y >= 160: none on the screen)
    mov di,ax
    add di,RB_DLD
    mov al,1
    rep stosb
.r:
    pop di
    pop cx
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
    mov bl,[si]                         ; (its offset in OAM)
    xor bh,bh
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
    mov al,[PPU_LY]
    mov cl,40
    mul cl                              ; AX = the line's offset, kept
    push es
    mov si,[PPU_OSRC]
    cmp byte [es:RB_DFULL],1            ; everything: the buffer is not what
    les di,[es:RB_DOUT]                 ;   the screen shows (2, a scroll's,
    je .all                             ;   is: compared as ever)
    add di,ax                           ; ES:DI = the line in the buffer
    mov cx,10
    repe cmpsw
    jne .d0
    add si,0Ch                          ; bit 1 is at +20h (DI is at the
    mov cl,10                           ;   line's byte 20)
    repe cmpsw
    je .same
    dec si                              ; bit 1 from its first word that
    dec si                              ;   differs on
    dec di
    dec di
    inc cx
    rep movsw
    jmp short .vga
.d0:
    dec si                              ; bit 0 from its first word that
    dec si                              ;   differs on, then bit 1
    dec di
    dec di
    inc cx
    rep movsw
    add si,0Ch
    mov cl,10
    rep movsw
    jmp short .vga
.all:
    add di,ax
    mov cx,10
    rep movsw
    add si,0Ch
    mov cl,10
    rep movsw
.vga:
    cmp word [cs:rb_dvga],0
    je .mk
    call ppu_dvga                       ; (AX = 40 x the line, still)
.mk:
    pop es
    mov bl,[PPU_LY]
    xor bh,bh
    mov byte [es:RB_DCHG+bx],1
    inc word [es:RB_DCNT]
    ret
.same:
    pop es
    ret

%ifndef RB_NOPAN
; ppu_dputp: ppu_dput PAN-ALIGNED - 42 bytes a line, each plane's 21 (the
; pan's leftmost pixels and the last byte's tail never shown), the buffer at
; offset 0; no VGA: a changed line is OWED to each of the host's three pages
; instead (RB_PGMSK, rb_tpage)
ppu_dputp:
    mov al,[PPU_LY]
    mov cl,42
    mul cl
    push es
    mov si,[PPU_OSRC]
    cmp byte [es:RB_DFULL],1
    les di,[es:RB_DOUT]
    je .all
    mov di,ax                           ; ES:DI = the line in the buffer
    mov cx,10
    repe cmpsw
    jne .w0
    cmpsb
    jne .b0
    add si,0Bh                          ; bit 1 at +20h
    mov cl,10
    repe cmpsw
    jne .w1
    cmpsb
    je .same
    dec si
    dec di
    movsb
    jmp short .mk
.w1:
    dec si                              ; from the first word that differs
    dec si
    dec di
    dec di
    inc cx
    rep movsw
    movsb
    jmp short .mk
.w0:
    dec si
    dec si
    dec di
    dec di
    inc cx
    rep movsw
    movsb
    jmp short .p1
.b0:
    dec si
    dec di
    movsb
.p1:
    add si,0Bh
    mov cx,10
    rep movsw
    movsb
    jmp short .mk
.all:
    mov di,ax
    mov cx,10
    rep movsw
    movsb
    add si,0Bh
    mov cl,10
    rep movsw
    movsb
.mk:
    mov bl,[PPU_LY]
    xor bh,bh
    mov byte [es:RB_PGMSK+bx],1         ; owed to every page
    mov byte [es:RB_PGMSK+144+bx],1
    mov byte [es:RB_PGMSK+288+bx],1
    pop es
    mov byte [es:RB_DCHG+bx],1
    inc word [es:RB_DCNT]
    test bl,7                           ; every eighth line, the host's flip
    jnz .r                              ;   looked at (rb_lhook)
    jmp ppu_lhook
.r:
    ret
.same:
    pop es
    ret

; RB_PGMSK: the host's three pages' owed lines - a byte a line at RB_PGMSK +
; 144 x the page, in the buffer's segment, which ppu_dputp sets for every
; page as it stores a changed line and rb_tpage clears as it writes one
; (THE CANVAS, REALBOY-SPEC 15.5)
RB_PGMSK        equ 144 * 42

; ppu_lhook: [rb_lhook], the host's, with DS = CS and every register kept
ppu_lhook:
    cmp word [cs:rb_lhook],0
    je .r
    push ds
    push cs
    pop ds
    call [cs:rb_lhook]
    pop ds
.r:
    ret
%endif

; ppu_lscr: DOUBLED's history - the line's SCY:SCX into PPU_LSCR, and the
; last call's into PPU_OSCR. DS = view; BX = the line. Kept: all but AX
ppu_lscr:
    push bx
    shl bx,1
    mov ax,[PPU_REGS+1]
    xchg ax,[PPU_LSCR+bx]
    mov [PPU_OSCR],ax
    pop bx
    ret

; ppu_dvga: the line just composed to VGA (rb_dvga), shade bit 0 to plane 0
; and bit 1 to plane 1, the plane the map mask holds first so a line turns
; it once - written where it is decided, not by a second pass over the
; buffer. DS = view; AX = 40 x the line, as ppu_dput left it
ppu_dvga:
    push dx
    mov di,ax
    mov es,[cs:rb_dvga]
    mov dx,3C4h
    mov si,[PPU_OSRC]
    cmp byte [cs:rb_dvmm],1
    je .one
    cmp byte [cs:rb_dvmm],0
    je .z
    mov ax,0102h
    out dx,ax
.z:
    mov cx,10                           ; plane 0, then 1
    rep movsw
    add si,0Ch
    sub di,20
    mov ax,0202h
    out dx,ax
    mov cl,10
    rep movsw
    mov byte [cs:rb_dvmm],1
    pop dx
    ret
.one:
    add si,20h                          ; plane 1, then 0
    mov cx,10
    rep movsw
    sub si,20h + 20
    sub di,20
    mov ax,0102h
    out dx,ax
    mov cl,10
    rep movsw
    mov byte [cs:rb_dvmm],0
    pop dx
    ret

; ppu_oam: PPU_LSPR from OAM - for each line, the sprites whose 16 rows
; from Y - 16 cover it, in OAM order, as their offsets in OAM (4 x index).
; The real height is LCDC's at the line, which a mid-frame write may change,
; so ppu_sprites checks it there - and the lists are built 8 tall when it is
; 8 for the whole frame (LCDC bit 2 clear as it began and no raster write to
; LCDC), so that half the candidates of 8x8 sprites are not looked at.
; Only the rows on the screen are walked: a sprite parked at Y = 0 costs
; nothing. The lists hang on the 40 Ys alone,
; so they are built again only when one moved: a sprite that went sideways
; or changed its tile, or a scroll that moved them all, leaves them be.
ppu_oam:
    push di
    push es
    push ds
    pop es
    call ppu_oamh
    mov si,0FE00h
    mov di,PPU_OAMY
    mov cx,40
    cmp al,[PPU_OAMH]                   ; (another height: all built again)
    je .hk
    mov [PPU_OAMH],al
    neg al
    add al,16
    cbw
    mov [PPU_OAMD],ax
    jmp short .new
.hk:
    cmp byte [PPU_OAMOK],0
    je .new
    xor dx,dx                           ; DL = the OAM offset, DH = the
.mv:                                    ;   sprites moved: a few are each
    mov al,[si]                         ;   moved in the lists it left and
    mov ah,[di]                         ;   joined (a sprite one row down is
    cmp al,ah                           ;   two rows' lists, not sixteen);
    je .mvn                             ;   past PPU_OAMFEW, all built again
    inc dh
    cmp dh,PPU_OAMFEW
    ja .new
    mov [di],al
    push si
    push di
    call ppu_oamv
    pop di
    pop si
.mvn:
    add si,4
    inc di
    add dl,4
    cmp dl,160
    jb .mv
    jmp short .done
.new:
    mov byte [PPU_OAMOK],1
    mov si,0FE00h
    mov di,PPU_OAMY
    mov cx,40
.yc:
    lodsb
    add si,3
    stosb
    loop .yc
    mov di,PPU_LSPR                     ; every count to 0
    mov cx,144
    xor al,al
.c:
    stosb
    add di,40
    loop .c
    mov si,0FE00h
    xor dl,dl                           ; DL = the OAM offset
    mov dh,41
.s:
    mov al,[si]                         ; rows Y-16 .. Y-1 (or Y-9), cut to
    xor ah,ah                           ;   0 .. 143
    mov bx,ax
    sub bx,16
    jge .lo
    xor bx,bx
.lo:
    sub ax,[PPU_OAMD]
    cmp ax,144
    jle .hi
    mov ax,144
.hi:
    sub ax,bx
    jle .ns
    mov cx,ax                           ; CX = its rows on the screen
    mov al,bl
    mul dh
    mov di,ax                           ; DI = the first one's entry
.r:
    mov bl,[PPU_LSPR+di]
    inc byte [PPU_LSPR+di]
    xor bh,bh
    mov [PPU_LSPR+1+bx+di],dl
    add di,41
    loop .r
.ns:
    add si,4
    add dl,4
    cmp dl,160
    jb .s
.done:
    pop es
    pop di
    ret

; ppu_oamh: AL = the height the lists are built for - 16 if LCDC says so
; at the frame's start or the frame writes LCDC at all, else 8. Kept: all
; but AX, CX, SI
ppu_oamh:
    mov al,16
    test byte [PPU_REGS+0],04h
    jnz .r
    xor ch,ch
    mov cl,[PPU_LOGN]
    jcxz .h8
    mov si,RB_RLOG+1
.l:
    cmp byte [si],40h
    je .r
    add si,4
    loop .l
.h8:
    mov al,8
.r:
    ret

; ppu_oamv: the sprite at OAM offset DL moved from Y = AH to Y = AL - out of
; the line lists of the rows it covered and does not, into those of the rows
; it covers and did not, each list kept in OAM order. ES = DS. Kept: DX
PPU_OAMFEW      equ 8
ppu_oamv:
    call .rows
    mov cx,bx                           ; CX = the new rows' first and end
    mov al,ah
    call .rows                          ; BX = the old ones'
    ; out of the old rows before the new ones' first and from their end on
    push cx
    mov al,bl                           ; [old first, min(old end, new first))
    mov ah,bh
    cmp ah,cl
    jbe .o1
    mov ah,cl
.o1:
    call .out
    pop cx
    push cx
    mov al,bl                           ; [max(old first, new end), old end)
    cmp al,ch
    jae .o2
    mov al,ch
.o2:
    mov ah,bh
    call .out
    pop cx
    mov al,cl                           ; into the new rows before the old
    mov ah,ch                           ;   ones' first and from their end
    cmp ah,bl
    jbe .i1
    mov ah,bl
.i1:
    call .in
    mov al,cl
    cmp al,bh
    jae .i2
    mov al,bh
.i2:
    mov ah,ch
    jmp short .in
.rows:                                  ; Y in AL -> BL, BH = the rows Y-16
    push ax                             ;   .. Y-1 (or Y-9) cut to 0 .. 144,
    xor ah,ah                           ;   BL <= BH; AX kept
    mov bx,ax
    sub bx,16
    jge .r1
    xor bx,bx
.r1:
    sub ax,[PPU_OAMD]
    cmp ax,144
    jle .r2
    mov ax,144
.r2:
    cmp ax,bx
    jge .r3
    mov ax,bx
.r3:
    mov bh,al
    pop ax
    ret
.out:                                   ; rows AL .. AH-1: DL out of each list
    cmp al,ah
    jae .x
    push bx
    push cx
    mov bl,ah
    sub bl,al
    push bx                             ; (the count, BL)
    mov ah,41
    mul ah
    mov bx,ax
    add bx,PPU_LSPR                     ; BX = the first row's list
    pop ax                              ; AL = the rows
.ol:
    mov cl,[bx]
    xor ch,ch
    lea di,[bx+1]
    push ax
    mov al,dl
    repne scasb                         ; DI past it, CX = the ones after it
    mov si,di
    dec di
    rep movsb
    pop ax
    dec byte [bx]
    add bx,41
    dec al
    jnz .ol
    pop cx
    pop bx
.x:
    ret
.in:                                    ; rows AL .. AH-1: DL into each list,
    cmp al,ah                           ;   in OAM order
    jae .x
    push bx
    push cx
    mov bl,ah
    sub bl,al
    push bx
    mov ah,41
    mul ah
    mov bx,ax
    add bx,PPU_LSPR
    pop ax
.il:
    mov cl,[bx]
    xor ch,ch
    lea si,[bx+1]
.if:
    jcxz .ia
    cmp [si],dl
    ja .ia
    inc si
    dec cx
    jmp short .if
.ia:
    jcxz .iz                            ; its place; the CX after it one up
    mov di,si
    add di,cx
.is:
    mov ah,[di-1]
    mov [di],ah
    dec di
    loop .is
.iz:
    mov [si],dl
    inc byte [bx]
    add bx,41
    dec al
    jnz .il
    pop cx
    pop bx
    ret

; ppu_taddr: PPU_TADDR for LCDC bit 4 in AL: tile n's row 0 at 8000 + 16n,
; or 9000 + 16 x (n as signed). Tile n's word is at PPU_TADDRC + 2 x (n as
; signed) - cbw's index, so ppu_list looks a map byte up in three bytes
ppu_taddr:
    push ax
    push bx
    push cx
    push si
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
    lea si,[bx+256]
    and si,511
    mov [PPU_TADDR+si],ax
    add bx,2
    cmp bx,512
    jb .t
    pop si
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
    jae .none
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
    mov byte [PPU_RCH],1
    cmp bl,3                            ; a palette: rebuild its masks
    jb ppu_log
    cmp bl,6
    jae ppu_log
    call ppu_pal
    jmp ppu_log
.r:
    mov [PPU_LOGL],al                   ; (AL: the next entry's line)
    ret
.none:
    mov byte [PPU_LOGL],0FFh
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
    mov si,PPU_PALM+8                   ; and the sprites' (PPU_SANF)
    mov di,PPU_SANF
    mov cx,2
.s:
    mov al,[si+1]                       ; A: colour 1's
    mov [di],al
    mov ah,[si+2]                       ; B: colour 2's
    mov [di+1],ah
    xor al,ah
    xor al,[si+3]                       ; C: colour 3's against the two
    mov [di+2],al
    mov al,[si+5]                       ; ...and shade bit 1's
    mov [di+3],al
    mov ah,[si+6]
    mov [di+4],ah
    xor al,ah
    xor al,[si+7]
    mov [di+5],al
    add si,8
    add di,6
    loop .s
    pop di
    pop si
    ret

; ppu_line: compose line PPU_LY into PPU_OL/PPU_OH
%macro PPU_LINE 3
%1:
    push es
    push di
    push ds
    pop es
%if %2
    mov al,[PPU_PANM]
    cmp byte [PPU_RCH],0                ; (the line's kind is the last one's
    jne .pt                             ;   until a register is written, or
    mov ah,[PPU_LY]                     ;   the window begins)
    cmp ah,[PPU_REGS+6]
    jne .nal
.pt:
    call ppu_ptype
.nal:
%endif
    mov al,[PPU_REGS+0]
    test al,80h
    jnz .on
    xor ax,ax                           ; the LCD is off: the line is white
    mov word [PPU_OSRC],PPU_OL
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
    cmp byte [PPU_RCH],0                ; (no register written since the
    je .tm                              ;   last background's setup: the tile
    mov ah,al                           ;   mode it saw)
    and ah,10h
    cmp ah,[PPU_TMODE]
    je .tm
    call ppu_taddr
.tm:
    test al,20h                         ; the window over the whole line
    jz .bgf                             ;   (WX <= 7, LY >= WY): no
    mov ah,[PPU_LY]                     ;   background under it to compose
    cmp ah,[PPU_REGS+6]
    jb .bgf
    cmp byte [PPU_REGS+7],7
    jbe .win
.bgf:
    ; the background: 21 tile rows from the map, shifted SCX AND 7 left -
    ; the last line's 21, and its row + 1, when this is the line after it,
    ; no register was written since and the row is in the same tile
    mov dl,[PPU_LY]
    cmp dl,[PPU_BNEXT]
    jne .bgs
    cmp byte [PPU_RCH],0
    jne .bgs
    mov dl,[PPU_BROW]
    inc dx
    cmp dl,8
    jae .bgs0
    mov [PPU_BROW],dl
    inc byte [PPU_BNEXT]
    jmp short .bgl
.bgs0:
    mov dl,[PPU_LY]
.bgs:
    mov byte [PPU_RCH],0
    mov [PPU_BNEXT],dl
    inc byte [PPU_BNEXT]
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
    mov [PPU_BROW],dl
    mov bl,[PPU_REGS+2]                 ; SCX: the first tile column (less
%if %2
    sub bl,[PPU_SPAN]                   ;   the pan, aligned to it)
%endif
    shr bl,1
    shr bl,1
    shr bl,1
    xor bh,bh
    call ppu_blist                      ; the 21 tile addresses the line reads
.bgl:
    mov si,PPU_BLIST
    mov cl,[PPU_REGS+2]
%if %2
    sub cl,[PPU_SPAN]
%endif
    and cl,7
    cmp byte [PPU_BLIST+42],1           ; one tile all along: its row, turned
    je .uni                             ;   by the fine scroll, 20 times (44%
    or cl,cl                            ;   of Super Mario Land's lines under
    jz .b0                              ;   its status bar are a sky)
    call ppu_fshift
    jmp short .win
.uni:
    mov bx,[si]
    mov al,dl
    xor ah,ah
    shl ax,1
    add bx,ax
    mov ax,[bx]                         ; AL, AH = the tile row's two planes
    rol al,cl
    rol ah,cl
    mov bx,ax
    mov al,bl
    mov ah,bl
    mov di,PPU_BL
    mov cx,10 + %2
    rep stosw
    mov al,bh
    mov ah,bh
    mov di,PPU_BH
    mov cx,10 + %2
    rep stosw
    jmp short .win
.b0:
    call ppu_fcopyb
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
    xor bx,bx                           ; from the window's own column 0
    mov bp,PPU_WLIST
    mov di,PPU_WKEY
    call ppu_list
    mov si,PPU_WLIST
    call ppu_fcopyw
    call ppu_wplace
.pal:
    ; the background's shades through BGP: none when BGP is E4h, the
    ; identity - the line is left where it was composed, and its sprites
    ; drawn over it there - else its ANF a word, sixteen pixels, at a time
    cmp byte [PPU_REGS+3],0E4h
    jne .anf
    mov word [PPU_OSRC],PPU_BL
    test byte [PPU_REGS+0],02h
    jz .done
    mov al,[PPU_LY]
    mov ah,41
    mul ah
    mov bx,ax
    cmp byte [PPU_LSPR+bx],0            ; (the sprites, if any, drawn over
    je .done                            ;   it: ppu_spriteb)
    call %3
    jmp short .done
.anf:
    mov word [PPU_OSRC],PPU_OL
    mov bp,PPU_ANF
    mov di,PPU_OL
    call ppu_anf
    mov bp,PPU_ANF+8
    mov di,PPU_OH
    call ppu_anf
.spr:
    test byte [PPU_REGS+0],02h
    jz .done
    call %3
.done:
%if %2
    cmp byte [PPU_PSH],0
    jne .psh
.dn:
%endif
    pop di
    pop es
    ret
%if %2
.psh:
    call ppu_panr                       ; (composed as ever: the pan's way)
    jmp short .dn
%endif

%endmacro
; ppu_line as ever, and ppu_linep PAN-ALIGNED (rb_panon): the same code
; with the line's kind, its offset and its shift - none of it in the first
PPU_LINE ppu_line, 0, ppu_sprites
%ifndef RB_NOPAN                        ; (a host with no use for it: the bare
PPU_LINE ppu_linep, 1, ppu_spritesp     ;   harness's other modes, for room)

; ppu_ptype: PAN-ALIGNED, line PPU_LY's kind, AL = the frame's pan - a
; background alone with SCX - pan a whole byte is composed at that offset
; (PPU_SPAN = the pan: copied, not shifted); anything else as ever, and
; shifted right by the pan after (PPU_PSH). A change of kind is a register
; written, for ppu_line's tile-row path. DS = view
ppu_ptype:
    xor bx,bx                           ; BL = PPU_SPAN, BH = PPU_PSH
    mov ah,[PPU_REGS+0]
    test ah,80h
    jz .sh
    test ah,01h
    jz .sh
    test ah,20h                         ; the window on the line: as ever
    jz .nw
    mov dl,[PPU_LY]
    cmp dl,[PPU_REGS+6]
    jb .nw
    cmp byte [PPU_REGS+7],166
    jbe .sh
.nw:
    mov dl,[PPU_REGS+2]
    sub dl,al
    test dl,7
    jnz .sh
    mov bl,al
    jmp short .s
.sh:
    or al,al                            ; (pan 0: as ever is aligned)
    jz .s
    mov dl,[PPU_LY]                     ; (THE STRIP: shown unpanned)
    cmp dl,[cs:rb_tss]
    jae .s
    inc bh
.s:
    mov [PPU_SPAN],bx
    cmp bl,[PPU_SPANL]
    je .r
    mov [PPU_SPANL],bl
    mov byte [PPU_RCH],1
.r:
    ret

; ppu_panr: the line's two planes at [PPU_OSRC], composed as ever, shifted
; right by the frame's pan into 21 bytes (pixel 0 lands at the pan, where
; the card starts showing). Bit 0 of byte 20 takes byte 20's own junk, a
; pixel past the screen's last
ppu_panr:
    mov si,[PPU_OSRC]
    mov cl,[PPU_PANM]
    call .p
    add si,20h
.p:
%assign ppu_k 20
%rep 20
    mov ax,[si+ppu_k-1]
    xchg al,ah
    shr ax,cl
    mov [si+ppu_k],al
%assign ppu_k ppu_k-1
%endrep
    shr byte [si],cl
    ret

; ppu_pan: AL = the frame's pan - its last SCX (the snapshot's, then the
; raster log's writes on the screen's lines) AND 7. DS = view
ppu_pan:
    mov al,[PPU_REGS+2]
    xor ch,ch
    mov cl,[PPU_LOGN]
    jcxz .r
    mov si,RB_RLOG
.l:
    cmp byte [si+1],43h
    jne .n
    cmp byte [si],144
    jae .n
    mov al,[si+2]
.n:
    add si,4
    loop .l
.r:
    and al,7
    ret

; =============================================================================
; THE CANVAS (REALBOY-SPEC 15.5): with rb_torus the host keeps the Game Boy's
; whole 256x256 background in VRAM - a 256-byte row stride, so the 64KB wrap
; is the background's own, and each page a 64-byte slot of every row, 32
; tiles and then columns 0-19 again - and shows it by the start address and
; the pel panning. rb_renderd composes only the OVERLAY lines, the ones the
; canvas cannot show (sprites, the window, a scroll, palette or tile mode of
; their own), into its 42-byte buffer as ever; rb_tpage puts a page right.
; Its state is RB_TSIZE bytes at [rb_tseg]:0, which rb_tinit starts.
;
; NOTHING HERE VISITS A LINE IT HAS NO BUSINESS WITH: the frame keeps the
; list of its overlay lines and each page the list it holds, and the cells
; are looked for only in the columns in view. The first build walked all
; 144 lines three times a frame and every column of a row with any cell
; owed, and on the 286 that bookkeeping cost more than the composing it
; saved (REALBOY-PLAN, the scroll round). AND NOTHING WRITES A BYTE THE
; CANVAS ALREADY SHOWS: a line that is an overlay only for its sprites is
; the background everywhere else, so only the bytes its sprites span are
; written (ppu_tspan), and restored.
; =============================================================================
RB_TKEY         equ 0                   ; 3 x 144 words: per page and line, the
                                        ;   canvas row:column of the overlay
                                        ;   written there, FFFFh none...
RB_TSPAN        equ 864                 ; 3 x 144 words: ...and which of its 21
                                        ;   bytes, the first and the last
RB_TDIRTY       equ 1728                ; 3 x 128: a bit a cell (row x 32 +
                                        ;   column), owed to the page
RB_TPL          equ 2112                ; 3 x 145: the lines the page holds an
                                        ;   overlay on, a count and the lines
RB_TPBGP        equ 2547                ; 3: the BGP each page's cells are in...
RB_TPLCD        equ 2550                ; 3: ...and the LCDC (bits 3-4)
RB_TSIZE        equ 2553
RB_TMID         equ 72                  ; the line the canvas is the state of:
                                        ;   a status bar is at a screen's top or
                                        ;   its bottom, the playfield between

; rb_tinit: THE CANVAS from nothing - every cell owed, no overlay held, no
; page's palette known, every line stale. [rb_tseg] = the state's segment.
; Kept: all
rb_tinit:
    push ax
    push cx
    push di
    push es
    cld
    mov es,[cs:rb_tseg]
    xor di,di
    mov cx,RB_TPL / 2                   ; keys FFFFh, every cell owed
    mov ax,0FFFFh
    rep stosw
    mov di,RB_TPL                       ; no line held
    xor al,al
    stosb
    mov di,RB_TPL + 145
    stosb
    mov di,RB_TPL + 290
    stosb
    mov di,RB_TPBGP                     ; no palette, map or tiles known
    mov cx,6
    mov al,0FFh
    rep stosb
    push cs
    pop es
    mov di,rb_tcls                      ; no line an overlay, every one stale
    mov cx,144
    xor al,al
    rep stosb
    mov di,rb_tstl
    mov cx,144
    mov al,1
    rep stosb
    mov word [cs:rb_tovn],0
    mov byte [cs:rb_tpan],0FFh
    mov ax,9090h                        ; no strip, none held, none laid out
    mov [cs:rb_tss],al                  ;   (144 = 90h)
    mov [cs:rb_tsc],al
    mov [cs:rb_tslay],al
    mov byte [cs:rb_tsn],0
    mov byte [cs:rb_tsall],0
    pop es
    pop di
    pop cx
    pop ax
    ret

; ppu_tframe: the frame's CANVAS - SCX, SCY, BGP and LCDC as line RB_TMID
; sees them (the snapshot, and the raster log's writes on the lines up to
; it) - into rb_tfr; every line stale when the pan moved, and with the
; host's whole (RB_DFULL = 1: a cleared screen, a state loaded) every cell
; owed too. AL = the pan. DS = view, ES = damage
ppu_tframe:
    push bx
    push cx
    push dx
    push si
    push di
    mov bl,[PPU_REGS+2]                 ; BL SCX, BH SCY, DL BGP, DH LCDC
    mov bh,[PPU_REGS+1]
    mov dl,[PPU_REGS+3]
    mov dh,[PPU_REGS+0]
    xor ch,ch
    mov cl,[PPU_LOGN]
    jcxz .k
    mov si,RB_RLOG
.l:
    cmp byte [si],RB_TMID
    ja .n
    mov al,[si+1]
    mov ah,[si+2]
    cmp al,43h
    jne .y
    mov bl,ah
.y:
    cmp al,42h
    jne .b
    mov bh,ah
.b:
    cmp al,47h
    jne .c
    mov dl,ah
.c:
    cmp al,40h
    jne .n
    mov dh,ah
.n:
    add si,4
    loop .l
.k:
    mov [cs:rb_tfr],bh                  ; SCY, SCX: [PPU_REGS+1]'s order
    mov [cs:rb_tfr+1],bl
    mov [cs:rb_tfr+2],dx                ; BGP, LCDC
    mov al,[es:RB_DFULL]
    push es
    cmp al,1
    jne .p
    mov es,[cs:rb_tseg]                 ; the host's whole: every cell owed
    mov di,RB_TDIRTY
    mov cx,384 / 2
    mov ax,0FFFFh
    rep stosw
    jmp short .st
.p:
    mov al,bl
    and al,7
    cmp al,[cs:rb_tpan]
    je .r
.st:
    mov al,bl
    and al,7
    mov [cs:rb_tpan],al
    push cs                             ; every line composed again at it
    pop es
    mov di,rb_tstl
    mov cx,144 / 2
    mov ax,0101h
    rep stosw
.r:
    pop es
    call ppu_tstrip
    mov al,bl
    and al,7
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; ppu_tstrip: THE STRIP (REALBOY-SPEC 15.5.1) - the window from WY to the
; screen's bottom, full width and unbroken, is shown under the line compare
; from the split's region, which the start address and the panning never
; move: composed once at pan 0 and written when it changes, where on the
; canvas it was an overlay every scrolled frame composed, put back and
; written again. The frame's candidate is WY when the frame's end has the LCD,
; the background and the window on, WX at most 7 and WY 8-143, and no write
; to LCDC, WY or WX on a line from WY - 1 on (the raster log); else 144. A
; strip goes OFF at once when the candidate leaves it, and ON only when one
; has held RB_TSWAIT frames - every strip line then composed and written.
; DS = view. Kept: all
RB_TSWAIT       equ 4
ppu_tstrip:
    push ax
    push bx
    push cx
    push dx
    push si
    mov bl,[PPU_REGS+0]                 ; BL LCDC, BH WY, DL WX: the frame's
    mov bh,[PPU_REGS+6]                 ;   start, then its writes
    mov dl,[PPU_REGS+7]
    xor dh,dh                           ; DH = the last such write's line + 1
    xor ch,ch
    mov cl,[PPU_LOGN]
    jcxz .k
    mov si,RB_RLOG
.l:
    mov al,[si]
    cmp al,144
    jae .n
    mov ah,[si+2]
    cmp byte [si+1],40h
    jne .wy
    mov bl,ah
    jmp short .w
.wy:
    cmp byte [si+1],4Ah
    jne .wx
    mov bh,ah
    jmp short .w
.wx:
    cmp byte [si+1],4Bh
    jne .n
    mov dl,ah
.w:
    inc al
    cmp al,dh
    jb .n
    mov dh,al
.n:
    add si,4
    loop .l
.k:
    mov al,144
    and bl,0A1h                         ; the LCD, the window, the background
    cmp bl,0A1h
    jne .c
    cmp dl,7
    ja .c
    cmp bh,8
    jb .c
    cmp bh,143
    ja .c
    cmp dh,bh                           ; (written at WY - 1 or later: no)
    jae .c
    mov al,bh
.c:
    mov ah,[cs:rb_tss]
    cmp ah,144
    je .off
    cmp al,ah                           ; in force: held, or OFF at once
    je .x
    mov byte [cs:rb_tss],144
    mov byte [cs:rb_tsn],0
    mov cl,ah                           ; its lines composed again at the
    xor ch,ch                           ;   pan, the canvas's again
    mov bl,ah
    xor bh,bh
    neg cx
    add cx,144
.st:
    mov byte [cs:rb_tstl+bx],1
    inc bx
    loop .st
    jmp short .x
.off:
    cmp al,144
    je .z
    cmp al,[cs:rb_tsc]
    jne .z
    inc byte [cs:rb_tsn]
    cmp byte [cs:rb_tsn],RB_TSWAIT
    jb .x
    mov [cs:rb_tss],al                  ; ON: every line of it owed
    mov byte [cs:rb_tsall],1
    jmp short .x
.z:
    mov byte [cs:rb_tsn],1
.x:
    mov [cs:rb_tsc],al
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ppu_sldirty: ppu_ldirty for a strip line - its scroll is not its picture
; (the window covers the whole line), so the line's record's SCY and SCX
; stand in for the frame's while it is judged. DS = view, ES = damage.
; Kept: all but the flags
ppu_sldirty:
    push ax
    push di
    mov al,[PPU_LY]
    mov ah,10
    mul ah
    mov di,ax
    push word [PPU_REGS+1]
    mov ax,[es:di+RB_DLREG+1]
    mov [PPU_REGS+1],ax
    call ppu_ldirty
    pop word [PPU_REGS+1]               ; (pop keeps the flags)
    pop di
    pop ax
    ret

; ppu_tcls: line BX (PPU_LY) on the canvas - CF = 0 CLEAN, which the canvas
; shows as it is: not composed, its buffer line left stale; CF = 1 an
; OVERLAY, onto the frame's list with the bytes to write, AL = 1 when its
; buffer line is stale. The registers' part of the verdict is judged again
; only when the raster log moved (PPU_LOGI); per line it is the window and
; the sprites, whose list [rb_tlsp] walks (the loop's). DS = view. Kept:
; all but AX and SI
ppu_tcls:
    mov al,[PPU_LOGI]
    cmp al,[cs:rb_tli]
    je .rk
    mov [cs:rb_tli],al
    call .regs
.rk:
    cmp byte [cs:rb_trk],0              ; the LCD, the background, the map,
    je .ov                              ;   tiles, scroll and palette
    test byte [cs:rb_trk],2             ; the window on from a line on
    jz .nw
    mov al,[PPU_LY]
    cmp al,[PPU_REGS+6]
    jae .ov
.nw:
    test byte [cs:rb_trk],4             ; sprites on: none that may cover it
    jz .cl
    mov si,[cs:rb_tlsp]
    cmp byte [si],0
    je .cl
    sub si,PPU_LSPR
    call ppu_tspan                      ; only its sprites': the bytes they
    jmp short .ovs                      ;   span
.cl:
    mov byte [cs:rb_tcls+bx],0
    mov byte [cs:rb_tstl+bx],1
    clc
    ret
.ov:
    mov ax,1400h                        ; anything else: all 21 bytes
.ovs:
    mov [cs:rb_tsp0+bx],al
    mov [cs:rb_tsp1+bx],ah
    mov byte [cs:rb_tcls+bx],1
    mov si,[cs:rb_tovn]
    mov [cs:rb_tovl+si],bl
    inc word [cs:rb_tovn]
    xor al,al
    xchg al,[cs:rb_tstl+bx]
    stc
    ret
.regs:                                  ; rb_trk: 0 an overlay whatever the
    mov byte [cs:rb_trk],0              ;   line, else 1, +2 the window from
    mov al,[PPU_REGS+0]                 ;   WY on, +4 sprites on
    mov ah,al
    xor ah,[cs:rb_tfr+3]                ; the frame's map and tiles
    test ah,18h
    jnz .rr
    mov ah,al
    and ah,81h                          ; the LCD and the background on
    cmp ah,81h
    jne .rr
    mov si,[PPU_REGS+1]                 ; the frame's scroll
    cmp si,[cs:rb_tfr]
    jne .rr
    mov ah,[PPU_REGS+3]                 ; ...and palette
    cmp ah,[cs:rb_tfr+2]
    jne .rr
    mov ah,1
    test al,20h
    jz .rw
    cmp byte [PPU_REGS+7],166
    ja .rw
    or ah,2
.rw:
    test al,02h
    jz .rs
    or ah,4
.rs:
    mov [cs:rb_trk],ah
.rr:
    ret

; ppu_tspan: the bytes of a pan-aligned line its sprites may cover - the
; ones PPU_LSPR lists at SI - AL the first, AH the last (0-20). A sprite at
; OAM X is at the buffer's pixel X - 8 + the pan. DS = view. Kept: all but
; AX and SI
ppu_tspan:
    push bx
    push cx
    push dx
    mov cl,[PPU_LSPR+si]
    xor ch,ch
    add si,PPU_LSPR + 1
    mov dx,00FFh                        ; DH the largest X, DL the smallest
.s:
    mov bl,[si]
    xor bh,bh
    mov al,[0FE01h+bx]
    cmp al,dl
    jae .s1
    mov dl,al
.s1:
    cmp al,dh
    jbe .s2
    mov dh,al
.s2:
    inc si
    loop .s
    mov bl,[PPU_PANM]
    xor bh,bh
    mov cl,3
    mov al,dl                           ; the first: (X - 8 + pan) / 8
    xor ah,ah
    add ax,bx
    sub ax,8
    jns .f
    xor ax,ax
.f:
    shr ax,cl
    cmp ax,20
    jbe .f1
    mov al,20
.f1:
    mov ch,al
    mov al,dh                           ; the last: (X - 1 + pan) / 8
    xor ah,ah
    add ax,bx
    dec ax
    jns .l
    xor ax,ax
.l:
    shr ax,cl
    cmp ax,20
    jbe .l1
    mov al,20
.l1:
    mov ah,al
    mov al,ch
    cmp ah,al                           ; (all off to the right: one byte)
    jae .r
    mov ah,al
.r:
    pop dx
    pop cx
    pop bx
    ret

; ppu_tmark: the cells this call's damage scan found changed, owed to every
; page - a byte of the frame's map, or a tile it shows (the map searched
; for its number; more than 16 tiles owe every cell). DS = view, ES = damage
ppu_tmark:
    mov dl,[cs:rb_tfr+3]                ; DL = the frame's LCDC
    cmp byte [es:RB_DMCH],0
    je .tiles
    mov bx,RB_DMD                       ; the frame's map's change bytes
    test dl,08h
    jz .m0
    add bx,1024
.m0:
    mov di,bx
    mov cx,1024
.m:
    xor al,al
    repe scasb
    je .tiles
    mov ax,di
    sub ax,bx
    dec ax                              ; AX = the cell
    call ppu_tbit
    jcxz .tiles
    jmp short .m
.tiles:
    cmp byte [es:RB_DTCH],0
    je .r
    mov byte [cs:rb_tln],0
    mov di,RB_DTD
    mov cx,384
.t:
    xor al,al
    repe scasb
    je .scan
    mov ax,di
    sub ax,RB_DTD + 1                   ; AX = the tile, 0-383 from 8000h
    test dl,10h                         ; as the frame's tile mode numbers it:
    jz .s                               ;   8000h on, 0-255 as they are
    cmp ax,256
    jae .tn
    jmp short .add
.s:
    cmp ax,128                          ;   8800h on, 128-255 as they are and
    jb .tn                              ;   256-383 as 0-127
    cmp ax,256
    jb .add
    sub ax,256
.add:
    mov bl,[cs:rb_tln]
    cmp bl,16
    jae .every
    xor bh,bh
    mov [cs:rb_tlst+bx],al
    inc byte [cs:rb_tln]
.tn:
    jcxz .scan
    jmp short .t
.every:
    push es                             ; (many: every cell)
    mov es,[cs:rb_tseg]
    mov di,RB_TDIRTY
    mov cx,384 / 2
    mov ax,0FFFFh
    rep stosw
    pop es
    ret
.scan:
    mov cl,[cs:rb_tln]
    xor ch,ch
    jcxz .r
    push es
    push ds
    pop es                              ; ES = the view, for its map
    mov bx,9800h
    test dl,08h
    jz .sb
    mov bx,9C00h
.sb:
    xor si,si
.sn:
    push cx
    mov al,[cs:rb_tlst+si]
    mov di,bx
    mov cx,1024
.f:
    repne scasb
    jne .fn
    push ax
    mov ax,di
    sub ax,bx
    dec ax
    call ppu_tbit
    pop ax
    jcxz .fn
    jmp short .f
.fn:
    pop cx
    inc si
    loop .sn
    pop es
.r:
    ret

; ppu_tbit: cell AX owed to every page. Kept: all but AL
ppu_tbit:
    push bx
    push cx
    push ds
    mov ds,[cs:rb_tseg]
    mov bx,ax
    mov cl,3
    shr bx,cl
    mov cl,al
    and cl,7
    mov al,1
    shl al,cl
    or [RB_TDIRTY+bx],al
    or [RB_TDIRTY+128+bx],al
    or [RB_TDIRTY+256+bx],al
    pop ds
    pop cx
    pop bx
    ret

; rb_tpage: the frame rb_renderd just composed (rb_torus) onto one of the
; host's three CANVAS pages (REALBOY-SPEC 15.5) - the overlays it holds that
; this frame does not keep restored, the cells in view it owes drawn, the
; overlays it does not hold written. AL = the page (0-2), ES = the card.
; Out BX = the start address that shows it (the pan is rb_panv). Kept: all
; but BX
rb_tpage:
    push ax
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    cld
    mov [cs:rb_tcard],es
    xor ah,ah
    mov si,ax                           ; SI = the page
    inc ax
    mov cl,6
    shl ax,cl
    mov [cs:rb_tslot],al                ; its slot: 64, 128, 192
    mov ax,si
    mov cx,288
    mul cx
    mov [cs:rb_tkey],ax                 ; its keys (RB_TKEY is 0)
    mov ax,si
    mov cl,7
    shl ax,cl
    add ax,RB_TDIRTY
    mov [cs:rb_tdirty],ax               ; its owed cells
    mov ax,si
    mov cl,145
    mul cl
    add ax,RB_TPL
    mov [cs:rb_tpl],ax                  ; the lines it holds
    mov ax,si
    mov cl,144
    mul cl
    add ax,RB_PGMSK
    mov [cs:rb_towed],ax                ; its owed lines, in the buffer's
    push ds
    mov ds,[cs:rb_dmgseg]
    mov ax,[RB_DOUT+2]
    pop ds
    mov [cs:rb_tpseg],ax
    mov al,[cs:rb_tfr+1]                ; the first column shown
    mov cl,3
    shr al,cl
    mov [cs:rb_tc0],al
    mov bx,9800h                        ; the frame's map
    test byte [cs:rb_tfr+3],08h
    jz .mp
    mov bx,9C00h
.mp:
    mov [cs:rb_tmap],bx
    mov ds,[cs:rb_tseg]
    mov ax,[cs:rb_tfr+2]                ; cells in another palette, map or
    cmp al,[RB_TPBGP+si]                ;   tile mode: every one owed
    jne .all
    mov ah,[RB_TPLCD+si]
    xor ah,[cs:rb_tfr+3]
    test ah,18h
    jz .anf
.all:
    mov [RB_TPBGP+si],al
    mov ah,[cs:rb_tfr+3]
    mov [RB_TPLCD+si],ah
    push es
    push ds
    pop es
    mov di,[cs:rb_tdirty]
    mov cx,128 / 2
    mov ax,0FFFFh
    rep stosw
    pop es
.anf:
    mov al,[cs:rb_tfr+2]
    call ppu_tanf
    mov ds,[cs:rb_viewseg]
    mov al,[cs:rb_tfr+3]                ; the tile addresses of its mode
    and al,10h
    cmp al,[PPU_TMODE]
    je .tm
    mov al,[cs:rb_tfr+3]
    call ppu_taddr
.tm:
    mov es,[cs:rb_tseg]
    ; 1. the overlays it holds that this frame does not keep where they
    ;    are, back to the background - unless one of this frame's at the
    ;    same row and column spans the same bytes, which is written over them
    mov si,[cs:rb_tpl]
    mov cl,[es:si]
    xor ch,ch
    jcxz .r1e
    inc si
.r1:
    mov bl,[es:si]
    xor bh,bh
    mov bp,bx                           ; BP = the line
    shl bx,1
    add bx,[cs:rb_tkey]
    mov dx,[es:bx]                      ; DX = its overlay's row:column,
    cmp dx,0FFFFh
    je .r1n
    mov ax,[es:bx+RB_TSPAN]             ;   rb_tb0 its bytes
    mov [cs:rb_tb0],ax
    cmp byte [cs:rb_tcls+bp],0
    je .r1r
    mov ax,bp                           ; this frame's place
    add al,[cs:rb_tfr]
    mov ah,al
    mov al,[cs:rb_tc0]
    cmp ax,dx
    je .r1n                             ; the same: phase 3's
.r1r:
    call .r1p                           ; (only what this frame's on its row
.r1c:                                   ;   does not write over)
    mov word [es:bx],0FFFFh
.r1n:
    inc si
    loop .r1
.r1e:
    call rb_tflush
    ; 2. the cells in view it owes: 19 tile rows, the 21 columns from c0
    mov cl,[cs:rb_tc0]                  ; the window's 32 bits, column k at
    xor ax,ax                           ;   bit k: 21 set from c0, round
    mov dx,001Fh
    mov ax,0FFFFh
    xor ch,ch
    jcxz .wd
.wr:
    shl ax,1
    rcl dx,1
    jnc .wr0
    or al,1
.wr0:
    loop .wr
.wd:
    mov [cs:rb_twm],ax
    mov [cs:rb_twm+2],dx
    mov al,[cs:rb_tfr]
    mov cl,3
    shr al,cl
    mov [cs:rb_tty],al
    mov byte [cs:rb_tny],19
.c2:
    mov bl,[cs:rb_tty]
    and bl,31
    xor bh,bh
    shl bx,1
    shl bx,1
    add bx,[cs:rb_tdirty]               ; BX = the tile row's 4 bytes
    mov ax,[es:bx]
    and ax,[cs:rb_twm]
    mov dx,[es:bx+2]
    and dx,[cs:rb_twm+2]
    mov cx,ax
    or cx,dx
    jz .c2n
    xor dh,dh                           ; DH = the byte, 0-3
.c3:
    mov dl,dh
    xor ah,ah
    push bx
    add bl,dh                           ; (4-aligned: no carry)
    mov al,[es:bx]
    pop bx
    push bx
    mov bl,dh
    xor bh,bh
    and al,[cs:rb_twm+bx]
    pop bx
    or al,al
    jz .c3n
    mov cl,dh                           ; its columns 8 x byte on
    shl cl,1
    shl cl,1
    shl cl,1
.c4:
    shr al,1
    jnc .c4n
    push ax
    push bx
    push dx
    mov dl,cl
    mov al,dh                           ; the bit, cleared
    xor ah,ah
    add bx,ax
    mov al,cl
    and al,7
    xchg cl,al
    mov ah,1
    shl ah,cl
    xchg cl,al
    not ah
    and [es:bx],ah
    call rb_tcell                       ; DL = the column
    pop dx
    pop bx
    pop ax
.c4n:
    inc cl
    or al,al
    jnz .c4
.c3n:
    inc dh
    cmp dh,4
    jb .c3
.c2n:
    inc byte [cs:rb_tty]
    dec byte [cs:rb_tny]
    jnz .c2
    ; 3. the overlays it does not hold: a new place, or the line owed since
    ;    - decided first (rb_twl: from, to and how many), then written a
    ;    plane at a time, under one map mask each
    mov ds,[cs:rb_tpseg]
    mov si,rb_tovl
    mov di,rb_twl
    mov cx,[cs:rb_tovn]
    jcxz .o3
.o:
    call .ol
    inc si
    loop .o
.o3:
    mov bp,di                           ; BP = the list's end
    mov es,[cs:rb_tcard]
    mov dx,3C4h
    mov ax,0102h
    out dx,ax
    xor ax,ax
    call .wrp
    mov ax,0202h
    out dx,ax
    mov ax,21
    call .wrp
    ; 4. THE STRIP's changed lines into the split's region (REALBOY-SPEC
    ;    15.5.1), one region for every page: line L at row L - S, bytes 0-20
    ;    of slot 0 - laid out by the host first when the strip changed
    mov al,[cs:rb_tss]
    cmp al,[cs:rb_tslay]
    je .s4
    mov [cs:rb_tslay],al
    cmp word [cs:rb_shook],0
    je .s4h
    push ds
    push cs
    pop ds
    call [cs:rb_shook]
    pop ds
.s4h:
    mov byte [cs:rb_tsall],1
.s4:
    cmp al,144
    jae .s4e
    mov di,rb_twl
    mov bl,al
    xor bh,bh                           ; BX = the line
    xor cx,cx                           ; CH = the row
    push es
    mov es,[cs:rb_dmgseg]
.s4l:
    cmp byte [cs:rb_tsall],0
    jne .s4w
    cmp byte [es:RB_DCHG+bx],0
    je .s4n
.s4w:
    mov ax,bx                           ; from: the buffer's line
    mov dl,42
    mul dl
    mov [cs:di],ax
    mov [cs:di+2],cx                    ; to: its row, slot 0, byte 0
    mov byte [cs:di+4],21
    add di,5
.s4n:
    inc ch
    inc bx
    cmp bx,144
    jb .s4l
    pop es
    mov byte [cs:rb_tsall],0
    mov bp,di
    cmp bp,rb_twl
    je .s4e
    mov es,[cs:rb_tcard]
    mov dx,3C4h
    mov ax,0102h
    out dx,ax
    xor ax,ax
    call .wrp
    mov ax,0202h
    out dx,ax
    mov ax,21
    call .wrp
.s4e:
    mov es,[cs:rb_tseg]
.oe:
    mov di,[cs:rb_tpl]                  ; it holds this frame's overlays now
    mov cx,[cs:rb_tovn]
    mov al,cl
    stosb
    jcxz .oc
    push ds
    push cs
    pop ds
    mov si,rb_tovl
    rep movsb
    pop ds
.oc:
    mov bh,[cs:rb_tfr]                  ; where it is shown from
    mov bl,[cs:rb_tslot]
    add bl,[cs:rb_tc0]
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret

.r1p:                                   ; phase 1's restore of DH:DL bytes
    push ax                             ;   rb_tb0-rb_tb1: by place in the
    push bx                             ;   slot, [a, b] - less what this
    push cx                             ;   frame's overlay on the row writes,
    push dx                             ;   [c, d], which leaves at most two
    mov al,dl                           ;   pieces
    add al,[cs:rb_tb0]                  ; AL = a
    mov ah,dl
    add ah,[cs:rb_tb1]                  ; AH = b
    mov bl,dh
    sub bl,[cs:rb_tfr]
    cmp bl,144
    jae .pw                             ; no line of this frame's there
    xor bh,bh
    cmp byte [cs:rb_tcls+bx],0
    je .pw
    mov cl,[cs:rb_tc0]
    mov ch,cl
    add cl,[cs:rb_tsp0+bx]              ; CL = c
    add ch,[cs:rb_tsp1+bx]              ; CH = d
    cmp cl,al                           ; the piece left of it: [a, c - 1]
    jbe .pr
    mov bl,cl
    dec bl
    cmp bl,ah
    jbe .pl
    mov bl,ah
.pl:
    push ax
    mov ah,bl
    call .pq
    pop ax
.pr:
    cmp ch,ah                           ; ...and right of it: [d + 1, b]
    jae .px
    mov bl,ch
    inc bl
    cmp bl,al
    jae .pr1
    mov bl,al
.pr1:
    mov al,bl
    call .pq
    jmp short .px
.pw:
    call .pq                            ; the whole of it
.px:
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.pq:                                    ; [AL, AH] of row DH, by place
    mov dl,0
    mov [cs:rb_tb0],ax
    jmp rb_trow
.ol:                                    ; phase 3's line [cs:SI]: onto rb_twl
    mov bl,[cs:si]
    xor bh,bh
    mov bp,bx
    test bl,15                          ; (now and then, the host's flip
    jnz .o1                             ;   looked at)
    call ppu_lhook
.o1:
    mov ax,bp
    add al,[cs:rb_tfr]
    mov ah,al
    mov al,[cs:rb_tc0]                  ; AX = its row:column,
    mov dl,[cs:rb_tsp0+bp]              ;   DX its bytes
    mov dh,[cs:rb_tsp1+bp]
    shl bx,1
    add bx,[cs:rb_tkey]
    mov [cs:rb_tb0],dx
    cmp ax,[es:bx]
    jne .ow                             ; a new place: its bytes
    push cx                             ; the same place: the old bytes and
    mov cx,[es:bx+RB_TSPAN]             ;   the new (the line's own outside
    cmp cl,dl                           ;   its sprites is the background)...
    jae .u1
    mov [cs:rb_tb0],cl
.u1:
    cmp ch,dh
    jbe .u2
    mov [cs:rb_tb1],ch
.u2:
    cmp cx,dx
    pop cx
    jne .ow
    push bx                             ; ...when they moved or the line
    mov bx,[cs:rb_towed]                ;   is owed
    add bx,bp
    cmp byte [bx],0
    pop bx
    je .on
.ow:
    mov [es:bx],ax
    mov [es:bx+RB_TSPAN],dx
    mov bx,[cs:rb_towed]                ; no longer owed
    add bx,bp
    mov byte [bx],0
    add al,[cs:rb_tslot]                ; to: its row, slot, column, byte
    add al,[cs:rb_tb0]
    mov [cs:di+2],ax
    mov ax,bp                           ; from: the buffer's line, byte
    mov dl,42
    mul dl
    add al,[cs:rb_tb0]
    adc ah,0
    mov [cs:di],ax
    mov al,[cs:rb_tb1]                  ; how many
    sub al,[cs:rb_tb0]
    inc ax
    mov [cs:di+4],al
    add di,5
.on:
    ret
.wrp:                                   ; rb_twl's writes, AX into the line
    mov bx,rb_twl                       ;   (0 plane 0's bytes, 21 plane 1's):
.wl:                                    ;   DS = the buffer, ES = the card
    cmp bx,bp
    jae .we
    mov si,[cs:bx]
    add si,ax
    mov di,[cs:bx+2]
    mov cl,[cs:bx+4]
    xor ch,ch
    rep movsb
    add bx,5
    jmp short .wl
.we:
    ret

; rb_trow: canvas row DH, the overlay at column DL's bytes rb_tb0 to rb_tb1,
; back to the background on the page - QUEUED (rb_tq*), and written by
; rb_tflush a plane at a time, as phase 3's are. DS = view. Kept: all
rb_trow:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    cmp byte [cs:rb_tqn],RB_TQMAX       ; (a full queue written first)
    jb .q
    call rb_tflush
.q:
    mov bl,dh
    and bl,0F8h
    xor bh,bh
    shl bx,1
    shl bx,1
    add bx,[cs:rb_tmap]
    mov bp,bx                           ; BP = the map row
    mov al,dh
    and al,7
    shl al,1
    xor ah,ah
    mov si,ax                           ; SI = the tile row's offset
    mov al,[cs:rb_tqn]                  ; DI = its bytes in the queue
    mov ah,42
    mul ah
    add ax,rb_tqb
    mov di,ax
    mov bl,[cs:rb_tqn]
    xor bh,bh
    mov al,dl                           ; to: the row, slot, column, byte
    add al,[cs:rb_tslot]
    add al,[cs:rb_tb0]
    mov ah,dh
    shl bx,1
    mov [cs:rb_tqd+bx],ax
    shr bx,1
    mov cl,dl
    add cl,[cs:rb_tb0]                  ; CL = its first column
    mov ch,[cs:rb_tb1]
    sub ch,[cs:rb_tb0]
    inc ch                              ; CH = how many
    mov [cs:rb_tqc+bx],ch
    inc byte [cs:rb_tqn]
.b:
    mov bl,cl
    and bl,31
    xor bh,bh
    add bx,bp
    mov al,[bx]                         ; the cell's tile
    cbw
    shl ax,1
    mov bx,ax
    mov bx,[PPU_TADDRC+bx]
    mov ax,[bx+si]                      ; its row's two bit planes
    cmp byte [cs:rb_tid],0              ; (BGP the identity: as they are)
    jne .id
    call ppu_tshade
.id:
    mov [cs:di],al
    mov [cs:di+21],ah
    inc di
    inc cl
    dec ch
    jnz .b
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rb_tflush: rb_trow's queue onto the page, plane 0's bytes then plane 1's,
; under one map mask each, and empty. Kept: all
rb_tflush:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push ds
    push es
    cmp byte [cs:rb_tqn],0
    je .r
    mov es,[cs:rb_tcard]
    push cs
    pop ds
    mov dx,3C4h
    mov ax,0102h
    out dx,ax
    xor ax,ax
    call .p
    mov ax,0202h
    out dx,ax
    mov ax,21
    call .p
    mov byte [cs:rb_tqn],0
.r:
    pop es
    pop ds
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.p:                                     ; AX into each entry's bytes
    xor bx,bx
    lea si,[rb_tqb]
    add si,ax
.e:
    shl bx,1
    mov di,[rb_tqd+bx]
    shr bx,1
    mov cl,[rb_tqc+bx]
    xor ch,ch
    push si
    rep movsb
    pop si
    add si,42
    inc bx
    cmp bl,[rb_tqn]
    jb .e
    ret

; rb_tcell: the cell at tile row [rb_tty] AND 31, column DL AND 31 drawn on
; the page - both copies of a column 0-19 - and an overlay kept on its rows
; owed again (RB_PGMSK). DS = view, ES = the state. Kept: all
rb_tcell:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov al,[cs:rb_tty]
    and al,31
    and dl,31
    mov [cs:rb_ttx],dl
    xor bh,bh
    mov bl,al
    mov cl,5
    shl bx,cl
    mov cl,dl
    xor ch,ch
    add bx,cx
    add bx,[cs:rb_tmap]
    push ax
    mov al,[bx]                         ; the tile
    cbw
    shl ax,1
    mov bx,ax
    mov si,[PPU_TADDRC+bx]
    mov di,rb_tbuf
    mov cx,8
.r:
    lodsw
    cmp byte [cs:rb_tid],0
    jne .id
    call ppu_tshade
.id:
    mov [cs:di],al
    mov [cs:di+8],ah
    inc di
    loop .r
    pop ax                              ; AL = the tile row
    mov bh,al
    shl bh,1
    shl bh,1
    shl bh,1
    mov bl,[cs:rb_ttx]
    add bl,[cs:rb_tslot]                ; BX = its top byte on the page
    push ax
    push ds
    push es
    mov es,[cs:rb_tcard]
    push cs
    pop ds
    mov dx,3C4h
    mov ax,0102h
    out dx,ax
    mov si,rb_tbuf
    call .two
    mov ax,0202h
    out dx,ax
    mov si,rb_tbuf + 8
    call .two
    pop es
    pop ds
    pop ax
    shl al,1                            ; its rows: an overlay kept there is
    shl al,1                            ;   owed again - OWED, not dropped, so
    shl al,1                            ;   its old bytes and its new are
    mov cx,8                            ;   written (a dropped key wrote only
    push ds                             ;   the new, and left the old sprite)
    mov ds,[cs:rb_tpseg]
.k:
    mov bl,al
    sub bl,[cs:rb_tfr]
    cmp bl,144
    jae .kn
    xor bh,bh
    cmp byte [cs:rb_tcls+bx],0
    je .kn
    add bx,[cs:rb_towed]
    mov byte [bx],1
.kn:
    inc al
    loop .k
    pop ds
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.two:
    call .put                           ; the column, and for 0-19 its copy
    cmp byte [cs:rb_ttx],20
    jae .tw
    sub si,8
    add bx,32
    call .put
    sub bx,32
.tw:
    ret
.put:
    mov di,bx
    mov cx,8
.p:
    movsb
    add di,255
    loop .p
    ret

; ppu_tanf: rb_tanf from BGP = AL - per shade bit D A B C, a bit being D
; xor (bit 0 and A) xor (bit 1 and B) xor (both and C) - and rb_tid set when
; it is the identity (E4h), which ppu_tshade leaves alone. Kept: all
ppu_tanf:
    push ax
    push bx
    push cx
    push si
    push di
    mov byte [cs:rb_tid],1
    cmp al,0E4h
    je .r
    mov byte [cs:rb_tid],0
    mov bl,al
    xor di,di                           ; the shade's bit 0, then bit 1
.p:
    mov cx,4                            ; colour c's bit, as a mask
    mov bh,bl
    xor si,si
.c:
    mov al,bh
    and al,1
    neg al
    mov [cs:rb_tm+si],al
    shr bh,1
    shr bh,1
    inc si
    loop .c
    mov al,[cs:rb_tm]                   ; D
    mov [cs:rb_tanf+di],al
    mov ah,al
    xor ah,[cs:rb_tm+1]                 ; A
    mov [cs:rb_tanf+di+1],ah
    mov ah,al
    xor ah,[cs:rb_tm+2]                 ; B
    mov [cs:rb_tanf+di+2],ah
    xor al,[cs:rb_tm+1]                 ; C
    xor al,[cs:rb_tm+2]
    xor al,[cs:rb_tm+3]
    mov [cs:rb_tanf+di+3],al
    shr bl,1
    add di,4
    cmp di,8
    jb .p
.r:
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; ppu_tshade: AL, AH = a tile row's bit 0 and bit 1 bytes; out the shade's
; bit 0 and bit 1 bytes through rb_tanf. Kept: all but AX
ppu_tshade:
    cmp byte [cs:rb_tid],0
    jne .r
    push bx
    push cx
    mov bx,ax                           ; BL bit 0, BH bit 1
    and ah,al
    mov cl,ah                           ; CL = both
    mov al,bl
    and al,[cs:rb_tanf+1]
    mov ah,bh
    and ah,[cs:rb_tanf+2]
    xor al,ah
    mov ah,cl
    and ah,[cs:rb_tanf+3]
    xor al,ah
    xor al,[cs:rb_tanf]
    mov ch,al                           ; CH = the shade's bit 0
    mov al,bl
    and al,[cs:rb_tanf+5]
    mov ah,bh
    and ah,[cs:rb_tanf+6]
    xor al,ah
    mov ah,cl
    and ah,[cs:rb_tanf+7]
    xor al,ah
    xor al,[cs:rb_tanf+4]
    mov ah,al
    mov al,ch
    pop cx
    pop bx
.r:
    ret

rb_tfr          db 0, 0, 0, 0           ; the frame's canvas: SCY, SCX, BGP,
                                        ;   LCDC, as line RB_TMID sees them
rb_tpan         db 0FFh                 ; the pan the buffer is composed at
rb_tovn         dw 0                    ; the frame's overlay lines: how many
rb_tovl         times 144 db 0          ;   ...and which
rb_tcls         times 144 db 0          ; per line: an overlay (1) or clean
rb_tstl         times 144 db 1          ; per line: the buffer's not current
rb_tovi         dw 0                    ; (rb_renderd's: the overlay at hand)
rb_tli          db 0                    ; ppu_tcls's: the log index its
rb_trk          db 0                    ;   registers' verdict is for, and it
rb_tlsp         dw 0                    ;   (the loop's: the line's PPU_LSPR)
rb_tsp0         times 144 db 0          ; per overlay line: its first byte to
rb_tsp1         times 144 db 0          ;   write and its last
rb_tb0          db 0                    ; rb_trow's and rb_tpage's: the first
rb_tb1          db 0                    ;   byte and the last (one word)
rb_tn           db 0
rb_tcard        dw 0                    ; rb_tpage's: the card,
rb_tkey         dw 0                    ;   the page's keys, owed cells,
rb_tdirty       dw 0                    ;   lines held and owed lines,
rb_tpl          dw 0
rb_towed        dw 0
rb_tpseg        dw 0                    ;   the buffer,
rb_tmap         dw 0                    ;   the frame's map,
rb_twm          dw 0, 0                 ;   the columns in view, a bit each,
rb_tslot        db 0                    ;   the page's slot,
rb_tc0          db 0                    ;   the first column,
rb_tid          db 0                    ;   BGP the identity,
rb_tty          db 0                    ;   the cells' tile row,
rb_tny          db 0                    ;   rows left
rb_ttx          db 0                    ;   and column
rb_tln          db 0                    ; ppu_tmark's tiles: how many...
rb_tlst         times 16 db 0           ;   ...and their numbers
rb_tanf         times 8 db 0            ; BGP's D A B C, the shade's bit 0, 1
rb_tm           times 4 db 0
rb_twl          times 144 * 5 db 0      ; rb_tpage's writes: from, to, how many
RB_TQMAX        equ 24
rb_tqn          db 0                    ; rb_trow's queue: how many,
rb_tqc          times RB_TQMAX db 0     ;   each one's byte count,
rb_tqd          times RB_TQMAX dw 0     ;   where it goes,
rb_tqb          times RB_TQMAX * 42 db 0 ;  and its bytes (plane 1's at +21)
rb_tsc          db 144                  ; the strip's candidate, last frame...
rb_tsn          db 0                    ;   ...and the frames it has held
rb_tsall        db 0                    ; every strip line owed to the region
rb_tslay        db 144                  ; the strip the region is laid out for
rb_tbuf         times 42 db 0           ; a row's 21 bytes a plane, or a
                                        ;   cell's 8
%endif

; ppu_anf: one shade plane of the background into DI, through the ANF words
; at BP (D A B C): D xor (bit0 and A) xor (bit1 and B) xor (both and C)
ppu_anf:
    mov si,PPU_BL
    mov cx,[PPU_WN]
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

; ppu_blist: PPU_BLIST for the background's map row at SI, column BX -
; ppu_list's, kept by rb_renderd from call to call a map row at a time
; (RB_DLC) with the 21 map bytes it was built from: while they are the
; same, and the tile mode, it is copied rather than built (a map byte is
; compared, not looked up). ES = DS. Kept: DX
ppu_blist:
    lea ax,[si+bx]
    cmp [PPU_BKEY],ax
    je .r
    cmp byte [PPU_LCOK],0
    jne .c
.l:
    mov bp,PPU_BLIST
    mov di,PPU_BKEY
    jmp ppu_list
.r:
    ret
.c:
    push dx
    mov dx,ax                           ; DX = the key
    mov es,[cs:rb_dmgseg]
    mov al,[PPU_TMODE]
    cmp al,[es:RB_DLCMODE]
    je .cm
    mov [es:RB_DLCMODE],al              ; another tile mode: none kept is
    call ppu_lcflush                    ;   for it
.cm:
    mov ax,si
    mov cl,5
    shr ax,cl
    and ax,31
    mov cl,RB_DLCN
    mul cl
    add ax,RB_DLC
    mov bp,ax                           ; BP = its entry (in ES)
    push si
    mov cx,32                           ; the map bytes against the entry's,
    sub cx,bx                           ;   to the row's end and on from its
    cmp cx,21                           ;   start
    jbe .c1
    mov cx,21
.c1:
    mov ax,21
    sub ax,cx                           ; AX = the ones after the wrap
    cmp [es:bp],dx
    jne .st
    add si,bx
    lea di,[bp+46]
    repe cmpsb
    jne .st
    mov cx,ax
    pop si
    push si
    repe cmpsb
    jne .st
    pop si                              ; KEPT: copied, not built
    mov [PPU_BKEY],dx
    push ds
    push es
    pop ds
    pop es
    lea si,[bp+2]
    mov di,PPU_BLIST
    mov cx,22
    rep movsw
    push es
    pop ds
    push ds
    pop es
    pop dx
    ret
.st:
    pop si                              ; built, and kept with its map bytes
    mov [es:bp],dx
    lea di,[bp+46]
    push si
    mov cx,32
    sub cx,bx
    cmp cx,21
    jbe .s1
    mov cx,21
.s1:
    mov ax,21
    sub ax,cx
    add si,bx
    rep movsb
    mov cx,ax
    pop si
    push si
    rep movsb
    pop si
    push ds
    pop es
    push bp
    mov bp,PPU_BLIST
    mov di,PPU_BKEY
    call ppu_list
    pop di
    inc di
    inc di
    mov es,[cs:rb_dmgseg]
    mov si,PPU_BLIST
    mov cx,22
    rep movsw
    push ds
    pop es
    pop dx
    ret

; ppu_lcflush: RB_DLC's lists all dropped - a new tile mode, or the host's
; whole frame (its memory may be anything). ES = damage. Kept: all but AX
ppu_lcflush:
    push cx
    push di
    mov di,RB_DLC
    mov cx,32
    xor ax,ax
.f:
    mov [es:di],ax
    add di,RB_DLCN
    loop .f
    pop di
    pop cx
    ret

; ppu_list: at BP, the 21 tile addresses a line reads from the map row at
; SI, column BX (0-31) on, wrapping at the row's end - built only when [DI]
; says the list holds another row or column - and at [BP+42] 1 when the 21
; are one tile. ES = DS. Kept: DX.
ppu_list:
    lea ax,[si+bx]
    cmp [di],ax
    je .r
    mov [di],ax
    push dx
    mov dx,si                           ; DX = the row's column 0
    mov di,bp
    add si,bx
    mov cx,32
    sub cx,bx                           ; the columns before the wrap
    cmp cx,21
    jbe .a
    mov cx,21
.a:
    mov bx,21
    sub bx,cx                           ; BX = the ones after it
    call .run
    mov cx,bx
    jcxz .d
    mov si,dx
    call .run
.d:
    mov di,bp                           ; ONE TILE all along (a sky): [BP+42]
    mov ax,[di]                         ;   1, for ppu_line's fill - asked
    mov cx,21                           ;   here, once a map row
    repe scasw
    mov byte [ds:bp+42],1
    je .nu
    mov byte [ds:bp+42],0
.nu:
    pop dx
.r:
    ret
.run:
    push bx
.t:
    lodsb
    cbw
    shl ax,1
    xchg ax,bx
    mov ax,[PPU_TADDRC+bx]
    stosw
    loop .t
    pop bx
    ret

; ppu_fshift: the background's 20 bytes into PPU_BL and PPU_BH from the 21
; tile addresses at SI (DL = the row in the tile), the picture CL bits (1-7)
; left of the first tile's edge - the fine scroll, done as the bytes are
; fetched: each is the previous tile row and this one, as one 16-bit string,
; CL bits left. Unrolled, the two tile rows alternating between AX and DX:
; a 286 pays for every byte of code it fetches, so the loop's own are gone.
; PPU_FSHIFT op, half: ppu_fshift's body - each byte the previous tile row
; and this one as BH:BL, shifted by CL (op), its half the result
%macro PPU_FSHIFT 2
%assign ppu_k 0
%rep 10
    mov bx,[si+2*ppu_k+2]
    mov dx,[bx+di]
    mov bh,al
    mov bl,dl
    %1 bx,cl
    mov [PPU_BL+ppu_k],%2
    mov bh,ah
    mov bl,dh
    %1 bx,cl
    mov [PPU_BH+ppu_k],%2
    mov bx,[si+2*ppu_k+4]
    mov ax,[bx+di]
    mov bh,dl
    mov bl,al
    %1 bx,cl
    mov [PPU_BL+ppu_k+1],%2
    mov bh,dh
    mov bl,ah
    %1 bx,cl
    mov [PPU_BH+ppu_k+1],%2
%assign ppu_k ppu_k+2
%endrep
    ret
%endmacro
ppu_fshift:
    mov al,dl
    xor ah,ah
    shl ax,1
    mov di,ax                           ; DI = the row's offset in a tile
    mov bx,[si]
    mov ax,[bx+di]                      ; the first tile's row
    cmp cl,4                            ; a 286 shifts a register by CL in
    ja .right                           ;   5 + CL clocks: past 4, the same
    PPU_FSHIFT shl, bh                  ;   byte is the pair 8 - CL RIGHT, in
.right:                                 ;   its low half (1-4 bits either way)
    neg cl
    add cl,8
    PPU_FSHIFT shr, bl

; ppu_fcopyb / ppu_fcopyw: no fine scroll - 21 tile rows as they are, into
; PPU_BL/PPU_BH or PPU_WL/PPU_WH (the window shifts its own left)
%macro PPU_FCOPY 1
    mov al,dl
    xor ah,ah
    shl ax,1
    mov di,ax
%assign ppu_k 0
%rep 21
    mov bx,[si+2*ppu_k]
    mov ax,[bx+di]
    mov [%1+ppu_k],al
    mov [%1+20h+ppu_k],ah
%assign ppu_k ppu_k+1
%endrep
    ret
%endmacro
ppu_fcopyb:
    PPU_FCOPY PPU_BL
ppu_fcopyw:
    PPU_FCOPY PPU_WL

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
    jz .al                              ; S = 0: whole bytes, copied
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
.al:                                    ; (Kirby's Dream Land's status bar,
    cmp bx,20                           ;   WX = 7: every line of it)
    jae .r
    push es
    push ds
    pop es
    mov cx,20
    sub cx,bx
    push cx
    mov si,PPU_WL
    lea di,[PPU_BL+bx]
    rep movsb
    pop cx
    mov si,PPU_WH
    lea di,[PPU_BH+bx]
    rep movsb
    pop es
    ret

; ppu_sprites: up to ten sprites on line PPU_LY, in priority order, over
; PPU_OL/PPU_OH
%macro PPU_SPRITES 2
%1:
    ; find them, in OAM order - the counts in registers, not memory: DI's
    ; distance into PPU_SPR is the sprites found, BP's to [PPU_TMP] the
    ; candidates left
    mov dx,0FF08h                       ; DL = the height, DH = the mask
    test byte [PPU_REGS+0],04h          ;   an 8x16's tile takes
    jz .h8
    mov dx,0FE10h
.h8:
    mov [PPU_SMASK],dh
    mov al,[PPU_LY]                     ; the line's candidates, from ppu_oam
    mov dh,al
    add dh,16                           ; DH = LY + 16
    mov bl,41
    mul bl
    mov bx,ax
    mov di,PPU_SPR
    mov al,[PPU_LSPR+bx]
    or al,al
    jz .found
    xor ah,ah
    lea bp,[PPU_LSPR+1+bx]              ; BP = its OAM indices
    add ax,bp
    mov [PPU_TMP],ax                    ; ...and their end
.f:
    mov al,[ds:bp]                      ; (its offset in OAM)
    inc bp
    mov ah,0FEh
    mov si,ax                           ; SI = the sprite's OAM entry
    mov al,dh
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
    and bl,[PPU_SMASK]                  ;   (FEh for 8x16: the pair's first)
    xor bh,bh
    shl bx,1
    shl bx,1
    shl bx,1
    shl bx,1
    add bl,al                           ; ...its row: the tile's low byte is
    add bl,al                           ;   16 x (n AND 0Fh), the row's 2 x 0-15
    or bh,80h                           ;   at most 30 more, and never carries
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
    mov al,[si+1]                       ; X - off the right edge, 0 (never
    cmp al,168                          ;   drawn)...
    jb .xk
    xor al,al
.xk:
%if %2
    or al,al                            ; ...and else moved by the line's pan
    jz .xs
    add al,[PPU_SPAN]
.xs:
%endif
    mov [di],al
    mov [di+1],cl
    mov [di+2],ch
    mov [di+3],ah
    add di,4
    cmp di,PPU_SPR+40                   ; ten: the DMG's most on a line
    jae .found
.nf:
    cmp bp,[PPU_TMP]
    jb .f
.found:
    mov bp,di                           ; BP = the found ones' end, kept to
    mov ax,di                           ;   the drawing (the sort leaves it)
    sub ax,PPU_SPR
    shr ax,1
    shr ax,1
    mov [PPU_NSPR],al
    ; insertion sort by X, stable: equal X keeps OAM order
    mov cl,[PPU_NSPR]
    xor ch,ch
    jcxz .r
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
    cmp word [PPU_OSRC],PPU_BL          ; (over the background's own planes)
    je .db
.d:
    call ppu_sprite                     ; (SI and BP kept)
    add si,4
    cmp si,bp
    jb .d
.r:
    ret
.db:
    call ppu_spriteb
    add si,4
    cmp si,bp
    jb .db
    ret

%endmacro
PPU_SPRITES ppu_sprites, 0
%ifndef RB_NOPAN
PPU_SPRITES ppu_spritesp, 1
%endif

; PPU_SPRITE name, put, plane 0, plane 1 - ppu_sprite: one sprite, SI = its PPU_SPR entry, over the line. Its
; shades are PPU_SANF's three terms a bit; the shifts are made once each,
; with no register saved around them
%macro PPU_SPRITE 4
%1:
    mov al,[si]                         ; X: the line's pixel is X - 8 (0,
    or al,al                            ;   or past the edge: none)
    jz .r
    push bp
    mov bl,al
    xor bh,bh
    sub bx,8                            ; BX = X - 8, signed
    mov cl,bl
    and cl,7                            ; CL = the shift S
    sar bx,1
    sar bx,1
    sar bx,1                            ; BX = the byte B (may be -1)
    mov bp,PPU_SANF
    test byte [si+3],10h
    jz .p0
    mov bp,PPU_SANF+6
.p0:
    mov ax,[si+1]                       ; AL, AH = its colour bits 0 and 1
    mov dl,al
    and dl,ah                           ; DL = both
    mov dh,al
    and al,[ds:bp+0]
    mov ch,ah
    and ch,[ds:bp+1]
    xor al,ch
    mov ch,dl
    and ch,[ds:bp+2]
    xor al,ch                           ; AL = shade bit 0
    and dh,[ds:bp+3]
    and ah,[ds:bp+4]
    xor ah,dh
    and dl,[ds:bp+5]
    xor ah,dl                           ; AH = shade bit 1
    mov di,ax                           ; DI = the shades
    mov al,[si+1]
    or al,[si+2]                        ; opaque: colour not 0
    xor ah,ah
    ror ax,cl                           ; AL = byte B's part, AH = B+1's
    mov dx,ax                           ; DL, DH = opaque, both halves
    mov ax,di
    xor ah,ah
    ror ax,cl
    xchg ax,di                          ; DI = shade bit 0, both halves
    mov al,ah
    xor ah,ah
    ror ax,cl
    mov bp,ax                           ; BP = shade bit 1, both halves
    cmp bx,20                           ; both bytes on the line (0-19, all
    jae .edge                           ;   but the edges; 21 bytes, so an
                                        ;   aligned line's last): a word
    test byte [si+3],80h
    jnz .wb
    mov ax,[PPU_CL+bx]                  ; over the background: a pixel another
    not ax                              ;   sprite claimed first stays theirs
    and dx,ax
    or [PPU_CL+bx],dx
.w:
    and di,dx
    and bp,dx
    not dx
    and [%3+bx],dx
    and [%4+bx],dx
    or [%3+bx],di
    or [%4+bx],bp
    pop bp
    ret
.wb:
    mov ax,[PPU_CL+bx]                  ; behind it: claimed, and shown only
    not ax                              ;   over its colour 0
    and dx,ax
    or [PPU_CL+bx],dx
    mov ax,[PPU_BL+bx]
    or ax,[PPU_BH+bx]
    not ax
    and dx,ax
    jmp short .w
.edge:                                  ; B = -1 or 20: the byte on the line
    or bx,bx
    js .right
    cmp bx,21
    jae .x
    mov al,dl
    mov cx,di
    mov ah,cl
    mov cx,bp
    mov ch,cl
    call %2                        ; (DH kept)
.right:
    inc bx
    cmp bx,21
    jae .x
    mov al,dh
    mov cx,di
    mov ah,ch
    mov cx,bp
    call %2
.x:
    pop bp
.r:
    ret

; ppu_put: one byte of a sprite at line byte BX: AL = opaque, AH = shade bit
; 0, CH = shade bit 1. A pixel another sprite claimed first stays theirs; a
; behind-the-background pixel shows only over colour 0.
%2:
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
    and [%3+bx],al
    and [%4+bx],al
    or [%3+bx],ah
    or [%4+bx],ch
    ret
%endmacro
; ppu_sprite draws over PPU_OL/PPU_OH; ppu_spriteb over the background's own
; PPU_BL/PPU_BH, when BGP is the identity and the line is left there - a
; pixel it changes is one it claimed, and a later sprite reads the
; background only where nothing is claimed, so what it reads is unchanged
PPU_SPRITE ppu_sprite, ppu_put, PPU_OL, PPU_OH
PPU_SPRITE ppu_spriteb, ppu_putb, PPU_BL, PPU_BH
