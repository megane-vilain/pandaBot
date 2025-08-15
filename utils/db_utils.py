from typing import Type, TypeVar
from tinydb.table import Document
from dataclasses import asdict

T = TypeVar("T")

def dataclass_to_document(obj: T) -> dict:
    data = asdict(obj)
    data.pop('doc_id', None)  # remove doc_id, TinyDB manages it
    return data

def document_to_dataclass(doc: Document, cls: Type[T]) -> T:
    return cls(**doc, doc_id=doc.doc_id)
