; =============================================================================
; apps/bonanza/bzmenu.inc - BONANZA's WINDOW (SPEC.md 137.26), resident: the
; Play Game button, the Game and Saves menus, the window's keys, the replays in
; SYSTEM\APPDATA, and suspending the bracket for the window and resuming it.
; The face's pictures are the shell part's (bzwface.inc); the button's record
; and its gesture are data the library writes, so they live here.
; =============================================================================

BZ_BW       equ 96              ; the Play Game button: its width ...
BZ_BH_S     equ 14              ; ...its height, SHORT (a 640 x 200 desktop) ...
BZ_BH_T     equ 20              ; ...and TALL
BZ_BY_S     equ 17              ; ...its top below the ledge picture's, SHORT and
BZ_BY_T     equ 38              ; TALL: centred on the ledge's top face (the owner's
                                ; mock-up, 2026-11-16), left of the ledge
BZ_SU_PATH  equ 1               ; [bz_susp]: the window was asked for from the
BZ_SU_CRS   equ 2               ; pathway, or from inside a course (137.26.4)
BZ_KSC_F5   equ 3fh             ; F5 and F6's make codes (137.26.3)
BZ_KSC_F6   equ 40h

; the window's size on VGA / Hercules / CGA: FIXED (the art does not scale,
; SPEC.md 137.26.1)
    OS88_PREFER bz_sizes, 440, 260,  440, 230,  440, 128

    OS88UI_BTNREC bz_btrec, bz_btr, bz_btlab, bz_btfl, 1, bz_bplace
bz_btlab:   dw bz_s_play
bz_s_play:  db 'Play Game', 0

; --- the menus (SPEC.md 137.26.3).  Every item's first byte is its MARK: ' ',
; or '*' when chosen; a greyed item is pointed at the MENU_DIS byte before it.
    OS88_MENUSET bz_menus, bz_title, bz_oncmd
        OS88_MENU bz_m_game, bz_mi_game, 7
        OS88_MENU bz_m_saves, bz_mi_saves, 7
    OS88_MENUSET_END bz_menus
bz_m_game:  db 'Game', 0
bz_m_saves: db 'Saves', 0
bz_mi_game: dw bz_i_play, bz_i_rsave, bz_i_rload, bz_i_sep
            dw bz_i_expl, bz_i_mouse, bz_i_snd
bz_mi_saves: dw bz_i_ld1, bz_i_ld2, bz_i_ld3, bz_i_sep
            dw bz_i_er1, bz_i_er2, bz_i_er3
            db MENU_DIS
bz_i_play:  db '  Play Game', 0
            db MENU_DIS
bz_i_rsave: db '  Save Replay      F5', 0
bz_i_rload: db '  Load Replay...   F6', 0
bz_i_sep:   db MENU_DIS, '-------------------', 0
bz_i_expl:  db '  Explore', 0
bz_i_mouse: db '  Use Mouse', 0
bz_i_snd:   db '  Sound', 0
bz_i_ld1:   db '  Load Slot 1', 0
bz_i_ld2:   db '  Load Slot 2', 0
bz_i_ld3:   db '  Load Slot 3', 0
bz_i_er1:   db '  Erase Slot 1', 0, 0  ; (a byte for the `?` an armed erase shows)
bz_i_er2:   db '  Erase Slot 2', 0, 0
bz_i_er3:   db '  Erase Slot 3', 0, 0
BZ_I_LDB    equ bz_i_ld2 - bz_i_ld1     ; the slots' items' strides
BZ_I_ERB    equ bz_i_er2 - bz_i_er1
BZ_I_ERQ    equ bz_i_er2 - bz_i_er1 - 2 ; ...and where the `?` goes
%if bz_i_ld3 - bz_i_ld2 != BZ_I_LDB || bz_i_er3 - bz_i_er2 != BZ_I_ERB
 %error "the slots' items are one stride apart"
%endif

; bz_mlabels - every item's mark and grey from the state.  Preserves all but
; AX, BX, SI.
bz_mlabels:
    mov si, bz_i_play           ; Play Game: greyed with the button
    call bz_canplay
    jnc .p
    dec si
