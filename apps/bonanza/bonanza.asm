; BONANZA - Bounce Bonanza, an isometric rolling-ball game for os8088.
; Contract: SPEC.md 128 (the plan: docs/plans/BOUNCE-BONANZA-PLAN.md).
;
; WAVE 0 IS THE ENGINE SPIKE (SPEC.md 128): a ball rolled over a generated
; isometric test course that HARDWARE-SCROLLS IN BOTH DIRECTIONS on the CGA
; (FSXM_CGA320) and the Hercules (FSXM_HERC with Excitebike's 200-line
; pair-pixel field, SPEC.md 102.7.1), the 64-frame phase-torus ball, and the
; instruments that price a frame.  No heightfield physics, obstacles, sound or
; game rules yet.
;
; This file is the header, the window and its desktop face (SPEC.md 128.1,
; 128.6, 128.14.3): the title, the keys, the adapter line, the held log's
; line, the tour's SCORECARD, and after a benchmark the RESULTS page - and the
; game's books: the tour, the best times and BONANZA.DAT (128.14.21).  bzvideo.inc is the bracket, the mode, the retrace wait, the ring
; writers and the boxes (128.2, 128.4); bzgame.inc is the frame loop, the
; simulation, the camera, the autopilot and the instruments (128.4 - 128.6).
; Nothing here is a reference game's: the ball is tools/bonanza_assets.py's
; (128.3) and the courses are text compiled by tools/bbcourse.py (128.10.4),
; generated into build/bonanza-art/ and carried as 3 + BZ_NCRS PARTS: three
; balls and one part a course, every one the CGA's (SPEC.md 128.11.3.1).
%include "os88api.inc"
OS88_HEADER 'BONANZA', bz_entry, OS88_F_ICON | OS88_F_ASSOC | OS88_F_GLYPH | OS88_F_PARTS, OS88_STACK_256 | OS88_HIGH | OS88_HIGHMEM
OS88_ICON16
    dw 0x07e0,0x1ff8,0x3ffc,0x7ffe,0x7ffe,0xffff,0xffff,0xffff
    dw 0xffff,0xffff,0xffff,0x7ffe,0x7ffe,0x3ffc,0x1ff8,0x07e0
    dw 0x07e0,0x1818,0x2004,0x4002,0x4c02,0x8c01,0x8001,0x8061
    dw 0x8061,0x8001,0x8c03,0x4c06,0x400e,0x203c,0x1ff8,0x07e0
OS88_ICON16_END
; a recorded demo, *.BZR, is BONANZA's document (SPEC.md 128.14.7.5, 54.6): a
; double-click launches BONANZA with it, and its page wears a ball and its
; bounce (54.3.2)
OS88_ASSOC16
    db 1
    OS88_ASSOC_EXT 'BZR'
OS88_ASSOC16_END
OS88_DOCGLYPH8
    db 00000110b
    db 00001111b
    db 01001111b
    db 00000110b
    db 10000000b
    db 00100000b
    db 01010101b
    db 00000000b
OS88_DOCGLYPH8_END
; The art files are PARTS of this file (SPEC.md 128.11.3.1, 20.12), every one
; lazy and compressed: only the play's course and ball are ever read, on the
; DESKTOP before the bracket (so op_fetch's refusal toast can be drawn), the
; course's stored form is expanded in place there (bz_cexp, SPEC.md
; 128.15.4.5), the Hercules translates both in place after it (bz_hxlat), and
; both are dropped when the bracket returns (SPEC.md 128.7, 128.11.3).
%define OP_NO_LAZYOK            ; (the fetch itself asks; no pre-check is used)
%include "os88parts.inc"
%include "bzconst.inc"          ; the ball part's layout (tools/bonanza_assets.py)
%include "bzcourse.inc"         ; the courses and their part rows (tools/bbcourse.py)
%include "bzsnd.inc"            ; the songs and the events (tools/bbmusic.py)
%include "drivers/sound/sndpkg.inc" ; SOUND.DRV's FM door (bzsound.inc), from the root
                                ; as every bonanza row assembles it

%macro SAVE 0
 push ax
 push bx
 push cx
 push dx
 push si
 push di
 push bp
 push es
%endmacro
%macro RESTORE 0
 pop es
 pop bp
 pop di
 pop si
 pop dx
 pop cx
 pop bx
 pop ax
%endmacro

BZ_LH       equ 10              ; the face's line pitch: an 8px cell and 2px of air
BZ_LMAX     equ 88              ; the longest padded line (a 720px Hercules content box)

; --- the part rows: the Makefile's BZ_PARTS order (SPEC.md 128.11.3.1) ---------
BZ_P_BALR   equ 0               ; BZBALR.BIN  the rubber ball: a material's row
BZ_P_BALS   equ 1               ; BZBALS.BIN  is BZ_P_BALR + the material
BZ_P_BALG   equ 2               ; BZBALG.BIN
                                ; course K: BZ_P_CRS + K, bzcourse.inc's rows

; --- the course part's header (BZC2: SPEC.md 128.15.4.1, 128.10.5.2) -----------
; Byte offsets from the part's first byte; the grid's from GRIDOFF.  Nothing
; here is checked on the guest: tools/bbcourse.py checked every one of them at
; build time (SPEC.md 128.10.6.2).  BZC1's fields keep their offsets; the map
; moved from +32 to +48 behind BZC2's own (128.15.4.1).
BZC_COLS    equ 4               ; word columns: 64 or 128
BZC_BROWS   equ 6               ; block rows
BZC_NBLK    equ 8               ; N, blocks (bz_hxlat)
BZC_MAPSH   equ 10              ; 4 for 64 columns, 5 for 128
BZC_BLKOFF  equ 12              ; block 0's offset (bz_hxlat, bz_cexp)
BZC_OCCIDX  equ 14              ; OCCIDX: BROWS + 1 words, each the offset of
                                ; the block row's first occluder record
