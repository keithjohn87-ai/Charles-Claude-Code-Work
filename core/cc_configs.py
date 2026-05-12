"""Common Crawl ingestion configs.

Per CC build directive 2026-05-11:
  Phase 1 — re-run existing tree branches through CC (4 configs)
  Phase 2 — three stack-specific configs Charles has zero coverage on

Sequencing per directive section 9:
  Phase 1 order: business_corpus → human_context → training_corpus → external
  Phase 2 order: qwen36 → mlx → agent_architecture
  Each branch/config completes fully before the next starts.

Phase 1 rewrite 2026-05-12: original configs had mismatched domain↔keyword
pairings (e.g. business_corpus domains were github/anthropic/openai but the
keywords were construction/contractor/trade — those keywords don't appear on
those domains, so the per-record keyword filter rejected most fetches). This
rewrite splits Phase 1 by the actual vertical:

  business_corpus  → running a trade business (construction PM, field
                     service software, AGC/NAHB doctrine, sales pipeline)
  training_corpus  → trade-vertical CONTENT (NEC, ASHRAE, HVAC technique,
                     electrical code, plumbing methods)
  human_context    → philosophy, ethics, language, communication, history
  external         → catch-all (programming forums, HN, lobste.rs)
"""
from __future__ import annotations


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — re-run existing tree branches.
#
# `domains` for each branch is the union of source URLs that fed the original
# URL sprint into that branch. Since the original URL list is in DB rows
# (long_term_facts.source) rather than a static file, the runner derives the
# per-branch domain list at startup by scanning facts whose tags include the
# branch name. The lists below are seed/anchor entries that should always be
# included regardless of what the URL-sprint history shows.
#
# `topic` maps to the canonical leaf in the topics table — add_fact uses it
# directly without semantic re-route.
# ─────────────────────────────────────────────────────────────────────────────

