#!/usr/bin/env bash
# AULA 2 - Azure SQL Database + App Settings (variaveis de ambiente do Web App)
source "$(dirname "$0")/config.sh"

# Senha: minimo 8 caracteres com maiusculas, minusculas e numeros.
# Evite & ^ % ! " ' (quebram o az no Windows). Use por ex. @ # - _
if [ -z "${SQL_PASSWORD:-}" ]; then
  read -r -s -p "Senha do administrador do SQL Server: " SQL_PASSWORD
  echo
fi

echo ">> 0. Registrando o provedor Microsoft.Sql na assinatura (so na 1a vez demora)"
az provider register --namespace Microsoft.Sql --wait

echo ">> 1. Criando o servidor logico $SQL_SERVER"
az sql server create \
  --resource-group "$RG" \
  --name "$SQL_SERVER" \
  --location "$SQL_LOCATION" \
  --admin-user "$SQL_ADMIN" \
  --admin-password "$SQL_PASSWORD" \
  --output table

echo ">> 2. Liberando o firewall"
# 0.0.0.0 -> 0.0.0.0 = "Permitir servicos do Azure" (necessario para o Web App conectar)
az sql server firewall-rule create -g "$RG" -s "$SQL_SERVER" \
  -n PermitirServicosAzure --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 --output none
# Seu IP, para voce consultar o banco pelo portal (Query editor) ou Azure Data Studio
MEU_IP="$(curl -s https://api.ipify.org)"
az sql server firewall-rule create -g "$RG" -s "$SQL_SERVER" \
  -n MeuIP --start-ip-address "$MEU_IP" --end-ip-address "$MEU_IP" --output none
echo "   IP liberado: $MEU_IP"

echo ">> 3. Criando o banco $SQL_DB (oferta gratuita: serverless com pausa automatica)"
az sql db create \
  --resource-group "$RG" \
  --server "$SQL_SERVER" \
  --name "$SQL_DB" \
  --edition GeneralPurpose --family Gen5 --capacity 2 \
  --compute-model Serverless \
  --use-free-limit --free-limit-exhaustion-behavior AutoPause \
  --backup-storage-redundancy Local \
  --output table
# Se a assinatura ja usou a oferta gratuita, use o tier Basic (~5 USD/mes):
# az sql db create -g "$RG" -s "$SQL_SERVER" -n "$SQL_DB" --service-objective Basic --backup-storage-redundancy Local

echo ">> 4. Passando a conexao para o Web App via App Settings"
az webapp config appsettings set \
  --resource-group "$RG" \
  --name "$WEBAPP" \
  --settings \
    SQL_SERVER="$SQL_SERVER.database.windows.net" \
    SQL_DATABASE="$SQL_DB" \
    SQL_USER="$SQL_ADMIN" \
    SQL_PASSWORD="$SQL_PASSWORD" \
  --output none

echo ">> 5. Reiniciando o Web App"
az webapp restart -g "$RG" -n "$WEBAPP"

URL="https://$(az webapp show -g "$RG" -n "$WEBAPP" --query defaultHostName -o tsv)"
echo ""
echo "Pronto! Confira o banco em: $URL/health  (deve mostrar \"banco\": \"azure-sql\")"
echo "Obs.: o banco gratuito pausa quando ocioso; o 1o acesso pode levar ~1 min (503). Recarregue."
