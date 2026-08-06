; =============================================================================
; os8088 - HDD.DRV / tool.inc
;
; The disk tool (SPEC.md 52.2) - ONE window where there were two.
;
; Partitioning and formatting were a Partition window (New / Delete / Write)
; and a Format window (pick a slot, Format), and between them the user had to
; know that a partition table entry is not a volume, that New only edits RAM,
; that Write is the commit, and that the formatter's slot list is the same four
; slots seen through a different window. None of that is a thing anybody wants
; to know about their disk. What they want is four slots and, for each one,
; either what is in it or a button that puts a usable volume there.
;
; So there is one window, one row per slot, and one button:
;
;   Slot  Size   State
;   1     31M    FAT16                 <- a volume; Mount will find it
;   2      -     Not Formatted         <- free, or a region with no volume in
;   3     50M    Unmountable              it: Format makes one
;   4      -     Not Formatted         <- foreign, or over the ceiling: greyed,
;   [Format]  [Close]                     and Format reclaims the first 32MB
;
; **Not Formatted covers unpartitioned AND partitioned-but-empty**, and that is
; deliberate: the difference is the tool's business and not the user's. Both
; mean "there is no volume here and Format will make one", and a table entry
; with nothing behind it is exactly what a format interrupted half way leaves
; (SPEC.md 52.3 writes the boot sector last).
;
; **Format on a slot that already has something confirms first**, in the
; caption, by asking for the click again. There is no dialog to put it in - a
; driver has no notice window and no modal - and a second click on the same
; button is the cheapest confirm that cannot be mistaken for the first one.
; Anything else (picking another row, closing) disarms it.
;
; A greyed row is CDGRAY, so on the two 1bpp adapters it renders BLACK -
; SPEC.md 39.4 rounds a glyph to black rather than dithering it, and [gfx_dis]
; is not in the package ABI. That is why the state is a WORD and not only a
; colour: 'Unmountable' is the whole signal on mono and the grey is a VGA
; nicety on top of it (SPEC.md 47 rule 7).
;
; The window is the unowned species (SPEC.md 38.1) - no instance, so its close
; box reduces to wm_hide and there is no teardown path to write. What there IS
; is the rule that detach must leave none on screen, because the kernel frees
; this image the moment detach returns.
; =============================================================================

HTW_W        equ 300
HTW_H        equ 150
HTW_LX       equ 4
HTW_HY       equ 6              ; the header row
HTW_R0Y      equ 22             ; the first slot row, content-relative
HTW_ROWH     equ 12
HTW_BY       equ 96             ; the button row
HTW_BH       equ 16
HTW_CAPY     equ 120
HTW_B0X      equ 4              ; 'Format'
HTW_B1X      equ 76             ; 'Close'
HTW_BW0      equ 64
HTW_BW1      equ 56

HTS_FREE     equ 0              ; nothing in this slot
HTS_RAW      equ 1              ; a FAT-typed extent with no volume in it
HTS_VOL      equ 2              ; a volume
HTS_ALIEN    equ 3              ; foreign type, or over the 65,535-sector
                                ; ceiling (SPEC.md 18.7) - either way this
                                ; kernel will never mount it

hd_ttpl:    dw 90, 90, HTW_W, HTW_H, hd_s_ttitle, hd_tw_paint, 0, hd_tw_click
hd_s_ttitle: db 'Format', 0

; -----------------------------------------------------------------------------
; hd_tw_open - put the tool up (module internal)
; in:  nothing; the gfx lock is HELD (a Control Panel click)
; out: nothing
;
; A fresh table every time it opens, because the disk can be swapped between
; two clicks - and the states with it, which is up to four sector reads and
; the only I/O this window does that is not a write.
; -----------------------------------------------------------------------------
hd_tw_open:
    push ax
    push bx
    push si
    mov al, [hd_sel]
    call hd_dev_row
    push di
    call hd_part_load
    pop di
    call hd_tw_scan
    mov byte [hd_tsel], 0
    mov byte [hd_tarm], 0
    mov word [hd_tmsg], hd_s_tready
    mov bx, [hd_twin]
    or bx, bx
    jnz .show
    mov si, hd_ttpl
    call OSAPI_WM_CREATE
    jc .out
    mov [hd_twin], bx
.show:
    call OSAPI_WM_SHOW
.out:
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_tw_scan - work out all four slots' states (module internal)
; in:  DI = the device row; hd_mbr holds the table
; out: hd_tstate[0..3] filled
; clobbers: flags
;
; The order of the tests is the order of the certainties: over the ceiling and
; a type we do not mount are facts about the TABLE, so neither costs a read;
; only a slot that could carry a volume is asked whether it does.
; -----------------------------------------------------------------------------
hd_tw_scan:
    push ax
    push bx
    push si
    xor bl, bl
