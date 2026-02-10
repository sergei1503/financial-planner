import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FlaskConical, Plus, Pencil, Trash2, X, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
import type { ProjectionResponse, ScenarioResponse } from '@/api/types';
import { useScenarios, useDeleteScenario, useRunScenario } from '@/hooks/use-scenarios';
import { ScenarioBuilder } from './scenario-builder';

const NONE_VALUE = '__none__';

interface ScenarioPanelProps {
  onScenarioProjection: (data: ProjectionResponse | undefined, name?: string) => void;
}

export function ScenarioPanel({ onScenarioProjection }: ScenarioPanelProps) {
  const { t } = useTranslation();
  const { data: scenarios } = useScenarios();
  const deleteMutation = useDeleteScenario();
  const runMutation = useRunScenario();

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [builderOpen, setBuilderOpen] = useState(false);
  const [editScenario, setEditScenario] = useState<ScenarioResponse | undefined>(undefined);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);

  const selectedScenario = scenarios?.find((s) => s.id === selectedId);

  const handleSelect = (value: string) => {
    if (value === NONE_VALUE) {
      setSelectedId(null);
      onScenarioProjection(undefined);
      return;
    }
    const id = Number(value);
    setSelectedId(id);
    const scenario = scenarios?.find((s) => s.id === id);
    runMutation.mutate(
      { id },
      {
        onSuccess: (data) => onScenarioProjection(data, scenario?.name),
        onError: () => {
          toast.error(t('messages.error_loading'));
        },
      },
    );
  };

  const handleClear = () => {
    setSelectedId(null);
    onScenarioProjection(undefined);
  };

  const handleNewScenario = () => {
    setEditScenario(undefined);
    setBuilderOpen(true);
  };

  const handleEditScenario = () => {
    if (selectedScenario) {
      setEditScenario(selectedScenario);
      setBuilderOpen(true);
    }
  };

  const handleDeleteConfirm = async () => {
    if (deleteConfirmId === null) return;
    try {
      await deleteMutation.mutateAsync(deleteConfirmId);
      if (selectedId === deleteConfirmId) {
        setSelectedId(null);
        onScenarioProjection(undefined);
      }
      toast.success(t('scenarios.deleted'));
    } catch {
      toast.error(t('messages.error_saving'));
    }
    setDeleteConfirmId(null);
  };

  const handleBuilderClose = (open: boolean) => {
    setBuilderOpen(open);
    if (!open) {
      setEditScenario(undefined);
    }
  };

  return (
    <>
      <Card className="mb-6" data-testid="scenario-panel">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="size-5" />
            {t('scenarios.title')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-3">
            <Select
              onValueChange={handleSelect}
              value={selectedId?.toString() ?? NONE_VALUE}
            >
              <SelectTrigger className="w-64" data-testid="scenario-select">
                <SelectValue placeholder={t('scenarios.select')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE_VALUE}>{t('scenarios.none')}</SelectItem>
                {scenarios?.map((s) => (
                  <SelectItem key={s.id} value={s.id.toString()}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button
              variant="secondary"
              onClick={handleNewScenario}
              data-testid="scenario-create-button"
            >
              <Plus className="size-4 me-2" />
              {t('scenarios.create')}
            </Button>

            {selectedScenario && (
              <>
                <Badge variant="outline" className="flex items-center gap-2">
                  {selectedScenario.name}
                  <span className="text-muted-foreground">
                    {t('scenarios.actions_count', { count: selectedScenario.actions.length })}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-4 w-4 p-0"
                    onClick={handleClear}
                  >
                    <X className="size-3" />
                  </Button>
                </Badge>

                <Button variant="ghost" size="sm" onClick={handleEditScenario}>
                  <Pencil className="size-4 me-1" />
                  {t('actions.edit')}
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive"
                  onClick={() => setDeleteConfirmId(selectedScenario.id)}
                >
                  <Trash2 className="size-4 me-1" />
                  {t('actions.delete')}
                </Button>
              </>
            )}

            {runMutation.isPending && (
              <span className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                {t('scenarios.running')}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      <ScenarioBuilder
        open={builderOpen}
        onOpenChange={handleBuilderClose}
        scenario={editScenario}
      />

      <AlertDialog open={deleteConfirmId !== null} onOpenChange={(open) => !open && setDeleteConfirmId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('scenarios.delete')}</AlertDialogTitle>
            <AlertDialogDescription>{t('messages.confirm_delete')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('actions.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteConfirm}>
              {t('actions.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
