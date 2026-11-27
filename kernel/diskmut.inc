; =============================================================================
; Directory mutations in DISKOPS.DRV (SPEC.md 18.5.3): the recursive folder
; removal on every kernel; New Folder, Rename and the empty folder only on
; kern_small (DSKW_DIRMOD), whose locked heap rung cannot take them resident.
; DS is the kernel, CS this image. Shared FAT/commit/rollback helpers remain
; cold and are reached through wm_cbd, except the two BP-taking private gates.
; The resident dispatcher loads before mutation and releases only its own hold.
;
; WHERE THE KERNEL ALREADY HAS IT, THE IMAGE CALLS IT (driver size pass 2).
; Every kernel but kern_small keeps the empty-folder removal RESIDENT
; (dskw_rmbody and dskw_rmbody_n83, diskw.inc), so there the tree reaches
; those two bodies through wm_cbd instead of carrying a copy of them - the
; gate, the find, the emptiness scan and the commit, the same decisions in the
; same order - and kern_small, which has no resident copy, keeps this file's.
; The answers the kernel spells as `mov ax, FERR_* / stc / ret` are spelled
; here too (dmo_e*), where a far hop to the kernel's own three instructions
; was nine bytes and two segment changes.
; =============================================================================
section .modl

%macro DMO_CALL 1
    mov bp, %1
    call COLD_SEG:wm_cbd
%endmacro
%macro DMO_TAIL 1
    DMO_CALL %1
    ret
%endmacro
%macro DMO_RAWCLU 0             ; diskw.inc's RAW_CLU_LD ax, from this image:
    mov ax, [dskw_raw+DSK_R_CLUS]
  %ifdef OS88_FAT32             ; [dsk_ch] = FstClusHI (SPEC.md 19.12.6)
    DMO_CALL dskw_rawhi
  %endif
%endmacro

; The verbs are private constants: on kern_small all four are clo_vtab's
; words (diskops.inc), and elsewhere clo_disp_x sends the tree here itself.

%ifdef DSKW_DIRMOD
; Gate failures discard exactly one NEAR image return address. Never call
; the resident dskw_gate through wm_cbd: its stack escape belongs to .cold.
; (kern_small has neither a redirected volume nor a held stream, so the two
; arms the resident gate carries for them are not here.)
dmo_gate:
    cmp byte [dsk_mntok], 1
    jne dmo_mounted.no
dmo_gate83:
    DMO_CALL dskw_name83n
    jnc dmo_mounted.ret
    mov ax, FERR_NAME
    jmp short dmo_mounted.fail
dmo_mounted:
    cmp byte [dsk_mntok], 1
    je .ret
.no:
    mov ax, FERR_NODISK
.fail:
    stc
    inc sp
    inc sp
.ret:
    ret

; Validate the destination first, refuse protected sources, and change only
; the eleven name bytes before using the shared one-sector commit.
dmo_nbody:
    call dmo_mounted
    mov bx, si                  ; the old name, then (xchg) the NEW one, held
    mov si, di                  ; in BX to the patch: nothing between spends it
    DMO_CALL dskw_name83n
    xchg si, bx
    jc dmo_ename
    DMO_CALL dskw_find
    jnc dmo_eexist
    cmp ax, FERR_NOENT
    jne dmo_estc
    call dmo_gate83
    DMO_CALL dskw_find
    jc dmo_eret
    test byte [dskw_raw+DSK_R_ATTR], DSKW_NPROT
    jnz dmo_eprot

    mov si, bx                  ; the new name parsed a second time, into the
    mov di, dskw_raw            ; staged entry: no dskw_n83b (kernel size
    DMO_CALL dskw_name83        ; pass 21, -11 resident .bss)
    and word [dskw_oldclus], 0
    DMO_TAIL dskw_rmbody_n83.entrel

%endif ; DSKW_DIRMOD

