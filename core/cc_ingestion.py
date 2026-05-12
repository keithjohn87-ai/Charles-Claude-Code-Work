"""Common Crawl ingestion — Charles foundation knowledge build.

Per build directive 2026-05-11 (PDF: "Charles — Common Crawl Foundation
Knowledge Build"). Replaces the live-web URL sprint with archived/frozen
Common Crawl as the upstream source. The existing classification → fact
extraction → tree routing pipeline (core/memory.add_fact) stays unchanged.

Module surface:
    query_cdx(domains, path_patterns, limit) -> list[CDXRecord]
    fetch_wet(record) -> str          # raw extracted text
    fetch_warc_fallback(record) -> str  # if WET missing main content
    deduplicate(records) -> list      # MinHash-based, prefer most recent
    quality_filter(text, keywords)    -> tuple[bool, str]  # (pass, reason)
    extract_main(html) -> str         # trafilatura main-content
    detect_lang(text) -> str
    ingest_batch(config, batch_size=100) -> dict  # progress counters

Each config (see CC_CONFIGS in core/cc_configs.py) describes one branch's
domain target, keyword validation, routing tag, and target record count.

Sequencing per directive section 9: serial only, branch by branch, config
by config. The runner (cc_runner.py — separate) calls ingest_batch() in a
loop and surfaces progress through system_status. tree_validator.py runs
between each branch/config completion.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Iterable

log = logging.getLogger("charles.cc_ingestion")

# ─────────────────────────────────────────────────────────────────────────────
# Module-lazy imports — these libs are heavy (fasttext loads a 130MB model,
# trafilatura pulls lxml, cdx_toolkit hits S3 on first use). Defer to
# call-time so `import core.cc_ingestion` stays cheap and side-effect-free.
# ─────────────────────────────────────────────────────────────────────────────


def _cdx_client():
    import cdx_toolkit
    return cdx_toolkit.CDXFetcher(source="cc")


def _trafilatura():
    import trafilatura
    return trafilatura


def _ftlangdetect():
    from ftlangdetect import detect as _detect
    return _detect


def _minhash():
    from datasketch import MinHash, MinHashLSH
    return MinHash, MinHashLSH


# ─────────────────────────────────────────────────────────────────────────────
# Records
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CDXRecord:
    """One CDX-index hit. Has enough info to fetch the WET/WARC body."""
    url: str
    timestamp: str        # YYYYMMDDhhmmss
    filename: str         # WARC filename within s3://commoncrawl/
    offset: int
    length: int
    mime: str = ""
    status: str = ""

    @property
    def cc_year_month(self) -> str:
        return f"{self.timestamp[:4]}-{self.timestamp[4:6]}"


@dataclass
class IngestStats:
    """Per-batch counters surfaced via system_status."""
    pages_queried: int = 0
    pages_fetched: int = 0
    pages_passed_filter: int = 0
    pages_ingested: int = 0
    facts_extracted: int = 0
    facts_superseded: int = 0
    failures: int = 0
    skipped_dedup: int = 0
    notes: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# CDX query
# ─────────────────────────────────────────────────────────────────────────────


def query_cdx(
    url_pattern: str,
    *,
    from_ts: str = "20200101",
    to_ts: str | None = None,
    limit: int = 1000,
) -> list[CDXRecord]:
    """Query the Common Crawl CDX index for URLs matching `url_pattern`.

    `url_pattern` accepts CDX wildcards: 'github.com/QwenLM/*' or
    '*.qwenlm.github.io/*'. The CC index is updated monthly; we filter by
    timestamp range to bias toward recent crawls.

    Returns a flat list — caller is responsible for batching + dedup.
    """
    cli = _cdx_client()
    records: list[CDXRecord] = []
    iter_kwargs = {"from_ts": from_ts, "limit": limit}
    if to_ts:
        iter_kwargs["to"] = to_ts
    try:
        for hit in cli.iter(url_pattern, **iter_kwargs):
            try:
                records.append(CDXRecord(
                    url=hit["url"],
                    timestamp=hit["timestamp"],
                    filename=hit["filename"],
                    offset=int(hit["offset"]),
                    length=int(hit["length"]),
                    mime=hit.get("mime", ""),
                    status=hit.get("status", ""),
                ))
            except (KeyError, ValueError) as e:
                log.warning("malformed CDX hit, skipping: %s", e)
    except Exception as e:  # noqa: BLE001
        log.error("CDX query failed for %r: %s", url_pattern, e)
    log.info("query_cdx %r → %d records", url_pattern, len(records))
    return records


# ─────────────────────────────────────────────────────────────────────────────
# Body fetch — WET preferred, WARC fallback
# ─────────────────────────────────────────────────────────────────────────────


def fetch_wet(record: CDXRecord) -> str | None:
    """Fetch the pre-extracted text from the WET (extracted-text) sidecar.

    WET filename is derived from the WARC filename by replacing path
    segment 'warc' with 'wet' and extension '.warc.gz' with '.warc.wet.gz'.
    Returns None on any failure (caller falls back to WARC).
    """
    import requests
    if not record.filename or "/warc/" not in record.filename:
        return None
    wet_filename = record.filename.replace("/warc/", "/wet/").replace(
        ".warc.gz", ".warc.wet.gz"
    )
    # CC HTTPS gateway. Anonymous, no auth required.
    url = f"https://data.commoncrawl.org/{wet_filename}"
    headers = {"Range": f"bytes={record.offset}-{record.offset + record.length - 1}"}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        log.warning("WET fetch failed for %s: %s", record.url, e)
        return None
    try:
        from warcio.archiveiterator import ArchiveIterator
        gz = io.BytesIO(r.content)
        for warc_record in ArchiveIterator(gz):
            if warc_record.rec_type == "conversion":
                body = warc_record.content_stream().read()
                return body.decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        log.warning("WET parse failed for %s: %s", record.url, e)
    return None


def fetch_warc_main(record: CDXRecord) -> str | None:
    """Fallback: fetch the raw WARC + extract main content via trafilatura.

    Used when WET fetch returns None or when the WET text is unusable
    (mostly boilerplate, see quality_filter).
    """
    import requests
    url = f"https://data.commoncrawl.org/{record.filename}"
    headers = {"Range": f"bytes={record.offset}-{record.offset + record.length - 1}"}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        log.warning("WARC fetch failed for %s: %s", record.url, e)
        return None
    try:
        from warcio.archiveiterator import ArchiveIterator
        gz = io.BytesIO(r.content)
        for warc_record in ArchiveIterator(gz):
            if warc_record.rec_type == "response":
                payload = warc_record.content_stream().read()
                # Strip HTTP headers (everything before first \r\n\r\n)
                if b"\r\n\r\n" in payload:
                    html = payload.split(b"\r\n\r\n", 1)[1].decode(
                        "utf-8", errors="replace"
                    )
                else:
                    html = payload.decode("utf-8", errors="replace")
                return _trafilatura().extract(html) or None
    except Exception as e:  # noqa: BLE001
        log.warning("WARC parse failed for %s: %s", record.url, e)
    return None


def fetch_text(record: CDXRecord) -> str | None:
    """Top-level fetch: WARC + trafilatura main-content extraction.

    Earlier versions tried fetch_wet first, but the CDX index only has WARC
    offsets — WET files have their own (different) offsets which aren't
    indexed. Range-requesting WET with WARC offsets returns HTTP 416
    "Requested Range Not Satisfiable" on every page. Bug fixed 2026-05-11.

    WARC + trafilatura is slightly slower per page but always correct —
    the byte range matches what the CDX index advertised.
    """
    return fetch_warc_main(record)


# ─────────────────────────────────────────────────────────────────────────────
# Quality filters
# ─────────────────────────────────────────────────────────────────────────────


_BOILERPLATE_MARKERS = (
    "cookie policy", "privacy policy", "terms of service", "404",
    "page not found", "subscribe to our newsletter", "click here to",
    "all rights reserved",
)


def _is_mostly_boilerplate(text: str) -> bool:
    """Heuristic: if 40% of lines look like nav/footer cruft, reject."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 5:
        return False
    boilerplate = sum(
        1 for ln in lines
        if any(m in ln.lower() for m in _BOILERPLATE_MARKERS) or len(ln) < 20
    )
    return boilerplate / len(lines) > 0.4


