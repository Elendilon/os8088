; =============================================================================
; os8088 - apps/tape/tape.asm
;
; TAPE (SPEC.md 88): it writes a file from a disk onto an audio cassette
; through the IBM PC 5150's cassette port, and reads one back, using the ROM's
; own `int 15h AH=02` and `AH=03`. **One package owns the window, the state
; machine, the format, every checksum, all file I/O and the transport. There
; is no driver** - SPEC.md 88.10 items 1 to 3 are why, and the shortest of
; those reasons is that a 5150 with 128-195 KB runs kern_small, which loads no
; `.DRV` of any kind.
;
; **THIS IS WAVE 5 (docs/plans/CASSETTE-PLAN.md 15) AND THE TRANSPORT IS
; FAKE.** `apps/tape/tapexfr.inc` has two arms: `-DTAPE_FAKE` moves records
; to and from a memory buffer with the ROM's own semantics, and the real
; `int 15h` bracket is wave 6. Everything else here - the layout, the buttons,
; the greying, the state machine, the coast, the format and all 29 of SPEC.md
; 88.9's checks - is the shipping code, exercised through that seam, which is
; the only kind of verification a feature with no emulator can have before it
; meets a deck (SPEC.md 88.11).
;
; WHAT IT IS MADE OF:
;   tape.asm       this: the window, the state machine, the file I/O
;   tapefmt.inc    the record format and every hostile-input check (88.4, 88.9)
;   tapeui.inc     the layout, computed from OSAPI_WM_GEOM, and the painters
;   tapexfr.inc    the transport (88.2), and the ONE routine wave 6 replaces
;   reels.inc      eight 16x16 masked hub phases (88.8.1)
;
; THE THREE THINGS TO KNOW BEFORE CHANGING ANYTHING HERE:
;
;  1. **The freeze is the design, not a defect** (SPEC.md 88.3). The IBM
;     cassette interface has no DMA - the 8088 IS the modem - so any interrupt
;     longer than 248 us corrupts the tape rather than slowing it. A record is
;     therefore 4 to 9 seconds with the scheduler, the mouse and every drawing
;     primitive switched off. What ships instead is four narrower promises,
;     and the state machine below is shaped entirely around them: the transfer
;     is cut into records, each interval is announced BEFORE it starts with
;     its length, between records the machine is entirely alive, and Stop is
;     honoured at the end of a block.
;
;  2. **The W_ONWAKE turn's order is the contract** (SPEC.md 88.8): coast,
;     check Stop, draw the freeze BEFORE it happens and draw only what
;     changed, RELEASE THE LOCK, file work, one record, advance. Releasing the
;     lock before the transfer is not an optimisation - gfx_lock hides the
;     cursor for the length of a hold, so holding it across the call would
;     take the arrow off the screen for nine seconds, and a vanished pointer
;     reads as a crash.
;
;  3. **Every byte off a tape is hostile, and worse than a disk's in three
;     ways** (SPEC.md 88.9): nobody but us has ever written one, there is no
;     mount to validate it, and a mis-synced read delivers somebody else's
;     data with a VALID CRC.
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'TAPE', tp_entry, OS88_F_ICON, OS88_STACK_192

; --- embedded 16x16 icon (SPEC.md 20.2, flags bit 0) -------------------------
; A compact cassette: shell, two reel hubs, the label panel and the two
; capstan holes along the bottom edge.
;
;   data                          mask
;   ................              ................
;   ................              .##############.
;   .##############.              ################
;   .#............#.              ################
;   .#.###....###.#.              ################
;   .#.#.#....#.#.#.              ################
;   .#.###....###.#.              ################
;   .#............#.              ################
;   .#.##########.#.              ################
;   .#.#........#.#.              ################
;   .#.##########.#.              ################
;   .##############.              ################
;   ..#.#....#.#....              ################
;   ................              .###.#####.##...
;   ................              ................
;   ................              ................
    OS88_ICON16
    dw 0x0000                       ; 16 mask rows
    dw 0xFFFF
    dw 0xFFFF
    dw 0xFFFF
    dw 0xFE7F
    dw 0xFE7F
    dw 0xFE7F
    dw 0xFFFF
    dw 0xFFFF
    dw 0xFFFF
    dw 0xFFFF
    dw 0xFFFF
    dw 0xFFFF
    dw 0x7CF8
    dw 0x0000
    dw 0x0000
    dw 0x0000                       ; 16 data rows
    dw 0x0000
    dw 0x7FFE
    dw 0x4002
    dw 0x5C3A
    dw 0x542A
    dw 0x5C3A
    dw 0x4002
    dw 0x5FFA
    dw 0x500A
    dw 0x5FFA
    dw 0x7FFE
    dw 0x2850
    dw 0x0000
    dw 0x0000
    dw 0x0000
    OS88_ICON16_END

; --- the states -------------------------------------------------------------
TS_IDLE     equ 0
TS_CUE      equ 1               ; the cue-confirm alert is up
TS_RUN      equ 2               ; records in flight
TS_DONE     equ 3
TS_ERR      equ 4

; ...the modes, which are the three radios
TM_SAVE     equ 0
TM_LOAD     equ 1
TM_CAT      equ 2

; ...and the phase within TS_RUN
TR_STAGE    equ 0               ; claim, read, classify, compress, geometry
TR_REC      equ 1               ; one record per turn
TR_ASK      equ 2               ; a question is up; the answer continues
TR_COMMIT   equ 3

TP_SCAN_KB  equ 2               ; the classify buffer: 5 x 256 must fit it
TP_SLACK_KB equ 5               ; the record buffer, at recblk = 4: FIVE times
                                ; the record, because that is the most the ROM
                                ; can write (SPEC.md 88.4.3)
TP_CAT_MAX  equ 40              ; how far a Catalog scans before it stops on
                                ; its own. A tape has no end mark, so the only
                                ; other ends are AH=04 and the user

; -----------------------------------------------------------------------------
; tp_entry - the loader's entry point
; out: BX = window ptr, CF=0; CF=1 = abort (wm_create refused)
;
; SPEC.md 88.1's two gates run ONCE, here, into one cached byte, so SPEC.md 47
; rule 5's cost corollary - a greying test runs on every paint - is satisfied
; by construction. They run BEFORE any window is shown and before any sound
; can be playing.
;
; The CF is CLEARED EXPLICITLY on the way out rather than inherited: of the
; six slots installed below, OSAPI_WM_ONDRAG answers CF=1 on kern_small (it
; carries the slot and not the body), and an entry proc that let that reach
; the loader would abort the launch on the 128 KB machine this feature is
; named after.
; -----------------------------------------------------------------------------
tp_entry:
    call tp_detect
    mov si, tp_tpl
    call OSAPI_WM_CREATE            ; BX = window ptr, CF = the table is full
    jc .fail
    mov [tp_win], bx
    mov ax, tp_onup                 ; the buttons fire on the RELEASE, over the
    call OSAPI_WM_ONMOUSEUP         ; control the press landed on (SPEC.md
    mov ax, tp_ondrag               ; 13.7), and TRACK between the two edges
    call OSAPI_WM_ONDRAG            ; (13.8.2). NO CAPABILITY TEST: on
                                    ; kern_small the control still goes down on
                                    ; the press and up on the release, which IS
                                    ; the static fallback
    mov ax, tp_onwake
    call OSAPI_WM_ONWAKE            ; the one callback that runs on the UI task
                                    ; WITHOUT the gfx lock, and the only place
                                    ; a package may do file work (20.6 rule 7)
    mov ax, tp_onclose
    call OSAPI_WM_ONCLOSE
    mov si, tp_prefer               ; SPEC.md 88.8: a fixed 320x146 content box
    call OSAPI_WM_PREFER            ; does not fit CGA, which is the adapter of
                                    ; the machine class this is named after
    mov si, tp_about
    call OSAPI_ABOUT_SET
    mov si, tp_menus
    call OSAPI_MENU_SET
    mov bx, [tp_win]
    clc
    ret
.fail:
    stc
    ret

; -----------------------------------------------------------------------------
; tp_paint - W_PAINT
; in:  SI = window ptr; the gfx lock is held and the content is already white
; out: nothing; every register preserved
; -----------------------------------------------------------------------------
tp_paint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    call tp_layout                  ; every rect, from the LIVE geometry
    jc .out
    call tp_draw_all
    cmp byte [tp_abon], 0           ; ...and the About card LAST, over the face
    je .out                         ; it is opaque about (SPEC.md 20.5.1)
    push si
    mov si, tp_ablines
    call os88ui_about_d             ; _d: this paint's region is already armed
    pop si
.out:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_onclick - W_ONCLICK: it ARMS and does not act (SPEC.md 13.8.3)
; in:  CX = x, DX = y (screen), SI = window; the gfx lock is HELD
; out: nothing; every register preserved
; -----------------------------------------------------------------------------
tp_onclick:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call tp_abdismiss               ; the credits are up: this click is spent
    jc .out                         ; taking them down
    mov bx, si
    call OSAPI_WM_CLIP_SET          ; nothing armed a region for a CLICK either
    jc .out                         ; (SPEC.md 11.3)
    push cx
    push dx
    call tp_layout
    pop dx
    pop cx
    jc .out
    mov ax, TP_NRECT
    mov bx, tp_rects
    call os88ui_bfind               ; AX = the control + 1, 0 = none
    call os88ui_arm                 ; ...and that is ALL a press acts on
    call tp_setdown                 ; what it DRAWS is the pressed state
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_ondrag - W_ONDRAG: the pointer moved, the press is still down
; in:  CX = x, DX = y (screen), SI = window; the gfx lock is HELD
; out: nothing; every register preserved
;
; The same question tp_onup asks at the release, one pass early, so what is
; drawn pressed is exactly what would fire. REDRAW ONLY ON A CHANGE - this is
; called per pointer packet, and tp_setdown is the one writer that enforces it.
; -----------------------------------------------------------------------------
tp_ondrag:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call os88ui_armed               ; PEEK: the arm is the release's to spend
    or ax, ax
    jz .out
    mov di, ax
    mov bx, si
    call OSAPI_WM_CLIP_SET
    jc .out
    push cx
    push dx
    call tp_layout                  ; the window may have moved since the press
    pop dx
    pop cx
    jc .out
    mov ax, TP_NRECT
    mov bx, tp_rects
    call os88ui_bfind
    cmp ax, di
    je .same
    xor ax, ax                      ; off it: nothing is down
