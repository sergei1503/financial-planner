import { useState } from 'react';
import type { ReactNode } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

export interface Column<T> {
  header: string;
  accessor: keyof T | ((row: T) => ReactNode);
  sortable?: boolean;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (row: T) => string | number;
  actions?: (row: T) => ReactNode;
  actionsHeader?: string;
}

export function DataTable<T>({ columns, data, keyExtractor, actions, actionsHeader }: DataTableProps<T>) {
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const handleSort = (idx: number) => {
    if (sortCol === idx) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortCol(idx);
      setSortDir('asc');
    }
  };

  const sorted = [...data].sort((a, b) => {
    if (sortCol === null) return 0;
    const col = columns[sortCol];
    if (typeof col.accessor === 'function') return 0;
    const av = a[col.accessor];
    const bv = b[col.accessor];
    if (av == null || bv == null) return 0;
    const cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return sortDir === 'asc' ? cmp : -cmp;
  });

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {columns.map((col, idx) => (
            <TableHead
              key={idx}
              className={`${col.className || ''} ${col.sortable ? 'cursor-pointer select-none' : ''}`}
              onClick={() => col.sortable && handleSort(idx)}
            >
              {col.header}
              {sortCol === idx && (sortDir === 'asc' ? ' \u2191' : ' \u2193')}
            </TableHead>
          ))}
          {actions && <TableHead>{actionsHeader || ''}</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((row) => (
          <TableRow key={keyExtractor(row)}>
            {columns.map((col, idx) => (
              <TableCell key={idx} className={col.className}>
                {typeof col.accessor === 'function'
                  ? col.accessor(row)
                  : String(row[col.accessor] ?? '')}
              </TableCell>
            ))}
            {actions && <TableCell>{actions(row)}</TableCell>}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
