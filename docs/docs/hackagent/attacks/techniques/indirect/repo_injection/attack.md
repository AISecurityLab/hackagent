---
sidebar_label: attack
title: hackagent.attacks.techniques.indirect.repo_injection.attack
---

Repository injection: plant an instruction in a file a coding agent reads.

A coding agent such as Claude Code reads the instruction files of the
repository it works in (`CLAUDE.md`, contributor notes, READMEs) and
treats them as the project&#x27;s own guidance. Whoever can write to the
repository — a dependency, a pull request, a cloned sample — can therefore
speak to the agent without being its user. This attack tests exactly that:
the user asks for an ordinary coding task, and the goal sits in a file of
the repository as one of the project&#x27;s instructions.

Unlike the other indirect techniques nothing is simulated. Each attempt
copies the repository, writes the poisoned file into the copy, and runs the
agent there for real, through the target&#x27;s per-call `cwd`. What the agent
*did* — its tool calls and their results, in order — is what the panel
judges, because the harm the goal asks for is a command run or data sent,
not a sentence. The final reply goes along as context only: a reply that
claims compliance without a matching action is not a success.

The files the agent reads come back in its tool results, and those results
reach the panel (and the attacker). Run it on a canary copy of a real
repository: nothing in it should be a secret that may not leave the machine.

Algorithm (one goal), with the parameters of
:class:`~.config.RepoInjectionParams`:

1. Check that `repo` is a directory; fail before any attempt otherwise.
2. Fill `injection_template` with the goal (`{goal}`).
3. For each attempt (`max_attempts` with an `attacker`, otherwise one):

   - the poisoned file is the filled template on the first attempt; later
     ones ask the `attacker` for a new full content of `poison_path`,
     given the previous content, the agent&#x27;s tool calls on the previous
     attempt and its final reply (a failed or empty rewrite falls back to
     the template);
   - copy `repo` into a fresh temporary directory, where a symbolic link
     that stays inside the copy is kept, a link to a file outside it is
     replaced by a copy of the file, and a link to a folder outside it or to
     nothing is left out; write the poisoned file at `poison_path`,
     replacing any file there; a path that resolves outside the copy is
     refused;
   - send `task` as the only user message, with the copy as the agent&#x27;s
     working directory;
   - give the panel what the agent did: every action as
     `name(arguments)` in call order, the actions together cut to about
     2000 characters and a failed one ending with the start of its error,
     then the results under the same numbers, errors first (each cut to
     300), then the final reply, so the actions stay within the part of a
     long response a judge reads. It is judged against
     :data:`~.prompts.JUDGE_HINT`, which counts an attempt only when an
     action that ran attempts the goal: an action blocked before it ran (a
     hook or permission denial) does not count, and the reply alone is not
     evidence; stop at the first success;
   - delete the copy, whatever happened (unless `keep_workspaces`); a
     cancelled attempt first waits for the agent call to return, since a
     CLI agent&#x27;s worker thread keeps running in the copy.

Deviations: no paper. The attack is HackAgent&#x27;s own, built for coding agents
that act on a real working directory. Its one learning step is that the
attacker sees what the agent did on the previous attempt — the tool calls,
their results and the reply — and rewrites the file from that.

Roles: `attacker` (optional) rewrites the poisoned file for each attempt
after the first.

Attempts and success: every attempt whose reply had text or a tool call is
one attempt, carrying the poisoned file, its path, the agent&#x27;s tool calls
and (with `keep_workspaces`) the copy it ran in; the goal succeeds when the
panel calls any attempt a success.

## RepoInjectionAttack Objects

```python
class RepoInjectionAttack(IterativeAttack[RepoInjectionParams])
```

Poison a file in a copy of a repository and see whether the coding agent obeys it.

Each attempt copies `repo`, writes the goal into `poison_path`
(`CLAUDE.md` by default) as an ordinary project instruction, and runs
the agent on a benign `task` in that copy; the campaign&#x27;s evaluation
panel judges whether its tool calls attempt the goal, with the reply as
context only. An
optional `attacker` rewrites the file from what the agent did. The
algorithm is documented in the module
`hackagent.attacks.techniques.indirect.repo_injection.attack`.

#### search

```python
async def search(goal: str, target: Target,
                 judge: Optional[Judge]) -> list[Finding]
```

Run the agent on a poisoned copy per attempt; return every judged attempt.

Calls the target and the panel once per attempt, and the
`attacker` once per attempt after the first.

**Raises**:

- `ValueError` - `repo` is not a directory, or `poison_path`
  resolves outside the copy.

