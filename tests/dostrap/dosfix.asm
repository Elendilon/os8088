; DOSFIX.COM - the two handle defects docs/plans/DOS-STREAM-PLAN.md 3 found,
; as a probe. OURS, MIT with the rest of the tree.
;
; 1. FDIR: open SUB\X.DAT from the ROOT and read all of it. X.DAT is 12 KB,
;    so the read crosses the box's 8 KB window and REFILLS, and a refill
;    that resolves the bare name where the program STANDS finds the DECOY -
;    a root X.DAT whose every byte is 0xEE - where the real one's byte i is
;    (i >> 10) + 1. A wrong folder is therefore a wrong BYTE, named with its
;    offset, and not an end of file that could be mistaken for a short read.
; 2. NOCLOSE: create NOCLOSE.DAT, write 3,000 bytes of 'N' and EXIT without
;    AH=3Eh. DOS closes every handle of a process that terminates; the host
;    reads the file off the floppy afterwards and wants all 3,000.
;
; Runs under a real DOS unchanged. It waits for a key after READY, so the
; host can read the screen; the exit that follows is still without AH=3Eh.

    org 0x100
    cpu 8086

XSIZE   equ 12288

start:
    ; --- 1. FDIR -----------------------------------------------------------
    mov ax, 0x3D00
    mov dx, n_sub
    int 0x21
    mov byte [stage], 'O'
    jc fail
    mov [fh], ax
    xor si, si                  ; SI = the file offset of buf[0]
.rd:
    mov ah, 0x3F
    mov bx, [fh]
    mov cx, 1000                ; not a cluster multiple on purpose
    mov dx, buf
    int 0x21
    mov byte [stage], 'R'
    jc fail
    or ax, ax
    jz .eof
    mov cx, ax
    mov di, buf
.ck:
    mov ax, si
    push cx
    mov cl, 10
    shr ax, cl
    pop cx
    inc al                      ; byte i of the real X.DAT is (i >> 10) + 1
    cmp [di], al
    jne .bad
    inc si
    inc di
    loop .ck
    jmp .rd
.bad:
    mov dx, s_fbad
    call puts
    mov ax, si
    call putn
    mov dx, s_got
    call puts
    mov al, [di]
    xor ah, ah
    call putn
    call crlf
    jmp .nc
.eof:
    mov byte [stage], 'L'
    cmp si, XSIZE
    jne fail
    mov dx, s_fok
    call puts
    mov ah, 0x3E
    mov bx, [fh]
    int 0x21
.nc:
    ; --- 2. NOCLOSE --------------------------------------------------------
    mov ah, 0x3C
    xor cx, cx
    mov dx, n_nc
    int 0x21
    mov byte [stage], 'C'
    jc fail
    mov bx, ax
    mov di, buf
    mov al, 'N'
    mov cx, 3000
    cld
    rep stosb
    mov ah, 0x40
    mov cx, 3000
    mov dx, buf
    int 0x21
    mov byte [stage], 'W'
    jc fail
    mov dx, s_ready
    call puts
    mov ah, 0x08                ; a key first, so the host can read the
    int 0x21                    ; screen before the desktop comes back
    mov ax, 0x4C00              ; ...and NO AH=3Eh: the exit must close it
    int 0x21

fail:
    mov dx, s_fail
    call puts
    mov dl, [stage]
    mov ah, 0x02
    int 0x21
    call crlf
    mov dx, s_ready
    call puts
    mov ax, 0x4C01
    int 0x21

puts:
    mov ah, 0x09
    int 0x21
    ret

crlf:
    mov dx, s_crlf
    jmp puts

putn:                           ; AX, unsigned decimal
    mov bx, 10
    xor cx, cx
.d:
    xor dx, dx
    div bx
    push dx
    inc cx
    or ax, ax
    jnz .d
.p:
    pop dx
    add dl, '0'
    mov ah, 0x02
    int 0x21
    loop .p
    ret

n_sub:   db 'SUB\X.DAT', 0
n_nc:    db 'NOCLOSE.DAT', 0
s_fok:   db 'FDIR ok', 13, 10, '$'
s_fbad:  db 'FDIR BAD at $'
s_got:   db ' got $'
s_ready: db 'READY', 13, 10, '$'
s_fail:  db 'FAILED at $'
s_crlf:  db 13, 10, '$'
fh:      dw 0
stage:   db 0
buf:
