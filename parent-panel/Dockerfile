ARG BUILD_FROM
FROM ${BUILD_FROM}

# TV Sitter — parental control for Android TV / Google TV.
# Copyright (C) 2026 Tomasz Syc
# SPDX-License-Identifier: AGPL-3.0-only

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# One dependency. The panel asks Home Assistant questions over HTTP and renders the answers;
# a framework would be more to keep current than the thing it is serving.
RUN pip install --no-cache-dir "aiohttp==3.13.2"

COPY panel /opt/panel
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
