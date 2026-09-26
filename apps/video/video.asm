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

    OS88_HEADER 'Video Player', vp_entry, 0x23  ; icon, assoc, doc glyph

; --- the icon (SPEC.md 20.2): a play button --------------------------------
; A solid disc with a play triangle cut out of it, so it reads as one shape
; on every adapter - no grey, no one-pixel stroke (SPEC.md 39.4). The mask
; is the disc dilated one pixel, a white underlay round it.
;
;   .....######.....    the data; the mask is every pixel but the corners
;   ..##########..
;   .####.#######.      (rows 0-2 and 13-15 shown trimmed)
;   .####..######.
;   #####....#####
;   #####.....####
;   #####.......##
    OS88_ICON16
    dw 0x3FFC, 0x7FFE, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF
    dw 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0x7FFE, 0x3FFC
    dw 0x07E0, 0x1FF8, 0x3FFC, 0x7BFE, 0x79FE, 0xF87F, 0xF83F, 0xF80F
    dw 0xF80F, 0xF83F, 0xF87F, 0x79FE, 0x7BFE, 0x3FFC, 0x1FF8, 0x07E0
    OS88_ICON16_END

    OS88_ASSOC16                    ; SPEC.md 54.6: double-click a .V88
    db 1
    OS88_ASSOC_EXT 'V88'
    OS88_ASSOC16_END

; --- what a .V88 wears (SPEC.md 54.3.2) -------------------------------------
; The disc reduced by majority would be a solid blob with the triangle gone,
; so a document wears the triangle alone, black on its page.
    OS88_DOCGLYPH8
    db 0x40                         ; .#......
    db 0x70                         ; .###....
    db 0x7C                         ; .#####..
    db 0x7E                         ; .######.
    db 0x7C                         ; .#####..
    db 0x70                         ; .###....
    db 0x40                         ; .#......
    db 0x00                         ; ........
    OS88_DOCGLYPH8_END

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
; --- the window (SPEC.md 98.4.1): content-relative, every x a byte's. What
;     depends on the file and the screen is vp_layfit's, in the vp_l* words
VP_BOXX     equ 8                   ; the picture box's inside, top left
VP_BOXY     equ 6
VP_MINBW    equ 208                 ; ...never narrower than the button row
VP_BARH     equ 10                  ; the scrub bar, frame included
VP_THW      equ 8                   ; the thumb's width
VP_CARDW    equ 280                 ; the info card: VP_COLS cells
VP_TXTY     equ 6
VP_CARDH    equ VP_TXTY + VP_LINES * VP_LPITCH + 4
VP_CARDBY   equ 96                  ; the buttons in the card, under its text
VP_CARDHB   equ VP_CARDBY + 20 + 4
VP_BTW      equ 28                  ; a button (Tracker's transport, SPEC.md
VP_BTH      equ 20                  ; 45), and their pitch
VP_BTP      equ 32
VP_NB       equ 4                   ; Open, previous key, Play, next key...
VP_NBTN     equ VP_NB + 1           ; ...and the info card's
VP_DRAGT    equ 9                   ; ticks between loads mid-drag, 286 up
VP_BSLACK   equ 3                   ; the box's rows under the picture: its
                                    ; top goes down to a bank (98.3.7)
VPX_STOP    equ 1                   ; how a bracket ended (98.3.7): stopped,
VPX_SWAP    equ 2                   ; swapped between window and full screen,
VPX_DESK    equ 3                   ; back to the desktop, paused - never 0,
                                    ; which is vp_poll's "nothing" 
VP_KMAXREC  equ 61440               ; the largest keyframe record we will read:
                                    ; a VGA8 one is up to a canvas (98.1.3),
                                    ; and what bounds it is the read - the
                                    ; record and a cluster either side in one
                                    ; 64 KB claim, which vp_parse works out

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
R_PAL       equ 32                  ; VGA8: the palette's offset (98.1.1)
R_RSCALE    equ 36                  ; ...and its row scale, 0/1 or 2
R_FLIP      equ 37                  ; MODEX: 2 = two pages, flipped (98.3.8)
VP_PAGE     equ 19200               ; a Mode X page, in plane bytes
VP_PREVKB   equ 31                  ; the last record's copy: REC_MAX + slack
PF_VGA8     equ 2                   ; [vp_pixfmt] is the format less one
PF_VGA4     equ 3                   ; ...16 colours on mode 12h's planes
LAY_LIN320  equ 3                   ; ...and [vp_layout] the layout less one
LAY_LIN80   equ 2
LAY_MODEX   equ 4
VP_MXPL     equ 0x4B0               ; a MODEX plane image, 19,200 bytes, in
                                    ; paragraphs: plane p of a RAM copy is
                                    ; at + p x this (98.1.3.1)
VP_MXSHD    equ 121                 ; ...and the claim a keyframe decodes
                                    ; into: plane 3's base + 64 KB, so a
                                    ; 16-bit write from any plane stays in
                                    ; it (98.1.6)
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
    OS88_ALTENTER_ARM               ; the key-state map, for Alt+Enter
    call OSAPI_CPU_INFO             ; a 286 loads keys as the thumb is
    mov [vp_tier], al               ; dragged (98.4.2)
    mov word [vp_wb], 80            ; THE WINDOW'S SIZE is the layout's, for a
    mov word [vp_pwb], 80           ; 640 x 200 video until one is open
    mov word [vp_h], 200
    mov word [vp_ph], 200
    call vp_layfit
    mov ax, [vp_lcw]
    add ax, 2
    mov [vp_tpl+4], ax
    mov ax, [vp_lch]
    add ax, TITLE_H + 1
    mov [vp_tpl+6], ax
    mov si, vp_tpl
    call OSAPI_WM_CREATE
    jc .fail
    mov [vp_win], bx
    mov al, 1                       ; A FIXED LAYOUT (SPEC.md 11.93): its
    call OSAPI_WM_KEEPH             ; height hangs over the dock rather than
                                    ; be cut - CGA's band is too short for the
                                    ; picture, the bar and the buttons (98.4.1)
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
; The document named at launch; then a layout owed (a file opened, the card
; toggled) - the picture made again if its scale moved, the caption made for
; the width to come (98.4.3), and the window resized to it. The resize is
; made UNDER our lock: the slot takes one itself now when a caller has none
; (SPEC.md 11.1.2), and a kernel from before that drew the grown window over
; the pointer with no hide promised
vp_onwake:
    push ax
    push bx
    push cx
    push dx
    call OSAPI_GFX_LOCK
    cmp byte [vp_argpend], 0
    je .lay
    mov byte [vp_argpend], 0
    mov dx, [vp_argdir]             ; where the document is (SPEC.md 54.5)
    mov bl, [vp_argvol]
    call OSAPI_FILE_GOTO_Q
    call vp_open
.lay:
    cmp byte [vp_relay], 0
    je .paint
    mov byte [vp_relay], 0
    call vp_layfit
    or ax, ax
    jz .size
    mov ax, [vp_dkey]               ; the picture at the new scale: the
    cmp ax, 0xFFFF                  ; session's frame, or a key's
    je .size
    cmp ax, 0xFFFE
    jne .key
    call vp_sesspic
    jmp short .size
.key:
    call vp_loadkey
    call vp_fmt
.size:
    mov cx, [vp_lcw]
    add cx, 2
    call vp_mkcap                   ; for the width it is about to have
    mov bx, [vp_win]
    call OSAPI_WM_GEOM              ; CX, DX = the content now
    cmp cx, [vp_lcw]
    jne .resize
    cmp dx, [vp_lch]
    jne .resize
    xor ax, ax                      ; the same size, maybe a new file: the
    call OSAPI_WM_TITLE             ; caption's strip and nothing else
.paint:
    call vp_repaint
    jmp short .unl
.resize:
    mov cx, [vp_lcw]
    add cx, 2
    mov dx, [vp_lch]
    add dx, TITLE_H + 1
    call OSAPI_WM_RESIZE            ; ...which draws the caption made above
    call OSAPI_WM_GEOM
    inc cx
    inc cx
    mov ax, [vp_lcw]
    inc ax
    inc ax
    cmp cx, ax
    jae .unl
    call vp_mkcap                   ; clamped below what we asked for: made
    xor ax, ax                      ; again for the width it got
    call OSAPI_WM_TITLE
.unl:
    call OSAPI_GFX_UNLOCK
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vp_mkcap - the caption for a window CX pixels wide, into vp_cap, which the
; record's W_TITLE names (SPEC.md 98.4.3): 'Video Player - <title>', else
; 'Video - <title>', else the title cut to fit - n characters fit when
; 8n <= CX - 56. The title is the header's, or the file's name without one
vp_mkcap:
    push ax
    push bx
    push cx
    push si
    push di
    mov ax, cx
    sub ax, 56
    jnc .w
    xor ax, ax
.w:
    mov cl, 3
    shr ax, cl                      ; AX = the characters the bar has room for
    mov di, vp_cap
    mov si, vp_ttl
    cmp byte [vp_loaded], 0
    je .last                        ; nothing open: the name alone
    mov si, vp_title
    cmp byte [si], 0
    jne .len
    mov si, vp_name
.len:
    mov bx, si
    mov cx, 15                      ; 'Video Player - '
.l:
    cmp byte [bx], 0
    je .ld
    inc bx
    inc cx
    jmp short .l
.ld:
    mov bx, vp_pfx1
    cmp cx, ax
    jbe .pre
    mov bx, vp_pfx2
    sub cx, 7                       ; 'Video - '
    cmp cx, ax
    ja .last
.pre:
    xchg si, bx
    call .cpy                       ; the prefix, then the title
    mov si, bx
.last:
    call .cpy
    mov byte [di], 0
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret
.cpy:                               ; SI to DI while AX lasts
    or ax, ax
    jz .cd
    mov cl, [si]
    or cl, cl
    jz .cd
    mov [di], cl
    inc si
    inc di
    dec ax
    jmp short .cpy
.cd:
    ret

; --- the menu, the keys and the buttons (SPEC.md 98.4) ---------------------------
vp_oncmd:                           ; AL = item, AH = menu, SI = window
    call vp_abdismiss
    cmp al, 1
    jb vp_opendlg
    je .play
    cmp al, 2
    je .fs
    cmp al, 5
    je vp_cardtog
    sub al, 3                       ; 3, 4: the key before, the key after
    mov ax, -1
    je .s
    mov ax, 1
.s:
    jmp vp_step
.fs:
    jmp vp_fsenter
.play:
    jmp vp_play

vp_opendlg:
    mov al, 2                       ; a new file: the session goes
    call vp_stopfor
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
    cmp ax, KEY_ALTENTER            ; Alt+Enter and F: full screen, PAUSED -
    je .fs                          ; it plays when Space says so (98.3.6)
    cmp ah, KSC_LEFT
    je .prev
    cmp ah, KSC_RIGHT
    je .next
    cmp al, 27                      ; Esc: a waiting session stops, where it
    je .esc                         ; got to kept
    cmp al, 13                      ; Enter, Space or P plays
    je .play
    cmp al, ' '
    je .play
    or al, 0x20
    cmp al, 'p'
    je .play
    cmp al, 'f'
    je .fs
    cmp al, 'i'
    jne .out
    call vp_cardtog
    jmp short .out
.esc:
    xor al, al
    call vp_stopfor
    jmp short .out
.fs:
    call vp_fsenter
    jmp short .out
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

; vp_cardtog - the info card out or in: a new layout, and the window resized
; to it, from the wake - OSAPI_WM_RESIZE may not be called under the lock
vp_cardtog:
    cmp byte [vp_lbin], 0           ; the buttons live in it: it stays
    jne .out
    xor byte [vp_card], 1
    mov byte [vp_relay], 1
    push bx
    mov bx, [vp_win]
    call OSAPI_WM_WAKE
    pop bx
.out:
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

; a press on no button: on the scrub bar it takes the THUMB (98.4.2), which
; follows the pointer until the release picks the key under it
vp_onclick:                         ; CX = x, DX = y (screen), SI = window
    push ax
    push cx
    push dx
    cmp word [vp_nkeys], 0
    je .out
    mov ax, dx
    sub ax, [vp_cy0]
    sub ax, [vp_lbary]
    cmp ax, VP_BARH
    jae .out
    mov ax, cx
    sub ax, [vp_cx0]
    sub ax, VP_BOXX
    cmp ax, [vp_lbw]
    jae .out
    mov byte [vp_drag], 1
    call vp_dragx
    call OSAPI_GET_TICKS
    mov [vp_dtk], ax
    call vp_pbar
.out:
    pop dx
    pop cx
    pop ax
    ret

; W_ONDRAG: the thumb follows the pointer; a button follows the press. On a
; 286 or better the picture follows too, a load at most every VP_DRAGT ticks
; (a key's load is ~1.3 s on an 8088, which a drag cannot wait for there -
; it loads on the release)
vp_ondrag:
    call vp_clip
    cmp byte [vp_drag], 0
    jne .thumb
    push bx
    mov bx, vp_btns
    call os88ui_btndrag
    pop bx
    ret
