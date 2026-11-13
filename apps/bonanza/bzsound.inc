; bzsound.inc - BONANZA's sound: the music and the effects (SPEC.md 128.20).
;
; ONE SCORE, TWO RENDERERS, ONE CLOCK.  The songs and the effects are
; tools/bbmusic.py's parts (BZSND.BIN, BZM<S>.BIN, 128.20.3); its Seq and Chip
; classes are this file's sequencer and AdLib arm in Python, step for step,
; and the rows hold the two to each other.  The clock is the physics
; SUB-TICK, 54.6 Hz (BZ_SUB): the bracket steps once per elapsed sub-tick, the
; desktop's title three a system tick (128.20.1).
;
; THE ARMS (128.20.4): the AdLib - SOUND.DRV's whole chip claimed
; (SND_FM_CLAIM) and at most ONE SNDV_OPLW batch a frame of only the
; registers the voices that changed need, capped at BZS_FMCAP, drums on two
; channels so a hit never re-patches, the vibrato the chip's own - or the
; speaker, OSAPI_SND_TONE, ONE voice folded from the effect, a drum's blip,
; the lead and the bass, sent only when its pitch or its note changes.
; Channel 2 and the OPL ports are never touched here (SPEC.md 53.7).
;
; A NOTE IS TWO STAMPS (128.20.1): the sub-tick it was keyed and the one its
; key goes up.  A sub-tick does nothing for a held note unless its pitch
; moves (bzs_dynm), and one deadline (bzs_next) says when a key goes up.
;
; THE EVENTS (128.20.5): physics is never touched for sound.  bzs_frame
; compares the counters it keeps (bz_nland, bz_nbnc, ...) with the last
; frame's and plays the material's effect for each.
;
; Entry points, all with DS = ours; each preserves every register but the
; flags unless it says otherwise:
;   bzs_dstart / bzs_dstop / bzs_dtick   the DESKTOP: the title, and the
;                                        goal's fanfare after a finish
;   bzs_gfetch / bzs_gdrop               bz_launch's: the course's song
;   bzs_open / bzs_frame / bzs_close     the BRACKET's
;   bzs_skey                             S: the player's choice
; =============================================================================

BZS_FMCAP   equ 8               ; OPL registers a frame, at most (128.20.4)
BZS_FMBUF   equ BZS_FMCAP       ; ...the batch: a patch is written a cap's
                                ; worth a frame (H_PPOS), so nothing passes it
%if BZS_FMCAP < 4
 %error "BZS_FMCAP must hold one voice's note: four registers"
%endif
BZS_MAXT    equ 8               ; sub-ticks a call steps, at most (the rest of
                                ; a long stall is dropped, not chased)
BZS_STALL   equ 36              ; desktop: a gap past 2 s (36 ticks) restarts
                                ; the title rather than chasing it
BZS_LMIN    equ 48              ; a LANDING's bz_lvz under this is silent
BZS_PRI     equ 40h             ; the tone priority: the package default

BZS_M_AUTO  equ 0               ; [bzs_mode], S cycles them
BZS_M_SPK   equ 1
BZS_M_FX    equ 2
BZS_M_OFF   equ 3
BZS_A_NONE  equ 0               ; [bzs_arm]
BZS_A_SPK   equ 1
BZS_A_FM    equ 2

; the sound part's header (128.20.3)
BZSH_HZT    equ 4
BZSH_OPT    equ 6
BZSH_INS    equ 8
BZSH_FXT    equ 10
BZSH_EMAP   equ 12
BZSH_MAC    equ 14
; an instrument record
BZI_CAR20   equ 5
BZI_CAR40   equ 6
BZI_MAC     equ 11              ; byte: from the macro pool, 0FFh none
BZI_PID     equ 12              ; the patch's id: instruments that share one
BZI_VDL     equ 13
BZI_VDP     equ 14
BZI_SPK     equ 15              ; bits 0 - 6 a drum's blip, bit 7 `alt`: the
                                ; AdLib's second drum channel (6)
; the song part's header
BZMH_GLEN   equ 3               ; ...then the groove (4), the rows, the order's
BZMH_OORD   equ 12              ; length, the loop row and the flags, copied
BZMH_OPH    equ 14              ; whole into bzs_glen..bzs_flags
BZMH_OSH    equ 16
BZMH_INST   equ 18

; a CHANNEL's record (bzs_ch, four of them)
CH_PTR      equ 0               ; word: the next event, 0 silent this pattern
CH_WAIT     equ 2               ; rows to the next read, 255 none this pattern
CH_INST     equ 3
CH_VOL      equ 4
CH_SHAPE    equ 5
CH_SLUR     equ 6
CH_SIZE     equ 8
; a VOICE's record (bzs_v, eight: 0 - 5 the music's, 6 and 7 the AdLib's
; effect voices, whose music half is unused).  A note is two STAMPS in song
; sub-ticks (bzs_nsub), not two counters: nothing is done for it between its
; key and its key-off unless its pitch moves (V_DYN).  The model's gate and age
; are end - now and now - t0 + 1 (now - end while silent, both at most 255).
V_ON        equ 0
V_RETRIG    equ 1
V_NOTE      equ 2
V_INST      equ 3
V_VOL       equ 4
V_MPOS      equ 5
V_T0        equ 6               ; word: the sub-tick it was keyed
V_END       equ 8               ; word: the sub-tick its key goes up
V_PITCH     equ 10              ; word
H_PITCH     equ 12              ; word: THE CHIP'S (what was last written):
H_TL        equ 14              ;   its pitch (0FFFFh unknown), the carrier's
H_A0        equ 15              ;   40h, A0h, B0h and the instrument whose
H_B0        equ 16              ;   patch it holds (0FFh none)
H_INST      equ 17
V_KEYS      equ 18              ; notes keyed, a byte: the speaker's re-send
V_SPARE     equ 19              ; (free)
V_IREC      equ 20              ; word: its instrument's record, set when keyed
V_DYN       equ 22              ; 1: its pitch moves (a macro): worked out
                                ; every sub-tick
V_BIT       equ 23              ; 1 << the voice (bzs_dynm, bzs_dirty)
H_PPID      equ 24              ; the CHANNEL's patch being written, a frame's
H_PPOS      equ 25              ; registers at a time: its id, the next one
V_SIZE      equ 26
; an EFFECT's slot (bzs_fx, two; the speaker uses the first)
F_PTR       equ 0               ; word: the next segment, 0 idle
F_LEFT      equ 2
F_PITCH     equ 3               ; word
F_SLIDE     equ 5               ; word
F_VOL       equ 7               ; 4.4
F_DECAY     equ 8
F_JIT       equ 9
F_TRANS     equ 10
F_BOOST     equ 11
F_PRIO      equ 12
F_INST      equ 13
F_RETRIG    equ 14
F_OUT       equ 15              ; word: this sub-tick's pitch, 0 silent
F_SEQ       equ 17              ; word: when it started
F_REST      equ 19
F_SEGN      equ 20              ; segments begun, a byte: the speaker's re-send
F_SVOL      equ 21              ; the segment's own volume: the AdLib's level
F_SIZE      equ 22

