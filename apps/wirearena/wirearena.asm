; WireArena - Wave 0 of docs/plans/MULTIPLAYER-FPS-PLAN.md: the renderer
; spike. A text-mode first-person arena: thin dim wall edges on black, solid
; bright stick figures, presented as changed cells only. It exists to answer
; the plan's first question on the glass - 80 or 40 columns - and to measure
; what a frame costs, so the HUD carries the meter.
;
; Not a game yet: three dummies run patrols, the pistol knocks them down
; (flinch, death, respawn), and there is no network and no opponent AI.
; Controls: mouse look (OSAPI_MOUSE_REL, SPEC.md 9.14), W/A/S/D move,
; arrows turn and pitch, Space jumps, left button or Ctrl fires, Tab swaps
; 80 and 40 columns, V waits for vertical retrace before presenting, B runs
; the bench (64 frames, a fixed spin - section 16 of the plan), Esc leaves.
%include "os88api.inc"
    OS88_HEADER 'WARENA', wa_entry, OS88_F_PARTS, OS88_HIGH | OS88_HIGHMEM
%define OP_WANT_CSEG            ; the renderer part is far-called through its
%define OP_ONMOVE wa_partsmv    ; CODE selector, and its claim MOVES (SPEC.md
%include "os88parts.inc"        ; 20.12.12): wa_partsmv re-reads both words

%include "waconst.inc"
%include "watab.inc"               ; its constants (the data comes later)
%include "wafb.inc"                ; the renderer part's ABI

wa_entry:
    clc                         ; kern_small refuses the relative mouse, and
    call OSAPI_MOUSE_REL        ; WireArena refuses kern_small (the owner,
    jc .small                   ; 2026-11-13): kern_big and kern_mega only
    call op_load                ; the renderer part (SPEC.md 20.12): SI is
    jc .out                     ; the kernel's, so before anything else; a
    call wa_rbind               ; refusal has said why in a toast
    jc .out
    mov al, OP_CARVE            ; ...and its claim may move: wa_partsmv
    call op_movable             ; re-reads the two words wa_rbind banked
    mov byte [wa_fov], 1        ; 75 degrees: the owner's pick of the three
    call OSAPI_CPU_INFO         ; THE DETAIL LEVEL (HEIGHTS-PLAN 9.10): Medium
    cmp al, CPU_8086            ; on the target machine, High (Medium and the
    mov al, 2                   ; floor grid, ~13 ms a frame on a 4.77 MHz
    je .lev                     ; 8088) on a 286 or better; keys 1..5
    mov al, 3
.lev:
    call wa_setlevel
    mov si, wa_tpl
    call OSAPI_WM_CREATE
    jc .out
    OS88_REGION_MOVABLE
    mov [wa_win], bx
    mov si, wa_menus
    call OSAPI_MENU_SET
    mov bx, [wa_win]
    clc
.out:
    ret
.small:
    push ds
    pop es
    mov si, wa_t_small
    xor cx, cx
    call OSAPI_TOAST
    stc
    ret

; --- the window ---------------------------------------------------------------
wa_paint:
    push ax
    push bx
    push cx
    push dx
    push si
    mov bx, si
    call OSAPI_WM_CONTENT       ; AX = left, DX = top
    mov bx, ax
    add bx, 8
    add dx, 6
    mov si, wa_help
.line:
    cmp byte [si], 0
    je .done
    mov cx, bx
    mov ax, (CWHITE << 8) | CBLACK  ; AL = ink, AH = the ground
    call OSAPI_FONT_RUN
.skip:
    lodsb
    or al, al
    jnz .skip
    add dx, 10
    jmp .line
.done:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

wa_oncmd:                       ; Game menu: wa_items maps the item
    xor ah, ah                  ; to (width, arena)
    shl ax, 1
    mov bx, ax
    mov al, [wa_items+bx]
    mov [wa_want], al
    mov al, [wa_items+bx+1]
    mov [wa_arena], al
    call wa_loadarena           ; off its part, before the bracket: CF = 1
    jc .out                     ; it could not be read, and a toast said why
    mov ax, wa_main
    mov bx, [wa_win]
    xor cx, cx
    call OSAPI_FSX_RUN
.out:
    ret

; --- the bracket ----------------------------------------------------------
wa_main:
    push ds
    pop es
    mov al, [wa_want]
    call wa_setmode
    jnc .go
    mov al, 0                   ; 40 refused (Hercules): 80 it is
    call wa_setmode
    jc .out
.go:
    call wa_geominit            ; (wa_oncmd loaded the arena)
    call wa_reset
    call OSAPI_MOUSE_REL        ; the desktop's motion is not ours: discard
    xor ax, ax
    mov [wa_acc], ax
    mov [wa_acc+2], ax
    call pit_now
    mov [wa_last], ax
    mov [wa_last+2], dx
.loop:                          ; DX:AX = now (the last frame's present's
    mov bx, ax                  ; end: one PIT read a frame fewer)
    mov cx, dx
    sub ax, [wa_last]
    sbb dx, [wa_last+2]
    mov [wa_last], bx
    mov [wa_last+2], cx
    add [wa_tfr], ax            ; frame time, summed for the meter
    adc [wa_tfr+2], dx
    add ax, [wa_acc]
    adc dx, [wa_acc+2]
    cmp dx, (WA_TICK*4) >> 16   ; more than four ticks behind: drop the
    jb .owe                     ; rest of the debt (a mode switch, the
    ja .cap                     ; bench). Four, not one: at 11 frames a
    cmp ax, (WA_TICK*4) & 0xFFFF ; second the sim owes ~3 ticks a frame, and
    jbe .owe                    ; a cap of one ran the world at a third of
.cap:                           ; its speed
    mov ax, (WA_TICK*4) & 0xFFFF
    mov dx, (WA_TICK*4) >> 16
.owe:
    mov [wa_acc], ax
    mov [wa_acc+2], dx
.sim:
    cmp word [wa_acc+2], 0
    jne .step
    cmp word [wa_acc], WA_TICK
    jb .simmed
.step:
    sub word [wa_acc], WA_TICK
    sbb word [wa_acc+2], 0
    call wa_tick
    jmp .sim
.simmed:
    call wa_frame_input
    cmp byte [wa_quit], 0
    jne .out
    call pit_now
    mov [wa_t0], ax
    mov [wa_t0+2], dx
    call wa_render
    call pit_now
    mov bx, ax
    mov cx, dx
    sub ax, [wa_t0]
    sbb dx, [wa_t0+2]
    add [wa_trn], ax
    adc [wa_trn+2], dx
    mov [wa_t0], bx
    mov [wa_t0+2], cx
    cmp byte [wa_vsync], 0
    je .present
    mov al, FSXW_VSYNC
    call OSAPI_FSX_WAIT
    call pit_now
    mov [wa_t0], ax
    mov [wa_t0+2], dx
.present:
    call wa_present
    call pit_now
    push dx
    push ax
    sub ax, [wa_t0]
    sbb dx, [wa_t0+2]
    add [wa_tpr], ax
    adc [wa_tpr+2], dx
    call wa_meter
    pop ax
    pop dx
    jmp .loop
.out:
    ret

; wa_setmode - AL = 0 for 80 columns, 1 for 40. CF = 1 refused.
wa_setmode:
    mov [wa_mode], al
    push ds
    pop es
    mov di, wa_fsi
    call OSAPI_FSX_MODE         ; FSXM_TEXT80 = 0, FSXM_TEXT40 = 1
    jc .out
    mov ax, [wa_fsi+FSI_SEG]
    mov [wa_vseg], ax
    mov ax, [wa_fsi+FSI_W]
    mov [wa_w], ax
    call wa_setfov
    mov ax, [wa_w]
    shl ax, 1
    mov [wa_w2], ax             ; 2W: the figures' sub-columns
    mov byte [wa_mono], 0
    cmp word [wa_vseg], 0xB000
    jne .colour
    mov byte [wa_mono], 1
.colour:
    mov ah, 1                   ; hide the cursor (SPEC.md 53.4's bare text
    mov cx, 0x2000              ; contract: the cursor is the app's)
    int 10h
    xor bx, bx                  ; row offsets, in cells (the HUD's; the
    mov si, wa_rowoff           ; renderer makes its own, in cell offsets)
    mov cx, WA_ROWS + 1
.rows:
    mov [si], bx
    add bx, [wa_w]
    inc si
    inc si
    loop .rows
    call wa_rsync               ; the mode into the renderer part, and its
    mov bx, WRV_INIT            ; row tables, stamps and lists started again
    call wa_rcall
    push ds
    pop es
    xor ax, ax
    mov [wa_frame], al
    mov [wa_tfr], ax            ; and the meter starts again
    mov [wa_tfr+2], ax
    mov [wa_trn], ax
    mov [wa_trn+2], ax
    mov [wa_tpr], ax
    mov [wa_tpr+2], ax
    mov [wa_nfr], ax
    mov [wa_ncells], ax
    mov [wa_ncells+2], ax
    mov si, wa_hudtpl           ; the HUD's fixed text
    call wa_hudfix
    clc
.out:
    ret

; wa_setfov - the projection's scales for [wa_fov] (0 = 90, 1 = 75, 2 = 60
; degrees across) at [wa_w] columns: f = 1 / tan(half the field), 8.8, on
; the column scale (8W f) and both vertical ones, so a narrower view is a
; zoom and the proportions hold. A wall at the edge of a 90-degree view
; projects 1.41x the height it has at the centre; at 60 degrees 1.15x.
wa_setfov:
    mov bl, [wa_fov]
    xor bh, bh
    shl bx, 1
    mov cx, [wa_fovf+bx]
    mov ax, [wa_w]
    mul cx
    mov [wa_wf], ax             ; W f (8.8 -> sub-columns x 256 a unit at z 1)
    mov ax, [wa_w]
    shl ax, 1
    shl ax, 1
    shl ax, 1
    mov [wa_c16], ax            ; 8W: the screen's centre, x16 - whatever f is
    mov ax, [wa_w]
    shl ax, 1
    shl ax, 1
    shl ax, 1
    mul cx
    mov al, ah
    mov ah, dl
    mov [wa_k16], ax            ; 8 W f
    mov ax, WA_KYQ
    mul cx
    mov al, ah
    mov ah, dl
    mov [wa_kyq], ax
    mov ax, WA_KYH256
    mul cx
    mov al, ah
    mov ah, dl
    mov [wa_kyh], ax
    jmp wa_rsync                ; ...and into the renderer part
