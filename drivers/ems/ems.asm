; =============================================================================
; os8088 - drivers/ems/ems.asm
;
; EMS.DRV: EXPANDED MEMORY on a LIM EMS board's page registers (SPEC.md 107).
;
; A board has four page registers. Writing one maps a 16 KB page of the board
; into one QUARTER of a 64 KB FRAME below 1 MB, and the CPU then reads and
; writes that page as ordinary memory - so nothing here ever moves a byte. This
; driver finds the board, keeps who owns which of its pages and which quarter
; of its frame, and maps on request; the package does the rest in the frame
; itself (docs/plans/VIDEO-XMS-PLAN.md 10 is the design record, and the
; measurement that a disk read lands in the frame at the disk's own rate).
;
; ONE REGISTER FAMILY, the CONSECUTIVE one (SPEC.md 107.2): quarter q's
; register at base + q, a page's value its number. The Lo-tech 2 MB board,
; MartyPC's model of it, 86Box's "Lo-tech EMS Board" and a PicoMEM's EMS. The
; registers are WRITE-ONLY, so nothing here ever reads one: the driver knows
; what it wrote, and a quarter's holder knows what IT wrote (107.4).
;
; Reached by packages through OSAPI_DRV_CALL (BH = DRVC_EMS), and by the
; kernel for one verb, EMSV_GONE, with ES = KERNEL_SEG (xm_release_rec). The
; kernel hands this class the CALLER'S INSTANCE SLOT in BH, where every other
; class gets its own class number - so every verb puts DRVC_EMS back in BH
; before it returns, and the BX a package called with is the BX it gets.
; =============================================================================

%include "os88drv.inc"

    OS88_DRIVER 'EMS', DRVC_EMS, em_entry, em_svc_end - em_svc

EM_MAXPG    equ 256             ; pages a register names (a 4 MB board)
EM_MINPG    equ 4               ; ...and fewer than a frame's four is no board
EM_FREEQ    equ 0xFE            ; [em_qown]: a quarter nobody holds. 0xFF is
                                ; inst_caller's "no instance" (the UI task, a
                                ; driver), which may hold one; 0xFE is no slot
EM_ROMSIG   equ 0xAA55          ; an option ROM's first word, as a word read

%if DRVV_ATTACH != 0 || DRVV_DETACH != 1
    %error "em_entry's verb test assumes ATTACH = 0 and DETACH = 1"
%endif
%if EMSV_IDENT != 0 || EMSV_CAPS != 1 || EMSV_ALLOC != 2 || EMSV_FREE != 3 || EMSV_FRAME != 4 || EMSV_UNFRAME != 5 || EMSV_MAP != 6 || EMSV_BASE != 7 || EMSV_GONE != 8
    %error "em_vtab is indexed by the EMSV_* numbers"
%endif

; =============================================================================
; ENTRY - BX is the kernel's row pointer across attach and must come back
; (drivers/usbmouse/usbmouse.asm's header has why), so nothing below writes it
; =============================================================================
em_entry:
    cmp al, DRVV_DETACH
    jb em_attach
    clc                         ; DETACH: nothing is hooked and nothing is
    ret                         ; claimed - the board keeps its contents, and
                                ; a holder's next call answers "no driver"

; -----------------------------------------------------------------------------
; DRVV_ATTACH - find the board (SPEC.md 107.2). out CF=0 SI = em_svc, or
; CF=1 AL = DRVE_HW
; -----------------------------------------------------------------------------
em_attach:
    push es                     ; the frames are walked in ES
    call em_find
    pop es
    ret

em_find:
    mov al, DRVC_POINT          ; 260h is the CH375's on a Book8088 (SPEC.md
    call OSAPI_DRV_CLASSK       ; 9.12): never written while a USB mouse
    sbb al, al                  ; driver is up. CF=1 is "none loaded", so
    mov [em_ok260], al          ; AL = FFh may write it, 0 may not
    mov si, em_frames
