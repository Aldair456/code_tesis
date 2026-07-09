#!/bin/bash

# Script para deployar la imagen Docker a AWS Lambda
# Uso: ./deploy.sh [AWS_REGION] [AWS_ACCOUNT_ID] [IMAGE_TAG]
#      IMAGE_TAG: dev | prod | latest (por defecto: dev)
#      Ejemplo dev:  ./deploy.sh us-east-1 051826715282 dev
#      Ejemplo prod: ./deploy.sh us-east-1 051826715282 prod

set -e

# Configuración
AWS_REGION=${1:-us-east-1}
AWS_ACCOUNT_ID=${2}
IMAGE_NAME="credit-proposal-coril"
IMAGE_TAG=${3:-dev}
ECR_REPOSITORY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${IMAGE_NAME}"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Iniciando deploy de ${IMAGE_NAME} a AWS Lambda${NC}\n"

# Verificar que AWS CLI está instalado
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI no está instalado. Instálalo desde: https://aws.amazon.com/cli/${NC}"
    exit 1
fi

# Verificar que Docker está corriendo
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker no está corriendo. Inicia Docker Desktop.${NC}"
    exit 1
fi

# Verificar AWS_ACCOUNT_ID
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${YELLOW}⚠️  AWS_ACCOUNT_ID no proporcionado. Obteniéndolo de AWS CLI...${NC}"
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    if [ -z "$AWS_ACCOUNT_ID" ]; then
        echo -e "${RED}❌ No se pudo obtener AWS_ACCOUNT_ID. Configura AWS CLI primero.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ AWS Account ID: ${AWS_ACCOUNT_ID}${NC}\n"
fi

# 1. Crear repositorio ECR si no existe
echo -e "${YELLOW}📦 Verificando repositorio ECR...${NC}"
if ! aws ecr describe-repositories --repository-names ${IMAGE_NAME} --region ${AWS_REGION} &> /dev/null; then
    echo -e "${YELLOW}   Creando repositorio ECR...${NC}"
    aws ecr create-repository \
        --repository-name ${IMAGE_NAME} \
        --region ${AWS_REGION} \
        --image-scanning-configuration scanOnPush=true \
        --image-tag-mutability MUTABLE
    echo -e "${GREEN}✓ Repositorio ECR creado${NC}\n"
else
    echo -e "${GREEN}✓ Repositorio ECR ya existe${NC}\n"
fi

# 2. Autenticar Docker con ECR
echo -e "${YELLOW}🔐 Autenticando Docker con ECR...${NC}"
aws ecr get-login-password --region ${AWS_REGION} | \
    docker login --username AWS --password-stdin ${ECR_REPOSITORY}
echo -e "${GREEN}✓ Autenticación exitosa${NC}\n"

# 3. Taggear la imagen (solo el tag indicado: dev, prod, etc.)
echo -e "${YELLOW}🏷️  Taggeando imagen como ${ECR_REPOSITORY}:${IMAGE_TAG} ...${NC}"
docker tag ${IMAGE_NAME}:latest ${ECR_REPOSITORY}:${IMAGE_TAG}
echo -e "${GREEN}✓ Imagen taggeada${NC}\n"

# 4. Push a ECR (solo el tag indicado; así dev y prod no se pisan)
echo -e "${YELLOW}📤 Subiendo imagen a ECR (esto puede tardar varios minutos)...${NC}"
docker push ${ECR_REPOSITORY}:${IMAGE_TAG}
echo -e "${GREEN}✓ Imagen subida exitosamente${NC}\n"

# 5. Mostrar URI de la imagen
echo -e "${GREEN}✅ Deploy completado!${NC}\n"
echo -e "URI de la imagen: ${ECR_REPOSITORY}:${IMAGE_TAG}"
echo -e "\n${YELLOW}Próximos pasos:${NC}"
echo -e "  Deploy a Lambda (usa la imagen según stage):"
echo -e "  STAGE=${IMAGE_TAG} serverless deploy   # o: serverless deploy --stage ${IMAGE_TAG}"

