import numpy as np
from probe_smd01_independent_outline import measure


def test_body_and_source_preserved():
    image = np.zeros((140,180,3), dtype=np.uint8)
    image[45:85,60:120] = 220
    original = image.copy()
    result = measure(image)
    assert result['valid']
    assert result['center'] == [89.5,64.5]
    assert np.array_equal(image,original)


def test_empty_rejected():
    assert not measure(np.zeros((140,180,3),dtype=np.uint8))['valid']


def test_full_bright_frame_rejected():
    assert not measure(np.full((140,180,3),220,dtype=np.uint8))['valid']


def test_multiple_bodies_rejected():
    image = np.zeros((140,180,3),dtype=np.uint8)
    image[30:60,30:60] = 220
    image[70:100,90:120] = 220
    assert measure(image)['reason'] == 'MULTIPLE_BRIGHT_BODIES'


def test_small_glint_rejected():
    image = np.zeros((140,180,3),dtype=np.uint8)
    image[65:75,85:95] = 255
    assert not measure(image)['valid']


def test_invalid_window_rejected():
    assert not measure(None)['valid']
    assert not measure(np.zeros((70,90,3),dtype=np.uint8))['valid']
