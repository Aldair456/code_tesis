# Stage 1: Construcción del layer usando la imagen oficial de AWS Lambda para Python 3.9
FROM public.ecr.aws/lambda/python:3.11 AS builder

WORKDIR /app

# Instalar el paquete zip
RUN yum install -y zip

# Copiar el archivo de requerimientos a la raíz del contenedor
COPY requirements.txt .

# Crear la estructura del layer (la carpeta 'python' es requerida por AWS Lambda)
RUN mkdir -p layer_common_lib/python

# Instalar las dependencias en la carpeta layer_common_lib/python
RUN pip install -r requirements.txt -t layer_common_lib/python

# Empaquetar el contenido del layer en un archivo ZIP
RUN cd layer_common_lib && zip -r ../layer_common_lib.zip .

# Stage 2: Imagen final usando busybox para incluir un comando dummy
FROM busybox AS final
COPY --from=builder /app/layer_common_lib.zip /layer_common_lib.zip
CMD ["cat", "/layer_common_lib.zip"]
