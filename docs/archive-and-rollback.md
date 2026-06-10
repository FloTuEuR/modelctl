# Archive and rollback

## Preview

```bash
modelctl archive model:1
modelctl archive alias:example
modelctl archive path:/path/to/example.gguf
```

No files are changed during preview.

## Apply

```bash
modelctl archive model:1 --yes
```

Optional explicit plan path:

```bash
modelctl archive model:1 --yes --plan ./archive-plan.json
```

## What apply changes

For each selected model, `archive --yes`:

1. writes a backup beside the router ini, e.g. `models.ini.bak`;
2. comments aliases that referenced the model;
3. updates the commented `model = ...` line to the archive destination;
4. moves the GGUF into the archive tree;
5. writes a rollback plan JSON.

## Rollback

Preview:

```bash
modelctl rollback ./archive-plan.json
```

Apply:

```bash
modelctl rollback ./archive-plan.json --yes
```
