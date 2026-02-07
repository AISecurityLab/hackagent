#!/bin/bash
# Check commit messages in a range, skipping bot-authored commits

set -e

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

for commit in $COMMITS; do
    # Get commit author email
    AUTHOR_EMAIL=$(git log -1 --format='%ae' "$commit")
    
    # Skip bot commits (those with @users.noreply.github.com or [bot] in email)
    if [[ "$AUTHOR_EMAIL" == *"[bot]@"* ]] || [[ "$AUTHOR_EMAIL" == *"+Copilot@"* ]]; then
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
