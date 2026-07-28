"""Canonical public facade for parsing and validating OQL documents."""

from __future__ import annotations

from oqlos.models.dsl_models import OqlDocument

from .cql_parser import parse_cql, validate_cql


def parse_oql_document(source: str, filename: str = "<string>") -> OqlDocument:
    """Parse OQL source into the runtime document AST."""
    return parse_cql(source, filename)


def validate_oql_document(document: OqlDocument) -> list[str]:
    """Validate a parsed OQL runtime document."""
    return validate_cql(document)


__all__ = ["parse_oql_document", "validate_oql_document"]
