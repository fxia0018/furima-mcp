# MCP over stdio: docker run -i --rm furima-mcp
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# Reads public pages over HTTPS and writes nothing, so it runs unprivileged.
USER nobody
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["furima-mcp"]
