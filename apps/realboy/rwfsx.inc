; =============================================================================
; os8088 - apps/realboy/rwfsx.inc
;
; RealBoy's FULL SCREEN (docs/REALBOY-SPEC.md section 15): the machine run on
; the UI task inside an OSAPI_FSX_RUN bracket, with the screen its own.
; Included by realboy.asm.
;
; The worker is FROZEN in there, so it must not be frozen INSIDE the machine
; - in the core, or in rb_render, whose working memory is the view's. It
; holds [rw_incore] from its loop's top to the end of its render and backs
; off at the top when [rw_fsq] is set; rw_fsenter sets [rw_fsq] and yields
; until [rw_incore] is clear. The store order is what makes it exact: the
; worker raises its byte BEFORE it reads ours, so once we have seen it clear
; with ours set, every later entry of its sees ours and backs off.
;
; THE SCREEN is mode 0Dh, 320x200 planar, the picture at 1x in the middle.
; rb_render's two shade planes go to VGA planes 0 and 1 as they are, through
; a RAM shadow of the last frame: a word is written only when it changed.
; Plane 2 is set everywhere but the picture, so the border is DAC entry 4 and
; the speed line, planes 0 and 1 over it, entry 7. The DAC is ours in here;
; the restore's BIOS mode set puts the desktop's back (SPEC.md 53.6).
;
; THE CLOCK is FSXF_RATE at the Game Boy's own frame rate: a hook on every
; period counts frames owed and nothing else, and the loop runs the machine
; to the count. It draws a frame when it has caught up, or when RW_FSSKIP
; frames have gone by undrawn. kern_small refuses FSXF_RATE (and has no
; VGA): the bracket is retried without it and paces by the tick.
; =============================================================================

RW_FSDIV        equ 19977           ; 1,193,182 / 59.7275: a period a frame
RW_FSSKIP       equ 4               ; frames run undrawn at most, behind
RW_FSX          equ 10              ; the picture's byte column (x = 80)
RW_FSY          equ 28              ; ...and its first row
RW_FSTXT        equ 182             ; the speed line's row
RW_FSVGA        equ 0               ; rw_fskind: the writers
RW_FSHERC       equ 1
RW_FSCGA        equ 2
RW_HX           equ 25              ; Hercules: the picture's byte column
RW_HY           equ 26              ;   (x = 200, 320 wide) and first row
RW_HTXT         equ 322             ;   (288 tall), and the speed line's
RW_CY           equ 28              ; CGA: the picture's first row (320 by
RW_CTXT         equ 182             ;   144), and the speed line's
RW_FSBUD        equ 6000            ; M-cycles a core run in here: no mouse
RW_FSBUD86      equ 1400            ;   to serve, so only IRQ0 bounds it - one
                                    ;   rate period is 16.7 ms, and a 286 at
                                    ;   ~35 clocks a busy M-cycle spends ~7 ms
                                    ;   on 6,000 of them all busy (an 8088 at
                                    ;   ~48, ~14 ms on 1,400)

; rw_mgrey - Machine > Full Screen, greyed with the reason when it cannot be
; had: no game, or a display with no mode 0Dh. Any context.
rw_mgrey:
    push ax
    push bx
    push dx
    push si
    mov si, rw_it_fs0
    cmp byte [rw_state], 1
    jne .set
    call rw_fspick                  ; CF = 1: no mode we have a writer for
    jc .set
    mov si, rw_it_fs
.set:
    mov [rw_i_mach + 4], si
    mov si, rw_it_jit0              ; Recompiler: what it is now
    cmp word [rw_jitseg], 0
    je .j
    mov si, rw_it_joff
    cmp byte [rw_jitwant], 0
    je .j
    mov si, rw_it_jon
.j:
    mov [rw_i_mach + 6], si
    mov si, rw_it_log0              ; Log: what it is now
    cmp byte [rw_logon], 0
    je .l
    mov si, rw_it_log1
.l:
    mov [rw_i_mach + 8], si
    pop si
    pop dx
    pop bx
    pop ax
    ret

