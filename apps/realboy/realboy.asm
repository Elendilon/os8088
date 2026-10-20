; =============================================================================
; os8088 - apps/realboy/realboy.asm
;
; REALBOY: a Game Boy in a window (docs/REALBOY-SPEC.md section 14). The
; core is parts 0 and 1 of this file - 64KB of generated SM83 handlers,
; apps/realboy/rbgen.py's, in two halves one segment apart - and the view the
; Game Boy's memory lives in is part 2, a zeroed 64KB carve; the cartridge is
; a claim of its own size.
; rbsys.inc runs the machine, rbppu.inc composes its frame, and this file is
; the window round them: open a .GB, run it to the wall clock in a worker,
; and put each frame it has time for on the glass.
;
; THE WORKER owns the machine. It counts BIOS ticks into Game Boy frames
; owed (59.7275 Hz against 18.2065: 840/256 of a frame a tick), runs the core
; in budgets of RW_BUDGET M-cycles - the core runs with interrupts off
; (REALBOY-SPEC section 5.2), so the budget is the IRQ latency, and the tick
; pre-empts it between two - and yields once a frame. It composes and blits a
; frame when the draw clock says so (rw_drawdue: half the machine at most
; once the game has caught up, a third while it is behind), so the game keeps
; its speed and the picture takes what is left (REALBOY-SPEC section 15.2).
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'REALBOY', rw_entry, OS88_F_ICON | OS88_F_ASSOC | OS88_F_PARTS, OS88_STACK_384

; --- embedded 16x16 icon: a Game Boy, the screen and the cross --------------
    OS88_ICON16
    dw 0x0000, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8
    dw 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x3FF8, 0x0000
    dw 0x0000, 0x3FF8, 0x2008, 0x2FE8, 0x2FE8, 0x2FE8, 0x2FE8, 0x2008
    dw 0x2008, 0x2468, 0x2E08, 0x2468, 0x2008, 0x2008, 0x3FF8, 0x0000
    OS88_ICON16_END

; --- the extension this program opens ---------------------------------------
    OS88_ASSOC16
    db 1
    OS88_ASSOC_EXT 'GB'
    OS88_ASSOC16_END

%include "os88parts.inc"

RW_CONT_W       equ 160
RW_CONT_H       equ 144
RW_BUDGET       equ 2000            ; M-cycles a core run: ~5.6 ms on a 286
RW_BUDGET86     equ 700             ; ...and on an 8088, where 2000 is ~20 ms
                                    ;   with interrupts off - two bytes of a
                                    ;   1200-baud serial mouse into an 8250
                                    ;   that holds one
RW_PERTICK      equ 840             ; frames a BIOS tick, x 256
RW_BEHIND       equ 30              ; frames a machine catches up at most:
                                    ;   half a second, longer than an 8088's
                                    ;   draw, which the frames during it
                                    ;   must outlast or the game slows
RW_OWEDMAX      equ RW_BEHIND * 256
RW_ROMMAX_KB    equ 256             ; one claim's; more is the bank cache's
RW_SLOTMAX      equ 40              ; ...slots at most (rwbank.inc)
RW_PRFN         equ 2048            ; Static's profile: entries, 4 bytes each,
RW_PRFTAIL      equ RW_PRFN * 4     ;   then the file's trailer: 'RBP1', the
RW_PRFFILE      equ RW_PRFTAIL + 9  ;   header's 014Dh byte and 014Eh word,
;
; REALBOY.CFG, in SYSTEM\APPDATA: 'RB', the version, then the settings -
; bit 0 Machine > Cache: 128K. Read at the start, written at the toggle.
; Version 2 goes on with a count at +4 and, from +8, RW_CFGGN games' own
; settings, the latest first: the header's 014Dh byte and 014Eh word (as a
; profile's name takes them), then Speed in bits 0-2 and Sound in 3-4. A
; version 1 file is read for its byte and games none.
RW_CFGN         equ 8 + RW_CFGGN * 4
RW_CFGGN        equ 32
RW_CFGVER       equ 2
RW_CFGBIG       equ 01h
RW_SPEEDS       equ 5               ; Machine > Speed's settings (rw_spdtab)
RW_JIT2N        equ 560             ; a profile this many blocks or more
                                    ;   asks for the second cache segment:
                                    ;   the first holds ~600 of Kirby's
                                    ;   Dream Land's (REALBOY-SPEC 16.2.1)
RW_PRFKB        equ 9               ;   the count (REALBOY-SPEC 16.8)

; --- the bss: the standard's words first, then ours --------------------------
rw_win          equ os88_image_end + OP_BSS
rw_state        equ rw_win + 2      ; 0 no game, 1 running, 2 stopped
rw_pause        equ rw_state + 1
rw_resetq       equ rw_pause + 1    ; Reset asked; the worker does it
rw_abon         equ rw_resetq + 1   ; the About card is up
rw_shown        equ rw_abon + 1     ; rw_fbuf holds a frame
rw_argpend      equ rw_shown + 1
rw_argvol       equ rw_argpend + 1
rw_last         equ rw_argvol + 1   ; word: the tick last counted
rw_owed         equ rw_last + 2     ; word: frames owed, x 256
rw_romseg       equ rw_owed + 2
rw_romkb        equ rw_romseg + 2
rw_banks        equ rw_romkb + 2
rw_argdir       equ rw_banks + 2
rw_spawned      equ rw_argdir + 2
rw_name         equ rw_spawned + 2  ; 16: the game's file name
rw_ovl          equ rw_name + 16    ; the F1 overlay is up
rw_f1was        equ rw_ovl + 1      ; F1 was held at the last look
rw_nrun         equ rw_f1was + 1    ; word: frames run since the last count
rw_ndrawn       equ rw_nrun + 2     ; word: ...and drawn
rw_tstat        equ rw_ndrawn + 2   ; word: the tick that count began
rw_ovltxt       equ rw_tstat + 2    ; 16: 'NNN% NNfps', composed once a second
rw_budget       equ rw_ovltxt + 16  ; word: M-cycles a core run, by CPU tier
rw_drawt        equ rw_budget + 2   ; dword: when the next draw may start
                                    ;   (rw_clk's counts: rw_drawdue)
rw_dlast        equ rw_drawt + 4    ; dword: how long the last draw took
rw_pfmt         equ rw_dlast + 4    ; rw_pbuf holds: 0 nothing, 1 the dither,
                                    ;   4 BLITP's planes (rb_render4)
rw_nobp         equ rw_pfmt + 1     ; BLITP refused us: dither until a paint
rw_incore       equ rw_nobp + 1     ; the worker is in the machine (rwfsx.inc)
rw_fsq          equ rw_incore + 1   ; full screen asked: the worker keeps out
rw_infsx        equ rw_fsq + 1      ; the machine runs in the bracket
rw_fsrate       equ rw_infsx + 1    ; ...paced by FSXF_RATE, not the tick
rw_fsrun        equ rw_fsrate + 1   ; frames run undrawn
rw_ovlnew       equ rw_fsrun + 1    ; rw_ovltxt changed since it was drawn
rw_fowed        equ rw_ovlnew + 1   ; word: rate periods counted by the hook
rw_fsleft       equ rw_fowed + 2    ; word: frames still to run this turn
rw_fsi          equ rw_fsleft + 2   ; FSI_SIZE: the mode's info block
rw_font         equ rw_fsi + FSI_SIZE ; 768: glyphs 32-127, copied at entry
rw_jitseg       equ rw_font + 768   ; word: the recompiler's 64KB, or 0
rw_jitwant      equ rw_jitseg + 2   ; translate when there is a cache for it
rw_jitq         equ rw_jitwant + 1  ; Machine > Recompiler asked; the worker
rw_tone         equ rw_jitq + 1     ; word: the hertz the speaker plays (0 off)
rw_sch          equ rw_tone + 2     ; byte: the square channel on the speaker
rw_ramseg       equ rw_sch + 1      ; word: cartridge RAM's banks, or 0
rw_rambanks     equ rw_ramseg + 2   ; byte: 8KB banks there (0 = none)
rw_batt         equ rw_rambanks + 1 ; byte: a battery: save it on close
rw_rtc          equ rw_batt + 1     ; byte: an MBC3 clock
rw_savelen      equ rw_rtc + 1      ; word: the .SAV's RAM bytes
rw_rtcgap       equ rw_savelen + 2  ; dword: seconds the save was put away
rw_rtcsave      equ rw_rtcgap + 4   ; 16: the clock, across a reset
rw_savename     equ rw_rtcsave + 16 ; 13: NAME.SAV
rw_fskind       equ rw_savename + 13 ; byte: full screen's writer (RW_FS*)
rw_htab         equ rw_fskind + 1   ; 512: a full-screen writer's table
rw_chg          equ rw_htab + 512   ; 144: the lines rb_renderd changed
rw_fsper        equ rw_chg + 144    ; word: rate periods in the bracket (rw_clk)
rw_logon        equ rw_fsper + 2    ; byte: Machine > Log is on (rwlog.inc)
rw_logn         equ rw_logon + 1    ; word: records taken
rw_ltick        equ rw_logn + 2     ; word: ticks since the log began
rw_acomp        equ rw_ltick + 2    ; word: lines composed this second
rw_achg         equ rw_acomp + 2    ; word: ...and changed
rw_ams          equ rw_achg + 2     ; word: ms drawing this second
rw_amax         equ rw_ams + 2      ; byte: the longest draw, ms
rw_aowed        equ rw_amax + 1     ; byte: the most frames owed
rw_aevt         equ rw_aowed + 1    ; byte: RLE_* this second
rw_stspan       equ rw_aevt + 1     ; word: rw_logsec's ticks
rw_llen         equ rw_stspan + 2   ; word: the log text's length
rw_ldig         equ rw_llen + 2     ; word: where its name's digits are
rw_lfile        equ rw_ldig + 2     ; 13: its name
rw_pkgdir       equ rw_lfile + 13   ; word: REALBOY.O88's folder...
rw_pkgvol       equ rw_pkgdir + 2   ; byte: ...and volume (the log's)
rw_romdir       equ rw_pkgvol + 1   ; word: the game's folder...
rw_romvol       equ rw_romdir + 2   ; byte: ...and volume (its .SAV's)
rw_hdir         equ rw_romvol + 1   ; word: where rw_fgo found us...
rw_hvol         equ rw_hdir + 2     ; byte
rw_dgen         equ rw_hvol + 1     ; byte: rw_drawnow's count (rw_timed)
rw_bcache       equ rw_dgen + 1     ; byte: the cartridge is the bank cache's
rw_nslot        equ rw_bcache + 1   ; word: its slots (rwbank.inc)
rw_slotseg      equ rw_nslot + 2    ; word: ...their claim
rw_xbase        equ rw_slotseg + 2  ; dword: the store above 1MB
rw_bcur         equ rw_xbase + 4    ; FSEQ_SIZE: the load's read cursor
rw_bnum         equ rw_bcur + FSEQ_SIZE ; word: the bank being loaded
rw_slotbank     equ rw_bnum + 2     ; RW_SLOTMAX words: each slot's bank
rw_bankreq      equ rw_slotbank + RW_SLOTMAX * 2 ; word: the bank x 2 the
                                    ;   worker waits for, or 0
rw_closing      equ rw_bankreq + 2  ; byte: the window is closing
rw_nmiss        equ rw_closing + 1  ; word: banks fetched
rw_pavail       equ rw_nmiss + 2    ; word: the heap's largest run at load
rw_tscan        equ rw_pavail + 2   ; dword: when rb_renderd's scan ended
rw_asms         equ rw_tscan + 4    ; dword: counts scanning this second
rw_acms         equ rw_asms + 4     ; dword: ...composing
rw_agms         equ rw_acms + 4     ; dword: ...running the Game Boy
rw_tgame        equ rw_agms + 4     ; dword: when this frame's run began
rw_lstat        equ rw_tgame + 4    ; 8: S_EVCOUNT, S_JITNB, S_JITFL and
                                    ;   rw_nmiss at the last record
rw_jitmode      equ rw_lstat + 8    ; byte: Machine > Recompiler, 0 Auto, 1
                                    ;   On, 2 Off (REALBOY-SPEC 16.7), 3
                                    ;   Static (16.8)
rw_jphase       equ rw_jitmode + 1  ; byte: Auto's window, 0 warming the
                                    ;   recompiler's cache, 1-4 timing (odd
                                    ;   with the recompiler), 5 holding
rw_jsec         equ rw_jphase + 1   ; byte: seconds into the window
rw_jhold        equ rw_jsec + 1     ; word: seconds still to hold
rw_jcost        equ rw_jhold + 2    ; dword: counts the machine ran this window
rw_jfr          equ rw_jcost + 4    ; word: ...and its frames
rw_jsum         equ rw_jfr + 2      ; 2 words: the windows' cost a frame, with
                                    ;   the recompiler and without, halved
rw_jnb          equ rw_jsum + 4     ; word: S_JITNB as the window began
rw_jretry       equ rw_jnb + 2      ; byte: this window's re-runs (Auto)
rw_jfl          equ rw_jretry + 1   ; word: S_JITFL as Auto's watch began
rw_undrawn      equ rw_jfl + 2      ; byte: a frame ran since the last draw
rw_klatch       equ rw_undrawn + 1  ; byte: buttons TYPED since the last look
rw_kraw         equ rw_klatch + 1   ; byte: the buttons at the last look
rw_kpref        equ rw_kraw + 1     ; byte: of each opposite pair, the newer
rw_prfseg       equ rw_kpref + 1    ; word: Static's profile (REALBOY-SPEC
                                    ;   16.8), RW_PRFKB, or 0
rw_prfdirty     equ rw_prfseg + 2   ; byte: the profile grew this session
rw_npre         equ rw_prfdirty + 1 ; word: the blocks the last preload made
rw_prfname      equ rw_npre + 2     ; 13: NAME.RBP
rw_f2was        equ rw_prfname + 13 ; F2 was held at the last look...
rw_f3was        equ rw_f2was + 1    ; ...and F3
rw_msgt         equ rw_f3was + 1    ; byte: a note is on the speed line
rw_msgclr       equ rw_msgt + 1     ; byte: ...and has just come down
rw_msgend       equ rw_msgclr + 1   ; word: the tick it comes down at
rw_msg          equ rw_msgend + 2   ; 21: the note (rw_note)
rw_logseg       equ rw_msg + 22     ; word: the log's records, RW_LOGN x
                                    ;   RW_LOGSZ, claimed while it is on
                                    ;   (rwlog.inc), or 0 (after a spare
                                    ;   byte: rw_fbuf stays even)
rw_lrec         equ rw_logseg + 2   ; RW_LOGSZ: the second's record, made
                                    ;   here and copied into the claim
rw_lrec2        equ rw_lrec + RW_LOGSZ ; RW_LOGSZ: the write's, a record
                                    ;   back out of it (the UI task's own)
rw_lring        equ rw_lrec2 + RW_LOGSZ ; word: the write's copy of
                                    ;   [rw_logseg]
rw_prfon        equ rw_lring + 2    ; byte: Machine > Profile is on (and a
                                    ;   spare byte: rw_jit2seg stays even)
rw_jit2seg      equ rw_prfon + 2    ; word: the recompiler's second 64KB
                                    ;   (REALBOY-SPEC 16.2.1), or 0
rw_cfg          equ rw_jit2seg + 2  ; RW_CFGN: REALBOY.CFG as it is read
                                    ;   and written (SYSTEM\APPDATA)
rw_cfgip        equ rw_cfg + RW_CFGN ; byte: os88data.inc's stamp for it
rw_big          equ rw_cfgip + 1    ; byte: Machine > Cache: 128K (the
                                    ;   setting, kept in REALBOY.CFG)
rw_286          equ rw_big + 1      ; byte: a 286 or later: a recompiler
rw_seg2q        equ rw_286 + 1      ; byte: the cache's segments changed:
                                    ;   the worker's to start it again
rw_f3q          equ rw_seg2q + 1    ; byte: F3 asked for Static in the
                                    ;   window: the UI task's first (rw_onwake)
rw_jitqn        equ rw_f3q + 1      ; byte: ...and the switch it queued says
                                    ;   itself on the speed line
rw_speed        equ rw_jitqn + 1    ; byte: Machine > Speed, 0-4 (rw_spdtab)
rw_sndm         equ rw_speed + 1    ; byte: Machine > Sound: 0 On, 1 at full
                                    ;   speed only, 2 Off
rw_spdq         equ rw_sndm + 1     ; byte: F4 changed Speed: the UI task's
                                    ;   to keep it (rw_onwake)
rw_f4was        equ rw_spdq + 1     ; byte: F4 was held at the last look
rw_fsfrac       equ rw_f4was + 1    ; byte: a frame's 256ths the bracket's
                                    ;   clock owes at a Speed under 100%
rw_gkon         equ rw_fsfrac + 1   ; byte: rw_gkey is the game's
rw_spdk         equ rw_gkon + 1     ; word: Speed, 256ths of the Game Boy's
rw_pertick      equ rw_spdk + 2     ; word: ...and frames a BIOS tick, x 256
rw_gkey         equ rw_pertick + 2  ; 3: the game's header 014Dh, 014Eh
rw_hmask        equ rw_gkey + 3     ; byte: the block table's mask (S_HMASK,
                                    ;   REALBOY-SPEC 16.3): 31 for 64KB, 7
rw_fbuf         equ rw_hmask + 1    ; 5,760: rb_render's frame (monochrome;
                                    ;   even)
