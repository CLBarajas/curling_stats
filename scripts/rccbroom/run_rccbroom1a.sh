#!/bin/bash
# rccbroom1a: broom4 (Granite's long cameras) tuned on the reviewed rccbroom
# frames alone (Rochester's end cameras). rcc2a's recipe; no left-right flip
# was needed there and none is harmful here, a pad looks the same mirrored.
#   DEVICE=mps scripts/rccbroom/run_rccbroom1a.sh        (about 6 minutes)
set -uo pipefail
cd "$(dirname "$0")/../.."
./.venv/bin/yolo detect train model=weights/broom4.pt data=out/rccbroom1/folds/a/data.yaml \
  imgsz=800 epochs=100 patience=25 batch=8 device=${DEVICE:-cpu} seed=0 \
  mosaic=1.0 close_mosaic=10 scale=0.4 degrees=0.0 fliplr=0.5 flipud=0.0 \
  hsv_h=0.015 hsv_s=0.6 hsv_v=0.4 \
  workers=2 plots=False project="$PWD/out/rccbroom1/runs" name=rccbroom1a exist_ok=True
