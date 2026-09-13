import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Suspense, useState } from "react"

import { TaskResultsService, TasksService } from "@/client"
import { StatusBadge } from "@/components/Migration/StatusBadge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export const Route = createFileRoute("/_layout/tasks/$taskId")({
  component: TaskDetailPage,
  head: () => ({ meta: [{ title: "任务详情" }] }),
})

function OverviewPanel({ taskId }: { taskId: string }) {
  const id = Number(taskId)
  const { data: task } = useQuery<any>({
    queryKey: ["task", id],
    queryFn: async (): Promise<any> =>
      await TasksService.readTask({ path: { id } }),
  })
  const { data: check } = useQuery<any>({
    queryKey: ["task-status-check", id],
    queryFn: async (): Promise<any> =>
      await TasksService.readTaskStatusCheck({ path: { id } }),
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? 10_000 : false,
  })

  if (!task || !check) return null
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="rounded-lg border p-4">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold">{task.name}</h3>
          <StatusBadge status={task.status} />
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {task.description ?? "-"}
        </p>
        <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
          <div>
            <dt className="text-muted-foreground">类型</dt>
            <dd>{task.task_type}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">股票</dt>
            <dd>{task.stock_code ?? "-"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Sheet</dt>
            <dd>{task.spreadsheet_id ?? "-"}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">进度</dt>
            <dd>
              {check.current_step}/{check.total_steps}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">心跳</dt>
            <dd>
              {check.heartbeat_at
                ? new Date(check.heartbeat_at).toLocaleTimeString()
                : "-"}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">执行实例</dt>
            <dd>{check.running_instance ?? "-"}</dd>
          </div>
        </dl>
        {check.latest_log && (
          <p className="mt-3 rounded bg-muted p-2 text-xs">
            {check.latest_log}
          </p>
        )}
      </div>
      <div className="rounded-lg border p-4">
        <h3 className="font-semibold">任务配置</h3>
        <pre className="mt-2 max-h-72 overflow-auto rounded bg-muted p-3 text-xs">
          {JSON.stringify(task.config ?? {}, null, 2)}
        </pre>
      </div>
    </div>
  )
}

function LogsPanel({ taskId }: { taskId: string }) {
  const id = Number(taskId)
  const [level, setLevel] = useState<string | undefined>(undefined)
  const { data } = useQuery<any>({
    queryKey: ["task-logs", id, level ?? "all"],
    queryFn: () =>
      TasksService.readTaskLogs({ path: { id }, query: { limit: 200, level } }),
    refetchInterval: 15_000,
  })
  return (
    <div className="rounded-lg border p-4">
      <div className="mb-3 flex gap-2">
        {["all", "INFO", "WARNING", "ERROR"].map((l) => (
          <Button
            key={l}
            size="sm"
            variant={
              level === l || (l === "all" && !level) ? "default" : "outline"
            }
            onClick={() => setLevel(l === "all" ? undefined : l)}
          >
            {l}
          </Button>
        ))}
      </div>
      <div className="max-h-96 space-y-1 overflow-auto font-mono text-xs">
        {((data?.data ?? []) as any[]).map((log: any) => (
          <div key={log.id} className="flex gap-2">
            <span className="text-muted-foreground">
              {log.created_at
                ? new Date(log.created_at).toLocaleTimeString()
                : ""}
            </span>
            <Badge variant={log.level === "ERROR" ? "destructive" : "outline"}>
              {log.level}
            </Badge>
            <span className="whitespace-pre-wrap">{log.message}</span>
          </div>
        ))}
        {data && (data.data as any[]).length === 0 && (
          <p className="text-muted-foreground">暂无日志</p>
        )}
      </div>
    </div>
  )
}

function ResultsPanel({ taskId }: { taskId: string }) {
  const id = Number(taskId)
  const { data } = useQuery<any>({
    queryKey: ["task-results", id],
    queryFn: () =>
      TaskResultsService.resultsReadTaskResults({
        path: { task_id: id },
        query: { limit: 100 },
      }),
  })
  const rows: any[] = ((data?.data as any)?.data ?? data?.data ?? []) as any[]
  return (
    <div className="rounded-lg border p-4">
      <p className="mb-2 text-sm text-muted-foreground">
        共 {data?.count ?? (data?.data as any)?.count ?? 0} 条结果（大 JSON
        请在结果页详情抽屉查看）
      </p>
      <div className="max-h-96 overflow-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b">
              <th className="p-2">#</th>
              <th className="p-2">股票</th>
              <th className="p-2">模型</th>
              <th className="p-2">周期</th>
              <th className="p-2">最优指标</th>
              <th className="p-2">Best</th>
            </tr>
          </thead>
          <tbody>
            {(rows as any[]).map((r: any) => (
              <tr key={r.id} className="border-b">
                <td className="p-2">{r.step_index}</td>
                <td className="p-2">{r.stock_code ?? "-"}</td>
                <td className="p-2">{r.model_name ?? r.model_key}</td>
                <td className="p-2">{r.period_key ?? "-"}</td>
                <td className="p-2">
                  {r.best_metric_name}: {r.best_metric_value ?? "-"}
                </td>
                <td className="p-2">{r.is_best ? "✓" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {(rows as any[]).length === 0 && (
          <p className="py-6 text-center text-muted-foreground">暂无结果</p>
        )}
      </div>
    </div>
  )
}

function TaskDetailContent({ taskId }: { taskId: string }) {
  return (
    <Tabs defaultValue="overview" className="gap-4">
      <TabsList>
        <TabsTrigger value="overview">概览</TabsTrigger>
        <TabsTrigger value="logs">日志</TabsTrigger>
        <TabsTrigger value="results">结果</TabsTrigger>
      </TabsList>
      <TabsContent value="overview">
        <OverviewPanel taskId={taskId} />
      </TabsContent>
      <TabsContent value="logs">
        <LogsPanel taskId={taskId} />
      </TabsContent>
      <TabsContent value="results">
        <ResultsPanel taskId={taskId} />
      </TabsContent>
    </Tabs>
  )
}

function TaskDetailPage() {
  const { taskId } = Route.useParams()
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">
          任务详情 #{taskId}
        </h1>
        <Button asChild variant="ghost">
          <Link to="/tasks">返回列表</Link>
        </Button>
      </div>
      <Suspense fallback={<p className="text-muted-foreground">加载中…</p>}>
        <TaskDetailContent taskId={taskId} />
      </Suspense>
    </div>
  )
}
