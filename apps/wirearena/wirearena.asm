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
    OS88_HEADER 'WARENA', wa_entry, 0, OS88_HIGH | OS88_HIGHMEM

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
WA_BLANK    equ 0x0720

; per-figure record
F_X     equ 0
F_Y     equ 2
F_ANG   equ 4                   ; facing, 0..1023
F_LEG   equ 6                   ; leg index * 8 (byte offset into the path)
F_STEP  equ 8                   ; steps left on this leg
F_HP    equ 10                  ; byte
F_ANIM  equ 11                  ; byte: first keyframe of the animation
F_NFR   equ 12                  ; byte: its keyframe count
F_LOOP  equ 13                  ; byte: 1 loops, 0 holds the last frame
F_PH    equ 14                  ; word: phase, quarter keyframes
F_FLASH equ 16                  ; byte: hit-flash frames left
F_DEAD  equ 17                  ; byte: ticks until respawn, 0 = alive
F_HEAD  equ 18                  ; heading of the current leg
F_PATH  equ 20                  ; -> its path
F_PZ    equ 22                  ; last projection: z (0 = not drawn)
F_PIZ   equ 24                  ;   inverse depth
F_PCX   equ 26                  ;   centre, sub-columns
F_PTOP  equ 28                  ;   head, half-rows
F_PBOT  equ 30                  ;   feet, half-rows
F_PWH   equ 32                  ;   half width, sub-columns
F_VH    equ 34                  ; the heading F_VX/F_VY are for, | 0x8000
F_VX    equ 36                  ;   (0: none yet): a tick's step, units
F_VY    equ 38
F_SIZE  equ 40

wa_entry:
    mov byte [wa_fov], 1        ; 75 degrees: the owner's pick of the three
    call OSAPI_CPU_INFO         ; the floor grid costs a 4.77 MHz 8088 ~13 ms
    cmp al, CPU_8086            ; a frame: on by default on a 286 or better,
    je .nogrid                  ; off on the target machine (G either way)
    mov byte [wa_grid], 1
.nogrid:
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
    mov ax, wa_main
    mov bx, [wa_win]
    xor cx, cx
    call OSAPI_FSX_RUN
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
    mov al, [wa_arena]
    call wa_loadarena
    call wa_geominit
    call wa_reset
    call OSAPI_MOUSE_REL        ; the desktop's motion is not ours: discard
    call pit_now
    mov [wa_last], ax
    mov [wa_last+2], dx
    xor ax, ax
    mov [wa_acc], ax
    mov [wa_acc+2], ax
.loop:
    call pit_now
    mov bx, ax
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
    sub ax, [wa_t0]
    sbb dx, [wa_t0+2]
    add [wa_tpr], ax
    adc [wa_tpr+2], dx
    call wa_meter
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
    xor bx, bx                  ; row offsets, in cells
    mov si, wa_rowoff
    mov di, wa_hroff
    mov cx, WA_ROWS + 1