BZC_OCCREC  equ 16              ; the first record (bz_cexp's COUNTS)
BZC_MASKOFF equ 20              ; mask 0 (D's MASKTAB read it; D was deleted, 128.15.5.3)
BZC_NMASK   equ 22              ; the masks
BZC_ROWB    equ 24              ; 2 COLS: the map row's byte stride, READ by the
                                ; column writer through DS = the part (128.10.6.4)
BZC_GRID    equ 26              ; GRIDOFF
BZC_PROPOFF equ 28              ; the prop table (SPEC.md 128.12.3.1): its first
BZC_NPROP   equ 30              ; record, and the records (0: none)
BZC_RECB    equ 32              ; byte: the record's size in RAM, 4 or 8
BZC_SB      equ 33              ; signed byte: the s bias (0 when RECB is 8)
BZC_TB      equ 34              ; the top bias, signed px (0 when RECB is 8)
BZC_MTAB    equ 36              ; the mask table (0 when RECB is 8)
BZC_DIROFF  equ 38              ; the section directory (SPEC.md 128.15.4.2):
BZC_NSEC    equ 40              ; its offset and its 8-byte entries
BZC_MAP     equ 48              ; the map: COLS x BROWS words, absolute offsets
BZX_FORM    equ 1               ; (a directory entry's) byte: its stored form
BZX_OFF     equ 2               ; its RAM offset
BZX_LEN     equ 4               ; its RAM length
BZX_DLEN    equ 6               ; its STORED length, at the end of its slot
BZX_ENTB    equ 8               ; an entry's size (BZX_: not BONANZA.DAT's BZD_)
BZG_NROWS   equ 4               ; (at GRIDOFF +) the rows
BZG_SMIN    equ 6               ; row 0's s = wx + wy
BZG_AMIN    equ 8               ; signed, even: the first cell's a = wx - wy
BZG_KW      equ 10              ; cells a row
BZG_ROWTAB  equ 12              ; ROWTAB's offset: a row's first cell
BZG_X0      equ 14              ; px
BZG_Y0      equ 16              ; signed px
BZG_ID      equ 18              ; the course's IDENTITY (SPEC.md 128.12.8)
BZG_WX      equ 20              ; the start tile
BZG_WY      equ 22
BZG_NWAY    equ 24              ; the route: NWAY pairs of words, the ball's
BZG_ROUTE   equ 26              ; picture top-left (px), at this offset
; --- the ball part's header (BZB2, SPEC.md 128.11.9.1); its layout is
; bzconst.inc's BZ_BAL_* -------------------------------------------------------
BZB_NSHA    equ 12              ; byte: shatter frames, 4 for glass, else 0
; --- the replay log's header (SPEC.md 128.11.12.1), in [bz_rlog] ---------------
BZR_CRS     equ 4               ; byte: the course K
BZR_MAT     equ 5               ; byte: the material
BZR_FLAGS   equ 6               ; byte: bit 0 COMPLETE, bit 1 TRUNCATED, bit 2
                                ; TILT (runs of three bytes, SPEC.md 128.14.8.3)
BZR_PHYS    equ 7               ; byte: the PHYSICS identity BZ_PHYSV (128.14.7.2)
BZR_STEPS   equ 8               ; DWORD: the steps recorded
BZR_NRUN    equ 12              ; word: the runs recorded
BZR_ID      equ 14              ; word: the course's identity (128.12.8)
BZR_RUNS    equ 16              ; the runs: (key byte, count 1 - 255) pairs, or
                                ; with TILT (key byte, tilt byte, count) triples
BZR_SIZE    equ 4096            ; the log, bz_rlog: at most 2,040 runs (1,360 TILT)
BZR_DONE    equ 1
BZR_TRUNC   equ 2
BZR_TILT    equ 4               ; (bzcourse.inc's BZ_RL_TILT, the tool's)
%if BZR_TILT != BZ_RL_TILT || (BZR_SIZE - BZR_RUNS) % 6
 %error "the log's TILT flag is +6 bit 2, and both run widths fill bz_rlog exactly"
%endif
BZ_P_DEMO   equ BZ_P_SONG + BZS_NSONG ; shipped demo K (1 - 5): BZ_P_DEMO + K - 1
; --- the game (SPEC.md 128.14.3) ------------------------------------------------
BZ_NTOUR    equ BZ_NCRS - 1     ; the TOUR: courses 1 .. BZ_NCRS - 1, in order
BZ_TOURMAX  equ BZ_NTOUR * 65534 ; a tour's total a file may hold: each under
                                ; the 65,535-step clamp (128.14.3.3)
; --- BONANZA.DAT (SPEC.md 128.14.3.3): SYSTEM\APPDATA, 64 bytes, in [bz_dat] ---
BZD_SIZE    equ 64              ; `BZT1`, +4 the course count, +5 three zeros
BZD_ENT     equ 8               ; 8 entries, K 0 - 7 (BENCH's unused): +0 the
BZD_ENTB    equ 6               ; course's IDENTITY, +2 its best in STEPS (0
BZD_NENT    equ 8               ; none), +4 that best's falls
BZD_TOUR    equ 56              ; the tour: +0 the XOR of its courses' identities,
                                ; +2 its best total in steps, DWORD, +6 zero
%if BZD_ENT + BZD_NENT * BZD_ENTB != BZD_TOUR || BZD_TOUR + 8 != BZD_SIZE || BZ_NCRS > BZD_NENT
 %error "BONANZA.DAT's layout (SPEC.md 128.14.3.3) holds 8 courses"
%endif

bz_entry:
    push es                     ; op_load spends ES, which arrives KERNEL_SEG
    call op_load                ; SI is still the kernel's name: FIRST. Every
    pop es                      ; row is lazy, so this copies the name and
    jc .out                     ; claims nothing
    call bz_argget              ; a double-clicked document's name, copied out
                                ; while ES is still the kernel's (128.14.7.5)
    mov si, bz_tpl
    call OSAPI_WM_CREATE        ; ...and AL = the class slots this kernel
    jc .out                     ; dispatches (SPEC.md 11.104): no timer slot
    cmp al, WC_ONTIMER + 1      ; is kern_small, the 128KB machine, which
    sbb al, al                  ; refuses the bracket (SPEC.md 128.1)
    neg al
    mov [bz_small], al
    mov [bz_win], bx
    call OSAPI_FILE_HERE        ; where BONANZA.O88 was launched from (SPEC.md
    mov [bz_homedir], dx        ; 128.14.7.6): BONANZA.DAT's volume, whatever
    mov [bz_homevol], bl        ; a dialog does to the instance later
    call bz_dload               ; the best times (128.14.3.3); kern_small: none
    mov byte [bz_crsel], BZ_CRS_FIRST ; the course Enter plays, and its ball
    mov al, [bz_cballs + BZ_CRS_FIRST] ; (N and M change them, SPEC.md
    mov [bz_matsel], al         ; 128.11.5.4)
    OS88_REGION_MOVABLE
    OS88_ALTENTER_ARM
    call bzs_dstart             ; the title's music (SPEC.md 128.20.6)           ; (also the ask 128.11.11.2 owes at the open:
                                ; asking arms SPEC.md 9.7's map, so the held-
                                ; key guard sees every key pressed after it)
    mov bx, [bz_win]            ; (a double-clicked .BZR is READ in W_ONWAKE,
    clc                         ; once the window is up: SPEC.md 54.10)
.out: ret

; -----------------------------------------------------------------------------
; the window's callbacks.  ES = KERNEL_SEG on entry to every one of them.
; -----------------------------------------------------------------------------
bz_paint:
    SAVE
    call bz_face
    cmp byte [bz_abon], 0
    je .done
    mov bx, [bz_win]
    mov si, bz_credits
    call os88ui_about_d
.done:
    RESTORE
    ret

bz_about:
    SAVE
    mov byte [bz_abon], 1
    mov bx, [bz_win]
    mov si, bz_credits
    call os88ui_about
    RESTORE
    ret

bz_click:
    SAVE
    cmp byte [bz_abon], 0
    je .done
    mov byte [bz_abon], 0
    call bz_repaint
.done:
    RESTORE
    ret

bz_onkey:
    SAVE
    cmp byte [bz_abon], 0
    je .key
    mov byte [bz_abon], 0
    call bz_repaint
    jmp .done
.key:
    mov cl, [bz_page]           ; a key on the RESULTS page is acted on as on
    mov byte [bz_page], 0       ; MAIN and returns the face to it (SPEC.md
    mov [bz_pgo], cl            ; 128.14.3.2): repainted whole at .done
    cmp ax, KEY_ALTENTER
    je .play
    cmp al, 13
    je .play
    cmp al, 27
    je .esc
    or al, 20h
    cmp al, 'f'
    je .play
    call bz_intour              ; A TOUR withholds every key that would replace
    jc .tour                    ; its state or its log (128.14.3.4)
    mov bx, bz_game
    cmp al, 'g'
    je .held
    cmp al, 'b'
    je .bench
    cmp al, 'r'
    je .replay
    mov bx, bz_ballkey          ; C, M, N, G, D, L, V, W, T: one press however
    cmp al, 'm'                 ; long it is held (SPEC.md 128.11.11.2,
    je .held                    ; 128.14.3.4)
    mov bx, bz_crskey
    cmp al, 'n'
    je .held
    mov bx, bz_dkey_d           ; D: the demo benchmark (128.14.7.3)
    cmp al, 'd'
    je .held
    mov bx, bz_lkey             ; L: load a demo (128.14.7.2)
    cmp al, 'l'
    je .held
    mov bx, bz_vkey             ; V: the next shipped demo (128.14.7.4)
    cmp al, 'v'
    je .held
.tour:
    mov bx, bz_camkey
    cmp al, 'c'
    je .held
    mov bx, bz_wkey             ; W: save the held log (128.14.7.1)
    cmp al, 'w'
    je .held
    mov bx, bz_tkey             ; T: the control, KEYS or MOUSE (128.14.8)
    cmp al, 't'
    je .held
    mov bx, bz_skey             ; S: the sound (SPEC.md 128.20.4), at home
    cmp al, 's'
    jne .done
.held:
    call bz_dkey                ; AH = the make code: CF = 1 a repeat, swallowed
    jc .done
    call bx
    jmp short .done
.esc:
    call bz_intour              ; Esc on the face between two tour courses
    jnc .done                   ; STOPS the tour (otherwise nothing, as before)
    mov byte [bz_tour], BZ_NTOUR + 2
    mov si, bz_stopl
    call bz_redraw
    jmp short .done
.replay:
    call bz_rhave               ; R: offered only when there is a log
    jne .done                   ; (SPEC.md 128.11.12.2): its course, and
    mov ah, [bz_rlog + BZR_CRS] ; bz_launch takes its ball
    mov al, 2
    jmp short .go
.bench:
    mov ax, 1 | (BZ_CRS_BENCH << 8) ; B: the benchmark, on BENCH (SPEC.md
    jmp short .go               ; 128.10.11.1)
.play:
    call bz_intour              ; Enter, F, Alt+Enter: in a tour its next
    jnc .free                   ; course
    call bz_tgo
    jmp short .done
.free:
    mov al, 0                   ; ...otherwise play the selected course
    mov ah, [bz_crsel]          ; freely (SPEC.md 128.11.11.3)
.go:
    call bz_go
.done:
    cmp byte [bz_pgo], 0        ; leaving RESULTS: MAIN whole, unless a bracket
    je .out                     ; ran (the kernel's restore painted it)
    mov byte [bz_pgo], 0
    call bz_repaint
.out:
    RESTORE
    ret

; G (one press, bz_dkey): a NEW TOUR (SPEC.md 128.14.3.1) - its times cleared
; and course 1 launched.  On kern_small nothing changes: bz_launch toasts the
; refusal (128.1).
bz_game:
    cmp byte [bz_small], 0
    jne bz_tgo
    xor ax, ax
    mov bx, bz_ttime
.z:
    mov [bx], ax
    inc bx
    inc bx
    cmp bx, bz_tfall + 2 * BZ_NTOUR
    jb .z
    mov byte [bz_tour], 1
    call bz_tgo
    cmp byte [bz_tour], 1       ; still course 1: its launch was REFUSED (a
    jne .ran                    ; course that ran moved the tour on, or Esc
    mov si, bz_stopl            ; stopped it), so no bracket repainted the face
    jmp bz_redraw               ; and the tour's lines are drawn here
.ran:
    ret
; the tour's next course, played with its own ball (bz_launch); a refused
; launch leaves the tour where it was, so Enter tries it again
bz_tgo:
    mov ah, [bz_tour]
    mov al, 0
; AL = the mode, AH = the course: launched, and a best it set saved
bz_go:
    mov [bz_mode], al
    mov [bz_crs], ah
    call bz_launch
    jmp bz_dsave

; bz_dkey - the held-key guard (SPEC.md 128.11.11.2), AH = a typed key's make
; code.  The key's typematic repeats arrive as typed keys too, and an interval
; test cannot see the typematic DELAY, so the fact asked is whether the key
; came UP: while [bz_dkk] is this key's code it has not, and the key is
; SWALLOWED (CF = 1).  Else it is a press (CF = 0): [bz_dkk] takes its code and
; the window's timer is armed for a tick, whose handler (bz_ontimer) asks
; OSAPI_KEY_DOWN.  With no timer (kern_small answers CF = 1) there is no guard.
; Preserves all but AX and the flags.
bz_dkey:
    cmp ah, [bz_dkk]
    stc
    je .out
    mov [bz_dkk], ah
    push bx
    mov bx, [bz_win]
    mov ax, 1
    call OSAPI_WM_TIMER
    pop bx
    jnc .out
    mov byte [bz_dkk], 0
    clc                         ; a press
.out:
    ret

; the window's timer (WC_ONTIMER, SPEC.md 13.9): is [bz_dkk] still down?
; Down, ask again in a tick; up, the next typed key of it is a press
bz_ontimer:
    SAVE
    call bzs_dtick              ; the title (re-arms the timer while it plays)
    mov al, [bz_dkk]
    or al, al
    jz .done
    call OSAPI_KEY_DOWN
    jnc .up
    mov bx, [bz_win]
    mov ax, 1
    call OSAPI_WM_TIMER
    jmp .done
.up:
    mov byte [bz_dkk], 0
.done:
    RESTORE
    ret

; ZF = 1 when [bz_rlog] holds a log (the recorder's signature, SPEC.md
; 128.11.12.1).  The log is the package's own bss, written by the package:
; trusted, not checked (128.11.12.2).  Preserves all but the flags.
bz_rhave:
    cmp word [bz_rlog], 'BZ'
    jne .out
    cmp word [bz_rlog + 2], 'R1'
.out:
    ret

; the window repainted outside a paint: arm the clip first (SPEC.md 11.3)
bz_repaint:
    mov bx, [bz_win]
    call OSAPI_WM_CLIP_SET
    jc .out
    call bz_paint
.out:
    ret

; -----------------------------------------------------------------------------
; bz_adapter - what this window's display is: AL = 1 CGA, 2 Hercules, 0 neither
; (or no FSX mode for it).  Preserves all but AX and the flags.
; -----------------------------------------------------------------------------
bz_adapter:
    push bx
    push dx
    mov bx, [bz_win]
    call OSAPI_FSX_CAPS
    jc .none
    cmp dl, VID_CGA
    jne .herc
    test ax, 1 << FSXM_CGA320
    jz .none
    mov al, 1
    jmp .out
.herc:
    cmp dl, VID_HERC
    jne .none
    test ax, 1 << FSXM_HERC
    jz .none
    mov al, 2
    jmp .out
.none:
    xor al, al
.out:
    pop dx
    pop bx
    ret

; -----------------------------------------------------------------------------
; bz_launch - the desktop side of a play, a benchmark or a replay: every
; refusal is here, where a toast can still be drawn (SPEC.md 128.1, 128.7).
; In: [bz_mode] (0 play, 1 benchmark, 2 replay, 3 the demo benchmark: a
; replay, measured, SPEC.md 128.14.7.3) and [bz_crs].  The MATERIAL is
; chosen here (SPEC.md 128.11.5.4): a play rolls the session's ball
; ([bz_matsel], M), a benchmark the course's own (BENCH's for B; the course a
; harness poked at this entry otherwise), a replay the log's.  Course K's part
; (row BZ_P_CRS + K) and the material's (BZ_P_BALR + [bz_mat]) are fetched -
; the same rows on both cards - the course's expanded in place at once
; (bz_cexp, SPEC.md 128.15.4.5), and on the Hercules both are translated in
; place (bz_hgen, bz_hxlat, SPEC.md 128.11.3); the bracket runs, and both are
; dropped on every way out.  Every fetch here - the course's, the balls', the
; sound's song and the title's after the bracket - is made at HOME (bz_home,
; SPEC.md 128.14.7.6), and the instance goes back where the user was after.
; -----------------------------------------------------------------------------
bz_launch:
    mov byte [bz_newb], 0       ; (only this launch's play may set a best)
    cmp byte [bz_small], 0
    je .big
    mov si, bz_t_small          ; kern_small: the parts are more heap than the
    jmp bz_toast                ; 128KB machine has
.big:
    call bz_adapter
    or al, al
    jnz .ok
    mov si, bz_t_adapt          ; VGA, EGA, MDA: CGA OR HERC ONLY
    jmp bz_toast
.ok:
    dec al
    mov [bz_herc], al
    mov al, [bz_matsel]         ; the material (above)
    mov bl, [bz_mode]
    dec bl
    jns .nplay
    call bz_intour              ; 0: a play, M's - but a TOUR's course rolls
    jnc .mat                    ; its own (SPEC.md 128.14.3.1)
    jmp short .own
.nplay:
    mov al, [bz_rlog + BZR_MAT]
    jnz .mat                    ; 2, 3: a replay, the log's
.own:
    mov bl, [bz_crs]            ; 1: a benchmark, the course's own
    xor bh, bh
    mov al, [bz_cballs + bx]
.mat:
    mov [bz_mat], al
    call bz_home                ; every part is read out of BONANZA.O88 at home
    jc .ret                     ; (its refusal toasted: no fetch at all)
    call .home
    jmp bz_back
.ret:
    ret
.home:
    mov al, [bz_crs]            ; course K's row: BZ_P_CRS + K (bzcourse.inc)
    add al, BZ_P_CRS
    mov [bz_pc], al
    call op_fetch               ; claim, read, expand - or a toast said why
    jc .out
    mov al, [bz_pc]             ; (each fetch's segment stored before the next
    call op_seg                 ; fetch, so tests/pins.txt keys each claim by
    mov [bz_cseg], ax           ; its own word: bz_cseg, bz_bsegs)
    call bz_cexp                ; the STORED form expanded in place, ONCE: this
                                ; fetch decoded, every exit below dropping the
                                ; part (SPEC.md 128.15.4.5)
    push es                     ; THE BALLS (wave 4, SPEC.md 128.14.4.4): the
    mov es, [bz_cseg]           ; starting one and every one the course's
    mov di, [es:BZC_GRID]       ; PAD MASK names (BZG1 +29), up to three, each
    mov ah, [es:di + BZG_PADS]  ; its own claim - and every FLAG's own ball,
    mov si, [es:BZC_PROPOFF]    ; which a respawn there gets (bz_rflag) whether
    mov dx, [es:BZC_NPROP]      ; or not a pad gives it
.fb:
    dec dx
    js .fb2
    cmp byte [es:si + BZP_KIND], BZ_PK_CKPT
    jne .fb1
    mov cl, [es:si + BZP_CBALL]
    mov al, 1
    shl al, cl
    or ah, al
.fb1:
    add si, BZ_PROPREC
    jmp short .fb
.fb2:
    pop es
    mov cl, [bz_mat]
    mov al, 1
    shl al, cl
    or ah, al
    mov [bz_pbm], ah
    mov byte [bz_pb], BZ_P_BALR
.ball:
    mov cl, [bz_pb]
    sub cl, BZ_P_BALR
    mov al, 1
    shl al, cl
    test al, [bz_pbm]
    jz .nball
    mov al, [bz_pb]
    call op_fetch
    jc .drop
    mov al, [bz_pb]
    call op_seg
    mov bl, [bz_pb]
    sub bl, BZ_P_BALR
    xor bh, bh
    shl bx, 1
    mov [bz_bsegs + bx], ax
.nball:
    inc byte [bz_pb]
    cmp byte [bz_pb], BZ_P_BALR + BZ_NMAT
    jb .ball
    mov bl, [bz_mat]            ; the sprite's: the starting ball's (a pad or
    xor bh, bh                  ; a flag's respawn changes it, bz_setmat)
    lea ax, [bx + BZ_P_BALR]
    mov [bz_pb], al
    shl bx, 1
    mov ax, [bz_bsegs + bx]
    mov [bz_bseg], ax
    push es                     ; the title off, the course's song fetched
    call bzs_gfetch             ; (none had: a SILENT play, SPEC.md 128.20.6)
    pop es
    call bz_crshdr              ; the course's header, copied into our data
    cmp byte [bz_mode], 2       ; a REPLAY (R or D) of a log made on another
    jb .idok                    ; course (a re-seeded one: its identity
    push es                     ; differs) is refused, and the face says so
    mov es, [bz_cseg]           ; (SPEC.md 128.12.8) - and one made under
    mov di, [bz_goff]           ; other PHYSICS (+7, 128.14.7.2)
    mov ax, [es:di + BZG_ID]
    pop es
    mov byte [bz_err], 3
    cmp ax, [bz_rlog + BZR_ID]
    jne .drop
    inc byte [bz_err]
    cmp byte [bz_rlog + BZR_PHYS], BZ_PHYSV
    jne .drop
.idok:
    cmp byte [bz_herc], 0       ; the Hercules's parts are the CGA's through
    je .run                     ; BZ_HTAB, made here (SPEC.md 128.11.3)
    push es                     ; (ES as the bracket call found it before:
    call bz_hgen                ; bz_hxlat leaves the ball's there)
    call bz_hxlat
    pop es
.run:
    mov byte [bz_err], 0
    mov bx, [bz_win]
    mov ax, bz_fullscreen
    mov cx, FSXF_FASTTICK
    call OSAPI_FSX_RUN
    jc .nofs
    mov byte [bz_pgo], 0        ; the kernel's restore painted the face whole
    jmp short .drop
.nofs:
    mov si, bz_t_nofs
    call bz_toast
.drop:
    push ds                     ; ES = ours, not whatever the bracket left:
    pop es                      ; op_drop restores its caller's ES after the
                                ; free, and on kern_mega a part's own selector
                                ; there is a #GP once its claim is gone (the
                                ; final pass of wave 1: bonanzamega's fault at
                                ; op_drop's POP ES, the ball's selector in ES)
    mov al, BZ_P_BALR           ; every ball row and the course's (op_drop
.dball:                         ; of a part that is not here is a no-op, so
    call op_drop                ; all go whichever failed; it preserves AX)
    inc ax
    cmp al, BZ_P_BALR + BZ_NMAT
    jb .dball
    mov al, [bz_pc]
    call op_drop
    xor ax, ax
    mov [bz_bsegs], ax
    mov [bz_bsegs + 2], ax
    mov [bz_bsegs + 4], ax
    mov [bz_cseg], ax
    mov [bz_bseg], ax
    call bzs_gdrop              ; the song back, and the title (a finish's
    cmp byte [bz_err], 3        ; fanfare first, SPEC.md 128.20.6); no bracket
    jb .out                     ; ran: the face repainted with the refusal (3
    mov byte [bz_pgo], 1        ; or 4), by bz_onkey (once, whatever page it
.out:                           ; was on)
    ret

; -----------------------------------------------------------------------------
; bz_crshdr - the fetched course part's header, copied into our data (SPEC.md
; 128.10.6.4, 128.10.8 item 4): the writers' map shift and stride, the camera's
; limits' inputs, the grid's place, X0 and Y0 (and the projection's
; constants physics derives the screen position with), and the route.  The
; start is physics's (bzphys.inc bz_pinit).  Nothing is checked: the part was
; checked when it was built (128.10.6.2).  DS = ours, [bz_cseg] the course.
; Preserves nothing.
; -----------------------------------------------------------------------------
bz_crshdr:
    push es
    mov es, [bz_cseg]
    mov ax, [es:BZC_COLS]
    mov [bz_cols], ax
    mov ax, [es:BZC_BROWS]
    mov [bz_brows], ax
    mov al, [es:BZC_MAPSH]
    mov [bz_mapsh], al
    mov ax, [es:BZC_ROWB]
    mov [bz_rowb], ax
    mov di, [es:BZC_GRID]
    mov [bz_goff], di
    mov ax, [es:di + BZG_X0]
    mov [bz_x0], ax
    mov ax, [es:di + BZG_Y0]
    mov [bz_y0], ax
    mov ax, [es:di + BZG_NWAY]
    mov [bz_nway], ax
    mov ax, [es:di + BZG_ROUTE]
    mov [bz_wayoff], ax
    mov ax, [bz_x0]             ; the projection's constants, 24.8 (128.10.8):
    sub ax, 8                   ; bz_kx = (X0 - 8) << 8 ...
    call .k
    mov [bz_kx], ax
    mov [bz_kx + 2], dx
    mov ax, [bz_y0]             ; ...bz_ky = (Y0 - 13) << 8, Y0 signed
    sub ax, 13
    call .k
    mov [bz_ky], ax
    mov [bz_ky + 2], dx
    pop es
    ret
; AX (signed) -> DX:AX = AX << 8
.k:
    mov dl, ah                  ; DL = the high byte
    mov ah, al
    xor al, al                  ; AX = the low word
    xchg ax, dx
    cbw                         ; (AL = that high byte) AX = the high word
    xchg ax, dx
    ret

; -----------------------------------------------------------------------------
; bz_cexp - THE COURSE PART EXPANDED IN PLACE (SPEC.md 128.15.4.4, 128.15.4.5),
; right after the fetch that DECODED it and before anything reads it.  The
; part is BZC2's STORED form: each section's slot [off, off + len) holds a
; zero hole and then its dlen stored bytes; the directory (the part's last
; 8 NSEC bytes) names each section's form.  The walk takes the entries in
; order, which is also the order the forms depend on (ROWTAB reads G, WAYS
; reads G, C and T, all before it).  Each form runs FORWARD through its own
; slot and never reaches a stored byte it has not read (the tool's in-place
; proof, --selfcheck item 10), and every loop counts with a field of the
; header, of BZG1 or of its own entry, never with a byte it is expanding.
; NOT idempotent (WDIFF adds), so it runs exactly once a decoding fetch: the
; caller drops the part on every way out, so every fetch decodes.  The
; Hercules translates AFTER it (bz_hgen's table lives in bz_boxbuf, which
; ROWPLANES and CELLS use as scratch first).  The part is read and written through its
; own segment (kern_mega: its LDT selector) in DS or ES, at offsets inside its
; length; nothing through CS, no segment arithmetic (128.15.11).
; DS = ours, [bz_cseg] the part.  Preserves BP, DS, ES.
; -----------------------------------------------------------------------------
bz_cexp:
    push bp
    push es
    cld
    mov es, [bz_cseg]           ; ES = the part (the walk reads it with ES:)
    mov bx, [es:BZC_DIROFF]
    mov cx, [es:BZC_NSEC]
.ent:
    push cx
    push bx
    mov di, [es:bx + BZX_OFF]   ; DI = S, the slot
    mov cx, [es:bx + BZX_LEN]   ; CX = its RAM length
    mov si, di
    add si, cx
    sub si, [es:bx + BZX_DLEN]  ; SI = S + H: its stored bytes
    mov bl, [es:bx + BZX_FORM]
    xor bh, bh
    shl bx, 1
    push ds
    call [bx + bz_cxtab]        ; (DS = ours: the table is ours)
    pop ds
    pop bx
    pop cx
    add bx, BZX_ENTB
    loop .ent
    pop es
    pop bp
    ret

; THE FORMS: SI = the stored bytes, DI = the slot, CX = its RAM length, DS =
; ours, ES = the part.  Each may change DS (bz_cexp restores it), and
; clobbers AX, BX, CX, DX, SI, DI, BP.
bz_cxtab:
    dw bz_cxret                 ; 0 PLAIN: in place already
    dw bz_cxmap                 ; 1 ROWPLANES
    dw bz_cxcnt                 ; 2 COUNTS
    dw bz_cxdif                 ; 3 WDIFF
    dw bz_cxret                 ; 4 MASKTAB: the 4-byte record's (D), not
BZ_CXFORMS  equ 0EFh            ; shipped - C's parts carry no mask table
                                ; (SPEC.md 128.15.5.3, 128.15.5.4's verdict)
    dw bz_cxrtb                 ; 5 ROWTAB
    dw bz_cxway                 ; 6 WAYS
    dw bz_cxcel                 ; 7 CELLS
%if BZ_FORMS & ~BZ_CXFORMS
 %error "bz_cexp: a course part uses a stored form its dispatch table does not hold"
%endif
%if BZ_REC != 8
 %error "bonanza: the occluder pass reads C's 8-byte records (SPEC.md 128.15.5.4); bzcourse.inc's BZ_REC is not 8"
%endif

; 1 ROWPLANES: block row r stored as C/4 high bytes (cell j's two high bits at
; bits 2 (j AND 3) of byte j >> 2) and then C low bytes; map word j = BLKOFF +
; 16 (low + 256 high).  The row's high bytes go to scratch (bz_boxbuf, at most
; 32) first, because the words of a late row overrun them.  COLS and BROWS
; count.
bz_cxmap:
    mov bp, [es:BZC_BLKOFF]
    mov dx, [es:BZC_BROWS]
.row:
    push dx                     ; (the rows left)
    mov cx, [es:BZC_COLS]
    shr cx, 1
    shr cx, 1
    mov dx, cx                  ; DL = C/4: the row's high bytes
    mov bx, bz_boxbuf
.hi:
    es lodsb                    ; ...to scratch, before the words overrun them
    mov [bx], al
    inc bx
    loop .hi
    mov ch, dl                  ; CH = the high bytes left
    mov cl, 4
    mov bx, bz_boxbuf
.grp:
    mov dl, [bx]                ; DL = four cells' high bits
    inc bx
    mov dh, 4
.cell:
    es lodsb                    ; AL = the cell's low byte
    mov ah, dl
    and ah, 3
    shl ax, cl
    add ax, bp
    stosw                       ; BLKOFF + 16 (low + 256 high)
    shr dl, 1
    shr dl, 1
    dec dh
    jnz .cell
    dec ch
    jnz .grp
    pop dx
    dec dx
    jnz .row
bz_cxret:
    ret

; 2 COUNTS: a count byte a block row; OCCIDX[br] = OCCREC + RECB x (the
; records before row br), br = 0 .. BROWS.  BROWS counts.
bz_cxcnt:
    mov dx, [es:BZC_OCCREC]
    mov cx, [es:BZC_BROWS]
    mov ax, dx
.w:
    stosw                       ; word br: it ends before count br's byte
    es lodsb
    mul byte [es:BZC_RECB]      ; (a count is a byte: AX = RECB count)
    add dx, ax
    mov ax, dx
    loop .w
    stosw                       ; word BROWS: OCCREC + RECB NOCC
    ret

; 3 WDIFF: the first record as it is, then each word the difference from the
; same word of the record before.  w[i] += w[i - RECB / 2], forward, so it
; reads only what it has already written.  ONE loop for both strides: RECB
; from the header; the entry's length (RECB NOCC) counts.
bz_cxdif:
    push es
    pop ds                      ; DS = the part
    mov bl, [BZC_RECB]
    xor bh, bh
    add si, bx                  ; (SI = S: stored as long as it is in RAM)
    sub cx, bx
    shr cx, 1                   ; the words after the first record
    jcxz .out                   ; (one record)
    neg bx                      ; BX = -RECB
.w:
    mov ax, [bx + si]
    add [si], ax
    inc si
    inc si
    loop .w
.out:
    ret

; 5 ROWTAB: ROWTAB[r] = GRIDOFF + 32 + 4 KW r, NROWS counts (BZG1, before it)
bz_cxrtb:
    mov bx, [es:BZC_GRID]
    mov cx, [es:bx + BZG_NROWS]
    mov dx, [es:bx + BZG_KW]
    shl dx, 1
    shl dx, 1
    lea ax, [bx + 32]
bz_cxramp:                      ; CX words from AX, DX apart
    stosw
    add ax, dx
    loop bz_cxramp
    ret

; 6 WAYS: each way's tile (wx, wy), a byte each; written as the ball's picture
; top-left on the tile's centre (the tool's rule, 128.10.4.5):
;   x = 16 a + X0 - 8,  y = 8 s - 2 (2 z0 + sx + sy) + Y0 - 5,
; s = wx + wy, a = wx - wy, z0, sx and sy the tile's CELL's, found as
; bzphys.inc finds a cell: ROWTAB[s - SMIN] + 4 ((a - AMIN) >> 1).  NWAY
; counts; way w's words end before way w + 1's stored pair.
bz_cxway:
    push es
    pop ds                      ; DS = ES = the part
    mov bx, [BZC_GRID]
    mov cx, [bx + BZG_NWAY]
