; =============================================================================
; os8088 - apps/tape/tapexfr.inc - the transport (SPEC.md 88.2)
;
; ONE record in, or one record out, and NOTHING ELSE IN THIS PACKAGE TOUCHES
; THE HARDWARE. Everything above it - the state machine, the format, the
; window - is written against `tp_xfer`'s register contract and never against
; `int 15h`, which is what makes the whole of it testable on a machine with no
; cassette port and no cassette.
;
; **TWO ARMS, AND ONLY ONE OF THEM IS BUILT.**
;
;   -DTAPE_FAKE   the transport is a memory buffer that stands in for the
;                 tape: records are laid down and read back with the same
;                 semantics the ROM gives them, including the two that decide
;                 the format (a short read CONSUMES the whole record, and a
;                 read past the end answers AH = 04). This is the arm the
;                 UI, the state machine and all 29 checks are exercised
;                 through - `make tapesimtest`, tests/tapesim.py.
;
;   (default)     the real `int 15h AH=02/03`, WITH THE WHOLE BRACKET OF
;                 SPEC.md 88.2 - the PIT lend, the IMR mask, the motor and the
;                 port-61h restore. **IT IS NOT WRITTEN YET**: this is wave 5
;                 and that is wave 6 (docs/plans/CASSETTE-PLAN.md 15). The arm
;                 below is a STUB that refuses in words, marked as such, and
;                 the refusal is honest about which gate said no rather than
;                 borrowing one of 88.1's two sentences.
;
; The split is at the smallest possible seam ON PURPOSE. Wave 6 fills in one
; routine and one detector; every line of format, layout, greying and state
; above it is already exercised, which is the only kind of verification a
; feature with no emulator (SPEC.md 88.11) can have before it meets a deck.
; =============================================================================

; --- what [tp_hw] holds (SPEC.md 88.1) ---------------------------------------
TP_HW_OK      equ 0             ; both gates passed
TP_HW_MODEL   equ 1             ; the model byte is not 0xFF - not a 5150
TP_HW_BIOS    equ 2             ; model 0xFF, and the ROM refused int 15h AH=01
TP_HW_WIP     equ 3             ; ...and a THIRD, which SPEC.md 88.1 does not
                                ; have: this build has no transport at all.
                                ; Reporting it as TP_HW_BIOS would be a
                                ; sentence about a ROM this code never asked

; --- what tp_xfer answers in AH (SPEC.md 88.2) -------------------------------
TP_AH_CRC     equ 1             ; the ROM's own
TP_AH_SIGNAL  equ 2
TP_AH_NODATA  equ 4
TP_AH_REFUSE  equ 0x80          ; refused by US, before the ROM was entered
TP_AH_SHORT   equ 0x81          ; ...and one 88.2's list does not have: the
                                ; call RETURNED, and one of 88.4.3's three
                                ; post-conditions did not hold. It is not
                                ; 0x80 (nothing was refused) and it is not a
                                ; ROM status (the ROM said AH = 0), so it
                                ; needs a sentence of its own - which is
                                ; exactly the case the GLaBIOS retry defect
                                ; produces

; -----------------------------------------------------------------------------
; tp_post - SPEC.md 88.4.3's THREE post-conditions, not one
; in:  AH = the status, BX = the end-of-output pointer, DX = the byte count,
;      CX = what was asked for
; out: CF=0 accepted; CF=1 and AH = why. Nothing else touched.
;
; **THIS IS THE HALF THAT CATCHES THE GLaBIOS RETRY**, and it is shared by both
; arms deliberately: the fake transport is checked by the same code the real
; one will be, so wave 6 inherits a tested checker rather than writing a second
; one. GLaBIOS's read retry re-arms CX to the original request without
; resetting the output pointer, so a dropout inside the two CRC bytes can store
; up to five requests' worth of bytes at an advancing DI - ~5,080 bytes into a
; 1,016-byte buffer - and on a successful retry AH = 0 and DX = CX, so the
; obvious post-condition PASSES. BX is the one that does not.
;
; DX is meaningless unless AH == 0, which is why the status is tested first:
; GLaBIOS returns DX = the original CX on a no-leader failure and IBM zeroes
; it, so a reader that believed DX would believe two different lies.
; -----------------------------------------------------------------------------
tp_post:
    or ah, ah
    jnz .rom                    ; the ROM said no: that answer IS the answer
    cmp dx, cx
    jne .short
    cmp bx, cx                  ; BX = 0 went in, so this is "exactly CX bytes
    jne .short                  ; were stored, and not one more"
    clc
    ret
