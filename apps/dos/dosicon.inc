; =============================================================================
; os8088 - apps/dos/dosicon.inc
;
; **THE DOS BOX'S FACE, AND BOTH HALVES OF THE PACKAGE WEAR IT** (SPEC.md
; 96.44.4). Since W9c the file's IMAGE is `apps/dos/dosload.asm` - a parts
; loader that reads the box and hands its identity over (20.12.10) - so the
; icon and the association block are read out of the LOADER, before the box
; exists, while the dock draws the box's own after the launch.
;
; It is a `%include` and not a copy, which is WEAVE-SPEC 1.2's rule one
; package along: two files that must agree byte for byte agree by being one
; file. A copied icon drifts the first time somebody redraws a pixel, and the
; symptom is a Disk window and a dock that disagree about what the program
; looks like.
; =============================================================================
; --- the icon (SPEC.md 20.2/20.5) -------------------------------------------
; A CRT on a stand with a `>` prompt and a cursor under it. It is 1bpp and
; reads the same on all three adapters, which is what SPEC.md 39.4 asks of a
; drawing - and it is what a .COM and a .EXE WEAR, because SPEC.md 54.1
; composes a document's icon out of its program's. An iconless package would
; leave every DOS program on a disk showing assoc_compose's bare page, and
; tools/os88mini.py refuses to bake a default glyph from one at all.
    OS88_ICON16
    dw 0x0000, 0x7FFE, 0x7FFE, 0x7FFE, 0x7FFE, 0x7FFE, 0x7FFE, 0x7FFE
    dw 0x7FFE, 0x7FFE, 0x7FFE, 0x03C0, 0x03C0, 0x1FF8, 0x0000, 0x0000
    dw 0x0000, 0x7FFE, 0x4002, 0x4002, 0x5002, 0x4802, 0x5002, 0x4002
    dw 0x5F02, 0x4002, 0x7FFE, 0x03C0, 0x03C0, 0x1FF8, 0x0000, 0x0000
    OS88_ICON16_END

    OS88_ASSOC16
    db 3                            ; ...and this COUNT is the thing to change
    OS88_ASSOC_EXT 'COM'            ; with them: a fourth entry left at 2 sits
                                    ; in the block and is never looked at, and
                                    ; the symptom is the loader trying to RUN
                                    ; the document
    OS88_ASSOC_EXT 'EXE'
    OS88_ASSOC_EXT 'LNK'            ; a SHORTCUT (SPEC.md 96.21): the target,
                                    ; its arguments and its environment, in
                                    ; Microsoft's own Shell Link layout
    OS88_ASSOC16_END
