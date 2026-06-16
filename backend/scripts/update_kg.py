"""
KG Update Pipeline
==================
Fetches recent tech papers from ArXiv + PubMed, extracts new technology nodes
and relationships via LLM, then upserts them into Neo4j.

Fixes vs previous version
--------------------------
1. Zero APOC dependency  — tag/synonym merging done in Python, not Cypher.
2. Cartesian product     — relationship MATCH uses MATCH…WITH…MATCH pattern.
3. Batch ordering        — all nodes are upserted before any relationship in
                           the same extraction batch, so intra-batch rels
                           always find both endpoints.
4. is_new flag           — Python-side branching (no Cypher timestamp trick).

Environment variables required (.env):
    GROQ_API_KEY        — Groq API key
    GROQ_MODEL          — (optional) override model name (default llama-3.3-70b-versatile)
    NEO4J_URI           — bolt://host.docker.internal:7687
    NEO4J_USER          — neo4j
    NEO4J_PASSWORD      — azerty12
"""

import os
import sys
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Reuse the shared LLM client from services/llm.py instead of duplicating it.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.llm import ask_llm, begin_interaction, finish_interaction  # noqa: E402

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://host.docker.internal:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "azerty12")

ARXIV_MAX_RESULTS  = int(os.getenv("ARXIV_MAX_RESULTS",  "30"))
PUBMED_MAX_RESULTS = int(os.getenv("PUBMED_MAX_RESULTS", "20"))

ARXIV_QUERY = (
    "cat:cs.LG OR cat:cs.SE OR cat:cs.DC OR cat:cs.AI OR cat:cs.IR "
    "AND ti:framework OR ti:library OR ti:platform OR ti:system OR ti:tool"
)

PUBMED_QUERY = (
    "bioinformatics software tool[Title] OR "
    "machine learning framework[Title] OR "
    "deep learning library[Title]"
)

# ──────────────────────────────────────────────────────────────────────────────
# Valid KG schema values
# ──────────────────────────────────────────────────────────────────────────────

VALID_CATEGORIES = {
    "Frontend", "FullStack", "Backend", "Mobile", "DevOps", "IaC", "CICD",
    "Observability", "Cloud", "Database", "Cache", "Search", "VectorDB",
    "DataWarehouse", "MessageBroker", "DataEngineering", "MLOps", "ML",
    "LLM", "Security", "API",
}

VALID_TYPES = {
    "Language", "Framework", "Library", "Platform", "Protocol",
    "Standard", "Runtime", "Tool", "Service", "Database",
}

VALID_REL_TYPES = {
    "TRANSFERABLE_TO", "EQUIVALENT_IN", "EXTENDS", "REQUIRES",
    "OFTEN_USED_WITH", "PART_OF", "BRIDGES", "EVOLVED_INTO", "IMPLEMENTS",
}

# LLM client is imported from services.llm (Groq-backed, shared with the
# rest of the backend so all calls share Groq's per-key rate limits).


# ──────────────────────────────────────────────────────────────────────────────
# Paper fetchers
# ──────────────────────────────────────────────────────────────────────────────

def _cutoff_date(days: int = 15) -> datetime:
    return datetime.utcnow() - timedelta(days=days)


def fetch_arxiv(max_results: int = ARXIV_MAX_RESULTS, days: int = 15) -> list[dict]:
    cutoff      = _cutoff_date(days)
    date_from   = cutoff.strftime("%Y%m%d0000")
    date_to     = datetime.utcnow().strftime("%Y%m%d2359")
    date_filter = f"submittedDate:[{date_from} TO {date_to}]"
    query       = f"({ARXIV_QUERY}) AND {date_filter}"

    params = {
        "search_query": query,
        "start":        0,
        "max_results":  max_results,
        "sortBy":       "submittedDate",
        "sortOrder":    "descending",
    }
    log.info(f"[ArXiv] Fetching papers from last {days} days (since {cutoff.date()}) …")
    resp = requests.get("https://export.arxiv.org/api/query", params=params, timeout=30)
    resp.raise_for_status()

    ns   = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)

    papers = []
    for entry in root.findall("atom:entry", ns):
        title     = (entry.find("atom:title",    ns).text or "").strip()
        summary   = (entry.find("atom:summary",  ns).text or "").strip()
        published = (entry.find("atom:published",ns).text or "").strip()
        papers.append({"source": "arxiv", "title": title,
                       "abstract": summary, "published": published})

    log.info(f"[ArXiv] Got {len(papers)} papers")
    return papers


