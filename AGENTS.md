# Repository instructions

## Keep feature documentation synchronized

The user requires maintained `FEATURE-<name>.md` documents containing the original
feature prompt, implementation details, update history, and transplit guidance.

- Before changing a documented feature, read its `FEATURE-*.md` file.
- Update the relevant feature document in the same change as its code or tests.
  Record changed behavior, controls, data/storage/event contracts, affected source
  files, validation actually performed, limitations, and deferred work as applicable.
- Preserve the original user prompt. Add follow-up requirements and dated update
  entries separately; do not rewrite the prompt to match the implementation.
- For new features, create a descriptive `FEATURE-<name>.md` using the same structure.
- Keep README instructions and `TRANSPLIT.md` synchronized when affected. Distinguish
  implemented Python behavior, verified Rust parity, and proposed conversion work.
- Do not claim tests or conversion validation that were not performed. Documentation-only
  changes need documentation checks rather than an unnecessary runtime test rerun.

The live drive scanner and map are documented in
[FEATURE-realtime-drive-scanner.md](FEATURE-realtime-drive-scanner.md).
