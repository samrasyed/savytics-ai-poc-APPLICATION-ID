from __future__ import annotations

from typing import Any

MEETING_SAMPLE: dict[str, Any] = {
    "summary": (
        'The team met for "{title}" to agree the scope of the next two-week sprint. '
        "They committed to shipping the billing page redesign and fixing the export timeout, "
        "and postponed the mobile push notifications work to the following sprint."
    ),
    "key_points": [
        "The billing page redesign is the top priority and must ship this sprint.",
        "The CSV export timeout affects about 8% of enterprise accounts.",
        "Mobile push notifications are deferred until design sign-off is complete.",
        "Team capacity is reduced by one engineer due to planned leave.",
        "QA will run a full regression pass before Thursday's release.",
    ],
    "entities": {
        "people": [
            {"text": "Priya", "context": "drafting the pricing copy"},
            {"text": "Marco", "context": "fixing the CSV export"},
            {"text": "Lena", "context": "raised the push notification question"},
        ],
        "organizations": [],
        "dates": [
            {"text": "Friday", "context": "pricing copy deadline"},
            {"text": "next week", "context": "design review"},
        ],
        "locations": [],
        "technologies": [{"text": "CSV export", "context": "export feature that times out"}],
        "monetary_values": [],
        "important_terms": [
            {"text": "billing page redesign", "context": "top priority this sprint"},
            {"text": "push notifications", "context": "feature that may be delayed"},
        ],
    },
    "action_items": [
        {
            "task": "Draft the new pricing table copy",
            "owners": ["Priya"],
            "due_date": "Friday",
            "deadline_type": "confirmed",
            "status": "open",
            "priority": "high",
            "priority_source": "explicit",
            "certainty": "high",
            "evidence": "@1",
        },
        {
            "task": "Fix the CSV export timeout for large accounts",
            "owners": ["Marco"],
            "due_date": None,
            "deadline_type": None,
            "status": "open",
            "priority": "high",
            "priority_source": "explicit",
            "certainty": "high",
            "evidence": "@2",
        },
        {
            "task": "Schedule the design review for push notifications",
            "owners": [],
            "due_date": "next week",
            "deadline_type": "tentative",
            "status": "open",
            "priority": None,
            "priority_source": None,
            "certainty": "medium",
            "evidence": "@4",
        },
        {
            "task": "Update the release checklist with the new QA steps",
            "owners": ["QA team"],
            "due_date": None,
            "deadline_type": None,
            "status": "open",
            "priority": "low",
            "priority_source": "inferred",
            "certainty": "low",
            "evidence": "@3",
        },
    ],
    "decisions": [
        {
            "description": "Prioritise the billing page redesign this sprint",
            "decision_maker": None,
            "status": "confirmed",
            "evidence": "@1",
        },
        {
            "description": "Whether to delay push notifications",
            "decision_maker": None,
            "status": "pending",
            "evidence": "@3",
        },
    ],
    "open_questions": [
        {
            "question": "Who owns the design review for push notifications?",
            "category": "missing_owner",
            "related_to": "Schedule the design review for push notifications",
            "evidence": "@4",
        },
        {
            "question": "Is the budget for the external QA contractor confirmed?",
            "category": "missing_approval",
            "related_to": None,
            "evidence": "@3",
        },
        {
            "question": "Will the billing redesign need a feature flag for the gradual rollout?",
            "category": "unanswered_question",
            "related_to": None,
            "evidence": None,
        },
    ],
}

PROJECT_BRIEF_SAMPLE: dict[str, Any] = {
    "summary": (
        '"{title}" describes a customer self-service portal that lets clients view invoices, '
        "update payment details and raise support tickets. The first release targets the end "
        "of Q2 and must integrate with the existing billing system without a data migration."
    ),
    "key_points": [
        "The portal covers invoices, payment details and support tickets in the first release.",
        "Integration must use the existing billing API; no data migration is in scope.",
        "Single sign-on through the company identity provider is a hard requirement.",
        "The deliverable includes a usability test with at least five customers.",
        "Mobile apps are explicitly out of scope for this phase.",
        "Success is measured by a 30% drop in billing-related support tickets.",
    ],
    "entities": {
        "dates": [{"text": "end of Q2", "context": "first release target"}],
        "technologies": [
            {"text": "billing API", "context": "existing system to integrate with"},
            {"text": "single sign-on", "context": "required login method"},
        ],
        "important_terms": [
            {"text": "self-service portal", "context": "the product being scoped"},
            {"text": "usability test", "context": "required deliverable"},
        ],
    },
    "action_items": [
        {
            "task": "Confirm the billing API rate limits with the platform team",
            "owners": ["Engineering lead"],
            "status": "open",
            "priority": "medium",
            "priority_source": "inferred",
            "certainty": "medium",
            "evidence": "@1",
        },
        {
            "task": "Recruit five customers for the usability test",
            "owners": ["Research"],
            "due_date": "end of April",
            "deadline_type": "tentative",
            "status": "open",
            "certainty": "medium",
            "evidence": "@2",
        },
        {
            "task": "Produce wireframes for the invoice and ticket views",
            "owners": [],
            "status": "open",
            "certainty": "low",
            "evidence": "@0",
        },
    ],
    "decisions": [
        {
            "description": "Mobile apps are out of scope for the first phase",
            "status": "confirmed",
            "evidence": "@3",
        }
    ],
    "open_questions": [
        "Which identity provider configuration will the portal use in staging?",
        "Who signs off the final scope before development starts?",
    ],
}

GENERAL_SAMPLE: dict[str, Any] = {
    "summary": (
        '"{title}" reviews last quarter\'s operational performance across support, '
        "infrastructure and onboarding. Response times improved, while infrastructure costs "
        "rose faster than usage and need closer monitoring."
    ),
    "key_points": [
        "Median first-response time in support fell from 6 hours to 3.5 hours.",
        "Infrastructure costs grew 18% while active usage grew 9%.",
        "Self-serve onboarding completion rose to 72%.",
        "Two major incidents were caused by expired TLS certificates.",
    ],
    "entities": {
        "technologies": [{"text": "TLS certificates", "context": "cause of two incidents"}],
        "important_terms": [{"text": "onboarding", "context": "self-serve completion rate"}],
    },
    "action_items": [],
    "decisions": [],
    "open_questions": [
        {
            "question": "What is driving the gap between infrastructure cost growth and usage growth?",
            "category": "unanswered_question",
        },
        {"question": "Is there a plan to automate certificate renewal?"},
        {"question": "Which onboarding step loses the most users?"},
    ],
}

_MEETING_KEYWORDS = ("meeting", "transcript", "attendees", "agenda", "sync")
_BRIEF_KEYWORDS = ("brief", "scope", "requirements", "deliverable")


# Picks the meeting, project-brief or general sample based on keywords in the text.
def select_sample(text: str) -> dict[str, Any]:
    lowered = text.lower()
    if any(k in lowered for k in _MEETING_KEYWORDS):
        return MEETING_SAMPLE
    if any(k in lowered for k in _BRIEF_KEYWORDS):
        return PROJECT_BRIEF_SAMPLE
    return GENERAL_SAMPLE
