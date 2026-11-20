"""The game's own video file, for the local viewer to play in the page.

YouTube's player draws its title, its clock and its logo over the picture
after every jump and for as long as the video is paused -- over the house
insets and the scoreboard, which are what a charter stepping through stones is
trying to read -- and an embedding page cannot turn that off (tried 2026-11-20
with ``controls: 0``). A ``<video>`` element playing a file draws nothing the
page does not ask for. The pipeline already has the file: every analysed
game's video is in the cache.

Not as it is, though. The download is the stream's fragments laid end to end,
each with its own header and no index of the whole (``ftyp moov moof mdat``,
1,568 times over for a two-hour game). Chrome will index that itself, with a
request per fragment before it shows a frame; Safari reads the first fragment,
calls the video two seconds long, and reports no error. So the page is given a
copy: the same pictures, not re-encoded, rewritten once by ffmpeg as one MP4
with its index at the front. About a second per gigabyte, and the size of the
video again on disk, under ``viewer/`` in the cache. The download itself is
never touched -- the detection cache keys on its bytes.

Everything here answers None rather than raising when there is no file to
play: the page then plays YouTube, as it always has.
"""

import json
import os
import re
import secrets
import subprocess
from dataclasses import dataclass
from pathlib import Path

from curling_score.ingest import cache

# Where the page asks for the file. The id is in the address so that a port
# pointed at another game is another address: nothing a browser kept of the
# last game's video can be mistaken for this one's.
ROUTE = "local-video"
# The indexed copies, beside the cache's `videos/`. Safe to delete at any
# time: the next `serve` of the game writes its copy again.
COPY_DIR = "viewer"
# What goes into that address and into the page. A timeline is a file anybody
# can hand to `serve`, so its video id is not trusted to be one.
_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
_RANGE = re.compile(r"bytes=(\d*)-(\d*)")


@dataclass(frozen=True)
class LocalVideo:
    """A game's video as a file a browser can play, and what the page calls it."""

    video_id: str
    path: Path

    @property
    def url(self) -> str:
        """Relative, so it holds on whatever host and port the page was
        reached by (a phone comes in through a tailnet route)."""
        return f"{ROUTE}/{self.video_id}.mp4"

    def for_page(self) -> dict:
        """``window.VIDEO``. ``offset_s`` is where on the stream's clock the
        file's first frame sits: 0 here, where the file is the whole stream,
        and something else only for a file cut down to its game."""
        return {"src": self.url, "video_id": self.video_id, "offset_s": 0}


class RangeNotSatisfiable(ValueError):
    """A Range that starts past the end of the file: the answer is 416."""


def byte_range(header: str | None, size: int) -> tuple[int, int] | None:
    """The first and last byte a ``Range`` header asks for, both inclusive.

    None means the whole file: no header, or one this server does not act on
    (several ranges at once, another unit, nonsense), which HTTP lets a server
    ignore. A video element sends the three shapes handled here: ``bytes=A-B``,
    ``bytes=A-`` and ``bytes=-N``.
    """
    if not header:
        return None
    m = _RANGE.fullmatch(header.strip())
    if not m or not (m[1] or m[2]):
        return None
    if not m[1]:                      # the last N bytes
        n = int(m[2])
        if n == 0 or size == 0:
            raise RangeNotSatisfiable(header)
        return max(0, size - n), size - 1
    start = int(m[1])
    if start >= size:
        raise RangeNotSatisfiable(header)
    end = min(int(m[2]), size - 1) if m[2] else size - 1
    return (start, end) if end >= start else None


class Slice:
    """So many bytes of an open file, read a piece at a time.

    The stock handler copies whatever ``send_head`` returns to the socket in
    64 KiB reads; this stops that copy at the end of the range. A video is one
    to four gigabytes, so nothing ever holds more than one read of it.
    """

    PIECE = 64 * 1024

    def __init__(self, f, length: int):
        self._f, self._left = f, length

    def read(self, n: int = -1) -> bytes:
        if self._left <= 0:
            return b""
        want = self.PIECE if n is None or n < 0 else n
        data = self._f.read(min(want, self._left))
        self._left -= len(data)
        return data

    def close(self) -> None:
        self._f.close()


def copy_path(vid: str, root: Path | None = None) -> Path:
    root = Path(root) if root is not None else cache.default_root()
    return root / COPY_DIR / f"{vid}.mp4"


def _readable(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return bool(f.read(1))
    except OSError:
        return False


def indexed_copy(vid: str, root: Path | None = None, *,
                 run=subprocess.run, note=None) -> Path | None:
    """The cached download of ``vid`` as one indexed MP4, written if absent.

    None when there is no download, or the copy cannot be made (no ffmpeg, no
    room): the caller plays YouTube. Written under another name and renamed
    into place when whole, so a copy cut short is never the one found here.
    A copy that exists is taken as good: the download it was made from never
    changes in place (see ``ingest.cache``). ``note(dest)`` is called before a
    copy is written, for a caller that wants to say why it is waiting.
    """
    dest = copy_path(vid, root)
    if _readable(dest):
        return dest
    source = cache.video_path(vid, root)
    if not _readable(source):
        return None
    tmp = dest.with_name(f"{vid}.part-{os.getpid()}-{secrets.token_hex(4)}.mp4")
    try:
        if note is not None:
            note(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-i", str(source), "-map", "0:v:0", "-c", "copy",
             "-movflags", "+faststart", str(tmp)],
            check=True, stderr=subprocess.DEVNULL)
        if not _readable(tmp):
            return None
        tmp.replace(dest)
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def for_run(out_dir, root: Path | None = None, *,
            run=subprocess.run, note=None) -> LocalVideo | None:
    """The video of the run in ``out_dir``, if this machine can play it.

    None for anything short of a playable file: a game analysed elsewhere, a
    live run (recorded, never downloaded), a cleared cache, a timeline with no
    usable id. None is not an error -- the page plays YouTube, as before.
    ``root`` is the cache to look in; the default is the pipeline's own.
    """
    try:
        doc = json.loads((Path(out_dir) / "timeline.json").read_text())
        vid = doc["source"]["video_id"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(vid, str) or not _VIDEO_ID.fullmatch(vid):
        return None
    path = indexed_copy(vid, root, run=run, note=note)
    return LocalVideo(vid, path) if path is not None else None
