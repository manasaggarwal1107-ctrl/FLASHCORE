# -*- coding: utf-8 -*-
"""Layout and styling library for FLASHCORE Official Academic Documentation.

Provides cross-platform ReportLab styles, custom page templates with running headers
and "Page X of Y" footers, tables, callout boxes, and figure blocks.
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table,
    TableStyle, Flowable, PageBreak, KeepTogether, HRFlowable
)

PAGE_W, PAGE_H = A4
MARGIN_L = 18 * mm
MARGIN_R = 18 * mm
MARGIN_T = 22 * mm
MARGIN_B = 22 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

# ---------------------------------------------------------------- palette
PRIMARY = HexColor("#0F172A")    # Slate 900
SECONDARY = HexColor("#1E293B")  # Slate 800
ACCENT = HexColor("#0284C7")     # Sky 600
ACCENT_DARK = HexColor("#0369A1")# Sky 700
MUTED = HexColor("#475569")      # Slate 600
FAINT = HexColor("#94A3B8")      # Slate 400
LINE_COLOR = HexColor("#E2E8F0") # Slate 200
BG_PANEL = HexColor("#F8FAFC")   # Slate 50
SUCCESS = HexColor("#16A34A")    # Green 600
WARN = HexColor("#D97706")       # Amber 600
DANGER = HexColor("#DC2626")     # Red 600

# ---------------------------------------------------------------- styles
styles = getSampleStyleSheet()

ST = {
    "title": ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        textColor=PRIMARY,
        alignment=TA_LEFT,
        spaceAfter=12
    ),
    "subtitle": ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=MUTED,
        alignment=TA_LEFT,
        spaceAfter=18
    ),
    "meta_label": ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        textColor=SECONDARY
    ),
    "meta_val": ParagraphStyle(
        "MetaVal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=MUTED
    ),
    "h1": ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=22,
        textColor=PRIMARY,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    ),
    "h2": ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=18,
        textColor=ACCENT_DARK,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    ),
    "h3": ParagraphStyle(
        "H3",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=SECONDARY,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    ),
    "body": ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=PRIMARY,
        alignment=TA_LEFT,
        spaceAfter=6
    ),
    "body_muted": ParagraphStyle(
        "BodyMuted",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=MUTED,
        spaceAfter=4
    ),
    "code": ParagraphStyle(
        "CodeText",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.5,
        leading=11.5,
        textColor=PRIMARY
    ),
    "table_header": ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12,
        textColor=colors.white,
        alignment=TA_LEFT
    ),
    "table_cell": ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=PRIMARY,
        alignment=TA_LEFT
    ),
    "table_cell_code": ParagraphStyle(
        "TableCellCode",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7.5,
        leading=10,
        textColor=PRIMARY
    ),
    "caption": ParagraphStyle(
        "Caption",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=MUTED,
        alignment=TA_CENTER,
        spaceAfter=8
    ),
    "badge": ParagraphStyle(
        "Badge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=SUCCESS,
        alignment=TA_LEFT
    )
}

# ---------------------------------------------------------------- canvas with page numbers
class NumberedCanvas(canvas.Canvas):
    """Custom canvas that tracks total page count for 'Page X of Y'."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages):
        # Skip decorations on cover page (page 1)
        if self._pageNumber == 1:
            return

        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(MUTED)

        # Header
        self.drawString(MARGIN_L, PAGE_H - 14 * mm, "FLASHCORE: High-Concurrency Retail Simulation & Database Systems")
        self.setStrokeColor(LINE_COLOR)
        self.setLineWidth(0.5)
        self.line(MARGIN_L, PAGE_H - 16 * mm, PAGE_W - MARGIN_R, PAGE_H - 16 * mm)

        # Footer
        self.line(MARGIN_L, 16 * mm, PAGE_W - MARGIN_R, 16 * mm)
        self.drawString(MARGIN_L, 11 * mm, "Manas Aggarwal (2501730302) | B.Tech CSE (AI/ML) | K.R. Mangalam University")
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(PAGE_W - MARGIN_R, 11 * mm, page_str)
        self.restoreState()


def create_document(output_filename, doc_title="FLASHCORE Documentation"):
    """Create a standardized BaseDocTemplate."""
    frame = Frame(
        MARGIN_L, MARGIN_B, CONTENT_W, PAGE_H - MARGIN_T - MARGIN_B,
        id='normal',
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0
    )
    doc = BaseDocTemplate(
        output_filename,
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B
    )
    doc.addPageTemplates([PageTemplate(id='content', frames=frame)])
    return doc


def make_callout(text, title="VERIFICATION STATEMENT", tone="info"):
    """Create a callout panel box."""
    tone_colors = {
        "info": (ACCENT, HexColor("#F0F9FF")),
        "success": (SUCCESS, HexColor("#F0FDF4")),
        "warn": (WARN, HexColor("#FFFBEB")),
        "danger": (DANGER, HexColor("#FEF2F2"))
    }
    bar_color, bg_color = tone_colors.get(tone, tone_colors["info"])
    
    t_style = ParagraphStyle(
        "CalloutTitle",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12,
        textColor=bar_color
    )
    b_style = ParagraphStyle(
        "CalloutBody",
        fontName="Helvetica",
        fontSize=8,
        leading=11.5,
        textColor=PRIMARY
    )
    
    table_data = [
        [Paragraph(f"<b>{title}</b>", t_style)],
        [Paragraph(text, b_style)]
    ]
    t = Table(table_data, colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_color),
        ('LINELEFT', (0,0), (-1,-1), 3, bar_color),
        ('BOX', (0,0), (-1,-1), 0.5, LINE_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    return t
