; =============================================================================
; os8088 - CDROM.DRV (SPEC.md 119)
;
; An ATAPI CD-ROM drive: the disc's ISO 9660 file system as a read-only volume
; on the desktop, and its audio tracks played through the drive's own audio
; output. A DRVC_CD driver - the third file class (SPEC.md 119.1) - so the
; kernel asks it FSV_* questions and never reads a sector of the volume, and a
; package plays the audio through the door in cdpkg.inc.
;
;   cdpkg.inc   the package door's ABI, shared with apps/cdrack
;   atapi.inc   the drive: the packet command, its waits and sense (the
;               probe is the LAST thing in this file: attach hands it back)
;   cddisc.inc  the disc: the TOC, the volume descriptor, the path table
;   cdiso.inc   the volume: records, names, handles and the FSV_* verbs
;   cdaudio.inc the door's verbs: play, pause, stop, where, eject, volume
;
; ATTACH PROBES AND REGISTERS NOTHING; READY registers the one volume, disc or
; none, because the drive is a drive whether or not a disc is in it. Nothing
; reads the disc until the volume is opened.
;
; ES IS KERNEL_SEG ON ENTRY TO EVERY CALLBACK (SPEC.md 20.1) - except the
; package door, where it is the CALLING PACKAGE's (SPEC.md 20.11).
; =============================================================================

%define OS88_DRV_HIGHOK          ; kern_mega may run this image above 1MB
                                ; (KERN-MEGA-MEMORY-PLAN MC8): no arithmetic
                                ; on its own CS or DS, PIO only - nothing of
                                ; ours reaches a BIOS or a DMA engine - and
                                ; cd_bnorm leaves an LDT selector's offset
                                ; unfolded
%include "os88drv.inc"
%include "cdpkg.inc"

    OS88_DRIVER 'CD-ROM', DRVC_CD, cd_entry

; -----------------------------------------------------------------------------
; The service table (SPEC.md 51.2). DSV_BLK is 0: a file class has no sectors
; for the kernel to ask for. DSV_CAPS is FSCAP_ICON and not FSCAP_LOCAL - a
; CD's read is a seek and a turn, so the mount takes the cache-only icon pass
; (62.9.2.1), and our zone wears our own picture (26.4.2).
; -----------------------------------------------------------------------------
cd_svc:
    dw FSCAP_ICON               ; DSV_CAPS: our volume draws its own picture,
                                ; a disc and not a hard disk (cdico.inc,
                                ; SPEC.md 26.4.2) - and NOT FSCAP_LOCAL: a
                                ; CD's read is a seek and a turn
    dw 0                        ; DSV_FM
    dw 0                        ; DSV_STREAM
    dw 0                        ; DSV_TICK
    dw 0                        ; DSV_RELINST
    dw cd_name                  ; DSV_NAME
    dw 0                        ; DSV_TONE
    dw 0                        ; DSV_TIERS
    dw 0                        ; DSV_BLK     - NO SECTORS (SPEC.md 119)
    dw 0                        ; DSV_CPNAME  - no Control Panel page
    dw 0                        ; DSV_CPPAINT
    dw 0                        ; DSV_CPCLICK
    dw 0                        ; DSV_CPCLOSE
    dw cd_fsv                   ; DSV_FS      - the verbs
    dw 0                        ; DSV_CPKEY
    dw 0                        ; DSV_CPUP
    dw 0                        ; DSV_CPDRAG
    dw cd_pkg                   ; DSV_PKGCALL - the audio door (SPEC.md 119.4)
    times DSV_SIZE - ($ - cd_svc) db 0
%if $ - cd_svc != DSV_SIZE
  %error "cdrom: the service table is not DSV_SIZE bytes"
%endif

; --- the FSV_* table DSV_FS points at (SPEC.md 62.9.1, 119.3.4) --------------
cd_fsv:
    dw cd_list                  ; FSV_LIST
    dw cd_chdir                 ; FSV_CHDIR
    dw cd_stat                  ; FSV_STAT
    dw cd_read                  ; FSV_READ
    dw cd_wprot                 ; FSV_WRITE   - a CD is read-only...
    dw cd_wprot                 ; FSV_APPEND
    dw cd_readat                ; FSV_READAT
    dw cd_wprot                 ; FSV_DELETE
    dw cd_wprot                 ; FSV_RENAME
    dw cd_wprot                 ; FSV_MKDIR
    dw cd_wprot                 ; FSV_RMDIR   ...and says so in FAT's words
    dw cd_dfree                 ; FSV_DFREE
    dw cd_enum                  ; FSV_ENUM
    dw 0                        ; FSV_COPY    - the kernel's fallback
    dw 0                        ; FSV_RMTREE  - ...and here, never reached
