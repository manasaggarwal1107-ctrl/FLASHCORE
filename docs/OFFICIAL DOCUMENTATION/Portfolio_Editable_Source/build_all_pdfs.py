# -*- coding: utf-8 -*-
"""Master PDF Compilation Script for FLASHCORE Official Documentation.

Executes all 4 ReportLab build scripts sequentially:
1. build_portfolio.py         -> Screenshot_Portfolio.pdf
2. build_database_doc.py      -> Database_Documentation.pdf
3. build_testing_doc.py       -> Testing_and_Validation.pdf
4. build_source_appendix.py   -> Source_Verification_Appendix.pdf
"""
import os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_portfolio
import build_database_doc
import build_testing_doc
import build_source_appendix

def main():
    print("=" * 70)
    print("FLASHCORE Official Documentation PDF Generator")
    print("=" * 70)
    
    start_time = time.time()
    
    print("\n[1/4] Building Screenshot_Portfolio.pdf...")
    build_portfolio.build_pdf()
    
    print("\n[2/4] Building Database_Documentation.pdf...")
    build_database_doc.build_pdf()
    
    print("\n[3/4] Building Testing_and_Validation.pdf...")
    build_testing_doc.build_pdf()
    
    print("\n[4/4] Building Source_Verification_Appendix.pdf...")
    build_source_appendix.build_pdf()
    
    elapsed = time.time() - start_time
    print(f"\nAll 4 official PDFs generated successfully in {elapsed:.2f} seconds!")
    print(f"Destination: {os.path.abspath(os.path.join(HERE, '..'))}")

if __name__ == "__main__":
    main()
