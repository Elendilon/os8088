; =============================================================================
; hfidx.inc - the index, and the volume's FSV_* verbs (SPEC.md 120.3, 120.4)
;
; HTTP has no directory listing, so the server carries one: OS88.IDX at the
; prefix, fetched ONCE into a heap claim and every listing answered from it.
; tools/os88httpdrv.py writes it and is the reference reader; every refusal
; here is one of index_parse's.
;
;   header, 16 bytes   'OS88IDX', 0 / dw records / dw 0 / dd serial
;   record, 18 bytes   db[11] the FAT name / db attr (10h = a folder; the
;                      disk's own read-only, hidden and system bits too) /
;                      dw parent / dd size, or for a folder (first, count)
;
; Record 0 is the root; every folder's children are a contiguous run, so a
; listing is a slice and an ordinal is an index into it - FSV_ENUM's stable
; ordinal (SPEC.md 62.9.1) by construction. THE HANDLE IS THE RECORD'S INDEX,
; and 0 is the root's, which is also what "no handle" means to the kernel.
; =============================================================================

HF_MAXREC    equ 896            ; one 16 KB claim: 16 + 18 x 896 = 16,144
HF_IDXKB     equ 16             ; ...the claim's KB, for drv_memk's figure
HF_HDR       equ 16
HF_REC       equ 18
HR_ATTR      equ 11
HR_PAR       equ 12
HR_A         equ 14             ; size low, or a folder's first child
HR_B         equ 16             ; size high, or a folder's child count
HF_DEPTH     equ 16             ; the deepest folder a path is composed for
%if HF_HDR + HF_REC * HF_MAXREC > HF_IDXKB * 1024
  %error "httpfs: HF_MAXREC records do not fit HF_IDXKB"
%endif

; --- hf_rec - AX = a record index -> BX = its offset in the index ----------
hf_rec:
    push ax
    mov bx, ax
    shl bx, 1                   ; 2n
    shl ax, 1
    shl ax, 1
    shl ax, 1
    shl ax, 1                   ; 16n
    add bx, ax
    add bx, HF_HDR
    pop ax
    ret

; -----------------------------------------------------------------------------
; hf_drop_idx - give the index back. clobbers: nothing
; -----------------------------------------------------------------------------
hf_drop_idx:
    push dx
    xor dx, dx
    xchg dx, [hf_iseg]
    or dx, dx
    jz .out
    call OSAPI_MEM_FREE
.out:
    mov word [hf_nrec], 0
    mov word [hf_cwd], 0
    pop dx
    ret

; -----------------------------------------------------------------------------
; hf_fetch - GET OS88.IDX, into a claim of its own, and validate it
; out: CF=0, [hf_iseg]/[hf_nrec] set; CF=1 and AX = an HFE_*, nothing held
;      [hf_err] and [hf_failed] say so for the page either way
; -----------------------------------------------------------------------------
hf_fetch:
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call hf_drop_idx
    call hf_parse
    jc .fail
    push ds
    pop es
    mov si, hf_s_idx
    mov di, hf_path
    mov cx, hf_s_idxl
    cld
    rep movsb
    mov byte [hf_rng], 0
    call hf_get
    jc .fail
    mov ax, HFE_STATUS
    cmp word [hf_status], 200
    jne .drop
    mov ax, HFE_INDEX
    cmp byte [hf_hasl], 0
    je .drop
    cmp word [hf_clen+2], 0
    jne .drop
    mov cx, [hf_clen]
    cmp cx, HF_HDR + HF_REC
    jb .drop
    cmp cx, HF_HDR + HF_REC * HF_MAXREC
    ja .drop
    mov ax, cx
    sub ax, HF_HDR
    xor dx, dx
    mov bx, HF_REC
    div bx
    or dx, dx
    mov dx, HFE_INDEX
    jnz .dropdx
    mov [hf_nwant], ax
    mov ax, cx                  ; the claim, in KB
    add ax, 1023
    mov cl, 10
    shr ax, cl
    call OSAPI_MEM_CLAIM_HI     ; owner = our segment: drv_release sweeps it
    jnc .claimed
    mov ax, HFE_MEM
    jmp short .drop
.claimed:
    mov [hf_tseg], dx
    mov [hf_bseg], dx
    xor ax, ax
    mov [hf_boff], ax
    mov [hf_skip], ax
    mov [hf_skip+2], ax
    mov [hf_prog], al
    mov ax, [hf_clen]
    mov [hf_left], ax
    mov word [hf_left+2], 0
    call hf_body
    jc .free
    call hf_done
    mov es, [hf_tseg]
    call hf_valid
    mov ax, HFE_INDEX
    jc .free
    mov ax, [hf_tseg]
    mov [hf_iseg], ax
    mov ax, [hf_nwant]
    mov [hf_nrec], ax
    mov word [hf_cwd], 0
    mov byte [hf_failed], 0
    mov word [hf_err], 0
    clc
    jmp short .out
.dropdx:
    mov ax, dx
.drop:
    call hf_abort
    jmp short .fail
.free:
    call hf_abort
    mov dx, [hf_tseg]
    call OSAPI_MEM_FREE
.fail:
    mov [hf_err], ax
    mov byte [hf_failed], 1
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

hf_s_idx:   db 'OS88.IDX', 0
hf_s_idxl   equ $ - hf_s_idx
hf_s_magic: db 'OS88IDX', 0

; -----------------------------------------------------------------------------
; hf_valid - ES = a fetched index of [hf_nwant] records -> CF=1 = refuse it
; clobbers: AX, BX, CX, DX, SI, DI
;
; EVERYTHING HERE IS HOSTILE, and every check is what makes a later walk
; bounded: a parent below its child is what stops a path walk going round, a
; folder run inside the table is what stops a listing reading past the claim,
; and a run whose every member names the folder is what makes the listing and
; the parent pointers one tree and not two.
; -----------------------------------------------------------------------------
hf_valid:
    mov si, hf_s_magic
    xor di, di
    mov cx, 8
    cld
    repe cmpsb
    jne .bad
    mov cx, [hf_nwant]
    cmp [es:8], cx
    jne .bad
    cmp word [es:10], 0
    jne .bad
    mov bx, HF_HDR
    test byte [es:bx+HR_ATTR], 0x10
    jz .bad
    cmp word [es:bx+HR_PAR], 0
    jne .bad
    xor ax, ax                  ; AX = this record's index, BX its offset
.r:
    test byte [es:bx+HR_ATTR], 0x10
    jz .self
    mov si, [es:bx+HR_B]        ; a folder: its run...
    or si, si
    jz .self
    mov di, [es:bx+HR_A]
    or di, di
    jz .bad                     ; ...starts past the root...
    cmp di, cx
    jae .bad
    mov dx, cx
    sub dx, di
    cmp si, dx
    ja .bad                     ; ...and ends inside the table...
    push bx
    push ax
    mov ax, di
    call hf_rec
    pop ax
.kid:
    cmp [es:bx+HR_PAR], ax      ; ...and every member names this folder
    jne .badkid
    add bx, HF_REC
    dec si
    jnz .kid
    pop bx
.self:
    or ax, ax
    jz .next                    ; the root has no parent and no name
    mov dx, [es:bx+HR_PAR]
    cmp dx, ax
    jae .bad
    push bx
    push ax
    mov ax, dx
    call hf_rec
    test byte [es:bx+HR_ATTR], 0x10
    pop ax
    pop bx
    jz .bad                     ; a parent that is a file
    cmp byte [es:bx], ' '
    je .bad
    push cx
    mov cx, 11
    mov si, bx
.nm:
    mov dl, [es:si]
    inc si
    call hf_chok
    jc .badnm
    loop .nm
    pop cx
.next:
    add bx, HF_REC
    inc ax
    cmp ax, cx
    jb .r
    clc
    ret
.badnm:
    pop cx
    stc
    ret
.badkid:
    pop bx
.bad:
    stc
    ret

; --- hf_chok - DL = a name byte -> CF=1 = not one the drive lists. Keeps AX ---
hf_chok:
    push ax
    call .t
    pop ax
    ret
.t:
    cmp dl, ' '
    je .ok
    cmp dl, '0'
    jb .sym
    cmp dl, '9'
    jbe .ok
    cmp dl, 'A'
    jb .sym
    cmp dl, 'Z'
    jbe .ok
.sym:
    push si
    mov si, hf_s_sym
.s:
    lodsb
    or al, al
    jz .no
    cmp al, dl
    jne .s
    pop si
.ok:
    clc
    ret
.no:
    pop si
    stc
    ret

hf_s_sym:   db "$%'-_@~`!(){}^#&", 0    ; os88httpdrv.py's NAME_OK, less A-Z/0-9

; -----------------------------------------------------------------------------
; hf_need - the index, fetched if it is not held
; out: CF=0 and ES = the index; CF=1 and AX = FERR_IO (ES untouched)
; -----------------------------------------------------------------------------
hf_need:
    cmp word [hf_iseg], 0
    jne .have
    cmp byte [hf_url], 0
    je .no
    call hf_fetch
    jc .no
.have:
    mov es, [hf_iseg]
    clc
    ret
.no:
    mov ax, FERR_IO
    stc
    ret

; --- hf_isdir - AX = a handle -> CF=0 a folder in the index (0 is the root) --
;     in: ES = the index. out: BX = its record. CF=1 and AX = FERR_NOENT
hf_isdir:
    cmp ax, [hf_nrec]
    jae .no
    call hf_rec
    test byte [es:bx+HR_ATTR], 0x10
    jz .no
    clc
    ret
.no:
    mov ax, FERR_NOENT
    stc
    ret

; --- hf_isfile - the same, for a file, and 0 is never one ------------------
hf_isfile:
    or ax, ax
    jz .no
    cmp ax, [hf_nrec]
    jae .no
    call hf_rec
    test byte [es:bx+HR_ATTR], 0x10
    jnz .prot
    clc
    ret
.prot:
    mov ax, FERR_PROT           ; a folder is not a file to read
    stc
    ret
.no:
    mov ax, FERR_NOENT
    stc
    ret

; -----------------------------------------------------------------------------
; hf_stage - AX = a record index (ES = the index) -> hf_ent, the SPEC.md 19.1
;            staged entry. clobbers: nothing
; -----------------------------------------------------------------------------
hf_stage:
    push ax
    push bx
    push cx
    push si
    push di
    push es
    push ax
    push es
    push ds
    pop es
    mov di, hf_ent
    xor ax, ax
    mov cx, 16
    cld
    rep stosw
    pop es
    pop ax
    mov [hf_ent+18], ax         ; @18: the handle
    call hf_rec
    mov al, [es:bx+HR_ATTR]     ; @24: the attribute, which FIND reports at
    mov [hf_ent+24], al         ; +13 (SPEC.md 62.9.17.1) - hidden + system
                                ; is how the installer knows KERNEL.SYS
    mov si, bx
    mov di, hf_ent
    call hf_pretty              ; @0: the name
    xor ax, ax
    test byte [es:bx+HR_ATTR], 0x10
    jz .file
    mov al, 2                   ; @16: 2 a folder, and size 0 (SPEC.md 19.1)
    jmp short .type
.file:
    mov cx, [es:bx+HR_A]        ; @20: the size
    mov [hf_ent+20], cx
    mov cx, [es:bx+HR_B]
    mov [hf_ent+22], cx
    cmp word [es:bx+8], 'O8'    ; 1 a package, 0 anything else
    jne .type
    cmp byte [es:bx+10], '8'
    jne .type
    inc ax
.type:
    mov [hf_ent+16], ax
    pop es
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hf_pretty - ES:SI = an 11-byte FAT name -> 'NAME.EXT', NUL, at DS:DI
; out: DI at the NUL. clobbers: AX, CX
; -----------------------------------------------------------------------------
hf_pretty:
    push si
    mov cx, 8
.b:
    mov al, [es:si]
    cmp al, ' '
    je .bend
    mov [di], al
    inc di
    inc si
    loop .b
.bend:
    pop si
    push si
    add si, 8
    cmp byte [es:si], ' '
    je .end
    mov byte [di], '.'
    inc di
    mov cx, 3
.e:
    mov al, [es:si]
    cmp al, ' '
    je .end
    mov [di], al
    inc di
    inc si
    loop .e
.end:
    mov byte [di], 0
    pop si
    ret

; -----------------------------------------------------------------------------
; hf_mkpath - AX = a record (ES = the index) -> [hf_path], its path below the
;             prefix: 'APPS/CALC.O88'. out: CF=1 = deeper than HF_DEPTH
; clobbers: AX, BX, CX, SI, DI
; -----------------------------------------------------------------------------
hf_mkpath:
    mov di, hf_chain
    xor cx, cx
.up:
    or ax, ax
    jz .walked
    cmp cx, HF_DEPTH
    jae .deep
    mov [di], ax
    inc di
    inc di
    inc cx
    call hf_rec
    mov ax, [es:bx+HR_PAR]      ; below it, so this ends (hf_valid)
    jmp short .up
.walked:
    mov si, di                  ; down again from the top
    mov di, hf_path
.dn:
    dec si
    dec si
    mov ax, [si]
    call hf_rec
    push si
    push cx
    mov si, bx
    call hf_pretty
    pop cx
    pop si
    mov byte [di], '/'
    inc di
    loop .dn
    mov byte [di-1], 0          ; the last '/' was never wanted
    clc
    ret
.deep:
    stc
    ret

; -----------------------------------------------------------------------------
; hf_name11 - the NUL 8.3 name at ES:SI (KERNEL_SEG) -> hf_want, eleven
;             bytes, upper case, space padded. clobbers: AX, CX, DI
; -----------------------------------------------------------------------------
hf_name11:
    push si
    push es
    push es
    push ds
    pop es
    mov di, hf_want
    mov al, ' '
    mov cx, 11
    cld
    rep stosb
    pop es
    mov di, hf_want
    mov cx, 8
.b:
    mov al, [es:si]
    inc si
    or al, al
    jz .out
    cmp al, '.'
    je .ext
    jcxz .b                     ; a base past 8 is no name we hold
    call .up
    mov [di], al
    inc di
    dec cx
    jmp short .b
.ext:
    mov di, hf_want + 8
    mov cx, 3
.e:
    mov al, [es:si]
    inc si
    or al, al
    jz .out
    jcxz .e
    call .up
    mov [di], al
    inc di
    dec cx
    jmp short .e
.out:
    pop es
    pop si
    ret
.up:
    cmp al, 'a'
    jb .r
    cmp al, 'z'
    ja .r
    sub al, 0x20
.r:
    ret

; =============================================================================
; THE VERBS. ES = KERNEL_SEG on entry to each (SPEC.md 20.1)
; =============================================================================

; FSV_WRITE, APPEND, DELETE, RENAME, MKDIR, RMDIR: read-only, in FAT's words
hf_wprot:
    mov ax, FERR_WPROT
    stc
    ret

; FSV_DFREE: nothing free, in 512-byte granules
hf_dfree:
    xor ax, ax
    xor dx, dx
    mov bx, 512
    clc
    ret

; -----------------------------------------------------------------------------
; FSV_CHDIR - AX = a folder's handle, 0 = the root. out: CF=0, DX = its
;             parent's handle; CF=1 and AX = a FERR_*. THE ROOT FETCHES THE
;             INDEX: it is what every mount asks first (SPEC.md 120.1)
; -----------------------------------------------------------------------------
hf_chdir:
    push bx
    push es
    push ax
    call hf_need
    pop bx
    jc .out
    mov ax, bx
    call hf_isdir
    jc .out
    mov [hf_cwd], ax
    mov dx, [es:bx+HR_PAR]      ; the root's is 0, which is never read
    clc
.out:
    pop es
    pop bx
    ret

; -----------------------------------------------------------------------------
; FSV_LIST - append the current folder's entries. out: CF=0 - a full listing
;            stops cleanly, and a missing index has been answered by FSV_CHDIR
; -----------------------------------------------------------------------------
hf_list:
    push ax
    push bx
    push cx
    push si
    push es
    call hf_need
    jc .out
    mov ax, [hf_cwd]
    call hf_isdir
    jc .out
    mov cx, [es:bx+HR_B]
    mov ax, [es:bx+HR_A]
    jcxz .out
.e:
    call hf_stage
    test byte [hf_ent+24], 0x06 ; hidden or system: a FAT listing leaves it
    jnz .skip                   ; out (dsk_synth), so the drive does too -
                                ; FSV_ENUM still answers it (SPEC.md 120.4)
    mov si, hf_ent              ; ES:SI - the X stub makes ES our DS
    push ax
    push cx
    call OSAPI_FS_ENT           ; AX = where it landed: not ours to keep
    pop cx
    pop ax
    jc .out                     ; the listing is full
.skip:
    inc ax
    loop .e
.out:
    pop es
    pop si
    pop cx
    pop bx
    pop ax
    clc
    ret

; -----------------------------------------------------------------------------
; FSV_ENUM - AX = a folder's handle, CX = the ordinal, DX:BX = 32 bytes
; out: CF=0 and the entry; CF=1 and AX = 0 past the end, or a FERR_*
; -----------------------------------------------------------------------------
hf_enum:
    push bx
    push cx
    push si
    push di
    push es
    mov [hf_bseg], dx
    mov [hf_boff], bx
    push ax
    call hf_need
    pop bx
    jc .out
    mov ax, bx
    call hf_isdir
    jc .out
    cmp cx, [es:bx+HR_B]
    jae .end
    mov ax, [es:bx+HR_A]
    add ax, cx
    call hf_stage
    mov es, [hf_bseg]
    mov di, [hf_boff]
    mov si, hf_ent
    mov cx, 16
    cld
    rep movsw
    clc
    jmp short .out
.end:
    xor ax, ax
    stc
.out:
    pop es
    pop di
    pop si
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; FSV_STAT - SI = a NUL 8.3 name in KERNEL_SEG, in the current folder
; out: CF=0, AX = the handle, DX:CX = the size, BL = 10h a folder / 0;
;      CF=1 and AX = a FERR_*
; -----------------------------------------------------------------------------
hf_stat:
    push si
    push di
    push es
    call hf_name11              ; (ES = KERNEL_SEG still)
    call hf_need
    jc .out
    mov ax, [hf_cwd]
    call hf_isdir
    jc .out
    mov cx, [es:bx+HR_B]
    mov ax, [es:bx+HR_A]
    jcxz .noent
.e:
    push cx
    call hf_rec
    mov si, hf_want
    mov di, bx
    mov cx, 11
    cld
    repe cmpsb                  ; DS:SI (ours) against ES:DI (the index)
    pop cx
    je .found
    inc ax
    loop .e
.noent:
    mov ax, FERR_NOENT
    stc
    jmp short .out
.found:
    xor dx, dx                  ; BX IS THE RECORD until the last instruction:
    xor cx, cx                  ; BL is the answer, and setting it first read
    test byte [es:bx+HR_ATTR], 0x10 ; the size out of a record 0x10 bytes off
    jnz .dir                    ; a folder: size 0, as its listing says
    mov cx, [es:bx+HR_A]
    mov dx, [es:bx+HR_B]
    xor bl, bl
    jmp short .ok
.dir:
    mov bl, 0x10
.ok:
    clc
.out:
    pop es
    pop di
    pop si
    ret

; -----------------------------------------------------------------------------
; hf_open_file - the start FSV_READ and FSV_READAT share: AX = a handle,
;                DX:BX = the buffer -> CF=0, [hf_fsize] and [hf_path] set
;                (ES = the index); CF=1, AX = a FERR_*, DX = 0
; -----------------------------------------------------------------------------
hf_open_file:
    mov [hf_bseg], dx
    mov [hf_boff], bx
    push ax
    call hf_need
    pop dx
    jc .fail
    mov ax, dx
    call hf_isfile
    jc .fail
    mov dx, [es:bx+HR_A]
    mov [hf_fsize], dx
    mov dx, [es:bx+HR_B]
    mov [hf_fsize+2], dx
    push cx
    push si
    push di
    call hf_mkpath
    pop di
    pop si
    pop cx
    mov ax, FERR_IO
    jc .fail
    clc
    ret
.fail:
    xor dx, dx
    stc
    ret

; --- hf_ioerr - [hf_err] = AX (an HFE_*) -> AX = FERR_IO, DX = 0, CF=1 ------
hf_ioerr:
    mov [hf_err], ax
    call hf_abort
    mov ax, FERR_IO
    xor dx, dx
    stc
    ret

; -----------------------------------------------------------------------------
; FSV_READ - AX = a handle, DX:BX = the buffer, DI:CX = its capacity
; out: CF=0 and DX:AX = the bytes read; CF=1 and AX = a FERR_*
;
; ONE GET, and the capacity checked HERE before it: the loader reaches this
; cell without the kernel's own check (SPEC.md 62.9.18). The body must be the
; index's size to the byte - a tree replaced under a mounted index fails here
; rather than handing over a different file.
; -----------------------------------------------------------------------------
hf_read:
    push bx
    push cx
    push si
    push di
    push es
    call hf_open_file
    jc .out
    mov ax, [hf_fsize+2]
    cmp ax, di
    ja .big
    jb .fits
    mov ax, [hf_fsize]
    cmp ax, cx
    ja .big
.fits:
    mov byte [hf_rng], 0
    call hf_get
    jc .io
    mov ax, HFE_SHORT
    cmp word [hf_status], 200
    jne .io
    call hf_lenis
    jc .io
    mov ax, [hf_fsize]
    mov [hf_left], ax
    mov ax, [hf_fsize+2]
    mov [hf_left+2], ax
    xor ax, ax
    mov [hf_skip], ax
    mov [hf_skip+2], ax
    mov byte [hf_prog], 1       ; the bar is ours to step (SPEC.md 12.8.1)
    call hf_body
    jc .io
    call hf_done
    mov ax, [hf_fsize]
    mov dx, [hf_fsize+2]
    clc
    jmp short .out
.big:
    mov ax, FERR_BIG
    xor dx, dx
    stc
    jmp short .out
.io:
    call hf_ioerr
.out:
    pop es
    pop di
    pop si
    pop cx
    pop bx
    ret

; --- hf_lenis - a Content-Length, if sent, must be [hf_fsize]. CF=1, AX ----
hf_lenis:
    cmp byte [hf_hasl], 0
    je .ok
    mov ax, [hf_clen]
    cmp ax, [hf_fsize]
    jne .no
    mov ax, [hf_clen+2]
    cmp ax, [hf_fsize+2]
    jne .no
.ok:
    clc
    ret
.no:
    mov ax, HFE_SHORT
    stc
    ret

; -----------------------------------------------------------------------------
; FSV_READAT - AX = a handle, DX:BX = the buffer, CX = its capacity, DI:SI =
;              the offset. out: CF=0 and DX:AX = the bytes delivered, 0 at or
;              past the end
;
; A `Range:` GET for exactly what is wanted. A server that answers 200 has
; ignored it: the body is the whole file, so the offset is DRAINED and the
; connection dropped after the bytes wanted - correct on any server, and slow
; only on one that will not range.
; -----------------------------------------------------------------------------
hf_readat:
    push bx
    push cx
    push si
    push di
    push es
    call hf_open_file
    jc .out
    mov [hf_rlo], si
    mov [hf_rlo+2], di
    mov ax, [hf_fsize]          ; what is left past the offset, 32 bits
    mov dx, [hf_fsize+2]
    sub ax, si
    sbb dx, di
    jc .eof
    or dx, dx
    jnz .clamp
    or ax, ax
    jz .eof
    cmp ax, cx
    jbe .take
.clamp:
    mov ax, cx
.take:
    or ax, ax
    jz .eof
    mov [hf_rn], ax
    mov byte [hf_rng], 1
    call hf_get
    jc .io
    xor ax, ax
    mov [hf_skip], ax
    mov [hf_skip+2], ax
    cmp word [hf_status], 206
    je .part
    call hf_lenis               ; 200: the whole file, and Range: ignored
    jc .io
    mov ax, [hf_rlo]
    mov [hf_skip], ax
    mov ax, [hf_rlo+2]
    mov [hf_skip+2], ax
    jmp short .body
.part:
    mov ax, HFE_SHORT
    cmp byte [hf_hascr], 0
    je .io                      ; a 206 that does not say where it starts
    mov dx, [hf_crlo]
    cmp dx, [hf_rlo]
    jne .io
    mov dx, [hf_crlo+2]
    cmp dx, [hf_rlo+2]
    jne .io
    cmp byte [hf_hasl], 0
    je .body
    cmp word [hf_clen+2], 0
    jne .io
    mov dx, [hf_clen]
    cmp dx, [hf_rn]
    jne .io
.body:
    mov ax, [hf_rn]
    mov [hf_left], ax
    mov word [hf_left+2], 0
    mov byte [hf_prog], 0       ; the copy engine steps its own bar
    call hf_body
    jc .io
    cmp word [hf_status], 206   ; a 206 was read whole and may be kept; a
    jne .tail                   ; 200's unread tail means the handle goes
    call hf_done
    jmp short .kept
.tail:
    call hf_abort
.kept:
    mov ax, [hf_rn]
.eof0:
    xor dx, dx
    clc
    jmp short .out
.eof:
    xor ax, ax
    jmp short .eof0
.io:
    call hf_ioerr
.out:
    pop es
    pop di
    pop si
    pop cx
    pop bx
    ret
