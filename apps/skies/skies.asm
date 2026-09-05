; =============================================================================
; os8088 - apps/skies/skies.asm
;
; CLEAR SKIES, a filled-polygon flight simulator (SPEC.md 88): take off from
; an airport, fly over Paris, land - or crash and be put back on the runway.
; A .o88 package at org 0 owning a segment (SPEC.md 20.1), prefix `cs_`,
; embedded icon, no worker task, and no kernel change of any kind.
;
; It is TANK ATTACK's shape (SPEC.md 85) with the other half of the 1983
; vocabulary attached: Tank draws nothing but lines and this FILLS the space
; between them. Like Tank it runs inside an fsx bracket in a foreign mode
; (SPEC.md 53.4), where no kernel drawing slot is legal (53.7) and every
; pixel is this package's own. It is built against one number: TWELVE FRAMES
; A SECOND on a 4.77 MHz 8088 with a Hercules card, the machine in the tree
; that can least afford a filled picture.
;
; THE THREE THINGS THAT DECIDE THE WHOLE DESIGN (SPEC.md 88.1)
;
;  1. EVERY PIXEL OF THE VIEW CHANGES EVERY FRAME, which inverts Tank's
;     central finding. Tank keeps a per-row dirty span so that the next frame
;     clears exactly what the last one drew; a flight simulator's frame IS a
;     clear - the sky and the ground together cover the view and the horizon
;     between them moves with every degree of pitch and roll. So the view
;     keeps no dirty spans at all: the sky/ground pass writes every byte of it,
;     the polygons and lines go over that, and the blit copies it whole. The
;     span set is kept for the PANEL, where an instrument that has not changed
;     is not redrawn and not copied.
;  2. THE VIEW IS HALF THE BOX. A frame's cost on this design is proportional
;     to the view's AREA - the fill, the blit and every polygon row scale with
;     it - so the view is sized to the budget and not to the screen: 320x112
;     on CGA, 320x144 on Mode X, and 400x112 in the middle of the 640-wide box
;     on Hercules, 50 bytes of the 80 in every row.
;  3. A POLYGON IS FILLED BY ITS EDGES, NEVER BY ITS PIXELS. Each edge is
;     walked once per ROW with an integer step into a left and a right bound,
;     and each row is then one masked run - which is how every game of the
;     period did it (SPEC.md 88.2), and why an 8088 can fill a building face
;     in the time it takes to walk one of its edges.
;
; ONE PLANE AND ONE AIRPORT, EACH A RECORD (SPEC.md 88.6): the flight model
; reads every constant it needs out of [cs_plane]'s row and the runway is
; built out of [cs_airport]'s at bracket entry, so a second of either is a
; row in a table and not a rewrite.
;
; Keys: arrows pitch and roll (down = nose up, as in every flight simulator),
; W/S throttle, A/D rudder and nosewheel, B brakes, P pauses, R puts the
; aeroplane back on the runway, M mutes the engine, Esc or F leaves.
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'SKIES', cs_entry, 1, OS88_STACK_DEFAULT
                                ; no worker: the whole flight is the bracket
                                ; on task 0, and the attract window is still

; --- embedded 16x16 icon (SPEC.md 20.2, flags bit 0) --------------------------
; A high-wing single seen from above: the Cessna's own silhouette.
;
;   ................
;   .......#........
;   ......###.......
;   ......###.......
;   .......#........
;   .......#........
;   ###############.
;   ###############.
;   .......#........
;   .......#........
;   .......#........
;   ......###.......
;   .....#####......
;   .......#........
;   ................
;   ................
    OS88_ICON16
    dw 0x0000                       ; 16 mask rows (white underlay)
    dw 0x0100
    dw 0x0380
    dw 0x0380
    dw 0x0100
    dw 0x0100
    dw 0xFFFE
    dw 0xFFFE
    dw 0x0100
    dw 0x0100
    dw 0x0100
    dw 0x0380
    dw 0x07C0
    dw 0x0100
    dw 0x0000
    dw 0x0000
    dw 0x0000                       ; 16 data rows (black pixels)
    dw 0x0100
    dw 0x0380
    dw 0x0380
    dw 0x0100
    dw 0x0100
    dw 0xFFFE
    dw 0xFFFE
    dw 0x0100
    dw 0x0100
    dw 0x0100
    dw 0x0380
    dw 0x07C0
    dw 0x0100
    dw 0x0000
    dw 0x0000
    OS88_ICON16_END

; =============================================================================
; Constants
; =============================================================================

; --- which raster we are on ---------------------------------------------------
CSB_NONE  equ 0                 ; windowed: no bracket, nothing to draw into
CSB_MODEX equ 1                 ; 320x240x256 planar, 3 pages - PAGE FLIP
CSB_CGA   equ 2                 ; 320x200x4 banked, 1 page  - SHADOW + BLIT
CSB_HERC  equ 3                 ; 720x348 mono, 4 banks     - SHADOW + BLIT

