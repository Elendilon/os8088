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
    db 3                            ; ...and this COUNT is the thing to change
    OS88_ASSOC_EXT 'COM'            ; with them: a fourth entry left at 2 sits
                                    ; in the block and is never looked at, and
                                    ; the symptom is the loader trying to RUN
                                    ; the document
    OS88_ASSOC_EXT 'EXE'
    OS88_ASSOC_EXT 'LNK'            ; a SHORTCUT (SPEC.md 96.21): the target,
                                    ; its arguments and its environment, in
                                    ; Microsoft's own Shell Link layout
    OS88_ASSOC16_END

; DOS_CONT_W/H WERE HERE and are gone (SPEC.md 96.20.3): they were 286 and 81,
; derived by hand from a 288x100 template, and the window is adapter-sized
; now. OSAPI_WM_GEOM answers both, is correct after a resize or a drag across
; a display seam, and cannot go stale when somebody edits the template.

DOS_MIN_KB  equ 64                  ; a machine that cannot offer this much has
                                    ; nothing worth running a DOS program in,
                                    ; and saying so is cheaper than a program
                                    ; that dies on its first allocation

; --- the arena's shape, in PARAGRAPHS (SPEC.md 96.3) -------------------------
DOS_ENVP    equ 32                  ; 512 bytes of environment block. IT WAS
                                    ; 8, which is 128 - and BLASTER= alone is
                                    ; ~24 of those, before the program's own
                                    ; path and anything the user typed
                                    ; (SPEC.md 96.20). Growing it moves the
                                    ; PSP and the program's load base, which
                                    ; is why it is a constant here and not a
                                    ; number anybody may pick
DOS_ENVMCB  equ 0                   ; para 0     : the environment's MCB
DOS_ENVSEG  equ 1                   ; para 1     : the environment itself
DOS_PRGMCB  equ DOS_ENVSEG+DOS_ENVP ; para 9     : the program's MCB ('Z')
DOS_PSPP    equ DOS_PRGMCB+1        ; para 10    : the PSP
DOS_IMGP    equ DOS_PSPP+16         ; para 26    : the image, at PSP:0100

; --- state -------------------------------------------------------------------
; THE ARGUMENTS BUFFER IS 128 AND THE FIELD TAKES 127 OF IT (SPEC.md 96.19).
; That is DOS's limit rather than a choice: PSP:0080 is a length byte, then
; the text, then an 0Dh, all inside 128 bytes. A field that let a 128th
; character in would be one the user could type into and not have obeyed.
DOS_TRACEN  equ 512                 ; DOSTRACE ring entries (power of two).
DOS_TRDUMPN equ 256                 ; ...and how many of them TRACE.LOG holds,
                                    ; which is separate because the RING is
                                    ; read live off a debugger and the FILE is
                                    ; what the field posts: 256 lines is
                                    ; plenty of the latter, and 512 entries of
                                    ; dump buffer would be 36KB of bss taken
                                    ; out of the program's own arena - which
                                    ; would change the measurement the
                                    ; instrument exists to take.
                                    ; IT HOLDS A WHOLE RUN, and 64 did not:
                                    ; the failure under investigation makes
                                    ; 169 calls, so a 64-entry ring threw away
                                    ; the FIRST 105 - which is where a
                                    ; divergence is, every time. The reference
                                    ; tracer (tests/dostrap) keeps the first
                                    ; 256 and stops for the same reason, and
                                    ; the two files only diff line-for-line if
                                    ; both start at entry 0
DOS_TRNM_N  equ 12                  ; ...and names it keeps. Plenty: the
                                    ; failure under investigation makes
                                    ; exactly ONE open in a whole session
DOS_ARGSZ   equ 128
DOS_ARGMAX  equ 127                 ; ...what LN_MAX gets: 126 characters + NUL
DOS_PBUF    equ 80                  ; the program's own path for the environment

; The arguments row, measured DOWN from the content origin. The label sits on
; DOS_LBLY and the box under it, so a 126-tall window has both inside it on a
; 640x200 CGA - which is the geometry that binds (SPEC.md 39).
; THE ENVIRONMENT PAGE (SPEC.md 96.20). Four rows because four fits a 640x200
; CGA under the status lines with the buttons still on the glass, and because
; the DOS programs this box exists for want one or two: BLASTER= is written
; for them and a SOUND= or an MTCPCFG= is the whole of what most of the rest
; ask for. The width is what a `NAME=C:\LONGISH\PATH` needs.
DOS_ENVN    equ 4                   ; rows
DOS_ENVW    equ 48                  ; characters in one, not counting the NUL
DOS_ENVBUF  equ DOS_ENVW + 1

; --- THE SHORTCUT FILE (SPEC.md 96.21) ---------------------------------------
; A valid subset of Microsoft's Shell Link format, because the extension is
; instantly recognisable and every field we need already has a home in it:
;
;   WORKING_DIR              the folder, `\BIN`
;   RELATIVE_PATH            the program, `.\DOSARGS.COM` - valid Windows
;                            spelling AND parseable by us
;   COMMAND_LINE_ARGUMENTS   the tail
;   an ExtraData block       the environment, under a signature of our own.
;                            ExtraData is specified as extensible and unknown
;                            signatures are to be SKIPPED, so this is a legal
;                            use of the mechanism rather than a squat
;
; WE READ ONLY OUR OWN. A Windows-authored link leads with a LinkTargetIDList
; - an arbitrary shell ID list - and a LinkInfo with volume IDs, and parsing
; that from hostile floppy input is real work for no benefit: a 64-bit Windows
; cannot run a DOS program anyway, so the value of the format here is that it
; is RECOGNISED, not that it round-trips. A foreign link is refused by name.
LNK_HDR     equ 76                  ; the fixed header, 0x4C
LNK_F_WDIR  equ 0x10                ; LinkFlags: HasWorkingDir...
LNK_F_RELP  equ 0x08                ; ...HasRelativePath...
LNK_F_ARGS  equ 0x20                ; ...HasArguments. Deliberately NOT
                                    ; HasLinkTargetIDList or HasLinkInfo: both
                                    ; are optional, and both are the parts we
                                    ; decline to write or read
LNK_EXTSIG  equ 0xA0088088          ; OUR ExtraData block: 'os8088' shaped, in
                                    ; the range MS leaves to other producers
LNK_MAX     equ 512                 ; what one may be, read or written

DOS_PAGE_MAIN equ 0
DOS_PAGE_ENV  equ 1

; The status lines land at content+10, +22 and +36 (dos_paint marches DX down
; by 12 then 14), so the arguments row starts below THAT rather than at a
; number chosen by eye - and the whole lot has to finish inside a content box
; ~110 rows tall, which is what a 126px window leaves once the title bar has
; its 16.
DOS_LBLY    equ 52                  ; the label's baseline
DOS_FLDY    equ 64                  ; the box's top...
DOS_FLDH    equ 13                  ; ...and its height, one 8px cell + frame
DOS_FLDW    equ 256                 ; ...and its width
DOS_EROWY   equ 24                  ; the first environment row's top...
DOS_EROWH   equ 16                  ; ...and one row's pitch, which with four
                                    ; rows of DOS_FLDH ends at 85 - clear of
                                    ; the button row below, which a pitch of
                                    ; 18 was not
DOS_BTNW    equ 104                 ; the page buttons. 'Environment' is 11
DOS_BTNH    equ 14                  ; cells = 88px, and a label that touches
DOS_BTNY    equ 90                  ; its own frame reads as struck through
DOS_SAVW    equ 112                 ; 'Save Shortcut' is 13 cells = 104px

; os88line.inc is included at the END of this file (its own rule: the header
; and the icon block are at fixed offsets), and the bss table above needs its
; block size BEFORE that. So the size is written here and CHECKED against the
; real one immediately after the include - a mirrored constant with a gate on
; it, which is what this tree does everywhere two files must agree.
DOS_LNSZ    equ 20

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
DER_BADEXE  equ 6

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

    call dos_size                   ; THE TEMPLATE, before create (SPEC.md
    mov si, dos_tpl                 ; 96.20.3) - wm_create runs wm_fit on the
    call OSAPI_WM_CREATE            ; size it is given, so asking afterwards
    jc .out                         ; would fit twice
    mov [dos_win], bx
    call dos_keeph                  ; ...and on a CGA it may cover the dock
    call dos_fld_init               ; the arguments field (SPEC.md 96.19)

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

    call dos_lnk_open               ; A SHORTCUT names another program and
                                    ; carries its arguments (SPEC.md 96.21);
                                    ; anything else is the program itself
    mov byte [dos_state], DST_READY
    mov bx, [dos_win]
    call OSAPI_WM_WAKE              ; ...and run it from the wake handler, which
    jmp .ok                   ; is the one callback without the gfx lock.
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
    jmp .err
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
    jmp .err
.got:
    mov [dos_arena], dx
    mov ax, [dos_akb]
    mov cl, 6
    shl ax, cl                      ; KB -> paragraphs, and AX < 1024 always
    mov [dos_apara], ax             ; (640KB is 640), so this cannot carry

    mov ax, dx                      ; the FIRST program: its PSP is the
    add ax, DOS_PSPP                ; arena's, and its name is the one the
    mov [dos_ldpsp], ax             ; desktop launched
    mov word [dos_ldname], dos_name

    call dos_fh_setup               ; ...and the file window comes OFF the top
    jc .freeerr                     ; of it before the program is ever told how
                                    ; much memory it has (SPEC.md 96.11), so
                                    ; there is no window for a program to find
                                    ; and no arithmetic for it to disagree with

    mov ax, [dos_apara]             ; ...and only NOW is the first program's
    sub ax, DOS_PSPP                ; block known: the window came off the top
    mov [dos_ldpara], ax            ; of the arena a moment ago, and a block
                                    ; sized before that would hand the program
                                    ; the file window as its own memory
    call dos_load                   ; the image, through the back end
    jc .freeerr
    call dos_is_exe                 ; ...and only NOW, because the answer is in
    jnc .isCOM                      ; the FILE and not in its name
    call dos_exe_setup              ; MZ: relocate, move down, size the block
    jnc .ready
    jmp short .freeerr              ; AL is already a DER_*
.isCOM:
    mov dx, [dos_imghi]             ; a .COM is ONE segment: 64KB - the PSP -
    or dx, dx                       ; the pushed word is the ceiling, so a high
    jnz .toobig                     ; word at all is a file that cannot be one
    cmp word [dos_imgsz], 0xFF00
    jbe .ready
.toobig:
    mov al, DER_BIG
    jmp short .freeerr
.ready:

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
%ifdef DOSTRACE
    call dos_trace_dump             ; ...and the field gets to read it too
%endif
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
    call dos_drv_back               ; ...and back again, on EVERY path through
                                    ; here including the refusals: a resume with
                                    ; nothing suspended is free and a machine
                                    ; left silent is not (SPEC.md 51.11.1)
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
                                    ; a burst it can state (SPEC.md 74.1)
    mov al, CWHITE                  ; **THE INK FIRST** (SPEC.md 96.19.5). AL
    call OSAPI_SET_COLOR            ; is the LOW BYTE of the AX that
                                    ; WM_CONTENT is about to answer x1 in, so
                                    ; setting it after was `mov al, 15` over a
                                    ; content left of 121 - a fill from x=15,
                                    ; which is the window's own left border and
                                    ; most of the desktop beside it
    mov bx, si
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top
    push ax
    push dx
    mov bx, si
    call OSAPI_WM_GEOM              ; CX = content width, DX = content height
    pop bx                          ; ...ASKED, not two constants left over
    pop ax                          ; from a 288x100 window. The window is
    jc .nofill                      ; adapter-sized now (SPEC.md 96.20.3) and
    add cx, ax                      ; a hardcoded width is the same class of
    dec cx                          ; bug as the ink that used to be set into
    add dx, bx                      ; this AX. AX,BX,CX,DX are x1,y1,x2,y2 by
    dec dx                          ; the time this falls through
    call OSAPI_GFX_FILL
.nofill:
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
    mov ax, [dos_ldpsp]
    add ax, 16
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
; in:  [dos_ldpsp], [dos_ldpara], [dos_name]
; out: CF=0 and [dos_imgsz] = the bytes; CF=1 with AL = a DER_*
; -----------------------------------------------------------------------------
dos_load:
    push bx
    push cx
    push dx
    push si
    push es

    mov ax, [dos_ldpsp]             ; THE PROGRAM BEING LOADED, not the arena
    add ax, 16                      ; (SPEC.md 96.14): a child from AH=4Bh is
    mov es, ax                      ; loaded exactly this way into a block of
    xor bx, bx                      ; its own, and everything below here would
                                    ; otherwise be the first program's for ever
    mov ax, [dos_ldpara]            ; the capacity is everything from the image
    sub ax, 16                      ; to the top of ITS block, in paragraphs...
    mov dx, 16
    mul dx                          ; ...as a 32-bit byte count in DX:AX, which
    mov cx, ax                      ; is what OSAPI_FILE_READ takes in DX:CX
    mov si, [dos_ldname]            ; THE NAME IS AN ARGUMENT TOO: AH=4Bh loads
                                    ; a file the running program named, and
                                    ; [dos_name] is the one the DESKTOP did -
                                    ; which made the first child a second copy
                                    ; of its own parent
    call dos_be_read                ; DX:AX = bytes read
    jc .rerr

    mov [dos_imgsz], ax             ; the WHOLE 32-bit size: an .EXE may be
    mov [dos_imghi], dx             ; bigger than a segment and the .COM
    pop es                          ; ceiling is the .COM path's business
    pop si
    pop dx
    pop cx
    pop bx
    clc
    ret
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
; THE .EXE LOADER (SPEC.md 96.8)
; =============================================================================
; MZ header fields, at the front of the file as it was read in.
MZ_CBLP     equ 0x02                ; bytes used in the last 512-byte page
MZ_CP       equ 0x04                ; pages, INCLUDING the header
MZ_CRLC     equ 0x06                ; relocation entries
MZ_CPARHDR  equ 0x08                ; header size in PARAGRAPHS
MZ_MINALLOC equ 0x0A                ; paragraphs wanted beyond the image
MZ_MAXALLOC equ 0x0C                ; ...and the most it can use
MZ_SS       equ 0x0E                ; initial SS, relative to the load segment
MZ_SP       equ 0x10
MZ_IP       equ 0x14
MZ_CS       equ 0x16                ; initial CS, likewise relative
MZ_LFARLC   equ 0x18                ; where the relocation table starts

; -----------------------------------------------------------------------------
; dos_exe_setup - turn the loaded file into a running .EXE image
; in:  the whole file is in the arena at DOS_IMGP, [dos_imgsz]/[dos_imghi] its
;      bytes
; out: CF=0 and [dos_exe_cs]/[dos_exe_ip]/[dos_exe_ss]/[dos_exe_sp] set, the
;      image moved down to DOS_IMGP; CF=1 with AL = a DER_*
;
; THE ORDER IS RELOCATE, THEN MOVE, and it is the whole reason this needs no
; scratch buffer. The relocation table lives in the HEADER, which the move is
; about to overwrite - so a loader that moves first has to copy the table out
; and then carries a bound on how many entries it can hold. The final load
; segment is known before either step (it is the PSP plus 16 paragraphs, by
; DOS's own arithmetic), so the fixups can be applied to the image WHERE IT
; STILL SITS and the table is read in place. No copy, no cap.
; -----------------------------------------------------------------------------
dos_exe_setup:
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es

    mov ax, [dos_ldpsp]
    add ax, 16                      ; the file, header and all
    mov es, ax
    mov [dos_exe_fseg], ax

    ; --- EVERY header field, read BEFORE anything overwrites it ------------
    ; The load segment is DOS_IMGP, which is where the file already sits - so
    ; the move that strips the header lands exactly on top of it. There is no
    ; copy of these four words afterwards and no "still there above": read
    ; them now or lose them.
    mov ax, [es:MZ_CS]
    mov [dos_exe_cs], ax
    mov ax, [es:MZ_IP]
    mov [dos_exe_ip], ax
    mov ax, [es:MZ_SS]
    mov [dos_exe_ss], ax
    mov ax, [es:MZ_SP]
    mov [dos_exe_sp], ax
    mov ax, [es:MZ_CPARHDR]
    mov [dos_exe_hpara], ax
    mov ax, [es:MZ_CRLC]
    mov [dos_exe_nrel], ax
    mov ax, [es:MZ_LFARLC]
    mov [dos_exe_rloc], ax
    mov ax, [es:MZ_MINALLOC]
    mov [dos_exe_minal], ax

    ; --- the image's size, in bytes then paragraphs ------------------------
    mov ax, [es:MZ_CP]              ; pages INCLUDING the header. A last-page
    or ax, ax                       ; count of 0 means the last page is FULL,
    jz .bad                         ; which is the encoding everybody forgets
    dec ax
    mov cx, 512
    mul cx                          ; DX:AX = the whole pages' bytes
    mov bx, [es:MZ_CBLP]
    or bx, bx
    jnz .tail
    mov bx, 512
.tail:
    add ax, bx
    adc dx, 0                       ; DX:AX = the FILE's own idea of its length
    mov bx, [dos_exe_hpara]
    mov cl, 4
    shl bx, cl                      ; header bytes - a header over 4,095
    sub ax, bx                      ; paragraphs is not a thing that exists
    sbb dx, 0
    jc .bad

    add ax, 15                      ; ...and in paragraphs, rounded up: a
    adc dx, 0                       ; 32-bit shift right by four
    mov cx, 4
.p2:
    shr dx, 1
    rcr ax, 1
    loop .p2
    or dx, dx                       ; a paragraph count past 16 bits is more
    jnz .bad                        ; than conventional memory can hold
    mov [dos_exe_ipara], ax

    ; --- does the arena hold PSP + image + minalloc? -----------------------
    mov bx, ax
    add bx, [dos_exe_minal]
    jc .nomem
    add bx, 16
    jc .nomem
    mov ax, [dos_ldpara]            ; the program's block, in paragraphs
    cmp ax, bx
    jb .nomem

    ; --- RELOCATE, in place, BEFORE the move -------------------------------
    ; The table lives in the header the move is about to destroy, and the
    ; final load segment is known already - so the fixups go on the image
    ; WHERE IT STILL SITS and the table is read in place. That is what spares
    ; this a scratch buffer and, with it, a cap on how many entries an .EXE
    ; may have.
    mov ax, [dos_ldpsp]
    add ax, 16                      ; == the file's base: DOS puts an .EXE
    mov [dos_exe_lseg], ax          ; image 16 paragraphs past the PSP, and
    mov bp, ax                      ; that is where dos_load put it

    mov cx, [dos_exe_nrel]
    jcxz .moved
    mov si, [dos_exe_rloc]
    mov dx, [dos_exe_fseg]
    add dx, [dos_exe_hpara]         ; where the image sits RIGHT NOW
.rel:
    mov di, [es:si]                 ; the entry: offset, then segment, both
    mov ax, [es:si+2]               ; relative to the load segment
    add ax, dx                      ; ...resolved against the image's CURRENT
    mov ds, ax                      ; base, which is what lets this run first
    add [di], bp                    ; THE FIXUP
    add si, 4
    loop .rel

.moved:
    ; --- ...and only NOW move the image down over the header ---------------
    push cs
    pop ds
    mov ax, [dos_exe_fseg]
    add ax, [dos_exe_hpara]
    mov dx, [dos_exe_lseg]
    mov cx, [dos_exe_ipara]
    call dos_movedown

    push cs                         ; dos_movedown spends DS and ES
    pop ds
    mov ax, [dos_exe_lseg]          ; CS and SS are RELATIVE to the load
    add [dos_exe_cs], ax            ; segment; IP and SP are absolute
    add [dos_exe_ss], ax
    mov byte [dos_isexe], 1

    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    clc
    ret
.nomem:
    mov al, DER_MEM
    jmp short .fail
.bad:
    mov al, DER_BADEXE
.fail:
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    stc
    ret

; -----------------------------------------------------------------------------
; dos_movedown - copy CX paragraphs from AX:0 down to DX:0
; in:  AX = source segment, DX = destination segment (BELOW it), CX = paragraphs
; out: nothing; clobbers AX, CX, DX, SI, DI, DS, ES, flags
;
; SEGMENT-STEPPED, so an image bigger than 64KB moves without a 16-bit offset
; binding - mem_bcopy's argument one layer out (SPEC.md 66.4). Forward within
; each chunk is safe because the destination is strictly below the source.
; -----------------------------------------------------------------------------
dos_movedown:
    cld
.chunk:
    jcxz .done
    push cx
    cmp cx, 0x800                   ; 2,048 paragraphs = 32KB, so the word
    jbe .last                       ; count below cannot leave a word
    mov cx, 0x800
.last:
    mov ds, ax
    mov es, dx
    push cx
    xor si, si
    xor di, di
    shl cx, 1                       ; paragraphs -> words, 8 words a paragraph.
    shl cx, 1                       ; THREE SINGLE-BIT SHIFTS and not `mov cl,
    shl cx, 1                       ; 3 / shl cx, cl`: the count being shifted
    rep movsw                       ; IS CX, so loading CL destroys its low
    pop cx                          ; byte first. 64 paragraphs became 3, and
                                    ; 48 bytes of a 1KB image moved - which
                                    ; looks like a loader that placed the image
                                    ; wrong rather than one that truncated it
    add ax, cx                      ; ...and both segments step by what moved
    add dx, cx
    pop bx
    sub bx, cx
    mov cx, bx
    jmp short .chunk
.done:
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

    call OSAPI_VIDEO                ; AX = width, BX = height: INT 33h's scale
    mov [dos_vw], ax                ; (SPEC.md 96.10). Asked ONCE, here, and
    mov [dos_vh], bx                ; not per call - it cannot change inside a
                                    ; bracket and a divide is 80+ clocks

    call dos_drv_take               ; THE DRIVERS, OUT OF THE WAY (SPEC.md
                                    ; 96.17) - before the PSP, because the
                                    ; environment it builds carries BLASTER=
                                    ; and the driver is the last thing that
                                    ; knew where the card was
    call dos_save_machine
    call dos_build_psp
    call dos_hook_vectors

    mov ax, [dos_arena]             ; the DTA starts at PSP:0080, which is the
    add ax, DOS_PSPP                ; command tail's own 128 bytes - DOS puts
    mov [dos_dtaseg], ax            ; it there and a program that never calls
    mov word [dos_dta], 0x80        ; AH=1Ah relies on it
    mov ax, [dos_dir]               ; ...and we start where the launch put us.
    mov [dos_curdir], ax            ; NOT a root: a program launched from a
    mov al, [dos_vol]               ; subdirectory can walk out of it, like it
    call dos_drv_bank               ; would under DOS (SPEC.md 96.6.1)
    call dos_date_init              ; the RTC once, or the kernel's fallback

    ; --- into the program --------------------------------------------------
    ; SS:SP is banked in OUR segment, reached through CS by the INT 21h
    ; terminate path, which runs on the program's stack with DS unknown.
    mov ax, ss
    mov [dos_sv_ss], ax
    mov [dos_sv_sp], sp

    call dos_prog_enter             ; ...and away (SPEC.md 96.14): the same
                                    ; door AH=4Bh's child goes through

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

    ; --- THE VECTORS WE DO NOT PROVIDE, HONESTLY NULL (SPEC.md 96.5.1) -----
    ; Banking the whole table is right for everything the machine really
    ; answers, and wrong for one thing: a vector os8088 has NEVER installed
    ; still holds whatever the boot left in it, which is a pointer into the
    ; HEAP. A DOS program asks "is there a mouse driver?" by reading INT 33h
    ; and testing it for non-null - so a stale pointer answers YES, and the
    ; program then CALLS it, into our heap, at whatever that memory happens
    ; to be. NULL is the truthful answer and the one DOS gives on a machine
    ; with no driver loaded. The bank above already holds the old value, so
    ; the restore puts it back untouched.
    xor ax, ax
    mov ds, ax
    mov [0x33*4], ax
    mov [0x33*4+2], ax

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
    mov word [es:0x2F*4], dos_int2f     ; the MULTIPLEX interrupt, which is
    mov [es:0x2F*4+2], cs               ; how a program finds XMS (SPEC.md
                                        ; 96.15) - and, unhooked, is how it
                                        ; finds whatever the ROM left there
    mov word [es:0x33*4], dos_int33     ; ...and the MOUSE (SPEC.md 96.10),
    mov [es:0x33*4+2], cs               ; which costs us a translation and not
    sti                                 ; a driver: the kernel's own ISR keeps
                                        ; mouse_x/y/btn fresh for the whole
                                        ; bracket (SPEC.md 53.1)

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

    mov ax, dx                      ; the environment itself: the variables,
    add ax, DOS_ENVSEG              ; then a NUL to end the set, then the count
    mov es, ax                      ; word and the program's own path - which
    xor di, di                      ; is what DOS 3+ puts there and what a
    cld                             ; program looks for when it wants to know
                                    ; where it came from
    cmp byte [dos_blaster], 0       ; BLASTER= is the one variable the MACHINE
    je .envuser                     ; contributes (SPEC.md 96.17), and it is
    mov si, dos_blaster             ; here only when a sound driver was
.envb:                              ; unloaded a moment ago and told us where
    lodsb                           ; its card was
    stosb
    or al, al
    jnz .envb
.envuser:
    ; --- and whatever the user typed (SPEC.md 96.20) -------------------------
    ; TWO ROWS ARE SKIPPED RATHER THAN EMITTED, and each would break the set
    ; in a different way:
    ;   EMPTY  - a bare NUL is what ENDS the environment, so four rows with
    ;            the second blank would hide the third and fourth from every
    ;            program that reads it.
    ;   NO '=' - DOS's own parser splits on it, so a row without one is a
    ;            variable with no name and nothing could ever look it up.
    push cx
    mov word [dos_erp], dos_ebuf
    mov cx, DOS_ENVN
.envrow:
    mov si, [dos_erp]
    cmp byte [si], 0
    je .envnext                     ; empty
    call dos_has_eq
    jc .envnext                     ; no '='
    mov si, [dos_erp]
.envcp:
    lodsb
    stosb
    or al, al
    jnz .envcp
.envnext:
    add word [dos_erp], DOS_ENVBUF
    loop .envrow
    pop cx
.envend:
    xor al, al
    stosb                           ; ...and the NUL that ends the SET
    mov ax, 1
    stosw
    call dos_envpath                ; ...and the program's own PATH, which is
    mov si, dos_pbuf                ; a real one since SPEC.md 19.2.4 - it was
.env:                               ; a bare 8.3 name while no package could
    lodsb                           ; name the folder it was launched from
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
    call dos_psp_make               ; ...which is a routine of its own, because
                                    ; AH=4Bh's child needs one too (SPEC.md
                                    ; 96.14) and it is not at the arena's base
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_fcb_blank - the unparsed FCB DOS leaves when there is no argument for it
; in:  ES = the PSP, DI = 5Ch or 6Ch; out: DI past the name
; -----------------------------------------------------------------------------
dos_fcb_blank:
    push ax
    push cx
    mov byte [es:di], 0             ; drive 0 = "whichever is current"
    inc di
    mov cx, 11
    mov al, ' '                     ; ...and a name of spaces, which is what a
    cld                             ; tail with nothing in it parses to
    rep stosb
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_jft_sync - the PSP's job file table, rewritten from our own handle table
;
; 0FFh is FREE and anything else is an index into the open-file table DOS keeps
; and we do not, so an open handle publishes its OWN NUMBER - the one thing
; about it that is certainly true (SPEC.md 96.21.4). All twenty are rewritten
; rather than poked one at a time, because a derived table that is only
; corrected where somebody remembered to correct it goes stale, and a stale
; 0FFh on a handle the program is holding is a worse answer than the zero this
; replaces.
; -----------------------------------------------------------------------------
dos_jft_sync:
    push ax
    push bx
    push cx
    push si
    push di
    push es
    mov es, [dos_ldpsp]
    mov si, dos_fhtab
    mov di, 0x18 + DOS_FH0
    mov cx, DOS_NFH
    mov bl, DOS_FH0
.one:
    mov al, 0xFF
    test byte [si+FH_FLAGS], FHF_USED
    jz .put
    mov al, bl
.put:
    mov [es:di], al
    inc di
    inc bl
    add si, FH_SIZEOF
    loop .one
    pop es
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_psp_make - a PSP at [dos_ldpsp], for a block of [dos_ldpara] paragraphs
; in:  [dos_ldpsp], [dos_ldpara], [dos_parent] (0 = nobody)
; out: [dos_prgsp] = the .COM stack offset; every register preserved
; -----------------------------------------------------------------------------
dos_psp_make:
    push ax
    push bx
    push cx
    push dx
    push di
    push es
    mov ax, [dos_ldpsp]
    mov es, ax
    xor di, di
    mov cx, 128                     ; zero it first: every field this does not
    xor ax, ax                      ; set is a field a program may read, and
    cld
    rep stosw                       ; zero is the answer DOS leaves in most

    mov word [es:0x00], 0x20CD      ; INT 20h, so a .COM that plain `ret`s
                                    ; lands here and terminates
    mov ax, [dos_ldpsp]
    add ax, [dos_ldpara]
    mov [es:0x02], ax               ; the paragraph past the block - mechanism 1

    ; --- the CP/M block at +05, WHOSE ADDRESS IS ALSO A FIELD ---------------
    ; The five bytes are a far call, and the word inside it is published in
    ; its own right: [PSP:0006] is "how many bytes are there in this segment",
    ; which is one of the four ways a DOS program asks how much memory it has
    ; (SPEC.md 96.21.4) and the only one that costs it no call at all. Writing
    ; the 9Ah and leaving the address zero - which is what this did - says
    ; ZERO BYTES AVAILABLE and points the call at 0000:0000.
    ;
    ; DOS picks the SEGMENT half so that segment:size addresses its own
    ; dispatcher, which is what lets one five-byte field carry two answers. We
    ; have a dispatcher at PSP:0050 - the `int 21h`/`retf` gate four lines down
    ; - so the segment is (PSP + 5) - size/16 and the call lands on it exactly.
    ; MEASURED against IBM DOS 3.30: 0FEF0h for a block of 64KB or more
    ; (SPEC.md 96.21.4).
    mov byte [es:0x05], 0x9A
    mov ax, [dos_ldpara]
    cmp ax, 0x20                    ; a block too small to hold a PSP and the
    jb .cpmnone                     ; field's own bias cannot answer at all
    cmp ax, 0x1000
    jb .cpmhave
    mov ax, 0x1000                  ; a SEGMENT is 64KB however big the block