def fetch_pubmed(max_results: int = PUBMED_MAX_RESULTS, days: int = 15) -> list[dict]:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    term = f"({PUBMED_QUERY}) AND {days}[PDAT]"

    log.info(f"[PubMed] Fetching papers from last {days} days …")
    search_resp = requests.get(
        f"{base}/esearch.fcgi",
        params={"db": "pubmed", "term": term, "retmax": max_results,
                "sort": "date", "retmode": "json", "datetype": "pdat",
                "reldate": days},
        timeout=30,
    )
    search_resp.raise_for_status()
    ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        log.info(f"[PubMed] No results in the last {days} days")
        return []

    fetch_resp = requests.get(
        f"{base}/efetch.fcgi",
        params={"db": "pubmed", "id": ",".join(ids),
                "rettype": "abstract", "retmode": "xml"},
        timeout=30,
    )
    fetch_resp.raise_for_status()

    papers = []
    root   = ET.fromstring(fetch_resp.text)
    for article in root.findall(".//PubmedArticle"):
        title_el    = article.find(".//ArticleTitle")
        abstract_el = article.find(".//AbstractText")
        title    = (title_el.text    or "") if title_el    is not None else ""
        abstract = (abstract_el.text or "") if abstract_el is not None else ""
        if title:
            papers.append({"source": "pubmed", "title": title, "abstract": abstract})

    log.info(f"[PubMed] Got {len(papers)} papers")
    return papers


# ──────────────────────────────────────────────────────────────────────────────
# LLM extractor
# ──────────────────────────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """You are a technical knowledge graph curator.
Given the title and abstract of a research paper, extract any software technologies,
frameworks, libraries, platforms, or tools that are either INTRODUCED or prominently USED.

Return a JSON object with exactly two keys:

  "nodes": list of technology nodes to add/update in the graph
  "relationships": list of directional relationships between technologies

Each node must follow this schema:
{{
  "name":     "Canonical display name (e.g. 'PyTorch')",
  "synonyms": ["alias1", "alias2"],
  "category": "One of: {categories}",
  "domain":   "Fine-grained sub-domain (e.g. 'NLP', 'Inference', 'VectorDB')",
  "type":     "One of: {types}",
  "language": "Implementation language (e.g. 'Python', 'Go', 'Agnostic')",
  "tags":     "Comma-separated lowercase keywords"
}}

Each relationship must follow this schema:
{{
  "from":   "source technology canonical name",
  "to":     "target technology canonical name",
  "type":   "One of: {rel_types}",
  "reason": "One sentence explanation",
  "weight": 0.0-1.0  (only for TRANSFERABLE_TO and EQUIVALENT_IN, else omit)
}}

Rules:
- Only include technologies that are clearly software tools, NOT concepts or algorithms.
- Always use the CANONICAL name (official title-cased name) in "name" and in "from"/"to".
- "synonyms" must include at minimum the lowercase form of "name".
- If the paper introduces a new tool, add it as a node.
- Link it to existing well-known technologies using relationship types.
- If nothing new is found, return {{"nodes": [], "relationships": []}}.
- Return ONLY valid JSON, no prose, no markdown fences.

