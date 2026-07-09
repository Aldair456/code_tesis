# Model 1 V2 (Reducto + IA propia)

Pipeline paralelo a `model_1`: PDF → Reducto → payload → BS/PL/CF → `subir_bd`.

## Dependencias Python (`requirements.txt`)

- Uso local: `pip install -r requirements.txt` (desde esta carpeta o con path al archivo).
- **Lambda**: las dependencias pesadas van en el **layer** `model1IaLib.zip`, referenciado en `model_1_ia_v2.yml`.

## Layer `model1IaLib.zip` con Docker

Desde la **raíz del repo** `vera-app_backend`:

```bash
docker build -f models/model_1V2/Dockerfile -t model1v2-layer models/model_1V2
```

**Windows (PowerShell):**

```powershell
docker run --rm -v "${PWD}/models/model_1V2:/out" model1v2-layer
```

**Linux / macOS:**

```bash
docker run --rm -v "$(pwd)/models/model_1V2:/out" model1v2-layer
```

Debe aparecer `models/model_1V2/model1IaLib.zip`. Ese archivo es el que usa Serverless en `artifact: models/model_1V2/model1IaLib.zip`.

### Notas

- El código de `src/` se empaqueta aparte en el deploy Serverless (`package.include`); el layer solo lleva **site-packages**.
- Si cambias versiones en `requirements.txt`, vuelve a construir el zip antes de deploy.
- Si una dependencia nativa no encuentra wheel para AL2/AL2023, construye con una imagen `sam/build-python3.11` y el mismo `pip install -t`.