.p:
    mov [bz_mi_game], si
    mov si, bz_i_rsave          ; Save Replay: a log the player recorded
    cmp byte [bz_rown], 0
    jne .s
    dec si
.s:
    mov [bz_mi_game + 2], si
    call bz_dslot               ; Explore: the slot's mode
    mov al, [si + 1]
    and al, 1
    mov bx, bz_i_expl
    call .mark
    mov al, [bz_ctl]            ; Use Mouse
    mov bx, bz_i_mouse
    call .mark
    mov al, [bzs_mode]          ; Sound: on unless OFF
    cmp al, BZS_M_OFF
    mov al, 0
    je .so
    inc ax
.so:
    mov bx, bz_i_snd
    call .mark
    mov bx, bz_i_ld1            ; the slots
    xor ah, ah
.sl:
    xor al, al
    cmp ah, [bz_slot]
    jne .sm
    inc ax
.sm:
    call .mark
    add bx, BZ_I_LDB
    inc ah
    cmp ah, BZD_NSLOT
    jb .sl
    mov bx, bz_i_er1 + BZ_I_ERQ ; the erases: `?` on the armed one
    mov ah, 1
.se:
    xor al, al
    cmp ah, [bz_earm]
    jne .sq
    mov al, '?'
.sq:
    mov [bx], al
    add bx, BZ_I_ERB
    inc ah
    cmp ah, BZD_NSLOT
    jbe .se
    ret
.mark:                          ; AL nonzero: BX's mark '*', else ' '
    or al, al
    mov al, ' '
    jz .m
    mov al, '*'
.m:
    mov [bx], al
    ret

; bz_canplay - CF = 1 when Play Game cannot run here: kern_small, or a display
; the bracket cannot drive (SPEC.md 137.1).  Preserves all but the flags.
bz_canplay:
    cmp byte [bz_small], 0
    stc
    jne .out
    push ax
    call bz_adapter
    cmp al, 1                   ; (0: none - CF)
    pop ax
.out:
    ret

; bz_bplace - OS88UI_BT_PLACE (SPEC.md 20.5.1.3.5): the button's rect from the
; content box, before every press and at every paint; and the aspect the face
; draws in, [bz_wtall], and whether there is a button, [bz_wbn].  Preserves
; every register.
bz_bplace:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov bx, [bz_win]
    call OSAPI_WM_DISPLAY       ; BX = the display's height
    cmp bx, 300
    cmc
    sbb al, al
    and al, 1
    mov [bz_wtall], al
    xor ax, ax                  ; the button: none under the instruments' face
%ifdef BZDEV
    cmp byte [bz_dev], 0
    jne .n
%endif
    inc ax
.n:
    mov [bz_wbn], ax
    mov [bz_btrec + OS88UI_BT_N], ax
    mov ax, OS88UI_DIS          ; ...greyed when it cannot run
    call bz_canplay
    jc .f
    xor ax, ax
.f:
    mov [bz_btfl], ax
    mov bx, [bz_win]            ; THE PLACE (SPEC.md 137.26.1): centred in the
    call OSAPI_WM_GEOM          ; space left of the ledge, its middle on the
    push cx                     ; ledge's top face - the ledge's own place is
    push dx                     ; bzwface.inc's, worked the same way
    call OSAPI_WM_CONTENT       ; AX, DX = the content's origin
    pop bx                      ; BX = its height
    pop cx                      ; CX = its width
    mov si, BZW_LEDGE_S_H + BZW_LBOT_S - BZ_BY_S
    mov di, BZ_BH_S
    cmp byte [bz_wtall], 0
    je .s
    mov si, BZW_LEDGE_T_H + BZW_LBOT_T - BZ_BY_T
    mov di, BZ_BH_T
.s:
    add dx, bx
    sub dx, si                  ; DX = y1: the ledge picture's top + BZ_BY
    mov [bz_btr + 2], dx
    add dx, di
    dec dx
    mov [bz_btr + 6], dx        ; y2
    sub cx, BZW_LEDGE_S_W       ; CX = the ledge's left, content-relative (as
    add cx, ax                  ; the face rounds it: up to a screen byte)
    add cx, 7
    and cx, 0fff8h
    sub cx, ax
    sub cx, BZ_BW
    sar cx, 1
    jns .x
    xor cx, cx