cd_fsv_end:
%if cd_fsv_end - cd_fsv != FSV_SIZE
  %error "cdrom: the FSV_* table is not FSV_SIZE bytes - a swallowed row?"
%endif

cd_name:    db 'CD-ROM', 0
cd_label:   db 'CD-ROM', 0      ; DV_LBL is 7 bytes inline (SPEC.md 18.7.3)

; =============================================================================
; ENTRY
; =============================================================================
cd_entry:
    cmp al, DRVV_ATTACH
    je cd_attach
    cmp al, DRVV_DETACH
    je cd_detach
    cmp al, DRVV_READY
    je cd_ready
    stc                         ; TIER, HWINFO and any later verb: REFUSED,
    ret                         ; with nothing to say (SPEC.md 51.2.2)

; -----------------------------------------------------------------------------
; DRVV_ATTACH - find the drive (SPEC.md 119.2)
; out: CF = 0 and SI = the service table; CF = 1 and AL = DRVE_HW
;
; ALL-OR-NOTHING (SPEC.md 51.6 rule 1): the probe selects devices and sends
; IDENTIFY PACKET DEVICE, which change nothing a refusal would have to put
; back; no vector is hooked and no memory claimed.
; -----------------------------------------------------------------------------
cd_attach:
    push bx
    push cx
    push dx
    cmp word [cd_base], 0
    jne .twice                  ; attached already: touch nothing (51.2.2)
    call OSAPI_CPU_INFO         ; AL = the tier (cd_bnorm asks for the flags
                                ; itself: KERN-MEGA-PLAN 14.112)
    cmp al, CPU_286
    jb .no                      ; a 16-bit data port on an 8-bit bus loses
                                ; every high byte (SPEC.md 52.1, 119.2)
    call cd_probe
    jc .no
    mov si, cd_svc
    clc
    jmp short .out
.twice:
    mov al, DRVE_TWICE
    stc
    jmp short .out
.no:
    mov al, DRVE_HW
    stc
.out:
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; DRVV_READY - the volume, registered now that the fence answers (51.2.2)
;
; A refusal to register is quiet: the driver stays loaded with its door open,
; so CDRack still plays a disc on a machine whose volume table is full.
; -----------------------------------------------------------------------------
cd_ready:
    push ax
    push cx
    push dx
    push si
    xor al, al                  ; our own volume handle: there is one drive
    xor cx, cx                  ; no sector count - the kernel reads none
    xor dx, dx                  ; a plain add, not a take (SPEC.md 52.1.1)
    mov si, cd_label
    call OSAPI_VOL_ADD
    jc .out
    mov [cd_vol], al
.out:
    pop si
    pop dx
    pop cx
    pop ax
    clc
    ret

; -----------------------------------------------------------------------------
; DRVV_DETACH - cannot fail (SPEC.md 51.6 rule 1)
;
; The volume goes. A disc that is playing is LEFT playing (SPEC.md 119.4): the
; drive plays on its own, and unticking the driver is not a request for
; silence. Nothing else was taken.
; -----------------------------------------------------------------------------
cd_detach:
    push ax
    mov al, [cd_vol]
    cmp al, 0xFF
    je .out
    call OSAPI_VOL_DEL
    mov byte [cd_vol], 0xFF
.out:
    pop ax
    clc
    ret

%include "atapi.inc"
%include "cddisc.inc"
%include "cdiso.inc"
%include "cdaudio.inc"
%include "cdico.inc"

; =============================================================================
; STATE - the volume index is the one cell whose load-time value is not 0
; =============================================================================
cd_vol:     db 0xFF             ; the volume index we registered, FF = none
cd_stag:    dw 0, 0xFFFF        ; the sector buffer's LBA; FFFFh in the high
                                ; word names no sector (cd_rdsec)

    OS88_STATE                  ; every cell from here is 0 at load
cd_base:    dw 0                ; the drive: its task file...
cd_unit:    db 0                ; ...unit...
cd_pkw:     dw 0                ; ...and packet length in WORDS (6 or 8)
cd_w0:      dw 0                ; IDENTIFY's word 0, banked across the drain
cd_model:   times CD_MODELSZ db 0

; --- the waits (atapi.inc) ---------------------------------------------------
cd_tlast:   dw 0                ; the BIOS tick's low word, last seen
cd_tleft:   dw 0                ; ticks left in the bound
cd_ilo:     dw 0                ; ...and polls left: the net under it
cd_ihi:     db 0
cd_tries:   db 0                ; cd_cmd's "becoming ready" retries
cd_uatry:   db 0                ; ...and its UNIT ATTENTION retry

