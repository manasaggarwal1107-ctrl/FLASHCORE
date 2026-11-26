/** Recharts can't read Tailwind classes; these resolve the same CSS tokens at runtime. */
export const chartColors = {
  accent: 'rgb(var(--accent))',
  brand: 'rgb(var(--brand))',
  success: 'rgb(var(--success))',
  warning: 'rgb(var(--warning))',
  danger: 'rgb(var(--danger))',
  simulation: 'rgb(var(--simulation))',
  grid: 'rgb(var(--line))',
  axis: 'rgb(var(--ink-faint))',
  tooltipBg: 'rgb(var(--surface-3))',
  tooltipBorder: 'rgb(var(--line-strong))',
  text: 'rgb(var(--ink))',
} as const;

export const axisProps = {
  stroke: chartColors.axis,
  tick: { fill: chartColors.axis, fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: chartColors.grid },
} as const;

export const tooltipStyle = {
  contentStyle: {
    background: chartColors.tooltipBg,
    border: `1px solid ${chartColors.tooltipBorder}`,
    borderRadius: 4,
    fontSize: 12,
    color: chartColors.text,
  },
  labelStyle: { color: chartColors.text, fontWeight: 600 },
  itemStyle: { color: chartColors.text },
  cursor: { stroke: chartColors.grid },
} as const;
