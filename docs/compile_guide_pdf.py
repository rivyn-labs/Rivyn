import os
import subprocess
import sys

def compile_pdf():
    docs_dir = os.path.dirname(os.path.abspath(__file__))
    html_file = os.path.join(docs_dir, "render_guide.html")
    pdf_file = os.path.join(docs_dir, "Rivyn_Product_Engineering_Guide.pdf")

    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]

    edge_bin = None
    for p in edge_paths:
        if os.path.exists(p):
            edge_bin = p
            break

    if not edge_bin:
        print("Error: Microsoft Edge not found for headless PDF generation", file=sys.stderr)
        sys.exit(1)

    file_uri = "file:///" + html_file.replace("\\", "/")
    print(f"Compiling {file_uri} -> {pdf_file}")

    cmd = [
        edge_bin,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_file}",
        file_uri
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(pdf_file) and os.path.getsize(pdf_file) > 0:
        print(f"Successfully generated PDF: {pdf_file} (Size: {os.path.getsize(pdf_file):,} bytes)")
    else:
        print(f"PDF generation failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    compile_pdf()
