; =============================================================================
; os8088 - HDD.DRV / part.inc
;
; The partition table (SPEC.md 52.2) and the window that edits it. The KERNEL
; never sees an MBR: a driver-backed volume's LBAs are volume-relative and
; the base lives in hd_vols, so everything about partitioning is here.
;
; The on-disk shape, at LBA 0:
;
;   0..445    boot code - we write a stub that halts with a message, because
;             os8088 does not boot from a hard disk (SPEC.md 52.9) and a
;             blank 446 bytes is a machine that hangs with no explanation
;   446+16n   four entries:
;               +0  status      80h active / 00h
;               +1  start head
;               +2  start sector in bits 0..5, cylinder bits 8..9 in 6..7
;               +3  start cylinder bits 0..7
;               +4  type        01h FAT12, 04h FAT16 <32MB, 06h FAT16
;               +5  end head / sector / cylinder, the same encoding
;               +8  start LBA, dword
;               +12 sector count, dword
;   510..511  55 AA
;
; Two era conventions are obeyed because DOS reads what we write: the first
; partition starts at LBA = spt (head 1, sector 1, cylinder 0), and every
; partition ends on a cylinder boundary. A partition is capped at 65,535
; sectors by the kernel's own BPB rule 8 - which is also the DOS 3.3 limit -
; so four primaries is the whole offering and an extended chain is not
; implemented.
; =============================================================================

HP_TBL       equ 446            ; where the four entries start
HP_ESZ       equ 16
HP_STATUS    equ 0
HP_SHEAD     equ 1
HP_SSEC      equ 2
HP_SCYL      equ 3
HP_TYPE      equ 4
HP_EHEAD     equ 5
HP_ESEC      equ 6
HP_ECYL      equ 7
HP_LBA       equ 8
HP_SECS      equ 12

HPT_NONE     equ 0x00
HPT_FAT12    equ 0x01
HPT_FAT16S   equ 0x04           ; FAT16 under 32MB - what DOS 3.3 wrote, and
                                ; every partition this driver makes is one
HPT_FAT16B   equ 0x06           ; FAT16 at or over 32MB, and
HPT_FAT16L   equ 0x0E           ; ...the LBA-addressed flavour of it. Both are
                                ; MOUNTABLE even though this driver never
                                ; writes one: another machine's FDISK did, and
                                ; the volume inside is the same FAT16
HP_MAXSEC    equ 65535          ; the kernel's volume ceiling (SPEC.md 18.7)

; --- the partitioner's window ------------------------------------------------
HPW_W        equ 300
HPW_H        equ 150
HPW_R0Y      equ 22             ; first slot row, content-relative
HPW_ROWH     equ 12
HPW_LX       equ 4
HPW_BY       equ 96             ; button row
HPW_BH       equ 16
HPW_CAPY     equ 120
HPW_B0X      equ 4              ; 'New'
HPW_B1X      equ 52             ; 'Delete'
HPW_B2X      equ 124            ; 'Write'
HPW_B3X      equ 188            ; 'Close'
HPW_BW0      equ 40
HPW_BW1      equ 64
HPW_BW2      equ 56
HPW_BW3      equ 56

