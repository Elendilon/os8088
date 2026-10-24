%ifdef CH_OVERLAY
; =============================================================================
; os88chartovl.inc - the resident half of the shared chart module (82.16).
;
; apps/os88chart.inc is ~4,800 bytes of rasterizer that BOTH sheet.asm and
; chart.asm carried a private copy of. It is a module now - one CHART.OVL
; loaded beside the package and far-called - and this file is what each
; package keeps resident to reach it: the loader, the shims the module calls
; back through, and the verb wrapper.
;
; ONLY SHEET OVERLAYS IT, and CHART.OVL IS SHEET'S FILE ALONE. chart.o88
; defines neither CH_ symbol, never includes this file, and carries the
; rasterizer resident; the Makefile cuts CHART.OVL from build/sheet.bin and
; from nothing else.
;
; An earlier version of this comment claimed "ONE FILE SERVES BOTH PACKAGES"
; and that "the Makefile asserts the two independently-assembled .OVLs are
; identical". BOTH HALVES ARE FALSE, and 82.16.1 - written later, and right -
; says why the first one CANNOT be true: the module reaches the ch_* block at
; absolute offsets past the package's own image end, and the two packages'
; images are different lengths, so one binary could never address both. There
; is no identity rule in the Makefile and no second assembly for it to compare
; against.
;
; The cost of leaving that standing is not a wrong result, it is a wrong
; BOUNDARY: a jointly-owned tail is one nothing else may be put in, so the
; comment quietly retires Sheet's only room to grow. It is Sheet's tail, and
; a second tenant belongs in it (82.16.6).
;
; Include it BEFORE os88chart.inc, and after os88fp.inc (the shims name it).
; The caller must have called OSAPI_FILE_HERE at entry and banked the answer
; in ch_ovdir/ch_ovdrv - that is where the .OVL lives, and the user is free to
; navigate away a moment later.
; =============================================================================
CH_OVKB      equ 52                 ; the claim CHART.OVL is read into, KB.
                                    ; 52 at the review of PR #289: main's
                                    ; SYLK borders/notes and the Border
                                    ; dialog's block walk (81.17.2), ported
                                    ; in, 52,372 of 51's 52,224.
                                    ; 48 for 81.102: the Note dialog and
                                    ; os88text.inc moved in, 47,364 bytes.
                                    ; 8 held the rasterizer alone; 82.16.9 put
                                    ; SHEET's file formats in the same tail and
                                    ; took it to 13,485 bytes; 82.16.10's
                                    ; financial family to 19,544; 81.10.10's
                                    ; formula decoder past 20,480, so 22; and
                                    ; 81.59 23, with 122 bytes left at 22 and
                                    ; no tenant yet; 81.62's text, logarithm
                                    ; and information functions 26; 81.63's
                                    ; macro engine 28; 81.65's DATABASE
                                    ; functions 29,220 bytes, so 29; 81.66's
                                    ; CELL 29,956, so 30; 81.67's array/
                                    ; matrix functions 31,638, so 31, and its
                                    ; own regression family (LINEST/LOGEST/
                                    ; TREND/GROWTH) 33,034, so 33 - that
                                    ; is heap, not image; and 81.77's BLANK
                                    ; records 44,031 of 44,032, so 44; and
                                    ; 81.81's Format > Justify 44,9xx, so 45
                                    ; - taken for the SAME reason as the step
                                    ; below, 59 bytes being no more a margin
                                    ; than one was; and 81.82's Data > Parse
                                    ; 45,896, so 46; and the macro plan's
                                    ; wave 1 (SHEET-MACRO-PLAN, subroutines
                                    ; and their ~1 KB of frame state) 48,553,
                                    ; so 50 - two ahead ON PURPOSE, the plan
                                    ; having ~8 KB still to come, and 64 the
                                    ; wall: the module is ONE segment; and
                                    ; wave 2's control functions (81.86)
                                    ; 50,725, so 54 ahead of the information
                                    ; half, which is the bigger one; and wave
                                    ; 3a's command equivalents (81.88) 54,541,
                                    ; so 58; and 63 for the macro text files
                                    ; (81.91), whose buffers are the claim's
                                    ; TAIL past the image - 63 is the most
                                    ; `mov cx, CH_OVKB * 1024` below can say.
                                    ; THAT
                                    ; LAST STEP WAS TAKEN FOR ONE BYTE, and
                                    ; deliberately: 43 still built, with a
                                    ; single byte spare, and a margin of one
                                    ; is not a margin - it is the next change
                                    ; failing a build for a reason that has
                                    ; nothing to do with it. ch_ovneed reads
                                    ; CH_OVKB*1024 bytes and a short claim
                                    ; would silently truncate the module, so
                                    ; it IS checked against the file, twice:
                                    ; the sheet.o88 rule, and os88ovlchk.py's
                                    ; CLAIMS row in the fast tier.
                                    ; AND 81.114.7's Data > Table stage 2
                                    ; (the table list, the two guards and the
                                    ; unmark walk) 49,204, so 51 - THREE
                                    ; ahead, the same deliberate step as 50
                                    ; above and for the same reason:
                                    ; SHEET-TABLE-PLAN has three stages left,
                                    ; and stage 4 is a BIFF reader AND a
                                    ; writer. 48 had 90 bytes spare when
                                    ; stage 2 began and 48 was where stage 2
                                    ; ran out, mid-fix. This is HEAP and not
                                    ; image - 82.16.3 already says a machine
                                    ; too small for the claim still runs the
                                    ; spreadsheet - and 63 is the wall
