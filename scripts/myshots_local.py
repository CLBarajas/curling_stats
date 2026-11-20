#!/usr/bin/env python
"""My shots on your own computer: your games, your rocks, no accounts.

    python scripts/myshots_local.py out/myshots.json [--port 8810] [--out out]

The lineup file names you, your position, and each game you played with its
run and your team's colour:

    {"team": "Bauman", "position": "third", "name": "Chris",
     "games": [{"date": "2026-11-04", "sheet": "A", "video_id": "Go_JOSxJPsQ",
                "color": "red", "against": "Pulli", "run": "rcc-1104-v17"}, ...]}

`color` is the stones' key in the timeline: red or yellow (yellow shows as
blue at a club whose second colour is blue). `run` is a directory under
--out holding a timeline.json; a game with no run yet is skipped and listed.

What runs is the real service (service/api.py) in memory, as
scripts/devserve.py does: each run is published through the worker routes,
then a play is saved for each game through PUT /api/me/plays, so the report
is exactly what My shots shows on a hosted site. The one difference is who
you are: auth.LocalPerson, signed in already, so the page needs no Firebase.
The server binds 127.0.0.1 only. Nothing is written to disk; every start
rebuilds it from the lineup and the runs, so a re-run shows on a restart.
"""
import argparse
import dataclasses
import json
import pathlib
import secrets
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]

from fastapi.testclient import TestClient  # noqa: E402
from starlette.middleware.trustedhost import TrustedHostMiddleware  # noqa: E402

from curling_score import timeline as timeline_mod  # noqa: E402
from curling_score.service import auth as auth_mod  # noqa: E402
from curling_score.service import site as site_mod  # noqa: E402
from curling_score.service.api import Settings, create_app  # noqa: E402
from curling_score.service.records import User  # noqa: E402
from curling_score.service.repo import MemoryRepo  # noqa: E402
from curling_score.service.store import MemoryStore  # noqa: E402
from curling_score.service.youtube import FakeYouTube, VideoMeta  # noqa: E402

CHANNEL = "UClocal-club"           # every game's channel: the one allowed
# New each start, like the person's token: a fixed one would open the worker
# and admin routes to anything that can reach the port.
WORKER_TOKEN = secrets.token_urlsafe(24)
ADMIN_TOKEN = secrets.token_urlsafe(24)
WORKER = {"Authorization": f"Bearer {WORKER_TOKEN}"}
# The only names this server answers to. A page elsewhere that points its own
# name at 127.0.0.1 (DNS rebinding) still sends its own name, and is refused.
HOSTS = ["127.0.0.1", "localhost"]
SHEETS = {"A": 1, "B": 2, "C": 3, "D": 4}


def sheet_number(sheet) -> int | None:
    if isinstance(sheet, int):
        return sheet
    return SHEETS.get(str(sheet or "").strip().upper())


def publish(c, store, yt, game: dict, doc: dict, fmt: str, who: dict) -> str:
    """Submit ``game``'s video and play the worker through to a published
    run, the way a hosted site gets one. Returns the game's source id."""
    vid = game["video_id"]
    played = datetime.fromisoformat(game["date"]).replace(hour=19, tzinfo=timezone.utc)
    title = f"{played:%-m/%-d} - Sheet {game.get('sheet') or '?'}"
    duration = float((doc.get("source") or {}).get("duration_s") or 0.0) or 4 * 3600.0
    yt.add(VideoMeta(vid, title, CHANNEL, duration, "none", played))
    r = c.post("/api/submissions", json={"url": f"https://youtu.be/{vid}",
                     # A stream over five hours needs its game's start.
                     "start_s": float(doc["games"][0].get("start_s") or 0.0)},
               headers={"X-Forwarded-For": "127.0.0.1", **who})
    if r.status_code not in (200, 201):
        raise SystemExit(f"{vid}: could not submit: {r.status_code} {r.text}")
    job = c.post("/api/worker/claim", headers=WORKER,
                 json={"worker_id": "home", "model_id": "local"}).json()["job"]
    if job is None:
        raise SystemExit(f"{vid}: no job to claim")
    plan = c.post(f"/api/worker/jobs/{job['id']}/artifacts", headers=WORKER,
                  json={"worker_id": "home",
                        "files": [{"name": "timeline.json", "bytes": 1}]}).json()
    for up in plan["uploads"]:
        store.put_bytes(up["key"], json.dumps(doc).encode())
    done = {"worker_id": "home", "title": title, "channel_id": CHANNEL,
            "duration_s": duration, "sheet": sheet_number(game.get("sheet")),
            "games": [timeline_mod.game_summary(g) for g in doc["games"]],
            "timings": {}, "format": fmt}
    r = c.post(f"/api/worker/jobs/{job['id']}/complete", headers=WORKER, json=done)
    if r.status_code != 200:
        raise SystemExit(f"{vid}: could not complete: {r.status_code} {r.text}")
    games = [g for g in c.get("/api/games").json()["games"]
             if g.get("video_id") == vid and g.get("source_id")]
    if not games:
        raise SystemExit(f"{vid}: published, but no game in the catalogue")
    return games[0]["source_id"]