; --- the logical inks (SPEC.md 88.4.4) ----------------------------------------
; Named by what they MEAN. Every backend's table gives an ink FOUR pattern
; bytes, one per row of a four-row cycle, which is what lets a Hercules dither
; and a Mode X colour index go through one fill.
CSI_SKY    equ 0
CSI_GROUND equ 1
CSI_RUNWAY equ 2
CSI_RIVER  equ 3
CSI_WALL   equ 4                ; a face toward the camera
CSI_WALL2  equ 5                ; a side
CSI_ROOF   equ 6
CSI_HILL   equ 7
CSI_LINE   equ 8                ; the tower, and every wireframe edge
CSI_MARK   equ 9                ; runway edges and roads
CSI_PBG    equ 10               ; the panel's ground...
CSI_PFG    equ 11               ; ...its ink...
CSI_PHI    equ 12               ; ...and its warning
CSI_NINK   equ 13

; --- the world (SPEC.md 88.5, 88.6) -------------------------------------------
; Metres. x east, z north, y up; the Eiffel Tower at the origin.
CS_NEAR   equ 40                ; the near plane
CS_NEARG  equ 4                 ; ...and a ground polygon's: the eye is 2 m up
                                ; and the view's bottom row is 10 m ahead, so
                                ; at 40 m the runway ended above it (88.5.5)
CS_FAR    equ 16000             ; nothing beyond this is transformed, and it
                                ; is what keeps every 16-bit sum in range
CS_MAXV   equ 24                ; vertices in the largest model (the tower's
                                ; five levels are 20)
CS_MAXPV  equ 10                ; ...and a face after the near clip
CS_NVIS   equ 32                ; objects that can be in one frame
CS_VISZ   equ 10                ; ...ten bytes each: ptr, dx, dy, dz, along
CS_MAXROW equ 240               ; the tallest box any backend offers
CS_LASTB  equ 79                ; the last byte of a box row, on all three
CS_SHSEG  equ 16000             ; the CGA/Hercules shadow, in bytes
CS_SHKB   equ 16                ; ...as a claim

; --- model types --------------------------------------------------------------
CSM_STACK equ 0                 ; levels of (wx, h, wz): boxes, pyramids, the
                                ; tower (SPEC.md 88.5)
CSM_FLAT  equ 1                 ; explicit (x, z) pairs on the ground

; --- a model: db type, nverts (STACK: nlevels), nfaces, nedges, edge ink, 0;
;     dw radius, verts, faces, edges ---------------------------------------------
CSM_TYPE  equ 0
CSM_NV    equ 1
CSM_NF    equ 2
CSM_NE    equ 3
CSM_EINK  equ 4                 ; the edges' ink (5 is 0)
CSM_RAD   equ 6
CSM_VERTS equ 8
CSM_FACES equ 10
CSM_EDGES equ 12
CSM_SIZE  equ 14

; a face: db n, ink, flags, then n vertex indices
CSF_NOCULL equ 1                ; a ground polygon: visible from either side

; --- an object (SPEC.md 88.6): sixteen bytes ----------------------------------
CSO_MODEL equ 0                 ; word: the model
CSO_FAR   equ 2                 ; word: the far model, or 0
CSO_X     equ 4
CSO_Z     equ 6
CSO_Y     equ 8                 ; the base height
CSO_RANGE equ 10                ; drawn within this (Manhattan) distance
CSO_LOD   equ 12                ; ...and the far model stands in beyond this
CSO_NAME  equ 14                ; word: for the crash line
CSO_FLAGS equ 16                ; word: CSO_*
CSO_SKIP  equ 18                ; word: the tick the cull looks at it again
                                ; (88.5.2): out of range by D metres is out
                                ; of range for D/16 ticks at any speed
CSO_SIZE  equ 20
CSO_COLLIDE equ 1               ; the first level's footprint and the tallest
CSO_SEEN  equ 0x8000            ; ...and bit 15: drawn last frame (88.5.1)
                                ; level's height are a box the aeroplane may
                                ; not enter

; --- an airport (SPEC.md 88.6) ------------------------------------------------
CSA_NAME  equ 0                 ; word: the name
CSA_X     equ 2
CSA_Z     equ 4
CSA_ELEV  equ 6
CSA_HDG   equ 8                 ; the runway heading, 65536 to the turn
CSA_HLEN  equ 10                ; half the runway's length
CSA_HWID  equ 12                ; ...and half its width
CSA_RWY   equ 14                ; word: the runway's designation
CSA_SPAWN equ 16                ; where the aeroplane stands at reset, along
                                ; the runway from its centre (negative = the
                                ; near threshold)
CSA_SIZE  equ 18

; --- a plane (SPEC.md 88.7) - speeds 16.8 m/s, angles 65536 to the turn -------
CSP_NAME   equ 0
CSP_VSTALL equ 2
CSP_VROT   equ 4
CSP_VMAX   equ 6
CSP_THRUST equ 8                ; 16.8 m/s a tick, at full throttle
CSP_DRAGK  equ 10               ; drag = v^2 x this >> 16, a tick
CSP_FRICT  equ 12               ; rolling friction a tick, on the ground
CSP_BRAKE  equ 14
CSP_ROLLR  equ 16               ; roll rate a tick, held
CSP_ROLLL  equ 18               ; ...and the return to level
CSP_PITCHR equ 20
CSP_PITCHT equ 22
CSP_TURNK  equ 24               ; heading a tick at sin(roll) = 1
CSP_EYE    equ 26               ; the pilot's eye above the wheels
CSP_MAXROLL equ 28
CSP_MAXPITCH equ 30
CSP_SIZE   equ 32

