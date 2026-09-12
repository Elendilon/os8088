; RENREF.COM - what AH=56h (Rename) really answers.
; OURS, MIT with the rest of the tree.  docs/DOS-DEBUGGING.md is the manual.
;
; DOS uses this call for TWO things - rename a file, and MOVE one between
; directories of a volume by re-linking its entry - and os8088's
; OSAPI_FILE_RENAME is a directory-entry rewrite in the folder you are
; standing in (SPEC.md 18.4). So the question is not "does rename work", it is
; which of these DOS answers with an error and which it does silently, and
; what the codes are.
;
;   nasm -f bin -o RENREF.COM tests/dostrap/renref.asm
;
; It runs UNDER A REAL DOS UNCHANGED, and it WRITES - so the disk it runs from
; must be writable and is left with T2.TXT on it.
;
; A line reads   <what> AX=hhhh CF=n
; and the two rows that decide the implementation are the last two: a rename
; whose target already EXISTS, and one that names a different DRIVE.

    org 0x100
    cpu 8086

start:
    mov dx, f_t1                ; the file this is all about
    call make

    mov si, s_1
    mov dx, f_t1
    mov di, f_t2
    call try                    ; 1. the ordinary rename

    mov si, s_2
    mov dx, f_t1
    mov di, f_t3
    call try                    ; 2. ...of a file that is no longer there

    mov si, s_3
    mov dx, f_t2
    mov di, f_t2
    call try                    ; 3. ...onto its own name

    mov si, s_4
    mov dx, f_t2d
    mov di, f_t4
    call try                    ; 4. the OLD name carries a drive

    mov dx, f_t4                ; ...AND A FILE FOR EACH OF THE LAST TWO. Row
    call make                   ; 4 was always going to fail, so rows 5 and 6
    mov si, s_5                 ; inherited a source that was never created
    mov dx, f_t4                ; and both answered "file not found" - which
    mov di, f_t5a               ; is a measurement of the probe, not of DOS
    call try                    ; 5. the NEW name names a DIFFERENT drive

    mov dx, f_t4
    call make
    mov si, s_6
    mov dx, f_t4
    mov di, f_sub
    call try                    ; 6. a PATH as the new name: DOS's MOVE

    mov si, s_done
    call puts
    xor ax, ax
    int 0x16
    mov ax, 0x4C00
    int 0x21

; --- make - create (or truncate) the file named at DS:DX ---------------------
make:
    push ax
    push bx
    push cx
    push dx
    xor cx, cx
    mov ah, 0x3C
    int 0x21
    jc .o
    mov bx, ax
    mov ah, 0x3E
    int 0x21
.o:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- try - AH=56h with DS:DX and ES:DI, reported -----------------------------
try:
    push dx
    push di
    call puts                   ; SI is the label, and puts leaves it past NUL
    pop di
    pop dx
    push ds
    pop es                      ; ES:DI = the new name, in our own segment
    mov ah, 0x56
    int 0x21
    pushf
    push ax
    mov si, s_ax
    call puts
    pop ax
    call puthex
    mov si, s_cf
    call puts
    pop ax
    and al, 1
    add al, '0'
    call putc
    mov si, s_crlf
    jmp puts

puthex:
    push cx
    mov cx, 4
.d:
    rol ax, 1
    rol ax, 1
    rol ax, 1
    rol ax, 1
    push ax
    and al, 0x0F
    add al, '0'
    cmp al, '9'
    jbe .ok
    add al, 7
.ok:
    call putc
    pop ax
    loop .d
    pop cx
    ret

putc:
    push ax
    push dx
    mov dl, al
    mov ah, 0x02
    int 0x21
    pop dx
    pop ax
    ret

puts:
    lodsb
    or al, al
    jz .o
    call putc
    jmp short puts
.o:
    ret

f_t1:   db 'T1.TXT', 0
f_t2:   db 'T2.TXT', 0
f_t3:   db 'T3.TXT', 0
f_t4:   db 'T4.TXT', 0
f_t2d:  db 'B:T2.TXT', 0
f_t5a:  db 'A:T5.TXT', 0
f_sub:  db '\T6.TXT', 0

s_1:    db 'rename        ', 0
s_2:    db 'gone          ', 0
s_3:    db 'onto itself   ', 0
s_4:    db 'old has drive ', 0
s_5:    db 'new other drv ', 0
s_6:    db 'new is a path ', 0
s_ax:   db 'AX=', 0
s_cf:   db ' CF=', 0
s_crlf: db 13, 10, 0
s_done: db 'RENREF READY', 13, 10, 0
