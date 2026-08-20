; =============================================================================
; os8088 - apps/ftpd/ftpd.asm
;
; FTPD - docs/NET-STACK-PLAN.md stage F, and the first thing in this system
; that makes the 5150 a SERVER rather than a client.
;
; Everything before it - the cable, Telnet, the browser, the card - had os8088
; reaching OUT. This inverts every one of those assumptions: the connection
; arrives, the far end asks the questions, and the answers come off the
; machine's own floppies. It is the answer to docs/FIELD-MACHINES.md's
; seven-step path in the other direction - a file reaches the 5150 by being
; dropped on it from a modern machine, rather than by being written to an
; image, carried, and booted.
;
; --- WHAT IT IS ---------------------------------------------------------------
; An RFC 959 server, deliberately small: one client at a time, one volume, 8.3
; names, binary transfers only. PASV and PORT both, EPSV for the clients that
; prefer it, and a UNIX-shaped LIST because that is the format every client
; parses (fd_c_syst says why that is a statement about the LISTING and not a
; claim to be Unix).
;
; --- THE ONE REAL CONSTRAINT, AND THE WHOLE SHAPE OF THIS FILE ----------------
; **A WORKER MAY NOT TOUCH A FILE** (SPEC.md 20.6 rule 7): the file slots share
; dsk_secbuf, the FAT snapshot and sch_lock, and are UI-task context only. An
; FTP server is socket-to-file BY DEFINITION, so that is not a detail here, it
; is the central design problem (docs/NET-STACK-PLAN.md 1.5.1).
;
; The answer is the one Frotz proved for @save (SPEC.md 61.6) and RunCPM for
; its Z80 slices (SPEC.md 74.1): **THE WORKER STAGES AND THE UI TASK COMMITS.**
;
;   worker                                    UI task (fd_wake)
;   ------                                    -----------------
;   fill fd_arg*, then [fd_req] = FR_*   -->  sees [fd_req], does the file work,
;   OSAPI_WM_WAKE                             writes fd_rst/fd_rlen,
;   poll until [fd_req] == FR_NONE       <--  clears [fd_req] LAST
;
; **[fd_req] IS THE WHOLE HANDSHAKE** and the ordering is the entire proof: the
; producer writes every argument BEFORE the flag and the consumer clears the
; flag AFTER every result, so neither ever reads a half-written answer. It is
; one byte, and a byte store is atomic on an 8086, so no lock is needed on
; either side - which matters, because the worker may not take one and the
; wake handler is the one callback that does not hold the gfx lock.
;
; OSAPI_WM_ONWAKE is what makes it possible at all: called on the UI task,
; billed to this instance, WITHOUT the gfx lock, and expressly allowed to call
; the file slots. Nothing else in the SDK is.
;
; --- EVERY BUFFER IS CLAIMED BEFORE THE WORKER EXISTS -------------------------
; OSAPI_MEM_* is not on rule 7's list either, so the staging buffer is claimed
; in fd_entry and never resized. Frotz's zi_load is the model.
;
; --- WHY A TRANSFER IS A LOOP AND NOT A STREAM --------------------------------
; The stage is bounded, so a 200KB upload is a run of stage-and-commit rather
; than one write, and the chunk is A WHOLE NUMBER OF CLUSTERS because that is
; OSAPI_FILE_APPEND's and OSAPI_FILE_READ_AT's shared precondition (SPEC.md
; 18.4.4). fd_chunk derives it from OSAPI_FILE_DFREE at the start of every
; transfer rather than baking it in - a hard-disk partition picks its cluster
; size from its capacity (SPEC.md 52.3) while a floppy is 512, and the volume
; can change under a CWD between two transfers.
;
; Every proc here is a near proc with a near `ret`: the kernel reaches a
; callback through the dispatcher in the package's own header (SPEC.md 20.1),
; and a `retf` returns into the loader's stack frame.
; =============================================================================

%include "os88api.inc"
%include "netpkg.inc"               ; ...THE DRIVER'S OWN HEADER, the same file
                                    ; drivers/ether/ether.asm includes, so the
                                    ; two ends cannot drift (SPEC.md 20.11)

    OS88_HEADER 'FTPD', fd_entry, 1
    OS88_ICON16
    ; 16 mask rows (the white underlay), then 16 of ink: a disk platter with
    ; an arrow leaving it - the machine's own storage, served outwards.
    dw 0x0000
    dw 0x0FF0
    dw 0x3FFC
    dw 0x7FFE
    dw 0x7FFE
    dw 0xFFFF
    dw 0xFFFF
    dw 0xFFFF
    dw 0xFFFF
    dw 0xFFFF
    dw 0x7FFE
    dw 0x7FFE
    dw 0x3FFC
    dw 0x0FF0
    dw 0x0000
    dw 0x0000
    dw 0x0000
    dw 0x0FF0
    dw 0x300C
    dw 0x4002
    dw 0x4002
    dw 0x8001
    dw 0x8181
    dw 0x83C1
    dw 0x8FF1
    dw 0x83C1
    dw 0x4181
    dw 0x4002
    dw 0x300C
    dw 0x0FF0
    dw 0x0000
    dw 0x0000
    OS88_ICON16_END

; --- geometry ----------------------------------------------------------------
FD_W        equ 400
FD_H        equ 176
FD_PAD      equ 4
FD_BTNW     equ 72
FD_BTNH     equ 14
FD_ROLBL    equ 9                   ; 'Read Only' in cells, so the Setup
                                    ; button's floor can be derived rather
                                    ; than guessed at