def detect_language(text: str) -> str:
    """Return ISO 639-1 lang code (e.g. 'en') or '' if uncertain."""
    sample = text[:2000].replace("\n", " ").strip()
    if not sample:
        return ""
    try:
        result = _ftlangdetect()(sample, low_memory=True)
        return result.get("lang", "") or ""
    except Exception as e:  # noqa: BLE001
        log.warning("lang detect failed: %s", e)
        return ""


def quality_filter(
    text: str,
    *,
    required_keywords: list[str] | None = None,
    min_keyword_hits: int = 2,
    min_chars: int = 500,
    require_english: bool = True,
) -> tuple[bool, str]:
    """Apply the directive's pre-ingestion quality gates. Returns
    (passed, reason). Reason is empty when passed."""
    if len(text) < min_chars:
        return False, f"too_short_{len(text)}"
    if require_english and detect_language(text) != "en":
        return False, "not_english"
    if _is_mostly_boilerplate(text):
        return False, "mostly_boilerplate"
    if required_keywords:
        text_lc = text.lower()
        hits = sum(1 for kw in required_keywords if kw.lower() in text_lc)
        if hits < min_keyword_hits:
            return False, f"keyword_hits_{hits}_below_{min_keyword_hits}"
    return True, ""


# ─────────────────────────────────────────────────────────────────────────────
# Deduplication via MinHash LSH
# ─────────────────────────────────────────────────────────────────────────────


