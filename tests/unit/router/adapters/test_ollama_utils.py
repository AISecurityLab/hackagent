# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for Ollama utility functions."""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from hackagent.router.adapters.ollama_utils import (
    get_installed_ollama_models,
    is_model_installed,
    is_ollama_available,
    is_ollama_running,
    normalize_ollama_model_aliases,
    pull_ollama_model,
)


class TestOllamaUtils(unittest.TestCase):
    """Test suite for Ollama utility functions."""

    def test_normalize_ollama_model_aliases_with_latest_tag(self):
        """Test normalizing model names with explicit :latest tag."""
        aliases = normalize_ollama_model_aliases("gemma3:latest")
        self.assertEqual(aliases, {"gemma3:latest", "gemma3"})

    def test_normalize_ollama_model_aliases_without_tag(self):
        """Test normalizing model names without tag."""
        aliases = normalize_ollama_model_aliases("gemma3")
        self.assertEqual(aliases, {"gemma3", "gemma3:latest"})

    def test_normalize_ollama_model_aliases_with_specific_tag(self):
        """Test normalizing model names with specific tag."""
        aliases = normalize_ollama_model_aliases("gemma3:4b")
        self.assertEqual(aliases, {"gemma3:4b"})

    @patch("hackagent.router.adapters.ollama_utils.shutil.which")
    def test_is_ollama_available_true(self, mock_which):
        """Test checking Ollama availability when installed."""
        mock_which.return_value = "/usr/local/bin/ollama"
        self.assertTrue(is_ollama_available())
        mock_which.assert_called_once_with("ollama")

    @patch("hackagent.router.adapters.ollama_utils.shutil.which")
    def test_is_ollama_available_false(self, mock_which):
        """Test checking Ollama availability when not installed."""
        mock_which.return_value = None
        self.assertFalse(is_ollama_available())
        mock_which.assert_called_once_with("ollama")

    @patch("hackagent.router.adapters.ollama_utils.urlopen")
    def test_is_ollama_running_true(self, mock_urlopen):
        """Test checking if Ollama is running when it is."""
        mock_response = MagicMock()
        mock_urlopen.return_value.__enter__.return_value = mock_response
        self.assertTrue(is_ollama_running())

    @patch("hackagent.router.adapters.ollama_utils.urlopen")
    def test_is_ollama_running_false(self, mock_urlopen):
        """Test checking if Ollama is running when it's not."""
        mock_urlopen.side_effect = Exception("Connection refused")
        self.assertFalse(is_ollama_running())

    @patch("hackagent.router.adapters.ollama_utils.subprocess.run")
    @patch("hackagent.router.adapters.ollama_utils.is_ollama_available")
    def test_get_installed_ollama_models_success(self, mock_available, mock_subprocess):
        """Test getting installed models when Ollama is available."""
        mock_available.return_value = True
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout=(
                "NAME                  ID              SIZE      MODIFIED\n"
                "gemma3:4b            abc123          2.4 GB    2 hours ago\n"
                "llama2-uncensored    def456          3.8 GB    1 day ago\n"
            ),
        )

        models = get_installed_ollama_models()
        self.assertEqual(models, {"gemma3:4b", "llama2-uncensored"})

    @patch("hackagent.router.adapters.ollama_utils.is_ollama_available")
    def test_get_installed_ollama_models_not_installed(self, mock_available):
        """Test getting installed models when Ollama is not installed."""
        mock_available.return_value = False

        with self.assertRaises(RuntimeError) as context:
            get_installed_ollama_models()

        self.assertIn("not installed", str(context.exception))

    @patch("hackagent.router.adapters.ollama_utils.subprocess.run")
    @patch("hackagent.router.adapters.ollama_utils.is_ollama_available")
    def test_get_installed_ollama_models_command_failure(
        self, mock_available, mock_subprocess
    ):
        """Test getting installed models when command fails."""
        mock_available.return_value = True
        mock_subprocess.return_value = MagicMock(
            returncode=1, stderr="Error listing models"
        )

        with self.assertRaises(RuntimeError) as context:
            get_installed_ollama_models()

        self.assertIn("Failed to read", str(context.exception))

    def test_is_model_installed_with_exact_match(self):
        """Test checking if model is installed with exact match."""
        installed = {"gemma3:4b", "llama2-uncensored"}
        self.assertTrue(is_model_installed("gemma3:4b", installed))

    def test_is_model_installed_with_alias_match(self):
        """Test checking if model is installed with alias match."""
        installed = {"gemma3:latest", "llama2-uncensored"}
        self.assertTrue(is_model_installed("gemma3", installed))

    def test_is_model_installed_not_found(self):
        """Test checking if model is installed when not found."""
        installed = {"gemma3:4b", "llama2-uncensored"}
        self.assertFalse(is_model_installed("mistral", installed))

    @patch("hackagent.router.adapters.ollama_utils.is_model_installed")
    @patch("hackagent.router.adapters.ollama_utils.is_ollama_available")
    def test_pull_ollama_model_already_installed(self, mock_available, mock_installed):
        """Test pulling model when already installed."""
        mock_available.return_value = True
        mock_installed.return_value = True

        result = pull_ollama_model("gemma3:4b")
        self.assertTrue(result)

    @patch("hackagent.router.adapters.ollama_utils.is_ollama_available")
    def test_pull_ollama_model_not_available(self, mock_available):
        """Test pulling model when Ollama is not available."""
        mock_available.return_value = False

        result = pull_ollama_model("gemma3:4b")
        self.assertFalse(result)

    @patch("hackagent.router.adapters.ollama_utils.subprocess.run")
    @patch("hackagent.router.adapters.ollama_utils.is_model_installed")
    @patch("hackagent.router.adapters.ollama_utils.is_ollama_available")
    def test_pull_ollama_model_success(
        self, mock_available, mock_installed, mock_subprocess
    ):
        """Test successfully pulling a model."""
        mock_available.return_value = True
        mock_installed.return_value = False
        mock_subprocess.return_value = MagicMock(returncode=0)

        result = pull_ollama_model("gemma3:4b")
        self.assertTrue(result)
        mock_subprocess.assert_called_once()

    @patch("hackagent.router.adapters.ollama_utils.subprocess.run")
    @patch("hackagent.router.adapters.ollama_utils.is_model_installed")
    @patch("hackagent.router.adapters.ollama_utils.is_ollama_available")
    def test_pull_ollama_model_failure(
        self, mock_available, mock_installed, mock_subprocess
    ):
        """Test failing to pull a model."""
        mock_available.return_value = True
        mock_installed.return_value = False
        mock_subprocess.return_value = MagicMock(returncode=1, stderr="Model not found")

        result = pull_ollama_model("invalid-model")
        self.assertFalse(result)

    @patch("hackagent.router.adapters.ollama_utils.subprocess.run")
    @patch("hackagent.router.adapters.ollama_utils.is_model_installed")
    @patch("hackagent.router.adapters.ollama_utils.is_ollama_available")
    def test_pull_ollama_model_timeout(
        self, mock_available, mock_installed, mock_subprocess
    ):
        """Test timeout while pulling a model."""
        mock_available.return_value = True
        mock_installed.return_value = False
        mock_subprocess.side_effect = subprocess.TimeoutExpired("ollama", 300)

        result = pull_ollama_model("large-model")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
