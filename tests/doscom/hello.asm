; =============================================================================
; os8088 - tests/doscom/hello.asm
;
; The wave-1 gate's DOS program (SPEC.md 96.7). A .COM, hand-written, and
; deliberately the smallest thing that exercises every load-bearing piece of
; docs/plans/DOS-EXEC-PLAN.md's wave 1 at once:
;
;   - it is ENTERED at PSP:0100 with DS=ES=SS=CS on the PSP, which is what
;     dos_build_psp has to have got right;
;   - it reads PSP:0002, the top-of-memory word, which is the first of the
;     four ways a DOS program asks how much memory it has (2.1) and the one
;     the arena's whole containment argument rests on;
;   - it prints through INT 21h AH=09h, which is the ROM teletype path;
;   - it asks INT 21h AH=30h for the DOS version;
;   - and it exits through AH=4Ch with a NON-ZERO code, so the window has to
;     survive and show it (SPEC.md 96.1).
;
; NOTHING HERE IS THIRD-PARTY. It is ours, MIT with the rest of the tree, and
; it is under tests/ because it is not shipped software (CLAUDE.md, Layout).
; =============================================================================

    cpu 8086
    bits 16
    org 0x100                   ; where DOS enters a .COM, and where every
                                ; address below is resolved from

start:
    mov ah, 0x09                ; --- 1. say who we are -----------------------
    mov dx, msg_hi
    int 0x21

    mov ah, 0x30                ; --- 2. the DOS version ----------------------
    int 0x21
    push ax
    mov ah, 0x09
    mov dx, msg_ver
    int 0x21
    pop ax
    push ax
    call put_dec                ; AL = the major
    mov al, '.'
    call put_chr
    pop ax
    mov al, ah                  ; ...and AH = the minor
    call put_dec
    call put_crlf

    mov ah, 0x09                ; --- 3. the top-of-memory word ---------------
    mov dx, msg_mem
    int 0x21
    mov ax, [es:0x0002]         ; ES is still the PSP: this is the paragraph
    mov bx, cs                  ; past our block, so minus our own base is the
    sub ax, bx                  ; size of it in paragraphs, and >> 6 is KB.
    mov cl, 6                   ; `sub ax, cs` is not an 8086 instruction -
    shr ax, cl                  ; a segment register is not an ALU operand
    call put_dec16              ; SIXTEEN bits: put_dec takes AL alone, and a
                                ; real arena is hundreds of KB - feeding it one
                                ; prints the low byte, so 520 reads as 8 and
                                ; looks exactly like a broken PSP:0002
    mov ah, 0x09
    mov dx, msg_kb
    int 0x21

    mov ah, 0x09                ; --- 4. an UNSUPPORTED call, on purpose ------
    mov dx, msg_bad             ; wave 1 must REFUSE rather than hang, and the
    int 0x21                    ; window names the function (SPEC.md 96.7)
    mov ah, 0x3D                ; open a file: not in wave 1
    xor al, al
    mov dx, msg_hi
    int 0x21
    jc .refused
    mov dx, msg_nocf            ; it answered - which is a FAILURE of the gate
    mov ah, 0x09
    int 0x21
    jmp short .done
.refused:
    mov dx, msg_cf
    mov ah, 0x09
    int 0x21
.done:

    mov ah, 0x09                ; --- 5. wait, so the screen can be READ ------
    mov dx, msg_key             ; a program that prints and exits leaves its
    int 0x21                    ; output on the glass for microseconds, which
    mov ah, 0x08                ; no harness can catch. This is also what a
    int 0x21                    ; real DOS program does, so it costs the gate
                                ; nothing in realism

    mov ax, 0x4C2A              ; --- 6. exit with 42 -------------------------
    int 0x21                    ; non-zero on purpose: the window has to stay
                                ; open and show it

; -----------------------------------------------------------------------------
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

; put_dec16 - AX (0..65535) as decimal, no leading zeros
put_dec16:
    push ax
    push bx
    push cx
    push dx
    mov bx, 10
    xor cx, cx                  ; CX counts the digits pushed
.div:
    xor dx, dx
    div bx                      ; DX:AX / 10 -> AX quotient, DX remainder
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

; put_dec - AL (0..255) as decimal, no leading zeros
put_dec:
    push ax
    push bx
    push cx
    xor ah, ah
    mov bl, 100
    div bl                      ; AL = hundreds, AH = the rest
    mov ch, ah
    or al, al
    jz .tens
    add al, '0'
    call put_chr
    mov al, ch
    xor ah, ah
    mov bl, 10
    div bl
    add al, '0'
    call put_chr
    jmp short .ones
.tens:
    mov al, ch
    xor ah, ah
    mov bl, 10
    div bl
    or al, al
    jz .ones
    add al, '0'
    call put_chr
.ones:
    add ah, '0'
    mov al, ah
    call put_chr
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
msg_hi:   db 13,10,'os8088 DOS gate - HELLO.COM',13,10,13,10,'$'
msg_ver:  db 'DOS version ','$'
msg_mem:  db 'Memory to top of block: ','$'
msg_kb:   db ' KB',13,10,'$'
msg_bad:  db 'Asking for an unsupported call...',13,10,'$'
msg_cf:   db 'refused with CF, as it should be',13,10,'$'
msg_nocf: db 'ANSWERED - the gate has FAILED',13,10,'$'
msg_key:  db 13,10,'READY - press a key to exit with code 42',13,10,'$'
