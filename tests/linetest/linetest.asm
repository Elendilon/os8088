; =============================================================================
; os8088 - tests/linetest/linetest.asm
;
; LINETEST: the gate for SPEC.md 5.6.6, the 1bpp three-column walk. That
; optimisation claims a dilated STEEP line is the identical pixel set drawn a
; third as often, and "identical" is the whole of it - so this package draws a
; deterministic fan of dilated lines and nothing else, and the gate is a
; framebuffer dump compared BYTE FOR BYTE against the same fan drawn by a
; kernel built without the change.
;
;   make bench   (or just: make test ... TESTAPPS=build/linetest.img)
;   make test VIDEO=herc HERCSEG=0x7000 TESTAPPS=build/linetest.img
;   ...launch it, then
;   python3 tools/qmp.py build/qmp.sock 'pmemsave 0x70000 0x8000 "/abs/a.bin"'
;
; Nothing here is random and nothing depends on the clock: the same build
; draws the same pixels every run, which is what makes the comparison mean
; something. The fan sweeps every steep slope the walk can take and BOTH
; directions of x, and its feet step one pixel at a time across several byte
; boundaries - the three columns can straddle two framebuffer bytes, and that
; is the case a mask-based walk gets wrong.
;
; Every proc is a near proc with a near ret: the kernel reaches a callback
; through the dispatcher in the package's own header (SPEC.md 20.1).
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'LINETEST', lt_entry

LT_APEXY  equ 4                     ; the fan's top row, in content coordinates
LT_FOOTX  equ 20                    ; ...and where its feet start
LT_FOOTD  equ 11                    ; the gap between feet: coprime with 8, so
                                    ; 24 of them land on every residue mod the
                                    ; framebuffer byte - and wide enough that
                                    ; no two lines touch, or a wrong pixel in
                                    ; one could be covered by its neighbour
LT_APEXD  equ 3                     ; the apex walks too: a sweep of slopes
LT_NFAN   equ 24
LT_REPS   equ 20                    ; fans per timed run

; -----------------------------------------------------------------------------
; lt_entry - package entry point (SPEC.md 20.2)
; in:  CS=DS=ES = our own segment, IF=1, gfx lock NOT held
; out: BX = window ptr, CF clear (CF set = abort, from wm_create)
; -----------------------------------------------------------------------------
lt_entry:
    push si
    mov si, lt_tpl
    call OSAPI_WM_CREATE
    pop si
    ret

; -----------------------------------------------------------------------------
; lt_paint - W_PAINT: the whole fan, every time
; in:  SI = window ptr; gfx lock held; content already filled
; out: nothing; preserves all registers
; -----------------------------------------------------------------------------
lt_paint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    mov [lt_win], si
    mov bx, si
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top
    mov [lt_ox], ax
    mov [lt_oy], dx
    mov bx, si
    call OSAPI_WM_GEOM              ; CX = content width, DX = content height
    mov [lt_cw], cx
    mov [lt_ch], dx

    mov al, CBLACK                  ; black behind, so a line and its erase are
    call OSAPI_SET_COLOR            ; both changes a dump can see
    mov ax, [lt_ox]
    mov bx, [lt_oy]
    mov cx, ax
    add cx, [lt_cw]
    dec cx
    mov dx, bx
    add dx, [lt_ch]
    dec dx
    call OSAPI_GFX_FILL

    ; --- the fan ------------------------------------------------------------
    ; dy is the content height and dx at most LT_NFAN, so every line is STEEP:
    ; the case 5.6.6 claims. The apex walks as well as the foot, so this is a
    ; sweep of slopes rather than one pencil through a single pixel.
    call lt_fan

    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; lt_fan - the fan alone, so lt_onkey can time exactly what the gate compares
lt_fan:
    push ax
    push bx
    push cx
    push dx
    push di
    mov al, CWHITE
    call OSAPI_SET_COLOR
    xor di, di
.fan:
    call lt_ends                    ; left-leaning: apex left of foot
    call lt_line
    inc di
    cmp di, LT_NFAN
    jb .fan

    xor di, di