; -----------------------------------------------------------------------------
; hd_part_load - read the selected device's partition table into hd_mbr
; in:  DI = the device row
; out: CF = 0 and hd_mbr holds a table with a valid signature;
;      CF = 1 = unreadable, and hd_mbr holds a BLANK table instead
; clobbers: flags
;
; A disk with no signature is not an error here - it is a disk nobody has
; partitioned - so the failure path leaves a table the user can edit rather
; than nothing at all. What it must never do is leave the PREVIOUS device's
; table in the buffer, which is why the blank happens before the read.
; -----------------------------------------------------------------------------
hd_part_load:
    push ax
    push bx
    push cx
    push dx
    push es
    call hd_mbr_blank
    push ds
    pop es
    mov bx, hd_mbr
    xor ax, ax
    xor dx, dx
    mov cx, 1
    mov byte [hd_rawop], 0      ; read
    call hd_raw
    jc .bad
    cmp word [hd_mbr+510], 0xAA55
    jne .bad
    mov byte [hd_mbrok], 1
    pop es
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.bad:
    call hd_mbr_blank
    pop es
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; hd_mbr_blank - a table with nothing in it (module internal)
; in:  nothing
; out: hd_mbr = the boot stub, four empty entries and the signature
; clobbers: flags
; -----------------------------------------------------------------------------
hd_mbr_blank:
    push ax
    push cx
    push si
    push di
    push es
    push ds
    pop es
    cld
    mov di, hd_mbr
    mov cx, 256
    xor ax, ax
    rep stosw
    mov si, hd_bootstub
    mov di, hd_mbr
    mov cx, hd_bootstub_end - hd_bootstub
    rep movsb
    mov word [hd_mbr+510], 0xAA55
    mov byte [hd_mbrok], 0
    pop es
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_part_ent - one partition entry's address
; in:  AL = slot (0..3)
; out: SI = the entry
; clobbers: SI (the output), flags
; -----------------------------------------------------------------------------
hd_part_ent:
    push ax
    push dx
    mov ah, HP_ESZ
    mul ah
    add ax, hd_mbr + HP_TBL
    mov si, ax
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_part_used - is a slot in use?
; in:  SI = the entry
; out: CF = 0 in use (a known type and a non-zero length)
; clobbers: flags
; -----------------------------------------------------------------------------
hd_part_used:
    cmp byte [si+HP_TYPE], HPT_NONE
    je .no
    cmp word [si+HP_SECS], 0
    jne .yes
    cmp word [si+HP_SECS+2], 0
    jne .yes
.no:
    stc
    ret
.yes:
    clc
    ret

; -----------------------------------------------------------------------------
; hd_part_isfat - is this slot a FAT volume we could mount?
; in:  SI = the entry
; out: CF = 0 yes; CF = 1 = free, or a type that is not FAT
; clobbers: flags
;
; The TYPE byte, and the type byte only: whether the volume inside is really
; a FAT one is the mount's question, and `osapi_vol_mount` answering CF=1 is
; how a partition that lies gets dropped again (SPEC.md 52.4). Extended
; (05h/0Fh) and FAT32 (0Bh/0Ch) are deliberately not here - the first is a
; chain this driver does not walk and the second is a format this kernel
; does not read.
; -----------------------------------------------------------------------------
hd_part_isfat:
    push ax
    call hd_part_used
    jc .no
    mov al, [si+HP_TYPE]
    cmp al, HPT_FAT12
    je .yes
    cmp al, HPT_FAT16S
    je .yes
    cmp al, HPT_FAT16B
    je .yes
    cmp al, HPT_FAT16L
    je .yes
.no:
    pop ax
    stc
    ret
.yes:
    pop ax
    clc
    ret

; -----------------------------------------------------------------------------
; hd_part_mb - one entry's size in whole MB
; in:  SI = the entry
; out: AX = megabytes
; clobbers: AX (the output), flags
; -----------------------------------------------------------------------------
hd_part_mb:
    push bx
    push cx
    push dx
    mov ax, [si+HP_SECS]
    mov dx, [si+HP_SECS+2]
    mov bx, ax
    mov cl, 11                  ; 2,048 sectors to the megabyte
.shift:
    shr dx, 1
    rcr bx, 1
    dec cl
    jnz .shift
    mov ax, bx
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; hd_part_end - the first LBA past everything already allocated
; in:  DI = the device row
; out: DX:AX = that LBA, aligned up to a cylinder boundary
; clobbers: AX, DX (the outputs), flags
;
; The first partition starts at LBA = spt - head 1, sector 1, cylinder 0 -
; because that is where every DOS-era table put it, and the sectors below it
; are the master boot record's own track.
; -----------------------------------------------------------------------------
hd_part_end:
    push bx
    push cx
    push si
    mov ax, [di+HDD_SPT]        ; the floor: one track in
    xor dx, dx
    mov byte [hd_rowslot], 0    ; the slot index lives in MEMORY: .take below
.slot:                          ; writes CX, and a counter there would go
    push ax                     ; with it
    push dx
    mov al, [hd_rowslot]
    call hd_part_ent
    call hd_part_used
    pop dx
    pop ax
    jc .next
    push ax
    push dx
    mov ax, [si+HP_LBA]         ; this partition's end, exclusive
    mov dx, [si+HP_LBA+2]
    add ax, [si+HP_SECS]
    adc dx, [si+HP_SECS+2]
    mov bx, ax
    mov cx, dx
    pop dx
    pop ax
    cmp cx, dx                  ; keep the highest
    ja .take
    jb .next
    cmp bx, ax
    jbe .next
