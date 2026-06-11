# Archive

## Archive: what it is for

Use `archive` when you want to get a model out of the active models folder without losing the ability to restore it later.

Typical use case:

1. a model is taking disk space or should no longer be active;
2. you want the GGUF moved into the archive tree;
3. you want any router aliases for that model disabled, not deleted;
4. you want a machine-readable undo file written at the same time.

## Archive apply

```bash
modelctl archive 1
```

Optional explicit plan path:

```bash
modelctl archive 1 --plan ./archive-plan.json
```

For each selected model, `archive`:

1. writes a backup beside the router ini, e.g. `models.ini.bak`;
2. comments aliases that referenced the model;
3. updates the commented `model = ...` line to the archive destination;
4. moves the GGUF into the archive tree;
5. writes a manual recovery plan JSON.

## Archive preview

```bash
modelctl archive 1 --dry-run
modelctl archive alias:example --dry-run
modelctl archive path:/path/to/example.gguf --dry-run
```

No files are changed during preview.

## Rollback: what it is for

Use `manual recovery` to undo a previous `archive`.

That manual recovery plan JSON is the receipt for the archive action. It records enough information to:

- move the GGUF back to its original location;
- restore the router ini state from before the archive;
- do that safely in preview mode first.

## Rollback apply

```bash
modelctl manual recovery ./archive-plan.json
```

## Rollback preview

```bash
modelctl manual recovery ./archive-plan.json --dry-run
```

This shows what would be restored. No files are changed.
