; =============================================================================
; os8088 - HDD.DRV / cfg.inc
;
; HDD.CFG (SPEC.md 52.6): the driver's own settings file, in the system disk's
; root, written through the ordinary file API. It carries two things, and both
; are things the driver cannot re-derive:
;
;   - the geometry of a drive the PROBE could not determine and the user typed
;     in. Losing it means typing it again at every boot.
;   - which drives were MOUNTED. A hard disk the user mounted is a hard disk
;     the user expects to find on the desktop next time.
;
; **It is the DRIVER's file and not SYSTEM.CFG's business.** SYSTEM.CFG's key
; table is kernel .text (SPEC.md 51.5), so putting a driver's settings in it
; would put a driver's settings in the kernel - which is the thing this whole
; subsystem is arranged not to do.
;
; The format is a signature and a WHOLE-FILE version, not SYSTEM.CFG's keyed
; records, and the difference is proportionate rather than lazy: that file has
; many independent settings and several kernel versions reading each other's
; work, while this one has a single owner that rewrites it entire on every
; change. The rule it borrows is the one that matters - **a version that does
; not match exactly means the defaults**, so changing the shape is a bump and
; never a misread.
;
;   +0   'O88HDD', 0, 0    the signature, byte for byte
;   +8   dw  version       HDC_VER; anything else = defaults
;   +10  db  count         devices described below, 0..HD_MAXDEV
;   +11  db  0
;   +12  count x HDC_ESZ:
;          db kind         HDK_*      } the three that IDENTIFY a device
;          db unit         80h/81h, or 0/1 on its channel
;          dw base         the IDE task file's base port, 0 for a BIOS drive
;          dw cyl
;          dw heads        the geometry to restore
;          dw spt
;          db flags        bit 0 = mount it at boot
;          db 0
;
; **A device is matched by kind+unit+base, never by its row index.** The probe
; runs again at every attach and a machine can gain or lose a drive between
; boots; an index would then restore one drive's geometry onto another's, and
; mount a partition table that belongs to somebody else.
; =============================================================================

HDC_VER      equ 1
HDC_NAME     equ 0              ; (the file name is hd_s_cfgname below)
HDC_COUNT    equ 10
HDC_ENT0     equ 12
HDC_E_KIND   equ 0
HDC_E_UNIT   equ 1
HDC_E_BASE   equ 2
HDC_E_CYL    equ 4
HDC_E_HEADS  equ 6
HDC_E_SPT    equ 8
HDC_E_FLAGS  equ 10
HDC_ESZ      equ 12
HDC_F_MOUNT  equ 1              ; bit 0: this drive was mounted
HDC_FBUF     equ HDC_ENT0 + HD_MAXDEV * HDC_ESZ     ; 60 bytes

; -----------------------------------------------------------------------------
; hd_cfg_save - write the current state to HDD.CFG
; in:  nothing; UI-task context (a Control Panel click)
; out: nothing - a failure is silent here and reported by the caller's caption
; clobbers: flags
;
; **The volume is put back afterwards.** Every file slot resolves in the
; CURRENT volume and directory (SPEC.md 19.2), and by the time this runs that
; may well be the hard disk we just mounted - so it banks the pair with
; OSAPI_FILE_HERE, goes to A:'s root, writes, and goes back. apps/notepad does
; the same thing around every save, for the same reason.
; -----------------------------------------------------------------------------
hd_cfg_save:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es

    call OSAPI_FILE_HERE        ; DX = the current directory, BL = its drive
    mov [hd_cwd], dx
    mov [hd_cdrv], bl
    xor dx, dx                  ; A:'s root, where the system disk lives
    xor bl, bl
    call OSAPI_FILE_GOTO
    jc .out                     ; no readable system disk: nothing to save to

    call hd_cfg_build           ; CX = the file's length
    push ds
    pop es
    mov bx, hd_cfgbuf
    xor dx, dx
    mov si, hd_s_cfgname
    call OSAPI_FILE_WRITE

    mov dx, [hd_cwd]            ; ...and back where we were
    mov bl, [hd_cdrv]
    call OSAPI_FILE_GOTO
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_cfg_build - lay the file out in hd_cfgbuf (module internal)
; in:  nothing
; out: CX = its length
; clobbers: CX (the output), flags
;
; A device earns a record if its geometry was typed in OR it is mounted -
; there is nothing to remember about a drive the probe describes correctly and
; the user has not mounted.
; -----------------------------------------------------------------------------
hd_cfg_build:
    push ax
    push bx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    cld
    mov si, hd_s_cfgsig
    mov di, hd_cfgbuf
    mov cx, 8
    rep movsb
    mov ax, HDC_VER
    stosw
    xor al, al
    stosb                       ; the count, filled in at the end
    stosb                       ; the pad
    mov byte [hd_cfgi], 0
    mov byte [hd_cfgn], 0
