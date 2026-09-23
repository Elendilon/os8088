; =============================================================================
; timus.inc - TITHE's MUSIC SEQUENCER (SPEC.md 97.10, TITHE-PLAN 13)
;
; ONE SCORE, TWO RENDERERS. A song is four channels - LEAD, BASS, CHORD, DRUM -
; packed by tools/os88tithemus.py into the MUSIC part (part 1). The SPEAKER
; plays the lead and nothing else, through OSAPI_SND_TONE; the FM arm plays
; all four on six OPL2 voices through OSAPI_SND_FM - the lead on 0, the bass
; on 1, the chord's up to three notes on 2..4, the drums on 5 - leaving 6 and
; 7 for effects and 8 to the kernel's tone tier (SPEC.md 34.8). The arm is
; chosen from OSAPI_SND_CAPS when a song STARTS, and never by calling the FM
; slot to see: with no driver that call wedges the machine (TITHE-PLAN 13.5).
;
; IT RUNS ON THE WORKER, BESIDE THE WHEEL (TITHE-PLAN 13.6) - tm_run is the
; first thing each pass does, before the frame and outside the gfx lock, so a
; frame that waits for the lock never holds a note up. It steps once per
; ELAPSED TICK: a pass that comes late steps twice, and a STALL - three ticks
; or more, a relayout or a region move - steps ONCE, because a sequencer that
; sprints to catch up plays the notes it missed as a smear. The music pauses
; instead, and every speaker tone carries a DURATION, so a worker that stops
; can never leave the speaker droning (snd_tick expires it, SPEC.md 34.3).
;
; THE UI TASK ONLY POSTS. `M` and `S` write [tm_req] and the worker services
; it: every sound call is made from ONE task, because two tasks of the same
; instance interleaving OPL address/data pairs would corrupt a register write
; that ownership (SPEC.md 34.1) cannot see. The post is one byte and the take
; is an `xchg`, so a key between the read and the clear cannot be lost.
;
; tools/os88tithemus.py carries the same sequencer in Python, reading the same
; packed bytes - its `Seq` is this file's model and SPEC.md 97.10.4 is the
; order both keep. tests/tithemus.py holds the guest to it tick for tick.
; =============================================================================

TM_PART     equ 1                   ; the MUSIC part's index (tithe.asm)
TM_OFF      equ 0xFF                ; [tm_song]: nothing is playing
TM_NOREQ    equ 0xFE                ; [tm_req]: nothing is asked for
TM_PRIO     equ 0x20                ; under the package default 0x40, so any
                                    ; effect preempts the music (TITHE-PLAN 13.8)
TM_NCH      equ 4
TM_CHORD    equ 2                   ; the channel whose notes are chords
TM_STALL    equ 3                   ; ticks late that count as a stall

TMC_PTR     equ 0                   ; dw where the phrase has got to (0: silent)
TMC_WAIT    equ 2                   ; rows until its next event
TMC_NOTE    equ 3                   ; what sounds, 0 = nothing
TMC_INST    equ 4
TMC_GATE    equ 5                   ; ticks it has left to sound
TMC_SHAPE   equ 6                   ; the chord shape
TMC_SLUR    equ 7                   ; the next note slurs into this one
TMC_FRESH   equ 8                   ; keyed THIS tick: the gate starts next
TMC_AGE     equ 9                   ; ticks since the note began
TMC_LASTF   equ 10                  ; dw the speaker's last frequency
TMC_SIZE    equ 12

; -----------------------------------------------------------------------------
; tm_post - ask for a song (AL = index) or silence (AL = TM_OFF). UI task.
; Preserves every register.
; -----------------------------------------------------------------------------
tm_post:
    mov [tm_req], al
    ret

