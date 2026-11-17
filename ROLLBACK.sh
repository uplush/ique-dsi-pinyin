#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [ "$#" -ne 3 ]; then
  echo 'Usage: ROLLBACK.sh patched-file undo.zip new-restored-file' >&2
  exit 2
fi
exec "${PYTHON:-python}" "$HERE/patch.py" rollback "$1" "$2" "$3"
