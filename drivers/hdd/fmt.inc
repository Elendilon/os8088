; =============================================================================
; os8088 - HDD.DRV / fmt.inc
;
; The FAT formatter (SPEC.md 52.3) and its window. A FAT format, NOT a surface
; format: low-level formatting an MFM surface is vendor-specific interleave
; and defect handling, minutes per drive, and the ST-11M ships its own ROM
; utility that does it correctly (`g=c800:5` from DEBUG).
;
; What it writes, in order, and the order is the safe one - the boot sector
; LAST, so a format interrupted half way leaves a volume nothing will mount
; rather than one that mounts and is wrong:
;
;   the FATs        zeroed, then entry 0 = the media byte and an EOC mark
;   the root dir    zeroed
;   the boot sector the BPB, and it is the commit
;
; The data area is NOT touched, which is what makes a 32MB format a hundred
; sector writes instead of 65,000.
;
; The layout is the FAT specification's own arithmetic, and every term of it
; fits a word because a partition is capped at 65,535 sectors (SPEC.md 18.7):
;
;   TmpVal1 = sectors - (reserved + rootsecs)
;   TmpVal2 = (256 * SecPerClus) + NumFATs        ; FAT16
;           = (512 * SecPerClus / 3) + NumFATs    ; FAT12, 1.5 bytes an entry
;   FATSz   = ceil(TmpVal1 / TmpVal2)
;   clusters = (sectors - (reserved + NumFATs*FATSz + rootsecs)) / SecPerClus
;
; SecPerClus is chosen as the SMALLEST power of two that lands the cluster
; count inside FAT16's legal range, and the search falls back to FAT12 for a
; partition too small to have 4,085 clusters at any cluster size.
; =============================================================================

HF_RSVD      equ 1              ; reserved sectors
HF_NFATS     equ 2
HF_ROOTENT   equ 512            ; the hard-disk convention
HF_ROOTSECS  equ HF_ROOTENT / 16
HF_MEDIA     equ 0xF8           ; fixed disk

; --- BPB offsets inside the sector we build ---------------------------------
HF_B_OEM     equ 3
HF_B_BPS     equ 11
HF_B_SPC     equ 13
HF_B_RSVD    equ 14
HF_B_NFATS   equ 16
HF_B_ROOTN   equ 17
HF_B_TOT16   equ 19
HF_B_MEDIA   equ 21
HF_B_FATSZ   equ 22
HF_B_SPT     equ 24
HF_B_HEADS   equ 26
HF_B_HIDD    equ 28
HF_B_TOT32   equ 32
HF_B_DRVNUM  equ 36
HF_B_BOOTSIG equ 38
HF_B_VOLID   equ 39
HF_B_VOLLAB  equ 43
HF_B_FSTYPE  equ 54

; --- the formatter's window --------------------------------------------------
; Its content is HFW_W-2 wide and HFW_H-TITLE_H-1 tall, and every string below
; fits: 34 characters at HFW_LX. font_str clips to the screen, not to the
; window (SPEC.md 5), so a longer one paints over the border and beyond.
HFW_W        equ 280
HFW_H        equ 120
HFW_LX       equ 4
HFW_L0Y      equ 8
HFW_L1Y      equ 22
HFW_L2Y      equ 36
HFW_BY       equ 62
HFW_BH       equ 16
HFW_CAPY     equ 90
HFW_B0X      equ 4              ; 'Format'
HFW_B1X      equ 76             ; 'Close'
HFW_BW0      equ 64
HFW_BW1      equ 56

; -----------------------------------------------------------------------------
; hd_fmt_plan - choose a cluster size and lay the volume out
; in:  [hd_fsecs] = the partition's sector count
; out: CF = 0 and [hd_fspc]/[hd_ffatsz]/[hd_fclus]/[hd_ftype] filled;
;      CF = 1 = no cluster size makes a legal volume of this size
; clobbers: flags
;
; **Start from a capacity table, not from one sector.** Smallest-cluster-first
; was the old rule - "a cluster is the unit of waste" - and it is true about
; SPACE and expensive about everything else. A 32MB partition came out with
; 512-byte clusters, which is legal and is the worst layout there is: 65,000
; clusters, a 254-sector FAT that the nine-sector window (SPEC.md 18.8) covers
; 3% of, and one FAT entry to walk per 512 bytes of every file. DOS's own
; table (the one in the FAT spec) picks by capacity, and picking the same way
; costs at most one cluster of slack per file while making the FAT four times
; smaller and every chain four times shorter.
;
; The table is a FLOOR, not an answer: the loop below still walks upward from
; it, so a size where the chosen cluster yields too few or too many clusters
; is corrected exactly as before, and FAT12 on a small partition still falls
; out of the same two tests.
; -----------------------------------------------------------------------------
hd_fmt_plan:
    push ax
    push bx
    push cx
    push dx
    call hd_fmt_spc0            ; AX = where to start looking
    mov [hd_fspc], ax
