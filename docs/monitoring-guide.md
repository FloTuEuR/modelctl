# Monitoring guide

`modelctl monitor`, `modelctl tail`, and `modelctl router logs` provide read-oriented access to local llama.cpp router/server status and logs.

## Endpoint discovery

```bash
modelctl monitor
modelctl monitor discover
modelctl monitor 8080
modelctl monitor 8082
```

Discovery remains read-only. It checks configured/common local OpenAI-compatible endpoints and reports whether a server appears reachable.

## Configured monitor backend

Use these for snapshots of explicitly configured monitor backends:

```bash
modelctl monitor router
modelctl monitor router --lines 200
```

For live human log follow, prefer the clearer wrappers:

```bash
modelctl tail 8080
modelctl router logs cuda
```

`modelctl monitor router --follow` remains available for compatibility with configured file/systemd monitor backends, but it is no longer the primary operator path.

Supported configured backends today:

```ini
[monitor]
backend = file
log_file = /path/to/router.log
```

```ini
[monitor]
backend = systemd
service = llama-cuda.service
```

The file backend reads/follows the configured log file. The systemd backend wraps `journalctl -u <service>`.

## Port-centric tail

```bash
modelctl tail 8080
```

`tail` uses explicit `[monitor.ports]` mappings:

```ini
[monitor.ports]
8080 = llama-cuda.service
8081 = llama-vulkan.service
8082 = llama-cpu.service
```

## Router service wrappers

For the common local services, use router wrappers instead of remembering raw commands:

```bash
modelctl router logs cuda
modelctl router logs vulkan
modelctl router logs cpu
```

These are equivalent to:

```bash
journalctl -u llama-cuda.service -f
journalctl -u llama-vulkan.service -f
journalctl -u llama-cpu.service -f
```

Lifecycle actions live under `modelctl router` rather than `monitor`, because `monitor` is read-only:

```bash
modelctl router restart cuda
modelctl router reset cuda
modelctl router reset-failed cuda  # compatibility/systemctl spelling
modelctl router start cuda
```

See [Router service wrappers](router-configuration.md) for the full router command surface.
