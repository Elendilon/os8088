; =============================================================================
; os8088 - apps/skies/cs3d.inc
;
; THE GEOMETRY (SPEC.md 88.5). Fixed point throughout, 8086 only, and the two
; expensive instructions on this machine - imul at ~140 clocks and idiv at
; ~170 - are what the whole shape of this file is arranged around.
;
; ANGLES ARE SIXTEEN BITS, 65536 to the turn, and the sine table has 1,024
; entries indexed by the top ten bits: Tank's byte angles were enough for a
; tank that yaws, but a horizon that moves in 1.4-degree steps jumps eight
; pixels of pitch at a time on Hercules, and 0.35 degrees is two.
;
; ONE MATRIX A FRAME, NINE MULTIPLIES A VERTEX. The camera's right, up and
; forward vectors are built once a frame from heading, pitch and roll, and a
; world point is M (w - p). The eye is never more than CS_CEIL up and nothing
; further than CS_FAR is transformed, so no partial sum overflows a word.
;
; A BOX IS EIGHTEEN MULTIPLIES, NOT SEVENTY-TWO. Every solid is a STACK of
; levels (wx, h, wz), a level being the four points (+-wx, h, +-wz). M is
; linear, so a level's corners are C + h M1 +- wx M0 +- wz M2: three scaled
; COLUMNS - nine multiplies - and then adds. Tank's shape cache (SPEC.md 85.5)
; generalised to a camera that pitches and rolls.
;
; SS != DS (CLAUDE.md): nothing here indexes with BP.
; =============================================================================

; AX = (AX * BX) >> 15, signed. Clobbers DX. Tank's MUL14 one bit over: the
; sine table and every matrix entry are Q15 here (SPEC.md 88.5.3), so the
; product is moved LEFT once and DX kept - two shifts fewer than Q14 on a
; machine that does five hundred of these a frame. The name is kept because
; every caller means "a fraction times a value" by it.
%macro MUL14 0
    imul bx
    shl ax, 1
    rcl dx, 1
    mov ax, dx
%endmacro

; -----------------------------------------------------------------------------
; cs_sin / cs_cos - AX = an angle; out AX = sin / cos x 32768, clamped to
;                   32767. Clobbers BX, CX.
; -----------------------------------------------------------------------------
cs_cos:
    add ax, 16384
cs_sin:
    mov bx, ax
    mov cl, 5                       ; the top ten bits, as a word index
    shr bx, cl
    and bx, 0x7FE
    mov ax, [cs_sintab + bx]
    ret

; -----------------------------------------------------------------------------
; cs_matrix - the camera matrix, once a frame, from [cs_hdg]/[cs_pitch]/
;             [cs_roll]; and the world's up vector in camera space out of it
; clobbers everything
;
; Rows are the camera's right, up and forward vectors in world coordinates,
; so that c = M d is (d.right, d.up, d.forward). With heading h, pitch p and
; roll r (right wing down positive):
;   right   = ( cr ch + sr sh sp,  -sr cp,  -cr sh + sr ch sp )
;   up      = ( sr ch - cr sh sp,   cr cp,  -sr sh - cr ch sp )
;   forward = ( sh cp,              sp,      ch cp            )
; -----------------------------------------------------------------------------
cs_matrix:
    mov ax, [cs_hdg]
    call cs_sin
    mov [cs_sinh], ax
    mov ax, [cs_hdg]
    call cs_cos
    mov [cs_cosh], ax
    mov ax, [cs_pitch]
    call cs_sin
    mov [cs_sinp], ax
    mov ax, [cs_pitch]
    call cs_cos
    mov [cs_cosp], ax
    mov ax, [cs_roll]
    call cs_sin
    mov [cs_sinr], ax
    mov ax, [cs_roll]
    call cs_cos
    mov [cs_cosr], ax

    mov al, [cs_conebase]             ; the cull's cone: the backend's
    mov [cs_cone], al                 ; factor, or all of the depth past 15
    mov ax, [cs_pitch]                ; degrees of pitch or roll
    or ax, ax
    jns .p
    neg ax
.p:
    cmp ax, 2730
    jg .wide
    mov ax, [cs_roll]
    or ax, ax
    jns .r
    neg ax
.r:
    cmp ax, 2730
    jle .cone
.wide:
    mov byte [cs_cone], 2
.cone:
    mov ax, [cs_sinh]                 ; t1 = sh sp, t2 = ch sp
    mov bx, [cs_sinp]
    MUL14
    mov [cs_t1], ax
    mov ax, [cs_cosh]
    mov bx, [cs_sinp]
    MUL14
    mov [cs_t2], ax

    mov ax, [cs_cosr]                 ; m00 = cr ch + sr t1
    mov bx, [cs_cosh]
    MUL14
    mov si, ax
    mov ax, [cs_sinr]
    mov bx, [cs_t1]
    MUL14
    add ax, si
    mov [cs_m + 0], ax
    mov ax, [cs_sinr]                 ; m01 = -sr cp
    mov bx, [cs_cosp]
    MUL14
    neg ax
    mov [cs_m + 2], ax
    mov ax, [cs_sinr]                 ; m02 = sr t2 - cr sh
    mov bx, [cs_t2]
    MUL14
    mov si, ax
    mov ax, [cs_cosr]
    mov bx, [cs_sinh]
    MUL14
    sub si, ax
    mov [cs_m + 4], si
    mov ax, [cs_sinr]                 ; m10 = sr ch - cr t1
    mov bx, [cs_cosh]
    MUL14
    mov si, ax
    mov ax, [cs_cosr]
    mov bx, [cs_t1]
    MUL14
    sub si, ax
    mov [cs_m + 6], si
    mov ax, [cs_cosr]                 ; m11 = cr cp
    mov bx, [cs_cosp]
    MUL14
    mov [cs_m + 8], ax
    mov ax, [cs_sinr]                 ; m12 = -sr sh - cr t2
    mov bx, [cs_sinh]
    MUL14
    mov si, ax
    mov ax, [cs_cosr]
    mov bx, [cs_t2]
    MUL14
    add ax, si
    neg ax
    mov [cs_m + 10], ax
    mov ax, [cs_sinh]                 ; m20 = sh cp
    mov bx, [cs_cosp]
    MUL14
    mov [cs_m + 12], ax
    mov ax, [cs_sinp]                 ; m21 = sp
    mov [cs_m + 14], ax
    mov ax, [cs_cosh]                 ; m22 = ch cp
    mov bx, [cs_cosp]
    MUL14
    mov [cs_m + 16], ax

    mov ax, [cs_m + 2]              ; the world's up vector in camera space is
    mov [cs_nx], ax                 ; the second COLUMN (SPEC.md 88.4.1)
    mov ax, [cs_m + 8]
    mov [cs_ny], ax
    mov ax, [cs_m + 14]
    mov [cs_nz], ax
    ret

; -----------------------------------------------------------------------------
; cs_rot - AX/BX/CX = a vector; out AX/BX/CX = M times it. Clobbers DX, SI, DI.
; -----------------------------------------------------------------------------
cs_rot:
    mov [cs_rvx], ax
    mov [cs_rvy], bx
    mov [cs_rvz], cx
    mov si, cs_m
    call cs_dot
    mov [cs_rox], ax
    call cs_dot
    mov [cs_roy], ax
    call cs_dot
    mov cx, ax
    mov ax, [cs_rox]
    mov bx, [cs_roy]
    ret

; cs_dot - SI = three matrix words; out AX = their dot with cs_rv*, SI += 6.
; Clobbers BX, DX, DI.
cs_dot:
    mov ax, [cs_rvx]
    mov bx, [si]
    MUL14
    mov di, ax
    mov ax, [cs_rvy]
    mov bx, [si+2]
    MUL14
    add di, ax
    mov ax, [cs_rvz]
    mov bx, [si+4]
    MUL14
    add ax, di
    add si, 6
    ret

