; BONANZA - Bounce Bonanza, an isometric rolling-ball game for os8088.
; Contract: SPEC.md 128 (the plan: docs/plans/BOUNCE-BONANZA-PLAN.md).
;
; WAVE 0 IS THE ENGINE SPIKE (SPEC.md 128): a ball rolled over a generated
; isometric test course that HARDWARE-SCROLLS IN BOTH DIRECTIONS on the CGA
; (FSXM_CGA320) and the Hercules (FSXM_HERC with Excitebike's 200-line
; pair-pixel field, SPEC.md 102.7.1), the 64-frame phase-torus ball, and the
; instruments that price a frame.  No heightfield physics, obstacles, sound or
; game rules yet.
;
; This file is the header, the window and its desktop face (SPEC.md 128.1,
; 128.6): the title, the keys, the adapter line, and after a benchmark the
; RESULTS.  bzvideo.inc is the bracket, the mode, the retrace wait, the ring
; writers and the boxes (128.2, 128.4); bzgame.inc is the frame loop, the
; simulation, the camera, the autopilot and the instruments (128.4 - 128.6).
; Nothing here is a reference game's: the art is tools/bonanza_assets.py's
; (128.3), generated into build/bonanza-art/ and carried as four PARTS.
%include "os88api.inc"
OS88_HEADER 'BONANZA', bz_entry, 1 | OS88_F_PARTS, OS88_STACK_256 | OS88_HIGH | OS88_HIGHMEM
OS88_ICON16
    dw 0x07e0,0x1ff8,0x3ffc,0x7ffe,0x7ffe,0xffff,0xffff,0xffff
    dw 0xffff,0xffff,0xffff,0x7ffe,0x7ffe,0x3ffc,0x1ff8,0x07e0
    dw 0x07e0,0x1818,0x2004,0x4002,0x4c02,0x8c01,0x8001,0x8061
    dw 0x8061,0x8001,0x8c03,0x4c06,0x400e,0x203c,0x1ff8,0x07e0