.cpmhave:
    mov cl, 4
    shl ax, cl                      ; paragraphs -> bytes, and 1000h shifted is
    sub ax, 0x110                   ; 0 - which is the wrap that MAKES it 0FEF0h
    mov bx, ax
    mov cl, 4
    shr bx, cl
    mov [es:0x06], ax
    mov ax, [dos_ldpsp]
    add ax, 5
    sub ax, bx
    mov [es:0x08], ax
.cpmnone:
    mov word [es:0x0A], dos_int22   ; the terminate address, which DOS copies
    mov [es:0x0C], cs               ; out of the vectors it is about to hook
    mov word [es:0x0E], dos_iret
    mov [es:0x10], cs
    mov word [es:0x12], dos_int24
    mov [es:0x14], cs
    mov ax, [dos_parent]            ; the PARENT's PSP, which AH=4Bh's child
    or ax, ax                       ; reads to find who launched it
    jnz .haveparent
    mov ax, [dos_ldpsp]             ; A PROGRAM WITH NO PARENT IS ITS OWN, which
.haveparent:                        ; is what DOS does for COMMAND.COM and what
    mov [es:0x16], ax               ; makes a walk up the chain TERMINATE. Zero
                                    ; does not: a walker that follows it reads
                                    ; the interrupt vector table as a PSP

    ; --- the job file table, and the two words that point at it -------------
    ; The twenty bytes at PSP:0018 are how a program asks whether a handle is
    ; open without making a call (SPEC.md 96.21.4). 0FFh is FREE and anything
    ; else is an index into the open-file table DOS keeps - so the zeroes the
    ; wipe above leaves say all twenty are OPEN and that they all share one
    ; file. The five devices take the indices IBM DOS 3.30 gives them,
    ; measured; every other entry starts free and dos_jft_sync keeps it true.
    mov di, 0x18
    mov cx, 20
    mov al, 0xFF
    cld
    rep stosb
    mov word [es:0x18], 0x0101      ; 0, 1: stdin and stdout, the console
    mov byte [es:0x1A], 0x01        ; 2: stderr, the same device
    mov byte [es:0x1B], 0x00        ; 3: AUX
    mov byte [es:0x1C], 0x02        ; 4: PRN
    mov word [es:0x32], 20          ; ...and its size and address, which is how
    mov word [es:0x34], 0x0018      ; a program with more than twenty files
    mov ax, [dos_ldpsp]             ; open finds the table that replaced it
    mov [es:0x36], ax
    mov word [es:0x38], 0xFFFF      ; the previous PSP: DOS 3 leaves FFFF:FFFF
    mov word [es:0x3A], 0xFFFF      ; and a program may test for it
    mov ax, [dos_arena]
    add ax, DOS_ENVSEG
    mov [es:0x2C], ax               ; ...and one environment, shared: a child
                                    ; inherits the parent's, which is the
                                    ; default AH=4Bh's block asks for with a 0
    mov word [es:0x50], 0x21CD      ; INT 21h / RETF, the DOS 2+ call gate
    mov byte [es:0x52], 0xCB
    call dos_psp_tail               ; THE ARGUMENTS (SPEC.md 96.19), or the
                                    ; empty tail this used to write flat
    mov di, 0x5C                    ; ...and the two FCBs, in the shape an
    call dos_fcb_blank              ; EMPTY tail parses to. Zero - which this
    mov di, 0x6C                    ; wrote before - is a name of eleven NULs
    call dos_fcb_blank              ; on drive A and not a blank one, so a
                                    ; program that opens FCB 1 without reading
                                    ; the tail got a file that cannot exist
                                    ; rather than one obviously unnamed
                                    ; (SPEC.md 96.21.6)

    ; --- the stack -----------------------------------------------------------
    mov ax, [dos_ldpara]            ; a .COM gets SP at the top of its own
    cmp ax, 0x1000                  ; 64KB when the block holds one, and the
    jb .small                       ; top of the block when it does not
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
    mov bp, sp                      ; [bp]=DS [bp+2]=BP [bp+4]=IP [bp+6]=CS
    push si                         ; [bp+8]=FLAGS, all on the PROGRAM's stack
    push di                         ; ...and [bp-2]=SI [bp-4]=DI [bp-6]=ES,
    push es                         ; banked here rather than per handler
    push cs
    pop ds
%ifdef DOSTRACE
    call dos_trace
%endif

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
    cmp ah, 0x40
    je .write
    cmp ah, 0x4A
    je .resize
    cmp ah, 0x48
    je .alloc
    cmp ah, 0x49
    je .free
    cmp ah, 0x3C
    je .create
    cmp ah, 0x3D
    je .open
    cmp ah, 0x3E
    je .close
    cmp ah, 0x3F
    je .read
    cmp ah, 0x41
    je .unlink
    cmp ah, 0x42
    je .seek
    cmp ah, 0x25
    je .setvec
    cmp ah, 0x35
    je .getvec
    cmp ah, 0x19
    je .curdrv
    cmp ah, 0x0E
    je .seldrv
    cmp ah, 0x1A
    je .setdta
    cmp ah, 0x2F
    je .getdta
    cmp ah, 0x4E
    je .ff
    cmp ah, 0x4F
    je .fn
    cmp ah, 0x39
    je .mkdir
    cmp ah, 0x3A
    je .rmdir
    cmp ah, 0x3B
    je .chdir
    cmp ah, 0x47
    je .getcwd
    cmp ah, 0x2A
    je .getdate
    cmp ah, 0x2B
    je .setdate
    cmp ah, 0x2C
    je .gettime
    cmp ah, 0x2D
    je .settime
    cmp ah, 0x4B
    je .exec
    cmp ah, 0x4D
    je .retcode
    cmp ah, 0x44
    je .ioctl
    cmp ah, 0x43
    je .getattr
    cmp ah, 0x06
    je .dconio
    cmp ah, 0x0C
    je .flushin
    jmp .bad

.term:
    mov sp, bp                      ; THE FRAME, not the top of the stack: the
    pop ds                          ; gate banks three registers below `bp` now
    pop bp                          ; (SPEC.md 96.7.1) and a bare pop pair here
    jmp dos_terminate               ; took two of them instead. AL is the code

.putc:
    mov al, dl
    call dos_tty
    jmp .ok

.puts:
    push ds                         ; the string is the PROGRAM's, at DS:DX, so
    mov ds, [bp]                    ; its DS addresses it and not ours - OFF THE
    push si                         ; FRAME and not off the top of the stack,
    mov si, dx                      ; which is three registers deeper than it
                                    ; was (SPEC.md 96.7.1). Ours is banked
                                    ; because .ok's own work is DS-relative
.sloop:
    mov al, [si]
    cmp al, '$'
    je .sdone
    inc si
    call dos_tty
    jmp short .sloop
.sdone:
    pop si
    pop ds
    jmp .ok

.getce:
    call dos_getkey                 ; AH=01h echoes what it read; AH=07h and
    push ax                         ; AH=08h do not, and 07h additionally does
    call dos_tty                    ; not check for Ctrl-Break - a distinction
    pop ax                          ; wave 1 has nothing to make
    jmp .ok
.getc:
    call dos_getkey
    jmp .ok
.kbhit:
    mov ah, 1                       ; AH=0Bh: FFh if a character is waiting,
    int 0x16                        ; 00h if not - the poll a program spins on
    mov al, 0
    jz .khdone
    mov al, 0xFF
.khdone:
    jmp .ok

.write:
    ; AH=40h: BX = handle, CX = bytes, DS:DX = the buffer, and DS is the
    ; PROGRAM's. Handles 1 and 2 are the console, which is the ROM teletype
    ; here; a real file wants the write wave (DOS-EXEC-PLAN 11 wave 5), and
    ; refusing is what keeps a save from reporting success.
    cmp bx, 2
    ja .fwrite                      ; ...and anything above them is a file
    or bx, bx
    jz .bad                         ; handle 0 is stdin: writing to it is not
    push si                         ; a thing, and DOS answers 0 bytes anyway
    push cx
    mov si, dx
    mov ds, [bp]                    ; THE PROGRAM'S DS, off the frame - [bp] and
                                    ; NOT [bp+2]: the prologue is `push bp /
                                    ; push ds / mov bp, sp`, so the DS push is
                                    ; the one BP lands on. BP is SS-relative by
                                    ; default, which is right - the frame is on
                                    ; the program's own stack
    jcxz .wdone
.wloop:
    mov al, [si]
    inc si
    push cx
    call dos_tty
    pop cx
    loop .wloop
.wdone:
    pop ax                          ; AX = the byte count, which is what a
    pop si                          ; caller checks against CX
    jmp .ok
; --- the file handles (SPEC.md 96.11) ---------------------------------------
; EVERY ONE OF THESE BANKS BX, because it is the handle a program keeps there
; across a read loop and DOS preserves every register but a call's documented
; outputs. dos_fh_slot spends it turning a handle into an index.
.fherr:                             ; AL = a DOS error code
    pop bx
    xor ah, ah
    jmp .badax
.fnoent:
    mov al, 2                       ; file not found
    jmp short .fherr
.fmany:
    mov al, 4                       ; too many open files
    jmp short .fherr
.fhbad:
    mov al, 6                       ; invalid handle
    jmp short .fherr
.fhacc:
    mov al, 5                       ; access denied - and it is the honest
    jmp short .fherr                ; answer for every write this layer cannot
                                    ; make (SPEC.md 96.11.2)
.fhok:
    pop bx
    jmp .ok

.fhabs:
    ; A LEADING "\" ON A FILE NAME names the program's root, and this wave
    ; resolves every name in the directory it is STANDING in - so below the
    ; root it would be the wrong folder. Refused, honestly, rather than
    ; answered from the wrong place (SPEC.md 96.12.2).
    cmp byte [dos_fabs], 0
    je .fhabsok
    cmp word [dos_curdir], 0        ; "\NAME" names the VOLUME's root, so it is
    jne .fhabsno                    ; answerable exactly when we are standing
.fhabsok:                           ; there. Elsewhere it is still refused
                                    ; rather than resolved in the wrong folder:
                                    ; this wave opens names, not paths
    clc
    ret
.fhabsno:
    stc
    ret

.open:
    ; AH=3Dh: DS:DX = an ASCIZ name, AL = the access mode; out AX = a handle.
    ; THE MODE IS NOT HONOURED and the handle is read-only whatever it says,
    ; because OSAPI_FILE_APPEND refuses a file whose size is not a cluster
    ; multiple - so there is no in-place write to give. A program that opens
    ; for writing gets its refusal at the WRITE, naming the call, rather than
    ; at the open naming nothing.
    push bx
    call dos_fh_name
    jc .fherr
    call .fhabs
    jc .fhpath
    call dos_fh_stat                ; fills [dos_fent]
    jc .fnoent
    call dos_fh_new                 ; BX = the handle, SI = the record, zeroed
    jc .fmany
    call dos_fh_setname
    mov ax, [dos_fent+18]
    mov [si+FH_SIZE], ax
    mov ax, [dos_fent+20]
    mov [si+FH_SIZE+2], ax
    mov byte [si+FH_FLAGS], FHF_USED
    test byte [dos_fent+22], OSAPI_FIND_CZ
    jz .opdone
    ; A COMPRESSED FILE CANNOT BE READ THROUGH THE WINDOW AT ALL: READ_AT is
    ; raw (SPEC.md 20.14.3), so it would deliver the wrapper. Small ones are
    ; read WHOLE instead, which expands - and the margin is the SDK's own,
    ; the packed bytes landing high in the buffer and expanding downwards.
    mov ax, [si+FH_SIZE+2]
    or ax, ax
    jnz .opbig
    mov ax, [si+FH_SIZE]
    add ax, 128
    jc .opbig
    cmp ax, [dos_wbytes]
    ja .opbig
    or byte [si+FH_FLAGS], FHF_WHOLE
.opdone:
    call dos_jft_sync               ; ...the PSP's own view of it (96.21.4)
    mov ax, bx                      ; AX = the handle
    jmp .fhok
.opbig:
    mov byte [si+FH_FLAGS], 0       ; hand the slot back: a refused open must
    jmp short .fhacc                ; not spend one

.create:
    ; AH=3Ch: DS:DX = an ASCIZ name, CX = attributes; out AX = a handle. The
    ; file is not touched until the first window flushes, which is also what
    ; makes the truncate free - the first flush REPLACES.
    push bx
    call dos_fh_name
    jc .fherr
    call .fhabs
    jc .fhpath
    call dos_fh_new
    jc .fmany
    call dos_fh_setname
    mov byte [si+FH_FLAGS], FHF_USED | FHF_WRITE
    call dos_jft_sync
    mov ax, bx
    jmp .fhok

.close:
    ; AH=3Eh: BX = the handle.
    push bx
    call dos_fh_slot                ; SI = the record, BX = its index
    jc .fhbad
    cmp bl, [dos_wown]
    jne .clnw
    call dos_fh_flush
    jc .fherr
.clnw:
    test byte [si+FH_FLAGS], FHF_WRITE
    jz .cldone
    test byte [si+FH_FLAGS], FHF_MADE
    jnz .cldone
    call dos_fh_touch               ; created, never written: DOS leaves a
    jc .fherr                       ; zero-length file and so does this
.cldone:
    mov byte [si+FH_FLAGS], 0
    call dos_jft_sync
    xor ax, ax
    jmp .fhok

.read:
    ; AH=3Fh: BX = the handle, CX = bytes, DS:DX = the buffer; out AX = the
    ; bytes delivered, 0 meaning end of file.
    push bx
    call dos_fh_slot
    jc .fhrdev
    call dos_fh_rdloop              ; AX = delivered
    jc .fherr
    jmp .fhok
.fhrdev:
    cmp bx, DOS_FH0                 ; a DEVICE handle: stdin has no line editor
    jae .fhbad                      ; here, so it is at end of file, which is
    xor ax, ax                      ; what a program reading it will act on
    jmp .fhok

.fwrite:
    ; AH=40h with a file handle: BX, CX and DS:DX as .write's.
    push bx
    call dos_fh_slot
    jc .fhbad
    test byte [si+FH_FLAGS], FHF_WRITE
    jz .fhacc
    mov ax, [si+FH_POS]             ; APPEND-ONLY, and the refusal is the point
    cmp ax, [si+FH_SIZE]            ; (SPEC.md 96.11.2): a write anywhere but
    jne .fhacc                      ; the end is one this layer cannot make,
    mov ax, [si+FH_POS+2]           ; and reporting success for it would lose
    cmp ax, [si+FH_SIZE+2]          ; the program's data silently
    jne .fhacc
    call dos_fh_wrloop
    jc .fherr
    jmp .fhok

.unlink:
    ; AH=41h: DS:DX = an ASCIZ name.
    push bx
    call dos_fh_name
    jc .fherr
    call .fhabs
    jc .fhpath
    push si
    mov si, dos_fname
    call dos_be_delete
    pop si
    jc .fhacc
    xor ax, ax
    jmp .fhok

.seek:
    ; AH=42h: AL = the origin, BX = the handle, CX:DX = a SIGNED offset; out
    ; DX:AX = the new position.
    push bx
    mov ah, al                      ; AL is about to be spent
    call dos_fh_slot
    jc .fhbad
    cmp ah, 2
    ja .fhacc
    or ah, ah
    jnz .skcur
    xor ax, ax                      ; origin 0: from the start
    xor bx, bx
    jmp short .skadd
.skcur:
    dec ah
    jnz .skend
    mov ax, [si+FH_POS]             ; origin 1: from here
    mov bx, [si+FH_POS+2]
    jmp short .skadd
.skend:
    mov ax, [si+FH_SIZE]            ; origin 2: from the end
    mov bx, [si+FH_SIZE+2]
.skadd:
    add ax, dx
    adc bx, cx
    mov [si+FH_POS], ax
    mov [si+FH_POS+2], bx
    mov dx, bx
    jmp .fhok

; --- vectors, drives and the DTA (SPEC.md 96.12) -----------------------------
.setvec:
    ; AH=25h: AL = the interrupt, DS:DX = the handler. It goes STRAIGHT into
    ; the live IVT, which is safe because the whole table is banked at bracket
    ; entry and put back at the end (SPEC.md 96.5) - so a program may hook
    ; anything it likes and the machine still comes back.
    push bx
    push es
    xor bx, bx
    mov es, bx
    mov bl, al
    xor bh, bh
    shl bx, 1
    shl bx, 1
    mov [es:bx], dx
    mov ax, [bp]                    ; ...and the PROGRAM's DS, off the frame
    mov [es:bx+2], ax
    pop es
    pop bx
    jmp .ok
.getvec:
    ; AH=35h: AL = the interrupt; out ES:BX = its handler.
    push ax
    xor bx, bx
    mov es, bx
    mov bl, al
    xor bh, bh
    shl bx, 1
    shl bx, 1
    mov ax, [es:bx+2]
    mov bx, [es:bx]
    mov [bp-6], ax                  ; ...the banked ES, as .getdta above
    pop ax
    jmp .ok
.curdrv:
    mov al, [dos_vol]               ; AH=19h: 0 = A. The map is the identity
    jmp .ok                         ; with our hole in it (SPEC.md 96.6), and
                                    ; it MOVES now - which is what makes the
                                    ; select-then-ask idiom above truthful
.seldrv:
    ; AH=0Eh: DL = the drive to select; out AL = how many there are.
    ;
    ; IT ACTUALLY SWITCHES NOW (SPEC.md 96.6.1). It used to answer the count
    ; and stay put, which is not a small gap: the way a program finds out
    ; whether a drive exists is to select it and then ask AH=19h where it
    ; ended up, so a select that silently does nothing reports EVERY drive as
    ; invalid - including the ones that are there.
    call dos_drv_sel
    call dos_drv_count
    jmp .ok
.setdta:
    mov [dos_dta], dx               ; AH=1Ah: DS:DX, and DS is the program's -
    mov ax, [bp]                    ; which for every real program is the PSP
    mov [dos_dtaseg], ax            ; it already runs on
    jmp .ok
.getdta:
    mov bx, [dos_dta]               ; AH=2Fh: out ES:BX - and ES is written into
    mov ax, [dos_dtaseg]            ; the gate's banked slot, which .leave
    mov [bp-6], ax                  ; restores from (SPEC.md 96.7.1)
    jmp .ok

; --- find first / find next (SPEC.md 96.12.1) --------------------------------
.ff:
    ; AH=4Eh: DS:DX = the pattern, CX = the attribute mask.
    push bx
    call dos_fh_name                ; the pattern travels the same road a name
    jc .fherr                       ; does, wildcards and all
    call dos_dta_seg                ; ES:DI = the caller's DTA, and DI STAYS
    mov [es:di+DTA_MASK], cl        ; ...the mask FIRST: the rep movsb below
                                    ; spends CX (SPEC.md 96.12.1)
    mov word [es:di+DTA_ORD], 0     ; there: .fstep below wants the DTA's BASE,
    push si                         ; and a stosw/rep movsb pair would leave it
    push di                         ; fifteen bytes along - which reads the
    add di, DTA_PAT                 ; ordinal out of the pattern
    mov si, dos_fname
    mov cx, 13                      ; the pattern lives in the DTA, so AH=4Fh
    cld                             ; needs no state of ours at all. DOS keeps
    rep movsb                       ; it there and so does this
    pop di
    pop si
    ; A SEARCH THAT MATCHED NOTHING ANSWERS 18, THE SAME AS ONE THAT RAN OUT,
    ; and the distinction this once drew is one DOS does not (SPEC.md
    ; 96.12.1.2). MEASURED, by running one binary under IBM DOS 3.30 and under
    ; this box: a name that is not there in a directory that IS answers 0012h,
    ; and 0002h is not what DOS says for it at all. What DOS answers 3 for is
    ; the DIRECTORY not being there, which `dos_fh_name` above has already
    ; refused by the time this runs.
    call dos_find_step
    jc .ffnone
    xor ax, ax
    jmp .fhok
.ffnone:
    mov al, 18
    jmp .fherr
.fn:
    ; AH=4Fh: everything it needs is in the DTA AH=4Eh filled.
    push bx
    call dos_dta_seg
    call dos_find_step              ; CF=1 with AL = 18 (no more files)
    jc .fherr
    xor ax, ax
    jmp .fhok

; --- directories (SPEC.md 96.12.2) -------------------------------------------
.mkdir:
    push bx
    call dos_fh_name
    jc .fherr
    push si
    mov si, dos_fname
    call dos_be_mkdir
    pop si
    jc .fhacc
    xor ax, ax
    jmp .fhok
.rmdir:
    push bx
    call dos_fh_name
    jc .fherr
    push si
    mov si, dos_fname
    xor al, al                      ; STRICT: remove it only if it is empty,
    call dos_be_rmdir               ; which is the one AH=3Ah means. The
    pop si                          ; recursive form is a different call and
    jc .fhacc                       ; DOS does not have it
    xor ax, ax
    jmp .fhok
.chdir:
    push bx
    call dos_fh_name
    jc .fherr
    call dos_cd_go
    jc .fhpath
    xor ax, ax
    jmp .fhok
.fhpath:
    mov al, 3                       ; path not found
    jmp .fherr
.getcwd:
    ; AH=47h: DL = the drive (0 = current, 1 = A), DS:SI = a 64-byte buffer.
    ; The path goes in WITHOUT its leading backslash, which is DOS's shape.
    ;
    ; IT IS OSAPI_FILE_PATH's ANSWER NOW, not a string this box maintained on
    ; the way down. The buffer, the level tables and the depth counter all
    ; existed because a package could not ask where it was standing; SPEC.md
    ; 19.2.4 is that question, and answering it here deletes the bookkeeping
    ; AND the 8-level limit that came with it.
    push bx
    mov [dos_cwdst], si
    mov byte [dos_cwdrv], 0
    mov al, dl
    or al, al
    jz .cw_here                     ; 0 is "the one I am on"
    dec al                          ; ...otherwise DOS counts A: as 1 here
    cmp al, [dos_vol]
    je .cw_here
    cmp al, DVOL_MAX
    jae .fhpath
    ; ANOTHER DRIVE: stand there, ask, and come back. A program asks this far
    ; less often than it asks about the drive it is on, and the alternative is
    ; a second copy of every drive's path kept up to date for the one call
    ; that reads it.
    mov [dos_cwdrv], al
    mov dl, al
    call dos_drv_sel
    mov al, [dos_cwdrv]
    cmp al, [dos_vol]
    jne .fhpath                     ; dos_drv_sel left us where we were, so
                                    ; that drive is not there
.cw_here:
    push si
    push di
    push es
    push ds
    pop es
    mov di, dos_pbuf
    mov cx, DOS_PBUF
    call OSAPI_FILE_PATH
    jc .cw_bad
    mov si, dos_pbuf
    cmp byte [si], '\'
    jne .cw_copy
    inc si                          ; DOS's shape carries no leading separator
.cw_copy:
    mov di, [dos_cwdst]
    mov es, [bp]                    ; the buffer is the PROGRAM's
    cld
.cw_byte:
    lodsb
    stosb
    or al, al
    jnz .cw_byte
    pop es
    pop di
    pop si
    call dos_cw_back
    mov ax, 0x0100                  ; DOS 3+ leaves AX = 0100h here, and at
    jmp .fhok                       ; least one program checks it
.cw_bad:
    pop es
    pop di
    pop si
    call dos_cw_back
    jmp .fhpath

; --- the date and the time (SPEC.md 96.13) ----------------------------------
.getdate:
    ; AH=2Ah: out CX = year, DH = month, DL = day, AL = the day of the week.
    call dos_date_roll
    mov cx, [dos_dy]
    mov dh, [dos_dm]
    mov dl, [dos_dd]
    call dos_dow                    ; AL = 0 Sunday .. 6 Saturday
    jmp .ok
.setdate:
    ; AH=2Bh: CX = year, DH = month, DL = day; out AL = 0 or FFh.
    cmp cx, 1980
    jb .dbad
    cmp cx, 2099
    ja .dbad
    or dh, dh
    jz .dbad
    cmp dh, 12
    ja .dbad
    or dl, dl
    jz .dbad
    cmp dl, 31
    ja .dbad
    mov [dos_dy], cx                ; ...into OUR copy, which is where DOS
    mov [dos_dm], dh                ; keeps it too on a machine with no clock
    mov [dos_dd], dl                ; chip (SPEC.md 96.13)
    xor al, al
    jmp .ok
.dbad:
    mov al, 0xFF
    jmp .ok
.gettime:
    ; AH=2Ch: out CH = hours, CL = minutes, DH = seconds, DL = hundredths.
    call dos_date_roll
    call dos_time_now
    jmp .ok
.settime:
    ; AH=2Dh: CH/CL/DH/DL as above; out AL = 0 or FFh.
    cmp ch, 23
    ja .tbad
    cmp cl, 59
    ja .tbad
    cmp dh, 59
    ja .tbad
    cmp dl, 99
    ja .tbad
    call dos_time_set
    xor al, al
    jmp .ok
.tbad:
    mov al, 0xFF
    jmp .ok

; --- AH=4Bh: load and run a CHILD (SPEC.md 96.14) ---------------------------
.retcode:
    ; AH=4Dh: out AL = the child's exit code, AH = how it ended (0 = normally).
    mov al, [dos_chexit]
    xor ah, ah
    jmp .ok

.exec:
    ; AL = 0 load-and-execute, DS:DX = the name, ES:BX = the parameter block.
    push bx
    or al, al
    jnz .exbadfn                    ; AL=1 (load, do not run) and AL=3 (an
                                    ; overlay) are different shapes and neither
                                    ; is built (SPEC.md 96.14.2)
    cmp byte [dos_inchild], 0
    jne .exnest                     ; ONE level, and it is a decision - see
                                    ; SPEC.md 96.14.1
    mov [dos_xparm], bx             ; the parameter block, banked while the
    mov [dos_xparms], es            ; name is copied out of the same segment
    call dos_fh_name
    jc .fherr
    call .fhabs
    jc .fhpath

    call dos_exec_load              ; block, load, relocate, PSP, command tail
    jc .exerr                       ; AL is a DOS code

    ; --- into the child ----------------------------------------------------
    ; THE `call` BELOW IS THE RETURN PATH. dos_terminate cannot jump to a
    ; label in here - a global one would re-scope every local label after it -
    ; so the child's exit puts SP back one word BELOW what is banked here and
    ; `ret`s, landing on the word this call is about to push.
    mov ax, ss
    mov [dos_psv_ss], ax
    mov [dos_psv_sp], sp
    mov byte [dos_inchild], 1
    call dos_prog_enter             ; ...and comes back HERE when it exits
    call dos_exec_unload            ; the child's block, back to the chain
    xor ax, ax
    jmp .fhok
.exerr:
    xor ah, ah
    jmp .fherr
.exbadfn:
    mov al, 1                       ; "invalid function"
    jmp .fherr
.exnest:
    mov al, 8                       ; "not enough memory", which is the honest
    jmp .fherr                      ; DOS answer for a child that cannot run

.resize:
    ; AH=4Ah: ES = the block, BX = the paragraphs wanted (SPEC.md 96.9).
    call dos_mcb_resize
    jc .badax
    jmp .ok

.alloc:
    ; AH=48h: BX = paragraphs wanted; out AX = the segment. A refusal answers
    ; the LARGEST available in BX, which is how a program asks "how much is
    ; there" - BX=FFFFh is that question and must get a truthful number.
    call dos_mcb_alloc
    jc .badax
    jmp .ok

.free:
    ; AH=49h: ES = a segment we handed out.
    call dos_mcb_free
    jc .badax
    jmp .ok

.ver:
    mov ax, 0x1F03                  ; AL = 3, AH = 31: DOS 3.31. The version is
    mov bx, 0                       ; a SETTING and not a constant the day a
    mov cx, 0                       ; program wants 5.00 - reporting a version
    jmp .ok                   ; whose functions we lack is worse than
                                    ; reporting a lower one, because a program
                                    ; branches on it (DOS-EXEC-PLAN 12 q1)

.ioctl:
    ; AH=44h - IOCTL, and only the two sub-functions a C runtime asks
    ; (SPEC.md 96.22). AL=00h is "WHAT IS THIS HANDLE?", and it is the call a
    ; library makes on the handle it has just opened, before it reads a byte.
    ; A shim that refuses it hands back CF=1 with DX UNTOUCHED - so the
    ; library tests bit 7 of whatever the program happened to leave in DL and,
    ; when that bit is set, concludes a data file is a character device like
    ; CON: it stops seeking and stops sizing, and the program reports its own
    ; files missing having successfully opened every one of them.
    or al, al
    je .ioc_get
    cmp al, 0x01
    je .ioc_set
    jmp .bad                        ; the block-device sub-functions are a
.ioc_get:                           ; different feature, refused by name
    cmp bx, DOS_FH0
    jae .ioc_file
    ; THE FIVE STANDARD HANDLES ARE NOT ALL THE CONSOLE, and answering as
    ; though they were is what a real DOS does not do (SPEC.md 96.22.1).
    ; Measured against IBM DOS 3.30 on the same machine: handle 3 is AUX and
    ; answers 80C0h, handle 4 is PRN and answers A0C0h - bit 13 is the
    ; printer's "output until busy" - and only 0, 1 and 2 are the console's
    ; 80D3h. A C runtime classifies all five at start-up, so telling it the
    ; printer is a console is a wrong answer it keeps.
    mov dx, 0x80D3
    cmp bx, 3
    jb .ioc_done                    ; 0, 1, 2: the console
    mov dx, 0x80C0
    je .ioc_done                    ; 3: AUX
    mov dx, 0xA0C0                  ; 4: PRN
    jmp short .ioc_done
.ioc_file:
    push bx                         ; dos_fh_slot spends BX and SI, and both
    push si                         ; are the program's here
    call dos_fh_slot
    pop si
    pop bx
    jc .ioc_bad
    mov dl, [dos_vol]               ; bits 0-5 the drive; BIT 7 CLEAR = a
    and dl, 0x3F                    ; FILE, which is the whole question asked
    xor dh, dh
.ioc_done:
    mov ax, dx                      ; DOS answers AX = DX here too, and a
    jmp .ok                         ; library may read either
.ioc_set:
    or dh, dh                       ; DH must be zero: anything else is a
    jne .ioc_bad                    ; device request, and we have no device
    jmp .ok
.ioc_bad:
    mov ax, 6                       ; invalid handle
    jmp .badax

.getattr:
    ; AH=43h - the attribute pair. AL=00h is how a program asks "IS THIS FILE
    ; THERE?" without opening it, so refusing it answers "no" for every file
    ; on the disk.
    or al, al
    je .att_get
    cmp al, 0x01
    je .att_set
    jmp .bad
