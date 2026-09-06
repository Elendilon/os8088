; =============================================================================
; os8088 - apps/tape/reels.inc - the cassette hub, eight phases (SPEC.md 88.8.1)
;
; **THE REELS COAST; THEY DO NOT SPIN.** SPEC.md 88.8.1 is binding about this
; and the reason is not decoration: a continuous spinner stopped dead for nine
; seconds reads as HUNG - SPEC.md 7.1.4.3 records this project shipping a
; lit-but-frozen pointer and the field calling it a stutter at a timescale of
; milliseconds, and a record is three orders of magnitude longer. So at every
; record boundary, the moment the machine comes back, the hubs spin an
; 8-frame decelerating burst over 560 ms and STOP.
;
; **EIGHT FRAMES = ONE FULL VISUAL REVOLUTION = ONE RECORD.** A four-spoke hub
; has 90-degree symmetry, so eight phases at 11.25 degrees is a complete
; revolution and the mapping MEANS something: one turn of the reels is one
; block on tape.
;
; THE RECORD IS 66 BYTES AND NOT 64 (SPEC.md 25.6): icon_draw_x reads a
; two-byte ww/rows header first and refuses any width but one word, so a phase
; is `db 1, 16` + 16 mask words + 16 data words. Eight of them is 528 bytes.
;
; MASK = the whole disc, DATA = the picture. The mask is what makes a phase
; ERASE the one before it - OSAPI_ICON_PEN's default lays the mask down in
; CWHITE and the data over it in CBLACK - so a coast needs no separate clear
; and writes no pixel twice. It is also why the disc is a filled circle rather
; than only the ink: a mask that covered the spokes alone would leave the
; previous frame's spokes standing.
;
; **NO GREY ANYWHERE** (SPEC.md 88.8.1, 39.4). Solid black on white: an
; outline rim, four straight spokes, a filled hub. Grey rounds to black on
; both 1bpp adapters, so a "dimmed" reel would be a black disc on the only
; machine that will ever run this.
;
; HUB RADII ARE REFUSED (SPEC.md 88.8.1): a shrinking supply reel and a
; growing take-up would be three states each - 24 records, 1,584 bytes - and
; ICON_DRAW is masked, so a smaller disc drawn where a larger one was leaves
; the outer ring standing. Tape position is the progress bar's job.
;
; The bitmaps are GENERATED - rim 6.6..7.7 px, hub r <= 1.9, four spokes 1.4 px
; wide from r 1.9 to 6.8, at 11.25 degrees a phase, on a 16x16 cell centred at
; (7.5, 7.5) - and the ASCII above each one is that phase rendered, so a change
; is reviewable without a machine.
; =============================================================================

; --- phase 0:  0.00 degrees ---
;   |      ####      |
;   |    ########    |
;   |   #...##...#   |
;   |  #....##....#  |
;   | #.....##.....# |
;   | #.....##.....# |
;   |##.....##.....##|
;   |################|
;   |################|
;   |##.....##.....##|
;   | #.....##.....# |
;   | #.....##.....# |
;   |  #....##....#  |
;   |   #...##...#   |
;   |    ########    |
;   |      ####      |
tp_reel0:
    db 1, 16                       ; ww = 1 word a row, 16 rows
    dw 0x03C0, 0x0FF0, 0x1FF8, 0x3FFC   ; mask
    dw 0x7FFE, 0x7FFE, 0xFFFF, 0xFFFF
    dw 0xFFFF, 0xFFFF, 0x7FFE, 0x7FFE
    dw 0x3FFC, 0x1FF8, 0x0FF0, 0x03C0
    dw 0x03C0, 0x0FF0, 0x1188, 0x2184   ; data
    dw 0x4182, 0x4182, 0xC183, 0xFFFF
    dw 0xFFFF, 0xC183, 0x4182, 0x4182
    dw 0x2184, 0x1188, 0x0FF0, 0x03C0

