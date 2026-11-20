/* The YouTube player, deliberately outside React.
 *
 * `YT.Player` replaces the element it is given with a cross-origin iframe and
 * talks to it over postMessage. It cannot be React state, and it must never be
 * recreated: the phone layout hides the video behind the house editor's opaque
 * background rather than unmounting it, precisely because a remount costs the
 * player and the seek. So this is a module singleton with an idempotent
 * mount() -- which also makes it safe under StrictMode's double effect.
 *
 * `#player` is created here rather than rendered by React. If React held a
 * vdom child for that slot, one reconciliation of #video's children would
 * remove the iframe YT put there; with no children in the vdom there is
 * nothing to reconcile, permanently.
 *
 * The page's own <video> lives here too, behind the same six functions.
 * YouTube draws its title, its clock and its logo over the picture after every
 * jump and for as long as it is paused, and an embedding page cannot stop it;
 * a file played by the browser has nothing drawn on it but what this module
 * draws. So where the page was offered the game's video as a file
 * (core/video.mjs) that is what mounts, and YouTube is what it falls back to
 * -- at the same moment, without a word on the page -- if the file will not
 * play.
 */
import { fileTime, reaches, videoClock } from "../core/video.mjs";

let player = null;           // the YT.Player, or "none" once it has failed
let ready = false;
let pending = null;          // a seek asked for before the player could take it: {t, autoplay}
let container = null;
let own = null;              // the page's own <video>, while it is the one playing: {el, offset, giveUp}

/* Written into #video rather than rendered by React. `.fallback` is styled
 * `height:100%` to fill the video box, and React must own no children there:
 * YT.Player replaces the element it is given with an iframe, so one
 * reconciliation of #video's children would take the player with it. */
function fail(why) {
  if (player) return;
  player = "none";
  if (!container) return;
  const box = document.createElement("div");
  box.className = "fallback";
  box.textContent = `Video cannot be embedded here (${why}).`;
  box.appendChild(document.createElement("br"));
  box.append("Use the YouTube link beside each shot.");
  container.replaceChildren(box);
}

export function mount(el, videoId, { autoplay = () => true, file = null } = {}) {
  if (player || own || !el) return;          // already mounted, or already failed
  container = el;
  if (file) mountFile(el, file, autoplay, () => mountYouTube(el, videoId, autoplay));
  else mountYouTube(el, videoId, autoplay);
}

function mountYouTube(el, videoId, autoplay) {
  const slot = document.createElement("div");
  slot.id = "player";
  el.appendChild(slot);

  window.onYouTubeIframeAPIReady = () => {
    player = new YT.Player("player", {
      videoId,
      // Muted until the watcher turns the sound on in the player's own
      // controls: the stream's sound is a rink's worth of other people's
      // talk, the chart is read with the picture, and a muted player is
      // one every browser lets start on its own ("play on jump").
      playerVars: { rel: 0, playsinline: 1, modestbranding: 1, mute: 1, origin: location.origin },
      events: {
        onReady: () => {
          ready = true;
          if (pending !== null) {
            const { t, autoplay: play } = pending;
            pending = null;
            seek(t, play ?? autoplay());
          }
        },
        onError: e => fail(`player error ${e.data}`),
      },
    });
  };

  const s = document.createElement("script");
  s.src = "https://www.youtube.com/iframe_api";
  s.onerror = () => fail("script blocked");
  document.head.appendChild(s);
  setTimeout(() => { if (!player) fail("timed out"); }, 8000);
}

/* The game's video as a file, in a <video> of the page's own. `youtube` mounts
 * the other player, for when this one has to be given up. */
function mountFile(el, file, autoplay, youtube) {
  const v = document.createElement("video");
  // Muted for the reason the YouTube player is, and so that "play on jump"
  // may start it; inline, or a phone takes it full screen on play. Only what
  // a seek needs is fetched ahead: the file is a gigabyte or four.
  v.muted = true;
  v.playsInline = true;
  v.preload = "metadata";

  /* Back to YouTube, at the moment the file was at or was being asked for,
   * playing only if it was. Nothing is said on the page: the file was a
   * convenience, and the player the page has always had is still there. */
  const giveUp = at => {
    if (!own) return;
    const where = at ?? (ready ? { t: v.currentTime + file.offset, autoplay: !v.paused } : pending);
    own = null;
    ready = false;
    pending = where;
    v.removeAttribute("src");
    v.load();                                // let go of the file
    el.replaceChildren();
    youtube();
  };
  own = { el: v, offset: file.offset, giveUp };

  v.addEventListener("error", () => giveUp());
  v.addEventListener("loadedmetadata", () => {
    ready = true;
    if (pending !== null) {
      const { t, autoplay: play } = pending;
      pending = null;
      seek(t, play ?? autoplay());
    }
  });
  v.addEventListener("click", togglePlay);
  el.append(v, controlBar(el, v, file.offset));
  v.src = file.src;
}

/* How long the controls stay after the pointer last moved over the picture. */
const BAR_LINGER_MS = 2500;

/* The file's controls: play, a scrubber, the time and full screen, along the
 * bottom of the picture -- and only while the pointer is moving over it. A
 * browser's built-in controls stay up for as long as a video is paused, which
 * is the overlay this player exists to be rid of. These never show because of
 * a jump or a pause, so stepping through rocks from the keyboard leaves the
 * frame bare, with the pointer resting on it or not. */
