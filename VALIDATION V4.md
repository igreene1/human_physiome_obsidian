---
title: "VALIDATION V4"
type: "validation"
status: "checked"
updated: "2026-09-29"
tags: [physiome, validation]
---

# VALIDATION V4

The integrated v4 vault passed local structural checks on 29 September 2026.

## Inventory and retention

| Check | Result |
|---|---:|
| Markdown notes | 827 |
| Canvas maps | 44 |
| Original Markdown topics retained | 436 of 436 |
| New substantive notes | 367 |
| Existing substantive notes rewritten | 179 |
| Reaction/transformation notes | 110 |
| Cell-type notes | 53 |
| New or rebuilt Canvas maps | 15 |
| Notes and maps reachable from the start page | 871 of 871 |

Counts include navigation and reference entries where applicable. A reaction note can describe an explicitly labelled module comprising several chemical steps; it does not always represent one elementary reaction.

## Checks completed

- All Markdown frontmatter parsed as YAML, with a title and type.
- All internal wiki-link targets resolved, including headings and file extensions.
- No ambiguous note names, case-colliding paths or Windows-incompatible filenames were found.
- All Canvas files parsed as JSON; IDs, edge endpoints, file paths, dimensions and heading subpaths were checked.
- New and rebuilt maps have no overlapping cards. Selected map previews were inspected and the new layouts were adjusted to reduce crossing arrows.
- The reaction and cell indexes include every corresponding note.
- All original Markdown topics remain at their repaired paths.
- No remaining replacement characters, the original filename encoding damage, unbalanced wiki-link delimiters or literal escaped-newline damage were detected in Markdown.

The machine-readable counts and findings are in `90 Maintenance/validation.json`.

## Run the checker after editing

From the vault folder, run:

```bash
python3 "90 Maintenance/validate_vault.py"
```

The checker uses the Python standard library. If PyYAML is installed, it also parses all YAML frontmatter. An optional `--report PATH` argument writes a JSON report. The delivered edition was checked with PyYAML available.

## Limits of this check

Validation covers local document structure. It does not establish biological accuracy, scientific completeness, external reference availability or mathematical consistency of reaction stoichiometry. Canvas layouts were inspected through coordinate-based previews; native Obsidian rendering was not executed in this environment. See the Evidence and Scope and Coverage and Gaps notes for content limitations.
