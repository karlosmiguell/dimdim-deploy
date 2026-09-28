#!/usr/bin/env bash
# AULA 1 - Primeiro deploy: Resource Group + App Service Plan + Web App (Python)
source "$(dirname "$0")/config.sh"

echo ">> 1. Criando o Resource Group $RG em $LOCATION"
az group create --name "$RG" --location "$LOCATION" --output table

echo ">> 2. Criando plano + Web App e enviando o codigo (az webapp up)"
cd "$PASTA_APP"
az webapp up \
  --name "$WEBAPP" \
  --resource-group "$RG" \
  --plan "$PLAN" \
  --runtime "$RUNTIME" \
  --sku "$SKU" \
  --location "$LOCATION" \
  --os-type Linux

echo ">> 3. Definindo o comando de inicializacao (gunicorn)"
az webapp config set \
  --resource-group "$RG" \
  --name "$WEBAPP" \
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 app:app" \
  --output none

echo ""
echo "Pronto! Acesse: https://$(az webapp show -g "$RG" -n "$WEBAPP" --query defaultHostName -o tsv)"
echo "Ver logs ao vivo:  az webapp log tail -g $RG -n $WEBAPP"
