"""What differs from one club's stream to another's.

Granite, where all of this was built, is the default everywhere; another club
is a profile here rather than a branch through the code.
"""

from dataclasses import dataclass, replace

from curling_score.game.fixedboard import FixedBoard
from curling_score.geometry import constants as C
from curling_score.geometry.calibrate import (
    BLUE_HSV, DARK_HSV, GRANITE_HOUSE, RED_HSV, HousePaint,
)
from curling_score.geometry.endcam import EndPaint
from curling_score.geometry.layout import PanelLayout


@dataclass(frozen=True)
class Panel:
    """One overhead house panel: which edge stones enter by, and its paint."""

    delivery_side: str  # "top" or "bottom"
    paint: HousePaint


@dataclass(frozen=True)
class Club:
    name: str
    panels: tuple[tuple[str, Panel], ...]  # ("top", ...), ("bottom", ...)
    # Side cameras that each look back at their own house: house -> (which
    # side of the composite that camera is on, its paint as it sees it). None
    # for long cameras looking down the sheet, as Granite's do.
    end_cameras: dict | None = None
    # Long cameras looking down the sheet, as Granite's do, but fitted as the
    # end cameras are, from the whole ring and the paint: house -> (side,
    # paint). None fits them Granite's way.
    long_cameras: dict | None = None
    # A composite whose panels have no letterbox bars to find them by: fixed.
    # A broadcast that cuts between camera layouts (DFW's): the name of the
    # layout (curling_score.broadcast) every frame is converted through before
    # anything reads it. None: the stream is read as it is.
    broadcast_layout: str | None = None
    # Each stream is one game of ``scheduled_ends`` (DFW's): no second game,
    # and ends past the last are dropped unless they break a tie
    # (`segment.one_game`, `timeline.past_scheduled`).
    # Where the overheads show only the houses (DFW): the long camera behind the
    # thrower times the far hog line (`fartime.time_far_crossings_from_long_camera`),
    # and places the guards resting beyond this far in front of the tee, which no
    # panel shows (`game/longguards.py`). None: no long-camera guards.
    far_hog_from_long: bool = False
    guards_from_long_m: float | None = None
    # How long after its far hog crossing a guard nothing saw arrive is read
    # (`longguards.AFTER_FAR_S` where None).
    guards_after_far_s: float | None = None
    one_game_per_stream: bool = False
    scheduled_ends: int | None = None
    panel_layout: PanelLayout | None = None
    # The rows of the side views that are ice and not broadcast graphics.
    side_rows: tuple[int, int] | None = None
    # A composite whose side cameras are not either side of a centre strip of
    # overheads (Rochester's sit above them): each one's rect, by side.
    side_rects: dict | None = None
    # Rows of each long camera that hold a logo painted on the ice that both
    # see, to tie the two cameras' fits together by (`logotie`): side -> rows.
    logo_rows: dict | None = None
    # The YouTube channels that carry this club's stream, so a worker given
    # only a video can pick the profile.
    channel_ids: tuple[str, ...] = ()
    # Detectors trained for this club's stream, as file names in weights/;
    # None runs Granite's (`weights.DEFAULT_NAME`, `weights.SIDE_NAME`). The
    # environment variables there still win. A worker claims jobs under one
    # overhead model, so a club with its own must be chosen by the worker's
    # CLUB, not by a channel id.
    overhead_model: str | None = None
    side_model: str | None = None
    # What this club's stones really look like, where they are not red and
    # yellow: class colour -> {"name", "color"}. The detector has two classes
    # and everything downstream calls them red and yellow; this only changes
    # what a page says and draws (`timeline.build_document`'s ``stones``).
    stone_display: dict | None = None
    # A wall scoreboard with a camera of its own at a fixed place in the
    # composite (`game/fixedboard.py`), read there instead of being found by
    # its markers. None: Granite's board, found and read by `game/scoreboard.py`.
    board: FixedBoard | None = None


