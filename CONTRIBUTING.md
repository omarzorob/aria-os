# Contributing to Aria OS

Thanks for your interest. Aria is built in public — PRs, issues, and ideas all welcome.

## Getting Started

```bash
git clone https://github.com/omarzorob/aria-os
cd aria-os
python3 -m venv .venv
source .venv/bin/activate
pip install -r agent/requirements.txt
```

## How to Contribute

### Reporting bugs
Open a GitHub Issue with label `bug`. Include:
- What you said to Aria
- What it did vs what you expected
- Device/OS info

### Building new tools
Tools are the actions Aria can take (send SMS, order food, etc.).

1. Add your tool to `agent/tools/`
2. Follow the tool interface in `agent/tools/base.py`
3. Register it in `agent/tool_registry.py`
4. Add tests in `tests/tools/`
5. PR with description of what the tool does

### Improving the agent core
- Agent reasoning lives in `agent/aria_agent.py`
- Memory system in `agent/memory/`
- Keep PRs focused — one thing per PR

### Adding device support
- New Android devices: add to `system/device_compat.md`
- Test on your device, document quirks

## Code Style
- Python: black formatter, type hints where reasonable
- Kotlin/Java (Android): follow Android coding conventions
- Flutter: dart format

## Roadmap
See the [task board in Discord](#) and `docs/ROADMAP.md` for what's planned.

## License
Apache 2.0. Your contributions are licensed the same way.
