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
VP_RL       equ 16384               ; the audio ring (SPEC.md 98.3.1)...
VP_RLCODE   equ 2                   ; ...4096 << 2
VP_BLOCK    equ 2048                ; the card's block: one interrupt each
VP_AMAX     equ 4                   ; frames of audio a hook call puts in
VP_SKIPMAX  equ 8                   ; shadow copies a play behind may skip
VP_SLOTP    equ VP_CHUNK / 16       ; ...in paragraphs
VP_KMAX     equ 8
VP_COLS     equ 35                  ; the info panel's text columns
VP_LINES    equ 8
VP_LINE     equ VP_COLS + 1
VP_LPITCH   equ 11                  ; ...and its line pitch
; --- the window (SPEC.md 98.4): content-relative, every x a byte's -----------
VP_CONT_W   equ 628                 ; the template's content rect: it fits
VP_CONT_H   equ 126                 ; CGA's 156-row desktop band, title and all
VP_BOXX     equ 8                   ; the poster box's inside
VP_BOXY     equ 6
VP_BOXW     equ 320
VP_BOXH     equ 100
VP_BARY     equ 112                 ; the scrub bar's frame, top row
VP_BARH     equ 10                  ; ...and its height, frame included
VP_THW      equ 8                   ; the thumb's width
VP_TXTX     equ 344                 ; the info panel
VP_TXTY     equ 6
VP_BTX      equ 344                 ; the buttons: first one's x, the row's y,
VP_BTY      equ 96
VP_BTW      equ 28                  ; ...a button's size, and the pitch
VP_BTH      equ 20                  ; (Tracker's transport, SPEC.md 45)
VP_BTP      equ 32
VP_NB       equ 4                   ; Open, previous key, Play, next key
VP_KMAXREC  equ 49152               ; the largest keyframe record we will read

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
R_KTAB      equ 8
R_NKEYS     equ 12
R_POSTER    equ 14
R_SP0       equ 16
R_SP0N      equ 20
R_SPMAX     equ 22
R_SLEN      equ 24
R_KMAX      equ 30
; a keyframe table entry (SPEC.md 98.1.3), as vp_ke holds it
KE_K        equ 0
KE_OFF      equ 4
KE_LEN      equ 8
KE_SP       equ 10
KE_SECS     equ 14
KE_IDX      equ 15

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
    push bx                         ; THE BUTTONS' GESTURE (SPEC.md 20.5.1.3):
    mov ax, bx                      ; press inverts, release fires, a slide
    mov bx, vp_btns                 ; off cancels
    mov si, vp_onup
    mov di, vp_ondrag
    mov dx, vp_onclick              ; ...a press on no button: the scrub bar
    call os88ui_btninit
    pop bx
    mov ax, vp_clickw               ; ...and the press reaches US first, so the
    call OSAPI_WM_ONCLICK           ; rects are where the window is NOW
    call vp_mkdtab
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

; --- the menu, the keys and the buttons (SPEC.md 98.4) ---------------------------
vp_oncmd:                           ; AL = item, AH = menu, SI = window
    call vp_abdismiss
    or al, al
    jz vp_opendlg
    cmp al, 1
    jne vp_menustep
    jmp vp_play

vp_menustep:                        ; AL = 2 or 3: the key before or after
    cmp al, 2
    mov ax, -1
    je .s
    mov ax, 1
.s:
    jmp vp_step

vp_opendlg:
    mov al, FDLG_OPEN
    mov bx, [vp_win]
    mov di, vp_onfile
    xor si, si
    call OSAPI_FILE_DLG
    ret

vp_onkey:                           ; AL = ascii, AH = scan, SI = window
    push ax
    call vp_abdismiss
    jc .out
    cmp ah, KSC_LEFT
    je .prev
    cmp ah, KSC_RIGHT
    je .next
    cmp al, 13                      ; Enter, Space or P plays
    je .play
    cmp al, ' '
    je .play
    or al, 0x20
    cmp al, 'p'
    jne .out
.play:
    call vp_play
    jmp short .out
.prev:
    mov ax, -1
    jmp short .step
.next:
    mov ax, 1
.step:
    call vp_step
.out:
    pop ax
    ret

; W_ONCLICK: the rects where the window IS, then the library, which hands a
; press on no button to vp_onclick (SPEC.md 20.5.1.3.3)
vp_clickw:
    call vp_abdismiss
    jc .out
    call vp_track
    call vp_clip
    jmp os88ui_btnclick
.out:
    ret

vp_ondrag:
    push bx
    call vp_clip
    mov bx, vp_btns
    call os88ui_btndrag             ; the pressed button follows the pointer
    pop bx
    ret

vp_onup:                            ; W_ONMOUSEUP: the button FIRES here
    push ax
    push bx
    push si
    call vp_track
    call vp_clip
    mov bx, vp_btns
    call os88ui_btnup               ; AX = the button, index + 1, or 0
    mov si, [vp_win]
    dec ax
    js .out
    jz .open
    dec ax
    jz .prev
    dec ax
    jz .play
    mov ax, 1
    jmp short .step
.prev:
    mov ax, -1
.step:
    call vp_step
    jmp short .out
.play:
    call vp_play
    jmp short .out
.open:
    call vp_opendlg
.out:
    pop si
    pop bx
    pop ax
    ret

; a press on no button: on the scrub bar it picks the keyframe under it
vp_onclick:                         ; CX = x, DX = y (screen), SI = window
    push ax
    push bx
    push cx
    push dx
    cmp word [vp_nkeys], 0
    je .out
    mov ax, dx
    sub ax, [vp_cy0]
    sub ax, VP_BARY
    cmp ax, VP_BARH
    jae .out
    mov ax, cx
    sub ax, [vp_cx0]
    sub ax, VP_BOXX
    cmp ax, VP_BOXW
    jae .out
    mul word [vp_nkeys]             ; the key whose share of the bar it is
    mov cx, VP_BOXW
    div cx
    call vp_seekto
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vp_step - AX = -1 or +1: the key before or after the one picked
vp_step:
    push ax
    add ax, [vp_sel]
    js .out
    call vp_seekto
.out:
    pop ax
    ret

; vp_seekto - AX = a keyframe: the play starts there (98.3.5), and the box
; shows it. Lock held, SI = window
vp_seekto:
    push ax
    push bx
    cmp ax, [vp_nkeys]
    jae .out
    call vp_loadkey
    cmp ax, [vp_kload]              ; its entry is what the play needs; a
    jne .fail                       ; picture that would not fit is only black
    mov [vp_sel], ax
    call vp_fmt
    jmp short .paint
.fail:
    mov word [vp_msg], vp_s_kbad
    call vp_fmt
.paint:
    mov bx, [vp_win]
    call OSAPI_WM_CLIP_SET
    jc .out
    call vp_track
    call vp_pposter
    call vp_pbar
    mov bx, 4                       ; the lines a key changes, and the buttons
    call vp_ptext
    call vp_buttons
.out:
    pop bx
    pop ax
    ret

vp_clip:
    push bx
    mov bx, [vp_win]
    call OSAPI_WM_CLIP_SET
    pop bx
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
    call vp_pfree                   ; the last file's poster, and its keys
    xor ax, ax
    mov [vp_nkeys], ax
    mov [vp_sel], ax
    dec ax
    mov [vp_kload], ax
    call OSAPI_FILE_DFREE           ; BX = sectors a cluster
    jc .io
    mov [vp_clsec], bx
    mov ax, bx
    mov cl, 9
    shl ax, cl
    mov [vp_clb], ax                ; ...and bytes
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
    cmp byte [vp_loaded], 0         ; THE POSTER (SPEC.md 98.4): the header's
    je .out                         ; keyframe, into the box - and only once
    mov ax, [vp_poster]             ; the header's claim is gone, so the
    cmp ax, [vp_nkeys]              ; poster's sits under what is freed
    jae .out
    call vp_loadkey
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
    mov al, [es:V88_AUDIO]          ; none, PCM8 with a byte a sample, or
    cmp al, 2                       ; ADPCM4 with a byte two samples - which
    ja .bad                         ; needs an even count (SPEC.md 98.1.1)
    mov [vp_audio], al
    xor bx, bx
    or al, al
    jz .aud
    mov bx, [vp_spf]
    cmp al, 1
    je .aud
    shr bx, 1
    jc .bad
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
    mov [vp_pitper0], al
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
    mov ax, [es:V88_REND+R_SLEN]    ; the stream's bytes, for its KB/s
    mov [vp_slen], ax
    mov ax, [es:V88_REND+R_SLEN+2]
    mov [vp_slen+2], ax
    ; --- THE KEYFRAMES (98.1.3): a table on a sector, 16,383 at most, a
    ;     poster inside it. A record too big for one read turns the Preview
    ;     and the seek off, and the file still plays from the start
    mov ax, [es:V88_REND+R_NKEYS]
    cmp ax, 16383
    ja .bad
    mov bx, [es:V88_REND+R_POSTER]
    cmp bx, 0xFFFF
    je .pok
    cmp bx, ax
    jae .bad
.pok:
    mov [vp_poster], bx
    or ax, ax
    jz .nokeys
    mov bx, [es:V88_REND+R_KTAB]
    test bx, 511
    jnz .bad
    mov [vp_ktab], bx
    mov bx, [es:V88_REND+R_KTAB+2]
    mov [vp_ktab+2], bx
    mov bx, [es:V88_REND+R_KMAX]
    cmp bx, 16
    jb .bad
    cmp bx, VP_KMAXREC
    ja .nokeys
    mov [vp_kmaxb], bx
    mov cx, [vp_clb]                ; its read: the record and a cluster
    add bx, cx                      ; either side, whole KB - which must be
    jc .nokeys                      ; one call of READ_AT (a word of bytes)
    add bx, cx
    jc .nokeys
    add bx, cx
    jc .nokeys
    sub bx, cx
    add bx, 1023
    jc .nokeys
    mov cl, 10
    shr bx, cl
    mov [vp_kbkb], bx
    mov [vp_nkeys], ax
.nokeys:
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

; vp_canplay - can THIS display play it (SPEC.md 98.3, 98.3.2)? In its own
; layout's mode if the display has it; else through the SHADOW, in the first
; other layout whose mode it has and whose screen holds the canvas
vp_canplay:
    mov byte [vp_shadow], 0
    mov bx, [vp_win]
    call OSAPI_FSX_CAPS             ; AX = the modes this window's display has
    mov [vp_caps], ax
    mov al, [vp_layout]
    call vp_try
    jnc .ok
    mov al, 2                       ; LIN80, HERC, CGA: the roomiest first
.l:
    cmp al, [vp_layout]
    je .n
    call vp_try
    jnc .shadow
.n:
    dec al
    jns .l
    mov bl, [vp_layout]             ; "made for <layout>": nothing here holds
    xor bh, bh                      ; it
    shl bx, 1
    mov ax, [vp_laynotab+bx]
    mov [vp_msg], ax
    ret
.shadow:
    mov byte [vp_shadow], 1
.ok:
    mov [vp_tlay], al
    mov bl, al                      ; the mode to take
    xor bh, bh
    mov ax, bx
    shl bx, 1
    add bx, ax
    shl bx, 1
    mov al, [vp_laytab+bx]
    mov [vp_mode], al
    mov byte [vp_ok], 1
    mov word [vp_msg], vp_s_ready
    cmp byte [vp_shadow], 0
    je .out
    mov bl, [vp_layout]
    xor bh, bh
    shl bx, 1
    mov ax, [vp_laycptab+bx]
    mov [vp_msg], ax
.out:
    ret

; vp_try - AL = a layout: CF=0 its mode is on this display and its screen
; holds the canvas. Preserves AL
vp_try:
    push ax
    mov bl, al
    xor bh, bh
    mov ax, bx
    shl bx, 1
    add bx, ax
    shl bx, 1                       ; BX = layout * 6
    mov cl, [vp_laytab+bx]
    mov ax, [vp_caps]
    shr ax, cl
    test al, 1
    jz .no
    mov ax, [vp_wb]
    cmp ax, [vp_laytab+bx+2]        ; stride
    ja .no
    mov ax, [vp_h]
    cmp ax, [vp_laytab+bx+4]        ; rows
    ja .no
    pop ax
    clc
    ret
.no:
    pop ax
    stc
    ret

; vp_rowaddr - AX = a row, BL = a layout -> AX = the row's first byte in that
; layout's memory image (SPEC.md 98.1.2). Preserves CX, DX, SI, DI
vp_rowaddr:
    push cx
    push dx
    xor bh, bh
    mov cx, bx
    shl bx, 1
    add bx, cx
    shl bx, 1                       ; BX = layout * 6
    mov cl, [vp_laytab+bx+1]        ; banks: 1, 2 or 4
    xor ch, ch
    dec cx
    mov dx, ax
    and dx, cx                      ; DX = the bank
    inc cx
.s:
    shr cx, 1
    jz .sd
    shr ax, 1                       ; AX = the row within its bank
    jmp short .s
.sd:
    push dx
    mul word [vp_laytab+bx+2]       ; ...times the stride
    pop dx
    mov cl, 13
    shl dx, cl                      ; + the bank x 8192
    add ax, dx
    pop dx
    pop cx
    ret

; =============================================================================
; THE KEYFRAMES (SPEC.md 98.1.3, 98.4): a table entry, and its picture halved
; into the poster the window shows
; =============================================================================
; vp_loadkey - keyframe AX: its entry into vp_ke ([vp_kload] = AX when it is
; there), its record decoded into a 64 KB shadow and halved into the poster
; ([vp_pseg] = 0 when there is none). Lock held. Preserves all
vp_loadkey:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    mov bx, ax
    call vp_pfree
    mov ax, [vp_wb]                 ; THE POSTER'S claim FIRST, so it sits
    inc ax                          ; under the two that are freed at the end
    shr ax, 1                       ; (the first half's size: a second pass
    mov cx, [vp_h]                  ; halves it in place)
    inc cx
    shr cx, 1
    mul cx
    add ax, 1023
    adc dx, 0
    mov cl, 10
    shr ax, cl
    mov cl, 6
    shl dx, cl
    or ax, dx
    call OSAPI_MEM_CLAIM            ; no room for a picture: the box is black
    jc .nop                         ; and the key is picked all the same - a
    mov [vp_pseg], dx               ; play needs only its entry
.nop:
    mov ax, [vp_kbkb]               ; the record, a cluster either side
    call OSAPI_MEM_CLAIM
    jc .nobuf
    mov [vp_rdseg], dx
    mov ax, bx
    call vp_kent
    jc .nent
    cmp word [vp_pseg], 0
    je .free
    call vp_kpic
    jnc .free
.nent:
    call vp_pfree
.free:
    mov dx, [vp_rdseg]
    call OSAPI_MEM_FREE
    jmp short .out
.nobuf:
    call vp_pfree
.out:
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vp_pfree - the poster's claim, if there is one
vp_pfree:
    push dx
    mov dx, [vp_pseg]
    or dx, dx
    jz .out
    call OSAPI_MEM_FREE
    mov word [vp_pseg], 0
.out:
    pop dx
    ret

; vp_kent - AX = a keyframe: its 16-byte entry into vp_ke, through
; [vp_rdseg], and checked. CF=1 it could not be read or is not sound
vp_kent:
    mov bx, ax
    mov dx, ax                      ; DX:AX = the entry's offset, 16 x AX
    mov cl, 4
    shl ax, cl
    mov cl, 12
    shr dx, cl
    add ax, [vp_ktab]
    adc dx, [vp_ktab+2]
    mov cx, 16
    call vp_rdat
    jc .bad
    push ds
    pop es
    mov di, vp_ke
    mov ax, [vp_rdseg]
    push ds
    mov ds, ax
    mov cx, 8
    cld
    rep movsw
    pop ds
    cmp word [vp_ke+KE_K+2], 0      ; a frame of the file's...
    jne .bad
    mov ax, [vp_ke+KE_K]
    cmp ax, [vp_frames]
    jae .bad
    mov ax, [vp_ke+KE_LEN]          ; ...a record no longer than the header
    cmp ax, 16                      ; said the largest is...
    jb .bad
    cmp ax, [vp_kmaxb]
    ja .bad
    cmp byte [vp_ke+KE_SECS], 64    ; ...and a super-packet after it
    ja .bad
    test word [vp_ke+KE_SP], 511
    jnz .bad
    mov [vp_kload], bx
    clc
    ret
.bad:
    stc
    ret

; vp_kpic - the record vp_ke names, decoded from black into a 64 KB shadow
; (98.1.6: the claim bounds a write the lists were not checked for) and
; halved into [vp_pseg] - twice for a canvas bigger than CGA's. CF=1 not
vp_kpic:
    mov ax, 64
    call OSAPI_MEM_CLAIM
    jc .no
    mov [vp_kshd], dx
    mov es, dx
    call vp_zero
    mov ax, [vp_ke+KE_OFF]
    mov dx, [vp_ke+KE_OFF+2]
    mov cx, [vp_ke+KE_LEN]
    call vp_rdat
    jc .free
    mov dx, [vp_rdseg]
    mov ax, si
    mov cl, 4
    shr ax, cl
    add dx, ax
    and si, 15
    add si, 6                       ; past len, y0, y1
    xor bp, bp
    push ds
    mov ds, dx
    call vd_native                  ; ES = the shadow, from its address 0
    pop ds
    mov ax, [vp_kshd]               ; the first half: out of the file's
    mov [vh_sseg], ax               ; layout...
    mov al, [vp_layout]
    mov [vh_lay], al
    mov ax, [vp_wb]
    mov [vh_wb], ax
    mov ax, [vp_h]
    mov [vh_h], ax
    mov ax, [vp_pseg]
    mov [vh_dseg], ax
    call vp_half
    mov ax, [vp_wb]                 ; the picture's width: half the canvas's
    shl ax, 1
    shl ax, 1
    cmp word [vp_wb], VP_BOXW / 4   ; ...unless that is wider than the box,
    ja .quarter                     ; or taller
    cmp word [vp_h], 2 * VP_BOXH
    jbe .sized
.quarter:
    mov ax, [vp_pseg]               ; ...and then a quarter, the second pass
    mov [vh_sseg], ax               ; in place: its rows are dense now
    mov byte [vh_lay], 0xFF
    mov ax, [vh_wb]
    mov [vh_sstr], ax
    call vp_half
    mov ax, [vp_wb]
    shl ax, 1
.sized:
    mov [vp_ppx], ax
    mov ax, [vh_wb]
    mov [vp_pbw], ax
    mov ax, [vh_h]                  ; rows past the box are cut, top and
    xor dx, dx                      ; bottom alike
    cmp ax, VP_BOXH
    jbe .rows
    mov dx, ax
    sub dx, VP_BOXH
    shr dx, 1
    mov ax, VP_BOXH
.rows:
    mov [vp_prows], ax
    mov ax, dx
    mul word [vp_pbw]
    mov [vp_pskip], ax
    inc word [vp_ploads]
    clc
.free:
    pushf
    mov dx, [vp_kshd]
    call OSAPI_MEM_FREE
    popf
.no:
    ret

; vp_zero - ES:0: the file's layout's memory image, black
vp_zero:
    push ax
    push bx
    push cx
    push di
    mov bl, [vp_layout]
    xor bh, bh
    mov ch, [vp_laykb+bx]           ; KB x 512 = words
    shl ch, 1
    xor cl, cl
    xor di, di
    xor ax, ax
    cld
    rep stosw
    pop di
    pop cx
    pop bx
    pop ax
    ret

; vp_rdat - DX:AX = a file offset, CX = bytes wanted (<= 64 KB less two
; clusters): the clusters under them read into [vp_rdseg]:0 (READ_AT takes
; whole clusters). out: CF=0 SI = where the offset landed; CF=1 the disk
; failed, or the file stops short of them
vp_rdat:
    push ax
    push bx
    push cx
    push dx
    push es
    mov bx, [vp_clb]
    dec bx
    mov si, ax
    and si, bx                      ; SI = into its cluster
    sub ax, si
    add cx, si                      ; the end, from that cluster's start
    jc .bad
    mov [vp_rdend], cx
    add cx, bx                      ; ...in whole clusters
    jc .bad
    not bx
    and cx, bx
    mov es, [vp_rdseg]
    xor bx, bx
    push si
    mov si, vp_name
    call OSAPI_FILE_READ_AT         ; DX:AX = the bytes delivered
    pop si
    jc .bad
    or dx, dx
    jnz .ok
    cmp ax, [vp_rdend]
    jb .bad
.ok:
    clc
    jmp short .out
.bad:
    stc
.out:
    pop es
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; THE HALF-SCALER (SPEC.md 98.4). Two rows of the source, a nibble of each at
; a time, index a 256-byte table that answers two output pixels: each lit
; when the four source pixels under it hold MORE lit ones than its threshold,
; 2x2 ordered dither - [0 2 / 3 1] by output row and column parity - so a
; grey stays a grey and a line one pixel wide survives. tools/os88vid.py's
; thumb_half is the reference; a table per row parity, made at start
; -----------------------------------------------------------------------------
vp_mkdtab:
    push ax
    push bx
    push cx
    push dx
    xor bx, bx                      ; BH = the row's parity, BL = the index
.l:
    mov al, bl
    xor dx, dx                      ; DH = the left pixel's count, DL the right's
    mov cx, 8
.b:
    shl al, 1                       ; bits 7,6 and 3,2 are the left pixel's,
    jnc .z                          ; 5,4 and 1,0 the right's: bit CX-1
    mov ah, cl
    dec ah
    test ah, 2
    jz .r
    inc dh
    jmp short .z
.r:
    inc dl
.z:
    loop .b
    xor al, al
    or bh, bh
    jnz .odd
    cmp dh, 0                       ; even rows: left over 0, right over 2
    jbe .e1
    or al, 2
.e1:
    cmp dl, 2
    jbe .st
    or al, 1
    jmp short .st
.odd:
    cmp dh, 3                       ; odd rows: left over 3, right over 1
    jbe .o1
    or al, 2
.o1:
    cmp dl, 1
    jbe .st
    or al, 1
.st:
    mov [vp_dtab+bx], al
    inc bx
    cmp bx, 512
    jb .l
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; two output pixels a nibble: AL = the upper row's byte, AH = the lower's,
; BX = this row's table, CL = 4 -> AL = four output pixels, bits 3..0.
; DX clobbered
%macro VH_NIB 0
    mov dx, ax
    and al, 0xF0
    shr ah, cl
    or al, ah                       ; upper's high nibble, lower's high
    cs xlatb
    mov ah, al
    mov al, dl
    shl al, cl
    and dh, 0x0F
    or al, dh                       ; ...and the low nibbles
    cs xlatb
    shl ah, 1
    shl ah, 1
    or al, ah
%endmacro

; vp_half - [vh_sseg]'s image, [vh_wb] bytes x [vh_h] rows - in the layout
; [vh_lay], or linear at [vh_sstr] when that is FFh - halved into [vh_dseg]:0,
; dense. out: [vh_wb], [vh_h] are the half's. The destination may be the
; source when it is linear: every write lands at or behind every read left
vp_half:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    mov ax, [vh_wb]
    inc ax
    shr ax, 1
    mov [vh_owb], ax
    mov es, [vh_dseg]
    xor di, di
    mov word [vh_y], 0
.row:
    mov ax, [vh_y]
    shl ax, 1
    cmp ax, [vh_h]
    jae .done
    push ax
    call vh_addr
    mov si, ax                      ; SI = the upper row
    pop ax
    inc ax
    xor bp, bp
    cmp ax, [vh_h]
    jae .one                        ; an odd last row pairs with itself
    call vh_addr
    sub ax, si
    mov bp, ax                      ; BP = the lower row, from the upper
.one:
    mov bl, [vh_y]
    and bl, 1
    mov bh, bl
    xor bl, bl
    add bx, vp_dtab
    mov ch, [vh_wb]
    shr ch, 1                       ; whole source byte pairs
    mov cl, 4
    mov ax, [vh_sseg]
    push ds
    mov ds, ax
    or ch, ch
    jz .last
.p:
    mov al, [si]
    mov ah, [ds:bp+si]
    inc si
    VH_NIB
    shl al, cl
    mov [es:di], al
    mov al, [si]
    mov ah, [ds:bp+si]
    inc si
    VH_NIB
    or [es:di], al
    inc di
    dec ch
    jnz .p
.last:
    test byte [cs:vh_wb], 1         ; an odd byte left: the high nibble alone
    jz .rd
    mov al, [si]
    mov ah, [ds:bp+si]
    VH_NIB
    shl al, cl
    mov [es:di], al
    inc di
.rd:
    pop ds
    inc word [vh_y]
    jmp .row
.done:
    mov ax, [vh_owb]
    mov [vh_wb], ax
    mov ax, [vh_h]
    inc ax
    shr ax, 1
    mov [vh_h], ax
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vh_addr - AX = a source row -> AX = its first byte (clobbers DX)
vh_addr:
    cmp byte [vh_lay], 0xFF
    je .lin
    push bx
    mov bl, [vh_lay]
    call vp_rowaddr
    pop bx
    ret
.lin:
    mul word [vh_sstr]
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
    ; --- the sound (SPEC.md 98.3.1): a card, audio in the file, and the ring
    ;     the card will read in place, page-safe and never moved (MC_DMA)
    mov byte [vp_snd], 0
    mov word [vp_aseg], 0
    cmp byte [vp_audio], 0
    je .nosnd
    cmp byte [vp_nosnd], 0
    jne .nosnd
    call OSAPI_SND_CAPS
    test ax, SND_CAP_PCM_BG
    jz .nosnd
    mov ax, VP_RL / 1024 + 1        ; the ring and its two control words
    mov cx, ax
    call OSAPI_MEM_CLAIM_DMA_HI
    jc .nosnd                       ; no room for it: the play is silent
    mov [vp_aseg], dx
    mov byte [vp_snd], 1
.nosnd:
    ; --- the SHADOW (SPEC.md 98.3.2): the file's own layout's memory image,
    ;     black, which the frames decode into and the screen is copied from.
    ;     64 KB whatever the layout, because a list is not checked entry by
    ;     entry and its writes reach anywhere in ES (98.1.6): the claim IS
    ;     the bound. Before the ring, which takes what is left
    mov word [vp_fcap], 2
    mov word [vp_shseg], 0
    cmp byte [vp_shadow], 0
    je .noshd
    mov ax, 64
    call OSAPI_MEM_CLAIM
    jnc .shd
    mov word [vp_msg], vp_s_mem
    jmp .done
.shd:
    mov [vp_shseg], dx
    mov es, dx
    call vp_zero
    mov word [vp_fcap], 8           ; the decode is cheap and the copy is not:
.noshd:                             ; more frames a call, one copy after them
    mov word [vp_dy0], 0xFFFF
    mov word [vp_dy1], 0
    ; --- the ring: K slots and the mirror, K a power of two, 2..VP_KMAX
    mov word [vp_ring], 0
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
    jmp .freering
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
    jmp .freering
.ring:
    mov [vp_ring], dx
    ; --- WHERE IT STARTS (98.3.5): the file's first super-packet, or the
    ;     picked keyframe's - its record read into the ring, to be decoded
    ;     once the mode is set and before the ring is filled over it
    xor ax, ax
    mov [vp_base], ax
    mov [vp_kidx], ax
    mov word [vp_krec], 0xFFFF
    mov byte [vp_aref], 0x80
    mov ax, [vp_sp0]
    mov [vp_ssp], ax
    mov ax, [vp_sp0+2]
    mov [vp_ssp+2], ax
    mov ax, [vp_sp0n]
    mov [vp_ssec], ax
    mov ax, [vp_sel]
    or ax, ax
    jz .start
    cmp ax, [vp_kload]
    jne .start
    mov [vp_rdseg], dx
    mov ax, [vp_ke+KE_OFF]
    mov dx, [vp_ke+KE_OFF+2]
    mov cx, [vp_ke+KE_LEN]
    call vp_rdat
    jnc .kin
    mov word [vp_msg], vp_s_kbad
    jmp .freering
.kin:
    mov [vp_krec], si
    mov ax, [vp_ke+KE_K]
    inc ax
    mov [vp_base], ax               ; the first frame the stream draws
    mov ax, [vp_ke+KE_SP]
    mov [vp_ssp], ax
    mov ax, [vp_ke+KE_SP+2]
    mov [vp_ssp+2], ax
    mov al, [vp_ke+KE_SECS]
    xor ah, ah
    mov [vp_ssec], ax
    mov al, [vp_ke+KE_IDX]          ; ...and the records before it there
    mov [vp_kidx], ax
.start:
    ; --- the reader: from the cluster boundary under the stream's start
    mov ax, [vp_clb]
    dec ax                          ; a cluster's mask
    mov bx, [vp_ssp]
    and bx, ax                      ; BX = how far the stream is into it
    push ds
    pop es
    mov di, vp_cur
    xor ax, ax
    mov cx, FSEQ_SIZE / 2
    cld
    rep stosw
    mov ax, [vp_ssp]
    sub ax, bx
    mov [vp_cur+FSEQ_OFF], ax
    mov ax, [vp_ssp+2]
    mov [vp_cur+FSEQ_OFF+2], ax
    ; --- the hook's state: before the first super-packet
    xor ax, ax
    mov [vp_lc], ax
    mov [vp_pc], ax
    mov [vp_po], bx
    mov [vp_fleft], ax
    mov [vp_owed], ax
    mov [vp_stall], ax
    mov [vp_ptk], ax
    mov [vp_late], ax
    mov [vp_dt], ax
    mov [vp_ready], al
    mov [vp_end], al
    mov [vp_eof], al
    mov [vp_err], al
    mov [vp_held], al
    mov [vp_upause], al
    mov ax, [vp_base]
    mov [vp_done], ax               ; frames before it count as drawn
    mov ax, [vp_ssec]
    mov [vp_psec], ax               ; the first super-packet, not yet entered
    ; --- the clock: the file's own period, or - with the card - half of it,
    ;     the hook then reading the card's position twice a frame
    mov dx, [vp_pitdiv]
    mov al, [vp_pitper0]
    cmp byte [vp_snd], 0
    je .clk
    cmp dx, 2 * FSX_RATE_MIN
    jb .clk
    cmp al, 127
    ja .clk
    shr dx, 1
    shl al, 1
.clk:
    mov [vp_pitper], al
    ; --- and in
    mov bx, [vp_win]
    mov ax, vp_main
    mov cx, FSXF_RATE
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
    or dx, dx
    jz .nor
    call OSAPI_MEM_FREE
    mov word [vp_ring], 0
.nor:
    mov dx, [vp_shseg]
    or dx, dx
    jz .done
    call OSAPI_MEM_FREE
    mov word [vp_shseg], 0
.done:
    mov dx, [vp_aseg]               ; ...and the sound's, if it had one
    or dx, dx
    jz .noa
    call OSAPI_MEM_FREE
    mov word [vp_aseg], 0
.noa:
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
    ; the origin: centred, the row on a bank (SPEC.md 98.1.2), on the
    ; screen's layout - the file's own, or the shadow's target (98.3.2)
    mov bl, [vp_tlay]
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
    push ax
    mul cx
    mov [vp_ty0], ax                ; ...as a row, for the shadow's copy
    pop ax
    mul word [vp_laytab+bx+2]       ; ...rows of stride
    mov cx, [vp_laytab+bx+2]
    sub cx, [vp_wb]
    shr cx, 1                       ; x0
    mov [vp_tx0], cx
    add ax, cx
    mov [vp_org], ax
    ; COMPOSITE (SPEC.md 98.3.3): a CGACOMP file on a real CGA turns the
    ; colour burst on, which is what makes its stripes colours on a
    ; composite monitor. 3D8h is the app's past the mode set (§53.7), and the
    ; bracket's restore sets the mode, and with it the burst, back
    mov byte [vp_burst], 0
    cmp byte [vp_pixfmt], 1         ; CGACOMP (the byte is the format - 1)
    jne .pre
    cmp byte [vp_mode], FSXM_CGA640
    jne .pre
    call OSAPI_VIDEO                ; DL = the adapter: only a CGA has a
    cmp dl, VID_CGA                 ; composite output; an EGA's or a VGA's
    jne .pre                        ; mode 6 is RGB and 3D8h is not theirs
    mov dx, 0x3D8
    mov al, 0x1A                    ; 640x200 graphics, video on, burst ON
    out dx, al
    mov byte [vp_burst], 1
    ; THE KEYFRAME (98.3.5): the screen after frame k, decoded onto the black
    ; the mode set left - or into the shadow, and copied - before the ring
    ; is filled over its record
.pre:
    cmp word [vp_krec], 0xFFFF
    je .fill
    mov si, [vp_krec]
    mov dx, [vp_ring]
    mov ax, si
    mov cl, 4
    shr ax, cl
    add dx, ax
    and si, 15
    push dx
    mov ax, si
    add ax, [vp_ke+KE_LEN]
    push ax                         ; the record's end
    call vp_decrec                  ; SI past its lists
    pop ax
    pop dx
    cmp byte [vp_audio], 2          ; ADPCM4's keyframe carries the card's
    jne .kd                         ; REFERENCE after its lists: the sample
    cmp si, ax                      ; the stream holds at frame k+1, its
    jae .kd                         ; scale 0 there (98.1.1.1). A file made
    push ds                         ; before that has none, and starts at 80h
    mov ds, dx
    mov al, [si]
    pop ds
    mov [vp_aref], al
.kd:
    cmp byte [vp_shadow], 0
    je .fill
    call vp_blit
.fill:                              ; fill the ring before the first frame: a
    call vp_fill                    ; stream that fits is read whole
    jnc .fill
    mov cx, [vp_kidx]               ; ...then step over the records before
    jcxz .sk0                       ; frame k+1 in its super-packet, a len
.sk:                                ; hop each (98.1.3) - all in the ring
    push cx
    mov bx, vp_pc
    call vp_next
    pop cx
    jnc .skn
    cmp al, 1                       ; the end: a key on the last frame
    je .sk0
    mov byte [vp_err], 1
    mov word [vp_errmsg], vp_s_badsp
    ret
.skn:
    loop .sk
.sk0:
    cmp byte [vp_snd], 0
    je .go
    call vp_sopen                   ; the card, started with the picture
.go:
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
    cmp al, ' '                     ; Space pauses, and resumes (98.3.4)
    jne .nokey
    call vp_upaus
.nokey:
    cmp byte [vp_end], 0
    jne .drain
    cmp byte [vp_snd], 0            ; ...or, with sound, every frame drawn:
    je .rd                          ; the clock stops at the last, so nothing
    mov ax, [vp_done]               ; asks the stream for one past it (the
    cmp ax, [vp_frames]             ; silent play still ends on the chain's
    jae .drain                      ; own 0, which a hold can sit in front of)
.rd:
    call vp_fill
    jnc .loop                       ; a chunk arrived: poll, and try again
    call vp_skeep
    mov al, FSXW_FRAME              ; nothing to read yet: give the period
    call OSAPI_FSX_WAIT             ; to the hook
    jmp short .loop
.drain:                             ; the picture is done: the sound plays
    cmp byte [vp_snd], 0            ; out to its last byte, the hook still
    je .stop                        ; topping the ring up with its silence
    cmp byte [vp_err], 0
    jne .stop
    call OSAPI_GET_TICKS
    mov [vp_tdr], ax
.dl:
    mov ah, 1
    int 0x16
    jz .dk
    xor ah, ah
    int 0x16
    cmp al, 27
    je .stop
.dk:
    cmp byte [vp_aend], 2           ; the audio ran out early: nothing to wait
    je .stop                        ; for
    cmp byte [vp_aend], 0
    je .dw
    mov ax, [vp_alast]              ; played past the last byte of sound?
    sub ax, [vp_afinal]
    jns .stop
.dw:
    call OSAPI_GET_TICKS            ; ...or two seconds: a card that has
    sub ax, [vp_tdr]                ; stopped does not hold the machine
    cmp ax, 37
    jae .stop
    call vp_skeep
    mov al, FSXW_FRAME
    call OSAPI_FSX_WAIT
    jmp short .dl
.stop:
    pushf
    cli
    mov byte [vp_ready], 0
    popf
    cmp byte [vp_upause], 0         ; stopped while paused: the pause so far
    je .np                          ; is not play time either
    call OSAPI_GET_TICKS
    sub ax, [vp_ptk0]
    add [vp_ptk], ax
.np:
    call OSAPI_GET_TICKS
    sub ax, [vp_t0]
    sub ax, [vp_ptk]                ; the time it PLAYED
    mov [vp_dt], ax
    cmp byte [vp_sopn], 0           ; open, whether or not it is still
    je .ret                         ; the clock
    mov al, 2                       ; verb 2: the card stops and lets go of
    mov ah, [vp_hand]               ; the ring before it is freed
    call OSAPI_SND_STREAM
    mov byte [vp_sopn], 0
.ret:
    ret

; -----------------------------------------------------------------------------
; vp_sopen - the sound (SPEC.md 98.3.1): the audio cursor at the stream's
; start, the ring filled as far as it goes, then the card started on it.
; Refused, the play is silent and paced by FSXF_RATE as before
; -----------------------------------------------------------------------------
vp_sopen:
    push ds
    pop es
    xor ax, ax
    mov di, vp_szero                ; the play's sound counters, all zero
    mov cx, VP_SZERO / 2
    cld
    rep stosw
    mov si, vp_pc                   ; the audio cursor starts where the
    mov di, va_pc                   ; video's does - past a keyframe's skip
    mov cx, 6
    rep movsw
    mov ax, [vp_base]               ; ...and at the same frame, which is
    mov [vp_afr], ax                ; what the clock reads until the card's
    mov [vp_syncf], ax              ; first block says otherwise
    mov byte [vp_afn], 0x80         ; PCM8's silence
    mov ax, VP_BLOCK                ; frames the clock may run on past the
    xor dx, dx                      ; card's last word: one block's worth,
    div word [vp_abytes]            ; and two more
    add ax, 2
    mov [vp_acap], ax
    mov es, [vp_aseg]
    xor ax, ax
    mov [es:VP_RL+SND_EXT_TOTAL], ax
    mov [es:VP_RL+SND_EXT_CONS], ax
    mov bl, SND_OPENF_RING + SND_OPENF_EXT + (VP_RLCODE << SND_OPENF_RLSH)
    cmp byte [vp_audio], 2
    jne .pf
    or bl, SND_OPENF_ADPCM4         ; ADPCM4: stream byte 0 is the card's
    mov al, [vp_aref]               ; reference - 80h, or a keyframe's
    mov [es:0], al                  ; (98.3.5) - and the silence is a
    mov word [vp_atot], 1           ; nibble of no change
    mov word [vp_a0], 1
    mov byte [vp_afn], 0
.pf:
    mov [vp_sflag], bl
.pfl:
    mov ax, [vp_atot]
    push ax
    call vp_afill
    pop ax
    cmp ax, [vp_atot]
    jne .pfl
    cmp word [vp_atot], VP_BLOCK    ; the card starts on a whole block: a clip
    jae .open                       ; shorter than one is silence past its end
    mov cx, VP_BLOCK
    sub cx, [vp_atot]
    xor dx, dx
    call vp_aput
.open:
    xor al, al                      ; verb 0: open, the ring in our claim
    mov ah, [vp_sflag]
    xor si, si
    mov di, [vp_aseg]
    mov cx, [vp_atot]
    mov dx, [vp_rate]
    call OSAPI_SND_STREAM
    or al, al
    jnz .fail
    mov [vp_hand], ah
    mov byte [vp_sopn], 1
    ret
.fail:
    mov byte [vp_snd], 0            ; the card said no: a silent play
    ret

; vp_skeep - a stream the card paused for want of data resumes the moment a
; whole block is queued again (SPEC.md 34.5.2's contract: verb 1 resumes it)
vp_skeep:
    cmp byte [vp_snd], 0
    je .out
    cmp byte [vp_upause], 0         ; a pause is not an underrun to resume
    jne .out
    mov al, 3
    mov ah, [vp_hand]
    call OSAPI_SND_STREAM           ; AX = state, DX = consumed
    cmp ax, 2                       ; ENDED: the card stopped interrupting and
    jne .und                        ; the driver's watchdog gave up on it. The
    mov byte [vp_snd], 0            ; picture goes on, silent, on the PIT -
    mov word [vp_owed], 0           ; never held for a clock that has gone
    inc word [vp_pause]
    ret
.und:
    cmp ax, 1
    jne .out
    mov ax, [vp_atot]
    sub ax, dx
    cmp ax, VP_BLOCK
    jb .out
    mov al, 1
    mov ah, [vp_hand]
    mov cx, [vp_atot]
    call OSAPI_SND_STREAM
    inc word [vp_pause]
.out:
    ret

; -----------------------------------------------------------------------------
; vp_upaus - Space (98.3.4): pause, or resume. Paused, the hook returns at
; once - nothing owed, no periods counted - so the clock stands where the
; picture stands; the card, if there is one, is halted where it is (verb 10,
; SPEC.md 34.5.4) and verb 1 starts it again. The ticks paused are not play
; time
; -----------------------------------------------------------------------------
vp_upaus:
    cmp byte [vp_upause], 0
    jne .resume
    mov byte [vp_upause], 1         ; one store: the hook reads it at IF = 0
    call OSAPI_GET_TICKS
    mov [vp_ptk0], ax
    cmp byte [vp_snd], 0
    je .out
    mov al, SND_V_PAUSE
    mov ah, [vp_hand]
    call OSAPI_SND_STREAM
.out:
    ret
.resume:
    call OSAPI_GET_TICKS
    sub ax, [vp_ptk0]
    add [vp_ptk], ax
    cmp byte [vp_snd], 0
    je .go
    mov al, 1                       ; the card first: it resumes where it
    mov ah, [vp_hand]               ; stopped, and the clock extrapolates
    mov cx, [vp_atot]               ; from its last word as before
    call OSAPI_SND_STREAM
.go:
    mov byte [vp_upause], 0
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
; SILENT, a frame is due every [vp_pitper] periods. At most two are drawn a
; call - one due and one owed - and the rest are counted LATE and forgiven: a
; delta frame cannot be skipped, so falling behind is paid for by the picture
; running slow, never by a wrong picture.
; WITH SOUND (SPEC.md 98.3.1) the CARD is the clock: the frames due are the
; frames whose audio it has played, as of its last block interrupt, plus the
; periods since - capped at a block's worth, so a card that stops holds the
; picture too. Then the ring is topped up from the audio cursor.
; =============================================================================
vp_hook:
    cmp byte [vp_ready], 0
    je .ret
    cmp byte [vp_upause], 0         ; paused (98.3.4): the periods are not
    jne .ret                        ; the play's
    add [vp_pers], ax
    cmp ax, [vp_gap]                ; the longest the hook was held off: a
    jbe .g                          ; picture late for THAT is the machine's,
    mov [vp_gap], ax                ; not the clock's
.g:
    cmp byte [vp_snd], 0
    jne .snd
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
    cmp cx, [vp_fcap]
    jbe .n
    sub cx, [vp_fcap]
    cmp byte [vp_shadow], 0
    jne .keep
    add [vp_late], cx               ; native: forgiven, the picture runs slow
    mov cx, [vp_fcap]
    jmp short .n
.keep:
    mov ax, cx                      ; SHADOW: the rest stays owed. The copy is
    mul bx                          ; what costs, once a call however many
    add [vp_owed], ax               ; frames it covers, so the decode catches
    mov cx, [vp_fcap]               ; up and the DISPLAY rate is what drops
.n:
    sti                             ; a disk's completion is not held behind a
.f:                                 ; frame (SPEC.md 53.2.2 allows it)
    push cx
    call vp_frame
    pop cx
    jc .stop
    loop .f
.stop:
    mov bl, [vp_pitper]             ; still a frame owed after them: behind
    xor bh, bh
    xor al, al
    cmp [vp_owed], bx
    jb .copy
    inc ax
.copy:
    call vp_blitck                  ; the shadow's band, once for them all
    cli
.ret:
    ret
.snd:                               ; --- the card's clock (SPEC.md 98.3.1)
    mov es, [vp_aseg]
    mov ax, [es:VP_RL+SND_EXT_CONS] ; what the card has consumed, as of its
    mov dx, ax                      ; last block interrupt
    sub ax, [vp_alast]
    jz .nosync
    mov [vp_alast], dx
    add [vp_aplay], ax
    adc word [vp_aplay+2], 0
    mov ax, [vp_aplay]
    mov dx, [vp_aplay+2]
    sub ax, [vp_a0]                 ; the reference byte is no frame's
    sbb dx, 0
    jc .neg
    cmp dx, [vp_abytes]             ; a quotient past 16 bits: long over
    jae .big
    div word [vp_abytes]            ; AX = frames wholly played
    jmp short .syn
.neg:
    xor ax, ax
    jmp short .syn
.big:
    mov ax, 0xFFF0
.syn:
    add ax, [vp_base]               ; ...from the frame the play started at
    jnc .syb
    mov ax, 0xFFF0
.syb:
    mov [vp_syncf], ax
    mov ax, [vp_pers]
    mov [vp_syncp], ax
.nosync:
    mov ax, [vp_pers]               ; ...and the periods since, at most a
    sub ax, [vp_syncp]              ; block's worth of frames
    xor dx, dx
    mov bl, [vp_pitper]
    xor bh, bh
    div bx
    cmp ax, [vp_acap]
    jbe .cap
    mov ax, [vp_acap]
.cap:
    add ax, [vp_syncf]
    inc ax                          ; AX = the frames due - never past the
    cmp ax, [vp_frames]             ; last, whose silence plays on after it
    jbe .due2
    mov ax, [vp_frames]
.due2:
    mov [vp_due], ax
    sub ax, [vp_done]
    jbe .top                        ; none: the picture is on time
    mov cx, ax
    cmp cx, [vp_skmax]
    jbe .sk
    mov [vp_skmax], cx
.sk:
    cmp cx, [vp_fcap]
    jbe .n2
    inc word [vp_late]              ; more behind the sound than a call draws
    mov cx, [vp_fcap]
.n2:
    sti
.f2:
    push cx
    call vp_frame
    pop cx
    jc .top
    loop .f2
.top:
    sti
    xor al, al                      ; still frames due after them: behind
    mov bx, [vp_due]
    cmp bx, [vp_done]
    jbe .tc
    inc ax
.tc:
    call vp_blitck
    call vp_afill                   ; the audio a few frames ahead of the card
    cli
    ret

; -----------------------------------------------------------------------------
; vp_blitck / vp_blit - the SHADOW's copy (SPEC.md 98.3.2): the canvas rows
; the frames since the last copy wrote, [vp_dy0, vp_dy1), from the file's
; layout to the screen's, a row at a time and each row re-addressed. Only the
; DISPLAY rate pays for it: the decode behind it has already run
; -----------------------------------------------------------------------------
; in: AL = 1 the play is behind. Then the copy waits and the call's time
; goes to the decode, which is what keeps the play in time - but never more
; than VP_SKIPMAX calls running, so a machine that can never catch up still
; sees its picture move
vp_blitck:
    cmp byte [vp_shadow], 0
    je .out
    mov bx, [vp_dy1]
    cmp bx, [vp_dy0]
    jbe .out
    or al, al
    jz .go
    cmp byte [vp_skipn], VP_SKIPMAX
    jae .go
    inc byte [vp_skipn]
    ret
.go:
    mov byte [vp_skipn], 0
    call vp_blit
.out:
    ret

vp_blit:
    mov es, [vp_vseg]
    mov dx, [vp_shseg]
    mov cx, [vp_dy0]
.r:
    cmp cx, [vp_dy1]
    jae .d
    mov ax, cx
    mov bl, [vp_layout]
    call vp_rowaddr
    mov si, ax
    mov ax, cx
    add ax, [vp_ty0]
    mov bl, [vp_tlay]
    call vp_rowaddr
    add ax, [vp_tx0]
    mov di, ax
    push cx
    mov cx, [vp_wb]
    push ds
    mov ds, dx
    cld
    shr cx, 1
    rep movsw
    adc cx, cx
    rep movsb
    pop ds
    pop cx
    inc cx
    jmp short .r
.d:
    mov word [vp_dy0], 0xFFFF       ; the band is empty again
    mov word [vp_dy1], 0
    ret

; vp_frame - draw the next frame. CF=1 it did not (stalled, held, ended)
vp_frame:
    cmp byte [vp_end], 0
    jne .no
    mov ax, [vp_done]
    cmp ax, [vp_stopat]             ; the gate's hold (tests/vidplay.py):
    jne .snd                        ; stop BEFORE this frame, the screen being
    mov byte [vp_held], 1           ; the host's frame [vp_stopat]-1
.no:
    stc
    ret
.snd:
    cmp byte [vp_snd], 0            ; WITH SOUND, never a picture whose audio
    je .go                          ; is not in the ring yet: the audio cursor
    cmp ax, [vp_frames]             ; is what keeps the chunks under it, and
    jae .theend                     ; the video may not overtake it - which
    cmp ax, [vp_afr]                ; is why the header's count is the end
    jae .no                         ; here, the chain's 0 never being reached
.go:
    mov bx, vp_pc
    call vp_next                    ; DX:SI = the record, CX = its len
    jnc .dec
    or al, al
    jz .stall
    cmp al, 1
    je .theend
    cmp al, 2
    je .badsp
    jmp short .badrec
.dec:
    call vp_decrec
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

; vp_decrec - DX:SI = a record: decoded onto the screen, or into the shadow
; with the rows it writes added to the band the next copy covers (98.3.2).
; clobbers AX, BX, CX, DX, SI, DI, BP, ES
vp_decrec:
    cmp byte [vp_shadow], 0
    je .native
    push ds                         ; SHADOW (98.3.2): into the file's own
    mov ds, dx                      ; image at its own address 0, and the rows
    mov ax, [si+2]                  ; the record writes added to the band the
    mov cx, [si+4]                  ; next copy covers
    pop ds
    cmp cx, [vp_h]
    jbe .y1
    mov cx, [vp_h]
.y1:
    cmp ax, [vp_dy0]
    jae .y0k
    mov [vp_dy0], ax
.y0k:
    cmp cx, [vp_dy1]
    jbe .y1k
    mov [vp_dy1], cx
.y1k:
    mov es, [vp_shseg]
    xor bp, bp
    jmp short .go2
.native:
    mov es, [vp_vseg]
    mov bp, [vp_org]
.go2:
    add si, 6
    push ds
    mov ds, dx
    call vd_native                  ; the lists, onto the adapter
    pop ds
    ret

; -----------------------------------------------------------------------------
; vp_next - step a stream cursor to its next record (SPEC.md 98.3)
; in:  BX = a cursor, six words: chunk, offset, sectors, next's sectors,
;      frames left, record offset - [vp_pc] the video's, [va_pc] the audio's
; out: CF=0 DX:SI = the record, CX = its len, the cursor past it;
;      CF=1 AL = 0 not loaded yet / 1 the end / 2 bad super-packet / 3 bad
;      record, and the cursor where it was
; clobbers: AX, CX, DX, SI, DI, ES
; One stepping for both cursors, worked on a copy: the video's is what the
; reader keys on, so the audio's may run ahead but never releases anything
; -----------------------------------------------------------------------------
vp_next:
    push bx
    push ds
    pop es
    mov si, bx
    mov di, vw_pc
    mov cx, 6
    cld
    rep movsw
    call vp_nextw
    pop bx
    pushf
    push ax
    push cx
    push si
    push ds
    pop es
    mov si, vw_pc
    mov di, bx
    mov cx, 6
    rep movsw
    pop si
    pop cx
    pop ax
    popf
    ret

vp_nextw:
    cmp word [vw_fleft], 0
    jne .rec
    ; --- ENTER the super-packet at (pc, po), psec sectors: all of it
    ;     loaded, or wait. (pc, po) moved here the moment the one before
    ;     it ended, so the reader is never held up by a finished one
    mov cx, [vw_psec]
    or cx, cx
    jnz .sp
    mov al, 1                       ; the chain's 0: the end of the stream
    stc
    ret
.sp:
    mov dx, cx
    mov cl, 9
    shl dx, cl                      ; its bytes (<= 32768)
    add dx, [vw_po]                 ; where it ends, from its chunk's start
    mov di, [vw_pc]
    cmp dx, VP_CHUNK
    jbe .one
    inc di                          ; ...in the next chunk
.one:
    cmp di, [vp_lc]
    jb .ld
    xor al, al                      ; not all read yet
    stc
    ret
.ld:
    mov ax, [vw_pc]
    mov bx, [vw_po]
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
    mov al, 2
    stc
    ret
.spok:
    mov [vw_fleft], cx
    mov [vw_nsec], ax
    mov word [vw_rofs], 4
.rec:
    ; --- the record at [rofs] into the super-packet
    mov ax, [vw_pc]
    mov bx, [vw_po]
    add bx, [vw_rofs]
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
    mov ax, [vw_psec]               ; ...against what is left of the
    mov di, ax                      ; super-packet
    push cx
    mov cl, 9
    shl di, cl
    pop cx
    sub di, [vw_rofs]
    cmp cx, di
    ja .brec
    mov ax, [vp_abytes]
    add ax, 6 + 10
    cmp cx, ax
    jae .rok
.brec:
    mov al, 3
    stc
    ret
.rok:
    add [vw_rofs], cx
    dec word [vw_fleft]
    jnz .out
    push cx                         ; ITS LAST FRAME: step to the next one's
    mov ax, [vw_psec]               ; start now - the reader may reuse this
    mov cl, 9                       ; one's chunks from here, and waiting for
    shl ax, cl                      ; the hook to ENTER the next one was a
    add ax, [vw_po]                 ; deadlock (a super-packet that needs a
    cmp ax, VP_CHUNK                ; chunk the reader may not read until
    jb .same                        ; this one is left)
    sub ax, VP_CHUNK
    inc word [vw_pc]
.same:
    mov [vw_po], ax
    mov ax, [vw_nsec]
    mov [vw_psec], ax
    pop cx
.out:
    clc
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

; -----------------------------------------------------------------------------
; vp_afill - put the audio of the next frames into the ring (SPEC.md 98.3.1):
; as far as the ring has room behind what the card has not played, and the
; reader has loaded - VP_AMAX frames a call, so a hook stays short. At the
; stream's end, silence to a whole block past it, so the card's last block
; interrupt finds a full one and the tail is heard
; -----------------------------------------------------------------------------
vp_afill:
    cmp byte [vp_aend], 0
    jne .out
    mov word [vp_acnt], VP_AMAX
.l:
    mov ax, [vp_afr]
    cmp ax, [vp_frames]
    jae .pad
    mov ax, [vp_atot]               ; room: what is queued and not played,
    sub ax, [vp_alast]              ; plus this frame, inside the ring
    add ax, [vp_abytes]
    cmp ax, VP_RL
    ja .out
    mov bx, va_pc
    call vp_next
    jnc .rec
    or al, al
    jz .out                         ; not read yet: next call
    mov byte [vp_aend], 2           ; the end early, or damage: the video
    ret                             ; says which when it gets there
.rec:
    add si, cx                      ; the audio is the record's last bytes
    sub si, [vp_abytes]
    mov cx, [vp_abytes]
    call vp_aput
    inc word [vp_afr]
    dec word [vp_acnt]
    jnz .l
.out:
    ret
.pad:
    cmp word [vp_apend], 0          ; the end: silence to a whole block past
    jne .pw                         ; the last byte, once
    mov ax, [vp_atot]
    mov [vp_afinal], ax
    add ax, 2 * VP_BLOCK - 1
    and ax, -VP_BLOCK
    mov [vp_apend], ax
.pw:
    mov cx, [vp_apend]
    sub cx, [vp_atot]
    jz .done
    mov ax, VP_RL                   ; as much as there is room for now
    add ax, [vp_alast]
    sub ax, [vp_atot]
    jz .out
    cmp cx, ax
    jbe .pz
    mov cx, ax
.pz:
    xor si, si                      ; DX:SI = nowhere: vp_aput fills
    xor dx, dx
    call vp_aput
    jmp short .pw
.done:
    mov byte [vp_aend], 1
    ret

; vp_aput - CX bytes from DX:SI into the ring at [vp_atot], wrapping, and the
; new total published to the card; DX = 0 writes [vp_afn] silence instead.
; clobbers AX, BX, CX, SI, DI, ES
vp_aput:
    mov es, [vp_aseg]
    push cx                         ; the whole count
    mov di, [vp_atot]
    and di, VP_RL - 1
    mov bx, VP_RL
    sub bx, di                      ; BX = room to the ring's end
    cmp cx, bx
    jbe .one
    mov cx, bx
    call .cp                        ; to the end...
    xor di, di                      ; ...and the rest from its start
    pop cx
    push cx
    sub cx, bx
.one:
    call .cp
    pop bx
    add [vp_atot], bx
    mov ax, [vp_atot]
    mov [es:VP_RL+SND_EXT_TOTAL], ax
    ret
.cp:
    or dx, dx
    jz .fill
    push ds
    mov ds, dx
    cld
    shr cx, 1
    rep movsw
    adc cx, cx
    rep movsb
    pop ds
    ret
.fill:
    mov al, [vp_afn]
    cld
    rep stosb
    ret


%include "video/vdec.inc"

; =============================================================================
; the window
; =============================================================================
vp_paint:                           ; W_PAINT: SI = window, region armed
    push ax
    push bx
    push si
    call vp_track
    call vp_pposter
    call vp_pbar
    xor bx, bx
    call vp_ptext
    call vp_buttons
    cmp byte [vp_abon], 0
    je .out
    mov bx, si
    mov si, vp_ablines
    call os88ui_about_d
.out:
    pop si
    pop bx
    pop ax
    ret

; vp_track - where the window is now: the content origin, and the buttons'
; rects in screen coordinates (a window moves without a paint). Preserves all
vp_track:
    push ax
    push bx
    push cx
    push dx
    push di
    mov bx, [vp_win]
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    mov [vp_cx0], ax
    mov [vp_cy0], dx
    add ax, VP_BTX
    add dx, VP_BTY
    mov di, vp_brects
    mov cx, VP_NB
.r:
    mov [di], ax
    mov [di+2], dx
    add ax, VP_BTW - 1
    mov [di+4], ax
    sub ax, VP_BTW - 1 - VP_BTP
    push dx
    add dx, VP_BTH - 1
    mov [di+6], dx
    pop dx
    add di, 8
    loop .r
    mov ax, VP_NB                   ; none live under the About card
    cmp byte [vp_abon], 0
    je .n
    xor ax, ax
.n:
    mov [vp_btns + OS88UI_BT_N], ax
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vp_buttons - every button, in the state it should be in now. Lock held
vp_buttons:
    push ax
    push bx
    cmp byte [vp_abon], 0
    jne .out
    mov ax, OS88UI_IMG              ; Open is always live; the key buttons
    mov [vp_bflags], ax             ; stop at the ends, and Play needs a file
    mov [vp_bflags+2], ax           ; that plays here
    mov [vp_bflags+4], ax
    mov [vp_bflags+6], ax
    cmp word [vp_sel], 0
    jne .p1
    or byte [vp_bflags+2], OS88UI_DIS
.p1:
    cmp byte [vp_ok], 1
    je .p2
    or byte [vp_bflags+4], OS88UI_DIS
.p2:
    mov ax, [vp_sel]
    inc ax
    cmp ax, [vp_nkeys]
    jb .p3
    or byte [vp_bflags+6], OS88UI_DIS
.p3:
    mov bx, vp_btns
    mov al, 1
.b:
    call os88ui_btn
    inc al
    cmp al, VP_NB
    jbe .b
.out:
    pop bx
    pop ax
    ret

; vp_ptext - the info panel's lines from BX on, each an opaque run the full
; width, so nothing is erased first (PERFORMANCE.md rule 2)
vp_ptext:
    push ax
    push bx
    push cx
    push dx
    push si
    mov ax, VP_LINE
    mul bx
    add ax, vp_lines
    mov si, ax
    mov al, VP_LPITCH
    mul bl
    add ax, [vp_cy0]
    add ax, VP_TXTY
    mov dx, ax
    mov cx, [vp_cx0]
    add cx, VP_TXTX
.l:
    cmp bx, VP_LINES
    jae .out
    mov ax, (CWHITE << 8) | CBLACK
    call OSAPI_FONT_RUN
    add si, VP_LINE
    add dx, VP_LPITCH
    inc bx
    jmp short .l
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vp_pposter - the box and the poster in it (98.4): the picture where there
; is one, black round it, each pixel written once
vp_pposter:
    push ax
    push bx
    push cx
    push dx
    push si
    push bp
    push es
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, [vp_cx0]
    add ax, VP_BOXX - 1
    mov bx, [vp_cy0]
    add bx, VP_BOXY - 1
    mov cx, ax
    add cx, VP_BOXW + 1
    mov dx, bx
    add dx, VP_BOXH + 1
    call OSAPI_GFX_FRAME
    mov ax, [vp_cx0]                ; the box's inside
    add ax, VP_BOXX
    mov [vp_bx1], ax
    add ax, VP_BOXW - 1
    mov [vp_bx2], ax
    mov ax, [vp_cy0]
    add ax, VP_BOXY
    mov [vp_by1], ax
    add ax, VP_BOXH - 1
    mov [vp_by2], ax
    cmp word [vp_pseg], 0
    je .black
    mov ax, VP_BOXW                 ; the picture's place: centred, its x on a
    sub ax, [vp_ppx]                ; byte (OSAPI_GFX_BLIT1 takes no other) -
    shr ax, 1                       ; the SCREEN's byte, so a window whose
    add ax, [vp_bx1]                ; content is off the grid loses up to 7
    add ax, 7                       ; columns at the right instead
    and ax, 0xFFF8
    mov [vp_px], ax
    mov cx, [vp_bx2]
    inc cx
    sub cx, ax
    cmp cx, [vp_ppx]
    jb .w
    mov cx, [vp_ppx]
.w:
    mov [vp_pdw], cx
    mov ax, VP_BOXH
    sub ax, [vp_prows]
    shr ax, 1
    add ax, [vp_by1]
    mov [vp_py], ax
    mov ax, [vp_bx1]                ; above it
    mov bx, [vp_by1]
    mov cx, [vp_bx2]
    mov dx, [vp_py]
    dec dx
    call vp_fillne
    mov bx, [vp_py]                 ; below it
    add bx, [vp_prows]
    mov dx, [vp_by2]
    call vp_fillne
    mov bx, [vp_py]                 ; left of it
    mov dx, bx
    add dx, [vp_prows]
    dec dx
    mov cx, [vp_px]
    dec cx
    call vp_fillne
    mov ax, [vp_px]                 ; right of it
    add ax, [vp_pdw]
    mov cx, [vp_bx2]
    call vp_fillne
    mov es, [vp_pseg]
    mov si, [vp_pskip]
    mov bp, [vp_pbw]
    mov ax, [vp_px]
    mov cx, [vp_pdw]
    mov bx, [vp_py]
    mov dx, [vp_prows]
    call OSAPI_GFX_BLIT1
    jnc .out
    mov ax, [vp_px]                 ; refused: black where it would be
    mov bx, [vp_py]
    mov cx, ax
    add cx, [vp_pdw]
    dec cx
    mov dx, bx
    add dx, [vp_prows]
    dec dx
    call vp_fillne
    jmp short .out
.black:
    mov ax, [vp_bx1]
    mov bx, [vp_by1]
    mov cx, [vp_bx2]
    mov dx, [vp_by2]
    call vp_fillne
.out:
    pop es
    pop bp
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vp_fillne - GFX_FILL AX,BX..CX,DX in the colour set, unless it is empty
vp_fillne:
    cmp cx, ax
    jl .no
    cmp dx, bx
    jl .no
    call OSAPI_GFX_FILL
.no:
    ret

; vp_pbar - the scrub bar (98.4): white, and the thumb black where the play
; starts - three fills and no pixel twice; grey with no keyframes to pick
vp_pbar:
    push ax
    push bx
    push cx
    push dx
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, [vp_cx0]
    add ax, VP_BOXX - 1
    mov bx, [vp_cy0]
    add bx, VP_BARY
    mov cx, ax
    add cx, VP_BOXW + 1
    mov dx, bx
    add dx, VP_BARH - 1
    call OSAPI_GFX_FRAME
    inc ax                          ; the inside
    mov [vp_tx1], ax
    inc bx
    dec cx
    dec dx
    cmp word [vp_nkeys], 0
    jne .live
    call OSAPI_GFX_FILL_GRAY
    jmp short .out
.live:
    xor ax, ax                      ; the thumb: where the play starts, along
    cmp word [vp_sel], 0            ; the file's frames
    je .at
    mov ax, [vp_ke+KE_K]
.at:
    push dx
    mov cx, VP_BOXW - VP_THW
    mul cx
    div word [vp_frames]
    pop dx
    add ax, [vp_tx1]
    mov [vp_tx], ax
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov ax, [vp_tx1]                ; white before it...
    mov cx, [vp_tx]
    dec cx
    call vp_fillne
    mov ax, [vp_tx]                 ; ...and after it
    add ax, VP_THW
    mov cx, [vp_tx1]
    add cx, VP_BOXW - 1
    call vp_fillne
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, [vp_tx]                 ; ...and the thumb
    mov cx, ax
    add cx, VP_THW - 1
    call vp_fillne
.out:
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
; vp_fmt - the info panel's lines (SPEC.md 98.4), each padded to the width
; (opaque runs, no erase):
;   0 the file   1 its title   2 canvas, screen, fps, length
;   3 the stream's KB/s and its sound   4 where Play starts   5 the message
;   6, 7 what the last play cost
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
    jne .have
    jmp .msg
.have:
    ; 1: the title
    mov di, vp_lines + VP_LINE
    mov si, vp_title
    call vp_puts
    ; 2: the canvas, its screen, the rate, the length
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
    call vp_putt
    ; 3: the stream's rate, and its sound
    mov di, vp_lines + 3 * VP_LINE
    mov ax, [vp_slen]               ; bytes a frame x fps / 1024: every step
    mov dx, [vp_slen+2]             ; inside 32 bits (a frame is < 64 KB)
    mov cx, [vp_frames]
    call vp_div32
    mov cx, [vp_rate]
    call vp_mul32
    mov cx, [vp_spf]
    call vp_div32
    mov cx, 1024
    call vp_div32
    xor bl, bl
    call vp_putn
    mov si, vp_s_kbs
    call vp_puts
    mov bl, [vp_audio]
    xor bh, bh
    shl bx, 1
    mov si, [vp_audnames+bx]
    call vp_puts
    ; 4: where Play starts
    mov di, vp_lines + 4 * VP_LINE
    mov si, vp_s_nokeys
    mov cx, [vp_nkeys]
    jcxz .kl
    mov si, vp_s_start
    cmp word [vp_sel], 0
    jne .key
    call vp_puts
    mov ax, cx
    xor dx, dx
    xor bl, bl
    call vp_putn
    jmp short .msg
.key:
    mov si, vp_s_fromk
    call vp_puts
    mov ax, [vp_sel]
    inc ax
    xor dx, dx
    xor bl, bl
    call vp_putn
    mov si, vp_s_of
    call vp_puts
    mov ax, cx
    xor dx, dx
    call vp_putn
    mov si, vp_s_comma
    call vp_puts
    mov ax, [vp_ke+KE_K]            ; its time: the screen after frame k
    call vp_putt
    jmp short .msg
.kl:
    call vp_puts
.msg:
    ; 5: what Play does, or why not
    mov di, vp_lines + 5 * VP_LINE
    mov si, [vp_msg]
    call vp_puts
    cmp byte [vp_played], 0
    jne .res
    jmp .out
.res:
    ; 6: frames drawn, stalls, pauses
    mov di, vp_lines + 6 * VP_LINE
    mov si, vp_s_drew
    call vp_puts
    mov ax, [vp_done]
    sub ax, [vp_base]
    xor dx, dx
    xor bl, bl
    call vp_putn
    mov si, vp_s_of
    call vp_puts
    mov ax, [vp_frames]
    sub ax, [vp_base]
    xor dx, dx
    call vp_putn
    mov si, vp_s_stall
    call vp_puts
    mov ax, [vp_stall]
    xor dx, dx
    call vp_putn
    cmp byte [vp_snd], 0
    je .nop
    mov si, vp_s_pause
    call vp_puts
    mov ax, [vp_pause]
    xor dx, dx
    call vp_putn
.nop:
    ; 7: late, and the time against the file's
    mov di, vp_lines + 7 * VP_LINE
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
    sub ax, [vp_base]               ; taken: frames x spf / 10 x 182 / rate,
    mul word [vp_spf]               ; in that order so every step fits 32
    mov cx, 10                      ; bits (65,535 x 920 / 10 x 182 < 2^31)
    call vp_div32
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

; vp_putt - AX = frames -> DI as the time they take, m:ss
vp_putt:
    push ax
    push bx
    push cx
    push dx
    mul word [vp_spf]
    mov cx, [vp_rate]
    call vp_div32                   ; DX:AX = seconds
    mov cx, 60
    call vp_div32                   ; ...minutes, CX = the seconds over
    xor bl, bl
    call vp_putn
    mov al, ':'
    call vp_putc
    mov ax, cx
    aam                             ; AH = tens, AL = units
    add ax, '00'
    xchg al, ah
    call vp_putc
    mov al, ah
    call vp_putc
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
    dw 7, 22, VP_CONT_W + 2, VP_CONT_H + TITLE_H + 1  ; W_X = 7 mod 8: the
                                    ; content on a byte (SPEC.md 11.94)
    dw vp_ttl, vp_paint, vp_onkey, vp_clickw

    OS88_MENUSET vp_menus, vp_ttl, vp_oncmd
        OS88_MENU vp_m_file, vp_i_file, 4
    OS88_MENUSET_END vp_menus
vp_ttl:       db 'Video Player', 0
vp_m_file:    db 'File', 0
vp_i_file:    dw vp_it_open, vp_it_play, vp_it_prev, vp_it_next
vp_it_open:   db 'Open...', 0
vp_it_play:   db 'Play (Space)', 0
vp_it_prev:   db 'Previous key (Left)', 0
vp_it_next:   db 'Next key (Right)', 0

; the buttons (SPEC.md 20.5.1.3): Tracker's transport pictures, 16 x 10
    OS88UI_BTNREC vp_btns, vp_brects, vp_blabels, vp_bflags, VP_NB
vp_blabels:   dw vp_i_open, vp_i_prev, vp_i_play, vp_i_next
vp_bflags:    times VP_NB dw OS88UI_IMG
vp_brects:    times VP_NB * 4 dw 0
vp_i_open:                          ; an eject
    db 1, 10
    times 10 dw 0FFFFh
    dw 00180h, 003C0h, 007E0h, 00FF0h, 01FF8h
    dw 03FFCh, 00000h, 03FFCh, 03FFCh, 00000h
vp_i_prev:                          ; |<<
    db 1, 10
    times 10 dw 0FFFFh
    dw 03084h, 0318Ch, 0339Ch, 037BCh, 03FFCh
    dw 03FFCh, 037BCh, 0339Ch, 0318Ch, 03084h
vp_i_play:                          ; >
    db 1, 10
    times 10 dw 0FFFFh
    dw 00C00h, 00F00h, 00FC0h, 00FF0h, 00FFCh
    dw 00FFCh, 00FF0h, 00FC0h, 00F00h, 00C00h
vp_i_next:                          ; >>|
    db 1, 10
    times 10 dw 0FFFFh
    dw 0210Ch, 0318Ch, 039CCh, 03DECh, 03FFCh
    dw 03FFCh, 03DECh, 039CCh, 0318Ch, 0210Ch

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
vp_laycptab:  dw vp_s_cpcga, vp_s_cpherc, vp_s_cpvga
vp_laykb:     db 16, 32, 38             ; each layout's memory image, KB
vp_s_cga:     db 'CGA  ', 0
vp_s_herc:    db 'Herc  ', 0
vp_s_vga:     db 'VGA  ', 0

vp_s_file:    db 'File: ', 0
vp_s_nofile:  db '(none) - File > Open...', 0
vp_s_none:    db 'Open a .V88 to play it', 0
vp_s_ready:   db 'Space plays and pauses; Esc stops', 0
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
vp_s_cpcga:   db 'Made for CGA: plays via a copy', 0
vp_s_cpherc:  db 'Made for Herc: plays via a copy', 0
vp_s_cpvga:   db 'Made for VGA: plays via a copy', 0
vp_s_fps:     db ' fps  ', 0
vp_s_kbs:     db ' KB/s, ', 0
vp_audnames:  dw vp_s_silent, vp_s_pcm8, vp_s_adpcm
vp_s_silent:  db 'silent', 0
vp_s_pcm8:    db 'sound PCM8', 0
vp_s_adpcm:   db 'sound ADPCM4', 0
vp_s_nokeys:  db 'No keyframes: plays from the start', 0
vp_s_start:   db 'From the start; keys ', 0
vp_s_fromk:   db 'From key ', 0
vp_s_comma:   db ', at ', 0
vp_s_kbad:    db 'That keyframe could not be read', 0
vp_s_drew:    db 'Drew ', 0
vp_s_of:      db ' of ', 0
vp_s_stall:   db ', stalls ', 0
vp_s_pause:   db ', pauses ', 0
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
vp_pitper:    db 0                  ; periods a frame, this play
vp_pitper0:   db 0                  ; ...and the file's
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
; the shadow (SPEC.md 98.3.2) and the burst (98.3.3)
vp_shadow:    db 0                  ; this file plays through the shadow
vp_burst:     db 0                  ; the colour burst was turned on
vp_tlay:      db 0                  ; the screen's layout (= [vp_layout] native)
              db 0
vp_caps:      dw 0
vp_ty0:       dw 0                  ; the canvas's top row on the screen
vp_tx0:       dw 0                  ; ...and its left byte
vp_shseg:     dw 0
vp_dy0:       dw 0                  ; the band the next copy covers
vp_dy1:       dw 0
vp_fcap:      dw 0                  ; frames a hook call may draw
vp_due:       dw 0                  ; with sound: the frames due, last call
vp_skipn:     db 0                  ; shadow copies skipped in a row
              db 0
; the sound (SPEC.md 98.3.1)
vp_audio:     db 0                  ; the file's: 0 none, 1 PCM8, 2 ADPCM4
vp_nosnd:     db 0                  ; 1: play silent whatever the machine has
vp_snd:       db 0                  ; this play has the card
vp_hand:      db 0
vp_sopn:      db 0                  ; the stream is open (and owes a close)
vp_sflag:     db 0
vp_afn:       db 0                  ; the silence byte
vp_aseg:      dw 0                  ; the ring, and its control words
vp_tdr:       dw 0
vp_szero:                           ; --- zeroed at every open ---
vp_atot:      dw 0                  ; bytes queued, free-running
vp_alast:     dw 0                  ; the card's consumed count, last seen
vp_aplay:     dw 0, 0               ; ...and summed, 32 bits
vp_afr:       dw 0                  ; frames whose audio is queued
vp_apend:     dw 0                  ; the end's silence runs to here
vp_afinal:    dw 0                  ; ...and the sound itself to here
vp_syncf:     dw 0                  ; frames played at the last word
vp_syncp:     dw 0                  ; [vp_pers] then
vp_pers:      dw 0                  ; periods, free-running
vp_a0:        dw 0                  ; stream bytes before frame 0's
vp_pause:     dw 0                  ; times the card ran dry
vp_skmax:     dw 0                  ; most frames the picture trailed
vp_gap:       dw 0                  ; most periods between two hook calls
vp_aend:      db 0                  ; 1 the end's silence queued, 2 stopped
              db 0
VP_SZERO      equ $ - vp_szero
vp_acap:      dw 0
vp_acnt:      dw 0
va_pc:        times 6 dw 0          ; the audio cursor (vp_next)
vw_pc:        dw 0                  ; vp_next's working copy
vw_po:        dw 0
vw_psec:      dw 0
vw_nsec:      dw 0
vw_fleft:     dw 0
vw_rofs:      dw 0
; the Preview (SPEC.md 98.4)
vp_cx0:       dw 0                  ; the content's origin, as vp_track saw it
vp_cy0:       dw 0
vp_clb:       dw 0                  ; a cluster, bytes
vp_slen:      dw 0, 0               ; the stream's bytes
vp_nkeys:     dw 0                  ; keyframes (0: no Preview, no seek)
vp_ktab:      dw 0, 0
vp_poster:    dw 0                  ; the header's poster, FFFFh none
vp_kmaxb:     dw 0                  ; the largest keyframe record
vp_kbkb:      dw 0                  ; ...and the claim that reads one, KB
vp_sel:       dw 0                  ; the key Play starts at; 0 = the start
vp_kload:     dw 0xFFFF             ; the key vp_ke holds
vp_ke:        times 16 db 0         ; its table entry (98.1.3)
vp_rdseg:     dw 0                  ; vp_rdat's destination
vp_rdend:     dw 0
vp_kshd:      dw 0
vp_pseg:      dw 0                  ; the poster: its claim, 0 = none...
vp_pbw:       dw 0                  ; ...its bytes a row...
vp_ppx:       dw 0                  ; ...its width in pixels...
vp_pdw:       dw 0                  ; ...of which the box shows this many...
vp_prows:     dw 0                  ; ...the rows shown...
vp_pskip:     dw 0                  ; ...from this offset
vp_px:        dw 0                  ; where the last paint put it (the gate
vp_py:        dw 0                  ; reads the screen there)
vp_ploads:    dw 0                  ; posters made: the gate waits on it
vp_bx1:       dw 0                  ; the box's inside, screen
vp_by1:       dw 0
vp_bx2:       dw 0
vp_by2:       dw 0
vp_tx1:       dw 0                  ; the bar's inside, and the thumb
vp_tx:        dw 0
vh_sseg:      dw 0                  ; vp_half's image...
vh_lay:       db 0                  ; ...its layout, or FFh linear...
              db 0
vh_sstr:      dw 0                  ; ...at this stride
vh_wb:        dw 0
vh_h:         dw 0
vh_dseg:      dw 0
vh_owb:       dw 0
vh_y:         dw 0
; the play's start and its pause (98.3.4, 98.3.5)
vp_base:      dw 0                  ; the first frame the stream draws
vp_krec:      dw 0                  ; the keyframe's record in the ring, or FFFFh
vp_kidx:      dw 0                  ; records to step over after it
vp_ssp:       dw 0, 0               ; the first super-packet this play reads
vp_ssec:      dw 0
vp_upause:    db 0                  ; Space: paused
vp_aref:      db 0                  ; ADPCM4's reference byte, this play
vp_ptk0:      dw 0                  ; the tick it paused at
vp_ptk:       dw 0                  ; ticks paused, this play
vp_fsi:       times FSI_SIZE db 0
vp_cur:       times FSEQ_SIZE db 0

%define OS88UI_ABOUT                ; the standard About card (SPEC.md 20.5.1)
%define OS88UI_BIMG                 ; ...and buttons with PICTURES, drawn with
%define OS88UI_NOGLYPH              ; no pixel written twice (SPEC.md 13.8.9),
%include "os88ui.inc"               ; and no check box or radio at all

; --- bss: zeroed by the loader, and no bytes of the file ----------------------
vp_dtab       equ os88_image_end    ; the half-scaler's two tables (vp_mkdtab)
vp_lines      equ vp_dtab + 512     ; the info panel's text
    OS88_BSS 512 + VP_LINES * VP_LINE
    OS88_IMAGE_END
