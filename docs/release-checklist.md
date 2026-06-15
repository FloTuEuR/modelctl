# Release Readiness Checklist

Use this checklist before every release to ensure quality and safety.

## Code Quality

- [ ] Clean git tree - no uncommitted changes
- [ ] Full pytest suite passes: `pytest tests -q`
- [ ] No linting issues: `git diff --check`
- [ ] No tracked transient artifacts (`uv.lock`, `.runlogs`, `.pytest_cache`, `.coverage`, `htmlcov`)

## Production Readiness

- [ ] Private marker audit - no secrets, tokens, or sensitive data in code/tests
- [ ] JSON envelope smoke checks - verify all commands produce valid JSON
- [ ] List filter smoke checks - verify `--json` with filters works correctly
- [ ] Add/archive/restore/delete/recover smoke checks

## Monitor Discovery

- [ ] Monitor read-only smoke check - verify no mutation occurs

## Code Review

- [ ] No private local paths in code (use generic placeholders)
- [ ] No secrets, API keys, or tokens in code
- [ ] No machine-specific details (hostname, IP addresses beyond standard)
- [ ] No user/hostnames/endpoints that could leak information

## Release Notes

- [ ] Draft release notes documenting changes
- [ ] Verify tag naming convention
- [ ] Update changelog if applicable

## Testing

- [ ] All existing tests pass
- [ ] New features have tests
- [ ] No test files reference local paths or secrets

## Documentation

- [ ] README updated if needed
- [ ] Command documentation complete
- [ ] JSON output documented

## Before Push

- [ ] Run full private audit: `grep -RInE "private|secret|token|api_key" . --exclude-dir=.git`
- [ ] Verify no sensitive data committed
- [ ] Branch name follows convention
