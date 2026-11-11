"""What the end-camera lines of `lines.py` say across a game, against the two
things that can check them: the broom the slide was aimed at, and where the
far end's camera saw the rock come in.

    python scripts/rcc-lines/stats.py out/rcc-1104-fit/timeline.json out/rcc-lines/end1.json out/rcc-lines/ends2-8.json
"""
import json
import sys

import numpy as np

TEE, HOG = 34.747, 6.401
HOG_Y = TEE - HOG


def main():
    doc = json.load(open(sys.argv[1]))
    lines = {}
    for p in sys.argv[2:]:
        lines.update(json.load(open(p)))
    rows = []
    for e in doc["games"][0]["ends"]:
        for s in e["shots"]:
            l = lines.get(f"{e['number']}.{s['number']}")
            if not l or not l["delivery"]:
                continue
            d = np.array(l["delivery"])                    # t, y, x
            yp = TEE - d[:, 1]
            last = (yp >= HOG - 3.0)
            if last.sum() < 15:
                continue
            b, a = np.polyfit(d[last, 1], d[last, 2], 1)   # x = a + b*y
            x_hog = a + b * HOG_Y
            broom, start = s["target_broom"], l["start"]
            need = aim_hog = None
            if broom and start:
                need = (broom["x"] - start["x"]) / (broom["y"] - start["y"])
                aim_hog = start["x"] + need * (HOG_Y - start["y"])
            far = l["path"][0] if l["path"] and l["path"][0][0] > 5.5 else None
            rest = l["path"][-1] if far else None
            rows.append(dict(end=e["number"], rock=s["number"], house=e["house"], color=s["color"],
                             split=s["long_split_s"], b=b, need=need, x_hog=x_hog,
                             off_hog=None if aim_hog is None else x_hog - aim_hog,
                             at_broom=None if not broom else a + b * broom["y"] - broom["x"],
                             far_pred=a + b * far[0] if far else None, far_obs=far[1] if far else None,
                             rest_x=rest[1] if far else None, rest_y=rest[0] if far else None,
                             type=s["shot_type"], rel=l.get("release")))
    f = lambda v, w=6, p=2: " " * w if v is None else f"{v:+{w}.{p}f}"
    print("end rk col    type     split  slope    need   x_hog off_hog  miss@broom | far: pred    obs   diff | in-house dx")
    for r in rows:
        diff = None if r["far_obs"] is None else r["far_obs"] - r["far_pred"]
        inh = None if r["far_obs"] is None else r["rest_x"] - r["far_obs"]
        print(f"{r['end']:2d} {r['rock']:2d} {r['color']:6s} {r['type']:8s} {f(r['split'], 5, 1)} {f(-r['b'], 7, 4)} "
              f"{f(None if r['need'] is None else -r['need'], 7, 4)} {f(r['x_hog'])} {f(r['off_hog'])} {f(r['at_broom'], 8)}"
              f"   | {f(r['far_pred'])} {f(r['far_obs'])} {f(diff)} | {f(inh)}")
    for house in ("top", "bottom", None):
        sel = [r for r in rows if r["need"] is not None and (house is None or r["house"] == house)]
        if len(sel) < 5:
            continue
        x = np.array([-r["need"] for r in sel]); y = np.array([-r["b"] for r in sel])
        k, c = np.polyfit(x, y, 1)
        off = np.array([r["off_hog"] for r in sel]); miss = np.array([r["at_broom"] for r in sel])
        print(f"\nhouse played to {house or 'either'}: {len(sel)} rocks with a broom and a start")
        print(f"  slope read = {k:.2f} x slope to the broom {c:+.4f}  (r {np.corrcoef(x, y)[0, 1]:.2f})")
        print(f"  off the start-to-broom line at the hog line: median {np.median(off) * 100:+.0f} cm, "
              f"IQR {np.percentile(off, 25) * 100:+.0f}..{np.percentile(off, 75) * 100:+.0f}, |median| {np.median(abs(off)) * 100:.0f}")
        print(f"  the last 3 m extended to the broom: median {np.median(miss) * 100:+.0f} cm, "
              f"IQR {np.percentile(miss, 25) * 100:+.0f}..{np.percentile(miss, 75) * 100:+.0f}, |median| {np.median(abs(miss)) * 100:.0f}")
    both = [r for r in rows if r["far_obs"] is not None]
    if both:
        diff = np.array([r["far_obs"] - r["far_pred"] for r in both])
        inh = np.array([r["rest_x"] - r["far_obs"] for r in both])
        ran = np.array([r["far_obs"] - r["rest_y"] * 0 for r in both])
        print(f"\n{len(both)} rocks seen at both ends. Far hog line, seen less straight-on from the slide: "
              f"median {np.median(diff) * 100:+.0f} cm, |median| {np.median(abs(diff)) * 100:.0f} cm")
        moved = abs(inh) > 0.1
        print(f"  of the {moved.sum()} that moved over 10 cm across inside the far hog line, "
              f"{(np.sign(diff[moved]) == np.sign(inh[moved])).sum()} had already left the slide's line the same way")
        pred = np.array([r["far_pred"] for r in both]); obs = np.array([r["far_obs"] for r in both])
        k, c = np.polyfit(pred, obs, 1)
        print(f"  where it came in = {k:.2f} x where the slide pointed {c:+.2f} m  (r {np.corrcoef(pred, obs)[0, 1]:.2f})")


if __name__ == "__main__":
    main()