.slot:
    mov al, bl
    call hd_part_ent
    mov al, HTS_FREE
    call hd_part_used
    jc .store
    mov al, HTS_ALIEN
    cmp word [si+HP_SECS+2], 0
    jne .store                  ; over 65,535 sectors (SPEC.md 18.7)
    call hd_part_isfat
    jc .store                   ; a type this driver does not mount
    mov al, HTS_VOL
    call hd_fmt_isfat
    jnc .store
    mov al, HTS_RAW
.store:
    push bx
    xor bh, bh
    mov [bx+hd_tstate], al
    pop bx
    inc bl
    cmp bl, 4
    jb .slot
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_tw_paint - W_PAINT (content already white-filled, lock held)
; in:  SI = the window
; out: nothing
; -----------------------------------------------------------------------------
hd_tw_paint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp

    mov bx, si
    call OSAPI_WM_CONTENT       ; AX = content left, DX = content top
    mov di, ax
    mov bp, dx

    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov si, hd_s_thdr
    mov cx, di
    add cx, HTW_LX
    mov dx, bp
    add dx, HTW_HY
    call OSAPI_FONT_STR

    xor cl, cl
.row:
    push cx
    mov al, cl
    call hd_tw_rowtext          ; hd_line = '1     31M   FAT16'
    pop cx
    push cx
    mov ax, cx
    mov ah, HTW_ROWH
    mul ah
    add ax, HTW_R0Y
    mov dx, bp
    add dx, ax                  ; DX = the row's text y
    push dx
    mov al, cl
    cmp al, [hd_tsel]
    jne .plain
    pop dx                      ; the selected slot: a black bar under it
    push dx
    push cx
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, di
    add ax, HTW_LX - 2
    mov bx, dx
    dec bx
    mov cx, di
    add cx, HTW_W - 14
    mov dx, bx
    add dx, 9
    call OSAPI_GFX_FILL
    pop cx
    mov al, CWHITE
    call OSAPI_SET_COLOR
    jmp short .text
.plain:
    push cx                     ; an unmountable slot is greyed - and says so
    xor ch, ch                  ; in words, because on 1bpp CDGRAY IS black
    mov bx, cx                  ; (SPEC.md 39.4)
    mov al, [bx+hd_tstate]
    cmp al, HTS_ALIEN
    mov al, CBLACK
    jne .pen
    mov al, CDGRAY
.pen:
    call OSAPI_SET_COLOR
    pop cx
.text:
    pop dx
    mov si, hd_line
    mov cx, di
    add cx, HTW_LX
    call OSAPI_FONT_STR
    pop cx
    inc cl
    cmp cl, 4
    jb .row

    mov al, CBLACK              ; the pen for both buttons and the caption:
    call OSAPI_SET_COLOR        ; hd_tw_button cannot set it (AX is the x)
    mov si, hd_s_tfmt
    mov ax, HTW_B0X
    mov bx, HTW_BW0
    call hd_tw_button
    mov si, hd_s_close
    mov ax, HTW_B1X
    mov bx, HTW_BW1
    call hd_tw_button

    mov si, [hd_tmsg]
    mov cx, di
    add cx, HTW_LX
    mov dx, bp
    add dx, HTW_CAPY
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
; hd_tw_button - one framed, labelled button (module internal)
; in:  AX = x, BX = width (both content-relative), SI = the label,
;      DI/BP = the content origin
; out: nothing (all registers preserved)
;
; Never greyed. Format is live on every row there is - including an
; unmountable one, which is the only way to get that space back - and the
; caption is what explains a refusal (SPEC.md 47 rule 3: the only honest test
; for "is there room" is working out the extent, which is what the click does).
;
; **The pen is the CALLER's**, because AX is the x here and OSAPI_SET_COLOR
; takes its colour in AL: setting it inside drew both buttons at the same
; place, one on top of the other.
; -----------------------------------------------------------------------------
hd_tw_button:
    push ax
    push bx
    push cx
    push dx
    push si
    add ax, di                  ; AX = x1
    mov cx, ax
    add cx, bx
    dec cx                      ; CX = x2
    mov bx, bp
    add bx, HTW_BY              ; BX = y1
    mov dx, bx
    add dx, HTW_BH - 1          ; DX = y2
    push ax
    push bx
    push cx
    push dx
    call OSAPI_GFX_FRAME
    pop dx
    pop cx
    pop bx
    pop ax
    add ax, 4                   ; the label, 4px in and centred vertically
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
; hd_tw_rowtext - one slot's line, into hd_line (module internal)
; in:  AL = slot
; out: hd_line holds a NUL string
; clobbers: flags
;
; 'n' + the size + the state, and the size is blank for a slot with no extent
; rather than a number nothing has promised: two free slots would otherwise
; both advertise the same megabytes and only one of them can have them.
; -----------------------------------------------------------------------------
hd_tw_rowtext:
    push ax
    push bx
    push si
    push di
    mov [hd_rowslot], al
    mov di, hd_line
    add al, '1'
    mov [di], al
    inc di
    mov si, hd_s_four
    call hd_scat

    mov bl, [hd_rowslot]
    xor bh, bh
    mov al, [bx+hd_tstate]
    cmp al, HTS_FREE
    jne .size
    mov si, hd_s_nosize         ; five spaces: nothing is claimed here
    call hd_scat
    jmp short .state
