; WireArena's shared constants and the figure record (docs/plans/
; WIREARENA-PARTS-PLAN.md). Included by the primary (wirearena.asm) and,
; from the split on, by the renderer part (wrpart.asm): one definition of
; every number both halves agree on.

WA_ROWS     equ 24              ; view rows; row 24 is the HUD
WA_HR       equ 48              ; view half-rows
WA_MAXW     equ 80
WA_CELLS    equ WA_MAXW*WA_ROWS
WA_NEAR     equ 16              ; near plane, units (1/64 m)
WA_KYQ      equ 133             ; quarter half-rows a unit of y/z (33.3 x 4)
WA_KYH256   equ 8533            ; half-rows a unit of y/z, x 256
WA_HTOP     equ 192             ; wall height, 3 m
WA_EYE      equ 102             ; eye height standing, 1.6 m
WA_RAD      equ 20              ; player radius
WA_TICK     equ 39773           ; PIT counts (838 ns) in a 30 Hz sim tick
WA_MSPD     equ 80              ; move: Q13 vector x 80 = 10 units a tick
WA_JUMPV    equ 2432            ; 8.8 units a tick: about a 1 m jump
WA_GRAV     equ 179             ; 8.8 units a tick a tick: 9.8 m/s^2
WA_PITCHU   equ 112             ; the pitch clamp, quarter half-rows: up
WA_PITCHD   equ 290             ; 33 degrees at 75, DOWN 59 - the same reach
                                ; (1.4 m) from the tower's top and its foot
                                ; (HEIGHTS-PLAN 7.1.1, 7.1.2: the owner
                                ; judges them by play; change them here)
WA_BLANK    equ 0x0720
; wa_look (the FRAME block): the DETAIL LEVEL's options (HEIGHTS-PLAN 9.11),
; a bit each - the game's wa_levtab makes them from the level, keys 1..5
LK_ROUND    equ 1               ; the products' rounded high words
LK_COARSE   equ 2               ; an edge moving under a half-row: level
LK_NOPOST   equ 4               ; no posts on walls under WA_POSTMIN
LK_ROOMF    equ 8               ; the room's walls as floor lines alone
LK_FARTOP   equ 16              ; a low box's far top only well above it
LK_RAMP2    equ 32              ; a ramp without its foot's line
LK_FEW      equ 64              ; J: a small figure's 7 joints, 5 limbs
WA_FLODV    equ 16              ; LK_FEW: fv8 below this: under ~7 half-rows tall

; per-figure record
F_X     equ 0
F_Y     equ 2
F_ANG   equ 4                   ; facing, 0..1023
F_LEG   equ 6                   ; leg index * 8 (byte offset into the path)
F_STEP  equ 8                   ; steps left on this leg
F_SH    equ 10                  ; byte: its shield (WEAPONS-PLAN 2.3) - the
                                ; renderer draws a chest yellow while it
                                ; holds any
F_ANIM  equ 11                  ; byte: first keyframe of the animation
F_NFR   equ 12                  ; byte: its keyframe count
F_LOOP  equ 13                  ; byte: 1 loops, 0 holds the last frame
F_PH    equ 14                  ; word: phase, quarter keyframes
F_FLASH equ 16                  ; byte: hit-flash frames left
F_DEAD  equ 17                  ; byte: ticks until respawn, 0 = alive
F_Z     equ 18                  ; the floor it stands on, units (HEIGHTS-
                                ; PLAN 3.3: wa_figtick, 0 on a flat arena)
F_HEAD  equ 20                  ; heading of the current leg
F_PATH  equ 22                  ; -> its path
F_PZ    equ 24                  ; last projection: z (0 = not drawn)
F_PIZ   equ 26                  ;   inverse depth
F_PCX   equ 28                  ;   centre, sub-columns
F_PTOP  equ 30                  ;   head, half-rows
F_PBOT  equ 32                  ;   feet, half-rows
F_PWH   equ 34                  ;   half width, sub-columns
F_VH    equ 36                  ; the heading F_VX/F_VY are for, | 0x8000
F_VX    equ 38                  ;   (0: none yet): a tick's step, units
F_VY    equ 40
F_HP    equ 42                  ; byte: its health (the game's alone)
F_KILL  equ 43                  ; byte: the weapon that killed it (0..2)
F_SIZE  equ 44
