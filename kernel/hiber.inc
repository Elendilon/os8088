; =============================================================================
; os8088 - hiber.inc
;
; Hibernate the machine to a file on the hard disk, and resume it at the next
; boot (SPEC.md 87). Prefix `hb_` for the resident half, `hbf_` for its .cold
; thunks, `hbk_` for the far entries the module reaches cold code through,
; `hbm_` for the on-demand module and `hbs_` for the resume stub.
;
; WHAT IS RESIDENT is the least that has to be: the System menu's three
; strings live in menu.inc beside their siblings; here are the window
; template and title, the state block the image carries, the .text thunks a
; kernel window's callbacks need (a W_SEG-0 window is dispatched NEAR in
; KERNEL_SEG), and in .cold the boot probe, the greying predicate, the far
; entries, and the thunks that load the module before calling into it -
; cpf_cp_paint's shape (SPEC.md 2.8).
;
; EVERYTHING ELSE IS HIBER.DRV, MOD_HIBER: the window, the write, the
; boot-time question, the extent walk, the stub
; that puts memory back, and the routine that wakes the restored kernel. It
; is .cold code with the address changed (SPEC.md 2.8): CS = its own claim,
; DS = KERNEL_SEG, every kernel address the one this assembly gave it, and
; its own strings read through CS (SPEC.md 2.8.6) - nothing can draw them
; while the image is not loaded, because every path in is a thunk below that
; runs mod_need first.
;
; kern_small has none of it (SPEC.md 62.9.15's reason: the 128KB machine is
; not the one with a hard disk to hibernate to), and ships a one-entry stub
; module so that os88mod.py cuts the same four files out of every kernel.
; =============================================================================

HB_M_ASK    equ 0               ; the window offers Hibernate... / Cancel
HB_M_BUSY   equ 1               ; the image is being written (or read)
HB_M_RESUME equ 2               ; the boot-time question: Resume / Discard
HB_M_GONE   equ 3               ; the window closed: the thunk drops the image

; --- the module's entry slots (SPEC.md 2.8.1) - its ABI with the thunks -----
HBE_PAINT   equ 0
HBE_ONCLICK equ 1
HBE_ONUP    equ 2
HBE_ONKEY   equ 3
HBE_KINIT   equ 4
HBE_PERFORM equ 5
HBE_OPEN    equ 6
HB_NENT     equ 7
%if HB_NENT > MOD_NENT
  %error "hiber: more entries than mod_fp has slots for"
%endif
%ifdef KERN_BIG
HBFP        equ mod_fp + MOD_HIBER * MODFP_STRIDE
%endif

; --- API cells the module calls (SPEC.md 20.3); the kernel has no copy of
; --- apps/os88api.inc, so the four it needs are named here ------------------
HB_API_FILL   equ 0x0038        ; AX=x1, BX=y1, CX=x2, DX=y2 in [gfx_color]
HB_API_FONTX  equ 0x0068        ; CX=x, DX=y, the string at the CALLER's DS:SI
HB_API_COLOR  equ 0x00C0        ; AL -> [gfx_color]
HB_API_XCAPS  equ 0x0190        ; out BL = free block-table entries (SPEC.md 41)

; --- the pointer file, HIBERNAT.PTR (SPEC.md 87.3) ---------------------------
HBP_MAGIC   equ 0               ; 'HIB1'
HBP_BUILD   equ 4               ; dw BUILD_NUM
HBP_STAMP   equ 6               ; dw MOD_STAMP
HBP_MEMTOP  equ 8               ; dw [mem_top]
HBP_VID     equ 10              ; db [vid_kind]
HBP_WAKE    equ 12              ; dd hbm_wake, off:seg - and the 12 bytes in
HBP_DOS     equ 16              ; db 1 = THIS WAS NOT THE USER LEAVING THE
                                ; MACHINE (docs/plans/KERN-DOS-PLAN.md 8): the
                                ; image was written for a DOS handoff, so the
                                ; boot resumes it rather than asking. It is
                                ; BEHIND the fixed head on purpose - hbm_ask
                                ; compares the first twelve bytes and this is
                                ; not one of them, because it describes the
                                ; OCCASION and not the machine
HBP_PAD     equ 17              ; db 0
HBP_SIZE    equ 18              ; front of it are hbm_ptrfix, one description

; --- the staging area in the text framebuffer (SPEC.md 87.5) -----------------
; B800:0000 (or B000:0000 on a Hercules primary), which vid_reboot has just
; made a linear 16KB+ of RAM that no rung of the ladder owns. The stub's CS,
; DS and SS are all this segment, and every datum it reads is at one of
; these offsets - numeric, so the stub is position-independent.
HS_CODE     equ 0x0000          ; the stub, up to HS_CODE_MAX bytes
HS_CODE_MAX equ 0x0400
HS_UNIT     equ 0x0400          ; dw the int 13h drive
HS_SPT      equ 0x0402          ; dw sectors per track
HS_HEADS    equ 0x0404          ; dw heads
HS_NX       equ 0x0406          ; dw extents
HS_WAKE     equ 0x0408          ; dd hbm_wake, off:seg
HS_MASKM    equ 0x0410          ; db the master PIC's mask before the stub
HS_MASKS    equ 0x0411          ; db ...and the slave's
HS_CLK      equ 0x0412          ; db[10] clk_sec..clk_year of the fresh boot
HS_LBA      equ 0x0420          ; dd the run's first LBA (scratch)
HS_LEFT     equ 0x0424          ; dw sectors left in this extent
HS_K        equ 0x0426          ; dw the file sector index = linear / 512
HS_N        equ 0x0428          ; dw sectors in the call being issued
HS_CHS      equ 0x042A          ; dw CX, dw DX as int 13h wants them
HS_DOSCODE  equ 0x043A          ; dw the DOS program's exit code on a handoff
                                ; return, 0xFFFF = an ordinary resume. IT NEEDS
                                ; NO STUB CODE AT ALL: hbm_wake already reads
                                ; the staging area for HS_CLK, and the stub
                                ; never writes into that segment
HS_SLAVE    equ 0x042E          ; db 1 = there is a second 8259 to mask and
                                ; put back; 0 on an XT, whose port 0xA0 is
                                ; the NMI mask register (SPEC.md 9.9.2)
HS_IVT      equ 0x0500          ; db[1024] file sectors 0..1, the IVT
HS_EXT      equ 0x0A00          ; {dd lba, dw count} x HS_XMAX
HS_XMAX     equ 1280            ; one per sector of a 640KB image at worst
HS_XSTRIDE  equ 6                ; ...and one entry's bytes
HS_STACK    equ 0x3FF0          ; the stub's stack top: under a CGA's 16KB

; --- the DOS handoff's own fields (SPEC.md 96.40.1) -------------------------
; They sit ABOVE HS_SLAVE and BELOW HS_IVT, which the DOS stub never uses: it
; reads to KD_SEG, which is above the IVT and the BDA both, so it has no
; late-copy problem to solve and 1,024 bytes of the staging area are free. The
; launch block takes 512 of them.
KDS_PLEN    equ 0x0430          ; dd the part's PACKED bytes
KDS_ULEN    equ 0x0434          ; dd ...and what they expand to
KDS_TSEG    equ 0x0438          ; dw where the packed stream is read
; --- AND THE CORE PART'S, because the stub expands TWICE (SPEC.md 96.44.5.4)
; ONE extent list covers both: os88pkg.py lays parts out in table order and
; 512-aligned, so the core's bytes are immediately followed by kern_dos's and
; a single run reads the pair. KDS_CDELTA is how far into that run kern_dos's
; stream begins, in PARAGRAPHS.
KDS_CPLEN   equ 0x043A          ; dd the CORE part's packed bytes
KDS_CDELTA  equ 0x043E          ; dw paragraphs from the run's base to
                                ; kern_dos's own stream
KDS_CORG    equ 0x0440          ; dw where the core lands in KD_SEG
KDS_LB      equ 0x0500          ; db[512] the launch block, on HS_IVT's ground
KDS_TMPSEG  equ 0x1000          ; 64KB up: above kern_dos's image, which starts
                                ; at KD_SEG and is 46KB, so the stream and the
                                ; thing it expands to never meet and SPEC.md
                                ; 20.13.7's in-place rules need no thought

; --- kern_dos's own three numbers, MIRRORED (kerndos/kdlayout.inc) -----------
; tests/unit/t_mirror.py is what keeps them honest: a name defined in more than
; one place has to agree everywhere, and these three are the whole of what the
; kernel needs to know about a machine it is handing over to.
KD_SEG      equ 0x0060          ; linear 0x00600, above the IVT and the BDA
KD_H_LBP    equ 4               ; dw: where the launch block goes
KD_H_LBSZ   equ 6               ; dw: ...and how many bytes of it there are
KDL_SIZE    equ 512             ; ...which is one sector
KDL_FLAGS   equ 6               ; dw in the block: KDLF_*
KDL_UNIT    equ 12              ; dw ...and the unit `int 19h` is to boot from,
                                ; which is also the kernel's to fill
KDLF_HIBER  equ 4               ; ...bit 2, which is the ONE bit the kernel
                                ; sets rather than the box - whether there is a
                                ; fixed disk to come back to is hb_pick's
                                ; question (docs/plans/KERN-DOS-PLAN.md 8)
KDL_DPT     equ 16              ; db[11] in the block: the DISKETTE PARAMETER
KDL_DPT_LEN equ 11              ; TABLE, the one field the box cannot fill.
                                ; `hbm_dosrun` patches it into the STAGED copy
                                ; out of `dsk_dpt` - see kerndos/kdlaunch.inc
%if KDL_DPT_LEN != DPT_LEN
  %error "hiber: the launch block's DPT field is not a diskette parameter table"
%endif

; --- the record a package posts (SPEC.md 96.40) -----------------------------
; MIRRORED in apps/os88api.inc, and t_mirror is the guard.
KDH_MAGIC   equ 0               ; dd 'KDH1'
KDH_VOL     equ 4               ; db the volume DOS.O88 is on
KDH_PAD     equ 5               ; db 0
KDH_DIR     equ 6               ; dw its folder's first cluster, 0 = the root
KDH_NAME    equ 8               ; db[13] its 8.3 name, NUL-terminated
KDH_POFF    equ 21              ; dw the part's first file SECTOR
KDH_PLEN    equ 23              ; dd its packed bytes
KDH_ULEN    equ 27              ; dd ...and its unpacked bytes
KDH_LB      equ 31              ; db[512] the launch block, verbatim
KDH_WIN     equ 543             ; dw the window to wake on the way back, which
                                ; is the box's and only the box knows it
KDH_CODE    equ 545             ; dw the exit code the RESTORED kernel pokes in,
                                ; 0xFFFF = the program has not run. Both sides
                                ; of this one are the ordinary wake the box
                                ; already services (SPEC.md 74.1), so the
                                ; return needs no new slot
; --- AND THE CORE PART'S THREE, because the stub reads TWO (96.44.5.4) ------
; They go on the END rather than beside KDH_POFF, so KDH_LB's offset does not
; move: the launch block is 512 of the 547 and every field before it is one a
; wave already published.
KDH_COFF    equ 547             ; dw the CORE part's first file SECTOR
KDH_CPLEN   equ 549             ; dd its packed bytes
KDH_CULEN   equ 553             ; dd ...and its unpacked bytes
KDH_CORG    equ 557             ; dw where the core sits in kern_dos's
                                ; segment - CORE_ORG, which only the box knows
KDH_SIZE    equ 559
KDH_SIG     equ 0x3148444B      ; 'KDH1', little-endian
KDH_NOCODE  equ 0xFFFF          ; ...and what KDH_CODE says until it has one

; --- the exit code's mailbox (SPEC.md 96.41) --------------------------------
; MIRRORED in kerndos/kdlayout.inc, and tests/unit/t_mirror.py is the guard.
KDB_SEG     equ 0x0040          ; the BDA...
KDB_OFF     equ 0x00F0          ; ...and its intra-application area
KDB_SIG     equ 0x3158444B      ; 'KDX1', little-endian
KDB_CODE    equ 4               ; dw the program's exit code, behind the magic
%if HS_EXT + HS_XMAX*HS_XSTRIDE > HS_STACK - 512
  %error "hiber: the extent list would run into the stub's stack"
%endif

%ifdef KERN_BIG

section .text
; --- resident data: the template and the title (read through DS by wm) -----
hb_tpl:     dw 160, 150, 320, 100, hb_ttl, hb_paint, hb_onkey, hb_onclick
hb_ttl:     db 'Hibernate', 0
hb_s_ptr:   db 'HIBERNAT.PTR', 0    ; THE ONE name (SPEC.md 87.3). The two
HB_S_EXT    equ hb_s_ptr + 9        ; files differ in three bytes, so the
                                    ; module STAMPS the extension it wants.
                                    ; Every use sets it, so there is no state
                                    ; to leave wrong; the resident probe is the
                                    ; one reader that does not, and it runs at
                                    ; boot before any module can have stamped

; --- the .text thunks: a kernel window's callbacks are near procs here ------
hb_paint:   call COLD_SEG:hbf_paint
            ret
hb_onclick: call COLD_SEG:hbf_onclick
            ret
hb_onup:    call COLD_SEG:hbf_onup
            ret
hb_onkey:   call COLD_SEG:hbf_onkey
            ret
hb_kinit:   call COLD_SEG:hbf_kinit     ; KD_INIT: preserves every register
            ret

section .bss
; The state block. Part of the image, which is the point: what hb_perform
; banks before the write is what hbm_wake reads after the restore.
hb_mode:    resb 1              ; HB_M_*
hb_vol:     resb 1              ; the volume the image is (or will be) on
hb_down:    resb 1              ; the button the press armed, 1/2, 0 = none
hb_pad:     resb 1
hb_drvmask: resw 1              ; drv_tab rows detached before the image
hb_sp:      resw 1              ; hbm_perform's entry SP (SPEC.md 87.4)
hb_wakep:   resw 2              ; hbm_wake as off:seg, in the image's module
hb_resumes: resw 1              ; how many times this machine has woken
hb_unit:    resw 1              ; the transport facts (SPEC.md 87.5 step 1)
hb_spt:     resw 1              ; - these FOUR are HS_UNIT..HS_NX's own order
hb_heads:   resw 1              ;   and are staged as one block copy
hb_nx:      resw 1              ; ...how many extents the walk found
hb_base:    resd 1
hb_xseg:    resw 1              ; the extent list's claim, 0 = none
; --- THE DOS HANDOFF's POSTED RECORD (SPEC.md 96.40) ------------------------
; A FAR POINTER and not a copy, which is osapi_pkg_rehome's economy: the
; package's region is alive until drv_shutdown, so the four bytes that say
; where its KDH_* record lies are all the kernel has to keep resident. A copy
; would be 543 bytes of every machine's RAM for a feature most never use.
hb_dosoff:  resw 1              ; the record, in the POSTER's segment
hb_dosseg:  resw 1              ; 0 = nothing posted
hb_doscode: resw 1              ; **THE ONLY RESIDENT BYTES THE RETURN COSTS**
                                ; (docs/plans/KERN-DOS-PLAN.md 8): the code a
                                ; DOS handoff left in the BDA, between hbm_ask
                                ; reading it at the boot and hbm_res staging it
                                ; for the wake. It cannot be module data -
                                ; those two are separate loads of the image
                                ; with a posted restart between them
                                ; ...and NO staging cells: the kernel already
                                ; has both singletons this module wanted, and
                                ; hbm_btn satisfies the invariant that makes
                                ; them singletons (UI task, gfx lock held,
                                ; stage-then-draw inside one call) -
                                ; os88ui_krect for the rect (SPEC.md 13) and
                                ; cp_sbuf for the label (ctrl.inc)

