import { useQuery } from "@tanstack/react-query";
import { BarChart3, ChevronDown } from "lucide-react";
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ErrorAlert, Loading, Notice } from "@/components/common";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ChartOrTable } from "@/features/analysis/charts";
import type { FilterValues } from "@/features/reports/ReportFilterField";
import { buildParams } from "@/features/reports/params";
import { api } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type {
  ReportChart,
  ReportCharts as ChartsData,
  ReportDefinition,
} from "@/types/api";

// Mismo orden de colores que el Excel y el PDF (tokens validados en claro y oscuro).
const COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];
const AXIS = "var(--muted-foreground)";
const tick = { fill: AXIS, fontSize: 12 };
const tooltipStyle = {
  labelStyle: { color: "var(--foreground)", fontWeight: 584 },
  itemStyle: { color: "var(--foreground)" },
  contentStyle: {
    background: "var(--popover)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    fontSize: 12,
    boxShadow: "var(--shadow)",
  },
};

function rowsOf(chart: ReportChart) {
  return chart.categories.map((x, i) =>
    Object.fromEntries([
      ["x", x],
      ...chart.series.map((s, j) => [`s${j}`, s.values[i]]),
    ]),
  );
}

function Plot({ chart }: { chart: ReportChart }) {
  const data = rowsOf(chart);
  const legend = chart.series.length > 1 && (
    <Legend wrapperStyle={{ fontSize: 12 }} />
  );
  const tooltip = (
    <Tooltip
      {...tooltipStyle}
      cursor={
        chart.kind === "bar"
          ? { fill: "var(--muted)" }
          : { stroke: "var(--border)" }
      }
      formatter={(value, name) => [
        value === null || value === undefined
          ? "Sin dato"
          : formatNumber(Number(value)),
        name,
      ]}
    />
  );
  const valueTick = (v: number) => formatNumber(v, 1);
  if (chart.kind === "line") {
    return (
      <ResponsiveContainer>
        <LineChart
          data={data}
          margin={{ top: 8, right: 12, bottom: 0, left: -8 }}
        >
          <CartesianGrid
            vertical={false}
            stroke="var(--grid)"
            strokeDasharray="3 5"
          />
          <XAxis
            dataKey="x"
            tick={tick}
            tickLine={false}
            axisLine={false}
            minTickGap={24}
          />
          <YAxis
            tick={tick}
            tickLine={false}
            axisLine={false}
            width={52}
            tickFormatter={valueTick}
          />
          {tooltip}
          {legend}
          {chart.series.map((s, j) => (
            <Line
              key={s.name}
              dataKey={`s${j}`}
              name={s.name}
              stroke={COLORS[j % COLORS.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5, stroke: "var(--card)", strokeWidth: 2 }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  }
  const horizontal = chart.horizontal;
  return (
    <ResponsiveContainer>
      <BarChart
        data={data}
        layout={horizontal ? "vertical" : "horizontal"}
        margin={{ top: 8, right: 12, bottom: 0, left: horizontal ? 8 : -8 }}
        barCategoryGap="22%"
      >
        <CartesianGrid
          vertical={horizontal}
          horizontal={!horizontal}
          stroke="var(--grid)"
          strokeDasharray="3 5"
        />
        {horizontal ? (
          <>
            <XAxis
              type="number"
              tick={tick}
              tickLine={false}
              axisLine={false}
              tickFormatter={valueTick}
            />
            <YAxis
              type="category"
              dataKey="x"
              tick={tick}
              tickLine={false}
              axisLine={false}
              width={170}
            />
          </>
        ) : (
          <>
            <XAxis
              dataKey="x"
              tick={tick}
              tickLine={false}
              axisLine={false}
              minTickGap={16}
            />
            <YAxis
              tick={tick}
              tickLine={false}
              axisLine={false}
              width={52}
              tickFormatter={valueTick}
            />
          </>
        )}
        {tooltip}
        {legend}
        {chart.series.map((s, j) => (
          <Bar
            key={s.name}
            dataKey={`s${j}`}
            name={s.name}
            fill={COLORS[j % COLORS.length]}
            radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]}
            maxBarSize={28}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

function DataTable({ chart }: { chart: ReportChart }) {
  return (
    <div className="max-h-72 overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Categoría</TableHead>
            {chart.series.map((s) => (
              <TableHead key={s.name} className="text-right">
                {s.name}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {chart.categories.map((c, i) => (
            <TableRow key={`${c}-${i}`}>
              <TableCell>{c}</TableCell>
              {chart.series.map((s) => (
                <TableCell key={s.name} className="text-right tabular-nums">
                  {formatNumber(s.values[i])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function Figure({ chart, number }: { chart: ReportChart; number: number }) {
  const wide = chart.kind === "line" || chart.categories.length > 14;
  const height = chart.horizontal
    ? Math.max(
        180,
        chart.categories.length * 30 * Math.max(1, chart.series.length * 0.7) +
          40,
      )
    : 288;
  return (
    <figure className={wide ? "grid gap-2 lg:col-span-2" : "grid gap-2"}>
      <figcaption className="text-sm">
        <span className="font-semibold">Figura {number}.</span>{" "}
        <span className="italic">{chart.title}</span>
      </figcaption>
      {chart.categories.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          Sin datos para graficar con los filtros seleccionados.
        </p>
      ) : (
        <ChartOrTable
          title={chart.title}
          chart={
            <div
              className="w-full"
              style={{ height }}
              role="img"
              aria-label={`${chart.title}; use «Ver tabla» para leer los valores`}
            >
              <Plot chart={chart} />
            </div>
          }
          table={<DataTable chart={chart} />}
        />
      )}
      {chart.unit && (
        <p className="text-muted-foreground text-xs">Unidad: {chart.unit}.</p>
      )}
    </figure>
  );
}

/**
 * Resumen y gráficos del reporte elegido con los filtros actuales. Los calcula el backend con las
 * mismas filas que exporta, así lo que se ve aquí coincide con el Excel y el PDF.
 */
export function ReportCharts({
  report,
  values,
}: {
  report: ReportDefinition;
  values: FilterValues;
}) {
  const [open, setOpen] = useState(true);
  const missing = report.filters.filter((f) => f.required && !values[f.key]);
  const badRange = Boolean(
    values.date_from && values.date_to && values.date_from >= values.date_to,
  );
  const { format: _format, ...params } = buildParams(report, values, "xlsx");
  const charts = useQuery({
    queryKey: ["reports", "charts", params],
    queryFn: async () =>
      (await api.get<ChartsData>("/reports/charts", { params })).data,
    enabled: open && missing.length === 0 && !badRange,
    placeholderData: (previous) => previous,
  });
  const data = charts.data;
  return (
    <Card className="mb-4" aria-labelledby="graficos-titulo">
      <CardContent className="grid gap-4">
        <h2 id="graficos-titulo" className="text-sm font-semibold">
          <button
            type="button"
            aria-expanded={open}
            aria-controls="graficos-cuerpo"
            onClick={() => setOpen(!open)}
            className="hover:text-foreground flex items-center gap-2 rounded-md text-left"
          >
            <BarChart3 className="size-4" aria-hidden /> Resumen y gráficos
            <span className="text-muted-foreground font-normal">
              · {report.label}
            </span>
            <ChevronDown
              className={`size-4 transition-transform ${open ? "rotate-180" : ""}`}
              aria-hidden
            />
          </button>
        </h2>
        <div id="graficos-cuerpo" hidden={!open} className="grid gap-4">
          {missing.length > 0 ? (
            <Notice tone="info">
              Para ver este reporte indique:{" "}
              {missing.map((f) => f.label.toLowerCase()).join(", ")}.
            </Notice>
          ) : (
            <>
              <ErrorAlert error={charts.error} />
              {charts.isLoading && <Loading />}
              {data && (
                <div
                  className={
                    charts.isFetching
                      ? "grid gap-4 opacity-60 transition-opacity"
                      : "grid gap-4"
                  }
                  aria-busy={charts.isFetching}
                >
                  <p className="text-muted-foreground text-xs">
                    {data.criteria.join(" · ")} · {data.rows} registro
                    {data.rows === 1 ? "" : "s"}. El Excel y el PDF incluyen
                    este mismo resumen y gráficos.
                  </p>
                  <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    {data.summary.map((item) => (
                      <div
                        key={item.label}
                        className="bg-muted/50 rounded-lg border px-3 py-2"
                      >
                        <dt className="text-muted-foreground text-xs">
                          {item.label}
                        </dt>
                        <dd className="text-lg font-semibold tabular-nums">
                          {item.value}
                        </dd>
                      </div>
                    ))}
                  </dl>
                  <div className="grid gap-6 lg:grid-cols-2">
                    {data.charts.map((chart, i) => (
                      <Figure key={chart.title} chart={chart} number={i + 1} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