OS88_ICON16_END
; The four art files are PARTS of this file (SPEC.md 128.3, 20.12), every one
; lazy and compressed: only the adapter's two are ever read, on the DESKTOP
; before the bracket (so op_fetch's refusal toast can be drawn), and both are
; dropped when the bracket returns (SPEC.md 128.7).
%define OP_NO_LAZYOK            ; (the fetch itself asks; no pre-check is used)
%include "os88parts.inc"
%include "bzconst.inc"

%macro SAVE 0
 push ax
 push bx
 push cx
 push dx
 push si
 push di
 push bp
 push es
%endmacro
%macro RESTORE 0
 pop es
 pop bp
 pop di
 pop si
 pop dx
 pop cx
 pop bx
 pop ax
%endmacro

BZ_LH       equ 10              ; the face's line pitch: an 8px cell and 2px of air
BZ_LMAX     equ 88              ; the longest padded line (a 720px Hercules content box)

; --- the part rows: the Makefile's BZ_PARTS order ------------------------------
BZ_P_CRSC   equ 0               ; BZCRSC.BIN  the course, CGA
BZ_P_CRSH   equ 1               ; BZCRSH.BIN  the course, Hercules
BZ_P_BALC   equ 2               ; BZBALC.BIN  the ball, CGA
BZ_P_BALH   equ 3               ; BZBALH.BIN  the ball, Hercules

bz_entry:
    push es                     ; op_load spends ES, which arrives KERNEL_SEG
    call op_load                ; SI is still the kernel's name: FIRST. Every
    pop es                      ; row is lazy, so this copies the name and
    jc .out                     ; claims nothing
    mov si, bz_tpl
    call OSAPI_WM_CREATE        ; ...and AL = the class slots this kernel
    jc .out                     ; dispatches (SPEC.md 11.104): no timer slot
    cmp al, WC_ONTIMER + 1      ; is kern_small, the 128KB machine, which
    sbb al, al                  ; refuses the bracket (SPEC.md 128.1)
    neg al
    mov [bz_small], al
    mov [bz_win], bx
    OS88_REGION_MOVABLE
    OS88_ALTENTER_ARM
    mov bx, [bz_win]
    clc
.out: ret

; -----------------------------------------------------------------------------
; the window's callbacks.  ES = KERNEL_SEG on entry to every one of them.
; -----------------------------------------------------------------------------
bz_paint:
    SAVE
    call bz_face
    cmp byte [bz_abon], 0
    je .done
    mov bx, [bz_win]
    mov si, bz_credits
    call os88ui_about_d
.done:
    RESTORE
    ret

bz_about:
    SAVE
    mov byte [bz_abon], 1
    mov bx, [bz_win]
    mov si, bz_credits
    call os88ui_about
    RESTORE
    ret

bz_click:
    SAVE
    cmp byte [bz_abon], 0
    je .done
    mov byte [bz_abon], 0
    call bz_repaint
.done:
    RESTORE
    ret

bz_onkey:
    SAVE
    cmp byte [bz_abon], 0
    je .key
    mov byte [bz_abon], 0
    call bz_repaint
    jmp .done
.key:
    cmp ax, KEY_ALTENTER
    je .play
    cmp al, 13
    je .play
    or al, 20h
    cmp al, 'f'
    je .play
    cmp al, 'b'
    jne .done
    mov byte [bz_mode], 1       ; B: the benchmark (SPEC.md 128.6)
    jmp .go
.play:
    mov byte [bz_mode], 0
.go:
    call bz_launch
.done:
    RESTORE
    ret

; the window repainted outside a paint: arm the clip first (SPEC.md 11.3)
bz_repaint:
    mov bx, [bz_win]
    call OSAPI_WM_CLIP_SET
    jc .out
    call bz_paint
.out:
    ret

; -----------------------------------------------------------------------------
; bz_adapter - what this window's display is: AL = 1 CGA, 2 Hercules, 0 neither
; (or no FSX mode for it).  Preserves all but AX and the flags.
; -----------------------------------------------------------------------------
bz_adapter:
    push bx
    push dx
    mov bx, [bz_win]
    call OSAPI_FSX_CAPS
    jc .none
    cmp dl, VID_CGA
    jne .herc
    test ax, 1 << FSXM_CGA320
    jz .none
    mov al, 1
    jmp .out
.herc:
    cmp dl, VID_HERC
    jne .none
    test ax, 1 << FSXM_HERC
    jz .none
    mov al, 2
    jmp .out
.none:
    xor al, al
.out:
    pop dx
    pop bx
    ret

; -----------------------------------------------------------------------------
; bz_launch - the desktop side of a play or a benchmark: every refusal is here,
; where a toast can still be drawn (SPEC.md 128.1, 128.7).  The adapter's two
; parts are fetched, the bracket runs, and both are dropped on every way out.
; -----------------------------------------------------------------------------
bz_launch:
    cmp byte [bz_small], 0
    je .big
    mov si, bz_t_small          ; kern_small: the parts are more heap than the
    jmp bz_toast                ; 128KB machine has
.big:
    call bz_adapter
    or al, al
    jnz .ok
    mov si, bz_t_adapt          ; VGA, EGA, MDA: CGA OR HERC ONLY
    jmp bz_toast
.ok:
    dec al
    mov [bz_herc], al
    mov al, BZ_P_CRSC
    add al, [bz_herc]
    mov [bz_pc], al
    mov al, BZ_P_BALC
    add al, [bz_herc]
    mov [bz_pb], al
    mov al, [bz_pc]
    call op_fetch               ; claim, read, expand - or a toast said why
    jc .out
    mov al, [bz_pb]
    call op_fetch
    jc .drop
    mov al, [bz_pc]
    call op_seg
    mov [bz_cseg], ax
    mov al, [bz_pb]
    call op_seg
    mov [bz_bseg], ax
    mov byte [bz_err], 0
    mov bx, [bz_win]
    mov ax, bz_fullscreen
    mov cx, FSXF_FASTTICK
    call OSAPI_FSX_RUN
    jnc .drop
    mov si, bz_t_nofs
    call bz_toast
.drop:
    mov al, [bz_pb]             ; (op_drop of a part that is not here is a
    call op_drop                ; no-op, so both go whichever failed)
    mov al, [bz_pc]
    call op_drop
    mov word [bz_cseg], 0
    mov word [bz_bseg], 0
.out:
    ret

; SI = a TOASTSTR in our segment
bz_toast:
    push es
    push ds
    pop es
    xor cx, cx
    call OSAPI_TOAST
    pop es
    ret

TOASTSTR bz_t_small, 'Bonanza: too little RAM'
TOASTSTR bz_t_adapt, 'CGA OR HERC ONLY'
TOASTSTR bz_t_nofs, 'Bonanza: no full screen'

; -----------------------------------------------------------------------------
; THE FACE.  Every line is ONE opaque OSAPI_FONT_RUN padded with spaces to the
; content's width (the padding is the erase, SPEC.md 6.1), and only the 2px
; gaps between lines and the strip under the last one are filled: no pixel is
; written twice.  The lines are built in bz_lbuf.
; -----------------------------------------------------------------------------
bz_face:
    mov bx, [bz_win]
    call OSAPI_WM_GEOM
    jc .out
    mov [bz_fw], cx
    mov [bz_fh], dx
    call OSAPI_WM_CONTENT
    mov [bz_ox], ax
    mov [bz_oy], dx
    mov ax, [bz_fw]
    mov cl, 3
    shr ax, cl
    cmp ax, BZ_LMAX
    jbe .cells
    mov ax, BZ_LMAX
.cells:
    mov [bz_fcells], ax
    mov word [bz_fy], 0
    ; line 0, 1: the title and the keys
    mov si, bz_s_title
    call bz_lstr
    call bz_line
    mov si, bz_s_keys
    call bz_lstr
    call bz_line
    ; line 2: the adapter, or the refusal's reason
    mov si, bz_s_small
    cmp byte [bz_small], 0
    jne .adl
    call bz_adapter
    mov si, bz_s_cga
    cmp al, 1
    je .adl
    mov si, bz_s_herc
    cmp al, 2
    je .adl
    mov si, bz_s_noad
.adl:
    call bz_lstr
    call bz_line
    mov si, bz_s_none
    call bz_lstr
    call bz_line
    cmp byte [bz_res], 0
    jne .results
    mov al, [bz_err]            ; 1 the mode was refused, 2 the display
    or al, al                   ; changed between the key and the bracket
    jz .hint
    mov si, bz_s_err
    cmp al, 1
    je .errl
    mov si, bz_s_err2
.errl:
    call bz_lstr
    call bz_line
.hint:
    mov si, bz_s_hint
    call bz_lstr
    call bz_line
    jmp .tail
.results:
    call bz_facres
.tail:
    ; the strip under the last line, to the content's foot
    mov bx, [bz_fy]
    mov dx, [bz_fh]
    dec dx
    cmp dx, bx
    jl .right
    call bz_fillrows
.right:
    ; the columns right of the last whole cell (a content width that is not
    ; a multiple of 8), over the lines' height only: the strips above own
    ; the full width already
    mov ax, [bz_fcells]
    mov cl, 3
    shl ax, cl
    cmp ax, [bz_fw]
    jae .out
    mov cx, [bz_fw]
    dec cx
    xor bx, bx
    mov dx, [bz_fh]
    dec dx
    call bz_fillrect
.out:
    ret

; the RESULTS of the last benchmark (SPEC.md 128.6): the frames and the display
; rate, the refreshes missed and the worst frame, then the mean CPU clocks of
; each part of a frame (PIT counts x 4), then the writer counts
bz_facres:
    mov si, bz_s_frames
    call bz_lstr
    mov ax, [bz_rframes]
    xor dx, dx
    call bz_lnum
    mov si, bz_s_disp
    call bz_lcat
    call bz_hz10                ; AX = the display rate x 10
    xor dx, dx
    mov cx, 10
    div cx
    push dx
    xor dx, dx
    call bz_lnum
    mov al, '.'
    call bz_lch
    pop ax
    add al, '0'
    call bz_lch
    mov si, bz_s_hz
    call bz_lcat
    call bz_line
    mov si, bz_s_miss           ; the refreshes missed and the worst frame: a
    call bz_lstr                ; mean rate cannot tell 0 misses from a few
    mov ax, [bz_rmiss]
    xor dx, dx
    call bz_lnum
    mov si, bz_s_worst
    call bz_lcat
    mov ax, [bz_rfmax]
    mov dx, [bz_rfmax + 2]
    shl ax, 1                   ; PIT counts x 4 = CPU clocks
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    call bz_lnum
    mov si, bz_s_clk
    call bz_lcat
    call bz_line
    mov si, bz_s_mean
    call bz_lstr
    call bz_line
    xor bx, bx                  ; BX = the part (0..5)
.part:
    push bx
    mov si, bx
    shl si, 1
    mov si, [bz_s_parts + si]
    call bz_lstr
    pop bx
    push bx
    call bz_meanclk             ; DX:AX = part BX's mean, CPU clocks
    call bz_lnum
    mov si, bz_s_clk
    call bz_lcat
    call bz_line
    pop bx
    inc bx
    cmp bx, BZ_NPART
    jb .part
    mov si, bz_s_cols
    call bz_lstr
    mov ax, [bz_rncol]
    xor dx, dx
    call bz_lnum
    mov si, bz_s_rows
    call bz_lcat
    mov ax, [bz_rnrow]
    xor dx, dx
    call bz_lnum
    mov si, bz_s_full
    call bz_lcat
    mov ax, [bz_rnfull]
    xor dx, dx
    call bz_lnum
    call bz_line
    ret

; -> AX = the display rate x 10, from the measured frames' mean period.  1 PIT
; count is 1/1,193,182 s, so rate x 10 = 11,931,820 / mean counts.  0 = none.
bz_hz10:
    push bx
    push cx
    push dx
    call bz_period              ; DX:AX = mean PIT counts a frame (DX = 0 if sane)
    or dx, dx
    jnz .zero
    cmp ax, 183                 ; (the divide's quotient must fit 16 bits)
    jb .zero
    mov cx, ax
    mov dx, 11931820 >> 16
    mov ax, 11931820 & 0ffffh
    div cx
    jmp .out
.zero:
    xor ax, ax
.out:
    pop dx
    pop cx
    pop bx
    ret

; -> DX:AX = the mean PIT counts of one measured frame (the six parts summed)
bz_period:
    push bx
    push cx
    push si
    xor ax, ax
    xor dx, dx
    mov si, bz_racc
    mov cx, BZ_NPART
.sum:
    add ax, [si]
    adc dx, [si + 2]
    add si, 4
    loop .sum
    call bz_div32
    pop si
    pop cx
    pop bx
    ret

; BX = part -> DX:AX = its mean in CPU clocks (PIT counts x 4)
bz_meanclk:
    push si
    mov si, bx
    shl si, 1
    shl si, 1
    mov ax, [bz_racc + si]
    mov dx, [bz_racc + si + 2]
    call bz_div32
    shl ax, 1
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    pop si
    ret

; DX:AX / [bz_rmfr] -> DX:AX (32 by 16, in two divides; 0 frames gives 0)
bz_div32:
    push bx
    push cx
    mov cx, [bz_rmfr]
    jcxz .zero
    mov bx, ax
    mov ax, dx
    xor dx, dx
    div cx                      ; the high word
    xchg ax, bx                 ; BX = the high quotient, AX = the low dividend
    div cx                      ; DX = the remainder from the high word
    mov dx, bx
    jmp .out
.zero:
    xor ax, ax
    xor dx, dx
.out:
    pop cx
    pop bx
    ret

; ---- the line builder ---------------------------------------------------------
; bz_lstr: SI = a NUL string -> bz_lbuf holds it (DI = its end)
bz_lstr:
    mov di, bz_lbuf
    mov byte [di], ' '          ; a cell of margin: the padding is the erase
    inc di
; bz_lcat: append SI's NUL string at DI
bz_lcat:
    push ax
.c:
    lodsb
    or al, al
    jz .e
    call bz_lch
    jmp .c
.e:
    pop ax
    ret

; AL = a character, appended at DI unless the line is full
bz_lch:
    cmp di, bz_lbuf + BZ_LMAX
    jae .full
    mov [di], al
    inc di
.full:
    ret

; DX:AX = an unsigned number, appended at DI in decimal
bz_lnum:
    ; STKBALANCE-LOOP: one digit pushed a turn and the second loop pops them down to the SI mark
    push ax
    push bx
    push cx
    push dx
    push si
    mov si, sp                  ; the digits go on the stack, least first
    mov cx, 10
.dig:
    mov bx, ax                  ; DX:AX / 10, in two divides
    mov ax, dx
    xor dx, dx
    div cx
    xchg ax, bx
    div cx
    push dx                     ; the digit
    mov dx, bx
    mov bx, ax
    or bx, dx
    jnz .dig
.out:
    pop ax
    add al, '0'
    call bz_lch
    cmp sp, si
    jne .out
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; the line at DI ends: pad it to the content's cells, draw it at [bz_fy] + 2,
; fill the 2px gap above it, and step [bz_fy]
bz_line:
    push ax
    push bx
    push cx
    push dx
    push si
    mov cx, [bz_fcells]
    add cx, bz_lbuf
.pad:
    cmp di, cx
    jae .padded
    mov byte [di], ' '
    inc di
    jmp .pad
.padded:
    mov di, cx
    mov byte [di], 0
    mov bx, [bz_fy]             ; the gap above the cell row
    mov dx, bx
    inc dx
    call bz_fillrows
    mov si, bz_lbuf
    xor cx, cx
    add cx, [bz_ox]
    mov dx, [bz_fy]
    add dx, 2
    add dx, [bz_oy]
    mov ax, CBLACK | (CWHITE << 8)
    call OSAPI_FONT_RUN
    add word [bz_fy], BZ_LH
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; BX = the first content row, DX = the last: filled white across the cells'
; width (bz_fillrect's x range)
bz_fillrows:
    push ax
    push cx
    xor ax, ax
    mov cx, [bz_fcells]
    shl cx, 1
    shl cx, 1
    shl cx, 1
    dec cx
    call bz_fillrect
    pop cx
    pop ax
    ret

; AX = x1, BX = y1, CX = x2, DX = y2 in content coordinates: a white fill,
; clipped to the content box's foot
bz_fillrect:
    push ax
    push bx
    push cx
    push dx
    cmp dx, [bz_fh]
    jl .h
    mov dx, [bz_fh]
    dec dx
.h:
    cmp dx, bx
    jl .out
    push ax
    mov al, CWHITE
    call OSAPI_SET_COLOR
    pop ax
    add ax, [bz_ox]
    add cx, [bz_ox]
    add bx, [bz_oy]
    add dx, [bz_oy]
    call OSAPI_GFX_FILL
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- the window -----------------------------------------------------------------
bz_tpl: dw 40, 24, 344, 168, bz_title, bz_cls
; its CLASS (SPEC.md 11.104): every handler; WF_OWNBG, the face paints every pixel
    OS88_CLASS bz_cls, WF_OWNBG, PAINT, bz_paint, ONKEY, bz_onkey, \
               ONCLICK, bz_click, ABOUT, bz_about
bz_title: db 'Bounce Bonanza',0
bz_credits: dw bz_title,bz_credit1,bz_credit2,bz_credit3,0
bz_credit1: db 'Isometric rolling-ball game',0
bz_credit2: db 'Wave 0: the two-way scroll engine',0
bz_credit3: db 'Generated art, original design',0

bz_s_title: db 'BOUNCE BONANZA - wave 0 engine spike',0
bz_s_keys:  db 'ENTER play   B benchmark',0
bz_s_cga:   db 'Adapter: CGA, 320x200 four colours',0
bz_s_herc:  db 'Adapter: Hercules, 360x200 pair pixels',0
bz_s_noad:  db 'CGA OR HERC ONLY',0
bz_s_small: db 'NEEDS MORE MEMORY (128KB kernel)',0
bz_s_none:  db 0
bz_s_hint:  db 'Arrows roll; Esc, F or Alt+Enter: back',0
bz_s_err:   db 'The full screen mode was refused',0
bz_s_err2:  db "The window's display changed",0
bz_s_frames: db 'Frames ',0
bz_s_disp:  db '   display ',0
bz_s_hz:    db ' Hz',0
bz_s_miss:  db 'Misses ',0
bz_s_worst: db '   worst frame ',0
bz_s_mean:  db 'Mean CPU clocks a frame:',0
bz_s_clk:   db ' clk',0
bz_s_cols:  db 'Columns ',0
bz_s_rows:  db '  rows ',0
bz_s_full:  db '  full writes ',0
bz_s_parts: dw bz_s_p0, bz_s_p1, bz_s_p2, bz_s_p3, bz_s_p4, bz_s_p5
bz_s_p0:    db '  sim+camera     ',0
bz_s_p1:    db '  box compose    ',0
bz_s_p2:    db '  rows           ',0
bz_s_p3:    db '  retrace (idle) ',0
bz_s_p4:    db '  flip+columns   ',0
bz_s_p5:    db '  box write      ',0

%include "bzvideo.inc"
%include "bzgame.inc"

; --- the part table (SPEC.md 128.3, 20.12) ------------------------------------
; Four rows, in the Makefile's BZ_PARTS order, every one OP_LAZY | OP_COMP:
; fetched by bz_launch on the desktop (op_fetch, 1942's pattern) and dropped
; when the bracket returns.
OS88_PARTS_BEGIN 4
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; 0  BZCRSC.BIN
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; 1  BZCRSH.BIN
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; 2  BZBALC.BIN
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; 3  BZBALH.BIN
OS88_PARTS_END

%define OS88UI_ABOUT
%define OS88UI_NOBTN
%include "os88ui.inc"
%include "os88alt.inc"

%assign BZ_BSS OP_BSS           ; the parts standard's bss comes first
%macro VAR 2
 %1 equ os88_image_end + BZ_BSS
 %assign BZ_BSS BZ_BSS + %2
%endmacro
; the desktop side
VAR bz_win,2
VAR bz_abon,1
VAR bz_small,1                  ; 1 = kern_small (no timer slot): refused
VAR bz_pc,1                     ; the course's part row for this adapter
VAR bz_pb,1                     ; ...and the ball's
VAR bz_fw,2                     ; the face: content width, height, origin
VAR bz_fh,2
VAR bz_ox,2
VAR bz_oy,2
VAR bz_fcells,2
VAR bz_fy,2
VAR bz_lbuf,BZ_LMAX + 2
; the engine's (bzgame.inc's head documents the ones a harness reads)
BZ_GAME_VARS
OS88_BSS BZ_BSS
OS88_IMAGE_END
