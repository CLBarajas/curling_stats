"""The local viewer playing the game's own video file.

``curling-score serve`` hands the page a file of the game's video where the
cache has one, a byte range at a time, so that the page can play it in a
``<video>`` of its own -- no YouTube title, clock or logo over the picture
after a jump or a pause. Held here: the ranges (a video element seeks by
asking for them, and the file is a gigabyte or four), what the page is told,
and that anything short of a playable file is simply no file -- the page then
plays YouTube, with nothing on it to say otherwise.
"""

import http.client
import json
import shutil
import struct
import subprocess
import threading
import time

import pytest

from curling_score import timeline, viewer
from curling_score.viewer import localvideo
from curling_score.viewer.localvideo import LocalVideo, RangeNotSatisfiable, Slice, byte_range

# Bigger than two of the server's reads, and every byte says where it is.
SIZE = 150_000
BYTES = b"".join(struct.pack(">I", i) for i in range(SIZE // 4))


def document(video_id="abc"):
    shot = {"number": 1, "color": "red", "stones": [], "state_known": False,
            "missing": False, "shot_type": "unknown"}
    return {
        "schema_version": timeline.SCHEMA_VERSION,
        "source": {"video_id": video_id, "url": "u", "sheet": 2, "duration_s": 1.0},
        "games": [{"index": 0, "start_s": 0.0, "end_s": 1.0,
                   "ends": [{"number": 3, "shots": [shot]}]}],
    }


def run_of(tmp_path, video_id="abc"):
    out = tmp_path / "run"
    out.mkdir()
    (out / "timeline.json").write_text(json.dumps(document(video_id)))
    return out


@pytest.fixture
def served(tmp_path):
    """A viewer server with a video to hand out: (port, the video's path)."""
    out = run_of(tmp_path)
    path = tmp_path / "abc.mp4"
    path.write_bytes(BYTES)
    httpd = viewer.make_server(out, port=0, video=LocalVideo("abc", path))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[1], path
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def ask(port, path="/local-video/abc.mp4", method="GET", **headers):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request(method, path, headers=headers)
        res = conn.getresponse()
        return res.status, dict(res.getheaders()), res.read()
    finally:
        conn.close()


class TestWhichBytes:
    """A Range header, read. Inclusive at both ends, as HTTP has it."""

    @pytest.mark.parametrize("header, want", [
        ("bytes=0-1", (0, 1)),                 # Safari's first question of any video
        ("bytes=10-19", (10, 19)),
        ("bytes=90-", (90, 99)),               # from here on: every seek
        ("bytes=-10", (90, 99)),               # the last ten: an index kept at the end
        ("bytes=-500", (0, 99)),               # more than there is: all of it
        ("bytes=50-5000", (50, 99)),           # past the end: up to the end
        ("bytes=99-99", (99, 99)),
        (" bytes=3-4 ", (3, 4)),
    ])
    def test_the_shapes_a_video_element_sends(self, header, want):
        assert byte_range(header, 100) == want

    @pytest.mark.parametrize("header", [
        None, "", "bytes=", "bytes=-", "bytes=5-2", "bytes=0-1,5-6", "items=0-1",
        "bytes=a-b", "0-1",
    ])
    def test_anything_else_is_the_whole_file(self, header):
        assert byte_range(header, 100) is None

    @pytest.mark.parametrize("header", ["bytes=100-", "bytes=100-200", "bytes=-0"])
    def test_a_range_with_nothing_in_it_is_refused(self, header):
        with pytest.raises(RangeNotSatisfiable):
            byte_range(header, 100)

    def test_nothing_can_be_asked_of_an_empty_file(self):
        with pytest.raises(RangeNotSatisfiable):
            byte_range("bytes=-5", 0)


class TestTheSlice:
    def test_it_stops_at_the_end_of_the_range(self, tmp_path):
        path = tmp_path / "f"
        path.write_bytes(BYTES)
        with open(path, "rb") as f:
            f.seek(1000)
            part = Slice(f, 70_000)
            got = b"".join(iter(lambda: part.read(64 * 1024), b""))
        assert got == BYTES[1000:71_000]

    def test_a_read_with_no_size_is_still_one_piece(self, tmp_path):
        """The file is gigabytes: nothing may ask for "the rest" and get it."""
        path = tmp_path / "f"
        path.write_bytes(BYTES)
        with open(path, "rb") as f:
            assert len(Slice(f, SIZE).read()) == Slice.PIECE


class TestRangesOverHttp:
    def test_with_no_range_it_is_the_whole_file_and_says_it_takes_ranges(self, served):
        port, _ = served
        status, headers, body = ask(port)
        assert status == 200 and body == BYTES
        assert headers["Accept-Ranges"] == "bytes"
        assert headers["Content-Type"] == "video/mp4"
        assert headers["Content-Length"] == str(SIZE)

    @pytest.mark.parametrize("header, first, last", [
        ("bytes=0-1", 0, 1),
        ("bytes=70000-139999", 70_000, 139_999),      # across two of the server's reads
        (f"bytes={SIZE - 10}-", SIZE - 10, SIZE - 1),
        ("bytes=-10", SIZE - 10, SIZE - 1),
        (f"bytes=100-{SIZE * 2}", 100, SIZE - 1),
    ])
    def test_a_range_is_those_bytes_and_no_others(self, served, header, first, last):
        port, _ = served
        status, headers, body = ask(port, Range=header)
        assert status == 206
        assert headers["Content-Range"] == f"bytes {first}-{last}/{SIZE}"
        assert headers["Content-Length"] == str(last - first + 1)
        assert body == BYTES[first:last + 1]

    def test_a_range_past_the_end_is_refused_with_the_size(self, served):
        port, _ = served
        status, headers, body = ask(port, Range=f"bytes={SIZE}-")
        assert status == 416 and body == b""
        assert headers["Content-Range"] == f"bytes */{SIZE}"

    def test_several_ranges_at_once_get_the_whole_file(self, served):
        port, _ = served
        status, _, body = ask(port, Range="bytes=0-1,10-11")
        assert status == 200 and body == BYTES

    def test_head_answers_like_get_without_the_bytes(self, served):
        port, _ = served
        status, headers, body = ask(port, method="HEAD", Range="bytes=5-9")
        assert status == 206 and body == b""
        assert headers["Content-Range"] == f"bytes 5-9/{SIZE}"

    def test_a_range_of_a_file_since_replaced_gets_the_new_file_whole(self, served):
        """If-Range: a browser resuming holds part of one file, and must not
        be handed the rest from another."""
        port, _ = served
        _, headers, _ = ask(port, Range="bytes=0-1")
        tag = headers["ETag"]
        assert ask(port, Range="bytes=5-9", **{"If-Range": tag})[0] == 206
        status, _, body = ask(port, Range="bytes=5-9", **{"If-Range": '"another"'})
        assert status == 200 and body == BYTES

    def test_a_file_the_browser_already_holds_costs_no_body(self, served):
        port, _ = served
        tag = ask(port, Range="bytes=0-1")[1]["ETag"]
        status, _, body = ask(port, **{"If-None-Match": tag})
        assert status == 304 and body == b""

    def test_only_this_game_s_video_is_there(self, served):
        port, _ = served
        assert ask(port, "/local-video/other.mp4")[0] == 404
        assert ask(port, "/local-video/")[0] == 404

    def test_a_request_dropped_part_way_costs_the_server_nothing(self, served, capfd):
        """A video element hangs up on a request every time it seeks: the
        server carries on, and does not print a traceback for each."""
        port, path = served
        # More than a socket will take in one go, so the server is still
        # sending when the browser stops listening.
        with open(path, "r+b") as f:
            f.truncate(40_000_000)
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("GET", "/local-video/abc.mp4")
        conn.getresponse().read(100)
        conn.close()
        status, _, body = ask(port, Range="bytes=0-3")
        assert status == 206 and body == BYTES[:4]
        time.sleep(0.5)                       # let the dropped one find out
        said = capfd.readouterr().err
        assert "Traceback" not in said and "Exception occurred" not in said

    def test_a_video_gone_since_start_up_is_a_plain_404(self, served):
        """The cache was cleared under a running viewer: the page's video
        element reports the 404 and the page goes back to YouTube."""
        port, path = served
        path.unlink()
        assert ask(port)[0] == 404
        assert ask(port, "/timeline.json")[0] == 200


class TestWhatThePageIsTold:
    def test_the_page_is_told_where_its_video_is(self, served):
        port, _ = served
        for address in ("/", "/index.html", "/index.html?x=1"):
            status, _, body = ask(port, address)
            assert status == 200
            assert ('<script>window.VIDEO={"src": "local-video/abc.mp4", '
                    '"video_id": "abc", "offset_s": 0};</script>') in body.decode()
            # Still the local page: nothing says view-only, so it edits.
            assert "<script>window.CHART=" not in body.decode()

    def test_the_copy_in_the_run_s_folder_is_told_nothing(self, served, tmp_path):
        """That folder gets copied and served by other things, which have no
        video to hand out: only this server's own answer names one."""
        assert "window.VIDEO" not in (tmp_path / "run" / "index.html").read_text()

    def test_with_no_video_the_page_is_the_page_it_always_was(self, tmp_path):
        out = run_of(tmp_path)
        httpd = viewer.make_server(out, port=0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            port = httpd.server_address[1]
            status, _, body = ask(port, "/index.html")
            assert status == 200 and "window.VIDEO" not in body.decode()
            assert body == (out / "index.html").read_bytes()
            assert ask(port)[0] == 404
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_the_hosted_page_can_carry_both(self):
        page = viewer.boot_page({"mode": "view"}, video=LocalVideo("abc", "x"))
        assert '<script>window.CHART={"mode": "view"};</script>' in page
        assert "<script>window.VIDEO=" in page and viewer.BOOT_ANCHOR not in page
        assert "window.VIDEO" not in viewer.boot_page({"mode": "view"})


def fake_ffmpeg(calls, writes=b"an indexed copy"):
    def run(cmd, **kwargs):
        calls.append(cmd)
        if writes is not None:
            open(cmd[-1], "wb").write(writes)
    return run


class TestWhichFile:
    """`for_run`: the run's video as a file a browser can play, or None."""

    def cache_with(self, tmp_path, video_id="abc", content=b"the download"):
        root = tmp_path / "cache"
        (root / "videos").mkdir(parents=True)
        (root / "videos" / f"{video_id}.mp4").write_bytes(content)
        return root

    def test_a_cached_download_is_copied_once_and_the_copy_is_what_plays(self, tmp_path):
        out, root, calls = run_of(tmp_path), self.cache_with(tmp_path), []
        noted = []
        video = localvideo.for_run(out, root, run=fake_ffmpeg(calls), note=noted.append)
        assert video == LocalVideo("abc", root / "viewer" / "abc.mp4")
        assert video.path.read_bytes() == b"an indexed copy"
        assert noted == [video.path]
        [cmd] = calls
        assert cmd[0] == "ffmpeg" and str(root / "videos" / "abc.mp4") in cmd
        # Rewritten, never re-encoded, with the index where a browser reads first.
        assert cmd[cmd.index("-c") + 1] == "copy"
        assert cmd[cmd.index("-movflags") + 1] == "+faststart"
        # The download is the detection cache's key: it is never the one written.
        assert (root / "videos" / "abc.mp4").read_bytes() == b"the download"
        assert [p.name for p in (root / "viewer").iterdir()] == ["abc.mp4"]

        again = localvideo.for_run(out, root, run=fake_ffmpeg(calls), note=noted.append)
        assert again == video and len(calls) == 1 and len(noted) == 1

    def test_a_game_with_no_download_here_has_no_file(self, tmp_path):
        out, calls = run_of(tmp_path), []
        assert localvideo.for_run(out, tmp_path / "cache", run=fake_ffmpeg(calls)) is None
        assert calls == []

    def test_an_empty_download_is_no_download(self, tmp_path):
        out, root, calls = run_of(tmp_path), self.cache_with(tmp_path, content=b""), []
        assert localvideo.for_run(out, root, run=fake_ffmpeg(calls)) is None
        assert calls == []

    @pytest.mark.parametrize("video_id", ["../abc", "../videos/abc", "a b", "a.b", "x" * 65, 7])
    def test_a_timeline_s_video_id_is_not_trusted_to_be_one(self, tmp_path, video_id):
        """It becomes part of an address and of a path into the cache -- so
        it is refused even where a file sits at the path it would make."""
        out, root, calls = run_of(tmp_path, video_id), self.cache_with(tmp_path), []
        there = root / "videos" / f"{video_id}.mp4"
        there.write_bytes(b"a file, where this id points")
        assert there.read_bytes()
        assert localvideo.for_run(out, root, run=fake_ffmpeg(calls)) is None
        assert calls == []

    @pytest.mark.parametrize("video_id", ["", None])
    def test_a_timeline_with_no_video_id_has_no_file(self, tmp_path, video_id):
        out, root, calls = run_of(tmp_path, video_id), self.cache_with(tmp_path), []
        assert localvideo.for_run(out, root, run=fake_ffmpeg(calls)) is None
        assert calls == []

    def test_a_folder_with_no_readable_timeline_has_no_file(self, tmp_path):
        out, root = run_of(tmp_path), self.cache_with(tmp_path)
        (out / "timeline.json").write_text("{not json")
        assert localvideo.for_run(out, root, run=fake_ffmpeg([])) is None
        assert localvideo.for_run(tmp_path / "nowhere", root, run=fake_ffmpeg([])) is None

    @pytest.mark.parametrize("failure", [
        FileNotFoundError("ffmpeg"),
        subprocess.CalledProcessError(1, "ffmpeg"),
        OSError(28, "No space left on device"),
    ])
    def test_a_copy_that_cannot_be_made_is_no_file_and_leaves_nothing(self, tmp_path, failure):
        out, root = run_of(tmp_path), self.cache_with(tmp_path)

        def run(cmd, **kwargs):
            open(cmd[-1], "wb").write(b"half a")
            raise failure

        assert localvideo.for_run(out, root, run=run) is None
        assert list((root / "viewer").iterdir()) == []

    def test_an_ffmpeg_that_wrote_nothing_is_no_file(self, tmp_path):
        out, root = run_of(tmp_path), self.cache_with(tmp_path)
        assert localvideo.for_run(out, root, run=fake_ffmpeg([], writes=None)) is None
        assert localvideo.for_run(out, root, run=fake_ffmpeg([], writes=b"")) is None
        assert list((root / "viewer").iterdir()) == []

    @pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
    def test_the_real_copy_has_its_index_before_its_pictures(self, tmp_path):
        """What the download is -- fragments, each with its own header, and no
        index of the whole -- and what the copy has to be for Safari to see
        more than the first of them."""
        out, root = run_of(tmp_path), tmp_path / "cache"
        (root / "videos").mkdir(parents=True)
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-f", "lavfi", "-i", "testsrc=size=64x64:rate=10:duration=3",
             "-c:v", "mpeg4", "-g", "10",
             "-movflags", "frag_keyframe+empty_moov+default_base_moof",
             str(root / "videos" / "abc.mp4")], check=True)
        assert b"moof" in (root / "videos" / "abc.mp4").read_bytes()

        video = localvideo.for_run(out, root)
        copy = video.path.read_bytes()
        assert b"moof" not in copy
        assert 0 < copy.index(b"moov") < copy.index(b"mdat")


class TestServeFromTheCommandLine:
    def run(self, monkeypatch, argv):
        from curling_score import cli

        seen = {}
        monkeypatch.setattr(viewer, "serve", lambda out, **kw: seen.update(out=out, **kw))
        assert cli.main(argv) == 0
        return seen

    def test_it_plays_the_cached_file_unless_told_not_to(self, monkeypatch):
        assert self.run(monkeypatch, ["serve", "--out", "x"])["local_video"] is True

    def test_no_local_video_keeps_the_youtube_player(self, monkeypatch):
        got = self.run(monkeypatch, ["serve", "--out", "x", "--no-local-video"])
        assert got["local_video"] is False

    def test_told_not_to_it_does_not_so_much_as_look(self, monkeypatch, tmp_path):
        out = run_of(tmp_path)
        monkeypatch.setattr(localvideo, "for_run",
                            lambda *a, **kw: pytest.fail("looked for a video"))
        made = {}

        class Stop(Exception):
            pass

        def make_server(out_dir, port, video=None):
            made["video"] = video
            raise Stop

        monkeypatch.setattr(viewer, "make_server", make_server)
        with pytest.raises(Stop):
            viewer.serve(out, port=0, open_browser=False, local_video=False)
        assert made == {"video": None}
