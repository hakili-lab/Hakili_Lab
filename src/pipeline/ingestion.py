import fitz  # PyMuPDF
from pathlib import Path

from src.models.domain import IngestionResult


def ingest_pdf(pdf_path: Path, copy_id: str, output_dir: Path) -> IngestionResult:
    """
    Convertit un PDF en images JPG, une par page.

    Args:
        pdf_path: Chemin vers le fichier PDF
        copy_id: Identifiant anonyme de la copie
        output_dir: Dossier de sortie (sera créé si nécessaire)

    Returns:
        IngestionResult avec les chemins des images extraites
    """
    output_dir = output_dir / copy_id / "pages"
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    image_paths = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=300)  # Haute résolution pour l'OCR

        image_path = output_dir / f"page_{page_num + 1:02d}.jpg"
        pix.save(str(image_path))
        image_paths.append(image_path)

    doc.close()

    return IngestionResult(
        copy_id=copy_id,
        total_pages=len(image_paths),
        pages=image_paths,
        output_dir=output_dir,
    )