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
%include "netpkg.inc"               ; THE SOCKET DRIVER'S OWN HEADER, for the
                                    ; NETV_RAW* verbs the packet driver rests
                                    ; on (SPEC.md 72.22, 96.23). Constants
                                    ; only at this point in the file; the code
                                    ; half is os88sock.inc at the end

%ifdef DOSTRACE
    ; **THE TRACE BUILD IS A PARTED PACKAGE AND THE SHIPPED ONE IS NOT**
    ; (SPEC.md 96.29.1). flags bit 2 is OS88_F_PARTS, and it is behind the
    ; %ifdef for the reason the whole instrument is: a byte the shipped build
    ; pays for an instrument is a byte the DOS program does not get.
    OS88_HEADER 'DOS', dos_entry, 3 | OS88_F_PARTS
%else
    OS88_HEADER 'DOS', dos_entry, 3     ; flags bit 0 = icon, bit 1 = the
%endif
                                        ; flags bit 0 = icon, bit 1 = the
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

; THE DISK CACHE IS WORTH MORE TO A DOS PROGRAM THAN THE RAM IT SITS IN
; (SPEC.md 96.24). A .COM owns every byte after its image, so the honest thing
; to ask for is "everything" - and everything includes SPEC.md 18.95's
; directory read-ahead window, which the claim used to shed to make that true.
; Measured loading Prince of Persia off a 720KB floppy on a 4.77MHz 5150, the
; cache alive against the cache shed, the program's own int 13h traffic is
; SEVEN TIMES what IBM DOS 3.30 makes on the same disk. The floor is the whole
; of the fix (SPEC.md 50.6.6): nothing at or above MEM_PG_HIGH is shed or
; dropped, so the compaction packs the window out of the way instead.
;
; A CONSTANT AND NOT A NUMBER ANYBODY MAY PICK, because the level it names has
; to be the same in both calls - the AVAIL that plans and the CLAIM that acts.
DOS_PG_FLOOR equ MEM_PG_HIGH

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
                                    ; **512 AGAIN, because the buffers are a
                                    ; PART now** (SPEC.md 96.29.1). It was cut
                                    ; to 256 when the trace build measured
                                    ; 61,437 of APP_MAX_SIZE's 61,440 - three
                                    ; bytes - and §96.26's cable networking
                                    ; stopped it assembling; the next cut
                                    ; after that was DOS_TRDUMPN, 256 to 240.
                                    ; Neither was a design decision, both were
                                    ; a ceiling, and the ceiling is gone: a
                                    ; part is outside the 60KB an image and
                                    ; its bss share, so this is sized by the
                                    ; failure it exists for again. That one
                                    ; makes 169 calls, so 256 was never the
                                    ; binding number - but 512 is what lets a
                                    ; run be read from its FIRST call with
                                    ; slack, and slack in a ring is the whole
                                    ; point of one
DOS_TRACE_SZ equ 32                 ; ...bytes an entry, NAMED so that the host
                                    ; side derives it rather than transcribing
                                    ; it (docs/DOS-DEBUGGING.md): every reader
                                    ; of this ring lives outside the guest, and
                                    ; a layout known in two places is one that
                                    ; decodes plausible nonsense the day it
                                    ; moves. It has moved twice already, 12 to
                                    ; 16 to 32
DOS_TRDUMPN equ 256                 ; ...and how many of them TRACE.LOG holds,
                                    ; which is separate because the RING is
                                    ; read live off a debugger and the FILE is
                                    ; what the field posts. **256 AGAIN, and
                                    ; for DOS_TRACEN's reason**: it was cut to
                                    ; 240 as the second stopgap under the same
                                    ; ceiling, its own comment saying "THE
                                    ; REAL FIX IS A PART" - which this is.
                                    ; Sixteen lines is not a quantity anybody
                                    ; chose; 256 is the ring, the reference
                                    ; tracer's own cap and this, all covering
                                    ; the same span, which is what makes two
                                    ; traces diff line for line
; --- THE PART'S OWN LAYOUT (SPEC.md 96.29.1) --------------------------------
; Two buffers in one OP_ZERO part, because a part is a claim and MEM_OWNER_MAX
; is eight of them: one 35KB row beats two rows for no gain. The offsets are
; the part's, not the package's, and everything that reads them does it
; through ES.
;
; **THE RENDERED DUMP GOES FIRST, AND THAT IS A CORRECTNESS REQUIREMENT AND
; NOT A LAYOUT TASTE.** [dos_tracei] holds the entry a result belongs to and
; spells "the call was filtered" as ZERO (it is in the bss block below, under
; that comment) - a sentinel that cost nothing while the ring was bss, because
; a bss offset is os88_image_end plus a positive displacement and can never be
; 0. In a part it can: with the ring at offset 0, ENTRY 0's index IS 0, so
; dos_tr_result reads "filtered" for it and its result is never filled. The
; symptom is a trace whose first call - and every 512th after a wrap - reads
; `axout=FFFF`, which the reader correctly renders as "this call never
; returned", about a call that returned perfectly well. Putting the dump's
; 18,432 bytes in front of the ring restores what bss gave for free, for zero
; bytes and no code.
DOS_TRD_OFF equ 0                           ; the rendered dump...
DOS_TRB_OFF equ DOS_TRDUMPN * 72            ; ...and THEN the ring
DOS_TRACE_BY equ DOS_TRB_OFF + DOS_TRACEN * DOS_TRACE_SZ + DOS_TRNM_N * 15 + 96
DOS_TRACE_KB equ (DOS_TRACE_BY + 1023) / 1024

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
LNK_EXTSIG2 equ 0xA0088089          ; ...and a SECOND one, the memory settings
                                    ; (SPEC.md 96.25.2). A second BLOCK and not
                                    ; two more fields on the first, because the
                                    ; first ends in a bare NUL after a variable
                                    ; number of rows - so anything appended
                                    ; sits at an offset that depends on what
                                    ; the user typed. ExtraData is a sequence
                                    ; whose consumers SKIP signatures they do
                                    ; not know, so a second block is what the
                                    ; mechanism is for, and its fields are at a
                                    ; fixed offset inside it. An older link
                                    ; simply has not got one
LNK_EXT2SZ  equ 12                  ; size(4) + signature(4) + memkb(2) + a
                                    ; byte for the cache and one of padding
LNK_MAX     equ 512                 ; what one may be, read or written

DOS_PAGE_MAIN equ 0
DOS_PAGE_ENV  equ 1
DOS_PAGE_MEM  equ 2                 ; SPEC.md 96.25's memory settings
DOS_PAGE_N    equ 3                 ; ...and the button CYCLES now rather than
                                    ; toggling, which is why this is a count

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

; THE MEMORY PAGE (SPEC.md 96.25), laid out in the same content box as the
; other two - three read-only lines, the field, the check box, and the page
; button already at DOS_BTNY. The two figures are what the user is choosing
; between, so they are on the glass rather than in the documentation.
DOS_MEMY    equ 6                   ; the heading's baseline
DOS_MROW1   equ 22                  ; ...the two figures
DOS_MROW2   equ 34
DOS_MFLDY   equ 52                  ; the limit box's top (DOS_FLDH tall)
DOS_MFLDW   equ 64                  ; ...and its width: 5 digits and the caret
DOS_MFLDX   equ 64                  ; ...indented past its own label
DOS_MCHKY   equ 72                  ; the check box's row
DOS_MEMBUF  equ 8                   ; the field's text: 5 digits + NUL, and
                                    ; room for the caret to sit past the end
DOS_MEMMAX  equ 5                   ; ...what LN_MAX gets. 640 is three and a
                                    ; machine cannot have six digits of KB
                                    ; below 1MB
DOS_MCHKSZ  equ 12                  ; os88ui.inc's OS88UI_CK_SIZE, written here
                                    ; and CHECKED against it after the include
                                    ; - DOS_LNSZ's rule exactly, and for the
                                    ; same reason: the bss table is above and
                                    ; the record's owner is below
DOS_MCHKON  equ 10                  ; ...and OS88UI_CK_ON inside it, so that
                                    ; [dos_keepc] IS the control's own byte and
                                    ; there is no second copy to keep in step

; os88line.inc is included at the END of this file (its own rule: the header
; and the icon block are at fixed offsets), and the bss table above needs its
; block size BEFORE that. So the size is written here and CHECKED against the
; real one immediately after the include - a mirrored constant with a gate on
; it, which is what this tree does everywhere two files must agree.
DOS_LNSZ    equ 20

; --- the built-in commands' sizes (apps/dos/dosh.inc, SPEC.md 96.30) --------
; HERE AND NOT IN dosh.inc: the DBSS table below sizes that file's buffers and
; `%assign` cannot forward-reference, so the numbers come before both.
DSH_LINE    equ 128                 ; DOS's own command tail is a counted byte,
                                    ; so 127 is the longest there has ever been
DSH_ARG     equ 64                  ; one argument - longer than any 8.3 path
                                    ; this box can walk, so a truncation here
                                    ; is a path that was going to be refused
DSH_PAT     equ 11                  ; a padded 8.3 name, the form a match is
                                    ; decided in
DSH_BUF     equ 128                 ; TYPE's chunk
DSH_CPKB    equ 8                   ; the COPY buffer, out of the DOS ARENA and
                                    ; not the heap (SPEC.md 96.30.6): 8KB asked
DSH_CPMINKB equ 1                   ; for, one accepted, which is 2 sectors and
                                    ; still copies

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
%ifdef DOSTRACE
    ; **op_load FIRST, BEFORE ANYTHING TOUCHES SI** (os88parts.inc rule 1):
    ; SI arrives holding an offset into the KERNEL's segment at the name of
    ; the file we came out of, and the loader reuses that buffer on the next
    ; launch - so nothing later can recover it. The pushes below would not
    ; lose it, but dos_size and OSAPI_WM_CREATE would.
    ;
    ; The part is OP_OPT, so a refusal is survivable and [dos_trseg] stays 0:
    ; the trace writes nothing and the program runs. That is the right answer
    ; for an instrument on a machine it does not fit on, and it is why there
    ; is no `jc` here.
    ;
    ; **AND IT IS INSIDE THE PUSHES**, which is not in tension with rule 1:
    ; `push` does not change what it pushes, so SI still holds the kernel's
    ; pointer here - while op_load's documented clobber list is AX, BX, CX,
    ; DX, SI, DI and ES, and every one of those except BX is a register this
    ; proc owes the kernel back.
    ;
    ; **AND ES IS BANKED, WHICH IS THE ONE THAT BIT.** ES arrives holding
    ; KERNEL_SEG (SPEC.md 20.1) and OSAPI_ARG_FILE below answers with an SI
    ; into THAT segment and does not reload it - it is documented as read
    ; through the ES a package proc was entered with (SPEC.md 74240). Every
    ; OSAPI slot preserves ES, so the entry proc can rely on it across
    ; wm_create and about_set; op_load is OUR code and clobbers it. Without
    ; this pair the name copy below reads RDSUM.COM's 13 bytes out of the
    ; PART's segment, [dos_name] is junk, and the failure surfaces four
    ; routines later as dos_be_read refusing - "It could not be read.", about
    ; a file that is perfectly readable.
    push es
    call op_load
    xor al, al
    call op_seg                     ; AX = the part's segment, or 0
    mov [dos_trseg], ax
    pop es
%endif

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

    call dos_pkt_bufs               ; THE PACKET DRIVER'S BUFFERS FIRST (SPEC.md
                                    ; 96.23.7): the sizing below takes
                                    ; everything left, so a claim after it is a
                                    ; claim that always fails. It is 2KB and it
                                    ; preserves BX, so it sits in front of the
                                    ; floor rather than inside it - and it asks
                                    ; at the DEFAULT level, which for two
                                    ; kilobytes never needs a purge to answer
    mov bl, MEM_LVL_TOP             ; THE FLOOR IS THE USER'S (SPEC.md 96.25),
    cmp byte [dos_keepc], 0         ; and the default is the box ticked -
    je .floor                       ; everything except the disk cache
    mov bl, DOS_PG_FLOOR            ; (SPEC.md 50.6.6, 96.24)
.floor:
    push bx
    mov al, bl
    call OSAPI_MEM_AVAIL_LVL        ; AX = the largest run a claim can HAVE at
    pop bx                          ; that level - already net of every
                                    ; purgeable cache BELOW it and of what a
                                    ; compaction would recover (SPEC.md 50.6.3,
                                    ; 66.10.3). Nothing to compute, nothing to
                                    ; probe, and BX is an OUTPUT here
    mov dx, [dos_memkb]             ; ...and the user's own cap, if there is
    or dx, dx                       ; one. 0 is "as much as the machine will
    jz .cap                         ; give", which is what a double click gets
    cmp ax, dx
    jbe .cap
    mov ax, dx
.cap:
    cmp ax, DOS_MIN_KB
    jb .nomem
    mov [dos_akb], ax               ; BANKED: the claim's answer is DX and the
                                    ; slot promises nothing about AX, so the KB
                                    ; figure has to survive the call somewhere
                                    ; other than in a register
    mov bh, 1                       ; BL is STILL the floor, and it has to be
    xor cx, cx                      ; the same one, or the number above was a
                                    ; plan the claim does not carry out. BH = 1
                                    ; is OSAPI_MEM_CLAIM_HI's own door (50.3.2)
    call OSAPI_MEM_CLAIM_LVL        ; AX = KB -> DX = base segment
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
    call dn_shut                    ; every translated flow closed, before the
                                    ; driver that owns its sockets is resumed
    call dos_pkt_shut               ; THE RAW CLAIM GOES BACK FIRST, on every
                                    ; path here for dos_drv_back's own reason
                                    ; (SPEC.md 96.23.5): a release by a caller
                                    ; that does not hold one is a no-op, and a
                                    ; machine left with its own stack switched
                                    ; off because a program crashed is not. It
                                    ; is BEFORE the resume because the driver
                                    ; the claim is against must still be
                                    ; mounted to hear it
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
    call dos_pkt_start              ; ...AND THE PACKET DRIVER (SPEC.md 96.23),
                                    ; after dos_hook_vectors because it takes a
                                    ; vector of its own and after
                                    ; dos_save_machine because the whole IVT is
                                    ; banked by then - so the unhook is the
                                    ; restore, the way every other vector's is

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
    cmp byte [dos_pkt_raw], 0       ; **THE THIRD POLL** (SPEC.md 96.23.4): a
    je .nopkt                       ; client doing file I/O between receives
    call dos_pkt_poll               ; drains here. One compare on a path that
.nopkt:                             ; is already a dispatch, and it costs a
                                    ; program with no packet driver nothing

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
    cmp ah, 0x36
    je .dfree
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
    cmp ah, 0x29
    je .parsefcb
    cmp ah, 0x56
    je .rename
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
    call dos_fh_leave               ; ...and off the drive the name named, if
    xor ah, ah                      ; it named one (SPEC.md 96.6.2). BOTH exits
    jmp .badax                      ; carry it, so no error path can forget
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
    call dos_fh_leave
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
    mov al, [dos_vol]               ; THE VOLUME THE NAME LANDED ON, which is
    mov [si+FH_VOL], al             ; where every later read of this handle
                                    ; goes - dos_fh_name is still standing
                                    ; there, so it is [dos_vol] and needs no
                                    ; second lookup (SPEC.md 96.6.2)
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
    mov al, [dos_vol]
    mov [si+FH_VOL], al
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
.dfree:
    ; AH=36h: DL = the drive - 0 the default, 1 = A. Out AX = sectors per
    ; cluster, BX = free clusters, CX = bytes per sector, DX = total clusters;
    ; AX = FFFFh for an INVALID DRIVE, which is the answer that matters
    ; (SPEC.md 96.27).
    ;
    ; **IT IS THE REFUSAL THAT WAS THE DEFECT, not the absence.** Unimplemented,
    ; this fell to .bad and returned AX=1 with CF - and DOS does not use CF
    ; here at all, so an installer read "one sector per cluster" and three
    ; stale registers. Prince of Persia's INSTALL selects C:, is told it is
    ; standing on C:, asks this, and prints "Invalid drive letter" (96.27.1).
    push bx
    push si
    push di
    push es
    mov al, dl
    or al, al
    jnz .df1
    mov al, [dos_vol]               ; 0 = the drive we are on
    jmp short .dfv
.df1:
    dec al                          ; 1-based -> a volume index
.dfv:
    mov bh, [dos_vol]               ; where to come back to
    cmp al, bh
    je .dfask                       ; the common case by far: a program selects
                                    ; the drive and then asks about it
    mov dl, al
    call dos_drv_sel                ; A REAL MOUNT, and dos_drv_sel is the one
    cmp al, [dos_vol]               ; place that knows how to put itself back
    jne .dfbad                      ; if the mount refuses
