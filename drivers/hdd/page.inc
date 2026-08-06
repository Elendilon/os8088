; =============================================================================
; os8088 - HDD.DRV / page.inc
;
; The Control Panel's Hard Drive page (SPEC.md 52.4), and the small helpers
; the rest of the driver shares.
;
; The page exists exactly while this driver is attached, which is not arranged
; anywhere: it falls out of the kernel clearing the DISK class's publication
; slot at detach (SPEC.md 31.9/51.2.1).
;
; The pane is 221 x 121 px - 27 characters by 13 rows - and the panel is not
; resizable, so this page is a list, an editor and three buttons, and anything
; that needs more room is a window of its own.
;
;   Hard Drive
;    IDE0  980x 10x 17   81M      <- one row per probed device, the selected
;    BIOS  615x  4x 17   20M         one drawn as a black bar
;   C[ 980] H[ 10] S[ 17]  - +    <- the geometry, editable when the probe
;   [Partition] [Format] [Mount]     could not determine it
;   Mounted as C:                 <- and the caption is where the truth goes
;
; **EVERY STRING HERE FITS ITS BOX, and that is a rule and not a habit.** The
; caption column is 27 characters (221px of pane, text at x=2) and a row is
; 26; font_str clips to the SCREEN and not to the pane (SPEC.md 5), so a
; longer one does not stop at the edge - it paints over the panel's border and
; out the other side. Two captions did.
;
; GREYING FOLLOWS SPEC.md 47: one predicate per control, shared by the
; greying, the click refusal and the explanation; a fact and never a guess;
; and the whole control, not just its caption. There is no gfx_pen_cf in the
; package ABI, so a disabled button is drawn in CDGRAY and its click refuses
; - and the caption says why, which is the half that matters.
; =============================================================================

HDP_HY       equ 4              ; the heading's text row
HDP_R0Y      equ 17             ; the first device row
HDP_ROWH     equ 11
HDP_LX       equ 2
HDP_EY       equ 63             ; the C/H/S editor's row
HDP_FH       equ 11
HDP_F0X      equ 10             ; the three field boxes
HDP_F1X      equ 66
HDP_F2X      equ 114
HDP_FW       equ 38
HDP_MX       equ 158            ; '-' and '+'
HDP_PX       equ 186
HDP_BTW      equ 24
HDP_BY       equ 82             ; the button row
HDP_BH       equ 16
HDP_B0X      equ 2              ; 'Partition'
HDP_B1X      equ 84             ; 'Format'
HDP_B2X      equ 146            ; 'Mount' / 'Unmount'
HDP_BW0      equ 80
HDP_BW1      equ 56
HDP_BW2      equ 72
HDP_CAPY     equ 104

; -----------------------------------------------------------------------------
; hd_page_paint - DSV_CPPAINT
; in:  DI = pane left, DX = pane top; the pane is white-filled and the gfx
;      lock is HELD (SPEC.md 31.9)
; out: nothing
; clobbers: whatever it likes - it is a callback
; -----------------------------------------------------------------------------
hd_page_paint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov bp, dx                  ; BP = pane top for the rest of the routine

    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov si, hd_s_page
    mov cx, di
    add cx, HDP_LX
    mov dx, bp
    add dx, HDP_HY
    call OSAPI_FONT_STR

    ; --- one row per probed device -------------------------------------------
    xor cl, cl
.row:
    cmp cl, [hd_ndev]
    jae .rows_done
    push cx
    mov [hd_rowslot], cl
    mov al, cl
    call hd_dev_line            ; hd_line = 'IDE0  980x 10x 17   81M'
    mov al, [hd_rowslot]
    mov ah, HDP_ROWH
    mul ah
    add ax, HDP_R0Y
    mov dx, bp
    add dx, ax                  ; DX = the row's text y
    mov al, [hd_rowslot]
    cmp al, [hd_sel]
    jne .plain
    push dx
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, di
    add ax, HDP_LX - 1
    pop dx
    push dx
    mov bx, dx
    dec bx
    mov cx, di
    add cx, 214
    mov dx, bx
    add dx, 9
    call OSAPI_GFX_FILL
    pop dx
    mov al, CWHITE
    call OSAPI_SET_COLOR
    jmp short .text
