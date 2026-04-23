import pypdf
import sys

def extract_text(pdf_path, output_path):
    try:
        reader = pypdf.PdfReader(pdf_path)
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, page in enumerate(reader.pages):
                f.write(f'--- PAGE {i+1} ---\n')
                f.write(page.extract_text() + '\n')
        print(f"Successfully extracted text to {output_path}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    extract_text('Sesion 03. Modelos en Django (ORM) (1).pdf', 'pdf_text_03.txt')
