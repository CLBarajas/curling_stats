"""The page's own video player, exercised in node.

Where the page is offered the game's video as a file it plays that in a
``<video>`` of its own, behind the same six functions the YouTube player
answers (``frontend/runtime/player.mjs``). What is held here is what the rest
of the page leans on without knowing which player it has: a seek asked for
early is kept, times are the stream's whatever the file's are, and a file that
will not play hands over to YouTube at the same moment -- with nothing put on
the page to say so.

The player builds its own DOM, so it runs against the stand-in browser in
``tests/js/player_harness.mjs``, one node process a test: it is a singleton.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests/js/player_harness.mjs"
PLAYER = ROOT / "frontend/runtime/player.mjs"
VIDEO = ROOT / "frontend/core/video.mjs"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node is not installed")

FILE = '{ src: "local-video/abc.mp4", offset: 0 }'


def run_js(body: str):
    """Run ``body`` with the harness (``H``), the player (``P``) and the
    core's video arithmetic (``V``) in scope; return what it hands ``out``."""
    script = (
        f"const H = await import({HARNESS.as_uri()!r});\n"
        f"const P = await import({PLAYER.as_uri()!r});\n"
        f"const V = await import({VIDEO.as_uri()!r});\n"
        "function out(v){ console.log(JSON.stringify(v)); }\n" + body
    )
    proc = subprocess.run([node, "--input-type=module", "-e", script],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def mounted(file=FILE, autoplay="true", duration=7842):
    """The player mounted on a file whose metadata has arrived (or has not,
    with ``duration=None``)."""
    ready = "" if duration is None else (
        f"v.duration = {duration}; v.fire('durationchange'); v.fire('loadedmetadata');\n")
    return (f"P.mount(H.box, 'abc', {{ autoplay: () => {autoplay}, file: {file} }});\n"
            "const v = H.the('video');\n" + ready)


class TestWhichVideoThePagePlays:
    """core/video.mjs: what the page makes of window.VIDEO."""

    def test_an_offered_file_is_taken(self):
        got = run_js('out(V.ownVideo({ src: "local-video/abc.mp4", video_id: "abc", offset_s: 0 }, "abc"));')
        assert got == {"src": "local-video/abc.mp4", "offset": 0}

    def test_a_file_cut_down_to_its_game_says_where_it_starts(self):
        got = run_js('out(V.ownVideo({ src: "https://media.example/g.mp4", offset_s: 280.5 }, "abc"));')
        assert got == {"src": "https://media.example/g.mp4", "offset": 280.5}

    @pytest.mark.parametrize("offer", [
        "undefined", "null", '"local-video/abc.mp4"', "{}", '{ src: "" }', "{ src: 7 }",
    ])
    def test_no_offer_is_youtube(self, offer):
        assert run_js(f'out(V.ownVideo({offer}, "abc"));') is None

    def test_another_game_s_file_is_refused(self):
        """The wrong pictures under this chart would be worse than an overlay."""
        got = run_js('out(V.ownVideo({ src: "local-video/xyz.mp4", video_id: "xyz" }, "abc"));')
        assert got is None

    def test_an_offset_that_is_not_a_number_is_none(self):
        got = run_js('out(V.ownVideo({ src: "f.mp4", offset_s: "280" }, "abc"));')
        assert got == {"src": "f.mp4", "offset": 0}

    def test_a_moment_is_found_in_the_file_and_never_before_its_start(self):
        got = run_js("out([V.fileTime(300, 0), V.fileTime(300, 280), V.fileTime(100, 280)]);")
        assert got == [300, 20, 0]

    def test_a_file_far_shorter_than_the_moment_asked_for_does_not_reach_it(self):
        got = run_js("""out([V.reaches(7842, 7800, 0), V.reaches(7842, 7880, 0),
                             V.reaches(2, 3600, 0), V.reaches(5500, 5770, 280),
                             V.reaches(NaN, 3600, 0), V.reaches(Infinity, 3600, 0)]);""")
        assert got == [True, True, False, True, True, True]

    def test_the_clock_reads_like_the_stream_s(self):
        got = run_js("out([0, 59.9, 274.13, 3600, 7842, NaN].map(V.videoClock));")
        assert got == ["0:00", "0:59", "4:34", "1:00:00", "2:10:42", "–:––"]


class TestTheFilePlays:
    def test_it_is_a_muted_video_of_the_page_s_own_and_youtube_is_never_asked(self):
        got = run_js(mounted(duration=None) + """
            out({ src: v.src, muted: v.muted, inline: v.playsInline, preload: v.preload,
                  controls: v.controls ?? false, inBox: H.box.children.includes(v),
                  scripts: H.all("script").length, youtube: H.youtube.length });""")
        assert got == {"src": "local-video/abc.mp4", "muted": True, "inline": True,
                       "preload": "metadata", "controls": False, "inBox": True,
                       "scripts": 0, "youtube": 0}

    def test_before_the_file_answers_there_is_no_time_and_nothing_plays(self):
        got = run_js(mounted(duration=None) + """
            P.pause(); P.togglePlay();
            out({ t: P.currentTime(), playing: P.isPlaying(), paused: v.paused });""")
        assert got == {"t": None, "playing": False, "paused": True}

    def test_a_seek_asked_for_early_is_kept_with_its_own_autoplay(self):
        """A linked rock seeks on load and asks not to play: "play on jump"
        must not override that when the file comes ready."""
        got = run_js(mounted(duration=None) + """
            P.seek(1234.5, false);
            const before = v.currentTime;
            v.duration = 7842; v.fire("loadedmetadata");
            out({ before, after: v.currentTime, paused: v.paused });""")
        assert got == {"before": 0, "after": 1234.5, "paused": True}

    def test_an_early_seek_that_did_not_say_takes_the_preference(self):
        for pref, paused in (("true", False), ("false", True)):
            got = run_js(mounted(duration=None, autoplay=pref) + """
                P.seek(60);
                v.duration = 7842; v.fire("loadedmetadata");
                out({ t: v.currentTime, paused: v.paused });""")
            assert got == {"t": 60, "paused": paused}

    def test_a_jump_goes_there_and_plays_only_if_asked(self):
        got = run_js(mounted() + """
            P.seek(183.6, false);
            const still = { t: P.currentTime(), playing: P.isPlaying() };
            P.seek(231.6, true);
            out({ still, moving: { t: P.currentTime(), playing: P.isPlaying() } });""")
        assert got == {"still": {"t": 183.6, "playing": False},
                       "moving": {"t": 231.6, "playing": True}}

    def test_pause_and_the_p_key_do_what_they_say(self):
        got = run_js(mounted() + """
            const seen = [];
            P.togglePlay(); seen.push(P.isPlaying());
            P.pause();      seen.push(P.isPlaying());
            P.pause();      seen.push(P.isPlaying());
            P.togglePlay(); seen.push(P.isPlaying());
            P.togglePlay(); seen.push(P.isPlaying());
            out(seen);""")
        assert got == [True, False, False, True, False]

    def test_a_video_that_ran_out_is_not_playing(self):
        got = run_js(mounted() + "P.togglePlay(); v.ended = true; out(P.isPlaying());")
        assert got is False

    def test_a_click_on_the_picture_plays_and_pauses(self):
        got = run_js(mounted() + """
            v.fire("click"); const a = v.paused;
            v.fire("click"); out([a, v.paused]);""")
        assert got == [False, True]

    def test_times_are_the_stream_s_when_the_file_starts_part_way_in(self):
        """A file cut down to its game: the chart's times are still the
        stream's, and so are the ones the player reports."""
        got = run_js(mounted(file='{ src: "g.mp4", offset: 280 }', duration=5500) + """
            P.seek(300, false);
            const at = v.currentTime;
            P.seek(100, false);
            const beforeItsStart = v.currentTime;
            v.currentTime = 25.5;
            out({ at, beforeItsStart, told: P.currentTime() });""")
        assert got == {"at": 20, "beforeItsStart": 0, "told": 305.5}

    def test_mounting_twice_is_mounting_once(self):
        got = run_js(mounted() + f"""
            P.mount(H.box, 'abc', {{ file: {FILE} }});
            P.mount(H.box, 'abc');
            out([H.all("video").length, H.all("script").length]);""")
        assert got == [1, 0]


class TestWithoutAFile:
    def test_no_file_is_the_youtube_player_as_before(self):
        got = run_js("""
            P.mount(H.box, 'abc', { autoplay: () => false });
            P.seek(500, false);
            const yt = H.youtubeReady();
            out({ videos: H.all("video").length, script: H.the("script").src,
                  id: yt.options.videoId, mute: yt.options.playerVars.mute, calls: yt.calls });""")
        assert got == {"videos": 0, "script": "https://www.youtube.com/iframe_api",
                       "id": "abc", "mute": 1, "calls": [["seekTo", 500]]}


class TestAFileThatWillNotPlay:
    """YouTube takes over, at the same moment, and the page says nothing."""

    def test_a_file_that_is_not_there_hands_its_waiting_seek_to_youtube(self):
        got = run_js(mounted(duration=None) + """
            P.seek(1234.5, false);
            v.fire("error");
            const between = { t: P.currentTime(), playing: P.isPlaying() };
            const yt = H.youtubeReady();
            out({ between, gone: !H.box.children.includes(v), letGo: [v.src ?? null, v.loads],
                  box: H.box.children.map(c => c.id || c.className || c.tagName),
                  calls: yt.calls });""")
        assert got == {"between": {"t": None, "playing": False}, "gone": True,
                       "letGo": [None, 1], "box": ["player"],
                       "calls": [["seekTo", 1234.5]]}

    def test_a_file_that_fails_while_playing_carries_on_from_there(self):
        got = run_js(mounted() + """
            P.seek(700, true);
            v.currentTime = 705.25;
            v.fire("error");
            out(H.youtubeReady().calls);""")
        assert got == [["seekTo", 705.25], ["playVideo"]]

    def test_a_file_that_fails_while_paused_stays_paused(self):
        got = run_js(mounted() + """
            P.seek(700, false);
            v.fire("error");
            out(H.youtubeReady().calls);""")
        assert got == [["seekTo", 700]]

    def test_a_file_that_fails_before_anything_was_asked_leaves_youtube_at_rest(self):
        got = run_js(mounted(duration=None) + "v.fire('error'); out(H.youtubeReady().calls);")
        assert got == []

    def test_a_file_that_stops_far_short_of_the_rock_is_not_this_game_s(self):
        """Safari reads a download that was never indexed as its first two
        seconds and reports no error. The first jump past them finds out."""
        got = run_js(mounted(duration=2) + """
            P.seek(3600, false);
            const yt = H.youtubeReady();
            out({ fileAskedFor: v.currentTime, gone: !H.box.children.includes(v), calls: yt.calls });""")
        assert got == {"fileAskedFor": 0, "gone": True, "calls": [["seekTo", 3600]]}

    def test_after_handing_over_every_function_is_youtube_s(self):
        got = run_js(mounted() + """
            v.fire("error");
            const yt = H.youtubeReady();
            P.seek(42, true); P.pause(); P.togglePlay();
            yt.time = 43;
            out({ t: P.currentTime(), playing: P.isPlaying(), calls: yt.calls, fileTouched: !v.paused });""")
        assert got == {"t": 43, "playing": True, "fileTouched": False,
                       "calls": [["seekTo", 0], ["seekTo", 42], ["playVideo"],
                                 ["pauseVideo"], ["playVideo"]]}

    def test_nothing_is_written_on_the_page_about_it(self):
        got = run_js(mounted() + """
            v.fire("error"); H.youtubeReady();
            out(H.made.filter(e => e.className === "fallback").length);""")
        assert got == 0


BAR = """
    const bar = H.made.find(e => e.className === "vbar");
    const on = () => bar.classList.contains("on");
    const lapse = () => H.timers.at(-1)[0]();
    const at = (x, y) => H.box.fire("pointermove", { clientX: x, clientY: y });
    const move = () => { at(100, 100); at(104, 101); };
"""


class TestTheControlsStayOutOfThePicture:
    """The reason for all of it: nothing is drawn over the frame because of a
    jump or a pause. The file's controls come up only for a pointer moving
    over the picture, and go again."""

    def test_a_jump_a_pause_and_play_draw_nothing(self):
        got = run_js(mounted() + BAR + """
            const seen = [on()];
            P.seek(183.6, true);  v.fire("seeked"); seen.push(on());
            P.pause();                              seen.push(on());
            P.seek(231.6, false); v.fire("seeked"); seen.push(on());
            P.togglePlay();                         seen.push(on());
            v.fire("timeupdate");                   seen.push(on());
            out(seen);""")
        assert got == [False] * 6

    def test_the_browser_s_own_controls_are_never_switched_on(self):
        """They stay up for as long as a video is paused."""
        src = PLAYER.read_text()
        assert ".controls" not in src and '"controls"' not in src

    def test_a_pointer_moving_over_the_picture_brings_them_up_for_a_while(self):
        got = run_js(mounted() + BAR + """
            move();
            const shown = on(), linger = H.timers.at(-1)[1];
            lapse();
            out({ shown, linger, after: on() });""")
        assert got == {"shown": True, "linger": 2500, "after": False}

    def test_a_pointer_resting_on_the_picture_does_not_count_as_moving(self):
        """Stepping changes the page under a still pointer, and a browser
        answers that by sending the pointer's position again -- the first
        time the page hears where the pointer is, and every time after."""
        got = run_js(mounted() + BAR + """
            const seen = [];
            at(100, 100); seen.push(on());
            at(100, 100); seen.push(on());
            at(101, 100); seen.push(on());
            lapse();
            at(101, 100); seen.push(on());
            out(seen);""")
        assert got == [False, False, True, False]

    def test_a_mouse_leaving_the_picture_takes_them_away_at_once(self):
        got = run_js(mounted() + BAR + """
            move(); H.box.fire("pointerleave", { pointerType: "mouse" }); out(on());""")
        assert got is False

    def test_a_tap_brings_them_up_and_they_outlast_the_finger(self):
        """A finger leaves the picture the moment it lifts. The controls have
        to still be there for it to come down on."""
        got = run_js(mounted() + BAR + """
            H.box.fire("pointerdown", { clientX: 1, clientY: 1, pointerType: "touch" });
            H.box.fire("pointerleave", { pointerType: "touch" });
            const lifted = on();
            lapse();
            out([lifted, on()]);""")
        assert got == [True, False]

    def test_the_scrubber_moves_the_video_and_gives_the_keys_back(self):
        """A focused slider takes the arrow keys, which are the page's: they
        step rocks."""
        got = run_js(mounted() + BAR + """
            const scrub = H.made.find(e => e.className === "vscrub");
            move();
            scrub.value = "3905"; scrub.fire("input");
            const dragging = { t: v.currentTime, max: scrub.max, tab: scrub.tabIndex };
            lapse();
            const heldWhileDragging = on();
            scrub.fire("change"); lapse();
            out({ dragging, heldWhileDragging, blurred: scrub.blurred, after: on() });""")
        assert got == {"dragging": {"t": 3905, "max": "7842", "tab": -1},
                       "heldWhileDragging": True, "blurred": 1, "after": False}

    def test_the_clock_shows_the_stream_s_time(self):
        got = run_js(mounted(file='{ src: "g.mp4", offset: 280 }', duration=5500) + BAR + """
            v.currentTime = 20; v.fire("timeupdate");
            out(H.made.find(e => e.className === "vtime").textContent);""")
        assert got == "5:00 / 1:36:20"


class TestTheAppOffersTheFile:
    def test_the_app_mounts_whatever_the_page_was_offered(self):
        app = (ROOT / "frontend/viewer/App.jsx").read_text()
        assert "file: ownVideo(globalThis.window?.VIDEO, doc.source.video_id)" in app

    def test_the_link_beside_each_shot_is_still_youtube_s(self):
        """Whichever player the page has, "YouTube" opens YouTube at the shot."""
        app = (ROOT / "frontend/viewer/App.jsx").read_text()
        assert "`https://youtu.be/${doc.source.video_id}?t=${Math.floor(t)}`" in app

    def test_the_bar_is_not_sized_like_the_player_it_sits_on(self):
        """`.video > div` is the YouTube slot's rule: full height. The bar is a
        div in the same box and must not inherit it."""
        css = (ROOT / "src/curling_score/viewer/style.css").read_text()
        rule = next(r for r in css.split("}") if ".video > div.vbar {" in r)
        assert "height:auto" in rule and "opacity:0" in rule and "pointer-events:none" in rule


class TestTheVideoKeys:
    """j and l, Shift with an arrow, m: the keys YouTube's player answers,
    answered by the page for either player (App.jsx's keydown)."""

    def test_a_jump_on_youtube_is_from_where_it_is_and_leaves_it_playing_or_not(self):
        got = run_js("""
            P.mount(H.box, 'abc', { autoplay: () => false });
            const yt = H.youtubeReady();
            yt.time = 100;
            P.seekBy(10); P.seekBy(-5);
            out(yt.calls);""")
        assert got == [["seekTo", 110], ["seekTo", 105]]

    def test_a_jump_back_stops_at_the_start(self):
        got = run_js("""
            P.mount(H.box, 'abc');
            const yt = H.youtubeReady();
            yt.time = 4;
            P.seekBy(-10);
            out(yt.calls);""")
        assert got == [["seekTo", 0]]

    def test_before_the_player_answers_a_jump_does_nothing(self):
        got = run_js("""
            P.mount(H.box, 'abc');
            P.seekBy(10);
            const yt = H.youtubeReady();     // drains anything queued
            out(yt.calls);""")
        assert got == []

    def test_quick_jumps_on_youtube_count_from_the_last_one_not_its_stale_clock(self):
        """getCurrentTime lags a seekTo: l l l must be +30, not +10 three times."""
        got = run_js("""
            P.mount(H.box, 'abc');
            const yt = H.youtubeReady();
            yt.getCurrentTime = () => 100;   // YouTube has not caught up with any of them
            P.seekBy(10); P.seekBy(10); P.seekBy(10);
            out(yt.calls);""")
        assert got == [["seekTo", 110], ["seekTo", 120], ["seekTo", 130]]

    def test_a_jump_on_a_file_stays_on_the_file_at_its_end(self):
        """A file asked for a moment past its end gives up to YouTube; l near
        the end must land on the end instead."""
        got = run_js(mounted(duration=600) + """
            v.currentTime = 595;
            P.seekBy(10);
            const at = v.currentTime;
            P.seekBy(-1000);
            out({ at, back: v.currentTime, youtube: H.youtube.length, paused: v.paused });""")
        assert got == {"at": 600, "back": 0, "youtube": 0, "paused": True}

    def test_a_jump_on_a_file_that_starts_part_way_in_keeps_to_the_stream_s_clock(self):
        got = run_js(mounted(file='{ src: "g.mp4", offset: 280 }', duration=600) + """
            v.currentTime = 20;
            P.seekBy(10);
            out({ file: v.currentTime, stream: P.currentTime() });""")
        assert got == {"file": 30, "stream": 310}

    def test_m_turns_the_sound_on_and_off_on_either_player(self):
        got = run_js(mounted() + """
            const was = v.muted; P.toggleMute(); const on = v.muted; P.toggleMute();
            out({ was, on, off: v.muted });""")
        assert got == {"was": True, "on": False, "off": True}
        got = run_js("""
            P.mount(H.box, 'abc');
            const yt = H.youtubeReady();
            P.toggleMute(); P.toggleMute();
            out(yt.calls);""")
        assert got == [["unMute"], ["mute"]]


class TestYouTubeGivesTheKeyboardBack:
    """A click on YouTube's frame gives it the keyboard; the page takes it back
    once the click has landed (keepKeys), so its own keys keep working."""

    def test_the_frame_is_let_go_of_after_the_window_loses_focus_to_it(self):
        got = run_js("""
            P.mount(H.box, 'abc');
            const frame = document.createElement("iframe");
            H.box.children[0].append(frame);
            document.activeElement = frame;
            H.windowFires("blur");
            const before = frame.blurred ?? 0;
            H.timers.at(-1)[0]();
            out({ before, after: frame.blurred, focus: document.activeElement });""")
        assert got == {"before": 0, "after": 1, "focus": None}

    def test_focus_that_arrives_by_tab_is_left_with_youtube(self):
        """Someone on the keyboard alone is going to YouTube's own controls."""
        got = run_js("""
            P.mount(H.box, 'abc');
            const frame = document.createElement("iframe");
            H.box.children[0].append(frame);
            H.windowFires("keydown", { key: "Tab" });
            document.activeElement = frame;
            const before = H.timers.length;
            H.windowFires("blur");
            for (const [fn] of H.timers.slice(before)) fn();
            out({ blurred: frame.blurred ?? 0, focus: document.activeElement === frame });""")
        assert got == {"blurred": 0, "focus": True}

    def test_a_frame_that_is_not_the_video_s_keeps_its_keyboard(self):
        got = run_js("""
            P.mount(H.box, 'abc');
            const other = document.createElement("iframe");
            document.activeElement = other;
            H.windowFires("blur");
            H.timers.at(-1)[0]();
            out(other.blurred ?? 0);""")
        assert got == 0

    def test_the_page_s_own_video_needs_no_taking_back(self):
        got = run_js(mounted() + "out((H.winListeners.blur ?? []).length);")
        assert got == 0


class TestTheKeysAreThePage_s:
    def test_the_app_answers_youtube_s_keys(self):
        app = (ROOT / "frontend/viewer/App.jsx").read_text()
        for line in ['case "j": player.seekBy(-JUMP_SEEK_S)', 'case "l": player.seekBy(JUMP_SEEK_S)',
                     'case "k": player.togglePlay()', 'case "m": player.toggleMute()',
                     'case "f": player.toggleFullscreen()',
                     'case " ": if (ev.target !== document.body && ev.target !== document.documentElement) return;',
                     'if (ev.repeat && TOGGLE_KEYS.includes(ev.key)) return;',
                     'if (ev.shiftKey) { player.seekBy(-SHIFT_SEEK_S); break; }',
                     'if (ev.shiftKey) { player.seekBy(SHIFT_SEEK_S); break; }']:
            assert line in app

    def test_every_key_the_card_lists_is_one_the_page_answers(self):
        """The card and the keydown handler must not drift apart."""
        card = (ROOT / "frontend/viewer/KeysDialog.jsx").read_text()
        app = (ROOT / "frontend/viewer/App.jsx").read_text()
        listed = set(re.findall(r'\[\["([a-z0-9?])"', card)) | set(re.findall(r'", "([a-z0-9])"\]', card))
        # A reformatted card must fail here, not pass with nothing found.
        assert {"j", "l", "k", "m", "f", "?", "v", "t", "n", "x", "c", "d", "r", "y", "0", "4"} <= listed, listed
        for k in listed:
            assert f'case "{k}"' in app, k
        for name, case in [("Enter", 'case "Enter"'), ("Esc", 'case "Escape"'), ("Space", 'case " "')]:
            assert f'"{name}"' in card and case in app, name

    def test_the_selected_rock_s_ring_stays_out_of_the_gap(self):
        """2 px of outline drawn 2 px inside: wholly on the chip, whatever the
        gap (1 px in some rows). Nothing may push it back out."""
        css = (ROOT / "src/curling_score/viewer/style.css").read_text()
        assert ".shot.sel { outline:2px solid var(--accent); outline-offset:-2px;" in css
        assert re.search(r"\.shot\.sel\s*\{[^}]*outline-offset:\s*[1-9]", css) is None
