; =============================================================================
; os8088 - apps/dos/doscore.asm
;
; **THE DOS CORE, ON ITS OWN** (SPEC.md 96.44; the design record is
; docs/plans/KERN-DOS-PLAN.md 4.1.3): INT 21h and everything under it - the PSP, the handle layer, the
; FCBs, the MCB chain, `AH=4Bh` and the built-in commands - assembled once,
; with no host around it.
;
; **IT IS THE SAME FILE, BEHIND TWO DEFINES, AND NOT A COPY.** `apps/dos/dos.asm`
; carries three populations now and each is marked where it stands:
;
;   %ifndef KD_BACKEND   the WINDOW half (96.43.2) - what `kern_dos` leaves out
;   %ifndef DOS_EXTCORE  the CORE (96.44) - what a HOST leaves out
;   everything else      the container: the package header, the constants, the
;                        DBSS table, the bss equates and the includes at the
;                        foot, which every build wants
;
; so this root is `KD_BACKEND` with no host, and a host is `DOS_EXTCORE` with
; no core.  Nothing was moved to make that true, which is the whole reason the
; split is checkable: `build/dos.o88` was byte-identical through the marking.
;
; WHAT IT NAMES OUTSIDE ITSELF IS THREE THINGS, and that is the measurement
; docs/plans/KERN-DOS-PLAN.md wanted (*"core -> box is ZERO"*):
;
;   os88_image_end   where the DBSS table is based.  A CONSTANT here, because
;                    the core's bss is at a fixed offset both hosts agree on
;   DVOL_MAX         how many volumes the machine can have (96.38)
;   dos_bevec        the twenty-two back-end doors AS ADDRESSES (96.44.1),
;                    filled by whichever host is running - the one edge that
;                    exists, and it is the door table this plan already built
;
; **NOTHING IS EMITTED FOR A HOST TO CALL YET.** This root exists so the
; marking is CHECKED rather than asserted: a span marked core that is really
; the container, or a core routine that still names a host symbol, fails here
; and nowhere else.  The entry table and `org CORE_ORG` are the next wave's.
; =============================================================================
cpu 8086
bits 16

%define KD_BACKEND                  ; ...so the window half is not in this one
%define DOS_CORE_ROOT               ; ...and the container knows it has no host

; --- what the host would otherwise have said --------------------------------
; Both are CONSTANTS to the core and neither is code: `DVOL_MAX` is the
; kernel's own (`assoc.inc` defines it first in every real build, which is why
; dos.asm's copy is `%ifndef`'d), and `os88_image_end` is where the DBSS table
; is based - a LABEL in the package and a fixed offset here, because the core's
; bss has to be at the same place whichever host it is joined to.
%ifndef DVOL_MAX
DVOL_MAX equ 8
%endif
%ifndef CORE_BSS
CORE_BSS equ 0x8000                 ; provisional - the budget is the next
%endif                              ; wave's (docs/plans/KERN-DOS-PLAN.md §4.1.3.1)
os88_image_end equ CORE_BSS

%include "dos.asm"
