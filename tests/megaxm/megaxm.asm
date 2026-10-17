; =============================================================================
; os8088 - tests/megaxm/megaxm.asm
;
; MEGAXM, a TEST instrument (nothing under tests/ ships): the XMEM cells end
; to end, from a package - CAPS, a 64KB ALLOC, sixteen 4KB patterns COPYed
; out and read back in and compared, and the FREE. Every result on port E9,
; one line each, so tools/os88bochs.py can read the verdict:
;
;   MEGAXM: caps NNNN          the KB OSAPI_XMEM_CAPS answers
;   MEGAXM: alloc DDDDAAAA     the block's linear base
;   MEGAXM: ok | bad NN | no NN    the verdict, or the step that refused
;
; It was written for kern_mega's own pool (docs/plans/KERN-MEGA-PLAN.md 12.2,
; mega.inc's mx_*), and runs on any kernel with a store: tier 0 answers caps 0
; and stops there.
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'MEGAXM', mz_entry

MZ_CHUNK    equ 4096
MZ_N        equ 16

mz_entry:
    push si
    push di
    mov si, mz_s_caps
    call mz_say
    call OSAPI_XMEM_CAPS
    call mz_hex4
    call mz_nl
    or ax, ax
    jz .done
    xor ax, ax                  ; DX:AX = 64KB
    mov dx, 1
    call OSAPI_XMEM_ALLOC
    mov cl, 1
    jc .no
    mov [mz_base], ax
    mov [mz_base+2], dx
    mov si, mz_s_alloc
    call mz_say
    xchg ax, dx
    call mz_hex4
    xchg ax, dx
    call mz_hex4
    call mz_nl
    ; --- out: chunk k holds bytes (i * 7 + k) for i in 0..4095 -------------
    xor bx, bx
.out:
    call mz_fill                ; mz_buf = pattern BL
    mov di, 0                   ; conventional -> extended
    call mz_copy
    mov cl, 2
    jc .no
    inc bx
    cmp bx, MZ_N
    jb .out
    ; --- in, and compare -------------------------------------------------
    xor bx, bx
.in:
    push bx
    mov di, mz_buf              ; clear the buffer first, so a copy that
    mov cx, MZ_CHUNK / 2        ; moved nothing cannot pass
    xor ax, ax
    push ds
    pop es
    cld
    rep stosw
    pop bx
    mov di, 1                   ; extended -> conventional
    call mz_copy
    mov cl, 3
    jc .no
    call mz_cmp                 ; CF = 1 a byte differs
    mov cl, bl                  ; ...and the verdict names the chunk
    jc .bad
    inc bx
    cmp bx, MZ_N
    jb .in
    mov ax, [mz_base]
    mov dx, [mz_base+2]
    call OSAPI_XMEM_FREE
    mov cl, 5
    jc .no
    mov si, mz_s_ok
    call mz_say
    call mz_nl
    jmp short .done
.no:                            ; CL = the step that refused
    mov si, mz_s_no
    jmp short .code
.bad:
    mov si, mz_s_bad
.code:
    call mz_say
    mov al, cl
    call mz_hex2
    call mz_nl
.done:
    pop di
    pop si
    stc                         ; no window: the instance ends here
    ret

; BL = the chunk. mz_buf <- its pattern
mz_fill:
    push ax
    push cx
    push di
    push ds
    pop es
    mov di, mz_buf
    mov al, bl
    mov cx, MZ_CHUNK
.l:
    stosb
    add al, 7
    loop .l
    pop di
    pop cx
    pop ax
    ret

; BL = the chunk -> CF = 1 if mz_buf is not its pattern
mz_cmp:
    push ax
    push cx
    push si
    mov si, mz_buf
    mov al, bl
    mov cx, MZ_CHUNK
.l:
    cmp [si], al
    jne .no
    inc si
    add al, 7
    loop .l
    clc
    jmp short .x
.no:
    stc
.x:
    pop si
    pop cx
    pop ax
    ret

; BL = the chunk, DI = the direction -> OSAPI_XMEM_COPY of mz_buf and
; base + chunk * 4KB. CF as the cell's. Keeps BX
mz_copy:
    push bx
    push si
    mov ax, bx
    mov cl, 12
    shl ax, cl                  ; chunk * 4096: under 64KB, no carry
    mov dx, [mz_base+2]
    add ax, [mz_base]
    adc dx, 0
    push ds
    pop es
    mov si, mz_buf
    mov cx, MZ_CHUNK
    call OSAPI_XMEM_COPY
    pop si
    pop bx
    ret

mz_say:
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
mz_nl:
    push ax
    mov al, 10
    out 0xE9, al
    pop ax
    ret
mz_hex4:
    push ax
    mov al, ah
    call mz_hex2
    pop ax
mz_hex2:
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

mz_s_caps:  db 'MEGAXM: caps ', 0
mz_s_alloc: db 'MEGAXM: alloc ', 0
mz_s_ok:    db 'MEGAXM: ok', 0
mz_s_no:    db 'MEGAXM: no ', 0
mz_s_bad:   db 'MEGAXM: bad ', 0

    OS88_BSS 4 + MZ_CHUNK
    OS88_IMAGE_END

mz_base     equ os88_image_end + 0
mz_buf      equ os88_image_end + 4