.x:
    add cx, ax
    mov [bz_btr], cx            ; x1
    add cx, BZ_BW - 1
    mov [bz_btr + 4], cx        ; x2
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; the button's release and drag (SPEC.md 13.7, 13.8): its press is the library's
bz_onup:
    SAVE
    mov bx, bz_btrec
    call os88ui_btnup           ; AX = what fired, 0 cancelled
    or ax, ax
    jz .out
    call bz_playgame
.out:
    jmp bz_rret
bz_ondrag:
    push ax
    push bx
    mov bx, bz_btrec
    call os88ui_btndrag
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; bz_oncmd - AM_ONCMD (SPEC.md 12.2): AL = the item, AH = the menu.  An armed
; erase holds only to the next pick.
; -----------------------------------------------------------------------------
bz_oncmd:
    cmp byte [bz_abon], 0       ; (a pick takes the About card down)
    je .c
    mov byte [bz_abon], 0
    push ax
    call bz_repaint
    pop ax
.c:
    xor cx, cx
    xchg cl, [bz_earm]          ; CL = the slot armed, 1 - 3 (0 none)
    or ah, ah
    jnz .saves
    cmp al, 7
    jae .out
    xor ah, ah
    mov bx, ax
    shl bx, 1
    jmp [bz_gcmds + bx]
.snd:
    call bzs_toggle             ; Sound
    jmp short .lab
.mouse:
    call bz_unsuscrs            ; (a play's input is its log's: a course held
    xor byte [bz_ctl], 1        ; is given up first)
    jmp short .lab
.expl:
    call bz_unsusp
    call bz_dslot
    xor byte [si + 1], 1
    jmp short .slotw
.saves:
    cmp al, 3
    jb .load
    je .out
    sub al, 3                   ; ERASE slot AL (1 - 3): armed, then erased
    cmp al, cl
    je .erase
    mov [bz_earm], al
    jmp short .lab
.erase:
    call bz_unsusp
    dec ax
    mov ah, [bz_slot]
    push ax
    mov [bz_slot], al
    call bz_dslot
    pop ax
    mov [bz_slot], ah
    mov di, si
    push es
    push ds
    pop es
    mov cx, BZD_SLOTB / 2
    xor ax, ax
    rep stosw
    pop es
    jmp short .slotw
.load:
    cmp al, [bz_slot]
    je .lab
    call bz_unsusp
    mov [bz_slot], al
    jmp short .lab
.slotw:
    mov byte [bz_gsave], 1      ; the slot to BONANZA.DAT (the merge keeps the
    call bz_home                ; others; at home, as every file is)
    jc .lab
    call bz_dsave
    call bz_back
.lab:
    call bz_mlabels
.out:
    ret
bz_gcmds:   dw bz_playgame, bz_rsavedk, bz_rloaddlg, bz_oncmd.out
            dw bz_oncmd.expl, bz_oncmd.mouse, bz_oncmd.snd

; bz_playgame - Play Game (the button, the menu, Enter, F, Alt+Enter): where
; the player left the bracket for the window, else the title (SPEC.md
; 137.26.4).  bz_title8 makes the refusals and runs the bracket.
bz_playgame:
    call bz_title8
    jmp bz_mlabels

; bz_unsusp - a suspended bracket given up (SPEC.md 137.26.3, 137.26.4): a
; course's parts back, its game read again from the slot (where its life is
; written already).  bz_unsuscrs only when a COURSE is held.  Preserves all.
bz_unsuscrs:
    cmp byte [bz_susp], BZ_SU_CRS
    je bz_unsusp
    ret
