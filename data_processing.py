from langchain_community.document_loaders import (
    PyMuPDFLoader,
    UnstructuredPowerPointLoader
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
import pdfplumber
import pandas as pd
import subprocess
import os


def load_file(file_path: str) -> list[Document]:
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".pdf":
            try:
                pymupdf_loader = PyMuPDFLoader(file_path)
                all_docs = pymupdf_loader.load()

                with pdfplumber.open(file_path) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        tables = page.find_tables()
                        for table in tables:
                            table_data = table.extract()
                            if table_data and len(table_data) > 1:
                                df = pd.DataFrame(table_data[1:], columns=table_data[0])
                                table_string = "Table from PDF:\n" + df.to_markdown(index=False)
                                table_doc = Document(
                                    page_content=table_string,
                                    metadata={
                                        "source": file_path,
                                        "page": page_num + 1,
                                        "type": "table"
                                    }
                                )
                                all_docs.append(table_doc)

                return all_docs

            except Exception as e:
                print(f"[WARN] Hybrid PDF loading failed: {e}. Falling back to PyMuPDFLoader.")
                loader = PyMuPDFLoader(file_path)
                return loader.load()

        elif ext == ".pptx":
            loader = UnstructuredPowerPointLoader(file_path)
            return loader.load()

        else:
            raise ValueError(f"[ERROR] Unsupported file extension: {ext}")
    
    except Exception as e:
        raise IOError(f"[ERROR] Failed to load file {file_path}: {e}")

def split_docs(docs: list[Document], chunk_size: int = 10000, chunk_overlap: int = 2000) -> list[Document]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True
    )
    return text_splitter.split_documents(docs)

def convert_pptx_to_pdf(pptx_path: str, output_dir: str) -> str:
    """
    Converts a PowerPoint file to a PDF using LibreOffice in headless mode.
    
    Args:
        pptx_path: The path to the input .pptx file.
        output_dir: The directory where the PDF should be saved.
        
    Returns:
        The path to the converted PDF file, or None if the conversion failed.
    """
    
    if not os.path.exists(pptx_path):
        return None
    
    file_name = os.path.splitext(os.path.basename(pptx_path))[0]
    pdf_path = os.path.join(output_dir, f"{file_name}.pdf")
    
    try:
        
        cmd = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "--headless",
            "--invisible",
            "--convert-to",
            "pdf",
            "--outdir",
            output_dir,
            pptx_path,
        ]
        
        
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        if os.path.exists(pdf_path):
            return pdf_path
        else:
            return None
            
    except subprocess.CalledProcessError as e:
        print(f"Error converting {pptx_path} to PDF: {e.stderr}")
        print(f"Stdout:\n{e.stdout}")
        return None
    except FileNotFoundError:
        print("LibreOffice not found. Please ensure it is installed and in your system's PATH.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during conversion: {e}")
        return None

#loader=PyMuPDFLoader(file_path)



