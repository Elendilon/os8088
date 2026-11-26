; =============================================================================
; os8088 - apps/snddiag/sdlab.inc - the DMA LAB, pages 4 and 5, and the report
; file (SPEC.md 127.4.1 - 127.4.3)
;
; THE LAB. The play test asks the driver's stream to play and watches; the lab
; asks the debug driver (SNDV_DIAG's SDGF_LAB) to drive the DSP and DMA channel
; 1 ITSELF, one variant at a time, and samples the 8237 every tick while each
; plays: the register shape (the driver's own, Creative's, slowed), the DMA
; cycle (4, 8, 16KB), the DSP block (2, 8, 16KB), the 8237 mode (single,
; demand, no auto-init), the DSP start (1Ch, 90h, 14h re-armed per block), the
; rate, the buffer's place in memory, and whether the 8237 is read at all.
; Each run is SL_TICKS ticks (~2.4 s, three passes of a 16KB ring at
; 22,050 Hz), so a stall at the first wrap is caught by every run that has
; one. A run that cannot apply here (no auto-init, no high-speed, no ESS) is
; skipped and says so.
;
; THE REPORT is benchlib's (tests/benchlib.inc), the standard every bench and
; REDLINE use: a TEXT FILE, numbered so no run overwrites another. Started
; from a link whose parameter is AUTO (the debug disk's \AUTOSTRT\SNDDIAG.LNK)
; the program saves SOUNDAn.TXT after the play test and SOUNDBn.TXT after
; the lab - two files on the input debug disk's precedent (SPEC.md 136.12): a
; machine that hangs in the lab still leaves the A file. S saves SOUNDSn.TXT
; at any time. Each holds every page as text and the raw samples behind them.
;
; Label prefix sl_ (sd_ for what the pages share).
; =============================================================================

SL_TICKS    equ 44              ; a run: ~2.4 s
SL_GAP      equ 5               ; ticks of quiet between runs
SL_QEVERY   equ 4               ; LF_QUIET: the 8237 is read one tick in 4
                                ; (8 would let 22kHz x2 lap a 16KB cycle)
SL_SAMPW    equ 4               ; a sample: dw channel 1's address, db its
                                ;   status (TC 0-3, DREQ 4-7), db 0EEh = the
                                ;   8237 was not read this tick (LF_QUIET)
SL_RECW     equ SDL_LOG + 12 * SDL_LOGW ; a run's driver record as kept: the
                                ; head and the first 12 block IRQs
SL_RESW     equ 16              ; a run's result
SLR_STAT    equ 0               ; db SLS_*
SLR_ERR     equ 1               ; db SDGF_LAB's refusal
SLR_NS      equ 2               ; db samples taken
SLR_TC      equ 3               ; db 8237 status bits OR'd (TC 0-3, DREQ 4-7)
SLR_MOVED   equ 4               ; dd bytes the 8237 moved, summed per tick
SLR_STALL   equ 8               ; db the sample the address froze at, 0FFh none
SLR_DTMO    equ 9               ; db DSP writes timed out
SLR_SPOS    equ 10              ; dw where in the cycle it froze (bytes in)
SLR_IRQ     equ 12              ; dw block IRQs
SLR_SADDR   equ 14              ; dw ...and the 8237 address it froze at
SLS_NONE    equ 0
SLS_RAN     equ 1
SLS_SKIP    equ 2
SLS_FAIL    equ 3
SLS_RUN     equ 4

; --- the runs -------------------------------------------------------------------
; one row: dw name, dw cycle bytes (0 = 16384), dw block bytes, dw rate,
; db 8237 mode, db DSP start, db TC, db LF_*, db buffer (0 low, 1 high),
; db needs (SLN_*)
SL_ROW      equ 16
SLT_BUF     equ 12              ; (the row's two bytes past the flags)
SLT_NEED    equ 13
SLN_AUTO    equ 1               ; auto-init DSP (>= 2.00)
SLN_HISP    equ 2               ; high-speed (DSP >= 3)
SLN_ESS     equ 4               ; an ESS chip
%macro SLRUN 10
    dw %1, %2, %3, %4
    db %5, %6, %7, %8, %9, %10
    dw 0
%endmacro
sl_tab:
    SLRUN sl_n1,  0,    2048,  22050, 0x59, 0x1C, 0xD3, 0, 0, SLN_AUTO
    SLRUN sl_n2,  0,    2048,  22050, 0x59, 0x1C, 0xD3, 0, 1, SLN_AUTO
    SLRUN sl_n3,  0,    2048,  22050, 0x59, 0x1C, 0xD3, LF_SDK, 0, SLN_AUTO
    SLRUN sl_n4,  0,    2048,  22050, 0x59, 0x1C, 0xD3, LF_SDK|LF_SLOW|LF_DMA1ST, 0, SLN_AUTO
    SLRUN sl_n5,  4096, 2048,  22050, 0x59, 0x1C, 0xD3, 0, 0, SLN_AUTO
    SLRUN sl_n6,  8192, 2048,  22050, 0x59, 0x1C, 0xD3, 0, 0, SLN_AUTO
    SLRUN sl_n7,  0,    8192,  22050, 0x59, 0x1C, 0xD3, 0, 0, SLN_AUTO
    SLRUN sl_n8,  0,    16384, 22050, 0x59, 0x1C, 0xD3, 0, 0, SLN_AUTO
    SLRUN sl_n9,  0,    2048,  22050, 0x19, 0x1C, 0xD3, 0, 0, SLN_AUTO
    SLRUN sl_n11, 0,    2048,  22050, 0x49, 0x14, 0xD3, LF_REARM, 0, 0
    SLRUN sl_n12, 0,    2048,  22050, 0x59, 0x90, 0xD3, 0, 0, SLN_HISP
    SLRUN sl_n13, 0,    2048,  11025, 0x59, 0x1C, 0xA5, 0, 0, SLN_AUTO
    SLRUN sl_n14, 0,    2048,  22050, 0x59, 0x1C, 0xD3, LF_QUIET, 0, SLN_AUTO
    SLRUN sl_n15, 0,    2048,  22050, 0x59, 0x1C, 0xD3, LF_NOACK, 0, SLN_AUTO
    SLRUN sl_n16, 0,    2048,  22050, 0x59, 0x1C, 0xD3, LF_ESSRD, 0, SLN_AUTO|SLN_ESS
    SLRUN sl_n10, 0,    2048,  22050, 0x49, 0x1C, 0xD3, 0, 0, SLN_AUTO ; LAST: it starves the card on purpose
sl_tab_end:
SL_N        equ (sl_tab_end - sl_tab) / SL_ROW
SL_P4       equ 13              ; runs on page 4; the rest on page 5
sl_n1:      db 'BASE', 0        ; the stream's regime, our own buffer
sl_n2:      db 'HIGHMEM', 0     ; ...in a buffer at the top of memory
sl_n3:      db 'SDKORDR', 0     ; 8237 in Creative's order
sl_n4:      db 'GAMEORD', 0     ; ...and slowed, and before the DSP
sl_n5:      db 'RING4K', 0      ; DMA cycle 4KB (two blocks)
sl_n6:      db 'RING8K', 0
sl_n7:      db 'BLK8K', 0       ; DSP block 8KB
sl_n8:      db 'BLK16K', 0      ; ...the whole cycle
sl_n9:      db 'DEMAND', 0      ; 8237 demand mode
sl_n10:     db 'NOAUTO', 0      ; 8237 not auto-init (expect a stop)
sl_n11:     db 'SINGLE', 0      ; 14h re-armed per block, no auto-init
sl_n12:     db 'HISPEED', 0     ; 90h
sl_n13:     db '11KHZ', 0
sl_n14:     db 'QUIET', 0       ; the 8237 barely read
sl_n15:     db 'NOACK', 0       ; no 2xEh ACK
sl_n16:     db 'ESSREGS', 0     ; BASE, ESS registers read at the stop

; --- the lab's state machine (from sd_ontimer) ------------------------------------
SL_PH_OFF   equ 0
SL_PH_RUN   equ 1
SL_PH_GAP   equ 2
SL_PH_DONE  equ 3

; sl_begin - the lab from run 1, on page 4. A refusal is a reason on the page
sl_begin:
    push ax
    push bx
    push cx
    push dx
    push di
    push ds
    pop es
    mov di, sl_res                  ; every result cleared
    mov cx, SL_N * SL_RESW
    xor al, al
    cld
    rep stosb
    mov byte [sd_page], 3
    mov byte [sd_auto], 1           ; (the first timer is ours now)
    mov byte [sl_why], 0
    mov byte [sl_run], 0
    cmp byte [sd_diag], 0
    mov al, 1
    je .no
    cmp byte [sd_rec+SDG_O_SBUP], 0
    mov al, 2
    je .no
    test byte [sd_cpu+1], CPU_F_PM
    mov al, 3
    jnz .no
    cmp byte [sd_pstate], SD_PS_RUN
    mov al, 5
    je .no
    call sl_bufs
    mov al, 4
    jc .no
    mov byte [sl_ph], SL_PH_RUN
    call sl_start
    jmp short .out
.no:
    mov [sl_why], al
    mov byte [sl_ph], SL_PH_DONE
    call sl_finish
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; sl_bufs - the two 16KB buffers, page-safe, filled with the tone. CF = 1 none
sl_bufs:
    cmp word [sl_buf], 0
    jne .have
    mov ax, 1024                    ; 16KB in paragraphs
    mov cx, ax                      ; ...all of it the DMA head
    mov bl, MEMP_CLAIM | MEMP_CPU | MEMP_CONV
    call OSAPI_MEM_P
    jc .r
    mov [sl_buf], dx
    mov ax, 1024
    mov cx, ax
    mov bl, MEMP_CLAIM_HI | MEMP_CPU | MEMP_CONV
    call OSAPI_MEM_P
    jnc .hi
    mov dx, [sl_buf]                ; no second: both runs use the first
.hi:
    mov [sl_buf+2], dx
    mov [sl_lbuf+2], dx
    mov dx, [sl_buf]
    mov [sl_lbuf], dx
.have:
    mov ax, 64                      ; ~345 Hz at 22,050
    call sd_tone
    push es
    push si
    push di
    xor bx, bx
.b:
    mov es, [sl_buf+bx]
    xor di, di
    mov dx, 16384 / SD_TONE
.f:
    mov si, sd_tonebuf
    mov cx, SD_TONE / 2
    cld
    rep movsw
    dec dx
    jnz .f
    add bx, 2
    cmp bx, 4
    jb .b
    pop di
    pop si
    pop es
    clc
.r:
    ret

; sl_free - the buffers back
sl_free:
    push dx
    mov dx, [sl_buf+2]
    cmp dx, [sl_buf]
    je .one
    or dx, dx
    jz .one
    call OSAPI_MEM_FREE
.one:
    mov dx, [sl_buf]
    or dx, dx
    jz .z
    call OSAPI_MEM_FREE
.z:
    mov word [sl_buf], 0
    mov word [sl_buf+2], 0
    pop dx
    ret

; sl_row - BX = the run's table row from AL = run index
sl_row:
    push ax
    xor ah, ah
    mov bl, SL_ROW
    mul bl
    add ax, sl_tab
    mov bx, ax
    pop ax
    ret

; sl_resp - SI = the run's result from AL = run index
sl_resp:
    push ax
    push cx
    xor ah, ah
    mov si, ax
    mov cl, 4
    shl si, cl
    add si, sl_res
    pop cx
    pop ax
    ret

; sl_len - AX = the run's DMA cycle in bytes (BX = its row)
sl_len:
    mov ax, [bx+2]
    or ax, ax
    jnz .r
    mov ax, 16384
.r:
    ret

; sl_start - start run [sl_run], skipping what this card cannot do; past the
; last, the lab is done
sl_start:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
.next:
    mov al, [sl_run]
    cmp al, SL_N
    jae .done
    call sl_row
    call sl_resp
    mov ah, [bx+SLT_NEED]                 ; needs
    test ah, SLN_AUTO               ; the DSP's version, not the driver's
    jz .na                          ; regime: on a machine whose 8237 cannot
    cmp byte [sd_rec+SDG_O_VERHI], 2    ; wrap the driver plays single-cycle
    jb .skip                        ; (SPEC.md 34.5.9), and the lab is how
                                    ; that is SEEN
.na:
    test ah, SLN_HISP
    jz .nh
    cmp byte [sd_rec+SDG_O_VERHI], 3
    jb .skip
.nh:
    test ah, SLN_ESS
    jz .go
    call sd_isess
    jc .skip
.go:
    ; the parameter block
    mov al, [bx+SLT_BUF]                 ; the buffer
    xor ah, ah
    shl ax, 1
    mov di, ax
    mov ax, [sl_buf+di]             ; its segment -> page : offset
    mov dx, ax
    mov cl, 4
    shl ax, cl
    mov [sl_lp+LP_OFF], ax
    mov cl, 12
    shr dx, cl
    mov [sl_lp+LP_PAGE], dl
    mov al, [bx+8]
    mov [sl_lp+LP_MODE], al
    call sl_len
    dec ax
    mov [sl_lp+LP_CNT], ax
    mov ax, [bx+4]
    dec ax
    mov [sl_lp+LP_BLK], ax
    mov al, [bx+10]
    mov [sl_lp+LP_TC], al
    mov al, [bx+9]
    mov [sl_lp+LP_CMD], al
    mov al, [bx+11]
    mov [sl_lp+LP_FLAGS], al
    mov byte [si+SLR_STAT], SLS_RUN
    mov byte [si+SLR_STALL], 0xFF
    push si
    push bx
    mov si, sl_lp
    mov al, SDGF_LAB
    mov bx, DRVC_SOUND * 256 + SNDV_DIAG
    call OSAPI_DRV_CALL
    pop bx
    pop si
    jc .fail
    mov [si+SLR_DTMO], al
    mov byte [sl_ph], SL_PH_RUN
    mov byte [sl_tk], 0
    jmp short .out
.fail:
    mov byte [si+SLR_STAT], SLS_FAIL
    mov [si+SLR_ERR], al
    mov byte [sl_ph], SL_PH_GAP
    mov byte [sl_tk], 0
    jmp short .out
.skip:
    mov byte [si+SLR_STAT], SLS_SKIP
    inc byte [sl_run]
    jmp .next
.done:
    mov byte [sl_ph], SL_PH_DONE
    call sl_finish
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; sl_tick - one tick of the lab
sl_tick:
    cmp byte [sl_ph], SL_PH_RUN
    je .run
    cmp byte [sl_ph], SL_PH_GAP
    jne .r
    inc byte [sl_tk]
    cmp byte [sl_tk], SL_GAP
    jb .r
    inc byte [sl_run]
    jmp sl_start
.run:
    call sl_sample
    inc byte [sl_tk]
    cmp byte [sl_tk], SL_TICKS
    jb .r
    call sl_stop
    mov byte [sl_ph], SL_PH_GAP
    mov byte [sl_tk], 0
.r:
    ret

; sl_sample - channel 1 now, into the run's next sample (LF_QUIET: read one
; tick in SL_QEVERY, a "not read" mark on the others)
sl_sample:
    push ax
    push bx
    push cx
    push si
    push di
    mov al, [sl_run]
    call sl_row
    call sl_resp
    mov al, [si+SLR_NS]
    cmp al, SL_TICKS
    jae .out
    inc byte [si+SLR_NS]
    call sl_sampp                   ; DI = sample AL of this run
    test byte [bx+11], LF_QUIET
    jz .read
    mov al, [sl_tk]
    inc ax
    test al, SL_QEVERY - 1
    jz .read
    mov word [di], 0
    mov word [di+2], 0xEE00         ; not read this tick
    jmp short .out
.read:
    push di
    mov di, sd_dbuf
    mov al, SDGF_DMARD
    push bx
    mov bx, DRVC_SOUND * 256 + SNDV_DIAG
    call OSAPI_DRV_CALL
    pop bx
    pop di
    mov ax, [sd_dbuf+SDD_CH+4]      ; channel 1's current address
    mov [di], ax
    mov al, [sd_dbuf+SDD_ST]
    mov ah, 0
    mov [di+2], ax
    or [si+SLR_TC], al
.out:
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; sl_sampp - DI = sample AL of run [sl_run]. Keeps everything else
sl_sampp:
    push ax
    push dx
    push cx
    xor ah, ah
    shl ax, 1
    shl ax, 1                       ; x SL_SAMPW
    push ax
    mov al, [sl_run]
    xor ah, ah
    mov cx, SL_TICKS * SL_SAMPW
    mul cx
    pop di
    add di, ax
    add di, sl_samp
    pop cx
    pop dx
    pop ax
    ret

; sl_recp - DI = run AL's kept record. Keeps everything else
sl_recp:
    push ax
    push dx
    push cx
    xor ah, ah
    mov cx, SL_RECW
    mul cx
    add ax, sl_recs
    mov di, ax
    pop cx
    pop dx
    pop ax
    ret

; sl_stop - end the run, keep the driver's record of it, judge it
sl_stop:
    push ax
    push bx
    push cx
    push si
    push di
    mov al, SDGF_LABSTOP
    mov bx, DRVC_SOUND * 256 + SNDV_DIAG
    call OSAPI_DRV_CALL
    mov di, sl_rec                  ; the whole record, then the part kept
    mov al, SDGF_LABREC
    mov bx, DRVC_SOUND * 256 + SNDV_DIAG
    call OSAPI_DRV_CALL
    mov al, [sl_run]
    call sl_recp
    push es
    push ds
    pop es
    mov si, sl_rec
    mov cx, SL_RECW
    cld
    rep movsb
    pop es
    mov al, [sl_run]
    call sl_row
    call sl_resp
    mov byte [si+SLR_STAT], SLS_RAN
    mov ax, [sl_rec+SDL_IRQ]
    mov [si+SLR_IRQ], ax
    mov al, [sl_rec+SDL_ST]
    or [si+SLR_TC], al
    mov al, [sl_rec+SDL_DTMO]
    add [si+SLR_DTMO], al
    call sl_judge
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; sl_judge - BX = the row, SI = the result: the bytes the 8237 moved (its
; address register's advance, summed over the read samples, modulo the cycle)
; and the first sample from which three read samples in a row show the
; address standing still
sl_judge:
    push ax
    push bx
    push cx
    push dx
    push di
    push bp
    call sl_len
    dec ax
    mov bp, ax                      ; BP = the cycle's mask (a power of two)
    xor al, al
    call sl_sampp                   ; DI = sample 0
    mov ax, [sl_lp+LP_OFF]
    mov [sl_jprev], ax              ; where the cycle began
    xor ax, ax
    mov [si+SLR_MOVED], ax
    mov [si+SLR_MOVED+2], ax
    mov byte [sl_jsame], 0
    mov byte [sl_jlast], 0
    mov cl, [si+SLR_NS]
    xor ch, ch
    xor dl, dl                      ; DL = the sample index
    jcxz .done
.s:
    cmp byte [di+3], 0xEE           ; not read this tick
    je .n
    mov ax, [di]
    mov bx, ax
    sub ax, [sl_jprev]
    and ax, bp
    mov [sl_jprev], bx
    add [si+SLR_MOVED], ax
    adc word [si+SLR_MOVED+2], 0
    or ax, ax
    jnz .moved
    or dl, dl                       ; (sample 0 standing at the start is a
    jz .moved                       ; DMA that never began: no stall point)
    inc byte [sl_jsame]
    cmp byte [sl_jsame], 2
    jb .n
    cmp byte [si+SLR_STALL], 0xFF
    jne .n
    mov al, [sl_jlast]              ; the stall began at the read before the
    mov [si+SLR_STALL], al          ; first standing one
    mov ax, [di]
    mov [si+SLR_SADDR], ax
    sub ax, [sl_lp+LP_OFF]
    and ax, bp
    mov [si+SLR_SPOS], ax
    jmp short .n
.moved:
    mov byte [sl_jsame], 0
    mov [sl_jlast], dl
.n:
    add di, SL_SAMPW
    inc dl
    loop .s
.done:
    pop bp
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; sl_finish - the lab is over: buffers back, the B report when AUTO
sl_finish:
    call sl_free
    cmp byte [sd_autorun], 0
    je .r
    mov byte [sd_autorun], 0
    mov al, 'B'
    call sd_save
    mov [sd_saveb], ax
.r:
    ret

; =============================================================================
; pages 4 and 5
; =============================================================================
sd_page4:
    ROW 1
    PUTS 'DMA lab: the debug driver drives the DSP and DMA channel 1 itself.'
    mov al, [sl_ph]
    cmp al, SL_PH_OFF
    jne .on
    COL 0
    PUTS 'DMA lab: not run yet. A runs the play test and the lab, L the lab alone.'
    jmp .tab
.on:
    COL 68                          ; (COL takes AX)
    mov al, [sl_ph]
    cmp al, SL_PH_DONE
    je .done
    PUTS 'RUN '
    mov al, [sl_run]
    xor ah, ah
    inc ax
    call sd_dec
    PUTS '/'
    mov ax, SL_N
    call sd_dec
    jmp .tab
.done:
    cmp byte [sl_why], 0
    jne .why
    PUTS 'Done.'
    jmp .tab
.why:
    COL 0
    PUTS 'DMA lab: NOT RUN - '
    mov al, [sl_why]
    cmp al, 1
    jne .w2
    PUTS 'this SOUND.DRV is not the debug build.'
    jmp .tab
.w2:
    cmp al, 2
    jne .w3
    PUTS 'no Sound Blaster DSP tier is up.'
    jmp .tab
.w3:
    cmp al, 3
    jne .w4
    PUTS 'kern_mega (protected mode) is not a lab machine.'
    jmp .tab
.w4:
    cmp al, 4
    jne .w5
    PUTS 'no memory for its two 16KB buffers.'
    jmp .tab
.w5:
    PUTS 'the play test is still running.'
.tab:
    ROW 2
    call sl_colhdr
    xor cx, cx
.r:
    mov al, cl
    add al, 3
    call sd_row
    mov al, cl
    call sl_line
    inc cx
    cmp cx, SL_P4
    jb .r
    ret

sl_colhdr:
    PUTS ' # run     buf  cycle block 8237 DSP  IRQs   moved  result'
    ret

sd_page5:
    ROW 1
    call sl_colhdr
    mov cx, SL_P4
.r:
    mov al, cl
    sub al, SL_P4 - 2
    call sd_row
    mov al, cl
    call sl_line
    inc cx
    cmp cx, SL_N
    jb .r
    ROW 6
    PUTS 'Buffers: low '
    mov ax, [sl_lbuf]
    call sl_phys
    PUTS '  high '
    mov ax, [sl_lbuf+2]
    call sl_phys
    cmp byte [sd_diag], 0
    je .ess
    PUTS '  stream ring '
    mov al, [sd_rec+SDG_O_XPAGE]
    call sd_hex2
    mov ax, [sd_rec+SDG_O_XOFF]
    call sd_hex4
    PUTS '+'
    mov ax, [sd_rec+SDG_O_XCNT]
    call sd_hex4
.ess:
    ROW 7
    PUTS 'ESS reg   '
    mov si, sdg_essl_p
.en:
    lodsb
    or al, al
    jz .ev
    call sd_hex2
    inc di
    jmp .en
.ev:
    ROW 8
    PUTS 'ext C6h   '
    mov si, sd_essx
    mov al, [sd_essxn]
    call sl_ess
    ROW 9
    PUTS 'compat    '
    mov si, sd_essc
    mov al, [sd_esscn]
    call sl_ess
    ROW 10
    PUTS 'at stop   '
    mov al, SL_N - 2                ; ESSREGS' record (NOAUTO is last)
    call sl_recp
    mov si, di
    mov di, [sd_rowp]
    add di, 10
    mov al, [si+SDL_ESSN]
    add si, SDL_ESS
    call sl_ess
    ROW 11
    PUTS '8237 after play: '
    call sl_dline
    ROW 13
    PUTS 'Ran on:  '
    mov ah, SLS_RAN
    mov al, 0
    call sl_names
    ROW 14
    PUTS 'Froze:   '
    mov ah, SLS_RAN
    mov al, 1
    call sl_names
    ROW 15
    PUTS 'Report:  '
    mov ax, [sd_savea]
    mov si, sd_namea
    call sl_saved
    PUTS '  '
    mov ax, [sd_saveb]
    mov si, sd_nameb
    call sl_saved
    ret

; sl_saved - SI = a name, AX = 0 written, 0FFFFh never asked, else an error
sl_saved:
    cmp ax, 0xFFFF
    je .r
    push ax
    call sd_puts
    pop ax
    or ax, ax
    jz .ok
    PUTS ' FAILED '
    call sd_dec
    ret
.ok:
    PUTS ' saved'
.r:
    ret

; sl_names - every run whose result is AH and which froze (AL = 1) or not
sl_names:
    push cx
    push si
    xor cx, cx
.l:
    push ax
    mov al, cl
    call sl_resp
    pop ax
    cmp [si+SLR_STAT], ah
    jne .n
    mov bl, [si+SLR_STALL]
    cmp bl, 0xFF
    je .nf
    or al, al
    jz .n
    jmp short .p
.nf:
    or al, al
    jnz .n
.p:
    push ax
    push bx
    mov al, cl
    call sl_row
    mov si, [bx]
    call sd_puts
    inc di
    pop bx
    pop ax
.n:
    inc cx
    cmp cx, SL_N
    jb .l
    pop si
    pop cx
    ret

; sl_ess - SI = 13 register bytes, AL = how many answered (0: none read)
sl_ess:
    or al, al
    jnz .g
    PUTS 'not read'
    ret
.g:
    mov cx, 13
.l:
    lodsb
    call sd_hex2
    inc di
    loop .l
    ret

; sl_phys - AX = a segment -> its physical address, five hex digits
sl_phys:
    or ax, ax
    jnz .g
    PUTS 'none'
    ret
.g:
    push ax
    mov al, ah
    mov cl, 4
    shr al, cl
    add al, '0'
    cmp al, '9'
    jbe .d
    add al, 7
.d:
    stosb
    pop ax
    shl ax, cl
    call sd_hex4
    ret

; sl_dline - the 8237 snapshot in sd_dpost as one row
sl_dline:
    cmp byte [sd_dpostok], 0
    jne .g
    PUTS 'not read'
    ret
.g:
    mov si, sd_dpost
    mov cx, 4
.c:
    lodsw                           ; address
    call sd_hex4
    PUTS '/'
    lodsw                           ; count
    call sd_hex4
    inc di
    loop .c
    ROW 12
    PUTS '                 status '
    lodsb
    call sd_hex2
    PUTS '  0Fh '
    lodsb
    call sd_hex2
    PUTS '  pages 87/83/81/82 '
    mov cx, 4
.p:
    lodsb
    call sd_hex2
    inc di
    loop .p
    ret

; sl_line - AL = run index: one row of the lab table at DI
sl_line:
    push ax
    push bx
    push cx
    push dx
    push si
    push ax
    call sl_row
    call sl_resp
    pop ax
    xor ah, ah
    inc ax
    mov cx, 2
    call sd_fld
    inc di
    push si
    mov si, [bx]
    call sd_puts
    pop si
    COL 11
    PUTS 'lo'
    cmp byte [bx+SLT_BUF], 0
    je .b
    dec di
    dec di
    PUTS 'hi'
.b:
    COL 13
    call sl_len
    mov cx, 6
    call sd_fld
    mov ax, [bx+4]
    mov cx, 6
    call sd_fld
    COL 27
    mov al, [bx+8]
    call sd_hex2
    COL 32
    mov al, [bx+9]
    call sd_hex2
    mov al, [si+SLR_STAT]
    cmp al, SLS_NONE
    je .out
    cmp al, SLS_SKIP
    jne .ns
    COL 49
    PUTS 'skipped (card cannot)'
    jmp .out
.ns:
    cmp al, SLS_FAIL
    jne .nf
    COL 49
    PUTS 'START REFUSED '
    mov al, [si+SLR_ERR]
    xor ah, ah
    call sd_dec
    jmp .out
.nf:
    cmp al, SLS_RUN
    jne .ran
    COL 49
    PUTS 'running...'
    jmp .out
.ran:
    COL 35
    mov ax, [si+SLR_IRQ]
    mov cx, 5
    call sd_fld
    mov ax, [si+SLR_MOVED]
    mov dx, [si+SLR_MOVED+2]
    mov cx, 8
    call sl_fld32
    COL 49
    mov ax, [si+SLR_MOVED]
    or ax, [si+SLR_MOVED+2]
    jnz .mv
    PUTS 'NO DMA'
    jmp .tc
.mv:
    cmp byte [si+SLR_STALL], 0xFF
    jne .st
    PUTS 'ran'
    jmp .tc
.st:
    PUTS 'FROZE at '
    mov ax, [si+SLR_SPOS]
    call sd_dec
    PUTS ' @'
    mov al, [si+SLR_STALL]          ; samples are a tick apart: tenths of a
    xor ah, ah                      ; second = (sample + 1) x 100 / 182
    inc ax
    mov cx, 100
    mul cx
    mov cx, 182
    div cx
    xor dx, dx
    mov cx, 10
    div cx
    call sd_dec
    PUTS '.'
    xchg ax, dx
    call sd_dec
    PUTS 's'
.tc:
    test byte [si+SLR_TC], 0x02
    jz .dt
    PUTS ' TC'
.dt:
    cmp byte [si+SLR_DTMO], 0
    je .out
    PUTS ' t/o'
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; sl_fld32 - DX:AX right-aligned in CX columns
sl_fld32:
    push si
    push bx
    mov si, sd_num
    xchg si, di
    push si
    call dec_u32                    ; into sd_num
    mov bx, di
    sub bx, sd_num                  ; BX = digits
    pop di
    sub cx, bx
    jbe .c
    mov al, ' '
.p:
    stosb
    loop .p
.c:
    mov si, sd_num
    mov cx, bx
    rep movsb
    pop bx
    pop si
    ret

sdg_essl_p: db 0xA1, 0xA2, 0xA4, 0xA5, 0xA8, 0xB1, 0xB2, 0xB4
            db 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0

; =============================================================================
; THE REPORT - benchlib's (tests/benchlib.inc): every line through bl_lcommit,
; the file through bl_save, numbered (BL_NUMBERED)
; =============================================================================

; sd_save - AL = 'A', 'B' or 'S': the whole report, rebuilt now, saved as
; SOUND<L>n.TXT for the first free n. out AX = 0 saved, 1 failed, and the
; name kept for page 5
sd_save:
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov [sd_sletter], al
    mov [sd_stem+5], al
    call sd_mkreport
    mov bx, [sd_win]                ; bl_progress's line is our keys row
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    add ax, 4
    mov [bl_cx], ax
    push dx
    call sd_pitch
    mov cx, SD_ROWS - 1
    mul cx
    pop dx
    add ax, dx
    add ax, 2
    mov [bl_cy], ax
    mov word [bl_prows], 0
    mov word [bl_vcols], SD_COLS
    mov si, sd_stem
    call bl_save                    ; "WRITING THE REPORT", then the file
    mov byte [sd_shown + (SD_ROWS - 1) * SD_LW], 0xFF   ; redraw that row
    xor ax, ax
    cmp word [bl_savemsg], bl_s_werr
    jne .ok
    inc ax
.ok:
    push ax
    push ds
    pop es
    mov si, bl_nname                ; the name it went to
    mov di, sd_namea
    cmp byte [sd_sletter], 'A'
    je .cp
    mov di, sd_nameb
.cp:
    mov cx, 13
    cld
    rep movsb
    pop ax
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; sl_emit - the scratch line (sd_line, built with the pages' own PUTS and
; hex helpers) into the report
sl_emit:
    push cx
    push si
    push di
    push es
    push ds
    pop es
    mov si, sd_line
    mov di, bl_lscr
    mov cx, BL_MAXLINE
    cld
    rep movsb
    mov byte [bl_lscr + BL_MAXLINE], 0
    pop es
    call bl_lcommit
    pop di
    pop si
    pop cx
    ret

; sd_lnew - a blank scratch line: DI = sd_line, [sd_rowp] = it, so PUTS and
; COL write it as they write a page row. ES = DS for the caller
sd_lnew:
    push ax
    push cx
    push ds
    pop es
    mov di, sd_line
    mov [sd_rowp], di
    mov cx, SD_COLS
    mov al, ' '
    cld
    rep stosb
    xor al, al
    stosb
    mov di, sd_line
    pop cx
    pop ax
    ret


; sl_hex - SI = bytes, CX = count: hex, 24 to a line
sl_hex:
    push ax
    push bx
    push cx
    xor bx, bx
.l:
    or bx, bx
    jnz .g
    call sd_lnew
    inc di
.g:
    lodsb
    call sd_hex2
    inc di
    inc bx
    cmp bx, 24
    jb .n
    call sl_emit
    xor bx, bx
.n:
    loop .l
    or bx, bx
    jz .r
    call sl_emit
.r:
    pop cx
    pop bx
    pop ax
    ret

; sd_mkreport - the report, from its first line: benchlib's banner (it is
; bl_lcommit's), our head, the five pages and the raw samples
sd_mkreport:
    mov word [bl_nrow], 0           ; a fresh report (bl_lcommit empties the
    mov al, [sd_page]               ; arena on its first line)
    push ax
    call sd_lnew
    PUTS 'os8088 Sound Debug  build '
    mov ax, BUILD_NUM
    call sd_dec
    PUTS ' report SOUND'
    mov al, [sd_sletter]
    stosb
    PUTS 'n.TXT  '
    call OSAPI_CLK_GET              ; CX year, DH month, DL day, BH:BL hh:mm
    push bx
    push dx
    mov ax, cx
    call sd_dec
    pop dx
    push dx
    mov al, dh
    call sl_two
    pop dx
    mov al, dl
    call sl_two
    pop bx
    push bx
    inc di
    mov al, bh
    call sl_2d
    mov byte [di], ':'
    inc di
    pop bx
    mov al, bl
    call sl_2d
    call sl_emit
    call sd_lnew
    PUTS 'A: after the play test.  B: after the DMA lab.  S: saved by hand.'
    call sl_emit
    xor al, al
.pg:
    mov [sd_page], al
    push ax
    call sd_build
    call sd_lnew
    call sl_emit                    ; a blank line between pages
    xor cx, cx
.row:
    mov ax, cx
    push cx
    mov cx, SD_LW
    mul cx
    pop cx
    add ax, sd_txt
    push cx
    push ds
    pop es
    mov si, ax
    mov di, bl_lscr
    mov cx, BL_MAXLINE
    cld
    rep movsb
    mov byte [bl_lscr + BL_MAXLINE], 0
    call bl_lcommit
    pop cx
    inc cx
    cmp cx, SD_ROWS - 1             ; (not the keys row)
    jb .row
    pop ax
    inc ax
    cmp al, 5
    jb .pg
    call sl_raw
    pop ax
    mov [sd_page], al
    call sd_build
    ret

; sl_two - '-' then AL (0..99) as two digits; sl_2d without the '-'
sl_two:
    mov byte [di], '-'
    inc di
sl_2d:
    aam
    add ax, 0x3030
    xchg al, ah
    stosw
    ret

; sl_raw - everything behind the pages
sl_raw:
    call sd_lnew
    call sl_emit
    call sd_lnew
    PUTS '== the debug driver record, SDG_LEN bytes'
    call sl_emit
    mov si, sd_rec
    mov cx, SDG_LEN
    call sl_hex
    call sd_lnew
    PUTS '== 8237 at boot, then after the play test: ch0-3 addr/count, status,'
    call sl_emit
    call sd_lnew
    PUTS '   0Fh, pages 87 83 81 82, high pages, 2xCh, PIC imr irr isr, IRQs'
    call sl_emit
    mov si, sd_dpre
    mov cx, SDD_LEN
    call sl_hex
    mov si, sd_dpost
    mov cx, SDD_LEN
    call sl_hex
    call sd_lnew
    PUTS '== ESS A1 A2 A4 A5 A8 B1 B2 B4 B5 B6 B7 B8 B9: C6h mode, then compat'
    call sl_emit
    mov si, sd_essx
    mov cx, 16
    call sl_hex
    mov si, sd_essc
    mov cx, 16
    call sl_hex
    ; --- the play test, a tick at a time ---------------------------------------
    call sd_lnew
    PUTS '== play test, every tick: 8237 ch1 count/IRQs (low byte), :status if TC'
    call sl_emit
    mov si, sd_plog
    xor cx, cx
.p:
    cmp cx, [sd_pln]
    jae .pd
    mov ax, cx
    mov bl, 9
    div bl
    or ah, ah
    jnz .pg
    call sd_lnew
.pg:
    inc di
    mov ax, [si+2]
    call sd_hex4
    PUTS '/'
    mov al, [si]
    call sd_hex2
    mov al, [si+4]
    test al, 0x0F
    jz .pn
    PUTS ':'
    call sd_hex2
.pn:
    add si, SD_PLW
    inc cx
    mov ax, cx
    mov bl, 9
    div bl
    or ah, ah
    jnz .p
    call sl_emit
    jmp .p
.pd:
    mov ax, cx
    mov bl, 9
    div bl
    or ah, ah
    jz .runs
    call sl_emit
    ; --- the lab, run by run --------------------------------------------------------
.runs:
    mov al, [sl_run]                ; (sl_sampp and sl_recp index by it)
    push ax
    xor cx, cx
.run:
    mov [sl_run], cl
    push cx
    mov al, cl
    call sl_row
    call sl_resp
    call sd_lnew
    call sl_emit
    call sd_lnew
    mov al, cl
    call sl_line                    ; the page's row...
    call sl_emit
    call sd_lnew                    ; ...and what it does not show
    PUTS '   mode '
    mov al, [bx+8]
    call sd_hex2
    PUTS ' cmd '
    mov al, [bx+9]
    call sd_hex2
    PUTS ' tc '
    mov al, [bx+10]
    call sd_hex2
    PUTS ' flags '
    mov al, [bx+11]
    call sd_hex2
    PUTS ' '
    mov ax, [bx+6]
    call sd_dec
    PUTS 'Hz buf '
    push bx
    mov bl, [bx+SLT_BUF]
    xor bh, bh
    shl bx, 1
    mov ax, [sl_lbuf+bx]
    pop bx
    call sl_phys
    PUTS ' st/dreq '
    mov al, [si+SLR_TC]
    call sd_hex2
    PUTS ' froze '
    mov al, [si+SLR_STALL]
    call sd_hex2
    PUTS ' @'
    mov ax, [si+SLR_SADDR]
    call sd_hex4
    call sl_emit
    cmp byte [si+SLR_STAT], SLS_RAN
    je .ran
    jmp .rn
.ran:
    ; the 8237 address a tick at a time (---- = not read; :xx = the 8237
    ; status when a TC bit was in it), twelve a line
    mov dl, [si+SLR_NS]
    xor dh, dh
    push di
    mov al, 0
    call sl_sampp
    mov bx, di                      ; BX = the sample, DI = the line
    pop di
.sm:
    cmp dh, dl
    jae .smd
    mov al, dh
    xor ah, ah
    mov cl, 12
    div cl
    or ah, ah
    jnz .sg
    call sd_lnew
    PUTS '  '
.sg:
    inc di
    cmp byte [bx+3], 0xEE
    jne .sv
    PUTS '----'
    jmp short .sw
.sv:
    mov ax, [bx]
    call sd_hex4
.sw:
    mov al, [bx+2]
    test al, 0x0F
    jz .sx
    PUTS ':'
    call sd_hex2
.sx:
    add bx, SL_SAMPW
    inc dh
    mov al, dh
    xor ah, ah
    mov cl, 12
    div cl
    or ah, ah
    jnz .sm
    call sl_emit
    jmp .sm
.smd:
    mov al, dh
    xor ah, ah
    mov cl, 12
    div cl
    or ah, ah
    jz .irqs
    call sl_emit
.irqs:
    ; the driver's record: the 8237 at each block IRQ
    pop cx
    push cx
    mov al, cl
    call sl_recp
    mov si, di
    call sd_lnew
    PUTS '   driver: IRQs '
    mov ax, [si+SDL_IRQ]
    call sd_dec
    PUTS ' status '
    mov al, [si+SDL_ST]
    call sd_hex2
    PUTS ' ack '
    mov al, [si+SDL_ACK]
    call sd_hex2
    PUTS ' t/o '
    mov al, [si+SDL_DTMO]
    xor ah, ah
    call sd_dec
    PUTS ' at each IRQ, addr/count/status:'
    call sl_emit
    mov dl, [si+SDL_N]
    cmp dl, 8
    jbe .ln
    mov dl, 8
.ln:
    push si
    add si, SDL_LOG
    xor dh, dh
.il:
    cmp dh, dl
    jae .ild
    test dh, 3
    jnz .ig
    call sd_lnew
    PUTS '  '
.ig:
    inc di
    mov ax, [si]
    call sd_hex4
    PUTS '/'
    mov ax, [si+2]
    call sd_hex4
    PUTS '/'
    mov al, [si+4]
    call sd_hex2
    add si, SDL_LOGW
    inc dh
    test dh, 3
    jnz .il
    call sl_emit
    jmp .il
.ild:
    test dh, 3
    jz .ie
    call sl_emit
.ie:
    pop si
    cmp byte [si+SDL_ESSN], 0
    je .rn
    call sd_lnew
    PUTS '   ESS registers at the stop (C0h, no C6h):'
    call sl_emit
    add si, SDL_ESS
    mov cx, 13
    call sl_hex
.rn:
    pop cx
    inc cx
    cmp cx, SL_N
    jae .end
    jmp .run
.end:
    pop ax
    mov [sl_run], al
    call sd_lnew
    call sl_emit
    call sd_lnew
    PUTS '== end of report'
    cmp byte [bl_full], 0
    je .e
    PUTS ' - TRUNCATED, the arena is full'
.e:
    call sl_emit
    ret
