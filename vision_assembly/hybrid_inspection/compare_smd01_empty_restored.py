"""Diagnostic same-board-coordinate SMD01 pair; no local fit or model changes."""
import argparse
import json
import hashlib
from pathlib import Path

import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('empty', type=Path)
    parser.add_argument('restored', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--first-label', default='EMPTY')
    parser.add_argument('--second-label', default='RESTORED')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    panels = []
    sources = []
    for index, (label, directory) in enumerate([(args.first_label, args.empty), (args.second_label, args.restored)]):
        source = directory / 'aligned_board.png'
        blob = source.read_bytes()
        board = cv2.imdecode(np.frombuffer(blob, np.uint8), cv2.IMREAD_COLOR)
        if board is None or board.shape[:2] != (1266, 1600):
            raise ValueError(f'Unexpected canonical image: {source}')
        crop = board[1014:1154, 1181:1361].copy()
        # Labels are display text only, never output paths.
        name = 'empty.png' if index == 0 else 'restored.png'
        if not cv2.imwrite(str(args.output / name), crop):
            raise OSError('Cannot save comparison crop')
        sources.append(dict(label=label, source=str(source), sha256=hashlib.sha256(blob).hexdigest(), crop=name))
        enlarged = cv2.resize(crop, (720, 560), interpolation=cv2.INTER_NEAREST)
        panel = cv2.copyMakeBorder(enlarged, 40, 0, 0, 0, cv2.BORDER_CONSTANT,
                                   value=(25, 25, 25))
        cv2.putText(panel, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
                    .8, (240, 240, 240), 1, cv2.LINE_AA)
        panels.append(panel)
    if not cv2.imwrite(str(args.output / 'comparison.png'), np.hstack(panels)):
        raise OSError('Cannot save comparison')
    (args.output / 'comparison.json').write_text(json.dumps({
        'empty_report': str(args.empty), 'restored_report': str(args.restored),
        'origin': [1181, 1014], 'size': [180, 140],
        'sources': sources,
        'policy': 'Board registration only. Native RGB crops, no local alignment, '
                  'no normalization, no certified wall or clearance measurement.'
    }, indent=2))


if __name__ == '__main__':
    main()
