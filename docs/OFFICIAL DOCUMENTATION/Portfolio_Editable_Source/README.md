# FLASHCORE — Portfolio Editable Source & PDF Generation Toolchain
## Python ReportLab Source Scripts, Layout Engine, Asset Manifest & Build Instructions

> **Student:** Manas Aggarwal (Roll No. 2501730302)  
> **Course / Programme:** B.Tech CSE (AI/ML), 3rd Semester, Section A  
> **Supervisor:** Ms. Mansi Kajal, Assistant Professor, SOET, K.R. Mangalam University  

---

## Directory Inventory

This folder maintains 100% reproducible editable source code for generating all official PDF documentation volumes for FLASHCORE:

| File / Subdirectory | Purpose & Description | Output PDF Target |
| :--- | :--- | :--- |
| **`lib.py`** | Shared ReportLab styling engine, typography, custom `NumberedCanvas` (Page X of Y), table templates, and callout blocks. | Framework / Dependency |
| **`build_portfolio.py`** | Compiles the 20-screen UI screenshot portfolio with figure titles, component metadata, and verification narratives. | `../Screenshot_Portfolio.pdf` |
| **`build_database_doc.py`** | Compiles complete relational schema documentation, 14 tables, 130 constraints, 28 indexes, data dictionary, and ER diagram. | `../Database_Documentation.pdf` |
| **`build_testing_doc.py`** | Compiles test suite execution evidence: 144 backend pytest tests, 124 frontend vitest tests, and concurrency stress benchmarks. | `../Testing_and_Validation.pdf` |
| **`build_source_appendix.py`** | Compiles forensic source verification, Git commit records, lines-of-code metrics, and 9 npm audit advisories disclosure. | `../Source_Verification_Appendix.pdf` |
| **`build_all_pdfs.py`** | Master orchestration script that compiles all four volumes sequentially. | All 4 PDFs |
| **`assets/screenshots/`** | Contains all 20 canonical application screenshots (`01-login-desktop.png` through `20-not-found-404-desktop.png`). | Visual Asset Source |
| **`assets/benchmarks/`** | Stores concurrency test harness outputs, latency percentiles, and throughput metrics. | Data Asset Source |

---

## Build Execution Instructions

To compile all 4 official PDFs from source:

```bash
# Navigate to the editable source directory
cd "docs/OFFICIAL DOCUMENTATION/Portfolio_Editable_Source"

# Run the master compilation script
python build_all_pdfs.py
```

### Compiling Individual PDF Volumes
```bash
python build_portfolio.py
python build_database_doc.py
python build_testing_doc.py
python build_source_appendix.py
```

### Build Requirements
- Python 3.10+
- `reportlab >= 4.0` (Verified with ReportLab 5.1.0)
- `pillow >= 10.0`