.try:
    call hd_fmt_layout          ; -> [hd_ffatsz], [hd_fclus]
    jc .next
    cmp word [hd_fclus], 4085
    jb .try12                   ; too few for FAT16 at this cluster size:
                                ; a SMALLER cluster is the only thing that
                                ; would add clusters, and we are counting up
    cmp word [hd_fclus], 65525
    jae .next                   ; too many: a bigger cluster it is
    mov byte [hd_ftype], 1      ; FAT16
    jmp short .ok
.try12:
    ; Fewer than 4,085 clusters at this cluster size, and the walk only ever
    ; goes UP - which would yield fewer still. So this partition is FAT12.
    ; Since the start is a capacity floor rather than one sector (hd_fmt_spc0)
    ; that verdict arrives sooner than it used to: a 4MB partition is FAT12
    ; with 1KB clusters now where it was FAT16 with 512-byte ones. Both are
    ; legal, DOS would have said FAT12 too, and it is the smaller FAT.
    cmp word [hd_fclus], 1
    jb .next
    mov byte [hd_ftype], 0
    call hd_fmt_layout12        ; the 1.5-byte entry changes FATSz
    jc .next
    cmp word [hd_fclus], 4085
    jae .next
.ok:
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.next:
    shl word [hd_fspc], 1
    cmp word [hd_fspc], 128
    jbe .try
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; hd_fmt_spc0 - the cluster size to start from, by capacity (SPEC.md 52.3)
; in:  [hd_fsecs] = the partition's sector count
; out: AX = sectors per cluster, a power of two
; clobbers: AX (the output), flags
;
; Microsoft's DskTableFAT16, trimmed to the sizes a 16-bit volume-relative LBA
; can reach (SPEC.md 18.7 caps a partition at 65,535 sectors = 31.99MB), so
; only its first two rows are reachable and the rest would be dead code:
;
;   <= 16MB   (32,680 sectors)   2 sectors, 1KB clusters
;   <= 32MB   (65,535 sectors)   4 sectors, 2KB clusters
;
; A partition too small for FAT16 at 1KB clusters walks DOWN by way of
; hd_fmt_plan's FAT12 branch, which is the same path it always took.
; -----------------------------------------------------------------------------
hd_fmt_spc0:
    mov ax, 2
    cmp word [hd_fsecs], 32680
    jbe .out
    mov ax, 4
.out:
    ret

; -----------------------------------------------------------------------------
; hd_fmt_layout - the FAT16 layout for the current [hd_fspc]
; in:  [hd_fsecs], [hd_fspc]
; out: CF = 0 and [hd_ffatsz], [hd_fclus]; CF = 1 = it does not fit at all
; clobbers: flags
; -----------------------------------------------------------------------------
hd_fmt_layout:
    push ax
    push bx
    push cx
    push dx
    mov ax, [hd_fsecs]
    mov bx, HF_RSVD + HF_ROOTSECS
    cmp ax, bx
    jbe .no
    sub ax, bx                  ; TmpVal1
    mov bx, [hd_fspc]
    mov cl, 8
    shl bx, cl                  ; 256 * SecPerClus (<= 32,768)
    add bx, HF_NFATS            ; TmpVal2
    xor dx, dx                  ; the ceiling in THIRTY-TWO bits: TmpVal1 is
    add ax, bx                  ; nearly 65,535 already and TmpVal1+TmpVal2-1
    adc dx, 0                   ; wraps a word for every cluster size there
    sub ax, 1                   ; is - which read as "no layout fits" for
    sbb dx, 0                   ; every partition over about 32MB
    div bx
    or ax, ax
    jz .no
    mov [hd_ffatsz], ax
    call hd_fmt_clusters
    jc .no
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