.thumb:
    push ax
    push dx
    mov dx, [vp_tpos]
    call vp_dragx                   ; AX = the key under it
    cmp dx, [vp_tpos]
    je .still
    call vp_pbar
.still:
    cmp byte [vp_tier], CPU_286
    jb .out
    cmp ax, [vp_sel]
    je .out
    push ax
    call OSAPI_GET_TICKS
    sub ax, [vp_dtk]
    cmp ax, VP_DRAGT
    pop ax
    jb .out
    call vp_seekto                  ; (the thumb stays under the pointer)
    call OSAPI_GET_TICKS            ; ...and the interval runs from the load's
    mov [vp_dtk], ax                ; END, so a slow disk is not asked again
.out:                               ; the moment it answers
    pop dx
    pop ax
    ret

; vp_dragx - CX = the pointer's x: [vp_tpos] the thumb under it, AX = the key
; whose share of the bar that is. Preserves the rest
vp_dragx:
    push cx
    push dx
    mov ax, cx
    sub ax, [vp_cx0]
    sub ax, VP_BOXX                 ; along the bar, clamped to it
    jns .p
    xor ax, ax
.p:
    mov cx, [vp_lbw]
    dec cx
    cmp ax, cx
    jbe .q
    mov ax, cx
.q:
    push ax
    sub ax, VP_THW / 2              ; the thumb centred on it, inside the bar
    jns .t
    xor ax, ax
.t:
    mov cx, [vp_lbw]
    sub cx, VP_THW
    cmp ax, cx
    jbe .u
    mov ax, cx
.u:
    mov [vp_tpos], ax
    pop ax
    mul word [vp_nkeys]
    div word [vp_lbw]
    pop dx
    pop cx
    ret

vp_onup:                            ; W_ONMOUSEUP: the button FIRES here
    push ax
    push bx
    push si
    call vp_track
    call vp_clip
    mov si, [vp_win]
    cmp byte [vp_drag], 0
    je .btn
    call vp_dragx                   ; THE THUMB'S RELEASE: the key under it
    mov byte [vp_drag], 0
    cmp ax, [vp_sel]
    je .snap
    call vp_seekto
    jmp short .out
.snap:
    call vp_pbar                    ; ...the one already picked: it snaps back
    jmp short .out
.btn:
    mov bx, vp_btns
    call os88ui_btnup               ; AX = the button, index + 1, or 0
    dec ax
    js .out
    jz .open
    dec ax
    jz .prev
    dec ax
    jz .play
    dec ax
    jz .next
    call vp_cardtog
    jmp short .out
.next:
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

; vp_step - AX = -1 or +1: the key before or after the one picked
vp_step:
    push ax
    push ax                         ; a session steps from where it IS: the
    mov al, 1                       ; key at or before it, then this one
    call vp_stopfor
    pop ax
    add ax, [vp_sel]
    js .out
    call vp_seekto
.out:
    pop ax
    ret

; vp_seekto - AX = a keyframe: the play starts there (98.3.5), and the box
; shows it. Lock held
vp_seekto:
    push ax
    push bx
    cmp ax, [vp_nkeys]
    jae .out
    push ax
    mov al, 2                       ; a key picked outright: the session goes
    call vp_stopfor
    pop ax
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
    mov bx, [vp_win]                ; the layout and the paint: the wake's
    call OSAPI_WM_WAKE
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
    call vp_rdpal                   ; VGA8's palette, and its luma
    jc .free
    mov byte [vp_loaded], 1
    call vp_canplay
.free:
    mov dx, [vp_tmp]
    call OSAPI_MEM_FREE
    cmp byte [vp_loaded], 0         ; THE LAYOUT for this video (98.4.1),
    je .out                         ; owed to the wake - with the card out
    mov byte [vp_relay], 1          ; if the file will not play here, since
    cmp byte [vp_ok], 0             ; the card is what says why
    jne .lf
    mov byte [vp_card], 1
.lf:
    call vp_layfit
    mov ax, [vp_poster]             ; THE POSTER (98.4): the header's keyframe,
    cmp ax, [vp_nkeys]              ; at the layout's scale - and only once the
    jae .out                        ; header's claim is gone, so the poster's
    call vp_loadkey                 ; sits under what is freed
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
    cmp al, PF_VGA4
    ja .bad
    mov [vp_pixfmt], al
    mov bl, [es:V88_REND+R_LAYOUT]  ; 1..5, and the canvas inside it
    dec bl
    cmp bl, LAY_MODEX
    ja .bad
    mov [vp_layout], bl
    mov word [vp_palo], 0
    mov word [vp_palo+2], 0
    cmp al, PF_VGA8                 ; VGA8 is LIN320's and MODEX's, and
    je .v8                          ; they take nothing else
    cmp al, PF_VGA4                 ; VGA4 is LIN80's planes (98.1.3.2)
    jne .v1
    cmp bl, LAY_LIN80
    jne .bad
    jmp short .lay
.v1:
    cmp bl, LAY_LIN320
    jae .bad
    jmp short .lay
.v8:
    cmp bl, LAY_LIN320
    jb .bad
    mov ax, [es:V88_REND+R_PAL]     ; the palette, on a sector
    or ax, ax
    jz .bad
    test ax, 511
    jnz .bad
    mov [vp_palo], ax
    mov ax, [es:V88_REND+R_PAL+2]
    mov [vp_palo+2], ax
.lay:
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
    ; PLANES (98.1.3.1, 98.1.3.2): Mode X's four byte-planes, or VGA4's four
    ; bit-planes, and how far apart a RAM image keeps them
    mov byte [vp_planar], 0
    cmp byte [vp_layout], LAY_MODEX
    jne .pl2
    mov byte [vp_planar], 1
    mov word [vp_plsp], VP_MXPL
    jmp short .pl3
.pl2:
    cmp byte [vp_pixfmt], PF_VGA4
    jne .pl3
    mov byte [vp_planar], 2
    mov cx, 80                      ; h rows of 80 bytes, in paragraphs
    mul cx
    add ax, 15
    mov cl, 4
    shr ax, cl
    mov [vp_plsp], ax
.pl3:
    ; THE ROW SCALE (98.2.4): each row shown twice by the CRTC, VGA8 only
    mov byte [vp_rs], 0
    mov al, [es:V88_REND+R_RSCALE]
    cmp al, 1
    jbe .rs1
    cmp al, 2
    jne .bad
    cmp byte [vp_pixfmt], PF_VGA8
    jne .bad
    mov byte [vp_rs], 1
.rs1:
    mov byte [vp_flip], 0           ; PAGE FLIPPING (98.3.8): Mode X's own
    mov al, [es:V88_REND+R_FLIP]
    cmp al, 1
    jbe .fl1
    cmp al, 2
    jne .bad
    cmp byte [vp_layout], LAY_MODEX
    jne .bad
    mov byte [vp_flip], 1
.fl1:
    mov ax, [vp_h]                  ; ...and the rows the picture SHOWS,
    mov cl, [vp_rs]                 ; which is what the Preview is made at
    shl ax, cl
    mov [vp_ph], ax
    ; THE PREVIEW'S WIDTH (98.4): a one-bit canvas's own, or for VGA8 the
    ; luma of its keyframe dithered to one bit, a byte per eight pixels -
    ; so what sizes and places the poster reads this and not [vp_wb]
    mov cx, [vp_wb]
    cmp byte [vp_pixfmt], PF_VGA8
    jne .pgeo
    cmp byte [vp_layout], LAY_MODEX ; MODEX: a plane byte is four pixels,
    jne .pl320                      ; so two of them make the poster's one
    shr cx, 1
    jc .bad
    jmp short .pgeo
.pl320:
    test cl, 7                      ; ...eight pixels to its byte
    jnz .bad
    shr cx, 1
    shr cx, 1
    shr cx, 1
.pgeo:
    mov [vp_pwb], cx
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
    cmp bx, 7                       ; an empty planar key is 7 bytes
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
    cmp byte [vp_pixfmt], PF_VGA8   ; colour has no one-bit screen to be
    jae .none                       ; copied onto
    mov al, 2                       ; LIN80, HERC, CGA: the roomiest first
.l:
    cmp al, [vp_layout]
    je .n
    call vp_try
    jnc .shadow
.n:
    dec al
    jns .l
.none:
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
    mov al, [vp_tlay]               ; THE FULL SCREEN's, kept: a bracket in the
    mov [vp_fslay], al              ; window sets its own (98.3.7)
    mov al, [vp_mode]
    mov [vp_fsmode], al
    mov al, [vp_shadow]
    mov [vp_fsshd], al
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
    mov ax, [vp_ph]                 ; the rows it SHOWS
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
    call vp_psize                   ; THE PICTURE'S claim FIRST, so it sits
    call OSAPI_MEM_CLAIM            ; under the two that are freed at the end            ; no room for a picture: the box is black
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
    push bx                         ; (the decode takes every register)
    call vp_kpic
    pop bx
    jc .nent
    mov [vp_dkey], bx
    mov ax, [vp_ps]
    mov [vp_pscale], ax
    jmp short .free
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
    mov word [vp_dkey], 0xFFFF
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
    cmp ax, 7                       ; said the largest is (and no shorter
    jb .bad                         ; than an empty one: 7 bytes planar,
    cmp byte [vp_planar], 0         ; 16 one-bit - BX is the key, kept)...
    jne .kmin
    cmp ax, 16
    jb .bad
.kmin:
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
    cmp byte [vp_planar], 0
    je .kc
    call vp_plshd                   ; planes: the last one's base + 64 KB
.kc:
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
    push ds
    mov ds, dx
    call vp_decram                  ; ES = the shadow, from its address 0
    pop ds
    call vp_mkpic
    clc
.free:
    pushf
    mov dx, [vp_kshd]
    call OSAPI_MEM_FREE
    popf
.no:
    ret

