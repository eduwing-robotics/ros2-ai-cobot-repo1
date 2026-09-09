#!/usr/bin/env bash
# Sourced only by Vision API launchers. Never print the credential.
vision_token_file="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/config/private/vision_api.token"
if [[ -f "${vision_token_file}" ]]; then
  IFS= read -r KSMC_VISION_API_TOKEN < "${vision_token_file}"
  if [[ ! "${KSMC_VISION_API_TOKEN}" =~ ^[[:xdigit:]]{64}$ ]]; then
    echo 'Invalid fixed Vision token: expected 64 hexadecimal characters.' >&2
    return 2
  fi
  export KSMC_VISION_API_TOKEN
fi
unset vision_token_file
