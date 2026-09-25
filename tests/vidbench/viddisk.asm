; =============================================================================
; os8088 - tests/vidbench/viddisk.asm
;
; VIDDISK: wave 0 (b) of docs/plans/VIDEO-PLAN.md - what STREAMING a large
; file off the fixed disk costs today, and what the disk itself could give.
;
;   python3 tests/viddisk.py [--machine os8088_5150_herc_hdd_sb_gla]
;
; Two families of rows, both tick-timed (benchlib's method T: a disk call is
; tens of milliseconds and more, so the 838 ns PIT is not the instrument):
;
;   READ_AT 32K @n MB  OSAPI_FILE_READ_AT, 32 KB at a fixed offset into
;                      STREAM.DAT (12.6 MB). The call re-walks the directory
;                      and the cluster chain from the front every time
;                      (SPEC.md 18.4.4), so the per-call time GROWS with the
;                      offset, and the slope is the cost that
;                      OSAPI_FILE_READ_SEQ (VIDEO-PLAN 4.2) removes.
;   int13 track / sect the ROM's own int 13h on unit 80h: one whole track
;                      (the geometry's sectors per track) and one sector,
;                      consecutive tracks. That is the controller's ceiling,
;                      which a streaming read that does no walking can
;                      approach and not pass.
;
; READ-ONLY. It writes nothing to any disk, and the raw reads land in its own
; claim. It is a bench, so it calls int 13h itself; the player never does
; (VIDEO-PLAN 4.2: no sector is ever exposed to a package).
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'VIDDISK', vk_entry

VK_NRES     equ 12
VK_BUFKB    equ 40                  ; 32 KB for READ_AT, a track for int 13h
VK_CHUNK    equ 32768

vk_entry:
    push si
    call bl_blank
    mov si, vk_s_title
    call bl_sline
    call bl_head
    mov si, vk_s_hint
    call bl_sline
    mov si, vk_tpl
    call OSAPI_WM_CREATE
    jc .out
    mov [vk_win], bx
    clc
.out:
    pop si
    ret

vk_paint:
    call bl_paint
    ret

vk_onkey:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov bl, al
    or bl, 0x20
    cmp bl, 'r'
    je .run
    call bl_key
    jc .out
    call bl_paint
    jmp short .out
.run:
    call vk_run
    call bl_paint
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

vk_onclick:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call vk_run
    call bl_paint
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- the bodies ---------------------------------------------------------------

; READ_AT 32 KB at [vk_off] (a dword, a cluster multiple)
vk_b_rat:
    push es
    mov es, [vk_buf]
    xor bx, bx
    mov si, vk_f_stream
    mov cx, VK_CHUNK
    mov ax, [vk_off]
    mov dx, [vk_off + 2]
    call OSAPI_FILE_READ_AT
    jnc .ok
    inc word [vk_err]
.ok:
    mov [vk_got], ax
    pop es
    ret

; int 13h, AL = [vk_nsec] sectors at the next track (head 0..H-1, cyl 1..)
vk_b_i13:
    push es
    mov es, [vk_buf]
    xor bx, bx
    mov al, [vk_nsec]
    mov ah, 2
    mov ch, [vk_cyl]
    mov cl, [vk_cylhi]              ; bits 6-7 = cylinder 8-9, sector 1
    or cl, 1
    mov dh, [vk_head]
    mov dl, 0x80
    int 0x13
    jnc .ok
    inc word [vk_err]
.ok:
    ; the next track: head + 1, and the cylinder after the last head
    mov al, [vk_head]
    inc al
    cmp al, [vk_heads]
    jb .h
    xor al, al
    add byte [vk_cyl], 1
    jnc .h
    add byte [vk_cylhi], 0x40
.h:
    mov [vk_head], al
    pop es
    ret

; vk_bank - BX = the result row
vk_bank:
    push ax
    push bx
    push dx
    push si
    mov si, bx
    shl si, 1
    shl si, 1
    mov ax, [bl_lastus]
    mov dx, [bl_lastus + 2]
    mov [vk_res + si], ax
    mov [vk_res + si + 2], dx
    pop si
    pop dx
    pop bx
    pop ax
    ret

; vk_ratrow - AX = the offset in MB, SI = the label, BX = the result row
vk_ratrow:
    push ax
    push bx                         ; the row: the body zeroes BX (its
    push dx                         ; buffer offset)
    mov dx, 16                      ; MB -> the high word: n * 1,048,576
    mul dx                          ; = n * 16 * 65,536
    mov [vk_off + 2], ax
    mov word [vk_off], 0
    push si                         ; (the body takes SI for the name)
    call vk_b_rat                   ; once to warm whatever warms: the
    pop si                          ; directory, the FAT window
    mov word [bl_body], vk_b_rat
    mov al, 1
    call bl_run
    pop dx
    pop bx
    call vk_bank
    pop ax
    ret

vk_run:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov word [vk_done], 0
    mov word [vk_err], 0
    mov word [bl_nrow], 0
    mov si, vk_s_title
    call bl_sline
    cmp word [vk_buf], 0
    jne .have
    mov ax, VK_BUFKB
    call OSAPI_MEM_CLAIM
    jc .fail
    mov [vk_buf], dx
.have:
    ; --- the fixed disk's geometry, off the ROM
    mov ah, 8
    mov dl, 0x80
    push es
    int 0x13
    pop es
    jc .fail
    mov al, cl
    and al, 0x3F
    mov [vk_spt], al
    inc dh
    mov [vk_heads], dh
    mov si, vk_r_spt
    mov al, [vk_spt]
    xor ah, ah
    xor dx, dx
    mov cx, 9
    call bl_kv
    mov si, vk_r_heads
    mov al, [vk_heads]
    xor ah, ah
    xor dx, dx
    call bl_kv

    ; --- (b) READ_AT at growing offsets ------------------------------------
    mov si, vk_s_hdra
    call bl_sline
    ; STREAM.DAT is the emulator's: a field disk has none unless somebody
    ; put one beside this package, so a miss skips the five rows rather than
    ; timing five refusals as if they were reads
    mov word [vk_off], 0
    mov word [vk_off + 2], 0
    call vk_b_rat
    cmp word [vk_err], 0
    je .stream
    mov word [vk_err], 0
    mov si, vk_s_nostr
    call bl_sline
    jmp .ctl
.stream:
    mov word [bl_n], 6
    mov ax, 0
    mov si, vk_r_r0
    mov bx, 0
    mov word [bl_body], vk_b_rat
    call vk_ratrow
    mov ax, 3
    mov si, vk_r_r3
    mov bx, 1
    mov word [bl_body], vk_b_rat
    call vk_ratrow
    mov ax, 6
    mov si, vk_r_r6
    mov bx, 2
    mov word [bl_body], vk_b_rat
    call vk_ratrow
    mov ax, 9
    mov si, vk_r_r9
    mov bx, 3
    mov word [bl_body], vk_b_rat
    call vk_ratrow
    mov ax, 12
    mov si, vk_r_r12
    mov bx, 4
    mov word [bl_body], vk_b_rat
    call vk_ratrow
    mov si, vk_r_got
    mov ax, [vk_got]
    xor dx, dx
    mov cx, 9
    call bl_kv

    ; --- the controller: whole tracks, then single sectors --------------------
.ctl:
    mov si, vk_s_hdri
    call bl_sline
    mov byte [vk_cyl], 1
    mov byte [vk_cylhi], 0
    mov byte [vk_head], 0
    mov al, [vk_spt]
    mov [vk_nsec], al
    mov word [bl_n], 40
    mov word [bl_body], vk_b_i13
    mov si, vk_r_trk
    mov al, 1
    call bl_run
    mov bx, 5
    call vk_bank
    mov byte [vk_nsec], 1
    mov word [bl_n], 60
    mov word [bl_body], vk_b_i13
    mov si, vk_r_sec
    mov al, 1
    call bl_run
    mov bx, 6
    call vk_bank

    mov si, vk_r_err
    mov ax, [vk_err]
    xor dx, dx
    mov cx, 9
    call bl_kv
    inc word [vk_done]
    jmp short .end
.fail:
    mov si, vk_s_fail
    call bl_sline
    mov word [vk_done], 0xFFFF
.end:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

%define BL_ARENA_BYTES 4000
%include "benchlib.inc"

vk_tpl:
    dw 7, 22, 632, 300
    dw vk_ttl, vk_paint, vk_onkey, vk_onclick

vk_ttl:       db 'Video Disk Bench', 0
vk_f_stream:  db 'STREAM.DAT', 0
vk_s_title:   db 'VIDDISK - streaming off the fixed disk (VIDEO-PLAN W0 b)', 0
vk_s_hint:    db 'Click, or press R, to run. It only reads.', 0
vk_s_hdra:    db '-- READ_AT 32 KB, by offset into a 12.6 MB file --', 0
vk_s_hdri:    db '-- int 13h on unit 80h: a whole track, one sector --', 0
vk_s_nostr:   db 'No STREAM.DAT beside VIDDISK: READ_AT rows skipped', 0
vk_s_fail:    db 'NO CLAIM, OR NO FIXED DISK ANSWERED', 0
vk_r_r0:      db 'READ_AT 32K @0 MB', 0
vk_r_r3:      db 'READ_AT 32K @3 MB', 0
vk_r_r6:      db 'READ_AT 32K @6 MB', 0
vk_r_r9:      db 'READ_AT 32K @9 MB', 0
vk_r_r12:     db 'READ_AT 32K @12 MB', 0
vk_r_trk:     db 'int13 one track', 0
vk_r_sec:     db 'int13 one sector', 0
vk_r_spt:     db 'sectors per track', 0
vk_r_heads:   db 'heads', 0
vk_r_got:     db 'bytes per READ_AT', 0
vk_r_err:     db 'errors (any row)', 0

vk_win:       dw 0
vk_buf:       dw 0
vk_off:       dw 0, 0
vk_got:       dw 0
vk_err:       dw 0
vk_done:      dw 0
vk_spt:       db 0
vk_heads:     db 0
vk_nsec:      db 0
vk_cyl:       db 0
vk_cylhi:     db 0
vk_head:      db 0
vk_res:       times VK_NRES dd 0

VK_BSS_OWN  equ 512
    OS88_BSS VK_BSS_OWN + BL_BSS_SIZE
    align 512
    OS88_IMAGE_END

    BL_BSS os88_image_end + VK_BSS_OWN
