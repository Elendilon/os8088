; =============================================================================
; os8088 - apps/dotdel/ddhs.inc
;
; THE TABLE (SPEC.md 93.12): six rows of a score and three initials, a file in
; SYSTEM\APPDATA, and the three keystrokes that earn a row.
;
; The shape is Cyclone's and Tank Attack's (SPEC.md 67.20, 85.9), and so are
; the two rules that fail QUIETLY when they are got wrong:
;
;  - **The file lives in SYSTEM\APPDATA on OUR OWN volume** (SPEC.md 19.9), not
;    beside the game. The file browser is the whole of how a user reaches an
;    application here, so a data file in an app folder is a misclick waiting to
;    happen.
;  - **It is OSAPI_FILE_GOTO and not its quiet twin.** GOTO_Q moves the GLOBAL
;    directory and deliberately not the instance's, while FILE_FIND, _READ and
;    _WRITE all resolve in the INSTANCE's - so a quiet move is undone by the
;    very next call, and the save writes nothing at all while the load appears
;    to work.
;
; The write happens when the initials are committed, not at close: a score is
; banked when the player finishes typing it, and a machine switched off - or a
; session ended any way but through the close box - would otherwise drop a row
; the table had already shown.
; =============================================================================

DD_NHS    equ 6
DD_HSFSZ  equ 4 + DD_NHS * 4 + DD_NHS * 3
DD_TABW   equ 19 * 8            ; the table's own width, in whole cells

dd_hs_file:  db 'DOTDEL.HS', 0
dd_hs_magic: db 'DD8', 1        ; so a stale or foreign file is refused rather
                                ; than decoded
dd_d_system: db 'SYSTEM', 0
dd_d_appdat: db 'APPDATA', 0

; The table a machine with no file has ever seen.
dd_hs_def:
    dw 20000, 0, 16000, 0, 12000, 0, 9000, 0, 6000, 0, 3000, 0
dd_hs_defn:  db 'ACE', 'BIT', 'CPU', 'DOT', 'EAT', 'FUN'

; -----------------------------------------------------------------------------
; dd_hs_init - the built-in table, before any file is read
; -----------------------------------------------------------------------------
dd_hs_init:
    push ax
    push cx
    push si
    push di
    mov si, dd_hs_def
    mov di, dd_hs
    mov cx, DD_NHS * 2
.s:
    mov ax, [si]
    mov [di], ax
    add si, 2
    add di, 2
    loop .s
    mov si, dd_hs_defn
    mov di, dd_hsn
    mov cx, DD_NHS * 3
.n:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    loop .n
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_hs_top - DX:AX = the biggest number the HIGH line should show: the table's
;             own first row, or this game's score once it has passed it
; -----------------------------------------------------------------------------
dd_hs_top:
    mov ax, [dd_hs + 0]
    mov dx, [dd_hs + 2]
    cmp dx, [dd_score + 2]
    ja .out
    jb .ours
    cmp ax, [dd_score]
    jae .out
.ours:
    mov ax, [dd_score]
    mov dx, [dd_score + 2]
.out:
    ret

; -----------------------------------------------------------------------------
; dd_hs_row_str - dd_rowbuf = row DI of the table, as "n. AAA      nnnnnnn"
; in:  DI = 0..DD_NHS-1. Preserves every register.
; -----------------------------------------------------------------------------
dd_hs_row_str:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov si, dd_rowbuf
    mov ax, di
    add al, '1'
    mov [si], al
    mov byte [si+1], '.'
    mov byte [si+2], ' '
    ; the initials
    mov ax, di
    mov bx, 3
    mul bx
    mov bx, ax
    mov al, [dd_hsn + bx]
    mov [si+3], al
    mov al, [dd_hsn + bx + 1]
    mov [si+4], al
    mov al, [dd_hsn + bx + 2]
    mov [si+5], al
    mov byte [si+6], ' '
    ; ...and the score, right where the HUD would put it
    mov bx, di
    shl bx, 1
    shl bx, 1
    mov ax, [dd_hs + bx]
    mov dx, [dd_hs + bx + 2]
    call dd_dec32
    mov si, dd_numbuf
    mov di, dd_rowbuf + 7
    call dd_hs_pad10
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; dd_hs_pad10 - copy the NUL string at SI to DI, RIGHT-aligned in ten cells
dd_hs_pad10:
    push ax
    push bx
    push cx
    push si
    push di
    mov bx, si
    xor cx, cx
.len:
    cmp byte [bx], 0
    je .have
    cmp byte [bx], ' '
    je .have                        ; dd_dec32 pads to its own width
    inc bx
    inc cx
    jmp short .len
.have:
    mov ax, 10
    sub ax, cx
    jle .copy
    push cx
    mov cx, ax
.sp:
    mov byte [di], ' '
    inc di
    loop .sp
    pop cx
