; =============================================================================
; os8088 - tests/trklog.inc
;
; THE TRACKER LOG. A per-tick record of what the audio chain and the drawing
; side were doing, written to TRKLOG.TXT so it can be carried off the machine
; and read somewhere with a screen bigger than 59 characters.
;
; This is BENCH CODE and it does not ship. `apps/tracker` carries a handful of
; one-line hooks, every one of them inside %ifdef TRKLOG, and everything else
; lives here; the shipped TRACKER.O88 is built without -DTRKLOG and contains
; none of it - not the records, not the claims, not the two keys. The bench
; build is TRKLOG.O88 on build/trklog.img (`make trklog`, docs/TESTING.md).
;
; WHY A LOG AND NOT A METER. The status line carried five running extremes and
; one live count, which was enough to rule things out - it retired the mixer,
; the drawing, the driver's own double buffer and the sample content in turn -
; and is exactly the wrong shape for what is left. An extreme says a bad thing
; happened; it cannot say WHEN, or what else was happening in the same tick, or
; whether the same tick was bad twice. The remaining question is a correlation
; between three clocks - the block IRQ, this worker's wakes and the drawing
; frames - and a correlation needs a time series.
;
; SO: one record per system tick (18.2065 Hz), 1,024 of them = 56 seconds, in a
; 16KB heap claim taken when the log is armed and given back when it is not.
; The rate limit matters and is not cosmetic: inside an fsx bracket
; OSAPI_TASK_SLEEP degenerates to an immediate resume (SPEC.md 53.3), so
; trk_feed is called far more often than 18 times a second and an unlimited log
; would fill in about a second of music.
;
; WHAT EACH FIELD IS FOR
;   TICK  [ticks] when the record was written. A GAP IN THIS COLUMN IS THE
;         MOST IMPORTANT THING IN THE FILE: it means neither the worker nor
;         the drawing side ran for that tick, which is the signature the
;         BLK/WAKE extremes could only report as one number.
;   CONS  the driver's free-running consumed count. It advances by one whole
;         2,048-byte half and only from sbl_isr, so the tick spacing between
;         two different values IS the block-IRQ interval - 6.8 ticks at
;         5,500 Hz - and this column shows every one of them rather than the
;         worst.
;   TOTL  the app's staged total. TOTL - CONS is the ring lead in bytes.
;   S     the stream state: 0 playing, 1 underrun-paused, 2 watchdog-ended.
;   PS PT RW  song position, pattern, row - so any row of the file can be
;         placed in the music, which is what "it hitches at the same point in
;         the song" needs to be checked rather than believed.
;   FR FD how many drawing frames and feed passes happened in that tick. FR 0
;         for a run of ticks is the text screen frozen; FD 0 is the worker not
;         running.
;   FL    1 a shadow rebuild started, 2 a rebuild step ran, 4 a blit ran,
;         8 a stream was opened - and 10h, the one bit a MACHINE cannot set:
;         M stamps it, so the listener can put a mark in the file at the
;         moment they hear a hitch. Everything else here says what the guest
;         was doing; this says what the guest sounded like, and the first
;         field capture showed exactly why that is needed - 62 seconds in
;         which every counter is healthy and nothing in the file knows
;         whether anything was audible.
;   BPM SP  the replayer's tempo, so rows-per-second is derivable per record
;         rather than assumed to be the 125/6 default.
; =============================================================================

TLOG_RECS   equ 1024                ; 56 s at one record per tick
TLOG_RSZ    equ 16                  ; a power of two so the index is 4 shifts
TLOG_KB     equ (TLOG_RECS * TLOG_RSZ + 1023) / 1024
TLOG_LINE   equ 42                  ; 40 columns + CR LF
TLOG_TXTKB  equ (TLOG_RECS * TLOG_LINE + 1024 + 1023) / 1024

TLOGF_REBUILD equ 1
TLOGF_STEP    equ 2
TLOGF_BLIT    equ 4
TLOGF_STREAM  equ 8
TLOGF_MARK    equ 16               ; M: the LISTENER heard something here

; record field offsets
TLR_TICK  equ 0
TLR_CONS  equ 2
TLR_TOTL  equ 4
TLR_STATE equ 6
TLR_POS   equ 7
TLR_PAT   equ 8
TLR_ROW   equ 9
TLR_FR    equ 10
TLR_FD    equ 11
TLR_FL    equ 12
TLR_BPM   equ 13
TLR_SPD   equ 14