; -----------------------------------------------------------------------------
; hd_fmt_layout12 - the same, for FAT12's 1.5-byte entries
; in / out: hd_fmt_layout's
; -----------------------------------------------------------------------------
hd_fmt_layout12:
    push ax
    push bx
    push cx
    push dx
    mov ax, [hd_fsecs]
    mov bx, HF_RSVD + HF_ROOTSECS
    cmp ax, bx
    jbe .no
    sub ax, bx
    mov bx, [hd_fspc]
    mov cl, 9
    shl bx, cl                  ; 512 * SecPerClus
    mov cx, bx
    mov ax, cx
    xor dx, dx
    mov bx, 3
    div bx                      ; (512 * SecPerClus) / 3 - two FAT12 entries
    mov bx, ax                  ; to three bytes
    add bx, HF_NFATS            ; TmpVal2
    mov ax, [hd_fsecs]
    sub ax, HF_RSVD + HF_ROOTSECS
    xor dx, dx                  ; ...and the same 32-bit ceiling
    add ax, bx
    adc dx, 0
    sub ax, 1
    sbb dx, 0
    div bx
    or ax, ax
    jz .no
    mov [hd_ffatsz], ax
    call hd_fmt_clusters
    jc .no
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

; -----------------------------------------------------------------------------
; hd_fmt_clusters - the cluster count the current layout leaves
; in:  [hd_fsecs], [hd_fspc], [hd_ffatsz]
; out: CF = 0 and [hd_fclus]; CF = 1 = the metadata eats the whole partition
; clobbers: flags
; -----------------------------------------------------------------------------
hd_fmt_clusters:
    push ax
    push bx
    push dx
    mov ax, [hd_ffatsz]
    mov bx, HF_NFATS
    mul bx
    or dx, dx
    jnz .no
    add ax, HF_RSVD + HF_ROOTSECS
    jc .no
    mov bx, ax                  ; BX = the first data sector
    mov ax, [hd_fsecs]
    cmp ax, bx
    jbe .no
    sub ax, bx
    xor dx, dx
    div word [hd_fspc]
    mov [hd_fclus], ax
    mov [hd_fdata], bx
    or ax, ax
    jz .no
    pop dx
    pop bx
    pop ax
    clc
    ret
.no:
    pop dx
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; hd_fmt_run - write the volume
; in:  DI = the device row, [hd_fbase] = the partition's first LBA (32-bit),
;      [hd_fsecs] = its length, and hd_fmt_plan has run
; out: CF = 0 written; CF = 1 = a write failed
; clobbers: flags
;
; The BOOT SECTOR IS LAST and that is the whole ordering argument: a format
; interrupted half way leaves a volume nothing will mount, rather than one
; that mounts and is wrong.
; -----------------------------------------------------------------------------
hd_fmt_run:
    push ax
    push bx
    push cx
    push dx
    push si
    push es
    push ds
    pop es

    ; --- the FATs: zeroed, then entry 0's media byte and EOC mark -----------
    call hd_sec_zero
    mov cx, [hd_ffatsz]
    mov bx, HF_RSVD
.fat1:
    push cx
    push bx
    mov ax, bx
    xor dx, dx
    call hd_fmt_wr              ; one zeroed sector at partition LBA AX
    pop bx
    pop cx
    jc .fail
    inc bx
    loop .fat1
    mov cx, [hd_ffatsz]
.fat2:
    push cx
    push bx
    mov ax, bx
    xor dx, dx
    call hd_fmt_wr
    pop bx
    pop cx
    jc .fail
    inc bx
    loop .fat2

    ; --- the root directory ---------------------------------------------------
    mov cx, HF_ROOTSECS
.root:
    push cx
    push bx
    mov ax, bx
    xor dx, dx
    call hd_fmt_wr
    pop bx
    pop cx
    jc .fail
    inc bx
    loop .root

    ; --- FAT[0]: the media byte, and the end-of-chain mark for cluster 1 ----
    call hd_sec_zero
    mov byte [hd_sec0+0], HF_MEDIA
    mov byte [hd_sec0+1], 0xFF
    mov byte [hd_sec0+2], 0xFF
    cmp byte [hd_ftype], 0
    je .f12
    mov byte [hd_sec0+3], 0xFF
