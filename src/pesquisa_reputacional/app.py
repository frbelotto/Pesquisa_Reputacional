"""Fluxo da aplicação para pesquisa reputacional no Bing."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
from tqdm.auto import tqdm

from .config import CONFIG, Config
from .email import send_report
from .engines.bing import BingNewsClient
from .model import NewsRecord
from .reports import save_product_results

LOGGER = logging.getLogger(__name__)

MARCA_COLUMN = "MARCA"
PRODUTO_COLUMN = "PRODUTO"
RESPONSIBLE_COLUMN = "RESPONSAVEL"
EMAIL_COLUMN = "EMAIL"
REPUTATION_TERMS = (
    "acusada",
    "corrupção",
    "denuncia",
    "investigada",
    "condenada",
    "assédio",
    "fraude",
    "Recuperação Judicial",
)


def _normalize_brand(brand: str) -> str:
    """Normaliza o nome da marca removendo separadores e espaços extras."""
    return " ".join(brand.replace(",", " ").replace(";", " ").split())


def read_brand_products(path: Path) -> dict[str, list[str]]:
    """Lê as marcas e seus produtos separados por vírgula na planilha de entrada."""
    if not path.is_file():
        raise FileNotFoundError(f"Input workbook not found: {path}")
    frame = pl.read_excel(path)
    missing = [
        column for column in (MARCA_COLUMN, PRODUTO_COLUMN) if column not in frame.columns
    ]
    if missing:
        raise ValueError(f"The workbook must contain columns: {', '.join(missing)}")

    result: dict[str, list[str]] = {}
    for brand_value, products_value in frame.select(
        [MARCA_COLUMN, PRODUTO_COLUMN]
    ).iter_rows():
        if brand_value is None or products_value is None:
            continue
        brand = " ".join(str(brand_value).split()).upper()
        products = [
            " ".join(product.split()).upper()
            for product in str(products_value).replace(";", ",").split(",")
            if product.strip()
        ]
        if not brand or not products:
            continue
        result.setdefault(brand, [])
        result[brand].extend(product for product in products if product not in result[brand])
    return result


def read_responsibles(path: Path) -> dict[str, tuple[str, str]]:
    """Lê a planilha que relaciona produtos e responsáveis."""
    if not path.is_file():
        raise FileNotFoundError(f"Responsible workbook not found: {path}")
    frame = pl.read_excel(path)
    missing = [
        column for column in (PRODUTO_COLUMN, RESPONSIBLE_COLUMN, EMAIL_COLUMN)
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(
            f"The responsible workbook must contain columns: {', '.join(missing)}"
        )

    result: dict[str, tuple[str, str]] = {}
    for product, name, email in frame.select(
        [PRODUTO_COLUMN, RESPONSIBLE_COLUMN, EMAIL_COLUMN]
    ).iter_rows():
        if product is None or name is None or email is None:
            continue
        normalized_product = " ".join(str(product).split()).upper()
        result[normalized_product] = (" ".join(str(name).split()), str(email).strip())
    return result


def make_queries(brands: list[str]) -> list[tuple[str, str, str]]:
    """Cria uma consulta para cada marca e termo fixo de reputação."""
    return [
        (brand, term, f'"{_normalize_brand(brand)}" "{term}"')
        for brand in brands
        for term in REPUTATION_TERMS
    ]


def collect(
    queries: list[tuple[str, str, str]], client: BingNewsClient
) -> list[NewsRecord]:
    """Executa as consultas em sequência e adiciona os metadados da coleta."""
    records: list[NewsRecord] = []
    with tqdm(total=len(queries), desc="Consultas", unit="consulta") as progress:
        for brand, term, query in queries:
            collected_at = datetime.now(timezone.utc).isoformat()
            records.extend(
                article.model_copy(update={
                    "source": "bing",
                    "brand": brand,
                    "suffix": term,
                    "query": query,
                    "collected_at": collected_at,
                })
                for article in client.search(query)
            )
            progress.update(1)
    return sorted(
        records,
        key=lambda row: (
            str(row.brand).casefold(),
            str(row.suffix).casefold(),
            str(row.title or ""),
        ),
    )


def _setup_logging() -> None:
    """Configura o registro de eventos com data, nível e mensagem."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )


def _create_client(config: Config) -> BingNewsClient:
    """Cria o único cliente suportado para o Bing News."""
    return BingNewsClient(
        limit=config.result_limit,
        days=config.days,
        delay=config.delay_seconds,
        timeout=config.timeout_seconds,
        retries=config.retries,
        proxy=config.proxy,
    )


def main(config: Config = CONFIG) -> None:
    """Executa o fluxo completo de pesquisa no Bing e envio de e-mail."""
    _setup_logging()
    brand_products = read_brand_products(config.input_path)
    responsibles = read_responsibles(config.responsible_path)
    active_products = {
        product for products in brand_products.values() for product in products
    }
    missing_products = sorted(active_products - responsibles.keys())
    if missing_products:
        raise ValueError(
            "No responsible configured for product(s): " + ", ".join(missing_products)
        )

    records = collect(make_queries(sorted(brand_products)), _create_client(config))
    records_with_products = [
        record.model_copy(update={"product": product})
        for record in records
        for product in brand_products.get(record.brand or "", [])
    ]
    for product in sorted(active_products):
        product_records = [
            record for record in records_with_products if record.product == product
        ]
        product_report = save_product_results(product_records, config.output_dir, product)
        if config.email_enabled:
            responsible_name, responsible_email = responsibles[product]
            send_report(product_report, product, responsible_name, responsible_email, config)

    LOGGER.info(
        "Finished: %d queries, %d records",
        len(make_queries(sorted(brand_products))),
        len(records),
    )
