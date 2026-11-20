/* The game's video as a file the page plays itself, in place of the YouTube
 * player, where whoever served the page offers one in window.VIDEO:
 *
 *   { src, video_id, offset_s }
 *
 * `curling-score serve` offers the cached download's indexed copy
 * (viewer/localvideo.py). Nothing else sets it, and a page without it plays
 * YouTube exactly as before -- the hosted service and the published site
 * among them.
 *
 * `offset_s` is where the file's first frame sits on the stream's clock, the
 * clock every time in a timeline is on. It is 0 for a file of the whole
 * stream; a file cut down to its game would say where the cut was.
 *
 * Plain ESM with no React and no DOM; see tests/test_viewer_js.py. */

/* How far short of a moment a file may fall and still be this game's video.
 * A rock's lead-in can reach a little past either end of a trimmed file;
 * a file an hour short is not the video the chart was made from. */
export const SHORT_BY_S = 60;

/* The file to play for `videoId`: { src, offset }, or null for YouTube. An
 * offer that names another video is refused -- the wrong game's pictures under
 * this game's chart would be worse than YouTube's overlay. */
export function ownVideo(offer, videoId) {
  if (!offer || typeof offer !== "object") return null;
  const { src, video_id: of, offset_s: offset } = offer;
  if (typeof src !== "string" || !src) return null;
  if (of != null && of !== videoId) return null;
  return { src, offset: typeof offset === "number" && Number.isFinite(offset) ? offset : 0 };
}

/* A moment on the stream's clock, as a position in the file. */
export function fileTime(t, offset) {
  return Math.max(0, t - offset);
}

/* Whether a file of this duration holds the moment `t`, near enough. A
 * duration not yet known (NaN, or Infinity for a file still growing) is given
 * the benefit of the doubt. Safari reads a download that was never indexed as
 * its first two seconds and reports no error: this is what notices. */
export function reaches(duration, t, offset) {
  if (typeof duration !== "number" || !Number.isFinite(duration)) return true;
  return t - offset <= duration + SHORT_BY_S;
}

/* 1:02:05, or 2:05 inside the first hour: a position in a two-hour stream. */
export function videoClock(seconds) {
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) return "–:––";
  const t = Math.max(0, Math.floor(seconds));
  const h = Math.floor(t / 3600), m = Math.floor(t / 60) % 60, s = t % 60;
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}
