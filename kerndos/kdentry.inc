; =============================================================================
; kerndos/kdentry.inc - kern_dos's REAL entry (docs/plans/KERN-DOS-PLAN.md §7 step 8)
;
; The machine has already been torn down and restarted into this image: the
; kernel is gone, the drivers are gone, the ROM's vectors are back, and what
; is left is a BIOS, a disk and a block of parameters the stub copied in.
; This hooks INT 21h and its neighbours, builds the PSP and the environment,
; loads the program and runs it - and when the program exits there is nothing
; to go back to, so it restarts the machine (§9).
;
; **IT IS `dos_run` PLUS `dos_fsx_main` WITH THE OS TAKEN OUT**, and that is
; the shape to keep: every step below is one of theirs in their order, minus
; the ones that name a kernel this machine has not got. What is left is the
; steps that are pure 8086 work on the IVT, the BDA and the DOS core's own
; bss - which W4 measured as 21 procs reaching no `OSAPI_*` and no indirect
; call at all (SPEC.md 96.38), and is why they port by being included.
;
; The W4 gate (`kdosgate.inc`) stages a block and comes in here too, so the
; ABI has a test that needs no kernel, no handoff and no hard disk.
; =============================================================================
section .text

; -----------------------------------------------------------------------------
; kd_entry - in: nothing; the stub has put a launch block at [kd_lbp]
; -----------------------------------------------------------------------------
kd_entry:
    cli
    mov ax, KD_SEG              ; CS is already ours; the rest follows
    mov ds, ax
    mov es, ax
    mov ax, LOW_SEG             ; SS is NOT DS (SPEC.md 2.1): the disk layer's
    mov ss, ax                  ; buffers are reached through it
    mov sp, KD_STACK
    sti
    cld

    ; --- THE BSS, WHICH ARRIVES AS WHATEVER WAS ALREADY THERE ---------------
    ; `.bss` and `.lowbss` are `nobits`: they cost the part no disk, and
    ; NOTHING THAT PUTS THIS IMAGE IN MEMORY WRITES THEM. On the W4 gate that
    ; was invisible - a machine four seconds out of POST has zeros above the
    ; image - and on the handoff it is the outgoing KERNEL's data, at its own
    ; offsets, which is a volume table, a FAT window and a handle table that
    ; all look plausible and are another operating system's. It surfaced as
    ; `the disk could not be mounted` about a floppy whose BPB int 13h had
    ; just read perfectly.
    ;
    ; Here rather than in each loader, for `mod_need`'s MOD_BSS reason one
    ; layer out: one place cannot be forgotten by the next thing that learns
    ; to start this image.
    ;
    ; **THE LAUNCH BLOCK IS THE ONE THING ALREADY WRITTEN**, so it is skipped
    ; at RUN time rather than at assembly time - the handoff's lands in
    ; `kd_lblock` and the gate's in `kd_glb`, and `[kd_lbp]` is the only thing
    ; that knows which. It is in `.text` and survives this.
    mov si, [kd_lbp]
    push ds
    pop es
    xor al, al
    mov di, kd_b_start
    mov cx, si
    sub cx, di
    rep stosb                   ; ...everything under the block
    mov di, si
    add di, KDL_SIZE
    mov cx, kd_e_bss
    sub cx, di
    rep stosb                   ; ...and everything over it
    push ss
    pop es                      ; ...and the disk layer's buffers, which are
    xor di, di                  ; SS's and whose section is `vstart=0`, so the
    mov cx, kd_e_lowbss         ; end label IS the length
    rep stosb
    push ds
    pop es

%ifndef KD_GATE
    ; --- the glass, because the STAGING AREA IS THE TEXT FRAMEBUFFER ---------
    ; SPEC.md 87.5 stages the handoff in the one RAM a conventional-memory
    ; image does not cover, which is the text page - so what is on the screen
    ; when this starts is the stub, its extent list and the launch block, drawn
    ; as characters. Setting the mode the machine is ALREADY in is the BIOS's
    ; own clear and costs six bytes; a hard-coded 3 would be wrong on an MDA.
    ; It is `%ifndef KD_GATE` because the gate arrives through a loader that
    ; left the screen clean and has already printed on it (kdosgate.inc).
    mov ah, 0x0F
    int 0x10                    ; AL = the mode vid_reboot left
    xor ah, ah
    int 0x10                    ; ...set again, which is how a BIOS clears
