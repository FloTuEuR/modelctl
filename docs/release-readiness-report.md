# Release Readiness Report

Branch: `work/modelctl-router-lifecycle`

Current HEAD at report creation: `a309668 docs: link operational references`

## Validation commands

```bash
uv run --no-project --with pytest python -m pytest tests -q
git diff --check
```

Latest supervised validation before this report:

```text
97 passed, 1 skipped, 18 subtests passed
```

`git diff --check` passed.

## Private/internal audit

Audit command:

```bash
run the private/internal marker audit from the release checklist
```

Result summary:

- Expected scanner fixture hits in `tests/test_production_readiness.py`.
- Expected generic safety/checklist wording about secrets, tokens, and private
  paths in public safety documentation.
- No unexpected private machine details, credentials, local setup files, or
  transient artifacts should be present before release.

## Capabilities ready for review

- Lifecycle command surface alignment around add, archive, restore, delete, and
  recover.
- Archive/restore lifecycle behavior with recovery metadata.
- Focused delete recovery manifests and recover flow.
- Modelctl-owned generated artifact directories.
- Stable JSON envelopes for automation and dashboards.
- List filters for active/archived and enabled/disabled views.
- Missing-argument help improvements.
- Read-only monitor log abstraction.
- Read-only monitor endpoint discovery.
- JSON output and monitor discovery documentation.
- Release checklist and release notes draft.

## Known limitations

- Destructive delete remains intentionally guarded.
- Monitor discovery is endpoint-based only; process-list discovery is not
  implemented.
- Monitor discovery does not persist endpoint selections or write config.
- Additional router setup and monitoring backend configuration remain future
  roadmap work.

## Recommended next action

After human review, either:

1. Open a pull request from `work/modelctl-router-lifecycle`, or
2. Tag a pre-release from this branch if it is intended to be tested directly.

Do not tag or publish a release without a final human review of the release notes
and checklist.