.take:
    mov ax, bx
    mov dx, cx
.next:
    inc byte [hd_rowslot]
    cmp byte [hd_rowslot], 4
    jb .slot
    call hd_cyl_up              ; ...rounded up to a cylinder boundary
    pop si
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; hd_cyl_up - round a 32-bit LBA up to a cylinder boundary (module internal)
; in:  DX:AX = an LBA, DI = the device row
; out: DX:AX = the next multiple of heads*spt at or above it
; clobbers: AX, DX (the outputs), flags
; -----------------------------------------------------------------------------
hd_cyl_up:
    push bx
    push cx
    push si
    mov bx, ax                  ; BX:SI = the LBA, banked: both multiplies
    mov si, dx                  ; below write DX
    mov ax, [di+HDD_HEADS]
    mul word [di+HDD_SPT]
    mov cx, ax                  ; CX = sectors per cylinder (<= 16,065)
    or cx, cx
    jz .keep
    mov ax, bx
    mov dx, si
    cmp dx, cx
    jae .keep                   ; the quotient would not fit a word: only a
    div cx                      ; corrupt table reaches this
    or dx, dx
    jz .exact
    inc ax
.exact:
    mul cx                      ; DX:AX = the boundary at or above the LBA
    jmp short .out
.keep:
    mov ax, bx
    mov dx, si
.out:
    pop si
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; hd_part_new - fill the first free slot with everything that is left
; in:  DI = the device row
; out: CF = 0 made; CF = 1 = no free slot, or no room worth taking
; clobbers: flags
;
; Capped at HP_MAXSEC, because the kernel's BPB rule 8 refuses a volume whose
; TotSec16 will not fit a word - so a 100MB drive becomes three partitions and
; three drive letters, which is exactly what DOS 3.3 did with one.
; -----------------------------------------------------------------------------
hd_part_new:
    push ax
    push bx
    push cx
    push dx
    push si
    xor cl, cl
.slot:
    mov al, cl
    call hd_part_ent
    call hd_part_used
    jc .free
    inc cl
    cmp cl, 4
    jb .slot
    jmp .no                     ; four primaries and no extended chain
.free:
    push si
    call hd_part_end            ; DX:AX = where it starts
    mov bx, ax
    mov cx, dx
    call hd_dev_secs            ; DX:AX = the whole device
    sub ax, bx                  ; ...minus what is taken = what is left
    sbb dx, cx
    pop si
    jc .no
    or dx, dx
    jnz .cap                    ; more than 65,535 sectors left: take the cap
    cmp ax, [di+HDD_SPT]
    jb .no                      ; less than a track: not worth a letter
    cmp ax, HP_MAXSEC
    jbe .have
.cap:
    mov ax, HP_MAXSEC
.have:
    push ax                     ; AX = the length; BX/CX = the start
    mov word [si+HP_LBA], bx
    mov [si+HP_LBA+2], cx
    mov [si+HP_SECS], ax
    mov word [si+HP_SECS+2], 0
    mov byte [si+HP_TYPE], HPT_FAT16S
    mov byte [si+HP_STATUS], 0
    call hd_part_chs            ; the CHS halves, which DOS reads and we do not
    pop ax
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.no:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; hd_dev_secs - a device's total sectors
; in:  DI = the device row
; out: DX:AX = cyl * heads * spt
; clobbers: AX, DX (the outputs), flags
; -----------------------------------------------------------------------------
hd_dev_secs:
    push bx
    mov ax, [di+HDD_HEADS]
    mul word [di+HDD_SPT]       ; DX:AX, and DX is 0: 255*63 is 16,065
    mul word [di+HDD_CYL]       ; ...so this is a true 32-bit product
    pop bx
    ret