; the part rows (bonanza.asm's table: after the courses)
BZ_P_SND    equ BZ_P_CRS + BZ_NCRS
BZ_P_SONG   equ BZ_P_SND + 1    ; song S's row: BZ_P_SONG + S

%macro BZ_SND_VARS 0
VAR bzs_mode,1                  ; the player's choice (S): BZS_M_*
VAR bzs_arm,1                   ; the arm open now: BZS_A_*
VAR bzs_live,1                  ; 1: a song is playing
VAR bzs_desk,1                  ; 1: the desktop's title is running (its timer)
VAR bzs_goalp,1                 ; 1: the desktop plays the goal's fanfare first
VAR bzs_song,1                  ; the song part's row, 0 none
VAR bzs_pseg,2                  ; the sound part's segment, 0 none
VAR bzs_mseg,2                  ; the song part's segment, 0 none
VAR bzs_hzt,2                   ; the sound part's tables (its header, copied)
VAR bzs_opt,2
VAR bzs_ins,2
VAR bzs_fxt,2
VAR bzs_emap,2
VAR bzs_mac,2                   ; ...the macro pool
VAR bzs_glen,1                  ; THE SONG: its header +3 .. +11, copied whole
VAR bzs_groove,4
VAR bzs_rows,1
VAR bzs_olen,1
VAR bzs_loop,1
VAR bzs_flags,1
VAR bzs_ooff,2                  ; ...+12 .. +17
VAR bzs_poff,2
VAR bzs_soff,2
VAR bzs_ord,1                   ; the order row playing
VAR bzs_row,1                   ; rows begun in this pattern
VAR bzs_gi,1                    ; the groove's step
VAR bzs_rtick,1                 ; sub-ticks left in the row
VAR bzs_start,1                 ; 0 until the first pattern is loaded
VAR bzs_nsub,2                  ; the song's sub-ticks since its top: NOW
VAR bzs_next,2                  ; the next sub-tick a key goes up
VAR bzs_dynm,1                  ; the voices whose pitch moves (V_BIT)
VAR bzs_dirty,1                 ; the voices the AdLib has not caught up with
VAR bzs_ch,4 * CH_SIZE
VAR bzs_v,8 * V_SIZE
VAR bzs_fx,2 * F_SIZE
VAR bzs_nfx,1                   ; effect slots: 1 on the speaker, 2 on the AdLib
VAR bzs_lfsr,2
VAR bzs_fxseq,2
VAR bzs_shz,2                   ; the speaker's last tone, Hz (0 off)
VAR bzs_stok,2                  ; ...and what sounded it: a source and its note
VAR bzs_spit,2                  ; ...and its pitch word (0 off): the compare
VAR bzs_fmn,2                   ; the batch's registers
VAR bzs_fmb,2 * BZS_FMBUF
VAR bzs_lsub,2                  ; the bracket: [bz_subs] at the last frame
VAR bzs_snap,1                  ; 0 until the counters have been read once
VAR bzs_last,20                 ; the counters, the last frame's (bzs_ctr0..)
VAR bzs_lgoal,1                 ; bz_goal, the last frame's
VAR bzs_lsum,2                  ; ...and the counters' sum
VAR bzs_dtk,2                   ; the desktop: [ticks] at the last call
VAR bz_nwall,2                  ; SOUND STATE the physics writes and never
VAR bz_lwv,2                    ; reads (bzphys.inc bz_refl, 128.20.5): wall
VAR bz_lwb,1                    ; reflections, the last one's speed, 1 a bumper's
%if bzs_groove != bzs_glen + 1 || bzs_rows != bzs_glen + 5 || bzs_flags != bzs_glen + 8 || bzs_ooff != bzs_glen + 9 || bzs_soff != bzs_glen + 13
 %error "bzs_rstart copies the song's header +3 .. +17 onto bzs_glen whole"
%endif
%endmacro

; -----------------------------------------------------------------------------
; THE DESKTOP: the title while the window is open (128.20.6)
; -----------------------------------------------------------------------------

; bzs_dstart - fetch the sound part and the title, open an arm, start the song
; (or only the goal's fanfare's effects machinery), and run the window's timer.
; kern_small has no timer and refuses the game: nothing.
bzs_dstart:
    cmp byte [bz_small], 0
    jne .r
    cmp byte [bzs_mode], BZS_M_OFF
    je .r
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call bzs_fsnd               ; the sound part
    jc .out
    mov al, BZ_P_SONG           ; the title, song 0
    call bzs_fsong
    jc .out
    call bzs_open
    call bzs_rstart
    cmp byte [bzs_goalp], 0     ; a finish: the fanfare over the title's start
    je .arm
    mov byte [bzs_goalp], 0
    mov ax, BZS_E_GOAL          ; (a shared effect: any material's column)
    xor dx, dx
    call bzs_trig
.arm:
    call OSAPI_GET_TICKS
    mov [bzs_dtk], ax
    mov byte [bzs_desk], 1
    mov bx, [bz_win]
    mov ax, 1
    call OSAPI_WM_TIMER
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
.r:
    ret

; bzs_dstop - the title off: the arm closed, both parts given back
bzs_dstop:
    cmp byte [bzs_desk], 0
    je .r
    mov byte [bzs_desk], 0
    call bzs_close
    push ax
    mov al, [bzs_song]
    call bzs_dsong
    mov al, BZ_P_SND
    call op_drop
    mov word [bzs_pseg], 0
    pop ax
.r:
    ret

; bzs_dtick - the window's timer (bz_ontimer): step the sub-ticks the system
; ticks since the last call are worth, three a tick, sound them, ask again
bzs_dtick:
    cmp byte [bzs_desk], 0
    je .r
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call OSAPI_GET_TICKS
    mov cx, ax
    xchg ax, [bzs_dtk]
    sub cx, ax                  ; system ticks since
    cmp cx, BZS_STALL
    jbe .run
    call bzs_rstart             ; a long stall: the title from its top
    mov cx, 1
.run:
    mov ax, cx                  ; x 3 sub-ticks
    shl cx, 1
    add cx, ax
    call bzs_run
    mov bx, [bz_win]
    mov ax, 1
    call OSAPI_WM_TIMER
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
.r:
    ret

; bzs_skey - S: AUTO, SPEAKER, EFFECTS, OFF.  The title stops and starts again
; under the new choice, and the face's sound line says which
bzs_skey:
    call bzs_dstop
    mov al, [bzs_mode]
    inc ax
    and al, 3
    mov [bzs_mode], al
    call bzs_dstart
    jmp bz_line4

; -----------------------------------------------------------------------------
; bz_launch's: the course's song for the bracket, and back to the title
; -----------------------------------------------------------------------------

; bzs_gfetch - the title off, and the sound part and course [bz_crs]'s song
; fetched (128.20.6: course K plays song K, BENCH song 1, past five wraps).  A
; part that cannot be had (its toast said why) leaves the play SILENT, never
; refused.  Preserves nothing.
bzs_gfetch:
    call bzs_dstop
    cmp byte [bzs_mode], BZS_M_OFF
    je .r
    call bzs_fsnd
    jc .r
    mov al, [bz_crs]
    or al, al
    jnz .k
    inc ax                      ; BENCH: song 1
.k:
    cmp al, BZS_NSONG
    jb .s
    sub al, BZS_NSONG - 1
    jmp short .k
.s:
    add al, BZ_P_SONG
    call bzs_fsong
.r:
    ret

; bzs_gdrop - after the bracket: the course's song given back, and the title
; again - with the goal's fanfare when the play or the replay finished
bzs_gdrop:
    push ax
    mov al, [bzs_song]
    call bzs_dsong
    mov al, BZ_P_SND
    call op_drop
    mov word [bzs_pseg], 0
    cmp byte [bz_mode], 1       ; (a benchmark has no finish)
    je .t
    mov al, [bz_goal]
    mov [bzs_goalp], al
.t:
    pop ax
    jmp bzs_dstart

; bzs_fsnd - the sound part fetched and its tables read.  CF = 1 it could not
; be had.  Clobbers AX, BX, CX, DX, SI, DI, ES.
bzs_fsnd:
    mov al, BZ_P_SND
    call op_fetch
    jc .r
    mov al, BZ_P_SND
    call op_seg
    mov [bzs_pseg], ax
    mov es, ax
    mov si, BZSH_HZT
    mov di, bzs_hzt
    mov cx, 6
.c:
    mov ax, [es:si]
    mov [di], ax
    inc si
    inc si
    inc di
    inc di
    loop .c
    clc
.r:
    ret

; bzs_fsong - part row AL (a song) fetched as the song.  CF = 1 not had.
; Clobbers AX, BX, CX, DX, SI, DI, ES.
bzs_fsong:
    push ax
    call op_fetch
    pop ax
    jc .r
    mov [bzs_song], al
    call op_seg
    mov [bzs_mseg], ax
    clc
.r:
    ret

; bzs_dsong - part row AL (the song, 0 none) given back.  Preserves all.
bzs_dsong:
    or al, al
    jz .r
    mov byte [bzs_song], 0
    mov byte [bzs_live], 0
    mov word [bzs_mseg], 0
    push ds                     ; (op_drop restores ES: ours, never the
    pop es                      ; part's selector, which is gone after it)
    call op_drop
.r:
    ret

; -----------------------------------------------------------------------------
; THE BRACKET: open, a frame, close
; -----------------------------------------------------------------------------

; bzs_open - an arm, from OSAPI_SND_CAPS and the player's choice (128.20.4):
; the AdLib where SND_CAP_FM is published AND the tone route is not the
; Control Panel's speaker (BL = 0), and the claim succeeds; else the speaker.
; The song from its top.  Also the desktop's.  Preserves all.
bzs_open:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov byte [bzs_arm], BZS_A_NONE
    mov byte [bzs_snap], 0
    cmp word [bzs_pseg], 0
    je .out
    mov al, [bzs_mode]
    cmp al, BZS_M_OFF
    je .out
    cmp al, BZS_M_SPK
    je .spk
    call OSAPI_SND_CAPS
    test ax, SND_CAP_FM
    jz .spk
    or bl, bl
    jz .spk
    mov bh, DRVC_SOUND          ; ASK IT FIRST (SPEC.md 20.11.1)
    mov bl, SNDV_IDENT
    call OSAPI_DRV_CALL
    jc .spk
    cmp ax, SND_SIG
    jne .spk
    mov al, SND_FM_CLAIM
    xor cl, cl                  ; OPL2 mode
    call OSAPI_SND_FM
    jc .spk
    mov byte [bzs_arm], BZS_A_FM
    mov byte [bzs_nfx], 1
    mov di, bzs_v               ; the chip's shadows: nothing known
    mov cx, 8
.h:
    mov word [di + H_PITCH], 0FFFFh
    mov word [di + H_TL], 0FFFFh ; H_TL and H_A0
    mov byte [di + H_PPID], 0FFh
    mov byte [di + H_B0], 0
    mov byte [di + H_INST], 0FFh
    add di, V_SIZE
    loop .h
    jmp short .fx
.spk:
    mov byte [bzs_arm], BZS_A_SPK
    mov byte [bzs_nfx], 1
    mov word [bzs_shz], 0
    mov word [bzs_spit], 0
.fx:
    mov di, bzs_v               ; each voice's bit
    mov al, 1
.bt:
    mov [di + V_BIT], al
    add di, V_SIZE
    shl al, 1
    jnc .bt
    mov byte [bzs_dirty], 0FFh  ; the chip: nothing known
    mov byte [bzs_dynm], 0
    mov word [bzs_fmn], 0
    mov word [bzs_fx + F_PTR], 0
    mov word [bzs_fx + F_SIZE + F_PTR], 0
    mov word [bzs_lfsr], 0ACE1h
    call bzs_rstart
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; bzs_close - silence, and the chip given back.  Every way out.  Preserves all.
bzs_close:
    push ax
    push cx
    push dx
    mov al, [bzs_arm]
    mov byte [bzs_arm], BZS_A_NONE
    mov byte [bzs_live], 0
    cmp al, BZS_A_FM
    jne .spk
    mov al, 3                   ; every voice off, the default patches, the
    call OSAPI_SND_FM           ; claim given back
    jmp short .out
.spk:
    cmp al, BZS_A_SPK
    jne .out
    xor ax, ax
    xor cx, cx
    mov dl, BZS_PRI
    call OSAPI_SND_TONE
.out:
    pop dx
    pop cx
    pop ax
    ret


; bzs_frame - once a frame, after the steps (bzgame.inc): the events the
; steps counted, a sound step for every sub-tick since the last frame, and the
; arm's output.  The bracket's first frame only reads the clock and the
; counters.  Preserves all.
bzs_frame:
    cmp byte [bzs_arm], BZS_A_NONE
    je .r
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov ax, [bz_subs]
    mov cx, ax
    xchg ax, [bzs_lsub]
    sub cx, ax                  ; sub-ticks since the last frame
    call bzs_events             ; (preserves CX)
    cmp byte [bzs_snap], 0
    jne .go
    mov byte [bzs_snap], 1
    jmp short .out
.go:
    call bzs_run
.fend:                          ; (bonanzasound prices a frame's sound to here)
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
.r:
    ret

; -----------------------------------------------------------------------------
; bzs_events - THE EVENTS (128.20.5): every counter the physics keeps against
; the last frame's copy; a difference plays the material's effect.  While
; [bzs_snap] is 0 the copies are only taken.  Preserves CX; clobbers AX, BX,
; DX, SI, DI, ES.
; -----------------------------------------------------------------------------
%define bzs_ctr0    bz_nland    ; the counters, compared unrolled (bzs_events)
%define bzs_ctr1    bz_nbnc
%define bzs_ctr2    bz_nwall
%define bzs_ctr3    bz_nstun
%define bzs_ctr4    bz_nshat
%define bzs_ctr5    bz_nhop
%define bzs_ctr6    bz_nfall
%define bzs_ctr7    bz_nkick    ; (wave 3's, SPEC.md 128.12.6.6)
%define bzs_ctr8    bz_nknock
%define bzs_ctr9    bz_ntube
BZS_NCTR    equ 10              ; (bzs_last holds 10, and DX has 16 bits)
bzs_ctab:   dw bzs_ctr0, bzs_ctr1, bzs_ctr2, bzs_ctr3, bzs_ctr4, bzs_ctr5, bzs_ctr6
            dw bzs_ctr7, bzs_ctr8, bzs_ctr9
%if ($ - bzs_ctab) / 2 != BZS_NCTR
 %error "bzs_ctab names every counter"
%endif
BZS_C_LAND  equ 1               ; the bits, bzs_ctab's order
BZS_C_BNC   equ 2
BZS_C_WALL  equ 4
BZS_C_STUN  equ 8
BZS_C_SHAT  equ 16
BZS_C_HOP   equ 32
BZS_C_FALL  equ 64
BZS_C_KICK  equ 128
BZS_C_KNOCK equ 256
BZS_C_TUBE  equ 512

bzs_events:
    push cx
    xor dx, dx                  ; DX: a bit for each counter that moved
    mov ax, [bzs_ctr0]          ; THE SUM FIRST: the counters only grow, so
%assign BZS_I 1                 ; it moves when any does (the usual frame:
%rep BZS_NCTR - 1               ; none does, and this is all)
    add ax, [bzs_ctr %+ BZS_I]
 %assign BZS_I BZS_I + 1
%endrep
    cmp ax, [bzs_lsum]
    je .goal
    mov [bzs_lsum], ax
    mov si, bzs_ctab            ; ...and only then which: a loop, on the frame
    mov di, bzs_last            ; something happened
    mov cx, 1
.c:
    mov bx, [si]
    mov ax, [bx]
    cmp ax, [di]
    je .n
    mov [di], ax
    or dx, cx
.n:
    inc si
    inc si
    inc di
    inc di
    shl cx, 1
    cmp cx, 1 << BZS_NCTR
    jb .c
.goal:
    mov al, [bz_goal]
    xchg al, [bzs_lgoal]
    or dx, dx                   ; nothing moved (the usual frame)
    jnz .any
    cmp al, [bzs_lgoal]
    je .out
.any:
    cmp byte [bzs_snap], 0
    je .out
    mov ah, [bz_mat]            ; AH = the material, for every trigger
    or al, al                   ; GOAL: 0 to 1 (in the bracket only on the
    jnz .shat                   ; frame the loop leaves; the desktop plays the
    cmp byte [bz_goal], 0       ; fanfare after it, bzs_gdrop)
    je .shat
    mov al, BZS_E_GOAL
    call bzs_trig0
.shat:
    test dx, BZS_C_SHAT
    jz .stun
    mov al, BZS_E_SHATTER
    call bzs_trig0
.stun:
    test dx, BZS_C_STUN
    jz .bnc
    mov al, BZS_E_STUN
    call bzs_trigz
.bnc:
    test dx, BZS_C_BNC
    jz .land
    mov al, BZS_E_BOUNCE
    call bzs_trigz
.land:
    test dx, BZS_C_LAND         ; a LANDING alone: not a bounce, stun, shatter
    jz .hop                     ; or hop of the same contact, and hard enough
    test dx, BZS_C_BNC | BZS_C_STUN | BZS_C_SHAT | BZS_C_HOP
    jnz .hop
    cmp word [bz_lvz], BZS_LMIN
    jl .hop
    mov al, BZS_E_LAND
    call bzs_trigz
.hop:
    test dx, BZS_C_HOP
    jz .wall
    mov al, BZS_E_HOP
    call bzs_trig0
.wall:
    test dx, BZS_C_WALL         ; a wall, or a bumper's face (bz_lwb)
    jz .fall
    mov al, BZS_E_WALL
    cmp byte [bz_lwb], 0
    je .w
    mov al, BZS_E_BUMPER
.w:
    push ax
    push dx
    mov dx, [bz_lwv]
    call bzs_trig
    pop dx
    pop ax
.fall:
    test dx, BZS_C_FALL
    jz .kick
    mov al, BZS_E_FALL
    call bzs_trig0
.kick:
    test dx, BZS_C_KICK         ; a bumper post's kick
    jz .knock
    mov al, BZS_E_BUMPER
    call bzs_trig0
.knock:
    test dx, BZS_C_KNOCK        ; a windmill's knock-back
    jz .tube
    mov al, BZS_E_KNOCK
    call bzs_trig0
.tube:
    test dx, BZS_C_TUBE         ; a tube's capture
    jz .out
    mov al, BZS_E_TUBE
    call bzs_trig0
.out:
    pop cx
    ret

; bzs_trigz - event AL for material AH at the landing's strength (bz_lvz);
; bzs_trig0 - at strength 0.  Both keep DX (the bits) and AH.
bzs_trigz:
    push dx
    mov dx, [bz_lvz]
    jmp short bzs_trigd
bzs_trig0:
    push dx
    xor dx, dx
bzs_trigd:
    push ax
    call bzs_trig
    pop ax
    pop dx
    ret

; -----------------------------------------------------------------------------
; bzs_trig - event AL, material AH, strength DX: its effect into a slot
; (Seq.trigger): an idle slot, else the lowest priority (the older on a tie)
; if that is not above this effect's.  Clobbers AX, BX, CX, SI, DI, ES.
; -----------------------------------------------------------------------------
bzs_trig:
    cmp word [bzs_pseg], 0
    je .r
    mov es, [bzs_pseg]
    xchg al, ah                 ; AL = the material, AH = the event
    mov bl, ah
    mov ah, BZS_NEV
    mul ah
    add al, bl
    adc ah, 0
    mov bx, ax
    add bx, [bzs_emap]
    mov bl, [es:bx]             ; the effect
    cmp bl, 0FFh
    je .r
    xor bh, bh
    shl bx, 1
    add bx, [bzs_fxt]
    mov si, [es:bx]             ; SI = its record
    mov di, bzs_fx              ; an idle slot...
    cmp word [di + F_PTR], 0
    je .slot
    cmp byte [bzs_nfx], 1
    je .low
    cmp word [di + F_SIZE + F_PTR], 0
    jne .two
    add di, F_SIZE
    jmp short .slot
.two:
    mov al, [di + F_PRIO]       ; ...else the lower priority, the older on a
    cmp al, [di + F_SIZE + F_PRIO] ; tie
    jb .low
    ja .sec
    mov ax, [di + F_SIZE + F_SEQ]
    sub ax, [di + F_SEQ]        ; (16-bit sequence, so a difference: the
    jns .low                    ; first is the older when this is >= 0)
.sec:
    add di, F_SIZE
.low:
    mov al, [es:si + 1]
    cmp [di + F_PRIO], al       ; that slot's priority above this one's: no
    ja .r
.slot:
    mov al, [es:si + 1]
    mov [di + F_PRIO], al
    mov al, [es:si]
    mov [di + F_INST], al
    xor ax, ax                  ; the transpose: strength >> sens, at most 7
    mov cl, [es:si + 2]
    cmp cl, 16
    jae .tr
    mov ax, dx
    shr ax, cl
    cmp ax, 7
    jbe .tr
    mov ax, 7
.tr:
    mov [di + F_TRANS], al
    shr al, 1
    mov [di + F_BOOST], al
    inc word [bzs_fxseq]
    mov ax, [bzs_fxseq]
    mov [di + F_SEQ], ax
    add si, 3
    mov [di + F_PTR], si
    mov byte [di + F_LEFT], 0
    mov word [di + F_OUT], 0
.r:
    ret

; -----------------------------------------------------------------------------
; THE SEQUENCER (Seq.music_tick, Seq.fx_tick)
; -----------------------------------------------------------------------------

; bzs_rstart - the song from its top (Seq.restart): its header copied, every
; channel and voice cleared.  A song only with a song part and the choice that
; plays music.  Preserves all.
bzs_rstart:
    push ax
    push cx
    push dx
    push si
    push di
    push es
    mov byte [bzs_live], 0
    push ds
    pop es
    mov di, bzs_v               ; the music's voices (0 - 5) cleared whole
    mov dx, 6                   ; (Seq.restart); the chip's shadows (H_*)
    xor ax, ax                  ; stay, and every voice is the chip's to
    cld                         ; catch up with (a key held goes up)
.v:
    mov cx, V_PITCH + 2
    rep stosb
    mov [di + V_KEYS - (V_PITCH + 2)], al
    mov [di + V_DYN - (V_PITCH + 2)], al
    add di, V_SIZE - (V_PITCH + 2)
    dec dx
    jnz .v
    mov [bzs_dynm], al
    or byte [bzs_dirty], 3Fh
    dec ax
    mov [bzs_next], ax
    cmp word [bzs_mseg], 0
    je .out
    mov al, [bzs_mode]
    cmp al, BZS_M_FX
    jae .out
    push ds
    mov si, BZMH_GLEN           ; +3 .. +17: glen, the groove, rows, the
    mov di, bzs_glen            ; order's length, loop, flags, then the three
    mov cx, BZMH_INST - BZMH_GLEN ; offsets
    mov ds, [bzs_mseg]
    cld
    rep movsb
    pop ds
    mov es, [bzs_mseg]
    mov di, bzs_ch
    mov si, BZMH_INST
    mov cx, 4
.ch:
    mov word [di + CH_PTR], 0
    mov byte [di + CH_WAIT], 0
    mov al, [es:si]
    mov [di + CH_INST], al
    mov byte [di + CH_VOL], 12
    mov byte [di + CH_SHAPE], 0
    mov byte [di + CH_SLUR], 0
    inc si
    add di, CH_SIZE
    loop .ch
    xor ax, ax
    mov [bzs_ord], al
    mov [bzs_row], al
    mov [bzs_gi], al
    mov [bzs_rtick], al
    mov [bzs_start], al
    mov word [bzs_nsub], 0
    mov byte [bzs_live], 1
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret


; bzs_run - CX sub-ticks stepped, then the arm's output: the one way the
; desktop and the bracket both sound.  bzs_tp is where tests/bonanza_sound.py
; stops a guest to hold its state to the model's (bzs_nsub sub-ticks of the
; song).  Clobbers AX, BX, CX, DX, SI, DI, ES.
bzs_run:
    call bzs_steps
    call bzs_output
bzs_tp:
    ret

; bzs_steps - CX sub-ticks (at most BZS_MAXT): the song's and the effects'.
; Clobbers AX, BX, CX, DX, SI, DI, ES.
bzs_steps:
    jcxz .r
    cmp cx, BZS_MAXT
    jbe .s
    mov cx, BZS_MAXT
.s:
    push cx
    cmp byte [bzs_live], 0
    je .fx
    inc word [bzs_nsub]
    call bzs_mtick
.fx:
    call bzs_fxtick
    pop cx
    loop .s
.r:
    ret

; bzs_pattern - the order row [bzs_ord]'s phrases into the channels (ES = the
; song).  Clobbers AX, BX, CX, SI, DI.
bzs_pattern:
    mov al, [bzs_ord]
    xor ah, ah
    shl ax, 1
    shl ax, 1
    mov si, ax
    add si, [bzs_ooff]
    mov di, bzs_ch
    mov cx, 4
.c:
    xor bx, bx
    mov bl, [es:si]
    cmp bl, 0FFh
    je .z
    shl bx, 1
    add bx, [bzs_poff]
    mov bx, [es:bx]
    jmp short .p
.z:
    xor bx, bx
.p:
    mov [di + CH_PTR], bx
    mov byte [di + CH_WAIT], 0
    mov bx, 4 + BZMH_INST       ; EVERY PATTERN STARTS FROM THE VOICE'S OWN
    sub bx, cx                  ; instrument, v12 and a single note: the
    mov al, [es:bx]             ; state the tool packs every phrase from
    mov [di + CH_INST], al
    mov byte [di + CH_VOL], 12
    mov byte [di + CH_SHAPE], 0
    mov byte [di + CH_SLUR], 0
    inc si
    add di, CH_SIZE
    loop .c
    ret

; bzs_mtick - one sub-tick of the song (Seq.music_tick).  Clobbers AX, BX, CX,
; DX, SI, DI, ES.
bzs_mtick:
    mov es, [bzs_mseg]
    cmp byte [bzs_start], 0
    jne .row
    mov byte [bzs_start], 1
    call bzs_pattern
.row:
    cmp byte [bzs_rtick], 0
    jne .age
    mov al, [bzs_row]           ; A ROW BEGINS: past the pattern's last, the
    cmp al, [bzs_rows]          ; next order row (the loop row after the last)
    jne .rd
    mov byte [bzs_row], 0
    mov al, [bzs_ord]
    inc ax
    cmp al, [bzs_olen]
    jb .o
    mov al, [bzs_loop]
.o:
    mov [bzs_ord], al
    call bzs_pattern
.rd:
    mov bx, bzs_ch              ; every channel whose wait has run out reads
    xor cl, cl                  ; to its next note or rest
.ch:
    cmp byte [bx + CH_WAIT], 0
    jne .dec
    push cx
    call bzs_read
    pop cx
.dec:
    cmp byte [bx + CH_WAIT], 255
    je .nx
    dec byte [bx + CH_WAIT]
.nx:
    add bx, CH_SIZE
    inc cx
    cmp cl, 4
    jb .ch
    mov bl, [bzs_gi]            ; the row's length, the groove's next count
    xor bh, bh
    mov al, [bzs_groove + bx]
    mov [bzs_rtick], al
    inc bx
    cmp bl, [bzs_glen]
    jb .g
    xor bl, bl
.g:
    mov [bzs_gi], bl
    inc byte [bzs_row]
.age:
    dec byte [bzs_rtick]
    mov ax, [bzs_nsub]          ; THE NOTES (Seq.music_tick's loop): a key
    cmp ax, [bzs_next]          ; goes up only at the deadline, and only a
    jne .dyn                    ; voice whose pitch moves is worked on
    call bzs_offs
.dyn:
    mov al, [bzs_dynm]
    or al, al
    jz .r
    mov es, [bzs_pseg]
    mov di, bzs_v
.d:
    shr al, 1
    jnc .dn
    push ax
    call bzs_vpitch
    pop ax
.dn:
    add di, V_SIZE
    or al, al
    jnz .d
.r:
    ret

; bzs_offs - the deadline: every key whose end is now goes up (its pitch
; stops moving, the chip has to catch up), and the next deadline is the
; nearest end of those still down.  Clobbers AX, BX, CX, DX, DI.
bzs_offs:
    mov bx, [bzs_nsub]
    mov dx, 0FFFFh              ; DX: the nearest end, as a distance
    mov di, bzs_v
    mov cx, 6
.o:
    cmp byte [di + V_ON], 0
    je .n
    mov ax, [di + V_END]
    sub ax, bx
    jnz .k
    mov byte [di + V_ON], 0     ; up
    mov al, [di + V_BIT]
    or [bzs_dirty], al
    not al
    and [bzs_dynm], al
    jmp short .n
.k:
    cmp ax, dx
    jae .n
    mov dx, ax
.n:
    add di, V_SIZE
    loop .o
    add dx, bx
    mov [bzs_next], dx
    ret

; bzs_read - channel BX (index CL) reads events to its next note or rest
; (Seq.read).  ES = the song.  Clobbers AX, CX, DX, SI, DI.
bzs_read:
    mov si, [bx + CH_PTR]
    or si, si
    jz .sil
.ev:
    mov al, [es:si]
    cmp al, 0FFh
    je .sil
    inc si
    test al, 80h
    jnz .cmd
    or al, al
    jz .rest
    mov ah, [es:si]             ; a NOTE: rows, then the gate
    mov [bx + CH_WAIT], ah
    mov ah, [es:si + 1]
    inc si
    inc si
    mov [bx + CH_PTR], si
    jmp bzs_key
.rest:
    mov al, [es:si]
    inc si
    mov [bx + CH_WAIT], al
    mov [bx + CH_PTR], si
    ret
.cmd:
    mov ah, al
    and ah, 0E0h
    and al, 1Fh
    cmp ah, 80h
    jne .shp
    mov [bx + CH_INST], al      ; 80 | i
    jmp .ev
.shp:
    cmp ah, 0A0h
    jne .vol
    mov [bx + CH_SHAPE], al     ; A0 | s
    jmp .ev
.vol:
    cmp al, 10h                 ; (D0: the low five bits are 10h)
    je .slur
    and al, 0Fh
    mov [bx + CH_VOL], al       ; C0 | v
    jmp .ev
.slur:
    mov byte [bx + CH_SLUR], 1
    jmp .ev
.sil:
    mov byte [bx + CH_WAIT], 255
    ret

; bzs_key - channel BX (index CL) keys note AL with gate AH (Seq.key): the
; chord's shape fans it to three voices.  Clobbers AX, CX, DX, SI, DI.
bzs_key:
    mov dl, [bx + CH_SLUR]
    mov byte [bx + CH_SLUR], 0
    cmp cl, 2                   ; the chord on the speaker: never played by
    jne .k                      ; the fold, so never keyed (Seq.key)
    cmp byte [bzs_arm], BZS_A_FM
    je .k
    ret
.k:
    mov ch, cl                  ; the channel's first voice: 0, 1, 2, 5
    cmp cl, 3
    jne .v
    mov ch, 5
.v:
    push ax
    mov al, ch
    mov ah, V_SIZE
    mul ah
    add ax, bzs_v
    mov di, ax
    pop ax
    call bzs_kv
    cmp cl, 2                   ; the chord: two more, at the shape's
    jne .r                      ; intervals (0: no note)
    push ax
    mov al, [bx + CH_SHAPE]
    xor ah, ah
    shl ax, 1
    mov si, ax
    add si, [bzs_soff]
    mov si, [es:si]             ; the two intervals
    pop ax
    mov dh, al                  ; DH = the root, AH the gate still
    mov cx, si
    add di, V_SIZE
    mov al, cl
    or al, al
    jz .a
    add al, dh
.a:
    call bzs_kv
    add di, V_SIZE
    mov al, ch
    or al, al
    jz .b
    add al, dh
.b:
    jmp bzs_kv
.r:
    ret

; bzs_kv - voice DI keys note AL (0: the voice off) with gate AH, slurred when
; DL; channel BX's instrument and volume (Seq.key).  Its stamps, its record,
; whether its pitch moves (the sound part's instrument), the deadline, and the
; chip told.  Preserves all but the flags.
bzs_kv:
    push ax
    push cx
    push si
    push es
    or al, al
    jnz .on
    cmp byte [di + V_ON], 0     ; (a chord's missing note: its voice up)
    je .out
    mov byte [di + V_ON], 0
    mov al, [di + V_BIT]
    or [bzs_dirty], al
    not al
    and [bzs_dynm], al
    jmp .out
.on:
    mov [di + V_NOTE], al
    mov cl, [bx + CH_VOL]
    mov [di + V_VOL], cl
    mov cl, [bx + CH_INST]
    mov [di + V_INST], cl
    xor ch, ch                  ; its record, once (bzs_vpitch, bzs_spk)
    shl cx, 1
    shl cx, 1
    shl cx, 1
    shl cx, 1
    add cx, [bzs_ins]
    mov [di + V_IREC], cx
    mov si, cx
    inc byte [di + V_KEYS]
    mov cx, [bzs_nsub]          ; the end: now + the gate
    mov al, ah
    xor ah, ah
    add ax, cx
    mov [di + V_END], ax
    sub ax, cx                  ; ...the deadline if it is the nearest
    mov cx, [bzs_next]
    sub cx, [bzs_nsub]
    cmp ax, cx
    jae .dl
    add ax, [bzs_nsub]
    mov [bzs_next], ax
.dl:
    or dl, dl                   ; slurred onto a sounding voice: re-pitched,
    jz .new                     ; not re-keyed
    cmp byte [di + V_ON], 0
    jne .pit
.new:
    mov byte [di + V_ON], 1
    mov byte [di + V_RETRIG], 1
    mov byte [di + V_MPOS], 0
    mov ax, [bzs_nsub]
    mov [di + V_T0], ax
.pit:
    mov ah, [di + V_NOTE]       ; the note's own pitch; a macro or a vibrato
    xor al, al                  ; moves it from bzs_mtick's loop, this
    mov [di + V_PITCH], ax      ; sub-tick included
    mov al, [di + V_BIT]
    or [bzs_dirty], al
    mov ah, al
    not ah
    and [bzs_dynm], ah
    mov byte [di + V_DYN], 0
    mov es, [bzs_pseg]          ; its pitch moves only under a macro (no
    cmp byte [es:si + BZI_MAC], 0FFh ; vibrato is written: 128.20.4)
    je .out
    mov byte [di + V_DYN], 1
    or [bzs_dynm], al
.out:
    pop es
    pop si
    pop cx
    pop ax
    ret

; bzs_vpitch - a voice whose pitch moves, DI, this sub-tick: the note and its
; instrument's macro at the macro's place.  A macro run out and held takes the
; voice out of bzs_dynm.  ES = the sound part.  Clobbers AX, BX, DX, SI.
bzs_vpitch:
    mov si, [di + V_IREC]       ; SI = the instrument
    mov dh, [di + V_NOTE]
    xor dl, dl                  ; DX = the pitch
    mov bl, [es:si + BZI_MAC]
    xor bh, bh
    add bx, [bzs_mac]
    mov al, [di + V_MPOS]       ; the macro's semitones at its place
    xor ah, ah
    push bx
    add bx, ax
    mov ah, [es:bx + 2]
    pop bx
    xor al, al
    add dx, ax                  ; (AH signed: AX = semitones x 256)
    mov al, [di + V_MPOS]
    inc ax
    cmp al, [es:bx]             ; past its length: the loop, else the last
    jne .mp
    mov al, [es:bx + 1]
    cmp al, [es:bx]
    jb .mp
    mov al, [es:bx]
    dec ax
    cmp al, [di + V_MPOS]       ; a macro run out and held: the pitch moves
    jne .mp                     ; no more
    mov byte [di + V_DYN], 0
    mov ah, [di + V_BIT]
    not ah
    and [bzs_dynm], ah
.mp:
    mov [di + V_MPOS], al
    xchg ax, dx
    call bzs_clamp
    cmp ax, [di + V_PITCH]
    je .r
    mov [di + V_PITCH], ax
    mov al, [di + V_BIT]
    or [bzs_dirty], al
.r:
    ret

; bzs_clamp - pitch AX into C0 .. G9 less a step: 12 x 256 .. 127 x 256 - 1
bzs_clamp:
    cmp ax, 12 * 256
    jge .hi
    mov ax, 12 * 256
.hi:
    cmp ax, 127 * 256 - 1
    jle .r
    mov ax, 127 * 256 - 1
.r:
    ret

; bzs_fxtick - one sub-tick of every effect slot (Seq.fx_tick).  Clobbers AX,
; BX, CX, DX, SI, DI, ES.
bzs_fxtick:
    mov ax, [bzs_fx + F_PTR]    ; both slots idle (the usual case): nothing
    or ax, [bzs_fx + F_SIZE + F_PTR]
    jz .r
    cmp word [bzs_pseg], 0
    je .r
    mov es, [bzs_pseg]
    mov di, bzs_fx
    mov cl, [bzs_nfx]
    xor ch, ch
.s:
    push cx
    call bzs_fx1
    pop cx
    add di, F_SIZE
    loop .s
.r:
    ret

bzs_fx1:
    mov si, [di + F_PTR]
    or si, si
    jz .r
    mov al, 40h                 ; its AdLib voice, 6 or 7, has to catch up
    cmp di, bzs_fx
    je .b
    shl al, 1
.b:
    or [bzs_dirty], al
    cmp byte [di + F_LEFT], 0
    jne .run
    mov al, [es:si]             ; a SEGMENT: its sub-ticks, 0 the end
    or al, al
    jnz .seg
    mov word [di + F_PTR], 0
    mov word [di + F_OUT], 0
.r:
    ret
.seg:
    mov [di + F_LEFT], al
    mov al, [es:si + 1]         ; the note: 0 silent, bit 7 legato
    mov byte [di + F_REST], 1
    mov ah, al
    and ah, 7Fh
    jz .sl
    mov byte [di + F_REST], 0
    add ah, [di + F_TRANS]
    mov [di + F_PITCH + 1], ah
    mov byte [di + F_PITCH], 0
    test al, 80h
    jnz .sl
    mov byte [di + F_RETRIG], 1
.sl:
    inc byte [di + F_SEGN]
    mov al, [es:si + 2]         ; the slide, 1/16 semitone: x 16
    cbw
    mov cl, 4
    shl ax, cl
    mov [di + F_SLIDE], ax
    mov al, [es:si + 3]         ; the volume, with the strength's boost, x 16
    add al, [di + F_BOOST]
    cmp al, 15
    jbe .v
    mov al, 15
.v:
    mov [di + F_SVOL], al
    mov cl, 4
    shl al, cl
    mov [di + F_VOL], al
    mov ax, [es:si + 4]
    mov [di + F_DECAY], ax      ; F_DECAY and F_JIT
    add si, 6
    mov [di + F_PTR], si
.run:
    xor ax, ax                  ; this sub-tick's output: silent on a rest or
    cmp byte [di + F_REST], 0   ; a volume under 1
    jne .out
    cmp byte [di + F_VOL], 16
    jb .out
    mov ax, [di + F_PITCH]
    mov cl, [di + F_JIT]
    or cl, cl
    jz .clamp
    push ax
    call bzs_rand
    and al, cl                  ; ((r & jit) - (jit >> 1)) x 16
    shr cl, 1
    sub al, cl
    cbw
    mov cl, 4
    shl ax, cl
    pop dx
    add ax, dx
.clamp:
    call bzs_clamp
.out:
    mov [di + F_OUT], ax
    mov ax, [di + F_PITCH]      ; then the slide and the decay
    add ax, [di + F_SLIDE]
    call bzs_clamp
    mov [di + F_PITCH], ax
    mov al, [di + F_VOL]
    sub al, [di + F_DECAY]
    jnb .dk
    xor al, al
.dk:
    mov [di + F_VOL], al
    dec byte [di + F_LEFT]
    ret

; bzs_rand - the effects' 16-bit Galois LFSR (Seq.rand): AL = its low byte.
; Clobbers AX.
bzs_rand:
    mov ax, [bzs_lfsr]
    shr ax, 1
    jnc .n
    xor ax, 0B400h
.n:
    mov [bzs_lfsr], ax
    ret

; -----------------------------------------------------------------------------
; THE ARMS (128.20.4)
; -----------------------------------------------------------------------------

; bzs_output - what the arm open makes of this frame's state.  Clobbers AX,
; BX, CX, DX, SI, DI, ES.
bzs_output:
    cmp word [bzs_pseg], 0
    je .r
    mov es, [bzs_pseg]
    mov al, [bzs_arm]
    cmp al, BZS_A_SPK
    je bzs_spk
    cmp al, BZS_A_FM
    je bzs_fm
.r:
    ret

; bzs_spk - THE SPEAKER: one voice, folded (Seq.spk_choice, Seq.spk_out): an
; effect (its silence too), else a drum's blip, else the lead, else - with
; the song's flag - the bass.  A tone only when the Hz changes, lasting the
; source's sub-ticks left in system ticks plus one.  ES = the sound part.
bzs_spk:
    mov di, bzs_fx
    cmp word [di + F_PTR], 0
    je .mus
    mov ax, [di + F_OUT]
    or ax, ax
    jz .off
    mov cl, [di + F_LEFT]
    xor ch, ch
    inc cx
    mov bl, [di + F_SEGN]       ; the token: 1, the segment
    mov bh, 1
    jmp short .on
.mus:
    cmp byte [bzs_live], 0
    je .off
    mov di, bzs_v + 5 * V_SIZE  ; the drum: its instrument's blip, while the
    cmp byte [di + V_ON], 0     ; note is no older than it
    je .lead
    mov si, [di + V_IREC]
    mov cl, [es:si + BZI_SPK]
    and cx, 7Fh
    jcxz .lead
    mov ax, [bzs_nsub]          ; younger than its blip: now - t0 < spk, and
    sub ax, [di + V_T0]         ; spk - (now - t0) left
    cmp ax, cx
    jae .lead
    sub cx, ax
    mov bh, 2
    jmp short .vk
.lead:
    mov di, bzs_v               ; the lead
    mov bh, 3
    cmp byte [di + V_ON], 0
    jne .vo
    test byte [bzs_flags], 1    ; the BASS, where the song says so and the
    jz .off                     ; lead has been silent past an articulation
    mov ax, [bzs_nsub]          ; gap: now - its end >= 2
    sub ax, [di + V_END]
    cmp ax, 2
    jb .off
    add di, V_SIZE
    mov bh, 4
    cmp byte [di + V_ON], 0
    je .off
.vo:
    mov cx, [di + V_END]        ; its gate left: end - now
    sub cx, [bzs_nsub]
.vk:
    mov bl, [di + V_KEYS]       ; the token: the source, its note
    mov ax, [di + V_PITCH]
.on:
    cmp ax, [bzs_spit]          ; the same pitch from the same note: nothing
    jne .send
    cmp bx, [bzs_stok]
    je .r
.send:
    mov [bzs_spit], ax
    mov [bzs_stok], bx
    push cx
    call bzs_hz                 ; AX = Hz (only for a tone that is sent)
    pop cx
    mov [bzs_shz], ax
    push ax                     ; the duration: (left + 2) / 3 + 1 ticks
    mov ax, cx
    inc ax
    inc ax
    mov cl, 3
    div cl
    xor ah, ah
    inc ax
    mov cx, ax
    pop ax
    jmp short .tone
.off:
    xor ax, ax
    cmp [bzs_spit], ax
    je .r
    mov [bzs_spit], ax
    mov [bzs_shz], ax
    xor cx, cx
.tone:
    mov dl, BZS_PRI
    call OSAPI_SND_TONE
.r:
    ret

; bzs_hz - pitch AX -> AX = Hz (pitch_hz): ONE division for the octave and
; the semitone, the fraction interpolated in the top octave's table (C7..B7,
; B's next a C7 doubled), then shifted to the octave, rounded down there, and
; kept in 19 .. 20,000.  DIV, not AAM 12: a V20 ignores AAM's base.  ES = the
; sound part.  Clobbers BX, CX, DX.
bzs_hz:
    mov dl, al                  ; DL = the fraction
    mov bx, [bzs_hzt]
    call bzs_tab                ; AX = the entry, interpolated; CL = the octave
    sub cl, 8
    jb .dn
    shl ax, cl
    jmp short .c
.dn:
    neg cl                      ; (h >> (s - 1) + 1) >> 1: rounded
    dec cl
    shr ax, cl
    inc ax
    shr ax, 1
.c:
    cmp ax, 19
    jae .h
    mov ax, 19
.h:
    cmp ax, 20000
    jbe .r
    mov ax, 20000
.r:
    ret

; bzs_tab - note AH, fraction DL, in the octave table at ES:BX: AX = its
; entry interpolated toward the next semitone's (B's next: C's doubled), CL =
; the note's octave.  Clobbers BX, CH, DX.
bzs_tab:
    mov al, ah
    xor ah, ah
    mov cl, 12
    div cl                      ; AL = the octave, AH = the semitone
    mov cx, ax                  ; CL = the octave, CH = the semitone
    mov al, ah
    xor ah, ah
    shl ax, 1
    add bx, ax
    mov ax, [es:bx]             ; this semitone's entry
    or dl, dl
    jz .r
    push ax
    cmp ch, 11
    jne .nx
    sub bx, 22
    mov ax, [es:bx]
    shl ax, 1                   ; B: the next is C, an octave up
    jmp short .d
.nx:
    mov ax, [es:bx + 2]
.d:
    pop bx                      ; BX = this entry
    sub ax, bx
    xor dh, dh
    mul dx                      ; (next - this) x the fraction
    mov al, ah
    mov ah, dl                  ; >> 8
    add ax, bx
.r:
    ret

; bzs_fnum - pitch AX -> AL = A0h, AH = B0h without the key (pitch_opl): the
; F-number interpolated in C4..B4's, the block the octave less one, kept in
; 0 .. 7.  ES = the sound part.  Clobbers BX, CX, DX.
bzs_fnum:
    mov dl, al
    mov bx, [bzs_opt]
    call bzs_tab                ; AX = f, CL = the octave
    dec cl                      ; the block
    jns .hi
    shr ax, 1                   ; (octave 0: block 0, an octave down)
    xor cl, cl
    jmp short .k
.hi:
    cmp cl, 7
    jbe .k
    sub cl, 7
    shl ax, cl
    mov cl, 7
    cmp ax, 1023
    jbe .k
    mov ax, 1023
.k:
    shl cl, 1
    shl cl, 1
    or ah, cl                   ; AH = block << 2 | f >> 8, AL = f's low 8
    ret

; bzs_fm - THE ADLIB: the logical voices the chip has not caught up with
; (bzs_dirty), in the serving order, against the shadows of the CHANNEL each
; plays on; the registers that differ onto the batch, capped (Chip.voice_regs);
; the batch sent.  ES = the sound part.
bzs_fm:
    mov word [bzs_fmn], 0
    mov si, bzs_order
.v:
    lodsb
    cmp al, 0FFh
    je .send
    mov bl, al                  ; only a voice the chip has not caught up with
    xor bh, bh
    mov ah, [bzs_bits + bx]
    test [bzs_dirty], ah
    jz .v
    push si
    push ax
    call bzs_fmv
    pop ax
    pop si
    jc .send                    ; (the cap: it and the rest stay dirty)
    not ah
    and [bzs_dirty], ah
    jmp short .v
.send:
    mov cx, [bzs_fmn]
    jcxz .r
    push es
    push ds
    pop es
    mov si, bzs_fmb
    mov bh, DRVC_SOUND
    mov bl, SNDV_OPLW
.call:                          ; (bonanzasound prices the driver's batch)
    call OSAPI_DRV_CALL
.back:
    pop es
    jnc .r
    mov byte [bzs_arm], BZS_A_SPK ; the claim is gone: the speaker from here
    mov word [bzs_shz], 0
    mov word [bzs_spit], 0
.r:
    ret

bzs_order:  db 6, 0, 5, 1, 2, 3, 4, 0FFh ; the effect, lead, drums, bass, chord
bzs_bits:   db 1, 2, 4, 8, 10h, 20h, 40h
bzs_slot:   db 0, 1, 2, 8, 9, 10, 16, 17, 18
bzs_opreg:  db 20h, 40h, 60h, 80h, 0E0h

; bzs_fmv - logical voice AL (0 - 5 the music's, 6 the effect) onto the batch,
; on its channel: its own for 0 - 4, 5 or (an `alt` drum) 6 for the drums, 7
; for the effect (Chip.voice_regs).  CF = 1: the cap is reached and the
; serving stops (this voice and the rest keep their state for the next
; frame).  ES = the sound part.  Clobbers AX, BX, CX, DX, SI, DI.
bzs_fmv:
    cmp al, 6
    jb .mus
    mov bx, bzs_fx              ; THE EFFECT: on while running and sounding
    xor ch, ch
    cmp word [bx + F_PTR], 0
    je .f0
    cmp word [bx + F_OUT], 0
    je .f0
    inc ch
.f0:
    mov dx, [bx + F_OUT]
    mov al, [bx + F_INST]
    mov ah, 16
    mul ah
    add ax, [bzs_ins]
    mov si, ax
    mov al, [bx + F_SVOL]       ; its SEGMENT's level: the chip decays it
    lea bx, [bx + F_RETRIG]
    mov cl, 7
    jmp short .want
.mus:
    mov cl, al                  ; CL = the channel: the voice's own, but
    mov ah, V_SIZE
    mul ah
    add ax, bzs_v
    mov bx, ax
    mov ch, [bx + V_ON]
    mov dx, [bx + V_PITCH]
    mov si, [bx + V_IREC]
    cmp cl, 5                   ; ...an `alt` drum's on 6
    jne .vv
    test byte [es:si + BZI_SPK], 80h
    jz .vv
    inc cx
.vv:
    mov al, [bx + V_VOL]
    lea bx, [bx + V_RETRIG]
.want:                          ; CH on, DX the pitch, ES:SI the instrument,
    push bx                     ; AL the volume, CL the channel, [SP] -> the
    push ax                     ; retrigger flag
    mov al, V_SIZE
    mul cl
    add ax, bzs_v
    mov di, ax                  ; DI = the CHANNEL's shadows
    or ch, ch                   ; ANOTHER PATCH: written first, as much of it
    jz .cap                     ; as the cap leaves room for this frame; a
    mov al, [es:si + BZI_PID]   ; patch not finished stops the serving (the
    cmp al, [di + H_INST]       ; note follows it, a frame or so late)
    je .cap
    cmp al, [di + H_PPID]
    je .more
    mov [di + H_PPID], al
    mov byte [di + H_PPOS], 0
.more:
    mov ah, BZS_FMCAP
    sub ah, [bzs_fmn]
    mov al, 11
    sub al, [di + H_PPOS]
    cmp ah, al
    jbe .k
    mov ah, al
.k:
    mov al, [di + H_PPOS]       ; AL = from, AH = how many
    add [di + H_PPOS], ah
    call bzs_patch
    cmp byte [di + H_PPOS], 11
    jb .stop
    mov al, [di + H_PPID]       ; written whole: the channel holds it
    mov [di + H_INST], al
    mov byte [di + H_TL], 0FFh
    mov byte [di + H_PPID], 0FFh
.cap:
    mov bx, [bzs_fmn]           ; THE CAP: the note needs at most 4 more
    add bx, 4
    cmp bx, BZS_FMCAP
    jbe .go
.stop:
    pop ax
    pop bx
    stc
    ret
.go:
    pop ax
    mov ah, al                  ; AH = the volume
    push dx                     ; the pitch
    or ch, ch
    jz .off
.tl:
    mov dl, ah                  ; DL = the carrier's 40h: its TL + (15 - vol)
    mov al, [es:si + BZI_CAR40] ; x 2, at most 63, under its KSL bits
    mov ah, al
    and ah, 0C0h
    and al, 3Fh
    mov dh, 15
    sub dh, dl
    shl dh, 1
    add al, dh
    cmp al, 63
    jbe .t6
    mov al, 63
.t6:
    or al, ah
    mov dl, al
    pop ax                      ; AX = the pitch
    pop si                      ; SI -> the retrigger flag
    push si
    cmp byte [si], 0            ; struck again while keyed: the key off first
    je .pitch
    test byte [di + H_B0], 20h
    jz .pitch
    push ax
    and byte [di + H_B0], 0DFh
    mov ah, [di + H_B0]
    mov al, 0B0h
    add al, cl
    call bzs_put
    pop ax
.pitch:
    cmp ax, [di + H_PITCH]      ; the same pitch: the registers it made
    je .same
    mov [di + H_PITCH], ax
    push cx
    push dx
    call bzs_fnum
    pop dx
    pop cx
    jmp short .key
.same:
    mov al, [di + H_A0]
    mov ah, [di + H_B0]
.key:
    or ah, 20h
    cmp al, [di + H_A0]         ; A0h
    je .t
    mov [di + H_A0], al
    push ax
    mov ah, al
    mov al, 0A0h
    add al, cl
    call bzs_put
    pop ax
.t:
    cmp dl, [di + H_TL]         ; the carrier's 40h
    je .b
    mov [di + H_TL], dl
    push ax
    push bx
    mov al, cl
    mov bx, bzs_slot
    xlatb
    add al, 43h
    mov ah, dl
    call bzs_put
    pop bx
    pop ax
.b:
    cmp ah, [di + H_B0]         ; B0h: the key, the block, F's top 2
    je .clr
    mov [di + H_B0], ah
    mov al, 0B0h
    add al, cl
    call bzs_put
.clr:
    pop si
    mov byte [si], 0
    clc
    ret
.off:                           ; OFF: the key released, if it is held (the
    pop dx                      ; retrigger flag is left as it is)
    pop si
    test byte [di + H_B0], 20h
    jz .r
    and byte [di + H_B0], 0DFh
    mov ah, [di + H_B0]
    mov al, 0B0h
    add al, cl
    call bzs_put
.r:
    clc
    ret

; bzs_patch - AH of channel CL's patch registers from the AL-th, the
; instrument's at ES:SI, in SOUND.DRV's order: the modulator's five (0 - 4),
; the carrier's five (5 - 9), C0h (10) - the carrier's 20h with the VIB bit
; where the instrument has a vibrato, the chip's own (Chip.patch).  Preserves
; all but the flags.
bzs_patch:
    push ax
    push bx
    push cx
    push dx
    push si
    or ah, ah
    jz .out
    mov dh, ah                  ; DH = how many
    mov dl, al                  ; DL = the index
    mov al, cl
    mov bx, bzs_slot
    xlatb
    mov ch, al                  ; CH = the modulator's slot
.r:
    mov bl, dl
    xor bh, bh
    mov ah, [es:si + bx]        ; the value
    cmp dl, 10
    jb .op
    mov al, 0C0h                ; C0h
    add al, cl
    jmp short .w
.op:
    mov al, ch                  ; the operator's slot: the carrier's 3 on
    cmp dl, 5
    jb .md
    add al, 3
    sub bl, 5
    jnz .md
    cmp byte [es:si + BZI_VDP], 0 ; the carrier's 20h: its VIB
    je .md
    or ah, 40h
.md:
    add al, [bzs_opreg + bx]
.w:
    call bzs_put
    inc dl
    dec dh
    jnz .r
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; bzs_put - register AL, value AH onto the batch.  Preserves all but the flags.
bzs_put:
    push di
    mov di, [bzs_fmn]
    cmp di, BZS_FMBUF
    jae .r
    inc word [bzs_fmn]
    shl di, 1
    mov [bzs_fmb + di], ax
.r:
    pop di
    ret