.dev:
    mov bl, [hd_cfgi]
    cmp bl, [hd_ndev]
    jae .done
    xor dl, dl
    call hd_dev_mounted         ; BL = the index
    jc .nomount
    mov dl, HDC_F_MOUNT
.nomount:
    mov al, [hd_cfgi]
    push di                     ; DI is the WRITE CURSOR and hd_dev_row
    call hd_dev_row             ; answers in it, so the two have to take
    mov bx, di                  ; turns - BX carries the row from here
    pop di
    test byte [bx+HDD_FLAGS], 2 ; typed in by hand?
    jnz .write
    test dl, dl
    jz .next                    ; probed geometry and not mounted: there is
                                ; nothing about this drive worth a record
.write:
    mov al, [bx+HDD_KIND]
    stosb
    mov al, [bx+HDD_UNIT]
    stosb
    mov ax, [bx+HDD_BASE]
    stosw
    mov ax, [bx+HDD_CYL]
    stosw
    mov ax, [bx+HDD_HEADS]
    stosw
    mov ax, [bx+HDD_SPT]
    stosw
    mov al, dl
    stosb
    xor al, al
    stosb
    inc byte [hd_cfgn]
.next:
    inc byte [hd_cfgi]
    jmp short .dev
.done:
    mov al, [hd_cfgn]
    mov [hd_cfgbuf+HDC_COUNT], al
    mov cx, di
    sub cx, hd_cfgbuf
    pop es
    pop di
    pop si
    pop dx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_dev_mounted - does device index BL have a volume up? (module internal)
; in:  BL = the device index
; out: CF = 0 yes, CF = 1 no
; clobbers: flags
; -----------------------------------------------------------------------------
hd_dev_mounted:
    push ax
    push cx
    push si
    mov cx, HD_MAXVOL
    mov si, hd_vols
.scan:
    cmp byte [si+HDV_USED], 0
    je .next
    mov al, [si+HDV_DEV]
    cmp al, bl
    je .yes
.next:
    add si, HDV_SIZE
    loop .scan
    pop si
    pop cx
    pop ax
    stc
    ret
.yes:
    pop si
    pop cx
    pop ax
    clc
    ret

; -----------------------------------------------------------------------------
; hd_cfg_load - read HDD.CFG and apply it (SPEC.md 52.6)
; in:  the probe has run; DRVV_READY context, so the API answers us
; out: nothing; geometry restored and [hd_wantmnt] set for the drives to mount
; clobbers: flags
;
; A missing or malformed file means the defaults - the probe's own answers and
; nothing mounted - and never an error. That is `drv_cfg_load`'s rule and the
; reason a freshly built disk boots at all.
; -----------------------------------------------------------------------------
hd_cfg_load:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es

    mov byte [hd_wantmnt], 0
    call OSAPI_FILE_HERE
    mov [hd_cwd], dx
    mov [hd_cdrv], bl
    xor dx, dx
    xor bl, bl
    call OSAPI_FILE_GOTO
    jc .out

    push ds
    pop es
    mov bx, hd_cfgbuf
    mov cx, HDC_FBUF
    xor dx, dx
    mov si, hd_s_cfgname
    call OSAPI_FILE_READ        ; AX = bytes read
    pushf
    push ax
    mov dx, [hd_cwd]            ; the volume goes back BEFORE anything is
    mov bl, [hd_cdrv]           ; applied: a mount below changes it again
    call OSAPI_FILE_GOTO
    pop ax
    popf
    jc .out

    cmp ax, HDC_ENT0
    jb .out
    mov [hd_cfglen], ax
    mov si, hd_cfgbuf
    mov di, hd_s_cfgsig
    mov cx, 8
.sig:
    mov al, [si]
    cmp al, [di]
    jne .out                    ; a foreign file of that name: left alone
    inc si
    inc di
    loop .sig
    cmp word [hd_cfgbuf+8], HDC_VER
    jne .out                    ; another version's shape: the defaults, and
                                ; the next save rewrites it in this one

    mov cl, [hd_cfgbuf+HDC_COUNT]
    xor ch, ch
    jcxz .out
    cmp cl, HD_MAXDEV
    ja .out
    mov si, hd_cfgbuf + HDC_ENT0
