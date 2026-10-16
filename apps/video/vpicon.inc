; =============================================================================
; os8088 - apps/video/vpicon.inc
;
; THE VIDEO PLAYER'S FACE, AND BOTH HALVES OF VIDEO.O88 WEAR IT (SPEC.md
; 98.3.23). The file's IMAGE is apps/video/vidload.asm - a parts loader that
; reads the player and hands its identity over (SPEC.md 20.12.10) - so the
; icon, the .V88 association and the document glyph are read out of the
; LOADER, before the player exists, while the dock and the About card draw
; the player's own after the launch. One include and not a copy, for
; apps/dos/dosicon.inc's reason: two files that must agree byte for byte
; agree by being one file.
; =============================================================================


; --- the icon (SPEC.md 20.2): a play button --------------------------------
; A solid disc with a play triangle cut out of it, so it reads as one shape
; on every adapter - no grey, no one-pixel stroke (SPEC.md 39.4). The mask
; is the disc dilated one pixel, a white underlay round it.
;
;   .....######.....    the data; the mask is every pixel but the corners
;   ..##########..
;   .####.#######.      (rows 0-2 and 13-15 shown trimmed)
;   .####..######.
;   #####....#####
;   #####.....####
;   #####.......##
    OS88_ICON16
    dw 0x3FFC, 0x7FFE, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF
    dw 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0x7FFE, 0x3FFC
    dw 0x07E0, 0x1FF8, 0x3FFC, 0x7BFE, 0x79FE, 0xF87F, 0xF83F, 0xF80F
    dw 0xF80F, 0xF83F, 0xF87F, 0x79FE, 0x7BFE, 0x3FFC, 0x1FF8, 0x07E0
    OS88_ICON16_END

    OS88_ASSOC16                    ; SPEC.md 54.6: double-click a .V88
    db 1
    OS88_ASSOC_EXT 'V88'
    OS88_ASSOC16_END

; --- what a .V88 wears (SPEC.md 54.3.2) -------------------------------------
; The disc reduced by majority would be a solid blob with the triangle gone,
; so a document wears the triangle alone, black on its page.
    OS88_DOCGLYPH8
    db 0x40                         ; .#......
    db 0x70                         ; .###....
    db 0x7C                         ; .#####..
    db 0x7E                         ; .######.
    db 0x7C                         ; .#####..
    db 0x70                         ; .###....
    db 0x40                         ; .#......
    db 0x00                         ; ........
    OS88_DOCGLYPH8_END
