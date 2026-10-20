<div align="center">

<img src="https://docs.hackagent.dev/img/banner.svg" alt="HackAgent" width="800">

**The open-source red-team toolkit for AI models and agents**

[Docs](https://docs.hackagent.dev/) · [App](https://app.hackagent.dev/) · [API](https://api.hackagent.dev/schema/redoc)

[![PyPI](https://img.shields.io/pypi/v/hackagent)](https://pypi.org/project/hackagent/)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![CI](https://img.shields.io/github/actions/workflow/status/AISecurityLab/hackagent/ci.yml)
![Coverage](https://img.shields.io/codecov/c/github/AISecurityLab/hackagent)

</div>

HackAgent attacks your AI model or agent with research-backed techniques —
jailbreaks, prompt injection, tool misuse — and has judge models score every
reply. You get a measured success rate per attack, so you can see how exposed a
target is and whether a fix helped.

## See it run

**Terminal UI.** Start from an example, change what you need, run it.

<img src="https://raw.githubusercontent.com/AISecurityLab/hackagent/main/docs/static/gifs/hackagent-tui.gif" alt="Building and running a campaign in the HackAgent terminal UI" width="100%">

**Command line.** The same campaign is one YAML file you can edit, check and run, in a shell or in CI.

<img src="https://raw.githubusercontent.com/AISecurityLab/hackagent/main/docs/static/gifs/hackagent-cli.gif" alt="Copying, editing, validating and running a campaign from the command line" width="100%">

**Dashboard.** Browse runs, results and traces with `hackagent web`, or on [app.hackagent.dev](https://app.hackagent.dev/).

<img src="https://raw.githubusercontent.com/AISecurityLab/hackagent/main/docs/static/gifs/hackagent-dashboard.gif" alt="Browsing campaign results in the HackAgent dashboard" width="100%">

## Quick start

```bash
pip install 'hackagent[tui]'
hackagent                # opens the terminal UI
```

Or run an example end to end, fully local, with [Ollama](https://ollama.com):

```bash
ollama pull gemma3:4b
hackagent examples copy h4rm3l-demo
hackagent campaign run h4rm3l-demo.yaml
```

No API key needed: results go to a local database unless a campaign says
otherwise.

## Learn more

- [Installation](https://docs.hackagent.dev/getting-started/installation) — extras, and standalone binaries that need no Python
- [Your first campaign](https://docs.hackagent.dev/getting-started/first-campaign) — write, check and run one
- [Concepts](https://docs.hackagent.dev/concepts) — attacks, judges and how a run works
- [Attacks](https://docs.hackagent.dev/reference/attacks) and the [campaign file reference](https://docs.hackagent.dev/reference/campaign)
- [Dashboard](https://docs.hackagent.dev/getting-started/dashboard) — `hackagent web`, locally or against your account

Questions? Join the [discussions](https://github.com/AISecurityLab/hackagent/discussions) or email ais@ai4i.it.

## Responsible use

HackAgent is for authorized security testing only. Test systems you own or
have written permission to test, and report what you find through coordinated
disclosure. Read the [responsible disclosure guidelines](https://docs.hackagent.dev/security/responsible-disclosure)
and our [security policy](SECURITY.md).

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

Licensed under Apache-2.0. See [LICENSE](LICENSE). HackAgent is intended for
security research and AI safety improvement; the authors are not responsible
for misuse.
