#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${DJAMP_HOME:-$HOME/Library/Application Support/DJAMP PRO}"
CA_CERT="$APP_HOME/certs/ca/djamp-pro-root-ca.crt"

if [[ ! -f "$CA_CERT" ]]; then
  echo "CA certificate not found at $CA_CERT"
  echo "Run generate-cert.sh first to bootstrap root CA."
  exit 1
fi

if [[ "$(uname -s)" == "Darwin" ]]; then
  sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "$CA_CERT"
  echo "Root CA installed in macOS System keychain"
  exit 0
fi

echo "Automatic install is implemented for macOS in this script."
exit 1
