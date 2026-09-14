; =============================================================================
; kerndos/kdosgate.inc - wave 4's entry: mount a disk, load a .COM, run it
;
; **kern_dos's REAL entry is docs/plans/KERN-DOS-PLAN.md §7's**, which is W5's:
; a handoff staged in the text framebuffer, a machine already torn down, and a
; block of parameters handed over rather than probed. This is the same steps
; with the handoff left out and a disk to boot from instead, so that W4 can
; answer its own question - does the DOS core run over the new back end - a
; wave before the way IN exists.
;
; It is behind KD_GATE and no shipping path defines it.
; =============================================================================
%ifdef KD_GATE
section .text

kd_dos_entry:
    cli
    mov ax, KD_SEG
    mov ds, ax
    mov es, ax
    mov ax, LOW_SEG             ; SS is NOT DS (SPEC.md 2.1): the disk layer's
    mov ss, ax                  ; buffers are reached through it
    mov sp, KD_STACK
    sti
    cld

    mov ax, LOW_SEG + (KD_LOW_KB * 64)
    mov [kd_floor], ax
    mov ax, KD_ARENA_TOP
    mov [kd_top], ax

    mov si, kd_s_boot
    call kd_puts
    mov dl, 1                   ; B:, kerndos.asm's reason: A: carries the
    call disk_mount_x           ; loader and the blob raw and has no volume
    jnc .mounted
    mov si, kd_s_nomount
    call kd_puts
    jmp kd_stop
.mounted:

    ; --- the ARENA, which is the whole point of the exercise ----------------
    ; A real DOS puts the program straight above itself and gives it
    ; everything to the top of memory. So does this: no heap, no claim, no
    ; region - [kd_floor] IS the first paragraph the program owns, and
    ; KD_ARENA_TOP the last.
    mov ax, [kd_floor]
    mov [dos_arena], ax
    mov dx, KD_ARENA_TOP
    sub dx, ax
    mov [dos_apara], dx             ; ...in paragraphs, which is the figure the
    mov ax, dx                      ; MCB chain and AH=48h are cut from
    mov cl, 6
    shr ax, cl
    mov [dos_akb], ax
    mov si, kd_s_arena
    call kd_puts
    call kd_dec                     ; ...on the glass, because it is the number
    mov si, kd_s_kb                 ; this whole plan exists to move
    call kd_puts

    ; --- the load geometry, which is dos_run's and is NOT the arena's -------
    ; **[dos_ldpsp] IS THE PSP AND NOT THE ARENA BASE.** dos_build_psp lays
    ; the environment's MCB at paragraph 0, the environment at 1, the
    ; program's MCB at 9 and the PSP at 10, so a gate that hands dos_load the
    ; arena base loads the image on top of the environment and builds the PSP
    ; where the first MCB goes. It assembles, it runs, and the program reads
    ; its own arena out of a word the loader has already overwritten.
    mov ax, [dos_arena]
    add ax, DOS_PSPP
    mov [dos_ldpsp], ax
    mov word [dos_ldname], kd_prog

    call dos_fh_setup               ; ...and the file window comes OFF the top
    jc .nofh                        ; before the program is told how much
                                    ; memory it has (SPEC.md 96.11)
    mov ax, [dos_apara]             ; ...so the block is only known now
    sub ax, DOS_PSPP
    mov [dos_ldpara], ax

    ; --- load it ------------------------------------------------------------
    call dos_load                   ; ...through dos_be_read, which is kdback's
    jc .noload
    call dos_is_exe                 ; the answer is in the FILE and not in the
    jnc .isCOM                      ; name (SPEC.md 96.8)
    call dos_exe_setup
    jc .noload
    mov byte [dos_isexe], 1
    jmp short .ready
.isCOM:
    mov byte [dos_isexe], 0