; -----------------------------------------------------------------------------
; hd_part_chs - fill one entry's start and end CHS fields
; in:  SI = the entry, DI = the device row
; out: nothing
; clobbers: flags
;
; The CHS halves must AGREE with the LBA halves under the geometry the drive
; is addressed with, or DOS reads the partition somewhere else entirely. A
; cylinder past 1023 is clamped to the all-ones form every tool of the era
; wrote, which is what says "read the LBA fields instead".
; -----------------------------------------------------------------------------
hd_part_chs:
    push ax
    push bx
    push cx
    push dx
    mov ax, [si+HP_LBA]
    mov dx, [si+HP_LBA+2]
    call hd_lba_chs             ; -> [hd_cyl]/[hd_head]/[hd_sec]
    mov al, [hd_head]
    mov [si+HP_SHEAD], al
    call hd_chs_pack            ; AX = the packed sector/cylinder pair
    mov [si+HP_SSEC], ax
    mov ax, [si+HP_LBA]         ; the LAST sector, not one past it
    mov dx, [si+HP_LBA+2]
    add ax, [si+HP_SECS]
    adc dx, [si+HP_SECS+2]
    sub ax, 1
    sbb dx, 0
    call hd_lba_chs
    mov al, [hd_head]
    mov [si+HP_EHEAD], al
    call hd_chs_pack
    mov [si+HP_ESEC], ax
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_lba_chs - hd_chs against an LBA in registers (module internal)
; in:  DX:AX = the LBA, DI = the device row
; out: [hd_cyl]/[hd_head]/[hd_sec]; a value past the geometry clamps to the
;      1023/255/63 form rather than failing
; clobbers: flags
; -----------------------------------------------------------------------------
hd_lba_chs:
    push ax
    push dx
    mov [hd_lba], ax
    mov [hd_lba+2], dx
    call hd_chs
    jnc .out
    mov word [hd_cyl], 1023
    mov word [hd_head], 254
    mov word [hd_sec], 63
.out:
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_chs_pack - [hd_sec] and [hd_cyl] as the two bytes an entry carries
; in:  [hd_cyl], [hd_sec]
; out: AX = low byte the sector|cylinder-high pair, high byte cylinder low
; clobbers: AX (the output), flags
; -----------------------------------------------------------------------------
hd_chs_pack:
    push cx
    mov cl, [hd_cyl+1]
    shl cl, 1
    shl cl, 1
    shl cl, 1
    shl cl, 1
    shl cl, 1
    shl cl, 1
    and cl, 0xC0
    or cl, [hd_sec]
    mov al, cl
    mov ah, [hd_cyl]
    pop cx
    ret

; -----------------------------------------------------------------------------
; hd_part_write - commit the table in hd_mbr to the device
; in:  DI = the device row
; out: CF = 0 written; CF = 1 = the write failed
; clobbers: flags
;
; ONE sector, and it is the commit: everything before this call edits RAM, so
; a user who changes their mind has changed nothing.
; -----------------------------------------------------------------------------
hd_part_write:
    push ax
    push bx
    push cx
    push dx
    push es
    push ds
    pop es
    mov bx, hd_mbr
    xor ax, ax
    xor dx, dx
    mov cx, 1
    mov byte [hd_rawop], 1      ; write
    call hd_raw
    pop es
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; The partitioner's window (SPEC.md 52.2)
;
; A driver's window is an ordinary wm_create'd one that no INSTANCE owns - the
; Standard File dialog's species (SPEC.md 38.1) - so its close box reduces to
; wm_hide and there is no teardown path to write. What there IS is the rule
; that detach must leave none of them on screen, because the kernel frees this
; image the moment detach returns.
; =============================================================================

hd_ptpl:    dw 90, 90, HPW_W, HPW_H, hd_s_ptitle, hd_pw_paint, 0, hd_pw_click
hd_s_ptitle: db 'Partition', 0

; -----------------------------------------------------------------------------
; hd_pw_open - put the partitioner up (module internal)
; in:  nothing; the gfx lock is HELD (a Control Panel click)
; out: nothing
; -----------------------------------------------------------------------------
hd_pw_open:
    push ax
    push bx
    push si
    mov al, [hd_sel]
    call hd_dev_row
    push di
    call hd_part_load           ; a fresh copy every time it opens: the disk
    pop di                      ; can be swapped between two clicks
    mov word [hd_pmsg], hd_s_pready
    mov bx, [hd_pwin]
    or bx, bx
    jnz .show
    mov si, hd_ptpl
    call OSAPI_WM_CREATE
    jc .out
    mov [hd_pwin], bx
.show:
    call OSAPI_WM_SHOW