; The named folder in the current directory, which must be a plain one with a
; real cluster: CF = 0 with AX(:[dsk_ch]) = it, or CF = 1 with AX = FERR_*
dmo_fdir:
    DMO_CALL dskw_find
    jc dmo_eret
    mov al, [dskw_raw+DSK_R_ATTR]
    test al, DSKW_NPROT
    jnz dmo_eprot
    test al, DSKW_DIR
    jz dmo_eprot
    DMO_RAWCLU
    DMO_CALL dskw_clok
    jnc dmo_eret                ; ...or a cluster outside the volume, which a
                                ; subdirectory never has: dmo_eio, next
; THE IMAGE'S OWN ANSWERS: AX = the FERR_*, CF = 1, what the kernel's
; dskw_rdata.corrupt, dskw_wbody.prot and dskw_mkbody.exists answer, without
; a hop to them (driver size pass 2)
dmo_eio:
    mov ax, FERR_IO
    jmp short dmo_estc
%ifdef DSKW_DIRMOD
dmo_eexist:
    mov ax, FERR_EXIST
    jmp short dmo_estc
%else
dmo_enodisk:
    mov ax, FERR_NODISK
    jmp short dmo_estc
%endif
dmo_ename:
    mov ax, FERR_NAME
    jmp short dmo_estc
dmo_eprot:
    mov ax, FERR_PROT
dmo_estc:
    stc
dmo_eret:
    ret

%ifdef DSKW_DIRMOD
; Remove an empty folder only after the same species/emptiness checks.
; The resident commit tail is shared with ordinary Delete and truncate.
dmo_rmbody:
    call dmo_gate

dmo_rmbody_n83:
    call dmo_fdir
    jc dmo_eret
    CLU_ST dskw_oldclus

    ; THE EMPTINESS SCAN of the folder dmo_fdir left in AX(:[dsk_ch]), which
    ; the store above keeps: the same scanner defines both occupancy and what
    ; the tree can name. Written in, its one caller's (driver size pass 2):
    ; its bank of five held nothing - they are the verb's, which dskw_wrap7
    ; restores - and its reload of the cluster was AX already
    push ss
    pop es
    call dmo_scan1
    jnc dmo_eprot               ; a live entry: not empty
    jz .empty                   ; the end (dmo_scan1's ZF): empty
    DMO_TAIL dskw_ioerr         ; ...or the walk's read failed
.empty:
    DMO_TAIL dskw_rmbody_n83.delent

%else ; DSKW_DIRMOD
; Everywhere else the empty-folder removal is RESIDENT, and the tree reaches
; the kernel's own two bodies (diskw.inc): dskw_rmbody with its gate, for a
; redirected volume whose driver has no tree verb, and dskw_rmbody_n83 for a
; folder the walk has emptied. dskw_rmbody calls dskw_gate NEAR, so the gate's
; escape lands in wm_cbd's retf exactly as dskw_rmbody's own `ret` would.
%ifdef OS88_REDIR
dmo_rmbody:
    mov bp, dskw_rmbody
    jmp short dmo_rmbx
%endif
dmo_rmbody_n83:
    mov bp, dskw_rmbody_n83
dmo_rmbx:
    call COLD_SEG:wm_cbd
    ret
%endif ; DSKW_DIRMOD

; Iterative depth-first delete, bounded by DSKW_RT_MAX. Parent links on the
; disk carry the walk, so nesting never grows the task stack. Return home
; on every failure and commit each removal before releasing its chain.
; Nothing is held in a register across the walk's helpers - every cell it
; carries is the kernel's dskw_rt_* - so none of them banks one (driver size
; pass 2 took the banks that kept registers nobody read).
dmo_rtbody:
%ifdef DSKW_DIRMOD
    call dmo_mounted