; --- the session (SPEC.md 88.8) -----------------------------------------------
CS_ST_GROUND equ 0
CS_ST_AIR    equ 1
CS_ST_CRASH  equ 2
CS_MAXSTEP equ 3                ; the most ticks a frame may ever spend
CS_PRATE  equ 6                 ; ticks between instrument readings (88.9.1)
RW_NDASH  equ 4                 ; centreline stripes drawn ahead (88.6.2)
RW_DASHM  equ 25                ; ...each this long, with as much gap
RW_DASHH  equ 150               ; ...within this height of the runway
RW_DASHW  equ 300               ; ...and this far from its axis
CS_CRASHT  equ 36               ; ticks the crash stays on the glass: 2 s
CS_GRAV    equ 138              ; 9.81 m/s^2 a tick, 16.8
CS_STALLSINK equ 24             ; 16.8 m/s of sink per 1 m/s under the stall
CS_STALLDROP equ 60             ; the nose drops this much a tick, stalled
CS_LIFTOFF equ 546              ; 3 degrees: the nose is up, and it flies
CS_RUDDER  equ 24               ; the rudder's yaw a tick, in the air
CS_STEERK  equ 2                ; the nosewheel: hdg += v x this >> 8
CS_LANDVS  equ -768             ; a landing sinks no faster than 3 m/s...
CS_LANDROLL equ 1820            ; ...banked under 10 degrees...
CS_LANDPMIN equ -910            ; ...with the nose between -5...
CS_LANDPMAX equ 2730            ; ...and +15
CS_CEIL    equ 3000             ; metres: what keeps the geometry in a word
CS_EDGE    equ 30000            ; ...and so does this, either way on x and z

; --- messages -----------------------------------------------------------------
CSG_NONE   equ 0
CSG_TAKEOFF equ 1
CSG_STALL  equ 2
CSG_LANDED equ 3
CSG_CRASH  equ 4
CSG_PAUSED equ 5
CSG_EDGE   equ 6

; --- the attract window (SPEC.md 88.10) ---------------------------------------
CS_WINW   equ 312
CS_WINH   equ 132

; --- scancodes this package reads directly (SPEC.md 9.7) ----------------------
CS_KW     equ 0x11
CS_KS     equ 0x1F
CS_KA     equ 0x1E
CS_KD     equ 0x20
CS_KB     equ 0x30

; --- a `loop` and a `jcxz` whose target is past a short jump's reach ---------
; NASM refuses an out-of-range short jump on cpu 8086 rather than widening it.
%macro LOOPF 1
    dec cx
    jz %%end
    jmp %1
%%end:
%endmacro
%macro JCXZF 1
    jcxz %%z
    jmp short %%go
%%z:
    jmp %1
%%go:
%endmacro

; =============================================================================
; cs_entry - the loader calls this once per instance (SPEC.md 20.1)
; =============================================================================
cs_entry:
    push si
    push di
    call OSAPI_VIDEO                ; AX = w, BX = h, CX = the dock's top row
    mov [cs_scrw], ax
    mov [cs_dock], cx

    mov al, KSC_SPACE               ; ARMING the scancode reader: the first
    call OSAPI_KEY_DOWN             ; answer is always "up" and this is where
                                    ; the SDK says to spend it (SPEC.md 9.7)
    mov word [cs_plane], cs_p_c172  ; the rows in use (SPEC.md 88.6)
    mov word [cs_airport], cs_a_issy
    mov byte [cs_sound], 1

    ; Centre the attract window in the desktop band.
    mov ax, [cs_scrw]
    sub ax, CS_WINW
    jns .xok
    xor ax, ax
.xok:
    shr ax, 1
    mov [cs_tpl + WT_X], ax
    mov ax, [cs_dock]
    sub ax, MBAR_H
    sub ax, CS_WINH
    jns .yok
    xor ax, ax
.yok:
    shr ax, 1
    add ax, MBAR_H
    mov [cs_tpl + WT_Y], ax

    mov si, cs_tpl
    call OSAPI_WM_CREATE
    jc .full
    mov [cs_win], bx
    mov al, 1                       ; an 8-aligned content origin: every
    call OSAPI_WM_SNAP              ; font_run below reaches SPEC.md 6.1's
                                    ; single-store cell
    call cs_adapter                 ; which raster we would take, and whether
                                    ; the machine will give it to us
    mov ax, cs_onresize             ; the card can change under us
    call OSAPI_WM_ONRESIZE          ; (SPEC.md 11.98)
    mov si, cs_menus
    call OSAPI_MENU_SET
    mov si, cs_about                ; 'About Clear Skies' above the Close the
    call OSAPI_ABOUT_SET            ; kernel puts in our pull-down (SPEC.md
                                    ; 12.2). WINDOWED only: in the bracket
                                    ; there is no bar to pull down
