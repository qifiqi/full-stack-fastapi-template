import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { ModelSummaryService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import useCustomToast from "@/hooks/useCustomToast"

export const Route = createFileRoute("/_layout/model-summary")({
  component: ModelSummaryPage,
  head: () => ({ meta: [{ title: "模型汇总" }] }),
})

function ModelSummaryPage() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [bestOnly, setBestOnly] = useState(true)
  const [stockCode, setStockCode] = useState("")
  const [search, setSearch] = useState("")

  const { data } = useQuery<any>({
    queryKey: ["model-summary", bestOnly, search],
    queryFn: async (): Promise<any> =>
      await ModelSummaryService.summaryReadModelSummary({
        query: {
          skip: 0,
          limit: 200,
          best_only: bestOnly,
          stock_code: search || undefined,
        },
      }),
  })
  const { data: status } = useQuery<any>({
    queryKey: ["model-summary-rebuild-status"],
    queryFn: async () =>
      (await ModelSummaryService.summaryRebuildStatus()) as any,
    refetchInterval: 5000,
  })

  const rebuild = useMutation({
    mutationFn: async (): Promise<any> =>
      await ModelSummaryService.summaryRebuildModelSummary({
        body: { all: true },
      }),
    onSuccess: () => {
      showSuccessToast("回填已执行完成")
      queryClient.invalidateQueries({ queryKey: ["model-summary"] })
      queryClient.invalidateQueries({
        queryKey: ["model-summary-rebuild-status"],
      })
    },
    onError: (err: any) =>
      showErrorToast(String(err?.body?.detail ?? "回填失败")),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">模型汇总</h1>
          <p className="text-muted-foreground">
            最优结果网格（is_best 热列直查，无全表扫描）
          </p>
        </div>
        <div className="flex items-center gap-3">
          {status && (
            <Badge
              variant={status.state === "running" ? "secondary" : "outline"}
            >
              回填: {status.state}
            </Badge>
          )}
          <Button
            disabled={rebuild.isPending || status?.state === "running"}
            onClick={() => rebuild.mutate()}
          >
            全量回填热列
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <label
          htmlFor="best-only-toggle"
          className="flex items-center gap-2 text-sm"
        >
          <Checkbox
            id="best-only-toggle"
            checked={bestOnly}
            onCheckedChange={(v) => setBestOnly(v === true)}
          />
          仅看最优（best_only）
        </label>
        <Input
          placeholder="股票代码"
          value={stockCode}
          onChange={(e) => setStockCode(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") setSearch(stockCode)
          }}
          className="max-w-48"
        />
        <Button variant="secondary" onClick={() => setSearch(stockCode)}>
          过滤
        </Button>
      </div>

      <div className="overflow-auto rounded-lg border">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="p-2">任务</th>
              <th className="p-2">股票</th>
              <th className="p-2">模型</th>
              <th className="p-2">周期</th>
              <th className="p-2">K线区间</th>
              <th className="p-2">最优指标</th>
              <th className="p-2">Best</th>
              <th className="p-2">时间</th>
            </tr>
          </thead>
          <tbody>
            {((data?.data ?? []) as any[]).map((r: any) => (
              <tr key={r.id} className="border-b">
                <td className="p-2">{r.task_id}</td>
                <td className="p-2">
                  {r.stock_code ?? "-"}
                  {r.stock_name ? ` (${r.stock_name})` : ""}
                </td>
                <td className="p-2">{r.model_name ?? r.model_key}</td>
                <td className="p-2">{r.period_key ?? "-"}</td>
                <td className="p-2 text-xs">{r.kline_range ?? "-"}</td>
                <td className="p-2">
                  {r.best_metric_name}: {r.best_metric_value ?? "-"}
                </td>
                <td className="p-2">{r.is_best ? "✓" : ""}</td>
                <td className="p-2 text-xs">
                  {r.result_timestamp
                    ? new Date(r.result_timestamp).toLocaleString()
                    : "-"}
                </td>
              </tr>
            ))}
            {(data?.data ?? []).length === 0 && (
              <tr>
                <td
                  colSpan={8}
                  className="p-6 text-center text-muted-foreground"
                >
                  暂无汇总数据（任务执行后由写入路径自动抽取热列）
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