.same:
    call tp_setdown
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_onup - W_ONMOUSEUP: the control fires HERE (SPEC.md 13.7)
; in:  CX = x, DX = y (screen), SI = window; the gfx lock is HELD
; out: nothing; every register preserved
;
; It puts the control UP FIRST and unconditionally, then fires only if the
; release landed on the same one - so a mis-aimed press can be slid off and
; cancelled, and a missed release can leave nothing drawn down.
; -----------------------------------------------------------------------------
tp_onup:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call os88ui_fire                ; AX = what was armed, and it is CLEARED
    mov di, ax
    mov bx, si
    call OSAPI_WM_CLIP_SET
    jc .out
    push cx
    push dx
    call tp_layout
    pop dx
    pop cx
    jc .out
    xor ax, ax
    call tp_setdown                 ; UP first, and unconditionally
    or di, di
    jz .out
    mov ax, TP_NRECT
    mov bx, tp_rects
    call os88ui_bfind
    cmp ax, di
    jne .out                        ; released somewhere else: a cancel, and
    call tp_act                     ; it draws nothing
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_setdown - THE ONE WRITER of [tp_down], and it draws nothing if the answer
; did not change (SPEC.md 88.8.2)
; in:  AX = the control + 1, 0 = none; the clip is armed and the lock held
; out: nothing; every register preserved
;
; The two groups are redrawn rather than the one control, which is recorder's
; discipline and its reason: it keeps the enable rules in a single place, and
; a press is a human-rate event.
; -----------------------------------------------------------------------------
tp_setdown:
    cmp ax, [tp_down]
    je .out
    push ax
    mov [tp_down], ax
    call tp_draw_btns
    call tp_draw_togs
    pop ax
.out:
    ret

; -----------------------------------------------------------------------------
; tp_act - a control fired
; in:  AX = the control (1..TP_NRECT); the gfx lock is held, the clip is armed
; out: nothing; every register preserved
; -----------------------------------------------------------------------------
tp_act:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov bx, ax
    cmp bx, TP_B_CHOOSE
    je .choose
    cmp bx, TP_B_GO
    je .go
    cmp bx, TP_B_VERIFY
    je .verify
    cmp bx, TP_B_STOP
    je .stop
    cmp bx, TP_T_ZIP
    je .zip
    ; --- a mode radio -------------------------------------------------------
    call tp_tog_on
    jc .out
    sub bl, TP_T_SAVE
    cmp bl, [tp_mode]
    je .out
    mov [tp_mode], bl
    mov word [tp_msg], 0
    call tp_redraw                  ; the footer's second line and the greying
    jmp short .out                  ; both follow the mode
.zip:
    call tp_tog_on
    jc .out
    xor byte [tp_wantz], 1
    call tp_draw_togs
    jmp short .out
.choose:
    mov al, TP_B_CHOOSE - 1
    call tp_btn_on
    jc .out
    call tp_cmd_choose
    jmp short .out
.go:
    mov al, TP_B_GO - 1
    call tp_btn_on
    jc .out
    mov byte [tp_doverify], 0
    call tp_cmd_go
    jmp short .out
.verify:
    mov al, TP_B_VERIFY - 1
    call tp_btn_on
    jc .out
    mov byte [tp_doverify], 1
    call tp_cmd_go
    jmp short .out
.stop:
    mov al, TP_B_STOP - 1
    call tp_btn_on
    jc .out
    call tp_cmd_stop
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_redraw / tp_repaint - the whole face
;   tp_redraw    the lock is HELD and the clip is armed (a click, a menu, a
;                dialog completion) - erase and draw
;   tp_repaint   from a wake, where neither is true: go through the burst
; out: nothing; every register preserved
; -----------------------------------------------------------------------------
tp_redraw:
    call tp_erase
    call tp_draw_all
    ret

tp_repaint:
    push bp
    mov bp, tp_redraw
    call tp_paint_now
    pop bp
    ret

; -----------------------------------------------------------------------------
; tp_show - repaint, WHICHEVER CONTEXT THIS IS
; out: nothing; every register preserved
;
; **THE ONE THING THIS PACKAGE GOT WRONG TWICE AND THE FIELD WOULD HAVE SEEN
; AS A DEAD MACHINE.** The state machine's endings are reached from two places
; that differ in exactly one thing: a W_ONWAKE turn holds NO gfx lock, and an
; alert completion, a click and a menu command all hold it already. Taking it
; again from a callback deadlocks the UI task against itself - the CPU sits in
; sch_switch, the pointer still moves because the mouse ISR draws it, and
; nothing else in the machine ever happens again. It reads exactly like a
; hang in the transfer, which is the one thing this package is expected to
; look like anyway.
;
; So the flag is set for the length of the wake turn and this is what every
; ending calls. A caller that KNOWS which side it is on may still call
; tp_redraw (the lock is held and a clip is armed) or tp_repaint directly.
; -----------------------------------------------------------------------------
tp_show:
    push ax
    push bx
    push si
    cmp byte [tp_inwake], 0
    jne .burst
    mov bx, [tp_win]
    call OSAPI_WM_CLIP_SET      ; the lock is our caller's; nothing has armed
    jc .out                     ; a region for a completion either
    mov si, [tp_win]
    call tp_layout
    jc .out
    call tp_redraw
    jmp short .out
.burst:
    call tp_repaint
.out:
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_cmd_choose - the Standard File dialog (SPEC.md 38)
; in:  the gfx lock is held (a click or a menu command)
; out: nothing; every register preserved
; -----------------------------------------------------------------------------
tp_cmd_choose:
    push ax
    push bx
    push si
    push di
    mov al, FDLG_OPEN
    mov bx, [tp_win]
    mov di, tp_dlgdone
    xor si, si
    call OSAPI_FILE_DLG
    pop di
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_dlgdone - the dialog's completion
; in:  AL = the mode it ran in, SI = our window, DI = the chosen name (ES =
;      KERNEL_SEG, and the buffer is the kernel's for the duration of this
;      call only - COPY IT), DX:CX = that file's size
;      The UI task, the gfx lock HELD, and WE must repaint our own content
; out: nothing; no register need be preserved
; -----------------------------------------------------------------------------
tp_dlgdone:
    mov si, di
    mov di, tp_name
    mov cx, 12
.copy:
    mov al, [es:si]
    mov [di], al
    or al, al
    jz .copied
    inc si
    inc di
    loop .copy
.copied:
    mov byte [tp_name+12], 0
    mov word [tp_msg], 0
    call tp_classify                ; the RAW on-disk size and the 'CZ' bit -
    jnc .ok                         ; free, out of the directory sector the
    mov byte [tp_name], 0           ; walk was holding anyway (SPEC.md 88.7)
    mov word [tp_msg], tp_s_nosrc
    jmp short .paint
.ok:
    mov ax, [tp_rawsize]
    mov [tp_size], ax
    mov [tp_usize], ax
    call tp_namefits                ; SPEC.md 88.4.1's field is 12 BYTES and a
    jnc .sized                      ; maximal 8.3 name is 12 CHARACTERS
    mov word [tp_msg], tp_s_longname
    mov byte [tp_name], 0
    jmp short .paint
.sized:
    cmp ax, TP_MAXFILE
    jbe .paint
    call tp_msg_toobig              ; ...with the arithmetic on the glass,
    mov byte [tp_name], 0           ; never a bare "cannot" (SPEC.md 88.7)
.paint:
    mov bx, [tp_win]
    call OSAPI_WM_CLIP_SET
    jc .out
    mov si, [tp_win]
    call tp_layout
    jc .out
    call tp_redraw
.out:
    ret

; -----------------------------------------------------------------------------
; tp_classify - SPEC.md 88.7's classification, in one directory walk
; in:  [tp_name]
; out: CF=0 and [tp_rawsize] = the size the file OCCUPIES, [tp_srccz] = 1 if it
;      is already a 'CZ' container; CF=1 no such file, a folder, or a size no
;      16-bit reader could hold
;      Every register but AX preserved
;
; It is OSAPI_FILE_FIND_RAW and not OSAPI_FILE_FIND because the tape carries
; **exactly the bytes that will land on the destination disk** (SPEC.md 88.7):
; the raw size is the one that goes with OSAPI_FILE_READ_AT, and expanding on
; the way out would LOSE the compression the file already has.
; -----------------------------------------------------------------------------
tp_classify:
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov ax, ds
    mov es, ax                      ; the find buffer is ours
    xor cx, cx
.next:
    mov di, tp_find
    call OSAPI_FILE_FIND_RAW        ; CX = the next ordinal on the way out
    jc .none
    mov si, tp_name
    mov di, tp_find
    call tp_namecmp
    jne .next
    cmp word [tp_find+14], OSAPI_FT_DIR
    jae .none                       ; "is this a file" is `type < FT_DIR`, and
    cmp word [tp_find+20], 0        ; type 1 is a PACKAGE rather than "a file"
    jne .none                       ; a size over 65,535: not ours to carry
    mov ax, [tp_find+18]
    mov [tp_rawsize], ax
    mov byte [tp_srccz], 0
    test word [tp_find+22], OSAPI_FIND_CZ
    jz .plain
    mov byte [tp_srccz], 1
