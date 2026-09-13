; =============================================================================
; apps/dos/dosc.inc - THE CONSOLE, AND THE PROMPT IN IT (SPEC.md 96.33)
; =============================================================================
; §96.32 cut the window to eighty columns and left the band below the top bar
; empty, with three lines of status text standing in it. This is what goes
; there: `apps/os88con.inc`'s 80x25 screen, black with white text, and a
; `COMMAND.COM`-shaped prompt typing into it.
;
; **THERE IS NO INTERPRETER HERE.** `dosh.inc` is the interpreter and has been
; since §96.30, whose own header says what this file is: *"a prompt in a window
; differs from this in its INPUT (a typed line rather than a command tail) and
; its OUTPUT (a text pane rather than the ROM teletype), and in nothing else"*.
; So what is below is an input, an output and a prompt - and every verb in
; `dsh_tab` became reachable from the keyboard without being touched.
;
; NO OSAPI_* FILE SLOT IS CALLED FROM THIS FILE either (§96.4), and the
; prompt's own path is the place that would have been the exception: it wants
; the instance's current directory, and `DBE_PATH` is the verb for it
; (§96.4.1).
; -----------------------------------------------------------------------------

; -----------------------------------------------------------------------------
; dos_con_start - the console a fresh window opens with
; in:  nothing; the entry proc, before the first paint
; out: nothing; clobbers AX, CX, SI, DI
;
; con_open is NOT OPTIONAL (§96.33.1): the loader zeroes bss, so an unopened
; console has attribute 0 - black on black - and every character written into
; it is invisible. The banner is two lines because the second one is the part a
; user needs and the first is the part they recognise.
; -----------------------------------------------------------------------------
dos_con_start:
    ; --- WHERE THE PROMPT STARTS (SPEC.md 96.33.2) --------------------------
    ; **THE DRIVE WE WERE LAUNCHED FROM, AT ITS ROOT.** The drive is neither a
    ; constant nor a guess - OSAPI_FILE_HERE answers the instance's own volume
    ; with no disk I/O at all, and [dos_vol] is zero out of bss where zero is
    ; drive A: (SPEC.md 96.6.3's sentinel trap one file along), so an installed
    ; machine's box stood on C: and printed `A:\>`.
    ;
    ; **AND THE FOLDER IS DELIBERATELY NOT THE ONE IT ANSWERS.** That is
    ; `APPS\` - where this package's file happens to live - and a user opening
    ; a DOS box has come for a machine, not for our installation layout. A
    ; prompt that opens `A:\APPS>` is one they have to `CD \` out of before
    ; anything they type means what it looks like.
    ;
    ; Both are overwritten the moment a document arrives: dos_entry's
    ; OSAPI_ARG_FILE path sets them from the argument, and it runs after this.
    call OSAPI_FILE_HERE            ; DX = the folder, BL = the drive
    mov [dos_vol], bl
    mov word [dos_curdir], 0        ; ...and dsh_home, below, walks us there
    call con_open
    mov si, dsh_s_ver               ; THE SHELL'S OWN `VER` LINE, which is what
    call con_say                    ; a DOS machine opens with - and sharing it
    mov si, dos_c_hint              ; means the version is stated in one place
    call con_say
    call dos_prompt
    ret

; -----------------------------------------------------------------------------
; dos_prompt - `$P$G`, recomposed (SPEC.md 96.33.2)
; in:  nothing; out: nothing; every register preserved
;
; **RECOMPOSED AND NEVER HELD**, so `CD` and a drive change need nothing
; invalidated: the letter is [dos_vol] through §96.6's identity map and the
; path is OSAPI_FILE_PATH's, which is the same pair dos_envpath builds MYPATH
; out of. There is no PROMPT command and `$P$G` is not stored (§96.33.2).
;
; IT STANDS WHERE THE SHELL STANDS FIRST. A built-in brackets itself with
; dsh_bank/dsh_home, but a PROGRAM that ran has left the instance wherever its
; own file was (dos_run's quiet GOTO), so the prompt after one would name that
; folder and the next command would resolve against ours. One dsh_home puts
; both back in step.
; -----------------------------------------------------------------------------
dos_prompt:
    push ax
    push bx                         ; **BX AND DX, WHICH THE PAIR BELOW EATS.**
    push cx                         ; dsh_home's own comment says it clobbers
    push dx                         ; AX/BX/DX, and this proc is called from
    push si                         ; dos_con_start in the middle of an entry
    push di                         ; proc that goes on to hand BX to
                                    ; OSAPI_WM_ONWAKE - so the handler was
                                    ; registered against a wrong window and
                                    ; every package-posted wake did nothing:
                                    ; Run, Enter-re-run and the prompt's own
                                    ; launch all left [dos_state] at DST_READY
                                    ; for ever, with no error anywhere
    call dsh_bank                   ; ...which is where the shell's own cwd
    call dsh_home                   ; LIVES: [dos_curdir] and [dos_vol], and
                                    ; dsh_home is what makes the instance agree
    call dos_con_nl
    mov al, [dos_vol]
    add al, 'A'
    call con_write
    mov al, ':'
    call con_write
    mov di, dos_pbuf                ; the path, into the buffer dos_envpath
    mov cx, DOS_PBUF                ; uses for MYPATH - not at the same time as
    call OSAPI_FILE_PATH            ; this, which runs on the UI task between
    mov si, dos_pbuf                ; launches
    jnc .say
    mov si, dos_lnk_root            ; no answer: the root, which is where a box
.say:                               ; with nothing mounted would be standing
    call con_say
    mov al, '>'
    call con_write
    call dos_con_mark
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_con_nl - a newline, unless the cursor is already at column 0
; in:  nothing; out: nothing; every register preserved
;
; So that a prompt after a verb that ended in CR LF does not leave a blank line
; and one after a verb that printed nothing at all still gets its own.
; -----------------------------------------------------------------------------
dos_con_nl:
    push ax
    cmp word [con_cx], 0
    je .out
    mov al, 13
    call con_write
    mov al, 10
    call con_write
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_con_mark / dos_con_take - where the typed line STARTS
; in:  nothing; out: nothing (mark), CF=1 if the cursor is back at it (take)
;
; BACKSPACE MAY NOT EAT THE PROMPT, and the console has no notion of one: it is
; a screen, and `A:\>` is four cells of it like any other four. So the column
; the prompt ended on is banked, and BS stops there. It is a COLUMN and not a
; cell offset because a scroll moves the row and not the column - which is the
; only thing that can happen to the input line while it is being typed.
; -----------------------------------------------------------------------------
dos_con_mark:
    push ax
    mov ax, [con_cx]
    mov [dos_cmdx], ax
    pop ax
    ret

dos_con_take:                       ; ...AX is spent, which every caller of this
    mov ax, [con_cx]                ; one has already banked
    cmp ax, [dos_cmdx]
    ret                             ; CF=1 (below) = the caller has rubbed out
                                    ; everything it typed

; -----------------------------------------------------------------------------
; dos_con_key - a keystroke the console takes (SPEC.md 96.33.3)
; in:  AL = ascii, AH = scan, the gfx lock HELD (W_ONKEY's contract)
; out: CF=0 = taken; CF=1 = not ours, and the caller goes on looking
; clobbers: nothing but the flags
;
; **IT ECHOES AND IT DOES NOT REPAINT THE SCREEN.** con_write marks the row it
; changed and dos_con_draw spends that mark, so typing a character costs one
; row of eighty cells and not twenty-five of them - §96.19.1's measurement one
; control along, and the reason con_rows_owed exists at all (§70.8.1).
; -----------------------------------------------------------------------------
dos_con_key:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    cmp al, 13
    je .enter
    cmp al, 8
    je .bs
    cmp al, 27
    je .esc
    cmp al, ' '
    jb .no                          ; every other control, and an extended key's
    cmp al, 0x7F                    ; AL=0: not the console's, and a scan code
    je .no                          ; the caller may still want
    mov bx, [dos_cmdn]
    cmp bx, DSH_LINE - 1
    jae .full                       ; a line at its limit takes no more, and
                                    ; does not scroll one off the side either
    mov [dsh_line + bx], al
    inc bx
    mov [dos_cmdn], bx
    mov byte [dsh_line + bx], 0
    call con_write
    call dos_con_draw
.full:
    jmp short .done
.bs:
    call dos_con_take
    jbe .done                       ; at the prompt: nothing of ours to rub out
    cmp word [dos_cmdn], 0
    je .done
    dec word [dos_cmdn]
    mov bx, [dos_cmdn]
    mov byte [dsh_line + bx], 0
    mov al, 8                       ; BS, space, BS - the teletype's own erase,
    call con_write                  ; and the only one a screen with no cell
    mov al, ' '                     ; addressing has
    call con_write
    mov al, 8
    call con_write
    call dos_con_draw
    jmp short .done
.esc:
    mov word [dos_cmdn], 0          ; DOS draws a `\` and opens a new line;
    mov byte [dsh_line], 0          ; this clears the line in place, which is
    call dos_con_clrline            ; what a windowed box with a visible cursor
    jmp short .done                 ; should do. Esc in FULL SCREEN is the way
                                    ; out of it instead (§96.33.3), and that is
                                    ; tested before this proc is reached
.enter:
    call dos_con_run
.done:
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

; -----------------------------------------------------------------------------
; dos_con_clrline - rub the typed line off the screen, cursor back to the mark
; in:  nothing; out: nothing; clobbers AX, CX, flags
; -----------------------------------------------------------------------------
dos_con_clrline:
    push ax
    push cx
.back:
    mov ax, [con_cx]
    cmp ax, [dos_cmdx]
    jbe .done
    mov al, 8
    call con_write
    mov al, ' '
    call con_write
    mov al, 8
    call con_write
    jmp short .back
.done:
    call dos_con_draw
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_con_run - ENTER: run the line, then a new prompt (SPEC.md 96.33.3)
; in:  the gfx lock held; out: nothing; clobbers everything but the segments
;
; **THE BUILT-IN FIRST, THE PROGRAM SECOND**, which is DOS's own order and the
; reason `dsh_exec` exists: dsh_run's `.unknown` arm prints *"Bad command or
; file name"* for a `/c` shell, because there is nothing else it could be; from
; a prompt there is, so the message is held back and [dsh_why] says which arm
; was taken.
;
; A PROGRAM GOES THROUGH dos_go, the same proc the Run button calls - so the
; path box ends up holding what was typed (§96.33.3's "update the text box"),
; the arguments field holds the tail, and the launch is the launch that has
; been tested since §96.19 rather than a second one.
; -----------------------------------------------------------------------------
dos_con_run:
    mov al, 13
    call con_write
    mov al, 10
    call con_write
    cmp word [dos_cmdn], 0          ; **THE COUNT AND NOT THE BUFFER'S FIRST
    mov word [dos_cmdn], 0          ; BYTE** - `mov` does not touch the flags,
    je .prompt                      ; so one compare answers both. dsh_line
                                    ; still holds the LAST command after it has
                                    ; run, so testing the text would make a bare
                                    ; Enter re-run it; the count is what says
                                    ; whether anything was typed. Spent either
                                    ; way, dsh_redir being about to write a NUL
                                    ; into the buffer
    mov byte [dsh_exec], 1          ; ...hold .unknown's message back
    mov si, dsh_line
    call dsh_run
    mov byte [dsh_exec], 0
    or al, al
    jz .prompt
    cmp byte [dsh_why], DSHW_NOCMD
    jne .prompt                     ; it ran and refused, and said so itself
    call dos_con_prog
    jc .nocmd
    ret                             ; it is launching: the prompt comes back
                                    ; with the exit line, from dos_con_ended
.nocmd:
    mov si, dsh_s_bad               ; ...and NOW the message dsh_run held back
    call con_say
    mov si, dsh_verb
    call con_say
    mov si, dsh_s_crlf
    call con_say
.prompt:
    call dos_prompt
    call dos_con_draw
    ret

; -----------------------------------------------------------------------------
; dos_con_prog - try the typed line as a PROGRAM
; in:  [dsh_verb] = the verb, upper-cased; SI is spent
; out: CF=0 = it is launching; CF=1 = there is no such program
; clobbers: everything but the segments
;
; The line has already been through dsh_redir, so `[dsh_line]` is truncated at
; any `>` and the tail after the verb is the argument text - which is what the
; verb handlers are handed and what the arguments field wants.
; -----------------------------------------------------------------------------
dos_con_prog:
    mov si, dsh_line                ; the VERB as typed, not [dsh_verb]: that
    call dsh_skipsp                 ; one is upper-cased for the table compare
    mov di, dos_path                ; and an 8.3 name on a FAT volume is too,
    mov cx, DOS_PBUF - 1            ; but a path is the user's own text
.v:
    mov al, [si]
    or al, al
    je .vend
    cmp al, ' '
    je .vend
    cmp al, 9
    je .vend
    mov [di], al
    inc si
    inc di
    dec cx
    jnz .v
.vend:
    mov byte [di], 0
    call dsh_skipsp                 ; ...and everything after it is the tail
    mov di, dos_args
    mov cx, DOS_ARGMAX
.a:
    mov al, [si]
    or al, al
    je .aend
    mov [di], al
    inc si
    inc di
    dec cx
    jnz .a
.aend:
    mov byte [di], 0
    mov si, dos_pln                 ; both boxes re-measured from their text,
    call os88line_resync            ; because a field whose LN_LEN disagrees
    mov si, dos_ln                  ; with its buffer draws the old length
    call os88line_resync

    call dos_path_take              ; **A PARSE AND A WALK, NOT AN EXISTENCE
    jc .no                          ; CHECK** - it resolves the folder and takes
    mov byte [dos_state], DST_READY ; the 8.3 name, and whether there is a file
    mov byte [dos_fromcon], 1       ; of that name is dos_run's answer. So the
                                    ; refusal a typo earns is DER_READ, and
                                    ; this byte is what lets dos_con_ended
                                    ; spell it the way DOS does
    mov bx, [dos_win]
    call OSAPI_WM_WAKE              ; ...and dos_wake runs it, exactly as the
    mov bx, [dos_win]               ; Run button's dos_go does
    call dos_swap
    clc
    ret
.no:
    mov byte [dos_path], 0          ; the box goes back to empty rather than
    mov byte [dos_args], 0          ; keeping a name that does not resolve
    mov si, dos_pln
    call os88line_resync
    mov si, dos_ln
    call os88line_resync
    stc
    ret

; -----------------------------------------------------------------------------
; dos_con_ended - the console's line about a program that has stopped
; in:  [dos_state] is DST_RAN or DST_ERR; the gfx lock NOT held
; out: nothing; clobbers AX, BX, CX, DX, SI, DI
;
; It is where the three status lines §96.32's band carried went: a console is a
; LOG, so the thing that happened is said once and stays said, rather than
; being a sentence that is true until the next launch overwrites it.
; -----------------------------------------------------------------------------
dos_con_ended:
    cmp byte [dos_state], DST_ERR
    jne .name
    cmp byte [dos_fromcon], 0
    je .name
    cmp byte [dos_err], DER_READ
    jne .name                       ; **A TYPO IS "BAD COMMAND", NOT A DISK
    mov si, dsh_s_bad               ; FAULT** (SPEC.md 96.33.3). dos_path_take
    call con_say                    ; takes any legal 8.3 name, so a verb that
    mov si, dos_name                ; is neither a built-in nor a file gets as
    call con_say                    ; far as the load and fails there - and
    mov si, dsh_s_crlf              ; "It could not be read." about a program
    call con_say                    ; the user never had is a sentence that
    jmp short .out                  ; sends them looking at the drive
.name:
    mov si, dos_name
    call con_say
    cmp byte [dos_state], DST_ERR
    je .err
    mov si, dos_c_exit
    call con_say
    call dos_fmt_exit               ; SI = the line with the code stamped in -
    mov si, dos_exitd               ; and only its digits are wanted here
    call con_say
    mov si, dsh_s_crlf
    call con_say
    jmp short .out
.err:
    mov si, dos_c_colon
    call con_say
    call dos_err_line               ; SI = the sentence for [dos_err]
    call con_say
    mov si, dsh_s_crlf
    call con_say
.out:
    mov byte [dos_fromcon], 0       ; ...spent, so the NEXT launch - a Run
    call dos_prompt                 ; click, or a document - is spelled its own
    ret                             ; way

; -----------------------------------------------------------------------------
; dos_con_draw - spend the marks, under a lock the CALLER holds
; in:  the gfx lock held, [dos_win] live
; out: nothing; every register preserved
;
; The geometry has to be asked for again, because nothing tells a package its
; window moved (§11.96.12) - so this is dos_con_geom and then the rows that
; owe, which on a keystroke is one.
; -----------------------------------------------------------------------------
dos_con_draw:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    cmp byte [dos_fsxup], 0
    jne .out                        ; **A FOREIGN TEXT SCREEN IS UP** (SPEC.md
                                    ; 53.1): every kernel drawing slot renders
                                    ; desktop geometry into a framebuffer that
                                    ; is now character cells, so not one of
                                    ; them may be called. The keystroke still
                                    ; reaches con_write and still marks its
                                    ; row - [con_drb] is what carries the
                                    ; change across, and dos_fsx_owed spends
                                    ; it on the OTHER renderer
    mov bx, [dos_win]
    call dos_con_geom
    jc .out                         ; not visible: the marks keep, and the next
    call con_scrollpaint            ; paint spends them
    call con_rows_owed
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_con_say - a string into the console, and drawn, with the lock TAKEN
; in:  SI = a NUL string; the gfx lock NOT held
; out: nothing; every register preserved
;
; For the paths that write to the console from outside a callback - dos_run's
; own, which is the wake handler's context (§74.1).
; -----------------------------------------------------------------------------
dos_con_say:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call con_say
    call OSAPI_GFX_LOCK
    call dos_con_draw
    call OSAPI_GFX_UNLOCK
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

dos_c_hint:  db 13, 10, 'Type a command, or the name of a program to run.'
             db 13, 10, 0
dos_c_exit:  db ' ended, exit code ', 0
dos_c_colon: db ': ', 0

; =============================================================================
; FULL SCREEN, AND ESC BACK OUT (SPEC.md 96.33.5)
; =============================================================================
; The same 80x25 buffer on the real text screen, which is the only place the
; whole of it fits: the band shows 25 rows on Hercules and VGA and 15 on CGA,
; and an 80-column program's output is 80 columns wide on all three.
;
; **THE RENDERER IS os88con.inc's AND THE BRACKET IS OURS** (SPEC.md 70.8.13),
; and the four things it holds are the four two carriers do not agree about:
;
;   the mode      FSXM_TEXT80, which every adapter here can set
;   the worker    THERE IS NONE. Telnet passes FSXF_KEEPWORKER because its
;                 worker owns the socket; this box's console is written by the
;                 UI task alone, so a kept worker would be a task with nothing
;                 to do and one more thing to be wrong about
;   the key out   ESC, and Telnet's is Ctrl+] - see below
;   the hint      ours names Esc, so the string is ours too
;
; **ESC IS OURS ONLY WHILE THE CONSOLE HAS THE SCREEN.** A DOS program reads
; Esc for its own purposes and a box that ate it could not run half the
; software it exists for - so this bracket is entered from the menu, ends
; before any program is launched, and the program's own bracket (96.2) is a
; different one with no key of ours in it at all. SPEC.md 11.2.1 asks for `F`
; in both directions and exempts an app taking typed text, which a command
; prompt is as completely as a terminal.
; -----------------------------------------------------------------------------

; --- dos_fsx - Program > Full Screen ----------------------------------------
; in:  SI = our window; UI task, gfx lock held (a callback's environment)
; out: nothing; preserves all registers
dos_fsx:
    push ax
    push bx
    push cx
    push si
    mov bx, si
    call OSAPI_FSX_CAPS             ; AX = the modes this adapter allows, DL =
    test ax, 1 << FSXM_TEXT80       ; the DISPLAY's own kind (SPEC.md 53.7.1),
    jz .out                         ; which osapi_video cannot answer for a
    mov [con_tkind], dl             ; window that is not on the primary
    mov byte [dos_fsxup], 1         ; ...BEFORE the bracket, so nothing between
    mov ax, dos_fsx_con             ; here and the mode set can reach a drawing
    mov bx, si                      ; slot either
    xor cx, cx                      ; NO FSXF_KEEPWORKER: this box has no worker
    call OSAPI_FSX_RUN
    mov byte [dos_fsxup], 0         ; ...and again on the refusal path, where
.out:                               ; dos_fsx_con never ran
    pop si
    pop cx
    pop bx
    pop ax
    ret

; --- dos_fsx_con - the bracket's body ---------------------------------------
; in:  SI = our window, ES = KERNEL_SEG, DS = CS = ours; near ret
dos_fsx_con:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es                          ; the FSI block is OURS (the gfx_blit4
    mov di, dos_fsi                 ; idiom: ES:DI is the caller's own)
    mov al, FSXM_TEXT80
    call OSAPI_FSX_MODE
    jc .done
    mov ax, [dos_fsi + FSI_SEG]     ; the ONE thing that is not a constant:
    mov [con_tseg], ax              ; B000 on Hercules and B800 on the rest
    mov byte [con_tcur], 0xFF       ; **NOT 0 AND NOT 1**: con_tx_cursor issues
                                    ; the SHAPE only on a change, and the mode
                                    ; set left the CRTC's own cursor blinking
                                    ; at 0,0 - so a byte that already agrees
                                    ; with [con_cvis] means it never places it
    call con_tx_ice                 ; ...and the blink bit, per adapter (70.8.9)
    mov byte [con_thint], 0xFF
    call con_markall
    call dos_fsx_owed
    mov si, dos_c_leave             ; ONCE, on entry, and anything that draws
    call con_tx_hint                ; over it may (SPEC.md 70.8.7)
.loop:
    call dos_fsx_keys
    jc .done
    call dos_fsx_owed
    mov al, FSXW_FRAME              ; YIELDS while it waits, so the rest of the
    call OSAPI_FSX_WAIT             ; machine keeps its slices
    jmp short .loop
.done:
    mov byte [dos_fsxup], 0         ; ...INSIDE the bracket, so fsx_restore's
    call con_markall                ; repaint finds the box windowed and the
    pop es                          ; whole band owed, and dos_con_draw is
    pop di                          ; whole band owed
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- dos_fsx_keys - the keyboard, polled. CF=1 = leave the bracket -----------
; int 16h directly, because no events are dispatched in here (SPEC.md 53.1) -
; and every other key is the console's, exactly as it is windowed. It cannot
; DRAW, though: dos_con_key ends in dos_con_draw, which is a kernel drawing
; slot and off-limits in a foreign text mode. [con_drb] is what carries the
; change across, and dos_fsx_owed below is what spends it.
dos_fsx_keys:
    push ax
.next:
    mov ah, 1
    int 0x16
    jz .none
    xor ah, ah
    int 0x16
    cmp al, 27
    je .quit
    call dos_con_key                ; THE SAME HANDLER, and it draws nothing:
    jmp short .next                 ; [dos_fsxup] stands dos_con_draw down and
                                    ; the marks it leaves are what dos_fsx_owed
                                    ; spends. One prompt, one line editor, two
                                    ; screens
.none:
    pop ax
    clc
    ret
.quit:
    pop ax
    stc
    ret

; --- dos_fsx_owed - the scroll, then the rows the bitmap names, then the pen -
dos_fsx_owed:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    cld
    call con_tx_scroll              ; ...FIRST: the rows below are written on
    xor bx, bx                      ; top of the cells this moves
.row:
    call con_takerow
    jnc .next
    call con_tx_row
.next:
    inc bx
    cmp bx, CON_ROWS
    jb .row
    call con_tx_cursor
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

dos_c_leave: db ' Esc to leave', 0
