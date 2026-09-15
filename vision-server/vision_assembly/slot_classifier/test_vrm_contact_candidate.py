import unittest
import numpy as np
import torch
from train_vrm_contact_candidate import windows, ContactTail


class WindowTests(unittest.TestCase):
    def test_rgb_and_fixed_coordinates_preserved(self):
        rgb=np.arange(256*256*3,dtype=np.uint32).reshape(256,256,3)
        original=rgb.copy()
        patches=windows(rgb)
        self.assertEqual(patches.shape,(8,96,96,3))
        np.testing.assert_array_equal(patches[0],rgb[:96,:96])
        np.testing.assert_array_equal(patches[4],rgb[160:256,160:256])
        np.testing.assert_array_equal(rgb,original)

    def test_invalid_input_rejected(self):
        with self.assertRaises(ValueError):
            windows(np.zeros((224,224,3)))

    def test_tail_backprop_keeps_window_batch_contract(self):
        tail=ContactTail(torch.nn.Conv2d(4,1280,1))
        x=torch.ones(2,8,4,1,1)
        output=tail(x)
        self.assertEqual(tuple(output.shape),(2,2))
        output.sum().backward()
        self.assertIsNotNone(tail.tail.weight.grad)
        self.assertIsNotNone(tail.head.weight.grad)


if __name__=='__main__':
    unittest.main()