; cs_colscale - AX = a scalar, SI = the matrix column's first word, DI = three
; words to fill with the scaled column. Clobbers AX, BX, CX, DX.
cs_colscale:
    mov cx, ax
    mov bx, [si]
    MUL14
    mov [di], ax
    mov ax, cx
    mov bx, [si+6]
    MUL14
    mov [di+2], ax
    mov ax, cx
    mov bx, [si+12]
    MUL14
    mov [di+4], ax
    ret

; -----------------------------------------------------------------------------
; cs_ktabs - the two projection tables, once a bracket (SPEC.md 85.5.3,
;            rebucketed for a 16 km world - 88.5)
;
; Row i stands for a depth: i itself below 1,024; 1,024 + 4(i - 1,024) + 2 to
; row 1,791; and 4,096 + 64(i - 1,792) + 32 beyond - the bucket's centre, so
; the error is signed both ways. Depths under CS_NEAR take its value.
; -----------------------------------------------------------------------------
cs_ktabs:
    xor si, si
.e:
    mov ax, si
    shr ax, 1                       ; AX = i
    cmp ax, 1024
    jb .z1
    cmp ax, 1792
    jb .z2
    sub ax, 1792
    mov cl, 6
    shl ax, cl
    add ax, 4096 + 32
    jmp short .zz
.z2:
    sub ax, 1024
    shl ax, 1
    shl ax, 1
    add ax, 1024 + 2
    jmp short .zz
.z1:
    cmp ax, CS_NEAR
    jae .zz
    mov ax, CS_NEAR
.zz:
    mov cx, ax                      ; CX = z
    mov ax, [cs_sclx]
    mov dx, 2048
    mul dx                          ; DX:AX = sclx x 2048
    div cx
    mov [cs_kx + si], ax
    mov ax, [cs_scly]
    mov dx, 2048
    mul dx
    div cx
    mov [cs_ky + si], ax
    add si, 2
    cmp si, 4096
    jb .e
    ret

; -----------------------------------------------------------------------------
; cs_project - one camera-space point onto the box
; in:  AX = cx, BX = cy, CX = cz (cz >= CS_NEAR)
; out: AX = screen x, BX = screen y (box coords, clamped to +-4000 about the
;      centre).  clobbers CX, DX, SI, DI
; -----------------------------------------------------------------------------
cs_project:
    mov si, bx                      ; SI = cy
    mov bx, cx                      ; the depth picks the row...
    cmp bx, [cs_pfloor]
    jb .near
    mov cl, [cs_pshr]
    shr bx, cl                      ; ...in whole metres (88.5.6)
    cmp bx, 1024
    jb .row
    cmp bx, 4096
    jb .mid
    sub bx, 4096                    ; 4096.. : every 64 units, from row 1792
    mov cl, 6
    shr bx, cl
    add bx, 1792
    cmp bx, 2047
    jbe .row
    mov bx, 2047
    jmp short .row
.mid:
    sub bx, 1024                    ; 1024..4095: every 4 units, from row 1024
    shr bx, 1
    shr bx, 1
    add bx, 1024
.row:
    shl bx, 1
    imul word [cs_kx + bx]          ; DX:AX = cx x kx
    call [cs_pshiftp]
    add ax, [cs_vcx]
    mov di, ax                      ; DI = screen x
    mov ax, si
    imul word [cs_ky + bx]
    call [cs_pshiftp]
    neg ax                          ; screen y grows DOWNWARD
    add ax, [cs_vcy]
    mov bx, ax
    mov ax, di
    ret
    ; --- under the table's floor: a ground polygon's near plane is 4 m
    ;     (88.5.5), where k would not fit a word, so the two divides are
    ;     real ones - clamped first, because a quotient past +-4000 would
    ;     not fit either and an 8088 faults on that ------------------------
.near:
    mov di, cx                      ; DI = z, 1..39
    mov cx, ax                      ; CX = cx
    mov ax, di
    mov bx, 9
    mul bx                          ; AX = 9 z: |cx| past it clamps (4000/443)
    mov bx, cx
    or bx, bx
    jns .ax
    neg bx
.ax:
    cmp bx, ax
    ja .xcl
    mov ax, cx
    imul word [cs_sclx]
    idiv di
    jmp short .xd
.xcl:
    mov ax, 4000
    or cx, cx
    jns .xd
    neg ax
.xd:
    add ax, [cs_vcx]
    mov cx, ax                      ; CX = screen x
    mov ax, di
    mov bx, 14
    mul bx                          ; AX = 14 z (4000/285)
    mov bx, si
    or bx, bx
    jns .ay
    neg bx
.ay:
    cmp bx, ax
    ja .ycl
    mov ax, si
    imul word [cs_scly]
    idiv di
    jmp short .yd
.ycl:
    mov ax, 4000
    or si, si
    jns .yd
    neg ax
.yd:
    neg ax
    add ax, [cs_vcy]
    mov bx, ax
    mov ax, cx
    ret

; cs_pshift - AX = (DX:AX) >> 11, clamped to +-4000 (SPEC.md 85.5.3)
cs_pshift:
    cmp dx, 125
    jge .hi
    cmp dx, -126
    jl .lo
    mov al, ah
    mov ah, dl
    sar ax, 1
    sar ax, 1
    sar ax, 1
    ret
.hi:
    mov ax, 4000
    ret
.lo:
    mov ax, -4000
    ret

; ...and the same at the two finer scales (88.5.6): quarter metres shift
; 13, sixteenths 15, each clamped by the product's high word first
cs_pshift13:
    cmp dx, 500
    jge cs_pshift.hi
    cmp dx, -501
    jl cs_pshift.lo
    mov al, ah
    mov ah, dl
    sar ax, 1
    sar ax, 1
    sar ax, 1
    sar ax, 1
    sar ax, 1
    ret
cs_pshift15:
    cmp dx, 2000
    jge cs_pshift.hi
    cmp dx, -2001
    jl cs_pshift.lo
    shl ax, 1
    rcl dx, 1
    mov ax, dx
    ret
cs_pshtab: dw cs_pshift, cs_pshift13, cs_pshift15

; -----------------------------------------------------------------------------
; cs_scale - the object's transform scale (SPEC.md 88.5.6): sixteenths of a
;            metre when its reach from the eye - the world offset's Manhattan
;            length, which no component of it rotated can exceed, plus the
;            radius - is under 2,048 m AND the radius under 1,024 (so that
;            the difference of two vertices fits a word as well: the
;            clippers subtract them), quarters under 8,192 and 4,096, whole
;            metres beyond: the finest that cannot overflow. The origin is ONE
;            rotation, at that scale, FROM THE EYE'S 16.8 POSITION, and its
;            whole-metre form for the size tests is that shifted back. The
;            first build rotated whole metres from a whole-metre eye, and a
;            runway transformed that way jumped a metre across between
;            frames: 20 pixels at 22 m.
; in:  SI = the cs_vis record (ptr, dx, dy, dz whole metres), [cs_obj]
; out: [cs_pshr], [cs_pfloor], [cs_pshiftp], cs_scx/y/z, cs_ocx/y/z.
;      Clobbers everything
; -----------------------------------------------------------------------------
cs_scale:
    xor ax, ax                      ; the world offset's Manhattan length...
    mov cx, 3
    push si
.l1:
    mov bx, [si + 2]
    or bx, bx
    jns .a1
    neg bx
.a1:
    add ax, bx
    jc .s0
    inc si
    inc si
    loop .l1
    pop si                          ; ...which no component of the rotated
    push si                         ; offset can exceed (it is over the
    mov si, [si]                    ; Euclidean length)...
    mov si, [si + CSO_MODEL]
    mov bx, [si + CSM_RAD]
    add ax, bx                      ; ...plus the radius: no vertex is further
    jc .s0
    mov cl, 4
    cmp ax, 2048                    ; sixteenths: every coordinate under 2^15,
    jae .q                          ; and every DIFFERENCE of two, which the
    cmp bx, 1024                    ; clippers subtract: twice the radius
    jb .have