.att_get:
    push bx
    call dos_fh_name
    jc .fherr
    call .fhabs
    jc .fhpath
    call dos_fh_stat                ; the same lookup AH=3Dh opens through, so
    jc .fnoent                      ; the two can never disagree about a name
    pop bx
    mov cx, 0x20                    ; ARCHIVE. SPEC.md 19 keeps no attribute of
    mov ax, cx                      ; its own and this is what an ordinary
    jmp .ok                         ; readable file reads as everywhere
.att_set:
    push bx
    call dos_fh_name                ; it still has to NAME something real...
    jc .fherr
    call .fhabs
    jc .fhpath
    call dos_fh_stat
    jc .fnoent
    pop bx
    xor ax, ax                      ; ...and the new attributes are then
    jmp .ok                         ; DROPPED rather than refused: there is
                                    ; nowhere to keep them, and a program that
                                    ; sets ARCHIVE on a file it has just
                                    ; written must not fail for it

.dconio:
    ; AH=06h - direct console I/O. DL=FFh asks for a character WITHOUT
    ; waiting, and answers ZF=1 when there is none: a flag in the pushed
    ; image, like the carry, and not a live one.
    cmp dl, 0xFF
    je .dcin
    mov al, dl
    call dos_tty
    jmp .ok
.dcin:
    mov ah, 1
    int 0x16
    jz .dcnone
    xor ah, ah
    int 0x16                        ; AL = the character, and TAKE it
    and word [bp+8], 0xFFBF         ; ZF=0: there was one
    jmp .ok
.dcnone:
    xor al, al
    or word [bp+8], 0x40            ; ZF=1: nothing waiting
    jmp .ok

.flushin:
    ; AH=0Ch - throw away what has been typed ahead, then BE the function in
    ; AL. Only the input calls are legal there; DOS does the flush either way
    ; and ignores anything else, which is what a program relies on when it
    ; clears the buffer with AL=0 before asking a question.
    push ax
.fl_loop:
    mov ah, 1
    int 0x16
    jz .fl_done
    xor ah, ah
    int 0x16
    jmp short .fl_loop
.fl_done:
    pop ax
    mov ah, al
    cmp ah, 0x01
    je .getce
    cmp ah, 0x06
    je .dconio
    cmp ah, 0x07
    je .getce
    cmp ah, 0x08
    je .getce
    jmp .ok                         ; flushed, and the rest is not ours

.bad:
    mov [dos_badfn], ah             ; the window NAMES it (SPEC.md 47): an
    mov ax, 1                       ; unsupported program reports its own gap
.badax:
%ifdef DOSTRACE
    stc                             ; ...as this exit is about to return it
    call dos_tr_result
%endif
    or word [bp+8], 1               ; CF=1 in the RETURNED flags
    jmp short .leave
.ok:
%ifdef DOSTRACE
    clc
    call dos_tr_result
%endif
    and word [bp+8], 0xFFFE         ; CF=0 in the returned flags
.leave:
    ; STKBALANCE-OK: the gate banks SI, DI and ES below `bp` and unwinds them
    ; with `mov sp, bp` rather than three pops, so every exit reads +3 to a
    ; walker that counts pushes. That is the POINT of the arrangement - the
    ; frame is restored from `bp`, so the gate's promise does not rest on
    ; every handler below it being balanced (SPEC.md 96.7.1).
    ;
    ; SI, DI AND ES GO BACK, AND THAT IS NOT TIDINESS (SPEC.md 96.7.1).
    ; No INT 21h function returns SI or DI, so a program keeps live pointers
    ; in them across a call - and the file handlers here use SI as the address
    ; of the handle record and hand it back, so an `open` returned a pointer
    ; into OUR OWN table in a register the program was still using. ES is the
    ; same guarantee with two documented exceptions, and AH=35h and AH=2Fh
    ; make theirs by writing the BANKED slot rather than the live register -
    ; the way the carry flag is already returned.
    mov si, [bp-2]
    mov di, [bp-4]
    mov es, [bp-6]
    mov sp, bp                      ; ...and whatever depth a handler left at,
    pop ds                          ; so the gate's promise does not rest on
    pop bp                          ; every one of them being balanced
    iret

; -----------------------------------------------------------------------------
; dos_terminate - back to the bracket, on our own stack
; in:  AL = the exit code; running on the PROGRAM's stack
; out: never returns
; -----------------------------------------------------------------------------
dos_terminate:
    cli
    mov [cs:dos_exit], al           ; through CS: DS is the program's and the
    cmp byte [cs:dos_inchild], 0
    je .top
    ; --- A CHILD (SPEC.md 96.14): back to the parent, not out of the bracket.
    ; SP goes one word BELOW what AH=4Bh banked, because the `call
    ; dos_prog_enter` it made pushed exactly that word - so the `ret` here
    ; lands inside the handler with no global label to jump to.
    mov [cs:dos_chexit], al
    mov byte [cs:dos_inchild], 0
    mov ax, [cs:dos_psv_ss]
    mov ss, ax
    mov ax, [cs:dos_psv_sp]
    sub ax, 2
    mov sp, ax
    sti
    push cs
    pop ds
    call dos_exec_back
    ret
.top:
    mov ax, [cs:dos_sv_ss]          ; stack is about to stop existing
    mov ss, ax
    mov sp, [cs:dos_sv_sp]
    mov byte [cs:dos_onprog], 0     ; back on the UI task's own stack, so a
    sti                             ; back-end call stops borrowing it
    push cs                         ; ...and back into dos_fsx_main's flow with
    pop ds                          ; our own DS, which every proc below wants
    jmp dos_prog_done

; -----------------------------------------------------------------------------
; dos_tty - one character to the screen, through the ROM
; in:  AL = the character
; out: nothing; preserves everything but the flags
; -----------------------------------------------------------------------------
%ifdef DOSTRACE
; EVERY INT 21h CALL, INTO A RING THE HOST READS - not onto the screen.
;
; The first version of this printed AH through the ROM teletype, which is
; unusable for exactly the programs worth tracing: a game SETS A MODE and owns
; every pixel (SPEC.md 53.7), so the characters land in a framebuffer nobody
; can read back as text, and the 60-call cap ran out during the C runtime's
; own start-up. A ring in .bss costs the traced program nothing, survives the
; mode change, and is read off the guest with the package's own segment - the
; way every other host-side probe in this tree reads package state.
;
; AH and AL both, because the sub-function is the interesting half of 44h,
; 43h, 42h and 4Eh alike. DOS_TRACEN entries, wrapping, with the TOTAL kept
; separately so a reader can tell a wrapped ring from a short one.
; --- dos_tr_name_in - bank [dos_fname], up to DOS_TRNM_N of them -----------
; Every name the program hands the file API, in order. DS is ours here (the
; caller has just restored it) and every register must survive.
dos_tr_name_in:
    push ax
    push bx
    push cx
    push si
    push di
    push es
    mov al, [dos_trnmi]
    cmp al, DOS_TRNM_N
    jae .out                        ; keep the FIRST ones: the interesting
    inc byte [dos_trnmi]            ; open is early and the tail is noise
    mov bl, al
    xor bh, bh
    mov ax, 13
    mul bx
    mov di, ax
    add di, dos_trnm
    push ds
    pop es
    mov si, dos_fname
    mov cx, 13
    cld
    rep movsb
.out:
    pop es
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

dos_tr_name: db 'TRACE.LOG', 0
dos_tr_hdr:  db 'os8088 DOS INT 21h trace', 13, 10
             db 'AX BX CX DX > AXout/CF, oldest first. TOTAL/WRAP ', 0

; --- AL -> two hex digits at DI; AX and the flags preserved -----------------
dos_tr_hex2:
    push ax
    push ax
    shr al, 1
    shr al, 1
    shr al, 1
    shr al, 1
    call dos_hexd
    mov [di], al
    inc di
    pop ax
    and al, 0x0F
    call dos_hexd
    mov [di], al
    inc di
    pop ax
    ret

; --- AX -> four hex digits at DI -------------------------------------------
dos_tr_hex4:
    push ax
    mov al, ah
    call dos_tr_hex2
    pop ax
    call dos_tr_hex2
    ret

; -----------------------------------------------------------------------------
; dos_trace_dump - the ring, as TEXT, into TRACE.LOG beside the program
;
; The ring is unreadable from inside the guest - a DOS program owns the screen
; - and reading it off the host needs a debugger the field does not have. So
; the box writes it: one file, plain text, in the directory the program was
; launched from, replaced on every run.
;
; UI-TASK CONTEXT, which is why it hangs off the end of the bracket and not
; off dos_terminate: the file API is the UI task's (SPEC.md 20.6 rule 7) and
; the program's own stack is gone by here anyway.
; -----------------------------------------------------------------------------
dos_trace_dump:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es

    mov di, dos_trdump
    mov si, dos_tr_hdr
.hdr:
    lodsb
    or al, al
    jz .hdrend
    mov [di], al
    inc di
    jmp short .hdr
.hdrend:
    mov ax, [dos_tracen]
    call dos_tr_hex4
    mov byte [di], '/'
    inc di
    mov ax, [dos_tracew]
    call dos_tr_hex4
    mov byte [di], 13
    inc di
    mov byte [di], 10
    inc di

    ; WHERE THE OLDEST ENTRY IS depends on whether the ring has wrapped: a
    ; short run starts at 0, a wrapped one starts at the write index.
    mov cx, [dos_tracen]
    cmp cx, DOS_TRACEN
    jbe .short
    mov cx, DOS_TRACEN
    mov bx, [dos_tracew]
    jmp short .go
.short:
    xor bx, bx
.go:
    cmp cx, DOS_TRDUMPN             ; the FILE holds fewer than the ring does
    jbe .fits
    mov cx, DOS_TRDUMPN
.fits:
    and bx, (DOS_TRACEN * 32) - 32
    or cx, cx
    jz .write
    xor dx, dx                      ; DX = entries on this line
.ent:
    mov ax, [bx+dos_traceb]         ; AX=
    call dos_tr_hex4
    mov byte [di], ' '
    inc di
    mov ax, [bx+dos_traceb+2]       ; BX=
    call dos_tr_hex4
    mov byte [di], ' '
    inc di
    mov ax, [bx+dos_traceb+4]       ; CX=
    call dos_tr_hex4
    mov byte [di], ' '
    inc di
    mov ax, [bx+dos_traceb+6]       ; DX=
    call dos_tr_hex4
    mov byte [di], '>'              ; ...and what it ANSWERED
    inc di
    mov ax, [bx+dos_traceb+8]
    call dos_tr_hex4
    mov byte [di], '/'
    inc di
    mov ax, [bx+dos_traceb+10]
    call dos_tr_hex4
    mov byte [di], '/'              ; ...and ES:BX, which for AH=35h, 48h and
    inc di                          ; 2Fh IS the answer and AX is not
    mov ax, [bx+dos_traceb+14]
    call dos_tr_hex4
    mov byte [di], ':'
    inc di
    mov ax, [bx+dos_traceb+12]
    call dos_tr_hex4
    mov byte [di], '@'              ; ...and WHO CALLED, which is what a pair
    inc di                          ; of traces that diverge with no call in
    mov ax, [bx+dos_traceb+18]      ; between is read on
    call dos_tr_hex4
    mov byte [di], ':'
    inc di
    mov ax, [bx+dos_traceb+16]
    call dos_tr_hex4
    mov byte [di], '/'
    inc di
    mov ax, [bx+dos_traceb+20]
    call dos_tr_hex4
    mov byte [di], 13
    inc di
    mov byte [di], 10
    inc di
    add bx, 32
    and bx, (DOS_TRACEN * 32) - 32
    dec cx                          ; ...and NOT `loop`: the body outgrew its
    jz .write                       ; own short displacement when the entry
    jmp .ent                        ; learned to say who called
.write:
    mov byte [di], 13
    inc di
    mov byte [di], 10
    inc di
    ; --- and the NAMES, one per line ------------------------------------
    mov si, dos_trnm
    mov cl, [dos_trnmi]
    xor ch, ch
    or cx, cx
    jz .nonames
.nm:
    push cx
    mov cx, 13
.nmc:
    lodsb
    or al, al
    jz .nmpad
    mov [di], al
    inc di
    loop .nmc
    jmp short .nmeol
.nmpad:
    dec cx                          ; step over the rest of the fixed field
    jz .nmeol
    add si, cx
.nmeol:
    mov byte [di], 13
    inc di
    mov byte [di], 10
    inc di
    pop cx
    loop .nm
.nonames:
    mov cx, di
    sub cx, dos_trdump              ; CX = how much of it there is
    push ds
    pop es
    mov bx, dos_trdump
    mov si, dos_tr_name
    xor dx, dx
    call OSAPI_FILE_WRITE           ; creates or REPLACES, in the directory
                                    ; the program was launched from
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

dos_trace:
    cmp ah, 0x02                    ; NOT the console writers. A 110-character
    je .skip                        ; message is 110 entries, which is a whole
    cmp ah, 0x09                    ; ring of noise standing exactly where the
    je .skip                        ; calls that CAUSED it used to be - and the
    cmp ah, 0x06                    ; message can be read off the screen
    je .skip
    push ax
    push bx
    push si
    mov si, [dos_tracew]
    and si, (DOS_TRACEN * 32) - 32  ; the ring's byte index, entry-aligned - a
    add si, dos_traceb              ; power-of-two stride so this is an AND
    mov [dos_tracei], si            ; where any other size needs a divide
    mov [si], ax                    ; AX carries the function AND its
    mov [si+2], bx                  ; sub-function; the other three carry what
    mov [si+4], cx                  ; it is ABOUT - a handle, a count, an
    mov [si+6], dx                  ; offset, a name's address. All four are
                                    ; still the caller's: `push` does not
                                    ; change what it pushes
    mov word [si+8], 0xFFFF         ; ...no result yet, so a call that never
    mov word [si+10], 0xFFFF        ; returned is visible as one
    mov word [si+12], 0xFFFF
    mov word [si+14], 0xFFFF

    ; --- WHO CALLED, which is the question AH and its arguments cannot answer.
    ; Two runs that make the same calls with the same arguments and then
    ; diverge have already diverged somewhere with no call in it, and the only
    ; thing that says where is the CS:IP the `int` pushed. CS is recorded raw
    ; and the reader subtracts the PSP, so the offset compares across two
    ; machines that loaded the program at different addresses.
    mov ax, [bp+4]
    mov [si+16], ax                 ; the return IP - one instruction past the
    mov ax, [bp+6]                  ; `int 21h` that got here
    mov [si+18], ax                 ; ...and its CS
    mov ax, [bp]                    ; ...and DS, BP: BOTH OFF THE FRAME, and
    mov [si+20], ax                 ; the live registers are NOT them -
    mov ax, [bp+2]                  ; dos_int21 pushed its own over the
    mov [si+26], ax                 ; caller's before this was reached
    pop ax                          ; SI is the caller's, under the push above
    push ax
    mov [si+22], ax
    mov [si+24], di                 ; DI is untouched from the gate
    mov ax, ss                      ; SS is still the program's - a DOS call
    mov [si+28], ax                 ; runs on the caller's stack
    lea ax, [bp+10]                 ; ...at the SP the `int` was taken on
    mov [si+30], ax

    add word [dos_tracew], 32
    inc word [dos_tracen]           ; ...and the TOTAL, which does not wrap
    pop si
    pop bx
    pop ax
    ret                             ; ...and NOT into .skip below, which would
                                    ; zero the entry pointer this just set
.skip:
    mov word [dos_tracei], 0        ; a filtered call must not overwrite the
    ret                             ; RESULT of the one before it

; --- dos_tr_result - what the call answered, into its own entry -------------
; in: AX = the answer, CF as it will be returned. Called from the two exits.
;
; ES AND BX ARE RECORDED TOO, and they are not padding. AX and the carry are
; the answer to most calls and to some they are not the answer at all:
; AH=35h's is ES:BX, AH=48h's block is AX with the FAILURE size in BX, and
; AH=2Fh's DTA is ES:BX as well. A ring that logs only AX reads those three as
; "returned 0, no error" - which is how a trace can be complete, correct, and
; silent about the value the program actually branched on.
dos_tr_result:
    push si
    push ax
    pushf                           ; CF IS THE SUBJECT here, and `or si, si`
    mov si, [dos_tracei]            ; two lines down would destroy it
    or si, si
    jz .out                         ; filtered, or no call in flight
    mov [si+8], ax
    mov word [si+10], 0
    mov [si+12], bx                 ; ...the OTHER answer, whole
    mov ax, [bp-6]                  ; ES as the PROGRAM will get it, off the
    mov [si+14], ax                 ; gate's banked slot and not the live
                                    ; register a handler happens to have left
    pop ax                          ; ...the flags, back off the stack
    push ax
    test al, 1                      ; CF is bit 0 of the low half
    jz .out
    mov word [si+10], 1
.out:
    popf
    pop ax
    pop si
    ret
%endif

