import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { axisProps, chartColors, tooltipStyle } from './chartTheme';

export interface TimePoint {
  /** ISO timestamp or label */
  t: string;
  value: number;
}

/** Renders only supplied points. With an empty array the caller must show an empty state instead. */
export function TimeSeriesChart({
  data,
  seriesLabel,
  color = 'accent',
  height = 220,
  formatValue = (v: number) => String(v),
}: {
  data: TimePoint[];
  seriesLabel: string;
  color?: 'accent' | 'brand' | 'success' | 'danger' | 'simulation';
  height?: number;
  formatValue?: (v: number) => string;
}) {
  const stroke = chartColors[color];
  const gradientId = `grad-${color}`;
  return (
    <div role="img" aria-label={`${seriesLabel} over time chart`} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity={0.22} />
              <stop offset="100%" stopColor={stroke} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={chartColors.grid} strokeDasharray="2 4" vertical={false} />
          <XAxis dataKey="t" {...axisProps} minTickGap={32} />
          <YAxis {...axisProps} width={48} tickFormatter={formatValue} />
          <Tooltip {...tooltipStyle} formatter={(v: number) => [formatValue(v), seriesLabel]} />
          <Area type="monotone" dataKey="value" stroke={stroke} strokeWidth={1.75} fill={`url(#${gradientId})`} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