def _minhash_for(text: str, num_perm: int = 128):
    MinHash, _ = _minhash()
    h = MinHash(num_perm=num_perm)
    # Shingle on word 5-grams
    words = text.lower().split()
    if len(words) < 5:
        return h
    for i in range(len(words) - 4):
        shingle = " ".join(words[i:i + 5]).encode()
        h.update(shingle)
    return h


def deduplicate(
    records: Iterable[tuple[CDXRecord, str]],
    *,
    threshold: float = 0.85,
    num_perm: int = 128,
) -> list[tuple[CDXRecord, str]]:
    """Drop near-duplicates via MinHash LSH. Same URL appearing in 12+ CC
    crawls is normal — we keep the most recent (highest timestamp).

    Input: iterable of (record, text). Output: deduped list, recent-first.
    """
    _, MinHashLSH = _minhash()
    items = sorted(records, key=lambda r: r[0].timestamp, reverse=True)
    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    kept: list[tuple[CDXRecord, str]] = []
    for i, (rec, text) in enumerate(items):
        if not text:
            continue
        h = _minhash_for(text, num_perm=num_perm)
        if lsh.query(h):
            continue  # near-dup of something we already kept
        lsh.insert(f"k{i}", h)
        kept.append((rec, text))
    return kept


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion entry — one batch
# ─────────────────────────────────────────────────────────────────────────────


