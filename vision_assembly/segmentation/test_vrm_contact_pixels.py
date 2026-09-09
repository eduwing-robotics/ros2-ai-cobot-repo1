import unittest
import numpy as np
from audit_vrm_contact_pixels import contact_features


class ContactTests(unittest.TestCase):
    def test_raw_input_unchanged(self):
        image=np.zeros((241,189,3),np.uint8)
        original=image.copy()
        features,windows=contact_features(image,(0,0,126,160))
        np.testing.assert_array_equal(image,original)
        self.assertEqual(features['raw'].shape,(8,32,32))
        self.assertEqual(len(windows),8)

    def test_translation_not_removed(self):
        image=np.zeros((241,189,3),np.uint8)
        image[32:52,24:44]=255
        shifted=np.roll(image,5,axis=1)
        a,_=contact_features(image,(0,0,126,160))
        b,_=contact_features(shifted,(0,0,126,160))
        self.assertGreater(float(np.abs(a['raw']-b['raw']).sum()),0)

    def test_clipping_rejected(self):
        with self.assertRaises(ValueError):
            contact_features(np.zeros((30,30,3),np.uint8),(0,0,126,160))


if __name__=='__main__':
    unittest.main()
