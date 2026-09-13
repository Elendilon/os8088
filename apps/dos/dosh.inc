; =============================================================================
; apps/dos/dosh.inc - THE BUILT-IN COMMANDS (SPEC.md 96.30)
; =============================================================================
; A `COMMAND.COM` that is not a file. `AH=4Bh` of a program whose name is
; COMMAND.COM does not load anything: it reads the command tail, runs one
; command out of the table below, and hands back an exit code. Nothing is
; spawned, no arena block is taken, and the caller cannot tell the difference
; from the outside - which is the whole point, because Microsoft C's system()
; is `COMSPEC` + `/c` + a string and thousands of DOS programs shell out that
; way for exactly the four or five verbs in here.
;
; MEASURED, NOT GUESSED. Prince of Persia's INSTALL.EXE carries `copy `,
; `*.* `, ` > NUL`, `del install.exe > NUL`, `/c`, `COMSPEC` and `command.com`
; in its data segment (docs/plans/DOS-EXEC-PLAN.md 15.10), so the two commands
; that had to work were fixed before a line of this was written, and the
; wildcard source and the `> NUL` are requirements rather than garnish.
;
; IT IS THE SAME INTERPRETER WAVE 7 WANTS. A prompt in a window differs from
; this in its INPUT (a typed line rather than a command tail) and its OUTPUT
; (a text pane rather than the ROM teletype), and in nothing else - so the
; parser and every verb below are built here, fullscreen, where a real program
; is the test.
;
; NO OSAPI_* FILE SLOT IS CALLED FROM THIS FILE. The back end's rule (96.4)
; is not relaxed for the shell: every file action goes through a `dos_be_*`,
; which is what keeps 14's hibernate phase a second back end rather than a
; rewrite.
; -----------------------------------------------------------------------------

; DSH_LINE, DSH_ARG, DSH_PAT and DSH_BUF are in dos.asm's constants block,
; EARLY, because the DBSS table sizes this file's buffers and `%assign` cannot
; forward-reference. dosnetabi.inc is in the tree for the same reason.

; -----------------------------------------------------------------------------
; dsh_tail - AH=4Bh of COMMAND.COM: run the command in the parameter block
; in:  ES:BX = the EXEC parameter block (SPEC.md 96.14)
; out: AL = the exit code, always CF=0 - the SHELL ran, whatever the command did
; clobbers: everything but the segment registers
;
; The tail at +2 is a FAR POINTER to a counted string: a length byte, the text,
; and a CR that is not counted. `/c` may be upper or lower case and may be
; followed by a space or not, and a tail with no `/c` at all is an interactive
; shell - which we cannot be, so it is refused rather than guessed at.
; -----------------------------------------------------------------------------
dsh_tail:
    push es
    mov ax, [es:bx+4]               ; the tail's far pointer, taken BEFORE ES
    mov dx, [es:bx+2]               ; moves off the parameter block
    mov es, ax
    mov si, dx
    mov cl, [es:si]                 ; the count byte
    xor ch, ch
    cmp cx, DSH_LINE - 1
    jbe .fits
    mov cx, DSH_LINE - 1            ; a tail longer than any DOS ever made;
.fits:                              ; truncate rather than refuse, because the
    inc si                          ; excess cannot be part of a command we run
    mov di, dsh_line
.cp:
    jcxz .cpend
    mov al, [es:si]
    cmp al, 13
    je .cpend                       ; the CR ends it wherever the count says
    mov [di], al
    inc si
    inc di
    dec cx
    jmp short .cp
.cpend:
    mov byte [di], 0
    pop es

    mov si, dsh_line
    call dsh_skipsp
    cmp byte [si], '/'
    jne .noc
    mov al, [si+1]
    or al, 0x20
    cmp al, 'c'
    jne .noc
    add si, 2
    call dsh_bank                   ; A CHILD SHELL'S DIRECTORY DIES WITH IT
    call dsh_run                    ; under DOS - `command /c cd \FOO` leaves
    push ax                         ; the caller exactly where it was - and
    call dsh_home                   ; running in-process is not a reason to
    pop ax                          ; behave differently. Wave 7's prompt calls
    ret                             ; dsh_run WITHOUT this bracket, which is
                                    ; the whole difference
.noc:
    mov al, 1                       ; no /C: an INTERACTIVE shell was asked
    ret                             ; for, and there is no window to put one
                                    ; in from inside a fullscreen bracket

; -----------------------------------------------------------------------------
; dsh_run - run ONE command line
; in:  SI = the line, ASCIZ, in our segment
; out: AL = the exit code (0 = it worked)
; clobbers: everything but the segment registers
; -----------------------------------------------------------------------------
dsh_run:
    mov byte [dsh_why], DSHW_NONE   ; ...and cleared per command, so a stale
    call dsh_redir                  ; one cannot be read as this one's
                                    ; `> NUL` off the end first, so the verb
    jc .badredir                    ; scan never sees it
    call dsh_skipsp
    mov di, dsh_verb
    call dsh_word
    cmp byte [dsh_verb], 0
    je .empty                       ; an empty command line is DOS's own no-op
    mov di, dsh_verb
    call dsh_upper

    ; --- A BARE `X:` IS A DRIVE CHANGE, and it is not a verb -----------------
    ; DOS answers it BEFORE the table, which is why `DIR` and `B:` feel like
    ; the same kind of thing and only one of them is. TWO characters exactly:
    ; `B:` changes drive and `B:FOO` does not - it names a file on B:, which
    ; dsh_word leaves in [dsh_verb] whole, so the length test IS the
    ; distinction and no lookahead is needed.
    ;
    ; From the PROMPT the change persists, because dos_con_run calls dsh_run
    ; with no dsh_bank/dsh_home bracket around it; from `command /c b:` it does
    ; not, because dsh_tail brackets it - and a child shell's drive dying with
    ; it is DOS's own behaviour (SPEC.md 96.30).
    cmp byte [dsh_verb+2], 0
    jne .notdrv
    cmp byte [dsh_verb+1], ':'
    jne .notdrv
    mov al, [dsh_verb]
    cmp al, 'A'
    jb .notdrv
    cmp al, 'Z'
    ja .notdrv
    sub al, 'A'                     ; SPEC.md 96.6's map is the identity
    call dos_vol_to                 ; ...and [dos_curdir] comes with it:
    jc .nodrive                     ; dos_drv_sel banks where we were and
    xor al, al                      ; RECALLS where that drive last stood
    ret                             ; (SPEC.md 96.6.2), so `B: / CD APPS / A: /
                                    ; B:` is back in B:\APPS and not at its root
.nodrive:
    mov si, dsh_s_nodrv
    call dsh_say
    mov byte [dsh_why], DSHW_NODRV
    mov al, 1
    ret
.notdrv:

    mov bx, dsh_tab
