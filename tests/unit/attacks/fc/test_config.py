# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for FC-Attack and tFC-Attack configuration."""

import unittest

from hackagent.attacks.techniques.fc.config import (
    DEFAULT_FC_CONFIG,
    DEFAULT_TFC_CONFIG,
    FCConfig,
    FCParams,
    tFCConfig,
    tFCParams,
    StepGeneratorConfig,
)


class TestDefaultFlowchartConfig(unittest.TestCase):
    """Test DEFAULT_FC_CONFIG structure and values."""

    def test_has_required_keys(self):
        required = ["attack_type", "fc_params", "step_generator"]
        for key in required:
            self.assertIn(key, DEFAULT_FC_CONFIG)

    def test_attack_type(self):
        self.assertEqual(DEFAULT_FC_CONFIG["attack_type"], "fc")

    def test_default_layout(self):
        self.assertEqual(DEFAULT_FC_CONFIG["fc_params"]["layout"], "vertical")

    def test_default_num_steps(self):
        self.assertEqual(DEFAULT_FC_CONFIG["fc_params"]["num_steps"], 6)

    def test_default_truncate_last_step(self):
        self.assertTrue(DEFAULT_FC_CONFIG["fc_params"]["truncate_last_step"])

    def test_default_dpi(self):
        self.assertEqual(DEFAULT_FC_CONFIG["fc_params"]["dpi"], 600)

    def test_default_image_dimensions(self):
        params = DEFAULT_FC_CONFIG["fc_params"]
        self.assertEqual(params["image_width"], 1200)
        self.assertEqual(params["image_height"], 800)

    def test_step_generator_is_none_by_default(self):
        self.assertIsNone(DEFAULT_FC_CONFIG["step_generator"])


class TestDefaultFlowchartTextConfig(unittest.TestCase):
    """Test DEFAULT_TFC_CONFIG structure and values."""

    def test_has_required_keys(self):
        required = ["attack_type", "tfc_params", "step_generator"]
        for key in required:
            self.assertIn(key, DEFAULT_TFC_CONFIG)

    def test_attack_type(self):
        self.assertEqual(DEFAULT_TFC_CONFIG["attack_type"], "tFC")

    def test_default_text_format(self):
        self.assertEqual(DEFAULT_TFC_CONFIG["tfc_params"]["text_format"], "dot")

    def test_default_layout(self):
        self.assertEqual(DEFAULT_TFC_CONFIG["tfc_params"]["layout"], "vertical")

    def test_default_num_steps(self):
        self.assertEqual(DEFAULT_TFC_CONFIG["tfc_params"]["num_steps"], 6)

    def test_no_image_params(self):
        params = DEFAULT_TFC_CONFIG["tfc_params"]
        self.assertNotIn("dpi", params)
        self.assertNotIn("image_width", params)
        self.assertNotIn("image_height", params)

    def test_step_generator_is_none_by_default(self):
        self.assertIsNone(DEFAULT_TFC_CONFIG["step_generator"])


