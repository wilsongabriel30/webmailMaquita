#!/usr/bin/env python3
"""
Maquita Webmail — Seed Demo / Synthetic Data
=============================================

Populates the database with **clearly fake** data so that new contributors
can explore every feature without touching real mailboxes.

Usage:
    DATABASE_URL=postgresql://mailserver:pass@localhost:5432/maildb python scripts/seed_demo_data.py

All inserts are idempotent (ON CONFLICT DO NOTHING) so re-running is safe.
"""

import os
import sys
import uuid
import hashlib
from datetime import datetime, timedelta, timezone

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    sys.exit("psycopg2 is required.  Install with:  pip install psycopg2-binary")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    sys.exit("Set DATABASE_URL environment variable first.")

# ---------------------------------------------------------------------------
# Synthetic helpers
# ---------------------------------------------------------------------------
FAKE_DOMAINS = ["example.com", "test.org", "demo.net", "sample.io"]

FAKE_USERS = [
    ("demo@example.com",    "Demo User",     "user"),
    ("auditor@example.com", "Audit Officer",  "auditor"),
    ("manager@example.com", "Mail Manager",   "admin"),
]

FAKE_SENDERS = [
    "alice@example.com", "bob@test.org", "carol@demo.net",
    "dave@sample.io", "eve@example.com", "frank@test.org",
    "grace@demo.net", "heidi@sample.io", "ivan@example.com",
    "judy@test.org",
]

FAKE_SUBJECTS = [
    "Quarterly report draft",
    "Meeting notes — project sync",
    "Invoice #12345 attached",
    "Vacation request — next week",
    "Security bulletin — patch available",
    "Welcome to the team!",
    "Re: Budget proposal",
    "Fwd: Vendor agreement",
    "Action required: password expiry",
    "Lunch plans tomorrow?",
]

NOW = datetime.now(timezone.utc)


def fake_message_id(index: int) -> str:
    """Generate a deterministic, clearly-fake Message-ID."""
    h = hashlib.sha256(f"demo-seed-{index}".encode()).hexdigest()[:16]
    return f"<{h}.demo@synthetic.example>"