.plain:
    clc
    jmp short .out
.none:
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; tp_namecmp - DS:SI against DS:DI, NUL-terminated, case-folded
; out: ZF=1 equal; every register preserved
tp_namecmp:
    push ax
    push bx
    push si
    push di
.ch:
    mov al, [si]
    mov bl, [di]
    call .up
    xchg al, bl
    call .up
    xchg al, bl
    cmp al, bl
    jne .out
    or al, al
    jz .out
    inc si
    inc di
    jmp short .ch
.out:
    pop di
    pop si
    pop bx
    pop ax
    ret
.up:
    cmp al, 'a'
    jb .noup
    cmp al, 'z'
    ja .noup
    sub al, 32
.noup:
    ret

; -----------------------------------------------------------------------------
; tp_cmd_go - the estimate, then the cue-confirm (SPEC.md 88.8.2)
; in:  the gfx lock is held and the clip is armed
; out: nothing; every register preserved
;
; **THE ESTIMATE IS SHOWN BEFORE START, ON EVERY OPERATION, AND THE
; CUE-CONFIRM IS NOT CEREMONY**: starting the relay without RECORD engaged
; wastes five minutes and produces a blank tape that reads as a bug.
; -----------------------------------------------------------------------------
tp_cmd_go:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    cmp byte [tp_state], TS_RUN
    je .out
    cmp byte [tp_state], TS_CUE
    je .out
    mov word [tp_msg], 0
    call tp_isread
    je .read
    cmp byte [tp_name], 0
    jne .est
    mov word [tp_msg], tp_s_pick
    call tp_redraw
    jmp short .out
.est:
    call tp_est_line                ; "NAME - 20 blocks, about 3:05"
    mov si, tp_q_save
    jmp short .ask
.read:
    mov word [tp_msg], tp_s_cueread
    mov si, tp_q_read
.ask:
    push si
    mov byte [tp_state], TS_CUE     ; the greying moves BEFORE the alert opens:
    call tp_redraw                  ; a repaint afterwards would draw over it
    pop si
    mov al, OS88UI_AYESNO
    mov bx, [tp_win]
    mov di, tp_cuedone
    call os88ui_ask
    jnc .out
    mov byte [tp_state], TS_IDLE    ; one is already up, and it has been RAISED
    mov word [tp_msg], tp_s_busy
    call tp_redraw
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_cuedone - the cue-confirm's answer
; in:  AL = the button index, or OS88UI_ACANCEL; SI = our window; the lock is
;      held and the alert is already destroyed
; -----------------------------------------------------------------------------
tp_cuedone:
    cmp byte [tp_state], TS_CUE
    jne .out
    or al, al
    jz .start                       ; index 0 = Yes = the DEFAULT
    mov byte [tp_state], TS_IDLE
    mov word [tp_msg], 0
    call tp_show
    ret
.start:
    call tp_start
.out:
    ret

; -----------------------------------------------------------------------------
; tp_start - take the deck, and post the first turn
; out: nothing; every register preserved
;
; **THE CLAIM IS WHAT REFUSES A SECOND TAPE WINDOW** (SPEC.md 88.5). Packages
; are multi-instance by default; two Tape windows share one deck, one motor
; bit, one PIC mask and one channel 0, and between one window's records the
; machine is fully alive - so the other's W_ONWAKE could start a record of its
; own and interleave its blocks into the first one's tape, which `AH=03`
; cannot report. AH = 3 is that refusal arriving in words.
;
; SPEC.md 88.2 puts the claim inside tp_xfer, on the first record. It is here
; instead, and the difference is ordering rather than behaviour: SPEC.md
; 88.8.2 requires Go to refuse in WORDS when another window holds the deck,
; and a claim taken inside the transfer would first have to coast, paint and
; announce a record it was about to refuse.
; -----------------------------------------------------------------------------
tp_start:
    push ax
    push bx
    mov al, OSAPI_PL_CLAIM
    call OSAPI_PIT_LEND
    jnc .got
    mov bx, tp_s_pitfast            ; AH = 1: [sch_fast] has moved ch0's
    cmp ah, 1                       ; divisor, so the restore could not survive
    je .no                          ; the round trip - the answer is no, not
    mov bx, tp_s_pitsnd             ; "probably"
    cmp ah, 2
    je .no
    mov bx, tp_s_pitheld
.no:
    mov [tp_msg], bx
    mov byte [tp_state], TS_IDLE
    call tp_show
    jmp short .out
.got:
    mov byte [tp_stop], 0
    mov word [tp_step], 0
    mov byte [tp_run], TR_STAGE
    mov byte [tp_state], TS_RUN
    mov byte [tp_phase], 0
    mov word [tp_cellip], 0xFFFF
    mov word [tp_nrecs], 0
    mov word [tp_total], 0
    mov word [tp_msg], 0
    call tp_show                    ; **THE GREYING HAPPENS ONCE, HERE** and
                                    ; does not change again until the transfer
                                    ; ends: repainting the controls per record
                                    ; is ~50 ms and five visible flickers, 34
                                    ; times over (SPEC.md 88.8, 77.17)
    mov bx, [tp_win]
    call OSAPI_WM_WAKE
.out:
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_cmd_stop - what Stop does, precisely, at each moment (SPEC.md 88.8.2)
; out: nothing; every register preserved
;
; During the coast it is LATCHED and the transfer parks before the next
; record - at most 560 ms. Mid-record a mouse click is PHYSICALLY LOST, IRQ3
; and IRQ4 being masked and the 8250 one byte deep with no FIFO, which is why
; the footer says "Stop takes effect at the end of a block" rather than
; promising something the hardware cannot do.
; -----------------------------------------------------------------------------
tp_cmd_stop:
    push ax
    cmp byte [tp_state], TS_CUE
    jne .run
    mov byte [tp_state], TS_IDLE
    mov word [tp_msg], 0
    call tp_redraw
    jmp short .out
.run:
    cmp byte [tp_state], TS_RUN
    jne .out
    mov byte [tp_stop], 1
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_onwake - ONE TURN, and the order IS the contract (SPEC.md 88.8)
; in:  SI = our window; the UI task, and THE GFX LOCK IS NOT HELD
; out: nothing; every register preserved
;
;   1. TS_COAST - 8 decelerating frames, 560 ms, [tp_stop] polled between them
;   2. check [tp_stop]; if set, tidy and do NOT re-post
;   3. DRAW THE FREEZE BEFORE IT HAPPENS, AND DRAW ONLY WHAT CHANGED, then
;      RELEASE THE GFX LOCK - the part that matters
;   4. file-half work, if this state has any: legal, because W_ONWAKE is on the
;      UI task and holds no lock (SPEC.md 20.6 rule 7)
;   5. ONE record through tp_xfer                        <-- THE FREEZE
;   6. advance the state; OSAPI_WM_WAKE to come back - or stop
;
; **RE-POST ONLY WHILE THERE IS WORK.** A handler that always re-posts spins
; the UI task (SPEC.md 74.1).
; -----------------------------------------------------------------------------
tp_onwake:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov byte [tp_inwake], 1         ; ...which is what tp_show reads: this turn
                                    ; holds NO gfx lock and every other entry
                                    ; into the state machine holds one
    cmp byte [tp_state], TS_RUN
    jne .out
    cmp byte [tp_run], TR_ASK
    je .out                         ; a question is up; its answer re-posts
    cmp byte [tp_run], TR_STAGE
    jne .turn
    call tp_stage                   ; claim, read, classify, compress, geometry
    jc .out                         ; it has already said why and finished
    mov byte [tp_run], TR_REC
    mov word [tp_step], 0
    jmp short .post
.turn:
    call tp_coast                   ; 1
    cmp byte [tp_stop], 0           ; 2
    je .live
    call tp_stopped
    jmp short .out
.live:
    call tp_prefreeze               ; 3
    call tp_step_one                ; 4 and 5
    jc .out                         ; the operation ended, either way
.post:
    mov bx, [tp_win]                ; 6
    call OSAPI_WM_WAKE              ; **RE-POST ONLY WHILE THERE IS WORK**
.out:
    mov byte [tp_inwake], 0
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_prefreeze - step 3: the block in flight, and the two numbers. NOT the
; caption, and NOT the greying
; out: nothing; every register preserved
;
; ~7 ms in total: one small gfx_fill for the progress cell and four cells of
; font_run for the two fixed-width numbers. The lock is released by
; tp_paint_now on the way out, which is the part that matters - gfx_lock hides
; the cursor for the length of a hold, and a pointer that vanishes for nine
; seconds reads as a crash.
; -----------------------------------------------------------------------------
tp_prefreeze:
    push ax
    push bp
    mov ax, [tp_step]
    mov [tp_cellip], ax
    mov bp, tp_prefreeze_draw
    call tp_paint_now
    pop bp
    pop ax
    ret

tp_prefreeze_draw:
    push ax
    mov ax, [tp_cellip]
    call tp_draw_cell
    call tp_draw_nums
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_stopped - Stop was latched during the coast
; out: nothing; every register preserved
; -----------------------------------------------------------------------------
tp_stopped:
    push ax
    push di
    call tp_endop
    mov di, tp_line3
    mov si, tp_s_stopped
    call tp_app
    mov ax, [tp_step]
    inc ax
    call tp_numl
    mov si, tp_s_of
    call tp_app
    mov ax, [tp_nrecs]
    call tp_numl
    mov byte [di], '.'
    inc di
    mov byte [di], 0
    mov word [tp_msg], tp_line3
    cmp byte [tp_mode], TM_SAVE
    jne .done
    mov word [tp_msg], tp_s_stopw   ; a partial file IS on the tape, and it
