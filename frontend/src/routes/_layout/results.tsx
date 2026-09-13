import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense, useState } from "react"

import {
  ModelSummaryService,
  type TaskResultListItem,
  TaskResultsService,
} from "@/client"
import PendingItems from "@/components/Pending/PendingItems"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"

export const Route = createFileRoute("/_layout/results")({
  component: ResultsPage,
  head: () => ({ meta: [{ title: "结果查询" }] }),
})

function ResultDetailDrawer({
  resultId,
  onClose,
}: {
  resultId: number | null
  onClose: () => void
}) {
  const { data } = useQuery<any>({
    queryKey: ["task-result", resultId],
    queryFn: async (): Promise<any> =>
      await TaskResultsService.resultsReadTaskResult({
        path: { id: resultId! },
      }),
    enabled: resultId !== null,
  })
  const { data: series } = useQuery<any>({
    queryKey: ["return-series", resultId],
    queryFn: async (): Promise<any> =>
      await TaskResultsService.resultsReadReturnSeries({
        path: { id: resultId! },
      }),
    enabled: resultId !== null,
  })

  const points = series ?? []
  const max = Math.max(
    0,
    ...(points as any[]).map((p: any) => p.start_return ?? 0),
  )
  const min = Math.min(
    0,
    ...(points as any[]).map((p: any) => p.start_return ?? 0),
  )

  return (
    <Dialog
      open={resultId !== null}
      onOpenChange={(open) => !open && onClose()}
    >
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>结果详情 #{resultId}</DialogTitle>
        </DialogHeader>
        {data && (
          <div className="flex flex-col gap-3 text-sm">
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">{data.stock_code ?? "-"}</Badge>
              <Badge variant="outline">
                {data.model_name ?? data.model_key}
              </Badge>
              <Badge variant="outline">{data.period_key ?? "-"}</Badge>
              <Badge variant="outline">{data.kline_range ?? "-"}</Badge>
              {data.is_best && <Badge>best</Badge>}
            </div>
            <div className="rounded border p-2 text-xs">
              最优指标：{data.best_metric_name} ={" "}
              {data.best_metric_value ?? "-"}
            </div>
            {points.length > 0 && (
              <div className="rounded border p-2">
                <p className="mb-1 text-xs text-muted-foreground">
                  收益序列（{points.length}{" "}
                  点，简单条形图；图表库沿用模板依赖策略）
                </p>
                <div className="flex h-24 items-end gap-px">
                  {(points as any[]).map((p: any) => {
                    const value = p.start_return ?? 0
                    const height =
                      max === min ? 50 : ((value - min) / (max - min)) * 100
                    return (
                      <div
                        key={p.date}
                        className={
                          value >= 0 ? "bg-green-500/70" : "bg-red-500/70"
                        }
                        style={{ height: `${Math.max(height, 2)}%`, width: 4 }}
                        title={`${p.date}: ${value}`}
                      />
                    )
                  })}
                </div>
              </div>
            )}
            <details>
              <summary className="cursor-pointer text-xs text-muted-foreground">
                params / result JSON
              </summary>
              <pre className="mt-1 max-h-64 overflow-auto rounded bg-muted p-2 text-xs">
                {JSON.stringify(
                  { params: data.params, result: data.result },
                  null,
                  2,
                )}
              </pre>
            </details>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

function ResultsTableContent() {
  const [keyword, setKeyword] = useState("")
  const [search, setSearch] = useState("")
  const [selected, setSelected] = useState<number | null>(null)

  const { data } = useQuery<any>({
    queryKey: ["results", search],
    queryFn: async (): Promise<any> => {
      // global results: reuse model summary hot-column query for filtering
      const summary: any = await ModelSummaryService.summaryReadModelSummary({
        query: {
          skip: 0,
          limit: 100,
          stock_code: search || undefined,
          best_only: false,
        },
      })
      return summary.data
    },
    placeholderData: (prev: any) => prev,
  })

  const rows = (data?.data ?? []) as unknown as Array<
    TaskResultListItem & { result_id: number }
  >

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Input
          placeholder="按股票代码过滤"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") setSearch(keyword)
          }}
          className="max-w-xs"
        />
        <Button variant="secondary" onClick={() => setSearch(keyword)}>
          过滤
        </Button>
      </div>
      <div className="overflow-auto rounded-lg border">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="p-2">ID</th>
              <th className="p-2">任务</th>
              <th className="p-2">股票</th>
              <th className="p-2">模型</th>
              <th className="p-2">周期</th>
              <th className="p-2">最优</th>
              <th className="p-2">Best</th>
              <th className="p-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.result_id ?? r.id} className="border-b">
                <td className="p-2">{r.result_id ?? r.id}</td>
                <td className="p-2">{r.task_id}</td>
                <td className="p-2">{r.stock_code ?? "-"}</td>
                <td className="p-2">{r.model_name ?? r.model_key}</td>
                <td className="p-2">{r.period_key ?? "-"}</td>
                <td className="p-2">
                  {r.best_metric_name}: {r.best_metric_value ?? "-"}
                </td>
                <td className="p-2">{r.is_best ? "✓" : ""}</td>
                <td className="p-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setSelected(r.result_id ?? r.id)}
                  >
                    详情
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && (
          <p className="py-8 text-center text-muted-foreground">暂无结果</p>
        )}
      </div>
      <ResultDetailDrawer
        resultId={selected}
        onClose={() => setSelected(null)}
      />
      {null}
    </div>
  )
}

function ResultsPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">结果查询</h1>
        <p className="text-muted-foreground">
          全局结果检索（热列直查；详情抽屉懒加载完整 JSON 与收益序列）
        </p>
      </div>
      <Suspense fallback={<PendingItems />}>
        <ResultsTableContent />
      </Suspense>
    </div>
  )
}
