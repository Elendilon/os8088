; kernel/cpwfmt.inc - CPWIDE.DAT's layout (SPEC.md 135.6, 135.7).
;
; Shared by the wide Control Panel (kernel/cpw*.inc, assembled into
; CPWIDE.DRV) and checked by tools/cpwdat.py, which builds the assets from
; kernel/cpwart/*.png and drivers/catalog.toml - build/cpwdat.bin, which
; cpwide.inc assembles into the module's image - and refuses to write them if
; they disagree with these numbers. Constants only: no code, no data, no
; section.

; ---- header -----------------------------------------------------------------
CWD_MAGIC    equ 'CW'          ; +0  dw, reads 'C','W'
CWD_VERSION  equ 2           ; 2: 16x16 slots, 44-byte records (dsp2)
CWD_H_MAGIC  equ 0             ; dw  'CW'
CWD_H_VER    equ 2             ; db  CWD_VERSION
CWD_H_N16    equ 3             ; db  16x16 icon count
CWD_H_N32    equ 4             ; db  32x32 icon count
CWD_H_NCAT   equ 5             ; db  catalog records
CWD_H_OFF16  equ 6             ; dw  offset of the 16x16 block
CWD_H_OFF32  equ 8             ; dw  offset of the 32x32 block
CWD_H_OFFCAT equ 10            ; dw  offset of the catalog
CWD_H_SIZE   equ 12            ; dw  the file's length
CWD_H_STR    equ 14            ; dw  offset of the description string block
CWD_HDR      equ 16

; ---- icons ------------------------------------------------------------------
; 4bpp packed, high nibble leftmost (SPEC.md 5.4), then the mask: one bit a
; pixel, bit 15 of each word the leftmost, 1 = opaque. A transparent pixel's
; nibble is 0 and the drawer substitutes the ground colour. (Pixels first and
; masks after, rather than a mask word before each sixteen pixels: that read
; with one lodsw a group, and packed 310 bytes worse - driver size pass 2.)
CWD_I16_PIX  equ 128           ; 16 rows x 8 bytes
CWD_I16_STR  equ 8             ; stride
CWD_I16_SZ   equ 160           ; + 16 mask words
CWD_I32_PIX  equ 512           ; 32 rows x 16 bytes
CWD_I32_STR  equ 16
CWD_I32_SZ   equ 640           ; + 32 rows x 2 mask words (left word first)

; 16x16 SLOTS of the 16x16 block. The sheet (kernel/cpwart/cp-icons-16.png,
; row-major) has CWD_S16_N cells, and six of its category cells are pixel for
; pixel a page icon - Display, Sound, Storage, Input, Memory and System are
; the Display, Sound, Hard disk, Mouse, Memory and gear pages' own - so the
; block stores each DISTINCT cell once, in sheet order (driver size pass 2,
; -960 bytes): those six names are the first cell's slot, and the cells after
; them move up. The `; cell N` after each name is its cell on the sheet, and
; tools/cpwdat.py refuses a file where a name's slot does not hold that cell -
; so a sheet edited into a new duplicate, or out of one, is a build error
CWD_S16_N    equ 32            ; cells on the sheet
CWI16_SCHED  equ 0             ; cell 0
CWI16_TIME   equ 1             ; cell 1
CWI16_KEYB   equ 2             ; cell 2
CWI16_FLOPPY equ 3             ; cell 3
CWI16_DRV    equ 4             ; cell 4
CWI16_DISP   equ 5             ; cell 5
CWI16_SOUND  equ 6             ; cell 6
CWI16_THEME  equ 7             ; cell 7
CWI16_DOCK   equ 8             ; cell 8
CWI16_HDD    equ 9             ; cell 9
CWI16_NET    equ 10            ; cell 10
CWI16_DEBUG  equ 11            ; cell 11
CWI16_GEAR   equ 12            ; cell 12
CWI16_MOUSE  equ 13            ; cell 13
CWI16_MEM    equ 14            ; cell 14
CWI16_PORTS  equ 15            ; cell 15
CWI16_C_DISP equ CWI16_DISP    ; cell 16 - the driver categories and the
CWI16_C_SND  equ CWI16_SOUND   ; cell 17   status marks
CWI16_C_STOR equ CWI16_HDD     ; cell 18
CWI16_C_CD   equ 16            ; cell 19
CWI16_C_RAMD equ 17            ; cell 20
CWI16_C_NET  equ 18            ; cell 21
CWI16_C_INP  equ CWI16_MOUSE   ; cell 22
CWI16_C_MEM  equ CWI16_MEM     ; cell 23
CWI16_C_SYS  equ CWI16_GEAR    ; cell 24
CWI16_C_SAVR equ 19            ; cell 25
CWI16_C_USB  equ 20            ; cell 26
CWI16_C_VM   equ 21            ; cell 27
CWI16_C_UNK  equ 22            ; cell 28
CWI16_OK     equ 23            ; cell 29 (OK, ERR, WARN in this order: the
CWI16_ERR    equ 24            ; cell 30  badge adds CPK_OK..CPK_WARN)
CWI16_WARN   equ 25            ; cell 31
CWI16_N      equ 26            ; slots: the sheet's distinct cells

; 32x32 indices = cells of kernel/cpwart/cp-icons-32.png
CWI32_SCHED  equ 0
CWI32_TIME   equ 1
CWI32_KEYB   equ 2
CWI32_FLOPPY equ 3
CWI32_DRV    equ 4
CWI32_DISP   equ 5
CWI32_SOUND  equ 6
CWI32_THEME  equ 7
CWI32_DOCK   equ 8
CWI32_HDD    equ 9
CWI32_NET    equ 10
CWI32_GEAR   equ 11
CWI32_N      equ 12

; ---- the blocks' offsets, fixed by the counts --------------------------------
; The header carries them too (tools/cpwdat.py refuses a file where the two
; differ), but the code is assembled WITH the assets now (SPEC.md 135.6), so
; it reads them as constants and never through the header
CWD_OFF16    equ CWD_HDR
CWD_OFF32    equ CWD_OFF16 + CWI16_N * CWD_I16_SZ
CWD_OFFCAT   equ CWD_OFF32 + CWI32_N * CWD_I32_SZ

; ---- the driver catalog (SPEC.md 135.7) -------------------------------------
CWD_CAT_SZ   equ 44            ; one fixed record per driver FILE (64 with
                               ; 20 reserved bytes until driver size pass
                               ; 2: the reader is assembled with the
                               ; writer's numbers now, so a field is added
                               ; by growing the record, and none is held)
CWD_C_FILE   equ 0             ; db [12]  8.3 name, NUL-padded: the key
CWD_C_CAT    equ 12            ; db       CWC_*
CWD_C_ICON   equ 13            ; db       16x16 slot (CWI16_*)
CWD_C_LONG   equ 14            ; db [26]  long name, NUL-terminated, <= 25
CWD_C_D1     equ 40            ; dw       offset (from file start) of line 1
CWD_C_D2     equ 42            ; dw       ...line 2 (0 = none)
CWD_DESC_MAX equ 46            ; a description line, characters, NUL-terminated

CWC_UNK      equ 0
CWC_DISP     equ 1
CWC_SOUND    equ 2
CWC_STOR     equ 3
CWC_NET      equ 4
CWC_INPUT    equ 5
CWC_MEM      equ 6
CWC_SYS      equ 7
CWC_N        equ 8
