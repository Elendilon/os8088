; =============================================================================
; os8088 - tests/dostrap/dwtty.asm - DWTTY.COM, how fast a windowed program
; PRINTS (SPEC.md 96.54.12)
;
; Three ways a DOS program puts text on the screen, each started by a key and
; each counted into the word at PSP:0103h when it is done - so guest seconds
; from the key to the count are its time, in the bracket and in a window:
;
;   9   LINES lines through INT 21h AH=09h, CR LF each: a command-line
;       utility, and a scroll a line
;   e   the same lines through INT 10h AH=0Eh, the ROM teletype a character
;       at a time
;   b   ROWS rows of COLS characters the way a compiled BASIC PRINT puts
;       them: INT 10h AH=02h to the cell, AH=09h with CX = 1, AH=02h to the
;       next - three calls a character, and no scroll (Galaxy Trek, 96.54.11)
;   q   exit
;
; It runs under a real IBM DOS 3.30 unchanged.
; =============================================================================
cpu 8086
org 0x100

LINES   equ 100
ROWS    equ 20
COLS    equ 66                      ; inside msg's printable part

    jmp short start
    nop
done:   dw 0                        ; PSP:0103h, one more per finished run
start:
    xor ah, ah
    int 0x16
    cmp al, 'q'
    je .quit
    cmp al, '9'
    je .p9
    cmp al, 'e'
    je .pe
    cmp al, 'b'
    je .pb
    jmp short start
.quit:
    mov ah, 0x4C
    int 0x21

.p9:
    mov cx, LINES
.l9:
    push cx
    mov dx, msg
    mov ah, 9
    int 0x21
    pop cx
    loop .l9
    jmp short .done

.pe:
    mov cx, LINES
.le:
    mov si, msg
.ce:
    lodsb
    cmp al, '$'
    je .ne
    push si
    mov ah, 0x0E
    mov bx, 0x0007
    int 0x10
    pop si
    jmp short .ce
.ne:
    loop .le
    jmp short .done

.pb:
    mov dh, 2                       ; rows 2.. so nothing scrolls
.rb:
    xor dl, dl
    mov si, msg
.cb:
    mov ah, 2
    xor bh, bh
    int 0x10                        ; to the cell...
    lodsb
    mov ah, 9
    mov bx, 0x0007
    push cx
    mov cx, 1
    int 0x10                        ; ...the character...
    pop cx
    inc dl
    mov ah, 2
    xor bh, bh
    int 0x10                        ; ...and the cursor on past it
    cmp dl, COLS
    jb .cb
    inc dh
    cmp dh, ROWS + 2
    jb .rb
.done:
    inc word [done]
    jmp start

msg: db "The quick brown fox jumps over the lazy dog, line after line of it.", 13, 10, "$"
