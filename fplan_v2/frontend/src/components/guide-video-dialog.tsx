import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';

const GUIDE_VIDEO_SEEN_KEY = 'guide-video-seen';

interface GuideVideoDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function GuideVideoDialog({ open, onOpenChange }: GuideVideoDialogProps) {
  const { t } = useTranslation();
  const [dontShowAgain, setDontShowAgain] = useState(false);
  const [loading, setLoading] = useState(true);

  const handleClose = () => {
    if (dontShowAgain) {
      localStorage.setItem(GUIDE_VIDEO_SEEN_KEY, '1');
    }
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl w-[95vw] max-h-[90vh] overflow-auto">
        <DialogHeader>
          <DialogTitle>{t('guide.title')}</DialogTitle>
        </DialogHeader>

        <div className="aspect-video w-full bg-muted rounded-lg overflow-hidden relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <p className="text-muted-foreground">{t('guide.loading')}</p>
            </div>
          )}
          <video
            src="/guide-video.mp4"
            controls
            preload="metadata"
            playsInline
            className="w-full h-full"
            onLoadedData={() => setLoading(false)}
            onError={() => {
              toast.error(t('guide.error_loading'));
              onOpenChange(false);
            }}
          />
        </div>

        <div className="flex items-center gap-2 pt-2">
          <Checkbox
            id="dont-show"
            checked={dontShowAgain}
            onCheckedChange={(checked) => setDontShowAgain(!!checked)}
          />
          <label
            htmlFor="dont-show"
            className="text-sm cursor-pointer select-none"
          >
            {t('guide.dont_show_again')}
          </label>
        </div>
      </DialogContent>
    </Dialog>
  );
}
