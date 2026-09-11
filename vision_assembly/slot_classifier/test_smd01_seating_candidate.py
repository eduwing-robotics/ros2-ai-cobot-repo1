from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pytest
from smd01_seating_candidate import assign_split, unique_cases, fixed_crop
from train_smd01_seating_candidate import metric


def test_day_split_keeps_later_capture_out_of_fit():
    assert assign_split('s22_inspection_roi_20260904_140754.png')=='train'
    assert assign_split('s22_inspection_roi_20260907_120931.png')=='validation'
    assert assign_split('s22_inspection_roi_20260910_100210.png')=='later_replay'
    with pytest.raises(ValueError):assign_split('unknown.png')


def test_identical_image_cannot_leak_across_sets_or_conflict_in_truth():
    row=dict(source_sha256='a'*64,label='LIP_SEATING',split='train')
    assert len(unique_cases([row,dict(row)]))==1
    for changes in [dict(split='later_replay'),dict(label='NORMAL_SEATED')]:
        with pytest.raises(ValueError):unique_cases([row,{**row,**changes}])
    with pytest.raises(ValueError):unique_cases([{**row,'label':'POSITION_ERROR'}])


def test_fixed_crop_preserves_image_relative_displacement_and_pixels():
    image=np.zeros((1266,1600,3),np.uint8);image[1040,1210]=[12,34,56]
    crop=fixed_crop(image)
    assert np.array_equal(crop[26,29],[12,34,56])
    moved=np.zeros_like(image);moved[1047,1210]=[12,34,56]
    assert np.array_equal(fixed_crop(moved)[33,29],crop[26,29])
    crop[:]=0
    assert np.array_equal(image[1040,1210],[12,34,56])
    with pytest.raises(ValueError):fixed_crop(image[:100])


def test_soft_predictions_do_not_count_as_qualified_detection():
    rows=[dict(label='NORMAL_SEATED'),dict(label='LIP_SEATING')]
    result=metric(rows,[.42,.61])
    assert result['raw_correct']==2
    assert result['at_fixed_090_gate']==dict(correct=0,incorrect=0,abstain=2)
    wrong=metric(rows,[.92,.04])
    assert wrong['false_normal']==1 and wrong['false_seating']==1
    assert wrong['at_fixed_090_gate']['incorrect']==2
    for bad in [[float('nan'),.5],[-.1,.6],[.5],[1.1,.6]]:
        with pytest.raises(ValueError):metric(rows,bad)
