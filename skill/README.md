# billing-engine-skill

An [agent skill](https://sulaimanh7877.github.io/saas-billing/guides/agent-skill/)
that teaches a coding agent how to use
[**billing-engine**](https://pypi.org/project/billing-engine/) — subscriptions,
entitlements/feature gating, invoices, credits, audit, reporting, and
channel/partner sales for a Python SaaS.

The skill is a single `SKILL.md` with the API cheatsheet, the non-negotiable
rules (integer money, UTC, table prefix, explicit renewals), common pitfalls,
and a testing pattern.

## Install

```bash
npx billing-engine-skill
```

This writes the skill to `./.claude/skills/billing-engine/SKILL.md`, where
Claude Code and compatible agents discover it automatically.

=== "opencode"

    ```bash
    npx billing-engine-skill --dest .opencode/skill
    ```

=== "Custom location"

    ```bash
    npx billing-engine-skill --dest .agents/skills
    ```

=== "Just print it"

    ```bash
    npx billing-engine-skill --print > SKILL.md
    ```

### Flags

| Flag | Effect |
|---|---|
| `--dest <dir>` | Skills root directory (default `.claude/skills`) |
| `--print` | Print `SKILL.md` to stdout |
| `--force` | Overwrite an existing file |
| `--help` | Show usage |

## What the agent learns

- Configure `EngineConfig` and run `billing.migrate()`.
- Model features, plans, immutable plan versions, and prices.
- Create customers and subscriptions; run trials and the lifecycle.
- Gate access with `can()` / `limit()` and apply overrides.
- Raise invoices, record offline payments, and manage credits.
- Sell through partners: agreements, allocations, license issuance, ledger,
  statements, invoices, and payouts.
- Run `process_due()` on a schedule and handle engine errors.

## Updating

The published package tracks the engine's minor version. Re-run the installer
with `--force` after upgrading `billing-engine`.

## Releasing (maintainers)

1. Edit `skill/SKILL.md` and keep the version in sync with `billing-engine`.
2. Run `python scripts/sync_skill.py` from the repository root to refresh the
   docs copies, and commit them with the skill change.
3. Tag a release as `skill-v<version>` (for example `skill-v0.2.0`) and push.
   The `publish-skill` workflow publishes to npm.

The workflow needs an `NPM_TOKEN` repository secret with publish rights. To
publish manually:

```bash
cd skill
npm publish --access public
```

## License

MIT — see the [repository](https://github.com/sulaimanh7877/saas-billing).
