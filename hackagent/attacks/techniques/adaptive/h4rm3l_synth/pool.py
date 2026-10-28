# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The program pool: what synthesis learns and carries between goals.

Every entry is a decorator program and the attack success rate it earned on
the goals it was scored against. Programs are drawn as few-shot examples in
proportion to that rate, so the synthesizer is shown what has been working
without ever being restricted to it: a program is sampled from a Beta
distribution centred on its rate, whose concentration grows with the round,
so early rounds explore and later ones exploit.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class Entry:
    """One program and how it scored."""

    program: str
    successes: int = 0
    trials: int = 0

    @property
    def asr(self) -> float:
        """Share of scored replies the panel called a success."""
        return self.successes / self.trials if self.trials else 0.0


@dataclass
class ProgramPool:
    """Scored programs, sampled in proportion to how well they did."""

    entries: dict[str, Entry] = field(default_factory=dict)
    _random: random.Random = field(default_factory=random.Random)

    def seed(self, programs: list[str]) -> None:
        """Add starting programs, unscored."""
        for program in programs:
            self.entries.setdefault(program, Entry(program))

    def record(self, program: str, successes: int, trials: int) -> Entry:
        """Add or update a program with the result of scoring it."""
        entry = self.entries.setdefault(program, Entry(program))
        entry.successes += successes
        entry.trials += trials
        return entry

    def mean_asr(self) -> float:
        """Mean rate over scored programs; 0.0 while none has been scored."""
        scored = [entry for entry in self.entries.values() if entry.trials]
        if not scored:
            return 0.0
        return sum(entry.asr for entry in scored) / len(scored)

    def best(self, count: int) -> list[str]:
        """The ``count`` programs with the highest rate, best first."""
        ranked = sorted(
            self.entries.values(),
            key=lambda entry: (entry.asr, entry.trials),
            reverse=True,
        )
        return [entry.program for entry in ranked[:count]]

    def sample(self, count: int, round_number: int, concentration: float) -> list[str]:
        """Draw ``count`` distinct programs, favouring the ones that worked.

        An unscored program is drawn from Beta(1, 1), which is uniform, so a
        new program competes with the proven ones until it has a rate of its
        own.
        """
        if count >= len(self.entries):
            return [entry.program for entry in self.entries.values()]

        strength = max(1.0, concentration * round_number)
        scored: list[tuple[float, str]] = []
        for entry in self.entries.values():
            if entry.trials:
                alpha = max(1e-6, entry.asr * strength)
                beta = max(1e-6, (1.0 - entry.asr) * strength)
            else:
                alpha = beta = 1.0
            scored.append((self._random.betavariate(alpha, beta), entry.program))
        scored.sort(reverse=True)
        return [program for _, program in scored[:count]]

    def size(self) -> int:
        return len(self.entries)


__all__ = ["Entry", "ProgramPool"]
