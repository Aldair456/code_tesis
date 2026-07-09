#!/bin/bash
set -e

# Construir la imagen Docker usando sudo
sudo docker build -t lambda-layer-builder .

# Crear un contenedor a partir de la imagen y obtener su ID
container_id=$(sudo docker create lambda-layer-builder)

# Copiar el archivo ZIP generado desde el contenedor a la raíz del proyecto
sudo docker cp "$container_id":/layer_common_lib.zip ./layer_common_lib.zip

# Eliminar el contenedor temporal
sudo docker rm "$container_id"

echo "El archivo layer_common_lib.zip se ha creado exitosamente."