.out:
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_pw_paint - W_PAINT (content already white-filled, lock held)
; in:  SI = the window
; out: nothing
; -----------------------------------------------------------------------------
hd_pw_paint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp

    mov bx, si
    call OSAPI_WM_CONTENT       ; AX = content left, DX = content top
    mov di, ax
    mov bp, dx

    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov si, hd_s_phdr
    mov cx, di
    add cx, HPW_LX
    mov dx, bp
    add dx, 6
    call OSAPI_FONT_STR

    xor cl, cl
.row:
    push cx
    mov al, cl
    call hd_pw_rowtext          ; hd_line = 'n  TYPE  nnnnM' or 'n  free'
    pop cx
    push cx
    mov ax, cx
    mov ah, HPW_ROWH
    mul ah
    add ax, HPW_R0Y
    mov dx, bp
    add dx, ax                  ; DX = the row's text y
    push dx
    mov al, cl
    cmp al, [hd_psel]
    jne .plain
    pop dx                      ; the selected slot: a black bar under it
    push dx
    push cx
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, di
    add ax, HPW_LX - 2
    mov bx, dx
    dec bx
    mov cx, di
    add cx, HPW_W - 14
    mov dx, bx
    add dx, 9
    call OSAPI_GFX_FILL
    pop cx
    mov al, CWHITE
    call OSAPI_SET_COLOR
    jmp short .text
.plain:
    mov al, CBLACK
    call OSAPI_SET_COLOR
.text:
    pop dx
    mov si, hd_line
    mov cx, di
    add cx, HPW_LX
    call OSAPI_FONT_STR
    pop cx
    inc cl
    cmp cl, 4
    jb .row

    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov si, hd_s_new
    mov ax, HPW_B0X
    mov bx, HPW_BW0
    call hd_pw_button
    mov si, hd_s_del
    mov ax, HPW_B1X
    mov bx, HPW_BW1
    call hd_pw_button
    mov si, hd_s_write
    mov ax, HPW_B2X
    mov bx, HPW_BW2
    call hd_pw_button
    mov si, hd_s_close
    mov ax, HPW_B3X
    mov bx, HPW_BW3
    call hd_pw_button

    mov si, [hd_pmsg]
    mov cx, di
    add cx, HPW_LX
    mov dx, bp
    add dx, HPW_CAPY
    call OSAPI_FONT_STR

    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_pw_button - one framed, labelled button (module internal)
; in:  AX = x, BX = width (both content-relative), SI = the label,
;      DI/BP = the content origin
; out: nothing (all registers preserved)
; -----------------------------------------------------------------------------
hd_pw_button:
    push ax
    push bx
    push cx
    push dx
    push si
    add ax, di                  ; AX = x1
    mov cx, ax
    add cx, bx
    dec cx                      ; CX = x2
    mov bx, bp
    add bx, HPW_BY              ; BX = y1
    mov dx, bx
    add dx, HPW_BH - 1          ; DX = y2
    push ax
    push bx
    push cx
    push dx
    call OSAPI_GFX_FRAME
    pop dx
    pop cx
    pop bx
    pop ax
    add ax, 4                   ; the label, 4px in and centred vertically
    mov cx, ax
    mov dx, bx
    add dx, 4
    call OSAPI_FONT_STR
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_pw_rowtext - one slot's line, into hd_line (module internal)
; in:  AL = slot
; out: hd_line holds a NUL string
; clobbers: flags
; -----------------------------------------------------------------------------
hd_pw_rowtext:
    push ax
    push si
    push di
    mov [hd_rowslot], al
    mov di, hd_line
    add al, '1'
    mov [di], al
    inc di
    mov word [di], '  '
    inc di
    inc di
    mov al, [hd_rowslot]
    call hd_part_ent            ; SI = the entry
    call hd_part_used
    jc .free
    mov si, hd_s_fat16
    call hd_scat                ; appends at DI, and advances it
    mov al, [hd_rowslot]
    call hd_part_ent
    call hd_part_mb             ; AX = megabytes
    call hd_utoa
    mov si, hd_s_mb
    call hd_scat
    jmp short .done
.free:
    mov si, hd_s_free
    call hd_scat