.done:                              ; cannot be read back (SPEC.md 88.8.2)
    mov byte [tp_state], TS_DONE
    call tp_show
    pop di
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_isread - is the operation in flight a READ?
; out: ZF=1 a read - Load, Catalog, or a VERIFY in any mode; every register
;      preserved
;
; **VERIFY IS THE READ PATH WITH THE COMMIT REPLACED BY A COMPARISON**
; (SPEC.md 88.8.2), and it is reachable from Save mode - which is where it is
; wanted, since it is the default prompt after every write. So the direction
; of the transfer is NOT [tp_mode] alone, and reading it as though it were is
; a Verify that writes the file to the tape a second time: the staging, the
; per-record work and the reels' direction all ask this instead.
; -----------------------------------------------------------------------------
tp_isread:
    push ax
    mov al, 1
    cmp byte [tp_doverify], 0
    jne .out
    mov al, 0
    cmp byte [tp_mode], TM_SAVE
    je .out
    mov al, 1
.out:
    cmp al, 1                       ; ZF = 1 exactly when it is a read
    pop ax                          ; (a pop writes no flags)
    ret

; -----------------------------------------------------------------------------
; tp_namefits - will this name survive the tape's 12-byte field?
; out: CF=0 it fits; CF=1 it does not. Every register preserved
;
; **SPEC.md 88.4.1's `name` FIELD IS ONE BYTE TOO SHORT FOR A FULL 8.3 NAME**
; and this is where that lands. The field is 12 bytes "NUL-terminated inside
; 12 bytes" (row 8), and a maximal 8.3 name - eight, a dot, three - is twelve
; CHARACTERS, so it needs thirteen. tools/os88tape.py has the same bound from
; the same sentence (`len(raw) > 11` is its refusal), so the two agree and
; neither can carry TAPEDATA.TXT.
;
; The honest answer for wave 5 is to REFUSE IT ON THE WAY OUT, in words, and
; leave the format alone: a writer that quietly filled all twelve bytes would
; make tapes this reader - and the host codec - correctly refuse, which is a
; worse failure than not writing them.
; -----------------------------------------------------------------------------
tp_namefits:
    push ax
    push si
    mov si, tp_name
    mov ax, 0
.next:
    cmp byte [si], 0
    je .done
    inc si
    inc ax
    cmp ax, 12
    jbe .next
.done:
    cmp ax, 12                      ; 11 characters plus the NUL is the field,
    cmc                             ; and `cmp` answers this the wrong way
    pop si                          ; round: CF=1 for a name SHORTER than 12 is
    pop ax                          ; exactly the case that fits
    ret

; -----------------------------------------------------------------------------
; tp_endop - give everything back, on every path out of a transfer
; out: nothing; every register preserved
;
; OSAPI_PL_RELEASE is IDEMPOTENT, which is what makes calling it blind here
; legal (SPEC.md 88.5) - and this routine is reached from the refusals as well
; as from the finishes, which is SPEC.md 88.2 step 17.
; -----------------------------------------------------------------------------
tp_endop:
    push ax
    push dx
    call tp_motor_off               ; the relay is on somebody's tape deck
    mov al, OSAPI_PL_RELEASE
    call OSAPI_PIT_LEND
    mov dx, [tp_pseg]
    or dx, dx
    jz .norec
    call OSAPI_MEM_FREE
    mov word [tp_pseg], 0
.norec:
    mov dx, [tp_rseg]
    or dx, dx
    jz .out
    call OSAPI_MEM_FREE
    mov word [tp_rseg], 0
    mov word [tp_rkb], 0
.out:
    mov word [tp_cellip], 0xFFFF
    mov byte [tp_doverify], 0       ; ...so the NEXT Go is a Go
    mov byte [tp_run], TR_COMMIT    ; ...and a stale TR_ASK cannot outlive the
                                    ; question it belonged to: tp_onwake drops
                                    ; every wake while that phase is set
    pop dx
    pop ax
    ret

; tp_claim_r - the record buffer, AX KB. It is claimed and re-claimed, because
; SPEC.md 88.9 row 5 sizes it from the header's OWN recblk at read time
tp_claim_r:
    push dx
    push cx
    mov cx, ax
    mov dx, [tp_rseg]
    or dx, dx
    jz .fresh
    cmp cx, [tp_rkb]
    jbe .have
    call OSAPI_MEM_FREE
    mov word [tp_rseg], 0
.fresh:
    mov ax, cx
    call OSAPI_MEM_CLAIM            ; PINNED: MC_RLOC = 0 is the default and
    jc .out                         ; must stay, a compaction between the call
    mov [tp_rseg], dx               ; and the ROM's first `mov al, es:[bx]`
    mov [tp_rkb], cx                ; moving the buffer under the ROM
.have:
    clc
.out:
    pop cx
    pop dx
    ret

; -----------------------------------------------------------------------------
; tp_stage - TR_STAGE: everything that happens before the first record
; out: CF=1 the operation ended here and has said why
;      Every register preserved
;
; **STAGING IS WHOLE-FILE, IN ONE PINNED CLAIM, BOTH DIRECTIONS** (SPEC.md
; 88.7). That shape is the only one in which `ckfile` is verified before any
; file is created, so a corrupt tape leaves nothing behind rather than a
; half-written file.
; -----------------------------------------------------------------------------
tp_stage:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call tp_isread
    jne .save
    ; --- a READ needs only the classify buffer: 5 x 256 must fit it --------
    mov ax, TP_SCAN_KB
    call tp_claim_r
    jc .nomem
    call tp_rewind
    mov word [tp_scanned], 0
    mov byte [tp_nrec], 0
    mov word [tp_nrecs], 0
    mov byte [tp_name], 0           ; **A READ FORGETS THE CHOSEN FILE**, and
                                    ; that is the honest state rather than a
                                    ; convenience: a Load's name comes off the
                                    ; TAPE and a Catalog has no file at all, so
                                    ; carrying the Save side's pick through
                                    ; would leave the file line naming a file
                                    ; this operation is not about. Go greys
                                    ; itself until one is chosen again, which
                                    ; is SPEC.md 47's rule working (it is a
                                    ; FACT that there is no file, not a guess)
    jmp .ok
.save:
    ; --- row 9's first half, with the arithmetic on the glass ---------------
    mov ax, [tp_size]
    or ax, ax
    jz .nosrc
    cmp ax, TP_MAXFILE
    ja .toobig
    ; --- OSAPI_FILE_DFREE is asked ONCE PER OPERATION and banked (88.7). It
    ; does no disk I/O and that is NOT the same as cheap: it counts every
    ; entry in the resident FAT snapshot, ~105 ms on a 20MB disk ------------
    call OSAPI_FILE_DFREE           ; DX:AX = free bytes, BX = sectors/cluster
    jc .noroom
    shr bx, 1
    or bx, bx
    jnz .cl
    inc bx                          ; a 512-byte cluster is still 1 KB of claim
.cl:
    mov [tp_clkb], bx
    ; --- the claim: payloadKB, rounded up to a whole number of clusters ----
    mov ax, [tp_size]
    add ax, 1023
    mov cl, 10
    shr ax, cl
    call tp_roundcl                 ; ...so OSAPI_FILE_READ_AT's cluster-
    mov [tp_pkb], ax                ; multiple rule is satisfied by the SIZE of
    call OSAPI_MEM_CLAIM            ; the claim rather than by a second buffer
    jc .nomem
    mov [tp_pseg], dx
    mov ax, TP_SLACK_KB
    call tp_claim_r
    jc .nomem
    ; --- read it RAW: the tape carries exactly the bytes that will land on
    ; the destination disk, wrapper and all (SPEC.md 88.7) ------------------
    mov es, [tp_pseg]
    xor bx, bx
    mov ax, [tp_pkb]
    mov cl, 10
    shl ax, cl
    mov cx, ax                      ; CX = the claim in bytes, a cluster
    mov si, tp_name                 ; multiple by construction
    xor dx, dx
    xor ax, ax
    call OSAPI_FILE_READ_AT
    jc .noread
    ; --- the classification, one bit and no extra I/O (SPEC.md 88.7) -------
    mov byte [tp_flags], 0
    mov ax, [tp_size]
    mov [tp_usize], ax
    cmp byte [tp_srccz], 0
    je .notcz
    mov byte [tp_flags], TP_F_PRECOMP   ; ALREADY COMPRESSED: carry it RAW
    jmp short .geom
.notcz:
    call tp_ext_img
    jc .plain
    ; A package or driver IMAGE. **CARRY IT VERBATIM AND NEVER WRAP IT** -
    ; wrapping one would make a file ld_check_hdr cannot start (SPEC.md
    ; 22.22.1), and SPEC.md 88.9 row 21 refuses it on the way back too
    mov es, [tp_pseg]
    cmp word [es:0], TP_HDR_M0
    jne .geom
    test byte [es:3], 8             ; the header's own "already packed" bit
    jz .geom
    mov byte [tp_flags], TP_F_PRECOMP
    jmp short .geom
.plain:
    cmp byte [tp_wantz], 0
    je .geom                        ; THE ONLY case where compressing buys
    call tp_compress                ; anything (SPEC.md 88.7 step 4)
.geom:
    call tp_crcpay
    mov [tp_ckfile], dx
    mov ax, [tp_size]
    mov bl, TP_RECBLK
    mov [tp_recblk], bl
    call tp_geom
    jc .toobig
    mov [tp_nrec], ch
    mov [tp_lastblk], cl
    mov [tp_cap], dx
    mov al, ch
    mov ah, 0
    inc ax
    mov [tp_nrecs], ax              ; the header record is a cell of its own
