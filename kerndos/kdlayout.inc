; =============================================================================
; kerndos/kdlayout.inc - the segment ladder
;
; kern_dos sits at the bottom of conventional memory and everything above it
; is the DOS program's, which is the whole point (docs/plans/KERN-DOS-PLAN.md
; its §1: ~39 KB for all of this against a 600 KB target).
;
; THE LADDER IS THE KERNEL'S SHAPE WITH THE MIDDLE TAKEN OUT: image, then the
; FAT snapshot, then the mount buffers, and no cold rung and no task stacks
; because there is no boot overlay and no scheduler (KERN-DOS-PLAN §4.2).  The kernel
; derives each rung from the section it follows; here the image rung is
; DECLARED and asserted at the foot of kerndos.asm, because a two-pass
; derivation buys nothing when there is one arm to size.
; =============================================================================
KD_SEG      equ 0x0060          ; linear 0x00600, above the IVT and the BDA
KERNEL_SEG  equ KD_SEG          ; ...and the kernel's own files call it this

KD_IMG_KB   equ 60              ; the image rung: every progbits section PLUS
KIMG_PARA   equ KD_IMG_KB * 64  ; the bss, rounded up to whole KB and asserted
                                ; at the foot of each root.  IT HAS TO CLEAR
                                ; THE WHOLE THING and not just `.text`: FAT_SEG
                                ; sits on top of it, so a rung short by a
                                ; kilobyte puts the FAT snapshot INSIDE the
                                ; code and the mount overwrites what called it.
                                ; At wave 4 kdos.asm measures .text 32,425 +
                                ; .cold 11,397 + .ovlw 762 + .modf 1,235 =
                                ; 45,827 of image and 12,316 of `.bss` above
                                ; it, so 58,144 all in and 60KB is the rung
                                ; that holds it.  **BOTH HALVES COST A ROUND
                                ; OF DEBUGGING**: 40 cleared neither and 56
                                ; cleared the image and missed the bss by 800
                                ; bytes, which ran anyway
COLD_SEG    equ KD_SEG          ; NO COLD RUNG: nothing here is boot-only, so
COLD_PARA   equ 0               ; .cold is ordinary code in the one image

FAT_SEG     equ KD_SEG + KIMG_PARA        ; the mount-time FAT snapshot
FAT_PARA    equ DSK_FAT_SECS * 32         ; 512 bytes = 32 paragraphs
LOW_SEG     equ FAT_SEG + FAT_PARA        ; ...and the mount buffers above it


KD_LOW_KB   equ 8               ; how much .lowbss the layer's buffers want
                                ; (3,328 today) PLUS the stack above them,
                                ; asserted in kerndos.asm
KD_STACK    equ KD_LOW_KB * 1024 ; ...and the stack sits at the top of it and
                                ; grows DOWN toward the buffers

; The top of the DOS program's memory, in paragraphs. 0x9000 is 576KB: below
; the adapters' own RAM on every machine this can boot, and where wave 4 stops
; asking - KERN-DOS-PLAN §1's 600KB is what the REAL entry negotiates, and it
; has a machine handed to it rather than a floppy to boot from.
KD_ARENA_TOP equ 0x9000