; -----------------------------------------------------------------------------
; tm_title - the window says what plays and on which arm. UI task, from a key.
; Preserves every register.
; -----------------------------------------------------------------------------
tm_title:
    push ax
    push bx
    push dx
    push si
    push di
    mov di, tm_tbuf
    mov si, ti_ttl
    cmp byte [tm_sel], TM_OFF
    je .last
    mov bl, [tm_sel]
    xor bh, bh
    shl bx, 1
    mov si, [tm_names + bx]
    call .copy
    call OSAPI_SND_CAPS             ; what the worker will find - the same
    mov si, tm_s_spk                ; question, asked the same way
    test al, SND_CAP_FM
    jz .last
    mov si, tm_s_fm
    cmp byte [tm_spkonly], 0
    je .last
    mov si, tm_s_spkf
.last:
    call .copy
    mov byte [di], 0
    mov bx, [ti_win]
    mov ax, tm_tbuf
    call OSAPI_WM_TITLE
    pop di
    pop si
    pop dx
    pop bx
    pop ax
    ret
.copy:
    lodsb
    or al, al
    jz .cdone
    mov [di], al
    inc di
    jmp short .copy
.cdone:
    ret

tm_s_fm:    db ' [FM]', 0
tm_s_spk:   db ' [speaker]', 0
tm_s_spkf:  db ' [one voice; S for FM]', 0
tm_tbuf:    times 64 db 0

; -----------------------------------------------------------------------------
; tm_run - the worker's step. No lock held, no lock taken.
; Preserves every register.
; -----------------------------------------------------------------------------
tm_run:
    push ax
    push bx
    push cx
    push es
    mov byte [tm_busy], 1           ; for an OBSERVER: a machine paused while
                                    ; this is set is mid-tick (tests/tithemus.py)
    mov al, TM_NOREQ                ; TAKE the post and clear it in one
    xchg al, [tm_req]               ; instruction: a key cannot land between
    cmp al, TM_NOREQ
    je .noreq
    call tm_start
.noreq:
    cmp byte [tm_song], TM_OFF
    je .out
    call OSAPI_GET_TICKS
    mov bx, ax
    sub ax, [tm_last]
    mov [tm_last], bx
    jz .out                         ; the tick has not turned over
    cmp ax, TM_STALL
    jb .n
    mov ax, 1                       ; A STALL: pause, never sprint
.n:
    mov cx, ax
    call tm_seg
    jc .out
.t:
    call tm_tick
    loop .t
.out:
    mov byte [tm_busy], 0
    pop es
    pop cx
    pop bx
    pop ax
    ret

; tm_seg - ES = the MUSIC part, read at the point of use (a part's segment is
; not a thing to cache: the region may have moved, SPEC.md 66). CF = 1 absent.
tm_seg:
    push ax
    mov al, TM_PART
    call op_seg
    or ax, ax
    jz .none
    mov es, ax
    pop ax
    clc
    ret
.none:
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; tm_start - stop what plays, then start song AL (or stay silent for TM_OFF)
; -----------------------------------------------------------------------------
tm_start:
    push ax
    push bx
    push cx
    push dx                         ; OSAPI_SND_CAPS answers in DX too
    push si
    push di
    push es
    call tm_silence
    cmp al, TM_OFF
    je .out
    cmp al, TM_NSONG
    jae .out
    mov ah, al
    call tm_seg
    jc .out
    mov [tm_song], ah
    ; THE ARM, asked of the caps and never of the FM slot itself
    call OSAPI_SND_CAPS
    xor bl, bl
    test al, SND_CAP_FM
    jz .arm
    cmp byte [tm_spkonly], 0
    jne .arm
    inc bl
.arm:
    mov [tm_arm], bl
    ; the song's header into our own bytes
    mov bl, [tm_song]
    xor bh, bh
    shl bx, 1
    mov si, [es:TMP_SONGS + bx]
    mov di, tm_hdr
    mov cx, TMS_PTAB + 2
