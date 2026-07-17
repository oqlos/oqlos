"""Role-scoped edit access for OQL hardware MAP (system / administrator / operator).

Hardware mapping is part of OQL configuration. Each persona may edit a different
slice of the document:

| Persona         | Domain              | MAP sections                          |
|-----------------|---------------------|---------------------------------------|
| system          | dostęp do systemu   | runtimeConfig, actions                |
| administrator   | funkcje / mapowania | objectActionMap, funcImplementations  |
| operator        | zmienne / parametry | paramSensorMap, operatorVariables     |

Write privilege is hierarchical: system ⊃ administrator ⊃ operator.
Read of the full MAP remains available for execution; the UI uses
``editable_sections`` to lock tabs.

Connect UI roles (admin, manager, …) are mapped onto these three personas.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping

# --- OQL config personas (product names) ------------------------------------

OQL_EDIT_PERSONAS = ("system", "administrator", "operator")

# Hierarchical rank (higher may write lower layers).
_PERSONA_RANK: dict[str, int] = {
    "system": 3,
    "administrator": 2,
    "operator": 1,
}

# Sections owned by each persona (primary editor).
PERSONA_OWNED_SECTIONS: dict[str, tuple[str, ...]] = {
    "system": ("runtimeConfig", "actions"),
    "administrator": ("objectActionMap", "funcImplementations"),
    "operator": ("paramSensorMap", "operatorVariables"),
}

# All MAP body sections (excluding meta).
MAP_BODY_SECTIONS: tuple[str, ...] = (
    "runtimeConfig",
    "objectActionMap",
    "paramSensorMap",
    "actions",
    "funcImplementations",
    "operatorVariables",
)

# Connect host role → OQL edit persona
_CONNECT_ROLE_TO_PERSONA: dict[str, str] = {
    "system": "system",
    "sys": "system",
    "root": "system",
    "admin": "administrator",
    "administrator": "administrator",
    "manager": "administrator",
    "technician": "administrator",
    "operator": "operator",
    "viewer": "operator",  # view-only enforced separately via can_write
    "guest": "operator",
}


class MappingAccessError(PermissionError):
    def __init__(self, message: str, *, issues: list[str] | None = None) -> None:
        self.issues = issues or [message]
        super().__init__(message)


def normalize_oql_persona(raw: str | None) -> str | None:
    value = str(raw or "").strip().lower()
    if not value:
        return None
    if value in OQL_EDIT_PERSONAS:
        return value
    if value in _CONNECT_ROLE_TO_PERSONA:
        return _CONNECT_ROLE_TO_PERSONA[value]
    return None


def persona_from_connect_role(role: str | None) -> str:
    """Map c2004 Connect role to OQL edit persona (default operator)."""
    return normalize_oql_persona(role) or "operator"


def resolve_edit_persona(
    *,
    persona: str | None = None,
    role: str | None = None,
    header_persona: str | None = None,
    header_role: str | None = None,
) -> str:
    """Pick persona from explicit persona, then role headers/params."""
    for candidate in (persona, header_persona, role, header_role):
        resolved = normalize_oql_persona(candidate)
        if resolved:
            return resolved
    return "operator"


def is_write_persona(persona: str, *, role: str | None = None) -> bool:
    """viewer/guest may not write even if persona maps to operator."""
    r = str(role or "").strip().lower()
    if r in {"viewer", "guest"}:
        return False
    return normalize_oql_persona(persona) in OQL_EDIT_PERSONAS


def sections_owned_by(persona: str) -> tuple[str, ...]:
    p = normalize_oql_persona(persona) or "operator"
    return PERSONA_OWNED_SECTIONS.get(p, PERSONA_OWNED_SECTIONS["operator"])


def sections_writable_by(persona: str) -> tuple[str, ...]:
    """Hierarchical: higher persona may edit own + lower layers."""
    p = normalize_oql_persona(persona) or "operator"
    rank = _PERSONA_RANK.get(p, 0)
    allowed: list[str] = []
    for name, owned in PERSONA_OWNED_SECTIONS.items():
        if _PERSONA_RANK.get(name, 0) <= rank:
            allowed.extend(owned)
    # Preserve stable order from MAP_BODY_SECTIONS
    return tuple(s for s in MAP_BODY_SECTIONS if s in allowed)


def section_owner(section: str) -> str | None:
    for persona, sections in PERSONA_OWNED_SECTIONS.items():
        if section in sections:
            return persona
    return None


def assert_sections_writable(
    persona: str,
    sections: Iterable[str],
    *,
    role: str | None = None,
) -> None:
    if not is_write_persona(persona, role=role):
        raise MappingAccessError(
            f"Role/persona '{role or persona}' cannot write OQL hardware MAP",
            issues=["write denied for viewer/guest or unknown persona"],
        )
    allowed = set(sections_writable_by(persona))
    forbidden = [s for s in sections if s not in allowed]
    if forbidden:
        raise MappingAccessError(
            f"Persona '{persona}' cannot edit sections: {', '.join(forbidden)}",
            issues=[f"section '{s}' owned by '{section_owner(s)}'" for s in forbidden],
        )


def merge_mapping_sections(
    base: Mapping[str, Any],
    patch: Mapping[str, Any],
    *,
    sections: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Deep-merge selected top-level sections into a copy of base."""
    result = deepcopy(dict(base))
    keys = list(sections) if sections is not None else [k for k in patch.keys() if k in MAP_BODY_SECTIONS]
    for key in keys:
        if key not in MAP_BODY_SECTIONS:
            continue
        if key not in patch:
            continue
        value = patch[key]
        if value is None:
            result[key] = {}
            continue
        if not isinstance(value, dict):
            raise MappingAccessError(
                f"Section '{key}' must be an object",
                issues=[f"{key} must be an object"],
            )
        result[key] = deepcopy(value)
    # Preserve/refresh meta access labels without requiring client to send them.
    result["meta"] = _build_meta(result.get("meta") if isinstance(result.get("meta"), dict) else {})
    return result


