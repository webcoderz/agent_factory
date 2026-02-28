FROM python:3.11-slim

WORKDIR /repo

# optional but helpful
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# If you use uv in this repo already, swap to uv here.
# Keeping pip-simple so it works everywhere tomorrow.
COPY pyproject.toml /repo/pyproject.toml
COPY README.md /repo/README.md

# Install runtime deps only (you can refine tomorrow)
RUN pip install --no-cache-dir rich

# If you want pydantic-ai here, add:
# RUN pip install --no-cache-dir "agent-patterns[agent]"
# (or pip install pydantic-ai)

COPY . /repo

CMD ["python", "-m", "agent_ext.workbench"]