# The two houses are played toward from opposite directions, and Granite's
# composite shows them so: stones enter the top panel from below.
GRANITE = Club("granite", (
    ("top", Panel("bottom", GRANITE_HOUSE)),
    ("bottom", Panel("top", GRANITE_HOUSE)),
))

# On Cincinnati's end cameras the red reads pink (S 50-76, V 210+) and the
# black grey (V 117-143 against ice at 225).
_END_PINK = (((0, 35, 120), (10, 255, 255)), ((165, 35, 120), (179, 255, 255)))
_END_GREY = ((0, 0, 0), (179, 45, 160))

# A centre column of red house, club logo, blue house. Both houses are shown
# with their front at the top, read from the lettering against the end
# cameras. The red house paints 12-to-8 red and 8-to-4 black around a white
# 4-foot; the blue house paints 12-to-8 blue and no 4-foot at all, only the
# club's logo.
CINCINNATI = Club("cincinnati", (
    ("top", Panel("top", HousePaint(twelve_ft=RED_HSV, four_ft=(DARK_HSV,),
                                    four_ft_edge="inner"))),
    ("bottom", Panel("top", HousePaint(twelve_ft=(BLUE_HSV,)))),
), end_cameras={
    # The red house's camera is on the right of the composite, the blue's on
    # the left; each sits above its own hog line.
    "top": ("right", EndPaint(ring=_END_PINK, inner_radius_m=C.R_4FT_M, also=(_END_GREY,))),
    "bottom": ("left", EndPaint(ring=(BLUE_HSV,), inner_radius_m=C.R_8FT_M)),
},
    # ds17b read the "Cincy Light" sponsor ring as red stones, so the red
    # house never emptied (cin1); ds13e lost the stone under the thrower's
    # hand and under the sweepers on the end cameras (cin2, cin3).
    overhead_model="cin1a-11n.pt", side_model="cin3a.pt")

# Swift Current's broadcast (SSN, 1920x1080): two house-only overheads framed
# in white with a rotating sponsor tile between them, and long cameras either
# side, as at Granite -- the left one looks down at the top house. The houses
# paint 12-to-8 red and a dark 4-foot around a red button; both are shown with
# their front at the top. The hog lines are dark and there is no painted
# centre line, so the sidelines give it. The score bar starts at row 990.
SWIFT_CURRENT = Club("swift-current", (
    ("top", Panel("top", HousePaint(twelve_ft=RED_HSV, four_ft=(DARK_HSV,),
                                    four_ft_edge="outer"))),
    ("bottom", Panel("top", HousePaint(twelve_ft=RED_HSV, four_ft=(DARK_HSV,),
                                       four_ft_edge="outer"))),
), long_cameras={
    house: (side, EndPaint(ring=RED_HSV, inner_radius_m=C.R_8FT_M, hog="dark", centre="sidelines"))
    for house, side in (("top", "left"), ("bottom", "right"))
}, panel_layout=PanelLayout(top=(730, 8, 460, 454), bottom=(730, 613, 460, 454)),
    side_rows=(0, 990),
    # The Pepsi logo at centre ice, near the bottom of both long cameras.
    logo_rows={"left": (770, 990), "right": (800, 990)})

# Ardsley's stream (1920x1080): Granite's arrangement -- two overheads
# stacked in a centre strip, top house entered from below, and long cameras
# either side, the left one looking down at the top house -- but framed in
# thin navy and gold lines rather than letterbox bars, so the panels are
# fixed. The houses paint 12-to-8 blue around a red 4-foot. The wall behind
# each house is the same blue, so the long cameras' views start below it;
# the sponsor bar starts at row 1018. Hog lines are dark. The overheads'
# ice is tinted blue (H 107-114, S 40-73) and passes BLUE_HSV; the ring is
# H ~120, S 180+.
_ARDSLEY_BLUE = ((115, 120, 30), (135, 255, 255))
ARDSLEY = Club("ardsley", (
    ("top", Panel("bottom", HousePaint(twelve_ft=(_ARDSLEY_BLUE,), four_ft=RED_HSV))),
    ("bottom", Panel("top", HousePaint(twelve_ft=(_ARDSLEY_BLUE,), four_ft=RED_HSV))),
), long_cameras={
    house: (side, EndPaint(ring=(BLUE_HSV,), inner_radius_m=C.R_8FT_M, hog="dark"))
    for house, side in (("top", "left"), ("bottom", "right"))
}, panel_layout=PanelLayout(top=(821, 7, 278, 498), bottom=(821, 515, 278, 488)),
    side_rows=(335, 1015), channel_ids=("UCyU3Hul8S0_AqhYnqNMuGRw",))

