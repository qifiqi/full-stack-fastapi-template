import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { ScheduledTasksService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"

export const Route = createFileRoute("/_layout/scheduled-tasks")({
  component: ScheduledTasksPage,
  head: () => ({ meta: [{ title: "调度任务" }] }),
})

const CRON_PRESETS = [
  { value: "0 0 * * *", label: "每天 0 点" },
  { value: "0 2 * * *", label: "每天 2 点" },
  { value: "0 */6 * * *", label: "每 6 小时" },
]

function ScheduledTasksPage() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [name, setName] = useState("")
  const [cron, setCron] = useState("0 0 * * *")
  const [jobType, setJobType] = useState("cleanup_old_data")

  const { data } = useQuery<any>({
    queryKey: ["scheduled-tasks"],
    queryFn: async () =>
      (
        await ScheduledTasksService.tasksReadScheduledTasks({
          query: { limit: 100 },
        })
      ).data,
    refetchInterval: 30_000,
  })
  const { data: stats } = useQuery<any>({
    queryKey: ["scheduler-stats"],
    queryFn: async (): Promise<any> =>
      await ScheduledTasksService.tasksReadSchedulerStats(),
    refetchInterval: 30_000,
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["scheduled-tasks"] })

  const create = useMutation({
    mutationFn: () =>
      ScheduledTasksService.tasksCreateScheduledTask({
        body: {
          name,
          task_type: jobType,
          cron_expression: cron,
          params: { days: 10 },
        },
      }),
    onSuccess: () => {
      showSuccessToast("调度任务已创建")
      setName("")
      invalidate()
    },
    onError: (err: any) =>
      showErrorToast(String(err?.body?.detail ?? "创建失败")),
  })

  const action = useMutation({
    mutationFn: async (args: { op: string; id: number }) => {
      const { op, id } = args
      if (op === "toggle") {
        return ScheduledTasksService.tasksToggleScheduledTask({ path: { id } })
      }
      if (op === "run") {
        return ScheduledTasksService.tasksRunScheduledTask({ path: { id } })
      }
      return ScheduledTasksService.tasksDeleteScheduledTask({ path: { id } })
    },
    onSuccess: (_r, v) => {
      if (v.op !== "toggle") showSuccessToast("成功")
      invalidate()
    },
    onError: (err: any) =>
      showErrorToast(String(err?.body?.detail ?? "操作失败")),
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">调度任务</h1>
        <p className="text-muted-foreground">
          cron 清理任务（croniter 校验；worker 30s tick 领取；DB 运行锁互斥）
        </p>
      </div>

      <div className="grid gap-3 rounded-lg border p-4 md:grid-cols-4">
        <Input
          placeholder="任务名"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Input
          placeholder="cron 表达式"
          value={cron}
          onChange={(e) => setCron(e.target.value)}
        />
        <Select value={jobType} onValueChange={setJobType}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="cleanup_old_data">cleanup_old_data</SelectItem>
            <SelectItem value="cleanup_old_logs">cleanup_old_logs</SelectItem>
            <SelectItem value="cleanup_old_results">
              cleanup_old_results
            </SelectItem>
          </SelectContent>
        </Select>
        <div className="flex flex-wrap items-center gap-1">
          {CRON_PRESETS.map((p) => (
            <Button
              key={p.value}
              size="sm"
              variant="outline"
              onClick={() => setCron(p.value)}
            >
              {p.label}
            </Button>
          ))}
        </div>
        <Button
          className="md:col-span-4"
          disabled={!name.trim() || create.isPending}
          onClick={() => create.mutate()}
        >
          新建调度任务
        </Button>
      </div>

      {stats && (
        <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
          <Badge variant="outline">worker: {stats.worker_instance_id}</Badge>
          <Badge variant="outline">运行锁: {stats.running_count}</Badge>
        </div>
      )}

      <div className="overflow-auto rounded-lg border">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="p-2">ID</th>
              <th className="p-2">名称</th>
              <th className="p-2">类型</th>
              <th className="p-2">Cron</th>
              <th className="p-2">上次运行</th>
              <th className="p-2">状态</th>
              <th className="p-2">下次触发</th>
              <th className="p-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {(data?.data ?? []).map((t: any) => {
              const fire = stats?.next_fire_times?.[String(t.id)]
              return (
                <tr key={t.id} className="border-b">
                  <td className="p-2">{t.id}</td>
                  <td className="p-2">{t.name}</td>
                  <td className="p-2 font-mono text-xs">{t.task_type}</td>
                  <td className="p-2 font-mono text-xs">{t.cron_expression}</td>
                  <td className="p-2">
                    {t.last_run_at
                      ? new Date(t.last_run_at).toLocaleString()
                      : "-"}
                    {t.last_status ? ` (${t.last_status})` : ""}
                  </td>
                  <td className="p-2">
                    {t.is_running ? (
                      <Badge variant="secondary">运行中</Badge>
                    ) : t.enabled ? (
                      <Badge variant="outline">启用</Badge>
                    ) : (
                      <Badge variant="destructive">停用</Badge>
                    )}
                  </td>
                  <td className="p-2">
                    {fire ? new Date(fire).toLocaleString() : "-"}
                  </td>
                  <td className="p-2 flex gap-1">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => action.mutate({ op: "toggle", id: t.id })}
                    >
                      {t.enabled ? "停用" : "启用"}
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => action.mutate({ op: "run", id: t.id })}
                    >
                      立即运行
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => action.mutate({ op: "delete", id: t.id })}
                    >
                      删除
                    </Button>
                  </td>
                </tr>
              )
            })}
            {(data?.data ?? []).length === 0 && (
              <tr>
                <td
                  colSpan={8}
                  className="p-6 text-center text-muted-foreground"
                >
                  暂无调度任务
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