section .cold
; =============================================================================
; The resident half's cold code: the probe, the predicate, the far entries
; and the thunks.
; =============================================================================

; -----------------------------------------------------------------------------
; hb_probe - is there a hibernation to offer? (SPEC.md 87.5; kmain, after
;            drv_boot and before the first paint)
; in:  nothing
; out: nothing (all registers preserved). A hit records the volume in [hb_vol]
;      and posts UI_RBQ_ASK, which ui_task's first pass spends.
;
; The ONE root a pointer can be in - hb_pick's volume, the one a hibernate
; writes to - in a drv_vol_bank/back bracket (SPEC.md 51.5.2) so the machine
; is left standing where drv_boot left it, and reached the way drv_load
; reaches a driver: a QUIET navigation (18.9: no listing, no icon harvest)
; and a walk of the directory sectors, not the snapshot. A floppy-only
; machine pays eight compares and no I/O; a machine with a hard disk pays
; one quiet mount of its root.
; -----------------------------------------------------------------------------
hb_probe_x:
    push ax
    push dx
    push si
    mov byte [hb_mode], HB_M_GONE   ; .bss is whatever the LAST kernel left
    mov word [hb_resumes], 0    ; (a warm boot clears nothing), and three of
    mov word [hb_xseg], 0       ; these are read before anything writes them
    mov word [hb_doscode], KDH_NOCODE   ; ...and this one means "no DOS program
                                ; ran", which is every resume but one
    call COLD_SEG:hb_pick_x     ; AL = the volume
    jc .out
    mov [hb_vol], al
    call drv_vol_bank
    mov dl, al
    xor ax, ax                  ; the root
    call dsk_chdir_q_x
    jc .back
    mov si, hb_s_ptr
    call drv_find               ; the directory sectors themselves
    jc .back
    mov byte [ui_rebootq], UI_RBQ_ASK
.back:
    call drv_vol_back
.out:
    pop si
    pop dx
    pop ax
    retf

; -----------------------------------------------------------------------------
; hb_pick - the disk a hibernation goes to, or is looked for on (SPEC.md 87.2):
;           the one the machine BOOTED from when that is a fixed disk, else
;           the first fixed volume there is - and never a DVK_FILE row, which
;           dsk_vol_fixed calls fixed and which has no sectors the stub could
;           read. THE predicate: the menu item, the probe and the window all
;           ask it, so what greys, what is probed and what is written to
;           cannot disagree (SPEC.md 47 rule 5)
; in:  nothing
; out: CF = 0 and AL = its index; CF = 1 no such volume
; clobbers: AX (the output), flags
; -----------------------------------------------------------------------------
; -----------------------------------------------------------------------------
; osapi_dos_handoff_x - the DOS box asks for the machine (SPEC.md 96.40)
; in:  ES:SI = a KDH_* record in the CALLER's segment
; out: CF=0 posted, CF=1 refused
;
; **IT ONLY RECORDS**, which is osapi_pkg_rehome's shape and
; osapi_mem_compact_wake's: what it asks for detaches every driver and takes
; the screen, and a package's callback is the one place that may not happen -
; the caller is executing in a region the teardown is about to stop caring
; about, with the gfx lock held. ui_task's step 0 spends it with nothing held.
;
; The record is read WHERE IT LIES rather than copied, so it must be in the
; package's image or bss and not on a stack: the four bytes here are the whole
; resident cost of the feature.
osapi_dos_handoff_x:
    push ax
    cmp word [hb_dosseg], 0     ; one at a time: a second post before the first
    jne .no                     ; is spent would be two machines' worth of
    mov ax, es                  ; parameters and one teardown
    or ax, ax
    jz .no
    mov [hb_dosseg], ax
    mov [hb_dosoff], si
    mov byte [ui_rebootq], UI_RBQ_DOSRUN
    mov byte [sch_uiwake], 1    ; ui_task blocks (SPEC.md 8.1.2), so the post
    pop ax                      ; has to wake it or the handoff waits for
    clc                         ; whatever else happens to
    retf
.no:
    pop ax
    stc
    retf

hb_pick_x:
    push bx
    push cx
    mov cl, [dsk_bootvol]
    call hb_pick1
    jnc .out
    xor cx, cx
.vol:
    call hb_pick1
    jnc .out
    inc cx
    cmp cx, DVOL_MAX
    jb .vol
    stc
.out:
    pop cx
    pop bx
    retf

hb_pick1:                       ; is volume CL one? out: CF = 0 and AL = CL
    mov bl, cl
    call dsk_vol_fixed_x        ; AL = 1 fixed, AH = the kind; CF = no row
    jc .no
    or al, al
    jz .no
    cmp ah, DVK_FILE
    je .no
    mov al, cl
    clc
    ret
.no:
    stc
    ret

