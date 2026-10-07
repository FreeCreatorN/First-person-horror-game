import ast
from pathlib import Path
import unittest


class SignOrientationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parents[1] / "Scripts/CreateOldTownDetailedProps.py"
        tree = ast.parse(source.read_text(encoding="utf-8-sig"))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == "_glyph_run_center")
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
        cls.center = staticmethod(namespace["_glyph_run_center"])

    def test_left_hand_stroke_is_on_positive_local_x(self):
        self.assertEqual(self.center(-39, 78, 0, 2, 3.9), 35.1)

    def test_right_hand_stroke_is_on_negative_local_x(self):
        self.assertAlmostEqual(self.center(-39, 78, 18, 20, 3.9), -35.1)

    def test_centered_stroke_remains_centered(self):
        self.assertEqual(self.center(-39, 78, 9, 11, 3.9), 0)


if __name__ == "__main__":
    unittest.main()
