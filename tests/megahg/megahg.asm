; =============================================================================
; os8088 - tests/megahg/megahg.asm
;
; MEGAHG, a TEST instrument (nothing under tests/ ships): kern_mega's HUGE
; claims MOVED by the pool's compaction and REGROWN past 64KB
; (docs/plans/KERN-MEGA-PLAN.md 14.37) - "if it is free RAM, a program can
; get it in a single claim". A package that says OS88_HIGH | OS88_HIGHMEM,
; so its claims are pool blocks above 1MB and its own region is one too.
;
;   F  fragment: OSAPI_MEM_HUGE claims of H KB (H = a sixth of the free
;      pool, so always over 64KB) and 60KB between them until the pool takes
;      no more, then a tail of ever smaller ones; every claim filled end to
;      end with its own tag. Then OSAPI_DRV_SUSPEND unloads the drivers and
;      the KB their images held at the top are plugged, pairs 1, 3, 5... are
;      freed, and the resume reloads the drivers - top-down, so a driver
;      placed above 1MB lands at the top of the highest HOLE, mid-pool
;   C  one OSAPI_MEM_HUGE claim of EVERY free KB (XMEM_CAPS's figure): bigger
;      than any hole, so only a compaction that moves the huge claims AND the
;      driver's image can place it; filled and read back whole, every
;      survivor read back whole through the selectors it was given, and the
;      drivers unloaded and reloaded once more, which runs each one's own
;      code where the move put it
;   R  regrow: R 100KB with S 60KB above it; R to 300KB (it has to move,
;      and its run with it); to 130KB (a shrink, in place); S freed and R to
;      400KB; then X1 X2 X3 of 200KB above it, X2 freed, and R to EVERY free
;      KB - a grow only a compaction and a move can satisfy - each time R's
;      bytes read back and the new ones written, and X1 and X3 read back
;   E  everything freed, and the pool's free KB what they were at the start
;
; Lines on port E9 (tools/os88bochs.py), and the verdict as a toast too,
; for a machine with no port E9 (86Box):
;   MEGAHG: free KKKK H hhhh            the pool at the start
;   MEGAHG: blk OOOO KKKK WW            the pool's blocks (OSAPI_XMEM_WALK)
;   MEGAHG: frag NN holes free KKKK     the claims taken, the KB left after F
;   MEGAHG: big SSSS kb KKKK ok         phase C
;   MEGAHG: regrow SSSS kb KKKK ok      each regrow (selector and KB after)
;   MEGAHG: ok                          ...the verdict
;   MEGAHG: no CC                       or the step that failed
; CC: 01 the pool is too small; 02 phase C refused; 03 it came back
; conventional (step not 8); 04 phase C's bytes; 05 a survivor's bytes; 06
; the second unload refused; 1x regrow x refused; 2x regrow x's bytes; 30
; X1-X3 refused; 31 X1's bytes; 32 X3's; 40 a leak (free KB not back).
; -DHG_RONLY builds the regrow phase alone, for a kernel phase C fails on.
;
; Run it (KERN-MEGA-PLAN 14.37):
;   OS88_BOCHS_MEGS=4 python3 tools/os88bochs.py sweep --sb --cfg 1 \
;       build/megahg.o88
; and on 86Box's 286-mega, B: a floppy holding it (os88disk.py), opened and
; the package double-clicked: `MEGAHG ok` on the menu bar
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'MEGAHG', hg_entry, 0, OS88_STACK_192 | OS88_HIGH | OS88_HIGHMEM

HG_MAX  equ 20

hg_entry:
    push si
    push di
    push bp
    call OSAPI_XMEM_CAPS            ; --- the pool at the start ------------
    mov [hg_free0], ax
    mov cl, 0x01
    cmp ax, 600
    jb .no
    mov si, hg_s_free
    call hg_say
    call hg_hex4
    push ax
    xor dx, dx
    mov bx, 6
    div bx
    mov bx, ax                      ; H = a sixth
    mov [hg_h], bx
    pop ax
    mov si, hg_s_h
    call hg_say
    mov ax, bx
    call hg_hex4
    call hg_nl
    call hg_walk
%ifdef HG_RONLY                     ; (-DHG_RONLY: the regrow phase alone,
    jmp .rphase                     ; for a kernel phase C already fails on)
%endif
    ; --- F: fill ------------------------------------------------------------
    xor bp, bp                      ; BP = the claims, x2
.fill:
    mov ax, [hg_h]
    test bp, 2
    jz .fsz
    mov ax, 60
.fsz:
    call hg_take
    jnc .fill
.tail:                              ; the tail: halving, each size until it
    mov ax, [hg_h]                  ; stops fitting
.tl:
    shr ax, 1
    jz .tdone
.tl2:
    cmp bp, HG_MAX * 2
    jae .tdone
    push ax
    call hg_take
    pop ax
    jnc .tl2
    jmp short .tl
.tdone:
    mov ax, 1                       ; --- the drivers out, and the KB their
    xor bl, bl                      ; images held at the top plugged, so
    xor di, di                      ; that their reload lands top-down in
    push bp                         ; the highest HOLE below - mid-pool,
    call OSAPI_DRV_SUSPEND          ; among the claims, where only a MOVE
    pop bp                          ; can take it out of the way
    jc .plug
    mov byte [hg_susp], 1
    mov byte [hg_dsus], 1
.plug:
    mov ax, 128
.pl:
    shr ax, 1
    jz .pdone
.pl2:
    cmp bp, HG_MAX * 2
    jae .pdone
    push ax
    call hg_take
    pop ax
    jnc .pl2
    jmp short .pl
.pdone:
    mov [hg_n], bp
    mov cl, 0x01
    cmp bp, 8 * 2                   ; two pairs freed need four pairs taken
    jb .no
    xor bx, bx                      ; --- free pairs 1, 3, 5 ... -----------
.free:
    test bx, 4
    jz .keep
    mov ax, [hg_kb + bx]            ; (the alternating pairs: the tail stays)
    cmp ax, [hg_h]
    je .fr
    cmp ax, 60
    jne .keep
.fr:
    mov dx, [hg_sel + bx]
    call OSAPI_MEM_FREE
    mov word [hg_sel + bx], 0
.keep:
    add bx, 2
    cmp bx, bp
    jb .free
    call hg_resume                  ; the drivers back, into a hole
    call hg_walk
    call OSAPI_XMEM_CAPS
    mov [hg_big], ax
    mov si, hg_s_frag
    call hg_say
    mov ax, bp
    shr ax, 1
    call hg_hex2
    mov si, hg_s_holes
    call hg_say
    mov ax, [hg_big]
    call hg_hex4
    call hg_nl
    ; --- C: every free KB in one claim ---------------------------------------
    mov ax, [hg_big]
    call OSAPI_MEM_HUGE
    mov bx, cx                      ; (the step: CL is the failure's code)
    mov cl, 0x02
    jc .no
    mov [hg_bsel], dx
    mov cl, 0x03
    cmp bx, 8
    jne .nob
    mov ax, [hg_big]
    mov bl, 0x77
    call hg_fill
    call hg_chk
    mov cl, 0x04
    jc .nob
    call hg_chkall
    mov cl, 0x05
    jc .nob
    mov si, hg_s_big
    call hg_say
    mov ax, dx
    call hg_hex4
    mov si, hg_s_kb
    call hg_say
    mov ax, [hg_big]
    call hg_hex4
    mov si, hg_s_ok
    call hg_say
    call hg_nl
    call hg_walk
    call OSAPI_MEM_FREE             ; DX = it
    mov word [hg_bsel], 0
    call hg_freeall
    cmp byte [hg_dsus], 0           ; --- the moved drivers' own code run:
    je .rg                          ; an unload calls each one's detach
    mov ax, 1                       ; through its pair, and the reload
    xor bl, bl                      ; attaches it again
    xor di, di
    call OSAPI_DRV_SUSPEND
    mov cl, 0x06
    jc .no
    mov byte [hg_susp], 1
    call hg_resume
    mov si, hg_s_drv
    call hg_say
    call hg_nl
.rg:
    ; --- R: regrow ----------------------------------------------------------
.rphase:
    mov ax, 100
    call OSAPI_MEM_HUGE             ; R
    mov cl, 0x10
    jc .no
    mov [hg_r], dx
    mov ax, 100
    mov [hg_rkb], ax
    mov bl, 0x52
    call hg_fill
    mov ax, 60
    call OSAPI_MEM_HUGE             ; S, above it
    jc .no
    mov [hg_s], dx
    mov ax, 300                     ; 1: to 300KB, which S makes a move
    mov cl, 0x11
    call hg_regrow
    jc .no
    mov ax, 130                     ; 2: a shrink
    mov cl, 0x12
    call hg_regrow
    jc .no
    mov dx, [hg_s]
    call OSAPI_MEM_FREE
    mov word [hg_s], 0
    mov ax, 400                     ; 3: S gone
    mov cl, 0x13
    call hg_regrow
    jc .no
    mov bl, 0x31                    ; --- X1 X2 X3 above it, X2 freed ------
    mov ax, 200
    call OSAPI_MEM_HUGE
    mov cl, 0x30
    jc .no
    mov [hg_x], dx
    call hg_fill
    mov ax, 200
    call OSAPI_MEM_HUGE
    mov cl, 0x30
    jc .no
    mov [hg_x+2], dx
    mov ax, 200
    call OSAPI_MEM_HUGE
    mov cl, 0x30
    jc .no
    mov [hg_x+4], dx
    mov bl, 0x33
    call hg_fill
    mov dx, [hg_x+2]
    call OSAPI_MEM_FREE
    mov word [hg_x+2], 0
    call OSAPI_XMEM_CAPS            ; 4: to every free KB
    mov cl, 0x30
    cmp ax, 420
    jb .no
    mov cl, 0x14
    call hg_regrow
    jc .no
    mov dx, [hg_x]
    mov ax, 200
    mov bl, 0x31
    call hg_chk
    mov cl, 0x31
    jc .no
    mov dx, [hg_x+4]
    mov bl, 0x33
    call hg_chk
    mov cl, 0x32
    jc .no
    ; --- E: everything back ---------------------------------------------
    call hg_freeall
    call OSAPI_XMEM_CAPS
    mov cl, 0x40
    cmp ax, [hg_free0]
    jne .no
    mov si, hg_s_okall
    call hg_say
    call hg_nl
    mov word [hg_tbuf+7], 'ok'      ; the verdict on the glass too, for a
    mov byte [hg_tbuf+9], 0         ; machine with no port E9 (86Box)
    call hg_toast
    stc                             ; (no window: a refusal, so the teardown
    jmp short .out                  ; is the kernel's ordinary one)
.nob:
    push cx
    mov dx, [hg_bsel]
    call OSAPI_MEM_FREE
    mov word [hg_bsel], 0
    pop cx
.no:
    mov [hg_code], cl
    call hg_resume                  ; (every exit path: SPEC.md 51.11)
    mov si, hg_s_bad
    call hg_say
    mov ax, [hg_bad]
    call hg_hex4
    mov ax, [hg_bad+2]
    call hg_hex4
    mov ax, [hg_bad+4]
    call hg_hex4
    call hg_nl
    call hg_walk                    ; the pool as the failure found it
    push cx
    call hg_freeall
    pop cx
    mov si, hg_s_no
    call hg_say
    mov al, cl
    call hg_hex2
    call hg_nl
    mov word [hg_tbuf+7], 'no'
    mov byte [hg_tbuf+9], ' '
    mov al, cl
    mov cl, 4
    shr al, cl
    call .hx
    mov [hg_tbuf+10], al
    mov al, [hg_code]
    and al, 15
    call .hx
    mov [hg_tbuf+11], al
    mov byte [hg_tbuf+12], 0
    call hg_toast
    stc
    jmp short .out
.hx:
    add al, '0'
    cmp al, '9'
    jbe .hx1
    add al, 7
.hx1:
    ret
.out:
    pop bp
    pop di
    pop si
    ret

; hg_take - AX = KB, BP = the table's index x 2 -> CF = 0 an OSAPI_MEM_HUGE
; claim of it ABOVE 1MB, kept at BP, filled with its tag, BP += 2; CF = 1 the
; pool took no more (a conventional answer goes back) or the table is full
hg_take:
    cmp bp, HG_MAX * 2
    jae .full
    push ax
    call OSAPI_MEM_HUGE
    pop ax
    jc .full
    test dl, 4
    jnz .sel
    call OSAPI_MEM_FREE             ; conventional: the pool is full
.full:
    stc
    ret
.sel:
    mov bx, bp                      ; (BX: [bp+...] would address SS)
    mov [hg_sel + bx], dx
    mov [hg_kb + bx], ax
    shr bl, 1
    add bl, 0x10                    ; the tag: 10h + the index
    call hg_fill
    add bp, 2
    clc
    ret

; hg_regrow - AX = the new KB, CL = the step's code -> R ([hg_r]) regrown
; to it: CF = 0 its old bytes (as many as fit) read back, the rest written
; and the whole read back, and the line said; CF = 1 and CL the failure
hg_regrow:
    push ax
    mov dx, [hg_r]
    push cx
    call OSAPI_MEM_REGROW
    pop cx
    pop ax
    jc .o                           ; (CL = 1x: refused)
    mov [hg_r], dx
    push ax                         ; R's bytes up to the smaller size
    cmp ax, [hg_rkb]
    jbe .k
    mov ax, [hg_rkb]
.k:
    mov bl, 0x52
    call hg_chk
    pop ax
    jnc .w
    add cl, 0x10                    ; 2x: the bytes
    stc
    jmp short .o
.w:
    mov [hg_rkb], ax
    mov bl, 0x52
    call hg_fill                    ; the whole of it, and read back
    call hg_chk
    jnc .say
    add cl, 0x10
    stc
    jmp short .o
.say:
    mov si, hg_s_rg
    call hg_say
    push ax
    mov ax, dx
    call hg_hex4
    mov si, hg_s_kb
    call hg_say
    pop ax
    call hg_hex4
    mov si, hg_s_ok
    call hg_say
    call hg_nl
    clc
.o:
    ret

; hg_fill / hg_chk - DX = a run's first selector, AX = its KB, BL = a tag:
; every word of every 64KB piece = BL:piece / CF = 1 one is not. Keep all
hg_fill:
    push ax
    push cx
    push di
    push es
    push dx
    mov bh, 0
.p:
    mov es, dx
    mov cx, ax
    cmp cx, 64
    jbe .n
    mov cx, 64
.n:
    sub ax, cx
    shl cx, 1                       ; KB -> words: x 512
    xchg ch, cl
    xor cl, cl
    or cx, cx
    jnz .c
    mov cx, 0x8000                  ; (64KB)
.c:
    push ax
    mov al, bh
    mov ah, bl
    xor di, di
    cld
    rep stosw
    pop ax
    inc bh
    add dx, 8
    or ax, ax
    jnz .p
    pop dx
    pop es
    pop di
    pop cx
    pop ax
    ret

hg_chk:
    push ax
    push cx
    push di
    push es
    push dx
    mov bh, 0
.p:
    mov es, dx
    mov cx, ax
    cmp cx, 64
    jbe .n
    mov cx, 64
.n:
    sub ax, cx
    shl cx, 1
    xchg ch, cl
    xor cl, cl
    or cx, cx
    jnz .c
    mov cx, 0x8000
.c:
    push ax
    mov al, bh
    mov ah, bl
    xor di, di
    cld
    repe scasw
    pop ax
    jne .bad
    inc bh
    add dx, 8
    or ax, ax
    jnz .p
    clc
    jmp short .o
.bad:
    mov [hg_bad], es                ; where: the piece's selector, the word
    mov [hg_bad+2], di              ; after it, and what it holds
    mov ax, [es:di-2]
    mov [hg_bad+4], ax
    stc
.o:
    pop dx
    pop es
    pop di
    pop cx
    pop ax
    ret

; hg_chkall - every kept fragment claim read back whole: CF = 1 one is not
hg_chkall:
    push ax
    push bx
    push dx
    push si
    xor si, si
.l:
    cmp si, [hg_n]
    jae .ok
    mov dx, [hg_sel + si]
    or dx, dx
    jz .n
    mov ax, [hg_kb + si]
    mov bx, si
    shr bl, 1
    add bl, 0x10
    call hg_chk
    jc .o
.n:
    add si, 2
    jmp short .l
.ok:
    clc
.o:
    pop si
    pop dx
    pop bx
    pop ax
    ret

; hg_toast - [hg_tbuf] ('MEGAHG ' and the verdict) on the menu bar, ~100s
hg_toast:
    mov word [hg_tbuf], 'ME'
    mov word [hg_tbuf+2], 'GA'
    mov word [hg_tbuf+4], 'HG'
    mov byte [hg_tbuf+6], ' '
    push ds
    pop es
    mov si, hg_tbuf
    mov cx, 1820
    call OSAPI_TOAST
    ret

; hg_resume - OSAPI_DRV_SUSPEND's resume, if a suspend stands. Keeps all
hg_resume:
    cmp byte [hg_susp], 0
    je .o
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    xor ax, ax
    call OSAPI_DRV_SUSPEND
    mov byte [hg_susp], 0
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
.o:
    ret

; hg_walk - the pool's blocks on E9, one 'MEGAHG: blk OOOO KKKK WW' each
hg_walk:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    mov di, hg_wbuf
    mov cx, HG_WN
    call OSAPI_XMEM_WALK
    jc .o
    mov cx, ax
    mov di, hg_wbuf
.l:
    jcxz .o
    mov si, hg_s_blk
    call hg_say
    mov ax, [di+XMW_OFF]
    call hg_hex4
    mov al, ' '
    out 0xE9, al
    mov ax, [di+XMW_KB]
    call hg_hex4
    mov al, ' '
    out 0xE9, al
    mov al, [di+XMW_OWN]
    call hg_hex2
    call hg_nl
    add di, XMW_SIZE
    dec cx
    jmp short .l
.o:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; hg_freeall - every claim this holds goes back
hg_freeall:
    push bx
    push dx
    xor bx, bx
.l:
    cmp bx, HG_MAX * 2 + 6 * 2
    jae .o
    mov dx, [hg_sel + bx]
    or dx, dx
    jz .n
    call OSAPI_MEM_FREE
    mov word [hg_sel + bx], 0
.n:
    add bx, 2
    jmp short .l
.o:
    mov word [hg_n], 0
    pop dx
    pop bx
    ret

hg_say:
    push ax
.l:
    lodsb
    or al, al
    jz .o
    out 0xE9, al
    jmp short .l
.o:
    pop ax
    ret
hg_nl:
    push ax
    mov al, 10
    out 0xE9, al
    pop ax
    ret
hg_hex4:
    push ax
    mov al, ah
    call hg_hex2
    pop ax
hg_hex2:
    push ax
    push cx
    mov ah, al
    mov cl, 4
    shr al, cl
    call .d
    mov al, ah
    and al, 15
    call .d
    pop cx
    pop ax
    ret
.d:
    add al, '0'
    cmp al, '9'
    jbe .p
    add al, 7
.p:
    out 0xE9, al
    ret

hg_s_free:  db 'MEGAHG: free ', 0
hg_s_h:     db ' H ', 0
hg_s_frag:  db 'MEGAHG: frag ', 0
hg_s_holes: db ' holes free ', 0
hg_s_big:   db 'MEGAHG: big ', 0
hg_s_rg:    db 'MEGAHG: regrow ', 0
hg_s_kb:    db ' kb ', 0
hg_s_ok:    db ' ok', 0
hg_s_okall: db 'MEGAHG: ok', 0
hg_s_no:    db 'MEGAHG: no ', 0
hg_s_blk:   db 'MEGAHG: blk ', 0
hg_s_bad:   db 'MEGAHG: bad ', 0
hg_s_drv:   db 'MEGAHG: drivers unloaded and reloaded', 0

; the bss: hg_sel's HG_MAX entries run straight on into the six below it,
; so hg_freeall frees R, S, X1-X3 and the big one with the fragments
HG_WN       equ 32
HG_BSS      equ HG_MAX * 2 * 2 + 6 * 2 + 12 + HG_WN * XMW_SIZE + 8 + 18
    OS88_BSS HG_BSS
    OS88_IMAGE_END

hg_sel      equ os88_image_end + 0
hg_r        equ hg_sel + HG_MAX * 2
hg_s        equ hg_r + 2
hg_x        equ hg_s + 2
hg_bsel     equ hg_x + 6
hg_kb       equ hg_bsel + 2
hg_n        equ hg_kb + HG_MAX * 2
hg_free0    equ hg_n + 2
hg_h        equ hg_free0 + 2
hg_big      equ hg_h + 2
hg_rkb      equ hg_big + 2
hg_wbuf     equ hg_rkb + 2
hg_bad      equ hg_wbuf + HG_WN * XMW_SIZE
hg_susp     equ hg_bad + 6              ; 1: a suspend stands
hg_dsus     equ hg_bad + 7              ; 1: one was taken
hg_code     equ hg_bad + 8              ; the failure's code
hg_tbuf     equ hg_bad + 9              ; the toast's line, 16 bytes