rw_pbuf         equ rw_fbuf + 5760  ; 11,520: the frame as the screen takes it
RW_BSS          equ rw_pbuf + 11520 - rw_win   ; derived: a sum by hand drifted

; =============================================================================
; rw_entry - the loader calls this once; the window appears afterwards
; =============================================================================
rw_entry:
    mov byte [rw_jitmode], 1        ; Recompiler: On (REALBOY-SPEC 16.7)
    call OSAPI_CPU_INFO
    cmp al, CPU_8086
    je .c86
    mov byte [rw_286], 1
.c86:
    call rw_cfgload
    call rw_spdset                  ; (Speed: 100% until a game says)
    call OSAPI_FILE_HERE            ; where the program is: the log's folder
    mov [rw_pkgdir], dx
    mov [rw_pkgvol], bl
    push es                         ; op_load spends ES, and OSAPI_ARG_FILE
    call op_load                    ;   reads through the kernel's
    pop es
    jc .refused                     ; no room for the core and view: it said
    mov al, KSC_UP                  ; arm the key map (the first call only
    call OSAPI_KEY_DOWN             ;   arms it)
    OS88_ALTENTER_ARM               ; and Alt, for Alt+Enter
    call OSAPI_ARG_FILE             ; CF = 1: launched empty
    jc .nodoc
    mov di, rw_name
    mov cx, 13
.cpn:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    or al, al
    jz .cpd
    loop .cpn
.cpd:
    mov byte [rw_name+13], 0
    mov [rw_argdir], dx
    mov [rw_argvol], bl
    mov byte [rw_argpend], 1
.nodoc:
    mov si, rw_tpl
    call OSAPI_WM_CREATE            ; BX = the window
    jc .refused
    mov [rw_win], bx
    mov ax, rw_onclose              ; the save RAM on the way out
    call OSAPI_WM_ONCLOSE
    mov al, 1
    call OSAPI_WM_SNAP              ; content on the byte grid, for BLITP
    call OSAPI_WM_OWNBG             ; we paint every pixel of it
    OS88_REGION_MOVABLE rw_reloc
    mov si, rw_menus
    call OSAPI_MENU_SET
    mov si, rw_about
    call OSAPI_ABOUT_SET
    mov ax, rw_onwake
    call OSAPI_WM_ONWAKE
    cmp byte [rw_argpend], 0
    je .ok
    call OSAPI_WM_WAKE              ; the document, once the window is up
.ok:
    clc
    ret
.refused:
    stc
    ret

; rw_reloc - OUR REGION MOVED (SPEC.md 66.6.1): BX = where it was, DX = where
; it is. rbsys's own words moved with it; the state block in the view, which
; did not, names our code segment in five vectors. The worker is parked at
; OSAPI_TASK_ALIVE whenever this runs, never in the core.
rw_reloc:
    push ax
    push ds
    mov ax, [cs:rb_viewseg]
    or ax, ax
    jz .r
    mov ds, ax
    cmp [S_EVVEC+2], bx
    jne .1
    mov [S_EVVEC+2], dx
.1:
    cmp [S_IORVEC+2], bx
    jne .2
    mov [S_IORVEC+2], dx
.2:
    cmp [S_IOWVEC+2], bx
    jne .3
    mov [S_IOWVEC+2], dx
.3:
    cmp [S_MBCVEC+2], bx
    jne .4
    mov [S_MBCVEC+2], dx
.4:
    cmp [S_TRACEVEC+2], bx
    jne .5
    mov [S_TRACEVEC+2], dx
.5:
    cmp [S_JITVEC+2], bx            ; the recompiler's entry, rb_jit
    jne .r
    mov [S_JITVEC+2], dx
.r:
    pop ds
    pop ax
    ret

; rbsys asks its host for these: the link port's bytes go nowhere, and this
; core is not a trace build
rb_putc:
rb_trbyte:
    ret

; =============================================================================
; Loading a game
; =============================================================================

; rw_onwake - on the UI task, no lock held: a document we were launched with,
; or the core having stopped
rw_onwake:
    call rw_bserve                  ; a bank the worker waits for
    cmp byte [rw_spdq], 0           ; F4 changed Speed: kept here, where a
    je .nf4                         ;   file may be written
    mov byte [rw_spdq], 0
    call rw_cfgsave
.nf4:
    cmp byte [rw_f3q], 0            ; F3 in the window, to Static: its
    je .nf3                         ;   profile and room here, then the
    mov byte [rw_f3q], 0            ;   switch the worker's (rw_jitq),
    call rw_stprep                  ;   said as F3's own is
    mov byte [rw_jitqn], 1
    mov byte [rw_jitq], 1
.nf3:
    cmp byte [rw_argpend], 0
    je .stopped
    mov byte [rw_argpend], 0
    call OSAPI_GFX_LOCK
    mov dx, [rw_argdir]
    mov bl, [rw_argvol]
    call OSAPI_FILE_GOTO_QM
    jc .unlock
    mov si, [rw_win]
    call rw_load
.unlock:
    call OSAPI_GFX_UNLOCK
    ret
.stopped:
    cmp byte [rw_state], 2
    jne .r
    call OSAPI_GFX_LOCK
    mov si, [rw_win]
    call rw_repaint
    call OSAPI_GFX_UNLOCK
.r:
    ret

; rw_open - File > Open: the Standard File dialog, then rw_opened
rw_open:
    cmp byte [rw_state], 0
    jne .one
    mov al, FDLG_OPEN
    mov bx, si
    mov di, rw_opened
    xor si, si
    call OSAPI_FILE_DLG
    ret
.one:
    mov si, rw_s_one                ; one game a window: another opens in
    jmp rw_toast                    ;   another window

; rw_opened - the dialog's completion: DI = the name, DX:CX = its size
rw_opened:
    push si
    mov si, di                      ; copy the kernel's name now
    mov di, rw_name
    mov bx, 13
.c:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    or al, al
    jz .cd
    dec bx
    jnz .c
.cd:
    mov byte [rw_name+13], 0
    pop si
    ; (the size the dialog read out of the listing is not used: rw_load asks
    ; the file itself, which knows its size unpacked)
; rw_load - rw_name in the current folder, SI = our window, the gfx lock
; held. THE SIZE PROBE first - a read with no room answers FERR_BIG with the
; KB the read needs, from the directory and unpacked, with some slack for a
; compressed file's expansion - then a claim that size, the read, and the
; check on the bytes that actually came in: whole 16KB banks, 32 to 256KB.
rw_load:
    push si
    push ds
    pop es
    xor bx, bx
    xor cx, cx
    xor dx, dx
    mov si, rw_name
    call OSAPI_FILE_READ
    jnc .notrom                     ; an empty file
    cmp ax, FERR_BIG
    jne .rdfail0
    cmp dx, 32
    jb .notrom
    mov [rw_romkb], dx
    call rw_dmgclaim                ; the damage memory and the recompiler's
    call rw_jitclaim                ;   cache FIRST: what the ROM's read
    call rw_jit2claim               ;   rebuilds of the disk caches lands in
    call rw_plan                    ;   what is left, and took the 64KB on
    jnc .planned                    ;   the second field run's Victory
    cmp word [rw_jit2seg], 0        ; no room with the cache's second
    je .nojit2                      ;   segment: the ROM without it first
    mov dx, [rw_jit2seg]
    call OSAPI_MEM_FREE
    mov word [rw_jit2seg], 0
    call rw_plan
    jnc .planned
.nojit2:
    cmp word [rw_jitseg], 0
    je .say
    cmp byte [rw_hmask], 7          ; ...then with the table at 16KB
    je .nobig
    mov dx, [rw_jitseg]
    call OSAPI_MEM_FREE
    mov word [rw_jitseg], 0
    mov ax, 64 + 16
    mov byte [rw_hmask], 7
    call OSAPI_MEM_CLAIM
    jc .nojit
    mov [rw_jitseg], dx
    call rw_plan
    jnc .planned
.nobig:
    mov dx, [rw_jitseg]             ; no room with it: the ROM without it
    call OSAPI_MEM_FREE
    mov word [rw_jitseg], 0
.nojit:
    mov byte [rw_jitwant], 0
    call rw_plan
    jc .say
.planned:
    cmp byte [rw_bcache], 0
    je .one
    call rw_bload
    jc .say
    jmp short .loaded
.one:
    mov ax, [rw_romkb]
    call OSAPI_MEM_CLAIM            ; DX = its segment
    jc .room
    mov [rw_romseg], dx
    mov es, dx
    xor bx, bx
    mov ax, [rw_romkb]
    mov cx, 1024
    mul cx
    mov cx, ax                      ; DX:CX = the claim's capacity
    mov si, rw_name
    call OSAPI_FILE_READ            ; DX:AX = the bytes read
    jc .rdfail
    ; the ROM itself: whole 16KB banks, 2 to 16 of them
    test ax, 3FFFh
    jnz .notrom1
    mov cx, 14
.sh:
    shr dx, 1
    rcr ax, 1
    loop .sh                        ; AX = banks
    cmp ax, 2
    jb .notrom1
    cmp ax, RW_ROMMAX_KB / 16
    ja .notrom1
    mov [rw_banks], ax
.loaded:
    call rw_jitclaim
    call rw_dmgclaim
    call rw_ramsetup
    call rw_prfload
    call rw_start
    call rw_spdgame                 ; its Speed and Sound, if it has them
    mov byte [rw_state], 1
    pop si
    call rw_hire
    call rw_repaint
    ret
.notrom1:
    mov dx, [rw_romseg]             ; the claim back
    call OSAPI_MEM_FREE
.notrom:
    mov si, rw_s_notrom
    jmp short .say
.rdfail:
    mov dx, [rw_romseg]
    call OSAPI_MEM_FREE
.rdfail0:
    mov si, rw_s_read
    jmp short .say
.room:
    mov si, rw_s_room
.say:
    pop bx                          ; (the window, banked)
    jmp rw_toast

; rw_start - rb_init: the view, the core, the ROM, its banks - and the
; recompiler over them when it has its cache (REALBOY-SPEC section 16)
rw_start:
    mov al, 2                       ; the view
    call op_seg
    push ax
    xor al, al                      ; the core, both halves from here
    call op_seg
    mov bx, ax
    pop ax
    mov cx, [rw_romseg]
    mov dx, [rw_banks]
    call rb_init
    call rw_ramattach
    call rw_dmgfull
    mov ax, [rw_prfseg]             ; the profile, recorded from here on
    push ds
    mov ds, [cs:rb_viewseg]
    mov [S_PRFSEG], ax
    mov word [S_PRFMASK], RW_PRFN - 1
    pop ds