.full:
    pop di
    pop si
    ret

; -----------------------------------------------------------------------------
; cs_adapter - the raster this machine would give us, and the mode to ask for
;
; out: [cs_want] = a CSB_*, [cs_fsxm] = the FSXM_* to set, [cs_caps], and the
;      menu item's caption. Preserves every register (cs_onresize is a
;      callback). EVERY BRANCH WRITES BOTH WAYS - SPEC.md 48's lesson.
; OSAPI_FSX_CAPS is asked with our WINDOW in BX, so on a two-card machine the
; answer is about the display this window is on (SPEC.md 39.18.2).
; -----------------------------------------------------------------------------
cs_adapter:
    push ax
    push bx
    push dx
    mov bx, [cs_win]
    call OSAPI_FSX_CAPS
    mov [cs_caps], ax
    mov [cs_vidk], dl
    mov byte [cs_cdim], CLGRAY      ; the panel's second inks: grey and cyan
    mov byte [cs_csub], CLCYAN      ; on a colour display, and white on a 1bpp
    cmp dl, VID_VGA                 ; one, where both round to BLACK (SPEC.md
    je .inks                        ; 39.4: only 12, 14 and 15 come out white)
    cmp dl, VID_EGA
    je .inks
    mov byte [cs_cdim], CWHITE
    mov byte [cs_csub], CWHITE
.inks:
    mov byte [cs_want], CSB_NONE
    mov byte [cs_fsxm], 0FFh
    test ax, 1 << FSXM_MODEX
    jz .cga
    mov byte [cs_want], CSB_MODEX
    mov byte [cs_fsxm], FSXM_MODEX
    jmp short .say
.cga:
    test ax, 1 << FSXM_CGA320
    jz .herc
    mov byte [cs_want], CSB_CGA
    mov byte [cs_fsxm], FSXM_CGA320
    jmp short .say
.herc:
    test ax, 1 << FSXM_HERC
    jz .say
    mov byte [cs_want], CSB_HERC
    mov byte [cs_fsxm], FSXM_HERC
.say:
    mov dx, cs_s_fly                ; the menu says WHY not, off the same
    cmp byte [cs_want], CSB_NONE    ; predicate the command refuses on
    jne .ok                         ; (SPEC.md 47)
    mov dx, cs_s_flyn
.ok:
    mov [cs_mi_flight + 0], dx
    pop dx
    pop bx
    pop ax
    ret

cs_onresize:
    call cs_adapter
    ret

; =============================================================================
; The windowed half: a still panel, and one command that leaves it
; (SPEC.md 88.10)
; =============================================================================

; -----------------------------------------------------------------------------
; cs_paint - W_PAINT.  in: SI = window ptr; gfx lock held.  preserves all
; -----------------------------------------------------------------------------
cs_paint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov bx, [cs_win]
    call OSAPI_WM_CONTENT
    mov [cs_winox], ax
    mov [cs_winoy], dx
    mov bx, [cs_win]
    call OSAPI_WM_GEOM              ; CX/DX = the content box
    jc .out
    mov [cs_cw], cx
    mov [cs_ch], dx

    mov al, CBLACK                  ; a night-blue panel would be the obvious
    call OSAPI_SET_COLOR            ; thing and rounds to black on two adapters
    mov ax, [cs_winox]              ; of three (SPEC.md 39.4), so it is black
    mov bx, [cs_winoy]              ; everywhere and every run below letters
    mov cx, ax                      ; onto it opaquely (SPEC.md 6.1)
    add cx, [cs_cw]
    dec cx
    mov dx, bx
    add dx, [cs_ch]
    dec dx
    call OSAPI_GFX_FILL

    mov si, cs_s_title
    mov bx, 8
    mov al, CWHITE
    call cs_at_centre
    mov si, cs_s_sub
    mov bx, 20
    mov al, [cs_csub]
    call cs_at_centre

    mov si, cs_s_plane              ; what is being flown, and from where -
    mov bx, 40                      ; read off the records, so a second row
    mov al, [cs_cdim]               ; in either table shows up here unasked
    mov cx, 16
    call cs_at_left
    mov si, [cs_plane]
    mov si, [si + CSP_NAME]
    mov al, CWHITE
    call cs_at_label
    mov si, cs_s_airport
    mov bx, 52
    mov al, [cs_cdim]
    call cs_at_left
    mov si, [cs_airport]
    mov si, [si + CSA_NAME]
    mov al, CWHITE
    call cs_at_label

    mov al, [cs_cdim]
    mov si, cs_s_k1
    mov bx, 72
    call cs_at_left
    mov si, cs_s_k2
    mov bx, 82
    call cs_at_left
    mov si, cs_s_k3
    mov bx, 92
    call cs_at_left

    mov si, cs_s_press
    cmp byte [cs_want], CSB_NONE
    jne .live
    mov si, cs_s_nomode             ; the reason, in the window (SPEC.md 47)