.f12:
    mov ax, HF_RSVD
    xor dx, dx
    call hd_fmt_wr
    jc .fail
    mov ax, HF_RSVD
    add ax, [hd_ffatsz]
    xor dx, dx
    call hd_fmt_wr
    jc .fail

    ; --- the boot sector: the commit -----------------------------------------
    call hd_fmt_boot
    xor ax, ax
    xor dx, dx
    call hd_fmt_wr
    jc .fail

    pop es
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.fail:
    pop es
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; hd_fmt_wr - write hd_sec0 at a PARTITION-relative LBA (module internal)
; in:  DX:AX = the LBA inside the partition, DI = the device row
; out: CF = 0 written
; clobbers: flags
; -----------------------------------------------------------------------------
hd_fmt_wr:
    push ax
    push bx
    push cx
    push dx
    push es
    push ds
    pop es
    add ax, [hd_fbase]
    adc dx, [hd_fbase+2]
    mov bx, hd_sec0
    mov cx, 1
    mov byte [hd_rawop], 1      ; write
    call hd_raw
    pop es
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_sec_zero - 512 zero bytes in hd_sec0 (module internal)
; in:  nothing
; out: nothing (all registers preserved)
; -----------------------------------------------------------------------------
hd_sec_zero:
    push ax
    push cx
    push di
    push es
    push ds
    pop es
    cld
    mov di, hd_sec0
    mov cx, 256
    xor ax, ax
    rep stosw
    pop es
    pop di
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_fmt_boot - build the boot sector in hd_sec0 (module internal)
; in:  DI = the device row, the plan, [hd_fbase]
; out: hd_sec0 holds it
; clobbers: flags
;
; BS_jmpBoot MATTERS: os8088's own BPB rule 2 rejects a volume whose first
; byte is not EB or E9 (SPEC.md 18.2), so a formatter that left it blank
; would write a volume its own kernel refuses to mount.
; -----------------------------------------------------------------------------
hd_fmt_boot:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    push di                     ; the device row, for the geometry below
    call hd_sec_zero
    mov byte [hd_sec0+0], 0xEB  ; jmp short 0x3E
    mov byte [hd_sec0+1], 0x3C
    mov byte [hd_sec0+2], 0x90  ; nop
    mov si, hd_s_oem
    mov di, hd_sec0 + HF_B_OEM
    mov cx, 8
    cld
    rep movsb
    mov word [hd_sec0+HF_B_BPS], 512
    mov ax, [hd_fspc]
    mov [hd_sec0+HF_B_SPC], al
    mov word [hd_sec0+HF_B_RSVD], HF_RSVD
    mov byte [hd_sec0+HF_B_NFATS], HF_NFATS
    mov word [hd_sec0+HF_B_ROOTN], HF_ROOTENT
    mov ax, [hd_fsecs]
    mov [hd_sec0+HF_B_TOT16], ax
    mov byte [hd_sec0+HF_B_MEDIA], HF_MEDIA
    mov ax, [hd_ffatsz]
    mov [hd_sec0+HF_B_FATSZ], ax
    pop di
    push di
    mov ax, [di+HDD_SPT]
    mov [hd_sec0+HF_B_SPT], ax
    mov ax, [di+HDD_HEADS]
    mov [hd_sec0+HF_B_HEADS], ax
    mov ax, [hd_fbase]          ; HiddSec: DOS reads it, os8088 does not -
    mov [hd_sec0+HF_B_HIDD], ax ; its volumes start at their own LBA 0
    mov ax, [hd_fbase+2]
    mov [hd_sec0+HF_B_HIDD+2], ax
    mov byte [hd_sec0+HF_B_DRVNUM], 0x80
    mov byte [hd_sec0+HF_B_BOOTSIG], 0x29
    call OSAPI_GET_TICKS        ; a volume serial with no clock behind it:
    mov [hd_sec0+HF_B_VOLID], ax    ; the tick counter is what there is
    mov [hd_sec0+HF_B_VOLID+2], ax
    mov si, hd_s_nolabel
    mov di, hd_sec0 + HF_B_VOLLAB
    mov cx, 11
    rep movsb
    mov si, hd_s_fat16id
    cmp byte [hd_ftype], 0
    jne .id
    mov si, hd_s_fat12id
.id:
    mov di, hd_sec0 + HF_B_FSTYPE
    mov cx, 8
    rep movsb
    mov word [hd_sec0+510], 0xAA55
    pop di
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