.q:
    mov cl, 2
    cmp ax, 8192
    jae .s0
    cmp bx, 4096
    jb .have
.s0:
    xor cl, cl
.have:
    pop si
    mov [cs_pshr], cl
    mov ax, CS_NEAR
    shl ax, cl
    mov [cs_pfloor], ax
    mov bl, cl
    xor bh, bh
    mov ax, [cs_pshtab + bx]        ; 0, 2, 4 are the table's byte offsets
    mov [cs_pshiftp], ax
    ; --- the origin from the 16.8 eye, at the scale ------------------------
    mov bx, [cs_obj]
    mov ax, [bx + CSO_X]
    mov si, cs_px
    call cs_sdiff
    push ax
    mov ax, [bx + CSO_Z]
    mov si, cs_pz
    call cs_sdiff
    push ax
    mov ax, [bx + CSO_Y]
    mov si, [cs_plane]
    sub ax, [si + CSP_EYE]          ; the eye is that much above the wheels
    mov si, cs_py
    call cs_sdiff
    mov bx, ax
    pop cx
    pop ax
    call cs_rot
    mov [cs_scx], ax
    mov [cs_scy], bx
    mov [cs_scz], cx
    mov cl, [cs_pshr]               ; ...and in whole metres, for the tests
    sar ax, cl
    mov [cs_ocx], ax
    sar bx, cl
    mov [cs_ocy], bx
    sar cx, cl
    mov [cs_ocz], cx
    ret

; cs_nearat - AX = a near plane in metres: [cs_near] at the object's scale
cs_nearat:
    mov cl, [cs_pshr]
    shl ax, cl
    mov [cs_near], ax
    ret

; cs_sdiff - AX = a whole-metre coordinate, SI -> a 16.8 position: out AX =
;            (coordinate - position) in 1/2^[cs_pshr] metres. Clobbers CX, DX
cs_sdiff:
    mov dx, 256
    imul dx                         ; DX:AX = the coordinate, 16.8
    sub ax, [si]
    sbb dx, [si + 2]
    mov cl, 8
    sub cl, [cs_pshr]
.s:
    sar dx, 1
    rcr ax, 1
    dec cl
    jnz .s
    ret

; =============================================================================
; The scene: cull, sort, draw (SPEC.md 88.5)
; =============================================================================

; -----------------------------------------------------------------------------
; cs_scene - every object worth drawing this frame, far to near
; clobbers everything
; -----------------------------------------------------------------------------
cs_scene:
    mov word [cs_nvisn], 0
    mov si, cs_rwobj                ; the runway first...
    call cs_consider
    mov si, cs_objtab               ; ...then the table
    mov cx, CS_NOBJ
.o:
    push cx
    push si
    call cs_consider
    pop si
    pop cx
    add si, CSO_SIZE
    loop .o
    ; --- the ground shapes, far to near, then the solids ---------------------
    mov byte [cs_pass], CSM_FLAT
    call cs_drawpass
    mov byte [cs_pass], CSM_STACK
    call cs_drawpass
    ret

; cs_skipclr - every object looked at on the next frame: the aeroplane has
;              been moved by something other than flying
cs_skipclr:
    mov si, cs_objtab
    mov cx, CS_NOBJ
.o:
    mov word [si + CSO_SKIP], 0
    add si, CSO_SIZE
    loop .o
    ret

cs_drawpass:
    mov si, cs_vkey
    mov cx, [cs_nvisn]
    jcxz .out
.v:
    push cx
    push si
    mov si, [si + 2]                ; the key's record
    mov bx, [si]
    mov bx, [bx + CSO_MODEL]
    mov al, [bx + CSM_TYPE]
    cmp al, [cs_pass]
    jne .next
    call cs_drawobj
.next:
    pop si
    pop cx
    add si, 4
    loop .v
.out:
    ret

