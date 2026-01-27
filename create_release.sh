#!/bin/bash
# Script to complete a release
# Usage: ./create_release.sh [VERSION]
# Example: ./create_release.sh 1.5.1
#
# If no version is provided, defaults to 1.5.1

set -e

# Configuration
VERSION="${1:-1.5.1}"

echo "================================"
echo "Release $VERSION Creation Script"
echo "================================"
echo ""

# Check if we're in the right repository
if [ ! -f "custom_components/eplucon/manifest.json" ]; then
    echo "Error: This script must be run from the repository root"
    exit 1
fi

# Check if the tag already exists remotely
if git ls-remote --tags origin | grep -q "refs/tags/$VERSION$"; then
    echo "✅ Tag $VERSION already exists on GitHub"
    echo ""
    echo "Checking if release exists..."
    echo "Visit: https://github.com/koenhendriks/ha-eplucon/releases/tag/$VERSION"
    exit 0
fi

# Check if we're on the main branch or can access it
if ! git rev-parse main >/dev/null 2>&1; then
    echo "Fetching main branch..."
    git fetch origin main
fi

# Get the main branch commit SHA
MAIN_SHA=$(git rev-parse main)

echo "Creating and pushing tag $VERSION..."
echo ""

# Create the tag if it doesn't exist locally
if git rev-parse "$VERSION" >/dev/null 2>&1; then
    echo "Tag $VERSION already exists locally"
    
    # Verify the local tag points to main
    TAG_SHA=$(git rev-parse "$VERSION^{commit}")
    if [ "$TAG_SHA" != "$MAIN_SHA" ]; then
        echo "⚠️  Warning: Local tag $VERSION points to $TAG_SHA but main is at $MAIN_SHA"
        echo "Deleting local tag and recreating..."
        git tag -d "$VERSION"
    else
        echo "✅ Tag $VERSION points to the correct commit"
    fi
fi

# Create the tag if needed
if ! git rev-parse "$VERSION" >/dev/null 2>&1; then
    echo "Creating tag $VERSION on main branch..."
    
    # Extract release notes from CHANGELOG.md
    RELEASE_NOTES=$(awk "/## \[$VERSION\]/,/## \[/{if(/## \[/ && !/## \[$VERSION\]/)exit;print}" CHANGELOG.md | grep -v "^## \[$VERSION\]" | sed '/^$/d')
    
    if [ -z "$RELEASE_NOTES" ]; then
        echo "Warning: No release notes found in CHANGELOG.md for version $VERSION"
        RELEASE_NOTES="Release version $VERSION"
    fi
    
    if ! git tag -a "$VERSION" main -m "Release version $VERSION

$RELEASE_NOTES"; then
        echo "❌ Failed to create tag"
        exit 1
    fi
    echo "✅ Tag created locally"
fi

# Push the tag
echo ""
echo "Pushing tag to GitHub..."
if ! git push origin "$VERSION"; then
    echo "❌ Failed to push tag"
    exit 1
fi

echo ""
echo "✅ Tag pushed successfully!"
echo ""
echo "The GitHub Actions workflow will now automatically create the release."
echo "Check the progress at: https://github.com/koenhendriks/ha-eplucon/actions"
echo ""
echo "Once complete, the release will be available at:"
echo "https://github.com/koenhendriks/ha-eplucon/releases/tag/$VERSION"