.live:
    mov bx, 112
    mov al, CYELLOW
    call cs_at_centre

    cmp byte [cs_abon], 0           ; ...and the About card LAST, over the
    je .out                         ; panel it is opaque about (20.5.1)
    push si
    mov bx, [cs_win]
    mov si, cs_ablines
    call os88ui_about_d
    pop si
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; cs_at_left - SI = string, BX = content y, CX = content x, AL = ink
cs_at_left:
    push ax
    push bx
    push cx
    push dx
    push si
    mov dx, [cs_winoy]
    add dx, bx
    add cx, [cs_winox]
    mov ah, CBLACK
    call OSAPI_FONT_RUN
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; cs_at_label - the same at x = 96: the record's name after its label
cs_at_label:
    push cx
    mov cx, 96
    call cs_at_left
    pop cx
    ret

; cs_at_centre - SI = string, BX = content y, AL = ink; centred on the window
cs_at_centre:
    push cx
    push si
    call cs_strlen                  ; CX = its length
    shl cx, 1
    shl cx, 1
    shl cx, 1
    push ax
    mov ax, [cs_cw]
    sub ax, cx
    jns .ok
    xor ax, ax
.ok:
    shr ax, 1
    and al, 0F8h                    ; onto a cell boundary (SPEC.md 6.1)
    mov cx, ax
    pop ax
    call cs_at_left
    pop si
    pop cx
    ret

; cs_strlen - SI = string; out CX = its length. Preserves SI.
cs_strlen:
    push si
    xor cx, cx
.s:
    cmp byte [si], 0
    je .d
    inc si
    inc cx
    jmp short .s
.d:
    pop si
    ret

; -----------------------------------------------------------------------------
; cs_onkey - W_ONKEY.  in: AL = ascii, SI = window; gfx lock held
; -----------------------------------------------------------------------------
cs_onkey:
    push ax
    call cs_abdismiss               ; any key takes the credits down, and is
    jc .out                         ; spent doing it
    cmp al, 'f'
    je .go
    cmp al, 'F'
    je .go
    cmp al, 0x0D
    jne .out
.go:
    call cs_cmd_fly
.out:
    pop ax
    ret

cs_onclick:
    call cs_abdismiss
    jc .out
    call cs_cmd_fly
.out:
    ret

; cs_oncmd - the menu handler.  in: AL = item index within the menu
cs_oncmd:
    push ax
    push bx
    call cs_abdismiss
    cmp al, 0
    jne .out
    call cs_cmd_fly
.out:
    pop bx
    pop ax
    ret

; =============================================================================
; Menus, strings, the About card
; =============================================================================
    OS88_MENUSET cs_menus, cs_m_name, cs_oncmd
        OS88_MENU cs_m_flight, cs_mi_flight, 1
    OS88_MENUSET_END cs_menus

cs_m_name:   db 'Clear Skies', 0
cs_m_flight: db 'Flight', 0
cs_mi_flight: dw cs_s_fly            ; rewritten by cs_adapter when no mode
cs_s_fly:    db 'Fly', 0            ; can be had
cs_s_flyn:   db 'Fly (no mode)', 0

cs_ttl:      db 'Clear Skies', 0
cs_s_title:  db 'CLEAR SKIES', 0
cs_s_sub:    db 'A FLIGHT SIMULATOR', 0
cs_s_plane:  db 'AEROPLANE', 0
cs_s_airport: db 'AIRPORT', 0
cs_s_k1:     db 'ARROWS PITCH AND ROLL, W/S THROTTLE', 0
cs_s_k2:     db 'A/D RUDDER, B BRAKES, P PAUSE, R RESET', 0
cs_s_k3:     db 'M MUTES THE ENGINE, ESC OR F LEAVES', 0
cs_s_press:  db 'PRESS F TO FLY', 0
cs_s_nomode: db 'NO FULLSCREEN MODE ON THIS DISPLAY', 0

; -----------------------------------------------------------------------------
; cs_about - the OSAPI_ABOUT_SET handler (slot 0x01E0)
; in:  SI = our window ptr; the UI task, gfx lock HELD.  preserves all
; -----------------------------------------------------------------------------
cs_about:
    push bx
    push si
    mov byte [cs_abon], 1
    mov bx, si
    mov si, cs_ablines
    call os88ui_about               ; arms the clip itself (SPEC.md 11.3)
    pop si
    pop bx
    ret

; cs_abdismiss - take the card down if it is up. out: CF = 1 spent doing it
cs_abdismiss:
    cmp byte [cs_abon], 0
    je .none
    push bx
    mov byte [cs_abon], 0
    mov bx, [cs_win]
    call OSAPI_WM_CLIP_SET
    jc .gone
    call cs_paint
.gone:
    pop bx
    stc
    ret
.none:
    clc
    ret

cs_ablines:
    dw cs_ab1, cs_ab2, cs_ab3, 0
cs_ab1:      db 'Clear Skies for os8088', 0
cs_ab2:      db 0
cs_ab3:      db 'Contributed by Elendilon', 0