def ingest_batch(
    config: dict,
    *,
    batch_size: int = 100,
    cdx_state: dict | None = None,
) -> IngestStats:
    """Ingest one batch of records for a given config.

    `config` shape (per directive Phase 1/Phase 2):
        {
            "name": "qwen36_base_model",
            "domains": ["qwenlm.github.io", "github.com/QwenLM", ...],
            "path_patterns": [...],            # used to refine URL filter
            "required_keywords": [...],
            "min_keyword_hits": 2,
            "routing_tag": "business_corpus/charles/base_model",
            "target_records": 12000,
            "topic": "charles_self",            # canonical leaf for add_fact
        }

    `cdx_state` carries cross-batch dedup memory + cursor:
        {"seen_urls": set[str], "lsh": MinHashLSH | None,
         "domain_cursor": int, "offset": int}

    Returns IngestStats with per-batch counts. Caller persists state across
    batches; this function is stateless beyond what's in cdx_state.
    """
    from core import memory as _memory
    stats = IngestStats()
    cdx_state = cdx_state or {"seen_urls": set(), "domain_cursor": 0}
    seen_urls: set[str] = cdx_state.setdefault("seen_urls", set())

    # Round-robin one domain per batch to spread coverage.
    domains: list[str] = config["domains"]
    if not domains:
        stats.notes.append("no_domains_configured")
        return stats
    cursor = cdx_state.get("domain_cursor", 0) % len(domains)
    domain = domains[cursor]
    cdx_state["domain_cursor"] = cursor + 1

    pattern = f"{domain}/*"
    records = query_cdx(pattern, limit=batch_size * 3)  # over-fetch for filtering
    stats.pages_queried = len(records)

    # Pull bodies + filter
    candidates: list[tuple[CDXRecord, str]] = []
    for rec in records:
        if rec.url in seen_urls:
            continue
        text = fetch_text(rec)
        if not text:
            stats.failures += 1
            continue
        stats.pages_fetched += 1
        ok, reason = quality_filter(
            text,
            required_keywords=config.get("required_keywords"),
            min_keyword_hits=config.get("min_keyword_hits", 2),
        )
        if not ok:
            log.debug("filtered %s: %s", rec.url, reason)
            continue
        stats.pages_passed_filter += 1
        candidates.append((rec, text))
        if len(candidates) >= batch_size:
            break

    # Dedup within batch + against config-cumulative state
    deduped = deduplicate(candidates)
    stats.skipped_dedup = len(candidates) - len(deduped)

    # Ingest into memory.long_term_facts via the existing pipeline
    routing_tag = config.get("routing_tag", "")
    topic = config.get("topic")
    config_name = config.get("name", "cc")
    for rec, text in deduped:
        seen_urls.add(rec.url)
        # First pass: store as a single fact per record. Future enhancement
        # could break long records into multiple facts via LLM extraction.
        # For now, the existing classifier path will handle that downstream
        # if/when this fact is read by Charles.
        snippet = text[:2000]  # bound the fact text — full body in source field
        try:
            _memory.add_fact(
                fact=snippet,
                tags=f"cc,{config_name},{routing_tag}",
                topic=topic,
                source=f"commoncrawl:{rec.url}",
                confidence=0.85,
            )
            stats.pages_ingested += 1
            stats.facts_extracted += 1
        except Exception as e:  # noqa: BLE001
            log.error("add_fact failed for %s: %s", rec.url, e)
            stats.failures += 1

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Smoke-test helpers (callable from runner / scripts)
# ─────────────────────────────────────────────────────────────────────────────


def smoke_test_cdx(pattern: str = "qwenlm.github.io/*", limit: int = 5) -> list[dict]:
    """Quick CDX query, no S3 fetch, no DB write. Use to verify connectivity."""
    records = query_cdx(pattern, limit=limit)
    return [
        {"url": r.url, "ts": r.timestamp, "year_month": r.cc_year_month}
        for r in records
    ]


def smoke_test_full(pattern: str = "qwenlm.github.io/*", limit: int = 3) -> dict:
    """End-to-end smoke: CDX → WET → quality filter → dedup. No DB write."""
    records = query_cdx(pattern, limit=limit)
    fetched = []
    for rec in records:
        text = fetch_text(rec)
        if text:
            fetched.append((rec, text))
    deduped = deduplicate(fetched)
    return {
        "queried": len(records),
        "fetched": len(fetched),
        "deduped": len(deduped),
        "sample_chars": sum(len(t) for _, t in deduped),
    }
