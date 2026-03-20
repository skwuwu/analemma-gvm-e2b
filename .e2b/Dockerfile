# e2b custom template for Analemma GVM demo.
# Built on top of the pre-published GVM runtime image.
# Adds curl, Python, and demo scenario configs.
#
# Build and register:
#   e2b template build --name analemma-gvm
#
# Use in demo.py:
#   Sandbox(template="analemma-gvm")

FROM ghcr.io/skwuwu/analemma-gvm:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    python3 \
    python3-pip \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Demo scenario configs
COPY scenarios/ /app/config/

# Startup helper: writes a GVM-SDK-compatible request and captures decision
COPY scripts/run_scenario.sh /usr/local/bin/run_scenario
RUN chmod +x /usr/local/bin/run_scenario

WORKDIR /app
