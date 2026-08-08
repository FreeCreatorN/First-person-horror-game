import ast
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "Scripts" / "UpgradeMainHomeHeroAsset.py"


class MainHomeHeroUpgradeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_sign_card_has_full_aspect_uv_correction(self):
        self.assertIn(
            'sign_uv.set_editor_property("v_tiling", -(408.0 / 88.0))',
            self.source,
        )
        self.assertIn(
            'sign_uv.set_editor_property("u_tiling", -1.0)',
            self.source,
        )
        self.assertIn("unreal.MaterialExpressionAdd", self.source)
        self.assertIn(
            "unreal.MaterialExpressionConstant2Vector",
            self.source,
        )

    def test_sign_card_is_offset_and_inside_the_approved_envelope(self):
        center = (0.0, -398.55, 319.0)
        size_x = 408.0
        size_z = 88.0
        self.assertGreater(center[1], -400.0)
        self.assertLess(center[1], 400.0)
        self.assertGreaterEqual(center[0] - size_x * 0.5, -250.0)
        self.assertLessEqual(center[0] + size_x * 0.5, 250.0)
        self.assertGreaterEqual(center[2] - size_z * 0.5, 1.0)
        self.assertLessEqual(center[2] + size_z * 0.5, 401.0)
        self.assertIn(
            "builder.rectangle_xz(\n"
            "        (0.0, -398.55, 319.0),\n"
            "        408.0,\n"
            "        88.0,",
            self.source,
        )

    def test_sign_material_is_masked_and_two_sided(self):
        self.assertIn(
            '_safe_set(material, "blend_mode", '
            "unreal.BlendMode.BLEND_MASKED)",
            self.source,
        )
        self.assertIn('_safe_set(material, "two_sided", True)', self.source)
        self.assertIn(
            '_safe_set(material, "opacity_mask_clip_value", 0.18)',
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