; -----------------------------------------------------------------------------
; cs_consider - cull object SI, and file it in cs_vis by depth if it survives
; clobbers everything but SI... no: everything (SI is the caller's to keep)
;
; A 32-bit distance box first, so the 16-bit arithmetic is never entered on
; a difference that would not fit it; then the Manhattan range the object
; asks for; then the transformed origin against the frustum, the model's
; radius folded in.
; -----------------------------------------------------------------------------
cs_consider:
    mov [cs_obj], si
    mov ax, [si + CSO_SKIP]         ; out of range last time by enough that
    sub ax, [cs_last]               ; it cannot be back yet (88.5.2)
    jg .out
    mov ax, [si + CSO_X]            ; the world is 16-bit metres and so is
    sub ax, [cs_ex]                 ; the eye's whole part, so the difference
    jo .far                         ; fits a word unless the subtraction
    mov [cs_ddx], ax                ; OVERFLOWS - and that is a flag
    mov ax, [si + CSO_Z]
    sub ax, [cs_ez]
    jo .far
    mov [cs_ddz], ax
    ; --- the Manhattan range ------------------------------------------------
    mov ax, [cs_ddx]
    or ax, ax
    jns .a1
    neg ax
.a1:
    mov bx, [cs_ddz]
    or bx, bx
    jns .a2
    neg bx
.a2:
    cmp ax, CS_FAR
    jae .far
    cmp bx, CS_FAR
    jae .far
    add ax, bx
    sub ax, [si + CSO_RANGE]
    jbe .inrange
    ; --- out of range by AX metres: not looked at again for AX/16 ticks.
    ;     The aeroplane covers under 5 m a tick at VMAX, so the margin is
    ;     threefold; a reset clears every skip (cs_skipclr) -----------------
    mov cl, 4
    shr ax, cl
    add ax, [cs_last]
    mov [si + CSO_SKIP], ax
    jmp .out
.far:                               ; sixteen kilometres or more away
    mov ax, [cs_last]
    add ax, 256
    mov [si + CSO_SKIP], ax
    jmp .out
.inrange:
    mov ax, [si + CSO_Y]
    sub ax, [cs_ey]
    mov [cs_ddy], ax
    ; --- drawn last frame: it is filed without the cone, which cs_drawobj's
    ;     frustum repeats exactly after the rotation it has to do anyway;
    ;     the bit goes and comes back if the frustum still has it (88.5.1)
    test byte [si + CSO_FLAGS + 1], CSO_SEEN >> 8
    jz .cone
    and byte [si + CSO_FLAGS + 1], ~(CSO_SEEN >> 8)
    mov ax, [cs_ddx]
    mov bx, [cs_sinh]
    MUL14
    mov cx, ax
    mov ax, [cs_ddz]
    mov bx, [cs_cosh]
    MUL14
    add cx, ax                      ; CX = along, the sort key
    jmp .file
.cone:
    ; --- the cheap cone first: along the heading and across it, two
    ;     multiplies each, so an object behind the aeroplane costs no
    ;     rotation. |across| <= 0.75 along + r + |dy| is the frustum's own
    ;     x test with the height folded into the margin; past 15 degrees of
    ;     pitch or roll the factor goes to 1 (cs_matrix's [cs_cone]), a
    ;     right angle being wider than the view's diagonal at any attitude.
    ;     (The first build kept the margin in DX across the multiplies,
    ;     which write DX: the cone read twice its angle and every frame
    ;     rotated six objects it then refused - 88.5.1.)
    mov ax, [cs_ddx]
    mov bx, [cs_sinh]
    MUL14
    mov cx, ax
    mov ax, [cs_ddz]
    mov bx, [cs_cosh]
    MUL14
    add cx, ax                      ; CX = along
    mov si, [cs_obj]
    mov si, [si + CSO_MODEL]
    mov dx, [si + CSM_RAD]          ; DX = the radius...
    mov ax, [cs_ddy]
    or ax, ax
    jns .dy
    neg ax
.dy:
    add dx, ax                      ; ...plus |dy|
    mov ax, cx
    add ax, dx
    js .out                         ; wholly behind
    mov si, cx
    sar si, 1                       ; SI = 0.5 along...
    cmp byte [cs_cone], 0
    je .f
    mov ax, cx
    sar ax, 1
    sar ax, 1
    add si, ax                      ; ...or 0.75...
    cmp byte [cs_cone], 1
    je .f
    add si, ax                      ; ...or all of it
.f:
    add si, dx                      ; ...+ r + |dy|
    mov ax, [cs_ddx]
    mov bx, [cs_cosh]
    MUL14
    mov di, ax
    mov ax, [cs_ddz]
    mov bx, [cs_sinh]
    MUL14
    sub di, ax                      ; DI = across
    jns .ac
    neg di
.ac:
    cmp di, si
    jg .out
    ; --- file it, far to near: the record in filing order, and a KEY
    ;     (along, record) inserted into cs_vkey by `along`, which is the
    ;     depth before pitch and roll and orders the same objects the same
    ;     way. A key is four bytes, so the insertion shifts four and not
    ;     the record's ten. The rotation itself waits for cs_drawobj, so
    ;     an object the frustum refuses there has cost the cone's four
    ;     multiplies and not nine more (SPEC.md 88.5.1) ----------------------
.file:
    mov di, [cs_nvisn]
    cmp di, CS_NVIS
    jae .out
    inc word [cs_nvisn]
    mov ax, di
    shl ax, 1
    shl ax, 1
    add ax, di
    shl ax, 1                       ; AX = 10 x (ten bytes a slot)...
    add ax, cs_vis                  ; ...the new record
    mov bx, ax
    mov ax, [cs_obj]
    mov [bx], ax
    mov ax, [cs_ddx]
    mov [bx+2], ax
    mov ax, [cs_ddy]
    mov [bx+4], ax
    mov ax, [cs_ddz]
    mov [bx+6], ax
    mov [bx+8], cx
    shl di, 1
    shl di, 1
    add di, cs_vkey                 ; DI = the new key's slot
.ins:
    cmp di, cs_vkey
    je .place
    mov si, di
    sub si, 4
    cmp [si], cx                    ; the key above holds a NEARER object:
    jge .place                      ; it stays; else it moves down
    mov ax, [si]
    mov [di], ax
    mov ax, [si+2]
    mov [di+2], ax
    mov di, si
    jmp short .ins
.place:
    mov [di], cx
    mov [di+2], bx
.out:
    ret

; -----------------------------------------------------------------------------
; cs_drawobj - one filed object: its vertices, faces and edges
; in:  SI = the cs_vis entry.  clobbers everything
; -----------------------------------------------------------------------------
cs_drawobj:
    mov bx, [si]
    mov [cs_obj], bx
    call cs_scale                   ; the origin at the object's scale, from
    mov si, [cs_obj]                ; the 16.8 eye (88.5.6), and in metres
    mov si, [si + CSO_MODEL]
    mov dx, [si + CSM_RAD]          ; DX = the radius
    mov si, cx
    add si, dx
    js .no                          ; wholly behind the eye
    mov si, cx                      ; the frustum: |cx| <= f cz + r, f the
    sar si, 1                       ; backend's 0.5 or 0.75 (over the field's
    cmp byte [cs_conebase], 0       ; 0.45 and 0.58)...
    je .fx
    mov di, cx
    sar di, 1
    sar di, 1
    add si, di
.fx:
    add si, dx
    or ax, ax
    jns .b1
    neg ax
.b1:
    cmp ax, si
    jg .no
    mov si, cx                      ; ...and |cy| <= 0.375 cz + r (the
    sar si, 1                       ; tallest view is 0.26)
    sar si, 1
    mov di, si
    sar di, 1
    add si, di
    add si, dx
    or bx, bx
    jns .b2
    neg bx
.b2:
    cmp bx, si
    jg .no
    mov bx, [cs_obj]
    or byte [bx + CSO_FLAGS + 1], CSO_SEEN >> 8
    mov word [cs_oby0], 0x7FFF      ; nothing marked yet (cs_markacc)
    mov word [cs_oby1], -1
    mov word [cs_oblo], 0x00FF      ; ...cs_oblo = 0xFF, cs_obhi = 0
    mov si, [bx + CSO_MODEL]
    mov cx, [bx + CSO_FAR]
    jcxz .mdl
    mov ax, [cs_ocz]
    cmp ax, [bx + CSO_LOD]          ; the far model stands in beyond LOD
    jl .mdl
    mov si, cx
.mdl:
    mov [cs_mdl], si
    call cs_sizepx                  ; under two pixels across: not drawn
    mov cx, [cs_ocz]
    shl cx, 1
    or dx, dx
    jnz .big
    cmp ax, cx
    jb .out
.big:
    mov al, [si + CSM_NF]
    cmp al, 1
    sbb al, al                      ; AL = -1 for a wireframe (no faces)
    mov [cs_wire], al
    cmp byte [si + CSM_TYPE], CSM_FLAT
    je .flat
    ; --- a solid under CS_LODPX pixels across is its box, filled: one
    ;     rectangle off THREE projected points for a dozen transformed
    ;     vertices and five faces, and nobody can tell at that size.
    ;     (The first build tested this after cs_projall, through an SI that
    ;     routine had spent, so it compared a random word and no solid was
    ;     ever boxed: a basilica five kilometres off was four polygons and
    ;     ten milliseconds - 88.5.4) ---------------------------------------
    or al, al
    jnz .stack                      ; a wireframe keeps its edges
    call cs_sizepx
    mov cx, [cs_ocz]
    mov bx, cx
    shl cx, 1
    shl cx, 1
    add cx, bx
    shl cx, 1
    add cx, bx                      ; CX = 11 cz... and the radius is nearer
    or dx, dx                       ; the half-height than the height, so
    jnz .stack                      ; this is about 6 px
    cmp ax, cx
    jae .stack
    mov ax, [cs_ocz]
    sub ax, [si + CSM_RAD]
    cmp ax, CS_NEAR
    jl .stack                       ; reaching the near plane: the full path
    call cs_boxlod
    jmp short .out
.stack:
    mov ax, CS_NEAR
    call cs_nearat
    call cs_stackverts
    call cs_projall
    jmp short .full
.flat:
    mov ax, CS_NEARG                ; the ground goes under the wheels (88.5.5)
    call cs_nearat
    call cs_flatverts
    call cs_projall
.full:
    call cs_faces
    ; --- a solid under CS_EDGEPX pixels across keeps no outline: twelve
    ;     segments round a fifteen-pixel box cost more than the box, and at
    ;     that size the walls' patterns already tell them apart. A wireframe
    ;     is its edges and always draws them (88.4.7) --------------------
    mov si, [cs_mdl]
    cmp byte [si + CSM_NF], 0
    je .edg
    mov cx, [cs_ocz]
    cmp cx, 2600
    ja .out                         ; 24 cz would not fit: far and small
    mov ax, [si + CSM_RAD]
    mul word [cs_scly]
    or dx, dx
    jnz .edg
    mov bx, cx
    shl cx, 1
    add cx, bx
    shl cx, 1
    shl cx, 1
    shl cx, 1                       ; CX = 24 cz
    cmp ax, cx
    jb .out
.edg:
    call cs_edges
    cmp word [cs_obj], cs_rwobj     ; the runway's centreline is its own
    jne .out                        ; (88.6.2)
    call cs_rwline
.out:
    mov si, [cs_oby0]               ; what the object drew goes to the glass,
    mov di, [cs_oby1]               ; marked ONCE over its rows
    cmp si, di
    jg .none
    mov ax, [cs_oblo]
    mov [cs_mklo], ax               ; ...both bytes
    call cs_markrows
.none:
.no:
    ret

; cs_sizepx - DX:AX = 0.75 x the model's radius x scly, the size tests'
;             measure: CSM_RAD is |wx| + |wz| + h/2, a Manhattan bound that
;             the cull needs (it must never be under the true radius) and
;             that overstates a box's real extent by up to 3/1.73; three
;             quarters of it is still over. SI = the model. Clobbers BX.
cs_sizepx:
    mov ax, [si + CSM_RAD]
    mov bx, ax
    shr bx, 1
    shr bx, 1
    sub ax, bx
    mul word [cs_scly]
    ret

; -----------------------------------------------------------------------------
; cs_boxlod - the object as its box (88.5.4): the base centre C, the top
;             centre C + h M1 with h the last level's, and the point half
;             the base's width to the right of C, projected - three points
;             and three multiplies where the full path transforms every
;             vertex - and the rectangle they span filled in the wall ink
;             through cs_rect. The model is [cs_mdl]; C is in front by its
;             radius (the caller checked)
; -----------------------------------------------------------------------------
cs_boxlod:
    mov byte [cs_pshr], 0           ; the cull's origin: whole metres
    mov word [cs_pfloor], CS_NEAR
    mov word [cs_pshiftp], cs_pshift
    mov si, [cs_mdl]
    mov cl, [si + CSM_NV]           ; levels
    xor ch, ch
    mov si, [si + CSM_VERTS]
    mov ax, [si]                    ; the base's wx + wz, halved: near
    add ax, [si + 4]                ; enough to its width from any side
    shr ax, 1
    mov [cs_bw], ax
    dec cx
    mov ax, cx
    mov bx, 6
    mul bx
    add si, ax
    mov ax, [si + 2]                ; h of the top level
    mov si, cs_m + 2
    mov di, cs_col1
    call cs_colscale                ; col1 = h M1
    mov ax, [cs_ocx]
    mov bx, [cs_ocy]
    mov cx, [cs_ocz]
    call cs_project                 ; the base
    mov [cs_bx0], ax
    mov [cs_by1], bx
    mov ax, [cs_ocx]
    add ax, [cs_col1]
    mov bx, [cs_ocy]
    add bx, [cs_col1 + 2]
    mov cx, [cs_ocz]
    add cx, [cs_col1 + 4]
    cmp cx, CS_NEAR
    jl .out
    call cs_project                 ; the top
    mov [cs_by0], bx
    mov ax, [cs_ocx]
    add ax, [cs_bw]
    mov bx, [cs_ocy]
    mov cx, [cs_ocz]
    call cs_project                 ; the right edge
    sub ax, [cs_bx0]
    jg .w
    mov ax, 1                       ; a pixel at least
.w:
    mov cx, [cs_bx0]
    add cx, ax                      ; CX = x1
    neg ax
    add ax, [cs_bx0]                ; AX = x0
    mov bx, [cs_by0]
    mov dx, [cs_by1]
    cmp bx, dx
    jle .y
    xchg bx, dx                     ; seen from below: the top is lower
.y:
    push ax
    mov al, CSI_WALL
    call cs_setink
    pop ax
    call cs_rect
.out:
    ret

; -----------------------------------------------------------------------------
; cs_stackverts - a STACK's levels into cs_cxv/cyv/czv, four a level
; -----------------------------------------------------------------------------
cs_stackverts:
    mov si, [cs_mdl]
    mov cl, [si + CSM_NV]
    xor ch, ch
    mov ax, cx
    shl ax, 1
    shl ax, 1
    mov [cs_nv], ax                 ; four vertices a level
    mov si, [si + CSM_VERTS]
    xor di, di                      ; DI = the vertex index x 2
.lvl:
    push cx
    push si
    push di
    mov cl, [cs_pshr]               ; the level at the object's scale (88.5.6)
    mov ax, [si]                    ; wx
    shl ax, cl
    mov [cs_lwx], ax
    mov ax, [si+4]                  ; wz
    shl ax, cl
    mov [cs_lwz], ax
    mov ax, [si+2]                  ; h -> ey = h M1
    shl ax, cl
    mov si, cs_m + 2
    mov di, cs_col1
    call cs_colscale
    mov ax, [cs_scy]                ; the level's centre: C + ey
    add ax, [cs_col1 + 2]
    mov [cs_lcy], ax
    mov ax, [cs_scx]
    add ax, [cs_col1]
    mov [cs_lcx], ax
    mov ax, [cs_scz]
    add ax, [cs_col1 + 4]
    mov [cs_lcz], ax
    mov ax, [cs_lwx]
    mov si, cs_m
    mov di, cs_col0
    call cs_colscale                ; ex = wx M0
    mov ax, [cs_lwz]
    mov si, cs_m + 4
    mov di, cs_col2
    call cs_colscale                ; ez = wz M2
    pop di
    ; v0 = c + ex + ez, v1 = c - ex + ez, v2 = c - ex - ez, v3 = c + ex - ez
    mov ax, [cs_lcx]
    add ax, [cs_col0]
    add ax, [cs_col2]
    mov [cs_cxv + di], ax
    sub ax, [cs_col0]
    sub ax, [cs_col0]
    mov [cs_cxv + di + 2], ax
    sub ax, [cs_col2]
    sub ax, [cs_col2]
    mov [cs_cxv + di + 4], ax
    add ax, [cs_col0]
    add ax, [cs_col0]
    mov [cs_cxv + di + 6], ax
    mov ax, [cs_lcy]
    add ax, [cs_col0 + 2]
    add ax, [cs_col2 + 2]
    mov [cs_cyv + di], ax
    sub ax, [cs_col0 + 2]
    sub ax, [cs_col0 + 2]
    mov [cs_cyv + di + 2], ax
    sub ax, [cs_col2 + 2]
    sub ax, [cs_col2 + 2]
    mov [cs_cyv + di + 4], ax
    add ax, [cs_col0 + 2]
    add ax, [cs_col0 + 2]
    mov [cs_cyv + di + 6], ax
    mov ax, [cs_lcz]
    add ax, [cs_col0 + 4]
    add ax, [cs_col2 + 4]
    mov [cs_czv + di], ax
    sub ax, [cs_col0 + 4]
    sub ax, [cs_col0 + 4]
    mov [cs_czv + di + 2], ax
    sub ax, [cs_col2 + 4]
    sub ax, [cs_col2 + 4]
    mov [cs_czv + di + 4], ax
    add ax, [cs_col0 + 4]
    add ax, [cs_col0 + 4]
    mov [cs_czv + di + 6], ax
    add di, 8
    pop si
    add si, 6
    pop cx
    LOOPF .lvl
    ret

; -----------------------------------------------------------------------------
; cs_flatverts - a FLAT model's (x, z) pairs: C + x M0 + z M2, six multiplies
; -----------------------------------------------------------------------------
cs_flatverts:
    mov si, [cs_mdl]
    mov cl, [si + CSM_NV]
    xor ch, ch
    mov [cs_nv], cx
    mov si, [si + CSM_VERTS]
    xor di, di
.v:
    push cx
    push si
    push di
    mov cl, [cs_pshr]               ; the pair at the object's scale (88.5.6)
    mov ax, [si]
    shl ax, cl
    mov si, cs_m
    mov di, cs_col0
    call cs_colscale
    pop di
    pop si
    push si
    push di
    mov cl, [cs_pshr]
    mov ax, [si+2]
    shl ax, cl
    mov si, cs_m + 4
    mov di, cs_col2
    call cs_colscale
    pop di
    mov ax, [cs_scx]
    add ax, [cs_col0]
    add ax, [cs_col2]
    mov [cs_cxv + di], ax
    mov ax, [cs_scy]
    add ax, [cs_col0 + 2]
    add ax, [cs_col2 + 2]
    mov [cs_cyv + di], ax
    mov ax, [cs_scz]
    add ax, [cs_col0 + 4]
    add ax, [cs_col2 + 4]
    mov [cs_czv + di], ax
    add di, 2
    pop si
    add si, 4
    pop cx
    loop .v
    ret

; -----------------------------------------------------------------------------
; cs_projall - project every vertex in front of the near plane, flag the rest
; -----------------------------------------------------------------------------
cs_projall:
    mov cx, [cs_nv]
    jcxz .out
    xor di, di
.v:
    push cx
    mov cx, [cs_czv + di]
    cmp cx, [cs_near]
    jl .behind
    mov ax, [cs_cxv + di]
    mov bx, [cs_cyv + di]
    push di
    call cs_project
    pop di
    mov [cs_sxv + di], ax
    mov [cs_syv + di], bx
    mov word [cs_fv + di], 1
    ; --- in front, but outside the frustum's SIDES (|x| or |y| over 4z)?
    ;     Its projection was clamped, and a line through a clamped point is
    ;     bent: the face or edge it is on gets clipped in camera space
    ;     instead (88.5.7)
    mov cx, [cs_czv + di]
    mov ax, [cs_cxv + di]
    or ax, ax
    jns .px
    neg ax
.px:
    sar ax, 1
    sar ax, 1
    cmp ax, cx
    jg .side
    mov ax, [cs_cyv + di]
    or ax, ax
    jns .py
    neg ax
.py:
    sar ax, 1
    sar ax, 1
    cmp ax, cx
    jle .next
.side:
    mov word [cs_fv + di], 2
    jmp short .next
.behind:
    mov word [cs_fv + di], 0
.next:
    add di, 2
    pop cx
    loop .v
.out:
    ret

; -----------------------------------------------------------------------------
; cs_faces - every face of [cs_mdl]: near-clipped where it has to be, culled
;            by the sign of one cross product, filled
; -----------------------------------------------------------------------------
cs_faces:
    mov si, [cs_mdl]
    mov cl, [si + CSM_NF]
    xor ch, ch
    JCXZF .out
    mov si, [si + CSM_FACES]
.f:
    push cx
    push si
    mov al, [si]                    ; n
    xor ah, ah
    mov [cs_fn], ax
    mov al, [si+1]
    mov [cs_fink], al
    mov al, [si+2]
    mov [cs_fflags], al
    add si, 3
    mov [cs_fidx], si
    ; --- how many ends are behind the near plane, how many past a side ------
    mov cx, [cs_fn]
    xor dx, dx                      ; DL = behind, DH = outside
.cnt:
    lodsb
    xor ah, ah
    mov bx, ax
    shl bx, 1
    mov ax, [cs_fv + bx]
    or ax, ax
    jnz .c1
    inc dl
.c1:
    cmp al, 2
    jne .c2
    inc dh
.c2:
    loop .cnt
    cmp dl, [cs_fn]
    je .skip                        ; all behind
    or dx, dx
    jz .plain                       ; all in front and inside: the projected
    call cs_fclip                   ; points as they are; else clip in
    jmp short .fill                 ; camera space and project the rest
.plain:
    mov si, [cs_fidx]
    mov cx, [cs_fn]
    mov [cs_pn], cx
    mov di, cs_pv
.cp:
    lodsb
    xor ah, ah
    mov bx, ax
    shl bx, 1
    mov ax, [cs_sxv + bx]
    mov [di], ax
    mov ax, [cs_syv + bx]
    mov [di+2], ax
    add di, 4
    loop .cp
.fill:
    cmp word [cs_pn], 3
    jb .skip
    ; --- (v1 - v0) x (v2 - v0), screen y down: a face toward us is negative,
    ;     and a ground polygon that may be either way round still needs the
    ;     sign, because it says which chain an edge is on (cs_pwind) ---------
    mov ax, [cs_pv + 4]
    sub ax, [cs_pv]                 ; x1 - x0
    mov bx, [cs_pv + 10]
    sub bx, [cs_pv + 2]             ; y2 - y0
    imul bx
    mov cx, ax
    mov si, dx
    mov ax, [cs_pv + 6]
    sub ax, [cs_pv + 2]             ; y1 - y0
    mov bx, [cs_pv + 8]
    sub bx, [cs_pv]                 ; x2 - x0
    imul bx
    sub cx, ax
    sbb si, dx
    mov byte [cs_pwind], 0
    js .draw                        ; toward us
    mov byte [cs_pwind], 1
    test byte [cs_fflags], CSF_NOCULL
    jz .skip                        ; away, or edge-on
.draw:
    mov al, [cs_fink]
    call cs_setink
    mov si, cs_pv
    mov cx, [cs_pn]
    call cs_poly
.skip:
    pop si
    mov al, [si]
    xor ah, ah
    add si, ax
    add si, 3
    pop cx
    LOOPF .f
.out:
    ret

; -----------------------------------------------------------------------------
; cs_nearclip - Sutherland-Hodgman against z = [cs_near], in camera space, then
;               project: the face at [cs_fidx] (cs_fn ends) into cs_pv/cs_pn
; -----------------------------------------------------------------------------
cs_fclip:
    mov word [cs_ncl], 0
    mov di, cs_clipx
    mov cx, [cs_fn]
    mov si, [cs_fidx]
.e:
    push cx
    push si
    mov al, [si]                    ; a
    xor ah, ah
    mov bx, ax
    shl bx, 1
    mov [cs_na], bx
    inc si
    dec cx
    jnz .nb
    mov si, [cs_fidx]               ; ...the last edge closes on the first
.nb:
    mov al, [si]                    ; b
    xor ah, ah
    mov bx, ax
    shl bx, 1
    mov [cs_nb], bx
    mov bx, [cs_na]
    cmp word [cs_fv + bx], 0
    je .aback
    ; a is in front: output it
    mov ax, [cs_cxv + bx]
    mov [di], ax
    mov ax, [cs_cyv + bx]
    mov [di+2], ax
    mov ax, [cs_czv + bx]
    mov [di+4], ax
    add di, 6
    inc word [cs_ncl]
    mov bx, [cs_nb]
    cmp word [cs_fv + bx], 0
    jne .next                       ; both in front: no crossing
    call cs_ncross
    jmp short .next
.aback:
    mov bx, [cs_nb]
    cmp word [cs_fv + bx], 0
    je .next                        ; both behind
    call cs_ncross
.next:
    pop si
    inc si
    pop cx
    loop .e
    ; --- then the four sides, each a Sutherland-Hodgman pass between the two
    ;     buffers (88.5.7) -----------------------------------------------------
    mov word [cs_csrc], cs_clipx
    mov word [cs_cdst], cs_clipy
    mov word [cs_cpln], 0
.pass:
    call cs_sidepass
    jnc .same                       ; nothing clipped: the same buffer
    mov ax, [cs_csrc]               ; swap the buffers
    xchg ax, [cs_cdst]
    mov [cs_csrc], ax
.same:
    add word [cs_cpln], 2
    cmp word [cs_cpln], 8
    jb .pass
    ; --- project the result ------------------------------------------------
    mov cx, [cs_ncl]
    mov [cs_pn], cx
    jcxz .out
    mov si, [cs_csrc]
    mov di, cs_pv
.p:
    push cx
    push si
    push di
    mov ax, [si]
    mov bx, [si+2]
    mov cx, [si+4]
    call cs_project
    pop di
    mov [di], ax
    mov [di+2], bx
    add di, 4
    pop si
    add si, 6
    pop cx
    loop .p
.out:
    ret

; cs_ncross - the point where edge [cs_na]->[cs_nb] crosses z = [cs_near],
; appended at DI (three words, DI advanced). Clobbers AX, BX, CX, DX.
cs_ncross:
    push si
    mov bx, [cs_na]
    mov si, [cs_nb]
    mov cx, [cs_czv + si]
    sub cx, [cs_czv + bx]           ; den = zb - za, never 0 (opposite sides)
    mov [cs_nden], cx
    mov ax, [cs_near]
    sub ax, [cs_czv + bx]           ; num = NEAR - za, |num| <= |den|
    mov [cs_nnum], ax
    mov ax, [cs_cxv + si]
    sub ax, [cs_cxv + bx]
    imul word [cs_nnum]
    idiv word [cs_nden]
    add ax, [cs_cxv + bx]
    mov [di], ax
    mov ax, [cs_cyv + si]
    sub ax, [cs_cyv + bx]
    imul word [cs_nnum]
    idiv word [cs_nden]
    add ax, [cs_cyv + bx]
    mov [di+2], ax
    mov ax, [cs_near]
    mov [di+4], ax
    add di, 6
    inc word [cs_ncl]
    pop si
    ret

; -----------------------------------------------------------------------------
; The frustum's sides (SPEC.md 88.5.7): the planes |x| = 4z and |y| = 4z in
; camera space, well inside where the projection would clamp (+-4000 is
; |x| = 9z), because a crossing is only exact to a distance UNIT - 16 of x
; or 4 of z - and at the near plane (z = 4) a unit of x is 444 projected
; pixels. 4z leaves the whole 5z between the plane and the clamp for that:
; a point on one projects to +-1778, and one 16 past it at z = 4 to 3554,
; still under the clamp, where the 8z the clipper first shipped with put
; the same point at 7104 and a road was seen bending at (4275, 2112).
; cs_cplanes: the component (x, y) and the sign each plane takes
; -----------------------------------------------------------------------------
; cs_cdist - AX = a point's distance from plane [cs_cpln], as z/4 - s c/16
;            (the quarter keeps the difference of two under a word), through
;            the plane's own routine (cs_cdtab, set by cs_cplane). SI -> the
;            point (x, y, z). Preserves SI, DI, CX, DX; clobbers BX
cs_cdist:
    jmp [cs_cdistp]
cs_cd_xp:
    mov ax, [si]
    jmp short cs_cd_p
cs_cd_xm:
    mov ax, [si]
    jmp short cs_cd_m
cs_cd_yp:
    mov ax, [si + 2]
    jmp short cs_cd_p
cs_cd_ym:
    mov ax, [si + 2]
cs_cd_m:
    neg ax
cs_cd_p:
    sar ax, 1
    sar ax, 1
    sar ax, 1
    sar ax, 1
    mov bx, [si + 4]
    sar bx, 1
    sar bx, 1
    sub bx, ax
    mov ax, bx
    ret
cs_cdtab: dw cs_cd_xp, cs_cd_xm, cs_cd_yp, cs_cd_ym

; cs_cplane - the plane [cs_cpln] (0, 2, 4, 6) selects its distance routine
cs_cplane:
    mov bx, [cs_cpln]
    mov ax, [cs_cdtab + bx]
    mov [cs_cdistp], ax
    ret

; cs_cxing - the point where A (SI ->) to B (DI ->) crosses plane [cs_cpln],
;            AX and BX its two distances of opposite sign, into cs_xpt:
;            t = da / (da - db), P = A + t (B - A). Preserves SI, DI
cs_cxing:
    push si
    push di
    mov cx, ax
    sub cx, bx                      ; CX = da - db, never 0
    mov bx, 32767
    imul bx                         ; DX:AX = da x 32767
    idiv cx                         ; AX = t, Q15, in 0..1
    mov [cs_ct], ax
    mov ax, [di]
    sub ax, [si]
    mov bx, [cs_ct]
    MUL14
    add ax, [si]
    mov [cs_xpt], ax
    mov ax, [di + 2]
    sub ax, [si + 2]
    mov bx, [cs_ct]
    MUL14
    add ax, [si + 2]
    mov [cs_xpt + 2], ax
    mov ax, [di + 4]
    sub ax, [si + 4]
    mov bx, [cs_ct]
    MUL14
    add ax, [si + 4]
    mov [cs_xpt + 4], ax
    pop di
    pop si
    ret

; cs_sidepass - one Sutherland-Hodgman pass of the [cs_ncl] points at
;               [cs_csrc] against plane [cs_cpln], into [cs_cdst]; [cs_ncl]
;               becomes the count out. Clobbers everything
cs_sidepass:
    mov cx, [cs_ncl]
    or cx, cx
    jz .none0
    call cs_cplane
    mov si, [cs_csrc]               ; --- every point's distance, once, and
    mov di, cs_cdists               ;     whether any is past the plane -----
    xor dx, dx
.d:
    call cs_cdist
    mov [di], ax
    or ax, ax
    jns .d1
    inc dx
.d1:
    add di, 2
    add si, 6
    loop .d
    or dx, dx
    jnz .clip                       ; all inside: the pass changes nothing
.none0:
    jmp .none
.clip:
    mov cx, [cs_ncl]
    mov word [cs_cn2], 0
    mov si, [cs_csrc]
    mov ax, [cs_cdst]
    mov [cs_cout], ax
    mov bp, cs_cdists               ; BP -> A's distance (a plain register:
.e:                                 ; SS != DS, so never [bp + n])
    push cx
    mov di, si                      ; DI -> B: the next point, or the first
    add di, 6                       ; after the last
    mov bx, bp
    add bx, 2                       ; BX -> B's distance...
    cmp cx, 1
    jne .b
    mov di, [cs_csrc]
    mov bx, cs_cdists               ; ...the first's, after the last
