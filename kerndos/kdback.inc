; =============================================================================
; kerndos/kdback.inc - the DOS box's back end, SECOND implementation
;
; **THIS FILE IS docs/plans/KERN-DOS-PLAN.md §3's WHOLE CLAIM, made good.**
; That section says the port is *"a second implementation of twenty-two doors
; plus dos_load, and nothing above them changes"* - and `dos_load` turned out
; not to be an exception either (W2), because it reads through `dos_be_read`
; like everything else. So this file is the port, and `apps/dos/dos.asm` is
; included whole and unedited above it.
;
; Each target has the same register contract as the one in `apps/dos/dos.asm`
; - that is what makes them interchangeable - and goes to the kernel's own
; disk layer directly instead of through an `OSAPI_*` cell, because there is
; no API table here (docs/plans/KERN-DOS-PLAN.md §4.2) and no UI task whose
; stack to borrow (SPEC.md 96.4.1): kern_dos has one task and `SS` never
; stops being its own.
;
; **WHAT IS REFUSED IS AS MUCH THE DESIGN AS WHAT IS IMPLEMENTED.** A door
; that answers CF=1 here is KERN-DOS-PLAN §6.1's levers in code: one volume
; class, no driver volumes, no copy engine. A DOS program gets a DOS error
; code, which is what it would get from a real DOS asked the same thing on a
; machine that could not do it.
;
; ---------------------------------------------------------------------------
; **SPELL EACH CALL THE WAY `kernel/kernel.asm` SPELLS IT, and check rather
; than assume.** The disk layer is not one calling convention: most of it is
; near, and FOUR of the sixteen routines named below end in `retf` because in
; the kernel they are reached from another segment (SPEC.md 2.6.1) - the
; `_x` suffix does NOT say which, `dskw_read_x` being near and `dsk_find_x`
; far. A near `call` to a `retf` body pops the return address AND two bytes
; of whatever was under it, so the machine carries on in the middle of the
; arena with no fault and nothing on the screen: that is exactly how
; `dos_k_path` presented, twenty steps after `dos_build_psp` had finished
; with it. `COLD_SEG` is `KD_SEG` here (kerndos/kdlayout.inc), so the
; kernel's own spelling assembles unchanged and stays right if either
; segment ever moves.
;
; `tests/unit/t_kdfar.py` is the gate: it reads every target named here out
; of the kernel source, decides near or far from the body, and fails the
; build when a call site here disagrees. Three of the four wrong ones were
; on paths this wave never reached, so nothing but that check would have
; found them before a program did.
; ---------------------------------------------------------------------------
; =============================================================================

section .text

; --- the file verbs ---------------------------------------------------------
; in: SI = name, ES:BX = buffer, DX:CX = capacity; out DX:AX = bytes read
dos_k_read:
    call dskw_read_x
    ret

; in: SI = name, ES:BX = buf, CX = cap, DX:AX = offset; out DX:AX = delivered
dos_k_rdat:
    call dskw_read_at_x
    ret

; in: SI = name, ES:BX = bytes, DX:CX = count
dos_k_write:
    call dskw_write_x
    ret

; in: SI = name, ES:BX = bytes, CX = count
dos_k_append:
    call dskw_append_x
    ret

; in: SI = name, ES:BX = bytes, CX = count, DX:AX = offset
dos_k_wrat:
    call dskw_write_at_x
    ret

dos_k_delete:
    call dskw_delete_x
    ret

dos_k_mkdir:
    call dskw_mkdir_x
    ret

; in: SI = a name, AL = 0 strict
dos_k_rmdir:
    call dskw_rmdir
    ret

; in: SI = the old name, DI = the new, both in the current directory
dos_k_rename:
    call dskw_rename_x
    ret

; --- where we are, and what is here -----------------------------------------
; in: DX = dir cluster, BL = volume.  The kernel's slot moves an INSTANCE and
; this moves the machine, which here are the same thing: there is one program.
dos_k_goto:
    push ax
    push dx
    mov ax, dx
    mov dl, bl
    call dsk_chdir_x
    pop dx
    pop ax
    ret