.rows:
    mov [si], bx                ; cells (the HUD's)...
    mov ax, bx
    shl ax, 1                   ; ...and cell OFFSETS, which is what the
    mov [si+wa_rowo2-wa_rowoff], ax ; renderer indexes everything by
    cmp cx, 1
    je .last                    ; (the HUD row has no half-rows)
    mov [di], ax
    mov [di+2], ax
    add di, 4
.last:
    add bx, [wa_w]
    inc si
    inc si
    loop .rows
    push ds
    pop es
    mov di, wa_vis              ; nothing of ours on the glass yet
    mov ax, WA_BLANK
    mov cx, WA_CELLS
    rep stosw
    mov di, wa_stamp
    xor ax, ax
    mov cx, WA_CELLS
    rep stosw
    mov di, wa_vst              ; the frame number restarts: so does the
    mov cx, WA_MVTX             ; vertex cache, or an old stamp could match
    rep stosw
    mov [wa_frame], al
    mov [wa_newn], ax
    mov [wa_oldn], ax
    mov word [wa_newp], wa_lista
    mov word [wa_oldp], wa_listb
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

; wa_loadarena - AL = an arena: its coordinate tables, vertices, corner rows
; and boxes into the working tables (the renderer and the collision read
; those), its counts, its tree's root and its start. The tree is walked
; where it was assembled.
wa_loadarena:
    mov ah, WA_ARENASZ
    mul ah
    add ax, wa_arenas
    mov bx, ax
    push ds
    pop es
    mov si, [bx]                ; x values
    mov cx, [bx+2]
    mov ax, cx
    shl ax, 1
    mov [wa_nxv2], ax
    mov di, wa_xv
    rep movsw
    mov si, [bx+4]              ; y values
    mov cx, [bx+6]
    mov ax, cx
    shl ax, 1
    mov [wa_nyv2], ax
    mov di, wa_yv
    rep movsw
    mov si, [bx+8]              ; vertices, two bytes each
    mov cx, [bx+10]
    mov di, wa_vtx
    rep movsw
    mov cx, [bx+16]             ; boxes
    mov [wa_nbox], cx
    mov si, [bx+12]             ; corner rows, the room's and one a box
    inc cx
    shl cx, 1
    mov di, wa_corn
    rep movsw
    mov si, [bx+14]
    mov cx, [bx+16]
    shl cx, 1
    shl cx, 1
    mov di, wa_boxes
    rep movsw
    mov ax, [bx+18]
    mov [wa_root], ax
    mov ax, [bx+20]
    mov [wa_sx], ax
    mov ax, [bx+22]
    mov [wa_sy], ax
    mov ax, [bx+24]
    mov [wa_sa], ax
    mov si, [bx+26]             ; the boxes' colours, the room's first
    mov cx, [wa_nbox]
    inc cx
    mov di, wa_bcol
    rep movsb
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
    ret
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
    mov word [wa_eye], WA_EYE
    mov di, wa_figs
    xor bx, bx
.fig:
    mov si, [wa_pathtab+bx]
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
    mov [di+F_HEAD], ax
    mov [di+F_ANG], ax
    mov ax, [si+8]
    mov [di+F_STEP], ax
    mov word [di+F_LEG], 0
    mov byte [di+F_HP], 3
    mov byte [di+F_DEAD], 0
    mov byte [di+F_FLASH], 0
    mov word [di+F_PZ], 0
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
wa_key:                         ; AL = scancode -> CF = 1 held
    call OSAPI_KEY_DOWN
    ret

; once a frame: typed keys, mouse look, the trigger
wa_frame_input:
.drain:
    mov bx, [wa_kqi]            ; what a tick took out of the BIOS buffer
    cmp bx, [wa_kqn]            ; first (wa_keys), then the buffer
    jb .queued
    xor bx, bx
    mov [wa_kqi], bx
    mov [wa_kqn], bx
    mov ah, 1
    int 16h
    jz .typed
    xor ah, ah
    int 16h
    call wa_kmark
    jmp .got
.queued:
    mov ax, [wa_kq+bx]
    inc bx
    inc bx
    mov [wa_kqi], bx
.got:
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
    jne .bh
    inc byte [wa_fov]
    cmp byte [wa_fov], 3
    jb .fov
    mov byte [wa_fov], 0
.fov:
    call wa_setfov
    jmp .drain
.bh:
    cmp ah, 0x23                ; H: hold far edges (EDGE)
    jne .bg
    xor byte [wa_hyst], 1
    jmp .drain
.bg:
    cmp ah, 0x22                ; G: the floor grid
    jne .bl
    xor byte [wa_grid], 1
    jmp .drain
.bl:
    cmp ah, 0x26                ; L: the wall detail level, full or sparse
    jne .bb
    xor byte [wa_sparse], 1
    jmp .drain
.bb:
    cmp ah, 0x30                ; B: the bench
    jne .bp
    call wa_bench
    jmp .drain
.bp:
    cmp ah, 0x19                ; P: the PLAY bench
    jne .drain
    call wa_pbstart
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
.clamp:
    cmp word [wa_pitch], 80
    jle .lo
    mov word [wa_pitch], 80
.lo:
    cmp word [wa_pitch], -80
    jge .fire
    mov word [wa_pitch], -80
.fire:
    mov al, 0x1D                ; Ctrl is a trigger too
    call wa_key
    jnc .btn
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
; poll. And not every key every frame: an OSAPI_KEY_DOWN is ~550 clk, so
; nine were ~1 ms of each frame. A key is asked about when it is WATCHED -
; it read down at the last poll, or its keystroke reached the BIOS buffer
; (wa_kmark: a press enqueues one at once, so a press is seen the frame it
; lands, as before) - and every key on every fourth frame (WA_KSWEEP),
; which catches a press the BIOS does not enqueue (Ctrl or Alt with an
; arrow) within three frames. A release is seen the next frame, as before.
WA_K_LEFT   equ 1
WA_K_RIGHT  equ 2
WA_K_UP     equ 4
WA_K_DOWN   equ 8
WA_K_W      equ 16
WA_K_S      equ 32
WA_K_A      equ 64
WA_K_D      equ 128
WA_K_SPACE  equ 256
wa_ktab:    db KSC_LEFT, KSC_RIGHT, KSC_UP, KSC_DOWN, 0x11, 0x1F, 0x1E, 0x20
            db KSC_SPACE
WA_NKEYS    equ 9
WA_KSWEEP   equ 4                ; every key, every this many frames
WA_KQ       equ 16               ; typed keys a tick can hold for the frame

; wa_keys - the held keys into [wa_kbits] (WA_K_*). Keeps all but the flags.
; The BIOS buffer is drained first, into wa_kq, which wa_frame_input reads
; before the buffer - the same keystrokes in the same order, only taken out
; earlier, so a press marks its key before the poll.
wa_keys:
    push ax
    push bx
    push cx
    push dx
    push si
.q:
    mov bx, [wa_kqn]
    cmp bx, WA_KQ*2
    jae .poll                   ; (full: the rest wait in the BIOS's)
    mov ah, 1
    int 16h
    jz .poll
    xor ah, ah
    int 16h
    mov [wa_kq+bx], ax
    inc bx
    inc bx
    mov [wa_kqn], bx
    call wa_kmark
    jmp .q
.poll:
    mov dx, [wa_kwatch]
    dec byte [wa_ksw]
    jns .some
    mov byte [wa_ksw], WA_KSWEEP-1
    mov dx, (1 << WA_NKEYS) - 1 ; the sweep: all of them
.some:
    mov si, wa_ktab
    xor bx, bx
    mov cx, WA_NKEYS
.k:
    lodsb
    shr dx, 1
    jnc .up                     ; not watched: up (CF = 0)
    call OSAPI_KEY_DOWN         ; CF = 1 held
.up:
    rcr bx, 1
    loop .k
    mov cl, 16 - WA_NKEYS
    shr bx, cl
    mov [wa_kbits], bx
    mov [wa_kwatch], bx         ; the held ones stay watched
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; wa_kmark - AH = a typed key's scancode: watch it if a tick reads it.
; Keeps every register.
wa_kmark:
    push bx
    push cx
    push si
    mov si, wa_ktab
    mov cx, WA_NKEYS
    mov bx, 1
.m:
    cmp ah, [si]
    je .hit
    inc si
    shl bx, 1
    loop .m
    jmp .out
.hit:
    or [wa_kwatch], bx
.out:
    pop si
    pop cx
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
    mov [wa_eye], ax
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

; wa_sincos - AX = an angle (any; taken mod 1024) -> AX = sin, DX = cos, Q14
wa_sincos:
    push bx
    and ax, 1023
    mov bx, ax
    shl bx, 1
    mov ax, [wa_sin+bx]
    add bx, 512
    and bx, 2047
    mov dx, [wa_sin+bx]
    pop bx
    ret

; wa_figtick - DI = a figure: one 30 Hz step of its patrol and its animation
wa_figtick:
    cmp byte [di+F_FLASH], 0
    je .alive
    dec byte [di+F_FLASH]
.alive:
    cmp byte [di+F_DEAD], 0
    je .live
    dec byte [di+F_DEAD]
    jnz .anim
    jmp wa_spawn
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
    mov [di+F_HEAD], ax
    mov ax, [si+8]
    mov [di+F_STEP], ax
.turn:
    mov ax, [di+F_HEAD]         ; face the way it is going, 48 a tick at most
    sub ax, [di+F_ANG]
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
    mov bx, [wa_w]
    and bx, 0xFFFE              ; the crosshair column's word in wa_colz
    call wa_wallz               ; (asked for: wa_colz fills on demand)
    mov ax, [wa_colz+bx]        ; ...what the wall there is at
    mov [wa_tmp], ax
    xor si, si                  ; best so far
    xor bp, bp                  ; ...and its inverse depth
    mov di, wa_figs
    mov cx, WA_NFIG
.f:
    cmp word [di+F_PZ], 0
    je .n
    cmp byte [di+F_DEAD], 0
    jne .n
    mov ax, [di+F_PCX]
    sub ax, [wa_w]
    jns .abs
    neg ax
.abs:
    cmp ax, [di+F_PWH]
    jg .n
    cmp word [di+F_PTOP], WA_HR/2
    jg .n
    cmp word [di+F_PBOT], WA_HR/2
    jl .n
    mov ax, [di+F_PIZ]
    cmp ax, [wa_tmp]
    jb .n                       ; a wall is nearer
    cmp ax, bp
    jbe .n
    mov bp, ax
    mov si, di
.n:
    add di, F_SIZE
    loop .f
    or si, si
    jz .miss
    mov di, si
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
    mov word [wa_px], WA_PB_X
    mov word [wa_py], WA_PB_Y
    xor ax, ax
    mov [wa_pxf], ax
    mov [wa_pyf], ax
    mov [wa_jz], ax
    mov [wa_jv], ax
    mov [wa_pitch], ax
    mov [wa_pbtk], ax
    mov [wa_pbfr], ax
    mov word [wa_eye], WA_EYE
    mov word [wa_ang], WA_PB_A << 6
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
    mov al, 'P'
    mov di, 32
    call wa_putc
    ret
wa_pbph:    dw 160, 64, 80      ; ticks along each patrol (the host search)

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
    add dx, WA_PB_A << 6
    mov [wa_ang], dx
    pop ax
    mov cx, WA_PB_PIT
    imul cx
    shl ax, 1
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
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
    mov al, 'P'
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
    mov al, '-'                 ; H: held edges
    cmp byte [wa_hyst], 0
    je .h
    mov al, 'H'
.h:
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

%include "wrender.inc"
%include "os88pit.inc"

; --- tables -----------------------------------------------------------------
%include "watab.inc"

wa_tpl:
    dw 120, 80, 330, 150
    dw wa_ttl, wa_cls
    OS88_CLASS wa_cls, 0, PAINT, wa_paint

    OS88_MENUSET wa_menus, wa_name, wa_oncmd
        OS88_MENU wa_m_game, wa_i_game, 4
    OS88_MENUSET_END wa_menus

wa_name:
wa_ttl:     db 'WireArena', 0
wa_m_game:  db 'Game', 0
wa_i_game:  dw wa_it_40, wa_it_80, wa_it_o40, wa_it_o80
wa_it_40:   db 'Play, 40 columns', 0
wa_it_80:   db 'Play, 80 columns', 0
wa_it_o40:  db 'Open arena, 40 columns', 0
wa_it_o80:  db 'Open arena, 80 columns', 0
wa_items:   db 1, 0, 0, 0, 1, 1, 0, 1  ; width (0 = 80, 1 = 40), arena

wa_help:
    db 'WireArena - renderer prototype', 0
    db 'Game menu: 40 or 80 columns; the full', 0
    db 'arena, or the open one (pillars only).', 0
    db 'Mouse looks; W A S D move; arrows', 0
    db 'turn and pitch; Space jumps; click', 0
    db 'or Ctrl fires; Tab: 80/40; V: vsync;', 0
    db 'B: bench. L: walls full/sparse. F: view', 0
    db '90/75/60. H: hold far edges. G: floor', 0
    db 'grid. P: play bench (8 s). Esc leaves.', 0
    db 'HUD: fps, frame, render, present ms,', 0
    db 'video writes a frame.', 0
    db 0

;               0         1         2         3
;               0123456789012345678901234567890123456789
wa_hudtpl:  db 'FPS       MS      R      P      N       ', 0

; a wall edge's glyph by half-row: upper half the middle line, lower the
; bottom one
wa_hgl:     times WA_HR/2 db 0xC4, '_'
; the figure layer's glyph for each 2x2 occupancy mask: bit 0 top-left,
; 1 top-right, 2 bottom-left, 3 bottom-right
wa_fglyph:  db 0x20, 0xDF, 0xDF, 0xDF, 0xDC, 0xDD, 0xDB, 0xDB
            db 0xDC, 0xDB, 0xDE, 0xDB, 0xDC, 0xDB, 0xDB, 0xDB
;              near   mid    far    figure flash  cross
; COLOUR SAYS WHAT A THING IS, not how far (the owner's call: two shades of
; blue never read as depth, and Hercules has no colour at all): a boundary
; wall dark blue, an item - a pillar, a block, a stair to come - cyan, the
; floor grid dark grey, the figures white. On mono every wall and dot is
; normal intensity and the figures alone are bright.
;              room   item   dot    figure flash  cross
wa_attrc:   db 0x01,  0x03,  0x08,  0x0F,  0x0C,  0x0E
wa_attrm:   db 0x07,  0x07,  0x07,  0x0F,  0x70,  0x0F
A_ROOM  equ 0
A_ITEM  equ 1
A_DOT   equ 2
A_FIG   equ 3
A_FLASH equ 4
A_CROSS equ 5

; --- bss ------------------------------------------------------------------
%assign WA_BSS 0
%macro WA_VAR 2
%1 equ os88_image_end+WA_BSS
%assign WA_BSS WA_BSS+%2
%endmacro
WA_VAR wa_win,2
WA_VAR wa_fsi,FSI_SIZE
WA_VAR wa_vseg,2
WA_VAR wa_w,2
WA_VAR wa_k16,2
WA_VAR wa_c16,2
WA_VAR wa_w2,2
WA_VAR wa_mode,1
WA_VAR wa_want,1
WA_VAR wa_mono,1
WA_VAR wa_quit,1
WA_VAR wa_vsync,1
WA_VAR wa_sparse,1
WA_VAR wa_arena,1
WA_VAR wa_nxv2,2
WA_VAR wa_nyv2,2
WA_VAR wa_nbox,2
WA_VAR wa_root,2
WA_VAR wa_sx,2
WA_VAR wa_sy,2
WA_VAR wa_sa,2
WA_VAR wa_xv,WA_MXV*2
WA_VAR wa_yv,WA_MYV*2
WA_VAR wa_vtx,WA_MVTX*2
WA_VAR wa_corn,(WA_MBOX+1)*4
WA_VAR wa_boxes,WA_MBOX*8
WA_VAR wa_bcol,WA_MBOX+2
WA_VAR wa_fov,1
WA_VAR wa_hyst,1
WA_VAR wa_grid,1
WA_VAR wa_kyq,2
WA_VAR wa_kyh,2
WA_VAR wa_wf,2
WA_VAR wa_trig,1
WA_VAR wa_mflash,1
WA_VAR wa_frame,1
WA_VAR wa_px,2
WA_VAR wa_py,2
WA_VAR wa_pxf,2
WA_VAR wa_pyf,2
WA_VAR wa_ang,2
WA_VAR wa_pitch,2
WA_VAR wa_jz,2
WA_VAR wa_jv,2
WA_VAR wa_eye,2
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
WA_VAR wa_rowo2,(WA_ROWS+1)*2
WA_VAR wa_figs,F_SIZE*WA_NFIG
WA_VAR wa_kbits,2                ; the held keys this frame (wa_keys)
WA_VAR wa_kfr,1                  ; ...polled in this frame
WA_VAR wa_kwatch,2               ; the keys to ask about (wa_keys)
WA_VAR wa_ksw,1                  ; frames to the next sweep of them all
WA_VAR wa_kqn,2                  ; wa_kq: typed keys a tick took, x 2,
WA_VAR wa_kqi,2                  ;   and how far wa_frame_input has read
WA_VAR wa_kq,WA_KQ*2
WR_BSS
WA_VAR wa_newp,2
WA_VAR wa_oldp,2
WA_VAR wa_newn,2
WA_VAR wa_oldn,2
WA_VAR wa_stamp,WA_CELLS*2       ; by cell OFFSET: even bytes only
WA_VAR wa_fmask,WA_CELLS*2
WA_VAR wa_cur,WA_CELLS*2
WA_VAR wa_vis,WA_CELLS*2
WA_VAR wa_lista,WA_CELLS*2
WA_VAR wa_listb,WA_CELLS*2
    OS88_BSS WA_BSS
    OS88_IMAGE_END