# ---------------------------------------------------------------------------
# Main seed logic
# ---------------------------------------------------------------------------
def seed(conn):
    cur = conn.cursor()
    counters: dict[str, int] = {}

    # ---- 1. Demo users -------------------------------------------------------
    for email, display_name, role in FAKE_USERS:
        cur.execute(
            """
            INSERT INTO users (email, display_name, role, is_active, created_at)
            VALUES (%s, %s, %s, TRUE, %s)
            ON CONFLICT (email) DO NOTHING
            """,
            (email, display_name, role, NOW),
        )
    counters["users"] = len(FAKE_USERS)

    # ---- 2. mail_trace records (50 synthetic messages) -----------------------
    traces = []
    for i in range(50):
        sender = FAKE_SENDERS[i % len(FAKE_SENDERS)]
        recipient = FAKE_USERS[i % len(FAKE_USERS)][0]
        subject = FAKE_SUBJECTS[i % len(FAKE_SUBJECTS)]
        msg_id = fake_message_id(i)
        sent_at = NOW - timedelta(hours=i * 6, minutes=i % 60)
        size_bytes = 1024 + (i * 137)  # arbitrary sizes
        traces.append((msg_id, sender, recipient, subject, size_bytes, sent_at, "delivered"))

    execute_values(
        cur,
        """
        INSERT INTO mail_trace (message_id, sender, recipient, subject, size_bytes, sent_at, status)
        VALUES %s
        ON CONFLICT (message_id) DO NOTHING
        """,
        traces,
    )
    counters["mail_trace"] = len(traces)

    # ---- 3. user_activity_log ------------------------------------------------
    activities = []
    actions = ["login", "read_email", "send_email", "delete_email", "change_password", "export_mailbox"]
    for i in range(30):
        user_email = FAKE_USERS[i % len(FAKE_USERS)][0]
        action = actions[i % len(actions)]
        ts = NOW - timedelta(hours=i * 2)
        ip = f"198.51.100.{10 + (i % 50)}"
        activities.append((user_email, action, ip, ts))

    execute_values(
        cur,
        """
        INSERT INTO user_activity_log (user_email, action, ip_address, created_at)
        VALUES %s
        ON CONFLICT DO NOTHING
        """,
        activities,
    )
    counters["user_activity_log"] = len(activities)

    # ---- 4. Compliance case --------------------------------------------------
    case_id = uuid.UUID("00000000-0000-4000-a000-000000000001")
    cur.execute(
        """
        INSERT INTO compliance_cases (id, title, description, status, created_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (
            str(case_id),
            "DEMO — Suspicious forwarding rule",
            "Synthetic case: user auto-forwards all mail to external address. "
            "Created by seed script for demonstration purposes.",
            "open",
            "auditor@example.com",
            NOW - timedelta(days=3),
        ),
    )
    counters["compliance_cases"] = 1

    # ---- 5. Legal hold -------------------------------------------------------
    hold_id = uuid.UUID("00000000-0000-4000-a000-000000000002")
    cur.execute(
        """
        INSERT INTO legal_holds (id, case_id, custodian_email, hold_type, status, created_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (
            str(hold_id),
            str(case_id),
            "demo@example.com",
            "full_mailbox",
            "active",
            "auditor@example.com",
            NOW - timedelta(days=2),
        ),
    )
    counters["legal_holds"] = 1

    # ---- 6. Fraud alerts -----------------------------------------------------
    fraud_alerts = [
        (
            uuid.UUID("00000000-0000-4000-a000-000000000010"),
            "Impossible travel detected",
            "demo@example.com logged in from two countries within 30 minutes.",
            "high",
            "open",
        ),
        (
            uuid.UUID("00000000-0000-4000-a000-000000000011"),
            "Bulk external forwarding",
            "eve@example.com created a rule forwarding all mail to external address.",
            "critical",
            "investigating",
        ),
        (
            uuid.UUID("00000000-0000-4000-a000-000000000012"),
            "Unusual attachment volume",
            "bob@test.org sent 50 attachments (200 MB) in 10 minutes.",
            "medium",
            "resolved",
        ),
    ]
    for alert_id, title, description, severity, status in fraud_alerts:
        cur.execute(
            """
            INSERT INTO fraud_alerts (id, title, description, severity, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (str(alert_id), title, description, severity, status, NOW - timedelta(days=1)),
        )
    counters["fraud_alerts"] = len(fraud_alerts)

    # ---- 7. eDiscovery search results ----------------------------------------
    search_id = uuid.UUID("00000000-0000-4000-a000-000000000020")
    cur.execute(
        """
        INSERT INTO ediscovery_searches
            (id, case_id, query, custodians, date_from, date_to, result_count, status, created_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (
            str(search_id),
            str(case_id),
            "invoice OR payment OR transfer",
            ["demo@example.com", "alice@example.com"],
            (NOW - timedelta(days=90)).date(),
            NOW.date(),
            12,
            "completed",
            "auditor@example.com",
            NOW - timedelta(hours=6),
        ),
    )
    counters["ediscovery_searches"] = 1

    conn.commit()
    return counters


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    print("Maquita Webmail — Seeding demo data ...")
    print(f"  Database: {DATABASE_URL.split('@')[-1]}")  # hide credentials
    conn = psycopg2.connect(DATABASE_URL)
    try:
        counters = seed(conn)
        print("\nDone! Summary:")
        for table, count in counters.items():
            print(f"  {table:.<30s} {count:>4} rows (ON CONFLICT DO NOTHING)")
        print("\nDemo credentials:")
        for email, name, role in FAKE_USERS:
            print(f"  {email:<25s}  role={role:<8s}  ({name})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
