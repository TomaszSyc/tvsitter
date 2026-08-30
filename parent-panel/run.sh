#!/usr/bin/with-contenv bashio
# TV Sitter — parental control for Android TV / Google TV.
# Copyright (C) 2026 Tomasz Syc
# SPDX-License-Identifier: AGPL-3.0-only
set -euo pipefail

bashio::log.info "TV Sitter parent panel starting"
exec python3 -m panel
