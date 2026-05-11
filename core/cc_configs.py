"""Common Crawl ingestion configs.

Per CC build directive 2026-05-11:
  Phase 1 — re-run existing tree branches through CC (4 configs)
  Phase 2 — three stack-specific configs Charles has zero coverage on

Sequencing per directive section 9:
  Phase 1 order: business_corpus → human_context → training_corpus → external
  Phase 2 order: qwen36 → mlx → agent_architecture
  Each branch/config completes fully before the next starts.
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
            # Charles self / Apprentice Accelerator / ContractorPro / RV Park
            # Seeded — runner unions with URL-sprint history at startup
            "github.com", "anthropic.com", "openai.com",
        ],
        "path_patterns": ["*"],
        "required_keywords": [
            "construction", "contractor", "trade", "training", "apprentice",
            "RV", "park", "campground", "ServiceTitan", "Procore", "BuilderTrend",
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
            # Philosophy/Doctrine, Family, History, Health, Work/Trade
            "plato.stanford.edu", "iep.utm.edu", "philpapers.org",
            "en.wikipedia.org", "history.com",
            "mayoclinic.org", "nih.gov",
            "linguisticsociety.org", "studylib.net",
        ],
        "path_patterns": ["*"],
        "required_keywords": [
            "philosophy", "ethics", "doctrine", "history", "family",
            "communication", "language", "pragmatics", "rhetoric",
            "health", "medicine", "construction", "trade",
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
            # Sales/Demo material, Electrical vertical, HVAC vertical
            "salesforce.com/blog", "hubspot.com",
            "ecmweb.com", "electricalcontractor.net",
            "achrnews.com", "contractingbusiness.com",
            "ieee.org", "nfpa.org",
        ],
        "path_patterns": ["*"],
        "required_keywords": [
            "sales", "demo", "pitch", "objection",
            "electrical", "wiring", "voltage", "NEC", "code",
            "HVAC", "refrigerant", "duct", "ASHRAE",
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
            # URL Corpus, Business URLs — broad
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
