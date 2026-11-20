/* Just enough of a browser to run frontend/runtime/player.mjs under bare node.
 *
 * The player is a module singleton that builds its own DOM, so each test is
 * its own node process: this file is imported first, sets up the globals the
 * player reaches for, and hands back the things a test pokes -- the elements
 * made, the timers set, the YouTube players constructed.
 *
 * This is a test fixture. Nothing in the application imports it.
 */
export const made = [];        // every element created, in order
export const timers = [];      // [fn, ms] for every setTimeout, never run unless a test runs it
export const youtube = [];     // every YT.Player constructed

class El {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.listeners = {};
    this.attrs = {};
    const classes = new Set();
    this.classList = {
      add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c),
    };
    if (tag === "video") Object.assign(this, { paused: true, ended: false, currentTime: 0, duration: NaN });
    made.push(this);
  }
  addEventListener(ev, fn) { (this.listeners[ev] ??= []).push(fn); }
  fire(ev, more = {}) { for (const fn of this.listeners[ev] ?? []) fn({ type: ev, ...more }); }
  append(...kids) { this.children.push(...kids); }
  appendChild(kid) { this.children.push(kid); return kid; }
  replaceChildren(...kids) { this.children = kids; }
  setAttribute(k, v) { this.attrs[k] = v; }
  removeAttribute(k) { delete this.attrs[k]; if (k === "src") delete this.src; }
  blur() { this.blurred = (this.blurred ?? 0) + 1; if (document.activeElement === this) document.activeElement = null; }
  contains(el) { return el === this || this.children.some(c => c.contains?.(el)); }
  // A <video>'s own.
  play() { this.paused = false; this.fire("play"); return Promise.resolve(); }
  pause() { this.paused = true; this.fire("pause"); }
  load() { this.loads = (this.loads ?? 0) + 1; }
}

export const head = new El("head");
export const box = new El("div");
made.length = 0;

globalThis.document = { createElement: tag => new El(tag), head, activeElement: null };
/* The window's own listeners (blur: the YouTube frame took the keyboard). */
export const winListeners = {};
globalThis.window = { addEventListener: (ev, fn) => (winListeners[ev] ??= []).push(fn) };
export function windowFires(ev, more = {}) { for (const fn of winListeners[ev] ?? []) fn({ type: ev, ...more }); }
globalThis.location = { origin: "http://viewer.test" };
globalThis.setTimeout = (fn, ms) => { timers.push([fn, ms]); return timers.length; };
globalThis.clearTimeout = () => {};
globalThis.YT = {
  Player: class {
    constructor(slot, options) {
      Object.assign(this, { slot, options, calls: [], state: -1, time: 0 });
      youtube.push(this);
    }
    seekTo(t) { this.calls.push(["seekTo", t]); this.time = t; }
    playVideo() { this.calls.push(["playVideo"]); this.state = 1; }
    pauseVideo() { this.calls.push(["pauseVideo"]); this.state = 2; }
    getCurrentTime() { return this.time; }
    getPlayerState() { return this.state; }
    isMuted() { return this.muted ?? true; }
    mute() { this.calls.push(["mute"]); this.muted = true; }
    unMute() { this.calls.push(["unMute"]); this.muted = false; }
  },
};

export const the = tag => made.find(e => e.tagName === tag.toUpperCase());
export const all = tag => made.filter(e => e.tagName === tag.toUpperCase());
/* YouTube's script arriving and its player coming ready. */
export function youtubeReady() {
  window.onYouTubeIframeAPIReady();
  youtube.at(-1).options.events.onReady();
  return youtube.at(-1);
}