.plain:
    mov al, CBLACK
    call OSAPI_SET_COLOR
.text:
    mov si, hd_line
    mov cx, di
    add cx, HDP_LX
    call OSAPI_FONT_STR
    pop cx
    inc cl
    jmp short .row
.rows_done:
    cmp byte [hd_ndev], 0
    jne .geom
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov si, hd_s_nodev
    mov cx, di
    add cx, HDP_LX
    mov dx, bp
    add dx, HDP_R0Y
    call OSAPI_FONT_STR

    ; --- the C/H/S editor ----------------------------------------------------
.geom:
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov si, hd_s_c
    mov cx, di
    add cx, HDP_LX
    mov dx, bp
    add dx, HDP_EY + 2
    call OSAPI_FONT_STR
    mov si, hd_s_h
    mov cx, di
    add cx, HDP_F1X - 10
    call OSAPI_FONT_STR
    mov si, hd_s_s
    mov cx, di
    add cx, HDP_F2X - 10
    call OSAPI_FONT_STR

    mov byte [hd_fldi], 0
.field:
    mov al, [hd_fldi]
    call hd_page_fieldx         ; AX = the box's pane-relative x
    mov [hd_fldx], ax
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, di
    add ax, [hd_fldx]
    mov cx, ax
    add cx, HDP_FW - 1
    mov bx, bp
    add bx, HDP_EY
    mov dx, bx
    add dx, HDP_FH - 1
    call OSAPI_GFX_FRAME
    mov al, [hd_fldi]
    cmp al, [hd_field]
    jne .fvalue
    mov ax, di                  ; the selected field: a second frame just
    add ax, [hd_fldx]           ; inside the first, which is how the
    inc ax                      ; Date/Time page says "this one"
    mov cx, ax
    add cx, HDP_FW - 3
    mov bx, bp
    add bx, HDP_EY + 1
    mov dx, bx
    add dx, HDP_FH - 3
    call OSAPI_GFX_FRAME
.fvalue:
    mov al, [hd_fldi]
    call hd_page_fieldv         ; AX = the value
    push di
    mov di, hd_line
    call hd_utoa
    mov byte [di], 0
    pop di
    mov si, hd_line
    call OSAPI_FONT_WIDTH       ; right-aligned in the box, so a 3-digit and
    mov cx, di                  ; a 4-digit value read as the same field
    add cx, [hd_fldx]
    add cx, HDP_FW - 4
    sub cx, ax
    mov dx, bp
    add dx, HDP_EY + 2
    mov si, hd_line
    call OSAPI_FONT_STR
    inc byte [hd_fldi]
    cmp byte [hd_fldi], 3
    jb .field

    ; --- the +/- pair ---------------------------------------------------------
    mov si, hd_s_minus
    mov ax, HDP_MX
    call hd_page_pm
    mov si, hd_s_plus
    mov ax, HDP_PX
    call hd_page_pm

    ; --- the three buttons ----------------------------------------------------
    mov si, hd_s_part
    mov ax, HDP_B0X
    mov bx, HDP_BW0
    mov cl, 0
    call hd_page_button
    mov si, hd_s_format
    mov ax, HDP_B1X
    mov bx, HDP_BW1
    mov cl, 1
    call hd_page_button
    mov si, hd_s_mount
    call hd_mounted
    jc .mlabel
    mov si, hd_s_unmount
.mlabel:
    mov ax, HDP_B2X
    mov bx, HDP_BW2
    mov cl, 2
    call hd_page_button

    ; --- and the caption, which is where the truth goes ----------------------
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov si, [hd_msg]
    mov cx, di
    add cx, HDP_LX
    mov dx, bp
    add dx, HDP_CAPY
    call OSAPI_FONT_STR

    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_page_button - one framed button, greyed when its predicate says no
