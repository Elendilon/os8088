; =============================================================================
; os8088 - apps/video/video.asm
;
; VIDEO PLAYER (SPEC.md 98.3): a .V88 file (SPEC.md 98.1) played fullscreen
; at its own frame rate, the decode inside the timer interrupt the way XDC
; (MobyGamer's, MIT, (c) 2014 Jim Leonard) does it, the file read behind it
; through OSAPI_FILE_READ_SEQ. Wave 3 of docs/plans/VIDEO-PLAN.md: SILENT,
; paced by FSXF_RATE (SPEC.md 53.2.2), on a surface of the file's own layout.
;
; THREE PIECES, and where each runs:
;   vp_hook    the FSXF_RATE hook - IRQ0, IF=0 on entry, 48 bytes of stack.
;              It draws the frames that are due, straight into the adapter,
;              from super-packets the reader has already put in memory.
;   vp_main    the bracket's foreground - the UI task, the machine frozen
;              round it. It reads the file into the ring in 32 KB chunks and
;              polls for Esc.
;   the rest   the window: the file's numbers, P to play, and what the last
;              play cost.
;
; THE RING (SPEC.md 98.3). K slots of 32 KB, K a power of two, and a MIRROR
; slot after them: every chunk that lands in slot 0 is copied there too, so a
; super-packet (<= 32 KB) that starts in slot K-1 runs on into the mirror and
; is contiguous. Positions are (chunk, offset) pairs; chunk c lives in slot
; c & (K-1). The reader may fill chunk c only when c < (the hook's
; super-packet's chunk) + K; the hook may enter a super-packet only when
; every chunk it touches has been loaded. [vp_lc], the chunks loaded, is the
; ONE word both sides read, and the reader writes it last.
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'Video Player', vp_entry, 2     ; flags bit 1 = assoc

    OS88_ASSOC16                    ; SPEC.md 54.6: double-click a .V88
    db 1
    OS88_ASSOC_EXT 'V88'
    OS88_ASSOC16_END

VP_CHUNK    equ 32768               ; a ring slot, and a READ_SEQ call
VP_SLOTP    equ VP_CHUNK / 16       ; ...in paragraphs
VP_KMAX     equ 8
VP_COLS     equ 38                  ; the window's text columns
VP_LINES    equ 6
VP_LINE     equ VP_COLS + 1
VP_CONT_W   equ 318                 ; the template's content rect
VP_CONT_H   equ 81

; --- the file (SPEC.md 98.1.1) -------------------------------------------------
V88_FRAMES  equ 8
V88_RATE    equ 12
V88_SPF     equ 14
V88_AUDIO   equ 16
V88_NREND   equ 17
V88_ABYTES  equ 18
V88_PITDIV  equ 20
V88_PITPER  equ 22
V88_TITLE   equ 32
V88_REND    equ 192                 ; rendition 0
R_PIXFMT    equ 0
R_LAYOUT    equ 1
R_WB        equ 2
R_H         equ 4
R_SP0       equ 16
R_SP0N      equ 20
R_SPMAX     equ 22

; =============================================================================
vp_entry:
    call OSAPI_ARG_FILE             ; CF = 1: launched with no document
    jc .nodoc
    mov di, vp_name                 ; ES:SI is the kernel's: copy it out now
    mov cx, 12
.cp:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    or al, al
    jz .cpd
    loop .cp
    mov byte [di], 0
.cpd:
    mov [vp_argdir], dx
    mov [vp_argvol], bl
    mov byte [vp_argpend], 1
.nodoc:
    mov si, vp_tpl
    call OSAPI_WM_CREATE
    jc .fail
    mov [vp_win], bx
    OS88_REGION_MOVABLE             ; SPEC.md 66.6.1.1. A play pins it anyway:
                                    ; the bracket's own frame is on the stack
    mov si, vp_menus
    call OSAPI_MENU_SET
    mov si, vp_about
    call OSAPI_ABOUT_SET
    mov ax, vp_onwake
    call OSAPI_WM_ONWAKE
    mov word [vp_msg], vp_s_none
    call vp_fmt
    mov bx, [vp_win]
    call OSAPI_WM_WAKE              ; the document, and a settled first paint,
    mov bx, [vp_win]                ; from the wake (SPEC.md 54.10)
    clc
    ret
.fail:
    stc
    ret

; --- W_ONWAKE: SI = the window --------------------------------------------------
vp_onwake:
    push ax
    push bx
    push dx
    cmp byte [vp_argpend], 0
    je .paint
    mov byte [vp_argpend], 0
    mov dx, [vp_argdir]             ; where the document is (SPEC.md 54.5)
    mov bl, [vp_argvol]
    call OSAPI_FILE_GOTO_Q
    call OSAPI_GFX_LOCK
    call vp_open
    jmp short .rep
.paint:
    call OSAPI_GFX_LOCK
.rep:
    call vp_repaint
    call OSAPI_GFX_UNLOCK
    pop dx
    pop bx
    pop ax
    ret

; --- the menu and the keys --------------------------------------------------------
vp_oncmd:                           ; AL = item, AH = menu, SI = window
    call vp_abdismiss
    or al, al
    jnz .play
    mov al, FDLG_OPEN
    mov bx, [vp_win]
    mov di, vp_onfile
    xor si, si
    call OSAPI_FILE_DLG
    ret
.play:
    call vp_play
    ret

vp_onkey:                           ; AL = ascii, SI = window
    push ax
    call vp_abdismiss
    jc .out
    or al, 0x20
    cmp al, 'p'
    jne .out
    call vp_play
.out:
    pop ax
    ret

vp_onclick:
    call vp_abdismiss
    ret

; --- the Open dialog's completion: ES:DI = the name, SI = the window ------------
vp_onfile:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov si, di
    mov di, vp_name
    mov cx, 12
.cp:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    or al, al
    jz .cpd
    loop .cp
    mov byte [di], 0
.cpd:
    call vp_open                    ; the dialog left us standing in its
    pop di                          ; folder (SPEC.md 19.2.1)
    pop si
    call vp_repaint
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; vp_open - read and check the header of [vp_name] (SPEC.md 98.1.6)
; out: [vp_ok] = 1 playable here; [vp_msg] says why not. Gfx lock held.
; =============================================================================
vp_open:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov byte [vp_ok], 0
    mov byte [vp_played], 0
    mov byte [vp_loaded], 0
    call OSAPI_FILE_DFREE           ; BX = sectors a cluster
    jc .io
    mov [vp_clsec], bx
    mov ax, bx
    inc ax
    shr ax, 1                       ; ...in KB, for one cluster's claim
    call OSAPI_MEM_CLAIM
    jc .mem
    mov [vp_tmp], dx
    mov es, dx
    xor bx, bx
    mov cx, [vp_clsec]
    mov ax, cx
    mov cl, 9
    shl ax, cl
    mov cx, ax                      ; CX = a cluster in bytes
    xor ax, ax
    xor dx, dx
    mov si, vp_name
    call OSAPI_FILE_READ_AT         ; the header is the file's first sector
    jc .iofree
    or dx, dx
    jnz .have
    cmp ax, 512
    jb .short
.have:
    call vp_parse
    jc .free
    mov byte [vp_loaded], 1
    call vp_canplay
.free:
    mov dx, [vp_tmp]
    call OSAPI_MEM_FREE
    jmp short .out
.short:
    mov word [vp_msg], vp_s_notv88
    jmp short .free
.iofree:
    mov word [vp_msg], vp_s_io
    jmp short .free
.io:
    mov word [vp_msg], vp_s_io
    jmp short .out
.mem:
    mov word [vp_msg], vp_s_mem
.out:
    call vp_fmt
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vp_parse - ES:0 = the header. CF=1 with [vp_msg] set when it refuses
vp_parse:
    mov word [vp_msg], vp_s_notv88
    cmp word [es:0], 'V8'
    jne .bad
    cmp word [es:2], '8' + (0x1A << 8)
    jne .bad
    mov word [vp_msg], vp_s_ver
    cmp word [es:4], 1              ; version 1, no flags
    jne .bad
    cmp word [es:6], 0
    jne .bad
    mov word [vp_msg], vp_s_bad
    cmp word [es:V88_FRAMES+2], 0   ; this player counts frames in a word
    jne .long
    mov ax, [es:V88_FRAMES]
    or ax, ax
    jz .bad
    mov [vp_frames], ax
    mov ax, [es:V88_RATE]
    or ax, ax
    jz .bad
    mov [vp_rate], ax
    mov ax, [es:V88_SPF]
    or ax, ax
    jz .bad
    mov [vp_spf], ax
    mov al, [es:V88_AUDIO]          ; none, or PCM8 with a chunk a sample a
    cmp al, 1                       ; frame. The sound itself is wave 4's: it
    ja .bad                         ; is skipped, not played
    xor bx, bx
    or al, al
    jz .aud
    mov bx, [vp_spf]
.aud:
    cmp bx, [es:V88_ABYTES]
    jne .bad
    mov [vp_abytes], bx
    mov al, [es:V88_NREND]
    dec al
    cmp al, 3
    ja .bad
    mov ax, [es:V88_PITDIV]
    cmp ax, FSX_RATE_MIN
    jb .bad
    mov [vp_pitdiv], ax
    mov al, [es:V88_PITPER]
    or al, al
    jz .bad
    mov [vp_pitper], al
    mov al, [es:V88_REND+R_PIXFMT]
    dec al
    cmp al, 1
    ja .bad
    mov [vp_pixfmt], al
    mov bl, [es:V88_REND+R_LAYOUT]  ; 1..3, and the canvas inside it
    dec bl
    cmp bl, 2
    ja .bad
    mov [vp_layout], bl
    xor bh, bh
    mov ax, bx
    shl bx, 1
    add bx, ax
    shl bx, 1                       ; BX = layout * 6
    mov ax, [es:V88_REND+R_WB]
    or ax, ax
    jz .bad
    cmp ax, [vp_laytab+bx+2]        ; stride
    ja .bad
    mov [vp_wb], ax
    mov ax, [es:V88_REND+R_H]
    or ax, ax
    jz .bad
    cmp ax, [vp_laytab+bx+4]        ; rows
    ja .bad
    mov [vp_h], ax
    mov ax, [es:V88_REND+R_SP0]
    test ax, 511
    jnz .bad
    mov [vp_sp0], ax
    mov ax, [es:V88_REND+R_SP0+2]
    mov [vp_sp0+2], ax
    mov ax, [es:V88_REND+R_SP0N]
    dec ax
    cmp ax, 63
    ja .bad
    inc ax
    mov [vp_sp0n], ax
    mov ax, [es:V88_REND+R_SPMAX]
    dec ax
    cmp ax, 63
    ja .bad
    push ds                         ; the title, NUL-terminated within its 48
    push es
    push ds
    push es
    pop ds
    pop es
    mov si, V88_TITLE
    mov di, vp_title
    mov cx, VP_COLS
.t:
    lodsb
    stosb
    or al, al
    jz .td
    loop .t
    mov byte [es:di], 0
.td:
    pop es
    pop ds
    clc
    ret
.long:
    mov word [vp_msg], vp_s_long
.bad:
    stc
    ret

; vp_canplay - can THIS display set the file's layout's mode? (SPEC.md 98.3)
vp_canplay:
    mov bl, [vp_layout]
    xor bh, bh
    mov ax, bx
    shl bx, 1
    add bx, ax
    shl bx, 1
    mov al, [vp_laytab+bx]          ; the FSXM id
    mov [vp_mode], al
    mov cl, al
    mov bx, [vp_win]
    call OSAPI_FSX_CAPS             ; AX = the modes this window's display has
    shr ax, cl
    test al, 1
    jz .no
    mov byte [vp_ok], 1
    mov word [vp_msg], vp_s_ready
    ret
.no:
    mov bl, [vp_layout]             ; "made for <layout>": the shadow path that
    xor bh, bh                      ; would show it here is wave 5's
    shl bx, 1
    mov ax, [vp_laynotab+bx]
    mov [vp_msg], ax
    ret

; =============================================================================
; vp_play - the fullscreen play (SPEC.md 98.3). Gfx lock held, SI = window
; =============================================================================
vp_play:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    cmp byte [vp_ok], 1
    jne .out
    ; --- the ring: K slots and the mirror, K a power of two, 2..VP_KMAX
    call OSAPI_MEM_AVAIL            ; AX = the largest free run, KB
    mov cl, 5
    shr ax, cl                      ; ...in 32 KB slots
    dec ax                          ; less the mirror
    mov cx, [vp_kmax]
.k:
    cmp cx, ax
    jbe .kfit
    shr cx, 1
    jmp short .k
.kfit:
    cmp cx, 2
    jae .kok
    mov word [vp_msg], vp_s_mem
    jmp .done
.kok:
    mov [vp_k], cx
    dec cx
    mov [vp_kmask], cx              ; chunk -> slot
    inc cx
    mov ax, cx
    inc ax
    mov cl, 5
    shl ax, cl                      ; (K + 1) x 32 KB
    call OSAPI_MEM_CLAIM
    jnc .ring
    mov word [vp_msg], vp_s_mem
    jmp .done
.ring:
    mov [vp_ring], dx
    ; --- the reader: from the cluster boundary under the stream's start
    mov ax, [vp_clsec]
    mov cl, 9
    shl ax, cl
    dec ax                          ; a cluster's mask
    mov bx, [vp_sp0]
    and bx, ax                      ; BX = how far the stream is into it
    push ds
    pop es
    mov di, vp_cur
    xor ax, ax
    mov cx, FSEQ_SIZE / 2
    cld
    rep stosw
    mov ax, [vp_sp0]
    sub ax, bx
    mov [vp_cur+FSEQ_OFF], ax
    mov ax, [vp_sp0+2]
    mov [vp_cur+FSEQ_OFF+2], ax
    ; --- the hook's state: before the first super-packet
    xor ax, ax
    mov [vp_lc], ax
    mov [vp_pc], ax
    mov [vp_po], bx
    mov [vp_fleft], ax
    mov [vp_owed], ax
    mov [vp_done], ax
    mov [vp_stall], ax
    mov [vp_late], ax
    mov [vp_dt], ax
    mov [vp_ready], al
    mov [vp_end], al
    mov [vp_eof], al
    mov [vp_err], al
    mov [vp_held], al
    mov ax, [vp_sp0n]
    mov [vp_psec], ax               ; the first super-packet, not yet entered
    ; --- and in
    mov bx, [vp_win]
    mov ax, vp_main
    mov cx, FSXF_RATE
    mov dx, [vp_pitdiv]
    mov di, vp_hook
    call OSAPI_FSX_RUN
    jnc .ran
    mov word [vp_msg], vp_s_refused
    jmp short .freering
.ran:
    mov byte [vp_played], 1
    mov word [vp_msg], vp_s_ready
    cmp byte [vp_err], 0
    je .freering
    mov ax, [vp_errmsg]
    mov [vp_msg], ax
.freering:
    mov dx, [vp_ring]
    call OSAPI_MEM_FREE
.done:
    call vp_fmt                     ; SI is still the window: fsx_run keeps
    call vp_repaint                 ; every register
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; vp_main - the bracket (SPEC.md 53.1): SI = window, DS = CS = ours
; =============================================================================
vp_main:
    push ds
    pop es
    mov di, vp_fsi
    mov al, [vp_mode]
    call OSAPI_FSX_MODE
    jnc .mode
    mov byte [vp_err], 1
    mov word [vp_errmsg], vp_s_refused
    ret
.mode:
    mov ax, [vp_fsi+FSI_SEG]
    mov [vp_vseg], ax
    ; the origin: centred, the row on a bank (SPEC.md 98.1.2)
    mov bl, [vp_layout]
    xor bh, bh
    mov ax, bx
    shl bx, 1
    add bx, ax
    shl bx, 1
    mov ax, [vp_laytab+bx+4]        ; rows
    sub ax, [vp_h]
    shr ax, 1                       ; y0
    xor dx, dx
    mov cl, [vp_laytab+bx+1]        ; banks
    xor ch, ch
    div cx                          ; AX = y0 / banks, rounded down
    mul word [vp_laytab+bx+2]       ; ...rows of stride
    mov cx, [vp_laytab+bx+2]
    sub cx, [vp_wb]
    shr cx, 1                       ; x0
    add ax, cx
    mov [vp_org], ax
.pre:                               ; fill the ring before the first frame: a
    call vp_fill                    ; stream that fits is read whole
    jnc .pre
    call OSAPI_GET_TICKS
    mov [vp_t0], ax
    mov byte [vp_ready], 1
.loop:
    mov ah, 1                       ; the bracket's input model: poll int 16h
    int 0x16                        ; (this IS the UI task, SPEC.md 53.1)
    jz .nokey
    xor ah, ah
    int 0x16
    cmp al, 27                      ; Esc stops, at any frame rate
    je .stop
.nokey:
    cmp byte [vp_end], 0
    jne .stop
    call vp_fill
    jnc .loop                       ; a chunk arrived: poll, and try again
    mov al, FSXW_FRAME              ; nothing to read yet: give the period
    call OSAPI_FSX_WAIT             ; to the hook
    jmp short .loop
.stop:
    pushf
    cli
    mov byte [vp_ready], 0
    popf
    call OSAPI_GET_TICKS
    sub ax, [vp_t0]
    mov [vp_dt], ax
    ret

; -----------------------------------------------------------------------------
; vp_fill - read the next chunk into its slot, if the hook has left it
; out: CF=0 one arrived; CF=1 none could be read now (ring full, or the end)
; -----------------------------------------------------------------------------
vp_fill:
    cmp byte [vp_eof], 0
    jne .none
    mov ax, [vp_lc]                 ; the chunk to read
    mov bx, [vp_pc]                 ; the hook's super-packet's chunk: its slot
    add bx, [vp_k]                  ; and every one after it are still live
    cmp ax, bx
    jae .none
    mov bx, [vp_k]
    dec bx
    and bx, ax                      ; its slot
    mov cl, 11
    shl bx, cl
    add bx, [vp_ring]
    mov dx, bx                      ; DX:BX = the slot, ES:DI = the cursor
    xor bx, bx
    mov cx, VP_CHUNK
    push ds
    pop es
    mov di, vp_cur
    mov si, vp_name
    call OSAPI_FILE_READ_SEQ
    jnc .got
    mov byte [vp_err], 1
    mov word [vp_errmsg], vp_s_io
    mov byte [vp_end], 1
    stc
    ret
.got:
    cmp ax, VP_CHUNK
    je .full
    mov byte [vp_eof], 1            ; the stream's last, short chunk
.full:
    mov ax, [vp_lc]
    mov bx, [vp_k]
    dec bx
    test ax, bx
    jnz .pub
    push ds                         ; slot 0 is copied to the MIRROR, so a
    mov ax, [vp_ring]               ; super-packet starting in slot K-1 runs on
    mov bx, [vp_k]                  ; into contiguous memory
    mov cl, 11
    shl bx, cl
    add bx, ax
    mov es, bx
    mov ds, ax
    xor si, si
    xor di, di
    mov cx, VP_CHUNK / 2
    cld
    rep movsw
    pop ds
.pub:
    inc word [vp_lc]                ; ...and published LAST
    clc
    ret
.none:
    stc
    ret

; =============================================================================
; vp_hook - FSXF_RATE's hook (SPEC.md 53.2.2, 98.3)
; in:  AX = periods since the last call; DS = ours; IF=0
; A frame is due every [vp_pitper] periods. At most two are drawn a call - one
; due and one owed - and the rest are counted LATE and forgiven: a delta frame
; cannot be skipped, so falling behind is paid for by the picture running
; slow, never by a wrong picture.
; =============================================================================
vp_hook:
    cmp byte [vp_ready], 0
    je .ret
    add [vp_owed], ax
    mov bl, [vp_pitper]
    xor bh, bh
    xor cx, cx
.due:
    cmp [vp_owed], bx
    jb .go
    sub [vp_owed], bx
    inc cx
    jmp short .due
.go:
    jcxz .ret
    cmp cx, 2
    jbe .n
    sub cx, 2
    add [vp_late], cx
    mov cx, 2
.n:
    sti                             ; a disk's completion is not held behind a
.f:                                 ; frame (SPEC.md 53.2.2 allows it)
    push cx
    call vp_frame
    pop cx
    jc .stop
    loop .f
.stop:
    cli
.ret:
    ret

; vp_frame - draw the next frame. CF=1 it did not (stalled, held, ended)
vp_frame:
    cmp byte [vp_end], 0
    jne .no
    mov ax, [vp_done]
    cmp ax, [vp_stopat]             ; the gate's hold (tests/vidplay.py):
    jne .go                         ; stop BEFORE this frame, the screen being
    mov byte [vp_held], 1           ; the host's frame [vp_stopat]-1
.no:
    stc
    ret
.go:
    cmp word [vp_fleft], 0
    jne .rec
    ; --- ENTER the super-packet at (vp_pc, vp_po), vp_psec sectors: all of it
    ;     loaded, or wait. (vp_pc, vp_po) moved here the moment the one before
    ;     it ended, so the reader is never held up by a finished one
    mov cx, [vp_psec]
    or cx, cx
    jnz .sp
    jmp .theend                     ; the chain's 0: the end of the stream
.sp:
    mov dx, cx
    mov cl, 9
    shl dx, cl                      ; its bytes (<= 32768)
    add dx, [vp_po]                 ; where it ends, from its chunk's start
    mov di, [vp_pc]
    cmp dx, VP_CHUNK
    jbe .one
    inc di                          ; ...in the next chunk
.one:
    cmp di, [vp_lc]
    jae .stall
    mov ax, [vp_pc]
    mov bx, [vp_po]
    call vp_addr                    ; DX:SI = the super-packet
    push ds
    mov ds, dx
    lodsw
    mov cx, ax                      ; frames
    lodsw                           ; next
    pop ds
    jcxz .bsp                       ; no frames, or a next past 64 sectors
    cmp ax, 64
    jbe .spok
.bsp:
    jmp .badsp
.spok:
    mov [vp_fleft], cx
    mov [vp_nsec], ax
    mov word [vp_rofs], 4
.rec:
    ; --- the record at [vp_rofs] into the super-packet
    mov ax, [vp_pc]
    mov bx, [vp_po]
    add bx, [vp_rofs]
    cmp bx, VP_CHUNK
    jb .ra
    sub bx, VP_CHUNK
    inc ax
.ra:
    call vp_addr                    ; DX:SI = the record
    push ds
    mov ds, dx
    mov cx, [si]                    ; its len...
    pop ds
    mov ax, [vp_psec]               ; ...against what is left of the
    mov di, ax                      ; super-packet
    push cx
    mov cl, 9
    shl di, cl
    pop cx
    sub di, [vp_rofs]
    cmp cx, di
    ja .badrec
    mov ax, [vp_abytes]
    add ax, 6 + 10
    cmp cx, ax
    jb .badrec
    add [vp_rofs], cx
    dec word [vp_fleft]
    jnz .dec
    push cx                         ; ITS LAST FRAME: step to the next one's
    mov ax, [vp_psec]               ; start now - the reader may reuse this
    mov cl, 9                       ; one's chunks from here, and waiting for
    shl ax, cl                      ; the hook to ENTER the next one was a
    add ax, [vp_po]                 ; deadlock (a super-packet that needs a
    cmp ax, VP_CHUNK                ; chunk the reader may not read until
    jb .same                        ; this one is left)
    sub ax, VP_CHUNK
    inc word [vp_pc]
.same:
    mov [vp_po], ax
    mov ax, [vp_nsec]
    mov [vp_psec], ax
    pop cx
.dec:
    add si, 6
    mov es, [vp_vseg]
    mov bp, [vp_org]
    push ds
    mov ds, dx
    call vd_native                  ; the lists, onto the adapter
    pop ds
    inc word [vp_done]
    clc
    ret
.stall:
    inc word [vp_stall]
    stc
    ret
.theend:
    mov byte [vp_end], 1
    stc
    ret
.badsp:
    mov word [vp_errmsg], vp_s_badsp
    jmp short .err
.badrec:
    mov word [vp_errmsg], vp_s_badrec
.err:
    mov byte [vp_err], 1
    mov byte [vp_end], 1
    stc
    ret

; vp_addr - AX = a chunk, BX = an offset in it -> DX:SI, a far pointer
; (clobbers AX, BX, CX)
vp_addr:
    and ax, [vp_kmask]
    mov cl, 11
    shl ax, cl
    add ax, [vp_ring]
    mov si, bx
    mov cl, 4
    shr bx, cl
    add ax, bx
    mov dx, ax
    and si, 15
    ret

%include "video/vdec.inc"

; =============================================================================
; the window
; =============================================================================
vp_paint:                           ; W_PAINT: SI = window, region armed
    push ax
    push bx
    push cx
    push dx
    push si
    mov bx, si
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    mov cx, ax
    add cx, 4
    add dx, 6
    mov si, vp_lines
    mov bx, VP_LINES
.l:
    mov ax, (CWHITE << 8) | CBLACK  ; one opaque run a line, each the full
    call OSAPI_FONT_RUN             ; width, so nothing needs erasing first
    add si, VP_LINE                 ; (PERFORMANCE.md rule 2)
    add dx, 12
    dec bx
    jnz .l
    pop si
    push si
    cmp byte [vp_abon], 0
    je .out
    mov bx, si
    mov si, vp_ablines
    call os88ui_about_d
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

vp_repaint:                         ; SI = window, lock held, no region armed
    push bx
    mov bx, si
    call OSAPI_WM_CLIP_SET
    jc .gone
    call vp_paint
.gone:
    pop bx
    ret

vp_about:                           ; OSAPI_ABOUT_SET's handler: SI = window
    push bx
    push si
    mov byte [vp_abon], 1
    mov bx, si
    mov si, vp_ablines
    call os88ui_about
    pop si
    pop bx
    ret

vp_abdismiss:                       ; CF=1: the click went on the card
    cmp byte [vp_abon], 0
    je .none
    mov byte [vp_abon], 0
    call vp_repaint
    stc
    ret
.none:
    clc
    ret

; -----------------------------------------------------------------------------
; vp_fmt - the six lines, each padded to the width (opaque runs, no erase)
; -----------------------------------------------------------------------------
vp_fmt:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    cld
    mov di, vp_lines                ; blank every line first
    mov bx, VP_LINES
.bl:
    mov al, ' '
    mov cx, VP_COLS
    rep stosb
    xor al, al
    stosb
    dec bx
    jnz .bl
    ; 0: the file
    mov di, vp_lines
    mov si, vp_s_file
    call vp_puts
    mov si, vp_name
    cmp byte [si], 0
    jne .nm
    mov si, vp_s_nofile
.nm:
    call vp_puts
    cmp byte [vp_loaded], 0
    je .msg
    ; 1: the title
    mov di, vp_lines + VP_LINE
    mov si, vp_title
    call vp_puts
    ; 2: the canvas, the rate, the length
    mov di, vp_lines + 2 * VP_LINE
    mov ax, [vp_wb]
    mov cl, 3
    shl ax, cl
    xor dx, dx
    xor bl, bl
    call vp_putn
    mov al, 'x'
    call vp_putc
    mov ax, [vp_h]
    xor dx, dx
    call vp_putn
    mov al, ' '
    call vp_putc
    mov bl, [vp_layout]
    xor bh, bh
    shl bx, 1
    mov si, [vp_laynames+bx]
    call vp_puts
    mov ax, [vp_rate]               ; fps to two places: rate x 100 / spf
    mov cx, 100
    mul cx
    div word [vp_spf]
    xor dx, dx
    mov bl, 2
    call vp_putn
    mov si, vp_s_fps
    call vp_puts
    mov ax, [vp_frames]
    xor dx, dx
    xor bl, bl
    call vp_putn
    mov si, vp_s_fr
    call vp_puts
.msg:
    ; 3: what P does, or why not
    mov di, vp_lines + 3 * VP_LINE
    mov si, [vp_msg]
    call vp_puts
    cmp byte [vp_played], 0
    je .out
    ; 4: frames drawn, stalls
    mov di, vp_lines + 4 * VP_LINE
    mov si, vp_s_drew
    call vp_puts
    mov ax, [vp_done]
    xor dx, dx
    xor bl, bl
    call vp_putn
    mov si, vp_s_of
    call vp_puts
    mov ax, [vp_frames]
    xor dx, dx
    call vp_putn
    mov si, vp_s_stall
    call vp_puts
    mov ax, [vp_stall]
    xor dx, dx
    call vp_putn
    ; 5: late, and the time against the file's
    mov di, vp_lines + 5 * VP_LINE
    mov si, vp_s_late
    call vp_puts
    mov ax, [vp_late]
    xor dx, dx
    xor bl, bl
    call vp_putn
    mov si, vp_s_ticks
    call vp_puts
    mov ax, [vp_dt]
    xor dx, dx
    call vp_putn
    mov si, vp_s_want
    call vp_puts
    mov ax, [vp_done]               ; the ticks those frames should have
    mul word [vp_spf]               ; taken: frames x spf / 10 x 182 / rate,
    mov cx, 10                      ; in that order so every step fits 32
    call vp_div32                   ; bits (65,535 x 920 / 10 x 182 < 2^31)
    mov cx, 182
    call vp_mul32
    mov cx, [vp_rate]
    call vp_div32
    xor bl, bl
    call vp_putn
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vp_puts - SI = NUL string -> DI, stopping at the line's end (DI's own NUL)
vp_puts:
    push ax
.l:
    lodsb
    or al, al
    jz .out
    call vp_putc
    jmp short .l
.out:
    pop ax
    ret

; vp_putc - AL -> [DI] unless DI is on its line's NUL
vp_putc:
    cmp byte [di], 0
    je .full
    stosb
.full:
    ret

; vp_putn - DX:AX unsigned, BL decimals -> DI
vp_putn:
    push ax
    push bx
    push cx
    push dx
    xor bh, bh                      ; BH = digits emitted
.d:
    ; STKBALANCE-LOOP: one digit (and the point) pushed a turn and the second loop pops them; the count is in BH
    mov cx, 10
    call vp_div32                   ; DX:AX /= 10, CX = the digit
    push cx
    inc bh
    cmp bh, bl
    jne .nopt
    mov cx, '.' - '0'               ; (no push imm on an 8086)
    push cx
    inc bh
.nopt:
    mov cx, ax
    or cx, dx
    jnz .d
    or bl, bl                       ; ...and with decimals, at least one digit
    jz .o                           ; before the point: "0.05", not ".05"
    mov cl, bl
    inc cl
    cmp bh, cl
    jbe .d
.o:
    pop ax
    add al, '0'
    call vp_putc
    dec bh
    jnz .o
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vp_div32 - DX:AX /= CX; CX = the remainder
vp_div32:
    push bx
    mov bx, ax
    mov ax, dx
    xor dx, dx
    div cx
    xchg ax, bx
    div cx
    mov cx, dx
    mov dx, bx
    pop bx
    ret

; vp_mul32 - DX:AX *= CX (the product must fit 32 bits)
vp_mul32:
    push bx
    mov bx, dx
    mul cx
    push dx
    push ax
    mov ax, bx
    mul cx
    pop bx                          ; the low product's low word
    pop dx                          ; ...and high
    add dx, ax
    mov ax, bx
    pop bx
    ret

; =============================================================================
; data
; =============================================================================
vp_tpl:
    dw 160, 90, 320, 100            ; content 318 x 81
    dw vp_ttl, vp_paint, vp_onkey, vp_onclick

    OS88_MENUSET vp_menus, vp_ttl, vp_oncmd
        OS88_MENU vp_m_file, vp_i_file, 2
    OS88_MENUSET_END vp_menus
vp_ttl:       db 'Video Player', 0
vp_m_file:    db 'File', 0
vp_i_file:    dw vp_it_open, vp_it_play
vp_it_open:   db 'Open...', 0
vp_it_play:   db 'Play (P)', 0

vp_ablines:   dw vp_ab1, vp_ab2, vp_ab3, vp_ab4, 0
vp_ab1:       db 'Video Player for os8088', 0
vp_ab2:       db 0
vp_ab3:       db 'After XDC, by Jim Leonard', 0
vp_ab4:       db '(MobyGamer), MIT', 0

; per layout (SPEC.md 98.1.2): FSXM id, banks, stride, rows
vp_laytab:
    db FSXM_CGA640, 2
    dw 80, 200
    db FSXM_HERC, 4
    dw 90, 348
    db FSXM_VGA12, 1
    dw 80, 480
vp_laynames:  dw vp_s_cga, vp_s_herc, vp_s_vga
vp_laynotab:  dw vp_s_nocga, vp_s_noherc, vp_s_novga
vp_s_cga:     db 'CGA  ', 0
vp_s_herc:    db 'Herc  ', 0
vp_s_vga:     db 'VGA  ', 0

vp_s_file:    db 'File: ', 0
vp_s_nofile:  db '(none) - File > Open...', 0
vp_s_none:    db 'Open a .V88 to play it', 0
vp_s_ready:   db 'P plays it fullscreen; Esc stops', 0
vp_s_notv88:  db 'Not a .V88 video', 0
vp_s_ver:     db 'A newer .V88 than this player', 0
vp_s_bad:     db 'This .V88 is damaged', 0
vp_s_long:    db 'Over 65,535 frames: too long', 0
vp_s_io:      db 'The disk could not be read', 0
vp_s_mem:     db 'Not enough memory to play it', 0
vp_s_refused: db 'The screen could not be taken', 0
vp_s_badsp:   db 'Stopped: a damaged super-packet', 0
vp_s_badrec:  db 'Stopped: a damaged frame', 0
vp_s_nocga:   db 'Made for CGA; not on this screen', 0
vp_s_noherc:  db 'Made for Hercules; not this screen', 0
vp_s_novga:   db 'Made for VGA; not on this screen', 0
vp_s_fps:     db ' fps  ', 0
vp_s_fr:      db ' fr', 0
vp_s_drew:    db 'Drew ', 0
vp_s_of:      db ' of ', 0
vp_s_stall:   db ', stalls ', 0
vp_s_late:    db 'Late ', 0
vp_s_ticks:   db ', ', 0
vp_s_want:    db ' ticks of ', 0

; --- state ------------------------------------------------------------------------
vp_kmax:      dw VP_KMAX            ; the ring's most slots (a test may lower it)
vp_stopat:    dw 0xFFFF             ; the gate's hold: stop before this frame
vp_win:       dw 0
vp_msg:       dw 0
vp_errmsg:    dw 0
vp_argdir:    dw 0
vp_argvol:    db 0
vp_argpend:   db 0
vp_abon:      db 0
vp_ok:        db 0
vp_loaded:    db 0
vp_played:    db 0
vp_mode:      db 0
vp_layout:    db 0
vp_pixfmt:    db 0
vp_pitper:    db 0
vp_name:      times 13 db 0
vp_title:     times VP_COLS + 1 db 0
vp_frames:    dw 0
vp_rate:      dw 0
vp_spf:       dw 0
vp_abytes:    dw 0
vp_pitdiv:    dw 0
vp_wb:        dw 0
vp_h:         dw 0
vp_sp0:       dw 0, 0
vp_sp0n:      dw 0
vp_clsec:     dw 0
vp_tmp:       dw 0
; the play
vp_ring:      dw 0
vp_k:         dw 0
vp_kmask:     dw 0
vp_vseg:      dw 0
vp_org:       dw 0
vp_t0:        dw 0
vp_dt:        dw 0
vp_lc:        dw 0                  ; chunks loaded - the one shared word
vp_pc:        dw 0                  ; the hook's super-packet: chunk...
vp_po:        dw 0                  ; ...offset...
vp_psec:      dw 0                  ; ...sectors (0 = the end)
vp_nsec:      dw 0                  ; the one after it
vp_fleft:     dw 0                  ; frames left in it
vp_rofs:      dw 0                  ; the next record, into it
vp_owed:      dw 0
vp_done:      dw 0
vp_stall:     dw 0
vp_late:      dw 0
vp_ready:     db 0
vp_end:       db 0
vp_eof:       db 0
vp_err:       db 0
vp_held:      db 0
vp_fsi:       times FSI_SIZE db 0
vp_cur:       times FSEQ_SIZE db 0
vp_lines:     times VP_LINES * VP_LINE db 0

%define OS88UI_ABOUT
%define OS88UI_NOBTN
%include "os88ui.inc"

    OS88_BSS 0
    OS88_IMAGE_END
