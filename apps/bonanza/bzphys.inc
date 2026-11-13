; bzphys.inc - BONANZA's physics (SPEC.md 128.10.7 as wave 2 changes it,
; 128.11.8; 128.10.8; wave 3's props, 128.12.6): the ball in GROUND units on
; the course part's BZG1 grid, one step a FASTTICK sub-tick.
; tools/bbcourse.py's Physics class is the
; reference and this is integer-exact to it, step for step; SPEC.md 128.11.8.2
; is the binding order both follow.
;
; =============================================================================
; GUEST STATE A HARNESS READS (128.10.7.1, 128.11.5.2, 128.11.8.1; offsets the
; package segment's)
; =============================================================================
;   bz_gx,bz_gy DWORD  the contact point, gu in 24.8: +0 the fraction, +1 the
;                      integer gu as a WORD (0 .. 4,095), +3 zero
;   bz_gz       DWORD  the ball's bottom, px in 24.8, SIGNED: +1 a signed word,
;                      +3 its sign (so the DWORD is the two's complement value)
;   bz_gvx,bz_gvy word 1/256 gu a step;  bz_gvz word 1/256 px a step, up +
;   bz_air      byte   1 while airborne
;   bz_ztop     word   the highest z (px, floor) of this flight
;   bz_lfall    word   the last landing's drop, ztop - h (px, >= 0)
;   bz_lvz      word   the last landing's impact RELATIVE TO THE FLOOR,
;                      max(0, fr - gvz) (128.11.8.5)
;   bz_safe     2 bytes the last SAFE cell stood on: wx, then wy
;   bz_nstep    DWORD  steps since the play began
;   bz_nfall    word   respawns;  bz_nland word landings (every contact)
;   bz_nbnc, bz_nstun, bz_nshat, bz_nhop  words: bounces, stuns, shatters,
;                      Hops this play (128.11.5.2)
;   bz_gh       word   the floor's h4 under an airborne ball over a FLOOR or
;                      GOAL cell; bz_ghv byte 1 when it is valid (128.11.8.1)
;   bz_lvl      4 bytes the arrows' ramp levels 0 .. 8, BZ_K_* order (L R U D)
;   bz_hopw     byte   the Hop's window, steps left
;   bz_mst      byte   0 none, 1 STUNNED, 2 SHATTERING;  bz_mct its steps left
;   bz_sqf      byte   the squash's steps left (128.11.9.3)
;   bz_kprev    byte   the last step's key byte
;   bz_goal     byte   1 once a step ends with the centre on a GOAL cell, in
;                      play or a replay (not the benchmark), grounded or not
;   bz_nwin     2 bytes the window's centre cell: wx, then wy.  A harness that
;                      POKES the ball's position need not touch it: it sets
;                      bz_pokd to 1, and the next step starts by refilling the
;                      window round the ball's cell and clearing bz_pokd
;                      (bz_wgx, bz_wgy are 16 wx, 16 wy, step 4's cell test)
;   bz_pokd     byte   1: the ball was POKED since the last step (the harness's)
;   bz_nbr      36 bytes the 3 x 3 cells round it, row-major by wy then wx,
;                      each the grid's 4 bytes (OPEN outside the grid)
;   bz_sb       word   the ball's cell row s_b = (gx >> 4) + (gy >> 4), whole gu
;                      (the occluder rule's and the idle test's, 128.10.8):
;                      written ONCE A FRAME, by bz_camera, not by the step
;   bz_resp     byte   1 when this FRAME's steps included a respawn (the cut)
;   bz_mat      byte   (bonanza.asm) the material; bz_pinit copies its BZ_MATTAB
;                      record into bz_mrec, and the step reads it there
;
; Wave 3's (SPEC.md 128.12.6.6; bbcourse.Physics's state3, compared at every
; frame by bonanzaphys):
;   bz_ps       byte   bit 0 bz_wol not empty, bit 1 in a tube, bit 2 carried
;   bz_wol      19 bytes the window's OBS cells: a count, then (cell 0 - 8,
;                      prop index) pairs in bz_wrt's order (bytes past the
;                      count's pairs are stale)
;   bz_tube     byte   the tube in transit, its index + 1 (0 none); bz_tseg
;                      byte its segment; bz_tcnt word the steps left in it;
;                      bz_tsin word the entry speed
;   bz_onp      byte   carried by the platform: its index + 1, 0 none
;   bz_pkick    16 words each prop's last kick step (0FFFAh: never)
;   bz_nkick, bz_nknock, bz_ntube words: kicks, knock-backs, captures
; and, the step's own (not the model's): bz_wcen, bz_wckd, bz_wbmp, bz_wkd
; (bz_wolf's centre prop, kinds and bumper count), bz_pcn/pcs/pcv (bz_ppos's
; cache), bz_cdd, bz_pdoor, bz_pdi, bz_fslab, bz_fair, bz_fnl.
;
; The SCREEN state 128.10.8 derives at the end of every step: bz_bx, bz_by
; (24.8, the ball's picture top-left) and bz_vx, bz_vy (how far they moved
; this step, a respawn's 0) - which the camera, the frame and the boxes read
; as they did in wave 0b.
;
; Every comparison of a floor with the ball is made in QUARTER px (the grid's
; h4) against the ball's 24.8 height floored to quarter px - exact, because
; 64 h4 > T  <=>  h4 > floor(T / 64)  for an integer h4 (BZ_Q64).
; =============================================================================

BZ_KVOID    equ 0               ; a cell's kind (the low nibble of byte +2;
BZ_KFLOOR   equ 1               ; the high nibble is its SURFACE, 128.11.6.2)
BZ_KWALL    equ 2
BZ_KGOAL    equ 3
BZ_FSAFE    equ 1               ; flags (byte +3): a respawn cell
BZ_FOCC     equ 2               ; ...the occluder pass may lay a record
BZ_ZOPEN    equ 80h             ; an OPEN cell's z0 (-128)
BZ_ST_STUN  equ 1               ; bz_mst: the hard landing's own number
BZ_ST_SHAT  equ 2               ; (BZM_HARD), stored as it is
BZN_NW      equ 0               ; bz_nbr: the cell (dx, dy) at 4 (3 (dy + 1) + dx + 1)
BZN_N       equ 4
BZN_NE      equ 8
BZN_W       equ 12
BZN_C       equ 16
BZN_E       equ 20
BZN_SW      equ 24
BZN_S       equ 28
BZN_SE      equ 32
%if BZ_GSL != 4 || BZ_CLIMB != 4
 %error "bzphys.inc multiplies by BZ_GSL and BZ_CLIMB * 4 with shifts: re-derive them"
%endif
%if BZ_ST_STUN != BZ_HARD_STUN || BZ_ST_SHAT != BZ_HARD_SHATTER
 %error "bzphys.inc stores BZM_HARD as bz_mst: the two numberings must agree"
%endif
%if BZ_K_L != 1 || BZ_K_R != 2 || BZ_K_U != 4 || BZ_K_D != 8
 %error "bzphys.inc's ramp walks bz_lvl in the key byte's bit order"
%endif

%macro BZ_PHYS_VARS 0
; the state bz_pinit zeroes, BZ_PHSN bytes from bz_phs (words first)
VAR bz_phs,0
VAR bz_gx,4
VAR bz_gy,4
VAR bz_gz,4
VAR bz_gvx,2
VAR bz_gvy,2
VAR bz_gvz,2
VAR bz_ztop,2
VAR bz_lfall,2
VAR bz_lvz,2
VAR bz_nstep,4
VAR bz_nfall,2
VAR bz_nland,2
VAR bz_nbnc,2                   ; wave 2's counters (128.11.5.2): bz_nshat
VAR bz_nstun,2                  ; MUST follow bz_nstun (bz_step's .hard)
VAR bz_nshat,2
VAR bz_nhop,2
VAR bz_pkick,2 * BZ_PROPMAX     ; wave 3 (SPEC.md 128.12.6.6): each prop's last
                                ; kick step (a bumper's), 0FFFAh at the start;
                                ; the post's LIT time is the display's (frames
                                ; on the glass, bzwheel.inc's bz_lhold,
                                ; 128.12.6.3) and physics never reads it
VAR bz_gh,2
VAR bz_sb,2
VAR bz_air,1
VAR bz_goal,1
VAR bz_resp,1
VAR bz_pokd,1                   ; a harness sets it after POKING the ball (the
                                ; next step refills the window, then clears it)
VAR bz_lvl,4                    ; a RESPAWN zeroes bz_lvl .. bz_ghv, 9 bytes
VAR bz_hopw,1                   ; (bz_step's .respawn writes them as words:
VAR bz_mst,1                    ; keep the order)
VAR bz_mct,1
VAR bz_sqf,1
VAR bz_ghv,1
VAR bz_kprev,1
VAR bz_tcnt,2                   ; wave 3's state (SPEC.md 128.12.6.6): the steps
VAR bz_tsin,2                   ; left in the tube's segment, the entry speed,
VAR bz_nkick,2                  ; and the kicks, knock-backs and captures this
VAR bz_nknock,2                 ; play
VAR bz_ntube,2
VAR bz_pcv,2                    ; bz_ppos's cache: the last (record, n) it
VAR bz_pcs,2                    ; answered and its pos (a pure function of the
VAR bz_pcn,2                    ; two; 0: none)
VAR bz_wol,19                   ; the window's OBS cells, a count and nine
                                ; (cell 0 - 8, prop index) pairs (128.12.3.2)
VAR bz_ps,1                     ; ...bit 0 bz_wol not empty, 1 in a tube, 2 carried
VAR bz_tube,1                   ; ...the tube in transit: index + 1, 0 none
VAR bz_tseg,1                   ; ...its segment
VAR bz_onp,1                    ; ...carried by the platform: its index + 1, 0 none
VAR bz_wcen,1                   ; bz_wolf's own: the centre cell's prop (index +
VAR bz_wckd,1                   ; 1, 0 none) and its kind, the bumpers on bz_wol,
VAR bz_wbmp,1                   ; and each pair's prop's kind - read by the step
VAR bz_wkd,9                    ; instead of the records (not the model's state)
VAR bz_ppad,1
VAR bz_phe,0
; the rest: written before they are read
VAR bz_mrec,BZ_MATREC           ; the material's BZ_MATTAB record (bz_pinit)
VAR bz_se,BZ_SURFREC            ; BZ_SURFTAB's entry for it on the centre's
                                ; surface: force, drag shift, brake, floor e
VAR bz_surf,1                   ; ...that surface (0FFh: none yet, bz_pinit)
VAR bz_kstep,1                  ; this step's key byte
VAR bz_ftg,BZ_LVLMAX + 1        ; the arrows' force a level, ground and air
VAR bz_fta,BZ_LVLMAX + 1        ; (128.11.7.1)
VAR bz_safe,2                   ; wx, wy
VAR bz_nwin,2                   ; wx, wy
VAR bz_wgx,2                    ; 16 wx, 16 wy of the window's centre (the cell test)
VAR bz_wgy,2
VAR bz_sgx,4                    ; the step's START ground position (step 3; z
VAR bz_sgy,4                    ; is put back by its gvz)
VAR bz_zq,2                     ; floor(start z / 64) quarter px, + 16 (the climb)
VAR bz_tsx,2                    ; step 2's slopes of C, signed
VAR bz_tsy,2
VAR bz_fr,2                     ; bz_fill's grid row r; its copies of NROWS, KW,
VAR bz_fnr,2                    ; ROWTAB; the centre's k and the rows s +- 1's
VAR bz_fkw,2                    ; first k
VAR bz_frt,2
VAR bz_fka,2
VAR bz_fdp,2
VAR bz_kx,4                     ; (X0 - 8) << 8 and (Y0 - 13) << 8, 24.8: the
VAR bz_ky,4                     ; projection's constants (bz_crshdr)
VAR bz_nbr,36
; the idle test's last frame (bz_mkboxes, 128.10.8 item 2)
VAR bz_osb,2
VAR bz_ozb,2
VAR bz_oair,1
VAR bz_fin,1                    ; 1: the last play reached the goal (the face)
VAR bz_disc,1                   ; 1: this frame is a centred full write (its
                                ; elapsed sub-ticks are discarded, 128.10.8 item 3)
VAR bz_wch,1                    ; step 4: bit 0 the cell's wx changed, bit 1 wy
VAR bz_nprop,1                  ; wave 3: NPROP (bz_pinit; 16 at most) ...
VAR bz_pdoor,1                  ; ...the step's path, 0 wave 2's, and on the prop
VAR bz_pdi,1                    ; path the centre's doorway: 1 none, 2 along -x,
                                ; 3 along -y; and its windmill;
VAR bz_fslab,1                  ; step 6's slab (index + 1, 0 none), the air
VAR bz_fair,1                   ; state step 6 began with
VAR bz_fnl,2                    ; ...and bz_nland then
VAR bz_cdd,2                    ; the carry's displacement this step, 1/256 gu
%if (bz_phe - bz_phs) & 1
 %error "bz_pinit zeroes the state as words: BZ_PHSN must be even"
%endif
%if bz_nshat != bz_nstun + 2 || bz_mst != bz_hopw + 1 || bz_mct != bz_hopw + 2 || bz_sqf != bz_hopw + 3 || bz_ghv != bz_hopw + 4
 %error "bz_land and bz_step's .respawn rely on the order of their variables"
%endif
%endmacro
BZ_PHSN     equ bz_phe - bz_phs

; -----------------------------------------------------------------------------
; bz_pinit - the ball at the course's start (SPEC.md 128.10.7.1, 128.11.5.2):
; the start tile's centre on its floor, at rest, grounded, the window filled,
; every counter and wave 2's state zero, the material's record copied from
; BZ_MATTAB ([bz_mat]) with its air force table, the ground's built for the
; start's surface by bz_fill, and the screen state derived with a zero
; velocity.  DS = ours, [bz_cseg] the course, bz_crshdr run.  Preserves
; nothing.
; -----------------------------------------------------------------------------
bz_pinit:
    push ds
    pop es
    xor ax, ax
    mov di, bz_phs
    mov cx, BZ_PHSN / 2
    rep stosw
    mov ax, 0fffah              ; every post starts dark: its last kick -6
    mov di, bz_pkick            ; (bbcourse.Physics's pkick)
    mov cx, BZ_PROPMAX
    rep stosw
    mov al, [bz_mat]            ; the material's record (the step reads it
    mov ah, BZ_MATREC           ; there, not as immediates)
    mul ah
    add ax, bz_mattab
    xchg ax, si
    mov di, bz_mrec
    mov cx, BZ_MATREC / 2
    rep movsw
    mov al, [bz_mrec + BZM_ACC] ; fta[l] = (ACC l + 4) >> 4: half the ramp
    mov di, bz_fta
    mov cl, 4
    call bz_ramp
    mov byte [bz_surf], 0ffh    ; bz_place's fill builds ftg for the start's
    mov es, [bz_cseg]
    mov ax, [es:BZC_PROPOFF]    ; the prop table, which every window refill
    mov [bz_poff], ax           ; scans for its OBS cells' owners (bz_wolf;
    mov al, [es:BZC_NPROP]      ; bz_pread reads it again for the lanes)
    mov [bz_nprop], al
    mov di, [bz_goff]
    mov al, [es:di + BZG_WX]
    mov ah, [es:di + BZG_WY]
    mov [bz_safe], ax           ; the start is SAFE (128.10.4.5)
    call bz_place
    call bz_derive
    xor ax, ax
    mov [bz_vx], ax
    mov [bz_vy], ax
    ret

; bz_ramp - a force table (128.11.7.1): [DI + l] = (AL l + 4) >> CL for the
; levels l = 0 .. BZ_LVLMAX (CL = 3 the ground's, 4 the air's).  DS = ours.
; Clobbers AX, BX, CH, DX, DI.
bz_ramp:
    cbw
    mov dx, 4
    mov ch, BZ_LVLMAX + 1
.l:
    mov bx, dx
    shr bx, cl
    mov [di], bl
    inc di
    add dx, ax
    dec ch
    jnz .l
    ret

; BZ_Q64: DX:AX (signed, 24.8) -> AX = floor(DX:AX / 64), when that fits a
; word: (DX:AX >> 8) << 2 from DL:AH, and the fraction's top two bits.
; Clobbers DX.
%macro BZ_Q64 0
    mov dh, dl
    mov dl, ah                  ; DX = DX:AX >> 8
    shl dx, 1
    shl dx, 1
    rol al, 1
    rol al, 1
    and ax, 3
    or ax, dx
%endmacro

; -----------------------------------------------------------------------------
; bz_step's steps 4 - 6 are written ONCE and run by both paths (SPEC.md
; 128.13.8): wave 2's (no prop in the window) and the PROP path (128.12.6.5),
; told apart by bz_pdoor - 0 on wave 2's path, written at step 4 every step
; that reaches it, and 1 - 3 on the prop path (no doorway, the doorway along
; -x, along -y).  The prop path's own parts sit where they hook in - its
; prefix (the START, the doorway, a drain's capture), the posts and the
; window after the walls, the floor's prop cells, bz_onp - each behind a test
; of bz_pdoor that wave 2's path jumps on and the prop path falls through;
; the doorway's own branch is out of line (bz_step.wdoor, .ndoor).  A ball
; with no prop near pays those four tests (about 133 clk raw a step, 128.13.8)
; and nothing else, and the two paths cannot drift apart.
; -----------------------------------------------------------------------------
; BZ_START: the step's START ground position, for the fallback's undo, from
; the moved one (gx - gvx, gy - gvy).  Clobbers AX, DX.
%macro BZ_START 0
    mov ax, [bz_gvx]
    cwd
    neg dx
    neg ax
    sbb dx, 0
    add ax, [bz_gx]
    adc dx, [bz_gx + 2]
    mov [bz_sgx], ax
    mov [bz_sgx + 2], dx
    mov ax, [bz_gvy]
    cwd
    neg dx
    neg ax
    sbb dx, 0
    add ax, [bz_gy]
    adc dx, [bz_gy + 2]
    mov [bz_sgy], ax
    mov [bz_sgy + 2], dx
%endmacro

; -----------------------------------------------------------------------------
; bz_step - ONE STEP, in SPEC.md 128.11.8.2's binding order (the numbers below
; are its steps).  DS = ours.  Preserves CX and ES (the frame loop's count and
; segment) and nothing else.
; -----------------------------------------------------------------------------
bz_step:
    push cx
    push es
    mov es, [bz_cseg]
    cmp byte [bz_pokd], 0       ; C: the centre's cell.  The window is centred
    jne .poked                  ; on it already unless a harness POKED the ball
.unpoked:                       ; and said so (bz_pokd: the hot path pays one
                                ; byte test, not the cell compares)
    ; ---- 1. the keys, whatever the ball's state: the key byte K ----
    mov al, [bz_mode]
    cmp al, 1
    je .auto
    ja .replay
    mov bl, [bz_keys]           ; PLAY: the frame's (bz_input), RECORDED - the
    cmp bl, [bz_rk]             ; current run extended while it is the same
    jne .rec                    ; byte and under 255 steps (SPEC.md
    cmp byte [bz_rn], 255       ; 128.11.12.1), else bz_rrec
    jae .rec
    inc byte [bz_rn]
    jmp short .key
.rec:
    call bz_rrec
    jmp short .key
.replay:
    call bz_rnext               ; a REPLAY: the log's next byte
    jmp short .key
.auto:
    call bz_auto                ; the benchmark: BL = the arrows it would hold
.key:
    mov [bz_kstep], bl
    mov si, bz_lvl              ; the ramp (128.11.7.1): a held arrow's level
    mov bh, bl                  ; up one to 8, a released one's down two to 0
    mov cx, 4
.lv:
    lodsb
    shr bh, 1
    jnc .rel
    cmp al, BZ_LVLMAX
    jae .lvs
    inc ax
    jmp short .lvs
.rel:
    sub al, 2
    jnc .lvs
    xor al, al
.lvs:
    mov [si - 1], al
    loop .lv
    mov al, bl                  ; the Hop's window: Space's key-down EDGE opens
    xchg al, [bz_kprev]         ; it, else it counts down (128.11.7.2)
    not al
    and al, bl
    test al, BZ_K_HOP
    jz .hw
    mov byte [bz_hopw], BZ_HOPWIN
    jmp short .st
.hw:
    cmp byte [bz_hopw], 0
    je .st
    dec byte [bz_hopw]
.st:                            ; ...then the ball's state
    cmp byte [bz_sqf], 0
    je .sq
    dec byte [bz_sqf]
.sq:
    mov al, [bz_mst]
    or al, al
    jz .forces
    dec byte [bz_mct]
    jnz .mlive
    mov byte [bz_mst], 0        ; its time is up: none (a stun's end) ...
    cmp al, BZ_ST_SHAT
    jne .forces
    jmp .respawn                ; ...or the shattered ball's RESPAWN
.mlive:
    cmp al, BZ_ST_SHAT          ; a shattering ball does not move
    jne .forces
    jmp .end
.ptr1:                          ; (the short jump's reach)
    jmp .pst
    ; ---- 2. forces ----
.forces:
    test byte [bz_ps], 6        ; wave 3 (SPEC.md 128.12.6.5 step 1): in a tube,
    jnz .ptr1                   ; or carried by the platform
.forces2:
    xor di, di                  ; DI, BP = the arrows on (gvx, gvy), each at its
    xor bp, bp                  ; level, pushed along the screen through the
    cmp byte [bz_mst], 0        ; ground (128.10.7.2); none while stunned
    jne .pushed
    mov dl, bl
    mov bx, bz_ftg              ; the ground's force a level, or the air's
    cmp byte [bz_air], 0
    je .k0
    mov bx, bz_fta
.k0:
    test dl, BZ_K_R
    jz .k1
    mov al, [bz_lvl + 1]
    xlat
    cbw
    add di, ax                  ; Right (+F, -F)
    sub bp, ax
.k1:
    test dl, BZ_K_L
    jz .k2
    mov al, [bz_lvl + 0]
    xlat
    cbw
    sub di, ax                  ; Left (-F, +F)
    add bp, ax
.k2:
    test dl, BZ_K_D
    jz .k3
    mov al, [bz_lvl + 3]
    xlat
    cbw
    add di, ax                  ; Down (+F, +F)
    add bp, ax
.k3:
    test dl, BZ_K_U
    jz .pushed
    mov al, [bz_lvl + 2]
    xlat
    cbw
    sub di, ax                  ; Up (-F, -F)
    sub bp, ax
.pushed:
    cmp byte [bz_air], 0
    jne .air
    mov cx, [bz_se + 1]         ; CL = the surface's drag shift (0 none), CH =
    test byte [bz_kstep], BZ_K_GRIP ; its brake, while Grip is held and the
    jz .nogrip                  ; ball is not stunned
    cmp byte [bz_mst], 0
    je .grip
.nogrip:
    xor ch, ch
.grip:
    mov ax, [bz_tsx]            ; gvx += arrows - BZ_GSL sx; drag; brake; clamp
    shl ax, 1                   ; (C's slopes: bz_win9f's, 0 off a plane floor)
    shl ax, 1
    neg ax
    add ax, di
    add ax, [bz_gvx]
    call bz_gax
    mov [bz_gvx], ax
    mov ax, [bz_tsy]            ; gvy the same with sy
    shl ax, 1
    shl ax, 1
    neg ax
    add ax, bp
    add ax, [bz_gvy]
    call bz_gax
    mov [bz_gvy], ax
    call bz_frate               ; gvz: the floor's own rate under the ball
    mov [bz_gvz], ax
    jmp short .move
.air:
    xor cx, cx                  ; airborne: the arrows at half force, clamped
    mov ax, [bz_gvx]            ; (128.11.7.3); no slope, no drag
    add ax, di
    call bz_gax
    mov [bz_gvx], ax
    mov ax, [bz_gvy]
    add ax, bp
    call bz_gax
    mov [bz_gvy], ax
    mov ax, [bz_gvz]            ; gravity, clamped
    sub ax, BZ_G
    cmp ax, BZ_VZMAX
    jle .g1
    mov ax, BZ_VZMAX
.g1:
    cmp ax, -BZ_VZMAX
    jge .g2
    mov ax, -BZ_VZMAX
.g2:
    mov [bz_gvz], ax
    ; ---- 3. move ----
.move:
    mov ax, [bz_gz]             ; zq = floor(start z / 64) quarter px, plus the
    mov dx, [bz_gz + 2]         ; climb in either air state: a neighbour BLOCKS
    BZ_Q64                      ; when its h4 > zq (128.11.8.2 step 5)
    add ax, BZ_CLIMB * 4        ; (+ 1,024 / 64)
    mov [bz_zq], ax
    mov ax, [bz_gvx]            ; gx += gvx, gy += gvy (the start is kept only
    cwd                         ; when the cell changes, below)
    add [bz_gx], ax
    adc [bz_gx + 2], dx
    mov ax, [bz_gvy]
    cwd
    add [bz_gy], ax
    adc [bz_gy + 2], dx
    cmp byte [bz_air], 0        ; airborne: z += gvz (an undo takes it back)
    je .win
    mov ax, [bz_gvz]
    cwd
    add [bz_gz], ax
    adc [bz_gz + 2], dx
    mov ax, [bz_gz + 1]         ; ztop = max(ztop, z) in whole px
    cmp ax, [bz_ztop]
    jle .win
    mov [bz_ztop], ax
    ; ---- 4. the window ----
.win:
    xor cx, cx                  ; CL: bit 0 the cell's wx changed, bit 1 its
    mov ax, [bz_gx + 1]         ; wy (the window is on the START's cell)
    and al, 0f0h
    cmp ax, [bz_wgx]
    je .w1
    inc cx
.w1:
    mov ax, [bz_gy + 1]
    and al, 0f0h
    cmp ax, [bz_wgy]
    je .w2
    or cl, 2
.w2:
    mov [bz_wch], cl
    jcxz .w3
    BZ_START                    ; a new cell: the START's ground position kept
                                ; for the fallback's undo (gx - gvx: only the
                                ; move has touched it yet)
    call bz_win9f               ; the centre's new cell
.w3:
    mov si, bz_nbr + BZN_C
    test byte [si + 2], 0fh
    jnz .w4
    cmp byte [si], BZ_ZOPEN
    jne .w4
    jmp .respawn                ; an OPEN cell (or outside the grid)
.w4:
    mov al, [bz_ps]             ; wave 3 (128.12.6.5 step 4): an OBS cell in the
    and al, 5                   ; window, or carried - the PROP path, which sets
    mov [bz_pdoor], al          ; bz_pdoor 1 - 3 here; else 0: wave 2's steps
    jz .walls                   ; 4 - 6, bz_pdoor 0 throughout
    cmp byte [bz_wch], 0        ; the START for the fallback's undo, which
    jne .pst0                   ; wave 2 keeps only on a cell change (a post's
    BZ_START                    ; push can change it here) ...
.pst0:                          ; (the lift's carry moves z alone, which the
                                ; start does not keep: the undo takes it back)
    mov byte [bz_pdoor], 1      ; the centre's cell's prop (bz_wol's cell 4):
    mov ax, [bz_wcen]           ; a plain tube's IN, the capture test (step 4);
    dec al                      ; a windmill's IN, its doorway (step 5)
    js .walls
    mov bl, al
    xor bh, bh
    cmp ah, BZ_PK_WINDMILL
    jne .ptube
    call bz_lrecsi
    mov [bz_pdi], al
    mov al, [es:si + BZP_TGVX]  ; 0 -x, 1 -y: bz_pdoor 2 or 3
    add al, 2
    mov [bz_pdoor], al
    jmp short .walls
.ptube:
    cmp ah, BZ_PK_TUBE
    jne .walls
    push bx                     ; a DRAIN: grounded, or airborne with z at
    cmp byte [bz_air], 0        ; most IN's floor + BZ_CLIMB at the centre's
    je .pcap                    ; point (128.12.6.1)
    call bz_ztouch
    jc .pcap
    pop bx
    jmp short .walls
.pcap:
    pop bx
    call bz_capture
    jmp .end
.walls:
    ; ---- 5. walls: the circle, the edge test SYMMETRIC (128.11.8.3), every
    ; zeroing a REFLECTION (128.11.8.4); the prop path adds the windmill's
    ; doorway on the -x and -y edges (128.12.6.2) ----
    mov dh, [bz_gy + 1]         ; DL = u, DH = v: integer gu inside C, BP their
    and dh, 15                  ; copy for the y edges (u is the one before
    mov ax, [bz_gx]             ; the x push, as the model)
    and ah, 15                  ; AX = pu, the in-cell x in 1/256 gu
    mov dl, ah
    mov bp, dx
    cmp ax, BZ_RAD * 256
    jae .xe
    mov si, bz_nbr + BZN_W      ; west, at its point (16, v)
    mov dl, 16
    call bz_blocks
    jnc .y
    cmp byte [bz_pdoor], 2      ; a windmill's DOORWAY along -x (128.12.6.2)
    je .trwd
.wwall:
    mov ax, [bz_gx + 1]
    and al, 0f0h
    add al, BZ_RAD              ; the centre BZ_RAD from the edge, no fraction
    mov [bz_gx + 1], ax
    mov byte [bz_gx], 0
    mov ax, [bz_gvx]            ; into the wall: reflected
    or ax, ax
    jns .y
    call bz_wrefl
    mov [bz_gvx], ax
    jmp short .y
.trwd:                          ; (the short jump's reach)
    jmp .wdoor
.xe:
    cmp ax, (16 - BZ_RAD) * 256 ; east when pu > 2,560: a true distance under
    jbe .y                      ; 6 gu, as west (P1)
    mov si, bz_nbr + BZN_E      ; east, at (0, v)
    mov dl, 0
    call bz_blocks
    jnc .y
    mov ax, [bz_gx + 1]
    and al, 0f0h
    add al, 16 - BZ_RAD
    mov [bz_gx + 1], ax
    mov byte [bz_gx], 0
    mov ax, [bz_gvx]
    or ax, ax
    jle .y
    call bz_wrefl
    mov [bz_gvx], ax
.y:
    mov dx, bp
    mov ax, [bz_gy]
    and ah, 15                  ; AX = pv
    cmp ax, BZ_RAD * 256
    jae .ye
    mov si, bz_nbr + BZN_N      ; north, at (u, 16)
    mov dh, 16
    call bz_blocks
    jnc .corner
    cmp byte [bz_pdoor], 3      ; ...along -y
    je .trnd
.nwall:
    mov ax, [bz_gy + 1]
    and al, 0f0h
    add al, BZ_RAD
    mov [bz_gy + 1], ax
    mov byte [bz_gy], 0
    mov ax, [bz_gvy]
    or ax, ax
    jns .corner
    call bz_wrefl
    mov [bz_gvy], ax
    jmp short .corner
.trnd:
    jmp .ndoor
.ye:
    cmp ax, (16 - BZ_RAD) * 256
    jbe .corner
    mov si, bz_nbr + BZN_S      ; south, at (u, 0)
    mov dh, 0
    call bz_blocks
    jnc .corner
    mov ax, [bz_gy + 1]
    and al, 0f0h
    add al, 16 - BZ_RAD
    mov [bz_gy + 1], ax
    mov byte [bz_gy], 0
    mov ax, [bz_gvy]
    or ax, ax
    jle .corner
    call bz_wrefl
    mov [bz_gvy], ax
.corner:
    mov ax, [bz_gx]             ; the corner: only within BZ_RAD of both a
    and ah, 15                  ; west or east edge and a north or south one
    sub ax, BZ_RAD * 256        ; (pu, pv outside 1,536 .. 2,560)
    cmp ax, (16 - 2 * BZ_RAD) * 256
    jbe .nocorner
    mov ax, [bz_gy]
    and ah, 15
    sub ax, BZ_RAD * 256
    cmp ax, (16 - 2 * BZ_RAD) * 256
    jbe .nocorner
    call bz_corner
.nocorner:
    cmp byte [bz_pdoor], 0      ; the prop path: the posts, the window and
    je .fb                      ; the cell change again, then the fallback
    call bz_posts               ; each post on bz_wol: the circle (128.12.6.3)
    mov ax, [bz_gx + 1]         ; a push into another cell: the window
    and al, 0f0h                ; refilled before the fallback judges it
    cmp ax, [bz_wgx]
    jne .pmv
    mov ax, [bz_gy + 1]
    and al, 0f0h
    cmp ax, [bz_wgy]
    je .pfb
.pmv:
    call bz_win9f
.pfb:
    xor cl, cl                  ; the fallback's cell change is against the
    mov ax, [bz_gx + 1]         ; START's cell
    xor ax, [bz_sgx + 1]
    and al, 0f0h
    jz .pf1
    inc cx
.pf1:
    mov ax, [bz_gy + 1]
    xor ax, [bz_sgy + 1]
    and al, 0f0h
    jz .pf2
    or cl, 2
.pf2:
    mov [bz_wch], cl
.fb:
    ; the fallback: the centre in a new cell that blocks is not entered.
    ; (Step 5 never moves the centre's cell: the window is still on it.)
    mov cl, [bz_wch]
    or cl, cl
    jz .floor
    mov si, bz_nbr + BZN_C
    mov dl, [bz_gx + 1]
    and dl, 15
    mov dh, [bz_gy + 1]
    and dh, 15
    mov bp, cx
    call bz_blocks
    jnc .floor
    test bp, 1                  ; each velocity whose cell coordinate changed,
    jz .ux                      ; reflected off C
    mov ax, [bz_gvx]
    call bz_wrefl
    mov [bz_gvx], ax
.ux:
    test bp, 2
    jz .uy
    mov ax, [bz_gvy]
    call bz_wrefl
    mov [bz_gvy], ax
.uy:
    mov ax, [bz_sgx]            ; undo the move: x and y back, and z (gvz is
    mov [bz_gx], ax             ; as the move found it)
    mov ax, [bz_sgx + 2]
    mov [bz_gx + 2], ax
    mov ax, [bz_sgy]
    mov [bz_gy], ax
    mov ax, [bz_sgy + 2]
    mov [bz_gy + 2], ax
    cmp byte [bz_air], 0
    je .unz
    mov ax, [bz_gvz]
    cwd
    sub [bz_gz], ax
    sbb [bz_gz + 2], dx
.unz:
    call bz_win9f               ; the window round the start's cell again
    cmp byte [bz_onp], 0        ; the undo takes the lift's CARRY back too: z
    je .floor                   ; to the step's start (the model's sgz; never
    mov ax, [bz_cdd]            ; on wave 2's path, bz_onp 0 there)
    cwd
    sub [bz_gz], ax
    sbb [bz_gz + 2], dx
    ; ---- 6. the floor (128.11.8.2, 128.11.8.5, 128.11.8.6): the prop path
    ; first finds a post cell's top or the slab's (after .floor, then .psolid with
    ; BX = that h4), and sets bz_onp after it (.ponp) ----
.floor:
    cmp byte [bz_pdoor], 0
    je .floorh
    mov al, [bz_air]            ; the prop path: a post cell's top, the slab's -
    mov [bz_fair], al           ; (what it began with, for that)
    mov ax, [bz_nland]
    mov [bz_fnl], ax
    mov byte [bz_fslab], 0
    mov ax, [bz_wcen]           ; (bz_wolf's: the centre's prop and its kind)
    dec al
    js .floorh
    mov bl, al
    xor bh, bh
    call bz_lrecsi
    cmp ah, BZ_PK_BUMPER
    je .pfpost
    cmp ah, BZ_PK_PLATFORM
    jne .floorh
    push bx                     ; the lift's SHAFT: the SLAB's top at n + 1
    call bz_slabon              ; when the ball began at or over it less
    pop ax                      ; BZ_CLIMB (128.12.6.4); else the shaft's
    jnc .floorh                ; NEAR VOID
    inc ax
    mov [bz_fslab], al
    jmp .psolid
.pfpost:
    call bz_ptop                ; a post cell: the post's top within 6 gu of
    jmp .psolid                 ; it (128.12.6.3)
.floorh:
    mov si, bz_nbr + BZN_C
    mov al, [si + 2]
    and al, 0fh
    cmp al, BZ_KFLOOR
    je .solid
    cmp al, BZ_KGOAL
    je .solid
    mov byte [bz_ghv], 0        ; no floor under it: no shadow
    cmp byte [bz_air], 0
    je .takeoff                 ; grounded over no floor: off it goes
    or al, al
    jnz .fnext                  ; (no other kind is under an airborne ball)
    mov al, [si]                ; VOID: below its kill height, 4 z0 px?
    cbw
    shl ax, 1
    shl ax, 1
    cmp [bz_gz + 1], ax
    jge .fnext
    jmp .respawn
.solid:
    mov dl, [bz_gx + 1]
    and dl, 15
    mov dh, [bz_gy + 1]
    and dh, 15
    call bz_h4
    mov bx, ax                  ; BX = h4, the floor under the centre
.psolid:
    cmp byte [bz_air], 0
    jne .airsolid
    cmp byte [bz_hopw], 0       ; the Hop from the ground (128.11.8.6): the
    je .follow                  ; window open, not stunned, on a FLOOR or GOAL
    cmp byte [bz_mst], 0
    jne .follow
    mov ax, [bz_gvz]            ; gvz = the floor's rate + HOP, at most
    add ax, [bz_mrec + BZM_HOP] ; BZ_VZMAX
    cmp ax, BZ_VZMAX
    jle .hg
    mov ax, BZ_VZMAX
.hg:
    mov [bz_gvz], ax
    mov byte [bz_hopw], 0
    inc word [bz_nhop]
    jmp short .launch
.follow:
    ; grounded: off when h < z + gvz - BZ_G - BZ_STICK, i.e. when
    ; h4 <= floor((z + gvz - BZ_G - 256 BZ_STICK - 1) / 64)
    mov ax, [bz_gvz]
    cwd
    add ax, [bz_gz]
    adc dx, [bz_gz + 2]
    sub ax, BZ_G + 256 * BZ_STICK + 1
    sbb dx, 0
    BZ_Q64
    cmp bx, ax
    jle .launch
    mov ax, bx                  ; z = h: the ball follows the floor
    call bz_setz
    jmp short .gh
.takeoff:                       ; over no floor: no bz_gh (bz_ghv cleared)
    call bz_toff
    jmp short .fnext
.launch:
    call bz_toff
    jmp short .gh
.airsolid:
    ; airborne: LAND when z <= h, i.e. when h4 > floor((z - 1) / 64)
    mov ax, [bz_gz]
    mov dx, [bz_gz + 2]
    sub ax, 1
    sbb dx, 0
    BZ_Q64
    cmp bx, ax
    jle .gh
    call bz_land
.gh:                            ; bz_gh, bz_ghv: the floor under an airborne
    mov al, [bz_air]            ; ball over a FLOOR or GOAL (BX = its h4; not
    mov [bz_ghv], al            ; reached over no floor, which cleared it)
    or al, al
    jz .fnext
    mov [bz_gh], bx
.fnext:
    cmp byte [bz_pdoor], 0      ; the prop path: bz_onp, then bz_ps
    je .safe
.ponp:                          ; bz_onp (128.12.6.4): SET grounded on, or
    mov al, [bz_fslab]          ; landed on (a bounce too), the slab ...
    or al, al
    jz .pkeep
    cmp byte [bz_fair], 0
    jne .pland
    cmp byte [bz_air], 0        ; (grounded: it followed the slab's top, no Hop
    je .pset                    ; and no take-off)
    jmp short .pkeep
.pland:
    mov dx, [bz_nland]
    cmp dx, [bz_fnl]
    je .pkeep
.pset:
    mov [bz_onp], al
    jmp short .pps
.pkeep:                         ; ...KEPT airborne over its slab - the centre
    cmp byte [bz_onp], 0        ; in its SHAFT (one lift a window, so the
    je .pps                     ; centre's prop is it) ...
    cmp byte [bz_air], 0
    je .pclr
    cmp byte [bz_wcen + 1], BZ_PK_PLATFORM
    je .pps
.pclr:                          ; ...CLEARED otherwise
    mov byte [bz_onp], 0
.pps:
    call bz_psync
    ; ---- 8. SAFE and the goal: not shattering ----
.safe:
    cmp byte [bz_mst], BZ_ST_SHAT
    je .end
    mov si, bz_nbr + BZN_C
    cmp byte [bz_air], 0        ; SAFE: grounded only
    jne .goal
    test byte [si + 3], BZ_FSAFE
    jz .goal
    mov ax, [bz_nwin]
    mov [bz_safe], ax
.goal:
    mov al, [si + 2]            ; the goal: grounded OR AIRBORNE, a finish
    and al, 0fh                 ; line (128.11.8.2 step 8)
    cmp al, BZ_KGOAL
    jne .end
    cmp byte [bz_mode], 1       ; play or a replay: the benchmark ignores it
    je .end
    mov byte [bz_goal], 1
    ; ---- 9. the step counted, the screen state derived ----
.end:
    call bz_derive
.count:
    inc word [bz_nstep]
    jnz .counted
    inc word [bz_nstep + 2]
.counted:
    pop es
    pop cx
    ret
.poked:                         ; (out of the hot path) a harness's POKE: the
    mov byte [bz_pokd], 0       ; window round the ball's cell, whatever it was
    call bz_win9f
    jmp .unpoked
    ; ---- 7. RESPAWN, on the last SAFE cell ----
.respawn:
    xor ax, ax                  ; wave 2's state zeroed (128.11.8.1): the
    mov [bz_lvl], ax            ; levels, the window, the ball's state, the
    mov [bz_lvl + 2], ax        ; squash and bz_ghv
    mov [bz_hopw], ax
    mov [bz_mct], ax
    mov [bz_ghv], al
    call bz_place
    inc word [bz_nfall]
    mov byte [bz_resp], 1
    call bz_derive
    xor ax, ax                  ; a respawn's screen velocity is 0
    mov [bz_vx], ax
    mov [bz_vy], ax
    jmp .count
    ; ---- wave 3 (SPEC.md 128.12.6.5): the steps a prop changes, out of the
    ; hot path ----
.pst:                           ; step 1 (bz_ps bits 1 - 2): in a TUBE, the
    cmp byte [bz_tube], 0       ; transit instead of the step (128.12.6.1) ...
    jne .transit
    push bx                     ; ...else CARRIED: the slab's displacement,
    call bz_carry               ; step 3's first move, made here - the forces
    pop bx                      ; read nothing of the position (128.12.6.4)
    jmp .forces2
.transit:
    call bz_transit
    jmp .end
.pdcap:                         ; the doorway open: swallowed
    mov bl, [bz_pdi]
    call bz_capture
    jmp .end
.wdoor:                         ; the ball's circle touches the doorway: low
    mov dx, bp                  ; enough (z <= IN's floor + BZ_CLIMB at its
    call bz_ztouchp             ; point, u before the push) ...
    mov si, bz_nbr + BZN_W
    jc .wd1
    jmp .wwall
.wd1:
    call bz_gate                ; ...the gate at the step's n: OPEN swallows
    jc .pdcap                   ; it, CLOSED knocks it back with eG
    mov ax, [bz_gx + 1]
    and al, 0f0h
    add al, BZ_RAD
    mov [bz_gx + 1], ax
    mov byte [bz_gx], 0
    mov ax, [bz_gvx]
    or ax, ax
    jns .wy
    call bz_refl
    mov [bz_gvx], ax
    inc word [bz_nknock]
.wy:
    jmp .y
.ndoor:
    mov dx, bp
    call bz_ztouchp
    mov si, bz_nbr + BZN_N
    jc .nd1
    jmp .nwall
.nd1:
    call bz_gate
    jc .pdcap
    mov ax, [bz_gy + 1]
    and al, 0f0h
    add al, BZ_RAD
    mov [bz_gy + 1], ax
    mov byte [bz_gy], 0
    mov ax, [bz_gvy]
    or ax, ax
    jns .ny
    call bz_refl
    mov [bz_gvy], ax
    inc word [bz_nknock]
.ny:
    jmp .corner

; -----------------------------------------------------------------------------
; bz_land - step 6's LAND (SPEC.md 128.11.8.5): an airborne ball meets C's
; floor (BX = its h4 under the centre, SI = C).  The impact is judged RELATIVE
; TO THE FLOOR: fr = (sx gvx + sy gvy) >> 2, lvz = max(0, fr - gvz), and the
; rebound r = (e min(lvz, -gvz)) >> 8, e the surface's floor restitution for
; the material (bz_se).  Then, in order: a STUN or a SHATTER (not on a mat);
; a Hop at the contact (the window open, not stunned) leaving at
; max(HOP, r if r >= BMIN else 0) + min(fr, 0); a BOUNCE (r >= BMIN, Grip not
; held) at r + min(fr, 0); else it lands.  A landing at lvz >= BZ_SQTHR
; squashes, but a shatter.  DS = ours.  Preserves BX and SI.
; Clobbers AX, CX, DX, DI, BP.
; -----------------------------------------------------------------------------
bz_land:
    push bx
    call bz_frate               ; AX = fr, the floor's own rate (C's slopes)
    pop bx
    mov di, ax
    sub ax, [bz_gvz]            ; lvz = max(0, fr - gvz)
    jge .lv
    xor ax, ax
.lv:
    mov [bz_lvz], ax
    mov cx, [bz_gvz]            ; r = (e max(0, min(lvz, -gvz))) >> 8
    neg cx
    cmp ax, cx
    jle .mn
    mov ax, cx
.mn:
    or ax, ax
    jns .mp
    xor ax, ax
.mp:
    mov cl, [bz_se + 3]
    xor ch, ch
    mul cx
    mov al, ah
    mov ah, dl
    mov bp, ax                  ; BP = r
    mov ax, bx                  ; lfall = max(0, ztop - h px), h's px floored
    sar ax, 1
    sar ax, 1
    neg ax
    add ax, [bz_ztop]
    jge .lf
    xor ax, ax
.lf:
    mov [bz_lfall], ax
    mov ax, bx                  ; z = h
    call bz_setz
    inc word [bz_nland]
    mov cx, [bz_mrec + BZM_BMIN] ; CL = BMIN, CH = GRIP (unused); CL = the
    mov al, [bz_mrec + BZM_HARD] ; mat's BZ_BMINMAT and no hard landing on a
    cmp byte [bz_surf], BZ_SURF_BOUNCE ; `bounce` floor (128.11.6.2)
    jne .hard
    mov cl, BZ_BMINMAT
    xor al, al
.hard:
    or al, al
    jz .soft
    mov dx, [bz_lvz]
    cmp dx, [bz_mrec + BZM_HTHR]
    jl .soft
    mov [bz_mst], al            ; 1. STUN or 2. SHATTER: grounded, every
    mov dl, [bz_mrec + BZM_HSTEPS] ; velocity stopped, the state's steps
    mov [bz_mct], dl
    cbw
    xchg ax, di
    shl di, 1
    inc word [bz_nstun - 2 + di] ; bz_nstun or bz_nshat
    xor ax, ax
    mov [bz_gvx], ax
    mov [bz_gvy], ax
    jmp short .ground
.soft:
    xor ch, ch                  ; CX = the rebound's floor
    cmp bp, cx
    jae .rok
    xor bp, bp                  ; BP = r if r >= BMIN, else 0
.rok:
    or di, di                   ; DI = min(fr, 0)
    jle .base
    xor di, di
.base:
    cmp byte [bz_hopw], 0       ; 3. a HOP AT THE CONTACT: max(HOP, that),
    je .bnc                     ; never a sum (O13)
    cmp byte [bz_mst], 0
    jne .bnc
    mov ax, [bz_mrec + BZM_HOP]
    cmp ax, bp
    jae .hp
    mov ax, bp
.hp:
    mov byte [bz_hopw], 0
    inc word [bz_nhop]
    jmp short .leave
.bnc:
    or bp, bp                   ; 4. a BOUNCE: r >= BMIN and Grip not held
    jz .ground
    test byte [bz_kstep], BZ_K_GRIP
    jnz .ground
    inc word [bz_nbnc]
    mov ax, bp
.leave:                         ; still airborne, from this height
    add ax, di
    mov [bz_gvz], ax
    mov ax, [bz_gz + 1]
    mov [bz_ztop], ax
    jmp short .sq
.ground:                        ; 5. lands as wave 1 (and 1., 2.)
    xor ax, ax
    mov [bz_gvz], ax
    mov [bz_air], al
.sq:
    cmp word [bz_lvz], BZ_SQTHR ; the squash, but a shatter's
    jl .out
    cmp byte [bz_mst], BZ_ST_SHAT
    je .out
    mov byte [bz_sqf], BZ_SQSTEPS
.out:
    ret

; bz_toff - TAKE OFF (128.10.7.3, and the Hop's, 128.11.8.6): airborne,
; ztop = z, z += gvz, keeping gvz.  Clobbers AX, DX.
bz_toff:
    mov byte [bz_air], 1
    mov ax, [bz_gz + 1]
    mov [bz_ztop], ax
    mov ax, [bz_gvz]
    cwd
    add [bz_gz], ax
    adc [bz_gz + 2], dx
    ret

; =============================================================================
; WAVE 3's PROPS (SPEC.md 128.12.6), bbcourse.Physics's _capture, _transit,
; _circle, _floor and the carry, integer-exact.  ES = the course throughout;
; a record is reached by its index through bz_lrecsi (bzwheel.inc).
; =============================================================================

; bz_psync - bz_ps from its three facts: bit 0 bz_wol not empty, bit 1 a tube
; in transit, bit 2 carried by the platform (128.12.3.2).  Preserves all.
bz_psync:
    push ax
    xor al, al
    cmp byte [bz_wol], 0
    je .a
    inc ax
.a:
    cmp byte [bz_tube], 0
    je .b
    or al, 2
.b:
    cmp byte [bz_onp], 0
    je .c
    or al, 4
.c:
    mov [bz_ps], al
    pop ax
    ret

; bz_wolf - bz_wol rebuilt for the window just filled (bz_fill, a course with
; props): its nine cells in bz_wrt's order - NW, W, N, SW, C, NE, S, E, SE, the
; model's Physics.WORDER - and for each OBS cell the record that owns it
; (bz_owner), as a (cell 0 - 8, index) pair; then bz_ps.  Clobbers BX, CX,
; DX, SI, DI and AX.
bz_wolf:
    xor ax, ax
    mov [bz_wcen], ax           ; (and bz_wckd)
    mov [bz_wbmp], al
    mov di, bz_wol + 1
    mov si, bz_wotab
    mov cx, 9
.c:
    mov bl, [si]
    xor bh, bh
    shl bx, 1
    shl bx, 1
    test byte [bz_nbr + bx + 3], BZ_FL_OBS
    jz .n
    mov dx, [bz_nwin]           ; the cell's wx, wy
    add dl, [si + 1]
    add dh, [si + 2]
    call bz_owner               ; AL = the index, AH = its kind
    jc .n
    mov bx, di                  ; the pair's kind beside it
    sub bx, bz_wol + 1
    shr bx, 1
    mov [bz_wkd + bx], ah
    cmp ah, BZ_PK_BUMPER
    jne .nb
    inc byte [bz_wbmp]
.nb:
    mov bl, [si]
    cmp bl, 4
    jne .nc
    inc ax                      ; the centre's
    mov [bz_wcen], ax
    dec ax
.nc:
    mov ah, al
    mov al, bl
    mov [di], ax
    inc di
    inc di
.n:
    add si, 3
    loop .c
    mov ax, di
    sub ax, bz_wol + 1
    shr ax, 1
    mov [bz_wol], al
    jmp bz_psync
; the window's cells in bz_wrt's order: the cell 0 - 8, dx, dy
bz_wotab:
    db 0, -1, -1,  3, -1, 0,  1, 0, -1,  6, -1, 1,  4, 0, 0
    db 2, 1, -1,  7, 0, 1,  5, 1, 0,  8, 1, 1

; bz_owner - the record owning cell DL = wx, DH = wy (128.12.3.2): the first,
; in the records' order, whose anchor is the cell - a tube's or windmill's IN,
; a bumper's post, a lift's shaft.  -> AL = its index, AH = its kind, CF = 0;
; CF = 1 none.
; Preserves all but AX and the flags.
bz_owner:
    push cx
    push si
    mov si, [bz_poff]
    mov cl, [bz_nprop]
.r:
    cmp dx, [es:si + BZP_WX]    ; (wx, wy as one word: a record that is not
    je .found                   ; the owner costs a compare, an ADD and a
    add si, BZ_PROPREC          ; count)
    dec cl
    jnz .r
    stc
    jmp short .out
.found:
    mov ax, si                  ; AL = (SI - PROPOFF) / 32, the index
    sub ax, [bz_poff]
    mov cl, 5
    shr ax, cl
    mov ah, [es:si + BZP_KIND]
    clc
.out:
    pop si
    pop cx
    ret
%if BZP_WY != BZP_WX + 1 || BZ_PROPREC != 32
 %error "bz_owner compares a record's (wx, wy) as one word and scales by 32"
%endif

; bz_ztouch - CF = 1 when the ball's z is at most the centre cell's floor at
; its point plus BZ_CLIMB (a drain's capture, a doorway's touch: 128.12.6.1,
; 128.12.6.2), exactly: z <= 64 (h4 + 16) <=> floor((z - 1) / 64) < h4 + 16.
; bz_ztouchp: at the point DL = u, DH = v.  Clobbers AX, BX, CX, DX, SI.
bz_ztouch:
    mov dl, [bz_gx + 1]
    and dl, 15
    mov dh, [bz_gy + 1]
    and dh, 15
bz_ztouchp:
    mov si, bz_nbr + BZN_C
    call bz_h4
    add ax, BZ_CLIMB * 4
    xchg ax, bx
    mov ax, [bz_gz]
    mov dx, [bz_gz + 2]
    sub ax, 1
    sbb dx, 0
    BZ_Q64
    cmp ax, bx
    jl .y
    clc
    ret
.y:
    stc
    ret

; bz_gate - the doorway's windmill ([bz_pdi]) at the step's n (128.12.6.2):
; phase = (n + seed) AND (P - 1), OPEN while phase < c0 or phase >= c1.  CF = 1
; open; else CF = 0 and BL = its gate's restitution eG (record +19).
; Clobbers AX, BX, SI.
bz_gate:
    mov bl, [bz_pdi]
    xor bh, bh
    call bz_lrecsi
    mov ax, [bz_nstep]
    add ax, [es:si + BZP_SEED]
    and al, [es:si + BZP_MASK]
    cmp al, [es:si + BZP_TC0]
    jb .open
    cmp al, [es:si + BZP_TC1]
    jae .open
    mov bl, [es:si + BZP_TEG]
    clc
    ret
.open:
    stc
    ret

; bz_capture - prop BL's tube takes the ball (128.12.6.1): the entry speed
; s_in = max(|gvx|, |gvy|); the centre at segment 0's start - IN's centre, a
; windmill's at its DOORWAY (the midpoint of IN's -x or -y edge) - on IN's
; floor there (IN is the window's centre); every velocity 0, grounded, no
; squash, no bz_gh, off the platform; the tube's first segment; bz_ntube + 1.
; Clobbers AX, BX, CX, DX, SI, DI.
bz_capture:
    xor bh, bh
    call bz_lrecsi
    inc bx
    mov [bz_tube], bl
    mov ax, [bz_gvx]
    cwd
    xor ax, dx
    sub ax, dx
    xchg ax, cx
    mov ax, [bz_gvy]
    cwd
    xor ax, dx
    sub ax, dx
    cmp ax, cx
    jae .s
    xchg ax, cx
.s:
    mov [bz_tsin], ax
    mov bx, 0808h               ; BL = u, BH = v: the centre ...
    cmp byte [es:si + BZP_KIND], BZ_PK_WINDMILL
    jne .at
    cmp byte [es:si + BZP_TGVX], 0
    jne .dy
    xor bl, bl                  ; ...the -x doorway's midpoint
    jmp short .at
.dy:
    xor bh, bh                  ; ...the -y one's
.at:
    mov cl, 4
    xor ah, ah
    mov al, [es:si + BZP_WX]
    shl ax, cl
    add al, bl
    mov [bz_gx + 1], ax
    xor ah, ah
    mov al, [es:si + BZP_WY]
    shl ax, cl
    add al, bh
    mov [bz_gy + 1], ax
    xor ax, ax
    mov [bz_gx], al
    mov [bz_gx + 3], al
    mov [bz_gy], al
    mov [bz_gy + 3], al
    mov [bz_gvx], ax
    mov [bz_gvy], ax
    mov [bz_gvz], ax
    mov [bz_air], al
    mov [bz_sqf], al
    mov [bz_ghv], al
    mov [bz_onp], al
    mov [bz_tseg], al
    mov di, [es:si + BZP_TSEGS]
    mov ax, [es:di]
    mov [bz_tcnt], ax
    inc word [bz_ntube]
    mov dx, bx
    mov si, bz_nbr + BZN_C
    call bz_h4
    call bz_setz
    jmp bz_psync

; bz_transit - a step in a tube (128.12.6.1): the ghost along its segment,
; the count down; at 0 the segment's END exactly and the next; after the last,
; the EXIT - KEEP grounded along the mouth at max(s_in, BZ_TMIN), LAUNCH
; airborne at the record's velocity (a take-off), DROP airborne along the
; mouth as KEEP with gvz 0 - and the window refilled round OUT.  Clobbers
; AX, BX, CX, DX, SI, DI.
bz_transit:
    mov bl, [bz_tube]
    dec bx
    xor bh, bh
    call bz_lrecsi
    mov al, [bz_tseg]
    xor ah, ah
    mov cl, 4
    shl ax, cl
    mov di, [es:si + BZP_TSEGS]
    add di, ax                  ; DI = the segment (BZ_SEGREC bytes)
    mov ax, [es:di + 2]
    cwd
    add [bz_gx], ax
    adc [bz_gx + 2], dx
    mov ax, [es:di + 4]
    cwd
    add [bz_gy], ax
    adc [bz_gy + 2], dx
    mov ax, [es:di + 6]
    cwd
    add [bz_gz], ax
    adc [bz_gz + 2], dx
    dec word [bz_tcnt]
    jnz .out
    xor ax, ax                  ; the segment's END, exactly
    mov [bz_gx], al
    mov [bz_gx + 3], al
    mov [bz_gy], al
    mov [bz_gy + 3], al
    mov [bz_gz], al
    mov ax, [es:di + 8]
    mov [bz_gx + 1], ax
    mov ax, [es:di + 10]
    mov [bz_gy + 1], ax
    mov ax, [es:di + 12]
    mov [bz_gz + 1], ax
    mov al, ah
    cbw
    mov [bz_gz + 3], ah
    inc byte [bz_tseg]
    mov al, [bz_tseg]
    cmp al, [es:si + BZP_TNSEG]
    jae .exit
    mov ax, [es:di + BZ_SEGREC]
    mov [bz_tcnt], ax
.out:
    jmp bz_psync
.exit:
    xor ax, ax
    mov [bz_tube], al
    mov [bz_tseg], al
    mov ax, [bz_gz + 1]         ; ztop = z, whole px
    mov [bz_ztop], ax
    mov al, [es:si + BZP_TSUB]
    cmp al, BZ_TK_LAUNCH
    jne .keep
    mov ax, [es:si + BZP_TGVX]  ; LAUNCH: the cannon's velocity, a take-off
    mov [bz_gvx], ax
    mov ax, [es:si + BZP_TGVY]
    mov [bz_gvy], ax
    mov ax, [es:si + BZP_TGVZ]
    mov [bz_gvz], ax
    mov byte [bz_air], 1
    cwd
    add [bz_gz], ax
    adc [bz_gz + 2], dx
    jmp short .win
.keep:                          ; KEEP grounded, DROP airborne: along the
    cmp al, BZ_TK_DROP          ; mouth at max(s_in, BZ_TMIN), gvz 0
    mov al, 0
    jne .k1
    inc ax
.k1:
    mov [bz_air], al
    mov ax, [bz_tsin]
    cmp ax, BZ_TMIN
    jae .v
    mov ax, BZ_TMIN
.v:
    xor dx, dx
    mov cl, [es:si + BZP_TDIR]  ; 0 +x, 1 -x, 2 +y, 3 -y
    test cl, 1
    jz .vs
    neg ax
.vs:
    test cl, 2
    jnz .vy
    xchg ax, dx
.vy:
    mov [bz_gvx], dx
    mov [bz_gvy], ax
    xor ax, ax
    mov [bz_gvz], ax
.win:
    call bz_win9f               ; the window round OUT (bz_ps with it)
    ret

; bz_ppos - the LIFT's (ES:SI, its record) rise above its low top at step AX
; = n, in 1/256 px (128.12.6.4; bbcourse.plat_pos): m = (n + seed) AND
; (P - 1), q = m in the first half and P - 1 - m in the second, pos =
; min(PMAX, max(0, q - W) v).  The last answer is kept (bz_pcn, bz_pcs,
; bz_pcv: a record offset is never 0, so the zeroed state holds none).  -> AX.
; Clobbers DX.
bz_ppos:
    cmp ax, [bz_pcn]            ; the last one asked (bz_carry asks pos(n)
    jne .calc                   ; first, which the last step's floor asked as
    cmp si, [bz_pcs]            ; its pos(n + 1))
    jne .calc
    mov ax, [bz_pcv]
    ret
.calc:
    mov [bz_pcn], ax
    mov [bz_pcs], si
    add ax, [es:si + BZP_SEED]
    mov dh, [es:si + BZP_MASK]
    and al, dh                  ; AL = m
    mov dl, dh
    shr dl, 1                   ; DL = P / 2 - 1
    cmp al, dl
    jbe .q
    sub dh, al
    mov al, dh                  ; q = P - 1 - m
.q:
    xor ah, ah
    sub al, [es:si + BZP_PW]
    jnc .w
    xor al, al
.w:
    mul word [es:si + BZP_PV]
    cmp ax, [es:si + BZP_PMAX]
    jbe .o
    mov ax, [es:si + BZP_PMAX]
.o:
    mov [bz_pcv], ax
    ret

; bz_carry - step 3's CARRY (128.12.6.4), a step that starts with bz_onp: the
; LIFT's rise pos(n + 1) - pos(n) added to z (and kept in bz_cdd for the
; undo).  Clobbers AX, BX, DX, SI.
bz_carry:
    mov bl, [bz_onp]
    dec bx
    xor bh, bh
    call bz_lrecsi
    mov ax, [bz_nstep]
    call bz_ppos                ; pos(n), and then pos(n + 1): what the step's
    push ax                     ; floor and bz_onp ask after it
    mov ax, [bz_nstep]
    inc ax
    call bz_ppos
    pop dx
    sub ax, dx
    mov [bz_cdd], ax
    cwd
    add [bz_gz], ax
    adc [bz_gz + 2], dx
    ret

; bz_slabon - step 6 in the SHAFT of the lift ES:SI: CF = 1 when its slab is
; the floor - the ball began the step at or over its top at n + 1 less
; BZ_CLIMB (zs >= 64 h4 - 256 BZ_CLIMB <=> zq >= h4) - with BX = that h4,
; 4 hP + pos(n + 1) / 64 (pos a multiple of 64: a whole quarter pixel).
; Clobbers AX, BX, CX, DX.
bz_slabon:
    mov ax, [bz_nstep]
    inc ax
    call bz_ppos
    mov cl, 6
    shr ax, cl
    mov bx, [es:si + BZP_PHP]
    shl bx, 1
    shl bx, 1
    add bx, ax
    cmp [bz_zq], bx
    jl .no
    stc
    ret
.no:
    clc
    ret

; bz_octe - the bumpers' OCTANT table's entry for AX = |du|, DX = |dv|
; (128.12.6.3): (a, b) = the larger and the smaller, at a (a + 1) / 2 + b.
; -> CF = 1 when a > BZ_OCTN (no contact); else BX = the entry (|n| along the
; larger, along the smaller, the depth) and CH = 1 when |dv| is the larger.
; Clobbers AX, DX.
bz_octe:
    xor ch, ch
    cmp ax, dx
    jae .s
    xchg ax, dx
    inc ch
.s:
    cmp ax, BZ_OCTN
    ja .no
    mov bl, al
    inc bx
    mul bl
    shr ax, 1
    add ax, dx
    mov bx, ax
    shl ax, 1
    add bx, ax
    add bx, bz_otab
    clc
    ret
.no:
    stc
    ret

; bz_pdist - AX = |gx - post's cx|, DX = |gy - cy| (integer gu; ES:SI the
; bumper's record), BP: bit 0 du < 0, bit 1 dv < 0.  Clobbers nothing else.
bz_pdist:
    xor bp, bp
    mov ax, [bz_gx + 1]
    sub ax, [es:si + BZP_BCX]
    jns .x
    neg ax
    inc bp
.x:
    mov dx, [bz_gy + 1]
    sub dx, [es:si + BZP_BCY]
    jns .y
    neg dx
    or bp, 2
.y:
    ret

; bz_ptop - step 6 on a POST cell (128.12.6.3; ES:SI the bumper): its floor at
; the centre's point, plus the post's height where the octant table's depth
; there is over 96 (within 6 gu of the post's centre).  -> BX = that h4.
; Clobbers AX, CX, DX, BP.
bz_ptop:
    push si
    mov dl, [bz_gx + 1]
    and dl, 15
    mov dh, [bz_gy + 1]
    and dh, 15
    mov si, bz_nbr + BZN_C
    call bz_h4
    pop si
    push ax
    call bz_pdist
    call bz_octe
    pop ax
    jc .out
    cmp byte [bx + 2], 16 * BZ_PRAD
    jbe .out
    mov cl, [es:si + BZP_BH]
    xor ch, ch
    shl cx, 1
    shl cx, 1
    add ax, cx
.out:
    xchg ax, bx
    ret

; bz_posts - step 5's CIRCLES (128.12.6.3): each post on bz_wol in its order,
; bz_circle.  Clobbers AX, BX, CX, DX, SI, DI, BP.
bz_posts:
    cmp byte [bz_wbmp], 0
    je .out
    mov cl, [bz_wol]
    xor ch, ch
    mov di, bz_wol + 1
.p:
    mov bx, di
    sub bx, bz_wol + 1
    shr bx, 1
    cmp byte [bz_wkd + bx], BZ_PK_BUMPER
    jne .n
    push cx
    push di
    mov bl, [di + 1]
    xor bh, bh
    call bz_lrecsi
    mov al, [di]
    call bz_circle
    pop di
    pop cx
.n:
    inc di
    inc di
    loop .p
.out:
    ret

; bz_circle - bumper BX (ES:SI its record, AL its post's window cell): when
; the octant table has a depth at (|du|, |dv|) and the step's START z is
; under the post's top (zs < 256 top <=> zq < 4 top + 16), the centre is pushed
; depth |n| / 4 out along each axis, and with d = (gvx nx + gvy ny) >> 6 the
; outward normal speed, t = max(K, ((BZ_EBUMPER (-d)) >> 8) + KA) when d < 0,
; max(K, d) else, and gv += ((t - d) n) >> 6, each axis clamped; the post's
; kick step = n, bz_nkick + 1.  Clobbers AX, BX, CX, DX, DI, BP.
bz_circle:
    push bx
    mov ah, 0
    push ax                     ; (the post's window cell)
    call bz_pdist               ; AX = |du|, DX = |dv|, BP their signs: the
    cmp ax, BZ_OCTN             ; table's reach first, the cheap refusal
    ja .out2
    cmp dx, BZ_OCTN
    ja .out2
    pop bx
    push ax
    push dx
    shl bx, 1
    shl bx, 1
    push si
    lea si, [bz_nbr + bx]
    mov dx, 0808h
    call bz_h4                  ; the post cell's floor (flat: as built)
    pop si
    sar ax, 1
    sar ax, 1
    mov cl, [es:si + BZP_BH]
    xor ch, ch
    add ax, cx                  ; its top, px
    shl ax, 1
    shl ax, 1
    add ax, BZ_CLIMB * 4
    cmp [bz_zq], ax
    pop dx
    pop ax
    jge .out
    call bz_octe
    jc .out
    mov cl, [bx]                ; |n| along the larger, along the smaller
    mov dh, [bx + 1]
    or ch, ch
    jz .ns
    xchg cl, dh                 ; (the larger along y)
.ns:
    mov ch, dh                  ; CL = |nx|, CH = |ny|
    mov dl, [bx + 2]            ; the depth (0: no contact)
    or dl, dl
    jz .out
    mov al, dl                  ; the push, along x ...
    mul cl
    shr ax, 1
    shr ax, 1
    test bp, 1
    jnz .xm
    add [bz_gx], ax
    adc word [bz_gx + 2], 0
    jmp short .y
.xm:
    sub [bz_gx], ax
    sbb word [bz_gx + 2], 0
.y:
    mov al, dl                  ; ...and along y
    mul ch
    shr ax, 1
    shr ax, 1
    test bp, 2
    jnz .ym
    add [bz_gy], ax
    adc word [bz_gy + 2], 0
    jmp short .n
.ym:
    sub [bz_gy], ax
    sbb word [bz_gy + 2], 0
.n:
    mov al, cl                  ; DI, CX = nx, ny, the quadrant's signs
    xor ah, ah
    test bp, 1
    jz .nx
    neg ax
.nx:
    xchg ax, di
    mov al, ch
    xor ah, ah
    test bp, 2
    jz .ny
    neg ax
.ny:
    xchg ax, cx
    mov ax, [bz_gvx]            ; d = (gvx nx + gvy ny) >> 6, in 32 bits
    imul di
    mov bx, ax
    mov bp, dx
    mov ax, [bz_gvy]
    imul cx
    add ax, bx
    adc dx, bp
    call bz_sar6
    mov bp, ax                  ; BP = d
    or ax, ax
    jns .t                      ; d >= 0: t = max(K, d)
    neg ax
    mov bx, BZ_EBUMPER          ; d < 0: never under the rail's rebound + KA
    mul bx
    mov al, ah
    mov ah, dl
    add ax, [es:si + BZP_BKA]
.t:
    cmp ax, [es:si + BZP_BK]
    jge .tk
    mov ax, [es:si + BZP_BK]
.tk:
    sub ax, bp                  ; t - d
    mov bp, ax
    imul di                     ; gvx += ((t - d) nx) >> 6, clamped
    call bz_sar6
    add ax, [bz_gvx]
    call bz_gax.clamp
    mov [bz_gvx], ax
    mov ax, bp                  ; gvy the same with ny
    imul cx
    call bz_sar6
    add ax, [bz_gvy]
    call bz_gax.clamp
    mov [bz_gvy], ax
    pop bx
    shl bx, 1
    mov ax, [bz_nstep]
    mov [bz_pkick + bx], ax
    inc word [bz_nkick]
    ret
.out2:
    pop ax
.out:
    pop bx
    ret

; -----------------------------------------------------------------------------
; bz_frate - the floor's own vertical rate under the ball at its ground
; velocity, (sx gvx + sy gvy) >> 2 with C's slopes (bz_tsx, bz_tsy: 0 off a
; plane floor).  -> AX.  Clobbers BX, CX, DX.
; -----------------------------------------------------------------------------
bz_frate:
    xor cx, cx
    mov ax, [bz_tsx]
    or ax, [bz_tsy]
    jz .out                     ; a flat floor: 0, and no product
    mov ax, [bz_gvx]
    mov bx, [bz_tsx]
    call bz_smul                ; (AX x BX)
    mov cx, ax
    mov ax, [bz_gvy]
    mov bx, [bz_tsy]
    call bz_smul
    add cx, ax
    sar cx, 1
    sar cx, 1
.out:
    xchg ax, cx
    ret

; -----------------------------------------------------------------------------
; bz_gax - one ground axis after its forces (128.11.8.2 step 2): AX through
; the DRAG ceil(|v| / 2^CL) toward 0 (CL = 0: none, ice), then the BRAKE CH
; toward 0 and never past it (0: none), then clamped to +-BZ_VMAXG.  The
; airborne axis passes CX = 0: the clamp alone.  -> AX.  Clobbers DX.
; -----------------------------------------------------------------------------
bz_gax:
    or cl, cl
    jz .brake
    mov dx, ax                  ; ceil(|v| / 2^k) = -((-|v|) >> k), arithmetic
    or ax, ax
    js .dn
    neg dx
    sar dx, cl
    add ax, dx
    jmp short .brake
.dn:
    sar dx, cl
    sub ax, dx
.brake:
    or ch, ch
    jz .clamp
    mov dl, ch
    xor dh, dh
    or ax, ax
    js .bn
    sub ax, dx                  ; v > b: v - b; else 0
    jg .clamp
    xor ax, ax
    jmp short .clamp
.bn:
    add ax, dx                  ; v < -b: v + b; else 0
    jl .clamp
    xor ax, ax
.clamp:
    cmp ax, BZ_VMAXG
    jle .c1
    mov ax, BZ_VMAXG
    ret
.c1:
    cmp ax, -BZ_VMAXG
    jge .out
    mov ax, -BZ_VMAXG
.out:
    ret

; -----------------------------------------------------------------------------
; bz_wrefl - a velocity component AX that met the blocking window cell at SI,
; REFLECTED (SPEC.md 128.11.8.4): t = (e |v|) >> 8, 0 under BZ_WMIN, and
; v = -sign(v) t; e is 230 off a BUMPER (a WALL with a `bounce` surface),
; else the material's stone EW (a floor too high to step onto included).
; bz_refl: the same with BL = e.  -> AX.  Preserve SI, DI, BP; clobber BX,
; CX, DX.
; -----------------------------------------------------------------------------
bz_wrefl:
    mov bl, BZ_EBUMPER
    cmp byte [si + 2], (BZ_SURF_BOUNCE << 4) | BZ_KWALL
    je bz_refl
    mov bl, [bz_mrec + BZM_EW]
bz_refl:
    mov cx, ax                  ; its sign
    or ax, ax
    jns .p
    neg ax
.p:
    cmp ax, BZ_WMIN             ; |v| under WMIN: e |v| >> 8 < |v| (e <= 255),
    jb .z                       ; so 0 exactly, without the MUL - a ball held
    xor bh, bh                  ; against a wall meets it every step
    mul bx                      ; DX:AX = e |v| (under 2^24)
    mov al, ah
    mov ah, dl                  ; >> 8
    cmp ax, BZ_WMIN
    jb .z
    inc word [bz_nwall]         ; SOUND STATE (SPEC.md 128.20.5), never read
    mov [bz_lwv], ax            ; by physics: a reflection that left a speed,
    mov byte [bz_lwb], 0        ; the speed, and whether off a bumper's face
    cmp bl, BZ_EBUMPER
    jne .t
    mov byte [bz_lwb], 1
    jmp short .t
.z:
    xor ax, ax
.t:
    or cx, cx                   ; v < 0: +t;  v >= 0: -t
    js .out
    neg ax
.out:
    ret

; -----------------------------------------------------------------------------
; bz_corner - step 5's corner: the centre within BZ_RAD of both edges at a
; corner (so neither edge neighbour blocked - one that did put the centre
; exactly BZ_RAD from its edge), the corner neighbour blocks, and the corner
; point is nearer than BZ_RAD: the centre pushed out along the normal and the
; velocity's component into the corner REFLECTED (128.10.7.3's table,
; 128.11.8.3's |du|, 128.11.8.4's rule): d = (gvx nx + gvy ny) >> 6; only if
; d < 0, t = (e (-d)) >> 8 (0 under BZ_WMIN), and v -= ((d - t) n) >> 6.
; ES = the course.  Clobbers AX, BX, CX, DX, SI, DI, BP.
; -----------------------------------------------------------------------------
bz_corner:
    xor bp, bp                  ; BP: bit 0 east, bit 1 south
    mov bx, BZN_NW              ; BX = the corner cell's window offset
    mov ax, [bz_gx]             ; across: west (|du| = pu >> 8) or east
    and ah, 15                  ; ((4,096 - pu) >> 8)
    cmp ax, BZ_RAD * 256
    jb .cw
    neg ax
    add ax, 4096
    mov bx, BZN_NE
    inc bp
.cw:
    mov cl, ah                  ; CL = |du|
    mov ax, [bz_gy]             ; down: north or south, the same
    and ah, 15
    cmp ax, BZ_RAD * 256
    jb .cn
    neg ax
    add ax, 4096
    add bx, BZN_SW - BZN_NW
    or bp, 2
.cn:                            ; AH = |dv|
    mov al, cl                  ; the entry: 3 (6 |du| + |dv|)
    shl al, 1
    add al, cl
    shl al, 1
    add al, ah
    mov cl, al
    shl al, 1
    add al, cl
    xor ah, ah
    mov di, ax
    add di, bz_ctab
    cmp byte [di + 2], 0        ; depth 0: du^2 + dv^2 >= 36, no contact
    je .out
    xor dx, dx                  ; the corner cell's point nearest the centre:
    test bp, 1                  ; (16 west, 0 east; 16 north, 0 south)
    jnz .pe
    mov dl, 16
.pe:
    test bp, 2
    jnz .ps
    mov dh, 16
.ps:
    lea si, [bz_nbr + bx]
    call bz_blocks
    jnc .out
    mov bl, BZ_EBUMPER          ; its restitution, kept on the stack
    cmp byte [si + 2], (BZ_SURF_BOUNCE << 4) | BZ_KWALL
    je .e
    mov bl, [bz_mrec + BZM_EW]
.e:
    push bx
    mov al, [di + 2]            ; the push: depth |n| / 4, 1/256 gu, an axis
    mul byte [di]
    shr ax, 1
    shr ax, 1
    test bp, 1
    jnz .mxe
    add [bz_gx], ax             ; west: +x
    adc word [bz_gx + 2], 0
    jmp short .my
.mxe:
    sub [bz_gx], ax             ; east: -x
    sbb word [bz_gx + 2], 0
.my:
    mov al, [di + 2]
    mul byte [di + 1]
    shr ax, 1
    shr ax, 1
    test bp, 2
    jnz .mys
    add [bz_gy], ax             ; north: +y
    adc word [bz_gy + 2], 0
    jmp short .dot
.mys:
    sub [bz_gy], ax             ; south: -y
    sbb word [bz_gy + 2], 0
.dot:
    mov al, [di]                ; CX, SI = nx, ny with the quadrant's signs
    xor ah, ah
    test bp, 1
    jz .nx
    neg ax
.nx:
    mov cx, ax
    mov al, [di + 1]
    xor ah, ah
    test bp, 2
    jz .ny
    neg ax
.ny:
    mov si, ax
    mov ax, [bz_gvx]            ; d = (gvx nx + gvy ny) >> 6, in 32 bits: the
    imul cx                     ; sum can pass a word
    mov bx, ax
    mov bp, dx
    mov ax, [bz_gvy]
    imul si
    add ax, bx
    adc dx, bp
    call bz_sar6
    pop bx                      ; BL = e
    or ax, ax
    jns .out                    ; not moving into the corner
    mov bp, ax                  ; BP = d
    push cx
    call bz_refl                ; AX = t (d < 0: +t)
    pop cx
    sub bp, ax                  ; BP = d - t
    mov ax, bp
    imul cx                     ; gvx -= ((d - t) nx) >> 6
    call bz_sar6
    sub [bz_gvx], ax
    mov ax, bp
    imul si                     ; gvy -= ((d - t) ny) >> 6
    call bz_sar6
    sub [bz_gvy], ax
.out:
    ret

; -----------------------------------------------------------------------------
; bz_blocks - does the window cell at SI block the ball at its point (DL = u,
; DH = v, 0 .. 16)?  A WALL always; a plane floor (FLOOR, GOAL) when its h4
; there is above [bz_zq] - the step's START z plus the climb, grounded or
; airborne (128.11.8.2 step 5); VOID and the reserved kinds never; a
; bumper's post cell never (wave 3, 128.12.6.5: its post is the circle's).
; CF = 1 blocks.  ES = the course.  Clobbers AX, BX, CX.
; -----------------------------------------------------------------------------
bz_blocks:
    mov al, [si + 2]
    and al, 0fh
    cmp al, BZ_KWALL
    je .yes
    cmp al, BZ_KFLOOR
    je .plane
    cmp al, BZ_KGOAL
    jne .no
.plane:
    call bz_h4
    cmp [bz_zq], ax             ; CF = zq < h4 (signed)
    jl .high
.no:
    clc
    ret
.high:
    test byte [si + 3], BZ_FL_OBS ; wave 3: a BUMPER's post cell never blocks
    jnz .obs                    ; (128.12.6.5 step 5; never set with no prop
.yes:                           ; in the window)
    stc
    ret
.obs:
    push dx
    push si
    mov ax, si                  ; the window cell's pair on bz_wol (and its
                                ; prop's kind beside it, bz_wkd)
    sub ax, bz_nbr
    shr ax, 1
    shr ax, 1
    mov cl, [bz_wol]
    xor ch, ch
    mov si, bz_wol + 1
.ol:
    cmp [si], al
    je .of
    inc si
    inc si
    loop .ol
    jmp short .oy
.of:
    sub si, bz_wol + 1
    shr si, 1
    cmp byte [bz_wkd + si], BZ_PK_BUMPER
    pop si
    pop dx
    je .no
    stc
    ret
.oy:
    pop si
    pop dx
    stc
    ret

; -----------------------------------------------------------------------------
; bz_h4 - the floor of the plane cell at SI (in bz_nbr) at its point (DL = u,
; DH = v, each 0 .. 16) in QUARTER px: h4 = 16 z0 + sx u + sy v (128.10.4.3).
; The products are bz_prod's, T[(n & 15) << 4 | u] = n u; the far edge (16)
; is 16 n, the slope nibble moved to the high nibble.  -> AX.  Clobbers BX, CX.
; -----------------------------------------------------------------------------
bz_h4:
    mov ch, [si + 1]            ; sy : sx
    or ch, ch
    jz .flat                    ; no slope: 16 z0 wherever
    mov bx, bz_prod
    mov al, ch
    mov cl, 4
    shl al, cl                  ; 16 sx (signed)
    cmp dl, 16
    je .ue
    or al, dl
    xlat                        ; sx u
.ue:
    cbw
    xchg ax, cx                 ; CX = sx u;  AH = the slopes
    mov al, ah
    and al, 0f0h                ; 16 sy (signed)
    cmp dh, 16
    je .ve
    or al, dh
    xlat                        ; sy v
.ve:
    cbw
    add cx, ax
    mov al, [si]
    cbw
    shl ax, 1
    shl ax, 1
    shl ax, 1
    shl ax, 1                   ; 16 z0
    add ax, cx
    ret
.flat:
    mov al, [si]
    cbw
    shl ax, 1
    shl ax, 1
    shl ax, 1
    shl ax, 1
    ret

; AX = h4 -> bz_gz = 64 h4 (24.8 px: the fraction (h4 & 3) << 6, the whole px
; h4 >> 2, its sign).  Clobbers AX, CX, DX.
bz_setz:
    mov dx, ax
    sar dx, 1
    sar dx, 1
    mov cl, 6
    shl al, cl
    mov [bz_gz], al
    mov [bz_gz + 1], dx
    mov al, dh
    cbw
    mov [bz_gz + 3], ah
    ret

; DX:AX (signed) -> AX = DX:AX >> 6, arithmetic, when that fits a word.
; Preserves all else.
bz_sar6:
    push cx
    push dx
    mov cl, 6
    shr ax, cl
    mov cl, 10
    shl dx, cl
    or ax, dx
    pop dx
    pop cx
    ret

; AX x BX (BX a slope, -8 .. 8) -> AX, by shifts and adds (no IMUL).
; Clobbers BX, DX.
bz_smul:
    xor dx, dx
    or bx, bx
    jns .p
    neg bx
    neg ax
.p:
    shr bx, 1
    jnc .n
    add dx, ax
.n:
    shl ax, 1
    or bx, bx
    jnz .p
    mov ax, dx
    ret

; -----------------------------------------------------------------------------
; bz_win9f - the window round the ball's cell (wx, wy = the integer gu >> 4),
; refilled.  bz_fill: the window round AL = wx, AH = wy.  Either sets bz_nwin,
; bz_wgx, bz_wgy (16 wx, 16 wy: what step 4's cell test compares) and bz_tsx, bz_tsy (the
; centre's slopes, sign-extended; 0 unless it is a plane floor, so step 2 reads
; them as they are).  ES = the course.  Preserve all but AX and the flags.
; -----------------------------------------------------------------------------
bz_win9f:
    push cx
    mov ax, [bz_gx + 1]
    mov cx, [bz_gy + 1]
    shr ax, 1
    shr ax, 1
    shr ax, 1
    shr ax, 1
    shr cx, 1
    shr cx, 1
    shr cx, 1
    shr cx, 1
    mov ah, cl                  ; (both < 256)
    pop cx
bz_fill:
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov [bz_nwin], ax
    mov bl, ah
    xor bh, bh
    xor ah, ah                  ; AX = wx, BX = wy
    mov cl, 4
    mov dx, ax
    shl dx, cl
    mov [bz_wgx], dx
    mov dx, bx
    shl dx, cl
    mov [bz_wgy], dx
    ; The nine cells are FIVE grid rows (128.10.4.3): s - 2 .. s + 2, each a
    ; run of 1, 2, 3, 2, 1 cells consecutive in k - so one ROWTAB read a row
    ; (bz_wrt is the rows: the first cell's k against the centre's, the run,
    ; the window cells).  A row or a k outside the grid is OPEN.
    mov di, [bz_goff]
    mov cx, [es:di + BZG_NROWS]
    mov [bz_fnr], cx
    mov cx, [es:di + BZG_KW]
    mov [bz_fkw], cx
    mov cx, [es:di + BZG_ROWTAB]
    mov [bz_frt], cx
    mov dx, ax
    add dx, bx
    sub dx, [es:di + BZG_SMIN]
    dec dx
    dec dx                      ; row s - 2's r (a negative r is huge)
    mov [bz_fr], dx
    sub ax, bx
    sub ax, [es:di + BZG_AMIN]  ; a - AMIN: a's parity, AMIN even
    mov cx, ax
    and cx, 1
    dec cx                      ; rows s +- 1 start at k - 1 for an even a, at
    mov [bz_fdp], cx            ; k for an odd one
    sar ax, 1
    mov [bz_fka], ax            ; the centre's k
    mov si, bz_wrt
    mov cx, 5
.row:
    push cx
    lodsw                       ; the first cell's k: 0, -1 or BZ_WRP (row s +- 1)
    cmp ax, BZ_WRP
    jne .dk
    mov ax, [bz_fdp]
.dk:
    add ax, [bz_fka]
    mov cx, ax
    lodsw
    xchg ax, cx                 ; CX = the run, AX = its first k
    mov bx, [bz_fr]
    cmp bx, [bz_fnr]
    jb .rowin
    mov ax, 8000h               ; a row outside the grid: every k "huge"
    jmp short .cell
.rowin:
    shl bx, 1
    add bx, [bz_frt]
    mov bx, [es:bx]             ; ROWTAB[r]: the row's first cell...
    mov dx, ax
    shl dx, 1
    shl dx, 1
    add bx, dx                  ; ...BX = the run's first
.cell:
    mov di, [si]                ; the window cell
    inc si
    inc si
    cmp ax, [bz_fkw]
    jae .open                   ; (a negative k is huge)
    mov dx, [es:bx]
    mov [di], dx
    mov dx, [es:bx + 2]
    mov [di + 2], dx
    jmp short .next
.open:
    mov word [di], BZ_ZOPEN     ; z0 -128, flat, VOID, no flags
    mov word [di + 2], 0
.next:
    add bx, 4
    inc ax
    loop .cell
    inc word [bz_fr]
    pop cx
    loop .row
    xor ax, ax                  ; the centre's slopes, for step 2
    mov dx, ax
    mov si, bz_nbr + BZN_C
    mov cl, [si + 2]
    and cl, 0fh
    cmp cl, BZ_KFLOOR
    je .sl
    cmp cl, BZ_KGOAL
    jne .nosl
.sl:
    mov al, [si + 1]            ; sy : sx, signed nibbles
    mov ah, al
    mov cl, 4
    shl al, cl
    sar al, cl                  ; AL = sx
    sar ah, cl                  ; AH = sy
    mov dl, ah
    cbw
    xchg ax, dx                 ; DX = sx
    cbw                         ; AX = sy
.nosl:
    mov [bz_tsx], dx
    mov [bz_tsy], ax
    mov al, [bz_nbr + BZN_C + 2] ; the centre's SURFACE (whatever its kind): a
    mov cl, 4                   ; new one rebuilds the step's force, drag,
    shr al, cl                  ; brake and floor e (128.11.7.1)
    cmp al, [bz_surf]
    je .same
    call bz_surfset
.same:
    cmp byte [bz_nprop], 0      ; wave 3: bz_wol and bz_ps (a course with no
    je .nowol                   ; prop has neither, so they stay 0)
    call bz_wolf
.nowol:
    mov ax, [bz_nwin]
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; bz_surfset - AL = the window centre's surface: [bz_surf] = it, bz_se =
; BZ_SURFTAB's entry for [bz_mat] on it (force, drag shift, brake, floor e),
; and bz_ftg rebuilt from its force, ftg[l] = (A l + 4) >> 3 (128.11.7.1).
; A surface 4 - 15 is RESERVED and the tool refuses it: nothing is checked.
; DS = ours.  Clobbers AX, BX, CX, DX, DI.
bz_surfset:
    mov [bz_surf], al
    mov bl, [bz_mat]
    shl bl, 1
    shl bl, 1
    add bl, al
    xor bh, bh
    shl bx, 1
    shl bx, 1                   ; 4 (4 mat + surface)
    mov ax, [bz_surftab + bx]
    mov [bz_se], ax
    mov ax, [bz_surftab + bx + 2]
    mov [bz_se + 2], ax
    mov al, [bz_se]             ; the force at full ramp
    mov di, bz_ftg
    mov cl, 3
    jmp bz_ramp

; bz_fill's five grid rows, s - 2 .. s + 2: the first cell's k against the
; centre's (BZ_WRP: -1 for an even a, 0 for an odd one), the run, and the
; window cells in k order (a ascending)
BZ_WRP      equ 1
bz_wrt:
    dw 0, 1, bz_nbr + BZN_NW                            ; s - 2: a
    dw BZ_WRP, 2, bz_nbr + BZN_W, bz_nbr + BZN_N        ; s - 1: a - 1, a + 1
    dw -1, 3, bz_nbr + BZN_SW, bz_nbr + BZN_C, bz_nbr + BZN_NE ; s: a - 2, a, a + 2
    dw BZ_WRP, 2, bz_nbr + BZN_S, bz_nbr + BZN_E        ; s + 1: a - 1, a + 1
    dw 0, 1, bz_nbr + BZN_SE                            ; s + 2: a

; -----------------------------------------------------------------------------
; bz_place - the ball on bz_safe's centre (16 wx + 8, 16 wy + 8) on its floor,
; at rest and grounded, the window filled round it (128.10.7.1, step 7).  ES =
; the course.  Clobbers AX, BX, CX, DX, SI.
; -----------------------------------------------------------------------------
bz_place:
    mov ax, [bz_safe]
    mov dl, ah
    xor ah, ah
    xor dh, dh
    mov cl, 4
    shl ax, cl
    add ax, 8
    mov [bz_gx + 1], ax
    shl dx, cl
    add dx, 8
    mov [bz_gy + 1], dx
    xor ax, ax
    mov [bz_gx], al
    mov [bz_gx + 3], al
    mov [bz_gy], al
    mov [bz_gy + 3], al
    mov [bz_gvx], ax
    mov [bz_gvy], ax
    mov [bz_gvz], ax
    mov [bz_air], al
    mov [bz_tube], al           ; out of any tube, off the platform (SPEC.md
    mov [bz_tseg], al           ; 128.12.6.5: a respawn changes no prop)
    mov [bz_onp], al
    mov [bz_tcnt], ax
    mov ax, [bz_safe]
    call bz_fill
    mov si, bz_nbr + BZN_C
    mov dx, 0808h
    call bz_h4
    jmp bz_setz

; -----------------------------------------------------------------------------
; bz_derive - the SCREEN state from (gx, gy, z) (SPEC.md 128.10.8):
;   bz_bx = gx - gy + (X0 - 8),  bz_by = (gx + gy) / 2 - z + (Y0 - 13)
; in 24.8 (fractions kept), and bz_vx, bz_vy = how far their low words moved.
; Clobbers AX, BX, CX, DX, SI, DI.
; -----------------------------------------------------------------------------
bz_derive:
    mov ax, [bz_gx]
    mov dx, [bz_gx + 2]
    mov si, [bz_gy]
    mov di, [bz_gy + 2]
    mov bx, ax
    mov cx, dx
    sub ax, si                  ; gx - gy
    sbb dx, di
    add ax, [bz_kx]
    adc dx, [bz_kx + 2]
    mov [bz_bx + 2], dx
    xchg ax, [bz_bx]            ; AX = last step's low word
    neg ax
    add ax, [bz_bx]
    mov [bz_vx], ax
    add bx, si                  ; (gx + gy) / 2
    adc cx, di
    shr cx, 1
    rcr bx, 1
    sub bx, [bz_gz]
    sbb cx, [bz_gz + 2]
    add bx, [bz_ky]
    adc cx, [bz_ky + 2]
    mov [bz_by + 2], cx
    mov ax, bx
    xchg ax, [bz_by]
    sub bx, ax
    mov [bz_vy], bx
    ret

; -----------------------------------------------------------------------------
; bz_ftime - the last play's time to the goal, in HUNDREDTHS of a second, from
; its steps: floor(nstep x 21,845 x 100 / 1,193,182) (SPEC.md 128.10.6.2; a
; play past 65,535 steps, 20 minutes, reads as that).  1,193,182 = 82 x 14,551,
; and floor(floor(X / a) / b) = floor(X / ab), so two chained 16-bit divides
; do it.  The desktop's, once a face.  -> DX:AX.  Clobbers BX, CX, SI, DI.
; -----------------------------------------------------------------------------
bz_ftime:
    mov ax, [bz_nstep]
    cmp word [bz_nstep + 2], 0
    je .w
    mov ax, 0ffffh
.w:
    mov cx, 21845
    mul cx                      ; DX:AX = n 21,845
    mov bx, dx
    mov cx, 100
    mul cx
    mov si, ax                  ; W0
    mov di, dx
    mov ax, bx
    mul cx
    add ax, di                  ; DX:AX = W2:W1 (W2 < 34)
    adc dx, 0
    mov cx, 14551
    div cx                      ; W2:W1 / 14,551: under 150
    mov bx, ax
    mov ax, si
    div cx                      ; BX:AX = X / 14,551
    mov cx, 82
    xchg ax, bx
    xor dx, dx
    div cx
    xchg ax, bx
    div cx                      ; BX:AX = X / 1,193,182
    mov dx, bx
    ret

; the products of bz_h4: T[(n & 15) << 4 | u] = n u, n -8 .. 7, u 0 .. 15
bz_prod:
%assign bz_i 0
%rep 256
 %assign bz_n bz_i >> 4
 %if bz_n >= 8
  %assign bz_n bz_n - 16
 %endif
    db (bz_n * (bz_i & 15)) & 0ffh
 %assign bz_i bz_i + 1
%endrep

; the corner table, the model's own (bzcourse.inc, 128.10.7.3)
bz_ctab:
    BZ_CORNER_TABLE
; the bumpers' octant table, the model's own (bzcourse.inc, 128.12.6.3)
bz_otab:
    BZ_OCTANT_TABLE
; the materials' records and every material's force, drag, brake and floor e on
; every surface (bzcourse.inc, bbcourse.MATERIALS: SPEC.md 128.11.5.1, 128.11.6.2)
bz_mattab:
    BZ_MATTAB
bz_surftab:
    BZ_SURFTAB