.copy:
    jcxz .done
.c:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    loop .c
.done:
    mov byte [di], 0
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_hs_offer - the game is over: does this score earn a row?
; -----------------------------------------------------------------------------
dd_hs_offer:
    push ax
    push dx
    mov ax, [dd_hs + (DD_NHS-1)*4]
    mov dx, [dd_hs + (DD_NHS-1)*4 + 2]
    cmp [dd_score + 2], dx
    ja .yes
    jb .no
    cmp [dd_score], ax
    ja .yes
.no:
    call dd_attract_begin
    pop dx
    pop ax
    ret
.yes:
    mov byte [dd_state], DDS_ENTER
    mov word [dd_ini], '  '
    mov byte [dd_ini + 2], ' '
    mov byte [dd_inip], 0
    mov byte [dd_boxd], 1           ; ...and the panel grows the prompt line.
                                    ; NO demo and NO full repaint: the board
                                    ; the score was made on stays exactly where
                                    ; it is, frozen under the box (SPEC.md
                                    ; 93.12.4). Starting the demo here is what
                                    ; used to take the initials on the attract
                                    ; screen a second after the game ended
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_hs_key - typing the initials. AL = ascii, AH = scan.
; -----------------------------------------------------------------------------
dd_hs_key:
    cmp ah, KSC_ENTER
    je .done
    cmp al, 8
    je .back
    cmp al, 'a'
    jb .noup
    cmp al, 'z'
    ja .noup
    sub al, 32
.noup:
    cmp al, 'A'
    jb .out
    cmp al, 'Z'
    ja .out
    mov bl, [dd_inip]
    cmp bl, 3
    jae .out
    xor bh, bh
    mov [dd_ini + bx], al
    inc byte [dd_inip]
    mov byte [dd_boxd], 1
.out:
    ret
.back:
    cmp byte [dd_inip], 0
    je .out
    dec byte [dd_inip]
    mov bl, [dd_inip]
    xor bh, bh
    mov byte [dd_ini + bx], ' '
    mov byte [dd_boxd], 1
    ret
.done:
    call dd_hs_commit
    call dd_attract_begin
    ret

; -----------------------------------------------------------------------------
; dd_box_str - dd_promptb = "NEW HIGH SCORE: AAA_", the panel's second line
;              (SPEC.md 93.12.4). The STRING only: dd_box_line places it, which
;              is what lets the panel measure it before it decides how wide to
;              be.
; -----------------------------------------------------------------------------
dd_box_str:
    push ax
    push bx
    push di
    mov di, dd_promptb
    mov bx, dd_s_newhs
.cp:
    mov al, [bx]
    or al, al
    jz .ini
    mov [di], al
    inc di
    inc bx
    jmp short .cp
.ini:
    mov al, [dd_ini]
    mov [di], al
    mov al, [dd_ini + 1]
    mov [di+1], al
    mov al, [dd_ini + 2]
    mov [di+2], al
    mov byte [di+3], '_'            ; where the next letter goes
    mov byte [di+4], 0
    pop di
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_hs_commit - put the score in, push the rest down, and write the file
; -----------------------------------------------------------------------------
dd_hs_commit:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov di, DD_NHS - 1
.find:
    or di, di
    jz .place
    mov bx, di
    dec bx
    shl bx, 1
    shl bx, 1
    mov ax, [dd_hs + bx + 2]
    cmp ax, [dd_score + 2]
    ja .place
    jb .up
    mov ax, [dd_hs + bx]
    cmp ax, [dd_score]
    jae .place
.up:
    ; the row above is smaller: shift it down and keep looking
    mov si, bx
    mov bx, di
    shl bx, 1
    shl bx, 1
    mov ax, [dd_hs + si]
    mov [dd_hs + bx], ax
    mov ax, [dd_hs + si + 2]
    mov [dd_hs + bx + 2], ax
    mov ax, di
    mov cx, 3
    mul cx
    mov bx, ax
    mov ax, di
    dec ax
    mul cx
    mov si, ax
    mov al, [dd_hsn + si]
    mov [dd_hsn + bx], al
    mov al, [dd_hsn + si + 1]
    mov [dd_hsn + bx + 1], al
    mov al, [dd_hsn + si + 2]
    mov [dd_hsn + bx + 2], al
    dec di
    jmp short .find
.place:
    mov bx, di
    shl bx, 1
    shl bx, 1
    mov ax, [dd_score]
    mov [dd_hs + bx], ax
    mov ax, [dd_score + 2]
    mov [dd_hs + bx + 2], ax
    mov ax, di
    mov cx, 3
    mul cx
    mov bx, ax
    mov al, [dd_ini]
    cmp al, ' '
    jne .n0
    mov al, '-'
.n0:
    mov [dd_hsn + bx], al
    mov al, [dd_ini + 1]
    cmp al, ' '
    jne .n1
    mov al, '-'
