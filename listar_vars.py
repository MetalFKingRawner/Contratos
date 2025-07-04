# listar_vars.py
import re, zipfile
from xml.etree import ElementTree

DOCX_PATH = "pdfs/templates/pdfs/contrato_ejidal_contado.docx"

def listar_placeholders(path):
    # Un docx es un ZIP. Abrimos el documento principal:
    with zipfile.ZipFile(path) as docx:
        xml = docx.read("word/document.xml")
    # Los placeholders vienen como texto {{ VAR }}
    text = xml.decode("utf-8")
    vars = set(re.findall(r"\{\{\s*(\w+)\s*\}\}", text))
    print("Placeholders encontrados en la plantilla:")
    for v in sorted(vars):
        print("  ", v)

if __name__ == "__main__":
    listar_placeholders(DOCX_PATH)
