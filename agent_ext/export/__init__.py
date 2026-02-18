from .html_writer import HtmlExporter
from .docx_writer import DocxExporter
from .pdf_writer import PdfExporter

EXPORTERS = {
    "html": HtmlExporter(),
    "docx": DocxExporter(),
    "pdf": PdfExporter(),
    # "pptx": PptxExporter(),  # add next
}