; vp_mkpic - the canvas in [vp_kshd] (the file's layout) into [vp_pseg] at
; the layout's scale: its own size, a half or a quarter (98.4)
vp_mkpic:
    push ax
    push cx
    push dx
    cmp byte [vp_pixfmt], PF_VGA4   ; 16 COLOURS: packed for OSAPI_GFX_BLIT4,
    jne .n4                         ; every [vp_ps]-th pixel (98.4.5)
    call vp_v4pack
    jmp .rows4
.n4:
    cmp byte [vp_pixfmt], PF_VGA8   ; 256 COLOURS: the luma dithered to one
    jne .mono                       ; bit, dense at its own size, and halved
    call vp_v8mono                  ; in place from there
    mov ax, [vp_pwb]
    mov [vh_sstr], ax
    mov [vh_wb], ax
    mov ax, [vp_ph]
    mov [vh_h], ax
    mov ax, [vp_pwb]
    mov cl, 3
    shl ax, cl
    cmp word [vp_ps], 1
    je .v8own
    mov ax, [vp_pseg]
    mov [vh_sseg], ax
    mov [vh_dseg], ax
    mov byte [vh_lay], 0xFF
    call vp_half
    mov ax, [vp_pwb]
    shl ax, 1
    shl ax, 1
    cmp word [vp_ps], 2
    je .sized
    mov ax, [vh_wb]
    mov [vh_sstr], ax
    call vp_half
    mov ax, [vp_pwb]
    shl ax, 1
    jmp short .sized
.v8own:
    mov [vp_ppx], ax
    mov ax, [vp_pwb]
    mov [vp_pbw], ax
    mov ax, [vp_ph]
    jmp short .rows
.mono:
    cmp word [vp_ps], 1             ; AT ITS OWN SIZE: the rows out of the
    jne .half                       ; file's layout, dense
    call vp_linear
    mov ax, [vp_wb]
    mov [vp_pbw], ax
    mov cl, 3
    shl ax, cl
    mov [vp_ppx], ax
    mov ax, [vp_h]
    jmp short .rows
.half:
    mov ax, [vp_kshd]               ; HALVED: out of the file's layout...
    mov [vh_sseg], ax
    mov al, [vp_layout]
    mov [vh_lay], al
    mov ax, [vp_wb]
    mov [vh_wb], ax
    mov ax, [vp_h]
    mov [vh_h], ax
    mov ax, [vp_pseg]
    mov [vh_dseg], ax
    call vp_half
    mov ax, [vp_wb]                 ; ...its width half the canvas's
    shl ax, 1
    shl ax, 1
    cmp word [vp_ps], 2
    je .sized
    mov ax, [vp_pseg]               ; ...or a QUARTER, the second pass in
    mov [vh_sseg], ax               ; place: its rows are dense now
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
    mov ax, [vh_h]
.rows:
    mov [vp_prows], ax
.rows4:
    mov word [vp_pskip], 0
    inc word [vp_ploads]
    pop dx
    pop cx
    pop ax
    ret

; vp_sesspic - the session's frame (the keeper) in the box (98.3.7): what a
; bracket paused back to the desktop shows, and a new layout remakes
vp_sesspic:
    push ax
    push dx
    mov ax, [vp_pscale]
    cmp ax, [vp_ps]
    je .same
    call vp_pfree                   ; a claim for another scale
.same:
    cmp word [vp_pseg], 0
    jne .have
    call vp_psize
    call OSAPI_MEM_CLAIM
    jc .out
    mov [vp_pseg], dx
.have:
    mov ax, [vp_keep]
    or ax, ax
    jz .out
    mov [vp_kshd], ax
    call vp_mkpic
    mov ax, [vp_ps]
    mov [vp_pscale], ax
    mov word [vp_dkey], 0xFFFE
.out:
    pop dx
    pop ax
    ret

; vp_psize - AX = the picture's claim at the layout's scale, KB: the canvas,
; or its first half (a quarter is the second pass, in place)
vp_psize:
    push cx
    push dx
    cmp byte [vp_pixfmt], PF_VGA4   ; packed nibbles at the scale
    jne .n4
    call vp_v4dims                  ; AX = bytes a row, CX = rows
    jmp short .sz
.n4:
    mov ax, [vp_pwb]
    mov cx, [vp_ph]
    cmp byte [vp_pixfmt], PF_VGA8   ; made whole, then halved in place
    je .sz
    cmp word [vp_ps], 1
    je .sz
    inc ax
    shr ax, 1
    inc cx
    shr cx, 1
.sz:
    mul cx
    add ax, 1023
    adc dx, 0
    mov cl, 10
    shr ax, cl
    mov cl, 6
    shl dx, cl
    or ax, dx
    pop dx
    pop cx
    ret

; vp_linear - the canvas out of the shadow ([vp_kshd], the file's layout)
; into [vp_pseg], a row after the other at [vp_wb] bytes
vp_linear:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push ds
    push es
    mov es, [vp_pseg]
    xor di, di
    xor dx, dx                      ; DX = the row
.r:
    cmp dx, [vp_h]
    jae .done
    mov ax, dx
    mov bl, [vp_layout]
    call vp_rowaddr
    mov si, ax
    mov cx, [vp_wb]
    mov ax, [vp_kshd]
    push ds
    mov ds, ax
    cld
    rep movsb
    pop ds
    inc dx
    jmp short .r
.done:
    pop es
    pop ds
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vp_rdpal - a VGA8 file's palette (98.1.1) into vp_pal, and the luma the
; Preview dithers by into vp_lum: (77 r + 150 g + 29 b) >> 8 of the DAC's
; six bits, then x 17 + 32 >> 6 for 0..16 against a 4 x 4 Bayer cell -
; tools/os88vid.py's vga8_lum16. CF=1 with [vp_msg] set: unreadable, or a
; value past the DAC's 63. Nothing for any other format
vp_rdpal:
    cmp byte [vp_pixfmt], PF_VGA8
    je .go
    clc
    ret
.go:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov ax, [vp_clb]                ; 768 bytes and a cluster either side
    add ax, ax
    add ax, 768 + 1023
    mov cl, 10
    shr ax, cl
    call OSAPI_MEM_CLAIM
    jc .mem
    mov [vp_rdseg], dx
    mov ax, [vp_palo]
    mov dx, [vp_palo+2]
    mov cx, 768
    call vp_rdat
    jc .io
    push ds
    pop es
    mov di, vp_pal
    mov cx, 768
    push ds
    mov ds, [vp_rdseg]
    cld
    rep movsb
    pop ds
    mov si, vp_pal                  ; every value a six-bit one
    mov cx, 768
.chk:
    lodsb
    cmp al, 63
    ja .bad
    loop .chk
    mov si, vp_pal
    mov di, vp_lum
    mov cx, 256
.lum:
    push cx
    lodsb
    mov bl, 77
    mul bl
    mov bx, ax
    lodsb
    mov cl, 150
    mul cl
    add bx, ax
    lodsb
    mov cl, 29
    mul cl
    add ax, bx
    mov al, ah                      ; >> 8: 0..63
    mov cl, 17
    mul cl
    add ax, 32
    mov cl, 6
    shr ax, cl                      ; 0..16
    mov [di], al
    inc di
    pop cx
    loop .lum
    mov dx, [vp_rdseg]
    call OSAPI_MEM_FREE
    clc
    jmp short .out
.bad:
    mov word [vp_msg], vp_s_bad
    jmp short .fr
.io:
    mov word [vp_msg], vp_s_io
.fr:
    mov dx, [vp_rdseg]
    call OSAPI_MEM_FREE
    stc
    jmp short .out
.mem:
    mov word [vp_msg], vp_s_mem
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vp_dac - VGA8: the file's 256 colours into the DAC, once the bracket has
; set 13h (the mode set loads the BIOS's own, and the bracket's restore
; sets the desktop's back). Preserves all
vp_dac:
    cmp byte [vp_pixfmt], PF_VGA8
    jne .out
    push ax
    push cx
    push dx
    push si
    mov dx, 0x3C8
    xor al, al
    out dx, al
    inc dx
    mov si, vp_pal
    mov cx, 768
    cld
.l:
    lodsb
    out dx, al
    loop .l
    pop si
    pop dx
    pop cx
    pop ax
.out:
    ret

; vp_crtc - a row scale of 2 (98.2.4): the CRTC's Maximum Scan Line (3D4h
; index 9) shows each row twice as many scan lines - 13h's and Mode X's 1
; (two lines a row) becomes 3 - so the mode's rows halve and the picture
; stays the screen's size. The bracket's restore sets the mode, and it,
; back. Preserves all
vp_crtc:
    cmp byte [vp_rs], 0
    je .out
    push ax
    push dx
    mov dx, 0x3D4
    mov al, 9
    out dx, al
    inc dx
    in al, dx
    mov ah, al
    and ah, 0xE0
    and al, 0x1F
    shl al, 1
    inc al                          ; n + 1 lines a row, twice: 2n + 1
    or al, ah
    out dx, al
    pop dx
    pop ax
.out:
    ret

; vp_v8mono - the VGA8 canvas in [vp_kshd] (LIN320: row y at y x 320) as a
; one-bit one in [vp_pseg], dense at [vp_pwb] bytes a row: a pixel is lit
; when its luma beats the 4 x 4 Bayer cell over it (tools/os88vid.py's
; vga8_mono, bit for bit). Preserves all
vp_v8mono:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    cmp byte [vp_layout], LAY_MODEX
    jne .lin
    jmp .mx
.lin:
    mov es, [vp_kshd]
    xor di, di                      ; DI = the output byte
    xor dx, dx                      ; DX = the row
.row:
    cmp dx, [vp_ph]
    jae .done
    mov ax, dx                      ; the canvas row this output row shows
    mov cl, [vp_rs]                 ; (each twice with a row scale of 2)
    shr ax, cl
    push dx
    mov cx, 320
    mul cx
    pop dx
    mov si, ax                      ; ES:SI = the row's first pixel
    mov bx, dx                      ; the row's four thresholds, where BX
    and bx, 3                       ; can index them
    shl bx, 1
    shl bx, 1
    mov ax, [vp_bayer4+bx]
    mov [vp_rthr], ax
    mov ax, [vp_bayer4+bx+2]
    mov [vp_rthr+2], ax
    mov cx, [vp_pwb]
.byte:
    push cx
    xor ah, ah                      ; AH = the byte, built from the left
    mov cx, 8
.pix:
    mov bl, [es:si]
    inc si
    xor bh, bh
    mov al, [vp_lum+bx]
    mov bx, si                      ; x & 3 of the pixel just read
    dec bx
    and bx, 3
    cmp [vp_rthr+bx], al            ; CF = threshold < luma: lit
    rcl ah, 1
    loop .pix
    push ds
    push ax
    mov ax, [vp_pseg]
    mov ds, ax
    pop ax
    mov [di], ah
    pop ds
    inc di
    pop cx
    loop .byte
    inc dx
    jmp short .row
.done:
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.mx:                                ; MODEX: pixel x of a row is plane x mod
    mov ax, [vp_kshd]               ; 4, byte x div 4 - so an output byte's
    mov bx, vp_mxseg                ; eight are two bytes of each plane
    mov cx, 4
.seg:
    mov [bx], ax
    add ax, VP_MXPL
    inc bx
    inc bx
    loop .seg
    xor di, di
    xor dx, dx
.mrow:
    cmp dx, [vp_ph]
    jae .done
    mov ax, dx
    mov cl, [vp_rs]
    shr ax, cl
    push dx
    mov cx, 80
    mul cx
    pop dx
    mov bp, ax                      ; BP = the row in each plane
    mov bx, dx
    and bx, 3
    shl bx, 1
    shl bx, 1
    mov ax, [vp_bayer4+bx]
    mov [vp_rthr], ax
    mov ax, [vp_bayer4+bx+2]
    mov [vp_rthr+2], ax
    mov cx, [vp_pwb]
.mbyte:
    push cx
    xor ah, ah
    xor cx, cx                      ; CX = the pixel, 0..7
.mpix:
    mov bx, cx
    and bx, 3
    shl bx, 1
    mov es, [vp_mxseg+bx]
    mov bx, cx
    shr bx, 1
    shr bx, 1
    add bx, bp
    mov bl, [es:bx]
    xor bh, bh
    mov al, [vp_lum+bx]
    mov bx, cx
    and bx, 3
    cmp [vp_rthr+bx], al            ; CF = threshold < luma: lit
    rcl ah, 1
    inc cx
    cmp cx, 8
    jb .mpix
    push ds
    push ax
    mov ax, [vp_pseg]
    mov ds, ax
    pop ax
    mov [di], ah
    pop ds
    inc di
    inc bp
    inc bp
    pop cx
    loop .mbyte
    inc dx
    jmp short .mrow

; vp_plshd - AX = the KB a planar keyframe decodes into: three planes'
; spacing and 64 KB past the last one's base, so a 16-bit write from any
; plane is inside the claim (98.1.6)
vp_plshd:
    push cx
    mov ax, [vp_plsp]
    mov cx, ax
    shl ax, 1
    add ax, cx                      ; 3 x plsp paragraphs
    add ax, 4096 + 63               ; + 64 KB, rounded up to a KB
    mov cl, 6
    shr ax, cl
    pop cx
    ret

; vp_v4dims - AX = a VGA4 poster's bytes a row at [vp_ps], CX = its rows:
; every ps-th pixel of every ps-th row, two to the byte. Preserves the rest
vp_v4dims:
    push dx
    push bx
    mov bx, [vp_ps]
    mov ax, [vp_wb]
    shl ax, 1
    shl ax, 1
    shl ax, 1                       ; the canvas's pixels
    xor dx, dx
    div bx
    inc ax
    shr ax, 1
    push ax
    mov ax, [vp_h]
    add ax, bx
    dec ax
    xor dx, dx
    div bx
    mov cx, ax
    pop ax
    pop bx
    pop dx
    ret

; vp_v4pack - the VGA4 canvas in [vp_kshd] (four bit-planes [vp_plsp]
; apart, row y at y x 80) as OSAPI_GFX_BLIT4's packed nibbles in [vp_pseg],
; the left pixel high, every [vp_ps]-th pixel of every [vp_ps]-th row -
; tools/os88vid.py's vga4_pack. Sets vp_pbw, vp_ppx, vp_prows. Preserves all
vp_v4pack:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    mov ax, [vp_kshd]
    mov bx, vp_mxseg
    mov cx, 4
.seg:
    mov [bx], ax
    add ax, [vp_plsp]
    inc bx
    inc bx
    loop .seg
    call vp_v4dims
    mov [vp_pbw], ax
    mov [vp_prows], cx
    mov ax, [vp_wb]
    shl ax, 1
    shl ax, 1
    shl ax, 1
    mov [vp_v4w], ax
    xor dx, dx
    div word [vp_ps]
    mov [vp_ppx], ax
    mov es, [vp_pseg]
    xor di, di
    xor si, si                      ; SI = the source row
.row:
    cmp si, [vp_h]
    jae .done
    mov ax, 80
    mul si
    mov bp, ax                      ; BP = the row in each plane
    mov word [vp_v4x], 0
    mov byte [vp_v4n], 0
    mov word [vp_v4xb], 0xFFFF
.pix:
    mov ax, [vp_v4x]
    cmp ax, [vp_v4w]
    jae .eol
    mov bx, ax
    shr bx, 1
    shr bx, 1
    shr bx, 1
    cmp bx, [vp_v4xb]
    je .have
    mov [vp_v4xb], bx               ; a new source byte: its four planes
    add bx, bp
    push es
    push si
    xor si, si
.ld:
    mov es, [vp_mxseg+si]
    mov al, [es:bx]
    shr si, 1
    mov [vp_v4c+si], al
    shl si, 1
    inc si
    inc si
    cmp si, 8
    jb .ld
    pop si
    pop es
.have:
    mov cl, [vp_v4x]
    and cl, 7
    xor ah, ah
    mov bx, 3                       ; plane 3 first, so AH = b3 b2 b1 b0
.bit:
    mov al, [vp_v4c+bx]
    shl al, cl
    shl al, 1                       ; CF = this pixel's bit
    rcl ah, 1
    dec bx
    jns .bit
    test byte [vp_v4n], 1
    jnz .lo
    mov cl, 4
    shl ah, cl
    mov [es:di], ah
    jmp short .nx
.lo:
    or [es:di], ah
    inc di
.nx:
    xor byte [vp_v4n], 1
    mov ax, [vp_ps]
    add [vp_v4x], ax
    jmp short .pix
.eol:
    test byte [vp_v4n], 1           ; a row ending on its high nibble
    jz .nr
    inc di
.nr:
    add si, [vp_ps]
    jmp .row
.done:
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vp_zero - ES:0: the file's layout's memory image, black
vp_zero:
    push ax
    push bx
    push cx
    push di
    cmp byte [vp_planar], 0         ; four planes, [vp_plsp] apart: past
    je .one                         ; one segment, so a plane at a time
    push es
    push dx
    mov dx, 4
.zp:
    xor ax, ax
    xor di, di
    mov cx, [vp_plsp]
    shl cx, 1
    shl cx, 1
    shl cx, 1                       ; paragraphs x 8 = words
    cld
    rep stosw
    mov ax, es
    add ax, [vp_plsp]
    mov es, ax
    dec dx
    jnz .zp
    pop dx
    pop es
    jmp short .out
.one:
    mov bl, [vp_layout]
    xor bh, bh
    mov ch, [vp_laykb+bx]           ; KB x 512 = words
    shl ch, 1
    xor cl, cl
    xor di, di
    xor ax, ax
    cld
    rep stosw
.out:
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
; THE PLAY IS A SESSION (SPEC.md 98.3, 98.3.7): the ring, the stream's
; cursors, the card and a copy of the canvas, which brackets come and go on.
; vp_play and vp_fsenter are the user's two ways in. A bracket ends by
; STOPPING the session, by SWAPPING between the window and the full screen,
; or by pausing back to the DESKTOP, where the session waits with its frame
; in the box until Play resumes it. Gfx lock held, SI = window, throughout
; =============================================================================
vp_play:                            ; Space, P, Enter, the Play button: play,
    push ax                         ; in the window if it can host it
    cmp byte [vp_ok], 1
    jne .out
    cmp byte [vp_sess], 0
    jne .resume
    mov byte [vp_startp], 0
    call vp_sstart
    jc .out
    jmp short .run
.resume:
    mov byte [vp_autop], 1          ; paused on the desktop: resumed as the
.run:                               ; bracket starts
    mov byte [vp_wantwin], 1
    call vp_srun
.out:
    pop ax
    ret

vp_fsenter:                         ; F, Alt+Enter: full screen, PAUSED -
    push ax                         ; played when Space says so (98.3.6)
    cmp byte [vp_ok], 1
    jne .out
    cmp byte [vp_sess], 0
    jne .run
    mov byte [vp_startp], 1
    call vp_sstart
    jc .out
.run:
    mov byte [vp_wantwin], 0
    call vp_srun
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; vp_sstart - a session, at the key picked: its claims, the reader and the
; hook's state, the clock. CF=1 it could not, [vp_msg] says why
; -----------------------------------------------------------------------------
vp_sstart:
    push bx
    push cx
    push dx
    push si
    push di
    push es
    ; --- the sound (SPEC.md 98.3.1): a card, audio in the file, and the ring
    ;     the card will read in place, page-safe and never moved (MC_DMA)
    mov byte [vp_snd], 0
    xor ax, ax
    mov [vp_aseg], ax
    mov [vp_keep], ax
    mov [vp_ring], ax
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
    ; --- THE CANVAS KEEPER (98.3.7): the file's own layout's memory image,
    ;     black. Where a bracket decodes through the SHADOW (98.3.2) it IS the
    ;     shadow, and so 64 KB whatever the layout - a list is not checked
    ;     entry by entry and its writes reach anywhere in ES (98.1.6), so the
    ;     claim is the bound. Where every bracket decodes onto the screen it is
    ;     only the image, read back from the screen as a bracket ends. Before
    ;     the ring, which takes what is left
    call vp_dinfo
    mov ax, 64
    cmp byte [vp_planar], 0         ; four planes' image (98.1.3.1)
    je .kx
    mov ax, [vp_plsp]               ; 4 x plsp paragraphs, in KB
    add ax, 15
    mov cl, 4
    shr ax, cl
    shl ax, 1
    shl ax, 1
    jmp short .kc
.kx:
    cmp byte [vp_fsshd], 0
    jne .kc
    mov bl, [vp_layout]
    cmp bl, [vp_dlay]
    jne .kc
    xor bh, bh
    mov al, [vp_laykb+bx]
    xor ah, ah
.kc:
    call OSAPI_MEM_CLAIM
    jnc .kok
    mov word [vp_msg], vp_s_mem
    jmp .fail
.kok:
    mov [vp_keep], dx
    cmp byte [vp_flip], 0           ; PAGE FLIPPING: the last record's copy
    je .nopv                        ; (98.3.8)
    mov ax, VP_PREVKB
    call OSAPI_MEM_CLAIM
    jnc .pv
    mov word [vp_msg], vp_s_mem
    jmp .fail
.pv:
    mov [vp_prevseg], dx
.nopv:
    mov [vp_shseg], dx
    mov es, dx
    call vp_zero
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
    jae .kok2
    mov word [vp_msg], vp_s_mem
    jmp .fail
.kok2:
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
    jmp .fail
.ring:
    mov [vp_ring], dx
    ; --- WHERE IT STARTS (98.3.5): the file's first super-packet, or the
    ;     picked keyframe's - its record read into the ring, to be decoded
    ;     once the surface is up and before the ring is filled over it
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
    jnz .kpick
    cmp byte [vp_pixfmt], PF_VGA8   ; key 0 too for colour: its frame 0 may
    jb .start                       ; be too big for one record, and the key
.kpick:                             ; is the whole picture
    cmp ax, [vp_kload]
    jne .start
    mov [vp_rdseg], dx
    mov ax, [vp_ke+KE_OFF]
    mov dx, [vp_ke+KE_OFF+2]
    mov cx, [vp_ke+KE_LEN]
    call vp_rdat
    jnc .kin
    mov word [vp_msg], vp_s_kbad
    jmp .fail
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
    mov [vp_gap], ax
    mov [vp_ready], al
    mov [vp_end], al
    mov [vp_eof], al
    mov [vp_err], al
    mov [vp_held], al
    mov [vp_upause], al
    mov [vp_sdefer], al
    mov [vp_autop], al
    mov [vp_stopq], al
    mov [vp_dtok], al
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
    mov [vp_pdiv], dx
    mov byte [vp_sess], 1
    mov byte [vp_sfirst], 1
    clc
    jmp short .out
.fail:
    call vp_sfree
    call vp_fmt
    call vp_repaint
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; vp_sfree - the session's claims, whichever it holds
vp_sfree:
    push dx
    mov dx, [vp_ring]
    call .f
    mov dx, [vp_keep]
    call .f
    mov dx, [vp_aseg]
    call .f
    mov dx, [vp_prevseg]
    call .f
    xor dx, dx
    mov [vp_prevseg], dx
    mov [vp_ring], dx
    mov [vp_keep], dx
    mov [vp_shseg], dx
    mov [vp_aseg], dx
    pop dx
    ret
.f:
    or dx, dx
    jz .n
    call OSAPI_MEM_FREE
.n:
    ret

; -----------------------------------------------------------------------------
; vp_srun - brackets on the session until it stops or goes back to the
; desktop. [vp_wantwin] asks for the window; the window is taken if it can
; host the play (vp_canwin) and the full screen otherwise
; -----------------------------------------------------------------------------
vp_srun:
    push ax
    push bx
    push cx
    push dx
    push di
.again:
    call vp_track
    mov byte [vp_winm], 0
    cmp byte [vp_wantwin], 0
    je .go
    call vp_canwin
    jc .go
    mov byte [vp_winm], 1           ; IN THE WINDOW: Play is Pause while it
    mov byte [vp_bpause], 1         ; plays, drawn before the bracket takes
    call vp_clip                    ; the screen
    call vp_buttons
    call vp_boxxy                   ; A DRAG moves the window's pixels by any
    mov ax, [vp_py]                 ; number of rows and the play puts the
    sub ax, [vp_cy0]                ; picture on a bank: where they differ,
    cmp ax, [vp_ppoff]              ; the box is painted again first, or
    je .go                          ; the rows between are left behind (the
    call vp_pposter                 ; owner's report)
.go:
    mov byte [vp_exitr], VPX_STOP
    mov bx, [vp_win]
    mov ax, vp_main
    mov cx, FSXF_RATE
    mov dx, [vp_pdiv]
    mov di, vp_hook
    call OSAPI_FSX_RUN
    jnc .ran
    mov word [vp_msg], vp_s_refused
    mov byte [vp_stopq], 2
    call vp_sstop
    jmp short .out
.ran:
    mov al, [vp_exitr]
    cmp al, VPX_SWAP
    je .swap
    cmp al, VPX_DESK
    je .out
    call vp_sstop                   ; STOPPED: over, and where it got to kept
    jmp short .out
.swap:
    cmp byte [vp_winm], 0
    je .tow
    mov byte [vp_wantwin], 0        ; the window -> the full screen, as it was
    jmp .again
.tow:                               ; the full screen -> the window: playing
    cmp byte [vp_autop], 0          ; on in it if it was playing and the
    je .out                         ; window can host it, else paused there
    mov byte [vp_wantwin], 1
    call vp_track
    call vp_canwin
    jnc .again
    mov byte [vp_autop], 0          ; (the pause the swap made is the user's
    call vp_fmt                     ; now: Play resumes it)
    call vp_repaint
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; vp_sstop - the session is over: the time it played, the card closed, its
; memory back, and - by [vp_stopq] - where the next play starts (vp_after):
; 0 kept, with its picture; 1 kept, the picture left to the caller; 2 not
; touched. Painted when 0
; -----------------------------------------------------------------------------
vp_sstop:
    push ax
    push bx
    cmp byte [vp_sess], 0
    je .out
    cmp byte [vp_dtok], 0           ; the time it played, if a bracket's end
    jne .tk                         ; did not take it already
    call vp_dtcalc
.tk:
    cmp byte [vp_sopn], 0           ; open, whether or not it is still the
    je .nc                          ; clock: verb 2, the card stops and lets
    mov al, 2                       ; go of the ring before it is freed
    mov ah, [vp_hand]
    call OSAPI_SND_STREAM
    mov byte [vp_sopn], 0
.nc:
    call vp_sfree
    xor al, al
    mov [vp_sess], al
    mov [vp_bpause], al
    mov [vp_upause], al
    mov [vp_ready], al
    cmp byte [vp_sfirst], 0         ; it never ran: no position, no costs
    jne .msg
    cmp word [vp_msg], vp_s_refused
    je .aft
    mov word [vp_msg], vp_s_ready
    cmp byte [vp_err], 0
    je .aft
    mov ax, [vp_errmsg]
    mov [vp_msg], ax
.aft:
    call vp_after                   ; WHERE THE PLAY GOT TO (98.3.6) - and
    mov byte [vp_played], 1         ; only then is it over, [vp_played] being
.msg:                               ; what a gate waits on
    cmp word [vp_msg], vp_s_ready   ; A PLAY THAT COULD NOT: the card comes
    je .fmt                         ; out, since it is what says why - on the
    cmp byte [vp_lcard], 0          ; wake, which lays the window out again
    jne .fmt
    mov byte [vp_card], 1
    mov byte [vp_relay], 1
    mov bx, [vp_win]
    call OSAPI_WM_WAKE
.fmt:
    call vp_fmt
    cmp byte [vp_stopq], 0
    jne .out
    call vp_repaint
.out:
    mov byte [vp_stopq], 0
    pop bx
    pop ax
    ret

; vp_stopfor - AL = vp_sstop's mode: the session over, if there is one, for
; something the user did in the window that it cannot outlive
vp_stopfor:
    cmp byte [vp_sess], 0
    je .out
    mov [vp_stopq], al
    call vp_sstop
.out:
    ret

; -----------------------------------------------------------------------------
; vp_canwin - CF=0 the window can host the play (98.3.7): the picture at the
; video's own size, the window uncovered, and the picture's rect whole on the
; screen. [vp_nowin] (a gate's) says no
; -----------------------------------------------------------------------------
vp_canwin:
    push ax
    push bx
    push cx
    push dx
    cmp byte [vp_nowin], 0
    jne .no
    cmp byte [vp_pixfmt], PF_VGA8   ; 256 colours: full screen only (98.3.7)
    je .no
    cmp word [vp_ps], 1
    jne .no
    mov bx, [vp_win]
    call OSAPI_WM_OBSCURED          ; covered, or hidden
    jc .no
    call vp_boxxy
    mov ax, [vp_pdw]                ; the whole width, on its byte
    cmp ax, [vp_lpw]
    jne .no
    call OSAPI_VIDEO                ; AX, BX = the screen
    mov cx, [vp_px]
    test cx, cx
    js .no
    add cx, [vp_lpw]
    cmp cx, ax
    ja .no
    mov dx, [vp_py]
    cmp dx, MBAR_H
    jl .no
    add dx, [vp_h]
    cmp dx, bx
    ja .no
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.no:
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; vp_dinfo - the desktop's framebuffer, as the decoder addresses it: its
; segment [vp_dseg] and its layout [vp_dlay] (98.1.2). The desktop IS one of
; the three: CGA's mode 6, the Hercules page, and mode 12h (or an EGA's 10h,
; the same linear image 350 rows deep), each at its adapter's segment
vp_dinfo:
    push ax
    push bx
    push cx
    push dx
    call OSAPI_VIDEO                ; DL = the adapter
    mov ax, 0xB800
    xor bl, bl
    cmp dl, VID_CGA
    je .s
    mov ax, 0xB000
    inc bl
    cmp dl, VID_HERC
    je .s
    mov ax, 0xA000
    inc bl
.s:
    mov [vp_dseg], ax
    mov [vp_dlay], bl
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vp_boxxy - where the picture goes in the box, on the screen: [vp_px] on a
; byte, [vp_py] on the desktop layout's bank (so the decoder's addresses
; land there unchanged, 98.1.2 - which is what the box's three rows of slack
; are for), [vp_pdw] the width the box shows. After vp_track. It asks the
; adapter itself: a box placed before the first play once rounded to the
; default layout's bank (CGA's two rows on a Hercules), and the play then
; drew up to three rows below the poster, leaving a bar (the owner's report)
vp_boxxy:
    push ax
    push bx
    push cx
    push dx
    call vp_dinfo
    mov ax, [vp_cx0]                ; the box's inside
    add ax, VP_BOXX
    mov [vp_bx1], ax
    add ax, [vp_lbw]
    dec ax
    mov [vp_bx2], ax
    mov ax, [vp_cy0]
    add ax, VP_BOXY
    mov [vp_by1], ax
    add ax, [vp_lbh]
    dec ax
    mov [vp_by2], ax
    mov ax, [vp_lbw]                ; x: centred, then up to the SCREEN's
    sub ax, [vp_lpw]                ; byte, so a window whose content is off
    shr ax, 1                       ; the grid loses up to 7 columns at the
    add ax, [vp_bx1]                ; right instead
    add ax, 7
    and ax, 0xFFF8
    mov [vp_px], ax
    mov cx, [vp_bx2]
    inc cx
    sub cx, ax
    cmp cx, [vp_lpw]
    jb .w
    mov cx, [vp_lpw]
.w:
    mov [vp_pdw], cx
    mov bl, [vp_dlay]               ; y: down to the next bank boundary
    xor bh, bh
    mov ax, bx
    shl bx, 1
    add bx, ax
    shl bx, 1
    mov cl, [vp_laytab+bx+1]        ; banks: 1, 2 or 4
    xor ch, ch
    dec cx
    mov ax, [vp_by1]
    add ax, cx
    not cx
    and ax, cx
    mov [vp_py], ax
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; vp_after - a play is over: Play starts next where this one got to (98.3.6).
; Stopped part way, that is the keyframe at or before the last frame drawn;
; played to the end, the start again, with the poster back in the box. A play
; that drew nothing past where it started leaves the key as it was
; -----------------------------------------------------------------------------
vp_after:
    push ax
    cmp byte [vp_stopq], 2          ; (the caller moves it itself)
    je .out
    cmp byte [vp_err], 0
    jne .out
    cmp word [vp_nkeys], 0
    je .out
    mov ax, [vp_done]
    cmp ax, [vp_frames]
    jb .mid
    mov word [vp_sel], 0            ; THE END: from the start, and the poster
    cmp byte [vp_stopq], 0
    jne .out
    mov ax, [vp_poster]
    cmp ax, [vp_nkeys]
    jae .out
    cmp ax, [vp_dkey]
    je .out
    call vp_loadkey
    jmp short .out
.mid:
    dec ax                          ; the last frame drawn
    js .out
    call vp_keyat                   ; AX = the key at or before it
    jc .out
    cmp byte [vp_stopq], 0          ; 1: the position alone - a step from it
    je .pic                         ; follows, and loads its own picture
    mov [vp_sel], ax
    jmp short .out
.pic:
    cmp ax, [vp_dkey]               ; THE BOX SHOWS WHERE PLAY STARTS NEXT: a
    jne .ld                         ; stop before the next key rounds back to
    cmp ax, [vp_kload]              ; the one it started from, and the box -
    je .sel                         ; the poster, or the paused frame - was
.ld:                                ; not that key's picture (the owner's
    call vp_loadkey                 ; field report)
    cmp ax, [vp_kload]              ; picked only if its entry is in hand,
    jne .out                        ; which is what a play from it needs
.sel:
    mov [vp_sel], ax
.out:
    pop ax
    ret

; vp_keyat - AX = a frame -> AX = the keyframe at or before it, CF=1 none
; could be read. The table is not in memory, so it is ESTIMATED - keys are
; evenly spaced, so frame x keys / frames is the one or its neighbour - and
; each guess read and stepped until it is right: one or two reads, and never
; more than a bounded number
vp_keyat:
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov [vp_kat_t], ax
    mul word [vp_nkeys]
    div word [vp_frames]            ; (t < frames, so the key < keys)
    mov [vp_kat_i], ax
    mov word [vp_kat_n], 24
    mov ax, [vp_kbkb]
    call OSAPI_MEM_CLAIM
    jc .fail
    mov [vp_rdseg], dx
.l:
    dec word [vp_kat_n]
    jz .got
    mov ax, [vp_kat_i]
    call vp_kent
    jc .bad
    mov ax, [vp_ke+KE_K]
    cmp ax, [vp_kat_t]
    jbe .up
    cmp word [vp_kat_i], 0          ; past it: the key before
    je .got
    dec word [vp_kat_i]
    jmp short .l
.up:
    mov ax, [vp_kat_i]              ; at or before it: is the next one too?
    inc ax
    cmp ax, [vp_nkeys]
    jae .got
    call vp_kent
    jc .bad
    mov ax, [vp_ke+KE_K]
    cmp ax, [vp_kat_t]
    ja .got
    inc word [vp_kat_i]
    jmp short .l
.got:
    mov dx, [vp_rdseg]
    call OSAPI_MEM_FREE
    mov ax, [vp_kat_i]
    clc
    jmp short .out
.bad:
    mov dx, [vp_rdseg]
    call OSAPI_MEM_FREE
.fail:
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; =============================================================================
; vp_main - a bracket on the session (SPEC.md 53.1, 98.3.7): SI = window,
; DS = CS = ours. The surface - the window's rect on the desktop as it
; stands (a same-mode bracket, §53.7), or the full screen in its mode - the
; canvas put back onto it, and the play from where the session is. It ends
; with [vp_exitr]: STOP, SWAP (F, Alt+Enter) or DESK (Space or a click, in
; the window: back to the desktop, paused)
; =============================================================================
vp_main:
    OS88_ALTENTER_SEED              ; the Alt+Enter that got us here is held
    cmp byte [vp_winm], 0
    je .fs
    call OSAPI_FSX_SURF             ; the display this bracket owns must be
    jc .fsw                         ; the primary, at (0,0): the decoder
    or ax, bx                       ; writes its framebuffer, and a window on
    jnz .fsw                        ; another card is not there (§53.7.1)
    call vp_wsurf
    jmp .surf
.fsw:
    mov byte [vp_winm], 0           ; ...else the full screen after all
.fs:
    mov al, [vp_fslay]              ; THE FULL SCREEN: the mode vp_canplay
    mov [vp_tlay], al               ; chose, native or through the shadow
    mov al, [vp_fsshd]
    mov [vp_shadow], al
    push ds
    pop es
    mov di, vp_fsi
    mov al, [vp_fsmode]
    call OSAPI_FSX_MODE
    jnc .mode
    mov byte [vp_err], 1
    mov word [vp_errmsg], vp_s_refused
    ret
.mode:
    mov ax, [vp_fsi+FSI_SEG]
    mov [vp_vseg], ax
    call vp_dac                     ; VGA8: the file's 256 colours
    call vp_crtc                    ; ...and each row twice, if it asks
    ; the origin: centred, the row on a bank (SPEC.md 98.1.2), on the
    ; screen's layout - the file's own, or the shadow's target (98.3.2)
    mov bl, [vp_tlay]
    xor bh, bh
    mov ax, bx
    shl bx, 1
    add bx, ax
    shl bx, 1
    mov ax, [vp_laytab+bx+4]        ; rows...
    mov cl, [vp_rs]                 ; ...which a row scale halves (98.2.4)
    shr ax, cl
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
    jne .surf
    cmp byte [vp_fsmode], FSXM_CGA640
    jne .surf
    call OSAPI_VIDEO                ; DL = the adapter: only a CGA has a
    cmp dl, VID_CGA                 ; composite output; an EGA's or a VGA's
    jne .surf                       ; mode 6 is RGB and 3D8h is not theirs
    mov dx, 0x3D8
    mov al, 0x1A                    ; 640x200 graphics, video on, burst ON
    out dx, al
    mov byte [vp_burst], 1
.surf:
    mov word [vp_fcap], 2           ; through the shadow the decode is cheap
    cmp byte [vp_shadow], 0         ; and the copy is not: more frames a call,
    je .fc                          ; one copy after them
    mov word [vp_fcap], 8
.fc:
    cmp byte [vp_flip], 0           ; FLIPPING: a frame a call, so a flip has
    je .fc1                         ; a period to latch before the next draw
    mov word [vp_fcap], 1           ; goes into the page it replaces
.fc1:
    mov word [vp_dy0], 0xFFFF
    mov word [vp_dy1], 0
    call OSAPI_MOUSE                ; the buttons as they are: a CLICK is a
    mov [vp_mbtn], al               ; press after this
    mov word [vp_wtk], 0xFFFF       ; the thumb: asked at the first frame
    xor ax, ax                      ; PAGES (98.3.8): page 0 on the glass,
    mov [vp_poff], ax               ; the other drawn next, and no record
    mov [vp_foff], ax               ; owed to it yet
    mov [vp_prevn], ax
    cmp byte [vp_flip], 0
    je .pg
    mov word [vp_poff], VP_PAGE
.pg:
    ; THE CANVAS onto this surface (98.3.7): where the session got to, black
    ; before its first frame
    call vp_kput
    cmp byte [vp_sfirst], 0
    jne .first
    cmp byte [vp_autop], 0          ; A LATER BRACKET: on from where it was,
    je .rdy                         ; playing again if the last one's end was
    mov byte [vp_autop], 0          ; what paused it
    call vp_upaus
.rdy:
    mov byte [vp_ready], 1
    jmp .loop
.first:
    mov byte [vp_sfirst], 0
    ; THE KEYFRAME (98.3.5): the screen after frame k, decoded onto the black
    ; - or into the shadow, and copied - before the ring is filled over its
    ; record
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
    call vp_decboth                 ; SI past its lists
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
    cmp byte [vp_startp], 0         ; F / Alt+Enter: IN PAUSED (98.3.6), on
    je .snd                         ; the picture where the play would start
    call vp_acur                    ; (the card, later, from HERE)
    cmp word [vp_krec], 0xFFFF      ; - the keyframe's, or else the first
    jne .held                       ; frame, drawn here with the hook idle
    mov al, [vp_snd]
    push ax
    mov byte [vp_snd], 0            ; (no card yet to keep it behind)
    call vp_frame
    pop ax
    mov [vp_snd], al
    cmp byte [vp_shadow], 0
    je .held
    call vp_blit
.held:
    mov byte [vp_upause], 1
    mov al, [vp_snd]                ; the card waits for the first Space
    mov [vp_sdefer], al
    call OSAPI_GET_TICKS
    mov [vp_t0], ax
    mov [vp_ptk0], ax
    mov byte [vp_ready], 1
    jmp short .loop
.snd:
    cmp byte [vp_snd], 0
    je .go
    call vp_acur
    call vp_sopen                   ; the card, started with the picture
.go:
    call OSAPI_GET_TICKS
    mov [vp_t0], ax
    mov byte [vp_ready], 1
.loop:
    call vp_poll                    ; AL = the way out, or 0
    or al, al
    jnz .leave
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
    call vp_wthumb                  ; (in the window, the thumb moves)
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
    call vp_poll                    ; any way out, now, is the end
    or al, al
    jnz .stop
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
.leave:
    mov [vp_exitr], al
    cmp al, VPX_STOP
    je .stop
    cmp byte [vp_upause], 0         ; SWAP or DESK: the session PAUSES - the
    jne .rb                         ; card halted where it is - and a swap's
    call vp_upaus                   ; pause is resumed by the next bracket,
    cmp byte [vp_exitr], VPX_DESK   ; where Space's or a click's is the
    je .rb                          ; user's own
    mov byte [vp_autop], 1
.rb:
    pushf
    cli
    mov byte [vp_ready], 0
    popf
    call vp_kget                    ; the canvas off the screen, for the next
    mov byte [vp_bpause], 0         ; surface and the box
    cmp byte [vp_exitr], VPX_DESK
    je .pic
    cmp byte [vp_winm], 0           ; the window -> the full screen: the
    jne .ret                        ; desktop between them is not the point
.pic:
    call vp_sesspic                 ; THE FRAME IN THE BOX, for the repaint
    call vp_fmt                     ; the bracket's exit makes (§53.6)
    ret
.stop:
    mov byte [vp_exitr], VPX_STOP
    pushf
    cli
    mov byte [vp_ready], 0
    popf
    call vp_dtcalc                  ; the time it played - NOW, and not after
.ret:                               ; the bracket's exit repaints the desktop
    ret

; vp_dtcalc - [vp_dt], the ticks the session PLAYED: since its first frame,
; less every pause - the one running now included
vp_dtcalc:
    push ax
    cmp byte [vp_upause], 0
    je .np
    call OSAPI_GET_TICKS
    sub ax, [vp_ptk0]
    add [vp_ptk], ax
    call OSAPI_GET_TICKS
    mov [vp_ptk0], ax
.np:
    call OSAPI_GET_TICKS
    sub ax, [vp_t0]
    sub ax, [vp_ptk]
    mov [vp_dt], ax
    mov byte [vp_dtok], 1
    pop ax
    ret

; vp_poll - the bracket's keys and, in the window, the mouse (SPEC.md 53.1:
; this IS the UI task, so it polls). out: AL = 0, or the way out - VPX_STOP
; for Esc, VPX_SWAP for F or Alt+Enter (off the key-state map, which int 16h
; never sees - apps/os88alt.inc), VPX_DESK for Space or a click in the
; window. Space in the full screen pauses and resumes in place
vp_poll:
    call os88alt_edge
    jc .swap
    cmp byte [vp_winm], 0
    je .key
    push cx
    push dx
    call OSAPI_MOUSE                ; AL = the buttons: a press is a click
    mov ah, [vp_mbtn]
    mov [vp_mbtn], al
    pop dx
    pop cx
    not ah
    and al, ah
    and al, 3
    jnz .desk
