; =============================================================================
; osrom.asm - the code that rides in os8088's ROM (docs/plans/ROM-PLAN.md 1.3)
;
; The ROM window is the five spare 8KB sockets of an IBM 5150, U28-U32, which
; decode F4000-FDFFF. tools/os88rom.py lays the window out as ONE option ROM:
;
;   F4000  55 AA 40  jmp near rom_init  'OS88'  fmt  kind  id  bal1     16 bytes
;   F4010  the payload: the kernel's `.cold` (segment F401), or the
;          socket-check pattern
;     ...  0xFF fill
;   TAIL   THIS FILE, assembled at the offset the tool chose (TAIL_AT)
;   FDFFF  bal2
;
; Two facts out of the BIOS listings decide the shape (ROM-PLAN 1.3):
;  - The option-ROM scan calls rom_init AFTER POST has pointed int 18h at
;    F600:0000, on 10/27/82 and on GLaBIOS alike, so rom_init can point it
;    here instead. Nothing has to sit at F600:0000, which lets `.cold` run
;    straight through it.
;  - The header declares 32KB (0x40), not 40. The 10/27/82 BASIC check runs
;    from wherever the scan pointer stopped until FE00 and tests before it
;    compares, so a 40KB declaration leaves the pointer on FE00 and the loop
;    wraps to segment 0 and checksums all of RAM. 32KB leaves it on FC00: one
;    module, FC000-FDFFF, which bal2 balances. bal1 balances the declared
;    32KB for the option-ROM check itself.
;
; It is assembled TWICE by the tool - once at TAIL_AT = 0 to learn its length,
; then at the real offset - because every near label in it is an offset into
; the F400 segment.
;
; CONTRACT at rom_init (an option-ROM init, both BIOSes): CS = F400, IP = 3
; through the header's jmp, far-called, interrupts in whatever state the BIOS
; left them. It preserves every register and returns with retf. At rom_stub
; (int 18h): whatever the BIOS had; it never returns.
; =============================================================================
cpu 8086
bits 16

%ifndef TAIL_AT
  %define TAIL_AT 0
%endif
%ifndef BUILD_STR
  %define BUILD_STR '?'
%endif

ROM_KIND_SOCK   equ 1           ; the socket-check ROM: a pattern, no OS
ROM_KIND_KERNEL equ 2           ; os8088's `.cold` and what adapts a kernel
                                ; to it (ROM-PLAN 3.4)
%ifndef ROM_KIND
  %define ROM_KIND ROM_KIND_SOCK
%endif

ROM_SIZE        equ 40960       ; F4000-FDFFF
ROM_SEG         equ 0xF400      ; U28's base, the header's paragraph...
ROM_COLDSEG     equ ROM_SEG + 1 ; ...and the segment `.cold` runs at in ROM,
                                ; kernel/kernel.asm's equate of the same name
ROMF_SIZE       equ 0           ; rom_modfix's functions: kernel/kernel.asm's
ROMF_COPY       equ 1           ; equates of the same names, which the kernel
ROMF_FIX        equ 2           ; loads into AL
ROMF_PKG        equ 3
SOCK_SIZE       equ 8192        ; one socket, U28 = 0 ... U32 = 4
SOCK_N          equ 5

    org TAIL_AT