.ready:

    ; --- the machine, banked, and the program built on top of it ------------
    ; **[dos_inbr] = 1 FOR EVER HERE, and it is a finding rather than a
    ; setting.** In the package that byte says "the fsx bracket is up, so
    ; dos_tty writes through the ROM teletype rather than into the console
    ; library" (SPEC.md 96.33), and dos_run clears it on the way out. kern_dos
    ; has no way out and no window: the program owns the machine from the
    ; moment it starts, so the console arm is not merely unused, it is
    ; UNREACHABLE - which is what makes apps/os88con.inc dead weight in this
    ; root and a lever for KERN-DOS-PLAN §6.1 to count.
    mov byte [dos_inbr], 1
    mov word [dos_vw], 640          ; INT 33h's scale (SPEC.md 96.10). The
    mov word [dos_vh], 200          ; package asks OSAPI_VIDEO; there is no
                                    ; kernel here to ask, and a text-mode
                                    ; machine's is the 80x25 cell grid's
    call dos_save_machine           ; **BEFORE dos_hook_vectors**: the whole
                                    ; IVT is what dos_restore_machine puts
                                    ; back, so a hook taken before the bank is
                                    ; a hook that is never taken off
    call dos_build_psp
    call dos_hook_vectors

    mov ax, [dos_arena]             ; the DTA starts at PSP:0080 (SPEC.md 96.3)
    add ax, DOS_PSPP
    mov [dos_dtaseg], ax
    mov word [dos_dta], 0x80
    mov ax, [dsk_cwd]               ; ...and we start where the MOUNT left us,
    mov [dos_curdir], ax            ; read off the machine rather than asserted
    mov al, [disk_drive]
    mov [dos_vol], al
    call dos_drv_bank
    call dos_date_init              ; the RTC once, or the fallback

    ; --- into the program, and back out of it -------------------------------
    ; **THE BANKED SP MUST SIT ON A RETURN ADDRESS**, which is the half that
    ; is easy to get wrong because banking SP looks like the whole job.
    ; dos_terminate restores SS:SP from these two words and JUMPS to
    ; dos_prog_done - and dos_prog_done ends in the `ret` that ends
    ; dos_fsx_main itself, at that routine's own entry depth. So the word the
    ; bank points AT is where the program's exit lands, and banking the plain
    ; SP of an entry nothing called points it at the top of an empty stack:
    ; the program ran, printed, exited correctly, and the machine then ran off
    ; into its own bss with every check but the last one green.
    mov si, kd_s_run
    call kd_puts
    mov ax, .back                   ; ...so put one there, which is what a
    push ax                         ; `call dos_fsx_main` does for the package
    mov ax, ss
    mov [dos_sv_ss], ax
    mov [dos_sv_sp], sp
    call dos_prog_enter
.back:

    mov si, kd_s_exit
    call kd_puts
    mov al, [dos_exit]
    xor ah, ah
    call kd_dec
    jmp short kd_stop
.nofh:
    mov si, kd_s_nofh
    call kd_puts
    jmp short kd_stop
.noload:
    mov si, kd_s_noload
    call kd_puts
kd_stop:
    mov si, kd_s_end
    call kd_puts
.h:
    hlt
    jmp .h

; --- the ROM's teletype, as kerndos.asm's gate uses it ----------------------
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

kd_s_boot:    db 13, 10, 'kern_dos: mount B: ', 0
kd_s_nomount: db 'MOUNT FAILED', 13, 10, 0
kd_s_arena:   db 'ok, arena ', 0
kd_s_kb:      db ' KB', 13, 10, 0
kd_s_noload:  db 'LOAD FAILED', 13, 10, 0
kd_s_nofh:    db 'FILE WINDOW FAILED', 13, 10, 0
kd_s_run:     db 'running', 13, 10, 0
kd_s_exit:    db 13, 10, 'kern_dos: exit code ', 0
kd_s_end:     db 13, 10, 'kern_dos: done', 13, 10, 0
kd_prog:      db 'KDHELLO.COM', 0

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

; --- and the DOS core's own bss ---------------------------------------------
; **IT GOES IN `.bss` AND NOT AT THE END OF AN IMAGE.** In the package,
; `os88_image_end` is where the loader zeroes from (SPEC.md 21 step 5) and the
; DBSS table is offsets from it. Here there is no loader and no image end:
; the same table lands in the root's own `.bss`, addressed through DS exactly
; as before, and the name is all that has to be kept.
section .bss
os88_image_end:
    resb DOS_BSS_SIZE + CON_BSS
%endif                          ; KD_GATE