.key:
    mov ah, 1
    int 0x16
    jz .none
    xor ah, ah
    int 0x16
    cmp al, 27
    je .stop
    cmp al, ' '
    je .space
    or al, 0x20
    cmp al, 'f'
    je .swap
.none:
    xor al, al
    ret
.space:
    cmp byte [vp_winm], 0
    jne .desk
    call vp_upaus
    xor al, al
    ret
.stop:
    mov al, VPX_STOP
    ret
.swap:
    mov al, VPX_SWAP
    ret
.desk:
    mov al, VPX_DESK
    ret

; vp_wsurf - the window's rect as this bracket's surface: the desktop's own
; framebuffer and layout, the picture's place in the box as the origin
vp_wsurf:
    push ax
    push bx
    call vp_dinfo
    mov ax, [vp_dseg]
    mov [vp_vseg], ax
    mov al, [vp_dlay]
    mov [vp_tlay], al
    mov byte [vp_shadow], 0         ; the file's own layout: decoded onto the
    cmp al, [vp_layout]             ; desktop in place; another's: through the
    je .n                           ; shadow, and copied (98.3.2)
    mov byte [vp_shadow], 1
.n:
    call vp_track
    call vp_boxxy
    mov ax, [vp_py]
    mov [vp_ty0], ax
    mov ax, [vp_px]
    shr ax, 1
    shr ax, 1
    shr ax, 1
    mov [vp_tx0], ax
    mov ax, [vp_ty0]
    mov bl, [vp_tlay]
    call vp_rowaddr
    add ax, [vp_tx0]
    mov [vp_org], ax
    pop bx
    pop ax
    ret