; --- the identity block, FIRST in the tail ------------------------------------
; The header's word at +12 points here. It is what a kernel's probe reads
; (ROM-PLAN 3.4.3), so its layout is versioned by the header's fmt byte and
; os88rom.py writes the fields it knows only after assembly (the key, the
; payload's length) into the zeros left for them.
rom_id:
    db 'OS88ROM', 0             ; +0  a second signature, past the payload
    db ROM_KIND                 ; +8
    db 0                        ; +9  reserved
    dw 0                        ; +10 payload offset in the window (tool)
    dw 0                        ; +12 payload length (tool)
    dw 0                        ; +14 tail length (tool)
    times 8 db 0                ; +16 the KEY (tool; kernel ROMs only)
    dw rom_patch                ; +24 the patcher's entry (kernel ROMs)
    dw 0                        ; +26 reserved
    times 4 db 0                ; +28 reserved
%if $ - rom_id != 32
  %error "rom_id must be 32 bytes - the kernel's probe reads it at fixed offsets"
%endif

; --- rom_init - called by the BIOS's option-ROM scan, during POST -------------
rom_init:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push ds
    push es
    pushf
    xor ax, ax
    mov ds, ax
    cli                         ; the vector is two words; nothing may take
    mov word [0x18*4], rom_stub ; int 18h between them
    mov [0x18*4+2], cs
    popf
    push cs
    pop ds
    mov si, rom_s_post
    call rom_puts
%if ROM_KIND == ROM_KIND_SOCK
    call rom_sock_check
%endif
    mov si, rom_s_crlf
    call rom_puts
    pop es
    pop ds
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    retf

; --- rom_stub - int 18h, which a BIOS raises when there is nothing to boot ---
; The request's "insert disk and press any key, then reboot": int 19h runs the
; BIOS's bootstrap again, and a bootstrap that fails comes back here.
rom_stub:
    sti
    push cs
    pop ds
.again:
    mov si, rom_s_stub
    call rom_puts
    xor ax, ax                  ; wait for a key
    int 0x16
    mov si, rom_s_crlf
    call rom_puts
    int 0x19
    jmp short .again            ; int 19h is not meant to return

; --- rom_puts - DS:SI = an asciz string, through the BIOS teletype ------------
rom_puts:
    push ax
    push bx
.next:
    lodsb
    or al, al
    jz .done
    mov ah, 0x0E
    mov bx, 0x0007
    int 0x10
    jmp short .next
.done:
    pop bx
    pop ax
    ret

; --- rom_putc - AL through the BIOS teletype; preserves every register ------
rom_putc:
    push ax
    push bx
    mov ah, 0x0E
    mov bx, 0x0007
    int 0x10
    pop bx
    pop ax
    ret

%if ROM_KIND == ROM_KIND_SOCK
; --- rom_sock_check - prove every socket reads back what was burned ----------
; The payload is the pattern f(o) = (lo(o) + 3*hi(o) + 0x5A) mod 256 over the
; window offset o (tools/os88rom.py, sock_byte). It moves with BOTH halves of
; the address, so a stuck or swapped address line, a chip select wired to the
; wrong socket (the high byte carries the socket), or a byte the board drops
; all read as a mismatch IN THE SOCKET THAT HAS IT. The header, the int 18h
; landing at F6000 and this tail are not pattern, and are skipped.
SKIP_A0 equ 0
SKIP_A1 equ 16                  ; the header
SKIP_B0 equ 0x2000              ; F6000: a far jump to rom_stub, for a BIOS
SKIP_B1 equ 0x2005              ; that never runs rom_init (the 1981 ones)
rom_sock_check:
    xor bx, bx                  ; BX = the offset under test
    xor dx, dx                  ; DL = bad sockets, one bit each
.loop:
    cmp bx, SKIP_A1
    jb .skip
    cmp bx, SKIP_B0
    jb .test
    cmp bx, SKIP_B1
    jb .skip
.test:
    mov al, bh
    add al, al
    add al, bh
    add al, bl
    add al, 0x5A
    cmp al, [cs:bx]
    je .skip
    mov cl, bh                  ; the socket is the offset's top three bits
    shr cl, 1                   ; (8192 = 2^13, so bits 13-15 of BX = bits
    shr cl, 1                   ; 5-7 of BH)
    shr cl, 1
    shr cl, 1
    shr cl, 1
    mov al, 1
    shl al, cl
    or dl, al
.skip:
    inc bx
    cmp bx, strict word TAIL_AT ; the pattern ends where this code starts
    jb .loop
    mov cl, 0                   ; ...and the verdict, one socket at a time
.say:
    mov si, rom_s_sock          ; " U"
    call rom_puts
    mov al, '8'                 ; U28 + n: "28" "29" "30" "31" "32"
    add al, cl
    mov ch, '2'
    cmp al, '9'
    jbe .digits
    sub al, 10
    mov ch, '3'
.digits:
    xchg al, ch
    call rom_putc
    mov al, ch
    call rom_putc
    mov si, rom_s_ok
    mov al, 1
    shl al, cl
    test dl, al
    jz .tell
    mov si, rom_s_bad
.tell:
    call rom_puts
    inc cl
    cmp cl, SOCK_N
    jb .say
    ret
%endif

%if ROM_KIND == ROM_KIND_KERNEL
; =============================================================================
; THE KERNEL'S ADAPTER (docs/plans/ROM-PLAN.md 3.4.3)
;
; A ROM_COLD kernel is assembled against its own RAM rung - every far
; reference to `.cold` names COLD_RAM - and is expanded whole by stage 2,
; `.cold` included. Then the boot overlay's first instruction rings rom_patch.
; This ROM was cut from ONE
; build and carries, in the tables tools/os88rom.py generated (ROMTAB), every
; place that build names `.cold`'s segment; it decides whether the kernel in
; RAM IS that build, and only then re-points those words at its own `.cold`.
;
; "Is that build" is three tests, every one before a byte is written:
;   1. this ROM's `.cold` and the one just expanded are the same bytes - the
;      strongest test there is, and free in a kernel that expands it anyway;
;   2. a hash over `.text`, the build number's words left out, so a ROM cut
;      before a commit that touched nothing else survives it - while a `.text`
;      routine that changed its contract without moving does not;
;   3. every word on the lists still says COLD_RAM.
; A NO from any of them is CF = 1 and an untouched kernel: a wrong ROM is no
; ROM. tools/os88rom.py is the other half and its --selfcheck is the gate.
;
; THE TABLES (ROMTAB, generated):
;   RT_KSEG RT_FATSEG RT_COLDRAM  the kernel's segments, as built
;   RT_COLDLEN                    `.cold`'s length; ours is at CS:0x10
;   RT_HASH                       the `.text` hash; rt_spans its word spans
;   rt_text / rt_ovlw / rt_ovl    the far references, by the segment each is
;                                 an offset into (`.ovl`'s is the blob's, which
;                                 the caller hands over in AX)
;   rt_vgab, RT_VGABRAM           kern_big's `.vgabuf` words, and the rung
;                                 they name, moved down to RT_COLDRAM
;   rt_mods                       per mod_tab ROW: its list and its count (the
;                                 settings core's row shares CTRL.DRV's)
;   rt_img                        per ROW: the image this ROM holds (its offset
;                                 in the window and its bytes), 0 = none
;   RT_PKGOFF RT_PKGLEN           the one package it may hold, and its name,
;   rt_pkgname                    which ROMF_PKG matches (SPEC.md 2.10.5)
;   RT_MFP                        rom_mfp's offset in the kernel's `.text`
; =============================================================================
%include ROMTAB

; --- rom_patch - adopt the kernel expanded at RT_KSEG, or say no -------------
; in:  AX = the blob's segment; far-called from the boot overlay's
;      rom_adopt, kmain_o's first instruction, before a byte of `.cold` has run
; out: CF = 0 adopted: every listed word names ROM_COLDSEG and the kernel's
;      rom_mfp names rom_modfix. CF = 1: nothing anywhere was written
; preserves: every register (the doorbell saves only what it touches); leaves
;      the direction flag clear
rom_patch:
    push ax                     ; EVERY REGISTER KEPT, here and not in the
    push bx                     ; kernel's doorbell: these bytes are ROM and
    push cx                     ; cost nobody RAM, the doorbell's are the
    push dx                     ; boot overlay's and it had 27 to spare
    push si
    push di
    push bp
    push ds
    push es
    cld
    mov bp, ax                  ; BP = the blob, for rt_ovl
    ; --- 1. `.cold`, byte for byte -------------------------------------------
    push cs
    pop ds
    mov si, 0x10                ; ours: the paragraph after the header
    mov ax, RT_COLDRAM
    mov es, ax
    xor di, di
    mov cx, RT_COLDLEN / 2
    repe cmpsw
    jne .no
%if RT_COLDLEN & 1
    cmpsb
    jne .no
%endif
    ; --- 2. `.text`, hashed over its spans -----------------------------------
    mov ax, RT_KSEG
    mov ds, ax
    xor dx, dx
    mov bx, rt_spans
.span:
    cmp bx, rt_spans_end
    jae .hashed
    mov si, [cs:bx]             ; start, even
    mov cx, [cs:bx+2]           ; words
    add bx, 4
    jcxz .span
.word:
    lodsw
    rol dx, 1
    xor dx, ax
    loop .word
    jmp short .span
.hashed:
    cmp dx, RT_HASH
    jne .no
    ; --- 3. every listed word names what it should - and only then, 4. ------
    xor bl, bl                  ; BL = 0: look
    call rp_walk
    jc .no
    mov bl, 1                   ; BL = 1: write
    call rp_walk
    mov ax, RT_KSEG             ; ...and the door mod_need far-calls
    mov es, ax
    mov word [es:RT_MFP], rom_modfix
    mov [es:RT_MFP+2], cs
    clc
    jmp short .out
.no:
    stc
.out:
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    retf

; rp_walk - the four lists, looked at (BL = 0, CF = 1 at the first word that
; is not COLD_RAM) or written (BL = 1). BP = the blob.
rp_walk:
    mov ax, RT_KSEG
    mov si, rt_text
    mov cx, RT_NTEXT
    call rp_list
    jc .out
    mov ax, RT_FATSEG
    mov si, rt_ovlw
    mov cx, RT_NOVLW
    call rp_list
    jc .out
    mov ax, bp
    mov si, rt_ovl
    mov cx, RT_NOVL
    call rp_list
    jc .out
    ; ...and the planar decoder's buffers (kern_big): RT_NVGAB words in
    ; `.text` that name the `.vgabuf` rung move to the BOTTOM of the dead cold
    ; rung, which is where mem_floor_ax leaves them (ROM-PLAN 3.4.2)
    mov ax, RT_KSEG
    mov es, ax
    mov si, rt_vgab
    mov cx, RT_NVGAB
    jcxz .vok
.vnext:
    mov di, [cs:si]
    add si, 2
    or bl, bl
    jnz .vwrite
    cmp word [es:di], RT_VGABRAM
    jne .vbad
    loop .vnext
    jmp short .vok
.vwrite:
    mov word [es:di], RT_COLDRAM
    loop .vnext
.vok:
    clc
.out:
    ret
.vbad:
    stc
    ret

; rp_list - AX = the segment, CS:SI = CX offsets, BL = look/write; CF = 1 at
; the first word that does not say COLD_RAM (look only). DX = no limit.
rp_list:
    mov es, ax
    mov dx, 0xFFFF
; ...and the module door's way in, with DX = the bytes it read: a word at or
; past DX is not in this claim (the settings core reads a PART, SPEC.md 2.8.7)
rp_list_lim:
    jcxz .ok
.next:
    mov di, [cs:si]
    add si, 2
    mov ax, di
    inc ax                      ; the word's second byte
    cmp ax, dx
    jae .skip
    or bl, bl
    jnz .write
    cmp word [es:di], RT_COLDRAM
    jne .bad
    jmp short .skip
.write:
    mov word [es:di], ROM_COLDSEG
.skip:
    loop .next
.ok:
    clc
    ret
.bad:
    stc
    ret

; --- rom_modfix - the door mod_need and the Task Manager item call ----------
; (ROM-PLAN 3.4.4, 4.3; SPEC.md 2.10.4, 2.10.5). AL picks, kernel.asm's ROMF_*:
;   0 SIZE  BX = a mod_tab ROW -> CF = 0, AX = the bytes of that row's image
;           this ROM holds; CF = 1 it holds none (the disk is asked instead)
;   1 COPY  BX = a row, ES = its claim, CX = bytes -> the image's first CX
;           bytes to ES:0, AX = CX, DX = 0, CF = 0 (dskw_read_x's answer)
;   2 FIX   BX = a row, ES = its claim, CX = the bytes it holds -> every
;           listed far reference to `.cold` re-pointed at F401; CF = 1 = not
;           this ROM's module (a word does not say COLD_RAM) and nothing
;           written - mod_need then refuses it. The ROM's own copies are kept
;           AS THE BUILD CUT THEM, so a copied module is fixed like a read one
;   3 PKG   DS:SI = a package's 8.3 name (the kernel's) -> CF = 0, ES:DI =
;           its image in this ROM, DX:CX = its length; CF = 1 none by that name
; preserves: every register but the outputs named and the flags. A ROW and
; not an id because mod_need has no register left holding the id - and the
; settings core (MOD_SETS) is a row of its own over CTRL.DRV's image, which
; the tool's tables already resolve, so nothing here knows it exists.
rom_modfix:
    cmp al, ROMF_PKG
    je rom_pkg
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    cld
    sub bx, RT_MODTAB           ; the row's offset into mod_tab...
    jb .no
    test bl, RT_MODRSZ - 1      ; ...on a row boundary...
    jnz .no
    cmp bx, RT_NMODS * RT_MODRSZ
    jae .no                     ; ...and inside the table
%if RT_MODRSZ != 4
  %error "rt_mods and rt_img are indexed by row*4 and mod_tab's stride is not 4"
%endif
    cmp al, ROMF_FIX
    je .fix
    mov si, [cs:rt_img+bx]      ; the image's offset in this ROM, 0 = none
    or si, si
    jz .no
    cmp al, ROMF_COPY
    je .copy
    mov ax, [cs:rt_img+bx+2]    ; SIZE: the bytes, out in AX - so the
    pop di                      ; epilogue below is not the way out
    pop si
    pop dx
    pop cx
    pop bx
    add sp, 2                   ; ...the caller's AX is the answer's
    clc
    retf
.copy:
    push ds
    push cs
    pop ds
    xor di, di
    rep movsb                   ; CX = the bytes asked for (mod_need's BP)
    pop ds
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    add sp, 2
    mov ax, cx                  ; the read's answer: all of it, DX:AX
    xor dx, dx
    clc
    retf
.fix:
    mov dx, cx                  ; DX = the limit for rp_list_lim
    mov si, [cs:rt_mods+bx]     ; the list...
    mov cx, [cs:rt_mods+bx+2]   ; ...and its count
    push si
    push cx
    xor bl, bl
    call rp_list_lim
    pop cx
    pop si
    jc .no
    mov bl, 1
    call rp_list_lim
    clc
    jmp short .out
.no:
    stc
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    retf

; rom_pkg - ROMF_PKG: the one package this ROM may carry, by name
rom_pkg:
%if RT_PKGLEN
    push ax
    push si
    push di
    mov di, rt_pkgname
.cmp:
    lodsb
    cmp al, [cs:di]
    jne .no
    inc di
    or al, al
    jnz .cmp
    pop di
    pop si
    pop ax
    push cs
    pop es
    mov di, RT_PKGOFF            ; the image, in the payload ahead of this tail
    mov cx, RT_PKGLEN
    xor dx, dx
    clc
    retf
.no:
    pop di
    pop si
    pop ax
%endif
    stc
    retf
%else
; A socket ROM carries a refusing stub so the identity block's pointer is never
; a wild one.
rom_patch:
    stc
    retf
%endif

; --- the strings ---------------------------------------------------------------
%if ROM_KIND == ROM_KIND_SOCK
rom_s_post: db 'os8088 ROM socket check, build ', BUILD_STR, ':', 0
rom_s_sock: db ' U', 0
rom_s_ok:   db ' ok', 0
rom_s_bad:  db ' BAD', 0
rom_s_stub: db 13, 10, 'os8088 socket-check ROM: no system here. '
            db 'Insert a system disk and press any key.', 0
%else
rom_s_post: db 'os8088 ROM build ', BUILD_STR, 0
rom_s_stub: db 13, 10, 'os8088 ROM build ', BUILD_STR, ': '
            db 'insert a system disk and press any key.', 0
%endif
rom_s_crlf: db 13, 10, 0

rom_tail_end:
