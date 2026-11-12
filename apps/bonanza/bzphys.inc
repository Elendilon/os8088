; bzphys.inc - BONANZA's physics v1 (SPEC.md 128.10.7, 128.10.8): the ball in
; GROUND units on the course part's BZG1 grid, one step a FASTTICK sub-tick.
; tools/bbcourse.py's Physics class is the reference and this is integer-exact
; to it, step for step; SPEC.md 128.10.7.3 is the binding order both follow.
;
; =============================================================================
; GUEST STATE A HARNESS READS (128.10.7.1; offsets the package segment's)
; =============================================================================
;   bz_gx,bz_gy DWORD  the contact point, gu in 24.8: +0 the fraction, +1 the
;                      integer gu as a WORD (0 .. 4,095), +3 zero
;   bz_gz       DWORD  the ball's bottom, px in 24.8, SIGNED: +1 a signed word,
;                      +3 its sign (so the DWORD is the two's complement value)
;   bz_gvx,bz_gvy word 1/256 gu a step;  bz_gvz word 1/256 px a step, up +
;   bz_air      byte   1 while airborne
;   bz_ztop     word   the highest z (px, floor) of this flight
;   bz_lfall    word   the last landing's drop, ztop - h (px, >= 0)
;   bz_lvz      word   the last landing's impact speed, -gvz
;   bz_safe     2 bytes the last SAFE cell stood on: wx, then wy
;   bz_nstep    DWORD  steps since the play began
;   bz_nfall    word   respawns;  bz_nland word landings
;   bz_goal     byte   1 once a grounded step lands on a GOAL cell in PLAY
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

BZ_KVOID    equ 0               ; a cell's kind (the low nibble of byte +2)
BZ_KFLOOR   equ 1
BZ_KWALL    equ 2
BZ_KGOAL    equ 3
BZ_FSAFE    equ 1               ; flags (byte +3): a respawn cell
BZ_FOCC     equ 2               ; ...the occluder pass may lay a record
BZ_ZOPEN    equ 80h             ; an OPEN cell's z0 (-128)
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
VAR bz_sb,2
VAR bz_air,1
VAR bz_goal,1
VAR bz_resp,1
VAR bz_pokd,1                   ; a harness sets it after POKING the ball (the
                                ; next step refills the window, then clears it)
VAR bz_phe,0
; the rest: written before they are read
VAR bz_safe,2                   ; wx, wy
VAR bz_nwin,2                   ; wx, wy
VAR bz_wgx,2                    ; 16 wx, 16 wy of the window's centre (the cell test)
VAR bz_wgy,2
VAR bz_sgx,4                    ; the step's START ground position (step 3; z
VAR bz_sgy,4                    ; is put back by its gvz)
VAR bz_zq,2                     ; floor(start z / 64) quarter px, + 16 grounded
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
%endmacro
BZ_PHSN     equ bz_phe - bz_phs

; -----------------------------------------------------------------------------
; bz_pinit - the ball at the course's start (SPEC.md 128.10.7.1): the start
; tile's centre on its floor, at rest, grounded, the window filled, every
; counter zero, and the screen state derived with a zero velocity.  DS = ours,
; [bz_cseg] the course, bz_crshdr run.  Preserves nothing.
; -----------------------------------------------------------------------------
bz_pinit:
    push ds
    pop es
    xor ax, ax
    mov di, bz_phs
    mov cx, BZ_PHSN / 2
    rep stosw
    mov es, [bz_cseg]
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

; BZ_DRAG: AX = a velocity -> AX through one step's drag (a 64th of it,
; rounded up, toward 0) and clamped to +-BZ_VMAXG (128.10.7.2).  CL = 6.
; Clobbers DX.  (The drag never changes the sign, so one side is clamped.)
%macro BZ_DRAG 0
    or ax, ax
    js %%neg
    mov dx, ax
    add dx, 63
    shr dx, cl
    sub ax, dx
    cmp ax, BZ_VMAXG
    jle %%ok
    mov ax, BZ_VMAXG
    jmp short %%ok
%%neg:
    mov dx, 63
    sub dx, ax
    shr dx, cl
    add ax, dx
    cmp ax, -BZ_VMAXG
    jge %%ok
    mov ax, -BZ_VMAXG
