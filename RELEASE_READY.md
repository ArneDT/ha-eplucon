# Release 1.5.1 - Ready to Publish

## Status: Prepared and Ready

All necessary components for release 1.5.1 have been prepared. A single manual step is required to publish the release (see below).

## What Has Been Prepared

### 1. Version Update ✅
- File: `custom_components/eplucon/manifest.json`
- Version set to: `1.5.1`
- Committed to: `main` branch

### 2. Changelog Entry ✅
- File: `CHANGELOG.md`
- Entry added for version 1.5.1 with release date 2026-01-27
- Contains: Fix for PR #31 (import_energy and export_energy type handling)

### 3. Git Tag Created ✅
- Tag: `1.5.1`
- Target: `main` branch (commit: 2ac4593)
- Message: "Release version 1.5.1"
- Created locally but not yet pushed

### 4. GitHub Actions Workflow ✅
- File: `.github/workflows/release.yaml`
- Automatically creates GitHub releases when tags are pushed
- Can also be manually triggered via workflow_dispatch

## Release Notes for 1.5.1

```markdown
### Fixed
* ([#31](https://github.com/koenhendriks/ha-eplucon/pull/31)) Changed import_energy and export_energy types to Union to handle both int and float values by [@joopmartens](https://github.com/joopmartens)
```

## Manual Step Required

To complete the release, someone with write access to the repository needs to push the tag:

```bash
git push origin 1.5.1
```

Once the tag is pushed:
1. The GitHub Actions workflow will automatically create the release
2. The release will be published with the correct notes from the CHANGELOG
3. The release will be available at: https://github.com/koenhendriks/ha-eplucon/releases/tag/1.5.1

## Alternative: Manual Release Creation

If preferred, the release can be created manually:

1. Go to: https://github.com/koenhendriks/ha-eplucon/releases/new
2. Tag version: `1.5.1`
3. Target: `main`
4. Release title: `v1.5.1`
5. Description:
   ```
   ### Fixed
   * ([#31](https://github.com/koenhendriks/ha-eplucon/pull/31)) Changed import_energy and export_energy types to Union to handle both int and float values by [@joopmartens](https://github.com/joopmartens)
   ```
6. Click "Publish release"

## Verification

After the release is published, verify:
- [ ] Release appears at https://github.com/koenhendriks/ha-eplucon/releases
- [ ] Release is titled "v1.5.1"
- [ ] Release notes match the changelog entry
- [ ] Release is not marked as pre-release or draft
- [ ] Tag 1.5.1 appears in the repository tags
