# Development

Build with `make`; run `make test` before committing. Tests use synthetic raw data and a fake USB device, with no camera access. Node.js is only needed for JavaScript tests. GitHub Actions runs the suite on macOS with Python 3.12 and Node.js 24. Use a local dataset with `python3 server.py --replay PATH` for UI development; see [data format](docs/data-format.md).

Document consequential changes and verification in [the logbook](docs/logbook.md). Keep hardware observations distinct from synthetic tests. Preserve raw data and metadata identity across capture/export, make calibration units explicit, and never silently substitute live data for replay (or vice versa).

Do not commit specimen data, vendor installers, credentials, local paths or session exports. Use synthetic fixtures for reproducible tests. Describe limitations and public interfaces in the relevant documentation. Changes to the on-disk schema need compatibility tests and a format/version decision. The source and contributed code are licensed under MIT; specimen data is separately licensed by its owner.