FD_TEXTX    equ 8                   ; **THE TEXT PEN, AND IT IS 8-ALIGNED.**
                                    ; WF_SNAP makes the content origin a
                                    ; multiple of 8 (SPEC.md 11.94), so a pen
                                    ; at origin+8 is aligned and every run here
                                    ; takes font_run's SINGLE-STORE path - the
                                    ; one that writes each cell old-to-final in
                                    ; one store, so a line is never momentarily
                                    ; blank. It was FD_PAD (4), which is 4 mod
                                    ; 8 for every window position on every
                                    ; adapter and could NEVER take that path
                                    ; (os88line.inc's own header is the same
                                    ; finding about the browser's location bar)
FD_ROWH     equ 8                   ; the log's line pitch
FD_LOGN     equ 10                  ; ...and how many lines it keeps
FD_LOGW     equ 44                  ; characters per line, NUL included below
FD_LOGSZ    equ (FD_LOGW + 1) * FD_LOGN

; --- the server's own state --------------------------------------------------
FD_OFF      equ 0                   ; not serving
FD_LISTEN   equ 1                   ; port 21 is open, nobody has called
FD_CTRL     equ 2                   ; a client is connected
FD_ERR      equ 3                   ; it could not start, and [fd_msg] says why

; -----------------------------------------------------------------------------
; TWO STATES, AND THEY MUST NOT SHARE A BYTE
;
; **HOW THE DATA CONNECTION IS BEING MADE** and **WHAT IS BEING TRANSFERRED**
; are independent, and the first version of this file held them in one byte.
; The sequence a real client sends is PASV, then RETR - so `fd_c_list` set the
; byte to FX_LIST over the FX_PASV that PASV had just put there, and
; fd_data_ready then had no idea a listener was armed. It never accepted, the
; client sat on a connection nobody answered, and the transfer timed out with
; the control connection perfectly healthy and a 150 already sent.
;
; It is the shape SPEC.md 48.22.1 is about - a flag written into a field that
; already means something - and it fails the same way: silently, at the far
; end, in a state every earlier reply says is fine.
; -----------------------------------------------------------------------------
DM_NONE     equ 0                   ; no data connection is arranged
DM_PASV     equ 1                   ; a listener is armed, waiting to accept
DM_PORT     equ 2                   ; connecting out to the client's PORT
DM_UP       equ 3                   ; ...and it is connected

FX_NONE     equ 0
FX_LIST     equ 1                   ; sending a directory listing
FX_RETR     equ 2                   ; sending a file
FX_STOR     equ 3                   ; receiving a file

; --- the file requests the worker posts to the UI task -----------------------
FR_NONE     equ 0
FR_LIST     equ 1                   ; fill the stage with listing lines
FR_RDCHK    equ 2                   ; does this file exist, and how big is it?
FR_READ     equ 3                   ; a chunk at [fd_foff] into the stage
FR_WCREATE  equ 4                   ; create the file with the stage's bytes
FR_WAPPEND  equ 5                   ; ...and append the stage's bytes to it
FR_DELE     equ 6
FR_MKD      equ 7
FR_RNFR     equ 8                   ; check the source exists, bank the name
FR_RNTO     equ 9
FR_CWD      equ 10
FR_PWD      equ 11                  ; render the current path into the stage
FR_SIZE     equ 12
FR_RMD      equ 13

; --- which face the content box is showing (SPEC.md 77.12) -------------------
; A PAGE and not a flag, because there are three of them now and there will be
; more: the About panel was `[fd_abon]`, one byte meaning one thing, and the
; moment Setup arrived that byte had to answer a question it was not shaped
; for. Pages are drawn by fd_draw_all and nothing else knows they exist.
FP_LOG      equ 0                   ; the command log - the working face
FP_SETUP    equ 1                   ; the settings, backed by FTPD.CFG
FP_ABOUT    equ 2                   ; the credits

FD_CTL      equ 512                 ; the control line buffer
FD_OUT      equ 256                 ; ...and the reply being composed
FD_NAMEMAX  equ 13                  ; an 8.3 name and its NUL
FD_PATHMAX  equ 128                 ; the longest path an argument may carry
; -----------------------------------------------------------------------------
; THE STAGE IS IN OUR OWN BSS AND IT CANNOT BE A HEAP CLAIM
;
; It was one, and that is a design this door forbids: OSAPI_DRV_CALL is an **X
; STUB** - it puts the CALLING PACKAGE's segment in ES, because a socket
; verb's buffer is the package's and the driver has to be able to read it
; (kernel/driver.inc, drv_pkg_call_x). So `mov es, [claim]` before a NETV_SEND
; is simply overwritten, and the driver reads the same offset out of OUR
; IMAGE instead.
;
; It fails in the most confusing way available: a LIST answered 227, 150 and
; 226 exactly as it should, and delivered four rows of the package's own
; header and code - which reads as memory corruption rather than as a wrong
; segment register, because the bytes really are ours.
;
; A claim is still right for the FILE half (the file slots are N stubs and
; keep the caller's ES), so the alternative was a claim plus a copy at every
; socket call. In our own segment BOTH halves reach it directly, the ES/DS
; twins of every append helper disappear, and the cost is that the package's
; region is FD_STGSZ bigger - which it would have been anyway, one claim over.
; -----------------------------------------------------------------------------
; -----------------------------------------------------------------------------
; FD_WDOG_T - how long a transfer may move NOTHING before it is abandoned
;
; **A STALLED TRANSFER USED TO HOLD ITS SOCKET FOR EVER**, and that is what
; wedged the server in the field (SPEC.md 77.19): the stack has NET_SOCKS = 4
; handles in total, the listener holds one and a control connection another,
; so ONE abandoned data socket means the next session can log in and cannot
; open a data connection - LIST fails and the client is dropped, which reads
; as "the server broke" rather than "the last transfer did". Restarting the
; app cleared it, which is exactly the shape of a leak.
;
; 90 seconds at 18.2065 Hz. It is deliberately LONG: the thing being waited
; for is a 4.77MHz machine committing 8KB to an MFM disk while the peer
; retransmits, and a watchdog that fires during honest slow progress is worse
; than no watchdog at all. It only ever fires on a connection that has moved
; NOTHING for a minute and a half.
; -----------------------------------------------------------------------------
FD_WDOG_T   equ 1638                ; ticks: 90s at 18.2065 Hz

; -----------------------------------------------------------------------------
; FD_STGSZ - the staging buffer, and THE SINGLE BIGGEST LEVER ON THROUGHPUT
;
; A power of two at least a cluster wide, so fd_setchunk's rounding always
; leaves a whole number of clusters on every volume this kernel mounts
; (SPEC.md 52.3 caps a cluster at 8KB). That is the CORRECTNESS constraint,
; and it was the only reason recorded when this was 8192.
;
; **IT IS ALSO THE NUMBER OF SEEKS A TRANSFER PAYS** (SPEC.md 77.21). One
; append is two FAT flushes plus a directory write, so the head leaves the
; data area and comes back several times PER CHUNK - and on the ST-225 the
; field reports from, a seek is ~65ms against ~10ms for a sector. The
; overhead is per APPEND and does not shrink with the chunk, so the chunk is
; what divides it: 8KB made a 126KB upload sixteen appends and about
; 7KB/s, which is 18 seconds - longer than WinSCP's 15-second control
; timeout, so it never finished. Four appends instead of sixteen is the
; whole fix.
;
; **32768 AND NOT MORE**: [fd_sfill] and [fd_sout] are words, and 65536
; is zero in one.
; -----------------------------------------------------------------------------
FD_STGSZ    equ 32768
FD_CDMAX    equ 16                  ; how deep CWD can go and still come back.
                                    ; **CDUP NEEDS A STACK BECAUSE THE KERNEL
                                    ; CANNOT ANSWER IT.** OSAPI_FILE_FIND never
                                    ; reports '..': dsk_find's species filter
                                    ; drops the on-disk dot links outright, and
                                    ; the synthesized type-3 parent row is
                                    ; disk_mount's LISTING (SPEC.md 19.5), which
                                    ; is a different thing a package cannot
                                    ; reach. OSAPI_FILE_GOTO takes a cluster, so
                                    ; the only way back up is to have kept the
                                    ; one we came from - which the walker that
                                    ; went down is the only thing that knows.
FD_PASVP    equ 2048                ; the passive port, plus a rotating count.
                                    ; ROTATING because a client that finishes
                                    ; one transfer and starts another leaves
                                    ; the last port in TIME_WAIT on ITS side
FD_PASVN    equ 8
; --- what on the face is behind the glass (SPEC.md 77.14) --------------------
; A BITMASK AND NOT ONE FLAG. It was `[fd_ldirty]`, so a Read Only tick - one
; 12px box - redrew the button, the status line and all ten log rows, and a
; single arriving log line redrew the whole face. Each bit is spent by the one
; routine that owns those pixels.
FDD_BTN     equ 0x01                ; the Start/Stop button
FDD_RO      equ 0x02                ; the Read Only box
FDD_STAT    equ 0x04                ; the status line
FDD_LOG     equ 0x08                ; ...and [fd_lognew] rows have arrived
FDD_PAGE    equ 0x10                ; ...or the whole content box, because the
                                    ; PAGE changed. It is a bit of its own and
                                    ; not "all four": leaving Setup returns to
                                    ; FP_LOG, where the incremental path would
                                    ; letter the arrived rows and leave the
                                    ; Setup page's pixels underneath them
FDD_ALL     equ 0x1F

FD_CFGSZ    equ 256                 ; FTPD.CFG, read and composed whole. It is
                                    ; a settings file and not a document: if
                                    ; it ever needs more than this, the thing
                                    ; that grew wants a file of its own

FTP_PORT    equ 21

; =============================================================================
; ENTRY
; =============================================================================
fd_entry:
    push si
    mov si, fd_tpl
    call OSAPI_WM_CREATE
    jc .out
    mov [fd_win], bx
    mov al, 1
    mov bx, [fd_win]
    call OSAPI_WM_SNAP              ; 8-aligned content, so every log line takes
                                    ; font_run's single-store path on the two
                                    ; mono adapters (SPEC.md 11.94)
    mov bx, [fd_win]
    mov ax, fd_wake
    call OSAPI_WM_ONWAKE            ; THE UI-TASK HALF. Everything this package
                                    ; does to a disk happens in there
    mov bx, [fd_win]
    mov ax, fd_onup
    call OSAPI_WM_ONMOUSEUP         ; SPEC.md 13.7: EVERY control here fires on
                                    ; the RELEASE, over the one the press
                                    ; landed on, so a mis-aimed press can be
                                    ; slid off. W_ONMOUSEUP is inside the
                                    ; 28-byte record, so it is on both kernels
    mov ax, fd_ondrag
    call OSAPI_WM_ONDRAG            ; ...and SPEC.md 13.8.2: the control it
                                    ; landed on FOLLOWS the pointer between the
                                    ; two edges. THE CARRY IS NOT TESTED - on
                                    ; kern_small this refuses and there is no
                                    ; drag edge, which leaves the static down
                                    ; state that section asks for: down on the
                                    ; press, up on the release, and the release
                                    ; still re-finds the control before firing
    mov ax, fd_onclose
    call OSAPI_WM_ONCLOSE           ; ...and the last chance to write the
                                    ; settings out (SPEC.md 77.17)
    push si
    mov si, fd_menus
    mov bx, [fd_win]
    call OSAPI_MENU_SET
    mov si, fd_about
    mov bx, [fd_win]
    call OSAPI_ABOUT_SET            ; preserves the flags, which matters: the
    pop si                          ; CF wm_create left still has to ride out
    call fd_cfg_load                ; SYSTEM\APPDATA\FTPD.CFG, if the disk has
                                    ; one. UI-task context, which the entry
                                    ; proc is - the worker does not exist yet
    mov si, fd_l_ready
    call fd_log
    clc
.out:
    pop si
    ret

; =============================================================================
; DRAWING
;
; The window is a status line, a Start/Stop button, a Read Only check box and
; a log of the last FD_LOGN command lines. Every text element is ONE OPAQUE
; font_run (SPEC.md 6.1): the run's own background is the erase, so there is
; no fill-then-letter pair to blank a line while it is drawn and no
; granularity failure to gate against (SPEC.md 11.3).
; =============================================================================

; --- fd_layout - every rect, from the LIVE content box -----------------------
; Re-derived on every paint rather than stored, because a window can be
; resized, moved across an extended desktop's seam or find itself on an
; adapter of a different size (SPEC.md 39.7/11.98) - and a control drawn from
; a remembered rect is one the hit-test cannot find.
fd_layout:
    push ax
    push bx
    push cx
    push dx
    mov bx, si
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    mov [fd_ox], ax
    mov [fd_oy], dx
    mov bx, si
    call OSAPI_WM_GEOM              ; CX = width, DX = height - and it takes BX,
    mov [fd_cw], cx                 ; which WM_CONTENT has spent
    mov [fd_ch], dx
    ; the button, top-left
    mov ax, [fd_ox]
    add ax, FD_PAD
    mov [fd_btn], ax
    add ax, FD_BTNW - 1
    mov [fd_btn+4], ax
    mov ax, [fd_oy]
    add ax, FD_PAD
    mov [fd_btn+2], ax
    add ax, FD_BTNH - 1
    mov [fd_btn+6], ax
    ; the Read Only box, to its right
    mov ax, [fd_ox]
    add ax, FD_PAD + FD_BTNW + 8
    mov [fd_rob], ax
    add ax, 11
    mov [fd_rob+4], ax
    mov ax, [fd_oy]
    add ax, FD_PAD + 2
    mov [fd_rob+2], ax
    add ax, 11
    mov [fd_rob+6], ax
    ; --- the Setup button, RIGHT-ALIGNED in the same row -------------------
    ; Right-aligned rather than laid at a constant, because the window can be
    ; grown and the toolbar's two left-hand controls cannot: a button pinned
    ; at x=182 leaves a widening gap on its right for the rest of the
    ; session. The FLOOR is what keeps it off the Read Only label when the
    ; window is dragged the other way - the label has nowhere else to go.
    mov ax, [fd_ox]
    add ax, [fd_cw]
    sub ax, FD_PAD + 1
    mov [fd_setb+4], ax
    sub ax, FD_BTNW - 1
    mov bx, [fd_rob+4]              ; the box's right edge...
    add bx, 6 + FD_ROLBL*8 + 8      ; ...its label, and a gap
    cmp ax, bx
    jae .setbx
    mov ax, bx
.setbx:
    mov [fd_setb], ax
    add ax, FD_BTNW - 1
    cmp ax, [fd_setb+4]             ; a floor may have pushed the right edge
    jbe .setbw                      ; past where it was
    mov [fd_setb+4], ax
.setbw:
    mov ax, [fd_btn+2]              ; the same row as Start, exactly
    mov [fd_setb+2], ax
    mov ax, [fd_btn+6]
    mov [fd_setb+6], ax
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- fd_paint - W_PAINT: SI = window, gfx lock held --------------------------
fd_paint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call fd_layout
    call fd_draw_all
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- fd_draw_all - the whole face. Lock held, fd_layout already run ----------
; -----------------------------------------------------------------------------
; fd_spend - put ONLY what changed on the glass. Lock held, fd_layout run
;
; The face is four independent things and they change on four different
; cadences: the button on a start or a stop, the box on a tick, the status
; line on a state change, and the log on every command the server answers.
; Drawing all four for any one of them is PERFORMANCE.md Part 1's redraw with
; nothing to show for it - ten opaque 44-cell runs to move a 12px checkbox.
;
; A PAGE that is not the log has none of these on it, so it is redrawn whole
; and the bits are spent unread: Setup and About cover the content box.
; -----------------------------------------------------------------------------
fd_spend:
%ifdef FTPDSLOW
    ; **THE REFERENCE BUILD** (make FTPDSLOW=1, SPEC.md 77.14). The claim these
    ; paths make is "the picture is the same, only the number of times it was
    ; drawn changed" - and a screenshot of ONE build cannot check that. This
    ; arm is the pre-optimisation behaviour: every change redraws the whole
    ; face. RAMPAGE.DRV's RPSLOW is the precedent (SPEC.md 62.9.11.1).
    call fd_draw_all
    mov byte [fd_dirty], 0
    ret
%endif
    push ax
    test byte [fd_dirty], FDD_PAGE
    jnz .page
    cmp byte [fd_page], FP_LOG
    jne .page
    mov al, [fd_dirty]
    test al, FDD_BTN
    jz .ro
    call fd_draw_btn
.ro:
    test al, FDD_RO
    jz .stat
    call fd_draw_ro
.stat:
    test al, FDD_STAT
    jz .log
    call fd_draw_stat
.log:
    test al, FDD_LOG
    jz .done
    call fd_draw_log_inc
.done:
    mov byte [fd_dirty], 0
    pop ax
    ret
.page:
    call fd_draw_all
    mov byte [fd_dirty], 0
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_clear_content - the content box, white. Lock held, fd_layout run
;
; **THE FILL SETS THE PEN, AND THE TWO PAGE FILLS DID NOT.** gfx_fill paints in
; [gfx_color], which is whatever the last drawing call in this lock hold left
; there - so opening Setup filled the content BLACK, and returning to the log
; face drew the button, the box, the status line and the rows on top of it and
; left everything they do not cover black for the rest of the session. It is
; SPEC.md 47 rule 2's shape in the other direction: a colour that is never set
; is not a colour, it is the previous caller's.
;
; It is called on a PAGE change and on W_PAINT and nowhere else. The
; incremental path never fills - which is the whole point of it - and W_PAINT
; already has wm_draw_win's white underneath, so the one redundant call there
; buys the page change its erase for a single drawing call.
; -----------------------------------------------------------------------------
fd_clear_content:
    push ax
    push bx
    push cx
    push dx
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov ax, [fd_ox]
    mov bx, [fd_oy]
    mov cx, ax
    add cx, [fd_cw]
    dec cx
    mov dx, bx
    add dx, [fd_ch]
    dec dx
    call OSAPI_GFX_FILL
    mov al, CBLACK                  ; ...and the pen is PUT BACK, or the next
    call OSAPI_SET_COLOR            ; caller inherits this one exactly as this
    pop dx                          ; routine inherited its bug
    pop cx
    pop bx
    pop ax
    ret

fd_draw_all:
    cmp byte [fd_page], FP_ABOUT
    jne .nab
    call fd_draw_about
    ret
.nab:
    cmp byte [fd_page], FP_SETUP
    jne .face
    call fd_draw_setup
    ret
.face:
    call fd_clear_content
    call fd_draw_btn
    call fd_draw_ro
    call fd_draw_setb
    call fd_draw_stat
    call fd_draw_log                ; ...which clears [fd_lognew]: a full paint
    mov byte [fd_dirty], 0          ; has just put every row on the glass
    ret

fd_draw_btn:
    push ax
    push bx
    push si
    push di
    mov si, fd_s_start
    cmp byte [fd_st], FD_OFF
    je .have
    cmp byte [fd_st], FD_ERR
    je .have
    mov si, fd_s_stop
.have:
    mov bx, fd_btn
    mov di, OS88UI_FILL             ; **NEVER GREYED, AND IT USED TO BE.** The
                                    ; greying was on FD_ERR with a comment
                                    ; saying "no staging buffer, so there is
                                    ; nothing to start" - and the stage moved
                                    ; into bss long before this, so that fact
                                    ; stopped existing while the greying
                                    ; stayed. What it actually greyed was
                                    ; EVERY error: no network driver, no link,
                                    ; port 21 in use, and now a Root that will
                                    ; not resolve. Every one of those is
                                    ; TRANSIENT - plug the cable in, tick the
                                    ; driver, fix the Root - and a greyed
                                    ; button is a dead end you cannot retry
                                    ; from. SPEC.md 48.5's rule, and 47 rule 3
                                    ; agrees: the only honest test is Start
    cmp word [fd_down], FD_R_MAIN   ; ...and the PRESSED look comes from the
    jne .draw                       ; VARIABLE, so a W_PAINT arriving mid-
    or di, OS88UI_DOWN              ; gesture draws it the way it really is
.draw:                              ; (SPEC.md 13.8.2)
    call os88ui_btn
    pop di
    pop si
    pop bx
    pop ax
    ret

; --- fd_draw_setb - the way IN, because a menu item is not a way in ----------
; The Setup page was reachable only from Server > Setup..., which is a pull-
; down nothing on the face points at. A button in the toolbar is the whole
; fix, and it is drawn only by fd_draw_all: its label never changes, so there
; is no dirty bit for it and nothing incremental to spend.
fd_draw_setb:
    push bx
    push si
    push di
    mov si, fd_s_setup
    mov bx, fd_setb
    mov di, OS88UI_FILL
    cmp word [fd_down], FD_R_C2
    jne .draw
    or di, OS88UI_DOWN
.draw:
    call os88ui_btn
    pop di
    pop si
    pop bx
    ret

fd_draw_ro:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov cx, [fd_rob]                ; the glyph takes a TOP-LEFT, not a rect -
    mov dx, [fd_rob+2]              ; the rect is kept for the hit-test alone
    mov al, OS88UI_GCHECK
    cmp byte [fd_ro], 0
    je .nz
    or al, OS88UI_GON
.nz:
    cmp word [fd_down], FD_R_C1
    jne .nd
    or al, OS88UI_GDOWN             ; the box black and the picture white -
.nd:                                ; os88ui_btn's down state one widget over
    xor ah, ah
    call os88ui_glyph
    mov cx, [fd_rob+4]
    add cx, 6
    mov dx, [fd_rob+2]
    add dx, 2
    mov si, fd_s_ro
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_draw_done / fd_draw_rchk / fd_draw_mchk - the SETUP page's three
;
; They exist so that fd_setdown can repaint ONE control mid-gesture. Without
; them the only painter for this page was fd_draw_setup, which clears the
; whole content box and re-letters four labels, four fields and two ticks -
; forty-odd drawing calls at PERFORMANCE.md Part 2's 756us apiece, per mouse
; packet, to move one 12px box. Each of these is one call and the label it
; needs.
; -----------------------------------------------------------------------------
fd_draw_done:
    push bx
    push si
    push di
    mov si, fd_s_done
    mov bx, fd_done
    mov di, OS88UI_FILL
    cmp word [fd_down], FD_R_MAIN
    jne .draw
    or di, OS88UI_DOWN
.draw:
    call os88ui_btn
    pop di
    pop si
    pop bx
    ret

fd_draw_rchk:
    push ax
    push bx
    push si
    mov bx, fd_rchk
    mov si, fd_s_ro
    mov al, [fd_ro]
    call fd_setup_box               ; the SAME body the full page draws with,
    pop si                          ; so a pressed tick and a repainted one
    pop bx                          ; cannot disagree about what it looks like
    pop ax
    ret

fd_draw_mchk:
    push ax
    push bx
    push si
    mov bx, fd_mchk
    mov si, fd_s_mach
    mov al, [fd_mach]
    call fd_setup_box
    pop si
    pop bx
    pop ax
    ret

; --- fd_draw_stat - one opaque padded run, so it never blanks ----------------
fd_draw_stat:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call fd_stat_text
    mov cx, [fd_ox]
    add cx, FD_TEXTX
    mov dx, [fd_oy]
    add dx, FD_PAD + FD_BTNH + 4
    mov si, fd_sline
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- fd_stat_text - compose the status line into fd_sline, space-padded ------
; **PADDED, not fill-then-letter**: a space paints background on font_run's
; fast path, so the padding IS the erase and the line is never momentarily
; blank (SPEC.md 27.2's rule, in the place it was learned).
fd_stat_text:
    push ax
    push bx
    push cx
    push si
    push di
    mov di, fd_sline
    mov al, [fd_st]
    xor ah, ah
    shl ax, 1
    mov bx, ax
    mov si, [fd_s_state+bx]
    call fd_dcat
    cmp byte [fd_st], FD_ERR
    jne .live
    mov si, [fd_msg]
    call fd_dcat
    jmp short .pad
.live:
    cmp byte [fd_st], FD_OFF
    je .pad
    mov si, fd_s_onport
    call fd_dcat
    mov ax, FTP_PORT
    call fd_dnum
    mov si, fd_s_at
    call fd_dcat
    mov ax, [fd_pasv]               ; the OVERRIDE is what a client is told, so
    or ax, [fd_pasv+2]              ; it is what the status line has to show -
    jz .own                         ; otherwise the one machine that needs the
    call fd_pasv_str                ; setting is the one whose window disagrees
    mov si, fd_pasvs                ; with what it is sending
    call fd_dcat
    jmp short .pad
.own:
    mov si, fd_ipstr
    call fd_dcat
.pad:
    mov cx, fd_sline + FD_LOGW
.p:
    cmp di, cx
    jae .done
    mov byte [di], ' '
    inc di
    jmp short .p
.done:
    mov byte [di], 0
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; --- fd_draw_log - the command log, newest at the bottom ---------------------
fd_draw_log:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call fd_log_y                   ; the first row's pen, banked
    xor bx, bx                      ; BX = the display row, 0 at the top
.row:
    call fd_log_row
    inc bx
    cmp bx, FD_LOGN
    jb .row
    mov byte [fd_lognew], 0
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- fd_log_y - bank the first row's pen y in [fd_leny] ---------------------
fd_log_y:
    push ax
    mov ax, [fd_oy]
    add ax, FD_PAD + FD_BTNH + 4 + FD_ROWH + 4
    mov [fd_leny], ax               ; banked because `mul` below writes DX, so
    pop ax                          ; a y held there is gone
    ret

; --- fd_log_row - letter display row BX -------------------------------------
fd_log_row:
    push ax
    push cx
    push dx
    push si
    mov ax, bx
    call fd_logline                 ; -> AX = that row's text
    mov si, ax
    mov ax, FD_ROWH
    mul bx                          ; DX:AX - the band is tiny, so AX is it
    add ax, [fd_leny]
    mov dx, ax
    mov cx, [fd_ox]
    add cx, FD_TEXTX
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    pop si
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_draw_log_inc - the rows that ARRIVED, and nothing else (SPEC.md 77.14)
;
; The log is the busiest thing on this window - every command the server
; answers is a line - and it was ten opaque runs of 44 cells each, 440 glyph
; cells, to put ONE new line at the bottom. At PERFORMANCE.md's ~1ms a cell on
; the machine this is for, that is most of half a second per FTP command.
;
; It is a blit and one run now: OSAPI_GFX_SCROLL moves the nine rows that are
; staying and the arrived row is lettered into the space it vacated. The x
; span is 8-aligned at BOTH ends because the primitive is byte-column granular
; on every adapter and refuses otherwise - x1 is the aligned pen and the width
; is a whole number of cells, so x2+1 lands on a multiple of 8 by construction.
;
; A REFUSED SCROLL FALLS BACK to the full redraw rather than leaving the band
; half-moved: a clip region that does not wholly contain the rect refuses, and
; a covered window is exactly when that happens (SPEC.md 11.3).
; -----------------------------------------------------------------------------
fd_draw_log_inc:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov al, [fd_lognew]
    or al, al
    je .out                         ; nothing arrived
    cmp al, FD_LOGN
    jae .whole                      ; more than the band holds: everything on
                                    ; screen is going anyway
    xor ah, ah
    mov [fd_scrn], ax               ; the rows...
    mov bx, FD_ROWH
    mul bx                          ; DX:AX - the band is tiny, so AX is it
    mov [fd_scry], ax               ; ...and the pixels. BANKED, because the
                                    ; rect below needs DX and `mul` writes it
    call fd_log_y
    mov ax, [fd_ox]
    add ax, FD_TEXTX
    mov cx, ax
    add cx, FD_LOGW * 8 - 1         ; ...so cx+1 is a multiple of 8
    mov bx, [fd_leny]
    mov dx, bx
    add dx, FD_LOGN * FD_ROWH - 1
    mov si, [fd_scry]               ; signed dy, positive scrolls UP
    call OSAPI_GFX_SCROLL
    jc .whole                       ; refused: nothing moved, so redraw it all
    mov bx, FD_LOGN                 ; the rows it vacated ARE the ones that
    sub bx, [fd_scrn]               ; arrived
.fill:
    call fd_log_row
    inc bx
    cmp bx, FD_LOGN
    jb .fill
    mov byte [fd_lognew], 0
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.whole:
    call fd_draw_log
    jmp short .out

; --- fd_logline - in AX = a display row 0..FD_LOGN-1; out AX -> its text -----
; The log is a ring of FD_LOGN slots with [fd_lognext] the one to write, so
; display row 0 is the OLDEST, which is the slot fd_lognext points at.
fd_logline:
    push bx
    push cx
    push dx
    add al, [fd_lognext]
    xor ah, ah
    xor dx, dx
    mov cx, FD_LOGN
    div cx                          ; DX = the ring slot
    mov ax, FD_LOGW + 1
    mul dx
    add ax, fd_log_b
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; fd_log - put a line in the ring. SI = NUL text. NO DRAWING and NO LOCK.
;
; Called from BOTH tasks - the worker logs every command it answers and the UI
; task logs what it did to the disk - so it may not draw and may not take the
; lock. [fd_dirty] is what says the glass is behind, and whoever next holds
; the lock spends it.
; -----------------------------------------------------------------------------
fd_log:
    push ax
    push cx
    push si
    push di
    mov al, [fd_lognext]
    xor ah, ah
    mov cx, FD_LOGW + 1
    mul cx
    add ax, fd_log_b
    mov di, ax
    mov cx, FD_LOGW
.c:
    lodsb
    or al, al
    jz .pad
    mov [di], al
    inc di
    loop .c
    jmp short .term
.pad:
    mov byte [di], ' '
    inc di
    loop .pad
.term:
    mov byte [di], 0
    mov al, [fd_lognext]
    inc al
    cmp al, FD_LOGN
    jb .st
    xor al, al
.st:
    mov [fd_lognext], al
    mov al, [fd_lognew]             ; SATURATES: past a bandful, "everything on
    cmp al, FD_LOGN                 ; screen is going" and one more changes
    jae .mark                       ; nothing about that
    inc al
    mov [fd_lognew], al
.mark:
    or byte [fd_dirty], FDD_LOG
    pop di
    pop si
    pop cx
    pop ax
    ret

; =============================================================================
; STRING HELPERS - all of them append at DI and leave DI past what they wrote
; =============================================================================

; --- fd_dcat - append the NUL string at SI. DI advances, no terminator -------
fd_dcat:
    push ax
.l:
    lodsb
    or al, al
    jz .out
    mov [di], al
    inc di
    jmp short .l
.out:
    pop ax
    ret

; --- fd_dnum - append AX as unsigned decimal ---------------------------------
fd_dnum:
    push ax
    push bx
    push cx
    push dx
    xor cx, cx
    mov bx, 10
.d:
    xor dx, dx
    div bx
    push dx
    inc cx
    or ax, ax
    jnz .d
.e:
    pop ax
    add al, '0'
    mov [di], al
    inc di
    loop .e
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- fd_dnum32 - append DX:AX as unsigned decimal ----------------------------
; A file's size is 32 bits and a listing has to say so.
;
; **THE DIVIDE IS THE LONG ONE AND IT HAS TO BE.** The 8086's `div bx` on a
; 32-bit DX:AX faults with a divide overflow whenever the quotient will not
; fit AX - which for a real file size over 655,350 is most of them - so the
; two-step form is not an optimisation, it is the only one that does not trap:
; divide the high half, carry its REMAINDER into the low half's dividend, and
; the pair of quotients is the 32-bit answer with the final remainder in DX.
fd_dnum32:
    push ax
    push bx
    push cx
    push dx
    push si
    xor si, si                      ; how many digits are on the stack
    mov bx, 10
.d:
    push ax
    mov ax, dx
    xor dx, dx
    div bx                          ; AX = the high quotient, DX = its remainder
    mov cx, ax
    pop ax
    div bx                          ; ...which is the low half's high word, so
                                    ; AX = the low quotient and DX = the digit
    push dx
    inc si
    mov dx, cx                      ; the quotient, back into DX:AX
    mov cx, dx
    or  cx, ax
    jnz .d
.e:
    pop ax
    add al, '0'
    mov [di], al
    inc di
    dec si
    jnz .e
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- fd_dpad - append spaces until DI reaches AX -----------------------------
fd_dpad:
    push ax
.l:
    cmp di, ax
    jae .out
    mov byte [di], ' '
    inc di
    jmp short .l
.out:
    pop ax
    ret

; =============================================================================
; THE WORKER - it owns every socket, and it never touches a disk
; =============================================================================
fd_hire:
    push ax
    push bx
    cmp byte [fd_spawned], 1
    je .out
    mov ax, fd_worker
    mov bx, [fd_win]
    call OSAPI_TASK_SPAWN
    jc .out
    mov byte [fd_spawned], 1
.out:
    pop bx
    pop ax
    ret

fd_worker:
.loop:
    mov bx, [fd_win]
    call OSAPI_TASK_ALIVE           ; the death door: may never return
    call fd_step
    mov ax, 1
    call OSAPI_TASK_SLEEP
    jmp .loop

; -----------------------------------------------------------------------------
; fd_step - one turn. Never blocks, never takes the gfx lock across the wire.
; -----------------------------------------------------------------------------
fd_step:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es                          ; ES = OURS for every NETV_* buffer: the
                                    ; door is the one driver entry point handed
                                    ; the CALLER's segment (SPEC.md 20.11)
    cmp byte [fd_req], FR_NONE
    jne .waiting                    ; a file request is out with the UI task,
                                    ; and NOTHING else may run until it comes
                                    ; back - the stage is its argument
    cmp byte [fd_st], FD_LISTEN
    je .listening
    cmp byte [fd_st], FD_CTRL
    je .serving
    jmp .done

.waiting:
    call fd_kick                    ; the wake may have been dropped when the
    jmp .done                       ; event ring was full - kick again, which
                                    ; is what its CF=1 asks for

; --- LISTEN: is anybody there? ----------------------------------------------
.listening:
    mov al, [fd_lhnd]
    mov bh, NET_CLASS
    mov bl, NETV_ACCEPT
    call OSAPI_DRV_CALL
    jc .lerr
    or ax, ax
    jz .done                        ; nobody yet, which is ORDINARY and not an
    mov [fd_chnd], al               ; error (netpkg.inc)
    mov byte [fd_st], FD_CTRL
    mov byte [fd_auth], 0
    mov word [fd_clen], 0
    mov byte [fd_rowed], 1          ; **A NEW SESSION STARTS AT THE ROOT**, and
                                    ; this is a FLAG rather than the work: a
                                    ; worker may not touch a file (SPEC.md
                                    ; 20.6 rule 7) and standing in a folder is
                                    ; OSAPI_FILE_GOTO. fd_wake spends it, ahead
                                    ; of any request, and there is time for
                                    ; several UI passes before the client's
                                    ; first command arrives - it has to read
                                    ; the 220 and log in first
    call fd_reset_xfer
    mov si, fd_l_conn
    call fd_log
    mov si, fd_r220
    call fd_reply
    jmp .done
.lerr:
    cmp ax, NETE_BUSY
    je .done
    mov si, fd_e_lost
    jmp .fail

; --- CTRL: drain the control line, then push the transfer along -------------
.serving:
    call fd_ctl_poll
    jc .drop
    cmp byte [fd_st], FD_CTRL       ; a QUIT inside fd_ctl_poll may have ended
    jne .done                       ; the session already
    cmp byte [fd_req], FR_NONE      ; **AND THE COMMAND JUST RUN MAY HAVE
    jne .kick                       ; POSTED ONE.** The guard at the top of
                                    ; this proc was taken BEFORE fd_ctl_poll,
                                    ; so it cannot see a request the command
                                    ; itself made - and LIST makes one.
                                    ;
                                    ; Without this, the pass that accepted the
                                    ; LIST went straight on to fd_xfer_poll,
                                    ; found the stage empty (fd_do_list runs on
                                    ; the UI TASK and had not run yet), read
                                    ; that as "the listing is finished", and
                                    ; closed the data connection with a 226.
                                    ; The client saw a perfect exchange - 227,
                                    ; 150, an empty stream, 226 - and reported
                                    ; an empty directory on a disk with four
                                    ; files on it
    call fd_xfer_poll
    jmp short .done
.kick:
    call fd_kick
    jmp short .done
.drop:
    call fd_bye
    jmp short .done
.fail:
    mov [fd_msg], si
    mov byte [fd_st], FD_ERR
    call fd_shutdown
    or byte [fd_dirty], FDD_BTN | FDD_STAT
.done:
    call fd_flush_glass
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- fd_kick - ask for a UI-task turn ---------------------------------------
fd_kick:
    push ax
    push bx
    mov bx, [fd_win]
    call OSAPI_WM_WAKE              ; ISR- and worker-safe, no lock. At most one
    pop bx                          ; is queued per window, so kicking from
    pop ax                          ; every turn is free and cannot fill the
    ret                             ; 16-record ring

; --- fd_flush_glass - the log or the status changed, so put them on screen ---
; **THE LOCK IS TAKEN HERE AND NOWHERE ELSE IN THE WORKER**, and never across
; a wire exchange: a NETV_RECV is up to 274 ms on the cable and the cursor
; would stop dead for it (SPEC.md 20.6 rule 3).
fd_flush_glass:
    push ax
    push bx
    push si
    cmp byte [fd_dirty], 0
    je .out
    mov bx, [fd_win]
    call OSAPI_WM_GEOM              ; CF=1 = not visible, so there is nothing to
    jc .out                         ; draw on and the ring keeps the lines
    call OSAPI_GFX_LOCK
    mov si, [fd_win]
    call fd_layout
    call fd_spend
    call OSAPI_GFX_UNLOCK
.out:
    pop si
    pop bx
    pop ax
    ret

; =============================================================================
; THE CONTROL CONNECTION
; =============================================================================

; --- fd_reply - send the NUL string at SI, then CRLF -------------------------
; **A REPLY IS BEST-EFFORT AND THAT IS DELIBERATE.** NETV_SEND takes what it
; can and says how much, and a control reply is tens of bytes against a
; NET_SKMAX of 1024, so a short take here means the far side has stopped
; reading - which the next poll will see as NSK_CLOSING anyway. Looping until
; it all went would be a blocking call on a worker (netpkg.inc).
fd_reply:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es                          ; **ES IS SET HERE AND NOT LEFT TO THE
                                    ; CALLER.** NETV_SEND reads ES:SI, and two
                                    ; of the callers - fd_do_read and
                                    ; fd_do_write on their failure paths - are
                                    ; still holding the STAGE's segment when
                                    ; they report. The reply would have been
                                    ; sent out of the transfer buffer
    mov di, fd_outb
    call fd_dcat
    mov byte [di], 13
    inc di
    mov byte [di], 10
    inc di
    mov cx, di
    sub cx, fd_outb
    mov si, fd_outb
    mov al, [fd_chnd]
    mov bh, NET_CLASS
    mov bl, NETV_SEND
    call OSAPI_DRV_CALL
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_ctl_poll - take what has arrived and run any COMPLETE line
; out: CF=1 = the control connection is finished
;
; ONE LINE PER TURN, deliberately: a command may post a file request, and
; nothing else may run until that comes back, so draining two commands out of
; one buffer would run the second against a stage the first still owns.
; -----------------------------------------------------------------------------
fd_ctl_poll:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call fd_line_ready              ; is a whole line already buffered?
    jnc .run
    mov al, [fd_chnd]
    mov di, fd_ctlb
    add di, [fd_clen]
    mov cx, FD_CTL
    sub cx, [fd_clen]
    cmp cx, 2
    jb .overflow
    mov bh, NET_CLASS
    mov bl, NETV_RECV
    call OSAPI_DRV_CALL
    jc .rerr
    or cx, cx
    jz .empty
    add [fd_clen], cx
    call fd_line_ready
    jc .none
.run:
    call fd_command
    jmp short .none
.empty:
    mov al, [fd_chnd]
    mov bh, NET_CLASS
    mov bl, NETV_STATUS
    call OSAPI_DRV_CALL
    jc .rerr
    cmp ah, NSK_UP
    je .none
    cmp ah, NSK_CONNECT
    je .none
    or cx, cx
    jnz .none                       ; closing, and there is still data behind:
    jmp short .gone                 ; NOTHING READ IS NOT AN END (netpkg.inc)
.overflow:
    mov word [fd_clen], 0           ; a line longer than the buffer is not a
    mov si, fd_r500                 ; command, so the buffer is thrown away
    call fd_reply                   ; rather than being run as one
.none:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.rerr:
    cmp ax, NETE_BUSY
    je .none
.gone:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; --- fd_line_ready - is there a CR or LF in the buffer? CF=0 = yes, at [fd_lend]
fd_line_ready:
    push ax
    push cx
    push si
    mov si, fd_ctlb
    mov cx, [fd_clen]
    jcxz .no
.l:
    mov al, [si]
    cmp al, 13
    je .yes
    cmp al, 10
    je .yes
    inc si
    loop .l
.no:
    pop si
    pop cx
    pop ax
    stc
    ret
.yes:
    sub si, fd_ctlb
    mov [fd_lend], si
    pop si
    pop cx
    pop ax
    clc
    ret

; -----------------------------------------------------------------------------
; fd_consume - drop the line at the front of fd_ctlb, EOL and all
; -----------------------------------------------------------------------------
fd_consume:
    push ax
    push cx
    push si
    push di
    mov si, [fd_lend]
.eat:
    cmp si, [fd_clen]               ; swallow the whole CR LF pair, and a bare
    jae .shift                      ; CR or LF on its own
    mov al, [fd_ctlb+si]
    cmp al, 13
    je .more
    cmp al, 10
    jne .shift
.more:
    inc si
    jmp short .eat
.shift:
    mov cx, [fd_clen]
    sub cx, si
    mov [fd_clen], cx
    jcxz .out
    mov di, fd_ctlb
    add si, fd_ctlb
.mv:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    loop .mv
.out:
    pop di
    pop si
    pop cx
    pop ax
    ret

; =============================================================================
; THE COMMANDS
; =============================================================================

; -----------------------------------------------------------------------------
; fd_command - split the buffered line into a verb and an argument, dispatch
;
; The verb is upper-cased into fd_verb (4 bytes, space padded) and compared as
; a pair of words, which is what makes the table a list of two `dw`s rather
; than a run of string compares. Four characters is every RFC 959 verb.
; -----------------------------------------------------------------------------
fd_command:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    ; --- the verb ---
    mov word [fd_verb], 0x2020
    mov word [fd_verb+2], 0x2020
    xor si, si
    xor di, di
.v:
    cmp si, [fd_lend]
    jae .varg
    mov al, [fd_ctlb+si]
    cmp al, ' '
    je .varg
    cmp di, 4
    jae .vnext
    cmp al, 'a'
    jb .vst
    cmp al, 'z'
    ja .vst
    sub al, 32                      ; RFC 959: a verb is case-insensitive
.vst:
    mov [fd_verb+di], al
    inc di
.vnext:
    inc si
    jmp short .v
.varg:
    ; --- the argument: everything after ONE space, to the end of the line ---
    cmp si, [fd_lend]
    jae .noarg
    inc si                          ; the separator
.noarg:
    xor di, di
.a:
    cmp si, [fd_lend]
    jae .adone
    cmp di, FD_PATHMAX - 1
    jae .adone
    mov al, [fd_ctlb+si]
    mov [fd_arg+di], al
    inc di
    inc si
    jmp short .a
.adone:
    mov byte [fd_arg+di], 0
    mov [fd_arglen], di
    call fd_logcmd
    call fd_consume                 ; **BEFORE THE HANDLER RUNS.** A handler may
                                    ; post a file request and return, and the
                                    ; next turn must not find the same line
                                    ; still at the front of the buffer
    ; --- dispatch ---
    mov ax, [fd_verb]
    mov dx, [fd_verb+2]
    mov bx, fd_ctab
.d:
    cmp word [bx], 0
    je .unknown
    cmp ax, [bx]
    jne .dn
    cmp dx, [bx+2]
    jne .dn
    mov si, [bx+4]                  ; the flags word: does it need a login?
    test si, 1
    jz .go
    cmp byte [fd_auth], 0
    jne .go
    mov si, fd_r530
    call fd_reply
    jmp short .out
.go:
    call word [bx+6]
    jmp short .out
.dn:
    add bx, 8
    jmp short .d
.unknown:
    mov si, fd_r502
    call fd_reply
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- fd_logcmd - the command, as the window shows it -------------------------
; PASS is logged as its verb alone. A password is not something to put on a
; screen anybody walking past can read, and this window is a log.
fd_logcmd:
    push ax
    push cx
    push si
    push di
    mov di, fd_tmp
    mov cx, 4
    mov si, fd_verb
.v:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    loop .v
    mov ax, [fd_verb]
    cmp ax, 'PA'
    jne .arg
    cmp word [fd_verb+2], 'SS'
    je .term
.arg:
    mov byte [di], ' '
    inc di
    mov si, fd_arg
    call fd_dcat
.term:
    mov byte [di], 0
    mov si, fd_tmp
    call fd_log
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; THE TABLE: verb (two words), flags, handler.
; flags bit 0 = a login is required, which is RFC 959's rule and the whole of
; this server's access control - see fd_c_pass.
; -----------------------------------------------------------------------------
fd_ctab:
    dw 'US','ER', 0, fd_c_user
    dw 'PA','SS', 0, fd_c_pass
    dw 'QU','IT', 0, fd_c_quit
    dw 'NO','OP', 0, fd_c_noop
    dw 'SY','ST', 0, fd_c_syst
    dw 'FE','AT', 0, fd_c_feat
    dw 'TY','PE', 1, fd_c_type
    dw 'MO','DE', 1, fd_c_mode
    dw 'ST','RU', 1, fd_c_stru
    dw 'PA','SV', 1, fd_c_pasv
    dw 'EP','SV', 1, fd_c_epsv
    dw 'PO','RT', 1, fd_c_port
    dw 'PW','D ', 1, fd_c_pwd
    dw 'XP','WD', 1, fd_c_pwd
    dw 'CW','D ', 1, fd_c_cwd
    dw 'XC','WD', 1, fd_c_cwd
    dw 'CD','UP', 1, fd_c_cdup
    dw 'XC','UP', 1, fd_c_cdup
    dw 'LI','ST', 1, fd_c_list
    dw 'NL','ST', 1, fd_c_nlst
    dw 'RE','TR', 1, fd_c_retr
    dw 'ST','OR', 1, fd_c_stor
    dw 'DE','LE', 1, fd_c_dele
    dw 'MK','D ', 1, fd_c_mkd
    dw 'XM','KD', 1, fd_c_mkd
    dw 'RN','FR', 1, fd_c_rnfr
    dw 'RN','TO', 1, fd_c_rnto
    dw 'SI','ZE', 1, fd_c_size
    dw 'AL','LO', 1, fd_c_noop
    dw 'AB','OR', 1, fd_c_abor
    dw 'RM','D ', 1, fd_c_rmd
    dw 'XR','MD', 1, fd_c_rmd
    dw 0, 0, 0, 0

; --- the simple ones ---------------------------------------------------------
fd_c_user:
    push cx
    push si
    push di
    mov byte [fd_auth], 0
    mov si, fd_arg                  ; BANKED, because the command buffer is the
    mov di, fd_userin               ; next command's and PASS arrives later
    mov cx, FD_USERMAX
    call fd_copyn
    mov si, fd_r331
    call fd_reply
    pop di
    pop si
    pop cx
    ret

; -----------------------------------------------------------------------------
; fd_c_pass - and what this server means by access control (SPEC.md 77.15)
;
; **AN EMPTY USER SETTING ACCEPTS ANYONE**, which is what this shipped with and
; what a disk with no FTPD.CFG on it still does. Set one and both halves must
; match: the name case-INSENSITIVELY, because a user types it and FTP has no
; opinion, and the password EXACTLY, because it is a secret and folding its
; case throws bits away.
;
; **THE WINDOW IS STILL THE REAL GATE.** A password here is stored in clear in
; a file on the very disk the server hands out, so it is a courtesy against the
; casual and not a secret against anyone who can read the volume - which is
; every client this server has just given a LIST to, if the file is inside the
; served root. What actually decides whether anyone can reach these files is
; the Start button, which the person at the machine presses, and the Read Only
; box beside it.
;
; It is still checked BEFORE the greeting's verbs do anything, because every
; command that touches the volume is gated on [fd_auth] - so a stray connection
; that never logs in cannot list a directory.
; -----------------------------------------------------------------------------
fd_c_pass:
    push si
    push di
    cmp byte [fd_users], 0
    je .open                        ; no user configured: anyone, as before
    mov si, fd_userin
    mov di, fd_users
    call fd_ieq                     ; the NAME, case-insensitively
    jc .no
    mov si, fd_arg
    mov di, fd_passs
    call fd_eqz                     ; ...and the PASSWORD, exactly
    jc .no
.open:
    mov byte [fd_auth], 1
    mov si, fd_r230
    call fd_reply
    pop di
    pop si
    ret
.no:
    mov byte [fd_auth], 0
    mov si, fd_r530b
    call fd_reply
    pop di
    pop si
    ret

; --- fd_copyn - SI -> DI, NUL included, at most CX bytes --------------------
fd_copyn:
    push ax
    push cx
    push si
    push di
    dec cx
.c:
    mov al, [si]
    or al, al
    jz .term
    mov [di], al
    inc si
    inc di
    loop .c
.term:
    mov byte [di], 0
    pop di
    pop si
    pop cx
    pop ax
    ret

; --- fd_eqz - SI vs DI, EXACTLY, NUL-terminated. CF=0 = equal ---------------
fd_eqz:
    push ax
    push si
    push di
.c:
    mov al, [si]
    cmp al, [di]
    jne .no
    or al, al
    jz .yes
    inc si
    inc di
    jmp short .c
.yes:
    pop di
    pop si
    pop ax
    clc
    ret
.no:
    pop di
    pop si
    pop ax
    stc
    ret

fd_c_quit:
    mov si, fd_r221
    call fd_reply
    call fd_bye
    ret

fd_c_noop:
    mov si, fd_r200
    call fd_reply
    ret

; -----------------------------------------------------------------------------
; fd_c_syst - and why it says UNIX when this is manifestly not Unix
;
; SYST's answer is what a client uses to pick a LIST PARSER, and there are two
; in practice: the `ls -l` shape and DOS's. Answering honestly - `215 OS8088` -
; makes every client fall back to guessing, and a guess that goes wrong shows
; the user an empty directory on a machine that listed it perfectly.
;
; So `UNIX Type: L8` is a statement about the FORMAT OF THE LISTING this
; server emits (fd_list_line writes `ls -l` rows and nothing else), which is
; the question the client is really asking. The About panel and this window
; both say what the machine is; no client reads either.
; -----------------------------------------------------------------------------
fd_c_syst:
    mov si, fd_r215
    call fd_reply
    ret

fd_c_feat:
    push si
    mov si, fd_r211a
    call fd_reply
    mov si, fd_r211b
    call fd_reply
    mov si, fd_r211c
    call fd_reply
    pop si
    ret

; -----------------------------------------------------------------------------
; fd_c_type - A and I are both taken and BOTH MEAN BINARY
;
; A DOS text file already has its CRLFs, so an ASCII transfer to another CRLF
; machine is byte-for-byte identical to a binary one - and translating to LF
; would corrupt every file going the other way. Refusing TYPE A instead would
; break the clients that send it out of habit before every transfer.
; -----------------------------------------------------------------------------
fd_c_type:
    push ax
    mov al, [fd_arg]
    cmp al, 'a'
    jb .up
    cmp al, 'z'
    ja .up
    sub al, 32
.up:
    cmp al, 'A'
    je .ok
    cmp al, 'I'
    je .ok
    cmp al, 'L'
    je .ok
    mov si, fd_r504
    call fd_reply
    pop ax
    ret
.ok:
    mov si, fd_r200t
    call fd_reply
    pop ax
    ret

fd_c_mode:
    push ax
    mov al, [fd_arg]
    and al, 0xDF
    cmp al, 'S'
    je .ok
    mov si, fd_r504
    call fd_reply
    pop ax
    ret
.ok:
    mov si, fd_r200
    call fd_reply
    pop ax
    ret

fd_c_stru:
    push ax
    mov al, [fd_arg]
    and al, 0xDF
    cmp al, 'F'
    je .ok
    mov si, fd_r504
    call fd_reply
    pop ax
    ret
.ok:
    mov si, fd_r200
    call fd_reply
    pop ax
    ret

fd_c_abor:
    call fd_data_drop
    call fd_reset_xfer
    mov si, fd_r226a
    call fd_reply
    ret

; -----------------------------------------------------------------------------
; fd_c_rmd - and it is a real command now (SPEC.md 18.90.2)
;
; It used to refuse with "RMD needs a kernel that has one", which was true:
; the kernel had dskw_rmdir and no slot published it, and the SDK's own note
; by OSAPI_FILE_MKDIR recorded the absence as deliberate. This server is what
; wanted it, so the cell exists and this is an ordinary one-shot.
;
; **AL = 0, THE STRICT FORM.** RFC 959's RMD is specified to FAIL on a
; non-empty directory, and a server that quietly emptied one would be
; destroying data the client believed it was protecting. The recursive form is
; there (AL non-zero) and this deliberately does not reach for it - FTP has no
; standard way for a client to ASK for a recursive delete, so using it here
; would make RMD mean something no client expects.
; -----------------------------------------------------------------------------
fd_c_rmd:
    mov al, FR_RMD
    jmp fd_one

; =============================================================================
; THE DATA CONNECTION
;
; FOUR HANDLES IS THE FLOOR AND THIS IS THE THING THAT SPENDS THEM (netpkg.inc,
; docs/NET-STACK-PLAN.md 1.2): the port-21 listener, the control connection,
; the passive listener and the data connection itself. All four are live at
; once for exactly as long as it takes a client to answer a 227 - and
; fd_data_ready CLOSES THE PASSIVE LISTENER the moment it has accepted, both
; because a passive listener is single-use by definition and because holding a
; fourth handle through a whole transfer would leave a second client unable to
; so much as reach the greeting.
; =============================================================================

; --- fd_pasv_port - the next passive port, rotating --------------------------
; ROTATING because a client that finishes one transfer and immediately starts
; another leaves the previous port in TIME_WAIT at ITS end, and a connect to a
; port in that state is refused for reasons the server cannot see.
fd_pasv_port:
    push bx
    mov al, [fd_pasvn]
    inc al
    cmp al, FD_PASVN
    jb .st
    xor al, al
.st:
    mov [fd_pasvn], al
    xor ah, ah
    add ax, FD_PASVP
    pop bx
    ret

; --- fd_log_pasv - the endpoint the 227 just named --------------------------
; `Data port 2048` in the window, at the moment it matters. A passive
; transfer needs the DATA port reachable as well as port 21, and behind a
; port forward or a NAT that is a second rule somebody has to write - so the
; number goes on the glass rather than only into a reply the user never sees.
fd_log_pasv:
    push ax
    push dx
    push di
    push si
    mov di, fd_outb2
    mov si, fd_l_dport
    call fd_dcat
    mov ax, [fd_dport]
    xor dx, dx
    call fd_dnum32
    mov byte [di], 0
    mov si, fd_outb2
    call fd_log
    pop si
    pop di
    pop dx
    pop ax
    ret

; --- fd_data_listen - open a passive listener. out CF=1 = it could not -------
fd_data_listen:
    push bx
    push cx
    call fd_data_drop               ; whatever the last transfer left
    call fd_pasv_port
    mov [fd_dport], ax
    mov cx, ax
    mov bh, NET_CLASS
    mov bl, NETV_LISTEN
    call OSAPI_DRV_CALL
    jc .no
    mov [fd_dlhnd], al
    mov byte [fd_dmode], DM_PASV
    pop cx
    pop bx
    clc
    ret
.no:
    pop cx
    pop bx
    stc
    ret

; --- fd_c_pasv - 227, with our own address ----------------------------------
; The address comes from NETV_ADDR, which exists for this reply and nothing
; else (netpkg.inc). On the cable it is the DOS box's, which is the true
; answer there: that is the machine an inbound connection reaches.
fd_c_pasv:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call fd_pasv_addr               ; the OVERRIDE if one is set, else our own
    jc .noaddr
    call fd_data_listen
    jc .nosock
    mov di, fd_outb2
    mov si, fd_r227
    call fd_dcat
    xor bx, bx
.q:
    mov al, [fd_ip+bx]
    xor ah, ah
    call fd_dnum
    inc bx
    cmp bx, 4
    jae .port
    mov byte [di], ','
    inc di
    jmp short .q
.port:
    mov byte [di], ','
    inc di
    mov ax, [fd_dport]
    mov al, ah                      ; p1 = the HIGH byte: the pair is
    xor ah, ah                      ; big-endian, p1*256 + p2
    call fd_dnum
    mov byte [di], ','
    inc di
    mov ax, [fd_dport]
    xor ah, ah                      ; ...and p2 the low
    call fd_dnum
    mov byte [di], ')'
    inc di
    mov byte [di], 0
    mov si, fd_outb2
    call fd_reply
    call fd_log_pasv                ; **AND SAY WHICH PORT.** The log said
    jmp short .out                  ; `PASV` and nothing else, so a client
                                    ; refused at the data port looked like a
                                    ; server fault when it was a port that
                                    ; nothing forwarded (SPEC.md 77.22)
.noaddr:
    mov si, fd_r425a
    call fd_reply
    jmp short .out
.nosock:
    mov si, fd_r425
    call fd_reply
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_pasv_addr - the address to put in a 227, into fd_ip
; out: CF=1 there is none to be had
;
; **THE OVERRIDE EXISTS BECAUSE THE SERVER CANNOT WORK THIS OUT** (SPEC.md
; 77.12.2). Behind NAT - 86Box or QEMU with port forwarding, a router, a
; container - the address a client must dial is one the guest has never seen
; and cannot derive: our own is 10.0.2.15 or similar, which is unroutable from
; the far side, and a 227 carrying it tells the client to connect somewhere
; nothing is listening. It is the same feature as vsftpd's `pasv_address` and
; ProFTPD's `MasqueradeAddress`, and it is configuration for the same reason
; they made it configuration.
;
; EPSV needs none of this, carrying only a port - so a client that speaks it
; works behind NAT with no setting at all, and fd_c_pasv's refusal says so.
; -----------------------------------------------------------------------------
fd_pasv_addr:
    push ax
    push si
    push di
    mov ax, [fd_pasv]
    or ax, [fd_pasv+2]
    jz .own
    mov ax, [fd_pasv]               ; the configured one, straight across
    mov [fd_ip], ax
    mov ax, [fd_pasv+2]
    mov [fd_ip+2], ax
    pop di
    pop si
    pop ax
    clc
    ret
.own:
    pop di
    pop si
    pop ax
    jmp fd_getaddr                  ; ...and its CF is the answer

; --- fd_c_epsv - 229, and NO address at all ----------------------------------
; RFC 2428's reply carries only the port, which is why the clients that prefer
; it work on a machine whose address the server cannot name. It is offered
; second rather than first because PASV is what everything understands.
fd_c_epsv:
    push ax
    push si
    push di
    call fd_data_listen
    jc .no
    mov di, fd_outb2
    mov si, fd_r229
    call fd_dcat
    mov ax, [fd_dport]
    call fd_dnum
    mov si, fd_r229b
    call fd_dcat
    mov byte [di], 0
    mov si, fd_outb2
    call fd_reply
    jmp short .out
.no:
    mov si, fd_r425
    call fd_reply
.out:
    pop di
    pop si
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_c_port - active mode: WE connect out to the address the client names
;
; `PORT h1,h2,h3,h4,p1,p2` is rebuilt into a dotted quad, because NETV_OPEN
; takes a host STRING - a name or a quad - and never a packed address, since
; resolution is part of connecting (netpkg.inc).
;
; Six fields are parsed into fd_pf FIRST and the string is built afterwards.
; Doing both in one pass is what the first version tried, and the port's two
; fields have to be combined while the host's four have to be punctuated - so
; one loop ends up carrying two unrelated state machines and a `mul` whose DX
; collides with the flag tracking whether a field had any digits at all.
; -----------------------------------------------------------------------------
fd_c_port:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call fd_data_drop
    mov si, fd_arg
    mov di, fd_pf
    xor cx, cx                      ; fields taken
.nf:
    cmp cx, 6
    jae .built
    xor bx, bx                      ; the accumulator
    mov byte [fd_tmpb], 0           ; ...and whether it saw a digit. IN MEMORY:
                                    ; `mul` below writes DX, so a flag there
                                    ; would be destroyed by the first digit
.dg:
    mov al, [si]
    cmp al, '0'
    jb .fend
    cmp al, '9'
    ja .fend
    inc si
    sub al, '0'
    xor ah, ah
    push ax
    mov ax, bx
    mov bx, 10
    mul bx                          ; DX:AX, and a field is < 256 by the test
    mov bx, ax                      ; below, so AX alone is the answer
    pop ax
    add bx, ax
    mov byte [fd_tmpb], 1
    cmp bx, 255
    ja .bad                         ; a field that cannot be a byte is not a
    jmp short .dg                   ; PORT argument, whatever else it is
.fend:
    cmp byte [fd_tmpb], 0
    je .bad                         ; an empty field
    mov [di], bx
    add di, 2
    inc cx
    mov al, [si]
    cmp al, ','
    jne .built
    inc si
    jmp short .nf
.built:
    cmp cx, 6
    jne .bad
    ; --- the dotted quad ---
    mov di, fd_dhost
    xor bx, bx
.q:
    mov ax, [fd_pf+bx]
    call fd_dnum
    add bx, 2
    cmp bx, 8
    jae .qdone
    mov byte [di], '.'
    inc di
    jmp short .q
.qdone:
    mov byte [di], 0
    ; --- the port: p1 * 256 + p2, big-endian on the wire ---
    mov ax, [fd_pf+8]
    mov ah, al
    xor al, al
    add ax, [fd_pf+10]
    mov [fd_dport], ax
    or ax, ax
    jz .bad                         ; port 0 is not a port
    mov si, fd_dhost
    mov cx, ax
    mov bh, NET_CLASS
    mov bl, NETV_OPEN
    call OSAPI_DRV_CALL
    jc .noconn                      ; **NOT 501.** The argument parsed; what
                                    ; failed is the CONNECTION
    mov [fd_dhnd], al
    mov byte [fd_dmode], DM_PORT
    mov si, fd_r200
    call fd_reply
    jmp short .out
.noconn:
    ; 425 IS TRANSIENT AND 501 IS PERMANENT, and the difference decides
    ; whether the client retries. The commonest cause here is NETE_FULL: four
    ; handles (netpkg.inc), and a session that has just ended still holds one
    ; while TCP finishes its close - so a client reconnecting immediately
    ; finds nothing free. Answered 501 it gives up and reports a malformed
    ; command; answered 425 it tries again a moment later and succeeds.
    call fd_data_drop
    mov si, fd_r425
    call fd_reply
    jmp short .out
.bad:
    call fd_data_drop
    mov si, fd_r501
    call fd_reply
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- fd_data_drop - close whatever data handles are open ---------------------
fd_data_drop:
    push ax
    push bx
    cmp byte [fd_dhnd], 0
    je .l
    mov al, [fd_dhnd]
    mov bh, NET_CLASS
    mov bl, NETV_CLOSE
    call OSAPI_DRV_CALL
    mov byte [fd_dhnd], 0
.l:
    cmp byte [fd_dlhnd], 0
    je .out
    mov al, [fd_dlhnd]
    mov bh, NET_CLASS
    mov bl, NETV_CLOSE
    call OSAPI_DRV_CALL
    mov byte [fd_dlhnd], 0
.out:
    mov byte [fd_dmode], DM_NONE
    pop bx
    pop ax
    ret

; --- fd_reset_xfer - forget everything about a transfer ----------------------
fd_reset_xfer:
    mov byte [fd_xf], FX_NONE
    mov word [fd_sfill], 0
    mov word [fd_sout], 0
    mov word [fd_foff], 0
    mov word [fd_foff+2], 0
    mov byte [fd_created], 0
    mov word [fd_lord], 0
    mov byte [fd_lmore], 0
    mov word [fd_xbytes], 0
    mov word [fd_xbytes+2], 0
    call fd_wdog_stamp              ; LAST, so the stamp records the counters
                                    ; this routine just zeroed rather than the
                                    ; finished transfer's - a fresh deadline
                                    ; for whatever comes next
    ret

; -----------------------------------------------------------------------------
; fd_data_ready - is the data connection usable yet?
; out: CF=0 = yes; CF=1 = not yet (or it failed, and [fd_xf] is FX_NONE)
; -----------------------------------------------------------------------------
fd_data_ready:
    push ax
    push bx
    push cx
    mov al, [fd_dmode]
    cmp al, DM_UP
    je .yes
    cmp al, DM_PASV
    je .pasv
    cmp al, DM_PORT
    je .port
    jmp short .no                   ; DM_NONE: nothing was ever arranged
.pasv:
    mov al, [fd_dlhnd]
    mov bh, NET_CLASS
    mov bl, NETV_ACCEPT
    call OSAPI_DRV_CALL
    jc .busy
    or ax, ax
    jz .no                          ; nobody yet - the ordinary answer
    mov [fd_dhnd], al
    mov al, [fd_dlhnd]              ; **THE LISTENER GOES NOW.** It is single-use
    mov bh, NET_CLASS               ; and it is the fourth of four handles
    mov bl, NETV_CLOSE
    call OSAPI_DRV_CALL
    mov byte [fd_dlhnd], 0
    mov byte [fd_dmode], DM_UP
    jmp short .yes
.port:
    mov al, [fd_dhnd]
    mov bh, NET_CLASS
    mov bl, NETV_STATUS
    call OSAPI_DRV_CALL
    jc .busy
    cmp ah, NSK_UP
    je .isup
    cmp ah, NSK_CONNECT
    je .no
    jmp short .failed
.isup:
    mov byte [fd_dmode], DM_UP
.yes:
    pop cx
    pop bx
    pop ax
    clc
    ret
.busy:
    cmp ax, NETE_BUSY
    je .no
.failed:
    call fd_data_drop
    mov byte [fd_xf], FX_NONE
.no:
    pop cx
    pop bx
    pop ax
    stc
    ret

; =============================================================================
; THE TRANSFERS - and every one of them is a stage-and-commit loop
;
; Nothing here touches a file. Each of these fills the stage or drains it and
; asks the UI task for the disk half through [fd_req] (see the file header),
; then does nothing at all until the answer comes back.
; =============================================================================

; --- fd_post - hand a request to the UI task and stop -----------------------
; in: AL = an FR_*. **THE FLAG IS WRITTEN LAST**: every argument is already in
; place, and the UI task may run the instant this byte lands.
fd_post:
    mov [fd_req], al
    call fd_kick
    ret

; -----------------------------------------------------------------------------
; fd_xfer_poll - push whatever transfer is running along by one step
; -----------------------------------------------------------------------------
; -----------------------------------------------------------------------------
; fd_log_stall - one line naming WHERE a transfer died and what the wire said
;
; The field cannot attach a debugger, and the one thing every report of this
; failure agreed on was a byte count - "always the exact same 106KB" - which
; is the observation that ruled out a timing race and sent this looking at
; the stack instead. So the server writes that number down itself, with the
; socket's own state beside it: `Stalled: 106496 bytes, sk 3 q 0`.
;
; NSK_* is what NETV_STATUS answers in AH and the queued count in CX, so a
; stall with the socket still UP and nothing queued is a different bug from
; one with the socket already CLOSING - and telling those apart is most of
; the remaining work (SPEC.md 77.19.1).
; -----------------------------------------------------------------------------
fd_log_stall:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov di, fd_outb2
    mov si, fd_l_stall
    call fd_dcat
    mov ax, [fd_xbytes]
    mov dx, [fd_xbytes+2]
    call fd_dnum32
    mov si, fd_l_stb
    call fd_dcat
    mov al, [fd_dhnd]               ; ...and what the DRIVER thinks of it
    mov bh, NET_CLASS
    mov bl, NETV_STATUS
    call OSAPI_DRV_CALL
    jc .nost
    push cx
    mov al, ah                      ; AH = NSK_*
    xor ah, ah
    call fd_dnum
    mov si, fd_l_stq
    call fd_dcat
    pop ax                          ; CX = what is still queued
    call fd_dnum
.nost:
    mov byte [di], 0
    mov si, fd_outb2
    call fd_log
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_wdog_stamp / fd_wdog_check - the transfer watchdog (SPEC.md 77.19)
;
; PROGRESS IS MEASURED, NOT ASSUMED. The stamp is taken against a PROGRESS
; COUNTER rather than on every poll, because fd_xfer_poll runs on the worker
; many times a second whether or not a byte has moved - stamping there would
; make the watchdog a clock that can never expire, which is the shape this
; kind of guard usually fails in.
;
; What counts as progress is the same number for both directions: the stage's
; fill for a receive and its drain for a send. Either one changing means the
; wire is alive.
;
; The comparison is `sub` and `cmp`, which is modular in 16 bits and therefore
; correct across the tick counter's own wrap - the discipline SPEC.md 13.9's
; timer and sch_isr's wake scan both use.
; -----------------------------------------------------------------------------
fd_wdog_stamp:
    push ax
    call OSAPI_GET_TICKS
    mov [fd_wdog], ax
    mov ax, [fd_sfill]
    add ax, [fd_sout]               ; the two together: one of them moves on
    mov [fd_wprog], ax              ; every byte, in either direction
    pop ax
    ret

fd_wdog_check:
    push ax
    push bx
    mov ax, [fd_sfill]
    add ax, [fd_sout]
    cmp ax, [fd_wprog]
    jne .moved
    call OSAPI_GET_TICKS
    sub ax, [fd_wdog]
    cmp ax, FD_WDOG_T
    jb .ok
    pop bx                          ; EXPIRED: the socket goes back, which is
    pop ax                          ; the whole point - the reply is a courtesy
    stc                             ; to a client that may not still be there
    ret
.moved:
    push cx                         ; ...and BANK HOW FAR, because a stall that
    mov cx, ax                      ; says only "it stopped" sends the next
    sub cx, [fd_wprog]              ; person looking in the wrong place
    add [fd_xbytes], cx
    adc word [fd_xbytes+2], 0
    pop cx
    call fd_wdog_stamp
.ok:
    pop bx
    pop ax
    clc
    ret

fd_xfer_poll:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov al, [fd_xf]
    cmp al, FX_NONE
    je .out
    call fd_wdog_check              ; **BEFORE the work, not after**: a poll
    jc .stalled                     ; that refuses to send must still be able
    cmp al, FX_LIST                 ; to expire, and every branch below can
    je .list                        ; return without moving a byte
    cmp al, FX_RETR
    je .retr
    cmp al, FX_STOR
    je .stor
    jmp .out
.stalled:
    call fd_log_stall               ; **THE LOG IS THE INSTRUMENT.** A stall
    mov si, fd_r426                 ; that only says "it stopped" leaves the
    call fd_xfail                   ; next person guessing; one that names the
    jmp .out                        ; byte it stopped at, and what the socket
                                    ; thought, is a measurement (SPEC.md 77.19.1)
.list:
    call fd_send_stage
    jc .out                         ; still draining, or the wire is busy
    cmp byte [fd_lmore], 0
    je .lend
    mov al, FR_LIST                 ; more entries: refill the stage
    call fd_post
    jmp short .out
.lend:
    call fd_xdone
    jmp short .out
.retr:
    call fd_send_stage
    jc .out
    cmp byte [fd_lmore], 0          ; FR_READ sets it when the chunk it
    je .lend                        ; delivered was a full one, so there may
    mov al, FR_READ                 ; be more
    call fd_post
    jmp short .out
.stor:
    call fd_recv_stage
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_send_stage - push [fd_sout]..[fd_sfill] of the stage at the data socket
; out: CF=1 = there is more to send (or the wire was busy); CF=0 = it is empty
; -----------------------------------------------------------------------------
fd_send_stage:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call fd_data_ready
    jc .later
    mov ax, [fd_sfill]
    sub ax, [fd_sout]
    jz .empty
    cmp ax, NET_SKMAX
    jbe .n
    mov ax, NET_SKMAX
.n:
    mov cx, ax
    mov si, fd_stage                ; ES is OURS - the door put it there
    add si, [fd_sout]
    mov al, [fd_dhnd]
    mov bh, NET_CLASS
    mov bl, NETV_SEND
    call OSAPI_DRV_CALL
    jc .later
    add [fd_sout], cx               ; **BY WHAT WAS TAKEN**, which may be less
    mov ax, [fd_sout]               ; than asked and may be 0 (netpkg.inc)
    cmp ax, [fd_sfill]
    jb .later
.empty:
    mov word [fd_sout], 0
    mov word [fd_sfill], 0
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.later:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; fd_recv_stage - take bytes into the stage; commit whenever a CHUNK is full
;
; **A COMMIT IS A WHOLE NUMBER OF CLUSTERS AND THE LAST ONE IS WHATEVER IS
; LEFT** - OSAPI_FILE_APPEND's precondition, and the reason this buffers
; instead of writing what each recv happened to deliver (SPEC.md 18.4.4).
; -----------------------------------------------------------------------------
fd_recv_stage:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call fd_data_ready
    jc .out
    mov ax, [fd_chunk]
    sub ax, [fd_sfill]
    jz .commit                      ; a full chunk is waiting to go to disk
    cmp ax, NET_SKMAX
    jbe .n
    mov ax, NET_SKMAX
.n:
    mov cx, ax
    mov di, fd_stage
    add di, [fd_sfill]
    mov al, [fd_dhnd]
    mov bh, NET_CLASS
    mov bl, NETV_RECV
    call OSAPI_DRV_CALL
    jc .busyq
    or cx, cx
    jz .quiet
    add [fd_sfill], cx
    mov ax, [fd_sfill]
    cmp ax, [fd_chunk]
    jb .out
.commit:
    mov al, FR_WCREATE
    cmp byte [fd_created], 0
    je .p
    mov al, FR_WAPPEND
.p:
    call fd_post
    jmp short .out
.quiet:
    ; NOTHING READ IS NOT AN END (netpkg.inc): the end is NSK_CLOSING with
    ; nothing left to read, and a transfer that believed a zero would truncate
    ; every file that arrived in more than one piece.
    mov al, [fd_dhnd]
    mov bh, NET_CLASS
    mov bl, NETV_STATUS
    call OSAPI_DRV_CALL
    jc .busyq
    cmp ah, NSK_UP
    je .out
    cmp ah, NSK_CONNECT
    je .out
    or cx, cx
    jnz .out                        ; closing, and there is still data behind
    ; --- the client has finished. Commit the tail, whatever size it is ---
    cmp word [fd_sfill], 0
    jne .last
    cmp byte [fd_created], 0
    jne .fin
.last:
    mov al, FR_WCREATE
    cmp byte [fd_created], 0
    je .lp
    mov al, FR_WAPPEND
.lp:
    mov byte [fd_lmore], 2          ; ...and this was the LAST one, so fd_wake
    call fd_post                    ; finishes the transfer rather than asking
    jmp short .out                  ; for more
.fin:
    call fd_xdone
.busyq:
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
; fd_xrefuse - say no to a transfer the client has ALREADY dialled in for
;
; **A REFUSAL MUST RELEASE THE DATA CONNECTION.** By the time RETR or STOR
; arrives the client has answered the 227 and its end is connected, so a
; refusal that only sends a reply leaves a passive listener armed with a
; connection waiting on it that nothing will ever accept.
;
; It is not merely untidy: those handles are FOUR (netpkg.inc), and a leaked
; one is the fourth. Measured, a read-only STOR followed by an ordinary LIST
; left the listener, the control connection, the stranded socket and the new
; passive listener all live - so NETV_ACCEPT had no handle to make the data
; connection from, and the LIST sat at its 150 until the client timed out. A
; refusal one command earlier is what a hung transfer two commands later
; looked like.
; -----------------------------------------------------------------------------
fd_xrefuse:
    call fd_data_drop
    call fd_reset_xfer
    call fd_reply
    ret

; --- fd_xdone - a transfer finished cleanly ----------------------------------
fd_xdone:
    push si
    call fd_data_drop
    call fd_reset_xfer
    mov si, fd_r226
    call fd_reply
    pop si
    ret

; -----------------------------------------------------------------------------
; fd_ferr_sel - AX = a FERR_* -> SI = the reply that is TRUE about it
; out: SI = the string; preserves everything else
;
; **THE SERVER USED TO ANSWER 552 "disk full or protected" TO EVERY WRITE
; FAILURE**, and the field found out the hard way what that costs. Uploading
; `banana split.mod` failed instantly with "disk full or protected" on a
; volume with 20MB free; the name was the problem - 8.3 has no room for
; twelve characters and a space - and the reply sent the investigation at the
; disk instead. Renaming it to `banana.mod` worked.
;
; The kernel has said which it was all along (FERR_NAME 3, FERR_FULL 6,
; FERR_PROT 8 - os88api.inc); this package threw the distinction away one
; instruction after receiving it. A reply that names the wrong cause is worse
; than a vague one, because it is ACTED on: SPEC.md 47 rule 3's rule about
; greying a fact rather than a guess, one layer out at the wire.
; -----------------------------------------------------------------------------
fd_ferr_sel:
    cmp ax, FERR_NAME
    je .name
    cmp ax, FERR_FULL
    je .full
    cmp ax, FERR_DIRFULL
    je .full
    cmp ax, FERR_PROT
    je .prot
    mov si, fd_r552                 ; FERR_IO, FERR_NODISK and anything new:
    ret                             ; the honest catch-all is "it failed"
.name:
    mov si, fd_r553
    ret
.full:
    mov si, fd_r552f
    ret
.prot:
    mov si, fd_r550w
    ret

; --- fd_xfail - it did not. SI = the reply to send ---------------------------
fd_xfail:
    call fd_data_drop
    call fd_reset_xfer
    call fd_reply
    ret

; =============================================================================
; THE COMMANDS THAT MOVE DATA
; =============================================================================

; --- fd_have_data - is a PASV or PORT still armed? CF=1 = no, and 425 sent ---
fd_have_data:
    push si
    cmp byte [fd_dmode], DM_NONE
    jne .ok
    mov si, fd_r425n
    call fd_reply
    pop si
    stc
    ret
.ok:
    pop si
    clc
    ret

; --- fd_c_list / fd_c_nlst ---------------------------------------------------
; NLST is the same walk with only the name on each line, which is one byte of
; state rather than a second builder - and the two CANNOT drift about which
; entries they show, which is the part that matters.
fd_c_list:
    mov byte [fd_lstyle], 0
    jmp short fd_list_go
fd_c_nlst:
    mov byte [fd_lstyle], 1
fd_list_go:
    push si
    call fd_have_data
    jc .out
    mov word [fd_lord], 0
    mov word [fd_sfill], 0
    mov word [fd_sout], 0
    mov byte [fd_lmore], 0
    mov si, fd_r150
    call fd_reply
    mov byte [fd_xf], FX_LIST
    mov al, FR_LIST
    call fd_post
.out:
    pop si
    ret

; --- fd_c_retr ---------------------------------------------------------------
fd_c_retr:
    push si
    call fd_have_data
    jc .out
    cmp word [fd_arglen], 0
    je .noname
    mov word [fd_foff], 0
    mov word [fd_foff+2], 0
    mov word [fd_sfill], 0
    mov word [fd_sout], 0
    mov byte [fd_lmore], 0
    call fd_keepname                ; **THE NAME IS BANKED HERE TOO.** A RETR
                                    ; runs for as long as the download takes
                                    ; and the control buffer is reused by the
                                    ; next command, exactly as it is for STOR
    mov al, FR_RDCHK                ; **THE CHECK COMES FIRST**: a 150 sent
    call fd_post                    ; before the file is known to exist has to
                                    ; be followed by a 550, and some clients
                                    ; have already opened their end by then
    jmp short .out
.noname:
    mov si, fd_r501
    call fd_reply
.out:
    pop si
    ret

; --- fd_c_stor ---------------------------------------------------------------
fd_c_stor:
    push si
    call fd_have_data
    jc .out
    cmp word [fd_arglen], 0
    je .noname
    cmp byte [fd_ro], 0
    je .allowed
    mov si, fd_r550w
    call fd_xrefuse
    jmp short .out
.allowed:
    mov word [fd_sfill], 0
    mov word [fd_sout], 0
    mov byte [fd_created], 0
    mov byte [fd_lmore], 0
    call fd_setchunk                ; the cluster-rounded commit size, for THIS
    jc .noroom                      ; volume, now (SPEC.md 52.3)
    call fd_keepname
    mov si, fd_r150
    call fd_reply
    mov byte [fd_xf], FX_STOR
    jmp short .out
.noroom:
    mov si, fd_r452
    call fd_reply
    jmp short .out
.noname:
    mov si, fd_r501
    call fd_xrefuse
.out:
    pop si
    ret

; -----------------------------------------------------------------------------
; fd_setchunk - the commit size for the volume we are standing on
; out: CF=1 = the stage cannot hold even one cluster
;
; **DERIVED PER TRANSFER AND NEVER BAKED IN.** A floppy's cluster is 512 and a
; hard-disk partition's is chosen from its capacity, up to 8KB (SPEC.md 52.3),
; and a CWD between two transfers can move between them - so a chunk sized
; once at startup is wrong on the second volume. OSAPI_FILE_DFREE answers
; SECTORS per cluster in BX and does NO disk I/O, which is why asking every
; time is free.
;
; It runs on the UI task's side of the fence by being called from a COMMAND
; handler - those run on the worker. So it does not call DFREE itself; the
; wake handler banks the answer in [fd_spc] whenever it does file work, and
; this rounds against that. [fd_spc] starts at 1 (a 512-byte cluster), which
; is every floppy and the safe assumption for a volume nothing has asked
; about yet: too SMALL a chunk is merely more commits, where too large a one
; is an append that FERR_NAMEs.
; -----------------------------------------------------------------------------
fd_setchunk:
    push ax
    push bx
    push dx
    mov al, [fd_spc]
    xor ah, ah
    or ax, ax
    jnz .n
    mov ax, 1
.n:
    mov bx, 512
    mul bx                          ; DX:AX = the cluster in bytes; a cluster
    or dx, dx                       ; over 64KB is not a thing this kernel
    jnz .no                         ; mounts (SPEC.md 18.7), so DX set is junk
    mov bx, ax
    or bx, bx
    jz .no
    mov ax, FD_STGSZ
    xor dx, dx
    div bx                          ; how many whole clusters fit the stage
    or ax, ax
    jz .no
    mul bx
    mov [fd_chunk], ax
    pop dx
    pop bx
    pop ax
    clc
    ret
.no:
    pop dx
    pop bx
    pop ax
    stc
    ret

; --- fd_keepname - bank the argument as the transfer's name ------------------
; The command line buffer is reused by the next command, and a STOR runs for
; as long as the upload takes - so the name has to be copied out of it.
fd_keepname:
    push ax
    push cx
    push si
    push di
    mov si, fd_arg
    mov di, fd_xname
    mov cx, FD_PATHMAX
.c:
    lodsb
    mov [di], al
    inc di
    or al, al
    jz .out
    loop .c
    mov byte [fd_xname + FD_PATHMAX - 1], 0
.out:
    pop di
    pop si
    pop cx
    pop ax
    ret

; --- the one-shot file commands: all of them are a request and a wait --------
fd_c_dele:
    mov al, FR_DELE
    jmp short fd_one
fd_c_mkd:
    mov al, FR_MKD
    jmp short fd_one
fd_c_rnfr:
    mov al, FR_RNFR
    jmp short fd_one
fd_c_rnto:
    mov al, FR_RNTO
    jmp short fd_one
fd_c_cwd:
    mov al, FR_CWD
    jmp short fd_one
fd_c_size:
    mov al, FR_SIZE
    jmp short fd_one
fd_c_pwd:
    mov al, FR_PWD
    jmp short fd_one

fd_c_cdup:
    push si
    mov word [fd_arg], '..'         ; CDUP is CWD .. and shares its walker, so
    mov byte [fd_arg+2], 0          ; the parent link is resolved in exactly
    mov byte [fd_arglen], 2         ; one place (SPEC.md 19.5's type-3 row)
    mov al, FR_CWD
    call fd_one
    pop si
    ret

; --- fd_one - post a request whose whole answer is one reply -----------------
fd_one:
    push bx
    cmp byte [fd_ro], 0
    je .go
    call fd_iswrite
    jnc .go
    mov si, fd_r550w
    call fd_reply
    pop bx
    ret
.go:
    call fd_post
    pop bx
    ret

; --- fd_iswrite - CF=1 if AL is a request the Read Only box must refuse ------
fd_iswrite:
    cmp al, FR_DELE
    je .yes
    cmp al, FR_MKD
    je .yes
    cmp al, FR_RMD
    je .yes
    cmp al, FR_RNTO
    je .yes
    clc
    ret
.yes:
    stc
    ret

; =============================================================================
; THE UI TASK'S HALF - everything in this system that touches a disk
;
; OSAPI_WM_ONWAKE's handler: called SI = our window, on the UI task, billed to
; this instance, **WITHOUT THE GFX LOCK**. That last part is the whole reason
; the design works - it is the one callback allowed to call the file slots,
; and it must take the lock itself before it draws anything.
;
; It is a KICK and not a message: nothing is delivered with it, a stale one is
; possible, and one may arrive with nothing to do - so the first thing it does
; is look at [fd_req] and the commonest answer is "nothing".
; =============================================================================
fd_wake:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    cmp byte [fd_rowed], 0          ; the session reset, BEFORE the request -
    je .noroot                      ; a LIST posted in the same pass has to
    mov byte [fd_rowed], 0          ; find the root already stood in
    call fd_goroot
    call fd_pathroot
    mov byte [fd_cdepth], 0
.noroot:
    mov al, [fd_req]
    cmp al, FR_NONE
    je .glass
    call fd_dfree_bank              ; the volume's cluster size, banked for
                                    ; fd_setchunk on the worker's side
    mov al, [fd_req]
    cmp al, FR_LIST
    je .r_list
    cmp al, FR_RDCHK
    je .r_rdchk
    cmp al, FR_READ
    je .r_read
    cmp al, FR_WCREATE
    je .r_write
    cmp al, FR_WAPPEND
    je .r_write
    cmp al, FR_DELE
    je .r_dele
    cmp al, FR_MKD
    je .r_mkd
    cmp al, FR_RNFR
    je .r_rnfr
    cmp al, FR_RNTO
    je .r_rnto
    cmp al, FR_CWD
    je .r_cwd
    cmp al, FR_PWD
    je .r_pwd
    cmp al, FR_SIZE
    je .r_size
    cmp al, FR_RMD
    je .r_rmd
    jmp .clear

.r_list:  call fd_do_list
          jmp short .clear
.r_rdchk: call fd_do_rdchk
          jmp short .clear
.r_read:  call fd_do_read
          jmp short .clear
.r_write: call fd_do_write
          jmp short .clear
.r_dele:  call fd_do_dele
          jmp short .clear
.r_mkd:   call fd_do_mkd
          jmp short .clear
.r_rnfr:  call fd_do_rnfr
          jmp short .clear
.r_rnto:  call fd_do_rnto
          jmp short .clear
.r_cwd:   call fd_do_cwd
          jmp short .clear
.r_pwd:   call fd_do_pwd
          jmp short .clear
.r_size:  call fd_do_size
          jmp short .clear
.r_rmd:   call fd_do_rmd

.clear:
    mov byte [fd_req], FR_NONE      ; **LAST, AND AFTER EVERY RESULT IS
                                    ; WRITTEN.** The worker is watching this
                                    ; byte and reads the stage the moment it
                                    ; goes to zero
.glass:
    cmp byte [fd_dirty], 0
    je .out
    mov bx, [fd_win]
    call OSAPI_WM_GEOM
    jc .out
    call OSAPI_GFX_LOCK             ; the one callback that has to take it
    mov si, [fd_win]                ; itself, and it may not draw before it has
    call fd_layout
    call fd_spend
    call OSAPI_GFX_UNLOCK
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- fd_dfree_bank - the volume's cluster size, for fd_setchunk --------------
; No disk I/O (the SDK says so), so this is free to ask on every request.
fd_dfree_bank:
    push ax
    push bx
    push dx
    call OSAPI_FILE_DFREE           ; BX = SECTORS per cluster
    jc .out
    or bl, bl
    jz .out
    mov [fd_spc], bl
.out:
    pop dx
    pop bx
    pop ax
    ret

; =============================================================================
; PATHS
;
; **A NAME RESOLVES IN THE INSTANCE'S OWN DIRECTORY** (SPEC.md 19.2.1), so the
; FTP session's working directory IS this instance's - the kernel banks and
; restores it underneath every file cell, and no Disk window, driver or other
; application can move it. That is why there is no path state here beyond the
; string PWD prints.
;
; A path with a '/' in it is walked with OSAPI_FILE_GOTO and walked back
; afterwards. It has to be GOTO and not GOTO_Q: the quiet twin deliberately
; does not move the app's own folder, so inst_vol_enter would stand us back in
; it before the very next file cell resolved anything.
; =============================================================================

; -----------------------------------------------------------------------------
; fd_split - SI = a path; leave the LEAF in fd_leaf and walk to its directory
; out: CF=1 = a component did not exist; [fd_banked] says whether to walk back
; -----------------------------------------------------------------------------
fd_split:
    push ax
    push bx
    push cx
    push dx
    push di
    mov byte [fd_banked], 0
    call fd_lastsep                 ; AX -> the last '/' , or 0
    or ax, ax
    jz .bare
    call fd_bank
    mov si, [fd_pathp]
    cmp byte [si], '/'
    jne .rel
    inc si
    push si
    call fd_goroot
    pop si
    jc .fail
.rel:
    ; walk every component up to (but not including) the leaf
.comp:
    mov di, fd_comp
    xor cx, cx
.cc:
    mov al, [si]
    or al, al
    jz .cdone
    cmp al, '/'
    je .cdone
    cmp cx, FD_NAMEMAX - 1
    jae .skip
    mov [di], al
    inc di
    inc cx
.skip:
    inc si
    jmp short .cc
.cdone:
    mov byte [di], 0
    cmp byte [si], '/'
    jne .leaf                       ; no separator left: this was the LEAF
    inc si
    jcxz .comp                      ; an empty component ('//') is nothing
    push si
    mov si, fd_comp
    call fd_enter
    pop si
    jc .fail
    jmp short .comp
.leaf:
    mov si, fd_comp
    mov di, fd_leaf
    call fd_copyz
    call fd_mangle83                ; ...and the leaf is 8.3 by the time ANY
    pop di                          ; command sees it (SPEC.md 77.20)
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.bare:
    cmp byte [fd_mlevel], 0         ; A BARE NAME AT THE MACHINE ROOT IS NOT A
    jne .fail                       ; FILE. There is no directory to resolve it
                                    ; in, and resolving it in whichever volume
                                    ; happened to be current last would serve a
                                    ; folder the client was never shown
    mov si, [fd_pathp]
    mov di, fd_leaf
    call fd_copyz
    call fd_mangle83                ; the bare-name exit takes the same path,
    pop di                          ; or `STOR long name.mod` in the served
    pop dx                          ; root would still refuse
    pop cx
    pop bx
    pop ax
    clc
    ret
.fail:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; =============================================================================
; fd_mangle83 - collapse [fd_leaf] to a name 8.3 can hold (SPEC.md 77.20)
;
; `banana split.mod` becomes `BANANA~1.MOD`, the way every DOS-era system
; showed a long name, rather than being refused. The field asked for exactly
; this: a refusal that explains itself is honest, but a name that WORKS is
; better, and the client has no way to know this machine's rules in advance.
;
; **A NAME THAT IS ALREADY LEGAL IS LEFT ALONE**, and that is what makes the
; mapping round-trip: LIST shows `BANANA~1.MOD`, the client asks for
; `BANANA~1.MOD`, and that name passes through here untouched, so RETR, DELE,
; SIZE and RNFR all reach the file LIST advertised. Mangling unconditionally
; would collapse `BANANA~1.MOD` to `BANANA~1.MOD` by luck and something like
; `README.TXT` to `README~1.TXT` by rule, breaking every name it had just
; shown.
;
; It is DETERMINISTIC - always `~1`, never a search for a free `~2` - and
; that is a deliberate trade rather than an oversight. A counter has to be
; resolved against the directory, which makes the name depend on what is
; already there: the same upload would land on a different name on a
; different disk, and DELE could not compute the name it had listed. The cost
; is that two long names sharing their first six legal characters collapse
; together, and the second STOR replaces the first - which is what STOR means
; anyway. `~1` is a courtesy to a human reading the listing, not a counter.
; =============================================================================
fd_mangle83:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call fd_is83                    ; already legal? then it is not ours to
    jnc .out                        ; touch
    ; --- the extension: the LAST dot, up to three legal characters ---------
    mov si, fd_leaf
    call fd_lastdot                 ; BX -> the last '.', or 0
    mov di, fd_mext
    xor cx, cx
    or bx, bx
    jz .noext
    mov si, bx
    inc si
.ex:
    mov al, [si]
    or al, al
    jz .noext
    call fd_c83                     ; upcases, CF=1 = drop it
    jc .exn
    cmp cx, 3
    jae .noext
    mov [di], al
    inc di
    inc cx
.exn:
    inc si
    jmp short .ex
.noext:
    mov byte [di], 0
    ; --- the stem: up to SIX legal characters before that dot -------------
    mov si, fd_leaf
    mov di, fd_leaf
    xor cx, cx
.st:
    mov al, [si]
    or al, al
    jz .stn
    cmp si, bx                      ; stop AT the last dot (bx = 0 means no
    je .stn                         ; dot, and si never equals 0)
    call fd_c83
    jc .stnx
    cmp cx, 6
    jae .stn
    mov [di], al
    inc di
    inc cx
.stnx:
    inc si
    jmp short .st
.stn:
    jcxz .nostem
.tilde:
    mov word [di], '~1'             ; two bytes, low first: '~' then '1'
    add di, 2
    mov si, fd_mext
    cmp byte [si], 0
    je .done
    mov byte [di], '.'
    inc di
.ec:
    mov al, [si]
    or al, al
    jz .done
    mov [di], al
    inc di
    inc si
    jmp short .ec
.done:
    mov byte [di], 0
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.nostem:
    mov di, fd_leaf                 ; nothing legal survived - `...` or a name
    mov si, fd_s_file               ; that is all spaces. It still has to
    call fd_copyz                   ; become SOMETHING, and FILE~1 is a name a
    mov di, fd_leaf                 ; person can see and delete
    add di, 4
    jmp short .tilde

; --- fd_is83 - is [fd_leaf] already a legal 8.3 name? CF=0 = yes ------------
; The kernel's dskw_name83 rule, asked rather than assumed: stem 1..8 legal
; characters, at most one dot, extension 1..3 if the dot is there.
fd_is83:
    push ax
    push cx
    push si
    mov si, fd_leaf
    xor cx, cx
.s:
    mov al, [si]
    or al, al
    jz .send
    cmp al, '.'
    je .dot
    call fd_c83
    jc .no
    inc cx
    cmp cx, 8
    ja .no
    inc si
    jmp short .s
.send:
    jcxz .no                        ; empty
    jmp short .yes
.dot:
    jcxz .no                        ; '.TXT' has no stem
    inc si
    xor cx, cx
.e:
    mov al, [si]
    or al, al
    jz .eend
    cmp al, '.'
    je .no                          ; a second dot
    call fd_c83
    jc .no
    inc cx
    cmp cx, 3
    ja .no
    inc si
    jmp short .e
.eend:
    jcxz .no                        ; a trailing dot
.yes:
    pop si
    pop cx
    pop ax
    clc
    ret
.no:
    pop si
    pop cx
    pop ax
    stc
    ret

; --- fd_c83 - AL upcased; CF=1 = 8.3 may not hold it ------------------------
; dskw_char_x's set, mirrored: A-Z, 0-9 and dskw_syms. A SPACE is not in it,
; which is what `banana split.mod` fell foul of.
fd_c83:
    cmp al, 'a'
    jb .nf
    cmp al, 'z'
    ja .nf
    sub al, 32
.nf:
    cmp al, 'A'
    jb .na
    cmp al, 'Z'
    jbe .ok
.na:
    cmp al, '0'
    jb .sym
    cmp al, '9'
    jbe .ok
.sym:
    push si
    mov si, fd_syms
.sc:
    cmp byte [si], 0
    je .bad
    cmp al, [si]
    je .gs
    inc si
    jmp short .sc
.gs:
    pop si
.ok:
    clc
    ret
.bad:
    pop si
    stc
    ret

; --- fd_lastdot - SI = a NUL string -> BX = the last '.', or 0 --------------
fd_lastdot:
    push ax
    push si
    xor bx, bx
.l:
    mov al, [si]
    or al, al
    jz .out
    cmp al, '.'
    jne .n
    mov bx, si
.n:
    inc si
    jmp short .l
.out:
    pop si
    pop ax
    ret

; --- fd_lastsep - AX = non-zero if the path at [fd_pathp] holds a '/' --------
fd_lastsep:
    push si
    mov si, [fd_pathp]
    xor ax, ax
.l:
    cmp byte [si], 0
    je .out
    cmp byte [si], '/'
    jne .n
    mov ax, si
.n:
    inc si
    jmp short .l
.out:
    pop si
    ret

; --- fd_copyz - SI -> DI, NUL included, at most FD_PATHMAX -------------------
fd_copyz:
    push ax
    push cx
    mov cx, FD_PATHMAX
.c:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    or al, al
    jz .out
    loop .c
    mov byte [di-1], 0
.out:
    pop cx
    pop ax
    ret

; --- fd_bank / fd_unbank - remember where we stand, and go back --------------
fd_bank:
    push ax
    push bx
    push dx
    call OSAPI_FILE_HERE            ; DX = the cluster, BL = the drive
    mov [fd_bclus], dx
    mov [fd_bdrv], bl
    mov al, [fd_mlevel]             ; ...AND WHETHER WE WERE ABOVE EVERY VOLUME
    mov [fd_bmlevel], al            ; at all, which no file cell can answer
    mov byte [fd_banked], 1
    pop dx
    pop bx
    pop ax
    ret

fd_unbank:
    push ax
    push bx
    push dx
    cmp byte [fd_banked], 0
    je .out
    mov byte [fd_banked], 0
    mov al, [fd_bmlevel]
    mov [fd_mlevel], al
    mov dx, [fd_bclus]
    mov bl, [fd_bdrv]
    call OSAPI_FILE_GOTO
.out:
    pop dx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_goroot - stand in the SESSION's root, which is not always the volume's
;
; Three things it can be, and the session never sees above it: the folder this
; instance was launched from (the default), the folder the Setup page names, or
; - in whole-machine mode - nothing at all, because the level above every
; volume is synthetic and there is no directory to stand in (SPEC.md 77.16).
; -----------------------------------------------------------------------------
fd_goroot:
    push ax
    push bx
    push dx
    cmp byte [fd_mach], 0
    je .real
    mov byte [fd_mlevel], 1         ; the machine level: no volume is current,
    pop dx                          ; and nothing is moved
    pop bx
    pop ax
    clc
    ret
.real:
    mov byte [fd_mlevel], 0
    mov dx, [fd_rclus]
    mov bl, [fd_rdrv]
    call OSAPI_FILE_GOTO
    pop dx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_root_resolve - the configured root into (fd_rdrv, fd_rclus). UI task.
;
; **A PATH AND NEVER A CLUSTER IN THE FILE.** A cluster is meaningless once the
; disk is swapped - Cyclone's own note (SPEC.md 19.9) - so FTPD.CFG carries the
; text and this walks it once, at Start, into the pair the session then uses.
;
; `X:/A/B` or `/A/B` or `A/B`; empty means where we are, which is where the app
; was launched (SPEC.md 19.2.1). It leaves the instance standing at the root it
; resolved, which is exactly where the first client should find itself.
; -----------------------------------------------------------------------------
fd_root_resolve:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    call OSAPI_FILE_HERE            ; BANKED, because .bad has to put us back
    mov [fd_rrclus], dx             ; EXACTLY here - falling back to the
    mov [fd_rrdrv], bl              ; volume's root instead would move the
                                    ; instance out of its launch folder, and
                                    ; the next resolve would then fall back to
                                    ; somewhere further away again
    cmp byte [fd_mach], 0
    jne .here                       ; whole machine: there is no root path
    mov byte [fd_mlevel], 0         ; **AND WE ARE NO LONGER ABOVE A VOLUME.**
                                    ; Everything below stands in a real one,
                                    ; and fd_enter routes a component to a
                                    ; DRIVE while this byte is set (SPEC.md
                                    ; 77.16.2) - so turning whole-machine mode
                                    ; off and setting a root in the same visit
                                    ; to the page left the walk asking for a
                                    ; volume called `DEEP` and refusing
    mov si, fd_roots
    cmp byte [si], 0
    je .here
    ; --- a leading drive letter? ---
    mov al, [si]
    cmp byte [si+1], ':'
    jne .nodrv
    call fd_upcase
    sub al, 'A'
    jb .bad
    cmp al, FD_VOLMAX
    jae .bad
    mov bl, al
    xor dx, dx                      ; that volume's ROOT
    call OSAPI_FILE_GOTO
    jc .bad
    add si, 2
    jmp short .walk
.nodrv:
    call OSAPI_FILE_HERE            ; this volume, from its root
    xor dx, dx
    call OSAPI_FILE_GOTO
    jc .bad
.walk:
    mov al, [si]
    call fd_issep                   ; **'/' OR '\' HERE, AND ONLY HERE.** This
    jc .comp                        ; is the one path in the system a PERSON
    inc si                          ; types at the machine, and the person is
.comp:                              ; looking at a DOS box: `A:\DOCS` is what
    cmp byte [si], 0                ; they will write. An FTP path stays '/'
    je .here                        ; alone - that is the protocol's, not ours
    mov di, fd_comp
    xor cx, cx
.cc:
    mov al, [si]
    or al, al
    jz .cdone
    call fd_issep
    jnc .cdone
    cmp cx, FD_NAMEMAX - 1
    jae .skip
    mov [di], al
    inc di
    inc cx
.skip:
    inc si
    jmp short .cc
.cdone:
    mov byte [di], 0
    jcxz .walk
    push si
    mov si, fd_comp
    call fd_enter
    pop si
    jc .bad
    jmp short .walk
.here:
    call OSAPI_FILE_HERE            ; wherever we now stand IS the root
    mov [fd_rclus], dx
    mov [fd_rdrv], bl
    mov byte [fd_mlevel], 0
    cmp byte [fd_mach], 0
    je .out
    mov byte [fd_mlevel], 1
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.bad:
    ; **A ROOT THAT WILL NOT RESOLVE IS A REFUSAL, and this used to fall back**
    ; - to the folder the app was launched from, silently. That is the worst
    ; available outcome and the field reported it in one sentence: a typed
    ; `A:\` served `B:\APPS`, and nothing on screen said the setting had not
    ; taken. A server that will not start says exactly what is wrong; a server
    ; quietly handing out a DIFFERENT directory is one the user cannot even
    ; tell has gone wrong (SPEC.md 77.16.1).
    mov dx, [fd_rrclus]             ; ...and we go back where we started, so a
    mov bl, [fd_rrdrv]              ; refused Start leaves the instance exactly
    call OSAPI_FILE_GOTO            ; where it was - in a real volume, which is
    mov byte [fd_mlevel], 0         ; what that byte has to agree with
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; --- fd_issep - AL. CF=0 = it is a path separator ---------------------------
fd_issep:
    cmp al, '/'
    je .yes
    cmp al, '\'
    je .yes
    stc
    ret
.yes:
    clc
    ret

; --- fd_upcase - AL ---------------------------------------------------------
fd_upcase:
    cmp al, 'a'
    jb .out
    cmp al, 'z'
    ja .out
    sub al, 32
.out:
    ret

; -----------------------------------------------------------------------------
; fd_enter - SI = one component; step into it. out CF=1 = there is no such folder
;
; A folder's first cluster comes out of OSAPI_FILE_FIND's +16, which is what
; OSAPI_FILE_GOTO takes. '..' is a REAL ROW here (type OSAPI_FT_UP, SPEC.md
; 19.5) carrying the parent's cluster, so stepping up needs no special case -
; the walk finds it like any other entry.
; -----------------------------------------------------------------------------
fd_enter:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    cmp byte [fd_mlevel], 0         ; **ONE CHOKE POINT FOR THE MACHINE ROOT.**
    jne .vol                        ; Above every volume a component names a
                                    ; DRIVE, and putting that here rather than
                                    ; at each caller is what makes an absolute
                                    ; `/A/DOCS/X.TXT` work for RETR, STOR,
                                    ; DELE, SIZE and the rest with no line of
                                    ; code in any of them (SPEC.md 77.16.2)
    call fd_find                    ; CF=0 and fd_fbuf filled
    jc .no
    mov ax, [fd_fbuf+14]
    cmp ax, OSAPI_FT_DIR
    je .go
    cmp ax, OSAPI_FT_UP
    jne .no
.go:
    call OSAPI_FILE_HERE            ; BL = the drive it answers with...
    mov dx, [fd_fbuf+16]            ; ...and the folder's own first cluster
    call OSAPI_FILE_GOTO
    jc .no
.done:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.vol:
    call fd_volgo                   ; it moves the DIRECTORY and nothing else;
    jc .no                          ; the session's own bookkeeping is
    mov byte [fd_mlevel], 0         ; fd_entervol's, because fd_split descends
    jmp short .done                 ; temporarily and must not move it
.no:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; fd_find - SI = a name; walk the directory for it. out CF=0 and fd_fbuf filled
;
; BY ORDINAL, because OSAPI_FILE_FIND keeps no cursor in the kernel: the loop
; it exists for is find -> read -> write -> find, and every middle step walks
; directories itself, so a shared cursor would be destroyed by the very work
; it was feeding.
; -----------------------------------------------------------------------------
fd_find:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    xor cx, cx
.l:
    mov di, fd_fbuf
    call OSAPI_FILE_FIND
    jc .no                          ; FERR_NOENT: the end of the directory
    push cx
    push si
    mov di, fd_fbuf
    call fd_ieq
    pop si
    pop cx
    jnc .yes
    jmp short .l
.yes:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.no:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; --- fd_ieq - SI vs DI, case-insensitive, NUL-terminated. CF=0 = equal -------
; CASE-INSENSITIVE because a FAT name is upper case and an FTP client sends
; whatever the user typed. A case-sensitive compare here means `get readme.txt`
; failing on a disk that plainly has README.TXT on it.
fd_ieq:
    push ax
    push bx
    push si
    push di
.l:
    mov al, [si]
    mov bl, [di]
    cmp al, 'a'
    jb .u1
    cmp al, 'z'
    ja .u1
    sub al, 32
.u1:
    cmp bl, 'a'
    jb .u2
    cmp bl, 'z'
    ja .u2
    sub bl, 32
.u2:
    cmp al, bl
    jne .no
    or al, al
    jz .yes
    inc si
    inc di
    jmp short .l
.yes:
    pop di
    pop si
    pop bx
    pop ax
    clc
    ret
.no:
    pop di
    pop si
    pop bx
    pop ax
    stc
    ret

; =============================================================================
; THE FILE OPERATIONS THEMSELVES - UI task, and nowhere else
; =============================================================================

; --- fd_argpath - point fd_pathp at the right string for this request --------
; A transfer's name was banked at STOR/RETR time (fd_keepname) because the
; command buffer is reused by the next command while the upload runs; a
; one-shot's is still sitting in fd_arg.
fd_argpath:
    mov word [fd_pathp], fd_arg
    ret
fd_xferpath:
    mov word [fd_pathp], fd_xname
    ret

; -----------------------------------------------------------------------------
; fd_do_list - fill the stage with as many listing rows as fit
;
; RESUMABLE: [fd_lord] is the next ordinal to ask for, so a directory bigger
; than the stage is several passes and the worker sends each one before asking
; for the next. That is the same stage-and-commit loop a file transfer is.
; -----------------------------------------------------------------------------
fd_do_list:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov byte [fd_lmore], 0
    cmp byte [fd_mlevel], 0         ; **THE MACHINE ROOT IS ANSWERED FIRST AND
    je .dir                         ; IS NOT A DIRECTORY AT ALL** - os88net's
    call fd_list_vols               ; srv_list makes the same move for the same
    jmp .out                        ; reason: the walk below has nothing to
.dir:                               ; walk at this level (SPEC.md 77.16)
    mov di, fd_stage                ; DI is an ABSOLUTE offset in our segment
    add di, [fd_sfill]              ; and fd_sfill is relative to fd_stage
    mov cx, [fd_lord]
.l:
    push cx
    push di
    mov di, fd_fbuf
    call OSAPI_FILE_FIND            ; CX = the ordinal in, the NEXT one out
    pop di
    jc .end
    mov [fd_lord], cx
    pop cx
    ; will the row fit? A row is at most FD_ROWMAX bytes.
    mov ax, fd_stage + FD_STGSZ - FD_ROWMAX
    cmp di, ax
    jae .more
    call fd_list_row                ; appends at ES:DI
    mov cx, [fd_lord]
    jmp short .l
.end:
    pop cx                          ; the ordinal that ran off the end
    sub di, fd_stage
    mov [fd_sfill], di
    jmp short .out
.more:
    mov byte [fd_lmore], 1          ; the stage is full and the walk is not
    sub di, fd_stage                ; done: the worker will ask again
    mov [fd_sfill], di
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
; fd_list_vols - the whole-machine root: one folder row per mounted volume
;
; Named for the DRIVE LETTER os8088 shows (SPEC.md 26.4) - `A`, `B`, `C` - so
; the name a client sees is the name on the desktop. OSAPI_VOL_KIND is the
; enumerator: it answers CF=1 for a volume index that is not mounted, and it is
; the only thing a package can ask about a volume without USING it.
;
; It fits the stage in one pass by construction - six volumes at ~60 bytes a
; row against 8KB - so unlike the directory walk it is never resumable.
; -----------------------------------------------------------------------------
fd_list_vols:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov di, fd_stage
    xor bx, bx                      ; the volume index
.v:
    mov al, bl
    call OSAPI_VOL_KIND
    jc .next                        ; not mounted
    cmp byte [fd_lstyle], 0
    jne .short
    mov si, fd_ls_dir
    call fd_dcat
    mov si, fd_ls_zero
    call fd_dcat
.short:
    mov al, bl
    add al, 'A'
    mov [di], al
    inc di
    mov byte [di], 13
    inc di
    mov byte [di], 10
    inc di
.next:
    inc bx
    cmp bx, FD_VOLMAX
    jb .v
    sub di, fd_stage
    mov [fd_sfill], di
    mov word [fd_sout], 0
    mov byte [fd_lmore], 0
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_list_row - one listing line from fd_fbuf, appended at ES:DI
;
; **UNIX `ls -l` SHAPE, AND fd_c_syst SAYS WHY**: it is the format every FTP
; client can parse, and the SYST reply that names it is a statement about this
; row and not a claim about the machine.
;
; The date is FIXED. OSAPI_FILE_FIND's record carries a name, an attribute, a
; type, a first cluster and a size - and no timestamp - so inventing one from
; the clock would be a lie about the FILE rather than about the format. Every
; client shows the same date for everything, which is honest and which no
; client depends on.
; -----------------------------------------------------------------------------
fd_list_row:
    push ax
    push bx
    push cx
    push dx
    push si
    cmp byte [fd_lstyle], 0
    jne .short
    mov ax, [fd_fbuf+14]
    cmp ax, OSAPI_FT_DIR
    je .dir
    cmp ax, OSAPI_FT_UP
    je .dir
    mov si, fd_ls_file
    jmp short .pfx
.dir:
    mov si, fd_ls_dir
.pfx:
    call fd_dcat
    ; the size, right-aligned in a field of 10
    mov ax, [fd_fbuf+18]
    mov dx, [fd_fbuf+20]
    call fd_ewidth32                ; CX = how many digits it will take
    mov ax, 10
    sub ax, cx
    jbe .num
    mov cx, ax
.sp:
    mov byte [di], ' '
    inc di
    loop .sp
.num:
    mov ax, [fd_fbuf+18]
    mov dx, [fd_fbuf+20]
    call fd_dnum32
    mov si, fd_ls_date
    call fd_dcat
.short:
    mov si, fd_fbuf                 ; the display name, NUL-terminated 8.3
    call fd_dcat
    mov byte [di], 13
    inc di
    mov byte [di], 10
    inc di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- fd_ewidth32 - how many decimal digits DX:AX takes. out CX --------------
; So the size column can be right-aligned, which is what an `ls -l` parser
; expects and what makes the listing readable in the client's own window.
fd_ewidth32:
    push ax
    push bx
    push dx
    push si
    xor cx, cx
    mov bx, 10
.d:
    inc cx
    push ax
    mov ax, dx
    xor dx, dx
    div bx                          ; AX = the high quotient, DX = its remainder
    mov si, ax
    pop ax
    div bx                          ; ...which is the low half's high word
    mov dx, si                      ; DX:AX = the quotient
    mov si, dx
    or  si, ax
    jnz .d
    pop si
    pop dx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_do_rdchk - does the file exist, and how big is it?
;
; **THE CHECK IS SEPARATE FROM THE FIRST READ ON PURPOSE.** A 150 is a promise
; that bytes are coming, and some clients open their end of the data
; connection the moment they see one - so a 150 followed by a 550 leaves them
; waiting on a connection that will never carry anything. This answers 550
; before any 150 is sent.
; -----------------------------------------------------------------------------
fd_do_rdchk:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call fd_xferpath
    mov si, [fd_pathp]
    call fd_split
    jc .no
    mov si, fd_leaf
    call fd_find
    jc .no
    mov ax, [fd_fbuf+14]
    cmp ax, OSAPI_FT_DIR            ; a directory is not a file to RETR, and
    jae .no                         ; 'type < OSAPI_FT_DIR' is the SDK's own
                                    ; way of asking (type 1 is a PACKAGE, not
                                    ; "a file")
    mov ax, [fd_fbuf+18]
    mov [fd_fsize], ax
    mov ax, [fd_fbuf+20]
    mov [fd_fsize+2], ax
    call fd_unbank
    call fd_setchunk
    jc .noroom
    mov si, fd_r150
    call fd_reply
    mov byte [fd_xf], FX_RETR
    mov byte [fd_lmore], 1          ; ...so the worker's first act is FR_READ
    jmp short .out
.noroom:
    call fd_unbank
    mov si, fd_r452
    call fd_xfail
    jmp short .out
.no:
    call fd_unbank
    mov si, fd_r550
    call fd_xfail
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_do_read - one chunk of the file at [fd_foff] into the stage
;
; OSAPI_FILE_READ_AT is STATELESS - the offset is the whole argument, there is
; no handle and no cursor - which is exactly what this loop needs, because
; between two of these the worker has been out on the wire and anything at all
; may have walked a directory (SPEC.md 18.4.4).
;
; **THE OFFSET AND THE CAPACITY MUST BOTH BE CLUSTER MULTIPLES** or the slot
; answers FERR_NAME and reads nothing. fd_chunk is rounded for this volume and
; [fd_foff] only ever advances by it, so both hold by construction.
; -----------------------------------------------------------------------------
fd_do_read:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call fd_xferpath
    mov si, [fd_pathp]
    call fd_split
    jc .no
    mov si, fd_leaf
    mov bx, fd_stage                ; ES:BX - ES is ours, set by fd_wake, and a
                                    ; file slot is an N stub that keeps it
    mov cx, [fd_chunk]
    mov ax, [fd_foff]
    mov dx, [fd_foff+2]
    call OSAPI_FILE_READ_AT         ; out DX:AX = bytes delivered, 0 = the end
    jc .no
    mov [fd_sfill], ax
    mov word [fd_sout], 0
    or ax, ax
    jnz .some
    or dx, dx
    jz .done                        ; 0 delivered IS the end of the file, which
                                    ; is how this loop terminates
.some:
    add [fd_foff], ax
    adc word [fd_foff+2], 0
    mov byte [fd_lmore], 1
    cmp ax, [fd_chunk]
    je .fin                         ; a FULL chunk, so there may be more
    mov byte [fd_lmore], 0          ; a short one is the last
.fin:
    call fd_unbank
    jmp short .out
.done:
    mov byte [fd_lmore], 0
    mov word [fd_sfill], 0
    call fd_unbank
    jmp short .out
.no:
    call fd_unbank
    mov si, fd_r551
    call fd_xfail
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
; fd_do_write - commit the stage: create the file, or append to it
;
; **EVERY COMMIT BUT THE LAST IS A WHOLE NUMBER OF CLUSTERS** - the shared
; precondition of OSAPI_FILE_WRITE-then-APPEND, and the reason fd_recv_stage
; buffers to [fd_chunk] instead of writing whatever a recv happened to bring.
; The last one is whatever is left, which is the one size the rule exempts.
; -----------------------------------------------------------------------------
fd_do_write:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call fd_xferpath
    mov si, [fd_pathp]
    call fd_split
    jc .no
    mov bx, fd_stage
    mov cx, [fd_sfill]
    mov si, fd_leaf
    cmp byte [fd_created], 0
    jne .append
    xor dx, dx
    call OSAPI_FILE_WRITE           ; creates or REPLACES, which is what STOR
    jc .no                          ; means
    mov byte [fd_created], 1
    jmp short .ok
.append:
    jcxz .ok                        ; an empty tail needs no append at all -
                                    ; and APPEND's own contract wants CX >= 1
    call OSAPI_FILE_APPEND
    jc .no
.ok:
    call fd_unbank
    mov word [fd_sfill], 0
    mov word [fd_sout], 0
    cmp byte [fd_lmore], 2          ; fd_recv_stage marks the final commit, so
    jne .out                        ; the transfer ends here rather than after
    mov byte [fd_lmore], 0          ; one more empty round trip
    call fd_xdone
    jmp short .out
.no:
    push ax                         ; THE FERR, and fd_unbank must not eat it -
    call fd_unbank                  ; it is the whole difference between "your
    pop ax                          ; name is wrong" and "my disk is full"
    call fd_ferr_sel
    call fd_xfail
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- the one-shots -----------------------------------------------------------
fd_do_dele:
    push si
    call fd_argpath
    mov si, [fd_pathp]
    call fd_split
    jc .no
    mov si, fd_leaf
    call OSAPI_FILE_DELETE
    jc .no
    call fd_unbank
    mov si, fd_r250
    call fd_reply
    pop si
    ret
.no:
    call fd_unbank
    mov si, fd_r550
    call fd_reply
    pop si
    ret

; -----------------------------------------------------------------------------
; fd_do_rmd - remove an EMPTY folder (SPEC.md 18.90.2)
;
; **A NON-EMPTY FOLDER ANSWERS FERR_PROT**, from dskw_isempty, and it is worth
; its own reply because it is the one failure the user can act on. That code
; also covers a read-only, hidden or system entry - but a package cannot SEE a
; hidden or system one at all (SPEC.md 19.6.1 fences the walk), so the cause a
; client can actually reach here is a folder with something in it.
; -----------------------------------------------------------------------------
fd_do_rmd:
    push ax
    push si
    call fd_argpath
    mov si, [fd_pathp]
    call fd_split
    jc .no
    mov si, fd_leaf
    xor al, al                      ; STRICT - see fd_c_rmd
    call OSAPI_FILE_RMDIR
    jc .fail
    call fd_unbank
    mov si, fd_r250
    call fd_reply
    pop si
    pop ax
    ret
.fail:
    cmp ax, FERR_PROT
    jne .no
    call fd_unbank
    mov si, fd_r550n
    call fd_reply
    pop si
    pop ax
    ret
.no:
    call fd_unbank
    mov si, fd_r550
    call fd_reply
    pop si
    pop ax
    ret

fd_do_mkd:
    push si
    call fd_argpath
    mov si, [fd_pathp]
    call fd_split
    jc .no
    mov si, fd_leaf
    call OSAPI_FILE_MKDIR
    jc .bad
    call fd_unbank
    ; **257 CARRIES THE NAME, QUOTED**, which is PWD's format and not a
    ; decoration: RFC 959 gives MKD the same reply type, and a client parses
    ; the quoted path back out of it. ftplib's parse257 answers an empty
    ; string rather than raising when it is missing, so the omission is
    ; TOLERATED by the one client that would have caught it - which is exactly
    ; the kind of thing that ships.
    push di
    mov di, fd_outb2
    mov si, fd_r257
    call fd_dcat
    mov si, fd_leaf
    call fd_dcat
    mov si, fd_r257c
    call fd_dcat
    mov byte [di], 0
    pop di
    mov si, fd_outb2
    call fd_reply
    pop si
    ret
.bad:
    push ax                         ; MKD fails for the SAME two reasons STOR
    call fd_unbank                  ; does - a name 8.3 cannot hold, or a full
    pop ax                          ; volume - and said "no such directory" to
    call fd_ferr_sel                ; both, which is true of neither
    call fd_reply
    pop si
    ret
.no:
    call fd_unbank
    mov si, fd_r550
    call fd_reply
    pop si
    ret

; --- RNFR / RNTO -------------------------------------------------------------
; **BOTH NAMES MUST LAND IN ONE DIRECTORY**, because OSAPI_FILE_RENAME takes
; two leaf names and renames within the current one. So RNFR banks the leaf
; and RNTO does the whole job: checking a source at RNFR time and then walking
; somewhere else at RNTO time would rename a file that was never looked at.
fd_do_rnfr:
    push si
    push di
    call fd_argpath
    mov si, [fd_pathp]
    call fd_split
    jc .no
    mov si, fd_leaf
    call fd_find
    jc .no
    call fd_unbank
    mov si, fd_arg
    mov di, fd_rnfrom
    call fd_copyz
    mov byte [fd_havern], 1
    mov si, fd_r350
    call fd_reply
    pop di
    pop si
    ret
.no:
    call fd_unbank
    mov byte [fd_havern], 0
    mov si, fd_r550
    call fd_reply
    pop di
    pop si
    ret

fd_do_rnto:
    push si
    push di
    cmp byte [fd_havern], 0
    je .seq
    mov byte [fd_havern], 0
    call fd_argpath
    mov si, [fd_pathp]
    call fd_split                   ; the DESTINATION decides the directory
    jc .no
    mov si, fd_leaf
    mov di, fd_rnto_l
    call fd_copyz
    mov word [fd_pathp], fd_rnfrom
    mov si, fd_rnfrom
    call fd_leafof                  ; ...and the source contributes its leaf
    mov si, fd_leaf
    mov di, fd_rnto_l
    call OSAPI_FILE_RENAME
    jc .no
    call fd_unbank
    mov si, fd_r250
    call fd_reply
    pop di
    pop si
    ret
.no:
    call fd_unbank
    mov si, fd_r550
    call fd_reply
    pop di
    pop si
    ret
.seq:
    mov si, fd_r503
    call fd_reply
    pop di
    pop si
    ret

; --- fd_leafof - SI = a path; put its last component in fd_leaf, NO walking --
fd_leafof:
    push ax
    push si
    push di
    mov ax, si
.l:
    cmp byte [si], 0
    je .done
    cmp byte [si], '/'
    jne .n
    mov ax, si
    inc ax
.n:
    inc si
    jmp short .l
.done:
    mov si, ax
    mov di, fd_leaf
    call fd_copyz
    pop di
    pop si
    pop ax
    ret

; --- CWD ---------------------------------------------------------------------
; The path string PWD prints is maintained HERE, beside the navigation that
; changes it, rather than being derived: the kernel can say which CLUSTER we
; are standing in but there is no slot that answers "what is the path to it",
; and walking back up to build one would be a mount per component.
fd_do_cwd:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov si, fd_arg
    cmp byte [si], 0
    je .bad
    call fd_pbank                   ; **A FAILED WALK IS UNDONE.** A multi-
                                    ; component CWD that dies on its third
                                    ; component has already moved twice, and
                                    ; leaving the session standing somewhere
                                    ; the client was never told about makes
                                    ; every later bare name resolve in the
                                    ; wrong folder - silently, which is
                                    ; docs/FIELD-NOTES.md 4's whole family
    cmp byte [si], '/'
    jne .rel
    inc si
    push si
    call fd_goroot
    pop si
    jc .bad
    call fd_pathroot
    mov byte [fd_cdepth], 0         ; the root has nothing above it
.rel:
    cmp byte [si], 0
    je .ok                          ; a bare '/' is the root and nothing more
.comp:
    mov di, fd_comp
    xor cx, cx
.cc:
    mov al, [si]
    or al, al
    jz .cdone
    cmp al, '/'
    je .cdone
    cmp cx, FD_NAMEMAX - 1
    jae .skip
    mov [di], al
    inc di
    inc cx
.skip:
    inc si
    jmp short .cc
.cdone:
    mov byte [di], 0
    jcxz .next
    mov ax, [fd_comp]               ; '..' does not go through fd_enter, which
    cmp ax, '..'                    ; could never find it (FD_CDMAX's comment)
    jne .notup
    cmp byte [fd_comp+2], 0
    jne .notup
    call fd_up
    jc .bad
    jmp .rec
.notup:
    cmp byte [fd_mlevel], 0         ; AT THE MACHINE LEVEL a component names a
    je .down                        ; VOLUME and not a folder in one
    push si
    mov si, fd_comp
    call fd_entervol
    pop si
    jc .bad
    jmp .rec
.down:
    call OSAPI_FILE_HERE            ; DX = the folder we are about to LEAVE,
    mov [fd_utmp], dx               ; banked before anything moves
    push si
    mov si, fd_comp
    call fd_enter
    pop si
    jc .bad
    mov dx, [fd_utmp]
    call fd_cpush                   ; ...and recorded only now that it worked
    jc .bad
.rec:
    push si
    mov si, fd_comp
    call fd_pathpush
    pop si
.next:
    cmp byte [si], 0
    je .ok
    inc si                          ; the separator
    jmp short .comp
.ok:
    mov byte [fd_banked], 0         ; it worked, so the bank is not spent -
                                    ; CWD is the one navigation that MEANS to
                                    ; move the instance (SPEC.md 19.2.1), and
                                    ; the path and the depth stand as walked
    mov si, fd_r250c
    call fd_reply
    jmp short .out
.bad:
    call fd_punbank
    mov si, fd_r550d
    call fd_reply
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_cpush / fd_up - the parent stack, and why the kernel cannot keep it
;
; See FD_CDMAX. A package has no way to ask what is above the folder it is
; standing in, so the walk that went down has to remember. It is maintained
; HERE and not in fd_enter, because fd_enter is also how a PATHED file
; operation steps into a directory it is about to step straight back out of
; (fd_split) - and those must not move the session's idea of where it is.
; -----------------------------------------------------------------------------
fd_cpush:
    push ax
    push bx
    mov al, [fd_cdepth]
    cmp al, FD_CDMAX
    jae .full
    xor ah, ah
    shl ax, 1
    mov bx, ax
    mov [fd_cstack+bx], dx
    inc byte [fd_cdepth]
    pop bx
    pop ax
    clc
    ret
.full:
    pop bx
    pop ax
    stc
    ret

; --- fd_up - one level. CF=1 only on a real failure -------------------------
; At the root this SUCCEEDS and stays put, which is what every FTP server
; does: there is nothing above the volume, and answering 550 to a CDUP that
; simply had nowhere to go makes a client's "go to the top" loop fail.
fd_up:
    push ax
    push bx
    push dx
    cmp byte [fd_mlevel], 0
    jne .ok                         ; already above every volume
    mov al, [fd_cdepth]
    or al, al
    jnz .pop
    cmp byte [fd_mach], 0
    je .ok                          ; folder mode: the root has nothing above
    mov byte [fd_mlevel], 1         ; ...and in machine mode it has the MACHINE
    call fd_pathroot
    jmp short .ok
.pop:
    mov al, [fd_cdepth]
    dec al
    mov [fd_cdepth], al
    xor ah, ah
    shl ax, 1
    mov bx, ax
    mov dx, [fd_cstack+bx]
    mov bl, [fd_bdrv]               ; ONE VOLUME, so the drive fd_pbank banked
    call OSAPI_FILE_GOTO            ; is the drive we are standing on
    jc .no
.ok:
    pop dx
    pop bx
    pop ax
    clc
    ret
.no:
    pop dx
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; fd_entervol - SI = a drive letter; stand in that volume's root
; out: CF=1 = there is no such mounted volume
;
; The name is the LETTER os8088 shows on the desktop (SPEC.md 26.4), which is
; the volume index plus 'A' - and OSAPI_VOL_KIND is what says whether that
; index is mounted, without using it.
; -----------------------------------------------------------------------------
fd_entervol:
    call fd_volgo
    jc .no
    mov byte [fd_mlevel], 0
    mov byte [fd_cdepth], 0         ; a volume root IS the session root now, so
    clc                             ; CDUP from it goes back to the machine
    ret
.no:
    stc
    ret

; --- fd_volgo - SI = a one-letter drive name; stand in its root --------------
; **THE MOVE ONLY.** fd_mlevel, fd_cdepth and the printed path belong to the
; caller, because fd_enter reaches this on a temporary descent (fd_split) that
; must put every one of them back afterwards.
fd_volgo:
    push ax
    push bx
    push dx
    mov al, [si]
    cmp byte [si+1], 0
    jne .no                         ; more than one character is not a drive
    call fd_upcase
    sub al, 'A'
    jb .no
    cmp al, FD_VOLMAX
    jae .no
    mov bl, al
    push bx
    call OSAPI_VOL_KIND             ; AL is still the index
    pop bx
    jc .no                          ; not mounted
    xor dx, dx                      ; that volume's ROOT
    call OSAPI_FILE_GOTO
    jc .no
    pop dx
    pop bx
    pop ax
    clc
    ret
.no:
    pop dx
    pop bx
    pop ax
    stc
    ret

; --- fd_pbank / fd_punbank - the directory, the depth AND the printed path ---
; Three things move together in a CWD and all three have to come back, or a
; failed walk leaves PWD naming a folder the session is not in - which is a
; worse answer than the 550 it is reporting.
fd_pbank:
    push ax
    push cx
    push si
    push di
    call fd_bank
    mov al, [fd_cdepth]
    mov [fd_bdepth], al
    mov si, fd_path
    mov di, fd_path2
    call fd_copyz
    pop di
    pop si
    pop cx
    pop ax
    ret

fd_punbank:
    push ax
    push cx
    push si
    push di
    call fd_unbank
    mov al, [fd_bdepth]
    mov [fd_cdepth], al
    mov si, fd_path2
    mov di, fd_path
    call fd_copyz
    pop di
    pop si
    pop cx
    pop ax
    ret

; --- fd_pathroot / fd_pathpush - the printable path -------------------------
fd_pathroot:
    mov word [fd_path], '/'         ; '/' and a NUL, in one store
    ret

fd_pathpush:
    push ax
    push cx
    push si
    push di
    mov ax, [fd_comp]
    cmp ax, '..'                    ; up: strip the last component instead
    jne .down
    cmp byte [fd_comp+2], 0
    je .up
.down:
    mov di, fd_path
    xor cx, cx
.e:
    cmp byte [di], 0
    je .at
    inc di
    inc cx
    jmp short .e
.at:
    cmp cx, FD_PATHMAX - FD_NAMEMAX - 2
    jae .out                        ; too deep to record: the NAVIGATION still
                                    ; worked, and PWD stops being able to say
                                    ; where - which is better than overrunning
    cmp cx, 1
    je .sep                         ; the root already ends in '/'
    mov byte [di], '/'
    inc di
.sep:
    mov si, fd_comp                 ; SPELLED OUT: every caller happens to have
                                    ; SI here already, which is exactly the
                                    ; kind of thing that stops being true
    call fd_copyz
    jmp short .out
.up:
    mov di, fd_path
    xor cx, cx
.e2:
    cmp byte [di], 0
    je .at2
    inc di
    inc cx
    jmp short .e2
.at2:
    cmp cx, 2
    jb .out                         ; already at the root
.back:
    dec di
    cmp di, fd_path
    jbe .rootify
    cmp byte [di], '/'
    jne .back
    mov byte [di], 0
    cmp di, fd_path
    ja .out
.rootify:
    call fd_pathroot
.out:
    pop di
    pop si
    pop cx
    pop ax
    ret

; --- PWD / SIZE --------------------------------------------------------------
fd_do_pwd:
    push si
    push di
    mov di, fd_outb2
    mov si, fd_r257
    call fd_dcat
    mov si, fd_path
    cmp byte [si], 0
    jne .have
    call fd_pathroot
    mov si, fd_path
.have:
    call fd_dcat
    mov byte [di], '"'
    inc di
    mov byte [di], 0
    mov si, fd_outb2
    call fd_reply
    pop di
    pop si
    ret

fd_do_size:
    push ax
    push dx
    push si
    push di
    call fd_argpath
    mov si, [fd_pathp]
    call fd_split
    jc .no
    mov si, fd_leaf
    call fd_find
    jc .no
    cmp word [fd_fbuf+14], OSAPI_FT_DIR
    jae .no
    call fd_unbank
    mov di, fd_outb2
    mov si, fd_r213
    call fd_dcat
    mov ax, [fd_fbuf+18]
    mov dx, [fd_fbuf+20]
    call fd_dnum32
    mov byte [di], 0
    mov si, fd_outb2
    call fd_reply
    pop di
    pop si
    pop dx
    pop ax
    ret
.no:
    call fd_unbank
    mov si, fd_r550
    call fd_reply
    pop di
    pop si
    pop dx
    pop ax
    ret

; =============================================================================
; STARTING AND STOPPING
; =============================================================================

; --- fd_getaddr - our own IPv4 into fd_ip, and its dotted form into fd_ipstr -
fd_getaddr:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    call net_find
    jc .no
    mov di, fd_ip
    mov bh, NET_CLASS
    mov bl, NETV_ADDR
    call OSAPI_DRV_CALL
    jc .no
    mov di, fd_ipstr
    xor bx, bx
.q:
    mov al, [fd_ip+bx]
    xor ah, ah
    call fd_dnum
    inc bx
    cmp bx, 4
    jae .done
    mov byte [di], '.'
    inc di
    jmp short .q
.done:
    mov byte [di], 0
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.no:
    mov si, fd_s_noaddr             ; **NOT A FAILURE TO START.** A machine
    mov di, fd_ipstr                ; whose DHCP has not bound yet still serves
    call fd_copyz                   ; perfectly to a client that knows where to
    pop es                          ; find it; what it cannot do is answer PASV,
    pop di                          ; and fd_c_pasv says so at the moment it is
    pop si                          ; asked (netpkg.inc's NETV_ADDR)
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; fd_start - open the listener
; -----------------------------------------------------------------------------
fd_start:
    push ax
    push bx
    push cx
    push si
    push es
    push ds
    pop es
    call net_find                   ; WHICH DRIVER: the card's class or the
    jc .nodrv                       ; cable's, and not the RAM disk sharing the
                                    ; second (apps/os88sock.inc, SPEC.md 20.11.1)
    mov bh, NET_CLASS
    mov bl, NETV_STATE
    call OSAPI_DRV_CALL
    jc .nodrv
    test al, NSTF_SOCK
    jz .nolink
    mov cx, FTP_PORT
    mov bh, NET_CLASS
    mov bl, NETV_LISTEN
    call OSAPI_DRV_CALL
    jc .noport
    mov [fd_lhnd], al
    mov byte [fd_st], FD_LISTEN
    call fd_getaddr                 ; for the status line and for PASV. Its CF
                                    ; is deliberately ignored: no address is a
                                    ; thing to SAY, not a reason to refuse
    call fd_root_resolve            ; THE ROOT IS WALKED ONCE, HERE - a path in
                                    ; the file, a (drive, cluster) for the
                                    ; session (SPEC.md 77.16.1)
    jc .badroot                     ; ...and a root that will not walk STOPS
                                    ; the server. The listener is already open
                                    ; at this point, so it has to be shut
    call fd_pathroot
    mov si, fd_l_listen
    call fd_log
    mov si, fd_l_prange             ; the range a passive transfer will use,
    call fd_log                     ; said ONCE and before anything needs it -
                                    ; forwarding port 21 alone is the single
                                    ; commonest way to make PASV unreachable
    call fd_hire
    jmp short .out
.badroot:
    mov al, [fd_lhnd]               ; the port is open and nothing is going to
    mov bh, NET_CLASS               ; serve on it, so it goes back rather than
    mov bl, NETV_CLOSE              ; being held for the session
    call OSAPI_DRV_CALL
    mov byte [fd_lhnd], 0
    mov si, fd_e_root
    jmp short .fail
.nodrv:
    mov si, fd_e_nodrv
    jmp short .fail
.nolink:
    mov si, fd_e_nolink
    jmp short .fail
.noport:
    mov si, fd_e_noport
.fail:
    mov [fd_msg], si
    mov byte [fd_st], FD_ERR
.out:
    or byte [fd_dirty], FDD_BTN | FDD_STAT
    pop es
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_onclose - W_ONCLOSE: the settings' last chance to reach the disk
;
; **MARK ON CLICK, WRITE ON CLOSE** is SPEC.md 31.8's rule for the Control
; Panel and this is the same trade: a FTPD.CFG write is a mount, a data
; sector, a FAT sector, a directory sector and a remount, which on the machine
; this is for is seconds of frozen UI - unaffordable on the click of a check
; box and entirely affordable once, on the way out.
;
; It NEVER refuses. There is nothing here a user could lose by closing the
; window - the log is a log and a transfer in flight is the client's problem,
; not a document - so an alert would be a question with no wrong answer.
; -----------------------------------------------------------------------------
fd_onclose:
    cmp byte [fd_cdirty], 0
    je .out                         ; nothing changed, so no floppy is touched
    call fd_cfg_save
.out:
    clc                             ; ...and the close happens either way
    ret

; --- fd_bye - the client has gone; go back to listening ----------------------
fd_bye:
    push ax
    push bx
    push si
    call fd_data_drop
    call fd_reset_xfer
    cmp byte [fd_chnd], 0
    je .n
    mov al, [fd_chnd]
    mov bh, NET_CLASS
    mov bl, NETV_CLOSE
    call OSAPI_DRV_CALL
    mov byte [fd_chnd], 0
.n:
    mov byte [fd_auth], 0
    mov word [fd_clen], 0
    mov byte [fd_havern], 0
    cmp byte [fd_st], FD_CTRL
    jne .done
    mov byte [fd_st], FD_LISTEN     ; **THE LISTENER OUTLIVES THE CONNECTION**,
                                    ; which is what NETV_ACCEPT being separate
                                    ; from NETV_LISTEN is for (netpkg.inc)
.done:
    mov si, fd_l_bye
    call fd_log
    pop si
    pop bx
    pop ax
    ret

; --- fd_shutdown - stop serving entirely -------------------------------------
fd_shutdown:
    push ax
    push bx
    push si
    call fd_data_drop
    call fd_reset_xfer
    cmp byte [fd_chnd], 0
    je .l
    mov al, [fd_chnd]
    mov bh, NET_CLASS
    mov bl, NETV_CLOSE
    call OSAPI_DRV_CALL
    mov byte [fd_chnd], 0
.l:
    cmp byte [fd_lhnd], 0
    je .done
    mov al, [fd_lhnd]
    mov bh, NET_CLASS
    mov bl, NETV_CLOSE
    call OSAPI_DRV_CALL
    mov byte [fd_lhnd], 0
.done:
    mov byte [fd_auth], 0
    mov word [fd_clen], 0
    mov byte [fd_req], FR_NONE
    or byte [fd_dirty], FDD_BTN | FDD_STAT
    pop si
    pop bx
    pop ax
    ret

fd_stop:
    call fd_shutdown
    mov byte [fd_st], FD_OFF
    push si
    mov si, fd_l_stop
    call fd_log
    pop si
    ret

; =============================================================================
; INPUT
; =============================================================================

; --- fd_onclick - W_ONCLICK: SI = window, CX = x, DX = y, lock held ----------
; -----------------------------------------------------------------------------
; fd_onclick - W_ONCLICK: the PRESS. It arms and it draws; it does not act
; in:  CX = x, DX = y (screen), SI = window; UI task, gfx lock held
; out: nothing; preserves all registers
;
; Three things happen on a press and none of them is the command: the credits
; come down if they are up, a field takes the caret if one was hit, and
; otherwise the control under the pointer is armed and drawn pressed. What it
; DOES waits for fd_onup.
; -----------------------------------------------------------------------------
fd_onclick:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call fd_layout
    cmp byte [fd_page], FP_ABOUT
    jne .nab
    mov byte [fd_page], FP_LOG      ; any press dismisses the credits, and it
    or byte [fd_dirty], FDD_PAGE    ; is SPENT doing that - nothing is armed,
    call fd_spend                   ; so the release that follows fires
    jmp short .out                  ; nothing (Calculator's cal_abdismiss)
.nab:
    cmp byte [fd_page], FP_SETUP
    jne .find
    call fd_setup_rects             ; the fields' rects and the two ticks,
    call fd_setup_press             ; DERIVED; then the fields, which keep the
    jnc .out                        ; press (SPEC.md 13.8.8)
.find:
    call fd_ctlfind                 ; AX = the control under the pointer
    call os88ui_arm
    mov [fd_dnb], ax                ; ...and SEED the drag's comparand with it,
                                    ; so the first delivery after a press that
                                    ; has not moved off compares equal and
                                    ; draws nothing
    call fd_setdown                 ; ...and the pressed look, through the one
.out:                               ; writer - 0 is a legal argument, so a
    pop di                          ; press that lands on nothing needs no test
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret                             ; near: dispatched (SPEC.md 20.5)

; -----------------------------------------------------------------------------
; fd_ondrag - W_ONDRAG (SPEC.md 13.8.2): the pointer moved, the press is live
; in:  CX = x, DX = y (screen, and possibly outside the window), SI = window
; out: nothing; preserves all registers
;
; THE PRESSED CONTROL FOLLOWS THE POINTER: down while it is over the control
; the press landed on, up the moment it is not, down again on the way back.
; That is what says the gesture is CANCELLED before the user commits to it,
; and it is the same two calls fd_onup makes at the release, one pass early,
; so what is lit is exactly what would fire.
;
; os88ui_armed and not os88ui_fire: the arm has to survive this and still be
; there for the release. Spending it here would leave the release with
; nothing armed and no control in this window would ever act.
; -----------------------------------------------------------------------------
fd_ondrag:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call os88ui_armed               ; AX = what the press armed, still armed
    or ax, ax
    jz .out                         ; the press landed on nothing - or on a
    mov di, ax                      ; field, which arms nothing: no repaint
    call fd_layout                  ; the window can have been dragged since
    cmp byte [fd_page], FP_SETUP    ; the press, so the rects are recomputed
    jne .find                       ; rather than trusted
    call fd_setup_rects
.find:
    call fd_ctlfind                 ; AX = what is under the pointer NOW
    cmp ax, [fd_dnb]
    je .out                         ; ...and it has not moved between controls
    mov [fd_dnb], ax                ; since the last delivery: nothing owed
    cmp ax, di
    je .set                         ; back on it (or never left)
    xor ax, ax                      ; off it: nothing down
.set:
    call fd_setdown                 ; ...which draws only if that CHANGED
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret                             ; near: dispatched (SPEC.md 20.5)

; -----------------------------------------------------------------------------
; fd_onup - W_ONMOUSEUP (SPEC.md 13.7): the control FIRES here
; in:  CX = x, DX = y (screen, and possibly outside the window), SI = window
; out: nothing; preserves all registers
;
; The armed control is put back up FIRST and unconditionally, before anything
; decides whether the gesture fired, because every other way out of this
; routine is a jmp to .out and a control left down is left down for the rest
; of the session (SPEC.md 13.8.2's second consequence).
; -----------------------------------------------------------------------------
fd_onup:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call fd_layout
    cmp byte [fd_page], FP_SETUP
    jne .fire
    call fd_setup_rects
.fire:
    call os88ui_fire                ; AX = what the press armed, and it is
    mov word [fd_dnb], 0            ; CLEARED - one release per press
    or ax, ax
    jz .out
    mov di, ax
    push ax
    xor ax, ax
    call fd_setdown                 ; ...upright again, FIRST and whatever
    pop ax                          ; happens next
    push di
    call fd_ctlfind                 ; AX = the control under the RELEASE
    pop di
    cmp ax, di
    jne .out                        ; a different one, or none: cancelled
    cmp byte [fd_page], FP_SETUP
    je .setup
    ; --- the LOG page ------------------------------------------------------
    cmp ax, FD_R_MAIN
    je .startstop
    cmp ax, FD_R_C1
    je .ro
    call fd_setup_toggle            ; Setup: into the page
    jmp short .paint
.startstop:
    cmp byte [fd_st], FD_OFF
    je .go
    cmp byte [fd_st], FD_ERR        ; an error is a state to RETRY out of, not
    je .go                          ; a dead end (SPEC.md 48.5)
    call fd_stop
    jmp short .paint
.go:
    call fd_start
    jmp short .paint
.ro:
    xor byte [fd_ro], 1
    mov byte [fd_cdirty], 1         ; MARKED, not written (SPEC.md 77.17.1)
    or byte [fd_dirty], FDD_RO      ; ONE 12px box
    jmp short .paint
    ; --- the SETUP page ----------------------------------------------------
.setup:
    cmp ax, FD_R_MAIN
    je .done
    cmp ax, FD_R_C1
    je .rtick
    xor byte [fd_mach], 1
    jmp short .tick
.rtick:
    xor byte [fd_ro], 1
.tick:
    mov byte [fd_cdirty], 1
    call fd_setup_defoc
    or byte [fd_dirty], FDD_PAGE
    jmp short .paint
.done:
    call fd_setup_toggle
.paint:
    call fd_layout
    call fd_spend
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret                             ; near: dispatched (SPEC.md 20.5)

; =============================================================================
; THE PRESS/DRAG/RELEASE GESTURE (SPEC.md 13.7, 13.8.2, 77.18)
;
; Every control in this window is a STANDARD one now: os88ui_btn and
; os88ui_glyph draw it, os88ui_bfind finds it, os88ui_arm/armed/fire carry the
; press across the three edges, and it FIRES ON THE RELEASE over the control
; the press landed on. That is SPEC.md 13.6's rule - a control with no safe
; prefix action wants the release - and none of these has one: starting a
; server, writing a setting and changing pages are all things a mis-aimed
; press should be able to slide off.
;
; The four Setup FIELDS are the exception and keep the press, because
; focusing a field is selecting and SPEC.md 13.8.8 keeps the press for
; exactly that. They are not in either rect table.
;
; W_ONDRAG is kern_big's alone and answers CF = 1 on the 128KB kernel
; (SPEC.md 13.8.2). NOTHING here tests that carry, and that is deliberate:
; with no drag edge the control still goes down on the press and up on the
; release, which is the static down state that section asks a package to fall
; back to. The half that is lost is the slide-off preview, and losing it
; costs correctness nothing - the release still re-finds the control and
; still refuses to fire if the pointer has moved off it.
; =============================================================================

FD_R_MAIN   equ 1                   ; bfind's answers are index PLUS ONE, so
FD_R_C1     equ 2                   ; these are the answers themselves and not
FD_R_C2     equ 3                   ; the indices - there is no dec anywhere
FD_NR       equ 3

; -----------------------------------------------------------------------------
; fd_rtab - the rect table for the page that is up
; out: BX = the table, AX = FD_NR; preserves everything else
;
; The page cannot change mid-gesture: only a release on Setup/Done or a menu
; item moves it, and neither can happen between a press and its release - the
; kernel owns the pointer for the whole of a menu tracking pass (SPEC.md
; 12.4). So the press, the drags and the release all read the same table.
; -----------------------------------------------------------------------------
fd_rtab:
    mov bx, fd_rects
    cmp byte [fd_page], FP_SETUP
    jne .l
    mov bx, fd_srects
.l:
    mov ax, FD_NR
    ret

; -----------------------------------------------------------------------------
; fd_ctlfind - which control is the SCREEN point CX,DX in?
; in:  CX = x, DX = y (screen); out: AX = FD_R_* or 0; preserves everything else
; -----------------------------------------------------------------------------
fd_ctlfind:
    push bx
    call fd_rtab
    call os88ui_bfind
    pop bx
    ret

; -----------------------------------------------------------------------------
; fd_setdown - THE ONE WRITER OF [fd_down], and the only thing that draws it
; in:  AX = the control to draw pressed (FD_R_* or 0 for none)
; out: nothing; preserves all registers
;
; It redraws the control that was down and the one that is now down, one
; call each, and IT RETURNS HAVING DRAWN NOTHING IF THE ANSWER DID NOT
; CHANGE. That early-out is not an optimisation here: W_ONDRAG is delivered
; once per pointer movement, so a handler that repainted every time would
; spend two os88ui_btn calls - PERFORMANCE.md Part 2's 756us apiece, plus the
; caption - on every mouse packet, which is the flicker the down state exists
; to avoid arriving through the other door.
;
; Because [fd_down] is what the painters read, a W_PAINT landing mid-gesture
; draws the pressed control pressed, and the release then puts it up rather
; than "back" to a state it was never in (SPEC.md 13.8.2).
; -----------------------------------------------------------------------------
fd_setdown:
    push ax
    push bx
    cmp ax, [fd_down]
    je .out
    mov bx, ax                      ; BX = the new one
    xchg ax, [fd_down]              ; AX = the OLD one, and the variable is
    call fd_drawctl                 ; already right for both of these draws
    mov ax, bx
    call fd_drawctl
.out:
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; fd_drawctl - draw ONE control in its current state. AX = FD_R_*, 0 = nothing
; in:  the layout is current and the gfx lock is held
; out: nothing; preserves all registers
;
; Six controls over two pages, and every one of them is drawn by the same
; routine that draws it in a full repaint - there is no second painter that
; could disagree with the first about what a pressed Start looks like.
; -----------------------------------------------------------------------------
fd_drawctl:
    push ax
    or ax, ax
    jz .out
    cmp byte [fd_page], FP_SETUP
    je .setup
    cmp ax, FD_R_MAIN
    je .btn
    cmp ax, FD_R_C1
    je .ro
    call fd_draw_setb
    jmp short .out
.btn:
    call fd_draw_btn
    jmp short .out
.ro:
    call fd_draw_ro
    jmp short .out
.setup:
    cmp ax, FD_R_MAIN
    je .done
    cmp ax, FD_R_C1
    je .rchk
    call fd_draw_mchk
    jmp short .out
.done:
    call fd_draw_done
    jmp short .out
.rchk:
    call fd_draw_rchk
.out:
    pop ax
    ret

.no:
    pop ax
    stc
    ret

; --- fd_onkey - W_ONKEY: AL = ASCII, AH = scan -------------------------------
; --- fd_onkey - W_ONKEY: AL = ASCII, AH = scan. Lock held ------------------
; The LOG face takes no typed text at all - it is two controls and a list - so
; this is the Setup field's and nothing else's.
fd_onkey:
    push si
    cmp byte [fd_page], FP_SETUP
    jne .out
    call fd_setup_key               ; ...which does nothing unless a field has
.out:                               ; been CLICKED: a stray keystroke must not
    pop si                          ; edit a setting the user is not looking at
    ret

; --- fd_oncmd - AL = the menu cell, AH = the item ----------------------------
fd_oncmd:
    push si
    or ah, ah                       ; **AL IS THE ITEM AND AH IS THE MENU**, and
    jnz .out                        ; this had them the other way round - which
                                    ; is the THIRD time in this tree: telnet's
                                    ; te_oncmd carries the same note and the
                                    ; browser's Go menu had it at the same place
                                    ; (SPEC.md 71.8).
                                    ;
                                    ; It fails in the way that survives review:
                                    ; there is exactly one menu here, so the
                                    ; menu index is always 0 - the FIRST item
                                    ; worked perfectly and every other one was
                                    ; unreachable, which reads as "the new item
                                    ; does nothing" rather than as a swapped
                                    ; pair.
    or al, al
    jne .clr
    cmp byte [fd_st], FD_OFF
    je .start
    call fd_stop
    jmp short .paint
.start:
    call fd_start
    jmp short .paint
.clr:
    cmp al, 1
    jne .setup
    call fd_logclear
    jmp short .paint
.setup:
    cmp al, 2
    jne .out
    call fd_setup_toggle
.paint:
    mov si, [fd_win]
    call fd_layout
    call fd_spend
.out:
    pop si
    ret

fd_logclear:
    push ax
    push cx
    push di
    mov di, fd_log_b
    mov cx, FD_LOGSZ
    xor al, al
.c:
    mov [di], al
    inc di
    loop .c
    mov byte [fd_lognext], 0
    pop di
    pop cx
    pop ax
    ret

; =============================================================================
; THE SETUP PAGE, AND FTPD.CFG (SPEC.md 77.12)
;
; **IT IS A PAGE OF THE MAIN WINDOW AND NOT A SECOND WINDOW**, and that is a
; decision about what comes next rather than about what is here now. A package
; may have more than one window, but `fdlg_open` fences on `inst_win_owner`:
; the window it is handed must belong to a live instance, and a package's
; SECOND window is deliberately unbound, so its close box reduces to wm_hide
; (SPEC.md 56 is the worked example - ModPlug's PlayList has to pass the
; PLAYER's window to open a file dialog at all). The settings that are coming -
; a root folder to serve - want a folder PICKER, so the page that hosts them
; has to be in the bound window. Doing it now costs nothing; discovering it
; later costs the window.
; =============================================================================
FD_IPMAX    equ 16                  ; '255.255.255.255' and its NUL
FD_ROOTMAX  equ 48                  ; a served-root path and its NUL
FD_USERMAX  equ 17                  ; a user or a password and its NUL
FD_SETX     equ FD_TEXTX            ; the labels' inset - ALIGNED, like every
                                    ; other pen on this window
FD_SETY     equ 22                  ; the first row's top - BELOW the Done
                                    ; button, which sits at FD_PAD and is
                                    ; FD_BTNH tall, so 4+14 = 18 is the floor
FD_SROW     equ 16                  ; ...and the pitch. LABEL AND FIELD SHARE A
                                    ; ROW rather than stacking, because the
                                    ; content box on CGA is ~117 rows once
                                    ; wm_fit has clamped the window (SPEC.md
                                    ; 39.7) and four stacked pairs do not fit
FD_FLDX     equ 112                 ; where the fields start, 8-aligned
FD_FLDW     equ 160
FD_FN       equ 4                   ; how many text fields there are
FD_VOLMAX   equ 8                   ; DVOL_MAX, mirrored - the volume table's
                                    ; size, so A: to H:. IT SAID 6, and the
                                    ; comment claiming to mirror DVOL_MAX was
                                    ; simply wrong: G: and H: were refused by
                                    ; a drive-letter root and skipped by
                                    ; whole-machine mode, silently, on the
                                    ; only machines that can have them (four
                                    ; primaries plus floppies, SPEC.md 52.2).
                                    ; The REAL fence is OSAPI_VOL_KIND's carry
                                    ; and every walk here tests it; this only
                                    ; bounds the loop, which is why being
                                    ; wrong cost nothing visible until now

; --- the Setup page's fields, as a TABLE -------------------------------------
; They are homogeneous - four one-line text boxes - so a table is the honest
; shape here where it was not for one field (the note that said so is gone with
; the guess it was warning about). The CHECK BOX is not in it, because it is
; not a text box and forcing it in would be the shape guessed again.
FDF_LBL     equ 0                   ; word: -> the label
FDF_BUF     equ 2                   ; word: -> the buffer, in our segment
FDF_MAX     equ 4                   ; word: its capacity, NUL included
FDF_SZ      equ 6

; --- fd_setup_toggle - in and out of the page, saving on the way out --------
; **THE SAVE IS ON LEAVING, NOT ON EVERY KEYSTROKE.** SPEC.md 31.8's rule for
; the Control Panel, and for its reason: a write here is a mount, a data
; sector, a FAT sector, a directory sector and a remount, which on the machine
; this is for is seconds of frozen UI - landing in the middle of typing an
; address, once per character.
;
; Three callers and they are three CONTROLS, not three code paths: the toolbar
; Setup button on the way in, the Done button on the way out, and the menu
; item either way (SPEC.md 77.17). The two buttons are in different corners
; deliberately - Done sits where Start does, because that corner is the
; primary action of whichever page is up - and the harness found the cost of
; getting that wrong the expensive way: clicking the way-IN button to come
; back out lands on empty desktop, the page never leaves, and since leaving is
; what COMMITS, the setting is typed, visible on screen, and never saved.
fd_setup_toggle:
    push si
    cmp byte [fd_page], FP_SETUP
    je .leave
    call fd_line_init
    mov byte [fd_page], FP_SETUP
    jmp short .out
.leave:
    call fd_setup_commit
    mov byte [fd_page], FP_LOG
.out:
    or byte [fd_dirty], FDD_PAGE    ; the face is a different face now
    mov byte [fd_pfoc], 0
    pop si
    ret

; --- fd_line_init - point each editor at its own buffer ---------------------
; **THE BLOCK'S BUFFER WORDS ARE NOT OPTIONAL**: bss arrives zeroed (SPEC.md
; 21 step 5), so an unset LN_BUF points at offset 0 - this package's own
; header - and the first keystroke writes into it. Telnet's te_entry carries
; the same note for the same reason.
fd_line_init:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    xor bx, bx                      ; the field index
.f:
    call fd_fblock                  ; SI = its line block, DI = its table row
    mov ax, [di+FDF_BUF]
    mov [si + LN_BUF], ax
    mov cx, [di+FDF_MAX]
    mov [si + LN_MAX], cx
    mov di, ax
    call os88line_set               ; LN_LEN/LN_CAR/LN_VIEW from the text
    inc bx
    cmp bx, FD_FN
    jb .f
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- fd_fblock - in BX = a field index; out SI = its block, DI = its row ------
fd_fblock:
    push ax
    push dx
    mov ax, OS88LINE_SZ
    mul bx
    add ax, fd_lines
    mov si, ax
    mov ax, FDF_SZ
    mul bx
    add ax, fd_ftab
    mov di, ax
    pop dx
    pop ax
    ret

; --- fd_setup_commit - parse what was typed, keep it, write it out ----------
; A field that will not parse is REFUSED and the old value stands, because the
; alternative - storing 0.0.0.0 and carrying on - is a server that answers
; PASV with an address telling the client to connect to itself.
fd_setup_commit:
    push ax
    push si
    push di
    ; --- the PASV address, which is the one field that PARSES ---------------
    mov si, fd_pasvs
    cmp byte [si], 0
    jne .parse
    xor ax, ax                      ; an EMPTY field clears the override, which
    mov [fd_pasv+0], ax             ; is how a user goes back to "use my own
    mov [fd_pasv+2], ax             ; address" without knowing what it is
    jmp short .save
.parse:
    mov di, fd_pasv
    call fd_parseip
    jnc .save
    call fd_pasv_str                ; refused: the old address goes back on
    jmp short .out                  ; screen and NOTHING is saved, so a typo
                                    ; cannot quietly take the rest with it
.save:
    ; the other three are strings and are already in their buffers, edited in
    ; place by os88line - there is nothing to parse and nothing to validate
    call fd_cfg_save
    mov byte [fd_cdirty], 0         ; spent: the close has nothing left to write
    cmp byte [fd_st], FD_CTRL       ; **NOT WHILE A CLIENT IS CONNECTED.** The
    je .nore                        ; root is where that session is standing,
    call fd_root_resolve            ; and re-walking it underneath them would
                                    ; move a client that asked for nothing.
                                    ; ITS CF IS DROPPED ON PURPOSE: a root
                                    ; that will not walk is a refusal to
                                    ; START, said on the status line at the
                                    ; moment it matters, and a page that
                                    ; erased the typing on the way out would
                                    ; teach nothing and lose the setting
.nore:
                                    ; Idle or stopped, the new setting is live
                                    ; at once rather than at the next Start
    call fd_pasv_str
.out:
    pop di
    pop si
    pop ax
    ret

; --- fd_parseip - SI = dotted quad -> DI = four bytes. CF=1 = it is not one --
fd_parseip:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    xor cx, cx                      ; fields taken
.f:
    xor bx, bx
    mov byte [fd_tmpb], 0
.d:
    mov al, [si]
    cmp al, '0'
    jb .fend
    cmp al, '9'
    ja .fend
    inc si
    sub al, '0'
    xor ah, ah
    push ax
    mov ax, bx
    mov bx, 10
    mul bx
    mov bx, ax
    pop ax
    add bx, ax
    mov byte [fd_tmpb], 1
    cmp bx, 255
    ja .no                          ; not a byte, so not a quad
    jmp short .d
.fend:
    cmp byte [fd_tmpb], 0
    je .no                          ; an empty field
    mov [di], bl
    inc di
    inc cx
    mov al, [si]
    or al, al
    jz .end
    cmp al, '.'
    jne .no
    inc si
    cmp cx, 4
    jae .no                         ; a fifth field
    jmp short .f
.end:
    cmp cx, 4
    jne .no
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.no:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; --- fd_pasv_str - render [fd_pasv] into the field, or empty when it is unset
fd_pasv_str:
    push ax
    push bx
    push di
    mov di, fd_pasvs
    mov ax, [fd_pasv]
    or ax, [fd_pasv+2]
    jz .none
    xor bx, bx
.q:
    mov al, [fd_pasv+bx]
    xor ah, ah
    call fd_dnum
    inc bx
    cmp bx, 4
    jae .done
    mov byte [di], '.'
    inc di
    jmp short .q
.done:
    mov byte [di], 0
    call fd_line_init
    pop di
    pop bx
    pop ax
    ret
.none:
    mov byte [di], 0
    call fd_line_init
    pop di
    pop bx
    pop ax
    ret

; --- fd_setup_click - CX,DX are the click. Lock held ------------------------
; -----------------------------------------------------------------------------
; fd_setup_press - the Setup page's PRESS half: the four fields, and only them
; in:  CX = x, DX = y (screen); the rects are current
; out: CF = 0 = a field took the press and nothing else may look at it
;      CF = 1 = it was not on a field; preserves all registers
;
; THE FIELDS KEEP THE PRESS and the three buttons do not. SPEC.md 13.8.8's
; test is about the control and not the app: putting the caret in a field is
; SELECTING, which that table keeps the press for, and a caret that waited
; for the release would feel late under a drag-select. The three that FIRE -
; Done and the two ticks - have no safe prefix action and take the release,
; through the rect table.
;
; A press on the page background is still a defocus, and it still returns
; CF = 1, so the release path sees "no control" and does nothing.
; -----------------------------------------------------------------------------
fd_setup_press:
    push ax
    push bx
    push si
    xor bx, bx
.f:
    call fd_fblock
    call os88line_click             ; CF=0 = it landed in THIS field
    jnc .got
    inc bx
    cmp bx, FD_FN
    jb .f
    call fd_ctlfind                 ; not a field: a tick or Done takes the
    or ax, ax                       ; release, and anything else is a press on
    jnz .no                         ; the background, which takes the caret
    cmp byte [fd_pfoc], 0           ; away - but only if something HAD it, or
    je .no                          ; every stray press repaints the page
    call fd_setup_defoc
    or byte [fd_dirty], FDD_PAGE
    call fd_spend
.no:
    pop si
    pop bx
    pop ax
    stc
    ret
.got:
    call fd_setup_defoc
    mov al, bl
    inc al                          ; 0 means NO field, so the index is +1
    mov [fd_pfoc], al
    call fd_fblock
    mov byte [si + LN_FOCUS], 1
    or byte [fd_dirty], FDD_PAGE
    call fd_spend
    pop si
    pop bx
    pop ax
    clc
    ret

; --- fd_setup_rects - every Setup rect, from the live content box ------------
fd_setup_rects:
    push ax
    push bx
    push si
    mov si, fd_btn                  ; Done stands exactly where Start does -
    mov bx, fd_done                 ; the same corner is the primary action of
    mov ax, [si]                    ; whichever page is up - but it gets its
    mov [bx], ax                    ; OWN four words, because a table shared
    mov ax, [si+2]                  ; between the pages would be a stale rect
    mov [bx+2], ax                  ; waiting for an ordering change
    mov ax, [si+4]
    mov [bx+4], ax
    mov ax, [si+6]
    mov [bx+6], ax
    pop si
    xor bx, bx
.f:
    call fd_field_rect
    inc bx
    cmp bx, FD_FN
    jb .f
    call fd_box_rects
    pop bx
    pop ax
    ret

; --- fd_setup_defoc - take the caret off whichever field has it -------------
fd_setup_defoc:
    push bx
    push si
    push di
    xor bx, bx
.f:
    call fd_fblock
    mov byte [si + LN_FOCUS], 0
    inc bx
    cmp bx, FD_FN
    jb .f
    mov byte [fd_pfoc], 0
    pop di
    pop si
    pop bx
    ret

; --- fd_setup_key - AL/AH from W_ONKEY. CF=0 = the field took it -------------
fd_setup_key:
    push bx
    push si
    push di
    mov bl, [fd_pfoc]
    or bl, bl
    jz .no                          ; nothing has the caret
    dec bl
    xor bh, bh
    call fd_fblock
    call os88line_key
    jc .no
    call fd_fblock
    call os88line_draw
    pop di
    pop si
    pop bx
    clc
    ret
.no:
    pop di
    pop si
    pop bx
    stc
    ret

; -----------------------------------------------------------------------------
; fd_draw_setup - the page. Lock held, fd_layout already run
;
; Every rect is derived from the LIVE content box on every paint, never stored:
; a window can be resized, moved across an extended desktop's seam or find
; itself on an adapter of a different size (SPEC.md 39.7/11.98), and a control
; drawn from a remembered rect is one the hit-test cannot find.
; -----------------------------------------------------------------------------
fd_draw_setup:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call fd_clear_content
    ; --- the way OUT, in the same corner the way IN was clicked from --------
    push di
    call fd_setup_rects             ; Done's rect and the ticks', DERIVED from
    call fd_draw_done               ; the live box before anything draws
    pop di
    mov cx, [fd_ox]
    add cx, FD_PAD + FD_BTNW + 8
    mov dx, [fd_oy]
    add dx, FD_PAD + 3
    mov si, fd_s_sethd
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    xor bx, bx                      ; (the rects were derived above, with
                                    ; Done's - one call for the whole page)
.f:
    call fd_fblock
    push bx
    mov cx, [fd_ox]
    add cx, FD_SETX
    mov dx, [si + LN_Y1]
    add dx, 3
    mov si, [di+FDF_LBL]
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    pop bx
    call fd_fblock
    call os88line_draw
    inc bx
    cmp bx, FD_FN
    jb .f
    ; --- the two check boxes, which are not fields --------------------------
    mov bx, fd_rchk
    mov si, fd_s_ro
    mov al, [fd_ro]
    call fd_setup_box
    mov bx, fd_mchk
    mov si, fd_s_mach
    mov al, [fd_mach]
    call fd_setup_box
    mov cx, [fd_ox]
    add cx, FD_SETX
    mov dx, [fd_mchk+2]
    add dx, 18
    mov si, fd_s_sethelp
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- fd_setup_box - BX = a rect, SI = its label, AL = its state -------------
fd_setup_box:
    push ax
    push cx
    push dx
    push si
    push di
    mov cx, [bx]                    ; the glyph takes a TOP-LEFT, not a rect -
    mov dx, [bx+2]                  ; the rect is kept for the hit-test alone
    or al, al                       ; the STATE, tested here...
    mov al, OS88UI_GCHECK           ; ...and `mov` does not touch the flags, so
    jz .nz                          ; this still branches on it
    or al, OS88UI_GON
.nz:
    ; --- and the PRESSED look, from WHICH RECT this is ----------------------
    ; The caller passes the rect and not the control's number: there are
    ; exactly two boxes on this page and the rect already names them, so a
    ; second argument would be a second thing to keep in step for nothing.
    push cx
    mov cx, FD_R_C1
    cmp bx, fd_rchk
    je .which
    mov cx, FD_R_C2
.which:
    cmp cx, [fd_down]
    pop cx
    jne .nd
    or al, OS88UI_GDOWN
.nd:
    xor ah, ah
    push bx
    call os88ui_glyph
    pop bx
    mov cx, [bx+4]
    add cx, 6
    mov dx, [bx+2]
    add dx, 2
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret

; --- fd_field_rect - fill field BX's block with its rect --------------------
fd_field_rect:
    push ax
    push bx
    push dx
    push si
    push di
    call fd_fblock
    push si
    mov ax, FD_SROW
    mul bx
    add ax, FD_SETY
    add ax, [fd_oy]
    pop si
    mov [si + LN_Y1], ax
    add ax, 13
    mov [si + LN_Y2], ax
    mov ax, [fd_ox]
    add ax, FD_FLDX
    mov [si + LN_X1], ax
    add ax, FD_FLDW
    mov [si + LN_X2], ax
    pop di
    pop si
    pop dx
    pop bx
    pop ax
    ret

; --- fd_box_rects - the two check boxes, stacked under the fields -----------
fd_box_rects:
    push ax
    push bx
    push cx
    mov bx, fd_rchk
    xor cx, cx
    call fd_box_rect
    mov bx, fd_mchk
    mov cx, 1
    call fd_box_rect
    pop cx
    pop bx
    pop ax
    ret

; --- fd_box_rect - BX = the rect, CX = which row under the fields ------------
fd_box_rect:
    push ax
    push dx
    mov ax, [fd_ox]
    add ax, FD_SETX
    mov [bx], ax
    add ax, OS88UI_GW - 1
    mov [bx+4], ax
    mov ax, FD_SROW
    mul cx
    add ax, [fd_oy]
    add ax, FD_SETY + FD_FN * FD_SROW + 4
    mov [bx+2], ax
    add ax, OS88UI_GW - 1
    mov [bx+6], ax
    pop dx
    pop ax
    ret

; =============================================================================
; FTPD.CFG - SYSTEM/APPDATA, and a format built to GROW (SPEC.md 77.12.1)
;
; **A KEYED FILE AND NOT A STRUCT**, because the settings that are coming - a
; root folder to serve, a single user and password - are not known yet and a
; fixed layout would have to be versioned for each of them. Every record is
; key, length, payload, so a reader SKIPS what it does not know using the
; length it was given: an old FTPD.CFG loads into a new build with the missing
; settings at their defaults, and a new one loads into an old build with the
; extra settings ignored. That is SPEC.md 51.5's rule for SYSTEM.CFG applied
; to a package's own file.
;
;   +0   8   'O88FTPD' and a NUL - byte for byte, or the file is not ours
;   +8   2   the format version, currently 1
;   +10  ..  records, until a key of 0:
;              +0 1  key
;              +1 1  payload length
;              +2 n  the payload
;
; A truncated record ends the parse with what has been read so far, rather
; than refusing the whole file: a half-written settings file should cost the
; setting, not the session.
; =============================================================================
FC_END      equ 0
FC_PASV     equ 'A'                 ; 4 bytes, the PASV address in wire order
FC_ROOT     equ 'R'                 ; the folder to serve, as a PATH
FC_USER     equ 'U'                 ; a user name; NO record = accept anyone
FC_PASS     equ 'P'                 ; a password
                                    ; ...and the three carry NO terminator:
                                    ; the record's own length byte is what
                                    ; bounds them, so an empty string is an
                                    ; ABSENT record and never a 1-byte one
FC_MACH     equ 'M'                 ; 1 byte: serve the WHOLE MACHINE
FC_RO       equ 'O'                 ; 1 byte: refuse every write

fd_cfg_name: db 'FTPD.CFG', 0
fd_cfg_sig:  db 'O88FTPD', 0        ; 8 bytes, and compared as 8
fd_d_system: db 'SYSTEM', 0
fd_d_appdat: db 'APPDATA', 0

; --- fd_data_enter / fd_data_leave - stand in SYSTEM\APPDATA on OUR volume --
; Cyclone's routine (SPEC.md 67.20) and its trap, which is worth repeating
; where the next person will read it: **IT IS OSAPI_FILE_GOTO AND NOT ITS
; QUIET TWIN.** GOTO_Q moves the GLOBAL cwd and deliberately not the
; INSTANCE's, while OSAPI_FILE_FIND, _READ and _WRITE every one resolve in the
; instance's folder through inst_vol_enter - so a quiet move is undone by the
; very next call and the write lands where the app was launched from. SPEC.md
; 19.9's own prose says to use the quiet twin and is wrong about it.
fd_data_enter:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    call OSAPI_FILE_HERE            ; DX = our cwd, BL = our drive
    mov [fd_dbclus], dx
    mov [fd_dbdrv], bl
    xor dx, dx                      ; the ROOT of that same volume
    call OSAPI_FILE_GOTO
    jc .back
    mov si, fd_d_system
    call fd_data_dive
    jc .back
    mov si, fd_d_appdat
    call fd_data_dive
    jc .back
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.back:
    ; A DISK WITHOUT THE FOLDER IS NOT AN ERROR (SPEC.md 19.9) - it is a user's
    ; own disk. Put the volume back and refuse; the caller then keeps its state
    ; in memory and says nothing, which is what a refused write already did.
    call fd_data_home
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

fd_data_leave:
    pushf                           ; the caller's result is in CF and AX
    push ax
    push bx
    push cx
    push dx
    push si
    call fd_data_home
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    popf
    ret

fd_data_home:
    push ax
    push bx
    push dx
    mov dx, [fd_dbclus]
    mov bl, [fd_dbdrv]
    call OSAPI_FILE_GOTO
    pop dx
    pop bx
    pop ax
    ret

; --- fd_data_dive - step into the folder named at SI. CF=1 = no such folder --
fd_data_dive:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call fd_find                    ; the ordinal walk, fd_fbuf filled
    jc .no
    cmp word [fd_fbuf+14], OSAPI_FT_DIR
    jne .no
    mov dx, [fd_fbuf+16]
    call OSAPI_FILE_HERE            ; BL = the drive; DX is spent by it...
    mov dx, [fd_fbuf+16]            ; ...so the folder's cluster goes back
    call OSAPI_FILE_GOTO
    jc .no
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret
.no:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    stc
    ret

; --- fd_cfg_load - read FTPD.CFG if it is there. Never fails visibly --------
fd_cfg_load:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    call fd_data_enter
    jc .out
    mov si, fd_cfg_name
    mov bx, fd_cfgb
    mov cx, FD_CFGSZ
    xor dx, dx
    call OSAPI_FILE_READ            ; DX:AX = the size
    jc .leave
    or dx, dx
    jnz .leave                      ; longer than our buffer: not ours
    cmp ax, 10
    jb .leave                       ; too short to hold a header
    mov [fd_cfgn], ax
    call fd_cfg_parse
.leave:
    call fd_data_leave
.out:
    call fd_pasv_str                ; the field shows whatever survived
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- fd_cfg_parse - the records, skipping what this build does not know -----
fd_cfg_parse:
    push ax
    push bx
    push cx
    push si
    push di
    mov si, fd_cfgb
    mov di, fd_cfg_sig
    mov cx, 8
.sig:
    mov al, [si]
    cmp al, [di]
    jne .out                        ; not our file: leave every default alone
    inc si
    inc di
    loop .sig
    add si, 2                       ; the version: nothing branches on it YET,
                                    ; because the KEYS carry compatibility and
                                    ; a version bump is for the day a key has
                                    ; to change MEANING rather than appear
.rec:
    mov bx, si
    sub bx, fd_cfgb
    add bx, 2
    cmp bx, [fd_cfgn]
    ja .out                         ; a truncated record: keep what we have
    mov al, [si]                    ; the key
    cmp al, FC_END
    je .out
    mov ah, [si+1]                  ; its length
    add si, 2
    push ax
    xor ah, ah
    mov bx, si
    sub bx, fd_cfgb
    pop ax
    push ax
    mov al, ah
    xor ah, ah
    add bx, ax
    cmp bx, [fd_cfgn]
    pop ax
    ja .out                         ; the payload runs off the end
    cmp al, FC_PASV
    jne .k_root
    cmp ah, 4
    jne .skip
    mov bx, [si]
    mov [fd_pasv], bx
    mov bx, [si+2]
    mov [fd_pasv+2], bx
    jmp short .skip
.k_root:
    cmp al, FC_ROOT
    jne .k_user
    mov di, fd_roots
    mov cx, FD_ROOTMAX
    call fd_cfg_getstr
    jmp short .skip
.k_user:
    cmp al, FC_USER
    jne .k_pass
    mov di, fd_users
    mov cx, FD_USERMAX
    call fd_cfg_getstr
    jmp short .skip
.k_pass:
    cmp al, FC_PASS
    jne .k_mach
    mov di, fd_passs
    mov cx, FD_USERMAX
    call fd_cfg_getstr
    jmp short .skip
.k_mach:
    cmp al, FC_MACH
    jne .kro
    or ah, ah
    jz .skip
    mov bl, [si]
    mov [fd_mach], bl
    jmp short .skip
.kro:
    cmp al, FC_RO
    jne .skip
    or ah, ah
    jz .skip
    mov bl, [si]
    mov [fd_ro], bl
.skip:
    mov al, ah                      ; **SKIP BY THE LENGTH**, which is the whole
    xor ah, ah                      ; of what makes this format grow: a key
    add si, ax                      ; this build has never heard of costs it
    jmp .rec                        ; nothing at all. NEAR: the key ladder above
                                    ; grew past a short jump's reach
.out:
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; --- fd_cfg_putflag - AL = the key, AH = the value, appended at DI ----------
; OFF writes no record at all, which is the same rule fd_cfg_putstr follows
; for an empty string: the file carries only what was actually set.
fd_cfg_putflag:
    or ah, ah
    jz .out
    mov [di], al
    mov byte [di+1], 1
    mov [di+2], ah
    add di, 3
.out:
    ret

; --- fd_cfg_getstr - a record's payload into DI, CX = its capacity ----------
; in: SI -> the payload, AH = its length. Clamped and always terminated: a
; length from a file is a number somebody else wrote.
fd_cfg_getstr:
    push ax
    push cx
    push si
    push di
    mov al, ah
    xor ah, ah
    dec cx                          ; leave room for the NUL
    cmp ax, cx
    jbe .n
    mov ax, cx                      ; a longer string than this build's buffer
.n:                                 ; is TRUNCATED, not refused
    mov cx, ax
    jcxz .term
.c:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    loop .c
.term:
    mov byte [di], 0
    pop di
    pop cx
    pop si
    pop ax
    ret

; --- fd_cfg_putstr - AL = the key, SI = a NUL string, appended at DI --------
; An empty string writes NO RECORD: the absent key is the default, so a file
; carries only what was actually set.
fd_cfg_putstr:
    push ax
    push bx
    push cx
    push si
    cmp byte [si], 0
    je .out
    mov bx, di                      ; the length byte's slot, filled after
    mov [di], al
    add di, 2
    xor cx, cx
.c:
    mov al, [si]
    or al, al
    jz .done
    mov [di], al
    inc di
    inc si
    inc cx
    jmp short .c
.done:
    mov [bx+1], cl
.out:
    pop si
    pop cx
    pop bx
    pop ax
    ret

; --- fd_cfg_save - compose and write. A refusal is silent (SPEC.md 19.9) ----
fd_cfg_save:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    mov di, fd_cfgb
    mov si, fd_cfg_sig
    mov cx, 8
.sig:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    loop .sig
    mov word [di], 1                ; the version
    add di, 2
    mov ax, [fd_pasv]               ; ...and the ONE record there is, omitted
    or ax, [fd_pasv+2]              ; entirely when it is unset rather than
    jz .end                         ; written as four zeroes
    mov byte [di], FC_PASV
    mov byte [di+1], 4
    add di, 2
    mov ax, [fd_pasv]
    mov [di], ax
    mov ax, [fd_pasv+2]
    mov [di+2], ax
    add di, 4
.end:
    mov al, FC_ROOT                 ; an EMPTY string is omitted rather than
    mov si, fd_roots                ; written as a record with nothing in it -
    call fd_cfg_putstr              ; the absent key IS the default
    mov al, FC_USER
    mov si, fd_users
    call fd_cfg_putstr
    mov al, FC_PASS
    mov si, fd_passs
    call fd_cfg_putstr
    mov al, FC_MACH                 ; ...and the two flags, each omitted when
    mov ah, [fd_mach]               ; it is off - the absent key IS the default
    call fd_cfg_putflag
    mov al, FC_RO
    mov ah, [fd_ro]
    call fd_cfg_putflag
.fin:
    mov byte [di], FC_END
    inc di
    mov cx, di
    sub cx, fd_cfgb
    call fd_data_enter
    jc .out
    mov si, fd_cfg_name
    mov bx, fd_cfgb
    xor dx, dx
    call OSAPI_FILE_WRITE
    call fd_data_leave
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
; fd_about - the credits, as a MODE of the window rather than a second window
;
; A flag the painter honours, cleared by the next click anywhere. That is
; Arkanoid's shape (SPEC.md 44) and it is what keeps the panel out of the
; window manager entirely: there is no second window to own, hide, or have a
; file dialog refuse (SPEC.md 56's PlayList is the cautionary case).
; -----------------------------------------------------------------------------
fd_about:
    push si
    mov byte [fd_page], FP_ABOUT
    mov si, [fd_win]
    call fd_layout
    call fd_draw_all                ; a PAGE change is the whole content box
    pop si
    ret

; --- fd_draw_about - the panel, over the whole content box -------------------
fd_draw_about:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call fd_clear_content
    mov di, fd_ab_l
    mov bx, [fd_oy]
    add bx, FD_PAD
.l:
    mov si, [di]
    or si, si
    jz .out
    mov cx, [fd_ox]
    add cx, FD_PAD
    mov dx, bx
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    add bx, FD_ROWH + 2
    add di, 2
    jmp short .l
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; STRINGS
;
; Every reply is an RFC 959 three-digit code and a line of text. The codes are
; not decoration: a client branches on the digits and shows the text to a
; person, so both halves have to be right.
; =============================================================================
fd_ttl:     db 'FTP Server', 0
fd_name_s:  db 'Ftpd', 0
fd_m_srv:   db 'Server', 0
fd_i_srv:   dw fd_it_run, fd_it_clr, fd_it_set
fd_it_run:  db 'Start / Stop', 0
fd_it_clr:  db 'Clear Log', 0
fd_it_set:  db 'Setup...', 0

; --- the status line ---------------------------------------------------------
fd_s_state: dw fd_s_off, fd_s_lis, fd_s_ctl, fd_s_err
fd_s_off:   db 'Stopped', 0
fd_s_lis:   db 'Listening', 0
fd_s_ctl:   db 'Client connected', 0
fd_s_err:   db '', 0
fd_s_onport: db ' port ', 0
fd_s_at:    db ' at ', 0
fd_l_dport: db 'Data port ', 0
fd_l_prange: db 'Passive data ports 2048-2055', 0
fd_s_noaddr: db '(no address)', 0
fd_s_start: db 'Start', 0
fd_s_stop:  db 'Stop', 0
fd_s_ro:    db 'Read Only', 0
fd_s_setup: db 'Setup', 0
fd_s_done:  db 'Done', 0

; --- what the log says -------------------------------------------------------
fd_l_ready: db 'Ready - press Start', 0
fd_l_listen: db 'Listening on port 21', 0
fd_l_conn:  db 'Client connected', 0
fd_l_bye:   db 'Client disconnected', 0
fd_l_stop:  db 'Stopped', 0

; --- why it would not start --------------------------------------------------
fd_e_nodrv: db 'No network driver', 0
fd_e_nolink: db 'No network', 0
fd_e_noport: db 'Port 21 is in use', 0
fd_e_root:  db 'No such Root folder', 0
fd_e_lost:  db 'Link lost', 0

; --- the replies -------------------------------------------------------------
fd_r220:    db '220 os8088 FTP server ready', 0
fd_r221:    db '221 Goodbye', 0
fd_r331:    db '331 Password required', 0
fd_r230:    db '230 Logged in', 0
fd_r530:    db '530 Log in first', 0
fd_r530b:   db '530 Login incorrect', 0
fd_r200:    db '200 Ok', 0
fd_r200t:   db '200 Type set to binary', 0
fd_r215:    db '215 UNIX Type: L8', 0
fd_r211a:   db '211-Features:', 0
fd_r211b:   db ' SIZE', 0
fd_r211c:   db '211 End', 0
fd_r150:    db '150 Opening data connection', 0
fd_r226:    db '226 Transfer complete', 0
fd_r226a:   db '226 Aborted', 0
fd_r227:    db '227 Entering Passive Mode (', 0
fd_r229:    db '229 Entering Extended Passive Mode (|||', 0
fd_r229b:   db '|)', 0
fd_r250:    db '250 Done', 0
fd_r250c:   db '250 Directory changed', 0
fd_r257:    db '257 "', 0
fd_r257c:   db '" created', 0
fd_r213:    db '213 ', 0
fd_r350:    db '350 Ready for RNTO', 0
fd_r425:    db '425 Cannot open a data connection', 0
fd_r425a:   db '425 No address yet - PASV needs one, try EPSV', 0
fd_r425n:   db '425 Use PASV or PORT first', 0
fd_r452:    db '452 No buffer for a transfer on this disk', 0
fd_r500:    db '500 Line too long', 0
fd_r501:    db '501 Bad argument', 0
fd_r502:    db '502 Not implemented', 0
fd_r503:    db '503 RNFR first', 0
fd_r504:    db '504 Not supported for that parameter', 0
fd_r550:    db '550 No such file or directory', 0
fd_r550d:   db '550 No such directory', 0
fd_r550n:   db '550 Directory not empty', 0
fd_r550w:   db '550 The server is read only', 0
fd_r551:    db '551 Read failed', 0
fd_r552:    db '552 Write failed - disk full or protected', 0
fd_r426:    db '426 Transfer stalled - no data for 90 seconds', 0
fd_r553:    db '553 File name not allowed - 8.3 only, no spaces', 0
fd_l_stall: db 'Stalled: ', 0
fd_l_stb:   db ' bytes, sk ', 0
fd_l_stq:   db ' q ', 0
fd_s_file:  db 'FILE', 0
fd_syms:    db '$', '%', 0x27, '-', '_', '@', '~', 0x60
            db '!', '(', ')', '{', '}', '^', '#', '&', 0
fd_r552f:   db '552 No free space on the volume', 0

; --- the listing's fixed columns ---------------------------------------------
; The permission bits are what an `ls -l` parser reads to tell a file from a
; directory, and they are the only part of the row a client acts on.
fd_ls_file: db '-rw-rw-rw-   1 os8088   os8088   ', 0
fd_ls_dir:  db 'drwxrwxrwx   1 os8088   os8088   ', 0
fd_ls_date: db ' Jan  1  1980 ', 0
fd_ls_zero: db '         0 Jan  1  1980 ', 0
FD_ROWMAX   equ 80                  ; the longest row fd_list_row can emit: the
                                    ; 32-byte prefix, 10 of size, 14 of date,
                                    ; 12 of name and a CRLF, with room over

; --- the Setup page ----------------------------------------------------------
fd_s_sethd:  db 'An empty field is the default', 0
fd_s_mach:   db 'Serve every drive (ignores Root)', 0
fd_s_sethelp: db 'Root:  A:/DOCS   /DOCS   or blank', 0
fd_s_f0:     db 'PASV addr', 0
fd_s_f1:     db 'Root', 0
fd_s_f2:     db 'User', 0
fd_s_f3:     db 'Password', 0

fd_ftab:
    dw fd_s_f0, fd_pasvs, FD_IPMAX
    dw fd_s_f1, fd_roots, FD_ROOTMAX
    dw fd_s_f2, fd_users, FD_USERMAX
    dw fd_s_f3, fd_passs, FD_USERMAX

; --- the About panel ---------------------------------------------------------
fd_ab_l:    dw fd_ab1, fd_ab2, fd_ab3, fd_ab4, fd_ab5, fd_ab6, 0
fd_ab1:     db 'FTP Server for os8088', 0
fd_ab2:     db 0
fd_ab3:     db 'RFC 959, one client at a time.', 0
fd_ab4:     db 'Serves the folder it was launched from.', 0
fd_ab5:     db 0
fd_ab6:     db 'Anyone on the network can read these', 0

    OS88_MENUSET fd_menus, fd_name_s, fd_oncmd
        OS88_MENU fd_m_srv, fd_i_srv, 3
    OS88_MENUSET_END fd_menus

fd_tpl:
    dw 40, 40, FD_W, FD_H
    dw fd_ttl, fd_paint, fd_onkey, fd_onclick

%include "os88ui.inc"
%include "os88line.inc"             ; the Setup page's address field. AFTER
                                    ; os88ui.inc, which it needs the UI_*
                                    ; macros from (its own header says so)
%include "os88sock.inc"             ; net_find (SPEC.md 72, SPEC.md 20.11.1)

    OS88_BSS FD_BSS
    OS88_IMAGE_END

; --- loader-zeroed bss (SPEC.md 21 step 5) -----------------------------------
fd_win      equ os88_image_end + 0   ; word
fd_ox       equ os88_image_end + 2   ; word
fd_oy       equ os88_image_end + 4   ; word
fd_cw       equ os88_image_end + 6   ; word
fd_ch       equ os88_image_end + 8   ; word
fd_leny     equ os88_image_end + 10  ; word: the log's first pen y, banked
fd_chunk    equ os88_image_end + 16  ; word: the cluster-rounded commit size
fd_sfill    equ os88_image_end + 18  ; word: bytes in the stage
fd_sout     equ os88_image_end + 20  ; word: ...and how many have been sent
fd_clen     equ os88_image_end + 22  ; word: bytes in the control buffer
fd_lend     equ os88_image_end + 24  ; word: where its first line ends
fd_arglen   equ os88_image_end + 26  ; word
fd_dport    equ os88_image_end + 28  ; word
fd_lord     equ os88_image_end + 30  ; word: the listing's next ordinal
fd_foff     equ os88_image_end + 32  ; dword: the read offset
fd_fsize    equ os88_image_end + 36  ; dword: the file's size
fd_bclus    equ os88_image_end + 40  ; word: the banked directory
fd_pathp    equ os88_image_end + 42  ; word: which string fd_split is walking
fd_dpp      equ os88_image_end + 44  ; word: PORT's p1, across the fields
fd_utmp     equ os88_image_end + 12  ; word: the folder a descent is leaving
                                     ; (the two words fd_sseg/fd_ssz freed
                                     ; when the stage moved into bss)
fd_bdepth   equ os88_image_end + 14  ; byte: the banked depth
fd_cdepth   equ os88_image_end + 15  ; byte: how deep the session has walked
fd_msg      equ os88_image_end + 46  ; word: -> why it will not start
fd_st       equ os88_image_end + 48  ; byte: FD_*
fd_xf       equ os88_image_end + 49  ; byte: FX_* - WHAT is moving
fd_dmode    equ os88_image_end + 71  ; byte: DM_* - HOW the data connection
                                     ; is made. A SEPARATE BYTE, and the
                                     ; comment by DM_NONE says what sharing
                                     ; one cost
fd_req      equ os88_image_end + 50  ; byte: FR_* - **THE HANDSHAKE**
fd_spawned  equ os88_image_end + 51  ; byte
fd_lhnd     equ os88_image_end + 52  ; byte: the port-21 listener
fd_chnd     equ os88_image_end + 53  ; byte: the control connection
fd_dlhnd    equ os88_image_end + 54  ; byte: the passive listener
fd_dhnd     equ os88_image_end + 55  ; byte: the data connection
fd_auth     equ os88_image_end + 56  ; byte: PASS has been seen
fd_ro       equ os88_image_end + 57  ; byte: the Read Only box
fd_dirty    equ os88_image_end + 58  ; byte: FDD_* - what on the face is
                                     ; behind the glass
fd_lognext  equ os88_image_end + 59  ; byte: the ring's write slot
fd_lstyle   equ os88_image_end + 60  ; byte: 0 = LIST, 1 = NLST
fd_lmore    equ os88_image_end + 61  ; byte: there is more to come (2 = last)
fd_created  equ os88_image_end + 62  ; byte: STOR has made the file
fd_banked   equ os88_image_end + 63  ; byte: fd_split moved us
fd_bdrv     equ os88_image_end + 64  ; byte: ...and the drive it moved from
fd_spc      equ os88_image_end + 65  ; byte: sectors per cluster, banked
fd_havern   equ os88_image_end + 66  ; byte: RNFR has been accepted
fd_pasvn    equ os88_image_end + 67  ; byte: the rotating passive port
fd_page     equ os88_image_end + 68  ; byte: FP_* - which face is drawn
fd_pfoc     equ os88_image_end + 69  ; byte: the Setup field has the caret
fd_tmpb     equ os88_image_end + 70  ; byte: PORT's saw-a-digit flag
fd_down     equ os88_image_end + 72  ; word: WHICH CONTROL IS DRAWN PRESSED,
                                     ; as bfind's index+1 on the page that is
                                     ; up, 0 = none. The PAINTER reads it, so
                                     ; a W_PAINT arriving mid-gesture draws
                                     ; the control the way it actually is
                                     ; (SPEC.md 13.8.2's first consequence)
fd_dnb      equ os88_image_end + 74  ; word: what os88ui_bfind answered last
                                     ; time fd_ondrag ran - the drag handler
                                     ; redraws ONLY on a change, and this is
                                     ; what "a change" is measured against
                                     ; (SPEC.md 13.8.2's third consequence)
fd_verb     equ os88_image_end + 88  ; 4, space padded
fd_pf       equ os88_image_end + 92  ; 6 words: PORT's fields
fd_ip       equ os88_image_end + 104 ; 4: our own address
fd_fbuf     equ os88_image_end + 108 ; OSAPI_FIND_SZ
fd_sline    equ fd_fbuf + OSAPI_FIND_SZ         ; FD_LOGW + 1
fd_ipstr    equ fd_sline + FD_LOGW + 1          ; 16
fd_tmp      equ fd_ipstr + 16                   ; FD_LOGW + 1
fd_log_b    equ fd_tmp + FD_LOGW + 1            ; FD_LOGSZ
fd_ctlb     equ fd_log_b + FD_LOGSZ             ; FD_CTL
fd_outb     equ fd_ctlb + FD_CTL                ; FD_OUT
fd_outb2    equ fd_outb + FD_OUT                ; FD_OUT: a composed reply
fd_arg      equ fd_outb2 + FD_OUT               ; FD_PATHMAX
fd_xname    equ fd_arg + FD_PATHMAX             ; FD_PATHMAX: the transfer's
fd_path     equ fd_xname + FD_PATHMAX           ; FD_PATHMAX: what PWD prints
fd_rnfrom   equ fd_path + FD_PATHMAX            ; FD_PATHMAX
fd_leaf     equ fd_rnfrom + FD_PATHMAX          ; FD_PATHMAX
fd_comp     equ fd_leaf + FD_PATHMAX            ; FD_NAMEMAX
fd_rnto_l   equ fd_comp + FD_NAMEMAX            ; FD_PATHMAX
fd_dhost    equ fd_rnto_l + FD_PATHMAX          ; 20: PORT's dotted quad
fd_cstack   equ fd_dhost + 20                   ; FD_CDMAX words: the clusters
                                     ; a CWD descended through, so CDUP has
                                     ; somewhere to go back to
fd_path2    equ fd_cstack + FD_CDMAX*2          ; FD_PATHMAX: the banked path
fd_pasv     equ fd_path2 + FD_PATHMAX           ; 4: the PASV override, wire
                                     ; order. All zero = unset, use our own
fd_pasvs    equ fd_pasv + 4                     ; FD_IPMAX: ...as typed
fd_roots    equ fd_pasvs + FD_IPMAX             ; FD_ROOTMAX: the folder to
                                     ; serve, as a PATH and never as a cluster
                                     ; - a cached cluster plus a swapped disk
                                     ; is somebody else's folder (SPEC.md 19.9)
fd_users    equ fd_roots + FD_ROOTMAX           ; FD_USERMAX: empty = anyone
fd_passs    equ fd_users + FD_USERMAX           ; FD_USERMAX
fd_userin   equ fd_passs + FD_USERMAX           ; FD_USERMAX: what THIS client
                                     ; sent, banked across USER -> PASS
fd_lines    equ fd_userin + FD_USERMAX          ; FD_FN * OS88LINE_SZ
fd_mach     equ fd_lines + FD_FN*OS88LINE_SZ    ; byte: serve every drive
fd_mlevel   equ fd_mach + 1                     ; byte: the session is AT the
                                     ; machine level, above any volume
fd_rrclus   equ fd_mlevel + 1                   ; word: where fd_root_resolve
fd_rrdrv    equ fd_rrclus + 2                   ; byte: ...started, so a root
                                     ; that will not walk goes back there
fd_rowed    equ fd_rrdrv + 1                    ; byte: a session has begun and
                                     ; owes a walk back to the root
fd_bmlevel  equ fd_rowed + 1                    ; byte: ...banked with the
                                     ; folder, because a temporary descent out
                                     ; of the machine root has to come back up
fd_rdrv     equ fd_bmlevel + 1                  ; byte: the resolved root...
fd_rclus    equ fd_rdrv + 1                     ; word: ...as (drive, cluster)
fd_cfgb     equ fd_rclus + 2                    ; FD_CFGSZ: FTPD.CFG, whole
fd_dbclus   equ fd_cfgb + FD_CFGSZ              ; word: the banked folder
fd_dbdrv    equ fd_dbclus + 2                   ; byte: ...and its drive
fd_cfgn     equ fd_dbdrv + 1                    ; word: bytes read
; -----------------------------------------------------------------------------
; THE TWO RECT TABLES - CONTIGUOUS, because os88ui_bfind strides an array
;
; One table per page, three 4-word rects each, laid out in the order
; FD_R_* names. They are separate rather than one table rebuilt per page so
; that no ORDER of layout calls can leave a stale rect behind: fd_onclick
; runs fd_layout unconditionally, and a shared table would have the log
; page's coordinates land on top of the Setup page's between that call and
; fd_setup_rects.
;
; A control that is not in a table is one that does NOT fire on the release:
; the four Setup fields keep the press, because focusing a field is
; SELECTING and SPEC.md 13.8.8 keeps the press for exactly that.
; -----------------------------------------------------------------------------
fd_rects    equ fd_cfgn + 2                     ; 24: the LOG page's three
fd_btn      equ fd_rects + 0                    ; ...Start/Stop
fd_rob      equ fd_rects + 8                    ; ...the Read Only box
fd_setb     equ fd_rects + 16                   ; ...and Setup
fd_srects   equ fd_rects + 24                   ; 24: the SETUP page's three
fd_done     equ fd_srects + 0                   ; ...Done, in Start's corner
fd_rchk     equ fd_srects + 8                   ; ...the Read Only tick - the
                                     ; same SETTING fd_rob shows, drawn twice
                                     ; because it is reachable from two pages
fd_mchk     equ fd_srects + 16                  ; ...and Serve every drive
fd_cdirty   equ fd_rchk + 8                     ; byte: a setting changed and
                                     ; the file owes a write (SPEC.md 77.17)
fd_lognew   equ fd_cdirty + 1                   ; byte: rows appended since the
                                     ; glass last agreed with the ring
fd_scrn     equ fd_lognew + 1                   ; word: ...as rows, banked
fd_scry     equ fd_scrn + 2                     ; word: ...and as pixels
fd_xbytes   equ fd_scry + 2                     ; 32-bit: bytes this transfer
                                     ; has actually MOVED, for the stall log
fd_mext     equ fd_xbytes + 4                   ; 4: the extension fd_mangle83
                                     ; lifted out, while it rewrites the stem
                                     ; UNDER it - the two overlap in fd_leaf,
                                     ; so the ext cannot stay where it was
fd_wdog     equ fd_mext + 4                     ; word: the tick the transfer
                                     ; last MOVED A BYTE (SPEC.md 77.19)
fd_wprog    equ fd_wdog + 2                     ; word: how far it had got when
                                     ; that was stamped, so "moved" is measured
                                     ; and not assumed
fd_stage    equ fd_wprog + 2                    ; FD_STGSZ - the transfer's
                                     ; staging ground, and IN OUR OWN SEGMENT
                                     ; for the reason FD_STGSZ's own comment
                                     ; gives: the package door hands a driver
                                     ; the CALLER's segment in ES, so a socket
                                     ; buffer anywhere else is unreachable
FD_BSS      equ fd_stage + FD_STGSZ - os88_image_end
