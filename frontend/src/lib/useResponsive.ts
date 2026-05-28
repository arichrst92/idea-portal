/**
 * useResponsive — hook untuk detect breakpoint changes via window.matchMedia.
 *
 * Breakpoints (sync dengan AntD default):
 * - mobile:  < 768px
 * - tablet:  768 - 1024px
 * - desktop: >= 1024px
 */

import { useEffect, useState } from 'react';

export type Breakpoint = 'mobile' | 'tablet' | 'desktop';

const MOBILE_MAX = 767;
const TABLET_MAX = 1023;

function computeBreakpoint(width: number): Breakpoint {
  if (width <= MOBILE_MAX) return 'mobile';
  if (width <= TABLET_MAX) return 'tablet';
  return 'desktop';
}

export function useResponsive() {
  const [breakpoint, setBreakpoint] = useState<Breakpoint>(() => {
    if (typeof window === 'undefined') return 'desktop';
    return computeBreakpoint(window.innerWidth);
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const onResize = () => setBreakpoint(computeBreakpoint(window.innerWidth));
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  return {
    breakpoint,
    isMobile: breakpoint === 'mobile',
    isTablet: breakpoint === 'tablet',
    isDesktop: breakpoint === 'desktop',
    isMobileOrTablet: breakpoint !== 'desktop',
  };
}
