#!/usr/bin/env python3
"""Create deterministic train/val folders from labeled GPU OBB images."""
import argparse
import random
import shutil
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();root=Path(__file__).parent/'dataset'
    parser.add_argument('--images',type=Path,default=root/'images/unlabeled')
    parser.add_argument('--labels',type=Path,default=root/'labels/all')
    parser.add_argument('--val-ratio',type=float,default=.2);parser.add_argument('--seed',type=int,default=42)
    args=parser.parse_args()
    pairs=[]
    for image in sorted([*args.images.glob('*.jpg'),*args.images.glob('*.png')]):
        label=args.labels/f'{image.stem}.txt'
        if label.is_file() and label.read_text(encoding='utf-8').strip():pairs.append((image,label))
    if len(pairs)<10:raise RuntimeError(f'Need at least 10 labeled images; found {len(pairs)}')
    random.Random(args.seed).shuffle(pairs);val_count=max(1,round(len(pairs)*args.val_ratio))
    for split,items in [('val',pairs[:val_count]),('train',pairs[val_count:])]:
        image_dir=root/f'images/{split}';label_dir=root/f'labels/{split}'
        # These folders are generated copies. Rebuild them so a changed split
        # never leaves an image in both train and validation.
        if image_dir.exists():shutil.rmtree(image_dir)
        if label_dir.exists():shutil.rmtree(label_dir)
        image_dir.mkdir(parents=True,exist_ok=True);label_dir.mkdir(parents=True,exist_ok=True)
        for image,label in items:
            shutil.copy2(image,image_dir/image.name);shutil.copy2(label,label_dir/label.name)
        print(f'{split}: {len(items)} images')


if __name__=='__main__':main()