.b:
    mov ax, [bx]
    mov bx, ax                      ; BX = B's distance
    xchg bx, bp
    mov ax, [bx]                    ; AX = A's
    xchg bx, bp
    inc bp
    inc bp
    or ax, ax
    js .aout
    call .emita                     ; A inside: out it goes...
    or bx, bx
    jns .next                       ; ...and B too: nothing between
    call cs_cxing                   ; ...B outside: the crossing follows
    call .emitx
    jmp short .next
.aout:
    or bx, bx
    js .next                        ; both outside
    call cs_cxing                   ; A outside, B in: the crossing
    call .emitx
.next:
    pop cx
    add si, 6
    loop .e
    mov ax, [cs_cn2]
    mov [cs_ncl], ax
    stc                             ; CF = the buffers changed hands
    ret
.none:
    clc
    ret
.emita:
    push bx
    push si
    jmp short .emit
.emitx:
    push bx
    push si
    mov si, cs_xpt
.emit:
    cmp word [cs_cn2], CS_MAXPV
    jae .full
    push di
    mov di, [cs_cout]
    mov ax, [si]
    mov [di], ax
    mov ax, [si + 2]
    mov [di + 2], ax
    mov ax, [si + 4]
    mov [di + 4], ax
    add word [cs_cout], 6
    inc word [cs_cn2]
    pop di
