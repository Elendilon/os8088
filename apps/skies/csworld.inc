; =============================================================================
; os8088 - apps/skies/csworld.inc
;
; THE WORLD (SPEC.md 88.6): the models, the objects that stand in Paris, and
; the two tables a second row could be added to - the aeroplanes and the
; airports. Metres; x east, z north, y up; the Eiffel Tower at the origin.
;
; A MODEL is db type, nverts (a STACK's LEVELS), nfaces, nedges, edge ink, 0;
; dw radius, verts, faces, edges. A STACK's verts are levels of (wx, h, wz),
; each standing for the four corners (+wx,h,+wz) (-wx,h,+wz) (-wx,h,-wz)
; (+wx,h,-wz), so a box is two levels and a pyramid a level and an apex. A
; FLAT model's verts are (x, z) pairs on the ground. A FACE is db n, ink,
; flags, then n indices, listed COUNTER-CLOCKWISE seen from outside; an EDGE
; is two indices.
; =============================================================================

; --- faces between level %1 and the one above, and a top --------------------
; The winding is checked once, in the panel, and every box in the world uses
; these four tables.
%macro CS_SIDES 3                   ; base, the +-z ink, the +-x ink
    db 4, %2, 0, %1+1, %1+5, %1+4, %1+0     ; +z
    db 4, %2, 0, %1+3, %1+7, %1+6, %1+2     ; -z
    db 4, %3, 0, %1+0, %1+4, %1+7, %1+3     ; +x
    db 4, %3, 0, %1+2, %1+6, %1+5, %1+1     ; -x
%endmacro
%macro CS_TOP 2                     ; base (the level's first index), ink
    db 4, %2, 0, %1+3, %1+0, %1+1, %1+2
%endmacro

cs_f_box:                           ; two levels: four walls and a roof
    CS_SIDES 0, CSI_WALL, CSI_WALL2
    CS_TOP 4, CSI_ROOF
cs_f_pyr:                           ; a level and an apex: four faces
    CS_SIDES 0, CSI_WALL, CSI_WALL2
cs_f_dome:                          ; a box with a pyramid on it: eight
    CS_SIDES 0, CSI_WALL, CSI_WALL2
    CS_SIDES 4, CSI_WALL, CSI_WALL2
cs_f_hill:                          ; a frustum in the hill's ink
    CS_SIDES 0, CSI_HILL, CSI_HILL
    CS_TOP 4, CSI_HILL
cs_f_sacre:                         ; a box, its roof, a drum and a dome
    CS_SIDES 0, CSI_WALL, CSI_WALL2
    CS_TOP 4, CSI_ROOF
    CS_SIDES 4, CSI_WALL, CSI_WALL2
    CS_SIDES 8, CSI_WALL, CSI_WALL2

; --- a box, a pyramid, a dome (SPEC.md 88.5) -----------------------------------
%macro CS_BOX 4                     ; label, wx, h, wz
%1: db CSM_STACK, 2, 5, 0, CSI_LINE, 0
    dw %2 + %4 + %3 / 2, %%v, cs_f_box, 0
%%v: dw %2, 0, %4
     dw %2, %3, %4
%endmacro
%macro CS_PYR 4                     ; label, wx, h, wz
%1: db CSM_STACK, 2, 4, 0, CSI_LINE, 0
    dw %2 + %4 + %3 / 2, %%v, cs_f_pyr, 0
%%v: dw %2, 0, %4
     dw 0, %3, 0
%endmacro
%macro CS_DOME 4                    ; label, w, the box's h, the apex's h
%1: db CSM_STACK, 3, 8, 0, CSI_LINE, 0
    dw %2 + %2 + %4 / 2, %%v, cs_f_dome, 0
%%v: dw %2, 0, %2
     dw %2, %3, %2
     dw 0, %4, 0
%endmacro

CS_BOX cs_m_troc,   50,  24,  60
CS_BOX cs_m_ecole, 100,  22,  40
CS_BOX cs_m_inval, 110,  22, 110
CS_DOME cs_m_idome, 25,  60, 107
CS_BOX cs_m_montp,  25, 210,  16
CS_BOX cs_m_louvre, 250, 24,  60
CS_PYR cs_m_lpyr,   17,  21,  17
CS_BOX cs_m_ndnave, 60,  32,  24
CS_BOX cs_m_ndtwr,  10,  69,  10
CS_BOX cs_m_arc,    25,  50,  12
CS_BOX cs_m_arche,  55, 110,  55
CS_BOX cs_m_def1,   30, 180,  30
CS_BOX cs_m_def2,   25, 150,  25
CS_BOX cs_m_def3,   28, 160,  28
CS_BOX cs_m_def4,   24, 120,  24
CS_BOX cs_m_hangar, 30,  12,  60
CS_BOX cs_m_shed,   40,  10,  40
CS_BOX cs_m_block,  60,  20,  60
CS_BOX cs_m_block2, 80,  20,  40
CS_BOX cs_m_small,  25,  15,  25

cs_m_panth: db CSM_STACK, 4, 13, 0, CSI_LINE, 0
    dw 120, .v, cs_f_sacre, 0
.v: dw 40, 0, 40
    dw 40, 30, 40
    dw 15, 50, 15
    dw 0, 83, 0

cs_m_sacre: db CSM_STACK, 4, 13, 0, CSI_LINE, 0
    dw 120, .v, cs_f_sacre, 0
.v: dw 40, 0, 40
    dw 40, 25, 40
    dw 12, 55, 12
    dw 0, 83, 0

cs_m_hill: db CSM_STACK, 2, 5, 0, CSI_LINE, 0
    dw 1300, .v, cs_f_hill, 0
.v: dw 700, 0, 500
    dw 150, 100, 120

; --- the tower (SPEC.md 88.5): five levels, thirty-two edges ------------------
cs_m_eiffel: db CSM_STACK, 5, 0, 32, CSI_LINE, 0
    dw 330, .v, 0, .e
.v: dw 62, 0, 62
    dw 35, 57, 35
    dw 20, 115, 20
    dw 8, 276, 8
    dw 0, 324, 0
.e: db 0,1, 1,2, 2,3, 3,0           ; the squares at the four platforms
    db 4,5, 5,6, 6,7, 7,4
    db 8,9, 9,10, 10,11, 11,8
    db 12,13, 13,14, 14,15, 15,12
    db 0,4, 1,5, 2,6, 3,7           ; the legs between them
    db 4,8, 5,9, 6,10, 7,11
    db 8,12, 9,13, 10,14, 11,15
    db 12,16, 13,17, 14,18, 15,19   ; ...and the spire

cs_m_eiffelf: db CSM_STACK, 2, 0, 4, CSI_LINE, 0    ; the far one: the four
    dw 330, .v, 0, .e                               ; legs to the apex. The
.v: dw 62, 0, 62                                    ; base square is eight
    dw 0, 300, 0                                    ; pixels wide where this
.e: db 0,4, 1,5, 2,6, 3,7                           ; stands in, and cost
                                                    ; four segments (88.5.4)

; --- the Seine, three strips cut in two (generated: SPEC.md 88.6): each half
;     a ribbon of two or three quads near, its centreline far, so a piece
;     that is a row of dither at the horizon is a segment or two and not a
;     dozen transformed vertices (88.6.1) ----------------------------------
cs_m_rive0: db CSM_FLAT, 6, 2, 0, CSI_RIVER, 0
    dw 1550, .v, .f, 0
.v: dw 1424, -1000
    dw -276, 99
    dw -1276, 700
    dw 1510, -866
    dw -190, 235
    dw -1190, 834
.f: db 4, CSI_RIVER, CSF_NOCULL, 0, 1, 4, 3
    db 4, CSI_RIVER, CSF_NOCULL, 1, 2, 5, 4
cs_m_rive0f: db CSM_FLAT, 3, 0, 2, CSI_MARK, 0
    dw 1550, .v, 0, .e
.v: dw 1467, -933
    dw -233, 167
    dw -1233, 767
.e: db 0,1, 1,2
cs_m_rive1: db CSM_FLAT, 6, 2, 0, CSI_RIVER, 0
    dw 1373, .v, .f, 0
.v: dw 1224, -600
    dw 43, 191
    dw -1333, 187
    dw 1310, -466
    dw 91, 343
    dw -1333, 347
.f: db 4, CSI_RIVER, CSF_NOCULL, 0, 1, 4, 3
    db 4, CSI_RIVER, CSF_NOCULL, 1, 2, 5, 4
cs_m_rive1f: db CSM_FLAT, 3, 0, 2, CSI_MARK, 0
    dw 1373, .v, 0, .e
.v: dw 1267, -533
    dw 67, 267
    dw -1333, 267
.e: db 0,1, 1,2
cs_m_rivc0: db CSM_FLAT, 6, 2, 0, CSI_RIVER, 0
    dw 1083, .v, .f, 0
.v: dw 1019, 239
    dw 26, -9
    dw -957, -450
    dw 981, 395
    dw -26, 143
    dw -1043, -316
.f: db 4, CSI_RIVER, CSF_NOCULL, 0, 1, 4, 3
    db 4, CSI_RIVER, CSF_NOCULL, 1, 2, 5, 4
cs_m_rivc0f: db CSM_FLAT, 3, 0, 2, CSI_MARK, 0
    dw 1083, .v, 0, .e
.v: dw 1000, 317
    dw 0, 67
    dw -1000, -383
.e: db 0,1, 1,2
cs_m_rivc1: db CSM_FLAT, 6, 2, 0, CSI_RIVER, 0
    dw 1350, .v, .f, 0
.v: dw 1310, 933
    dw -83, -163
    dw -1083, -962
    dw 1224, 1067
    dw -183, -37
    dw -1183, -838
.f: db 4, CSI_RIVER, CSF_NOCULL, 0, 1, 4, 3
    db 4, CSI_RIVER, CSF_NOCULL, 1, 2, 5, 4
cs_m_rivc1f: db CSM_FLAT, 3, 0, 2, CSI_MARK, 0
    dw 1350, .v, 0, .e
.v: dw 1267, 1000
    dw -133, -100
    dw -1133, -900
.e: db 0,1, 1,2
cs_m_rivw0: db CSM_FLAT, 6, 2, 0, CSI_RIVER, 0
    dw 1230, .v, .f, 0
.v: dw 1186, -78
    dw -43, -379
    dw -1190, 243
    dw 1148, 78
    dw -23, -221
    dw -1076, 357
.f: db 4, CSI_RIVER, CSF_NOCULL, 0, 1, 4, 3
    db 4, CSI_RIVER, CSF_NOCULL, 1, 2, 5, 4
cs_m_rivw0f: db CSM_FLAT, 3, 0, 2, CSI_MARK, 0
    dw 1230, .v, 0, .e
.v: dw 1167, 0
    dw -33, -300
    dw -1133, 300
.e: db 0,1, 1,2
cs_m_rivw1: db CSM_FLAT, 4, 1, 0, CSI_RIVER, 0
    dw 597, .v, .f, 0
.v: dw 193, -557
    dw -322, 464
    dw 307, -443
    dw -178, 536
.f: db 4, CSI_RIVER, CSF_NOCULL, 0, 1, 3, 2
cs_m_rivw1f: db CSM_FLAT, 2, 0, 1, CSI_MARK, 0
    dw 597, .v, 0, .e
.v: dw 250, -500
    dw -250, 500
.e: db 0,1

; --- the roads: the axis from the Louvre to La Defense, and the ring road ----
cs_e_road2: db 0,1, 1,2
cs_e_road3: db 0,1, 1,2, 2,3

cs_m_axis: db CSM_FLAT, 3, 0, 2, CSI_MARK, 0
    dw 4200, .v, 0, cs_e_road2
.v: dw -3700, 1900                  ; about (-600, 1900)
    dw 600, -200
    dw 3630, -1600

cs_m_per0: db CSM_FLAT, 4, 0, 3, CSI_MARK, 0
    dw 3739, cs_m_per0_v, 0, cs_e_road3
cs_m_per0_v:
    dw  -3076,   2124
    dw   -476,   1427
    dw   1427,   -476
    dw   2124,  -3076
cs_m_per1: db CSM_FLAT, 4, 0, 3, CSI_MARK, 0
    dw 3739, cs_m_per1_v, 0, cs_e_road3
cs_m_per1_v:
    dw   2124,   3076
    dw   1427,    476
    dw   -476,  -1427
    dw  -3076,  -2124
cs_m_per2: db CSM_FLAT, 4, 0, 3, CSI_MARK, 0
    dw 3739, cs_m_per2_v, 0, cs_e_road3
cs_m_per2_v:
    dw   3076,  -2124
    dw    476,  -1427
    dw  -1427,    476
    dw  -2124,   3076
cs_m_per3: db CSM_FLAT, 4, 0, 3, CSI_MARK, 0
    dw 3739, cs_m_per3_v, 0, cs_e_road3
cs_m_per3_v:
    dw  -2124,  -3076
    dw  -1427,   -476
    dw    476,   1427
    dw   3076,   2124

; --- the runway's face and edges: its vertices are built in bss by
;     cs_airport from the airport record (SPEC.md 88.6) --------------------------
cs_f_rwy:  db 4, CSI_RUNWAY, CSF_NOCULL, 0, 1, 2, 3
cs_e_rwy:  db 0,1, 1,2, 2,3, 3,0, 4,5

; =============================================================================
; The objects (SPEC.md 88.6): model, far model, x, z, y, range, lod, name,
; flags. Placed off a map with the tower at the origin.
; =============================================================================
%macro CS_OBJ 9
    dw %1, %2, %3, %4, %5, %6, %7, %8, %9, 0   ; ...and CSO_SKIP
%endmacro

cs_objtab:
    CS_OBJ cs_m_eiffel, cs_m_eiffelf,     0,     0,   0, 16000, 2500, cs_n_eiffel, CSO_COLLIDE
    CS_OBJ cs_m_troc,   0,             -480,   520,   0,  3000,    0, cs_n_troc,   CSO_COLLIDE
    CS_OBJ cs_m_troc,   0,             -180,   620,   0,  3000,    0, cs_n_troc,   CSO_COLLIDE
    CS_OBJ cs_m_ecole,  0,              150,  -900,   0,  3000,    0, cs_n_ecole,  CSO_COLLIDE
    CS_OBJ cs_m_inval,  0,             1320,  -380,   0,  3500,    0, cs_n_inval,  CSO_COLLIDE
    CS_OBJ cs_m_idome,  0,             1320,  -560,   0,  8000,    0, cs_n_inval,  CSO_COLLIDE
    CS_OBJ cs_m_montp,  0,             2000, -1800,   0, 16000,    0, cs_n_montp,  CSO_COLLIDE
    CS_OBJ cs_m_louvre, 0,             2900,   250,   0,  5000,    0, cs_n_louvre, CSO_COLLIDE
    CS_OBJ cs_m_lpyr,   0,             3030,   300,   0,  2500,    0, cs_n_louvre, CSO_COLLIDE
    CS_OBJ cs_m_ndnave, 0,             4060,  -600,   0,  4000,    0, cs_n_nd,     CSO_COLLIDE
    CS_OBJ cs_m_ndtwr,  0,             3995,  -585,   0,  6000,    0, cs_n_nd,     CSO_COLLIDE
    CS_OBJ cs_m_ndtwr,  0,             3995,  -615,   0,  6000,    0, cs_n_nd,     CSO_COLLIDE
    CS_OBJ cs_m_panth,  0,             4210, -1280,   0,  7000,    0, cs_n_panth,  CSO_COLLIDE
    CS_OBJ cs_m_arc,    0,                0,  1700,   0,  5000,    0, cs_n_arc,    CSO_COLLIDE
    CS_OBJ cs_m_arche,  0,            -4300,  3800,   0,  5000,    0, cs_n_def,    CSO_COLLIDE
    CS_OBJ cs_m_def1,   0,            -4000,  3500,   0, 14000,    0, cs_n_def,    CSO_COLLIDE
    CS_OBJ cs_m_def2,   0,            -3800,  3650,   0, 12000,    0, cs_n_def,    CSO_COLLIDE
    CS_OBJ cs_m_def3,   0,            -4100,  3350,   0, 12000,    0, cs_n_def,    CSO_COLLIDE
    CS_OBJ cs_m_def4,   0,            -3700,  3400,   0, 10000,    0, cs_n_def,    CSO_COLLIDE
    CS_OBJ cs_m_hill,   0,             3560,  3150,   0, 12000,    0, cs_n_mont,   0
    CS_OBJ cs_m_sacre,  0,             3560,  3150, 100,  9000,    0, cs_n_sacre,  CSO_COLLIDE
    CS_OBJ cs_m_rive0, cs_m_rive0f,   5033,  -1067,   0,  4500, 2600, cs_n_seine,  0
    CS_OBJ cs_m_rive1, cs_m_rive1f,   2533,    233,   0,  4500, 2600, cs_n_seine,  0
    CS_OBJ cs_m_rivc0, cs_m_rivc0f,    200,    183,   0,  4500, 2600, cs_n_seine,  0
    CS_OBJ cs_m_rivc1, cs_m_rivc1f,  -2067,  -1200,   0,  4500, 2600, cs_n_seine,  0
    CS_OBJ cs_m_rivw0, cs_m_rivw0f,  -4367,  -2100,   0,  4500, 2600, cs_n_seine,  0
    CS_OBJ cs_m_rivw1, cs_m_rivw1f,  -5750,  -1300,   0,  4500, 2600, cs_n_seine,  0
    CS_OBJ cs_m_axis,   0,             -600,  1900,   0,  8000,    0, cs_n_seine,  0
    CS_OBJ cs_m_per0,   0,             5576,  3576,   0,  8000,    0, cs_n_seine,  0
    CS_OBJ cs_m_per1,   0,             5576, -2576,   0,  8000,    0, cs_n_seine,  0
    CS_OBJ cs_m_per2,   0,             -576, -2576,   0,  8000,    0, cs_n_seine,  0
    CS_OBJ cs_m_per3,   0,             -576,  3576,   0,  8000,    0, cs_n_seine,  0
    CS_OBJ cs_m_hangar, 0,            -2750, -2350,   0,  3000,    0, cs_n_bldg,   CSO_COLLIDE
    CS_OBJ cs_m_shed,   0,            -2300, -2750,   0,  3000,    0, cs_n_bldg,   CSO_COLLIDE
    CS_OBJ cs_m_small,  0,            -2900, -2050,   0,  2500,    0, cs_n_bldg,   CSO_COLLIDE
    CS_OBJ cs_m_block,  0,             1000,  1200,   0,  3000,    0, cs_n_bldg,   CSO_COLLIDE
    CS_OBJ cs_m_block2, 0,             1900,   800,   0,  3000,    0, cs_n_bldg,   CSO_COLLIDE
    CS_OBJ cs_m_block,  0,             -900,  -700,   0,  3000,    0, cs_n_bldg,   CSO_COLLIDE
    CS_OBJ cs_m_block2, 0,            -1700,   200,   0,  3000,    0, cs_n_bldg,   CSO_COLLIDE
cs_objend:
CS_NOBJ equ (cs_objend - cs_objtab) / CSO_SIZE

cs_n_eiffel: db 'THE EIFFEL TOWER', 0
cs_n_troc:   db 'THE TROCADERO', 0
cs_n_ecole:  db 'THE ECOLE MILITAIRE', 0
cs_n_inval:  db 'LES INVALIDES', 0
cs_n_montp:  db 'THE MONTPARNASSE TOWER', 0
cs_n_louvre: db 'THE LOUVRE', 0
cs_n_nd:     db 'NOTRE-DAME', 0
cs_n_panth:  db 'THE PANTHEON', 0
cs_n_arc:    db 'THE ARC DE TRIOMPHE', 0
cs_n_def:    db 'LA DEFENSE', 0
cs_n_mont:   db 'MONTMARTRE', 0
cs_n_sacre:  db 'THE SACRE-COEUR', 0
cs_n_seine:  db 'THE SEINE', 0
cs_n_bldg:   db 'A BUILDING', 0
cs_n_ground: db 'THE GROUND', 0

; =============================================================================
; The aeroplanes (SPEC.md 88.7): one row, and every constant the flight model
; reads. Speeds are 16.8 m/s; angles 65536 to the turn; rates are per tick.
; =============================================================================
cs_p_c172:
    dw cs_s_c172                    ; CSP_NAME
    dw 24 * 256                     ; CSP_VSTALL   48 knots
    dw 28 * 256                     ; CSP_VROT     55 knots
    dw 78 * 256                     ; CSP_VMAX    150 knots, level at full power
    dw 31                           ; CSP_THRUST   2.2 m/s^2 at full throttle
    dw 334                          ; CSP_DRAGK    balances THRUST at VMAX
    dw 6                            ; CSP_FRICT    rolling, on the ground
    dw 40                           ; CSP_BRAKE
    dw 546                          ; CSP_ROLLR    3 degrees a tick, held
    dw 146                          ; CSP_ROLLL    0.8 a tick back to level
    dw 146                          ; CSP_PITCHR   0.8 a tick, held
    dw 0                            ; CSP_PITCHT   the nose STAYS where the stick
                                    ;              left it: a trimmed aeroplane
    dw 60                           ; CSP_TURNK    3 degrees a second at 30 of bank
    dw 2                            ; CSP_EYE      metres above the wheels
    dw 10923                        ; CSP_MAXROLL  60 degrees
    dw 7282                         ; CSP_MAXPITCH 40 degrees
cs_s_c172:   db 'CESSNA 172', 0

; =============================================================================
; The airports (SPEC.md 88.6): one row
; =============================================================================
cs_a_issy:
    dw cs_s_issy                    ; CSA_NAME
    dw -2600, -2300                 ; CSA_X, CSA_Z: 3.5 km south-west of the
    dw 0                            ; CSA_ELEV     tower, on the river bend
    dw 7282                         ; CSA_HDG      040
    dw 500                          ; CSA_HLEN     a 1,000 m runway...
    dw 20                           ; CSA_HWID     ...40 m wide
    dw cs_s_rwy04                   ; CSA_RWY
    dw -440                         ; CSA_SPAWN    60 m in from the threshold
cs_s_issy:   db 'PARIS-ISSY', 0
cs_s_rwy04:  db 'RUNWAY 04', 0
