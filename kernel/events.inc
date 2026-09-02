; =============================================================================
; os8088 - events.inc
;
; The system event queue (SPEC.md 10): a single ring of 16 fixed 8-byte
; records in .bss. A FULL ring discards its OLDEST INPUT rather than refusing
; the newest (SPEC.md 10.1) - see evq_push, and the one exception it makes.
; Producers may be ISRs (the mouse ISR pushes button
; events with IF=0), consumers are tasks (the UI task pops), so both push
; and pop guard their whole read-modify-write with pushf/cli ... popf -
; the caller's interrupt flag is preserved and never a bare sti.
; =============================================================================

; --- event record layout (8 bytes) -------------------------------------------
EV_TYPE     equ 0               ; word: EVT_*
EV_A        equ 2               ; word: payload a (mouse events: x)
EV_B        equ 4               ; word: payload b (mouse events: y)
EV_C        equ 6               ; word: payload c (unused so far)

EVT_NONE    equ 0
EVT_MDOWN   equ 1               ; a=x, b=y, c=birth tick
EVT_MUP     equ 2               ; a=x, b=y, c=birth tick
EVT_RDOWN   equ 3               ; a=x, b=y, c=birth tick; RIGHT button PRESS.
                                ; There is no EVT_RUP on purpose: the only
                                ; consumer is the context-menu tracker, which
                                ; polls mouse_btn bit 1 for its whole life
                                ; (SPEC.md 12.4), so a release record would
                                ; be one nobody ever pops. EV_C rides along
                                ; for record symmetry and is read by nobody -
                                ; a right double-click would need no format
                                ; change to arrive.
EVT_WAKE    equ 4               ; a=window ptr, b/c unused. A PACKAGE'S OWN
                                ; KICK (SPEC.md 74.1): posted through
                                ; OSAPI_WM_WAKE from any context, popped by
                                ; the UI task and dispatched to the window's
                                ; W_ONWAKE handler WITHOUT the gfx lock, so
                                ; the handler may call the file slots and may
                                ; take the lock itself for a stated burst.
                                ; wm_wake coalesces: one queued wake per
                                ; window at a time, so a package that kicks
                                ; from every callback cannot fill the ring.

EVQ_RECSIZE equ 8               ; bytes per record
EVQ_CAP     equ 16              ; records in the ring
EVQ_MASK    equ (EVQ_RECSIZE * EVQ_CAP) - 1     ; byte-offset wrap mask (0x7F)
%if EVQ_MASK > 0xFF
  %error "the three wrap sites mask AL alone (`and al, EVQ_MASK`), which is only the same answer while the ring's byte offsets fit a byte. Grow EVQ_RECSIZE * EVQ_CAP past 256 and every wrap silently keeps a high bit the ring has no room for"
%endif

; -----------------------------------------------------------------------------
; evq_init - reset the queue to empty
; in:  nothing
; out: nothing
; clobbers: nothing (flags only)
; ISR-SAFE, AND IT MUST STAY SO EVEN THOUGH ITS SECOND CALLER HAS GONE.
; kmain is the only caller again: blk_pass used to reset the queue here to
; drop the press that woke the screen, and SPEC.md 74.1.1 replaced that with a
; DRAIN through wm_wake_eaten, because a reset wiped EVT_WAKE records and left
; wm_wkq pointing at nothing - a window deaf for the rest of its life. The
; interrupts-off bracket stays regardless: an evq_push landing between the
; tail store and the count store writes at tail 0 and leaves tail one record
; ahead of head for the rest of the session, so every later evq_pop answers
; the PREVIOUS push's record. Cheap, once, at boot.
; -----------------------------------------------------------------------------
evq_init:
    push ax                     ; ...banked, so "clobbers nothing (flags only)"
    pushf                       ; is unchanged: three zeroes through the 3-byte
    cli                         ; `mov [moffs], ax` form beat three 6-byte
    xor ax, ax                  ; immediate stores even after the bank
    mov [evq_head], ax
    mov [evq_tail], ax
    mov [evq_count], ax
    popf
    pop ax
    ret