.look:
    mov al, [bx]
    or al, al
    jz .unknown
    push si
    mov si, bx
    inc si
    mov di, dsh_verb
    call dsh_same
    pop si
    jc .next
    mov ax, [bx+9]                  ; the handler: SI is the argument text
    jmp ax
.next:
    add bx, 11
    jmp short .look

.unknown:
    mov byte [dsh_why], DSHW_NOCMD  ; **THE MESSAGE IS THE CALLER'S NOW**
    cmp byte [dsh_exec], 0          ; (SPEC.md 96.33.3): from a `/c` shell an
    jne .noexec                     ; unknown verb is nothing else and this is
    mov si, dsh_s_bad               ; the answer, but from the PROMPT it may be
    call dsh_say                    ; a program - so the refusal is held back
    mov si, dsh_verb                ; and [dsh_why] says which arm ran
    call dsh_say
    mov si, dsh_s_crlf
    call dsh_say
.noexec:
    mov al, 1
    ret
.empty:
    xor al, al
    ret
.badredir:
    mov si, dsh_s_redir
    call dsh_say
    mov byte [dsh_why], DSHW_REDIR
    mov al, 1
    ret

; -----------------------------------------------------------------------------
; dsh_redir - cut a `>`, `>>` or `<` off the line and decide what it meant
; in:  SI = the line
; out: CF=0 and the line truncated at the operator; CF=1 = a target we cannot
;      honour, and the caller must refuse the whole command
; clobbers: AX, DI, flags
;
; NUL IS THE ONLY TARGET THAT WORKS, AND ANY OTHER IS REFUSED RATHER THAN
; IGNORED. Our verbs print almost nothing, so quietly dropping `> FILE` would
; be indistinguishable from honouring it right up until somebody read the file
; and found it missing - a wrong answer of SPEC.md 96.22's exact kind. A
; refusal with a non-zero exit code is a normal path (SPEC.md 47) and `> NUL`,
; which is what shelling-out code actually writes, costs nothing.
; -----------------------------------------------------------------------------
dsh_redir:
    push si
    push bx
    mov bx, si
.scan:
    mov al, [bx]
    or al, al
    jz .none
    cmp al, '>'
    je .cut
    cmp al, '<'
    je .cut
    inc bx
    jmp short .scan
.cut:
    mov byte [dsh_quiet], 1
    mov si, bx                      ; SI walks the target, BX marks the cut
    inc si
    cmp byte [si], '>'
    jne .tgt
    inc si                          ; `>>` is an append, same question
.tgt:
    call dsh_skipsp
    mov di, dsh_rtgt
    call dsh_word
    mov di, dsh_rtgt
    call dsh_upper
    mov byte [bx], 0                ; the command is what came before it
    mov si, dsh_rtgt
    mov di, dsh_s_nul
    call dsh_same
    jc .no
.none:
    pop bx
    pop si
    clc
    ret
.no:
    pop bx
    pop si
    stc
    ret

; --- the small string half ---------------------------------------------------
; dsh_skipsp - advance SI past spaces and tabs.  clobbers: SI, flags
dsh_skipsp:
    cmp byte [si], ' '
    je .step
    cmp byte [si], 9
    jne .done
.step:
    inc si
    jmp short dsh_skipsp
.done:
    ret

; dsh_word - one whitespace-delimited token from SI into DI (DSH_ARG bounded)
; out: SI past it, the token ASCIZ at DI.  clobbers: AX, CX, SI, DI, flags
dsh_word:
    push di
    mov cx, DSH_ARG - 1
.c:
    mov al, [si]
    or al, al
    jz .end
    cmp al, ' '
    je .end
    cmp al, 9
    je .end
    jcxz .skip                      ; past the buffer: consume the rest of the
    mov [di], al                    ; token but store none of it, so a long
    inc di                          ; argument truncates instead of running off
    dec cx                          ; into whatever follows
.skip:
    inc si
    jmp short .c
.end:
    mov byte [di], 0
    pop di
    ret

; dsh_upper - upper-case the ASCIZ string at DI in place.  clobbers: AL, flags
dsh_upper:
    push di
.c:
    mov al, [di]
    or al, al
    jz .done
    cmp al, 'a'
    jb .next
    cmp al, 'z'
    ja .next
    sub al, 0x20
    mov [di], al
.next:
    inc di
    jmp short .c
.done:
    pop di
    ret

; dsh_same - are the ASCIZ strings at SI and DI equal?
; out: CF=0 equal, CF=1 not.  clobbers: AX, flags (SI and DI preserved)
dsh_same:
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
    clc
    ret
.no:
    pop di
    pop si
    stc
    ret

; dsh_say - one ASCIZ string to the screen, unless the line was redirected
; in:  SI = the string.  clobbers: AX, SI, flags
;
; dos_tty is the ROM teletype, which is where a DOS program's own output goes
; inside this bracket - so a built-in's message lands in the same place, in the
; same colours, scrolling the same screen. That is the whole of "output" until
; wave 7 puts a pane behind it.
dsh_say:
    cmp byte [dsh_quiet], 0
    jne .out
.c:
    mov al, [si]
    or al, al
    jz .out
    call dos_tty
    inc si
    jmp short .c
.out:
    ret

; --- names and patterns ------------------------------------------------------
; dsh_to11 - an 8.3 ASCIZ name into the 11-byte padded form a match is decided
;            in, expanding `*` to `?` for the rest of its field
; in:  SI = the name, DI = an 11-byte buffer.  clobbers: AX, CX, SI, DI, flags
;
; DOS's own rule, and the reason a match is done this way round rather than by
; walking the two strings together: `?` matches a character OR the end of the
; name, which in the padded form is just "? matches a space" and needs no
; special case at all.
dsh_to11:
    push di
    mov cx, 8
    call .field                     ; the name...
    mov al, [si]
    cmp al, '.'
    jne .noext
    inc si
.noext:
    mov cx, 3                       ; ...and the extension
    call .field
    pop di
    ret
.field:
    mov al, [si]
    or al, al
    jz .pad
    cmp al, '.'
    je .pad
    cmp al, '*'
    jne .one
    inc si                          ; `*` fills what is left of THIS field with
.star:                              ; `?` and is not itself stored
    mov byte [di], '?'
    inc di
    loop .star
    jmp short .eat
.one:
    cmp al, 'a'
    jb .store
    cmp al, 'z'
    ja .store
    sub al, 0x20
.store:
    mov [di], al
    inc di
    inc si
    loop .field
.eat:
    mov al, [si]                    ; anything past the field's width is
    or al, al                       ; dropped, which is what DOS does to a
    jz .fdone                       ; ninth character
    cmp al, '.'
    je .fdone
    inc si
    jmp short .eat
.pad:
    mov byte [di], ' '
    inc di
    loop .pad