%%ok:
%endmacro

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
; bz_step - ONE STEP of physics v1, in SPEC.md 128.10.7.3's binding order (the
; numbers below are its steps).  DS = ours.  Preserves CX and ES (the frame
; loop's count and segment) and nothing else.
; -----------------------------------------------------------------------------
bz_step:
    push cx
    push es
    mov es, [bz_cseg]
    cmp byte [bz_pokd], 0       ; C: the centre's cell.  The window is centred
    jne .poked                  ; on it already unless a harness POKED the ball
.unpoked:                       ; and said so (bz_pokd: the hot path pays one
                                ; byte test, not the cell compares)
    ; ---- 1. the keys ----
    mov bl, [bz_keys]
    cmp byte [bz_mode], 0
    je .keys
    call bz_auto                ; the benchmark: BL = the keys it would hold
.keys:
    ; ---- 2. forces ----
    cmp byte [bz_air], 0
    jne .air
    xor di, di                  ; DI, BP = the arrows on (gvx, gvy), pushed
    xor bp, bp                  ; along the screen through the ground (128.10.7.2)
    test bl, BZ_K_R
    jz .k1
    add di, BZ_ACCG             ; Right (+A, -A)
    sub bp, BZ_ACCG
.k1:
    test bl, BZ_K_L
    jz .k2
    sub di, BZ_ACCG             ; Left (-A, +A)
    add bp, BZ_ACCG
.k2:
    test bl, BZ_K_D
    jz .k3
    add di, BZ_ACCG             ; Down (+A, +A)
    add bp, BZ_ACCG
.k3:
    test bl, BZ_K_U
    jz .k4
    sub di, BZ_ACCG             ; Up (-A, -A)
    sub bp, BZ_ACCG
.k4:
    mov cl, 6                   ; (BZ_DRAG's shift)
    mov bx, [bz_tsx]            ; C's slopes (bz_win9f: 0 off a plane floor)
    mov si, [bz_tsy]
    mov ax, bx                  ; gvx += arrows - BZ_GSL sx; the drag; the clamp
    shl ax, 1
    shl ax, 1
    neg ax
    add ax, di
    add ax, [bz_gvx]
    BZ_DRAG
    mov [bz_gvx], ax
    mov ax, si                  ; gvy the same with sy
    shl ax, 1
    shl ax, 1
    neg ax
    add ax, bp
    add ax, [bz_gvy]
    BZ_DRAG
    mov [bz_gvy], ax
    ; gvz = (sx gvx + sy gvy) >> 2: the floor's vertical rate under the ball
    xor cx, cx
    mov dx, bx
    or dx, si
    jz .gvz                     ; a flat floor: 0, and no product
    mov ax, [bz_gvx]
    call bz_smul                ; (AX x BX)
    mov cx, ax
    mov ax, [bz_gvy]
    mov bx, si
    call bz_smul
    add cx, ax
    sar cx, 1
    sar cx, 1
.gvz:
    mov [bz_gvz], cx
    jmp short .move
.air:
    mov ax, [bz_gvz]            ; airborne: gravity, clamped; no arrows, slope
    sub ax, BZ_G                ; or drag
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
    mov ax, [bz_gz]             ; zq = floor(start z / 64), quarter px, and the
    mov dx, [bz_gz + 2]         ; climb on top grounded: a neighbour BLOCKS
    BZ_Q64                      ; when its h4 > zq (128.10.7.3)
    cmp byte [bz_air], 0
    jne .zq
    add ax, BZ_CLIMB * 4        ; + 1,024 / 64
.zq:
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
    mov ax, [bz_gvx]            ; a new cell: the START's ground position kept
    cwd                         ; for the fallback's undo (gx - gvx: only the
    neg dx                      ; move has touched it yet)
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
    call bz_win9f               ; the centre's new cell
.w3:
    mov si, bz_nbr + BZN_C
    test byte [si + 2], 0fh
    jnz .walls
    cmp byte [si], BZ_ZOPEN
    jne .walls
    jmp .respawn                ; an OPEN cell (or outside the grid)
    ; ---- 5. walls: the circle ----
.walls:
    mov dl, [bz_gx + 1]
    and dl, 15                  ; DL = u, DH = v: integer gu inside C
    mov dh, [bz_gy + 1]
    and dh, 15
    cmp dl, BZ_RAD
    jae .xe
    mov si, bz_nbr + BZN_W      ; west, at its point (16, v)
    mov bp, dx
    mov dl, 16
    call bz_blocks
    mov dx, bp
    jnc .y
    mov ax, [bz_gx + 1]
    and al, 0f0h
    add al, BZ_RAD              ; the centre BZ_RAD from the edge, no fraction
    mov [bz_gx + 1], ax
    mov byte [bz_gx], 0
    cmp word [bz_gvx], 0
    jge .y
    mov word [bz_gvx], 0
    jmp short .y
.xe:
    cmp dl, 16 - BZ_RAD
    jbe .y
    mov si, bz_nbr + BZN_E      ; east, at (0, v)
    mov bp, dx
    mov dl, 0
    call bz_blocks
    mov dx, bp
    jnc .y
    mov ax, [bz_gx + 1]
    and al, 0f0h
    add al, 16 - BZ_RAD
    mov [bz_gx + 1], ax
    mov byte [bz_gx], 0
    cmp word [bz_gvx], 0
    jle .y
    mov word [bz_gvx], 0
.y:                             ; (u is the one before the x push, as the model)
    cmp dh, BZ_RAD
    jae .ye
    mov si, bz_nbr + BZN_N      ; north, at (u, 16)
    mov dh, 16
    call bz_blocks
    jnc .corner
    mov ax, [bz_gy + 1]
    and al, 0f0h
    add al, BZ_RAD
    mov [bz_gy + 1], ax
    mov byte [bz_gy], 0
    cmp word [bz_gvy], 0
    jge .corner
    mov word [bz_gvy], 0
    jmp short .corner
.ye:
    cmp dh, 16 - BZ_RAD
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
    cmp word [bz_gvy], 0
    jle .corner
    mov word [bz_gvy], 0
.corner:
    mov dl, [bz_gx + 1]         ; the corner: only within BZ_RAD of both a
    and dl, 15                  ; west or east edge and a north or south one
    sub dl, BZ_RAD              ; (u, v outside 6 .. 10)
    cmp dl, 16 - 2 * BZ_RAD
    jbe .nocorner
    mov dh, [bz_gy + 1]
    and dh, 15
    sub dh, BZ_RAD
    cmp dh, 16 - 2 * BZ_RAD
    jbe .nocorner
    call bz_corner
.nocorner:
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
    xor ax, ax                  ; each velocity whose cell coordinate changed
    test bp, 1
    jz .ux
    mov [bz_gvx], ax
.ux:
    test bp, 2
    jz .uy
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
    ; ---- 6. the floor ----
.floor:
    mov si, bz_nbr + BZN_C
    mov al, [si + 2]
    and al, 0fh
    cmp al, BZ_KFLOOR
    je .solid
    cmp al, BZ_KGOAL
    je .solid
    cmp byte [bz_air], 0
    je .takeoff                 ; grounded over no floor: off it goes
    or al, al
    jnz .end                    ; (no other kind is under an airborne ball)
    mov al, [si]                ; VOID: below its kill height, 4 z0 px?
    cbw
    shl ax, 1
    shl ax, 1
    cmp [bz_gz + 1], ax
    jge .end
    jmp .respawn
.solid:
    mov dl, [bz_gx + 1]
    and dl, 15
    mov dh, [bz_gy + 1]
    and dh, 15
    call bz_h4
    mov bx, ax                  ; BX = h4, the floor under the centre
    cmp byte [bz_air], 0
    jne .airsolid
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
    jle .takeoff
    mov ax, bx                  ; z = h: the ball follows the floor
    call bz_setz
    jmp short .safe
.takeoff:
    mov byte [bz_air], 1        ; TAKE OFF, keeping the floor's gvz
    mov ax, [bz_gz + 1]
    mov [bz_ztop], ax
    mov ax, [bz_gvz]
    cwd
    add [bz_gz], ax
    adc [bz_gz + 2], dx
    jmp short .end
.airsolid:
    ; airborne: LAND when z <= h, i.e. when h4 > floor((z - 1) / 64)
    mov ax, [bz_gz]
    mov dx, [bz_gz + 2]
    sub ax, 1
    sbb dx, 0
    BZ_Q64
    cmp bx, ax
    jle .end
    mov ax, [bz_gvz]
    neg ax
    mov [bz_lvz], ax            ; the impact speed...
    mov ax, bx
    sar ax, 1
    sar ax, 1                   ; h in whole px (floor)
    neg ax
    add ax, [bz_ztop]
    jge .lf
    xor ax, ax
.lf:
    mov [bz_lfall], ax          ; ...and the drop: wave 2's input
    mov ax, bx
    call bz_setz
    xor ax, ax
    mov [bz_gvz], ax
    mov [bz_air], al
    inc word [bz_nland]
    ; ---- 8. SAFE and the goal (grounded) ----
.safe:
    mov si, bz_nbr + BZN_C
    test byte [si + 3], BZ_FSAFE
    jz .goal
    mov ax, [bz_nwin]
    mov [bz_safe], ax
.goal:
    mov al, [si + 2]
    and al, 0fh
    cmp al, BZ_KGOAL
    jne .end
    cmp byte [bz_mode], 0       ; play only: the benchmark ignores it
    jne .end
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
    call bz_place
    inc word [bz_nfall]
    mov byte [bz_resp], 1
    call bz_derive
    xor ax, ax                  ; a respawn's screen velocity is 0
    mov [bz_vx], ax
    mov [bz_vy], ax
    jmp .count

; -----------------------------------------------------------------------------
; bz_corner - step 5's corner: the centre within BZ_RAD of both edges at a
; corner (so neither edge neighbour blocked - one that did put the centre
; exactly BZ_RAD from its edge), the corner neighbour blocks, and the corner
; point is nearer than BZ_RAD: the centre pushed out along the normal and the
; velocity's component into the corner removed (128.10.7.3, the table's rule).
; ES = the course.  Clobbers AX, BX, CX, DX, SI, DI, BP.
; -----------------------------------------------------------------------------
bz_corner:
    mov dl, [bz_gx + 1]
    and dl, 15
    mov dh, [bz_gy + 1]
    and dh, 15
    xor bp, bp                  ; BP: bit 0 east, bit 1 south
    mov bx, BZN_NW              ; BX = the corner cell's window offset
    cmp dl, BZ_RAD              ; across: west (|du| = u) or east (16 - u)
    jb .cw
    cmp dl, 16 - BZ_RAD
    jbe .out
    mov al, 16
    sub al, dl
    mov bx, BZN_NE
    inc bp
    jmp short .cy
