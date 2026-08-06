; =============================================================================
; fsx.inc - fullscreen exclusive (SPEC.md 53)
;
; The app borrows the machine: fsx_run is a BRACKET, not a latch - it is
; called from a window callback (UI task, gfx lock held) and does not return
; until the app's exclusive main does. While it runs, sch_switch passes only
; this task, its kept worker and TF_SERVICE workers (SPEC.md 53.2 - the
; whitelist lives in sched.inc, armed through [fsx_task]/[fsx_worker]); the
; held gfx lock keeps the mouse ISR off the screen; and the video mode is
; the app's to change through fsx_mode. The kernel never runs while the mode
; is foreign, because the kernel is parked on the stack underneath the app.
;
; The [vid_*] live block is never touched here: it keeps describing the
; DESKTOP mode, and the FSI info block is the app's only description of the
; foreign one. Restore is therefore vid_setmode + one wm_paint_all, and
; nothing kernel-side needs undoing.
; =============================================================================

; --- mode ids (SPEC.md 53.4; mirrored in apps/os88api.inc) -------------------
FSXM_TEXT80 equ 0               ; 80x25 text        VGA CGA HERC (vid_text)
FSXM_TEXT40 equ 1               ; 40x25 text        VGA CGA      (mode 01h)
FSXM_CGA320 equ 2               ; 320x200x4         VGA CGA      (mode 04h)
FSXM_CGA640 equ 3               ; 640x200x2         VGA CGA      (mode 06h)
FSXM_HERC   equ 4               ; 720x348 mono              HERC (vid_setmode)
FSXM_VGA0D  equ 5               ; 320x200x16 planar VGA          (mode 0Dh)
FSXM_VGA13  equ 6               ; 320x200x256       VGA          (mode 13h)
FSXM_VGA12  equ 7               ; 640x480x16        VGA          (mode 12h)
FSXM_MODEX  equ 8               ; 320x240x256       VGA  (13h + unchain/retime)
FSXM_COUNT  equ 9

FSXF_KEEPWORKER equ 1           ; fsx_run CX bit 0 (SPEC.md 53.2)

; --- the info block fsx_mode fills (SPEC.md 53.4) ----------------------------
FSI_SEG    equ 0                ; word: framebuffer segment
FSI_W      equ 2                ; word: width  - pixels; COLUMNS in text
FSI_H      equ 4                ; word: height - pixels; ROWS in text
FSI_STRIDE equ 6                ; word: bytes per row (text: per char row)
FSI_FLAGS  equ 8                ; byte: FSIF_*
FSI_BPP    equ 9                ; byte: bits per pixel (text: 0)
FSI_BANKS  equ 10               ; byte: interleaved banks (1 = linear)
FSI_PAGES  equ 11               ; byte: display pages
FSI_BSTEP  equ 12               ; word: bank step bytes (0 when linear)
FSI_MODE   equ 14               ; byte: the FSXM_* id, echoed back
FSI_RSVD   equ 15               ; byte: 0
FSI_SIZE   equ 16

FSIF_TEXT   equ 1
FSIF_PLANAR equ 2
FSIF_BANKED equ 4

; -----------------------------------------------------------------------------
; fsx_caps - which FSXM ids the live adapter can set (SPEC.md 53.8, 0x02B8)
;
; in:       nothing
; out:      AX = bitmask (bit n = FSXM id n settable), DL = [vid_kind]; CF=0
; clobbers: nothing else. Any context, lock held or not (the osapi_video
;           precedent) - an app greys its mode menu with this per SPEC.md 47,
;           and fsx_mode refuses with the same bit, one predicate for both.
; -----------------------------------------------------------------------------
fsx_caps:
    push bx
    mov dl, [vid_kind]
    mov bl, dl
    xor bh, bh
    shl bx, 1
    mov ax, [bx+fsx_capstab]
    pop bx
    clc
    ret