.fdone:
    ret

; dsh_match - does the padded name at SI match the padded pattern at DI?
; out: CF=0 it matches, CF=1 it does not.  clobbers: AX, CX, flags
dsh_match:
    push si
    push di
    mov cx, DSH_PAT
.c:
    mov al, [di]
    cmp al, '?'
    je .next
    cmp al, [si]
    jne .no
.next:
    inc si
    inc di
    loop .c
    pop di
    pop si
    clc
    ret
.no:
    pop di
    pop si
    stc
    ret

; --- where a name lives ------------------------------------------------------
; dsh_bank / dsh_home - the place we are standing, banked and put back
; clobbers: AX (bank), AX/BX/DX (home)
dsh_bank:
    mov al, [dos_vol]
    mov [dsh_bvol], al
    mov ax, [dos_curdir]
    mov [dsh_bclus], ax
    ret

dsh_home:
    push ax
    mov al, [dsh_bvol]
    call dos_vol_to                 ; the DRIVE first, because that is what
    mov dx, [dsh_bclus]             ; banks and recalls a per-drive directory
    mov bl, [dsh_bvol]              ; (dos_drv_bank) - going straight to the
    call dos_be_goto                ; cluster would leave that pair disagreeing
    mov [dos_curdir], dx
    pop ax
    ret

; dsh_cdto - stand in the folder the spec at SI names
; in:  SI = an ASCIZ spec in our segment
; out: CF=0 and we are standing there; CF=1 = there is no such folder, and
;      where we stand is then whatever the attempt left (the caller banks)
; clobbers: AX, BX, CX, DX, DI, flags
;
; ONE COMPONENT PAST THE ROOT, which is dos_fh_core's own limit (a separator
; anywhere past a leading one is "path not found", code 3) and not a new one
; invented here. `C:\PRINCE` resolves and `C:\A\B` does not - and that is
; exactly the reach INSTALL.EXE asks for. dos_walk_pbuf is the upgrade when
; something wants deeper, and it is isolated to this routine.
dsh_cdto:
    mov dx, si
    mov ax, ds
    mov [dos_fnseg], ax
    mov di, dos_fname
    call dos_fh_core                ; -> dos_fname, [dos_fdrv], [dos_fabs]
    jc .no
    mov al, [dos_fdrv]
    cmp al, 0xFF
    je .nodrv                       ; no letter: wherever we already are
    call dos_vol_to
    jc .no
.nodrv:
    call dos_cd_go
    jc .no
    clc
    ret
.no:
    stc
    ret

; dsh_resolve - a spec into a PLACE and a LEAF
; in:  SI = the spec, AL = 1 to try the whole spec as a folder first
; out: CF=0 with [dsh_rdrv]/[dsh_rclus] the folder and dsh_leaf the last
;      component - EMPTY when the whole spec was itself a folder; CF=1 = no
;      such folder
; clobbers: AX, BX, CX, DX, SI, DI, flags
;
; AL=1 IS HOW `copy *.* C:\PRINCE` KNOWS WHAT PRINCE IS. DOS decides a
; destination by looking: if it exists and is a directory the files keep their
; own names, and otherwise the last component is the name to write. That is a
; question about the disk rather than about the string, so it is asked of the
; disk - and asked FIRST, because `PRINCE` is a perfectly good filename too.
dsh_resolve:
    mov [dsh_asdir], al
    mov di, dsh_spec
    call dsh_cpspec
    mov byte [dsh_leaf], 0

    cmp byte [dsh_asdir], 0
    je .split
    call dsh_bank
    mov si, dsh_spec
    call dsh_cdto
    pushf                           ; ...AND THE popf GOES AFTER dsh_home, not
    call .record                    ; before it: dsh_home ends in dos_be_goto,
    call dsh_home                   ; whose CF=0 would otherwise become the
    popf                            ; answer to "was that a folder" - so every
    jnc .ok                         ; destination looked like one and every
                                    ; copy read as a copy onto itself

.split:
    mov si, dsh_spec
    xor bx, bx                      ; BX = the spec's length
.scan:
    cmp byte [si+bx], 0
    je .findsep
    inc bx
    jmp short .scan
.findsep:
    mov si, dsh_spec                ; ...then walk BACK for a separator. SI and
    add si, bx                      ; not CX: on an 8086 only BX, BP, SI and DI
.back:                              ; index, so the pointer has to be the one
    cmp si, dsh_spec                ; that moves
    jbe .colon
    dec si
    cmp byte [si], '\'
    jne .back
    inc si                          ; KEEP the separator with the folder part,
    jmp short .havecut              ; so a leading one still reads as absolute
.colon:
    cmp bx, 2                       ; no separator: is there a drive letter?
    jb .nodir
    cmp byte [dsh_spec+1], ':'
    jne .nodir
    mov si, dsh_spec                ; "d:" is the whole folder part
    add si, 2
.havecut:
    push si                         ; SI is the leaf, and everything before it
    mov di, dsh_leaf                ; is the folder
    call dsh_cpz
    pop si
    mov byte [si], 0
    call dsh_bank
    mov si, dsh_spec
    call dsh_cdto
    pushf
    call .record
    call dsh_home
    popf
    jc .no
    jmp short .ok

.nodir:
    mov si, dsh_spec                ; no folder part at all: right here
    mov di, dsh_leaf
    call dsh_cpz
    mov al, [dos_vol]
    mov [dsh_rdrv], al
    mov ax, [dos_curdir]
    mov [dsh_rclus], ax
.ok:
    clc
    ret
.no:
    stc
    ret
.record:
    mov al, [dos_vol]
    mov [dsh_rdrv], al
    mov ax, [dos_curdir]
    mov [dsh_rclus], ax
    ret

; dsh_cpspec - SI -> dsh_spec, bounded.  clobbers: AX, CX, SI, DI, flags
dsh_cpspec:
    mov di, dsh_spec
; dsh_cpz - ASCIZ from SI to DI, DSH_ARG bounded and always terminated
dsh_cpz:
    push di
    mov cx, DSH_ARG - 1
.c:
    mov al, [si]
    or al, al
    jz .end
    jcxz .end
    mov [di], al
    inc si
    inc di
    dec cx
    jmp short .c
.end:
    mov byte [di], 0
    pop di
    ret