; in:  AX = x, BX = width (pane-relative), SI = label, CL = which button,
;      DI = pane left, BP = pane top
; out: nothing (all registers preserved)
;
; ONE PREDICATE, shared with the click and the caption (SPEC.md 47): the pen
; comes from hd_btn_ok and so does the refusal, so a greyed button can never
; be one that would have worked.
; -----------------------------------------------------------------------------
hd_page_button:
    push ax
    push bx
    push cx
    push dx
    push si
    push ax
    push bx
    push si
    mov al, cl
    call hd_btn_ok              ; CF = 1 = this control is disabled
    mov al, CBLACK
    jnc .pen
    mov al, CDGRAY              ; the disabled pen - and it colours the FRAME
.pen:                           ; as well as the label, because greying half
    call OSAPI_SET_COLOR        ; a control is worse than not greying it
    pop si
    pop bx
    pop ax
    add ax, di
    mov cx, ax
    add cx, bx
    dec cx
    mov bx, bp
    add bx, HDP_BY
    mov dx, bx
    add dx, HDP_BH - 1
    push ax
    push bx
    push cx
    push dx
    call OSAPI_GFX_FRAME
    pop dx
    pop cx
    pop bx
    pop ax
    add ax, 4
    mov cx, ax
    mov dx, bx
    add dx, 4
    call OSAPI_FONT_STR
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_page_pm - one of the two adjust buttons (module internal)
; in:  AX = x, SI = its label, DI/BP = the pane origin
; -----------------------------------------------------------------------------
hd_page_pm:
    push ax
    push bx
    push cx
    push dx
    push si
    add ax, di
    mov cx, ax
    add cx, HDP_BTW - 1
    mov bx, bp
    add bx, HDP_EY - 1
    mov dx, bx
    add dx, HDP_FH + 1
    push ax
    push bx
    push cx
    push dx
    mov al, CBLACK
    call OSAPI_SET_COLOR
    pop dx
    pop cx
    pop bx
    pop ax
    push ax
    push bx
    push cx
    push dx
    call OSAPI_GFX_FRAME
    pop dx
    pop cx
    pop bx
    pop ax
    add ax, HDP_BTW/2 - 4
    mov cx, ax
    mov dx, bx
    add dx, 3
    call OSAPI_FONT_STR
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_btn_ok - may this button be clicked? (module internal)
; in:  AL = 0 Partition / 1 Format / 2 Mount
; out: CF = 0 yes, CF = 1 = disabled
; clobbers: flags
;
; A FACT and never a guess (SPEC.md 47 rule 4): every test here is something
; already known - is there a device, is its geometry usable, is it already
; mounted - and none of them is "try it and see".
; -----------------------------------------------------------------------------
hd_btn_ok:
    push bx
    push di
    cmp byte [hd_ndev], 0
    je .no
    push ax
    mov al, [hd_sel]
    call hd_dev_row
    call hd_geom_ok
    pop ax
    jc .no                      ; no usable geometry: nothing may be written
    cmp al, 2
    jne .yes                    ; Partition and Format need nothing more
    pop di
    pop bx
    clc
    ret                         ; Mount is live either way - it becomes
                                ; Unmount when this device already has a
                                ; volume, and that is a different ACTION and
                                ; not a disabled one
.yes:
    pop di
    pop bx
    clc
    ret
.no:
    pop di
    pop bx
    stc
    ret

; -----------------------------------------------------------------------------
; hd_mounted - does the selected device already have a mounted volume?
; in:  nothing
; out: CF = 1 no, CF = 0 and BX = the hd_vols row
; clobbers: BX (the output), flags
; -----------------------------------------------------------------------------
hd_mounted:
    push ax
    push cx
    mov cx, HD_MAXVOL
    mov bx, hd_vols
.scan:
    cmp byte [bx+HDV_USED], 0
    je .next
    mov al, [bx+HDV_DEV]
    cmp al, [hd_sel]
    je .yes