.way:
    push cx
    lodsw                       ; AL = wx, AH = wy
    mov cl, ah
    xor ch, ch
    xor ah, ah
    mov dx, ax
    add dx, cx                  ; DX = s
    sub ax, cx                  ; AX = a
    mov bp, ax
    mov cl, 4
    shl ax, cl
    add ax, [bx + BZG_X0]
    sub ax, 8
    stosw                       ; x
    sub bp, [bx + BZG_AMIN]
    and bp, byte -2
    shl bp, 1                   ; BP = 4 k
    mov ax, dx
    sub ax, [bx + BZG_SMIN]
    shl ax, 1
    add ax, [bx + BZG_ROWTAB]
    push si
    xchg ax, si
    mov si, [si]                ; ROWTAB[r]
    add si, bp
    lodsw                       ; AL = z0, AH = sy : sx (signed nibbles)
    pop si
    mov ch, ah
    sar ch, cl                  ; CH = sy
    shl ah, cl
    sar ah, cl                  ; AH = sx
    add ch, ah                  ; CH = sx + sy
    cbw
    shl ax, 1                   ; AX = 2 z0
    xchg ax, cx
    mov al, ah
    cbw
    add ax, cx
    shl ax, 1                   ; AX = 2 (2 z0 + sx + sy)
    mov cl, 3
    shl dx, cl
    sub dx, ax
    add dx, [bx + BZG_Y0]
    sub dx, 5
    xchg ax, dx
    stosw                       ; y
    pop cx
    loop .way
    ret
