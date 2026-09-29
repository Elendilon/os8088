; =============================================================================
; os8088 - apps/tracker/trkspk.inc
;
; TRACKER ON THE PC SPEAKER, WITH NO CARD (SPEC.md 45.25,
; docs/plans/completed/SPEAKER-PCM-PLAN.md). The mixer's output goes through the
; speaker shaper (apps/os88spkfx.inc) into 34.11's ring and out as pulse
; widths, from inside Tracker's own FSXF_RATE bracket: the IMPOSTER WINDOW
; (the windowed face live, the desktop frozen - the Video Player's in-window
; play, 98.3.7) or the full screen, whose bracket takes FSXF_RATE in place of
; FSXF_KEEPWORKER | FSXF_FASTTICK when there is no card.
;
; THE BRACKET'S BODY MIXES. The worker feeds a card and nothing else, and
; under a sample ISR a switch rides the 18.2 Hz tick (34.11.3), so tsp_poll -
; called by the imposter's loop and by both of trk_fsx_main's - mixes a span,
; shapes it and puts it in the ring, as the card's worker would have staged
; it; [trk_total] and [trk_consumed] are the ring's, so everything that shows
; the row the LISTENER hears (45.15) reads the speaker the way it read the card.
;
; A 4.77 MHz 8088 CANNOT DO THIS, and the plan's arithmetic said so before a
; line was written: 8 kHz of pulses is ~75% of it and the mixer ~51%. So the
; first Play CALIBRATES (the owner's question 5): the mixer is timed for eight
; ticks and the shaper for four, and the load each rung of rates would put on
; THIS machine is predicted from them - the highest rung under 85% is the one
; played, and with none a Play is refused with the figure, and the next Play
; plays anyway (question 2). A play that falls behind all the same comes down
; a rung, as Audio's does (86.21).
;
;   tsp_play    trk_play's arm with no card: calibrate, start, and - windowed -
;               the imposter bracket. Inside the full screen only the start:
;               its own loop plays it. lock held
;   tsp_poll    the producer: the door, the ring filled, the ladder, the end
;   tsp_halt    the door shut and the play over (trk_play_stop's)
;   tsp_leave   ...the door shut at a bracket's end, the play going on
;   tsp_preemph a loaded module's samples pre-emphasised (no card, at load)
; =============================================================================

TSP_RSIZE   equ 0x20                ; the ring: 4096 << 2
TSP_RL      equ 16384               ; ...16 KB, 2 s at 8 kHz
TSP_LOW     equ TSP_RL / 4          ; a lead under this: behind
TSP_SPANS   equ 4                   ; spans a poll makes at most
TSP_BTICKS  equ 4                   ; ticks the shaper is timed for...
TSP_MTICKS  equ 8                   ; ...and the mixer
%ifndef TSP_PCTMAX
TSP_PCTMAX  equ 100                 ; the most a rung may predict: THE SOUND
%endif                              ; must fit, and the picture has what is
                                    ; left - a frame only while the ring is
                                    ; half full (tsp_wmain), the visualiser
                                    ; off (tw_vizxhi), so a short machine sheds
                                    ; the picture and keeps the music (question
                                    ; 1). A 5150 predicts 95 at 5,512 Hz and
                                    ; holds it with the ring never dry (45.25)
TSP_CS      equ 89                  ; THE SPEAKER'S SHARE against the shaper's
                                    ; bench, MEASURED on MartyPC's 5150 (45.25):
                                    ; the bench emits a sample in ~107 cycles
                                    ; there (Ne = 9,728) and the sample ISR
                                    ; takes ~325 a pulse (37% at 5,417 Hz), so
                                    ; (325 / 107 + 1) x 400 / 18.2 = 89 - and
                                    ; the share at R is R x 89 / Ne percent on
                                    ; any machine the bench has timed
TSP_FSDIV   equ 21845               ; the full screen's period: 54.6 Hz, the
                                    ; text screen's frame clock (45.16)

TSPX_DESK   equ 1                   ; a click or Space: paused, the desktop
TSPX_STOP   equ 2                   ; Esc or S
TSPX_SWAP   equ 3                   ; F: the full screen
TSPX_END    equ 4                   ; the song over
TSPX_ERR    equ 5                   ; the status line says why

; THE RUNGS: an 8088's, and a 286's (a pulse of 54 counts at 22,050 Hz,
; 34.11.8). The owner: the higher rates on a 286, the field confirms them
tsp_r88:    dw 8000, 5512, 0
tsp_rat:    dw 22050, 16000, 11025, 8000, 0

    TRKB tsp_cal                    ; calibrated this session
    TRKB tsp_force                  ; refused once: the next Play plays anyway
    TRKB tsp_run                    ; a speaker play is on
    TRKB tsp_open                   ; ...and the door is open
    TRKB tsp_rung                   ; the rung, kept for the session
    TRKB tsp_exit                   ; TSPX_*
    TRKB tsp_btn                    ; the mouse's buttons, last seen
    TRKB tsp_pend                   ; the imposter's first pass: tsp_prep
    TRKB tsp_pre                    ; the module's samples are filtered (a load
                                    ; on this machine: tsp_preemph)
    TRKW tsp_rseg                   ; the ring's claim
    TRKW tsp_rate                   ; the rate it plays at
    TRKW tsp_span                   ; samples a span
    TRKW tsp_hk                     ; rate periods (tsp_hook)
    TRKW tsp_drawt                  ; ...at the last frame
    TRKW tsp_nm                     ; the mixer's samples in TSP_MTICKS
    TRKW tsp_mchunk                 ; ...mixed a tick's chunk at a time
    TRKW tsp_ne                     ; the shaper's in TSP_BTICKS
    TRKW tsp_pct                    ; the load predicted for the rung
    TRKBUF tsp_save, 3              ; mp_playing, mp_tickrem across the bench
    TRKBUF tsp_chsave, MP_CHSZ * 4  ; ...and the channel records
    TRKBUF tsp_msg, 64              ; the refusal, with its figure (<= 55)
    TRKBUF tsp_fam, SPKFX_NLEV * 256    ; the shaper's level family

tsp_hook:                           ; FSXF_RATE's hook: a period, counted
    inc word [tsp_hk]
    ret

; -----------------------------------------------------------------------------
; tsp_play - trk_play with no card. [trk_pmode] as trk_play's AL. lock held
; -----------------------------------------------------------------------------
tsp_play:
    call tsp_ring                   ; the ring claimed once, for the session
    jc .out
    cmp byte [trk_fs], 0            ; INSIDE THE FULL SCREEN: its bracket is
    je .win                         ; already up and its loop plays it
    call tsp_prep                   ; (tsp_poll) - one bracket at a time
    jmp short .out
.win:
    call trk_repaint_done           ; the face as it is NOW: a load plays
    mov byte [tsp_pend], 1          ; before its completion repaint - and the
    call tsp_window                 ; bracket's first pass is tsp_prep
.out:
    ret

; tsp_prep - calibrated (once), the rung picked, the play started. INSIDE A
; BRACKET, always: THE WORKER IS PARKED THERE, and outside one it draws a
; frame a tick beside the bench - on a 5150's Hercules that read the machine
; at a THIRD of itself. out: CF = 1 refused or not started (said)
tsp_prep:
    cmp byte [tsp_cal], 0
    jne .cal
    call tsp_calib
.cal:
    call tsp_pick                   ; CF = 1 refused, the status line says why
    jc .out
    call tsp_start
.out:
    ret

; tsp_ring - the ring's claim, once. out: CF = 1 no memory (said)
tsp_ring:
    cmp word [tsp_rseg], 0
    jne .ok
    push ax
    push dx
    mov ax, (TSP_RL + 272 + 1023) / 1024
    call OSAPI_MEM_CLAIM
    jc .no
    mov [tsp_rseg], dx
    pop dx
    pop ax
.ok:
    clc
    ret
.no:
    pop dx
    pop ax
    push si
    mov si, trk_s_nomem
    call tui_msg
    pop si
    stc
    ret

; tsp_rates - SI -> this machine's rungs
tsp_rates:
    push ax
    call OSAPI_CPU_INFO
    mov si, tsp_rat
    cmp al, CPU_8086
    jne .at
    mov si, tsp_r88
.at:
    pop ax
    ret

; tsp_tables - the ring's count table and the shaper's family for AX Hz.
; out: CF = 1 the door will not take it
tsp_tables:
    push ax
    push cx
    push dx
    push di
    mov [tsp_rate], ax
    mov word [tsp_span], 256        ; ~32 ms a span (os88spkfx's block)
    cmp ax, 11025
    jbe .sp
    mov word [tsp_span], 512
.sp:
    mov dx, ax
    mov di, [tsp_rseg]
    mov ah, TSP_RSIZE
    xor cl, cl
    call os88spk_init
    jc .out
    mov di, tsp_fam
    mov ax, 0x0100 | SPKFX_PRE_NONE ; the samples were filtered at load
    call os88spkfx_init
    clc
.out:
    pop di
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tsp_calib - TIME THIS MACHINE: the shaper over a span for TSP_BTICKS ticks,
; the mixer for TSP_MTICKS at the first rung's rate, the replayer put back
; where it was. ~0.7 s, once a session
; -----------------------------------------------------------------------------
tsp_calib:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call tsp_rates
    mov ax, [si]
    call tsp_tables
    ; --- THE SHAPER: spans emitted into the ring, counted over the ticks ---
    mov es, [tsp_rseg]
    call tsp_edge                   ; AX = the tick it starts on
    mov bx, ax
    xor dx, dx
.sb:
    mov si, mp_outbuf
    xor di, di
    mov cx, 256
    push ax
    call os88spkfx_emit
    pop ax
    add dx, 256
    call OSAPI_GET_TICKS
    sub ax, bx
    cmp ax, TSP_BTICKS
    jb .sb
    mov [tsp_ne], dx
    ; --- THE MIXER: FOUR CHANNELS, all audible, the song untouched. A bench
    ; of the song's own opening priced BEVERLY.MOD's sparse intro and read
    ; the mixer at a third of its cost in a full passage - so the channel
    ; records are put aside, each given the module's longest sample looped
    ; whole at a step near one, and mixed with no tick due, so the replayer
    ; never moves; then put back ---
    push ds
    pop es
    mov si, mp_chans
    mov di, tsp_chsave
    mov cx, MP_CHSZ * 2
    cld
    rep movsw
    mov al, [mp_playing]
    mov [tsp_save], al
    mov ax, [mp_tickrem]
    mov [tsp_save+1], ax
    mov bx, mp_smptab               ; the longest sample: DI -> its record
    xor di, di
    xor dx, dx
    mov cx, 31
.lg:
    mov ax, [bx+MS_PLEN]
    cmp ax, dx
    jbe .lgn
    mov dx, ax
    mov di, bx
.lgn:
    add bx, MS_SZ
    loop .lg
    mov word [tsp_nm], 0xFFFF       ; no sample at all: the mixer is free
    cmp dx, 2
    jb .mput
    mov bx, mp_chans
    mov cx, 4
.ch:
    mov ax, [di+MS_SEG]
    mov [bx+MP_SEG], ax
    mov ax, [di+MS_OFF]
    mov [bx+MP_OFF], ax
    mov [bx+MP_POSI], ax
    mov [bx+MP_PLEN], dx
    mov [bx+MP_LLEN], dx            ; looped whole: it never goes quiet
    mov word [bx+MP_POSF], 0
    mov word [bx+MP_STEPI], 1       ; ~C-3 at 8 kHz
    mov word [bx+MP_STEPF], 0x0A00
    mov byte [bx+MP_OVOL], 64
    mov byte [bx+MP_ACT], 1
    add bx, MP_CHSZ
    loop .ch
    mov byte [mp_playing], 1
    mov ax, [tsp_rate]              ; the chunk: the rate over 50, a tick at
    mov cx, 50                      ; 125 BPM (2.5 / 125 s)
    xor dx, dx
    div cx
    mov [tsp_mchunk], ax
    call tsp_edge
    mov bx, ax
    xor dx, dx
.mb:
    push bx
    push dx
    mov cx, [tsp_mchunk]            ; A TICK'S CHUNK, as a song mixes: a
    mov ax, cx                      ; chunk ends at every replayer tick, and
    inc ax                          ; each pays the channels' set-up again
    mov [mp_tickrem], ax            ; - one left over, so no tick falls due
    call mp_gen                     ; and the rows stay put (clobbers freely:
    pop dx                          ; the mp_* rule)
    pop bx
    add dx, [tsp_mchunk]
    call OSAPI_GET_TICKS
    sub ax, bx
    cmp ax, TSP_MTICKS
    jb .mb
    mov [tsp_nm], dx
.mput:
    push ds
    pop es
    mov si, tsp_chsave              ; the song as it was
    mov di, mp_chans
    mov cx, MP_CHSZ * 2
    cld
    rep movsw
    mov al, [tsp_save]
    mov [mp_playing], al
    mov ax, [tsp_save+1]
    mov [mp_tickrem], ax
    mov byte [tsp_cal], 1
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tsp_edge - wait for a tick to begin. out: AX = it
tsp_edge:
    push bx
    call OSAPI_GET_TICKS
    mov bx, ax
.w:
    call OSAPI_GET_TICKS
    cmp ax, bx
    je .w
    pop bx
    ret

; -----------------------------------------------------------------------------
; tsp_pick - the rung: from the session's, the first whose predicted load is
; TSP_PCTMAX or under -
;     R x 44 / Nm   the mixer (8 ticks, 100 / 18.2)
;   + R x CS / Ne   the pulses and the shaper, scaled by what the shaper's
;                   bench says this machine is against a 5150
;   + 5             the rest: the display, the tick, the disk
; out: CF = 0 [tsp_rung] set; CF = 1 refused, the status line says so and
;      the next Play plays anyway, at the last rung
; -----------------------------------------------------------------------------
tsp_pick:
    push ax
    push bx
    push si
    call tsp_rates
    mov bl, [tsp_rung]
    xor bh, bh
.r:
    push bx
    shl bx, 1
    mov ax, [si+bx]
    pop bx
    or ax, ax
    jz .none
    call tsp_predict                ; AX = the rate -> AX = percent
    mov [tsp_pct], ax
    cmp ax, TSP_PCTMAX
    jbe .ok
    inc bx
    jmp short .r
.none:
    dec bx                          ; the last rung
    cmp byte [tsp_force], 0
    jne .ok                         ; asked twice: played, and behind
    mov byte [tsp_force], 1
    call tsp_refuse
    stc
    jmp short .out
.ok:
    mov [tsp_rung], bl
    clc
.out:
    pop si
    pop bx
    pop ax
    ret

; tsp_predict - AX = a rate -> AX = the load it would put on this machine, %
tsp_predict:
    push bx
    push cx
    push dx
    mov cx, ax
    mov bx, 44                      ; the mixer
    mul bx
    mov bx, [tsp_nm]
    or bx, bx
    jz .inf
    cmp dx, bx
    jae .inf
    div bx
    push ax
    mov ax, cx                      ; the pulses and the shaper
    mov bx, TSP_CS
    mul bx
    mov bx, [tsp_ne]
    or bx, bx
    jz .inf2
    cmp dx, bx
    jae .inf2
    div bx
    pop bx
    add ax, bx
    add ax, 5
    jmp short .out
.inf2:
    pop ax
.inf:
    mov ax, 999
.out:
    pop dx
    pop cx
    pop bx
    ret

; tsp_refuse - the status line: the load the last rung would need, and what
; to do about it. [tsp_pct] is that load
tsp_refuse:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    cld
    mov si, trk_s_spk1
    mov di, tsp_msg
.c1:
    lodsb
    or al, al
    jz .num
    stosb
    jmp short .c1
.num:
    mov ax, [tsp_pct]               ; the figure, 1..999
    cmp ax, 999
    jbe .n
    mov ax, 999
.n:
    mov bx, 10
    xor cx, cx
    ; STKBALANCE-LOOP: one digit pushed a turn and the second loop pops them; the count is in CX
.d:
    xor dx, dx
    div bx
    push dx
    inc cx
    or ax, ax
    jnz .d
.p:
    pop ax
    add al, '0'
    stosb
    loop .p
    mov si, trk_s_spk2
.c2:
    lodsb
    stosb
    or al, al
    jnz .c2
    mov si, tsp_msg
    call tui_msg
    call trk_say
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tsp_start - the play set up at the rung's rate, from where trk_play's mode
; says (the card's own start, trk_play, with the ring in place of the grant).
; out: CF = 1 refused (said)
; -----------------------------------------------------------------------------
tsp_start:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call tsp_halt                   ; nothing of a last play left open
    call tsp_rates
    mov bl, [tsp_rung]
    xor bh, bh
    shl bx, 1
    mov ax, [si+bx]
    call tsp_tables
    jc .rate
    mov es, [tsp_rseg]              ; the ring empty
    xor ax, ax
    mov [es:TSP_RL], ax             ; TOTAL
    mov [es:TSP_RL+2], ax           ; CONS
    mov ax, [tsp_rate]
    mov [mp_mixrate], ax
    mov al, [trk_pmode]
    call tw_newstream               ; the face's clock, as trk_play's
    mov al, [trk_pmode]
    call mp_start
    xor ax, ax
    mov [trk_total], ax             ; the stream's counters ARE the ring's
    mov [trk_consumed], ax
    mov [mp_stampbase], ax
    call mp_stclear
    mov byte [tui_noppos], 1        ; no card to ask: CONS is the position
    mov word [tui_play], 0
    mov ax, [tsp_rate]              ; bytes a tick, trk_play's arithmetic
    mov dx, 3600
    mul dx
    mov [tui_bpt], dx
    mov word [trk_mixed], 0
    mov byte [trk_ended], 0
    mov byte [trk_pause], 0
    mov byte [tsp_open], 0
    mov byte [tsp_run], 1
    call trk_transport
    clc
    jmp short .out
.rate:
    mov si, trk_s_snderr
    call tui_msg
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tsp_halt - the door shut and the play over (preserves all)
tsp_halt:
    call tsp_leave
    mov byte [tsp_run], 0
    ret

; tsp_leave - the door shut at a bracket's end, CONS exact (preserves all)
tsp_leave:
    cmp byte [tsp_open], 0
    je .out
    call os88spk_stop
    mov byte [tsp_open], 0
.out:
    ret

; -----------------------------------------------------------------------------
; tsp_poll - THE PRODUCER, a pass: once a frame from the imposter's loop and
; from both of trk_fsx_main's. The door opened on a full ring, spans mixed and
; shaped while there is room, the stream's counters the ring's, the ladder,
; and the song's end when the ring has played it out. lock held
; -----------------------------------------------------------------------------
tsp_poll:
    cmp byte [tsp_run], 0
    je .out
    push ax
    push es
    cmp byte [tsp_open], 0
    jne .fill
.pre:                               ; the ring FULL before the door opens
    call tsp_fill
    jnc .pre
    call os88spk_go
    jnc .opened
    mov byte [tsp_run], 0
    push si
    mov si, trk_s_spkbusy
    call tui_msg
    pop si
    mov byte [tsp_exit], TSPX_ERR
    jmp short .done
.opened:
    mov byte [tsp_open], 1
.fill:
    call tsp_fill
    mov es, [tsp_rseg]
    mov ax, [es:TSP_RL]
    mov [trk_total], ax
    mov ax, [es:TSP_RL+2]
    mov [trk_consumed], ax
    cmp byte [mp_playing], 0
    jne .live
    cmp ax, [trk_total]             ; THE SONG OVER, and played out: the next
    jne .done                       ; is trk_song_over's, where a load may
    call tsp_halt                   ; happen - the full screen's loop or the
    mov byte [trk_ended], 1         ; wake the imposter posts on its way out
    mov byte [trk_sover], 1
    mov byte [tsp_exit], TSPX_END
    jmp short .done
.live:
    call tsp_behind
.done:
    pop es
    pop ax
.out:
    ret

; tsp_fill - up to TSP_SPANS spans while the ring has room and the song
; plays. out: CF = 0 one was made, CF = 1 none
tsp_fill:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    mov bp, TSP_SPANS
    stc
    pushf
.l:
    cmp byte [mp_playing], 0
    je .stop
    mov es, [tsp_rseg]
    mov ax, [es:TSP_RL]             ; room: RL - (TOTAL - CONS) >= a span
    mov bx, ax
    sub bx, [es:TSP_RL+2]
    mov cx, TSP_RL
    sub cx, bx
    cmp cx, [tsp_span]
    jb .stop
    mov [mp_stampbase], ax          ; where mp_outbuf[0] lands (45.15)
    push bp
    mov cx, [tsp_span]
    call mp_gen                     ; (clobbers freely: the mp_* rule)
    pop bp
    mov es, [tsp_rseg]
    mov si, mp_outbuf
    mov cx, [tsp_span]
    call os88spkfx_level
    mov di, [es:TSP_RL]             ; into the ring at TOTAL, split at its end
    and di, TSP_RL - 1
    mov bx, cx
    mov ax, TSP_RL
    sub ax, di
    cmp ax, cx
    jae .one
    mov cx, ax
    call os88spkfx_emit
    xor di, di
    mov cx, bx
    sub cx, ax
.one:
    call os88spkfx_emit
    add [es:TSP_RL], bx             ; TOTAL, LAST: the ISR reads it
    popf
    clc
    pushf
    dec bp
    jnz .l
.stop:
    popf
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tsp_behind - a lead under TSP_LOW with the song still playing: the machine
; is behind. The ring played out, the door shut, a rung down (the session
; keeps it), the tables for the new rate - the mixer follows mp_mixrate, its
; steps cached per rate - and the door opened again on a full ring; the
; counters and the stamps run on, so the display does not jump. Past the last
; rung the play goes on behind (the owner: sound and nothing else)
; -----------------------------------------------------------------------------
tsp_behind:
    push ax
    push bx
    push si
    push es
    mov es, [tsp_rseg]
    mov ax, [es:TSP_RL]
    sub ax, [es:TSP_RL+2]
    cmp ax, TSP_LOW
    jae .out
    call tsp_rates
    mov bl, [tsp_rung]
    inc bl
    xor bh, bh
    shl bx, 1
    cmp word [si+bx], 0
    je .out                         ; the last rung: on, behind
.drain:
    mov ax, [es:TSP_RL]
    cmp ax, [es:TSP_RL+2]
    je .down
    mov al, FSXW_FRAME
    call OSAPI_FSX_WAIT
    jmp short .drain
.down:
    call tsp_leave
    inc byte [tsp_rung]
    mov ax, [si+bx]
    call tsp_tables
    mov [mp_mixrate], ax
    push dx
    mov dx, 3600
    mul dx
    mov [tui_bpt], dx
    pop dx
.out:
    pop es
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tsp_window - THE IMPOSTER WINDOW: the play in a bracket of the windowed face,
; again after the full screen hands it back, until it pauses, stops or ends
; -----------------------------------------------------------------------------
tsp_window:
    push ax
    push bx
    push cx
    push dx
    push di
.again:
    mov byte [tsp_exit], TSPX_ERR
    mov bx, [trk_win]
    mov ax, tsp_wmain
    mov cx, FSXF_RATE
    mov dx, 0xFFFF                  ; a period a tick: the face's own pace
    mov di, tsp_hook
    call OSAPI_FSX_RUN
    jnc .ran
    call tsp_halt                   ; (kern_small: no FSXF_RATE at all)
    push si
    mov si, trk_s_nosb
    call tui_msg
    pop si
    jmp short .out
.ran:
    call tsp_leave
    mov al, [tsp_exit]
    cmp al, TSPX_DESK
    jne .n1
    call trk_play_stop              ; PAUSED where the listener is (45.17):
    call trk_transport              ; Space or Play plays on from there
    jmp short .out
.n1:
    cmp al, TSPX_STOP
    jne .n2
    call trk_stop
    jmp short .out
.n2:
    cmp al, TSPX_SWAP
    jne .n3
    call trk_fs_enter               ; the full screen, playing on - and back
    cmp byte [tsp_run], 0           ; here after it while it still plays
    jne .again
    jmp short .out
.n3:
    cmp al, TSPX_END
    jne .out
    call trk_wake                   ; the song over: the wake walks the list
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tsp_wmain - the imposter's body. DS = CS, SI = our window
tsp_wmain:
    mov byte [tsp_btn], 0xFF        ; a button already down is not a click
    mov word [tsp_drawt], 0xFFFF
    cmp byte [tsp_pend], 0          ; THE FIRST PASS: the bench, the rung and
    je .loop                        ; the start, with the worker parked
    mov byte [tsp_pend], 0
    call tsp_prep
    jc .ret                         ; refused: [tsp_exit] is TSPX_ERR
.loop:
    call tsp_poll
    cmp byte [tsp_run], 0
    je .ret                         ; the end, or the door refused (tsp_exit)
    mov ax, [tsp_hk]                ; A FRAME A PERIOD: the face's dynamic
    cmp ax, [tsp_drawt]             ; parts, as the worker draws them -
    je .keys                        ; AUDIO FIRST, as the worker's trk_deep:
    push es                         ; no frame while the ring is under half,
    mov es, [tsp_rseg]              ; so a machine that is short sheds the
    mov bx, [es:TSP_RL]             ; picture and not the sound
    sub bx, [es:TSP_RL+2]
    pop es
    mov [tsp_drawt], ax
    cmp bx, TSP_RL / 2
    jae .draw
    call tw_book                    ; shed: the clock and the position still
    jmp short .keys                 ; booked, as a covered window's are
.draw:
    call tsp_frame
.keys:
    call OSAPI_MOUSE                ; a PRESS anywhere: paused, the desktop
    mov ah, [tsp_btn]
    mov [tsp_btn], al
    not ah
    and al, ah
    test al, 1
    jnz .desk
    mov ah, 1
    int 0x16
    jz .wait
    xor ah, ah
    int 0x16
    cmp al, ' '
    je .desk
    cmp al, 0x0D
    je .desk
    cmp al, 27
    je .stop
    or al, 0x20
    cmp al, 's'
    je .stop
    cmp al, 'f'
    je .swap
    jmp .loop
.wait:
    cmp byte [mp_playing], 0        ; BEHIND: room for a span and a song to
    je .idle                        ; make it from - no waiting for a frame
    push es                         ; (the ISR takes what it needs between)
    mov es, [tsp_rseg]
    mov bx, [es:TSP_RL]
    sub bx, [es:TSP_RL+2]
    pop es
    add bx, [tsp_span]
    cmp bx, TSP_RL
    jbe .loop
.idle:
    mov al, FSXW_FRAME
    call OSAPI_FSX_WAIT
    jmp .loop
.desk:
    mov byte [tsp_exit], TSPX_DESK
    ret
.stop:
    mov byte [tsp_exit], TSPX_STOP
    ret
.swap:
    mov byte [tsp_exit], TSPX_SWAP
.ret:
    ret

; tsp_frame - trk_render's frame with the lock already held (the bracket's)
tsp_frame:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call tw_want
    jnc .out
    mov bx, [trk_win]
    call OSAPI_WM_GEOM
    jc .book
    call OSAPI_WM_CLIP_SET
    jc .book
    cmp byte [trk_abon], 0
    jne .book
    mov byte [tw_inframe], 1
    call tui_draw_dyn
    mov byte [tw_inframe], 0
    jmp short .out
.book:
    call tw_book
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tsp_preemph - the loaded module's SAMPLES pre-emphasised, in place: the
; first difference, y = (x - prev) / 2, each sample from a prev of 0 - the
; shaper's high-pass and tilt (34.11.9) paid ONCE, at load, not per output
; sample: a linear filter commutes with the mix. Only with no card, and for
; the module's life (a card's route taken later hears it thinner). ~1 s for
; 116 KB on a 5150
; -----------------------------------------------------------------------------
tsp_preemph:
    push ax
    push bx
    push cx
    push dx
    push si
    push bp
    push ds
    mov bx, mp_smptab
    mov bp, 31
.s:
    mov cx, [bx+MS_PLEN]
    jcxz .n
    push ds
    mov si, [bx+MS_OFF]
    mov ds, [bx+MS_SEG]
    mov ah, 0x80                    ; prev = 0, biased
.b:
    mov al, [si]
    xor al, 0x80                    ; BIASED: the borrow of x' - prev' is then
    mov dl, al                      ; x < prev, the 9th bit of the true
    sub al, ah                      ; difference - rotated back in, exactly
    rcr al, 1                       ; (x - prev) >> 1, signed
    mov [si], al
    mov ah, dl
    inc si
    loop .b
    pop ds
.n:
    add bx, MS_SZ
    dec bp
    jnz .s
    pop ds
    mov byte [tsp_pre], 1           ; (tests/lzmod.py reads it: the bytes in
    pop bp                          ; memory are no longer the file's)
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
