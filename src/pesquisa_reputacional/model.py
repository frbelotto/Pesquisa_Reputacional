"""Data models shared by news search engines and output adapters."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class NewsRecord(BaseModel):
    """Normalized news record used throughout the research pipeline."""

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    source: str | None = Field(default=None, alias="fonte")
    brand: str | None = Field(default=None, alias="marca")
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

