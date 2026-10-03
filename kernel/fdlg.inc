; =============================================================================
; os8088 - fdlg.inc
;
; The Standard File dialog (SPEC.md 38): a DISK WINDOW (SPEC.md 22) put into a
; chooser role for one application, in an Open form and a Save form, that
; hands a chosen 8.3 name back to whoever asked. Label prefix fdlg_.
;
; It is the missing half of SPEC.md 18.4. The file slots gave packages five
; whole-file operations and no way to NAME a file, which is why Note Pad
; wrote a hard-coded NOTES.TXT (SPEC.md 27.1) - not because one note is
; enough, but because there was nothing to ask a filename with.
;
; **This file is GLUE, not a browser (SPEC.md 38.1).** It used to be one: its
; own window, listing, row painter, selection bar, scroll bar wiring, name
; editor, New Folder button, drive cycling and path stack - 3,622 resident
; bytes on kern_big, every one of them a second copy of something files.inc
; already had resident. The chooser is now a KIND_FILES instance launched
; through app_launch, and what lives here is only what is genuinely the
; dialog's:
;
;   - WHO ASKED: the requester's record, window, I_SPTR and completion proc,
;     and the staleness triple that guards the callback (SPEC.md 38.6).
;   - MODALITY: fdlg_grab / fdlg_top / fdlg_gate, unchanged (SPEC.md 38.2).
;   - THE TWO FORMS' ANSWERS: files.inc raises an FDH_* event at nine sites
;     through `fdlg_hook`, which is a resident compare of the acting block
;     against [fdlg_blk] - so a Disk window that is not the chooser never
;     crosses into this file (SPEC.md 38.9).
;   - THE BUTTON COLUMN: Open|Save, Cancel, Drive (SPEC.md 38.3).
;   - WHERE TO OPEN and what to remember (SPEC.md 38.10).
;   - THE ANSWER IS POSTED: every hook that ends the dialog runs inside the
;     chooser's OWN callback, whose caller goes on drawing that window, so the
;     hook only records [fdlg_act] and fdlg_reap does the close and the
;     callback on the next UI pass (SPEC.md 38.6).
;
; **This module is `.cold` (SPEC.md 2.6)** on kern_big and FDLG.DRV on
; kern_small (SPEC.md 38.0). Its code has a CS of its own; calls that leave
; the cold set go out through `KERNEL_SEG:cw_*`. All of its data is above the
; single section toggle, and a `db`/`dw` added below it is read at the wrong
; segment with no diagnostic.
;
; **MEASURING THIS FILE: `kernsize --modules` OVERSTATES IT BY ~1,600 BYTES.**
; That tool brackets the `%include` in kernel.asm, and `%include "os88ui.inc"`
; is NESTED INSIDE this one, at the foot below the section toggle - so
; os88ui.inc's kernel copy is billed here. NONE of it is this module's: it is
; the shared control, resident on BOTH kernels, and files.inc, ctrl.inc and
; apps.inc reach it as well. Quote the dialog's own symbols, and say which
; figure you mean.
; =============================================================================

FD_NAMEMAX  equ 12              ; an 8.3 name, dot included
%if FD_NAMEMAX + 1 > INST_FNSZ
  %error "INST_FNSZ too small for FD_NAMEMAX + NUL"
%endif

