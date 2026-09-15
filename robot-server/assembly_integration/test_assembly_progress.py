import tempfile
import unittest
from pathlib import Path

from assembly_progress import ProgressStore, load_recipe, DEFAULT_RECIPE


class ProgressTest(unittest.TestCase):
    def test_idempotent_completion_and_next_step(self):
        recipe = load_recipe(DEFAULT_RECIPE)
        with tempfile.TemporaryDirectory() as directory:
            store = ProgressStore(Path(directory) / "test.sqlite3")
            cycle = store.start(recipe["recipe_version"], "test-cycle")
            first, inserted = store.record(cycle, recipe["steps"][0], "ASSEMBLED", 1)
            repeated, inserted_again = store.record(cycle, recipe["steps"][0], "ASSEMBLED", 1)
            self.assertTrue(inserted); self.assertFalse(inserted_again)
            self.assertEqual(first["event_id"], repeated["event_id"])
            state = store.state(cycle, recipe)
            self.assertEqual(state["completed_count"], 1)
            self.assertEqual(state["next_step"]["order"], 2)
            self.assertEqual(state["assembled"][0]["part_id"], "GPU")
            self.assertEqual(state["next_step"]["slot_code"], "HBM-01")

    def test_out_of_order_completion_is_rejected(self):
        recipe = load_recipe(DEFAULT_RECIPE)
        with tempfile.TemporaryDirectory() as directory:
            store = ProgressStore(Path(directory) / "test.sqlite3")
            cycle = store.start(recipe["recipe_version"], "order-test")
            with self.assertRaisesRegex(ValueError, "out of order"):
                store.record(cycle, recipe["steps"][1], "ASSEMBLED", 1)


if __name__ == "__main__": unittest.main()
