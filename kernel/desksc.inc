; =============================================================================
; os8088 - desksc.inc - desktop SHORTCUTS (SPEC.md 26.8)
;
; An entry dragged out of a Disk window onto the desktop becomes a shortcut:
; its picture and a caption on a grid cell, selected by a click, opened by a
; double-click or Enter exactly as the Disk window would open it, moved by a
; drag, removed by Delete, a right-click or Locator's File menu - and kept in
; SYSTEM.CFG, so it is there after a reboot. kern_big only (OS88_SHORTCUTS).
;
; WHERE EACH HALF LIVES, which is the whole of the design (docs/plans/
; completed/DESKTOP-SHORTCUTS-PLAN.md 7):
;
;   .cold    drawing, hit-testing, selection, the drag's tracking loop, the
;            open, the keys and the right-click - what a click needs at once
;   .text    the claim (sc_resize, sc_reloc), the strings, the badge
;   .modc    CTRL.DRV: CREATING, MOVING and REMOVING one, and the SYSTEM.CFG
;            trailer. Every one of them ends in a SYSTEM.CFG write and the
;            writer is already in that image, so the gesture's body rides the
;            load the save needed anyway - and a machine that never makes a
;            shortcut never carries a byte of it
;   .ovl     the boot reader, which runs once and is gone
;
; THE TABLE IS A HEAP CLAIM, never .bss: one claim for every shortcut, grown
; and shrunk a KB at a time (eight records a KB), freed when the last one goes.
; A machine with no shortcuts pays this file's code and four bytes of .bss.
;
; A shortcut is zone index DESK_SC0 + its row, so desk.inc's selection,
; double-click and redraw machinery serve it through one-compare arms - the
; Wire zone's arrangement (SPEC.md 26.7) with a table instead of a record.
; =============================================================================

%ifdef OS88_SHORTCUTS

; --- the record (SPEC.md 26.8.1) - the claim's row AND the file's, verbatim --
SC_R_VOL    equ 0               ;  1: the volume index (0 = A:), 0xFF = free row
SC_R_COL    equ 1               ;  1: the grid cell's column...
SC_R_ROW    equ 2               ;  1: ...and its row; together, a WORD
SC_R_KIND   equ 3               ;  1: 0 document, 1 package, 2 folder - the
                                ;     SPEC.md 19.1 type word's low byte
SC_R_CAPX   equ 4               ;  1: the caption's pen, px into the cell. It
                                ;     is CENTRED, so its width is SC_W - 2x
                                ;     this, and nothing measures it at paint
