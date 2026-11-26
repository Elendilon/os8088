; =============================================================================
; os8088 - apps/inputchk/auto.inc - the AUTOMATIC RUN (SPEC.md 136.12)
;
; Started from a link whose parameter is AUTO (SPEC.md 26.10.7) - the input
; debug disk's \AUTOSTRT\INPUTCHK.LNK, SPEC.md 127.5 - Input Check runs a fixed
; script with nobody needing to drive it, and writes what it saw to the disk it
; was started from. Started any other way none of this runs and the program
; writes nothing by itself.
;
;   1  AU_T1 ticks (~20 s): sample, and ask for keys on the screen. Whether a
;      keystroke reaches the BIOS on THIS boot is the first question.
;   2  write the report, INPUTnnA.TXT, the first free nn: a machine that hangs
;      in step 3 still leaves this one on the disk, and it is the boot as the
;      machine left it, before anything here touched the controller.
;   3  the controller check (kbd.inc) and, where the kernel's own probe left
;      the port alone, Probe PS/2 (probe.inc).
;   4  AU_T2 ticks (~10 s) more for keys: did the keyboard survive the check?
;   5  write INPUTnnB.TXT, complete. Done; the window stays up. The B file is
;      a file of its own and not the A file rewritten: the 2026-11-17 field
;      report's A state (port 64h at 7D, an AUX byte stuck) was the evidence,
;      and the overwrite threw it away (SPEC.md 9.9.1.1).
;
; Commands typed during the run are counted and ignored (mc_onkey), so a user
; asked to press keys cannot close the window by pressing Q or Esc.
; Label prefix au_.
; =============================================================================

AU_T1       equ 364             ; ticks: ~20 s of keys before the first write
AU_T2       equ 182             ; ~10 s after the controller check
AU_NMAX     equ 99              ; INPUT01 .. INPUT99

; -----------------------------------------------------------------------------
; au_init - from the entry proc, where OSAPI_ARG_TEXT is still valid. Keeps all
; -----------------------------------------------------------------------------
au_init:
    push ax
    push dx
    push si
    push ds
    call OSAPI_ARG_TEXT             ; CF = 1: none, every ordinary launch
    jc .out
    mov ds, dx                      ; DX:SI = the link's parameter
    mov ax, [si]
    and ax, 0xDFDF                  ; either case
    cmp ax, 'AU'
    jne .no
    mov ax, [si+2]
    and ax, 0xDFDF
    cmp ax, 'TO'
    jne .no
    cmp byte [si+4], 0
.no:
    pop ds
    push ds
    jne .out
    mov byte [au_ph], 1
    call OSAPI_GET_TICKS
    mov [au_t0], ax
.out:
    pop ds
    pop si
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; au_tick - one step of the script, from mc_tick before its rebuild
; -----------------------------------------------------------------------------
au_tick:
    mov al, [au_ph]
    cmp al, 1
    je .p1
    cmp al, 2
    je .p2
    cmp al, 3
    je .p3
    ret
.p1:
    call au_left
    jnc .r
    call au_pick                    ; the first free INPUTnnA.TXT
    inc byte [au_ph]                ; 2 BEFORE the write, so the report shows
    mov si, au_name                 ; this stage. The check runs on the NEXT
    call au_write
    mov [au_e1], ax                 ; tick, so the screen says "saved" first
.r:
    ret
.p2:
    call kb_check
    call mc_kes
    call p2_canprobe
    jc .np
    call mc_kes
    call p2x_run
    mov byte [au_prb], 1
.np:
    call OSAPI_GET_TICKS
    mov [au_t0], ax
    inc byte [au_ph]                ; 3
    ret
.p3:
    call au_left
    jnc .r
    inc byte [au_ph]                ; 4 BEFORE the write: the file is the
    mov si, au_nameb                ; finished report, and a file of its own -
    call au_write                   ; the A file keeps the boot UNTOUCHED
    mov [au_e2], ax
    mov si, au_t_done
    or ax, ax
    jz .t
    mov si, mc_t_nosave
.t:
    jmp mc_toast

; au_left - CF = 1: the phase's time is up; else AX = whole seconds left
au_left:
    call OSAPI_GET_TICKS
    sub ax, [au_t0]
    mov dx, AU_T1
    cmp byte [au_ph], 1
    je .t
    mov dx, AU_T2
.t:
    cmp ax, dx
    jae .up
    sub dx, ax
    xchg ax, dx                     ; AX = ticks left
    mov dx, 10                      ; ticks to seconds: x10 / 182
    mul dx
    mov cx, 182
    div cx
    inc ax
    clc
    ret
.up:
    stc
    ret

; au_pick - [au_name] = the first INPUTnnA.TXT that is not on the disk, and
;           [au_nameb] its INPUTnnB.TXT
au_pick:
    mov byte [au_n], 1