; rw_fsenter - Machine > Full Screen, on the UI task with the lock held
rw_fsenter:
    cmp byte [rw_state], 1
    jne .r
    call rw_fspick                  ; AL = the writer
    jc .r                           ; greyed; a shortcut gets nothing either
    mov [rw_fskind], al
    call OSAPI_FONT_GLYPHS          ; DX:SI, AL first, AH last: copied now,
    call rw_fscopy                  ;   before the mode leaves the desktop's
    mov byte [rw_fsq], 1
.wait:
    cmp byte [rw_incore], 0         ; the worker out of the machine first
    je .go
    call OSAPI_TASK_YIELD
    jmp short .wait
.go:
    mov byte [rw_pfmt], 0           ; rw_pbuf is our shadow in there: the
                                    ;   restore's repaint paints white
    mov byte [rw_fsrate], 1
    mov ax, rw_fsmain
    mov bx, [rw_win]
    mov cx, FSXF_RATE
    mov dx, RW_FSDIV
    mov di, rw_fshook
    call OSAPI_FSX_RUN
    jnc .out
    mov byte [rw_fsrate], 0         ; kern_small: no rate, the tick paces
    mov ax, rw_fsmain
    mov bx, [rw_win]
    xor cx, cx
    call OSAPI_FSX_RUN
.out:
    call OSAPI_GET_TICKS            ; the window takes up from now
    mov [rw_last], ax
    mov word [rw_owed], 0
    mov byte [rw_fsq], 0
.r:
    ret

; rw_fspick - the writer for this window's display: VGA mode 0Dh, else the
; Hercules page at 2x2, else CGA's 320x200 in four colours. AL = RW_FS*, or
; CF = 1 for none.
rw_fspick:
    push bx
    mov bx, [rw_win]
    call OSAPI_FSX_CAPS             ; AX = the modes this display can set
    pop bx
    test ax, 1 << FSXM_VGA0D
    jz .h
    mov al, RW_FSVGA
    clc
    ret
.h:
    test ax, 1 << FSXM_HERC
    jz .c
    mov al, RW_FSHERC
    clc
    ret
.c:
    test ax, 1 << FSXM_CGA320
    jz .no
    mov al, RW_FSCGA
    clc
    ret
.no:
    stc
    ret

; rw_fscopy - the glyphs for 32-127 into rw_font, blanks where the table
; stops. DX:SI = the table, AL = its first code, AH = its last.
rw_fscopy:
    push ds
    push ds
    pop es
    mov di, rw_font
    mov bl, 32
    mov ds, dx
.c:
    cmp bl, al
    jb .blank
    cmp bl, ah
    ja .blank
    push si
    mov cl, bl
    sub cl, al
    xor ch, ch
    shl cx, 1
    shl cx, 1
    shl cx, 1
    add si, cx                      ; SI = this code's 8 rows
    mov cx, 8
    rep movsb
    pop si
    jmp short .next
.blank:
    push ax
    xor al, al
    mov cx, 8
    rep stosb
    pop ax
.next:
    inc bl
    cmp bl, 128
    jb .c
    pop ds
    ret

