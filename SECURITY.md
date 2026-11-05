# Security policy

## Supported versions

Only the latest version on `main` gets fixes.

## Reporting a vulnerability

**Please don't open a public issue for security problems.** Report them privately through GitHub:
go to this repository's **Security** tab and click **Report a vulnerability**. You'll get a reply
within 7 days, and a fix or a mitigation plan as soon as the issue is confirmed. You'll be credited
in the fix unless you'd rather not be.

## What's in scope

The skill runs model calls on your machine with your credentials. Reports in these areas are especially welcome:

- **Credential exposure.** Anything that could leak `ANTHROPIC_API_KEY`, the `claude` CLI login, or other
  environment variables into logs, `.consult/` files, prompts or output.
- **Tool permissions.** The consultant and board seats run `claude -p` restricted to read-only tools
  (`Read`, `Grep`, `Glob`). Any way around that restriction, such as writing files or running commands, is a bug.
- **Prompt injection from repository content.** The board reads the repo it's run in. Content in a repo
  that makes the board or the agent take actions the user didn't ask for counts.
- **The installer** writing outside `~/.claude/skills`, `~/.codex/skills`, `~/.agents/skills` or the
  chosen `--project` folder.

Out of scope: the quality of the models' advice, and the cost of calls you chose to make.

## Good practice for users

- `.consult/` holds your questions, the models' answers and their cost. Add it to your project's
  `.gitignore` if your questions mention private details.
- Board resolutions are advice. Review the plan before approving it, especially for auth, payments
  and data deletion.