.hdr:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    loop .hdr
    mov ax, [es:TMP_FREQ]
    mov [tm_freq], ax
    mov ax, [es:TMP_INST]
    mov [tm_insts], ax
    mov ax, [es:TMP_MACRO]
    mov [tm_macros], ax
    mov ax, [es:TMP_SHAPE]
    mov [tm_shapes], ax
    ; every channel empty, the grid at its start
    mov di, tm_ch
    mov cx, TM_NCH * TMC_SIZE
    xor al, al
.clr:
    mov [di], al
    inc di
    loop .clr
    mov byte [tm_ord], 0
    mov byte [tm_row], 0
    mov byte [tm_tleft], 0
    mov byte [tm_gi], 0
    mov word [tm_ticks], 0
    call tm_pattern
    call OSAPI_GET_TICKS            ; the first tick is NOW
    mov [tm_last], ax
    call tm_tick
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tm_silence - whatever is sounding stops, and [tm_song] = TM_OFF
; Preserves every register.
; -----------------------------------------------------------------------------
tm_silence:
    push ax
    push bx
    push cx
    cmp byte [tm_song], TM_OFF
    je .clear
    cmp byte [tm_arm], 0
    jne .fm
    xor ax, ax                      ; the speaker, off - at OUR priority, so an
    xor cx, cx                      ; effect that owns it is left alone
    call tm_tone
    jmp short .clear
.fm:
    mov al, 3                       ; verb 3: every voice off AND every claim
    call OSAPI_SND_FM               ; given back
.clear:
    mov byte [tm_song], TM_OFF
    xor bx, bx
.v:
    mov byte [tm_fmpatch + bx], 0xFF
    mov byte [tm_fmkeyed + bx], 0
    inc bx
    cmp bx, TM_NVOICE
    jb .v
    mov bx, tm_ch
.c:
    mov byte [bx + TMC_NOTE], 0
    add bx, TMC_SIZE
    cmp bx, tm_ch + TM_NCH * TMC_SIZE
    jb .c
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tm_tick - ONE TICK of the song (SPEC.md 97.10.4). ES = the part.
; Preserves every register.
;
; A row begins when the last one's ticks are spent: the pattern turns over if
; this was its last row, every channel whose wait has run out reads its next
; event, and the groove says how many ticks the new row lasts. Then every
; sounding note ages a tick - its gate runs down and the speaker's lead takes
; its macro and vibrato.
; -----------------------------------------------------------------------------
tm_tick:
    push ax
    push bx
    push di
    cmp byte [tm_tleft], 0
    jne .ticks
    mov al, [tm_row]
    cmp al, [tm_rows]
    jb .row
    mov byte [tm_row], 0            ; the pattern is over: the next order row
    mov al, [tm_ord]
    inc al
    cmp al, [tm_ordlen]
    jb .ord
    mov al, [tm_loop]
.ord:
    mov [tm_ord], al
    call tm_pattern
.row:
    xor bx, bx
    mov di, tm_ch
.ev:
    cmp byte [di + TMC_WAIT], 0
    jne .dec
    call tm_event
.dec:
    dec byte [di + TMC_WAIT]
    add di, TMC_SIZE
    inc bx
    cmp bx, TM_NCH
    jb .ev
    inc byte [tm_row]
    mov bl, [tm_gi]                 ; the groove: this row's ticks
    xor bh, bh
    mov al, [tm_groove + bx]
    mov [tm_tleft], al
    inc bl
    cmp bl, [tm_glen]
    jb .g
    xor bl, bl
.g:
    mov [tm_gi], bl
.ticks:
    dec byte [tm_tleft]
    xor bx, bx
    mov di, tm_ch
.ct:
    call tm_chtick
    add di, TMC_SIZE
    inc bx
    cmp bx, TM_NCH
    jb .ct
    inc word [tm_ticks]
    pop di
    pop bx
    pop ax
    ret