; -----------------------------------------------------------------------------
; evq_push - append one event record to the queue
; in:  SI -> 8-byte record (in DS)
; out: nothing; drops the event silently when the queue is full
; clobbers: nothing (flags only)
; ISR-safe: the copy + index update sit inside pushf/cli ... popf, so a
; caller running with IF=0 (the mouse ISR) stays that way throughout.
; -----------------------------------------------------------------------------
evq_push:
    call sch_wake_ui            ; an event means the UI task has work
    push ax                     ; work (docs/SCHED-IDLE-PLAN.md 6.3)
    push si                     ; ...and no CX bank: with the record copy
                                ; unrolled nothing in this body writes it. The
                                ; CONTRACT is unchanged - CX still comes back
                                ; untouched - it just costs nothing to keep.
    push di
    push es
    pushf
    cli

    cmp word [evq_count], EVQ_CAP
    jb .room
    ; --- SPEC.md 10.1: full, so something is lost. Lose the OLDEST ----------
    mov di, [evq_head]          ; ...unless the oldest is a WAKE, which is a
    add di, evq_buf             ; PROMISE and not a sample: wm_wake coalesces
    cmp word [ss:di + EV_TYPE], EVT_WAKE ; on a per-window flag that only a
                                ; DISPATCH clears - and `ss:` because the ring
                                ; is in LOW_SEG now (SPEC.md 10.1.1), which SS
                                ; names for every kernel task and every ISR
                                ; that runs on one
    je .full                    ; DISPATCH clears, so discarding one hangs
                                ; that window's handshake for the session.
                                ; A ring full of input has input at its head,
                                ; so this falls back to dropping the newest
                                ; about as often as a wake is the oldest
    mov ax, [evq_head]
    add ax, EVQ_RECSIZE
    and al, EVQ_MASK           ; AL alone - see the %if beside EVQ_MASK
    mov [evq_head], ax
    dec word [evq_count]        ; ...and the copy below puts it straight back
.room:
    push ss                     ; copy runs DS:SI -> ES:DI, and ES is LOW_SEG
    pop es                      ; rather than the kernel's since SPEC.md 10.1.1
                                ; - which is what SS names, set as kmain's
                                ; third instruction, before evq_init and before
                                ; any ISR is hooked, and never changed again
                                ; (every task stack is in LOW_SEG). The `ss:`
                                ; override above already rests on that; this
                                ; makes the COMMON path rest on it too.
                                ; **IT IS 5 TO 12 CLOCKS SLOWER PER SITE**, not
                                ; faster: a push and a pop each move a word
                                ; through memory (~13.5 clocks each here, ~34
                                ; by the operand-byte rule) against the `mov`
                                ; pair's 21.7 on the prefetch floor. evq_push
                                ; runs once per input event, so it is under
                                ; 0.01% of the machine and the 8 bytes win.
    mov di, [evq_tail]          ; put the ring there: the SOURCE is the caller's
    add di, evq_buf             ; record and stays DS-relative
    cld
    movsw                       ; EVQ_RECSIZE / 2 = 4, unrolled: four `movsw`
    movsw                       ; is 4 bytes and 72 clocks against `mov cx,4 /
    movsw                       ; rep movsw` at 5 and 77 - and it stops
    movsw                       ; spending CX. GROW EVQ_RECSIZE AND THIS COPY
                                ; TRUNCATES SILENTLY.

    mov ax, [evq_tail]
    add ax, EVQ_RECSIZE
    and al, EVQ_MASK           ; AL alone - see the %if beside EVQ_MASK
    mov [evq_tail], ax
    inc word [evq_count]

.full:
    popf
    jmp evq_pop.done            ; THE SAME FOUR POPS AND THE SAME `ret`: this
                                ; routine and evq_pop push ax/si/di/es in that
                                ; order and unwind them in the mirror, so one
                                ; epilogue serves both. That makes the two PUSH
                                ; SETS one contract - change either without the
                                ; other and this returns to the wrong address.
                                ; `pop` writes no flag, so the FLAGS this
                                ; `popf` restores survive the shared tail
                                ; exactly as they did when it was local.

; -----------------------------------------------------------------------------
; evq_pop - remove the oldest event record from the queue
; in:  DI -> 8-byte destination buffer (in DS)
; out: CF=0 and the record copied to [DI]; CF=1 if the queue was empty
;      (destination untouched)
; clobbers: nothing but CF
; The whole read-modify (copy + index update) sits inside pushf/cli ... popf
; so a concurrent ISR push can never interleave with it.
; -----------------------------------------------------------------------------
; evq_drain - empty the ring, owing every wake (SPEC.md 74.1.1)
; in:  DI -> an 8-byte record buffer IN DS, PRIVATE TO THE CALLER
; out: the ring is empty; DI preserved (evq_pop preserves it, and
;      wm_wake_eaten preserves every register)
; clobbers: flags
;
; THE BUFFER IS AN IN-PARAMETER AND THAT IS THE POINT.  Three drains had this
; loop written out - fsx_restore's, blk_pass's and osapi_snd_play's click
; abort - and the obvious consolidation gives them one shared buffer as well
; as one loop.  It must not: only the snd drain is atomic (it holds sch_lock
; across its loop), the two UI-task drains are not, and a kept worker or a
; TF_SERVICE task calling OSAPI_SND_PLAY - which the kernel cannot refuse,
; apps/os88api.inc says so in terms - would overwrite a record task 0 is one
; instruction away from reading.  That turns a documented visible stall into
; a window deaf for the rest of its life, which is the failure blank.inc's
; own comment already records.  So each site keeps the buffer it has.
;
; AND NO BUFFER LIVES HERE.  events.inc's data is in TWO sections: the ring
; in `.lowbss` (LOW_SEG, reached through SS) and the rest in `.bss`.  A
; buffer "beside the ring" would land in LOW_SEG while evq_pop writes ES:DI
; with ES = KERNEL_SEG.
;
; All three call sites are `.text` = KERNEL_SEG, like this, so the call is
; near.
; -----------------------------------------------------------------------------
evq_drain:
.dl:
    call evq_pop
    jc .dend
    call wm_wake_eaten          ; a package's wake is OWED, not dropped
    jmp short .dl
