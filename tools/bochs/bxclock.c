/* bxclock.c - an LD_PRELOAD for bochs-bin: a STOPPED Bochs costs the guest
 * no time (docs/BOCHS.md, *The clock*).
 *
 * `clock: sync=slowdown` makes Bochs's guest time its instruction count and
 * caps it at real time by comparing against time(NULL) - Bochs 2.7's
 * iodev/slowdown_timer.cc, its only reader of time() once `time0=` is given.
 * That reference is the WALL clock, so host seconds spent stopped at the
 * debugger prompt (a memory read, a screenshot, a breakpoint) put the guest
 * behind it, and on the resume the timer stops sleeping until the guest has
 * caught up: up to a guest second run flat out, ~25x real time here. Every
 * harness interval measured in host time after a stop - an input gap, a
 * status poll, the lag of a reading - then holds a burst of guest time, and
 * how much depends on how long the stops took, i.e. on host load.
 *
 * This replaces time() with a clock that does not move while Bochs does not
 * run. The slowdown timer is a guest timer firing every guest millisecond,
 * so a RUNNING Bochs calls time() every host millisecond or less; a gap of
 * more than OS88_BXCLOCK_GAP_MS (default 50) between two calls is a stop -
 * the debugger's prompt, a SIGSTOP, a host stall - and is taken out of the
 * clock whole, less the one millisecond a call is expected to take. Nothing
 * else changes: the guest's own clock is still the instruction count, and
 * the cap at real time still holds against the time Bochs actually ran.
 *
 * MartyPC has this property by construction (a stopped core is a stopped
 * machine), and every row shimmed onto Bochs by tools/os88megabochs.py
 * assumes it. Measured on a loaded box (docs/BOCHS.md): half a host second
 * of running after a 2 s stop held 2.4-2.6 guest seconds without this and
 * 0.59-0.61 with it, against 0.42-0.45 with no stop at all.
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdlib.h>
#include <time.h>

static int64_t bx_base_real, bx_base_mono, bx_last, bx_off, bx_gap = -1;

static int64_t bx_ns(clockid_t c)
{
    struct timespec t;
    clock_gettime(c, &t);
    return (int64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}

time_t time(time_t *tp)
{
    int64_t now = bx_ns(CLOCK_MONOTONIC), v;
    time_t r;
    if (bx_gap < 0) {
        const char *g = getenv("OS88_BXCLOCK_GAP_MS");
        bx_gap = (g && *g ? atoll(g) : 50) * 1000000;
        bx_base_real = bx_ns(CLOCK_REALTIME);
        bx_base_mono = bx_last = now;
    } else if (now - bx_last > bx_gap) {
        bx_off += now - bx_last - 1000000;
    }
    bx_last = now;
    v = bx_base_real + (now - bx_base_mono) - bx_off;
    r = (time_t)(v / 1000000000);
    if (tp)
        *tp = r;
    return r;
}
