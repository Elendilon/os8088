;;; =============================================================================
;;; apps/bonanza/bzface.inc - BONANZA's desktop FACE, assembled into the SHELL
;;; PART (apps/bonanza/bzshell.asm, SPEC.md 130.19.2) - never into the package.
;;; Moved out of bonanza.asm by wave 8a whole; what changed is only where its
;;; tables are read: the part's own through CS (`[cs:...]`, bz_lcat), the
;;; package's bss through DS, as every vector is entered with DS = the package.
;;; =============================================================================

bz_face:
    call bz_fgeom
    jc .out
    cmp byte [bz_page], 0
    jne .res
    xor ax, ax                  ; MAIN: lines 0 - 6, each by its builder
.main:
    push ax
    call bz_fline
    pop ax
    inc ax
    cmp al, BZ_NLINE
    jb .main
    jmp short .tail
.res:                           ; RESULTS (after B, until the next key)
    mov word [bz_fy], 0
    call bz_l0                  ; lines 0 and 1 as MAIN's
    call bz_l1
    call bz_adname              ; line 2: `CGA frames <n>  <r> Hz  misses <n>`
    mov si, bx
    call bz_lstr
    call bz_frline
    call bz_line
    call bz_lmeas               ; line 3: what was measured
    call bz_facres              ; lines 4 - 11: the worst frame, the parts'
    mov si, bz_s_back           ; means, the writers' counts; line 12
    call bz_lline
.tail:
    ; the strip under the last line, to the content's foot
    mov bx, [bz_fy]
    mov dx, [bz_fh]
    dec dx
    cmp dx, bx
    jl .right
    call bz_fillrows
.right:
    ; the columns right of the last whole cell (a content width that is not
    ; a multiple of 8), over the lines' height only: the strips above own
    ; the full width already
    mov ax, [bz_fcells]
    mov cl, 3
    shl ax, cl
    cmp ax, [bz_fw]
    jae .out
    mov cx, [bz_fw]
    dec cx
    xor bx, bx
    mov dx, [bz_fh]
    dec dx
    call bz_fillrect
.out:
    ret

; the face's geometry: [bz_fw], [bz_fh], [bz_ox], [bz_oy], [bz_fcells].  CF = 1
; when the window has none.  Clobbers AX, BX, CX, DX.
bz_fgeom:
    mov bx, [bz_win]
    call OSAPI_WM_GEOM
    jc .out
    mov [bz_fw], cx
    mov [bz_fh], dx
    call OSAPI_WM_CONTENT
    mov [bz_ox], ax
    mov [bz_oy], dx
    mov ax, [bz_fw]
    mov cl, 3
    shr ax, cl
    cmp ax, BZ_LMAX
    jbe .cells
    mov ax, BZ_LMAX
.cells:
    mov [bz_fcells], ax
    clc
.out:
    ret

; the window's clip armed and the face's geometry read: CF = 1 when either
; cannot be had - or when this key LEAVES the RESULTS page ([bz_pgo]), whose
; whole MAIN face bz_onkey paints after it, so no line is drawn twice.
; Clobbers AX, BX, CX, DX.
bz_fclip:
    cmp byte [bz_pgo], 0
    stc
    jne .out
    mov bx, [bz_win]
    call OSAPI_WM_CLIP_SET
    jc .out
    call bz_fgeom
.out:
    ret

; MAIN's line AL (0 - 6) drawn at its place.  Preserves nothing.
bz_fline:
    xor ah, ah
    mov bx, ax
    mov ah, BZ_LH
    mul ah
    mov [bz_fy], ax
    shl bx, 1
    jmp [cs:bz_ftab + bx]
bz_ftab:    dw bz_ltour, bz_l1, bz_l2, bz_l3, bz_l4, bz_l5, bz_l6
%if ($ - bz_ftab) / 2 != BZ_NLINE
 %error "MAIN is the tour's line and six more - no scorecard, whatever the tour (SPEC.md 130.26.8)"
%endif

; MAIN's lines in the 0FFh-ended list at SI, redrawn outside a paint (the clip
; armed first, SPEC.md 11.3); AL = one line, for bz_redraw1.  Preserves nothing.
bz_redraw:
    call bz_fclip
    jc .out
.l:
    lodsb
    cmp al, 0ffh
    je .out
    push si
    call bz_fline
    pop si
    jmp .l
.out:
    ret

; ---- MAIN's builders: each draws its line at [bz_fy] and steps it -------------
; RESULTS's line 0: the title (MAIN's line 0 is the tour's since SPEC.md 130.16.8)
bz_l0:
    mov si, bz_s_title
; SI's string as a whole line
bz_lline:
    call bz_lstr
    jmp bz_line

