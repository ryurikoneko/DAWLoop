# Live FL Studio tests

Live FL Studio tests are intentionally not discovered or run by the ordinary test command. They require a dedicated disposable test project, a blank existing Pattern, an identified Channel, the bundled upstream scripts installed, and an external `identity_reader` capable of verifying project / Pattern / Channel identity before and after operations.

The upstream Piano Roll state does not include Pattern identity, so the current repository does not yet provide a safe end-to-end Live test runner. Until a trustworthy target identity reader is available, the adapter must return `STOP` without writing. Do not use a private song as a substitute test project.

The future explicit runner must preserve the target identity and read-back event evidence described in [`docs/VERIFICATION.md`](../../docs/VERIFICATION.md), and only then may it record `Live FL Studio Verified`.
