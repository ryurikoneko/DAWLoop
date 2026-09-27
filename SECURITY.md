# Security

## Sensitive information

Do not commit or publicly post access tokens, passwords, cookies, authentication data, personal access credentials, private keys, private MCP configuration, local desktop details or absolute paths, private project state, runtime logs containing secrets, private FL Studio projects, or copyrighted/private samples.

## Reporting a security issue

Do not disclose vulnerability details in a public issue. If GitHub provides a private vulnerability reporting option for this repository, use that channel. Otherwise, contact the maintainer only through contact information actually published on the maintainer GitHub profile. This repository does not document another private reporting channel.

## Safe contributions and live testing

- Do not submit private FL Studio projects, commercial samples, copyrighted music, plugin binaries, or unredacted local logs.
- Run live tests only in a dedicated disposable FL Studio project with synthetic notes.
- Agents and adapters must stop when the target project, Pattern, Channel, or operation state is ambiguous. Destructive or irreversible operations require explicit user confirmation.
- A tool success response is not proof that the DAW reached the intended state. Use readback and verification before reporting success.
- When reporting a live issue, remove usernames, absolute paths, project names, and unrelated event data from logs.