; vp_kput / vp_kget - the canvas between the keeper and the surface (98.3.7).
; Through the shadow the keeper IS the shadow: put is a copy of all of it,
; get is nothing. Onto the screen in place, the canvas's rows at the origin
vp_kput:
    mov word [vp_kpo], 0
    cmp byte [vp_shadow], 0
    je .native
    mov word [vp_dy0], 0
    push ax
    mov ax, [vp_h]
    mov [vp_dy1], ax
    pop ax
    jmp vp_blit
.native:
    push ax
    xor al, al
    call vp_kmove
    cmp byte [vp_flip], 0           ; ...onto both pages when flipping
    je .one
    mov word [vp_kpo], VP_PAGE
    call vp_kmove
    mov word [vp_kpo], 0
.one:
    pop ax
    ret

vp_kget:
    cmp byte [vp_shadow], 0
    jne .out
    push ax
    mov ax, [vp_foff]               ; off the page on the glass
    mov [vp_kpo], ax
    mov al, 1
    call vp_kmove
    pop ax
.out:
    ret

vp_kmove:                           ; AL = 0 keeper -> screen, 1 screen -> keeper
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov [vp_kdir], al
    cld
    mov ax, [vp_keep]
    mov [vp_kseg], ax
    cmp byte [vp_planar], 0
    je .one
    xor cx, cx                      ; PLANES: one at a time, the Map Mask
