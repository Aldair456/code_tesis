# Usar imagen base de Python 3.11 con Debian (tiene GLIBC 2.28+)
# Luego instalamos el runtime de Lambda manualmente
FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para WeasyPrint
# WeasyPrint requiere: Cairo, Pango, GDK-PixBuf, Fontconfig
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fontconfig \
    fonts-liberation \
    fonts-unifont \
    fonts-dejavu \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    && rm -rf /var/lib/apt/lists/*

# Evitar errores de fontconfig tipo "No writable cache directories" en Lambda:
# forzamos HOME y cache a /tmp (writable).
ENV HOME=/tmp
ENV XDG_CACHE_HOME=/tmp
RUN mkdir -p /tmp/.cache/fontconfig && chmod -R 777 /tmp/.cache

# Regenerar cache de fuentes para que WeasyPrint las reconozca
RUN fc-cache -fv

# Instalar AWS Lambda Runtime Interface Client (RIC)
RUN pip install --no-cache-dir awslambdaric

# Copiar requirements e instalar dependencias Python
COPY services/service_credit_proposal_coril/requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copiar código común necesario
COPY common/ ${LAMBDA_TASK_ROOT}/common/
COPY common_aws_clients/ ${LAMBDA_TASK_ROOT}/common_aws_clients/
COPY common_ia_clients/ ${LAMBDA_TASK_ROOT}/common_ia_clients/

COPY common_appsync/ ${LAMBDA_TASK_ROOT}/common_appsync/
# Copiar código del servicio
COPY services/service_credit_proposal_coril/src/ ${LAMBDA_TASK_ROOT}/services/service_credit_proposal_coril/src/

# Copiar repositorio de business que se usa desde service_loans
COPY services/service_loans/src/repositories/ ${LAMBDA_TASK_ROOT}/services/service_loans/src/repositories/

# Configurar variables de entorno para Lambda
ENV LAMBDA_TASK_ROOT=/var/task
ENV LAMBDA_RUNTIME_DIR=/var/runtime

# Configurar el entrypoint para usar el runtime de Lambda
ENTRYPOINT [ "python", "-m", "awslambdaric" ]

# Configurar el handler principal (puedes cambiarlo según necesites)
# Para diferentes handlers, puedes crear múltiples funciones Lambda con diferentes CMD
CMD [ "services.service_credit_proposal_coril.src.handlers.create_credit_proposal_coril.lambda_handler" ]
