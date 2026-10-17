#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$(readlink -f "$0")")"
# Keep this helper consistent with the automatic launcher; running it is optional.
exec ./start_gui.sh
