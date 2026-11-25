# KITE HILL's clock CONCEPTS (course 5; the brief is the course guide's G23, ../../mill/clocks/frames.py the
# precedent, ../../clockkit.py the kit that compiles and draws them).  One object a concept, a variant a clock:
# the course's four clocks are the MEADOW (start), the FAN PLAZA, the LAUNCH PLAZA and the SUMMIT, and what
# changes between them says how far up the hill the player is.  Drawn in the course's inks BY INDEX - KITE is
# `palette 0`, so ink 1 (CYN) is GREEN, ink 2 (MAG) RED and ink 3 (WHT) YELLOW; on the Hercules green and red are
# one grey checker and yellow is white, so every form is carried by yellow and black as well.
#
#   sock   A WINDSOCK on a pole, the digits on its first band; the wind fills it up the hill: limp at the meadow,
#          half out at the fan plaza, straight out at the launch plaza, taut and fluttering on the summit.
#          THE OWNER'S PICK (2026-11-25) and the course's: tools/bbcourse.py's `sock1` .. `sock4` (`_clock_sock`,
#          SPEC.md 130.18.5.2) - named here, drawn there.
#   kite   A KITE on its string, the digits on its sail; its TAIL grows a bow a clock (1, 2, 3, then a full
#          streaming tail of 5) and it leans the way the course goes next.  Not picked for this course, kept in
#          the tool: `kite1` .. `kite4` (`_clock_kite`).
CONCEPTS = {
    "kite": [("kite1", "digits 0 -16"), ("kite2", "digits 0 -16"), ("kite3", "digits 0 -16"),
             ("kite4", "digits 0 -16")],
    "sock": [("sock1", ""), ("sock2", ""), ("sock3", ""), ("sock4", "")],
}
BASE = "sock"


DRAW = {}                                             # (both concepts are the tool's own frames now)