; tm_pattern - point every channel at its phrase for order row [tm_ord]
; ES = the part. Preserves every register.
tm_pattern:
    push ax
    push bx
    push si
    push di
    mov al, [tm_states]
    add al, 3                       ; an order row: bass, chord, drum, leads
    mul byte [tm_ord]
    add ax, [tm_order]
    mov si, ax
    mov bl, [tm_state]              ; the lead the state names (TITHE-PLAN
    cmp bl, [tm_states]             ; 13.4) - a title has one
    jb .st
    xor bl, bl
.st:
    xor bh, bh
    mov al, [es:si + bx + 3]
    mov di, tm_ch                   ; channel 0, the LEAD
    call tm_phrase
    mov al, [es:si]
    add di, TMC_SIZE
    call tm_phrase
    mov al, [es:si + 1]
    add di, TMC_SIZE
    call tm_phrase
    mov al, [es:si + 2]
    add di, TMC_SIZE
    call tm_phrase
    pop di
    pop si
    pop bx
    pop ax
    ret

; tm_phrase - AL = phrase index (TM_PHNONE: silent) into the record at DI
tm_phrase:
    push ax
    push bx
    mov byte [di + TMC_WAIT], 0
    xor bx, bx
    cmp al, TM_PHNONE
    je .set
    xor ah, ah
    shl ax, 1
    add ax, [tm_ptab]
    mov bx, ax
    mov bx, [es:bx]
.set:
    mov [di + TMC_PTR], bx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tm_event - the channel's next event. BX = channel, DI = its record, ES = part
; Preserves every register.
; -----------------------------------------------------------------------------
tm_event:
    push ax
    push si
    mov si, [di + TMC_PTR]
    or si, si
    jnz .read
    mov byte [di + TMC_WAIT], 255   ; silent for the pattern: tm_pattern resets
    jmp short .out                  ; the wait at the next one
.read:
    mov al, [es:si]
    inc si
    cmp al, TME_END
    je .end
    cmp al, 0x80
    jb .sound
    mov ah, al
    and ah, 0xE0
    and al, 0x1F
    cmp ah, TME_INST
    jne .nshape
    mov [di + TMC_INST], al
    jmp short .read
.nshape:
    cmp ah, TME_SHAPE
    jne .nslur
    mov [di + TMC_SHAPE], al
    jmp short .read
.nslur:
    cmp ah, TME_SLUR
    jne .end                        ; 0xE0..0xFE are not events: stop reading
    mov byte [di + TMC_SLUR], 1
    jmp short .read
.end:
    dec si                          ; stay ON the end, for good
    mov [di + TMC_PTR], si
    mov byte [di + TMC_WAIT], 255
    jmp short .out
.sound:
    mov ah, [es:si]                 ; rows until the next event
    mov [di + TMC_WAIT], ah
    inc si
    or al, al
    jnz .note
    mov [di + TMC_PTR], si          ; TME_REST
    call tm_off
    jmp short .out
.note:
    mov ah, [es:si]                 ; the gate, in ticks
    mov [di + TMC_GATE], ah
    inc si
    mov [di + TMC_PTR], si
    call tm_on
.out:
    pop si
    pop ax
    ret

; -----------------------------------------------------------------------------
; tm_on - AL = a note starts on channel BX (record DI). ES = the part.
; Preserves every register.
; -----------------------------------------------------------------------------
tm_on:
    push ax
    push cx
    push dx
    push si
    mov ah, [di + TMC_SLUR]         ; a slur only means something over a note
    mov byte [di + TMC_SLUR], 0     ; that is still sounding
    cmp byte [di + TMC_NOTE], 0
    jne .sl
    xor ah, ah
.sl:
    mov [tm_slur], ah
    mov [di + TMC_NOTE], al
    mov byte [di + TMC_FRESH], 1
    mov byte [di + TMC_AGE], 0
    cmp byte [tm_arm], 0
    jne .fm
    or bx, bx                       ; THE SPEAKER PLAYS THE LEAD AND NOTHING
    jnz .out                        ; ELSE (TITHE-PLAN 13.2)
    call tm_spkhz
    mov [di + TMC_LASTF], ax
    mov cl, [di + TMC_GATE]
    xor ch, ch
    call tm_tone
    jmp short .out
