"""CLI tests use local synthetic inputs only; no runtime integration imports."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from vision_assembly.hybrid_inspection.run_hbm_pin_profile_review import load_rgb, main
from vision_assembly.hybrid_inspection.test_hbm_pin_profile_candidate import STRIPS, synthetic


class ReviewCliTests(unittest.TestCase):
    def test_cli_gates_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ref = synthetic()
            sample = ref.copy()
            sample[36:42, 8:20] = 45
            for name, rgb in [('reference', ref), ('sample', sample)]:
                self.assertTrue(cv2.imwrite(str(root / (name+'.png')),
                                           cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)))
            strips = root / 'strips.json'
            strips.write_text(json.dumps(STRIPS))
            base = ['--image', str(root/'sample.png'), '--strips', str(strips),
                    '--reference', str(root/'reference.png')]
            flags = ['--reference-reliable', '--orientation-usable', '--quality-usable',
                     '--angle-error', '0']
            variants = [[], flags, flags[1:], flags[:1]+flags[2:],
                        flags[:2]+flags[3:], flags[:-2], flags[:-1]+['nan']]
            for i, options in enumerate(variants):
                out = root / str(i)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(base+options+['--output-dir', str(out)]), 0)
                report = json.loads((out/'review.json').read_text())
                inputs = report['evidence']['review_inputs']
                for key, file in [('source_sha256', root/'sample.png'),
                                  ('reference_sha256', root/'reference.png'),
                                  ('strips_sha256', strips)]:
                    self.assertEqual(inputs[key], hashlib.sha256(file.read_bytes()).hexdigest())
                self.assertEqual(report['status'], 'UNKNOWN')
                self.assertEqual(report['evidence']['diagnostic'],
                                 'ROW_DEFICIT_CANDIDATE' if i == 1 else 'UNKNOWN')
                self.assertIsNotNone(cv2.imread(str(out/'profile_overlay.png')))
                original = (out/'review.json').read_bytes()
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(base+['--output-dir', str(out)])
                self.assertEqual((out/'review.json').read_bytes(), original)
            with contextlib.redirect_stdout(io.StringIO()):
                main(base[:-2]+['--output-dir', str(root/'no_reference')])
            report = json.loads((root/'no_reference/review.json').read_text())
            self.assertIsNone(report['evidence']['review_inputs']['reference_sha256'])
            self.assertEqual(report['status'], 'UNKNOWN')

    def test_rgb_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rgb = synthetic()
            rgb[0, 0] = (200, 30, 10)
            cv2.imwrite(str(root/'rgb.png'), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
            np.testing.assert_array_equal(load_rgb(root/'rgb.png'), rgb)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(['--image', str(root/'missing.png'), '--strips', str(root/'none.json'),
                      '--output-dir', str(root/'out')])
            self.assertFalse((root/'out').exists())


if __name__ == '__main__':
    unittest.main()
