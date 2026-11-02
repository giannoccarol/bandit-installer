#!/bin/sh
# Builds the release packages from the committed tree (HEAD):
#   dist/bandit-installer-<version>-linux.tar.gz
#   dist/bandit-installer-<version>-windows.zip   (with the official embeddable Python)
#   dist/SHA256SUMS
# Usage: scripts/build-release.sh [cache folder for the Python download]
set -eu

cd "$(dirname "$0")/.."
PY_VERSION=3.14.10
PY_ZIP="python-$PY_VERSION-embed-amd64.zip"
PY_URL="https://www.python.org/ftp/python/$PY_VERSION/$PY_ZIP"
# from python.org (also listed in the file's .spdx.json)
PY_SHA256=90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159

VERSION=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' bandit_installer/web.py)
[ -n "$VERSION" ] || { echo "VERSION not found in bandit_installer/web.py"; exit 1; }
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "Commit your changes first: the packages are built from HEAD."; exit 1
fi

NAME="bandit-installer-$VERSION"
CACHE="${1:-${XDG_CACHE_HOME:-$HOME/.cache}/bandit-installer}"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
rm -rf dist && mkdir -p dist "$CACHE"

# sources, with the .gitattributes line endings (installer.bat in CRLF)
git archive --format=tar --prefix="$NAME/" HEAD | tar -x -C "$STAGE"
rm -rf "$STAGE/$NAME/scripts" "$STAGE/$NAME/tests" "$STAGE/$NAME/.gitattributes" "$STAGE/$NAME/.gitignore"
# rom/ and twrp/ keep only their README.txt: the ROM and TWRP are downloaded separately

# Linux
tar -C "$STAGE" --owner=0 --group=0 --sort=name -czf "dist/$NAME-linux.tar.gz" "$NAME"

# Windows: add the embeddable Python in python\
if [ ! -f "$CACHE/$PY_ZIP" ]; then
    curl -fL --proto '=https' -o "$CACHE/$PY_ZIP.part" "$PY_URL"
    mv "$CACHE/$PY_ZIP.part" "$CACHE/$PY_ZIP"
fi
echo "$PY_SHA256  $CACHE/$PY_ZIP" | sha256sum -c -
mkdir "$STAGE/$NAME/python"
python3 -I -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$CACHE/$PY_ZIP" "$STAGE/$NAME/python"
(cd "$STAGE" && zip -qrX9 "$OLDPWD/dist/$NAME-windows.zip" "$NAME")

(cd dist && sha256sum "$NAME-linux.tar.gz" "$NAME-windows.zip" > SHA256SUMS && cat SHA256SUMS)
