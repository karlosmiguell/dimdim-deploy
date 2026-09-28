#!/usr/bin/env bash
# Apaga TUDO que foi criado na aula (Web App, plano, SQL Server e banco).
source "$(dirname "$0")/config.sh"

echo ">> Recursos que serao apagados:"
az resource list -g "$RG" --query "[].{nome:name, tipo:type}" -o table
read -r -p "Apagar o Resource Group $RG? (s/N) " RESPOSTA
if [ "$RESPOSTA" = "s" ]; then
  az group delete --name "$RG" --yes --no-wait
  echo "Exclusao iniciada (leva alguns minutos). Acompanhe: az group show -n $RG"
fi