wa_fovf:    dw 256, 334, 443
wa_fovc:    db '976'    ; 1/tan(45), 1/tan(37.5), 1/tan(30), x 256

wa_reset:
    mov ax, [wa_sx]
    mov [wa_px], ax
    mov ax, [wa_sy]
    mov [wa_py], ax
    xor ax, ax
    mov [wa_pxf], ax
    mov [wa_pyf], ax
    mov ax, [wa_sa]
    mov cl, 6
    shl ax, cl
    mov [wa_ang], ax
    xor ax, ax                  ; (the rest start at 0: AX held the angle)
    mov [wa_pitch], ax
    mov [wa_jz], ax
    mov [wa_jv], ax
    mov [wa_quit], al
    mov [wa_hits], ax
    mov [wa_kills], ax
    mov [wa_feet], ax
    mov word [wa_eye], WA_EYE
    mov [wa_lon], ax            ; the lift at rest, nobody on it
    mov [wa_loff], ax
    dec ax
    mov [wa_fpx], ax            ; (the floor: read afresh)
    inc ax
    call wa_lset0
    mov di, wa_figs
    xor bx, bx
.fig:
    mov si, [wa_pptr]           ; the arena's own patrols, or ours
    mov si, [si+bx]
    mov [di+F_PATH], si
    call wa_spawn
    add di, F_SIZE
    inc bx
    inc bx
    cmp bx, WA_NFIG*2
    jb .fig
    ret

; wa_spawn - DI = a figure: to its path's first waypoint, running, 3 hits
wa_spawn:
    push si
    mov si, [di+F_PATH]
    mov ax, [si+2]
    mov [di+F_X], ax
    mov ax, [si+4]
    mov [di+F_Y], ax
    mov ax, [si+6]
    and ax, 1023                ; (bit 15: the leg climbs, wa_figz)
    mov [di+F_HEAD], ax
    mov [di+F_ANG], ax
    mov ax, [si+8]
    mov [di+F_STEP], ax
    mov word [di+F_LEG], 0
    mov byte [di+F_HP], 3
    mov byte [di+F_DEAD], 0
    mov byte [di+F_FLASH], 0
    mov word [di+F_PZ], 0
    call wa_figz
    call wa_runanim
    pop si
    ret

wa_runanim:
    mov byte [di+F_ANIM], WA_A_RUN
    mov byte [di+F_NFR], WA_N_RUN
    mov byte [di+F_LOOP], 1
    mov word [di+F_PH], 0
    ret

; --- input ----------------------------------------------------------------
; once a frame: typed keys, mouse look, the trigger
wa_frame_input:
.drain:
    mov ah, 1
    int 16h
    jz .typed
    xor ah, ah
    int 16h
    mov byte [wa_hold], 0       ; any typed key frees the meter
    cmp ah, KSC_ESC
    jne .tab
    mov byte [wa_quit], 1
    jmp .drain
.tab:
    cmp ah, 0x0F                ; Tab: the other width
    jne .v
    mov al, [wa_mode]
    xor al, 1
    call wa_setmode
    jnc .drain
    mov al, [wa_mode]           ; refused (no 40 on Hercules): put it back
    xor al, 1
    call wa_setmode
    jmp .drain
.v:
    cmp ah, 0x2F                ; V: present after vertical retrace
    jne .b
    xor byte [wa_vsync], 1
    jmp .drain
.b:
    cmp ah, 0x21                ; F: the field of view, 90 -> 75 -> 60
    jne .bg
    inc byte [wa_fov]
    cmp byte [wa_fov], 3
    jb .fov
    mov byte [wa_fov], 0
.fov:
    call wa_setfov
    jmp .drain
.bg:
    cmp ah, 0x22                ; G: the floor grid
    jne .bl
    xor byte [wa_grid], 1
    jmp .drain
.bl:
    cmp ah, 0x26                ; L: the walls' tops off (sparse): a debug
    jne .bb                     ; key, in no detail level
    xor byte [wa_sparse], 1
    jmp .drain
.bb:
    cmp ah, 0x30                ; B: the bench
    jne .bp
    call wa_bench
    jmp .drain
.bp:
    cmp ah, 0x14                ; T: a ramp drawn as stepped treads (the
    jne .bpb                    ; graphics option, HEIGHTS-PLAN 7.4.2)
    xor byte [wa_treads], 1
    jmp .drain
.bpb:
    cmp ah, 0x19                ; P: the PLAY bench
    jne .bk
    call wa_pbstart
    jmp .drain
.bk:
    cmp ah, 0x13                ; R: a ramp drawn as its two sides (RAMP2,
    jne .bn                     ; its own key while the owner judges it)
    xor byte [wa_look], LK_RAMP2
    jmp .drain
.bn:
    mov al, ah                  ; 1..5: the DETAIL LEVEL (HEIGHTS-PLAN 9.10)
    sub al, 0x02
    cmp al, WA_NLEV
    jae .drain
    call wa_setlevel
    jmp .drain
.typed:
    cmp byte [wa_pbon], 0
    je .live
    call OSAPI_MOUSE_REL        ; (the hand's motion is not the test's)
    jmp wa_pbview
.live:
    call OSAPI_MOUSE_REL
    jc .nomouse                 ; kern_small refuses: keys only
    mov bl, al                  ; the buttons
    sub [wa_pitch], dx          ; pitch: down is +dy, the horizon rises
    mov ax, cx                  ; yaw: right is clockwise, angle falls
    mov cx, 96
    imul cx
    sub [wa_ang], ax
    jmp .clamp
.nomouse:
    xor bl, bl
.clamp:                         ; 112 quarter half-rows up, 290 down: 33
    cmp word [wa_pitch], WA_PITCHU ; and 59 degrees at 75, the same reach
    jle .lo                     ; from the tower and its foot (HEIGHTS-
    mov word [wa_pitch], WA_PITCHU ; PLAN 7.1.1; down is a falling pitch)
.lo:
    cmp word [wa_pitch], -WA_PITCHD
    jge .fire
    mov word [wa_pitch], -WA_PITCHD
.fire:
    KEYMAP_TEST wa_kmap, 0x1D   ; Ctrl is a trigger too: the map the
    jz .btn                     ; frame's first tick took (wa_keys)
    or bl, 1
.btn:
    and bl, 1
    mov al, bl
    xchg al, [wa_trig]
    cmp al, 0
    jne .held                   ; edge only: one shot a press
    cmp bl, 0
    je .held
    call wa_fire
.held:
    ret

; --- the 30 Hz tick -------------------------------------------------------
; The keys a tick reads, polled ONCE A FRAME (wa_keys): the ticks a frame
; runs are its catch-up, all due at the same instant, so they read one
; poll. ONE OSAPI_KEY_MAP (SPEC.md 9.7.3) for all of them - an OSAPI_KEY_DOWN
; is ~540 clk EACH, so nine were ~1 ms of a frame, and asking only the keys
; that could have changed was still ~2,000 clk with a sweep every fourth
; frame to catch the presses the BIOS never enqueues. The map has no such
; gap: a press is seen the frame it lands, Ctrl or Alt with it or not, and a
; release the next frame.
WA_K_LEFT   equ 1
WA_K_RIGHT  equ 2
WA_K_UP     equ 4
WA_K_DOWN   equ 8
WA_K_W      equ 16
WA_K_S      equ 32
WA_K_A      equ 64
WA_K_D      equ 128
WA_K_SPACE  equ 256

; WA_KBIT scancode, bit - the held key's bit into BX
%macro WA_KBIT 2
    KEYMAP_TEST wa_kmap, %1
    jz %%up
 %if (%2) > 255
    or bh, (%2) >> 8
 %else
    or bl, %2
 %endif
%%up:
%endmacro

; wa_keys - the held keys into [wa_kbits] (WA_K_*), and the whole map into
; wa_kmap for wa_frame_input's trigger. Keeps all but the flags.
wa_keys:
    push bx
    push di
    mov di, wa_kmap
    call OSAPI_KEY_MAP          ; every key at once (and the first call arms)
    xor bx, bx
    WA_KBIT KSC_LEFT, WA_K_LEFT
    WA_KBIT KSC_RIGHT, WA_K_RIGHT
    WA_KBIT KSC_UP, WA_K_UP
    WA_KBIT KSC_DOWN, WA_K_DOWN
    WA_KBIT 0x11, WA_K_W
    WA_KBIT 0x1F, WA_K_S
    WA_KBIT 0x1E, WA_K_A
    WA_KBIT 0x20, WA_K_D
    WA_KBIT KSC_SPACE, WA_K_SPACE
    mov [wa_kbits], bx
    pop di
    pop bx
    ret

