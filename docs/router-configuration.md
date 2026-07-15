# Router service wrappers

`modelctl router` wraps the systemd commands used for the local llama.cpp router services so operators do not need to remember the exact `journalctl` and `systemctl` invocations.

## Configured targets

Targets are resolved from `[router.services]` and `[monitor.ports]` in the modelctl config. Built-in defaults are also available for the common local services:

```ini
[router.services]
cuda = llama-cuda.service
vulkan = llama-vulkan.service
cpu = llama-cpu.service
8080 = llama-cuda.service
8081 = llama-vulkan.service
8082 = llama-cpu.service
```

An explicit `*.service` name can also be passed when needed.

## Log wrappers

```bash
modelctl router logs cuda --follow
modelctl router logs vulkan --follow
modelctl router logs cpu --follow
```

These wrap:

```bash
journalctl -u llama-cuda.service -f
journalctl -u llama-vulkan.service -f
journalctl -u llama-cpu.service -f
```

Without `--follow`, `--lines N` shows recent lines through `journalctl -n N --no-pager -o cat`.

## Lifecycle wrappers

These commands intentionally mutate systemd service state because the user explicitly requested the action:

```bash
modelctl router restart cuda
modelctl router restart vulkan
modelctl router restart cpu
modelctl router reset-failed cuda
modelctl router start cuda
```

They wrap:

```bash
sudo systemctl restart llama-cuda.service
sudo systemctl restart llama-vulkan.service
sudo systemctl restart llama-cpu.service
sudo systemctl reset-failed llama-cuda.service
sudo systemctl start llama-cuda.service
```

Use `--dry-run` to print the command without executing it. Use `--no-sudo` only when running in an environment where direct `systemctl` is appropriate.

## Status and command preview

```bash
modelctl router status cuda
modelctl router command logs cuda --follow
modelctl router command restart vulkan
modelctl router services
```

`status`, `command`, and `services` are read-only. JSON output is available via `--json` for automation.

## Safety

- Service targets are config/default driven; modelctl does not scan processes or guess arbitrary service names.
- Unknown targets fail clearly and list configured targets.
- `logs`, `status`, `command`, and `services` are read-only.
- `restart`, `reset-failed`, and `start` are explicit systemd state changes and return the underlying command's exit code.