.pl:                                ; for a put and the Read Map for a get,
    call vp_mxsel                   ; into the keeper's planes plsp apart
    push cx
    call .rows
    pop cx
    mov ax, [vp_plsp]
    add [vp_kseg], ax
    inc cx
    cmp cx, 4
    jb .pl
    call vp_mxall
    jmp short .d
.one:
    call .rows
    jmp short .d
.rows:
    xor dx, dx                      ; DX = the row
.r:
    cmp dx, [vp_h]
    jae .rd
    mov ax, dx
    mov bl, [vp_layout]
    call vp_rowaddr                 ; AX = the row, in the keeper
    mov si, ax
    mov di, ax
    add di, [vp_org]                ; ...and on the screen, on the page it
    add di, [vp_kpo]                ; is moved to or from (98.3.8)
    mov cx, [vp_wb]
    mov ax, [vp_kseg]
    mov bx, [vp_vseg]
    cmp byte [vp_kdir], 0
    jne .get
    mov es, bx
    push ds
    mov ds, ax
    rep movsb
    pop ds
    jmp short .n
.get:
    xchg si, di
    mov es, ax
    push ds
    mov ds, bx
    rep movsb
    pop ds
.n:
    inc dx
    jmp short .r
.rd:
    ret
.d:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; vp_mxsel - CL = a MODEX plane: the Map Mask (writes) and the Read Map
; (reads) both on it. vp_mxall - writes to all four again, which is what the
; decoder's 0Fh sub-records and the mode set assume. Preserve all
vp_mxsel:
    push ax
    push dx
    mov ah, 1
    shl ah, cl
    mov al, 2
    mov dx, 0x3C4
    out dx, ax
    mov ah, cl
    mov al, 4
    mov dx, 0x3CE
    out dx, ax
    pop dx
    pop ax
    ret
vp_mxall:
    push ax
    push dx
    mov ax, 0x0F02
    mov dx, 0x3C4
    out dx, ax
    pop dx
    pop ax
    ret

; vp_wthumb - in the window, the thumb follows the play (98.3.7): when its
; offset moves, the old 8 x 8 block is made white and the new one black,
; written into the desktop's framebuffer here - the kernel's drawing is not
; the bracket's to use - so a move is sixteen rows of two bytes, not a bar.
; On a VGA desktop the stores go through the Graphics Controller's Bit Mask
; with interrupts off, so the hook's decode always finds the planes at rest
vp_wthumb:
    cmp byte [vp_winm], 0
    je .out
    push ax
    mov ax, [vp_done]               ; nothing to ask until a frame is drawn
    cmp ax, [vp_wtk]
    je .p
    mov [vp_wtk], ax
    call vp_thumbx
    cmp ax, [vp_wtx]
    je .p
    push bx
    push cx
    push dx
    mov bx, [vp_wtx]
    mov [vp_wtx], ax
    mov cx, bx
    add cx, [vp_tx1]
    mov dl, 1                       ; where it was: white
    call vp_wbox
    mov cx, ax
    add cx, [vp_tx1]
    xor dl, dl                      ; where it is: black
    call vp_wbox
    pop dx
    pop cx
    pop bx
.p:
    pop ax
.out:
    ret

; vp_wbox - the thumb's block at screen x CX, the bar's inside rows, in DL's
; colour (1 white, 0 black), on the desktop's framebuffer ([vp_dseg], laid
; out as [vp_dlay]). A 1 bpp desktop takes an OR or an AND; mode 12h a store
; through the Bit Mask after a read loads the latches, so the four planes
; move together and no pixel outside the block changes. Preserves all
vp_wbox:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    pushf
    cli
    mov es, [vp_dseg]
    mov bp, cx
    shr bp, 1
    shr bp, 1
    shr bp, 1                       ; BP = the block's first byte
    mov al, 0xFF
    and cl, 7
    shr al, cl                      ; AL = its bits in that byte...
    mov ah, al
    not ah                          ; ...AH = in the next (0: on a byte)
    mov [vp_wbm], ax
    mov si, [vp_cy0]
    add si, [vp_lbary]
    inc si                          ; SI = the first row inside the bar
    mov cx, VP_BARH - 2
.row:
    mov ax, si
    mov bl, [vp_dlay]
    call vp_rowaddr
    add ax, bp
    mov di, ax
    mov al, [vp_wbm]
    call .put
    mov al, [vp_wbm+1]
    or al, al
    jz .nx
    inc di
    call .put
.nx:
    inc si
    loop .row
    cmp byte [vp_dlay], 2           ; mode 12h: every bit writable again
    jne .d
    mov dx, 0x3CE
    mov ax, 0xFF08
    out dx, ax
.d:
    popf
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.put:                               ; AL = the bits at ES:DI, DL the colour
    cmp byte [vp_dlay], 2
    je .vga
    or dl, dl
    jz .blk
    or [es:di], al
    ret
.blk:
    not al
    and [es:di], al
    ret
.vga:
    push dx
    mov ah, al
    mov al, 8                       ; the Bit Mask
    mov dx, 0x3CE
    out dx, ax
    pop dx
    mov al, [es:di]                 ; the latches, all four planes
    xor al, al
    or dl, dl
    jz .v0
    dec al
.v0:
    mov [es:di], al
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
    mov ax, [vp_abase]              ; the audio cursor is vp_acur's, at the
    mov [vp_afr], ax                ; frame the clock reads until the card's
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
; vp_acur - the audio cursor where the video's is now - past a keyframe's
; skip - and [vp_abase] the frame it is at. Before vp_sopen; and, going in
; paused (98.3.6), before the first frame is drawn, so the card starts on
; that frame's sound while that frame is on the screen
vp_acur:
    push cx
    push si
    push di
    push es
    push ds
    pop es
    mov si, vp_pc
    mov di, va_pc
    mov cx, 6
    cld
    rep movsw
    mov cx, [vp_done]
    mov [vp_abase], cx
    pop es
    pop di
    pop si
    pop cx
    ret

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
    cmp byte [vp_sdefer], 0         ; in paused (98.3.6): the card starts now,
    je .v1                          ; at the frame the picture holds
    mov byte [vp_sdefer], 0
    call vp_sopen
    jmp short .go
.v1:
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
    add ax, [vp_abase]              ; ...from the frame the card started at
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
    cmp byte [vp_flip], 0
    jne .flip
    call vp_decrec
    inc word [vp_done]
    clc
    ret
.flip:
    call vp_flipdec
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

; vp_flipdec - DX:SI = a record, played with PAGE FLIPPING (98.3.8): the
; back page holds the frame before last, so the last record is decoded into
; it again and then this one, which brings it to this frame; this record is
; kept for the other page's turn; and the CRTC is pointed at the page - it
; latches the start address at the next retrace, so nothing waits, and the
; next draw, a frame period later, is into the page that was showing.
; clobbers AX, BX, CX, DX, SI, DI, BP, ES
vp_flipdec:
    push dx
    push si
    cmp word [vp_prevn], 0
    je .cur
    mov dx, [vp_prevseg]
    xor si, si
    call vp_decrec
.cur:
    pop si
    pop dx
    push dx
    push si
    call vp_decrec
    pop si
    pop dx
    push ds                         ; the record, for the other page
    mov es, [vp_prevseg]
    xor di, di
    mov ds, dx
    mov cx, [si]
    mov bx, cx
    cld
    shr cx, 1
    rep movsw
    adc cx, cx
    rep movsb
    pop ds
    mov [vp_prevn], bx
    mov ax, [vp_poff]               ; show it...
    call vp_show
    mov [vp_foff], ax
    xor word [vp_poff], VP_PAGE     ; ...and draw the other next
    ret

; vp_show - AX = a page's offset: the CRTC's start address (3D4h 0Ch/0Dh),
; in Mode X's bytes. Latched at the next retrace. Preserves all
vp_show:
    push ax
    push bx
    push dx
    mov bx, ax
    mov dx, 0x3D4
    mov al, 0x0C
    mov ah, bh
    out dx, ax
    mov al, 0x0D
    mov ah, bl
    out dx, ax
    pop dx
    pop bx
    pop ax
    ret

; vp_decboth - DX:SI = a record decoded into BOTH pages when flipping (a
; keyframe: the stream after it takes either), else as vp_decrec. SI past
; its lists, as vp_decrec leaves it
vp_decboth:
    cmp byte [vp_flip], 0
    je vp_decrec
    push dx
    push si
    mov word [vp_poff], 0
    call vp_decrec
    pop si
    pop dx
    mov word [vp_poff], VP_PAGE
    call vp_decrec
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
    add bp, [vp_poff]               ; the page being drawn (98.3.8), or 0