; line 1: what Enter does.  `ENTER PLAY  F <title>  N NEXT` (wave 8b, 130.19.5:
; Enter the game, F a free play of the selected course); in a tour `ENTER
; next  ESC stop tour`
bz_l1:
    mov si, bz_s_tkeys
    call bz_intour
    jc bz_lline
    mov si, bz_s_keys           ; wave 8c (130.19.8.3): `ENTER SLOT n  LIVES l
    call bz_lstr                ; TIMED|EXPLORE  F <NAME>` - the game's slot,
    mov al, [bz_slot]           ; its lives (`-` none) and mode, then F's free
    add al, '1'                 ; play of the selected course
    call bz_lch
    mov si, bz_s_lv
    call bz_lcat
    mov al, [bz_slot]
    mov ah, BZD_SLOTB
    mul ah
    mov bx, ax
    mov al, [bz_dat + BZD_SLOT + bx]
    or al, al
    mov ah, '-'
    jz .lv
    add al, '0'
    mov ah, al
.lv:
    mov al, ah
    call bz_lch
    mov si, bz_s_timed
    test byte [bz_dat + BZD_SLOT + 1 + bx], 1
    jz .md
    mov si, bz_s_expl
.md:
    call bz_lcat
    mov si, bz_s_fk
    call bz_lcat
    mov al, [bz_crsel]
    call bz_lname
    jmp bz_line

; line 2: the adapter, or why there is none, or why the last launch was
; refused (bz_err 1 the mode, 2 the display changed under the key)
bz_l2:
    call bz_adname
    mov al, [bz_err]
    mov bx, bz_s_err
    cmp al, 1
    je .err
    mov bx, bz_s_err2
    cmp al, 2
    jne bz_lline
.err:
    mov si, bx
    jmp bz_lline

; the adapter's names: SI = line 2's (`Adapter: ...`, or why there is none),
; BX = the results' prefix (`CGA frames `).  Clobbers AX.
bz_adname:
    mov si, bz_s_small
    cmp byte [bz_small], 0
    jne .none
    call bz_adapter
    mov si, bz_s_cga
    mov bx, bz_s_cgar
    cmp al, 1
    je .out
    mov si, bz_s_herc
    mov bx, bz_s_hercr
    cmp al, 2
    je .out
    mov si, bz_s_vga
    mov bx, bz_s_vgar
    cmp al, 3
    je .out
    mov si, bz_s_noad
.none:
    mov bx, si
.out:
    ret

; line 3: the settings and their keys, `M <ball>  T <control>`; a tour
; rolls each course's own ball, so M is not offered in one
bz_l3:
    call bz_intour              ; (no C since the camera became LATTICE alone,
    mov si, bz_s_ctlk + 2       ; and the VGA's own: the line starts at M, or
    jc .l                       ; in a tour at T)
    mov si, bz_s_ballk + 2
    call bz_lstr
    mov bl, [bz_matsel]
    xor bh, bh
    shl bx, 1
    mov si, [cs:bz_s_mats + bx]
    call bz_lcat
    mov si, bz_s_ctlk           ; T: KEYS or MOUSE (SPEC.md 130.14.8)
    call bz_lcat
    jmp short .k
.l:
    call bz_lstr
.k:
    mov si, bz_s_keyb
    cmp byte [bz_ctl], 0
    je .c
    mov si, bz_s_mouse
.c:
    call bz_lcat
    jmp bz_line

; line 4: `S <the sound>` - the player's choice and, under AUTO, the arm it
; found (SPEC.md 130.20.4).  S redraws it (bzs_skey, bz_line4).
bz_l4:
    mov si, bz_s_sndk
    call bz_lstr
    mov bl, [bzs_mode]
    xor bh, bh
    shl bx, 1
    mov si, [cs:bz_s_smodes + bx]
    call bz_lcat
    cmp byte [bzs_mode], BZS_M_SPK
    jae .l
    mov si, bz_s_sfm
    cmp byte [bzs_arm], BZS_A_FM
    je .a
    mov si, bz_s_sspk
.a:
    call bz_lcat
.l:
    jmp bz_line

; line 5: the demo keys (SPEC.md 130.14.3.2): `B BENCH  L LOAD  V DEMO`, and
; with a log held `R PLAY  D TIME  W SAVE  L LOAD  V DEMO` - B, the engine
; benchmark, is the key dropped for the 42 cells (130.14.17 item 2), and still
; works; a tour offers `W SAVE` alone, with a log held
bz_l5:
    call bz_lbeg
    call bz_rhave
    jne .nolog
    mov si, bz_s_savk
    call bz_intour
    jc .cat
    mov si, bz_s_repk
    call bz_lcat
    mov si, bz_s_savk
    call bz_lcat
    jmp short .lv
.nolog:
    call bz_intour
    jc .l
    mov si, bz_s_benk
.cat:
    call bz_lcat
    call bz_intour
    jc .l