; out: DX = where we stand, BL = its drive.  osapi_file_here's `.global` arm,
; which is the one a caller with no instance behind it already took.
dos_k_here:
    mov dx, [dsk_cwd]
    mov bl, [disk_drive]
    clc
    ret

; in: CX = ordinal, ES:DI = an OSAPI_FIND_SZ buffer
dos_k_find:
    call COLD_SEG:dsk_find_x    ; FAR, and kernel.asm:4472 says so
    ret

; out: BX = sectors per cluster
dos_k_dfree:
    call dskw_dfree_x
    ret

; in: ES:DI = a VS_SIZEOF record, CX = its size
dos_k_vstat:
    call COLD_SEG:dwf_dskw_vstat ; FAR. In the kernel this is the same call
                                ; behind an inst_vol_enter that stands the
                                ; machine in the CALLER's volume (SPEC.md
                                ; 19.2.1); there is one caller here and it is
                                ; already standing there, so the bracket is
                                ; what goes and the call is not.
    ret

; in: AL = a volume index; out CF=1 no such volume, else AL/AH = VK_*/VT_*
dos_k_vkind:
    push bx
    mov bl, al                  ; osapi_vol_kind's whole body is this: the
    call dsk_vol_fixed          ; index into BL, and dsk_vol_fixed answers
    pop bx                      ; both halves (a `pop` leaves CF alone)
    ret

; in: ES:DI = a buffer, CX = its size; out CX = the length
dos_k_path:
    call COLD_SEG:dsk_path_x    ; FAR, and kernel.asm:4500 says so
    ret

; --- the refusals, which are KERN-DOS-PLAN 6.1's levers in code -------------
; **A REFUSAL IS A DECISION AND NOT AN OMISSION.** Each of these is a verb the
; file manager owns rather than the file system, or a layer this machine does
; not have; a DOS program asked for it gets the error code a real DOS gives on
; a machine that cannot do it. They are named individually rather than sharing
; one label so that the day one is implemented, the diff says which.
;
; Cut, Copy and Paste are SPEC.md 22.24/22.25's copy engine - the Disk
; window's, with a progress widget and a batch bracket, and 6.1 lever 3 leaves
; the whole of it behind.
dos_k_copy:
dos_k_move:
dos_k_xcopy:
; ...and the store above 1MB (SPEC.md 41), which needs a driver, a CPU tier
; and a probe, none of which a 4.77MHz 8088 has and all of which are
; resident bytes against the 39KB (KERN-DOS-PLAN §1).
dos_k_xcaps:
dos_k_xalloc:
dos_k_xfree:
kd_k_refuse:
    stc
    ret

; -----------------------------------------------------------------------------
; kdb_bevec - the twenty-two doors, as addresses (SPEC.md 96.44.1)
; in:  nothing; out: nothing, every register preserved
;
; kern_dos's half of what `dos_be_bind` is for the box: the core stores a
; `DBE_*` ORDINAL and `dos_be_go` turns it into an address through `dos_bevec`,
; so the core is ONE object and the back end under it is whichever host bound
; itself. `kd_entry` calls this before the mount.
; -----------------------------------------------------------------------------
kdb_bevec:
    push cx
    push si
    push di
    push es
    push ds
    pop es
    mov si, kdb_betab
    mov di, dos_bevec
    mov cx, DBE_NENT
    cld
    rep movsw
    pop es
    pop di
    pop si
    pop cx
    ret

kdb_betab:
    dw dos_k_goto, dos_k_read, dos_k_find, dos_k_rdat, dos_k_write
    dw dos_k_append, dos_k_delete, dos_k_dfree, dos_k_mkdir, dos_k_rmdir
    dw dos_k_xcaps, dos_k_xalloc, dos_k_xfree, dos_k_xcopy, dos_k_rename
    dw dos_k_copy, dos_k_move, dos_k_path, dos_k_vstat, dos_k_wrat
    dw dos_k_here, dos_k_vkind
