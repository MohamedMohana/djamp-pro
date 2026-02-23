#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -lt 1 ]]; then
  echo "Usage: $0 <domain1> [domain2] ..."
  exit 1
fi

HOSTS_FILE="/etc/hosts"
BEGIN="# BEGIN DJAMP PRO MANAGED"
END="# END DJAMP PRO MANAGED"
TMP_FILE="$(mktemp)"

awk -v begin="$BEGIN" -v end="$END" '
  $0 == begin {in_block=1; next}
  $0 == end {in_block=0; next}
  !in_block {print}
' "$HOSTS_FILE" > "$TMP_FILE"

{
  echo
  echo "$BEGIN"
  for DOMAIN in "$@"; do
    echo "127.0.0.1 $DOMAIN"
  done
  echo "$END"
} >> "$TMP_FILE"

sudo cp "$TMP_FILE" "$HOSTS_FILE"
rm -f "$TMP_FILE"

echo "Updated $HOSTS_FILE"