.next:
    add bx, HDV_SIZE
    loop .scan
    xor bx, bx
    pop cx
    pop ax
    stc
    ret
.yes:
    pop cx
    pop ax
    clc
    ret

; -----------------------------------------------------------------------------
; hd_page_fieldx / hd_page_fieldv - the C/H/S editor's three fields
; in:  AL = field (0 = cylinders, 1 = heads, 2 = sectors)
; out: hd_page_fieldx: AX = the box's pane-relative x
;      hd_page_fieldv: AX = the selected device's value for it
; clobbers: AX (the output), flags
; -----------------------------------------------------------------------------
hd_page_fieldx:
    cmp al, 1
    je .f1
    ja .f2
    mov ax, HDP_F0X
    ret
.f1:
    mov ax, HDP_F1X
    ret
.f2:
    mov ax, HDP_F2X
    ret

hd_page_fieldv:
    push bx
    push di
    mov bl, al
    mov al, [hd_sel]
    call hd_dev_row
    xor ax, ax
    cmp byte [hd_ndev], 0
    je .out
    cmp bl, 1
    je .v1
    ja .v2
    mov ax, [di+HDD_CYL]
    jmp short .out
.v1:
    mov ax, [di+HDD_HEADS]
    jmp short .out
.v2:
    mov ax, [di+HDD_SPT]
.out:
    pop di
    pop bx
    ret

; -----------------------------------------------------------------------------
; hd_page_adjust - move the selected field by AL (+1 / -1)
; in:  AL = the step, signed
; out: nothing
; clobbers: flags
;
; The bounds are CHS addressing's own: 1..1024 cylinders, 1..255 heads, 1..63
; sectors. A value outside them is not a geometry, so the field simply stops.
; -----------------------------------------------------------------------------
hd_page_adjust:
    push ax
    push bx
    push cx
    push dx
    push di
    cmp byte [hd_ndev], 0
    je .out
    mov cl, al                  ; CL = the step
    mov al, [hd_sel]
    call hd_dev_row
    mov bl, [hd_field]
    mov al, bl
    call hd_page_fieldv         ; AX = the value now
    mov dx, 1024                ; DX = its ceiling
    cmp bl, 1
    jb .have
    mov dx, 255
    je .have
    mov dx, 63
.have:
    cmp cl, 1
    jne .down
    cmp ax, dx
    jae .out
    inc ax
    jmp short .store
.down:
    cmp ax, 2
    jb .out
    dec ax
.store:
    cmp bl, 1
    je .s1
    ja .s2
    mov [di+HDD_CYL], ax
    jmp short .flag
.s1:
    mov [di+HDD_HEADS], ax
    jmp short .flag
.s2:
    mov [di+HDD_SPT], ax
.flag:
    and byte [di+HDD_FLAGS], 0xFE   ; typed in by hand is still KNOWN, as
    call hd_geom_ok                 ; long as it is usable - which is the
    jc .out                         ; whole point of the editor
    or byte [di+HDD_FLAGS], 1
    mov word [hd_msg], hd_s_typed
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_dev_line - one device row's line, into hd_line (module internal)
; in:  AL = the device index
; out: hd_line holds a NUL string
; clobbers: flags
; -----------------------------------------------------------------------------
hd_dev_line:
    push ax
    push bx
    push si
    push di
    mov [hd_rowdev], al
    call hd_dev_row
    mov bx, di                  ; BX = the device row for the whole routine;
    mov di, hd_line             ; DI is the string cursor
    mov si, hd_s_bios
    cmp byte [bx+HDD_KIND], HDK_IDE
    jne .kind
    mov si, hd_s_ide