class TestFlowchartParams(unittest.TestCase):
    """Test FlowchartParams Pydantic model validation."""

    def test_defaults(self):
        params = FCParams()
        self.assertEqual(params.layout, "vertical")
        self.assertEqual(params.dpi, 600)
        self.assertEqual(params.image_width, 1200)
        self.assertEqual(params.image_height, 800)
        self.assertEqual(params.font_size, 16)
        self.assertEqual(params.num_steps, 6)
        self.assertTrue(params.truncate_last_step)

    def test_valid_layouts(self):
        for layout in ("vertical", "horizontal", "tortuous", "s_shaped"):
            params = FCParams(layout=layout)
            self.assertEqual(params.layout, layout)

    def test_invalid_layout_rejected(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            FCParams(layout="diagonal")

    def test_dpi_bounds(self):
        from pydantic import ValidationError

        FCParams(dpi=72)  # minimum
        FCParams(dpi=1200)  # maximum
        with self.assertRaises(ValidationError):
            FCParams(dpi=50)
        with self.assertRaises(ValidationError):
            FCParams(dpi=2000)

    def test_num_steps_bounds(self):
        from pydantic import ValidationError

        FCParams(num_steps=2)  # minimum
        FCParams(num_steps=15)  # maximum
        with self.assertRaises(ValidationError):
            FCParams(num_steps=1)
        with self.assertRaises(ValidationError):
            FCParams(num_steps=16)


class TestFlowchartTextParams(unittest.TestCase):
    """Test FlowchartTextParams Pydantic model validation."""

    def test_defaults(self):
        params = tFCParams()
        self.assertEqual(params.layout, "vertical")
        self.assertEqual(params.text_format, "dot")
        self.assertEqual(params.num_steps, 6)
        self.assertTrue(params.truncate_last_step)

    def test_valid_text_formats(self):
        for fmt in ("dot", "mermaid", "tikz", "plantuml", "ascii"):
            params = tFCParams(text_format=fmt)
            self.assertEqual(params.text_format, fmt)

    def test_invalid_text_format_rejected(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            tFCParams(text_format="html")

    def test_num_steps_bounds(self):
        from pydantic import ValidationError

        tFCParams(num_steps=2)
        tFCParams(num_steps=15)
        with self.assertRaises(ValidationError):
            tFCParams(num_steps=0)


class TestFCConfig(unittest.TestCase):
    """Test FCConfig Pydantic model."""

    def test_from_dict_defaults(self):
        cfg = FCConfig.from_dict({})
        self.assertEqual(cfg.attack_type, "fc")
        self.assertEqual(cfg.output_dir, "./logs/fc")
        self.assertIsNone(cfg.step_generator)

    def test_from_dict_with_overrides(self):
        cfg = FCConfig.from_dict(
            {
                "fc_params": {"layout": "horizontal", "num_steps": 8},
                "step_generator": {"identifier": "gpt-4"},
            }
        )
        self.assertEqual(cfg.fc_params.layout, "horizontal")
        self.assertEqual(cfg.fc_params.num_steps, 8)
        self.assertEqual(cfg.step_generator["identifier"], "gpt-4")

    def test_to_dict_roundtrip(self):
        cfg = FCConfig.from_dict({"output_dir": "./custom_dir"})
        dumped = cfg.to_dict()
        self.assertEqual(dumped["attack_type"], "fc")
        self.assertEqual(dumped["output_dir"], "./custom_dir")
        self.assertIn("fc_params", dumped)


class TesttFCConfig(unittest.TestCase):
    """Test tFCConfig Pydantic model."""

    def test_from_dict_defaults(self):
        cfg = tFCConfig.from_dict({})
        self.assertEqual(cfg.attack_type, "tFC")
        self.assertEqual(cfg.output_dir, "./logs/tFC")
        self.assertEqual(cfg.tfc_params.text_format, "dot")

    def test_from_dict_with_overrides(self):
        cfg = tFCConfig.from_dict(
            {
                "tfc_params": {"text_format": "mermaid", "num_steps": 4},
            }
        )
        self.assertEqual(cfg.tfc_params.text_format, "mermaid")
        self.assertEqual(cfg.tfc_params.num_steps, 4)

    def test_to_dict_roundtrip(self):
        cfg = tFCConfig.from_dict({})
        dumped = cfg.to_dict()
        self.assertEqual(dumped["attack_type"], "tFC")
        self.assertIn("tfc_params", dumped)
        self.assertEqual(dumped["tfc_params"]["text_format"], "dot")


class TestStepGeneratorConfig(unittest.TestCase):
    """Test StepGeneratorConfig model."""

    def test_defaults(self):
        cfg = StepGeneratorConfig()
        self.assertEqual(cfg.identifier, "gemma3:4b")
        self.assertEqual(cfg.max_tokens, 512)
        self.assertEqual(cfg.temperature, 0.3)
        self.assertIsNone(cfg.api_key)

    def test_override(self):
        cfg = StepGeneratorConfig(identifier="gpt-4", api_key="sk-test")
        self.assertEqual(cfg.identifier, "gpt-4")
        self.assertEqual(cfg.api_key, "sk-test")


if __name__ == "__main__":
    unittest.main()