.dend:
    ret

; -----------------------------------------------------------------------------
evq_pop:
    push ax
    push si                     ; ...and no CX bank, for evq_push's reason
    push di
    push es
    pushf
    cli

    cmp word [evq_count], 0
    je .empty

    push ds                     ; copy runs DS:SI -> ES:DI: the DESTINATION is
    pop es                      ; the caller's buffer and is still the kernel's
    mov si, [evq_head]
    add si, evq_buf
    cld
    push ds                     ; ...and the SOURCE is the ring, in LOW_SEG
    push ss                     ; since SPEC.md 10.1.1. DS is BANKED rather than
    pop ds                      ; the copy wearing a segment prefix: the 8086
    movsw                       ; LOSES the prefix when a string op restarts
    movsw                       ; after an interrupt, and NMI reaches inside the
    movsw                       ; cli above. EVQ_RECSIZE / 2 = 4, unrolled -
    movsw                       ; GROW THE RECORD AND THIS TRUNCATES SILENTLY.
    pop ds

    mov ax, [evq_head]
    add ax, EVQ_RECSIZE
    and al, EVQ_MASK           ; AL alone - see the %if beside EVQ_MASK
    mov [evq_head], ax
    dec word [evq_count]

    popf                        ; restore caller's IF first, then report
    clc
    jmp .done

.empty:
    popf
    stc

.done:                          ; ...and evq_push's exit too - see there
    pop es
    pop di
    pop si
    pop ax
    ret

; -----------------------------------------------------------------------------
; evq_pending - how many events are still queued behind this one?
; out: AX = 0..EVQ_CAP; preserves every other register and the flags
;
; SPEC.md 13.4. A callback is dispatched one event at a time, so a handler that
; REDRAWS has no way to know it is about to be asked to do the same thing
; again - and a user holding down a scroll arrow, or spamming the track, queues
; a burst of clicks whose redraws then play out one after the other long after
; the clicking stopped. The scroll positions in that burst are superseded the
; instant the next one is read; only the last one is worth a repaint.
;
; One word, read with no lock. It is a single memory read of a word the ISR
; only ever increments, so a torn value is not possible and a stale one is
; harmless in the only direction that matters: too LOW means a redraw happens
; that need not have, which is exactly today's behaviour.
;
; It answers a question about the QUEUE and not about which window an event is
; for, so a handler that skips a redraw on the strength of it must still make
; sure the redraw eventually happens - the next event may belong to somebody
; else. Note Pad owes it to its worker (SPEC.md 27.7.8).
; -----------------------------------------------------------------------------
evq_pending:
    mov ax, [evq_count]
    ret                             ; NEAR - the OSAPI_SLOT cell owns the retf

; -----------------------------------------------------------------------------
section .lowbss                 ; LOW_SEG (SPEC.md 2.1, 10.1.1): 128 bytes of
                                ; ring out of the 64KB segment, which is the
                                ; scarce one, for nine bytes of code and no
                                ; footprint at all - the block lands inside
                                ; `.lowbss`'s existing rung.
                                ;
                                ; It is reached through SS (the WAKE test, which
                                ; is an ordinary read) and through ES and a
                                ; banked DS (the two copies). `.lowbss` does not
                                ; arrive zeroed and does not need to: evq_init
                                ; clears the three indices below, and no record
                                ; is ever read that a push did not write.
                                ;
                                ; events.inc is %included AFTER sched.inc, so
                                ; this cannot move sch_stacks' word-alignment
                                ; pad - which is the one thing adding `.lowbss`
                                ; can break at a distance. That pad was 256
                                ; bytes and is now a word (SPEC.md 2.1), so a
                                ; block ADDED ABOVE sch_stacks moves it by at
                                ; most one byte rather than by up to 256 - and
                                ; sched.inc's %if is what refuses the odd case.
evq_buf:    resb EVQ_RECSIZE * EVQ_CAP  ; the ring itself (128 bytes)

section .bss
evq_head:   resw 1                      ; byte offset of the oldest record
evq_tail:   resw 1                      ; byte offset of the next free slot
evq_count:  resw 1                      ; records currently queued (0..EVQ_CAP)

section .text
