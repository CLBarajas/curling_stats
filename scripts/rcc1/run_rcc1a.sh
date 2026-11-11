#!/bin/bash
# rcc1a: overhead-3's weights tuned on the reviewed rcc1 frames alone (Rochester's
# red and blue stones). overhead-3's augmentation; on the Mac's GPU.
set -uo pipefail
cd "$(dirname "$0")/../.."
./.venv/bin/yolo detect train model=weights/overhead-3.pt data=out/rcc1/folds/${FOLD:-a}/data.yaml \
  epochs=100 patience=25 batch=16 imgsz=640 device=${DEVICE:-mps} seed=0 deterministic=True \
  degrees=5.0 fliplr=0.5 flipud=0.0 mosaic=1.0 close_mosaic=8 \
  hsv_h=0.005 hsv_s=0.5 hsv_v=0.4 translate=0.1 scale=0.5 erasing=0.4 \
  workers=2 plots=False project="$PWD/out/rcc1/runs" name=${NAME:-rcc1a} exist_ok=True