.ok:
    mov word [tp_total], 0
    clc
    jmp short .out
.nosrc:
    mov word [tp_msg], tp_s_nosrc
    jmp short .stop
.toobig:
    call tp_msg_toobig
    jmp short .stop
.noread:
    mov word [tp_msg], tp_s_noread
    jmp short .stop
.noroom:
    mov word [tp_msg], tp_s_nodisk
    jmp short .stop
.nomem:
    call tp_msg_nomem
.stop:
    call tp_endop
    mov byte [tp_state], TS_ERR
    call tp_setretry
    call tp_show
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

; tp_roundcl - AX KB, rounded UP to a whole number of clusters
tp_roundcl:
    push bx
    push dx
    or ax, ax
    jnz .some
    inc ax
.some:
    mov bx, [tp_clkb]
    or bx, bx
    jnz .div
    inc bx
.div:
    add ax, bx
    dec ax
    xor dx, dx
    div bx
    mul bx
    pop dx
    pop bx
    ret

; -----------------------------------------------------------------------------
; tp_compress - SPEC.md 88.6's encoder, and 88.7's one place for it
; out: [tp_size], [tp_usize] and [tp_flags] updated if it paid; nothing changed
;      if it did not. Every register preserved
;
; **COMPRESSION PAYS FOR THE CHUNKING, AND THAT IS WHY IT IS NOT OPTIONAL**
; (SPEC.md 88.7): the responsive design is CHEAPER than the unresponsive one -
; 16,304 bytes plain in 1 KB records is 153 s, and 7,607 bytes of LZB in the
; same records is 75.7 s. The result is kept only if `packed + 8 < size`.
;
; A failure to compress is NOT a failure to transfer (SPEC.md 48.5's rule that
; a permanent refusal and a transient one must not be coded alike): mod_need
; goes to [dsk_bootvol] and only there, so on a one-floppy machine the system
; disk may simply not be in the drive - and then it says so and writes the file
; uncompressed.
; -----------------------------------------------------------------------------
tp_compress:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov word [tp_msg], tp_s_zip
    call tp_show                    ; paint the caption, RELEASE THE LOCK, then
                                    ; call: it is ~3.2 s and a lock held across
                                    ; it hides the pointer for all of it
    mov ax, [tp_pkb]
    call OSAPI_MEM_CLAIM
    jc .out                         ; no tables, no compression, no harm
    mov [tp_zseg], dx
    mov ax, [tp_pseg]
    mov cx, [tp_size]
    mov dx, [tp_zseg]
    call OSAPI_COMPRESS
    jc .refused
    mov [tp_packed], ax
    mov [tp_zfmt], bl
    add ax, TP_CZ_HDR
    cmp ax, [tp_size]
    jae .free                       ; it did not get smaller after the wrapper
    ; --- the stream into the payload claim, behind an 8-byte 'CZ' header ---
    mov cx, [tp_packed]
    mov ax, [tp_zseg]
    mov dx, [tp_pseg]
    push ds
    mov ds, ax                      ; both segments are read out of OUR ds
    mov es, dx                      ; before either is loaded
    xor si, si
    mov di, TP_CZ_HDR
    cld
    rep movsb
    pop ds
    mov es, [tp_pseg]
    mov word [es:0], TP_CZ_MAG
    mov al, [tp_zfmt]
    mov [es:2], al
    mov byte [es:3], 0
    mov ax, [tp_size]
    mov [es:4], ax                  ; the UNPACKED size, all 32 bits of it
    mov word [es:6], 0
    mov ax, [tp_packed]
    add ax, TP_CZ_HDR
    mov [tp_size], ax               ; ...and [tp_usize] keeps the original,
    mov byte [tp_flags], TP_F_CZ    ; which is what the file line prints
    cmp byte [tp_zfmt], 0
    je .free
    or byte [tp_flags], TP_F_LZB
    jmp short .free
.refused:
    cmp ax, OSAPI_CMP_NODISK
    jne .free
    mov si, tp_s_nozip              ; the SYSTEM disk is not in the boot drive:
    mov ax, ds                      ; refuse the COMPRESSION only
    mov es, ax
    xor cx, cx
    call OSAPI_TOAST
.free:
    mov dx, [tp_zseg]
    call OSAPI_MEM_FREE
    mov word [tp_zseg], 0
.out:
    mov word [tp_msg], 0
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; ONE RECORD PER TURN
; =============================================================================

; -----------------------------------------------------------------------------
; tp_step_one - steps 4 and 5 of the turn: the file half, then THE FREEZE
; out: CF=1 the operation is over (either way); CF=0 there is more to do
;      Every register preserved
; -----------------------------------------------------------------------------
tp_step_one:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    cmp byte [tp_mode], TM_CAT
    je .cat
    call tp_isread                  ; ...and a VERIFY is a read in Save mode
    je .read
    call tp_save_one
    jmp short .out
.read:
    call tp_load_one
    jmp short .out
.cat:
    call tp_cat_one
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
; tp_save_one - lay one record down
; out: CF=1 the operation is over
; -----------------------------------------------------------------------------
tp_save_one:
    mov ax, [tp_step]
    or ax, ax
    jnz .body
    call tp_hdr_lay                 ; the header record is EXACTLY one block,
    mov cx, TP_BLOCK                ; which is what makes 88.4.3's read-length
    jmp short .send                 ; invariant free
.body:
    call tp_body_lay                ; CX = the record's length in bytes
.send:
    mov es, [tp_rseg]
    xor bx, bx                      ; the ROM's inner loops do `INC BX` with no
    mov al, 3                       ; segment fixup, so BX = 0 and a claim base
    call tp_xfer                    ; is the only shape that is safe (row 27)
    jc .fail
    mov ax, [tp_step]
    inc ax
    mov [tp_step], ax
    mov bl, [tp_nrec]
    mov bh, 0
    cmp ax, bx
    ja .done
    clc
    ret
.done:
    call tp_save_done
    stc
    ret
.fail:
    call tp_failed
    stc
    ret

; -----------------------------------------------------------------------------
; tp_save_done - and THE APP NEVER SAYS "WRITTEN" (SPEC.md 88.8.2)
;
; `AH=03` returns AH = 0 unconditionally, so running off the end of the tape, a
; jammed deck, a disconnected cable, RECORD not engaged and a perfect recording
; are the same answer. Verify is the read path with the commit replaced by a
; comparison, and it is the default prompt after every write.
; -----------------------------------------------------------------------------
tp_save_done:
    push ax
    push si
    push di
    call tp_endop
    mov di, tp_line3
    mov ax, [tp_nrecs]
    call tp_numl
    mov si, tp_s_sent
    call tp_app
    mov byte [di], 0
    mov word [tp_msg], tp_line3
    mov byte [tp_state], TS_DONE
    call tp_show
    pop di
    pop si
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_load_one - read one record, and check every field it can lie about
; out: CF=1 the operation is over
; -----------------------------------------------------------------------------
tp_load_one:
    mov ax, [tp_step]
    or ax, ax
    jnz .body
    ; --- THE CLASSIFY READ: exactly 256 bytes, which consumes a header
    ; exactly and leaves the tape at the first body record ------------------
    mov es, [tp_rseg]
    xor bx, bx
    mov cx, TP_BLOCK
    mov al, 2
    call tp_xfer
    jc .fail
    mov es, [tp_rseg]
    call tp_hdr_parse               ; rows 1 to 11
    jc .nothdr
    call tp_load_prep               ; rows 5 and 9's machine halves
    jc .quit
    mov word [tp_step], 1
    clc
    ret
.nothdr:
    cmp al, TPE_MAGIC               ; not ours at all: name it and keep
    je .skip                        ; scanning, which is what a tape with
    cmp al, TPE_BASIC               ; other things on it needs
    je .skip
    call tp_msg_fmt                 ; ours, and malformed: REFUSED, and it
    jmp short .quit                 ; names the field
.skip:
    inc word [tp_scanned]
    mov ax, [tp_scanned]
    cmp ax, TP_CAT_MAX
    jb .again
    mov word [tp_msg], tp_s_nofound
    jmp short .quit
.again:
    clc
    ret
.body:
    mov al, [tp_step]
    call tp_blocks                  ; AX = blocks; NEVER a CX the header did
    mov cl, 8                       ; not declare (SPEC.md 88.4.3)
    shl ax, cl
    mov cx, ax
    mov es, [tp_rseg]
    xor bx, bx
    mov al, 2
    call tp_xfer
    jc .fail
    mov es, [tp_rseg]
    mov ax, [tp_step]
    call tp_body_parse              ; rows 12 to 18, then the copy
    jc .badbody
    mov ax, [tp_step]
    inc ax
    mov [tp_step], ax
    mov bl, [tp_nrec]
    mov bh, 0
    cmp ax, bx
    ja .commit
    clc
    ret
.commit:
    call tp_commit
    stc
    ret
.badbody:
    call tp_msg_fmt
    jmp short .quit
.fail:
    call tp_failed
    stc
    ret
.quit:
    call tp_endop
    mov byte [tp_state], TS_ERR
    call tp_setretry
    call tp_show
    stc
    ret