fsx_capstab:                    ; indexed by VID_* (VGA 0, HERC 1, CGA 2)
    dw 0x01EF                   ; VGA:  0,1,2,3 + 5,6,7,8
    dw 0x0011                   ; HERC: 0 (mode 7 text) + 4 (its own graphics)
    dw 0x000F                   ; CGA:  0,1,2,3

; -----------------------------------------------------------------------------
; fsx_run - the bracket (SPEC.md 53.1, slot 0x02C0 via X stub)
;
; in:       AX = near entry inside the caller's image, BX = the caller's own
;           window ptr, CX = flags (bit 0 = FSXF_KEEPWORKER; others refuse);
;           ES = the CALLER's DS (the X stub) - the ownership fence reads it.
;           UI-task window-callback context, gfx lock held.
; out:      CF=1 refused, nothing changed. CF=0: the app's proc ran to its
;           ret and the desktop is restored (SPEC.md 53.6). Every register
;           preserved either way.
;
; The fence is inst_pkg_spawn's, verbatim: BX must be a live package
; instance's window whose segment is the caller's own, and AX must lie
; inside its image+bss. The entry is called through wm_pkgcall - SI = the
; window ptr, DS = CS = the package's segment, ES = KERNEL_SEG - an ordinary
; near proc with a near ret, exactly a W_ONKEY's environment.
; -----------------------------------------------------------------------------
fsx_run:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    test cx, ~FSXF_KEEPWORKER   ; undefined flag bits refuse, so the word
    jnz .fail                   ; stays extensible (SPEC.md 53.1)
    cmp byte [sch_cur], 0       ; the UI task alone may enter - a worker's
    jne .fail                   ; bracket would freeze the UI task mid-frame
    cmp byte [fsx_task], 0xFF   ; one bracket at a time
    jne .fail
    cmp word [fdlg_win], 0      ; not under the modal file dialog (SPEC.md 38)
    jne .fail
    call inst_wchk              ; the ownership fence (SPEC.md 53.1): bound
    jc .fail                    ; the package's BX before any deref...
    call inst_of_win            ; DI = the record owning the window
    jc .fail
    cmp byte [di+I_STATE], 1    ; ...live only...
    jne .fail
    test byte [di+I_KIND], KIND_PKG
    jz .fail
    mov dx, es                  ; ...a package whose segment is the caller's
    cmp dx, [di+I_SPTR]         ; own DS (identity, not containment)...
    jne .fail
    cmp ax, [di+I_SIZE]         ; ...and an entry inside its image+bss
    jae .fail

    mov dx, di                  ; DL = the caller's instance index - the
    sub dx, inst_tab            ; release walk below exempts it
    push cx
    mov cl, 5
    shr dx, cl
    pop cx
    mov dh, 0xFF                ; DH = the kept worker's slot, or none
    test cl, FSXF_KEEPWORKER
    jz .nokeep
    mov dh, [di+I_TASK]         ; 0xFF when the instance has no worker -
.nokeep:                        ; keeping nothing is not an error

    pushf                       ; arm the freeze (SPEC.md 53.2) in one IF=0
    cli                         ; window: both bytes or neither
    mov [fsx_worker], dh
    mov byte [fsx_task], 0      ; task 0 - checked above
    popf
    mov byte [fsx_cur], 0xFF    ; no foreign mode yet

    ; silence what the freeze strands (SPEC.md 53.3) - AFTER the arm, so no
    ; foreign task can take a fresh grant between the two. snd_release_inst
    ; is the SPEC.md 29.4 teardown routine: DSV_RELINST first, then the
    ; clip, then the tone channel, then the generation bump that makes the
    ; thaw safe. The caller's own grants stay - it keeps running, which is
    ; what carries a FSXF_KEEPWORKER stream in.
    push ax
    mov si, inst_tab
    mov cx, INST_MAX
    xor al, al
.rel:
    cmp byte [si+I_STATE], 0
    je .relnext
    cmp al, dl
    je .relnext
    call snd_release_inst