def slot_of(position: str, doc: dict) -> int:
    fmt = doc.get("format") or {}
    positions = fmt.get("positions") or ["lead", "second", "third", "skip"]
    want = position.strip().lower()
    aliases = {"vice": "third", "vice-skip": "third", "vice skip": "third"}
    want = aliases.get(want, want)
    if want not in positions:
        raise SystemExit(f"position {position!r} is not one of {positions}")
    return positions.index(want) + 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("lineup", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "out",
                    help="where the runs named in the lineup are (default: out)")
    ap.add_argument("--port", type=int, default=8810)
    ap.add_argument("--club", default="Rochester Curling Club")
    ap.add_argument("--tz", default="America/New_York")
    args = ap.parse_args()

    lineup = json.loads(args.lineup.read_text())
    me = auth_mod.LocalPerson(uid="local", name=lineup.get("name") or lineup.get("team") or "Me")
    # Granite's site with the club's name and clock, and no pages a person on
    # their own computer has no use for (submitting, practice, labelling).
    profile = dataclasses.replace(
        site_mod.GRANITE, name="localhost", club_name=args.club, tz=args.tz,
        nav_hidden=frozenset({"/submit", "/practice", "/label", "/playlists", "/ice"}))
    base = f"http://127.0.0.1:{args.port}"
    settings = Settings(public_base_url=base, worker_token=WORKER_TOKEN,
                        admin_token=ADMIN_TOKEN, allowed_channels={CHANNEL},
                        model_id="local", max_queued=999, rate_hour=999, rate_day=9999,
                        club_tz=args.tz, site=profile)
    repo, store, yt = MemoryRepo(), MemoryStore(), FakeYouTube()
    app = create_app(repo, store, yt, settings, auth=me)
    # Before the first request: Starlette takes no middleware once started.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=HOSTS)
    c = TestClient(app, base_url=base)
    who = {"Authorization": f"Bearer {me.token}"}
    # Validated is all naming teams needs (api_set_teams); admin would also
    # open the user and role routes, which one person here has no use for.
    repo.put_user(User(id=me.uid, created_at=datetime.now(timezone.utc), name=me.name,
                       role="validated"))

    say = lambda line: print(line, flush=True)
    say(f"\n  {lineup.get('team', '?')}, {lineup.get('position', '?')}")
    for game in lineup.get("games", []):
        label = f"{game.get('date')} sheet {game.get('sheet')} v {game.get('against')}"
        run = game.get("run")
        if not run or not game.get("color") or not game.get("video_id"):
            say(f"  skipped   {label}: {game.get('note') or 'no run yet'}")
            continue
        path = args.out / run / "timeline.json"
        if not path.is_file():
            say(f"  skipped   {label}: no {path}")
            continue
        doc = json.loads(path.read_text())
        fmt = (doc.get("format") or {}).get("name") or "fours"
        sid = publish(c, store, yt, game, doc, fmt, who)
        body = {"path": f"/g/{sid}/", "color": game["color"],
                "slot": slot_of(lineup["position"], doc)}
        # Team names live on the game, not in the run (api_set_teams).
        teams = (doc["games"][0].get("teams") or {})
        names = {k: (teams.get(k) or {}).get("name") for k in ("red", "yellow")}
        if any(names.values()):
            c.post(f"/api/games/{sid}/teams", json=names, headers=who)
        r = c.put(f"/api/me/plays/{sid}", json=body, headers=who)
        if r.status_code != 200:
            raise SystemExit(f"{label}: could not save the play: {r.status_code} {r.text}")
        say(f"  loaded    {label}: {run}  ->  {base}/g/{sid}/")

    say(f"\n  My shots   {base}/shots")
    say(f"  games      {base}/games\n")

    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
