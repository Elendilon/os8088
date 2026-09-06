%ifdef CSDIAG
; =============================================================================
; os8088 - apps/skies/csdiag.inc
;
; THE WATCHDOG (SPEC.md 88.14) - A DIAGNOSTIC BUILD ONLY. No shipped floppy
; carries this; `make skiesdiag` is what builds it.
;
; A hard freeze inside an fsx bracket takes the whole machine with it, and a
; field machine has no debugger: the only instrument is a photograph of the
; glass. So this hooks int 08h for the length of the bracket and paints,
; every tick and straight into VRAM, the last CSD_SLOTS interrupted IPs and a
; TICK COUNTER. The frozen screen then says where the machine is stuck.
;
; The counter is half the answer on its own. If it is still moving when the
; picture has stopped, IRQ0 is alive, IF is set, and the freeze is a loop in
; this package that the IPs beside it name. If it has stopped too, the
; machine is dead below us - IF clear, or the tick chain gone - and no amount
; of looking at Clear Skies will find it.
;
; A word is painted BIG-ENDIAN as sixteen pixels, bit 15 leftmost, CSD_ROWS
; scan rows tall, at the top-left corner of the VIEW. The frame overwrites it
; constantly, which is the point: what survives is what was painted after the
; last frame that ever finished.
;
; It chains rather than replacing: the kernel's sch_isr is what schedules and
; what sends the EOI, and this runs in front of it on the interrupted task's
; stack, which is ~20 bytes of one slice for as long as the bracket lasts.
; =============================================================================

CSD_SLOTS equ 3                     ; interrupted IPs kept
CSD_ROWS  equ 4                     ; scan rows a word is painted in

; -----------------------------------------------------------------------------
; cs_diag_on / cs_diag_off - take and give back the int 08h vector. Called
; with the bracket up and cs_devoff built. Preserve everything
; -----------------------------------------------------------------------------
cs_diag_on:
    push ax
    push es
    xor ax, ax
    mov es, ax
    mov word [cs_dhead], 0
    mov word [cs_dtick], 0
    pushf                           ; CLAUDE.md: pushf/cli ... popf, so an
    cli                             ; interrupt disabled here comes back
    mov ax, [es:8*4]
    mov [cs_dold], ax
    mov ax, [es:8*4 + 2]
    mov [cs_dold + 2], ax
    mov word [es:8*4], cs_diag_isr
    mov ax, cs
    mov [es:8*4 + 2], ax
    popf
    pop es
    pop ax
    ret

cs_diag_off:
    push ax
    push es
    xor ax, ax
    mov es, ax
    pushf
    cli
    mov ax, [cs_dold]
    mov [es:8*4], ax
    mov ax, [cs_dold + 2]
    mov [es:8*4 + 2], ax
    popf
    pop es
    pop ax
    ret

; -----------------------------------------------------------------------------
; cs_diag_isr - int 08h, in front of the kernel's
; -----------------------------------------------------------------------------
cs_diag_isr:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    mov ax, cs                      ; a package's CS is its DS (SPEC.md 20)
    mov ds, ax
    cld
    mov bp, sp                      ; SS != DS (CLAUDE.md), and [bp] wants SS
    mov ax, [bp + 9*2]              ; nine pushes down to the IRET frame's IP
    mov bx, [cs_dhead]
    mov [cs_dring + bx], ax
    add bx, 2
    cmp bx, CSD_SLOTS * 2
    jb .head
    xor bx, bx
.head:
    mov [cs_dhead], bx
    inc word [cs_dtick]
    call cs_diag_paint
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    jmp far [cs:cs_dold]            ; the kernel's, which EOIs and schedules

; -----------------------------------------------------------------------------
; cs_diag_paint - the ring and the counter into VRAM. Clobbers everything
; -----------------------------------------------------------------------------
cs_diag_paint:
    cmp byte [cs_back], 0           ; no bracket, no framebuffer
    je .out
    mov es, [cs_fsi + FSI_SEG]
    cmp byte [cs_back], CSB_MODEX
    jne .go
    mov dx, 0x3C4                   ; every plane, or a Mode X word lands in
    mov ax, 0x0F02                  ; whichever one was last selected
    out dx, ax
.go:
    xor bx, bx                      ; BX = the slot
.slot:
    mov si, bx
    shl si, 1
    mov ax, [cs_dring + si]
    cmp bx, CSD_SLOTS               ; ...and the last slot is the COUNTER,
    jb .word                        ; which is what says IRQ0 is still alive
    mov ax, [cs_dtick]
.word:                              ; AH goes down first, so the leftmost eight
    mov di, bx                      ; pixels are bits 15..8 and the next eight
                                    ; are bits 7..0 - a word read left to right
    shl di, 1
    shl di, 1                       ; CSD_ROWS = 4: the slot's first row
    mov cx, CSD_ROWS
.row:
    mov si, di
    shl si, 1
    mov si, [cs_devoff + si]
    cmp cx, 1                       ; the last row of a block is left BLANK,
    jne .put                        ; so four blocks read as four in a
    xor ax, ax                      ; photograph rather than as one smear
.put:
    mov [es:si], ah
    mov [es:si + 1], al
    inc di
    loop .row
    inc bx
    cmp bx, CSD_SLOTS
    jbe .slot
.out:
    ret

%endif
