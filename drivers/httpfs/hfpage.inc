; =============================================================================
; hfpage.inc - HTTPFS.DRV's Control Panel page and its remembered address
; (SPEC.md 120.5)
;
;     HTTP Drive
;     Address
;     [http://10.0.0.2:8088/________]
;     [ Mount ]  [Unmount]
;     Drive E:  70 entries
;     <the last failure, in words>
;
; ONE FIELD, so it always has the caret: there is nothing else on the page a
; key could be for. Enter is Mount. A page draws unclipped and must repaint
; what it changes (SPEC.md 31.9), so every handler here redraws exactly the
; field, a button or the two status lines - never the whole pane on a key.
;
; MOUNT FETCHES NOW, where a drive mounted at boot fetches when it is first
; opened: a user who has just typed an address wants to know at once whether
; the server answers, and the status line is where they are looking.
;
; NOTHING REACHES A DISK ON A CLICK (SPEC.md 31.8). Mount and Unmount mark
; [hf_dirty] and DSV_CPCLOSE writes HTTPDRV.CFG - ETHER.CFG's shape exactly
; (drivers/ether/ethcfg.inc), at the boot volume's root.
; =============================================================================

HP_LX       equ 2
HP_HY       equ 4               ; the heading
HP_AY       equ 20              ; 'Address'
HP_FY       equ 32              ; the field...
HP_FH       equ 13              ; ...and its last row, inclusive
HP_FX2      equ 218
HP_BY       equ 54              ; the buttons
HP_BH       equ 16
HP_BW       equ 68
HP_B2X      equ 76
HP_S1Y      equ 80              ; the two status lines
HP_S2Y      equ 92
HP_HINTY    equ 108
HP_COLS     equ 27              ; a line is padded to the pane: font_run is
                                ; opaque, so a shorter string than last time
                                ; leaves no tail (SPEC.md 31.9.3)
HP_BMOUNT   equ 1               ; the press's token, os88ui_arm's
HP_BUNMNT   equ 2

; -----------------------------------------------------------------------------
; DSV_CPPAINT - DI = pane left, DX = pane top
; -----------------------------------------------------------------------------
hf_cp_paint:
    call os88_ent
    mov [hf_px], di
    mov [hf_py], dx
    mov si, hf_name
    mov bx, HP_HY
    call hp_lab
    mov si, hp_s_addr
    mov bx, HP_AY
    call hp_lab
    mov si, hp_s_hint
    mov bx, HP_HINTY
    call hp_lab
    call hp_field
    call hp_btns
    call hp_status
    jmp os88_r_bp

; --- hp_field - the field's rect from the pane, synced, drawn ---------------
hp_field:
    push ax
    push si
    mov si, hf_lnb
    mov ax, [hf_px]
    add ax, HP_LX
    mov [si+LN_X1], ax
    mov ax, [hf_px]
    add ax, HP_FX2
    mov [si+LN_X2], ax
    mov ax, [hf_py]
    add ax, HP_FY
    mov [si+LN_Y1], ax
    add ax, HP_FH
    mov [si+LN_Y2], ax
    mov word [si+LN_BUF], hf_url
    mov word [si+LN_MAX], HF_URLMAX
    cmp byte [hf_lsync], 0
    jne .drawn
    call os88line_resync        ; the buffer was filled behind its back: by
    mov byte [hf_lsync], 1      ; the settings file, or a package's MOUNT
.drawn:
    mov byte [si+LN_FOCUS], 1
    call hp_fdraw
    pop si
    pop ax
    ret

; --- hp_fdraw - SI = the field: drawn, and SCROLLED HOME whenever the whole
;     address fits - os88line keeps a view a deletion left behind, and an
;     address that fits should never read 'ttp://...'
hp_fdraw:
    push cx
    call os88line_cols          ; CX = the columns the box shows
    cmp [si+LN_LEN], cx
    jae .draw
    mov word [si+LN_VIEW], 0
.draw:
    pop cx
    jmp os88line_draw

; -----------------------------------------------------------------------------
; DSV_CPKEY - BL = ASCII, BH = scan. CF=0 taken, CF=1 not ours
; -----------------------------------------------------------------------------
hf_cp_key:
    call os88_ent
    mov ax, bx                  ; os88line_key takes AL/AH
    mov si, hf_lnb
    call os88line_key
    jc .mine
    call hp_fdraw               ; ...and only the field it changed
    jmp short .took
.mine:
    cmp al, 13
    jne .no
    call hp_mount               ; Enter is Mount
.took:
    clc
    jmp os88_r_bp
.no:
    stc
    jmp os88_r_bp

; -----------------------------------------------------------------------------
; DSV_CPCLICK - CX = pane x, BX = pane y. The field takes a click at once;
; a button only ARMS and draws pressed, and fires on the release (13.8.4)
; -----------------------------------------------------------------------------
hf_cp_click:
    call os88_ent
    mov [hf_px], di
    mov [hf_py], dx
    push cx
    push bx
    add cx, [hf_px]
    mov dx, bx
    add dx, [hf_py]
    mov si, hf_lnb
    call os88line_click
    pop bx
    pop cx
    jc .btn
    call hp_fdraw
    jmp short .out
.btn:
    call hp_bhit
    jc .out
    cmp al, HP_BUNMNT
    jne .arm
    cmp byte [hf_vol], 0xFF
    je .out                     ; greyed: the same predicate the paint reads
.arm:
    xor ah, ah
    call os88ui_arm
    call hp_setdown
.out:
    jmp os88_r_bp

; --- DSV_CPDRAG / DSV_CPUP: one body, CF says which (etherui.inc's shape) ---
hf_cp_drag:
    CLC_OR_STC hf_cp_up
hp_ud:
    call os88_ent
    mov [hf_px], di
    mov [hf_py], dx
    mov dl, 1
    jc .fire
    dec dx
    call os88ui_armed           ; a drag peeks
    jmp short .got
.fire:
    call os88ui_fire            ; a release spends it
.got:
    or ax, ax
    jz .out
    mov dh, al
    call hp_bhit
    jc .off
    cmp al, dh
    jne .off
    or dl, dl
    jz .set
    mov byte [hf_down], 0
    call hp_btns                ; upright again before the work starts
    cmp al, HP_BUNMNT
    je .unmount
    call hp_mount
    jmp short .out
.unmount:
    call hf_unmount
    mov byte [hf_dirty], 1
    call hp_btns
    call hp_status
    jmp short .out
.off:
    xor al, al
.set:
    call hp_setdown
.out:
    jmp os88_r_bp

; -----------------------------------------------------------------------------
; hp_mount - the field's address, mounted and fetched, said on the page
; -----------------------------------------------------------------------------
hp_mount:
    push ax
    mov byte [hf_dirty], 1
    mov byte [hf_failed], 0
    mov word [hf_err], 0
    call hf_parse
    jc .fail
    call hf_vadd
    jc .fail
    call hp_btns
    mov word [hf_err], HFE_BUSY ; 'Fetching...' while the wire works
    call hp_status
    call hf_fetch               ; ...which says how it went in [hf_err]
    jmp short .show
.fail:
    mov [hf_err], ax
    mov byte [hf_failed], 1
.show:
    call hp_btns
    call hp_status
    pop ax
    ret

; --- hp_bhit - CX/BX pane-relative -> CF=0, AL = HP_B*. keeps every other ---
hp_bhit:
    push bx
    push cx
    push dx
    call hp_brects
    mov dx, bx
    add dx, [hf_py]
    add cx, [hf_px]
    mov bx, hf_brect
    mov al, HP_BMOUNT
.t:
    call os88ui_bhit
    jnc .out
    add bx, 8
    inc al
    cmp al, HP_BUNMNT
    jbe .t
    stc
.out:
    pop dx
    pop cx
    pop bx
    ret

; --- hp_brects - both buttons' screen rects, from [hf_px]/[hf_py] ----------
hp_brects:
    push ax
    push bx
    push dx
    mov bx, hf_brect
    mov dx, [hf_py]
    add dx, HP_BY
    mov ax, [hf_px]
    add ax, HP_LX
    call .one
    mov ax, [hf_px]
    add ax, HP_B2X
    call .one
    pop dx
    pop bx
    pop ax
    ret
.one:
    mov [bx], ax
    mov [bx+2], dx
    add ax, HP_BW - 1
    mov [bx+4], ax
    push dx
    add dx, HP_BH - 1
    mov [bx+6], dx
    pop dx
    add bx, 8
    ret

hp_setdown:
    cmp al, [hf_down]
    je .out
    mov [hf_down], al
    call hp_btns
.out:
    ret

; --- hp_btns - both, in the state they are in -------------------------------
hp_btns:
    push ax
    push bx
    call hp_brects
    mov ax, OS88UI_FILL
    cmp byte [hf_down], HP_BMOUNT
    jne .m
    or ax, OS88UI_DOWN
.m:
    mov [hf_bflg], ax
    mov ax, OS88UI_FILL
    cmp byte [hf_vol], 0xFF     ; DISABLED IS A FACT: no drive, nothing to
    jne .u                      ; unmount (SPEC.md 47 rule 3)
    or ax, OS88UI_DIS
    jmp short .uset
.u:
    cmp byte [hf_down], HP_BUNMNT
    jne .uset
    or ax, OS88UI_DOWN
.uset:
    mov [hf_bflg+2], ax
    mov bx, hf_brec
    mov word [bx+OS88UI_BT_N], 2    ; both live, always
    mov al, HP_BMOUNT
    call os88ui_btn
    mov al, HP_BUNMNT
    call os88ui_btn
    pop bx
    pop ax
    ret

hf_brec:    dw hf_brect, hf_blbl, hf_bflg, 0
            times OS88UI_BT_SIZE - 8 db 0
hf_blbl:    dw hp_s_mount, hp_s_unmnt

; -----------------------------------------------------------------------------
; hp_status - the two lines: where the drive is and what it holds, and the
;             last failure in words
; -----------------------------------------------------------------------------
hp_status:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    mov di, hf_sbuf             ; --- line 1 -----------------------------------
    mov si, hp_s_none
    mov al, [hf_vol]
    cmp al, 0xFF
    je .l1
    mov si, hp_s_drive          ; 'Drive '
    call hf_scpy                ; (lodsb: AL is spent, so read it again)
    mov al, [hf_vol]
    add al, 'A'
    stosb
    mov al, ':'
    stosb
    mov si, hp_s_lazy
    cmp word [hf_iseg], 0
    je .l1
    mov ax, ' '
    stosb
    stosb
    mov ax, [hf_nrec]
    dec ax                      ; the root is not an entry
    xor dx, dx
    call hf_ultoa
    mov si, hp_s_ents
.l1:
    call hf_scpy
    mov bx, HP_S1Y
    call hp_padrun
    mov di, hf_sbuf             ; --- line 2 -----------------------------------
    mov bx, [hf_err]
    or bx, bx
    jz .l2
    cmp bx, HFE_MAXMSG
    ja .l2
    shl bx, 1
    mov si, [hp_msgs+bx-2]
    call hf_scpy
    cmp word [hf_err], HFE_STATUS
    jne .l2
    mov ax, [hf_status]
    xor dx, dx
    call hf_ultoa
.l2:
    mov bx, HP_S2Y
    call hp_padrun
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- hp_padrun - [hf_sbuf] up to DI, padded to HP_COLS, drawn at row BX ----
hp_padrun:
    mov al, ' '
.p:
    cmp di, hf_sbuf + HP_COLS
    jae .z
    stosb
    jmp short .p
.z:
    mov byte [di], 0
    mov si, hf_sbuf
                                ; ...and falls into hp_lab
hp_lab:                         ; SI = a string, BX = its y in the pane
    push ax
    push cx
    push dx
    mov cx, [hf_px]
    add cx, HP_LX
    mov dx, [hf_py]
    add dx, bx
    mov ax, (CWHITE << 8) | CBLACK
    call OSAPI_FONT_RUN
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; DSV_CPCLOSE - write HTTPDRV.CFG if a Mount or Unmount changed it. SILENT
; about failing, ethcfg.inc's reason: the panel is gone and what was asked
; for - a drive - already happened
; -----------------------------------------------------------------------------
hf_cp_close:
    call os88_ent
    push es
    mov byte [hf_down], 0
    cmp byte [hf_dirty], 0
    je .out
    mov byte [hf_dirty], 0
    mov word [hf_cfg], HF_CFMAGIC
    mov byte [hf_cfg+2], HF_CFVER
    xor al, al
    cmp byte [hf_vol], 0xFF
    je .fl
    inc ax                      ; bit 0: mount it at the next boot
.fl:
    mov [hf_cfg+3], al
    call hp_fargs
    jc .back
    call OSAPI_FILE_WRITE
.back:
    call hp_vback
.out:
    pop es
    jmp os88_r_bp

; -----------------------------------------------------------------------------
; hf_cfg_load - HTTPDRV.CFG, if there is one (DRVV_READY). out: CF=0 and the
;               address is in [hf_url], AL = its flags; CF=1 none
; -----------------------------------------------------------------------------
hf_cfg_load:
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call hp_fargs
    jc .back
    call OSAPI_FILE_READ
    pushf
    call hp_vback
    popf
    jc .no
    cmp word [hf_cfg], HF_CFMAGIC
    jne .no
    cmp byte [hf_cfg+2], HF_CFVER
    jne .no
    mov byte [hf_url + HF_URLMAX - 1], 0    ; hostile: terminated, whatever
    mov al, [hf_cfg+3]
    clc
    jmp short .out
.back:
    call hp_vback
.no:
    mov byte [hf_url], 0        ; a refused read may have left half of it
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; --- hp_fargs - stand on the boot volume's root (QUIETLY, ethcfg.inc's rule)
;     and load a read or write: ES:BX = the record, SI = the name, DX:CX = its
;     size. CF=1 = we could not get there and nothing was moved
hp_fargs:
    call OSAPI_FILE_HERE        ; DX = our cluster, BL = our drive
    mov [hf_bdrv], bl
    mov [hf_bclus], dx
    call OSAPI_VOL_SYS          ; BL = the volume we booted from
    xor dx, dx
    call OSAPI_FILE_GOTO_Q      ; CF=1: nothing moved
    push ds
    pop es
    mov si, hp_s_file
    mov bx, hf_cfg
    mov cx, HF_CFSIZE
    mov dx, 0                   ; NOT xor: CF is the answer
    ret

hp_vback:
    push ax
    push bx
    push dx
    pushf
    mov bl, [hf_bdrv]
    mov dx, [hf_bclus]
    call OSAPI_FILE_GOTO_Q
    popf
    pop dx
    pop bx
    pop ax
    ret

HF_CFMAGIC  equ 'HD'
HF_CFVER    equ 1
HF_CFSIZE   equ 4 + HF_URLMAX   ; magic, version, flags, then the address
HFE_BUSY    equ 11              ; the page's own: 'Fetching...' (not an error)
HFE_MAXMSG  equ 11

hp_s_file:  db 'HTTPDRV.CFG', 0
hp_s_addr:  db 'Address', 0
hp_s_hint:  db 'e.g. http://10.0.0.2:8088/', 0
hp_s_mount: db 'Mount', 0
hp_s_unmnt: db 'Unmount', 0
hp_s_none:  db 'Not mounted', 0
hp_s_drive: db 'Drive ', 0
hp_s_lazy:  db '  not read yet', 0
hp_s_ents:  db ' entries', 0
hp_msgs:    dw hp_e1, hp_e2, hp_e3, hp_e4, hp_e5, hp_e6, hp_e7, hp_e8
            dw hp_e9, hp_e10, hp_e11
%if ($ - hp_msgs) / 2 != HFE_MAXMSG
  %error "hfpage: one message per HFE_*, 1..HFE_MAXMSG"
%endif
hp_e1:      db 'Not an http:// address', 0
hp_e2:      db 'No network driver or link', 0
hp_e3:      db 'Could not connect', 0
hp_e4:      db 'No answer (timed out)', 0
hp_e5:      db 'Server answered ', 0
hp_e6:      db 'No OS88.IDX index there', 0
hp_e7:      db 'Transfer cut short', 0
hp_e8:      db 'Not enough memory', 0
hp_e9:      db 'No drive letter free', 0
hp_e10:     db 'Not understood', 0
hp_e11:     db 'Fetching...', 0
