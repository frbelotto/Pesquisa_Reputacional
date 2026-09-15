"""Simple News reputation research application."""


import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
from tqdm.auto import tqdm

from .cache import append_cache, cache_key, load_cache, remove_cache
from .config import CONFIG, Config
from .engines.base import NewsSearchEngine
from .engines.factory import create_engine
from .model import NewsRecord
from .reports import save_results

LOGGER = logging.getLogger(__name__)

MARCA_COLUMN = "MARCA"


def _normalize_brand(brand: str) -> str:
    """Normalize brand name by removing extra spaces and converting to uppercase."""
    return " ".join(brand.replace(",", " ").replace(";", " ").split())


def read_brands(path: Path) -> list[str]:
    """Read and clean the required MARCA column from an Excel workbook.
    
    Args:
        path: Path to the Excel file containing the MARCA column.
        
    Returns:
        Sorted list of unique, cleaned brand names in uppercase.
        
    Raises:
        FileNotFoundError: If the input file does not exist.
        ValueError: If the workbook lacks a MARCA column.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Input workbook not found: {path}")

    frame = pl.read_excel(path)

    if MARCA_COLUMN not in frame.columns:
        raise ValueError(f"The workbook must contain a '{MARCA_COLUMN}' column")

    # Process brands in clear steps: select, clean, filter, deduplicate, sort
    return (
        frame.select(pl.col(MARCA_COLUMN).cast(pl.String).alias("brand"))
        .with_columns(
            pl.col("brand")
            .str.replace_all(r"\s+", " ")  # Collapse multiple spaces
            .str.strip_chars()  # Remove leading/trailing whitespace
            .str.to_uppercase()  # Normalize case
        )
        .filter(pl.col("brand").is_not_null() & (pl.col("brand") != ""))  # Remove empty
        .unique(maintain_order=True)  # Deduplicate
        .sort("brand", descending=False)  # Sort alphabetically
        .get_column("brand")
        .to_list()
    )


def make_queries(brands: list[str], suffixes: list[str]) -> list[tuple[str, str, str]]:
    """Create unique brand, suffix and query tuples.
    
    Args:
        brands: List of brand names to search.
        suffixes: List of negative keywords (sufixos) to append.
        
    Returns:
        List of (original_brand, suffix, normalized_query_string) tuples.
    """
    queries: list[tuple[str, str, str]] = []
    for brand in brands:
        normalized = _normalize_brand(brand)
        for suffix in suffixes:
            query_string = f'"{normalized}" "{suffix}"'
            queries.append((brand, suffix, query_string))
    return queries


def _search_worker(
    item: tuple[str, str, str], client: NewsSearchEngine
) -> list[NewsRecord]:
    """Execute a single search query and enrich results with metadata.
    
    Args:
        item: Tuple of (brand, suffix, query_string).
        client: News search engine client.
        
    Returns:
        List of article records with source, brand, suffix, and collection metadata.
    """
    brand, suffix, query = item
    articles = client.search(query)
    collected_at = datetime.now(timezone.utc).isoformat()

    return [
        article.model_copy(update={
            "source": client.source_name,
            "brand": brand,
            "suffix": suffix,
            "query": query,
            "collected_at": collected_at,
        })
        for article in articles
    ]


def collect(
    queries: list[tuple[str, str, str]],
    client: NewsSearchEngine,
    cache_path: Path | None = None,
    cache_max_age_days: int = CONFIG.cache_max_age_days,
) -> list[NewsRecord]:
    """Collect queries concurrently and attach collection metadata.
    
    Args:
        queries: List of query tuples to execute.
        client: News search engine client with concurrency settings.
        
    Returns:
        Sorted list of article records by marca, sufixo, and título.
    """
    records: list[NewsRecord] = []
    cached = load_cache(cache_path, cache_max_age_days) if cache_path else {}
    query_keys = [(query, cache_key(query[2], client)) for query in queries]
    pending = [(query, key) for query, key in query_keys if key not in cached]

    for _, key in query_keys:
        records.extend(cached.get(key, []))

    with tqdm(
        total=len(queries),
        initial=len(queries) - len(pending),
        desc="Consultas",
        unit="consulta",
    ) as progress:
        with ThreadPoolExecutor(max_workers=client.concurrency) as executor:
            futures = {
                executor.submit(_search_worker, query, client): key
                for query, key in pending
            }
            for future in as_completed(futures):
                key = futures[future]
                query_records = future.result()
                records.extend(query_records)
                if cache_path:
                    # The workers only search; cache writes stay in this main thread.
                    append_cache(cache_path, key, query_records)
                progress.update(1)

    # Sort for consistent output
    return sorted(
        records,
        key=lambda row: (
            str(row.brand).casefold(),
            str(row.suffix).casefold(),
            str(row.title or ""),
        ),
    )


def _setup_logging() -> None:
    """Configure logging with timestamp, level, and message."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )


def _parse_arguments(default_source: str) -> str:
    """Parse command-line arguments and return the selected source.
    
    Args:
        default_source: Default news engine source from config.
        
    Returns:
        Selected news engine source.
    """
    parser = argparse.ArgumentParser(
        description="Search partner brands in Bing News or Google News."
    )
    parser.add_argument(
        "--source",
        default=default_source,
        help="Registered news engine (e.g., bing or google)",
    )
    return parser.parse_args().source


def _create_client(config: Config) -> NewsSearchEngine:
    """Create a news search engine client from configuration.
    
    Args:
        config: Application configuration.
        
    Returns:
        Initialized news search engine client.
    """
    return create_engine(
        config.source,
        limit=config.result_limit,
        days=config.days,
        concurrency=config.concurrency,
        delay=config.delay_seconds,
        timeout=config.timeout_seconds,
        retries=config.retries,
        proxy=config.proxy,
    )


def main(config: Config = CONFIG) -> None:
    """Run one complete news research workflow.
    
    Args:
        config: Application configuration (default: CONFIG).
    """
    # Parse arguments and override source if provided
    source = _parse_arguments(config.source)
    config = Config.model_validate({**config.model_dump(), "source": source})

    # Setup logging
    _setup_logging()

    # Initialize client
    client = _create_client(config)

    # Execute research pipeline
    brands = read_brands(config.input_path)
    queries = make_queries(brands, config.suffixes)
    cache_path = (
        config.cache_dir / f"{config.source}_consultas.jsonl"
        if config.cache_enabled
        else None
    )
    records = collect(queries, client, cache_path, config.cache_max_age_days)
    destination = save_results(records, config.output_dir, config.source)
    remove_cache(cache_path)

    LOGGER.info(
        "Finished: %d queries, %d records, report=%s",
        len(queries),
        len(records),
        destination,
    )