%else
  %ifdef DSKW_WSEQ
    DMO_CALL dws_gate           ; dskw_mounted's two tests, written here: the
  %endif                        ; walk is their one caller in this image
    cmp byte [dsk_mntok], 1     ; (driver size pass 2)
    jne dmo_enodisk
  %ifdef OS88_REDIR
    cmp byte [dsk_vkind], DVK_FILE
    jne .fat

    mov bp, FSV_RMTREE
    call COLD_SEG:dskw_dir_fsop_f

    jnc dmo_eret
    or ax, ax
    jz dmo_rmbody               ; (one jcc: kernel size pass 21, -2)
    jmp short dmo_estc
  %endif
%endif
.fat:
%ifdef OS88_FAT32
    mov ax, [dsk_cwd]           ; the folder the walk comes home to, all 32
    mov [dskw_rt_home], ax      ; bits - [dsk_ch] is the find's to load, and
    mov ax, [dsk_cwd+2]         ; no step before it reads it
    mov [dskw_rt_home+2], ax
%else
    CLU_LD dsk_cwd
    CLU_ST dskw_rt_home
%endif
    mov di, dskw_rt_name
    DMO_CALL dskw_name83
    jc dmo_ename

    call dmo_rtn83
    call dmo_fdir
    jc dmo_eret

    CLU_ST dskw_rt_top
    call dmo_chdir_dl
    jc dmo_eio                  ; (.ioerr's own jump, short from here)

    mov word [dskw_rt_guard], DSKW_RT_MAX
.loop:
    dec word [dskw_rt_guard]
    jz .corrupt
    call dmo_rt_scan
    jc .empty
    cmp byte [dskw_rt_attr], 0x0F
    je .lfn
    test byte [dskw_rt_attr], DSKW_DIR
    jnz .down
    DMO_CALL dskw_dbody_n83
    jc .home
    jmp short .loop
.lfn:
    and word [dskw_oldclus], 0
%ifdef OS88_FAT32
    and word [dskw_oldclus+2], 0
%endif
    DMO_CALL dskw_rmbody_n83.delent
    jc .home

    jmp short .loop
.down:
    CLU_LD dskw_rt_clus
    DMO_CALL dskw_clok
    jc .corrupt_home
    call dmo_chdir_dl
    jc .iohome
    jmp short .loop

.empty:
    cmp byte [dskw_rt_ioerr], 0
    jne .iohome
%ifdef OS88_FAT32
    mov ax, [dsk_cwd]           ; all 32 bits on kern_mega, through DX, which
    mov dx, [dsk_cwd+2]         ; holds nothing here - and [dsk_ch] is not
    cmp ax, [dskw_rt_top]       ; loaded: dsk_dotdot_x loads AX:[dsk_ch]
    jne .notop                  ; itself, and .finish's go-home does
    cmp dx, [dskw_rt_top+2]
    je .finish
.notop:
    mov [dskw_rt_clus], ax
    mov [dskw_rt_clus+2], dx
%else
    CLU_LD dsk_cwd
    cmp ax, [dskw_rt_top]
    je .finish
    CLU_ST dskw_rt_clus
%endif
    DMO_CALL dsk_dotdot_x
    jc .corrupt_home
    call dmo_chdir_dl
    jc .iohome
    call dmo_rt_byclus
    jc .corrupt_home
    call dmo_rmbody_n83
    jc .home
    jmp .loop

.corrupt_home:
.iohome:
    call dmo_rt_go_home
.corrupt:
.ioerr:
    jmp dmo_eio
.home:
    push ax
    call dmo_rt_go_home
    pop ax
    stc
    ret

.finish:
    call dmo_rt_go_home
    jc .ioerr
    call dmo_rtn83
    jmp dmo_rmbody_n83

dmo_rt_go_home:
    CLU_LD dskw_rt_home

dmo_chdir_dl:                   ; (DX was banked here for nobody: driver
    mov dl, [disk_drive]        ; size pass 2)
    DMO_TAIL dsk_chdir_x

; One live entry, including orphan LFN slots; retain I/O failure separately
; from a successfully empty directory.
dmo_rt_scan:
    mov byte [dskw_rt_ioerr], 0
    push ss
    pop es
    CLU_LD dsk_cwd
    call dmo_scan1
    jnc .found
    jz .none
    mov byte [dskw_rt_ioerr], 1
.none:
    stc
    ret
.found:
    mov [dskw_cursec], dx

    DMO_CALL dskw_hit

    call dmo_rawn83
    mov al, [dskw_raw+DSK_R_ATTR]
    mov [dskw_rt_attr], al
    DMO_RAWCLU
    CLU_ST dskw_rt_clus
    clc
.ret:                           ; (and dmo_rt_byclus's refusal, CF = 1)
    ret

; Recover the child name by first cluster after returning to its parent.
dmo_rt_byclus:
    CLU_LD dsk_cwd
    mov dx, [dskw_rt_clus]
%ifdef OS88_FAT32
    push word [dskw_rt_clus+2]  ; DX:[dsk_vh] = the cluster sought
    pop word [dsk_vh]
%endif
    DMO_CALL dsk_byclus_x
    jc dmo_rt_scan.ret
    mov di, dskw_raw
    mov cx, 32
    DMO_CALL dsk_copy_in_x
    call dmo_rawn83
    clc
    ret

dmo_scan1:
    DMO_CALL dsk_dirw_start_x
.sector:
    DMO_CALL dsk_dirw_get_x
    jc .out
    xchg dx, ax
    mov si, dsk_secbuf
    mov cx, 16
.entry:
    mov al, [es:si]
    test al, al
    jz .none
    cmp al, 0xE5
    je .next
    cmp al, '.'
    jne .live
    mov al, [es:si+1]
    cmp al, '.'
    je .next
    cmp al, ' '
    jne .live
.next:
    add si, 32
    loop .entry
    jmp short .sector
.live:
    clc
    ret
.none:
    stc
.out:
    ret

%ifdef DSKW_DIRMOD
; Allocate and initialize the new cluster, flush FAT, then commit the entry.
; mkclus stays resident because ordinary file writes grow directories too.
dmo_mkbody:
    call dmo_gate
    DMO_CALL dskw_find
    jnc dmo_eexist
    cmp ax, FERR_NOENT
    jne .fail

    DMO_CALL dskw_dirgrow
    jc .fail

    mov bp, dskw_dotents
    call COLD_SEG:dskw_dir_mkclus_f
    jc .fail

    DMO_CALL dskw_flush_x
    jc .rollax

    xor ax, ax
    mov [dskw_len], ax
    mov [dskw_lenhi], ax
    inc ax
    mov [dskw_new], al
    mov [dskw_isdir], al
    DMO_CALL dskw_commit
    mov byte [dskw_isdir], 0    ; (kern_small's commit leaves the flag, and
    jc .rollax                  ; nothing else sets it there: .rollax finds it
    DMO_TAIL dskw_relold.flush  ; clear on both ways in)

.rollax:                        ; CF = 1 on both ways in, and dskw_refat keeps
    DMO_CALL dskw_refat         ; every register and flag, AX the answer among
.fail:                          ; them (driver size pass 2: the bank of AX,
    ret                         ; the `stc` and a second clear of a clear flag)

%endif ; DSKW_DIRMOD

; Name buffers remain kernel data: the FAT parsers consume DS:DI. The walk's
; copy (dmo_rawn83, an entry's) falls through; the folder's own jumps
dmo_rtn83:
    mov si, dskw_rt_name
    jmp short dmo_n83go
dmo_rawn83:
    mov si, dskw_raw
dmo_n83go:
    mov di, dskw_n83
    DMO_TAIL dskw_copy11

%unmacro DMO_CALL 1
%unmacro DMO_TAIL 1
%unmacro DMO_RAWCLU 0
section .text
