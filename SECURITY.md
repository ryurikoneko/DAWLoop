# Security and Safety

## Reporting a security issue

Do not publish credentials, private project content, or sensitive logs in a public issue. For a suspected security issue, contact the repository maintainer through the GitHub profile's available contact channel and share only the minimum details needed to investigate.

## Safe contributions and live testing

- Never commit API keys, tokens, passwords, cookies, authentication data, or personal access credentials.
- Do not submit private FL Studio projects, commercial samples, copyrighted music, plugin binaries, or unredacted local logs.
- Run live tests only in a dedicated disposable FL Studio project with synthetic notes.
- Agents and adapters must stop when the target project, Pattern, Channel, or operation state is ambiguous. Destructive or irreversible operations require explicit user confirmation.
- A tool's success response is not proof that the DAW reached the intended state. Use readback and verification before reporting success.

When reporting a live issue, remove usernames, absolute paths, project names, and unrelated event data from logs.