rw_jiton:                           ; (and Machine > Recompiler's way back in)
    push ds
    push bx
    mov ds, [cs:rb_viewseg]
    cmp word [cs:rw_jitseg], 0      ; no cache or not wanted: the plain
    je .off                         ;   interpreter, hooks and all removed
    cmp byte [cs:rw_jitwant], 0
    je .off
    call rw_rtinit
    cmp byte [cs:rw_jitmode], 3     ; Static: the profile made now
    jne .dyn
    call rt_preload
    mov [cs:rw_npre], ax
.dyn:
    pop bx
    pop ds
    ret
.off:
    xor al, al
    call rt_dispatch
    pop bx
    pop ds
    ret

; rw_jitsegs - AX = the recompiler's cache, BX = its block table: the 16KB
; after it in the one claim (rw_jitclaim); CX = its second 64KB, or 0; DL
; = the table's mask
rw_jitsegs:
    mov ax, [cs:rw_jitseg]
    mov bx, ax
    add bh, 10h
    mov cx, [cs:rw_jit2seg]
    mov dl, [cs:rw_hmask]
    ret

; rw_rtinit - DS = the view: rt_init over the package's claims, every
; register kept
rw_rtinit:
    push ax
    push bx
    push cx
    push dx
    call rw_jitsegs
    call rt_init
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rw_jitback - the recompiler on again, between two core runs: over the
; cache it had, or from nothing when there is none since rb_init
rw_jitback:
    cmp word [cs:rw_jitseg], 0
    je .r
    push ds
    mov ds, [cs:rb_viewseg]
    cmp byte [S_JITON], 0
    jne .x
    cmp word [S_JITSEG], 0
    je .init
    call rt_resume
.x:
    pop ds
.r:
    ret
.init:
    push bx
    call rw_rtinit
    pop bx
    pop ds
    ret

; rw_jitset - Machine > Recompiler's mode, between two core runs: Off is
; the interpreter; On is the recompiler; Auto starts with it and times both
rw_jitset:
    xor ax, ax
    mov [rw_jsec], al
    mov [rw_jcost], ax
    mov [rw_jcost + 2], ax
    mov [rw_jfr], ax
    mov [rw_jsum], ax
    mov [rw_jsum + 2], ax
    mov [rw_jretry], al
    mov byte [rw_jitwant], 1        ; (rw_jiton's, at a reset)
    cmp byte [rw_jitmode], 3
    je rw_static
    push ds                         ; anything but Static: the table is the
    mov ds, [cs:rb_viewseg]         ;   dynamic recompiler's again, over
    mov byte [S_JITFIX], 0          ;   what a preload left in it
    mov byte [S_JITPRE], 0
    pop ds
    cmp byte [rw_jitmode], 2
    jne .on
    mov byte [rw_jitwant], 0
    mov al, RLE_JITOFF
    call rw_logevt
    jmp rw_jitoff
.on:
    mov al, RLE_JITON
    call rw_logevt
    jmp rw_jitwatch                 ; (Auto watches it; On ignores the watch)

; rw_static - Machine > Recompiler: Static (REALBOY-SPEC 16.8), between two
; core runs: the cache flushed, the profile - everything translated in
; this game's sessions so far, this one's included - translated into it
; heaviest first, and the block table fixed
rw_static:
    mov al, RLE_JITON
    call rw_logevt
    push ds
    push bx
    mov ds, [cs:rb_viewseg]
    call rw_rtinit
    call rt_preload
    mov [cs:rw_npre], ax
    pop bx
    pop ds
    ret

; rw_jitauto - once a second, between frames (rw_stat): Machine >
; Recompiler's Auto (REALBOY-SPEC 16.7). It WATCHES the recompiler: every
; RW_JWATCH seconds it counts the cache's flushes, and only a recompiler
; whose cache thrashes - RW_JTHRASH flushes or more - is timed against the
; interpreter: a window of RW_JWIN seconds with the recompiler NOT timed (a
; cold cache timed it dearer than it was), then four, with it, without,
; with and without, each's cost a frame summed by kind. The recompiler
; unless the interpreter is an eighth cheaper, and watched again; the
; interpreter for RW_JHOLD seconds, then both timed again. It timed both at
; every start and every minute until the fourth field run, whose music
; slowed for each interpreted window: two seconds at 8-11 pictures a second
; in Super Mario Land, which the recompiler runs at 16-19.
RW_JWIN         equ 2
RW_JHOLD        equ 60
RW_JWATCH       equ 30
RW_JTHRASH      equ 3
RW_JWARM        equ 48              ; blocks a window may translate and count
RW_JRETRY       equ 3
rw_jitauto:
    cmp byte [rw_jitmode], 0
    jne .r
    cmp word [rw_jitseg], 0
    je .r
    cmp byte [rw_jphase], 5
    jae .hold
    inc byte [rw_jsec]
    cmp byte [rw_jsec], RW_JWIN
    jb .r
    mov byte [rw_jsec], 0
    mov cx, [rw_jfr]                ; the window's cost a frame
    or cx, cx                       ; (no frame: it says nothing)
    jz .r
    mov ax, [rw_jcost]
    mov dx, [rw_jcost + 2]
    xor bx, bx
    mov [rw_jcost], bx
    mov [rw_jcost + 2], bx
    mov [rw_jfr], bx
    push ds                         ; BX = blocks translated in the window
    mov ds, [cs:rb_viewseg]
    mov bx, [S_JITNB]
    pop ds
    xchg bx, [rw_jnb]
    neg bx
    add bx, [rw_jnb]
    cmp byte [rw_jphase], 0
    jne .t
    inc byte [rw_jphase]            ; the warm-up: on, with the recompiler
    ret
.t:
    test byte [rw_jphase], 1        ; a window with the recompiler that was
    jz .tk                          ;   still translating - a level's start -
    cmp bx, RW_JWARM                ;   times the interpreter's hooks and the
    jb .tk                          ;   translator, not the recompiler: again,
    cmp byte [rw_jretry], RW_JRETRY ;   up to RW_JRETRY times (the field run
    jae .tk                         ;   lost it so on Super Mario Land's first
    inc byte [rw_jretry]            ;   level, 233 blocks in its two windows)
    ret
.tk:
    mov byte [rw_jretry], 0
    cmp dx, cx
    jb .d
    mov ax, 0FFFFh                  ; (a frame of 55 ms or more: as that)
    jmp short .h
.d:
    div cx
.h:
    shr ax, 1
    mov bl, [rw_jphase]
    inc bl
    and bx, 1
    shl bx, 1                       ; 0 with the recompiler, 2 without
    add [rw_jsum + bx], ax
    inc byte [rw_jphase]
    cmp byte [rw_jphase], 5
    jae .decide
    test byte [rw_jphase], 1        ; odd windows with it
    jnz rw_jitback
    jmp rw_jitoff
.decide:
    mov ax, [rw_jsum]               ; AX with the recompiler, BX without
    mov bx, [rw_jsum + 2]
    mov cx, bx                      ; the recompiler unless it is an eighth
    shr cx, 1                       ;   dearer: a title screen times both the
    shr cx, 1                       ;   same, and Super Mario Land timed there
    shr cx, 1                       ;   once chose the interpreter for its
    add cx, bx                      ;   levels (60-70% scrolling, not 100%)
    jc rw_jitwatch
    cmp ax, cx
    jbe rw_jitwatch
    mov word [rw_jhold], RW_JHOLD   ; the interpreter, for a minute
    jmp rw_jitoff
.hold:
    dec word [rw_jhold]
    jnz .r
    push ds                         ; the recompiler watched: its flushes
    mov ds, [cs:rb_viewseg]
    mov ax, [S_JITFL]
    cmp byte [S_JITON], 0
    pop ds
    je .again                       ; (the interpreter's minute is up)
    sub ax, [rw_jfl]
    cmp ax, RW_JTHRASH
    jb rw_jitwatch                  ; not thrashing: watched again
.again:
    xor ax, ax                      ; time both, from the recompiler
    mov [rw_jphase], al
    mov [rw_jsec], al
    mov [rw_jcost], ax
    mov [rw_jcost + 2], ax
    mov [rw_jfr], ax
    mov [rw_jsum], ax
    mov [rw_jsum + 2], ax
    mov [rw_jretry], al
    jmp rw_jitback
.r:
    ret


; rw_jitwatch - Auto's recompiler, watched for RW_JWATCH seconds from its
; flush count now (rw_jitauto)
rw_jitwatch:
    mov byte [rw_jphase], 5
    mov word [rw_jhold], RW_JWATCH
    push ds
    mov ds, [cs:rb_viewseg]
    mov ax, [S_JITFL]
    pop ds
    mov [rw_jfl], ax
    jmp rw_jitback

; rw_jitoff - the interpreter alone, between two core runs (the worker's)
rw_jitoff:
    push ds
    mov ds, [cs:rb_viewseg]
    mov byte [S_JITON], 0
    mov word [S_RESVEC], RBC_RB_DISPATCH
    xor al, al
    call rt_dispatch
    pop ds
    ret

; rw_jitclaim - on the UI task, once: a 64KB cache and the 16KB of its block
; table after it (REALBOY-SPEC 16.3), on a 286 or later. The
; recompiler's code is bigger than the interpreter's, and an 8088's bus makes
; bytes the cost; and without the memory it is simply not used.
rw_jitclaim:
    cmp word [rw_jitseg], 0
    jne .r
    call OSAPI_CPU_INFO
    cmp al, CPU_8086
    je .r
    mov ax, 64 + JIT_HASHN * 8 / 1024 ; the cache and its block table: 64KB
    mov byte [rw_hmask], JIT_HMMAX  ;   of table, a quarter of the slot
    call OSAPI_MEM_CLAIM            ;   fights 16KB's has (REALBOY-SPEC
    jnc .got                        ;   16.3: Kirby's Dream Land 330 -> 266
    mov ax, 64 + 16                 ;   ticks, the CPU alone) - or 16KB
    mov byte [rw_hmask], 7
    call OSAPI_MEM_CLAIM            ; DX = its segment, pinned: the core's
    jc .r                           ;   state block names it
.got:
    mov [rw_jitseg], dx
    mov byte [rw_jitwant], 1
.r:
    ret

; rw_hire - the worker, once (the lock is held: paint, a menu or a dialog)
rw_hire:
    cmp byte [rw_spawned], 0
    jne .r
    mov ax, rw_worker
    mov bx, [rw_win]
    call OSAPI_TASK_SPAWN
    jc .r                           ; refused for now: the next paint asks
    OS88_WORKER_RESTARTABLE rw_worker_rs
    mov byte [rw_spawned], 1
.r:
    ret

; =============================================================================
; Cartridge RAM, its battery and the MBC3 clock (REALBOY-SPEC section 10.1)
; =============================================================================

; rw_ramsetup - after the ROM is read, on the UI task: what the header says
; the cartridge carries, a claim for the banks when there is more than one
; (or a clock, or a battery), and a battery's NAME.SAV from beside the game
rw_ramsetup:
    call OSAPI_FILE_HERE            ; the game's folder: its .SAV's
    mov [rw_romdir], dx
    mov [rw_romvol], bl
    push es
    mov es, [rw_romseg]
    mov al, [es:0147h]              ; the cartridge type
    mov ah, [es:0149h]              ; the RAM size code
    pop es
    xor bx, bx
    mov [rw_ramseg], bx
    mov [rw_rtc], bl
    mov [rw_batt], bl
    mov si, rw_battab               ; a battery?
.bt:
    cmp byte [si], 0
    je .bd
    cmp al, [si]
    je .by
    inc si
    jmp short .bt
.by:
    mov byte [rw_batt], 1
.bd:
    cmp al, 0Fh                     ; MBC3 + timer
    je .rt
    cmp al, 10h
    jne .sz
.rt:
    mov byte [rw_rtc], 1
.sz:
    mov cx, 512                     ; MBC2: 512 nibbles of its own
    mov bl, 1
    cmp al, 05h
    je .have
    cmp al, 06h
    je .have
    xor cx, cx
    xor bl, bl
    cmp ah, 1
    jb .have                        ; none
    mov cx, 2048
    mov bl, 1
    je .have                        ; 2KB
    mov cx, 8192
    cmp ah, 2
    je .have
    mov cx, 32768                   ; 32KB - and 64/128KB kept as 32KB
    mov bl, 4
.have:
    mov [rw_savelen], cx
    mov [rw_rambanks], bl
    cmp bl, 1                       ; one bank and nothing to keep: the
    ja .claim                       ;   window alone holds it
    cmp byte [rw_rtc], 0
    jne .claim
    cmp byte [rw_batt], 0
    je .r
    or bl, bl
    jz .r                           ; a battery and no RAM: nothing to save
.claim:
    mov al, bl
    or al, al
    jnz .k
    inc al
.k:
    mov ah, 8
    mul ah                          ; AX = 8KB a bank
    add al, [rw_rtc]                ; + 1KB for the clock's trailer
    push ax
    call OSAPI_MEM_CLAIM            ; DX = its segment, pinned: the state
    pop ax                          ;   block names it
    jc .room
    mov [rw_ramseg], dx
    push es                         ; FFh, as a cartridge without a save
    mov es, dx
    xor di, di
    mov ch, al                      ; (AX = KB, under 128)
    xor cl, cl
    shl ch, 1                       ; CX = KB x 512 words
    mov ax, 0FFFFh
    cld
    rep stosw
    pop es
    call rw_savenm
    cmp byte [rw_batt], 0
    je .r
    ; the save, if there is one: a short or missing file leaves FFh
    push es
    mov es, [rw_ramseg]
    xor bx, bx
    mov cx, [rw_savelen]
    xor dx, dx
    cmp byte [rw_rtc], 0
    je .cap
    add cx, 48
.cap:
    mov si, rw_savename             ; beside the game, which is where we
    call OSAPI_FILE_READ            ;   stand (rw_load): DX:AX = bytes
    pop es
    jc .r
    cmp byte [rw_rtc], 0
    je .r
    mov cx, [rw_savelen]
    add cx, 44
    cmp ax, cx
    jb .r
    call rw_rtcin
.r:
    ret
.room:
    mov si, rw_s_noram
    jmp rw_toast

; rw_savenm - rw_savename = rw_name with its extension made .SAV
rw_savenm:
    mov di, rw_savename
    mov ax, '.S'
    mov dx, 'AV'
; rw_extnm - DI = rw_name with its extension made AX:DX's four characters
rw_extnm:
    mov si, rw_name
    mov cx, 8
.c:
    lodsb
    or al, al
    jz .e
    cmp al, '.'
    je .e
    mov [di], al
    inc di
    loop .c
.e:
    mov [di], ax
    mov [di+2], dx
    mov byte [di+4], 0
    ret

; rw_ramattach - after rb_init (which zeroed the view): the banks and the
; clock into the state block, bank 0 into the window, and any time a save
; spent switched off onto the clock
rw_ramattach:
    mov ax, [rw_ramseg]
    mov bl, [rw_rambanks]
    mov bh, [rw_rtc]
    push ds
    pop es                          ; ES = ours, for the clock's copy
    push ds
    mov ds, [cs:rb_viewseg]
    mov [S_RAMSEG], ax
    mov [S_RAMBANKS], bl
    mov byte [S_RAMCUR], 0
    mov si, rw_rtcsave              ; our copy of the clock into the view
    mov di, S_RTC
    mov cx, 13
.c:
    mov dl, [es:si]
    mov [di], dl
    inc si
    inc di
    loop .c
    mov [S_RTC+RTC_ON], bh
    mov byte [S_RTC+RTC_LST], 0FFh
    or ax, ax
    jz .nr
    call rb_ramin                   ; bank 0 into the window
.nr:
    mov ax, [es:rw_rtcgap]          ; the time a save spent put away
    mov dx, [es:rw_rtcgap+2]
    mov cx, ax
    or cx, dx
    jz .p
    call rb_rtcadd
.p:
    pop ds
    xor ax, ax
    mov [rw_rtcgap], ax
    mov [rw_rtcgap+2], ax
    ret

; =============================================================================
; Static's profile: NAME.RBP beside the game (REALBOY-SPEC 16.8)
; =============================================================================

; rw_prfload - after the ROM is read, on the UI task, beside the game: a
; claim for the profile when there is a recompiler, emptied, and NAME.RBP
; read into it - kept only if it is this game's (the trailer's magic, the
; header's checksums and the count)
rw_prfload:
    cmp word [rw_jitseg], 0
    je .r
    push es
    cmp word [rw_prfseg], 0         ; read before the ROM's plan
    jne .check                      ;   (rw_jit2claim): checked now
    cmp byte [rw_jitmode], 3        ; Static reads it, so Static is the
    jne .want                       ;   profile on
    mov byte [rw_prfon], 1
.want:
    cmp byte [rw_prfon], 0          ; Machine > Profile: off, no claim
    je .r0
    mov ax, RW_PRFKB
    call OSAPI_MEM_CLAIM            ; DX = its segment, pinned: the state
    jc .r0                          ;   block names it
    mov [rw_prfseg], dx
    call rw_prfrd
    jc .empty
.check:
    mov es, [rw_prfseg]
    xor ch, ch
    call rw_prftail                 ; ZF = 1: the trailer is this game's
    je .r0
.empty:
    mov es, [rw_prfseg]
    xor di, di
    mov cx, RW_PRFFILE / 2 + 1
    xor ax, ax
    cld
    rep stosw
.r0:
    pop es
.r:
    ret

; rw_prfrd - NAME.RBP beside the game into [rw_prfseg]'s claim. CF = 1: not
; there, or not a profile's size
rw_prfrd:
    push es
    mov byte [rw_prfdirty], 0
    mov di, rw_prfname
    mov ax, '.R'
    mov dx, 'BP'
    call rw_extnm
    cmp byte [rw_state], 0          ; a game running: its folder (the
    je .here                        ;   current one may have moved since)
    mov dx, [rw_romdir]
    mov bl, [rw_romvol]
    call rw_fgo
    jc .back
.here:
    mov es, [rw_prfseg]
    xor bx, bx
    mov cx, RW_PRFFILE
    xor dx, dx
    mov si, rw_prfname
    call OSAPI_FILE_READ            ; DX:AX = the bytes read
    jc .back
    cmp ax, RW_PRFFILE
    je .back
    stc
.back:
    pushf
    cmp byte [rw_state], 0
    je .r
    call rw_fback
.r:
    popf
    pop es
    ret

; rw_prfblocks - AX = the blocks the profile names (its entries weighing
; anything), or 0 with none
rw_prfblocks:
    xor ax, ax
    cmp word [rw_prfseg], 0
    je .r
    push bx
    push cx
    push es
    mov es, [rw_prfseg]
    mov bx, 3
    mov cx, RW_PRFN
.c:
    cmp byte [es:bx], 0
    je .n
    inc ax
.n:
    add bx, 4
    loop .c
    pop es
    pop cx
    pop bx
.r:
    ret

; rw_jit2claim - on the UI task at the load, after rw_jitclaim and before
; the ROM's plan: the cache's second 64KB (REALBOY-SPEC 16.2.1) when the
; game's NAME.RBP names more blocks than the first holds. Read here, it is
; kept, and the Profile is on: the game has one. The ROM takes what is left,
; and gives it back if that is not enough (rw_load).
rw_jit2claim:
    cmp word [rw_jitseg], 0
    je .r
    cmp word [rw_prfseg], 0         ; (a load that failed left one)
    jne .have
    mov ax, RW_PRFKB
    call OSAPI_MEM_CLAIM            ; DX = the profile's segment
    jc .r
    mov [rw_prfseg], dx
.have:
    call rw_prfrd
    jnc .got
    xor dx, dx                      ; no profile: no claim
    xchg dx, [rw_prfseg]
    call OSAPI_MEM_FREE
    cmp byte [rw_big], 0            ; Machine > Cache: 128K asks for it
    jne rw_jit2get                  ;   whatever the profile says
.r:
    ret
.got:
    mov byte [rw_prfon], 1
; rw_jit2more - the profile is in: the second 64KB if it names more than the
; first holds, or Machine > Cache says 128K, from what the heap has left.
; One segment without it.
rw_jit2more:
    cmp byte [rw_big], 0
    jne rw_jit2get
    call rw_prfblocks
    cmp ax, RW_JIT2N
    jb rw_jit2get.r
rw_jit2get:
    cmp word [rw_jitseg], 0
    je .r
    cmp word [rw_jit2seg], 0
    jne .r
    mov ax, 64
    call OSAPI_MEM_CLAIM            ; DX = its segment, pinned: the state
    jc .r                           ;   block names it
    mov [rw_jit2seg], dx
.r:
    ret

; rw_cfgload - REALBOY.CFG out of SYSTEM\APPDATA at the start: the
; settings, or none of them for a file that is not ours
rw_cfgload:
    push ax
    push bx
    push cx
    push dx
    push si
    push es
    push ds
    pop es
    mov si, rw_s_cfg
    mov bx, rw_cfg
    mov cx, RW_CFGN
    xor dx, dx
    call od_read
    jc .r
    or dx, dx
    jnz .r
    cmp word [rw_cfg], 'RB'
    jne .none
    cmp ax, RW_CFGN
    jne .v1
    cmp byte [rw_cfg + 2], RW_CFGVER
    jne .none
    cmp byte [rw_cfg + 4], RW_CFGGN
    jbe .big
    jmp short .none
.v1:
    cmp ax, 4                       ; version 1: the byte, and no games
    jne .none
    cmp byte [rw_cfg + 2], 1
    jne .none
    mov byte [rw_cfg + 4], 0
.big:
    test byte [rw_cfg + 3], RW_CFGBIG
    jz .r
    mov byte [rw_big], 1
    jmp short .r
.none:
    mov byte [rw_cfg + 4], 0        ; (not ours: no games of it either)
.r:
    pop es
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rw_cfgsave - the settings back into REALBOY.CFG, on the UI task. A
; refusal says nothing: the setting holds for this session
rw_cfgsave:
    push es
    push ds
    pop es
    mov word [rw_cfg], 'RB'
    mov byte [rw_cfg + 2], RW_CFGVER
    mov al, [rw_big]
    mov [rw_cfg + 3], al
    mov si, rw_s_cfg
    mov bx, rw_cfg
    mov cx, RW_CFGN
    mov di, rw_cfgip
    call od_write
    pop es
    ret

; rw_bigtoggle - Machine > Cache, on the UI task with the lock held: 64K
; or 128K, the recompiler's code (REALBOY-SPEC 16.2.1), kept in REALBOY.CFG
; for every game after. 128K in a session takes the second 64KB from what
; the heap has left, and the worker starts the recompiler again over both;
; without the room - or going back to 64K - it is the next game's.
rw_bigtoggle:
    cmp byte [rw_286], 0
    je .r
    xor byte [rw_big], 1
    call rw_cfgsave
    call rw_mgrey
    cmp byte [rw_state], 0          ; no game: the next one's
    je .r
    mov si, rw_s_bignx
    cmp byte [rw_big], 0
    je .say                         ; 64K: the next game's
    cmp word [rw_jit2seg], 0
    jne .r                          ; (already had it, from its profile)
    call rw_jit2get
    cmp word [rw_jit2seg], 0
    je .say                         ; no room now
    mov byte [rw_seg2q], 1          ; the worker: the recompiler again
    ret
.say:
    jmp rw_toast
.r:
    ret

; rw_prftoggle - Machine > Profile, on the UI task with the lock held. On:
; the claim and NAME.RBP, and recording from here on. Off: what was
; recorded saved, then the claim given back - a session meant for On alone
; keeps its 9KB and writes no file at the close. Static reads the profile,
; so it stays on while Static is the setting. Before a game it is the
; setting the load takes.
rw_prftoggle:
    cmp byte [rw_286], 0            ; (before a game too: its load claims
    je .r                           ;   it)
    cmp byte [rw_prfon], 0
    jne .off
    mov byte [rw_prfon], 1
    call rw_prfup
    jmp short .m
.off:
    cmp byte [rw_jitmode], 3
    je .st
    mov byte [rw_prfon], 0
    call rw_prfdrop
.m:
    jmp rw_mgrey
.st:
    mov si, rw_s_prfst
    jmp rw_toast
.r:
    ret

; rw_stprep - on the UI task, before Machine > Recompiler's next setting
; (the menu, or F3): when that is Static, which reads the profile, the
; profile on and read here, where a file can be, and the cache's second
; 64KB if it names more than the first holds (REALBOY-SPEC 16.2.1)
rw_stprep:
    cmp byte [rw_jitmode], 1        ; On -> Static
    jne .r
    mov byte [rw_prfon], 1
    call rw_prfup
    call rw_jit2more
    call rw_mgrey
.r:
    ret

; rw_prfup - on the UI task, a game running: the profile claimed, read and
; handed to the core. The table is whole before the core is told of it.
rw_prfup:
    cmp byte [rw_state], 0
    je .r
    cmp word [rw_prfseg], 0         ; already in, and recording: as it is
    jne .r                          ;   (rw_prfload would check a trailer
    call rw_prfload                 ;   only the save writes)
    mov ax, [rw_prfseg]
    or ax, ax
    jz .r
    push ds
    mov ds, [cs:rb_viewseg]
    mov word [S_PRFMASK], RW_PRFN - 1
    mov [S_PRFSEG], ax
    pop ds
.r:
    ret

; rw_prfdrop - on the UI task: the profile saved if it grew, the core told
; to record no more, and - once the worker has been seen out of the
; machine, so a rt_prfadd that read [S_PRFSEG] first has finished - the
; claim freed
rw_prfdrop:
    cmp word [rw_prfseg], 0
    je .r
    call rw_prfsave
    push ds
    mov ds, [cs:rb_viewseg]
    mov word [S_PRFSEG], 0
    pop ds
.wait:
    cmp byte [rw_incore], 0
    je .free
    call rw_bserve                  ; (it may be waiting on us for a bank)
    call OSAPI_TASK_YIELD
    jmp short .wait
.free:
    xor dx, dx
    xchg dx, [rw_prfseg]
    call OSAPI_MEM_FREE
.r:
    ret

; rw_prftail - ES = the profile: ZF = 1 when its trailer is this game's;
; with CH = 1, the trailer written first. The header is bank 0's, which
; rw_romseg holds in either load (rw_ramsetup reads it so too)
rw_prftail:
    push ds
    mov ds, [rw_romseg]
    mov ax, [014Eh]
    mov dl, [014Dh]
    pop ds
    mov di, RW_PRFTAIL
    or ch, ch
    jz .cmp
    mov word [es:di], 'RB'
    mov word [es:di+2], 'P1'
    mov [es:di+4], dl
    mov [es:di+5], ax
    mov word [es:di+7], RW_PRFN
.cmp:
    cmp word [es:di], 'RB'
    jne .x
    cmp word [es:di+2], 'P1'
    jne .x
    cmp [es:di+4], dl
    jne .x
    cmp [es:di+5], ax
    jne .x
    cmp word [es:di+7], RW_PRFN
.x:
    ret

; rw_prfnote - the profile's growth this run, before rb_init zeroes the count
rw_prfnote:
    push ds
    mov ds, [cs:rb_viewseg]
    cmp word [S_PRFNEW], 0
    pop ds
    je .r
    mov byte [rw_prfdirty], 1
.r:
    ret

; rw_prfsave - at the close, on the UI task: NAME.RBP beside the game, if
; the profile grew. A failure says nothing - the profile is only a speed-up
rw_prfsave:
    cmp word [rw_prfseg], 0
    je .r
    call rw_prfnote
    cmp byte [rw_prfdirty], 0
    je .r
    push es
    mov es, [rw_prfseg]
    mov ch, 1
    call rw_prftail                 ; the trailer, written
    mov dx, [rw_romdir]             ; beside the game
    mov bl, [rw_romvol]
    call rw_fgo
    jc .back
    xor bx, bx
    mov cx, RW_PRFFILE
    xor dx, dx
    mov si, rw_prfname
    call OSAPI_FILE_WRITE
.back:
    call rw_fback
    pop es
.r:
    ret

; rw_ramkeep - before a reset or a save: the window back to its bank, and the
; clock into rw_rtcsave
rw_ramkeep:
    push ds
    pop es
    push ds
    mov ds, [cs:rb_viewseg]
    call rb_ramsync
    mov si, S_RTC
    mov di, rw_rtcsave
    mov cx, 16
    cld
    rep movsb
    pop ds
    ret

; rw_onclose - the close negotiator, on the UI task with the lock held: a
; battery's RAM saved, and the close always goes ahead
rw_onclose:
    mov byte [rw_closing], 1        ; a worker waiting on a bank ends now
    cmp byte [rw_logon], 0          ; the log, if it was on
    je .s
    mov byte [rw_logon], 0
    call rw_logwrite
.s:
    cmp byte [rw_state], 0
    je .r
    call rw_prfsave
    cmp byte [rw_batt], 0
    je .r
    cmp word [rw_ramseg], 0
    je .r
    call rw_save
.r:
    clc
    ret

; rw_save - NAME.SAV beside the game: the RAM, and for a clock VBA's
; 48-byte trailer, so the file is any emulator's
rw_save:
    call rw_ramkeep
    mov cx, [rw_savelen]
    cmp byte [rw_rtc], 0
    je .w
    call rw_rtcout
    add cx, 48
.w:
    push cx
    mov dx, [rw_romdir]             ; beside the game
    mov bl, [rw_romvol]
    call rw_fgo
    pop cx
    jc .no
    push es
    mov es, [rw_ramseg]
    xor bx, bx
    xor dx, dx
    mov si, rw_savename
    call OSAPI_FILE_WRITE
    pop es
.no:
    call rw_fback                   ; (CF kept)
    jnc .r
    mov si, rw_s_nosave
    jmp rw_toast
.r:
    ret

; rw_rtcout - the trailer at rw_ramseg:rw_savelen: ten dwords (the live
; registers, then the latched) and the time it was written as 64 bits
rw_rtcout:
    push ax
    push cx
    push dx
    push si
    push di
    push es
    mov es, [rw_ramseg]
    mov di, [rw_savelen]
    mov si, rw_rtcsave
    mov cx, 10
    cld
.c:
    lodsb
    xor ah, ah
    stosw
    xor ax, ax
    stosw
    loop .c
    call rw_unix                    ; DX:AX
    stosw
    mov ax, dx
    stosw
    xor ax, ax
    stosw
    stosw
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret

; rw_rtcin - the trailer read back: the registers, and the seconds since it
; was written (none if the clock reads earlier than the stamp)
rw_rtcin:
    push ds
    push ds
    pop es
    mov si, [rw_savelen]
    mov di, rw_rtcsave
    mov cx, 10
    mov ds, [rw_ramseg]
    cld
.c:
    lodsw
    stosb
    lodsw
    loop .c
    mov ax, [si]                    ; the stamp's low dword
    mov dx, [si+2]
    pop ds
    mov bx, ax
    or bx, dx
    jz .r
    mov cx, ax
    mov bx, dx
    call rw_unix
    sub ax, cx
    sbb dx, bx
    jc .r                           ; the clock is behind the save
    mov [rw_rtcgap], ax
    mov [rw_rtcgap+2], dx
.r:
    ret

; rw_unix - the system clock as seconds since 1970 (DX:AX). Years 1980-2099,
; so every fourth year is a leap year.
rw_unix:
    push bx
    push cx
    push si
    push di
    call OSAPI_CLK_GET              ; CX year, DH:DL month:day, BH:BL h:m,
    push ax                         ;   AH seconds
    push bx
    mov si, cx                      ; SI = the year
    mov bl, dh
    xor bh, bh
    dec bx
    shl bx, 1
    mov di, [rw_cumdays+bx]         ; days before the month
    xor dh, dh
    dec dx
    add di, dx                      ; + the day
    cmp bx, 4                       ; past February in a leap year
    jb .nl
    test si, 3
    jnz .nl
    inc di
.nl:
    mov ax, si
    sub ax, 1969
    shr ax, 1
    shr ax, 1
    add di, ax                      ; + the leap days since 1970
    mov ax, si
    sub ax, 1970
    mov cx, 365
    mul cx
    add ax, di                      ; AX = days since 1970
    mov cx, 43200
    mul cx
    shl ax, 1
    rcl dx, 1                       ; DX:AX = days x 86,400
    mov si, ax
    mov di, dx
    pop bx                          ; BH hour, BL minute
    mov al, bh
    xor ah, ah
    mov cx, 3600
    mul cx
    add si, ax
    adc di, dx
    mov al, bl
    mov cl, 60
    mul cl
    add si, ax
    adc di, 0
    pop ax                          ; AH = seconds
    mov al, ah
    xor ah, ah
    add ax, si
    adc di, 0
    mov dx, di
    pop di
    pop si
    pop cx
    pop bx
    ret

rw_battab:      db 03h, 06h, 09h, 0Fh, 10h, 13h, 1Bh, 1Eh, 0
rw_cumdays:     dw 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334

; rw_fgo - stand in folder DX of volume BL (UI task), remembering where we
; stood for rw_fback. CF = 1: it could not, and nothing moved.
rw_fgo:
    push dx
    push bx
    call OSAPI_FILE_HERE
    mov [rw_hdir], dx
    mov [rw_hvol], bl
    pop bx
    pop dx
    push si
    push di
    call OSAPI_FILE_GOTO_QM
    pop di
    pop si
    ret

; rw_fback - back where rw_fgo found us. Every register and flag kept.
rw_fback:
    pushf
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov dx, [rw_hdir]
    mov bl, [rw_hvol]
    call OSAPI_FILE_GOTO_QM
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    popf
    ret

; rw_toast - SI = a line of our own, 24 characters at most
rw_toast:
    push ds
    pop es
    xor cx, cx
    call OSAPI_TOAST
    ret

; =============================================================================
; The worker
; =============================================================================
rw_worker_rs:                       ; THE RESTART POINT: our region moved with
rw_worker:                          ;   the worker parked at the top of its
    call OSAPI_CPU_INFO             ;   loop; draw the next frame whole
    mov bx, RW_BUDGET86
    cmp al, CPU_8086
    je .bud
    mov bx, RW_BUDGET
.bud:
    mov [rw_budget], bx
    call OSAPI_GET_TICKS
    mov [rw_last], ax
    call rw_drawnow                 ; the next frame draws
.loop:
    mov bx, [rw_win]
    call OSAPI_TASK_ALIVE           ; no lock held; a closed window ends here
    mov byte [rw_incore], 1         ; raised BEFORE [rw_fsq] is read: the
    cmp byte [rw_fsq], 0            ;   order rwfsx.inc's handoff rests on
    jne .sleep
    cmp byte [rw_resetq], 0
    je .noreset
    mov byte [rw_resetq], 0
    call rw_reset
.noreset:
    cmp byte [rw_seg2q], 0          ; Machine > Cache's second segment: the
    je .nosq                        ;   recompiler again over both (and
    mov byte [rw_seg2q], 0          ;   Static's preload, into the room)
    call rw_jiton
.nosq:
    cmp byte [rw_jitq], 0
    je .nojq
    mov byte [rw_jitq], 0
    mov bl, [rw_jitmode]            ; On -> Static -> Off -> Auto -> On
    xor bh, bh
    mov al, [rw_jnext + bx]
    mov [rw_jitmode], al
    call rw_jitset
    call rw_mgrey                   ; the item says what it is now
    cmp byte [rw_jitqn], 0          ; (F3's, through the UI task: said)
    je .nojq
    mov byte [rw_jitqn], 0
    mov si, [rw_i_mach + 6]
    call rw_note
.nojq:
    cmp byte [rw_state], 1
    jne .held
    cmp byte [rw_pause], 0
    jne .held
    call OSAPI_GET_TICKS
    mov bx, ax
    sub bx, [rw_last]
    js .resync
    mov [rw_last], ax
    cmp bx, 10
    jbe .acc
    mov bx, 10
.acc:
    mov ax, [rw_pertick]            ; (RW_PERTICK at 100%: Machine > Speed)
    mul bx
    add ax, [rw_owed]
    cmp ax, RW_OWEDMAX              ; a machine that fell behind runs on from
    jbe .owe                        ;   here rather than racing to catch up
    mov ax, RW_OWEDMAX
.owe:
    mov [rw_owed], ax
    push ax
    mov al, ah                      ; (frames owed, for the log)
    call rw_logowed
    pop ax
    cmp ax, 256                     ; nothing owed yet: draw what has not
    jb .idle                        ;   been, else sleep to the tick
    call rw_keys
    call rw_frame
    jc .loop                        ; it stopped
    call rw_sound
    inc word [rw_nrun]
    call rw_stat
    sub word [rw_owed], 256
    xor bx, bx                      ; caught up: draw this one, once the
    cmp word [rw_owed], 256         ;   last draw's own length has passed
    jb .due                         ;   since it ended...
    mov bl, [rw_owed + 1]           ; ...or, behind, draws' lengths later
    xor bh, bh                      ;   again (rw_drawdue): a third of the
    call rw_behind                  ;   machine to the picture, or less the
.due:                               ;   further behind, the rest to catching
    call rw_drawdue                 ;   up
    jnc .loop
    mov si, rw_present
    call rw_timed                   ; a draw of D ticks: the next after D more
    jmp .loop                       ; the clock is read again after EVERY
                                    ;   frame: a worker that spent what it
                                    ;   was owed before looking slept a tick
                                    ;   it did not have whenever it was behind
.idle:                              ; caught up, and the machine would
    cmp byte [rw_undrawn], 0        ;   only sleep: the picture has it,
    je .sleep                       ;   whatever rw_drawdue says (its half
    mov si, rw_present              ;   of the machine is for a game that
    call rw_timed                   ;   has frames to run)
    jmp .loop
.held:                              ; paused or stopped: nothing owed, and
    mov word [rw_owed], 0           ;   the clock kept - Go ran at once what
    call OSAPI_GET_TICKS            ;   the menu's own stall had owed before
.resync:                            ;   the pause (gblog: 30 frames, 133%)
    mov [rw_last], ax
.sleep:
    cmp byte [rw_pause], 0          ; paused or stopped: the speaker quiet
    jne .q
    cmp byte [rw_state], 1
    je .sl
.q:
    call rw_quiet
.sl:
    mov byte [rw_incore], 0
    mov ax, 1
    call OSAPI_TASK_SLEEP
    jmp .loop

; rw_drawdue - CF = 1 if a draw is due. BX = 0: the game has caught up, and
; a draw may start once as long as the last one took has passed since it
; ended, so drawing takes at most half the machine. BX = k: the game is
; behind, and k more such lengths must pass (rw_behind) - so a
; game that slips a little loses a little of its picture rate rather than
; dropping to a draw every few ticks, which is how the first field run saw
; Super Mario Land fall from ~30 frames drawn to 4 whenever it slipped under
; 100%. The clock is rw_clk's, 838 ns a count: a 286's draw is milliseconds
; and a tick could not tell one from nothing.
rw_drawdue:
    push ax
    push dx
    push bx
    call rw_clk
    sub ax, [rw_drawt]
    sbb dx, [rw_drawt + 2]
    js .no                          ; (signed: [rw_drawt] may be ahead)
.k:
    or bx, bx
    jz .yes
    sub ax, [rw_dlast]
    sbb dx, [rw_dlast + 2]
    js .no
    dec bx
    jmp short .k
.yes:
    pop bx
    pop dx
    pop ax
    stc
    ret
.no:
    pop bx
    pop dx
    pop ax
    clc
    ret

; rw_behind - BX = frames owed: BX = the draws' lengths rw_drawdue waits
; beyond the last one's - one, and one more for every eight frames behind,
; to three (a third of the machine to the picture, down to a fifth). The
; second field run's logs had Super Mario Land owing the whole half second
; through every scroll with a third still going to the picture.
rw_behind:
    shr bx, 1
    shr bx, 1
    shr bx, 1
    inc bx
    cmp bx, 3
    jbe .r
    mov bx, 3
.r:
    ret

; rw_drawnow - the next draw is due at once (a fresh start, or a clock that
; changed under the last one: into or out of full screen)
rw_drawnow:
    inc byte [rw_dgen]
    push ax
    push dx
    call rw_clk
    sub ax, 1
    sbb dx, 0
    mov [rw_drawt], ax
    mov [rw_drawt + 2], dx
    xor ax, ax
    mov [rw_dlast], ax
    mov [rw_dlast + 2], ax
    pop dx
    pop ax
    ret

; rw_timed - call SI (a draw), then [rw_drawt] = its end + its length, and
; the log told how long it took
rw_timed:
    mov byte [rw_undrawn], 0
    mov al, [rw_dgen]               ; (a clock changed under the draw - it
    push ax                         ;   parked across a whole full screen -
    call rw_clk                     ;   is no draw's length: the field run's
    push dx                         ;   window drew nothing for 34 seconds
    push ax                         ;   after leaving one)
    inc word [rw_ndrawn]
    call si
    call rw_clk                     ; DX:AX = the end
    pop bx
    pop cx                          ; CX:BX = the start
    pop si                          ; (SI's low byte: the count then)
    xchg si, ax
    cmp al, [rw_dgen]               ; ...against the count now
    xchg si, ax                     ; (xchg keeps the flags)
    je .same
    ret
.same:
    push dx
    push ax
    sub ax, bx
    sbb dx, cx                      ; DX:AX = the length
    mov [rw_dlast], ax
    mov [rw_dlast + 2], dx
    pop bx
    pop cx                          ; CX:BX = the end
    add bx, ax
    adc cx, dx
    mov [rw_drawt], bx
    mov [rw_drawt + 2], cx
    jmp rw_logdraw

; rw_frame - run the machine to its next frame, yielding between budgets.
; CF = 1: the core stopped (a bad opcode), and the UI task is told.
rw_frame:
    mov byte [rw_undrawn], 1
    call rw_clk                     ; (the log's: how long the machine ran,
    mov [rw_tgame], ax              ;   two reads of the clock a frame)
    mov [rw_tgame + 2], dx
    mov cx, 26                      ; with the LCD off no frame ever ends:
.run:                               ;   a frame's worth of budgets is one
    push cx
    mov ax, [rw_budget]
    push es                         ; the recompiler on: twice the budget -
    mov es, [rb_viewseg]            ;   it is the IRQ latency, and recompiled
    cmp byte [es:S_JITON], 0        ;   2000 M-cycles are ~2 ms on a 286, so
    pop es                          ;   4000 are still inside a 1200-baud
    je .b                           ;   mouse's 8 ms; half the runs, and of
    shl ax, 1                       ;   rb_run's rb_sched and event exit
.b:
    call rb_run                     ; ...and each returns with interrupts
    pop cx                          ;   on, so the tick can pre-empt us
    cmp al, RBX_FRAME               ;   between two: no yield per budget,
    je .done                        ;   which was nine task switches a frame
    cmp al, RBX_BADOP
    je .bad
    loop .run
.done:
    call rw_gameacc
    cmp byte [rw_infsx], 0          ; (in the bracket there is no one else)
    jne .ok
    call OSAPI_TASK_YIELD           ; one a frame, for a UI task a click woke
.ok:
    clc
    ret
.bad:
    mov byte [rw_state], 2
    mov bx, [rw_win]
    call OSAPI_WM_WAKE
    stc
    ret

; rw_sound - the speaker, after a frame: the LOUDER of the two square
; channels rbsys keeps (REALBOY-SPEC section 17), at 131,072 / (2048 - x)
; Hz, through OSAPI_SND_TONE - and only when the note changed. A refusal (a
; louder owner of the speaker) leaves [rw_tone] stale-zero, so the next
; frame asks again.
rw_sound:
    cmp byte [rw_sndm], 0           ; Machine > Sound: Off, or at full speed
    je .on                          ;   only - a tune slowed to Speed's 75%
    cmp byte [rw_sndm], 2           ;   is in time with nothing
    je rw_quiet
    cmp byte [rw_speed], 0
    jne rw_quiet
.on:
    push ds
    mov ds, [cs:rb_viewseg]
    xor bx, bx                      ; BL, BH = channel 1's, 2's volume (0 off)
    cmp byte [S_SQ1 + SQ_ON], 0
    je .v2
    mov bl, [S_SQ1 + SQ_VOL]
.v2:
    cmp byte [S_SQ2 + SQ_ON], 0
    je .v
    mov bh, [S_SQ2 + SQ_VOL]
.v:
    pop ds
    mov al, [rw_sch]                ; the channel playing STAYS while it
    cmp al, 1                       ;   sounds, unless the other is clearly
    jne .c2                         ;   louder: two voices crossing as their
    or bl, bl                       ;   envelopes fall made one speaker hop
    jz .any                         ;   between melody and harmony note by
    mov ah, bl                      ;   note (the first field run's "odd")
    add ah, 4
    cmp bh, ah
    jb .have
    mov al, 2
    jmp short .have
.c2:
    cmp al, 2
    jne .any
    or bh, bh
    jz .any
    mov ah, bh
    add ah, 4
    cmp bl, ah
    jb .have
    mov al, 1
    jmp short .have
.any:
    xor al, al                      ; none playing: the louder, if any
    cmp bl, bh
    jb .a2
    or bl, bl
    jz .have
    mov al, 1
    jmp short .have
.a2:
    mov al, 2
.have:
    mov [rw_sch], al
    push ds
    mov ds, [cs:rb_viewseg]
    mov dx, 0FF13h
    mov bl, al                      ; BL = the channel (0 none)
    cmp al, 2
    jne .pick
    mov dx, 0FF18h
.pick:
    xor ax, ax                      ; silent unless a channel sounds
    or bl, bl
    jz .play
    mov si, dx
    mov cx, [si]                    ; NRx3, NRx4: the 11-bit frequency
    and ch, 7
    mov bx, 2048
    sub bx, cx                      ; BX = 2048 - x, 1..2048
    mov dx, 2                       ; DX:AX = 131,072
    xor ax, ax
    div bx                          ; AX = hertz
    cmp ax, 20                      ; past the speaker's range: silent
    jb .zero
    cmp ax, 15000
    jbe .play
.zero:
    xor ax, ax
.play:
    pop ds
    cmp ax, [rw_tone]
    je .r
    mov [rw_tone], ax
    xor cx, cx                      ; until off
    mov dl, 40h
    call OSAPI_SND_TONE
    jnc .r
    mov word [rw_tone], 0FFFFh      ; refused: ask again next frame
.r:
    ret

; rw_quiet - the speaker off, if we had it
rw_quiet:
    cmp word [rw_tone], 0
    je .r
    mov word [rw_tone], 0
    xor ax, ax
    xor cx, cx
    mov dl, 40h
    call OSAPI_SND_TONE
.r:
    ret

; rw_reset - Machine > Reset, on the worker: rb_init again from the ROM
rw_reset:
    cmp byte [rw_state], 0
    je .r
    mov al, RLE_RESET
    call rw_logevt
    call rw_prfnote                 ; the profile's growth, before rb_init
    call rw_ramkeep                 ; the cartridge's RAM and clock survive
    call rw_start
    mov byte [rw_state], 1
    mov word [rw_owed], 0
.r:
    ret

; rw_stat - once a second, the overlay's line: the game's speed, frames run
; against the 59.7275 a second the cartridge expects, and the frames drawn
rw_stat:
    call OSAPI_GET_TICKS
    mov cx, ax
    sub cx, [rw_tstat]              ; CX = ticks counted
    cmp cx, 18
    jb .r
    mov [rw_tstat], ax
    cmp cx, 600                     ; a pause, or the first look: start over
    ja .zero0
    ; speed = run x 100 x 18.2065 / (59.7275 x ticks) = run x 3048 / (ticks x 100)
    mov ax, 100
    mul cx
    mov bx, ax                      ; BX = ticks x 100
    mov ax, [rw_nrun]
    mov dx, 3048
    mul dx                          ; DX:AX = run x 3048
    div bx                          ; AX = speed, %
    push ds
    pop es
    mov di, rw_ovltxt
    call rw_dec
    mov al, '%'
    stosb
    mov al, ' '
    stosb
    ; fps = drawn x 18.2065 / ticks ~ drawn x 182 / (ticks x 10)
    mov ax, 10
    mul cx
    mov bx, ax                      ; BX = ticks x 10
    mov ax, [rw_ndrawn]
    mov dx, 182
    mul dx
    div bx
    call rw_dec
    mov si, rw_s_fps
.c:
    lodsb
    stosb
    or al, al
    jnz .c
    push ds                         ; " JIT": the recompiler is running,
    mov ds, [cs:rb_viewseg]         ;   for a photograph of the glass to say
    mov al, [S_JITON]
    pop ds
    or al, al
    jz .rec
    dec di
    mov si, rw_s_jit
    cmp byte [rw_jitmode], 3        ; " AOT": Static's
    jne .cj
    mov si, rw_s_aot
.cj:
    lodsb
    stosb
    or al, al
    jnz .cj
.rec:
    call rw_logsec                  ; the second, into the log if it is on
    call rw_jitauto                 ; and Auto's look at the recompiler
    jmp short .zero
.zero0:
    call rw_logsec.zero
.zero:
    mov byte [rw_ovlnew], 1
    xor ax, ax
    mov [rw_nrun], ax
    mov [rw_ndrawn], ax
.r:
    ret

; rw_dec - AX (0-999) as decimal at ES:DI, no leading zeros
rw_dec:
    ; STKBALANCE-LOOP: one digit pushed a turn and the second loop pops them; the count is in CX
    push bx
    push cx
    push dx
    mov bx, 10
    xor cx, cx
.d:
    xor dx, dx
    div bx
    push dx
    inc cx
    or ax, ax
    jnz .d
.o:
    pop ax
    add al, '0'
    stosb
    loop .o
    pop dx
    pop cx
    pop bx
    ret

; rw_keys - the joypad, from the keys held - and nothing held while another
; window has the keyboard. F1 toggles the speed overlay.
rw_keys:
    xor dl, dl
    xor al, al                      ; the typed presses, taken whoever's the
    xchg al, [rw_klatch]            ;   keyboard is
    mov [rw_ktyped], al
    cmp byte [rw_infsx], 0          ; the bracket's keyboard is ours
    jne .f1
    call OSAPI_WM_TOP
    cmp bx, [rw_win]
    jne .set
    call OSAPI_MENU_OWNER
    cmp bx, [rw_win]
    jne .set
.f1:
    mov al, KSC_ALT                 ; Alt held: a chord of ours (Alt+Enter
    call OSAPI_KEY_DOWN             ;   would otherwise press Start too)
    jc .set
    mov al, 3Bh                     ; F1, on its press
    mov bx, rw_f1was
    call rw_kedge
    jnc .nof1
    xor byte [rw_ovl], 1
    mov byte [rw_ovlnew], 1
    mov al, RLE_F1
    call rw_logevt
    call rw_dmgfull                 ; the line it covered, or uncovered, is
                                    ;   not a change the picture made
.nof1:
    push dx
    mov al, 3Ch                     ; F2: Machine > Interlace's next, and
    mov bx, rw_f2was                ;   said (rw_note)
    call rw_kedge
    jnc .nof2
    call rw_iltoggle
    mov si, [rw_i_mach + 10]        ; (what rw_mgrey made the item say)
    call rw_note
.nof2:
    mov al, 3Dh                     ; F3: Machine > Recompiler's next - here,
    mov bx, rw_f3was                ;   between two core runs, in the window
    call rw_kedge                   ;   and the bracket alike (the menu's
    jnc .nof3                       ;   goes through the worker's rw_jitq)
    cmp word [rw_jitseg], 0
    je .nof3
    cmp byte [rw_jitmode], 1        ; On -> Static reads the profile and
    jne .f3go                       ;   may want the cache's room: the UI
    cmp byte [rw_infsx], 0          ;   task's (rw_stprep) - this one in
    jne .f3ui                       ;   the bracket, the window's woken
    mov byte [rw_f3q], 1
    mov bx, [rw_win]
    call OSAPI_WM_WAKE
    jmp short .nof3
.f3ui:
    call rw_stprep
.f3go:
    mov bl, [rw_jitmode]
    xor bh, bh
    mov al, [rw_jnext + bx]
    mov [rw_jitmode], al
    call rw_jitset
    call rw_mgrey
    mov si, [rw_i_mach + 6]
    call rw_note
.nof3:
    mov al, 3Eh                     ; F4: Machine > Speed's next, said, and
    mov bx, rw_f4was                ;   kept for the game by the UI task
    call rw_kedge
    jnc .nof4
    call rw_spdnext
    mov si, [rw_i_mach + 16]
    call rw_note
    mov byte [rw_spdq], 1
    mov bx, [rw_win]
    call OSAPI_WM_WAKE
.nof4:
    pop dx
    mov si, rw_keymap
    mov dh, 1
.k:
    lodsb
    or al, al
    jz .typ
    call OSAPI_KEY_DOWN             ; CF = 1: held
    jnc .n
    or dl, dh
.n:
    shl dh, 1
    jnz .k
.typ:
    ; A press TYPED since the last look is one, held now or not - a tap
    ; inside a draw is never seen held - but only for a button that was up
    ; then: a held key's typematic repeat, taken from the buffer after its
    ; release, would otherwise be a press nobody made
    mov al, [rw_kraw]
    not al
    and al, [cs:rw_ktyped]
    or dl, al
    ; OPPOSITE DIRECTIONS: a Game Boy's pad cannot hold both, a keyboard can,
    ; and Super Mario Land given both runs on to the right. Of a pair held
    ; together, the one pressed LATER wins - a roll from Right to Left turns
    ; at once, and letting Left go turns back while Right is still held
    push bx
    push cx
    mov ah, [rw_kraw]
    mov [rw_kraw], dl
    not ah
    and ah, dl                      ; AH = pressed since the last look
    mov cl, [rw_kpref]
    mov bl, 03h                     ; Right, Left
    call rw_socd
    mov bl, 0Ch                     ; Up, Down
    call rw_socd
    mov [rw_kpref], cl
    pop cx
    pop bx
.set:
    push ds
    mov ds, [cs:rb_viewseg]
    mov [S_JOY], dl
    pop ds
    ret
; rw_kedge - AL = a key's scancode, BX = its was-held byte: CF = 1 on its
; press (held now, not at the last look)
rw_kedge:
    call OSAPI_KEY_DOWN
    sbb al, al
    mov ah, al
    xchg al, [bx]
    not al
    and al, ah
    add al, 0FFh                    ; CF = 1: pressed now
    ret

; rw_note - SI = a line (a menu item's, its MENU_DIS mark skipped): said for
; a moment - a toast on the desktop, the speed line in the bracket, where a
; toast would wait for the desktop to come back (F2, F3)
rw_note:
    cmp byte [si], MENU_DIS
    jne .s
    inc si
.s:
    cmp byte [rw_infsx], 0
    jne .fs
    push es
    push cx
    push ds
    pop es
    xor cx, cx                      ; ~3 s
    call OSAPI_TOAST
    pop cx
    pop es
    ret
.fs:
    push di
    push cx
    push es
    push ds
    pop es
    mov di, rw_msg
    mov cx, 20
.c:
    lodsb
    stosb
    or al, al
    loopnz .c
    mov byte [di], 0
    pop es
    call OSAPI_GET_TICKS
    add ax, 45                      ; ~2.5 s
    mov [rw_msgend], ax
    mov byte [rw_msgt], 1
    mov byte [rw_ovlnew], 1
    pop cx
    pop di
    ret

; S_JOY's bits: Right, Left, Up, Down, A, B, Select, Start
rw_jnext:   db 1, 3, 0, 2           ; the setting after Auto, On, Off, Static
rw_keymap:  db KSC_RIGHT, KSC_LEFT, KSC_UP, KSC_DOWN, 2Dh, 2Ch, 39h, KSC_ENTER, 0
rw_ktyped:  db 0                    ; (rw_keys: this look's rw_klatch)

; rw_socd - one opposite pair, BL its two bits: DL the buttons, AH those
; pressed since the last look, CL the preferred of each pair. Not both held:
; the held one, or none, is the preference. Both: one newly pressed takes
; it, and the other is dropped from DL
rw_socd:
    mov bh, dl
    and bh, bl
    cmp bh, bl
    je .both
.pref:
    not bl
    and cl, bl
    not bl
    or cl, bh
    ret
.both:
    mov bh, ah
    and bh, bl
    jz .k                           ; neither new: as it was
    cmp bh, bl
    je .k                           ; both new at once: as it was
    call .pref                      ; the newer
.k:
    mov bh, cl
    and bh, bl
    not bl
    and dl, bl
    not bl
    or dl, bh
    ret

; rw_klat - AH = a typed key's scancode: its button latched for rw_keys
rw_klat:
    push ax
    push si
    mov si, rw_keymap
    mov al, 1
.l:
    cmp byte [si], 0
    je .r
    cmp ah, [si]
    je .hit
    inc si
    shl al, 1
    jmp short .l
.hit:
    or [rw_klatch], al
.r:
    pop si
    pop ax
    ret

; rw_present - compose the frame and put it on the glass (the worker's)
rw_present:
    mov bx, [rw_win]
    call OSAPI_WM_DISPLAY           ; DH = bits per pixel
    push ds
    pop es
    cmp dh, 1
    jbe .mono
    cmp byte [rw_nobp], 0
    jne .mono
    cmp byte [rw_pfmt], 4           ; colour: the changed lines, as the
    je .c1                          ;   four planes BLITP reads (a buffer of
    call rw_dmgfull                 ;   the other format: every line again)
.c1:
    call rw_render
    mov byte [rw_pfmt], 4
    or ax, ax
    jz .none
    call rw_planes
    jmp short .show
.mono:
    cmp byte [rw_pfmt], 1           ; the buffer held the other format:
    je .m1                          ;   every line again
    call rw_dmgfull
.m1:
    call rw_render                  ; AX = the lines that changed
    mov byte [rw_pfmt], 1
    or ax, ax
    jnz .m2
.none:
    mov byte [rw_incore], 0         ; nothing did: nothing to put up
    ret
.m2:
    call rw_dither
.show:
    mov byte [rw_incore], 0         ; out of the machine BEFORE the lock: the
                                    ;   UI task may hold it, waiting on this
    mov byte [rw_shown], 1
    cmp byte [rw_abon], 0           ; the About card is over us: keep it
    jne .r
    call OSAPI_GFX_LOCK
    mov ax, KERNEL_SEG              ; a worker loads ES itself
    mov es, ax
    mov bx, [rw_win]
    test word [es:bx + W_FLAGS], 2
    jz .un
    call OSAPI_WM_CLIP_SET          ; CF = 1: not a pixel of us shows
    jc .un
    call rw_blitd                   ; the changed lines' bands
    call rw_overlay
.un:
    call OSAPI_GFX_UNLOCK
.r:
    ret

; rw_overlay - the speed line over the picture's top left, when F1 put it up
rw_overlay:
    cmp byte [rw_ovl], 0
    je .r
    cmp byte [rw_ovltxt], 0
    je .r
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    mov cx, ax
    mov si, rw_ovltxt
    mov ax, (CWHITE << 8) | CBLACK
    call OSAPI_FONT_RUN
.r:
    ret

; rw_blit - rw_pbuf onto the content, the lock held and the clip armed:
; BLITP's four planes on a colour display, the dithered band through BLIT1 on
; a monochrome one (or where BLITP refuses). A buffer composed for the other
; kind of display - the window moved between two - paints white, and the
; worker's next draw puts the picture back.
rw_blit:
    mov bx, [rw_win]
    call OSAPI_WM_DISPLAY           ; DH = bits per pixel
    cmp dh, 1
    jbe .mono
    cmp byte [rw_pfmt], 4
    jne .colmono
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    mov bx, dx
    push ds
    pop es
    mov si, rw_pbuf
    mov di, 4000h | 20              ; walk an armed clip; 20 bytes a plane
    mov bp, 80
    mov cx, RW_CONT_W
    mov dx, RW_CONT_H
    call OSAPI_GFX_BLITP
    jnc .r
    mov byte [rw_nobp], 1           ; refused (a straddle, kern_small): the
    jmp short .white                ;   next frame is dithered
.colmono:
    cmp byte [rw_pfmt], 1
    jne .white
    mov al, CWHITE                  ; the dither on a colour display, in two
    mov ah, CBLACK                  ;   colours
    call OSAPI_GFX_BLIT1_PEN
    jmp short .b1
.mono:
    cmp byte [rw_pfmt], 1
    jne .white
.b1:
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT
    mov bx, dx
    push ds
    pop es
    mov si, rw_pbuf
    mov bp, 20
    mov cx, RW_CONT_W
    mov dx, RW_CONT_H
    call OSAPI_GFX_BLIT1
.r:
    ret
.white:
    jmp rw_fillwhite

; rw_dither - rw_fbuf as one bit a pixel, 1 = lit: shade 0 all lit, 1 a
; quarter dark, 2 half (a checkerboard), 3 all dark - a 2x2 ordered dither
rw_dither:
    push ds
    pop es
    mov si, rw_fbuf
    mov di, rw_pbuf
    xor dx, dx                      ; DL = the row's parity
.row:
    call rw_dchg                    ; ZF = 1: this line did not change
    jnz .do
    add si, 40
    add di, 20
    jmp short .nx
.do:
    mov bl, 0AAh                    ; even rows: half on even columns, the
    mov bh, 0AAh                    ;   quarter on even columns
    test dl, 1
    jz .ev
    mov bl, 055h                    ; odd rows: the other half, no quarter
    xor bh, bh
.ev:
    mov cx, 20
.b:
    mov al, [si]                    ; bit 0
    mov ah, [si+20]                 ; bit 1
    mov dh, al
    and dh, ah                      ; shade 3: dark
    not al
    and al, ah                      ; shade 2: bit 1 alone
    and al, bl
    or dh, al
    mov al, [si]
    not ah
    and al, ah                      ; shade 1: bit 0 alone
    and al, bh
    or al, dh
    not al                          ; lit = not dark
    stosb
    inc si
    loop .b
    add si, 20
.nx:
    inc dl
    cmp dl, RW_CONT_H
    jb .row
    ret

; rw_dchg - DL = a line: ZF = 0 if the last rb_renderd changed it
rw_dchg:
    push bx
    mov bl, dl
    xor bh, bh
    cmp byte [rw_chg + bx], 0
    pop bx
    ret

; rw_render - rb_renderd into rw_fbuf, and its changed lines into rw_chg
; (every line, without the damage memory). AX = how many.
rw_render:
    push bx
    push cx
    push dx
    push si
    push di
    push ds
    pop es
    mov di, rw_fbuf
    mov word [rb_dhook], rw_dscanhk
    call rw_clk                     ; (the log's: the scan and the lines)
    mov [rw_tscan], ax              ; (the scan's end, if there is none)
    mov [rw_tscan + 2], dx
    push dx
    push ax
    call rb_renderd
    push ax
    call rw_clk
    mov bx, [rw_tscan]
    mov cx, [rw_tscan + 2]
    mov si, rw_acms                 ; the lines: the scan's end to now
    call rw_logacc
    mov ax, bx
    mov dx, cx
    pop si
    pop bx
    pop cx
    push si
    mov si, rw_asms                 ; the scan: the start to its end
    call rw_logacc
    pop ax
    push ax
    add [rw_achg], ax               ; (the log's counts)
    mov di, rw_chg
    mov cx, 144 / 2
    mov ax, [rb_dmgseg]
    or ax, ax
    jnz .cp
    add word [rw_acomp], 144
    mov ax, 0101h
    rep stosw
    jmp short .r
.cp:
    push ds
    mov ds, ax
    mov si, RB_DCHG
    rep movsw
    xor ax, ax
    xchg ax, [RB_DCOMP]
    pop ds
    add [rw_acomp], ax
.r:
    pop ax
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; rw_blitd - the lines rb_renderd changed onto the content, a band a run of
; them, the lock held and the clip armed. Nothing changed, nothing drawn.
rw_blitd:
    mov bx, [rw_win]
    call OSAPI_WM_DISPLAY           ; DH = bits per pixel
    cmp dh, 1
    jbe .mono
    cmp byte [rw_pfmt], 4           ; (the planes: BLITP's bands below)
    je .mono
    mov al, CWHITE                  ; the dither on a colour display
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
.mono:
    xor dl, dl                      ; DL = the line
.find:
    call rw_dchg
    jnz .run
.nx:
    inc dl
    cmp dl, RW_CONT_H
    jb .find
    ret
.run:
    mov dh, dl                      ; DH = the run's first line
.ext:
    inc dl
    cmp dl, RW_CONT_H
    jae .put
    call rw_dchg
    jnz .ext
.put:                               ; DH = the run's first line, DL past it
    push dx
    mov bl, dh
    xor bh, bh
    mov ax, 20
    mul bx
    mov si, rw_pbuf
    add si, ax                      ; SI = the run in the dithered buffer
    push bx
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    pop bx
    add bx, dx                      ; BX = the run's row on the screen
    pop dx
    push dx
    mov cl, dl
    sub cl, dh
    xor ch, ch
    mov dx, cx                      ; DX = its lines
    push ds
    pop es
    cmp byte [rw_pfmt], 4
    je .planes
    mov bp, 20
    mov cx, RW_CONT_W
    call OSAPI_GFX_BLIT1
    pop dx
    jmp short .nx
.planes:                            ; the four planes' band, from the same
    sub si, rw_pbuf                 ;   first line: 80 bytes a line, not 20
    shl si, 1
    shl si, 1
    add si, rw_pbuf
    mov di, 4000h | 20              ; walk an armed clip; 20 bytes a plane
    mov bp, 80
    mov cx, RW_CONT_W
    call OSAPI_GFX_BLITP
    pop dx
    jnc .nx
    mov byte [rw_nobp], 1           ; refused (a straddle, kern_small): the
    mov byte [rw_pfmt], 0           ;   next draw is dithered, every line
    ret

; rw_planes - the lines rb_renderd changed, from rw_fbuf's two shade planes
; into rw_pbuf as BLITP's four: NOT bit 1 three times, then NOT bit 0 - the
; desktop's 15, 7, 8 and 0 for shades 0-3 (rb_render4's layout)
rw_planes:
    push ds
    pop es
    xor dx, dx                      ; DL = the line
    mov si, rw_fbuf
    mov di, rw_pbuf
.l:
    call rw_dchg
    jz .n
    push si
    push di
    add si, 20                      ; bit 1, NOT, to planes 0-2
    mov cx, 10
.b1:
    lodsw
    not ax
    mov [di + 20], ax
    mov [di + 40], ax
    stosw
    loop .b1
    add di, 40                      ; bit 0, NOT, to plane 3
    sub si, 40
    mov cx, 10
.b0:
    lodsw
    not ax
    stosw
    loop .b0
    pop di
    pop si
.n:
    add si, 40
    add di, 80
    inc dl
    cmp dl, RW_CONT_H
    jb .l
    ret

; rw_dmgclaim - on the UI task, once: rb_renderd's memory, when there is
; room (without it every frame is composed whole)
rw_dmgclaim:
    cmp word [rb_dmgseg], 0
    jne .r
    mov ax, (RB_DMG_SIZE + 1023) / 1024
    call OSAPI_MEM_CLAIM
    jc .r
    mov [rb_dmgseg], dx
.r:
    ret

; rw_dmgfull - the next rb_renderd composes and writes every line
; rw_spdset - [rw_speed] into the clocks: rw_spdk, the Game Boy's frames
; 256ths at a time, and rw_pertick, the window's frames a BIOS tick x 256.
; 100% is 256 and RW_PERTICK, as ever. Kept: all
rw_spdset:
    push ax
    push bx
    push dx
    mov bl, [rw_speed]
    xor bh, bh
    shl bx, 1
    mov ax, [rw_spdtab + bx]
    mov [rw_spdk], ax
    mov dx, RW_PERTICK
    mul dx
    mov al, ah
    mov ah, dl
    mov [rw_pertick], ax
    pop dx
    pop bx
    pop ax
    ret

; rw_spdnext - Machine > Speed's next (F4's too, on the worker or in the
; bracket): the clocks, the game's record, the menu. The file is the UI
; task's (rw_spdmenu, rw_onwake)
rw_spdnext:
    mov al, [rw_speed]
    inc ax
    cmp al, RW_SPEEDS
    jb .s
    xor al, al
.s:
    mov [rw_speed], al
    call rw_spdset
    call rw_cfgrec
    jmp rw_mgrey

; rw_spdmenu / rw_sndmenu - Machine > Speed and Sound, on the UI task: the
; next, and REALBOY.CFG written - each kept for the game it was chosen in
rw_spdmenu:
    call rw_spdnext
    jmp rw_cfgsave
rw_sndmenu:
    mov al, [rw_sndm]
    inc ax
    cmp al, 3
    jb .s
    xor al, al
.s:
    mov [rw_sndm], al
    call rw_cfgrec
    call rw_mgrey
    jmp rw_cfgsave

; rw_spdgame - a game loaded: its header's key (014Dh, 014Eh, as its
; profile's name), and its Speed and Sound if REALBOY.CFG has them - a game
; it does not have keeps what was chosen before it, kept at its first change
rw_spdgame:
    push si
    push ds
    mov ds, [cs:rb_viewseg]
    mov al, [014Dh]
    mov si, [014Eh]
    pop ds
    mov [rw_gkey], al
    mov [rw_gkey + 1], si
    mov byte [rw_gkon], 1
    call rw_cfgfind                 ; SI = its entry, CF = 1 none
    jc .r
    mov al, [si + 3]
    mov ah, al
    and al, 7
    cmp al, RW_SPEEDS
    jae .r
    mov cl, 3
    shr ah, cl
    and ah, 3
    cmp ah, 3
    jae .r
    mov [rw_speed], al
    mov [rw_sndm], ah
    call rw_spdset
    call rw_mgrey
.r:
    pop si
    ret

; rw_cfgfind - SI = the game's entry in rw_cfg's table, or CF = 1
rw_cfgfind:
    push cx
    mov cl, [rw_cfg + 4]
    xor ch, ch
    mov si, rw_cfg + 8
    jcxz .no
.f:
    mov al, [si]
    cmp al, [rw_gkey]
    jne .n
    mov ax, [si + 1]
    cmp ax, [rw_gkey + 1]
    je .y
.n:
    add si, 4
    loop .f
.no:
    stc
    pop cx
    ret
.y:
    clc
    pop cx
    ret

; rw_cfgrec - the game's Speed and Sound to the front of rw_cfg's table (its
; old entry out, or the oldest when it is full). No game, nothing. Kept: all
rw_cfgrec:
    cmp byte [rw_gkon], 0
    je .r0
    push ax
    push cx
    push si
    push di
    push es
    push ds
    pop es
    call rw_cfgfind                 ; SI = its entry: the ones before it
    jnc .mv                         ;   move up over it
    mov al, [rw_cfg + 4]            ; none: every one moves, the last off the
    cmp al, RW_CFGGN                ;   end when it is full
    jae .full
    inc byte [rw_cfg + 4]
.full:
    mov si, rw_cfg + 8 + (RW_CFGGN - 1) * 4
.mv:
    mov cx, si                      ; CX = the bytes before it
    sub cx, rw_cfg + 8
    lea di, [si + 3]                ; backwards: each up one entry
    lea si, [si - 1]
    std
    rep movsb
    cld
    mov al, [rw_gkey]
    mov [rw_cfg + 8], al
    mov ax, [rw_gkey + 1]
    mov [rw_cfg + 9], ax
    mov al, [rw_sndm]
    mov cl, 3
    shl al, cl
    or al, [rw_speed]
    mov [rw_cfg + 11], al
    pop es
    pop di
    pop si
    pop cx
    pop ax
.r0:
    ret

; rw_iltoggle - Machine > Interlace (REALBOY-SPEC 13.2), Off -> On ->
; Scrolling: a draw composes the lines of one parity, the next the other's,
; for twice the pictures a second at a price in looks - always, or only
; while the picture scrolls; off, every line again. Either way the next draw
; is whole
rw_iltoggle:
    mov al, [rb_ilace]              ; Off -> On -> Scrolling -> Doubled
    inc ax                          ;   -> Off
    cmp al, 4
    jb .s
    xor al, al
.s:
    mov [rb_ilace], al
    call rw_dmgfull
    jmp rw_mgrey

rw_dmgfull:
    push es
    push ax
    mov ax, [rb_dmgseg]
    or ax, ax
    jz .r
    mov es, ax
    mov byte [es:RB_DFULL], 1
.r:
    pop ax
    pop es
    ret

; =============================================================================
; The window
; =============================================================================

; rw_paint - SI = the window, the lock held, the clip armed
rw_paint:
    call rw_mgrey
    push si
    mov byte [rw_nobp], 0           ; a paint asks BLITP again: the window
    cmp byte [rw_shown], 0          ;   may have moved off the straddle
    je .blank
    call rw_blit
    jmp short .about
.blank:
    call rw_fillwhite
    mov si, rw_s_open1
    cmp byte [rw_state], 2
    jne .t
    mov si, rw_s_stop1
.t:
    mov dx, 60
    call rw_line
    mov si, rw_s_open2
    cmp byte [rw_state], 2
    jne .t2
    mov si, rw_s_stop2
.t2:
    mov dx, 74
    call rw_line
.about:
    pop si
    cmp byte [rw_abon], 0
    je .r
    push si
    mov bx, si
    mov si, rw_ablines
    call os88ui_about_d
    pop si
    cmp byte [rw_spawned], 0        ; a refused hire is asked again here
    jne .r
    cmp byte [rw_state], 1
    jne .r
    call rw_hire
.r:
    ret

; rw_line - SI = a string, DX = its row in the content, centred
rw_line:
    push ax
    push bx
    push cx
    push dx
    mov cx, dx
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT           ; AX = left, DX = top
    add dx, cx                      ; DX = the row
    mov bx, ax
    call OSAPI_FONT_WIDTH           ; AX = the string's width
    mov cx, RW_CONT_W
    sub cx, ax
    sar cx, 1
    add cx, bx                      ; CX = x
    mov ax, (CWHITE << 8) | CBLACK
    call OSAPI_FONT_RUN
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rw_fillwhite - the content white
rw_fillwhite:
    push ax
    push bx
    push cx
    push dx
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov bx, [rw_win]
    call OSAPI_WM_CONTENT
    mov bx, dx
    mov cx, ax
    add cx, RW_CONT_W - 1
    add dx, RW_CONT_H - 1
    call OSAPI_GFX_FILL
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; rw_repaint - SI = the window, the lock held: everything, ourselves
rw_repaint:
    push bx
    mov bx, si
    call OSAPI_WM_CLIP_SET
    pop bx
    jc .r
    jmp rw_paint
.r:
    ret

; rw_oncmd - AH = the menu, AL = the item, SI = the window, the lock held
rw_oncmd:
    push ax
    call rw_abdismiss
    pop ax
    cmp ah, 0
    jne .machine
    cmp al, 0
    je rw_open
    push si                         ; File > Close: the close box's work
    call rw_onclose                 ;   first - the battery's RAM, the
    pop si                          ;   profile, the log - since a close the
    mov bx, si                      ;   package asks for itself is never put
    call OSAPI_WM_CLOSE             ;   to its negotiator (SPEC.md 75.2)
    ret
.machine:
    cmp al, 0
    jne .pause
    mov byte [rw_resetq], 1         ; Reset: the worker's to do
    ret
.pause:
    cmp al, 1
    je .p
    cmp al, 2
    je rw_fsenter                   ; Full Screen
    cmp al, 4
    je rw_logtoggle                 ; Log
    cmp al, 5
    je rw_iltoggle                  ; Interlace
    cmp al, 6
    je rw_prftoggle                 ; Profile
    cmp al, 7
    je rw_bigtoggle                 ; Cache
    cmp al, 8
    je rw_spdmenu                   ; Speed
    cmp al, 9
    je rw_sndmenu                   ; Sound
    cmp word [rw_jitseg], 0         ; Recompiler: the worker flips it
    je .r
    cmp byte [rw_jitq], 0
    jne .r
    call rw_stprep
    mov byte [rw_jitq], 1
.r:
    ret
.p:
    xor byte [rw_pause], 1
    mov al, RLE_PAUSE
    jnz .pe
    mov al, RLE_GO
.pe:
    jmp rw_logevt

; rw_onkey - AX = a typed key, SI = the window, the lock held: Alt+Enter is
; Machine > Full Screen (SPEC.md 11.2.1.1); the game reads the keys held,
; not the keys typed, so nothing else here is ours
rw_onkey:
    cmp ax, KEY_ALTENTER
    jne .r
    call rw_abdismiss
    jmp rw_fsenter
.r:
    jmp rw_klat                     ; a press a draw would hide (rw_keys)

rw_about:
    mov byte [rw_abon], 1
    mov bx, si
    mov si, rw_ablines
    jmp os88ui_about

rw_abdismiss:
    mov bx, rw_abon
    mov ax, rw_repaint
    jmp os88ui_abdismiss

rw_tpl:
    dw 160, 60, RW_CONT_W + 2, RW_CONT_H + TITLE_H + 2
    dw rw_ttl, rw_paint, rw_onkey, rw_abdismiss

    OS88_MENUSET rw_menus, rw_ttl, rw_oncmd
        OS88_MENU rw_m_file, rw_i_file, 2
        OS88_MENU rw_m_mach, rw_i_mach, 10
    OS88_MENUSET_END rw_menus

rw_ttl:         db 'RealBoy', 0
rw_m_file:      db 'File', 0
rw_i_file:      dw rw_it_open, rw_it_close
rw_it_open:     db 'Open...', 0
rw_it_close:    db 'Close', 0
rw_m_mach:      db 'Machine', 0
rw_i_mach:      dw rw_it_reset, rw_it_pause, rw_it_fs0, rw_it_jit0, rw_it_log0
                dw rw_it_il0, rw_it_prf0, rw_it_big0, rw_it_spd0, rw_it_snd0
rw_it_reset:    db 'Reset', 0
rw_it_pause:    db 'Pause', 0
rw_it_fs:       db 'Full Screen', 0
rw_it_fs0:      db MENU_DIS, 'Full Screen', 0
rw_it_jauto:    db 'Recompiler: Auto', 0
rw_it_jon:      db 'Recompiler: On', 0
rw_it_joff:     db 'Recompiler: Off', 0
rw_it_jst:      db 'Recompiler: Static', 0
rw_it_jit0:     db MENU_DIS, 'Recompiler (286)', 0
rw_it_log0:     db 'Log: Off', 0
rw_it_log1:     db 'Log: On', 0
rw_it_il0:      db 'Interlace: Off', 0
rw_it_il1:      db 'Interlace: On', 0
rw_it_prf0:     db 'Profile: Off', 0
rw_it_prf1:     db 'Profile: On', 0
rw_it_prfd:     db MENU_DIS, 'Profile (286)', 0
rw_s_prfst:     db 'Static reads the profile', 0
rw_it_big0:     db 'Cache: 64K', 0
rw_it_big1:     db 'Cache: 128K', 0
rw_it_bigd:     db MENU_DIS, 'Cache (286)', 0
rw_s_bignx:     db 'Cache: from the next game', 0
rw_s_cfg:       db 'REALBOY.CFG', 0
rw_it_il2:      db 'Interlace: Scrolling', 0
rw_it_il3:      db 'Interlace: Doubled', 0
rw_it_spd0:     db 'Speed: 100%', 0
rw_it_spd1:     db 'Speed: 90%', 0
rw_it_spd2:     db 'Speed: 75%', 0
rw_it_spd3:     db 'Speed: 60%', 0
rw_it_spd4:     db 'Speed: 50%', 0
rw_it_snd0:     db 'Sound: On', 0
rw_it_snd1:     db 'Sound: At 100% only', 0
rw_it_snd2:     db 'Sound: Off', 0
rw_spdit:       dw rw_it_spd0, rw_it_spd1, rw_it_spd2, rw_it_spd3, rw_it_spd4
rw_sndit:       dw rw_it_snd0, rw_it_snd1, rw_it_snd2
rw_spdtab:      dw 256, 230, 192, 154, 128  ; Speed, 256ths of the Game Boy's

rw_s_fps:       db 'fps', 0
rw_s_jit:       db ' JIT', 0
rw_s_aot:       db ' AOT', 0
rw_s_open1:     db 'File > Open a', 0
rw_s_open2:     db 'Game Boy .GB', 0
rw_s_stop1:     db 'The game stopped:', 0
rw_s_stop2:     db 'an invalid opcode', 0
rw_s_one:       db 'REALBOY: one game each', 0
rw_s_big:       db 'REALBOY: over 256K wants XMS', 0
rw_s_notrom:    db 'REALBOY: not a GB ROM', 0
rw_s_room:      db 'REALBOY: no room for ROM', 0
rw_s_read:      db 'REALBOY: read failed', 0
rw_s_noram:     db 'REALBOY: no room for RAM', 0
rw_s_nosave:    db 'REALBOY: save failed', 0

rw_ablines:
    dw rw_ab1, rw_ab2, rw_ab3, rw_ab4, rw_ab5, rw_ab6, rw_ab7, 0
rw_ab1:         db 'RealBoy', 0
rw_ab2:         db 'a Game Boy for os8088', 0
rw_ab3:         db 0
rw_ab4:         db 'Arrows, X = A, Z = B', 0
rw_ab5:         db 'Enter = Start', 0
rw_ab6:         db 'Space = Select', 0
rw_ab7:         db 'F1 = speed', 0

%include "rbdefs.inc"
%include "rbsys.inc"
%include "rbppu.inc"
%include "rwfsx.inc"
%include "rbjit.inc"

%include "os88alt.inc"
%include "os88pit.inc"
%include "rwlog.inc"
%include "rwbank.inc"
%include "os88data.inc"

%define OS88UI_ABOUT
%define OS88UI_NOBTN
%define OS88UI_ABDISMISS
%include "os88ui.inc"

; THE PART TABLE (SPEC.md 20.12.3): the core, compressed on the disk, and the
; view, a zeroed carve that costs no disk at all
OS88_PARTS_BEGIN 3
    OS88_PART OP_SEG, OP_COMP                   ; 0  the core's first half
    OS88_PART OP_ASSET, OP_COMP                 ; 1  ...and its second: one
                                                ;    part is at most 65,024
                                                ;    bytes (SPEC.md 20.12.11)
    OS88_PART OP_ASSET, OP_ZERO, 64             ; 2  the view
OS88_PARTS_END
    align 2, db 0
    OS88_BSS OP_BSS + RW_BSS
    OS88_IMAGE_END
