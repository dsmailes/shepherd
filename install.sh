#!/bin/sh
set -eu
pack_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$pack_root/scripts/install.py" "$@"