; -----------------------------------------------------------------------------
; tp_load_prep - rows 5 and 9's MACHINE halves, before a single body record
; out: CF=1 refused, and it has said why with the arithmetic
;
; Row 5's second clause: **the record buffer is 5 x recbytes**, five because
; that is the most the ROM can write (SPEC.md 88.4.3), and it is sized from
; the header's own recblk at read time - so a foreign recblk = 16 tape asks
; for 20 KB and is refused with the arithmetic on the glass rather than
; overrunning.
;
; Row 9's second and third clauses: the payload must fit the largest free run,
; and OSAPI_FILE_DFREE is asked ONCE and banked - before the first body record,
; because a refusal after nineteen of them is minutes of the user's time spent
; to say no.
; -----------------------------------------------------------------------------
tp_load_prep:
    push ax
    push bx
    push cx
    push dx
    mov al, [tp_recblk]
    mov ah, 0
    mov bx, 5
    mul bx
    add ax, 3
    mov cl, 2
    shr ax, cl                      ; ceil(recblk * 1280 / 1024) KB
    mov [tp_needkb], ax
    call tp_claim_r
    jc .nobuf
    call OSAPI_FILE_DFREE           ; DX:AX = free bytes, BX = sectors/cluster
    jc .nodisk
    or dx, dx
    jnz .room                       ; over 64 KB free: any payload of ours fits
    cmp ax, [tp_size]
    jb .nodisk
.room:
    shr bx, 1
    or bx, bx
    jnz .cl
    inc bx
.cl:
    mov [tp_clkb], bx
    mov ax, [tp_size]
    add ax, 1023
    mov cl, 10
    shr ax, cl
    call tp_roundcl
    mov [tp_pkb], ax
    mov [tp_needkb], ax
    call OSAPI_MEM_CLAIM
    jc .nomem
    mov [tp_pseg], dx
    mov al, [tp_nrec]
    mov ah, 0
    inc ax
    mov [tp_nrecs], ax
    mov word [tp_total], 0
    clc
    jmp short .out
.nobuf:
    call tp_msg_nomem
    stc
    jmp short .out
.nodisk:
    mov word [tp_msg], tp_s_nodisk
    stc
    jmp short .out
.nomem:
    call tp_msg_nomem
    stc
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_commit - the last record has arrived
; out: nothing (the operation ends here on every path)
;
; **`ckfile` IS CHECKED AFTER THE LAST RECORD AND BEFORE A BYTE REACHES THE
; DISK** (SPEC.md 88.4.2): a mismatch means the file is not created at all.
; -----------------------------------------------------------------------------
tp_commit:
    call tp_pay_check               ; rows 19, 20, 21 and 29
    jc .bad
    cmp byte [tp_doverify], 0
    jne .verify
    call tp_classify                ; is there already a file of that name?
    jc .write
    mov byte [tp_run], TR_ASK       ; **ASK BEFORE REPLACING** (row 28):
    call tp_ask_replace             ; OSAPI_FILE_WRITE replaces silently
    ret
.write:
    call tp_write_now
    ret
.verify:
    call tp_verify_now
    ret
.bad:
    call tp_msg_fmt
    call tp_endop
    mov byte [tp_state], TS_ERR
    call tp_setretry
    call tp_show
    ret

; -----------------------------------------------------------------------------
; tp_ask_replace - the one question that needs the lock from a wake
; The wake handler holds no lock, and os88ui_ask draws a window - so it takes
; the lock for a burst it can state and releases it, which is exactly what
; OSAPI_WM_ONWAKE's contract permits.
; -----------------------------------------------------------------------------
tp_ask_replace:
    push ax
    push bx
    push si
    push di
    push es
    call OSAPI_GFX_LOCK
    mov ax, KERNEL_SEG              ; **ES MUST BE THE KERNEL'S HERE.**
    mov es, ax                      ; os88ui_ask reads [es:bx + W_TITLE] to
                                    ; borrow our caption, and ES is only the
                                    ; kernel's ON ENTRY to a callback - by the
                                    ; time a W_ONWAKE turn reaches its commit
                                    ; it is the record buffer's, and the alert
                                    ; would take its title out of a tape record
    mov al, OS88UI_AYESNO
    mov bx, [tp_win]
    mov si, tp_q_repl
    mov di, tp_repldone
    call os88ui_ask
    pushf
    call OSAPI_GFX_UNLOCK
    popf
    jnc .out
    mov word [tp_msg], tp_s_busy    ; one is already up: nothing is written,
    call tp_endop                   ; which is the safe direction
    mov byte [tp_state], TS_ERR
    call tp_setretry
    call tp_show
.out:
    pop es
    pop di
    pop si
    pop bx
    pop ax
    ret

tp_repldone:
    cmp byte [tp_run], TR_ASK
    jne .out
    or al, al
    jz .yes
    mov word [tp_msg], tp_s_kept
    call tp_endop
    mov byte [tp_state], TS_DONE
    call tp_show
    ret
.yes:
    call tp_write_now
.out:
    ret

; -----------------------------------------------------------------------------
; tp_write_now - ONE OSAPI_FILE_WRITE, at the end (SPEC.md 88.7)
;
; dskw_name83 is the SINGLE validator of the name (SPEC.md 88.9 row 8): this
; hands the twelve bytes the tape declared straight to the slot and lets it
; answer FERR_NAME. There is no '_' substitution anywhere on this path -
; substituting on a WRITE silently targets a different file.
; -----------------------------------------------------------------------------
tp_write_now:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov si, tp_name
    mov es, [tp_pseg]
    xor bx, bx
    mov cx, [tp_size]
    xor dx, dx
    call OSAPI_FILE_WRITE
    jc .err
    mov di, tp_line3
    mov si, tp_name
    call tp_app
    mov si, tp_s_written
    call tp_app
    mov byte [di], 0
    mov word [tp_msg], tp_line3
    call tp_endop
    mov byte [tp_state], TS_DONE
    jmp short .paint
.err:
    mov [tp_ferr], ax
    mov di, tp_line3
    mov si, tp_s_wrfail
    call tp_app
    mov ax, [tp_ferr]
    call tp_numl
    mov byte [di], 0
    mov word [tp_msg], tp_line3
    call tp_endop
    mov byte [tp_state], TS_ERR
    call tp_setretry
.paint:
    call tp_show
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_verify_now - the read path with the commit replaced by a COMPARISON
; (SPEC.md 88.8.2)
;
; Every block CRC (the ROM's), every preamble field, `ckfile` over the
; assembled payload - and then `ckfile` against a fresh CRC over the file as it
; sits on disk, RAW. A pass proves *the tape holds this file*, which is what a
; write can never say: `AH=03` returns 0 unconditionally.
;
; **THE LAST CLAUSE HAS A HOLE SPEC.md 88.8.2 DOES NOT NAME**, and it is
; stated rather than papered over: when the writer COMPRESSED the file
; (88.7 step 4), the tape's payload is a 'CZ' container and the disk's bytes
; are the plain file, so their CRCs cannot agree and never should. The tape's
; own checksum has still been verified end to end; what cannot be done is the
; comparison with the disk, and the sentence says which of the two it did.
; -----------------------------------------------------------------------------
tp_verify_now:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    test byte [tp_flags], TP_F_CZ
    jnz .czonly
    call tp_classify                ; the file's RAW size, by the tape's name
    jc .nofile
    mov ax, [tp_rawsize]
    cmp ax, [tp_size]
    jne .differ
    call tp_crcdisk                 ; DX = the CRC over the file on disk
    jc .noread
    cmp dx, [tp_ckfile]
    jne .differ
    mov si, tp_s_vok
    jmp short .say
.czonly:
    mov si, tp_s_vczok
    jmp short .say
.nofile:
    mov si, tp_s_vnofile
    jmp short .say
.noread:
    mov si, tp_s_noread
    jmp short .say
.differ:
    mov si, tp_s_vbad
    mov word [tp_msg], si
    call tp_endop
    mov byte [tp_state], TS_ERR
    call tp_setretry
    jmp short .paint
.say:
    mov word [tp_msg], si
    call tp_endop
    mov byte [tp_state], TS_DONE
.paint:
    call tp_show
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_crcdisk - a fresh CRC over the file as it sits on disk, RAW
; out: CF=0 and DX = the CRC; CF=1 it could not be read in this buffer
;      Every register but DX preserved
;
; OSAPI_FILE_READ_AT wants a cluster multiple for BOTH the offset and the
; capacity, so the chunk is the record buffer rounded DOWN to whole clusters -
; and a volume whose cluster is bigger than that buffer is refused rather than
; guessed at.
; -----------------------------------------------------------------------------
tp_crcdisk:
    push ax
    push bx
    push cx
    push si
    push di
    push es
    mov ax, [tp_rkb]
    mov bx, [tp_clkb]
    or bx, bx
    jnz .cl
    inc bx
.cl:
    xor dx, dx
    div bx
    or ax, ax
    jz .nofit                       ; the cluster is bigger than the buffer
    mul bx
    mov cl, 10
    shl ax, cl
    mov [tp_chunk], ax
    mov word [tp_off], 0
    mov dx, TP_CRC_PRE
    mov [tp_dcrc], dx
    mov di, [tp_size]               ; how much is left to cover
.loop:
    or di, di
    jz .done
    mov es, [tp_rseg]
    xor bx, bx
    mov cx, [tp_chunk]
    mov si, tp_name
    mov ax, [tp_off]
    xor dx, dx
    call OSAPI_FILE_READ_AT         ; DX:AX = the bytes delivered
    jc .nofit
    or ax, ax
    jz .done
    mov cx, ax
    cmp cx, di
    jbe .part
    mov cx, di
.part:
    add [tp_off], cx
    sub di, cx
    push di
    mov es, [tp_rseg]
    xor si, si
    mov dx, [tp_dcrc]
    call tp_crc16
    mov [tp_dcrc], dx
    pop di
    jmp short .loop
.done:
    mov dx, [tp_dcrc]
    clc
    jmp short .out
.nofit:
    stc
.out:
    pop es
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_cat_one - **READING IS A SCAN, AND THE SCAN NAMES WHAT GOES PAST**
; (SPEC.md 88.8.2)
; out: CF=1 the scan is over
;
; Repeated `AH=02` with CX = 256, one block, the buffer zeroed before each
; (row 23, and tp_xfer does it), with a coast between every one. **NEVER SCAN
; WITH CX > 256**: a larger read consumes and CRC-checks a whole record you may
; not want, at 1.5 s a block.
; -----------------------------------------------------------------------------
tp_cat_one:
    mov es, [tp_rseg]
    xor bx, bx
    mov cx, TP_BLOCK
    mov al, 2
    call tp_xfer
    jc .end
    inc word [tp_step]
    call tp_cat_name
    mov word [tp_catline], tp_line3
    push bp
    mov bp, tp_cat_draw
    call tp_paint_now
    pop bp
    mov ax, [tp_step]
    cmp ax, TP_CAT_MAX
    jae .end
    clc
    ret
.end:
    push ax
    push si
    push di
    call tp_endop
    mov di, tp_line3
    mov si, tp_s_catend
    call tp_app
    mov ax, [tp_step]
    call tp_numl
    mov byte [di], '.'
    inc di
    mov byte [di], 0
    mov word [tp_msg], tp_line3
    mov word [tp_catline], 0
    mov byte [tp_state], TS_DONE
    call tp_show
    pop di
    pop si
    pop ax
    stc
    ret

tp_cat_draw:
    call tp_draw_file
    call tp_draw_nums
    ret

; -----------------------------------------------------------------------------
; tp_cat_name - what the 256 bytes in the record buffer ARE
; out: tp_line3 composed; every register preserved
; -----------------------------------------------------------------------------
tp_cat_name:
    push ax
    push bx
    push cx
    push si
    push di
    push es
    mov es, [tp_rseg]
    mov di, tp_line3
    cmp byte [es:0], 0xA5
    jne .ours
    ; IBM Cassette BASIC's header. RECOGNISED AND NEVER WRITTEN (SPEC.md
    ; 88.4.3): "this tape has three BASIC programs on it and none of ours" is
    ; worth about a dozen bytes more than "this tape is unreadable"
    mov si, tp_s_basic
    call tp_app
    mov cx, 8
    mov bx, 1
