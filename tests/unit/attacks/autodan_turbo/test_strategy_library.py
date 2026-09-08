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

    @patch("litellm.completion")
    @patch("litellm.embedding")
    def test_normal_embedder_uses_provider_vectors(self, mock_embedding, mock_chat):
        mock_embedding.return_value = {"data": [{"embedding": [0.25, 0.75]}]}
        backend = MagicMock()
        lib = StrategyLibrary(
            embedder_config={
                "identifier": "embeddinggemma:300m",
                "endpoint": "http://localhost:11434",
                "agent_type": "OLLAMA",
            },
            backend=backend,
            logger=MagicMock(),
        )
        vec = lib.embed("retrieval context")
        np.testing.assert_array_equal(vec, [0.25, 0.75])
        self.assertEqual(vec.dtype, np.float32)
        mock_embedding.assert_called_once_with(
            model="openai/embeddinggemma:300m",
            custom_llm_provider="openai",
            api_base="http://localhost:11434/v1",
            api_key="ollama",
            encoding_format="float",
            input=["retrieval context"],
        )
        mock_chat.assert_not_called()
        self.assertEqual(backend.mock_calls, [])

    @patch("litellm.embedding", side_effect=RuntimeError("HTTP 400: unsupported model"))
    def test_external_failure_disables_without_local_fallback(self, mock_embedding):
        lib = StrategyLibrary(
            embedder_config={
                "identifier": "embeddinggemma:300m",
                "endpoint": "http://localhost:11434",
                "agent_type": "OLLAMA",
            },
            backend=MagicMock(),
            logger=MagicMock(),
        )
        with patch.object(lib, "_local_embed") as mock_local:
            self.assertIsNone(lib.embed("external failure"))
            self.assertIsNone(lib.embed("later request"))
        mock_local.assert_not_called()
        mock_embedding.assert_called_once()
        lib.logger.error.assert_called_once()

    @patch("litellm.embedding", side_effect=RuntimeError("unreachable"))
    def test_explicit_raise_policy(self, mock_embedding):
        lib = StrategyLibrary(embedder_config={"on_error": "raise"}, logger=MagicMock())
        with self.assertRaisesRegex(RuntimeError, "unreachable"):
            lib.embed("query")

    @patch("litellm.embedding")
    def test_local_modes_need_no_provider_or_credentials(self, mock_embedding):
        for kwargs in (
            {"embedder_config": {"identifier": "local/bag-of-words"}},
            {"embedding_model": "local/bag-of-words"},
            {"embedding_api_key": "legacy-key-only"},
        ):
            with self.subTest(kwargs=kwargs):
                lib = StrategyLibrary(**kwargs)
                vector = lib.embed("same text")
                self.assertEqual(vector.shape, (512,))
                np.testing.assert_array_equal(vector, lib.embed("same text"))
        mock_embedding.assert_not_called()

    @patch("litellm.embedding")
    def test_provider_vectors_drive_real_faiss_retrieval(self, mock_embedding):
        mock_embedding.side_effect = [
            {"data": [{"embedding": vector}]}
            for vector in ([10.0, 0.0], [0.0, 1.0], [0.0, 0.9])
        ]
        lib = StrategyLibrary(logger=MagicMock())
        for name in ("far", "near"):
            lib.add(
                {
                    "Strategy": name,
                    "Score": [6.0],
                    "Example": [name],
                    "Embeddings": [lib.embed(name)],
                }
            )
        valid, result = lib.retrieve("query")
        self.assertTrue(valid)
        self.assertEqual(result[0]["Strategy"], "near")
        self.assertEqual(mock_embedding.call_count, 3)

    @patch("litellm.embedding")
    def test_dimension_change_disables_retrieval(self, mock_embedding):
        mock_embedding.side_effect = [
            {"data": [{"embedding": [0.0, 1.0]}]},
            {"data": [{"embedding": [0.0, 1.0, 2.0]}]},
        ]
        lib = StrategyLibrary(logger=MagicMock())
        self.assertIsNotNone(lib.embed("first"))
        self.assertIsNone(lib.embed("second"))
        self.assertIn("dimension changed", lib._embedding_disabled_reason)

    @patch("litellm.embedding")
    def test_malformed_responses_never_fall_back(self, mock_embedding):
        for response in (
            None,
            {},
            {"data": []},
            {"choices": [{"text": "signature"}]},
            {"data": [{"embedding": []}]},
            {"data": [{"embedding": [float("nan")]}]},
        ):
            with self.subTest(response=response):
                mock_embedding.return_value = response
                lib = StrategyLibrary(logger=MagicMock())
                self.assertIsNone(lib.embed("query"))
                self.assertIsNotNone(lib._embedding_disabled_reason)

    def test_retrieval_skips_invalid_stored_vectors_and_preserves_score_alignment(self):
        lib = StrategyLibrary(logger=MagicMock())
        lib.embed = MagicMock(return_value=np.array([0.0, 1.0], dtype=np.float32))
        invalid = [
            np.array([]),
            np.array([0.0]),
            np.array([[0.0, 1.0]]),
            np.array([float("nan"), 1.0]),
            np.array([float("inf"), 1.0]),
        ]
        lib.add(
            {
                "Strategy": "valid",
                "Embeddings": invalid + [np.array([0.0, 1.0])],
                "Score": [0] * len(invalid) + [6],
                "Example": ["bad"] * len(invalid) + ["correct"],
            }
        )
        valid, result = lib.retrieve("query")
        self.assertTrue(valid)
        self.assertEqual(result[0]["Example"], "correct")

    def test_retrieval_rejects_invalid_query_before_faiss(self):
        lib = StrategyLibrary(logger=MagicMock())
        lib.add({"Strategy": "S", "Embeddings": [np.array([1.0, 2.0])]})
        for value in ([], [[1.0, 2.0]], [float("nan"), 1.0]):
            with self.subTest(value=value):
                lib.embed = MagicMock(return_value=np.array(value))
                self.assertEqual(lib.retrieve("query"), (True, []))

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

    def test_missing_embeddings_keep_examples_and_scores_aligned_on_merge(self):
        lib = StrategyLibrary(logger=MagicMock())
        lib.add(
            {"Strategy": "S", "Example": ["failed"], "Score": [0], "Embeddings": []}
        )
        lib.add(
            {
                "Strategy": "S",
                "Example": ["success"],
                "Score": [6],
                "Embeddings": [np.array([0.0, 1.0])],
            }
        )
        lib.embed = MagicMock(return_value=np.array([0.0, 1.0]))
        valid, result = lib.retrieve("query")
        self.assertTrue(valid)
        self.assertEqual(result[0]["Example"], "success")

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

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as td:
            path = f"{td}/strategy_lib"
            lib.save(path)
            lib2 = StrategyLibrary(logger=MagicMock())
            lib2.load(path)
            self.assertIn("S", lib2.library)

    def test_saved_vectors_are_only_reused_in_same_space(self):
        lib = StrategyLibrary(embedding_model="local/bag-of-words", logger=MagicMock())
        lib.add(
            {
                "Strategy": "S",
                "Score": [6],
                "Example": ["example"],
                "Embeddings": [lib.embed("example")],
            }
        )
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as td:
            path = f"{td}/strategy_lib"
            lib.save(path)
            compatible = StrategyLibrary(embedding_model="local/bag-of-words")
            compatible.load(path)
            np.testing.assert_array_equal(
                compatible.library["S"]["Embeddings"][0],
                lib.library["S"]["Embeddings"][0],
            )
            incompatible = StrategyLibrary(logger=MagicMock())
            incompatible.load(path)
            self.assertEqual(incompatible.library["S"]["Embeddings"], [None])
            self.assertEqual(incompatible.library["S"]["Example"], ["example"])

    def test_unversioned_normal_library_does_not_reuse_chat_hashes(self):
        import pickle

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as td:
            path = f"{td}/strategy_lib.pkl"
            with open(path, "wb") as file:
                pickle.dump(
                    {
                        "S": {
                            "Embeddings": [np.zeros(512)],
                            "Score": [6],
                            "Example": ["old"],
                        }
                    },
                    file,
                )
            lib = StrategyLibrary(logger=MagicMock())
            lib.load(path)
            self.assertEqual(lib.library["S"]["Embeddings"], [None])

    def test_provider_space_metadata_normalizes_urls_and_never_stores_keys(self):
        config = {
            "identifier": "embeddinggemma:300m",
            "agent_type": "OLLAMA",
            "endpoint": "http://ollama.test/api/embed",
            "api_key": "secret-embedding-key",
        }
        lib = StrategyLibrary(embedder_config=config)
        lib.add(
            {
                "Strategy": "S",
                "Score": [6],
                "Example": ["example"],
                "Embeddings": [np.array([0.0, 1.0])],
            }
        )
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as td:
            path = f"{td}/strategy_lib"
            lib.save(path)
            self.assertNotIn(b"secret-embedding-key", Path(path + ".pkl").read_bytes())
            compatible = StrategyLibrary(
                embedder_config={
                    **config,
                    "endpoint": "http://ollama.test/v1",
                    "api_key": "rotated-key",
                }
            )
            compatible.load(path)
            np.testing.assert_array_equal(
                compatible.library["S"]["Embeddings"][0], [0.0, 1.0]
            )
            incompatible = StrategyLibrary(
                embedder_config={**config, "identifier": "other-model"},
                logger=MagicMock(),
            )
            incompatible.load(path)
            self.assertEqual(incompatible.library["S"]["Embeddings"], [None])

    def test_load_missing_file_noop(self):
        lib = StrategyLibrary(logger=MagicMock())
        lib.load("non_existing_path_12345")
        self.assertEqual(lib.library, {})


if __name__ == "__main__":
    unittest.main()