cs_tpl:
    dw 0, 0, CS_WINW, CS_WINH
    dw cs_ttl, cs_paint, cs_onkey, cs_onclick

%include "csraster.inc"
%include "cs3d.inc"
%include "csworld.inc"
%include "csflight.inc"
%include "csgame.inc"

; =============================================================================
; .bss (SPEC.md 20.5: the loader zeroes CS_BSS bytes after the image, and
; every name below is an offset from os88_image_end)
; =============================================================================
%assign CS_BSS 0
%macro ZWORD 1
%1 equ os88_image_end + CS_BSS
%assign CS_BSS CS_BSS + 2
%endmacro
%macro ZBYTE 1
%1 equ os88_image_end + CS_BSS
%assign CS_BSS CS_BSS + 1
%endmacro
%macro ZBUF 2
%1 equ os88_image_end + CS_BSS
%assign CS_BSS CS_BSS + (%2)
%endmacro
%macro ZDWORD 1
%1 equ os88_image_end + CS_BSS
%assign CS_BSS CS_BSS + 4
%endmacro

; --- the desktop side ---------------------------------------------------------
    ZWORD cs_scrw
    ZWORD cs_dock
    ZWORD cs_win
    ZWORD cs_winox
    ZWORD cs_winoy
    ZWORD cs_cw
    ZWORD cs_ch
    ZWORD cs_caps
    ZBYTE cs_want
    ZBYTE cs_fsxm
    ZBYTE cs_vidk
    ZBYTE cs_cdim                   ; the attract panel's dim and subtitle
    ZBYTE cs_csub                   ; inks, per adapter
    ZBYTE cs_abon
    ZWORD cs_plane                  ; the rows in use (SPEC.md 88.6)
    ZWORD cs_airport

