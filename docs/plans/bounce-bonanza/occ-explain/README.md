# Occlusion explained (2026-11-17, for the owner's question)

Scratch scripts, NOT build inputs; nothing in `make` runs them. They made the two
pictures beside this folder:

- `../occ-why-peak-fall.png` (`diag.py` then `pics.py`): the PEAK back-edge fall of
  `occ-fall-peak.png`, with each pixel coloured by its depth against the ball. The
  ball rolls off the back of floor (24, 18) into the void (23, 18), directly behind
  the tall wall block (21 - 23, 19 - 21) at height 54 (`cells.py`): the wall face
  with the exit mouth is that block's FRONT face, so today's records are right.
- `../occ-storage-methods.png` (`methods.py`): one patch of PEAK as the picture, the
  per-pixel depth buffer the tool builds (`sbuf`/`tbuf`), today's records (only the
  blocks a reachable ball can be behind, one colour a record), and a 2-bit 4x4
  per-block-palette map.
- `sizes.py`: the RAM each storage method needs on every course (MEASURED on the
  host at 28f4859dd; the 4x4 column leaves out the per-block column byte and the
  row index, about +nocc + 2 (BROWS + 1)).

Run from the repository root: `python3 docs/plans/bounce-bonanza/occ-explain/diag.py`
writes `peakfall.pkl` in this folder, which `pics.py` reads.