.frame:
    lodsw
    or ax, ax
    jz .none
    mov es, ax
    xor di, di                  ; AN OPTION ROM anywhere in the frame (the
.rom:                           ; BIOS's own scan, a 2 KB step): somebody
    cmp word [es:di], EM_ROMSIG ; else's, and NO PORT is written for it
    je .frame
    add di, 2048
    jnz .rom
    mov bp, em_bases
.base:
    mov dx, [ds:bp]             ; (BP would name SS)
    or dx, dx
    jz .frame
    add bp, 2
    cmp dx, 0x260
    jne .try
    test byte [em_ok260], 1
    jz .base
.try:
    call em_try
    jc .base
    mov [em_port], dx
    mov [em_frame], es
    call em_size                ; CX = the pages
    cmp cx, EM_MINPG
    jb .base
    mov [em_npg], cx
    mov ax, EM_FREEQ * 257
    mov [em_qown], ax
    mov [em_qown + 2], ax
    xor ax, ax                  ; pages 0..3 into the four quarters, so the
.map:                           ; frame reads as the board and nothing else
    out dx, al
    inc ax
    inc dx
    cmp al, 4
    jb .map
    mov si, em_svc
    clc
    ret
.none:
    mov al, DRVE_HW
    stc
    ret

; em_try - DX = a base, ES = a frame: CF=0 a paging board answers there. The
; two bytes it writes are put back when nothing pages, since then they may be
; somebody's RAM; a board's pages are this driver's to write
em_try:
    mov cl, [es:0]
    mov ch, [es:0x4000]
    xor ax, ax                  ; page 0 -> quarter 0, page 1 -> quarter 1
    out dx, al
    inc dx
    inc ax
    out dx, al
    dec dx
    mov byte [es:0], 0x5A
    mov byte [es:0x4000], 0xA5
    cmp byte [es:0], 0x5A       ; two different bytes stuck...
    jne .no
    cmp byte [es:0x4000], 0xA5
    jne .no
    inc dx                      ; ...and page 0 into quarter 1 as well reads
    dec ax                      ; quarter 0's byte there
    out dx, al
    dec dx
    cmp byte [es:0x4000], 0x5A
    jne .no
    mov byte [es:0x4000], 0x3C  ; ...and a write through quarter 1 is seen
    cmp byte [es:0], 0x3C       ; through quarter 0: one page, two windows
    jne .no
    clc
    ret
.no:
    mov [es:0], cl
    mov [es:0x4000], ch
    stc
    ret

; em_size - DX = the board's base, ES = its frame: CX = its pages. A signature
; in each page's first four bytes from the top DOWN, read UP: a smaller board
; aliases, and the last write to a physical page is its own number
em_size:
    mov cx, EM_MAXPG
.wr:
    mov ax, cx
    dec ax
    out dx, al
    mov [es:0], ax
    not ax
    mov [es:2], ax
    loop .wr
.rd:                            ; CX = 0 here
    mov ax, cx
    out dx, al
    cmp [es:0], ax
    jne .out
    not ax
    cmp [es:2], ax
    jne .out
    inc cx
    cmp cx, EM_MAXPG
    jb .rd
.out:
    ret

; =============================================================================
; THE PACKAGE DOOR (DSV_PKGCALL, SPEC.md 107.3)
; in: BL = the verb, BH = the CALLER'S INSTANCE SLOT, ES = its segment (the
; kernel's for EMSV_GONE), AX/CX/DX the verb's. out: CF, and the answers in
; AX, CX, DX, SI; BX comes back with BH = DRVC_EMS, DI is never written.
; Every verb runs with interrupts off: a package's worker and its UI task may
; both be in here, and the tables are a handful of bytes each
; =============================================================================
em_pkg:
    pushf
    cli
    cmp bl, EMSV_GONE
    ja .unk
    push bp
    mov bp, bx
    and bp, 0x00FF
    shl bp, 1
    call [cs:em_vtab + bp]      ; CF = the verb's answer
    pop bp
    jc .bad
    popf                        ; the caller's IF back, and THEN the answer:
    clc                         ; popf would have put the entry's CF back
    jmp short .out
.unk:
    mov ax, EMSE_BAD            ; a verb this driver does not have
.bad:
    popf
    stc
.out:
    mov bh, DRVC_EMS            ; (writes no flag)
    ret

em_vtab:
    dw em_ident, em_caps, em_alloc, em_free, em_fr, em_unfr, em_map, em_base
    dw em_gone

em_ident:
    mov ax, 'EM'
    ret                         ; CF = 0 off em_pkg's `shl`

; CAPS: AX = pages free, CX = the board's, DX = the frame, SI = free quarters
em_caps:
    push di
    xor ax, ax
    mov cx, [em_npg]
    mov di, em_pown
.c:
    cmp byte [di], 0
    jne .n
    inc ax
.n:
    inc di
    loop .c
    mov cx, [em_npg]
    mov dx, [em_frame]
    xor si, si                  ; the free quarters, bit q for quarter q
    mov di, 3
.q:
    shl si, 1
    cmp byte [em_qown + di], EM_FREEQ
    jne .h
    inc si
.h:
    dec di
    jns .q
    pop di
    clc
    ret

; ALLOC: AX = pages -> AX = a handle. FIRST FIT, one contiguous run, so a
; handle is (its first page, its length) and an interrupt can map from that
; alone (SPEC.md 107.4)
em_alloc:
    push cx
    push dx
    push si
    push di
    or ax, ax
    jz .bad
    cmp ax, [em_npg]
    ja .room
    mov si, 1                   ; a free handle: length 0
.h:
    mov di, si
    shl di, 1
    cmp word [em_hlen + di], 0
    je .gotp
    inc si
    cmp si, EMS_NHND
    jbe .h
    mov ax, EMSE_HND
    jmp short .fail
.gotp:                          ; SI = the handle, DI = its word index
    xor cx, cx                  ; CX = the run's start, DX = its length so far
    xor dx, dx
    push si
    mov si, cx
.scan:
    cmp si, [em_npg]
    jae .noroom
    cmp byte [em_pown + si], 0
    je .free
    lea cx, [si + 1]            ; an owned page: the run starts after it
    xor dx, dx
    jmp short .step
.free:
    inc dx
    cmp dx, ax
    je .found
.step:
    inc si
    jmp short .scan
.noroom:
    pop si
.room:
    mov ax, EMSE_ROOM
    jmp short .fail
.found:
    pop si                      ; the handle
    mov [em_hbase + di], cx
    mov [em_hlen + di], ax
    mov [em_hown + si], bh
    xchg ax, cx                 ; CX = the length, AX = the first page
    mov di, ax
    mov ax, si
.mark:
    mov [em_pown + di], al
    inc di
    loop .mark
    clc                         ; AX = the handle
    jmp short .out
.bad:
    mov ax, EMSE_BAD
.fail:
    stc
.out:
    pop di
    pop si
    pop dx
    pop cx
    ret

; em_hnd - AX = a handle: CF=0 it is live and the caller's, SI = it, DI = its
; word index; CF=1 AX = EMSE_BAD
em_hnd:
    cmp ax, 1
    jb .bad
    cmp ax, EMS_NHND
    ja .bad
    mov si, ax
    mov di, ax
    shl di, 1
    cmp word [em_hlen + di], 0
    je .bad
    cmp [em_hown + si], bh
    jne .bad
    clc
    ret
.bad:
    mov ax, EMSE_BAD
    stc
    ret

; FREE: AX = a handle of yours
em_free:
    push cx
    push si
    push di
    call em_hnd
    jc .out
    call em_drop
.out:
    pop di
    pop si
    pop cx
    ret

; em_drop - SI = a live handle, DI = its word index: its pages and itself
; freed. CF = 0. Clobbers CX
em_drop:
    push di
    mov cx, [em_hlen + di]
    mov di, [em_hbase + di]
.c:
    mov byte [em_pown + di], 0
    inc di
    loop .c
    pop di
    mov word [em_hlen + di], 0
    clc
    ret

; FRAME: AL = quarters -> all of them the caller's, or none (EMSE_BUSY).
; out DX = the frame, CX = quarter 0's register, SI = the step, AL = 0
em_fr:
    push di
    and al, 0x0F
    jz .bad
    mov ah, al
    xor di, di
.chk:                           ; every one asked is free or already ours
    shr ah, 1
    jnc .nc
    mov cl, [em_qown + di]
    cmp cl, EM_FREEQ
    je .nc
    cmp cl, bh
    jne .busy
.nc:
    inc di
    cmp di, 4
    jb .chk
    mov ah, al                  ; ...so take them all
    xor di, di
.take:
    shr ah, 1
    jnc .nt
    mov [em_qown + di], bh
.nt:
    inc di
    cmp di, 4
    jb .take
    mov dx, [em_frame]
    mov cx, [em_port]
    mov si, 1                   ; the CONSECUTIVE family: base + q
    xor ax, ax                  ; ...and a page's value is its number
    pop di
    ret                         ; CF = 0 off `cmp di, 4` / `jb` falling out
.busy:
    mov ax, EMSE_BUSY
    jmp short .fail
.bad:
    mov ax, EMSE_BAD
.fail:
    pop di
    stc
    ret

; UNFRAME: AL = quarters: the ones the caller holds are free again
em_unfr:
    push di
    xor di, di
.u:
    shr al, 1
    jnc .n
    cmp [em_qown + di], bh
    jne .n
    mov byte [em_qown + di], EM_FREEQ
.n:
    inc di
    cmp di, 4
    jb .u
    pop di
    clc
    ret

; MAP: AL = a quarter you hold, DX = a handle of yours, CX = a page of it
em_map:
    push dx
    push si
    push di
    cmp al, 3
    ja .bad
    mov ah, 0
    mov si, ax
    cmp [em_qown + si], bh
    jne .bad
    push ax                     ; the quarter
    mov ax, dx
    call em_hnd
    pop dx                      ; DL = the quarter
    jc .out
    cmp cx, [em_hlen + di]
    jae .bad
    mov ax, [em_hbase + di]
    add ax, cx                  ; the board's page
    xor dh, dh
    add dx, [em_port]
    out dx, al
    clc
    jmp short .out
.bad:
    mov ax, EMSE_BAD
    stc
.out:
    pop di
    pop si
    pop dx
    ret

; BASE: AX = a handle of yours -> AX = its first page, CX = its length
em_base:
    push si
    push di
    call em_hnd
    jc .out
    mov ax, [em_hbase + di]
    mov cx, [em_hlen + di]
.out:
    pop di
    pop si
    ret

; GONE: the KERNEL's (ES = KERNEL_SEG), AL = an instance slot that is being
; torn down - every handle and quarter of its freed. EVERY REGISTER BUT AX IS
; KEPT: xm_release_rec banks only AX and BX round it (SPEC.md 107.1)
em_gone:
    push cx
    push dx
    push si
    push di
    mov dx, es
    cmp dx, KERNEL_SEG
    jne .bad                    ; a package cannot send it: its calls arrive
    mov si, 1                   ; with its own segment in ES
.h:
    mov di, si
    shl di, 1
    cmp word [em_hlen + di], 0
    je .nh
    cmp [em_hown + si], al
    jne .nh
    call em_drop
.nh:
    inc si
    cmp si, EMS_NHND
    jbe .h
    xor di, di
.q:
    cmp [em_qown + di], al
    jne .nq
    mov byte [em_qown + di], EM_FREEQ
.nq:
    inc di
    cmp di, 4
    jb .q
    clc
    jmp short .out
.bad:
    mov ax, EMSE_BAD
    stc
.out:
    pop di
    pop si
    pop dx
    pop cx
    ret

; --- the service table: the package door and nothing else --------------------
em_svc:
    times DSV_PKGCALL db 0
    dw em_pkg                   ; DSV_PKGCALL
em_svc_end:

em_frames:  dw 0xE000, 0xD000, 0xC000, 0     ; the frames tried, in order
em_bases:   dw 0x260, 0x264, 0x268, 0x26C ; ...and the bases, in each: the
            dw 0x288, 0               ; Lo-tech's, and a PicoMEM's default

; =============================================================================
; State. Zero-only below OS88_STATE, so it costs the file nothing
; =============================================================================
    OS88_STATE
em_port:    dw 0                ; quarter 0's register
em_frame:   dw 0                ; the frame's segment
em_npg:     dw 0                ; the board's pages
em_ok260:   db 0                ; attach: FFh = 260h may be written
            db 0
em_qown:    times 4 db 0        ; per quarter: its holder's slot, EM_FREEQ
em_hbase:   times EMS_NHND + 1 dw 0     ; per handle (1..8): its first page,
em_hlen:    times EMS_NHND + 1 dw 0     ; ...its length, 0 = a free handle,
em_hown:    times EMS_NHND + 1 db 0     ; ...and its owner's slot
em_pown:    times EM_MAXPG db 0 ; per page: the handle owning it, 0 = free

    OS88_DRV_END
