# Contributing

Please do not attach tokens, account identifiers, device IDs, Home Assistant backups, or raw WireGuard configuration to issues.

Device discovery must remain driven by `/api/v1/device/list-owned`. Driver adapters may describe protocol capabilities, but must never contain account-specific device IDs or assume a fixed device count.

Any additional cloud command requires a separate safety review. The initial release allow-lists only D18 (`ctrl_max_on_grid_current`).

Before opening a change:

```bash
ruff format --check .
ruff check .
pytest
python -m compileall -q custom_components
```