; 7 CELLS (SPEC.md 128.15.6): each cell as in RAM but two fields, each stored
; as its difference from the RULE: a VOID cell's z0 as z0 - rule_z0 (8 bits),
; and every cell's SAFE bit XOR rule_safe.  The rule, as the tool builds the
; grid (bbcourse.cells_rule is this routine's model):
;   V = a cell's lowest corner + 79h, z0 + min(0, sx) + min(0, sy) + 79h in
;       8 bits, UNSIGNED, for a cell that is not VOID; FFh for a VOID cell
;       and outside the grid
;   rule_z0 = the least V within two tiles (Chebyshev in wx and wy) + 81h:
;       the least corner less 6 (NEAR), or FFh + 81h = -128 (OPEN).  The bias
;       makes OPEN's value the sentinel's and the order the corners' for every
;       corner a NEAR cell can hold (-122 .. 127; -122's NEAR z0 IS -128)
;   rule_safe = a FLOOR cell with sx = sy = 0, OBS clear and its four edge
;       neighbours not VOID
; The 5 x 5 least is SEPARABLE: A = the least V on the wx diagonal's 5 cells
; through a cell, then the least A on the wy diagonal's.  In the grid's rows
; a wx step is (row + 1, k + p) and a wy step (row + 1, k + p - 1), p the
; row's parity (SMIN + row, AND 1), so each reaches 2 rows and a cell either
; way.  The A rows are scratch in bz_boxbuf, BZ_CXRW bytes a row with a pad
; (FFh) either side of KW cells, in a window that slides down the buffer and
; is copied back to its start at the end.  Iteration j = 0 .. NROWS + 3 holds
; A rows j - 6 .. j + 2: it sets row j + 2 to FFh; lays each non-VOID cell of
; grid row j into A rows j - 2 .. j + 2 and XORs its SAFE; then takes A rows
; j - 6 .. j - 2 for each VOID cell of grid row j - 4.  The rule reads only
; fields the form does not change (a VOID cell's z0 and every SAFE bit are the
; two it never reads), so its order is free.  NROWS and KW count; the A
; writes stay inside the window (one cell either side of KW, the pads), and
; the grid writes inside the slot, whatever the bytes.  The tool keeps every
; non-VOID cell two tiles inside the grid (read_part), so the edge reads stay
; in the grid.  DS = ours (the A rows), ES = the part; the frame is SS:BP.
; About 0.19 s on PEAK, with bz_cxsafe (priced, 128.15.6).
BZ_CXRW     equ 36              ; an A row's stride: a pad, KW cells, a pad
BZ_CXNS     equ 4 * BZ_BOXB / BZ_CXRW   ; the A rows bz_boxbuf holds
%if BZ_CXRW < BZ_KWMAX + 2 || BZ_CXNS < 10 || BZ_CXRW & 1
 %error "bz_cxcel: bz_boxbuf does not hold its window of A rows"
%endif
BZ_CXF_R    equ 0               ; A row j - 6's first byte (its left pad)
BZ_CXF_J    equ 2               ; j
BZ_CXF_P    equ 4               ; row j's parity
BZ_CXF_RS   equ 6               ; 4 KW: a grid row's bytes
BZ_CXF_G    equ 8               ; grid row j
BZ_CXF_N    equ 10              ; NROWS
BZ_CXF_KW   equ 12              ; KW
BZ_CXF_U    equ 14              ; from cell k, row j - 1's cell k + p - 1: 4 p - 4 - 4 KW
BZ_CXF_D    equ 16              ; and row j + 1's: 4 p - 4 + 4 KW
BZ_CXF      equ 18
%if BZ_CXF != 18
 %error "bz_cxcel: .out's add sp is the frame's size"
%endif
bz_cxcel:
    mov bx, [es:BZC_GRID]
    mov cx, [es:bx + BZG_KW]
    mov dx, cx
    shl dx, 1
    shl dx, 1                   ; DX = 4 KW
    mov ax, [es:bx + BZG_SMIN]
    and ax, 1                   ; AX = p, row 0's
    mov si, ax
    shl si, 1
    shl si, 1
    sub si, 4
    add si, dx
    push si                     ; D: 4 p - 4 + 4 KW
    sub si, dx
    sub si, dx
    push si                     ; U: 4 p - 4 - 4 KW
    push cx                     ; KW
    push word [es:bx + BZG_NROWS]       ; N
    push di                     ; G: grid row 0, the slot
    push dx                     ; RS
    push ax                     ; P
    xor ax, ax
    push ax                     ; J
    mov di, bz_boxbuf
    push di                     ; R
    mov bp, sp
    mov cx, 9 * BZ_CXRW / 2     ; A rows -6 .. 2: FFh
.fill:
    push es
    push ds
    pop es
    mov ax, 0FFFFh
    rep stosw
    pop es
    mov bx, [bp + BZ_CXF_P]     ; BX = p, both passes'
; row j: lay each cell that is not VOID into the A rows j - 2 .. j + 2
    mov ax, [bp + BZ_CXF_J]
    cmp ax, [bp + BZ_CXF_N]
    jae .gat                    ; (past the grid: no row j)
    mov si, [bp + BZ_CXF_G]
    mov di, [bp + BZ_CXF_R]
    add di, 6 * BZ_CXRW + 1     ; A row j, cell 0
    mov ch, [bp + BZ_CXF_KW]
    mov cl, 4
.sc:
    mov ax, [es:si + 2]         ; AL = surface : kind, AH = flags
    test al, 15
    jz .scn                     ; VOID: no corner
    call bz_cxsafe
    mov dx, [es:si]             ; DL = z0, DH = sy : sx
    mov al, 79h
    add al, dl
    test dh, 8
    jz .lx
    mov dl, dh
    or dl, 0F0h                 ; sx < 0
    add al, dl
.lx:
    sar dh, cl                  ; DH = sy
    jns .ly
    add al, dh
.ly:                            ; AL = V, what this cell lays
    cmp [di + 2 * BZ_CXRW + 1], al      ; A(j + 2, k + 1)
    jbe .s1
    mov [di + 2 * BZ_CXRW + 1], al
.s1:
    cmp [bx + di + BZ_CXRW], al         ; A(j + 1, k + p)
    jbe .s2
    mov [bx + di + BZ_CXRW], al
.s2:
    cmp [di], al                        ; A(j, k)
    jbe .s3
    mov [di], al
.s3:
    cmp [bx + di - BZ_CXRW - 1], al     ; A(j - 1, k + p - 1)
    jbe .s4
    mov [bx + di - BZ_CXRW - 1], al
.s4:
    cmp [di - 2 * BZ_CXRW - 1], al      ; A(j - 2, k - 1)
    jbe .scn
    mov [di - 2 * BZ_CXRW - 1], al
.scn:
    add si, 4
    inc di
    dec ch
    jnz .sc
; row j - 4: each VOID cell's z0, from the A rows j - 6 .. j - 2
.gat:
    cmp word [bp + BZ_CXF_J], 4
    jb .nx
    mov si, [bp + BZ_CXF_RS]
    shl si, 1
    shl si, 1
    neg si
    add si, [bp + BZ_CXF_G]     ; grid row j - 4 (its parity is row j's)
    mov di, [bp + BZ_CXF_R]
    add di, 2 * BZ_CXRW + 1     ; A row j - 4, cell 0
    mov cx, [bp + BZ_CXF_KW]
.ga:
    test byte [es:si + 2], 15
    jnz .gan                    ; not VOID: its z0 is stored as it is
    mov al, [di - 2 * BZ_CXRW + 1]      ; A(s - 2, k + 1)
    cmp al, [bx + di - BZ_CXRW]         ; A(s - 1, k + p)
    jbe .g1
    mov al, [bx + di - BZ_CXRW]
.g1:
    cmp al, [di]                        ; A(s, k)
    jbe .g2
    mov al, [di]
.g2:
    cmp al, [bx + di + BZ_CXRW - 1]     ; A(s + 1, k + p - 1)
    jbe .g3
    mov al, [bx + di + BZ_CXRW - 1]
.g3:
    cmp al, [di + 2 * BZ_CXRW - 1]      ; A(s + 2, k - 1)
    jbe .g4
    mov al, [di + 2 * BZ_CXRW - 1]
.g4:
    add al, 81h                 ; the least corner - 6, or FFh + 81h = -128
    add [es:si], al             ; z0 = the stored difference + rule_z0
.gan:
    add si, 4
    inc di
    loop .ga
.nx:
    mov ax, [bp + BZ_CXF_RS]
    add [bp + BZ_CXF_G], ax
    mov ax, 4
    xor byte [bp + BZ_CXF_P], 1
    jnz .np
    neg ax
.np:
    add [bp + BZ_CXF_U], ax     ; the edge neighbours' cells move with p
    add [bp + BZ_CXF_D], ax
    mov ax, [bp + BZ_CXF_N]
    add ax, 4
    inc word [bp + BZ_CXF_J]
    cmp [bp + BZ_CXF_J], ax     ; j = 0 .. NROWS + 3
    jae .out
; the window moves down a row; at the buffer's end, rows j - 6 .. j + 1 go
; back to its start
    mov si, [bp + BZ_CXF_R]
    add si, BZ_CXRW
    mov di, si
    cmp si, bz_boxbuf + (BZ_CXNS - 9) * BZ_CXRW
    jbe .fit
    push es
    push ds
    pop es
    mov di, bz_boxbuf
    mov cx, 4 * BZ_CXRW
    rep movsw
    pop es
    mov di, bz_boxbuf
.fit:
    mov [bp + BZ_CXF_R], di
    add di, 8 * BZ_CXRW         ; row j + 2: FFh
    mov cx, BZ_CXRW / 2
    jmp .fill
.out:
    add sp, 18                  ; BZ_CXF: the frame's nine words (spelled as
    ret                         ; a number, which tools/stkbalance.py reads)

; bz_cxcel's SAFE: AL = the cell's surface : kind, AH = its flags, ES:SI =
; the cell, SS:BP bz_cxcel's frame; XORs rule_safe into the cell's flags.
; Clobbers AL and DX.
bz_cxsafe:
    and al, 15
    cmp al, 1                   ; FLOOR
    jne .no
    test ah, BZ_FL_OBS          ; a prop's cell: never SAFE
    jnz .no
    cmp byte [es:si + 1], 0     ; sx = sy = 0
    jne .no
    mov dx, si
    add si, [bp + BZ_CXF_U]     ; row j - 1: cells k + p - 1 and k + p ...
    mov ah, 2
.nbr:
    test byte [es:si + 2], 15
    jz .nb
    test byte [es:si + 6], 15
    jz .nb
    mov si, dx
    add si, [bp + BZ_CXF_D]     ; ... then row j + 1's two
    dec ah
    jnz .nbr
    mov si, dx
    xor byte [es:si + 3], BZ_FL_SAFE
.nb:
    mov si, dx
.no:
    ret
; -----------------------------------------------------------------------------
; THE HERCULES MADE AT THE FETCH (SPEC.md 128.11.3).  A Hercules byte is the
; CGA byte with each 2-bit pixel c replaced by herc_pair(c, line, column): 00
; for 0, 11 for 3, and for 1 or 2, 10 where line + column is even and 01 where
; it is odd.  Every block, ball row and squash or shatter row starts on a
; 4-pixel world column, so only the PARITY p of a byte's line chooses, and
; BZ_HTAB[256 p + b] is the byte b translated: two 256-byte tables.
;
; bz_hgen - BUILD BZ_HTAB into the first 512 bytes of bz_boxbuf, which nothing
; uses until the bracket starts.  Per byte, bitwise rather than per pixel: a
; field is MID (1 or 2) where its two bits differ, m = those fields' 11s, and
; the byte is b ^ ((b ^ P) & m) with P the parity's mid pattern - 10 01 10 01
; (99h) for p = 0, 01 10 01 10 (66h) for p = 1, which is NOT 99h.  The tool's
; bbcourse.htab() is the same table; bonanzaring's Hercules oracle checks this
; one by its picture (SPEC.md 128.11.17.2).  DS = ours.  Preserves nothing.
; -----------------------------------------------------------------------------
bz_hgen:
    mov di, bz_boxbuf
    mov dl, 99h                 ; P for p = 0
.p:
    xor cx, cx                  ; CL = b, 0 .. 255
.b:
    mov al, cl
    mov ah, al
    shr ah, 1
    xor ah, al
    and ah, 55h                 ; each mid field's low bit
    mov bh, ah
    shl ah, 1
    or ah, bh                   ; AH = m
    mov bh, al
    xor bh, dl
    and bh, ah
    xor al, bh                  ; AL = b ^ ((b ^ P) & m)
    mov [di], al
    inc di
    inc cl
    jnz .b
    not dl                      ; 99h -> 66h: the second table; 66h -> 99h: done
    cmp dl, 66h
    je .p
    ret

; -----------------------------------------------------------------------------
; bz_hxlat - translate the fetched course and ball parts IN PLACE through
; BZ_HTAB (SPEC.md 128.11.3), on the Hercules, before the bracket:
;   the course's blocks, BLKOFF .. BLKOFF + 16 N: a block line is ONE WORD, its
;     index in the block the line, so the table changes every two bytes (8
;     lines a block, even: one run of 8 N rows of 2 bytes from table 0);
;   the ball's ROLL frames: frame f's row r through ((f >> 3) + r) & 1, so each
;     run of 8 frames is 128 rows of 5 bytes from table (f >> 3) & 1;
;   the FRAME half of each squash and shatter entry (frame x shift x parity
;     copy p x (mask 80, frame 80)): 16 rows from table p;
;   a PLATFORM's sprite (wave 3, SPEC.md 128.12.6.4): parity copy p x (mask
;     144, frame 144), the frame's row r through table (p + r) AND 1.
; Every ball part this launch fetched (bz_bsegs, wave 4), each the same way.
; Masks and the shadow are the same bytes on both cards and are not touched.
; XLAT reads DS:BX + AL, so DS = OURS (the table, in our bss) and the part is
; ES (`es lodsb`, `stosb`, SI = DI): on kern_mega ES is the part's own
; selector, written whole at offsets under its length, as op_fetch's expand
; already writes it; nothing through CS (SPEC.md 128.11.14).  DS = ours.
; Preserves nothing; ES is left the ball's (bz_launch saves and restores it).
; -----------------------------------------------------------------------------
bz_hxlat:
    mov bx, bz_boxbuf           ; BX = table 0, BP = the toggle to table 1 and
    lea bp, [bx + 256]          ; back: table 0 ^ table 1, two byte bases 256
    xor bp, bx                  ; apart (any alignment)
    mov es, [bz_cseg]           ; the course: 8 N rows of 2 bytes
    mov si, [es:BZC_BLKOFF]
    mov cx, [es:BZC_NBLK]
    shl cx, 1
    shl cx, 1
    shl cx, 1
    mov dl, 2
    call bz_hxrows
    mov cx, [es:BZC_NPROP]      ; the PLATFORMS' sprites (SPEC.md 128.12.6.4):
    mov di, [es:BZC_PROPOFF]    ; parity copy p's frame half, row r through
    jcxz .noplat                ; table (p + r) AND 1 (BX is table 0 here: the
.prec:                          ; blocks' run is even)
    cmp byte [es:di + BZP_KIND], BZ_PK_PLATFORM
    jne .pnext
    push cx
    push di
    mov si, [es:di + BZP_PSPR]
    mov dl, BZ_PLW / 4
    add si, BZ_PLH * BZ_PLW / 4 ; past copy 0's mask
    mov cx, BZ_PLH              ; (even: back on table 0)
    call bz_hxrows
    add si, BZ_PLH * BZ_PLW / 4 ; past copy 1's mask
    xor bx, bp                  ; copy 1's first row: table 1
    mov cx, BZ_PLH
    call bz_hxrows
    xor bx, bp                  ; (table 0 again)
    pop di
    pop cx
.pnext:
    add di, BZ_PROPREC
    loop .prec
.noplat:
    mov di, bz_bsegs            ; each ball fetched (wave 4: up to three)
.nb:
    mov ax, [di]
    or ax, ax
    jz .nbn
    push di
    mov es, ax
    call bz_hxball
    pop di
.nbn:
    inc di
    inc di
    cmp di, bz_bsegs + 2 * BZ_NMAT
    jb .nb
    ret
; ES = a ball part: its roll frames, squash and shatter entries (BP the toggle)
bz_hxball:
    mov bx, bz_boxbuf           ; (table 0 for its first row)
    mov si, BZ_BAL_FRMOFF
    mov dl, BZ_BAL_RB
    mov dh, BZ_BAL_FRAMES / 8
.roll:
    mov cx, 8 * BZ_BAL_ROWS     ; (even: the run ends on its first table)
    call bz_hxrows
    xor bx, bp                  ; the next run's first row: the other table
    dec dh
    jnz .roll
    mov si, BZ_BAL_SQOFF        ; the squash entries
    mov al, BZ_BAL_NSQ
    call bz_hxents
    mov si, BZ_BAL_SHAOFF       ; ...and glass's shatter entries: +12 counts
    mov al, [es:BZB_NSHA]       ; them, 0 for rubber and steel
; AL = frames of entries at SI: each frame's BZ_BAL_SHIFTS x 2 parity copies,
; every copy's frame half 16 rows from table p (copies alternate p = 0, 1)
bz_hxents:
    mov ah, BZ_BAL_SHIFTS * 2
    mul ah
    or ax, ax
    jz .out
    mov dh, al                  ; (at most 4 x 8 entries)
    mov bx, bz_boxbuf
.ent:
    add si, BZ_BAL_ENT / 2      ; past the mask half to the frame half
    mov cx, BZ_BAL_ROWS
    call bz_hxrows              ; (even: back on the copy's own table)
    xor bx, bp                  ; the next copy is the other parity
    dec dh
    jnz .ent
.out:
    ret

; ES:SI = the first byte, CX = rows (at least 1) of DL bytes, BX = the first
; row's table, BP = the toggle: each byte through the table, each row then the
; other table.  Out: SI past the last byte, BX the next row's table.  Clobbers
; AX, CX, DI.
bz_hxrows:
    mov di, si
.r:
    mov ah, dl
.b:
    es lodsb
    xlat
    stosb
    dec ah
    jnz .b
    xor bx, bp
    loop .r
    ret

; SI = a TOASTSTR in our segment
bz_toast:
    push es
    push ds
    pop es
    xor cx, cx
    call OSAPI_TOAST
    pop es
    ret

TOASTSTR bz_t_small, 'Bonanza: too little RAM'
TOASTSTR bz_t_adapt, 'CGA OR HERC ONLY'
TOASTSTR bz_t_nofs, 'Bonanza: no full screen'

; -----------------------------------------------------------------------------
; THE FACE (SPEC.md 128.14.3.2): two PAGES, [bz_page] 0 MAIN and 1 RESULTS.
; Every line is ONE opaque OSAPI_FONT_RUN padded with spaces to the content's
; width (the padding is the erase, SPEC.md 6.1), and only the 2px gaps between
; lines and the strip under the last one are filled: no pixel is written
; twice.  The lines are built in bz_lbuf.  MAIN's thirteen are a builder each
; (bz_ftab), so a key redraws exactly the lines it changed (bz_redraw); the
; RESULTS page is drawn whole and left by the next key.  EVERY LINE FITS THE
; CGA's 42 CELLS (128.14.17 item 2): each builder's widest output - its
; strings, which BZS measures, and its fields at their widest - is asserted
; under the strings (BZ_FIT), so a longer string fails the build.
; -----------------------------------------------------------------------------
BZ_NLINE    equ 13              ; the CGA's content holds 13 lines of 42 cells
BZ_FACEW    equ 42
BZ_TIMEW    equ 6               ; a time: `ss.hh`, `ssss.h` (from 100 s) or `20:00+`
BZ_FALLMAX  equ 9999            ; falls are shown, and filed, to four digits
BZ_SC_NAME  equ 3               ; the scorecard's columns (bz_lbuf offsets; 0 is
BZ_SC_TIME  equ 9               ; the margin cell): `K NAME  time* f<n> par <p>
BZ_SC_FALL  equ 17              ; best <b>`
BZ_SC_PAR   equ 23
BZ_SC_BEST  equ 31

bz_face:
    call bz_fgeom
    jc .out
    cmp byte [bz_page], 0
    jne .res
    xor ax, ax                  ; MAIN: lines 0 - 12, each by its builder
.main:
    push ax
    call bz_fline
    pop ax
    inc ax
    cmp al, BZ_NLINE
    jb .main
    jmp short .tail
.res:                           ; RESULTS (after B, until the next key)
    mov word [bz_fy], 0
    call bz_l0                  ; lines 0 and 1 as MAIN's
    call bz_l1
    call bz_adname              ; line 2: `CGA frames <n>  <r> Hz  misses <n>`
    mov si, bx
    call bz_lstr
    call bz_frline
    call bz_line
    call bz_lmeas               ; line 3: what was measured
    call bz_facres              ; lines 4 - 11: the worst frame, the parts'
    mov si, bz_s_back           ; means, the writers' counts; line 12
    call bz_lline
.tail:
    ; the strip under the last line, to the content's foot
    mov bx, [bz_fy]
    mov dx, [bz_fh]
    dec dx
    cmp dx, bx
    jl .right
    call bz_fillrows
.right:
    ; the columns right of the last whole cell (a content width that is not
    ; a multiple of 8), over the lines' height only: the strips above own
    ; the full width already
    mov ax, [bz_fcells]
    mov cl, 3
    shl ax, cl
    cmp ax, [bz_fw]
    jae .out
    mov cx, [bz_fw]
    dec cx
    xor bx, bx
    mov dx, [bz_fh]
    dec dx
    call bz_fillrect
.out:
    ret

; the face's geometry: [bz_fw], [bz_fh], [bz_ox], [bz_oy], [bz_fcells].  CF = 1
; when the window has none.  Clobbers AX, BX, CX, DX.
bz_fgeom:
    mov bx, [bz_win]
    call OSAPI_WM_GEOM
    jc .out
    mov [bz_fw], cx
    mov [bz_fh], dx
    call OSAPI_WM_CONTENT
    mov [bz_ox], ax
    mov [bz_oy], dx
    mov ax, [bz_fw]
    mov cl, 3
    shr ax, cl
    cmp ax, BZ_LMAX
    jbe .cells
    mov ax, BZ_LMAX
.cells:
    mov [bz_fcells], ax
    clc
.out:
    ret

; the window's clip armed and the face's geometry read: CF = 1 when either
; cannot be had - or when this key LEAVES the RESULTS page ([bz_pgo]), whose
; whole MAIN face bz_onkey paints after it, so no line is drawn twice.
; Clobbers AX, BX, CX, DX.
bz_fclip:
    cmp byte [bz_pgo], 0
    stc
    jne .out
    mov bx, [bz_win]
    call OSAPI_WM_CLIP_SET
    jc .out
    call bz_fgeom
.out:
    ret

; MAIN's line AL (0 - 12) drawn at its place.  Preserves nothing.
bz_fline:
    xor ah, ah
    mov bx, ax
    mov ah, BZ_LH
    mul ah
    mov [bz_fy], ax
    shl bx, 1
    jmp [bz_ftab + bx]
bz_ftab:    dw bz_l0, bz_l1, bz_l2, bz_l3, bz_l4, bz_l5, bz_l6
            dw bz_sc, bz_sc, bz_sc, bz_sc, bz_sc, bz_l12
%if ($ - bz_ftab) / 2 != BZ_NLINE || BZ_NTOUR != 5
 %error "MAIN is thirteen lines, five of them the scorecard's (SPEC.md 128.14.3.2)"
%endif

; MAIN's lines in the 0FFh-ended list at SI, redrawn outside a paint (the clip
; armed first, SPEC.md 11.3); AL = one line, for bz_redraw1.  Preserves nothing.
bz_redraw:
    call bz_fclip
    jc .out
.l:
    lodsb
    cmp al, 0ffh
    je .out
    push si
    call bz_fline
    pop si
    jmp .l
.out:
    ret

; C, M and N on the desktop (one press each, bz_dkey): the next camera mode,
; ball or course, and the lines that name them redrawn.  N sets the ball to the
; new course's own (SPEC.md 128.11.5.4).  Every one is the session's.
bz_camkey:
    call bz_cnext
    jmp short bz_line3

bz_ballkey:
    inc byte [bz_matsel]
    cmp byte [bz_matsel], BZ_NMAT
    jb bz_line3
    mov byte [bz_matsel], 0
bz_line3:
    mov al, 3
    jmp short bz_redraw1
bz_line4:                       ; S (bzsound.inc bzs_skey): the sound's line
    mov al, 4
bz_redraw1:
    push ax
    call bz_fclip
    pop ax
    jc .out
    jmp bz_fline
.out:
    ret

%if BZ_CRS_BENCH != 0
 %error "bz_crskey cycles courses 1 .. BZ_NCRS - 1: BENCH must be course 0"
%endif
bz_crskey:
    mov bl, [bz_crsel]          ; every course but BENCH: FIRST, TRIAL, ...
    inc bx
    cmp bl, BZ_NCRS
    jb .k
    mov bl, 1
.k:
    mov [bz_crsel], bl
    xor bh, bh
    mov al, [bz_cballs + bx]
    mov [bz_matsel], al
    mov si, bz_crsl             ; Enter's title (1) and the ball (3)
    jmp bz_redraw
bz_crsl:    db 1, 3, 0ffh
bz_stopl:   db 1, 3, 5, 12, 0ffh ; a tour stopped on the face: the keys, M,
                                ; the demo keys and the tour's line

; CF = 1 while a tour's course is next or playing ([bz_tour] 1 - 5, SPEC.md
; 128.14.3.1).  Preserves all but the flags.
bz_intour:
    push ax
    mov al, [bz_tour]
    dec al
    cmp al, BZ_NTOUR
    pop ax
    ret

; ---- MAIN's builders: each draws its line at [bz_fy] and steps it -------------
; line 0: the title
bz_l0:
    mov si, bz_s_title
; SI's string as a whole line
bz_lline:
    call bz_lstr
    jmp bz_line

; line 1: what Enter does.  `G GAME  ENTER <title>  N NEXT`; in a tour `ENTER
; next  ESC stop tour`
bz_l1:
    mov si, bz_s_tkeys
    call bz_intour
    jc bz_lline
    mov si, bz_s_keys
    call bz_lstr
    mov al, [bz_crsel]
    call bz_ltitle
    mov si, bz_s_nk
    call bz_lcat
    jmp bz_line

; line 2: the adapter, or why there is none, or why the last launch was
; refused (bz_err 1 the mode, 2 the display changed under the key)
bz_l2:
    call bz_adname
    mov al, [bz_err]
    mov bx, bz_s_err
    cmp al, 1
    je .err
    mov bx, bz_s_err2
    cmp al, 2
    jne bz_lline
.err:
    mov si, bx
    jmp bz_lline

; the adapter's names: SI = line 2's (`Adapter: ...`, or why there is none),
; BX = the results' prefix (`CGA frames `).  Clobbers AX.
bz_adname:
    mov si, bz_s_small
    cmp byte [bz_small], 0
    jne .none
    call bz_adapter
    mov si, bz_s_cga
    mov bx, bz_s_cgar
    cmp al, 1
    je .out
    mov si, bz_s_herc
    mov bx, bz_s_hercr
    cmp al, 2
    je .out
    mov si, bz_s_noad
.none:
    mov bx, si
.out:
    ret

; line 3: the settings and their keys, `C <camera>  M <ball>  T <control>`;
; a tour rolls each course's own ball, so M is not offered in one
bz_l3:
    mov si, bz_s_camk
    call bz_lstr
    mov bl, [bz_cmode]
    xor bh, bh
    shl bx, 1
    mov si, [bz_s_cmodes + bx]
    call bz_lcat
    call bz_intour
    jc .l
    mov si, bz_s_ballk
    call bz_lcat
    mov bl, [bz_matsel]
    xor bh, bh
    shl bx, 1
    mov si, [bz_s_mats + bx]
    call bz_lcat
.l:
    mov si, bz_s_ctlk           ; T: KEYS or MOUSE (SPEC.md 128.14.8)
    call bz_lcat
    mov si, bz_s_keyb
    cmp byte [bz_ctl], 0
    je .c
    mov si, bz_s_mouse
.c:
    call bz_lcat
    jmp bz_line

; line 4: `S <the sound>` - the player's choice and, under AUTO, the arm it
; found (SPEC.md 128.20.4).  S redraws it (bzs_skey, bz_line4).
bz_l4:
    mov si, bz_s_sndk
    call bz_lstr
    mov bl, [bzs_mode]
    xor bh, bh
    shl bx, 1
    mov si, [bz_s_smodes + bx]
    call bz_lcat
    cmp byte [bzs_mode], BZS_M_SPK
    jae .l
    mov si, bz_s_sfm
    cmp byte [bzs_arm], BZS_A_FM
    je .a
    mov si, bz_s_sspk
.a:
    call bz_lcat
.l:
    jmp bz_line

; line 5: the demo keys (SPEC.md 128.14.3.2): `B BENCH  L LOAD  V DEMO`, and
; with a log held `R PLAY  D TIME  W SAVE  L LOAD  V DEMO` - B, the engine
; benchmark, is the key dropped for the 42 cells (128.14.17 item 2), and still
; works; a tour offers `W SAVE` alone, with a log held
bz_l5:
    call bz_lbeg
    call bz_rhave
    jne .nolog
    mov si, bz_s_savk
    call bz_intour
    jc .cat
    mov si, bz_s_repk
    call bz_lcat
    mov si, bz_s_savk
    call bz_lcat
    jmp short .lv
