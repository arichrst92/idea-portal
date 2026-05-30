"""Pay slip PDF generator — TSK-051.

Uses weasyprint (HTML → PDF) for ringkas template + Indonesian locale formatting.
Output di-upload ke MinIO (bucket idea-portal), object path:
  payroll/{period_id}/slip-{slip_no}.pdf
"""

from __future__ import annotations

from datetime import date
from io import BytesIO
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import upload_fileobj
from app.organization.models import Employee
from app.payroll.models import PayrollPeriod, PayrollSlip
from app.payroll.payroll_service import list_components


MONTHS_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def _fmt_idr(amount: float | int) -> str:
    try:
        return f"Rp {float(amount):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def _build_html(
    slip: PayrollSlip,
    period: PayrollPeriod,
    employee: Employee | None,
    components: list,
) -> str:
    """Generate inline-styled HTML untuk slip gaji."""
    period_label = f"{MONTHS_ID[period.month - 1]} {period.year}"
    pay_date = period.pay_date.strftime("%d %B %Y")
    today = date.today().strftime("%d %B %Y")

    incomes = [c for c in components if c.component_type == "INCOME"]
    deductions = [c for c in components if c.component_type == "DEDUCTION"]

    nik = employee.nik if employee else "—"
    full_name = employee.full_name if employee else "—"

    income_rows = "".join(
        f"""<tr>
              <td>{c.code}</td>
              <td>{c.name}</td>
              <td class="num">{_fmt_idr(c.amount)}</td>
            </tr>""" for c in incomes
    )
    deduction_rows = "".join(
        f"""<tr>
              <td>{c.code}</td>
              <td>{c.name}</td>
              <td class="num">{_fmt_idr(c.amount)}</td>
            </tr>""" for c in deductions
    )

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<title>Slip Gaji {slip.slip_no}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Helvetica', Arial, sans-serif; font-size: 11pt; color: #1d1d1f; padding: 28px; }}
  .header {{ display: flex; justify-content: space-between; border-bottom: 2px solid #0071E3; padding-bottom: 12px; margin-bottom: 18px; }}
  .company {{ font-size: 16pt; font-weight: 800; color: #0071E3; }}
  .meta {{ text-align: right; font-size: 10pt; color: #6e6e73; }}
  h1 {{ font-size: 14pt; margin: 0 0 4px 0; }}
  .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px 24px; margin-bottom: 20px; }}
  .info-grid div {{ font-size: 10.5pt; }}
  .info-label {{ color: #6e6e73; font-size: 9.5pt; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 14px; }}
  th {{ background: #F5F5F7; padding: 8px 10px; text-align: left; font-size: 10pt; border-bottom: 1.5px solid #E8E8ED; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #E8E8ED; font-size: 10pt; }}
  td.num {{ text-align: right; font-family: 'Courier New', monospace; font-weight: 500; }}
  .section-title {{ font-weight: 700; font-size: 11pt; margin: 12px 0 6px 0; padding: 4px 0; }}
  .green {{ color: #34C759; }}
  .red {{ color: #FF3B30; }}
  .totals {{ background: #F5F5F7; border-radius: 6px; padding: 14px 18px; margin-top: 14px; }}
  .totals-row {{ display: flex; justify-content: space-between; padding: 5px 0; font-size: 11pt; }}
  .totals-row.take-home {{ border-top: 2px solid #1d1d1f; margin-top: 6px; padding-top: 12px; font-weight: 800; font-size: 13pt; }}
  .totals-row.take-home .amount {{ color: #34C759; font-size: 14pt; }}
  .footer {{ margin-top: 30px; padding-top: 14px; border-top: 1px solid #E8E8ED; font-size: 9pt; color: #86868B; text-align: center; }}
  .signature {{ margin-top: 40px; display: flex; justify-content: space-between; }}
  .sig-block {{ width: 180px; text-align: center; font-size: 10pt; }}
  .sig-line {{ border-top: 1px solid #1d1d1f; margin-top: 50px; padding-top: 4px; }}
</style>
</head>
<body>

<div class="header">
  <div>
    <div class="company">PT. Solusi Inovasi Bangsa</div>
    <div style="font-size: 9pt; color: #6e6e73; margin-top: 2px;">IDEA Portal — Slip Gaji</div>
  </div>
  <div class="meta">
    Slip No: <strong>{slip.slip_no}</strong><br>
    Periode: <strong>{period_label}</strong><br>
    Pay Date: {pay_date}<br>
    Generated: {today}
  </div>
</div>

<div class="info-grid">
  <div><span class="info-label">NIK:</span><br><strong>{nik}</strong></div>
  <div><span class="info-label">Nama:</span><br><strong>{full_name}</strong></div>
</div>

<div class="section-title green">📈 Penghasilan (Income)</div>
<table>
  <thead><tr><th style="width:120px">Code</th><th>Komponen</th><th style="width:140px" class="num">Jumlah</th></tr></thead>
  <tbody>{income_rows or '<tr><td colspan="3" style="text-align:center;color:#86868B">Tidak ada komponen income</td></tr>'}</tbody>
</table>

<div class="section-title red">📉 Potongan (Deductions)</div>
<table>
  <thead><tr><th style="width:120px">Code</th><th>Komponen</th><th style="width:140px" class="num">Jumlah</th></tr></thead>
  <tbody>{deduction_rows or '<tr><td colspan="3" style="text-align:center;color:#86868B">Tidak ada potongan</td></tr>'}</tbody>
</table>

<div class="totals">
  <div class="totals-row"><span>Gross Income</span><span class="num">{_fmt_idr(slip.gross_income)}</span></div>
  <div class="totals-row"><span>Total Deductions</span><span class="num red">- {_fmt_idr(slip.total_deductions)}</span></div>
  <div class="totals-row take-home"><span>Take Home Pay</span><span class="num amount">{_fmt_idr(slip.take_home_pay)}</span></div>
</div>

<div class="signature">
  <div class="sig-block">
    <div class="sig-line">Karyawan</div>
    <div style="font-size: 9pt; color: #6e6e73; margin-top: 4px;">({full_name})</div>
  </div>
  <div class="sig-block">
    <div class="sig-line">HR / Finance</div>
    <div style="font-size: 9pt; color: #6e6e73; margin-top: 4px;">PT. Solusi Inovasi Bangsa</div>
  </div>
</div>

<div class="footer">
  Dokumen ini di-generate otomatis oleh IDEA Portal. Confidential — internal use only.
</div>

</body></html>"""


async def generate_slip_pdf(
    session: AsyncSession,
    slip: PayrollSlip,
) -> str:
    """Generate PDF + upload ke MinIO. Returns object_name (MinIO key)."""
    # Fetch period + employee + components
    period = await session.get(PayrollPeriod, slip.period_id)
    if period is None:
        raise ValueError(f"Period {slip.period_id} not found")
    employee = await session.get(Employee, slip.employee_id)
    components = await list_components(session, slip.id)

    html = _build_html(slip, period, employee, list(components))
    # Lazy import — weasyprint butuh native libs (pango, glib).
    # Backend tetap bisa start tanpa libs ini; error muncul saat PDF generation.
    try:
        from weasyprint import HTML as _HTML
    except OSError as e:
        raise RuntimeError(
            f"WeasyPrint native libs missing. Install di macOS: 'brew install pango libffi'. "
            f"Detail: {e}"
        ) from e
    pdf_bytes = _HTML(string=html).write_pdf()

    object_name = f"payroll/{slip.period_id}/slip-{slip.slip_no}.pdf"
    upload_fileobj(
        BytesIO(pdf_bytes),
        object_name,
        content_type="application/pdf",
        length=len(pdf_bytes),
    )
    return object_name
