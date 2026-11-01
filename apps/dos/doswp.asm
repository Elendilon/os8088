; =============================================================================
; os8088 - apps/dos/doswp.asm
;
; **DOS's WINDOWED LAYER AS A PART** (SPEC.md 96.54.9): dosw.inc and doswm.inc
; (SPEC.md 96.54 to 96.54.7) assembled on their own, at org 0, as part
; DOS_PART_DVW of DOS.O88 - an OP_ASSET | OP_COMP | OP_LAZY | OP_SELF row the
; re-homed host reads with op_self into a claim of its own at the first Run in
; Window (apps/dos/doswr.inc's dvw_pfetch).
;
; THE SECOND PASS OF A TWO-PASS BUILD. The host is assembled first with its
; map (-DDOSP_MAP), tools/os88dvwexp.py checks these sources against it and
; writes $(BUILD)/doswexp.inc - the host's symbols, by name - and this file
; assembles against that. So the part names `con_write` or `dos_win` exactly
; as the inline layer did, and the macros of apps/dos/doswabi.inc decide, by
; who OWNS each name, how the reference crosses: CS is this claim, DS is the
; host's wherever host data is touched or the kernel is called.
;
; THE LAYOUT, every offset an assembly constant of this file:
;
;   0              the entry table, DVWE_N four-byte entries (doswabi.inc)
;   ...            dosw.inc, doswm.inc and the part-only glue below
;   dvwx_tab       a far pointer per host routine the part calls, and the
;                  two thunks of HICALL and DVW_POSTRET
;   dvw_pcells     apps/dos/doswcell.inc: the layer's own cells, as zeros
; =============================================================================

%define DVW
%define DVW_PART
    cpu 8086
    bits 16
    org 0

%include "os88api.inc"              ; the OSAPI_* cells and the OS88_* macros
%include "doswexp.inc"              ; ...THEN the host's names, which shadow
                                    ; any constant os88api.inc also defines
                                    ; with the same value (os88dvwexp.py)
%include "doswabi.inc"

; --- the entry table: entry n at n * 4 ---------------------------------------
dvwp_entries:
dvwe_start:   call dvw_start        ; DVWE_START
              retf
dvwe_wake:    call dvw_wake         ; DVWE_WAKE
              retf
dvwe_key:     call dvw_key          ; DVWE_KEY
              retf
dvwe_onclose: call dvw_onclose      ; DVWE_ONCLOSE
              retf
dvwe_mouse:   call dwm_mouse        ; DVWE_MOUSE
              retf
dvwe_txt:     call dwm_txt          ; DVWE_TXT
              retf
dvwe_fsmain:  call dvw_fsmain       ; DVWE_FSMAIN
              retf
dvwe_runprog: call dvw_runprog      ; DVWE_RUNPROG
              retf
dvwe_post:    jmp strict near dvw_post  ; DVWE_POST - a JUMP: the door stub's
              db 0xCC               ; return is the word dvw_post reads
dvwe_fin:     jmp strict near dvw_fin   ; DVWE_FIN - a JUMP: the core's return
              db 0xCC               ; is the word dvw_fin drops
%if ($ - $$) != DVWE_N * 4 || (dvwe_runprog - $$) != DVWE_RUNPROG * 4 || (dvwe_fin - $$) != DVWE_FIN * 4
 %error "the entry table is DVWE_N four-byte entries, in DVWE_* order (doswabi.inc)"
%endif

%include "dosw.inc"
%include "doswm.inc"

; -----------------------------------------------------------------------------
; dvw_hbind - the HOST's segment into dvw_hseg and every far pointer OUT
; (DVW_HBIND, at the head of dvw_start). in: DS = the host; every register kept
;
; dvw_start is the first entry of every run, and the host can move only
; between runs (its region is pinned by the worker's frame for a run), so
; once here is enough: no other entry can be reached with stale pointers.
; -----------------------------------------------------------------------------
dvw_hbind:
    push di
    mov [cs:dvw_hseg], ds
    mov di, PADDR(dvwx_tab) + 2
.b:
    mov [cs:di], ds
    add di, 4
    cmp di, PADDR(dvwx_end)
    jb .b
    pop di
    ret

; dvw_rpopf - dvw_post's way back (DVW_POSTRET): the ten registers, then the
; host's `ret`, which pops the core's own near return with CS the host's
dvw_rpopf:
    pop ax
    pop bx
    pop cx
    pop dx
    pop si
    pop di
    pop bp
    pop es
    pop ds
    popf
    jmp far [cs:dvwx_ret]

; -----------------------------------------------------------------------------
; dvw_key - DVWE_KEY: dos_key's arm for a running program (SPEC.md 96.54,
; 96.54.1), moved here because both cells it decides on are the part's
; in:  AX = the key, BX = the window, DS = the host
; -----------------------------------------------------------------------------
dvw_key:
    cmp ax, KSC_ENTER << 8          ; ALT+ENTER is the full screen, for a
    jne .key                        ; running program and a frozen one alike
    mov byte [cs:dvw_fsreq], 1
    call OSAPI_WM_WAKE              ; (entered from the wake: the bracket
    ret                             ; wants the lock free, and dos_key holds it)
.key:
    cmp byte [cs:dvw_frz], 0        ; a frozen program takes no keys
    jne .r
    call dvw_kput
.r:
    ret

; --- OUT: a far pointer per host routine, the segments dvw_hbind's ----------
    align 2, db 0
%assign DVWH_N 0                    ; numbered as doswr.inc numbers the
%macro DVW_HX 1                     ; thunks, off the same list
dvwx_%1:
    dw dvwh_ %+ DVWH_N, 0           ; DVWCHK-OK: the host's thunk, by design
%assign DVWH_N DVWH_N + 1
%endmacro
dvwx_tab:
    DVW_HOSTCALLS
dvwx_icall:
    dw dvwh_icall, 0                ; DVWCHK-OK: HICALL's thunk
dvwx_ret:
    dw dvwh_ret, 0                  ; DVWCHK-OK: DVW_POSTRET's `ret`
dvwx_end:

%include "doswcell.inc"