; --- phase 1: 11.25 degrees ---
;   |      ####      |
;   |    ###..###    |
;   |   #....##..#   |
;   |  #.....##...#  |
;   | #......#.....# |
;   | #......#.....# |
;   |####...##.....##|
;   |#.########.....#|
;   |#.....########.#|
;   |##.....##...####|
;   | #.....#......# |
;   | #.....#......# |
;   |  #...##.....#  |
;   |   #..##....#   |
;   |    ###..###    |
;   |      ####      |
tp_reel1:
    db 1, 16                       ; ww = 1 word a row, 16 rows
    dw 0x03C0, 0x0FF0, 0x1FF8, 0x3FFC   ; mask
    dw 0x7FFE, 0x7FFE, 0xFFFF, 0xFFFF
    dw 0xFFFF, 0xFFFF, 0x7FFE, 0x7FFE
    dw 0x3FFC, 0x1FF8, 0x0FF0, 0x03C0
    dw 0x03C0, 0x0E70, 0x10C8, 0x20C4   ; data
    dw 0x4082, 0x4082, 0xF183, 0xBFC1
    dw 0x83FD, 0xC18F, 0x4102, 0x4102
    dw 0x2304, 0x1308, 0x0E70, 0x03C0

; --- phase 2: 22.50 degrees ---
;   |      ####      |
;   |    ###..###    |
;   |   #.....##.#   |
;   |  #......##..#  |
;   | #.......#....# |
;   | ###....##....# |
;   |######.##.....##|
;   |#....#####.....#|
;   |#.....#####....#|
;   |##.....##.######|
;   | #....##....### |
;   | #....#.......# |
;   |  #..##......#  |
;   |   #.##.....#   |
;   |    ###..###    |
;   |      ####      |
tp_reel2:
    db 1, 16                       ; ww = 1 word a row, 16 rows
    dw 0x03C0, 0x0FF0, 0x1FF8, 0x3FFC   ; mask
    dw 0x7FFE, 0x7FFE, 0xFFFF, 0xFFFF
    dw 0xFFFF, 0xFFFF, 0x7FFE, 0x7FFE
    dw 0x3FFC, 0x1FF8, 0x0FF0, 0x03C0
    dw 0x03C0, 0x0E70, 0x1068, 0x2064   ; data
    dw 0x4042, 0x70C2, 0xFD83, 0x87C1
    dw 0x83E1, 0xC1BF, 0x430E, 0x4202
    dw 0x2604, 0x1608, 0x0E70, 0x03C0

; --- phase 3: 33.75 degrees ---
;   |      ####      |
;   |    ###..###    |
;   |   #.......##   |
;   |  #.......##.#  |
;   | ###.....##...# |
;   | #.###...##...# |
;   |##..######....##|
;   |#.....####.....#|
;   |#.....####.....#|
;   |##....######..##|
;   | #...##...###.# |
;   | #...##.....### |
;   |  #.##.......#  |
;   |   ##.......#   |
;   |    ###..###    |
;   |      ####      |
tp_reel3:
    db 1, 16                       ; ww = 1 word a row, 16 rows
    dw 0x03C0, 0x0FF0, 0x1FF8, 0x3FFC   ; mask
    dw 0x7FFE, 0x7FFE, 0xFFFF, 0xFFFF
    dw 0xFFFF, 0xFFFF, 0x7FFE, 0x7FFE
    dw 0x3FFC, 0x1FF8, 0x0FF0, 0x03C0
    dw 0x03C0, 0x0E70, 0x1018, 0x2034   ; data
    dw 0x7062, 0x5C62, 0xCFC3, 0x83C1
    dw 0x83C1, 0xC3F3, 0x463A, 0x460E
    dw 0x2C04, 0x1808, 0x0E70, 0x03C0

; --- phase 4: 45.00 degrees ---
;   |      ####      |
;   |    ###..###    |
;   |   #........#   |
;   |  ###......###  |
;   | #.###....###.# |
;   | #..###..###..# |
;   |##...######...##|
;   |#.....####.....#|
;   |#.....####.....#|
;   |##...######...##|
;   | #..###..###..# |
;   | #.###....###.# |
;   |  ###......###  |
;   |   #........#   |
;   |    ###..###    |
;   |      ####      |
tp_reel4:
    db 1, 16                       ; ww = 1 word a row, 16 rows
    dw 0x03C0, 0x0FF0, 0x1FF8, 0x3FFC   ; mask
    dw 0x7FFE, 0x7FFE, 0xFFFF, 0xFFFF
    dw 0xFFFF, 0xFFFF, 0x7FFE, 0x7FFE
    dw 0x3FFC, 0x1FF8, 0x0FF0, 0x03C0
    dw 0x03C0, 0x0E70, 0x1008, 0x381C   ; data
    dw 0x5C3A, 0x4E72, 0xC7E3, 0x83C1
    dw 0x83C1, 0xC7E3, 0x4E72, 0x5C3A
    dw 0x381C, 0x1008, 0x0E70, 0x03C0

