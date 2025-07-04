# utils.py
from docx import Document
from docx2pdf import convert
from docxtpl import DocxTemplate
import os
import subprocess, shlex, logging

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
    cmd = f'unoconv -f pdf -o "{output_pdf_path}" "{docx_path}"'
    logger.debug(f"Ejecutando comando: {cmd}")
    proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
    logger.debug(f"unoconv returncode={proc.returncode}")
    logger.debug(f"unoconv stdout:\n{proc.stdout}")
    logger.debug(f"unoconv stderr:\n{proc.stderr}")
    if proc.returncode != 0:
        msg = f"Error en conversión DOCX→PDF (returncode {proc.returncode})."
        logger.error(msg)
        raise RuntimeError(f"{msg}\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
    return True