.size:
    mov al, [hd_rowslot]
    call hd_part_ent
    call hd_part_mb             ; AX = megabytes
    call hd_utoa4
    mov si, hd_s_mb
    call hd_scat
.state:
    mov si, hd_s_two
    call hd_scat
    mov bl, [hd_rowslot]
    xor bh, bh
    mov al, [bx+hd_tstate]
    cmp al, HTS_ALIEN
    je .alien
    cmp al, HTS_VOL
    je .vol
    mov si, hd_s_traw           ; free and partitioned-but-empty read the same
    call hd_scat                ; on purpose: both mean Format makes a volume
    jmp short .done
.alien:
    mov si, hd_s_talien
    call hd_scat
    jmp short .done
.vol:
    mov al, [hd_rowslot]        ; the TYPE byte's name: what the table says,
    call hd_part_ent            ; and what this driver wrote into it
    cmp byte [si+HP_TYPE], HPT_FAT12
    mov si, hd_s_f16name        ; (no flags touched between the two)
    jne .tname
    mov si, hd_s_f12name
.tname:
    call hd_scat
.done:
    mov byte [di], 0
    pop di
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_tw_click - W_ONCLICK (absolute screen coords, lock held)
; in:  CX = x, DX = y, SI = the window
; out: nothing
; -----------------------------------------------------------------------------
hd_tw_click:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp

    mov bx, si
    mov si, dx
    call OSAPI_WM_CONTENT
    mov di, ax
    mov bp, dx
    sub cx, di                  ; CX = content-relative x
    mov dx, si
    sub dx, bp                  ; DX = content-relative y

    cmp dx, HTW_BY
    jge .buttons

    mov ax, dx                  ; a slot row?
    sub ax, HTW_R0Y
    jl .done
    mov bl, HTW_ROWH
    div bl                      ; AL = the row, AH = the remainder
    cmp al, 4
    jae .done
    mov [hd_tsel], al
    mov byte [hd_tarm], 0       ; a different row is a different question
    mov word [hd_tmsg], hd_s_tready
    jmp short .repaint

.buttons:
    cmp dx, HTW_BY + HTW_BH
    jge .done
    mov ax, cx
    cmp ax, HTW_B0X
    jl .done
    cmp ax, HTW_B0X + HTW_BW0
    jl .format
    cmp ax, HTW_B1X
    jl .done
    cmp ax, HTW_B1X + HTW_BW1
    jge .done
    mov byte [hd_tarm], 0
    mov bx, [hd_twin]
    call OSAPI_WM_HIDE
    jmp short .done

.format:
    call hd_tw_format
.repaint:
    call hd_tw_repaint
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
; hd_tw_format - partition and format the selected slot (module internal)
; in:  [hd_tsel]; the gfx lock is HELD
; out: [hd_tmsg] says what happened; the states are re-scanned
; clobbers: flags
;
; **The table entry goes down BEFORE the volume**, and that is the same
; argument as the boot sector going last inside the format (SPEC.md 52.3):
; every way this can be interrupted has to leave a state the tool can describe
; and re-offer. Entry first, volume second means an interruption leaves 'Not
; Formatted' - a claimed region with nothing in it - which is exactly what the
; button is for. The other order leaves a volume nothing can see and an entry
; still pointing at data that has just been overwritten.
; -----------------------------------------------------------------------------
hd_tw_format:
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    mov bl, [hd_tsel]
    xor bh, bh
    cmp byte [bx+hd_tstate], HTS_FREE
    je .go                      ; nothing here to lose

    mov al, [hd_tsel]
    inc al
    cmp al, [hd_tarm]
    je .go                      ; asked and answered
    mov [hd_tarm], al           ; ...otherwise ask, and it is the CAPTION that
    call hd_tw_arm              ; asks: a driver has no dialog to put it in
    jmp .out