bz_unsusp:
    cmp byte [bz_susp], 0
    je .r
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    cmp byte [bz_susp], BZ_SU_CRS
    jne .p
    call bz_cdrop
    call bzs_gdrop0
    call bz_phfree
    mov byte [bz_tgame], 0      ; (the slot on the disk is the game)
    mov byte [bz_xmode], 0
    mov byte [bz_lfx], 0        ; (a life the play gave is the disk's no more, 137.55)
.p:
    mov byte [bz_susp], 0
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
.r:
    ret

; -----------------------------------------------------------------------------
; THE REPLAYS (SPEC.md 137.26.3): SYSTEM\APPDATA\NNNCOURS.BZR
; -----------------------------------------------------------------------------
; bz_rscan - in APPDATA (od_enter done), course AL's saves: AX = the greatest
; number (0 none), and that file's name in [bz_dname] and its size in DX:CX
; when there is one.  The name's tail is the course's NAME cut to five and its
; extension BZR.  Clobbers BX, SI, DI.
bz_rscan:
    mov ah, BZ_CRS_NAMEB        ; [bz_rtail] = the NAME cut to five, `.BZR`
    mul ah
    add ax, bz_cnames
    xchg ax, si
    mov di, bz_rtail
    mov cx, 5
.t:
    lodsb
    or al, al
    jz .te
    mov [di], al
    inc di
    loop .t
.te:
    mov word [di], '.B'
    mov word [di + 2], 'ZR'
    mov byte [di + 4], 0
    mov word [bz_rbest], 0
    xor cx, cx
.f:
    push es
    push ds
    pop es
    mov di, od_find
    call OSAPI_FILE_FIND
    pop es
    jc .done
    push cx
    mov si, od_find             ; NNN, then the tail exactly
    xor bx, bx
    mov cx, 3
.d:
    lodsb
    sub al, '0'
    cmp al, 9
    ja .no
    xchg ax, bx
    mov ah, 10
    mul ah
    add al, bl
    adc ah, 0
    xchg ax, bx                 ; (BH kept 0 by the 3 digits: under 1,000)
    loop .d
    mov di, bz_rtail
.c:
    lodsb
    cmp al, [di]
    jne .no
    inc di
    or al, al
    jnz .c
    cmp bx, [bz_rbest]
    jbe .no
    mov [bz_rbest], bx
    mov si, od_find             ; the newest so far: its name and size
    mov di, bz_dname
    mov cx, 13
.cp:
    lodsb
    mov [di], al
    inc di
    loop .cp
    mov ax, [od_find + 18]
    mov [bz_rbsz], ax
    mov ax, [od_find + 20]
    mov [bz_rbsz + 2], ax
.no:
    pop cx
    jmp short .f
.done:
    mov ax, [bz_rbest]
    mov cx, [bz_rbsz]
    mov dx, [bz_rbsz + 2]
    ret

; bz_rsave - the held log, recorded by a play, to APPDATA as the course's next
; number (137.26.3).  CF = 1 refused, SI = why (a TOASTSTR; the bracket's
; cards say their own); else [bz_dname] the name written.  Preserves nothing.
bz_rsave:
    mov si, bz_t_nolog
    cmp byte [bz_rown], 0
    stc
    je .out
    call bz_rhave
    stc
    jne .out
    call od_enter
    mov si, bz_t_noad
    jc .out
    mov al, [bz_rlog + BZR_CRS]
    call bz_rscan
    inc ax
    mov si, bz_t_rfull
    cmp ax, 1000
    cmc
    jc .back
    mov di, bz_dname            ; NNN
    mov cl, 100
    div cl
    add al, '0'
    mov [di], al
    mov al, ah
    aam
    add ax, '00'
    mov [di + 1], ah
    mov [di + 2], al
    add di, 3
    mov si, bz_rtail
.n:
    lodsb
    mov [di], al
    inc di
    or al, al
    jnz .n
    push es
    call bz_rout                ; ES:BX, CX = the log, one piece (137.11.12.1)
    mov si, bz_dname
    xor dx, dx
    call OSAPI_FILE_WRITE
    pop es
    mov si, bz_t_rfail
.back:
    call od_back                ; (flags kept)
.out:
    ret

; Save Replay and F5 on the window: written, and a toast either way
bz_rsavedk:
    call bz_bigok
    jc .out
    call bz_rsave
    jc .t
    mov si, bz_t_rsaved
.t:
    call bz_toast
.out:
    ret

; Load Replay... and F6 on the window: the Open dialog, IN APPDATA (the
; instance is left standing there: the dialog lists where it stands, and the
; next dialog opens in the folder last used); the pick is replayed at once
bz_rloaddlg:
    call bz_bigok
    jc .out
    call od_enter               ; (no APPDATA: the dialog where we are)
    mov al, FDLG_OPEN
    xor si, si
    mov di, bz_rldone
    mov bx, [bz_win]
    call OSAPI_FILE_DLG
.out:
    ret
; ...its completion: L's checks (bz_ldone), then the replay, full screen
bz_rldone:
    mov byte [bz_lsv], 0
    call bz_ldone
    cmp byte [bz_lsv], 2        ; (bz_lfile's mark: it was read and checked)
    jne .out
    call bz_rhave
    jne .out
    mov ah, [bz_rlog + BZR_CRS]
    mov al, 2
    call bz_go
    call bz_mlabels
.out:
    ret

TOASTSTR bz_t_nolog, 'No replay to save'
TOASTSTR bz_t_noad, 'No APPDATA folder'
TOASTSTR bz_t_rfull, 'Replays full'
TOASTSTR bz_t_rfail, 'Replay not saved'
TOASTSTR bz_t_rsaved, 'Replay saved'

; -----------------------------------------------------------------------------
; THE PATHWAY's F5, F6 and V (SPEC.md 137.26.3), from bz_grounds once the
; pathway's play has ended with [bz_pwq] 'r', 'l' or 'v'.  The cards say what
; happened; nothing here toasts (the bracket's framebuffer is ours).
; -----------------------------------------------------------------------------
; bz_gfsave - F5: the held log saved, and a card saying so
bz_gfsave:
    call bz_rsave
    mov si, bz_kc_saved
    jnc .ok
    mov si, bz_kc_nosv
    call bz_card
    jmp bz_kwait
.ok:
    push es                     ; REPLAY SAVED / the name
    push ds
    pop es
    mov di, bz_kbuf
    call bz_kput
    stosb
    mov si, bz_dname
    call bz_kput
    stosb
    stosb
    pop es
    mov si, bz_kbuf
    call bz_card
    jmp bz_kwait

; bz_gfload - F6 (AL 'l') or V (AL 'v'): course [bz_pwck]'s newest save, or its
; shipped demo, into the session's log.  CF = 1 none (its card shown).
bz_gfload:
    mov bl, [bz_pwck]
    cmp bl, BZ_CRS_MAX
    jae .none
    cmp al, 'v'
    jne .f6
    mov al, bl                  ; V: the course's shipped demo, its row found
    xor bx, bx                  ; in bz_dcrs (137.14.7.4: by the table, never
.dr:                            ; by K - 1)
    cmp al, [bz_dcrs + bx]
    je .dg
    inc bx                      ; (every row: one past the list's demos
    cmp bl, BZ_CRS_MAX          ; names course 0FFh, no K)
    jb .dr
    jmp short .none
.dg:
    lea ax, [bx + BZ_P_DEMO]
    call bz_tlog
    jc .none
    mov byte [bz_rown], 0
    clc
    ret
.f6:
    call od_enter
    jc .none
    mov al, [bz_pwck]
    call bz_rscan
    or ax, ax
    jz .nob
    or dx, dx
    jnz .nob
    cmp cx, BZR_RUNS
    jb .nob
    cmp cx, BZR_SIZE
    ja .nob
    xor al, al
    call bz_lfile               ; (its refusals say nothing in the bracket: bz_toast)
    jc .nob
    call od_back
    mov byte [bz_rown], 0
    clc
    ret
.nob:
    call od_back
.none:
    mov si, bz_kc_none
    call bz_card
    call bz_kwait
    stc
    ret

bz_kc_saved: db 'REPLAY SAVED', 0
bz_kc_nosv:  db 'REPLAY NOT SAVED', 0, 'ANY KEY', 0, 0
bz_kc_none:  db 'NO REPLAY HERE', 0, 'ANY KEY', 0, 0
