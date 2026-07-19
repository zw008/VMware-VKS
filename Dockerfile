FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
COPY vmware_vks/ vmware_vks/

RUN uv pip install --system .

CMD ["python", "-m", "vmware_vks.mcp_server"]