%endif

    ; --- the block, checked before a byte of it is believed ------------------
    mov si, [kd_lbp]
    cmp word [si+KDL_MAGIC], KDL_SIG & 0xFFFF
    jne .nolb
    cmp word [si+KDL_MAGIC+2], KDL_SIG >> 16
    jne .nolb
    cmp word [si+KDL_VER], KDL_VER_NOW
    jne .nolb
    cmp word [si+KDL_TLEN], KDL_MINE  ; **AND THE LENGTH, WHICH IS THE HALF
    jne .nolb                         ; THAT ROTS** - the magic survives a
                                      ; field being added on one side only and
                                      ; this does not, because both sides sum
                                      ; their own copy of the same list
                                      ; (kdlaunch.inc)

    ; --- the fields, back into the DOS core's own bss -------------------------
    call kd_scatter

    ; --- and the DISKETTE PARAMETER TABLE, which is not one of them ----------
    ; SPEC.md 18.92: `int 1Eh` is a POINTER to eleven bytes the BIOS re-reads
    ; on every floppy operation, and os8088 owns it - so the vector we inherit
    ; names KERNEL_SEG:dsk_dpt, which is THIS segment at an offset that is not
    ; our table. The handoff carries the bytes (kerndos/kdlaunch.inc) and this
    ; puts them in ours and names it; a block with none - the W4 gate, which
    ; arrives through a loader that never touched the vector - leaves the ROM's
    ; alone, and a table whose first byte is zero is not one.
    cmp byte [si+KDL_DPT], 0
    je .nodpt
    push si
    push di
    add si, KDL_DPT
    mov di, dsk_dpt             ; ES is ours
    mov cx, DPT_LEN
    rep movsb
    xor ax, ax
    mov es, ax
    pushf
    cli                         ; the vector is two words and an interrupt
    mov word [es:0x0078], dsk_dpt   ; between them would hand the BIOS half an
    mov word [es:0x007A], KD_SEG    ; address (dsk_dpt_init_x's reason)
    popf
    push ds
    pop es
    pop di
    pop si
.nodpt:

    ; --- the arena ------------------------------------------------------------
    ; A real DOS puts the program straight above itself and gives it
    ; everything to the top of memory. So does this: no heap, no claim, no
    ; region - [kd_floor] IS the first paragraph the program owns.
    mov ax, LOW_SEG + (KD_LOW_KB * 64)
    mov [kd_floor], ax
    mov [dos_arena], ax
    mov bx, [si+KDL_CAP]        ; KB, the BDA's own figure banked by the box
    cmp bx, KD_CAP_MAX
    jbe .cap
    mov bx, KD_CAP_MAX          ; a cap over the 640KB an 8086 can address at
.cap:                           ; all is a block nobody staged
    mov cl, 6
    shl bx, cl                  ; KB -> paragraphs; KD_CAP_MAX keeps it in 16
    mov [kd_top], bx
    sub bx, ax
    jbe .noroom
    mov [dos_apara], bx
    mov ax, bx
    shr ax, cl
    mov [dos_akb], ax

    ; --- the volume the program came off --------------------------------------
    mov dl, [dos_vol]           ; SPEC.md 96.6's map is the identity, so the
    call disk_mount_x           ; DOS drive IS the volume index
    jc .nomount

    ; --- the load geometry, which is dos_run's and is NOT the arena's ---------
    ; [dos_ldpsp] is the PSP and not the arena base: dos_build_psp lays the
    ; environment's MCB at paragraph 0 and the PSP at 10, so a base handed to
    ; dos_load loads the image on top of the environment (SPEC.md 96.38.2).
    mov ax, [dos_arena]
    add ax, DOS_PSPP
    mov [dos_ldpsp], ax
    mov word [dos_ldname], dos_name
    call dos_fh_setup           ; ...and the file window comes OFF the top
    jc .nofh                    ; before the program is told how much memory
    mov ax, [dos_apara]         ; it has (SPEC.md 96.11)
    sub ax, DOS_PSPP
    mov [dos_ldpara], ax

    ; --- where the launch stood -----------------------------------------------
    mov ax, [dos_dir]           ; NOT a root: a program launched from a
    or ax, ax                   ; subdirectory can walk out of it, like it
    jz .stood                   ; would under DOS (SPEC.md 96.6.1)
    mov dx, ax                  ; DX = the cluster, BL = its volume
    mov bl, [dos_vol]
    call dos_be_goto
.stood:

    ; --- load it ---------------------------------------------------------------
    call dos_load               ; ...through dos_be_read, which is kdback's
    jc .noload
    call dos_is_exe             ; the answer is in the FILE and not in the
    jnc .isCOM                  ; name (SPEC.md 96.8)
    call dos_exe_setup
    jc .noload
    mov byte [dos_isexe], 1
    jmp short .ready
.isCOM:
    mov byte [dos_isexe], 0
.ready:

    ; --- the machine, banked, and the program built on top of it ---------------
    ; [dos_inbr] = 1 FOR EVER here and it is a finding rather than a setting
    ; (SPEC.md 96.38): the program owns the machine from the moment it starts,
    ; so dos_tty's console arm is unreachable and there is no window to come
    ; back to.
    mov byte [dos_inbr], 1
    mov word [dos_vw], 640      ; INT 33h's scale (SPEC.md 96.10). The package
    mov word [dos_vh], 200      ; asks OSAPI_VIDEO; there is no kernel here to
                                ; ask, and a text-mode machine's is the 80x25
                                ; cell grid's
    call dos_save_machine       ; **BEFORE dos_hook_vectors**: the whole IVT is
                                ; what dos_restore_machine puts back, so a hook
                                ; taken before the bank is never taken off
    call dos_build_psp
    call dos_hook_vectors

    mov ax, [dos_arena]         ; the DTA starts at PSP:0080 (SPEC.md 96.3)
    add ax, DOS_PSPP
    mov [dos_dtaseg], ax
    mov word [dos_dta], 0x80
    mov ax, [dsk_cwd]           ; ...and we stand where the mount and the goto
    mov [dos_curdir], ax        ; left us, read off the machine rather than
    mov al, [dos_vol]           ; asserted
    call dos_drv_bank
    call dos_date_init          ; the RTC once, or the fallback

    ; --- into the program, and back out of it ----------------------------------
    ; **THE BANKED SP MUST SIT ON A RETURN ADDRESS** (SPEC.md 96.38.2):
    ; dos_terminate restores SS:SP from these two words and JUMPS to
    ; dos_prog_done, which ends in the `ret` that ends dos_fsx_main at its own
    ; entry depth. Banking the plain SP of an entry nothing called points it at
    ; the top of an empty stack.
    mov ax, .back
    push ax
    mov ax, ss
    mov [dos_sv_ss], ax
    mov [dos_sv_sp], sp
    call dos_prog_enter
.back:
    mov al, [dos_exit]
    mov [kd_code], al
    jmp kd_leave

.nolb:
    mov si, kd_s_nolb
    jmp short .say
.noroom:
    mov si, kd_s_noroom
    jmp short .say
.nomount:
    mov si, kd_s_nomount
    jmp short .say
.nofh:
    mov si, kd_s_nofh
    jmp short .say
.noload:
    mov si, kd_s_noload
.say:
    call kd_puts
    mov byte [kd_code], 0xFF
    jmp kd_leave

; -----------------------------------------------------------------------------
; kd_leave - the program is over (docs/plans/KERN-DOS-PLAN.md §9)
;
; **THERE IS NOTHING TO GO BACK TO ON THIS ARM**, which is the first
; deliberately destructive thing this OS does and reads like one: the user is
; to be asked in its own window, at the moment of launch, with Cancel as the
; default - docs/plans/KERN-DOS-PLAN.md §9, which is W7 and is not built. So
; the machine restarts - and it says so first, because a
; screen that goes black on its own is a crash and a screen that says why is a
; machine doing what it was told.
;
; W6's arm hangs off the same byte: with KDLF_REBOOT clear there is a
; hibernation image to put back, and this is where the return stub goes.
; -----------------------------------------------------------------------------
kd_leave:
    ; **INTERRUPTS BACK ON, BECAUSE THE PROGRAM'S EXIT CAME THROUGH A GATE.**
    ; AH=4Ch arrives on an `int 21h`, which clears IF, and `dos_terminate`
    ; restores SS:SP and JUMPS rather than `iret`-ing - so the flags the gate
    ; pushed are never popped and we are back here with IF = 0. In the box
    ; that is invisible; here the very next thing is the ROM, and a BIOS disk
    ; read waits on IRQ6. `int 19h` ran, its read timed out with AH=01, and it
    ; RETURNED - so the machine printed "Press any key to restart" and then sat
    ; in `.hold`'s `hlt` for ever, which reads exactly like a refusal to
    ; restart rather than like a masked interrupt.
    sti
    mov si, [kd_lbp]
    test word [si+KDL_FLAGS], KDLF_REBOOT
    jz .hold                    ; W6: the return. Until it exists, a block
                                ; that does not ask for the reboot has nowhere
                                ; to go and says so rather than restarting a
                                ; machine the user expected back
    mov si, kd_s_over
    call kd_puts
    mov al, [kd_code]
    xor ah, ah
    call kd_dec
    mov si, kd_s_boot
    call kd_puts
    xor ah, ah                  ; the ROM's own wait: a program that printed
    int 0x16                    ; its last line deserves to have it read

    ; --- the park, AND the DL the ROM boots from (SPEC.md 18.100, 96.40.2) ---
    ; **`int 19h` READS THE BOOT DRIVE OUT OF DL AS IT FINDS IT.** The
    ; bootstrap takes no documented input, so a routine that just calls it
    ; hands the ROM whatever the DOS program left - here 0xA1, which is
    ; `int 13h` answering AH=01 "bad command" twice and the bootstrap RETURNING
    ; rather than booting. It reads as a machine that refuses to restart, and
    ; it sat in `.hold`'s `hlt` for ever with its own message underneath.
    ; kernel/disk.inc's `dsk_fdd_park_x` leaves DL = 0 by falling out of its
    ; own loop, which is why the desktop's Restart has never shown this.
    ;
    ; The resets are that routine's other half and are owed anyway: the FDC has
    ; just run a whole DOS program's worth of I/O, and SPEC.md 18.97's probe on
    ; the next boot decides on drive B's own TRACK 0 line.
    mov dl, 2
.park:
    dec dl                      ; ...1, then 0 - and it LEAVES DL = 0
    xor ah, ah                  ; AH=00 RESET DISK SYSTEM = recalibrate to
    int 0x13                    ; track 0. No result is read: the int 19h
    or dl, dl                   ; below resets the FDC whatever this leaves
    jnz .park                   ; behind (SPEC.md 18.100)
    int 0x19
.hold:
    mov si, kd_s_held
    call kd_puts
.h:
    hlt
    jmp .h

; -----------------------------------------------------------------------------
; kd_scatter - the block's fields into the DOS core's bss
; in:  SI = the block; DS = ES = KD_SEG
; out: everything clobbered but SI
;
; The table is kdlaunch.inc's and the box emits the identical one, so this is
; the same walk in the other direction. One segment throughout: the stub put
; the block in OUR image (§7 step 7), which is what makes it a plain `movsb`
; and not a segment argument.
; -----------------------------------------------------------------------------
kd_scatter:
    push si
    mov bx, kd_lbtab
    lea si, [si+KDL_BODY]
.row:
    mov cx, [bx+2]
    jcxz .out
    mov di, [bx]
    add di, os88_image_end
    rep movsb
    add bx, 4
    jmp short .row
.out:
    pop si
    ret

; --- the table this walk reads, and our own idea of the payload's length ----
%macro KDL_F 2
    dw (%1 - os88_image_end), %2
%endmacro
kd_lbtab:
    KDL_FIELDS
    dw 0, 0
%unmacro KDL_F 2

%assign KDL_ACC 0
%macro KDL_F 2
    %assign KDL_ACC KDL_ACC + %2
%endmacro
    KDL_FIELDS
%unmacro KDL_F 2
KDL_MINE equ KDL_ACC
%if KDL_ACC + KDL_BODY > KDL_SIZE
  %error "kern_dos: the launch block's payload outgrew KDL_SIZE"
%endif

; --- the ROM's teletype, which is the only screen this machine has ----------
kd_puts:
    push ax
    push bx
    push si
.c:
    mov al, [si]
    or al, al
    jz .out
    inc si
    mov ah, 0x0E
    mov bx, 0x0007
    int 0x10
    jmp short .c
.out:
    pop si
    pop bx
    pop ax
    ret

kd_dec:                         ; AX, in decimal, smallest thing that works
    push ax
    push bx
    push cx
    push dx
    mov cx, 0
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
    mov ah, 0x0E
    mov bx, 7
    int 0x10
    loop .e
    pop dx
    pop cx
    pop bx
    pop ax
    ret

kd_s_nolb:    db 13, 10, 'kern_dos: no launch block', 13, 10, 0
kd_s_noroom:  db 13, 10, 'kern_dos: no room for a program', 13, 10, 0
kd_s_nomount: db 13, 10, 'kern_dos: the disk could not be mounted', 13, 10, 0
kd_s_nofh:    db 13, 10, 'kern_dos: no file window', 13, 10, 0
kd_s_noload:  db 13, 10, 'kern_dos: the program could not be loaded', 13, 10, 0
kd_s_over:    db 13, 10, 13, 10, 'os8088: the program has exited, code ', 0
kd_s_boot:    db '.', 13, 10, 'Press any key to restart.', 13, 10, 0
kd_s_held:    db 13, 10, 'kern_dos: nothing to return to.', 13, 10, 0

section .bss
kd_code:    resb 1              ; the program's exit code, for
            resb 1              ; docs/plans/KERN-DOS-PLAN.md §12 question 3

; **THE BLOCK LIVES IN `.bss`, WHICH IS NOBITS**, and the image's fixed header
; is a POINTER to it rather than the block itself (kdlayout.inc's KD_H_LBP).
; The stub has no symbol table, so something at a known offset has to say
; where to write - and a word says it for four bytes where the block itself
; would cost 512 of the part on every disk that ships one.
kd_lblock:
    resb KDL_SIZE

section .text

; --- what the kernel's own kernel.asm would have given the disk layer -------
; `dsk_vol_fixed` is a two-instruction thunk in kernel.asm:7030 and it is
; COPIED here rather than shortened. The obvious shortening - `jmp
; dkf_dsk_vol_fixed`, on the reasoning that `.cold` is not another segment
; here so the call need not be far - is WRONG, because near or far is a
; property of the BODY and not of the distance: `dkf_dsk_vol_fixed` ends in
; `retf` whatever segment it is in. kdback.inc's header has the rest of it.
section .text
dsk_vol_fixed:
    call COLD_SEG:dkf_dsk_vol_fixed
    ret

section .bss
kd_glb:
    resb KDL_SIZE

; --- and the DOS core's own bss ---------------------------------------------
; **IT GOES IN `.bss` AND NOT AT THE END OF AN IMAGE.** In the package,
; `os88_image_end` is where the loader zeroes from (SPEC.md 21 step 5) and the
; DBSS table is offsets from it. Here there is no loader and no image end:
; the same table lands in the root's own `.bss`, addressed through DS exactly
; as before, and the name is all that has to be kept.
section .bss
os88_image_end:
    resb DOS_BSS_SIZE + CON_BSS

section .text
