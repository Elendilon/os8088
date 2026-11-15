#!/bin/sh
# the SKIP AUDITION's knob build, into build/sk/ (never build/): run from the worktree's root
set -e
mkdir -p build/sk/src
cp apps/bonanza/*.asm apps/bonanza/*.inc build/sk/src/
{ echo '%define BZS_SKIPTEST'; cat apps/bonanza/bonanza.asm; } > build/sk/src/bonanza.asm
nasm -f bin -w+error -DBZS_SKIPTEST -I apps/ -I apps/bonanza/ -I build/bonanza-art/ -l build/sk/bonanza.lst -o build/sk/bonanza.bin apps/bonanza/bonanza.asm
A=build/bonanza-art
PARTS=""
for p in BZBALR BZBALS BZBALG BZ0 BZ1 BZ2 BZ3 BZ4 BZ5 BZ6 BZSND BZM0 BZM1 BZM2 BZM3 BZM4 BZM5 BZD1 BZD2 BZD3 BZD4 BZD5 BZD6; do PARTS="$PARTS --part $A/$p.BIN"; done
python3 tools/os88pkg.py --compress-if=lz4 build/sk/bonanza.bin -o build/sk/bonanza.o88 $PARTS --part-compress lzb > /dev/null
python3 tools/os88disk.py -o build/sk/bonanza360.img --size 360 build/sk/bonanza.o88 build/zdata-lz4/bonanza/README.md --folder SYSTEM/APPDATA
