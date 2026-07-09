# =============================================================================
# Construye model1IaLib.zip (Lambda layer): python/lib/python3.11/site-packages/
#
# Desde la raíz del repo:
#   docker build -f models/model_1V2/Dockerfile -t model1v2-layer models/model_1V2
#   docker run --rm -v "%cd%/models/model_1V2:/out" model1v2-layer    (Windows)
#   docker run --rm -v "$(pwd)/models/model_1V2:/out" model1v2-layer  (Linux/macOS)
#
# Salida: models/model_1V2/model1IaLib.zip → usado por model_1_ia_v2.yml
# =============================================================================

FROM python:3.11-slim-bookworm

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends zip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN mkdir -p python/lib/python3.11/site-packages \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt -t python/lib/python3.11/site-packages

RUN zip -r9 /model1IaLib.zip python

CMD ["sh", "-c", "cp /model1IaLib.zip /out/model1IaLib.zip && ls -la /out/model1IaLib.zip"]