.kind:
    call hd_scat
    mov al, [bx+HDD_UNIT]       ; the DRIVE, not the row: an int 13h unit is
    and al, 0x7F                ; 80h/81h and an IDE one is 0/1, and neither
    xor ah, ah                  ; is the order we happened to probe them in
    call hd_utoa
    mov si, hd_s_two
    call hd_scat
    push di                     ; hd_geom_ok wants the row in DI
    mov di, bx
    call hd_geom_ok
    pop di
    jc .unknown
    mov ax, [bx+HDD_CYL]
    call hd_utoa4
    mov si, hd_s_x
    call hd_scat
    mov ax, [bx+HDD_HEADS]
    call hd_utoa3
    mov si, hd_s_x
    call hd_scat
    mov ax, [bx+HDD_SPT]
    call hd_utoa3
    mov si, hd_s_two
    call hd_scat
    push di
    mov di, bx
    call hd_dev_mb              ; AX = megabytes
    pop di
    call hd_utoa4
    mov si, hd_s_mb
    call hd_scat
    jmp short .done
.unknown:
    mov si, hd_s_unk
    call hd_scat
.done:
    mov byte [di], 0
    pop di
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_page_click - DSV_CPCLICK
; in:  DI = pane left, DX = pane top, CX = pane-relative x, BX = relative y
;      (the gfx lock is HELD)
; out: nothing
; -----------------------------------------------------------------------------
hd_page_click:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov bp, dx
    mov dx, bx                  ; DX = the relative y, for the tests below
    mov [hd_clx], cx
    mov [hd_cly], dx

    cmp dx, HDP_R0Y - 2
    jl .done
    cmp dx, HDP_EY - 2
    jl .devrow
    cmp dx, HDP_BY - 2
    jl .editor
    cmp dx, HDP_BY + HDP_BH
    jl .buttons
    jmp .done

.devrow:
    mov ax, dx
    sub ax, HDP_R0Y - 2
    mov bl, HDP_ROWH
    div bl
    cmp al, [hd_ndev]
    jae .done
    mov [hd_sel], al
    mov word [hd_msg], hd_s_pick
    jmp .repaint

.editor:
    mov cx, [hd_clx]
    cmp cx, HDP_MX
    jl .pickfield
    cmp cx, HDP_MX + HDP_BTW
    jl .minus
    cmp cx, HDP_PX
    jl .done
    cmp cx, HDP_PX + HDP_BTW
    jge .done
    mov al, 1
    call hd_page_adjust
    jmp .repaint
.minus:
    mov al, 0
    call hd_page_adjust
    jmp .repaint
.pickfield:
    xor bl, bl
.fscan:
    mov al, bl
    call hd_page_fieldx
    cmp cx, ax
    jl .fnext
    add ax, HDP_FW
    cmp cx, ax
    jge .fnext
    mov [hd_field], bl
    jmp .repaint
.fnext:
    inc bl
    cmp bl, 3
    jb .fscan
    jmp .done

.buttons:
    mov cx, [hd_clx]
    xor bl, bl                  ; BL = which button
    cmp cx, HDP_B0X
    jl .done
    cmp cx, HDP_B0X + HDP_BW0
    jl .hit
    mov bl, 1
    cmp cx, HDP_B1X
    jl .done
    cmp cx, HDP_B1X + HDP_BW1
    jl .hit
    mov bl, 2
    cmp cx, HDP_B2X
    jl .done
    cmp cx, HDP_B2X + HDP_BW2
    jge .done
.hit:
    mov al, bl
    call hd_btn_ok
    jc .refused
    cmp bl, 0
    je .dopart
    cmp bl, 1
    je .dofmt
    call hd_mounted
    jc .domount
    call hd_unmount
    jmp .repaint
.domount:
    call hd_mount
    jmp .repaint
.dopart:
    call hd_pw_open
    jmp .repaint
.dofmt:
    call hd_fw_open
    jmp .repaint
.refused:
    ; A greyed control explains itself (SPEC.md 47 rule 5), so the refusal
    ; says nothing new - it just makes sure the reason is on screen.
    mov word [hd_msg], hd_s_nogeom
    cmp byte [hd_ndev], 0
    jne .repaint
    mov word [hd_msg], hd_s_nodev