# Martensville's broadcast (SSN for CurlingZone, 1920x1080): Swift Current's
# arrangement -- two overheads in a centre strip framed in blue, both with the
# front of the house at the top, long cameras either side with the left one
# looking down at the top house. The house is a brewery's logo: a yellow band
# whose outer edge is the 12-foot circle (stones agree, 0.29 m at the scale it
# gives) and whose inner edge is 1.30 m out, not the 8-foot; the thin circle
# inside it is decoration, not the 4-foot. The overhead tiles are stretched,
# 0.94-0.95 as tall as wide. Hog lines are blue; the centre line is painted,
# faintly, and sponsors' logos break it up on the right camera. The sheet's
# name bar starts at row 978. CurlingZone carries many venues, so no channel
# picks this profile.
_MARTENSVILLE_YELLOW = ((18, 60, 110), (40, 255, 255))
# The long cameras see the band paler and browner: H 19-27, S 57-93.
_MARTENSVILLE_FAR_YELLOW = ((12, 35, 80), (40, 255, 255))
_MARTENSVILLE_HOUSE = HousePaint(twelve_ft=(_MARTENSVILLE_YELLOW,), inner_radius_m=1.30,
                                 fit_aspect=True)
MARTENSVILLE = Club("martensville", (
    ("top", Panel("top", _MARTENSVILLE_HOUSE)),
    ("bottom", Panel("top", _MARTENSVILLE_HOUSE)),
), long_cameras={
    house: (side, EndPaint(ring=(_MARTENSVILLE_FAR_YELLOW,), inner_radius_m=1.30, hog="blue",
                          centre_min_rows=40))
    for house, side in (("top", "left"), ("bottom", "right"))
}, panel_layout=PanelLayout(top=(728, 7, 468, 462), bottom=(728, 608, 468, 459)),
    side_rows=(330, 975),
    # overhead-3 read the logo's hop cones and lettering as yellow stones all
    # game, so the house never emptied (mv1).
    overhead_model="mv1a.pt")

# DFW Curling Club's broadcast (Dallas, 1920x1080) as `scripts/dallas/normalize.py`
# rewrites it: the stream cuts every half minute between a three-panel view and a
# score view of the house in play, and the normaliser maps the score view back into
# the three-panel one. That is Granite's arrangement -- two overheads in a centre
# strip, long cameras either side -- with no bars between the panels, both houses
# front at the top, and the left long camera looking down at the BOTTOM house. The
# houses paint 12-to-8 blue around a red 4-foot, with the club's logo on the
# button. Hog lines are dark grey; the centre line is painted. The stones are green
# and yellow; green is the red_stone class. The overheads are exposed darker
# than Granite's (value p95 ~145 against 185-204, lights fully on). The worker
# converts the raw stream through the 5U event's layout (`broadcast_layout`)
# before anything reads it. Its own models mean no channel id: a DFW worker is
# set up with CLUB=dallas (a worker loads one overhead model).
_DFW_HOUSE = HousePaint(twelve_ft=(BLUE_HSV,), four_ft=RED_HSV, lit_min_p95=120.0)
DALLAS = Club("dallas", (
    ("top", Panel("top", _DFW_HOUSE)),
    ("bottom", Panel("top", _DFW_HOUSE)),
), long_cameras={
    house: (side, EndPaint(ring=(BLUE_HSV,), inner_radius_m=C.R_8FT_M, hog="dark"))
    for house, side in (("top", "right"), ("bottom", "left"))
}, panel_layout=PanelLayout(top=(764, 0, 379, 526), bottom=(764, 526, 379, 554)),
    broadcast_layout="dfw-5u", one_game_per_stream=True, scheduled_ends=8,
    far_hog_from_long=True, guards_from_long_m=3.3,
    # The long cameras' ice starts below the far wall: the clubhouse window
    # above it holds a blue neon cowboy hat, which in the 5U Qualifier's
    # framing (46wEMds_tYQ) outweighs the ring and was fitted as the house.
    side_rows=(390, 1080),
    # overhead-3 and long-1 have never seen a green stone: they missed DFW's
    # or read them as yellow (dfw1, dfw2).
    overhead_model="dfw1b.pt", side_model="dfw2c.pt")

