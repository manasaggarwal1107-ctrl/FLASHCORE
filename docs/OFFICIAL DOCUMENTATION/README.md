# FLASHCORE — Official Documentation Portfolio
## Formal Academic PDFs, High-Resolution Diagrams & Editable Build Sources

> **Student:** Manas Aggarwal (Roll No. 2501730302)  
> **Course / Programme:** B.Tech CSE (AI/ML), 3rd Semester, Section A  
> **Supervisor:** Ms. Mansi Kajal, Assistant Professor, SOET, K.R. Mangalam University  
> **Institution:** K.R. Mangalam University, Gurugram  

---

## Directory Inventory

This folder contains formal academic deliverables compiled for evaluation, external examination, and technical archival:

### 1. Generated Formal PDF Portfolios
- **`Database_Documentation.pdf`**: Complete relational schema documentation, table specifications, integrity constraints, indexing strategies, and ER diagrams.
- **`Testing_and_Validation.pdf`**: Comprehensive verification report documenting 144 backend pytest tests, 124 frontend vitest tests, and multi-threaded concurrency benchmarks.
- **`Screenshot_Portfolio.pdf`**: High-resolution screenshot portfolio capturing 20 genuine desktop, mobile, and authenticated views of the running application.
- **`Source_Verification_Appendix.pdf`**: Code verification appendix documenting repository commits, supply-chain audits, file manifests, and environment reproducibility.

### 2. Architectural Diagrams (`B_Diagrams/`)
Located in [`B_Diagrams/`](B_Diagrams/README.md):
- `mermaid/`: 16+ editable Mermaid diagram source files (`.mmd`).
- `png/`: High-resolution rendered raster diagrams for academic reports and presentations.
- `svg/`: Scalable vector graphics versions for loss-free zoom and printing.

### 3. Portfolio Editable Source (`Portfolio_Editable_Source/`)
Located in [`Portfolio_Editable_Source/`](Portfolio_Editable_Source/README.md):
- `build_portfolio.py`: Python ReportLab script compiling `Screenshot_Portfolio.pdf`.
- `build_database_doc.py`: Python ReportLab script compiling `Database_Documentation.pdf`.
- `build_testing_doc.py`: Python ReportLab script compiling `Testing_and_Validation.pdf`.
- `build_source_appendix.py`: Python ReportLab script compiling `Source_Verification_Appendix.pdf`.
- `lib.py`: Shared typography, color palette, header/footer, and table layout engine.
- `assets/`: Screen captures, benchmark CSVs/JSONs, and diagrams used during PDF generation.

---

## Re-compiling the Official PDFs

All PDFs in this directory are 100% reproducible from source using Python and ReportLab:

```bash
cd "docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source"
python build_all_pdfs.py
```
Generated PDFs will be placed directly into `docs/OFFICIAL DOCUMENTATION/`.
