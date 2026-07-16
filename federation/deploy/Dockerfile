# AIR/1 federation node - dependency-free stdlib HTTP wrapper around the
# independent air_federation_verifier package.
FROM python:3.12-slim

WORKDIR /app

# Install the verifier package itself (the parent dir is the build context).
COPY pyproject.toml README.md ./
COPY air_federation_verifier ./air_federation_verifier
RUN pip install --no-cache-dir .

# The HTTP node wrapper.
COPY deploy/server.py ./server.py

ENV AIR_NODE_PORT=8080
EXPOSE 8080

# Simple in-container liveness check against the /health endpoint.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"AIR_NODE_PORT\",\"8080\")}/health').status==200 else 1)"

CMD ["python", "server.py"]