hd_s_oem:     db 'OS8088   '    ; 8 bytes; the trailing space is not copied
hd_s_nolabel: db 'NO NAME    '
hd_s_fat16id: db 'FAT16   '    ; the BPB's 8-byte field: NOT terminated, so
hd_s_fat12id: db 'FAT12   '    ; it must never reach font_str
hd_s_f16name: db 'FAT16', 0    ; ...and the display names, which must
hd_s_f12name: db 'FAT12', 0

; =============================================================================
; The formatter's window (SPEC.md 52.3)
; =============================================================================

hd_ftpl:    dw 120, 120, HFW_W, HFW_H, hd_s_ftitle, hd_fw_paint, 0, hd_fw_click
hd_s_ftitle: db 'Format', 0

; -----------------------------------------------------------------------------
; hd_fw_open - put the formatter up (module internal)
; in:  nothing; the gfx lock is HELD
; out: nothing
; -----------------------------------------------------------------------------
hd_fw_open:
    push ax
    push bx
    push si
    mov al, [hd_sel]
    call hd_dev_row
    push di
    call hd_part_load           ; a fresh table: the target list is its slots
    pop di
    mov byte [hd_fsel], 0
    mov word [hd_fmsg], hd_s_fready
    mov bx, [hd_fwin]
    or bx, bx
    jnz .show
    mov si, hd_ftpl
    call OSAPI_WM_CREATE
    jc .out
    mov [hd_fwin], bx
.show:
    call OSAPI_WM_SHOW
.out:
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_fw_paint - W_PAINT
; in:  SI = the window (content white-filled, lock held)
; out: nothing
; -----------------------------------------------------------------------------
hd_fw_paint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov bx, si
    call OSAPI_WM_CONTENT
    mov di, ax
    mov bp, dx

    mov al, CBLACK
    call OSAPI_SET_COLOR

    mov si, hd_s_fhdr
    mov cx, di
    add cx, HFW_LX
    mov dx, bp
    add dx, HFW_L0Y
    call OSAPI_FONT_STR

    call hd_fw_target           ; hd_line = 'Partition n  nnnnM'
    mov si, hd_line
    mov cx, di
    add cx, HFW_LX
    mov dx, bp
    add dx, HFW_L1Y
    call OSAPI_FONT_STR

    call hd_fw_planline         ; hd_line = 'FAT16  2K clusters' or a refusal
    mov si, hd_line
    mov cx, di
    add cx, HFW_LX
    mov dx, bp
    add dx, HFW_L2Y
    call OSAPI_FONT_STR

    mov si, hd_s_fmt
    mov ax, HFW_B0X
    mov bx, HFW_BW0
    call hd_fw_button
    mov si, hd_s_close
    mov ax, HFW_B1X
    mov bx, HFW_BW1
    call hd_fw_button

    mov si, [hd_fmsg]
    mov cx, di
    add cx, HFW_LX
    mov dx, bp
    add dx, HFW_CAPY
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
; hd_fw_button - one framed button, the formatter's row (module internal)
; in:  AX = x, BX = width, SI = label, DI/BP = the content origin
; -----------------------------------------------------------------------------
hd_fw_button:
    push ax
    push bx
    push cx
    push dx
    push si
    add ax, di
    mov cx, ax
    add cx, bx
    dec cx
    mov bx, bp
    add bx, HFW_BY
    mov dx, bx
    add dx, HFW_BH - 1
    push ax
    push bx
    push cx
    push dx
    call OSAPI_GFX_FRAME
    pop dx
    pop cx
    pop bx
    pop ax
    add ax, 4
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
; hd_fw_target - the chosen partition's line, into hd_line (internal)
; -----------------------------------------------------------------------------
hd_fw_target:
    push ax
    push si
    push di
    mov di, hd_line
    mov si, hd_s_fpart
    call hd_scat
    mov al, [hd_fsel]
    inc al
    xor ah, ah
    call hd_utoa
    mov si, hd_s_two
    call hd_scat
    mov al, [hd_fsel]
    call hd_part_ent
    call hd_part_used
    jc .free
    call hd_part_mb
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
; hd_fw_planline - what the plan came out as, into hd_line (internal)
; -----------------------------------------------------------------------------
hd_fw_planline:
    push ax
    push si
    push di
    mov di, hd_line
    call hd_fw_plansel
    jc .none
    mov si, hd_s_f16name
    cmp byte [hd_ftype], 0
    jne .name
    mov si, hd_s_f12name