; -----------------------------------------------------------------------------
; dos_getkey - one character from the ROM
; in:  nothing; out: AL = the character (0 for an extended key's first half)
;
; A POLL AND NOT int 16h AH=00h, and the reason is the MOUSE. INT 33h's press
; and release counts are accumulated by whatever reads the state (SPEC.md
; 96.10.1), so a program parked in a blocking key read is the one place a
; click can happen with nothing looking - and "press a key or click" is a
; prompt DOS programs write. AH=00h is itself a spin on the BIOS buffer's head
; and tail, so sampling round it costs a machine that has ALREADY borrowed the
; screen nothing at all, and buys the wait its edges.
; -----------------------------------------------------------------------------
dos_getkey:
    push bx                         ; BX because a ROM can eat it, and CX/DX
    push cx                         ; because the mouse sample below answers in
    push dx                         ; them - DOS preserves every register but a
.poll:                              ; call's documented outputs, and INT 21h
                                    ; here hands back whatever a handler left
    mov ah, 1
    int 0x16                        ; ZF=0 with a key waiting, and it is NOT
    jnz .take                       ; consumed by the check
    call dos_mou_read               ; ...so keep the button edges alive
    jmp short .poll
.take:
    xor ah, ah
    int 0x16                        ; AL = the character, AH = the scan code.
    pop dx                          ; An extended key answers AL = 0 and DOS
    pop cx                          ; makes the caller ask twice for the scan;
    pop bx                          ; wave 1 hands back the 0 and no more
    ret

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
DBE_FIND    equ 4                   ; CX = ordinal, ES:DI = OSAPI_FIND_SZ buf
DBE_RDAT    equ 6                   ; SI = name, ES:BX = buf, CX = cap,
                                    ;   DX:AX = offset; out DX:AX = delivered
DBE_WRITE   equ 8                   ; SI = name, ES:BX = bytes, DX:CX = count
DBE_APPEND  equ 10                  ; SI = name, ES:BX = bytes, CX = count
DBE_DELETE  equ 12                  ; SI = name
DBE_DFREE   equ 14                  ; out BX = SECTORS per cluster
DBE_MKDIR   equ 16                  ; SI = a name in the current directory
DBE_RMDIR   equ 18                  ; SI = a name, AL = 0 strict
DBE_XCAPS   equ 20                  ; out AX = extended-memory KB
DBE_XALLOC  equ 22                  ; DX:AX = bytes; out DX:AX = a linear base
DBE_XFREE   equ 24                  ; DX:AX = a base
DBE_XCOPY   equ 26                  ; ES:SI, DX:AX, CX, DI (SPEC.md 96.15)
DBE_NENT    equ 14

dos_be_goto:
    mov word [dos_betgt], dos_k_goto
    jmp short dos_be_go
dos_be_read:
    mov word [dos_betgt], dos_k_read
    jmp short dos_be_go
dos_be_find:
    mov word [dos_betgt], dos_k_find
    jmp short dos_be_go
dos_be_rdat:
    mov word [dos_betgt], dos_k_rdat
    jmp short dos_be_go
dos_be_write:
    mov word [dos_betgt], dos_k_write
    jmp short dos_be_go
dos_be_append:
    mov word [dos_betgt], dos_k_append
    jmp short dos_be_go
dos_be_delete:
    mov word [dos_betgt], dos_k_delete
    jmp short dos_be_go
dos_be_dfree:
    mov word [dos_betgt], dos_k_dfree
    jmp short dos_be_go
dos_be_mkdir:
    mov word [dos_betgt], dos_k_mkdir
    jmp short dos_be_go
dos_be_rmdir:
    mov word [dos_betgt], dos_k_rmdir
    jmp short dos_be_go
dos_be_xcaps:
    mov word [dos_betgt], dos_k_xcaps
    jmp short dos_be_go
dos_be_xalloc:
    mov word [dos_betgt], dos_k_xalloc
    jmp short dos_be_go
dos_be_xfree:
    mov word [dos_betgt], dos_k_xfree
    jmp short dos_be_go
dos_be_xcopy:
    mov word [dos_betgt], dos_k_xcopy

; -----------------------------------------------------------------------------
; dos_be_go - the one door, and it SWAPS THE STACK (SPEC.md 96.4.1)
; in:  [dos_betgt] = the dos_k_* to run; every register is its argument
; out: whatever the slot answers, flags included
;
; A KERNEL FILE CALL MAY NOT RUN ON THE DOS PROGRAM'S STACK. Inside the
; bracket SS is the program's - a segment in the middle of the arena - and
; every os8088 context has SS = LOW_SEG (SPEC.md 2.1); the scheduler tests
; for exactly that and declines to switch when it does not hold (SPEC.md 8.5),
; which is safe for a short call and is not what a multi-sector disk write is.
; The symptom is the whole reason this comment is long: OSAPI_FILE_WRITE was
; ENTERED and never came back, the bracket was torn down, and the window said
; `Exit code 000` - a program that ran and exited cleanly, from the outside.
;
; So the call runs on the UI TASK's own stack, which is where the rest of the
; package's file work already runs - [dos_sv_ss]/[dos_sv_sp], banked by
; dos_fsx_main at the deepest point it reaches, so what is reused below that
; point is stack nothing else is holding.
;
; OUTSIDE the bracket it must NOT swap: dos_run's own load is already on that
; stack and [dos_sv_sp] is not yet a number. [dos_onprog] is the test, set at
; the jump into the program and cleared by dos_terminate with SS:SP.
; -----------------------------------------------------------------------------
dos_be_go:
    cmp byte [dos_onprog], 0
    je .direct
    cli                             ; SS and SP move as a pair, as everywhere
    mov [dos_bk_ss], ss             ; else in this file: an interrupt between
    mov [dos_bk_sp], sp             ; them lands on a stack that is half of
    mov ss, [dos_sv_ss]             ; each
    mov sp, [dos_sv_sp]
    sti
    call word [dos_betgt]
    pushf                           ; the answer's FLAGS are on the UI stack
    pop word [dos_beflg]            ; and the `ret` below is on the program's,
    cli                             ; so they are banked ACROSS the swap and
    mov ss, [dos_bk_ss]             ; not carried on either
    mov sp, [dos_bk_sp]
    sti
    push word [dos_beflg]
    popf
    ret
.direct:
    jmp word [dos_betgt]

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

dos_k_find:
    call OSAPI_FILE_FIND
    ret

dos_k_rdat:
    call OSAPI_FILE_READ_AT
    ret

dos_k_write:
    call OSAPI_FILE_WRITE
    ret

dos_k_append:
    call OSAPI_FILE_APPEND
    ret

dos_k_delete:
    call OSAPI_FILE_DELETE
    ret

dos_k_dfree:
    call OSAPI_FILE_DFREE
    ret

dos_k_mkdir:
    call OSAPI_FILE_MKDIR
    ret

dos_k_rmdir:
    call OSAPI_FILE_RMDIR
    ret

dos_k_xcaps:
    call OSAPI_XMEM_CAPS
    ret

dos_k_xalloc:
    call OSAPI_XMEM_ALLOC
    ret

dos_k_xfree:
    call OSAPI_XMEM_FREE
    ret

dos_k_xcopy:
    call OSAPI_XMEM_COPY
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

    cmp byte [dos_page], DOS_PAGE_ENV
    jne .mainpage
    mov bx, si
    call dos_paint_env
    jmp .out
.mainpage:

    cmp byte [dos_state], DST_READY  ; THE RE-KICK (SPEC.md 74.1): the kernel
    jne .nokick                      ; keeps at most one queued wake per window,
    mov bx, si                       ; so this is free when one is already
    call OSAPI_WM_WAKE               ; waiting and is the difference between a
.nokick:                             ; full ring costing a frame and costing
                                     ; the whole launch
    mov bx, si
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top
    mov [dos_ctop], dx              ; banked: DX marches down the status lines
    mov bx, ax                      ; below, and the field's row is measured
    add bx, 8                       ; from the ORIGIN rather than from wherever
    add dx, 10                      ; those happened to end

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

    ; --- the arguments field (SPEC.md 96.19) ---------------------------------
    ; Not drawn at DST_IDLE: there is no program named yet, so there is nothing
    ; for arguments to be arguments TO, and a field that accepted text nothing
    ; would read is worse than no field.
    mov bx, [dos_win]
    call OSAPI_WM_CONTENT
    mov cx, ax
    add cx, 8
    mov dx, [dos_ctop]              ; the content top dos_line has been
    add dx, DOS_LBLY                ; walking down from
    mov si, dos_l_args
    mov ax, (CWHITE << 8) | CBLACK
    call OSAPI_FONT_RUN
    mov bx, [dos_win]
    call dos_fld_place
    mov si, dos_ln
    call os88line_draw

    mov bx, [dos_win]               ; ...and the way to the other page
    call dos_btn_rect
    mov bx, dos_brect
    mov si, dos_l_envb
    xor di, di
    call os88ui_btn

    mov bx, [dos_win]               ; ...and the way OUT of the session
    call dos_sav_rect
    mov bx, dos_srect
    mov si, dos_l_savb
    xor di, di
    call os88ui_btn
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

; -----------------------------------------------------------------------------
; dos_swap - the other page, onto the glass
; in:  BX = the window; the gfx lock is held
;
; **THIS IS THE ONE PLACE A GROUND FILL IS RIGHT** (SPEC.md 96.20.1), and it
; is worth saying which case it is rather than leaving the next reader to
; wonder whether 13.14.6 was forgotten. That rule forbids erasing what you are
; about to draw again - a keystroke, a caret, a status line. Here the ENTIRE
; content is replaced by something else, so nothing is drawn twice: every
; pixel is either the new page's or the ground it needed anyway, and there is
; no window in which the old content is gone and the new is not yet there,
; because both happen under one lock before the caller returns.
;
; The alternative - painting the new page over the old and hoping it covers -
; is what leaves the tail of a longer line behind.
; -----------------------------------------------------------------------------
dos_swap:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bx
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    mov si, ax
    mov di, dx
    pop bx
    push bx
    call OSAPI_WM_GEOM              ; CX = content width, DX = content height
    jc .out2
    mov ax, si                      ; ...the whole of it, once
    mov bx, di
    add cx, si
    dec cx
    add dx, di
    dec dx
    push ax
    mov al, CWHITE
    call OSAPI_SET_COLOR            ; the SLOTS and not os88ui.inc's UI_*
    pop ax                          ; macros: that file is included at the END
    call OSAPI_GFX_FILL             ; of this one (its own rule - the header
    mov al, CBLACK                  ; and the icon are at fixed offsets), so
    call OSAPI_SET_COLOR            ; its macros are not defined up here
.out2:
    pop bx
    mov si, bx                      ; dos_paint takes the window in SI, which
    call dos_paint                  ; is how the kernel calls it
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_size - how big this window should be on THIS adapter (SPEC.md 96.20.3)
;
; apps/browser's br_size, verbatim in policy and for its reasons - and this
; window wants the room for the same kind of thing, because SPEC.md 96's wave
; 6 puts a TEXT CONSOLE in here and a console is a number of ROWS.
;
;   VGA and Hercules   90% of the desktop band, centred in it, so the window
;                      still reads as a window and can be grabbed by an edge
;   CGA                the whole band AND the dock's strip, because 640x200
;                      gives the band 155 rows and the chrome here is already
;                      ~100 of them. The dock stays reachable - a window over
;                      it is wm_dock_under's ordinary case (SPEC.md 11.90)
;
; Written into the TEMPLATE rather than set after create: wm_create runs
; wm_fit on the size it is handed, so asking afterwards fits twice.
; -----------------------------------------------------------------------------
dos_size:
    push ax
    push bx
    push cx
    push dx
    call OSAPI_VIDEO                ; AX = w, BX = h, CX = the dock's first row
    cmp dl, VID_CGA
    je .cga
    sub cx, MBAR_H                  ; CX = the desktop band
    mov ax, cx
    mov bx, 9
    mul bx                          ; **MUL WRITES DX** (SPEC.md 1), which is
    mov bx, 10                      ; why nothing is banked there across it
    xor dx, dx
    div bx                          ; AX = 90% of the band
    mov [dos_tpl+6], ax
    sub cx, ax
    shr cx, 1
    add cx, MBAR_H                  ; ...centred in what is left
    mov [dos_tpl+2], cx
    jmp short .out
.cga:
    sub bx, MBAR_H                  ; the whole screen below the bar, less the
    dec bx                          ; row the drop shadow lives on
    mov [dos_tpl+6], bx
    mov word [dos_tpl+2], MBAR_H
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_keeph - a CGA window may hang over the dock (SPEC.md 11.93)
; in:  BX = the window; out: FLAGS PRESERVED - the CF wm_create left is the
;      loader's answer and still has to ride out of dos_entry
;
; IT ANSWERS BOTH WAYS, which is br_keeph's own hard-won note: a KEEPH left
; set on a VGA raises the height ceiling by the dock's rows on a screen with
; no shortage of them, and this is reachable from a resize where the adapter
; can have gone the other way.
; -----------------------------------------------------------------------------
dos_keeph:
    pushf
    push ax
    push bx
    push cx
    push dx
    push si
    push bx                         ; **BX IS THE WINDOW AND THE ANSWER COMES
    call OSAPI_WM_DISPLAY           ; BACK IN IT** - and it is the card this
    pop bx                          ; window is ON, not the primary (SPEC.md
                                    ; 39.16.4), because a drag across a seam is
                                    ; exactly when the answer changes
    xor al, al
    cmp dl, VID_CGA
    jne .set
    inc al
.set:
    call OSAPI_WM_KEEPH
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    popf
    ret

; -----------------------------------------------------------------------------
; dos_btn_rect - the page button's rect, into dos_brect
; in:  BX = the window; out: dos_brect filled; every register preserved
;
; BOTTOM RIGHT of the content on both pages, so the button does not move when
; the page does - a control that jumps under the pointer is one the user
; clicks by accident.
; -----------------------------------------------------------------------------
dos_btn_rect:
    push ax
    push cx
    push dx
    push si
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top
    mov si, dos_brect
    mov cx, ax
    add cx, 8 + DOS_FLDW - DOS_BTNW
    mov [si+0], cx
    add cx, DOS_BTNW
    mov [si+4], cx
    mov cx, dx
    add cx, DOS_BTNY
    mov [si+2], cx
    add cx, DOS_BTNH
    mov [si+6], cx
    pop si
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_sav_rect - the Save Shortcut button's rect, into dos_srect
; in:  BX = the window; every register preserved
; -----------------------------------------------------------------------------
dos_sav_rect:
    push ax
    push cx
    push dx
    push si
    call OSAPI_WM_CONTENT
    mov si, dos_srect
    mov cx, ax
    add cx, 8
    mov [si+0], cx
    add cx, DOS_SAVW
    mov [si+4], cx
    mov cx, dx
    add cx, DOS_BTNY
    mov [si+2], cx
    add cx, DOS_BTNH
    mov [si+6], cx
    pop si
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_sav_go - the Save Shortcut button was pressed
; in:  BX = the window
;
; The kernel's Standard File dialog in SAVE mode (SPEC.md 38), with the
; completion proc below. The DEFAULT NAME is the program's own with .LNK on
; it, because that is what the user would type.
; -----------------------------------------------------------------------------
dos_sav_go:
    push ax
    push cx
    push si
    push di
    call dos_lnk_build              ; **BUILT BEFORE THE DIALOG OPENS**, and
    jc .out                         ; that is not an ordering preference: the
    mov [dos_lend], cx              ; dialog NAVIGATES, so by the time its
                                    ; completion runs the instance stands
                                    ; wherever the user went - and the link's
                                    ; WORKING_DIR would be that folder rather
                                    ; than the program's. It read `\` before
                                    ; this moved
    call dos_sav_dfl                ; dos_wname = `NAME.LNK`
    mov bx, [dos_win]               ; **BX IS THE WINDOW WE WANT TO HEAR BACK
                                    ; ABOUT**, and leaving it out is a dialog
                                    ; given a garbage pointer - which opens,
                                    ; closes on Enter, and writes nothing
    mov si, dos_wname
    mov di, dos_sav_done
    mov al, FDLG_SAVE
    call OSAPI_FILE_DLG             ; CF=1 = one is already up, or no room -
.out:                               ; and a refusal needs no report: the user
    pop di                          ; pressed a button and nothing happened,
    pop si                          ; which is what a busy dialog looks like
    pop cx
    pop ax
    ret

; --- dos_sav_dfl - `NAME.LNK` from dos_name, into dos_sbuf ------------------
dos_sav_dfl:
    push ax
    push cx
    push si
    push di
    mov si, dos_name
    mov di, dos_wname
    mov cx, 8
.c:
    mov al, [si]
    or al, al
    jz .ext
    cmp al, '.'
    je .ext
    mov [di], al
    inc si
    inc di
    dec cx
    jnz .c
.ext:
    mov byte [di+0], '.'
    mov byte [di+1], 'L'
    mov byte [di+2], 'N'
    mov byte [di+3], 'K'
    mov byte [di+4], 0
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_sav_done - the dialog's completion (SPEC.md 38.6)
; in:  AL = the mode it ran in, SI = OUR window ptr, DI = the chosen name IN
;      KERNEL_SEG (ES points there); UI task, gfx lock HELD, the dialog window
;      already destroyed
;
; **A CANCELLED DIALOG NEVER GETS HERE**, so there is no flag to test - which
; the first version of this did, on a CF the kernel never set.
;
; **THE NAME IS THE KERNEL'S**, so it is copied out before anything else is
; called: the next slot is free to move what DI points at.
;
; IT MUST REPAINT. The kernel does not repaint after a callback returns and
; the window under the dialog has just been uncovered by wm_destroy.
; -----------------------------------------------------------------------------
dos_sav_done:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov dx, si                      ; bank our window: SI is about to be ours
    push di
    mov si, di
    mov di, dos_wname               ; ...the name, out of KERNEL_SEG. **NOT
                                    ; dos_sbuf**: dos_lnk_build below calls
                                    ; dos_lnk_rel, which stages `.\NAME.EXT`
                                    ; there - so the write got `.\DOSARGS.COM`
                                    ; as its FILENAME and answered FERR_NAME,
                                    ; which is a dialog that opens, closes and
                                    ; writes nothing
    mov cx, 13
.cp:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    or al, al
    loopnz .cp
    mov byte [di], 0
    pop di

    push ds                         ; the bytes were built by dos_sav_go,
    pop es                          ; before the dialog moved us
    mov si, dos_wname
    mov bx, dos_lbuf
    mov cx, [dos_lend]
    xor dx, dx
    call dos_be_write
.paint:
    push ds
    pop es
    mov si, [dos_win]
    call dos_paint                  ; the dialog's window was destroyed over
                                    ; ours and nothing else will put it back
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_paint_env - the environment page
; in:  BX = the window; the gfx lock is held, as every W_PAINT's is
;
; NO GROUND FILL FIRST (SPEC.md 13.14.6). The window's own content is already
; the ground the kernel painted, and every line below is an OPAQUE font_run or
; an os88line that draws its own - so nothing here writes a pixel twice, and
; the page is never momentarily blank between an erase and its content.
; -----------------------------------------------------------------------------
dos_paint_env:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bx
    call OSAPI_WM_CONTENT           ; ASKED, not read out of [dos_ctop]: that
    mov cx, ax                      ; is the MAIN page's banked value and is
    add cx, 8                       ; zero until the main page has painted at
    add dx, 6                       ; least once
    mov si, dos_l_envt
    mov ax, (CWHITE << 8) | CBLACK
    call OSAPI_FONT_RUN
    pop bx

    xor cx, cx
.row:
    push cx
    call dos_erow                   ; SI = the block, rect placed
    call os88line_draw
    pop cx
    inc cx
    cmp cx, DOS_ENVN
    jb .row

    call dos_btn_rect
    push bx
    mov bx, dos_brect
    mov si, dos_l_done
    xor di, di
    call os88ui_btn
    pop bx
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret

; -----------------------------------------------------------------------------
; dos_fld_place - put the arguments field where the window is now
; in:  BX = the window; out: nothing, every register preserved
;
; The rect is recomputed from the CONTENT origin on every paint rather than
; banked, because a window moves and os88line's rect is in SCREEN coordinates
; (its LN_X1 comment says so). Banking it would put the caret one drag behind.
; -----------------------------------------------------------------------------
dos_fld_place:
    push ax
    push cx
    push dx
    push si
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top
    mov si, dos_ln
    mov cx, ax
    add cx, 8
    mov [si+LN_X1], cx
    add cx, DOS_FLDW
    mov [si+LN_X2], cx
    mov cx, dx
    add cx, DOS_FLDY
    mov [si+LN_Y1], cx
    add cx, DOS_FLDH
    mov [si+LN_Y2], cx
    pop si
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_key - W_ONKEY. The field owns a keystroke it can use; everything else
; comes back here (os88line_key's CF is that split).
; in:  AL = ascii, AH = scan, SI = the window
; -----------------------------------------------------------------------------
dos_key:
    push bx
    push cx
    push dx
    push si
    push di
    mov bx, si
    cmp byte [dos_state], DST_IDLE   ; nothing is named, so there is nothing
    je .no                           ; for an argument to be an argument to

    ; --- whoever has the caret gets first refusal ----------------------------
    cmp byte [dos_page], DOS_PAGE_ENV
    je .envp
    call dos_fld_place
    mov si, dos_ln
    jmp short .have
.envp:
    call dos_erow_focus              ; SI = the focused row, or 0
.have:
    or si, si
    jz .nofield
    cmp byte [si+LN_FOCUS], 0
    je .nofield
    mov dx, [si+LN_VIEW]             ; bank what os88line_edit compares against
    mov [dos_lnv], dx                ; - IN MEMORY, because AL is the KEYSTROKE
    mov dx, [si+LN_LEN]              ; and loading the view into AX would eat it
    mov [dos_lnl], dx
    call os88line_key                ; CF=0 = the field used it. IT DOES NOT
    jc .nofield                      ; DRAW - its header says "redraw the
    mov ax, [dos_lnv]                ; field", and the redraw is the caller's.
    mov bx, [dos_lnl]
    call os88line_edit               ; EDIT and not DRAW: typing the 21st
    add [dos_ncell], cx              ; character must not repaint twenty that
    inc word [dos_nkey]              ; did not change (SPEC.md 96.19.1)
    jmp short .done

    ; --- ENTER RUNS IT AGAIN (SPEC.md 96.19.4) -------------------------------
    ; **REACHED WHETHER OR NOT A FIELD HAS THE CARET**, which is not where this
    ; started: the run used to sit under the focus test, so pressing Done and
    ; then Enter did nothing at all. A window whose only action key works only
    ; while a particular box is focused is one the user thinks is broken.
.nofield:
    cmp al, 13
    jne .no
    cmp byte [dos_state], DST_RAN    ; only from a program that has FINISHED -
    je .again                        ; DST_READY is one already queued and a
    cmp byte [dos_state], DST_ERR    ; second wake would run it twice
    jne .no
.again:
    mov byte [dos_state], DST_READY
    mov bx, [dos_win]
    call OSAPI_WM_WAKE               ; ...and dos_wake does the rest, exactly
    jmp short .done                  ; as it did for the launch
.no:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    stc
    ret
.done:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    clc
    ret

; -----------------------------------------------------------------------------
; dos_erow_focus - the environment row with the caret, rect placed for drawing
; in:  BX = the window; out: SI = the block, or 0
;
; The rect has to be re-placed before the field is drawn OR hit, because
; os88line's rect is in SCREEN coordinates and the window moves - which is
; dos_fld_place's note, one page along.
; -----------------------------------------------------------------------------
dos_erow_focus:
    push ax
    push cx
    push dx
    push di
    xor cx, cx
.r:
    push cx
    call dos_erow
    cmp byte [si+LN_FOCUS], 0
    jne .got
    pop cx
    inc cx
    cmp cx, DOS_ENVN
    jb .r
    xor si, si
    jmp short .out
.got:
    pop cx
.out:
    pop di
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_click - W_ONCLICK. A press inside the field takes the caret; a press
; outside it gives the caret up.
; in:  CX = x, DX = y, SI = the window
; -----------------------------------------------------------------------------
dos_click:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov bx, si
    cmp byte [dos_state], DST_IDLE
    je .out

    call dos_btn_rect               ; THE PAGE BUTTON FIRST, on both pages -
    push bx                         ; it is in the same place on each, which
    mov bx, dos_brect               ; is what stops it moving under the
    call os88ui_bhit                ; pointer between two clicks
    pop bx
    jc .notpage
    call dos_defocus                ; a field on the page we are leaving must
    xor byte [dos_page], 1          ; not keep the caret, or keys would still
    call dos_swap                   ; reach a box nobody can see
    jmp .out
.notpage:
    cmp byte [dos_page], DOS_PAGE_ENV
    je .notbtn                      ; Save Shortcut is the main page's only
    call dos_sav_rect
    push bx
    mov bx, dos_srect
    call os88ui_bhit
    pop bx
    jc .notbtn
    call dos_sav_go
    jmp .out
.notbtn:
    cmp byte [dos_page], DOS_PAGE_ENV
    jne .mainp
    call dos_click_env
    jmp .out
.mainp:
    call dos_fld_place
    mov si, dos_ln
    call os88line_hit               ; CF=0 = inside
    jc .away
    cmp byte [si+LN_FOCUS], 0
    jne .move                       ; already ours: just move the caret
    mov byte [si+LN_FOCUS], 1
    call os88line_draw              ; ...and the frame gains its caret
    jmp short .out
.move:
    call os88line_click
    jmp short .out
.away:
    cmp byte [si+LN_FOCUS], 0
    je .out
    mov byte [si+LN_FOCUS], 0
    call os88line_caroff            ; ONE CELL, not the field (SPEC.md 13.14.6)
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    clc
    ret

; -----------------------------------------------------------------------------
; dos_click_env - a press on the environment page
; in:  BX = the window, CX = x, DX = y
; -----------------------------------------------------------------------------
dos_click_env:
    push ax
    push cx
    push dx
    push si
    push di
    mov di, cx                      ; bank the point: dos_erow uses CX for the
    mov bp, dx                      ; row index
    xor cx, cx
.r:
    push cx
    call dos_erow
    mov cx, di
    mov dx, bp
    call os88line_hit
    jnc .in
    pop cx
    inc cx
    cmp cx, DOS_ENVN
    jb .r
    call dos_defocus                ; the background: nobody keeps the caret
    jmp short .out
.in:
    pop cx
    call dos_defocus_but            ; SI keeps its focus, every other row loses
    cmp byte [si+LN_FOCUS], 0
    jne .move
    mov byte [si+LN_FOCUS], 1
    call os88line_draw
    jmp short .out
.move:
    mov cx, di
    mov dx, bp
    call os88line_click
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_defocus - no field on either page keeps the caret
; dos_defocus_but - ...except the one in SI
; Each drops ONE CELL per field that had it, never a repaint (SPEC.md 13.14.6).
; -----------------------------------------------------------------------------
dos_defocus:
    push si
    xor si, si
    call dos_defocus_but
    pop si
    ret

dos_defocus_but:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov di, si
    mov si, dos_ln
    call .one
    mov cx, DOS_ENVN
    mov si, dos_eln
.e:
    call .one
    add si, DOS_LNSZ
    loop .e
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.one:
    cmp si, di
    je .skip
    cmp byte [si+LN_FOCUS], 0
    je .skip
    mov byte [si+LN_FOCUS], 0
    push cx
    call os88line_caroff
    pop cx
.skip:
    ret

; -----------------------------------------------------------------------------
; dos_focused - SI = the field with the caret, or SI = 0
; -----------------------------------------------------------------------------
dos_focused:
    push cx
    mov si, dos_ln
    cmp byte [dos_page], DOS_PAGE_ENV
    je .env
    cmp byte [si+LN_FOCUS], 0
    jne .got
    jmp short .none
.env:
    mov si, dos_eln
    mov cx, DOS_ENVN
.e:
    cmp byte [si+LN_FOCUS], 0
    jne .got
    add si, DOS_LNSZ
    loop .e
.none:
    xor si, si
.got:
    pop cx
    ret

; -----------------------------------------------------------------------------
; dos_fld_init - the field's block, once, at entry
; -----------------------------------------------------------------------------
dos_fld_init:
    push ax
    push bx
    push cx
    push dx
    push si
    mov si, dos_ln
    mov ax, dos_args
    mov [si+LN_BUF], ax
    mov word [si+LN_MAX], DOS_ARGMAX
    mov byte [si+LN_FOCUS], 0
    mov byte [dos_args], 0
    call os88line_resync            ; LN_LEN/LN_CAR/LN_VIEW from the text

    mov si, dos_eln                 ; ...and the four environment rows
    mov bx, dos_ebuf
    mov cx, DOS_ENVN
.e:
    mov [si+LN_BUF], bx
    mov word [si+LN_MAX], DOS_ENVBUF
    mov byte [si+LN_FOCUS], 0
    mov byte [bx], 0
    push cx
    call os88line_resync
    pop cx
    add si, DOS_LNSZ
    add bx, DOS_ENVBUF
    loop .e
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_erow - the Nth environment row's block and its rect
; in:  CX = the row (0..DOS_ENVN-1), BX = the window
; out: SI = its os88line block, rect filled in; CX preserved
; -----------------------------------------------------------------------------
dos_erow:
    push ax
    push dx
    push di
    mov ax, DOS_LNSZ
    mul cx
    mov si, dos_eln
    add si, ax
    mov di, cx                      ; ...the row, for the y below
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top
    mov cx, ax
    add cx, 8
    mov [si+LN_X1], cx
    add cx, DOS_FLDW
    mov [si+LN_X2], cx
    mov cx, dx                      ; BANK THE TOP: the multiply below lands
                                    ; its high word in DX, so reading the top
                                    ; back out of DX afterwards put every row
                                    ; at y = row*18 + 24 - above the window
    mov ax, DOS_EROWH
    mul di
    add ax, cx
    add ax, DOS_EROWY
    mov [si+LN_Y1], ax
    add ax, DOS_FLDH
    mov [si+LN_Y2], ax
    mov cx, di
    pop di
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_lnk_open - was this instance handed a .LNK? If so, BECOME what it names
; in:  dos_name = what we were launched with, [dos_dir]/[dos_vol] its folder
; out: nothing; on any refusal the state is left exactly as it was
;
; A shortcut is READ HERE AND NOT IN THE WAKE, because everything downstream -
; the window's own caption, the arguments field, the environment page - wants
; the TARGET's name rather than the link's, and the wake is where the program
; is already being launched.
;
; **A REFUSAL LEAVES THE LINK'S OWN NAME IN PLACE**, so a corrupt or foreign
; .LNK produces the ordinary "it is not a program" failure a moment later,
; with the file the user actually double-clicked named in the window. The
; alternative - a half-applied link - is a window naming a program the user
; never chose.
; -----------------------------------------------------------------------------
dos_lnk_open:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov si, dos_name
    call dos_is_lnk
    jc .out
    mov dx, [dos_dir]               ; ...stand where the link is, exactly as
    mov bl, [dos_vol]               ; dos_run does before loading a program
    call dos_be_goto
    jc .out
    push ds
    pop es
    mov si, dos_name                ; ...and read it whole, in one go
    mov bx, dos_lbuf
    xor dx, dx                      ; DX:CX is the capacity, and a link that
    mov cx, LNK_MAX                 ; needs more than 512 is not one of ours
    call dos_be_read
    jc .out
    mov cx, ax                      ; AX = bytes delivered
    call dos_lnk_parse              ; ...which rewrites dos_name on success
    jc .out
    call dos_fld_reload             ; the fields show what the link carried
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- dos_is_lnk - does the NUL 8.3 name at SI end in .LNK? ------------------
; out: CF=0 yes. Case-insensitive: a FAT name is upper case and this one came
; off a disk, but a name staged by something else need not have.
dos_is_lnk:
    push ax
    push si
.f:
    cmp byte [si], 0
    je .no
    cmp byte [si], '.'
    je .dot
    inc si
    jmp short .f
.dot:
    mov al, [si+1]
    call dos_upc
    cmp al, 'L'
    jne .no
    mov al, [si+2]
    call dos_upc
    cmp al, 'N'
    jne .no
    mov al, [si+3]
    call dos_upc
    cmp al, 'K'
    jne .no
    cmp byte [si+4], 0
    jne .no
    pop si
    pop ax
    clc
    ret
.no:
    pop si
    pop ax
    stc
    ret

dos_upc:
    cmp al, 'a'
    jb .out
    cmp al, 'z'
    ja .out
    sub al, 32
.out:
    ret

; --- dos_fld_reload - the fields show what is in the buffers now ------------
dos_fld_reload:
    push bx
    push cx
    push si
    mov si, dos_ln                  ; RESYNC and not SET: a shortcut writes
    call os88line_resync            ; dos_args and dos_ebuf DIRECTLY, and those
    mov si, dos_eln                 ; ARE these fields' own LN_BUFs - so there
    mov cx, DOS_ENVN                ; is nothing to copy from, and `set` copied
.e:                                 ; from a DI nobody had loaded, straight
    push cx                         ; over the arguments it was called to show
    call os88line_resync
    pop cx
    add si, DOS_LNSZ
    loop .e
    pop si
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_lnk_build - this instance's state as a Shell Link, into dos_lbuf
; out: CX = its length; CF=1 = it does not fit LNK_MAX
;
; THE HEADER IS 76 BYTES AND ALMOST ALL OF IT IS LEGALLY ZERO - three
; FILETIMEs, the file size, the icon index, the hotkey and three reserved
; fields. What is not zero is the size dword, the fixed CLSID, LinkFlags and
; ShowCommand, so the template below IS the header and nothing is patched.
;
; Each StringData entry is a 2-byte CHARACTER COUNT then the characters, NOT
; NUL-terminated. Count is characters rather than bytes, which are the same
; thing here only because IsUnicode is clear.
; -----------------------------------------------------------------------------
dos_lnk_build:
    push ax
    push bx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    mov di, dos_lbuf
    mov si, dos_lnk_hdr
    mov cx, LNK_HDR
    cld
    rep movsb

    call dos_lnk_wdir               ; WORKING_DIR: the folder we came from
    jc .no
    call dos_lnk_rel                ; RELATIVE_PATH: `.\` and the 8.3 name
    jc .no
    mov si, dos_args                ; COMMAND_LINE_ARGUMENTS
    call dos_lnk_str
    jc .no
    call dos_lnk_env                ; ...and ours, in an ExtraData block
    jc .no
    xor ax, ax                      ; the terminal block: any value below 4
    stosw
    stosw
    mov cx, di
    sub cx, dos_lbuf
    clc
    jmp short .out
.no:
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop bx
    pop ax
    ret

; --- dos_lnk_str - SI = a NUL string -> a counted StringData at ES:DI --------
; out: DI advanced; CF=1 = it would pass LNK_MAX and nothing was written
dos_lnk_str:
    push ax
    push cx
    push si
    mov ax, si
    xor cx, cx
.len:
    cmp byte [si], 0
    je .got
    inc si
    inc cx
    jmp short .len
.got:
    mov si, ax                      ; ...back to the start
    mov ax, di
    sub ax, dos_lbuf
    add ax, cx
    add ax, 2
    cmp ax, LNK_MAX
    ja .no
    mov ax, cx
    stosw                           ; the character count...
    jcxz .done
    rep movsb                       ; ...and the characters, no NUL
.done:
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

; --- dos_lnk_wdir - the launch folder, as a StringData ----------------------
; **DI IS AN OUTPUT AND MUST NOT BE RESTORED.** dos_lnk_str advances it past
; the entry it wrote, and an earlier version of this banked DI across the
; whole routine - so the working directory was written and then OVERWRITTEN by
; the next string, and every field in the file came out one place early.
dos_lnk_wdir:
    push cx
    push si
    push di                         ; ...only across the CALL that needs it as
    mov di, dos_pbuf                ; a destination of its own
    mov cx, DOS_PBUF
    call OSAPI_FILE_PATH            ; ES is the caller's DS: an X cell sets it
    pop di
    jc .bare
    mov si, dos_pbuf
    jmp short .w
.bare:
    mov si, dos_lnk_root            ; a refusal is not fatal - `\` is a folder
.w:                                 ; and the link still resolves from it
    call dos_lnk_str                ; ...and DI comes out ADVANCED
    pop si
    pop cx
    ret

; --- dos_lnk_rel - `.\NAME.EXT`, which is BOTH spellings --------------------
; Windows wants a link-relative path and so do we, and `.\` satisfies each.
dos_lnk_rel:
    push ax
    push cx
    push si
    push bx
    mov bx, dos_sbuf
    mov byte [bx], '.'
    mov byte [bx+1], '\'
    inc bx
    inc bx
    mov si, dos_name
.c:
    mov al, [si]
    mov [bx], al
    inc si
    inc bx
    or al, al
    jnz .c
    mov si, dos_sbuf
    call dos_lnk_str
    pop bx
    pop si
    pop cx
    pop ax
    ret

; --- dos_lnk_env - the four rows, in an ExtraData block ---------------------
; {size, signature, data}: size counts ITSELF and the signature, so an
; unknown-signature reader steps over the whole thing with one add - which is
; what makes a private block legal rather than a squat.
dos_lnk_env:
    push ax
    push bx
    push cx
    push dx
    push si
    mov dx, di                      ; bank where the size goes
    add di, 8                       ; ...and step over it and the signature
    mov bx, dos_ebuf
    mov cx, DOS_ENVN
.row:
    push cx
    mov si, bx
    cmp byte [si], 0
    je .next
    mov ax, di
    sub ax, dos_lbuf
    add ax, DOS_ENVBUF + 8
    cmp ax, LNK_MAX
    ja .no
.cp:
    mov al, [si]
    stosb
    inc si
    or al, al
    jnz .cp                         ; ...NUL and all: the block is a SET, and
                                    ; a set's members are NUL-terminated
.next:
    pop cx
    add bx, DOS_ENVBUF
    loop .row
    xor al, al
    stosb                           ; ...and the bare NUL that ends the set
    mov ax, di                      ; now the size, over the hole banked above
    sub ax, dx
    push di
    mov di, dx
    stosw
    xor ax, ax
    stosw                           ; ...a dword, and 512 never needs the top
    mov ax, LNK_EXTSIG & 0xFFFF
    stosw
    mov ax, LNK_EXTSIG >> 16
    stosw
    pop di                          ; ...back to the END of the block
    clc
    jmp short .out
.no:
    pop cx
    stc
.out:
    pop si                          ; **DI IS NOT RESTORED**, for dos_lnk_wdir's
    pop dx                          ; reason: it is an OUTPUT. Banking it here
    pop cx                          ; left the block written and then
    pop bx                          ; OVERWRITTEN by the terminal marker, which
    pop ax                          ; presents as a link with no environment
    ret

; -----------------------------------------------------------------------------
; dos_lnk_parse - dos_lbuf holds CX bytes of a .LNK; take it apart
; out: CF=0 and dos_name/dos_args/dos_ebuf filled; CF=1 = not one of OURS
;
; **IT REFUSES A FOREIGN LINK BY NAME AND THAT IS DELIBERATE** (SPEC.md
; 96.21.1). A Windows-authored shortcut leads with a LinkTargetIDList - an
; arbitrary shell ID list - and a LinkInfo carrying volume IDs, and parsing
; those from hostile floppy input is real work for no benefit: a modern
; Windows cannot run a DOS program anyway, so what the format buys here is
; that it is RECOGNISED, not that it round-trips. The flags word says which
; it is in one compare.
;
; EVERY LENGTH IS CHECKED AGAINST WHAT IS LEFT, not against the buffer: a
; count that runs past the end of a SHORT file would otherwise read whatever
; follows it in our own image (SPEC.md 20.8 rule 2).
; -----------------------------------------------------------------------------
dos_lnk_parse:
    push ax
    push bx
    push dx
    push si
    push di
    mov [dos_lend], cx
    cmp cx, LNK_HDR + 6
    jb .no                          ; too short to be a link at all
    cmp word [dos_lbuf], LNK_HDR    ; HeaderSize, the format's own magic
    jne .no
    cmp word [dos_lbuf+2], 0
    jne .no
    cmp byte [dos_lbuf+4], 0x01     ; ...and the CLSID's first two bytes, which
    jne .no                         ; is as much of a 16-byte constant as is
    cmp byte [dos_lbuf+5], 0x14     ; worth comparing to refuse a wrong file
    jne .no
    mov ax, [dos_lbuf+20]           ; LinkFlags
    test ax, 0x03                   ; HasLinkTargetIDList | HasLinkInfo
    jnz .no                         ; ...a Windows-authored one. Refused.
    mov bx, ax
    mov si, LNK_HDR                 ; SI walks the buffer as an OFFSET, so one
                                    ; bound test serves every field
    mov byte [dos_pbuf], 0
    test bx, LNK_F_WDIR
    jz .norel
    push di                         ; WORKING_DIR -> dos_pbuf, and it is USED
    push dx                         ; (dos_lnk_cd below). A shortcut whose
    mov di, dos_pbuf                ; whole point is sitting where the user put
    mov dx, DOS_PBUF                ; it cannot resolve its program relative to
    call dos_lnk_takeb              ; ITSELF
    pop dx
    pop di
    jc .no
.norel:
    test bx, LNK_F_RELP
    jz .noargs
    call dos_lnk_take               ; RELATIVE_PATH -> dos_sbuf
    jc .no
    call dos_lnk_name               ; ...its last component -> dos_name
    jc .no
.noargs:
    test bx, LNK_F_ARGS
    jz .extra
    mov di, dos_args
    mov dx, DOS_ARGSZ
    call dos_lnk_takeb              ; COMMAND_LINE_ARGUMENTS -> dos_args
    jc .no
.extra:
    call dos_lnk_ext                ; ...and our own block, if it is there
    call dos_lnk_cd                 ; ...and stand where the link says, which
                                    ; makes [dos_dir] the TARGET's folder
                                    ; rather than the link's
    clc
    jmp short .out
.no:
    stc
.out:
    pop di
    pop si
    pop dx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_lnk_cd - walk to the link's WORKING_DIR and make it [dos_dir]
;
; DOWN FROM THE VOLUME ROOT, one component at a time - the only direction a
; package can walk (SPEC.md 19.2.4: dsk_find drops the dot links, so there is
; no up). OSAPI_FILE_GOTO_QM is the move and it is A WORD inside the volume we
; are already on, so the walk costs its directory reads and no mounts at all.
;
; A REFUSAL IS NOT FATAL: [dos_dir] keeps the link's own folder, which is
; where a shortcut saved beside its program resolves anyway. What the user
; then sees is the ordinary "it could not be read", naming the program.
; -----------------------------------------------------------------------------
dos_lnk_cd:
    push ax
    push dx
    cmp byte [dos_pbuf], 0
    je .out                         ; no working directory in the link
    call dos_walk_pbuf
    jc .out                         ; A REFUSAL IS NOT FATAL: [dos_dir] keeps
    mov [dos_dir], dx               ; the link's own folder, which is where a
.out:                               ; shortcut saved beside its program
    pop dx                          ; resolves anyway. What the user then sees
    pop ax                          ; is the ordinary "it could not be read",
    ret                             ; naming the program

; -----------------------------------------------------------------------------
; dos_walk_pbuf - stand at the absolute path in dos_pbuf, from the volume ROOT
; out: CF=0 with DX = the cluster it ended on (0 = the root); CF=1 = some
;      component does not exist, and where the machine stands is then undefined
; clobbers: DX and the flags, nothing else
;
; DOWN AND ONLY DOWN, one component at a time, because that is the only
; direction a package has: dsk_find drops the on-disk dot links, so
; OSAPI_FILE_FIND never reports '..' and nothing outside the kernel can walk
; upward at all (SPEC.md 19.2.4). Every move is OSAPI_FILE_GOTO_QM, which
; inside the volume we are already on is a WORD and no I/O - so the walk costs
; its directory reads and no mounts.
;
; It is what makes '..' possible WITHOUT a descent stack: ask where we are,
; drop the last component, and re-descend to what is left. That has no depth
; limit, needs nothing remembered, and is right after a drive switch - which a
; recorded stack would not have been.
; -----------------------------------------------------------------------------
dos_walk_pbuf:
    push ax
    push bx
    push cx
    push si
    push di
    push es
    push ds
    pop es
    xor dx, dx                      ; ...the volume root, first
    mov bl, [dos_vol]
    call OSAPI_FILE_GOTO_QM
    jc .no
    mov si, dos_pbuf
.comp:
    cmp byte [si], '\'
    jne .name
    inc si
    jmp short .comp
.name:
    cmp byte [si], 0
    je .here                        ; ...every component walked
    mov di, dos_cname
    mov cx, 12
.c:
    mov al, [si]
    or al, al
    jz .cend
    cmp al, '\'
    je .cend
    mov [di], al
    inc si
    inc di
    loop .c
.cend:
    mov byte [di], 0
    call dos_lnk_find               ; DX = its cluster
    jc .no
    mov bl, [dos_vol]
    call OSAPI_FILE_GOTO_QM         ; ...a WORD inside this volume
    jc .no
    jmp short .comp
.here:
    call OSAPI_FILE_HERE            ; DX = where we ended up
    clc
    jmp short .out
.no:
    stc
.out:
    pop es
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; --- dos_lnk_find - the folder called dos_cname here; DX = its cluster ------
dos_lnk_find:
    push ax
    push cx
    push si
    push di
    xor cx, cx
.l:
    mov di, dos_fbuf
    push ds
    pop es
    call OSAPI_FILE_FIND
    jc .no
    cmp word [dos_fbuf+14], OSAPI_FT_DIR
    jne .l
    mov si, dos_fbuf
    mov di, dos_cname
    call dos_ceq
    jc .l
    mov dx, [dos_fbuf+16]
    pop di
    pop si
    pop cx
    pop ax
    clc
    ret
.no:
    pop di
    pop si
    pop cx
    pop ax
    stc
    ret

; --- dos_ceq - SI vs DI, NUL strings, case-insensitive. CF=0 = equal --------
; NOT dos_streq, which already exists here and answers in ZF against ES:DI -
; this one is DS-relative on both sides and folds case, because a FAT name is
; upper and a link's stored one need not be.
dos_ceq:
    push ax
    push si
    push di
.c:
    mov al, [si]
    call dos_upc
    mov ah, al
    mov al, [di]
    call dos_upc
    cmp al, ah
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

; --- dos_lnk_skip - step SI over one StringData ------------------------------
dos_lnk_skip:
    push ax
    mov ax, [dos_lend]
    sub ax, si
    cmp ax, 2
    jb .no
    mov ax, [dos_lbuf+si]           ; the character count
    add si, 2
    push bx
    mov bx, [dos_lend]
    sub bx, si
    cmp ax, bx                      ; ...against what is LEFT, never against
    pop bx                          ; the buffer (SPEC.md 20.8 rule 2)
    ja .no
    add si, ax
    pop ax
    clc
    ret
.no:
    pop ax
    stc
    ret

; --- dos_lnk_take - one StringData -> dos_sbuf, NUL-terminated --------------
dos_lnk_take:
    push di
    push dx
    mov di, dos_sbuf
    mov dx, 20
    call dos_lnk_takeb
    pop dx
    pop di
    ret

; --- dos_lnk_takeb - one StringData -> ES:DI (DS), DX = its capacity --------
dos_lnk_takeb:
    push ax
    push bx
    push cx
    push di
    mov ax, [dos_lend]
    sub ax, si
    cmp ax, 2
    jb .no
    mov cx, [dos_lbuf+si]
    add si, 2
    mov bx, [dos_lend]
    sub bx, si
    cmp cx, bx
    ja .no
    mov bx, dx
    dec bx                          ; ...room for the NUL we add
    cmp cx, bx
    ja .no                          ; REFUSED, never truncated (SPEC.md 47)
    push si
.cp:
    jcxz .done
    mov al, [dos_lbuf+si]
    mov [di], al
    inc si
    inc di
    dec cx
    jmp short .cp
.done:
    mov byte [di], 0
    pop ax                          ; the SI we pushed; SI is already advanced
    pop di
    pop cx
    pop bx
    pop ax
    clc
    ret
.no:
    pop di
    pop cx
    pop bx
    pop ax
    stc
    ret

; --- dos_lnk_name - the last component of dos_sbuf -> dos_name --------------
dos_lnk_name:
    push ax
    push bx
    push si
    push di
    mov bx, dos_sbuf                ; find the last separator...
    mov si, bx
.f:
    mov al, [si]
    or al, al
    jz .at
    cmp al, '\'
    jne .n
    mov bx, si
    inc bx
.n:
    inc si
    jmp short .f
.at:
    mov si, bx
    mov di, dos_name
    mov cx, 13
.c:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    or al, al
    jz .ok
    dec cx
    jnz .c
    mov byte [di-1], 0              ; a name longer than an 8.3 one is not one
    pop di
    pop si
    pop bx
    pop ax
    stc
    ret
.ok:
    cmp byte [dos_name], 0
    je .bad
    pop di
    pop si
    pop bx
    pop ax
    clc
    ret
.bad:
    pop di
    pop si
    pop bx
    pop ax
    stc
    ret

; --- dos_lnk_ext - find OUR ExtraData block and load the rows ---------------
; A block we do not recognise is STEPPED OVER by its own size, which is what
; the format is for. A missing block is not an error: a link written by
; anything else simply carries no environment.
dos_lnk_ext:
    push ax
    push bx
    push cx
    push di
.blk:
    mov ax, [dos_lend]
    sub ax, si
    cmp ax, 8
    jb .out                         ; no room for another block header
    mov ax, [dos_lbuf+si]           ; BlockSize, low word
    cmp ax, 4
    jb .out                         ; ...the terminal value
    mov bx, [dos_lend]
    sub bx, si
    cmp ax, bx
    ja .out                         ; a size past the end: stop, do not trust
    mov cx, [dos_lbuf+si+4]         ; the signature
    mov di, [dos_lbuf+si+6]
    cmp cx, LNK_EXTSIG & 0xFFFF
    jne .next
    cmp di, LNK_EXTSIG >> 16
    jne .next
    call dos_lnk_rows
    jmp short .out
.next:
    add si, ax
    jmp short .blk
.out:
    pop di
    pop cx
    pop bx
    pop ax
    ret

; --- dos_lnk_rows - the NUL-separated set at SI+8 -> dos_ebuf ---------------
dos_lnk_rows:
    push ax
    push bx
    push cx
    push si
    push di
    add si, 8
    mov bx, dos_ebuf
    mov cx, DOS_ENVN
.row:
    cmp si, [dos_lend]
    jae .out
    cmp byte [dos_lbuf+si], 0
    je .out                         ; the bare NUL that ends the set
    mov di, bx
    mov ax, DOS_ENVW
.cp:
    cmp si, [dos_lend]
    jae .out
    push ax
    mov al, [dos_lbuf+si]
    mov [di], al
    inc si
    inc di
    or al, al
    pop ax
    jz .done
    dec ax
    jnz .cp
    mov byte [di], 0                ; a row longer than a row is cut HERE and
.done:                              ; nowhere else - it is our own file and
    add bx, DOS_ENVBUF              ; the field is what bounds it on the way in
    loop .row
.out:
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_has_eq - does the NUL string at SI carry an '='?
; out: CF=0 yes, CF=1 no; SI and every register preserved
; -----------------------------------------------------------------------------
dos_has_eq:
    push si
.c:
    cmp byte [si], 0
    je .no
    cmp byte [si], '='
    je .yes
    inc si
    jmp short .c
.yes:
    pop si
    clc
    ret
.no:
    pop si
    stc
    ret

; -----------------------------------------------------------------------------
; dos_psp_tail - the user's arguments into the new PSP's command tail
; in:  ES = the PSP's segment; out: nothing, every register preserved
;
; THE DOS FORMAT IS A LENGTH BYTE, THE TEXT, AND AN 0Dh (SPEC.md 96.19), and
; the length counts the text alone. A program that parses its own arguments
; finds the terminator; one that uses PSP:0080 as a counted string finds the
; count. Both are wrong about the other, so both are written.
;
; It is BOUNDED AT SOURCE rather than here: dos_args is 128 bytes and the line
; field's LN_MAX is 127 + the NUL, because the tail plus its count and its 0Dh
; have to live inside the PSP's 128. That is DOS's limit and not ours, which
; is why the field REFUSES the 128th character rather than this routine
; truncating a line the user can see (SPEC.md 47).
; -----------------------------------------------------------------------------
dos_psp_tail:
    push ax
    push cx
    push si
    push di
    mov si, dos_args
    xor cx, cx
.len:
    cmp byte [si], 0
    je .got
    inc si
    inc cx
    cmp cx, 126
    jb .len
.got:
    mov es:[0x80], cl               ; ...the count DOS puts there
    mov di, 0x81
    mov si, dos_args
    cld
    jcxz .term
    push cx
    rep movsb                       ; DS:SI is ours, ES:DI the PSP's
    pop cx
.term:
    mov byte [es:di], 0x0D
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_envpath - the program's own path, for the tail of the environment
; out: dos_pbuf = `\DIR\NAME.EXT`, NUL-terminated; every register preserved
;
; DOS 3+ puts the program's full path after the environment's terminating NUL
; and a count word, and a program looks there when it wants to know where it
; came from. This wrote a bare 8.3 name until SPEC.md 19.2.4 existed, because
; no package could name the folder it was launched from.
;
; A REFUSAL IS NOT FATAL HERE. If the slot cannot answer - a corrupt chain, a
; buffer too small - the name alone goes in, which is exactly what this wrote
; before and is better than nothing: a program that cannot find its own
; directory falls back on the current one, and every program has that path.
; -----------------------------------------------------------------------------
dos_envpath:
    push ax
    push cx
    push si
    push di
    mov di, dos_pbuf
    mov cx, DOS_PBUF
    call OSAPI_FILE_PATH            ; ES is the CALLER's DS here: an X cell
    jc .bare                        ; sets it (SPEC.md 19.2.4)
    mov di, dos_pbuf
    add di, cx                      ; ...to the NUL it wrote
    cmp cx, 1
    jbe .name                       ; the root already ends in its separator
    mov byte [di], '\'
    inc di
.name:
    mov si, dos_name                ; ...and the program's own 8.3 name
.nm:
    lodsb
    mov [di], al
    inc di
    or al, al
    jnz .nm
    jmp short .out
.bare:
    mov si, dos_name                ; no path: the name alone, which is what
    mov di, dos_pbuf                ; this did before 19.2.4 and is still a
.bn:                                ; thing a program can resolve
    lodsb
    mov [di], al
    inc di
    or al, al
    jnz .bn
.out:
    pop di
    pop si
    pop cx
    pop ax
    ret

; =============================================================================
; DATA
; =============================================================================
dos_tpl:
    dw 120, 64, 288, 126            ; x, y, w, h. TALLER AND HIGHER THAN WAVE
                                    ; 1's 110/100, which put the bottom at 210
                                    ; on a 640x200 CGA and left the clamp to
                                    ; sort out - and there is a field down
                                    ; there now
    dw dos_ttl, dos_paint, dos_key, dos_click

dos_ttl:    db 'DOS', 0
dos_l_args: db 'Arguments:', 0
dos_l_envb: db 'Environment', 0
dos_l_envt: db 'Environment - one NAME=VALUE to a line:', 0
dos_l_done: db 'Done', 0
dos_l_savb: db 'Save Shortcut', 0
dos_lnk_root: db '\', 0

; --- the Shell Link header, 76 bytes, fixed (SPEC.md 96.21) ------------------
dos_lnk_hdr:
    dd 0x0000004C                   ; HeaderSize, and the format's own magic
    db 0x01,0x14,0x02,0x00          ; LinkCLSID {00021401-0000-0000-
    db 0x00,0x00, 0x00,0x00         ;            C000-000000000046}, in the
    db 0xC0,0x00,0x00,0x00,0x00,0x00,0x00,0x46   ; mixed-endian GUID order
    dd LNK_F_WDIR | LNK_F_RELP | LNK_F_ARGS      ; LinkFlags
    dd 0                            ; FileAttributes
    dd 0, 0                         ; CreationTime  - legally zero...
    dd 0, 0                         ; AccessTime
    dd 0, 0                         ; WriteTime
    dd 0                            ; FileSize      - ...and so is this
    dd 0                            ; IconIndex
    dd 1                            ; ShowCommand = SW_SHOWNORMAL
    dw 0                            ; HotKey
    dw 0                            ; Reserved1
    dd 0                            ; Reserved2
    dd 0                            ; Reserved3
DOS_LNK_HDRLEN equ $ - dos_lnk_hdr
%if DOS_LNK_HDRLEN != LNK_HDR
 %error "the Shell Link header is 76 bytes and this template is not"
%endif

dos_be:                             ; the table, in DBE_* order
    dw dos_k_goto
    dw dos_k_read
    dw dos_k_find
    dw dos_k_rdat
    dw dos_k_write
    dw dos_k_append
    dw dos_k_delete
    dw dos_k_dfree
    dw dos_k_mkdir
    dw dos_k_rmdir
    dw dos_k_xcaps
    dw dos_k_xalloc
    dw dos_k_xfree
    dw dos_k_xcopy

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
    dw dos_e_badexe
dos_e_goto:  db 'Its folder could not be opened.', 0
dos_e_mem:   db 'Not enough memory.', 0
dos_e_read:  db 'It could not be read.', 0
dos_e_big:   db 'Too large for one segment.', 0
dos_e_fsx:   db 'The screen is already in use.', 0
dos_e_exe:   db '.EXE is not supported yet.', 0
dos_e_badexe: db 'Its .EXE header is malformed.', 0
dos_dotdot:  db '..', 0
dos_s_blast: db 'BLASTER=A', 0
dos_mlen:    db 31,28,31,30,31,30,31,31,30,31,30,31
dos_dowt:    db 0,3,2,5,0,3,5,1,4,6,2,4    ; Sakamoto's month table
dos_e_fn:    db 'It asked for INT 21h AH='
dos_fnd:     db '00h.', 0


; =============================================================================
; INT 33h - THE MOUSE (SPEC.md 96.10)
; =============================================================================
; NOT A DRIVER. os8088's own mouse ISR runs for the whole bracket and keeps
; mouse_x/y/btn fresh (SPEC.md 53.1 - it never draws, because the gfx lock is
; held), so what a DOS program needs is the INT 33h SHAPE over numbers that
; are already being maintained. CuteMouse is a driver and we do not need one.
;
; THE VIRTUAL SCREEN IS 640x200 IN MICKEY UNITS, which is INT 33h's own
; convention: positions go in and out doubled horizontally in modes narrower
; than 640, and every caller expects a 0..639 x 0..199 range whatever the
; card is. os8088's pointer lives on the DESKTOP's geometry - 640x480 on VGA,
; 720x348 on Hercules - so the translation is a scale, and it is done with a
; multiply and a divide rather than a table because the desktop's size is a
; run-time fact (SPEC.md 39.2) and not one of three constants.
;
; FUNCTIONS 5 AND 6 NEED EDGES, and a handler that only runs when the program
; calls it can only see the transitions its polls straddle (SPEC.md 96.10.1).
; Answering "0 presses" would be honest and would also break the common case -
; a program whose whole click detection IS function 5 - so the counts are
; accumulated on EVERY state read, function 3's poll feeding them as much as
; function 5's own call does. A click shorter than the program's poll interval
; is lost and no shim can do better without an ISR of its own.
;
; WHAT IS NOT HERE, and is named rather than silently wrong: function 0Bh's
; MICKEY COUNTERS. mou_apply consumes the raw deltas into a screen-clamped
; position and keeps no accumulator, so a relative count can only be derived
; from position changes - which loses every mickey spent while the pointer is
; against an edge. Absolute programs (menus, CAD, paint packages) do not care;
; a mouselook does. docs/plans/DOS-EXEC-PLAN.md 9.1 prices the kernel-side fix
; at about ten resident bytes and leaves it as a decision rather than taking it.
; BX, CX AND DX ARE OUTPUTS AND ARE NOT SAVED, which is the whole difference
; between this prologue and INT 21h's a few hundred lines up. INT 33h answers
; in registers rather than in the caller's FLAGS, so a handler that restores
; them the way an ISR normally would returns the caller its own arguments back
; - "bx=65532" for a reset that set BX to 2, and every position exact in AX
; and garbage everywhere else. The paths that are not asked for them simply do
; not write them, which is what a real driver's "undefined" means.
dos_int33:
    sti
    push bp
    push ds
    push cs
    pop ds
    push si
    push di

    or ax, ax
    jz .reset
    cmp ax, 1
    je .none                       ; show/hide: the kernel owns the pointer and
    cmp ax, 2                      ; the bracket holds the gfx lock, so it is
    je .none                       ; not ON the screen to raise or lower - and
    cmp ax, 3                      ; a REFUSAL would make a program that hides
    je .pos                        ; before drawing abandon the drawing
    cmp ax, 4
    je .none                       ; set position: warping the host pointer is
    cmp ax, 5                      ; the kernel's, and a program that borrowed
    je .press                      ; the screen has not borrowed the arrow
    cmp ax, 6
    je .release
    cmp ax, 0x0B
    je .motion
    jmp short .none

.reset:
    call dos_mou_zero              ; a reset clears the edge state with it
    mov ax, 0xFFFF                 ; a mouse IS installed - and it is, whatever
    mov bx, 2                      ; the machine has, because the kernel found
    jmp short .out                 ; one at boot or the pointer would not move
.pos:
    call dos_mou_read              ; BX = the buttons, CX = x, DX = y
    jmp short .out
.press:
    mov si, bx                     ; the button asked about, banked before the
    call dos_mou_read              ; read overwrites BX with the live mask
    mov ax, bx
    and si, 1                      ; two buttons, so anything else is button 1
    mov bl, [si+dos_mou_pc]
    mov byte [si+dos_mou_pc], 0    ; reading a count CONSUMES it, which is why
    xor bh, bh                     ; it is a count and not a flag
    mov cx, [dos_mou_px]
    mov dx, [dos_mou_py]
    jmp short .out
.release:
    mov si, bx
    call dos_mou_read
    mov ax, bx
    and si, 1
    mov bl, [si+dos_mou_rc]
    mov byte [si+dos_mou_rc], 0
    xor bh, bh
    mov cx, [dos_mou_rx]
    mov dx, [dos_mou_ry]
    jmp short .out
.motion:
    call dos_mou_delta             ; CX = dx, DX = dy since the last call -
    jmp short .out                 ; derived, see the header
.none:
    xor ax, ax                     ; INT 33h's "not supported"
.out:
    pop di
    pop si
    pop ds
    pop bp
    iret

; -----------------------------------------------------------------------------
; dos_mou_zero - forget the edge state (function 0)
; clobbers: nothing
; -----------------------------------------------------------------------------
dos_mou_zero:
    mov byte [dos_mou_lb], 0
    mov word [dos_mou_pc], 0       ; both counts are one word apiece in pairs,
    mov word [dos_mou_rc], 0       ; so two stores clear four bytes
    ret

; -----------------------------------------------------------------------------
; dos_mou_read - the pointer, in INT 33h's 640x200 virtual units
; out: BX = the button mask (bit 0 left, bit 1 right), CX = x, DX = y
; clobbers: flags
;
; The multiply EATS DX, which is the y this routine has to answer, so y is
; banked across it - and the divide's remainder lands there too. Both are the
; kind of clobber that reads as a mouse that only works horizontally.
; -----------------------------------------------------------------------------
dos_mou_read:
    push ax
    call OSAPI_MOUSE                ; CX = x, DX = y, AL = the buttons - and
    mov bl, al                      ; mouse_btn's bits ARE INT 33h's, bit 0
    xor bh, bh                      ; left and bit 1 right (SPEC.md 9), so the
    push bx                         ; mask needs no translation at all
    push dx                         ; the y the x scale below is about to eat
    mov ax, cx
    mov cx, [dos_vw]
    jcxz .nox                       ; a zero divisor cannot happen and must not
    mov bx, 640                     ; take the axis with it: leave x as it is
    mul bx                          ; DX:AX = x * 640, and x < vw always, so
    div cx                          ; the quotient is < 640 and cannot overflow
.nox:
    mov cx, ax
    pop ax                          ; y
    push cx                         ; ...and the scaled x, which is AX's next
    mov cx, [dos_vh]
    jcxz .noy
    mov bx, 200
    mul bx
    div cx
.noy:
    mov dx, ax
    pop cx
    pop bx
    pop ax
    call dos_mou_edge               ; every state read feeds functions 5 and 6
    ret

; -----------------------------------------------------------------------------
; dos_mou_edge - accumulate the press/release counts 5 and 6 answer
; in:  BL = the live button mask, CX = x, DX = y (INT 33h units)
; out: nothing, every register preserved
;
; The press POSITION is latched once and shared between the two buttons rather
; than kept per button (SPEC.md 96.10.1): a caller that asks button 1 where
; button 0 went down is answered the wrong point, and a caller with one button
; in play - in practice, all of them - is answered exactly.
; -----------------------------------------------------------------------------
dos_mou_edge:
    push ax
    push bx
    mov al, [dos_mou_lb]
    mov [dos_mou_lb], bl
    xor al, bl                      ; AL = the bits that CHANGED since the last
    jz .out                         ; read, which is the whole of the history
    mov bh, al                      ; a polled shim can have
    and bh, bl                      ; ...of which these went DOWN
    jz .up
    mov [dos_mou_px], cx
    mov [dos_mou_py], dx
    test bh, 1
    jz .d1
    inc byte [dos_mou_pc]
.d1:
    test bh, 2
    jz .up
    inc byte [dos_mou_pc+1]
.up:
    not bl
    and al, bl                      ; ...and these went UP
    jz .out
    mov [dos_mou_rx], cx
    mov [dos_mou_ry], dx
    test al, 1
    jz .u1
    inc byte [dos_mou_rc]
.u1:
    test al, 2
    jz .out
    inc byte [dos_mou_rc+1]
.out:
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_mou_delta - function 0Bh, derived from the position
; out: CX = dx, DX = dy since the last call
; clobbers: BX, flags
; -----------------------------------------------------------------------------
dos_mou_delta:
    push ax
    call dos_mou_read
    mov ax, cx
    sub cx, [dos_mou_lx]
    mov [dos_mou_lx], ax
    mov ax, dx
    sub dx, [dos_mou_ly]
    mov [dos_mou_ly], ax
    pop ax
    ret

; =============================================================================
; THE MCB CHAIN (SPEC.md 96.9)
; =============================================================================
; A real first-fit allocator over the blocks dos_build_psp laid out, because a
; stub is not enough for anything compiled: a C runtime's startup SHRINKS its
; own block with AH=4Ah and then asks for its heap with AH=48h, and a 48h that
; always refuses leaves malloc returning NULL for ever. SOPWITH 7.F15 does
; exactly that and then spins - one write to the console and no further DOS
; call at all, which is what an unchecked allocation failure looks like from
; outside.
;
; An MCB is 16 bytes at the paragraph BEFORE the block it describes:
;   +0  byte  'M' = another follows, 'Z' = the last one
;   +1  word  the owning PSP, 0 = free
;   +3  word  the block's size in paragraphs
;   +5  11    reserved, and DOS 4's 8-byte name
MCB_SIG     equ 0
MCB_OWN     equ 1
MCB_SZ      equ 3
MCB_M       equ 'M'
MCB_Z       equ 'Z'

; -----------------------------------------------------------------------------
; dos_mcb_split - make BX paragraphs of the block at ES, freeing the rest
; in:  ES = the MCB, BX = the paragraphs to keep
; out: nothing; the block is shortened and a free MCB follows it
; clobbers: AX, CX, DX, flags
;
; Only splits when there is room for the new header AND at least one paragraph
; under it: a zero-length free block is a chain entry nothing can ever use and
; one more thing for every later walk to step over.
; -----------------------------------------------------------------------------
dos_mcb_split:
    push es
    push dx                         ; DX IS THE CALLER'S AND MUST SURVIVE. Not
    mov cx, [es:MCB_SZ]             ; tidiness: dos_mcb_alloc walks the chain in
    sub cx, bx                      ; DX and forms its ANSWER from it after
    jbe .out                        ; calling here, so a split that moved DX
    dec cx                          ; handed the program a segment one whole
    jz .out                         ; block high - inside the FREE remainder
                                    ; this call had just cut (SPEC.md 96.9.1)
    mov al, [es:MCB_SIG]            ; the tail inherits our end-of-chain flag
    mov dx, es
    mov [es:MCB_SZ], bx
    mov byte [es:MCB_SIG], MCB_M    ; ...and we are no longer the last
    add dx, bx
    inc dx                          ; the new header sits past our block
    mov es, dx
    mov [es:MCB_SIG], al
    mov word [es:MCB_OWN], 0        ; free
    mov [es:MCB_SZ], cx
.out:
    pop dx
    pop es
    ret

; -----------------------------------------------------------------------------
; dos_mcb_alloc - AH=48h
; in:  BX = paragraphs wanted
; out: CF=0 and AX = the block's segment; CF=1 with AX = 8 and BX = the
;      largest free block there is
; -----------------------------------------------------------------------------
dos_mcb_alloc:
    push cx
    push dx
    push si
    push es
    xor cx, cx                      ; CX = the largest seen, for the refusal
    mov dx, [dos_arena]             ; the chain starts at the arena's floor
.scan:
    mov es, dx
    cmp byte [es:MCB_SIG], MCB_M
    je .live
    cmp byte [es:MCB_SIG], MCB_Z
    jne .broken                     ; a chain a program has trampled: refuse
.live:                              ; rather than walk into the heap
    cmp word [es:MCB_OWN], 0
    jne .next
    mov si, [es:MCB_SZ]
    cmp si, cx
    jbe .notbig
    mov cx, si                      ; remember the largest free
.notbig:
    cmp si, bx
    jb .next
    call dos_mcb_split              ; it fits: keep BX and free the rest
    mov ax, [dos_arena]
    add ax, DOS_PSPP
    mov [es:MCB_OWN], ax            ; ...owned by the program's PSP
    mov ax, dx
    inc ax                          ; the block is the paragraph after its MCB
    pop es
    pop si
    pop dx
    pop cx
    clc
    ret
.next:
    cmp byte [es:MCB_SIG], MCB_Z
    je .nomem
    add dx, [es:MCB_SZ]
    inc dx
    jmp short .scan
.nomem:
    mov bx, cx                      ; the truthful largest, which is what a
    mov ax, 8                       ; BX=FFFFh probe is asking for
    jmp short .fail
.broken:
    xor bx, bx
    mov ax, 7                       ; "memory control blocks destroyed"
.fail:
    pop es
    pop si
    pop dx
    pop cx
    stc
    ret

; -----------------------------------------------------------------------------
; dos_mcb_free - AH=49h
; in:  ES = a segment this allocator handed out
; out: CF=0 freed; CF=1 with AX = 9 (invalid block address)
;
; It marks the block free and does NOT coalesce. DOS does not coalesce here
; either - it does it on the next alloc's walk - and a program that frees two
; neighbours and asks for their sum is asking for something DOS would also
; refuse.
; -----------------------------------------------------------------------------
dos_mcb_free:
    push dx
    push es
    mov dx, es
    dec dx                          ; the MCB is the paragraph before it
    mov es, dx
    cmp byte [es:MCB_SIG], MCB_M
    je .ok
    cmp byte [es:MCB_SIG], MCB_Z
    jne .bad
.ok:
    mov word [es:MCB_OWN], 0
    pop es
    pop dx
    clc
    ret
.bad:
    pop es
    pop dx
    mov ax, 9
    stc
    ret

; -----------------------------------------------------------------------------
; dos_mcb_resize - AH=4Ah
; in:  ES = the block, BX = the paragraphs wanted
; out: CF=0 resized; CF=1 with AX = 8 and BX = the most it could have, or
;      AX = 9 for a block that is not one of ours
;
; GROWING is refused unless the free block immediately above is big enough,
; which is DOS's own rule: a block only ever grows into its own neighbour.
; -----------------------------------------------------------------------------
dos_mcb_resize:
    push cx
    push dx
    push es
    mov dx, es
    dec dx
    mov es, dx
    cmp byte [es:MCB_SIG], MCB_M
    je .known
    cmp byte [es:MCB_SIG], MCB_Z
    jne .bad
.known:
    mov cx, [es:MCB_SZ]
    cmp bx, cx
    jbe .shrink
    ; --- grow: only into a FREE neighbour --------------------------------
    cmp byte [es:MCB_SIG], MCB_Z
    je .nofit                       ; nothing above us at all
    push es
    push dx
    add dx, cx
    inc dx
    mov es, dx                      ; the block above
    cmp word [es:MCB_OWN], 0
    jne .nofit2
    mov ax, [es:MCB_SZ]
    add ax, cx
    inc ax                          ; ...absorbed, header and all
    mov ch, [es:MCB_SIG]            ; ITS end-of-chain flag, banked in a
                                    ; register the two pops below do not
                                    ; touch. It was DL, one instruction in
                                    ; front of `pop dx` - so the byte written
                                    ; back was the LOW HALF OF THIS BLOCK'S
                                    ; OWN SEGMENT, and dos_mcb_split then
                                    ; handed that to the tail it cut. A chain
                                    ; ending in 1Ch instead of 'Z' is refused
                                    ; whole by dos_mcb_alloc's .broken arm,
                                    ; which answers BX=0: "0 KBytes is
                                    ; Available", with 319 KB free behind it
    pop dx
    pop es
    cmp bx, ax
    ja .nofitax
    mov [es:MCB_SZ], ax             ; take the whole neighbour, then give back
    mov [es:MCB_SIG], ch            ; what is not wanted
    call dos_mcb_split
    jmp short .done
.nofit2:
    pop dx
    pop es
.nofit:
    mov ax, cx
.nofitax:
    mov bx, ax                      ; the most it could have had
    pop es
    pop dx
    pop cx
    mov ax, 8
    stc
    ret
.shrink:
    call dos_mcb_split
.done:
    pop es
    pop dx
    pop cx
    clc
    ret
.bad:
    pop es
    pop dx
    pop cx
    mov ax, 9
    stc
    ret

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
    DBSS DOS_B_CTOP,  2          ; the content top, banked for one paint
    DBSS DOS_B_LNV,   2          ; the field's view and length as they were
    DBSS DOS_B_LNL,   2          ; before a keystroke (os88line_edit's inputs)
    DBSS DOS_B_NCELL, 2          ; glyph cells the edits have redrawn...
    DBSS DOS_B_NKEY,  2          ; ...over this many keystrokes
    DBSS DOS_B_PAGE,  1          ; which page is up (DOS_PAGE_*)
    DBSS DOS_B_BRECT, 8          ; the page button's rect, x1 y1 x2 y2
    DBSS DOS_B_SRECT, 8          ; ...and Save Shortcut's
    DBSS DOS_B_ERP,   2          ; the environment row being emitted
    DBSS DOS_B_LBUF,  LNK_MAX    ; a shortcut, read or written
    DBSS DOS_B_SBUF,  20         ; ...and `.\NAME.EXT` while one is built
    DBSS DOS_B_CNAME, 14         ; one component of a link's working directory
    DBSS DOS_B_FBUF,  24         ; ...and OSAPI_FIND_SZ while it is looked up
    DBSS DOS_B_WNAME, 14         ; ...and the name a Save dialog chose, which
                                 ; may NOT share dos_sbuf: the builder uses it
    DBSS DOS_B_LEND,  2          ; how many bytes of dos_lbuf are real
    DBSS DOS_B_EBUF,  DOS_ENVN * DOS_ENVBUF   ; the environment rows...
    DBSS DOS_B_ELN,   DOS_ENVN * DOS_LNSZ     ; ...and their field blocks
    DBSS DOS_B_ARGS,  DOS_ARGSZ  ; the user's arguments, NUL-terminated
    DBSS DOS_B_PBUF,  DOS_PBUF   ; ...and the program's own path, for the env
    DBSS DOS_B_LN,    DOS_LNSZ  ; the arguments field's block (os88line.inc)
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
    DBSS DOS_B_ISEXE, 1
%ifdef DOSTRACE                 ; ...and NOTHING when it is off: the ring is
    DBSS DOS_B_TRACEN, 2        ; 514 bytes, and an instrument that costs the
    DBSS DOS_B_TRACEW, 2        ; shipped build anything is one that gets
    DBSS DOS_B_TRACEB, DOS_TRACEN * 32  ; deleted rather than kept
    DBSS DOS_B_TRACEI, 2                ; the entry a result belongs to, 0 =
                                        ; the call was filtered out
    DBSS DOS_B_TRNM,   DOS_TRNM_N * 13      ; the NAMES the program passed
    DBSS DOS_B_TRNMI,  1                    ; ...and how many, capped
    DBSS DOS_B_TRDUMP, DOS_TRDUMPN * 72 + DOS_TRNM_N * 15 + 96
%endif
    DBSS DOS_B_VW,    2
    DBSS DOS_B_VH,    2
    DBSS DOS_B_MLX,   2
    DBSS DOS_B_MLY,   2
    DBSS DOS_B_MLB,   1        ; the button mask the last state read saw
    DBSS DOS_B_MPC,   2        ; press counts, one BYTE per button
    DBSS DOS_B_MRC,   2        ; ...and release counts
    DBSS DOS_B_MPX,   2        ; where the last press landed, shared
    DBSS DOS_B_MPY,   2        ; between the buttons (SPEC.md 96.10.1)
    DBSS DOS_B_MRX,   2
    DBSS DOS_B_MRY,   2
    DBSS DOS_B_IMGHI, 2
    DBSS DOS_B_XFSEG, 2
    DBSS DOS_B_XLSEG, 2
    DBSS DOS_B_XHPAR, 2

; =============================================================================
; FILE HANDLES (SPEC.md 96.11)
; =============================================================================
; os8088 HAS NO FILE HANDLE ANYWHERE. The whole published API is by NAME and
; by WHOLE FILE - read a file into a buffer you sized, write or replace one
; from a buffer - so the handle layer is built here, out of those pieces, and
; docs/plans/DOS-EXEC-PLAN.md 6.3 is the design record for why it is here
; rather than in the kernel.
;
; What makes it work at all is ONE WINDOW: a buffer carved off the top of the
; arena before the program is told how much memory it has, holding a
; cluster-aligned span of one file. A read inside the window is a `movsb`; a
; read outside it refills with OSAPI_FILE_READ_AT, whose offset and capacity
; must BOTH be cluster multiples, which is the whole reason the window is
; aligned and cluster-sized rather than 512 bytes or "big".
;
; ONE handle owns the window at a time. Two open files interleaved thrash it
; and are correct; the alternative is a buffer per handle and the arena is the
; program's, not ours.
;
; WRITES ARE SEQUENTIAL, and that is the API's shape rather than a shortcut:
; OSAPI_FILE_APPEND refuses a file whose size is not a whole number of
; clusters, so the only append that can ever work is one onto a file this
; layer itself wrote in whole windows. A create-then-write-then-close is
; therefore exact, and a write anywhere else REFUSES (SPEC.md 96.11.2) rather
; than reporting a success it did not have.
DOS_FH0     equ 5                   ; 0..4 are the five devices DOS opens for
DOS_NFH     equ 8                   ; every process; files start after them
FH_NAME     equ 0                   ; char[13], NUL-terminated
FH_FLAGS    equ 13
FH_POS      equ 14                  ; dword
FH_SIZE     equ 18                  ; dword
FH_SIZEOF   equ 22
FHF_USED    equ 1
FHF_WRITE   equ 2                   ; opened by AH=3Ch: writes are accepted
FHF_MADE    equ 4                   ; ...and at least one window has been
                                    ; flushed, so the next one APPENDS
FHF_WHOLE   equ 8                   ; a COMPRESSED file, read whole and
                                    ; expanded: the window is the file and
                                    ; never refills (SPEC.md 96.11.1)

DVOL_MAX    equ 6                   ; MIRRORS the kernel's (kernel/assoc.inc).
                                    ; It is a CAPACITY here rather than a fact
                                    ; about the machine, and every use of it
                                    ; below is bound-checked - so a kernel that
                                    ; grows a seventh volume costs this box
                                    ; reach and can never cost it a write past
                                    ; its own bss, which is somebody else's
                                    ; heap claim
DOS_WKB     equ 8                   ; the window's floor in KB; a volume whose
                                    ; cluster is bigger gets a window of one
                                    ; cluster instead, because READ_AT cannot
                                    ; be asked for less

; -----------------------------------------------------------------------------
; dos_fh_setup - size and place the window, and take it OUT of the arena
; in:  [dos_arena] and [dos_apara] are set; called from dos_run
; out: CF=0, [dos_apara] reduced; CF=1 with AL = DER_MEM if the arena cannot
;      spare it
; -----------------------------------------------------------------------------
dos_fh_setup:
    push bx
    push cx
    push dx

    push di
    push es
    push ds
    pop es
    mov di, dos_fhtab               ; a launch starts with nothing open, and
    mov cx, FH_SIZEOF * DOS_NFH     ; saying so costs six bytes against a
    xor al, al                      ; stale handle surviving into a second run
    cld
    rep stosb
    pop es
    pop di

    mov byte [dos_wown], 0xFF       ; nobody owns it yet
    mov word [dos_wlen], 0
    mov byte [dos_wdirty], 0
    mov byte [dos_wfill], 0

    call dos_be_dfree               ; BX = SECTORS per cluster, and this is the
    jc .guess                       ; O(clusters) call the SDK warns about, so
    or bx, bx                       ; it is asked ONCE per launch and never in
    jnz .got                        ; a loop
.guess:
    mov bx, 2                       ; a volume that will not say: 1KB, which is
.got:                               ; the 360KB floppy's own and is a multiple
    mov cl, 9                       ; of every smaller one
    shl bx, cl                      ; sectors -> bytes
    mov [dos_cbytes], bx

    mov ax, DOS_WKB * 1024
    cmp bx, ax                      ; a cluster larger than the floor IS the
    jbe .round                      ; window: READ_AT cannot be asked for a
    mov ax, bx                      ; capacity that is not a multiple of one
    jmp short .have
.round:
    xor dx, dx                      ; ...otherwise the largest multiple of the
    div bx                          ; cluster that fits the floor, which for
    mul bx                          ; every power-of-two cluster IS the floor
.have:
    mov [dos_wbytes], ax
    mov cl, 4
    shr ax, cl                      ; bytes -> paragraphs; the window is always
    mov cx, ax                      ; a cluster multiple and so paragraph-round

    mov ax, [dos_apara]
    sub ax, cx
    jc .nomem
    cmp ax, DOS_PSPP + 0x100        ; 4KB past the PSP, or there is no program
    jb .nomem                       ; worth starting
    mov [dos_apara], ax
    add ax, [dos_arena]
    mov [dos_wseg], ax              ; ...which is the paragraph the arena now
    clc                             ; ends at, so the program can never see it
    jmp short .out
.nomem:
    mov al, DER_MEM
    stc
.out:
    pop dx
    pop cx
    pop bx
    ret

; =============================================================================
; FIND, DIRECTORIES AND THE CWD (SPEC.md 96.12)
; =============================================================================
; The DTA's first 21 bytes are the driver's own by DOS's own definition, and
; the whole walk lives there - the ordinal and the pattern - so AH=4Fh needs
; no state in the package at all, and two programs, or one program with two
; DTAs, cannot tread on each other. DOS does exactly this, for exactly that.
DTA_ORD     equ 0                   ; word: the kernel ordinal to ask next
DTA_PAT     equ 2                   ; char[13]: the pattern, as it was given
DTA_MASK    equ 15                  ; byte: the ATTRIBUTE MASK AH=4Eh was
                                    ; given, which DOS also keeps in the
                                    ; reserved head of the DTA. AH=4Fh needs
                                    ; it and is handed nothing but the DTA
DTA_ATTR    equ 21                  ; ...and from here it is DOS's PUBLISHED
DTA_TIME    equ 22                  ; layout, which the program reads
DTA_DATE    equ 24
DTA_SIZE    equ 26                  ; dword
DTA_NAME    equ 30                  ; char[13], NUL-terminated

; -----------------------------------------------------------------------------
; dos_dta_seg - ES:DI = the caller's DTA
; out: ES:DI; clobbers nothing else
; -----------------------------------------------------------------------------
dos_dta_seg:
    mov di, [dos_dta]
    mov es, [dos_dtaseg]
    ret

; -----------------------------------------------------------------------------
; dos_find_step - one step of a walk, into the DTA at ES:DI
; in:  ES:DI = the DTA, its ordinal and pattern set
; out: CF=0 and the DTA filled; CF=1 with AL = 18, "no more files"
; -----------------------------------------------------------------------------
dos_find_step:
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov [dos_dtasv], di             ; the caller's DTA, banked: the kernel's
    mov [dos_dtasvs], es            ; own record has to be read through OUR
    mov cx, [es:di+DTA_ORD]         ; ES and there is only one
.next:
    push ds
    pop es
    mov di, dos_fent
    call dos_be_find
    jc .none
    mov [dos_ford], cx
    cmp word [dos_fent+14], OSAPI_FT_UP
    je .next                        ; '..' is SYNTHESIZED (SPEC.md 19.5) and is
                                    ; not a file a DOS program can be shown
    mov di, [dos_dtasv]
    mov es, [dos_dtasvs]
    add di, DTA_PAT
    mov si, dos_fent
    call dos_wild                   ; DS:SI the name, ES:DI the pattern
    mov cx, [dos_ford]
    jne .next
    ; --- the name matches; does the ATTRIBUTE MASK allow it? ----------------
    ; AH=4Eh's CX is a mask and this used to ignore it, which is not a
    ; refinement: a program asking "what is this disk called" got handed the
    ; first ORDINARY FILE on it. Prince of Persia asks exactly that - mask 08h,
    ; pattern ????????.??? - to check it is running from its own floppy, and a
    ; disk with no label must answer NO MORE FILES. It got FAT.DAT and 28 more
    ; and refused to start (SPEC.md 96.12.1).
    mov di, [dos_dtasv]
    mov es, [dos_dtasvs]
    push ax
    mov al, [es:di+DTA_MASK]
    test al, 0x08
    jnz .skipit                     ; A VOLUME LABEL SEARCH matches the label
                                    ; and nothing else. A package cannot see
                                    ; one at all - the kernel reports labels to
                                    ; a DRIVER only - so the honest answer is
                                    ; the one a label-less disk gives anyway
    test byte [dos_fent+13], 0x10
    jz .allowed
    test al, 0x10
    jz .skipit                      ; a directory the caller did not ask for
.allowed:
    pop ax
    ; --- a hit ---------------------------------------------------------------
    mov [es:di+DTA_ORD], cx
    mov al, [dos_fent+13]
    mov [es:di+DTA_ATTR], al
    mov word [es:di+DTA_TIME], 0    ; the kernel's find record carries no
    mov word [es:di+DTA_DATE], 0    ; timestamp (SPEC.md 96.12.1), and 0 is
    mov ax, [dos_fent+18]           ; what an unset one looks like to DOS
    mov [es:di+DTA_SIZE], ax
    mov ax, [dos_fent+20]
    mov [es:di+DTA_SIZE+2], ax
    add di, DTA_NAME
    mov si, dos_fent
    mov cx, 13
    cld
    rep movsb
    clc
    jmp short .out
.skipit:
    pop ax
    jmp .next                       ; CX is already [dos_ford], which is what
                                    ; .next asks for
.none:
    mov al, 18
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_wild - does the 8.3 name at DS:SI match the pattern at ES:DI?
; out: ZF=1 on a match; every register preserved
;
; BOTH SIDES ARE EXPANDED TO THE ELEVEN-BYTE 8.3 FORM first - eight of name,
; three of extension, space-padded - because that is the only shape in which
; DOS's two wildcards mean what everyone expects. `*` fills THE REST OF ITS
; OWN FIELD and stops at the dot, so `*.TXT` matches `A.TXT` and not
; `A.TXTX`; and `?` stands for one character OR for the padding past a short
; name, which is why `A???????.TXT` finds `A.TXT`.
; -----------------------------------------------------------------------------
dos_wild:
    push ax
    push cx
    push si
    push di
    push ds
    push es

    push es                         ; the pattern's far pointer, banked while
    push di                         ; the NAME is expanded out of our own DS
    push ds
    pop es
    mov di, dos_w83a
    call dos_83
    pop si                          ; ...and now the pattern, whose segment is
    pop ds                          ; the program's
    push cs
    pop es
    mov di, dos_w83b
    call dos_83
    push es                         ; both buffers are ours, so both segments
    pop ds                          ; are too

    mov si, dos_w83a
    mov di, dos_w83b
    mov cx, 8
    call dos_wfld
    jne .out
    mov si, dos_w83a + 8
    mov di, dos_w83b + 8
    mov cx, 3
    call dos_wfld
.out:
    pop es
    pop ds
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_wfld - one 8.3 FIELD: CX bytes at DS:SI against the pattern at ES:DI
; out: ZF=1 on a match; clobbers AX, CX, SI, DI
; -----------------------------------------------------------------------------
dos_wfld:
    mov al, [es:di]
    cmp al, '*'
    je .yes                         ; the rest of this field, whatever it is
    cmp al, '?'
    je .step
    cmp al, [si]
    jne .no
.step:
    inc si
    inc di
    loop dos_wfld
.yes:
    xor al, al                      ; ZF=1
    ret
.no:
    mov al, 1
    or al, al                       ; ZF=0, and `or al, al` on a 0 would not
    ret                             ; say so - which is why AL is loaded first

; -----------------------------------------------------------------------------
; dos_83 - the NUL-terminated name at DS:SI into eleven bytes at ES:DI
; out: nothing; DI is left where it started. Clobbers AX, CX, SI
; -----------------------------------------------------------------------------
dos_83:
    push di
    push di
    mov al, ' '
    mov cx, 11
    cld
    rep stosb
    pop di
    push di
    mov cx, 8
.name:
    lodsb
    or al, al
    jz .done
    cmp al, '.'
    je .ext
    jcxz .name                      ; past eight: read on, store nothing
    stosb
    dec cx
    jmp short .name
.ext:
    pop di
    push di
    add di, 8
    mov cx, 3
.eloop:
    lodsb
    or al, al
    jz .done
    jcxz .eloop
    stosb
    dec cx
    jmp short .eloop
.done:
    pop di
    pop di
    ret

; -----------------------------------------------------------------------------
; dos_cd_go - AH=3Bh's body: stand in the directory [dos_fname] names
; out: CF=1 if there is no such directory, or it is out of reach
;
; THE LAUNCH DIRECTORY IS THE PROGRAM'S ROOT (SPEC.md 96.12.2). Nothing above
; it is reachable, `\` means it, and AH=47h answers a path relative to it.
; -----------------------------------------------------------------------------
dos_cd_go:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es

    cmp byte [dos_fabs], 0          ; "\" or "\NAME": from the VOLUME's root.
    je .rel                         ; There is no jail any more - a program
    xor dx, dx                      ; launched from a subdirectory may leave it
    mov bl, [dos_vol]               ; and may change drives, as it would under
    call dos_be_goto                ; DOS (SPEC.md 96.6.1)
    jc .no
    mov [dos_curdir], dx
    cmp byte [dos_fname], 0
    je .same                        ; a bare "\" is the whole request
.rel:
    mov al, [dos_fname]
    or al, al
    jz .same
    cmp al, '.'
    jne .named
    mov al, [dos_fname+1]
    or al, al
    jz .same                        ; "." is where we already are
    cmp al, '.'
    jne .named
    cmp byte [dos_fname+2], 0
    jne .named

    ; --- ".." IS A RE-DESCENT, and that is the whole trick ----------------
    ; A package cannot walk up: dsk_find drops the on-disk dot links, so
    ; OSAPI_FILE_FIND never reports '..'. What it CAN do since SPEC.md 19.2.4
    ; is ask where it is standing - so up is "take the path, drop the last
    ; component, walk down to what is left". No stack, no depth limit, and
    ; correct across a drive switch, which a recorded stack would not have
    ; been.
    cmp word [dos_curdir], 0
    je .same                        ; at a root, and DOS ignores '..' there
    mov di, dos_pbuf                ; (pbuf is free here: the link's working
    mov cx, DOS_PBUF                ; directory and the environment's program
    call OSAPI_FILE_PATH            ; path are both spent before the program
    jc .no                          ; runs, and this only happens while it does)
    add di, cx                      ; ...CX is the length, so DI is the NUL
.strip:
    cmp di, dos_pbuf
    jbe .cut
    dec di
    cmp byte [di], '\'
    jne .strip
.cut:
    mov byte [di], 0                ; "\A\B" -> "\A", and "\A" -> ""
    call dos_walk_pbuf
    jc .no
    mov [dos_curdir], dx
    jmp short .same

.named:
    xor cx, cx
.scan:
    mov di, dos_fent
    call dos_be_find
    jc .no
    cmp word [dos_fent+14], OSAPI_FT_DIR
    jb .scan                        ; a file is not somewhere to stand
    mov si, dos_fname
    mov di, dos_fent
    call dos_streq
    jne .scan
    mov dx, [dos_fent+16]
    mov bl, [dos_vol]
    call dos_be_goto
    jc .no
    mov [dos_curdir], dx
.same:
    clc
    jmp short .out
.no:
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

; =============================================================================
; DRIVES (SPEC.md 96.6.1)
; =============================================================================
; AH=0Eh used to answer the COUNT and never move, on the reasoning that a
; program reads the count far more often than it changes drives and that a
; real change wanted a directory walk this box did not have. The first half is
; true and is why the no-op path below is still free; the second stopped being
; true at SPEC.md 19.2.4.
;
; WHAT A STUB COSTS IS NOT THE SWITCH, IT IS THE ANSWER TO THE NEXT QUESTION.
; The way a program finds out whether a drive exists is to select it and then
; ask AH=19h where it is - so a select that silently does nothing reports
; every drive as invalid, including the ones that are there. That is what an
; installer moving from B: to a mounted C: was told.
; -----------------------------------------------------------------------------

; --- dos_cw_back - undo AH=47h's temporary visit to another drive -----------
; A no-op when it never left, which is the ordinary case.
dos_cw_back:
    push ax
    push dx
    mov al, [dos_cwdrv]
    or al, al
    jz .out
    cmp al, [dos_vol]
    jne .out
    mov dl, [dos_dvfrom]
    call dos_drv_sel
.out:
    pop dx
    pop ax
    ret

; --- dos_drv_bank - remember where drive AL is standing ---------------------
dos_drv_bank:
    push ax
    push bx
    mov bl, al
    xor bh, bh
    shl bx, 1
    mov ax, [dos_curdir]
    mov [bx+dos_dvcwd], ax
    pop bx
    pop ax
    ret

; --- dos_drv_recall - stand drive AL where it last was (0 = its root) -------
dos_drv_recall:
    push ax
    push bx
    mov bl, al
    xor bh, bh
    shl bx, 1
    mov ax, [bx+dos_dvcwd]
    mov [dos_curdir], ax
    pop bx
    pop ax
    ret

; --- dos_drv_count - how many volumes there are, probed ONCE ----------------
; out: AL = the count; every other register preserved
dos_drv_count:
    push bx
    push cx
    mov al, [dos_ndrv]
    or al, al
    jnz .out                    ; PROBED ONCE and remembered: AH=0Eh is called
    xor bl, bl                  ; for its count far more often than to change
    xor cl, cl                  ; drives, and six far calls an ask would be a
.probe:                         ; poll nobody asked for
    mov al, bl
    push bx
    push cx
    call OSAPI_VOL_KIND
    pop cx
    pop bx
    jc .gap
    inc cl
.gap:
    inc bl
    cmp bl, DVOL_MAX
    jb .probe
    or cl, cl
    jnz .have
    mov cl, 1                   ; a machine with no volume at all still has a
.have:                          ; drive as far as a DOS program is concerned
    mov [dos_ndrv], cl
    mov al, cl
.out:
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_drv_sel - AH=0Eh's body: stand on drive DL
; in:  DL = the drive, 0 = A
; out: nothing. The drive is UNCHANGED if DL names no volume, which is what
;      makes the AH=19h that follows a truthful answer either way
; clobbers: nothing but the flags
; -----------------------------------------------------------------------------
dos_drv_sel:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    cmp dl, [dos_vol]
    je .out                     ; already there, and this is the common case:
                                ; no volume probe, no mount, nothing
    cmp dl, DVOL_MAX
    jae .out                    ; past our own array: refused rather than
                                ; written past (see DVOL_MAX)
    mov [dos_dvtgt], dl
    mov al, dl
    call OSAPI_VOL_KIND         ; CF=1 = there is no such volume, and that is
    jc .out                     ; the whole of "invalid drive letter"
    mov al, [dos_vol]
    mov [dos_dvfrom], al
    call dos_drv_bank           ; bank where we are...
    mov al, [dos_dvtgt]
    mov [dos_vol], al
    call dos_drv_recall         ; ...and stand where that drive last was
    mov dx, [dos_curdir]
    mov bl, [dos_vol]
    call dos_be_goto            ; A REAL MOUNT, and only here: a switch across
    jnc .out                    ; volumes re-reads the boot sector (19.2.2)
    mov al, [dos_dvfrom]        ; the mount refused - put the whole switch
    mov [dos_vol], al           ; back, so a drive that cannot be reached
    call dos_drv_recall         ; leaves the program exactly where it was
    mov dx, [dos_curdir]
    mov bl, [dos_vol]
    call dos_be_goto            ; ...and this one worked a moment ago
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; THE DATE AND THE TIME (SPEC.md 96.13)
; =============================================================================
; There is NO date or time slot in the SDK at all, so this is the one group
; that goes to the ROM and the BDA directly - which is legitimate here and
; nowhere else: inside the bracket the machine is ours (SPEC.md 53.1), and it
; is the same place DOS gets them.
;
; THE TIME IS THE BIOS TICK COUNT AT 0040:006C, read DIRECTLY rather than
; through int 1Ah AH=00h, and that is a correctness choice and not a shortcut:
; AH=00h CLEARS the midnight-rollover flag as it answers, and the kernel's own
; clock is chained to the same counter (SPEC.md 8.5) - so asking the ROM would
; consume, once a day, the very event the kernel needs to advance ITS date.
; Reading the four bytes has no side effect at all, and midnight is detected
; here by the count going BACKWARDS, which needs nobody's flag.
;
; THE DATE IS OURS TO KEEP, which is what DOS does on a machine with no clock
; chip: the RTC is asked once at bracket entry and believed only if it answers
; something possible, and AH=2Bh writes into the same copy.
CLK_DEF_Y   equ 2026                ; MIRRORED from kernel/clock.inc, so a DOS
CLK_DEF_M   equ 7                   ; program and the menu bar agree about a
CLK_DEF_D   equ 4                   ; machine that has no clock to ask.
                                    ; tests/unit/t_mirror.py is what keeps them
                                    ; equal, because nothing else would notice

; -----------------------------------------------------------------------------
; dos_ticks - the BIOS tick count
; out: DX:AX; every other register preserved
; -----------------------------------------------------------------------------
dos_ticks:
    push bx
    push es
    mov bx, 0x40
    mov es, bx
    mov ax, [es:0x6C]
    mov dx, [es:0x6E]
    pop es
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_date_init - believe the RTC, or the kernel's fallback
; out: nothing; every register preserved
; -----------------------------------------------------------------------------
dos_date_init:
    push ax
    push bx
    push cx
    push dx
    mov word [dos_dy], CLK_DEF_Y
    mov byte [dos_dm], CLK_DEF_M
    mov byte [dos_dd], CLK_DEF_D

    mov ah, 0x04                    ; the RTC's date, BCD, AT and later
    int 0x1A
    jc .stamp                       ; no clock chip: the fallback stands
    mov al, ch                      ; ...AND A 5150's ROM DOES NOT SET CF FOR A
    call dos_unbcd                  ; FUNCTION IT HAS NEVER HEARD OF, so every
    mov bx, 100                     ; field below is checked for a value that
    mul bx                          ; is merely POSSIBLE before any of it is
    mov [dos_tmp1], ax              ; believed - which is the only thing
    mov al, cl                      ; standing between a garbage register and a
    call dos_unbcd                  ; date the program will stamp on its files
    add [dos_tmp1], ax
    mov ax, [dos_tmp1]
    cmp ax, 1980
    jb .stamp
    cmp ax, 2099
    ja .stamp
    mov [dos_tmp2], ax
    mov al, dh
    call dos_unbcd
    or al, al
    jz .stamp
    cmp al, 12
    ja .stamp
    mov [dos_tmp3], al
    mov al, dl
    call dos_unbcd
    or al, al
    jz .stamp
    cmp al, 31
    ja .stamp
    mov [dos_dd], al
    mov al, [dos_tmp3]
    mov [dos_dm], al
    mov ax, [dos_tmp2]
    mov [dos_dy], ax
.stamp:
    call dos_ticks                  ; the count midnight is measured against
    mov [dos_lasttl], ax
    mov [dos_lastth], dx
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_unbcd - AL from packed BCD to binary
; out: AX = 0..99; clobbers nothing else
; -----------------------------------------------------------------------------
dos_unbcd:
    push bx
    push cx
    mov bh, al
    and bh, 0x0F
    mov cl, 4
    shr al, cl
    mov ah, 10
    mul ah                          ; AX = tens * 10
    add al, bh
    adc ah, 0
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_date_roll - has midnight passed since anyone last looked?
; out: nothing; every register preserved
; -----------------------------------------------------------------------------
dos_date_roll:
    push ax
    push dx
    call dos_ticks
    cmp dx, [dos_lastth]
    jb .rolled                      ; the count going BACKWARDS is midnight,
    ja .keep                        ; and it needs no flag from the ROM
    cmp ax, [dos_lasttl]
    jae .keep
.rolled:
    call dos_date_inc
.keep:
    mov [dos_lasttl], ax
    mov [dos_lastth], dx
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_date_inc - one day on
; out: nothing; every register preserved
; -----------------------------------------------------------------------------
dos_date_inc:
    push ax
    push bx
    mov al, [dos_dd]
    inc al
    mov bl, [dos_dm]
    xor bh, bh
    dec bx
    mov ah, [bx+dos_mlen]
    cmp bl, 1                       ; February
    jne .chk
    test word [dos_dy], 3           ; the century rule cannot bite between 1980
    jnz .chk                        ; and 2099 - 2000 is a leap year by BOTH
    inc ah                          ; tests - so `and 3` is exact here
.chk:
    cmp al, ah
    jbe .store
    mov al, 1
    mov bl, [dos_dm]
    inc bl
    cmp bl, 12
    jbe .mok
    mov bl, 1
    inc word [dos_dy]
.mok:
    mov [dos_dm], bl
.store:
    mov [dos_dd], al
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_dow - the day of the week, Sakamoto's method
; out: AL = 0 Sunday .. 6 Saturday; clobbers AH
; -----------------------------------------------------------------------------
dos_dow:
    push bx
    push cx
    push dx
    mov cx, [dos_dy]
    mov bl, [dos_dm]
    xor bh, bh
    cmp bl, 3
    jae .nm
    dec cx                          ; January and February belong to the year
.nm:                                ; before, which is what makes the table work
    dec bx
    mov al, [bx+dos_dowt]
    xor ah, ah
    mov [dos_acc], ax
    mov al, [dos_dd]
    xor ah, ah
    add [dos_acc], ax
    add [dos_acc], cx
    mov ax, cx
    shr ax, 1
    shr ax, 1
    add [dos_acc], ax               ; + y/4
    mov ax, cx
    xor dx, dx
    mov bx, 100
    div bx
    sub [dos_acc], ax               ; - y/100
    mov ax, cx
    xor dx, dx
    mov bx, 400
    div bx
    add [dos_acc], ax               ; + y/400
    mov ax, [dos_acc]
    xor dx, dx
    mov bx, 7
    div bx
    mov ax, dx                      ; the remainder IS the day
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_time_now - the tick count as DOS's four fields
; out: CH = hours, CL = minutes, DH = seconds, DL = hundredths
;
; THE COUNT IS HALVED FIRST, because there are 65,543.4 ticks in an hour and
; that does not fit a 16-bit divisor - half of it does. What the whole chain
; costs in accuracy is about a second at the end of an hour, which is the
; same order as the drift a PC's own tick clock has against the wall: the
; divisors here are 32,772 / 1,092 / 18.2 against true values of 32,771.7 /
; 1,092.39 / 18.2065.
; -----------------------------------------------------------------------------
dos_time_now:
    push ax
    push bx
    call dos_ticks
    shr dx, 1
    rcr ax, 1
    mov bx, 32772
    div bx                          ; AX = hours, DX = half-ticks left over
    mov [dos_tmp1], al
    mov ax, dx
    shl ax, 1                       ; ...whole ticks again, 0..65,542
    xor dx, dx
    mov bx, 1092
    div bx
    cmp ax, 59
    jbe .m
    mov ax, 59                      ; 1092 against a true 1092.39 can round the
.m:                                 ; last minute of an hour up to 60
    mov [dos_tmp2], al
    mov ax, dx
    mov bx, 10
    mul bx
    mov bx, 182                     ; ticks in a second, times ten
    div bx
    cmp ax, 59
    jbe .s
    mov ax, 59
.s:
    mov [dos_tmp3], al
    mov ax, dx
    mov bx, 100
    mul bx
    mov bx, 182
    div bx
    mov dl, al                      ; hundredths
    mov dh, [dos_tmp3]
    mov ch, [dos_tmp1]
    mov cl, [dos_tmp2]
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_time_set - AH=2Dh's body: the four fields back into the tick count
; in:  CH = hours, CL = minutes, DH = seconds
; out: nothing; every register preserved
;
; It writes 0040:006C, which is banked at bracket entry and put back at the
; end (SPEC.md 96.5) - so a DOS program may set the clock, read it back and
; agree with itself, and the machine's own time is not moved by it.
; -----------------------------------------------------------------------------
dos_time_set:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov [dos_tmp1], ch
    mov [dos_tmp2], cl
    mov [dos_tmp3], dh

    mov al, [dos_tmp1]
    xor ah, ah
    mov bx, 32772
    mul bx
    shl ax, 1
    rcl dx, 1                       ; hours, in ticks
    mov si, ax
    mov di, dx
    mov al, [dos_tmp2]
    xor ah, ah
    mov bx, 1092
    mul bx
    add si, ax
    adc di, dx
    mov al, [dos_tmp3]
    xor ah, ah
    mov bx, 182
    mul bx
    mov bx, 10
    div bx
    xor dx, dx
    add si, ax
    adc di, dx

    mov bx, 0x40
    mov es, bx
    mov [es:0x6C], si
    mov [es:0x6E], di
    mov [dos_lasttl], si            ; ...and midnight is measured from here now
    mov [dos_lastth], di
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; AH=4Bh - LOADING AND RUNNING A CHILD (SPEC.md 96.14)
; =============================================================================
; -----------------------------------------------------------------------------
; dos_prog_enter - hand the CPU to the program at [dos_ldpsp]
; in:  [dos_ldpsp], [dos_isexe], [dos_prgsp] or the [dos_exe_*] four
; out: NEVER RETURNS BY FALLING OUT. dos_terminate is how control comes back,
;      and for a child it comes back to the word the CALLER's `call` pushed.
;
; The same door for the launched program and for AH=4Bh's child, which is
; what stops the two drifting: a .COM is entered at PSP:0100 and NOT PSP:0000
; - the first 256 bytes ARE the PSP and its first two are the `CD 20` a
; program's own `ret` lands on, so jumping to 0 runs that INT 20h and, from
; outside, is indistinguishable from a program that exited 0 having printed
; nothing.
; -----------------------------------------------------------------------------
dos_prog_enter:
    mov dx, [dos_ldpsp]             ; the PSP, which is DS and ES for both
    cmp byte [dos_isexe], 0         ; kinds (SPEC.md 96.3)
    je .com
    mov bx, [dos_exe_sp]            ; an .EXE brings its OWN stack, out of the
    mov cx, [dos_exe_ss]            ; header and relocated with everything else
    mov si, [dos_exe_cs]
    mov di, [dos_exe_ip]
    jmp short .go
.com:
    mov bx, [dos_prgsp]             ; a .COM runs on the PSP's own segment
    mov cx, dx
    mov si, dx
    mov di, 0x100
.go:
    mov byte [dos_onprog], 1        ; from here until dos_terminate, a kernel
                                    ; call has to borrow a stack (SPEC.md 96.4.1)
    cli                             ; SS and SP are loaded as a pair, always:
    mov ss, cx                      ; an interrupt between them lands on a
    mov sp, bx                      ; stack that is half of each
    sti
    mov ds, dx
    mov es, dx
    xor ax, ax                      ; AL/AH = the two FCB drive checks, and 0
                                    ; is "both valid"
    push si
    push di
    retf

; -----------------------------------------------------------------------------
; dos_exec_load - give the child a block, load it into it, and build its PSP
; in:  [dos_fname], [dos_xparm]/[dos_xparms] = the parameter block
; out: CF=0 with everything set for dos_prog_enter; CF=1 with AL = a DOS code
; -----------------------------------------------------------------------------
dos_exec_load:
    push bx
    push cx
    push dx
    push si
    push di
    push es

    mov ax, [dos_ldpsp]             ; BANK THE PARENT. It is still the running
    mov [dos_ppsp], ax              ; program, and everything below is about to
    mov [dos_parent], ax            ; describe the child instead
    mov ax, [dos_ldpara]
    mov [dos_ppara], ax
    mov ax, [dos_prgsp]
    mov [dos_pgpar], ax
    mov al, [dos_isexe]
    mov [dos_pexe], al

    mov bx, 0xFFFF                  ; THE LARGEST FREE BLOCK, asked for the way
    call dos_mcb_alloc              ; a program asks: 0FFFFh cannot be granted,
    jnc .nomem                      ; so the refusal is the answer and BX is it
    or bx, bx
    jz .nomem
    cmp bx, 64                      ; a PSP and a KB, or there is no point
    jb .nomem
    call dos_mcb_alloc              ; ...and now for real
    jc .nomem
    mov [dos_chblk], ax
    mov [dos_ldpsp], ax
    mov [dos_ldpara], bx
    mov word [dos_ldname], dos_fname

    call dos_load
    jc .noent
    call dos_is_exe
    jnc .com
    call dos_exe_setup              ; sets [dos_isexe] itself
    jc .bad
    jmp short .psp
.com:
    mov byte [dos_isexe], 0
    cmp word [dos_imghi], 0         ; a .COM is ONE segment
    jne .bad
    cmp word [dos_imgsz], 0xFF00
    ja .bad
.psp:
    call dos_psp_make
    call dos_exec_tail
    clc
    jmp short .out
.nomem:
    call dos_exec_back              ; the parent, whole again: a refusal must
    mov al, 8                       ; not leave the machine describing a child
    jmp short .err                  ; that never ran
.noent:
    call dos_exec_back
    mov al, 2
    jmp short .err
.bad:
    call dos_exec_unload
    call dos_exec_back
    mov al, 11                      ; "invalid format", which is DOS's own
.err:
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_exec_back - the parent is the running program again
; out: nothing; every register preserved
; -----------------------------------------------------------------------------
dos_exec_back:
    push ax
    mov word [dos_ldname], dos_name
    mov ax, [dos_ppsp]
    mov [dos_ldpsp], ax
    mov ax, [dos_ppara]
    mov [dos_ldpara], ax
    mov ax, [dos_pgpar]
    mov [dos_prgsp], ax
    mov al, [dos_pexe]
    mov [dos_isexe], al
    mov word [dos_parent], 0
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_exec_unload - the child's block, back to the chain
; out: nothing; every register preserved
; -----------------------------------------------------------------------------
dos_exec_unload:
    push ax
    push es
    mov ax, [dos_chblk]
    or ax, ax
    jz .out
    mov es, ax
    call dos_mcb_free
    mov word [dos_chblk], 0
.out:
    pop es
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_exec_tail - the parameter block's command tail into the child's PSP:0080
; out: nothing; every register preserved
;
; A zero SEGMENT means no tail, and the empty one dos_psp_make already wrote
; stands. The length byte is clamped to 126 because the tail plus its own
; count and the 0Dh have to live inside the PSP's 128.
; -----------------------------------------------------------------------------
dos_exec_tail:
    push ax
    push cx
    push si
    push di
    push ds
    push es
    mov es, [dos_xparms]
    mov di, [dos_xparm]
    mov si, [es:di+2]
    mov ax, [es:di+4]
    or ax, ax
    jz .none
    mov ds, ax
    mov ax, [cs:dos_ldpsp]          ; through CS: DS is the tail's now
    mov es, ax
    mov di, 0x80
    cld
    lodsb
    cmp al, 126
    jbe .len
    mov al, 126
.len:
    mov cl, al
    xor ch, ch
    stosb
    jcxz .term
    rep movsb
.term:
    mov al, 0x0D
    stosb
.none:
    pop es
    pop ds
    pop di
    pop si
    pop cx
    pop ax
    ret

; =============================================================================
; XMS - EXTENDED MEMORY (SPEC.md 96.15)
; =============================================================================
; A DOS program finds extended memory by asking the MULTIPLEX interrupt
; whether an XMS driver is there (int 2Fh AX=4300h), then asking the same
; interrupt for its entry point (AX=4310h) and far-calling that. So what is
; needed is the SHAPE of HIMEM.SYS over os8088's own pool, which the kernel
; already publishes as four slots: OSAPI_XMEM_CAPS, _ALLOC, _FREE and _COPY.
; No driver change, and no second allocator.
;
; THEY ARE UI-TASK SLOTS, so every one of them goes through dos_be_go and runs
; on the UI task's own stack (SPEC.md 96.4.1) - the same rule the file calls
; live under, and for the same reason.
;
; A HANDLE IS OURS, not the kernel's. OSAPI_XMEM_ALLOC answers a 32-bit linear
; base and XMS handles are 16-bit, so the table below is the mapping. It is
; small on purpose: the SDK's own advice is to take one big block and
; subdivide it rather than take many, and a program that wants more handles
; than this is a program that would exhaust the kernel's table too.
XMS_NH      equ 8
XH_BASE     equ 0                   ; dword: what the kernel handed back
XH_KB       equ 4                   ; word
XH_USED     equ 6
XH_SIZE     equ 8

; -----------------------------------------------------------------------------
; dos_int2f - the multiplex interrupt
; -----------------------------------------------------------------------------
dos_int2f:
    sti
    push bp
    push ds
    mov bp, sp
    push cs
    pop ds
    cmp ax, 0x4300
    je .installed
    cmp ax, 0x4310
    je .entry
    pop ds                          ; EVERY OTHER MULTIPLEX NUMBER IS ANSWERED
    pop bp                          ; "nobody is here", which is AL = 0 and is
    xor al, al                      ; what an unhooked 2Fh cannot say: before
    iret                            ; this the vector was the ROM's or nothing
.installed:
    call dos_xms_kb                 ; AX = KB the pool can hand out
    or ax, ax
    jz .absent                      ; NO STORE IS NOT AN XMS DRIVER (SPEC.md
    mov al, 0x80                    ; 96.15.1): on the 8088 this project is
    jmp short .out                  ; calibrated against there is none, and a
.absent:                            ; program that is told "yes" and then
    xor al, al                      ; refused every call is worse off than one
.out:                               ; told "no" and using conventional memory
    pop ds
    pop bp
    iret
.entry:
    mov bx, dos_xms_ent
    pop ds
    pop bp
    push cs
    pop es
    iret

; -----------------------------------------------------------------------------
; dos_xms_kb - the pool's free KB, through the back end
; out: AX = KB; clobbers nothing else
; -----------------------------------------------------------------------------
dos_xms_kb:
    push bx
    push cx
    push dx
    call dos_be_xcaps
    jnc .ok
    xor ax, ax
.ok:
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_xms_ent - the XMS entry point itself, FAR CALLED by the program
; in:  AH = the function; out: AX = 1 done / 0 refused with BL = the code
; -----------------------------------------------------------------------------
dos_xms_ent:
    push bp
    push ds
    mov bp, sp
    push cs
    pop ds

    cmp ah, 0x00
    je .ver
    cmp ah, 0x08
    je .query
    cmp ah, 0x09
    je .alloc
    cmp ah, 0x0A
    je .free
    cmp ah, 0x0B
    je .move
    cmp ah, 0x03                    ; the four A20 calls. WE DO NOT FIGHT OVER
    jb .nope                        ; A20 (SPEC.md 96.15.2): the kernel's own
    cmp ah, 0x07                    ; memory above 1MB is reached by the same
    ja .nope                        ; BIOS path, so the line is already however
    mov ax, 1                       ; it needs to be and a program toggling it
    xor bl, bl                      ; is told yes and changes nothing
    jmp .out
.nope:
    xor ax, ax
    mov bl, 0x80                    ; "not implemented", which is XMS's own
    jmp .out
.ver:
    mov ax, 0x0300                  ; XMS 3.0
    mov bx, 0
    xor dx, dx                      ; ...and NO HMA: the high memory area is a
    jmp .out                        ; 286 addressing trick and this is an 8086
                                    ; contract (SPEC.md 96.15.2)
.query:
    call dos_xms_kb
    mov dx, ax                      ; total free
    mov bl, 0                       ; ...and the largest, which for one pool
    or ax, ax                       ; with one free run is the same number
    jnz .out
    mov bl, 0xA0                    ; "all extended memory is allocated"
    jmp .out
.alloc:
    ; DX = KB wanted; out DX = the handle
    call dos_xms_new                ; SI = a free row, AX = its handle
    jc .nohand
    push si
    mov ax, dx
    mov dx, 1024
    mul dx                          ; DX:AX = bytes, and 64MB is the ceiling a
    call dos_be_xalloc              ; 16-bit KB count can even ask for
    pop si
    jc .noroom
    mov [si+XH_BASE], ax
    mov [si+XH_BASE+2], dx
    mov byte [si+XH_USED], 1
    mov dx, si
    sub dx, dos_xmstab
    mov ax, XH_SIZE
    push bx
    mov bx, ax
    mov ax, dx
    xor dx, dx
    div bx
    inc ax                          ; handles are 1-based: 0 means CONVENTIONAL
    pop bx                          ; memory in a move block
    mov dx, ax
    mov ax, 1
    xor bl, bl
    jmp .out
.nohand:
    xor ax, ax
    mov bl, 0xA1                    ; "all handles are in use"
    jmp .out
.noroom:
    xor ax, ax
    mov bl, 0xA0
    jmp .out
.free:
    ; DX = the handle
    mov ax, dx
    call dos_xms_row                ; SI = its row
    jc .badh
    mov ax, [si+XH_BASE]
    mov dx, [si+XH_BASE+2]
    call dos_be_xfree
    mov byte [si+XH_USED], 0
    mov ax, 1
    xor bl, bl
    jmp .out
.badh:
    xor ax, ax
    mov bl, 0xA2                    ; "invalid handle"
    jmp .out
.move:
    ; DS:SI = a sixteen-byte move block, and DS is the CALLER's
    call dos_xms_move
    jc .mvbad
    mov ax, 1
    xor bl, bl
    jmp short .out
.mvbad:
    xor ax, ax                      ; BL is dos_xms_move's own
.out:
    pop ds
    pop bp
    retf

; -----------------------------------------------------------------------------
; dos_xms_new - the first free handle row
; out: CF=0 with SI = the row; CF=1 if the table is full
; -----------------------------------------------------------------------------
dos_xms_new:
    push cx
    mov si, dos_xmstab
    mov cx, XMS_NH
.scan:
    cmp byte [si+XH_USED], 0
    je .got
    add si, XH_SIZE
    loop .scan
    stc
    jmp short .out
.got:
    clc
.out:
    pop cx
    ret

; -----------------------------------------------------------------------------
; dos_xms_row - the row handle AX names
; out: CF=0 with SI = the row; CF=1 if it is not an open handle
; -----------------------------------------------------------------------------
dos_xms_row:
    push ax
    push bx
    or ax, ax
    jz .no
    cmp ax, XMS_NH
    ja .no
    dec ax
    mov bl, XH_SIZE
    mul bl
    mov si, ax
    add si, dos_xmstab
    cmp byte [si+XH_USED], 0
    je .no
    pop bx
    pop ax
    clc
    ret
.no:
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; dos_xms_move - AH=0Bh's body
; in:  the caller's DS:SI -> the move block; [bp] = the caller's DS
; out: CF=0 done; CF=1 with BL = an XMS error code
;
; ONE END MUST BE CONVENTIONAL. OSAPI_XMEM_COPY moves between a conventional
; address and a linear extended one, in either direction, and has no
; extended-to-extended form at all - so a move with two extended ends is
; REFUSED rather than bounced through a buffer the program did not give us.
; -----------------------------------------------------------------------------
dos_xms_move:
    push ax
    push cx
    push dx
    push di
    push es
    push ds

    mov ds, [bp]                    ; the block is the CALLER's
    mov ax, [si]                    ; the length, which must be even
    mov dx, [si+2]
    mov [cs:dos_xmlen], ax
    mov [cs:dos_xmlen+2], dx
    test al, 1
    jnz .badlen
    mov ax, [si+4]
    mov [cs:dos_xmsh], ax           ; the source handle...
    mov ax, [si+6]
    mov [cs:dos_xmso], ax           ; ...and its offset, far or linear
    mov ax, [si+8]
    mov [cs:dos_xmso+2], ax
    mov ax, [si+10]
    mov [cs:dos_xmdh], ax
    mov ax, [si+12]
    mov [cs:dos_xmdo], ax
    mov ax, [si+14]
    mov [cs:dos_xmdo+2], ax
    push cs
    pop ds

    mov ax, [dos_xmsh]
    or ax, ax
    jz .fromconv
    mov ax, [dos_xmdh]
    or ax, ax
    jnz .bothx
    ; --- extended -> conventional ------------------------------------------
    mov ax, [dos_xmsh]
    call dos_xms_row
    jc .badsh
    mov ax, [si+XH_BASE]
    mov dx, [si+XH_BASE+2]
    add ax, [dos_xmso]
    adc dx, [dos_xmso+2]
    mov [dos_xmlin], ax
    mov [dos_xmlin+2], dx
    mov ax, [dos_xmdo]              ; the conventional end, as a far pointer
    mov dx, [dos_xmdo+2]
    mov word [dos_xmdir], 1
    jmp short .run
.fromconv:
    mov ax, [dos_xmdh]
    or ax, ax
    jz .bothc
    call dos_xms_row
    jc .baddh
    mov ax, [si+XH_BASE]
    mov dx, [si+XH_BASE+2]
    add ax, [dos_xmdo]
    adc dx, [dos_xmdo+2]
    mov [dos_xmlin], ax
    mov [dos_xmlin+2], dx
    mov ax, [dos_xmso]
    mov dx, [dos_xmso+2]
    mov word [dos_xmdir], 0
.run:
    mov [dos_xmcon], ax             ; ES:SI for the copy, kept whole because
    mov [dos_xmcon+2], dx           ; the chunk loop below moves BOTH ends
.chunk:
    mov ax, [dos_xmlen]
    mov dx, [dos_xmlen+2]
    mov cx, ax
    or dx, dx
    jnz .big
    or cx, cx
    jz .done
    cmp cx, 32768
    jbe .go
.big:
    mov cx, 32768                   ; the slot's own ceiling, and the reason it
.go:                                ; has one is its interrupts-off window
    push cx
    mov es, [dos_xmcon+2]
    mov si, [dos_xmcon]
    mov ax, [dos_xmlin]
    mov dx, [dos_xmlin+2]
    mov di, [dos_xmdir]
    call dos_be_xcopy
    pop cx
    jc .ioerr
    sub [dos_xmlen], cx             ; ...and every pointer forward by what went
    sbb word [dos_xmlen+2], 0
    add [dos_xmlin], cx
    adc word [dos_xmlin+2], 0
    add [dos_xmcon], cx             ; a 32KB step cannot carry a paragraph-
    jnc .chunk                      ; aligned offset past 64KB by more than
    add word [dos_xmcon+2], 0x1000  ; one segment's worth
    jmp short .chunk
.done:
    clc
    jmp short .out
.bothc:
    mov bl, 0x8E                    ; conventional to conventional: a program
    jmp short .err                  ; with two far pointers can `movsb`
.bothx:
    mov bl, 0x8E                    ; ...and extended to extended has no slot
    jmp short .err
.badsh:
    mov bl, 0xA3
    jmp short .err
.baddh:
    mov bl, 0xA5
    jmp short .err
.badlen:
    push cs
    pop ds
    mov bl, 0xA7
    jmp short .err
.ioerr:
    mov bl, 0xA8
.err:
    stc
.out:
    pop ds
    pop es
    pop di
    pop dx
    pop cx
    pop ax
    ret


; =============================================================================
; THE DRIVERS, OUT OF THE WAY (SPEC.md 96.17)
; =============================================================================
; A DOS program that wants the Sound Blaster wants to program it ITSELF -
; reset the DSP, set its own IRQ and DMA, own the card completely - and
; os8088's SOUND.DRV is in the way of that in three separate ways: it owns an
; IRQ vector, it owns DMA channel 1, and its refill worker is TF_SERVICE, so
; it KEEPS RUNNING inside the bracket by design (SPEC.md 53.2) and can feed
; the DSP while the DOS program is resetting it.
;
; SPEC.md 51.11 is the door: one call, and every driver that owns hardware is
; unloaded - service table, worker, vector, memory and all. Two things follow
; that are worth saying here rather than leaving to be discovered:
;
; THE DRIVER IS NOT MOUNTED ONLY BY SYSTEM.CFG. SPEC.md 51.3.1's boot sniff
; runs an OPL timer dance and sets the sound row's want bit, so a machine with
; a card and NO SYSTEM.CFG AT ALL mounts the driver - which is to say the
; common case on a machine with a sound card is that the driver IS there.
;
; RESUME IS CALLED ON EVERY EXIT PATH, including the ones that refuse before
; the bracket ever opened, because a resume with nothing suspended is free and
; a machine left silent is not. SPEC.md 51.11.1 puts that rule on the caller
; and this is the caller.

; -----------------------------------------------------------------------------
; dos_drv_take - the hardware drivers, out of the way; BLASTER= from what they
;                say on the way past
; in:  inside the bracket, on the exclusive task
; out: nothing; [dos_blaster] is a string or an empty one
; -----------------------------------------------------------------------------
dos_drv_take:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es

    mov byte [dos_blaster], 0
    push ds
    pop es
    mov di, dos_dqbuf
    mov al, 1
    call OSAPI_DRV_SUSPEND          ; AX = the classes, CX = records
    jc .out                         ; not our bracket: nothing moved
    mov [dos_drvmask], ax
    jcxz .out
    mov si, dos_dqbuf
.rec:
    cmp byte [si+DQ_CLASS], DRVC_SOUND
    je .sound
    add si, DQ_SIZE
    loop .rec
    jmp short .out
.sound:
    call dos_blaster_set
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
; dos_drv_back - ...and back again
; out: nothing; every register preserved
; -----------------------------------------------------------------------------
dos_drv_back:
    push ax
    push cx
    push di
    push es
    push ds
    pop es
    xor di, di
    xor al, al
    call OSAPI_DRV_SUSPEND
    mov word [dos_drvmask], 0
    pop es
    pop di
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_blaster_set - "BLASTER=A220 I5 D1 T4" from the record at SI
; in:  SI = a DQ record whose class is DRVC_SOUND
; out: nothing; [dos_blaster] written
;
; THE TYPE IS DERIVED FROM THE DSP VERSION, which is what every DOS program
; that reads this variable expects: 1 is an original Sound Blaster, 3 a 2.0,
; 4 a Pro and 6 an SB16. Getting it wrong does not stop a program running -
; almost all of them only parse A, I and D - but a program that picks its
; stereo path off T would pick the wrong one.
; -----------------------------------------------------------------------------
dos_blaster_set:
    push ax
    push bx
    push cx
    push si
    push di
    push ds
    pop es
    cld
    mov di, dos_blaster
    mov bx, si
    mov si, dos_s_blast             ; "BLASTER=A"
.hdr:
    lodsb
    or al, al
    jz .port
    stosb
    jmp short .hdr
.port:
    mov ax, [bx+DQ_A]               ; the base port, in hex as DOS writes it
    call dos_hex3
    mov al, ' '
    stosb
    mov al, [bx+DQ_B]               ; THE IRQ, IF THERE IS ONE TO HAVE. The
    cmp al, 0xFF                    ; driver defers discovery to first use
    je .noirq                       ; (SPEC.md 34.5), so a machine that has
    push ax                         ; not played a sound yet genuinely does
    mov al, 'I'                     ; not know - and a BLASTER= naming the
    stosb                           ; WRONG line sends a program to wait on an
    pop ax                          ; interrupt that never comes, where its
    call dos_dec2                   ; absence sends it to its own default and
    mov al, ' '                     ; lets it own the guess (SPEC.md 96.17.1)
    stosb
.noirq:
    mov al, 'D'
    stosb
    mov al, [bx+DQ_B+1]
    call dos_dec2
    mov al, ' '
    stosb
    mov al, 'T'
    stosb
    mov al, [bx+DQ_C+1]             ; the DSP's MAJOR version
    cmp al, 4
    jb .t3
    mov al, '6'                     ; 4.xx is an SB16
    jmp short .temit
.t3:
    cmp al, 3
    jb .t2
    mov al, '4'                     ; 3.xx is a Pro
    jmp short .temit
.t2:
    cmp al, 2
    jb .t1
    mov al, '3'                     ; 2.xx
    jmp short .temit
.t1:
    mov al, '1'                     ; ...and anything older is the original
.temit:
    stosb
    xor al, al
    stosb
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_hex3 - AX's low twelve bits as three hex digits at ES:DI (DI advanced)
; -----------------------------------------------------------------------------
dos_hex3:
    push ax
    push bx
    push cx
    push dx
    mov dx, ax
    mov cx, 3
.next:
    mov ax, dx
    push cx
    dec cx
    shl cx, 1
    shl cx, 1                   ; CL = 8, then 4, then 0
    shr ax, cl
    pop cx
    and al, 0x0F
    add al, '0'
    cmp al, '9'
    jbe .emit
    add al, 7
.emit:
    stosb
    loop .next
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_dec2 - AL (0..99) as one or two digits at ES:DI
; An SB16 can be on IRQ 10, so one digit is not enough and the second one is
; four instructions.
; -----------------------------------------------------------------------------
dos_dec2:
    push ax
    push bx
    cmp al, 99                      ; A TWO-DIGIT EMITTER MUST NEVER EMIT A
    jbe .ok                         ; LETTER, and this one did: handed 255 -
    mov al, 99                      ; which is the sound driver's "no IRQ
.ok:                                ; discovered yet" - it divided to 25 and 5
    cmp al, 10                      ; and wrote '0'+25, so a BLASTER= read
    jb .one                         ; `I5` where it meant 255
    xor ah, ah
    mov bl, 10
    div bl
    push ax
    add al, '0'
    stosb
    pop ax
    mov al, ah
.one:
    add al, '0'
    stosb
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_fh_setname - [dos_fname] into the record at SI
; in:  SI = the record; out: nothing, every register preserved
; -----------------------------------------------------------------------------
dos_fh_setname:
    push cx
    push si
    push di
    push es
    push ds
    pop es
    mov di, si
    add di, FH_NAME
    mov si, dos_fname
    mov cx, 13
    cld
    rep movsb
    pop es
    pop di
    pop si
    pop cx
    ret

; -----------------------------------------------------------------------------
; dos_fh_touch - make the zero-length file the record at SI names
; in:  SI = the record; out: CF=1 with AL = a DOS error code
; -----------------------------------------------------------------------------
dos_fh_touch:
    push bx
    push cx
    push dx
    push si
    push es
    push ds
    pop es                          ; a count of 0 reads no buffer, but ES:BX
    xor bx, bx                      ; still has to be an address
    xor cx, cx
    xor dx, dx
    add si, FH_NAME
    call dos_be_write
    pop es
    pop si
    pop dx
    pop cx
    pop bx
    jc .err
    or byte [si+FH_FLAGS], FHF_MADE
    clc
    ret
.err:
    mov al, 5
    stc
    ret

; -----------------------------------------------------------------------------
; dos_fh_rdloop - AH=3Fh's body
; in:  SI = the record, CX = the bytes wanted, DX = the offset in the
;      PROGRAM's segment, [bp] = its DS
; out: CF=0 with AX = the bytes delivered (0 = end of file); CF=1 with AL = a
;      DOS error code
;
; THE COUNT LIVES IN BX and not in CX, because dos_fh_fill answers a chunk
; size in CX and `rep movsb` eats it - a loop counter in the same register as
; the primitive's answer is one that reads as a short read.
; -----------------------------------------------------------------------------
dos_fh_rdloop:
    push bx
    push cx
    push dx
    push si
    push di
    push es

    mov di, dx                      ; ES:DI walks the PROGRAM's buffer
    mov es, [bp]
    xor dx, dx                      ; ...and DX counts what has been delivered

    mov ax, [si+FH_SIZE]            ; NEVER PAST THE END, which is what turns a
    sub ax, [si+FH_POS]             ; read loop round: DOS answers short and
    mov bx, ax                      ; then 0, and a program reads until 0
    mov ax, [si+FH_SIZE+2]
    sbb ax, [si+FH_POS+2]
    jc .rdone                       ; the position is past the size
    jnz .rcap                       ; 64KB or more left, so the ask binds
    cmp bx, cx
    jae .rcap
    mov cx, bx
.rcap:
    mov bx, cx
.rchunk:
    or bx, bx
    jz .rdone
    call dos_fh_fill                ; AX = the offset in the window, CX = what
    jc .rerr                        ; is there
    jcxz .rdone                     ; end of file inside the walk
    cmp cx, bx
    jbe .rcopy
    mov cx, bx
.rcopy:
    push cx
    push si
    push ds
    mov si, ax
    mov ax, [dos_wseg]
    mov ds, ax
    cld
    rep movsb                       ; the window -> the program's buffer, and
    pop ds                          ; DI is left advanced, which is the point
    pop si
    pop cx
    sub bx, cx
    add dx, cx
    add [si+FH_POS], cx
    adc word [si+FH_POS+2], 0
    jmp short .rchunk
.rdone:
    mov ax, dx
    clc
    jmp short .rout
.rerr:
    stc
.rout:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_fh_wrloop - AH=40h's body for a file handle
; in:  SI = the record, CX = the bytes, DX = the offset in the PROGRAM's
;      segment, [bp] = its DS
; out: CF=0 with AX = the bytes written; CF=1 with AL = a DOS error code
; -----------------------------------------------------------------------------
dos_fh_wrloop:
    push bx
    push cx
    push dx
    push si
    push di
    push es

    mov di, dx                      ; DI walks the PROGRAM's buffer
    mov bx, cx                      ; BX = what is still to go
    xor dx, dx                      ; DX counts what has gone in
.wchunk:
    or bx, bx
    jz .wdone
    call dos_fh_take                ; for a write the window is an accumulator
    jc .werr                        ; rather than a view
    mov cx, [dos_wbytes]
    sub cx, [dos_wlen]
    jnz .wroom
    call dos_fh_flush               ; full - and a full window is a cluster
    jc .werr                        ; multiple, which is what keeps the next
    mov cx, [dos_wbytes]            ; APPEND legal
.wroom:
    cmp cx, bx
    jbe .wcopy
    mov cx, bx
.wcopy:
    push cx
    push si
    push ds
    mov si, di                      ; source: the program's buffer
    mov di, [dos_wlen]              ; destination: the window's free end, read
    mov ax, [dos_wseg]              ; while DS is still OURS
    mov es, ax
    mov ds, [bp]
    cld
    rep movsb
    pop ds
    mov di, si                      ; the source pointer, advanced by the copy
    pop si
    pop cx
    add [dos_wlen], cx
    mov byte [dos_wdirty], 1
    sub bx, cx
    add dx, cx
    add [si+FH_POS], cx             ; a sequential write moves both, and they
    adc word [si+FH_POS+2], 0       ; stay equal, which is the invariant
    add [si+FH_SIZE], cx            ; .fwrite refuses on
    adc word [si+FH_SIZE+2], 0
    jmp short .wchunk
.wdone:
    mov ax, dx
    clc
    jmp short .wout
.werr:
    stc
.wout:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_fh_slot - the record for handle BX
; in:  BX = a DOS handle
; out: CF=0 with SI = the record and BX = the index 0..DOS_NFH-1; CF=1 if it
;      is not an open file handle
; -----------------------------------------------------------------------------
dos_fh_slot:
    push ax
    cmp bx, DOS_FH0
    jb .no
    cmp bx, DOS_FH0 + DOS_NFH
    jae .no
    sub bx, DOS_FH0
    mov ax, FH_SIZEOF
    mul bl
    mov si, ax
    add si, dos_fhtab
    test byte [si+FH_FLAGS], FHF_USED
    jz .no
    mov [dos_fhix], bl              ; THE INDEX LIVES HERE and not in a
    pop ax                          ; register: the window's owner is asked
    clc                             ; for at four call sites down two levels,
    ret                             ; and threading BL through all of them is
                                    ; how one of them ends up holding a count
.no:
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; dos_fh_new - the first free handle
; out: CF=0 with BX = the DOS handle and SI = the record, zeroed; CF=1 if the
;      table is full
; -----------------------------------------------------------------------------
dos_fh_new:
    push ax
    push cx
    push di
    push es
    push ds
    pop es
    mov si, dos_fhtab
    xor bx, bx
.scan:
    test byte [si+FH_FLAGS], FHF_USED
    jz .free
    add si, FH_SIZEOF
    inc bx
    cmp bx, DOS_NFH
    jb .scan
    stc
    jmp short .out
.free:
    mov [dos_fhix], bl
    ; --- AND THE WINDOW CANNOT SURVIVE ITS FILE (SPEC.md 96.11.5) ----------
    ; dos_fh_take decides whether the window already holds the right bytes by
    ; comparing this record's INDEX with the window's owner - so a handle that
    ; is closed and another opened lands on the same index, `take` says "mine",
    ; and the new file is read out of the old one's window. The close has
    ; already flushed anything dirty, so disowning is the whole of it.
    cmp bl, [dos_wown]
    jne .nowin
    mov byte [dos_wown], 0xFF
    mov byte [dos_wfill], 0
    mov word [dos_wlen], 0
.nowin:
    mov di, si                      ; a reused slot must not inherit a stale
    mov cx, FH_SIZEOF               ; name or position from the last program's
    xor al, al                      ; file
    cld
    rep stosb
    add bx, DOS_FH0
    clc
.out:
    pop es
    pop di
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_fh_name - copy a program's ASCIZ path into [dos_fname], 8.3 and upper
; in:  DX = the offset in the PROGRAM's segment, [bp] = its DS
; out: CF=0; CF=1 with AL = a DOS error code for a path this wave cannot walk
; clobbers: nothing else
;
; A DRIVE LETTER THAT NAMES OUR OWN VOLUME IS STRIPPED AND NOT REFUSED - it is
; what a program echoes back out of its own command line - and a SUBDIRECTORY
; is refused with "path not found" rather than silently opened in the current
; one, which would hand the program the wrong file under the right name.
; -----------------------------------------------------------------------------
dos_fh_name:
    push bx
    push cx
    push si
    push di
    push es
    push ds
    pop es
    mov di, dos_fname
    mov si, dx
    mov ds, [bp]                    ; the program's, off the frame
    mov cx, 13

    cmp byte [si+1], ':'            ; "C:NAME" - drop the drive, whatever it
    jne .nodrv                      ; is: the map is the identity with one
    add si, 2                       ; hole in it (SPEC.md 96.6) and a program
.nodrv:                             ; that names its own is naming ours
    cmp byte [si], '.'              ; ".\NAME" and "./NAME"
    jne .nodot
    cmp byte [si+1], '\'
    je .skip2
    cmp byte [si+1], '/'
    jne .nodot
.skip2:
    add si, 2
.nodot:
    mov byte [es:dos_fabs], 0       ; A LEADING SEPARATOR IS STRIPPED AND
    cmp byte [si], '\'              ; REMEMBERED (SPEC.md 96.12.2): "\" is the
    je .abs                         ; program's own root, and "\NAME" is one
    cmp byte [si], '/'              ; step down from it. An EMBEDDED one is
    jne .copy                       ; still refused below - this wave stands in
.abs:                               ; one directory at a time
    inc si
    mov byte [es:dos_fabs], 1
.copy:
    lodsb
    cmp al, '\'                     ; a separator ANYWHERE past here is a path,
    je .path                        ; and this wave stands in one directory
    cmp al, '/'
    je .path
    cmp al, 'a'
    jb .store
    cmp al, 'z'
    ja .store
    sub al, 32                      ; 8.3 names are upper case on the disk
.store:
    stosb
    or al, al
    jz .done
    loop .copy
    mov al, 3                       ; longer than 8.3 can be: "path not found"
    jmp short .bad
.path:
    mov al, 3
.bad:
    push es
    pop ds
    stc
    jmp short .out
.done:
    push es
    pop ds
%ifdef DOSTRACE
    call dos_tr_name_in             ; WHICH FILE - AH/AL alone cannot say, and
%endif                              ; that is the question a field trace asks
    clc
.out:
    pop es
    pop di
    pop si
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_fh_stat - find [dos_fname] in the current directory
; out: CF=0 with DX:AX = its size and BL = OSAPI_FIND_CZ bits; CF=1 if there
;      is no such file
; -----------------------------------------------------------------------------
dos_fh_stat:
    push cx
    push si
    push di
    push es
    push ds
    pop es
    xor cx, cx
.next:
    mov di, dos_fent
    call dos_be_find
    jc .no
    cmp word [dos_fent+14], OSAPI_FT_DIR
    jae .next                       ; a folder is not a file, and '..' is not
    mov si, dos_fname               ; either
    mov di, dos_fent
    call dos_streq
    jne .next
    mov ax, [dos_fent+18]
    mov dx, [dos_fent+20]
    mov bl, [dos_fent+22]
    pop es
    pop di
    pop si
    pop cx
    clc
    ret
.no:
    pop es
    pop di
    pop si
    pop cx
    stc
    ret

; -----------------------------------------------------------------------------
; dos_streq - compare the NUL-terminated strings at DS:SI and ES:DI
; out: ZF=1 equal; clobbers nothing but the flags
; -----------------------------------------------------------------------------
dos_streq:
    push si
    push di
    push ax
.loop:
    mov al, [si]
    cmp al, [es:di]
    jne .out
    or al, al
    jz .out
    inc si
    inc di
    jmp short .loop
.out:
    pop ax
    pop di
    pop si
    ret

; -----------------------------------------------------------------------------
; dos_fh_flush - write the window out if it is dirty
; out: CF=0; CF=1 with AL = a DOS error code. Preserves everything else.
;
; THE FIRST FLUSH REPLACES AND EVERY ONE AFTER IT APPENDS, which is exactly
; what makes AH=3Ch's truncate free and what keeps OSAPI_FILE_APPEND's
; cluster-multiple rule satisfied: a window is a cluster multiple by
; construction, so the file's size is one until the LAST flush - which is
; allowed to be short because nothing appends after it.
; -----------------------------------------------------------------------------
dos_fh_flush:
    push ax
    push bx
    push cx
    push dx
    push si
    push es

    cmp byte [dos_wdirty], 0
    je .ok
    mov bl, [dos_wown]
    cmp bl, 0xFF
    je .ok
    mov cx, [dos_wlen]
    jcxz .clean

    xor bh, bh
    mov al, FH_SIZEOF
    mul bl
    mov si, ax
    add si, dos_fhtab
    mov al, [si+FH_FLAGS]
    add si, FH_NAME
    mov bx, [dos_wseg]
    mov es, bx
    xor bx, bx
    test al, FHF_MADE
    jnz .append
    xor dx, dx
    call dos_be_write
    jc .err
    sub si, FH_NAME
    or byte [si+FH_FLAGS], FHF_MADE
    jmp short .clean
.append:
    call dos_be_append
    jc .err
.clean:
    mov byte [dos_wdirty], 0
    mov word [dos_wlen], 0
.ok:
    clc
    jmp short .out
.err:
    mov byte [dos_wdirty], 0        ; do not retry it for ever - one write that
    mov word [dos_wlen], 0          ; will not go is reported once
    pop es
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    mov al, 5                       ; "access denied", which is what DOS
    stc                             ; answers for a write that will not go
    ret
.out:
    pop es
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_fh_take - give the window to the handle [dos_fhix] names
; out: CF=1 with AL = a DOS error if the previous owner would not flush
; -----------------------------------------------------------------------------
dos_fh_take:
    push bx
    mov bl, [dos_fhix]
    cmp bl, [dos_wown]
    je .mine
    call dos_fh_flush
    jc .out
    mov bl, [dos_fhix]
    mov [dos_wown], bl
    mov word [dos_wlen], 0
    mov word [dos_wbase], 0
    mov word [dos_wbase+2], 0
    mov byte [dos_wfill], 0         ; ...and the window holds nothing of the
.mine:                              ; new owner's file yet
    clc
.out:
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_fh_fill - make the window cover the handle's current position
; in:  SI = the record ([dos_fhix] is its index)
; out: CF=0 with AX = the offset into [dos_wseg] and CX = the bytes available
;      there, CX = 0 at end of file. CF=1 with AL = a DOS error.
;      Preserves BX, DX, SI, DI, ES.
;
; AX AND NOT DI, because the caller's DI is where the bytes are GOING and a
; source handed back in it costs a shuffle at every call site.
; -----------------------------------------------------------------------------
dos_fh_fill:
    push bx
    push dx
    push es

    call dos_fh_take
    jc .errp

    cmp byte [dos_wfill], 0         ; is the position already inside it?
    je .refill
    mov ax, [si+FH_POS]
    mov dx, [si+FH_POS+2]
    sub ax, [dos_wbase]
    sbb dx, [dos_wbase+2]
    jc .refill                      ; before the window
    or dx, dx
    jnz .refill                     ; more than 64KB past it
    cmp ax, [dos_wlen]
    jae .refill
    mov cx, [dos_wlen]
    sub cx, ax
    jmp .okp

.refill:
    test byte [si+FH_FLAGS], FHF_WHOLE
    jnz .whole                      ; the window IS the file on that arm, and
                                    ; it is re-read rather than kept because
                                    ; another handle may have taken it
    mov ax, [si+FH_POS]             ; the cluster-aligned base under the
    mov dx, [si+FH_POS+2]           ; position. The cluster is a power of two,
    mov bx, [dos_cbytes]            ; so the mask is its own negation
    neg bx
    and ax, bx
    mov [dos_wbase], ax
    mov [dos_wbase+2], dx

    push si
    mov bx, [dos_wseg]
    mov es, bx
    xor bx, bx
    mov cx, [dos_wbytes]
    add si, FH_NAME
    call dos_be_rdat                ; out DX:AX = the bytes delivered, 0 at or
    pop si                          ; past the end
    jc .eof
    jmp short .got
.whole:
    mov word [dos_wbase], 0
    mov word [dos_wbase+2], 0
    push si
    mov bx, [dos_wseg]
    mov es, bx
    xor bx, bx
    mov cx, [dos_wbytes]
    xor dx, dx
    add si, FH_NAME
    call dos_be_read                ; EXPANDS on the way in (SPEC.md 20.14),
    pop si                          ; which is the whole reason this arm exists
    jc .eof
.got:
    or dx, dx
    jz .short
    mov ax, [dos_wbytes]            ; a delivery bigger than the window cannot
.short:                             ; happen, and clamping is two bytes
    cmp ax, [dos_wbytes]
    jbe .set
    mov ax, [dos_wbytes]
.set:
    mov [dos_wlen], ax
    mov byte [dos_wfill], 1
    or ax, ax
    jz .eof
    mov ax, [si+FH_POS]
    sub ax, [dos_wbase]
    cmp ax, [dos_wlen]
    jae .eof
    mov cx, [dos_wlen]
    sub cx, ax
    jmp short .okp
.eof:
    xor cx, cx
    xor ax, ax
.okp:
    clc
    jmp short .outp
.errp:
    stc
.outp:
    pop es
    pop dx
    pop bx
    ret

    DBSS DOS_B_XNREL, 2
    DBSS DOS_B_XRLOC, 2
    DBSS DOS_B_XMINA, 2
    DBSS DOS_B_XIPAR, 2
    DBSS DOS_B_XCS,   2
    DBSS DOS_B_XIP,   2
    DBSS DOS_B_XSS,   2
    DBSS DOS_B_XSP,   2
    DBSS DOS_B_FSI,   FSI_SIZE
    DBSS DOS_B_WSEG,  2        ; the file window (SPEC.md 96.11): the
    DBSS DOS_B_WBYTES,2        ; paragraph it starts at and its size, which
    DBSS DOS_B_CBYTES,2        ; is a multiple of the volume's cluster
    DBSS DOS_B_WOWN,  1        ; the handle index holding it, 0xFF = nobody
    DBSS DOS_B_WFILL, 1        ; ...and whether it holds anything of that
    DBSS DOS_B_WDIRTY,1        ; file, which "0 bytes at offset 0" cannot say
    DBSS DOS_B_WPAD,  1
    DBSS DOS_B_WBASE, 4        ; the file offset it starts at
    DBSS DOS_B_WLEN,  2        ; ...and the valid bytes in it
    DBSS DOS_B_FNAME, 16       ; the 8.3 name a call named
    DBSS DOS_B_FENT,  OSAPI_FIND_SZ
    DBSS DOS_B_BKSS,  2
    DBSS DOS_B_BKSP,  2
    DBSS DOS_B_BETGT, 2        ; the back end's own three words
    DBSS DOS_B_BEFLG, 2
    DBSS DOS_B_ONPRG, 1
    DBSS DOS_B_ONPAD, 1
    DBSS DOS_B_FHIX,  1        ; the window owner's index, set by every
    DBSS DOS_B_FHPAD, 1        ; slot resolution rather than threaded
    DBSS DOS_B_FHTAB, FH_SIZEOF * DOS_NFH
    DBSS DOS_B_DTA,   2        ; the Disk Transfer Area a find fills,
    DBSS DOS_B_DTASEG,2        ; PSP:0080 until AH=1Ah moves it
    DBSS DOS_B_DTASV, 2        ; ...banked while the kernel's own record is
    DBSS DOS_B_DTASVS,2        ; read through OUR ES
    DBSS DOS_B_FORD,  2        ; the ordinal a find walk resumes from
    DBSS DOS_B_W83A,  11       ; the two 8.3 forms dos_wild compares
    DBSS DOS_B_W83B,  11
    DBSS DOS_B_W83P,  2
    DBSS DOS_B_PARENT, 2       ; the PSP that launched the running program,
    DBSS DOS_B_INCHLD, 1       ; 0 at the top level (SPEC.md 96.14)
    DBSS DOS_B_XPAD,  1
    DBSS DOS_B_PSVSS, 2        ; ...and the stack it was on when it did
    DBSS DOS_B_PSVSP, 2
    DBSS DOS_B_PPSP,  2        ; the parent's own PSP/block, to put back
    DBSS DOS_B_PPARA, 2
    DBSS DOS_B_PGPAR, 2
    DBSS DOS_B_PEXE,  1
    DBSS DOS_B_PEPAD, 1
    DBSS DOS_B_CHEXIT, 1       ; the child's code, for AH=4Dh
    DBSS DOS_B_CHPAD, 1
    DBSS DOS_B_CHBLK, 2        ; the block it was given, to hand back
    DBSS DOS_B_DQBUF, DQ_SIZE * DQ_MAXREC  ; what the drivers said on their
    DBSS DOS_B_DRVMASK, 2      ; way out, and which classes went (96.17)
    DBSS DOS_B_BLAST, 32       ; "BLASTER=A220 I5 D1 T4", or empty
    DBSS DOS_B_XMSTAB, XH_SIZE * XMS_NH  ; the XMS handle table (96.15)
    DBSS DOS_B_XMLEN, 4        ; ...and AH=0Bh's move, unpacked out of the
    DBSS DOS_B_XMSH,  2        ; caller's sixteen-byte block
    DBSS DOS_B_XMSO,  4
    DBSS DOS_B_XMDH,  2
    DBSS DOS_B_XMDO,  4
    DBSS DOS_B_XMLIN, 4
    DBSS DOS_B_XMCON, 4
    DBSS DOS_B_XMDIR, 2
    DBSS DOS_B_XPARM, 2        ; AH=4Bh's parameter block, banked while the
    DBSS DOS_B_XPARMS, 2       ; name is copied out of the same segment
    DBSS DOS_B_LDNAME, 2       ; ...and which FILE it comes from
    DBSS DOS_B_LDPSP, 2        ; the PSP of the program being LOADED, and
    DBSS DOS_B_LDPAR, 2        ; its block - not always the arena's
    DBSS DOS_B_DY,    2        ; the date we keep (SPEC.md 96.13)
    DBSS DOS_B_DM,    1
    DBSS DOS_B_DD,    1
    DBSS DOS_B_LTL,   2        ; the tick count midnight is measured against
    DBSS DOS_B_LTH,   2
    DBSS DOS_B_TMP1,  2        ; the clock arithmetic's fields, held in memory
    DBSS DOS_B_TMP2,  2        ; rather than in registers a divide needs back
    DBSS DOS_B_TMP3,  2
    DBSS DOS_B_ACC,   2
    DBSS DOS_B_FABS,  1        ; did the name carry a leading separator?
    DBSS DOS_B_CURDIR, 2       ; the cluster we are standing in
; --- WHERE EACH DRIVE IS STANDING (SPEC.md 96.6.1) -------------------------
; DOS keeps a current directory per drive, and here that is one CLUSTER each
; and nothing else. It is that small because there is no jail: every drive's
; root is its volume's root, so a slot nobody has touched is 0 - which .bss
; already is, and which is exactly right. No "has this been initialised" flag,
; because there is no state a fresh drive could be in other than its root.
    DBSS DOS_B_DVCWD,  2 * DVOL_MAX
    DBSS DOS_B_DVTGT,  1            ; the drive a switch is going TO, banked
                                    ; because OSAPI_VOL_KIND promises nothing
                                    ; about DX
    DBSS DOS_B_DVFROM, 1            ; the drive a switch is leaving, for its
                                    ; own rollback
    DBSS DOS_B_NDRV,   1            ; the count AH=0Eh answers, probed once
    DBSS DOS_B_CWDST,  2            ; AH=47h: the program's buffer, banked
                                    ; across OSAPI_FILE_PATH, which wants ES:DI
                                    ; for its OWN answer
    DBSS DOS_B_CWDRV,  1            ; ...and the drive it was asked about
    DBSS DOS_B_IVT,   1024
    DBSS DOS_B_BDA,   256
DOS_BSS_SIZE equ DB

; os88ui.inc first (os88line.inc needs its UI_* macros), and both LAST -
; the header and the icon block are at fixed offsets in the image (SPEC.md
; 20.2), so code emitted between them fails the icon macro's own assertion.
%include "os88ui.inc"
%include "os88line.inc"

%if DOS_LNSZ != OS88LINE_SZ
 %error "DOS_LNSZ must equal os88line.inc's OS88LINE_SZ - the bss table above reserves DOS_LNSZ bytes for a block this file does not own"
%endif

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
dos_ctop    equ os88_image_end + DOS_B_CTOP    ; word: this paint's content top
dos_lnv     equ os88_image_end + DOS_B_LNV     ; word: LN_VIEW before a key
dos_lnl     equ os88_image_end + DOS_B_LNL     ; word: LN_LEN before a key
dos_ncell   equ os88_image_end + DOS_B_NCELL   ; word: cells the edits redrew
dos_nkey    equ os88_image_end + DOS_B_NKEY    ; word: ...over this many keys
dos_page    equ os88_image_end + DOS_B_PAGE    ; byte: DOS_PAGE_*
dos_brect   equ os88_image_end + DOS_B_BRECT   ; the page button's rect
dos_srect   equ os88_image_end + DOS_B_SRECT   ; ...and Save Shortcut's
dos_erp     equ os88_image_end + DOS_B_ERP     ; word: the row being emitted
dos_lbuf    equ os88_image_end + DOS_B_LBUF    ; a .LNK, read or written
dos_sbuf    equ os88_image_end + DOS_B_SBUF    ; `.\NAME.EXT` while building
dos_cname   equ os88_image_end + DOS_B_CNAME   ; one path component
dos_fbuf    equ os88_image_end + DOS_B_FBUF    ; OSAPI_FIND_SZ, for the walk
dos_wname   equ os88_image_end + DOS_B_WNAME   ; ...the name to write it under
dos_lend    equ os88_image_end + DOS_B_LEND    ; word: bytes of dos_lbuf read
dos_ebuf    equ os88_image_end + DOS_B_EBUF    ; the four environment rows
dos_eln     equ os88_image_end + DOS_B_ELN     ; ...and their os88line blocks
dos_args    equ os88_image_end + DOS_B_ARGS    ; 128: the command tail the user
                                               ; typed, without its count or
                                               ; its 0Dh - both are DOS's
                                               ; framing and go on at the PSP
dos_pbuf    equ os88_image_end + DOS_B_PBUF    ; the program's own path
dos_ln      equ os88_image_end + DOS_B_LN      ; the field's os88line block
dos_pic1    equ os88_image_end + DOS_B_PIC1    ; byte: the 8259 masks as found
dos_pic2    equ os88_image_end + DOS_B_PIC2    ; byte:
dos_isexe   equ os88_image_end + DOS_B_ISEXE   ; byte: 1 = an .EXE was set up
%ifdef DOSTRACE
dos_tracen  equ os88_image_end + DOS_B_TRACEN  ; word: DOSTRACE's call counter
dos_tracew  equ os88_image_end + DOS_B_TRACEW  ; word: its ring write index
dos_traceb  equ os88_image_end + DOS_B_TRACEB  ; the ring, 16 bytes an entry
dos_tracei  equ os88_image_end + DOS_B_TRACEI  ; ...the live entry's offset
dos_trnm    equ os88_image_end + DOS_B_TRNM   ; the names passed in
dos_trnmi   equ os88_image_end + DOS_B_TRNMI  ; ...how many so far
dos_trdump  equ os88_image_end + DOS_B_TRDUMP  ; ...rendered, for the file
%endif
dos_vw      equ os88_image_end + DOS_B_VW      ; word: the desktop's width...
dos_vh      equ os88_image_end + DOS_B_VH      ; word: ...and height, for 33h
dos_mou_lx  equ os88_image_end + DOS_B_MLX     ; word: the last position 0Bh
dos_mou_ly  equ os88_image_end + DOS_B_MLY     ; word: ...answered a delta from
dos_mou_lb  equ os88_image_end + DOS_B_MLB     ; byte: the mask the last state
dos_mou_pc  equ os88_image_end + DOS_B_MPC     ;       read saw, for the edges
dos_mou_rc  equ os88_image_end + DOS_B_MRC     ; 2 bytes each, INDEXED BY THE
dos_mou_px  equ os88_image_end + DOS_B_MPX     ; button number, so they are a
dos_mou_py  equ os88_image_end + DOS_B_MPY     ; pair and not two names
dos_mou_rx  equ os88_image_end + DOS_B_MRX
dos_mou_ry  equ os88_image_end + DOS_B_MRY
dos_wseg    equ os88_image_end + DOS_B_WSEG
dos_wbytes  equ os88_image_end + DOS_B_WBYTES
dos_cbytes  equ os88_image_end + DOS_B_CBYTES
dos_wown    equ os88_image_end + DOS_B_WOWN
dos_wfill   equ os88_image_end + DOS_B_WFILL
dos_wdirty  equ os88_image_end + DOS_B_WDIRTY
dos_wbase   equ os88_image_end + DOS_B_WBASE
dos_wlen    equ os88_image_end + DOS_B_WLEN
dos_fname   equ os88_image_end + DOS_B_FNAME
dos_fent    equ os88_image_end + DOS_B_FENT
dos_bk_ss   equ os88_image_end + DOS_B_BKSS
dos_bk_sp   equ os88_image_end + DOS_B_BKSP
dos_betgt   equ os88_image_end + DOS_B_BETGT
dos_beflg   equ os88_image_end + DOS_B_BEFLG
dos_onprog  equ os88_image_end + DOS_B_ONPRG
dos_fhix    equ os88_image_end + DOS_B_FHIX
dos_fhtab   equ os88_image_end + DOS_B_FHTAB
dos_dta     equ os88_image_end + DOS_B_DTA
dos_dtaseg  equ os88_image_end + DOS_B_DTASEG
dos_dtasv   equ os88_image_end + DOS_B_DTASV
dos_dtasvs  equ os88_image_end + DOS_B_DTASVS
dos_ford    equ os88_image_end + DOS_B_FORD
dos_w83a    equ os88_image_end + DOS_B_W83A
dos_w83b    equ os88_image_end + DOS_B_W83B
dos_parent  equ os88_image_end + DOS_B_PARENT
dos_inchild equ os88_image_end + DOS_B_INCHLD
dos_psv_ss  equ os88_image_end + DOS_B_PSVSS
dos_psv_sp  equ os88_image_end + DOS_B_PSVSP
dos_ppsp    equ os88_image_end + DOS_B_PPSP
dos_ppara   equ os88_image_end + DOS_B_PPARA
dos_pgpar   equ os88_image_end + DOS_B_PGPAR
dos_pexe    equ os88_image_end + DOS_B_PEXE
dos_chexit  equ os88_image_end + DOS_B_CHEXIT
dos_chblk   equ os88_image_end + DOS_B_CHBLK
dos_dqbuf   equ os88_image_end + DOS_B_DQBUF
dos_drvmask equ os88_image_end + DOS_B_DRVMASK
dos_blaster equ os88_image_end + DOS_B_BLAST
dos_xmstab  equ os88_image_end + DOS_B_XMSTAB
dos_xmlen   equ os88_image_end + DOS_B_XMLEN
dos_xmsh    equ os88_image_end + DOS_B_XMSH
dos_xmso    equ os88_image_end + DOS_B_XMSO
dos_xmdh    equ os88_image_end + DOS_B_XMDH
dos_xmdo    equ os88_image_end + DOS_B_XMDO
dos_xmlin   equ os88_image_end + DOS_B_XMLIN
dos_xmcon   equ os88_image_end + DOS_B_XMCON
dos_xmdir   equ os88_image_end + DOS_B_XMDIR
dos_xparm   equ os88_image_end + DOS_B_XPARM
dos_xparms  equ os88_image_end + DOS_B_XPARMS
dos_ldname  equ os88_image_end + DOS_B_LDNAME
dos_ldpsp   equ os88_image_end + DOS_B_LDPSP
dos_ldpara  equ os88_image_end + DOS_B_LDPAR
dos_dy      equ os88_image_end + DOS_B_DY
dos_dm      equ os88_image_end + DOS_B_DM
dos_dd      equ os88_image_end + DOS_B_DD
dos_lasttl  equ os88_image_end + DOS_B_LTL
dos_lastth  equ os88_image_end + DOS_B_LTH
dos_tmp1    equ os88_image_end + DOS_B_TMP1
dos_tmp2    equ os88_image_end + DOS_B_TMP2
dos_tmp3    equ os88_image_end + DOS_B_TMP3
dos_acc     equ os88_image_end + DOS_B_ACC
dos_fabs    equ os88_image_end + DOS_B_FABS
dos_curdir  equ os88_image_end + DOS_B_CURDIR
dos_dvcwd   equ os88_image_end + DOS_B_DVCWD   ; per drive: its cluster
dos_dvtgt   equ os88_image_end + DOS_B_DVTGT   ; ...and the one it goes to
dos_dvfrom  equ os88_image_end + DOS_B_DVFROM  ; the drive a switch is leaving
dos_ndrv    equ os88_image_end + DOS_B_NDRV    ; AH=0Eh's count, 0 = unprobed
dos_cwdst   equ os88_image_end + DOS_B_CWDST   ; AH=47h's destination
dos_cwdrv   equ os88_image_end + DOS_B_CWDRV   ; ...and the drive asked about
dos_imghi   equ os88_image_end + DOS_B_IMGHI   ; word: the file's size, high
dos_exe_fseg equ os88_image_end + DOS_B_XFSEG  ; word: where the FILE landed
dos_exe_lseg equ os88_image_end + DOS_B_XLSEG  ; word: ...and the load segment
dos_exe_hpara equ os88_image_end + DOS_B_XHPAR ; word: header paragraphs
dos_exe_nrel equ os88_image_end + DOS_B_XNREL  ; word: relocation entries
dos_exe_rloc equ os88_image_end + DOS_B_XRLOC  ; word: ...where the table is
dos_exe_minal equ os88_image_end + DOS_B_XMINA ; word: paragraphs it must have
dos_exe_ipara equ os88_image_end + DOS_B_XIPAR ; word: the image's paragraphs
dos_exe_cs  equ os88_image_end + DOS_B_XCS     ; word: the entry state, all
dos_exe_ip  equ os88_image_end + DOS_B_XIP     ; word: four out of the header
dos_exe_ss  equ os88_image_end + DOS_B_XSS     ; word: and CS/SS relocated
dos_exe_sp  equ os88_image_end + DOS_B_XSP     ; word:
dos_fsi     equ os88_image_end + DOS_B_FSI     ; FSI_SIZE: the fsx info block
dos_ivt     equ os88_image_end + DOS_B_IVT     ; 1024: the whole vector table
dos_bda     equ os88_image_end + DOS_B_BDA     ; 256:  ...and the whole BDA
