/**
 * Persona helpers — TSK-201.
 *
 * Per NC-EX-005: Wakil Direktur Utama = role terpisah dari Direktur Utama
 * dengan permission identik. UI dan audit log WAJIB display persona name
 * eksplisit ('Siti Hartono (Wakil Direktur Utama)') BUKAN generic 'Direktur'.
 *
 * Mirror backend app/identity/service.get_persona_name.
 */

import type { Role, User } from '@/api/auth';

/** Pick top role dengan Wakil Direktur prioritized eksplisit. */
export function getTopRole(user: User | null | undefined): Role | null {
  if (!user || user.roles.length === 0) return null;
  // Wakil Direktur explicit priority for clarity
  const wakil = user.roles.find((r) => r.code === 'WAKIL_DIREKTUR_UTAMA');
  if (wakil) return wakil;
  // Otherwise lowest level (more senior) wins
  return [...user.roles].sort((a, b) => a.level - b.level)[0];
}

/** Format: "Nama (Role)" atau fallback ke NIK. */
export function getPersonaLabel(user: User | null | undefined): string {
  if (!user) return '—';
  const role = getTopRole(user);
  return role ? `${user.nik} (${role.name})` : user.nik;
}

/** Apakah user adalah eksekutif (Direktur Utama atau Wakil)? */
export function isExecutiveRole(user: User | null | undefined): boolean {
  if (!user) return false;
  return user.roles.some(
    (r) => r.code === 'DIREKTUR_UTAMA' || r.code === 'WAKIL_DIREKTUR_UTAMA',
  );
}

/** Khusus Wakil Direktur — untuk membedakan styling Crown icon. */
export function isWakilDirektur(user: User | null | undefined): boolean {
  if (!user) return false;
  return user.roles.some((r) => r.code === 'WAKIL_DIREKTUR_UTAMA');
}

/** Khusus Direktur Utama (bukan Wakil). */
export function isDirekturUtama(user: User | null | undefined): boolean {
  if (!user) return false;
  return user.roles.some((r) => r.code === 'DIREKTUR_UTAMA');
}

/** Color hint untuk avatar / crown — beda warna Direktur vs Wakil. */
export function executiveColor(user: User | null | undefined): string {
  if (isWakilDirektur(user)) return 'var(--ide-teal, #32ADE6)'; // Teal untuk Wakil
  if (isDirekturUtama(user)) return 'var(--ide-purple, #AF52DE)'; // Purple untuk Direktur
  return 'var(--ide-blue, #0071E3)';
}
