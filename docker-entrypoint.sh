#!/bin/sh
# Runs the app as PUID:PGID instead of root.
#
# Started as root (the default), it takes ownership of the data folder, so
# files written by older images (which ran as root) stay writable, then drops
# to PUID:PGID.  Started as another user (`user:` in Compose), it runs as is.
set -e

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
DATA_DIR="$(dirname "${DB_PATH:-/data/jobs.db}")"

case "$PUID$PGID" in
    *[!0-9]*|"") echo "PUID and PGID must be numbers (got PUID=$PUID PGID=$PGID)" >&2; exit 1 ;;
esac

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR"
    # Only touches files that aren't already owned by PUID:PGID.
    if ! find "$DATA_DIR" \( ! -user "$PUID" -o ! -group "$PGID" \) -exec chown "$PUID:$PGID" {} +; then
        echo "Warning: could not change the owner of $DATA_DIR to $PUID:$PGID" >&2
    fi
    # HOME stays /root otherwise, which the dropped user cannot write to.
    export HOME=/tmp
    exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups "$@"
fi

exec "$@"
