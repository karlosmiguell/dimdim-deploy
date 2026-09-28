from datetime import date, datetime, timezone
from decimal import Decimal

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

db = SQLAlchemy()


def agora():
    return datetime.now(timezone.utc)


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    saldo: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    transacoes: Mapped[list["Transacao"]] = relationship(
        back_populates="usuario", order_by="Transacao.id"
    )

    def to_dict(self, com_transacoes=False):
        dados = {"id": self.id, "nome": self.nome, "saldo": float(self.saldo)}
        if com_transacoes:
            dados["transacoes"] = [t.to_dict() for t in self.transacoes]
        return dados


class Transacao(db.Model):
    __tablename__ = "transacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    tipo: Mapped[str] = mapped_column(String(10))  # 'entrada' ou 'saida'
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    data: Mapped[datetime] = mapped_column(DateTime, default=agora)
    usuario: Mapped[Usuario] = relationship(back_populates="transacoes")

    def to_dict(self):
        return {
            "id": self.id,
            "usuario_id": self.usuario_id,
            "tipo": self.tipo,
            "valor": float(self.valor),
            # o banco guarda sem fuso; marcamos como UTC para o navegador converter
            "data": self.data.replace(tzinfo=timezone.utc).isoformat(timespec="seconds"),
        }


class ProdutoEmFalta(db.Model):
    __tablename__ = "out_stock"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(255))
    descricao: Mapped[str] = mapped_column(String(255))
    data_solicitacao: Mapped[date] = mapped_column(Date)

    def to_dict(self):
        return {
            "id": self.id,
            "codigo": self.codigo,
            "descricao": self.descricao,
            "data_solicitacao": self.data_solicitacao.isoformat(),
        }
