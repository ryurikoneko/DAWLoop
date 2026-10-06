"""无宿主调用的全屏诊断采样；全景只保存到仓库外私有目录。"""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'research'))
from preview_pixel_observer import PixelObserver
from full_screen_preview_capture import FullScreenPreviewCapture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, default=3)
    parser.add_argument('--private-output', type=Path, required=True)
    args = parser.parse_args()
    output = args.private_output.resolve()
    if not 0 < args.duration <= 60 or output.is_relative_to(ROOT):
        raise ValueError('INVALID_PRIVATE_DIAGNOSTIC_OUTPUT')
    output.mkdir(parents=True, exist_ok=False)
    observer = PixelObserver(capture_factory=FullScreenPreviewCapture)
    try:
        observer.start()
        time.sleep(args.duration)
    finally:
        observer.stop()
    result = observer.result()
    result['scope'] = 'FULL_SCREEN_DIAGNOSTIC_ONLY'
    result['host_calls'] = 0
    result['runtime_state_emitted'] = False
    result['exact_set_verified'] = False
    result['full_frame_hashes'] = {}
    for name, frame in observer.full_frames.items():
        np.save(output/(name+'.npy'), frame)
        result['full_frame_hashes'][name] = hashlib.sha256(frame.tobytes()).hexdigest()
    with (output/'diagnostic.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(dict(scope=result['scope'], host_calls=0, frame_count=len(result['frames']),
        actual_fps=result['actual_fps'], error=result['error']), ensure_ascii=False))


if __name__ == '__main__':
    main()
