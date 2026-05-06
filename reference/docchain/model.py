"""Generic Document Chain event model helpers.

This module intentionally contains no project-specific scoring or validation.
Individual Doc Chain indexers and profilers should compose these neutral records with their own rules.
"""

from dataclasses import dataclass
from typing import Mapping


def _field(raw: Mapping[str, object], snake_name: str, camel_name: str) -> object:
    if snake_name in raw:
        return raw[snake_name]
    return raw[camel_name]


@dataclass(frozen=True)
class DocBlock:
    doc_chain_id: str
    doc_ref: int
    parent_hash: str
    content_hash: str


@dataclass(frozen=True)
class DocumentAttestation:
    attester: str
    doc_block: DocBlock
    uri: str
    deadline: int


@dataclass(frozen=True)
class DocumentAttested:
    doc_chain_id: str
    attester: str
    doc_ref: int
    submitter: str
    parent_hash: str
    block_hash: str
    content_hash: str
    uri_hash: str
    uri: str
    block_number: int
    transaction_hash: str
    log_index: int


def normalize_document_attested(raw: Mapping[str, object]) -> DocumentAttested:
    """Build a neutral event record from an already-decoded log mapping."""
    return DocumentAttested(
        doc_chain_id=str(_field(raw, "doc_chain_id", "docChainId")),
        attester=str(raw["attester"]),
        doc_ref=int(_field(raw, "doc_ref", "docRef")),
        submitter=str(raw["submitter"]),
        parent_hash=str(_field(raw, "parent_hash", "parentHash")),
        block_hash=str(_field(raw, "block_hash", "blockHash")),
        content_hash=str(_field(raw, "content_hash", "contentHash")),
        uri_hash=str(_field(raw, "uri_hash", "uriHash")),
        uri=str(raw.get("uri", "")),
        block_number=int(_field(raw, "block_number", "blockNumber")),
        transaction_hash=str(_field(raw, "transaction_hash", "transactionHash")),
        log_index=int(_field(raw, "log_index", "logIndex")),
    )
