"""Separation domain — TSK-017.

Lifecycle akhir employee:
- RESIGNATION: employee self-initiated
- LAYOFF: company-initiated (efisiensi/restrukturisasi)
- TERMINATION: disciplinary (triggered by SP3 chain)
- END_OF_CONTRACT: PKWT habis tanpa renewal
- RETIREMENT: usia pensiun

Workflow approval (2-layer per knowledge.md sec.5):
DRAFT → PENDING_APPROVAL_L1 (atasan langsung)
     → PENDING_APPROVAL_L2 (GM/C-Level/Executive)
     → APPROVED → EXECUTED (update employee.status + soft delete)
     → REJECTED / CANCELLED (kapan saja sebelum EXECUTED)
"""
