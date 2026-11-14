; wasetup.inc - the opening window: the MATCH SETUP (docs/plans/
; WIREARENA-NET-PLAN.md 2, wave N1). It replaces the list of every key the
; game knows, which is now behind Keys.
;
; Rows of text (walink.inc's wa_lkrows: built, compared, drawn with
; font_run only where they changed): row 0 what the link is doing, rows 2
; to 6 the settings - Arena, Bots, Skill, Width, Play - each a value
; between arrows, changed by a click on an arrow or Left / Right on the
; focused row (Up / Down move the focus), rows 8, 9 and 11 the players once
; linked. Two os88ui buttons under them: Play (alone) or Ready, and Keys.
; A joined player's arena, bots and skill are the host's: changing one
; says so (wa_t_host).

WS_FIRST    equ 2               ; the settings' rows
WS_LAST     equ 6
WS_BTNY     equ 6 + 7 * 10 + 2  ; the buttons' row, from the content's top:
                                ; under the settings (rows 7 and 8 kept
                                ; blank), the players after them - all of it
                                ; above a CGA's dock
WS_BTNW     equ 104
WS_BTNH     equ 16

; wa_sinit - the window is open: the settings' first focus, the buttons
wa_sinit:
    mov byte [wa_sfoc], WS_FIRST
    mov ax, [wa_win]
    mov bx, wa_sbrec
    mov dx, wa_sclick
    call os88ui_btninit
    ret

; wa_sline - BP = a row of the setup: its text at DI (wa_lkln, blank)
wa_sline:
    cmp bp, WS_LAST
    ja .out
    mov al, ' '                 ; the focus: a marker, and the row inverted
    cmp bp, [wa_sfoc]           ; (wa_lkput reads it)
    jne .m
    mov al, '>'                 ; (the font has no triangles)
