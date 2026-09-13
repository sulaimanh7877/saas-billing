# Use with a coding agent

Ship this skill to your AI coding agent so it knows the API, the locked rules,
and the pitfalls before it writes any billing code. It is published to npm as
[`billing-engine-skill`](https://www.npmjs.com/package/billing-engine-skill).

<div class="be-skill-copy" markdown>
<button class="md-button md-button--primary be-button--copy" data-copy-skill="../assets/skill/billing-engine-skill.txt" data-label="Copy SKILL.md">Copy SKILL.md</button>
<a class="md-button" href="../assets/skill/billing-engine-skill.txt" download="SKILL.md">Download</a>
</div>

## Install

=== "Claude Code / compatible"

    ```bash
    npx billing-engine-skill
    ```

    Writes `./.claude/skills/billing-engine/SKILL.md`.

=== "opencode"

    ```bash
    npx billing-engine-skill --dest .opencode/skill
    ```

=== "Anywhere"

    ```bash
    npx billing-engine-skill --dest .agents/skills     # custom skills root
    npx billing-engine-skill --print > SKILL.md        # just print it
    npx billing-engine-skill --force                   # overwrite
    ```

The installer is a single dependency-free Node script. It copies the bundled
`SKILL.md`; no network access beyond npm is required.

## What the skill gives the agent

- **Non-negotiable rules** — integer minor-unit money, UTC timestamps, the
  required table prefix, tight transactions, no editing published plan versions.
- **A full API cheatsheet** for catalog, subscriptions, entitlements, invoices,
  credits, partners, licenses, and reporting.
- **The entitlement resolution order** and how overrides interact.
- **The explicit-renewal rule** — the agent will add a `process_due()` job rather
  than assume the engine renews itself.
- **Error handling** and a test pattern using in-memory SQLite.
- **Common pitfalls** that otherwise lead to subtly broken billing code.

## Full skill source

The canonical file lives at
[`skill/SKILL.md`](https://github.com/sulaimanh7877/saas-billing/blob/main/skill/SKILL.md)
in the repository; it is synced into this page byte-for-byte.

<div class="be-skill-source" markdown>
--8<-- "skill/SKILL.md:docs"
</div>

## Keeping it current

The npm package version tracks the engine's minor version. After upgrading
`billing-engine`, re-run the installer with `--force`.

## Next

- [Quick start](../getting-started/quickstart.md)
- [Tutorial](../getting-started/tutorial.md)
