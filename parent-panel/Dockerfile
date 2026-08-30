ARG BUILD_FROM
FROM ${BUILD_FROM}

# TV Sitter — parental control for Android TV / Google TV.
# Copyright (C) 2026 Tomasz Syc
# SPDX-License-Identifier: AGPL-3.0-only

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# One dependency. The panel asks Home Assistant questions over HTTP and renders the answers;
# a framework would be more to keep current than the thing it is serving.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY panel /opt/panel
COPY run.sh /run.sh
RUN chmod a+x /run.sh

# So that `python3 -m panel` finds it. Copying a package somewhere nothing points at is a
# container that starts, logs one line and exits — which is exactly what the first install
# did, and the only place it said so was the Supervisor's log.
WORKDIR /opt

CMD ["/run.sh"]