.dfask:
    push ds
    pop es                          ; the record lands in OUR bss, not the
    mov di, dos_vsbuf               ; program's: nothing here is the caller's
    mov cx, VS_SIZEOF               ; buffer and DOS gives us nowhere to put one
    call OSAPI_VOL_STAT
    jc .dfback
    cmp cx, VS_SIZEOF
    jb .dfback                      ; a short answer has no free count in it,
                                    ; and three quarters of a reply is not one
    mov ax, [dos_vsbuf+VS_SPC]
    mov bx, [dos_vsbuf+VS_FREE]
    mov cx, [dos_vsbuf+VS_BPS]
    mov dx, [dos_vsbuf+VS_CLUS]
    call .dfhome
    pop es
    pop di
    pop si
    add sp, 2                       ; BX is an ANSWER: drop the banked one
    jmp .ok
.dfback:
    call .dfhome
.dfbad:
    mov ax, 0xFFFF                  ; DOS's own "invalid drive", and a value a
    pop es                          ; program can test even when it ignores the
    pop di                          ; flag - which for this call every program
    pop si                          ; does, DOS never setting CF here
    add sp, 2
    jmp .ok
; --- .dfhome - back to the drive we were standing on, if we left it ---------
.dfhome:
    push ax
    push dx
    mov dl, bh
    cmp dl, [dos_vol]
    je .dfh
    call dos_drv_sel
.dfh:
    pop dx
    pop ax
    ret

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
    mov al, [dos_vol]               ; spends CX (SPEC.md 96.12.1)
    mov [es:di+DTA_VOL], al         ; ...and the volume dos_fh_name put us on
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
    mov al, [es:di+DTA_VOL]         ; ...the volume included: a walk started on
    mov [dos_fdrv], al              ; B: carries on there whatever the program
    call dos_fh_enter               ; has done to its own drive since, and
    jc .fherr                       ; .fhok/.fherr bring us home
    call dos_find_step              ; CF=1 with AL = 18 (no more files)
    jc .fherr
    xor ax, ax
    jmp .fhok

; --- AH=29h: parse a filename into an FCB (SPEC.md 96.28) --------------------
.parsefcb:
    ; in:  DS:SI = the name, ES:DI = the FCB, AL = the parse flags
    ; out: AL = 0 no wildcards / 1 wildcards / FFh a drive past the last, SI
    ;      advanced past what was parsed, ES:DI untouched.
    ;
    ; IT SETS NO CARRY, and that is the whole reason it is here. Unimplemented
    ; it fell to .bad, which answers CF=1 with AX=0001 - and a program reading
    ; AL, which for this call every program does, is told its plain name HAD
    ; WILDCARDS IN IT. Measured over eleven inputs under IBM DOS 3.30
    ; (tests/dostrap/parsefcb.asm): CF is clear on every one, the invalid
    ; drive included. SPEC.md 96.22's shape for the fourth time in this box.
    ;
    ; THE SEGMENTS ARE WHY IT IS THREE PHASES. The name is in the program's
    ; DS, the FCB in the program's ES, and the separator table in OURS - so it
    ; copies in, parses at home, and copies out, rather than juggling two
    ; overrides through a loop that also has to index a table.
    push bx
    push cx
    push dx
    push si
    push di
    push es

    ; --- phase 1: the name, out of the program's segment ------------------
    push ds
    pop es                          ; ES = ours for the copy in
    mov ds, [bp]                    ; DS = the program's
    xor cx, cx                      ; CX counts the LEADING BLANKS, which DOS
.pf_blank:                          ; skips and which still count towards SI
    mov al, [si]
    cmp al, ' '
    je .pf_bs
    cmp al, 9
    jne .pf_copy
.pf_bs:
    inc si
    inc cx
    cmp cx, DOS_PFIN
    jb .pf_blank                    ; a string of nothing but blanks parses to
                                    ; a blank FCB, which is what it is
.pf_copy:
    mov di, dos_pfbuf
    mov dx, cx                      ; DX = the blanks, banked across the copy
    mov cx, DOS_PFIN
.pf_cp:
    mov al, [si]
    mov [es:di], al
    inc si
    inc di
    or al, al
    loopnz .pf_cp
    mov byte [es:di-1], 0           ; TERMINATED WHATEVER CAME IN: a name with
                                    ; no NUL in DOS_PFIN bytes is not a name
    push es
    pop ds                          ; ...and home, where the table lives

    ; --- phase 2: the parse, entirely in our own segment ------------------
    mov si, dos_pfbuf
    mov di, dos_pfcb
    xor bh, bh                      ; BH = the answer, BL = "a ? was stored"
    xor bl, bl
    xor al, al                      ; the drive byte: 0 = the one we are on
    cmp byte [si+1], ':'
    jne .pf_drvset
    mov al, [si]
    cmp al, 'a'
    jb .pf_dup
    cmp al, 'z'
    ja .pf_dup
    sub al, 32
.pf_dup:
    sub al, 'A' - 1                 ; the FCB numbers A: as 1, not as 0
    add si, 2
    cmp al, DVOL_MAX
    jbe .pf_drvset
    mov bh, 0xFF                    ; past the last drive - and the byte STILL
.pf_drvset:                         ; goes in, measured: Z: writes 26
    mov [di], al
    inc di
    mov cx, 8                       ; the name...
    call .pf_field
    mov cx, 3                       ; ...and the extension, which is there only
    cmp byte [si], '.'              ; if a dot says so
    jne .pf_noext
    inc si
    call .pf_field
    jmp short .pf_ans
.pf_noext:
    mov al, ' '                     ; no dot, so the extension is three blanks
.pf_nex:
    mov [di], al
    inc di
    loop .pf_nex
.pf_ans:
    or bh, bh
    jnz .pf_out                     ; FFh beats everything
    mov bh, bl                      ; ...otherwise 1 if any ? landed, else 0
.pf_out:
    sub si, dos_pfbuf               ; how far the parse got, plus the blanks
    add si, dx                      ; phase 1 skipped - an ADVANCE and not a
    add [bp-2], si                  ; pointer, so it is ADDED to the banked
                                    ; slot, which still holds the SI the
                                    ; program came in with (SPEC.md 96.7.1).
                                    ; Storing it flat left every caller's SI
                                    ; pointing at the same low address

    ; --- phase 3: the twelve bytes, into the program's FCB ----------------
    mov es, [bp-6]                  ; ES = the program's, as it passed it
    mov di, [bp-4]                  ; ...and DI, which is NOT ours to move
    mov si, dos_pfcb
    mov cx, 12
    cld
    rep movsb

    mov al, bh
    xor ah, ah
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    jmp .ok                         ; .ok and NOT .badax: there is no carry in
                                    ; this call's contract at all

; --- .pf_field - CX bytes of one FCB field at DS:DI from DS:SI --------------
; Stops at a separator, blank-pads what is left, and expands `*` to `?` for
; the rest of the field - which is the FCB's own convention and not ours: DOS
; answers `*.*` with eleven question marks. BL is set when one lands.
.pf_field:
    mov al, [si]
    call .pf_sep
    jc .pf_fpad
    inc si
    cmp al, '*'
    je .pf_fstar
    cmp al, 'a'
    jb .pf_fst
    cmp al, 'z'
    ja .pf_fst
    sub al, 32                      ; AN FCB MATCHES A DIRECTORY ENTRY, which
.pf_fst:                            ; is upper - and Prince's installer really
    cmp al, '?'                     ; does pass "B:Prince.exe"
    jne .pf_fnq
    mov bl, 1
.pf_fnq:
    mov [di], al
    inc di
    loop .pf_field
    ret
.pf_fstar:
    mov al, '?'
    mov bl, 1
.pf_fss:
    mov [di], al
    inc di
    loop .pf_fss
    ret
.pf_fpad:
    mov al, ' '
.pf_fps:
    mov [di], al
    inc di
    loop .pf_fps
    ret

; --- .pf_sep - does AL end an FCB field? CF=1 if it does --------------------
.pf_sep:
    cmp al, ' '
    jbe .pf_syes                    ; the NUL, the tab, a control byte and the
    push cx                         ; blank itself all end it
    push si
    mov si, .pf_seps
    mov cx, DOS_PFSEPN
.pf_sscan:
    cmp al, [si]
    je .pf_shit
    inc si
    loop .pf_sscan
    pop si
    pop cx
    clc
    ret
.pf_shit:
    pop si
    pop cx
.pf_syes:
    stc
    ret
; The characters DOS ends an FCB field on, above the blank - the ones at or
; below it are covered by one compare. `.` is in here because .pf_field has to
; stop on it; the caller is what looks for it and starts the extension.
; A LOCAL LABEL, and that is not a style choice: a global one here re-scopes
; every `.local` in dos_int21 below it, and the whole dispatch stops resolving.
.pf_seps:   db '.', ':', ';', ',', '=', '+', '"', '/', '\\', '[', ']', '|'
            db '<', '>'

