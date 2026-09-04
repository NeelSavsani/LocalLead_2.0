import os
from datetime import datetime
from typing import List, Optional
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from app.config import settings
from app.models.schemas import LeadRecord


# Theme styling constants
NAVY_HEADER_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
WHITE_BOLD_FONT = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")

TITLE_FILL = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
TITLE_FONT = Font(name="Segoe UI", size=15, bold=True, color="FFFFFF")
SUBTITLE_FONT = Font(name="Segoe UI", size=10, italic=True, color="94A3B8")

ZEBRA_EVEN_FILL = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
ZEBRA_ODD_FILL = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

DATA_FONT = Font(name="Segoe UI", size=10, color="1E293B")
LINK_FONT = Font(name="Segoe UI", size=10, color="2563EB", underline="single")
PHONE_FONT = Font(name="Segoe UI", size=10, bold=True, color="0F766E")

THIN_BORDER = Border(
    left=Side(style="thin", color="E2E8F0"),
    right=Side(style="thin", color="E2E8F0"),
    top=Side(style="thin", color="E2E8F0"),
    bottom=Side(style="thin", color="E2E8F0"),
)

CALL_STATUS_OPTIONS = [
    "Pending Call",
    "Attempted",
    "Interested - Demo Scheduled",
    "Not Interested",
    "Closed",
]


def generate_leads_excel(
    job_id: str,
    location: str,
    leads: List[LeadRecord],
    output_dir: Optional[str] = None,
) -> str:
    """
    Generates a beautifully styled .xlsx workbook using openpyxl:
    - Sheet Name: "Qualified Leads - [Location]"
    - Top Title card and scan metadata
    - Dark Navy (#1E293B) Header row with 28pt height
    - Alternating row zebra striping (#FFFFFF and #F8FAFC)
    - Auto-fit column widths with clean cell padding
    - Excel Data Validation dropdown for Call Status
    - Hyperlinks for Google Maps links
    - Frozen panes above data rows
    """
    wb = openpyxl.Workbook()
    ws = wb.active

    # Clean sheet name (max 31 characters for Excel specification)
    clean_loc = location.replace(":", " ").replace("/", " ").replace("\\", " ")
    sheet_title = f"Leads - {clean_loc}"[:31]
    ws.title = sheet_title

    # 1. Top Title Banner (Row 1 & Row 2)
    ws.merge_cells("A1:K1")
    title_cell = ws["A1"]
    title_cell.value = f"LOCALLEADPULSE B2B SALES PIPELINE — {location.upper()}"
    title_cell.font = TITLE_FONT
    title_cell.fill = TITLE_FILL
    title_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 36

    ws.merge_cells("A2:K2")
    sub_cell = ws["A2"]
    scan_date = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    sub_cell.value = (
        f"Generated: {scan_date}  |  Total Qualified Leads: {len(leads)}  |  "
        "Filter: Dual-Layer Verified (No Maps Website + No Organic Search Domain)"
    )
    sub_cell.font = SUBTITLE_FONT
    sub_cell.fill = TITLE_FILL
    sub_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 22

    # Empty spacer row 3
    ws.row_dimensions[3].height = 8

    # 2. Header Row (Row 4)
    headers = [
        "ID",
        "Shop / Business Name",
        "Category",
        "Contact Number",
        "Full Physical Address",
        "Area / Landmark",
        "Google Maps URL",
        "Web Search Verification Status",
        "Call Status",
        "Pitch Angle / Opportunity",
        "Lead Identified Date",
    ]

    ws.row_dimensions[4].height = 28
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=col_idx, value=header)
        cell.fill = NAVY_HEADER_FILL
        cell.font = WHITE_BOLD_FONT
        cell.alignment = Alignment(horizontal="center" if col_idx in [1, 4, 9, 11] else "left", vertical="center")
        cell.border = THIN_BORDER

    # 3. Data Rows
    start_row = 5
    max_row = start_row + len(leads) - 1 if leads else start_row

    for idx, lead in enumerate(leads):
        current_row = start_row + idx
        ws.row_dimensions[current_row].height = 22
        fill = ZEBRA_EVEN_FILL if idx % 2 == 0 else ZEBRA_ODD_FILL

        row_data = [
            (lead.id, "center", DATA_FONT),
            (lead.name, "left", Font(name="Segoe UI", size=10, bold=True, color="0F172A")),
            (lead.category, "left", DATA_FONT),
            (lead.phone, "center", PHONE_FONT),
            (lead.address, "left", DATA_FONT),
            (lead.area or "N/A", "left", DATA_FONT),
            (lead.maps_url or "N/A", "left", LINK_FONT),
            (lead.verification_status, "left", DATA_FONT),
            (lead.call_status, "center", DATA_FONT),
            (lead.pitch_angle, "left", DATA_FONT),
            (lead.date_identified, "center", DATA_FONT),
        ]

        for col_idx, (val, align_h, font) in enumerate(row_data, start=1):
            cell = ws.cell(row=current_row, column=col_idx, value=val)
            cell.fill = fill
            cell.font = font
            cell.alignment = Alignment(horizontal=align_h, vertical="center")
            cell.border = THIN_BORDER

            # Hyperlink Maps URL
            if col_idx == 7 and val and val.startswith("http"):
                cell.hyperlink = val

    # 4. Data Validation Dropdown for Call Status (Column I, index 9)
    dv = DataValidation(
        type="list",
        formula1=f'"{",".join(CALL_STATUS_OPTIONS)}"',
        allow_blank=True,
        showDropDown=False,
    )
    dv.error = "Please choose a valid status from the CRM dropdown list."
    dv.errorTitle = "Invalid Call Status"
    dv.prompt = "Select cold call outreach stage"
    dv.promptTitle = "Call Status"
    ws.add_data_validation(dv)

    if leads:
        dv.add(f"I{start_row}:I{max_row}")
    else:
        dv.add(f"I{start_row}:I{start_row + 10}")

    # 5. Column Auto-Fit Widths
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            # Skip title banner rows when calculating column widths
            if cell.row in [1, 2, 3]:
                continue
            if cell.value:
                val_str = str(cell.value)
                max_len = max(max_len, len(val_str))
        
        # Specific ideal minimum/maximum bounds
        if col_letter == "A":
            ws.column_dimensions[col_letter].width = 12
        elif col_letter == "B":
            ws.column_dimensions[col_letter].width = max(max_len + 4, 30)
        elif col_letter == "D":
            ws.column_dimensions[col_letter].width = 20
        elif col_letter == "E":
            ws.column_dimensions[col_letter].width = min(max(max_len + 4, 35), 55)
        elif col_letter == "G":
            ws.column_dimensions[col_letter].width = 28
        elif col_letter == "I":
            ws.column_dimensions[col_letter].width = 26
        elif col_letter == "J":
            ws.column_dimensions[col_letter].width = 38
        else:
            ws.column_dimensions[col_letter].width = max(max_len + 4, 16)

    # 6. Freeze Panes: Lock rows 1-4 so headers stay visible while scrolling data
    ws.freeze_panes = "A5"

    # 7. Save workbook to output directory
    target_dir = output_dir or settings.EXPORTS_DIR
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, f"leads_{job_id}.xlsx")
    wb.save(file_path)

    return file_path
