; =============================================================================
; kerndos/kdresume.inc - THE LIVE RESUME (SPEC.md 96.49,
; docs/plans/KERN-DOS-PLAN.md 8.1)
;
; The DOS program has exited and there is a hibernation image on the fixed
; disk. W6 got back to it by `int 19h` - a whole POST and a whole boot, after
; which os8088's own `hb_probe` finds the pointer and resumes. This puts the
; image back HERE, with no boot in between: read `HIBERNAT.IMG` over
; conventional memory and jump to the kernel's wake address, which is exactly
; what SPEC.md 87.5's stub does for an ordinary resume.
;
; **8.1 REFUSED THIS AND THE REFUSAL WAS WRONG ABOUT *WHEN*.** Its argument
; was that the extent list cannot be bounded cheaply, because *"the one place
; it could live is `kern_dos`'s own image: the text framebuffer is not
; available, since the DOS program prints into it"*. That is true DURING the
; program and this runs after it has gone - at `kd_leave`, with the screen
; about to be overwritten by the image anyway. So the list goes where the
; kernel's own goes, at `HS_EXT`, and costs this image nothing at all: 1,280
; extents of video RAM that no rung of the ladder owns.
;
; What it does cost is the STUB, and that is irreducible - `kernel/hbstub.inc`
; is ~440 bytes and has to BE somewhere to be staged. It is shared as source
; rather than copied (that file's own header says why), and the second half of
; the bill is this file's find, walk and stage.
;
; **THE DISK LAYER IS THE REASON THIS IS SMALL.** `kern_dos` already carries
; `disk.inc` whole, so finding a file and walking its chain are calls rather
; than code - and since SPEC.md 96.46 it carries the kernel's volume table
; too, so the FIXED DISK the image lives on is a volume it can actually
; mount. This wave rests on that one.
;
; EVERY REFUSAL FALLS BACK TO `int 19h`, which is W6's route and works. A
; machine that cannot find its image, cannot mount its volume or runs out of
; extents reboots and resumes the long way instead of losing the session -
; so the fast path is an optimisation and never a new way to fail.
; =============================================================================

; -----------------------------------------------------------------------------
; kd_resume - put the session back, or answer CF=1 and let kd_leave reboot
; in:  SI -> the launch block; DS = ES = KD_SEG; interrupts on
; out: DOES NOT RETURN on success. CF=1 = could not, and nothing is disturbed
;      beyond a mount.
;
; **NOTHING IS TORN DOWN UNTIL THE LAST MOMENT**, which is `hbm_res`'s order
; and for its reason: every refusal above the handover is survivable, and a
; machine that has masked its interrupts and then found no image is one that
; cannot reboot cleanly either.
; -----------------------------------------------------------------------------
kd_resume:
    test word [si+KDL_FLAGS], KDLF_HIBER
    jz .no                      ; no image was written: 96.42's floppy arm,
                                ; where the machine restarts and says so
    cmp word [si+KDL_WAKE + 2], 0
    je .no                      ; ...and no wake address is the same answer
                                ; from the other side: a kernel too old to
                                ; carry one (KDL_VER's whole job)

    ; --- 1. the volume the image is on, and the image ------------------------
    mov al, [si+KDL_HBVOL]
    cmp al, DVOL_MAX
    jae .no
    mov [kdr_vol], al
    mov dl, al
    call disk_mount_x
    jc .no
    xor ax, ax                  ; the ROOT: hb_probe writes the pointer and
    call dsk_chdir_q_x          ; the image there (SPEC.md 87.1). THE QUIET
                                ; ONE (96.47): this stands in a directory to
                                ; READ one file out of it and never to list
                                ; it, and the loud chdir rebuilds the global
                                ; listing on the way
    jc .no
    mov si, kdr_s_img
    call dsk_find_name_x        ; AX = the index
    jc .no
    call dsk_get_dir_x          ; SI -> the staged entry (SPEC.md 19.1)
    jc .no
    mov ax, [si + 18]           ; the first cluster is at 18 and NOT at the
    mov [kdr_clus], ax          ; FAT record's own 26 (SPEC.md 96.37.1 item 4)
    ; **AND ITS LENGTH, WHICH IS THE FILE'S AND NOT MEMORY'S.** The first
    ; version sized the walk from `[kd_top]` - the box's banked BDA figure -
    ; because that is what `hbm_extents` does with `[mem_top]` over there.
    ; They are two different quantities: the kernel writes `[mem_top]`
    ; paragraphs and this host's idea of the top of memory is a cap the BOX
    ; banked, so a machine where they disagree restores SHORT. It presented
    ; as a session that came back with the kernel intact and the package heap
    ; full of rubbish - a window whose title was 24 bytes of 0x86 - because a
    ; region is claimed TOP-DOWN (mem_claim_hi_x) and so lives in the tail
    ; that was never read. The directory entry says how long the file is; ask
    ; it.
    ; **AT 20 AND NOT AT 28**, which is the same trap as the cluster one line
    ; up wearing different clothes: this is SPEC.md 19.1's SYNTHESIZED entry
    ; and not an on-disk FAT record, so the size is the dword at 20 (lo @20,
    ; hi @22) where the raw record keeps it at 28. Bytes 24..31 of a staged
    ; entry are DECLARED ZERO, so reading 28 gets a confident nothing - the
    ; walk refused, `kd_leave` fell back to `int 19h`, and the only symptom
    ; was a return that took fifteen guest seconds instead of three.
    mov ax, [si + 20]
    mov dx, [si + 22]
    add ax, 511                 ; ...as whole sectors, rounded up
    adc dx, 0
    mov cl, 9
    shr ax, cl
    mov cl, 7
    shl dx, cl                  ; the high word's bits fold down beside them
    or ax, dx
    or ax, ax
    jz .no
    mov [kdr_secs], ax

    ; --- 2. the transport, out of the table 96.46 carried --------------------
    ; No probe and no second set of fields: the unit and the partition base
    ; are this volume's own row, and a fixed disk's spt/heads came over beside
    ; the table. That is the whole of what `hbm_geomd` works out over there.
    mov bl, [kdr_vol]
    xor bh, bh
    mov cl, 4
    shl bx, cl
    add bx, dsk_vtab
    mov al, [bx+DV_UNIT]
    xor ah, ah
    mov [kdr_unit], ax
    mov bl, [kdr_vol]
    xor bh, bh
    shl bx, 1
    shl bx, 1
    add bx, dsk_vbase
    mov ax, [bx]
    mov [kdr_base], ax
    mov ax, [bx+2]
    mov [kdr_base+2], ax
    mov si, [kd_lbp]
    mov ax, [si+KDL_HDSPT]
    or ax, ax
    jz .no                      ; a zero geometry is the mount failing later
    mov [kdr_spt], ax
    mov ax, [si+KDL_HDHDS]
    or ax, ax
    jz .no
    mov [kdr_heads], ax

    ; --- 3. the staging area, which is FREE now the program has gone --------
    call kd_stageseg            ; ES = the text framebuffer
    mov [kdr_stage], es
    call kd_extents             ; the chain, into HS_EXT
    jc .no

    ; --- 4. ...and from here nothing may fail --------------------------------
    ; **IT SAYS SO FIRST**, which is `kd_leave`'s own manner one route along:
    ; a screen that changes by itself is a crash and a screen that says why is
    ; a machine doing what it was told. It is also the only POSITIVE signal
    ; that this route and not the reboot was taken - absence of the reboot's
    ; own line would be absence of evidence, and `tests/kdreturn.py` asserts
    ; on this one.
    mov si, kdr_s_back
    call kd_puts
    mov es, [kdr_stage]
    push ds
    push cs
    pop ds
    mov si, hbs_stub
    mov di, HS_CODE
    mov cx, hbs_stub_end - hbs_stub
    rep movsb
    pop ds
    mov ax, [kdr_unit]
    mov [es:HS_UNIT], ax
    mov ax, [kdr_spt]
    mov [es:HS_SPT], ax
    mov ax, [kdr_heads]
    mov [es:HS_HEADS], ax
    mov ax, [kdr_nx]
    mov [es:HS_NX], ax
    mov si, [kd_lbp]
    mov ax, [si+KDL_WAKE]       ; where the restored kernel comes back in
    mov [es:HS_WAKE], ax
    mov ax, [si+KDL_WAKE + 2]
    mov [es:HS_WAKE + 2], ax
    mov ax, [si+KDL_KSEG]       ; ...and the DS it comes back with, which the
    mov [es:HS_KSEG], ax        ; stub used to spell as a constant that means
                                ; something else in this host (hbstage.inc)

    ; --- the CLOCK, which has to be FRESH and not the handoff's --------------
    ; SPEC.md 87.6: the image holds the clock as it was when it was written,
    ; and a DOS program may have run for an hour. The ROM has the answer and
    ; `cw_clk_snapshot` is kern_dos's way of asking (kerndos/kdshim.inc) - the
    ; one shim in that file that is not a stub, for this reason one layer up.
    ; **AND IT IS NOT THE SHIM'S LAYOUT.** `hbm_wake` copies these ten bytes
    ; into `clk_sec` and that block is sec/min/hour/day/mon then **clk_rtc and
    ; clk_dirty** then the year (kernel/clock.inc) - two bytes of machine state
    ; that say whether a usable RTC was found and whether it is owed a write.
    ; `kern_dos` cannot know either, so the launch block carries the kernel's
    ; own ten and only the TIME fields are overwritten from the ROM. Staging a
    ; zeroed block instead would tell the resumed machine it has no RTC.
    mov si, [kd_lbp]
    add si, KDL_CLK
    mov di, HS_CLK
    mov cx, 10
.ck:
    mov al, [si]
    mov [es:di], al
    inc si
    inc di
    loop .ck
    call KERNEL_SEG:cw_clk_snapshot     ; FAR: kdshim.inc's `cw_` shims end in
                                        ; `retf` and a near call to one pops a
                                        ; stack word into CS
    mov al, [clk_sn_sec]
    mov [es:HS_CLK + 0], al
    mov al, [clk_sn_min]
    mov [es:HS_CLK + 1], al
    mov al, [clk_sn_hour]
    mov [es:HS_CLK + 2], al
    mov al, [clk_sn_day]
    mov [es:HS_CLK + 3], al
    mov al, [clk_sn_mon]
    mov [es:HS_CLK + 4], al
    mov ax, [clk_sn_year]
    mov [es:HS_CLK + 7], ax

    ; ...and the exit code, which is what the whole return is FOR (96.41).
    ; The BDA copy stays too: it costs nothing and a resume that loses this
    ; word still comes back, just without a number in the window.
    mov al, [kd_code]
    xor ah, ah
    mov [es:HS_DOSCODE], ax
    mov ax, [dos_akb]           ; ...AND THE ARENA IT WAS GIVEN (SPEC.md
    mov [es:HS_DOSAKB], ax      ; 96.41.1). `kd_arena` worked it out off
                                ; `[kd_top]` and the box cannot: over there
                                ; the figure is what OSAPI_MEM_AVAIL_MAX said
                                ; about a HEAP, and this program had the
                                ; machine. Staged in the cell `hbm_res` uses
                                ; for the reboot route, so one reader serves
                                ; both ways home

    ; --- 5. the PIC masks, the ROM's tick, and go ----------------------------
    ; `hbm_handover`'s tail, with the half that is about a running kernel
    ; taken out: there are no drivers to shut down, no lock to take and no
    ; mode to set - `kern_dos` has been in text mode since the ROM left it.
    cli
    in al, 0x21
    mov [es:HS_MASKM], al
    mov byte [es:HS_SLAVE], 0   ; an XT's port 0xA0 is the NMI mask register
    mov al, 0xFF                ; and not a second 8259 (SPEC.md 9.9.2), so
    out 0x21, al                ; the stub must not write it back
    call kd_mou_stop            ; ...and OUR mouse goes quiet before the
                                ; machine stops being ours (96.45.1)
    mov ax, [kdr_stage]         ; a FAR JUMP INTO THE STUB spelled as a
    push ax                     ; return, which is hbm_handover's own idiom.
    mov ax, HS_CODE             ; `push imm` is not an 8086 instruction
    push ax                     ; (CLAUDE.md 1), so both halves go via AX
    retf
.no:
    stc
    ret

; -----------------------------------------------------------------------------
; kd_stageseg - the text framebuffer, as a segment
; out: ES = 0xB000 on a mono adapter, 0xB800 otherwise; AX spent
;
; The BDA's own byte (0040:0049), which is what the ROM set and what the DOS
; program may have changed: mode 7 is the MDA/Hercules text mode and every
; other text mode is at B800. `hbm_stageseg` asks the kernel's video state for
; the same answer, and there is none here.
; -----------------------------------------------------------------------------
kd_stageseg:
    push ds
    mov ax, 0x0040
    mov ds, ax
    mov al, [0x0049]
    pop ds
    mov ax, 0xB800
    cmp al, 7
    jne .out
    mov ax, 0xB000
.out:
    mov es, ax
    ret

; -----------------------------------------------------------------------------
; kd_extents - HIBERNAT.IMG's chain, as absolute runs at HS_EXT
; in:  [kdr_clus] = its first cluster, [kdr_base] the partition base,
;      ES = the staging segment
; out: [kdr_nx] = the count, CF=1 = it does not fit or the chain is broken
; clobbers: AX, BX, CX, DX, SI, DI, flags
;
; `hbm_extents` one host along, and the two are NOT shared: that one reaches
; `dsk_clus2lba_x` and `dsk_next_clus_x` through the module's far shim and
; keeps its state in `.modh` cells, so the seam runs THROUGH the routine
; rather than around it - six of its twenty lines. Where a shared body would
; have to be a macro with a call-shape parameter, this is the same arithmetic
; against the same two primitives, reached near.
;
; THE IMAGE IS AS LONG AS THE FILE SAYS, which is the one quantity both sides
; agree on: the kernel wrote `[mem_top]` paragraphs of it and this host knows
; only `[kd_top]`, a cap the box banked out of the BDA, and a machine where
; those differ restores SHORT and silently.
; -----------------------------------------------------------------------------
kd_extents:
    mov word [kdr_nx], 0
    mov di, HS_EXT              ; STRAIGHT THERE, and `[es:di-2]` below still
                                ; reaches the run in hand because DI is past
                                ; the last store by then
    mov si, [kdr_clus]
    mov cx, [kdr_secs]          ; CX = sectors still to place, out of the
                                ; DIRECTORY ENTRY (see kd_resume): the file's
                                ; own length and not this host's idea of
                                ; where memory ends
.clus:
    mov ax, si
    call dsk_clus2lba_x         ; AX = its first LBA, volume-relative
    jc .bad
    xor dx, dx
    add ax, [kdr_base]
    adc dx, [kdr_base + 2]      ; DX:AX = absolute
    mov bl, [dsk_spc]
    xor bh, bh
    cmp bx, cx
    jbe .whole
    mov bx, cx                  ; ...capped at what the image still needs
.whole:
    cmp word [kdr_nx], 0
    je .new
    cmp ax, [kdr_nextlo]        ; does this cluster follow the run in hand?
    jne .new
    cmp dx, [kdr_nexthi]
    jne .new
    add [es:di-2], bx           ; contiguous: the run grows
    jmp short .grown
.new:
    cmp word [kdr_nx], HS_XMAX
    jae .bad
    mov [es:di], ax
    mov [es:di+2], dx
    mov [es:di+4], bx
    add di, HS_XSTRIDE
    inc word [kdr_nx]
    mov [kdr_nextlo], ax
    mov [kdr_nexthi], dx
.grown:
    add [kdr_nextlo], bx
    adc word [kdr_nexthi], 0
    sub cx, bx
    jz .done
    mov ax, si
    call dsk_next_clus_x
    jc .bad
    mov si, ax
    jmp .clus                   ; near: the walk outgrew a short displacement
.done:
    clc
    ret
.bad:
    stc
    ret

kdr_s_img:  db 'HIBERNAT.IMG', 0
kdr_s_back: db 13, 10, 13, 10, 'os8088: putting the session back...', 13, 10, 0

section .bss
kdr_vol:    resb 1
kdr_clus:   resw 1
kdr_unit:   resw 1
kdr_spt:    resw 1
kdr_heads:  resw 1
kdr_base:   resd 1
kdr_secs:   resw 1
kdr_nx:     resw 1
kdr_nextlo: resw 1
kdr_nexthi: resw 1
kdr_stage:  resw 1
section .text

%include "hbstub.inc"           ; ...and SPEC.md 87.5's stub itself, in THIS
                                ; host's `.text` - the section is the
                                ; includer's choice (that file's header)