.m:
    stosb
    inc di
    mov bx, bp
    sub bx, WS_FIRST
    shl bx, 1
    mov si, [wa_snames+bx]
    call wa_lkcpy
    mov di, wa_lkln+11
    mov al, '<'
    stosb
    inc di
    push bx
    call [wa_svals+bx]          ; the value's text, at DI
    pop bx
    mov di, wa_lkln+27
    mov al, '>'
    stosb
    cmp bx, 3 * 2               ; (arena, bots, skill: a guest sees the
    jae .out                    ; host's)
    call wa_lklinked
    jz .out
    call wa_lkhost
    jnz .out
    mov di, wa_lkln+29
    mov si, wa_lt_host
    jmp wa_lkcpy
.out:
    ret

wa_snames:  dw wa_sn_a, wa_sn_b, wa_sn_s, wa_sn_w, wa_sn_p
wa_svals:   dw wa_sv_a, wa_sv_b, wa_sv_s, wa_sv_w, wa_sv_p
wa_sn_a:    db 'Arena', 0
wa_sn_b:    db 'Bots', 0
wa_sn_s:    db 'Skill', 0
wa_sn_w:    db 'Width', 0
wa_sn_p:    db 'Play', 0

wa_sv_a:
    mov bl, [wa_lkarena]
    xor bh, bh
    shl bx, 1
    mov si, [wa_lt_anames+bx]
    jmp wa_lkcpy
wa_sv_b:
    mov al, [wa_lkbots]
    add al, '0'
    stosb
    ret
wa_sv_s:
    mov bl, [wa_lkdiff]
    xor bh, bh
    shl bx, 1
    mov si, [wa_lt_dnames+bx]
    jmp wa_lkcpy
wa_sv_w:
    mov si, wa_sw_40
    cmp byte [wa_want], 0
    jne .c
    mov si, wa_sw_80
.c:
    jmp wa_lkcpy
wa_sv_p:
    mov bl, [wa_splay]
    xor bh, bh
    shl bx, 1
    mov si, [wa_sp_names+bx]
    jmp wa_lkcpy

wa_sw_40:       db '40 columns', 0
wa_sw_80:       db '80 columns', 0
wa_sp_names:    dw wa_sp_0, wa_sp_1, wa_sp_2
wa_sp_0:        db 'alone', 0
wa_sp_1:        db 'serial cable', 0
wa_sp_2:        db 'Ethernet', 0

; wa_sset - AL = the setting's row, AH = -1 or +1: it changes
wa_sset:
    mov byte [wa_lkfull], 1
    cmp al, WS_FIRST + 3
    jae .mine
    call wa_lklinked            ; (a joined player: the host's)
    jz .mine
    call wa_lkhost
    jnz .mine
    push ds
    pop es
    mov si, wa_t_host
    xor cx, cx
    call OSAPI_TOAST
    ret
.mine:
    sub al, WS_FIRST
    mov bl, al
    xor bh, bh
    shl bx, 1
    jmp [wa_ssets+bx]
wa_ssets:   dw .arena, .bots, .skill, .width, .play
.arena:
    mov bx, wa_lkarena
    mov cl, WA_NARENA
    jmp .wrap
.bots:
    mov bx, wa_lkbots
    mov cl, WA_NFIG + 1         ; alone: 0..3; linked: two at most (LINK-
    cmp byte [wa_splay], 0      ; PLAN 8: four in all, two of them players)
    je .wrap
    mov cl, 3
    jmp .wrap
.skill:
    mov bx, wa_lkdiff
    mov cl, 3
    call .wrap
    mov al, [wa_lkdiff]
    mov [wa_diff], al
    ret
.width:
    xor byte [wa_want], 1
    ret
.play:
    mov bx, wa_splay
    mov cl, 3
    call .wrap
    mov al, [wa_splay]          ; ALONE: neither carrier; SERIAL: the
    or al, al                   ; cable's search; ETHERNET: the card
    jnz .linked
    call wa_lkcable
    jmp lk_disconnect
.linked:
    cmp byte [wa_lkbots], 2     ; (linked: two bots at most)
    jbe .b
    mov byte [wa_lkbots], 2
.b:
    cmp al, 1
    jne wa_lknetgo
    call wa_lkcable
    call lk_disconnect
    call lk_auto
    mov word [lk_blk+LK_MSG], lk_m_search
    ret
.wrap:                          ; [BX] += AH, within 0..CL-1, round
    mov al, [bx]
    add al, ah
    jns .lo
    mov al, cl
    dec al
.lo:
    cmp al, cl
    jb .ok
    xor al, al
.ok:
    mov [bx], al
    ret

; wa_sstart - Play (alone: the arena now) or Ready (linked)
wa_sstart:
    cmp byte [wa_splay], 0
    jne wa_lkready
    mov al, [wa_lkarena]
    mov [wa_arena], al
    mov al, [wa_lkdiff]
    mov [wa_diff], al
    mov al, [wa_lkbots]
    mov [wa_lknb], al
    call wa_loadarena
    jc .out
    mov ax, wa_main
    mov bx, [wa_win]
    xor cx, cx
    call OSAPI_FSX_RUN
    mov byte [wa_lkfull], 1
.out:
    ret

; wa_skeys - Keys / Back: the key list in the rows, or the setup again
wa_skeys:
    xor byte [wa_keysv], 1
    mov byte [wa_lkfull], 1
    ret

; wa_skey - ONKEY's: Up / Down the focus, Left / Right the value, Enter
; the first button, K the second. AL = ASCII, AH = scan; CF = 1 taken
wa_skey:
    cmp byte [wa_keysv], 0      ; (the key list: any key back)
    je .set
    call wa_skeys
    stc
    ret
.set:
    cmp ah, 0x48
    je .up
    cmp ah, 0x50
    je .down
    cmp ah, 0x4B
    je .left
    cmp ah, 0x4D
    je .right
    cmp al, 13
    je .enter
    mov ah, al
    or ah, 0x20
    cmp ah, 'k'
    je .keys
    clc
    ret
.up:
    cmp byte [wa_sfoc], WS_FIRST
    je .done
    dec byte [wa_sfoc]
    jmp .moved
.down:
    cmp byte [wa_sfoc], WS_LAST
    je .done
    inc byte [wa_sfoc]
.moved:
    mov byte [wa_lkfull], 1
    jmp .done
.left:
    mov ah, -1
    jmp .chg
.right:
    mov ah, 1
.chg:
    mov al, [wa_sfoc]
    call wa_sset
    jmp .done
.enter:
    call wa_sstart
    jmp .done
.keys:
    call wa_skeys
.done:
    stc
    ret

; wa_sclick - a press in the content not on a button (os88ui chains it):
; CX = x, DX = y. On a setting's row: the focus there, and its left arrow's
; half takes it back, the right's on. The key list: back to the setup
wa_sclick:
    cmp byte [wa_keysv], 0
    je .set
    push si
    call wa_skeys
    pop si
    ret
.set:
    push si
    push cx                     ; (x)
    push dx                     ; (y)
    mov bx, [wa_win]
    call OSAPI_WM_CONTENT       ; AX = left, DX = top
    pop cx
    sub cx, dx                  ; CX = y in the content
    pop dx
    sub dx, ax                  ; DX = x in the content
    sub cx, 6
    jb .done
    mov ax, cx
    mov cl, 10
    div cl                      ; AL = the row
    cmp al, WS_FIRST
    jb .done
    cmp al, WS_LAST
    ja .done
    mov [wa_sfoc], al
    mov byte [wa_lkfull], 1
    sub dx, 8
    jb .done
    shr dx, 1
    shr dx, 1
    shr dx, 1                   ; DX = the column: left of the value's
    mov ah, -1                  ; middle back, right of it on
    cmp dx, 19
    jb .chg
    mov ah, 1
.chg:
    call wa_sset
.done:
    pop si
    ret

; wa_sbtnup - ONMOUSEUP: a button fired (os88ui_btnup)
wa_sbtnup:
    push si
    mov bx, wa_sbrec
    call os88ui_btnup           ; AX = the button + 1, or 0
    cmp ax, 1
    jne .k
    call wa_sstart
    jmp .out
.k:
    cmp ax, 2
    jne .out
    call wa_skeys
.out:
    pop si
    ret

; wa_sbtndrag - ONDRAG
wa_sbtndrag:
    mov bx, wa_sbrec
    jmp os88ui_btndrag

; wa_splace - OS88UI_BT_PLACE: the two buttons' rects from where the
; window is now. Draws nothing, keeps every register
wa_splace:
    push ax
    push bx
    push dx
    mov bx, [wa_win]
    call OSAPI_WM_CONTENT       ; AX = left, DX = top
    add ax, 8
    add dx, WS_BTNY
    mov [wa_sbrects], ax
    mov [wa_sbrects+2], dx
    add ax, WS_BTNW - 1
    mov [wa_sbrects+4], ax
    add dx, WS_BTNH - 1
    mov [wa_sbrects+6], dx
    add ax, 17
    mov [wa_sbrects+8], ax
    sub dx, WS_BTNH - 1
    mov [wa_sbrects+10], dx
    add ax, WS_BTNW - 1
    mov [wa_sbrects+12], ax
    add dx, WS_BTNH - 1
    mov [wa_sbrects+14], dx
    pop dx
    pop bx
    pop ax
    ret

; wa_sbtns - the buttons, their labels as things stand, drawn (the lock
; held); DX nonzero only when a label changed or after a paint
wa_sbtns:
    mov si, wa_sb_play          ; the first: Play alone, else Ready / Not
    cmp byte [wa_splay], 0      ; ready
    je .l1
    mov si, wa_sb_rdy
    cmp byte [wa_lkst], 0
    je .l1
    mov si, wa_sb_nrdy
.l1:
    mov di, wa_sb_keys
    cmp byte [wa_keysv], 0
    je .l2
    mov di, wa_sb_back
.l2:
    cmp byte [wa_lkfull], 0     ; (a full pass, or a label changed: draw)
    jne .draw
    cmp si, [wa_sblab]
    jne .draw
    cmp di, [wa_sblab+2]
    je .out
.draw:
    mov [wa_sblab], si
    mov [wa_sblab+2], di
    mov word [wa_sbrec+OS88UI_BT_N], 0 ; (the key list fills the rows: no
    cmp byte [wa_keysv], 0      ; buttons, a key or a click goes back)
    jne .out
    mov word [wa_sbrec+OS88UI_BT_N], 2
    call wa_splace
    mov bx, wa_sbrec
    mov al, 1
    call os88ui_btn
    mov al, 2
    call os88ui_btn
.out:
    ret

wa_sb_play:     db 'Play', 0
wa_sb_rdy:      db 'Ready', 0
wa_sb_nrdy:     db 'Not ready', 0
wa_sb_keys:     db 'Keys', 0
wa_sb_back:     db 'Back', 0
wa_sbflags:     dw OS88UI_FILL, OS88UI_FILL
    OS88UI_BTNREC wa_sbrec, wa_sbrects, wa_sblab, wa_sbflags, 2, wa_splace