.nolog:
    call bz_intour
    jc .l
    mov si, bz_s_benk
.cat:
    call bz_lcat
    call bz_intour
    jc .l
.lv:
    mov si, bz_s_ldk
    call bz_lcat
.l:
    jmp bz_line

; line 6: THE HELD LOG's last run (SPEC.md 128.14.3.2, 128.14.16 item 1): after
; a play or a replay, finished or stopped, `<NAME> <time> s <end> falls <n>`
; and on a course with flags `flags <reached>/<all>` - the clock, the falls,
; the flags and the hole-out, on the face that costs the frame nothing.  The
; play's stuns and shatters are the field it drops to fit (128.14.17 item 2).
; With none, the keys' hint (the mouse's under T MOUSE).  After L, `<NAME>
; <time> s  <8.3 name>`, and after V `<NAME> <time> s  demo`: the held log's
; course and its steps (SPEC.md 128.14.3.2).
bz_l6:
    mov al, [bz_lsv]
    cmp al, 1
    je .run
    jb .hint
    call bz_lbeg                ; 2 a loaded file, 3 a shipped demo
    push ax
    mov al, [bz_rlog + BZR_CRS]
    call bz_lname
    mov al, ' '
    call bz_lch
    mov ax, [bz_rlog + BZR_STEPS] ; (a log's steps are at most 255 x 2,040:
    mov dx, [bz_rlog + BZR_STEPS + 2] ; under bz_t100's 2^19)
    call bz_ltime
    mov si, bz_s_secs
    call bz_lcat
    mov al, ' '
    call bz_lch
    pop ax
    mov si, bz_lfn
    cmp al, 2
    je .fn
    mov si, bz_s_demo
.fn:
    call bz_lcat
    jmp bz_line
.hint:
    mov si, bz_s_hint
    cmp byte [bz_ctl], 0
    je bz_lline
    mov si, bz_s_mhint
    jmp bz_lline
.run:
    call bz_lbeg
    mov al, [bz_lsk]
    call bz_lname
    mov al, ' '
    call bz_lch
    mov ax, [bz_lsn]
    call bz_ltimew
    mov si, bz_s_secs
    call bz_lcat
    mov bl, [bz_lsend]          ; 0 stopped, 1 the goal line, 2 the cup
    xor bh, bh
    shl bx, 1
    mov si, [bz_s_ends + bx]
    call bz_lcat
    mov si, bz_s_falls
    call bz_lcat
    mov ax, [bz_lsf]
    call bz_lnumw
    mov bl, [bz_lsk]
    xor bh, bh
    mov ah, [bz_cncks + bx]
    or ah, ah
    jz .l
    mov si, bz_s_flags
    call bz_lcat
    mov al, [bz_lsc]
    add al, '0'
    call bz_lch
    mov al, '/'
    call bz_lch
    mov al, ah
    add al, '0'
    call bz_lch
.l:
    jmp bz_line

; lines 7 - 11: THE SCORECARD, tour course K = line - 6: `K NAME  <time>[*]
; f<falls>  par <p>  best <b>` (SPEC.md 128.14.3.1 - 128.14.3.3): the tour's
; time (`-` none), `*` at or under par, its falls, the par, BONANZA.DAT's best.
; The NAME, not the title: the title's 24 cells and the rest are 61.
bz_sc:
    mov ax, [bz_fy]
    mov cl, BZ_LH
    div cl
    sub al, 6                   ; K, 1 - 5
    xor ah, ah
    mov si, ax
    shl si, 1                   ; SI = 2K
    call bz_lbeg
    push ax
    add al, '0'
    call bz_lch
    mov cx, bz_lbuf + BZ_SC_NAME
    call bz_lto
    pop ax
    push si
    call bz_lname
    pop si
    mov cx, bz_lbuf + BZ_SC_TIME
    call bz_lto
    mov ax, [bz_ttime - 2 + si] ; steps, 0 none
    or ax, ax
    jnz .t
    mov al, '-'
    call bz_lch
    jmp short .par
.t:
    push ax
    call bz_ltimew
    mov ax, 100                 ; the time AT OR UNDER par: hundredths <=
    mul word [bz_cpars + si]    ; par x 100
    mov bx, dx
    xchg ax, cx
    pop ax
    xor dx, dx
    call bz_t100
    cmp dx, bx
    ja .nostar
    jb .star
    cmp ax, cx
    ja .nostar
.star:
    mov al, '*'
    call bz_lch
.nostar:
    mov cx, bz_lbuf + BZ_SC_FALL
    call bz_lto
    mov al, 'f'
    call bz_lch
    mov ax, [bz_tfall - 2 + si]
    call bz_lnumw
.par:
    mov cx, bz_lbuf + BZ_SC_PAR
    call bz_lto
    push si
    mov si, bz_s_par
    call bz_lcat
    pop si
    mov ax, [bz_cpars + si]
    call bz_lnumz
    mov cx, bz_lbuf + BZ_SC_BEST
    call bz_lto
    mov bx, si                  ; entry K: bz_dat + BZD_ENT + 6K
    shl si, 1
    add bx, si
    mov si, bz_s_best
    call bz_lcat
    mov ax, [bz_dat + BZD_ENT + 2 + bx]
    call bz_lbest
    jmp bz_line

; line 12: the tour.  During one `ENTER next: <title>`; stopped `Tour
; stopped`; else `Tour <total>  best <b>` (`-` for none).  A refused replay's
; reason takes it (SPEC.md 128.12.8): R is not offered in a tour.
bz_l12:
    mov si, bz_s_err3
    cmp byte [bz_err], 3
    je bz_lline
    mov si, bz_s_err4
    cmp byte [bz_err], 4
    je bz_lline
    mov al, [bz_tour]
    dec al
    cmp al, BZ_NTOUR
    jae .card
    inc ax
    push ax
    mov si, bz_s_tnext
    call bz_lstr
    pop ax
    call bz_ltitle
    jmp bz_line
.card:
    mov si, bz_s_tstop
    cmp al, BZ_NTOUR + 1
    je bz_lline
    mov si, bz_s_tour
    call bz_lstr
    cmp al, BZ_NTOUR            ; finished: its total
    jne .none
    call bz_ttotal
    call bz_ltime
    jmp short .best
.none:
    mov al, '-'
    call bz_lch
.best:
    mov si, bz_s_best2
    call bz_lcat
    mov ax, [bz_dat + BZD_TOUR + 2]
    mov dx, [bz_dat + BZD_TOUR + 4]
    mov cx, ax
    or cx, dx
    jz .nb
    call bz_ltime
    jmp bz_line
.nb:
    mov al, '-'
    call bz_lch
    jmp bz_line

; RESULTS line 3: what was measured - `BENCH autopilot`, or after D `Demo
; <NAME> <time> s` and `TRUNCATED` when it stopped measuring at 65,535 frames
; (SPEC.md 128.14.3.2, 128.14.7.3).  The held log is D's until the next key
; leaves the page.
bz_lmeas:
    mov si, bz_s_meas
    cmp byte [bz_mode], 3
    jne bz_lline
    mov si, bz_s_dmeas
    call bz_lstr
    mov al, [bz_rlog + BZR_CRS]
    call bz_lname
    mov al, ' '
    call bz_lch
    mov ax, [bz_rlog + BZR_STEPS]
    mov dx, [bz_rlog + BZR_STEPS + 2]
    call bz_ltime
    mov si, bz_s_secs
    call bz_lcat
    cmp byte [bz_dtr], 0
    je .l
    mov si, bz_s_trunc
    call bz_lcat
.l:
    jmp bz_line

; -> DX:AX = the tour's total steps, the sum of [bz_ttime]'s five; BL = 1 when
; one of them is the 65,535 clamp (such a total is never kept, 128.14.3.1).
; Preserves all else.
bz_ttotal:
    push cx
    push si
    xor ax, ax
    cwd
    mov bl, al
    mov si, bz_ttime
    mov cx, BZ_NTOUR
.s:
    cmp word [si], 0ffffh
    jne .a
    mov bl, 1
.a:
    add ax, [si]
    adc dx, 0
    inc si
    inc si
    loop .s
    pop si
    pop cx
    ret

; RESULTS line 2's numbers (SPEC.md 128.6), after the adapter's prefix: the
; frames, the display rate (to 999.9, the field's width) and the refreshes
; missed - a mean rate cannot tell 0 misses from a few
bz_frline:
    mov ax, [bz_rframes]
    call bz_lnumw
    mov si, bz_s_disp
    call bz_lcat
    call bz_hz10                ; AX = the display rate x 10
    cmp ax, 9999
    jbe .hz
    mov ax, 9999
.hz:
    xor dx, dx
    mov cx, 10
    div cx
    push dx
    call bz_lnumw
    mov al, '.'
    call bz_lch
    pop ax
    add al, '0'
    call bz_lch
    mov si, bz_s_hz
    call bz_lcat
    mov ax, [bz_rmiss]
    jmp bz_lnumw

; RESULTS lines 4 - 11: the worst frame, the mean CPU clocks of each part of a
; frame (PIT counts x 4), the writers' counts
bz_facres:
    mov si, bz_s_worst          ; the worst frame, and the means' heading
    call bz_lstr
    mov ax, [bz_rfmax]
    mov dx, [bz_rfmax + 2]
    shl ax, 1                   ; PIT counts x 4 = CPU clocks
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    call bz_lnum
    mov si, bz_s_mean
    call bz_lcat
    call bz_line
    xor bx, bx                  ; BX = the part (0..5)
.part:
    push bx
    mov si, bx
    shl si, 1
    mov si, [bz_s_parts + si]
    call bz_lstr
    pop bx
    push bx
    call bz_meanclk             ; DX:AX = part BX's mean, CPU clocks
    call bz_lnum
    mov si, bz_s_clk
    call bz_lcat
    call bz_line
    pop bx
    inc bx
    cmp bx, BZ_NFACE            ; (the wheel's part is the rows' to read)
    jb .part
    mov si, bz_s_cols
    call bz_lstr
    mov ax, [bz_rncol]
    call bz_lnumw
    mov si, bz_s_rows
    call bz_lcat
    mov ax, [bz_rnrow]
    call bz_lnumw
    mov si, bz_s_full
    call bz_lcat
    mov ax, [bz_rnfull]
    call bz_lnumw
    mov si, bz_s_late           ; the row-0 boxes the beam overtook (SPEC.md
    call bz_lcat                ; 128.9 item 6)
    mov ax, [bz_rlate]
    call bz_lnumw
    jmp bz_line

; -> AX = the display rate x 10, from the measured frames' mean period.  1 PIT
; count is 1/1,193,182 s, so rate x 10 = 11,931,820 / mean counts.  0 = none.
bz_hz10:
    push bx
    push cx
    push dx
    call bz_period              ; DX:AX = mean PIT counts a frame (DX = 0 if sane)
    or dx, dx
    jnz .zero
    cmp ax, 183                 ; (the divide's quotient must fit 16 bits)
    jb .zero
    mov cx, ax
    mov dx, 11931820 >> 16
    mov ax, 11931820 & 0ffffh
    div cx
    jmp .out
.zero:
    xor ax, ax
.out:
    pop dx
    pop cx
    pop bx
    ret

; -> DX:AX = the mean PIT counts of one measured frame (the seven parts summed)
bz_period:
    push bx
    push cx
    push si
    xor ax, ax
    xor dx, dx
    mov si, bz_racc
    mov cx, BZ_NPART
.sum:
    add ax, [si]
    adc dx, [si + 2]
    add si, 4
    loop .sum
    call bz_div32
    pop si
    pop cx
    pop bx
    ret

; BX = part -> DX:AX = its mean in CPU clocks (PIT counts x 4)
bz_meanclk:
    push si
    mov si, bx
    shl si, 1
    shl si, 1
    mov ax, [bz_racc + si]
    mov dx, [bz_racc + si + 2]
    call bz_div32
    shl ax, 1
    rcl dx, 1
    shl ax, 1
    rcl dx, 1
    pop si
    ret

; DX:AX / [bz_rmfr] -> DX:AX (32 by 16, in two divides; 0 frames gives 0)
bz_div32:
    push bx
    push cx
    mov cx, [bz_rmfr]
    jcxz .zero
    mov bx, ax
    mov ax, dx
    xor dx, dx
    div cx                      ; the high word
    xchg ax, bx                 ; BX = the high quotient, AX = the low dividend
    div cx                      ; DX = the remainder from the high word
    mov dx, bx
    jmp .out
.zero:
    xor ax, ax
    xor dx, dx
.out:
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; bz_t100 - STEPS to HUNDREDTHS of a second (SPEC.md 128.10.6.2, 128.14.3.1):
; floor(n x 21,845 x 100 / 1,193,182), a step being 21,845 PIT counts.  In
; DX:AX = n (at most 2^19: a tour's total is under 327,671), out DX:AX.  The
; product is a 48-bit Q (its top word under 300), and 1,193,182 = 14,551 x 82,
; floor(floor(Q / a) / b) = floor(Q / ab): four 16-bit divides.  Times are kept
; as steps everywhere and converted only to be shown.  Preserves all else.
; -----------------------------------------------------------------------------
bz_t100:
    push bx
    push cx
    push si
    push di
    mov bx, dx                  ; n's high word
    mov cx, 21845
    mul cx
    mov si, ax                  ; P = n x 21,845 = BX':DI':SI
    mov di, dx
    xchg ax, bx
    mul cx                      ; (n's high word is at most 8)
    add ax, di
    adc dx, 0
    mov bx, dx                  ; P = BX:AX:SI
    mov cx, 100                 ; Q = P x 100 = BX:DI:SI
    xchg ax, si
    mul cx
    xchg ax, si                 ; SI = Q0
    mov di, dx
    mul cx
    add di, ax                  ; DI = Q1
    adc dx, 0
    xchg ax, bx
    mov bx, dx
    mul cx
    add ax, bx                  ; AX = Q2, under 300
    xchg ax, dx
    mov cx, 14551               ; Q / 14,551: DX < CX, so each quotient fits
    mov ax, di
    div cx
    mov bx, ax
    mov ax, si
    div cx                      ; BX:AX = Q / 14,551
    mov cx, 82
    xchg ax, bx
    xor dx, dx
    div cx
    xchg ax, bx
    div cx                      ; BX:AX = Q / 1,193,182
    mov dx, bx
    pop di
    pop si
    pop cx
    pop bx
    ret

; ---- the line builder ---------------------------------------------------------
; bz_lstr: SI = a NUL string -> bz_lbuf holds it (DI = its end)
bz_lstr:
    call bz_lbeg
; bz_lcat: append SI's NUL string at DI
bz_lcat:
    push ax
.c:
    lodsb
    or al, al
    jz .e
    call bz_lch
    jmp .c
.e:
    pop ax
    ret

; bz_lbeg: an empty line at bz_lbuf: a cell of margin (the padding is the
; erase), DI after it
bz_lbeg:
    mov di, bz_lbuf
    mov byte [di], ' '
    inc di
    ret

; CX = bz_lbuf + a column: spaces to it (none when DI is there or past it)
bz_lto:
    cmp di, cx
    jae .o
    mov byte [di], ' '
    inc di
    jmp bz_lto
.o:
    ret

; AL = a course K: its title (bz_ctitles) or its NAME (bz_cnames) appended.
; Clobbers AX, SI.
bz_ltitle:
    mov ah, BZ_CRS_TITLEB
    mul ah
    add ax, bz_ctitles
    xchg ax, si
    jmp bz_lcat
bz_lname:
    mov ah, BZ_CRS_NAMEB
    mul ah
    add ax, bz_cnames
    xchg ax, si
    jmp bz_lcat

; AX = a best in steps, 0 none (`-`), appended as a time
bz_lbest:
    or ax, ax
    jnz bz_ltimew
    jmp short bz_ldash
; AX = a number, 0 none (`-`)
bz_lnumz:
    or ax, ax
    jnz bz_lnumw
bz_ldash:
    push ax
    mov al, '-'
    call bz_lch
    pop ax
    ret

; AX = a course time in steps: `20:00+` for the clamp (SPEC.md 128.14.3.1),
; else as bz_ltime.  Preserves all.
bz_ltimew:
    cmp ax, 0ffffh
    jne .t
    push si
    mov si, bz_s_clamp
    call bz_lcat
    pop si
    ret
.t:
    push dx
    xor dx, dx
    call bz_ltime
    pop dx
    ret

; DX:AX = steps -> appended as seconds: `s.hh` under 100 s, `s.h` from there
; (SPEC.md 128.14.17 item 2), at most BZ_TIMEW cells for a tour's total.
; Preserves all.
bz_ltime:
    push ax
    push bx
    push cx
    push dx
    call bz_t100
    mov cx, 100
    div cx                      ; (under 6,553,600 hundredths: it fits)
    mov bx, ax
    push dx
    call bz_lnumw
    mov al, '.'
    call bz_lch
    pop ax
    aam                         ; AH = tenths, AL = hundredths
    xchg al, ah
    add ax, '00'
    call bz_lch
    cmp bx, 100
    jae .o
    mov al, ah
    call bz_lch
.o:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; AL = a character, appended at DI unless the line is full
bz_lch:
    cmp di, bz_lbuf + BZ_LMAX
    jae .full
    mov [di], al
    inc di
.full:
    ret

; AX = an unsigned word, appended at DI in decimal.  Preserves all.
bz_lnumw:
    push dx
    xor dx, dx
    call bz_lnum
    pop dx
    ret

; DX:AX = an unsigned number, appended at DI in decimal
bz_lnum:
    ; STKBALANCE-LOOP: one digit pushed a turn and the second loop pops them down to the SI mark
    push ax
    push bx
    push cx
    push dx
    push si
    mov si, sp                  ; the digits go on the stack, least first
    mov cx, 10
.dig:
    mov bx, ax                  ; DX:AX / 10, in two divides
    mov ax, dx
    xor dx, dx
    div cx
    xchg ax, bx
    div cx
    push dx                     ; the digit
    mov dx, bx
    mov bx, ax
    or bx, dx
    jnz .dig
.out:
    pop ax
    add al, '0'
    call bz_lch
    cmp sp, si
    jne .out
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; the line at DI ends: pad it to the content's cells, draw it at [bz_fy] + 2,
; fill the 2px gap above it, and step [bz_fy]
bz_line:
    push ax
    push bx
    push cx
    push dx
    push si
    mov cx, [bz_fcells]
    add cx, bz_lbuf
.pad:
    cmp di, cx
    jae .padded
    mov byte [di], ' '
    inc di
    jmp .pad
.padded:
    mov di, cx
    mov byte [di], 0
    mov bx, [bz_fy]             ; the gap above the cell row
    mov dx, bx
    inc dx
    call bz_fillrows
    add dx, BZ_LH - 1           ; DX = the cell's foot, exclusive
    cmp dx, [bz_fh]
    jle .fits
    inc bx                      ; a cell past the content's foot is not drawn
    inc bx                      ; (FONT_RUN does not clip to it): its rows
    call bz_fillrows            ; that are inside are filled instead
    jmp .next
.fits:
    mov si, bz_lbuf
    xor cx, cx
    add cx, [bz_ox]
    mov dx, [bz_fy]
    add dx, 2
    add dx, [bz_oy]
    mov ax, CBLACK | (CWHITE << 8)
    call OSAPI_FONT_RUN
.next:
    add word [bz_fy], BZ_LH
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; BX = the first content row, DX = the last: filled white across the cells'
; width (bz_fillrect's x range)
bz_fillrows:
    push ax
    push cx
    xor ax, ax
    mov cx, [bz_fcells]
    shl cx, 1
    shl cx, 1
    shl cx, 1
    dec cx
    call bz_fillrect
    pop cx
    pop ax
    ret

; AX = x1, BX = y1, CX = x2, DX = y2 in content coordinates: a white fill,
; clipped to the content box's foot
bz_fillrect:
    push ax
    push bx
    push cx
    push dx
    cmp dx, [bz_fh]
    jl .h
    mov dx, [bz_fh]
    dec dx
.h:
    cmp dx, bx
    jl .out
    push ax
    mov al, CWHITE
    call OSAPI_SET_COLOR
    pop ax
    add ax, [bz_ox]
    add cx, [bz_ox]
    add bx, [bz_oy]
    add dx, [bz_oy]
    call OSAPI_GFX_FILL
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; THE GAME'S BOOKS (SPEC.md 128.14.3.1, 128.14.3.3)
; -----------------------------------------------------------------------------
; bz_post - after the frame loop, IN the bracket (bzvideo.inc), so the face the
; kernel's restore paints is the new one: what the run just did, in memory
; only.  B: its RESULTS page.  A play or a replay: the held log's line (line
; 6).  A PLAY alone: in a tour, its time entered (a finish) or the tour
; STOPPED (Esc, F, Alt+Enter); and a best, when it finished with the course's
; own ball under the 65,535-step clamp - and the tour's, at its fifth.
; [bz_newb] = 1 when a best was set: bz_dsave writes the file on the desktop.
; Preserves nothing.
bz_post:
    mov al, [bz_res]            ; B and D: their results, when they ran to
    test byte [bz_mode], 1      ; their ends (D's line 3 names the demo, and
    jz .snap                    ; whether it measured all of it: bz_dtr)
    mov [bz_page], al
    ret
.snap:
    mov byte [bz_lsv], 1        ; THE LINE: the course, its steps (clamped
    mov al, [bz_crs]            ; to a word), its falls (to four digits),
    mov [bz_lsk], al            ; its flags reached and how it ended
    mov ax, [bz_nstep]
    cmp word [bz_nstep + 2], 0
    je .n
    mov ax, 0ffffh
.n:
    mov [bz_lsn], ax
    mov ax, [bz_nfall]          ; (a fall into a pit or a shatter: every
    cmp ax, BZ_FALLMAX          ; respawn but a RETURN)
    jbe .f
    mov ax, BZ_FALLMAX
.f:
    mov [bz_lsf], ax
    xor ax, ax
    mov ah, [bz_cksn]
.c:
    shl ah, 1
    adc al, 0
    or ah, ah
    jnz .c
    mov [bz_lsc], al
    mov al, [bz_goal]           ; 0 stopped, 1 the goal line, 2 holed out (a
    add al, [bz_hid]            ; holed ball has finished): the GOAL STEP, not
    mov [bz_lsend], al          ; bz_fin - an Esc in the goal's frame is read
                                ; first, and the run still finished
    cmp byte [bz_mode], 0       ; a replay posts nothing
    jne .out
    call bz_intour
    jnc .best
    cmp byte [bz_goal], 0
    jne .enter
    mov byte [bz_tour], BZ_NTOUR + 2 ; stopped: no total is entered
    ret
.enter:
    mov bl, [bz_tour]           ; (bz_crs is the tour's course k)
    xor bh, bh
    shl bx, 1
    mov ax, [bz_lsn]
    mov [bz_ttime - 2 + bx], ax
    mov ax, [bz_lsf]
    mov [bz_tfall - 2 + bx], ax
    inc byte [bz_tour]
    cmp byte [bz_tour], BZ_NTOUR + 1
    jne .best
    call bz_ttotal              ; the fifth: the total, DX:AX
    or bl, bl
    jnz .best                   ; (one at the clamp: never kept)
    mov cx, [bz_dat + BZD_TOUR + 2]
    mov bx, [bz_dat + BZD_TOUR + 4]
    mov si, cx
    or si, bx
    jz .tset                    ; no best tour yet
    cmp dx, bx
    ja .best
    jb .tset
    cmp ax, cx
    jae .best
.tset:
    mov [bz_dat + BZD_TOUR + 2], ax
    mov [bz_dat + BZD_TOUR + 4], dx
    mov byte [bz_newb], 1
.best:
    cmp byte [bz_goal], 0       ; THE COURSE'S BEST: a finish, started with
    je .out                     ; the course's own ball, under the clamp, and
    mov bl, [bz_crs]            ; under the best (or none yet)
    xor bh, bh
    mov al, [bz_cballs + bx]
    cmp al, [bz_rlog + BZR_MAT]
    jne .out
    mov ax, [bz_lsn]
    cmp ax, 0ffffh
    je .out
    mov si, bx                  ; entry K: bz_dat + BZD_ENT + 6K
    shl si, 1
    add si, bx
    shl si, 1
    mov cx, [bz_dat + BZD_ENT + 2 + si]
    jcxz .set
    cmp ax, cx
    jae .out
.set:
    mov [bz_dat + BZD_ENT + 2 + si], ax
    mov ax, [bz_lsf]
    mov [bz_dat + BZD_ENT + 4 + si], ax
    mov byte [bz_newb], 1
.out:
    ret

; bz_dload - the entry proc's read of BONANZA.DAT (SPEC.md 128.14.3.3), and
; [bz_dat] made this build's whole image whatever it found.  The file is
; HOSTILE (§19): exactly 64 bytes, then bz_dchk's whole-file checks
; (128.14.17 item 6) - any failure and it is treated as ABSENT; then
; bz_dnorm keeps an entry only under this build's identity with a best 1 -
; 65,534.  A missing file or folder is the first run: silent.  kern_small
; refuses at the launch keys (128.1), so it reads nothing.  Preserves nothing.
bz_dload:
    xor cl, cl
    cmp byte [bz_small], 0
    jne bz_dnorm
    push es
    push ds
    pop es
    mov si, bz_s_dat
    mov bx, bz_dat
    mov cx, BZD_SIZE
    xor dx, dx
    call od_read                ; (a file over 64 bytes is FERR_BIG before any
    pop es                      ; data is read: the image is untouched)
    mov cl, 0
    jc bz_dnorm
    or dx, dx
    jnz bz_dnorm
    cmp ax, BZD_SIZE
    jne bz_dnorm
    call bz_dchk
; CL = 1: keep what this build can file; 0: nothing (the first run's image)
bz_dnorm:
    mov word [bz_dat], 'BZ'     ; `BZT1`, the count, three zero bytes
    mov word [bz_dat + 2], 'T1'
    mov word [bz_dat + 4], BZ_NCRS
    mov word [bz_dat + 6], 0
    mov si, bz_dat + BZD_ENT
    xor bx, bx                  ; BX = 2K
.e:
    xor ax, ax                  ; the identity entry K is filed under: 0 for
    cmp bx, 2 * BZ_NCRS         ; BENCH's and past the courses
    jae .id
    or bx, bx
    jz .id
    mov ax, [bz_cids + bx]
.id:
    or ax, ax                   ; BENCH's entry and those past the courses are
    jz .clr                     ; ALWAYS zero, whatever the file filed under
    or cl, cl                   ; identity 0 there (a count-8 file's entry 6
    jz .clr                     ; would otherwise be kept, then written under
                                ; this build's count, and the next read would
                                ; refuse the whole file); a course identity is
                                ; never 0 (bbcourse asserts it)
    cmp ax, [si]                ; a course rebuilt with another identity
    jne .clr                    ; loses its best by itself
    mov dx, [si + 2]
    dec dx                      ; a best 1 - 65,534
    cmp dx, 0fffdh
    jbe .keep
.clr:
    mov word [si + 2], 0
    mov word [si + 4], 0
.keep:
    mov [si], ax
    add si, BZD_ENTB
    inc bx
    inc bx
    cmp bx, 2 * BZD_NENT
    jb .e
    or cl, cl                   ; THE TOUR: this build's XOR and a total 1 -
    jz .tclr                    ; 327,670
    cmp word [bz_dat + BZD_TOUR], BZ_CRS_TOURX
    jne .tclr
    mov ax, [bz_dat + BZD_TOUR + 2]
    mov dx, [bz_dat + BZD_TOUR + 4]
    sub ax, 1
    sbb dx, 0
    jc .tclr
    cmp dx, (BZ_TOURMAX - 1) >> 16
    ja .tclr
    jb .tok
    cmp ax, (BZ_TOURMAX - 1) & 0ffffh
    jbe .tok
.tclr:
    xor ax, ax
    mov [bz_dat + BZD_TOUR + 2], ax
    mov [bz_dat + BZD_TOUR + 4], ax
.tok:
    mov word [bz_dat + BZD_TOUR], BZ_CRS_TOURX
    mov word [bz_dat + BZD_TOUR + 6], 0
    ret

; bz_dchk - BONANZA.DAT's 64 bytes in [bz_dat], checked IN FULL (SPEC.md
; 128.14.17 item 6): `BZT1`; the count it was written with 1 - 8; +5 - +7
; zero; every entry's falls at most 9,999; every UNUSED entry (BENCH's, and
; K at or past the count) all zero; the tour's +6 zero.  -> CL = 1 it passes,
; 0 it is refused whole.  Clobbers AX, BX, SI.
bz_dchk:
    xor cl, cl
    cmp word [bz_dat], 'BZ'
    jne .out
    cmp word [bz_dat + 2], 'T1'
    jne .out
    mov al, [bz_dat + 4]
    dec al
    cmp al, BZD_NENT
    jae .out
    inc ax
    cmp byte [bz_dat + 5], 0
    jne .out
    cmp word [bz_dat + 6], 0
    jne .out
    mov si, bz_dat + BZD_ENT
    xor bl, bl                  ; K
.e:
    cmp word [si + 4], BZ_FALLMAX
    ja .out
    or bl, bl
    jz .z
    cmp bl, al
    jb .n
.z:
    cmp word [si], 0
    jne .out
    cmp word [si + 2], 0
    jne .out
    cmp word [si + 4], 0
    jne .out
.n:
    add si, BZD_ENTB
    inc bx
    cmp bl, BZD_NENT
    jb .e
    cmp word [bz_dat + BZD_TOUR + 6], 0
    jne .out
    inc cx
.out:
    ret

; bz_dsave - on the desktop after a launch: when the play set a best, the 64
; bytes to SYSTEM\APPDATA\BONANZA.DAT on the package's own volume (os88data.inc:
; the session's first save a full write, every later one a sector).  A save
; that fails - no folder, write-protected, full - toasts ONCE a session and
; the bests stay in memory (SPEC.md 128.14.3.3).  The save MERGES: the file is
; read again first (bz_dload, as hostile as at the entry) and the smaller best
; of the two kept per entry and for the tour, so a second instance - a
; double-clicked .BZR opens one - never overwrites the first's bests with its
; older copy.  Preserves nothing.
bz_dsave:
    cmp byte [bz_newb], 0
    je .out
    push es
    push ds
    pop es
    mov si, bz_dat              ; ours aside, the disk's read and made this
    mov di, bz_dmine            ; build's image (any failure: the first run's)
    mov cx, BZD_SIZE / 2
    rep movsw
    call bz_dload               ; (preserves ES)
    mov si, bz_dmine + BZD_ENT
    mov di, bz_dat + BZD_ENT
    mov cx, BZD_NENT            ; per entry (both carry this build's identities
.m:                             ; and zeros where no best is: 0 - 1 is the
    mov ax, [si + 2]            ; largest, so "none" never wins)
    dec ax
    mov dx, [di + 2]
    dec dx
    cmp ax, dx
    jae .mn
    mov ax, [si + 2]
    mov [di + 2], ax
    mov ax, [si + 4]
    mov [di + 4], ax
.mn:
    add si, BZD_ENTB
    add di, BZD_ENTB
    loop .m
    mov ax, [bz_dmine + BZD_TOUR + 2] ; the tour's total, 32 bits, the same way
    mov dx, [bz_dmine + BZD_TOUR + 4]
    sub ax, 1
    sbb dx, 0
    mov bx, [bz_dat + BZD_TOUR + 2]
    mov cx, [bz_dat + BZD_TOUR + 4]
    sub bx, 1
    sbb cx, 0
    cmp dx, cx
    ja .tk
    jb .tm
    cmp ax, bx
    jae .tk
.tm:
    add ax, 1
    adc dx, 0
    mov [bz_dat + BZD_TOUR + 2], ax
    mov [bz_dat + BZD_TOUR + 4], dx
.tk:
    mov si, bz_s_dat
    mov bx, bz_dat
    mov cx, BZD_SIZE
    mov di, bz_datst
    call od_write
    pop es
    jnc .out
    cmp byte [bz_datw], 0
    jne .out
    mov byte [bz_datw], 1
    mov si, bz_t_nosave
    jmp bz_toast
.out:
    ret

TOASTSTR bz_t_nosave, 'Best times not saved'

%define OD_TVOL bz_homevol      ; the volume BONANZA.O88 was launched from,
%include "os88data.inc"         ; banked at the entry (128.14.7.6), not where a
                                ; dialog has moved the instance since

; -----------------------------------------------------------------------------
; RECORDED DEMOS ON THE DISK (SPEC.md 128.14.7): W saves the held log, L loads
; one through the Open dialog, a double-clicked .BZR opens with BONANZA, V
; copies a shipped demo part into the log, D benchmarks it - and HOME, where
; every part is read from (128.14.7.6).
; -----------------------------------------------------------------------------
; bz_home - stand where BONANZA.O88 was launched from before a part is read out
; of it: op_fetch reads the package BY NAME in the instance's folder, which the
; Save and Open dialogs and a double-clicked document MOVE (SPEC.md 38.10).
; OSAPI_FILE_HERE is no I/O, so a fetch from home costs a compare; a move is a
; quiet OSAPI_FILE_GOTO_QM each way (PIXEL's px_pfetch).  CF = 1: home cannot
; be stood in (its disk is out) - toasted, NOTHING moved, nothing is to be
; fetched (a part read out of whatever BONANZA.O88 stands here would be worse).
; [bz_hmov] = 1 when it moved, for bz_back.  Preserves all but AX and the flags.
bz_home:
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov byte [bz_hmov], 0
    call OSAPI_FILE_HERE
    mov [bz_awdir], dx
    mov [bz_awvol], bl
    cmp dx, [bz_homedir]
    jne .go
    cmp bl, [bz_homevol]
    je .out                     ; (equal: CF = 0)
.go:
    mov dx, [bz_homedir]
    mov bl, [bz_homevol]
    call OSAPI_FILE_GOTO_QM
    jc .refused
    mov byte [bz_hmov], 1
    jmp short .out              ; (CF = 0)
.refused:
    mov si, bz_t_out
    call bz_toast
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; bz_back - back where bz_home found the user, so the next dialog opens in the
; folder last used.  Preserves every register and the flags.
bz_back:
    pushf
    cmp byte [bz_hmov], 0
    je .out
    mov byte [bz_hmov], 0
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov dx, [bz_awdir]
    mov bl, [bz_awvol]
    call OSAPI_FILE_GOTO_QM     ; (a failure moved nothing: we stay home)
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
.out:
    popf
    ret

; S on the desktop: the sound's own key (bzsound.inc bzs_skey), whose title is
; fetched - so at home, as bz_launch's fetches are (SPEC.md 128.14.10's two
; sound fetches: bzs_gfetch inside bz_launch's home, bzs_dstart here and in
; the entry proc, which runs at home)
bz_skey:
    call bz_home
    jc .out
    call bzs_skey
    jmp bz_back
.out:
    ret

; CF = 1 on kern_small, its refusal toasted (SPEC.md 128.1, 128.14.3.4).
; Clobbers what bz_toast does.
bz_bigok:
    cmp byte [bz_small], 0
    je .out                     ; (CF = 0)
    mov si, bz_t_small
    call bz_toast
    stc
.out:
    ret

; D (one press): THE DEMO BENCHMARK, bz_mode 3 - the held log replayed and
; measured (SPEC.md 128.14.7.3)
bz_dkey_d:
    call bz_bigok
    jc .out
    call bz_rhave
    jne .out
    mov al, 3
    mov ah, [bz_rlog + BZR_CRS]
    jmp bz_go
.out:
    ret

; W (one press): the held log through the SAVE dialog as `<NAME>.BZR` (SPEC.md
; 128.14.7.1); bz_wdone writes it.  A tour's held log is the course just
; played.  A dialog already up refuses, and that dialog is the answer.
bz_wkey:
    call bz_bigok
    jc .out
    call bz_rhave
    jne .out
    mov al, [bz_rlog + BZR_CRS] ; (the session's log: its course is in range)
    mov ah, BZ_CRS_NAMEB
    mul ah
    add ax, bz_cnames
    xchg ax, si
    mov di, bz_dname
.c:
    lodsb
    or al, al
    jz .e
    mov [di], al
    inc di
    jmp .c
.e:
    mov word [di], '.B'
    mov word [di + 2], 'ZR'
    mov byte [di + 4], 0
    mov al, FDLG_SAVE
    mov si, bz_dname
    mov di, bz_wdone
.dlg:
    mov bx, [bz_win]
    call OSAPI_FILE_DLG
.out:
    ret

; L (one press): a log through the OPEN dialog (SPEC.md 128.14.7.2)
bz_lkey:
    call bz_bigok
    jc bz_wkey.out
    mov al, FDLG_OPEN
    xor si, si
    mov di, bz_ldone
    jmp bz_wkey.dlg

; W's completion (SPEC.md 38.6: AL = 1, DI = the name in the kernel's segment,
; ES; the instance stands in the folder chosen): the log's bytes AS THEY ARE -
; the file IS the log, `16 + 2 N` or `16 + 3 N` bytes - and a toast either way
bz_wdone:
    call bz_gname
    push ds
    pop es
    mov di, bz_rlog
    call bz_esz                 ; CX = the held log's bytes
    mov si, bz_dname
    mov bx, bz_rlog
    xor dx, dx
    call OSAPI_FILE_WRITE
    mov si, bz_t_saved
    jnc bz_toast
; AX = a FERR_*: the kernel's own words for it, toasted
bz_ftoast:
    call OSAPI_FERR_TEXT
    xor cx, cx
    call OSAPI_TOAST
    ret

; L's completion (AL = 0, DI = the name, DX:CX its size, which is what the
; read will deliver, 38.6.1).  Refused BEFORE THE DISK IS TOUCHED, in this
; order: not `.BZR`, then a size under 16 or over 4,096 - `Not a Bonanza
; demo`; then bz_lfile claims exactly the size, reads, checks and copies.
bz_ldone:
    push cx
    push dx
    call bz_gname
    pop dx
    pop cx
    call bz_isbzr
    jc .not
    or dx, dx
    jnz .not
    cmp cx, BZR_RUNS
    jb .not
    cmp cx, BZR_SIZE
    ja .not
    xor al, al                  ; the size is the dialog's: exact
    call bz_lfile
    jc .out
    jmp bz_dheld
.not:
    mov si, bz_t_notbzr
    jmp bz_toast
.out:
    ret

; ES:DI = a NUL name of at most 12 characters (the kernel's) -> [bz_dname].
; Clobbers AX, CX, SI, DI.
bz_gname:
    mov si, bz_dname
    mov cx, 12
.c:
    mov al, [es:di]
    inc di
    mov [si], al
    inc si
    or al, al
    jz .out
    loop .c
    mov [si], cl                ; (a 12-character name: its NUL)
.out:
    ret

; CF = 0 when [bz_dname]'s extension is `BZR`.  Clobbers AL, SI.
bz_isbzr:
    mov si, bz_dname
.f:
    lodsb
    or al, al
    jz .no
    cmp al, '.'
    jne .f
    cmp word [si], 'BZ'
    jne .no
    cmp word [si + 2], 'R'      ; `R` and the NUL
    je .out                     ; (equal: CF = 0)
.no:
    stc
.out:
    ret

; ES:DI = a log -> CX = its bytes, `16 + 2 N` or with TILT `16 + 3 N`.
; Clobbers AX.
bz_esz:
    mov cx, [es:di + BZR_NRUN]
    mov ax, cx
    shl cx, 1
    test byte [es:di + BZR_FLAGS], BZR_TILT
    jz .p
    add cx, ax
.p:
    add cx, BZR_RUNS
    ret

; -----------------------------------------------------------------------------
; bz_lfile - a demo FILE, which is HOSTILE (SPEC.md 19, 128.14.7.2): [bz_dname]
; in the instance's folder, CX its size (L: the dialog's, 16 - 4,096, AL = 0)
; or the read's capacity (the double-click: 4,096, AL = 1, 128.14.7.5), read
; into a TRANSIENT claim of exactly CX bytes (pinned, held for this call
; alone) and CHECKED IN FULL (bz_lchk) before a byte reaches bz_rlog, so a
; refused file leaves the session's log as it was and fetches no part.  The
; claim is an LDT selector on kern_mega: read into at ES:0, checked through
; [es:], copied whole - never added to (128.14.13).  CF = 0: the log is the
; file's, [bz_lsv] 2 and [bz_lfn] its name; CF = 1: refused and toasted.
; Preserves nothing.
; -----------------------------------------------------------------------------
bz_lfile:
    mov [bz_lcap], al
    mov [bz_lfsz], cx
    mov ax, cx
    add ax, 15
    mov cl, 4
    shr ax, cl
    push ax                     ; ASKED first (os88api.inc, SPEC.md 38.6): a
    mov bl, MEMP_AVAIL          ; claim that fails SHEDS the disk caches on its
    call OSAPI_MEM_P            ; way down, so a size past the largest run is
    pop dx                      ; refused with nothing claimed, shed or read
    mov si, bz_t_nomem
    cmp ax, dx
    jb .toast
    xchg ax, dx
    mov bl, MEMP_CLAIM          ; EXACTLY the size
    call OSAPI_MEM_P
    jc .toast

    mov [bz_lseg], dx
    push es
    mov es, dx
    xor bx, bx
    mov cx, [bz_lfsz]
    xor dx, dx
    mov si, bz_dname
.read:                          ; (a row's breakpoint: the disk is touched here)
    call OSAPI_FILE_READ        ; DX:AX = the bytes read (at most CX)
    jc .rerr
    mov si, bz_t_dmg
    or dx, dx
    jnz .ref
    cmp byte [bz_lcap], 0
    je .exact
    mov [bz_lfsz], ax            ; the double-click: the size IS the bytes read,
    mov si, bz_t_notbzr         ; refused under 16
    cmp ax, BZR_RUNS
    jb .ref
    jmp short .chk
.exact:
    cmp ax, [bz_lfsz]            ; 1: the bytes the dialog said
    jne .ref
.chk:
    call bz_lchk                ; 2 - 8
    or si, si
    jnz .ref
    mov cx, [bz_lfsz]            ; PASSED: the bytes into the log
    cld
    push ds
    push ds
    push es
    pop ds                      ; DS = the claim, ES = ours
    pop es
    xor si, si
    mov di, bz_rlog
    rep movsb
    pop ds
    call .free
    pop es
    mov byte [bz_lsv], 2        ; the face's log line: the file's name
    mov si, bz_dname
    mov di, bz_lfn
    mov cx, 13
.n:
    lodsb
    mov [di], al
    inc di
    loop .n
    clc
    ret
.rerr:
    mov si, bz_t_notbzr         ; FERR_BIG: over the capacity, decided from
    cmp ax, FERR_BIG            ; the directory entry before any data I/O
    je .ref
    call .free
    pop es
    call bz_ftoast              ; a disk's refusal, in the kernel's words
    stc
    ret
.ref:
    call .free
    pop es
.toast:
    call bz_toast
    stc
    ret
.free:
    mov dx, [bz_lseg]
    call OSAPI_MEM_FREE
    mov word [bz_lseg], 0
    ret

; bz_lchk - 128.14.7.2's checks 2 - 8 on the log at ES:0, [bz_lfsz] bytes (16 -
; 4,096: check 1 is the caller's, so the header is inside it).  -> SI = 0 it
; passed, else the toast: `Demo from other physics` (5) or `Damaged demo file`.
; K indexes BZ_CRS_IDS only once bounded, and no run is read before N is tied
; to the length.  Clobbers AX, BX, CX, DX, DI, BP (a register here: no [bp]).
bz_lchk:
    mov si, bz_t_dmg
    cmp word [es:0], 'BZ'       ; 2: the magic
    jne .out
    cmp word [es:2], 'R1'
    jne .out
    mov bl, [es:BZR_CRS]        ; 3: the course, the material, the flags
    cmp bl, BZ_NCRS
    jae .out
    cmp byte [es:BZR_MAT], BZ_NMAT
    jae .out
    test byte [es:BZR_FLAGS], ~(BZR_DONE | BZR_TRUNC | BZR_TILT) & 0ffh
    jnz .out
    xor bh, bh                  ; 4: the course's IDENTITY, this build's
    shl bx, 1
    mov ax, [bz_cids + bx]
    cmp ax, [es:BZR_ID]
    jne .out
    mov si, bz_t_phys           ; 5: the PHYSICS identity
    cmp byte [es:BZR_PHYS], BZ_PHYSV
    jne .out
    mov si, bz_t_dmg
    mov cx, [es:BZR_NRUN]       ; 6: N >= 1, the size exactly 16 + w N
    jcxz .out
    cmp cx, (BZR_SIZE - BZR_RUNS) / 2
    ja .out
    mov ax, cx
    shl ax, 1
    mov dx, 2                   ; DX = w
    test byte [es:BZR_FLAGS], BZR_TILT
    jz .w
    add ax, cx
    inc dx
.w:
    add ax, BZR_RUNS
    cmp ax, [bz_lfsz]
    jne .out
    xor ax, ax                  ; BP:AX = the runs' counts, summed in 32 bits
    xor bp, bp
    mov di, BZR_RUNS
.run:
    test byte [es:di], 80h      ; 8: a key byte's bit 7 clear ...
    jnz .out
    cmp dl, 3
    jne .cnt
    mov bl, [es:di + 1]         ; ...a tilt byte's nibbles each 0 - 8 ...
    cmp bl, (BZ_LVLMAX + 1) << 4
    jae .out
    and bl, 0fh
    cmp bl, BZ_LVLMAX
    ja .out
.cnt:
    add di, dx
    mov bl, [es:di - 1]         ; ...a count 1 - 255
    or bl, bl
    jz .out
    xor bh, bh
    add ax, bx
    adc bp, 0
    loop .run
    cmp ax, [es:BZR_STEPS]      ; 7: the steps, the runs' sum
    jne .out
    cmp bp, [es:BZR_STEPS + 2]
    jne .out
    xor si, si
.out:
    ret

; the entry proc's: the document this instance was launched to open (SPEC.md
; 54.5), READ AND CLEARED and its name copied out while ES is the kernel's -
; RECORDED only: bz_onwake reads it once the window is up (SPEC.md 54.10)
bz_argget:
    call OSAPI_ARG_FILE
    jc .out
    mov [bz_argdir], dx
    mov [bz_argvol], bl
    mov di, si
    call bz_gname
    mov byte [bz_argp], 1
.out:
    ret

; a DOUBLE-CLICKED .BZR (SPEC.md 128.14.7.5): no size comes with it, so the
; read is bounded by its CAPACITY - 4,096, FERR_BIG decided from the directory
; before any data is read - and its bytes are the size.  Not .BZR refused; the
; document's folder stood in; bz_lfile's claim, read, checks and copy; home
; again.  A refusal toasts and the window keeps no log.  kern_small (no
; associations, the game refused) reads nothing.  -> CF = 0 a log was loaded.
bz_argdemo:
    cmp byte [bz_small], 0
    jne .no
    call bz_isbzr
    mov si, bz_t_notbzr
    jc .toast
    mov dx, [bz_argdir]
    mov bl, [bz_argvol]
    call OSAPI_FILE_GOTO_QM
    jc .ftoast
    mov al, 1
    mov cx, BZR_SIZE
    call bz_lfile
    pushf
    mov dx, [bz_homedir]
    mov bl, [bz_homevol]
    call OSAPI_FILE_GOTO_QM
    popf
    ret
.toast:
    call bz_toast
    jmp short .no
.ftoast:
    call bz_ftoast
.no:
    stc
    ret

; W_ONWAKE (SPEC.md 74.1): a document launch's SECOND phase (SPEC.md 54.10) -
; the window is on the glass, the gfx lock is not held, and the file slots
; may be called.  A wake with no document pending is a stale kick: nothing.
; A log loaded is shown on the face's lines 5, 6 and 12 (bz_dheld).
bz_onwake:
    SAVE
    cmp byte [bz_argp], 0
    je .done
    mov byte [bz_argp], 0       ; (spent once, whatever its read does)
    call bz_argdemo
    jc .done
    call bz_dheld
.done:
    RESTORE
    ret

; V (one press, not in a tour): the next SHIPPED demo, 1 - 5 in turn, into the
; held log (SPEC.md 128.14.7.4) - its part fetched at home, copied whole (a
; PART is trusted: the tool checked it, 128.10.6.2) and dropped.  It replaces
; the session's last log, as a new play does.
bz_vkey:
    call bz_bigok
    jc .out
    call bz_home
    jc .out
    mov al, [bz_vk]
    add al, BZ_P_DEMO
    mov [bz_pc], al
    call op_fetch
    jc .back
    mov al, [bz_pc]
    call op_seg
    push es
    mov es, ax
    xor di, di
    call bz_esz
    cld
    push ds
    push ds
    push es
    pop ds                      ; DS = the part, ES = ours
    pop es
    xor si, si
    mov di, bz_rlog
    rep movsb
    pop ds
    pop es                      ; (op_fetch left ES the part's own selector:
    push ds                     ; op_drop restores its caller's ES after the
    pop es                      ; free, a #GP on kern_mega - ES = ours, as
    mov al, [bz_pc]             ; bz_fullscreen's .drop; the final pass of
    call op_drop                ; wave 4: bonanzamega's fault in V)
    mov byte [bz_lsv], 3
    inc byte [bz_vk]
    cmp byte [bz_vk], BZ_NDEMO
    jb .shown
    mov byte [bz_vk], 0
.shown:
    call bz_back
    jmp short bz_dheld
.back:
    jmp bz_back                 ; (op_fetch toasted why)
.out:
    ret

; a new held log (L, V): the lines that name it and offer its keys - the demo
; keys, the log's line, and line 12's refused-replay reason, now stale
bz_dheld:
    mov byte [bz_err], 0
    mov si, bz_heldl
    jmp bz_redraw
bz_heldl:   db 5, 6, 12, 0ffh

; T (one press, in a tour too): the control, KEYS or MOUSE (SPEC.md 128.14.8)
bz_tkey:
    xor byte [bz_ctl], 1
    mov si, bz_tlines
    jmp bz_redraw
bz_tlines:  db 3, 6, 0ffh

TOASTSTR bz_t_out, "Bonanza's disk is out"
TOASTSTR bz_t_saved, 'Demo saved'
TOASTSTR bz_t_notbzr, 'Not a Bonanza demo'
TOASTSTR bz_t_dmg, 'Damaged demo file'
TOASTSTR bz_t_phys, 'Demo from other physics'
TOASTSTR bz_t_nomem, 'Bonanza: no memory'

; --- the window -----------------------------------------------------------------
bz_tpl: dw 40, 24, 344, 168, bz_title, bz_cls
; its CLASS (SPEC.md 11.104): every handler; WF_OWNBG, the face paints every pixel
    OS88_CLASS bz_cls, WF_OWNBG, PAINT, bz_paint, ONKEY, bz_onkey, \
               ONCLICK, bz_click, ABOUT, bz_about, ONTIMER, bz_ontimer, \
               ONWAKE, bz_onwake
bz_title: db 'Bounce Bonanza',0
bz_credits: dw bz_title,bz_credit1,bz_credit2,bz_credit3,0
bz_credit1: db 'Isometric rolling-ball game',0
bz_credit2: db 'Wave 4: a game',0
bz_credit3: db 'Generated art, original design',0

; the face's strings: BZS measures each (<label>_n), for BZ_FIT below
%macro BZS 2
%1: db %2
%%e: db 0
%assign %{1}_n %%e - %1
%endmacro
BZS bz_s_title, 'BOUNCE BONANZA'
BZS bz_s_keys,  'G GAME  ENTER '
BZS bz_s_nk,    '  N NEXT'
BZS bz_s_tkeys, 'ENTER next  ESC stop tour'
BZS bz_s_sndk,  'S SOUND '
bz_s_smodes: dw bz_s_sauto, bz_s_sspkf, bz_s_sfx, bz_s_soff
BZS bz_s_sauto, 'AUTO'
BZS bz_s_sspkf, 'SPEAKER'
BZS bz_s_sfx,   'EFFECTS ONLY'
BZS bz_s_soff,  'OFF'
BZS bz_s_sfm,   ': ADLIB'
BZS bz_s_sspk,  ': SPEAKER'
BZS bz_s_benk,  'B BENCH'
BZS bz_s_repk,  'R PLAY  D TIME  '
BZS bz_s_savk,  'W SAVE'
BZS bz_s_ldk,   '  L LOAD  V DEMO'
BZS bz_s_ctlk,  '  T '
BZS bz_s_keyb,  'KEYS'
BZS bz_s_mouse, 'MOUSE'
bz_ctitles: BZ_CRS_TITLES       ; the courses' titles, BZ_CRS_TITLEB bytes each
bz_cnames:  BZ_CRS_NAMES        ; ...their NAMEs, BZ_CRS_NAMEB bytes each
bz_cballs:  BZ_CRS_BALLS        ; ...their balls, a byte each
bz_cncks:   BZ_CRS_NCKS         ; ...their flags, a byte each
bz_cpars:   BZ_CRS_PARS         ; ...their pars, whole seconds, a word each
bz_cids:    BZ_CRS_IDS          ; ...their identities, a word each
BZS bz_s_cga,   'Adapter: CGA, 320x200 four colours'
BZS bz_s_herc,  'Adapter: Hercules, 360x200 pair pixels'
BZS bz_s_noad,  'CGA OR HERC ONLY'
BZS bz_s_small, 'NEEDS MORE MEMORY (128KB kernel)'
BZS bz_s_camk,  'C '
BZS bz_s_ballk, '  M '
bz_s_mats:  dw bz_s_rubber, bz_s_steel, bz_s_glass
BZS bz_s_rubber, 'RUBBER'
BZS bz_s_steel, 'STEEL'
BZS bz_s_glass, 'GLASS'
bz_s_cmodes: dw bz_s_glide, bz_s_trickle   ; bz_cmode's (SPEC.md 128.11.11.1)
BZS bz_s_glide, 'GLIDE'
BZS bz_s_trickle, 'TRICKLE'
BZS bz_s_hint,  'Arrows roll  Space hop  L.Shift grip'
BZS bz_s_mhint, 'Mouse tilts  left hop  right grip'
BZS bz_s_demo,  'demo'
BZS bz_s_secs,  ' s '
bz_s_ends:  dw bz_s_estop, bz_s_egoal, bz_s_ecup
BZS bz_s_estop, 'stop'
BZS bz_s_egoal, 'goal'
BZS bz_s_ecup,  'cup'
BZS bz_s_falls, ' falls '
BZS bz_s_flags, ' flags '
BZS bz_s_par,   'par '
BZS bz_s_best,  'best '
BZS bz_s_tnext, 'ENTER next: '
BZS bz_s_tstop, 'Tour stopped'
BZS bz_s_tour,  'Tour '
BZS bz_s_best2, '  best '
BZS bz_s_clamp, '20:00+'
BZS bz_s_err,   'The full screen mode was refused'
BZS bz_s_err2,  "The window's display changed"
BZS bz_s_err3,  "Another course's log"
BZS bz_s_err4,  "Other physics' log"
BZS bz_s_cgar,  'CGA frames '
BZS bz_s_hercr, 'Herc frames '
BZS bz_s_disp,  '  '
BZS bz_s_hz,    ' Hz  misses '
BZS bz_s_meas,  'BENCH autopilot'
BZS bz_s_dmeas, 'Demo '
BZS bz_s_trunc, 'TRUNCATED'
BZS bz_s_back,  'Any key: back'
BZS bz_s_worst, 'Worst '
BZS bz_s_mean,  ' clk   means (GLIDE):'
BZS bz_s_clk,   ' clk'
BZS bz_s_cols,  'col '
BZS bz_s_rows,  ' row '
BZS bz_s_full,  ' full '
BZS bz_s_late,  ' late '
bz_s_parts: dw bz_s_p0, bz_s_p1, bz_s_p2, bz_s_p3, bz_s_p4, bz_s_p5
BZS bz_s_p0,    '  sim+camera     '
BZS bz_s_p1,    '  box compose    '
BZS bz_s_p2,    '  rows           '
BZS bz_s_p3,    '  retrace (idle) '
BZS bz_s_p4,    '  flip+columns   '
BZS bz_s_p5,    '  box write      '
bz_s_dat:   db 'BONANZA.DAT', 0

; EVERY FACE LINE FITS THE CGA's 42 CELLS (SPEC.md 128.14.17 item 2): each
; builder's widest line - the margin cell, its strings, its fields at their
; widest (a word 5 digits, a DWORD 10, a time BZ_TIMEW, the longest title and
; NAME and the widest par as bzcourse.inc measures them) - or the build fails.
%macro BZ_FIT 2
 %assign %%w %2
 %if %%w > BZ_FACEW
  %error face line %1 is %[%%w] cells and the CGA content holds BZ_FACEW (SPEC.md 128.14.17 item 2)
 %endif
%endmacro
%assign BZ_SNDW bz_s_sauto_n
%if bz_s_sspkf_n > BZ_SNDW
 %assign BZ_SNDW bz_s_sspkf_n
%endif
%if bz_s_sfx_n > BZ_SNDW
 %assign BZ_SNDW bz_s_sfx_n
%endif
%if bz_s_sfm_n > bz_s_sspk_n
 %assign BZ_SNDW BZ_SNDW + bz_s_sfm_n
%else
 %assign BZ_SNDW BZ_SNDW + bz_s_sspk_n
%endif
BZ_FIT 0, 1 + bz_s_title_n
BZ_FIT 1, 1 + bz_s_keys_n + BZ_CRS_TITLEW + bz_s_nk_n
BZ_FIT 1t, 1 + bz_s_tkeys_n
BZ_FIT 2, 1 + bz_s_cga_n
BZ_FIT 2h, 1 + bz_s_herc_n
BZ_FIT 2s, 1 + bz_s_small_n
BZ_FIT 2e, 1 + bz_s_err_n
BZ_FIT 2d, 1 + bz_s_err2_n
BZ_FIT 3, 1 + bz_s_camk_n + bz_s_trickle_n + bz_s_ballk_n + bz_s_rubber_n + bz_s_ctlk_n + bz_s_mouse_n
BZ_FIT 4, 1 + bz_s_sndk_n + BZ_SNDW
BZ_FIT 5, 1 + bz_s_repk_n + bz_s_savk_n + bz_s_ldk_n
BZ_FIT 5b, 1 + bz_s_benk_n + bz_s_ldk_n
BZ_FIT 6, 1 + bz_s_hint_n
BZ_FIT 6m, 1 + bz_s_mhint_n
BZ_FIT 6f, 1 + BZ_CRS_NAMEW + 1 + BZ_TIMEW + bz_s_secs_n + 1 + 12
BZ_FIT 6l, 1 + BZ_CRS_NAMEW + 1 + BZ_TIMEW + bz_s_secs_n + bz_s_estop_n + bz_s_falls_n + 4 + bz_s_flags_n + 3
BZ_FIT 7, BZ_SC_BEST + bz_s_best_n + BZ_TIMEW
%if BZ_SC_NAME + BZ_CRS_NAMEW >= BZ_SC_TIME || BZ_SC_TIME + BZ_TIMEW + 1 >= BZ_SC_FALL || BZ_SC_FALL + 5 >= BZ_SC_PAR || BZ_SC_PAR + bz_s_par_n + BZ_CRS_PARW >= BZ_SC_BEST
 %error "the scorecard's fields overrun their columns (bz_sc)"
%endif
BZ_FIT 12, 1 + bz_s_tnext_n + BZ_CRS_TITLEW
BZ_FIT 12t, 1 + bz_s_tour_n + BZ_TIMEW + bz_s_best2_n + BZ_TIMEW
BZ_FIT 12e, 1 + bz_s_err3_n
BZ_FIT 12p, 1 + bz_s_err4_n
BZ_FIT 12s, 1 + bz_s_tstop_n
BZ_FIT r2, 1 + bz_s_hercr_n + 5 + bz_s_disp_n + 5 + bz_s_hz_n + 5
BZ_FIT r3, 1 + bz_s_meas_n
BZ_FIT r3d, 1 + bz_s_dmeas_n + BZ_CRS_NAMEW + 1 + BZ_TIMEW + bz_s_secs_n + bz_s_trunc_n
BZ_FIT r4, 1 + bz_s_worst_n + 10 + bz_s_mean_n
BZ_FIT r5, 1 + bz_s_p0_n + 10 + bz_s_clk_n
BZ_FIT r11, 1 + bz_s_cols_n + 5 + bz_s_rows_n + 5 + bz_s_full_n + 5 + bz_s_late_n + 5
BZ_FIT r12, 1 + bz_s_back_n
%if bz_s_estop_n < bz_s_egoal_n || bz_s_estop_n < bz_s_ecup_n || bz_s_trickle_n < bz_s_glide_n || bz_s_rubber_n < bz_s_steel_n || bz_s_rubber_n < bz_s_glass_n || bz_s_p0_n != bz_s_p5_n || bz_s_hercr_n < bz_s_cgar_n || bz_s_mouse_n < bz_s_keyb_n || bz_s_demo_n > 12
 %error "BZ_FIT measures each line by its widest choice: the choices above moved"
%endif

%include "bzvideo.inc"
%include "bzgame.inc"
%include "bzwheel.inc"
%include "bzphys.inc"
%include "bzsound.inc"
%if 4 * BZ_BOXB < 512
 %error "bz_hgen: BZ_HTAB's 512 bytes do not fit bz_boxbuf"
%endif

; --- the part table (SPEC.md 128.11.3.1, 20.12) --------------------------------
; 3 + BZ_NCRS + 1 + BZS_NSONG + BZ_NDEMO rows, in the Makefile's BZ_PARTS
; order, every one OP_LAZY | OP_COMP: the three balls, then each course
; (BZ_COURSES's order, bzcourse.inc's rows, every one the CGA's), the sound
; and its songs, and a shipped demo a tour course.  Fetched by bz_launch on the desktop (op_fetch,
; 1942's pattern) and dropped when the bracket returns.
OS88_PARTS_BEGIN 3 + BZ_NCRS + 1 + BZS_NSONG + BZ_NDEMO
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; 0  BZBALR.BIN  rubber
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; 1  BZBALS.BIN  steel
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; 2  BZBALG.BIN  glass
    BZ_CRS_PARTS                            ; 3 + K: BZ<K>.BIN
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ_P_SND: BZSND.BIN (128.20.3)
 %rep BZS_NSONG
    OS88_PART OP_ASSET, OP_LAZY | OP_COMP   ; BZ_P_SONG + S: BZM<S>.BIN
 %endrep
    BZ_DEMO_PARTS                           ; BZ_P_DEMO + K - 1: BZD<K>.BIN (128.14.7.4)
OS88_PARTS_END
%if BZ_P_DEMO != 3 + BZ_NCRS + 1 + BZS_NSONG || BZ_NDEMO != BZ_NCRS - 1
 %error "the demo rows follow the songs', one a tour course (SPEC.md 128.14.7.4)"
%endif

%define OS88UI_ABOUT
%define OS88UI_NOBTN
%include "os88ui.inc"
%include "os88alt.inc"

%assign BZ_BSS OP_BSS           ; the parts standard's bss comes first
%macro VAR 2
 %1 equ os88_image_end + BZ_BSS
 %assign BZ_BSS BZ_BSS + %2
%endmacro
; the desktop side
VAR bz_win,2
VAR bz_abon,1
VAR bz_small,1                  ; 1 = kern_small (no timer slot): refused
VAR bz_page,1                   ; the face's page: 0 MAIN, 1 RESULTS (128.14.3.2)
VAR bz_pgo,1                    ; 1: this key left RESULTS (or a refused replay):
                                ; bz_onkey repaints MAIN whole after it
VAR bz_pc,1                     ; the course's part row (BZ_P_CRS + K)
VAR bz_pb,1                     ; ...and the starting ball's (BZ_P_BALR + [bz_mat])
VAR bz_pbm,1                    ; the balls a launch fetches: a bit a material
VAR bz_crsel,1                  ; the course Enter plays (N): FIRST, TRIAL, ...
VAR bz_matsel,1                 ; the ball a play rolls (M; N sets the course's)
VAR bz_mat,1                    ; THIS launch's material, 0 rubber, 1 steel,
                                ; 2 glass (bz_launch; bz_pinit copies its
                                ; BZ_MATTAB record, SPEC.md 128.11.5.2)
VAR bz_dkk,1                    ; the held-key guard: the make code of the C, M
                                ; or N not yet seen up, 0 none (128.11.11.2)
VAR bz_fw,2                     ; the face: content width, height, origin
VAR bz_fh,2
VAR bz_ox,2
VAR bz_oy,2
VAR bz_fcells,2
VAR bz_fy,2
VAR bz_lbuf,BZ_LMAX + 2
; the game (SPEC.md 128.14.3): the tour, the held log's line, the bests
VAR bz_ttime,2 * BZ_NTOUR       ; the tour's steps a course, 0 none (bz_game
VAR bz_tfall,2 * BZ_NTOUR       ; clears both: keep them together) and falls
VAR bz_homedir,2                ; where BONANZA.O88 was launched from: its
                                ; folder (128.14.7.6) ...
VAR bz_lsn,2                    ; line 6: the last play's or replay's steps
VAR bz_lsf,2                    ; ...its falls (to 9,999)
VAR bz_dmine,BZD_SIZE           ; bz_dsave's: ours, while the disk's is merged in
VAR bz_dat,BZD_SIZE             ; BONANZA.DAT's image, always this build's whole
                                ; file (bz_dnorm): what the face shows and the
                                ; save writes
VAR bz_homevol,1                ; ...and its volume (os88data.inc's OD_TVOL)
VAR bz_tour,1                   ; 0 none, k 1 - 5 course k next or playing, 6
                                ; finished, 7 stopped (128.14.3.1)
VAR bz_lsv,1                    ; line 6: 1 = a play or a replay ran (bz_post)
VAR bz_lsk,1                    ; ...its course
VAR bz_lsc,1                    ; ...the flags it reached
VAR bz_lsend,1                  ; ...0 stopped, 1 the goal line, 2 the cup
VAR bz_newb,1                   ; 1: this launch's play set a best (bz_post)
VAR bz_datst,1                  ; od_write's state byte for BONANZA.DAT
VAR bz_datw,1                   ; 1: the failed save was toasted this session
VAR bz_pkey,1                   ; FFh while P is HELD since its last edge (PAUSE)
VAR bz_ptyp,1                   ; 1: bz_exitchk took a typed P (bz_kedge)
VAR bz_btyp,1                   ; ...and a typed Backspace (RETURN)
; the demos on the disk and the mouse (SPEC.md 128.14.7, 128.14.8)
VAR bz_awdir,2                  ; bz_home: where the user was, to go back to
VAR bz_lseg,2                   ; L's and the double-click's staging claim, 0 none
VAR bz_lfsz,2                    ; ...its size, then the bytes read
VAR bz_argdir,2                 ; the double-clicked document's folder ...
VAR bz_dname,14                 ; a demo file's name: W's default, the dialog's
                                ; answer, the double-click's (12 and a NUL)
VAR bz_lfn,14                   ; ...and the loaded log's, for the face's line 6
VAR bz_awvol,1                  ; ...bz_home's volume to go back to
VAR bz_hmov,1                   ; 1: bz_home moved the instance
VAR bz_argvol,1                 ; ...the document's volume
VAR bz_argp,1                   ; 1: a document came with the launch
VAR bz_lcap,1                   ; bz_lfile: 1 the read is bounded by its capacity
VAR bz_vk,1                     ; V: the next shipped demo, 0 - BZ_NDEMO - 1
VAR bz_ctl,1                    ; T: the control, 0 KEYS, 1 MOUSE (the session's)
VAR bz_dtr,1                    ; D stopped measuring at 65,535 frames (128.14.7.3)
VAR bz_rw,1                     ; the held log's run width: 2, or 3 with TILT
VAR bz_tilt,1                   ; the frame's TILT BYTE, capx << 4 | capy: 88h a
                                ; keyboard play's (bz_input, SPEC.md 128.14.8.2)
VAR bz_tby,1                    ; the STEP's tilt byte (bz_step: the play's
                                ; frame's, the replay's run's, 88h the autopilot's)
VAR bz_tanc,1                   ; 1: anchor the stick at the next frame
VAR bz_tarm,1                   ; 1: the stick has been in its dead zone
VAR bz_apilot,1                 ; a HARNESS byte, never set by the package: a
                                ; play takes its key bytes from the autopilot
                                ; (bzphys.inc bz_step; bonanzagame, 128.14.14)
VAR bz_tax,BZT_SIZE             ; the stick's x axis (bzgame.inc bz_tmouse) ...
VAR bz_tay,BZT_SIZE             ; ...and its y axis
%if bz_tfall != bz_ttime + 2 * BZ_NTOUR || (BZ_BSS & 1)
 %error "bz_game clears bz_ttime and bz_tfall as one run; the game's VARs stay even"
%endif
; the engine's (bzgame.inc's head documents the ones a harness reads)
BZ_GAME_VARS
BZ_PHYS_VARS
BZ_SND_VARS
VAR bz_rlog,BZR_SIZE                ; THE REPLAY LOG (SPEC.md 128.11.12.1): `BZR1`,
                                ; the course (+4), the material (+5), flags,
                                ; the steps, the runs.  The recorder writes
                                ; it; R replays it (bz_rhave)
OS88_BSS BZ_BSS
OS88_IMAGE_END