.full:
    pop si
    pop bx
    ret

; -----------------------------------------------------------------------------
; cs_edges - every edge of [cs_mdl], in the model's line ink
; -----------------------------------------------------------------------------
cs_edges:
    mov si, [cs_mdl]
    mov cl, [si + CSM_NE]
    xor ch, ch
    jcxz .out
    mov al, [si + CSM_EINK]
    call cs_setink
    mov si, [si + CSM_EDGES]
    cld
.e:
    lodsw                           ; AL/AH = the edge's two vertex indices
    push cx
    push si
    call cs_edge1
    pop si
    pop cx
    loop .e
.out:
    ret

; cs_edge1 - the edge between vertices AL and AH, near-clipped where it has
;            to be, in the current ink. Clobbers everything
cs_edge1:
    mov bl, al
    xor bh, bh
    shl bx, 1
    mov dl, ah
    xor dh, dh
    shl dx, 1
    mov di, dx
    mov cx, [cs_fv + bx]
    add cx, [cs_fv + di]
    jcxz .skip                      ; both behind the near plane
    cmp cx, 2
    jne .gen
    cmp word [cs_fv + bx], 1
    jne .gen
.both:                              ; both in front and inside: as projected
    mov ax, [cs_sxv + bx]
    mov bx, [cs_syv + bx]
    mov cx, [cs_sxv + di]
    mov dx, [cs_syv + di]