; rw_fshook - every rate period: a frame owed. AX = periods since the last.
rw_fshook:
    add [rw_fowed], ax
    add [rw_fsper], ax              ; (rw_clk's, for the log)
    ret

; rw_fsmain - the bracket. DS = CS = ours, ES = KERNEL_SEG, SI = the window.
rw_fsmain:
    OS88_ALTENTER_SEED              ; the Alt+Enter that got us here is held
    push ds
    pop es
    mov bl, [rw_fskind]
    xor bh, bh
    mov al, [rw_fsmodes + bx]
    mov di, rw_fsi
    call OSAPI_FSX_MODE
    jc .r
    cmp byte [rw_fskind], RW_FSVGA
    jne .mono
    call rw_fsdac
    call rw_fsframe
    push ds
    pop es
    mov di, rw_pbuf                 ; the shadow: the mode set cleared the
    mov cx, 5760 / 2                ;   screen to zero, and so is it
    xor ax, ax
    rep stosw
    call rw_dmgfull                 ; and every line of the first frame
    jmp short .in
.mono:
    call rw_fsclear                 ; Hercules or CGA: the screen black,
    call rw_fstab                   ;   the writer's table, and every line
    call rw_dmgfull                 ;   of the first frame
.in:
    mov byte [rw_infsx], 1
    push word [rw_budget]           ; the window's budget, back at the end
    mov ax, RW_FSBUD
    cmp word [rw_budget], RW_BUDGET86
    jne .bud
    mov ax, RW_FSBUD86
.bud:
    mov [rw_budget], ax
    mov byte [rw_ovlnew], 1
    mov word [rw_fowed], 0
    mov byte [rw_fsrun], 0
    call OSAPI_GET_TICKS
    mov [rw_last], ax
    sub ax, 100                     ; long enough ago: the first draws now
    mov [rw_drawt], ax
.loop:
    call rw_fsdrain                 ; ZF = 0: Esc
    jnz .out
    call rw_fsowed                  ; AX = frames owed now (taken)
    or ax, ax
    jnz .run
    mov al, FSXW_FRAME
    cmp byte [rw_fsrate], 0
    jne .w
    mov al, FSXW_TICK
.w:
    call OSAPI_FSX_WAIT
    jmp short .loop
.run:
    cmp ax, RW_BEHIND               ; behind by more than that: run on
    jbe .n                          ;   from here rather than race
    mov ax, RW_BEHIND
.n:
    mov [rw_fsleft], ax
    call rw_logowed                 ; (AL = frames owed, for the log)
.f:
    call rw_keys
    call rw_frame
    jc .out                         ; it stopped
    call rw_sound
    inc word [rw_nrun]
    call rw_stat
    inc byte [rw_fsrun]
    xor bx, bx
    dec word [rw_fsleft]
    jz .due                         ; caught up: draw this one, when due
    cmp byte [rw_fsrun], RW_FSSKIP  ; (rw_drawdue, as the window's)...
    jb .f
    mov bx, RW_DRAWTICKS            ; ...or behind by the clock
.due:
    call rw_drawdue
    jc .draw
    mov byte [rw_fsrun], 0
    cmp word [rw_fsleft], 0
    jne .f
    jmp .loop
.draw:
    mov byte [rw_fsrun], 0
    mov si, rw_fsdraw
    call rw_timed
    call rw_fsdrain                 ; Esc between two draws too: on an 8088
    jnz .out                        ;   a turn of frames is longer than a press
    cmp word [rw_fsleft], 0
    jne .f
    jmp .loop
.out:
    pop word [rw_budget]
    mov byte [rw_infsx], 0
.r:
    ret

; rw_fsowed - AX = the frames owed since the last call, and none left owed
rw_fsowed:
    cmp byte [rw_fsrate], 0
    je .tick
    pushf
    cli
    mov ax, [rw_fowed]
    mov word [rw_fowed], 0
    popf
    ret
.tick:
    push bx
    push dx
    call OSAPI_GET_TICKS
    mov bx, ax
    xchg bx, [rw_last]
    sub ax, bx
    cmp ax, 10                      ; away longer than that: start over
    jbe .t
    mov ax, 10
.t:
    mov dx, RW_PERTICK
    mul dx
    add ax, [rw_owed]
    mov dl, al                      ; the fraction stays owed
    xor dh, dh
    mov [rw_owed], dx
    mov al, ah
    xor ah, ah
    pop dx
    pop bx
    ret

; rw_fsdrain - the BIOS key buffer emptied (a full one beeps); ZF = 0 when
; Esc is held
rw_fsdrain:
.k:
    mov ah, 1
    int 16h
    jz .e
    xor ah, ah
    int 16h
    jmp short .k
.e:
    mov al, 1                       ; Esc
    call OSAPI_KEY_DOWN             ; CF = 1: held
    jc .out
    call os88alt_edge               ; ...or a fresh Alt+Enter
    jc .out
    xor al, al                      ; (ZF = 1: stay)
    ret
.out:
    or al, 1                        ; (ZF = 0: leave)
    ret

; rw_fsdac - shades 0-3 as greys at DAC 0-3, the border at 4, the text at 7
rw_fsdac:
    mov dx, 3C8h
    xor al, al
    out dx, al
    inc dx
    mov si, rw_fsgreys
    mov cx, 8 * 3
.d:
    lodsb
    out dx, al
    loop .d
    ret

; rw_fsframe - plane 2 set everywhere but the picture: the border
rw_fsframe:
    mov es, [rw_fsi + FSI_SEG]
    mov dx, 3C4h
    mov ax, 0402h                   ; map mask: plane 2
    out dx, ax
    xor di, di
    mov cx, 40 * 200 / 2
    mov ax, 0FFFFh
    rep stosw
    mov di, RW_FSY * 40 + RW_FSX
    mov bx, 144
    xor ax, ax
.r:
    mov cx, 10
    rep stosw
    add di, 40 - 20
    dec bx
    jnz .r
    ret

; rw_fsdraw - the frame onto VRAM through the shadow, and the speed line
; when F1 has it up and it changed
rw_fsdraw:
    cmp byte [rw_fskind], RW_FSVGA
    je .vga
    jmp rw_fsdrawd
.vga:
    call rw_render                  ; the changed lines, by damage
    mov es, [rw_fsi + FSI_SEG]
    mov dx, 3C4h
    mov ax, 0102h                   ; plane 0: the shade's bit 0
    out dx, ax
    mov si, rw_fbuf
    call rw_fsplane
    mov ax, 0202h                   ; plane 1: bit 1
    out dx, ax
    mov si, rw_fbuf + 20
    call rw_fsplane
    cmp byte [rw_ovl], 0
    je .r
    cmp byte [rw_ovlnew], 0
    je .r
    mov byte [rw_ovlnew], 0
    call rw_fstext
.r:
    ret

; rw_fsplane - one plane of rw_fbuf (SI = its line 0) against the shadow
; beside it in rw_pbuf, the changed words to VRAM. ES = VRAM.
rw_fsplane:
    push dx
    mov bx, si
    add bx, rw_pbuf - rw_fbuf       ; BX = the shadow of the same bytes
    mov di, RW_FSY * 40 + RW_FSX
    xor dx, dx                      ; DL = the line
.l:
    call rw_dchg                    ; a line rb_renderd left alone: past it
    jnz .w0
    add si, 40
    add bx, 40
    add di, 40
    jmp short .nx
.w0:
    mov cx, 10
.w:
    lodsw
    cmp ax, [bx]
    je .s
    mov [bx], ax
    mov [es:di], ax
.s:
    inc bx
    inc bx
    inc di
    inc di
    loop .w
    add si, 20
    add bx, 20
    add di, 40 - 20
.nx:
    inc dl
    cmp dl, 144
    jb .l
    pop dx
    ret

; rw_fstext - rw_ovltxt on the border under the picture, 16 cells wide
rw_fstext:
    mov dx, 3C4h
    mov ax, 0302h                   ; planes 0 and 1: the glyph's set bits
    out dx, ax                      ;   read 7, its clear ones 4
    mov si, rw_ovltxt
    mov di, RW_FSTXT * 40 + RW_FSX
    mov cx, 20
.c:
    lodsb
    or al, al
    jnz .g
    dec si                          ; past the end: blanks
    mov al, ' '
.g:
    push si
    push cx
    sub al, 32
    xor ah, ah
    shl ax, 1
    shl ax, 1
    shl ax, 1
    mov si, rw_font
    add si, ax
    mov cx, 8
    push di
.row:
    movsb
    add di, 40 - 1
    loop .row
    pop di
    inc di
    pop cx
    pop si
    loop .c
    ret

; DAC 0-7, six bits a gun: the shades (0 lightest), the border, -, -, text
rw_fsgreys:
    db 63, 63, 63,  42, 42, 42,  21, 21, 21,  0, 0, 0
    db 4, 4, 8,  0, 0, 0,  0, 0, 0,  48, 48, 52

rw_fsmodes:     db FSXM_VGA0D, FSXM_HERC, FSXM_CGA320

; =============================================================================
; The Hercules and CGA writers (REALBOY-SPEC section 15.1): rb_renderd's
; changed lines, through a table, straight to the page. A Game Boy byte -
; eight pixels, two shade bits each - is two NIBBLE indices, (bit 0's four
; pixels << 4) | bit 1's, and each index is a table entry: on a Hercules two
; bytes, the 2x2 dither's top and bottom rows of those four pixels doubled;
; on a CGA a word, the four pixels doubled in four colours.
; =============================================================================

; rw_fsclear - the page black. ES:DI from rw_fsi.
rw_fsclear:
    mov es, [rw_fsi + FSI_SEG]
    xor di, di
    mov cx, 8000h / 2               ; Hercules' 32KB (CGA's 16KB, twice)
    cmp byte [rw_fskind], RW_FSHERC
    je .c
    mov cx, 4000h / 2
.c:
    xor ax, ax
    rep stosw
    ret

; rw_fstab - rw_htab for the writer: 256 x (row a, row b) bytes for a
; Hercules, 256 words for a CGA
rw_fstab:
    xor bx, bx                      ; BL = the index
.i:
    xor dx, dx                      ; the entry, a pixel at a time
    mov ch, 3                       ; CH = the pixel's bit in each nibble,
.p:                                 ;   the leftmost (3) first
    mov cl, ch
    mov al, bl
    shr al, cl                      ; bit 1's: the low nibble
    and al, 1
    shl al, 1
    mov ah, bl
    add cl, 4
    shr ah, cl                      ; bit 0's: the high nibble
    and ah, 1
    or al, ah                       ; AL = the shade, 0-3
    push bx
    mov bl, al
    xor bh, bh
    cmp byte [rw_fskind], RW_FSHERC
    jne .cga
    shl dl, 1                       ; Hercules: two pixels on each row
    shl dl, 1
    shl dh, 1
    shl dh, 1
    or dl, [rw_hdita + bx]
    or dh, [rw_hditb + bx]
    jmp short .nx
.cga:
    mov cl, 4                       ; CGA: the colour twice, four bits
    shl dx, cl
    or dl, [rw_cgac + bx]
.nx:
    pop bx
    dec ch
    jns .p
    push bx
    xor bh, bh
    shl bx, 1
    cmp byte [rw_fskind], RW_FSHERC
    jne .w
    mov [rw_htab + bx], dl          ; Hercules: row a, then row b
    mov [rw_htab + bx + 1], dh
    jmp short .wd
.w:
    xchg dl, dh                     ; CGA: the left pixels' byte first
    mov [rw_htab + bx], dx
.wd:
    pop bx
    inc bl
    jnz .i
    ret

rw_hdita:       db 3, 3, 2, 0       ; the 2x2 dither, a shade's two pixels
rw_hditb:       db 3, 2, 1, 0       ;   on the top row and on the bottom
rw_cgac:        db 0Fh, 05h, 0Ah, 00h ; shade -> CGA colour, doubled: white,
                                    ;   cyan, magenta, black

; rw_fsdrawd - a frame by damage onto the Hercules or CGA page, and the speed
; line when it changed
rw_fsdrawd:
    call rw_render                  ; AX = the lines that changed
    mov es, [rw_fsi + FSI_SEG]
    or ax, ax
    jz .txt
    xor dl, dl                      ; DL = the line
.l:
    call rw_dchg
    jz .n
    push dx
    mov al, dl
    mov ah, 40
    mul ah
    mov si, rw_fbuf
    add si, ax                      ; SI = the line's two planes
    xor dh, dh
    cmp byte [rw_fskind], RW_FSHERC
    jne .cga
    call rw_hline
    jmp short .p
.cga:
    call rw_cline
.p:
    pop dx
.n:
    inc dl
    cmp dl, 144
    jb .l
.txt:
    cmp byte [rw_ovl], 0
    je .r
    cmp byte [rw_ovlnew], 0
    je .r
    mov byte [rw_ovlnew], 0
    call rw_fstext1
.r:
    ret

; rw_hrow - AX = a Hercules row: DI = its first byte at the picture's column
rw_hrow:
    push ax
    push cx
    push dx
    mov di, ax
    and di, 3
    mov cl, 13
    shl di, cl                      ; the bank: (row AND 3) x 2000h
    mov cl, 2
    shr ax, cl
    mov cx, 90
    mul cx
    add di, ax
    add di, RW_HX
    pop dx
    pop cx
    pop ax
    ret

; rw_hline - DX = a Game Boy line, SI = its planes: Hercules rows HY + 2 x
; line and the one under it, 40 bytes each
rw_hline:
    mov ax, dx
    shl ax, 1
    add ax, RW_HY
    call rw_hrow
    mov bp, di                      ; BP = row a
    inc ax
    call rw_hrow                    ; DI = row b
    xchg bp, di
    mov bx, rw_htab
    mov ch, 20
    mov cl, 4
.b:
    mov al, [si]                    ; bit 0's eight pixels
    mov ah, [si + 20]               ; bit 1's
    inc si
    mov dl, al
    and dl, 0F0h
    mov dh, ah
    shr dh, cl
    or dl, dh                       ; DL = the left four's index
    shl al, cl
    and ah, 0Fh
    or ah, al                       ; AH = the right four's
    mov al, dl
    xor dh, dh
    mov dl, ah                      ; (DL kept: the right index)
    xor ah, ah
    shl ax, 1
    xchg ax, bx
    mov ax, [rw_htab + bx]          ; AL = row a, AH = row b, left four
    xchg ax, bx
    mov [es:di], bl
    mov [es:bp], bh
    mov bl, dl
    xor bh, bh
    shl bx, 1
    mov ax, [rw_htab + bx]          ; ...the right four
    mov [es:di + 1], al
    mov [es:bp + 1], ah
    add di, 2
    add bp, 2
    dec ch
    jnz .b
    ret

; rw_cline - DX = a Game Boy line, SI = its planes: CGA row CY + line, 80
; bytes (even rows at 0, odd at 2000h)
rw_cline:
    mov ax, dx
    add ax, RW_CY
    mov di, ax
    and di, 1
    mov cl, 13
    shl di, cl
    shr ax, 1
    mov cx, 80
    push dx
    mul cx
    pop dx
    add di, ax
    mov ch, 20
    mov cl, 4
.b:
    mov al, [si]
    mov ah, [si + 20]
    inc si
    mov dl, al
    and dl, 0F0h
    mov dh, ah
    shr dh, cl
    or dl, dh                       ; DL = the left four's index
    shl al, cl
    and ah, 0Fh
    or ah, al                       ; AH = the right four's
    mov bl, dl
    xor bh, bh
    shl bx, 1
    mov dx, [rw_htab + bx]
    mov [es:di], dx
    mov bl, ah
    xor bh, bh
    shl bx, 1
    mov dx, [rw_htab + bx]
    mov [es:di + 2], dx
    add di, 4
    dec ch
    jnz .b
    ret

; rw_fstext1 - rw_ovltxt under the picture on a Hercules or CGA page, the
; glyph's set bits lit (a CGA's in colour 3)
rw_fstext1:
    mov si, rw_ovltxt
    xor bx, bx                      ; BX = the cell
