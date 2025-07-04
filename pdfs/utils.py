# utils.py
from docx import Document
from docx2pdf import convert
import pythoncom
from docxtpl import DocxTemplate
import os

def fill_word_template(template_path, context, output_docx_path):
    """
    Rellena la plantilla Word (con marcadores Jinja {{ CAMPO }})
    y escribe el resultado en output_docx_path.
    """
    tpl = DocxTemplate(template_path)
    tpl.render(context)
    tpl.save(output_docx_path)
    return output_docx_path

def convert_docx_to_pdf(docx_path, output_pdf_path):
    """Convierte DOCX a PDF usando docx2pdf, inicializando COM."""
    try:
        pythoncom.CoInitialize()            # <— Inicializa COM
        convert(docx_path, output_pdf_path)
        return True
    except Exception as e:
        print(f"Error al convertir DOCX a PDF: {e}")
        return False
    finally:
        pythoncom.CoUninitialize()          # <— Libera COM