.short:
    mov ah, TP_AH_SHORT
.rom:
    stc
    ret

%ifdef TAPE_FAKE
; =============================================================================
; THE FAKE TRANSPORT (-DTAPE_FAKE)
;
; A heap claim stands in for the tape. It holds a sequence of records, each a
; two-byte length followed by that many bytes, and [tp_fpos] is the head.
; What makes it worth having is that it reproduces the THREE BIOS behaviours
; the format is built around (SPEC.md 88.4):
;
;   * a read scans forward to the next record for free - here, the head is
;     already at one;
;   * **a read of CX less than the record's length CONSUMES THE WHOLE RECORD**
;     - the head advances past all of it, and the remainder can never be
;     recovered. That is what makes the header record's one-block size
;     load-bearing and what makes the unit of retry the FILE;
;   * a read past the end answers AH = 04, "no data leader", which is the same
;     answer as a stopped deck and is NEVER read as the end of a file.
;
; What it does NOT model, stated rather than implied: bit timing, the leader,
; the sync byte, the block CRC (the ROM's, not ours), dropouts, and every
; failure mode a real deck has. It cannot be a substitute for a field run
; (SPEC.md 88.11) and nothing here should be read as one.
; =============================================================================
TP_FAKE_KB    equ 24            ; the tape's length, in KB. It bounds the
                                ; fixture rather than the format: a real deck
                                ; holds TP_MAXFILE and more

; -----------------------------------------------------------------------------
; tp_fake_want - claim the tape, once per instance
; out: CF=0 and [tp_fseg] is live; CF=1 the heap would not fund it
; -----------------------------------------------------------------------------
tp_fake_want:
    push ax
    push dx
    cmp word [tp_fseg], 0
    jne .have
    mov ax, TP_FAKE_KB
    call OSAPI_MEM_CLAIM        ; PINNED, which is MC_RLOC's default and must
    jc .out                     ; stay: the buffer stands where a ROM's inner
    mov [tp_fseg], dx           ; loop would be walking it
    mov word [tp_fcap], TP_FAKE_KB * 1024
.have:
    clc
.out:
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_rewind - put the head back at the start of the tape
; out: nothing; every register preserved. `Rewind` on the deck, and the one
; thing the software may do that SPEC.md 88.10 item 14 refuses: it moves NO
; tape, because there is none - it is the fixture's own control
; -----------------------------------------------------------------------------
tp_rewind:
    mov word [tp_fpos], 0
    ret

; -----------------------------------------------------------------------------
; tp_xfer - move ONE record (SPEC.md 88.2's contract, the fake transport)
; in:  AL    = 2 (read) or 3 (write)
;      ES:BX = the record buffer, BX = 0, ES = the base of a PINNED claim
;      CX    = bytes to move: 256, or the recblk x 256 / lastblk x 256 the
;              header declared. ALWAYS a multiple of 256, 256..4096
; out: CF=0  the record moved and all three post-conditions hold
;      CF=1  AH = why (TP_AH_*)
;      BX, CX, DX, SI, DI, BP, DS and ES come back as they went in
;
; CONTEXT: the W_ONWAKE handler, on the UI task, GFX LOCK NOT HELD (SPEC.md
;          88.8). The real one does not return for 4.1 to 8.8 seconds; this
;          one returns at once, which is the whole reason a test can drive it.
; -----------------------------------------------------------------------------
tp_xfer:
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov [tp_verb], al           ; **THE VERB IS BANKED IN MEMORY AND NOT ON THE
                                ; STACK**, and that is not a style choice: AH
                                ; is the ANSWER, so a `pop ax` on the way out
                                ; would put the caller's incoming AH back over
                                ; the status this routine just computed. It
                                ; did exactly that for one build - the write
                                ; and the first two reads passed because the
                                ; caller happened to be holding AH = 0, and
                                ; the third record failed as "no data leader"
                                ; on a tape that had it. AL is the only half
                                ; wanted twice, and it is a byte
    ; --- step 1: refuse before anything else (SPEC.md 88.2) -----------------
    cmp byte [tp_hw], TP_HW_OK
    jne .refuse
    test cx, 0x00FF
    jnz .refuse                 ; a multiple of 256, ALWAYS - which is what
    cmp cx, TP_BLOCK            ; keeps both ROMs' pad loops out of the picture
    jb .refuse                  ; entirely (SPEC.md 88.9 row 24)
    cmp cx, 16 * TP_BLOCK
    ja .refuse
    call tp_fake_want
    jc .refuse
    mov al, [tp_verb]
    cmp al, 3
    je .write
    cmp al, 2
    jne .refuse
    ; ======================= READ =========================================
    ; Row 23: ZERO THE RECORD BUFFER BEFORE EVERY READ. Mandatory - a short or
    ; a failed read leaves the previous record's bytes in place and they will
    ; pass a magic check. It is done HERE and not in the caller so that no call
    ; site can forget it.
    mov di, bx
    xor ax, ax
    push cx
    cld
    rep stosb
    pop cx
    mov si, [tp_fpos]
    cmp si, [tp_flen]
    jae .nodata
    push ds                     ; the tape is the SOURCE, and movsb's source is
    mov ds, [tp_fseg]           ; DS:SI - so DS is the tape for the copy and
    mov dx, [si]                ; ours for everything else. Every read of a
    add si, 2                   ; variable of ours is outside this bracket
    mov ax, dx
    cmp ax, cx
    jbe .have                   ; a read SHORTER than the record is legal, and
    mov ax, cx                  ; it leaves the tape past the WHOLE of it
.have:
    mov di, bx
    push cx
    push ax
    mov cx, ax
    cld
    rep movsb                   ; DS:SI (the tape) -> ES:DI (the buffer)
    pop ax
    pop cx
    pop ds
    add dx, 2
    add [tp_fpos], dx           ; ...past all of it. The remainder can never be
    mov dx, ax                  ; recovered, which is why the unit of retry is
    mov bx, ax                  ; the FILE and not the record (SPEC.md 88.4.3)
    mov ah, 0
    jmp short .answer
.nodata:
    mov ah, TP_AH_NODATA        ; the end of the recorded tape, or nothing
    mov dx, cx                  ; playing - GLaBIOS leaves DX = the original CX
    xor bx, bx                  ; here, which tp_post refuses to believe
    jmp short .answer
    ; ======================= WRITE ========================================
.write:
    mov si, [tp_fpos]
    mov ax, si
    add ax, cx
    add ax, 2
    jc .full
    cmp ax, [tp_fcap]
    ja .full
    mov di, si                  ; DI = where on the tape
    push ds
    mov ax, es                  ; the caller's buffer is the SOURCE this time,
    mov dx, [tp_fseg]           ; so the two segments swap round. Both are read
    mov ds, ax                  ; out of OUR ds before either is loaded
    mov es, dx
    mov si, bx
    mov [es:di], cx             ; the record's own length...
    add di, 2
    push cx
    cld
    rep movsb                   ; ...and the record
    pop cx
    pop ds
    mov ax, di
    mov [tp_fpos], ax
    mov [tp_flen], ax
    mov ah, 0                   ; `AH=03` returns 0 UNCONDITIONALLY on both
    mov dx, cx                  ; ROMs, which is why the app never says
    mov bx, cx                  ; "written" on the strength of it (row 25)
    jmp short .answer
.full:
    mov ah, TP_AH_SIGNAL        ; the tape ran out. A real write cannot report
    xor dx, dx                  ; that at all, which is what Verify is for -
    xor bx, bx                  ; the fixture says so where the ROM cannot
.answer:
    pop es
    call tp_post                ; ...and the three post-conditions, which both
    jmp short .out              ; arms answer through
.refuse:
    pop es
    mov ah, TP_AH_REFUSE
    stc
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; tp_detect - SPEC.md 88.1's two gates, once, in the entry proc
; out: [tp_hw] set; every register preserved
;
; The fake transport IS the hardware, so both gates pass by construction. It
; touches no port and calls no BIOS - which matters more than it looks: gate 2
; is a real `int 15h` and MartyPC's PPI returns a hardwired zero for the
; cassette data line, so a fixture that made the call would be asserting
; against an emulator's stub rather than against this package.
; -----------------------------------------------------------------------------
tp_detect:
    mov byte [tp_hw], TP_HW_OK
    mov byte [tp_model], 0xFF
    ret

; -----------------------------------------------------------------------------
; tp_motor_off - the relay is on somebody's tape deck (SPEC.md 88.9 row 28)
; out: nothing; every register preserved. Nothing to do here, and the call site
; is what matters: it is on EVERY exit path including the refusals, so wave 6
; fills in one instruction rather than hunting for the eleven places to put it
; -----------------------------------------------------------------------------
tp_motor_off:
    ret

%else
; =============================================================================
; THE REAL TRANSPORT - **WAVE 6, AND NOT WRITTEN** (docs/plans/CASSETTE-PLAN.md
; 15). Everything below refuses.
;
; What goes here is SPEC.md 88.2's eighteen steps IN ORDER, and every one of
; them is load-bearing: the OSAPI_PIT_LEND claim and the floppy-motor wait, the
; pushf/cli bank of ports 21h and 61h, the IRQ mask (IRQ0/3/4 always, IRQ1 on a
; WRITE only - mask where the failure is silent, keep the escape where it is
; loud), OSAPI_PL_ENTER, the `int 15h` itself, a `cli` as the VERY FIRST
; instruction after it, the bank of AX/BX/DX, OSAPI_PL_LEAVE, `AH=01` BEFORE
; the IMR restore, the IMR restored byte for byte, port 61h restored with bits
; 0 and 1 CLEARED, and OSAPI_PL_RELEASE on the last record and on every refusal
; path.
;
; It is not stubbed here as a convenience. A cassette read cannot be executed
; by any instrument in this project (SPEC.md 88.11), so the code that will do
; it has to arrive with the field disk and the ROM fixture that go with it -
; and shipping a plausible-looking one now would make the wave 5 gates green
; about a transport nobody has run.
;
; THE STUB REFUSES IN ITS OWN WORDS. It does not borrow either of 88.1's two
; sentences, because both of them are claims about the MACHINE and this is a
; fact about the BUILD.
; =============================================================================

; -----------------------------------------------------------------------------
; tp_xfer - WAVE 6. See above.
; -----------------------------------------------------------------------------
tp_xfer:
    mov ah, TP_AH_REFUSE
    stc
    ret

; -----------------------------------------------------------------------------
; tp_detect - WAVE 6. Gate 1, the model byte, is four instructions with no side
; effect and would be right to run here - but a build with no transport cannot
; answer TP_HW_OK whatever the badge says, so running it would only choose
; which false sentence to print. The honest answer is the build's own.
; -----------------------------------------------------------------------------
tp_detect:
    mov byte [tp_hw], TP_HW_WIP
    mov byte [tp_model], 0
    ret

; -----------------------------------------------------------------------------
; tp_motor_off - WAVE 6: `mov ah, 1 / int 15h`, unconditionally, on every exit
; path. Nothing to put back until there is something that turns it on.
; -----------------------------------------------------------------------------
tp_motor_off:
    ret

tp_rewind:
    ret
%endif

; --- the transport's state ---------------------------------------------------
tp_hw:      db TP_HW_WIP        ; tp_detect's one cached byte (SPEC.md 88.1),
                                ; so SPEC.md 47 rule 5's cost corollary - a
                                ; greying test runs on every paint - is
                                ; satisfied by construction
tp_model:   db 0                ; ...and the model byte we read, banked, so the
                                ; refusal can NAME it
tp_verb:    db 0                ; the AL tp_xfer was called with
%ifdef TAPE_FAKE
tp_fseg:    dw 0                ; the claim that stands in for the tape
tp_fpos:    dw 0                ; the head
tp_flen:    dw 0                ; how much has been laid down
tp_fcap:    dw 0
%endif