.relnext:
    inc al
    add si, I_RECSZ
    loop .rel
    pop ax

    push ax                     ; stash the desktop to extended memory while
    push bx                     ; it is still on screen (SPEC.md 53.6): a
    call fsx_stash_save         ; 286+/VGA machine with a store gets an
    pop bx                      ; instant restore instead of a full repaint.
    pop ax                      ; No-op and harmless on tier 0. AX/BX are the
                                ; entry+window the wm_pkgcall setup below
                                ; needs, so they are banked across it.

    push bp                     ; the app owns the machine from here to its
    mov si, bx                  ; ret: wm_pkgcall's contract, record in SI,
    mov bp, ax                  ; offset in BP (SPEC.md 53.1)
    call wm_pkgcall
    pop bp
    call fsx_restore            ; SPEC.md 53.6, ordered
    clc
    jmp short .out
.fail:
    stc
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fsx_restore - one path home (SPEC.md 53.6, order binding)
;
; 1. the desktop's mode back (skipped when no fsx_mode call happened - the
;    screen is already the desktop's mode); this also restores the standard
;    planar VGA state the stash-load's plane writes need; 2. drain the BIOS
;    key buffer and the event queue - keys typed and clicks queued at the
;    game must not land in the desktop ladder (the SPEC.md 34.4 click-abort
;    drain is the precedent); 3. disarm the freeze; 4. bring the desktop
;    back under the still-held lock - the XMS stash if one was taken
;    (SPEC.md 53.6), a full wm_paint_all otherwise. The callback epilogue's
;    gfx_unlock then flushes (if buffered) and re-shows the cursor with a
;    fresh save-under from the restored VRAM - SPEC.md 7's own contract.
; -----------------------------------------------------------------------------
fsx_restore:
    push ax
    push di
    cmp byte [fsx_cur], 0xFF
    je .nomode
    call vid_setmode            ; idempotent; the Hercules body clears its
.nomode:                        ; 32KB, the BIOS resets the palette + state
.kd:
    mov ah, 1                   ; drain the BIOS key buffer
    int 0x16
    jz .kdone
    xor ah, ah
    int 0x16
    jmp short .kd
.kdone:
.ed:
    mov di, fsx_evtmp           ; drain the event queue
    call evq_pop
    jnc .ed
    pushf
    cli
    mov byte [fsx_task], 0xFF   ; disarm - sleepers marked ready during the
    mov byte [fsx_worker], 0xFF ; bracket run from the next tick
    popf
    mov byte [fsx_cur], 0xFF
    cmp byte [fsx_stashed], 0   ; a stash to write back?
    je .repaint
    call fsx_stash_load         ; AL=1 it wrote the desktop, 0 it could not
    or al, al                   ; (the back buffer got armed - VRAM is stale)
    jz .repaint
    mov byte [menu_bdirty], 1   ; the restored bar carries a stale clock - one
    call menu_draw_bar          ; cheap bar redraw, not a whole-screen repaint
    jmp short .done
.repaint:
    mov byte [menu_bdirty], 1   ; the bar was overdrawn (the save-under
    call wm_paint_all           ; precedent, SPEC.md 12.05)
.done:
    pop di
    pop ax
    ret

