; =============================================================================
; os8088 - apps/dos/dos.asm
;
; DOS (SPEC.md 96) - run a DOS .COM or .EXE program.
;
; NOT AN EMULATOR. This machine is an 8086 in real mode and a DOS .COM is
; machine code for the processor already running, so nothing here interprets
; anything: the package builds the memory a DOS program expects, points
; INT 21h at code of its own, and far-jumps in. What it provides is the
; operating SYSTEM the program calls, not the processor it runs on.
;
; WAVE 1 (docs/plans/DOS-EXEC-PLAN.md 11): .COM only, read-only file access,
; INT 20h and INT 21h AH=00h/02h/09h/30h/4Ch. Everything else refuses with
; DOS's own "invalid function" rather than hanging, and the window names the
; function that was asked for - SPEC.md 47's refusal, so an unsupported
; program reports its own gap.
;
; THE ORDER IN dos_run IS BINDING (SPEC.md 96.2). The disk read happens in
; the wake handler's own lock-free context, because file slots are legal
; there and a floppy read under the gfx lock is the freeze SPEC.md 7.4
; exists to avoid; the lock is taken only for the bracket itself.
;
; EVERY KERNEL FILE CALL GOES THROUGH dos_be (SPEC.md 96.4). It is one
; near-call table today with one implementation, and it is here from the
; first line because docs/plans/DOS-EXEC-PLAN.md 14 wants a mode where the
; kernel is hibernated out and the file half is served by something else. A
; table makes that a second back end; direct calls would make it a rewrite
; of every file function.
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'DOS', dos_entry, 3     ; flags bit 0 = icon, bit 1 = the
                                        ; association block after it

; --- the icon (SPEC.md 20.2/20.5) -------------------------------------------
; A CRT on a stand with a `>` prompt and a cursor under it. It is 1bpp and
; reads the same on all three adapters, which is what SPEC.md 39.4 asks of a
; drawing - and it is what a .COM and a .EXE WEAR, because SPEC.md 54.1
; composes a document's icon out of its program's. An iconless package would
; leave every DOS program on a disk showing assoc_compose's bare page, and
; tools/os88mini.py refuses to bake a default glyph from one at all.
    OS88_ICON16
    dw 0x0000, 0x7FFE, 0x7FFE, 0x7FFE, 0x7FFE, 0x7FFE, 0x7FFE, 0x7FFE
    dw 0x7FFE, 0x7FFE, 0x7FFE, 0x03C0, 0x03C0, 0x1FF8, 0x0000, 0x0000
    dw 0x0000, 0x7FFE, 0x4002, 0x4002, 0x5002, 0x4802, 0x5002, 0x4002
    dw 0x5F02, 0x4002, 0x7FFE, 0x03C0, 0x03C0, 0x1FF8, 0x0000, 0x0000
    OS88_ICON16_END

    OS88_ASSOC16
    db 2
    OS88_ASSOC_EXT 'COM'
    OS88_ASSOC_EXT 'EXE'
    OS88_ASSOC16_END

DOS_CONT_W  equ 286                 ; content width:  288 outer - 2px borders
DOS_CONT_H  equ 81                  ; content height: 100 outer - TITLE_H - 1

DOS_MIN_KB  equ 64                  ; a machine that cannot offer this much has
                                    ; nothing worth running a DOS program in,
                                    ; and saying so is cheaper than a program
                                    ; that dies on its first allocation

; --- the arena's shape, in PARAGRAPHS (SPEC.md 96.3) -------------------------
DOS_ENVP    equ 8                   ; 128 bytes of environment block
DOS_ENVMCB  equ 0                   ; para 0     : the environment's MCB
DOS_ENVSEG  equ 1                   ; para 1     : the environment itself
DOS_PRGMCB  equ DOS_ENVSEG+DOS_ENVP ; para 9     : the program's MCB ('Z')
DOS_PSPP    equ DOS_PRGMCB+1        ; para 10    : the PSP
DOS_IMGP    equ DOS_PSPP+16         ; para 26    : the image, at PSP:0100

