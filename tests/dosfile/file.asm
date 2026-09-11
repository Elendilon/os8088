; =============================================================================
; os8088 - tests/dosfile/file.asm
;
; The wave-2 file-handle gate's DOS program (SPEC.md 96.11). A .COM that puts
; a file through the whole handle layer and checks the bytes came back:
;
;   - AH=3Ch create, then AH=40h forty times, which is 20,480 bytes and so
;     crosses the 8KB window TWICE - the first flush REPLACES and the two
;     after it APPEND, which is the one ordering OSAPI_FILE_APPEND's
;     cluster-multiple rule allows (SPEC.md 96.11);
;   - AH=42h origin 2, which is how a program asks a file's size;
;   - AH=3Fh in 512-byte reads, every byte checked against its own offset, so
;     a window that refills at the wrong base is caught at the seam rather
;     than looking like a short read;
;   - AH=42h to 12,345 - inside no window boundary - and a read there, which
;     is the random-access case the sequential one cannot catch;
;   - AH=41h delete, and an open afterwards that MUST fail with code 2.
;
; THE FILE IS BYTE N = N & 0FFh, deliberately: it makes every check a
; comparison against the position itself, so an off-by-one window is a wrong
; VALUE and not a missing one.
;
; NOTHING HERE IS THIRD-PARTY. It is ours, MIT with the rest of the tree, and
; it is under tests/ because it is not shipped software (CLAUDE.md, Layout).
; =============================================================================

    cpu 8086
    bits 16
    org 0x100

BLK       equ 512                   ; one write, and one read
NBLK      equ 40                    ; 20,480 bytes: two window crossings
SEEKTO    equ 12345                 ; ...and a point inside none of them

start:
    mov ah, 0x09
    mov dx, msg_hi
    int 0x21

    ; --- 1. create and write ------------------------------------------------
    mov ah, 0x3C
    xor cx, cx
    mov dx, fname
    int 0x21
    jc .cfail
    mov [handle], ax

    xor bx, bx                      ; BX = the running file offset, which is
    mov cx, NBLK                    ; also the byte value at it
.wblk:
    push cx
    call fill                       ; buf[] = (BX+i) & 0FFh
    mov ah, 0x40
    mov bx, [handle]
    mov cx, BLK
    mov dx, buf
    int 0x21
    jc .wfail
    cmp ax, BLK
    jne .wshort
    pop cx
    add word [fpos], BLK
    mov bx, [fpos]
    loop .wblk

    mov ah, 0x3E
    mov bx, [handle]
    int 0x21
    jc .clfail
    mov ah, 0x09
    mov dx, msg_wrote
    int 0x21

    ; --- 2. open it again and ask its size ----------------------------------
    mov ax, 0x3D00
    mov dx, fname
    int 0x21
    jc .ofail
    mov [handle], ax

    mov ax, 0x4202                  ; seek to the end: DX:AX = the size
    mov bx, [handle]
    xor cx, cx
    xor dx, dx
    int 0x21
    jc .sfail
    push ax
    mov ah, 0x09
    mov dx, msg_size
    int 0x21
    pop ax
    call put_dec16
    call put_crlf

    ; --- 3. read it all back, checking every byte ---------------------------
    mov ax, 0x4200
    mov bx, [handle]
    xor cx, cx
    xor dx, dx
    int 0x21
    jc .sfail
    mov word [fpos], 0
.rblk:
    mov ah, 0x3F
    mov bx, [handle]
    mov cx, BLK
    mov dx, buf
    int 0x21
    jc .rfail
    or ax, ax
    jz .rdone
    mov cx, ax
    mov bx, [fpos]
    call check                      ; CF=1 with BX = the offset that differed
    jc .vfail
    add [fpos], cx
    jmp short .rblk
.rdone:
    mov ah, 0x09
    mov dx, msg_read
    int 0x21
    mov ax, [fpos]
    call put_dec16
    call put_crlf

    ; --- 4. a seek into the middle, and a read there ------------------------
    mov ax, 0x4200
    mov bx, [handle]
    xor cx, cx
    mov dx, SEEKTO
    int 0x21
    jc .sfail
    mov ah, 0x3F
    mov bx, [handle]
    mov cx, 16
    mov dx, buf
    int 0x21
    jc .rfail
    cmp ax, 16
    jne .vfail2
    mov cx, 16
    mov bx, SEEKTO
    call check
    jc .vfail                       ; check leaves BX on the byte that differed,
                                    ; and .vfail2 would overwrite it with the
                                    ; seek target - the offset is the finding
    mov ah, 0x09
    mov dx, msg_seek
    int 0x21

    ; --- 5. close, delete, and prove it is gone -----------------------------
    mov ah, 0x3E
    mov bx, [handle]
    int 0x21
    mov ah, 0x41
    mov dx, fname
    int 0x21
    jc .dfail
    mov ax, 0x3D00
    mov dx, fname
    int 0x21
    jnc .still
    cmp ax, 2
    jne .wrongerr
    mov ah, 0x09
    mov dx, msg_gone
    int 0x21
    jmp short .done