# Rochester Curling Club's stream (one YouTube channel a sheet, 1920x1080,
# measured on Go_JOSxJPsQ, sheet A): two end cameras fill the top of the frame
# side by side, each above its own hog line looking back at its own house, as
# Cincinnati's do. The overheads are two small insets in the bottom corners,
# framed in blue, showing the house only (about 82 px/m) with the hack end at
# the top, so stones enter from the bottom of both. A camera on the wall
# scoreboard fills the bottom centre. The left house paints 12-to-8 teal
# around a purple 4-foot and a white button; the right house the reverse. The
# paint is pale on video (S 20-80 against ice at S < 12) and the frame's blue
# (H 101-103, S 150+) sits between the two hues. Hog lines are dark grey; the
# centre line is painted. The stones are red and blue.
_RCC_TEAL = ((70, 18, 60), (99, 140, 240))
_RCC_PURPLE = ((112, 18, 60), (145, 140, 240))
ROCHESTER = Club("rochester", (
    ("top", Panel("bottom", HousePaint(twelve_ft=(_RCC_TEAL,), four_ft=(_RCC_PURPLE,)))),
    ("bottom", Panel("bottom", HousePaint(twelve_ft=(_RCC_PURPLE,), four_ft=(_RCC_TEAL,)))),
), end_cameras={
    "top": ("left", EndPaint(ring=(_RCC_TEAL,), inner_radius_m=C.R_8FT_M, hog="dark",
                             hog_search_rows=340)),
    "bottom": ("right", EndPaint(ring=(_RCC_PURPLE,), inner_radius_m=C.R_8FT_M, hog="dark",
                             hog_search_rows=340)),
}, panel_layout=PanelLayout(top=(6, 733, 310, 341), bottom=(1604, 734, 310, 340)),
    side_rects={"left": (6, 6, 950, 838), "right": (964, 6, 950, 838)},
    one_game_per_stream=True,
    # The overheads end 2 m in front of the tee, so a guard is in neither: the
    # end camera facing the house places it (`game/longguards.py`). Read 10 s
    # after the far hog line: Go_JOSxJPsQ end 3's blue guard crossed at 38:26,
    # was still sliding at 3.7 m at 38:32 and stopped at 2.4 m by 38:36.
    guards_from_long_m=1.7, guards_after_far_s=10.0,
    # One channel a sheet, @RCCStreamingSheetA to D, each stream one game.
    # Everything here was measured on sheet A (UCC4CItKubmNVSPpsDInEcWQ);
    # sheet C (UCsAcOSWFFZDKce1DL5umYOA) is painted the same way. Its own
    # models mean no channel id picks this profile: a worker is set up with
    # CLUB=rochester, as Dallas's is.
    # overhead-3 has never seen a blue stone and missed every one (rcc1);
    # blue is the yellow_stone class.
    # long-1 found fewer than one blue stone in four on the end cameras, and
    # half its boxes were not stones (rcc2).
    overhead_model="rcc1b.pt", side_model="rcc2b.pt",
    stone_display={"yellow": {"name": "Blue", "color": "#4d8ef0"}},
    # The board camera, bottom centre, as sheet A frames it: red's cards hang
    # on the red band above the strip, blue's on the pale band below.
    board=FixedBoard(rect=(322, 850, 1276, 226), top="red", bottom="yellow"))

