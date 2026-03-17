import tempfile
import unittest
import runpy
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np


_IMPORT_ERROR = None


try:
    from hackagent.attacks.techniques.autodan_turbo.strategy_library import (
        StrategyLibrary,
    )
except Exception as exc:  # pragma: no cover - optional dependency guard
    StrategyLibrary = None
    _IMPORT_ERROR = exc


@unittest.skipIf(
    StrategyLibrary is None, f"StrategyLibrary unavailable: {_IMPORT_ERROR}"
)
class TestStrategyLibrary(unittest.TestCase):
    def test_module_import_guard_when_faiss_missing(self):
        module_path = (
            Path(__file__).resolve().parents[4]
            / "hackagent"
            / "attacks"
            / "techniques"
            / "autodan_turbo"
            / "strategy_library.py"
        )
        original_import = __import__

        def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "faiss":
                raise ImportError("missing faiss")
            return original_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=_fake_import):
            with self.assertRaises(ImportError):
                runpy.run_path(str(module_path))

    def test_init_passes_embedding_api_kwargs(self):
        lib = StrategyLibrary(
            embedding_model="openai/text-embedding-3-small",
            embedding_api_key="k",
            embedding_api_base="http://base",
            logger=MagicMock(),
        )
        self.assertEqual(lib.embedding_api_key, "k")
        self.assertEqual(lib.embedding_api_base, "http://base")

    def test_add_merge_all_size(self):
        lib = StrategyLibrary(logger=MagicMock())
        lib.logger.info.reset_mock()  # ignore the init-time "Embedding backend" log

        s = {
            "Strategy": "S",
            "Definition": "D",
            "Example": ["e1"],
            "Score": [1.0],
            "Embeddings": [np.array([0.1, 0.2], dtype=np.float32)],
        }
        lib.add(s, notify=False)
        lib.add({**s, "Example": ["e2"], "Score": [2.0]}, notify=False)

        self.assertEqual(lib.size(), 1)
        self.assertEqual(lib.all()["S"]["Definition"], "D")
        self.assertEqual(len(lib.all()["S"]["Example"]), 2)
        lib.logger.info.assert_not_called()

    def test_add_notify_logs(self):
        logger = MagicMock()
        lib = StrategyLibrary(logger=logger)
        logger.info.reset_mock()  # ignore the init-time "Embedding backend" log
        lib.add({"Strategy": "S", "Definition": "D"}, notify=True)
        logger.info.assert_called_once()

    @patch("litellm.embedding")
    def test_embed_success(self, mock_litellm_embedding):
        emb_item = MagicMock()
        emb_item.embedding = [0.0, 1.0]
        mock_litellm_embedding.return_value = MagicMock(data=[emb_item])

        lib = StrategyLibrary(
            embedding_model="openai/text-embedding-3-small",
            logger=MagicMock(),
        )
        vec = lib.embed("hello")
        self.assertEqual(vec.dtype, np.float32)
        self.assertEqual(vec.shape[0], 2)

    @patch("litellm.embedding")
    def test_embed_failure_returns_none(self, mock_litellm_embedding):
        mock_litellm_embedding.side_effect = RuntimeError("embed failed")
        logger = MagicMock()
        lib = StrategyLibrary(
            embedding_model="openai/text-embedding-3-small",
            logger=logger,
        )
        self.assertIsNone(lib.embed("hello"))
        logger.error.assert_called_once()

    @patch(
        "hackagent.attacks.techniques.autodan_turbo.strategy_library.faiss.IndexFlatL2"
    )
    def test_retrieve_high_score_returns_single_best(self, mock_index_cls):
        class _FakeIndex:
            def __init__(self, _dim):
                pass

            def add(self, _matrix):
                return None

            def search(self, _query, n):
                d = np.arange(n, dtype=np.float32).reshape(1, -1)
                i = np.arange(n, dtype=np.int64).reshape(1, -1)
                return d, i

        mock_index_cls.side_effect = _FakeIndex

        lib = StrategyLibrary(logger=MagicMock())
        lib.embed = MagicMock(return_value=np.array([0.1, 0.1], dtype=np.float32))
        lib.library = {
            "A": {
                "Strategy": "A",
                "Definition": "DA",
                "Example": ["ea"],
                "Score": [6.0],
                "Embeddings": [np.array([0.1, 0.1], dtype=np.float32)],
            },
            "B": {
                "Strategy": "B",
                "Definition": "DB",
                "Example": ["eb"],
                "Score": [1.0],
                "Embeddings": [np.array([0.2, 0.2], dtype=np.float32)],
            },
        }

        valid, out = lib.retrieve("query", k=2)
        self.assertTrue(valid)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["Strategy"], "A")

    def test_retrieve_on_empty_library(self):
        lib = StrategyLibrary(logger=MagicMock())
        valid, out = lib.retrieve("query", k=2)
        self.assertTrue(valid)
        self.assertEqual(out, [])

    @patch(
        "hackagent.attacks.techniques.autodan_turbo.strategy_library.faiss.IndexFlatL2"
    )
    def test_retrieve_moderate_scores_returns_valid_list(self, mock_index_cls):
        class _FakeIndex:
            def __init__(self, _dim):
                pass

            def add(self, _matrix):
                return None

            def search(self, _query, n):
                d = np.arange(n, dtype=np.float32).reshape(1, -1)
                i = np.arange(n, dtype=np.int64).reshape(1, -1)
                return d, i

        mock_index_cls.side_effect = _FakeIndex

        lib = StrategyLibrary(logger=MagicMock())
        lib.embed = MagicMock(return_value=np.array([0.1, 0.1], dtype=np.float32))
        lib.library = {
            "A": {
                "Strategy": "A",
                "Definition": "DA",
                "Example": ["ea"],
                "Score": [3.0],
                "Embeddings": [np.array([0.1, 0.1], dtype=np.float32)],
            }
        }
        valid, out = lib.retrieve("query", k=2)
        self.assertTrue(valid)
        self.assertEqual(len(out), 1)

    @patch(
        "hackagent.attacks.techniques.autodan_turbo.strategy_library.faiss.IndexFlatL2"
    )
    def test_retrieve_moderate_scores_respect_k_break(self, mock_index_cls):
        class _FakeIndex:
            def __init__(self, _dim):
                pass

            def add(self, _matrix):
                return None

            def search(self, _query, n):
                d = np.arange(n, dtype=np.float32).reshape(1, -1)
                i = np.arange(n, dtype=np.int64).reshape(1, -1)
                return d, i

        mock_index_cls.side_effect = _FakeIndex

        lib = StrategyLibrary(logger=MagicMock())
        lib.embed = MagicMock(return_value=np.array([0.1, 0.1], dtype=np.float32))
        lib.library = {
            "A": {
                "Strategy": "A",
                "Definition": "DA",
                "Example": ["ea"],
                "Score": [3.0],
                "Embeddings": [np.array([0.1, 0.1], dtype=np.float32)],
            },
            "B": {
                "Strategy": "B",
                "Definition": "DB",
                "Example": ["eb"],
                "Score": [4.0],
                "Embeddings": [np.array([0.12, 0.12], dtype=np.float32)],
            },
        }
        valid, out = lib.retrieve("query", k=1)
        self.assertTrue(valid)
        self.assertEqual(len(out), 1)

    @patch(
        "hackagent.attacks.techniques.autodan_turbo.strategy_library.faiss.IndexFlatL2"
    )
    def test_retrieve_low_scores_returns_ineffective(self, mock_index_cls):
        class _FakeIndex:
            def __init__(self, _dim):
                pass

            def add(self, _matrix):
                return None

            def search(self, _query, n):
                d = np.arange(n, dtype=np.float32).reshape(1, -1)
                i = np.arange(n, dtype=np.int64).reshape(1, -1)
                return d, i

        mock_index_cls.side_effect = _FakeIndex

        lib = StrategyLibrary(logger=MagicMock())
        lib.embed = MagicMock(return_value=np.array([0.1, 0.1], dtype=np.float32))
        lib.library = {
            "A": {
                "Strategy": "A",
                "Definition": "DA",
                "Example": ["ea"],
                "Score": [1.0],
                "Embeddings": [np.array([0.1, 0.1], dtype=np.float32)],
            }
        }
        valid, out = lib.retrieve("query", k=2)
        self.assertFalse(valid)
        self.assertEqual(len(out), 1)

    @patch(
        "hackagent.attacks.techniques.autodan_turbo.strategy_library.faiss.IndexFlatL2"
    )
    def test_retrieve_duplicate_strategy_updates_average_and_example(
        self, mock_index_cls
    ):
        class _FakeIndex:
            def __init__(self, _dim):
                pass

            def add(self, _matrix):
                return None

            def search(self, _query, n):
                d = np.arange(n, dtype=np.float32).reshape(1, -1)
                i = np.arange(n, dtype=np.int64).reshape(1, -1)
                return d, i

        mock_index_cls.side_effect = _FakeIndex

        lib = StrategyLibrary(logger=MagicMock())
        lib.embed = MagicMock(return_value=np.array([0.1, 0.1], dtype=np.float32))
        lib.library = {
            "A": {
                "Strategy": "A",
                "Definition": "DA",
                "Example": ["e1", "e2"],
                "Score": [2.0, 3.0],
                "Embeddings": [
                    np.array([0.1, 0.1], dtype=np.float32),
                    np.array([0.11, 0.11], dtype=np.float32),
                ],
            }
        }
        valid, out = lib.retrieve("query", k=1)
        self.assertTrue(valid)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["Strategy"], "A")

    def test_retrieve_returns_empty_for_embed_none_or_invalid_embeddings(self):
        lib = StrategyLibrary(logger=MagicMock())
        lib.library = {
            "A": {
                "Strategy": "A",
                "Definition": "DA",
                "Example": ["ea"],
                "Score": [1.0],
                "Embeddings": ["not-numpy"],
            }
        }
        lib.embed = MagicMock(return_value=None)
        valid, out = lib.retrieve("query", k=2)
        self.assertTrue(valid)
        self.assertEqual(out, [])

        lib.embed = MagicMock(return_value=np.array([0.1, 0.2], dtype=np.float32))
        valid, out = lib.retrieve("query", k=2)
        self.assertTrue(valid)
        self.assertEqual(out, [])

    def test_save_load(self):
        lib = StrategyLibrary(logger=MagicMock())
        lib.library = {
            "S": {
                "Strategy": "S",
                "Definition": "D",
                "Example": [],
                "Score": [],
                "Embeddings": [],
            }
        }

        with tempfile.TemporaryDirectory() as td:
            path = f"{td}/strategy_lib"
            lib.save(path)
            lib2 = StrategyLibrary(logger=MagicMock())
            lib2.load(path)
            self.assertIn("S", lib2.library)

    def test_load_missing_file_noop(self):
        lib = StrategyLibrary(logger=MagicMock())
        lib.load("non_existing_path_12345")
        self.assertEqual(lib.library, {})


if __name__ == "__main__":
    unittest.main()