; --- the events files.inc raises (SPEC.md 38.9) -------------------------------
; `fdlg_hook` takes one of these in AL and answers CF=1 when the acting Disk
; window IS the chooser and the event was taken. The ORDER is the dispatch
; table's below, and the two kern_small-only events are LAST so kern_big's
; table simply stops short of them.
FDH_ARM     equ 0               ; fm_layout: re-arm the Save form's name box
FDH_BANK    equ 1               ; fm_edit_end: bank a mode-8 buffer
FDH_PICK    equ 2               ; fm_open_sel, a FILE; AX = its index
FDH_SEL     equ 3               ; fm_onclick: FS_SEL changed
FDH_COMMIT  equ 4               ; fm_edit_commit, mode 8 (Enter)
FDH_KEY     equ 5               ; fm_onkey_x: any key, in DX (AL/AH's shape)
FDH_BTN     equ 6               ; a column button fired; AH = its FM_B* id
FDH_PAINT   equ 7               ; fm_draw_core's end: draw the column
FDH_RECT    equ 8               ; kern_big's fm_brect: AH = a column id
FDH_LABEL   equ 9               ; kern_big's fm_btn1: AH = a column id
FDH_CLICK   equ 10              ; kern_small: a press, [fm_pressx/y]
FDH_UP      equ 11              ; kern_small: the release (fdlg_onup)

FDA_COMMIT  equ 1               ; [fdlg_act]: the posted answer (SPEC.md 38.6)
FDA_CANCEL  equ 2

fdlg_s_topen:  db 'Open', 0     ; files.inc's fm_s_open is this string
fdlg_s_tsave:  db 'Save As', 0  ; ...and the Save form's caption
fdlg_s_save:   db 'Save', 0
fdlg_s_cancel: db 'Cancel', 0
%ifndef NOFDMEDIA
fdlg_s_media:  db 'MEDIA', 0    ; SPEC.md 38.10's default folder
%endif

; -----------------------------------------------------------------------------
; fdlg_win - the chooser's window, 0 = none, 0FFFFh = being launched, AND the
; modal gate (SPEC.md 38.2). fdlg_blk - its fm_pool block, 0 = none.
;
; Both live HERE, in .text with an initialiser, and not in .bss: `-f bin`
; gives .bss no image bytes and nothing zeroes it at boot, and fdlg_grab
; reads the first on the very first mouse press the machine ever sees, while
; fm_layout reads the second (through fdlg_hook) on the very first Disk
; window paint. As garbage either one is a chooser that does not exist.
; -----------------------------------------------------------------------------
fdlg_win:   dw 0
fdlg_blk:   dw 0

%ifdef FDLG_MOD
FD_NENT     equ 5               ; entries FDLG.DRV publishes (SPEC.md 2.8)
FDE_OPEN    equ 0
FDE_HOOK    equ 1
FDE_REAP    equ 2
FDE_GRAB    equ 3
FDE_TOP     equ 4
%endif

; =============================================================================
; TWO SHAPES, ONE SOURCE - SPEC.md 22.3.0.1's three rules
; =============================================================================
; kern_big keeps every body below resident in `.cold`. kern_small emits them
; into `.modd`, which tools/os88mod.py cuts out as FDLG.DRV and mod_need reads
; back when an application asks for a dialog.
;
;   FDBODY  the label a body carries: `fdlg_open_x` resident, `fdlg_open_x_m`
;           in the image with a resident stub of the public name in front.
;   FDX     a call OUT of the image, near on big and `call COLD_SEG:xd_<name>`
;           on small - COLD_SEG being an assembly-time constant.
;   FDK     a call INTO `.text` through one of the `.cold` trampolines of
;           SPEC.md 2.6.2: `call ct_<target>` on big, and the plain
;           `call KERNEL_SEG:<target>` on small.
;   FDXF    the resident far entry FDX names, `call <body> / retf`. The prefix
;           is `xd_` and filecp.inc's is `xf_`: both blocks share `.cold`.
;   fdk_*   the shared register epilogues. A module may not `jmp kretc_di` -
;           that is a near `ret` against a far frame - so the image carries
;           its own ladder.
; =============================================================================
%ifdef FDLG_MOD
  %macro FDBODY 1
%1 %+ _m:
  %endmacro
  %macro FDX 1
    call COLD_SEG:xd_ %+ %1
  %endmacro
  %macro FDK 1
    call KERNEL_SEG:%1
  %endmacro
  %macro FDXF 1
xd_ %+ %1:
    call %1
    retf
  %endmacro
%else
  %macro FDBODY 1
%1:
  %endmacro
  %macro FDX 1
    call %1
  %endmacro
  %macro FDK 1
    call ct_ %+ %1
  %endmacro
  %macro FDXF 1
  %endmacro
%endif

%ifndef FDLG_MOD
section .cold                   ; cold code (SPEC.md 2.6): resident, but in a
                                ; segment of its own, so it costs KERN_CODE_MAX
                                ; nothing. DS is still KERNEL_SEG, so every data
                                ; reference below is unchanged
%else
section .modd                   ; THE ON-DEMAND IMAGE (SPEC.md 2.8). The header
modd_hdr:                       ; is at offset 0 because vstart is 0 and
    dw 0x384F                   ; mod_check reads it through ES
    db MOD_VER
    db MOD_FDLG
    dw BUILD_NUM                ; the commit...
    dw MOD_STAMP                ; ...and this build's LAYOUT
    dw modd_end                 ; MOD_H_IMG - vstart 0, so the end label IS it
    dw FD_NENT
    dw modd_e_open              ; A FAR-RETURNING BODY IS ITS OWN ENTRY and a
    dw modd_e_hook              ; near-returning one is wrapped: an entry is
    dw fdlg_reap_x_m            ; reached by `call far`, so what it ends in has
    dw fdlg_grab_x_m            ; to be a `retf`. reap/grab/top leave through
    dw fdlg_top_x_m             ; their own; open and the hook leave near

modd_e_open:    call fdlg_open_x_m
            retf
modd_e_hook:    call fdlg_hook_x_m
            retf
%endif

; --- the shared epilogues (filecp.inc's shape: a copy, on both builds) ------
fdk_di:     pop di
            pop si
            pop dx
            pop cx
            pop bx
            pop ax
            ret

; -----------------------------------------------------------------------------
; fdlg_open - slot 0x0124's body (SPEC.md 38.6, 38.7)
; in:  AL = 0 Open / 1 Save, BX = requester window, DI = completion proc,
;      SI = a default name (NUL, <= 12) or 0; gfx lock HELD by the caller
; out: CF=0 the chooser is ON SCREEN; CF=1 refused. All registers preserved.
;
; It launches a Disk window through app_launch, which takes the gfx lock
; itself - so [inst_lkhd] says the caller already holds it and app_launch
; shows the window under that hold instead (SPEC.md 38.6). [fdlg_win] =
; 0FFFFh is the mark fm_kinit adopts the window by; a launch that never
; reached fm_kinit leaves the mark, which is the refusal.
; -----------------------------------------------------------------------------
FDBODY fdlg_open_x
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    cmp word [fdlg_win], 0
    jne .ref                    ; no dialog ever opens on top of another
    mov [fdlg_rqcb], di
    mov [fdlg_rqwin], bx
    mov [fdlg_mode], al

    FDK cw_inst_win_owner       ; DI = the owning record, or 0; BX preserved
    or di, di
    jz .ref
    cmp byte [di+I_STATE], 1
    jne .ref
    mov [fdlg_rqrec], di
    mov ax, [di+I_SPTR]
    mov [fdlg_rqsp], ax

    xor ax, ax
    mov [fdlg_act], al          ; no answer yet
    mov [fdlg_size], ax         ; nothing picked: a redirected volume's size
    mov [fdlg_sizeh], ax        ; is the picked row's (SPEC.md 38.6.1)
    mov [fdlg_name], al
    or si, si                   ; the caller's default wins...
    jnz .setname
    call fdlg_home_name         ; ...else the name this app last committed
    jc .named
.setname:
    mov di, fdlg_name
    mov cx, FD_NAMEMAX
    FDX fm_ncpy
.named:

    call fdlg_seed              ; AL = volume, DX = folder, SI = its name|0
    mov [fdlg_sdrv], al         ; where it OPENED, so a cancel that never
    mov [fdlg_scwd], dx         ; moved records nothing (SPEC.md 38.10)
    FDX fm_seed                 ; parked for fm_kinit, as a drive icon does

    mov ax, fdlg_s_topen        ; the caption fm_kinit puts on it
    cmp byte [fdlg_mode], 0
    je .ttl
    mov ax, fdlg_s_tsave
.ttl:
    mov [fdlg_ttl], ax
    mov word [fdlg_win], 0xFFFF ; fm_kinit adopts the window being built
    mov byte [inst_lkhd], 1     ; ...and app_launch shows it under OUR hold
    mov al, KIND_FILES
    call KERNEL_SEG:cw_app_launch
    mov byte [inst_lkhd], 0
    jc .fail
    cmp word [fdlg_win], 0xFFFF ; launched, but not by fm_kinit: impossible,
    je .fail                    ; and refused rather than trusted
%ifdef KERN_SMALL
    mov bx, [fdlg_win]          ; the column's release (SPEC.md 38.3): this
    mov word [bx+W_ONMOUSEUP], fdlg_onup ; build's Disk window has none of
                                ; its own, so the chooser's is ours - and
                                ; wm_onmouseup IS this store, which kern_small
                                ; publishes no shim for
%endif
    clc
    jmp short .out
.fail:
    mov word [fdlg_win], 0
.ref:
    stc
.out:
    jmp fdk_di

; -----------------------------------------------------------------------------
; fdlg_seed - where the chooser opens (SPEC.md 38.10)
; out: AL = volume, DX = first cluster (0 = root), SI = the folder's name for
;      the title's path, or 0
; clobbers: AX, BX, CX, DX, SI (fdlg_open banked them all)
;
; The user's last folder if they ever chose one; else MEDIA at the root of the
; instance's own drive (assembled out by NOFDMEDIA=1, which then takes the
; first arm with the launch folder in it); else, with no row at all, where
; the volume globals stand. The MEDIA arm mounts the root to look, which
; moves the globals - nothing reads them on this path, and fm_kinit's own
; listing is the second mount.
; -----------------------------------------------------------------------------
fdlg_seed:
    call fdlg_hidx              ; BX = the requester's row
    mov si, 0                   ; (a MOV: hidx's CF is the answer)
    jc .glob
    mov al, [inst_fdrv+bx]
%ifndef NOFDMEDIA
    cmp byte [inst_fpick+bx], 0
    je .media
%endif
    shl bx, 1
    mov dx, [inst_fcwd+bx]
    ret
.glob:
    mov al, [disk_drive]
    mov dx, [dsk_cwd]
    ret
%ifndef NOFDMEDIA
.media:
    push ax
    mov dl, al
    xor ax, ax
    FDX dsk_chdir_x             ; the root - and only for the volume and
    jc .root                    ; folder it publishes: a mount with no
    cmp byte [dsk_vkind], DVK_FILE ; listing store lists nothing, so MEDIA
    je .root                    ; is looked up BY NAME in the directory
    mov si, fdlg_s_media        ; (dskw_stat), not in a listing (SPEC.md
    call COLD_SEG:dwf_dskw_stat ; 38.10). A redirected volume's stat writes
    jc .root                    ; no dskw_raw, so it is the root there
    test byte [dskw_raw+DSK_R_ATTR], 0x10
    jz .root                    ; a FILE called MEDIA is not the folder
    mov dx, [dskw_raw+DSK_R_CLUS]
    mov si, fdlg_s_media
    pop ax
    ret
.root:
    xor dx, dx
    xor si, si
    pop ax
    ret
%endif

; -----------------------------------------------------------------------------
; fdlg_hidx - the requester's row in instance.inc's side table
; out: CF=0 with BX = the row and SI -> its inst_fname; CF=1 = no row
; -----------------------------------------------------------------------------
fdlg_hidx:
    push di
    mov di, [fdlg_rqrec]
    or di, di
    jz .no
    call KERNEL_SEG:cw_inst_fhome_idx
    cmp bx, INST_MAX
    jae .no
    push ax
    push cx
    mov al, bl
    mov cl, INST_FNSZ
    mul cl
    mov si, inst_fname
    add si, ax
    pop cx
    pop ax
    pop di
    clc
    ret
.no:
    pop di
    stc
    ret

; fdlg_home_name - SI -> the name this app last committed; CF=1 = none or empty
fdlg_home_name:
    push bx
    call fdlg_hidx
    jc .out
    cmp byte [si], 1            ; CF=1 exactly when the name is empty
.out:
    pop bx
    ret

; -----------------------------------------------------------------------------
; fdlg_home_dir - record where the chooser stood as the app's folder
; in:  [fdlg_cdrv] / [fdlg_ccwd]; out: nothing (all registers preserved)
;
; It is the instance's ACTUAL current directory (SPEC.md 19.2.1), and
; [inst_fpick] says the USER chose it, so the MEDIA default stops applying.
; -----------------------------------------------------------------------------
fdlg_home_dir:
    push ax
    push bx
    push si
    call fdlg_hidx
    jc .out
    mov al, [fdlg_cdrv]
    mov [inst_fdrv+bx], al
    mov byte [inst_fpick+bx], 1
    shl bx, 1
    mov ax, [fdlg_ccwd]
    mov [inst_fcwd+bx], ax
.out:
    pop si
    pop bx
    pop ax
    ret

; ...and on a COMMIT the name as well (SPEC.md 38.10): a Save As moves the app
fdlg_home_save:
    push cx
    push si
    push di
    call fdlg_home_dir
    call fdlg_hidx
    jc .out
    mov di, si
    mov si, fdlg_name
    mov cx, INST_FNSZ - 1
    FDX fm_ncpy
.out:
    pop di
    pop si
    pop cx
    ret

; -----------------------------------------------------------------------------
; fdlg_gate - is the chooser still a USED and VISIBLE window? (SPEC.md 38.2)
; in:  AL = 1 the caller holds the gfx lock, 0 it does not
; out: CF=0 with BX = the chooser; CF=1 with BX = 0 when there is none -
;      and one that has gone (close box, minimize, anything) is CANCELLED here
; -----------------------------------------------------------------------------
fdlg_gate:
    push cx
    mov bx, [fdlg_win]
    or bx, bx
    jz .none
    mov cx, [bx+W_FLAGS]
    and cx, 3
    cmp cx, 3
    jne .dead
    pop cx
    clc
    ret
.dead:
    or al, al
    jnz .close
    FDK cw_gfx_lock
    call fdlg_close
    FDK cw_gfx_unlock
    jmp short .none
.close:
    call fdlg_close
.none:
    xor bx, bx
    pop cx
    stc
    ret

; -----------------------------------------------------------------------------
; fdlg_reap - once per UI pass while a chooser is up (SPEC.md 38.1.1, 38.6)
; in:  nothing; the gfx lock is FREE (this is ui_task's deferred section)
; out: nothing (all registers preserved)
;
; The collection of a dead chooser, and THE ONE PLACE A POSTED ANSWER IS
; ACTED ON: close, then - for a commit - the callback, all under one hold.
; -----------------------------------------------------------------------------
FDBODY fdlg_reap_x
    cmp word [fdlg_win], 0
    je .out
    push ax
    push bx
    xor al, al
    call fdlg_gate              ; a dead chooser is cancelled, lock and all
    jc .done
    mov al, [fdlg_act]
    or al, al
    jz .done
    FDK cw_gfx_lock
    mov byte [fdlg_act], 0
    push ax
    call fdlg_close
    pop ax
    cmp al, FDA_COMMIT
    jne .unlk
    call fdlg_commit
.unlk:
    FDK cw_gfx_unlock
.done:
    pop bx
    pop ax
.out:
    retf

; -----------------------------------------------------------------------------
; fdlg_grab - a press outside the chooser is swallowed (SPEC.md 38.2)
; in:  CX = x, DX = y; the gfx lock is free
; out: CF=1 swallow it (with a beep); CF=0 let it through
; -----------------------------------------------------------------------------
FDBODY fdlg_grab_x
    push ax
    push bx
    xor al, al
    call fdlg_gate
    jc .pass
    cmp cx, [bx+W_X]
    jl .swallow
    mov ax, [bx+W_X]
    add ax, [bx+W_W]
    cmp cx, ax
    jge .swallow
    cmp dx, [bx+W_Y]
    jl .swallow
    mov ax, [bx+W_Y]
    add ax, [bx+W_H]
    cmp dx, ax
    jge .swallow
.pass:
    clc
    jmp short .out
.swallow:
    FDK cw_snd_beep
    stc
.out:
    pop bx
    pop ax
    retf

; fdlg_top - in: BX = wm_top's answer; out: BX = the chooser instead, if up
FDBODY fdlg_top_x
    push ax
    push cx
    mov cx, bx
    mov al, 1
    call fdlg_gate
    jnc .out
    mov bx, cx
.out:
    pop cx
    pop ax
    retf

; -----------------------------------------------------------------------------
; fdlg_close - take the chooser down (SPEC.md 38.7 step 6)
; in:  the gfx lock held; out: nothing (all registers preserved)
;
; Records where it stood FIRST, out of a block that is still intact whichever
; route got here - a close box has already torn the instance down, and the
; pool block is only reused by the next launch. A failed mount is not a
; folder to bring an app back to (FS_MOK), and arriving at the seed without
; moving is not a choice (SPEC.md 38.10).
; -----------------------------------------------------------------------------
fdlg_close:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov bx, [fdlg_win]
    or bx, bx
    jz .out
    xor ax, ax
    mov [fdlg_win], ax
    mov si, [fdlg_blk]
    mov [fdlg_blk], ax

    mov al, [fdlg_sdrv]         ; the seed, unless the chooser really moved
    mov dx, [fdlg_scwd]
    cmp byte [si+FS_MOK], 0
    je .stood
    mov al, [si+FS_DRV]
    mov dx, [si+FS_CWD]
.stood:
    mov [fdlg_cdrv], al
    mov [fdlg_ccwd], dx
    cmp al, [fdlg_sdrv]
    jne .moved
    cmp dx, [fdlg_scwd]
    je .kept
.moved:
    call fdlg_home_dir          ; ...moving is a statement about the location
.kept:
    FDK cw_inst_win_owner       ; DI = the window's record, or 0
    or di, di
    jz .gone                    ; already torn down: the close box did it
    cmp byte [di+I_STATE], 1
    jne .gone
    cmp [di+I_SPTR], si         ; ...and it is still the CHOOSER's: a window
    jne .gone                   ; slot is reused, a pool block names one role
    call KERNEL_SEG:cw_app_close_win ; frees the cache claim with the record
.gone:
    mov bx, [fdlg_rqwin]
    call KERNEL_SEG:cw_menu_activate ; the bar goes back to the requester
    call KERNEL_SEG:cw_menu_draw_bar
.out:
    jmp fdk_di

; -----------------------------------------------------------------------------
; fdlg_commit - the answer (SPEC.md 38.6, 38.7 step 7)
; in:  the chooser closed by fdlg_close; the gfx lock held
; out: nothing (all registers preserved)
; -----------------------------------------------------------------------------
fdlg_commit:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov dl, [fdlg_cdrv]         ; the callback's contract: the file's volume
    mov ax, [fdlg_ccwd]         ; is mounted and its folder is current - put
    cmp dl, [disk_drive]        ; them back if anything moved them, which
    jne .cd                     ; costs nothing when nothing did
    cmp ax, [dsk_cwd]
    je .here
.cd:
    FDX dsk_chdir_x
.here:
    mov di, [fdlg_rqrec]        ; THE STALENESS TRIPLE (SPEC.md 38.6)
    or di, di
    jz .out
    cmp byte [di+I_STATE], 1
    jne .out
    mov ax, [fdlg_rqwin]
    cmp ax, [di+I_WIN]
    jne .out
    mov ax, [fdlg_rqsp]
    cmp ax, [di+I_SPTR]
    jne .out
    call fdlg_home_save
    call fdlg_sizeof            ; DX:CX = what the READ will deliver
    mov ax, [fdlg_rqcb]
    or ax, ax
    jz .out
    push word [snd_inst]        ; the callback is the PACKAGE's code, so its
    call KERNEL_SEG:cw_snd_disp_set ; sound stamp is the requester's (34.3)
    push es                     ; the callback owes us nothing (SPEC.md
    push bp                     ; 38.6), and ES is the one register the
    mov bp, ax                  ; kernel cannot shrug off (SPEC.md 1)
    mov al, [fdlg_mode]         ; AL = mode, SI = its window, DI = the name
    mov ah, 0                   ; (ours - for a package DS is its own
    mov si, [fdlg_rqwin]        ; segment and this buffer is in the
    mov di, fdlg_name           ; kernel's, 20.1), DX:CX = the size
    call KERNEL_SEG:cw_wm_pkgcall
    pop bp
    pop es
    pop word [snd_inst]
.out:
    jmp fdk_di

; -----------------------------------------------------------------------------
; fdlg_sizeof - DX:CX = what OSAPI_FILE_READ will deliver for [fdlg_name]
; (SPEC.md 38.6.1): 0 when there is no such file or it is a folder, the
; UNPACKED size when it is compressed. A redirected volume answers the picked
; row's size, because dskw_stat's DVK_FILE arm never writes dskw_raw.
; -----------------------------------------------------------------------------
fdlg_sizeof:
    mov cx, [fdlg_size]
    mov dx, [fdlg_sizeh]
    cmp byte [dsk_vkind], DVK_FILE
    je .ret
    push ax
    push bx
    push si
    xor cx, cx
    xor dx, dx
    mov si, fdlg_name
    push cx
    push dx
    call COLD_SEG:dwf_dskw_stat ; CF=1 = no such name in this folder
    pop dx
    pop cx
    jc .out
    test byte [dskw_raw+DSK_R_ATTR], 0x10
    jnz .out                    ; a folder has no size to report
    mov cx, [dskw_raw+DSK_R_SIZE]
    mov dx, [dskw_raw+DSK_R_SIZE+2]
    mov al, [dskw_raw+DSK_R_CZM] ; ...and the UNPACKED size when the hint
    sub al, DSK_CZ_MARK         ; says it is packed (cmz_sizes' reading)
    cmp al, LZ_LZB
    ja .out
    mov cx, [dskw_raw+DSK_R_CZL]
    mov dl, [dskw_raw+DSK_R_CZH]
    xor dh, dh
.out:
    pop si
    pop bx
    pop ax
.ret:
    ret

; =============================================================================
; THE HOOK (SPEC.md 38.9): files.inc's nine sites, one dispatch
; =============================================================================
; in:  AL = FDH_*, and AH = the button for FDH_BTN. An index is never passed:
;      every route into fm_open_sel opens FS_SEL, so the handlers read that
; out: CF=1 the chooser took it; BX preserved, AX and the rest per handler
; -----------------------------------------------------------------------------
FDBODY fdlg_hook_x
    push bx
    mov bl, al
    mov bh, 0
    add bx, bx                  ; every handler reads what it needs from
    call [cs:fdlg_htab+bx]      ; the block, AH (FDH_BTN) or the layout
    pop bx
    ret

fdlg_htab:
    dw fdlg_h_arm, fdlg_h_bank, fdlg_h_pick, fdlg_h_sel
    dw fdlg_h_commit, fdlg_h_key, fdlg_h_btn, fdlg_h_paint
%ifdef KERN_BIG
    dw fdlg_h_rect, fdlg_h_label
%else
    dw fdlg_h_no, fdlg_h_no, fdlg_h_click, fdlg_h_up
%endif

; FDH_ARM - fm_layout, before it caches FS_EDIT: a Save chooser that is not
; in some other prompt is typing its name (SPEC.md 38.5). CF=0.
fdlg_h_arm:
    cmp byte [fdlg_mode], 0
    je fdlg_h_no
    mov bx, [fdlg_blk]
    cmp byte [bx+FS_EDIT], 0
    jne fdlg_h_no
    ; fall through

; fdlg_toebuf - fdlg_name into the line editor, as mode 8
fdlg_toebuf:
    push si
    push di
    push cx
    mov bx, [fdlg_blk]
    mov byte [bx+FS_EDIT], FM_ESAVE
    mov si, fdlg_name
    mov di, fm_ebuf
    xor bx, bx
.c:
    mov al, [si+bx]
    mov [di+bx], al
    or al, al
    jz .d
    inc bx
    cmp bx, FD_NAMEMAX
    jb .c
    mov byte [di+bx], 0
.d:
    mov [fm_elen], bl
    pop cx
    pop di
    pop si
fdlg_h_no:
    clc
    ret

; FDH_BANK - fm_edit_end, BEFORE it clears the shared buffer: a mode-8 name
; goes back to fdlg_name so the next FDH_ARM restores it. CF=0.
fdlg_h_bank:
    mov bx, [fdlg_blk]
    cmp byte [bx+FS_EDIT], FM_ESAVE
    jne fdlg_h_no
fdlg_bank:
    push si
    push di
    push cx
    mov si, fm_ebuf
    mov di, fdlg_name
    mov cx, FD_NAMEMAX
    FDX fm_ncpy
    pop cx
    pop di
    pop si
    clc
    ret

; fdlg_take - stage entry AX of the chooser's listing as the answer
; out: CF=1 it is a folder (nothing taken); else fdlg_name and fdlg_size
fdlg_take:
    push si
    push di
    push cx
    FDX fm_stage_name           ; fm_name, fm_ftype, fm_fsize
    cmp word [fm_ftype], 2
    cmc                         ; CF=1 exactly for a folder or '..'
    jc .out
    mov si, fm_name
    mov di, fdlg_name
    mov cx, FD_NAMEMAX
    FDX fm_ncpy
    mov cx, [fm_fsize]
    mov [fdlg_size], cx
    mov cx, [fm_fsizeh]
    mov [fdlg_sizeh], cx
    clc
.out:
    pop cx
    pop di
    pop si
    ret

; FDH_PICK - a FILE opened (double-click, Enter, File > Open, the Open
; button) - FS_SEL, which is what every route into fm_open_sel opens. Open form: it is the answer. Save form: it is the
; name in the box, redrawn here because fm_open_sel then reports "quiet".
fdlg_h_pick:
    mov bx, [fdlg_blk]
    mov ax, [bx+FS_SEL]
    call fdlg_take
    cmp byte [fdlg_mode], 0
    je fdlg_post_commit
    call fdlg_toebuf
    push si
    mov si, [fdlg_win]
    FDX fm_status_only
    pop si
    stc
    ret

; FDH_SEL - fm_onclick's new FS_SEL. Save form: a file fills the box (the
; status line is the caller's to redraw - the click ended mode 8, so it is
; owed). Open form: the default button's greying is the selection. CF=0.
fdlg_h_sel:
    mov bx, [fdlg_blk]
    cmp byte [fdlg_mode], 0
    je .open
    mov ax, [bx+FS_SEL]
    cmp ax, [bx+FS_N]
    jae fdlg_h_no
    call fdlg_take
    jc fdlg_h_no
    jmp fdlg_toebuf
.open:
    mov al, FM_BGO
    call fdlg_drawbtn
    clc
    ret

; FDH_COMMIT - Enter in the Save form's box. CF=1 either way.
fdlg_h_commit:
    call fdlg_bank
fdlg_save:
    cmp byte [fdlg_name], 0
    jne fdlg_post_commit
fdlg_beep:
    FDK cw_snd_beep             ; an empty box answers nothing
    stc
    ret

; FDH_KEY - DX = the key, DL the ASCII and DH the scan (fm_onkey_x's AL/AH).
; Escape cancels, unless some OTHER prompt is open in the chooser (a Rename, a
; New Folder), whose own Escape it is. Anything else is the Disk window's -
; the arrows SCROLL, as they do in every Disk window. CF=1 taken.
;
; On kern_big the arrows MOVE A SELECTION in every Disk window, this one
; included (SPEC.md 22.26): that is files.inc's, and arrives here only as
; FDH_SEL. kern_small's scroll, because its Disk window is resident and the
; bytes are not worth it there (SPEC.md 38.4).
fdlg_h_key:
    mov bx, [fdlg_blk]
    mov al, [bx+FS_EDIT]
    or al, al
    jz .mine
    cmp al, FM_ESAVE
    jne fdlg_h_no               ; another prompt owns the keyboard
.mine:
    cmp dl, 27
    jne fdlg_h_no               ; ...and Escape falls into the cancel below

fdlg_post_cancel:
    mov al, FDA_CANCEL
    jmp short fdlg_post
fdlg_post_commit:
    mov al, FDA_COMMIT
; fdlg_post - record the answer and wake ui_task; fdlg_reap acts on it
fdlg_post:
    mov [fdlg_act], al
    inc byte [ui_post]
    stc
    ret

; FDH_BTN - AH = FM_BGO / FM_BCANCEL / FM_BDRIVE (kern_small's press enters
; at fdlg_btn with it in AL). CF=1.
fdlg_h_btn:
    mov al, ah
fdlg_btn:
    cmp al, FM_BCANCEL
    je fdlg_post_cancel
    mov bx, [fdlg_blk]
    cmp al, FM_BDRIVE
    je .drive
    cmp byte [fdlg_mode], 0
    jne .save
    mov ax, [bx+FS_SEL]         ; Open: the selection acts - a file is the
    cmp ax, [bx+FS_N]           ; answer (back through FDH_PICK), a folder is
    jae fdlg_beep               ; entered, nothing selected refuses
    FDX fm_open_sel
    jnc .done
.paint:
    push si
    mov si, [fdlg_win]
    FDX fm_repaint
    pop si
.done:
    stc
    ret
.save:
    cmp byte [bx+FS_EDIT], FM_ESAVE
    jne .saved                  ; ...the box was banked when the edit ended
    call fdlg_bank
.saved:
    jmp fdlg_save
.drive:
    call fdlg_nextvol           ; DL = the next live volume (SPEC.md 38.11)
    FDX fm_mount
    jmp short .paint

; -----------------------------------------------------------------------------
; fdlg_nextvol - DL = the next live volume after the chooser's own, wrapping
; (SPEC.md 38.11). A machine with one live volume answers that volume.
; -----------------------------------------------------------------------------
fdlg_nextvol:
    push bx
    push cx
    mov bx, [fdlg_blk]
    mov dl, [bx+FS_DRV]
    mov cl, DVOL_MAX
.next:
    inc dl
    cmp dl, DVOL_MAX
    jb .test
    xor dl, dl
.test:
    mov bl, dl
    FDX dsk_vol_slot_x          ; BX -> the row; CF = out of range
    jc .skip
    cmp byte [bx+DV_KIND], DVK_FREE
    jne .out
.skip:
    dec cl
    jnz .next
.out:
    pop cx
    pop bx
    ret

; =============================================================================
; THE BUTTON COLUMN (SPEC.md 38.3)
; =============================================================================
; fdlg_brect - os88ui_krect = button AL's rect (FM_BGO..FM_BDRIVE), off the
; layout cache. CF=0; all registers preserved. kern_big's fm_brect hands its
; ids above FM_BVIEW here, so both builds place the column identically.
fdlg_brect:
    push ax
    mov ah, 20
    sub al, FM_BGO
    mul ah                      ; AX = 20 * row
    add ax, [fm_cy]
    add ax, 2
    mov [os88ui_krect+2], ax
    add ax, FM_BTN_H-1
    mov [os88ui_krect+6], ax
    mov ax, [fm_rgt]
    add ax, 5
    mov [os88ui_krect+0], ax
    add ax, FM_BTN_W-1
    mov [os88ui_krect+4], ax
    pop ax
    clc
    ret

%ifdef KERN_BIG
; FDH_RECT / FDH_LABEL - kern_big's fm_brect and fm_btn1 asking about id AH
fdlg_h_rect:
    mov al, ah
    jmp short fdlg_brect
fdlg_h_label:
    mov al, ah
    jmp short fdlg_blabel
%endif

; fdlg_blabel - SI = button AL's label, DI = its OS88UI_* flags: the first is
; the default, and greyed in the Open form with nothing selected (SPEC.md 47)
fdlg_blabel:
    mov di, OS88UI_FILL
    mov si, fdlg_s_cancel
    cmp al, FM_BCANCEL
    je .out
    mov si, fdlg_s_drive
    ja .out
    mov di, OS88UI_FILL | OS88UI_DEF
    mov si, fdlg_s_save
    cmp byte [fdlg_mode], 0
    jne .out
    mov si, fdlg_s_topen
    push bx
    mov bx, [fdlg_blk]
    cmp word [bx+FS_SEL], 0xFFFF
    pop bx
    jne .out
    or di, OS88UI_DIS
.out:
    ret

; fdlg_drawbtn - draw button AL (all registers preserved)
fdlg_drawbtn:
%ifdef KERN_BIG
    FDX fm_btn1                 ; the Disk window's own: pressed look and all
    ret
%else
    push bx
    push si
    push di
    call fdlg_brect
    call fdlg_blabel
    cmp al, [fdlg_down]         ; the one being held (SPEC.md 13.8.3)
    jne .up
    or di, OS88UI_DOWN
.up:
    mov bx, os88ui_krect
    FDX os88ui_kbtn
    pop di
    pop si
    pop bx
    ret
%endif

; FDH_PAINT - fm_draw_core's end: the whole column. CF=0.
fdlg_h_paint:
    mov al, FM_BGO
.l:
    call fdlg_drawbtn
    inc al
    cmp al, FM_BDRIVE
    jbe .l
    clc
    ret

%ifdef KERN_SMALL
; FDH_CLICK - kern_small's press: ARM and draw pressed, nothing more - the
; release fires (SPEC.md 13.7), exactly as kern_big's ids 3-5 do through
; fm_onup_x. CF=1 a button took it.
fdlg_h_click:
    push cx
    push dx
    mov cx, [fm_pressx]
    mov dx, [fm_pressy]
    mov al, FM_BGO
.l:
    call fdlg_brect
    push bx
    mov bx, os88ui_krect
    FDX os88ui_bhit
    pop bx
    jnc .hit
    inc al
    cmp al, FM_BDRIVE
    jbe .l
    pop dx
    pop cx
    clc
    ret
.hit:
    pop dx
    pop cx
    mov [fdlg_down], al         ; the ARM and the pressed look are one byte:
                                ; kern_small carries no os88ui_armw
    call fdlg_drawbtn
    stc
    ret

; FDH_UP - the release, from fdlg_onup with CX/DX = the point. What was armed
; is SPENT first (13.7's second rule: a release anywhere disarms), the button
; comes back up, and it fires only if the pointer is still on it.
fdlg_h_up:
    push cx                     ; a W_ONMOUSEUP gives every register back
    push dx
    push si
    push di
    xor ax, ax                  ; take it and clear it, os88ui_fire's shape
    xchg al, [fdlg_down]
    or al, al
    jz .out
    mov si, [fdlg_win]
    push bx
    mov bx, si
    FDX fm_layout               ; the layout cache, for THIS window
    pop bx
    call fdlg_drawbtn           ; up again
    call fdlg_brect
    push bx
    mov bx, os88ui_krect
    FDX os88ui_bhit
    pop bx
    jc .out                     ; slid off: thought better of
    call fdlg_btn
.out:
    pop di
    pop si
    pop dx
    pop cx
    clc
    ret
%endif

; =============================================================================
; .bss
; =============================================================================
section .bss

fdlg_mode:  resb 1              ; 0 = Open, 1 = Save
fdlg_ttl:   resw 1              ; its caption, for fm_kinit to adopt
fdlg_act:   resb 1              ; the posted answer: 0, FDA_COMMIT, FDA_CANCEL
fdlg_rqwin: resw 1              ; the requester's window...
fdlg_rqcb:  resw 1              ; ...its near completion proc...
fdlg_rqrec: resw 1              ; ...its instance record...
fdlg_rqsp:  resw 1              ; ...and that record's I_SPTR: the staleness
                                ; triple of SPEC.md 38.6
fdlg_name:  resb FD_NAMEMAX+1   ; the answer, and the Save box between edits
fdlg_size:  resw 1              ; the picked row's size, lo...
fdlg_sizeh: resw 1              ; ...and hi (a redirected volume's answer)
fdlg_sdrv:  resb 1              ; where the chooser OPENED...
fdlg_scwd:  resw 1
fdlg_cdrv:  resb 1              ; ...and where it stood when it closed
fdlg_ccwd:  resw 1
%ifdef KERN_SMALL
fdlg_down:  resb 1              ; the column button drawn pressed, 0 = none
%endif

section .text

section .cold                   ; far entries (SPEC.md 2.6): the resident
                                ; thunks in kernel.asm far-call these, and
                                ; these near-call the bodies above - so every
                                ; routine here keeps its ordinary near `ret`

; --- os88ui.inc IS RESIDENT, and that is what makes the split possible ------
; Its kernel copy is SHARED: apps.inc near-calls ui_krect4, files.inc and
; ctrl.inc draw with it, and os88ui_btn / _arm / _armed / _fire / _krect are
; used by five other files between them. Moving it into FDLG.DRV would take
; the standard controls off every one of them, so it stays here, the image
; far-calls in through the FDXF entries below, and tools/os88ovlchk.py's own
; `EXTRA` table - which files this include as `.cold` - stays true.
%define OS88UI_KERNEL
%define OS88UI_SCROLL          ; SPEC.md 13.10: the Disk window's bar uses it
                               ; OS88UI_SBDRAG - SPEC.md 13.10.5's thumb drag -
                               ; is NOT defined here. It has to be resolved
                               ; before files.inc, which is included first;
                               ; kernel.asm carries it beside WM_ANIM and
                               ; OS88_THEME and says why
%include "os88ui.inc"

; -----------------------------------------------------------------------------
; ui_krect4 - stage a whole inclusive rect into the kernel's ONE button rect
; in:  AX = x1, BX = y1, CX = x2, DX = y2
; out: os88ui_krect filled; ALL registers preserved
;
; os88ui_krect is declared in .bss by os88ui.inc and there is exactly one of
; it, which is legal because every writer is on the UI task under the gfx lock
; (SPEC.md 13). apps.inc's Timer button stages a rect it already holds WHOLE
; and follows it with `mov bx, os88ui_krect / call os88ui_kbtn`.
; -----------------------------------------------------------------------------
ui_krect4:
    mov [os88ui_krect+0], ax
    mov [os88ui_krect+2], bx
    mov [os88ui_krect+4], cx
    mov [os88ui_krect+6], dx
    ret

fdf_fdlg_open:          call fdlg_open_x
                    retf

; -----------------------------------------------------------------------------
; fdlg_hook - files.inc's ONE door into the chooser (SPEC.md 38.1.1, 38.9)
; in:  AL = FDH_*, the rest per event
; out: CF=1 the acting Disk window IS the chooser and it took the event;
;      CF=0 otherwise, with nothing changed
;
; RESIDENT ON BOTH BUILDS, and the compare is on this side for 38.1.1's
; reason: fm_layout raises FDH_ARM on every paint of every Disk window, and a
; window that is not the chooser must not pay a far call to be told so.
; [fdlg_blk] is 0 with no chooser up, and no pool block is at offset 0.
; -----------------------------------------------------------------------------
fdlg_hook:
    push bx
    mov bx, [fm_vp]
    cmp bx, [fdlg_blk]
    pop bx
    jne .no
%ifdef FDLG_MOD
    call far [FDFP + FDE_HOOK*4]
    ret
%else
    jmp fdlg_hook_x
%endif
.no:
    clc
    ret

%ifdef FDLG_MOD
; =============================================================================
; THE RESIDENT HALF (SPEC.md 2.8.1) - kern_small only
; =============================================================================
; fdlg_load - is the image in RAM?
; out: CF=1 it is not. AX and every other register preserved.
fdlg_load:
    push ax
    mov al, MOD_FDLG
    call mod_need
    pop ax
    ret

; --- fdlg_open: the ONE place a human waits, so the ONE place that loads ----
; Its CF=1 already means "refused - one is already up, or the table is full",
; and every caller treats that as "the command does nothing". A module that
; will not load is the same answer.
fdlg_open_x:
    call fdlg_load
    jc .no                      ; CF=1 already: the refusal
    call far [FDFP + FDE_OPEN*4]
.no:
    ret

fdlg_reap_x:
    cmp word [fdlg_win], 0
    je .drop                    ; ALREADY GONE, and the image is what is left
    call far [FDFP + FDE_REAP*4]
    cmp word [fdlg_win], 0
    jne .no                     ; still up - or a callback opened another -
.drop:                          ; so the image stays
    push ax
    mov al, MOD_FDLG
    call mod_drop
    pop ax
.no:
    retf

fdlg_grab_x:
    cmp word [fdlg_win], 0
    je .no
    call far [FDFP + FDE_GRAB*4]
    retf
.no:
    clc                         ; fdlg_gate's `.none` answer: nothing to
    retf                        ; swallow, so the press passes through

fdlg_top_x:
    cmp word [fdlg_win], 0
    je .no
    call far [FDFP + FDE_TOP*4]
.no:
    retf                        ; BX unchanged, which is wm_top's own answer

; fdlg_onup - the chooser's W_ONMOUSEUP (SPEC.md 38.3). Installed only on
; the chooser's window, which exists only while the image is loaded, so it
; needs no guard of its own
fdlg_onup:
    push ax
    mov al, FDH_UP
    call far [FDFP + FDE_HOOK*4]
    pop ax
    ret

    FDXF fm_ncpy
    FDXF fm_seed
    FDXF fm_stage_name
    FDXF fm_status_only
    FDXF fm_repaint
    FDXF fm_mount
    FDXF fm_open_sel
    FDXF fm_layout
    FDXF dsk_chdir_x
    FDXF dsk_vol_slot_x
    FDXF os88ui_kbtn            ; the column's buttons, drawn by the image
    FDXF os88ui_bhit            ; ...and hit by it (SPEC.md 38.3)
%endif

section .text
