"""Onboarding domain — TSK-016.

Pattern:
- OnboardingTemplate: blueprint checklist per dept/level (mis. "Engineer Onboarding")
- OnboardingTask: item dalam template (HR docs, IT setup, dept-specific tasks)
- OnboardingAssignment: instance template di-assign ke karyawan baru
- TaskCompletion: status per task per assignment (PENDING → DONE/SKIPPED/BLOCKED)

Per knowledge.md sec.6 (hiring & onboarding lifecycle).
"""
