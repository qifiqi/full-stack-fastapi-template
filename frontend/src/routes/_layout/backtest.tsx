import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { BacktestService, GlobalPreviewService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useCustomToast from "@/hooks/useCustomToast"

export const Route = createFileRoute("/_layout/backtest")({
  component: BacktestPage,
  head: () => ({ meta: [{ title: "回测域" }] }),
})

function SummaryPanel() {
  const [taskId, setTaskId] = useState("")
  const [submittedId, setSubmittedId] = useState<number | null>(null)
  const { showErrorToast } = useCustomToast()

  const { data, error } = useQuery<any>({
    queryKey: ["backtest-summary", submittedId],
    queryFn: async (): Promise<any> =>
      await BacktestService.readBacktestSummary({
        path: { task_id: submittedId! },
      }),
    enabled: submittedId !== null,
    retry: false,
  })
  if (error) {
    showErrorToast("任务不存在或无回测数据")
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <input
          className="h-9 max-w-xs rounded-md border px-3 text-sm"
          placeholder="回测任务 ID"
          value={taskId}
          onChange={(e) => setTaskId(e.target.value)}
        />
        <Button
          onClick={() => {
            const id = Number(taskId)
            if (Number.isFinite(id) && id > 0) setSubmittedId(id)
          }}
        >
          查询任务级汇总
        </Button>
      </div>
      {data && (
        <div className="rounded-lg border p-4">
          <div className="mb-2 flex gap-2 text-sm">
            <Badge variant="outline">{data.task_type}</Badge>
            <span>
              共 {data.total} 条 / 成功 {data.success_count} / 失败{" "}
              {data.failed_count}
            </span>
          </div>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b">
                <th className="p-2">股票</th>
                <th className="p-2">模型</th>
                <th className="p-2">周期</th>
                <th className="p-2">最优指标</th>
              </tr>
            </thead>
            <tbody>
              {(data.best as any[]).map((b: any) => (
                <tr key={b.result_id} className="border-b">
                  <td className="p-2">{b.stock_code ?? "-"}</td>
                  <td className="p-2">{b.model_key}</td>
                  <td className="p-2">{b.period_key ?? "-"}</td>
                  <td className="p-2">
                    {b.best_metric_name}: {b.best_metric_value ?? "-"}
                  </td>
                </tr>
              ))}
              {data.best.length === 0 && (
                <tr>
                  <td
                    colSpan={4}
                    className="p-4 text-center text-muted-foreground"
                  >
                    暂无 best 结果
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function PreviewPanel() {
  const [taskId, setTaskId] = useState("")
  const [submittedId, setSubmittedId] = useState<number | null>(null)
  const { data } = useQuery<any>({
    queryKey: ["global-preview", submittedId],
    queryFn: async (): Promise<any> =>
      await GlobalPreviewService.previewReadGlobalPreview({
        path: { task_id: submittedId! },
        query: { best_only: true },
      }),
    enabled: submittedId !== null,
  })

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <input
          className="h-9 max-w-xs rounded-md border px-3 text-sm"
          placeholder="任务 ID"
          value={taskId}
          onChange={(e) => setTaskId(e.target.value)}
        />
        <Button
          onClick={() => {
            const id = Number(taskId)
            if (Number.isFinite(id) && id > 0) setSubmittedId(id)
          }}
        >
          查看全局预览（best 分组）
        </Button>
      </div>
      {data && (
        <div className="flex flex-col gap-3">
          {(Object.entries(data.groups ?? {}) as [string, any[]][]).map(
            ([key, rows]) => (
              <div key={key} className="rounded-lg border p-3">
                <p className="mb-2 font-mono text-xs text-muted-foreground">
                  {key}
                </p>
                <table className="w-full text-left text-sm">
                  <tbody>
                    {(rows ?? []).map((row: any) => (
                      <tr
                        key={row.result_id}
                        className="border-b last:border-0"
                      >
                        <td className="p-1">{row.stock_name ?? "-"}</td>
                        <td className="p-1">{row.period_key ?? "-"}</td>
                        <td className="p-1">
                          {row.best_metric_name}: {row.best_metric_value ?? "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ),
          )}
        </div>
      )}
    </div>
  )
}

function BacktestPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          回测域（训练 / 多产品）
        </h1>
        <p className="text-muted-foreground">
          两域共用视图：任务级汇总（热列直查）与全局预览分组；Excel/Word 导出在
          P6 联调
        </p>
      </div>
      <Tabs defaultValue="summary" className="gap-4">
        <TabsList>
          <TabsTrigger value="summary">任务汇总</TabsTrigger>
          <TabsTrigger value="preview">全局预览</TabsTrigger>
        </TabsList>
        <TabsContent value="summary">
          <SummaryPanel />
        </TabsContent>
        <TabsContent value="preview">
          <PreviewPanel />
        </TabsContent>
      </Tabs>
    </div>
  )
}