function controlBar(box, v, offset) {
  const make = (tag, cls) => Object.assign(document.createElement(tag), { className: cls });
  const bar = make("div", "vbar");
  const play = make("button", "vplay");
  const scrub = make("input", "vscrub");
  const time = make("span", "vtime");
  const full = make("button", "vfull");
  play.type = full.type = "button";
  scrub.type = "range";
  scrub.min = "0";
  scrub.max = "0";
  scrub.value = "0";
  scrub.tabIndex = -1;                       // the keys are the page's: arrows step rocks
  scrub.setAttribute("aria-label", "Position in the video");
  full.textContent = "⛶";
  full.title = "Full screen";

  let dragging = false;
  const paint = () => {
    play.textContent = v.paused ? "▶" : "❚❚";
    play.title = v.paused ? "Play (p)" : "Pause (p)";
    if (Number.isFinite(v.duration)) scrub.max = String(Math.floor(v.duration));
    if (!dragging) scrub.value = String(v.currentTime);
    time.textContent = `${videoClock(v.currentTime + offset)} / ${videoClock(v.duration + offset)}`;
  };
  for (const ev of ["play", "pause", "durationchange", "timeupdate", "seeked"])
    v.addEventListener(ev, paint);
  paint();

  play.addEventListener("click", togglePlay);
  scrub.addEventListener("input", () => { dragging = true; v.currentTime = Number(scrub.value); });
  // Let go of the keyboard with the mouse: a focused slider takes the arrow
  // keys, and the next press should step a rock, not nudge the video.
  scrub.addEventListener("change", () => { dragging = false; scrub.blur(); });
  full.addEventListener("click", () => {
    const on = document.fullscreenElement ?? document.webkitFullscreenElement;
    const done = on ? (document.exitFullscreen ?? document.webkitExitFullscreen)?.call(document)
                    : (box.requestFullscreen ?? box.webkitRequestFullscreen)?.call(box);
    done?.catch?.(() => {});                 // refused (an embedded pane): nothing to do about it
  });

  let timer = null, at = null;
  const hide = () => {
    clearTimeout(timer);
    if (dragging) timer = setTimeout(hide, BAR_LINGER_MS);
    else bar.classList.remove("on");
  };
  const show = e => {
    // A browser re-sends the pointer's position when the page under it
    // changes, as it does on every step: only a pointer that has gone from
    // one place to another counts as moving.
    const was = at;
    at = `${e.clientX},${e.clientY}`;
    if (e.type === "pointermove" && (was === null || was === at)) return;
    bar.classList.add("on");
    clearTimeout(timer);
    timer = setTimeout(hide, BAR_LINGER_MS);
  };
  box.addEventListener("pointermove", show);
  box.addEventListener("pointerdown", show);
  // A mouse that has gone takes them with it. A finger "leaves" the moment it
  // lifts, and has to be able to come back down on a button: there they wait
  // out their time.
  box.addEventListener("pointerleave", e => { if (e.pointerType !== "touch") hide(); });

  bar.append(play, scrub, time, full);
  return bar;
}

export function seek(t, autoplay) {
  if (player === "none") return;
  // Queued with the caller's own autoplay: a rock restored from a link or the
  // session seeks before the iframe is ready and asks not to start playing,
  // which the "play on jump" preference must not override.
  if (!ready) { pending = { t, autoplay }; return; }
  if (own) {
    // A file that stops far short of the moment asked for is not this game's
    // video, whatever it loaded as: YouTube takes the seek instead.
    if (!reaches(own.el.duration, t, own.offset)) { own.giveUp({ t, autoplay }); return; }
    own.el.currentTime = fileTime(t, own.offset);
    if (autoplay) own.el.play()?.catch(() => {});
    return;
  }
  player.seekTo(t, true);
  if (autoplay) player.playVideo();
}

/* Where the playhead is, for a list that follows along. Guarded exactly as
 * seek() is: before the iframe answers, and after it has failed, there is no
 * time to report -- and null says so rather than 0, which is a real position
 * and would drag a following list back to the top of the end. */
export function currentTime() {
  if (own) return ready ? own.el.currentTime + own.offset : null;
  if (!player || player === "none" || !ready) return null;
  const t = player.getCurrentTime();
  return typeof t === "number" && Number.isFinite(t) ? t : null;
}

/* Whether it is actually playing. A paused video should not pull the list
 * around under a thumb that stopped it deliberately. */
export function isPlaying() {
  if (own) return ready && !own.el.paused && !own.el.ended;
  if (!player || player === "none" || !ready) return false;
  return player.getPlayerState() === 1;
}

export function pause() {
  if (own) { if (ready) own.el.pause(); return; }
  if (!player || player === "none" || !ready) return;
  player.pauseVideo();
}

export function togglePlay() {
  if (own) {
    if (!ready) return;
    if (own.el.paused) own.el.play()?.catch(() => {});
    else own.el.pause();
    return;
  }
  if (!player || player === "none" || !ready) return;
  player.getPlayerState() === 1 ? player.pauseVideo() : player.playVideo();
}
