# Contributing to HackAgent

First off, thank you for considering contributing to HackAgent! It's people like you that make HackAgent such a great tool. We welcome contributions of all kinds, from bug reports and feature requests to documentation improvements and code contributions.

Following these guidelines helps to communicate that you respect the time of the developers managing and developing this open-source project. In return, they should reciprocate that respect in addressing your issue, assessing changes, and helping you finalize your pull requests.

## Table of Contents

*   [Code of Conduct](#code-of-conduct)
*   [Getting Started](#getting-started)
*   [How Can I Contribute?](#how-can-i-contribute)
    *   [Reporting Bugs](#reporting-bugs)
    *   [Suggesting Enhancements](#suggesting-enhancements)
    *   [Your First Code Contribution](#your-first-code-contribution)
    *   [Pull Requests](#pull-requests)
*   [Development Setup](#development-setup)
*   [Styleguides](#styleguides)
    *   [Git Commit Messages](#git-commit-messages)
    *   [Python Styleguide](#python-styleguide)
*   [License](#license)

## Code of Conduct

This project and everyone participating in it is governed by the [HackAgent Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to [ais@ai4i.it](mailto:ais@ai4i.it).

## Getting Started

Before you begin, make sure you have set up your development environment as described in the [Development](#development-setup) section below and in the main [README.md](README.md#development).

## How Can I Contribute?

### Reporting Bugs

This section guides you through submitting a bug report for HackAgent. Following these guidelines helps maintainers and the community understand your report, reproduce the behavior, and find related reports.

*   **Use the GitHub Issues:** Report bugs using GitHub Issues.
*   **Check Existing Issues:** Before creating a bug report, please check if the issue has already been reported.
*   **Provide Details:** Explain the problem and include additional details to help maintainers reproduce the problem:
    *   Use a clear and descriptive title.
    *   Describe the exact steps which reproduce the problem.
    *   Provide specific examples to demonstrate the steps.
    *   Describe the behavior you observed after following the steps and point out what exactly is the problem with that behavior.
    *   Explain which behavior you expected to see instead and why.
    *   Include details about your environment (Python version, OS, HackAgent version).

### Suggesting Enhancements

This section guides you through submitting an enhancement suggestion for HackAgent, including completely new features and minor improvements to existing functionality.

*   **Use the GitHub Issues:** Suggest enhancements using GitHub Issues.
*   **Check Existing Issues:** Before creating an enhancement suggestion, please check if it has already been suggested.
*   **Provide Details:**
    *   Use a clear and descriptive title.
    *   Provide a step-by-step description of the suggested enhancement in as many details as possible.
    *   Describe the current behavior and explain which behavior you expected to see instead and why.
    *   Explain why this enhancement would be useful.

### Your First Code Contribution

Unsure where to begin contributing to HackAgent? You can start by looking through `good first issue` and `help wanted` issues:

*   [Good first issues](https://github.com/vistalabs-org/hackagent/labels/good%20first%20issue) - issues which should only require a few lines of code, and a test or two.
*   [Help wanted issues](https://github.com/vistalabs-org/hackagent/labels/help%20wanted) - issues which should be a bit more involved than `good first issue` issues.

### Pull Requests

The process described here has several goals:

*   Maintain HackAgent's quality
*   Fix problems that are important to users
*   Engage the community in working toward the best possible HackAgent
*   Enable a sustainable system for HackAgent's maintainers to review contributions

Please follow these steps to have your contribution considered by the maintainers:

1.  **Fork the repository** and create your branch from `main`.
    ```bash
    git checkout -b name-of-your-feature-or-fix
    ```
2.  **Set up the development environment** (see [Development Setup](#development-setup)).
3.  **Make your changes.**
4.  **Ensure code quality:**
    *   Format your code: `uv run ruff format .`
    *   Check for linting issues: `uv run ruff check .`
    *   Run tests: `uv run pytest tests/`
    *   Ensure pre-commit checks pass if you have them installed.
5.  **Commit your changes** using a descriptive commit message that follows our [Commit Message Guidelines](#git-commit-messages).
    ```bash
    git add .
    git commit -m "feat: Add new amazing feature"
    ```
6.  **Push your branch** to your fork on GitHub.
    ```bash
    git push origin name-of-your-feature-or-fix
    ```
7.  **Open a Pull Request** to the `main` branch of the `vistalabs-org/hackagent` repository.
8.  **Link to issues:** If your Pull Request addresses an open issue, please link to it in the PR description (e.g., `Closes #123`).
9.  **Explain your changes:** Provide a clear description of the changes you've made and why.
10. **Wait for review:** The maintainers will review your Pull Request. Be prepared to make changes based on their feedback.

## Development Setup

To set up your environment for local development:

1. Clone the repository:

    ```bash
    git clone https://github.com/AISecurityLab/hackagent.git
    cd hackagent
    ```

2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/):

    ```bash
    # On macOS and Linux
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # On Windows
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

    # Or with pip
    pip install uv
    ```

3. Install dependencies, including development dependencies:

    ```bash
    uv sync --extra dev
    ```

4. (Optional but Recommended) Install pre-commit hooks:

    ```bash
    uv run pre-commit install --hook-type commit-msg --hook-type pre-commit
    ```

## Styleguides

### Git Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification. This is enforced locally via pre-commit hooks (if installed) and in our CI pipeline.

Commit messages should be structured as follows:

## License

By contributing to HackAgent, you agree that your contributions will be licensed under its [Apache License 2.0](LICENSE).