; -----------------------------------------------------------------------------
; hb_ok - may the machine hibernate, AND WHICH STRING SAYS SO (SPEC.md 87.2,
;         47 rule 5)
; in:  nothing
; out: [menu_items_logo + 8] = menu_s_hiber / menu_s_hibernh / menu_s_hiberxm.
;      IT ANSWERS IN MEMORY AND NOT IN CF: ui_loc_gate is the only reader this
;      predicate has ever had, and it turned the CF/AL pair straight back into
;      one of three pointers - so the choice is here, where it is .cold bytes,
;      and .text is 19 lighter for it. A second caller wanting the reason back
;      re-adds the `clc`/`stc`; nothing wants it today
; clobbers: AX (AH is XCAPS's), flags. Everything else is
;           preserved, CX AND DX INCLUDED - see below
;
; Called on the press that opens the menu bar, so it is at most eight row
; tests and one far call into a table - no I/O, no probe.
;
; **THE FAR CALL ANSWERS IN THREE REGISTERS, NOT ONE** (SPEC.md 87.2).
; OSAPI_XM_CAPS is AX = free KB, DX:CX = the pool's linear base and BL = free
; block-table entries (SPEC.md 41.8), and this routine reads BL alone - so it
; saves CX and DX across it as well as BX, or it hands its caller three
; clobbers where its contract promises one.
;
; That is not a defensive push. ui_loc_gate promises ITS caller that nothing
; moves, and that caller is ui_task's mouse-down arm holding the press's x in
; CX and its y in DX; CX goes to menu_track three instructions later. And the
; call is reached ONLY when hb_pick found a fixed volume, so a floppy-booted
; machine takes the `jc .no` above it and never sees the damage: on an
; INSTALLED machine CX came back 0, every press in the bar hit-tested at x = 0,
; and cell 0 is the System menu in every application - so every menu title on
; the bar dropped the System menu.
; -----------------------------------------------------------------------------
hb_ok_x:
    push bx
    push cx                     ; ...and these two, for the reason above
    push dx
    call COLD_SEG:hb_pick_x     ; the volume a hibernate would go to
    mov al, 1
    jc .no
    call KERNEL_SEG:HB_API_XCAPS    ; BL = free block-table entries; on a
    cmp bl, XM_MAX_BLKS         ; machine with no store, all of them
    jb .xms
    mov bx, menu_s_hiber        ; ...and the STRING, because ui_loc_gate is
    jmp short .set              ; the only reader this answer has ever had
.xms:
    mov al, 2
.no:
    mov bx, menu_s_hibernh      ; BX for the string, because AL IS the reason
    cmp al, 1                   ; and a `mov ax` here read '(XMS)' on a
    je .set                     ; floppy-only machine
    mov bx, menu_s_hiberxm
.set:
    mov [menu_items_logo + 8], bx   ; item 4 of the System menu
    pop dx
    pop cx
    pop bx
    retf

; --- far entries for the module (SPEC.md 2.6): cold bodies that end in a near
; --- ret, reached from a segment of their own. Four bytes each.
hbk_bp:             call bp             ; cw_mem_disp's shape one segment
                    retf                ; along: ONE cold far entry for every
                                        ; cold body the module calls with BP
                                        ; free, which is nine of its ten
hbk_drv_blk_call:   call drv_blk_call_x ; ...and the tenth, which cannot use
                    retf                ; it: BP IS drv_blk_call's verb cell

; hbf_need - make the image resident (cpf_need's shape, ctrl.inc): the id in
; AL and the caller's AX put back, so a thunk below is three bytes and not
; seven. A NEAR call, and so is the mod_need inside it.
hbf_need:
    push ax
    mov al, MOD_HIBER
    call mod_need
    pop ax
    ret

; --- the thunks that load the module and call in (SPEC.md 2.8, cpf_'s shape)
hbf_paint:
    call hbf_need
    jc .gone
    call far [HBFP + HBE_PAINT*4]
.gone:
    retf

hbf_onclick:
    call hbf_need
    jc .gone
    call far [HBFP + HBE_ONCLICK*4]
.gone:
    retf

hbf_onup:                       ; a release can only follow a press this
    push ax                     ; window took, so mod_live, not mod_need
    mov al, MOD_HIBER           ; (SPEC.md 13.8.3)
    call mod_live
    pop ax
    jc .gone
    call far [HBFP + HBE_ONUP*4]
    call hbf_dropck
.gone:
    retf

hbf_onkey:
    call hbf_need
    jc .gone
    call far [HBFP + HBE_ONKEY*4]
    call hbf_dropck
.gone:
    retf

hbf_kinit:
    call hbf_need
    jc .gone
    call far [HBFP + HBE_KINIT*4]
.gone:
    retf

; hbf_open - the System menu's Hibernate... (ui_cmd, no lock held)
; A refusal here is about the DISK - the module could not be read - and the
; toast names it the way the Control Panel's does, out of the same table.
hbf_open:
    call hbf_need
    jc .no
    call far [HBFP + HBE_OPEN*4]
    retf
.no:
    call hbf_nodisk
    retf

hbf_nodisk:
    push ax
    push bx
    push cx
    mov al, 1
    mov bx, cp_opentab
    mov cx, CP_NOPEN
    call KERNEL_SEG:toast_say
    pop cx
    pop bx
    pop ax
    ret

; hbf_perform - a posted UI_RBQ_HIBER / UI_RBQ_RESUME / UI_RBQ_ASK, spent by
;               ui_task with nothing held (SPEC.md 87.4, 87.5)
; in:  AL = which
; out: nothing. Returns only on a refusal or a discard: a hibernate ends in
;      int 19h and a resume ends in the stub.
hbf_perform:
    call hbf_need
    jc .no
    call far [HBFP + HBE_PERFORM*4]
    call hbf_dropck
    retf
.no:
    cmp al, UI_RBQ_ASK          ; a question that cannot be asked is not
    je .quiet                   ; worth a toast: the pointer stays for a
    call hbf_nodisk             ; boot that has the system disk in
.quiet:
    retf

; hbf_dropck - the window closed inside the call that just returned, so the
;              image goes back now, from OUTSIDE it (SPEC.md 87.1)
hbf_dropck:
    cmp byte [hb_mode], HB_M_GONE
    jne .out
    push ax
    mov al, MOD_HIBER
    call mod_drop
    pop ax
.out:
    ret

; hbf_closed - app_close_win's KIND_HIBER hook (SPEC.md 87.1): the window went
;              by a route the module did not take - the close box, Close
;              Window, the Task Manager, the restart sweep - so nothing of the
;              module is on the stack and the image can go now. The module's
;              own closes set HB_M_GONE FIRST, and that is the test: a GONE
;              window is the module closing itself, and hbf_dropck drops the
;              image once it has returned
hbf_closed:
    cmp byte [hb_mode], HB_M_GONE
    je .out
    mov byte [hb_mode], HB_M_GONE
    push ax
    mov al, MOD_HIBER
    call mod_drop
    pop ax
.out:
    retf

; =============================================================================
; THE MODULE - HIBER.DRV (SPEC.md 2.8, 87)
;
; CS = the image's own claim, DS = KERNEL_SEG. Kernel data by name through
; DS; this file's own strings through CS; kernel code through KERNEL_SEG:cw_*
; shims (.text), COLD_SEG:*_x / hbk_* far entries (.cold) and the API cells.
; =============================================================================
section .modh
modh_hdr:
    dw 0x384F                   ; MOD_H_MAGIC
    db MOD_VER                  ; MOD_H_VER
    db MOD_HIBER                ; MOD_H_ID
    dw BUILD_NUM                ; MOD_H_BUILD  (SPEC.md 2.8.2)
    dw MOD_STAMP                ; MOD_H_STAMP
    dw modh_end                 ; MOD_H_IMG
    dw HB_NENT                  ; MOD_H_NENT
    dw modh_e_paint             ; HBE_PAINT
    dw modh_e_onclick           ; HBE_ONCLICK
    dw modh_e_onup              ; HBE_ONUP
    dw modh_e_onkey             ; HBE_ONKEY
    dw modh_e_kinit             ; HBE_KINIT
    dw modh_e_perform           ; HBE_PERFORM
    dw modh_e_open              ; HBE_OPEN
    times MOD_NENT - HB_NENT dw 0

modh_e_paint:   call hbm_paint
                retf
modh_e_onclick: call hbm_onclick
                retf
modh_e_onup:    call hbm_onup
                retf
modh_e_onkey:   call hbm_onkey
                retf
modh_e_kinit:   call hbm_kinit
                retf
modh_e_perform: call hbm_perform
                retf
modh_e_open:    call hbm_open
                retf

; --- the two names, stamped (SPEC.md 87.3): the kernel carries ONE and the
; --- module writes the three bytes that tell them apart. Out: SI = the name.
hbm_nptr:
    mov word [HB_S_EXT], 'PT'
    mov byte [HB_S_EXT+2], 'R'
    mov si, hb_s_ptr
    ret
hbm_nimg:
    mov word [HB_S_EXT], 'IM'
    mov byte [HB_S_EXT+2], 'G'
    mov si, hb_s_ptr
    ret

; --- geometry of the window's content (SPEC.md 87.1) -------------------------
HBW_LX      equ 8               ; text left, content-relative
HBW_LY      equ 6               ; first line's top
HBW_LH      equ 12              ; line pitch
HBW_BY      equ 54              ; the button band's top
HBW_BH      equ 16              ; ...and height
HBW_B1X     equ 8               ; the first button
HBW_B1W     equ 120
HBW_B2X     equ 140             ; the second
HBW_B2W     equ 80
HBW_CW      equ 320 - 2         ; content width: the template's W_W less the
HBW_CH      equ 100 - TITLE_H - 1   ; borders; height less the title bar

; -----------------------------------------------------------------------------
; hbm_str - draw one of THIS image's strings (SPEC.md 2.8.6)
; in:  CX = x, DX = y, SI = the string's offset in this image; the pen is set
; out: nothing (all registers preserved)
;
; The transparent string cell is an X stub: ES becomes the CALLER's DS and DS
; the kernel's, so with DS = CS for the call the string is read from here and
; [gfx_color] from where it lives.
; -----------------------------------------------------------------------------
hbm_str:
    push ds
    push cs
    pop ds
    call KERNEL_SEG:HB_API_FONTX
    pop ds
    ret

; -----------------------------------------------------------------------------
; hbm_stage - copy one of this image's NUL strings to DS:DI (kernel memory)
; in:  SI = the string's offset here, DI = the destination, CX = its size
; out: nothing (all registers preserved). Always NUL-terminated.
; -----------------------------------------------------------------------------
hbm_stage:
    push ax
    push cx
    push si
    push di
    dec cx                      ; room for the NUL
.copy:
    mov al, [cs:si]
    mov [di], al
    or al, al
    jz .done
    inc si
    inc di
    loop .copy
    mov byte [di], 0
.done:
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_toast - say one of this image's strings in the menu bar (SPEC.md 59)
; in:  SI = the string's offset here
; out: nothing (all registers preserved)
; -----------------------------------------------------------------------------
hbm_toast:
    push cx
    push es
    push cs
    pop es                      ; toast_show takes ES:SI
    xor cx, cx
    call KERNEL_SEG:cw_toast_show
    pop es
    pop cx
    ret

; -----------------------------------------------------------------------------
; hbm_origin - the window's content origin
; in:  SI = window ptr
; out: AX = content left, DX = content top
; -----------------------------------------------------------------------------
hbm_origin:
    push bx
    mov bx, si
    call KERNEL_SEG:cw_wm_content
    pop bx
    ret

; -----------------------------------------------------------------------------
; hbm_btnrect - one button's rect, staged in os88ui_krect
; in:  AL = 1 or 2, SI = window ptr
; out: BX = os88ui_krect, filled; SI = the label's offset here (this mode)
; clobbers: AX, BX, CX, DX, SI, flags
; -----------------------------------------------------------------------------
hbm_btnrect:
    push ax
    call hbm_origin             ; AX = left, DX = top
    mov bx, os88ui_krect
    add dx, HBW_BY
    mov [bx+2], dx
    add dx, HBW_BH - 1
    mov [bx+6], dx
    mov cx, ax
    pop ax
    cmp al, 1
    jne .two
    add cx, HBW_B1X
    mov [bx], cx
    add cx, HBW_B1W - 1
    mov [bx+4], cx
    mov si, hbm_s_bhib
    cmp byte [hb_mode], HB_M_RESUME
    jne .out
    mov si, hbm_s_bres
    jmp short .out
.two:
    add cx, HBW_B2X
    mov [bx], cx
    add cx, HBW_B2W - 1
    mov [bx+4], cx
    mov si, hbm_s_bcan
    cmp byte [hb_mode], HB_M_RESUME
    jne .out
    mov si, hbm_s_bdis
.out:
    ret

; -----------------------------------------------------------------------------
; hbm_btn - draw one button, upright or pressed as [hb_down] says
; in:  AL = 1 or 2, SI = window ptr; the gfx lock is held
; out: nothing (all registers preserved)
; -----------------------------------------------------------------------------
hbm_btn:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov di, OS88UI_FILL         ; the interior is erased first, so a redraw
    cmp al, 1                   ; between the two states never leaves a mark
    jne .flags
    or di, OS88UI_DEF           ; Enter is the first button
.flags:
    cmp al, [hb_down]
    jne .up
    or di, OS88UI_DOWN
.up:
    call hbm_btnrect            ; BX = the rect, SI = the label here
    push di
    mov di, cp_sbuf
    mov cx, CP_SBUF
    call hbm_stage              ; ...staged where the button drawer reads it
    pop di
    mov si, cp_sbuf
    call COLD_SEG:os88ui_btn_f
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_hit - which button is a point in?
; in:  CX = x, DX = y (screen), SI = window ptr
; out: AL = 1, 2 or 0
; clobbers: AL (the output), flags
; -----------------------------------------------------------------------------
hbm_hit:
    push bx
    push cx
    push dx
    push si
    push di
    mov di, cx                  ; DI = x, BX = y, across hbm_btnrect
    mov bx, dx
    mov al, 1
    call hbm_hitone
    jc .yes
    mov al, 2
    call hbm_hitone
    jc .yes
    xor al, al
.yes:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; hbm_hitone - is the point DI,BX inside button AL? (out CF = 1 yes)
hbm_hitone:
    push ax                     ; AL is hbm_hit's OWN output on a hit, BX the
    push bx                     ; y it carries across both calls and SI the
    push si                     ; window ptr - hbm_btnrect eats the last two,
    push bx                     ; y, across hbm_btnrect - which clobbers CX,
    call hbm_btnrect            ; BX = the krect. (It was `mov cx, bx` BEFORE
    pop cx                      ; the call, and no click ever landed)
    cmp di, [bx]
    jb .no
    cmp di, [bx+4]
    ja .no
    cmp cx, [bx+2]
    jb .no
    cmp cx, [bx+6]
    ja .no
    stc
    jmp short .out
.no:
    clc
.out:
    pop si                      ; ...and hbm_hit banks CX, DX and DI itself
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_paint - W_PAINT (SPEC.md 87.1)
; in:  SI = window ptr; content already white; the gfx lock is held
; out: nothing (all registers preserved)
; -----------------------------------------------------------------------------
hbm_paint:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov al, CBLACK
    call KERNEL_SEG:HB_API_COLOR
    call hbm_origin             ; AX = left, DX = top
    mov cx, ax
    add cx, HBW_LX
    add dx, HBW_LY
    mov bx, hbm_lines_ask
    mov al, [hb_mode]
    cmp al, HB_M_BUSY
    jne .notbusy
    mov bx, hbm_lines_busy
.notbusy:
    push ax
    mov al, [hb_vol]            ; the letter, patched into both faces' lines
    add al, 'A'
    mov [cs:hbm_s_r1 + HBM_R1_LTR], al
    mov [cs:hbm_s_a2 + HBM_A2_LTR], al
    pop ax
    cmp al, HB_M_RESUME
    jne .lines
    mov bx, hbm_lines_res
.lines:
    push si
.line:
    mov si, [cs:bx]
    or si, si
    jz .lined
    call hbm_str
    add dx, HBW_LH
    add bx, 2
    jmp short .line
.lined:
    pop si
    cmp byte [hb_mode], HB_M_BUSY
    je .out                     ; no buttons while it is happening
    mov al, 1
    call hbm_btn
    mov al, 2
    call hbm_btn
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; hbm_repaint - erase the content and paint it again, for a mode change
; in:  SI = window ptr; the gfx lock is held
hbm_repaint:
    push ax
    push bx
    push cx
    push dx
    call hbm_origin             ; AX = left, DX = top
    mov bx, dx
    mov cx, ax
    add cx, HBW_CW - 1
    mov dx, bx
    add dx, HBW_CH - 1
    push ax
    mov al, CWHITE
    call KERNEL_SEG:HB_API_COLOR
    pop ax
    call KERNEL_SEG:HB_API_FILL ; AX=x1, BX=y1, CX=x2, DX=y2
    call hbm_paint
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; hbm_win - this kind's window, if it is up
; out: CF = 0 and SI = window ptr; CF = 1 none
hbm_win:
    push ax
    push di
    mov al, KIND_HIBER
    call KERNEL_SEG:cw_inst_find_kind   ; DI = the record
    jc .no
    mov si, [di+I_WIN]
    or si, si
    jz .no
    pop di
    pop ax
    clc
    ret
.no:
    pop di
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; hbm_onclick - W_ONCLICK: arm the button the press landed on (SPEC.md 13.8)
; in:  CX = x, DX = y, SI = window ptr; the gfx lock is held
; -----------------------------------------------------------------------------
hbm_onclick:
    push ax
    cmp byte [hb_mode], HB_M_BUSY
    je .out
    call hbm_hit
    mov [hb_down], al
    or al, al
    jz .out
    call hbm_btn                ; ...drawn pressed
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_onup - W_ONMOUSEUP: fire if the release is on the armed button
; in:  CX = x, DX = y, SI = window ptr; the gfx lock is held
; -----------------------------------------------------------------------------
hbm_onup:
    push ax
    push bx
    mov bl, [hb_down]
    mov byte [hb_down], 0
    or bl, bl
    jz .out
    cmp byte [hb_mode], HB_M_BUSY
    je .out
    mov al, bl
    call hbm_btn                ; upright again, whatever happens next
    call hbm_hit
    cmp al, bl
    jne .out
    call hbm_act
.out:
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_onkey - W_ONKEY: Enter is the first button, Esc the second
; in:  AL = ascii, AH = scan, SI = window ptr; the gfx lock is held
; -----------------------------------------------------------------------------
hbm_onkey:
    push ax
    cmp byte [hb_mode], HB_M_BUSY
    je .out
    cmp al, 13
    jne .notcr
    mov al, 1
    jmp short .act
.notcr:
    cmp al, 27
    jne .out
    mov al, 2
.act:
    call hbm_act
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_act - one of the two buttons, in this mode (SPEC.md 87.1)
; in:  AL = 1 or 2, SI = window ptr; the gfx lock is held, UI task
; out: nothing (all registers preserved)
; -----------------------------------------------------------------------------
hbm_act:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    cmp byte [hb_mode], HB_M_RESUME
    je .resume
    cmp al, 2
    je .close
    call hbm_arm                ; Hibernate: check the disk, then post
    jmp short .out
.resume:
    cmp al, 2
    je .discard
    ; --- Resume: say so, and post the restore for the top of the pass -------
    mov byte [hb_mode], HB_M_BUSY
    call hbm_repaint
    cmp byte [ui_rebootq], 0
    jne .out                    ; a restart already posted wins (SPEC.md 20.10)
    mov byte [ui_rebootq], UI_RBQ_RESUME
    jmp short .out
.discard:
    call COLD_SEG:drvf_drv_vol_bank
    call hbm_forget             ; the pointer and the image go
    call COLD_SEG:drvf_drv_vol_back
.close:
    mov byte [hb_mode], HB_M_GONE       ; BEFORE the close: app_close_win's
    mov bx, si                          ; KIND_HIBER hook drops the image on
    mov bp, app_close_win
    call KERNEL_SEG:cw_mem_disp    ; every OTHER route (SPEC.md 87.1), and
                                        ; GONE is how it knows this is not one.
                                        ; Synchronous: task-less kind; the
                                        ; thunk drops the image on the way back
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_enter / hbm_root - stand in the root of [hb_vol], where BOTH files are
;              (SPEC.md 87.3). hbm_enter banks the user's volume first; the
;              callers that have already banked enter at hbm_root.
; out: CF = the chdir's; DX preserved
; -----------------------------------------------------------------------------
hbm_enter:
    call COLD_SEG:drvf_drv_vol_bank
hbm_root:
    push dx
    mov dl, [hb_vol]
    xor ax, ax                  ; the root: both files live in it (87.3)
    mov bp, dsk_chdir_x         ; ...through the one far entry (SPEC.md 2.6)
    call COLD_SEG:hbk_bp
    pop dx                      ; ...and a pop does not touch the chdir's CF
    ret

; -----------------------------------------------------------------------------
; hbm_findimg - find HIBERNAT.IMG in the volume standing now, and stage its
;               directory entry
; out: CF = 0 and SI = the staged entry; CF = 1 there is no such file
; -----------------------------------------------------------------------------
hbm_findimg:
    call hbm_nimg               ; SI = the name - this build has ONE, and the
    mov bp, dsk_find_name_x     ; extension is stamped on (SPEC.md 87.3)
    call COLD_SEG:hbk_bp
    jc .no
    mov bp, dsk_get_dir_x
    call COLD_SEG:hbk_bp
    clc                         ; dsk_get_dir's documented clobber is the
.no:                            ; FLAGS - the three sites this replaces each
    ret                         ; set their own before looking at CF

; -----------------------------------------------------------------------------
; hbm_forget - delete the pointer and the image (SPEC.md 87.6 step 5, and
;              87.4 step 3, before a new pair is written)
; in:  [hb_vol] = the volume; both files are in its root
; out: nothing (all registers preserved); failures are ignored - there is
;      nothing further to do about a file that is already gone. The volume is
;      left at the root of [hb_vol]: a caller standing elsewhere brackets
;      this with drv_vol_bank/back.
; -----------------------------------------------------------------------------
hbm_forget:
    push ax
    push dx
    push si
    call hbm_root               ; both live in the root (SPEC.md 87.3)
    jc .out
    call hbm_nptr               ; the pointer FIRST: with it gone there is
    call COLD_SEG:dwf_dskw_delete   ; nothing to resume whatever becomes of
    call hbm_nimg               ; the image (SPEC.md 87.3)
    call COLD_SEG:dwf_dskw_delete
.out:
    pop si
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_kinit - KD_INIT (SPEC.md 29.3): the release hook and the snap
; in:  BX = window ptr, DI = 0, SI = the record; no lock; not yet visible
; out: nothing (all registers preserved)
; -----------------------------------------------------------------------------
hbm_kinit:
    push ax
    mov byte [hb_down], 0
    mov ax, hb_onup
    call KERNEL_SEG:cw_wm_onmouseup
    mov al, 1
    call KERNEL_SEG:cw_wm_snap  ; text on cell boundaries (SPEC.md 11.94)
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_open - the System menu's Hibernate... (SPEC.md 87.1): open the window
; in:  nothing; UI task, no lock
; out: nothing (all registers preserved)
; -----------------------------------------------------------------------------
hbm_open:
    push ax
    push si
    call hbm_win                ; already up, in whatever mode: app_launch
    jnc .launch                 ; fronts it and the mode stays what it is
    call COLD_SEG:hb_pick_x     ; the disk (SPEC.md 87.2): the item was
    jc .out                     ; live, so there is one
    mov [hb_vol], al            ; ...and the window names it
    mov byte [hb_mode], HB_M_ASK
    mov byte [hb_down], 0
.launch:
    mov al, KIND_HIBER
    call KERNEL_SEG:cw_app_launch
    jnc .out
    call KERNEL_SEG:cw_snd_beep
.out:
    pop si
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_geom - the transport facts for a volume (SPEC.md 87.5 step 1)
; in:  AL = the volume index
; out: CF = 0 and [hb_unit], [hb_spt], [hb_heads], [hb_base] filled;
;      CF = 1: not a fixed disk the ROM's int 13h reaches
; clobbers: flags
; -----------------------------------------------------------------------------
hbm_geom:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov bl, al
    call COLD_SEG:dskf_dsk_vol_row  ; BX = the row
    jc .no
    cmp byte [bx+DV_KIND], DVK_BIOS
    jne .drv
    mov dl, [bx+DV_UNIT]        ; the boot partition (SPEC.md 52.10.3): the
    test dl, 0x80               ; kernel holds every fact itself
    jz .no
    xor dh, dh
    mov [hb_unit], dx
    mov bl, al
    xor bh, bh
    shl bx, 1
    shl bx, 1
    mov dx, [dsk_vbase + bx]
    mov [hb_base], dx
    mov dx, [dsk_vbase + bx + 2]
    mov [hb_base + 2], dx
    mov dx, [dsk_bootspt]
    mov [hb_spt], dx
    mov dx, [dsk_boothds]
    mov [hb_heads], dx
    jmp short .check
.drv:
    cmp byte [bx+DV_KIND], DVK_DRV
    jne .no
    mov ah, [bx+DV_UNIT]        ; the driver's handle
    mov al, [bx+DV_CLASS]
    mov [drv_blkcls], al
    call COLD_SEG:drvf_drv_cls_svc  ; DI = the class's service table
    jc .no
    mov bp, [di+DSV_GEOM]       ; == DSV_BLK, and AL = 2 is the sub-function
    mov al, 2
    call COLD_SEG:hbk_drv_blk_call  ; DL = unit, CX:BX = base, SI = spt,
    jc .no                      ; DI = heads; CF = 1 not int 13h
    xor dh, dh
    mov [hb_unit], dx
    mov [hb_base], bx
    mov [hb_base + 2], cx
    mov [hb_spt], si
    mov [hb_heads], di
.check:
    mov ax, [hb_spt]            ; 1..63 and 1..255 as ONE unsigned window
    dec ax                      ; each: 0 wraps to 0xFFFF and is refused by
    cmp ax, 62                  ; the same `ja` the upper bound needs
    ja .no
    mov ax, [hb_heads]
    dec ax
    cmp ax, 254
    ja .no
    clc
    jmp short .out
.no:
    stc
.out:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_arm - the Hibernate button (SPEC.md 87.2, 87.4): the disk in [hb_vol]
;           has to be one the ROM reaches and have the room, and then the
;           write is POSTED for the top of the pass
; in:  SI = the window; the gfx lock is held
; out: nothing (all registers preserved); a refusal is a toast
; -----------------------------------------------------------------------------
hbm_arm:
    push ax
    push bx
    push cx
    push dx
    push si
    call COLD_SEG:drvf_drv_vol_bank ; the user may be standing anywhere
    mov al, [hb_vol]
    call hbm_geom
    jc .nobios
    call hbm_root               ; the root: where the image goes, and where
    jc .failed                  ; dfree answers for
    call COLD_SEG:dwf_dskw_dfree    ; DX:AX = free bytes
    jc .failed
    push ax
    push dx
    push si
    call hbm_findimg            ; ...plus what replacing an old image frees
    jc .noold                   ; SI = the staged entry, its size at 20
    pop bx
    pop dx
    pop ax
    add ax, [si+20]
    adc dx, [si+22]
    push ax
    push dx
    push bx
.noold:
    pop si
    pop dx
    pop ax
    push ax
    push dx
    call hbm_imgsize            ; DX:AX = the image's bytes
    add ax, 0x1000              ; ...and the pointer, with room to spare
    adc dx, 0
    mov cx, ax
    mov bx, dx                  ; BX:CX = the need
    pop dx
    pop ax                      ; DX:AX = the room
    cmp dx, bx
    jb .noroom
    ja .room
    cmp ax, cx
    jb .noroom
.room:
    call COLD_SEG:drvf_drv_vol_back
    mov byte [hb_mode], HB_M_BUSY
    call hbm_repaint
    cmp byte [ui_rebootq], 0
    jne .out                    ; a restart already posted wins (SPEC.md 20.10)
    mov byte [ui_rebootq], UI_RBQ_HIBER
    jmp short .out
.nobios:
    mov si, hbm_s_nobios
    jmp short .refuse
.failed:
    mov si, hbm_s_failed        ; the disk could not be read, which is not
    jmp short .refuse           ; "no room" (LESSONS: the right refusal with
.noroom:                        ; the wrong reason sends the user deleting
    mov si, hbm_s_noroom        ; files that were never the problem)
.refuse:
    call hbm_toast
    call COLD_SEG:drvf_drv_vol_back
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_perform - a posted request, spent with nothing held (SPEC.md 87.4/87.5)
; in:  AL = UI_RBQ_HIBER / UI_RBQ_RESUME / UI_RBQ_ASK; UI task, no lock
; out: nothing; returns only from a refusal, a discard, or the question
;
; [hb_sp] is this routine's entry SP - the word under it is the return into
; modh_e_perform - and it is the frame hbm_wake comes back to after a
; resume, and the one every exit below returns through.
; -----------------------------------------------------------------------------
hbm_perform:
    ; STKBALANCE-OK: enters the resume stub by pushing HS_CODE:0 and `retf`
    ; into it (SPEC.md 87.5) - a far jump spelled as a return, on purpose, so
    ; the static walk sees a ret two words deep. Nothing returns here.
    mov [hb_sp], sp
    cld
    cmp al, UI_RBQ_HIBER
    je hbm_hib
    cmp al, UI_RBQ_RESUME
    je hbm_res
    cmp al, UI_RBQ_DOSRUN
    je hbm_dosrun
    jmp hbm_ask

; --- hbm_hib: write the image and stop (SPEC.md 87.4) ------------------------
; -----------------------------------------------------------------------------
; hbm_wrimg - THE IMAGE AND ITS POINTER, and nothing after them (87.4 steps 1-6)
; in:  AL = what HBP_DOS is to say: 0 the user is leaving, 1 a DOS handoff
; out: CF = 0 written. CF = 1 not, and the caller owns the unwind - the lock,
;      [sch_lock] and the detached drivers are STILL TAKEN either way, because
;      both callers go on holding them
;
; Factored because docs/plans/KERN-DOS-PLAN.md 8 has a second customer: the DOS
; handoff writes an image so that the machine has somewhere to come back to,
; and then does NOT stop - where hibernate's own step 7 asks the user to switch
; the machine off.
; -----------------------------------------------------------------------------
hbm_wrimg:
    push ax
    mov [cs:hbm_dosflag], al
    mov byte [cs:hbm_dosheld], 1    ; ...both taken below, and given back by
                                    ; neither arm
    call COLD_SEG:drvf_drv_vol_bank ; where the user stands, for a refusal
    call hbm_detach             ; 1. the hardware drivers go, and are noted
    call KERNEL_SEG:cw_gfx_lock ; 2. held from here: the machine is one
    inc byte [sch_lock]         ;    instant from here on - and only NOW
    call hbm_root               ; 3. the root of the disk the boot picked:
    jc .no                      ;    the detach yields, and a task that took
                                ;    the turn could have moved the current
                                ;    directory under the write
    call hbm_forget             ;    ...and the OLD pointer and image go
                                ;    before a byte is written: a pointer that
                                ;    outlived its question would otherwise
                                ;    name the NEW image with the old session's
                                ;    wake address (SPEC.md 87.3)
    mov word [hb_wakep], hbm_wake   ; 4. where the restored kernel enters
    mov [hb_wakep + 2], cs
    call hbm_nimg               ; 5. the image: all of memory, one write
    xor bx, bx
    mov es, bx
    call hbm_imgsize            ; DX:AX = bytes
    mov cx, ax
    call COLD_SEG:dwf_dskw_write
    jc .no
    call hbm_ptr_build          ; 6. the pointer, beside it
    call hbm_nptr
    push cs
    pop es
    mov bx, hbm_ptrbuf
    xor dx, dx
    mov cx, HBP_SIZE
    call COLD_SEG:dwf_dskw_write
    jc .no
    pop ax
    clc
    ret
.no:
    pop ax
    stc
    ret

hbm_hib:
    xor al, al                  ; HBP_DOS = 0: this IS the user leaving
    call hbm_wrimg
    jc .fail
    call hbm_kbdrain            ; 7. a key typed during the write is not the
    mov bp, vid_reboot
    call KERNEL_SEG:cw_mem_disp   ;    answer; text mode, the sentence, a key
    mov si, hbm_s_off
    call hbm_tty
    xor ah, ah
    int 0x16
    call COLD_SEG:drv_shutdown_x    ; ...and the reboot path's tail (20.10)
%ifndef NO_FDDPARK
    jmp KERNEL_SEG:sched_unhook     ; ...and the WHOLE of that tail, shared and
                                    ; not copied: unhook, SPEC.md 18.100's park
                                    ; and the int 19h at the end of it. The user
                                    ; is ASKED to switch off here, and one who
                                    ; does not gets an ordinary boot off a
                                    ; machine that has read floppies all
                                    ; session. NEVER RETURNS, which is why this
                                    ; is a jmp and there is nothing after it
%else
    mov bp, sched_unhook            ; ...and on this arm sched_unhook DOES
    call KERNEL_SEG:cw_mem_disp     ; return, so it is a call through the
    int 0x19                        ; kernel's generic BP trampoline and the
    jmp $                           ; int 19h is ours to issue
%endif
.fail:
    mov byte [cs:hbm_dosheld], 0
    dec byte [sch_lock]
    call KERNEL_SEG:cw_gfx_unlock
    call hbm_reload             ; the drivers come back
    call COLD_SEG:drvf_drv_vol_back
    mov byte [hb_mode], HB_M_ASK
    mov si, hbm_s_failed
    call hbm_toast
    call hbm_winback
    mov sp, [hb_sp]
    ret

; hbm_winback - the window, if it is up, painted for the mode it is in now
; in:  nothing; no lock held
hbm_winback:
    push si
    call hbm_win
    jc .out
    call KERNEL_SEG:cw_gfx_lock
    call hbm_repaint
    call KERNEL_SEG:cw_gfx_unlock
.out:
    pop si
    ret

; hbm_kbdrain - empty the ROM's keyboard buffer (SPEC.md 87.4 step 7, 87.5)
; in:  nothing; out: nothing (all registers preserved)
hbm_kbdrain:
    push ax
.more:
    mov ah, 0x01
    int 0x16
    jz .out
    xor ah, ah
    int 0x16
    jmp short .more
.out:
    pop ax
    ret

; hbm_tty - print one of this image's strings through the ROM's teletype
; in:  SI = the string's offset here; text mode
hbm_tty:
    push ax
    push bx
    push si
.ch:
    mov al, [cs:si]
    or al, al
    jz .out
    mov ah, 0x0E
    mov bx, 0x0007
    int 0x10
    inc si
    jmp short .ch
.out:
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_detach / hbm_reload - the drivers that own hardware (SPEC.md 87.4 step 2)
; in:  nothing; UI task, NO lock held (an unload waits on its worker)
; out: nothing (all registers preserved); [hb_drvmask] says which rows
; -----------------------------------------------------------------------------
hbm_detach:
    push ax
    push bx
    push cx
    mov word [hb_drvmask], 0
    xor cx, cx
.row:
    mov al, cl
    call COLD_SEG:drvf_drv_row  ; BX = the row
    cmp word [bx+DRVR_SEG], 0
    je .next
    mov al, [bx+DRVR_CLASS]
    cmp al, DRVC_DISK
    je .next                    ; memory and the ROM's int 13h: it stays
    cmp al, DRVC_FILE
    je .next                    ; the RAM disk: memory, and it stays
    mov ax, 1
    shl ax, cl
    or [hb_drvmask], ax
    mov al, cl
    call COLD_SEG:drvf_drv_unload
.next:
    inc cx
    cmp cx, DRV_MAX
    jb .row
    pop cx
    pop bx
    pop ax
    ret

hbm_reload:
    push ax
    push cx
    push dx
    xor cx, cx
    mov dx, [hb_drvmask]
.row:
    shr dx, 1
    jnc .next
    mov al, cl
    call COLD_SEG:drvf_drv_load ; failures show on the Drivers page, as at boot
.next:
    inc cx
    cmp cx, DRV_MAX
    jb .row
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_ptr_build - compose the pointer file in this image's buffer (87.3)
; -----------------------------------------------------------------------------
hbm_ptr_build:
    call hbm_ptrfix_set
    push ax
    push cx
    push si
    push di
    push es
    push cs
    pop es
    cld
    push ds                     ; the fixed head, staged from the ONE
    push cs                     ; description of it (SPEC.md 87.3): magic,
    pop ds                      ; build, stamp, mem_top and the adapter, all
    mov si, hbm_ptrfix          ; twelve bytes of it, in one copy
    mov di, hbm_ptrbuf
    mov cx, HBP_WAKE / 2
    rep movsw
    pop ds
    mov di, hbm_ptrbuf          ; ...and the wake address, this session's own
    mov ax, [hb_wakep]
    mov [es:di+HBP_WAKE], ax
    mov ax, [hb_wakep + 2]
    mov [es:di+HBP_WAKE + 2], ax
    mov al, [cs:hbm_dosflag]    ; ...and WHY this image exists, which is the
    mov [es:di+HBP_DOS], al     ; one thing in the file that is about the
    mov byte [es:di+HBP_PAD], 0 ; occasion rather than the machine
    pop es
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_ask - the boot-time question (SPEC.md 87.5): validate the pointer,
;           find the image, and open the window in HB_M_RESUME
; in:  [hb_vol] = the volume the probe found the pointer on; no lock
; -----------------------------------------------------------------------------
hbm_ask:
    call hbm_enter
    jc .gone
    call hbm_nptr
    push cs
    pop es
    mov bx, hbm_ptrbuf
    xor dx, dx
    mov cx, HBP_SIZE
    call COLD_SEG:dwf_dskw_read ; DX:AX = bytes
    jc .gone
    cmp ax, HBP_SIZE
    jne .stale
    call hbm_ptrfix_set         ; ONE description of the fixed head, written
    push ds                     ; by hbm_ptr_build and compared here (87.3)
    push es
    push cs
    pop ds
    push cs
    pop es
    mov si, hbm_ptrfix
    mov di, hbm_ptrbuf
    mov cx, HBP_WAKE / 2
    repe cmpsw
    pop es                      ; ...and a pop does not touch cmpsw's ZF
    pop ds
    jne .stale
    call hbm_findimg            ; ...which is mounted: the pointer came from it
    jc .lost                    ; SI = the staged entry
    call hbm_imgsize            ; DX:AX = what the image must be
    cmp [si+20], ax
    jne .lost
    cmp [si+22], dx
    jne .lost
    mov al, [hb_vol]
    call hbm_geom
    jc .nobios
    call COLD_SEG:drvf_drv_vol_back
    mov byte [hb_mode], HB_M_RESUME
    ; --- ...AND WHETHER TO ASK AT ALL (docs/plans/KERN-DOS-PLAN.md 8) -------
    ; An image written for a DOS handoff is not the user leaving the machine,
    ; so there is no question to put: the session is coming back and the only
    ; thing the user did was run a program. Everything above still runs - the
    ; fixed head, the image's size, the geometry - because a stale or
    ; unreadable pointer is exactly as fatal either way.
    cmp byte [cs:hbm_ptrbuf + HBP_DOS], 0
    je .askit
    call hbm_dosbda             ; the exit code, out of the BDA
    cmp byte [ui_rebootq], 0
    jne .out                    ; a restart already posted wins (SPEC.md 20.10)
    mov byte [ui_rebootq], UI_RBQ_RESUME
    jmp short .out
.askit:
    mov byte [hb_down], 0
    call hbm_kbdrain            ; a key held at the hibernate's own prompt
                                ; repeats through int 19h into this boot, and
                                ; ui_task's next step hands it to the front
                                ; window - where Esc is Discard
    mov al, KIND_HIBER
    call KERNEL_SEG:cw_app_launch
    jmp short .out
.stale:
    mov si, hbm_s_stale
    jmp short .drop
.lost:
    mov si, hbm_s_lost
    jmp short .drop
.nobios:
    mov si, hbm_s_nobios
.drop:
    call hbm_toast
    call hbm_forget             ; a pointer nothing can act on
.gone:
    call COLD_SEG:drvf_drv_vol_back
    mov byte [hb_mode], HB_M_GONE   ; ...and the image goes back too
.out:
    mov sp, [hb_sp]
    ret

; -----------------------------------------------------------------------------
; hbm_dosbda - the DOS program's exit code, out of the BDA (SPEC.md 96.41)
; out: [hb_doscode] = the code, or KDH_NOCODE; the mailbox is CLEARED
;
; `kd_leave` wrote it at `0040:00F0` before its `int 19h` and it survived the
; ROM's bootstrap and our own boot (docs/plans/KERN-DOS-PLAN.md 8.2). Read
; ONCE and cleared, because the next thing that reads it would otherwise find
; a code from a session two boots ago and attach it to the wrong program.
; -----------------------------------------------------------------------------
hbm_dosbda:
    push ax
    push di
    push es
    mov word [hb_doscode], KDH_NOCODE
    mov ax, KDB_SEG
    mov es, ax
    mov di, KDB_OFF
    cmp word [es:di], KDB_SIG & 0xFFFF
    jne .out
    cmp word [es:di+2], KDB_SIG >> 16
    jne .out
    mov ax, [es:di+KDB_CODE]
    mov [hb_doscode], ax
    xor ax, ax
    mov [es:di], ax             ; spent: the magic goes, not the code, so a
    mov [es:di+2], ax           ; second reader gets nothing rather than this
.out:
    pop es
    pop di
    pop ax
    ret

; hbm_ptrfix_set - fill the two fields of the fixed head that are the running
;                  machine's, so hbm_ptr_build and hbm_ask read ONE object
hbm_ptrfix_set:
    push ax
    mov ax, [mem_top]
    mov [cs:hbm_ptrfix + HBP_MEMTOP], ax
    mov al, [vid_kind]
    mov [cs:hbm_ptrfix + HBP_VID], al
    mov byte [cs:hbm_ptrfix + HBP_VID + 1], 0
    pop ax
    ret

; hbm_imgsize - out: DX:AX = [mem_top] * 16, the bytes an image must have
hbm_imgsize:
    push cx
    mov ax, [mem_top]
    mov dx, ax
    mov cl, 4
    shl ax, cl
    mov cl, 12
    shr dx, cl
    pop cx
    ret

; -----------------------------------------------------------------------------
; hbm_res - put the image back (SPEC.md 87.5): the extents, then the stub
; in:  the question was answered Resume; no lock held
; -----------------------------------------------------------------------------
hbm_res:
    call hbm_enter              ; where the user stands, for a refusal
    jc .fail
    call hbm_findimg            ; SI = the entry: [si+18] its first cluster
    jc .fail
    mov ax, [si+18]
    push ax
    call hbm_xcap               ; 2. sized for THIS volume, not the worst one
    mov bx, MEM_K_HIB
    mov bp, mem_claim_x
    call COLD_SEG:hbk_bp ; DX = its segment
    pop ax
    jc .fail
    mov [hb_xseg], dx
    call hbm_extents            ; AX = first cluster in; [hb_nx] out
    jc .failx
    ; 3. the panel's settings, the fresh boot's drivers go, the lock is taken,
    ;    text mode - ui_cmd_reboot's order (SPEC.md 20.10, 31.8) -----------
    call COLD_SEG:cpf_cp_flush_close
    call COLD_SEG:drv_shutdown_x
    call KERNEL_SEG:cw_gfx_lock
    mov bp, vid_reboot
    call KERNEL_SEG:cw_mem_disp
    ; 4. the staging area ---------------------------------------------------
    call hbm_stageseg           ; ES = the text framebuffer
    push ds
    push cs
    pop ds
    mov si, hbs_stub            ; the stub, to offset 0
    mov di, HS_CODE
    mov cx, hbs_stub_end - hbs_stub
    rep movsb
    pop ds
    mov si, hb_unit             ; unit, spt, heads, extents - the stub's order
    mov di, HS_UNIT
    mov cx, 4
    rep movsw
    push ds                     ; ...and the wake address out of the pointer
    push cs
    pop ds
    mov si, hbm_ptrbuf + HBP_WAKE
    mov di, HS_WAKE
    mov cx, 2
    rep movsw
    pop ds
    mov si, clk_sec             ; the fresh boot's clock (SPEC.md 87.6): ten
    mov di, HS_CLK              ; bytes, clk_sec..clk_year, and NOT the two
    mov cx, 5                   ; display toggles after them, which are the
    rep movsw                   ; image's to keep
    mov ax, [hb_doscode]        ; ...and the DOS program's exit code, if this
    mov [es:HS_DOSCODE], ax     ; resume is a handoff coming home. NO STUB CODE
                                ; AT ALL: hbm_wake reads this segment anyway
    push ds
    mov ds, [hb_xseg]           ; the extents
    xor si, si
    mov di, HS_EXT
    mov cx, [es:HS_NX]
    mov ax, cx
    shl cx, 1
    add cx, ax                  ; words: 3 per extent
    rep movsw
    pop ds
    ; 5. the ROM's int 08h back, the kernel's IRQs masked, and go ----------
    jmp hbm_handover            ; **A JUMP AND NOT A CALL**: what ends that
                                ; routine is a `retf` that is a FAR JUMP INTO
                                ; THE STUB spelled as a return (SPEC.md 87.5),
                                ; so os88ovlchk's 2.6.1 rule reads a near call
                                ; to it as a far entry called wrongly - and it
                                ; is right that nothing returns here

.failx:
    mov dx, [hb_xseg]
    mov bx, MEM_K_HIB
    mov bp, mem_free_x
    call COLD_SEG:hbk_bp
    mov word [hb_xseg], 0
.fail:
    call COLD_SEG:drvf_drv_vol_back
    mov byte [hb_mode], HB_M_RESUME
    mov si, hbm_s_lost
    call hbm_toast
    call hbm_winback
    mov sp, [hb_sp]
    ret

; =============================================================================
; THE DOS HANDOFF (SPEC.md 96.40, docs/plans/KERN-DOS-PLAN.md §7)
; =============================================================================
; The DOS box has asked for the WHOLE machine. What follows is §87.5's resume
; with a different payload and a different stub - the same extent walk, the
; same staging area, the same teardown in the same order - and it is here
; rather than in a module of its own for exactly that reason: one walker, one
; staging layout, one place where the kernel stops being the kernel.
;
; WHAT IS DIFFERENT is the thing being read. A resume reads an IMAGE that is
; the whole of memory; this reads a PART of a package - a byte range of
; DOS.O88 - and the range is compressed, so the stub expands it. The walk
; therefore takes a SKIP and a COUNT where the resume's takes neither.
;
; It does not come back. The machine it hands over has no kernel in it.
; -----------------------------------------------------------------------------
hbm_dosrun:
    ; --- 1. the record, where the poster left it (SPEC.md 96.40) -----------
    ; It is copied into the MODULE's own data and every read of it carries a
    ; `cs:`, because DS here is KERNEL_SEG - the module runs with the kernel's
    ; data segment and its own code segment, which is what the rest of this
    ; file assumes and what makes [hb_dosseg] readable without an override.
    push ds
    push es
    mov si, [hb_dosoff]         ; **THE OFFSET BEFORE THE SEGMENT.** Both words
                                ; are KERNEL_SEG's, and the line below is what
                                ; stops DS being it - so loading DS first makes
                                ; the second read come out of the POSTER's own
                                ; image at that offset. It assembles, it runs,
                                ; and it copies 543 bytes of somebody else's
                                ; bss over the record
    mov ds, [hb_dosseg]
    push cs
    pop es
    mov di, hbm_dosrec
    mov cx, KDH_SIZE
    rep movsb
    pop es
    pop ds
    cmp word [cs:hbm_dosrec + KDH_MAGIC], KDH_SIG & 0xFFFF
    jne .b1
    cmp word [cs:hbm_dosrec + KDH_MAGIC + 2], KDH_SIG >> 16
    jne .b1

    ; --- 2. stand where DOS.O88 is, and find it -----------------------------
    call COLD_SEG:drvf_drv_vol_bank     ; hbm_enter's first half: bank where
    mov ax, [cs:hbm_dosrec + KDH_DIR]   ; the user stands, then stand where
    mov dl, [cs:hbm_dosrec + KDH_VOL]   ; DOS.O88 is - a FOLDER cluster, not
    mov bp, dsk_chdir_x                 ; hbm_root's zero, because a package
    call COLD_SEG:hbk_bp                ; lives in APPS/ and not in the root
    jc .b2
    ; **THE NAME HAS TO BE IN KERNEL_SEG**, which is not what ES says: the
    ; compare underneath is `dsk_streq`, and that reads DS:SI against DS:DI
    ; (kernel/disk.inc) - so a name in the module's own image is read at that
    ; offset in the KERNEL's segment and matches nothing. `api_name` is the
    ; kernel's own 13-byte stage for exactly this question, it is exactly
    ; KDH_NAME's length, and it is free here: it is what the N cells copy a
    ; package's name into, and nothing is inside a package call at ui_task's
    ; step 0. Zero resident bytes for the buffer, thirteen for the copy.
    mov si, hbm_dosrec + KDH_NAME
    mov di, api_name
    mov cx, 13
.nm:
    mov al, [cs:si]             ; ...and BYTE BY BYTE, not `movsb`: a module's
    mov [di], al                ; own data is CS-relative (SPEC.md 2.8.6) and
    inc si                      ; a repeated string op with a segment override
    inc di                      ; loses the prefix to an interrupt on an 8086
    loop .nm
    mov si, api_name
    mov bp, dsk_find_name_x
    call COLD_SEG:hbk_bp                ; AX = the index
    jc .b3
    mov bp, dsk_get_dir_x       ; SI -> the staged entry (SPEC.md 19.1): the
    call COLD_SEG:hbk_bp        ; first cluster is at 18 and NOT at the FAT
    mov ax, [si + 18]           ; record's own 26 (SPEC.md 96.37.1 item 4)
    mov [cs:hbm_dosclus], ax

    ; --- 3. the transport facts, and the extents ----------------------------
    mov al, [cs:hbm_dosrec + KDH_VOL]
    call hbm_geomd              ; hb_unit / hb_spt / hb_heads / hb_base
    jc .b4
    call hbm_xcap               ; a claim big enough for the worst case
    mov bx, MEM_K_HIB
    mov bp, mem_claim_x
    call COLD_SEG:hbk_bp        ; DX = its segment
    jc .b5
    mov [hb_xseg], dx
    ; **ONE RUN COVERS BOTH PARTS** (SPEC.md 96.44.5.4). The core is part 1 and
    ; `kern_dos` is part 2; `os88pkg.py` lays parts out in TABLE ORDER, each
    ; 512-aligned, so the core's packed bytes are immediately followed by
    ; `kern_dos`'s and the extent list wanted is one range from KDH_COFF to the
    ; end of KDH_PLEN. Nothing here knows that adjacency as a fact - it takes
    ; the difference of the two offsets the box posted, so a layout that ever
    ; put something between them would read that something too and still hand
    ; the stub the right two streams.
    mov ax, [cs:hbm_dosrec + KDH_PLEN]  ; the PACKED bytes, as sectors: what
    add ax, 511                         ; the stub reads is the stream and not
    mov cl, 9                           ; what it expands to
    shr ax, cl
    mov cx, [cs:hbm_dosrec + KDH_COFF]  ; CX = sectors to skip: the CORE's
    mov bx, [cs:hbm_dosrec + KDH_POFF]  ; start, which is the lower of the two
    sub bx, cx                          ; BX = the gap to kern_dos's stream...
    add bx, ax                          ; ...plus kern_dos's own sectors
    mov ax, [cs:hbm_dosclus]
    call hbm_extat
    jc .b6

    ; --- 3b. SOMEWHERE TO COME BACK TO (docs/plans/KERN-DOS-PLAN.md 8) ------
    ; Here and not earlier: everything above can still refuse, and an image
    ; written for a handoff that then refuses is a hibernation the user did not
    ; ask for. Here and not later: step 4 takes the screen and shuts the
    ; drivers down, and the write wants the machine it is a picture OF.
    ;
    ; **THE POST IS STILL STANDING WHEN THE PICTURE IS TAKEN**, deliberately:
    ; [hb_dosseg]/[hb_dosoff] are in the image, so the restored kernel knows
    ; whose record to put the exit code in. `hbm_wake` is what spends it over
    ; there; the zero below spends it here.
    ;
    ; A FAILURE IS NOT FATAL. What the user asked for is to run the program
    ; with the whole machine, and that still happens - it is the coming back
    ; that is lost, and `KDLF_HIBER` staying clear is what says so all the way
    ; down to `kd_leave`.
    call COLD_SEG:hb_pick_x     ; is there a fixed disk at all? THE predicate
    jc .noimg                   ; (SPEC.md 87.2), so what greys, what is probed
    mov [hb_vol], al            ; and what is written cannot disagree
    mov al, 1                   ; HBP_DOS = 1: not the user leaving
    call hbm_wrimg
    jc .noimg
    ; **THE RECORD'S COPY AND NOT THE STAGE'S**: the stage is filled at step 5,
    ; below, out of this very record - so a bit set in the staging area here is
    ; a bit `rep movsw` overwrites forty lines later. It read as the whole
    ; return working and `kd_leave` posting nothing, which is a machine that
    ; comes back with no exit code in it.
    or word [cs:hbm_dosrec + KDH_LB + KDL_FLAGS], KDLF_HIBER
    mov word [hb_dosseg], 0     ; the post is spent HERE, and the image has it
    jmp short .staged
.noimg:
    mov word [hb_dosseg], 0
.staged:

    ; --- 4. the panel, the drivers, the lock, text mode - 87.5 step 3's order
    ; The lock and [sch_lock] may already be ours - `hbm_wrimg` takes both and
    ; gives neither back - so this arm cannot simply take them again. **AND
    ; `[sch_lock]` IS NOT THE WAY TO ASK**: `dsk_xfer` raises it around every
    ; `int 13h` and `ui_task` holds it for its own reasons, so a non-zero there
    ; means nothing about whether the image write took it. Testing it skipped
    ; `cw_gfx_lock` on the floppy arm - where nothing had been taken at all -
    ; and the teardown then ran unlocked. A byte this routine sets itself is
    ; the only thing that knows.
    call COLD_SEG:cpf_cp_flush_close
    call COLD_SEG:drv_shutdown_x
    cmp byte [cs:hbm_dosheld], 0
    jne .locked                 ; hbm_wrimg's, still held
    call KERNEL_SEG:cw_gfx_lock
.locked:
    mov bp, vid_reboot
    call KERNEL_SEG:cw_mem_disp

    ; --- 5. the staging area ------------------------------------------------
    call hbm_stageseg           ; ES = the text framebuffer
    push ds
    push cs
    pop ds                      ; ...and DS the module, for the three copies
    mov si, kds_stub            ; that come out of it
    mov di, HS_CODE
    mov cx, kds_stub_end - kds_stub
    rep movsb
    mov si, hbm_dosrec + KDH_PLEN   ; the two lengths, as they lie
    mov di, KDS_PLEN
    mov cx, 4
    rep movsw
    mov si, hbm_dosrec + KDH_CPLEN  ; ...and the CORE's packed length beside
    mov di, KDS_CPLEN               ; them (96.44.5.4). Its UNPACKED length is
    mov cx, 2                       ; not staged: `kds_expand` is unbounded, so
    rep movsw                       ; nothing over there reads one
    mov ax, [cs:hbm_dosrec + KDH_CORG]  ; **`cs:` THOUGH DS IS CS HERE**: the
    mov [es:KDS_CORG], ax               ; module's own data is CS-relative
    mov ax, [cs:hbm_dosrec + KDH_POFF]  ; (SPEC.md 2.8.6) and os88ovlchk reads
    sub ax, [cs:hbm_dosrec + KDH_COFF]  ; the instruction rather than the two
    mov cl, 5                       ; lines of context that make it safe. The
    shl ax, cl                      ; delta is exact: the parts are
                                    ; 512-aligned, so a sector is 32 paragraphs
    mov [es:KDS_CDELTA], ax
    mov si, hbm_dosrec + KDH_LB     ; ...and the launch block, verbatim
    mov di, KDS_LB
    mov cx, KDL_SIZE / 2
    rep movsw
    pop ds
    push bx                     ; **AND THE DRIVE THE ROM IS TO BOOT FROM**,
    mov bl, [dsk_bootvol]       ; which is this machine's and not the
    call COLD_SEG:dskf_dsk_vol_row  ; program's: `int 19h` reads DL as it finds
    jc .nobootu                 ; it (SPEC.md 96.40.2), and A: is an empty
    mov al, [bx+DV_UNIT]        ; drive on every machine that has a hard disk
    xor ah, ah
    mov [es:KDS_LB + KDL_UNIT], ax
.nobootu:
    pop bx
    mov si, dsk_dpt             ; **THE DISKETTE PARAMETER TABLE IS OURS AND NOT
    mov di, KDS_LB + KDL_DPT    ; THE BOX'S**, so the block is patched here
    mov cx, DPT_LEN             ; rather than gathered there: `int 1Eh` names
    rep movsb                   ; KERNEL_SEG:dsk_dpt and kern_dos lands on that
                                ; same segment with its own table at a
                                ; different offset, so without these eleven
                                ; bytes the ROM reads kern_dos's code as an
                                ; EOT and a gap length (SPEC.md 18.92, 96.40.1)
    mov si, hb_unit             ; unit, spt, heads, extents - the stub's order,
    mov di, HS_UNIT             ; and these four are the KERNEL's
    mov cx, 4
    rep movsw
    mov word [es:KDS_TSEG], KDS_TMPSEG  ; where the PACKED stream lands: above
                                        ; the image it expands to, so the two
                                        ; never meet
    push ds
    mov ds, [hb_xseg]           ; the extents
    xor si, si
    mov di, HS_EXT
    mov cx, [es:HS_NX]
    mov ax, cx
    shl cx, 1
    add cx, ax                  ; words: 3 per extent
    rep movsw
    pop ds

    ; --- 6. the VECTORS the ROM is about to need (SPEC.md 96.40.2) ----------
    ; `sched_unhook` is exactly this and cannot be called: it falls into
    ; SPEC.md 18.100's park and the `int 19h` at its tail, so what is wanted is
    ; its BODY and there is no entry for one. Two shim calls and five
    ; instructions is cheaper than factoring it, and every byte here is the
    ; module's rather than the kernel's.
    ;
    ; **INT 09h IS THE ONE THAT MATTERS.** `mouse_init` hooks it for keypad 5
    ; and `hbm_handover` below UNMASKS IRQ1 on the way out, so a key pressed
    ; any time after the handover vectors into kern_dos's image at `kbm_isr`'s
    ; KERNEL offset - which is SPEC.md 9.6.5's hard freeze one segment along,
    ; and `kd_leave` ends on `int 16h`.
    mov bp, mouse_unhook
    call KERNEL_SEG:cw_mem_disp ; int 09h, int 0Ch/0Bh, int 74h, the UARTs
    mov bp, snd_unhook
    call KERNEL_SEG:cw_mem_disp ; 61h bits 0-1 back to their boot state

    ; ...and the PIT, whose divisor is the kernel's fast one (SPEC.md 8.1).
    ; The ROM counts a tick per IRQ0 whatever the rate, so a machine handed
    ; over fast keeps a clock that gains. IF stays 0 from here: `hbm_handover`
    ; opens with `cli` anyway, and closing the window costs nothing.
    cli
    mov al, 0x36
    out 0x43, al
    xor al, al
    out 0x40, al
    out 0x40, al

    ; --- 7. the ROM's int 08h back, the kernel's IRQs masked, and go --------
    jmp hbm_handover            ; 87.5 step 5, factored. A JUMP for the reason
                                ; hbm_res's is one: nothing returns from it
; **A REFUSAL SAYS WHICH STEP, and that is not only for the bring-up.** Six
; things can go wrong before the machine is torn down and they are six
; different repairs: a stale record, a folder that has moved, a DOS.O88 that
; is not there, a volume int 13h cannot reach, no heap for the extent list,
; and a part too fragmented to hand over. `kern_dos could not be reached` is
; true of all six and useful for none, and these strings are MODULE bytes -
; the machine pays nothing for them until it asks.
.b1:
    mov si, hbm_s_d1
    jmp short .bad
.b2:
    mov si, hbm_s_d2
    jmp short .bad
.b3:
    mov si, hbm_s_d3
    jmp short .bad
.b4:
    mov si, hbm_s_d4
    jmp short .bad
.b5:
    mov si, hbm_s_d5
    jmp short .bad
.b6:
    mov si, hbm_s_d6
.bad:
    mov word [hb_dosseg], 0
    call hbm_toast
    mov sp, [hb_sp]
    ret

; -----------------------------------------------------------------------------
; hbm_geomd - the transport facts for a volume kern_dos will be read OFF
; in:  AL = the volume index; that volume is the one standing
; out: as hbm_geom
;
; **A FLOPPY IS THE CASE hbm_geom REFUSES, AND IT IS THIS ONE'S ORDINARY CASE.**
; Hibernate writes an image and can only write it to a fixed disk, so its
; `test dl, 0x80 / jz .no` is right for it; the DOS handoff READS a part of a
; package, and on the machine docs/plans/KERN-DOS-PLAN.md §9 is about - no hard
; disk, so the program runs and the machine reboots - that package is on a
; floppy by definition.
;
; The facts for one are simpler rather than different: the unit is the row's,
; there is no partition so the base is zero, and the geometry is the MOUNTED
; volume's, which is this one because the caller has just stood on it.
; -----------------------------------------------------------------------------
hbm_geomd:
    call hbm_geom
    jnc .out                    ; a fixed disk: hibernate's own answer
    push ax
    push bx
    push dx
    mov bl, al
    call COLD_SEG:dskf_dsk_vol_row  ; BX = the row
    jc .no
    cmp byte [bx+DV_KIND], DVK_BIOS
    jne .no                     ; a DRIVER volume that refused really is one
    mov dl, [bx+DV_UNIT]        ; this machine cannot read without its driver
    test dl, 0x80
    jnz .no                     ; ...and a fixed disk that got here failed
    xor dh, dh                  ; hbm_geom's own range check, not its class one
    mov [hb_unit], dx
    mov word [hb_base], 0       ; a floppy has no partition to be offset into
    mov word [hb_base + 2], 0
    mov dx, [disk_spt]          ; the MOUNTED volume's, which is this one
    mov [hb_spt], dx
    mov dx, [disk_heads]
    mov [hb_heads], dx
    mov ax, [hb_spt]            ; hbm_geom's range check, repeated rather than
    dec ax                      ; shared: 1..63 and 1..255 as one unsigned
    cmp ax, 62                  ; window each, so a zero wraps and is refused
    ja .no
    mov ax, [hb_heads]
    dec ax
    cmp ax, 254
    ja .no
    pop dx
    pop bx
    pop ax
    clc
    ret
.no:
    pop dx
    pop bx
    pop ax
    stc
.out:
    ret

; -----------------------------------------------------------------------------
; hbm_extat - a chain's sectors as extents, with a SKIP and a COUNT
; in:  AX = the first cluster, CX = sectors to skip, BX = sectors to take;
;      [hb_xseg] = where to build
; out: CF=0 and [hb_nx] runs of {dd lba, dw count}; CF=1 the chain ran out
;
; hbm_extents is this with CX = 0 and BX from [mem_top]. THE SKIP IS THE WHOLE
; DIFFERENCE and it is why a part can be handed over at all: the part is a byte
; range of a file (docs/plans/KERN-DOS-PLAN.md §4.1.1), so the walk has to
; arrive at file sector N without reading anything, and N is not a cluster
; boundary. Sector N is the (N mod spc)'th of the (N div spc)'th cluster, which
; is the one place an off-by-one lands in the MIDDLE of the image rather than
; at its edge - tests/kdpart.py does the same arithmetic on the host.
; -----------------------------------------------------------------------------
hbm_extat:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov es, [hb_xseg]
    xor di, di
    mov word [hb_nx], 0
    mov si, ax                  ; SI = the cluster in hand
    mov [cs:hbm_xskip], cx
    mov [cs:hbm_xtake], bx
.clus:
    mov al, [dsk_spc]
    xor ah, ah
    mov dx, ax                  ; DX = this cluster's sectors
    cmp [cs:hbm_xskip], dx
    jb .here                    ; the part starts inside this cluster
    sub [cs:hbm_xskip], dx      ; ...or past it: step over, reading nothing
    jmp short .next
.here:
    mov ax, si
    mov bp, dsk_clus2lba_x
    call COLD_SEG:hbk_bp        ; AX = its first LBA, volume-relative
    jc .bad
    add ax, [cs:hbm_xskip]      ; ...plus however far in the part starts
    sub dx, [cs:hbm_xskip]      ; DX = sectors of this cluster we want
    mov word [cs:hbm_xskip], 0
    xor bx, bx
    add ax, [hb_base]           ; DX:AX would be the absolute LBA, and the
    adc bx, [hb_base + 2]       ; high half is BX because DX is in use
    cmp dx, [cs:hbm_xtake]
    jbe .whole
    mov dx, [cs:hbm_xtake]      ; ...capped at what is left to take
.whole:
    cmp word [hb_nx], 0
    je .new
    cmp ax, [cs:hbm_nextlo]     ; does this cluster follow the run in hand?
    jne .new
    cmp bx, [cs:hbm_nexthi]
    jne .new
    add [es:di-2], dx           ; contiguous: the run grows
    jmp short .grown
.new:
    cmp di, [cs:hbm_xlim]
    jae .bad                    ; more runs than the staging area holds
    mov [es:di], ax
    mov [es:di+2], bx
    mov [es:di+4], dx
    add di, HS_XSTRIDE
    inc word [hb_nx]
.grown:
    add ax, dx
    adc bx, 0
    mov [cs:hbm_nextlo], ax
    mov [cs:hbm_nexthi], bx
    sub [cs:hbm_xtake], dx
    jz .done
.next:
    mov ax, si
    mov bp, dsk_next_clus_x
    call COLD_SEG:hbk_bp        ; AX = the next cluster; CF = outside the
    jc .bad                     ; volume's [2, dsk_maxclus]
    mov si, ax
    jmp .clus                   ; near: hbk_bp made the walk longer
.done:
    clc
    jmp short .out
.bad:
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

hbm_xskip:  dw 0                ; sectors still to step over
hbm_xtake:  dw 0                ; -----------------------------------------------------------------------------
; hbm_handover - SPEC.md 87.5 step 5, and it does not come back
; in:  ES = the staging segment, the stub already copied to HS_CODE
;
; FACTORED because the DOS handoff (96.40) ends exactly here too: the same
; vector, the same three masks, the same far jump spelled as a return. What
; differs between a resume and a handoff is the payload, not the way out.
;
; **IT IS JUMPED TO AND NEVER CALLED.** The `retf` at the foot of it is the
; jump into the stub, not a return, so a near `call` here would read to
; os88ovlchk as 2.6.1's defect - and the reading would be fair: there is
; nothing for a return address to return to.
; -----------------------------------------------------------------------------
hbm_handover:
    cli
    push es
    xor ax, ax
    mov es, ax
    mov ax, [sch_old08]
    mov [es:0x20], ax
    mov ax, [sch_old08 + 2]
    mov [es:0x22], ax
    pop es
    in al, 0x21
    mov [es:HS_MASKM], al
    or al, 0x1A                 ; IRQ 1, 3, 4: the keyboard and the mice
    out 0x21, al
    mov byte [es:HS_SLAVE], 0
    cmp byte [cpu_tier], CPU_8086   ; an XT has no second 8259, and its port
    je .noslave                 ; 0xA0 is the NMI mask register with 0xA1 an
    mov byte [es:HS_SLAVE], 1   ; alias of it - mou_p2_init's refusal (9.9.2)
    in al, 0xA1
    mov [es:HS_MASKS], al
    or al, 0x10                 ; IRQ 12: the auxiliary port
    out 0xA1, al
.noslave:
    push es
    mov ax, HS_CODE
    push ax
    retf                        ; into the stub, IF = 0

; ...and still to place

; hbm_stageseg - out: ES = the text framebuffer the stub will run in
hbm_stageseg:
    push ax
    mov ax, 0xB800
    cmp byte [vid_kind], VID_HERC
    jne .set
    mov ax, 0xB000
.set:
    mov es, ax
    pop ax
    ret

; -----------------------------------------------------------------------------
; hbm_extents - the image's chain as absolute sector runs (SPEC.md 87.5 step 2)
; in:  AX = the first cluster; [hb_xseg] = where to build; the volume mounted
; out: CF = 0 and [hb_nx] runs of {dd lba, dw count, dw 0} at [hb_xseg]:0;
;      CF = 1 the chain is broken or too fragmented
; -----------------------------------------------------------------------------
hbm_extents:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov es, [hb_xseg]
    xor di, di                  ; the next entry
    mov word [hb_nx], 0
    mov si, ax                  ; SI = the cluster in hand
    mov cx, [mem_top]
    mov bl, 5
    xchg cx, bx
    shr bx, cl                  ; BX = sectors the image has: paragraphs / 32
    mov cx, bx                  ; CX = sectors still to place
.clus:
    mov ax, si
    mov bp, dsk_clus2lba_x
    call COLD_SEG:hbk_bp  ; AX = its first LBA, volume-relative
    jc .bad
    xor dx, dx
    add ax, [hb_base]
    adc dx, [hb_base + 2]       ; DX:AX = absolute
    mov bl, [dsk_spc]
    xor bh, bh                  ; BX = this cluster's sectors...
    cmp bx, cx
    jbe .whole
    mov bx, cx                  ; ...capped at what the image still needs
.whole:
    cmp word [hb_nx], 0
    je .new
    cmp ax, [cs:hbm_nextlo]     ; does this cluster follow the run in hand?
    jne .new
    cmp dx, [cs:hbm_nexthi]
    jne .new
    add [es:di-2], bx           ; contiguous: the run grows
    jmp short .grown
.new:
    cmp di, [cs:hbm_xlim]       ; the claim's own end, hbm_xcap's bound
    jae .bad
    mov [es:di], ax
    mov [es:di+2], dx
    mov [es:di+4], bx
    add di, HS_XSTRIDE
    inc word [hb_nx]
    mov [cs:hbm_nextlo], ax
    mov [cs:hbm_nexthi], dx
.grown:
    add [cs:hbm_nextlo], bx
    adc word [cs:hbm_nexthi], 0
    sub cx, bx
    jz .done
    mov ax, si
    mov bp, dsk_next_clus_x
    call COLD_SEG:hbk_bp ; AX = the next
    jc .bad
    mov si, ax
    jmp .clus       ; near: hbk_bp made the walk longer
.done:
    clc
    jmp short .out
.bad:
    stc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

hbm_nextlo: dw 0                ; the LBA the run in hand ends at
hbm_nexthi: dw 0
hbm_xlim:   dw 0                ; ...and the byte the extent list stops at

; -----------------------------------------------------------------------------
; hbm_xcap - the extent list's bound for THIS volume (SPEC.md 87.5 step 2).
;            A run spans at least one cluster, so the image's CLUSTERS bound
;            the runs, and [dsk_spc] - which the walk beside it already reads
;            - is what turns its sectors into them. HS_XMAX stays the ceiling:
;            the staging region is fixed at assembly time and cannot grow.
; in:  the volume mounted
; out: AX = KB to claim; [cs:hbm_xlim] = the walk's byte bound
; -----------------------------------------------------------------------------
hbm_xcap:
    push bx
    push cx
    push dx
    mov bl, [dsk_spc]
    xor bh, bh
    or bx, bx                   ; a BPB that says 0 is not one this can divide
    jz .worst                   ; by: take the assembly-time bound instead
    mov ax, [mem_top]
    mov cl, 5
    shr ax, cl                  ; sectors the image has: paragraphs / 32
    add ax, bx
    dec ax
    xor dx, dx
    div bx                      ; AX = clusters, and so the runs' bound
    cmp ax, HS_XMAX
    jbe .cap
.worst:
    mov ax, HS_XMAX
.cap:
    mov bx, HS_XSTRIDE          ; ...as bytes, for the walk's own stop test
    mul bx
    mov [cs:hbm_xlim], ax
    add ax, 1023                ; ...and as whole KB, for the claim
    mov cl, 10
    shr ax, cl
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; hbm_wake - the restored kernel wakes up here (SPEC.md 87.6)
; in:  CS = this image's segment IN THE RESTORED MEMORY, DS = KERNEL_SEG,
;      SS:SP = hbm_perform's entry frame, IF = 0, the gfx lock held and
;      [sch_lock] up - all of it as the write left it
; out: does not return: it RETURNS THROUGH THE FRAME, into modh_e_perform
; -----------------------------------------------------------------------------
hbm_wake:
    mov ax, LOW_SEG             ; 0. every task stack is in LOW_SEG (SPEC.md
    mov ss, ax                  ;    2.1) and [hb_sp] is the frame
    mov sp, [hb_sp]             ;    hbm_perform banked - both just restored
    sti                         ; 1. the IVT is the image's; nobody switches
    cld
    call hbm_stageseg           ; 2. the clock the boot just read
    mov si, HS_CLK
    mov di, clk_sec
    mov cx, 10
.clk:
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    loop .clk
    mov ax, [ticks]
    mov [clk_last], ax
    mov word [clk_acc], 0
    mov byte [clk_barq], 1
    ; 3. the disk caches are the write's, not the disk's (SPEC.md 87.4) -----
    xor al, al
.drop:
    push ax
    mov bp, dsk_fatw_drop
    call COLD_SEG:hbk_bp
    pop ax
    inc al
    cmp al, DVOL_MAX
    jb .drop
    mov word [dsk_fatd0], 0xFFFF
    mov word [dsk_fatw0], 0xFFFF
    mov byte [dsk_mntok], 0
    mov word [disk_nfiles], 0
    mov byte [dsk_batch], 0
    mov byte [dskw_batch], 0
    mov byte [dskw_syswr], 0
    mov byte [dskw_isdir], 0
    mov bp, dsk_rah_flush
    call COLD_SEG:hbk_bp
    mov word [mem_pinseg], 0    ; dsk_xfer's pin, mid-transfer in the image
    call KERNEL_SEG:fpg_end     ; ...and the progress widget it had up
    ; 4. the desktop, the way fsx_restore gets it back (SPEC.md 53) - before
    ;    any disk work, so the progress widget has a graphics mode to draw in
    mov bp, vid_setmode
    call KERNEL_SEG:cw_mem_disp
    mov byte [hb_mode], HB_M_GONE   ; before the close: app_close_win's hook
    call hbm_win                ; leaves a GONE window's image to the thunk
    jc .nowin                   ; (SPEC.md 87.1), and this code IS the image
    mov bx, si
    mov bp, app_close_win
    call KERNEL_SEG:cw_mem_disp
.nowin:
    mov bp, menu_force
    call KERNEL_SEG:cw_mem_disp
    mov bp, dock_force
    call KERNEL_SEG:cw_mem_disp
    call KERNEL_SEG:cw_wm_paint_all
    ; 5. the two files are spent, and the drivers come back -----------------
    call hbm_forget
    call hbm_reload
    ; 5b. ...and the DOS program's exit code, to the box that asked for it ---
    ; **THIS IS THE ONLY THING THE RETURN ADDS TO THE WAKE**
    ; (docs/plans/KERN-DOS-PLAN.md 8). The staging area is still the one
    ; `hbm_res` filled - step 2 above reads `HS_CLK` out of it - and
    ; `[hb_dosseg]`/`[hb_dosoff]` are the IMAGE's, standing because
    ; `hbm_dosrun` took the picture before it spent the post. So the record the
    ; box posted is exactly where it was, and it gets a number in it.
    ;
    ; The wake is the ordinary one (SPEC.md 74.1): the box already registers a
    ; handler and already services `DST_RAN`, so the way home needed no slot
    ; and no second mechanism.
    call hbm_stageseg
    mov ax, [es:HS_DOSCODE]
    cmp ax, KDH_NOCODE
    je .nodos
    mov bx, [hb_dosseg]
    or bx, bx
    jz .nodos
    mov es, bx
    mov di, [hb_dosoff]
    mov [es:di+KDH_CODE], ax
    mov bx, [es:di+KDH_WIN]
    mov word [hb_dosseg], 0     ; spent HERE, where it was left standing
    or bx, bx
    jz .nodos
    mov bp, wm_wake
    call KERNEL_SEG:cw_mem_disp
.nodos:
    ; 6. and the machine is the user's again --------------------------------
    mov bp, blk_wake
    call KERNEL_SEG:cw_mem_disp
    inc word [hb_resumes]
    call KERNEL_SEG:cw_gfx_unlock
    mov byte [sch_lock], 0      ; NOT a dec: the image holds the count as the
                                ; write left it, and dsk_xfer raises it around
                                ; every int 13h - so it reads 2, and one down
                                ; from that is a machine that never switches
    mov sp, [hb_sp]
    ret

; =============================================================================
; THE STUB (SPEC.md 87.5). Copied to HS_CODE in the text framebuffer and
; entered by a far jump with IF = 0. Position-independent: every jump is
; relative and every datum is at a numeric HS_* offset in its own segment.
; =============================================================================
; =============================================================================
; kds_stub - THE DOS HANDOFF'S STUB (SPEC.md 96.40.1)
; =============================================================================
; It runs with CS, DS and SS in the text framebuffer, on a machine with no
; kernel in it, and does three things: read the part's sectors, expand them
; into `kern_dos`'s segment, and jump.
;
; **IT IS hbs_stub WITH THE HARD PART TAKEN OUT.** A resume reads an image to
; its own linear address and has to put the IVT back LAST, under `cli`, after
; the final `int 13h` - which is the whole of that stub's awkwardness. This
; reads to KD_SEG, which is 0x0060: above the IVT and above the BDA, so
; nothing it writes is anything the ROM is still using and there is no
; special case at all.
;
; What it has that the other does not is a DECODER. The part is `OP_COMP`
; because the 360KB system disk cannot afford it raw
; (docs/reports/KERN-DOS-PART-COST-2026-09-14.md), and the packed stream is
; read to KDS_TMPSEG - a segment ABOVE the image it expands to, so the two
; never meet and the in-place rules of SPEC.md 20.13.7 do not have to be
; reasoned about at all.
; -----------------------------------------------------------------------------
kds_stub:
    mov ax, cs
    mov ds, ax
    mov ss, ax
    mov sp, HS_STACK
    cld
    ; --- 1. the packed stream, one run per int 13h --------------------------
    mov word [HS_K], 0
    mov si, HS_EXT
    mov cx, [HS_NX]
.extent:
    or cx, cx
    jz .expand
    push cx
    mov ax, [si]
    mov [HS_LBA], ax
    mov ax, [si+2]
    mov [HS_LBA+2], ax
    mov ax, [si+4]
    mov [HS_LEFT], ax
.run:
    cmp word [HS_LEFT], 0
    je .nextext
    ; --- CHS of [HS_LBA], hd_chs's one div pair, and the track's remainder --
    mov ax, [HS_LBA+2]
    xor dx, dx
    div word [HS_SPT]
    mov bx, ax
    mov ax, [HS_LBA]
    div word [HS_SPT]           ; DX = sector - 1
    mov cx, [HS_SPT]
    sub cx, dx                  ; CX = sectors to the end of the track
    mov [HS_N], cx
    inc dx
    push dx
    mov dx, bx
    div word [HS_HEADS]         ; AX = cylinder, DX = head
    pop bx                      ; BL = the sector
    mov dh, dl
    mov dl, [HS_UNIT]
    mov ch, al
    mov cl, ah
    ror cl, 1
    ror cl, 1
    and cl, 0xC0
    or cl, bl
    mov [HS_CHS], cx
    mov [HS_CHS+2], dx
    ; --- the run: to the track's end, the extent's end, the DMA page --------
    mov cx, [HS_N]
    cmp cx, [HS_LEFT]
    jbe .cap1
    mov cx, [HS_LEFT]
.cap1:
    mov bx, [HS_K]
    push cx
    mov cl, 5
    shl bx, cl                  ; the destination, k * 32 paragraphs...
    add bx, [KDS_TSEG]          ; ...above the packed stream's base
    mov ax, bx
    and ax, 0x0FFF
    neg ax
    add ax, 0x1000              ; paragraphs to the 64KB page's end...
    shr ax, cl                  ; ...in sectors
    pop cx
    cmp cx, ax
    jbe .go
    mov cx, ax
.go:
    mov [HS_N], cx
    mov es, bx
    xor bx, bx
    mov di, 3                   ; tries
.try:
    mov ax, [HS_N]
    mov ah, 0x02
    mov cx, [HS_CHS]
    mov dx, [HS_CHS+2]
    sti                         ; the ROM wants its interrupts on an AT
    int 0x13
    jnc .ok
    xor ah, ah
    mov dl, [HS_UNIT]
    int 0x13                    ; reset, and again
    dec di
    jnz .try
    jmp .fail
.ok:
    mov ax, [HS_N]
    add [HS_K], ax
    add [HS_LBA], ax
    adc word [HS_LBA+2], 0
    sub [HS_LEFT], ax
    jmp .run
.nextext:
    add si, HS_XSTRIDE
    pop cx
    dec cx
    jmp .extent

    ; --- 2. expand it into kern_dos's own segment ---------------------------
.expand:
    cli
    mov al, [HS_MASKM]          ; the PIC masks go back BEFORE the expansion:
    out 0x21, al                ; it is the longest thing this stub does and a
    cmp byte [HS_SLAVE], 0      ; machine with the timer masted through it
    je .noslave                 ; would lose ticks the ROM counts
    mov al, [HS_MASKS]
    out 0xA1, al
.noslave:
    sti
    ; **KERN_DOS FIRST, AND THE ORDER IS THE WHOLE OF IT** (SPEC.md 96.44.5.4).
    ; `kern_dos`'s image carries a HOLE where the core goes - `times CORE_MAX +
    ; CORE_BSS_SIZE db 0`, which is what reserves the core's address space in
    ; the host that does not contain it - so expanding kern_dos SECOND writes
    ; those zeros straight over the core that had just arrived, and the machine
    ; jumps into a table of `jmp near 0`. The other order costs nothing at all:
    ; neither stream is read twice and neither lands anywhere different.
    mov ax, KD_SEG
    mov es, ax
    mov cx, [KDS_PLEN]          ; ONE BLOCK EACH, because os88pkg.py caps a
    mov ax, [KDS_TSEG]          ; part at 64KB (SPEC.md 20.12)
    add ax, [KDS_CDELTA]        ; ...and kern_dos's stream begins that many
    push ds                     ; paragraphs into the run the extents brought
    mov ds, ax                  ; in, the core's occupying the front of it
    xor si, si
    call kds_expand             ; DS:SI -> ES:0, CX packed bytes
    pop ds
    ; --- ...and then the core, into the hole kern_dos just left -------------
    mov ax, [KDS_CORG]          ; CORE_ORG, which is 512-aligned, so the shift
    mov cl, 4                   ; is exact and there is no intra-paragraph
    shr ax, cl                  ; remainder for kds_expand's DI to carry
    add ax, KD_SEG
    mov es, ax
    mov cx, [KDS_CPLEN]
    push ds
    mov ds, [cs:KDS_TSEG]       ; the core's stream IS the run's own base
    xor si, si
    call kds_expand
    pop ds

    ; --- 3. the launch block, into the image that just arrived --------------
    ; kern_dos's first eight bytes are a fixed header (kerndos/kdlayout.inc):
    ; a near jump and a word saying where the block goes. The stub has no
    ; symbol table, which is why that word is there.
    mov ax, KD_SEG
    mov es, ax
    mov di, [es:KD_H_LBP]
    mov cx, [es:KD_H_LBSZ]
    shr cx, 1
    mov si, KDS_LB
    push ds
    push cs
    pop ds
    rep movsw
    pop ds
    jmp KD_SEG:0x0000           ; ...and away. Its header jumps to the entry

.fail:
    mov ah, 0x02                ; the cursor to row 8 first, hbs_stub's reason:
    xor bh, bh                  ; rows 0-2 of this page ARE the stub
    mov dx, 0x0800
    int 0x10
    mov si, kds_s_fail - kds_stub
.ch:
    mov al, [si]
    or al, al
    jz .key
    mov ah, 0x0E
    mov bx, 0x0007
    int 0x10
    inc si
    jmp short .ch
.key:
    xor ah, ah
    int 0x16
    int 0x19
    jmp $

; --- kds_expand: one LZ4 stream, kernel/lz.inc's lz_lz4 with no bounds -------
; in:  DS:SI = the stream, T WORD FIRST; ES = where it expands to, DI free;
;      CX = the stream's PACKED bytes
;
; **THE STREAM IS NOT A CLASSIC LZ4 BLOCK AND THIS IS THE THIRD READER OF THE
; ONE THAT SHIPS** (SPEC.md 20.13.7): a T word, then the symbols cut at the
; first peak of (produced - consumed), then T bytes of RAW TAIL that go across
; as they are. `os88lz.py` writes it, `kernel/lz.inc` reads it, and this reads
; it again because the kernel is gone by the time this runs. A classic decoder
; on one of these streams does not fail - it reads the T word AS A TOKEN, and
; `05 00` is "copy nine bytes from 0xFC00 back", so the image lands NINE BYTES
; along with the header still holding whatever was there before. That is what
; it did, and the machine jumped into it.
;
; UNBOUNDED, for kz_expand's reason one file along: what it produces is the
; thing that is about to be jumped into, and a bound cannot make a wrong
; expansion safe. What can is that tests/kdpart.py has already checked, on the
; host, that these exact sectors expand to these exact bytes.
;
; The two bounds live in the STAGE's own scratch rather than in registers -
; `HS_LBA` and `HS_LEFT` are the disk walk's and it has finished - and they are
; read through `cs:` because the match copy below owns DS.
kds_expand:
    xor di, di
    add cx, si                  ; the stream's end...
    mov ax, [si]
    add si, 2                   ; ...past the T word
    sub cx, ax                  ; ...and so where the raw tail begins: the ONLY
    mov [cs:HS_LBA], cx         ; source bound the loop tests
    mov [cs:HS_LEFT], ax        ; ...and how much of it there is
.seq:
    cmp si, [cs:HS_LBA]
    jae .tail
    mov al, [si]                ; the token: literal length in the high nibble,
    inc si                      ; match length - 4 in the low one.
    mov bl, al                  ; **THE STRING FORM IS REFUSED IN A MODULE
                                ; IMAGE** (SPEC.md 2.8.6): a module's own data
                                ; is CS-relative and os88ovlchk cannot see that
                                ; this body is COPIED OUT of the module before
                                ; it runs. Two bytes a site, and hbs_stub reads
                                ; its own string the same way
    mov cl, 4
    shr al, cl
    xor ah, ah
    mov cx, ax
    cmp al, 15
    jne .lits
.lx:
    mov al, [si]
    inc si
    xor ah, ah
    add cx, ax
    cmp al, 255
    je .lx
.lits:
    rep movsb                   ; CX = 0 is legal and moves nothing
    cmp si, [cs:HS_LBA]
    jae .tail                   ; the symbols never end on a literal run in
                                ; this format - the tail is what ends it
    mov ax, [si]                ; the match offset
    add si, 2
    mov bp, ax
    mov al, bl
    and al, 0x0F
    xor ah, ah
    mov cx, ax
    cmp al, 15
    jne .mat
.mx:
    mov al, [si]
    inc si
    xor ah, ah
    add cx, ax
    cmp al, 255
    je .mx
.mat:
    add cx, 4                   ; the minimum match, which the token omits
    push ds
    push si
    mov si, di
    sub si, bp
    push es
    pop ds                      ; a match reads what we have already written
    rep movsb
    pop si
    pop ds
    jmp short .seq
.tail:
    mov cx, [cs:HS_LEFT]        ; SI is standing on it
    rep movsb
    ret

kds_s_fail: db 13, 10, 'kern_dos could not be read off the disk.', 13, 10
            db 'Press any key to restart.', 13, 10, 0
kds_stub_end:
%if kds_stub_end - kds_stub > HS_CODE_MAX
  %error "hiber: the DOS handoff stub is bigger than its staging slot"
%endif

hbs_stub:
    mov ax, cs
    mov ds, ax
    mov ss, ax
    mov sp, HS_STACK
    cld
    mov word [HS_K], 0
    mov si, HS_EXT
    mov cx, [HS_NX]
.extent:
    or cx, cx
    jnz .have
    jmp .done
.have:
    push cx
    mov ax, [si]
    mov [HS_LBA], ax
    mov ax, [si+2]
    mov [HS_LBA+2], ax
    mov ax, [si+4]
    mov [HS_LEFT], ax
.run:
    cmp word [HS_LEFT], 0
    je .nextext
    ; --- CHS of [HS_LBA] (hd_chs's one div pair), and the track's remainder --
    mov ax, [HS_LBA+2]
    xor dx, dx
    div word [HS_SPT]
    mov bx, ax                  ; BX:AX = track after the second div...
    mov ax, [HS_LBA]
    div word [HS_SPT]           ; ...and DX = sector - 1
    mov cx, [HS_SPT]
    sub cx, dx                  ; CX = sectors from this one to the track end
    mov [HS_N], cx
    inc dx
    push dx                     ; the sector, 1-based
    mov dx, bx
    div word [HS_HEADS]         ; AX = cylinder, DX = head
    pop bx                      ; BL = the sector
    mov dh, dl                  ; DH = head
    mov dl, [HS_UNIT]           ; DL = drive
    mov ch, al                  ; CH = cylinder low 8, CL = sector | high 2
    mov cl, ah
    ror cl, 1
    ror cl, 1
    and cl, 0xC0
    or cl, bl
    mov [HS_CHS], cx
    mov [HS_CHS+2], dx
    ; --- the run: to the track's end, the extent's end, the DMA page ---------
    mov cx, [HS_N]
    cmp cx, [HS_LEFT]
    jbe .cap1
    mov cx, [HS_LEFT]
.cap1:
    mov bx, [HS_K]
    cmp bx, 3
    jae .high
    mov cx, 1                   ; file sectors 0..2 go to 0060:0000, singly
    mov bx, 0x0060
    jmp short .go
.high:
    push cx
    mov cl, 5
    shl bx, cl                  ; ES = k * 32: linear k * 512
    mov ax, bx
    and ax, 0x0FFF
    neg ax
    add ax, 0x1000              ; paragraphs to the 64KB page's end...
    shr ax, cl                  ; ...in sectors
    pop cx
    cmp cx, ax
    jbe .go
    mov cx, ax
.go:
    mov [HS_N], cx
    mov es, bx
    xor bx, bx
    mov di, 3                   ; tries
.try:
    mov ax, [HS_N]
    mov ah, 0x02
    mov cx, [HS_CHS]
    mov dx, [HS_CHS+2]
    sti                         ; the ROM wants its interrupts on an AT
    int 0x13
    jnc .ok
    xor ah, ah
    mov dl, [HS_UNIT]
    int 0x13                    ; reset, and again
    dec di
    jnz .try
    jmp short .fail
.ok:
    mov bx, [HS_K]
    cmp bx, 2
    jae .advance
    ; --- file sector 0 or 1: the IVT, into the staging area for later -------
    push ds
    push si
    mov cl, 9
    shl bx, cl
    add bx, HS_IVT
    mov di, bx
    mov ax, cs
    mov es, ax
    mov ax, 0x0060
    mov ds, ax
    xor si, si
    mov cx, 256
    rep movsw
    pop si
    pop ds
.advance:
    mov ax, [HS_N]
    add [HS_K], ax
    add [HS_LBA], ax
    adc word [HS_LBA+2], 0
    sub [HS_LEFT], ax
    jmp .run
.nextext:
    add si, HS_XSTRIDE
    pop cx
    dec cx
    jmp .extent
.done:
    cli                         ; --- the IVT goes back last, under cli ------
    xor ax, ax
    mov es, ax
    xor di, di
    mov si, HS_IVT
    mov cx, 512
    rep movsw
    mov al, [HS_MASKM]
    out 0x21, al
    cmp byte [HS_SLAVE], 0
    je .noslave
    mov al, [HS_MASKS]
    out 0xA1, al
.noslave:
    mov ax, KERNEL_SEG
    mov ds, ax                  ; ...and NOT SS:SP - hbm_wake builds its own
    jmp far [cs:HS_WAKE]        ; out of the memory it has just put back
.fail:
    mov ah, 0x02                ; the cursor to row 8 first: rows 0-2 of this
    xor bh, bh                  ; page ARE the stub, and the ROM's teletype
    mov dx, 0x0800              ; writes at the cursor the mode set homed. Row
    int 0x10                    ; 8 is the IVT copy, dead on this path, and
    mov si, hbs_s_fail - hbs_stub   ; three lines from there never scroll
.ch:
    mov al, [si]
    or al, al
    jz .key
    mov ah, 0x0E
    mov bx, 0x0007
    int 0x10
    inc si
    jmp short .ch
.key:
    xor ah, ah
    int 0x16
    int 0x19
    jmp $
hbs_s_fail: db 13, 10, 'Resume failed: the disk could not be read.', 13, 10
            db 'Press any key to restart.', 13, 10, 0
hbs_stub_end:
%if hbs_stub_end - hbs_stub > HS_CODE_MAX
  %error "hiber: the resume stub is bigger than its staging slot"
%endif

; =============================================================================
; The image's own data (SPEC.md 2.8.6): strings read through CS, and the
; pointer's buffer, which dskw_write and dskw_read reach as ES:BX.
; =============================================================================
; --- the DOS handoff's record, copied out of the poster's segment ------------
; MODULE DATA and not kernel bss: 543 bytes that only exist while the module
; is resident, which is the whole economy of osapi_dos_handoff_x keeping a far
; POINTER (SPEC.md 96.40).
hbm_dosrec:     times KDH_SIZE db 0
hbm_dosclus:    dw 0            ; DOS.O88's first cluster, across hbm_geom
hbm_dosflag:    db 0            ; what HBP_DOS is to say, across hbm_wrimg
hbm_dosheld:    db 0            ; 1 = hbm_wrimg took the gfx lock and [sch_lock]
                                ; and still holds them, so step 4 must not
hbm_s_d1:       db 'The handoff record is not one of ours', 0
hbm_s_d2:       db 'The folder DOS.O88 was in has moved', 0
hbm_s_d3:       db 'DOS.O88 is not on that disk any more', 0
hbm_s_d4:       db 'That disk is not one the ROM can read', 0
hbm_s_d5:       db 'No room to list where kern_dos is', 0
hbm_s_d6:       db 'kern_dos is too scattered to hand over', 0

hbm_ptrfix:     db 'HIB1'      ; the pointer's fixed head, described ONCE
                dw BUILD_NUM
                dw MOD_STAMP
                dw 0            ; [mem_top], filled by hbm_ptrfix_set
                db 0, 0         ; ...[vid_kind], and the pad
hbm_ptrbuf:     times HBP_SIZE db 0

hbm_lines_ask:  dw hbm_s_a1, hbm_s_a2, hbm_s_a3, 0
hbm_lines_busy: dw hbm_s_b1, 0
hbm_lines_res:  dw hbm_s_r1, hbm_s_r2, hbm_s_r3, 0

hbm_s_a1:   db 'Save everything in memory to', 0
hbm_s_a2:   db 'C:\HIBERNAT.IMG and stop the machine?'
HBM_A2_LTR  equ 0
            db 0
hbm_s_a3:   db 'Restarting offers to resume it.', 0
hbm_s_b1:   db 'Hibernating...', 0
hbm_s_r1:   db 'A hibernation file is on drive '
HBM_R1_LTR  equ $ - hbm_s_r1
            db 'C:.', 0        ; 34 cells: the content is 39 wide
hbm_s_r2:   db 'Resume where you left off, or', 0
hbm_s_r3:   db 'discard it and start normally?', 0

hbm_s_bhib: db 'Hibernate', 0
hbm_s_bcan: db 'Cancel', 0
hbm_s_bres: db 'Resume', 0
hbm_s_bdis: db 'Discard', 0

hbm_s_nobios: db 'Hibernate needs a BIOS-known hard disk', 0
hbm_s_noroom: db 'Not enough room for the hibernation file', 0
hbm_s_failed: db 'Hibernate failed', 0
hbm_s_stale:  db 'Hibernation file is from another build', 0
hbm_s_lost:   db 'Hibernation file could not be read', 0

hbm_s_off:  db 13, 10, 'os8088 has hibernated.', 13, 10, 13, 10
            db 'It is now safe to switch the machine off.', 13, 10
            db 'Press any key to restart it.', 13, 10, 0

%endif                          ; --- kern_small has NO hibernate at all,
                                ; and so no module and no mod_tab row

section .text                   ; every module ends where the next include
                                ; expects to begin (SPEC.md 1)
