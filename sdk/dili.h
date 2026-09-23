#ifndef DILI_H
#define DILI_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Experimental IS500/Beta 0547:c004 SDK. Calls on one handle must be serialized.
 * 1280x960 or 2592x1944, 8-bit raw sensor data. RGGB layout derived from the legacy driver; color accuracy uncalibrated.
 * Exposure is in sensor lines, NOT milliseconds. No automatic exposure or WB.
 * All functions return zero on success; errors are negative. */
typedef struct dili_camera dili_camera;
/* Legacy constants/start remain the 1280x960 preview mode for compatibility. */
enum { DILI_WIDTH=1280, DILI_HEIGHT=960, DILI_FRAME_BYTES=1280*960,
       DILI_FULL_WIDTH=2592, DILI_FULL_HEIGHT=1944, DILI_FULL_FRAME_BYTES=2592*1944 };
enum { DILI_MODE_PREVIEW=0, DILI_MODE_FULL=1 };
enum { DILI_NOT_FOUND=-100, DILI_MULTIPLE=-101, DILI_UNSUPPORTED=-102,
       DILI_STATE=-103, DILI_ARGUMENT=-104, DILI_BAD_FRAME=-105, DILI_WB_REFERENCE=-106 };
const char *dili_error(int code);
int dili_open(dili_camera **out);
int dili_start(dili_camera *camera, unsigned exposure_lines, unsigned gain);
/* Select mode while stopped. Stop/start to change resolution. Exposure stays in
 * sensor lines; line duration differs by mode. No implicit exposure conversion. */
int dili_start_mode(dili_camera *camera, unsigned mode, unsigned exposure_lines, unsigned gain);
int dili_get_frame_size(dili_camera *camera, unsigned *width, unsigned *height);
/* Reads one valid frame, with a bulk-read budget of timeout_ms (100..30000).
 * Control acknowledgments/cleanup have separate 2-second timeouts.
 * Rejects short transfers and startup-marker buffers; acknowledges complete
 * frames before returning. A transport error stops acquisition. Retry by start.
 * pixels must hold width*height bytes from dili_get_frame_size(). No partial image is returned. */
int dili_read(dili_camera *camera, uint8_t *pixels, size_t length, unsigned timeout_ms);
/* Settings follow the old driver's limits: exposure 1..3000, gain 1..70.
 * Next two frames are discarded to allow queued acquisition to settle. */
int dili_set_exposure_lines(dili_camera *camera, unsigned value);
int dili_set_gain(dili_camera *camera, unsigned value);
/* Pure software RGGB bilinear reconstruction, preserving full dimensions.
 * Raw and RGB buffers must not overlap. RGB is tightly packed R,G,B, 8 bits each.
 * Gains are R,G,B multipliers in [0.125,8]; unity leaves channel levels unchanged.
 * No gamma, black subtraction, color matrix or automatic contrast is applied. */
int dili_rgb8(const uint8_t *raw, size_t raw_size, unsigned width, unsigned height,
              const double gains[3], uint8_t *rgb, size_t rgb_size);
/* One-shot balance from a view filled with a neutral grey/white reference.
 * Does not establish color accuracy or channel order from a neutral target.
 * Rejects references with fewer than 64 usable unsaturated Bayer cells. */
int dili_white_balance(const uint8_t *raw, size_t raw_size, unsigned width, unsigned height, double gains[3]);
int dili_stop(dili_camera *camera);
void dili_close(dili_camera *camera);
#ifdef __cplusplus
}
#endif
#endif