; --- one command: the packet and its transfer, ADJACENT (cd_sense banks the
; whole run as CD_PKT_W words and puts it back) ---------------------------------
cd_pkt:     times 16 db 0
cd_xseg:    dw 0
cd_xoff:    dw 0
cd_xmax:    dw 0
cd_xout:    db 0, 0
cd_pkt_end:
cd_pkt2:    times 24 db 0       ; cd_sense's bank of the run above
cd_xgot:    dw 0                ; bytes the data phase moved
cd_lkey:    db 0                ; the last refusal's sense key (or CD_TMO)...
cd_lop:     db 0                ; ...and the command it answered
cd_snsbuf:  times 18 db 0       ; REQUEST SENSE's answer
%if cd_pkt_end - cd_pkt != 24
  %error "cdrom: cd_sense banks the packet and the transfer as 12 words"
%endif

; --- the disc (cddisc.inc) ---------------------------------------------------
cd_gen:     db 0                ; the media generation (SPEC.md 119.3.4)
cd_valid:   db 0                ; 1 = the tables below describe the disc
cd_stale:   db 0                ; 1 = handles refuse until the root is mounted
cd_iso:     db 0                ; 1 = the disc carries a readable volume
cd_first:   db 0                ; the TOC's first and last track
cd_last:    db 0
cd_kind:    db 0                ; CDK_*
cd_tsum:    dw 0                ; a sum of the last TOC read, and whether one
cd_tsok:    db 0                ; was: a TOC that differs is a changed disc
cd_vdlba:   dw 0, 0             ; the last data track's start
cd_rlba:    dw 0, 0             ; the root directory's extent...
cd_rlen:    dw 0, 0             ; ...and length in bytes
cd_dbase:   dw 0, 0             ; the lowest directory extent (119.3.3)
cd_ptlba:   dw 0, 0             ; the type-L path table
cd_ptlen:   dw 0, 0
cd_toc:     times CD_TOCSZ db 0 ; READ TOC's answer, raw

; --- the sector buffer, tagged by cd_stag above ------------------------------
cd_sbuf:    times 2048 db 0

; --- the volume (cdiso.inc) --------------------------------------------------
cd_cwd:     dw 0                ; the folder we stand in: its handle...
cd_cwdlba:  dw 0, 0             ; ...extent...
cd_cwdlen:  dw 0, 0             ; ...and length
cd_it_lba:  dw 0, 0             ; the directory walk: this sector...
cd_it_n:    dw 0                ; ...sectors left, this one included...
cd_it_off:  dw 0                ; ...and the next record's offset
cd_r_lba:   dw 0, 0             ; cd_resolve's answer: extent...
cd_r_len:   dw 0, 0             ; ...length...
cd_r_fl:    db 0                ; ...ISO flags...
cd_r_cda:   db 0                ; ...and the audio track, 0 = a real record
cd_hcache:  times CD_HC_N * CD_HC_SZ db 0
cd_hcnext:  db 0                ; the next cache row to overwrite
cd_ent:     times 32 db 0       ; the staged SPEC.md 19.1 entry
cd_nm:      times 16 db 0       ; a mangled name
cd_want:    times 16 db 0       ; FSV_STAT's name, staged and upper-cased
cd_hash:    db 0                ; cd_mangle's scratch
cd_opos:    dw 0
cd_dot:     dw 0
cd_nlen:    dw 0
cd_pos:     dw 0, 0             ; cd_bytes: the offset into the file...
cd_left:    dw 0, 0             ; ...bytes still to move...
cd_bseg:    dw 0                ; ...and where they go
cd_boff:    dw 0
cd_prog:    db 0                ; 1 = report progress (FSV_READ)
cd_cda:     times 44 db 0       ; a TRACKnn.CDA's bytes, composed
cd_tmp:     dw 0, 0             ; a parent walk's scratch
cd_tmp2:    dw 0, 0
cd_ord:     dw 0                ; FSV_ENUM's ordinal

; --- the door (cdaudio.inc) --------------------------------------------------
cd_abuf:    times CD_MPLEN db 0 ; SUB-CHANNEL and MODE SENSE answers
cd_vpage:   dw 0                ; ...and where MODE SENSE's page 0Eh is

%if cd_rlen - cd_rlba != 4 || cd_cwdlen - cd_cwdlba != 4 || cd_r_len - cd_r_lba != 4
  %error "cdrom: cd_resolve and cd_setcwd copy an extent and its length as one run"
%endif

; =============================================================================
; THE PROBE (SPEC.md 119.2) - ATTACH'S AND NOTHING ELSE'S, SO IT IS LAST
;
; After every cell of the image's state: cd_attach writes DRV_H_KEEP =
; cd_keep once its probe has found the drive, and the kernel gives these bytes
; back (SPEC.md 51.1.3) - the 8,2xx-byte image is 17 of the heap's 512-byte
; granules and the part it keeps is 16. Nothing reaches them again: cd_probe
; is called by cd_attach alone, cd_ident by cd_probe alone, cd_bases is read
; by cd_probe alone, and a second DRVV_ATTACH into the same image is turned
; away (DRVE_TWICE) by cd_attach's test of cd_base - a cell BEFORE the offset
; - before it could get here. A refused attach frees the whole image and
; never writes the word (driver size pass 2).
; =============================================================================
cd_keep:
cd_bases:   dw 0x168, 0x1E8, 0x170, 0x1F0   ; BACKWARDS: cd_probe walks it down
CD_NBASE    equ 4                           ; from the end, 1F0h first

