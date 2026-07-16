## Summary

<!-- What does this change and why? -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactor / internal
- [ ] Protocol / wire-format change (coordinated with the AIP spec)

## How was this tested?

<!-- Commands run, new tests added. HTTP is mocked; no real funds needed. -->

```
ruff check . && ruff format --check . && pytest
```

## Checklist

- [ ] Tests added or updated for the change
- [ ] `README.md` updated if public behavior changed
- [ ] `CHANGELOG.md` updated under `Unreleased`
- [ ] No hard-coded gateway, provider, or platform (stays vendor-neutral)
- [ ] No private keys, secrets, or real credentials in code or tests