PHASE_1_CONFIGS = [
    {
        "name": "p1_business_corpus",
        "branch": "business_corpus",
        "domains": [
            # Construction project / field-service management software
            "procore.com", "servicetitan.com", "buildertrend.com",
            "coconstruct.com", "jobnimbus.com", "knowify.com",
            "contractorforeman.com",
            # Industry publications + forums
            "enr.com",                       # Engineering News-Record
            "constructiondive.com",
            "forconstructionpros.com",
            "constructconnect.com",
            "contractortalk.com",
            "jlconline.com",                 # Journal of Light Construction
            "thisoldhouse.com",
            "finehomebuilding.com",
            # Trade associations / doctrine
            "agc.org",                       # Associated General Contractors
            "abc.org",                       # Associated Builders and Contractors
            "nahb.org",                      # National Association of Home Builders
            # B2B sales motion (Charles's apprentice-accelerator / ContractorPro
            # ventures sit on these patterns)
            "hubspot.com", "saastr.com", "close.com", "intercom.com",
            "saleshacker.com", "gong.io", "chorus.ai",
        ],
        "path_patterns": ["*"],
        "required_keywords": [
            # Trade-business operations
            "construction", "contractor", "subcontractor", "general contractor",
            "trade", "tradesperson", "apprentice", "journeyman",
            "project management", "field service", "scheduling", "estimating",
            "bid", "RFP", "change order", "punch list", "permit", "inspection",
            "ServiceTitan", "Procore", "BuilderTrend", "CoConstruct",
            # Sales motion
            "pipeline", "objection", "demo", "cold call", "outbound",
            "discovery call", "qualification", "BANT", "MEDDIC",
            "close rate", "ACV", "ARR",
        ],
        "min_keyword_hits": 1,
        "routing_tag": "phase1/business_corpus",
        "target_records": 5000,
        "topic": None,  # let canonical router pick the leaf
    },
    {
        "name": "p1_human_context",
        "branch": "human_context",
        "domains": [
            # Philosophy / ethics / doctrine
            "plato.stanford.edu", "iep.utm.edu", "philpapers.org",
            # General reference + history
            "en.wikipedia.org", "history.com",
            # Health (where construction overlaps: ergonomics, jobsite safety)
            "mayoclinic.org", "nih.gov", "cdc.gov", "osha.gov",
            # Language + communication
            "linguisticsociety.org", "psychologytoday.com", "hbr.org",
            # Trade-skill humanity: the people who do the work
            "mikeroweworks.org",
        ],
        "path_patterns": ["*"],
        "required_keywords": [
            "philosophy", "ethics", "stoic", "doctrine",
            "history", "family", "culture",
            "communication", "language", "pragmatics", "rhetoric",
            "psychology", "leadership", "trust", "negotiation",
            "health", "safety", "ergonomics", "jobsite",
        ],
        "min_keyword_hits": 1,
        "routing_tag": "phase1/human_context",
        "target_records": 5000,
        "topic": None,
    },
    {
        "name": "p1_training_corpus",
        "branch": "training_corpus",
        "domains": [
            # Electrical — code, training, industry pubs
            "ecmweb.com",                    # Electrical Construction & Maintenance
            "electricalcontractor.net",      # NECA's pub
            "mikeholt.com",                  # NEC training (the standard)
            "necanet.org",                   # National Electrical Contractors Assoc
            "ewweb.com",                     # Electrical Wholesaling
            "ieee.org", "nfpa.org",          # academic + code authority
            # HVAC — code, technique, industry pubs
            "achrnews.com",                  # Air Conditioning Heating & Refrigeration News
            "contractingbusiness.com",       # HVAC contractor business pub
            "ashrae.org",                    # ASHRAE (the standard body)
            "esmagazine.com",                # Engineered Systems
            "hvac-talk.com",                 # practitioner forum
            "rsesjournal.com",               # Refrigeration Service Engineers Society
            # Plumbing
            "phcppros.com",                  # Plumbing, Hydronics, Heating, Cooling pub
            "plumbermag.com",
            "iapmo.org",                     # plumbing code body
            # Trade-school + apprenticeship content
            "skillsusa.org",
        ],
        "path_patterns": ["*"],
        "required_keywords": [
            # Electrical
            "electrical", "wiring", "voltage", "amperage", "circuit",
            "NEC", "National Electrical Code", "panel", "breaker", "GFCI",
            "AFCI", "grounding", "conduit",
            # HVAC
            "HVAC", "refrigerant", "duct", "ductwork", "ASHRAE",
            "compressor", "condenser", "evaporator", "BTU", "load calculation",
            "Manual J", "Manual D", "thermostat", "heat pump", "VAV",
            # Plumbing
            "plumbing", "fixture", "drain", "vent", "DWV", "supply line",
            "UPC", "IPC", "backflow",
            # Cross-cutting
            "code compliance", "inspection", "license", "journeyman",
        ],
        "min_keyword_hits": 1,
        "routing_tag": "phase1/training_corpus",
        "target_records": 5000,
        "topic": None,
    },
    {
        "name": "p1_external",
        "branch": "external",
        "domains": [
            "github.com", "stackoverflow.com",
            "news.ycombinator.com", "lobste.rs",
        ],
        "path_patterns": ["*"],
        "required_keywords": [],  # external is a catch-all; rely on dedup + quality
        "min_keyword_hits": 0,
        "routing_tag": "phase1/external",
        "target_records": 3000,
        "topic": None,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — three stack-specific configs.
#
# These are verbatim from the directive. Charles has zero foundation in his
# tree on his own architecture — these fill the gap.
# Routing tag uses the directive's path-style ("business_corpus/charles/X");
# the canonical router picks the appropriate leaf based on tags+topic.
# ─────────────────────────────────────────────────────────────────────────────

PHASE_2_CONFIGS = [
    {
        "name": "p2_qwen36",
        "branch": "qwen36_base_model",
        "domains": [
            "qwenlm.github.io",
            "github.com/QwenLM",
            "huggingface.co/Qwen",
            "huggingface.co/mlx-community",
            "huggingface.co/blog",
            "reddit.com/r/LocalLLaMA",
        ],
        "path_patterns": [
            "model card", "blog", "discussions", "quantization", "release",
        ],
        "required_keywords": [
            "Qwen", "Qwen3", "Qwen3.6", "MoE", "A3B", "Alibaba",
            "instruct", "chat template", "context length", "tokenizer",
            "35B", "4bit", "quantization",
        ],
        "min_keyword_hits": 2,
        "routing_tag": "business_corpus/charles/base_model",
        "target_records": 12000,
        "topic": "charles_self",
    },
    {
        "name": "p2_mlx",
        "branch": "mlx_runtime",
        "domains": [
            "ml-explore.github.io",
            "github.com/ml-explore",
            "developer.apple.com",
            "huggingface.co/blog",
            "reddit.com/r/LocalLLaMA",
            "reddit.com/r/MachineLearning",
        ],
        "path_patterns": [
            "docs", "issues", "discussions", "blog", "wwdc", "mlx-lm",
        ],
        "required_keywords": [
            "MLX", "Apple Silicon", "Metal", "unified memory",
            "mlx-lm", "mlx_lm", "quantization",
            "M1", "M2", "M3", "M4 Ultra", "mx.array",
        ],
        "min_keyword_hits": 2,
        "routing_tag": "business_corpus/charles/mlx_runtime",
        "target_records": 15000,
        "topic": "charles_self",
    },
    {
        "name": "p2_agent_architecture",
        "branch": "agent_architecture",
        "domains": [
            "github.com/langchain-ai",
            "github.com/microsoft/autogen",
            "github.com/joaomdmoura/crewAI",
            "github.com/Significant-Gravitas/AutoGPT",
            "python.langchain.com",
            "docs.crewai.com",
            "reddit.com/r/LocalLLaMA",
            "reddit.com/r/LangChain",
            "reddit.com/r/AI_Agents",
        ],
        "path_patterns": [
            "docs", "discussions", "agent loop", "tool use",
            "memory", "retrieval", "planner", "executor",
        ],
        "required_keywords": [
            "agent", "tool use", "function calling", "ReAct",
            "planner", "executor", "memory", "vector store",
            "embedding", "retrieval", "RAG", "orchestration", "agent loop",
        ],
        "min_keyword_hits": 2,
        "reject_keywords": [
            "what is an LLM", "hello world", "beginner", "tutorial",
        ],
        "routing_tag": "business_corpus/charles/agent_architecture",
        "target_records": 15000,
        "topic": "charles_self",
    },
]


def all_configs() -> list[dict]:
    """Phase 1 + Phase 2 in directive-mandated order."""
    return PHASE_1_CONFIGS + PHASE_2_CONFIGS


def by_name(name: str) -> dict | None:
    for c in all_configs():
        if c["name"] == name:
            return c
    return None


# Hard stop thresholds per directive section 11
HARD_STOPS = {
    "min_ram_gb": 4.0,
    "max_backlog": 1000,
    "max_uncategorized_rate_per_batch": 0.10,
    "max_consecutive_batch_failures": 3,
    "max_supersede_rate_per_branch": 0.80,
}