; -----------------------------------------------------------------------------
; tlog_key - D: arm or disarm. Arming claims the record buffer, disarming
;            gives it back, so a log that is not running costs no memory at
;            all and the heap is not split for the rest of the session
;            (SPEC.md 50.3 - the mistake docs/FIELD-NOTES.md entry 2 was).
; -----------------------------------------------------------------------------
tlog_key:
    push ax
    push bx
    push dx
    push si
    push es                         ; the claim slots are X stubs: they put
                                    ; the caller's DS in ES and the callback
                                    ; contract wants KERNEL_SEG back
    cmp word [tlog_seg], 0
    jne .off
    mov ax, TLOG_KB                 ; AX = KB in, DX = the base segment OUT
    call OSAPI_MEM_CLAIM            ; (SPEC.md 50.3 - the answer moves
    jc .nomem                       ; register, and reading it out of AX
    mov [tlog_seg], dx              ; writes 16KB of records over the IVT)
    mov word [tlog_n], 0
    mov byte [tlog_full], 0
    mov byte [tlog_flags], 0
    mov byte [tlog_frames], 0
    mov byte [tlog_feeds], 0
    call OSAPI_GET_TICKS
    mov [tlog_lastt], ax
    jmp short .say
.off:
    mov dx, [tlog_seg]              ; DX both ways
    call OSAPI_MEM_FREE
    mov word [tlog_seg], 0
    jmp short .say
.nomem:
    mov si, tlog_s_nomem
    call tui_msg
    jmp short .out
.say:
    call tlog_status
.out:
    pop es
    pop si
    pop dx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tlog_stream - trk_play opened a stream: flag it into the next record
; -----------------------------------------------------------------------------
tlog_stream:
    or byte [tlog_flags], TLOGF_STREAM
    ret

; -----------------------------------------------------------------------------
; tlog_mark - M: the listener heard something. Stamped into the next record.
;
; The one input to this log that is not a measurement. Everything else says
; what the machine was doing; a hitch is a thing a person hears, and without
; a mark a file of healthy counters cannot be told from a file of healthy
; counters taken while the audio was fine.
; -----------------------------------------------------------------------------
tlog_mark:
    push si
    or byte [tlog_flags], TLOGF_MARK
    mov si, tlog_s_mark
    call tui_msg
    pop si
    ret

; -----------------------------------------------------------------------------
; tlog_flag - AL = a TLOGF_* bit the drawing side wants recorded
; -----------------------------------------------------------------------------
tlog_flag:
    or [tlog_flags], al
    ret

; -----------------------------------------------------------------------------
; tlog_feed - called from trk_feed with AX = stream state, DX = consumed.
;             Banks what only the worker can see, then offers a record.
; -----------------------------------------------------------------------------
tlog_feed:
    push ax
    mov [tlog_state], al
    mov [tlog_cons], dx
    mov ax, [trk_total]
    mov [tlog_totl], ax
    inc byte [tlog_feeds]
    jnz .ok
    dec byte [tlog_feeds]           ; saturate rather than wrap: 255 already
.ok:                                ; means "far more than one"
    call tlog_tick
    pop ax
    ret

; -----------------------------------------------------------------------------
; tlog_frame - called once per drawn frame. Bumps the counter, offers a
;              record, and refreshes the status line, which is live because
;              the record count is the only sign the log is running.
; -----------------------------------------------------------------------------
tlog_frame:
    inc byte [tlog_frames]
    jnz .ok
    dec byte [tlog_frames]
.ok:
    call tlog_tick
    call tlog_status
    ret