.repaint:
    call hd_page_repaint
.done:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_page_repaint - erase the pane and draw it again (module internal)
; in:  DI = pane left, BP = pane top; the lock is held
; out: nothing (all registers preserved)
;
; The pane and nothing else: a page draws itself and the kernel does not
; repaint after a click returns (SPEC.md 31.9).
; -----------------------------------------------------------------------------
hd_page_repaint:
    push ax
    push bx
    push cx
    push dx
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov ax, di
    mov bx, bp
    mov cx, di
    add cx, 221
    mov dx, bp
    add dx, 120
    call OSAPI_GFX_FILL
    mov dx, bp
    call hd_page_paint
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; Mounting (SPEC.md 52.4)
; =============================================================================

; -----------------------------------------------------------------------------
; hd_mount - mount the selected device's first FAT partition
; in:  nothing; the gfx lock is HELD (a page click)
; out: nothing; [hd_msg] says what happened
; clobbers: flags
;
; The listing claim comes FIRST and is handed to the kernel with the volume,
; because a mounted volume with no listing buffer lists 32 entries instead of
; DSK_VENT and there is no second chance to say so (SPEC.md 22.6). A refused
; claim is not an error - the volume mounts with the kernel's own floor.
; -----------------------------------------------------------------------------
hd_mount:
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    mov word [hd_msg], hd_s_mnotab
    mov al, [hd_sel]
    call hd_dev_row
    call hd_part_load
    jc .out                     ; no readable table: nothing to mount

    xor cl, cl                  ; find the first FAT partition
.slot:
    mov al, cl
    call hd_part_ent
    call hd_part_used
    jnc .found
    inc cl
    cmp cl, 4
    jb .slot
    jmp .out
.found:
    cmp word [si+HP_SECS+2], 0
    jne .toobig
    call hd_vol_new             ; BX = a free hd_vols row
    jc .full
    mov [bx+HDV_DEV], al
    mov al, [hd_sel]
    mov [bx+HDV_DEV], al
    mov [bx+HDV_PART], cl
    mov ax, [si+HP_LBA]
    mov [bx+HDV_BASE], ax
    mov ax, [si+HP_LBA+2]
    mov [bx+HDV_BASE+2], ax
    mov ax, [si+HP_SECS]
    mov [bx+HDV_SECS], ax

    mov ax, HDD_LISTKB          ; the listing claim (SPEC.md 22.6)
    call OSAPI_MEM_CLAIM
    jnc .claimed
    xor dx, dx                  ; refused: the kernel's 32-entry floor, which
.claimed:                       ; works and shows fewer files
    mov [bx+HDV_LSEG], dx

    mov al, [bx+HDV_VOLH]       ; our own handle IS the row index
    mov cx, [bx+HDV_SECS]
    mov si, hd_s_hddc
    call OSAPI_VOL_ADD          ; out AL = the kernel's volume index
    jc .novol
    mov [bx+HDV_VOL], al
    mov byte [bx+HDV_USED], 1
    call OSAPI_VOL_MOUNT        ; AL is still the volume index
    jc .badvol
    mov word [hd_msg], hd_s_mounted
    jmp short .out
.badvol:
    call hd_unmount_row
    mov word [hd_msg], hd_s_mbad
    jmp short .out
.novol:
    mov dx, [bx+HDV_LSEG]
    or dx, dx
    jz .nofree
    call OSAPI_MEM_FREE
.nofree:
    mov byte [bx+HDV_USED], 0
.full:
    mov word [hd_msg], hd_s_mfull
    jmp short .out
.toobig:
    mov word [hd_msg], hd_s_mbig
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_vol_new - the first free hd_vols row (module internal)
; in:  nothing
; out: CF = 0 and BX = the row, with HDV_VOLH set to its own index;
;      CF = 1 = all of them are in use
; clobbers: BX (the output), flags
; -----------------------------------------------------------------------------
hd_vol_new:
    push ax
    push cx
    mov bx, hd_vols
    xor al, al
    mov cx, HD_MAXVOL