SC_R_PATH   equ 5               ; 46: the ENTRY's whole path, `\APPS\CALC.O88`,
SC_PATHMAX  equ 46              ;     NUL: a 32-byte folder path (dsk_path's
                                ;     own bound), a `\` and an 8.3 name
SC_R_CAP    equ 51              ; 13: the caption, NUL, decided at the drop
SC_CAPMAX   equ 13
SC_R_BODY   equ 64              ; 64: the 16x16 picture (SPEC.md 25 body form),
                                ;     as the Disk window had it
SC_REC      equ 128
SC_MAX      equ 16              ; ...rows, and [sc_nrows] never exceeds it
SC_PERKB    equ 8               ; rows a KB: 8 * 128, exactly
SC_VER      equ 1               ; the trailer's own version (SPEC.md 26.8.6)
%if SC_PERKB * SC_REC > 1024
  %error "desksc: SC_PERKB records must fit one KB of the claim"
%endif

; --- the grid (SPEC.md 26.8.2) -----------------------------------------------
SC_PX       equ 104             ; cell pitch, rightwards from the band's edge
SC_W        equ 96              ; the caption's room: twelve 8px glyphs - the
                                ; longest 8.3 name, and every header name the
                                ; tree ships but one (26.8.4)
SC_H        equ 16 + DESK_ZGAP + DESK_LBLH  ; the picture, the gap, the label
SC_X0       equ 4               ; the first column's left, off the band's edge
SC_ICX      equ (SC_W - 16) / 2 ; the picture, centred over the caption
DESK_SC0    equ 16              ; zone index of row 0: desk_sel's byte holds
                                ; 16..31, which no volume index can be
DESK_SCBIT  equ 0x8000          ; the zone mask's bit for "and [sc_dmgm]"
SC_OP_NEW   equ 0               ; CTRL.DRV's one entry, CPE_SC, takes these
SC_OP_MOVE  equ 1               ; in AH (SPEC.md 26.8.7)
SC_OP_DEL   equ 2
%if DESK_NZ >= 15
  %error "desksc: bit 15 of the zone mask is the shortcuts' and DESK_NZ has reached it"
%endif

; =============================================================================
section .cold
; =============================================================================

; -----------------------------------------------------------------------------
; sc_row - a zone's record, and whether it is a shortcut that exists
; in:  AL = a shortcut zone (DESK_SC0..)
; out: CF = 0 it is, ES:BX = its record; CF = 1 no claim, past the claim or a
;      free row (ES:BX are its record's address whenever the row is inside the
;      claim, which is what sc_xy relies on)
; clobbers: ES, BX, flags
; -----------------------------------------------------------------------------
sc_row:
    push ax
    sub al, DESK_SC0
    cmp al, [sc_nrows]
    cmc                         ; CF = 1 iff past the claim
    jc .out
    mov ah, SC_REC
    mul ah
    mov bx, ax
    mov es, [sc_seg]
    cmp byte [es:bx+SC_R_VOL], 0xFF
    cmc                         ; CF = 1 iff the free mark
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; sc_xy - a shortcut's cell origin (SPEC.md 26.8.2)
; in:  AL = a live shortcut zone
; out: AX = the cell's left, DX = its top
; clobbers: AX, DX (the outputs), flags
;
; Columns run rightwards from the BAND's left edge - a left dock pushes them
; over (SPEC.md 30.5) - and rows down on the drive zones' own pitch, so the
; two grids line up row for row. A machine moved to a smaller screen keeps
; the cell numbers and draws them where they now fall; the next move snaps.
; -----------------------------------------------------------------------------
sc_xy:
    push bx
    push cx
    push es
    call sc_row
    mov al, [es:bx+SC_R_ROW]
    cbw                         ; rows are under 16: AH = 0
    mul word [desk_zstep]       ; 15 * 60: DX = 0
    add ax, DESK_ZY0
    xchg ax, cx                 ; CX = the top
    mov al, [es:bx+SC_R_COL]
    mov ah, SC_PX
    mul ah
    add ax, SC_X0
    add ax, [vid_band_x0]
    mov dx, cx
    pop es
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; sc_rect - a shortcut's DRAWN rect, desk_zone_rect's contract
; in:  AL = a live shortcut zone
; out: AX = x1, BX = y1, CX = x2, DX = y2, inclusive - the cell plus the
;      label's overhang, which is what the refill, the damage and a hit cover
; clobbers: the four outputs
; -----------------------------------------------------------------------------
sc_rect:
    call sc_xy
    mov bx, dx
    mov cx, ax
    add cx, SC_W + DESK_ZOVER - 1
    sub ax, DESK_ZOVER
    add dx, SC_H - 1
    ret

; -----------------------------------------------------------------------------
; sc_caprect - the white rect that HUGS a shortcut's caption (SPEC.md 26.4's
;              rule), its overhang included; the pen is at x1 + DESK_ZOVER,
;              y1 + 2. The draw and the highlight both come here, so the two
;              cannot disagree about it.
; in:  AL = a live shortcut zone
; out: AX = x1, BX = y1, CX = x2, DX = y2
; clobbers: the four outputs, flags
; -----------------------------------------------------------------------------
sc_caprect:
    push es
    call sc_row
    mov cl, [es:bx+SC_R_CAPX]
    pop es
    xor ch, ch
    call sc_xy                  ; AX = the cell's left, DX = its top
    add ax, cx                  ; AX = the pen
    neg cx
    shl cx, 1
    add cx, ax
    add cx, SC_W + DESK_ZOVER - 1   ; x2: pen + (SC_W - 2 * capx) - 1 + overhang
    sub ax, DESK_ZOVER
    add dx, 16 + DESK_ZGAP
    mov bx, dx
    add dx, DESK_LBLH - 1
    ret

; -----------------------------------------------------------------------------
; sc_hit - the shortcut under a desktop press, if any
; in:  DI = x, SI = y
; out: CF = 0 and CL = its zone; CF = 1 none
; clobbers: AX, BX, CX, DX, flags
; -----------------------------------------------------------------------------
sc_hit:
    push es
    mov cl, DESK_SC0
.z:
    push cx
    mov al, cl
    call sc_row
    jc .n
    call sc_rect
    cmp di, ax
    jb .n
    cmp di, cx
    ja .n
    cmp si, bx
    jb .n
    cmp si, dx
    ja .n
    pop cx
    clc
    jmp short .out
.n:
    pop cx
    inc cl
    cmp cl, DESK_SC0 + SC_MAX
    jb .z
    stc
.out:
    pop es
    ret

; -----------------------------------------------------------------------------
; sc_dmg - desk_dmg_zones' second half: which shortcuts the damage touches
; in:  [wm_dmg_*]; DI = the volume mask under construction; lock held
; out: [sc_dmgm] = bit n set = row n is in the damage, and the damage rect
;      grown to cover each; DI gains DESK_SCBIT when any is
; clobbers: AX, BX, CX, DX, SI, flags (desk_dmg_zones banked them all)
; -----------------------------------------------------------------------------
sc_dmg:
    push es
    mov si, DESK_SC0 + SC_MAX   ; the LAST row first: each answer is rotated
.z:                             ; in at the bottom, so sixteen rotations
    dec si                      ; leave row n at bit n and nothing stale
    mov ax, si
    call sc_row
    jc .n                       ; CF = 1 there - turned into a 0 below
    call sc_rect
    call KERNEL_SEG:cw_wm_dmg_hit
    jnc .r                      ; CF = 0: not in the damage
    call KERNEL_SEG:cw_wm_dmg_add
    or di, DESK_SCBIT
    stc
    jmp short .r
.n:
    clc
.r:
    rcl word [sc_dmgm], 1
    cmp si, DESK_SC0
    ja .z
    pop es
    ret

; -----------------------------------------------------------------------------
; sc_paint_mask - draw the shortcuts [sc_dmgm] names; lock held
; out: nothing (all registers preserved)
; -----------------------------------------------------------------------------
sc_paint_mask:                  ; BX and DX are desk_pm_body's to restore
    push ax
    push es
    mov dx, [sc_dmgm]
    mov al, DESK_SC0
.n:
    shr dx, 1
    jnc .s
    call sc_row
    jc .s
    call sc_draw
.s:
    inc al
    or dx, dx
    jnz .n
    pop es
    pop ax
    ret

; -----------------------------------------------------------------------------
; sc_stage - one field of a record, into dsk_ico where the kernel's drawing
;            routines can read it through DS (the record is in the claim)
; in:  AL = a live shortcut zone, SI = the field's offset, CX = its length
; out: SI = dsk_ico, holding it
; clobbers: BX, CX, SI, ES, flags
;
; dsk_ico is the painters' shared scratch and every caller holds the gfx
; lock, which is that buffer's rule for its painting tenants (disk.inc).
; -----------------------------------------------------------------------------
sc_stage:
    push di
    call sc_row
    add si, bx
    mov di, dsk_ico
    push ds
    push es
    push ds
    pop es
    pop ds
    cld
    rep movsb
    pop ds
    mov si, dsk_ico
    pop di
    ret

; -----------------------------------------------------------------------------
; sc_draw - repaint one shortcut whole: the desktop under its cell, its
;           picture, its caption, and the highlight when it is selected.
;           desk_draw_zone's contract.
; in:  AL = a live shortcut zone; the gfx lock held
; out: nothing (all registers preserved; [gfx_color] restored)
;
; THE BADGE IS ITS OWN RECORD, drawn BESIDE the picture (SPEC.md 26.8.3): a
; body that arrived all zero leaves the badge alone, which is the fallback
; the ask named.
; -----------------------------------------------------------------------------
sc_draw:
    call kentc_di
    push es
    mov ah, [gfx_color]         ; the pen on the stack: thm_desk writes it
    push ax                     ; (desk_draw_zone's note) - AL is the zone
    call sc_rect
    call KERNEL_SEG:cw_thm_desk ; the desktop under the cell
    pop ax
    push ax
    mov si, SC_R_BODY
    mov cx, 64
    call sc_stage               ; SI = the picture
    pop ax
    push ax
    call sc_xy
    xchg ax, cx
    add cx, SC_ICX
    call KERNEL_SEG:cw_icon_draw16
    pop ax
    push ax
    call sc_xy                  ; THE BADGE, beside the picture rather than
    xchg ax, cx                 ; over it: its own small record, its bottom
    add cx, SC_ICX - 11         ; on the picture's and one column clear of
    add dx, 16 - 10             ; its left edge (SPEC.md 26.8.3)
    mov si, sc_bdg
    call KERNEL_SEG:cw_icon_draw
    pop ax
    push ax
    mov si, SC_R_CAP
    mov cx, SC_CAPMAX
    call sc_stage               ; SI = the caption...
    mov byte [dsk_ico+SC_CAPMAX-1], 0   ; ...terminated: the file is untrusted
    pop ax
    push ax
    call sc_caprect
    mov byte [gfx_color], CWHITE
    call ct_cw_gfx_fill
    mov cx, ax
    add cx, DESK_ZOVER
    mov dx, bx
    add dx, 2
    mov ax, (CWHITE << 8) | CBLACK
    call ct_cw_font_run         ; OPAQUE, SPEC.md 26.6's rule
    pop ax
    push ax
    cmp al, [desk_sel]
    jne .done
    call sc_hilite
.done:
    pop ax
    mov [gfx_color], ah
    pop es
    jmp kretc_di

; -----------------------------------------------------------------------------
; sc_hilite - XOR a shortcut's picture and its caption: the selection, and
;             desk_zone_hilite's contract (self-inverse; lock held)
; in:  AL = a live shortcut zone
; clobbers: AX, BX, CX, DX
;
; Not the CELL: a 96x30 inverted block around a 16x16 picture reads as a hole
; in the desktop. The two rects are the two things that ARE the shortcut.
; -----------------------------------------------------------------------------
sc_hilite:
    push ax
    call sc_xy
    add ax, SC_ICX
    mov bx, dx
    mov cx, ax
    add cx, 15
    add dx, 15
    call ct_cw_gfx_xor_fill
    sub ax, 11                  ; ...the badge beside it, which IS part of the
    add bx, 16 - 10             ; picture: its rect off the picture's (sc_draw)
    mov cx, ax
    add cx, 9
    call ct_cw_gfx_xor_fill
    pop ax
    call sc_caprect
    jmp ct_cw_gfx_xor_fill      ; the NEAR trampoline (desk_zone_hilite's note)

; -----------------------------------------------------------------------------
; sc_open - what a double-click on a shortcut does (SPEC.md 26.8.5)
; in:  AL = a live shortcut zone; UI task, no lock held
; out: nothing (all registers preserved)
;
; WHAT THE DISK WINDOW WOULD DO, by name, through the doors it already has:
; a folder is fm_choose, a package is OSAPI_PKG_START's by-name arm and a
; document is that slot's document arm, which is the association route a
; double-click on it takes (SPEC.md 21.5.3). The Disk window's own fm_open_sel
; is welded to a listing index, and every arm it reaches has this twin.
;
; THE PATH IS WALKED, never a cluster trusted: there is no volume identity on
; this system (every disk carries one serial), so the same path on another
; copy of the disk is the same shortcut - and one whose disk is not in the
; drive says so, as one toast naming the drive: no disk and no file are the
; same thing to whoever double-clicked.
;
; assoc_doc is the component buffer and then the document's locator: it is
; UI-task-only scratch, and ld_pkg_byname copies the locator into exactly that
; block, so for a document the copy is onto itself. The claim may MOVE across
; any of the I/O, so ES is re-read from [sc_seg] and never carried.
; -----------------------------------------------------------------------------
sc_open:
    call kentc_bp
    push es
    call sc_row
    mov bp, bx                  ; BP = the record's offset, for the duration
    call drv_vol_bank
    mov al, [es:bp+SC_R_VOL]
    mov [sc_vol], al
    xor bx, bx
    call fcp_goto               ; the volume's root - CF = no disk there
    jc .nf
    lea di, [bp+SC_R_PATH]
.comp:
    mov es, [sc_seg]
    cmp byte [es:di], '\'
    jne .c0
    inc di
.c0:
    mov si, assoc_doc
.cc:
    mov al, [es:di]
    cmp al, '\'
    je .cend
    or al, al
    jz .cend
    mov [si], al
    inc si
    inc di
    cmp si, assoc_doc + SC_CAPMAX - 1
    jb .cc
.cend:
    mov byte [si], 0
    mov si, assoc_doc
    call dskw_stat_x            ; AL = attribute, BX = first cluster; SI, DI
    jc .nf                      ; and BP survive it
    mov es, [sc_seg]
    cmp byte [es:di], 0
    je .leaf                    ; the last component is the entry itself
    test al, 0x10
    jz .nf                      ; a FILE of that name is not the folder
    mov al, [sc_vol]
    call fcp_goto
    jc .nf
    jmp short .comp
.leaf:
    test al, 0x10               ; WHAT IT IS NOW decides, and not what it was:
    jnz .dir                    ; a folder opens as one whatever the record
    mov ah, [es:bp+SC_R_KIND]   ; says, and a file runs as a package or opens
    xor dx, dx
    mov es, dx                  ; a PACKAGE: SI = its name, nothing through
    dec ah                      ; ES:DI (SPEC.md 21.5) - a kind of 1
    jz .run
    mov ax, [dsk_cwd]           ; a DOCUMENT: the locator is the name, the
    mov [assoc_dclus], ax       ; directory it is in and the volume - the
    mov al, [sc_vol]            ; shape OSAPI_ARG_FILE answers with
    mov [assoc_ddrv], al
    push ds
    pop es
    mov di, assoc_doc
    mov si, sc_nul              ; ...and NO name: its extension picks the
.run:                           ; program, which is the double-click
    xor cx, cx                  ; DX:CX = 0: read the file
    call COLD_SEG:ldf_ld_pkg_start
    jnc .back
    call ld_say_status          ; the Disk window's verdicts (SPEC.md 22.9)
    jmp short .back
.dir:
    call drv_vol_back
    mov al, [sc_vol]            ; a Disk window there: fm_choose fronts one
    mov dx, bx                  ; already showing it, opens one, or moves the
    call fm_choose              ; frontmost at the cap (SPEC.md 22.1)
    jmp short .out
.nf:                            ; ONE answer, naming the drive: no disk
    mov al, [sc_vol]            ; and no file are the same thing to whoever
    add al, 'A'                 ; double-clicked (the letter is the volume's,
    mov [sc_s_nf+20], al        ; desk_lbl_gen's way)
    mov si, sc_s_nf
    call drv_vol_back           ; the volume FIRST, then the toast - putting
    push ds                     ; it back touches the floppy (ui_sys_open's
    pop es                      ; order)
    xor cx, cx
    call KERNEL_SEG:cw_toast_show
    jmp short .out
.back:
    call drv_vol_back
.out:
    jmp kretc_es

; -----------------------------------------------------------------------------
; sc_drag - a press on a shortcut that MOVES (SPEC.md 26.8.4)
; in:  AL = the zone, just selected; CX, DX = the press; no lock held
; out: nothing (AL preserved); clobbers AX's high half, BX, CX, DX
;
; Only the THRESHOLD is resident: fm_drag's four pixels, waited out with the
; lock free. Past it the gesture is CTRL.DRV's, outline and all - the drop has
; to load that image to write SYSTEM.CFG anyway, and a press that never moves
; four pixels, which is every ordinary click, never asks for it.
; -----------------------------------------------------------------------------
sc_drag:
    push ax
    mov [fm_startx], cx         ; fm_drag's own banked press point: a Disk
    mov [fm_starty], dx         ; window's drag cannot be live (it runs inside
    cmp byte [mou_ptr], 0       ; that window's W_ONCLICK). No mouse, no drag
    je .out
    call ct_cw_gfx_lock
    call fm_dgwait              ; fm_drag's own four pixels
    jc .unl                     ; let go where it was pressed: a click
    pop ax
    push ax
    mov ah, SC_OP_MOVE
    call sc_modcall
.unl:
    call ct_cw_gfx_unlock
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; sc_modcall - run one of CTRL.DRV's shortcut entries (SPEC.md 26.8.7)
; in:  AH = SC_OP_*; AL, CX, DX = the operation's own arguments; the gfx
;      lock held
; out: nothing; a module that cannot be read says `Needs Sys Disk A:`
; clobbers: whatever the entry clobbers
;
; The panel may be OPEN, and then its image is already here and must stay:
; cpf_cp_flush_close's mod_drop cannot tell (mod.inc), so this asks first
; whether it is resident and only drops what it loaded itself.
; -----------------------------------------------------------------------------
sc_modcall:
    push ax
    mov al, MOD_CTRL
    call mod_live               ; CF = 0 resident already: the panel is open
    pop ax                      ; (mod_live answers its row in BX)
    pushf
    call cpf_need
    jc .no
    call far [CPFP + CPE_SC * 4]
    popf
    jnc .ret
    push ax
    mov al, MOD_CTRL
    call mod_drop
    pop ax
.ret:
    ret
.no:
    popf
    jmp hbf_nodisk              ; the panel's own sentence (SPEC.md 2.8.4)

; -----------------------------------------------------------------------------
; desk_open - spend a desktop zone: what a double-click or Enter does
; in:  AL = the zone; no lock held
; out: nothing; clobbers AX..DI
;
; desk_click's double-click arm, made a routine of its own because Enter on a
; selected zone is the same act (SPEC.md 26.8.5).
; -----------------------------------------------------------------------------
desk_open:
    call ct_cw_gfx_lock         ; the store is INSIDE the lock (SPEC.md 26.2)
    mov byte [desk_sel], 0xFF
    call desk_zone_redraw
    call ct_cw_gfx_unlock
    cmp al, DESK_SC0
    jae sc_open
    cmp al, DESK_SVZ
    je .svc
    jmp files_open_drive_x      ; AL = the drive, no lock held (SPEC.md 22)
.svc:
    call KERNEL_SEG:cw_ui_svc_open
    ret

; -----------------------------------------------------------------------------
; desk_select - make AL the desktop's selection (SPEC.md 26.2)
; in:  AL = the zone; no lock held
; out: nothing; AL preserved, AH and BX clobbered
;
; desk_click's selection arm, shared with the right press (SPEC.md 26.8.5):
; the store is inside the lock hold, because desk_zone_redraw's partial case
; FLIPS the highlight rather than repainting it.
; -----------------------------------------------------------------------------
desk_select:
    mov bx, [ui_click_t]        ; the double-click timer restarts here
    mov [desk_clkt], bx
    mov ah, [desk_sel]
    cmp ah, al
    je .out
    call ct_cw_gfx_lock
    mov [desk_sel], al
    cmp ah, 0xFF
    je .new
    xchg al, ah
    call desk_zone_redraw       ; the old one, deselected
    xchg al, ah
.new:
    call desk_zone_redraw       ; ...and the new one
    call ct_cw_gfx_unlock
.out:
    ret

; -----------------------------------------------------------------------------
; desk_key - Enter and Delete on the desktop's selection (SPEC.md 26.8.5)
; in:  AX = the keystroke (AL = ASCII, AH = scan); no lock held
; out: CF = 1 the desktop took it (registers clobbered - a window's own key
;      handler would have clobbered them too); CF = 0 it goes where keys
;      always went, every register preserved
;
; Only while LOCATOR owns the bar - a click on the bare desktop is what hands
; it the bar (SPEC.md 12) - so a window the user went back to gets its keys
; as before with a zone still lit. Enter is AL = 13 rather than a scan code,
; so the keypad's arrives too; Delete is scan 53h, which both keys send.
; Enter opens ANY zone, drives included - it is the double-click.
; -----------------------------------------------------------------------------
desk_key_x:
    cmp word [menu_win], 0
    jne .no
    cmp byte [desk_sel], 0xFF
    je .no
    cmp al, 13
    mov al, [desk_sel]          ; `mov` writes no flag
    je .enter
    cmp ah, 0x53
    jne .no
    call sc_del                 ; a drive's zone is refused in CTRL.DRV
    jmp short .yes
.enter:
    call desk_open
.yes:
    stc                         ; TAKEN: ui_task goes straight to its event
    retf                        ; drain, which reads no register it left
.no:
    clc                         ; ...and NOT taken, every register as it came
    retf

; sc_del - remove the shortcut AL; no lock held (the three routes' door).
; CTRL.DRV refuses a zone that is not a live shortcut, so no route checks.
sc_del:
    call ct_cw_gfx_lock
    mov ah, SC_OP_DEL
    call sc_modcall
    jmp ct_cw_gfx_unlock

; sc_menu_del_f - Locator's File > Remove Shortcut (ui_cmd, no lock held)
sc_menu_del_f:
    mov al, [desk_sel]
    call sc_del
    retf

; -----------------------------------------------------------------------------
; sc_rclick - a right press on the bare desktop (ui_rdown, no lock held)
; in:  CX, DX = the press
; out: nothing; clobbers what ui_rdown may (AX..BP, its own header)
;
; On a shortcut: select it and pop its one command (SPEC.md 26.8.5).
; -----------------------------------------------------------------------------
sc_rclick_x:
    mov di, cx
    mov si, dx
    call sc_hit
    jc .out
    mov al, cl
    call desk_select
    call ct_cw_gfx_lock
    push ax
    mov cx, di
    mov dx, si
    mov bx, sc_popup
    mov ax, 1
    call KERNEL_SEG:cw_menu_popup
    pop ax                      ; `pop` writes no flag: the pick's CF stands
    pushf                       ; ...but gfx_unlock does, so it is banked
    call ct_cw_gfx_unlock       ; across the unlock - and the lock IS let go
    popf                        ; first: sc_del takes its own
    jc .out
    call sc_del
.out:
    retf

; --- far entries for CTRL.DRV and the boot overlay (SPEC.md 2.8) -------------
sc_rect_f:      call sc_rect
                retf
sc_peek_f:      call dsk_peek_x
                retf
sc_dgxor_f:     call fm_dgxor
                retf
sc_dgmove_f:    call fm_dgmove
                retf

; -----------------------------------------------------------------------------
; sc_mem_f - the table's door to the heap (SPEC.md 26.8.1), FAR
; in:  AX = KB (0 = free the claim at DX); DX = the claim, 0 = a new one;
;      CX = a NEW claim's relocation proc, 0 = leave it pinned
; out: CF = 0 and DX = the claim now; CF = 1 refused, the old one as it was
; clobbers: DX (the output), flags
;
; ONE door, MEM_K_SC every time, and the bookkeeping is the callers': the
; heap's routines are `.cold` (SPEC.md 50.3), CTRL.DRV and the boot overlay
; reach `.cold` only far, and three doors would be three times the stub.
; -----------------------------------------------------------------------------
sc_mem_f:
    push ax
    push bx
    mov bx, MEM_K_SC
    or ax, ax
    jz .free
    or dx, dx
    jnz .regrow
    call mem_claim_x
    jc .out
    jcxz .out                   ; CF is the claim's 0: a pinned claim
    push dx
    mov ax, cx
    call mem_movable_x          ; a refusal only PINS it (ico_need's note)
    pop dx
    clc
    jmp short .out
.regrow:
    call mem_regrow
    jmp short .out
.free:
    call mem_free_x
.out:
    pop bx
    pop ax
    retf

; =============================================================================
section .text
; =============================================================================

; sc_reloc - the compactor moved the table (DX = its new base). In .text,
; called through the kernel's segment (ico_reloc's note). No compare against
; the old base: the table is the one claim this proc is registered on - the
; trailer's claim (sc_m_ser) is made PINNED, with none.
sc_reloc:
    mov [sc_seg], dx
    ret

; --- the File menu's item and the right-click's, ONE string ------------------
; ui_loc_gate points item 1 at the MENU_DIS byte or past it, the Close Window
; idiom (menu.inc), so the greyed twin costs one byte and not a second string.
sc_s_remx   db MENU_DIS
sc_s_rem    db 'Remove Shortcut'    ; NO NUL OF ITS OWN: it ends on sc_nul's,
sc_nul      db 0                ; ...which is also an EMPTY name, for a
                                ; document's open. Nothing may go between
sc_s_nf     db 'Shortcut not found (?:)', 0   ; 23: exactly a toast
sc_popup    dw sc_s_rem         ; the right-click's one-item menu
sc_bdg      db 1, 10            ; the badge: 10x10, one word across - a box
            times 10 dw 0xFFC0  ; the mask: the whole box white
            dw 0xFFC0, 0x8040, 0x8740, 0x8340, 0x8540   ; the box, and an arrow
            dw 0xB840, 0xA040, 0xA040, 0x8040, 0xFFC0   ; curving up and right

; =============================================================================
section .bss
; =============================================================================
sc_seg      resw 1              ; the table's claim, 0 = no shortcuts
sc_nrows    resb 1              ; rows the claim holds, 0..SC_MAX
sc_vol      resb 1              ; sc_open: the volume, across its walk
sc_dmgm     resw 1              ; bit n = row n is in the damage (26.8.3)

; =============================================================================
section .modc                   ; CTRL.DRV (SPEC.md 26.8.7): CS = the image,
; =============================================================================
; DS = KERNEL_SEG, out through far entries only - and the image's own data,
; strings and scratch alike, read through `cs:`. Every routine here runs with
; the gfx lock HELD (sc_modcall's contract).

modc_e_sc:                      ; CPE_SC: AH = the operation
    or ah, ah
    jz .new
    dec ah
    jz .move
    call sc_m_del
    retf
.new:
    call sc_m_new
    retf
.move:
    call sc_m_move
    retf

; -----------------------------------------------------------------------------
; sc_m_new - CPE_SC_NEW: a Disk window's entry dropped on the bare desktop
; in:  CX, DX = the drop point; dsk_ico = the entry's 16x16 body; [fcp_cb*] =
;      its identity (the Cut fm_drag armed, which the caller has disarmed)
; out: nothing; a new shortcut on the nearest free cell and SYSTEM.CFG written,
;      or a toast saying why not
;
; THE RECORD IS FILLED BEFORE ANY I/O. dsk_ico is a shared scratch (disk.inc)
; and the claim may move across a mount, so the body is taken first and every
; access after the first far call re-reads [sc_seg] through sc_m_off.
; -----------------------------------------------------------------------------
sc_m_new:
    cmp dx, MBAR_H              ; not the bar, not the dock, not another
    jb .ret                     ; display: those are not the desktop, and a
    cmp dx, [vid_dock_y0]       ; drop there does what it always did -
    jae .ret                    ; nothing
    cmp cx, [vid_band_x0]
    jb .ret
    cmp cx, [vid_band_xe]
    jae .ret
    push cx
    push dx
    call sc_m_row               ; AL = a free zone
    pop dx
    pop cx
    jc .ret                     ; ...and the user has been told why not
    mov [cs:sc_mz], al
    mov bl, 0xFF                ; no row to leave out of the search
    call sc_m_cell              ; [cs:sc_bc] = the nearest free cell
    jc .noroom
    mov al, [cs:sc_mz]
    call sc_m_off
    mov ax, [cs:sc_bc]
    mov [es:di+SC_R_COL], ax
    mov al, [fcp_cbtype]
    cmp al, 2
    jbe .kind
    mov al, 2
.kind:
    mov [es:di+SC_R_KIND], al
    push di
    add di, SC_R_CAP            ; CAPTION and BODY are contiguous, so the two
    cld                         ; copies run on
    mov si, fcp_cbname
    mov cx, SC_CAPMAX
    rep movsb                   ; the name, as the caption until 26.8.4 says
    mov si, dsk_ico             ; otherwise...
    mov cx, 32
    rep movsw                   ; ...and the picture
    pop di
    mov al, [fcp_cbdrv]
    mov [es:di+SC_R_VOL], al    ; LIVE from here: nothing can paint it before
                                ; this returns, the lock being ours

    ; --- the path, and a package's own name: standing in the entry's folder -
    call COLD_SEG:drvf_drv_vol_bank
    mov al, [fcp_cbdrv]
    mov bx, [fcp_cbcwd]
    call COLD_SEG:fcpf_fcp_goto
    jc .bad
    mov al, [cs:sc_mz]
    call sc_m_off
    add di, SC_R_PATH
    mov cx, SC_PATHMAX - SC_CAPMAX  ; room left for `\` and the name
    call COLD_SEG:dsk_path_x    ; the folder's REAL path, which a window's
    jc .bad                     ; FS_PATH is not when it was opened part-way
    add di, cx                  ; down (it records navigation). CX = its
    cmp cx, 1                   ; length, so ES:DI = its NUL - and the root
    je .nm                      ; answers `\`, which needs no second one
    mov byte [es:di], '\'
    inc di
.nm:
    mov si, fcp_cbname
    mov cx, SC_CAPMAX
    rep movsb                   ; `\APPS\CALC.O88` (SPEC.md 26.8.1)
    mov al, [cs:sc_mz]
    call sc_m_off
    cmp byte [es:di+SC_R_KIND], 1
    jne .capx
    mov si, fcp_cbname          ; a PACKAGE is captioned with its header name
    call COLD_SEG:dwf_dskw_stat ; when that fits the cell (SPEC.md 26.8.4):
    jc .stem                    ; one sector, inside a gesture that is about
    mov ax, bx                  ; to spend several on the write
    mov cx, 32
    call COLD_SEG:sc_peek_f     ; ES:BX = the header, AX = what arrived
    jc .stem
    cmp ax, 32
    jb .stem
    cmp word [es:bx], 0x384F    ; 'O8': a package, and not a file that is
    jne .stem                   ; merely named like one
    lea si, [bx+16]
    xor cx, cx
.nlen:
    cmp byte [es:si], 0
    je .nend
    inc si
    inc cx
    cmp cx, 16
    jb .nlen
.nend:
    jcxz .stem
    cmp cx, SC_CAPMAX - 1
    ja .stem                    ; longer than the cell: the stem instead
    inc cx                      ; ...with its NUL
    lea si, [bx+16]
    mov al, [cs:sc_mz]
    push ds                     ; the kernel's DS, for after
    push es                     ; the header's segment
    call sc_m_off               ; ES:DI = the record
    pop ds                      ; DS = the header's segment
    add di, SC_R_CAP
    rep movsb
    pop ds
    jmp short .capx
.stem:
    mov al, [cs:sc_mz]          ; the 8.3 name up to its dot - CALC.O88 is
    call sc_m_off               ; CALC, which a desktop should say even where
    add di, SC_R_CAP            ; the Disk window's listing would not
.st:
    mov al, [es:di]
    or al, al
    jz .capx
    cmp al, '.'
    je .cut
    inc di
    jmp short .st
.cut:
    mov byte [es:di], 0
.capx:
    mov al, [cs:sc_mz]          ; the caption's pen, centred: it is FIXED-cell
    call sc_m_off               ; text (font_width is 8 a glyph), so its width
    xor cx, cx                  ; is its length and nothing measures it again
.cl:
    cmp byte [es:di+SC_R_CAP], 0
    je .cle
    inc di
    inc cx
    cmp cx, SC_CAPMAX - 1
    jb .cl
.cle:
    shl cx, 1
    shl cx, 1
    shl cx, 1                   ; its width
    mov ax, SC_W
    sub ax, cx
    shr ax, 1
    mov ah, al                  ; AH = the pen's offset
    mov al, [cs:sc_mz]
    call sc_m_off
    mov [es:di+SC_R_CAPX], ah
    jmp short .done
.bad:
    mov al, [cs:sc_mz]          ; the folder is gone or its path will not fit
    call sc_m_off
    mov byte [es:di+SC_R_VOL], 0xFF
    call COLD_SEG:drvf_drv_vol_back
    mov si, sc_s_path
    jmp sc_m_say
.done:
    call COLD_SEG:drvf_drv_vol_back
    mov al, [cs:sc_mz]
    call sc_m_paint
    jmp sc_m_save
.noroom:
    mov si, sc_s_room
    jmp sc_m_say
.ret:
    ret

; sc_m_say - toast one of THIS image's strings, at CS:SI
sc_m_say:
    push cs
    pop es
    xor cx, cx
    call KERNEL_SEG:cw_toast_show
    ret

; sc_m_off - AL = a zone -> ES:DI = its record. Preserves AX.
sc_m_off:
    push ax
    sub al, DESK_SC0
    mov ah, SC_REC
    mul ah
    mov di, ax
    mov es, [sc_seg]
    pop ax
    ret

; sc_m_paint - AL = a zone: repaint its rect
sc_m_paint:
    call COLD_SEG:sc_rect_f
    call KERNEL_SEG:cw_wm_paint_dmg
    ret

; sc_m_save - SYSTEM.CFG, NOW: a shortcut is meant to survive a power-off, so
; it does not wait for the panel to close. cp_flush_close_x is the panel's own
; spend - it writes, says so, and keeps [cp_wdirty] on a failure so the next
; close or Restart tries again (SPEC.md 59.6).
sc_m_save:
    mov byte [cp_wdirty], 1
    jmp cp_flush_close_x

; -----------------------------------------------------------------------------
; sc_m_kb - the table's claim, to AL KB (0 = none), with its bookkeeping
; out: CF = 0 [sc_seg]/[sc_nrows] describe it and the rows a grow added are
;      marked free; CF = 1 refused, nothing changed
; -----------------------------------------------------------------------------
sc_m_kb:
    push ax
    push bx
    push cx
    push dx
    push di
    push es
    xor ah, ah
    mov dx, [sc_seg]
    mov cx, sc_reloc            ; a NEW claim moves with its proc
    call COLD_SEG:sc_mem_f
    jc .out
    or ax, ax
    jnz .live
    xor dx, dx                  ; freed
.live:
    mov [sc_seg], dx
    mov cl, 3
    shl ax, cl                  ; the rows it holds...
    cmp ax, SC_MAX
    jbe .cap
    mov al, SC_MAX              ; ...and never more than SC_MAX
.cap:
    mov ch, [sc_nrows]          ; CH = the first row a grow adds
    mov [sc_nrows], al
.mark:
    cmp ch, al
    jae .ok
    push ax
    mov al, ch
    add al, DESK_SC0
    call sc_m_off
    mov byte [es:di+SC_R_VOL], 0xFF
    pop ax
    inc ch
    jmp short .mark
.ok:
    clc
.out:
    pop es
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; sc_m_row - a free record, growing the claim a KB if every row is taken
; out: CF = 0 and AL = its zone; CF = 1 refused, and said
; -----------------------------------------------------------------------------
sc_m_row:
    mov al, DESK_SC0
.s:
    mov ah, al
    sub ah, DESK_SC0
    cmp ah, [sc_nrows]
    jae .grow
    call sc_m_off
    cmp byte [es:di+SC_R_VOL], 0xFF
    je .got                     ; equal: CF is already 0
    inc ax
    jmp short .s
.grow:
    cmp ah, SC_MAX
    jae .full
    push ax
    mov al, ah
    shr al, 1
    shr al, 1
    shr al, 1
    inc ax                      ; a KB more than the rows in use need
    call sc_m_kb
    pop ax
    jnc .s
    mov si, fm_s_nomem          ; the Disk window's own words
    push ds
    pop es
    xor cx, cx
    call KERNEL_SEG:cw_toast_show
    stc
    ret
.full:
    mov si, sc_s_many
    call sc_m_say
    stc
.got:
    ret

; -----------------------------------------------------------------------------
; sc_m_cell - the free grid cell NEAREST a point (SPEC.md 26.8.2)
; in:  CX, DX = the point; BL = a zone to treat as absent (its own cell is
;      free to it, which is what a move wants), 0xFF for none
; out: CF = 0 and [cs:sc_bc] = the cell, a WORD in the record's own order -
;      the column, then the row; CF = 1 the grid is full
; clobbers: AX, BX, CX, DX, flags
;
; Nearest by the cell's CENTRE, in city-block pixels: the user never has to
; aim at an edge, and a drop on a taken cell lands beside it.
;
; THE GRID STOPS SHORT OF EVERY COLUMN THE DRIVE ZONES COULD REACH. They wrap
; leftwards as volumes mount (SPEC.md 26.1), so the columns DESK_NZ zones would
; need are reserved whatever is mounted now - a hard disk mounted later cannot
; land on a shortcut, and no damage pass has to reconcile the two.
; -----------------------------------------------------------------------------
sc_m_cell:
    mov [cs:sc_px], cx
    mov [cs:sc_py], dx
    mov [cs:sc_ex], bl
    mov word [cs:sc_best], 0xFFFF
    mov ax, [desk_rows]
    cmp ax, 15
    jbe .rows
    mov ax, 15
.rows:
    mov [cs:sc_nr], al
    mov cx, ax
    mov ax, DESK_NZ - 1
    add ax, cx
    xor dx, dx
    div cx                      ; AX = the drive columns DESK_NZ zones need
    dec ax
    mov cx, DESK_COLW
    mul cx
    mov dx, [vid_desk_zx]
    sub dx, ax                  ; DX = the leftmost such column's left
    sub dx, [vid_band_x0]
    sub dx, SC_X0 + SC_W + 2*DESK_ZOVER + 4
    js .none                    ; not even one column of room
    mov ax, dx
    xor dx, dx
    mov cx, SC_PX
    div cx
    inc ax
    cmp ax, 15
    jbe .cols
    mov ax, 15
.cols:
    mov [cs:sc_nc], al
    xor bx, bx                  ; BL = the column, BH = the row: BX is the
.cell:                          ; cell word itself
    call sc_m_occ
    jc .next
    mov al, bl
    mov ah, SC_PX
    mul ah
    add ax, [vid_band_x0]
    add ax, SC_X0 + SC_W / 2
    sub ax, [cs:sc_px]
    jns .xa
    neg ax
.xa:
    mov cx, ax
    mov al, bh
    xor ah, ah
    mul word [desk_zstep]
    add ax, DESK_ZY0 + SC_H / 2
    sub ax, [cs:sc_py]
    jns .ya
    neg ax
.ya:
    add ax, cx
    cmp ax, [cs:sc_best]
    jae .next
    mov [cs:sc_best], ax
    mov [cs:sc_bc], bx
.next:
    inc bh
    cmp bh, [cs:sc_nr]
    jb .cell
    xor bh, bh
    inc bl
    cmp bl, [cs:sc_nc]
    jb .cell
    cmp word [cs:sc_best], 0xFFFF
    je .none
    clc
    ret
.none:
    stc
    ret

; sc_m_occ - BX = a cell word: CF = 1 another live shortcut is on it
sc_m_occ:
    push ax
    push cx
    push di
    push es
    mov ch, [sc_nrows]
    mov cl, DESK_SC0
    or ch, ch
    jz .free
.o:
    mov al, cl
    call sc_m_off
    cmp byte [es:di+SC_R_VOL], 0xFF
    je .n
    cmp cl, [cs:sc_ex]
    je .n
    cmp bx, [es:di+SC_R_COL]
    je .occ
.n:
    inc cl
    dec ch
    jnz .o
.free:
    clc
    jmp short .out
.occ:
    stc
.out:
    pop es
    pop di
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; sc_m_move - CPE_SC_MOVE: a shortcut dragged past the threshold
; in:  AL = its zone; the button still down
;
; fm_drag's tracking loop and its outline (fm_dgxor), the outline erased
; before the lock may drop, and the drop going to the nearest free cell under
; the pointer - its own cell counting as free, so a short drag stays put.
; -----------------------------------------------------------------------------
sc_m_move:
    mov [cs:sc_mz], al
    call COLD_SEG:sc_dgmove_f
    call COLD_SEG:sc_dgxor_f    ; the outline is up from here on
.track:
    test byte [mouse_btn], 1
    jz .drop
    call COLD_SEG:sc_dgxor_f    ; erase at the old place...
    call KERNEL_SEG:cw_gfx_unlock   ; ...and only then may the lock drop
    call KERNEL_SEG:cw_task_yield
    call KERNEL_SEG:cw_gfx_lock
    call COLD_SEG:sc_dgmove_f
    call COLD_SEG:sc_dgxor_f
    mov ax, [ticks]             ; held with the outline lit (fm_drag's linger)
.l:
    call KERNEL_SEG:cw_task_yield
    cmp ax, [ticks]
    je .l
    jmp short .track
.drop:
    call COLD_SEG:sc_dgxor_f
    mov cx, [mouse_x]
    mov dx, [mouse_y]
    mov bl, [cs:sc_mz]          ; its own cell is free to it
    call sc_m_cell
    jc .ret
    mov al, [cs:sc_mz]
    call sc_m_off
    mov ax, [cs:sc_bc]
    cmp ax, [es:di+SC_R_COL]
    je .ret                     ; it went nowhere: nothing to write
    mov al, [cs:sc_mz]
    call COLD_SEG:sc_rect_f     ; the OLD rect, before the cell changes
    push ax
    push bx
    push cx
    push dx
    mov al, [cs:sc_mz]
    call sc_m_off
    mov ax, [cs:sc_bc]
    mov [es:di+SC_R_COL], ax
    pop dx
    pop cx
    pop bx
    pop ax
    call KERNEL_SEG:cw_wm_paint_dmg ; the old place, bare desktop now
    mov al, [cs:sc_mz]
    call sc_m_paint             ; ...and the new one
    jmp sc_m_save
.ret:
    ret

; -----------------------------------------------------------------------------
; sc_m_del - CPE_SC_DEL: Remove Shortcut, from any of its three routes
; in:  AL = its zone
;
; The claim gives back a KB once the rows above the highest one in use fill
; it, and goes altogether with the last - so a machine whose user removed
; every shortcut holds nothing for them.
; -----------------------------------------------------------------------------
sc_m_del:
    mov ah, al                  ; THE ROUTES DO NOT CHECK, this does: the
    sub ah, DESK_SC0            ; Delete key and the menu hand over whatever
    cmp ah, [sc_nrows]          ; the desktop's selection is, a drive's zone
    jae .ret                    ; and "none" (0xFF) included
    call sc_m_off
    cmp byte [es:di+SC_R_VOL], 0xFF
    je .ret
    mov [cs:sc_mz], al
    call COLD_SEG:sc_rect_f
    push ax
    push bx
    push cx
    push dx
    mov al, [cs:sc_mz]
    call sc_m_off
    mov byte [es:di+SC_R_VOL], 0xFF
    cmp al, [desk_sel]
    jne .ns
    mov byte [desk_sel], 0xFF
.ns:
    pop dx
    pop cx
    pop bx
    pop ax
    call KERNEL_SEG:cw_wm_paint_dmg
    mov cl, [sc_nrows]          ; the highest row still in use decides the KB
.h:
    or cl, cl
    jz .kb
    dec cl
    mov al, cl
    add al, DESK_SC0
    call sc_m_off
    cmp byte [es:di+SC_R_VOL], 0xFF
    je .h
    inc cx                      ; CL = the rows still needed
.kb:
    mov al, cl
    call .kb8
    mov ah, al
    mov al, [sc_nrows]
    call .kb8
    cmp ah, al
    jae .save
    mov al, ah
    call sc_m_kb
.save:
    jmp sc_m_save
.ret:
    ret
.kb8:                           ; AL rows -> AL KB
    add al, SC_PERKB - 1
    shr al, 1
    shr al, 1
    shr al, 1
    ret

; -----------------------------------------------------------------------------
; sc_m_ser - the shortcut TRAILER, after cpc_ser's terminator (SPEC.md 26.8.6)
; in:  ES:BX = the settings cpc_ser just built (CTRL.DRV's own buffer), CX =
;      their length
; out: CF = 0 and ES:BX, CX = what to WRITE - unchanged when there are no
;      shortcuts, else a claim of its own holding the settings, the live rows
;      verbatim and compacted, and a 4-byte footer: 'SC', its version and the
;      count. CF = 1: there are shortcuts and no room to compose them
; clobbers: ES, BX, CX (the outputs), flags
;
; The footer is read from the END, so the boot reader needs no walk of the
; records above it. NO SHORTCUTS, NO TRAILER: the file is then byte for byte
; what it was before this feature - the "costs nothing in the file when there
; is none" the ask set.
;
; A CLAIM OF ITS OWN, PINNED, for the length of the write: CTRL.DRV's bss is
; the slack in its own KB rounding (kernel.asm's MODC_BSS assertion) and two
; KB of rows do not fit there, and a buffer the write is reading must not be
; moved by a compaction the write itself triggers. sc_m_serx gives it back.
; -----------------------------------------------------------------------------
sc_m_ser:
    mov word [cs:sc_tseg], 0
    push ax
    push dx
    push si
    push di
    push es
    xor dl, dl                  ; DL = the live rows
    mov dh, [sc_nrows]
    mov al, DESK_SC0
    or dh, dh
    jz .none
.c:
    call sc_m_off
    cmp byte [es:di+SC_R_VOL], 0xFF
    je .cn
    inc dx
.cn:
    inc ax
    dec dh
    jnz .c
.none:
    pop es
    mov [cs:sc_tcnt], dl
    or dl, dl
    jz .plain                   ; none: the settings, as they are
    mov al, dl
    mov ah, SC_REC
    mul ah
    add ax, cx
    add ax, 4 + 1023
    push cx
    mov cl, 10
    shr ax, cl                  ; the KB the whole file needs
    xor cx, cx                  ; PINNED
    xor dx, dx
    call COLD_SEG:sc_mem_f      ; DX = the claim
    pop cx
    jc .out                     ; CF = 1: the caller refuses the write
    mov [cs:sc_tseg], dx
    push ds
    push es
    pop ds                      ; DS = the settings' segment
    mov es, dx
    mov si, bx
    xor di, di
    cld
    rep movsb                   ; the settings...
    pop ds
    mov ax, [sc_seg]
    mov dh, [sc_nrows]
    push ds
    mov ds, ax                  ; DS = the table: no kernel word below
    xor si, si
.r:
    cmp byte [si+SC_R_VOL], 0xFF
    je .skip
    mov cx, SC_REC
    rep movsb                   ; ...the rows...
    jmp short .nx
.skip:
    add si, SC_REC
.nx:
    dec dh
    jnz .r
    pop ds
    mov ax, 'SC'                ; ...and the footer
    stosw
    mov al, SC_VER
    stosb
    mov al, [cs:sc_tcnt]
    stosb
    mov cx, di
    xor bx, bx                  ; ES:BX = the claim, CX = the file
.plain:
    clc
.out:
    pop di
    pop si
    pop dx
    pop ax
    ret

; sc_m_serx - give sc_m_ser's claim back. CF and AX survive: the write's
; answer is in them.
sc_m_serx:
    pushf
    push ax
    push dx
    mov dx, [cs:sc_tseg]
    or dx, dx
    jz .out
    xor ax, ax
    call COLD_SEG:sc_mem_f
.out:
    pop dx
    pop ax
    popf
    ret

sc_s_room   db 'No room on the desktop', 0  ; the image's own strings: a toast
sc_s_many   db 'Too many shortcuts', 0      ; copies, and these cost the
sc_s_path   db 'Path too long', 0           ; kernel nothing (SPEC.md 2.8)

; =============================================================================
section .ovl                    ; the BOOT half (SPEC.md 2.5.1): runs once,
; =============================================================================
; from ovc_load, and costs no resident byte and no disk read - .ovl rides the
; fixed ten-sector blob (docs/plans/completed/DESKTOP-SHORTCUTS-PLAN.md 3.1).

; -----------------------------------------------------------------------------
; ovl_sc_load - SYSTEM.CFG, when it carries shortcuts (SPEC.md 26.8.6)
; in:  the boot volume mounted at its root; ovc_load's read set up in BX, CX,
;      DX, SI and ES - all preserved, so a refusal falls through into it
; out: CF = 0: the file was read whole into the shortcut claim, its settings
;      head staged in ovc_buf and AX = that head's length; the rows, if a
;      valid trailer carried any, at the claim's base. CF = 1: take ovc_load's
;      own read - the file is too small to carry a trailer, or something here
;      was refused
;
; A FILE OF CFG_FBUF OR LESS NEVER GETS PAST THE FIRST COMPARE, so a machine
; with no shortcuts boots exactly as it did, plus one dskw_stat answered out
; of the directory the mount already holds. A file bigger than that with no
; valid trailer still has its settings read: the head is staged either way,
; so a future kernel's longer file costs the shortcuts and not the settings.
; -----------------------------------------------------------------------------
ovl_sc_load:
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov si, drv_cfgname
    call COLD_SEG:dwf_dskw_stat ; DX:CX = its size
    jc .plain
    or dx, dx
    jnz .plain
    cmp cx, CFG_FBUF
    jbe .plain                  ; no room for a trailer: today's read
    cmp cx, 4096
    ja .plain                   ; nothing this kernel writes is that big
    mov di, cx                  ; DI = the size
    mov ax, cx
    add ax, 1023
    mov cl, 10
    shr ax, cl                  ; ...in KB: 3 at the most
    mov cx, sc_reloc
    call COLD_SEG:sc_mem_f      ; DX = the claim, whole-file sized
    jc .plain
    mov [sc_seg], dx
    mov cl, 3
    shl al, cl                  ; the rows it holds, at most SC_MAX
    cmp al, SC_MAX
    jbe .cap
    mov al, SC_MAX
.cap:
    mov [sc_nrows], al
    mov es, dx
    xor bx, bx
    mov cx, di
    xor dx, dx
    mov si, drv_cfgname
    call COLD_SEG:dwf_dskw_read ; AX = the bytes read
    jc .drop
    mov dx, ax                  ; DX = where the head ends: the whole file...
    xor bl, bl                  ; BL = the rows: none until the footer says
    mov di, ax
    sub di, 4
    jb .stage
    cmp word [es:di], 'SC'
    jne .stage
    cmp byte [es:di+2], SC_VER
    jne .stage
    mov bh, [es:di+3]
    mov al, bh
    dec al
    cmp al, SC_MAX              ; 1..SC_MAX, and 0 wraps to 255 and fails
    jae .stage
    mov al, bh
    mov ah, SC_REC
    mul ah
    sub di, ax                  ; DI = where the rows start
    jb .stage
    cmp di, CFG_REC0 + 2
    jb .stage
    mov dx, di                  ; ...unless a trailer is there
    mov bl, bh
.stage:
    mov cx, dx                  ; the settings head, into ovc_buf
    cmp cx, CFG_FBUF
    jbe .hc
    mov cx, CFG_FBUF
.hc:
    push cx                     ; ...which is ovc_deser's AX
    push ds
    push es
    pop ds                      ; DS = the claim
    push cs
    pop es                      ; ES = this overlay
    xor si, si
    mov di, ovc_buf
    cld
    rep movsb
    pop ds
    mov es, [sc_seg]
    or bl, bl
    jz .none
    mov al, bl                  ; the rows, down to the claim's base
    mov ah, SC_REC
    mul ah
    mov cx, ax
    push ds
    push es
    pop ds
    mov si, dx
    xor di, di
    rep movsb
    pop ds
    xor di, di                  ; every string terminated, whatever the file
    mov cl, bl                  ; said (CL = the count, CH = the row), and
    xor ch, ch                  ; every row past the count FREE
.san:
    cmp ch, cl
    jb .lv
    mov byte [es:di+SC_R_VOL], 0xFF
.lv:
    mov byte [es:di+SC_R_PATH+SC_PATHMAX-1], 0
    mov byte [es:di+SC_R_CAP+SC_CAPMAX-1], 0
    add di, SC_REC
    inc ch
    cmp ch, [sc_nrows]
    jb .san
    jmp short .done
.none:
    call .free                  ; no trailer after all: give the claim back
.done:
    pop ax                      ; the head's length
    clc
    jmp short .out
.drop:
    call .free
.plain:
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret
.free:
    xor ax, ax
    mov dx, [sc_seg]
    call COLD_SEG:sc_mem_f
    mov [sc_seg], ax
    mov [sc_nrows], al
    ret

section .modc                   ; ...and the image's own scratch, IN the
sc_mz       db 0                ; image: a module may write its own bytes
sc_px       dw 0                ; (MODULE-SELFCONTAIN-PLAN), and its bss is
sc_py       dw 0                ; only the slack in its KB rounding, which
sc_ex       db 0                ; the settings buffer already spends
sc_best     dw 0                ; sc_m_cell: the point, the zone it leaves
sc_bc       dw 0                ; out, the nearest distance so far and its
sc_nr       db 0                ; cell, and the grid's rows and columns;
sc_nc       db 0                ; sc_m_ser's claim and the rows it holds
sc_tseg     dw 0
sc_tcnt     db 0

section .text

%endif                          ; OS88_SHORTCUTS