.draw:
    call cs_seg
.skip:
    ret
    ; --- one end behind the near plane or past a side (88.5.7): the two
    ;     ends in camera space, the near crossing for a behind one, then the
    ;     four sides, an end past one brought to it along the edge ----------
.gen:
    mov [cs_na], bx
    mov [cs_nb], dx
    mov si, bx
    mov di, cs_ea
    call cs_ecopy                   ; A -> cs_ea
    mov si, [cs_nb]
    mov di, cs_eb
    call cs_ecopy                   ; B -> cs_eb
    mov bx, [cs_na]
    cmp word [cs_fv + bx], 0
    jne .bnear
    mov ax, [cs_nb]                 ; A behind: the crossing from B replaces it
    mov [cs_na], ax
    mov [cs_nb], bx
    mov di, cs_ea
    call cs_ncross
    jmp short .sides
.bnear:
    mov bx, [cs_nb]
    cmp word [cs_fv + bx], 0
    jne .sides
    mov di, cs_eb                   ; B behind: the crossing from A replaces it
    call cs_ncross
.sides:
    mov word [cs_cpln], 0
.side:
    call cs_cplane
    mov si, cs_ea
    call cs_cdist
    mov [cs_cda], ax
    mov si, cs_eb
    call cs_cdist
    mov bx, ax                      ; BX = B's distance
    mov ax, [cs_cda]                ; AX = A's
    mov si, cs_ea
    mov di, cs_eb
    or ax, ax
    jns .ain
    or bx, bx
    js .skip                        ; both past this side: nothing to draw
    call cs_cxing                   ; A past it: to the crossing
    mov si, cs_xpt
    mov di, cs_ea
    call cs_ecopy
    jmp short .nside