.fm:
    mov dl, al                      ; DL = the root
    mov cl, [tm_vbase + bx]         ; CL = its voice
    call tm_voice
    cmp bx, TM_CHORD
    jne .out
    mov al, [di + TMC_SHAPE]        ; ...and a chord's two upper notes
    xor ah, ah
    shl ax, 1
    add ax, [tm_shapes]
    mov si, ax
    mov ah, dl
    mov al, [es:si]
    call .upper
    mov al, [es:si + 1]
    call .upper
    jmp short .out
.upper:                             ; AL = interval (0: this voice is unused),
    inc cl                          ; AH = the root
    xor dl, dl
    or al, al
    jz .key
    mov dl, ah
    add dl, al
.key:
    call tm_voice
    ret
.out:
    pop si
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tm_voice - OPL voice CL takes note DL (0 = off) in the record DI's instrument.
; The patch is loaded only when the voice holds a different one; a held note
; is RETRIGGERED - keyed off, then on, because the envelope only restarts on a
; key-on - unless [tm_slur] says it glides. A refusal drops the FM arm.
; Preserves every register.
; -----------------------------------------------------------------------------
tm_voice:
    push ax
    push bx
    mov bl, cl
    xor bh, bh
    or dl, dl
    jnz .on
    cmp byte [tm_fmkeyed + bx], 0
    je .out
    mov al, 1                       ; verb 1: note-off
    call OSAPI_SND_FM
    mov byte [tm_fmkeyed + bx], 0
    jmp short .out
.on:
    mov al, [di + TMC_INST]
    cmp al, [tm_fmpatch + bx]
    je .same
    cmp byte [tm_fmkeyed + bx], 0
    je .patch
    mov al, 1
    call OSAPI_SND_FM
    mov byte [tm_fmkeyed + bx], 0
.patch:
    call tm_patch_ld
    jc .refused
    mov al, [di + TMC_INST]
    mov [tm_fmpatch + bx], al
    jmp short .key
.same:
    cmp byte [tm_fmkeyed + bx], 0
    je .key
    cmp byte [tm_slur], 0
    jne .key
    mov al, 1                       ; the retrigger
    call OSAPI_SND_FM
.key:
    mov al, dl
    call tm_hz
    push bx
    mov bx, ax
    mov al, 0                       ; verb 0: note-on, BX = Hz
    call OSAPI_SND_FM
    pop bx
    jc .refused
    mov byte [tm_fmkeyed + bx], 1
    jmp short .out
.refused:
    call tm_fm_drop
.out:
    pop bx
    pop ax
    ret

; tm_patch_ld - the record DI's instrument onto voice CL. CF = 1 refused.
; The eleven bytes are copied into OUR segment first: the FM slot stages its
; patch from the caller's DS (SPEC.md 34.2), and the bank is in the part.
tm_patch_ld:
    push ax
    push cx
    push si
    push di
    mov al, [di + TMC_INST]
    xor ah, ah
    mov si, ax
    shl si, 1                       ; x TM_INSTREC, which is 16
    shl si, 1
    shl si, 1
    shl si, 1
    add si, [tm_insts]
    mov di, tm_patch
    push cx
    mov cx, 11
.cp:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    loop .cp
    pop cx                          ; CL = the voice again
    mov si, tm_patch
    mov al, 2                       ; verb 2: patch-load
    call OSAPI_SND_FM
    pop di
    pop si
    pop cx
    pop ax
    ret

; tm_fm_drop - the FM arm was refused (another package holds a voice): give
; everything back and carry on as the SPEAKER, which cannot be refused this
; way. The lead picks up at its next note.
tm_fm_drop:
    push ax
    push bx
    mov al, 3
    call OSAPI_SND_FM
    mov byte [tm_arm], 0
    xor bx, bx