.go2:
    add si, 6
    push ds
    mov ds, dx
    cmp byte [cs:vp_planar], 0
    jne .mx
    call vd_native                  ; the lists, onto the adapter
    pop ds
    ret
.mx:                                ; MODEX (98.1.3.1): each sub-record's Map
    lodsb                           ; Mask, then its lists - four pixels a
    or al, al                       ; store under 0Fh, a plane's under the
    jz .mxd                         ; rest
    mov ah, al
    mov al, 2
    mov dx, 0x3C4
    out dx, ax
    push bp
    call vd_native
    pop bp
    jmp short .mx
.mxd:
    mov ax, 0x0F02                  ; all four planes again: the desktop's
    mov dx, 0x3C4                   ; own drawing, and a one-bit file's
    out dx, ax                      ; decode, assume it (98.1.3.2)
    pop ds
    ret

; vp_decram - DS:SI = a record's lists, ES = a RAM image at its address 0:
; decoded there, BP = 0. A MODEX image is four planes VP_MXPL paragraphs
; apart, and a sub-record is decoded into every plane its mask names.
; clobbers AX, BX, CX, DX, SI, DI, BP
vp_decram:
    xor bp, bp
    cmp byte [cs:vp_planar], 0
    jne .mx
    jmp vd_native
.mx:
    push es
    mov bx, es
.sub:
    lodsb
    or al, al
    jz .done
    mov ah, al                      ; AH = the mask, shifted as it is spent
    mov dx, bx                      ; DX = plane 0's image
    mov cx, 4
    mov di, si                      ; the lists, decoded again per plane
.p:
    shr ah, 1
    jnc .np
    push ax
    push bx
    push cx
    push dx
    push di
    mov es, dx
    mov si, di
    xor bp, bp
    call vd_native                  ; SI past them, the last time counting
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
.np:
    add dx, [cs:vp_plsp]
    loop .p
    jmp short .sub
.done:
    pop es
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
    add ax, 6 + 10                  ; the header and ten lists' ends - or
    cmp byte [vp_planar], 0         ; a planar record's one 0 after its
    je .rmin                        ; sub-records (98.1.3.1): an empty
    sub ax, 9                       ; frame is seven bytes
.rmin:
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