.lv:
    mov si, bz_s_ldk
    call bz_lcat
.l:
    jmp bz_line

; line 6: THE HELD LOG's last run (SPEC.md 130.14.3.2, 130.14.16 item 1): after
; a play or a replay, finished or stopped, `<NAME> <time> s <end> falls <n>`
; and on a course with flags `flags <reached>/<all>` - the clock, the falls,
; the flags and the hole-out, on the face that costs the frame nothing.  The
; play's stuns and shatters are the field it drops to fit (130.14.17 item 2).
; With none, the keys' hint (the mouse's under T MOUSE).  After L, `<NAME>
; <time> s  <8.3 name>`, and after V `<NAME> <time> s  demo`: the held log's
; course and its steps (SPEC.md 130.14.3.2).
bz_l6:
    mov al, [bz_lsv]
    cmp al, 1
    je .run
    jb .hint
    call bz_lbeg                ; 2 a loaded file, 3 a shipped demo
    push ax
    mov al, [bz_rlog + BZR_CRS]
    call bz_lname
    mov al, ' '
    call bz_lch
    mov ax, [bz_rlog + BZR_STEPS] ; (a log's steps are at most 255 x 2,040:
    mov dx, [bz_rlog + BZR_STEPS + 2] ; under bz_t100's 2^19)
    call bz_ltime
    mov si, bz_s_secs
    call bz_lcat
    mov al, ' '
    call bz_lch
    pop ax
    mov si, bz_lfn              ; (the loaded file's name: the package's bss)
    cmp al, 2
    jne .dm
    call bz_lcatd
    jmp bz_line
.dm:
    mov si, bz_s_demo
    call bz_lcat
    jmp bz_line
.hint:
    mov si, bz_s_hint
    cmp byte [bz_ctl], 0
    je bz_lline
    mov si, bz_s_mhint
    jmp bz_lline
.run:
    call bz_lbeg
    mov al, [bz_lsk]
    call bz_lname
    mov al, ' '
    call bz_lch
    mov ax, [bz_lsn]
    call bz_ltimew
    mov si, bz_s_secs
    call bz_lcat
    mov bl, [bz_lsend]          ; 0 stopped, 1 the goal line, 2 the cup
    xor bh, bh
    shl bx, 1
    mov si, [cs:bz_s_ends + bx]
    call bz_lcat
    mov si, bz_s_falls
    call bz_lcat
    mov ax, [bz_lsf]
    call bz_lnumw
    mov bl, [bz_lsk]
    xor bh, bh
    mov ah, [cs:bz_cncks + bx]
    or ah, ah
    jz .l
    mov si, bz_s_flags
    call bz_lcat
    mov al, [bz_lsc]
    add al, '0'
    call bz_lch
    mov al, '/'
    call bz_lch
    mov al, ah
    add al, '0'
    call bz_lch
.l:
    jmp bz_line

; line 0 (BZ_LTOUR; the title's until the PLAYGROUND made the tour six, SPEC.md
; 130.16.8 - RESULTS keeps the title there): the tour.  During one `ENTER
; next: <title>`, the tour's next course (BZ_TOUR, SPEC.md 130.26.8); stopped `Tour
; stopped`; else `Tour <total>  best <b>` (`-` for none).  A refused replay's
; reason takes it (SPEC.md 130.12.8): R is not offered in a tour.
bz_ltour:
    mov si, bz_s_err3
    cmp byte [bz_err], 3
    je bz_lline
    mov si, bz_s_err4
    cmp byte [bz_err], 4
    je bz_lline
    cmp byte [bz_tour], 0       ; wave 8c (130.19.8.3): no tour - the SLOT's
    jne .tr                     ; keys, or X's second press asked for
    mov si, bz_s_skeys
    cmp byte [bz_xarm], 0
    je bz_lline
    mov si, bz_s_xarm
    call bz_lstr
    mov al, [bz_slot]
    add al, '1'
    call bz_lch
    jmp bz_line
.tr:
    mov al, [bz_tour]
    dec al
    cmp al, BZ_NTOUR
    jae .card
    cbw                         ; (AL < BZ_NTOUR: AH = 0)
    mov bx, ax
    mov si, bz_s_tnext
    call bz_lstr
    mov al, [cs:bz_ctour + bx]  ; the tour's course k + 1 (BX = k)
    call bz_ltitle
    jmp bz_line
.card:
    mov si, bz_s_tstop
    cmp al, BZ_NTOUR + 1
    je bz_lline
    mov si, bz_s_tour
    call bz_lstr
    cmp al, BZ_NTOUR            ; finished: its total
    jne .none
    call bz_ttotal
    call bz_ltime
    jmp short .best
.none:
    mov al, '-'
    call bz_lch
.best:
    mov si, bz_s_best2
    call bz_lcat
    mov ax, [bz_dat + BZD_TOUR + 2]
    mov dx, [bz_dat + BZD_TOUR + 4]
    mov cx, ax
    or cx, dx
    jz .nb
    call bz_ltime
    jmp bz_line
.nb:
    mov al, '-'
    call bz_lch
    jmp bz_line

; RESULTS line 3: what was measured - `BENCH autopilot`, or after D `Demo
; <NAME> <time> s` and `TRUNCATED` when it stopped measuring at 65,535 frames
; (SPEC.md 130.14.3.2, 130.14.7.3).  The held log is D's until the next key
; leaves the page.
bz_lmeas:
    mov si, bz_s_meas
    cmp byte [bz_mode], 3
    jne bz_lline
    mov si, bz_s_dmeas
    call bz_lstr
    mov al, [bz_rlog + BZR_CRS]
    call bz_lname
    mov al, ' '
    call bz_lch
    mov ax, [bz_rlog + BZR_STEPS]
    mov dx, [bz_rlog + BZR_STEPS + 2]
    call bz_ltime
    mov si, bz_s_secs
    call bz_lcat
    cmp byte [bz_dtr], 0
    je .l
    mov si, bz_s_trunc
    call bz_lcat
.l:
    jmp bz_line

; -> DX:AX = the tour's total steps, the sum of [bz_ttime]'s BZ_NTOUR; BL = 1
; when one of them is the 65,535 clamp (such a total is never kept, 130.14.3.1).
; Preserves all else.
bz_ttotal:
    push cx
    push si
    xor ax, ax
    cwd
    mov bl, al
    mov si, bz_ttime
    mov cx, BZ_NTOUR
.s:
    cmp word [si], 0ffffh
    jne .a
    mov bl, 1
.a:
    add ax, [si]
    adc dx, 0
    inc si
    inc si
    loop .s
    pop si
    pop cx
    ret

; RESULTS line 2's numbers (SPEC.md 130.6), after the adapter's prefix: the
; frames, the display rate (to 999.9, the field's width) and the refreshes
; missed - a mean rate cannot tell 0 misses from a few
bz_frline:
    mov ax, [bz_rframes]
    call bz_lnumw
    mov si, bz_s_disp
    call bz_lcat
    call bz_hz10                ; AX = the display rate x 10
    cmp ax, 9999
    jbe .hz
    mov ax, 9999
.hz:
    xor dx, dx
    mov cx, 10
    div cx
    push dx
    call bz_lnumw
    mov al, '.'
    call bz_lch
    pop ax
    add al, '0'
    call bz_lch
    mov si, bz_s_hz
    call bz_lcat
    mov ax, [bz_rmiss]
    jmp bz_lnumw

; RESULTS lines 4 - 11: the worst frame, the mean CPU clocks of each part of a
; frame (PIT counts x 4), the writers' counts
bz_facres:
    mov si, bz_s_worst          ; the worst frame, and the means' heading
    call bz_lstr
    mov ax, [bz_rfmax]
    mov dx, [bz_rfmax + 2]
    shl ax, 1                   ; PIT counts x 4 = CPU clocks
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    call bz_lnum
    mov si, bz_s_mean
    call bz_lcat
    call bz_line
    xor bx, bx                  ; BX = the part (0..5)
.part:
    push bx
    mov si, bx
    shl si, 1
    mov si, [cs:bz_s_parts + si]
    call bz_lstr
    pop bx
    push bx
    call bz_meanclk             ; DX:AX = part BX's mean, CPU clocks
    call bz_lnum
    mov si, bz_s_clk
    call bz_lcat
    call bz_line
    pop bx
    inc bx
    cmp bx, BZ_NFACE            ; (the wheel's part is the rows' to read)
    jb .part
    mov si, bz_s_cols
    call bz_lstr
    mov ax, [bz_rncol]
    call bz_lnumw
    mov si, bz_s_rows
    call bz_lcat
    mov ax, [bz_rnrow]
    call bz_lnumw
    mov si, bz_s_full
    call bz_lcat
    mov ax, [bz_rnfull]
    call bz_lnumw
    mov si, bz_s_late           ; the row-0 boxes the beam overtook (SPEC.md
    call bz_lcat                ; 130.9 item 6)
    mov ax, [bz_rlate]
    call bz_lnumw
    jmp bz_line

; -> AX = the display rate x 10, from the measured frames' mean period.  1 PIT
; count is 1/1,193,182 s, so rate x 10 = 11,931,820 / mean counts.  0 = none.
bz_hz10:
    push bx
    push cx
    push dx
    call bz_period              ; DX:AX = mean PIT counts a frame (DX = 0 if sane)
    or dx, dx
    jnz .zero
    cmp ax, 183                 ; (the divide's quotient must fit 16 bits)
    jb .zero
    mov cx, ax
    mov dx, 11931820 >> 16
    mov ax, 11931820 & 0ffffh
    div cx
    jmp .out
.zero:
    xor ax, ax
.out:
    pop dx
    pop cx
    pop bx
    ret

; -> DX:AX = the mean PIT counts of one measured frame (the seven parts summed)
bz_period:
    push bx
    push cx
    push si
    xor ax, ax
    xor dx, dx
    mov si, bz_racc
    mov cx, BZ_NPART
.sum:
    add ax, [si]
    adc dx, [si + 2]
    add si, 4
    loop .sum
    call bz_div32
    pop si
    pop cx
    pop bx
    ret

; BX = part -> DX:AX = its mean in CPU clocks (PIT counts x 4)
bz_meanclk:
    push si
    mov si, bx
    shl si, 1
    shl si, 1
    mov ax, [bz_racc + si]
    mov dx, [bz_racc + si + 2]
    call bz_div32
    shl ax, 1
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    pop si
    ret

; DX:AX / [bz_rmfr] -> DX:AX (32 by 16, in two divides; 0 frames gives 0)
bz_div32:
    push bx
    push cx
    mov cx, [bz_rmfr]
    jcxz .zero
    mov bx, ax
    mov ax, dx
    xor dx, dx
    div cx                      ; the high word
    xchg ax, bx                 ; BX = the high quotient, AX = the low dividend
    div cx                      ; DX = the remainder from the high word
    mov dx, bx
    jmp .out
.zero:
    xor ax, ax
    xor dx, dx
.out:
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; bz_t100 - STEPS to HUNDREDTHS of a second (SPEC.md 130.10.6.2, 130.14.3.1):
; floor(n x 21,845 x 100 / 1,193,182), a step being 21,845 PIT counts.  In
; DX:AX = n (at most 2^19: a tour's total is under 327,671), out DX:AX.  The
; product is a 48-bit Q (its top word under 300), and 1,193,182 = 14,551 x 82,
; floor(floor(Q / a) / b) = floor(Q / ab): four 16-bit divides.  Times are kept
; as steps everywhere and converted only to be shown.  Preserves all else.
; -----------------------------------------------------------------------------
bz_t100:
    push bx
    push cx
    push si
    push di
    mov bx, dx                  ; n's high word
    mov cx, 21845
    mul cx
    mov si, ax                  ; P = n x 21,845 = BX':DI':SI
    mov di, dx
    xchg ax, bx
    mul cx                      ; (n's high word is at most 8)
    add ax, di
    adc dx, 0
    mov bx, dx                  ; P = BX:AX:SI
    mov cx, 100                 ; Q = P x 100 = BX:DI:SI
    xchg ax, si
    mul cx
    xchg ax, si                 ; SI = Q0
    mov di, dx
    mul cx
    add di, ax                  ; DI = Q1
    adc dx, 0
    xchg ax, bx
    mov bx, dx
    mul cx
    add ax, bx                  ; AX = Q2, under 300
    xchg ax, dx
    mov cx, 14551               ; Q / 14,551: DX < CX, so each quotient fits
    mov ax, di
    div cx
    mov bx, ax
    mov ax, si
    div cx                      ; BX:AX = Q / 14,551
    mov cx, 82
    xchg ax, bx
    xor dx, dx
    div cx
    xchg ax, bx
    div cx                      ; BX:AX = Q / 1,193,182
    mov dx, bx
    pop di
    pop si
    pop cx
    pop bx
    ret

; ---- the line builder ---------------------------------------------------------
; bz_lstr: SI = a NUL string -> bz_lbuf holds it (DI = its end)
bz_lstr:
    call bz_lbeg
; bz_lcat: append SI's NUL string at DI - the PART's own, read through CS
; (SPEC.md 130.19.2: the face's strings live in the shell part)
bz_lcat:
    push ax
.c:
    mov al, [cs:si]
    inc si
    or al, al
    jz .e
    call bz_lch
    jmp .c
.e:
    pop ax
    ret
; bz_lcatd: the same for a string in the PACKAGE's segment (DS): bss names
bz_lcatd:
    push ax
.c:
    lodsb
    or al, al
    jz .e
    call bz_lch
    jmp .c
.e:
    pop ax
    ret

; bz_lbeg: an empty line at bz_lbuf: a cell of margin (the padding is the
; erase), DI after it
bz_lbeg:
    mov di, bz_lbuf
    mov byte [di], ' '
    inc di
    ret

; AL = a course K: its title (bz_ctitles) or its NAME (bz_cnames) appended.
; Clobbers AX, SI.
bz_ltitle:
    mov ah, BZ_CRS_TITLEB
    mul ah
    add ax, bz_ctitles
    xchg ax, si
    jmp bz_lcat
bz_lname:
    mov ah, BZ_CRS_NAMEB
    mul ah
    add ax, bz_cnames
    xchg ax, si
    jmp bz_lcat

; AX = a course time in steps: `20:00+` for the clamp (SPEC.md 130.14.3.1),
; else as bz_ltime.  Preserves all.
bz_ltimew:
    cmp ax, 0ffffh
    jne .t
    push si
    mov si, bz_s_clamp
    call bz_lcat
    pop si
    ret
.t:
    push dx
    xor dx, dx
    call bz_ltime
    pop dx
    ret

; DX:AX = steps -> appended as seconds: `s.hh` under 100 s, `s.h` from there
; (SPEC.md 130.14.17 item 2), at most BZ_TIMEW cells for a tour's total.
; Preserves all.
bz_ltime:
    push ax
    push bx
    push cx
    push dx
    call bz_t100
    mov cx, 100
    div cx                      ; (under 6,553,600 hundredths: it fits)
    mov bx, ax
    push dx
    call bz_lnumw
    mov al, '.'
    call bz_lch
    pop ax
    aam                         ; AH = tenths, AL = hundredths
    xchg al, ah
    add ax, '00'
    call bz_lch
    cmp bx, 100
    jae .o
    mov al, ah
    call bz_lch
.o:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; AL = a character, appended at DI unless the line is full
bz_lch:
    cmp di, bz_lbuf + BZ_LMAX
    jae .full
    mov [di], al
    inc di
.full:
    ret

; AX = an unsigned word, appended at DI in decimal.  Preserves all.
bz_lnumw:
    push dx
    xor dx, dx
    call bz_lnum
    pop dx
    ret

; DX:AX = an unsigned number, appended at DI in decimal
bz_lnum:
    ; STKBALANCE-LOOP: one digit pushed a turn and the second loop pops them down to the SI mark
    push ax
    push bx
    push cx
    push dx
    push si
    mov si, sp                  ; the digits go on the stack, least first
    mov cx, 10
.dig:
    mov bx, ax                  ; DX:AX / 10, in two divides
    mov ax, dx
    xor dx, dx
    div cx
    xchg ax, bx
    div cx
    push dx                     ; the digit
    mov dx, bx
    mov bx, ax
    or bx, dx
    jnz .dig
.out:
    pop ax
    add al, '0'
    call bz_lch
    cmp sp, si
    jne .out
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; the line at DI ends: pad it to the content's cells, draw it at [bz_fy] + 2,
; fill the 2px gap above it, and step [bz_fy]
bz_line:
    push ax
    push bx
    push cx
    push dx
    push si
    mov cx, [bz_fcells]
    add cx, bz_lbuf
.pad:
    cmp di, cx
    jae .padded
    mov byte [di], ' '
    inc di
    jmp .pad
.padded:
    mov di, cx
    mov byte [di], 0
    mov bx, [bz_fy]             ; the gap above the cell row
    mov dx, bx
    inc dx
    call bz_fillrows
    add dx, BZ_LH - 1           ; DX = the cell's foot, exclusive
    cmp dx, [bz_fh]
    jle .fits
    inc bx                      ; a cell past the content's foot is not drawn
    inc bx                      ; (FONT_RUN does not clip to it): its rows
    call bz_fillrows            ; that are inside are filled instead
    jmp .next
.fits:
    mov si, bz_lbuf
    xor cx, cx
    add cx, [bz_ox]
    mov dx, [bz_fy]
    add dx, 2
    add dx, [bz_oy]
    mov ax, CBLACK | (CWHITE << 8)
    call OSAPI_FONT_RUN
.next:
    add word [bz_fy], BZ_LH
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; BX = the first content row, DX = the last: filled white across the cells'
; width (bz_fillrect's x range)
bz_fillrows:
    push ax
    push cx
    xor ax, ax
    mov cx, [bz_fcells]
    shl cx, 1
    shl cx, 1
    shl cx, 1
    dec cx
    call bz_fillrect
    pop cx
    pop ax
    ret

; AX = x1, BX = y1, CX = x2, DX = y2 in content coordinates: a white fill,
; clipped to the content box's foot
bz_fillrect:
    push ax
    push bx
    push cx
    push dx
    cmp dx, [bz_fh]
    jl .h
    mov dx, [bz_fh]
    dec dx
.h:
    cmp dx, bx
    jl .out
    push ax
    mov al, CWHITE
    call OSAPI_SET_COLOR
    pop ax
    add ax, [bz_ox]
    add cx, [bz_ox]
    add bx, [bz_oy]
    add dx, [bz_oy]
    call OSAPI_GFX_FILL
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret


; the course tables the face reads, through CS (the package keeps its own
; bz_cnames and bz_ctour for its own code: a few bytes a course)
bz_ctitles: BZ_CRS_TITLES
bz_cnames:  BZ_CRS_NAMES
bz_cncks:   BZ_CRS_NCKS
bz_ctour:   BZ_TOUR             ; the tour's courses, a byte each (SPEC.md 130.26.8)

; the face's strings: BZS measures each (<label>_n), for BZ_FIT below
%macro BZS 2
%1: db %2
%%e: db 0
%assign %{1}_n %%e - %1
%endmacro
BZS bz_s_title, 'BOUNCE BONANZA'
BZS bz_s_keys,  'ENTER SLOT '
BZS bz_s_lv,    '  LIVES '
BZS bz_s_timed, '  TIMED'
BZS bz_s_expl,  '  EXPLORE'
BZS bz_s_fk,    '  F '
BZS bz_s_skeys, '1 2 3 SLOT  E MODE  X ERASE'
BZS bz_s_xarm,  'X AGAIN: ERASE SLOT '
BZS bz_s_tkeys, 'ENTER next  ESC stop tour'
BZS bz_s_sndk,  'S SOUND '
bz_s_smodes: dw bz_s_sauto, bz_s_sspkf, bz_s_sfx, bz_s_soff
BZS bz_s_sauto, 'AUTO'
BZS bz_s_sspkf, 'SPEAKER'
BZS bz_s_sfx,   'EFFECTS ONLY'
BZS bz_s_soff,  'OFF'
BZS bz_s_sfm,   ': ADLIB'
BZS bz_s_sspk,  ': SPEAKER'
BZS bz_s_benk,  'B BENCH'
BZS bz_s_repk,  'R PLAY  D TIME  '
BZS bz_s_savk,  'W SAVE'
BZS bz_s_ldk,   '  L LOAD  V DEMO'
BZS bz_s_ctlk,  '  T '
BZS bz_s_keyb,  'KEYS'
BZS bz_s_mouse, 'MOUSE'
BZS bz_s_cga,   'Adapter: CGA, 320x200 four colours'
BZS bz_s_herc,  'Adapter: Hercules, 360x200 pair pixels'
BZS bz_s_vga,   'Adapter: VGA, 320x200, two planes'
BZS bz_s_noad,  'CGA, HERC OR VGA ONLY'
BZS bz_s_small, 'NEEDS MORE MEMORY (128KB kernel)'
BZS bz_s_ballk, '  M '
bz_s_mats:  dw bz_s_rubber, bz_s_steel, bz_s_glass
BZS bz_s_rubber, 'RUBBER'
BZS bz_s_steel, 'STEEL'
BZS bz_s_glass, 'GLASS'
BZS bz_s_hint,  'Arrows roll  Space hop  L.Shift grip'
BZS bz_s_mhint, 'Mouse tilts  left hop  right grip'
BZS bz_s_demo,  'demo'
BZS bz_s_secs,  ' s '
bz_s_ends:  dw bz_s_estop, bz_s_egoal, bz_s_ecup, bz_s_etime
BZS bz_s_estop, 'stop'
BZS bz_s_egoal, 'goal'
BZS bz_s_ecup,  'cup'
BZS bz_s_etime, 'TIME'
BZS bz_s_falls, ' falls '
BZS bz_s_flags, ' flags '
BZS bz_s_tnext, 'ENTER next: '
BZS bz_s_tstop, 'Tour stopped'
BZS bz_s_tour,  'Tour '
BZS bz_s_best2, '  best '
BZS bz_s_clamp, '20:00+'
BZS bz_s_err,   'The full screen mode was refused'
BZS bz_s_err2,  "The window's display changed"
BZS bz_s_err3,  "Another course's log"
BZS bz_s_err4,  "Other physics' log"
BZS bz_s_cgar,  'CGA frames '
BZS bz_s_hercr, 'Herc frames '
BZS bz_s_vgar,  'VGA frames '
BZS bz_s_disp,  '  '
BZS bz_s_hz,    ' Hz  misses '
BZS bz_s_meas,  'BENCH autopilot'
BZS bz_s_dmeas, 'Demo '
BZS bz_s_trunc, 'TRUNCATED'
BZS bz_s_back,  'Any key: back'
BZS bz_s_worst, 'Worst '
BZS bz_s_mean,  ' clk   means (GLIDE):'
BZS bz_s_clk,   ' clk'
BZS bz_s_cols,  'col '
BZS bz_s_rows,  ' row '
BZS bz_s_full,  ' full '
BZS bz_s_late,  ' late '
bz_s_parts: dw bz_s_p0, bz_s_p1, bz_s_p2, bz_s_p3, bz_s_p4, bz_s_p5
BZS bz_s_p0,    '  sim+camera     '
BZS bz_s_p1,    '  box compose    '
BZS bz_s_p2,    '  rows           '
BZS bz_s_p3,    '  retrace (idle) '
BZS bz_s_p4,    '  flip+columns   '
BZS bz_s_p5,    '  box write      '

; EVERY FACE LINE FITS THE CGA's 42 CELLS (SPEC.md 130.14.17 item 2): each
; builder's widest line - the margin cell, its strings, its fields at their
; widest (a word 5 digits, a DWORD 10, a time BZ_TIMEW, the longest title and
; NAME and the widest par as bzcourse.inc measures them) - or the build fails.
%macro BZ_FIT 2
 %assign %%w %2
 %if %%w > BZ_FACEW
  %error face line %1 is %[%%w] cells and the CGA content holds BZ_FACEW (SPEC.md 130.14.17 item 2)
 %endif
%endmacro
%assign BZ_SNDW bz_s_sauto_n
%if bz_s_sspkf_n > BZ_SNDW
 %assign BZ_SNDW bz_s_sspkf_n
%endif
%if bz_s_sfx_n > BZ_SNDW
 %assign BZ_SNDW bz_s_sfx_n
%endif
%if bz_s_sfm_n > bz_s_sspk_n
 %assign BZ_SNDW BZ_SNDW + bz_s_sfm_n
%else
 %assign BZ_SNDW BZ_SNDW + bz_s_sspk_n
%endif
BZ_FIT 0, 1 + bz_s_title_n
BZ_FIT 1, 1 + bz_s_keys_n + 1 + bz_s_lv_n + 1 + bz_s_expl_n + bz_s_fk_n + BZ_CRS_NAMEW
BZ_FIT 0s, 1 + bz_s_skeys_n
BZ_FIT 0x, 1 + bz_s_xarm_n + 1
BZ_FIT 1t, 1 + bz_s_tkeys_n
BZ_FIT 2, 1 + bz_s_cga_n
BZ_FIT 2h, 1 + bz_s_herc_n
BZ_FIT 2v, 1 + bz_s_vga_n
BZ_FIT 2s, 1 + bz_s_small_n
BZ_FIT 2e, 1 + bz_s_err_n
BZ_FIT 2d, 1 + bz_s_err2_n
BZ_FIT 3, 1 + bz_s_ballk_n + bz_s_rubber_n + bz_s_ctlk_n + bz_s_mouse_n
BZ_FIT 4, 1 + bz_s_sndk_n + BZ_SNDW
BZ_FIT 5, 1 + bz_s_repk_n + bz_s_savk_n + bz_s_ldk_n
BZ_FIT 5b, 1 + bz_s_benk_n + bz_s_ldk_n
BZ_FIT 6, 1 + bz_s_hint_n
BZ_FIT 6m, 1 + bz_s_mhint_n
BZ_FIT 6f, 1 + BZ_CRS_NAMEW + 1 + BZ_TIMEW + bz_s_secs_n + 1 + 12
BZ_FIT 6l, 1 + BZ_CRS_NAMEW + 1 + BZ_TIMEW + bz_s_secs_n + bz_s_estop_n + bz_s_falls_n + 4 + bz_s_flags_n + 3
BZ_FIT 6t, 1 + BZ_CRS_NAMEW + 1 + BZ_TIMEW + bz_s_secs_n + bz_s_etime_n + bz_s_falls_n + 4 + bz_s_flags_n + 3
BZ_FIT 12, 1 + bz_s_tnext_n + BZ_CRS_TITLEW
BZ_FIT 12t, 1 + bz_s_tour_n + BZ_TIMEW + bz_s_best2_n + BZ_TIMEW
BZ_FIT 12e, 1 + bz_s_err3_n
BZ_FIT 12p, 1 + bz_s_err4_n
BZ_FIT 12s, 1 + bz_s_tstop_n
BZ_FIT r2, 1 + bz_s_hercr_n + 5 + bz_s_disp_n + 5 + bz_s_hz_n + 5
BZ_FIT r3, 1 + bz_s_meas_n
BZ_FIT r3d, 1 + bz_s_dmeas_n + BZ_CRS_NAMEW + 1 + BZ_TIMEW + bz_s_secs_n + bz_s_trunc_n
BZ_FIT r4, 1 + bz_s_worst_n + 10 + bz_s_mean_n
BZ_FIT r5, 1 + bz_s_p0_n + 10 + bz_s_clk_n
BZ_FIT r11, 1 + bz_s_cols_n + 5 + bz_s_rows_n + 5 + bz_s_full_n + 5 + bz_s_late_n + 5
BZ_FIT r12, 1 + bz_s_back_n
%if bz_s_estop_n < bz_s_egoal_n || bz_s_estop_n < bz_s_ecup_n || bz_s_rubber_n < bz_s_steel_n || bz_s_rubber_n < bz_s_glass_n || bz_s_p0_n != bz_s_p5_n || bz_s_hercr_n < bz_s_cgar_n || bz_s_mouse_n < bz_s_keyb_n || bz_s_demo_n > 12
 %error "BZ_FIT measures each line by its widest choice: the choices above moved"
%endif