.n1:
    mov [dd_hsn + bx + 1], al
    mov al, [dd_ini + 2]
    cmp al, ' '
    jne .n2
    mov al, '-'
.n2:
    mov [dd_hsn + bx + 2], al
    call dd_hs_save
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; SYSTEM\APPDATA, AND THE FILE
; =============================================================================

; dd_data_enter - bank where we are and go to SYSTEM\APPDATA on this volume.
; out: CF = 1 we did not get there and NOTHING was banked or moved.
dd_data_enter:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    call OSAPI_FILE_HERE            ; DX = our directory, BL = our drive
    mov [dd_dbclus], dx
    mov [dd_dbdrv], bl
    xor dx, dx                      ; the ROOT of that same volume
    call OSAPI_FILE_GOTO
    jc .back
    mov si, dd_d_system
    call dd_data_dive
    jc .back
    mov si, dd_d_appdat
    call dd_data_dive
    jc .back
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.back:
    call dd_data_home               ; a disk without the folder is a user's own
    pop es                          ; disk, not an error: put the volume back
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

dd_data_leave:
    pushf
    push ax
    push bx
    push cx
    push dx
    push si
    call dd_data_home
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    popf
    ret

dd_data_home:
    push ax
    push bx
    push dx
    mov dx, [dd_dbclus]
    mov bl, [dd_dbdrv]
    call OSAPI_FILE_GOTO
    pop dx
    pop bx
    pop ax
    ret

; dd_data_dive - step into the folder named at SI. CF = 1 there is none.
dd_data_dive:
    push ax
    push cx
    push si
    push di
    xor cx, cx
.each:
    push ds                         ; ES EVERY TIME: nothing promises it
    pop es                          ; survives a far call into the kernel
    mov di, dd_dfind
    call OSAPI_FILE_FIND
    jc .none
    cmp word [dd_dfind + 14], OSAPI_FT_DIR
    jne .each                       ; only a FOLDER can be dived into, and
                                    ; type 1 is a PACKAGE, not "a file"
    push cx
    push si
    mov di, dd_dfind
    call dd_data_same
    pop si
    pop cx
    jc .each
    mov dx, [dd_dfind + 16]
    mov bl, [dd_dbdrv]
    call OSAPI_FILE_GOTO
    jc .none
    pop di
    pop si
    pop cx
    pop ax
    clc
    ret
.none:
    pop di
    pop si
    pop cx
    pop ax
    stc
    ret

; dd_data_same - is the NUL name at SI the one at DI? CF = 0 yes.
dd_data_same:
    push ax
.n:
    mov al, [si]
    cmp al, [di]
    jne .no
    or al, al
    jz .yes
    inc si
    inc di
    jmp short .n
.yes:
    pop ax
    clc
    ret
.no:
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; dd_hs_load - read the table once, at startup. Anything wrong with the file
;              leaves the built-in rows standing: a score table is not worth an
;              error box, and a first run has no file at all.  UI TASK ONLY.
; -----------------------------------------------------------------------------
dd_hs_load:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call dd_data_enter
    jc .out
    push ds
    pop es
    mov si, dd_hs_file
    mov bx, dd_hsbuf
    mov cx, DD_HSFSZ
    xor dx, dx
    call OSAPI_FILE_READ
    jc .leave
    cmp ax, DD_HSFSZ
    jne .leave
    mov si, dd_hsbuf
    mov di, dd_hs_magic
    mov cx, 4
.mag:
    mov al, [si]
    cmp al, [di]
    jne .leave
    inc si
    inc di
    loop .mag
    mov di, dd_hs
    mov cx, DD_NHS * 2
.sc:
    mov ax, [si]
    mov [di], ax
    add si, 2
    add di, 2
    loop .sc
    mov di, dd_hsn
    mov cx, DD_NHS * 3
.nm:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    loop .nm
.leave:
    call dd_data_leave
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_hs_save - write it back. UI TASK ONLY, and a bracket IS the UI task
;              (SPEC.md 53.7), which is why this is legal from either world.
; -----------------------------------------------------------------------------
dd_hs_save:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov si, dd_hs_magic
    mov di, dd_hsbuf
    mov cx, 4
.mag:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    loop .mag
    mov si, dd_hs
    mov cx, DD_NHS * 2
.sc:
    mov ax, [si]
    mov [di], ax
    add si, 2
    add di, 2
    loop .sc
    mov si, dd_hsn
    mov cx, DD_NHS * 3
.nm:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    loop .nm
    call dd_data_enter
    jc .out
    push ds
    pop es
    mov si, dd_hs_file
    mov bx, dd_hsbuf
    mov cx, DD_HSFSZ
    xor dx, dx
    call OSAPI_FILE_WRITE
    call dd_data_leave
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