; -----------------------------------------------------------------------------
; cd_probe - find the first CD-ROM. out: CF = 0 and [cd_base], [cd_unit],
;            [cd_pkw] and [cd_model] set; CF = 1 = none
;
; The first two channels, then - only if neither held one - the other two:
; 1E8h and 168h are where a sound card's own IDE port sits, and a machine
; that already showed us its CD-ROM has no reason to have them written.
; -----------------------------------------------------------------------------
cd_probe:
    push ax
    push bx
    push cx
    push dx
    push si
    mov si, (CD_NBASE - 1) * 2  ; the table's LAST row is 1F0h
.base:
    mov bx, [cd_bases+si]
    lea dx, [bx+ATA_STAT]
    in al, dx
    cmp al, 0xFF
    je .nextbase                ; a floating bus: nothing written to it
    xor cl, cl
.unit:
    call cd_ident
    jnc .found
    xor cl, 1                   ; unit 0, then 1, then back to 0 and out
    jnz .unit
.nextbase:
    sub si, 2                   ; the borrow past the first row is CF = 1:
    jnc .base                   ; "none", with nothing more to say
    jmp short .out
.found:
    mov [cd_base], bx           ; CF = 0 off the `jnc`
    mov [cd_unit], cl
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; cd_ident - IDENTIFY PACKET DEVICE on one unit (internal)
; in:  BX = base, CL = unit
; out: CF = 0 a CD-ROM: [cd_pkw] and [cd_model] set; CF = 1 not one
; clobbers: AX, DX, ES, flags
;
; An ATA disk aborts A1h; an absent device never raises DRQ inside
; CD_PROBE_T; an ATAPI device that is not a CD-ROM (a tape, a ZIP) answers
; with another type in word 0. All 256 words are drained whatever they say -
; the drive holds DRQ until they are.
; -----------------------------------------------------------------------------
cd_ident:
    push cx
    push di
    mov ax, CD_PROBE_T
    call cd_tmo_set
    call cd_select
    call cd_wait                ; DX = the status port, on every answer
    jc .no
    cmp al, 0xFF
    je .no
    mov al, ATA_C_PIDENT
    out dx, al
    call cd_delay
    call cd_wait
    jc .no
    test al, ATA_ST_ERR
    jnz .no
    test al, ATA_ST_DRQ
    jz .no                      ; nobody answered: no device there
    mov dx, bx                  ; ATA_DATA
    in ax, dx                   ; word 0, ON THE STACK across the drain
    push ax
    mov cx, 26                  ; words 1-26, dropped
.skip:
    in ax, dx
    loop .skip
    push ds                     ; ES = ours for the model, and NOT put back:
    pop es                      ; the one caller is DRVV_ATTACH, and the
                                ; drv_stamped that sent it restores ES itself
    mov di, cd_model
    mov cx, 20                  ; words 27-46: the model, two characters a
.model:                         ; word and the FIRST in the HIGH byte
    in ax, dx
    xchg al, ah
    stosw
    loop .model
    mov cx, 256 - 47
.rest:
    in ax, dx
    loop .rest
                                ; (cd_model+40, the NUL, is 0 from the load
                                ; and nothing writes it: the 20 words above
                                ; are bytes 0-39, and the trim writes zeros)
    pop ax                      ; word 0
    and ah, 0xDF                ; bits 15-14 = 10b (ATAPI) and 12-8 = 5 (a
    cmp ah, 0x85                ; CD-ROM): bit 13 is reserved
    jne .no
    and al, 3                   ; the packet's size: 0 = 12 bytes, 1 = 16,
    cmp al, 1                   ; and 2 or 3 a size no ATAPI version defines
    ja .no
    shl al, 1
    add al, 6
    cbw                         ; 6 or 8 WORDS - and AH = 0, the high byte the
    mov [cd_pkw], ax            ; trim below stops on
    mov di, cd_model + 39       ; the model is padded with spaces: trim them,
.tr:                            ; down to cd_pkw's high byte if it is ALL
    cmp byte [di], ' '          ; spaces - which is never one
    jne .ok
    mov byte [di], 0
    dec di
    jmp short .tr
.ok:
    CLC_OR_STC .no              ; CF = 0 here, CF = 1 at .no: cd_probe asks
                                ; for nothing but CF
    pop di
    pop cx
    ret


    OS88_DRV_END
