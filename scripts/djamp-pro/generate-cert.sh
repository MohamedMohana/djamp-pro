#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-}"
if [[ -z "$DOMAIN" ]]; then
  echo "Usage: $0 <domain> [alt1,alt2,...]"
  exit 1
fi

ALT_CSV="${2:-}"
APP_HOME="${DJAMP_HOME:-$HOME/Library/Application Support/DJAMP PRO}"
CA_DIR="$APP_HOME/certs/ca"
CERT_DIR="$APP_HOME/certs"
CA_CERT="$CA_DIR/djamp-pro-root-ca.crt"
CA_KEY="$CA_DIR/djamp-pro-root-ca.key"
CERT="$CERT_DIR/$DOMAIN.crt"
KEY="$CERT_DIR/$DOMAIN.key"
CONF="$CERT_DIR/$DOMAIN.cnf"
CSR="$CERT_DIR/$DOMAIN.csr"

mkdir -p "$CA_DIR" "$CERT_DIR"

if [[ ! -f "$CA_CERT" || ! -f "$CA_KEY" ]]; then
  openssl req -x509 -newkey rsa:4096 -keyout "$CA_KEY" -out "$CA_CERT" -days 3650 -nodes \
    -subj "/C=US/ST=Local/L=Local/O=DJAMP PRO/OU=Development/CN=DJAMP PRO Root CA" \
    -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
    -addext "keyUsage=critical,keyCertSign,cRLSign"
fi

SAN=("DNS.1 = $DOMAIN")
INDEX=2
if [[ -n "$ALT_CSV" ]]; then
  IFS=',' read -ra ALTS <<< "$ALT_CSV"
  for ALT in "${ALTS[@]}"; do
    ALT_TRIMMED="$(echo "$ALT" | xargs)"
    if [[ -n "$ALT_TRIMMED" ]]; then
      SAN+=("DNS.$INDEX = $ALT_TRIMMED")
      INDEX=$((INDEX + 1))
    fi
  done
fi

{
  echo "[req]"
  echo "distinguished_name = req_distinguished_name"
  echo "req_extensions = v3_req"
  echo "prompt = no"
  echo
  echo "[req_distinguished_name]"
  echo "CN = $DOMAIN"
  echo
  echo "[v3_req]"
  echo "keyUsage = keyEncipherment, dataEncipherment"
  echo "extendedKeyUsage = serverAuth"
  echo "subjectAltName = @alt_names"
  echo
  echo "[alt_names]"
  for LINE in "${SAN[@]}"; do
    echo "$LINE"
  done
} > "$CONF"

openssl genrsa -out "$KEY" 2048
openssl req -new -key "$KEY" -out "$CSR" -config "$CONF"
openssl x509 -req -in "$CSR" -CA "$CA_CERT" -CAkey "$CA_KEY" -CAcreateserial -out "$CERT" -days 365 -sha256 -extensions v3_req -extfile "$CONF"

rm -f "$CSR" "$CONF"

echo "Certificate generated: $CERT"
echo "Key generated: $KEY"
