# Configuracao compartilhada pelos scripts. EDITE a variavel ALUNO.
# Os nomes do Web App e do SQL Server precisam ser unicos no Azure inteiro,
# por isso usamos o seu nome como sufixo (so letras minusculas e numeros).

ALUNO="${ALUNO:-seunome}"      # ou rode: ALUNO=fulano bash scripts/...
LOCATION="${LOCATION:-brazilsouth}"   # erro "disallowed by Azure"? veja as regioes liberadas no README

RG="rg-dimdim-$ALUNO"
PLAN="plan-dimdim-$ALUNO"
WEBAPP="app-dimdim-$ALUNO"
RUNTIME="PYTHON:3.12"
SKU="F1"                        # F1 = gratuito

SQL_SERVER="${SQL_SERVER:-sql-dimdim-$ALUNO}"
SQL_LOCATION="${SQL_LOCATION:-$LOCATION}"   # o banco pode ficar em outra regiao se a sua estiver sem capacidade
SQL_DB="dimdim"
SQL_ADMIN="dimdimadmin"

if [ "$ALUNO" = "seunome" ]; then
  echo "Edite scripts/config.sh e troque ALUNO=\"seunome\" pelo seu nome." >&2
  exit 1
fi

set -euo pipefail
PASTA_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASTA_APP="$PASTA_SCRIPTS/../app"