; -----------------------------------------------------------------------------
; tlog_tick - write one record IF the tick has moved since the last one
;
; Both producers call this, so a tick in which either side ran gets a record
; and a tick in which NEITHER ran gets none - which is what makes a gap in the
; TICK column mean something. Preserves every register.
; -----------------------------------------------------------------------------
tlog_tick:
    push ax
    push bx
    push di
    push es
    mov ax, [tlog_seg]
    or ax, ax
    jz .out
    mov bx, [tlog_n]
    cmp bx, TLOG_RECS
    jae .full
    push ax
    call OSAPI_GET_TICKS
    mov di, ax
    pop ax
    cmp di, [tlog_lastt]
    je .out                         ; same tick: fold into the counters
    mov [tlog_lastt], di
    mov es, ax
    mov ax, bx                      ; AX = n * TLOG_RSZ (16)
    shl ax, 1
    shl ax, 1
    shl ax, 1
    shl ax, 1
    xchg ax, di                     ; DI = offset, AX = the tick again
    mov [es:di + TLR_TICK], ax
    mov ax, [tlog_cons]
    mov [es:di + TLR_CONS], ax
    mov ax, [tlog_totl]
    mov [es:di + TLR_TOTL], ax
    mov al, [tlog_state]
    mov [es:di + TLR_STATE], al
    mov al, [mp_songpos]
    mov [es:di + TLR_POS], al
    mov al, [mp_pattern]
    mov [es:di + TLR_PAT], al
    mov al, [mp_row]
    mov [es:di + TLR_ROW], al
    mov al, [tlog_frames]
    mov [es:di + TLR_FR], al
    mov al, [tlog_feeds]
    mov [es:di + TLR_FD], al
    mov al, [tlog_flags]
    mov [es:di + TLR_FL], al
    mov al, [mp_bpm]
    mov [es:di + TLR_BPM], al
    mov al, [mp_speed]
    mov [es:di + TLR_SPD], al
    mov byte [es:di + 15], 0
    mov byte [tlog_frames], 0
    mov byte [tlog_feeds], 0
    mov byte [tlog_flags], 0
    inc word [tlog_n]
    jmp short .out
.full:
    mov byte [tlog_full], 1
.out:
    pop es
    pop di
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tlog_status - 'LOG 0123/1024' / 'LOG FULL 1024' / 'LOG off' into [tui_msgp]
; -----------------------------------------------------------------------------
tlog_status:
    push ax
    push di
    push si
    cmp word [tlog_seg], 0
    je .off
    mov si, tlog_s_run
    cmp byte [tlog_full], 0
    je .have
    mov si, tlog_s_full
.have:
    mov di, tlog_s_stat
    call tui_scpy
    mov ax, [tlog_n]                ; the count, four decimal digits
    mov di, tlog_s_stat + 4
    call tlog_dec4
    mov si, tlog_s_stat
    jmp short .say
.off:
    mov si, tlog_s_off
.say:
    call tui_msg
    pop si
    pop di
    pop ax
    ret

; tlog_dec4 - AX right-aligned, zero-padded, four decimal digits at [DI]
tlog_dec4:
    push ax
    push bx
    push cx
    push dx
    push di
    add di, 3
    mov cx, 4
    mov bx, 10