; =============================================================================
; THE LAYOUT (SPEC.md 98.4.1). The picture at the video's own size if the
; screen has the room, else a half, else a quarter; the scrub bar under it;
; the transport buttons centred under THAT with the info card's button at the
; right - or, where there is room for the picture and the bar but not for a
; row of buttons as well, the buttons in the info card instead, which is then
; always shown. The info card beside the picture when it is asked for, and
; its room is taken from the picture's scale if it must be. The window may
; reach down over the dock (CGA's desktop band is too short otherwise)
; =============================================================================
; vp_layfit - the layout for [vp_wb] x [vp_h] and [vp_card] on this screen,
; into the vp_l* words. out: AX = 1 the picture's scale changed. Preserves
; the rest
vp_layfit:
    push bx
    push cx
    push dx
    push si
    push di
    call OSAPI_VIDEO                ; AX = width, BX = height
    sub ax, 10                      ; the widest content: frame x 7, 1 border
    mov [vp_lcwm], ax
    sub bx, MBAR_H + TITLE_H + 1    ; the tallest, over the dock
    mov [vp_lchm], bx
    mov ax, [vp_ps]
    mov [vp_lops], ax
    mov si, 1                       ; SI = the scale tried: 1, 2, 4
.s:
    call vp_laysize                 ; the picture's size at SI -> vp_lpw/lph
    mov cl, [vp_card]
    call vp_layA
    jnc .a
    call vp_layB
    jnc .b
    shl si, 1
    cmp si, 4
    jbe .s
    mov si, 4                       ; nothing fits: a quarter, buttons below
    call vp_laysize
    mov cl, [vp_card]
    call vp_layA
.a:
    mov byte [vp_lbin], 0
    jmp short .set
.b:
    mov byte [vp_lbin], 1
.set:
    mov [vp_ps], si
    mov bx, [vp_lpw]                ; the box: the picture's width, and never
    cmp bx, VP_MINBW                ; less than the button row wants
    jae .bw
    mov bx, VP_MINBW
.bw:
    mov [vp_lbw], bx
    mov ax, [vp_lph]
    add ax, VP_BSLACK               ; the picture's row goes down to a bank
    mov [vp_lbh], ax
    add ax, VP_BOXY + 6
    mov [vp_lbary], ax              ; the bar's frame, under the box
    add ax, VP_BARH + 6
    mov [vp_lbty], ax               ; the button row, under the bar
    mov ax, bx                      ; the card: past the box, on a byte
    add ax, VP_BOXX + 8 + 7
    and ax, 0xFFF8
    mov [vp_lcardx], ax
    mov ax, [vp_ps]
    xor ax, [vp_lops]
    jz .same
    mov ax, 1
.same:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; vp_laysize - SI = a scale: vp_lpw, vp_lph = the picture's size at it
vp_laysize:
    push ax
    push cx
    mov ax, [vp_pwb]                ; pixels: 8 a byte, over the scale
    mov cl, 3
    shl ax, cl
    mov cx, si
.w:
    shr cx, 1
    jz .wd
    shr ax, 1
    jmp short .w
.wd:
    mov [vp_lpw], ax
    mov ax, [vp_ph]                 ; rows: halved rounding UP, as vp_half
    mov cx, si                      ; does
.h:
    shr cx, 1
    jz .hd
    inc ax
    shr ax, 1
    jmp short .h
.hd:
    mov [vp_lph], ax
    pop cx
    pop ax
    ret

; vp_layA - buttons under the bar, the card if CL says so: CF=0 it fits, the
; content size in vp_lcw/vp_lch and [vp_lcard] set
vp_layA:
    push ax
    push bx
    mov [vp_lcard], cl
    call vp_laybw                   ; AX = the box's width
    add ax, VP_BOXX + 8             ; the content without the card
    or cl, cl
    jz .w
    add ax, 7                       ; ...or with it, past the box on a byte
    and ax, 0xFFF8
    add ax, VP_CARDW + 4
.w:
    cmp ax, [vp_lcwm]
    ja .no
    mov [vp_lcw], ax
    mov ax, [vp_lph]
    add ax, VP_BSLACK + VP_BOXY + 6 + VP_BARH + 6 + VP_BTH + 5
    mov bx, VP_CARDH                ; the card's own height, when it is shown
    or cl, cl
    jz .h
    cmp ax, bx
    jae .h
    mov ax, bx
.h:
    cmp ax, [vp_lchm]
    ja .no
    mov [vp_lch], ax
    pop bx
    pop ax
    clc
    ret
.no:
    pop bx
    pop ax
    stc
    ret

; vp_layB - the buttons in the card, which is then shown: CF=0 it fits
vp_layB:
    push ax
    mov byte [vp_lcard], 1
    call vp_laybw
    add ax, VP_BOXX + 8 + 7
    and ax, 0xFFF8
    add ax, VP_CARDW + 4
    cmp ax, [vp_lcwm]
    ja .no
    mov [vp_lcw], ax
    mov ax, [vp_lph]
    add ax, VP_BSLACK + VP_BOXY + 6 + VP_BARH + 5
    cmp ax, VP_CARDHB
    jae .h
    mov ax, VP_CARDHB
.h:
    cmp ax, [vp_lchm]
    ja .no
    mov [vp_lch], ax
    pop ax
    clc
    ret
.no:
    pop ax
    stc
    ret

vp_laybw:                           ; AX = the box's width at vp_lpw
    mov ax, [vp_lpw]
    cmp ax, VP_MINBW
    jae .o
    mov ax, VP_MINBW
.o:
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
    mov di, vp_brects
    cmp byte [vp_lbin], 0
    jne .incard
    mov bx, [vp_lbw]                ; UNDER THE BAR: the four centred on the
    sub bx, VP_NB * VP_BTP - (VP_BTP - VP_BTW)  ; box, the card's at its
    shr bx, 1                       ; right edge
    add ax, bx
    add ax, VP_BOXX
    add dx, [vp_lbty]
    jmp short .row
.incard:
    add ax, [vp_lcardx]             ; IN THE CARD, under its text
    add dx, VP_CARDBY
.row:
    mov cx, VP_NB
.r:
    call vp_rect
    add ax, VP_BTP
    loop .r
    mov ax, VP_NB                   ; ...and the fifth, the card's, only
    cmp byte [vp_lbin], 0           ; under the bar
    jne .n
    mov ax, [vp_cx0]
    add ax, VP_BOXX
    add ax, [vp_lbw]
    sub ax, VP_BTW
    call vp_rect
    mov ax, VP_NB + 1
.n:
    cmp byte [vp_abon], 0           ; none live under the About card
    je .live
    xor ax, ax
.live:
    mov [vp_btns + OS88UI_BT_N], ax
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

vp_rect:                            ; AX, DX = a button's top left -> [DI], DI += 8
    mov [di], ax
    mov [di+2], dx
    push ax
    add ax, VP_BTW - 1
    mov [di+4], ax
    mov ax, dx
    add ax, VP_BTH - 1
    mov [di+6], ax
    pop ax
    add di, 8
    ret

; vp_buttons - every button, in the state it should be in now. Lock held
vp_buttons:
    push ax
    push bx
    cmp byte [vp_abon], 0
    jne .out
    mov ax, vp_i_play               ; PLAY IS PAUSE while it plays in the
    cmp byte [vp_bpause], 0         ; window (98.3.7)
    je .pl
    mov ax, vp_i_pause
.pl:
    mov [vp_blabels+4], ax
    mov ax, OS88UI_IMG              ; Open is always live; the key buttons
    mov [vp_bflags], ax             ; stop at the ends, and Play needs a file
    mov [vp_bflags+2], ax           ; that plays here
    mov [vp_bflags+4], ax
    mov [vp_bflags+6], ax
    cmp byte [vp_lcard], 0          ; the card's button stands DOWN while the
    je .c                           ; card is out (OS88UI_LATCH)
    or ax, OS88UI_LATCH
.c:
    mov [vp_bflags+8], ax
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
    cmp al, [vp_btns + OS88UI_BT_N]
    ja .out
    call os88ui_btn
    inc al
    jmp short .b
.out:
    pop bx
    pop ax
    ret

; vp_ptext - the info card's lines from BX on, each an opaque run the full
; width, so nothing is erased first (PERFORMANCE.md rule 2). Nothing while
; the card is in
vp_ptext:
    push ax
    push bx
    push cx
    push dx
    push si
    cmp byte [vp_lcard], 0
    je .out
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
    add cx, [vp_lcardx]
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

; vp_pposter - the box and the picture in it (98.4): the picture where there
; is one, black round it, each pixel written once
vp_pposter:
    push ax
    push bx
    push cx
    push dx
    push si
    push bp
    push es
    call vp_boxxy                   ; the box, and the picture's place in it
    mov ax, [vp_py]                 ; where it is drawn, from the content's
    sub ax, [vp_cy0]                ; origin: a drag moves the pixels by any
    mov [vp_ppoff], ax              ; number of rows, and the play looks
    cmp word [vp_pseg], 0
    je .black
    mov ax, [vp_by2]                ; rows past the box - a picture made at
    sub ax, [vp_py]                 ; another scale, between a relayout and
    inc ax                          ; its reload - are not drawn
    cmp ax, [vp_prows]
    jbe .r
    mov ax, [vp_prows]
.r:
    mov [vp_pdh], ax
    ; THE FRAME HUGS THE PICTURE (98.3.7): its row is on a bank, so up to
    ; three of the box's rows are spare, above it and below. Inside the
    ; frame they read as black bars round a picture that has none (the
    ; owner's report), so they go OUTSIDE it, in the window's ground
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov ax, [vp_bx1]                ; above the frame
    dec ax
    mov bx, [vp_by1]
    dec bx
    mov cx, [vp_bx2]
    inc cx
    mov dx, [vp_py]
    sub dx, 2
    call vp_fillne
    mov bx, [vp_py]                 ; below it
    add bx, [vp_pdh]
    inc bx
    mov dx, [vp_by2]
    inc dx
    call vp_fillne
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, [vp_bx1]                ; the frame, on the picture's rows
    dec ax
    mov bx, [vp_py]
    dec bx
    mov cx, [vp_bx2]
    inc cx
    mov dx, [vp_py]
    add dx, [vp_pdh]
    call OSAPI_GFX_FRAME
    mov bx, [vp_py]                 ; left of it
    mov dx, bx
    add dx, [vp_pdh]
    dec dx
    mov cx, [vp_px]
    dec cx
    call vp_fillne
    mov ax, [vp_px]                 ; right of it
    add ax, [vp_pdw]
    mov cx, [vp_bx2]
    call vp_fillne
    mov es, [vp_pseg]
    xor si, si
    mov bp, [vp_pbw]
    mov ax, [vp_px]
    mov cx, [vp_pdw]
    mov bx, [vp_py]
    mov dx, [vp_pdh]
    cmp byte [vp_pixfmt], PF_VGA4   ; 16 colours, as they are (98.4.5)
    jne .b1
    call OSAPI_GFX_BLIT4
    jmp .out
.b1:
    call vp_blitb
    jnc .out
    mov ax, [vp_px]                 ; refused: black where it would be
    mov bx, [vp_py]
    mov cx, ax
    add cx, [vp_pdw]
    dec cx
    mov dx, bx
    add dx, [vp_pdh]
    dec dx
    call vp_fillne
    jmp short .out
.black:
    mov al, CBLACK                  ; no picture: the box, framed, black
    call OSAPI_SET_COLOR
    mov ax, [vp_bx1]
    dec ax
    mov bx, [vp_by1]
    dec bx
    mov cx, [vp_bx2]
    inc cx
    mov dx, [vp_by2]
    inc dx
    call OSAPI_GFX_FRAME
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

; vp_blitb - OSAPI_GFX_BLIT1's arguments, any number of rows: it takes 255
; at a time. CF = 1 a call refused. Preserves all
vp_blitb:
    push ax
    push bx
    push dx
    push si
    mov [vp_brem], dx
.l:
    mov dx, [vp_brem]
    or dx, dx
    jz .out                         ; (CF = 0 from the or)
    cmp dx, 255
    jbe .n
    mov dx, 255
.n:
    sub [vp_brem], dx
    call OSAPI_GFX_BLIT1
    jc .out
    add bx, dx                      ; the next band: its rows down the screen,
    push ax                         ; its bytes along the picture
    push dx
    mov ax, dx
    mul bp
    add si, ax
    pop dx
    pop ax
    jmp short .l
.out:
    pop si
    pop dx
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
; starts - or, mid-drag, under the pointer - three fills and no pixel twice;
; grey with no keyframes to pick
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
    add bx, [vp_lbary]
    mov cx, ax
    add cx, [vp_lbw]
    inc cx
    mov dx, bx
    add dx, VP_BARH - 1
    call OSAPI_GFX_FRAME
    inc ax                          ; the inside
    mov [vp_tx1], ax
    inc bx
    dec cx
    mov [vp_tx2], cx
    dec dx
    cmp word [vp_nkeys], 0
    jne .live
    call OSAPI_GFX_FILL_GRAY
    jmp short .out
.live:
    call vp_thumbx                  ; AX = the thumb's x in the bar
    mov [vp_wtx], ax
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
    mov cx, [vp_tx2]
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

; vp_thumbx - AX = the thumb's offset along the bar: under the pointer while
; it is dragged, else where the play starts, along the file's frames
vp_thumbx:
    push cx
    push dx
    mov ax, [vp_tpos]
    cmp byte [vp_drag], 0
    jne .out
    cmp byte [vp_sess], 0           ; a session: where it has got to
    je .key
    mov ax, [vp_done]
    or ax, ax
    jz .at
    dec ax
    jmp short .at
.key:
    xor ax, ax
    cmp word [vp_sel], 0
    je .out
    mov ax, [vp_ke+KE_K]
.at:
    mov cx, [vp_lbw]
    sub cx, VP_THW
    mul cx
    div word [vp_frames]
.out:
    pop dx
    pop cx
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
    mov ax, [vp_pwb]                ; the pixels, whatever a byte holds
    mov cl, 3
    shl ax, cl
    xor dx, dx
    xor bl, bl
    call vp_putn
    mov al, 'x'
    call vp_putc
    mov ax, [vp_ph]
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
    ; 4: where Play starts - or, a session waiting, where it is paused
    mov di, vp_lines + 4 * VP_LINE
    cmp byte [vp_sess], 0
    je .nos
    mov si, vp_s_pausedat
    call vp_puts
    mov ax, [vp_done]
    or ax, ax
    jz .pz
    dec ax
.pz:
    call vp_putt
    jmp .msg
.nos:
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
    dw 7, 22, 0, 0                  ; W_X = 7 mod 8: the content on a byte
                                    ; (SPEC.md 11.94). The size: vp_entry's,
                                    ; from the layout (98.4.1)
    dw vp_cap, vp_paint, vp_onkey, vp_clickw

    OS88_MENUSET vp_menus, vp_ttl, vp_oncmd
        OS88_MENU vp_m_file, vp_i_file, 6
    OS88_MENUSET_END vp_menus
vp_ttl:       db 'Video Player', 0
vp_pfx1:      db 'Video Player - ', 0
vp_pfx2:      db 'Video - ', 0
vp_cap:       db 'Video Player', 0  ; the window's caption (98.4.3): the
              times 15 + VP_COLS + 1 - 13 db 0  ; longest is pfx1 + a title
vp_m_file:    db 'File', 0
vp_i_file:    dw vp_it_open, vp_it_play, vp_it_fs, vp_it_prev, vp_it_next
              dw vp_it_info
vp_it_open:   db 'Open...', 0
vp_it_play:   db 'Play (Space)', 0
vp_it_fs:     db 'Full screen (F)', 0
vp_it_prev:   db 'Previous key (Left)', 0
vp_it_next:   db 'Next key (Right)', 0
vp_it_info:   db 'Info (I)', 0

; the buttons (SPEC.md 20.5.1.3): Tracker's transport pictures, 16 x 10
    OS88UI_BTNREC vp_btns, vp_brects, vp_blabels, vp_bflags, VP_NB
vp_blabels:   dw vp_i_open, vp_i_prev, vp_i_play, vp_i_next, vp_i_info
vp_bflags:    times VP_NBTN dw OS88UI_IMG
vp_brects:    times VP_NBTN * 4 dw 0
vp_i_pause:                         ; ||
    db 1, 10
    times 10 dw 0FFFFh
    times 10 dw 00E70h
vp_i_info:                          ; an i: the info card
    db 1, 10
    times 10 dw 0FFFFh
    dw 00180h, 00180h, 00000h, 00380h, 00180h
    dw 00180h, 00180h, 00180h, 003C0h, 00000h
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
    db FSXM_VGA13, 1
    dw 320, 200
    db FSXM_MODEX, 1
    dw 80, 240
vp_laynames:  dw vp_s_cga, vp_s_herc, vp_s_vga, vp_s_vga8, vp_s_modex
vp_laynotab:  dw vp_s_nocga, vp_s_noherc, vp_s_novga, vp_s_novga8
              dw vp_s_novga8
vp_laycptab:  dw vp_s_cpcga, vp_s_cpherc, vp_s_cpvga, vp_s_novga8
              dw vp_s_novga8
vp_laykb:     db 16, 32, 38, 63, 75     ; each layout's memory image, KB
vp_bayer4:    db 0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5
vp_rthr:      db 0, 0, 0, 0             ; vp_v8mono: this row's four
vp_mxseg:     dw 0, 0, 0, 0             ; ...and a planar image's four planes
vp_v4c:       db 0, 0, 0, 0             ; vp_v4pack: a source byte's planes,
vp_v4x:       dw 0                      ; the pixel, the canvas's width,
vp_v4w:       dw 0
vp_v4xb:      dw 0                      ; the byte cached, and which nibble
vp_v4n:       db 0
vp_planar:    db 0                      ; 1 Mode X's planes, 2 VGA4's bits
vp_plsp:      dw 0                      ; ...and a RAM image's spacing, paras
vp_kseg:      dw 0                      ; vp_kmove: the keeper's plane
vp_s_cga:     db 'CGA  ', 0
vp_s_herc:    db 'Herc  ', 0
vp_s_vga:     db 'VGA  ', 0
vp_s_vga8:    db 'VGA 256  ', 0
vp_s_modex:   db 'Mode X  ', 0

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
vp_s_novga8:  db '256 colours: a VGA, full screen', 0
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
vp_s_pausedat: db 'Paused at ', 0
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
vp_pwb:       dw 0                  ; the Preview's bytes a row (98.4)...
vp_ph:        dw 0                  ; ...and its rows: the canvas's, shown
vp_rs:        db 0                  ; ...this many times over, as a shift
vp_flip:      db 0                  ; Mode X page flipping (98.3.8)...
vp_poff:      dw 0                  ; ...the page being drawn...
vp_foff:      dw 0                  ; ...the one on the glass...
vp_kpo:       dw 0                  ; ...the one vp_kmove uses...
vp_prevseg:   dw 0                  ; ...and the last record's copy, its
vp_prevn:     dw 0                  ; bytes (0: none owed)
vp_palo:      dd 0                  ; VGA8: the palette's offset
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
vp_ppoff:     dw 0                  ; the poster's row less the content's,
                                    ; as last painted
vp_py:        dw 0                  ; reads the screen there)
vp_ploads:    dw 0                  ; posters made: the gate waits on it
vp_bx1:       dw 0                  ; the box's inside, screen
vp_by1:       dw 0
vp_bx2:       dw 0
vp_by2:       dw 0
vp_tx1:       dw 0                  ; the bar's inside, and the thumb
vp_tx2:       dw 0
vp_tx:        dw 0
vp_pdh:       dw 0                  ; the picture's rows drawn
vp_brem:      dw 0                  ; vp_blitb's rows left
vp_dkey:      dw 0xFFFF             ; the key the picture is, FFFFh none
vp_pscale:    dw 0                  ; ...and the scale it was made at
; the layout (98.4.1), vp_layfit's
vp_card:      db 0                  ; the user's: the info card out
vp_lcard:     db 0                  ; ...and whether it is (layout B forces it)
vp_lbin:      db 0                  ; 1: the buttons are in the card
vp_relay:     db 0                  ; the wake owes a layout and a resize
vp_ps:        dw 2                  ; the picture's scale: 1, 2 or 4
vp_lops:      dw 0
vp_lpw:       dw 0                  ; the picture at it, pixels and rows
vp_lph:       dw 0
vp_lbw:       dw 0                  ; the box: its width and height
vp_lbh:       dw 0
vp_lbary:     dw 0                  ; the bar's frame top, the button row's
vp_lbty:      dw 0
vp_lcardx:    dw 0                  ; the card's x
vp_lcw:       dw 0                  ; the content's size
vp_lch:       dw 0
vp_lcwm:      dw 0                  ; ...and the most the screen allows
vp_lchm:      dw 0
; the thumb's drag (98.4.2)
vp_drag:      db 0
vp_tier:      db 0                  ; OSAPI_CPU_INFO's AL
vp_tpos:      dw 0                  ; the thumb's offset along the bar
vp_dtk:       dw 0                  ; the tick the last mid-drag load ended
vp_kat_t:     dw 0                  ; vp_keyat's frame and key
vp_kat_i:     dw 0
vp_kat_n:     dw 0
; the paused start and the play's end (98.3.4, 98.3.6)
vp_startp:    db 0                  ; F: into full screen paused
vp_sdefer:    db 0                  ; ...the card started at the first Space
vp_ranok:     db 0                  ; the bracket ran: the position to keep
              db 0
vp_abase:     dw 0                  ; the frame the card's stream starts at
; the session (98.3.7)
vp_sess:      db 0                  ; a play is alive, brackets or none
vp_autop:     db 0                  ; paused by a bracket's end, not the user:
                                    ; the next bracket resumes it
vp_sfirst:    db 0                  ; ...and the next bracket is its first
vp_winm:      db 0                  ; this bracket is in the window
vp_wantwin:   db 0                  ; ...and the next one asks for it
vp_exitr:     db 0                  ; VPX_*: how the bracket ended
vp_stopq:     db 0                  ; vp_sstop's mode
vp_bpause:    db 0                  ; the Play button shows Pause
vp_mbtn:      db 0                  ; the mouse's buttons, last seen
vp_fslay:     db 0                  ; the full screen's layout, mode, and
vp_fsmode:    db 0                  ; whether through the shadow
vp_fsshd:     db 0
vp_dlay:      db 0                  ; the desktop's layout (vp_dinfo)
vp_kdir:      db 0
vp_dtok:      db 0                  ; [vp_dt] is taken
vp_nowin:     db 0                  ; 1: never in the window (a gate's)
vp_dseg:      dw 0                  ; the desktop's framebuffer
vp_keep:      dw 0                  ; the canvas keeper (the shadow, or not)
vp_pdiv:      dw 0                  ; this play's PIT divisor
vp_wtk:       dw 0                  ; the frame the thumb was last asked at
vp_wtx:       dw 0                  ; ...and where it was drawn
vp_wbm:       dw 0                  ; vp_wbox: the block's two byte masks
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

%include "os88alt.inc"              ; Alt+Enter in the bracket (SPEC.md 11.2.1.1)
%define OS88UI_ABOUT                ; the standard About card (SPEC.md 20.5.1)
%define OS88UI_BIMG                 ; ...and buttons with PICTURES, drawn with
%define OS88UI_NOGLYPH              ; no pixel written twice (SPEC.md 13.8.9),
%include "os88ui.inc"               ; and no check box or radio at all

; --- bss: zeroed by the loader, and no bytes of the file ----------------------
vp_dtab       equ os88_image_end    ; the half-scaler's two tables (vp_mkdtab)
vp_lines      equ vp_dtab + 512     ; the info panel's text
vp_pal        equ vp_lines + VP_LINES * VP_LINE ; VGA8's palette (98.1.1)
vp_lum        equ vp_pal + 768      ; ...and each entry's luma, 0..16
    OS88_BSS 512 + VP_LINES * VP_LINE + 768 + 256
    OS88_IMAGE_END