.rec:
    push cx
    mov ax, si
    add ax, HDC_ESZ
    sub ax, hd_cfgbuf
    cmp ax, [hd_cfglen]
    ja .recdone                 ; the record would run past what was read
    call hd_cfg_apply
    add si, HDC_ESZ
    pop cx
    loop .rec
    jmp short .out
.recdone:
    pop cx
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_cfg_apply - one saved record onto the device it describes (internal)
; in:  SI = the record
; out: the matching row's geometry restored, and its bit set in [hd_wantmnt]
; clobbers: flags
; -----------------------------------------------------------------------------
hd_cfg_apply:
    push ax
    push bx
    push cx
    push di
    xor bl, bl
.scan:
    cmp bl, [hd_ndev]
    jae .out
    mov al, bl
    call hd_dev_row
    mov al, [si+HDC_E_KIND]     ; matched by WHAT IT IS, never by where it sat
    cmp al, [di+HDD_KIND]       ; in the table last time (see the header)
    jne .next
    mov al, [si+HDC_E_UNIT]
    cmp al, [di+HDD_UNIT]
    jne .next
    mov ax, [si+HDC_E_BASE]
    cmp ax, [di+HDD_BASE]
    jne .next
    mov ax, [si+HDC_E_CYL]      ; the geometry, restored whether the probe
    mov [di+HDD_CYL], ax        ; found one or not: a saved record only
    mov ax, [si+HDC_E_HEADS]    ; exists when the user typed it in or mounted
    mov [di+HDD_HEADS], ax      ; with it, and either way it is the one that
    mov ax, [si+HDC_E_SPT]      ; worked
    mov [di+HDD_SPT], ax
    and byte [di+HDD_FLAGS], 0xFC
    call hd_geom_ok
    jc .nogeom
    or byte [di+HDD_FLAGS], 1
.nogeom:
    test byte [si+HDC_E_FLAGS], HDC_F_MOUNT
    jz .out
    mov cl, bl
    mov al, 1
    shl al, cl                  ; 8086: a variable shift goes through CL
    or [hd_wantmnt], al
    jmp short .out
.next:
    inc bl
    jmp short .scan
.out:
    pop di
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_cfg_automount - mount what the settings said was mounted (SPEC.md 52.6)
; in:  [hd_wantmnt]; DRVV_READY context
; out: nothing
; clobbers: flags
;
; **The volume is put back afterwards**, for hd_cfg_save's reason and one
; more: this runs inside drv_boot, before the desktop's first paint, and the
; rest of the boot expects the system disk to be the current volume. The
; desktop icons appear anyway - osapi_vol_add posts the kernel's own deferred
; repaint (SPEC.md 31.2), which is drained after the first paint.
; -----------------------------------------------------------------------------
hd_cfg_automount:
    push ax
    push bx
    push cx
    push dx
    cmp byte [hd_wantmnt], 0
    je .out
    call OSAPI_FILE_HERE
    mov [hd_cwd], dx
    mov [hd_cdrv], bl
    mov byte [hd_selsave], 0
    mov al, [hd_sel]
    mov [hd_selsave], al
    xor bl, bl
.dev:
    cmp bl, [hd_ndev]
    jae .done
    mov cl, bl
    mov al, 1
    shl al, cl
    test [hd_wantmnt], al
    jz .next
    mov [hd_sel], bl            ; hd_mount works on the SELECTED device, and
    call hd_mount               ; this is the one place that is not a click
.next:
    inc bl
    jmp short .dev
.done:
    mov al, [hd_selsave]
    mov [hd_sel], al
    mov dx, [hd_cwd]            ; the boot goes on with the system disk as
    mov bl, [hd_cdrv]           ; the current volume, exactly as it would
    call OSAPI_FILE_GOTO        ; have without us
    mov word [hd_msg], hd_s_pick
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

hd_s_cfgname: db 'HDD.CFG', 0
hd_s_cfgsig:  db 'O88HDD', 0, 0

; -----------------------------------------------------------------------------
; hd_cfg_flush - save, if anything worth saving has changed
; in:  nothing; UI-task context
; out: nothing
; clobbers: flags
;
; Deferred for cp_flush's reason (SPEC.md 31.8): a floppy write is about a
; second on the floor machine, and a session of nudging the cylinder count
; with the + button must not cost one per click. What spends it is any action
; that USES the geometry - Partition, Format, Mount - plus detach; a mount or
; an unmount saves outright, because the set of mounted drives is what the
; next boot reads.
; -----------------------------------------------------------------------------
hd_cfg_flush:
    cmp byte [hd_dirty], 0
    je .out
    mov byte [hd_dirty], 0
    call hd_cfg_save
.out:
    ret