wa_tick:
    mov al, [wa_frame]          ; this frame's first tick polls the keys
    cmp al, [wa_kfr]
    je .polled
    mov [wa_kfr], al
    call wa_keys
.polled:
    cmp byte [wa_pbon], 0
    je .live
    inc word [wa_pbtk]           ; the play bench: its clock, and no keys
    mov word [wa_kbits], 0
.live:
    mov dx, [wa_kbits]
    or dx, dx
    jz .jump                    ; nothing held: no turn, no step
    test dl, WA_K_LEFT
    jz .r
    add word [wa_ang], 12 << 6
.r:
    test dl, WA_K_RIGHT
    jz .u
    sub word [wa_ang], 12 << 6
.u:
    test dl, WA_K_UP
    jz .d
    add word [wa_pitch], 4
.d:
    test dl, WA_K_DOWN
    jz .move
    sub word [wa_pitch], 4
.move:
    xor bx, bx                  ; BL = forward, BH = right, each -1/0/+1
    test dl, WA_K_W
    jz .s
    inc bl
.s:
    test dl, WA_K_S
    jz .a
    dec bl
.a:
    test dl, WA_K_A
    jz .dk
    dec bh
.dk:
    test dl, WA_K_D
    jz .walk
    inc bh
.walk:
    or bx, bx
    jz .jump                    ; standing: no step, nothing to collide
    mov ax, [wa_ang]
    mov cl, 6
    shr ax, cl
    call wa_sincos              ; AX = sin, DX = cos (Q14)
    sar ax, 1                   ; Q13, so forward + strafe cannot overflow
    sar dx, 1
    ; vx = fwd*cos + right*sin ; vy = fwd*sin - right*cos
    xor si, si                  ; vx
    xor di, di                  ; vy
    or bl, bl
    jz .side
    js .back
    add si, dx
    add di, ax
    jmp .side
.back:
    sub si, dx
    sub di, ax
.side:
    or bh, bh
    jz .apply
    js .left
    add si, ax
    sub di, dx
    jmp .apply
.left:
    sub si, ax
    add di, dx
.apply:
    or si, si
    jz .ymove                   ; (no x step: the x position cannot collide)
    mov ax, si
    mov cx, WA_MSPD
    imul cx                     ; DX:AX = the step, 16.16 units
    mov bx, [wa_px]
    mov cx, [wa_pxf]
    add [wa_pxf], ax
    adc [wa_px], dx
    call wa_collide
    jnc .ymove
    mov [wa_px], bx
    mov [wa_pxf], cx
.ymove:
    or di, di
    jz .jump
    mov ax, di
    mov cx, WA_MSPD
    imul cx
    mov bx, [wa_py]
    mov cx, [wa_pyf]
    add [wa_pyf], ax
    adc [wa_py], dx
    call wa_collide
    jnc .jump
    mov [wa_py], bx
    mov [wa_pyf], cx
.jump:
    cmp byte [wa_aflat], 0      ; HEIGHTS: the floor under the feet, the
    jne .flatj                  ; step, the fall and the landing, and the
    call wa_hjump               ; lift (HEIGHTS-PLAN 3.1, 3.2)
    jmp .grounded
.flatj:
    cmp word [wa_jz], 0
    jne .air
    cmp word [wa_jv], 0
    jne .air
    test word [wa_kbits], WA_K_SPACE
    jz .grounded
    mov word [wa_jv], WA_JUMPV
.air:
    mov ax, [wa_jv]
    add [wa_jz], ax
    sub word [wa_jv], WA_GRAV
    cmp word [wa_jz], 0
    jg .grounded
    xor ax, ax
    mov [wa_jz], ax
    mov [wa_jv], ax
.grounded:
    mov ax, [wa_jz]
    mov al, ah                  ; 8.8 -> units
    cbw
    add ax, WA_EYE
    add ax, [wa_feet]           ; (the floor under the player: 0 until
    mov [wa_eye], ax            ; HEIGHTS-PLAN wave 3, but for the benches)
    cmp byte [wa_mflash], 0
    je .figs
    dec byte [wa_mflash]
.figs:
    mov di, wa_figs
    mov cx, WA_NFIG
.fig:
    push cx
    call wa_figtick
    pop cx
    add di, F_SIZE
    loop .fig
    ret

; wa_collide - CF = 1 when the player at [wa_px],[wa_py] is inside a wall.
; Keeps every register. The player's square is widened once (x +- R, y +-
; R), so a box is four compares against its own corners.
wa_collide:
    cmp byte [wa_aflat], 0
    jne .flat
    jmp wa_hcollide
.flat:
    push ax
    push bx
    push cx
    push dx
    push si
    push bp
    mov ax, [wa_px]
    mov bx, [wa_py]
    cmp ax, WA_ROOM_X0 + WA_RAD
    jl .hit
    cmp ax, WA_ROOM_X1 - WA_RAD
    jg .hit
    cmp bx, WA_ROOM_Y0 + WA_RAD
    jl .hit
    cmp bx, WA_ROOM_Y1 - WA_RAD
    jg .hit
    mov dx, ax
    add dx, WA_RAD              ; DX = x + R, AX = x - R
    sub ax, WA_RAD
    mov bp, bx
    add bp, WA_RAD              ; BP = y + R, BX = y - R
    sub bx, WA_RAD
    mov si, wa_boxes
    mov cx, [wa_nbox]
.box:
    cmp dx, [si]                ; inside x0 - R < x < x1 + R, and the same
    jle .next                   ; for y
    cmp ax, [si+4]
    jge .next
    cmp bp, [si+2]
    jle .next
    cmp bx, [si+6]
    jl .hit
.next:
    add si, 8
    loop .box
    clc
    jmp .out
.hit:
    stc
