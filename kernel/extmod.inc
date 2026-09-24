; =============================================================================
; EXTD.DRV - the extended desktop's placement policy (SPEC.md 39.19.6), an
; on-demand module (SPEC.md 2.8) held for exactly as long as [vid_dmode] asks
; for Extend. kern_big's alone: kern_small has no second display at all.
;
; WHAT IS HERE is the half of SPEC.md 39.13-39.19 that runs on a DECISION -
; bringing display 1 up (vid_disp_init's Extend arm), where a window lands
; when it is put down on the other card or across the seam (39.16.3), which
; display a window is told it is on (39.16.4.1) and the fsx bracket's
; collapse and restore (39.18). What is NOT here is everything that runs per
; primitive, per glyph cell or inside the mouse ISR - GFXDISP, font_ch_cut,
; cur_move_multi - because a far call under every primitive of an extended
; machine is the wrong trade, and that half is generalised in place rather
; than gated anyway.
;
; THE INVARIANT: [vid_ndisp] > 1 only while this image is mounted. The one
; routine that makes it 2 is ext_extend_b below (and vid_fsx_leave, also
; here, restoring it), so it cannot happen without the image; and exf_sync
; drops the image only once the relayout has put [vid_ndisp] back to 1. Every
; kernel caller therefore either sits behind a [vid_ndisp] test it already
; had, or is content with mod_gone's CF = 1, registers preserved, as the
; one-display answer - and the kernel calls the slot straight, with EXTCALL:
; no thunk, no mod_need on the path, nothing to hook or unhook.
;
; DS = KERNEL_SEG throughout. Kernel routines are reached through the exk_*
; stubs at the foot: `push cs` + a near call builds the far frame, and the
; routine's own near `ret` lands on cw_kretf - dockmod.inc's device, so the
; image costs no resident shim. os88ovlchk refuses a near call either way
; across the boundary (its MODS list names `.modx`).
; =============================================================================
%ifdef KERN_BIG
section .cold
; -----------------------------------------------------------------------------
; exf_sync - EXTD.DRV follows [vid_dmode] (far)
; in:  [vid_dmode], [vid_ndisp]
; out: CF = 1 Extend was asked for and the image could not be had - no system
;      disk, no heap, a stamp - and [vid_dmode] is Single again, so the caller
;      owes the refusal (SPEC.md 2.8.4, 47). Registers preserved.
;
; The Control Panel's arrangement row calls it on BOTH sides of
; vid_disp_relayout: the first loads before anything moves, the second drops
; after the collapse - a DROP waits until [vid_ndisp] says the relayout has
; actually happened, which is the invariant above kept by construction. The
; boot settings reader calls it once, after SYSTEM.CFG's two arrangement bytes
; are stored and before the adapter switch that can extend (driver.inc
; drv_boot_x); a refusal there is Single, with the file left as it is.
; -----------------------------------------------------------------------------
exf_sync:
    push ax
    mov al, MOD_EXT
    cmp byte [vid_dmode], 0
    jne .need
    cmp byte [vid_ndisp], 1
    ja .out                     ; CF = 0: still extended, drop after relayout
    call mod_drop               ; (a drop of an empty row is a no-op)
    clc
    jmp short .out
.need:
    call mod_need
    jnc .out
    mov byte [vid_dmode], 0     ; MOV keeps mod_need's CF = 1
.out:
    pop ax
    retf

section .modx
EXT_NENT    equ 7
modx_hdr:
    dw 0x384F                   ; MOD_H_MAGIC
    db MOD_VER, MOD_EXT         ; MOD_H_VER, MOD_H_ID
    dw BUILD_NUM, MOD_STAMP     ; MOD_H_BUILD, MOD_H_STAMP (SPEC.md 2.8.2)
    dw modx_end, EXT_NENT       ; MOD_H_IMG, MOD_H_NENT
    dw ext_e_extend             ; EXT_EXTEND
    dw ext_e_land               ; EXT_LAND
    dw ext_e_strads             ; EXT_STRADS
    dw ext_e_apply              ; EXT_APPLY
    dw ext_e_fitbox             ; EXT_FITBOX
    dw ext_e_dispnow            ; EXT_DISPNOW
    dw ext_e_fsx                ; EXT_FSX
    times MOD_NENT - EXT_NENT dw 0

ext_e_extend:                   ; EXT_EXTEND: vid_disp_init's Extend arm.
    call ext_extend_b           ; mod_gone's CF = 1 is that routine's
    clc                         ; `jc .single`, which is the refusal path
    retf
ext_e_land:                     ; EXT_LAND: ui_drag_size with CF INVERTED -
    call ui_drag_size           ; CF = 1 NOT moved, so the resident `cmc`
    cmc                         ; after the call reads mod_gone's CF = 1 as
    retf                        ; "not moved" and the drag cache survives
ext_e_strads:                   ; EXT_STRADS: CF = 1 not straddling, which is
    call wm_strads              ; also mod_gone's answer and the one-display
    retf                        ; one
ext_e_apply:                    ; EXT_APPLY: wm_apply_wh's straddle arm, the
    call wm_strads              ; two calls in one entry. CF = 1: not
    jc .r                       ; straddling, the caller's .one
    call wm_strad_fit
    clc
.r: retf
ext_e_fitbox:                   ; EXT_FITBOX: wm_fit's box. Not loaded, the
    call wm_fit_box             ; registers come back untouched, which is the
    retf                        ; primary's box and the one-display answer
ext_e_dispnow:                  ; EXT_DISPNOW: both callers keep their
    call wm_disp_now            ; [vid_ndisp] gate
    retf
ext_e_fsx:                      ; EXT_FSX: AH = EXTF_*, the bracket's three.
    cmp ah, EXTF_LEAVE          ; No flags are read and every one is a no-op
    je .l                       ; on one display
    ja .u
    call vid_fsx_enter
    retf
.l: call vid_fsx_leave
    retf
.u: call vid_fsx_unblank
    retf

; ==== the landing and the straddle (SPEC.md 39.16.3), from wm.inc =========
; -----------------------------------------------------------------------------
; wm_land_fit - the window has been PUT DOWN: has the adapter under it changed,
;               and if so what size does it want here? (SPEC.md 39.16.3.3)
; in:       BX = the window, its rect already where the user left it
; out:      nothing; every register preserved, FLAGS INCLUDED
;
; **THE RULE IS ABOUT ADAPTER IDENTITY AND NOT ABOUT GEOMETRY**, which is the
; whole of docs/plans/completed/WINDOW-SIZING-PLAN.md 12 and the correction of everything
; above it. What a window wants is not "a size that fits the box the drag left
; me in" but "my size for adapter kind Y, and I am standing on adapter kind
; Y" - so the TRIGGER is a change of kind and nothing else. A move within one
; adapter changes no size at all, however far it goes and however much of the
; frame ends up past the bottom of the screen.
;
; Three separate mechanisms used to share this job and each produced its own
; defect. ui_drag restored the NATURAL BANK on every release, so a drag from
; one place to another inside the CGA handed the window its HERCULES size; the
; straddle cut geometrically to the rows both displays have, which is an
; arbitrary number rather than a designed one and turned Missile Command into
; a letterbox; and a landing wholly on the short display was clamped by
; nothing at all, and then (11's withdrawn 3.6) by a rule derived from the
; union's BOUNDING BOX, which reads rows no display has as a hole in the
; desktop.
;
; wm_kind_now answers the question - including the straddle, where it is the
; MORE RESTRICTIVE of the two displays, which is what makes a Hercules-to-CGA
; round trip exactly two resizes instead of four: one entering the straddle
; and one leaving it on the far side.
;
; THE SNAP AND THE HANG ARE THE SAME MECHANISM SEEN FROM TWO SIDES (12.4). A
; window whose floor beats the room has its origin moved up until the frame
; ends on the last row the display has - because a user cannot SEE a window's
; floor while dragging it, so a placement that floors out crossing a seam was
; never an informed one. A move within one adapter never reaches here, so it
; hangs, and that is informed.
;
; AND A KERNEL-INITIATED RESIZE ALWAYS ASKS (SPEC.md 11.1). wm_ask_size is put
; the size this arrives at and answers with the one the window will accept -
; per axis, so a shrink that would lose columns and not rows still gets its
; rows - and a REFUSAL means the window keeps its size and HANGS rather than
; being cropped. apps/paint is the consumer and it answers out of its own
; canvas state rather than the record, which is why the ask can follow the
; write instead of having to precede it.
; -----------------------------------------------------------------------------
wm_land_fit:
    pushf
    push ax
    push dx
    cmp byte [vid_ndisp], 1
    jbe .out                    ; one display: a drag can never change a kind
    push ax                     ; **THE DISPLAY IS DECIDED ONCE, HERE** (SPEC.md
    call wm_disp_now            ; 39.16.4.2). Armed before the first question is
    mov [wm_lf_disp], al        ; asked and spent at .fin, so the resize this
    mov [wm_lf_win], bx         ; routine applies cannot change the answer under
    pop ax                      ; the steps that follow it
    push cs
    call exk_wm_kind_now        ; **NEITHER OF THESE MAY BE BANKED IN AH.**
    mov dl, al                  ; wm_kind_was goes through wm_ptr2idx, which
    call wm_kind_was            ; answers AL = index and AH = 0, so `mov ah,al`
    cmp al, dl                  ; before it compared the banked kind against
    je .fin                     ; VID_VGA - and `push ax`/`pop ax` around it
                                ; restores AH along with AL, which is the same
                                ; bug wearing the fix's clothes. Both shipped;
                                ; the first is why a drag from one place to
                                ; another INSIDE one adapter still re-derived a
                                ; size, and the second is why a drag STRAIGHT
                                ; from one card to the other did nothing at all
                                ; (measured: AX = 0x0202 against a banked
                                ; 0x0001). DL survives both calls
    call wm_strads
    jc .land
    call wm_strad_fit           ; ...across the seam: the constrained axis
    jmp short .ask              ; ONLY, or wm_fit's x clamp would yank the frame
.land:                          ; wholly onto one display and undo the drag
    call wm_apply_size_wh
.ask:
    push cx
    push dx
    mov cx, [bx+W_W]
    mov dx, [bx+W_H]
    push cs
    call exk_wm_ask_size        ; the window's own veto (SPEC.md 11.1)
    mov [bx+W_W], cx
    mov [bx+W_H], dx
    pop dx
    pop cx
    call wm_land_snap           ; ...and the origin follows whatever it ended
    push cs
    call exk_wm_kind_bank       ; up with
    push cs
    call exk_wm_sz_notify       ; TOLD EVEN IF THE BOX DID NOT MOVE: the ADAPTER
                                ; did, and half the tree caches facts about it
                                ; (SPEC.md 11.98). wm_refit has always done this
                                ; and the drag path never did. IT IS INSIDE THE
                                ; LATCH: the handler asks OSAPI_WM_DISPLAY and
                                ; has to be told the card the kernel just sized
                                ; it for, not the one its new frame sits on
.fin:
    mov word [wm_lf_win], 0     ; ...and 0 is no window, wm_wins starting well
.out:                           ; above it
    pop dx
    pop ax
    popf
    ret

; -----------------------------------------------------------------------------
; wm_apply_size_wh - the size half of wm_apply_size, for a window the USER has
;                    just placed (SPEC.md 39.16.3.3)
; in:       BX = the window
; out:      nothing; every register preserved, FLAGS INCLUDED
;
; wm_apply_size restores the natural rect WHOLE, which is right when the screen
; changed under a window that nobody has touched and wrong the moment a hand is
; on it: the origin is the user's and only the size is in question. The third
; row of 12.5's table is here rather than in wm_fit - a window that is not
; sizable and has published nothing for this adapter is left ALONE, because the
; kernel cannot see a layout and shortening a fixed one buys nothing and costs
; a rect nothing will repaint (39.16.3.1).
; -----------------------------------------------------------------------------
wm_apply_size_wh:
    pushf
    push ax
    push cs
    call exk_wm_nat_take_wh     ; the size it ASKED for, not what a clamp left
    push cs
    call exk_wm_pref_now        ; ...or the one it published for this adapter
    jnc .fit
    call wm_reflows
    jnc .done
.fit:
    push cs
    call exk_wm_fit
.done:
    pop ax
    popf
    ret

; -----------------------------------------------------------------------------
; wm_land_snap - the origin follows the size, so a frame that will not fit from
;                where it was dropped ends ON the display's last row
; in:       BX = the window
; out:      nothing; every register preserved, FLAGS INCLUDED
;
; The floor outranks the box (11.100.2), so a window whose minimum is taller
; than the room left below the pointer cannot honour both - and this is the
; half that keeps it whole: y = min(y, limit - h), floored at the top of the
; band. A frame too tall for the band at all lands at the top and hangs down
; from there, which is the best available answer for a window that REFUSED to
; shrink (apps/paint with a picture in it): nothing is cropped and as much of
; it as the display has is on screen.
;
; The limit is the nearer of the two far edges while the frame straddles, and
; the landing display's own otherwise. wm_fit already did this once with the
; pre-ask size; it is done again because the ask may have given the height
; back.
; -----------------------------------------------------------------------------
wm_land_snap:
    pushf
    push ax
    push cx
    push dx
    push si
    push di
    push bp
%ifdef DOCK_OPT
    mov ax, [vid_band_x0]       ; the NEAR edges of the display it is on -
    mov cx, [vid_band_xe]       ; MBAR_H on the primary and the card's own vy
%else
    xor ax, ax                  ; the NEAR edges of the display it is on -
    mov cx, [vid_pw]            ; MBAR_H on the primary and the card's own vy
%endif
    mov si, MBAR_H              ; anywhere else, since nothing but the primary
    mov di, [vid_dock_y0]       ; has a menu bar (39.16.2). ui_ylow answers the
    mov dx, [vid_ph]            ; same question and may not be used: it reads
    call wm_fit_box             ; the DRAG's proposed x, which is meaningless
    mov bp, si                  ; on the ui_grow path
    push ax                     ; ...both banked, DX being about to be the axis
    call wm_sf_axis             ; DL = the constrained axis
    call wm_sf_lim              ; SI = one past the last row (column) available
    pop ax
    or dl, dl
    jz .x
    mov cx, si
    sub cx, [bx+W_H]
    cmp [bx+W_Y], cx
    jle .yfl
    mov [bx+W_Y], cx            ; may go NEGATIVE for a frame taller than the
.yfl:                           ; band, and the floor below takes it straight
    cmp [bx+W_Y], bp            ; back - which is the REFUSAL case landing at
    jge .done                   ; the top and hanging down from there
    mov [bx+W_Y], bp
    jmp short .done
.x:
    mov cx, si
    sub cx, [bx+W_W]
    cmp [bx+W_X], cx
    jle .xfl
    mov [bx+W_X], cx
.xfl:
    cmp [bx+W_X], ax
    jge .done
    mov [bx+W_X], ax
.done:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    popf
    ret

; -----------------------------------------------------------------------------
; wm_sf_axis - DL = 1 the displays tile SIDE BY SIDE (y is what has to come
;              in), 0 STACKED (x does)
; out:      DL; every other register preserved
; clobbers: DL, flags
;
; Side by side (39.19.2's Right) they are contiguous in x and overlap in y - so
; spanning x is the whole point of extending and must stay free, while y is
; what has to come in. Stacked (Below) it is the other way round. The test is
; geometric rather than a read of [vid_dlay]: display 1's VY against display
; 0's height, display 0 being at the virtual origin by construction.
; -----------------------------------------------------------------------------
wm_sf_axis:
    push ax
    mov ax, [vid_ctx + VID_CTX_SZ + VID_CTX_VY]
    cmp ax, [vid_ctx + VID_CTX_CH]
    mov dl, 1                   ; the MOV writes no flags, so the cmp decides
    jb .out
    xor dl, dl
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; wm_sf_lim - SI = one past the last row (column) BOTH displays have
; in:       DL = the axis, from wm_sf_axis; BX = the window
; out:      SI; every other register preserved
; clobbers: SI, flags
;
; The nearer of the two far edges while the frame straddles, and the display
; the window is ON otherwise - so this one routine bounds a straddle and a
; landing alike.
; -----------------------------------------------------------------------------
wm_sf_lim:
    push ax
    push di
    call wm_strads
    jc .own
    xor al, al
    push cs
    call exk_vid_ctx_ptr
    call wm_sf_far
    mov si, ax
    mov al, 1
    push cs
    call exk_vid_ctx_ptr
    call wm_sf_far
    cmp ax, si
    jae .out
    mov si, ax
    jmp short .out
.own:
    push bx
    mov ax, [bx+W_X]
    mov bx, [bx+W_Y]
    push cs
    call exk_vid_disp_of
    pop bx
    push cs
    call exk_vid_ctx_ptr
    call wm_sf_far
    mov si, ax
.out:
    pop di
    pop ax
    ret

; -----------------------------------------------------------------------------
; wm_strads - does this window's frame reach BOTH displays?
; in:       BX = the window
; out:      CF = 0 it straddles, CF = 1 it does not (a one-display machine
;           included); every register preserved
; clobbers: flags
; -----------------------------------------------------------------------------
wm_strads:
    push ax
    push di
    cmp byte [vid_ndisp], 1
    jbe .no
    xor al, al
    push cs
    call exk_vid_ctx_ptr
    call wm_sf_reach
    jc .no
    mov al, 1
    push cs
    call exk_vid_ctx_ptr
    call wm_sf_reach
    jc .no
    pop di
    pop ax
    clc
    ret
.no:
    pop di
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; wm_strad_fit - a window across the seam takes the size for the MORE
;                RESTRICTIVE of the two displays (SPEC.md 39.16.3)
; in:       BX = the window, known to straddle and known to have changed kind
; out:      nothing; every register preserved, FLAGS INCLUDED
;
; WHAT IS WRONG WITH A STRADDLING WINDOW is not the straddle - SPEC.md 39.14's
; split draws one fragment per display and that works. It is that the virtual
; desktop is a UNION and not a rectangle (39.2.1), so beyond the seam the two
; displays stop agreeing about which rows exist: a 720x348 Hercules beside a
; 640x200 CGA leaves rows 220..347 present on the left and absent on the
; right. A window tall enough to use them, dragged until its right-hand edge
; is over the CGA, has its bottom-right corner in the DEAD ZONE - drawn
; nowhere, clickable nowhere, and containing whatever the app put there.
;
; **THE SIZE COMES FROM THE ADAPTER AND THE CLAMP MERELY BOUNDS IT.** This
; routine used to do only the second half, which is why it produced a number
; nobody had designed: the size it arrived at was whatever the geometry left,
; so a game whose playfield IS its rules came out a letterbox. Now the natural
; size or the published preference is taken FIRST, and the clamp is what stops
; the answer reaching into the dead zone.
;
; IT NEVER MOVES THE ORIGIN - wm_land_snap owns that, after the window has had
; its say about the size. "The more restrictive size" is a statement about
; size.
;
; AND IT ONLY SHORTENS A WINDOW THAT WILL LAY ITSELF OUT AGAIN (39.16.3.1).
; The frame is not the pixels: the gfx primitives clip to the SCREEN and not
; to a window (SPEC.md 11.3), so a fixed layout drawn against remembered
; offsets puts exactly the same pixels on the glass whatever this writes into
; W_H - the rows below the shortened frame are still drawn, they are simply no
; longer inside anything the window manager thinks the window owns. So the
; shrink buys nothing at all there and costs a rect nothing will ever repaint.
; wm_reflows is the question, and it is a NARROWER question than it was: an
; 11.98 handler means "tell me when my box moved", not "you may pick any box
; for me" (12.5), so a non-sizable window opts in by PUBLISHING A PREFERENCE
; instead - a promise about three boxes rather than about every box.
; -----------------------------------------------------------------------------
wm_strad_fit:
    pushf
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    push cs
    call exk_wm_nat_take_wh     ; the size it ASKED for...
    push cs
    call exk_wm_pref_now        ; ...or the one it published for this adapter
%ifndef NOSIZESNAP
    pushf                       ; ...AND BACK ONTO A BYTE BOUNDARY (SPEC.md
    mov ax, [bx+W_W]            ; 39.16.3.4). Both calls above hand back an ASK
    push cs
    call exk_wm_snap_w          ; - a bank holds what the window wanted, never
    mov [bx+W_W], ax            ; a snap - so the width that arrives here is
    popf                        ; 11.94.5-unrounded. Every other path that
%endif                          ; settles a size ends in wm_snap_win; this one
                                ; deliberately does not call wm_fit, which is
                                ; how it inherited the clamp and not the snap
                                ; and landed a straddling Disk window 2px thin.
                                ; BEFORE the clamp, so that a STACKED straddle
                                ; can still narrow x afterwards - rounding up
                                ; after an x clamp hands back dead zone. The
                                ; pushf/popf is wm_pref_now's CF, which the
                                ; jnc below owes
    jnc .clamp
%ifndef STRAD_ALL               ; ...and `make STRAD=all` is the A/B: no test,
    call wm_reflows             ; so every straddling window is shortened,
    jnc .done                   ; which is exactly what 39.16.3.1 reports
%endif                          ; rather than an imitation of it
.clamp:
    call wm_sf_axis             ; DL = the axis that has to come in
    call wm_sf_lim              ; SI = one past the last row (column) both
                                ; displays have
    or dl, dl
    jz .limx

    ; --- y: the rows available from where the window stands -----------------
    mov cx, si
    sub cx, [bx+W_Y]
    jg .yroom
    xor cx, cx
.yroom:
    cmp [bx+W_H], cx
    jbe .yfl
    mov [bx+W_H], cx
.yfl:
    mov ax, si                  ; ...and the floor cannot be cut through. The
    sub ax, MBAR_H              ; cap is the limit less the TOP OF THE BAND
    push cs
    call exk_wm_min_ax          ; rather than less W_Y, which is what makes it
    cmp [bx+W_H], ax            ; provable: a frame that big can only start at
    jae .done                   ; the top, and wm_land_snap floors it there
    mov [bx+W_H], ax
    jmp short .done

    ; --- x: the same, for displays that tile vertically ---------------------
.limx:
    mov cx, si
    sub cx, [bx+W_X]
    jg .xroom
    xor cx, cx
.xroom:
    cmp [bx+W_W], cx
    jbe .xfl
    mov [bx+W_W], cx
.xfl:
    mov ax, si
    push cs
    call exk_wm_min_ax
    cmp [bx+W_W], ax
    jae .done
    mov [bx+W_W], ax
.done:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    popf
    ret

; -----------------------------------------------------------------------------
; wm_sf_far - DI = a display record: one past its last row, or column
; in:       DI = the record, DL != 0 = the y axis / 0 = the x axis
; out:      AX = the far edge, in VIRTUAL coordinates
; clobbers: AX, flags
; -----------------------------------------------------------------------------
wm_sf_far:
    or dl, dl
    jz .x
    mov ax, [di+VID_CTX_VY]
    add ax, [di+VID_CTX_CH]
    ret
.x:
    mov ax, [di+VID_CTX_VX]
    add ax, [di+VID_CTX_CW]
    ret

; -----------------------------------------------------------------------------
; wm_sf_reach - does window BX's frame overlap the display DI describes?
; in:       BX = the window, DI = the display record
; out:      CF = 0 it overlaps, CF = 1 it does not
; clobbers: AX, flags - CX and DX are LIVE in the caller
; -----------------------------------------------------------------------------
wm_sf_reach:
    push cx
    mov ax, [di+VID_CTX_VX]
    mov cx, [bx+W_X]
    add cx, [bx+W_W]
    cmp cx, ax
    jbe .no                     ; wholly left of it
    add ax, [di+VID_CTX_CW]
    cmp [bx+W_X], ax
    jae .no                     ; wholly right of it
    mov ax, [di+VID_CTX_VY]
    mov cx, [bx+W_Y]
    add cx, [bx+W_H]
    cmp cx, ax
    jbe .no                     ; wholly above it
    add ax, [di+VID_CTX_CH]
    cmp [bx+W_Y], ax
    jae .no                     ; wholly below it
    pop cx
    clc
    ret
.no:
    pop cx
    stc
    ret

; -----------------------------------------------------------------------------
; wm_reflows - will this window DRAW ITSELF INTO a box the kernel shortens?
;              (SPEC.md 39.16.3.1)
; in:       BX = the window
; out:      CF = 1 yes, it re-derives its layout from the live content box;
;           CF = 0 no, so its height is not to be reduced. Every register
;           preserved.
;
; THE KERNEL CANNOT SEE A LAYOUT, so it can only ask what the window has
; already said, and two things say it. WF_SIZABLE is a grow box, which moves
; the content box on the user's whim - an app that takes one has no choice but
; to lay out from the live one, and every one in this tree does (apps/telnet
; says so in as many words). SPEC.md 11.98's size-CHANGED handler is the other
; and covers the app that is NOT resizable and still follows: apps/calc is not
; sizable at all and re-folds its history pane on the notice, which is exactly
; the case this rule must not throw away.
;
; WF_KEEPH OUTRANKS BOTH, because it is the window saying the opposite in the
; first person (SPEC.md 11.93) - and apps/browser is both sizable and KEEPH,
; so the order is not academic.
;
; It is a question about the WINDOW and not about the geometry, so it is asked
; before any of wm_strad_fit's arithmetic: the cheapest way to not shorten a
; window is to not work out by how much.
; -----------------------------------------------------------------------------
wm_reflows:
    test byte [bx+W_FLAGS], WF_KEEPH
    jnz .no                     ; "not the kernel's to reduce" - and it is the
                                ; FIRST test for browser's sake, which is
                                ; sizable AND keeps its height
    test byte [bx+W_FLAGS], WF_SIZABLE
    jz .no
    stc
    ret
.no:
    clc
    ret

; -----------------------------------------------------------------------------
; wm_fit_box - the box for the display this window's ORIGIN is on
;              (SPEC.md 39.16.1)
; in:       BX = the window; AX/CX/SI/DI/DX = the primary's box and hard floor
; out:      the same five, for that display
; clobbers: AX, CX, DX, SI, DI, flags
;
; The ORIGIN and not the centre, deliberately: wm_disp_of's centre test is for
; deciding which monitor an app OWNS (docs/plans/completed/DUAL-DISPLAY-PLAN.md 6.5.1), and
; this is deciding which edges a frame may not pass - which is a question
; about the corner the clamps are written from. A window whose origin is in
; the dead zone gets the primary, the only answer that cannot leave it
; unreachable.
;
; DX IS AN OUTPUT TOO (SPEC.md 11.93), and it is the reason the display index
; is banked on the stack rather than kept in DL: this used to preserve DX, and
; the caller's fifth number is the bottom a window that will not fit the band
; may hang down to. On a secondary that IS ye, there being no dock to hang
; over; on the primary it is [vid_ph], the number already loaded.
; -----------------------------------------------------------------------------
wm_fit_box:
    cmp byte [vid_ndisp], 1
    jbe .out
    push bx
    mov ax, [bx+W_X]
    mov bx, [bx+W_Y]
    push cs
    call exk_vid_disp_of        ; AL = the display holding the origin
    push ax                     ; ...banked: DX is an output now
    mov dl, al
    push cs
    call exk_vid_ctx_ptr        ; DI = its record
    mov ax, [di+VID_CTX_VX]
    mov cx, ax
    add cx, [di+VID_CTX_CW]
    mov si, [di+VID_CTX_VY]
    add si, [di+VID_CTX_CH]     ; ...ye first, while DI is still the record
    push si
    mov si, [di+VID_CTX_VY]
    pop di                      ; DI = ye, SI = y0
    mov dx, di                  ; a secondary's hard floor is its own bottom
    pop ax
    or al, al
    jnz .done                   ; a secondary has no menu bar and no dock, so
    mov si, MBAR_H              ; its whole height is desktop
    mov di, [vid_dock_y0]
    mov dx, [vid_ph]            ; ...and the primary's floor is its own height
%ifdef DOCK_OPT
    mov ax, [vid_band_x0]       ; ...and its band's x extent, which a strip on
    mov cx, [vid_band_xe]       ; a side narrows (SPEC.md 30.5)
%endif
.done:
    pop bx
.out:
    ret

; -----------------------------------------------------------------------------
; wm_disp_now - WHICH DISPLAY IS THIS WINDOW'S? (SPEC.md 39.16.4.1)
; in:       BX = the window
; out:      AL = the display index; every other register preserved
; clobbers: AX, flags
;
; **ONE ANSWER, because two of them disagreed and the field found it.** A
; straddling window is SIZED for the more restrictive of the two displays
; (WINDOW-SIZING-PLAN 12.2) and was TOLD about the one its origin sits on - so
; the Task Manager straddling a Hercules and a CGA was handed the CGA's frame
; and the Hercules' geometry, worked out that one column fits, and stayed one
; column in a window twice that wide. Both callers come here now.
;
; Not straddling - or in the dead zone, where nothing does - the origin is the
; only answer that cannot leave a window unreachable (39.17).
; -----------------------------------------------------------------------------
wm_disp_now:
    cmp [wm_lf_win], bx         ; **A LANDING DECIDES THIS ONCE** (SPEC.md
    jne .ask                    ; 39.16.4.2): wm_land_fit arms the latch with
    mov al, [wm_lf_disp]        ; the answer it acted on, because the RESIZE it
    ret                         ; then applies can stop the straddle being
.ask:                           ; true - and every step after it re-derived
    push bx                     ; the answer from the new geometry
    push dx
    call wm_strads
    jc .one
    call wm_sf_axis             ; DL = the axis they tile on
    call wm_disp_rest           ; ...and AL = the MORE RESTRICTIVE of the two
    jmp short .out
.one:
    mov ax, [bx+W_X]
    mov bx, [bx+W_Y]
    push cs
    call exk_vid_disp_of
.out:
    pop dx
    pop bx
    ret

; -----------------------------------------------------------------------------
; wm_disp_rest - which of the two displays is the MORE RESTRICTIVE?
; in:       DL = the axis, from wm_sf_axis
; out:      AL = 0 or 1, the display index; every other register preserved
; clobbers: AX, flags
;
; A STRADDLING WINDOW READS AS THE SMALLER CARD, which is what makes the seam
; one transition in each direction rather than two: dragging on from the
; straddle to the small display is then not a change of kind at all, so
; nothing resizes twice (WINDOW-SIZING-PLAN 12.2).
;
; The comparison is the USABLE BAND and not the raw extent, because the
; primary carries the menu bar and the dock and a secondary carries neither -
; a 348-row Hercules primary offers 304 rows where a 348-row secondary would
; offer 348. A tie goes to the primary, which is where windows are born.
; -----------------------------------------------------------------------------
wm_disp_rest:
    push cx
    push di
    mov al, 1
    push cs
    call exk_vid_ctx_ptr        ; (preserves AX and DX)
    or dl, dl
    jz .x
    mov cx, [vid_dock_y0]
    sub cx, MBAR_H
    cmp [di+VID_CTX_CH], cx
    jb .one
    jmp short .zero
.x:
%ifdef DOCK_OPT
    mov cx, [vid_band_xe]       ; the primary's USABLE width (SPEC.md 30.5)
    sub cx, [vid_band_x0]
%else
    mov cx, [vid_pw]
%endif
    cmp [di+VID_CTX_CW], cx
    jb .one
.zero:
    xor al, al
    jmp short .out
.one:
    mov al, 1
.out:
    pop di
    pop cx
    ret

; -----------------------------------------------------------------------------
; wm_kind_was - AL = the adapter kind this window was last SIZED for
; in:  BX = window ptr
; out: AL = a VID_* kind; every other register preserved
; clobbers: AX, flags
; -----------------------------------------------------------------------------
wm_kind_was:
    mov al, [bx+W_PKIND]
    ret
; ==== the drop (SPEC.md 11.100.3/.4), from ui.inc =========================
; -----------------------------------------------------------------------------
; ui_drag_size - what size should a dropped window have? (SPEC.md 11.100.3/.4)
; in:       BX = the window, W_X/W_Y already clamped to where it was dropped
; out:      CF = 1 if W_W or W_H changed, CF = 0 if neither did. Every register
;           preserved. (EXT_LAND hands the kernel the INVERSE - see ext_e_land.)
;
; TWO THINGS, and they are for the two halves of the tree. Every window gets
; 11.100.3: the size it WANTS comes back out of the natural bank, so the clamps
; below re-derive from that rather than from whatever the last drag's clamp
; left behind - which is what makes a walk across the seam and home again
; reversible instead of costing sixty rows a trip.
;
; A window WITHOUT a grow box also gets 11.100.4: landing wholly on a display of
; a different adapter takes its own declared size for that adapter. One WITH a
; grow box does not, and that is the rule rather than an optimisation - its
; size is one the user chose, and a user outranks an application.
;
; The straddle test is why this is not simply "the kind changed": a frame still
; over both cards belongs to 39.16.3, and a preference applied there would be
; cut by it in the same breath.
; -----------------------------------------------------------------------------
ui_drag_size:
    push ax
    push cx
    push dx
    mov cx, [bx+W_W]            ; what it had, so the answer is a comparison
    mov dx, [bx+W_H]            ; rather than a promise
    push si
    push di
    mov si, [bx+W_X]            ; ...and the ORIGIN too, because wm_land_snap
    mov di, [bx+W_Y]            ; can move a window that kept its size
    call wm_land_fit            ; ONE question: has the adapter changed, and if
                                ; so what size does this window want here?
                                ; (docs/plans/completed/WINDOW-SIZING-PLAN.md 12)
    cmp si, [bx+W_X]
    jne .moved2
    cmp di, [bx+W_Y]
.moved2:
    pop di
    pop si
    jne .moved
    cmp cx, [bx+W_W]
    jne .moved
    cmp dx, [bx+W_H]
    jne .moved
    pop dx
    pop cx
    pop ax
    clc
    ret
.moved:
    pop dx
    pop cx
    pop ax
    stc
    ret
; ==== bringing display 1 up (SPEC.md 39.13, 39.19), from vidsel.inc ========
; -----------------------------------------------------------------------------
; ext_extend_b - vid_disp_init's Extend arm: set the second card's mode, bank
;                it as display 1, place it Right or Below, and make the
;                desktop the union
; in:  AL = the other display's adapter kind, AH = the primary's (vid_disp_init
;      .paired's registers, which the far call leaves as they were)
; out: [vid_ndisp] = 2. The ONLY place it becomes 2 - the invariant this image
;      exists on (see the top of this file)
; -----------------------------------------------------------------------------
ext_extend_b:
    mov [vid_kind], al
    push cs
    call exk_vid_apply          ; the live block is the SECONDARY's now...
    push cs
    call exk_vid_setmode        ; ...which is what points this at the right
                                ; card, and what makes its 32KB/16KB clear
                                ; land on the right memory
    mov al, 1
    push cs
    call exk_vid_ctx_capture    ; bank it as display 1

    mov [vid_kind], ah          ; ...and back. No vid_setmode: the primary is
    push cs
    call exk_vid_apply          ; already in its mode with the splash on it
    push cs
    call exk_vid_equip          ; 40:10 back to the primary's KIND, because
                                ; vid_setmode's CGA path flipped it to colour
                                ; and nothing else ever would (SPEC.md 39.11.2)
    xor al, al
    push cs
    call exk_vid_ctx_capture    ; a no-op today - vid_apply has just republished
                                ; what vid_ctx_init banked - and 39.12's rule
                                ; followed mechanically rather than reasoned
                                ; about one instance at a time

    mov al, 1                   ; --- and WHERE display 1 sits (SPEC.md 39.19.2)
    push cs
    call exk_vid_ctx_ptr        ; The primary is at the origin either way, so
                                ; one of the two words is 0 and the other is
                                ; the primary's own extent - which vid_apply
                                ; has just republished into the live block.
                                ; Each arm writes BOTH words, so there is no
                                ; pre-zero: the RIGHT arm overwrote it in both
    cmp byte [vid_dlay], VID_L_BELOW
    je .below
    mov ax, [vid_cw]
    mov [di+VID_CTX_VX], ax
    mov ax, MBAR_H                    ; ...AND ITS TOP ROW IS THE DESKTOP'S,
                                      ; not the screen's (SPEC.md 39.19.3).
                                      ; The second monitor carries no menu
                                      ; bar, so aligning its row 0 with the
                                      ; primary's row 0 spends the first
                                      ; MBAR_H of it on a band no straddling
                                      ; window may enter - 20 of a CGA's 200
                                      ; rows, 10%. Aligning it with the
                                      ; DESKTOP BAND instead gives those rows
                                      ; back and costs nothing: the dead zone
                                      ; moves from below the card to above it
                                      ; and does not grow, mou_clamp is
                                      ; written against the union rather than
                                      ; against a rectangle (39.15.4), and
                                      ; ui_ylow already reads this very word
    jmp short .placed
.below:
    mov word [di+VID_CTX_VX], 0
    mov ax, [vid_ch]
.placed:
    mov [di+VID_CTX_VY], ax

    mov byte [vid_cur], 0       ; the live block is display 0's again
    mov byte [vid_ndisp], 2
    push cs
    call exk_vid_desk_union     ; ...and the DESKTOP is both of them now
    ret
; ==== the fsx bracket (SPEC.md 39.18), from vidsel.inc =====================
; -----------------------------------------------------------------------------
; vid_fsx_enter - one display, and the others dark (SPEC.md 39.18)
;
; in:       AL = the display the bracket runs on
; out:      the machine describes itself as having ONE display, that one, at
;           the virtual origin; every other card is blanked
; clobbers: flags
;
; INSIDE A BRACKET THE MACHINE IS SINGLE-DISPLAY AGAIN, and that is the whole
; design: every SPEC.md 53 contract - fsx_mode, the FSI block, fsx_wait,
; FSXF_KEEPWORKER, FSXF_FASTTICK - is then exactly what it is today, and no
; fsx app needs a line.
;
; [vid_kind] MOVES TO THAT DISPLAY'S ADAPTER, which is what makes it work
; rather than merely look right: fsx_caps, fsx_mode and vid_setmode all read
; it, and vid_apply then republishes the live block, the desktop words and
; 39.16's chrome extent from vid_tab - one call, no second opinion.
;
; The others are BLANKED because nothing can maintain them: the kernel does
; not run inside the bracket (53.1), so what a live card would show is a
; frozen desktop. 39.11.4's argument, unchanged.
; -----------------------------------------------------------------------------
vid_fsx_enter:
    cmp byte [vid_ndisp], 1
    jbe .out                    ; one display: nothing here applies
    push ax
    push cx
    push di
    mov [fsx_vdisp], al
    mov cl, [vid_kind]
    mov [fsx_vkind], cl         ; the DESKTOP's adapter, to come back to
    mov cl, [vid_ndisp]
    mov [fsx_vndisp], cl

    xor ch, ch                  ; ...dark every card but the bracket's
.blank:
    cmp ch, al
    je .bnext
    push ax
    mov al, ch
    push cs
    call exk_vid_kind_of
    push cs
    call exk_vid_blank_kind
    pop ax
.bnext:
    inc ch
    cmp ch, cl
    jb .blank

    push cs
    call exk_vid_kind_of        ; ...and become that one
    mov [vid_kind], al
    push cs
    call exk_vid_apply          ; the live block, the desktop words and the
                                ; chrome, all of it that display's
    xor ax, ax                  ; consistent with the lie: one display, and
    mov [vid_cur], al           ; it is at the virtual origin. Through AX: the
    mov [vid_ox], ax            ; accumulator forms are 3 bytes where
    mov [vid_oy], ax            ; `mov byte [m],imm8` is 5 and
    inc ax                      ; `mov word [m],imm16` is 6. AL is spent - its
    mov [vid_ndisp], al         ; last reader was the vid_kind_of above and the
    pop di                      ; caller's AX is on the stack
    pop cx
    pop ax
.out:
    ret

; -----------------------------------------------------------------------------
; vid_fsx_leave - the desktop's geometry back (SPEC.md 39.18)
; in:       nothing
; out:      the union, the primary's chrome, the records unchanged
; clobbers: flags
;
; The records were never written inside the bracket, so this is vid_apply on
; the desktop's own adapter plus 39.16's union - and NOT an unblank, which
; owes the repaint first (39.18.1).
; -----------------------------------------------------------------------------
vid_fsx_leave:
    cmp byte [fsx_vndisp], 1
    jbe .out
    push ax
    mov al, [fsx_vkind]
    mov [vid_kind], al
    push cs
    call exk_vid_apply
    push cs
    call exk_vid_equip          ; 40:10 BACK TO THE PRIMARY'S KIND, because a
                                ; bracket on a COLOUR second display left it
                                ; saying colour: vid_text's own arm flips it so
                                ; that the ROM's mode set - and SPEC.md 96.33's
                                ; teletype under it - reach the card the app is
                                ; on (SPEC.md 39.19.4.1). vid_disp_init's
                                ; .extend arm is this same three-call pattern
                                ; for the same reason, and leaving the flag is
                                ; what SPEC.md 39.20's Restart then reads
    mov al, [fsx_vndisp]
    mov [vid_ndisp], al
    mov byte [vid_cur], 0
    push cs
    call exk_vid_desk_union
%ifdef DOCK_OPT
    push cs
    call exk_dock_band          ; ...and the strip where the user put it (30.5)
%endif
    pop ax
.out:
    ret

; -----------------------------------------------------------------------------
; vid_fsx_unblank - the dark monitors back, AFTER the repaint (SPEC.md 39.18.1)
; in:       nothing
; out:      every card lit again; [fsx_vndisp] spent
; clobbers: flags
;
; AFTER wm_paint_all AND NOT BEFORE IT. Blanking gates the video SIGNAL and
; not memory, so a blanked card's framebuffer still holds the desktop as it
; was when the bracket started - minutes stale, on a monitor the user has not
; been looking at. Unblanking first shows that frame and then paints over it;
; repainting first means the card is only ever shown what is current.
; -----------------------------------------------------------------------------
vid_fsx_unblank:
    cmp byte [fsx_vndisp], 1
    jbe .out
    push ax
    push cx
    push di
    mov cl, [fsx_vndisp]
    mov byte [fsx_vndisp], 1    ; one-shot: a bracket that set no mode and a
    xor ch, ch                  ; second restore must not write these ports
.d:
    cmp ch, [fsx_vdisp]
    je .next
    mov al, ch
    push cs
    call exk_vid_kind_of
    push cs
    call exk_vid_unblank_kind
.next:
    inc ch
    cmp ch, cl
    jb .d
    pop di
    pop cx
    pop ax
.out:
    ret

; kernel routines this image calls (dockmod.inc's dkk_* device)
exk_kretf: dw cw_kretf
exk_dock_band:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:dock_band
exk_vid_apply:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:vid_apply
exk_vid_blank_kind:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:vid_blank_kind
exk_vid_ctx_capture:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:vid_ctx_capture
exk_vid_ctx_ptr:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:vid_ctx_ptr
exk_vid_desk_union:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:vid_desk_union
exk_vid_disp_of:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:vid_disp_of
exk_vid_equip:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:vid_equip
exk_vid_kind_of:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:vid_kind_of
exk_vid_setmode:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:vid_setmode
exk_vid_unblank_kind:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:vid_unblank_kind
exk_wm_ask_size:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:wm_ask_size
exk_wm_fit:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:wm_fit
exk_wm_kind_bank:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:wm_kind_bank
exk_wm_kind_now:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:wm_kind_now
exk_wm_min_ax:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:wm_min_ax
exk_wm_nat_take_wh:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:wm_nat_take_wh
exk_wm_pref_now:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:wm_pref_now
exk_wm_snap_w:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:wm_snap_w
exk_wm_sz_notify:
    ; STKBALANCE-NET: -1
    push word [cs:exk_kretf]
    jmp KERNEL_SEG:wm_sz_notify
section .text
%endif
