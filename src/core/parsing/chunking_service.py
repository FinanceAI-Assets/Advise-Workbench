"""
Semantic chunking service for Stage 1.2: Content Extraction.

Splits parsed content into chunks with overlap, preserving source location.
"""

import logging
from typing import List, Dict, Any, Tuple
import re

logger = logging.getLogger(__name__)


class ChunkingService:
    """Service for creating semantic chunks from parsed documents."""

    def __init__(self, chunk_size: int = 1024, overlap: int = 204):
        """
        Initialize chunking service.

        Args:
            chunk_size: Characters per chunk (default: 1024)
            overlap: Overlap between chunks in characters (default: 204 = 20%)
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

    @staticmethod
    def _get_sentence_boundaries(text: str, max_pos: int) -> int:
        """Find sentence boundary near max_pos."""
        # Try to find sentence end (. ! ?) before max_pos
        for i in range(max_pos, max(0, max_pos - 100), -1):
            if i < len(text) and text[i] in '.!?':
                # Found punctuation, return position after it
                return min(i + 1, len(text))

        # Try paragraph boundary
        for i in range(max_pos, max(0, max_pos - 100), -1):
            if i < len(text) and text[i] == '\n':
                return i + 1

        # Try space
        for i in range(max_pos, max(0, max_pos - 50), -1):
            if i < len(text) and text[i] == ' ':
                return i + 1

        # Fallback: return max_pos
        return max_pos

    def create_chunks(self, text: str, source_info: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Create semantic chunks from text.

        Args:
            text: Full text to chunk
            source_info: Dictionary with page_number, table_index, image_index, etc.

        Returns:
            List of chunk dictionaries
        """
        if source_info is None:
            source_info = {"page_number": 1}

        chunks = []
        start_pos = 0
        chunk_num = 1

        while start_pos < len(text):
            # Calculate end position
            end_pos = min(start_pos + self.chunk_size, len(text))

            # Find sentence boundary
            if end_pos < len(text):
                end_pos = self._get_sentence_boundaries(text, end_pos)

            # Extract chunk
            chunk_text = text[start_pos:end_pos].strip()

            if chunk_text:  # Only add non-empty chunks
                chunk = {
                    "chunk_number": chunk_num,
                    "text": chunk_text,
                    "character_count": len(chunk_text),
                    "token_estimate": len(chunk_text) // 4,  # Rough estimate
                    "source": source_info.copy(),
                    "start_char": start_pos,
                    "end_char": end_pos,
                }
                chunks.append(chunk)
                chunk_num += 1

            # Move start position (with overlap)
            start_pos = end_pos - self.overlap

            if end_pos >= len(text):
                break

        logger.info(f"[CHUNK] Created {len(chunks)} chunks from {len(text)} characters")
        return chunks

    def create_chunks_from_parsed(self, parsed_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Create chunks from entire parsed document.

        Args:
            parsed_data: Output from DoclingParserService.parse_document()

        Returns:
            Dictionary with chunks organized by source
        """
        all_chunks = {
            "main_text": [],
            "table_text": [],
            "image_text": [],
            "total_chunks": 0,
        }

        # Chunk main text page by page so every chunk keeps its page number
        pages = parsed_data.get("pages") or [{"page_number": None, "text": parsed_data.get("full_text") or ""}]
        for page in pages:
            if (page.get("text") or "").strip():
                all_chunks["main_text"].extend(
                    self.create_chunks(
                        page["text"],
                        {"source_type": "main_text", "page_number": page.get("page_number")},
                    )
                )

        # Chunk table content
        for table in parsed_data.get("tables", []):
            table_chunks = self.create_chunks(
                table.get("markdown", ""),
                {
                    "source_type": "table",
                    "page_number": table.get("page_number"),
                    "table_index": table.get("table_index"),
                }
            )
            all_chunks["table_text"].extend(table_chunks)

        # Chunk image descriptions (when available)
        for image in parsed_data.get("images", []):
            if image.get("description"):
                image_chunks = self.create_chunks(
                    image["description"],
                    {
                        "source_type": "image",
                        "page_number": image.get("page_number"),
                        "image_index": image.get("image_index"),
                    }
                )
                all_chunks["image_text"].extend(image_chunks)

        # Number chunks once across the whole document (create_chunks restarts at 1 per call)
        number = 0
        for group in ("main_text", "table_text", "image_text"):
            for chunk in all_chunks[group]:
                number += 1
                chunk["chunk_number"] = number
        all_chunks["total_chunks"] = number

        logger.info(
            f"[CHUNK] Total chunks created: {all_chunks['total_chunks']} "
            f"(main: {len(all_chunks['main_text'])}, "
            f"tables: {len(all_chunks['table_text'])}, "
            f"images: {len(all_chunks['image_text'])})"
        )

        return all_chunks


def get_chunking_service(chunk_size: int = 1024, overlap: int = 204) -> ChunkingService:
    """Get chunking service instance."""
    return ChunkingService(chunk_size=chunk_size, overlap=overlap)