.c:
    mov al, [si]
    or al, al
    jnz .g
    mov al, ' '
    dec si
.g:
    inc si
    sub al, 32
    xor ah, ah
    shl ax, 1
    shl ax, 1
    shl ax, 1
    push si
    mov si, rw_font
    add si, ax                      ; SI = its eight rows
    xor cx, cx                      ; CX = the row
.r:
    lodsb
    push cx
    push bx
    cmp byte [rw_fskind], RW_FSHERC
    jne .cg
    mov dl, al
    mov ax, RW_HTXT
    add ax, cx
    call rw_hrow
    add di, bx
    mov [es:di], dl
    jmp short .rn
.cg:
    mov dl, al                      ; eight pixels in colour 3: a word
    xor ax, ax
    mov cx, 8
.x:
    shl ax, 1
    shl ax, 1
    shl dl, 1
    jnc .x0
    or al, 3
.x0:
    loop .x
    xchg al, ah                     ; the left pixels' byte first
    pop bx
    pop cx
    push cx
    push bx
    push ax
    mov ax, RW_CTXT
    add ax, cx
    mov di, ax
    and di, 1
    mov cl, 13
    shl di, cl
    shr ax, 1
    mov cx, 80
    mul cx
    add di, ax
    shl bx, 1
    add di, bx
    add di, 10                      ; the line starts 20 pixels in... x 4
    pop ax
    mov [es:di], ax
.rn:
    pop bx
    pop cx
    inc cx
    cmp cx, 8
    jb .r
    pop si
    inc bx
    cmp bx, 16
    jb .c
    ret