.name:
    call hd_scat
    mov si, hd_s_two
    call hd_scat
    mov ax, [hd_fspc]
    shr ax, 1                   ; sectors -> KB per cluster (512 bytes each)
    or ax, ax
    jnz .kb
    mov si, hd_s_half
    call hd_scat
    jmp short .clus
.kb:
    call hd_utoa
    mov si, hd_s_k
    call hd_scat
.clus:
    mov si, hd_s_clus
    call hd_scat
    jmp short .done
.none:
    mov si, hd_s_fnofit
    call hd_scat
.done:
    mov byte [di], 0
    pop di
    pop si
    pop ax
    ret

; -----------------------------------------------------------------------------
; hd_fw_plansel - plan the selected partition (module internal)
; in:  [hd_fsel]
; out: CF = 0 and the plan + [hd_fbase]/[hd_fsecs]; CF = 1 = nothing to plan
; clobbers: flags
; -----------------------------------------------------------------------------
hd_fw_plansel:
    push ax
    push si
    mov al, [hd_fsel]
    call hd_part_ent
    call hd_part_used
    jc .no
    mov ax, [si+HP_LBA]
    mov [hd_fbase], ax
    mov ax, [si+HP_LBA+2]
    mov [hd_fbase+2], ax
    mov ax, [si+HP_SECS]
    mov [hd_fsecs], ax
    cmp word [si+HP_SECS+2], 0
    jne .no                     ; past 65,535 sectors: not a volume this
    call hd_fmt_plan            ; kernel can carry (SPEC.md 18.7)
    jc .no
    pop si
    pop ax
    clc
    ret
.no:
    pop si
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; hd_fw_click - W_ONCLICK
; in:  CX = x, DX = y (absolute), SI = the window
; -----------------------------------------------------------------------------
hd_fw_click:
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
    sub cx, di
    mov dx, si
    sub dx, bp

    cmp dx, HFW_L1Y - 2
    jl .done
    cmp dx, HFW_L1Y + 10
    jl .cycle                   ; the target line cycles through the slots
    cmp dx, HFW_BY
    jl .done
    cmp dx, HFW_BY + HFW_BH
    jge .done
    mov ax, cx
    cmp ax, HFW_B0X
    jl .done
    cmp ax, HFW_B0X + HFW_BW0
    jl .format
    cmp ax, HFW_B1X
    jl .done
    cmp ax, HFW_B1X + HFW_BW1
    jge .done
    mov bx, [hd_fwin]
    call OSAPI_WM_HIDE
    jmp short .done

.cycle:
    inc byte [hd_fsel]
    cmp byte [hd_fsel], 4
    jb .repaint
    mov byte [hd_fsel], 0
    jmp short .repaint

.format:
    call hd_fw_plansel
    jc .nofit
    mov al, [hd_sel]
    call hd_dev_row
    mov word [hd_fmsg], hd_s_fdoing
    call hd_fw_repaint          ; say so BEFORE the writes: a 32MB format is
                                ; a hundred sectors and the user should not
                                ; watch a frozen window wonder
    mov al, [hd_sel]
    call hd_dev_row
    call hd_fmt_run
    mov word [hd_fmsg], hd_s_fdone
    jnc .repaint
    mov word [hd_fmsg], hd_s_ferr
    jmp short .repaint
.nofit:
    mov word [hd_fmsg], hd_s_fnofit
.repaint:
    call hd_fw_repaint
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
; hd_fw_repaint - erase and redraw the formatter's content (internal)
; -----------------------------------------------------------------------------
hd_fw_repaint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov bx, [hd_fwin]
    or bx, bx
    jz .out
    call hd_win_erase           ; the CONTENT, and only the content
    mov si, [hd_fwin]
    call hd_fw_paint
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

hd_s_fhdr:    db 'Format a partition as FAT', 0
hd_s_fpart:   db 'Partition ', 0
hd_s_two:     db '  ', 0
hd_s_k:       db 'K', 0
hd_s_half:    db '512-byte', 0
hd_s_clus:    db ' clusters', 0
hd_s_fmt:     db 'Format', 0
hd_s_fready:  db 'Click the line above to pick', 0
hd_s_fdoing:  db 'Writing...', 0
hd_s_fdone:   db 'Formatted - now Mount it', 0
hd_s_ferr:    db 'Write failed', 0
hd_s_fnofit:  db 'No FAT layout fits that partition', 0
