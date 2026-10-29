/* pmhost_audio.cpp - the I2S DAC's driver (audio_i2s.c on the iron).
 *
 * The firmware's mixer (pm_audio.cpp, dev_audiomix.cpp) fills buffers and
 * hands them to audio_i2s.c, whose DMA plays them out of a PIO state
 * machine. Wave 0 needs the mixer to link and nothing more; wave 2 makes
 * this the end that pm_audio() pulls samples from.
 *
 * GPL-2.0-or-later, like the firmware it is compiled into.
 */
#include "pmhost_pico.h"
#include "audio_i2s.h"

static bool enabled;
bool audio_i2s_setup(const audio_i2s_config_t *config) { (void)config; return true; }
void audio_i2s_set_enabled(bool e) { enabled = e; }
