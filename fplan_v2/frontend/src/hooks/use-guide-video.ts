import { useState, useEffect } from 'react';
import { useDemoMode } from '@/contexts/demo-context';
import { useLocation } from 'react-router-dom';

const GUIDE_VIDEO_SEEN_KEY = 'guide-video-seen';

export function useGuideVideo() {
  const { isDemo } = useDemoMode();
  const location = useLocation();
  const [showGuide, setShowGuide] = useState(false);

  useEffect(() => {
    // Auto-show conditions:
    // 1. User is in demo mode (unauthenticated)
    // 2. On dashboard page (/)
    // 3. Haven't seen video before
    const hasSeenVideo = localStorage.getItem(GUIDE_VIDEO_SEEN_KEY) === '1';

    if (isDemo && location.pathname === '/' && !hasSeenVideo) {
      // Small delay to let page render
      const timer = setTimeout(() => setShowGuide(true), 2000);
      return () => clearTimeout(timer);
    }
  }, [isDemo, location.pathname]);

  return [showGuide, setShowGuide] as const;
}
