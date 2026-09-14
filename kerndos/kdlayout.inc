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

KD_IMG_KB   equ 61              ; the image rung: every progbits section PLUS
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
                                ; bytes, which ran anyway.
                                ;
                                ; **THIS IS NOT A RUNG AND IT IS NOT FREE.**
                                ; `LOW_SEG` sits on it and the arena sits on
                                ; that, so a KB here is a KB OFF THE DOS
                                ; PROGRAM - the one quantity
                                ; docs/plans/KERN-DOS-PLAN.md 1 is a budget
                                ; for. So it is raised to the smallest whole
                                ; KB that fits and never to a round one: 60 ->
                                ; 61 at wave 5, the image having measured
                                ; 61,482 (SPEC.md 96.40.2's refusal table is
                                ; 1,432 of it and 96.30.7's console the rest),
                                ; which leaves 982 bytes and costs the program
                                ; 560 -> 559 KB
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

; The top of the DOS program's memory is the MACHINE's, and it arrives in the
; launch block rather than being a constant here: `KDL_CAP` is the BDA's own
; KB, which is what `int 12h` answers and what a real DOS uses. Wave 4's gate
; asked 0x9000 (576KB) on the reasoning that it was below the adapters' RAM on
; anything this can boot; the BDA says 640 on those same machines, which is
; 60KB the arithmetic was throwing away.
KD_CAP_MAX  equ 640             ; KB. The clamp, not the answer: 640 * 64 is
                                ; 0xA000 paragraphs and the last figure that
                                ; fits the `shl` in 16 bits, and an 8086 has
                                ; nowhere above it to put a .COM anyway

; --- where the stub leaves the launch block (docs/plans/KERN-DOS-PLAN.md §7 step 7) ---
; The image's first bytes are a FIXED HEADER, because the stub has no symbol
; table: a near jump to the entry, then a word saying where to put the block.
; Putting the block itself here would cost 512 bytes of the part on disk for
; every machine that never uses them; a pointer costs four and lets it live in
; `.bss`, which is nobits.
KD_H_JMP    equ 0               ; 3: `jmp kd_entry`
KD_H_LBP    equ 4               ; dw: where the block goes
KD_H_LBSZ   equ 6               ; dw: ...and how many bytes of it there are