; =============================================================================
; THE VERBS
; =============================================================================
; dsh_two - the `<source> <destination>` argument shape every file verb has
; in:  SI = the argument text
; out: CF=0 with the source resolved into [dsh_sdrv]/[dsh_sclus] + dsh_pat (the
;      padded pattern) and the destination into [dsh_ddrv]/[dsh_dclus] +
;      dsh_dname (empty = keep each source's own name); CF=1 with AL = the exit
;      code and the message already said
; clobbers: everything but the segment registers
dsh_two:
    call dsh_skipsp
    mov di, dsh_a1
    call dsh_word
    call dsh_skipsp
    mov di, dsh_a2
    call dsh_word
    cmp byte [dsh_a1], 0
    je .nosrc
    cmp byte [dsh_a2], 0
    je .nodst

    mov si, dsh_a1                  ; the SOURCE is never "try it as a folder":
    xor al, al                      ; `copy B:` means every file on B:, and
    call dsh_resolve                ; asking the disk would make it mean the
    jc .nopath                      ; folder itself
    mov al, [dsh_rdrv]
    mov [dsh_sdrv], al
    mov ax, [dsh_rclus]
    mov [dsh_sclus], ax
    cmp byte [dsh_leaf], 0
    jne .haspat
    mov word [dsh_leaf], '*' | ('.' << 8)   ; a bare folder means everything in
    mov word [dsh_leaf+2], '*'              ; it, which is `*.*`
.haspat:
    mov si, dsh_leaf
    mov di, dsh_pat
    call dsh_to11

    mov si, dsh_a2                  ; ...and the DESTINATION always is
    mov al, 1
    call dsh_resolve
    jc .nopath
    mov al, [dsh_rdrv]
    mov [dsh_ddrv], al
    mov ax, [dsh_rclus]
    mov [dsh_dclus], ax
    mov si, dsh_leaf
    mov di, dsh_dname
    call dsh_cpz
    clc
    ret
.nosrc:
.nodst:
    mov si, dsh_s_syntax
    call dsh_say
    mov byte [dsh_why], DSHW_SYNTAX
    mov al, 1
    stc
    ret
.nopath:
    mov si, dsh_s_nopath
    call dsh_say
    mov byte [dsh_why], DSHW_NOPATH
    mov al, 3
    stc
    ret

; -----------------------------------------------------------------------------
; dsh_nth - the [dsh_skip]th name in the CURRENT folder matching dsh_pat
; out: CF=0 with dsh_fname = the name and [dsh_isdir] set; CF=1 = no more
; clobbers: AX, BX, CX, DX, SI, DI, flags
;
; BY ORDINAL AND WITH A SKIP COUNT, because OSAPI_FILE_FIND is by ordinal and
; a directory that is being WRITTEN renumbers underneath one (SPEC.md 19.7.1).
; A copy leaves the source folder alone, so it walks with the skip count
; rising; a DELETE or a MOVE takes an entry out, so it asks for the FIRST match
; every time and each pass makes progress. One loop, one parameter, and the
; destructive case cannot skip a file by counting one that has gone.
; -----------------------------------------------------------------------------
dsh_nth:
    push es
    push ds
    pop es
    xor cx, cx                      ; the ordinal
    mov dx, [dsh_skip]              ; how many matches to pass over
.step:
    mov di, dsh_fnd
    call dos_be_find
    jc .none
    push cx
    mov si, dsh_fnd                 ; +0 is the ASCIZ name
    mov di, dsh_nm11
    call dsh_to11
    mov si, dsh_nm11
    mov di, dsh_pat
    call dsh_match
    pop cx
    jc .step
    cmp word [dsh_fnd+14], OSAPI_FT_DIR
    jae .step                       ; a folder is not a file to copy, and '..'
                                    ; is never reported anyway (96.12.2)
    or dx, dx
    jz .got
    dec dx
    jmp short .step
.got:
    mov si, dsh_fnd
    mov di, dsh_fname
    call dsh_cpz
    pop es
    clc
    ret
.none:
    pop es
    stc
    ret

; -----------------------------------------------------------------------------
; dsh_c_copy - COPY, and the engine XCOPY and MOVE also run
; in:  SI = the arguments
; out: AL = the exit code
; -----------------------------------------------------------------------------
dsh_c_copy:
    mov byte [dsh_del], 0
dsh_copy_go:
    call dsh_two
    jc .out
    mov al, [dsh_sdrv]              ; ONTO ITSELF is refused, and not only
    cmp al, [dsh_ddrv]              ; because DOS refuses it: a copy INTO the
    jne .ok                         ; folder being walked adds entries, which
    mov ax, [dsh_sclus]             ; renumbers the ordinals dsh_nth is
    cmp ax, [dsh_dclus]             ; counting, and the walk would never end
    jne .ok
    cmp byte [dsh_dname], 0
    je .self                        ; same folder, no new name
.ok:
    call dsh_bank
    call dsh_bufget                 ; the DOS arena's, not the heap's
    jc .nomem
    mov word [dsh_skip], 0
    mov word [dsh_n], 0
.each:
    mov dx, [dsh_sclus]             ; stand in the source folder for the walk
    mov bl, [dsh_sdrv]
    call dos_be_goto
    jc .ioerr
    mov [dos_curdir], dx
    call dsh_nth
    jc .done

    mov si, dsh_dname               ; the destination's name: the one it was
    cmp byte [dsh_dname], 0         ; given, or each source's own
    jne .named
    mov si, dsh_fname
.named:
    mov di, dsh_cname
    call dsh_cpz

    cmp byte [dsh_del], 0
    je .justcopy

    push ds                         ; A MOVE FIRST: on one volume this rewrites
    pop es                          ; the directory entry and reads no data at
    mov si, dsh_fname               ; all (SPEC.md 22.25). AX=0 is "not
    mov bl, [dsh_sdrv]              ; attempted", and only then is a copy worth
    mov bh, [dsh_ddrv]              ; its cost
    mov dx, [dsh_sclus]
    mov cx, [dsh_dclus]
    call dos_be_move
    jnc .moved
    or ax, ax
    jnz .ioerr
    call dsh_stream                 ; ...and the copy half of the fallback
    jc .ioerr
    mov dx, [dsh_sclus]             ; ...then the source, once it is whole
    mov bl, [dsh_sdrv]
    call dos_be_goto
    jc .ioerr
    mov [dos_curdir], dx
    mov si, dsh_fname
    call dsh_delone
    jc .ioerr
.moved:
    inc word [dsh_n]
    jmp .each                       ; the source lost an entry, so the FIRST
                                    ; match is the next one
.justcopy:
    call dsh_stream
    jc .ioerr
    inc word [dsh_n]
    inc word [dsh_skip]             ; the source is untouched, so step past the
    jmp .each                       ; one just done

.done:
    call dsh_bufput
    call dsh_home
    cmp word [dsh_n], 0
    je .nofile
    call dsh_count
    xor al, al
    ret
.ioerr:
    call dsh_bufput
    call dsh_home
    mov si, dsh_s_ioerr
    call dsh_say
    mov byte [dsh_why], DSHW_IO
    mov al, 1
    ret
.nomem:
    call dsh_home
    mov si, dsh_s_nomem
    call dsh_say
    mov byte [dsh_why], DSHW_MEM
    mov al, 1
    ret
.nofile:
    mov si, dsh_s_nofile
    call dsh_say
    mov byte [dsh_why], DSHW_NOFILE
    mov al, 1
    ret
.self:
    mov si, dsh_s_self
    call dsh_say
    mov byte [dsh_why], DSHW_SELF
    mov al, 1
.out:
    ret

dsh_c_move:
    mov byte [dsh_del], 1
    jmp dsh_copy_go

dsh_c_xcopy:
    mov byte [dsh_del], 0
    jmp dsh_copy_go

; -----------------------------------------------------------------------------
; dsh_bufget / dsh_bufput - THE COPY BUFFER, OUT OF THE DOS ARENA
; out: CF=0 with [dsh_cpseg] a block and [dsh_cpkb] its KB; CF=1 = none
; clobbers: AX, BX, ES, flags
;
; NOT THE HEAP, AND NOT THE DISK CACHE - and the second of those is the
; interesting one (SPEC.md 96.30.6). A copy's payload never enters the
; read-ahead cache: SPEC.md 18.95.1 skips the fill whenever the caller's
; request already covers the whole chunk, because filling would read exactly
; what the direct path reads and evict a slot for sectors nobody asks for
; twice - which is what stops a streaming copy flushing the DIRECTORY chunks
; out from under itself. So there is no cached copy of the payload to write
; from; the bytes are DMA'd into a buffer once and written out of it once, and
; the only question is whose buffer.
;
; Inside the fsx bracket the heap is the DOS program's, every byte of it, so
; OSAPI_FILE_COPY's own claim answers FERR_FULL. The arena is where DOS itself
; would take it: a program that EXECs must free memory first - that is the DOS
; contract and tests/dosexec/parent.asm asserts it, a 4Bh before AH=4Ah
; answering 8 - so a program that shells out has, by construction, left room
; for a shell to load into. Ours loads a buffer instead of a COMMAND.COM.
; -----------------------------------------------------------------------------
dsh_bufget:
    mov word [dsh_cpseg], 0
    mov ax, DSH_CPKB
.try:
    mov [dsh_cpkb], ax
    mov bx, ax
    mov cl, 6
    shl bx, cl                      ; KB -> paragraphs
    call dos_mcb_alloc
    jnc .got
    mov ax, [dsh_cpkb]              ; halve and retry: a machine that cannot
    shr ax, 1                       ; fund 8KB can very often fund one, and a
    cmp ax, DSH_CPMINKB             ; smaller buffer is a slower copy rather
    jae .try                        ; than no copy
    stc
    ret
.got:
    mov [dsh_cpseg], ax
    clc
    ret

dsh_bufput:
    push es
    mov ax, [dsh_cpseg]
    or ax, ax
    jz .none
    mov es, ax
    call dos_mcb_free
    mov word [dsh_cpseg], 0
.none:
    pop es
    ret

; -----------------------------------------------------------------------------
; dsh_stream - ONE file, from the folder we are standing in to the destination
; in:  dsh_fname = the source's name, dsh_cname = the destination's,
;      [dsh_ddrv]/[dsh_dclus] the destination place; we are STANDING in the
;      source folder and are put back there
; out: CF=0 copied; CF=1 with AX = FERR_*
; clobbers: AX, BX, CX, DX, SI, DI, flags
;
; A HAND-ROLLED COPY, WHICH SPEC.md 22.24 WARNS ABOUT - and the half it says
; gets got wrong is written here on purpose: a destination that was created
; and then failed is DELETED, so a half-copy never survives as a plausible
; file. The other half of the warning, the redirector's FSV_COPY fast path, is
; genuinely lost; it applies to a remote-to-remote pair, which is not a thing
; a DOS program inside an fsx bracket has.
; -----------------------------------------------------------------------------
dsh_stream:
    mov word [dsh_off], 0
    mov word [dsh_off+2], 0
    mov byte [dsh_made], 0
.chunk:
    mov dx, [dsh_sclus]             ; the SOURCE, every pass: the write below
    mov bl, [dsh_sdrv]              ; stands in the destination folder
    call dos_be_goto
    jc .ioerr
    mov [dos_curdir], dx
    mov es, [dsh_cpseg]
    mov si, dsh_fname
    xor bx, bx
    mov cx, [dsh_cpkb]
    mov ax, cx
    mov cl, 10
    shl ax, cl                      ; KB -> bytes; DSH_CPKB is small enough
    mov cx, ax                      ; that this cannot reach 64KB
    mov dx, [dsh_off+2]
    mov ax, [dsh_off]
    call dos_be_rdat                ; out DX:AX = what it delivered
    jc .ioerr
    mov cx, ax
    or cx, cx
    jnz .write
    cmp word [dsh_off], 0           ; nothing delivered on the FIRST pass is an
    jne .done                       ; empty file, which still has to be created
    cmp word [dsh_off+2], 0
    jne .done
.write:
    mov [dsh_got], cx
    mov dx, [dsh_dclus]
    mov bl, [dsh_ddrv]
    call dos_be_goto
    jc .ioerr
    mov [dos_curdir], dx
    mov es, [dsh_cpseg]
    mov si, dsh_cname
    xor bx, bx
    mov cx, [dsh_got]
    cmp byte [dsh_made], 0
    jne .app
    xor dx, dx                      ; the FIRST chunk CREATES (and replaces)...
    call dos_be_write
    jc .ioerr
    mov byte [dsh_made], 1
    jmp short .step
.app:
    call dos_be_append              ; ...and every one after it extends
    jc .ioerr
.step:
    mov cx, [dsh_got]
    add [dsh_off], cx
    adc word [dsh_off+2], 0
    or cx, cx
    jnz .chunk
.done:
    clc
    ret
.ioerr:
    push ax                         ; THE UNDO: a destination that exists and
    cmp byte [dsh_made], 0          ; is short is worse than no destination at
    je .nofile                      ; all, because it looks like a file
    mov dx, [dsh_dclus]
    mov bl, [dsh_ddrv]
    call dos_be_goto
    jc .nofile
    mov [dos_curdir], dx
    mov si, dsh_cname
    call dos_be_delete
.nofile:
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; dsh_delone - delete the name at SI in the folder we are standing in
; out: CF from the back end.  clobbers: AX, flags
dsh_delone:
    push si
    call dos_be_delete
    pop si
    ret

; dsh_c_del - DEL and ERASE
dsh_c_del:
    call dsh_skipsp
    mov di, dsh_a1
    call dsh_word
    cmp byte [dsh_a1], 0
    je .syntax
    mov si, dsh_a1
    xor al, al
    call dsh_resolve
    jc .nopath
    cmp byte [dsh_leaf], 0
    jne .haspat
    mov word [dsh_leaf], '*' | ('.' << 8)
    mov word [dsh_leaf+2], '*'
.haspat:
    mov si, dsh_leaf
    mov di, dsh_pat
    call dsh_to11

    call dsh_bank
    mov word [dsh_skip], 0          ; ALWAYS THE FIRST MATCH: each delete takes
    mov word [dsh_n], 0             ; an entry out and renumbers the ordinals
.each:
    mov dx, [dsh_rclus]
    mov bl, [dsh_rdrv]
    call dos_be_goto
    jc .ioerr
    mov [dos_curdir], dx
    call dsh_nth
    jc .done
    mov si, dsh_fname
    call dsh_delone
    jc .ioerr
    inc word [dsh_n]
    jmp short .each
.done:
    call dsh_home
    cmp word [dsh_n], 0
    je .nofile
    xor al, al
    ret
.ioerr:
    call dsh_home
    mov si, dsh_s_ioerr
    call dsh_say
    mov byte [dsh_why], DSHW_IO
    mov al, 1
    ret
.nofile:
    mov si, dsh_s_nofile
    call dsh_say
    mov byte [dsh_why], DSHW_NOFILE
    mov al, 1
    ret
.syntax:
    mov si, dsh_s_syntax
    call dsh_say
    mov byte [dsh_why], DSHW_SYNTAX
    mov al, 1
    ret
.nopath:
    mov si, dsh_s_nopath
    call dsh_say
    mov byte [dsh_why], DSHW_NOPATH
    mov al, 3
    ret

; -----------------------------------------------------------------------------
; dsh_c_ren - REN and RENAME: both names in ONE folder, which is what DOS's own
; AH=56h does (SPEC.md 96.31) and what OSAPI_FILE_RENAME publishes. A rename
; that would move is MOVE's job and says so.
dsh_c_ren:
    call dsh_skipsp
    mov di, dsh_a1
    call dsh_word
    call dsh_skipsp
    mov di, dsh_a2
    call dsh_word
    cmp byte [dsh_a1], 0
    je .syntax
    cmp byte [dsh_a2], 0
    je .syntax
    mov si, dsh_a1
    xor al, al
    call dsh_resolve
    jc .nopath
    cmp byte [dsh_leaf], 0
    je .syntax
    mov si, dsh_leaf                ; the old name, out of the resolve
    mov di, dsh_a1
    call dsh_cpz

    call dsh_bank
    mov dx, [dsh_rclus]
    mov bl, [dsh_rdrv]
    call dos_be_goto
    jc .ioerr
    mov [dos_curdir], dx
    mov si, dsh_a1
    mov di, dsh_a2
    call dos_be_rename
    jc .ioerr
    call dsh_home
    xor al, al
    ret
.ioerr:
    call dsh_home
    mov si, dsh_s_ioerr
    call dsh_say
    mov byte [dsh_why], DSHW_IO
    mov al, 1
    ret
.syntax:
    mov si, dsh_s_syntax
    call dsh_say
    mov byte [dsh_why], DSHW_SYNTAX
    mov al, 1
    ret
.nopath:
    mov si, dsh_s_nopath
    call dsh_say
    mov byte [dsh_why], DSHW_NOPATH
    mov al, 3
    ret

; -----------------------------------------------------------------------------
; dsh_c_md / dsh_c_rd / dsh_c_cd - one folder name each
dsh_c_md:
    mov byte [dsh_dirop], 0
    jmp short dsh_dir_go
dsh_c_rd:
    mov byte [dsh_dirop], 1
    jmp short dsh_dir_go
dsh_c_cd:
    mov byte [dsh_dirop], 2
dsh_dir_go:
    call dsh_skipsp
    mov di, dsh_a1
    call dsh_word
    cmp byte [dsh_a1], 0
    je .syntax
    cmp byte [dsh_dirop], 2
    je .chdir

    mov si, dsh_a1                  ; MD and RD name a folder INSIDE another,
    xor al, al                      ; so the leaf is the new name and the place
    call dsh_resolve                ; is where it goes
    jc .nopath
    cmp byte [dsh_leaf], 0
    je .syntax
    call dsh_bank
    mov dx, [dsh_rclus]
    mov bl, [dsh_rdrv]
    call dos_be_goto
    jc .ioerr
    mov [dos_curdir], dx
    mov si, dsh_leaf
    cmp byte [dsh_dirop], 0
    jne .rm
    call dos_be_mkdir
    jmp short .fin
.rm:
    xor al, al                      ; strict: a folder with anything in it is
    call dos_be_rmdir               ; refused, which is DOS's own answer
.fin:
    jc .ioerr
    call dsh_home
    xor al, al
    ret
.chdir:
    mov si, dsh_a1                  ; ...and CD just stands there. In a /C
    call dsh_cdto                   ; shell dsh_tail puts us back afterwards,
    jc .nopath                      ; which is what a child shell's exit does
    xor al, al                      ; under DOS
    ret
.ioerr:
    call dsh_home
    mov si, dsh_s_ioerr
    call dsh_say
    mov byte [dsh_why], DSHW_IO
    mov al, 1
    ret
.syntax:
    mov si, dsh_s_syntax
    call dsh_say
    mov byte [dsh_why], DSHW_SYNTAX
    mov al, 1
    ret
.nopath:
    mov si, dsh_s_nopath
    call dsh_say
    mov byte [dsh_why], DSHW_NOPATH
    mov al, 3
    ret

; -----------------------------------------------------------------------------
; dsh_c_type - a file to the screen, in chunks, through the ROM teletype
dsh_c_type:
    call dsh_skipsp
    mov di, dsh_a1
    call dsh_word
    cmp byte [dsh_a1], 0
    je .syntax
    mov si, dsh_a1
    xor al, al
    call dsh_resolve
    jc .nopath
    cmp byte [dsh_leaf], 0
    je .syntax
    call dsh_bank
    mov dx, [dsh_rclus]
    mov bl, [dsh_rdrv]
    call dos_be_goto
    jc .ioerr
    mov [dos_curdir], dx
    mov word [dsh_off], 0
    mov word [dsh_off+2], 0
.chunk:
    push ds
    pop es
    mov si, dsh_leaf
    mov bx, dsh_buf
    mov cx, DSH_BUF
    mov dx, [dsh_off+2]
    mov ax, [dsh_off]
    call dos_be_rdat                ; out DX:AX = what it delivered
    jc .ioerr
    mov cx, ax
    or cx, cx
    jz .fin
    add [dsh_off], cx
    adc word [dsh_off+2], 0
    mov si, dsh_buf
.putc:
    mov al, [si]
    cmp al, 26                      ; ^Z ends a text file, as it does under DOS
    je .fin
    call dos_tty
    inc si
    loop .putc
    jmp short .chunk
.fin:
    call dsh_home
    xor al, al
    ret
.ioerr:
    call dsh_home
    mov si, dsh_s_ioerr
    call dsh_say
    mov byte [dsh_why], DSHW_IO
    mov al, 1
    ret
.syntax:
    mov si, dsh_s_syntax
    call dsh_say
    mov byte [dsh_why], DSHW_SYNTAX
    mov al, 1
    ret
.nopath:
    mov si, dsh_s_nopath
    call dsh_say
    mov byte [dsh_why], DSHW_NOPATH
    mov al, 3
    ret

; -----------------------------------------------------------------------------
; dsh_c_dir - DIR (SPEC.md 96.33.4)
; in:  SI = the arguments
; out: AL = the exit code
;
; **THE TABLE HAD NO DIR AND THAT WAS RIGHT UNTIL THERE WAS A PROMPT.** Every
; other verb here is one a PROGRAM shells out for (SPEC.md 96.30.1 measured
; which); nothing shells out to list a directory, because a program that wants
; a listing calls `AH=4Eh`. A person at a prompt wants nothing else first.
;
; ONE LINE A FILE, DOS's own columns: the name padded to 8, the extension
; padded to 3, then `<DIR>` or the size right-aligned. No date and no time -
; the listing record carries neither (`OSAPI_FIND_SZ`'s six fields) and a
; column of blanks is worse than no column.
;
; **FOLDERS ARE LISTED AND `..` IS NOT SKIPPED**, which is the opposite of
; dsh_nth's rule and deliberate: that walker feeds COPY, where a folder is not
; a file to copy; this one is the user's picture of where they are, and `..`
; is how they know they are not at the root.
; -----------------------------------------------------------------------------
dsh_c_dir:
    call dsh_skipsp
    mov di, dsh_a1
    call dsh_word
    cmp byte [dsh_a1], 0
    jne .havearg
    mov word [dsh_a1], '*' | ('.' << 8)     ; a bare DIR is `*.*`, here as
    mov word [dsh_a1+2], '*'                ; everywhere else
.havearg:
    mov si, dsh_a1
    mov al, 1                       ; ...and a whole spec that IS a folder is
    call dsh_resolve                ; listed rather than matched, which is what
    jc .nopath                      ; `DIR APPS` has to mean
    cmp byte [dsh_leaf], 0
    jne .haspat
    mov word [dsh_leaf], '*' | ('.' << 8)
    mov word [dsh_leaf+2], '*'
.haspat:
    mov si, dsh_leaf
    mov di, dsh_pat
    call dsh_to11

    call dsh_bank
    mov dx, [dsh_rclus]
    mov bl, [dsh_rdrv]
    call dos_be_goto
    jc .ioerr
    mov [dos_curdir], dx
    mov word [dsh_n], 0
    xor cx, cx                      ; the ordinal
.each:
    push ds
    pop es
    push cx
    mov di, dsh_fnd
    call dos_be_find                ; out CX = the NEXT ordinal
    jc .done
    pop ax                          ; ...the one we asked for, spent
    push cx
    mov si, dsh_fnd
    mov di, dsh_nm11
    call dsh_to11
    mov si, dsh_nm11
    mov di, dsh_pat
    call dsh_match
    jc .next
    call dsh_dirline
    inc word [dsh_n]
.next:
    pop cx
    jmp short .each
.done:
    pop cx
    call dsh_home
    call dsh_dirtot
    xor al, al
    ret
.ioerr:
    call dsh_home
    mov si, dsh_s_ioerr
    call dsh_say
    mov byte [dsh_why], DSHW_IO
    mov al, 1
    ret
.nopath:
    mov si, dsh_s_nopath
    call dsh_say
    mov byte [dsh_why], DSHW_NOPATH
    mov al, 3
    ret

; --- dsh_dirline - one entry of [dsh_fnd], as DOS lays it out ----------------
; clobbers: AX, BX, CX, DX, SI, DI, flags
dsh_dirline:
    mov si, dsh_nm11                ; the padded form dsh_to11 just built, which
    mov cx, 8                       ; is the columns already - the `?` a pattern
    call .field                     ; expansion leaves is not in it, dsh_to11
    mov al, ' '                     ; having been given a real name
    call dos_tty
    mov si, dsh_nm11 + 8
    mov cx, 3
    call .field
    mov al, ' '
    call dos_tty
    cmp word [dsh_fnd+14], OSAPI_FT_DIR
    jb .size
    mov si, dsh_s_dir               ; `<DIR>`, and `..` gets it too
    call dsh_say
    jmp short .eol
.size:
    mov ax, [dsh_fnd+18]            ; **THE LOW WORD, and the high one is not
    mov dx, [dsh_fnd+20]            ; dropped** - dsh_num32 takes both, because
    call dsh_num32                  ; a 65KB file on a 1.44MB floppy is ordinary
.eol:
    mov si, dsh_s_crlf
    call dsh_say
    ret
.field:                             ; CX bytes at SI, verbatim
    mov al, [si]
    call dos_tty
    inc si
    loop .field
    ret

; --- dsh_dirtot - `N file(s)`, DOS's own footer -----------------------------
dsh_dirtot:
    mov si, dsh_s_crlf
    call dsh_say
    mov ax, [dsh_n]
    xor dx, dx
    call dsh_num32
    mov si, dsh_s_files
    call dsh_say
    ret

; --- dsh_num32 - DX:AX as decimal, right-aligned in eight columns -----------
; clobbers: AX, BX, CX, DX, SI, DI, flags
;
; A 32-BIT DIVIDE and not two 16-bit ones: `div bx` on DX:AX quotients into AX
; with the remainder in DX and needs the high half to be smaller than the
; divisor, which after the first step it always is - so the loop is the
; ordinary one and the only thing 32 bits costs is zeroing DX once.
dsh_num32:
    mov di, dsh_num + 11
    mov byte [di], 0
    mov bx, 10
.d:
    push ax
    mov ax, dx
    xor dx, dx
    div bx                          ; the HIGH half first, remainder into DX
    mov cx, ax                      ; ...which is the top of the next divide
    pop ax
    div bx                          ; DX:AX / 10 completed
    dec di
    add dl, '0'
    mov [di], dl
    mov dx, cx
    or ax, ax
    jnz .d
    or dx, dx
    jnz .d
.pad:
    mov si, dsh_num + 11
    sub si, di                      ; SI = the digits written
    mov cx, 8
    sub cx, si
    jbe .say
.sp:
    mov al, ' '
    call dos_tty
    loop .sp
.say:
    mov si, di
    call dsh_say
    ret

; -----------------------------------------------------------------------------
; dsh_c_ver / dsh_c_echo / dsh_c_rem
dsh_c_ver:
    mov si, dsh_s_ver
    call dsh_say
    xor al, al
    ret

dsh_c_echo:
    call dsh_skipsp
    call dsh_say
    mov si, dsh_s_crlf
    call dsh_say
    xor al, al
    ret

dsh_c_rem:
    xor al, al
    ret

; dsh_count - "N file(s) copied", DOS's own report
; clobbers: AX, BX, CX, DX, SI, DI, flags
dsh_count:
    mov ax, [dsh_n]
    mov di, dsh_num + 5
    mov byte [di], 0
    mov bx, 10
.d:
    xor dx, dx
    div bx
    dec di
    add dl, '0'
    mov [di], dl
    or ax, ax
    jnz .d
    mov si, di
    call dsh_say
    mov si, dsh_s_copied
    call dsh_say
    ret

; =============================================================================
; THE TABLE
; =============================================================================
; Eleven bytes a row: a marker, the verb NUL-padded to eight, and the handler.
; A marker rather than a length because the compare is dsh_same's, which needs
; the terminator and not the count; zero ends the table.
%macro DSHCMD 2
    db 0xFF
  %%n:
    db %1, 0
    times 8 - ($ - %%n) db 0
    dw %2
%endmacro

dsh_tab:
    DSHCMD 'COPY',   dsh_c_copy
    DSHCMD 'XCOPY',  dsh_c_xcopy
    DSHCMD 'MOVE',   dsh_c_move
    DSHCMD 'DEL',    dsh_c_del
    DSHCMD 'ERASE',  dsh_c_del
    DSHCMD 'REN',    dsh_c_ren
    DSHCMD 'RENAME', dsh_c_ren
    DSHCMD 'MD',     dsh_c_md
    DSHCMD 'MKDIR',  dsh_c_md
    DSHCMD 'RD',     dsh_c_rd
    DSHCMD 'RMDIR',  dsh_c_rd
    DSHCMD 'CD',     dsh_c_cd
    DSHCMD 'CHDIR',  dsh_c_cd
    DSHCMD 'TYPE',   dsh_c_type
    DSHCMD 'DIR',    dsh_c_dir
    DSHCMD 'VER',    dsh_c_ver
    DSHCMD 'ECHO',   dsh_c_echo
    DSHCMD 'REM',    dsh_c_rem
    db 0

; [dsh_why] - WHICH refusal, for a debugger and not for the program
; The exit code stays DOS's (1, or 3 for a path), because a shell's exit code
; is what a batch file tests and inventing a richer one would be a contract
; nobody asked for. But `> NUL` silences the message, so under exactly the
; conditions a program shells out in there is NOTHING to read - which cost this
; session two emulator runs to recover by other means. One byte fixes it.
DSHW_NONE   equ 0
DSHW_MEM    equ 1               ; no DOS block for the copy buffer (96.30.6)
DSHW_IO     equ 2               ; the back end refused
DSHW_NOFILE equ 3               ; nothing matched the pattern
DSHW_SELF   equ 4               ; source and destination are one file
DSHW_NOPATH equ 5               ; no such folder
DSHW_SYNTAX equ 6               ; wrong number of arguments
DSHW_REDIR  equ 7               ; a redirection target that is not NUL
DSHW_NOCMD  equ 8               ; no such verb - which from a prompt means
                                ; "try it as a program" (SPEC.md 96.33.3)
DSHW_NODRV  equ 9               ; `X:` named a drive that is not there

dsh_s_nul:      db 'NUL', 0
dsh_s_crlf:     db 13, 10, 0
dsh_s_bad:      db 'Bad command or file name: ', 0
dsh_s_syntax:   db 'Invalid number of parameters', 13, 10, 0
dsh_s_nopath:   db 'Path not found', 13, 10, 0
dsh_s_nofile:   db 'File not found', 13, 10, 0
dsh_s_ioerr:    db 'File creation error', 13, 10, 0
dsh_s_self:     db 'File cannot be copied onto itself', 13, 10, 0
dsh_s_copied:   db ' file(s) copied', 13, 10, 0
dsh_s_files:    db ' file(s)', 13, 10, 0
dsh_s_dir:      db '<DIR>', 0
dsh_s_redir:    db 'Cannot redirect to that file', 13, 10, 0
dsh_s_nomem:    db 'Insufficient memory', 13, 10, 0
dsh_s_nodrv:    db 'Invalid drive specification', 13, 10, 0
dsh_s_ver:      db 13, 10, 'os8088 DOS Version 3.31', 13, 10, 0
                                ; **NOT "box" AND NOT "MS-DOS"** - this is not
                                ; a box to the person typing at it and it is
                                ; not Microsoft's. The VERSION stays 3.31
                                ; because that is what AH=30h answers
                                ; (SPEC.md 96.7), and a machine whose VER and
                                ; whose programs disagree is worse than either

; -----------------------------------------------------------------------------
; dsh_isshell - is the AH=4Bh program name our built-in COMMAND.COM?
; in:  [bp] = the caller's DS and DX its offset - the EXEC argument untouched
; out: CF=0 it is; CF=1 it is not, and .exec carries on as before
; clobbers: flags only
;
; THE RAW NAME AND NOT THE PARSED ONE, deliberately: COMSPEC is usually a full
; path (`C:\COMMAND.COM`) on a drive that may not exist here, so parsing it
; first would refuse with "invalid drive" before anything could recognise it.
; The last component is the whole question.
; -----------------------------------------------------------------------------
dsh_isshell:
    push ax
    push cx
    push si
    push di
    push es
    mov ax, [bp]
    mov es, ax
    mov si, dx
    xor cx, cx
.len:
    cmp byte [es:si], 0
    je .end
    inc si
    inc cx
    cmp cx, 80
    jb .len
    jmp short .no                   ; longer than any COMSPEC: not ours
.end:
    or cx, cx
    jz .no
.back:
    or cx, cx
    jz .cmp
    dec si
    dec cx
    mov al, [es:si]
    cmp al, '\'
    je .fwd
    cmp al, '/'
    je .fwd
    cmp al, ':'
    je .fwd
    jmp short .back
.cmp:
    dec si                          ; .back stopped AT the separator when it
    inc si                          ; found one and one short of the start when
.fwd:                               ; it did not; .fwd is the shared step past
    inc si                          ; it, and this pair makes the no-separator
    dec si                          ; case land on the same instruction
    mov di, dsh_s_cmd
.c:
    mov al, [es:si]
    or al, al
    jz .tail
    or al, 0x20                     ; case-insensitively: COMSPEC is normally
    cmp al, [di]                    ; upper case and the literal fallback a
    jne .no                         ; program carries is normally lower
    inc si
    inc di
    jmp short .c
.tail:
    cmp byte [di], 0
    jne .no
    pop es
    pop di
    pop si
    pop cx
    pop ax
    clc
    ret
.no:
    pop es
    pop di
    pop si
    pop cx
    pop ax
    stc
    ret

dsh_s_cmd:      db 'command.com', 0