# Sheets B and D: the same composite, the two houses' paint the other way
# round -- purple on the left, teal on the right (channels
# UCeANiSRDAxfXybHkgQ0iY4w and UCBhd8WiPmssoGcoYVSGcXJQ). Measured on
# Df66u7Sv84c (B, 2026-11-10) and Vu6sd-fo0PE (D, 2026-11-09), the end
# cameras also on JA_qWEzaABk (B, 2026-11-09, a stream of an empty sheet);
# `datasets/rcc-sheets.md` has the numbers.
# The left camera's purple is held to V 100 and up: sheet B's left camera
# looks down the dark strip between sheets B and A (H 114, S 29, V 85-100),
# which the house's purple (V 120 and up) otherwise runs into as one blob.
_RCC_PURPLE_END = ((112, 18, 100), (145, 140, 240))
ROCHESTER_BD = replace(
    ROCHESTER, name="rochester-bd",
    panels=(("top", ROCHESTER.panels[1][1]), ("bottom", ROCHESTER.panels[0][1])),
    end_cameras={"top": ("left", replace(ROCHESTER.end_cameras["bottom"][1], ring=(_RCC_PURPLE_END,))),
                 "bottom": ("right", ROCHESTER.end_cameras["top"][1])},
    # Each sheet's board camera frames its board differently: rochester-b and
    # rochester-d say where. This profile is their common paint and cameras.
    board=None)
# The board camera's rectangle is the composite's, the same on every sheet;
# where the strip of numerals falls inside it is not. Sheet B's board sits
# lower and further right, the BLANK ENDS box from 0.88 of the width, and its
# camera is soft: the black cards blur to V 75-115, and an 8 read at 0.986,
# short of the reader's 0.99.
ROCHESTER_B = replace(ROCHESTER_BD, name="rochester-b", board=replace(
    ROCHESTER.board, strip_x=(0.125, 0.875), card_v=100))
# Sheet D's fills the width: the strip's "1" starts at 0.115, "18" ends at 0.865.
ROCHESTER_D = replace(ROCHESTER_BD, name="rochester-d", board=replace(
    ROCHESTER.board, strip_x=(0.105, 0.875)))
# Sheet C (R-7qQORH0dQ, 2026-11-09): painted as A, but its left end camera
# sees the teal bluer (H 100-101) than A's (H 95), so its band runs to H 106 --
# short of the purple (112) and with the composite's frame blue (H 101-103)
# kept out by its saturation (150+). The board's "18" ends at 0.92, past
# sheet A's strip. Its right end camera stops short of its hog line: the
# board camera's picture starts above it, so that fit fails ("no dark hog
# line in view") and, as analyze stands, so do both end cameras' splits.
ROCHESTER_C = replace(
    ROCHESTER, name="rochester-c",
    end_cameras={"top": ("left", replace(ROCHESTER.end_cameras["top"][1],
                                         ring=(((70, 18, 60), (106, 140, 240)),))),
                 "bottom": ROCHESTER.end_cameras["bottom"]},
    # Its camera is bright: the cards read navy, V 105-125, the red band 150 and
    # up. The top team's cards hang lower than on A, over the strip's top edge:
    # cut off there, a 2 read at 0.55.
    board=replace(ROCHESTER.board, strip_x=(0.125, 0.925), card_v=130, top_row=(1.10, -0.12)))

CLUBS = {c.name: c for c in (GRANITE, CINCINNATI, SWIFT_CURRENT, ARDSLEY, MARTENSVILLE, DALLAS,
                             ROCHESTER, ROCHESTER_BD, ROCHESTER_B, ROCHESTER_C, ROCHESTER_D)}


def for_channel(channel_id) -> Club:
    """The club whose stream a YouTube channel carries; Granite otherwise."""
    for club in CLUBS.values():
        if channel_id and channel_id in club.channel_ids:
            return club
    return GRANITE
