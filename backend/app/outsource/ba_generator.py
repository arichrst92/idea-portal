"""Berita Acara PDF generator — TSK-105.

Auto-generate BA PDF dari approved timesheet:
- IDE Asia letterhead
- Period + placement info (employee, client, role)
- Attendance table (daily entries)
- Total workdays + summary
- Signature blocks (IDEA + Client)

Upload PDF ke MinIO: outsource/ba/{ba_no}.pdf
"""

from __future__ import annotations

from datetime import date
from io import BytesIO

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import upload_fileobj
from app.organization.models import Employee
from app.outsource.models import (
    Client as ClientModel,
    OutsourcePlacement,
    Timesheet,
    TimesheetItem,
)


MONTHS_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

DAYS_ID = ["Min", "Sen", "Sel", "Rab", "Kam", "Jum", "Sab"]


def _build_html(
    ba_no: str,
    timesheet: Timesheet,
    placement: OutsourcePlacement,
    employee: Employee,
    client: ClientModel,
    items: list[TimesheetItem],
    nik: str | None = None,
) -> str:
    period_label = f"{MONTHS_ID[timesheet.month - 1]} {timesheet.year}"
    today_str = date.today().strftime("%d %B %Y")
    present_count = sum(1 for i in items if i.is_present)
    absent_count = sum(1 for i in items if not i.is_present)

    # Build attendance table rows
    rows = []
    items_sorted = sorted(items, key=lambda i: i.work_date)
    for it in items_sorted:
        weekday_name = DAYS_ID[(it.work_date.weekday() + 1) % 7]
        status_color = "#34C759" if it.is_present else "#FF3B30"
        status_label = "Hadir" if it.is_present else "Tidak Hadir"
        notes = it.notes or "—"
        rows.append(f"""
          <tr>
            <td style="text-align:center">{it.work_date.day}</td>
            <td>{weekday_name}</td>
            <td>{it.work_date.strftime("%d %B %Y")}</td>
            <td style="text-align:center;color:{status_color};font-weight:600">{status_label}</td>
            <td>{notes}</td>
          </tr>
        """)
    table_rows = "".join(rows) if rows else """
      <tr><td colspan="5" style="text-align:center;color:#86868B;padding:20px">
        Tidak ada entry attendance
      </td></tr>
    """

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<title>Berita Acara {ba_no}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Helvetica', Arial, sans-serif; font-size: 11pt; color: #1d1d1f; padding: 28px; }}
  .header {{ border-bottom: 3px solid #0071E3; padding-bottom: 14px; margin-bottom: 22px; }}
  .company {{ font-size: 18pt; font-weight: 800; color: #0071E3; }}
  .subtitle {{ font-size: 10pt; color: #6e6e73; margin-top: 2px; }}
  h1 {{ font-size: 16pt; margin: 16px 0 4px 0; text-align: center; letter-spacing: 1px; }}
  .ba-no {{ text-align: center; font-size: 11pt; color: #6e6e73; margin-bottom: 22px; }}
  .info-block {{ background: #F5F5F7; border-radius: 8px; padding: 16px; margin-bottom: 18px; }}
  .info-row {{ display: flex; margin-bottom: 6px; font-size: 10.5pt; }}
  .info-label {{ width: 140px; color: #6e6e73; font-weight: 500; }}
  .info-value {{ flex: 1; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 14px; font-size: 9.5pt; }}
  th {{ background: #0071E3; color: white; padding: 8px 10px; text-align: left; font-size: 9.5pt; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #E8E8ED; }}
  td:first-child {{ width: 40px; }}
  .summary-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin: 16px 0 20px 0; }}
  .summary-box {{ background: #F5F5F7; padding: 14px; border-radius: 8px; text-align: center; }}
  .summary-label {{ font-size: 9pt; color: #6e6e73; text-transform: uppercase; letter-spacing: 0.5px; }}
  .summary-value {{ font-size: 22pt; font-weight: 800; margin-top: 4px; }}
  .signature {{ margin-top: 40px; display: flex; justify-content: space-around; }}
  .sig-block {{ width: 240px; text-align: center; font-size: 10pt; }}
  .sig-line {{ border-top: 1.5px solid #1d1d1f; margin-top: 64px; padding-top: 4px; }}
  .sig-title {{ font-size: 9pt; color: #6e6e73; margin-bottom: 4px; font-weight: 600; }}
  .footer {{ margin-top: 36px; padding-top: 14px; border-top: 1px solid #E8E8ED;
            font-size: 8.5pt; color: #86868B; text-align: center; }}
  .signed-stamp {{
    margin-top: 6px; padding: 2px 8px; border-radius: 12px;
    background: rgba(52,199,89,0.15); color: #34C759;
    display: inline-block; font-size: 8pt; font-weight: 700;
  }}
</style>
</head>
<body>

<div class="header">
  <div class="company">PT. Solusi Inovasi Bangsa</div>
  <div class="subtitle">IDE Asia · IDEA Portal — Outsource Management</div>
</div>

<h1>BERITA ACARA KEHADIRAN</h1>
<div class="ba-no">No: <strong>{ba_no}</strong> · Tanggal: {today_str}</div>

<div class="info-block">
  <div class="info-row">
    <div class="info-label">Periode</div>
    <div class="info-value">{period_label}</div>
  </div>
  <div class="info-row">
    <div class="info-label">Karyawan</div>
    <div class="info-value">{employee.full_name} ({nik or '—'})</div>
  </div>
  <div class="info-row">
    <div class="info-label">Client</div>
    <div class="info-value">{client.name} ({client.code})</div>
  </div>
  <div class="info-row">
    <div class="info-label">Posisi/Role</div>
    <div class="info-value">{placement.role_at_client}</div>
  </div>
  <div class="info-row">
    <div class="info-label">PIC Client</div>
    <div class="info-value">{client.pic_name or '—'}</div>
  </div>
</div>

<div class="summary-grid">
  <div class="summary-box" style="background:rgba(52,199,89,0.08)">
    <div class="summary-label">Hari Hadir</div>
    <div class="summary-value" style="color:#34C759">{present_count}</div>
  </div>
  <div class="summary-box" style="background:rgba(255,59,48,0.08)">
    <div class="summary-label">Tidak Hadir</div>
    <div class="summary-value" style="color:#FF3B30">{absent_count}</div>
  </div>
  <div class="summary-box" style="background:rgba(0,113,227,0.08)">
    <div class="summary-label">Total Workdays</div>
    <div class="summary-value" style="color:#0071E3">{timesheet.workdays_count}</div>
  </div>
</div>

<h3 style="margin-top:24px;margin-bottom:8px">Rincian Kehadiran Harian</h3>
<table>
  <thead>
    <tr>
      <th style="width:40px;text-align:center">Tgl</th>
      <th style="width:60px">Hari</th>
      <th style="width:120px">Tanggal</th>
      <th style="width:100px;text-align:center">Status</th>
      <th>Catatan</th>
    </tr>
  </thead>
  <tbody>{table_rows}</tbody>
</table>

<p style="margin-top:18px;font-size:10pt;color:#6e6e73">
  Berita Acara ini merupakan rekapitulasi kehadiran karyawan outsource untuk
  periode <strong>{period_label}</strong> yang telah diverifikasi dan disetujui
  oleh Operation PT. Solusi Inovasi Bangsa, dan akan dijadikan dasar penagihan
  ke client.
</p>

<div class="signature">
  <div class="sig-block">
    <div class="sig-title">IDE ASIA</div>
    <div class="sig-line">PT. Solusi Inovasi Bangsa</div>
    <div style="font-size:9pt;color:#6e6e73;margin-top:4px">Operation Manager</div>
  </div>
  <div class="sig-block">
    <div class="sig-title">CLIENT</div>
    <div class="sig-line">{client.name}</div>
    <div style="font-size:9pt;color:#6e6e73;margin-top:4px">{client.pic_name or 'Authorized Signatory'}</div>
  </div>
</div>

<div class="footer">
  Dokumen ini di-generate otomatis oleh IDEA Portal. Confidential — internal &amp; client use only.<br>
  PT. Solusi Inovasi Bangsa · portal.ide.asia
</div>

</body></html>"""


async def generate_ba_pdf(
    session: AsyncSession, timesheet_id, ba_no: str,
) -> str:
    """Generate BA PDF + upload ke MinIO. Returns object_name."""
    # Fetch timesheet + items + placement + employee + client
    ts_stmt = select(Timesheet).where(Timesheet.id == timesheet_id)
    ts = (await session.execute(ts_stmt)).scalar_one_or_none()
    if ts is None:
        raise ValueError(f"Timesheet {timesheet_id} not found")

    items_stmt = (
        select(TimesheetItem)
        .where(TimesheetItem.timesheet_id == timesheet_id)
        .order_by(TimesheetItem.work_date)
    )
    items = list((await session.execute(items_stmt)).scalars().all())

    placement = await session.get(OutsourcePlacement, ts.placement_id)
    if placement is None:
        raise ValueError(f"Placement {ts.placement_id} not found")
    employee = await session.get(Employee, placement.employee_id)
    client = await session.get(ClientModel, placement.client_id)

    # Fetch nik via User join
    nik = None
    if employee:
        from app.identity.models import User as _User
        r = await session.execute(select(_User.nik).where(_User.id == employee.user_id))
        nik = r.scalar_one_or_none()

    html = _build_html(ba_no, ts, placement, employee, client, items, nik)

    # Lazy import weasyprint (native libs)
    try:
        from weasyprint import HTML as _HTML
    except OSError as e:
        raise RuntimeError(
            f"WeasyPrint native libs missing. Install di macOS: 'brew install pango libffi'. "
            f"Detail: {e}"
        ) from e
    pdf_bytes = _HTML(string=html).write_pdf()

    object_name = f"outsource/ba/{ba_no}.pdf"
    upload_fileobj(
        BytesIO(pdf_bytes),
        object_name,
        content_type="application/pdf",
        length=len(pdf_bytes),
    )
    return object_name
