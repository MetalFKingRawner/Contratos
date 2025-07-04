# utils.py
from docx import Document
from docx2pdf import convert
from docxtpl import DocxTemplate
import os
import subprocess
import shlex

def fill_word_template(template_path, context, output_docx_path):
    """
    Rellena la plantilla Word (con marcadores Jinja {{ CAMPO }})
    y escribe el resultado en output_docx_path.
    """
    tpl = DocxTemplate(template_path)
    tpl.render(context)
    tpl.save(output_docx_path)
    return output_docx_path

def convert_docx_to_pdf(docx_path: str, output_pdf_path: str) -> bool:
    """
    Convierte DOCX a PDF usando unoconv (LibreOffice).
    Lanza RuntimeError si falla.
    """
    # Construye el comando
    cmd = f'unoconv -f pdf -o "{output_pdf_path}" "{docx_path}"'
    proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Error en unoconv:\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}"
        )
    return True
