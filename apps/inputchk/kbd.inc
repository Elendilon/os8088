; =============================================================================
; os8088 - apps/inputchk/kbd.inc - the KEYBOARD section (SPEC.md 136.11)
;
; The other half of the 8042. A PS/2 keyboard and a PS/2 mouse share one
; controller, and the field case this section exists for - an STPC board whose
; keyboard is "sometimes not recognised" under os8088 alone - is the same
; controller the PS/2 section is about. So the keyboard is read with the same
; two disciplines:
;
; PASSIVE, every refresh (kb_sample, from mc_tick and once at open): the BIOS
; data area's keyboard bytes, the BIOS buffer's tail (every key the ROM's int
; 09h stored moves it, whoever reads the key afterwards), the three vectors the
; keyboard path runs through, the master 8259's mask and request bits for IRQ1,
; and port 64h's status. A keyboard byte that SITS in the output buffer across
; refreshes is the signature of an IRQ1 nobody is servicing; it is counted
; rather than read, because reading 60h would take it.
;
; ACTIVE, only on K or in the automatic run (kb_check, SPEC.md 136.11.2): with
; IRQ1 and IRQ12 masked, the keyboard interface off (0xAD) - mou_p2_init's own
; discipline - read the command byte NOW (0x20), the output port (0xD0), run
; the keyboard interface test (0xAB), turn the interface back on (0xAE) and
; send the KEYBOARD an echo (0xEE), which only a keyboard that can clock a byte
; both ways answers. Every step waits in ticks and every exit restores the
; masks bit by bit. A byte already waiting before 0xAD is taken and SHOWN: it is
; the keystroke (or reply) the machine never delivered.
;
; Label prefix kb_. ES = KERNEL_SEG, DS = the package, on entry to every proc
; the shell calls.
; =============================================================================

KB_LOWP     equ 0x0002          ; the window's paragraph: int 08h's cell
KB_LOWN     equ 0x04E0          ; ...to the BDA's end (0x020 .. 0x4FF)
KB_V09      equ 0x24 - 0x20     ; int 09h, 15h, 16h's vectors in that window
KB_V15      equ 0x54 - 0x20
KB_V16      equ 0x58 - 0x20
KB_FLAG     equ 0x417 - 0x20    ; shift states
KB_FLAG1    equ 0x418 - 0x20
KB_HEAD     equ 0x41A - 0x20    ; the BIOS buffer: head and tail offsets
KB_TAIL     equ 0x41C - 0x20
KB_BSTART   equ 0x480 - 0x20    ; ...and its bounds (AT BIOSes)
KB_BEND     equ 0x482 - 0x20
KB_FLAG3    equ 0x496 - 0x20    ; 101-key, E0/E1 prefixes, ID read
KB_FLAG2    equ 0x497 - 0x20    ; LEDs, ACK, RESEND, LED update, ERROR

KB_TMO      equ 2               ; ticks a controller step may take
KB_ETMO     equ 4               ; ...and the keyboard's echo

KBO_P2M1    equ MOP_SIZE + 1 + 4 ; mou_p2m1 past the span: cmdr, then the
                                ; old int 74h vector (kern_big's layout,
                                ; held by tests/unit/t_inputchk.py)

; -----------------------------------------------------------------------------
; kb_init - once at open. Keeps every register
; -----------------------------------------------------------------------------
kb_init:
    push ax
    push bx
    push cx
    push dx
    push es
    mov dx, KB_LOWP
    mov cx, KB_LOWN
    xor ax, ax
    mov bl, SEG_WIN
    call OSAPI_SEG                  ; DX = a window over it (a selector on
    jc .out                         ; kern_mega, the paragraph elsewhere)
    mov [kb_lowsel], dx
    inc byte [kb_lowok]
    mov es, dx
    mov ax, [es:KB_TAIL]
    mov [kb_tail0], ax
    mov al, [es:KB_FLAG]
    mov [kb_flag0], al
.out:
    pop es
    pop dx
    pop cx
    pop bx
    pop ax
    jmp kb_sample