.scan:
    cmp byte [bx+HDV_USED], 0
    je .free
    add bx, HDV_SIZE
    inc al
    loop .scan
    xor bx, bx
    pop cx
    pop ax
    stc
    ret
.free:
    mov [bx+HDV_VOLH], al
    pop cx
    pop ax
    clc
    ret

; -----------------------------------------------------------------------------
; hd_unmount - take the selected device's volume away
; in:  nothing; the lock is HELD
; out: nothing
; -----------------------------------------------------------------------------
hd_unmount:
    push bx
    call hd_mounted
    jc .out
    call hd_unmount_row
    mov word [hd_msg], hd_s_unmounted
.out:
    pop bx
    ret

; -----------------------------------------------------------------------------
; hd_unmount_row - drop one volume and its claim (module internal)
; in:  BX = the hd_vols row
; out: nothing (all registers preserved)
; -----------------------------------------------------------------------------
hd_unmount_row:
    push ax
    push dx
    cmp byte [bx+HDV_USED], 0
    je .out
    mov al, [bx+HDV_VOL]
    call OSAPI_VOL_DEL
    mov dx, [bx+HDV_LSEG]
    or dx, dx
    jz .noseg
    call OSAPI_MEM_FREE
.noseg:
    mov byte [bx+HDV_USED], 0
    mov word [bx+HDV_LSEG], 0