.ain:
    or bx, bx
    jns .nside
    call cs_cxing                   ; B past it: to the crossing
    mov si, cs_xpt
    mov di, cs_eb
    call cs_ecopy
.nside:
    add word [cs_cpln], 2
    cmp word [cs_cpln], 8
    jb .side
    mov ax, [cs_ea]                 ; --- both ends inside: project and draw --
    mov bx, [cs_ea + 2]
    mov cx, [cs_ea + 4]
    call cs_project
    mov [cs_ex1], ax
    mov [cs_ey1], bx
    mov ax, [cs_eb]
    mov bx, [cs_eb + 2]
    mov cx, [cs_eb + 4]
    call cs_project
    mov cx, ax
    mov dx, bx
    mov ax, [cs_ex1]
    mov bx, [cs_ey1]
    jmp .draw

; cs_ecopy - the camera-space point at SI (a triple, or a vertex's byte
;            index into cs_cxv/cyv/czv when SI < 64) to the triple at DI
cs_ecopy:
    cmp si, 64
    jae .triple
    mov ax, [cs_cxv + si]
    mov [di], ax
    mov ax, [cs_cyv + si]
    mov [di + 2], ax
    mov ax, [cs_czv + si]
    mov [di + 4], ax
    ret
.triple:
    mov ax, [si]
    mov [di], ax
    mov ax, [si + 2]
    mov [di + 2], ax
    mov ax, [si + 4]
    mov [di + 4], ax
    ret

; -----------------------------------------------------------------------------
; cs_rwline - the runway's centreline (SPEC.md 88.6.2): DASHED from the stripe
;             the aeroplane is on, RW_NDASH stripes of RW_DASHM metres with as
;             much gap, then solid to the far end - so a take-off roll can be
;             seen moving. Every endpoint is a point along the transformed
;             centreline (vertices 5 -> 4, at the object's scale), put into
;             scratch vertices 6 and 7 and drawn through cs_edge1, which
;             near-clips it. Away from the runway - above RW_DASHH, beyond
;             RW_DASHW of its axis, or past its far end - the line is solid
;             from end to end and costs one segment, as it did before.
;             Runs after cs_edges, in its ink.
; -----------------------------------------------------------------------------
cs_rwline:
    call cs_runway_xy               ; [cs_along], [cs_across]
    mov si, [cs_airport]
    mov ax, [cs_py+1]
    sub ax, [si + CSA_ELEV]
    cmp ax, RW_DASHH
    jg .solid
    mov ax, [cs_across]
    or ax, ax
    jns .w
    neg ax
.w:
    cmp ax, RW_DASHW
    jg .solid
    mov ax, [cs_along]
    add ax, [si + CSA_HLEN]         ; AX = metres from the near end
    js .zero
    mov dx, 16384
    mul dx
    div word [si + CSA_HLEN]        ; AX = the aeroplane's u, Q15 of 2 hlen
    cmp ax, 32000
    jae .solid                      ; past the far end
    jmp short .u
.zero:
    xor ax, ax
.u:
    xor dx, dx                      ; the stripe it is on: u rounded down
    mov cx, [cs_rwdu]               ; to a pitch
    shl cx, 1
    div cx
    mul cx
    mov cx, RW_NDASH
.dash:
    push cx
    push ax
    mov cx, ax
    add cx, [cs_rwdu]               ; CX = the stripe's far end
    cmp cx, 32767
    jae .last                       ; past the runway's: nothing more
    call cs_rwsegu                  ; the stripe (AX..CX)
    pop ax
    add ax, [cs_rwdu]
    add ax, [cs_rwdu]               ; the next stripe
    pop cx
    loop .dash
    mov cx, 32767                   ; ...then solid to the far end
    cmp ax, cx
    jae .out
    jmp short cs_rwsegu
.last:
    pop ax
    pop cx
.out:
    ret
.solid:
    xor ax, ax
    mov cx, 32767
    ; falls into cs_rwsegu

; cs_rwsegu - the centreline from u = AX to u = CX (Q15): scratch vertices
;             6 and 7, then the edge. Clobbers everything
cs_rwsegu:
    push cx
    mov di, 12                      ; vertex 6
    call cs_rwpt
    pop ax
    mov di, 14                      ; vertex 7
    call cs_rwpt
    mov ax, 0x0706                  ; AL = 6, AH = 7
    jmp cs_edge1

; cs_rwpt - the point at u = AX (Q15) along the centreline, vertex 5 -> 4,
;           into vertex DI (its byte index): camera space, the near flag
;           and, in front, the projection. Clobbers everything but DI
cs_rwpt:
    mov [cs_rwu], ax
    mov ax, [cs_cxv + 8]
    sub ax, [cs_cxv + 10]
    mov bx, [cs_rwu]
    MUL14
    add ax, [cs_cxv + 10]
    mov [cs_cxv + di], ax
    mov ax, [cs_cyv + 8]
    sub ax, [cs_cyv + 10]
    mov bx, [cs_rwu]
    MUL14
    add ax, [cs_cyv + 10]
    mov [cs_cyv + di], ax
    mov ax, [cs_czv + 8]
    sub ax, [cs_czv + 10]
    mov bx, [cs_rwu]
    MUL14
    add ax, [cs_czv + 10]
    mov [cs_czv + di], ax
    mov word [cs_fv + di], 0
    cmp ax, [cs_near]
    jl .out                         ; behind: cs_edge1 clips to it
    mov word [cs_fv + di], 1
    mov cx, ax
    mov ax, [cs_cxv + di]
    mov bx, [cs_cyv + di]
    push di
    call cs_project
    pop di
    mov [cs_sxv + di], ax
    mov [cs_syv + di], bx
.out:
    ret

cs_sintab:
%include "cssin.inc"
