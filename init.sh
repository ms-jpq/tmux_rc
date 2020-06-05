#!/usr/bin/env bash

set -eu
set -o pipefail


plugins="$(rg '^set -g @plugin' < entry.conf)"
uris="$(echo "$plugins" | sd 'set -g @plugin "([^"]+)"' '$1' | xargs -l printf 'https://github.com/%s\n')"

cd "$(dirname "$0")/plugins" || exit 1

echo "$uris" | xargs -l git clone --depth=1
