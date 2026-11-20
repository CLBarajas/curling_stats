"""Serve the local charting viewer, and take back what the charter enters.

The page is static; the one thing the server does beyond handing out files is
accept ``overrides.json``. Corrections are written to that file rather than
into ``timeline.json`` so that re-running the analysis never destroys them --
``analyze`` layers the same file back over the fresh detection.

One more thing since 2026-11: where the game's video is in the cache, the
server hands the page a file of it a byte range at a time, and the page plays
that in a ``<video>`` of its own rather than in YouTube's player, which draws
over the picture after every jump. Which file, and why: ``localvideo``.
"""

import functools
import io
import json
import http.server
import os
import shutil
import tempfile
import threading
import urllib.parse
import webbrowser
from pathlib import Path

from curling_score.viewer import localvideo
from curling_score.viewer.localvideo import LocalVideo

HERE = Path(__file__).parent
ASSETS = ("index.html", "app.js", "style.css", "source-sans-3.woff2",
          "source-sans-3.OFL.txt")

# The comment in index.html that the hosted service replaces with the page's
# configuration. A comment rather than the script tag: a tag is markup a tool
# might legitimately reshape, and this substitution failing is silent in the
# worst direction -- a view-only link that boots editable, or a review link
# that tries to save.
BOOT_ANCHOR = "<!--CHART-->"
OVERRIDES = "overrides.json"
# A whole game's charting is a few hundred small patches; a game with every
# stone placed by hand measures around 300 KB, so this is already generous.
# The hosted side keeps the same figure for a different reason: past 1 MiB
# Firestore refuses the document outright.
MAX_BODY_BYTES = 700_000


class ViewerHandler(http.server.SimpleHTTPRequestHandler):
    """Static files, plus a POST that saves the charter's corrections."""

    _lock = threading.Lock()

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802  (stdlib naming)
        # The server binds to loopback, but a POST writes to disk, so it says
        # so itself rather than relying on how it happened to be started.
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            return self._json(403, {"ok": False, "error": "loopback only"})
        if self.path.rstrip("/").lstrip("/") != OVERRIDES:
            return self._json(404, {"ok": False, "error": "unknown path"})

        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self._json(400, {"ok": False, "error": "no length"})
        if not 0 < length <= MAX_BODY_BYTES:
            return self._json(400, {"ok": False, "error": "bad length"})

        try:
            data = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            return self._json(400, {"ok": False, "error": f"invalid JSON: {err}"})
        if not isinstance(data, dict) or not all(
            isinstance(v, dict) for v in data.values()
        ):
            return self._json(400, {"ok": False, "error": "expected {key: patch}"})

        try:
            self._write(data)
        except OSError as err:
            return self._json(500, {"ok": False, "error": str(err)})
        return self._json(200, {"ok": True, "shots": len(data)})

    def _write(self, data: dict) -> None:
        """Replace overrides.json in one step.

        Written to a temporary file and renamed, so a save interrupted halfway
        leaves the previous corrections intact rather than a truncated file.
        """
        directory = Path(self.directory)
        with self._lock:
            fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(data, f, indent=2, sort_keys=True)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, directory / OVERRIDES)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise

    def do_GET(self):  # noqa: N802  (stdlib naming)
        # A video element drops the request it no longer wants every time it
        # seeks. That is not an error, and not worth a traceback each.
        try:
            super().do_GET()
        except ConnectionError:
            self.close_connection = True

    def _send_video(self, video: LocalVideo):
        """The video file, or the part of it asked for. Returns what the stock
        handler should copy to the socket, like ``send_head``; None once the
        answer has no body left to send."""
        try:
            f = open(video.path, "rb")
        except OSError:
            # Gone since start-up (the cache was cleared): the page's video
            # element reports it and the page goes back to YouTube.
            self.send_error(404, "the video is not in the cache")
            return None
        try:
            stat = os.fstat(f.fileno())
            size = stat.st_size
            # The game is in the address; this only has to tell a copy written
            # again from the one a browser already holds part of.
            etag = f'"{size:x}-{stat.st_mtime_ns:x}"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.end_headers()
                f.close()
                return None
            wanted = self.headers.get("Range")
            if self.headers.get("If-Range") not in (None, etag):
                wanted = None         # a range of some other file: send this one whole
            try:
                span = localvideo.byte_range(wanted, size)
            except localvideo.RangeNotSatisfiable:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                f.close()
                return None
            start, end = span or (0, size - 1)
            self.send_response(206 if span else 200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if span:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("ETag", etag)
            self.end_headers()
            f.seek(start)
            return localvideo.Slice(f, end - start + 1)
        except BaseException:
            f.close()
            raise

    def _send_page(self, video: LocalVideo):
        """index.html, told where its video is. Built per request and never
        written to the run's folder: a copy of that folder served by anything
        else must not ask for a video that server does not have."""
        body = boot_page(video=video).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        return io.BytesIO(body)

    def send_head(self):
        video = getattr(self.server, "video", None)
        if video is not None:
            route = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path).lstrip("/")
            if route == video.url:
                return self._send_video(video)
            if route in ("", "index.html"):
                return self._send_page(video)
        # "Not modified" only for the very file the browser holds. The stock
        # handler answers 304 whenever its file is no newer than the copy the
        # browser has -- right for one file that changes, wrong for a port
        # pointed at another run: an older run's timeline.json is "not
        # modified since" a newer run's, and the browser went on showing the
        # game it had (sheet D, with sheet A being served).
        since = self.headers.get("If-Modified-Since")
        if since is not None:
            path = self.translate_path(self.path)
            if os.path.isdir(path):
                path = os.path.join(path, "index.html")
            try:
                same = since.strip() == self.date_time_string(int(os.stat(path).st_mtime))
            except OSError:
                same = False
            if not same:
                del self.headers["If-Modified-Since"]
        return super().send_head()

    def end_headers(self):
        # Every file is asked for again each time, answered 304 where it has
        # not changed: without this a browser keeps `timeline.json` and
        # `app.js` on its own guess (a tenth of the file's age), so a port
        # pointed at a newer run, or a rebuilt viewer, shows the old one.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):  # quieter: one line per request is noise
        if self.command == "POST":
            super().log_message(fmt, *args)


