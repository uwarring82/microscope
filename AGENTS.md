# Repository working agreement

- Read `CONTRIBUTING.md` and the relevant SDK/data-format notes before changing public behavior.
- Record consequential development, decisions, evidence and known limitations in `docs/logbook.md`. Distinguish hardware observations, synthetic tests and pending validation.
- Keep code, tests, schemas and documentation together in reviewable commits. Preserve raw frame identity, provenance, explicit units and exact-resolution calibration matching.
- Use offline replay or synthetic fixtures for UI development. Connecting to the camera or acquiring new specimens requires the user's task to call for it; never silently fall back from replay to USB.
- Run `make test` for code changes and appropriate browser checks for UI changes. Tests must not require a camera or private datasets.
- Keep specimen recordings, sessions, exports, vendor software, credentials and private filesystem/network paths out of Git. The MIT code license does not grant rights to specimen data or vendor binaries.
- Maintain `CITATION.cff`, `codemeta.json`, `VERSION` and schema compatibility when releasing. State archival/DOI and calibration limitations honestly.
