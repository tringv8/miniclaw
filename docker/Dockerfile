FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install Node.js 20 for the WhatsApp bridge
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg git && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get purge -y gnupg && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app"

ARG MINICLAW_REPO=https://github.com/tringv8/Miniclaw.git
ARG MINICLAW_REF=main

RUN git clone "${MINICLAW_REPO}" . && \
    git -c advice.detachedHead=false checkout "${MINICLAW_REF}" && \
    rm -rf .git

RUN uv pip install --system -r requirements.txt

WORKDIR /app/bridge
RUN npm install && npm run build
WORKDIR /app

# Create config directory
RUN mkdir -p /root/.miniclaw

# Gateway + Launcher ports
EXPOSE 18790 18801

ENTRYPOINT ["miniclaw"]
CMD ["status"]
