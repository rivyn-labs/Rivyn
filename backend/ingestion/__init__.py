"""Log Ingestion Module"""
from backend.ingestion.detector import LogStructureDetector
from backend.ingestion.loader import LogLoader

__all__ = ["LogStructureDetector", "LogLoader"]