.out:
    pop bp
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- heights: the floor, the step, the fall, the lift (HEIGHTS-PLAN 3) -----
; The floor under a square is the tallest height of any box it overlaps - a
; RAMP's (a FLIGHT's, kind 1) at the square's highest point on it, the slope
; linear from 0 at its low face to its height at the face it rises toward
; (arenagen's height_at, to the unit). A move is refused where that is more
; than a step (WA_STEPUP) above the feet; on the ground the feet follow the
; floor up a step and down one, and past that they fall; in the air the
; feet land on whatever floor they come down onto. A flat arena never comes
; here (wa_aflat): its walls and its jump are as they were.

; wa_floor - AX = x, BX = y, SI = a box table (wa_lists: wa_lowp, the low
; boxes, for the player's square; wa_lowf, for a dummy's feet; wa_allp,
; every box, a wall at its height, for the player's collision): AX = the
; floor under the square (x +- r, y +- r, r the table's), DX = the record
; (x 4, into wa_bxh) of the box it is, -1 the ground. Each entry holds its
; box WIDENED by r, so overlapping it is the point inside: four compares
; against registers. Keeps BX, CX, SI, DI, BP.
WA_LTE      equ 12              ; a table's entry: x0-r, y0-r, x1+r, y1+r,
                                ; box x 8 (wa_boxes), box x 4 (wa_bxh)
wa_floor:
    push si
    push di
    push bp
    push cx
    mov [wa_qx], ax
    mov [wa_qy], bx
    mov cx, [si]                ; CX = its entries
    mov di, [si+2]
    mov [wa_qr], di             ; (its r, for a ramp's reach)
    add si, 4
    xor bp, bp                  ; BP = the floor so far, DX its record
    mov dx, -1
    jcxz .done
.box:
    cmp ax, [si]
    jle .next
    cmp ax, [si+4]
    jge .next
    cmp bx, [si+2]
    jle .next
    cmp bx, [si+6]
    jge .next
    mov di, [si+10]
    push si
    mov si, [si+8]
    add di, wa_bxh
    call wa_hat                 ; AX = its height there (AX was x: again
    sub di, wa_bxh              ; after)
    pop si
    cmp ax, bp
    jbe .again
    mov bp, ax
    mov dx, di
.again:
    mov ax, [wa_qx]
.next:
    add si, WA_LTE
    loop .box
.done:
    mov ax, bp
    pop cx
    pop bp
    pop di
    pop si
    ret

; wa_lists - once an arena is loaded: its box tables (wa_floor's), every box
; for the player's collision and the low ones (below the tallest height,
; and the lift) for the player's floor and a dummy's
wa_lists:
    mov di, wa_allp
    mov dx, WA_RAD
    xor bp, bp                  ; (every box)
    call .one
    mov di, wa_lowp
    mov dx, WA_RAD
    mov bp, 1                   ; (the low ones)
    call .one
    mov di, wa_lowf
    mov dx, WA_FRAD
    ; (falls through)
.one:                           ; DI = the table, DX = r, BP = 1 low only
    push di
    mov [di+2], dx
    add di, 4
    xor bx, bx                  ; BX = box x 8
    xor cx, cx                  ; CX = its entries
.b:
    cmp bx, [wa_nbox8]
    jae .end
    mov si, bx
    shr si, 1                   ; SI = box x 4
    or bp, bp
    jz .take
    mov ax, [wa_bxh+si]
    cmp ax, [wa_ahmax]
    jae .skip
.take:
    mov ax, [wa_boxes+bx]
    sub ax, dx
    mov [di], ax
    mov ax, [wa_boxes+bx+2]
    sub ax, dx
    mov [di+2], ax
    mov ax, [wa_boxes+bx+4]
    add ax, dx
    mov [di+4], ax
    mov ax, [wa_boxes+bx+6]
    add ax, dx
    mov [di+6], ax
    lea ax, [wa_boxes+bx]
    mov [di+8], ax
    mov [di+10], si
    add di, WA_LTE
    inc cx
.skip:
    add bx, 8
    jmp .b
.end:
    pop di
    mov [di], cx
    ret

; wa_hat - SI = a box (wa_boxes), DI = its record, the square overlapping it
; ([wa_qx], [wa_qy] +- [wa_qr]): AX = its height under the square. Keeps
; every register but AX. A ramp's: h x num / len, num the square's reach along it from its
; low face (1 <= num <= len, the square overlapping it), len its extent
; (> 0: arenagen refuses an empty box) - so the quotient is at most h and
; the divide cannot fault (HEIGHTS-PLAN 9.5)
wa_hat:
    mov ax, [di]
    test byte [di+2], 3
    jz .out                     ; (solid, or a lift: its height as it is)
    test byte [di+2], 2
    jnz .out
    push bx
    push cx
    push dx
    mov bl, [di+2]
    and bl, 0x0C                ; the face it rises toward, x 4
    cmp bl, 0x04
    je .e
    cmp bl, 0x08
    je .n
    cmp bl, 0x0C
    je .w
    mov cx, [si+6]              ; S: num = y1 - max(qy0, y0)
    mov bx, [wa_qy]
    sub bx, [wa_qr]
    cmp bx, [si+2]
    jge .s1
    mov bx, [si+2]
.s1:
    sub cx, bx
    jmp .ylen
.n:
    mov cx, [wa_qy]             ; N: num = min(qy1, y1) - y0
    add cx, [wa_qr]
    cmp cx, [si+6]
    jle .n1
    mov cx, [si+6]
.n1:
    sub cx, [si+2]
.ylen:
    mov bx, [si+6]
    sub bx, [si+2]
    jmp .div
.w:
    mov cx, [si+4]              ; W: num = x1 - max(qx0, x0)
    mov bx, [wa_qx]
    sub bx, [wa_qr]
    cmp bx, [si]
    jge .w1
    mov bx, [si]
.w1:
    sub cx, bx
    jmp .xlen
.e:
    mov cx, [wa_qx]             ; E: num = min(qx1, x1) - x0
    add cx, [wa_qr]
    cmp cx, [si+4]
    jle .e1
    mov cx, [si+4]
.e1:
    sub cx, [si]
.xlen:
    mov bx, [si+4]
    sub bx, [si]
.div:
    mul cx                      ; DX:AX = h x num, < len x 65536
    div bx                      ; (num <= len: no fault)
    pop dx
    pop cx
    pop bx
.out:
    ret

; wa_hcollide - CF = 1 when the player at [wa_px],[wa_py] stands where the
; floor is more than a step above the feet (in the air: above the feet at
; all), or outside the room. Keeps every register.
wa_hcollide:
    push ax
    push bx
    push cx
    push dx
    push si
    mov ax, [wa_px]
    mov bx, [wa_py]
    cmp ax, WA_ROOM_X0 + WA_RAD
    jl .hit
    cmp ax, WA_ROOM_X1 - WA_RAD
    jg .hit
    cmp bx, WA_ROOM_Y0 + WA_RAD
    jl .hit
    cmp bx, WA_ROOM_Y1 - WA_RAD
    jg .hit
    mov si, wa_allp
    call wa_floor
    call wa_fabs                ; DX = the feet, units: on the ground a
    mov cx, [wa_jz]             ; step more, in the air nothing more - a
    or cx, [wa_jv]              ; jump reaches what its feet clear (the
    jnz .air                    ; back room's 48, not the platform's 80)
    add dx, WA_STEPUP
.air:
    cmp ax, dx
    jg .hit
    clc
    jmp .out
.hit:
    stc
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; wa_fabs - DX = the feet's height: the floor they stood on plus the jump,
; whole units (wa_jz is 8.8 above wa_feet). Keeps every other register.
wa_fabs:
    push ax
    mov ax, [wa_jz]
    mov al, ah
    cbw
    add ax, [wa_feet]
    mov dx, ax
    pop ax
    ret

; wa_hjump - the tick's vertical: the floor under the player (wa_flr, and
; its box), the jump, the step up and down, the fall, the landing; then the
; lift. On the ground (wa_jz = wa_jv = 0) the feet ARE wa_feet; in the air
; wa_feet is a base and wa_jz the height above it, 8.8, rebased whenever it
; would go below 0 so that a fall from any height stays in range.
wa_hjump:
    mov ax, [wa_px]             ; (the floor read again only where the
    mov bx, [wa_py]             ; player has moved, or stands on the lift,
    cmp ax, [wa_fpx]            ; which moves under them)
    jne .read
    cmp bx, [wa_fpy]
    jne .read
    mov ax, [wa_flrb]
    or ax, ax
    js .same                    ; (the ground)
    cmp ax, [wa_lift]
    je .read
.same:
    mov ax, [wa_flr]
    jmp .have
.read:
    mov [wa_fpx], ax
    mov [wa_fpy], bx
    mov si, wa_lowp
    call wa_floor
    mov [wa_flr], ax
    mov [wa_flrb], dx
.have:
    mov cx, [wa_jz]
    or cx, [wa_jv]
    jnz .air
    test word [wa_kbits], WA_K_SPACE
    jz .walk
    mov word [wa_jv], WA_JUMPV
    jmp .air
.walk:
    mov dx, [wa_feet]           ; the step: up (wa_hcollide let no more
    cmp ax, dx                  ; than a step through), or down a step -
    jge .onto                   ; past that, a fall
    sub dx, ax
    cmp dx, WA_STEPUP
    ja .air
.onto:
    mov [wa_feet], ax
    jmp wa_ltick
.air:
    mov ax, [wa_jv]
    add [wa_jz], ax
    sub word [wa_jv], WA_GRAV
    mov ax, [wa_jz]
    or ax, ax
    jns .chk
    mov dx, ax                  ; below the base: whole units into wa_feet
    mov cl, 8                   ; (rounded down), the fraction kept
    sar dx, cl
    add [wa_feet], dx
    and word [wa_jz], 0x00FF
.chk:
    cmp word [wa_jv], 0         ; still rising: no landing yet
    jg wa_ltick
    call wa_fabs
    cmp dx, [wa_flr]
    jl .land                    ; (below the floor: onto it)
    jg wa_ltick
    test word [wa_jz], 0x00FF   ; at it, no fraction over: down
    jnz wa_ltick
.land:
    mov ax, [wa_flr]
    mov [wa_feet], ax
    xor ax, ax
    mov [wa_jz], ax
    mov [wa_jv], ax
    ; (falls through)

; wa_ltick - the lift's tick (HEIGHTS-PLAN 3.2): someone standing on it
; (the player's floor is its box, on the ground) for WA_LWAIT ticks sends
; it up WA_LSPD a tick to its raised height; empty for WA_LHOLD it comes
; back down. Its height goes into wa_bxh, which wa_floor reads, and the
; renderer's copy every frame (wa_rframe). A rider's feet follow it by the
; step rule: WA_LSPD is under a step.
WA_LWAIT    equ 10              ; 1/3 s on it before it starts
WA_LHOLD    equ 45              ; 1.5 s empty before it returns
WA_LSPD     equ 5               ; units a tick: 144 in ~1 s
wa_ltick:
    mov bx, [wa_lift]
    or bx, bx
    js .out
    mov ax, [wa_jz]
    or ax, [wa_jv]
    jnz .empty
    cmp bx, [wa_flrb]
    jne .empty
    mov word [wa_loff], 0
    inc word [wa_lon]
    cmp word [wa_lon], WA_LWAIT
    jb .out
    mov ax, [wa_bxh+bx]
    add ax, WA_LSPD
    cmp ax, [wa_ltop]
    jle .set
    mov ax, [wa_ltop]
    jmp .set
.empty:
    mov word [wa_lon], 0
    inc word [wa_loff]
    cmp word [wa_loff], WA_LHOLD
    jb .out
    mov ax, [wa_bxh+bx]
    sub ax, WA_LSPD
    cmp ax, [wa_lrest]
    jge .set
    mov ax, [wa_lrest]
.set:
    mov [wa_bxh+bx], ax
.out:
    ret

; wa_lset0 - the lift (if any) at its rest height
wa_lset0:
    mov bx, [wa_lift]
    or bx, bx
    js .out
    mov ax, [wa_lrest]
    mov [wa_bxh+bx], ax
.out:
    ret

; wa_figz - DI = a figure: F_Z, the floor under its feet (WA_FRAD), 0 on a
; flat arena. Its patrol is arenagen's to keep to steps (patrol checks).
; Keeps every register.
wa_figz:
    push ax
    push bx
    push cx
    push dx
    push si
    xor ax, ax
    cmp byte [wa_aflat], 0
    jne .set
    mov si, [di+F_PATH]         ; a leg arenagen found on the ground all
    add si, [di+F_LEG]          ; the way (its heading's bit 15 clear):
    test byte [si+7], 0x80      ; the ground, unread
    jz .set
    mov ax, [di+F_X]
    mov bx, [di+F_Y]
    mov si, wa_lowf
    call wa_floor
.set:
    mov [di+F_Z], ax
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

%include "wasin.inc"
; wa_figtick - DI = a figure: one 30 Hz step of its patrol and its animation
wa_figtick:
    cmp word [di+F_FLASH], 0    ; (F_FLASH and F_DEAD, one word: the usual
    jne .flash                  ; tick has neither)
.live:
    cmp byte [di+F_ANIM], WA_A_FLINCH
    je .anim                    ; a flinch stops it in its tracks
    mov ax, [di+F_HEAD]         ; a leg's step is the same every tick of
    or ah, 0x80                 ; it: worked out once per heading
    cmp ax, [di+F_VH]
    je .stepped
    mov [di+F_VH], ax
    mov ax, [di+F_HEAD]
    call wa_sincos
    push dx
    mov cx, WA_SPEED
    imul cx                     ; DX:AX = sin x 8, Q14
    call .q14                   ; -> AX units
    mov [di+F_VY], ax
    pop ax
    imul cx
    call .q14
    mov [di+F_VX], ax
.stepped:
    mov ax, [di+F_VY]
    add [di+F_Y], ax
    mov ax, [di+F_VX]
    add [di+F_X], ax
    dec word [di+F_STEP]
    jnz .turn
    mov si, [di+F_PATH]         ; next leg: snap to its waypoint
    mov bx, [di+F_LEG]
    add bx, 8
    mov ax, bx
    shr ax, 1
    shr ax, 1
    shr ax, 1
    cmp ax, [si]
    jb .leg
    xor bx, bx
.leg:
    mov [di+F_LEG], bx
    add si, bx
    mov ax, [si+2]
    mov [di+F_X], ax
    mov ax, [si+4]
    mov [di+F_Y], ax
    mov ax, [si+6]
    and ax, 1023
    mov [di+F_HEAD], ax
    mov ax, [si+8]
    mov [di+F_STEP], ax
.turn:
    cmp byte [wa_aflat], 0      ; the floor it now stands on (none on a
    jne .flatz                  ; flat arena: F_Z stays 0)
    mov si, [di+F_PATH]         ; on a leg arenagen found on the ground all
    add si, [di+F_LEG]          ; the way, the ground - wa_figz's own test,
    test byte [si+7], 0x80      ; without its call: most ticks of most legs
    jnz .zread
    mov word [di+F_Z], 0
    jmp short .flatz
.zread:
    call wa_figz
.flatz:
    mov ax, [di+F_HEAD]         ; face the way it is going, 48 a tick at most
    sub ax, [di+F_ANG]
    jz .anim                    ; (it does, most ticks)
    and ax, 1023
    cmp ax, 512
    jb .ccw
    sub ax, 1024
    cmp ax, -48
    jge .set
    mov ax, -48
    jmp .set
.ccw:
    cmp ax, 48
    jle .set
    mov ax, 48
.set:
    add ax, [di+F_ANG]
    and ax, 1023
    mov [di+F_ANG], ax
.anim:
    inc word [di+F_PH]
    mov al, [di+F_NFR]
    xor ah, ah
    shl ax, 1
    shl ax, 1                   ; quarter keyframes in the cycle
    cmp [di+F_PH], ax
    jb .out
    cmp byte [di+F_LOOP], 0
    je .hold
    mov word [di+F_PH], 0
    ret
.hold:
    dec ax
    mov [di+F_PH], ax
    cmp byte [di+F_ANIM], WA_A_FLINCH
    jne .out
    jmp wa_runanim              ; the flinch is over: run again
.out:
    ret
.flash:
    cmp byte [di+F_FLASH], 0
    je .alive
    dec byte [di+F_FLASH]
.alive:
    cmp byte [di+F_DEAD], 0
    je .live
    dec byte [di+F_DEAD]
    jnz .anim
    jmp wa_spawn
.q14:                           ; DX:AX Q14 -> AX, rounding toward -inf
    shl ax, 1
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    mov ax, dx
    ret

; wa_fire - the pistol: hitscan through the crosshair, against the figures
; as the last frame drew them
wa_fire:
    mov byte [wa_mflash], 2
    mov ax, 1200
    mov cx, 1
    mov dl, 0x40
    call OSAPI_SND_TONE
    call wa_rframe              ; the figures as they stand (F_DEAD)...
%assign wa_i 0
%rep WA_NFIG
    cmp word [wa_figs + wa_i*F_SIZE + F_PZ], 0
    jne .drawn%[wa_i]           ; ...and one respawned since the last frame
    mov word [es:WA_RAT(wa_figs) + wa_i*F_SIZE + F_PZ], 0 ; was not drawn
.drawn%[wa_i]:                  ; where the part's projection says
%assign wa_i wa_i+1
%endrep
    mov bx, WRV_TRACE           ; the ray, in the renderer part: AX = the
    call wa_rcall               ; figure hit, or -1
    push ds
    pop es
    or ax, ax
    js .miss
    add ax, wa_figs
    mov di, ax
    inc word [wa_hits]
    mov byte [di+F_FLASH], 5
    dec byte [di+F_HP]
    jz .kill
    mov byte [di+F_ANIM], WA_A_FLINCH
    mov byte [di+F_NFR], WA_N_FLINCH
    mov byte [di+F_LOOP], 0
    mov word [di+F_PH], 0
    ret
.kill:
    inc word [wa_kills]
    mov byte [di+F_ANIM], WA_A_DEATH
    mov byte [di+F_NFR], WA_N_DEATH
    mov byte [di+F_LOOP], 0
    mov word [di+F_PH], 0
    mov byte [di+F_DEAD], 90    ; three seconds on the floor
.miss:
    ret

; --- the bench --------------------------------------------------------------
; B: 64 frames from the arena's middle, turning 1/64 of a circle each, the
; dummies frozen - the SAME work on every build and in either width, so two
; runs compare. The HUD then holds its averages until the next 16 frames.
WA_BENCHN equ 64
wa_bench:
    push word [wa_px]
    push word [wa_py]
    push word [wa_ang]
    push word [wa_pitch]
    push word [wa_eye]
    mov word [wa_px], 1024
    mov word [wa_py], 700
    mov word [wa_pitch], 0
    mov word [wa_eye], WA_EYE
    mov di, wa_figs             ; the dummies from their starts, frozen
    mov cx, WA_NFIG
.fig:
    call wa_spawn
    add di, F_SIZE
    loop .fig
    xor ax, ax
    mov [wa_trn], ax
    mov [wa_trn+2], ax
    mov [wa_tpr], ax
    mov [wa_tpr+2], ax
    mov [wa_ncells], ax
    mov [wa_ncells+2], ax
    mov [wa_bang], ax
    mov word [wa_nbench], WA_BENCHN
.frame:
    mov ax, [wa_bang]
    mov [wa_ang], ax
    add word [wa_bang], 65536 / WA_BENCHN
    call pit_now
    mov [wa_t0], ax
    mov [wa_t0+2], dx
    call wa_render
    call pit_now
    mov bx, ax
    mov cx, dx
    sub ax, [wa_t0]
    sbb dx, [wa_t0+2]
    add [wa_trn], ax
    adc [wa_trn+2], dx
    mov [wa_t0], bx
    mov [wa_t0+2], cx
    call wa_present
    call pit_now
    sub ax, [wa_t0]
    sbb dx, [wa_t0+2]
    add [wa_tpr], ax
    adc [wa_tpr+2], dx
    mov ax, [wa_nwr]
    add [wa_ncells], ax
    adc word [wa_ncells+2], 0
    dec word [wa_nbench]
    jnz .frame
    mov cx, 2                   ; 64 frames: quarter the sums, and the meter's
.q:                             ; divide-by-16 reads them as per-frame
    shr word [wa_trn+2], 1
    rcr word [wa_trn], 1
    shr word [wa_tpr+2], 1
    rcr word [wa_tpr], 1
    shr word [wa_ncells+2], 1
    rcr word [wa_ncells], 1
    loop .q
    mov ax, [wa_trn]            ; frame = render + present
    mov dx, [wa_trn+2]
    add ax, [wa_tpr]
    adc dx, [wa_tpr+2]
    mov [wa_tfr], ax
    mov [wa_tfr+2], dx
    pop word [wa_eye]
    pop word [wa_pitch]
    pop word [wa_ang]
    pop word [wa_py]
    pop word [wa_px]
    mov byte [wa_benched], 1
    ret

; --- the PLAY bench (P) --------------------------------------------------------
; What play costs, not what a spin costs (the owner, 2026-11-13: "the higher
; framerates of the benchmark come from spinning ... or from having the
; characters static"). A fixed pose in the full arena - mid-room, not in a
; corner - the dummies RUNNING their patrols from offsets chosen on the host so
; two or more are in view the whole time (tools-side search over the patrols:
; two or more at every sample of the run, three at a fifth of them), and the
; view moved in a moderate CIRCLE, yaw and pitch together, the way a hand
; circling the mouse moves it - driven by the sim's clock, so it moves at the
; same speed whatever the frame rate. 8 s; the HUD then holds the run's
; averages, marked P, until a key. It runs on any machine the game does: the
; 5150, 86Box, MartyPC alike.
WA_PB_X     equ 224
WA_PB_Y     equ 800
WA_PB_A     equ 32              ; a little north of east, across the room
WA_PBT      equ 240             ; ticks: 8 s
WA_PB_YAW   equ 17 * 64         ; the circle: +-6 degrees of yaw (ang16)...
WA_PB_PIT   equ 16              ; ...+-2 rows of pitch (quarter half-rows)
WA_PB_STEP  equ 23              ; ...once round every ~1.5 s (1024 / 45)
wa_pbstart:
    xor bx, bx                  ; the pose: P's own in arenas 0 and 1; in
    cmp byte [wa_arena], 2      ; the heights arena five in turn, A to E
    jb .pose                    ; (docs/plans/WIREARENA-HEIGHTS-PLAN.md 9)
    mov bl, [wa_pbsel]
    inc bx
    mov al, bl
    cmp al, WA_PBN
    jb .nsel
    xor al, al
.nsel:
    mov [wa_pbsel], al
.pose:
    mov ax, WA_PBSZ
    mul bx
    mov si, ax
    add si, wa_pbposes
    lodsw
    mov [wa_px], ax
    lodsw
    mov [wa_py], ax
    lodsw
    mov [wa_pba], ax
    mov [wa_ang], ax
    lodsw
    mov [wa_pbp], ax
    lodsw
    mov [wa_feet], ax
    lodsw
    mov [wa_pbm], al
    xor ax, ax
    mov [wa_pxf], ax
    mov [wa_pyf], ax
    mov [wa_jz], ax
    mov [wa_jv], ax
    mov [wa_pitch], ax
    mov [wa_pbtk], ax
    mov word [wa_fpx], -1       ; (the floor: read afresh)
    mov [wa_pbfr], ax
    mov ax, WA_EYE
    add ax, [wa_feet]
    mov [wa_eye], ax
    mov di, wa_figs             ; the dummies from their starts, then on to
    mov si, wa_pbph             ; the bench's points along their patrols
    mov cx, WA_NFIG
.fig:
    push cx
    call wa_spawn
    lodsw
    mov cx, ax
    jcxz .placed
.walk:
    push cx
    push si
    call wa_figtick
    pop si
    pop cx
    loop .walk
.placed:
    pop cx
    add di, F_SIZE
    loop .fig
    xor ax, ax                  ; the sums, from here
    mov [wa_tfr], ax
    mov [wa_tfr+2], ax
    mov [wa_trn], ax
    mov [wa_trn+2], ax
    mov [wa_tpr], ax
    mov [wa_tpr+2], ax
    mov [wa_ncells], ax
    mov [wa_ncells+2], ax
    mov [wa_acc], ax            ; and no sim debt carried in
    mov [wa_acc+2], ax
    mov byte [wa_hold], 0
    mov byte [wa_pbon], 1
    mov si, wa_hudtpl           ; the HUD's numbers cleared while it runs,
    call wa_hudfix              ; so the screen shows only the run's result
    mov al, [wa_pbm]
    mov di, 32
    call wa_putc
    ret
wa_pbph:    dw 160, 64, 80      ; ticks along each patrol (the host search)
; the benches' poses: x, y, angle (ang16), pitch, the floor under the eye,
; the HUD's mark. P's own, then the heights arena's (HEIGHTS-PLAN 9): A the
; busiest floor view, B the open floor, C on the platform, D on the tower
; looking down, E in the annex's north hallway looking west (HEIGHTS-PLAN
; 7.4: the revised arena)
WA_PBSZ     equ 12
WA_PBN      equ 5
wa_pbposes: dw WA_PB_X, WA_PB_Y, WA_PB_A << 6, 0, 0, 'P'
            dw 800, 400, 160 << 6, 0, 0, 'A'
            dw 1600, 1024, 512 << 6, 0, 0, 'B'
            dw 1248, 1024, 512 << 6, 0, 80, 'C'
            dw 1952, 1024, 512 << 6, -40, 160, 'D'
            dw 600, 1568, 512 << 6, 0, 0, 'E'

; wa_pbview - the circle: yaw and pitch at the play bench's clock
wa_pbview:
    mov ax, [wa_pbtk]
    mov cx, WA_PB_STEP
    mul cx
    call wa_sincos              ; AX = sin, DX = cos (Q14)
    push ax
    mov ax, dx
    mov cx, WA_PB_YAW
    imul cx
    shl ax, 1
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    add dx, [wa_pba]
    mov [wa_ang], dx
    pop ax
    mov cx, WA_PB_PIT
    imul cx
    shl ax, 1
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    add dx, [wa_pbp]
    mov [wa_pitch], dx
    ret

; wa_pbmeter - each frame of the play bench: sum it; at its end, the averages
; over every frame of the run into the HUD, marked P, and the meter held
wa_pbmeter:
    mov ax, [wa_nwr]
    add [wa_ncells], ax
    adc word [wa_ncells+2], 0
    inc word [wa_pbfr]
    cmp word [wa_pbtk], WA_PBT
    jae .done
    ret
.done:
    mov byte [wa_pbon], 0
    mov cx, [wa_pbfr]
    mov si, wa_tfr
    call wa_avgn                ; AX = ms x 10 a frame
    push ax
    mov bx, ax
    mov ax, 0x86A0              ; 100,000 / ms10 = fps x 10
    mov dx, 1
    cmp bx, 2
    jae .div
    mov bx, 2
.div:
    div bx
    mov di, 4
    call wa_put10
    pop ax
    mov di, 12
    call wa_put10
    mov cx, [wa_pbfr]
    mov si, wa_trn
    call wa_avgn
    mov di, 19
    call wa_put10
    mov cx, [wa_pbfr]
    mov si, wa_tpr
    call wa_avgn
    mov di, 26
    call wa_put10
    mov ax, [wa_ncells]
    mov dx, [wa_ncells+2]
    div word [wa_pbfr]
    mov di, 33
    mov cx, 3
    call wa_putn
    mov al, [wa_pbm]
    mov di, 32
    call wa_putc
    mov byte [wa_hold], 1
    xor ax, ax
    mov [wa_nfr], ax
    ret

; wa_avgn - SI -> a 32-bit sum of 838 ns counts, CX = frames: AX = the
; average a frame in tenths of a ms (sum x 549 / 65536 / frames, 32-bit)
wa_avgn:
    mov ax, [si]
    mov bx, 549
    mul bx
    push dx
    mov ax, [si+2]
    mul bx
    pop bx
    add ax, bx
    adc dx, 0
    div cx
    ret

; --- the meter ------------------------------------------------------------
; Every 16 frames: average frame, render and present times, and cells
; written, into the HUD row.
wa_meter:
    cmp byte [wa_pbon], 0
    je .norm
    jmp wa_pbmeter
.norm:
    mov ax, [wa_nwr]            ; video writes this frame
    add [wa_ncells], ax
    adc word [wa_ncells+2], 0
    cmp byte [wa_benched], 0
    je .count
    mov byte [wa_benched], 0
    mov byte [wa_benchm], 1
    mov byte [wa_hold], 1       ; and keep them there until a key moves on
    jmp .show                   ; the bench's sums, as they stand
.count:
    cmp byte [wa_hold], 0
    je .live
    ret
.live:
    inc word [wa_nfr]
    cmp word [wa_nfr], 16
    jae .show
    ret
.show:
    mov si, wa_tfr
    call wa_avg_ms10            ; AX = ms x 10
    push ax
    mov bx, ax
    mov ax, 0x86A0              ; 100,000 / ms10 = fps x 10
    mov dx, 1
    or bx, bx
    jz .z
    cmp bx, 2
    jae .div
.z:
    mov bx, 2
.div:
    div bx
    mov di, 4
    call wa_put10
    pop ax
    mov di, 12
    call wa_put10
    mov si, wa_trn
    call wa_avg_ms10
    mov di, 19
    call wa_put10
    mov si, wa_tpr
    call wa_avg_ms10
    mov di, 26
    call wa_put10
    mov ax, [wa_ncells]         ; cells a frame, the average
    mov dx, [wa_ncells+2]
    mov cx, 16
    div cx
    mov di, 33
    mov cx, 3
    call wa_putn
    xor ax, ax
    mov [wa_nfr], ax
    mov [wa_tfr], ax
    mov [wa_tfr+2], ax
    mov [wa_trn], ax
    mov [wa_trn+2], ax
    mov [wa_tpr], ax
    mov [wa_tpr+2], ax
    mov [wa_ncells], ax
    mov [wa_ncells+2], ax
    mov bl, [wa_fov]            ; the field of view: 9, 7 or 6 (tens)
    xor bh, bh
    mov al, [wa_fovc+bx]
    mov di, 36
    call wa_putc
    mov al, [wa_level]          ; the detail level, 1..5
    add al, '1'
    call wa_putc
    mov al, 'F'                 ; the detail level
    cmp byte [wa_sparse], 0
    je .det
    mov al, 'S'
.det:
    call wa_putc
    mov al, '-'                 ; G: the floor grid
    cmp byte [wa_grid], 0
    je .g
    mov al, 'G'
.g:
    call wa_putc
    mov al, 'N'                 ; B: these are the bench's figures
    cmp byte [wa_benchm], 0
    je .bm
    mov al, 'B'
.bm:
    mov byte [wa_benchm], 0
    mov di, 32
    call wa_putc
    ret

; wa_avg_ms10 - SI -> a 32-bit sum of 838 ns counts over 16 frames: AX =
; the average in tenths of a millisecond (counts x 549 / 65536, in 32 bits:
; a frame of a whole second still reads true)
wa_avg_ms10:
    mov ax, [si]
    mov dx, [si+2]
    mov cx, 4
.sh:
    shr dx, 1
    rcr ax, 1
    loop .sh
    mov cx, 549
    push dx
    mul cx                      ; low word x 549: its high word carries
    mov bx, dx
    pop ax
    mul cx                      ; high word x 549: whole tenths x 65536
    add ax, bx
    ret

; wa_put10 - AX = a value in tenths, as "NNN.N" at HUD column DI (5 cells)
wa_put10:
    push ax
    xor dx, dx
    mov cx, 10
    div cx                      ; AX = whole, DX = tenth
    push dx
    mov cx, 3
    call wa_putn
    mov al, '.'
    call wa_putc
    pop ax
    add al, '0'
    call wa_putc
    pop ax
    ret

; wa_putn - AX as CX right-aligned digits at HUD column DI; DI moves on
wa_putn:
    push bx
    add di, cx
    push di
    mov bx, 10
.d:
    dec di
    xor dx, dx
    div bx
    push ax
    push di
    mov al, dl
    add al, '0'
    call wa_putc
    pop di
    pop ax
    loop .d
    pop di
    pop bx
    ret

; wa_putc - AL at HUD column DI (row 24); DI moves on. Off the 40-column
; screen it is dropped.
wa_putc:
    cmp di, [wa_w]
    jae .skip
    push es
    push di
    push ax
    mov es, [wa_vseg]
    mov ax, [wa_rowoff+WA_ROWS*2]
    add di, ax
    shl di, 1
    pop ax
    push ax
    mov ah, 0x07
    stosw
    pop ax
    pop di
    pop es
.skip:
    inc di
    ret

wa_hudfix:                      ; SI = the HUD's template, NUL-terminated
    xor di, di
.c:
    lodsb
    or al, al
    jz .out
    call wa_putc
    jmp .c
.out:
    ret

; --- the renderer part (docs/plans/WIREARENA-PARTS-PLAN.md section 7) --------
; The renderer is part 0 of this file, apps/wirearena/wrpart.asm: its own
; segment, its own data, entered by far call with DS = that data. The names
; this file always called it by - wa_render, wa_present, wa_geominit,
; wa_loadarena - are the glue below, so the loop and the benches read as they
; did. What the renderer reads is copied into its FRAME BLOCK
; (apps/wirearena/wafb.inc) at a fixed offset, WR_FB; WA_RAT names a frame
; block variable's address there.

; wa_rbind - at entry, once op_load has the carve: bank the part's data
; segment and code selector and its verbs' offsets, after checking its header
; is the one this primary was built with. CF = 1 refused, with a toast.
wa_rbind:
    xor al, al
    call op_seg
    or ax, ax
    jz .bad
    mov es, ax
    cmp word [es:0], 'WR'
    jne .bad
    cmp word [es:2], 'PA'
    jne .bad
    cmp word [es:4], 'RT'
    jne .bad
    cmp word [es:WR_H_ABI], WR_ABI | (WR_NVERB << 8)
    jne .bad
    mov [wa_rds], ax
    xor bx, bx
.v:
    mov ax, [es:WR_H_VERB+bx]
    mov [wa_rverb+bx], ax
    inc bx
    inc bx
    cmp bx, WR_NVERB*2
    jb .v
    xor al, al
    call op_cseg
    mov [wa_rcs], ax
    push ds
    pop es
    clc
    ret
.bad:
    push ds
    pop es
    mov si, wa_t_part
    xor cx, cx
    call OSAPI_TOAST
    stc
    ret

; wa_partsmv - the parts standard's hook (OP_ONMOVE, SPEC.md 20.12.12): the
; carve moved, op_seg is right again, and the two words wa_rbind banked are
; asked for anew. Safe because the renderer part calls no kernel slot: no
; claim - so no move - happens while this task stands in it. A relocation
; proc: registers are the kernel's to restore
wa_partsmv:
    xor al, al
    call op_seg
    mov [wa_rds], ax
    xor al, al
    call op_cseg
    mov [wa_rcs], ax
    ret

; wa_rcall - BX = a verb (WRV_*): far-call it in the renderer part, DS = its
; data for the call. AX..DI and BP as the verb takes them; out its AX and
; flags, everything else the verb's to clobber, ES included. Built as
; push/push/RETF so no vector is read after DS has moved (apps/xtmp3/
; x3pars.inc's x3p_fcall)
wa_rcall:
    ; STKBALANCE-OK: a far CALL built by hand - the return (CS:wa_rret) and
    ; the target are pushed and RETF enters the part, whose own RETF comes
    ; back to wa_rret, which pops the DS pushed before them
    push ds
    push cs
    push word [wa_rretv]
    push word [wa_rcs]
    push word [wa_rverb+bx]
    mov ds, [wa_rds]
    retf
wa_rret:
    ; STKBALANCE-OK: the far return of wa_rcall's verb lands here, one push
    ; deep, and this pops it
    pop ds
    ret
wa_rretv:   dw wa_rret

; wa_rsync - the CONFIG section into the renderer part (after a mode set, a
; field-of-view change). Keeps every register but the flags.
; THE DETAIL LEVELS (docs/plans/WIREARENA-HEIGHTS-PLAN.md 9.10): per level,
; Very Low to Very High, the options it turns on - wa_look's LK_ bits (RAMP2
; apart: its own key), then the floor grid (G) and the stepped treads (T),
; which their keys still override until the next level is chosen. Moving
; an option between levels is a change to this table and nothing else.
WA_NLEV equ 5
wa_levtab:
    db LK_FEW|LK_ROUND|LK_COARSE|LK_NOPOST|LK_ROOMF|LK_FARTOP, 0, 0 ; 1 Very Low
    db LK_FEW|LK_ROUND|LK_COARSE|LK_NOPOST, 0, 0                    ; 2 Low
    db LK_FEW|LK_ROUND|LK_COARSE, 0, 0                              ; 3 Medium
    db LK_FEW|LK_ROUND|LK_COARSE, 1, 0                              ; 4 High
    db 0, 1, 1                                                      ; 5 Very High

; wa_setlevel - AL = a level, 0..WA_NLEV-1: its options into the frame
; block (wa_look keeps RAMP2, its own key's). Clobbers AX, BX
wa_setlevel:
    mov [wa_level], al
    mov bl, 3
    mul bl
    xchg ax, bx
    mov al, [wa_look]
    and al, LK_RAMP2
    or al, [wa_levtab+bx]
    mov [wa_look], al
    mov al, [wa_levtab+bx+1]
    mov [wa_grid], al
    mov al, [wa_levtab+bx+2]
    mov [wa_treads], al
    ret

wa_rsync:
    push cx
    push si
    push di
    push es
    mov es, [wa_rds]
    mov si, wa_fb_cfg
    mov di, WA_RAT(wa_fb_cfg)
    mov cx, (wa_fb_frm - wa_fb_cfg) / 2
    cld
    rep movsw
    pop es
    pop di
    pop si
    pop cx
    ret

; wa_rframe - the FRAME section and the head of each figure record (bytes
; 0..19: where it is, which way it faces, its animation, its flash, whether
; it is dead, the floor it stands on) into the renderer part: three runs, the first taking FRAME and
; figure 0 together - FRAME's camera sin and cos made here first. Clobbers
; CX, SI, DI, ES (= the part)
WA_FHW equ WA_FIGHEAD/2
wa_rframe:
    push ax
    push dx
    mov ax, [wa_ang]            ; the camera's sin and cos (the part has no
    mov cl, 6                   ; table): wa_ang's 1024-step angle, as the
    shr ax, cl                  ; renderer's wa_cang
    call wa_sincos
    mov [wa_fsn], ax
    mov [wa_fcs], dx
    pop dx
    pop ax
    mov es, [wa_rds]
    cld
    mov si, wa_fb_frm
    mov di, WA_RAT(wa_fb_frm)
    mov cx, (wa_figs - wa_fb_frm) / 2 + WA_FHW
    rep movsw
%assign wa_i 1
%rep WA_NFIG-1
    mov si, wa_figs + wa_i*F_SIZE
    mov di, WA_RAT(wa_figs) + wa_i*F_SIZE
    mov cx, WA_FHW
    rep movsw
%assign wa_i wa_i+1
%endrep
    mov si, [wa_lift]           ; the lift's height, which the sim moves
    or si, si                   ; (HEIGHTS-PLAN 3.2: ARENA's one word that
    js .nolift                  ; goes G -> R)
    mov cx, [wa_bxh+si]
    mov [es:WA_RAT(wa_bxh)+si], cx
.nolift:
    ret

; wa_render - a frame: the frame state into the part, the renderer, and back
; its frame number (the sim's key poll, wa_tick). Each figure's F_PZ here
; then says only "drawn since it last spawned" (wa_spawn zeroes it): the
; projection itself stays in the part, where TRACE reads it. ES = DS out, as
; the renderer left it.
wa_render:
    call wa_rframe
    mov bx, WRV_RENDER
    call wa_rcall
    mov [wa_frame], al
    push ds
    pop es
%assign wa_i 0
%rep WA_NFIG
    mov word [wa_figs + wa_i*F_SIZE + F_PZ], 1
%assign wa_i wa_i+1
%endrep
    ret

; wa_present - the changed cells onto the glass, and how many (the meter)
wa_present:
    mov bx, WRV_PRESENT
    call wa_rcall
    mov [wa_nwr], ax
    push ds
    pop es
    ret

; wa_geominit - once an arena is loaded: the reciprocal table and the
; coordinate steps, in the part
wa_geominit:
    mov bx, WRV_GEOM
    call wa_rcall
    push ds
    pop es
    ret

; wa_loadarena - arena [wa_arena], a part of its own (WIREARENA-PARTS-PLAN
; 7.5): fetched, read into the renderer part's working tables (ARENA), its
; ARENA section - the boxes the collision walks, the start wa_reset takes -
; copied back into ours, and dropped again: both halves keep what they need,
; so no claim outlives the call. CF = 1: it could not be had, and the parts
; standard's toast has said why. UI task (a menu command): op_fetch's rule.
WA_PARTA equ 1                  ; arena 0's row; the renderer is row 0
wa_loadarena:
    mov al, [wa_arena]
    add al, WA_PARTA
    push ax
    call op_fetch
    pop ax
    jc .out
    push ax
    call op_seg
    mov dx, ax
    mov bx, WRV_ARENA
    call wa_rcall
    push ds
    push ds
    pop es
    mov si, WA_RAT(wa_fb_arn)
    mov di, wa_fb_arn
    mov cx, (wa_fb_end - wa_fb_arn) / 2
    mov ds, [wa_rds]
    cld
    rep movsw
    pop ds
    mov ax, [wa_nbox]
    mov cl, 3
    shl ax, cl
    mov [wa_nbox8], ax
    call wa_lists               ; the boxes the floor and the walls read
    mov word [wa_pptr], wa_pathtab ; the patrols: the arena's own, if its
    cmp word [wa_apn], 0        ; part carries them (HEIGHTS-PLAN 7.4.5) -
    je .own                     ; their offsets in the block made addresses
    mov word [wa_pptr], wa_aptab
    xor bx, bx
.ap:
    mov ax, [wa_apath+bx]
    add ax, wa_apath
    mov [wa_aptab+bx], ax
    inc bx
    inc bx
    cmp bx, WA_NFIG*2
    jb .ap
.own:
    pop ax
    call op_drop
    clc
.out:
    ret

%include "os88pit.inc"

; --- tables -----------------------------------------------------------------
%define WA_TAB_SIN               ; the tables this half reads (the renderer
%define WA_TAB_PATHS             ; part takes the arenas and the keyframes)
%include "watab.inc"

wa_tpl:
    dw 120, 80, 330, 150
    dw wa_ttl, wa_cls
    OS88_CLASS wa_cls, 0, PAINT, wa_paint

    OS88_MENUSET wa_menus, wa_name, wa_oncmd
        OS88_MENU wa_m_game, wa_i_game, 6
    OS88_MENUSET_END wa_menus

wa_name:
wa_ttl:     db 'WireArena', 0
wa_m_game:  db 'Game', 0
wa_i_game:  dw wa_it_40, wa_it_80, wa_it_o40, wa_it_o80, wa_it_h40, wa_it_h80
wa_it_40:   db 'Play, 40 columns', 0
wa_it_80:   db 'Play, 80 columns', 0
wa_it_o40:  db 'Open arena, 40 columns', 0
wa_it_o80:  db 'Open arena, 80 columns', 0
wa_it_h40:  db 'Heights arena, 40 columns', 0
wa_it_h80:  db 'Heights arena, 80 columns', 0
wa_items:   db 1, 0, 0, 0, 1, 1, 0, 1, 1, 2, 0, 2  ; width (0 = 80, 1 = 40), arena

wa_help:
    db 'WireArena - renderer prototype', 0
    db 'Game menu: 40 or 80 columns; the full', 0
    db 'arena, or the open one (pillars only).', 0
    db 'Mouse looks; W A S D move; arrows', 0
    db 'turn and pitch; Space jumps; click', 0
    db 'or Ctrl fires; Tab: 80/40; V: vsync;', 0
    db 'B: bench. P: play bench (8 s). F: view', 0
    db '90/75/60. 1-5: detail, very low to', 0
    db 'very high (HUD). G: floor grid. T:', 0
    db 'ramps as treads. R: ramps as two sides.', 0
    db 'L: no wall tops (debug). Esc leaves.', 0
    db 'HUD: fps, frame, render, present ms,', 0
    db 'video writes a frame.', 0
    db 0

;               0         1         2         3
;               0123456789012345678901234567890123456789
wa_hudtpl:  db 'FPS       MS      R      P      N       ', 0

TOASTSTR wa_t_small, 'Needs kern_big or mega'
TOASTSTR wa_t_part, 'Renderer part mismatch'

; --- the parts (SPEC.md 20.12.3): the renderer, with its BSS as zeros
; neither stored nor decoded (OP_ZFILL, 20.12.7.5), and an arena a row, read
; when a match starts and dropped again (wa_loadarena)
    OS88_PARTS_BEGIN 1 + WA_NARENA
      OS88_PART OP_SEG, OP_COMP | OP_ZFILL  ; 0 build/wrpart.bin
%rep WA_NARENA
      OS88_PART OP_ASSET, OP_LAZY | OP_COMP ; 1.. build/waa<n>.bin
%endrep
    OS88_PARTS_END

; --- bss ------------------------------------------------------------------
; The parts standard's words first (OP_BSS, apps/os88parts.inc), then the
; FRAME BLOCK in wafb.inc's order (the renderer part holds the same layout at
; WR_FB), then this half's own.
%assign WA_BSS 0
%macro WA_VAR 2
%1 equ os88_image_end+OP_BSS+WA_BSS
%assign WA_BSS WA_BSS+%2
%endmacro
%macro WA_FBV 2
WA_VAR %1,%2
%endmacro
WA_FBLOCK
WA_VAR wa_win,2
WA_VAR wa_rds,2                  ; the renderer part: its data segment,
WA_VAR wa_rcs,2                  ;   its code selector (op_cseg)
WA_VAR wa_rverb,WR_NVERB*2       ;   and its verbs' offsets (wa_rbind)
WA_VAR wa_nwr,2                  ; video writes the last present made
WA_VAR wa_fsi,FSI_SIZE
WA_VAR wa_mode,1
WA_VAR wa_want,1
WA_VAR wa_quit,1
WA_VAR wa_vsync,1
WA_VAR wa_level,1                ; the detail level, 0..WA_NLEV-1 (keys 1..5)
WA_VAR wa_arena,1
WA_VAR wa_feet,2                 ; the floor under the player (HEIGHTS-PLAN
                                 ; 3.1): on the ground the feet, in the air
                                 ; the base wa_jz is above
WA_VAR wa_flr,2                  ; the floor under the player this tick,
WA_VAR wa_flrb,2                 ;   and its box's record (-1 the ground),
WA_VAR wa_fpx,2                  ;   read where the player stood (-1:
WA_VAR wa_fpy,2                  ;   read again)
WA_VAR wa_qx,2                   ; wa_floor's square: its middle and r
WA_VAR wa_qy,2
WA_VAR wa_qr,2
WA_VAR wa_nbox8,2                ; the boxes x 8 (wa_lists)
WA_VAR wa_lon,2                  ; the lift: ticks someone has stood on it,
WA_VAR wa_loff,2                 ;   ticks it has stood empty
WA_VAR wa_allp,4+WA_MBOX*WA_LTE  ; wa_floor's box tables (wa_lists): every
WA_VAR wa_lowp,4+WA_MBOX*WA_LTE  ;   box and the low ones for the player,
WA_VAR wa_lowf,4+WA_MBOX*WA_LTE  ;   the low ones for a dummy's feet
WA_VAR wa_pptr,2                 ; -> the patrols' table: wa_pathtab, or
WA_VAR wa_aptab,WA_NFIG*2        ;   this, the arena's own (wa_loadarena)
WA_VAR wa_pbsel,1                ; the play bench: the heights arena's pose,
WA_VAR wa_pba,2                  ;   the angle and pitch it circles round,
WA_VAR wa_pbp,2                  ;   and its HUD mark
WA_VAR wa_pbm,1
WA_VAR wa_trig,1
WA_VAR wa_frame,1                ; the renderer's, after each frame (wa_tick)
WA_VAR wa_pxf,2
WA_VAR wa_pyf,2
WA_VAR wa_jz,2
WA_VAR wa_jv,2
WA_VAR wa_s13,2
WA_VAR wa_c13,2
WA_VAR wa_hits,2
WA_VAR wa_kills,2
WA_VAR wa_tmp,2
WA_VAR wa_last,4
WA_VAR wa_acc,4
WA_VAR wa_t0,4
WA_VAR wa_tfr,4
WA_VAR wa_trn,4
WA_VAR wa_tpr,4
WA_VAR wa_ncells,4
WA_VAR wa_nfr,2
WA_VAR wa_bang,2
WA_VAR wa_nbench,2
WA_VAR wa_benched,1
WA_VAR wa_benchm,1
WA_VAR wa_pbon,1
WA_VAR wa_pbtk,2
WA_VAR wa_pbfr,2
WA_VAR wa_hold,1
WA_VAR wa_rowoff,(WA_ROWS+1)*2
WA_VAR wa_kbits,2                ; the held keys this frame (wa_keys)
WA_VAR wa_kfr,1                  ; ...polled in this frame
WA_VAR wa_kmap,KEYMAP_BYTES      ; ...and the whole map they came from
    OS88_BSS OP_BSS+WA_BSS
    OS88_IMAGE_END
