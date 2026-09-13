import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/performance-analysis")({
  component: PerformanceAnalysisPage,
  head: () => ({ meta: [{ title: "性能分析" }] }),
})

function PerformanceAnalysisPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">性能分析</h1>
        <p className="text-muted-foreground">
          收益序列分析与权重组合（NDJSON 流式 + 虚拟滚动大表）
        </p>
      </div>
      <div className="rounded-lg border border-dashed p-8 text-center">
        <p className="font-medium">分析引擎移植中（P6 联调）</p>
        <p className="mt-2 text-sm text-muted-foreground">
          本页对应 API
          <code className="mx-1 rounded bg-muted px-1">
            POST /api/v1/performance-analysis/v1/analyze
          </code>
          （NDJSON 流式）与
          <code className="mx-1 rounded bg-muted px-1">
            /v1/weight-combination
          </code>
          （十万行权重组合，TanStack Virtual 虚拟化渲染）。当前后端返回
          501，引擎包随 P6 联调上线后自动可用。
        </p>
        <ul className="mx-auto mt-4 max-w-md space-y-1 text-left text-sm text-muted-foreground">
          <li>
            · 流式消费：fetch + ReadableStream 逐行
            JSON.parse（NdjsonStreamConsumer）
          </li>
          <li>
            · 权重组合：分块 append + 行虚拟化（旧版实测 10 万行 DOM 渲染
            5-10s）
          </li>
        </ul>
      </div>
    </div>
  )
}
