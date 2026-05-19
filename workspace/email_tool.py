#!/usr/bin/env python3
"""
email_tool.py — Email management tool for John's Gmail inbox.

Reads John's mailbox, identifies promotional junk (LinkedIn, Reddit,
newsletter senders, marketing blasts), and clears it from Primary.

Categories:
  - junk: LinkedIn, Reddit, noreply newsletters, marketing blasts,
          "% off" deals, social notifications — auto-archived
  - business: from known business contacts, invoices, receipts,
              project-related — kept in inbox
  - personal: from friends/family, direct emails — kept in inbox
  - from_self: emails Charles sent (charlescreatorai@gmail.com) — kept

Usage:
  python3 workspace/email_tool.py              # dry-run report
  python3 workspace/email_tool.py --archive    # archive junk messages

Or import as module:
  from workspace.email_tool import scan_inbox, classify, archive_junk
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

# Add charles root to path so we can import tools
sys.path.insert(0, "/Users/home/charles")

from tools.gmail import list_emails, read_email, archive_email

log = logging.getLogger("charles.email_tool")

WORKSPACE = Path("/Users/home/charles/workspace")
CATEGORIZED_PATH = WORKSPACE / "gmail_categorized.json"
META_PATH = WORKSPACE / "gmail_messages_meta.json"

# ---- Trusted service providers — exempt from generic noreply rule ----
_TRUSTED_SERVICE_SENDERS = [
    r"email\.apple\.com$", r"insideapple\.apple\.com$", r"id\.apple\.com$",
    r"accounts\.google\.com$", r"no-reply@google\.com$",
    r"notifications@stripe\.com$", r"notifications@carrd\.com$",
    r"noreply@openrouter\.ai$",
    r"e\.fiverr\.com$",
    r"no-reply@twilio\.com$",
    r"noreply@namecheap\.com$",
    r"support@namecheap\.com$",
    r"support@letterstream",
    r"em\.linkedin\.com$",
    r"businessprofile",
    r"microsoft.*email", r"microsoft.*account",
    r"appstore@insideapple", r"applemusic@insideapple",
    r"noreply@redditmail\.com$",
]

# ---- Junk sender patterns (email addresses / domains) ----
_JUNK_SENDER_PATTERNS = [
    # Social networks
    r"linkedin\.com", r"reddit\.com", r"redditmail\.com",
    r"facebookmail\.com", r"fb\.com", r"instagram\.com",
    r"twitter\.com", r"x\.com", r"tiktok\.com",
    r"pinterest\.com", r"tumblr\.com", r"discord\.com",
    r"twitch\.com", r"snapchat\.com",
    # Newsletter / marketing senders
    r"noreply@", r"no-reply@", r"do-not-reply@",
    r"newsletter@", r"news@", r"marketing@", r"promo@",
    r"deals?@", r"offers?@", r"updates?@", r"announce@",
    r"notification@", r"hello@", r"team@", r"info@",
    r"tips@", r"tips@", r"digest@", r"weekly@", r"daily@",
    # Generic marketing subdomains
    r"mail\.", r"email\.", r"notifications\.",
    r"messages-noreply@", r"updates-noreply@", r"notifications-noreply@",
    r"jobs-listings@", r"jobs@",
]

# ---- Junk subject patterns ----
_JUNK_SUBJECT_PATTERNS = [
    r"\d+%\s*off", r"\bsale\b", r"\bdeals?\b", r"limited time",
    r"last chance", r"don'?t miss", r"flash sale", r"final hours",
    r"unsubscribe", r"\bnewsletter\b", r"weekly digest", r"daily digest",
    r"new arrivals?", r"now available", r"introducing",
    r"exclusive offer", r"save \$", r"earn \$", r"free shipping",
    r"shop now", r"get yours", r"your puzzle", r"on a roll",
    r"recommended actions", r"see who reached out", r"posted on",
    r"you're on a roll", r"add .* operations", r"share their thoughts",
    r"your puzzle is closing", r"new messages", r"jobs.*hiring",
    r"is hiring", r"recommended", r"posts you might",
]

# ---- Business / personal sender domains (NOT junk) ----
_BUSINESS_SENDER_PATTERNS = [
    r"tennesseeriversteel\.com$", r"contrpro\.com$",
    r"keith\.john87@gmail\.com$", r"john\.m\.keffer@gmail\.com$",
    r"charlescreatorai@gmail\.com$",
    r"stripe\.com$", r"paypal\.com$", r"apple\.com$",
    r"google\.com$", r"amazon\.com$", r"vercel\.com$",
    r"github\.com$", r"gitlab\.com$", r"cloudflare\.com$",
    r"hostedsolutions$", r"icloud\.com$", r"yahoo\.com$",
    r"protonmail\.com$", r"outlook\.com$", r"hotmail\.com$",
    r"fastmail\.com$",
]

# ---- Business / personal subject patterns ----
_BUSINESS_SUBJECT_PATTERNS = [
    r"\breceipt\b", r"\binvoice\b", r"payment confirm",
    r"order confirm", r"shipped", r"delivered", r"tracking",
    r"security alert", r"password reset", r"verification code",
    r"account statement", r"statement available",
    r"project", r"estimate", r"bid", r"quote", r"proposal",
    r"contract", r"permit", r"inspection", r"license",
    r"invoice", r"payment", r"billing", r"account",
    r"forward", r"fwd:", r"re:", r"reply",
    r"question", r"help", r"support", r"update",
    r"report", r"data", r"download", r"ready",
    r"confirmation", r"verified", r"approved",
    r"meeting", r"call", r"schedule", r"appointment",
    r"appointment", r"reminder", r"invitation",
    r"welcome", r"signup", r"registration", r"account",
    r"password", r"reset", r"change", r"update",
    r"notification", r"alert", r"warning", r"notice",
    r"memo", r"memo", r"memo", r"memo",
]


@dataclass
class EmailEntry:
    message_id: str
    thread_id: str
    date: str
    from_addr: str
    subject: str
    category: str  # junk | business | personal | from_self
    snippet: str = ""
    size_estimate: int = 0
    labels: list = None

    def __post_init__(self):
        if self.labels is None:
            self.labels = []


def _extract_email(addr_field: str) -> str:
    """Pull just the email out of 'Name <email@host>' style headers."""
    m = re.search(r"<([^>]+)>", addr_field)
    return m.group(1).lower() if m else addr_field.strip().lower()


def _classify(sender: str, subject: str) -> str:
    """Classify a single email as junk | business | personal | from_self."""
    sender_email = _extract_email(sender)
    sender_lower = sender_email.lower()
    subject_lower = subject.lower()

    # From self — keep
    if "charlescreatorai@gmail.com" in sender_lower:
        return "from_self"

    # Junk sender patterns — check BEFORE business senders
    # so noreply@redditmail.com and messages-noreply@linkedin.com
    # get caught as junk before generic noreply@ matches business
    # BUT exempt trusted service providers from generic noreply rule
    if any(re.search(p, sender_lower) for p in _TRUSTED_SERVICE_SENDERS):
        return "business"
    if any(re.search(p, sender_lower) for p in _JUNK_SENDER_PATTERNS):
        return "junk"

    # Junk subject patterns — mark junk
    if any(re.search(p, subject_lower) for p in _JUNK_SUBJECT_PATTERNS):
        return "junk"

    # Business / personal sender domains — keep
    if any(re.search(p, sender_lower) for p in _BUSINESS_SENDER_PATTERNS):
        return "business"

    # Business / personal subject — keep
    if any(re.search(p, subject_lower) for p in _BUSINESS_SUBJECT_PATTERNS):
        return "business"

    # Default: personal/business — keep
    return "personal"


def scan_inbox(max_results: int = 500) -> list[EmailEntry]:
    """Scan the live inbox and return classified EmailEntry objects."""
    listing = list_emails(query="in:inbox", max_results=max_results)
    if listing.startswith("[error]"):
        raise RuntimeError(f"Gmail API error: {listing}")
    if "(no messages" in listing:
        return []

    entries = []
    for line in listing.splitlines():
        parts = [p.strip() for p in line.split("|", 3)]
        if len(parts) != 4:
            continue
        msg_id, date, sender, subject = parts
        category = _classify(sender, subject)
        entries.append(EmailEntry(
            message_id=msg_id,
            thread_id=msg_id,  # fallback; full scan gets real threadId
            date=date,
            from_addr=sender,
            subject=subject,
            category=category,
            snippet=subject[:120],
        ))

    return entries


def classify(entries: list[EmailEntry]) -> dict[str, list[EmailEntry]]:
    """Group entries by category."""
    result: dict[str, list[EmailEntry]] = {
        "junk": [], "business": [], "personal": [], "from_self": [],
    }
    for e in entries:
        result[e.category].append(e)
    return result


def archive_junk(entries: list[EmailEntry]) -> dict:
    """Archive all junk-category messages. Returns summary."""
    junk = [e for e in entries if e.category == "junk"]
    archived = 0
    failures = []

    for e in junk:
        result = archive_email(e.message_id)
        if result.startswith("archived"):
            archived += 1
        else:
            failures.append(f"{e.message_id} ({e.from_addr}): {e.subject[:60]}")

    return {
        "total_junk": len(junk),
        "archived": archived,
        "failures": failures,
        "failure_count": len(failures),
    }


def save_report(entries: list[EmailEntry], output_path: Optional[Path] = None) -> Path:
    """Save a categorized report as JSON."""
    if output_path is None:
        output_path = CATEGORIZED_PATH

    categorized = classify(entries)
    report = {
        "categories": {k: len(v) for k, v in categorized.items()},
        "message_counts": {k: len(v) for k, v in categorized.items()},
        "messages": {k: [asdict(e) for e in v] for k, v in categorized.items()},
    }

    output_path.write_text(json.dumps(report, indent=2, default=str))
    log.info("saved report to %s", output_path)
    return output_path


def print_report(entries: list[EmailEntry]):
    """Pretty-print a report of the inbox state."""
    categorized = classify(entries)
    total = len(entries)

    print(f"\n{'='*70}")
    print(f"  EMAIL TOOL — Inbox Report")
    print(f"  Total messages in Primary: {total}")
    print(f"{'='*70}\n")

    print(f"  JUNK (promotional/social):  {len(categorized['junk']):>4}  ← will be archived")
    print(f"  Business / personal:        {len(categorized['business']):>4}  ← kept")
    print(f"  Personal:                   {len(categorized['personal']):>4}  ← kept")
    print(f"  From self (charlescreatorai):{len(categorized['from_self']):>4}  ← kept")
    print()

    if categorized["junk"]:
        print("  JUNK MESSAGES:")
        print(f"  {'ID':<22} {'Date':<22} {'From':<35} {'Subject':<50}")
        print(f"  {'-'*129}")
        for e in categorized["junk"][:50]:  # show first 50
            print(f"  {e.message_id:<22} {e.date:<22} {e.from_addr[:35]:<35} {e.subject[:50]}")
        if len(categorized["junk"]) > 50:
            print(f"  ... and {len(categorized['junk']) - 50} more junk messages")
        print()

    print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(description="Email management tool")
    parser.add_argument("--archive", action="store_true",
                        help="Actually archive junk messages (default: dry-run report)")
    parser.add_argument("--max-results", type=int, default=500,
                        help="Max messages to scan (default 500)")
    parser.add_argument("--save", action="store_true",
                        help="Save report to workspace/gmail_categorized.json")
    parser.add_argument("--output", type=str, default=None,
                        help="Output path for JSON report")
    args = parser.parse_args()

    print(f"\nScanning inbox (up to {args.max_results} messages)...")
    entries = scan_inbox(max_results=args.max_results)
    print(f"Found {len(entries)} messages in Primary.\n")

    print_report(entries)

    junk_count = len([e for e in entries if e.category == "junk"])
    print(f"  → {junk_count} junk messages identified for archival.\n")

    if args.archive:
        print("Archiving junk messages...")
        result = archive_junk(entries)
        print(f"  Archived: {result['archived']}/{result['total_junk']}")
        if result["failures"]:
            print(f"  Failures ({result['failure_count']}):")
            for f in result["failures"][:10]:
                print(f"    - {f}")
        print()

    if args.save:
        path = save_report(entries, Path(args.output) if args.output else None)
        print(f"  Report saved to {path}")

    print()


if __name__ == "__main__":
    main()