; --- phase 5: 56.25 degrees ---
;   |      ####      |
;   |    ###..###    |
;   |   ##.......#   |
;   |  #.##.......#  |
;   | #...##.....### |
;   | #...##...###.# |
;   |##....######..##|
;   |#.....####.....#|
;   |#.....####.....#|
;   |##..######....##|
;   | #.###...##...# |
;   | ###.....##...# |
;   |  #.......##.#  |
;   |   #.......##   |
;   |    ###..###    |
;   |      ####      |
tp_reel5:
    db 1, 16                       ; ww = 1 word a row, 16 rows
    dw 0x03C0, 0x0FF0, 0x1FF8, 0x3FFC   ; mask
    dw 0x7FFE, 0x7FFE, 0xFFFF, 0xFFFF
    dw 0xFFFF, 0xFFFF, 0x7FFE, 0x7FFE
    dw 0x3FFC, 0x1FF8, 0x0FF0, 0x03C0
    dw 0x03C0, 0x0E70, 0x1808, 0x2C04   ; data
    dw 0x460E, 0x463A, 0xC3F3, 0x83C1
    dw 0x83C1, 0xCFC3, 0x5C62, 0x7062
    dw 0x2034, 0x1018, 0x0E70, 0x03C0

; --- phase 6: 67.50 degrees ---
;   |      ####      |
;   |    ###..###    |
;   |   #.##.....#   |
;   |  #..##......#  |
;   | #....#.......# |
;   | #....##....### |
;   |##.....##.######|
;   |#.....#####....#|
;   |#....#####.....#|
;   |######.##.....##|
;   | ###....##....# |
;   | #.......#....# |
;   |  #......##..#  |
;   |   #.....##.#   |
;   |    ###..###    |
;   |      ####      |
tp_reel6:
    db 1, 16                       ; ww = 1 word a row, 16 rows
    dw 0x03C0, 0x0FF0, 0x1FF8, 0x3FFC   ; mask
    dw 0x7FFE, 0x7FFE, 0xFFFF, 0xFFFF
    dw 0xFFFF, 0xFFFF, 0x7FFE, 0x7FFE
    dw 0x3FFC, 0x1FF8, 0x0FF0, 0x03C0
    dw 0x03C0, 0x0E70, 0x1608, 0x2604   ; data
    dw 0x4202, 0x430E, 0xC1BF, 0x83E1
    dw 0x87C1, 0xFD83, 0x70C2, 0x4042
    dw 0x2064, 0x1068, 0x0E70, 0x03C0

; --- phase 7: 78.75 degrees ---
;   |      ####      |
;   |    ###..###    |
;   |   #..##....#   |
;   |  #...##.....#  |
;   | #.....#......# |
;   | #.....#......# |
;   |##.....##...####|
;   |#.....########.#|
;   |#.########.....#|
;   |####...##.....##|
;   | #......#.....# |
;   | #......#.....# |
;   |  #.....##...#  |
;   |   #....##..#   |
;   |    ###..###    |
;   |      ####      |
tp_reel7:
    db 1, 16                       ; ww = 1 word a row, 16 rows
    dw 0x03C0, 0x0FF0, 0x1FF8, 0x3FFC   ; mask
    dw 0x7FFE, 0x7FFE, 0xFFFF, 0xFFFF
    dw 0xFFFF, 0xFFFF, 0x7FFE, 0x7FFE
    dw 0x3FFC, 0x1FF8, 0x0FF0, 0x03C0
    dw 0x03C0, 0x0E70, 0x1308, 0x2304   ; data
    dw 0x4102, 0x4102, 0xC18F, 0x83FD
    dw 0xBFC1, 0xF183, 0x4082, 0x4082
    dw 0x20C4, 0x10C8, 0x0E70, 0x03C0

; The eight in order. tp_reel_at indexes it rather than doing the 66-byte
; multiply at each of the two call sites a frame makes.
tp_reels:
    dw tp_reel0, tp_reel1, tp_reel2, tp_reel3
    dw tp_reel4, tp_reel5, tp_reel6, tp_reel7
