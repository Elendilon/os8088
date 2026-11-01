; =============================================================================
; os8088 - apps/dos/doswr.inc
;
; **THE WINDOWED LAYER'S RESIDENT HALF, IN A SPLIT HOST** (SPEC.md 96.54.9).
; The layer is PART DOS_PART_DVW of DOS.O88 (apps/dos/doswp.asm); what stays
; in the instance's region is what the host and the kernel ENTER it by, what
; it calls the host by, and the fetch, pin and move of the claim it lives in.
; dosw.inc's own resident pieces - the worker's loop and the door table - are
; assembled beside this, under the same DVW_SPLIT.
; =============================================================================

%ifdef DVW_SPLIT

; --- INTO the part: six-byte stubs, their segment word PATCHED --------------
; `call far PART:entry / ret` for a CALL entry, `jmp far PART:entry` (and a
; byte nobody reaches) for a JUMP one. The segment is written by dvw_patch at
; the fetch - never while a run is in, which is the only time a stub can be
; executing, so none is ever mid-flight (apps/tracker/trkplay.inc patches its
; immediates on the same argument).
%macro DVWT 2
hent_%1:
    db 0x9A                         ; call far
    dw %2 * 4, 0
    ret
%endmacro
%macro DVWJ 2
hent_%1:
    db 0xEA                         ; jmp far
    dw %2 * 4, 0
    db 0xCC                         ; (unreached: the stride is six)
%endmacro
dvw_stubs:
    DVWT dvw_start,   DVWE_START
    DVWT dvw_wake,    DVWE_WAKE
    DVWT dvw_key,     DVWE_KEY
    DVWT dvw_onclosef, DVWE_ONCLOSE ; (...and hent_dvw_onclose)
    DVWT dwm_mouse,   DVWE_MOUSE
    DVWT dwm_txt,     DVWE_TXT
    DVWT dvw_fsmain,  DVWE_FSMAIN
    DVWT dvw_runprog, DVWE_RUNPROG
    DVWJ dvw_post,    DVWE_POST
    DVWJ dvw_fin,     DVWE_FIN
dvw_stubs_end:
DVWT_N equ (dvw_stubs_end - dvw_stubs) / 6
%if DVWT_N != DVWE_N
 %error "one host stub per part entry (doswabi.inc's DVWE_*)"
%endif

; hent_dvw_onclose - OSAPI_WM_ONCLOSE's callback. With no program running the
; part may not even be fetched, and the close is simply allowed (CF = 0 off
; the compare)
hent_dvw_onclose:
    cmp byte [dvw_run], 0
    jne hent_dvw_onclosef
    ret

; --- OUT of the part: a thunk per host routine (DVW_HOSTCALLS) --------------
; NUMBERED, not named: a core routine's name is an %xdefine of its slot in
; this host (apps/dos/doscall.inc), so `dvwh_%1` would paste the slot's
; ARITHMETIC into a label. The part numbers its far pointers in the same
; order off the same list, which is what pairs them.
%assign DVWH_N 0
%macro DVW_HX 1
dvwh_ %+ DVWH_N:
    call %1
    retf
%assign DVWH_N DVWH_N + 1
%endmacro
    DVW_HOSTCALLS
dvwh_icall:                         ; HICALL: dvw_serve's posted door, its
    call word [cs:dvw_rtgt]         ; registers all the program's by now
    retf
dvwh_ret:                           ; DVW_POSTRET: dvw_post back to the core,
    ret                             ; which near-called a stub of OURS

; -----------------------------------------------------------------------------
; dvw_pfetch - dos_run's: the part for a run in the window (SPEC.md 96.54.9)
; in:  [dvw_want]; UI task, lock FREE
; out: CF=1 a run in the window whose part could not be had; every register
;      preserved
;
; Idempotent - dos_run comes back here on a compaction wake, and a window
; that ran in the window before keeps its part between runs.
; -----------------------------------------------------------------------------
dvw_pfetch:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    cmp byte [dvw_want], 0
    je .out                         ; (CF = 0)
    cmp word [dvw_pseg], 0
    jne .out                        ; (CF = 0: had already)
    mov si, dos_dvwrow
    xor ah, ah                      ; no floor: the image is the claim
    call dos_pself                  ; DX = the claim, CX = the part's length
    jc .out
    mov ax, cx                      ; ...and only the image's own KB of it:
    add ax, 1023                    ; op_self claimed for its read's slack
    mov al, ah                      ; too, and a shrink is always in place
    xor ah, ah                      ; (OSAPI_MEM_REGROW), DX unchanged
    shr al, 1
    shr al, 1
    call OSAPI_MEM_REGROW
    mov [dvw_pseg], dx
    call dvw_patch                  ; (born PINNED, and held so for the
    clc                             ; window's life)
.out:
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; dvw_patch - the part's segment into every stub; every register preserved
dvw_patch:
    push ax
    push cx
    push di
    mov ax, [dvw_pseg]
    mov di, dvw_stubs + 3
    mov cx, DVWT_N
.p:
    mov [di], ax
    add di, 6
    loop .p
    pop di
    pop cx
    pop ax
    ret

%endif                              ; DVW_SPLIT
