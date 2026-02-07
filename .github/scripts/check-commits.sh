#!/bin/bash
# Check commit messages in a range, skipping bot-authored commits
#
# This script validates commits individually rather than in batch to allow
# selective skipping of bot commits while validating human commits.

set -euo pipefail

BASE_SHA=$1
HEAD_SHA=$2

if [ -z "$BASE_SHA" ] || [ -z "$HEAD_SHA" ]; then
    echo "Usage: $0 <base-sha> <head-sha>"
    exit 1
fi

echo "Checking commits from $BASE_SHA to $HEAD_SHA"

# Get list of commits in range
COMMITS=$(git rev-list "$BASE_SHA..$HEAD_SHA")

if [ -z "$COMMITS" ]; then
    echo "No commits to check"
    exit 0
fi

FAILED=0

# Bot email patterns to skip during validation
BOT_PATTERNS=(
    "\[bot\]@"
    "\+Copilot@"
    "noreply@github\.com"
    "dependabot"
)

for commit in $COMMITS; do
    # Get commit author email
    AUTHOR_EMAIL=$(git log -1 --format='%ae' "$commit")
    
    # Check if this is a bot commit
    IS_BOT=false
    for pattern in "${BOT_PATTERNS[@]}"; do
        if [[ "$AUTHOR_EMAIL" =~ $pattern ]]; then
            IS_BOT=true
            break
        fi
    done
    
    # Skip bot commits
    if [ "$IS_BOT" = true ]; then
        COMMIT_MSG=$(git log -1 --format='%s' "$commit")
        echo "⏭️  Skipping bot commit $commit: $COMMIT_MSG"
        continue
    fi
    
    # Check commit message format
    COMMIT_MSG=$(git log -1 --format='%B' "$commit")
    echo "Checking commit $commit..."
    
    if echo "$COMMIT_MSG" | uv run cz check --message -; then
        echo "✅ Commit $commit passed"
    else
        echo "❌ Commit $commit failed validation"
        echo "   Message: $COMMIT_MSG"
        FAILED=1
    fi
done

if [ $FAILED -eq 1 ]; then
    echo ""
    echo "❌ Some commits failed validation"
    echo "Please ensure all commit messages follow the commitizen format:"
    echo "  type(scope): subject"
    echo ""
    echo "Example: fix: resolve issue with API calls"
    echo "Example: feat: add new feature"
    exit 1
fi

echo ""
echo "✅ All commits passed validation"
exit 0
