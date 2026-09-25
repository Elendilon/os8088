; =============================================================================
; os8088 - apps/tithe/tifull.inc
;
; THE FULL CARD (SPEC.md 97.12.10.8): a RIGHT click on a card in the hand, or
; on a character on the board, puts the whole card over the board - its name,
; what it costs and what a kill of it pays, both rows' numbers, and every
; keyword with a line saying what it DOES - and any click or key takes it away.
;
; THE REPAIR IS WHAT THE OWNER ASKED ABOUT, and it is two calls. The pixels the
; card covers are SAVED into a claim taken for the moment it is up
; (OSAPI_GFX_SAVE, SPEC.md 5.3 - 16 KB on a VGA's four planes, 4 on one bit)
; and RESTORED when it goes, while the worker draws no frame at all in between
; - so nothing under the card moves and the restore is exact. A claim the heap
; refuses, or a save refused for straddling two displays, still shows the card
; and repairs the old way: a whole repaint, asked of the worker.
;
; The card is ONE band and ONE blit, composed in the scratch part in the small
; face (97.4.1.1): white on black inside a white frame, the list's own look.
; =============================================================================

TI_FW_COLS  equ 56                  ; characters a line, in the small face
TI_FW_BYTES equ 44                  ; the card's width in bytes: 352 pixels
TI_FW_LINES equ 12                  ; the most lines a card has
TI_FW_LH    equ 8                   ; ...and a line's pitch, the face's 6 + 2
TI_FW_STRIDE equ TI_FW_BYTES + 1    ; (ti_glyph's pad byte)
TI_FULLBAND equ TI_FW_STRIDE * (TI_FW_LINES * TI_FW_LH + 8)

; -----------------------------------------------------------------------------
; ti_onrclick - OSAPI_WM_ONRCLICK: CX, DX = the press, SI = the window. The UI
; task, the lock held. A card up goes; otherwise the card or the character
; under the press comes up. Preserves every register.
; -----------------------------------------------------------------------------
ti_onrclick:
    push ax
    push bx
    mov [ti_win], si
    cmp byte [tg_fcard], 0
    je .open
    call ti_full_close
    jmp short .out
.open:
    cmp byte [ti_ok], 0
    je .out
    cmp byte [tg_ph], TG_PH_PLAN    ; while a player plans, and nothing else
    jne .out                        ; owns the glass
    cmp byte [ti_rv], 0
    jne .out
    cmp byte [ti_rowst], 0
    jne .out
    mov ax, -1
    cmp byte [tg_list], 0           ; A CARD IN THE HAND...
    jne .cell
    call ti_card_hit
    cmp ax, -1
    jne .view
.cell:
    call ti_cell_hit                ; ...or A CHARACTER ON THE BOARD
    cmp ax, -1
    je .out
    add ax, TI_HAND
.view:
    mov bl, TI_C_SIZE
    mul bl
    mov bx, ax
    mov al, [ti_cards + bx + TI_C_CARD]
    cmp al, TR_EMPTY
    je .out
    call ti_full_open
.out:
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_full_open - card AL, whole, over the board: composed, the glass under it
; saved, and put down. Preserves every register.
; -----------------------------------------------------------------------------
ti_full_open:
    push ax
    push di
    call ti_full_compose            ; [ti_fwh] = its rows
    mov di, ti_fwx
    call ti_box_show
    mov byte [tg_fcard], 1          ; ...and the worker draws nothing under it
    pop di
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_box_show - the band at TI_S_FULL, TI_FW_BYTES wide, put down in the
; middle of the board with the glass under it SAVED first. DI -> its record:
; x, y, rows, the claim (words); the rows are the caller's, the rest is set
; here. Preserves every register.
;
; TWO BOXES USE IT, the full card and the mulligan offer, each with its own
; record - so a card read over the offer comes off onto the offer again.
; -----------------------------------------------------------------------------
ti_box_show:
    push ax
    push bx
    push cx
    push dx
    push si
    push bp
    push es
    mov ax, [ti_boardw]             ; WHERE: centred on the board, on the
    sub ax, TI_FW_BYTES * 8         ; byte grid, inside the content box
    sar ax, 1
    add ax, [ti_bx]
    and ax, 0FFF8h
    cmp ax, [ti_ox]
    jge .xok
    mov ax, [ti_ox]
    add ax, 7
    and ax, 0FFF8h
.xok:
    mov [di], ax
    mov ax, [ti_boardh]
    sub ax, [di + 4]
    sar ax, 1
    add ax, [ti_by]
    cmp ax, [ti_oy]
    jge .yok
    mov ax, [ti_oy]
.yok:
    mov [di + 2], ax

    mov word [di + 6], 0            ; THE GLASS UNDER IT, saved: a claim for
    push di                         ; this long, the width's bytes by its rows
    call OSAPI_VIDEO                ; by the planes (DH = bits a pixel: 4 on
    pop di                          ; a VGA's planes, 1 on one bit)
    mov al, dh
    xor ah, ah
    mov bx, TI_FW_BYTES
    mul bx
    mul word [di + 4]
    add ax, 1023
    adc dx, 0
    mov cx, 1024
    div cx
    call OSAPI_MEM_CLAIM
    jc .show
    mov [di + 6], dx
    mov es, dx
    push di
    call ti_box_rect
    xor di, di
    call OSAPI_GFX_SAVE
    pop di
    jnc .show
    mov dx, [di + 6]                ; refused (it straddles two displays): the
    call OSAPI_MEM_FREE             ; old repair, a whole repaint
    mov word [di + 6], 0
.show:
    call ti_ess                     ; ...AND THE BOX, one blit
    mov si, TI_S_FULL
    mov ax, [di]
    mov bx, [di + 2]
    mov cx, TI_FW_BYTES * 8
    mov dx, [di + 4]
    mov bp, TI_FW_STRIDE
    call OSAPI_GFX_BLIT1
    pop es
    pop bp
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_box_rect - DI -> a box's record: AX, BX, CX, DX = its rectangle,
; inclusive, for the save and the restore. Preserves every other register.
ti_box_rect:
    mov ax, [di]
    mov bx, [di + 2]
    mov cx, ax
    add cx, TI_FW_BYTES * 8 - 1
    mov dx, bx
    add dx, [di + 4]
    dec dx
    ret

; ti_box_hide - DI -> a box's record: the glass under it put back, and the
; claim freed - or, when nothing was saved, a whole repaint asked of the
; worker. The lock held. Preserves every register.
ti_box_hide:
    push ax
    push bx
    push cx
    push dx
    push si
    push es
    mov dx, [di + 6]
    or dx, dx
    jz .whole
    mov es, dx
    call ti_box_rect
    xor si, si
    call OSAPI_GFX_REST
    mov dx, [di + 6]
    call OSAPI_MEM_FREE
    mov word [di + 6], 0
    jmp short .out
.whole:
    mov byte [ti_rpq], 1
.out:
    pop es
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_box_free - DI -> a box's record: a whole paint is about to draw over it,
; so its claim goes with nothing restored. Preserves every register.
ti_box_free:
    push dx
    mov dx, [di + 6]
    or dx, dx
    jz .out
    call OSAPI_MEM_FREE
    mov word [di + 6], 0
.out:
    pop dx
    ret

; -----------------------------------------------------------------------------
; ti_full_close - the card goes, and the glass under it comes back. The lock
; held. Preserves every register.
; -----------------------------------------------------------------------------
ti_full_close:
    cmp byte [tg_fcard], 0
    je .ret
    push di
    mov byte [tg_fcard], 0
    mov di, ti_fwx
    call ti_box_hide
    pop di
.ret:
    ret

; ti_full_drop - a whole paint is about to draw over the boxes: both are gone,
; and their claims with them, with nothing restored - the full card for good,
; the mulligan offer until the worker puts it up again (tg_mull_ck).
; Preserves every register.
ti_full_drop:
    push di
    mov byte [tg_fcard], 0
    mov di, ti_fwx
    call ti_box_free
    mov byte [ti_mbup], 0
    mov di, ti_mbx
    call ti_box_free
    pop di
    ret

; -----------------------------------------------------------------------------
; ti_mull_up - THE MULLIGAN OFFER (SPEC.md 97.12.10.9), composed and put down
; over the board the way the full card is - its glass saved, so taking it
; away is one restore. The worker, the lock held. Preserves every register.
;
;   P1 - YOUR OPENING HAND
;   KEEP IT, OR SHUFFLE IT BACK AND DRAW AS MANY AGAIN.
;   ONCE, AND ONLY BEFORE YOUR FIRST MOVE.
;
;      [ KEEP - ENTER ]      [ REDRAW - D ]
; -----------------------------------------------------------------------------
TI_MB_LINE  equ 4                   ; the buttons' line...
TI_MB_BY    equ 4 + TI_MB_LINE * TI_FW_LH - 2   ; ...their rows in the box
TI_MB_BH    equ 10
TI_MB_K0    equ 6                   ; KEEP's bytes, [K0, K1)
TI_MB_K1    equ 20
TI_MB_R0    equ 24                  ; REDRAW's, [R0, R1)
TI_MB_R1    equ 38

ti_mull_up:
    push ax
    push bx
    push dx
    push si
    push di
    push bp
    push es
    push word [ti_face]
    xor ax, ax
    call ti_face_set                ; the small face
    call ti_fw_clear
    call ti_fw_start
    mov al, 'P'
    stosb
    mov al, [tg_side]
    add al, '1'
    stosb
    mov si, ti_s_mull1
    call ti_poke
    call ti_fw_line
    mov si, ti_s_mull2
    call ti_fw_text
    mov si, ti_s_mull3
    call ti_fw_text
    call ti_fw_start                ; (a line left empty)
    call ti_fw_line
    mov dx, 4 + TI_MB_LINE * TI_FW_LH   ; THE TWO BUTTONS: lettered white on
    mov di, TI_S_FULL               ; the black, and then the two boxes they
    mov bp, TI_FW_STRIDE            ; sit in inverted - black on white, the
    mov bx, TI_MB_K0 * 8 + ((TI_MB_K1 - TI_MB_K0) * 8 - 12 * 6) / 2
    mov si, ti_s_mkeep              ; plan list's own buttons
    call ti_text
    mov bx, TI_MB_R0 * 8 + ((TI_MB_R1 - TI_MB_R0) * 8 - 10 * 6) / 2
    mov si, ti_s_mredo
    call ti_text
    inc word [ti_fwl]
    mov di, TI_S_FULL + TI_MB_BY * TI_FW_STRIDE
    mov dx, TI_MB_BH
.r:
    mov bx, TI_MB_K0
.c:
    cmp bx, TI_MB_K1
    jne .x
    mov bx, TI_MB_R0
.x:
    xor byte [es:di + bx], 0FFh
    inc bx
    cmp bx, TI_MB_R1
    jb .c
    add di, TI_FW_STRIDE
    dec dx
    jnz .r
    call ti_fw_frame
    pop ax
    call ti_face_set
    mov ax, [ti_fwh]
    mov [ti_mbh], ax
    mov di, ti_mbx
    call ti_box_show
    mov byte [ti_mbup], 1
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop bx
    pop ax
    ret

; ti_mull_down - the offer comes off and the glass under it back. The lock
; held. Preserves every register.
ti_mull_down:
    cmp byte [ti_mbup], 0
    je .ret
    push di
    mov byte [ti_mbup], 0
    mov di, ti_mbx
    call ti_box_hide
    pop di
.ret:
    ret

; ti_mull_hit - CX, DX = a click: AL = 1 on KEEP, 2 on REDRAW, 0 on neither.
; Preserves every other register.
ti_mull_hit:
    push cx
    push dx
    xor al, al
    cmp byte [ti_mbup], 0
    je .out
    sub dx, [ti_mby]
    jb .out
    cmp dx, TI_MB_BY
    jb .out
    cmp dx, TI_MB_BY + TI_MB_BH
    jae .out
    sub cx, [ti_mbx]
    jb .out
    cmp cx, TI_MB_K0 * 8
    jb .out
    mov al, 1
    cmp cx, TI_MB_K1 * 8
    jb .out
    mov al, 2
    cmp cx, TI_MB_R0 * 8
    jb .no
    cmp cx, TI_MB_R1 * 8
    jb .out
.no:
    xor al, al
.out:
    pop dx
    pop cx
    ret

ti_s_mull1: db ' - YOUR OPENING HAND', 0
ti_s_mull2: db 'KEEP IT, OR SHUFFLE IT BACK AND DRAW AS MANY AGAIN.', 0
ti_s_mull3: db 'ONCE, AND ONLY BEFORE YOUR FIRST MOVE.', 0
ti_s_mkeep: db 'KEEP - ENTER', 0
ti_s_mredo: db 'REDRAW - D', 0

; -----------------------------------------------------------------------------
; ti_full_compose - card AL into the band at TI_S_FULL, [ti_fwh] = its rows.
; Preserves every register.
;
;   PIKEMAN
;   COST 1G   POWER 1 - A KILL OF IT PAYS 1 SOULS
;   FRONT  <hp melee ranged shield gold heal>
;     GUARD  TAKES GAP HITS AIMED ABOVE OR BELOW IT
;   REAR   ...
;
; An ORDER has one block, its EFFECT for the round it is played in.
; -----------------------------------------------------------------------------
ti_full_compose:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    push word [ti_face]
    mov [ti_fwcard], al
    xor ax, ax
    call ti_face_set                ; the small face
    call ti_fw_clear
    mov al, [ti_fwcard]             ; --- the NAME -------------------------
    xor ah, ah
    mov bx, ax
    shl bx, 1
    mov si, [ti_cardname + bx]
    call ti_fw_start
    call ti_poke
    call ti_fw_line
    mov al, [ti_fwcard]             ; (ti_poke left AL at the NUL)
    call tr_crec                    ; BX = the record
    mov [ti_fwrec], bx
    call ti_fw_start                ; --- COST, POWER ----------------------
    mov si, ti_s_fcost
    call ti_poke
    mov bx, [ti_fwrec]
    mov al, [bx + TI_CR_COSTG]
    call tg_num
    mov al, 'G'
    stosb
    mov al, [bx + TI_CR_COSTS]
    or al, al
    jz .nos
    mov al, ' '
    stosb
    mov al, [bx + TI_CR_COSTS]
    call tg_num
    mov al, 'S'
    stosb
.nos:
    cmp byte [bx + TI_CR_KIND], TI_KIND_ORDER
    je .ord
    mov si, ti_s_fpow
    call ti_poke
    mov al, [bx + TI_CR_POWER]
    call tg_num
    mov si, ti_s_fsoul
    call ti_poke
    mov al, [bx + TI_CR_POWER]      ; (POWER is what a kill of it pays)
    call tg_num
    mov si, ti_s_fsouls
    call ti_poke
    call ti_fw_line
    mov si, ti_s_ffront             ; --- FRONT and REAR -------------------
    mov bx, [ti_fwrec]
    add bx, TI_CR_FRONT
    call ti_fw_block
    mov si, ti_s_frear
    mov bx, [ti_fwrec]
    add bx, TI_CR_REAR
    call ti_fw_block
    jmp short .frame
.ord:
    mov si, ti_s_ford
    call ti_poke
    call ti_fw_line
    mov si, ti_s_feff               ; an ORDER: its one block, the round's
    mov bx, [ti_fwrec]
    add bx, TI_CR_FRONT
    call ti_fw_block
.frame:
    call ti_fw_frame
    pop ax
    call ti_face_set
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_fw_clear - the band black and no lines in it: ES = the scratch part, the
; small face asked for by the caller. Preserves every register bar ES.
ti_fw_clear:
    push ax
    push cx
    push di
    call ti_ess
    cld
    mov di, TI_S_FULL
    mov cx, TI_FULLBAND
    xor al, al
    rep stosb
    mov word [ti_fwl], 0
    pop di
    pop cx
    pop ax
    ret

; ti_fw_frame - [ti_fwh] = the rows the lines took, and a frame round them.
; ES = the scratch part. Preserves every register.
ti_fw_frame:
    push ax
    push bx
    push cx
    push dx
    push di
    mov ax, [ti_fwl]
    mov dx, TI_FW_LH
    mul dx
    add ax, 6
    mov [ti_fwh], ax
    xor bx, bx                      ; the top and the foot
    call ti_fw_hrow
    mov bx, [ti_fwh]
    dec bx
    call ti_fw_hrow
    mov cx, [ti_fwh]                ; and the two uprights
    mov di, TI_S_FULL
.up:
    or byte [es:di], 080h
    or byte [es:di + TI_FW_BYTES - 1], 01h
    add di, TI_FW_STRIDE
    loop .up
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_fw_hrow - band row BX, all set across the card. Preserves every register.
ti_fw_hrow:
    push ax
    push cx
    push di
    mov ax, bx
    mov cx, TI_FW_STRIDE
    mul cx
    add ax, TI_S_FULL
    mov di, ax
    mov cx, TI_FW_BYTES
    mov al, 0FFh
    rep stosb
    pop di
    pop cx
    pop ax
    ret

; ti_fw_start - DI = the line buffer, ES = ours, for a line to be built into.
; Preserves every register bar DI and ES.
ti_fw_start:
    push ds
    pop es
    mov di, ti_fwbuf
    ret

; ti_fw_text - SI = a sentence, as the next line. Preserves every register
; bar AL, SI and ES.
ti_fw_text:
    push di
    call ti_fw_start
    call ti_poke
    call ti_fw_line
    pop di
    ret

; ti_fw_line - the line built at ti_fwbuf (DI past it) lettered into the band
; as line [ti_fwl], and ES back on the scratch part. Preserves every register
; bar ES.
ti_fw_line:
    push ax
    push bx
    push dx
    push si
    push di
    push bp
    mov byte [di], 0
    call ti_ess
    mov ax, [ti_fwl]
    cmp ax, TI_FW_LINES
    jae .out
    mov dx, TI_FW_LH
    mul dx
    add ax, 4
    mov dx, ax
    mov di, TI_S_FULL
    mov bp, TI_FW_STRIDE
    mov bx, 6
    mov si, ti_fwbuf
    call ti_text
    inc word [ti_fwl]
.out:
    pop bp
    pop di
    pop si
    pop dx
    pop bx
    pop ax
    ret

; ti_fw_block - SI = the row's word (FRONT, REAR, EFFECT), BX -> the block:
; its numbers on a line, then a line for each keyword saying what it does.
; Preserves every register.
ti_fw_block:
    push ax
    push bx
    push cx
    push si
    push di
    push es
    push bx
    call ti_fw_start
    call ti_poke
    pop bx
    push bx
    mov al, [bx + TI_B_HP]          ; HP, where it has a body
    or al, al
    jz .nohp
    mov ah, TI_IC_HP
    call .pair
.nohp:
    call tg_blkst                   ; then the five, as a card shows them
    xor bx, bx
.st:
    mov al, [tg_st + bx]
    or al, al
    jz .stn
    mov ah, [tg_icon + bx]
    call .pair
.stn:
    inc bx
    cmp bx, 5
    jb .st
    pop bx
    call ti_fw_line
    lea si, [bx + TI_B_KW]          ; THE KEYWORDS, a line each
    mov cx, 3
.kw:
    lodsb
    or al, al
    jz .kn
    push si
    push ax
    call ti_fw_start
    mov al, ' '
    stosb
    stosb
    pop ax
    push ax
    mov bl, al
    and bl, 31
    xor bh, bh
    shl bx, 1
    mov si, [ti_kwname + bx]
    call ti_poke
    pop ax
    push cx
    mov cl, 5
    shr al, cl
    pop cx
    or al, al                       ; ...its number, where it has one
    jz .nonum
    push ax
    mov al, ' '
    stosb
    pop ax
    call tg_num
.nonum:
    mov al, ' '
    stosb
    stosb
    mov si, [ti_kwrule + bx]
    call ti_poke
    call ti_fw_line
    pop si
.kn:
    loop .kw
    pop es
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret
.pair:                              ; `  <icon><n>` at DI. AH = icon, AL = n
    push ax
    mov al, ' '
    stosb
    stosb
    mov al, ah
    stosb
    pop ax
    call tg_num
    ret

ti_s_fcost: db 'COST ', 0
ti_s_fpow:  db '   POWER ', 0
ti_s_fsoul: db ' - A KILL OF IT PAYS ', 0
ti_s_fsouls: db ' SOULS', 0
ti_s_ford:  db '   AN ORDER, FOR THE ROUND IT IS PLAYED', 0
ti_s_ffront: db 'FRONT', 0
ti_s_frear: db 'REAR ', 0
ti_s_feff:  db 'EFFECT', 0

tg_fcard:   db 0                    ; the FULL CARD is up
ti_fwcard:  db 0                    ; ...which card
ti_fwrec:   dw 0                    ; ...its record
ti_fwl:     dw 0                    ; ...the lines composed
ti_fwx:     dw 0                    ; ITS BOX (ti_box_show): where,
ti_fwy:     dw 0
ti_fwh:     dw 0                    ; ...its rows on the glass,
ti_fwseg:   dw 0                    ; ...and the claim the glass under it went to
ti_mbup:    db 0                    ; THE MULLIGAN OFFER is on the glass
ti_mbx:     dw 0                    ; ...and its box, the same shape
ti_mby:     dw 0
ti_mbh:     dw 0
ti_mbseg:   dw 0
ti_fwbuf:   times TI_FW_COLS + 4 db 0
