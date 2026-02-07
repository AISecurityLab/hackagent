# CI Scripts

## check-commits.sh

This script validates commit messages in a Git range to ensure they follow the commitizen format required by the project.

### Features

- **Selective Validation**: Skips commits authored by bots (identified by email patterns like `[bot]@` or `+Copilot@`)
- **Human-Focused**: Only enforces commitizen format for commits authored by humans
- **Clear Feedback**: Provides detailed output showing which commits pass, fail, or are skipped

### Usage

```bash
bash check-commits.sh <base-sha> <head-sha>
```

### Why Skip Bot Commits?

Automated tools (like Copilot, Dependabot, or other CI bots) may create commits that serve specific purposes but don't always follow conventional commit message formats. By skipping validation for these automated commits while still enforcing standards for human authors, we get the best of both worlds:

1. **Maintain Quality**: Human commits still must follow the commitizen format
2. **Enable Automation**: Bots can work without being blocked by format requirements
3. **Reduce Friction**: No need to manually fix or rebase bot commits

### Commitizen Format

Human-authored commits must follow this format:

```
type(scope): subject

body

footer
```

Examples:
- `fix: resolve API timeout issue`
- `feat(auth): add OAuth2 support`
- `docs: update installation instructions`

For the full list of supported types, see the project's commitizen configuration in `pyproject.toml`.