; --- AH=56h: rename (SPEC.md 96.31) ------------------------------------------
.rename:
    ; in: DS:DX = the old name, ES:DI = the new one - and note the SECOND is
    ; in the program's ES, which is why dos_fh_core takes a far pointer.
    ;
    ; EVERY RULE BELOW IS MEASURED, under IBM DOS 3.30, by the same binary
    ; (tests/dostrap/renref.asm) - and two of them are not what a reading of
    ; the call would give you:
    ;
    ;   * THE TWO NAMES MUST RESOLVE TO THE SAME DRIVE, and an unqualified one
    ;     means the CURRENT drive - not the OTHER NAME's. "B:X.TXT" -> "Y.TXT"
    ;     standing on A: is 11h, not same device. A handler that resolved the
    ;     new name against wherever the old one lives renames happily on B:.
    ;   * A PATH IN THE NEW NAME IS A MOVE, and DOS does it: "\Y.TXT" succeeds
    ;     and the file is in the root afterwards. OSAPI_FILE_RENAME rewrites a
    ;     directory entry WHERE WE STAND (SPEC.md 18.4), so that is the one
    ;     shape refused here rather than half-done.
    ;
    ; AX is junk on success in DOS (the row that worked reports 0012h), so
    ; only CF carries the answer and zero is as good as anything.
    push bx
    mov al, [dos_vol]               ; THE ENTRY VOLUME, banked before anything
    mov [dos_rnvol], al             ; moves us: it is what an unqualified name
                                    ; means, for BOTH names

    push ax                         ; --- the OLD name, parsed and NOT entered
    mov ax, [bp]
    mov [dos_fnseg], ax
    pop ax
    push di
    mov di, dos_fname
    call dos_fh_core
    pop di
    jc .fherr
    call .rndrv                     ; AL = the drive it means
    mov [dos_rndrv], al
    mov al, [dos_fabs]
    mov [dos_rnabs], al

    push ax                         ; --- ...and the NEW one, out of its ES
    mov ax, [bp-6]                  ; (SPEC.md 96.7.1's banked slot)
    mov [dos_fnseg], ax
    pop ax
    push di
    push dx
    mov dx, di
    mov di, dos_fname2
    call dos_fh_core
    pop dx
    pop di
    jc .fherr
    call .rndrv
    cmp al, [dos_rndrv]
    je .rnone
    mov al, 0x11                    ; "not same device" - measured, and the
    jmp .fherr                      ; only code DOS has for this

.rnone:
    cmp byte [dos_fabs], 0          ; a leading separator on EITHER name is a
    jne .rnroot                     ; move - unless we are standing in the
.rnone2:                            ; root already, where it names this very
    cmp byte [dos_rnabs], 0         ; folder and the move is a rename
    jne .rnroot2
.rngo:
    mov [dos_fdrv], al              ; ...and now stand on it. .fhok/.fherr are
    call dos_fh_enter               ; what come home (SPEC.md 96.6.2)
    jc .fherr
    push si
    push di
    mov si, dos_fname
    mov di, dos_fname2
    call dos_be_rename
    pop di
    pop si
    jc .rnerr
    xor ax, ax
    jmp .fhok
.rnroot:
    cmp word [dos_curdir], 0
    jne .rnmove
    jmp short .rnone2
.rnroot2:
    cmp word [dos_curdir], 0
    jne .rnmove
    jmp short .rngo
.rnmove:
    mov al, 5                       ; THE MOVE DOS WOULD MAKE, refused: this
    jmp .fherr                      ; layer rewrites an entry where it stands
                                    ; and cannot re-link one into another
                                    ; folder. "Access denied" is the honest
                                    ; code for a change we cannot make
                                    ; (SPEC.md 96.11.2's own reasoning)
.rnerr:
    cmp ax, FERR_NOENT              ; the source is not there: DOS says 2, and
    jne .fhacc                      ; everything else this can fail with - the
    mov al, 2                       ; target existing included - it says 5 for
    jmp .fherr

; --- .rndrv - the drive a just-parsed name MEANS ----------------------------
; out: AL = [dos_fdrv], or the volume we entered on when the name named none.
; clobbers: AL, flags
.rndrv:
    mov al, [dos_fdrv]
    cmp al, 0xFF
    jne .rnd
    mov al, [dos_rnvol]
.rnd:
    ret

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

    ; --- COMMAND.COM IS NOT A FILE HERE (SPEC.md 96.30) --------------------
    ; Before the name is parsed, before the arena is asked for anything: a
    ; shell-out runs one built-in command and comes straight back. Nothing is
    ; loaded, so dos_inchild is not set and the one-level rule below does not
    ; apply - a program may shell out as often as it likes.
    call dsh_isshell
    jc .noshell
    call dsh_tail                   ; ES:BX is still the parameter block
    mov [dos_chexit], al            ; ...and AH=4Dh is where the caller reads
    xor ax, ax                      ; the command's own verdict
    pop bx
    jmp .ok
.noshell:
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
    call dos_fh_leave               ; ...and HOME BEFORE THE CHILD RUNS: under
                                    ; DOS, EXEC "B:FOO" does not leave the
                                    ; program on B:, and the restore at .fhok
                                    ; is on the far side of the whole child
                                    ; (SPEC.md 96.6.2)

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
    mov ax, 0x1E03                  ; AL = 3, AH = 30: DOS 3.30 (SPEC.md
    mov bx, 0                       ; 96.21.7). The version is a SETTING and
    mov cx, 0                       ; not a constant the day a program wants
    jmp .ok                         ; 5.00 - reporting a version whose
                                    ; functions we lack is worse than reporting
                                    ; a lower one, because a program branches
                                    ; on it (DOS-EXEC-PLAN 12 q1) - and 3.31
                                    ; was half a release above the machine this
                                    ; box is measured against, for no feature
                                    ; it has. BX and CX are the OEM and serial,
                                    ; and 0/0 is what IBM DOS 3.30 answers too

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
    mov cx, 0x20                    ; ARCHIVE. SPEC.md 19 keeps no attribute of
    mov ax, cx                      ; its own and this is what an ordinary
    jmp .fhok                       ; readable file reads as everywhere. .fhok
                                    ; AND NOT .ok: these two were the only
                                    ; dos_fh_name callers that popped BX and
                                    ; left by the front door, which since
                                    ; SPEC.md 96.6.2 is also the door that
                                    ; comes off the named drive
.att_set:
    push bx
    call dos_fh_name                ; it still has to NAME something real...
    jc .fherr
    call .fhabs
    jc .fhpath
    call dos_fh_stat
    jc .fnoent
    xor ax, ax                      ; ...and the new attributes are then
    jmp .fhok                       ; DROPPED rather than refused: there is
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
    mov [es:di], al
    inc di
    pop ax
    and al, 0x0F
    call dos_hexd
    mov [es:di], al
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
    cmp word [dos_trseg], 0         ; no part, nothing to dump (SPEC.md
    je .nopart                      ; 96.29.1)
    mov es, [dos_trseg]             ; **ES IS THE PART FOR THE WHOLE ROUTINE**,
                                    ; which is what makes this cheap: the ring
                                    ; is read through it, the text is written
                                    ; through it, and OSAPI_FILE_WRITE takes
                                    ; ES:BX already - so handing 18KB of
                                    ; rendered log to the file system costs
                                    ; not one instruction more than it did
                                    ; when the buffer was our own bss

    mov di, dos_trdump
    mov si, dos_tr_hdr
.hdr:
    lodsb
    or al, al
    jz .hdrend
    mov [es:di], al
    inc di
    jmp short .hdr
.hdrend:
    mov ax, [dos_tracen]
    call dos_tr_hex4
    mov byte [es:di], '/'
    inc di
    mov ax, [dos_tracew]
    call dos_tr_hex4
    mov byte [es:di], 13
    inc di
    mov byte [es:di], 10
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
    cmp cx, DOS_TRDUMPN             ; the FILE holds no more than the ring
    jbe .fits
    mov cx, DOS_TRDUMPN
.fits:
    and bx, (DOS_TRACEN * DOS_TRACE_SZ) - DOS_TRACE_SZ
    or cx, cx
    jz .write
    xor dx, dx                      ; DX = entries on this line
.ent:
    mov ax, [es:bx+dos_traceb]         ; AX=
    call dos_tr_hex4
    mov byte [es:di], ' '
    inc di
    mov ax, [es:bx+dos_traceb+2]       ; BX=
    call dos_tr_hex4
    mov byte [es:di], ' '
    inc di
    mov ax, [es:bx+dos_traceb+4]       ; CX=
    call dos_tr_hex4
    mov byte [es:di], ' '
    inc di
    mov ax, [es:bx+dos_traceb+6]       ; DX=
    call dos_tr_hex4
    mov byte [es:di], '>'              ; ...and what it ANSWERED
    inc di
    mov ax, [es:bx+dos_traceb+8]
    call dos_tr_hex4
    mov byte [es:di], '/'
    inc di
    mov ax, [es:bx+dos_traceb+10]
    call dos_tr_hex4
    mov byte [es:di], '/'              ; ...and ES:BX, which for AH=35h, 48h and
    inc di                          ; 2Fh IS the answer and AX is not
    mov ax, [es:bx+dos_traceb+14]
    call dos_tr_hex4
    mov byte [es:di], ':'
    inc di
    mov ax, [es:bx+dos_traceb+12]
    call dos_tr_hex4
    mov byte [es:di], '@'              ; ...and WHO CALLED, which is what a pair
    inc di                          ; of traces that diverge with no call in
    mov ax, [es:bx+dos_traceb+18]      ; between is read on
    call dos_tr_hex4
    mov byte [es:di], ':'
    inc di
    mov ax, [es:bx+dos_traceb+16]
    call dos_tr_hex4
    mov byte [es:di], '/'
    inc di
    mov ax, [es:bx+dos_traceb+20]
    call dos_tr_hex4
    mov byte [es:di], 13
    inc di
    mov byte [es:di], 10
    inc di
    add bx, DOS_TRACE_SZ
    and bx, (DOS_TRACEN * DOS_TRACE_SZ) - DOS_TRACE_SZ
    dec cx                          ; ...and NOT `loop`: the body outgrew its
    jz .write                       ; own short displacement when the entry
    jmp .ent                        ; learned to say who called
.write:
    mov byte [es:di], 13
    inc di
    mov byte [es:di], 10
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
    mov [es:di], al
    inc di
    loop .nmc
    jmp short .nmeol
.nmpad:
    dec cx                          ; step over the rest of the fixed field
    jz .nmeol
    add si, cx
.nmeol:
    mov byte [es:di], 13
    inc di
    mov byte [es:di], 10
    inc di
    pop cx
    loop .nm
.nonames:
    mov cx, di
    sub cx, dos_trdump              ; CX = how much of it there is
    mov bx, dos_trdump              ; ES IS ALREADY THE PART, so the `push ds /
    mov si, dos_tr_name             ; pop es` that used to be here is gone -
    xor dx, dx                      ; the slot's buffer argument was ES:BX all
    call OSAPI_FILE_WRITE           ; along (os88api.inc). Creates or REPLACES,
                                    ; in the directory the program was
                                    ; launched from
.nopart:
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
    cmp word [dos_trseg], 0         ; **NO PART, NO TRACE** (SPEC.md 96.29.1).
    je .skip                        ; It is OP_OPT, so a machine that could
                                    ; not spare 35KB runs the program with the
                                    ; instrument silent - which is the whole
                                    ; point of an optional part, and far
                                    ; better than 35KB of stores into segment
                                    ; zero
    push ax
    push bx
    push si
    push es
    mov es, [dos_trseg]             ; ES IS THE PART from here to the pop, and
                                    ; every store below carries the override.
                                    ; ES on entry is the CLIENT's - the gate
                                    ; banked the program's at [bp-6] - so it
                                    ; is ours to borrow and must be put back
    mov si, [dos_tracew]
    and si, (DOS_TRACEN * DOS_TRACE_SZ) - DOS_TRACE_SZ  ; the ring's byte index, entry-aligned - a
    add si, dos_traceb              ; power-of-two stride so this is an AND
    mov [dos_tracei], si            ; where any other size needs a divide
    mov [es:si], ax                    ; AX carries the function AND its
    mov [es:si+2], bx                  ; sub-function; the other three carry what
    mov [es:si+4], cx                  ; it is ABOUT - a handle, a count, an
    mov [es:si+6], dx                  ; offset, a name's address. All four are
                                    ; still the caller's: `push` does not
                                    ; change what it pushes
    mov word [es:si+8], 0xFFFF         ; ...no result yet, so a call that never
    mov word [es:si+10], 0xFFFF        ; returned is visible as one
    mov word [es:si+12], 0xFFFF
    mov word [es:si+14], 0xFFFF

    ; --- WHO CALLED, which is the question AH and its arguments cannot answer.
    ; Two runs that make the same calls with the same arguments and then
    ; diverge have already diverged somewhere with no call in it, and the only
    ; thing that says where is the CS:IP the `int` pushed. CS is recorded raw
    ; and the reader subtracts the PSP, so the offset compares across two
    ; machines that loaded the program at different addresses.
    mov ax, [bp+4]
    mov [es:si+16], ax                 ; the return IP - one instruction past the
    mov ax, [bp+6]                  ; `int 21h` that got here
    mov [es:si+18], ax                 ; ...and its CS
    mov ax, [bp]                    ; ...and DS, BP: BOTH OFF THE FRAME, and
    mov [es:si+20], ax                 ; the live registers are NOT them -
    mov ax, [bp+2]                  ; dos_int21 pushed its own over the
    mov [es:si+26], ax                 ; caller's before this was reached
    pop ax                          ; SI is the caller's, under the push above
    push ax
    mov [es:si+22], ax
    mov [es:si+24], di                 ; DI is untouched from the gate
    mov ax, ss                      ; SS is still the program's - a DOS call
    mov [es:si+28], ax                 ; runs on the caller's stack
    lea ax, [bp+10]                 ; ...at the SP the `int` was taken on
    mov [es:si+30], ax

    add word [dos_tracew], DOS_TRACE_SZ
    inc word [dos_tracen]           ; ...and the TOTAL, which does not wrap
    pop es
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
    push es
    pushf                           ; CF IS THE SUBJECT here, and `or si, si`
    mov si, [dos_tracei]            ; two lines down would destroy it
    or si, si
    jz .out                         ; filtered, or no call in flight
    mov es, [dos_trseg]             ; the part (SPEC.md 96.29.1), and no guard
                                    ; of its own: [dos_tracei] is only ever
                                    ; SET by dos_trace, which refuses without
                                    ; a segment, so a zero there already means
                                    ; there is no entry to finish
    mov [es:si+8], ax
    mov word [es:si+10], 0
    mov [es:si+12], bx                 ; ...the OTHER answer, whole
    mov ax, [bp-6]                  ; ES as the PROGRAM will get it, off the
    mov [es:si+14], ax                 ; gate's banked slot and not the live
                                    ; register a handler happens to have left
    pop ax                          ; ...the flags, back off the stack
    push ax
    test al, 1                      ; CF is bit 0 of the low half
    jz .out
    mov word [es:si+10], 1
.out:
    popf
    pop es
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
DBE_RENAME  equ 28                  ; SI = the old name, DI = the new, both in
                                    ; the CURRENT directory (SPEC.md 96.31)
DBE_COPY    equ 30                  ; ES:SI = source name, ES:DI = destination
                                    ; name, BL/DX = the source place, BH/CX =
                                    ; the destination's (SPEC.md 22.24)
DBE_MOVE    equ 32                  ; ES:SI = the name, BL/DX and BH/CX the two
                                    ; places, ONE volume (SPEC.md 22.25). AX=0
                                    ; with CF is NOT ATTEMPTED, not an error
DBE_NENT    equ 17

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
dos_be_rename:
    mov word [dos_betgt], dos_k_rename
    jmp short dos_be_go
dos_be_copy:
    mov word [dos_betgt], dos_k_copy
    jmp short dos_be_go
dos_be_move:
    mov word [dos_betgt], dos_k_move
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

dos_k_rename:
    call OSAPI_FILE_RENAME
    ret

dos_k_copy:
    call OSAPI_FILE_COPY            ; the file manager's own engine, published
    ret                             ; (SPEC.md 22.24) - so the built-in COPY
                                    ; below is not a second one, and gets the
                                    ; partial-destination undo for nothing

dos_k_move:
    call OSAPI_FILE_MOVE            ; ...and its re-link (22.25). AX=0 with CF
    ret                             ; is "not attempted" and the shell's MOVE
                                    ; falls back to copy-then-delete on it

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

    cmp byte [dos_page], DOS_PAGE_MAIN
    je .mainpage
    mov bx, si
    cmp byte [dos_page], DOS_PAGE_MEM
    je .mempage
    call dos_paint_env
    jmp .out
.mempage:
    call dos_paint_mem
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

    mov bx, [dos_win]               ; ...and the way to the NEXT page, which
    call dos_btn_rect               ; the label has to name rather than imply
    mov bx, dos_brect               ; now that the button cycles
    call dos_btn_lbl
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
    call dos_btn_lbl
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
; dos_mfld_place - put the memory limit field where the window is now
; in:  BX = the window; every register preserved
;
; dos_fld_place's shape and for its reason: os88line's rect is in SCREEN
; coordinates, so a banked one puts the caret one drag behind.
; -----------------------------------------------------------------------------
dos_mfld_place:
    push ax
    push cx
    push dx
    push si
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top
    mov si, dos_mln
    mov cx, ax
    add cx, DOS_MFLDX
    mov [si+LN_X1], cx
    add cx, DOS_MFLDW
    mov [si+LN_X2], cx
    mov cx, dx
    add cx, DOS_MFLDY
    mov [si+LN_Y1], cx
    add cx, DOS_FLDH
    mov [si+LN_Y2], cx
    pop si
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_mchk_place - put the check box's record where the window is now
; in:  BX = the window; every register preserved
;
; The RECT IS THE WHOLE CLICKABLE AREA - box, gap and label - which is
; os88ui_chk's own contract, so a press on the words counts. Recomputed from
; the content origin on every paint and every click for dos_fld_place's reason:
; the rect is in SCREEN coordinates and a window moves.
; -----------------------------------------------------------------------------
dos_mchk_place:
    push ax
    push cx
    push dx
    push si
    push di
    call OSAPI_WM_CONTENT           ; AX = content left, DX = content top
    mov si, dos_mchk
    mov di, dos_l_memc
    mov [si+OS88UI_CK_LABEL], di
    mov cx, ax
    add cx, 8
    mov [si+0], cx
    add cx, OS88UI_CKBOX + OS88UI_CKGAP + 8 * DOS_MEMC_N
    mov [si+4], cx                  ; ...x2 INCLUSIVE, so the label's last
    dec word [si+4]                 ; cell is inside and the next pixel is not
    mov cx, dx
    add cx, DOS_MCHKY
    mov [si+2], cx
    add cx, OS88UI_CKBOX
    dec cx
    mov [si+6], cx
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_mem_figs - the two numbers the page is a choice BETWEEN
; out: AX = KB with the cache kept, DX = KB with it taken; flags
;
; Both come from the kernel rather than from arithmetic here, and they are the
; SAME question dos_run asks - so what the page shows is what the program will
; get, not an estimate of it (SPEC.md 50.6.6, 96.25.1).
; -----------------------------------------------------------------------------
dos_mem_figs:
    push bx
    push cx
    mov al, DOS_PG_FLOOR
    call OSAPI_MEM_AVAIL_LVL        ; AX = the largest run that leaves the
    push ax                         ; cache alive
    call OSAPI_MEM_AVAIL            ; ...and the one that does not
    mov dx, ax
    pop ax
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_paint_mem - the memory page (SPEC.md 96.25)
; in:  BX = the window; the gfx lock is held, as every W_PAINT's is
;
; NO GROUND FILL (SPEC.md 13.14.6), dos_paint_env's reason exactly: every line
; is an opaque font_run, an os88line or a control that draws its own ground.
; -----------------------------------------------------------------------------
dos_paint_mem:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bx
    call OSAPI_WM_CONTENT           ; ASKED and not read out of [dos_ctop],
    mov cx, ax                      ; which is the MAIN page's banked value
    add cx, 8
    mov [dos_mx], cx
    add dx, DOS_MEMY
    mov [dos_my], dx
    mov si, dos_l_memt
    mov ax, (CWHITE << 8) | CBLACK
    call OSAPI_FONT_RUN
    pop bx

    push bx
    call dos_mem_figs               ; AX = kept, DX = taken
    push dx
    mov di, dos_memk1
    call dos_mem_num                ; AX -> the first line's five digits
    pop ax
    mov di, dos_memk2
    call dos_mem_num
    mov bx, [dos_mx]
    mov dx, [dos_my]
    sub dx, DOS_MEMY
    add dx, DOS_MROW1
    mov si, dos_l_memk
    call dos_line
    add dx, DOS_MROW2 - DOS_MROW1
    mov si, dos_l_memt2
    call dos_line
    pop bx

    push bx                         ; the limit's label, then its box
    mov bx, [dos_mx]
    mov dx, [dos_my]
    sub dx, DOS_MEMY
    add dx, DOS_MFLDY + 3
    mov si, dos_l_meml
    call dos_line
    pop bx
    push bx
    call dos_mfld_place
    mov si, dos_mln
    call os88line_draw
    pop bx

    push bx                         ; ...and the choice itself
    call dos_mchk_place
    mov bx, dos_mchk
    xor di, di
    call os88ui_chk
    pop bx

    call dos_btn_rect
    push bx
    mov bx, dos_brect
    call dos_btn_lbl
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
; dos_btn_lbl - SI = what the page button should SAY, for the page that is up
; out: SI; every other register preserved
;
; It names WHERE IT GOES and not where you are, which is what a cycle needs: a
; button labelled with the current page is one the user has to press to find
; out what it does.
; -----------------------------------------------------------------------------
dos_btn_lbl:
    push bx
    xor bh, bh
    mov bl, [dos_page]
    shl bl, 1
    mov si, [dos_btn_tab+bx]
    pop bx
    ret

; in:  AX = 0..65535, DI -> five bytes inside a literal; clobbers nothing
;
; Into the LITERAL rather than into a buffer, which is dos_fmt_exit's shape
; one line along: the line is drawn by one opaque font_run and a number
; assembled anywhere else would need a second store to get there.
; -----------------------------------------------------------------------------
dos_mem_num:
    push ax
    push bx
    push cx
    push dx
    push di
    add di, 4                       ; the units digit, and work backwards
    mov cx, 5
    mov bx, 10
.d:
    xor dx, dx
    div bx                          ; AX = quotient, DX = this digit
    add dl, '0'
    mov [di], dl
    dec di
    dec cx
    jz .out
    or ax, ax
    jnz .d
.blank:
    mov byte [di], ' '              ; a LEADING BLANK and not a zero: the two
    dec di                          ; lines sit under one another and 00419
    loop .blank                     ; reads as a different quantity
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_mem_take - the limit field's text -> [dos_memkb]
; out: nothing; every register preserved
;
; EMPTY IS ZERO AND ZERO IS "ALL", which is what makes the field need no
; second control: a user who wants the machine's own answer clears the box.
; Anything that is not a digit ends the number, so a half-typed entry is the
; digits in front of it rather than a refusal in the middle of typing.
; -----------------------------------------------------------------------------
dos_mem_take:
    push ax
    push bx
    push cx
    push si
    xor ax, ax
    mov si, dos_mbuf
    mov bx, 10
.d:
    mov cl, [si]
    cmp cl, '0'
    jb .out
    cmp cl, '9'
    ja .out
    mul bx
    sub cl, '0'
    xor ch, ch
    add ax, cx
    inc si
    jmp short .d
.out:
    mov [dos_memkb], ax
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_mem_put - [dos_memkb] -> the limit field's text (0 = empty)
; out: nothing; every register preserved
; -----------------------------------------------------------------------------
dos_mem_put:
    push ax
    push bx
    push cx
    push dx
    push di
    push si
    mov byte [dos_mbuf], 0
    mov ax, [dos_memkb]
    or ax, ax
    jz .sync
    mov di, dos_mbuf + DOS_MEMMAX   ; right to left into the buffer, then
    mov byte [di], 0                ; shuffled down - five digits is not worth
    mov bx, 10                      ; a second pass over
    mov cx, DOS_MEMMAX
.d:
    xor dx, dx
    div bx
    add dl, '0'
    dec di
    mov [di], dl
    dec cx
    jz .move
    or ax, ax
    jnz .d
.move:
    mov si, di
    mov di, dos_mbuf
.m:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    or al, al
    jnz .m
.sync:
    mov si, dos_mln
    call os88line_resync
    pop si
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_click_mem - a press on the memory page
; in:  BX = the window, CX = x, DX = y
; -----------------------------------------------------------------------------
dos_click_mem:
    push ax
    push si
    push di
    mov di, cx
    mov bp, dx
    call dos_mchk_place             ; THE CHECK BOX FIRST: it is the control
    push bx                         ; the page exists for. os88ui_chkhit takes
    mov bx, dos_mchk                ; the point in CX/DX, toggles the record's
    call os88ui_chkhit              ; own ON byte and redraws THE MARK - not
    pop bx                          ; the control and not the page (13.15.2)
    jc .notchk
    call dos_defocus                ; ...and a field keeping the caret while
    jmp short .out                  ; another control is worked is a caret the
.notchk:                            ; user cannot account for
    call dos_mfld_place
    mov si, dos_mln
    mov cx, di
    mov dx, bp
    call os88line_hit
    jc .away
    call dos_defocus_but
    cmp byte [si+LN_FOCUS], 0
    jne .move
    mov byte [si+LN_FOCUS], 1
    call os88line_draw
    jmp short .out
.move:
    mov cx, di
    mov dx, bp
    call os88line_click
    jmp short .out
.away:
    call dos_defocus
.out:
    pop di
    pop si
    pop ax
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
    cmp byte [dos_page], DOS_PAGE_MEM
    je .memp
    call dos_fld_place
    mov si, dos_ln
    jmp short .have
.memp:
    call dos_mfld_place              ; the memory page has ONE field, so its
    mov si, dos_mln                  ; focus is the field's own byte
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
    mov al, [dos_page]              ; ...and the button CYCLES rather than
    inc al                          ; toggling now: main -> environment ->
    cmp al, DOS_PAGE_N              ; memory -> main, which is why its label
    jb .setpage                     ; is a table (SPEC.md 96.25)
    xor al, al
.setpage:
    mov [dos_page], al
    call dos_mem_take               ; THE LIMIT IS READ ON THE WAY OUT, so a
                                    ; number the user typed and did not press
                                    ; anything after is still the setting - a
                                    ; field that only commits on Enter loses
                                    ; what was typed, silently
    call dos_swap                   ; reach a box nobody can see
    jmp .out
.notpage:
    cmp byte [dos_page], DOS_PAGE_MAIN
    jne .notbtn                     ; Save Shortcut is the main page's only
    call dos_sav_rect
    push bx
    mov bx, dos_srect
    call os88ui_bhit
    pop bx
    jc .notbtn
    call dos_sav_go
    jmp .out
.notbtn:
    cmp byte [dos_page], DOS_PAGE_MEM
    jne .notmem
    call dos_click_mem
    jmp .out
.notmem:
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
    mov si, dos_mln                 ; ...the memory page's too: "no field on
    call .one                       ; EITHER page" is now three pages, and a
    mov cx, DOS_ENVN                ; caret left behind on a page nobody can
    mov si, dos_eln                 ; see still takes the keystrokes
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
    cmp byte [dos_page], DOS_PAGE_MEM
    jne .one
    mov si, dos_mln
.one:
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

    mov si, dos_mln                 ; ...and the memory limit (SPEC.md 96.25).
    mov ax, dos_mbuf                ; THE DEFAULTS ARE SET HERE and not in the
    mov [si+LN_BUF], ax             ; bss table, because -f bin zeroes nothing
    mov word [si+LN_MAX], DOS_MEMMAX  ; and "keep the cache" is a 1
    mov byte [si+LN_FOCUS], 0
    mov byte [dos_mbuf], 0
    mov word [dos_memkb], 0         ; 0 = as much as the machine will give,
    mov byte [dos_keepc], 1         ; which is what a double click gets
    call os88line_resync

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
    call dos_lnk_mem                ; ...and the memory settings, in a SECOND
    jc .no                          ; one (SPEC.md 96.25.2)
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

; --- dos_lnk_mem - the memory settings, in an ExtraData block of their own --
; A SECOND BLOCK and not two more fields on the first (SPEC.md 96.25.2): that
; one ends in a bare NUL after a variable number of rows, so anything appended
; to it sits at an offset that depends on what the user typed. Here the two
; fields are at a fixed offset inside a fixed-size block, and a reader that
; does not know the signature steps over it with one add - which is what
; ExtraData is specified for.
dos_lnk_mem:
    push ax
    mov ax, di
    sub ax, dos_lbuf
    add ax, LNK_EXT2SZ
    cmp ax, LNK_MAX
    ja .no
    mov ax, LNK_EXT2SZ              ; BlockSize, counting itself
    stosw
    xor ax, ax
    stosw
    mov ax, LNK_EXTSIG2 & 0xFFFF
    stosw
    mov ax, LNK_EXTSIG2 >> 16
    stosw
    mov ax, [dos_memkb]             ; the cap, 0 = as much as the machine gives
    stosw
    mov al, [dos_keepc]             ; ...and the one choice
    stosb
    xor al, al
    stosb                           ; ...and a byte of padding, so the block is
    clc                             ; a whole number of dwords like every other
    jmp short .out
.no:
    stc
.out:
    pop ax
    ret                             ; DI IS NOT RESTORED - it is an OUTPUT, for
                                    ; dos_lnk_env's reason

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
    cmp di, LNK_EXTSIG >> 16        ; both of ours share a high word
    jne .next
    cmp cx, LNK_EXTSIG & 0xFFFF
    jne .m
    call dos_lnk_rows
    jmp short .next                 ; ...AND KEEP WALKING: there are two of our
.m:                                 ; blocks now, and a link written by an
    cmp cx, LNK_EXTSIG2 & 0xFFFF    ; older build has only the first
    jne .next
    cmp ax, LNK_EXT2SZ
    jb .next                        ; short: not one of ours, whatever it says
    call dos_lnk_memr
.next:
    add si, ax
    jmp short .blk
.out:
    pop di
    pop cx
    pop bx
    pop ax
    ret

; --- dos_lnk_memr - the memory block at SI -> [dos_memkb] / [dos_keepc] -----
; The size was checked against LNK_EXT2SZ before the call and the block's own
; size was checked against what is LEFT of the file before that, so both reads
; are inside the buffer by construction (SPEC.md 20.8 rule 2).
;
; THE CAP IS CLAMPED and the choice is FORCED TO 0 OR 1, because this is a file
; somebody else may have written: a cap of 0xFFFF is harmless (dos_run takes
; the smaller of it and what the machine offers) but a keep byte of 0x7F would
; make the check box draw a mark for a value it can never toggle back to.
dos_lnk_memr:
    push ax
    mov ax, [dos_lbuf+si+8]
    mov [dos_memkb], ax
    mov al, [dos_lbuf+si+10]
    cmp al, 1
    jbe .set
    mov al, 1                       ; anything else means the default, which is
.set:                               ; the one a double click gets
    mov [dos_keepc], al
    call dos_mem_put                ; ...and the field shows what the link said
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
; --- the memory page (SPEC.md 96.25) -----------------------------------------
; The two figures are PATCHED IN PLACE by dos_mem_num and drawn as part of one
; opaque font_run, which is dos_fmt_exit's shape: a number assembled anywhere
; else needs a second store to reach the line, and a second pass over the
; pixels is what SPEC.md 6.1 exists to stop.
dos_l_memb: db 'Memory', 0
; ...and WHERE THE BUTTON GOES from each page, indexed by DOS_PAGE_*
dos_btn_tab:
    dw dos_l_envb                   ; main -> environment
    dw dos_l_memb                   ; environment -> memory
    dw dos_l_done                   ; memory -> back to the main page
dos_l_memt: db 'Memory for the program:', 0
dos_l_memk: db 'Keeping the disk cache:  '
dos_memk1:  db '     K', 0
dos_l_memt2: db 'Taking it as well:       '
dos_memk2:  db '     K', 0
dos_l_meml: db 'Limit:', 0
dos_l_memc: db 'Keep the disk cache', 0
DOS_MEMC_N  equ 19                  ; ...its length, for the click rect. A
                                    ; literal because the label is one and
                                    ; font_width would be a call per paint to
                                    ; re-derive a constant
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
%ifdef DOSTRACE
; =============================================================================
; THE TRACE BUFFERS ARE A PART (SPEC.md 96.29.1)
; =============================================================================
; **WHAT THIS BUYS IS THE CEILING, NOT THE ARENA**, and saying so is the whole
; of why it is worth doing. The two buffers are 35,092 bytes - the ring and
; the rendered dump - and in bss they were 80% of APP_MAX_SIZE, which is a
; HARD 60KB and cannot be raised at all: a package's offsets are 16 bits. The
; trace arm was measured at 61,437 of 61,440 - THREE BYTES - so §96.26's
; cable networking stopped the instrument assembling, and the only row that
; noticed was `dosdbg` quoting the assembler about a probe.
;
; As a part they are outside the image and outside that cap: image + bss goes
; 49,199 -> 23,379, which is the same 38% the SHIPPED build sits at. The ring
; can go back to 512 entries and the next feature in this file has room.
;
; It does NOT give the DOS program memory back, and the arithmetic is worth
; writing down rather than discovering: 35,092 bytes of bss become a 35KB
; CLAIM plus the parts standard's own 1,080 image bytes, so the arena is
; ~1,900 bytes WORSE. That is a fair price for 25,820 bytes under an absolute
; ceiling, in a build nothing ships - and the shipped build is BYTE-IDENTICAL,
; because every line of this is behind the %ifdef.
;
; OP_ZERO, so there is no disk in it at all: os88pkg.py writes a row that asks
; for KB and nothing else, and `make` puts not one extra byte on a floppy.
; OP_OPT, so a machine that cannot spare 35KB still RUNS the program - the
; trace simply refuses, which is what an instrument owes a machine it cannot
; fit on.
%include "os88parts.inc"
OS88_PARTS_BEGIN 1
  OS88_PART OP_ASSET, OP_ZERO | OP_OPT, DOS_TRACE_KB
OS88_PARTS_END
%endif

%include "dosnetabi.inc"             ; the cable translation's numbers, EARLY
                                    ; (SPEC.md 96.26) - its code is dosnet.inc
                                    ; at the end, and the bss table below
                                    ; cannot see an equ from there

PKT_NHAND   equ 4                   ; handles. mTCP opens ONE (IP) and ARP
                                    ; rides the same one; four is room for a
                                    ; client that separates them and one more
PKT_HUSED   equ 0                   ; --- a handle row ---
PKT_HTYPE   equ 1                   ; word: the ethertype, big-endian as it
                                    ; sits on the wire. 0 = every frame
PKT_HRCVO   equ 3                   ; word: the client's receiver...
PKT_HRCVS   equ 5                   ; word: ...far
PKT_HSIZE   equ 7

PKT_VEC_LO  equ 0x60                ; the range the spec reserves, and which a
PKT_VEC_HI  equ 0x80                ; client walks looking for the signature

; --- what CF=1 means, in DH (Crynwr) -----------------------------------------
PKE_BADHAND equ 1
PKE_NOCLASS equ 2
PKE_NOTYPE  equ 3
PKE_NONUM   equ 4
PKE_BADTYPE equ 5
PKE_NOSPACE equ 9
PKE_TYPEUSED equ 10
PKE_BADCMD  equ 11
PKE_CANTSEND equ 12

; --- get_statistics' record: six DWORDS, in the Crynwr order -----------------
; These are the numbers mTCP's PKTTOOL prints, so they are kept for real
; rather than left at zero - and they used to be two DIAGNOSTIC word counters
; written over bytes_out and errors_in, which made a debugging aid into a
; wrong answer to a published call.
PKS_PIN     equ 0                   ; packets in  - frames handed to a client
PKS_POUT    equ 4                   ; packets out - frames a client sent
PKS_BIN     equ 8                   ; ...and their lengths, as the client
PKS_BOUT    equ 12                  ; asked for them rather than as padded
PKS_ERRIN   equ 16                  ; errors in: nothing here can report one -
                                    ; a frame the driver could not read never
                                    ; reaches us at all
PKS_DROP    equ 20                  ; dropped: no handle matched it, or the
                                    ; client refused the buffer

PKT_ETYPE   equ 12                  ; where the ethertype sits in a frame. The
                                    ; ABI publishes the header's SIZE and this
                                    ; is the one offset inside it a demux needs
PKT_STK     equ 1024                ; the tick poll's own stack
                                    ; (SPEC.md 96.23.4.1). The chain under it
                                    ; is OSAPI_DRV_CALL into the kernel, the
                                    ; driver's verb, ne_rx's DMA loop and then
                                    ; the CLIENT's receiver - and the last of
                                    ; those is the one we cannot measure, so
                                    ; this is cut generously rather than to a
                                    ; walked depth

; =============================================================================
; THE NETWORK CLAIM (SPEC.md 96.23.7) - every byte the wire needs, and NONE
; of it in this package's bss
; =============================================================================
; **A BSS BYTE IS A BYTE THE DOS PROGRAM CANNOT HAVE.** §96.3 hands the
; program OSAPI_MEM_AVAIL's whole answer, and this package's image + bss is
; claimed off the same heap first - so every byte declared below the DBSS
; macro comes straight out of the arena, on every machine, whether or not
; there is a wire to use it. The frames, the staging copy and the poll's
; private stack were 4,052 bytes of exactly that: on the 128KB floor machine
; that is 8% of the arena spent on a driver kern_small does not even ship
; (SPEC.md 24.5).
;
; So they live in a claim `dos_pkt_bufs` takes only when net_find answers -
; and the shape that makes it nearly free is that **DS IS THIS CLAIM inside
; every dn_* routine** (SPEC.md 96.26.6). dosnet.inc's premise was already
; "one segment, no segment override", so pointing that one segment at the
; claim instead of at ourselves leaves all 78 of its frame references
; untouched: what changes is the VALUE of the symbols, not the code.
;
; It also collapses two branches that were only ever about which buffer:
; dos_pkt_deliver and dos_pkt_poll each had a `[dos_pkt_xl]` arm choosing
; between the claim and our bss, and both arms are now the same claim.
; **THE ORDER IS THE CARD'S NEEDS FIRST**, so that the two routes' claims
; nest: a card wants the received frame and the stack and nothing else, and
; putting the cable-only parts above them means the card claims 3KB rather
; than paying for a hole.
PKB_RX      equ 0                   ; NET_FRAME: the frame FOR the client -
                                    ; the card's received one, or the one the
                                    ; translation built
PKB_STK     equ 1536                ; PKT_STK bytes of private stack
PKB_STKTOP  equ PKB_STK + PKT_STK
PKB_TX      equ PKB_STKTOP          ; NET_FRAME: the CLIENT's own frame,
                                    ; staged - the CABLE PATH ALONE, because
                                    ; the card hands the client's buffer to
                                    ; the driver where it lies (96.23.8)
PKB_STATE   equ PKB_TX + 1536       ; ...and the translation's own state, laid
                                    ; out by dosnetabi.inc's DNB_*
PKT_RXOFF   equ PKB_RX              ; the packet driver's own name for it,
                                    ; kept because SPEC.md 96.23.7 publishes
                                    ; that one

; **THE TWO ROUTES CLAIM DIFFERENT AMOUNTS**, which is the other half of not
; spending a byte that cannot be used: a card needs the received frame and the
; stack and nothing else, because send_pkt hands the client's own buffer to the
; driver where it lies (SPEC.md 96.23.8). The cable needs the staging frame and
; the whole translation state on top.
PKB_CARDKB  equ (PKB_STK + PKT_STK + 1023) / 1024
PKB_XLKB    equ (PKB_STATE + DNB_SIZE + 1023) / 1024

PKT_CLASS   equ 1                   ; DIX Ethernet (Blue Book), which is what
                                    ; an NE2000 is and what mTCP expects
PKT_TYPE    equ 1
PKT_FUNC    equ 2                   ; basic plus extended: set/get_rcv_mode
                                    ; and get_statistics are answered
PKT_VERSION equ 9

; **THE CHAIN STARTS PAST THE PARTS STANDARD'S OWN BSS** in the trace build
; (SPEC.md 96.29.1). os88parts.inc puts its 86 bytes at OP_BSS_AT, which
; defaults to `os88_image_end` - exactly where this chain starts - so with
; `DB` at 0 the two OVERLAP, silently and completely. What it looked like:
; op_load ran perfectly (op_allkb 35, op_optok 1, op_base and dos_trseg both
; 0x2600) and NOTHING traced, because `op_name` and the first words of this
; table are the same bytes and each was writing over the other. The tell is
; that `op_name` read `&\0S.O88` - a package name with op_base's low word
; sitting on top of its first two characters.
;
; os88parts.inc's own usage note says this in as many words - "OUR words come
; first, yours follow them, and OS88_BSS is told the sum" - and it is one
; line, once, rather than a term on every symbol.
%ifdef DOSTRACE
%assign DB OP_BSS
%else
%assign DB 0
%endif
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
    DBSS DOS_B_VSBUF, VS_SIZEOF  ; OSAPI_VOL_STAT's record (SPEC.md 18.4.6),
                                 ; for AH=36h. OURS and not the program's:
                                 ; DOS gives that call nowhere to put a buffer
    DBSS DOS_B_MEMKB, 2          ; SPEC.md 96.25: the arena cap in KB, 0 = as
                                 ; much as the machine will give
    DBSS DOS_B_MCHK,  DOS_MCHKSZ ; ...and the 'Keep disk cache' check box's own
                                 ; record (os88ui.inc), whose ON byte IS the
                                 ; setting - os88ui_chkhit toggles and redraws
                                 ; it, so a copy here would be a second truth
    DBSS DOS_B_MBUF,  DOS_MEMBUF ; the limit field's text...
    DBSS DOS_B_MLN,   DOS_LNSZ   ; ...and its os88line block
    DBSS DOS_B_MX,    2          ; the memory page's content origin, banked
    DBSS DOS_B_MY,    2          ; for one paint (dos_ctop's shape)
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
                                ; ...and the RING is not here: it is in the
                                ; part (SPEC.md 96.29.1), with the rendered
                                ; dump beside it. 35,092 bytes that used to be
                                ; 80% of APP_MAX_SIZE
    DBSS DOS_B_TRACEI, 2                ; the entry a result belongs to, 0 =
                                        ; the call was filtered out
    DBSS DOS_B_TRNM,   DOS_TRNM_N * 13      ; the NAMES the program passed
    DBSS DOS_B_TRNMI,  1                    ; ...and how many, capped
    DBSS DOS_B_TRSEG,  2        ; THE PART'S SEGMENT, banked by dos_entry.
                                ; 0 = the part was refused (it is OP_OPT), and
                                ; dos_trace tests it: an instrument that
                                ; cannot fit writes NOTHING rather than
                                ; writing to segment zero. It is also what the
                                ; HOST reads - tools/os88dosdbg.py needs one
                                ; word to find the ring, where op_seg's
                                ; arithmetic would have to be reimplemented
                                ; outside the guest
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
FH_VOL      equ 22                  ; the VOLUME the name is resolved against
                                    ; (SPEC.md 96.6.2). A handle is a name
                                    ; here and not a file, so without this a
                                    ; read re-resolves it wherever the program
                                    ; happens to be standing - which is how a
                                    ; copy off B: onto C: reads the
                                    ; destination back into itself
FH_SIZEOF   equ 23
FHF_USED    equ 1
FHF_WRITE   equ 2                   ; opened by AH=3Ch: writes are accepted
FHF_MADE    equ 4                   ; ...and at least one window has been
                                    ; flushed, so the next one APPENDS
FHF_WHOLE   equ 8                   ; a COMPRESSED file, read whole and
                                    ; expanded: the window is the file and
                                    ; never refills (SPEC.md 96.11.1)

DOS_PFIN    equ 24                  ; AH=29h reads at most this much of the
                                    ; program's name: "D:NNNNNNNN.EEE" is 14,
                                    ; so it is a whole one with room over
DOS_PFSEPN  equ 14                  ; ...and the separators above the blank
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
DTA_VOL     equ 16                  ; byte: ...and the VOLUME it was walking,
                                    ; for the same reason one level along - a
                                    ; walk that began on B: continues on B:
                                    ; however the program has moved since
                                    ; (SPEC.md 96.6.2)
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


; =============================================================================
; THE PACKET DRIVER (SPEC.md 96.23)
; =============================================================================
; A Crynwr packet driver over ETHER.DRV's raw verbs (SPEC.md 72.22). What is
; published is an INTERFACE - a vector in 60h..80h whose handler carries
; `PKT DRVR` at offset 3, and a dozen functions through AH - and what consumes
; it is a DOS application bringing its own TCP/IP.
;
; ETHER.DRV hooks no interrupt vector at all, so there is no IRQ to arbitrate
; and no ISR to hand over: this is a translation and not a negotiation. The
; price is that receive is a POLL underneath an UP-CALL, which is 96.23.4.

dos_pkt_name: db 'os8088 ETHER', 0

; -----------------------------------------------------------------------------
; dos_pkt_entry - THE VECTOR (SPEC.md 96.23.2)
;
; The first three bytes are a jump and the signature starts at offset 3, which
; is the whole of how a client finds this. A short jump would be two and put
; the signature one byte early, so the assertion below is not decoration - it
; is the one thing in this file a reader cannot check by eye.
; -----------------------------------------------------------------------------
dos_pkt_entry:
    jmp near dos_pkt_go
dos_pkt_sig:
    db 'PKT DRVR', 0
%if dos_pkt_sig - dos_pkt_entry != 3
 %error "the PKT DRVR signature must begin at offset 3 of the handler (Crynwr)"
%endif

; -----------------------------------------------------------------------------
; The gate, in dos_int21's shape and for its reasons (SPEC.md 96.7.1): entered
; on the CLIENT's stack with the client's segment registers, so the first thing
; it does is reach its own data through CS, and the carry flag it returns is
; the one in the FLAGS image the `int` pushed.
;
;   [bp]=DS [bp+2]=BP [bp+4]=IP [bp+6]=CS [bp+8]=FLAGS
;   [bp-2]=SI [bp-4]=DI [bp-6]=ES
;
; SI, DI and ES are banked BELOW bp and restored from there, so a handler that
; leaves the stack at any depth still returns the client's registers - and
; `driver_info` writes its DS:SI answer into [bp] and [bp-2] rather than into
; the live registers, which is the same trick AH=35h uses one section up.
; -----------------------------------------------------------------------------
dos_pkt_go:
    sti
    push bp
    push ds
    mov bp, sp
    push si
    push di
    push es
    push ds                         ; **THE CLIENT'S DS, BANKED FROM THE
    push cs                         ; REGISTER** (SPEC.md 96.23.9) - the
    pop ds                          ; version that read it back out of [bp]
    pop word [dos_pkt_cds]          ; answered our OWN segment, and `[bp]` is
                                    ; SS-relative so it was never going to be
                                    ; checkable by eye. This pops the value
                                    ; pushed one instruction earlier, with DS
                                    ; already ours so the store lands here

    call dos_pkt_poll               ; **DRAIN FIRST** (SPEC.md 96.23.4): a
                                    ; client in a send loop receives as it
                                    ; sends, without waiting for a tick

    cmp ah, 1
    je .info
    cmp ah, 2
    je .access
    cmp ah, 3
    je .release
    cmp ah, 4
    je .send
    cmp ah, 5
    je .term
    cmp ah, 6
    je .getaddr
    cmp ah, 20
    je .setmode
    cmp ah, 21
    je .getmode
    cmp ah, 24
    je .stats
    mov dh, PKE_BADCMD              ; a client asking for a feature it can
    jmp .err                        ; live without expects exactly this

; --- AH=1 driver_info --------------------------------------------------------
; out BX=version CH=class DX=type CL=number DS:SI=name AL=functionality
.info:
    mov bx, PKT_VERSION
    mov ch, PKT_CLASS
    mov dx, PKT_TYPE
    mov cl, 0                       ; interface number
    mov al, PKT_FUNC
    mov word [bp-2], dos_pkt_name   ; the BANKED SI and DS, not the live ones:
    mov [bp], cs                    ; the exit path restores both from here
    jmp .ok

; --- AH=2 access_type --------------------------------------------------------
; in AL=if_class BX=if_type DL=if_number DS:SI=type CX=typelen ES:DI=receiver
; out AX = a handle
;
; DS:SI is the CLIENT's - our own DS is CS by now - so the ethertype is read
; through the banked [bp]. ES and DI are still the client's in the live
; registers, which is what makes the receiver pointer a plain bank.
.access:
    cmp al, PKT_CLASS
    jne .noclass
    cmp bx, PKT_TYPE                ; 0FFFFh is the spec's "any type of card"
    je .clsok
    cmp bx, 0xFFFF
    jne .notype
.clsok:
    or dl, dl                       ; one card, number 0
    jz .numok
    cmp dl, 0xFF
    jne .nonum
.numok:
    push cx
    push si
    xor ax, ax                      ; AX = the ethertype, 0 = every frame
    or cx, cx
    jz .anytype
    cmp cx, 2                       ; **A LENGTH OTHER THAN 2 IS REFUSED**
    jne .badtype                    ; rather than read short: an ethertype is
    push es                         ; two bytes and a client that passed a
    mov es, [bp]                    ; longer one means a protocol this card
    mov ah, [es:si]                 ; layer does not have (802.2 LSAPs)
    mov al, [es:si+1]
    pop es
.anytype:
    call dos_pkt_hnew               ; BX = the row, or CF=1 = full
    jc .nospace
    mov [bx+PKT_HTYPE], ax
    mov [bx+PKT_HRCVO], di
    mov ax, es
    mov [bx+PKT_HRCVS], ax
    mov byte [bx+PKT_HUSED], 1
    call dos_pkt_claim              ; **THE WIRE, ON THE FIRST HANDLE**
    jc .noclaim                     ; (SPEC.md 96.23.5) - not at bracket entry
    mov ax, bx                      ; the handle IS the row address: it is
    pop si                          ; ours to choose and this makes every
    pop cx                          ; later lookup a bounds check instead of
    jmp .ok                         ; a multiply
.badtype:
    pop si
    pop cx
    mov dh, PKE_BADTYPE
    jmp .err
.nospace:
    pop si
    pop cx
    mov dh, PKE_NOSPACE
    jmp .err
.noclaim:
    mov byte [bx+PKT_HUSED], 0      ; the row goes back: a handle that cannot
    pop si                          ; receive is worse than a refusal
    pop cx
    mov dh, PKE_NOSPACE
    jmp .err
.noclass:
    mov dh, PKE_NOCLASS
    jmp .err
.notype:
    mov dh, PKE_NOTYPE
    jmp .err
.nonum:
    mov dh, PKE_NONUM
    jmp .err

; --- AH=3 release_type -------------------------------------------------------
; in BX = the handle
.release:
    call dos_pkt_hchk
    jc .badhand
    mov byte [bx+PKT_HUSED], 0
    call dos_pkt_idle               ; the last handle takes the claim with it
    jmp .ok
.badhand:
    mov dh, PKE_BADHAND
    jmp .err

; --- AH=4 send_pkt -----------------------------------------------------------
; in DS:SI = the frame, CX = its length. The client's DS again.
.send:
    cmp cx, NET_EHSIZE
    jb .cantsend
    cmp cx, NET_FRAME
    ja .cantsend
    ; --- **THERE IS NO STAGING COPY** (SPEC.md 96.23.8) --------------------
    ; NETV_RAWTX takes the segment (SPEC.md 72.22.4), so the client's own
    ; buffer is handed over where it lies: DX = the DS the `int` pushed, SI =
    ; the offset it was called with. The driver copies into eth_txb either
    ; way, so a staging copy of ours was a SECOND copy of 1,514 bytes on a
    ; 4.77MHz machine and 1,514 bytes of claim to hold it - and it was where
    ; a whole class of segment bug lived, because it was the one place this
    ; package addressed the client's memory itself.
    mov dx, [dos_pkt_cds]           ; the CLIENT's DS, banked at the gate
    push cx                         ; ...and the LENGTH, because get_statistics
                                    ; wants it after the route has run and
                                    ; OSAPI_DRV_CALL publishes CX as the
                                    ; driver's to define
    cmp byte [dos_pkt_xl], 0
    jne .xlate                      ; the cable carries no frames (SPEC.md
                                    ; 72.22.3), so they are TRANSLATED
    mov bh, DRVC_NET
    mov bl, NETV_RAWTX
    call OSAPI_DRV_CALL
    jnc .sent
    pop cx
    jmp short .cantsend
.xlate:
    ; --- the translation reads the frame in OUR segment --------------------
    ; dn_tx and everything under it use no segment override, because every
    ; other byte they touch is ours. So this is the one copy the card path
    ; does not make - 42 to 1514 bytes, against a wire that moves 3,741 a
    ; second, which is not the cost that decides anything here.
    push cx
    push si
    push di
    push es
    push ds
    mov es, [dos_pkt_bseg]          ; ES:DI is the CLAIM's staging frame and
    mov di, dos_pkt_txs             ; DS:SI the client's own buffer
    mov ds, dx
    call dos_pkt_copy               ; DS:SI -> ES:DI, CX bytes
    pop ds
    pop es
    pop di
    pop si
    pop cx
    mov si, dos_pkt_txs
    call dn_tx
.sent:
    ; --- get_statistics' OWN numbers, and they are the real ones -----------
    ; Both routes end here so the count is written once. It is the client's
    ; own frame length that is added, not the driver's padded one: a Crynwr
    ; client asked for these bytes and mTCP's PKTTOOL prints them back.
    pop cx
    add word [dos_pkt_stats+PKS_POUT], 1
    adc word [dos_pkt_stats+PKS_POUT+2], 0
    add word [dos_pkt_stats+PKS_BOUT], cx
    adc word [dos_pkt_stats+PKS_BOUT+2], 0
    jmp .ok
.cantsend:
    mov dh, PKE_CANTSEND
    jmp .err

; --- AH=5 terminate ----------------------------------------------------------
.term:
    call dos_pkt_hchk
    jc .badhand
    call dos_pkt_rawdrop            ; NOT dos_pkt_shut: the buffers are the
    jmp .ok                         ; bracket's and a program that terminates
                                    ; the driver may still open it again

; --- AH=6 get_address --------------------------------------------------------
; in BX = handle, ES:DI = a buffer, CX = its size; out CX = bytes written
.getaddr:
    call dos_pkt_hchk
    jc .badhand
    cmp cx, 6
    jb .badhand
    push si
    push di
    mov si, dos_pkt_mac             ; banked by the claim (SPEC.md 72.22), so
    mov cx, 6                       ; this costs no driver call at all
    call dos_pkt_copy             ; DS:SI -> ES:DI
    pop di
    pop si
    mov cx, 6
    jmp .ok

; --- AH=20 / 21 set and get receive mode -------------------------------------
; 3 is "every frame addressed to me, plus broadcast", which is the mode
; ne_init leaves the card in and the only one this driver can honestly offer.
.setmode:
    cmp cx, 3
    jne .badmode
    mov byte [dos_pkt_mode], 3
    jmp .ok
.badmode:
    mov dh, PKE_BADTYPE
    jmp .err
.getmode:
    xor ax, ax
    mov al, [dos_pkt_mode]
    jmp .ok

; --- AH=24 get_statistics ----------------------------------------------------
; out DS:SI = six dwords: packets in, packets out, bytes in, bytes out,
;     errors in, packets dropped.
.stats:
    mov word [bp-2], dos_pkt_stats
    mov [bp], cs
    jmp .ok

.ok:
    and word [bp+8], 0xFFFE         ; CF=0 in the RETURNED flags, not the live
    jmp short .leave                ; ones - the iret would discard those
.err:
    or word [bp+8], 1
.leave:
    ; STKBALANCE-OK: dos_int21's arrangement and its reasons (SPEC.md 96.7.1)
    ; - the frame is restored from `bp`, so this gate's promise does not rest
    ; on every handler above being balanced.
    mov si, [bp-2]
    mov di, [bp-4]
    mov es, [bp-6]
    mov sp, bp
    pop ds
    pop bp
    iret

; -----------------------------------------------------------------------------
; dos_pkt_hnew / dos_pkt_hchk - the handle table
;
; **A HANDLE IS THE ROW'S OWN ADDRESS**, which is ours to choose and makes
; every later lookup a bounds check rather than a multiply. hchk is what makes
; that safe: a client handing back a number it made up is refused before it
; can index anything.
; out: hnew  CF=0 with BX = a free row, CF=1 = the table is full
;      hchk  CF=0 = BX is one of ours and in use
; -----------------------------------------------------------------------------
dos_pkt_hnew:
    push cx
    mov bx, dos_pkt_htab
    mov cx, PKT_NHAND
.l:
    cmp byte [bx+PKT_HUSED], 0
    je .got
    add bx, PKT_HSIZE
    loop .l
    pop cx
    stc
    ret
.got:
    pop cx
    clc
    ret

dos_pkt_hchk:
    push ax
    push dx
    mov ax, bx
    sub ax, dos_pkt_htab            ; below the table wraps to a huge unsigned,
    cmp ax, PKT_NHAND * PKT_HSIZE   ; so one compare catches both ends
    jae .no
    xor dx, dx
    mov cx, PKT_HSIZE               ; ...and it must be ON a row boundary, not
    div cx                          ; merely inside the table
    or dx, dx
    jnz .no
    cmp byte [bx+PKT_HUSED], 0
    je .no
    pop dx
    pop ax
    clc
    ret
.no:
    pop dx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; dos_pkt_claim / dos_pkt_idle / dos_pkt_shut - the raw claim's lifetime
;
; Taken on the FIRST handle and dropped when the last one goes or the bracket
; ends (SPEC.md 96.23.5). A DOS program that never asks for a packet driver
; leaves our own stack running, which is most of them.
; -----------------------------------------------------------------------------
dos_pkt_claim:
    cmp byte [dos_pkt_raw], 0
    jne .have
    ; --- **THE CABLE HAS NO RAW CLAIM TO TAKE** (SPEC.md 96.26.4) ----------
    ; NETV_RAW is one of the three verbs NET.DRV refuses (72.22.3), so asking
    ; for it here would fail every access_type on the machine this translation
    ; exists for. There is nothing to claim: no ring, no card, and our own
    ; stack is not using a wire the DOS program can collide with.
    ;
    ; It also has to invent the STATION ADDRESS the claim would have handed
    ; back, because get_address must answer something and there is no PROM to
    ; read. Locally-administered unicast again, and one digit off the
    ; gateway's - a client that saw its own address on both ends of a frame
    ; would drop it as a loop.
    cmp byte [dos_pkt_xl], 0
    je .real
    push ax
    push cx
    push si
    push di
    mov si, dn_ourmac_c             ; **THE IMAGE COPY AND NOT THE CLAIM'S**:
    mov di, dos_pkt_mac             ; dn_ourmac is an offset into the network
    mov cx, 6                       ; claim now (SPEC.md 96.26.6) and DS here
    call dn_copy                    ; is ours, so reading it would fetch six
                                    ; bytes of our own bss. The constant is in
                                    ; the image, which is the one place both
                                    ; segments can see
    pop di
    pop si
    pop cx
    pop ax
    mov byte [dos_pkt_raw], 1
    clc
    ret
.real:
    push ax
    push bx
    push di
    mov di, dos_pkt_mac             ; the claim hands back the station address
    mov al, 1                       ; (SPEC.md 72.22) - a consumer that is the
    mov bh, DRVC_NET                ; stack now cannot build a frame without it
    mov bl, NETV_RAW
    call OSAPI_DRV_CALL
    jc .no
    mov byte [dos_pkt_raw], 1
    pop di
    pop bx
    pop ax
.have:
    clc
    ret
.no:
    pop di
    pop bx
    pop ax
    stc
    ret

dos_pkt_idle:                       ; the LAST handle takes the claim with it
    push bx
    push cx
    mov bx, dos_pkt_htab
    mov cx, PKT_NHAND
.l:
    cmp byte [bx+PKT_HUSED], 0
    jne .busy
    add bx, PKT_HSIZE
    loop .l
    pop cx
    pop bx
    jmp dos_pkt_rawdrop             ; a TAIL JUMP and not a fall-through: the
                                    ; label between them would take the local
                                    ; names below it into its own namespace,
                                    ; which is how `.busy` stopped resolving
.busy:
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_pkt_rawdrop - the handles and the raw claim, but NOT the buffers
; dos_pkt_shut    - ...and the buffers too, which only the bracket may do
;
; **THE SPLIT IS THE POINT.** The first version had release_type free the
; buffer claim along with everything else, and that is unrecoverable: §96.3
; has already given the whole heap to the program, so a client that released
; a handle and asked for another got its access_type refused for ever. The
; buffers belong to the BRACKET's lifetime and the raw claim to the handles'.
; -----------------------------------------------------------------------------
dos_pkt_rawdrop:
    push ax
    push bx
    push cx
    push di
    mov cx, PKT_NHAND               ; every handle goes, whichever path came
    mov bx, dos_pkt_htab            ; here: terminate is defined to end them
.z:
    mov byte [bx+PKT_HUSED], 0
    add bx, PKT_HSIZE
    loop .z
    cmp byte [dos_pkt_raw], 0
    je .out
    cmp byte [dos_pkt_xl], 0        ; nothing was claimed on the translation
    jne .letgo                      ; path, so there is nothing to give back
    xor di, di                      ; no MAC wanted on the way out
    xor al, al                      ; release
    mov bh, DRVC_NET
    mov bl, NETV_RAW
    call OSAPI_DRV_CALL
.letgo:
    mov byte [dos_pkt_raw], 0
.out:
    pop di
    pop cx
    pop bx
    pop ax
    ret

dos_pkt_shut:
    call dos_pkt_rawdrop
    cmp word [dos_pkt_bseg], 0      ; ...and NOW the buffers. The kernel frees
    je .nobuf                       ; a dead instance's claims anyway
    push dx                         ; (os88api.inc), so this is only about
    mov dx, [dos_pkt_bseg]          ; handing memory back MID-SESSION - which
    call OSAPI_MEM_FREE             ; is exactly what a DOS window that stays
    mov word [dos_pkt_bseg], 0      ; open after a run is
    pop dx
.nobuf:
    ret

; -----------------------------------------------------------------------------
; dos_pkt_poll - drain the ring, up-calling the client once per frame
;
; **BP IS NOT TOUCHED**: this is called from the gate, where BP is the frame
; pointer every exit path restores the client's registers through.
;
; The budget is what stops a busy segment of network from holding a tick for
; as long as it likes, and it is the ring's own depth rather than a guess: the
; NE2000 holds about ten frames, so a drain of ten empties whatever was there
; and an eleventh would be a frame that arrived while we were working.
; -----------------------------------------------------------------------------
PKT_BUDGET  equ 10

dos_pkt_poll:
    cmp byte [dos_pkt_raw], 0
    je .out                         ; no claim, no frames - and this is the
                                    ; common case: most DOS programs are not
                                    ; network programs
    cmp byte [dos_pkt_busy], 0
    jne .out                        ; **THE TICK CAN LAND INSIDE A CALL** and
                                    ; the client's receiver is not re-entrant
                                    ; merely because ours is
    cmp word [dos_pkt_bseg], 0      ; **AND THE CLAIM GUARD IS BOTH ROUTES'**
    je .out                         ; now (SPEC.md 96.23.7): it was the card's
                                    ; alone while the translation kept its
                                    ; frame in bss, and the symptom of getting
                                    ; that wrong was an ARP that vanished -
                                    ; dn_tx had swallowed the request and
                                    ; built the reply correctly, and this test
                                    ; stopped the poll before anything came to
                                    ; collect it
    mov byte [dos_pkt_busy], 1
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov dx, PKT_BUDGET
.f:
    push dx                         ; the budget: DX is the segment argument now
    cmp byte [dos_pkt_xl], 0
    jne .xl
    mov di, PKT_RXOFF
    mov cx, NET_FRAME
    mov dx, [dos_pkt_bseg]
    mov bh, DRVC_NET
    mov bl, NETV_RAWRX
    call OSAPI_DRV_CALL
    pop dx
    jc .done
    jmp short .got
.xl:
    call dn_ready                   ; ...and it is ALREADY at PKB_RX, because
    pop dx                          ; the translation BUILT it there - which
    jc .done                        ; is the one place the two routes differ
                                    ; and the only reason this branch is left
.got:                        ; the ring is empty
    cmp cx, NET_FRAME                ; the TRUE length may exceed what we asked
    ja .next                        ; for (SPEC.md 72.22.2), and a cut frame
                                    ; handed to a stack is worse than none
    cmp cx, NET_EHSIZE
    jbe .next
    push dx                         ; **THE BUDGET GOES ON THE STACK ACROSS
    call dos_pkt_deliver            ; THE UP-CALL**, because DX is not ours
    pop dx                          ; over it: dos_pkt_deliver far-calls the
                                    ; CLIENT's receiver twice, and a client
                                    ; owes us no register at all. With the
                                    ; count in DX a receiver that used it
                                    ; turned a ten-frame drain into up to
                                    ; 65,535 of them, inside a tick handler -
                                    ; the same livelock dn_pump's CL counter
                                    ; had, one layer out
.next:
    dec dx
    jnz .f
.done:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    mov byte [dos_pkt_busy], 0
.out:
    ret

; -----------------------------------------------------------------------------
; dos_pkt_deliver - one frame in the claim, CX bytes, to whoever registered
;
; **THE UP-CALL IS TWO CALLS** and that is the Crynwr contract rather than a
; choice (SPEC.md 96.23.4): AX=0 asks the client for somewhere to put CX
; bytes, and AX=1 hands the same buffer back full. A client that answers 0:0
; has refused it, and the frame is gone - it is off the ring already and there
; is nowhere to put it back.
; -----------------------------------------------------------------------------
dos_pkt_deliver:
    push es                         ; **ONE SOURCE ON BOTH ROUTES NOW** - the
    mov es, [dos_pkt_bseg]          ; card writes the claim through NETV_RAWRX
    mov ax, [es:PKT_RXOFF+PKT_ETYPE] ; and the translation BUILDS in it
    pop es                          ; (SPEC.md 96.23.7), so the two arms this
                                    ; routine had, and the [dos_pkt_xl] test
                                    ; that chose between them, are gone
    xchg al, ah                     ; the wire is big-endian and we are not
    mov bx, dos_pkt_htab
    mov si, PKT_NHAND
.l:
    cmp byte [bx+PKT_HUSED], 0
    je .next
    cmp word [bx+PKT_HTYPE], 0
    je .hit                         ; 0 = every frame, whatever its type
    cmp [bx+PKT_HTYPE], ax
    je .hit
.next:
    add bx, PKT_HSIZE
    dec si
    jnz .l
                                    ; nobody registered for it, so it is
                                    ; dropped - which is what a packet driver
                                    ; does and not an error of ours, and
                                    ; get_statistics has a FIELD for saying so
.dropped:
    add word [dos_pkt_stats+PKS_DROP], 1
    adc word [dos_pkt_stats+PKS_DROP+2], 0
    ret
.hit:
    mov ax, [bx+PKT_HRCVO]
    mov [dos_pkt_cvec], ax
    mov ax, [bx+PKT_HRCVS]
    mov [dos_pkt_cvec+2], ax
    mov [dos_pkt_chand], bx         ; the handle, which both calls carry

    push cx                         ; --- call one: where shall I put it? ---
    xor ax, ax
    push ds
    push bp                         ; the CLIENT is about to run: it owes us
    call far [dos_pkt_cvec]         ; nothing, and BP is the gate's frame
    pop bp
    pop ds
    pop cx
    mov ax, es
    or ax, di
    jz .dropped                     ; 0:0 - refused, and the frame is gone -
                                    ; it is off the ring already and there is
                                    ; nowhere to put it back, so it is a DROP
                                    ; and get_statistics counts it as one

    push cx                         ; --- the copy, the claim to theirs ---
    push di
    push es
    push ds
    mov si, PKT_RXOFF               ; DS:SI is the claim and ES:DI the buffer
    mov ds, [dos_pkt_bseg]          ; the client just gave us
    call dos_pkt_copy
    pop ds
    pop es
    pop di
    pop cx

    mov bx, [dos_pkt_chand]         ; --- call two: here it is ---
    mov si, di                      ; DS:SI is the buffer THEY chose, which is
    mov ax, 1                       ; what the contract hands back
    push ds
    push bp
    push es
    pop ds                          ; **DS IS THE CLIENT'S FROM HERE TO THE
    call far [cs:dos_pkt_cvec]      ; POP**, so the vector is only reachable
    pop bp                          ; with an override - and reading it from
    pop ds                          ; the client's segment would be a wild
                                    ; far call into the program's own data
    add word [dos_pkt_stats+PKS_PIN], 1
    adc word [dos_pkt_stats+PKS_PIN+2], 0
    add word [dos_pkt_stats+PKS_BIN], cx
    adc word [dos_pkt_stats+PKS_BIN+2], 0
.out:
    ret

; -----------------------------------------------------------------------------
; dos_pkt_copy - DS:SI -> ES:DI, CX bytes
;
; Written out rather than `rep movsb` for the reason every package here has
; one of these: a package's ES is the kernel's on entry to a callback and its
; own only where it has just set it, so the string instructions are the one
; family whose implicit segment is worth not relying on.
; -----------------------------------------------------------------------------
dos_pkt_copy:
    push ax
    push cx
    push si
    push di
    jcxz .out
.l:
    mov al, [si]
    mov [es:di], al
    inc si
    inc di
    loop .l
.out:
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_pkt_bufs - the two frame buffers, and WHY THEY ARE CLAIMED HERE
;
; **BEFORE THE ARENA, OR NOT AT ALL** (SPEC.md 96.23.7). §96.3 claims
; OSAPI_MEM_AVAIL's whole answer for the program, with no arithmetic between
; the two calls - so by the time a client calls access_type there is no heap
; left and a claim then would always be refused. Taking it here means
; OSAPI_MEM_AVAIL simply answers 3KB less, which is the honest trade and the
; one the DOS program can see.
;
; A MACHINE WITH NO CARD CLAIMS NOTHING, which is the whole point of moving
; them out of bss: 3,028 bytes of a package's bss are zeroed into its heap
; claim at every launch, on every machine, whether or not there is a wire.
; out: [dos_pkt_bseg] = the claim, or 0
; -----------------------------------------------------------------------------
dos_pkt_bufs:
    push ax
    push bx
    push cx
    push dx
    push di
    push es
    mov word [dos_pkt_bseg], 0
    call net_find                   ; **EITHER WIRE** (SPEC.md 96.26.1): the
    jc .out                         ; CARD if there is one and the CABLE if
                                    ; there is not - net_find's own preference
                                    ; order, for its own reason
    mov byte [dos_pkt_xl], 0
    ; --- WHICH ROUTE, AND IT IS DECIDED BY WHICH WIRE ----------------------
    ; A card carries frames, so the packet driver hands the client's frames
    ; straight to it. The cable carries SOCKETS and no frames at all (SPEC.md
    ; 72.22.3), so on that wire the frames are TRANSLATED - the endpoint in
    ; dosnet.inc terminates the client's TCP and re-opens it as a socket
    ; (96.26.3).
    mov ax, PKB_CARDKB               ; ...and the two want DIFFERENT amOUNTS
%ifdef DOSNET_CARD
    jmp short .xlate                ; ...and this knob forces the translation
                                    ; where a card is present, which is the
                                    ; only way it can be DRIVEN until the
                                    ; harness has a cable partner
                                    ; (DOS-CABLE-NET-PLAN 7.0)
%endif
    cmp byte [net_cls], DRVC_NET    ; **DRVC_NET IS THE CARD.** The cable is
    je .claim                       ; DRVC_FILE - it moved there when it
                                    ; started serving a volume (SPEC.md 62.9)
                                    ; and the comment at the constant's own
                                    ; definition still says "the parallel
                                    ; link", which is how this compare got
                                    ; written the wrong way round once
.xlate:
    mov byte [dos_pkt_xl], 1
    mov ax, PKB_XLKB                ; the translation wants the staging frame
                                    ; and its own state as well
.claim:
    push ax
    call OSAPI_MEM_CLAIM
    pop cx                          ; (the size, for the zeroing below)
    jc .out                         ; **A REFUSAL IS SURVIVABLE**: the program
    mov [dos_pkt_bseg], dx          ; still runs, the interface is simply not
                                    ; published (dos_pkt_start tests this)
    ; --- AND IT IS ZEROED, which is not tidiness ---------------------------
    ; A heap claim arrives with whatever was last in it, and this one's bytes
    ; go ON THE WIRE: ne_tx pads a short frame but does not touch the length
    ; the caller gave, so a send that staged nothing would put 42 bytes of
    ; somebody else's heap onto the network. It is also where every dn_*
    ; counter, flow row and name slot now lives, and those are read before
    ; they are written.
    mov es, dx
    xor di, di
    mov ax, cx
    mov cl, 10
    shl ax, cl                      ; KB -> bytes; the claim is in KB and the
    mov cx, ax                      ; loop is in bytes
    xor al, al
.z:
    mov [es:di], al
    inc di
    loop .z
    cmp byte [dos_pkt_xl], 0
    je .out
    call dn_init                    ; ...and THEN the translation's own start,
                                    ; which copies the two MACs in and needs
                                    ; the claim to exist (SPEC.md 96.26.6)
.out:
    pop es
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_pkt_start - publish the interface, if there is a card to publish it over
;
; **NOT PUBLISHED ON A MACHINE WITH NO NIC**, and that is SPEC.md 96.15.1's
; argument for the third time in this package: a signature a client can find,
; over a card that is not there, sends it to open a handle that cannot work
; and it has no way to ask why. Its absence sends it to its own "no packet
; driver" path, which every mTCP application has and which says so.
;
; The CARD by name and not net_find: the cable answers the socket verbs too
; and refuses every raw one (SPEC.md 72.22.3), so preferring one of two is
; the wrong question here.
; -----------------------------------------------------------------------------
dos_pkt_start:
    push bx
    mov byte [dos_pkt_vec], 0
    mov byte [dos_pkt_raw], 0
    mov byte [dos_pkt_busy], 0
    mov word [dos_pkt_can], 0x5A5A  ; the canary, armed
    mov byte [dos_pkt_mode], 3      ; what the card is in, and what get_rcv_mode
                                    ; answers until somebody sets it
    cmp byte [dos_pkt_xl], 0        ; the translation needs no buffers...
    jne .go
    cmp word [dos_pkt_bseg], 0      ; ...and the card path's dos_pkt_bufs
    je .none                        ; already asked whether there is a card
                                    ; AND got the buffers for it, so that is
                                    ; both of its questions in one compare
.go:
    call dos_pkt_install
    cmp byte [dos_pkt_vec], 0
    je .none
    call dos_pkt_hook08
.none:
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_pkt_install - find a free vector and put ourselves on it (SPEC.md 96.23.2)
; out: [dos_pkt_vec] = the vector taken, or 0 if every one was occupied
;
; **SEARCHED RATHER THAN CHOSEN**, which costs four instructions and buys the
; case that actually happens: a program the user ran earlier left something at
; 60h, or the .COM being run is itself a packet driver for a card we have not
; got. A vector whose handler already answers to `PKT DRVR` is somebody's.
; -----------------------------------------------------------------------------
dos_pkt_install:
    push ax
    push bx
    push cx
    push si
    push di
    push es
    mov byte [dos_pkt_vec], 0
    mov bl, PKT_VEC_LO
.v:
    mov bh, 0
    mov ax, bx
    shl ax, 1
    shl ax, 1                       ; the vector's slot: v * 4
    mov si, ax
    xor ax, ax
    mov es, ax
    mov ax, [es:si+2]               ; its segment...
    or ax, [es:si]                  ; ...and offset: a NULL vector is free
    jz .take
    call dos_pkt_issig              ; ...and so is one nobody signed
    jc .take
.next:
    inc bl
    cmp bl, PKT_VEC_HI
    jbe .v
    jmp short .out                  ; every one taken: [dos_pkt_vec] stays 0
                                    ; and dos_run reports it
.take:
    cli
    mov word [es:si], dos_pkt_entry
    mov [es:si+2], cs
    sti
    mov [dos_pkt_vec], bl
.out:
    pop es
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; --- dos_pkt_issig - does the handler at ES:SI carry `PKT DRVR` at offset 3? --
; out: CF=1 = it does NOT (the vector is free to take)
dos_pkt_issig:
    push ax
    push bx
    push cx
    push si
    push di
    push ds
    push es
    mov ax, [es:si+2]
    mov bx, [es:si]
    mov ds, ax
    mov si, bx
    add si, 3
    push cs
    pop es
    mov di, dos_pkt_sig
    mov cx, 8
.c:
    mov al, [si]
    cmp al, [es:di]
    jne .free
    inc si
    inc di
    loop .c
    pop es                          ; every byte matched: somebody else's
    pop ds
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    clc
    ret
.free:
    pop es
    pop ds
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; dos_pkt_hook08 - chain INT 08h for the life of the bracket (SPEC.md 96.23.4)
;
; This is the poll that makes asynchronous delivery real: a client that calls
; us once and then waits still receives. The unhook is dos_restore_machine's,
; which puts the WHOLE IVT back.
; -----------------------------------------------------------------------------
dos_pkt_hook08:
    push ax
    push es
    xor ax, ax
    mov es, ax
    cli
    mov ax, [es:0x08*4]
    mov [dos_pkt_old08], ax
    mov ax, [es:0x08*4+2]
    mov [dos_pkt_old08+2], ax
    mov word [es:0x08*4], dos_pkt_tick
    mov [es:0x08*4+2], cs
    sti
    pop es
    pop ax
    ret

; -----------------------------------------------------------------------------
; dos_pkt_tick - IRQ0, chained, with the poll on a stack of our own
;
; **THE CHAIN GOES FIRST**, so the tick reaches the kernel at the depth it
; always did and on the stack it always did - the scheduler saves SP per task
; and a private one under it is a thing nothing here has tested.
;
; **THEN THE STACK SWAPS** (SPEC.md 96.23.4.1). The poll's deepest chain is
; OSAPI_DRV_CALL into the kernel, into the driver, into ne_rx's byte-at-a-time
; DMA loop and out into the client's receiver, and without this it would land
; on whatever stack the DOS program was running on at whatever depth it had
; reached - a .COM's default being 256 bytes under its own image. `mov
; [cs:x], sp` and `mov sp, imm16` need no register, which is what makes the
; swap possible at a gate where every register is the program's.
; -----------------------------------------------------------------------------
dos_pkt_tick:
    pushf                           ; the chain, exactly as an `int` would
    call far [cs:dos_pkt_old08]     ; have entered it - and through CS, since
                                    ; DS is the interrupted program's
    push ax
    push ds
    push cs
    pop ds
    cmp byte [dos_pkt_raw], 0       ; nothing claimed: not even the swap
    je .out
    cmp byte [dos_pkt_busy], 0      ; already inside a poll somewhere below
    jne .out
    mov [dos_pkt_sss], ss
    mov [dos_pkt_ssp], sp
    mov ax, [dos_pkt_bseg]          ; **THE STACK IS IN THE NETWORK CLAIM**
                                    ; (SPEC.md 96.23.7), not in our bss - and
                                    ; [dos_pkt_raw] above is what proves there
                                    ; is one: a claim that was refused
                                    ; publishes no interface, so nothing can
                                    ; have taken a handle
    cli
    mov ss, ax                      ; **SS AND SP IN CONSECUTIVE INSTRUCTIONS**
    mov sp, dos_pkt_stk_top         ; - an 8086 masks interrupts for one
    sti                             ; instruction after a `mov ss`, which is
                                    ; exactly this pair and is why the `cli`
                                    ; is belt and braces rather than the rule
    call dos_pkt_poll
    cli
    mov ss, [dos_pkt_sss]
    mov sp, [dos_pkt_ssp]
    sti
.out:
    pop ds
    pop ax
    iret

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
; A DRIVE LETTER IS TAKEN OFF THE NAME AND OBEYED (SPEC.md 96.6.2), not
; thrown away: it goes in [dos_fdrv] and dos_fh_enter below stands on that
; volume for the length of the call.  A SUBDIRECTORY is refused with "path not
; found" rather than silently opened in the current one, which would hand the
; program the wrong file under the right name.
;
; IT USED TO BE DROPPED, on the reasoning that "a program that names its own
; drive is naming ours" - which was true of a box that had one volume and
; stopped being true the day AH=0Eh really switched (SPEC.md 96.6.1).  What it
; cost is in tests/dostrap/drvname.asm: standing on B:, this box answered
; A:*.* with B:'s own directory and answered C:*.* on a machine that HAS no
; C:, both of them reporting success.
; -----------------------------------------------------------------------------
dos_fh_name:
    push di
    push ax                         ; ...AND PUT AX BACK BEFORE THE CALL: this
    mov ax, [bp]                    ; routine's own answer on CF=1 is AL, so the
    mov [dos_fnseg], ax             ; segment travels in a word rather than in
    pop ax                          ; the register that carries the error code
    mov di, dos_fname
    call dos_fh_core
    jc .nout
%ifdef DOSTRACE
    call dos_tr_name_in             ; WHICH FILE - AH/AL alone cannot say, and
%endif                              ; that is the question a field trace asks
    call dos_fh_enter               ; ...and WHICH DRIVE, which is the same
    jc .nout                        ; question one level up (SPEC.md 96.6.2)
    clc
.nout:
    pop di
    ret

; -----------------------------------------------------------------------------
; dos_fh_core - the parse itself, from ANY segment into ANY buffer of ours
; in:  [dos_fnseg]:DX = the ASCIZ name, DI = a 13-byte buffer in OUR segment
; out: CF=0 with the name copied, [dos_fdrv] the drive it named (0xFF = none)
;      and [dos_fabs] whether it carried a leading separator; CF=1 with AL = a
;      DOS error code for a path this wave cannot walk
; clobbers: AL
;
; IT IS SEPARATE FROM dos_fh_name BECAUSE THERE ARE THREE CALLERS AND ONLY ONE
; OF THEM IS AN INT 21h ARGUMENT. AH=56h's second name is in the program's ES
; rather than its DS, and the built-in commands (SPEC.md 22.24) parse names
; out of OUR OWN segment - so the source is a far pointer and the destination
; is a parameter, and dos_fh_name is what adds the trace hook and the drive
; bracket on top for the calls that want them.
; -----------------------------------------------------------------------------
dos_fh_core:
    push bx
    push cx
    push si
    push di
    push es
    push ds
    pop es
    mov si, dx
    mov ds, [es:dos_fnseg]          ; ...wherever the name really is
    mov cx, 13

    mov byte [es:dos_fdrv], 0xFF    ; "C:NAME" - the letter comes off the name
    cmp byte [si+1], ':'            ; and goes in [dos_fdrv], where dos_fh_enter
    jne .nodrv                      ; picks it up. A LETTER IS NOT CHECKED HERE:
    mov al, [si]                    ; anything that is not a volume falls out of
    add si, 2                       ; range and dos_fh_enter refuses it with the
    cmp al, 'a'                     ; code a real DOS gives, which is 3 and not
    jb .drvup                       ; 15 (measured - drvname.asm under IBM DOS
    cmp al, 'z'                     ; 3.30)
    ja .drvup
    sub al, 32
.drvup:
    sub al, 'A'
    mov [es:dos_fdrv], al
.nodrv:
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
    clc
.out:
    pop es
    pop di
    pop si
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dos_fh_enter - stand on the volume [dos_fdrv] named, for one call
; out: CF=0, having moved or not; CF=1 with AL = 3 for a drive that is not
;      there. [dos_fhome] is where to go back to, 0xFF when we never left
; clobbers: AL, which dos_fh_name has already spent on the name it copied
;
; UNDER DOS A DRIVE LETTER IN A NAME DOES NOT CHANGE THE DEFAULT DRIVE - it
; selects which drive's current directory the name is resolved against, and
; AH=0Eh alone moves the program.  Our back end resolves against whatever is
; MOUNTED, so "resolve elsewhere" has to be spelled "go there and come back":
; the bracket IS the implementation and not a shortcut, which is why the
; restore is at the two exits every handler already funnels through and not at
; ten call sites.
;
; THE CODE FOR A DRIVE THAT IS NOT THERE IS 3 AND NOT 15, which is measured
; rather than reasoned: IBM DOS 3.30 answers AH=4Eh on C: with AX=0003 CF=1 on
; a machine with no hard disk (tests/dostrap/drvname.asm).  15 is what a
; program gets from calls that take a drive NUMBER, and this is not one.
; -----------------------------------------------------------------------------
dos_fh_enter:
    push dx
    mov byte [dos_fhome], 0xFF
    mov dl, [dos_fdrv]
    cmp dl, 0xFF
    je .none                        ; no letter: resolve where we stand, which
                                    ; is the common case and costs one compare
    cmp dl, [dos_vol]
    je .none                        ; named the drive we are already on
    cmp dl, DVOL_MAX
    jae .bad                        ; past the array - and a non-letter lands
                                    ; here too, 'C'-'A' being the only shape
                                    ; that does not
    mov al, [dos_vol]
    mov [dos_fhome], al
    call dos_drv_sel
    mov al, [dos_fdrv]
    cmp al, [dos_vol]
    jne .back                       ; dos_drv_sel leaves us put when the volume
                                    ; is not there, and that is the whole of
                                    ; "invalid drive" (SPEC.md 96.6.1)
.none:
    pop dx
    clc
    ret
.back:
    mov byte [dos_fhome], 0xFF      ; we did not move, so there is nothing to
.bad:                               ; put back - and a stale [dos_fhome] would
    mov al, 3                       ; move us on the way out
    pop dx
    stc
    ret

; -----------------------------------------------------------------------------
; dos_vol_to - stand on volume AL
; in:  AL = the volume, 0 = A
; out: CF=0 with AL = the volume we WERE on, for the caller to hand back;
;      CF=1, AL untouched, if that volume is not there
; clobbers: nothing else
;
; dos_fh_enter is this with [dos_fdrv]'s policy on top and one place to come
; back to.  The window routines want the bare mechanism instead: they bracket
; a single back-end call, they are reached with no name in hand, and their
; volume is the HANDLE's rather than the call's.
; -----------------------------------------------------------------------------
dos_vol_to:
    push dx
    mov dl, al
    mov al, [dos_vol]
    cmp dl, al
    je .same                        ; already there: the common case, and it
    push ax                         ; costs one compare
    call dos_drv_sel
    pop ax
    cmp dl, [dos_vol]
    jne .no
.same:
    pop dx
    clc
    ret
.no:
    pop dx
    stc
    ret

; -----------------------------------------------------------------------------
; dos_fh_leave - back to the drive dos_fh_enter left, if it left one
; clobbers: nothing, flags included
;
; IT IS AT .fhok AND .fherr, the two exits every file handler funnels through,
; so a handler that grows a new error path cannot forget it.
; -----------------------------------------------------------------------------
dos_fh_leave:
    push ax
    pushf
    mov al, [dos_fhome]
    cmp al, 0xFF
    je .out
    push dx
    mov dl, al
    mov byte [dos_fhome], 0xFF
    call dos_drv_sel
    pop dx
.out:
    popf
    pop ax
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
    mov al, [si+FH_VOL]             ; THE BYTES GO WHERE THE FILE IS, not where
    call dos_vol_to                 ; the program is standing: a copy off B:
    jc .err                         ; onto C: writes with B: current every
    mov [dos_wvsv], al              ; other window (SPEC.md 96.6.2)
    mov al, [si+FH_FLAGS]
    add si, FH_NAME
    mov bx, [dos_wseg]
    mov es, bx
    xor bx, bx
    test al, FHF_MADE
    jnz .append
    xor dx, dx
    call dos_be_write
    jc .errv
    sub si, FH_NAME
    or byte [si+FH_FLAGS], FHF_MADE
    jmp short .home
.append:
    call dos_be_append
    jc .errv
.home:
    mov al, [dos_wvsv]              ; ...and back, before anything else can
    call dos_vol_to                 ; run: it worked a moment ago, so a
.clean:                             ; refusal here is not a case
    mov byte [dos_wdirty], 0
    mov word [dos_wlen], 0
.ok:
    clc
    jmp short .out
.errv:
    mov al, [dos_wvsv]              ; a failed write still comes home, or the
    call dos_vol_to                 ; program is left standing somewhere it
.err:                               ; never asked to be
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
    mov al, [si+FH_VOL]             ; THE VOLUME FIRST, because AX becomes the
    mov [dos_fvvol], al             ; file OFFSET four lines down and AL is its
                                    ; low byte. Reading it later cost a whole
                                    ; round: FH_VOL is 0 for A:, so the arm
                                    ; under test read correctly and every
                                    ; ordinary read on B: came back EMPTY
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
    mov bx, [dos_wseg]              ; THE BYTES COME FROM WHERE THE FILE IS,
    mov es, bx                      ; not from where the program is standing
    xor bx, bx                      ; (SPEC.md 96.6.2)
    mov cx, [dos_wbytes]
    add si, FH_NAME
    mov word [dos_fvtgt], dos_k_rdat
    call .onvol                     ; out DX:AX = the bytes delivered, 0 at or
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
    mov word [dos_fvtgt], dos_k_read ; EXPANDS on the way in (SPEC.md 20.14),
    call .onvol                      ; which is the whole reason this arm exists
    pop si
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

; --- .onvol - dos_be_go, standing where the WINDOW OWNER's file is ----------
; [dos_fvtgt] is the back end's target and [dos_fvvol] is the volume.  It is
; one routine rather than two brackets because dos_be_rdat and dos_be_read
; differ in that word alone, and a bracket written twice is one that gets
; fixed once.
;
; THE TARGET IS COPIED IN AFTER THE SWITCH AND NOT BEFORE, which is the whole
; reason it travels in a word of its own: dos_drv_sel mounts through
; dos_be_goto, and dos_be_goto's first act is to write [dos_betgt]. Setting
; the target first and then switching ran every cross-volume READ as a
; DIRECTORY GOTO - which returns, so the caller read a byte count out of
; whatever it left in DX:AX and called the file empty.
.onvol:
    push ax
    push dx
    mov al, [dos_fvvol]
    call dos_vol_to
    jc .onbad
    mov [dos_fvsv], al
    pop dx
    pop ax
    push ax                         ; ...and only now, with every mount the
    mov ax, [dos_fvtgt]             ; switch needed already made. BP IS NOT A
    mov [dos_betgt], ax             ; SCRATCH REGISTER HERE - it is the INT 21h
    pop ax                          ; frame, and [bp] is the program's own DS
    call dos_be_go
    pushf                           ; the back end's answer is DX:AX and CF,
    push ax                         ; and the walk home must not spend any of
    push dx                         ; them
    mov al, [dos_fvsv]
    call dos_vol_to
    pop dx
    pop ax
    popf
    ret
.onbad:
    pop dx                          ; THE VOLUME IS GONE - the floppy came out
    pop ax                          ; between the open and the read.  The
    stc                             ; caller reads this as end of file, which
    ret                             ; is the honest half of it: no bytes, and
                                    ; no lie about which ones

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
    DBSS DOS_B_PFBUF, DOS_PFIN + 1  ; AH=29h's copy of the program's name...
    DBSS DOS_B_PFCB,  12            ; ...and the twelve bytes it hands back
    DBSS DOS_B_FNAME2, 16      ; AH=56h's SECOND name (SPEC.md 96.31)
    DBSS DOS_B_RNVOL,  1       ; ...the volume it was ASKED on, which is what
    DBSS DOS_B_RNDRV,  1       ; an unqualified name means; the old name's
    DBSS DOS_B_RNABS,  1       ; drive; and whether it carried a separator
    DBSS DOS_B_RNPAD,  1
    DBSS DOS_B_FNSEG, 2        ; the segment dos_fh_core reads a name FROM
    DBSS DOS_B_FDRV,  1        ; ...and the DRIVE it named, 0xFF = none
    DBSS DOS_B_FHOME, 1        ; where to go back to, 0xFF = we never left
    DBSS DOS_B_FVTGT, 2        ; the back end call a bracketed read makes
    DBSS DOS_B_FVVOL, 1        ; the window owner's volume, and where the read
    DBSS DOS_B_FVSV,  1        ; came from; the FLUSH has a byte of its own
    DBSS DOS_B_WVSV,  1        ; because it runs INSIDE a fill, through
    DBSS DOS_B_WVPAD, 1        ; dos_fh_take, and must not spend the fill's
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
; --- THE PACKET DRIVER (SPEC.md 96.23) ---------------------------------------
; None of this is resident: a package's bss is zeroed into its heap claim at
; launch and goes back when the window closes, so what it costs is a DOS
; session's memory and not a machine's.
    DBSS DOS_B_PKTVEC,  1           ; the vector we took, 0 = none
    DBSS DOS_B_PKTRAW,  1           ; 1 = we hold NETV_RAW
    DBSS DOS_B_PKTBSY,  1           ; the poll's re-entrancy guard
    DBSS DOS_B_PKTMODE, 1           ; what set_rcv_mode was told
    DBSS DOS_B_PKTHTAB, PKT_NHAND * PKT_HSIZE
    DBSS DOS_B_PKTMAC,  6           ; the station address, banked by the claim
    DBSS DOS_B_PKTCVEC, 4           ; the client receiver being called
    DBSS DOS_B_PKTCHAND, 2          ; ...and the handle both calls carry
    DBSS DOS_B_PKTOLD08, 4          ; the tick we chain
    DBSS DOS_B_PKTSSS,  2           ; the program's stack, banked across a poll
    DBSS DOS_B_PKTSSP,  2
    DBSS DOS_B_PKTCAN,  2           ; **A CANARY UNDER THE PRIVATE STACK**, and
                                    ; it is here because the alternative was a
                                    ; HANG: the two words above are what the
                                    ; program's SS:SP is banked in, they sit
                                    ; directly below the stack, and an overflow
                                    ; writes a bogus stack back and takes the
                                    ; machine with it. The translation made the
                                    ; chain under this poll much deeper than
                                    ; §96.23.4.1 sized it for
    DBSS DOS_B_PKTCDS,  2           ; the CLIENT's DS, captured at the gate
                                    ; (SPEC.md 96.23.9) - NOT read back out of
                                    ; the stack frame, which is what the first
                                    ; version did and got wrong
    DBSS DOS_B_PKTBSEG, 2           ; **THE FRAME BUFFER IS A HEAP CLAIM**
                                    ; (SPEC.md 96.23.7) and this is its segment,
                                    ; 0 = none. They were 3,028 bytes of bss,
                                    ; which every DOS window paid for on every
                                    ; machine - including every machine with no
                                    ; card in it
    DBSS DOS_B_PKTSTAT, 24          ; six dwords, get_statistics' own order
; --- AND NOTHING FOR THE WIRE ITSELF (SPEC.md 96.23.7) -----------------------
; Every frame, the staging copy, the poll's private stack and the whole of the
; cable translation's state are in the NETWORK CLAIM - see PKB_* above. They
; were 4,052 bytes of this table, which every DOS window paid for on every
; machine, including the 128KB one that ships no network driver at all.
    DBSS DOS_B_PKTXL,   1           ; **WHICH PATH, and it is NOT the same
                                    ; question as which CLASS** (SPEC.md
                                    ; 96.26.1): the translation calls sockets
                                    ; on whatever [net_cls] says, so forcing
                                    ; the path on a card machine - which is
                                    ; how it is tested at all - must not
                                    ; forge the class underneath it
; --- the built-in commands' own state (SPEC.md 96.30, apps/dos/dosh.inc) -----
    DBSS DOS_B_SHLINE,  DSH_LINE    ; the command tail, unpacked
    DBSS DOS_B_SHVERB,  DSH_ARG     ; the verb, upper-cased
    DBSS DOS_B_SHA1,    DSH_ARG     ; ...and its two arguments
    DBSS DOS_B_SHA2,    DSH_ARG
    DBSS DOS_B_SHSPEC,  DSH_ARG     ; one of them, being taken apart
    DBSS DOS_B_SHLEAF,  DSH_ARG     ; ...into a folder and this
    DBSS DOS_B_SHDNAM,  DSH_ARG     ; the destination's name, empty = keep
    DBSS DOS_B_SHRTGT,  DSH_ARG     ; what a `>` named
    DBSS DOS_B_SHPAT,   DSH_PAT     ; the pattern, padded to eleven...
    DBSS DOS_B_SHNM11,  DSH_PAT     ; ...and the candidate, the same way
    DBSS DOS_B_SHFNAM,  16          ; the match's own name
    DBSS DOS_B_SHFND,   OSAPI_FIND_SZ
    DBSS DOS_B_SHBUF,   DSH_BUF     ; TYPE's chunk
    DBSS DOS_B_SHNUM,   6           ; a count, as digits
    DBSS DOS_B_SHQUIET, 1           ; the line was redirected
    DBSS DOS_B_SHASDIR, 1           ; try the whole spec as a folder
    DBSS DOS_B_SHDEL,   1           ; ...and delete the source after
    DBSS DOS_B_SHDIROP, 1           ; 0 MD, 1 RD, 2 CD
    DBSS DOS_B_SHSKIP,  2           ; matches to pass over
    DBSS DOS_B_SHN,     2           ; ...and how many were done
    DBSS DOS_B_SHOFF,   4           ; TYPE's offset, 32 bits
    DBSS DOS_B_SHBVOL,  1           ; where we were standing before a verb
    DBSS DOS_B_SHBCLUS, 2
    DBSS DOS_B_SHRDRV,  1           ; what dsh_resolve answered
    DBSS DOS_B_SHRCLUS, 2
    DBSS DOS_B_SHSDRV,  1           ; the source place...
    DBSS DOS_B_SHSCLUS, 2
    DBSS DOS_B_SHDDRV,  1           ; ...and the destination's
    DBSS DOS_B_SHDCLUS, 2
    DBSS DOS_B_SHCNAME, DSH_ARG     ; the name this file is written under
    DBSS DOS_B_SHCPSEG, 2           ; the copy buffer's DOS block...
    DBSS DOS_B_SHCPKB,  2           ; ...and how many KB it turned out to be
    DBSS DOS_B_SHMADE,  1           ; the destination has been created
    DBSS DOS_B_SHGOT,   2           ; bytes in the buffer this pass
    DBSS DOS_B_SHWHY,   1           ; DSHW_*: WHICH refusal, for a debugger

DOS_BSS_SIZE equ DB

%include "dosh.inc"                 ; THE BUILT-IN COMMANDS (SPEC.md 96.30) -
                                    ; a COMMAND.COM that is not a file, over
                                    ; the back end like every other file verb

; os88ui.inc first (os88line.inc needs its UI_* macros), and both LAST -
; the header and the icon block are at fixed offsets in the image (SPEC.md
; 20.2), so code emitted between them fails the icon macro's own assertion.
%define OS88UI_CHK                  ; SPEC.md 13.15: the memory page's one
                                    ; choice. Opted into here because os88ui's
                                    ; rule is that a package that does not use
                                    ; a control pays NOTHING for it
%include "os88ui.inc"
%include "os88line.inc"
%include "dosnet.inc"               ; THE CABLE TRANSLATION (SPEC.md 96.26) -
                                    ; only reached when the route is the cable
%include "os88sock.inc"             ; net_try - WHICH driver answers (SPEC.md
                                    ; 20.11.1). The packet driver wants the
                                    ; CARD and not the cable, so it asks
                                    ; DRVC_NET by name rather than calling
                                    ; net_find, whose job is to prefer one of
                                    ; two and whose second answer refuses
                                    ; every verb this feature is made of

%if DOS_MCHKSZ != OS88UI_CK_SIZE
 %error "DOS_MCHKSZ must equal os88ui.inc's OS88UI_CK_SIZE - the bss table \
above reserves DOS_MCHKSZ bytes for a record this file does not own"
%endif
%if DOS_MCHKON != OS88UI_CK_ON
 %error "DOS_MCHKON must equal os88ui.inc's OS88UI_CK_ON - [dos_keepc] IS \
that byte of the record, and a wrong offset writes the label pointer"
%endif

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
dos_vsbuf   equ os88_image_end + DOS_B_VSBUF   ; OSAPI_VOL_STAT's record
dos_memkb   equ os88_image_end + DOS_B_MEMKB   ; word: the arena cap, 0 = all
dos_mchk    equ os88_image_end + DOS_B_MCHK    ; the check box's record
dos_keepc   equ dos_mchk + DOS_MCHKON          ; byte: 1 = keep the disk cache
dos_mbuf    equ os88_image_end + DOS_B_MBUF    ; the limit field's text
dos_mln     equ os88_image_end + DOS_B_MLN     ; ...and its os88line block
dos_mx      equ os88_image_end + DOS_B_MX      ; word: this paint's content x
dos_my      equ os88_image_end + DOS_B_MY      ; word: ...and its top
dos_pic1    equ os88_image_end + DOS_B_PIC1    ; byte: the 8259 masks as found
dos_pic2    equ os88_image_end + DOS_B_PIC2    ; byte:
dos_isexe   equ os88_image_end + DOS_B_ISEXE   ; byte: 1 = an .EXE was set up
%ifdef DOSTRACE
dos_tracen  equ os88_image_end + DOS_B_TRACEN  ; word: DOSTRACE's call counter
dos_tracew  equ os88_image_end + DOS_B_TRACEW  ; word: its ring write index
dos_traceb  equ DOS_TRB_OFF         ; **AN OFFSET IN THE PART, NOT IN US**
                                    ; (SPEC.md 96.29.1), so every reference to
                                    ; it carries an `es:` and ES is
                                    ; [dos_trseg]. An unprefixed one reads our
                                    ; own image at that offset, which
                                    ; assembles cleanly and traces nonsense
dos_tracei  equ os88_image_end + DOS_B_TRACEI  ; ...the live entry's offset
dos_trnm    equ os88_image_end + DOS_B_TRNM   ; the names passed in
dos_trnmi   equ os88_image_end + DOS_B_TRNMI  ; ...how many so far
dos_trdump  equ DOS_TRD_OFF         ; ...rendered, for the file - and in the
                                    ; part beside the ring. OSAPI_FILE_WRITE
                                    ; takes ES:BX, so handing it over costs
                                    ; nothing at all
dos_trseg   equ os88_image_end + DOS_B_TRSEG
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
dsh_line    equ os88_image_end + DOS_B_SHLINE
dsh_verb    equ os88_image_end + DOS_B_SHVERB
dsh_a1      equ os88_image_end + DOS_B_SHA1
dsh_a2      equ os88_image_end + DOS_B_SHA2
dsh_spec    equ os88_image_end + DOS_B_SHSPEC
dsh_leaf    equ os88_image_end + DOS_B_SHLEAF
dsh_dname   equ os88_image_end + DOS_B_SHDNAM
dsh_rtgt    equ os88_image_end + DOS_B_SHRTGT
dsh_pat     equ os88_image_end + DOS_B_SHPAT
dsh_nm11    equ os88_image_end + DOS_B_SHNM11
dsh_fname   equ os88_image_end + DOS_B_SHFNAM
dsh_fnd     equ os88_image_end + DOS_B_SHFND
dsh_buf     equ os88_image_end + DOS_B_SHBUF
dsh_num     equ os88_image_end + DOS_B_SHNUM
dsh_quiet   equ os88_image_end + DOS_B_SHQUIET
dsh_asdir   equ os88_image_end + DOS_B_SHASDIR
dsh_del     equ os88_image_end + DOS_B_SHDEL
dsh_dirop   equ os88_image_end + DOS_B_SHDIROP
dsh_skip    equ os88_image_end + DOS_B_SHSKIP
dsh_n       equ os88_image_end + DOS_B_SHN
dsh_off     equ os88_image_end + DOS_B_SHOFF
dsh_bvol    equ os88_image_end + DOS_B_SHBVOL
dsh_bclus   equ os88_image_end + DOS_B_SHBCLUS
dsh_rdrv    equ os88_image_end + DOS_B_SHRDRV
dsh_rclus   equ os88_image_end + DOS_B_SHRCLUS
dsh_sdrv    equ os88_image_end + DOS_B_SHSDRV
dsh_sclus   equ os88_image_end + DOS_B_SHSCLUS
dsh_ddrv    equ os88_image_end + DOS_B_SHDDRV
dsh_dclus   equ os88_image_end + DOS_B_SHDCLUS
dsh_cname   equ os88_image_end + DOS_B_SHCNAME
dsh_cpseg   equ os88_image_end + DOS_B_SHCPSEG
dsh_cpkb    equ os88_image_end + DOS_B_SHCPKB
dsh_made    equ os88_image_end + DOS_B_SHMADE
dsh_got     equ os88_image_end + DOS_B_SHGOT
dsh_why     equ os88_image_end + DOS_B_SHWHY
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
dos_pfbuf   equ os88_image_end + DOS_B_PFBUF   ; AH=29h's name scratch...
dos_pfcb    equ os88_image_end + DOS_B_PFCB    ; ...and its FCB prefix
dos_fname2  equ os88_image_end + DOS_B_FNAME2  ; AH=56h's second name
dos_rnvol   equ os88_image_end + DOS_B_RNVOL   ; ...and its three bytes of
dos_rndrv   equ os88_image_end + DOS_B_RNDRV   ; drive arithmetic
dos_rnabs   equ os88_image_end + DOS_B_RNABS
dos_fnseg   equ os88_image_end + DOS_B_FNSEG   ; word: where a name is read from
dos_fdrv    equ os88_image_end + DOS_B_FDRV    ; byte: the drive a name named
dos_fhome   equ os88_image_end + DOS_B_FHOME   ; byte: ...and where it left
dos_fvtgt   equ os88_image_end + DOS_B_FVTGT   ; word: the read's back end
dos_fvvol   equ os88_image_end + DOS_B_FVVOL   ; byte: the fill's volume...
dos_fvsv    equ os88_image_end + DOS_B_FVSV    ; byte: ...and where it came from
dos_wvsv    equ os88_image_end + DOS_B_WVSV    ; byte: the flush's own
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

; --- the packet driver's (SPEC.md 96.23) -------------------------------------
dos_pkt_vec   equ os88_image_end + DOS_B_PKTVEC
dos_pkt_raw   equ os88_image_end + DOS_B_PKTRAW
dos_pkt_busy  equ os88_image_end + DOS_B_PKTBSY
dos_pkt_mode  equ os88_image_end + DOS_B_PKTMODE
dos_pkt_htab  equ os88_image_end + DOS_B_PKTHTAB
dos_pkt_mac   equ os88_image_end + DOS_B_PKTMAC
dos_pkt_cvec  equ os88_image_end + DOS_B_PKTCVEC
dos_pkt_chand equ os88_image_end + DOS_B_PKTCHAND
dos_pkt_old08 equ os88_image_end + DOS_B_PKTOLD08
dos_pkt_sss   equ os88_image_end + DOS_B_PKTSSS
dos_pkt_ssp   equ os88_image_end + DOS_B_PKTSSP
dos_pkt_can   equ os88_image_end + DOS_B_PKTCAN
dos_pkt_cds   equ os88_image_end + DOS_B_PKTCDS
dos_pkt_bseg  equ os88_image_end + DOS_B_PKTBSEG
dos_pkt_stats equ os88_image_end + DOS_B_PKTSTAT

dos_pkt_xl  equ os88_image_end + DOS_B_PKTXL

; --- the cable translation's, IN THE NETWORK CLAIM (SPEC.md 96.26.6) --------
; These are offsets into [dos_pkt_bseg] and NOT into our own segment, which is
; the whole of what made the move cheap: dosnet.inc already addressed all of
; them DS-relative with no override, so pointing DS at the claim leaves its
; seventy-eight frame references untouched and only these fourteen lines move.
dn_flows    equ PKB_STATE + DNB_FLOWS
dn_names    equ PKB_STATE + DNB_NAMES
dn_qname    equ PKB_STATE + DNB_QNAME
dn_pend     equ PKB_STATE + DNB_PEND
dn_lastip   equ PKB_STATE + DNB_LASTIP
dn_pseudo   equ PKB_STATE + DNB_PSEUDO
dn_rr       equ PKB_STATE + DNB_RR
dn_gwmac    equ PKB_STATE + DNB_GWMAC       ; copied out of the image by
dn_ourmac   equ PKB_STATE + DNB_OURMAC      ; dn_init (dn_mac_c below)
dn_lsn      equ PKB_STATE + DNB_LSN         ; the inbound listeners (96.26.8)
dn_lrr      equ PKB_STATE + DNB_LRR
dn_cip      equ PKB_STATE + DNB_CIP         ; ...and the client's own address
dn_frame    equ PKB_RX                      ; the frame we build FOR the
                                            ; client, which is also...
dos_pkt_rxs equ PKB_RX                      ; ...the one dos_pkt_deliver hands
                                            ; over, on EITHER route: the card
                                            ; writes the same offset through
                                            ; NETV_RAWRX, which is why both
                                            ; of that routine's arms collapsed
dos_pkt_txs equ PKB_TX                      ; and the client's own, staged
dos_pkt_stk_top equ PKB_STKTOP
