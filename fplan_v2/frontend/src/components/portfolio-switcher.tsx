import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Briefcase,
  Check,
  ChevronDown,
  Download,
  Pencil,
  Plus,
  Star,
  Trash2,
  Upload,
} from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

import { usePortfolioContext } from '@/contexts/portfolio-context';
import {
  useCreatePortfolio,
  useDeletePortfolio,
  useImportPortfolio,
  useRenamePortfolio,
  useSetDefaultPortfolio,
} from '@/hooks/use-portfolios';
import { portfoliosApi } from '@/api/portfolios';

export function PortfolioSwitcher() {
  const { t } = useTranslation();
  const { portfolios, activeId, activePortfolio, isLoading, switchPortfolio } =
    usePortfolioContext();

  const createMutation = useCreatePortfolio();
  const renameMutation = useRenamePortfolio();
  const deleteMutation = useDeletePortfolio();
  const setDefaultMutation = useSetDefaultPortfolio();
  const importMutation = useImportPortfolio();

  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState('');
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameName, setRenameName] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const errMessage = (e: unknown, fallback?: string) =>
    (e as { message?: string })?.message || fallback || t('portfolio.action_failed');

  const submitCreate = async () => {
    const name = createName.trim();
    if (!name) return;
    try {
      const created = await createMutation.mutateAsync(name);
      setCreateOpen(false);
      setCreateName('');
      toast.success(t('portfolio.created'));
      switchPortfolio(created.id);
    } catch (e) {
      toast.error(errMessage(e));
    }
  };

  const submitRename = async () => {
    const name = renameName.trim();
    if (!name || !activePortfolio) return;
    try {
      await renameMutation.mutateAsync({ id: activePortfolio.id, name });
      setRenameOpen(false);
      toast.success(t('portfolio.renamed'));
    } catch (e) {
      toast.error(errMessage(e));
    }
  };

  const handleSetDefault = async () => {
    if (!activePortfolio) return;
    try {
      await setDefaultMutation.mutateAsync(activePortfolio.id);
      toast.success(t('portfolio.default_set'));
    } catch (e) {
      toast.error(errMessage(e));
    }
  };

  const handleExport = async () => {
    if (!activePortfolio) return;
    try {
      const doc = await portfoliosApi.export(activePortfolio.id);
      const blob = new Blob([JSON.stringify(doc, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${activePortfolio.name.replace(/\s+/g, '_') || 'portfolio'}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success(t('portfolio.exported'));
    } catch (e) {
      toast.error(errMessage(e));
    }
  };

  const onFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-importing the same file
    if (!file) return;
    try {
      const created = await importMutation.mutateAsync(file);
      toast.success(t('portfolio.imported', { name: created.name }));
      switchPortfolio(created.id);
    } catch (err) {
      toast.error(errMessage(err, t('portfolio.import_failed')));
    }
  };

  const confirmDelete = async () => {
    if (!activePortfolio) return;
    try {
      await deleteMutation.mutateAsync(activePortfolio.id);
      setDeleteOpen(false);
      toast.success(t('portfolio.deleted'));
      // PortfolioProvider notices the active id is gone and falls back to the default.
    } catch (e) {
      toast.error(errMessage(e));
    }
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            disabled={isLoading}
            className="max-w-[220px] gap-2"
            aria-label={t('portfolio.switch')}
          >
            <Briefcase className="size-4 shrink-0" />
            <span className="truncate">
              {activePortfolio?.name ?? t('portfolio.label')}
            </span>
            <ChevronDown className="size-4 shrink-0 opacity-60" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-64">
          <DropdownMenuLabel>{t('portfolio.label')}</DropdownMenuLabel>
          {portfolios.map(p => (
            <DropdownMenuItem
              key={p.id}
              onSelect={() => switchPortfolio(p.id)}
              className="gap-2"
            >
              <Check
                className={cn(
                  'size-4 shrink-0',
                  p.id === activeId ? 'opacity-100' : 'opacity-0'
                )}
              />
              <span className="flex-1 truncate">{p.name}</span>
              {p.is_default && (
                <span className="text-xs text-muted-foreground">
                  {t('portfolio.default_badge')}
                </span>
              )}
            </DropdownMenuItem>
          ))}

          <DropdownMenuSeparator />

          <DropdownMenuItem onSelect={() => setCreateOpen(true)} className="gap-2">
            <Plus className="size-4" />
            {t('portfolio.new')}
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => {
              setRenameName(activePortfolio?.name ?? '');
              setRenameOpen(true);
            }}
            disabled={!activePortfolio}
            className="gap-2"
          >
            <Pencil className="size-4" />
            {t('portfolio.rename')}
          </DropdownMenuItem>
          {activePortfolio && !activePortfolio.is_default && (
            <DropdownMenuItem onSelect={handleSetDefault} className="gap-2">
              <Star className="size-4" />
              {t('portfolio.set_default')}
            </DropdownMenuItem>
          )}
          <DropdownMenuItem onSelect={handleExport} disabled={!activePortfolio} className="gap-2">
            <Download className="size-4" />
            {t('portfolio.export')}
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => fileInputRef.current?.click()}
            className="gap-2"
          >
            <Upload className="size-4" />
            {t('portfolio.import')}
          </DropdownMenuItem>
          {portfolios.length > 1 && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={() => setDeleteOpen(true)}
                className="gap-2 text-destructive focus:text-destructive"
              >
                <Trash2 className="size-4" />
                {t('portfolio.delete')}
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      <input
        ref={fileInputRef}
        type="file"
        accept="application/json,.json"
        className="hidden"
        onChange={onFileChange}
      />

      {/* Create */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('portfolio.create_title')}</DialogTitle>
            <DialogDescription>{t('portfolio.create_desc')}</DialogDescription>
          </DialogHeader>
          <form
            onSubmit={e => {
              e.preventDefault();
              submitCreate();
            }}
            className="space-y-4"
          >
            <div className="space-y-2">
              <Label htmlFor="pf-create-name">{t('portfolio.name_label')}</Label>
              <Input
                id="pf-create-name"
                value={createName}
                onChange={e => setCreateName(e.target.value)}
                placeholder={t('portfolio.name_placeholder')}
                autoFocus
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
                {t('portfolio.cancel')}
              </Button>
              <Button type="submit" disabled={!createName.trim() || createMutation.isPending}>
                {t('portfolio.create_submit')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Rename */}
      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('portfolio.rename_title')}</DialogTitle>
            <DialogDescription>{t('portfolio.rename_desc')}</DialogDescription>
          </DialogHeader>
          <form
            onSubmit={e => {
              e.preventDefault();
              submitRename();
            }}
            className="space-y-4"
          >
            <div className="space-y-2">
              <Label htmlFor="pf-rename-name">{t('portfolio.name_label')}</Label>
              <Input
                id="pf-rename-name"
                value={renameName}
                onChange={e => setRenameName(e.target.value)}
                placeholder={t('portfolio.name_placeholder')}
                autoFocus
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setRenameOpen(false)}>
                {t('portfolio.cancel')}
              </Button>
              <Button type="submit" disabled={!renameName.trim() || renameMutation.isPending}>
                {t('portfolio.save')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('portfolio.delete_confirm_title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('portfolio.delete_confirm_body', { name: activePortfolio?.name ?? '' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('portfolio.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {t('actions.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
