; =============================================================================
; hfpkg.inc - HTTPFS.DRV's package door (SPEC.md 120.4), behind OSAPI_DRV_CALL
;
; Included by the driver and by any package that mounts an address itself - an
; installer pointing the drive at a release, a test. The netpkg.inc/cdpkg.inc
; shape (SPEC.md 20.11): the verbs are the DRIVER's ABI, not the kernel's.
;
;       mov  bh, DRVC_HTTP
;       mov  bl, HFV_MOUNT
;       mov  si, my_url             ; ES:SI - the X stub makes ES your DS
;       call OSAPI_DRV_CALL
;       jc   .no                    ; AX = an HFE_* below
;
; **UI TASK ONLY, EVERY VERB**: MOUNT adds a volume and FETCH waits on the
; network with the machine's file layer in hand, neither of which SPEC.md 20.6
; rule 7 lets a worker near.
; =============================================================================

HFV_IDENT    equ PKGV_IDENT     ; = 0. -> AX = HF_SIG, CX = HF_ABI. ASK FIRST
HFV_STATE    equ 1              ; -> AL = the volume index (0FFh = none),
                                ;    AH = HFS_*, CX = records in the index
                                ;    (0 = none fetched), DX = the last HTTP
                                ;    status (0 = none yet), SI = the last
                                ;    HFE_* (0 = none)
HFV_MOUNT    equ 2              ; ES:SI = a NUL address, http://host[:port]/
                                ;    [prefix/] -> CF=0, AL = the volume index.
                                ;    LAZY: nothing is fetched until the drive
                                ;    is opened. A drive already mounted is
                                ;    re-pointed, its index dropped
HFV_UNMOUNT  equ 3              ; -> CF=0; the volume and the index go back
HFV_FETCH    equ 4              ; fetch the index NOW -> CF=0, CX = records;
                                ;    CF=1, AX = an HFE_*. So a caller learns
                                ;    whether the server answers before it
                                ;    shows anything
HFV_MAX      equ 4

HF_SIG       equ 'HF'
HF_ABI       equ 1

HFS_IDLE     equ 0              ; no address, or not mounted
HFS_LAZY     equ 1              ; mounted, nothing fetched yet
HFS_READY    equ 2              ; the index is held
HFS_FAILED   equ 3              ; the last fetch of the index failed

; --- what CF=1 means, in AX ---------------------------------------------------
HFE_NODRV    equ 0              ; the kernel's own: no DRVC_HTTP driver
HFE_URL      equ 1              ; the address is not http://host[:port]/...
HFE_NONET    equ 2              ; no socket driver, or it has no link
HFE_CONNECT  equ 3              ; the server refused, or the name did not
                                ;    resolve, or the connection broke
HFE_TIMEOUT  equ 4              ; nothing arrived for HF_IDLE ticks
HFE_STATUS   equ 5              ; an HTTP status other than 200/206 (DX has it)
HFE_INDEX    equ 6              ; OS88.IDX is not an index HTTPFS.DRV accepts
HFE_SHORT    equ 7              ; a body that ended before its length, or a
                                ;    length that is not the index's
HFE_MEM      equ 8              ; no heap for the index
HFE_VOL      equ 9              ; no free drive letter
HFE_ARG      equ 10             ; a verb this driver does not have