; --- the raster ---------------------------------------------------------------
    ZBUF  cs_fsi, FSI_SIZE
    ZBYTE cs_back
    ZBYTE cs_par
    ZBYTE cs_kshift                 ; log2 of the pixels in a byte: 3 or 2
    ZBYTE cs_quit
    ZWORD cs_vx                     ; THE NINE WORDS cs_vptab's row lands on,
    ZWORD cs_vy                     ; in its order: the box...
    ZWORD cs_vw
    ZWORD cs_vh
    ZWORD cs_wx0                    ; ...the view's first x, width and height
    ZWORD cs_ww
    ZWORD cs_wh
    ZWORD cs_sclx                   ; ...and the two scales
    ZWORD cs_scly
    ZWORD cs_wx1                    ; the view's last x
    ZWORD cs_wb0                    ; ...its first byte and byte count
    ZWORD cs_wbn
    ZWORD cs_vcx                    ; the projection centre
    ZWORD cs_vcy
    ZWORD cs_tseg                   ; the target: the shadow, or VRAM
    ZWORD cs_tbase
    ZWORD cs_page0
    ZWORD cs_page1
    ZWORD cs_shseg
    ZWORD cs_inktab
    ZWORD cs_hrunproc
    ZWORD cs_rowsproc               ; the polygon's row loop (88.4.6)
    ZBYTE cs_cone                   ; the cull's cone factor this frame (88.5.1)
    ZBYTE cs_conebase               ; ...and the backend's: 0 = 0.5, 1 = 0.75
    ZBYTE cs_wire                   ; the object being drawn has no faces
    ZWORD cs_near                   ; ...and its near plane: CS_NEAR or CS_NEARG
    ZBYTE cs_pshr                   ; the object's transform scale (88.5.6):
    ZWORD cs_pfloor                 ; 0, 2 or 4 (whole, quarter, sixteenth
    ZWORD cs_pshiftp                ; metres), the table's floor and the
    ZWORD cs_scx                    ; projection's shift at that scale, and
    ZWORD cs_scy                    ; the origin from the eye's 16.8 position
    ZWORD cs_scz
    ZWORD cs_rwu                    ; cs_rwpt's u
    ZWORD cs_rwdu                   ; a runway stripe, on, in Q15 of the
                                    ; centreline (88.6.2); the pitch is twice
    ZBYTE cs_pgate                  ; the panel's rate gate (88.9.1)...
    ZWORD cs_plast                  ; ...and the tick the instruments last read
    ZWORD cs_bw                     ; cs_boxlod's half-width, and its
    ZWORD cs_bx0                    ; projected centre x, top row and base
    ZWORD cs_by0                    ; row
    ZWORD cs_by1
    ZWORD cs_hzproc
    ZWORD cs_glyphproc
    ZWORD cs_lsh                    ; the walk trio: shallow, steep, vertical
    ZWORD cs_lst
    ZWORD cs_lvt
    ZBYTE cs_ink
    ZBYTE cs_ink8
    ZBYTE cs_pbg8                   ; the panel's ground, as a glyph stores it
    ZBUF  cs_pat, 4                 ; the ink's four pattern bytes
    ZWORD cs_spcur                  ; this frame's span set and the last
    ZWORD cs_spprv                  ; frame's (SPEC.md 85.3.1, 88.3)
    ZBUF  cs_spanp, 4
    ZBUF  cs_spguard0, 8
    ZBUF  cs_span0, CS_MAXROW * 2
    ZBUF  cs_spguard1, 8
    ZBUF  cs_span1, CS_MAXROW * 2
    ZBUF  cs_spguard2, 8
    ZBYTE cs_mklo                   ; the bytes cs_markrows marks
    ZBYTE cs_mkhi
    ZWORD cs_pbx0                   ; a polygon's clamped x range
    ZWORD cs_pbx1
    ZWORD cs_oby0                   ; the OBJECT's mark, accumulated by
    ZWORD cs_oby1                   ; cs_markacc over its polygons and
    ZBYTE cs_oblo                   ; segments and marked once by
    ZBYTE cs_obhi                   ; cs_drawobj (SPEC.md 88.3.2)
    ZWORD cs_hzkt                   ; cs_hzrows' pattern table
    ZBUF  cs_devoff, CS_MAXROW * 2
    ZBUF  cs_rowoff, CS_MAXROW * 2
    ZBUF  cs_xl, CS_MAXROW * 2      ; a polygon's left and right bound per row
    ZBUF  cs_xr, CS_MAXROW * 2
    ZBUF  cs_rowkind, CS_MAXROW     ; a view row at the last blit: bits 0-1
                                    ; 0 all sky, 1 all ground, 3 split or
                                    ; unknown; bit 7 drawn on since (88.3)
    ZWORD cs_fullspan               ; the span pair of a touched view row
    ZWORD cs_slx                    ; the slice's (85.3.6): its first x, whole
    ZWORD cs_slq                    ; step, error, runs to go and last run
    ZWORD cs_slerr
    ZWORD cs_slcnt
    ZWORD cs_slfin
    ZWORD cs_cx1                    ; the clipper's four, CONTIGUOUS
    ZWORD cs_cy1
    ZWORD cs_cx2
    ZWORD cs_cy2
    ZBYTE cs_ctry
    ZBYTE cs_xdir
    ZWORD cs_e2
    ZWORD cs_ystep
    ZWORD cs_eq                     ; the edge tracer's step, remainder, dy,
    ZWORD cs_er                     ; and the lower end's row
    ZWORD cs_edy
    ZWORD cs_ey2
    ZWORD cs_py0                    ; a polygon's row range...
    ZWORD cs_py1
    ZWORD cs_pvp                    ; ...its vertex list and edges to go
    ZWORD cs_pei
    ZBYTE cs_pwind                  ; ...and its winding (88.4.2)
    ZBYTE cs_eside                  ; the chain an edge is on: 0 both, 1, 2
    ZWORD cs_lrunproc               ; the run a LINE's slice lays
    ZBUF  cs_pv, CS_MAXPV * 4       ; a projected face: (x, y) pairs
    ZWORD cs_pn
    ZWORD cs_rx1                    ; cs_prect's
    ZWORD cs_rx2
    ZWORD cs_ry2
    ZWORD cs_hzy0                   ; the horizon (88.4.1): the band's rows...
    ZWORD cs_hzy1
    ZWORD cs_hnx                    ; ...the quartered up vector...
    ZWORD cs_hny
    ZWORD cs_hnz
    ZDWORD cs_hza
    ZWORD cs_hzx0                   ; ...the intercept and the two ends...
    ZWORD cs_hzxa
    ZWORD cs_hzya
    ZWORD cs_hzyb
    ZBYTE cs_hzl                    ; ...the four inks...
    ZBYTE cs_hzr
    ZBYTE cs_hzab
    ZBYTE cs_hzbl
    ZWORD cs_hzlt                   ; ...and their pattern tables
    ZWORD cs_hzrt
    ZWORD cs_hzat
    ZWORD cs_hzbt
    ZWORD cs_hzpat
    ZBUF  cs_gbuf, 8
    ZWORD cs_gtab
    ZWORD cs_gseg
    ZBYTE cs_gfirst
    ZBYTE cs_glast
    ZWORD cs_gcol
    ZWORD cs_gcol2
    ZWORD cs_nibp

