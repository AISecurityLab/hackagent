# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What the TUI sets up before Textual takes over the terminal."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.skipif(os.name != "posix", reason="the resource tracker is POSIX-only")
def test_a_run_can_load_a_hugging_face_dataset_once_the_tui_is_up():
    """Textual replaces stderr with an object that has no file descriptor.

    Loading a Hugging Face dataset makes tqdm create a multiprocessing lock,
    and the first such lock starts multiprocessing's resource tracker, handing
    it stderr's descriptor. Started after Textual took over, that failed with
    'bad value(s) in fds_to_keep', so no campaign drawing goals from a preset
    could run in the TUI. The TUI starts the tracker before Textual does.
    """
    script = textwrap.dedent(
        """
        import multiprocessing
        import sys

        from textual.app import App

        from hackagent.interfaces.cli.config import CLIConfig
        from hackagent.interfaces.tui.app import HackAgentTUI

        class NoDescriptor:
            def write(self, text):
                return len(text)

            def flush(self):
                pass

            def fileno(self):
                return -1

        def textual_run(self, *args, **kwargs):
            # What Textual does to stderr, then what tqdm does mid-run.
            sys.stderr = NoDescriptor()
            multiprocessing.RLock()
            print("lock created")

        App.run = textual_run
        HackAgentTUI(CLIConfig()).run()
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=60
    )
    assert "lock created" in result.stdout, result.stdout + result.stderr