.cfail:  push ax
         mov ah, 0x09
         mov dx, msg_ecreate
         int 0x21
         pop ax
         call put_dec16
         call put_crlf
         jmp short .done
.wfail:  mov dx, msg_ewrite
         jmp short .say
.wshort: mov dx, msg_eshort
         jmp short .say
.clfail: mov dx, msg_eclose
         jmp short .say
.ofail:  mov dx, msg_eopen
         jmp short .say
.sfail:  mov dx, msg_eseek
         jmp short .say
.rfail:  mov dx, msg_eread
         jmp short .say
.dfail:  mov dx, msg_edel
         jmp short .say
.still:  mov dx, msg_estill
         jmp short .say
.wrongerr: mov dx, msg_ecode
         jmp short .say
.vfail2: mov bx, SEEKTO
.vfail:  push bx
         mov ah, 0x09
         mov dx, msg_ebad
         int 0x21
         pop ax
         call put_dec16
         call put_crlf
         jmp short .done
.say:
    mov ah, 0x09
    int 0x21
.done:
    mov ah, 0x09
    mov dx, msg_key
    int 0x21
    mov ah, 0x08
    int 0x21
    mov ax, 0x4C21
    int 0x21

; -----------------------------------------------------------------------------
; fill - buf[0..BLK) = (BX + i) & 0FFh
fill:
    push ax
    push cx
    push di
    mov di, buf
    mov ax, bx
    mov cx, BLK
.next:
    mov [di], al
    inc di
    inc ax
    loop .next
    pop di
    pop cx
    pop ax
    ret

; check - CX bytes at buf[] against (BX + i) & 0FFh
; out: CF=1 with BX = the offset that differed
check:
    push ax
    push cx
    push si
    mov si, buf
    mov ax, bx
.next:
    cmp [si], al
    jne .bad
    inc si
    inc ax
    inc bx
    loop .next
    pop si
    pop cx
    pop ax
    clc
    ret
.bad:
    pop si
    pop cx
    pop ax
    stc
    ret

put_chr:
    push ax
    push dx
    mov dl, al
    mov ah, 0x02
    int 0x21
    pop dx
    pop ax
    ret

put_crlf:
    mov al, 13
    call put_chr
    mov al, 10
    call put_chr
    ret

put_dec16:
    push ax
    push bx
    push cx
    push dx
    mov bx, 10
    xor cx, cx
.div:
    xor dx, dx
    div bx
    push dx
    inc cx
    or ax, ax
    jnz .div
.emit:
    pop ax
    add al, '0'
    call put_chr
    loop .emit
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
fname:    db 'DOSTEST.DAT', 0
handle:   dw 0
fpos:     dw 0

msg_hi:      db 13,10,'os8088 DOS file gate - DOSFILE.COM',13,10,13,10,'$'
msg_wrote:   db 'WROTE 20480 and closed',13,10,'$'
msg_size:    db 'SIZE ','$'
msg_read:    db 'READ ','$'
msg_seek:    db 'SEEK ok',13,10,'$'
msg_gone:    db 'GONE ok',13,10,'$'
msg_ecreate: db 'FAILED at create, code ','$'
msg_ewrite:  db 'FAILED at write',13,10,'$'
msg_eshort:  db 'FAILED - a short write',13,10,'$'
msg_eclose:  db 'FAILED at close',13,10,'$'
msg_eopen:   db 'FAILED at open',13,10,'$'
msg_eseek:   db 'FAILED at seek',13,10,'$'
msg_eread:   db 'FAILED at read',13,10,'$'
msg_edel:    db 'FAILED at delete',13,10,'$'
msg_estill:  db 'FAILED - it opened after the delete',13,10,'$'
msg_ecode:   db 'FAILED - the delete left the wrong error code',13,10,'$'
msg_ebad:    db 'FAILED - a wrong byte at offset ','$'
msg_key:     db 13,10,'READY - press a key to exit with code 33',13,10,'$'

    align 16
buf:
