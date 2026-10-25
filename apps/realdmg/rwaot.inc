; =============================================================================
; os8088 - apps/realdmg/rwaot.inc
;
; A PRECOMPILED CARTRIDGE's load (docs/REALDMG-SPEC.md section 20.10): the
; RDG_AOT build of realdmg.asm, one game's package, which tools/gbaot.py's
; `package` writes. Included by realdmg.asm after rdgaot.inc.
;
; THE PARTS (realdmg.asm's table): 0 and 1 the core with the host's code in
; its holes, 2 the view, 3 the block table (16KB, the tokens F000h + n in its
; segment words), 4 the meta with the list after it, and from 5 each code
; image's two 32KB halves, which are OP_SELF: rw_aread reads them into a
; claim of 65KB each (the read lands up to 1,022 bytes past a half's end).
;
; THE META, part 4:
;   0   'RDAOT1'
;   6   db the code images past the core, 7 db the table's mask
;   8   dw the list's entries, 10 dw the relocations
;   12  dw the list's offset in the part, a multiple of 16
;   14  the cartridge's header, 0134h-014Fh (28 bytes)
;   42  the ROM's file name, NUL-terminated (13 bytes)
;   56  dw the list's filter's offset, a multiple of 16 (8KB of zeros:
;       rdg_aotattach builds it)
;   58  the relocations, 4 bytes each: db the image the far jump is in (0 the
;       core), db the image it jumps to | 80h when the site is a switchable
;       bank's (`cmp byte [ss:S_BANK],B / jne +5` first, the jump 8 bytes on),
;       dw the site: the `mov dx,SITE` the host linked over
;
; AN IMAGE THE HEAP CANNOT HOLD IS LEFT ON THE DISK, and what it held is
; interpreted: its table and list entries get offset 0 (rdgaot.inc's miss
; falls to the interpreter at one), and every far jump into it becomes the
; exit it was before the host linked it - `mov dx,SITE / jmp tr_lsite` -
; which tr_link, finding no block, leaves to the interpreter at run time.
; The images are claimed in the order the host wrote them, so what goes is
; the last.
;
; THE CARVE IS PINNED (rwmove.inc's rw_mdecl): the images name the core's
; segment in their far jumps. Every image is a claim that is never declared,
; so it stays put too.
; =============================================================================

RWA_TOKEN       equ 0F000h          ; a segment word the loader has to give
RWA_RELOCS      equ 58

; rw_ameta - at the entry, after op_load: the meta checked against the table
; it came with, and every segment the run needs banked. CF = 1: it is not one
; of ours, and that is said
rw_ameta:
    xor al, al
    call op_seg
    mov [rw_acore], ax
    mov [rw_asega], ax
    mov al, RWA_TABLE
    call op_seg
    mov [rw_atseg], ax
    mov al, RWA_META
    call op_seg
    mov [rw_amseg], ax
    or ax, ax
    jz .bad
    push es
    mov es, ax
    cmp word [es:0], 'RD'
    jne .bad1
    cmp word [es:2], 'AO'
    jne .bad1
    cmp word [es:4], 'T1'
    jne .bad1
    mov al, [es:6]
    cmp al, RWA_MAX
    ja .bad1
    mov [rw_ans], al
    xor ah, ah                      ; the table the package was made with:
    shl ax, 1                       ;   two rows an image
    add ax, RWA_CODE
    cmp al, [op_t_n]
    jne .bad1
    mov al, [es:7]
    mov [rw_ahm], al
    mov ax, [es:8]
    mov [rw_aln], ax
    mov ax, [es:12]
    mov cl, 4
    shr ax, cl
    add ax, [rw_amseg]
    mov [rw_alseg], ax
    mov ax, [es:56]
    mov cl, 4
    shr ax, cl
    add ax, [rw_amseg]
    mov [rw_afseg], ax
    pop es
    clc
    ret
.bad1:
    pop es
.bad:
    mov si, rw_s_ameta
    call rw_toast
    stc
    ret

; rw_aname - launched with no document: the ROM the package was made from,
; in the package's own folder - KIRBY.O88 beside KIRBY.GB is the whole of
; how it is used
rw_aname:
    push es
    mov es, [rw_amseg]
    cmp byte [es:42], 0
    je .r
    mov si, 42
    mov di, rw_name
    mov cx, 13
.c:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    loop .c
    mov byte [rw_name + 13], 0
    mov dx, [rw_pkgdir]
    mov [rw_argdir], dx
    mov al, [rw_pkgvol]
    mov [rw_argvol], al
    mov byte [rw_argpend], 1
.r:
    pop es
    ret

; rw_ahdr - ES = the cartridge's bank 0 (rw_hdrchk's): ZF = 1 when its
; header is the one the package was made from, else SI = why. Every other
; register kept
rw_ahdr:
    push cx
    push di
    push ds
    mov ds, [rw_amseg]
    mov si, 14
    mov di, 0134h
    mov cx, 014Fh + 1 - 0134h
    cld
    repe cmpsb
    pop ds
    mov si, rw_s_other              ; (a mov: ZF stays the compare's)
    pop di
    pop cx
    ret

; rw_aclaim - at the load, before the ROM's plan: a 65KB claim for each code
; image not claimed yet, while the heap has one. Once they are read
; (rw_aread) they are the session's and this does nothing
rw_aclaim:
    cmp byte [rw_afix], 0
    jne .r
.l:
    mov al, [rw_anseg]
    cmp al, [rw_ans]
    jae .r
    mov ax, 65
    call OSAPI_MEM_CLAIM            ; DX = its segment
    jc .r
    mov bl, [rw_anseg]
    xor bh, bh
    shl bx, 1
    mov [rw_aseg + bx], dx
    inc byte [rw_anseg]
    jmp short .l
.r:
    ret

; rw_adrop - the ROM's plan did not fit: the last image claimed given back.
; CF = 1: none to give (or they are read already, and stay)
rw_adrop:
    cmp byte [rw_afix], 0
    jne .no
    cmp byte [rw_anseg], 0
    je .no
    dec byte [rw_anseg]
    mov bl, [rw_anseg]
    xor bh, bh
    shl bx, 1
    xor dx, dx
    xchg dx, [rw_aseg + bx]
    call OSAPI_MEM_FREE
    clc
    ret
.no:
    stc
    ret

; rw_aread - after the plan, on the UI task in the game's folder: every
; image claimed read from the package's own folder (rw_jpart's reason), each
; one that cannot be read given back, and then everything put right
; (rw_afixup). Once a session
rw_aread:
    cmp byte [rw_afix], 0
    jne .r
    mov byte [rw_afix], 1
    push bp
    mov dx, [rw_pkgdir]
    mov bl, [rw_pkgvol]
    call rw_fgo
    jc .fix                         ; (no folder: none of them, interpreted)
    xor bx, bx
.l:
    cmp bl, [rw_anseg]
    jae .back
    push bx
    shl bx, 1
    mov bp, [rw_aseg + bx]
    shr bx, 1
    mov al, bl
    shl al, 1
    add al, RWA_CODE
    call rw_apart                   ; the first half...
    jc .lost
    inc al
    add bp, 800h
    call rw_apart                   ; ...and the second
    jnc .ok
.lost:
    pop bx
    push bx
    shl bx, 1
    xor dx, dx
    xchg dx, [rw_aseg + bx]
    call OSAPI_MEM_FREE
.ok:
    pop bx
    inc bx
    jmp short .l
.back:
    call rw_fback
.fix:
    call rw_afixup
    pop bp
.r:
    ret

; rw_apart - AL = a row, BP = where it goes: the part read there, packed or
; plain (rw_jpart's read, for any row). CF = 1: it could not be. Every
; register but the flags kept; the folder is the package's (rw_fgo)
rw_apart:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov si, op_table + OP_T_ROWS
    xor ah, ah
    mov cl, 3
    shl ax, cl
    add si, ax                      ; SI = the row
    mov es, bp
    mov bx, [si + OP_R_LEN]         ; BX = what it is in memory
    mov cx, bx                      ; (plain: read where it goes)
    xor di, di
    test byte [si + OP_R_FLAG], OP_COMP
    jz .rd
    mov cx, [si + OP_R_ZKB]         ; CX = the packed bytes
    sub bx, cx                      ; BX = R, a sector boundary: where the
    jbe .no                         ;   stream is read, up from where it
    add bx, 511                     ;   expands to
    and bx, ~511
    mov di, bx
.rd:
    push si
    mov ax, [si + OP_R_OFF]         ; DX:AX = the part's byte offset
    mov dx, ax
    push cx
    mov cl, 9
    shl ax, cl
    mov cl, 7
    shr dx, cl
    pop cx
    push cx
    add cx, 511
    and cx, ~511                    ; whole sectors
    mov bx, di
    mov si, op_name
    call OSAPI_FILE_READ_AT         ; DX:AX = the bytes delivered
    pop cx
    pop si
    jc .no
    cmp ax, cx
    jb .no
    test byte [si + OP_R_FLAG], OP_COMP
    jz .ok
    mov dx, [si + OP_R_LEN]
    mov al, [op_table + OP_T_FMT]
    xor ah, ah
    mov si, di                      ; DS:SI = the stream, ES:0 its output
    xor bx, bx
    xor di, di
    push ds
    mov ds, bp
    call OSAPI_DECOMP
    pop ds
    jc .no
.ok:
    clc
    jmp short .r
.no:
    stc
.r:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rw_aimg - AL = an image, 0 the core: AX = its segment, or 0 when it is
; not in memory. Every other register kept
rw_aimg:
    or al, al
    jnz .c
    mov ax, [rw_acore]
    ret
.c:
    cmp al, [rw_anseg]
    ja .none
    push bx
    mov bl, al
    xor bh, bh
    dec bx
    shl bx, 1
    mov ax, [rw_aseg + bx]
    pop bx
    ret
.none:
    xor ax, ax
    ret

; rw_afixup - the far jumps' segments given, or the exit put back where the
; image it jumps to is not here; then every token in the table and the list
; made a segment, or the entry emptied. S_JITSEGA's image chosen
rw_afixup:
    push bp
    push es
    mov es, [rw_amseg]
    mov cx, [es:10]
    mov si, RWA_RELOCS
    jcxz .tab
.rl:
    mov al, [es:si]                 ; the image the jump is in
    call rw_aimg
    or ax, ax
    jz .rn                          ; (not here: nothing in it runs)
    mov bp, ax                      ; BP = its segment
    mov al, [es:si + 1]
    mov dl, al                      ; DL = the form
    and al, 7Fh
    call rw_aimg                    ; AX = the target's, or 0
    mov di, [es:si + 2]             ; DI = the site
    push es
    mov es, bp
    or ax, ax
    jz .unl
    mov bx, di
    test dl, 80h
    jz .b0
    add bx, 8                       ; a bank's site: the jump after the test
.b0:
    mov [es:bx + 3], ax             ; jmp far off:SEG
    jmp short .rp
.unl:
    mov byte [es:di], 0BAh          ; mov dx, SITE...
    mov [es:di + 1], di
    mov byte [es:di + 3], 0E9h      ; ...jmp tr_lsite, as rt_exit wrote it
    mov ax, RDGC_TR_LSITE - 6
    sub ax, di
    mov [es:di + 4], ax
.rp:
    pop es
.rn:
    add si, 4
    loop .rl
.tab:
    mov es, [rw_atseg]              ; the table: (mask + 1) x 256 entries
    mov cl, [rw_ahm]
    xor ch, ch
    inc cx
    xchg cl, ch                     ; CX = x 256
    call .ents
    mov es, [rw_alseg]              ; ...and the list
    mov cx, [rw_aln]
    call .ents
    mov bx, 1                       ; S_JITSEGA: the first image here, or
.sa:                                ;   the core
    cmp bl, [rw_anseg]
    ja .sx
    mov al, bl
    call rw_aimg
    or ax, ax
    jnz .sg
    inc bx
    jmp short .sa
.sg:
    mov [rw_asega], ax
.sx:
    pop es
    pop bp
    ret
.ents:                              ; CX entries at ES:0
    xor di, di
    jcxz .er
.e:
    cmp word [es:di + 4], 0
    je .en
    mov ax, [es:di + 6]
    sub ax, RWA_TOKEN
    cmp ax, RWA_MAX
    ja .en                          ; (a segment already: a second load)
    call rw_aimg
    or ax, ax
    jnz .es
    mov [es:di + 4], ax             ; not here: offset 0, interpreted
    jmp short .en
.es:
    mov [es:di + 6], ax
.en:
    add di, 8
    loop .e
.er:
    ret

; rw_aoton - DS = the view, after rdg_init: what the precompiled machine
; is (aothost.asm's mode 3 says the same to the harness): the table fixed
; and the host's, nothing translated - not even HRAM's code - the control
; transfers looking for translated code, and the table's misses searching
; the list. Every register kept
rw_aoton:
    push ax
    push cx
    mov ax, [cs:rw_asega]
    mov [S_JITSEGA], ax
    mov [S_JITSEG], ax
    mov [S_JITOUT + 2], ax
    mov word [S_JITSEGB], 0
    mov ax, [cs:rw_atseg]
    mov [S_JITHSEG], ax
    mov al, [cs:rw_ahm]
    mov [S_HMASK], al
    mov byte [S_JITNOC], 1
    mov word [S_JITVEC], rw_aotstub
    mov [S_JITVEC + 2], cs
    mov word [S_RESVEC], RDGC_TR_ENTER
    mov byte [S_JITON], 1
    mov byte [S_JITFIX], 1
    mov byte [S_JITPRE], 2
    mov word [S_JITEND], 0
    call rw_jdon
    mov ax, [cs:rw_alseg]
    mov cx, [cs:rw_aln]
    push bx
    mov bx, [cs:rw_afseg]
    call rdg_aotattach
    pop bx
    pop cx
    pop ax
    ret

; rw_jdon - DS = the view: the control transfers look for translated code
; (rdgjit.inc's rt_dispatch with AL = 1): each of RDGC_JDTAB's sites made
; cmp si,8000h / jae - ROM PCs to the table, the rest dispatched
rw_jdon:
    push bx
    push cx
    push si
    push es
    mov es, [S_DISP + 2]            ; the core
    mov si, rw_jdtab
    mov cx, RDGC_JDN
.s:
    mov bx, [cs:si]
    mov word [es:bx], 0FE81h
    mov word [es:bx + 2], 8000h
    mov byte [es:bx + 4], 73h
    inc si
    inc si
    loop .s
    pop es
    pop si
    pop cx
    pop bx
    ret

; the translator's door: nothing is translated, so a block asked for is the
; interpreter's (aothost.asm's h_jitstub)
rw_aotstub:
    RDG_TOHOST
    mov word [S_JITOUT], 0
    jmp rdg_ret