; --- state -------------------------------------------------------------------
DST_IDLE    equ 0                   ; launched with no document (wave 7's prompt)
DST_READY   equ 1                   ; a program is named and not yet run
DST_RAN     equ 2                   ; it ran; [dos_exit] is its code
DST_ERR     equ 3                   ; it did not; [dos_err] says why

; --- why it did not ----------------------------------------------------------
DER_GOTO    equ 0
DER_MEM     equ 1
DER_READ    equ 2
DER_BIG     equ 3
DER_FSX     equ 4
DER_EXE     equ 5

; -----------------------------------------------------------------------------
; dos_entry - package entry (SPEC.md 20.2)
; in:  DS=ES=KERNEL_SEG, IF=1, gfx lock NOT held
; out: BX = window ptr, CF clear
;
; ARG_FILE is READ-AND-CLEAR and its name lives in the KERNEL segment, so it
; is copied out through ES before anything else is called (SPEC.md 54.5).
; -----------------------------------------------------------------------------
dos_entry:
    push ax
    push cx
    push dx
    push si
    push di

    mov si, dos_tpl
    call OSAPI_WM_CREATE
    jc .out
    mov [dos_win], bx

    mov ax, dos_wake
    call OSAPI_WM_ONWAKE
    mov si, dos_about
    call OSAPI_ABOUT_SET

    call OSAPI_ARG_FILE             ; CF=1 = launched empty, the ordinary case
    jc .idle                        ; for every package and the COMMAND.COM
                                    ; door for this one (wave 7)
    mov [dos_dir], dx
    mov [dos_vol], bl
    mov di, dos_name                ; copy the name out of KERNEL_SEG first:
    mov cx, 13                      ; ES is the kernel's here and the next call
.cp:                                ; is free to move what SI points at
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    or al, al
    loopnz .cp

    mov byte [dos_state], DST_READY
    mov bx, [dos_win]
    call OSAPI_WM_WAKE              ; ...and run it from the wake handler, which
    jmp short .ok                   ; is the one callback without the gfx lock.
                                    ; CF=1 here means the ring was FULL and
                                    ; nothing was posted - not an error, and the
                                    ; SDK's own remedy is to kick again from the
                                    ; next callback, which dos_paint does. It
                                    ; is not hypothetical: a launch that had to
                                    ; SWEEP VOLUMES to find this package
                                    ; (SPEC.md 54.4.2) fills the ring with the
                                    ; mounts on the way, and the symptom is a
                                    ; window that sits on "Starting..." for ever

.idle:
    mov byte [dos_state], DST_IDLE
.ok:
    mov bx, [dos_win]
    clc
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_wake - the OSAPI_WM_ONWAKE handler (SPEC.md 74.1)
; in:  SI = our window, UI task, gfx lock NOT held
; out: nothing
;
; A wake is a KICK and a stale one is possible, so the state byte is advanced
; BEFORE the run: a second wake arriving for any reason finds DST_RAN and
; does nothing, rather than launching the program twice.
; -----------------------------------------------------------------------------
dos_wake:
    cmp byte [dos_state], DST_READY
    jne .out
    mov byte [dos_state], DST_RAN
    call dos_run
.out:
    ret

; -----------------------------------------------------------------------------
; dos_run - navigate, claim, load, and take the machine
; in:  nothing; UI task, lock NOT held
; out: nothing; [dos_state] and [dos_exit]/[dos_err] are the answer
; -----------------------------------------------------------------------------
dos_run:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es

    mov dx, [dos_dir]               ; ...stand where the file is (SPEC.md 19.2.1
    mov bl, [dos_vol]               ; put us there already, but a quiet GOTO is
    call dos_be_goto                ; what makes that true after any navigation)
    jnc .there
    mov al, DER_GOTO
    jmp short .err
.there:

    call OSAPI_MEM_AVAIL            ; AX = the largest run a claim can HAVE -
    cmp ax, DOS_MIN_KB              ; already net of every purgeable cache and
    jb .nomem                       ; of what a compaction would recover
                                    ; (SPEC.md 50.6.3, 66.10.3). There is
                                    ; nothing to compute and nothing to probe
    mov [dos_akb], ax               ; BANKED: the claim's answer is DX and the
                                    ; slot promises nothing about AX, so the KB
                                    ; figure has to survive the call somewhere
                                    ; other than in a register
    call OSAPI_MEM_CLAIM_HI         ; AX = KB -> DX = base segment
    jnc .got
.nomem:
    mov al, DER_MEM
    jmp short .err
.got:
    mov [dos_arena], dx
    mov ax, [dos_akb]
    mov cl, 6
    shl ax, cl                      ; KB -> paragraphs, and AX < 1024 always
    mov [dos_apara], ax             ; (640KB is 640), so this cannot carry

    call dos_load                   ; the image, through the back end
    jc .freeerr
    call dos_is_exe                 ; ...and only NOW, because the answer is in
    jnc .isCOM                      ; the FILE and not in its name
    mov al, DER_EXE
    jmp short .freeerr
.isCOM:

    call OSAPI_GFX_LOCK             ; ...and only NOW, because fsx_run wants it
    mov ax, dos_fsx_main            ; held and nothing above this may pay for it
    mov bx, [dos_win]
    xor cx, cx                      ; no FSXF_KEEPWORKER: there is no worker
    call OSAPI_FSX_RUN
    pushf
    call OSAPI_GFX_UNLOCK
    popf
    jnc .ran
    mov al, DER_FSX
    jmp short .freeerr
.ran:
    mov byte [dos_state], DST_RAN
    jmp short .free
.freeerr:
    mov [dos_err], al
    mov byte [dos_state], DST_ERR
.free:
    mov dx, [dos_arena]
    or dx, dx
    jz .out
    call OSAPI_MEM_FREE
    mov word [dos_arena], 0
    jmp short .out
.err:
    mov [dos_err], al
    mov byte [dos_state], DST_ERR
.out:
    call dos_repaint                ; THE WINDOW DOES NOT REPAINT ITSELF. On the
                                    ; path that runs, fsx_restore's wm_paint_all
                                    ; (SPEC.md 53.6) happens to redraw us and
                                    ; the exit code appears - so every FAILURE
                                    ; path silently left "Starting..." on the
                                    ; glass while the real reason sat in
                                    ; [dos_err] where nobody could see it. That
                                    ; is the worst shape a refusal can have
                                    ; (SPEC.md 47): the state was right and the
                                    ; screen was a lie
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_repaint - the content, under a lock WE take
; in:  nothing; the wake handler's context, gfx lock NOT held (SPEC.md 74.1)
; out: nothing; preserves all registers
; -----------------------------------------------------------------------------
dos_repaint:
    push ax
    push bx
    push cx
    push dx
    push si
    call OSAPI_GFX_LOCK             ; a wake handler is the one callback
    mov si, [dos_win]               ; without the lock, and it MAY take it for
    mov bx, si                      ; a burst it can state (SPEC.md 74.1)
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top
    mov bx, dx
    mov cx, ax
    add cx, DOS_CONT_W - 1
    add dx, DOS_CONT_H - 1
    mov al, CWHITE
    call OSAPI_SET_COLOR
    call OSAPI_GFX_FILL             ; AX = x1 already, BX = y1
    mov si, [dos_win]
    call dos_paint
    call OSAPI_GFX_UNLOCK
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_is_exe - is the loaded image an .EXE?
; in:  the image is already in the arena at PSP:0100
; out: CF=1 yes; preserves everything but the flags
;
; THE SIGNATURE DECIDES, NOT THE EXTENSION, and that is DOS's own rule rather
; than a simplification of it: INT 21h AH=4Bh reads the header and loads an
; MZ (or the rarer ZM) as a relocatable .EXE and ANYTHING ELSE as a .COM at
; PSP:0100, whatever the file is called. The extension only drives
; COMMAND.COM's search order when a bare name is typed.
;
; This is not a corner: SOPWITH2.EXE - a period game, verified on real
; hardware - has NO MZ header at all. It is a Microsoft-C-style .COM whose
; first instructions read PSP:0002 and set DS past the code, and it is named
; .EXE. Dispatching on the name refuses a file DOS runs, and this routine used
; to do exactly that, under a comment asserting the opposite rule.
; -----------------------------------------------------------------------------
dos_is_exe:
    push ax
    push es
    mov ax, [dos_arena]
    add ax, DOS_IMGP
    mov es, ax
    mov ax, [es:0]
    cmp ax, 0x5A4D                  ; 'MZ'
    je .yes
    cmp ax, 0x4D5A                  ; 'ZM' - the same header, byte-swapped,
    je .yes                         ; which a few very early linkers emitted
    pop es
    pop ax
    clc
    ret
.yes:
    pop es
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; dos_load - read the program into the arena at PSP:0100
; in:  [dos_arena], [dos_apara], [dos_name]
; out: CF=0 and [dos_imgsz] = the bytes; CF=1 with AL = a DER_*
; -----------------------------------------------------------------------------
dos_load:
    push bx
    push cx
    push dx
    push si
    push es

    mov ax, [dos_arena]
    add ax, DOS_IMGP
    mov es, ax                      ; ES:0 is PSP:0100
    xor bx, bx

    mov ax, [dos_apara]             ; the capacity is everything from the image
    sub ax, DOS_IMGP                ; to the top of the claim, in paragraphs...
    mov dx, 16
    mul dx                          ; ...as a 32-bit byte count in DX:AX, which
    mov cx, ax                      ; is what OSAPI_FILE_READ takes in DX:CX
    mov si, dos_name
    call dos_be_read                ; DX:AX = bytes read
    jc .rerr

    or dx, dx                       ; a .COM is one segment: 64KB - 256 - 2 is
    jnz .toobig                     ; the ceiling, so a high word at all is a
    cmp ax, 0xFF00                  ; file that cannot be one
    ja .toobig
    mov [dos_imgsz], ax
    pop es
    pop si
    pop dx
    pop cx
    pop bx
    clc
    ret
.toobig:
    mov al, DER_BIG
    jmp short .out
.rerr:
    mov al, DER_READ
.out:
    pop es
    pop si
    pop dx
    pop cx
    pop bx
    stc
    ret


; =============================================================================
; THE BRACKET (SPEC.md 96.2)
; =============================================================================
; -----------------------------------------------------------------------------
; dos_fsx_main - the fullscreen bracket's body
; in:  SI = our window ptr, DS = CS = our segment, ES = KERNEL_SEG, task 0,
;      the gfx lock HELD; a near proc with a near ret (SPEC.md 53.1)
; out: nothing
;
; THE FSX_MODE CALL IS NOT OPTIONAL. fsx_restore skips vid_setmode when no
; mode was ever set (SPEC.md 53.6), and a DOS program sets its own through
; the ROM behind our back - so without this the desktop comes back into
; whatever mode the program left it in.
; -----------------------------------------------------------------------------
dos_fsx_main:
    ; STKBALANCE-OK: the `retf` below is a JUMP INTO THE PROGRAM and not a
    ; return - the two words under it are the far address of PSP:0000 that a
    ; .COM is entered with, placed on the PROGRAM's stack and consumed by the
    ; program's own exit. Control comes back to dos_prog_done, which is
    ; INSIDE this routine, after dos_terminate has restored SS:SP; so the
    ; `ret` that ends it really is at entry depth, and the walker is counting
    ; a frame that belongs to a different stack.
    push ds
    pop es                          ; FSI is ours, and OSAPI_FSX_MODE takes
    mov di, dos_fsi                 ; ES:DI like every other buffer slot
    mov al, FSXM_TEXT80
    call OSAPI_FSX_MODE
                                    ; a refusal is survivable: the screen is
                                    ; already the desktop's mode and the
                                    ; program will draw on it. Not worth
                                    ; abandoning the run for

    call dos_save_machine
    call dos_build_psp
    call dos_hook_vectors

    ; --- into the program --------------------------------------------------
    ; SS:SP is banked in OUR segment, reached through CS by the INT 21h
    ; terminate path, which runs on the program's stack with DS unknown.
    mov ax, ss
    mov [dos_sv_ss], ax
    mov [dos_sv_sp], sp

    mov ax, [dos_arena]
    add ax, DOS_PSPP
    mov bx, [dos_prgsp]
    cli                             ; SS and SP are loaded as a pair, always:
    mov ss, ax                      ; an interrupt between them lands on a
    mov sp, bx                      ; stack that is half of each
    sti
    mov ds, ax                      ; a .COM is entered with every segment
    mov es, ax                      ; register on the PSP (SPEC.md 96.3)
    push ax                         ; ...and at PSP:0100, NOT PSP:0000 - the
    mov ax, 0x100                   ; first 256 bytes ARE the PSP and its first
    push ax                         ; two bytes are the CD 20 that a program's
    retf                            ; own `ret` lands on. Pushing 0 here jumps
                                    ; straight into that INT 20h, and what it
                                    ; looks like is a program that ran and
                                    ; exited with code 0 having printed nothing
                                    ; - which is indistinguishable, from the
                                    ; outside, from a program that does that

dos_prog_done:                      ; the INT 21h terminate path jumps here,
                                    ; having already put SS:SP back
    call dos_unhook_vectors
    call dos_restore_machine
    ret

; =============================================================================
; THE MACHINE-STATE LEDGER (SPEC.md 96.5)
; =============================================================================
; The saves land in OUR OWN BSS and never in the arena: the arena is the
; program's to scribble on, and a save area the program can corrupt is worse
; than none, because it fails at restore time when nothing can be done.
; -----------------------------------------------------------------------------
dos_save_machine:
    push ax
    push cx
    push si
    push di
    push ds
    push es

    cld
    xor ax, ax                      ; the whole IVT. A list of vectors to
    mov ds, ax                      ; remember would be wrong for the ones we
    push cs                         ; do not know about, and a DOS program
    pop es                          ; hooks vectors as a matter of routine
    xor si, si
    mov di, dos_ivt
    mov cx, 512
    rep movsw

    mov ax, 0x40                    ; ...and the whole BDA, saved so the list
    mov ds, ax                      ; that comes BACK can be audited against
    xor si, si                      ; what actually changed
    mov di, dos_bda
    mov cx, 128
    rep movsw

    push cs
    pop ds
    in al, 0x21                     ; the 8259 masks: a program that masks IRQs
    mov [dos_pic1], al              ; and does not put them back leaves us with
    in al, 0xA1                     ; no timer
    mov [dos_pic2], al

    pop es
    pop ds
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_restore_machine - the named list, and the four bytes that are ZEROED
; -----------------------------------------------------------------------------
dos_restore_machine:
    push ax
    push cx
    push dx
    push si
    push di
    push ds
    push es

    cld
    push cs
    pop ds
    mov al, [dos_pic1]              ; the masks first: everything below runs
    out 0x21, al                    ; with the machine's own interrupt set back
    mov al, [dos_pic2]
    out 0xA1, al

    mov al, 0x36                    ; PIT channel 0 back to the kernel's rate.
    out 0x43, al                    ; A program that wanted a fast timer took
    xor al, al                      ; the scheduler's quantum with it
    out 0x40, al
    out 0x40, al

    mov ax, 0x40                    ; --- the BDA's named list (SPEC.md 96.5) -
    mov es, ax
    mov si, dos_bdalist
.bda:
    mov di, [si]                    ; offset in the BDA, 0xFFFF ends the list
    cmp di, 0xFFFF
    je .bdadone
    mov cx, [si+2]                  ; bytes, always even
    add si, 4
    push si
    mov si, di
    add si, dos_bda                 ; ...from our own copy
    shr cx, 1
    rep movsw
    pop si
    jmp short .bda
.bdadone:
    xor ax, ax                      ; the keyboard flag bytes are ZEROED and
    mov [es:0x17], ax               ; not restored: they say which keys are
    mov [es:0x96], ax               ; HELD, and the honest answer on the way
                                    ; back is that none is. A restored phantom
                                    ; Ctrl makes every menu behave oddly until
                                    ; the user happens to press and release it,
                                    ; and a stuck ScrollLock silently disables
                                    ; the keypad-5 mouse hatch (SPEC.md 9.6.4)

    xor ax, ax                      ; --- and the IVT LAST, under cli ---------
    mov es, ax                      ; nothing below may take an interrupt
    mov si, dos_ivt                 ; through a half-restored table
    xor di, di
    mov cx, 512
    cli
    rep movsw
    sti

    pop es
    pop ds
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_hook_vectors / dos_unhook_vectors
;
; The unhook is a no-op by design: dos_restore_machine puts the WHOLE IVT
; back, which covers our own vectors and every one the program installed. It
; is a named step so the bracket reads in the order it happens.
; -----------------------------------------------------------------------------
dos_hook_vectors:
    push ax
    push bx
    push es
    xor ax, ax
    mov es, ax
    cli
    mov word [es:0x20*4], dos_int20     ; terminate, the CP/M door
    mov [es:0x20*4+2], cs
    mov word [es:0x21*4], dos_int21     ; ...and the one that matters
    mov [es:0x21*4+2], cs
    mov word [es:0x22*4], dos_int22     ; terminate address - a program may read
    mov [es:0x22*4+2], cs               ; it out of its own PSP
    mov word [es:0x23*4], dos_iret      ; Ctrl-Break
    mov [es:0x23*4+2], cs
    mov word [es:0x24*4], dos_int24     ; critical error: FAIL, never retry
    mov [es:0x24*4+2], cs
    sti

    mov ax, [dos_arena]                 ; ...and INT 12h's own source, so "how
    add ax, [dos_apara]                 ; much memory is there" agrees with the
    mov bx, 0x40                        ; PSP and the MCB chain (SPEC.md 96.3).
    mov es, bx                          ; Safe because the kernel reads int 12h
    mov cl, 6                           ; exactly twice in the tree - once at
    shr ax, cl                          ; boot, once in the Task Manager, which
    mov [es:0x13], ax                   ; cannot run inside a bracket
    pop es
    pop bx
    pop ax
    ret

dos_unhook_vectors:
    ret

dos_iret:
    iret

dos_int24:                              ; DOS's critical-error contract: AL = 3
    mov al, 3                           ; is FAIL, which turns a dead drive into
    iret                                ; a failed call instead of an "Abort,
                                        ; Retry, Fail?" nobody can answer

; =============================================================================
; THE ARENA (SPEC.md 96.3)
; =============================================================================
; -----------------------------------------------------------------------------
; dos_build_psp - the MCB chain, the environment and the PSP
; in:  [dos_arena], [dos_apara], [dos_imgsz]
; out: [dos_prgsp] = the program's initial SP; preserves nothing but segments
;
; Two blocks, because a .COM is given everything: an 'M' for the environment
; and a 'Z' for the program, which runs to the top of the claim. PSP:0002 is
; the paragraph past it, which is the first of the four ways a DOS program
; asks how much memory it has (docs/plans/DOS-EXEC-PLAN.md 2.1).
; -----------------------------------------------------------------------------
dos_build_psp:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es

    cld
    mov dx, [dos_arena]

    ; --- the environment's MCB, and the environment --------------------------
    mov ax, dx
    mov es, ax
    xor di, di
    mov al, 'M'                     ; 'M' = a block with another after it
    stosb
    mov ax, dx
    add ax, DOS_PSPP
    stosw                           ; owner: the PSP that owns it
    mov ax, DOS_ENVP
    stosw                           ; size, in paragraphs
    mov cx, 11                      ; the three reserved bytes and the 8-byte
    xor al, al                      ; name field DOS 4 added - zeroed, which is
    rep stosb                       ; what a block with no name looks like

    mov ax, dx                      ; the environment itself: one NUL for an
    add ax, DOS_ENVSEG              ; empty set of variables, a second to end
    mov es, ax                      ; the set, then the count word and the
    xor di, di                      ; program's own path, which is what DOS 3+
    xor al, al                      ; puts there and what a program looks for
    stosb                           ; when it wants to know where it came from
    stosb
    mov ax, 1
    stosw
    mov si, dos_name                ; ...as a bare 8.3 name for now: a real
.env:                               ; path needs the walk of SPEC.md 96 that
    lodsb                           ; wave 1 does not have yet
    stosb
    or al, al
    jnz .env

    ; --- the program's MCB ---------------------------------------------------
    mov ax, dx
    add ax, DOS_PRGMCB
    mov es, ax
    xor di, di
    mov al, 'Z'                     ; 'Z' = the last block in the chain
    stosb
    mov ax, dx
    add ax, DOS_PSPP
    stosw
    mov ax, [dos_apara]
    sub ax, DOS_PSPP                ; everything from the PSP to the top
    stosw
    mov cx, 11
    xor al, al
    rep stosb

    ; --- the PSP -------------------------------------------------------------
    mov ax, dx
    add ax, DOS_PSPP
    mov es, ax
    xor di, di
    mov cx, 128                     ; zero it first: every field this does not
    xor ax, ax                      ; set is a field a program may read, and
    rep stosw                       ; zero is the answer DOS leaves in most

    mov word [es:0x00], 0x20CD      ; INT 20h, so a .COM that plain `ret`s
                                    ; lands here and terminates
    mov ax, [dos_arena]
    add ax, [dos_apara]
    mov [es:0x02], ax               ; the paragraph past the block - mechanism 1

    mov byte [es:0x05], 0x9A        ; the CP/M-style far call to the dispatcher
    mov word [es:0x0A], dos_int22   ; the terminate address, which DOS copies
    mov [es:0x0C], cs               ; out of the vectors it is about to hook
    mov word [es:0x0E], dos_iret
    mov [es:0x10], cs
    mov word [es:0x12], dos_int24
    mov [es:0x14], cs
    mov word [es:0x2C], dx          ; the environment segment...
    add word [es:0x2C], DOS_ENVSEG
    mov word [es:0x50], 0x21CD      ; INT 21h / RETF, the DOS 2+ call gate
    mov byte [es:0x52], 0xCB
    mov byte [es:0x80], 0           ; an empty command tail, and the 0Dh that
    mov byte [es:0x81], 0x0D        ; terminates it - a program that parses its
                                    ; own arguments must find the terminator
    mov word [es:0x5C], 0           ; the two FCBs stay zeroed, which is what
    mov word [es:0x6C], 0           ; an empty tail parses to

    ; --- the stack -----------------------------------------------------------
    mov ax, [dos_apara]             ; a .COM gets SP at the top of its own
    sub ax, DOS_PSPP                ; 64KB when the block holds one, and the
    cmp ax, 0x1000                  ; top of the block when it does not
    jb .small
    mov bx, 0xFFFE
    jmp short .sp
.small:
    mov cl, 4
    shl ax, cl
    sub ax, 2
    mov bx, ax
.sp:
    sub bx, 2                       ; ...and the 0 word DOS pushes, which is
    mov [dos_prgsp], bx             ; the offset half of that PSP:0000 return
    mov word [es:bx], 0

    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; INT 20h / INT 21h (SPEC.md 96.7)
; =============================================================================
; Entered on the PROGRAM's stack with the program's segment registers, so the
; first thing either does is reach its own data through CS.
;
; The carry flag a DOS call returns is the one in the FLAGS image the `int`
; pushed, not the live one, so the refusal path edits [bp+8] rather than
; executing `stc` - which the `iret` would discard.
; -----------------------------------------------------------------------------
dos_int20:
    xor al, al                      ; INT 20h is AH=4Ch with a zero code, and
    jmp dos_terminate               ; DOS treats them as the same exit

dos_int22:                          ; the terminate ADDRESS: a child process
    xor al, al                      ; returning here is an exit too, and wave 1
    jmp dos_terminate               ; has no children to send

dos_int21:
    sti                             ; DOS runs its calls with interrupts on
    push bp
    push ds
    mov bp, sp                      ; [bp]=bp [bp+2]=ds [bp+4]=IP [bp+6]=CS
    push cs                         ; [bp+8]=FLAGS, all on the PROGRAM's stack
    pop ds

    cmp ah, 0x4C
    je .term
    cmp ah, 0x00
    je .term
    cmp ah, 0x02
    je .putc
    cmp ah, 0x09
    je .puts
    cmp ah, 0x30
    je .ver
    cmp ah, 0x01
    je .getce
    cmp ah, 0x07
    je .getc
    cmp ah, 0x08
    je .getc
    cmp ah, 0x0B
    je .kbhit
    jmp .bad

.term:
    pop ds
    pop bp
    jmp dos_terminate               ; AL is already the exit code

.putc:
    mov al, dl
    call dos_tty
    jmp short .ok

.puts:
    pop ds                          ; the string is the PROGRAM's, at DS:DX -
    push ds                         ; so its DS is what addresses it, not ours
    push si
    mov si, dx
.sloop:
    mov al, [si]
    cmp al, '$'
    je .sdone
    inc si
    call dos_tty
    jmp short .sloop
.sdone:
    pop si
    jmp short .ok

.getce:
    call dos_getkey                 ; AH=01h echoes what it read; AH=07h and
    push ax                         ; AH=08h do not, and 07h additionally does
    call dos_tty                    ; not check for Ctrl-Break - a distinction
    pop ax                          ; wave 1 has nothing to make
    jmp short .ok
.getc:
    call dos_getkey
    jmp short .ok
.kbhit:
    mov ah, 1                       ; AH=0Bh: FFh if a character is waiting,
    int 0x16                        ; 00h if not - the poll a program spins on
    mov al, 0
    jz .khdone
    mov al, 0xFF
.khdone:
    jmp short .ok

.ver:
    mov ax, 0x1F03                  ; AL = 3, AH = 31: DOS 3.31. The version is
    mov bx, 0                       ; a SETTING and not a constant the day a
    mov cx, 0                       ; program wants 5.00 - reporting a version
    jmp short .ok                   ; whose functions we lack is worse than
                                    ; reporting a lower one, because a program
                                    ; branches on it (DOS-EXEC-PLAN 12 q1)

.bad:
    mov [dos_badfn], ah             ; the window NAMES it (SPEC.md 47): an
    mov ax, 1                       ; unsupported program reports its own gap
    or word [bp+8], 1               ; CF=1 in the RETURNED flags
    pop ds
    pop bp
    iret
.ok:
    and word [bp+8], 0xFFFE         ; CF=0 in the returned flags
    pop ds
    pop bp
    iret

; -----------------------------------------------------------------------------
; dos_terminate - back to the bracket, on our own stack
; in:  AL = the exit code; running on the PROGRAM's stack
; out: never returns
; -----------------------------------------------------------------------------
dos_terminate:
    cli
    mov [cs:dos_exit], al           ; through CS: DS is the program's and the
    mov ax, [cs:dos_sv_ss]          ; stack is about to stop existing
    mov ss, ax
    mov sp, [cs:dos_sv_sp]
    sti
    push cs                         ; ...and back into dos_fsx_main's flow with
    pop ds                          ; our own DS, which every proc below wants
    jmp dos_prog_done

; -----------------------------------------------------------------------------
; dos_tty - one character to the screen, through the ROM
; in:  AL = the character
; out: nothing; preserves everything but the flags
; -----------------------------------------------------------------------------
; -----------------------------------------------------------------------------
; dos_getkey - one character from the ROM
; in:  nothing; out: AL = the character (0 for an extended key's first half)
; -----------------------------------------------------------------------------
dos_getkey:
    push bx
    xor ah, ah
    int 0x16                        ; AL = the character, AH = the scan code.
    pop bx                          ; An extended key answers AL = 0 and DOS
    ret                             ; makes the caller ask twice for the scan;
                                    ; wave 1 hands back the 0 and no more

dos_tty:
    push ax
    push bx
    mov ah, 0x0E                    ; the ROM's teletype: it scrolls, it wraps,
    mov bx, 0x0007                  ; and it is what a DOS program's output
    int 0x10                        ; goes through when it is not writing the
    pop bx                          ; framebuffer itself
    pop ax
    ret

; =============================================================================
; THE BACK END (SPEC.md 96.4)
; =============================================================================
; One near-call table, one implementation. It is here from the first line
; because docs/plans/DOS-EXEC-PLAN.md 14 wants a mode in which the kernel is
; hibernated out and the file half is served by something else; a table makes
; that a second back end where direct calls would make it a rewrite of every
; file function. The system already does this twice one layer down - DSV_BLK
; for a volume's blocks (SPEC.md 18.7) and DSV_FS for a whole file system
; (SPEC.md 51.8) - and this is the same want one layer up.
;
; NO INT 21h HANDLER MAY CALL AN OSAPI_* FILE SLOT DIRECTLY. That is the
; whole discipline, and it is the only thing wave 1 owes the later phase.
; -----------------------------------------------------------------------------
DBE_GOTO    equ 0                   ; DX = dir cluster, BL = volume
DBE_READ    equ 2                   ; SI = name, ES:BX = buffer, DX:CX = cap
DBE_NENT    equ 2

dos_be_goto:
    jmp word [dos_be + DBE_GOTO]

dos_be_read:
    jmp word [dos_be + DBE_READ]

; --- the os8088 implementation ------------------------------------------------
dos_k_goto:
    call OSAPI_FILE_GOTO_QM         ; QM AND NOT Q, and the difference is the
    ret                             ; whole of whether this works when the
                                    ; handler is on a different volume from the
                                    ; document. GOTO_Q moves the MACHINE and not
                                    ; the INSTANCE, and the SDK says what that
                                    ; costs in as many words: "GOTO_Q alone is
                                    ; undone by that next cell, which first
                                    ; re-stands the machine in your instance's
                                    ; folder". Our instance stands where
                                    ; assoc_locate found DOS.O88 - A:\APPS on a
                                    ; cross-volume launch - so the read looked
                                    ; for the program THERE. It worked at all
                                    ; only while the handler happened to sit
                                    ; beside the document, which is the one
                                    ; arrangement a gate disk naturally has

dos_k_read:
    call OSAPI_FILE_READ
    ret

; =============================================================================
; THE WINDOW
; =============================================================================
; -----------------------------------------------------------------------------
; dos_paint - W_PAINT
; in:  SI = window ptr; the gfx lock is held
; out: nothing; preserves all registers
; -----------------------------------------------------------------------------
dos_paint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    cmp byte [dos_state], DST_READY  ; THE RE-KICK (SPEC.md 74.1): the kernel
    jne .nokick                      ; keeps at most one queued wake per window,
    mov bx, si                       ; so this is free when one is already
    call OSAPI_WM_WAKE               ; waiting and is the difference between a
.nokick:                             ; full ring costing a frame and costing
                                     ; the whole launch
    mov bx, si
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top
    mov bx, ax
    add bx, 8
    add dx, 10

    mov di, dos_l_idle              ; one line per state, and the second line
    mov si, dos_l2_idle             ; is the detail
    cmp byte [dos_state], DST_READY
    jne .notready
    mov di, dos_l_ready
    mov si, dos_l2_ready
.notready:
    cmp byte [dos_state], DST_RAN
    jne .notran
    mov di, dos_l_ran
    mov si, dos_l2_ran
    call dos_fmt_exit
.notran:
    cmp byte [dos_state], DST_ERR
    jne .noterr
    mov di, dos_l_err
    call dos_err_line               ; SI = the reason
.noterr:

    push si
    mov si, di
    call dos_line
    pop si
    add dx, 12
    call dos_line
    add dx, 14
    mov si, dos_name                ; ...and the program's own name last, which
    cmp byte [dos_state], DST_IDLE  ; is the thing the user recognises
    je .out
    call dos_line
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_line - one opaque run at BX, DX
; in:  SI = NUL string, BX = x, DX = y
; out: nothing; preserves all registers
;
; font_run and not a fill-then-letter pair: one pass draws the ground and the
; glyphs, so the line is never momentarily blank (SPEC.md 6.1).
; -----------------------------------------------------------------------------
dos_line:
    push ax
    push cx
    push dx
    mov cx, bx
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_fmt_exit - stamp the exit code into dos_l2_ran
; in:  nothing; out: SI = the line
; -----------------------------------------------------------------------------
dos_fmt_exit:
    push ax
    push di
    mov al, [dos_exit]
    mov di, dos_exitd
    xor ah, ah
    mov cl, 100
    div cl                          ; AL = hundreds, AH = the rest
    add al, '0'
    mov [di], al
    mov al, ah
    xor ah, ah
    mov cl, 10
    div cl
    add al, '0'
    mov [di+1], al
    add ah, '0'
    mov [di+2], ah
    mov si, dos_l2_ran
    pop di
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_err_line - SI = the sentence for [dos_err]
; -----------------------------------------------------------------------------
dos_err_line:
    push ax
    push bx
    mov al, [dos_err]
    xor ah, ah
    shl ax, 1
    mov bx, ax
    mov si, [dos_errs + bx]
    cmp byte [dos_err], DER_FSX     ; the unsupported-function case borrows the
    jne .out                        ; refusal line and stamps the number, so
    call dos_fmt_fn                 ; "it asked for AH=3Dh" is on the glass
.out:
    pop bx
    pop ax
    ret

dos_fmt_fn:
    push ax
    push di
    mov al, [dos_badfn]
    mov di, dos_fnd
    mov ah, al
    shr al, 1
    shr al, 1
    shr al, 1
    shr al, 1
    call dos_hexd
    mov [di], al
    mov al, ah
    and al, 0x0F
    call dos_hexd
    mov [di+1], al
    mov si, dos_e_fn
    pop di
    pop ax
    ret

dos_hexd:
    add al, '0'
    cmp al, '9'
    jbe .out
    add al, 7
.out:
    ret

; -----------------------------------------------------------------------------
; dos_about - the standard About card's handler (SPEC.md 12.2, 20.5.1)
; -----------------------------------------------------------------------------
dos_about:
    ret

; =============================================================================
; DATA
; =============================================================================
dos_tpl:
    dw 120, 110, 288, 100           ; x, y, w, h
    dw dos_ttl, dos_paint, 0, 0     ; no onkey, no onclick: wave 1 has nothing
                                    ; to click and the bracket owns the keys

dos_ttl:    db 'DOS', 0

dos_be:                             ; the table, in DBE_* order
    dw dos_k_goto
    dw dos_k_read

; --- the BDA's RESTORE list (SPEC.md 96.5): offset, bytes, 0xFFFF ends it ----
; Every span here is a field the KERNEL reads, or one whose stale value would
; point the ROM at memory we are about to free. Everything absent is absent on
; purpose, and the two that matter are 0040:003F (the floppy motor state
; dsk_fdd_probe calls the only place the current state exists) and 0040:006C
; (the tick spl_clock and SOUND.DRV's pm_ticks read) - restoring either would
; hand a live reader a statement that is not true of the machine.
dos_bdalist:
    dw 0x0000, 16                   ; COM and LPT port tables - NET.DRV finds
                                    ; the parallel port through the LPT half
    dw 0x0010, 2                    ; the equipment word the kernel WRITES to
                                    ; match the adapter it chose
    dw 0x0013, 2                    ; conventional memory KB - ours
    dw 0x001A, 4                    ; the keyboard buffer head and tail, which
                                    ; kbd_ovflow reads on every int 09h
    dw 0x0072, 2                    ; the soft-reset flag
    dw 0x0080, 4                    ; the keyboard buffer BOUNDS - a TSR that
                                    ; enlarges the buffer repoints these into
                                    ; memory we are about to free, and the ROM
                                    ; keeps writing keystrokes there
    dw 0x0098, 10                   ; the int 15h wait-flag pointer, count and
                                    ; flag - the same trap in another field
    dw 0xFFFF, 0

dos_l_idle:  db 'No program to run.', 0
dos_l2_idle: db 'Open a .COM from a disk window.', 0
dos_l_ready: db 'Starting...', 0
dos_l2_ready: db 'Reading it...', 0
dos_l_ran:   db 'The program has finished.', 0
dos_l2_ran:  db 'Exit code '
dos_exitd:   db '000', 0
dos_l_err:   db 'Could not run it.', 0

dos_errs:
    dw dos_e_goto, dos_e_mem, dos_e_read, dos_e_big, dos_e_fsx, dos_e_exe
dos_e_goto:  db 'Its folder could not be opened.', 0
dos_e_mem:   db 'Not enough memory.', 0
dos_e_read:  db 'It could not be read.', 0
dos_e_big:   db 'Too large for one segment.', 0
dos_e_fsx:   db 'The screen is already in use.', 0
dos_e_exe:   db '.EXE is not supported yet.', 0
dos_e_fn:    db 'It asked for INT 21h AH='
dos_fnd:     db '00h.', 0

; --- bss offsets, as a RUNNING TOTAL so the size cannot disagree with the -----
; fields (the Arkanoid %assign pattern). DOS_BSS_SIZE was written by hand once
; and was 6 bytes short of dos_bda's end, which the loader would have answered
; by zeroing less than we write - and a write past our bss is a write past our
; REGION, which is somebody else's heap claim.
%assign DB 0
%macro DBSS 2
    %1 equ DB
    %assign DB DB + %2
%endmacro
    DBSS DOS_B_WIN,   2
    DBSS DOS_B_STATE, 1
    DBSS DOS_B_ERR,   1
    DBSS DOS_B_EXIT,  1
    DBSS DOS_B_BADFN, 1
    DBSS DOS_B_DIR,   2
    DBSS DOS_B_VOL,   1
    DBSS DOS_B_PAD,   1
    DBSS DOS_B_NAME,  16
    DBSS DOS_B_ARENA, 2
    DBSS DOS_B_APARA, 2
    DBSS DOS_B_AKB,   2
    DBSS DOS_B_IMGSZ, 2
    DBSS DOS_B_PRGSP, 2
    DBSS DOS_B_SVSS,  2
    DBSS DOS_B_SVSP,  2
    DBSS DOS_B_PIC1,  1
    DBSS DOS_B_PIC2,  1
    DBSS DOS_B_FSI,   FSI_SIZE
    DBSS DOS_B_IVT,   1024
    DBSS DOS_B_BDA,   256
DOS_BSS_SIZE equ DB

    OS88_BSS DOS_BSS_SIZE
    OS88_IMAGE_END

; =============================================================================
; BSS - zeroed by the loader (SPEC.md 21 step 5)
; =============================================================================
; THE IVT AND BDA SAVES ARE HERE AND NOT IN THE ARENA, ON PURPOSE (SPEC.md
; 96.5): the arena is the program's to scribble on, and a save area the
; program can corrupt is worse than none, because it fails at restore time
; when there is nothing left to do about it.
dos_win     equ os88_image_end + DOS_B_WIN     ; word: our window
dos_state   equ os88_image_end + DOS_B_STATE   ; byte: DST_*
dos_err     equ os88_image_end + DOS_B_ERR     ; byte: DER_*, when DST_ERR
dos_exit    equ os88_image_end + DOS_B_EXIT    ; byte: the program's exit code
dos_badfn   equ os88_image_end + DOS_B_BADFN   ; byte: the AH we lack
dos_dir     equ os88_image_end + DOS_B_DIR     ; word: its folder's cluster
dos_vol     equ os88_image_end + DOS_B_VOL     ; byte: ...and its volume
dos_name    equ os88_image_end + DOS_B_NAME    ; 16:   its NUL 8.3 name
dos_arena   equ os88_image_end + DOS_B_ARENA   ; word: the claim, 0 = none
dos_apara   equ os88_image_end + DOS_B_APARA   ; word: ...its paragraphs
dos_akb     equ os88_image_end + DOS_B_AKB     ; word: ...and its KB, banked
dos_imgsz   equ os88_image_end + DOS_B_IMGSZ   ; word: the image's bytes
dos_prgsp   equ os88_image_end + DOS_B_PRGSP   ; word: the program's first SP
dos_sv_ss   equ os88_image_end + DOS_B_SVSS    ; word: OUR stack, banked
dos_sv_sp   equ os88_image_end + DOS_B_SVSP    ; word: ...across the far jump
dos_pic1    equ os88_image_end + DOS_B_PIC1    ; byte: the 8259 masks as found
dos_pic2    equ os88_image_end + DOS_B_PIC2    ; byte:
dos_fsi     equ os88_image_end + DOS_B_FSI     ; FSI_SIZE: the fsx info block
dos_ivt     equ os88_image_end + DOS_B_IVT     ; 1024: the whole vector table
dos_bda     equ os88_image_end + DOS_B_BDA     ; 256:  ...and the whole BDA