; -----------------------------------------------------------------------------
; kb_sample - one passive sample (every refresh). Keeps every register.
; NO WRITE TO A KEYBOARD PORT: 64h and 21h are read, and the 8259's OCW3 is
; written to read the request register, which selects a register and changes
; nothing else (it is left on IRR, the state after initialisation)
; -----------------------------------------------------------------------------
kb_sample:
    push ax
    push bx
    push cx
    push dx
    push es
    cmp byte [p2_tier], CPU_8086    ; an XT has an 8255 and no 64h: the
    je .bda                         ; BIOS's half still applies
    in  al, 0x64
    mov [kb_s64], al
    cmp al, 0xFF
    je .bda
    test al, 0x01                   ; OBF: a byte, EITHER side's - an AUX
    jz .noobf                       ; byte nobody reads blocks the keyboard
    and al, 0x20                    ; exactly as a keyboard byte does
    or  [kb_obfaux], al             ; (SPEC.md 9.9.1.1): bit 5 remembered
    inc byte [kb_obfn]              ; still there
    jnz .obfmx
    dec byte [kb_obfn]
.obfmx:
    mov al, [kb_obfn]
    cmp al, [kb_obfmax]
    jbe .bda0
    mov [kb_obfmax], al
    jmp short .bda0
.noobf:
    mov byte [kb_obfn], 0
.bda0:
.bda:
    pushf
    cli
    in  al, 0x21
    mov [kb_imr], al
    mov al, 0x0A                    ; OCW3: read the IRR
    out 0x20, al
    in  al, 0x20
    popf
    mov [kb_irr], al
    test al, 0x02
    jz .nirr
    inc word [kb_irrn]
.nirr:
    inc word [kb_nsamp]
    cmp byte [kb_lowok], 0
    je .out
    mov es, [kb_lowsel]
    mov al, [es:KB_FLAG]            ; a shift key changes this and never
    cmp al, [kb_flag0]              ; the buffer
    je .tl
    mov [kb_flag0], al
    inc word [kb_mods]
.tl:
    mov ax, [es:KB_TAIL]            ; keys the ROM stored since the last look
    mov dx, ax
    sub ax, [kb_tail0]
    jz .out
    mov [kb_tail0], dx
    jnc .pos
    mov bx, [es:KB_BEND]            ; it wrapped: add the buffer's length
    sub bx, [es:KB_BSTART]
    cmp bx, 2
    ja .len
    mov bx, 32                      ; no bounds published: the IBM 16 keys
.len:
    add ax, bx
.pos:
    shr ax, 1                       ; a key is a word
    add [kb_bios], ax
    cmp byte [kb_chkd], 0
    je .out
    add [kb_biosx], ax              ; ...and since the controller check
.out:
    pop es
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; kb_onkey - a key reached the window (the shell counts before it acts)
kb_onkey:
    inc word [kb_mine]
    cmp byte [kb_chkd], 0
    je .r
    inc word [kb_minex]
.r:
    ret

; =============================================================================
; kb_check - the controller check (SPEC.md 136.11.2). UI task, synchronous,
; about a quarter of a second on a controller that answers. Keeps nothing.
; =============================================================================
kb_check:
    cmp byte [p2_tier], CPU_8086
    jne .at
    ret
.at:
    in  al, 0x64
    cmp al, 0xFF
    jne .go
    ret
