; =============================================================================
; os8088 - tests/pm2dma/pm2dma.asm
;
; PM2DMA: CAN A PICOMEM 2 BE THE DEVICE IN A DMA WRITE TRANSFER?
; (docs/plans/PICOMEM2-DMA-DISK-PLAN.md, wave 0 - the go / no-go.)
;
; A disk read by DMA is the 8237's WRITE transfer: AEN up, IOR to the device
; holding DACK, MEMW to memory at the address the 8237 counts. The 2.0's only
; DMA acknowledge input is DACK-and-IOW (the Sound Blaster's direction), and
; its firmware never reads AEN - which suggests the board gates the ordinary
; I/O strobes with AEN, and then the card sees only the transfer's MEMW. This
; asks the board. It needs the PROBE firmware, Elendilon/ISA-PicoMEM branch
; pm2-dma built -DPM2DMA_PROBE=1, which adds commands B0h-B4h (pm2dma_probe.h).
;
; For each run the package programs the jumpered channel (1, or 3 with the
; key 3) for a single-mode write transfer of 512 bytes into a buffer of its
; own, filled with EEh, arms the card, unmasks the channel with interrupts
; off, and polls the 8237's status for the channel's terminal count. Then it
; reads the card's counters and compares the buffer with the card's pattern.
;
;   mode 0  the card drives nothing: which strobes did it SEE, at what address?
;   mode 1  the card drives its byte on the transfer's MEMW (x3)
;   mode 2  the card drives its byte as an I/O read, on MEMW+IOR or IOR (x3)
;
; PASS is mode 1 or mode 2 with 512 bytes right, three runs running. The
; Sound Blaster must be quiet (nothing playing): it shares the DRQ line.
;
;   ...open PM2DMA.O88 and click the window or press R (channel 1), or press
;   3 (channel 3, the jumper on 3). The report is saved beside the package
;   as PM2DMA1.TXT, PM2DMA2.TXT... - bring them back.
;
; `make pm2dma` puts it alone on a 1.44MB and a 360KB disk. Refused on
; kern_mega: segments are selectors there and this computes a linear address.
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'PM2DMA', p2_entry

P2_PORT     equ 0x2A0               ; the card's command port (2A0h-2A3h)
P2_LEN      equ 512                 ; bytes a run
P2_POLLS    equ 20000               ; status polls before giving up (~100 ms)
P2_FILL     equ 0xEE                ; the buffer before a run

CMD_TESTRAM equ 0x0B                ; the card's CMD_Test_RAM: swaps a byte
CMD_P2D_ADDR  equ 0xB0
CMD_P2D_SETUP equ 0xB1
CMD_P2D_GO    equ 0xB2
CMD_P2D_STOP  equ 0xB3
CMD_P2D_STAT  equ 0xB4

p2_entry:
    push si
    call bl_blank
    mov si, p2_s_title
    call bl_sline
    mov si, p2_s_hint
    call bl_sline
    mov si, p2_s_hint2
    call bl_sline
    mov si, p2_tpl
    call OSAPI_WM_CREATE
    jc .out
    mov [p2_win], bx
    mov al, 1
    call OSAPI_WM_SNAP
    clc
.out:
    pop si
    ret

p2_paint:
    call bl_paint
    ret

p2_onkey:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov [p2_win], si
    mov bl, al
    or bl, 0x20
    mov byte [p2_ch], 1
    cmp bl, 'r'
    je .run
    cmp al, '1'
    je .run
    mov byte [p2_ch], 3
    cmp al, '3'
    je .run
    call bl_key
    jc .out
    call bl_paint
    jmp short .out
.run:
    call p2_run
    call bl_paint
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

p2_onclick:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov [p2_win], si
    mov byte [p2_ch], 1
    call p2_run
    call bl_paint
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; p2_cmd - one card command. AL = the command, BX = its two data bytes.
; out: CF=0, BX = the data bytes the card left; CF=1, AL = the status it
;      stopped at (FFh = it never went ready). Preserves CX, DX, SI, DI.
; -----------------------------------------------------------------------------
p2_cmd:
    push cx
    push dx
    mov ah, al
    mov dx, P2_PORT
    mov cx, 0xFFFF
.ready:
    in al, dx
    or al, al
    jz .send
    loop .ready
    mov al, 0xFF
    stc
    jmp short .out
.send:
    inc dx
    mov al, bl
    out dx, al                      ; 2A1h: data low
    inc dx
    mov al, bh
    out dx, al                      ; 2A2h: data high
    sub dx, 2
    mov al, ah
    out dx, al                      ; 2A0h: the command
    mov cx, 0xFFFF
.wait:
    in al, dx
    cmp al, 1                       ; STAT_CMDINPROGRESS
    jne .ended
    loop .wait
    mov al, 0xFF
    stc
    jmp short .out
.ended:
    or al, al                       ; STAT_READY
    jz .ok
    stc
    jmp short .out
.ok:
    inc dx
    in al, dx
    mov bl, al
    inc dx
    in al, dx
    mov bh, al
    clc
.out:
    pop dx
    pop cx
    ret

; p2_stat - AL = counter index -> AX = the card's counter (FFFFh on failure)
p2_stat:
    push bx
    xor bh, bh
    mov bl, al
    mov al, CMD_P2D_STAT
    call p2_cmd
    mov ax, bx
    jnc .out
    mov ax, 0xFFFF
.out:
    pop bx
    ret

; p2_alive - CF=0 when the card answers commands at 2A0h. CMD_Test_RAM
; swaps a byte, so two calls must hand back the first one's value. A port
; locked by CMD_LockPort is unlocked (37h then 94h) and asked again.
p2_alive:
    push ax
    push bx
    push cx
    push dx
    mov cx, 2
.try:
    mov bx, 0x005A
    mov al, CMD_TESTRAM
    call p2_cmd
    jc .unlock
    mov bx, 0x00A5
    mov al, CMD_TESTRAM
    call p2_cmd
    jc .unlock
    cmp bl, 0x5A
    je .yes
.unlock:
    mov dx, P2_PORT
    mov al, 0x37
    out dx, al
    mov al, 0x94
    out dx, al
    loop .try
    stc
    jmp short .out
.yes:
    clc
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; p2_run - the whole report, on channel [p2_ch]
; -----------------------------------------------------------------------------
p2_run:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov word [bl_nrow], 0
    mov si, p2_s_title
    call bl_sline
    call OSAPI_CPU_INFO
    test ah, CPU_F_PM
    jz .real
    mov si, p2_s_mega
    call bl_sline
    jmp .save
.real:
    xor ah, ah
    xor dx, dx
    mov cx, 5
    mov si, p2_s_tier
    call bl_kv
    mov al, [p2_ch]
    xor ah, ah
    mov cx, 5
    mov si, p2_s_chan
    call bl_kv
    ; the card, and the probe in it
    call p2_alive
    jnc .alive
    mov si, p2_s_nocard
    call bl_sline
    jmp .save
.alive:
    mov al, 39                      ; P2D_VERSION
    call p2_stat
    cmp ax, 1
    je .probe
    mov si, p2_s_noprobe
    xor dx, dx
    mov cx, 5
    call bl_kv
    mov dx, P2_PORT                 ; an unknown command leaves the status at
    xor al, al                      ; "not found", which blocks the card BIOS's
    out dx, al                      ; next command: command 0 clears it
    jmp .save
.probe:
    call p2_place
    mov ax, [p2_lin]
    mov dx, [p2_lin + 2]
    mov cx, 8
    mov si, p2_s_lin
    call bl_kv
    ; mode 0 once, then modes 1 and 2 three times each
    mov byte [p2_mode], 0
    mov byte [p2_rep], 1
    call p2_once
    mov byte [p2_mode], 1
    mov cx, 3
.m1:
    mov al, 4
    sub al, cl
    mov [p2_rep], al
    call p2_once
    loop .m1
    mov byte [p2_mode], 2
    mov cx, 3
.m2:
    mov al, 4
    sub al, cl
    mov [p2_rep], al
    call p2_once
    loop .m2
.save:
    call bl_blank
    mov si, p2_f_txt
    call bl_save
    inc word [p2_done]
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; p2_place - [p2_buf] = a 512-byte span of p2_area that no 64KB page
; boundary crosses (a transfer's page register cannot carry), [p2_lin] its
; linear address
p2_place:
    push ax
    push bx
    push cx
    push dx
    mov bx, p2_area
.again:
    mov ax, ds
    mov dx, ax
    mov cl, 4
    shl ax, cl
    mov cl, 12
    shr dx, cl
    add ax, bx
    adc dx, 0                       ; DX:AX = the span's linear address
    mov cx, ax
    add cx, P2_LEN - 1
    jnc .fits                       ; no carry out of the low word: one page
    add bx, P2_LEN
    jmp short .again
.fits:
    mov [p2_buf], bx
    mov [p2_lin], ax
    mov [p2_lin + 2], dx
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; p2_once - one transfer on [p2_ch] in [p2_mode], and its lines
; -----------------------------------------------------------------------------
p2_once:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    ; the heading: "-- channel C, mode M, run R --"
    mov al, [p2_ch]
    add al, '0'
    mov [p2_s_run_c], al
    mov al, [p2_mode]
    add al, '0'
    mov [p2_s_run_m], al
    mov al, [p2_rep]
    add al, '0'
    mov [p2_s_run_r], al
    call bl_blank
    mov si, p2_s_run
    call bl_sline
    ; the buffer, EEh throughout
    push ds
    pop es
    cld
    mov di, [p2_buf]
    mov cx, P2_LEN
    mov al, P2_FILL
    rep stosb
    ; the 8237: masked, single / increment / write transfer, the buffer, 511
    mov bl, [p2_ch]
    xor bh, bh
    pushf
    cli
    mov al, bl
    or al, 4
    out 0x0A, al                    ; mask the channel
    mov al, 0x44
    or al, bl
    out 0x0B, al                    ; mode 44h + channel
    out 0x0C, al                    ; clear the flip-flop
    mov dx, bx
    shl dx, 1                       ; DX = the address port, 2 x channel
    mov ax, [p2_lin]
    out dx, al
    mov al, ah
    out dx, al
    inc dx                          ; the count port
    mov ax, P2_LEN - 1
    out dx, al
    mov al, ah
    out dx, al
    mov al, [p2_lin + 2]
    mov dx, 0x83                    ; channel 1's page register
    cmp bl, 1
    je .page
    mov dx, 0x82                    ; channel 3's
.page:
    out dx, al
    popf
    ; the card: where, how, and go (it raises DRQ; the channel is masked)
    mov bx, [p2_lin]
    mov al, CMD_P2D_ADDR
    call p2_cmd
    jc .cmdfail
    mov bl, [p2_lin + 2]
    mov bh, [p2_ch]
    mov cl, 4
    shl bh, cl
    or bh, [p2_mode]
    mov al, CMD_P2D_SETUP
    call p2_cmd
    jc .cmdfail
    mov bx, P2_LEN
    mov al, CMD_P2D_GO
    call p2_cmd
    jc .cmdfail
    ; unmask, interrupts off, and wait for the channel's terminal count
    mov bl, [p2_ch]
    mov ah, 1
    mov cl, bl
    shl ah, cl                      ; AH = the channel's TC bit
    xor si, si                      ; SI = polls
    pushf
    cli
    mov al, bl
    out 0x0A, al                    ; unmask: the transfer runs
    mov cx, P2_POLLS
.poll:
    inc si
    in al, 0x08
    test al, ah
    jnz .tc
    loop .poll
    xor si, si                      ; no terminal count: 0 polls reported
.tc:
    mov al, bl
    or al, 4
    out 0x0A, al                    ; mask it again
    popf
    mov bx, 0
    mov al, CMD_P2D_STOP
    call p2_cmd
    mov ax, si
    xor dx, dx
    mov cx, 6
    mov si, p2_s_tc
    call bl_kv
    call p2_check
    call p2_counters
    jmp short .out
.cmdfail:
    xor ah, ah
    xor dx, dx
    mov cx, 5
    mov si, p2_s_cmdfail
    call bl_kv
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; p2_check - the buffer against the card's pattern: right, still EEh, FFh,
; and the first wrong byte
p2_check:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov si, [p2_buf]
    xor bx, bx                      ; BX = i
    xor di, di                      ; DI = right
    mov word [p2_nee], 0
    mov word [p2_nff], 0
    mov word [p2_bad], 0xFFFF
.b:
    mov ax, bx
    mov cx, 7
    mul cx
    add al, 0x13
    xor al, bh                      ; AL = (i x 7 + 13h) ^ (i >> 8)
    mov ah, [si + bx]
    cmp ah, P2_FILL                 ; what the byte IS, counted over every
    jne .ff                         ; byte: the pattern itself is EEh and FFh
    inc word [p2_nee]               ; at a few places
.ff:
    cmp ah, 0xFF
    jne .cmp
    inc word [p2_nff]
.cmp:
    cmp ah, al
    jne .wrong
    inc di
    jmp short .next
.wrong:
    cmp word [p2_bad], 0xFFFF
    jne .next
    mov [p2_bad], bx
    mov [p2_got], ah
    mov [p2_want], al
.next:
    inc bx
    cmp bx, P2_LEN
    jb .b
    xor dx, dx
    mov cx, 6
    mov ax, di
    mov si, p2_s_right
    call bl_kv
    mov ax, [p2_nee]
    mov si, p2_s_nee
    call bl_kv
    mov ax, [p2_nff]
    mov si, p2_s_nff
    call bl_kv
    mov ax, [p2_bad]
    mov si, p2_s_bad
    call bl_kv
    cmp ax, 0xFFFF
    je .out
    mov al, [p2_got]
    xor ah, ah
    mov si, p2_s_got
    call bl_kv
    mov al, [p2_want]
    mov si, p2_s_want
    call bl_kv
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; p2_counters - the card's own account of the run (pm2dma_probe.h's indices)
p2_counters:
    push ax
    push bx
    push cx
    push dx
    push si
    mov bx, p2_ctab
.c:
    mov si, [bx]
    or si, si
    jz .out
    mov al, [bx + 2]
    call p2_stat
    xor dx, dx
    mov cx, 6
    call bl_kv
    add bx, 3
    jmp short .c
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

%define BL_ARENA_BYTES 9000
%define BL_NUMBERED                 ; a field run saves NAME1, NAME2... (benchlib)
%define BL_INTRO_HOW 'automatically, when the run ends' ; benchlib's banner
%include "benchlib.inc"

p2_tpl:
    dw 7, 22, 632, 300
    dw p2_ttl, p2_paint, p2_onkey, p2_onclick

; the counters a run reports: label, then the card's index
p2_ctab:
    dw p2_c_served
    db 0
    dw p2_c_mwin
    db 1
    dw p2_c_mwodd
    db 2
    dw p2_c_n6in
    db 3
    dw p2_c_iorin
    db 4
    dw p2_c_first
    db 5
    dw p2_c_firsth
    db 6
    dw p2_c_last
    db 7
    dw p2_c_lasth
    db 8
    dw p2_c_done
    db 32
    dw p2_c_nib1
    db 17
    dw p2_c_nib2
    db 18
    dw p2_c_nib4
    db 20
    dw p2_c_nib6
    db 22
    dw p2_c_nib8
    db 24
    dw p2_c_nib9
    db 25
    dw p2_c_snpa
    db 33
    dw p2_c_snpp
    db 34
    dw p2_c_snpc
    db 35
    dw p2_c_snpm
    db 36
    dw 0

p2_ttl:       db 'PicoMEM 2 DMA probe', 0
p2_f_txt:     db 'PM2DMA.TXT', 0
p2_s_title:   db 'PM2DMA - can a PicoMEM 2 be the device in a DMA write?', 0
p2_s_hint:    db 'Click or R: channel 1. Key 3: channel 3. Needs the', 0
p2_s_hint2:   db 'pm2-dma PROBE firmware, and the Sound Blaster quiet.', 0
p2_s_mega:    db 'kern_mega: refused (a linear address from a selector)', 0
p2_s_nocard:  db 'NO PICOMEM answering commands at 2A0h', 0
p2_s_noprobe: db 'NOT the probe firmware', 0
p2_s_tier:    db 'CPU tier', 0
p2_s_chan:    db 'channel', 0
p2_s_lin:     db 'buffer linear address', 0
p2_s_run:     db '-- channel '
p2_s_run_c:   db '1, mode '
p2_s_run_m:   db '0, run '
p2_s_run_r:   db '1 --', 0
p2_s_cmdfail: db 'COMMAND FAILED, status', 0
p2_s_tc:      db 'TC after polls (0=none)', 0
p2_s_right:   db 'bytes right of 512', 0
p2_s_nee:     db 'bytes still EEh', 0
p2_s_nff:     db 'bytes FFh', 0
p2_s_bad:     db 'first wrong (65535=none)', 0
p2_s_got:     db '...got', 0
p2_s_want:    db '...wanted', 0
p2_c_served:  db 'card: driven', 0
p2_c_mwin:    db 'card: MEMW in buffer', 0
p2_c_mwodd:   db 'card: ...off sequence', 0
p2_c_n6in:    db 'card: MEMW+IOR in buffer', 0
p2_c_iorin:   db 'card: IOR in buffer', 0
p2_c_first:   db 'card: first addr low', 0
p2_c_firsth:  db 'card: first hi+nib<<8', 0
p2_c_last:    db 'card: last addr low', 0
p2_c_lasth:   db 'card: last hi+nib<<8', 0
p2_c_done:    db 'card: count ran out', 0
p2_c_nib1:    db 'card: cycles MEMR', 0
p2_c_nib2:    db 'card: cycles MEMW', 0
p2_c_nib4:    db 'card: cycles IOR', 0
p2_c_nib6:    db 'card: cycles MEMW+IOR', 0
p2_c_nib8:    db 'card: cycles IOW', 0
p2_c_nib9:    db 'card: cycles MEMR+IOW', 0
p2_c_snpa:    db 'card saw: base address', 0
p2_c_snpp:    db 'card saw: page', 0
p2_c_snpc:    db 'card saw: base count', 0
p2_c_snpm:    db 'card saw: autoinit|mask', 0

p2_win:       dw 0
p2_ch:        db 1
p2_mode:      db 0
p2_rep:       db 1
p2_buf:       dw 0
p2_lin:       dw 0, 0
p2_nee:       dw 0
p2_nff:       dw 0
p2_bad:       dw 0
p2_got:       db 0
p2_want:      db 0
p2_done:      dw 0                  ; runs completed

P2_BSS_OWN  equ 2 * P2_LEN          ; p2_area: room to step past a page edge
    OS88_BSS P2_BSS_OWN + BL_BSS_SIZE
    OS88_IMAGE_END

p2_area     equ os88_image_end + 0

    BL_BSS os88_image_end + P2_BSS_OWN
