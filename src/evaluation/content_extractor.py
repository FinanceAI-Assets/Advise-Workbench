"""
Content Extraction from Artifacts

Extracts text content from various file formats:
- DOCX (Word documents)
- PPTX (PowerPoint presentations)
- XLSX (Excel workbooks)
- PDF (via text extraction)
- JSON (structured data)
- TXT (plain text)
- Markdown

Used by content quality evaluator to get text for LLM judgment.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ContentExtractor:
    """Extracts text content from various artifact formats."""

    def extract_content(self, file_path: Path, max_chars: int = 10000) -> str:
        """
        Extract text content from artifact file.

        Args:
            file_path: Path to artifact file
            max_chars: Maximum characters to extract (for efficiency)

        Returns:
            Extracted text content
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()

        extractors = {
            ".docx": self._extract_docx,
            ".pptx": self._extract_pptx,
            ".xlsx": self._extract_xlsx,
            ".pdf": self._extract_pdf,
            ".json": self._extract_json,
            ".txt": self._extract_txt,
            ".md": self._extract_txt,
        }

        extractor = extractors.get(suffix)
        if not extractor:
            logger.warning(f"No extractor for {suffix}, attempting text read")
            return self._extract_txt(file_path)

        try:
            content = extractor(file_path)
            # Truncate for efficiency
            if len(content) > max_chars:
                content = content[:max_chars] + f"\n\n[... content truncated at {max_chars} characters ...]"
            return content
        except Exception as e:
            logger.error(f"Error extracting content from {file_path}: {e}", exc_info=True)
            return ""

    @staticmethod
    def _extract_docx(file_path: Path) -> str:
        """Extract text from DOCX file."""
        try:
            from docx import Document
        except ImportError:
            logger.error("python-docx not installed. Install with: pip install python-docx")
            return ""

        try:
            doc = Document(file_path)
            paragraphs = [para.text for para in doc.paragraphs]

            # Also extract from tables
            tables_text = []
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text for cell in row.cells)
                    tables_text.append(row_text)

            all_text = "\n".join(paragraphs + tables_text)
            return all_text
        except Exception as e:
            logger.error(f"Error reading DOCX: {e}")
            return ""

    @staticmethod
    def _extract_pptx(file_path: Path) -> str:
        """Extract text from PPTX file."""
        try:
            from pptx import Presentation
        except ImportError:
            logger.error("python-pptx not installed. Install with: pip install python-pptx")
            return ""

        try:
            prs = Presentation(file_path)
            slides_text = []

            for slide_num, slide in enumerate(prs.slides, 1):
                slide_content = [f"=== SLIDE {slide_num} ==="]

                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        slide_content.append(shape.text)
                    elif hasattr(shape, "table"):
                        # Extract table content
                        table = shape.table
                        for row in table.rows:
                            row_text = " | ".join(cell.text for cell in row.cells)
                            slide_content.append(row_text)

                slides_text.append("\n".join(slide_content))

            return "\n\n".join(slides_text)
        except Exception as e:
            logger.error(f"Error reading PPTX: {e}")
            return ""

    @staticmethod
    def _extract_xlsx(file_path: Path) -> str:
        """Extract text from XLSX file."""
        try:
            import openpyxl
        except ImportError:
            logger.error("openpyxl not installed. Install with: pip install openpyxl")
            return ""

        try:
            wb = openpyxl.load_workbook(file_path)
            sheets_text = []

            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                sheet_content = [f"=== SHEET: {sheet_name} ==="]

                for row in ws.iter_rows(values_only=True):
                    row_text = " | ".join(str(cell) if cell is not None else "" for cell in row)
                    if row_text.strip():
                        sheet_content.append(row_text)

                sheets_text.append("\n".join(sheet_content))

            return "\n\n".join(sheets_text)
        except Exception as e:
            logger.error(f"Error reading XLSX: {e}")
            return ""

    @staticmethod
    def _extract_pdf(file_path: Path) -> str:
        """Extract text from PDF file."""
        try:
            import pypdf
        except ImportError:
            logger.warning("pypdf not installed. Install with: pip install pypdf")
            logger.info("Attempting fallback with pdfminer...")
            try:
                from pdfminer.high_level import extract_text
                return extract_text(str(file_path))
            except ImportError:
                logger.error("Neither pypdf nor pdfminer installed")
                return ""

        try:
            reader = pypdf.PdfReader(file_path)
            pages_text = []

            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                pages_text.append(f"=== PAGE {page_num} ===\n{text}")

            return "\n\n".join(pages_text)
        except Exception as e:
            logger.error(f"Error reading PDF: {e}")
            return ""

    @staticmethod
    def _extract_json(file_path: Path) -> str:
        """Extract text from JSON file (process maps, structured data, etc.)."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Convert JSON to readable text format
            return ContentExtractor._json_to_text(data)
        except Exception as e:
            logger.error(f"Error reading JSON: {e}")
            return ""

    @staticmethod
    def _json_to_text(obj: any, indent: int = 0) -> str:
        """Recursively convert JSON object to readable text."""
        if isinstance(obj, dict):
            lines = []
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    lines.append(f"{'  ' * indent}{key}:")
                    lines.append(ContentExtractor._json_to_text(value, indent + 1))
                else:
                    lines.append(f"{'  ' * indent}{key}: {value}")
            return "\n".join(lines)
        elif isinstance(obj, list):
            lines = []
            for item in obj:
                lines.append(ContentExtractor._json_to_text(item, indent))
            return "\n".join(lines)
        else:
            return str(obj)

    @staticmethod
    def _extract_txt(file_path: Path) -> str:
        """Extract text from plain text or markdown file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading text file: {e}")
                return ""
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return ""


# Example usage and testing
if __name__ == "__main__":
    extractor = ContentExtractor()

    # Test with a text file
    test_file = Path("test.txt")
    if test_file.exists():
        content = extractor.extract_content(test_file)
        print(f"Extracted {len(content)} characters")
        print(content[:500])
