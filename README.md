# DimDim: deploy de Python no Azure App Service com Azure CLI

Projeto de aula: uma API Flask com página web (usuários com entradas e saídas
de dinheiro + produtos em falta no estoque) publicada no **Azure App Service**,
com dados no **Azure SQL Database**. Tudo é criado com **Azure CLI**.

A conexão com o banco não fica no código: vem das **App Settings** do Web App
(variáveis de ambiente `SQL_SERVER`, `SQL_DATABASE`, `SQL_USER` e `SQL_PASSWORD`).

```
dimdim-deploy/
├── app/                  <- SOMENTE esta pasta vai para o Azure
│   ├── app.py            rotas da API + conexão com o Azure SQL
│   ├── models.py         tabelas (SQLAlchemy)
│   ├── templates/        página inicial
│   ├── static/           CSS e logo (padrão FIAP)
│   └── requirements.txt
├── scripts/              (opcional) os mesmos comandos deste README em scripts bash
└── requests.http         testes da API
```

## Arquitetura

```
 Navegador ──HTTPS──> Azure App Service (Linux, Python 3.12, gunicorn)
                              │  App Settings: SQL_SERVER, SQL_DATABASE,
                              │                SQL_USER, SQL_PASSWORD
                              ▼
                      Azure SQL Database (porta 1433, TLS, firewall)
```

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | página web |
| GET | `/health` | status do app e da conexão com o Azure SQL (200 ok / 503 erro) |
| GET/POST | `/api/usuarios` | listar / criar usuário `{"nome": "..."}` |
| GET | `/api/usuarios/<id>` | usuário com extrato |
| POST | `/api/usuarios/<id>/transacoes` | `{"tipo": "entrada"\|"saida", "valor": 100}` |
| GET/POST | `/api/out_stock` | listar / criar `{"codigo", "descricao", "data_solicitacao"}` |
| PUT/DELETE | `/api/out_stock/<id>` | atualizar / remover |

---

## Pré-requisitos

- Conta no Azure (Azure for Students serve).
- **Azure CLI** e um terminal **bash**: o **Azure Cloud Shell** do portal (já tem
  tudo) ou o **Git Bash** no Windows com o Azure CLI instalado.
- Não precisa instalar Python: o build e a execução acontecem no Azure.
- Clone este repositório e abra o terminal na pasta `dimdim-deploy`.

## Passo 0: login e variáveis

Faça login e confira se a assinatura está certa:

```bash
az login
```

```bash
az account show -o table
```

Descubra em quais regiões a sua assinatura pode criar recursos. A Azure for
Students aplica uma política que muda de conta para conta:

```bash
az policy assignment list --query "[?displayName=='Allowed resource deployment regions'].parameters.listOfAllowedLocations.value" -o tsv
```

Se a lista vier vazia, não existe restrição e `brazilsouth` funciona.

Agora defina as variáveis usadas em todos os comandos. Troque `seunome` (só
letras minúsculas e números) e a região. Os nomes do Web App e do SQL Server
precisam ser **únicos no Azure inteiro**.

```bash
ALUNO=seunome
LOCATION=francecentral
RG=rg-dimdim-$ALUNO
PLAN=plan-dimdim-$ALUNO
WEBAPP=app-dimdim-$ALUNO
SQL_SERVER=sql-dimdim-$ALUNO
SQL_LOCATION=$LOCATION
SQL_DB=dimdim
SQL_ADMIN=dimdimadmin
```

> ⚠️ As variáveis valem só para este terminal. Se fechar ou abrir outro, defina
> de novo antes de continuar.

---

## Aula 1: primeiro deploy (App Service)

### 1. Criar o Resource Group

A "pasta" que agrupa todos os recursos da aula e facilita apagar tudo no final.

```bash
az group create --name $RG --location $LOCATION
```

### 2. Criar o plano + Web App e enviar o código

O `az webapp up` cria o **App Service Plan** (a máquina, SKU **F1 gratuito**) e o
**Web App**, compacta a pasta atual e faz o deploy. No Azure, o **Oryx** roda o
`pip install -r requirements.txt`. Rode o comando **de dentro da pasta `app/`**:

```bash
cd app
```

```bash
az webapp up --name $WEBAPP --resource-group $RG --plan $PLAN --runtime PYTHON:3.12 --sku F1 --location $LOCATION --os-type Linux
```

### 3. Definir o comando de inicialização

