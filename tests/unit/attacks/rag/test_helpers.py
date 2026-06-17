# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from hackagent.attacks.techniques.rag import attack as rag_attack
from hackagent.attacks.techniques.rag.attack import (
    _deep_update,
    _split_internal_keys,
    _trim_payload_prefix_overlap,
    build_faiss_index,
    chunk_text,
    chunk_text_with_offsets,
    get_embeddings,
    parse_documents,
    search_index,
)

LOGGER = logging.getLogger("test.rag.helpers")


class TestDeepUpdate(unittest.TestCase):
    def test_recursive_merge(self):
        target = {"a": 1, "nested": {"x": 1, "y": 2}}
        source = {"nested": {"y": 20, "z": 30}, "b": 2}
        _deep_update(target, source)
        self.assertEqual(target["a"], 1)
        self.assertEqual(target["b"], 2)
        self.assertEqual(target["nested"], {"x": 1, "y": 20, "z": 30})

    def test_internal_keys_passed_by_reference(self):
        sentinel = object()
        target = {}
        _deep_update(target, {"_client": sentinel})
        self.assertIs(target["_client"], sentinel)

    def test_non_dict_overwrites(self):
        target = {"k": {"inner": 1}}
        _deep_update(target, {"k": [1, 2, 3]})
        self.assertEqual(target["k"], [1, 2, 3])


class TestSplitInternalKeys(unittest.TestCase):
    def test_split(self):
        user, internal = _split_internal_keys(
            {"a": 1, "_run_id": "x", "b": 2, "_backend": None}
        )
        self.assertEqual(user, {"a": 1, "b": 2})
        self.assertEqual(internal, {"_run_id": "x", "_backend": None})

    def test_non_string_keys_are_user(self):
        user, internal = _split_internal_keys({1: "a"})
        self.assertEqual(user, {1: "a"})
        self.assertEqual(internal, {})


class TestTrimPayloadPrefixOverlap(unittest.TestCase):
    def test_removes_duplicate_prefix(self):
        left = "The quarterly report shows strong revenue growth this period."
        payload = "this period. Additional hidden guidance follows here clearly."
        trimmed = _trim_payload_prefix_overlap(left, payload)
        self.assertNotIn("this period. this period", trimmed.lower())
        self.assertIn("Additional hidden guidance", trimmed)

    def test_empty_inputs(self):
        self.assertEqual(_trim_payload_prefix_overlap("", "payload"), "payload")
        self.assertEqual(_trim_payload_prefix_overlap("left", ""), "")

    def test_no_overlap_returns_payload(self):
        out = _trim_payload_prefix_overlap("abc def", "totally different text here")
        self.assertEqual(out, "totally different text here")


class TestChunking(unittest.TestCase):
    def test_chunk_text_overlap(self):
        text = "x" * 2500
        chunks = chunk_text(text, chunk_size=1000, overlap=200)
        self.assertGreaterEqual(len(chunks), 3)
        self.assertTrue(all(len(c) <= 1000 for c in chunks))

    def test_chunk_text_with_offsets(self):
        text = "abcdefghij" * 30  # 300 chars
        chunks = chunk_text_with_offsets(text, chunk_size=100, overlap=20)
        self.assertTrue(chunks)
        for chunk, start, end in chunks:
            self.assertEqual(text[start:end], chunk)

    def test_empty_text(self):
        self.assertEqual(chunk_text("", chunk_size=100, overlap=10), [])
        self.assertEqual(chunk_text_with_offsets("", 100, 10), [])


class TestParseDocuments(unittest.TestCase):
    def test_parses_txt_and_md(
        self,
    ):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "a.txt").write_text("hello world", encoding="utf-8")
            (base / "b.md").write_text("# Title\nbody", encoding="utf-8")
            (base / "empty.txt").write_text("   ", encoding="utf-8")
            docs = parse_documents(
                sources=[str(base)],
                include_globs=["*.txt", "*.md"],
                recursive=True,
                fail_on_parse_error=False,
                logger=LOGGER,
            )
        ids = sorted(d["id"] for d in docs)
        self.assertEqual(ids, ["a", "b"])

    def test_skips_unsupported_and_handles_single_file(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            f = base / "doc.txt"
            f.write_text("content here", encoding="utf-8")
            (base / "ignore.bin").write_text("data", encoding="utf-8")
            docs = parse_documents(
                sources=[str(f), str(base / "ignore.bin")],
                include_globs=["*.txt"],
                recursive=False,
                fail_on_parse_error=False,
                logger=LOGGER,
            )
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["id"], "doc")

    def test_glob_expansion_source(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "one.txt").write_text("one", encoding="utf-8")
            (base / "two.txt").write_text("two", encoding="utf-8")
            docs = parse_documents(
                sources=[str(base / "*.txt")],
                include_globs=["*.txt"],
                recursive=False,
                fail_on_parse_error=False,
                logger=LOGGER,
            )
        self.assertEqual(len(docs), 2)

    def test_parse_error_raises_when_configured(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            f = base / "bad.txt"
            f.write_text("x", encoding="utf-8")
            with patch.object(
                rag_attack.Path, "read_text", side_effect=OSError("boom")
            ):
                with self.assertRaises(RuntimeError):
                    parse_documents(
                        sources=[str(f)],
                        include_globs=["*.txt"],
                        recursive=False,
                        fail_on_parse_error=True,
                        logger=LOGGER,
                    )


class TestGetEmbeddings(unittest.TestCase):
    def _fake_client(self, dim=4):
        fake_client = MagicMock()

        def _create(input, model):
            resp = MagicMock()
            resp.data = [
                MagicMock(embedding=[float(i + 1)] * dim) for i in range(len(input))
            ]
            return resp

        fake_client.embeddings.create.side_effect = _create
        return fake_client

    def test_basic_embeddings(self):
        fake_client = self._fake_client()
        with patch("openai.OpenAI", return_value=fake_client):
            arr = get_embeddings(
                ["a", "b", "c"],
                {
                    "identifier": "embeddinggemma",
                    "endpoint": "http://x/v1",
                    "api_key": "k",
                },
                LOGGER,
            )
        self.assertEqual(arr.shape, (3, 4))
        self.assertEqual(arr.dtype, np.float32)

    def test_strips_embeddings_suffix(self):
        fake_client = self._fake_client()
        captured = {}
        with patch(
            "openai.OpenAI", side_effect=lambda **kw: captured.update(kw) or fake_client
        ):
            get_embeddings(
                ["a"],
                {"endpoint": "http://x/v1/embeddings/"},
                LOGGER,
            )
        self.assertTrue(captured["base_url"].endswith("/v1"))


class TestFaiss(unittest.TestCase):
    def test_build_and_search(self):
        embeddings = np.array([[1.0, 0.0], [0.0, 1.0], [0.9, 0.1]], dtype=np.float32)
        index = build_faiss_index(embeddings)
        self.assertEqual(index.ntotal, 3)
        query = np.array([1.0, 0.0], dtype=np.float32)
        result = search_index(index, query, top_k=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], 0)

    def test_build_handles_zero_vectors(self):
        embeddings = np.array([[0.0, 0.0], [1.0, 1.0]], dtype=np.float32)
        index = build_faiss_index(embeddings)
        self.assertEqual(index.ntotal, 2)

    def test_search_zero_query(self):
        embeddings = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        index = build_faiss_index(embeddings)
        result = search_index(index, np.array([0.0, 0.0], dtype=np.float32), top_k=1)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