; -----------------------------------------------------------------------------
; fsx_mode - set a foreign mode and describe it (SPEC.md 53.4, 0x02C8)
;
; in:       AL = FSXM_* id, ES:DI = an FSI_SIZE buffer (ES is the caller's
;           own, the gfx_blit4 idiom). Bracket-only, exclusive task only.
; out:      CF=0 mode set, buffer filled. CF=1 refused: no bracket, wrong
;           task, id out of range, not on this adapter (fsx_caps' own bit),
;           or the back buffer is armed - it describes desktop geometry and
;           nothing else, so osapi_gfx_dbuf off comes first (SPEC.md 53.5).
;           Every register preserved.
; -----------------------------------------------------------------------------
fsx_mode:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov ah, [fsx_task]
    cmp ah, 0xFF
    je .fail
    cmp ah, [sch_cur]
    jne .fail
    cmp byte [bb_dbl], 0
    jne .fail
    cmp al, FSXM_COUNT
    jae .fail
    mov bl, [vid_kind]          ; the caps bit - the same predicate the
    xor bh, bh                  ; app's greying used (SPEC.md 47)
    shl bx, 1
    mov dx, [bx+fsx_capstab]
    mov cl, al
    mov bx, 1
    shl bx, cl
    test dx, bx
    jz .fail

    mov ch, al                  ; CH = the id, live across the mode set
    cmp al, FSXM_TEXT80
    je .text
    cmp al, FSXM_HERC
    je .herc
    cmp al, FSXM_MODEX
    je .modex
    mov bx, fsx_bmodes          ; the plain BIOS rows
    xlatb                       ; AL = the BIOS mode number
    call fsx_setbios
    jmp short .fill
.text:
    call vid_text               ; mode 3, or 3BFh<-0 + mode 7 on Hercules
    jmp short .fill
.herc:
    call vid_setmode            ; the 6845 body + the load-bearing 32KB clear
    jmp short .fill
.modex:
    mov al, 0x13
    call fsx_setbios
    call fsx_modex              ; unchain + retime to 320x240 (SPEC.md 53.4)
.fill:
    mov al, ch                  ; DS:SI = the id's row, ES:DI = the buffer;
    mov ah, FSXR_SIZE           ; the row IS bytes 0..13 of the block
    mul ah
    mov si, ax
    add si, fsx_mtab
    push cx                     ; CH is the id and rep movsw eats CX whole
    push di
    cld
    mov cx, 7
    rep movsw
    pop di
    pop cx
    mov [es:di+FSI_MODE], ch
    mov byte [es:di+FSI_RSVD], 0
    ; the three per-adapter fixups (SPEC.md 53.4)
    cmp ch, FSXM_HERC
    jne .f1
    mov ax, [vid_seg]           ; NOT a constant: a HERCSEG= test build
    mov [es:di+FSI_SEG], ax     ; (SPEC.md 39.9) flows through to the app,
    jmp short .f3               ; or hercshot could never see an fsx frame
.f1:
    cmp ch, FSXM_TEXT80
    jne .f3
    cmp byte [vid_kind], VID_HERC
    jne .f2
    mov word [es:di+FSI_SEG], 0xB000
    mov byte [es:di+FSI_PAGES], 1
    jmp short .f3
.f2:
    cmp byte [vid_kind], VID_CGA
    jne .f3
    mov byte [es:di+FSI_PAGES], 4
.f3:
    mov [fsx_cur], ch
    clc
    jmp short .out
.fail:
    stc
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fsx_setbios - int 10h AH=00h with everything banked. A mode set is rare
; and some BIOSes scribble more than AX, so the insurance is cheap where it
; matters and paid nowhere hot.
; in: AL = BIOS mode number
; -----------------------------------------------------------------------------
fsx_setbios:
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    xor ah, ah
    int 0x10
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; fsx_modex - Mode X: 13h unchained and retimed to 320x240 (SPEC.md 53.4)
;
; The canonical sequence: chain4 off through a sequencer sync reset, the
; 25MHz dot clock and 480-scan polarity on the misc output, the CRTC
; unprotected and retimed (240 doubled lines), dword mode off, byte mode
; on, and all four planes cleared through map mask 0Fh - the BIOS cleared
; only the 64KB the chained mode could see.
; -----------------------------------------------------------------------------
fsx_modex:
    push ax
    push cx
    push dx
    push si
    push di
    push es
    mov dx, 0x3C4
    mov ax, 0x0604              ; chain4 off, odd/even off
    out dx, ax
    mov ax, 0x0100              ; sync reset while the clock changes
    out dx, ax
    mov dx, 0x3C2
    mov al, 0xE3                ; 25MHz, 60Hz, 480-line sync polarity
    out dx, al
    mov dx, 0x3C4
    mov ax, 0x0300              ; run again
    out dx, ax
    mov dx, 0x3D4
    mov al, 0x11                ; unprotect CRTC 0..7
    out dx, al
    inc dx
    in al, dx
    and al, 0x7F
    out dx, al
    dec dx
    mov si, fsx_xcrtc
    mov cx, 10
    cld
.crtc:
    lodsw
    out dx, ax
    loop .crtc
    mov dx, 0x3C4
    mov ax, 0x0F02              ; map mask: all four planes...
    out dx, ax
    mov ax, 0xA000              ; ...and clear the whole 256KB
    mov es, ax
    xor di, di
    xor ax, ax
    mov cx, 0x8000
    rep stosw
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret

fsx_xcrtc:                      ; Mode X CRTC retiming, index in the low byte
    dw 0x0D06, 0x3E07, 0x4109, 0xEA10, 0xAC11
    dw 0xDF12, 0x0014, 0xE715, 0x0616, 0xE317

; -----------------------------------------------------------------------------
; fsx_wait - the frame clock, and the present (SPEC.md 53.5, 0x02D0)
;
; in:       AL = 0 return at the next [ticks] change (hlt between polls);
;           AL = 1 return in vertical retrace. Bracket-only, exclusive task
;           only.
; out:      CF=0 (a timed-out retrace wait too - timing degrades, it does
;           not fail); CF=1 outside a bracket. Every register preserved.
;
; The present: while [bb_dbl] is armed and no mode switch has happened, the
; armed buffer is flushed BEFORE the wait - the bracket never calls
; gfx_unlock, so this is the only flush a buffered renderer gets. Every
; retrace poll is bounded by a [ticks] delta (SPEC.md 37.90's rule: the one
; way to hang is waiting forever for a bit that never changes on a machine
; where every read is 0FFh).
; -----------------------------------------------------------------------------
fsx_wait:
    push ax
    push bx
    push dx
    mov ah, [fsx_task]
    cmp ah, 0xFF
    je .fail
    cmp ah, [sch_cur]
    jne .fail
    cmp byte [fsx_cur], 0xFF    ; the present clause: unswitched + armed
    jne .nopresent
    cmp byte [bb_dbl], 0
    je .nopresent
    call gfx_flush
.nopresent:
    or al, al
    jnz .vsync
    mov bx, [ticks]             ; AL = 0: the next tick
.tick:
    hlt                         ; IF=1 in callback context - the tick wakes it
    cmp bx, [ticks]
    je .tick
    jmp short .ok
.vsync:
    mov dx, 0x3DA               ; the port by the CURRENT mode: on a Hercules
    cmp byte [vid_kind], VID_HERC ; machine every settable mode is the 3BAh
    jne .pa                     ; family, on VGA/CGA every one is 3DAh - so
    mov dx, 0x3BA               ; the adapter kind IS the mode's family
.pa:
    mov bx, [ticks]             ; phase A: wait until OUT of retrace, so a
.paw:                           ; call landing mid-retrace syncs to the NEXT
    call fsx_insync
    jnc .pb
    mov ax, [ticks]
    sub ax, bx
    cmp ax, 3
    jb .paw
    jmp short .ok               ; dead port: timed out, return anyway
.pb:                            ; phase B: wait until retrace begins
    mov ax, [ticks]
    sub ax, bx
    cmp ax, 3
    jae .ok
    call fsx_insync
    jnc .pb
.ok:
    clc
    jmp short .out
.fail:
    stc
.out:
    pop dx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fsx_insync - CF = 1 when the adapter at DX is in vertical retrace.
; VGA/CGA (3DAh): bit 3 set. Hercules (3BAh): bit 7 LOW while vertical sync
; is active - the polarity is inverted there.
; -----------------------------------------------------------------------------
fsx_insync:
    push ax
    in al, dx
    cmp dl, 0xBA
    je .herc
    test al, 8
    jz .no
    jmp short .yes
.herc:
    test al, 0x80
    jnz .no
.yes:
    stc
    jmp short .done
.no:
    clc
.done:
    pop ax
    ret

; --- the mode rows: bytes 0..13 of the FSI block, verbatim (SPEC.md 53.4) ----
FSXR_SIZE equ 14

fsx_mtab:
    ;  seg     w    h    stride  flags        bpp banks pages  bstep
    dw 0xB800, 80,  25,  160
    db FSIF_TEXT, 0, 1, 8
    dw 0                        ; 0 TEXT80 (B000/pages fixed up per adapter)
    dw 0xB800, 40,  25,  80
    db FSIF_TEXT, 0, 1, 8
    dw 0                        ; 1 TEXT40
    dw 0xB800, 320, 200, 80
    db FSIF_BANKED, 2, 2, 1
    dw 0x2000                   ; 2 CGA320 (even/odd row interleave)
    dw 0xB800, 640, 200, 80
    db FSIF_BANKED, 1, 2, 1
    dw 0x2000                   ; 3 CGA640
    dw 0xB000, 720, 348, 90
    db FSIF_BANKED, 1, 4, 2
    dw 0x2000                   ; 4 HERC (seg <- [vid_seg] at fill)
    dw 0xA000, 320, 200, 40
    db FSIF_PLANAR, 4, 1, 8
    dw 0                        ; 5 VGA0D
    dw 0xA000, 320, 200, 320
    db 0, 8, 1, 1
    dw 0                        ; 6 VGA13 (linear, byte per pixel)
    dw 0xA000, 640, 480, 80
    db FSIF_PLANAR, 4, 1, 1
    dw 0                        ; 7 VGA12
    dw 0xA000, 320, 240, 80
    db FSIF_PLANAR, 8, 1, 3
    dw 0                        ; 8 MODEX (stride = bytes per PLANE row)

fsx_bmodes:                     ; the plain-BIOS rows' mode numbers; ids 0,
    db 0x00, 0x01, 0x04, 0x06  ; 4 and 8 dispatch before the xlatb and
    db 0x00, 0x0D, 0x13, 0x12  ; never read theirs
    db 0x13

; =============================================================================
; The XMS desktop stash (SPEC.md 53.6): on a 286+/VGA machine with an extended
; store, save the desktop's four planes at bracket entry and write them back
; at exit - an instant restore instead of a full wm_paint_all. Tier 0 (the
; 8086 target) and mono adapters fall through to the repaint, untouched.
;
; The engine is COLD code (SPEC.md 2.6): it runs once per bracket entry/exit,
; never on a hot path, so it costs guard 1 (the budget) and NOT guard 2 (the
; 64KB segment). CS = COLD_SEG, DS = KERNEL_SEG - so the state words are
; DS-direct and the xm_* calls leave through cw_ shims. Only the ~30 bytes of
; .text glue below (two entry thunks, three cw_ shims) touch guard 2.
;
; xm_copy under the held gfx lock is exactly the sanctioned use since SPEC.md
; 41.8 - the copy touches no VRAM and takes no lock of its own, and the freeze
; means there is no painter to stall anyway.
; =============================================================================
section .cold

; fsxc_save - stash the desktop. Gated to VGA + a store + the desktop straight
; in VRAM (not a back buffer). Sets [fsx_stashed]. retf to its .text thunk.
fsxc_save:
    cmp byte [cpu_tier], CPU_8086   ; tier 0: no store at all
    je .no
    cmp byte [vid_mono], 0          ; VGA only - four planes to read
    jne .no
    cmp byte [bb_dbl], 0            ; the desktop must be in VRAM (SPEC.md 53.6)
    jne .no
    mov ax, 0x5800                 ; DX:AX = 153,600 bytes = 150KB: the four
    mov dx, 0x0002                 ; planes of a 640x480 screen
    call KERNEL_SEG:cw_xm_alloc
    jc .no
    mov [fsx_xlo], ax
    mov [fsx_xhi], dx
    xor di, di                     ; direction 0: conventional -> extended
    call fsxc_xfer
    mov byte [fsx_stashed], 1
    retf
.no:
    mov byte [fsx_stashed], 0
    retf

; fsxc_load - write the planes back and free the block. out AL = 1 it wrote
; the desktop, 0 it only freed (the back buffer was armed during the bracket,
; so the VRAM the stash holds is stale and the caller must repaint). Called
; only when [fsx_stashed] is set.
fsxc_load:
    xor bx, bx                     ; BX = "wrote it" flag
    cmp byte [bb_dbl], 0
    jne .free
    mov di, 1                      ; direction 1: extended -> conventional
    call fsxc_xfer
    mov dx, 0x3C4                  ; SEQ Map Mask back to all four planes, so
    mov ax, 0x0F02                ; the kernel's own drawing writes normally
    out dx, ax
    inc bx
.free:
    mov ax, [fsx_xlo]
    mov dx, [fsx_xhi]
    call KERNEL_SEG:cw_xm_free
    mov byte [fsx_stashed], 0
    mov ax, bx                    ; AL = the wrote-it flag
    retf

; fsxc_xfer - the eight-copy engine (four planes, two 19,200-byte halves each,
; because a whole 38,400-byte plane is past XM_MAX_COPY and would also straddle
; the 0xA000 segment). DI = 0 reads each plane through GC Read Map Select /
; 1 writes each through SEQ Map Mask; DI is also xm_copy's own direction word,
; so it is set once and left. Near proc, cold-local.
fsxc_xfer:
    xor bp, bp                    ; BP = copy index 0..7
.each:
    test bp, 1
    jnz .body                     ; half 1: the plane register is already set
    mov ax, bp                    ; half 0: this plane is bp >> 1
    mov cl, 1
    shr ax, cl
    or di, di
    jnz .wr
    mov ah, al                    ; save: GC index 4 (Read Map Select) = plane
    mov al, 4
    mov dx, 0x3CE
    out dx, ax
    jmp short .body
.wr:
    mov cl, al                    ; load: SEQ index 2 (Map Mask) = 1 << plane
    mov ah, 1
    shl ah, cl
    mov al, 2
    mov dx, 0x3C4
    out dx, ax
.body:
    mov ax, 0x4B00                ; XMS end = base + bp * 19,200
    mul bp                        ; DX:AX (bp <= 7, fits 32 bits)
    add ax, [fsx_xlo]
    adc dx, [fsx_xhi]
    mov si, bp                    ; conventional SI = (bp & 1) * 19,200
    and si, 1
    jz .lo
    mov si, 0x4B00
    jmp short .es
.lo:
    xor si, si
.es:
    push ax                       ; ES = the framebuffer (xm_copy wants ES:SI);
    mov ax, 0xA000                ; preserve the XMS low word across the load
    mov es, ax
    pop ax
    mov cx, 0x4B00                ; 19,200 bytes: even, <= XM_MAX_COPY
    call KERNEL_SEG:cw_xm_copy    ; DI already carries the direction
    inc bp
    cmp bp, 8
    jb .each
    ret

section .text

; --- the stash's .text glue (SPEC.md 2.6) ------------------------------------
; Six-byte entry thunks fsx_run / fsx_restore near-call, and four-byte cw_
; shims the cold engine far-calls out through. This is the whole guard-2 cost.
fsx_stash_save:   call COLD_SEG:fsxc_save
                  ret
fsx_stash_load:   call COLD_SEG:fsxc_load
                  ret
cw_xm_alloc:      call xm_alloc
                  retf
cw_xm_copy:       call xm_copy
                  retf
cw_xm_free:       call xm_free
                  retf

; --- state -------------------------------------------------------------------
section .bss

fsx_cur:   resb 1               ; the FSXM id on screen, 0xFF = unswitched.
                                ; Written by fsx_run before anything reads
                                ; it, so it needs no boot-time init.
fsx_evtmp: resb 8               ; fsx_restore's event-drain scratch
fsx_xlo:   resw 1               ; the stash block's 32-bit linear base, from
fsx_xhi:   resw 1               ; xm_alloc (SPEC.md 53.6)
fsx_stashed: resb 1            ; 1 = a desktop stash is live and owed a free

section .text