Diz ao App Service Linux como iniciar o app: `gunicorn`, o servidor de produção,
carregando o objeto `app` do arquivo `app.py`.

```bash
az webapp config set --resource-group $RG --name $WEBAPP --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 app:app"
```

### 4. Abrir e explorar

```bash
az webapp browse --resource-group $RG --name $WEBAPP
```

O site já está no ar, com o selo **Azure SQL (não configurado)** e um aviso para
criar o banco. O `/health` responde 503 até a aula 2.

Ver os logs ao vivo (Ctrl+C para sair):

```bash
az webapp log tail --resource-group $RG --name $WEBAPP
```

Ver os detalhes do Web App:

```bash
az webapp show --resource-group $RG --name $WEBAPP --query "{estado:state, url:defaultHostName, runtime:siteConfig.linuxFxVersion}" -o table
```

### 5. Redeploy

Altere algo (por exemplo, o título em `templates/index.html`) e, dentro de `app/`, rode:

```bash
az webapp up --runtime PYTHON:3.12
```

O `az webapp up` lembra nome, grupo, plano e SKU (salvos em `app/.azure/config`),
**mas não o runtime**. Se você rodar só `az webapp up`, ele troca o site para a
versão padrão do Python (vimos cair para 3.10). A página mostra a versão em uso:
confira depois do deploy.

> 💡 Na página, repare no campo **Container**: cada deploy cria um container
> novo. Por isso nada pode ser guardado em arquivo dentro do app. Os dados
> ficam no banco gerenciado (aula 2).

---

## Aula 2: Azure SQL Database

### 1. Registrar o provedor do SQL na assinatura

Assinaturas novas precisam "ativar" o serviço SQL uma vez. Sem isso dá
`MissingSubscriptionRegistration`. Pode levar alguns minutos:

```bash
az provider register --namespace Microsoft.Sql --wait
```

### 2. Definir a senha do administrador

Mínimo 8 caracteres, com maiúsculas, minúsculas e números. **Evite `& ^ % ! " '`**,
porque o `az` no Windows é um `.cmd` e esses caracteres quebram o comando. Use por
exemplo `@ # - _`. O comando abaixo pede a senha sem mostrá-la na tela:

```bash
read -s -p "Senha do SQL: " SQL_PASSWORD; echo
```

### 3. Criar o servidor lógico

O servidor tem o endpoint `<nome>.database.windows.net` e o login de administrador:

```bash
az sql server create --resource-group $RG --name $SQL_SERVER --location $SQL_LOCATION --admin-user $SQL_ADMIN --admin-password "$SQL_PASSWORD"
```

### 4. Liberar o firewall

Por padrão **ninguém** acessa o servidor. A regra de `0.0.0.0` a `0.0.0.0`
significa "permitir serviços do Azure", e é ela que deixa o Web App conectar:

```bash
az sql server firewall-rule create --resource-group $RG --server $SQL_SERVER --name PermitirServicosAzure --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
```

Libere também o seu IP, para consultar o banco pelo **Query editor** do portal:

```bash
MEU_IP=$(curl -s https://api.ipify.org)
```

```bash
az sql server firewall-rule create --resource-group $RG --server $SQL_SERVER --name MeuIP --start-ip-address $MEU_IP --end-ip-address $MEU_IP
```

### 5. Criar o banco (oferta gratuita)

O banco usa o modelo serverless na oferta gratuita e **pausa sozinho** quando
fica ocioso:

```bash
az sql db create --resource-group $RG --server $SQL_SERVER --name $SQL_DB --edition GeneralPurpose --family Gen5 --capacity 2 --compute-model Serverless --use-free-limit --free-limit-exhaustion-behavior AutoPause --backup-storage-redundancy Local
```

Se a assinatura já usou a oferta gratuita, crie no tier **Basic** (cerca de 5 USD/mês):

```bash
az sql db create --resource-group $RG --server $SQL_SERVER --name $SQL_DB --service-objective Basic --backup-storage-redundancy Local
```

### 6. Passar a conexão para o Web App (App Settings)

As **App Settings** viram **variáveis de ambiente** dentro do app. O código lê
`os.environ["SQL_SERVER"]` e conecta. **Nenhuma linha de código muda e não há novo deploy.**

```bash
az webapp config appsettings set --resource-group $RG --name $WEBAPP --settings SQL_SERVER=$SQL_SERVER.database.windows.net SQL_DATABASE=$SQL_DB SQL_USER=$SQL_ADMIN SQL_PASSWORD="$SQL_PASSWORD"
```