.bch:
    mov al, [es:bx]
    cmp al, 0x20
    jb .bdone
    cmp al, 0x7E
    ja .bdone
    mov [di], al
    inc di
    inc bx
    loop .bch
.bdone:
    jmp short .done
.ours:
    cmp word [es:0], TP_HDR_M0
    jne .body
    cmp word [es:2], TP_HDR_M1
    jne .body
    mov si, tp_s_chdr
    call tp_app
    mov cx, 12
    mov bx, TPH_NAME
.nch:
    mov al, [es:bx]
    cmp al, 0x21
    jb .ndone
    cmp al, 0x7E
    ja .ndone
    mov [di], al
    inc di
    inc bx
    loop .nch
.ndone:
    mov byte [di], ' '
    inc di
    mov ax, [es:TPH_SIZE]
    call tp_numl
    jmp short .done
.body:
    cmp word [es:0], TP_BODY_MAG
    jne .unknown
    mov si, tp_s_cpart          ; we joined mid-file: a body record still names
    call tp_app                 ; the file's shape at once
    mov al, [es:TPB_SEQ]
    mov ah, 0
    call tp_numl
    mov si, tp_s_of
    call tp_app
    mov al, [es:TPB_NREC]
    mov ah, 0
    call tp_numl
    jmp short .done
.unknown:
    mov si, tp_s_cunk
    call tp_app
.done:
    mov byte [di], 0
    pop es
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_failed - the transport said no, and AH=1, AH=2 and AH=4 get DIFFERENT
; SENTENCES (SPEC.md 88.8.2), because they mean different things to the
; user's hands
; in:  AH = the code tp_xfer answered
; -----------------------------------------------------------------------------
tp_failed:
    push ax
    push bx
    push si
    mov bx, tp_s_ecrc
    cmp ah, TP_AH_CRC
    je .say
    mov bx, tp_s_esig
    cmp ah, TP_AH_SIGNAL
    je .say
    mov bx, tp_s_enodata
    cmp ah, TP_AH_NODATA
    je .say
    mov bx, tp_s_eshort
    cmp ah, TP_AH_SHORT
    je .say
    mov bx, tp_s_erefuse
.say:
    mov [tp_msg], bx
    call tp_endop
    mov byte [tp_state], TS_ERR
    call tp_setretry                ; **the caption becomes Retry and the
    call tp_show                    ; button STAYS LIVE** (SPEC.md 88.8.2):
    pop si                          ; a greyed button is a dead end you cannot
    pop bx                          ; retry from
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_setretry / tp_setgo - the Go button's caption
; -----------------------------------------------------------------------------
tp_setretry:
    mov word [tp_blbls+2], tp_l_retry
    ret

tp_setgo:
    mov word [tp_blbls+2], tp_l_go
    ret

; -----------------------------------------------------------------------------
; The composed refusals. **NEVER A BARE "CANNOT"** (SPEC.md 88.7): the
; arithmetic goes on the glass, because every one of these is a number the
; user can act on.
; -----------------------------------------------------------------------------
tp_msg_toobig:
    push ax
    push si
    push di
    mov di, tp_line3
    mov si, tp_name
    call tp_app
    mov si, tp_s_is
    call tp_app
    mov ax, [tp_size]
    call tp_numl
    mov si, tp_s_maxis
    call tp_app
    mov ax, TP_MAXFILE
    call tp_numl
    mov byte [di], '.'
    inc di
    mov byte [di], 0
    mov word [tp_msg], tp_line3
    pop di
    pop si
    pop ax
    ret

tp_msg_nomem:
    push ax
    push si
    push di
    mov di, tp_line3
    mov si, tp_s_needs
    call tp_app
    mov ax, [tp_needkb]
    call tp_numl
    mov si, tp_s_largest
    call tp_app
    call OSAPI_MEM_AVAIL            ; AX = the largest free run in KB, which is
    call tp_numl                    ; the only number that accounts for what
    mov si, tp_s_kb                 ; the kernel and every other package hold
    call tp_app
    mov byte [di], 0
    mov word [tp_msg], tp_line3
    pop di
    pop si
    pop ax
    ret

tp_msg_fmt:
    push ax
    push bx
    push si
    push di
    mov bl, al
    mov bh, 0
    cmp bx, TPE_LAST
    jbe .known
    xor bx, bx
.known:
    shl bx, 1
    mov si, [tp_emsg + bx]
    mov di, tp_line3
    push si
    mov si, tp_s_refused
    call tp_app
    pop si
    call tp_app
    mov byte [di], 0
    mov word [tp_msg], tp_line3
    pop di
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_est_line - the estimate, BEFORE Start, on every operation
; -----------------------------------------------------------------------------
tp_est_line:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov ax, [tp_size]
    mov bl, TP_RECBLK
    mov [tp_recblk], bl
    call tp_geom
    jc .out
    mov [tp_nrec], ch
    mov [tp_lastblk], cl
    mov [tp_cap], dx
    mov di, tp_line3
    mov si, tp_name
    call tp_app
    mov si, tp_s_dash
    call tp_app
    mov al, [tp_nrec]
    mov ah, 0
    inc ax
    call tp_numl
    mov si, tp_s_blocks
    call tp_app
    call tp_total_secs              ; every published duration rounds UP
    call tp_mmss
    mov byte [di], '.'
    inc di
    mov byte [di], 0
    mov word [tp_msg], tp_line3
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tp_mmss - AX seconds as m:ss at DS:DI; DI advanced
tp_mmss:
    push ax
    push bx
    push cx
    push dx
    mov bx, 60
    xor dx, dx
    div bx
    push dx
    call tp_numl
    mov byte [di], ':'
    inc di
    pop ax
    mov cx, 2
    call tp_num
    add di, 2
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_onclose - W_ONCLOSE (SPEC.md 75.1, 88.8)
; in:  SI = our window; the UI task, the gfx lock HELD
; out: CF=0 let the close happen, CF=1 REFUSE it
;
; It calls `int 15h AH=01` UNCONDITIONALLY - the motor is a relay on the
; user's deck - releases the PIT claim and frees the claims. **It REFUSES
; mid-transfer**, because a claim handed to the ROM cannot be freed while the
; ROM is in it; the refusal is not a dead end, Stop being live throughout.
;
; It is NOT called on a Restart (SPEC.md 88.2): `ui_cmd_reboot` reaches
; `drv_shutdown_x` and no package at all, so a machine restarted with a
; transfer armed rides the reboot with port B bit 3 still set - the relay
; stays energised until POST rewrites port 61h, about a second later.
; -----------------------------------------------------------------------------
tp_onclose:
    push ax
    push cx
    push si
    push es
    cmp byte [tp_state], TS_RUN
    jne .ok
    mov si, tp_s_closebusy
    mov ax, ds
    mov es, ax
    xor cx, cx
    call OSAPI_TOAST
    pop es
    pop si
    pop cx
    pop ax
    stc
    ret
.ok:
    call tp_motor_off
    call tp_endop
    pop es
    pop si
    pop cx
    pop ax
    clc
    ret

; -----------------------------------------------------------------------------
; The About card, and the menu the app's own name carries (SPEC.md 12.2)
; -----------------------------------------------------------------------------
tp_about:
    push bx
    push si
    mov byte [tp_abon], 1
    mov bx, si
    mov si, tp_ablines
    call os88ui_about               ; arms the clip itself: a menu dispatch
    pop si                          ; arrives without one (SPEC.md 11.3)
    pop bx
    ret

