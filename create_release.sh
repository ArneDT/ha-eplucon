#!/bin/bash
# Script to complete the 1.5.1 release
# This script should be run by someone with push access to the repository

set -e

echo "================================"
echo "Release 1.5.1 Creation Script"
echo "================================"
echo ""

# Check if we're in the right repository
if [ ! -f "custom_components/eplucon/manifest.json" ]; then
    echo "Error: This script must be run from the repository root"
    exit 1
fi

# Check if the tag already exists remotely
if git ls-remote --tags origin | grep -q "refs/tags/1.5.1$"; then
    echo "✅ Tag 1.5.1 already exists on GitHub"
    echo ""
    echo "Checking if release exists..."
    echo "Visit: https://github.com/koenhendriks/ha-eplucon/releases/tag/1.5.1"
    exit 0
fi

# Check if we're on the main branch or can access it
if ! git rev-parse main >/dev/null 2>&1; then
    echo "Fetching main branch..."
    git fetch origin main
fi

echo "Creating and pushing tag 1.5.1..."
echo ""

# Create the tag if it doesn't exist locally
if ! git rev-parse 1.5.1 >/dev/null 2>&1; then
    echo "Creating tag 1.5.1 on main branch..."
    git tag -a 1.5.1 main -m "Release version 1.5.1

### Fixed
* ([#31](https://github.com/koenhendriks/ha-eplucon/pull/31)) Changed import_energy and export_energy types to Union to handle both int and float values by [@joopmartens](https://github.com/joopmartens)"
    echo "✅ Tag created locally"
else
    echo "✅ Tag 1.5.1 already exists locally"
fi

# Push the tag
echo ""
echo "Pushing tag to GitHub..."
git push origin 1.5.1

echo ""
echo "✅ Tag pushed successfully!"
echo ""
echo "The GitHub Actions workflow will now automatically create the release."
echo "Check the progress at: https://github.com/koenhendriks/ha-eplucon/actions"
echo ""
echo "Once complete, the release will be available at:"
echo "https://github.com/koenhendriks/ha-eplucon/releases/tag/1.5.1"