.v:
    mov byte [tm_fmpatch + bx], 0xFF
    mov byte [tm_fmkeyed + bx], 0
    inc bx
    cmp bx, TM_NVOICE
    jb .v
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tm_off - channel BX (record DI) stops sounding. Preserves every register.
; -----------------------------------------------------------------------------
tm_off:
    push ax
    push cx
    push dx
    cmp byte [di + TMC_NOTE], 0
    je .out
    mov byte [di + TMC_NOTE], 0
    mov byte [di + TMC_SLUR], 0
    cmp byte [tm_arm], 0
    jne .fm
    or bx, bx
    jnz .out
    xor ax, ax
    xor cx, cx
    call tm_tone
    jmp short .out
.fm:
    mov cl, [tm_vbase + bx]
    mov ch, [tm_vcnt + bx]
    xor dl, dl
.v:
    call tm_voice                   ; DL = 0: off, if it is keyed
    inc cl
    dec ch
    jnz .v
.out:
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tm_chtick - a sounding note ages one tick. BX = channel, DI = record.
; A note keyed THIS tick is left alone, so a gate of G sounds G whole ticks.
; Preserves every register.
; -----------------------------------------------------------------------------
tm_chtick:
    push ax
    push cx
    push si
    cmp byte [di + TMC_NOTE], 0
    je .out
    cmp byte [di + TMC_FRESH], 0
    je .old
    mov byte [di + TMC_FRESH], 0
    jmp short .out
.old:
    inc byte [di + TMC_AGE]
    dec byte [di + TMC_GATE]
    jnz .live
    call tm_off
    jmp short .out
.live:
    cmp byte [tm_arm], 0            ; only the speaker's lead moves in a note:
    jne .out                        ; FM's vibrato is the chip's own
    or bx, bx
    jnz .out
    call tm_irec
    cmp byte [es:si + TMI_VSHIFT], 0
    jne .move
    cmp byte [es:si + TMI_MLEN], 1
    jbe .out
.move:
    call tm_spkhz
    cmp ax, [di + TMC_LASTF]
    je .out                         ; unchanged: no call at all
    mov [di + TMC_LASTF], ax
    mov cl, [di + TMC_GATE]
    xor ch, ch
    call tm_tone
.out:
    pop si
    pop cx
    pop ax
    ret

; tm_irec - SI = the record DI's instrument, in the part
tm_irec:
    push ax
    mov al, [di + TMC_INST]
    xor ah, ah
    mov si, ax
    shl si, 1
    shl si, 1
    shl si, 1
    shl si, 1
    add si, [tm_insts]
    pop ax
    ret

; -----------------------------------------------------------------------------
; tm_spkhz - AX = the lead's frequency THIS tick: its note, moved by the
; instrument's macro at the note's age, then by its square vibrato.
; DI = the lead's record, ES = the part. Preserves every other register.
; -----------------------------------------------------------------------------
tm_spkhz:
    push bx
    push cx
    push dx
    push si
    call tm_irec
    mov al, [di + TMC_AGE]          ; the macro's step: the age, wrapped into
    mov bl, [es:si + TMI_MLEN]      ; the loop once it runs past the end
    cmp al, bl
    jb .step
    mov bh, [es:si + TMI_MLOOP]
    cmp bl, bh
    ja .wrap
    mov al, bl                      ; no loop: the last step holds
    dec al
    jmp short .step
.wrap:
    sub al, bh                      ; mloop + (age - mloop) mod (mlen - mloop)
    sub bl, bh
    xor ah, ah
    div bl
    mov al, ah
    add al, bh
