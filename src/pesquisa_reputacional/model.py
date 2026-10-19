"""Modelos de dados usados pela pesquisa e pelos adaptadores de saída."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class NewsRecord(BaseModel):
    """Registro normalizado de notícia usado em todo o fluxo da pesquisa."""

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    source: str | None = Field(default=None, alias="fonte")
    brand: str | None = Field(default=None, alias="marca")
    product: str | None = Field(default=None, alias="produto")
    suffix: str | None = Field(default=None, alias="sufixo")
    query: str | None = Field(default=None, alias="consulta")
    title: str | None = Field(default=None, alias="título")
    summary: str | None = Field(default=None, alias="resumo")
    origin: str | None = Field(default=None, alias="origem")
    publication_date: str | None = Field(default=None, alias="data_publicação")
    publication_text: str | None = Field(default=None, alias="data_texto")
    link: str | None = None
    collected_at: str | None = Field(default=None, alias="data_coleta")
    http_status: int | None = Field(default=None, alias="status_http")
    status: str | None = None
    error: str | None = Field(default=None, alias="erro")
