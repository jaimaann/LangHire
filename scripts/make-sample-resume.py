"""Write a one-page fictional resume PDF (for the canary and local e2e runs)."""
import sys

import pymupdf

TEXT = """Jordan Rivera
jordan.rivera@example.com | (512) 555-0142 | Austin, TX

Data Analyst with 3 years of experience in SQL, Python, Tableau and Excel.

EXPERIENCE
Data Analyst, Acme Data, Austin TX (2022 - present)
- Built Tableau dashboards used by 40 managers; automated weekly reports in Python.

EDUCATION
B.S. Statistics, University of Texas at Austin, 2021

SKILLS
SQL, Python, pandas, Tableau, Power BI, Excel, A/B testing
"""

doc = pymupdf.open()
page = doc.new_page()
page.insert_text((72, 72), TEXT, fontsize=11)
doc.save(sys.argv[1] if len(sys.argv) > 1 else "sample-resume.pdf")
