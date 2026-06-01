"""Offering Letter PDF generator — TSK-034 (US-OP-002 AC-04).

Generate offering letter PDF dari JobApplication + JobOpening:
- IDE Asia letterhead
- Candidate info (nama, kontak)
- Position offer detail: position name, level, dept, salary breakdown
- Start date + additional terms
- Acceptance / signature block

Upload ke MinIO: hiring/offer-letters/{application_id}.pdf

WeasyPrint lazy import (NC-DEV-007).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import upload_fileobj
from app.hiring.models import JobApplication, JobOpening
from app.organization.models import Department, Position

MONTHS_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def _fmt_idr(v: Decimal | float | None) -> str:
    if v is None:
        return "—"
    n = float(v)
    return f"Rp {n:,.0f}".replace(",", ".")


def _fmt_date_id(d: date | None) -> str:
    if d is None:
        return "—"
    return f"{d.day} {MONTHS_ID[d.month - 1]} {d.year}"


def _build_html(
    application: JobApplication,
    opening: JobOpening,
    position: Position | None,
    department: Department | None,
) -> str:
    today_str = date.today().strftime("%d %B %Y")
    candidate_name = application.candidate_name or "—"
    position_name = (position.name if position else opening.title) or "—"
    position_level = position.level if position else "—"
    dept_name = department.name if department else "—"

    salary = _fmt_idr(application.offered_salary)
    start_date_str = _fmt_date_id(application.offered_start_date)
    additional = (application.offer_additional_terms or "").strip()

    additional_block = ""
    if additional:
        additional_block = f"""
        <div class="section">
          <h3>Ketentuan Tambahan</h3>
          <div class="terms">{additional.replace(chr(10), "<br>")}</div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<title>Offering Letter — {candidate_name}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Helvetica', Arial, sans-serif; font-size: 11pt; color: #1d1d1f; padding: 32px; line-height: 1.5; }}
  .header {{ border-bottom: 3px solid #0071E3; padding-bottom: 14px; margin-bottom: 22px; }}
  .company {{ font-size: 18pt; font-weight: 800; color: #0071E3; }}
  .subtitle {{ font-size: 10pt; color: #6e6e73; margin-top: 2px; }}
  h1 {{ font-size: 16pt; margin: 16px 0 4px 0; text-align: center; letter-spacing: 1px; }}
  .ref-no {{ text-align: center; font-size: 11pt; color: #6e6e73; margin-bottom: 22px; }}
  .greeting {{ font-size: 11pt; margin-bottom: 14px; }}
  p.body-text {{ font-size: 11pt; margin: 10px 0; text-align: justify; }}
  .section {{ margin: 18px 0; }}
  .section h3 {{ font-size: 12pt; color: #0071E3; margin: 0 0 8px 0; padding-bottom: 4px; border-bottom: 1.5px solid #E8E8ED; }}
  table.offer-detail {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  table.offer-detail td {{ padding: 8px 12px; border-bottom: 1px solid #E8E8ED; font-size: 10.5pt; }}
  table.offer-detail td.label {{ width: 200px; color: #6e6e73; font-weight: 500; background: #F5F5F7; }}
  table.offer-detail td.value {{ font-weight: 700; }}
  .terms {{ background: #F5F5F7; padding: 12px 14px; border-radius: 6px; font-size: 10.5pt; }}
  .acceptance {{ background: rgba(0,113,227,0.05); border: 1.5px solid #0071E3;
                  padding: 16px; border-radius: 8px; margin-top: 22px; }}
  .acceptance h3 {{ color: #0071E3; border: none; margin-top: 0; }}
  .signature {{ margin-top: 28px; display: flex; justify-content: space-between; }}
  .sig-block {{ width: 240px; text-align: center; font-size: 10pt; }}
  .sig-line {{ border-top: 1.5px solid #1d1d1f; margin-top: 64px; padding-top: 4px; }}
  .sig-title {{ font-size: 9pt; color: #6e6e73; margin-bottom: 4px; font-weight: 600; }}
  .footer {{ margin-top: 36px; padding-top: 14px; border-top: 1px solid #E8E8ED;
            font-size: 8.5pt; color: #86868B; text-align: center; }}
</style>
</head>
<body>

<div class="header">
  <div class="company">PT. Solusi Inovasi Bangsa</div>
  <div class="subtitle">IDE Asia · IDEA Portal — Hiring &amp; Recruitment</div>
</div>

<h1>OFFERING LETTER</h1>
<div class="ref-no">Ref: <strong>OFR-{str(application.id)[:8].upper()}</strong> · Tanggal: {today_str}</div>

<div class="greeting">
  Kepada Yth.<br>
  <strong>{candidate_name}</strong><br>
  Di Tempat
</div>

<p class="body-text">
Dengan hormat,
</p>

<p class="body-text">
Berdasarkan hasil proses seleksi yang telah Anda jalani untuk posisi
<strong>{position_name}</strong> di PT. Solusi Inovasi Bangsa, dengan ini kami
dengan senang hati menawarkan kepada Anda untuk bergabung sebagai bagian dari tim
IDE Asia dengan rincian sebagai berikut:
</p>

<div class="section">
  <h3>Detail Penawaran</h3>
  <table class="offer-detail">
    <tr>
      <td class="label">Posisi</td>
      <td class="value">{position_name}</td>
    </tr>
    <tr>
      <td class="label">Level</td>
      <td class="value">Level {position_level}</td>
    </tr>
    <tr>
      <td class="label">Departemen</td>
      <td class="value">{dept_name}</td>
    </tr>
    <tr>
      <td class="label">Gaji Pokok</td>
      <td class="value" style="color:#0071E3;font-size:12pt">{salary} / bulan</td>
    </tr>
    <tr>
      <td class="label">Tanggal Mulai</td>
      <td class="value">{start_date_str}</td>
    </tr>
    <tr>
      <td class="label">Status Karyawan</td>
      <td class="value">Probation 3 (tiga) bulan</td>
    </tr>
  </table>
</div>

{additional_block}

<div class="section">
  <h3>Hak &amp; Kewajiban Karyawan</h3>
  <p class="body-text" style="font-size:10pt">
  Karyawan berhak atas: BPJS Kesehatan, BPJS Ketenagakerjaan, cuti tahunan
  sesuai ketentuan perusahaan, slip gaji bulanan via portal IDEA Internal,
  serta tunjangan lainnya yang akan disampaikan dalam onboarding.
  </p>
  <p class="body-text" style="font-size:10pt">
  Karyawan wajib menjaga kerahasiaan informasi perusahaan, mematuhi
  peraturan internal, dan menyelesaikan onboarding checklist dalam
  30 hari kerja pertama.
  </p>
</div>

<div class="acceptance">
  <h3>Konfirmasi Penerimaan</h3>
  <p style="margin:8px 0;font-size:10.5pt">
    Mohon Anda memberikan konfirmasi atas penawaran ini paling lambat
    <strong>7 (tujuh) hari kerja</strong> sejak surat ini diterima.
    Apabila tidak ada konfirmasi dalam jangka waktu tersebut, penawaran
    ini akan dianggap kadaluwarsa.
  </p>
  <p style="margin:8px 0;font-size:10.5pt">
    Konfirmasi dapat disampaikan melalui email
    <strong>hr@ide.asia</strong> atau membalas dokumen ini dengan tanda tangan.
  </p>
</div>

<div class="signature">
  <div class="sig-block">
    <div class="sig-title">IDE Asia</div>
    <div class="sig-line">HR / Operation</div>
  </div>
  <div class="sig-block">
    <div class="sig-title">Kandidat</div>
    <div class="sig-line">{candidate_name}</div>
  </div>
</div>

<div class="footer">
  PT. Solusi Inovasi Bangsa · portal.ide.asia · Confidential — Offering Letter
</div>

</body>
</html>
"""


async def generate_offer_pdf(
    session: AsyncSession, application_id: UUID
) -> str:
    """Generate offering letter PDF + upload ke MinIO. Returns presigned URL key.

    Lazy import WeasyPrint (NC-DEV-007).
    """
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise RuntimeError(
            "PDF generator butuh native libs. Install via: "
            "brew install pango glib cairo (macOS) atau apt install python3-cffi "
            "libpango-1.0-0 libpangoft2-1.0-0 (Linux)"
        ) from e

    # Fetch entities
    application = await session.get(JobApplication, application_id)
    if application is None:
        raise ValueError(f"JobApplication {application_id} not found")

    opening = await session.get(JobOpening, application.job_opening_id)
    if opening is None:
        raise ValueError(f"JobOpening {application.job_opening_id} not found")

    position = (
        await session.get(Position, opening.position_id) if opening.position_id else None
    )
    department = (
        await session.get(Department, opening.department_id)
        if opening.department_id
        else None
    )

    html_str = _build_html(application, opening, position, department)

    # Render PDF
    buf = BytesIO()
    HTML(string=html_str).write_pdf(buf)
    buf.seek(0)

    # Upload to MinIO
    object_key = f"hiring/offer-letters/{application_id}.pdf"
    upload_fileobj(
        buf,
        object_key=object_key,
        content_type="application/pdf",
    )

    return object_key