def filter_mapping_for_persona(
    mapping: Mapping[str, Any],
    persona: str,
    *,
    include_locked: bool = True,
) -> dict[str, Any]:
    """Return mapping view annotated with editability (full body by default)."""
    p = normalize_oql_persona(persona) or "operator"
    writable = set(sections_writable_by(p))
    body = {k: deepcopy(mapping.get(k) if isinstance(mapping.get(k), dict) else {}) for k in MAP_BODY_SECTIONS}
    if not include_locked:
        body = {k: v for k, v in body.items() if k in writable}
    return {
        "persona": p,
        "editable_sections": list(sections_writable_by(p)),
        "owned_sections": list(sections_owned_by(p)),
        "locked_sections": [s for s in MAP_BODY_SECTIONS if s not in writable],
        "mapping": body,
        "meta": _build_meta(mapping.get("meta") if isinstance(mapping.get("meta"), dict) else {}),
    }


def access_policy_document() -> dict[str, Any]:
    layers = []
    for persona in OQL_EDIT_PERSONAS:
        layers.append(
            {
                "persona": persona,
                "rank": _PERSONA_RANK[persona],
                "owned_sections": list(PERSONA_OWNED_SECTIONS[persona]),
                "writable_sections": list(sections_writable_by(persona)),
                "description": {
                    "system": "Dostęp do systemu — binding runtime, akcje sprzętowe",
                    "administrator": "Funkcje i mapowania obiektów OQL → hardware",
                    "operator": "Zmienne / parametry / sensory (paramSensorMap)",
                }.get(persona, ""),
            }
        )
    return {
        "ok": True,
        "contract": "hardware-map-v1+access",
        "personas": list(OQL_EDIT_PERSONAS),
        "sections": list(MAP_BODY_SECTIONS),
        "section_owners": {s: section_owner(s) for s in MAP_BODY_SECTIONS},
        "layers": layers,
        "headers": {
            "persona": "X-Oql-Edit-Persona",
            "role": "X-Connect-Role",
        },
        "notes": [
            "Hardware MAP is part of OQL configuration (not a separate product island).",
            "Full PUT /hardware/mapping remains available for system persona / import tools.",
            "Prefer PATCH /hardware/mapping/layer/{persona} for role-scoped edits.",
            "DisplayNet (.109) stores MAP; BoardNet (.122) executes via OqlOS plugins.",
        ],
    }


def _build_meta(existing: Mapping[str, Any] | None = None) -> dict[str, Any]:
    meta = dict(existing or {})
    meta["access"] = {
        "personas": list(OQL_EDIT_PERSONAS),
        "section_owners": {s: section_owner(s) for s in MAP_BODY_SECTIONS},
        "model": "hierarchical-system-admin-operator",
    }
    return meta