.go:
    push es
    push ds
    pop es
    mov di, kb_ck
    mov cx, KBC_N
    xor al, al
    cld
    rep stosb
    pop es
    call OSAPI_GET_TICKS
    or  al, 1
    mov [kb_ckt], ax
    ; THE KEY THAT ASKED IS STILL DOWN (p2x_run's reason): IRQ1 stays live for
    ; a few ticks so its release reaches int 09h, not the flush below
    call p2x_keyw
    in  al, 0x21
    mov [kb_m1], al
    in  al, 0xA1
    mov [kb_m2], al
    mov ax, 0x0210
    call p2x_mset                   ; IRQ1 and IRQ12 off at the 8259s

    in  al, 0x64
    mov [kb_ck+KBC_S0], al
    test al, 0x01                   ; A BYTE IS ALREADY WAITING: take it, and
    jz .ad                          ; say whose (bit 5)
    mov [kb_ck+KBC_WS], al
    in  al, 0x60
    mov [kb_ck+KBC_WB], al
    or  byte [kb_ck+KBC_OK], KBF_WAIT

.ad:
    mov al, 0xAD                    ; the keyboard interface off
    call kb_cmd
    jc .wedge
    call kb_flush
    mov al, 0x20                    ; the command byte, NOW
    call kb_cmd
    jc .wedge
    call kb_rd
    jc .nocmd
    mov [kb_ck+KBC_CMD], al
    or  byte [kb_ck+KBC_OK], KBF_CMD
.nocmd:
    mov al, 0xD0                    ; the output port: A20, the keyboard's
    call kb_cmd                     ; clock and data lines as driven
    jc .wedge
    call kb_rd
    jc .noout
    mov [kb_ck+KBC_OUT], al
    or  byte [kb_ck+KBC_OK], KBF_OUT
.noout:
    mov al, 0xAB                    ; the keyboard interface test: 00 good,
    call kb_cmd                     ; 01-04 a clock or data line stuck
    jc .wedge
    call kb_rd
    jc .noab
    mov [kb_ck+KBC_AB], al
    or  byte [kb_ck+KBC_OK], KBF_AB
.noab:
    ; 0xAB may itself leave the interface disabled on some controllers, so
    ; the command byte goes back as it was READ (bit 4 is 0xAD's own and
    ; 0xAE below clears it), and only if it was read at all
    test byte [kb_ck+KBC_OK], KBF_CMD
    jz .ae
    mov al, 0x60
    call kb_cmd
    jc .wedge
    mov al, [kb_ck+KBC_CMD]
    call kb_dat
    jc .wedge
.ae:
    call kb_flush
    mov al, 0xAE                    ; the keyboard interface on
    call kb_cmd
    jc .wedge
    ; --- the keyboard itself: ECHO. Still with IRQ1 masked, so int 09h never
    ; sees the answer. A keystroke racing it is told apart by its value
    mov al, 0xEE
    call kb_dat
    jc .wedge
    call OSAPI_GET_TICKS
    mov dx, ax
.ew:
    in  al, 0x64
    test al, 0x01
    jnz .eg
    call OSAPI_GET_TICKS
    sub ax, dx
    cmp ax, KB_ETMO
    jb .ew
    jmp short .done
.eg:
    mov [kb_ck+KBC_ES], al
    in  al, 0x60
    mov [kb_ck+KBC_EB], al
    or  byte [kb_ck+KBC_OK], KBF_ECHO
    jmp short .done
.wedge:
    or  byte [kb_ck+KBC_OK], KBF_WEDGE
    mov al, 0xAE                    ; whatever stalled, the interface ON
    out 0x64, al                    ; (a bare write: the wait already failed)
.done:
    in  al, 0x64
    mov [kb_ck+KBC_S1], al
    mov ah, [kb_m1]                 ; the two mask bits as found
    mov al, [kb_m2]
    and ax, 0x0210
    call p2x_mset
    or  byte [kb_ck+KBC_OK], KBF_RAN
    mov byte [kb_chkd], 1
    ret

; kb_cmd / kb_dat - AL to 64h / 60h after IBF clears. CF = 1 never took it
kb_cmd:
    call kb_wr
    jc .r
    out 0x64, al
.r:
    ret
kb_dat:
    call kb_wr
    jc .r
    out 0x60, al
.r:
    ret

; kb_wr - wait for IBF clear, KB_TMO ticks. CF = 1 timed out. Keeps all
kb_wr:
    push ax
    push dx
    call OSAPI_GET_TICKS
    mov dx, ax
.w:
    in  al, 0x64
    test al, 0x02
    jz .ok                          ; (test cleared CF)
    call OSAPI_GET_TICKS
    sub ax, dx
    cmp ax, KB_TMO
    jb .w
    stc
.ok:
    pop dx
    pop ax
    ret

; kb_rd - the next byte, KB_TMO ticks. out AL, CF = 1 none. Keeps the rest
kb_rd:
    push dx
    call OSAPI_GET_TICKS
    mov dx, ax
.w:
    in  al, 0x64
    test al, 0x01
    jnz .g
    call OSAPI_GET_TICKS
    sub ax, dx
    cmp ax, KB_TMO
    jb .w
    stc
    jmp short .o
.g:
    in  al, 0x60
    clc
.o:
    pop dx
    ret

; kb_flush - empty the output buffer, bounded. Keeps everything
kb_flush:
    push ax
    push cx
    mov cx, 16
.f:
    in  al, 0x64
    test al, 0x01
    jz .o
    in  al, 0x60
    loop .f
.o:
    pop cx
    pop ax
    ret

; =============================================================================
; kb_rows - the section
; =============================================================================
kb_rows:
    mov byte [kb_lp], LP_OK
    mov si, kb_s_head
    mov al, LP_INFO
    call mc_head

    ; --- does a keystroke get anywhere? ---------------------------------
    mov si, kb_rv_bios
    call mc_row
    mov ax, [kb_bios]
    call mc_dec
    mov si, kb_s_shift
    call mc_put
    mov ax, [kb_mods]
    call mc_dec
    mov al, ')'
    call mc_putc
    mov si, kb_rv_mine
    call mc_row
    mov ax, [kb_mine]
    call mc_dec
    cmp byte [kb_chkd], 0
    je .nox
    mov si, kb_rv_after
    call mc_row
    mov ax, [kb_biosx]
    call mc_dec
    mov si, kb_s_bios
    call mc_put
    mov ax, [kb_minex]
    call mc_dec
    mov si, kb_s_here
    call mc_put
.nox:
    cmp byte [kb_lowok], 0
    jne .bda
    jmp .vec9
.bda:
    push es
    mov es, [kb_lowsel]
    mov si, kb_rv_buf               ; head tail, and how many wait
    call mc_row
    mov ax, [es:KB_HEAD]
    call mc_hex16
    mov al, ' '
    call mc_putc
    mov ax, [es:KB_TAIL]
    call mc_hex16
    mov al, ' '
    call mc_putc
    mov ax, [es:KB_BSTART]
    call mc_hex16
    mov al, '-'
    call mc_putc
    mov ax, [es:KB_BEND]
    call mc_hex16
    mov si, kb_rv_flag              ; 40:17 40:18, the toggles by name
    call mc_row
    mov al, [es:KB_FLAG]
    call mc_hex8
    mov al, ' '
    call mc_putc
    mov al, [es:KB_FLAG1]
    call mc_hex8
    mov al, ' '
    call mc_putc
    mov al, [es:KB_FLAG]
    mov si, kb_b_flag
    call mc_bits
    mov si, kb_rv_flag2             ; 40:97: the LED handshake's bits
    call mc_row
    mov al, [es:KB_FLAG2]
    call mc_hex8
    mov al, ' '
    call mc_putc
    mov al, [es:KB_FLAG2]
    mov si, kb_b_flag2
    call mc_bits
    mov al, [es:KB_FLAG2]
    mov [kb_f2], al
    mov si, kb_rv_flag3             ; 40:96: bit 4 a 101-key keyboard
    call mc_row
    mov al, [es:KB_FLAG3]
    call mc_hex8
    mov si, kb_s_101
    test al, 0x10
    jnz .k101
    mov si, kb_s_84
.k101:
    call mc_put
    ; --- the three vectors the keyboard path runs through -----------------
    mov bx, KB_V09
    mov si, kb_rv_v09
    call kb_vec
    mov [kb_v9k], al
    mov bx, KB_V15
    mov si, kb_rv_v15
    call kb_vec
    mov [kb_v15k], al
    mov bx, KB_V16
    mov si, kb_rv_v16
    call kb_vec
    pop es
    mov si, kb_rv_hook              ; which of the kernel's two hooks
    call mc_row                     ; (SPEC.md 9.7.2)
    mov si, kb_s_h15
    cmp byte [kb_v15k], 0
    jne .hk
    mov si, kb_s_h09
    cmp byte [kb_v9k], 0
    jne .hk
    mov si, kb_s_hnone
.hk:
    call mc_put
    test byte [kb_f2], 0x80         ; the ROM's own transmit-error flag
    jz .vec9
    mov al, LP_WARN
    call kb_worse
    mov si, kb_l_txerr
    call mc_line
.vec9:
    ; --- the interrupt controller ----------------------------------------
    mov si, kb_rv_irq1
    call mc_row
    mov si, p2_s_open
    test byte [kb_imr], 0x02
    jz .im
    mov si, p2_s_shut
.im:
    call mc_put
    mov si, kb_s_req
    call mc_put
    mov ax, [kb_irrn]
    call mc_dec
    mov al, '/'
    call mc_putc
    mov ax, [kb_nsamp]
    call mc_dec
    mov si, kb_s_samp
    call mc_put
    test byte [kb_imr], 0x02
    jz .imok
    mov al, LP_BAD
    call kb_worse
    mov si, kb_l_masked
    call mc_line
.imok:
    cmp byte [p2_tier], CPU_8086
    jne .ctl
    mov si, kb_l_xt
    call mc_line
    jmp .verdict
.ctl:
    ; --- the 8042, passively ---------------------------------------------
    mov si, kb_rv_64
    call mc_row
    mov al, [kb_s64]
    call kb_st
    mov si, kb_rv_obf               ; a keyboard byte left waiting
    call mc_row
    mov al, [kb_obfmax]
    xor ah, ah
    call mc_dec
    mov si, kb_s_obf
    call mc_put
    cmp byte [kb_obfaux], 0
    je .oa
    mov si, kb_s_oaux               ; at least one of them was the AUX side's
    call mc_put
.oa:
    cmp byte [kb_obfmax], 3
    jb .boot
    mov al, LP_BAD
    call kb_worse
    mov si, kb_l_stuck
    call mc_line
    mov si, kb_l_stuck2
    cmp byte [kb_obfaux], 0
    je .ok2
    mov si, kb_l_stuck3             ; an aux byte: IRQ12, masked or not taken
.ok2:
    call mc_line
.boot:
    ; --- what the kernel's boot did to the controller (SPEC.md 9.9.1) -----
    cmp byte [mc_kok], 0
    je .ck
    mov bx, [p2_sp]
    or bx, bx
    jz .ck
    mov si, kb_rv_bcmd
    call mc_row
    mov al, [es:bx+MOP_CMD0+1]      ; mou_p2cmdr: the BIOS's byte, bit 4 clear
    mov [kb_bcmd], al
    cmp byte [es:bx+MOP_ST], 2
    jae .bc
    mov si, kb_s_nread
    call mc_put
    jmp short .rst
.bc:
    call kb_cmdw
.rst:
    mov si, kb_rv_reset             ; did the boot's probe send D4 FF?
    call mc_row
    mov al, [es:bx+MOP_ST]
    mov si, kb_s_rsno
    cmp al, 4
    jb .rs
    mov si, kb_s_rsyes
    cmp byte [es:bx+MOP_P2], 0
    jne .rs
    cmp al, 9
    jae .rs
    mov si, kb_s_rsfail
.rs:
    call mc_put
    test byte [p2_cpuf], CPU_F_PM   ; mou_p2m1 is kern_big's layout only
    jnz .ck
    mov si, kb_rv_bm1
    call mc_row
    mov al, [es:bx+KBO_P2M1]
    mov si, p2_s_open
    test al, 0x02
    jz .bm
    mov si, p2_s_shut
.bm:
    call mc_put
.ck:
    ; --- the controller check, if it ran ----------------------------------
    test byte [kb_ck+KBC_OK], KBF_RAN
    jnz .ran
    mov si, kb_l_nock
    call mc_line
    jmp .verdict
.ran:
    mov si, kb_rv_ckb
    call mc_row
    mov al, [kb_ck+KBC_S0]
    call kb_st
    test byte [kb_ck+KBC_OK], KBF_WAIT
    jz .nw
    mov si, kb_rv_wait
    call mc_row
    mov al, [kb_ck+KBC_WB]
    call mc_hex8
    mov si, kb_s_wkbd
    test byte [kb_ck+KBC_WS], 0x20
    jz .ww
    mov si, kb_s_waux
.ww:
    call mc_put
.nw:
    mov si, kb_rv_cmd
    call mc_row
    test byte [kb_ck+KBC_OK], KBF_CMD
    jnz .cm
    mov si, kb_s_noans
    call mc_put
    mov al, LP_BAD
    call kb_worse
    jmp short .op
.cm:
    mov al, [kb_ck+KBC_CMD]
    and al, 0xEF                    ; bit 4 is our own 0xAD's: not shown
    call kb_cmdw
    test byte [kb_ck+KBC_CMD], 0x01
    jnz .c1
    mov al, LP_BAD
    call kb_worse
    mov si, kb_l_noirq
    call mc_line
.c1:
    cmp byte [mc_kok], 0
    je .op
    cmp word [p2_sp], 0
    je .op
    mov al, [kb_ck+KBC_CMD]
    and al, 0xEF                    ; bit 4 is 0xAD's own
    xor al, [kb_bcmd]
    jz .same
    mov [kb_x], al
    mov si, kb_rv_chg               ; WHICH bits moved since the boot read it
    call mc_row
    call mc_hex8
    test byte [kb_x], 0x41          ; IRQ1 or translation: the KEYBOARD's
    jnz .kchg
    mov si, kb_s_auxchg             ; bits 1 and 5 are the aux port's, and a
    call mc_put                     ; live PS/2 mouse moves both by design
    jmp short .op
.kchg:
    mov si, kb_s_kchg
    call mc_put
    mov al, LP_BAD
    call kb_worse
    jmp short .op
.same:
    mov si, kb_l_same
    call mc_line
.op:
    mov si, kb_rv_out
    call mc_row
    test byte [kb_ck+KBC_OK], KBF_OUT
    jnz .o1
    mov si, kb_s_noans
    call mc_put
    jmp short .ab
.o1:
    mov al, [kb_ck+KBC_OUT]
    call mc_hex8
    mov al, ' '
    call mc_putc
    mov al, [kb_ck+KBC_OUT]
    mov si, kb_b_out
    call mc_bits
.ab:
    mov si, kb_rv_ab
    call mc_row
    test byte [kb_ck+KBC_OK], KBF_AB
    jnz .a1
    mov si, kb_s_noans
    call mc_put
    jmp short .ec
.a1:
    mov al, [kb_ck+KBC_AB]
    call mc_hex8
    cmp al, 4
    jbe .a2
    mov al, 5                       ; any other answer
.a2:
    xor ah, ah
    mov bx, ax
    shl bx, 1
    mov si, [kb_abtab+bx]
    call mc_put
    cmp byte [kb_ck+KBC_AB], 0
    je .ec
    mov al, LP_BAD
    call kb_worse
.ec:
    mov si, kb_rv_echo
    call mc_row
    test byte [kb_ck+KBC_OK], KBF_ECHO
    jnz .e1
    mov si, kb_s_noecho
    call mc_put
    mov al, LP_BAD
    call kb_worse
    jmp short .wd
.e1:
    mov al, [kb_ck+KBC_EB]
    call mc_hex8
    mov si, kb_s_eok
    cmp al, 0xEE
    je .e2
    mov si, kb_s_eodd
    test byte [kb_ck+KBC_ES], 0x20
    jz .e2
    mov si, kb_s_eaux
.e2:
    call mc_put
    cmp byte [kb_ck+KBC_EB], 0xEE
    je .wd
    mov al, LP_WARN
    call kb_worse
.wd:
    test byte [kb_ck+KBC_OK], KBF_WEDGE
    jz .ca
    mov al, LP_BAD
    call kb_worse
    mov si, kb_l_wedge
    call mc_line
.ca:
    mov si, kb_rv_cka
    call mc_row
    mov al, [kb_ck+KBC_S1]
    call kb_st

    ; --- the verdict -------------------------------------------------------
.verdict:
    cmp word [kb_bios], 0
    jne .some
    mov si, kb_l_none
    call mc_line
    mov al, LP_WARN
    call kb_worse
    jmp short .vd
.some:
    mov si, kb_l_some
    call mc_line
.vd:
    mov al, [kb_lp]
    jmp mc_lamp

; kb_worse - AL = a lamp; [kb_lp] takes it when it is worse. Keeps all
kb_worse:
    push ax
    cmp al, [kb_lp]                 ; OK < WARN < BAD: the only lamps
    jbe .k                          ; this section raises
    mov [kb_lp], al
.k:
    pop ax
    ret

; kb_vec - ES = the low window, BX = a vector's offset in it, SI = the label:
;          a row "SSSS:OOOO whose". out AL = 1 it points into the kernel
kb_vec:
    call mc_row
    mov ax, [es:bx+2]
    mov dx, [es:bx]
    push ax
    call p2_farp
    pop bx
    mov si, p2_vcls                 ; whose it is, by its segment (ps2.inc)
.vc:
    lodsw
    cmp bx, ax
    lodsw
    jb .vc
    xchg ax, si
    call mc_put
    xor al, al
    cmp bx, P2_KSEG
    jne .r
    inc al
.r:
    ret

; kb_st - AL = a 64h status: hex, then its bits by name
kb_st:
    push ax
    call mc_hex8
    mov al, ' '
    call mc_putc
    pop ax
    mov si, kb_b_st
    jmp mc_bits

; kb_cmdw - AL = a command byte: hex, then what the keyboard half of it says
kb_cmdw:
    push ax
    call mc_hex8
    pop ax
    push ax
    mov si, kb_s_irq1on
    test al, 0x01
    jnz .i
    mov si, kb_s_irq1off
.i:
    call mc_put
    pop ax
    push ax
    mov si, kb_s_xon
    test al, 0x40
    jnz .x
    mov si, kb_s_xoff
.x:
    call mc_put
    pop ax
    test al, 0x10
    jz .r
    mov si, kb_s_kdis
    call mc_put
.r:
    ret

; --- data ----------------------------------------------------------------------
KBC_OK      equ 0               ; KBF_* below
KBC_S0      equ 1               ; 64h before
KBC_WS      equ 2               ; a byte already waiting: 64h with it
KBC_WB      equ 3               ; ...and the byte
KBC_CMD     equ 4               ; the command byte now
KBC_OUT     equ 5               ; the output port
KBC_AB      equ 6               ; the interface test's answer
KBC_ES      equ 7               ; the echo: 64h with it
KBC_EB      equ 8               ; ...and the byte
KBC_S1      equ 9               ; 64h after
KBC_N       equ 10

KBF_RAN     equ 0x01
KBF_WAIT    equ 0x02
KBF_CMD     equ 0x04
KBF_OUT     equ 0x08
KBF_AB      equ 0x10
KBF_ECHO    equ 0x20
KBF_WEDGE   equ 0x40

kb_s_head:  db 'Keyboard', 0
kb_rv_bios: db 'Keys the BIOS stored', 0
kb_s_shift: db ' (shift-key changes ', 0
kb_rv_mine: db 'Keys reaching here', 0
kb_rv_after: db 'After the check', 0
kb_s_bios:  db ' stored, ', 0
kb_s_here:  db ' reached here', 0
kb_rv_buf:  db 'BIOS buffer', 0
kb_rv_flag: db 'Shift flags 17/18', 0
kb_b_flag:  db 'ICNSACLR'                ; Ins Caps Num Scroll Alt Ctrl LSh RSh
kb_rv_flag2: db 'KB flag 2 (97)', 0
kb_b_flag2: db 'EURA.CNS'                ; Error, Update, Resend, Ack, -, LEDs
kb_rv_flag3: db 'KB flag 3 (96)', 0
kb_s_101:   db ' a 101-key keyboard', 0
kb_s_84:    db ' no 101-key keyboard seen', 0
kb_rv_v09:  db 'int 09h', 0
kb_rv_v15:  db 'int 15h', 0
kb_rv_v16:  db 'int 16h', 0
kb_rv_hook: db "Kernel's key hook", 0
kb_s_h15:   db 'int 15h AH=4Fh (the ROM reads 60h)', 0
kb_s_h09:   db 'int 09h (peeks 60h, then the ROM)', 0
kb_s_hnone: db 'none found in the vectors', 0
kb_l_txerr: db 'The BIOS flags a keyboard TRANSMIT ERROR (40:97 bit 7).', 0
kb_rv_irq1: db 'IRQ 1', 0
kb_s_req:   db '- requested in ', 0
kb_s_samp:  db ' looks', 0
kb_l_masked: db 'IRQ 1 is MASKED: no keystroke can be delivered.', 0
kb_l_xt:    db 'An XT keyboard (8255): no controller to check.', 0
kb_rv_64:   db 'Port 64h now', 0
kb_b_st:    db 'PTAKcsIO'                ; Parity Timeout Aux Kbd-free cmd sys IBF OBF
kb_rv_obf:  db 'Byte left waiting', 0
kb_s_obf:   db ' looks in a row (most)', 0
kb_s_oaux:  db ', AUX seen', 0
kb_l_stuck: db 'A byte sat unread in the 8042 across looks, and the', 0
kb_l_stuck2: db 'keyboard is BLOCKED behind it: IRQ 1 is not taken.', 0
kb_l_stuck3: db 'keyboard is BLOCKED behind an AUX byte (SPEC 9.9.1.1).', 0
kb_rv_bcmd: db 'Command byte at boot', 0
kb_s_nread: db 'never read', 0
kb_rv_reset: db 'Boot sent D4 FF', 0
kb_s_rsno:  db 'no: the PS/2 probe stopped before it', 0
kb_s_rsyes: db 'yes, and a device answered', 0
kb_s_rsfail: db 'yes, and nothing answered it', 0
kb_rv_bm1:  db 'IRQ 1 at boot probe', 0
kb_l_nock:  db 'K runs the controller check (keyboard off ~0.3 s).', 0
kb_rv_ckb:  db 'Check: 64h before', 0
kb_rv_wait: db 'Byte already waiting', 0
kb_s_wkbd:  db " (keyboard's, never delivered)", 0
kb_s_waux:  db " (the aux port's)", 0
kb_rv_cmd:  db 'Command byte now', 0
kb_s_noans: db 'no answer', 0
kb_l_noirq: db 'IRQ 1 is OFF in the 8042 command byte.', 0
kb_rv_chg:  db 'Changed since boot', 0
kb_s_auxchg: db ' (aux-port bits only)', 0
kb_s_kchg:  db ' - IRQ1/xlate, the KEYBOARD', 0
kb_l_same:  db 'The same as at boot (bit 4 aside).', 0
kb_rv_out:  db 'Output port (D0)', 0
kb_b_out:   db 'DCUKcdAR'                ; kbd Data, kbd Clock, aUx irq, Kbd irq, aux c d, A20, Reset
kb_rv_ab:   db 'Interface test (AB)', 0
kb_abtab:   dw kb_s_ab0, kb_s_ab1, kb_s_ab2, kb_s_ab3, kb_s_ab4, kb_s_abx
kb_s_ab0:   db ' lines OK', 0
kb_s_ab1:   db ' CLOCK stuck low', 0
kb_s_ab2:   db ' CLOCK stuck high', 0
kb_s_ab3:   db ' DATA stuck low', 0
kb_s_ab4:   db ' DATA stuck high', 0
kb_s_abx:   db ' (not a defined answer)', 0
kb_rv_echo: db 'Keyboard echo (EE)', 0
kb_s_noecho: db 'NO ANSWER: keyboard unreachable', 0
kb_s_eok:   db ' the keyboard answered', 0
kb_s_eodd:  db ' (not EE: a key, or confused)', 0
kb_s_eaux:  db ' (from the AUX side!)', 0
kb_l_wedge: db 'The 8042 stopped taking writes during the check.', 0
kb_rv_cka:  db 'Check: 64h after', 0
kb_l_none:  db 'No keystroke has reached the BIOS since this started.', 0
kb_l_some:  db 'Keystrokes reach the BIOS.', 0
kb_s_irq1on:  db ' IRQ1 on', 0
kb_s_irq1off: db ' IRQ1 OFF', 0
kb_s_xon:   db ', xlate on', 0
kb_s_xoff:  db ', xlate OFF', 0
kb_s_kdis:  db ', kbd DISABLED', 0

; --- loader-zeroed bss --------------------------------------------------------
    OS88_ABYTE kb_lowok
    OS88_ABYTE kb_obfn              ; looks in a row with a keyboard byte waiting
    OS88_ABYTE kb_obfmax            ; ...the most
    OS88_ABYTE kb_obfaux            ; 20h: one of them was the AUX side's
    OS88_ABYTE kb_s64               ; 64h at the last look
    OS88_ABYTE kb_imr               ; the master's mask at the last look
    OS88_ABYTE kb_irr               ; ...and its request register
    OS88_ABYTE kb_flag0             ; 40:17 at the last look
    OS88_ABYTE kb_chkd              ; the controller check has run
    OS88_ABYTE kb_m1                ; the masks the check found
    OS88_ABYTE kb_m2
    OS88_ABYTE kb_lp                ; the section's lamp, built up
    OS88_ABYTE kb_f2                ; 40:97 this rebuild
    OS88_ABYTE kb_v9k               ; int 09h / 15h point into the kernel
    OS88_ABYTE kb_v15k
    OS88_ABYTE kb_bcmd              ; the boot's command byte
    OS88_ABYTE kb_x                 ; the bits that moved since it
    OS88_AWORD kb_lowsel
    OS88_AWORD kb_tail0             ; 40:1C at the last look
    OS88_AWORD kb_bios              ; keys the ROM stored since open
    OS88_AWORD kb_biosx             ; ...since the check
    OS88_AWORD kb_mods              ; shift-state changes
    OS88_AWORD kb_mine              ; keys our window received
    OS88_AWORD kb_minex             ; ...since the check
    OS88_AWORD kb_irrn              ; looks with IRQ 1 requested
    OS88_AWORD kb_nsamp             ; looks
    OS88_AWORD kb_ckt               ; the check's tick stamp
    OS88_ABUF  kb_ck, KBC_N
