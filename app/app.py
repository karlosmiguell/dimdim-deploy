"""DimDim - API de exemplo para a aula de deploy no Azure App Service + Azure SQL.

Usuarios com transacoes (entrada/saida de dinheiro) e produtos em falta no estoque.

A conexao com o Azure SQL vem das App Settings do Web App (variaveis de ambiente):
  SQL_SERVER, SQL_DATABASE, SQL_USER e SQL_PASSWORD
Enquanto elas nao existirem o app sobe, mas avisa "banco nao configurado".
"""
import logging
import os
import platform
import socket
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify, render_template, request
from sqlalchemy import text
from sqlalchemy.engine import URL

from models import ProdutoEmFalta, Transacao, Usuario, db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("dimdim")

VARIAVEIS_BANCO = ("SQL_SERVER", "SQL_USER", "SQL_PASSWORD")
BANCO_CONFIGURADO = all(os.environ.get(v) for v in VARIAVEIS_BANCO)
SERVIDOR_SQL = os.environ.get("SQL_SERVER", "")

app = Flask(__name__)

if BANCO_CONFIGURADO:
    app.config["SQLALCHEMY_DATABASE_URI"] = URL.create(
        "mssql+pyodbc",
        username=os.environ["SQL_USER"],
        password=os.environ["SQL_PASSWORD"],  # URL.create trata caracteres especiais
        host=SERVIDOR_SQL,
        port=1433,
        database=os.environ.get("SQL_DATABASE", "dimdim"),
        query={
            "driver": os.environ.get("SQL_DRIVER", "ODBC Driver 18 for SQL Server"),
            "Encrypt": "yes",
            "TrustServerCertificate": "no",
        },
    )
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,  # testa a conexao antes de usar: o Azure SQL derruba conexoes ociosas
        "pool_recycle": 280,
        "connect_args": {"timeout": 30},  # segundos para conectar (o banco serverless pode estar "acordando")
    }
    db.init_app(app)

    # Cria as tabelas na inicializacao. Se o banco estiver fora do ar, o app sobe
    # mesmo assim e o problema aparece em /health e no log (az webapp log tail).
    with app.app_context():
        try:
            db.create_all()
            log.info("Azure SQL pronto: %s", SERVIDOR_SQL)
        except Exception:
            log.exception("Nao foi possivel conectar/criar tabelas no Azure SQL (%s)", SERVIDOR_SQL)
else:
    log.warning("Banco nao configurado: defina %s nas App Settings do Web App.", ", ".join(VARIAVEIS_BANCO))


def erro(mensagem, status=400):
    return jsonify({"erro": mensagem}), status


@app.before_request
def exigir_banco():
    if not BANCO_CONFIGURADO and request.path.startswith("/api/"):
        return erro("Banco nao configurado: defina SQL_SERVER, SQL_USER e SQL_PASSWORD nas App Settings.", 503)


def ler_valor(dados):
    try:
        valor = Decimal(str(dados.get("valor")))
    except (InvalidOperation, TypeError):
        return None
    return valor if valor > 0 else None


# ---------------------------------------------------------------- paginas

@app.route("/")
def index():
    return render_template(
        "index.html",
        banco_configurado=BANCO_CONFIGURADO,
        servidor_sql=SERVIDOR_SQL,
        site=os.environ.get("WEBSITE_SITE_NAME", "-"),
        host=socket.gethostname(),
        python_versao=platform.python_version(),
    )


@app.route("/health")
def health():
    """Usado para verificar o deploy e a conexao com o banco."""
    banco_ok = False
    if BANCO_CONFIGURADO:
        try:
            db.session.execute(text("SELECT 1"))
            banco_ok = True
        except Exception as e:
            log.warning("Health check falhou: %s", e)
    return jsonify(
        {
            "status": "ok" if banco_ok else "erro",
            "banco_configurado": BANCO_CONFIGURADO,
            "banco_conectado": banco_ok,
            "servidor_sql": SERVIDOR_SQL or None,
            "site": os.environ.get("WEBSITE_SITE_NAME"),
            "host": socket.gethostname(),
            "python": platform.python_version(),
        }
    ), 200 if banco_ok else 503


# ------------------------------------------------- usuarios e transacoes

@app.get("/api/usuarios")
def listar_usuarios():
    usuarios = db.session.scalars(db.select(Usuario).order_by(Usuario.id)).all()
    return jsonify([u.to_dict() for u in usuarios])


@app.post("/api/usuarios")
def criar_usuario():
    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    if not nome:
        return erro("Informe o campo 'nome'.")
    usuario = Usuario(nome=nome, saldo=Decimal("0"))
    db.session.add(usuario)
    db.session.commit()
    return jsonify(usuario.to_dict()), 201


@app.get("/api/usuarios/<int:usuario_id>")
def obter_usuario(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    return jsonify(usuario.to_dict(com_transacoes=True))


@app.post("/api/usuarios/<int:usuario_id>/transacoes")
def criar_transacao(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    dados = request.get_json(silent=True) or {}
    tipo = dados.get("tipo")
    if tipo not in ("entrada", "saida"):
        return erro("O campo 'tipo' deve ser 'entrada' ou 'saida'.")
    valor = ler_valor(dados)
    if valor is None:
        return erro("O campo 'valor' deve ser um numero maior que zero.")
    if tipo == "saida" and valor > usuario.saldo:
        return erro("Saldo insuficiente.", 422)

    usuario.saldo += valor if tipo == "entrada" else -valor
    transacao = Transacao(usuario=usuario, tipo=tipo, valor=valor)
    db.session.add(transacao)
    db.session.commit()
    return jsonify(transacao.to_dict()), 201


# ------------------------------------------------------ produtos em falta

def ler_produto(dados):
    codigo = (dados.get("codigo") or "").strip()
    descricao = (dados.get("descricao") or "").strip()
    if not codigo or not descricao:
        return None, "Informe 'codigo' e 'descricao'."
    try:
        data_solicitacao = date.fromisoformat(dados.get("data_solicitacao") or date.today().isoformat())
    except ValueError:
        return None, "'data_solicitacao' deve estar no formato AAAA-MM-DD."
    return {"codigo": codigo, "descricao": descricao, "data_solicitacao": data_solicitacao}, None


@app.get("/api/out_stock")
def listar_produtos():
    produtos = db.session.scalars(db.select(ProdutoEmFalta).order_by(ProdutoEmFalta.id)).all()
    return jsonify([p.to_dict() for p in produtos])


@app.post("/api/out_stock")
def criar_produto():
    campos, msg = ler_produto(request.get_json(silent=True) or {})
    if msg:
        return erro(msg)
    produto = ProdutoEmFalta(**campos)
    db.session.add(produto)
    db.session.commit()
    return jsonify(produto.to_dict()), 201


@app.put("/api/out_stock/<int:produto_id>")
def atualizar_produto(produto_id):
    produto = db.get_or_404(ProdutoEmFalta, produto_id)
    campos, msg = ler_produto(request.get_json(silent=True) or {})
    if msg:
        return erro(msg)
    for nome, valor in campos.items():
        setattr(produto, nome, valor)
    db.session.commit()
    return jsonify(produto.to_dict())


@app.delete("/api/out_stock/<int:produto_id>")
def remover_produto(produto_id):
    produto = db.get_or_404(ProdutoEmFalta, produto_id)
    db.session.delete(produto)
    db.session.commit()
    return jsonify({"mensagem": "Registro removido."})


@app.errorhandler(404)
def nao_encontrado(e):
    return erro("Recurso nao encontrado.", 404)
