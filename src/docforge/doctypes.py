"""Single source of truth for the documentation set: each doc's purpose and required H2 sections.

`init` renders skeletons from this table and `check` verifies the same sections exist, so the two can never
drift apart. The section lists follow the docs-as-code brief the project was specified from.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

UNCERTAIN = "uncertain — verify with developer"
# Accept hyphen/en-dash/em-dash variants so a hand-typed marker still counts.
UNCERTAIN_RE = re.compile(r"uncertain\s*[-–—]\s*verify with developer", re.IGNORECASE)


@dataclass(frozen=True)
class DocType:
    path: str
    title: str
    purpose: str
    sections: tuple[str, ...]
    entry_template: str = ""  # optional structured block repeated per item (fragile area, problem, ...)


DOC_TYPES: tuple[DocType, ...] = (
    DocType(
        "README.md",
        "{name}",
        "Concise entry point. Link to docs/ rather than duplicating them.",
        ("Purpose", "Technologies", "Architecture at a Glance", "Prerequisites", "Local Development",
         "Running Tests", "Deployment", "Documentation"),
    ),
    DocType(
        "docs/ARCHITECTURE.md",
        "Architecture",
        "Which components exist and how information flows between them.",
        ("Overview", "Components", "Information Flow", "External Systems", "Infrastructure",
         "Deployment Architecture"),
    ),
    DocType(
        "docs/DESIGN.md",
        "Design",
        "Design intent: boundaries, abstractions and conventions, not a file listing.",
        ("Design Principles", "Component Boundaries", "Key Abstractions and Patterns", "Configuration Strategy",
         "Error Handling", "Logging", "Authentication and Authorisation", "State Management", "API Conventions"),
    ),
    DocType(
        "docs/HOW_IT_WORKS.md",
        "How It Works",
        "End-to-end workflows. For each: trigger, receiver, processing, services called, storage, async work, "
        "result, failure modes.",
        ("Workflows",),
        "### Workflow: <name>\n\n1. Trigger:\n2. Received by:\n3. Processing:\n4. Services called:\n"
        "5. Data stored:\n6. Asynchronous work:\n7. Result:\n8. What can fail:\n",
    ),
    DocType(
        "docs/DEPLOYMENT.md",
        "Deployment",
        "How the system is built, configured and deployed, and how to roll back.",
        ("Environments", "Build", "Deploy", "Configuration", "Rollback"),
    ),
    DocType(
        "docs/MAINTENANCE.md",
        "Maintenance",
        "Written for the engineer who inherits this system.",
        ("Starting and Stopping", "Dependency Updates", "Database Migrations", "Secret Rotation",
         "Configuration Management", "Logs", "Backups", "Releases", "Making Production Changes",
         "Known Technical Debt", "Fragile Areas"),
        "### Fragile area: <component>\n\n- Component:\n- Why it is sensitive:\n- What depends on it:\n"
        "- What must be tested before changing it:\n- Relevant files:\n- Relevant ADR:\n",
    ),
    DocType(
        "docs/TROUBLESHOOTING.md",
        "Troubleshooting",
        "Practical guide. Keep historical lessons even after the bug is fixed.",
        ("Known Problems",),
        "### Problem: <title>\n\n- Possible symptoms:\n- Likely causes:\n- Diagnostic steps:\n- Resolution:\n"
        "- Relevant logs:\n- Relevant components:\n- Escalation considerations:\n",
    ),
    DocType(
        "docs/SECURITY.md",
        "Security",
        "Security architecture, trust boundaries and who is responsible for what.",
        ("Trust Boundaries", "Authentication", "Authorisation", "Secrets Management", "Session Handling",
         "API Security", "Network Exposure", "Input Validation", "Dependency Security", "Logging and Audit",
         "Sensitive Data", "Rate Limiting", "Encryption and TLS", "Security Assumptions", "Responsibilities"),
    ),
    DocType(
        "docs/TESTING.md",
        "Testing",
        "Testing strategy and what must pass before a change is accepted.",
        ("Strategy", "Unit Tests", "Integration Tests", "End-to-End Tests", "Security Tests",
         "Manual and Smoke Tests", "Test Environments and Data", "Running Tests", "Required Before Changes"),
    ),
    DocType(
        "docs/DATA_MODEL.md",
        "Data Model",
        "Entities, relationships, constraints, ownership and business rules.",
        ("Overview", "Entities", "Relationships", "Constraints and Indexes", "Ownership and Retention",
         "Migrations", "Business Rules"),
    ),
    DocType(
        "docs/API.md",
        "API",
        "Behaviour, assumptions and side effects that a generated API spec does not capture.",
        ("Overview", "Endpoints", "Errors"),
        "### <METHOD> <path>\n\n- Purpose:\n- Authentication:\n- Parameters:\n- Request example:\n"
        "- Response example:\n- Error codes:\n- Dependencies:\n- Side effects:\n",
    ),
    DocType(
        "docs/DEPENDENCIES.md",
        "Dependencies",
        "Dependencies that would be hard to replace or could significantly affect the application.",
        ("Critical Dependencies",),
        "### <dependency>\n\n- Purpose:\n- Current version:\n- Why it is used:\n- Replacement difficulty:\n"
        "- Upgrade considerations:\n- Known limitations:\n",
    ),
    DocType(
        "docs/OPERATIONS.md",
        "Operations",
        "Running the system day to day: monitoring, alerts, routine tasks, incidents.",
        ("Monitoring", "Alerts", "Routine Operations", "Incident Response"),
    ),
)

BY_PATH: dict[str, DocType] = {d.path: d for d in DOC_TYPES}


def render(doc: DocType, project_name: str) -> str:
    """Skeleton for a new doc: every required section present, every claim marked uncertain."""
    parts = [f"# {doc.title.format(name=project_name)}\n", f"> {doc.purpose}\n"]
    for section in doc.sections:
        parts.append(f"## {section}\n")
        if doc.entry_template and section == doc.sections[-1]:
            parts.append(doc.entry_template)
        parts.append(f"> {UNCERTAIN}\n")
    return "\n".join(parts)