.out:
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_win_close_all - hide both tool windows (detach's obligation)
; in:  nothing
; out: nothing (all registers preserved)
; -----------------------------------------------------------------------------
hd_win_close_all:
    push bx
    mov bx, [hd_pwin]
    or bx, bx
    jz .nop
    call OSAPI_WM_HIDE
.nop:
    mov bx, [hd_fwin]
    or bx, bx
    jz .nof
    call OSAPI_WM_HIDE
.nof:
    pop bx
    ret

; =============================================================================
; Shared helpers
; =============================================================================

; -----------------------------------------------------------------------------
; hd_win_erase - white-fill one of our windows' CONTENT, and nothing else
; in:  BX = the window; the gfx lock is HELD
; out: nothing (all registers preserved)
;
; **The size comes from OSAPI_WM_GEOM, never from the template's own
; constants**, and that is not caution - it is a bug this had. A window's
; CONTENT is `W_W - 2` by `W_H - TITLE_H - 1`, and TITLE_H is EIGHTEEN; a
; repaint that open-coded `HPW_H - 14` filled six rows past the bottom of the
; content, straight through the window's border and its drop shadow and into
; whatever was behind it. The kernel's primitives clip to the SCREEN and not
; to a window (SPEC.md 5), so nothing downstream was ever going to catch it.
;
; The frame size is not the answer either, even with the right subtraction:
; wm_fit clamps a template that does not fit the live screen (SPEC.md 39.7),
; so the record - not the template - is the truth. Asking is the only thing
; that is right on all three adapters.
; -----------------------------------------------------------------------------
hd_win_erase:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call OSAPI_WM_GEOM          ; CX = content width, DX = content height
    jc .out                     ; not visible: nothing to erase
    mov si, cx
    mov di, dx
    call OSAPI_WM_CONTENT       ; AX = content left, DX = content top
    mov bx, dx
    mov cx, ax
    add cx, si
    dec cx                      ; x2 = left + width - 1
    mov dx, bx
    add dx, di
    dec dx                      ; y2 = top + height - 1
    push ax
    push bx
    push cx
    push dx
    mov al, CWHITE
    call OSAPI_SET_COLOR
    pop dx
    pop cx
    pop bx
    pop ax
    call OSAPI_GFX_FILL
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_raw - one raw transfer to a DEVICE, outside any volume
; in:  [hd_rawop] = 0 read / 1 write, DX:AX = the LBA, ES:BX = the buffer,
;      CX = sectors, DI = the device row
; out: CF = 0 done; CF = 1 failed
; clobbers: flags
;
; The op is in MEMORY rather than a register because the LBA needs DX:AX and
; the buffer needs ES:BX - the same reason DSV_BLK takes its own buffer in
; DX:BX (SPEC.md 51.8).
; -----------------------------------------------------------------------------
hd_raw:
    mov [hd_lba], ax
    mov [hd_lba+2], dx
    mov [hd_bofs], bx
    mov [hd_bcnt], cx
    push ax
    mov ax, es
    mov [hd_bseg], ax
    pop ax
    push ax
    mov al, [hd_rawop]
    mov [hd_bop], al
    pop ax
hd_raw_op:
    push ax
    cmp byte [di+HDD_KIND], HDK_IDE
    je .ide
    call hd_bios_xfer
    jmp short .out
.ide:
    call hd_ide_xfer
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_scat - append the NUL string at SI to DI, leaving DI past it
; in:  SI = source, DI = destination
; out: DI advanced to the NUL (which is not written)
; clobbers: DI (the output), flags
; -----------------------------------------------------------------------------
hd_scat:
    push ax
    push si
.next:
    mov al, [si]
    or al, al
    jz .done
    mov [di], al
    inc si
    inc di
    jmp short .next
.done:
    mov [hd_lineptr], di
    pop si
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_utoa / hd_utoa3 / hd_utoa4 - AX as decimal at DI, DI advanced
; in:  AX = the value, DI = the destination
; out: DI past the last digit
; clobbers: DI (the output), flags
;
; The padded forms right-align a column of numbers without a second pass, and
; a value too wide for its field simply prints wide - a geometry the user can
; see is worth more than a column that lines up.
; -----------------------------------------------------------------------------
hd_utoa:
    push cx
    xor cx, cx
    jmp short hd_utoa_body
hd_utoa3:
    push cx
    mov cx, 3
    jmp short hd_utoa_body
hd_utoa4:
    push cx
    mov cx, 4
hd_utoa_body:
    push ax
    push bx
    push dx
    push si
    mov si, cx                  ; SI = the width wanted. It CANNOT stay on
    mov bx, 10                  ; the stack: the digits go there next, and
    xor cx, cx                  ; the pop would take the last of them
.divide:
    xor dx, dx
    div bx
    push dx                     ; the digits, least significant first
    inc cx
    or ax, ax
    jnz .divide
    cmp si, cx
    jbe .emit
    sub si, cx                  ; pad with leading spaces
.pad:
    mov byte [di], ' '
    inc di
    dec si
    jnz .pad
.emit:
    pop dx
    add dl, '0'
    mov [di], dl
    inc di
    loop .emit
    mov [hd_lineptr], di
    pop si
    pop dx
    pop bx
    pop ax
    pop cx
    ret

hd_s_bios:    db 'BIOS', 0
hd_s_ide:     db 'IDE', 0
hd_s_x:       db 'x', 0
hd_s_unk:     db ' geometry unknown', 0
hd_s_c:       db 'C', 0
hd_s_h:       db 'H', 0
hd_s_s:       db 'S', 0
hd_s_minus:   db '-', 0
hd_s_plus:    db '+', 0
hd_s_part:    db 'Partition', 0
hd_s_format:  db 'Format', 0
hd_s_mount:   db 'Mount', 0
hd_s_unmount: db 'Unmount', 0
hd_s_hddc:    db 'HDD C', 0
hd_s_pick:    db 'Pick a drive, then a button', 0
hd_s_nodev:   db 'No hard disk found', 0
hd_s_nogeom:  db 'Geometry unknown: type it', 0
hd_s_typed:   db 'Geometry set by hand', 0
hd_s_mounted: db 'Mounted - see the desktop', 0
hd_s_unmounted: db 'Unmounted', 0
hd_s_mnotab:  db 'No partition table yet', 0
hd_s_mfull:   db 'No free volume', 0
hd_s_mbad:    db 'Not a FAT volume: Format', 0
hd_s_mbig:    db 'Partition is over 32MB', 0