.fan2:
    call lt_ends                    ; ...and the mirror, so the walk takes
    xchg ax, cx                     ; sx = -1 as well
    call lt_line
    inc di
    cmp di, LT_NFAN
    jb .fan2
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; lt_ends - fan line DI's endpoints
; out: AX,BX = apex   CX,DX = foot; clobbers AX/BX/CX/DX
lt_ends:
    mov ax, di
    mov cl, LT_APEXD
    mul cl                          ; DI < 256, so AL * CL is the whole of it
    add ax, 6
    mov bx, LT_APEXY
    push ax
    mov ax, di
    mov cl, LT_FOOTD
    mul cl
    add ax, LT_FOOTX
    mov cx, ax
    pop ax
    mov dx, [lt_ch]
    sub dx, 5
    ret

; lt_line - one DILATED line in content coordinates
; in:  AX,BX = x1,y1  CX,DX = x2,y2; preserves every register
lt_line:
    push ax
    push bx
    push cx
    push dx
    push si
    add ax, [lt_ox]
    add cx, [lt_ox]
    add bx, [lt_oy]
    add dx, [lt_oy]
    mov si, 1                       ; DILATED - the whole point of the gate
    call OSAPI_GFX_LINE
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; lt_onkey - any key: draw the fan LT_REPS times and report the PIT counts it
; took. The gate answers "same pixels"; this answers "how much cheaper", and
; the two have to be asked of the same drawing or neither means anything.
; -----------------------------------------------------------------------------
lt_onkey:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov si, [lt_win]
    call lt_now
    mov [lt_t0], ax
    mov [lt_t0+2], dx
    mov cx, LT_REPS
.rep:
    push cx
    call lt_fan
    pop cx
    loop .rep
    call lt_now
    sub ax, [lt_t0]
    sbb dx, [lt_t0+2]
    mov [lt_res], ax
    mov [lt_res+2], dx
    call lt_report
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; lt_now - DX:AX = ticks:position, the missile-logger clock (PERFORMANCE.md)
lt_now:
    push cx
.retry:
    call OSAPI_GET_TICKS
    mov cx, ax
    call lt_pit
    neg ax
    push ax
    call OSAPI_GET_TICKS
    pop dx
    cmp ax, cx
    jne .retry
    xchg ax, dx
    pop cx
    ret

lt_pit:
    push dx
    mov al, 0
    out 0x43, al
    jmp short $+2
    in al, 0x40
    mov dl, al
    jmp short $+2
    in al, 0x40
    mov ah, al
    mov al, dl
    pop dx
    ret

; lt_report - the count, as decimal, over the fan
lt_report:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, [lt_ox]
    mov bx, [lt_oy]
    mov cx, ax
    add cx, 130
    mov dx, bx
    add dx, 9
    call OSAPI_GFX_FILL
    mov ax, [lt_res]
    mov dx, [lt_res+2]
    mov di, lt_buf + 11
    mov byte [di], 0
    mov bx, 10
.dig:
    mov cx, ax
    mov ax, dx
    xor dx, dx
    div bx
    mov si, ax
    mov ax, cx
    div bx
    add dl, '0'
    dec di
    mov [di], dl
    mov dx, si
    mov cx, ax
    or ax, dx
    mov ax, cx
    jnz .dig
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov si, di
    mov cx, [lt_ox]
    add cx, 2
    mov dx, [lt_oy]
    add dx, 1
    call OSAPI_FONT_STR
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
lt_onclick:
    ret

lt_tpl:
    dw 40, 40, 320, 200
    dw lt_ttl, lt_paint, lt_onkey, lt_onclick

lt_ttl:     db 'Line Test', 0
lt_ox:      dw 0
lt_oy:      dw 0
lt_cw:      dw 0
lt_ch:      dw 0
lt_win:     dw 0
lt_t0:      dw 0, 0
lt_res:     dw 0, 0
lt_buf:     times 12 db 0

    OS88_IMAGE_END
