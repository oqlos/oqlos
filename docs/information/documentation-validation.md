---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "documentation-validation",
  "kind": "information",
  "version": 1,
  "title": "Documentation validation",
  "status": "implemented",
  "owner": "oqlos/oqlos",
  "created": "2026-09-15",
  "updated": "2026-09-15",
  "review_after": "2026-10-15",
  "source_revision": "55f1ef6f69ce81abf70e65b97d52f52a4d1d1173",
  "affected_repositories": [
    "oqlos/oqlos"
  ],
  "evidence": [
    "repo://oqlos/oqlos/scripts/check-docs-report.py",
    "repo://oqlos/oqlos/standards/standards-lock.json"
  ],
  "scope": "repository"
}
---

# Documentation validation

<!-- docs:section purpose -->
## Purpose

Validate durable documents and report artifacts before completion.

<!-- docs:section scope -->
## Scope

Repository documentation only. No runtime, hardware or database changes.

<!-- docs:section evidence -->
## Evidence

Immutable published Docs 6f475fb223e7a259d514b5483fb0d62f0e80a46e and Report 3eafc9c212bbfd4060fe15b63eb97e4614725234 are copied with SHA256 verification in standards/standards-lock.json.

<!-- docs:section content -->
## Content

Before writing, run the pinned Docs checker with --prepare, --scope repository, kind, id and canonical --deliverable; save the JSON in ignored .subactor/receipts/. After staging the exact document, run python3 scripts/check-docs-report.py --base <full-base-sha> --complete --deliverable <path> --prepared-plan <receipt>. Changed analyses require adjacent tracked .report.json manifests. Run python3 -m unittest discover -s standards/tests and the checker before publication. The documentation workflow invokes both.

<!-- docs:section limitations -->
## Limitations

Local conformance is not proof of publication, temporal ordering or protected CI execution. Report supports repository-local Docs v1; compact v2 compatibility is not claimed. Legacy documents are migrated when changed. In OneDev, authenticated job identity and base bind read-only mirror URL mapping; local environment variables never grant publication authority.

<!-- docs:section next_actions -->
## Next Actions

Observe the documentation CI result for each exact published head. Keep raw logs in ignored recovery storage; publish durable results in their owning repository and index them.