def boot_page(config: dict | None = None, video: LocalVideo | None = None) -> str:
    """index.html with ``window.CHART`` injected, or as-is for the local server.

    ``config`` is what tells the page whether this link edits, views or
    reviews. The local ``curling-score serve`` passes None and sets nothing,
    which is what makes everything editable and unversioned there.

    ``video`` is the local server's alone: ``window.VIDEO``, a file of the
    game's video for the page to play in place of the YouTube player. The
    address in it is built from an id `localvideo.for_run` has already held to
    letters, digits, ``-`` and ``_``, so nothing in it can end the script early.

    A missing anchor raises rather than returning the page unchanged. The
    version this replaced used ``str.replace(..., 1)``, which silently does
    nothing when it does not match: a 500 on a chart page is recoverable, a
    quietly editable share link is not.
    """
    text = (HERE / "index.html").read_text()
    if BOOT_ANCHOR not in text:
        raise RuntimeError(
            f"{BOOT_ANCHOR} is missing from index.html, so window.CHART cannot "
            f"be injected and every link would boot as a local, editable one")
    boot = ""
    if config is not None:
        boot += f"<script>window.CHART={json.dumps(config)};</script>"
    if video is not None:
        boot += f"<script>window.VIDEO={json.dumps(video.for_page())};</script>"
    return text.replace(BOOT_ANCHOR, boot, 1)


def make_server(out_dir, port: int = 8000, video: LocalVideo | None = None):
    """A viewer server for ``out_dir``. Port 0 picks a free one, for tests.

    With ``video`` the page plays that file; without, YouTube."""
    out_dir = Path(out_dir)
    timeline = out_dir / "timeline.json"
    if not timeline.is_file():
        raise SystemExit(
            f"no timeline at {timeline}\n"
            f"Run: curling-score analyze <url> --out {out_dir}"
        )
    for name in ASSETS:
        shutil.copyfile(HERE / name, out_dir / name)

    handler = functools.partial(ViewerHandler, directory=str(out_dir))
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    httpd.video = video
    return httpd


def serve(out_dir, port: int = 8000, open_browser: bool = True,
          local_video: bool = True) -> None:
    """Serve ``timeline.json`` from ``out_dir`` alongside the viewer page.

    ``local_video`` plays the game's video from a file in the page where the
    cache has it (`localvideo.for_run`); False keeps the YouTube player
    regardless. On by default, and falling back by itself, because nothing is
    lost by it but the stream's sound: the page does the same things either
    way, and a game with no file here plays from YouTube as it always has.
    """
    video = None
    if local_video:
        video = localvideo.for_run(out_dir, note=lambda dest: print(
            f"Writing a copy of the video the page can seek in, once per game: {dest}",
            flush=True))
    with make_server(out_dir, port, video=video) as httpd:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/index.html"
        print(f"Curling chart viewer at {url}   (ctrl-c to stop)")
        print(f"Corrections are saved to {Path(out_dir) / OVERRIDES}")
        if video is not None:
            print(f"The video plays from {video.path}: nothing drawn over the "
                  f"picture, and no sound\n  (--no-local-video for the YouTube player)")
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