Paper title: {title}
Paper abstract: {abstract}
"""


def extract_from_paper(paper: dict) -> dict:
    prompt = EXTRACTION_PROMPT.format(
        title=paper["title"],
        abstract=paper["abstract"][:1500],
        categories=", ".join(sorted(VALID_CATEGORIES)),
        types=", ".join(sorted(VALID_TYPES)),
        rel_types=", ".join(sorted(VALID_REL_TYPES)),
    )
    try:
        raw    = ask_llm(prompt, json_mode=True, _span_name="kg_extractor")
        result = json.loads(raw)
        return result
    except Exception as e:
        log.warning(f"[Extractor] Failed for '{paper['title']}': {e}")
        return {"nodes": [], "relationships": []}


def validate_extraction(data: dict) -> dict:
    """Validate and normalise extracted nodes and relationships."""
    clean_nodes = []
    for n in data.get("nodes", []):
        name = (n.get("name") or "").strip()
        if not name:
            continue

        n["category"] = n.get("category") if n.get("category") in VALID_CATEGORIES else "ML"
        n["type"]     = n.get("type")     if n.get("type")     in VALID_TYPES       else "Library"
        n.setdefault("domain",   "General")
        n.setdefault("language", "Agnostic")
        n.setdefault("tags",     "")

        # Normalise synonyms — always a list, always includes lowercase name
        raw_syn = n.get("synonyms") or []
        if isinstance(raw_syn, str):
            raw_syn = [s.strip() for s in raw_syn.split(",") if s.strip()]
        synonyms = list({s.strip() for s in raw_syn if isinstance(s, str) and s.strip()})
        if name.lower() not in {s.lower() for s in synonyms}:
            synonyms.append(name.lower())
        n["synonyms"] = synonyms
        n["name"]     = name

        clean_nodes.append(n)

    clean_rels = []
    for r in data.get("relationships", []):
        if r.get("type") not in VALID_REL_TYPES:
            continue
        if not r.get("from") or not r.get("to"):
            continue
        r.setdefault("reason", "")
        if r["type"] in ("TRANSFERABLE_TO", "EQUIVALENT_IN"):
            r["weight"] = float(r.get("weight", 0.75))
        clean_rels.append(r)

    return {"nodes": clean_nodes, "relationships": clean_rels}


# ──────────────────────────────────────────────────────────────────────────────
# Neo4j writer  (zero APOC, no cartesian product warning)
# ──────────────────────────────────────────────────────────────────────────────

class KGUpdater:
    """
    Deduplication strategy
    ─────────────────────
    Nodes
        Each Technology stores a ``synonyms`` list and a ``synonyms_str``
        (pipe-separated lowercase) property.  Before creating a node we search
        for any existing node whose name or synonyms_str overlaps the incoming
        aliases (case-insensitive).  Merging of tags/synonyms is done in
        Python and written back with a simple SET — zero APOC required.

    Relationships
        Both endpoint names are resolved to canonical graph names via the
        synonym index before the MERGE.  The MATCH uses MATCH…WITH…MATCH
        (not a comma-separated pattern) to eliminate the cartesian-product
        warning.

    Batch ordering
        All nodes in an extraction batch are upserted BEFORE any relationship
        so intra-batch relationships always find their endpoints.
    """

    def __init__(self):
        self.driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        log.info(f"[Neo4j] Connected to {NEO4J_URI}")

    def close(self):
        self.driver.close()

    # ── Schema setup ──────────────────────────────────────────────────────────

    def ensure_constraints(self):
        with self.driver.session() as session:
            try:
                session.run(
                    "CREATE CONSTRAINT tech_name_unique IF NOT EXISTS "
                    "FOR (t:Technology) REQUIRE t.name IS UNIQUE"
                )
            except Exception as e:
                log.warning(f"[Neo4j] name constraint: {e}")
            log.info("[Neo4j] Constraints ensured")

    # ── Synonym resolution ────────────────────────────────────────────────────

    def _resolve_canonical(self, session, name: str) -> str | None:
        """
        Return the canonical graph name for any alias, or None if not found.

        Step 1 — exact case-insensitive match on the indexed ``name`` property.
        Step 2 — substring search in ``synonyms_str`` (pipe-separated lowercase).
        """
        # Step 1: uses the unique index on name — fast
        rec = session.run(
            "MATCH (t:Technology) WHERE toLower(t.name) = toLower($name) "
            "RETURN t.name AS c LIMIT 1",
            name=name,
        ).single()
        if rec:
            return rec["c"]

        # Step 2: synonyms_str is stored lowercase so we just lowercase $name
        rec = session.run(
            "MATCH (t:Technology) "
            "WHERE t.synonyms_str IS NOT NULL "
            "  AND t.synonyms_str CONTAINS $name_lc "
            "RETURN t.name AS c LIMIT 1",
            name_lc=name.lower(),
        ).single()
        return rec["c"] if rec else None

    # ── Node upsert ───────────────────────────────────────────────────────────

    def upsert_node(self, node: dict) -> bool:
        """
        Idempotent node upsert with synonym-aware deduplication.

        - Checks ALL incoming aliases against the graph before touching it.
        - If a match is found → fetch, merge tags + synonyms in Python, SET.
        - If no match → CREATE a new node.
        - Returns True only when a brand-new node is created.
        """
        all_aliases = list({node["name"]} | {s for s in node.get("synonyms", [])})

        with self.driver.session() as session:
            canonical = None
            for alias in all_aliases:
                canonical = self._resolve_canonical(session, alias)
                if canonical:
                    break

            if canonical:
                # ── Merge into existing node (pure Python, no APOC) ───────
                rec = session.run(
                    "MATCH (t:Technology {name: $name}) "
                    "RETURN t.tags AS tags, t.synonyms_str AS syn_str",
                    name=canonical,
                ).single()

                existing_tags = {
                    t.strip()
                    for t in (rec["tags"] or "").split(",")
                    if t.strip()
                }
                new_tags = {
                    t.strip()
                    for t in node.get("tags", "").split(",")
                    if t.strip()
                }
                merged_tags = ",".join(sorted(existing_tags | new_tags))

                existing_syn = {
                    s for s in (rec["syn_str"] or "").split("|") if s
                }
                new_syn = {a.lower() for a in all_aliases}
                merged_syn = "|".join(sorted(existing_syn | new_syn))

                session.run(
                    "MATCH (t:Technology {name: $name}) "
                    "SET t.tags = $tags, t.synonyms_str = $syn_str",
                    name=canonical,
                    tags=merged_tags,
                    syn_str=merged_syn,
                )
                return False  # existing node — not new

            else:
                # ── Create brand-new node ─────────────────────────────────
                synonyms_str = "|".join(sorted({a.lower() for a in all_aliases}))
                session.run(
                    """
                    CREATE (t:Technology {
                        name:         $name,
                        category:     $category,
                        domain:       $domain,
                        type:         $type,
                        language:     $language,
                        tags:         $tags,
                        synonyms:     $synonyms,
                        synonyms_str: $synonyms_str,
                        source:       'auto',
                        created:      timestamp()
                    })
                    """,
                    name=node["name"],
                    category=node["category"],
                    domain=node["domain"],
                    type=node["type"],
                    language=node["language"],
                    tags=node.get("tags", ""),
                    synonyms=all_aliases,
                    synonyms_str=synonyms_str,
                )
                return True  # new node created

    # ── Relationship upsert ───────────────────────────────────────────────────

    def upsert_relationship(self, rel: dict) -> bool:
        """
        Idempotent relationship upsert.

        - Resolves both endpoints to their canonical graph names first.
        - Uses MATCH…WITH…MATCH (not comma-separated) to eliminate the
          cartesian-product performance warning from Neo4j.
        - Returns True if the relationship was written (new or updated).
        """
        with self.driver.session() as session:
            from_c = self._resolve_canonical(session, rel["from"])
            to_c   = self._resolve_canonical(session, rel["to"])

            if not from_c:
                log.debug(f"[Neo4j] Rel skip — unknown source: '{rel['from']}'")
                return False
            if not to_c:
                log.debug(f"[Neo4j] Rel skip — unknown target: '{rel['to']}'")
                return False

            has_weight = rel["type"] in ("TRANSFERABLE_TO", "EQUIVALENT_IN")
            set_clause = "r.reason = $reason, r.source = 'auto'"
            if has_weight:
                set_clause += ", r.weight = $weight"

            # MATCH…WITH…MATCH avoids the cartesian product warning
            cypher = f"""
            MATCH (a:Technology {{name: $from_c}})
            WITH a
            MATCH (b:Technology {{name: $to_c}})
            MERGE (a)-[r:{rel['type']}]->(b)
            ON CREATE SET {set_clause}, r.created = timestamp()
            ON MATCH  SET {set_clause}
            RETURN r IS NOT NULL AS ok
            """
            params: dict = {
                "from_c": from_c,
                "to_c":   to_c,
                "reason": rel.get("reason", ""),
            }
            if has_weight:
                params["weight"] = rel.get("weight", 0.75)

            try:
                rec = session.run(cypher, **params).single()
                return bool(rec and rec["ok"])
            except Exception as e:
                log.warning(
                    f"[Neo4j] Rel failed "
                    f"({from_c} -[{rel['type']}]-> {to_c}): {e}"
                )
                return False

    # ── Bulk upsert: nodes first, then relationships ──────────────────────────

    def bulk_upsert(self, extracted: dict) -> tuple[int, int, int, int]:
        """
        Upsert all nodes FIRST, then all relationships.

        Processing nodes before relationships guarantees that intra-batch
        relationships (where both endpoints come from the same paper) always
        find their endpoints in the graph.

        Returns (nodes_new, nodes_existing, rels_ok, rels_failed).
        """
        nodes_new = nodes_existing = rels_ok = rels_failed = 0

        # Pass 1 — nodes
        for node in extracted.get("nodes", []):
            if self.upsert_node(node):
                nodes_new += 1
            else:
                nodes_existing += 1

        # Pass 2 — relationships (both endpoints now in graph)
        for rel in extracted.get("relationships", []):
            if self.upsert_relationship(rel):
                rels_ok += 1
            else:
                rels_failed += 1

        return nodes_new, nodes_existing, rels_ok, rels_failed


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline orchestrator
# ──────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    arxiv_results:  int   = ARXIV_MAX_RESULTS,
    pubmed_results: int   = PUBMED_MAX_RESULTS,
    delay_between:  float = 1.0,
    days:           int   = 15,
):
    log.info("═" * 60)
    log.info("KG UPDATE PIPELINE — START")
    log.info("═" * 60)

    papers: list[dict] = []
    try:
        papers += fetch_arxiv(arxiv_results, days=days)
    except Exception as e:
        log.error(f"[ArXiv] Fetch failed: {e}")

    try:
        papers += fetch_pubmed(pubmed_results, days=days)
    except Exception as e:
        log.error(f"[PubMed] Fetch failed: {e}")

    if not papers:
        log.warning("No papers fetched. Exiting.")
        return

    log.info(f"Total papers to process: {len(papers)}")

    # ── Open Raindrop interaction ─────────────────────────────────────────────
    begin_interaction(
        event      = "kg_update_pipeline",
        input_text = f"{len(papers)} papers (ArXiv + PubMed, last {days} days)",
        n_papers   = len(papers),
        days       = days,
    )

    updater = KGUpdater()
    updater.ensure_constraints()

    totals = {"nodes_new": 0, "nodes_existing": 0, "rels_ok": 0, "rels_failed": 0}

    for i, paper in enumerate(papers, 1):
        log.info(
            f"[{i}/{len(papers)}] {paper['source'].upper()} "
            f"— {paper['title'][:80]}"
        )

        extracted = extract_from_paper(paper)   # ask_llm() tracked inside
        validated = validate_extraction(extracted)

        n_nodes = len(validated["nodes"])
        n_rels  = len(validated["relationships"])
        log.info(f"  → Extracted {n_nodes} nodes, {n_rels} relationships")

        if n_nodes or n_rels:
            nn, ne, ro, rf = updater.bulk_upsert(validated)
            totals["nodes_new"]      += nn
            totals["nodes_existing"] += ne
            totals["rels_ok"]        += ro
            totals["rels_failed"]    += rf
            log.info(
                f"  → Neo4j: +{nn} new nodes | {ne} existing "
                f"| {ro} rels ok | {rf} failed"
            )

        if i < len(papers):
            time.sleep(delay_between)

    updater.close()

    log.info("═" * 60)
    log.info("PIPELINE COMPLETE")
    log.info(f"  New nodes created   : {totals['nodes_new']}")
    log.info(f"  Existing nodes hit  : {totals['nodes_existing']}")
    log.info(f"  Relationships OK    : {totals['rels_ok']}")
    log.info(f"  Relationships failed: {totals['rels_failed']}")
    log.info("═" * 60)

    # ── Close Raindrop interaction ────────────────────────────────────────────
    finish_interaction(
        output        = f"{totals['nodes_new']} new nodes, {totals['rels_ok']} rels written",
        nodes_new     = totals["nodes_new"],
        nodes_existing= totals["nodes_existing"],
        rels_ok       = totals["rels_ok"],
        rels_failed   = totals["rels_failed"],
        n_papers      = len(papers),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="KG Update Pipeline")
    parser.add_argument("--arxiv",  type=int,   default=ARXIV_MAX_RESULTS)
    parser.add_argument("--pubmed", type=int,   default=PUBMED_MAX_RESULTS)
    parser.add_argument("--delay",  type=float, default=1.0)
    parser.add_argument("--days",   type=int,   default=15)
    args = parser.parse_args()

    run_pipeline(
        arxiv_results=args.arxiv,
        pubmed_results=args.pubmed,
        delay_between=args.delay,
        days=args.days,
    )