.done:
    mov byte [di], 0
    pop di
    pop si
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_pw_click - W_ONCLICK (absolute screen coords, lock held)
; in:  CX = x, DX = y, SI = the window
; out: nothing
; -----------------------------------------------------------------------------
hd_pw_click:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp

    mov bx, si
    mov si, dx
    call OSAPI_WM_CONTENT
    mov di, ax
    mov bp, dx
    sub cx, di                  ; CX = content-relative x
    mov dx, si
    sub dx, bp                  ; DX = content-relative y

    cmp dx, HPW_BY
    jge .buttons

    mov ax, dx                  ; a slot row?
    sub ax, HPW_R0Y
    jl .done
    mov bl, HPW_ROWH
    div bl                      ; AL = the row, AH = the remainder
    cmp al, 4
    jae .done
    mov [hd_psel], al
    call hd_pw_repaint
    jmp .done

.buttons:
    cmp dx, HPW_BY + HPW_BH
    jge .done
    mov ax, cx
    cmp ax, HPW_B0X
    jl .done
    cmp ax, HPW_B0X + HPW_BW0
    jl .new
    cmp ax, HPW_B1X
    jl .done
    cmp ax, HPW_B1X + HPW_BW1
    jl .del
    cmp ax, HPW_B2X
    jl .done
    cmp ax, HPW_B2X + HPW_BW2
    jl .write
    cmp ax, HPW_B3X
    jl .done
    cmp ax, HPW_B3X + HPW_BW3
    jge .done
    mov bx, [hd_pwin]
    call OSAPI_WM_HIDE
    jmp short .done

.new:
    mov al, [hd_sel]
    call hd_dev_row
    call hd_part_new
    mov word [hd_pmsg], hd_s_pnew
    jnc .repaint
    mov word [hd_pmsg], hd_s_pfull
    jmp short .repaint
.del:
    mov al, [hd_psel]
    call hd_part_ent
    mov byte [si+HP_TYPE], HPT_NONE
    mov word [si+HP_SECS], 0
    mov word [si+HP_SECS+2], 0
    mov word [hd_pmsg], hd_s_pdel
    jmp short .repaint
.write:
    mov al, [hd_sel]
    call hd_dev_row
    call hd_part_write
    mov word [hd_pmsg], hd_s_pwrote
    jnc .repaint
    mov word [hd_pmsg], hd_s_pwerr
.repaint:
    call hd_pw_repaint
.done:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_pw_repaint - redraw the partitioner's content (module internal)
; in:  nothing; the lock is held
; out: nothing (all registers preserved)
; -----------------------------------------------------------------------------
hd_pw_repaint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov bx, [hd_pwin]
    or bx, bx
    jz .out
    call hd_win_erase           ; the CONTENT, and only the content
    mov si, [hd_pwin]
    call hd_pw_paint
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

hd_s_phdr:   db 'Slot  Type       Size', 0
hd_s_fat16:  db 'FAT16  ', 0
hd_s_free:   db '(free)', 0
hd_s_mb:     db 'M', 0
hd_s_new:    db 'New', 0
hd_s_del:    db 'Delete', 0
hd_s_write:  db 'Write', 0
hd_s_close:  db 'Close', 0
hd_s_pready: db 'New adds one; Write commits them', 0
hd_s_pnew:   db 'Added - Write commits it', 0
hd_s_pfull:  db 'No free slot or no room left', 0
hd_s_pdel:   db 'Cleared - Write commits it', 0
hd_s_pwrote: db 'Partition table written', 0
hd_s_pwerr:  db 'Could not write the table', 0

; The MBR's boot code. os8088 does not boot from a hard disk (SPEC.md 52.9),
; and 446 blank bytes is a machine that hangs with no explanation - so this
; says so and stops.
hd_bootstub:
    db 0xFA                     ; cli
    db 0xFC                     ; cld
    db 0x31, 0xC0               ; xor ax, ax
    db 0x8E, 0xD8               ; mov ds, ax
    db 0xBE, 0x1B, 0x7C         ; mov si, msg (0x7C00 + 27)
    db 0xAC                     ; lodsb
    db 0x08, 0xC0               ; or al, al
    db 0x74, 0x06               ; jz halt
    db 0xB4, 0x0E               ; mov ah, 0x0E
    db 0xCD, 0x10               ; int 0x10
    db 0xEB, 0xF5               ; jmp lodsb
    db 0xF4                     ; halt: hlt
    db 0xEB, 0xFD               ; jmp halt
    db 'Not bootable', 13, 10, 0
hd_bootstub_end:
