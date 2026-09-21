# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the module-level helpers of the indirect prompt injection attack."""

import logging
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from hackagent.attacks.techniques.indirect_prompt_injection import attack as ipi
from hackagent.attacks.techniques.indirect_prompt_injection.attack import (
    _deep_update,
    _parse_pdf,
    _split_internal_keys,
    _trim_payload_prefix_overlap,
    build_faiss_index,
    chunk_text,
    chunk_text_with_offsets,
    get_embeddings,
    parse_documents,
    search_index,
)

LOGGER = logging.getLogger("test.ipi.helpers")
LOGGER.addHandler(logging.NullHandler())


class TestDeepUpdate(unittest.TestCase):
    def test_nested_dicts_are_merged_not_replaced(self):
        target = {"rag": {"top_k": 5, "chunk_size": 1000}}

        _deep_update(target, {"rag": {"top_k": 9}})

        self.assertEqual(target["rag"], {"top_k": 9, "chunk_size": 1000})

    def test_new_keys_are_added(self):
        target = {"a": 1}

        _deep_update(target, {"b": 2})

        self.assertEqual(target, {"a": 1, "b": 2})

    def test_plain_values_are_deep_copied(self):
        source_value = [{"nested": True}]
        target = {}

        _deep_update(target, {"items": source_value})

        self.assertEqual(target["items"], source_value)
        self.assertIsNot(target["items"][0], source_value[0])

    def test_internal_keys_keep_their_identity(self):
        tracker = object()
        target = {}

        _deep_update(target, {"_tracker": tracker})

        self.assertIs(target["_tracker"], tracker)

    def test_scalar_overwrites_a_dict(self):
        target = {"rag": {"top_k": 5}}

        _deep_update(target, {"rag": "disabled"})

        self.assertEqual(target["rag"], "disabled")


class TestSplitInternalKeys(unittest.TestCase):
    def test_underscore_prefixed_keys_are_separated(self):
        user, internal = _split_internal_keys(
            {"goals": ["g"], "_run_id": "r", "_tracker": None}
        )

        self.assertEqual(user, {"goals": ["g"]})
        self.assertEqual(internal, {"_run_id": "r", "_tracker": None})

    def test_non_string_keys_stay_user_facing(self):
        user, internal = _split_internal_keys({1: "one"})

        self.assertEqual(user, {1: "one"})
        self.assertEqual(internal, {})

    def test_empty_config(self):
        self.assertEqual(_split_internal_keys({}), ({}, {}))


class TestTrimPayloadPrefixOverlap(unittest.TestCase):
    def test_no_overlap_returns_the_payload_unchanged(self):
        self.assertEqual(
            _trim_payload_prefix_overlap("left side text", "  totally different  "),
            "totally different",
        )

    def test_duplicated_prefix_is_removed(self):
        shared = "the quick brown fox jumps over the lazy dog again"
        payload = f"{shared}, and then more payload text"

        trimmed = _trim_payload_prefix_overlap(f"prelude {shared}", payload)

        self.assertEqual(trimmed, "and then more payload text")

    def test_overlap_shorter_than_the_minimum_is_ignored(self):
        trimmed = _trim_payload_prefix_overlap("ends with abc", "abc rest of payload")

        self.assertEqual(trimmed, "abc rest of payload")

    def test_whitespace_is_normalised_before_comparison(self):
        shared = "a sentence long enough to count as an overlap"
        trimmed = _trim_payload_prefix_overlap(f"x   {shared}", f"{shared}\n\n  tail")

        self.assertEqual(trimmed, "tail")

    def test_empty_inputs_are_handled(self):
        self.assertEqual(_trim_payload_prefix_overlap("", " payload "), "payload")
        self.assertEqual(_trim_payload_prefix_overlap("left", ""), "")
        self.assertEqual(_trim_payload_prefix_overlap("   ", " payload "), "payload")

    def test_full_overlap_keeps_the_payload(self):
        shared = "identical payload text that is long enough to overlap"

        self.assertEqual(_trim_payload_prefix_overlap(shared, shared), shared)


class TestParseDocuments(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _write(self, relative, text="document body"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_single_file_source(self):
        path = self._write("a.txt", "hello world")

        docs = parse_documents([str(path)], ["*.txt"], True, False, LOGGER)

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["id"], "a")
        self.assertEqual(docs[0]["text"], "hello world")
        self.assertEqual(docs[0]["path"], str(path))

    def test_directory_source_is_globbed_recursively(self):
        self._write("top.txt")
        self._write("nested/deep.txt")

        docs = parse_documents([str(self.root)], ["*.txt"], True, False, LOGGER)

        self.assertEqual({d["id"] for d in docs}, {"top", "deep"})

    def test_non_recursive_directory_source_skips_subfolders(self):
        self._write("top.txt")
        self._write("nested/deep.txt")

        docs = parse_documents([str(self.root)], ["*.txt"], False, False, LOGGER)

        self.assertEqual({d["id"] for d in docs}, {"top"})

    def test_markdown_is_supported_and_unknown_types_are_skipped(self):
        self._write("notes.md", "# heading")
        self._write("data.csv", "a,b")

        docs = parse_documents([str(self.root)], ["*.md", "*.csv"], True, False, LOGGER)

        self.assertEqual([d["id"] for d in docs], ["notes"])

    def test_glob_pattern_source_is_expanded(self):
        self._write("one.txt")
        self._write("two.txt")

        docs = parse_documents(
            [str(self.root / "*.txt")], ["*.txt"], True, False, LOGGER
        )

        self.assertEqual({d["id"] for d in docs}, {"one", "two"})

    def test_blank_documents_are_dropped(self):
        self._write("blank.txt", "   \n  ")

        docs = parse_documents([str(self.root)], ["*.txt"], True, False, LOGGER)

        self.assertEqual(docs, [])

    def test_duplicate_sources_are_de_duplicated(self):
        path = self._write("a.txt")

        docs = parse_documents(
            [str(path), str(self.root)], ["*.txt"], True, False, LOGGER
        )

        self.assertEqual(len(docs), 1)

    def test_parse_failure_is_logged_by_default(self):
        self._write("a.txt")
        logger = MagicMock()

        with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
            docs = parse_documents([str(self.root)], ["*.txt"], True, False, logger)

        self.assertEqual(docs, [])
        logger.warning.assert_called_once()

    def test_parse_failure_can_be_fatal(self):
        self._write("a.txt")

        with patch.object(Path, "read_text", side_effect=OSError("boom")):
            with self.assertRaises(RuntimeError):
                parse_documents([str(self.root)], ["*.txt"], True, True, LOGGER)

    def test_pdf_sources_are_routed_to_the_pdf_parser(self):
        self._write("doc.pdf", "%PDF-fake")

        with patch.object(ipi, "_parse_pdf", return_value="pdf text") as parser:
            docs = parse_documents([str(self.root)], ["*.pdf"], True, False, LOGGER)

        parser.assert_called_once()
        self.assertEqual(docs[0]["text"], "pdf text")

    def test_missing_sources_are_ignored(self):
        docs = parse_documents(
            [str(self.root / "nope")], ["*.txt"], True, False, LOGGER
        )

        self.assertEqual(docs, [])


class TestParsePdf(unittest.TestCase):
    def test_pages_are_joined(self):
        reader = MagicMock()
        reader.pages = [
            SimpleNamespace(extract_text=lambda: "page one"),
            SimpleNamespace(extract_text=lambda: None),
            SimpleNamespace(extract_text=lambda: "page three"),
        ]
        fake_module = SimpleNamespace(PdfReader=MagicMock(return_value=reader))

        with patch.dict(sys.modules, {"pypdf": fake_module}):
            text = _parse_pdf(Path("/tmp/doc.pdf"))

        self.assertEqual(text, "page one\n\n\n\npage three")

    def test_missing_pypdf_raises_a_helpful_error(self):
        with patch.dict(sys.modules, {"pypdf": None}):
            with self.assertRaises(ImportError) as ctx:
                _parse_pdf(Path("/tmp/doc.pdf"))

        self.assertIn("pip install pypdf", str(ctx.exception))


class TestChunking(unittest.TestCase):
    def test_chunks_overlap_by_the_requested_amount(self):
        text = "".join(str(i % 10) for i in range(25))

        chunks = chunk_text(text, chunk_size=10, overlap=5)

        self.assertEqual(chunks[0], text[:10])
        self.assertEqual(chunks[1], text[5:15])

    def test_short_text_is_a_single_chunk(self):
        self.assertEqual(chunk_text("short", chunk_size=100, overlap=10), ["short"])

    def test_empty_text_yields_no_chunks(self):
        self.assertEqual(chunk_text("", chunk_size=10, overlap=2), [])

    def test_whitespace_only_chunks_are_dropped(self):
        text = "ab" + " " * 10 + "cd"

        chunks = chunk_text(text, chunk_size=4, overlap=0)

        self.assertNotIn("    ", chunks)
        self.assertEqual(chunks[0], "ab  ")

    def test_offsets_match_the_chunk_boundaries(self):
        text = "".join(str(i % 10) for i in range(25))

        chunks = chunk_text_with_offsets(text, chunk_size=10, overlap=5)

        for chunk, start, end in chunks:
            self.assertEqual(chunk, text[start:end])
        self.assertEqual(chunks[0][1:], (0, 10))
        self.assertEqual(chunks[1][1:], (5, 15))

    def test_offsets_on_empty_text(self):
        self.assertEqual(chunk_text_with_offsets("", chunk_size=5, overlap=1), [])


class TestGetEmbeddings(unittest.TestCase):
    def _client(self, dim=3):
        client = MagicMock()

        def _create(input, model):
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.1] * dim) for _ in input]
            )

        client.embeddings.create.side_effect = _create
        return client

    def _run(self, texts, config, client=None):
        client = client or self._client()
        with patch("openai.OpenAI", return_value=client) as factory:
            result = get_embeddings(texts, config, LOGGER)
        return result, client, factory

    def test_returns_a_float32_matrix(self):
        result, _, _ = self._run(["a", "b"], {})

        self.assertEqual(result.shape, (2, 3))
        self.assertEqual(result.dtype, np.float32)

    def test_endpoint_trailing_slash_is_stripped(self):
        _, _, factory = self._run(["a"], {"endpoint": "http://localhost:11434/v1/"})

        self.assertEqual(
            factory.call_args.kwargs["base_url"], "http://localhost:11434/v1"
        )

    def test_embeddings_suffix_is_removed_from_the_endpoint(self):
        _, _, factory = self._run(
            ["a"], {"endpoint": "http://localhost:11434/v1/embeddings"}
        )

        self.assertEqual(
            factory.call_args.kwargs["base_url"], "http://localhost:11434/v1"
        )

    def test_placeholder_api_key_is_used_for_keyless_backends(self):
        with patch.dict("os.environ", {}, clear=True):
            _, _, factory = self._run(["a"], {})

        self.assertEqual(factory.call_args.kwargs["api_key"], "not-needed")

    def test_environment_api_key_is_picked_up(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
            _, _, factory = self._run(["a"], {})

        self.assertEqual(factory.call_args.kwargs["api_key"], "env-key")

    def test_explicit_api_key_wins(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
            _, _, factory = self._run(["a"], {"api_key": "explicit"})

        self.assertEqual(factory.call_args.kwargs["api_key"], "explicit")

    def test_model_identifier_is_forwarded(self):
        _, client, _ = self._run(["a"], {"identifier": "nomic-embed-text"})

        self.assertEqual(
            client.embeddings.create.call_args.kwargs["model"], "nomic-embed-text"
        )

    def test_requests_are_batched_in_hundreds(self):
        result, client, _ = self._run([f"t{i}" for i in range(250)], {})

        self.assertEqual(client.embeddings.create.call_count, 3)
        self.assertEqual(result.shape[0], 250)


class TestFaissIndex(unittest.TestCase):
    def test_index_dimension_matches_the_embeddings(self):
        embeddings = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

        index = build_faiss_index(embeddings)

        self.assertEqual(index.d, 2)
        self.assertEqual(index.ntotal, 2)

    def test_zero_vectors_do_not_divide_by_zero(self):
        embeddings = np.array([[0.0, 0.0], [3.0, 4.0]], dtype=np.float32)

        index = build_faiss_index(embeddings)

        self.assertEqual(index.ntotal, 2)

    def test_search_returns_the_closest_vector_first(self):
        embeddings = np.array([[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]], dtype=np.float32)
        index = build_faiss_index(embeddings)

        indices = search_index(index, np.array([0.0, 2.0], dtype=np.float32), top_k=2)

        self.assertEqual(indices[0], 1)
        self.assertEqual(len(indices), 2)

    def test_search_tolerates_a_zero_query_vector(self):
        embeddings = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        index = build_faiss_index(embeddings)

        indices = search_index(index, np.array([0.0, 0.0], dtype=np.float32), top_k=1)

        self.assertEqual(len(indices), 1)

    def test_top_k_beyond_the_index_size_pads_with_minus_one(self):
        embeddings = np.array([[1.0, 0.0]], dtype=np.float32)
        index = build_faiss_index(embeddings)

        indices = search_index(index, np.array([1.0, 0.0], dtype=np.float32), top_k=3)

        self.assertEqual(indices[0], 0)
        self.assertIn(-1, indices)


if __name__ == "__main__":
    unittest.main()
