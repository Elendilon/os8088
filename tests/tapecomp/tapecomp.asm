; =============================================================================
; tapecomp - THE GATE ON OSAPI_COMPRESS (SPEC.md 88.6)
;
; docs/plans/CASSETTE-PLAN.md makes this wave 4's gate. The cell publishes an
; ENCODER beside OSAPI_DECOMP for the first time, and the thing worth proving
; is not that it compresses - it is that THE TWO AGREE. A stream this machine
; packs has to be one this machine expands, byte for byte, because on a tape
; there is no second copy to fall back to.
;
; **THE ROUND TRIP IS THE TEST.** Ratio is not asserted at all: it is data-
; dependent, it is measured on the host by tools/os88tape.py, and a row that
; asserted a percentage would go red the day the parser improved. What is
; asserted is that the bytes come back.
;
; Four things, one results byte each:
;
;   * compressible data compresses, the packed length is strictly less than
;     the source, and the format byte is LZB - the byte a 'CZ' container's +2
;     wants, and the only format the machine's encoder writes (SPEC.md 20.15).
;   * OSAPI_DECOMP expands that stream to the IDENTICAL bytes. 2 KB compared
;     one at a time, and the first difference is reported by offset so a
;     failure names where rather than that.
;   * INCOMPRESSIBLE data answers CF=1 with OSAPI_CMP_NOGAIN, which is the
;     ORDINARY answer for an already-compressed file and not an error. It is
;     the arm the tape writer takes for every 'CZ' file and every packed
;     .o88, so it is not an edge case - it is the common path.
;   * the registers the contract promises come back.
;
; It needs no cassette and no tape: the cell is a kernel contract.
;
; NEVER SHIPPED. Its own scratch image, the lzfence precedent:
;   make tapecomptest && python3 tests/tapecomp.py
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'TAPECOMP', tc_entry

TC_MAGIC    equ 0x4354          ; 'TC'
TC_KB       equ 2               ; each of the three buffers
TC_LEN      equ 2048            ; ...and the bytes we use of them

; -----------------------------------------------------------------------------
tc_entry:
    mov ax, TC_KB               ; the source
    call OSAPI_MEM_CLAIM
    jc .nomem
    mov [tc_src], dx
    mov ax, TC_KB               ; the packed stream
    call OSAPI_MEM_CLAIM
    jc .nomem
    mov [tc_pak], dx
    mov ax, TC_KB               ; ...and what it expands back to
    call OSAPI_MEM_CLAIM
    jc .nomem
    mov [tc_out], dx

    ; --- 1. a compressible source: 2 KB of a short repeating run ------------
    mov es, [tc_src]
    xor di, di
    mov cx, TC_LEN
    cld
    xor bx, bx
.fill:
    mov al, bl
    and al, 0x0F                ; a 16-byte cycle: LZB should eat this whole
    stosb
    inc bx
    loop .fill

    ; --- 2. compress it -----------------------------------------------------
    mov ax, [tc_src]
    mov cx, TC_LEN
    mov dx, [tc_pak]
    mov si, 0x1111              ; poison the registers the contract promises
    mov di, 0x2222              ; back, and check them below
    mov bp, 0x3333
    call OSAPI_COMPRESS
    mov [tc_r_ax], ax           ; the packed length, or the refusal
    mov [tc_r_bl], bl
    pushf
    pop bx
    and bl, 1
    mov [tc_r_cf], bl
    ; the promised registers
    mov al, 1
    cmp cx, TC_LEN
    je .ck1
    xor al, al
.ck1:
    cmp si, 0x1111
    je .ck2
    xor al, al
.ck2:
    cmp di, 0x2222
    je .ck3
    xor al, al
.ck3:
    cmp bp, 0x3333
    je .ck4
    xor al, al
.ck4:
    mov [tc_r_regs], al

    cmp byte [tc_r_cf], 0
    jne .done                   ; it refused: the driver says so, and there is
                                ; nothing to round-trip

    ; --- 3. ...and expand it straight back ----------------------------------
    ; OSAPI_DECOMP: DS:SI = the stream, CX = its length, ES:0 = the
    ; destination with DI = 0, BX:DX = the EXACT expected output, AL = format.
    ; BOTH SEGMENTS OUT OF THE PACKAGE FIRST. `mov ds, [tc_pak]` and then
    ; `mov es, [tc_out]` reads tc_out out of the SOURCE buffer, because DS has
    ; already moved - which assembles cleanly and hands the decoder a
    ; destination made of whatever happened to be there.
    mov es, [tc_out]
    mov cx, [tc_r_ax]
    mov al, [tc_r_bl]
    push ds
    mov ds, [tc_pak]
    xor si, si
    xor di, di
    mov bx, 0
    mov dx, TC_LEN
    call OSAPI_DECOMP
    pop ds
    sbb al, al
    mov [tc_r_dcf], al

    ; compare the two buffers byte for byte
    mov es, [tc_out]            ; ...and the same trap here
    push ds
    mov ds, [tc_src]
    xor si, si
    xor di, di
    mov cx, TC_LEN
    cld
    repe cmpsb
    pop ds
    mov al, 1
    jcxz .same
    xor al, al
.same:
    mov [tc_r_same], al

    ; --- 4. INCOMPRESSIBLE data must answer NOGAIN --------------------------
    ; A 16-bit LCG. It is not a good generator and does not need to be: what
    ; it has to be is something LZB cannot find a match in.
    mov es, [tc_src]
    xor di, di
    mov cx, TC_LEN
    mov bx, 0xACE1
.rnd:
    mov ax, bx
    mov dx, 25173
    mul dx
    add ax, 13849
    mov bx, ax
    mov al, ah
    stosb
    loop .rnd

    mov ax, [tc_src]
    mov cx, TC_LEN
    mov dx, [tc_pak]
    call OSAPI_COMPRESS
    mov [tc_r_nax], ax
    pushf
    pop bx
    and bl, 1
    mov [tc_r_ncf], bl

.done:
.nomem:
    stc                         ; no window: there is nothing to look at, and
    retf                        ; one would only be a thing to close

; -----------------------------------------------------------------------------
; THE DRIVER'S ABI (tests/tapecomp.py). 0x3F = never reached.
            dw TC_MAGIC
tc_r_cf:    db 0x3F             ; the compress CF          -> want 0
tc_r_ax:    dw 0x3F3F           ; ...the packed length     -> want < TC_LEN
tc_r_bl:    db 0x3F             ; ...the format            -> want OSAPI_LZ_LZB
tc_r_regs:  db 0x3F             ; CX/SI/DI/BP came back    -> want 1
tc_r_dcf:   db 0x3F             ; the decompress CF        -> want 0
tc_r_same:  db 0x3F             ; the bytes are identical  -> want 1
tc_r_ncf:   db 0x3F             ; incompressible: CF       -> want 1
tc_r_nax:   dw 0x3F3F           ; ...and why  -> want OSAPI_CMP_NOGAIN

tc_src:     dw 0
tc_pak:     dw 0
tc_out:     dw 0

    OS88_IMAGE_END
