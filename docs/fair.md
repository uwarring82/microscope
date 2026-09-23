# FAIR practice and data stewardship

This project follows the [FAIR guiding principles](https://www.gofair.foundation/fair-principles) to improve findability, accessibility, interoperability and reuse. FAIR does not require every laboratory image to be public. The source release is public; specimen recordings and sessions remain local unless their owner deliberately publishes them.

| Principle | Implemented practice | Remaining responsibility |
|---|---|---|
| Findable | Public repository, release version, Git history, CITATION.cff and CodeMeta. New sessions have a UUID URN; captures and profiles have unique IDs. | Archive releases/datasets with a persistent DOI when appropriate. GitHub URLs and UUIDs do not by themselves provide archival preservation. |
| Accessible | Source and metadata through public HTTPS; local sessions are documented files, usable without the UI. | Dataset owners select a repository, access policy and retention plan. Local sessions are not publicly indexed. |
| Interoperable | Documented RAW8 RGGB, JSON with a versioned JSON Schema, FITS 4.0 image export, PNG inspection sheets, explicit units and coordinate conventions. | External readers must respect Bayer phase and row order. The JSON schema validates structure, while the loader also verifies file lengths and checksums. |
| Reusable | MIT code license, checksums, captured settings, raw/display separation, source provenance, calibration references and fit uncertainty, software version/commit/modified paths and explicitly timed process snapshot (older records have only the modified flag). | Assign a data license before sharing specimen datasets. The code license does not automatically license specimen data or third-party vendor binaries. |

## Publishing a dataset

Retain `manifest.json`, every referenced `.raw`, capture metadata, annotation JSON and calibration references. Describe the specimen, objective, adapter/zoom, illumination, calibration reference and acquisition purpose. Check that every raw SHA-256 matches. Record which exports are processed derivatives. Select an appropriate data license with the data owner, and deposit the package in an institutional or research repository. Add its assigned DOI to the manifest and retain a public metadata record if data access is restricted or later withdrawn.

There is currently no project or dataset DOI and none is fabricated. No captured specimen data or vendor software is distributed in this source repository. Tests generate synthetic fixtures. See [data format](data-format.md), [development logbook](logbook.md), and [CITATION.cff](../CITATION.cff).