CHM_DRAW     equ 0                  ; the verbs - the module's dispatch indices
CHM_SCALE    equ 1
CHM_BMPWRITE equ 2
CHM_MAX      equ 2

; -----------------------------------------------------------------------------
; ch_xthunk - EVERY CALL A MODULE MAKES BACK INTO THE PACKAGE (82.16.11).
;
; A module reaches resident code with `call far [vector]`, which pushes the
; MODULE'S OWN CS for the far return. The module's claim is MOVABLE (82.16.11,
; NO-PINNING P1b), and a resident routine can claim - a file call, a window
; shown, a dialog asked - so a compaction under it could slide the module and
; leave that CS naming whatever took its place. The retf would land there.
; apps/cc/crt0.asm's cc_ovthunk is the same problem in the C SDK, and this is
; its shape, done IN PLACE because no register here is dead:
;
;   way in   the stacked CS is swapped for a TAG naming WHICH module called:
;            the ADDRESS of the word that names it - ch_ovseg for this
;            include's module, CH_OV2SEG for the includer's second one
;            (SHEET's MACRO.OVL, [sh_m2far+2]) - and the routine is entered
;            with a near return to .back, so it sees [ret][IP][tag]: the same
;            depth as the old shim's [ret][IP][CS], every offset unchanged.
;   way back the tag is dereferenced: that module's segment AS IT IS NOW, the
;            word its relocation proc keeps (ch_ovreloc, sh_m2reloc), and the
;            retf takes it. No compare, so no flag is touched on the way back.
;
; Nothing is stashed off the stack, so there is no depth limit and no global
; to race: a routine may re-enter a module (ch_ovcall pushes the REGION's CS,
; which the kernel pins while a callback stands - mem_in_nest) and that module
; may call back again, each frame carrying its own tag. A CS that is NEITHER
; module's cannot reach here: every vector is called from module code, and a
; module runs only at its own claim. So "not the first" is taken as "the
; second" without a second compare.
;
; EVERY REGISTER AND THE FLAGS pass through both ways, as through the old
; `call routine / retf` shim, so each routine keeps its own contract. The
; routine's offset is the word after the shim's `call` (CHX), read through CS.
;
; Cost: ~400 clocks a crossing over the old shim's call/retf, ~84 us on a
; 4.77MHz 8088 (82.16.11 counts it); one byte more per shim.
; -----------------------------------------------------------------------------
%ifnmacro CHX 1                     ; the includer may have defined it first,
%macro CHX 1                        ; for shims of its own above this include
    call ch_xthunk
    dw %1
%endmacro
%endif

ch_xthunk:                          ; [sp]: the CHX word, the module's IP, CS
    ; STKBALANCE-OK: its `ret` is a JUMP into the routine through a pushed
    ; slot, and its `retf` the module's own return - both are the design
    push ax                         ; a slot for the routine's address
    pushf
    push bp
    push ax
    mov bp, sp                      ; +6 slot, +8 &word, +10 IP, +12 CS
    mov ax, [bp+12]
    cmp ax, [cs:ch_ovseg]           ; CS, not DS: the thunk is the REGION's,
    mov ax, ch_ovseg                ; DS is whatever the caller left. The TAG
                                    ; is the word naming the module
    je .tag
%ifdef CH_OV2SEG
    mov ax, CH_OV2SEG               ; ...and the only other caller there is
%endif
.tag:
    mov [bp+12], ax
    mov ax, ch_xthunk.back
    xchg ax, [bp+8]                 ; the routine returns to .back; AX = &word
    xchg ax, bp                     ; BP = &word, AX = the frame
    mov bp, [cs:bp]                 ; the routine
    xchg ax, bp
    mov [bp+6], ax                  ; ...into the slot, which the ret takes
    pop ax
    pop bp
    popf
    ret                             ; into the routine: [.back][IP][tag]
.back:                              ; NO FLAG IS TOUCHED from here: the
    push bp                         ; routine's CF is its answer
    mov bp, sp                      ; +2 IP, +4 the tag
    push bx
    mov bx, [bp+4]
    mov bx, [cs:bx]                 ; the module's segment NOW - through CS,
                                    ; whatever DS the routine returned with
    mov [bp+4], bx
    pop bx
    pop bp
    retf

; -----------------------------------------------------------------------------
; The shims apps/os88chart.inc's vectors point at (82.16).
;
; Each is CHX: ch_xthunk calls the real routine, then makes the FAR return the
; module's `call far [ch_v_*]` is waiting for, through the module's segment as
; it is NOW. Registers and flags pass through both ways untouched, so a
; shimmed routine keeps its own contract - which is the whole reason the shim
; exists rather than the vector naming the routine: every routine here is a
; near proc ending in `ret`, and far-calling one pops the offset, leaves the
; segment on the stack and returns into nothing.
;
; ch_s_aiszero is the fused one. The module used to load `bx, fp_am0` itself,
; which is an address in THIS package's bss and exactly what a module shared
; with another package cannot know. The shim supplies it.
; -----------------------------------------------------------------------------
ch_s_unpacka:
    CHX fp_unpack_a
ch_s_unpackb:
    CHX fp_unpack_b
ch_s_a2i:
    CHX fp_a2i
ch_s_cmpab:
    CHX fp_cmpab
ch_s_round:
    CHX fp_round
ch_s_scale10:
    CHX fp_scale10
ch_s_aiszero:
    mov bx, fp_am0
    CHX fp_iszero
ch_s_dec_s16:                         ; apps/os88dec.inc's two, which sheet.asm
    CHX dec_s16                       ; claims for .text because sh_itoa calls
                                      ; dec_s16 near from there (20.5.2)
ch_s_dec_u16:
    CHX dec_u16

; ch_ovreloc - CHART.OVL'S CLAIM MOVED (SPEC.md 66.3, 82.16.11). BX = where it
; was, DX = where it is. The module names no segment of its own - it addresses
; itself through CS and its data through DS, the package's - so the two words
; ch_ovcall and ch_xthunk read are the whole of it.
ch_ovreloc:
    mov [ch_ovseg], dx
    mov [ch_ovfar+2], dx
    ret

; ch_ovbind - fill the vector table: this package's shim offsets, and this
; package's segment. The offsets are assembled in; only the segment is a
; runtime fact, and it is the same one for all of them.
ch_ovbind:
    push ax
    push bx
    push si
    push di
    mov si, ch_ovshims
    mov di, ch_v_first
    mov ax, cs
    mov bx, 9                         ; ch_ovshims' length, and ch_v_*'s
.l:
    push ax
    mov ax, [si]
    mov [di], ax                      ; the shim's offset...
    pop ax
    mov [di+2], ax                    ; ...and our own segment
    add si, 2
    add di, 4
    dec bx
    jnz .l
    pop di
    pop si
    pop bx
    pop ax
    ret

ch_ovshims:
    dw ch_s_unpacka, ch_s_unpackb, ch_s_a2i, ch_s_cmpab
    dw ch_s_round, ch_s_scale10, ch_s_aiszero
    dw ch_s_dec_s16, ch_s_dec_u16     ; ...in ch_v_*'s own order, below

; -----------------------------------------------------------------------------
; ch_ovneed - make sure CHART.OVL is loaded.
; out: CF=0 with [ch_ovseg] holding it; CF=1 and [ch_ovfail] set. Preserves
; every register, because it sits under calls whose arguments are in them.
; A failure is remembered, not retried (sh_m2need's rule): every formula door
; comes through here, and a repaint must not re-claim 51KB per cell. A file
; whose stamp (the host's CH_OVSTAMP: CH_OVLEN, then os88_image_end) is not
; THIS build's is refused the same way - it would read our bss at stale
; offsets and return through a vector table laid out for another build.
;
; REFUSAL IS AN ORDINARY PATH (SPEC.md 47): no heap, or a disk without the
; file, and the chart simply does not draw. The caller sees CF=1 and says so
; in its own voice - this include has no toast of its own and should not grow
; one, because the two packages report differently.
; -----------------------------------------------------------------------------
ch_ovneed:
    cmp word [ch_ovseg], 0
    jne .ok
    cmp byte [ch_ovfail], 0
    jne .fail
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    call OSAPI_FILE_HERE            ; where the USER is, to be put back
    mov [ch_ovwas], dx
    mov [ch_ovwdr], bl
    mov dx, [ch_ovdir]              ; ...and off to where we were launched
    mov bl, [ch_ovdrv]
    call OSAPI_FILE_GOTO
    mov ax, CH_OVKB
    call OSAPI_MEM_CLAIM
    jc .nomem
    mov [ch_ovseg], dx
    mov word [ch_ovfar], 0          ; the dispatcher is at the claim's 0
    mov [ch_ovfar+2], dx
    mov es, dx
    xor bx, bx
    mov cx, CH_OVKB * 1024
    xor dx, dx
    mov si, ch_ovname
    call OSAPI_FILE_READ
    jc .noread
    mov ax, [es:CH_OVSTAMP]         ; THIS build's module, or none
    cmp ax, CH_OVLEN
    jne .noread
    mov ax, [es:CH_OVSTAMP + 2]
    cmp ax, os88_image_end
    jne .noread
    mov dx, [ch_ovseg]              ; READ AND CHECKED: now it may move
    mov ax, ch_ovreloc              ; (82.16.11). Not before - the read holds
    call OSAPI_MEM_MOVABLE          ; ES:BX into it - and a refusal only leaves
                                    ; it pinned, which is what it was
    call ch_ovback
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
.ok:
    clc
    ret
.noread:
    mov dx, [ch_ovseg]              ; the claim goes back: a half-loaded
    call OSAPI_MEM_FREE             ; module is worse than none
    mov word [ch_ovseg], 0
.nomem:
    mov byte [ch_ovfail], 1
    call ch_ovback
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
.fail:
    stc
    ret

; ch_ovback - put the volume back where the user left it. Preserves all.
ch_ovback:
    push bx
    push dx
    mov dx, [ch_ovwas]
    mov bl, [ch_ovwdr]
    call OSAPI_FILE_GOTO
    pop dx
    pop bx
    ret

%endif

%ifdef CH_OVERLAY
; -----------------------------------------------------------------------------
; ch_ovcall - far-call the module.
; in:  BP = the verb (CHM_*), everything else as that verb documents
; out: as the verb; CF=1 if the module could not be loaded at all.
;
; BP carries the verb because none of the four entry points takes it as an
; argument - ch_scale wants DX/SI/DI/CX, ch_bmp_write ES/BX/SI - so it is the
; one register free to say WHICH without disturbing what they were handed.
; -----------------------------------------------------------------------------
ch_ovcall:
    call ch_ovneed
    jc .no
    call far [ch_ovfar]             ; the dispatcher is at the claim's offset
.no:                                ; 0, so the far pointer is (0, the claim)
    ret

ch_ovname:  db 'CHART.OVL', 0
%endif