; --- the geometry -------------------------------------------------------------
    ZBUF  cs_m, 9 * 2               ; the camera matrix, rows right/up/forward
    ZWORD cs_sinh                   ; the six trig values it is built from
    ZWORD cs_cosh
    ZWORD cs_sinp
    ZWORD cs_cosp
    ZWORD cs_sinr
    ZWORD cs_cosr
    ZWORD cs_t1
    ZWORD cs_t2
    ZWORD cs_nx                     ; the world's up vector in camera space:
    ZWORD cs_ny                     ; the matrix's second column (88.4.1)
    ZWORD cs_nz
    ZWORD cs_rvx                    ; cs_rot's operand and result
    ZWORD cs_rvy
    ZWORD cs_rvz
    ZWORD cs_rox
    ZWORD cs_roy
    ZWORD cs_ex                     ; the eye, in whole metres, and the high
    ZWORD cs_exh                    ; words of x and z for the 32-bit cull
    ZWORD cs_ey
    ZWORD cs_ez
    ZWORD cs_ezh
    ZWORD cs_ddx                    ; an object's offset from the eye
    ZWORD cs_ddy
    ZWORD cs_ddz
    ZWORD cs_ocx                    ; the object's origin in camera space
    ZWORD cs_ocy
    ZWORD cs_ocz
    ZWORD cs_mdl
    ZWORD cs_obj
    ZBYTE cs_pass
    ZBUF  cs_col0, 6                ; the three scaled columns (88.5)
    ZBUF  cs_col1, 6
    ZBUF  cs_col2, 6
    ZWORD cs_lwx                    ; a level's half-widths and centre
    ZWORD cs_lwz
    ZWORD cs_lcx
    ZWORD cs_lcy
    ZWORD cs_lcz
    ZWORD cs_nv
    ZBUF  cs_cxv, CS_MAXV * 2
    ZBUF  cs_cyv, CS_MAXV * 2
    ZBUF  cs_czv, CS_MAXV * 2
    ZBUF  cs_sxv, CS_MAXV * 2
    ZBUF  cs_syv, CS_MAXV * 2
    ZBUF  cs_fv,  CS_MAXV * 2
    ZWORD cs_fn                     ; the face in hand: ends, ink, flags, list
    ZBYTE cs_fink
    ZBYTE cs_fflags
    ZWORD cs_fidx
    ZBUF  cs_clipx, CS_MAXPV * 6    ; a face clipped to the near plane, x/y/z
    ZWORD cs_ncl
    ZWORD cs_na
    ZWORD cs_nb
    ZWORD cs_nnum
    ZWORD cs_nden
    ZBUF  cs_kx, 2048 * 2           ; the projection tables (85.5.3, 88.5)
    ZBUF  cs_ky, 2048 * 2
    ZBUF  cs_vis, CS_NVIS * CS_VISZ ; the frame's objects: ptr, dx, dy, dz, along
    ZBUF  cs_vkey, CS_NVIS * 4      ; ...sorted far to near: along, record
    ZWORD cs_nvisn
    ZBUF  cs_rwverts, 6 * 4         ; the runway, built from the airport
    ZBUF  cs_rwmodel, CSM_SIZE
    ZBUF  cs_rwobj, CSO_SIZE
    ZWORD cs_rwax                   ; its along and across vectors
    ZWORD cs_rwaz
    ZWORD cs_rwcx
    ZWORD cs_rwcz

; --- the aeroplane (SPEC.md 88.7) ---------------------------------------------
    ZDWORD cs_px                    ; 16.8 metres
    ZDWORD cs_py
    ZDWORD cs_pz
    ZWORD cs_hdg                    ; 65536 to the turn
    ZWORD cs_pitch
    ZWORD cs_roll
    ZWORD cs_spd                    ; 16.8 m/s
    ZWORD cs_hs                     ; ...its horizontal component...
    ZWORD cs_vs                     ; ...and its vertical
    ZWORD cs_ht                     ; the ground moved this tick
    ZWORD cs_thr                    ; 0..100
    ZWORD cs_thrust                 ; CSP_THRUST x thr / 100, kept current
    ZBYTE cs_state
    ZBYTE cs_stall
    ZBYTE cs_inited                 ; the aeroplane has been put on the runway
    ZBYTE cs_kpitch                 ; the held keys, latched by cs_input and
    ZBYTE cs_kroll                  ; spent one step at a time by cs_step
    ZBYTE cs_kyaw
    ZBYTE cs_kthr
    ZBYTE cs_kbrake
    ZBYTE cs_pause
    ZWORD cs_crasht
    ZWORD cs_crashwhy               ; a string: what was hit
    ZWORD cs_crashes                ; read by tests/skies.py
    ZWORD cs_landings
    ZBYTE cs_msg
    ZBYTE cs_sound
    ZWORD cs_tone                   ; the engine tone being played, or 0
    ZWORD cs_last                   ; the tick the last frame was stepped at
    ZWORD cs_frames                 ; frames rendered; the only instrument
    ZWORD cs_rwsin                  ; the runway heading's sine and cosine
    ZWORD cs_rwcos
    ZWORD cs_along                  ; the aeroplane in runway coordinates
    ZWORD cs_across
    ZBYTE cs_stallt                 ; the stall beep's cadence

; --- the panel (SPEC.md 88.9) -------------------------------------------------
    ZBUF  cs_pkeys, 2 * 16 * 2      ; sixteen items' keys, one set per page
    ZWORD cs_pcur                   ; the item in hand, and its key
    ZWORD cs_pkeyv
    ZBYTE cs_ppage                  ; the page whose keys apply
    ZBUF  cs_numbuf, 16
    ZBUF  cs_msgbuf, 48
    ZWORD cs_hsx                    ; the panel's horizontal scale, in eighths
    ZWORD cs_pany                   ; the panel's first row
    ZBYTE cs_pfirst                 ; bit n: page n has never had its ground

; --- the shared controls (SPEC.md 20.5.1) -------------------------------------
%define OS88UI_ABOUT
%define OS88UI_NOBTN
%include "os88ui.inc"

    OS88_BSS CS_BSS
    OS88_IMAGE_END