.step:
    xor ah, ah
    mov bx, ax
    mov al, [es:si + TMI_MIDX]
    xor ah, ah
    add bx, ax
    add bx, [tm_macros]
    mov al, [es:bx]                 ; signed semitones, widened, so a note
    cbw                             ; near the top cannot wrap a byte
    mov dl, [di + TMC_NOTE]
    xor dh, dh
    add ax, dx
    cmp ax, TM_NOTE0                ; ...and held on the table
    jge .lo
    mov ax, TM_NOTE0
.lo:
    cmp ax, TM_NOTE0 + TM_NNOTE - 1
    jle .hi
    mov ax, TM_NOTE0 + TM_NNOTE - 1
.hi:
    call tm_hz                      ; AX = Hz
    mov cl, [es:si + TMI_VSHIFT]
    or cl, cl
    jz .done
    mov bl, [di + TMC_AGE]
    sub bl, [es:si + TMI_VDELAY]
    jb .done                        ; not old enough yet
    mov dx, ax
    shr dx, cl                      ; the depth
    test bl, 2                      ; two ticks up, two down
    jnz .down
    add ax, dx
    jmp short .done
.down:
    sub ax, dx
.done:
    pop si
    pop dx
    pop cx
    pop bx
    ret

; tm_hz - AL = a note, AX = its Hz from the part's table. ES = the part.
tm_hz:
    push bx
    sub al, TM_NOTE0
    xor ah, ah
    shl ax, 1
    add ax, [tm_freq]
    mov bx, ax
    mov ax, [es:bx]
    pop bx
    ret

; tm_tone - the speaker: AX = Hz (0 = off), CX = ticks. At OUR priority, so an
; effect preempts it; a refusal is exactly that and is not an error.
tm_tone:
    push ax                         ; the slot answers AL = the generation
    push dx
    mov dl, TM_PRIO
    call OSAPI_SND_TONE
    pop dx
    pop ax
    ret

; --- the voices each channel sounds on (SPEC.md 97.10.3) ----------------------
TM_NVOICE   equ 6
tm_vbase:   db 0, 1, 2, 5
tm_vcnt:    db 1, 1, 3, 1

; --- state: static, because a worker restart re-enters at the top of its loop
; and every byte that outlives a pass is here (OS88_WORKER_RESTARTABLE) ------
tm_req:     db TM_NOREQ             ; posted by the UI task, taken by tm_run
tm_song:    db TM_OFF               ; what is playing
tm_sel:     db TM_OFF               ; what `M` last chose (UI task's)
tm_spkonly: db 0                    ; `S`: the speaker even with FM there
tm_arm:     db 0                    ; 0 the speaker, 1 FM
tm_state:   db 0                    ; the lead a battle state names (13.4)
tm_slur:    db 0
tm_busy:    db 0                    ; set across tm_run
tm_last:    dw 0                    ; the tick the sequencer last stepped at
tm_ticks:   dw 0                    ; ticks since the song began
tm_hdr:     times TMS_PTAB + 2 db 0 ; the song's header, copied at tm_start
tm_glen     equ tm_hdr + TMS_GLEN   ; ...and named by the offsets tisong.inc
tm_groove   equ tm_hdr + TMS_GROOVE ; publishes, so this copy cannot drift
tm_rows     equ tm_hdr + TMS_ROWS   ; from the part's own layout
tm_states   equ tm_hdr + TMS_STATES
tm_ordlen   equ tm_hdr + TMS_ORDLEN
tm_loop     equ tm_hdr + TMS_LOOP
tm_order    equ tm_hdr + TMS_ORDER
tm_ptab     equ tm_hdr + TMS_PTAB
tm_freq:    dw 0
tm_insts:   dw 0
tm_macros:  dw 0
tm_shapes:  dw 0
tm_ord:     db 0
tm_row:     db 0
tm_tleft:   db 0
tm_gi:      db 0
tm_ch:      times TM_NCH * TMC_SIZE db 0
tm_fmpatch: times TM_NVOICE db 0xFF
tm_fmkeyed: times TM_NVOICE db 0
tm_patch:   times 11 db 0