Conferir o que foi gravado:

```bash
az webapp config appsettings list --resource-group $RG --name $WEBAPP -o table
```

### 7. Reiniciar e testar

```bash
az webapp restart --resource-group $RG --name $WEBAPP
```

```bash
curl https://$WEBAPP.azurewebsites.net/health
```

A resposta deve trazer `"banco_conectado": true`, e a página passa a mostrar o
selo verde **Azure SQL**. O banco gratuito pode estar pausado: se vier 503,
espere cerca de 1 minuto e tente de novo.

Cadastre dados na página e faça um redeploy (`az webapp up --runtime PYTHON:3.12`
dentro de `app/`). O container muda, mas **os dados permanecem**.

### 8. Consultar o banco

No portal: SQL database `dimdim` → **Query editor**, logando com `dimdimadmin`:

```sql
SELECT * FROM usuarios;
SELECT * FROM transacoes;
SELECT * FROM out_stock;
```

> 🔐 **Discussão sobre segurança:** a senha está em App Settings, em texto no
> portal. Em produção se usa **Key Vault references** ou **Managed Identity**
> (sem senha). A regra `0.0.0.0` libera *qualquer* serviço do Azure; o ideal é
> **VNet Integration + Private Endpoint**.

---

## Encerramento: apagar tudo

Veja o que foi criado:

```bash
az resource list --resource-group $RG -o table
```

Apague o Resource Group inteiro (Web App, plano, SQL Server e banco):

```bash
az group delete --name $RG --yes --no-wait
```

---

## Atalho (opcional): scripts

A pasta `scripts/` tem os mesmos comandos em scripts bash, para quem quiser
repetir tudo de uma vez. Eles usam as variáveis de `scripts/config.sh`, que podem
ser passadas na linha de comando:

```bash
ALUNO=seunome LOCATION=francecentral bash scripts/aula1-webapp.sh
```

```bash
ALUNO=seunome LOCATION=francecentral bash scripts/aula2-azure-sql.sh
```

```bash
ALUNO=seunome bash scripts/limpar.sh
```

---

## Problemas comuns

| Sintoma | Causa / solução |
|---|---|
| `Application Error` na página | rode o `az webapp log tail`. Normalmente é erro no `requirements.txt` ou no startup command |
| Deploy demorou e ficou 5+ min em "Starting" | normal no F1 na primeira vez ou ao trocar a versão do Python |
| Página mostra "banco não configurado" | faltam as App Settings `SQL_*`. Rode o passo 6 da aula 2 e confira com `az webapp config appsettings list` |
| `/health` retorna **503** com `banco_configurado: true` logo após criar o banco | o banco serverless estava pausado e está "acordando" (~1 min). Recarregue |
| `/health` 503 com `Login failed` no log | senha ou usuário errados nas App Settings |
| `Cannot open server ... not allowed to access` | falta regra de firewall (`PermitirServicosAzure` ou o seu IP) |
| `The subscription ... free limit` / erro no `--use-free-limit` | a assinatura já usa a oferta gratuita. Use o comando com `--service-objective Basic` |
| `RequestDisallowedByAzure` / *disallowed by Azure* | região bloqueada pela política da assinatura. Veja as regiões liberadas (passo 0) e troque `LOCATION` |
| `MissingSubscriptionRegistration` ... `Microsoft.Sql` | faltou o passo 1 da aula 2: `az provider register --namespace Microsoft.Sql --wait` |
| `RegionDoesNotAllowProvisioning` (SQL) | a região está sem capacidade para SQL. Troque só `SQL_LOCATION` para outra região liberada e rode de novo o passo 3 |
| `already exists in location ...` logo após um erro | a tentativa que falhou deixou um registro temporário, que pode demorar horas para sumir. Use outro nome só para o servidor (`SQL_SERVER=sql-dimdim-$ALUNO-2`) e continue |
| Página mostra Python 3.10 depois do redeploy | você rodou `az webapp up` sem `--runtime PYTHON:3.12` |
| Nome já existe (`is already taken`) | nomes de Web App e SQL Server são globais. Mude `ALUNO` e redefina as variáveis |
| Comando falha com "argument expected" ou nome vazio | as variáveis sumiram (terminal novo). Rode de novo o bloco de variáveis do passo 0 |
| Deploy enviando arquivos enormes | há arquivos extras em `app/` (ex.: uma `.venv`). Só o código deve ficar nessa pasta |