.d:
    xor dx, dx
    div bx
    add dl, '0'
    mov [di], dl
    dec di
    loop .d
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tlog_save - W: format every record and write TRKLOG.TXT (SPEC.md 18.4)
;
; WINDOWED ONLY, and not by choice: the file slots are UI-callback-only and a
; bracket owns the machine until it returns (SPEC.md 53.7), so Esc first. The
; text is a TRANSIENT claim held across this one call - 44KB of it, which has
; no business living in a region that caps at 60 (SPEC.md 27.6's rule, and
; Note Pad's) - and the write itself is ~20 seconds of floppy at the measured
; 2,100 bytes/second (PERFORMANCE.md Part 2), which is why the status line
; says so before it starts.
; -----------------------------------------------------------------------------
tlog_save:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    cmp word [tlog_seg], 0
    jne .have
    mov si, tlog_s_none
    call tui_msg
    jmp .out
.have:
    mov si, tlog_s_writing
    call tui_msg
    call trk_repaint_done           ; the notice has to reach the glass BEFORE
                                    ; twenty seconds of floppy, not after
    mov ax, TLOG_TXTKB
    call OSAPI_MEM_CLAIM
    jc .nomem
    mov [tlog_txt], dx              ; DX, not AX (SPEC.md 50.3)
    mov es, dx
    xor di, di
    mov si, tlog_s_h1
    call tlog_emit
    mov si, tlog_s_h2
    call tlog_emit
    mov si, tlog_s_h3
    call tlog_emit
    mov si, tlog_s_h4
    call tlog_emit
    mov word [tlog_i], 0
.row:
    mov ax, [tlog_i]
    cmp ax, [tlog_n]
    jae .done
    call tlog_fmt                   ; record [tlog_i] -> tlog_line
    mov si, tlog_line
    call tlog_emit
    inc word [tlog_i]
    jmp short .row
.done:
    mov cx, di                      ; DX:CX = the byte count
    xor dx, dx
    mov bx, 0
    mov si, tlog_s_name
    call OSAPI_FILE_WRITE
    pushf
    push ax
    mov dx, [tlog_txt]              ; the staging claim goes back either way
    call OSAPI_MEM_FREE
    pop ax
    popf
    jc .werr
    mov si, tlog_s_wrote
    call tui_msg
    jmp short .out
.werr:
    mov si, tlog_s_werr
    call tui_msg
    jmp short .out
.nomem:
    mov si, tlog_s_nomem
    call tui_msg
.out:
    call trk_repaint_done
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tlog_emit - copy the NUL string at DS:SI to ES:DI, then CR LF. DI advances.
tlog_emit:
    push ax
    push si
    cld
.l:
    lodsb
    or al, al
    jz .eol
    stosb
    jmp short .l
.eol:
    mov al, 13
    stosb
    mov al, 10
    stosb
    pop si
    pop ax
    ret

; -----------------------------------------------------------------------------
; tlog_fmt - record [tlog_i] -> tlog_line as
;            'TICK CONS TOTL S PS PT RW FR FD FL BPM SP'
;
; Hex throughout and a table lookup per nibble (tui_hexb), because the one
; thing this must not do is spend a div per field on a 4.77MHz machine while
; the user waits.
; -----------------------------------------------------------------------------
tlog_fmt:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov ax, [tlog_seg]
    mov es, ax
    mov si, [tlog_i]
    shl si, 1
    shl si, 1
    shl si, 1
    shl si, 1
    mov di, tlog_line
    mov ax, [es:si + TLR_TICK]
    call tlog_hex4
    mov ax, [es:si + TLR_CONS]
    call tlog_hex4
    mov ax, [es:si + TLR_TOTL]
    call tlog_hex4
    mov al, [es:si + TLR_STATE]     ; the state is one nibble; the rest are
    add al, '0'                     ; bytes
    mov [di], al
    inc di
    mov al, ' '
    mov [di], al
    inc di
    mov bx, TLR_POS
.b:
    push bx
    add bx, si
    mov al, [es:bx]
    pop bx
    call tui_hexb
    mov byte [di], ' '
    inc di
    inc bx
    cmp bx, TLR_SPD
    jbe .b
    dec di                          ; drop the trailing space
    mov byte [di], 0
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tlog_hex4 - AX as four hex digits plus a space at [DI]; DI advances by 5
tlog_hex4:
    push ax
    mov al, ah
    call tui_hexb
    pop ax
    call tui_hexb
    mov byte [di], ' '
    inc di
    ret

; --- strings -----------------------------------------------------------------
tlog_s_name:    db 'TRKLOG.TXT', 0
tlog_s_run:     db 'LOG      /1024  W saves', 0
tlog_s_full:    db 'LOG FULL     /1024  W saves', 0
tlog_s_off:     db 'LOG off - D arms it', 0
tlog_s_none:    db 'No log - D arms one first', 0
tlog_s_nomem:   db 'Log: out of memory', 0
tlog_s_writing: db 'Writing TRKLOG.TXT - 20s of floppy', 0
tlog_s_wrote:   db 'Wrote TRKLOG.TXT', 0
tlog_s_werr:    db 'TRKLOG.TXT write failed', 0
tlog_s_fsw:     db 'Save is windowed: Esc first', 0
tlog_s_mark:    db 'MARK', 0
tlog_s_h1:      db 'os8088 tracker log - one record per system tick (18.2065 Hz)', 0
tlog_s_h2:      db 'CONS advances one 2048-byte half per block IRQ; TOTL-CONS is the ring lead', 0
tlog_s_h3:      db 'FL bits: 1 rebuild  2 step  4 blit  8 stream opened  10 LISTENER MARK', 0
tlog_s_h4:      db 'TICK CONS TOTL S PS PT RW FR FD FL BP SP', 0

; --- bss ---------------------------------------------------------------------
    TRKW tlog_seg                   ; the record claim, 0 = not armed
    TRKW tlog_txt                   ; the staging claim, live inside tlog_save
    TRKW tlog_n                     ; records written
    TRKW tlog_i                     ; tlog_save's cursor
    TRKW tlog_lastt                 ; the tick the last record carries
    TRKW tlog_cons                  ; what the worker last saw...
    TRKW tlog_totl
    TRKB tlog_state
    TRKB tlog_frames                ; ...and what has happened since the last
    TRKB tlog_feeds                 ; record was written
    TRKB tlog_flags
    TRKB tlog_full
    TRKBUF tlog_s_stat, 32          ; the live status line
    TRKBUF tlog_line, TLOG_LINE + 8