.cw:
    mov al, dl
.cy:
    cmp dh, BZ_RAD              ; down: north (|dv| = v) or south (16 - v)
    jb .cn
    cmp dh, 16 - BZ_RAD
    jbe .out
    mov ah, 16
    sub ah, dh
    add bx, BZN_SW - BZN_NW
    or bp, 2
    jmp short .ct
.cn:
    mov ah, dh
.ct:
    mov cl, al                  ; the entry: 3 (6 |du| + |dv|)
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
    imul cx                     ; sum can pass a word (|v| 543, |n| 64)
    mov bx, ax
    mov bp, dx
    mov ax, [bz_gvy]
    imul si
    add ax, bx
    adc dx, bp
    call bz_sar6
    or ax, ax
    jns .out                    ; not moving into the corner
    mov bx, ax
    imul cx                     ; gvx -= (d nx) >> 6
    call bz_sar6
    sub [bz_gvx], ax
    mov ax, bx
    imul si                     ; gvy -= (d ny) >> 6
    call bz_sar6
    sub [bz_gvy], ax
.out:
    ret

; -----------------------------------------------------------------------------
; bz_blocks - does the window cell at SI block the ball at its point (DL = u,
; DH = v, 0 .. 16)?  A WALL always; a plane floor (FLOOR, GOAL) when its h4
; there is above [bz_zq] - the step's START z, plus the climb grounded; VOID
; and the reserved kinds never.  CF = 1 blocks.  Clobbers AX, BX, CX.
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
    jl .yes
.no:
    clc
    ret
.yes:
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
    mov ax, [bz_nwin]
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

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
