#!/bin/bash

echo "🔧 Fixing Git violations..."

# Remove files from Git tracking that should be ignored
echo "📁 Removing .DS_Store from Git tracking..."
git rm --cached .DS_Store 2>/dev/null || echo "   .DS_Store not tracked"

echo "🐍 Removing Python cache from Git tracking..."
git rm -r --cached __pycache__/ 2>/dev/null || echo "   __pycache__ not tracked"

echo "🖼️  Removing image files from Git tracking..."
git rm -r --cached received_images/ 2>/dev/null || echo "   received_images not tracked"

echo "📊 Removing model data from Git tracking..."
git rm -r --cached model_data/ 2>/dev/null || echo "   model_data not tracked"

echo "🐍 Removing virtual environment from Git tracking..."
git rm -r --cached .venv/ 2>/dev/null || echo "   .venv not tracked"

# Clean up any remaining untracked files that should be ignored
echo "🧹 Cleaning up untracked files..."
git clean -fd

echo "✅ Git violations fixed!"
echo "📝 Run 'git status' to see the current state"
echo "💾 Run 'git add .' and 'git commit -m \"Fix Git violations\"' to commit changes" 