.l:
    call au_mkname
    push es
    push ds
    pop es
    mov si, au_name
    mov bx, mc_tmp
    xor cx, cx                      ; capacity 0: the directory entry alone
    xor dx, dx                      ; answers (FERR_BIG before any data I/O)
    call OSAPI_FILE_READ
    pop es
    jc .e
    jmp short .taken                ; an empty file of that name
.e:
    cmp ax, FERR_BIG
    jne .free                       ; NOENT, or a disk error: the write says
.taken:
    inc byte [au_n]
    cmp byte [au_n], AU_NMAX
    jbe .l
    mov byte [au_n], AU_NMAX        ; all taken: the last is rewritten
    call au_mkname
.free:
    ret

; au_mkname - "INPUTnnA.TXT" and "INPUTnnB.TXT" from [au_n]
au_mkname:
    push ax
    push si
    push di
    mov si, au_stem
    mov di, au_name
.c:
    lodsb
    mov [di], al
    inc di
    or al, al
    jnz .c
    mov al, [au_n]
    aam
    add ax, 0x3030
    mov [au_name+5], ah
    mov [au_name+6], al
    mov si, au_name
    mov di, au_nameb
.d:
    lodsb
    mov [di], al
    inc di
    or al, al
    jnz .d
    mov byte [au_nameb+7], 'B'
    pop di
    pop si
    pop ax
    ret

; au_write - the report as it is now into SI's name. out AX = 0 or a FERR_*
au_write:
    call mc_writerep
    jnc .ok
    or ax, ax
    jnz .r
    mov ax, 0xFF                    ; no memory for the text
.r:
    ret
.ok:
    xor ax, ax
    ret

; =============================================================================
; au_rows - the section, FIRST in the list while the run is on
; =============================================================================
au_rows:
    cmp byte [au_ph], 0
    jne .on
    ret
.on:
    mov si, au_s_head
    mov al, LP_INFO
    call mc_head
    mov al, [au_ph]
    cmp al, 1
    jne .after1
    mov si, au_l_keys
    call mc_line
    mov si, au_l_keys2
    call mc_line
    mov si, au_rv_save
    call mc_row
    call au_left
    jc .z
    call mc_dec
.z:
    mov si, au_s_sec
    jmp mc_put
.after1:
    mov si, au_rv_r1
    mov ax, [au_e1]
    mov di, au_name
    call au_res
    cmp byte [au_ph], 3
    jb .x
    mov si, au_rv_chk
    call mc_row
    mov si, au_s_ran
    call mc_put
    cmp byte [au_prb], 0
    je .np
    mov si, au_s_prb
    call mc_put
.np:
    cmp byte [au_ph], 3
    jne .done
    mov si, au_l_again
    call mc_line
    mov si, au_rv_save
    call mc_row
    call au_left
    jc .z
    call mc_dec
    jmp short .z
.done:
    mov si, au_rv_r2
    mov ax, [au_e2]
    mov di, au_nameb
    call au_res
    mov si, au_l_fin
    call mc_line
    mov si, au_l_fin2
    jmp mc_line
.x:
    ret

; au_res - SI = a label, DI = the name, AX = 0 or an error: the name, or
;          the name and "FAILED, nn"
au_res:
    push ax
    call mc_row
    mov si, di
    call mc_put
    pop ax
    or ax, ax
    jz .ok
    push ax
    mov si, au_s_fail
    call mc_put
    pop ax
    call mc_dec
    mov al, LP_BAD
    jmp mc_lamp
.ok:
    ret

; --- data ----------------------------------------------------------------------
au_stem:    db 'INPUT00A.TXT', 0
au_s_head:  db 'Automatic report (started by the debug disk)', 0
au_s_sec:   db ' s', 0
au_l_keys:  db 'PRESS SOME KEYS NOW: letters, Num Lock, Caps Lock.', 0
au_l_keys2: db 'Q and Esc do nothing while this runs.', 0
au_rv_save: db 'Saving in', 0
au_rv_r1:   db 'First report', 0
au_rv_chk:  db 'Controller check', 0
au_s_ran:   db 'done', 0
au_s_prb:   db ', and Probe PS/2', 0
au_l_again: db 'PRESS SOME KEYS AGAIN: did the keyboard survive it?', 0
au_rv_r2:   db 'Final report', 0
au_l_fin:   db 'Done. Send the INPUT*.TXT files: A before, B after.', 0
au_l_fin2:  db 'Restart to run again: each boot writes a new file.', 0
au_s_fail:  db ' - SAVE FAILED, error ', 0
    TOASTSTR au_t_done, 'Input report saved'

; --- loader-zeroed bss --------------------------------------------------------
    OS88_ABYTE au_ph                ; 0 off; 1 keys, 2 check, 3 keys, 4 done
    OS88_ABYTE au_n                 ; the report's number
    OS88_ABYTE au_prb               ; Probe PS/2 ran too
    OS88_AWORD au_t0                ; the phase's start
    OS88_AWORD au_e1                ; the two writes' answers
    OS88_AWORD au_e2
    OS88_ABUF  au_name, 14
    OS88_ABUF  au_nameb, 14