tp_abdismiss:
    cmp byte [tp_abon], 0
    je .none
    push ax
    push bx
    push dx
    mov byte [tp_abon], 0
    mov bx, si
    call OSAPI_WM_CLIP_SET
    jc .gone
    push si
    call tp_layout
    pop si
    jc .gone
    call tp_redraw
.gone:
    pop dx
    pop bx
    pop ax
    stc
    ret
.none:
    clc
    ret

; -----------------------------------------------------------------------------
; tp_oncmd - the menu set's handler
; in:  AL = the item, AH = the menu, SI = our window, BX = the set; the UI task
;      with the gfx lock HELD
; out: nothing
;
; Each item calls the very routine its button calls, guards and all, so a
; command picked in the wrong state is refused with the same status line a
; click on the greyed button would have written (recorder's discipline).
; -----------------------------------------------------------------------------
tp_oncmd:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov bx, si
    call OSAPI_WM_CLIP_SET
    jc .out
    push ax
    call tp_layout
    pop ax
    jc .out
    mov ah, 0
    mov bx, ax
    inc bx                          ; the item order IS TP_B_*'s order, which
    mov ax, bx                      ; is the wire format between the two
    call tp_act
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; THE WINDOW, ITS SIZES AND ITS WORDS
; =============================================================================
tp_tpl:
    dw 100, 50, 322, 165            ; x, y, w, h -> content 320 x 146
    dw tp_ttl, tp_paint, 0, tp_onclick

tp_ttl:     db 'Tape', 0

; **A FIXED CONTENT BOX DOES NOT FIT CGA** (SPEC.md 88.8, 11.100.1), which is
; the adapter of the machine class this feature is named after: wm_fit's
; ceiling there is 176 - 1 - 20 = 155, so the CGA row asks for a frame of
; exactly that and tapeui.inc's formula folds the two footer lines away at the
; 136 content rows it comes back as.
    OS88_PREFER tp_prefer, 322,165,  322,165,  322,155

tp_ablines:
    dw tp_ab1, tp_ab2, tp_ab3, tp_ab4, 0
tp_ab1:     db 'Tape for os8088', 0
tp_ab2:     db 0
tp_ab3:     db 'The IBM PC 5150 cassette port,', 0
tp_ab4:     db 'at 168 bytes a second.', 0

    OS88_MENUSET tp_menus, tp_ttl, tp_oncmd
        OS88_MENU tp_m_tape, tp_i_tape, 4
    OS88_MENUSET_END tp_menus

tp_m_tape:  db 'Tape', 0
tp_i_tape:  dw tp_it_choose, tp_it_go, tp_it_verify, tp_it_stop
tp_it_choose: db 'Choose...', 0
tp_it_go:   db 'Go', 0
tp_it_verify: db 'Verify', 0
tp_it_stop: db 'Stop', 0

; the questions. OS88UI_AMAX is 34 characters and the alert CLIPS rather than
; refusing, so these are counted
tp_q_save:  db 'RECORD+PLAY on the deck, then Go', 0
tp_q_read:  db 'Press PLAY on the deck, then Go', 0
tp_q_repl:  db 'Replace the file on the disk?', 0

; the status sentences
tp_s_pick:  db 'Choose a file to save first.', 0
tp_s_cueread: db 'Wind to just before the file.', 0
tp_s_busy:  db 'A dialog is already up.', 0
tp_s_pitfast: db 'The timer is re-rated: no tape now.', 0
tp_s_pitsnd: db 'The speaker is in use: no tape now.', 0
tp_s_pitheld: db 'Another Tape window holds the deck.', 0
tp_s_nosrc: db 'No such file on this disk.', 0
tp_s_noread: db 'The file could not be read.', 0
tp_s_nodisk: db 'Not enough room on the disk.', 0
tp_s_zip:   db 'Compressing...', 0
tp_s_nozip: db 'No system disk: writing it plain.', 0
tp_s_sent:  db ' blocks sent. Rewind, then Verify.', 0
tp_s_written: db ' written to the disk.', 0
tp_s_wrfail: db 'The disk refused the write: error ', 0
tp_s_kept:  db 'Kept the file that was there.', 0
tp_s_stopped: db 'Stopped after block ', 0
tp_s_stopw: db 'Stopped. A partial file is on the tape.', 0
tp_s_nofound: db 'No os8088 file found on the tape.', 0
tp_s_longname: db 'The name is too long for the tape.', 0
tp_s_catend: db 'Catalog: records read: ', 0
tp_s_vok:   db 'Verified: the tape holds this file.', 0
tp_s_vczok: db 'Tape checksum ok (compressed copy).', 0
tp_s_vbad:  db 'The tape does NOT match the file.', 0
tp_s_vnofile: db 'No file of that name to compare.', 0
tp_s_closebusy: db 'Stop the tape first', 0

; the transport's five, and they are five because AH=1, AH=2 and AH=4 mean
; different things to the user's HANDS (SPEC.md 88.8.2)
tp_s_ecrc:  db 'CRC error - the block is damaged.', 0
tp_s_esig:  db 'Bad signal - check volume and head.', 0
tp_s_enodata: db 'No more data: tape end, or no play.', 0
tp_s_eshort: db 'The block was short - tape refused.', 0
tp_s_erefuse: db 'The transport refused the block.', 0

; the pieces the composed lines are made of
tp_s_is:    db ' is ', 0
tp_s_maxis: db ' bytes; the format holds ', 0
tp_s_needs: db 'Needs ', 0
tp_s_largest: db ' KB; the largest free block is ', 0
tp_s_kb:    db ' KB.', 0
tp_s_refused: db 'Refused: ', 0
tp_s_dash:  db ' - ', 0
tp_s_blocks: db ' blocks, about ', 0
tp_s_basic: db 'IBM BASIC: ', 0
tp_s_chdr:  db 'File: ', 0
tp_s_cpart: db '...part ', 0
tp_s_cunk:  db 'Unknown record.', 0

; --- which field a refusal names (SPEC.md 88.9) ------------------------------
TPE_LAST    equ TPE_BASIC
tp_emsg:
    dw tp_e_ok, tp_e_magic, tp_e_ver, tp_e_kind, tp_e_flags, tp_e_recblk
    dw tp_e_nrec, tp_e_lastblk, tp_e_name, tp_e_size, tp_e_bmagic, tp_e_seq
    dw tp_e_bnrec, tp_e_bck, tp_e_paylen, tp_e_over, tp_e_short, tp_e_ckfile
    dw tp_e_cz, tp_e_basic
tp_e_ok:    db 'nothing', 0
tp_e_magic: db 'not an os8088 tape record', 0
tp_e_ver:   db 'a version this reader does not know', 0
tp_e_kind:  db 'not a file record', 0
tp_e_flags: db 'an unknown flag bit', 0
tp_e_recblk: db 'the record size', 0
tp_e_nrec:  db 'nrec disagrees with the size', 0
tp_e_lastblk: db 'lastblk disagrees with the size', 0
tp_e_name:  db 'the name field', 0
tp_e_size:  db 'the size field', 0
tp_e_bmagic: db 'a record that is neither kind', 0
tp_e_seq:   db 'a record out of order', 0
tp_e_bnrec: db 'a record from a longer file', 0
tp_e_bck:   db 'a record from a DIFFERENT file', 0
tp_e_paylen: db 'the payload length', 0
tp_e_over:  db 'more payload than the file has', 0
tp_e_short: db 'less payload than the file has', 0
tp_e_ckfile: db 'the file checksum - it is damaged', 0
tp_e_cz:    db 'the compressed wrapper', 0
tp_e_basic: db 'an IBM Cassette BASIC record', 0

; =============================================================================
; THE STATE
; =============================================================================
tp_win:     dw 0
tp_down:    dw 0                ; os88ui_bfind's answer: the control PLUS ONE
tp_msg:     dw 0                ; the status sentence, 0 = the idle one
tp_catline: dw 0                ; ...and the file line's, during a Catalog
tp_step:    dw 0                ; 0 = the header record, 1..nrec = the bodies
tp_nrecs:   dw 0                ; how many cells the progress bar has
tp_cellip:  dw 0xFFFF           ; ...and which one is in flight
tp_scanned: dw 0
tp_pseg:    dw 0                ; the payload claim
tp_rseg:    dw 0                ; the record buffer
tp_zseg:    dw 0                ; the encoder's output, freed at once
tp_rkb:     dw 0
tp_pkb:     dw 0
tp_clkb:    dw 1                ; the volume's cluster, in KB
tp_needkb:  dw 0
tp_chunk:   dw 0
tp_off:     dw 0
tp_dcrc:    dw 0
tp_packed:  dw 0
tp_rawsize: dw 0                ; what the source file OCCUPIES on the disk
tp_ferr:    dw 0
tp_state:   db TS_IDLE
tp_run:     db TR_STAGE
tp_mode:    db TM_SAVE
tp_phase:   db 0                ; the reels'
tp_stop:    db 0
tp_wantz:   db 1                ; Compress, on by default: it PAYS for the
                                ; chunking (SPEC.md 88.7)
tp_doverify: db 0
tp_srccz:   db 0
tp_zfmt:    db 0
tp_abon:    db 0
tp_inwake:  db 0                ; 1 while a W_ONWAKE turn is running, which is
                                ; the one context in this package that holds no
                                ; gfx lock (SPEC.md 20.6 rule 7)
tp_find:    times OSAPI_FIND_SZ db 0

; =============================================================================
%include "tapefmt.inc"
%include "tapexfr.inc"
%include "tapeui.inc"
%include "reels.inc"
%include "os88pit.inc"

%define OS88UI_ALERT            ; the cue-confirm and the replace question
%define OS88UI_ABOUT            ; ...and the standard About card, beside the
%include "os88ui.inc"           ; buttons and glyphs this already draws

    OS88_IMAGE_END
