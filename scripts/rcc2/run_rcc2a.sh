#!/bin/bash
# rcc2a: cin3a's weights (Cincinnati's end cameras) tuned on the reviewed rcc2
# frames alone (Rochester's end cameras, red and blue stones). The long-camera
# recipe of dfw2a, fewer epochs: this starts from a trained model.
set -uo pipefail
cd "$(dirname "$0")/../.."
./.venv/bin/yolo detect train model=weights/cin3a.pt data=out/rcc2/folds/a/data.yaml \
  imgsz=800 epochs=100 patience=25 batch=8 device=${DEVICE:-cpu} seed=0 \
  mosaic=1.0 close_mosaic=10 scale=0.4 degrees=0.0 fliplr=0.5 flipud=0.0 \
  hsv_h=0.015 hsv_s=0.6 hsv_v=0.4 \
  workers=2 plots=False project="$PWD/out/rcc2/runs" name=rcc2a exist_ok=True