.go:
    mov byte [hd_tarm], 0
    mov al, [hd_sel]
    call hd_dev_row
    mov al, [hd_tsel]
    call hd_slot_extent         ; -> [hd_fbase] / [hd_fsecs] (SPEC.md 52.2.1)
    jc .noroom
    call hd_fmt_plan            ; -> the cluster size and the FAT type
    jc .nofit

    mov word [hd_tmsg], hd_s_tdoing
    call hd_tw_repaint          ; say so BEFORE the writes: a 32MB format is
                                ; hundreds of sectors and the user should not
                                ; watch a frozen window wonder

    mov al, [hd_tsel]           ; the entry: the extent, the type the plan
    call hd_part_ent            ; chose, and the CHS halves DOS reads
    mov ax, [hd_fbase]
    mov [si+HP_LBA], ax
    mov ax, [hd_fbase+2]
    mov [si+HP_LBA+2], ax
    mov ax, [hd_fsecs]
    mov [si+HP_SECS], ax
    mov word [si+HP_SECS+2], 0
    mov byte [si+HP_TYPE], HPT_FAT16S
    cmp byte [hd_ftype], 0
    jne .type
    mov byte [si+HP_TYPE], HPT_FAT12
.type:
    mov byte [si+HP_STATUS], 0
    mov al, [hd_sel]
    call hd_dev_row
    call hd_part_chs

    call hd_part_write          ; one sector, and it is the first commit
    jc .werr
    mov al, [hd_sel]
    call hd_dev_row
    call hd_fmt_run             ; ...and the volume, boot sector last
    jc .ferr
    mov word [hd_tmsg], hd_s_tdone
    jmp short .rescan
.werr:
    mov word [hd_tmsg], hd_s_twerr
    jmp short .rescan
.ferr:
    mov word [hd_tmsg], hd_s_tferr
    jmp short .rescan
.noroom:
    mov word [hd_tmsg], hd_s_tnoroom
    jmp short .out
.nofit:
    mov word [hd_tmsg], hd_s_tnofit
    jmp short .out
.rescan:
    mov al, [hd_sel]            ; the states again, which re-reads the boot
    call hd_dev_row             ; sector we just wrote: the row is what the
    call hd_tw_scan             ; DISK says and not what we hoped
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_tw_arm - the confirm question, into hd_line (module internal)
; in:  [hd_tsel]
; out: [hd_tmsg] points at the built line
; clobbers: flags
;
; hd_line is the row painter's buffer too, so this has to be its own: the
; caption survives a repaint and a row does not.
; -----------------------------------------------------------------------------
hd_tw_arm:
    push ax
    push si
    push di
    mov di, hd_ask
    mov si, hd_s_task0
    call hd_scat
    mov al, [hd_tsel]
    inc al
    xor ah, ah
    call hd_utoa
    mov si, hd_s_task1
    call hd_scat
    mov byte [di], 0
    mov word [hd_tmsg], hd_ask
    pop di
    pop si
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_tw_repaint - redraw the tool's content (module internal)
; in:  nothing; the lock is held
; out: nothing (all registers preserved)
; -----------------------------------------------------------------------------
hd_tw_repaint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov bx, [hd_twin]
    or bx, bx
    jz .out
    call hd_win_erase           ; the CONTENT, and only the content
    mov si, [hd_twin]
    call hd_tw_paint
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

hd_s_thdr:    db 'Slot  Size   State', 0
hd_s_four:    db '     ', 0     ; slot digit -> size column
hd_s_nosize:  db '     ', 0     ; ...and the size column when nothing claims it
hd_s_traw:    db 'Not Formatted', 0
hd_s_talien:  db 'Unmountable', 0
hd_s_tfmt:    db 'Format', 0
hd_s_tready:  db 'Pick a slot, then Format', 0
hd_s_tdoing:  db 'Writing...', 0
hd_s_tdone:   db 'Formatted - now Mount it', 0
hd_s_twerr:   db 'Could not write the table', 0
hd_s_tferr:   db 'Could not write the volume', 0
hd_s_tnoroom: db 'No room left on this drive', 0
hd_s_tnofit:  db 'No FAT layout fits that space', 0
hd_s_task0:   db 'Erase slot ', 0
hd_s_task1:   db '? Click Format again', 0
