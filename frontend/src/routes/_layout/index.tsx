import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"

import { type TaskPublic, TasksService } from "@/client"
import { StatusBadge } from "@/components/Migration/StatusBadge"
import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({ meta: [{ title: "仪表盘" }] }),
})

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  )
}

function DashboardContent() {
  const { user: currentUser } = useAuth()
  const { data } = useQuery<any>({
    queryKey: ["dashboard-tasks"],
    queryFn: async () =>
      (
        await TasksService.readTasks({
          query: { skip: 0, limit: 10, include_statistics: true },
        })
      ).data,
    refetchInterval: (query) =>
      (query.state.data?.data ?? []).some((t: any) => t.status === "running")
        ? 15_000
        : 60_000,
  })

  const stats = data?.statistics
  const recent = data?.data ?? []

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl truncate max-w-sm font-bold">
          Hi, {currentUser?.full_name || currentUser?.email} 👋
        </h1>
        <p className="text-muted-foreground">
          任务执行总览（运行中 15s / 空闲 60s 刷新）
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="任务总数" value={stats?.total ?? 0} />
        <StatCard label="运行中" value={stats?.by_status?.running ?? 0} />
        <StatCard label="成功" value={stats?.by_status?.success ?? 0} />
        <StatCard
          label="平均耗时（秒）"
          value={
            stats?.avg_running_seconds != null
              ? Math.round(stats.avg_running_seconds)
              : "-"
          }
        />
      </div>

      <div className="flex flex-wrap gap-2">
        {(Object.entries(stats?.by_status ?? {}) as [string, number][]).map(
          ([status, count]) => (
            <div
              key={status}
              className="flex items-center gap-2 rounded-full border px-3 py-1 text-sm"
            >
              <StatusBadge status={status} />
              <span className="font-medium">{count}</span>
            </div>
          ),
        )}
      </div>

      <div className="rounded-lg border">
        <div className="flex items-center justify-between border-b p-3">
          <h2 className="font-semibold">最近任务</h2>
          <Button asChild size="sm" variant="ghost">
            <Link to="/tasks">查看全部</Link>
          </Button>
        </div>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="p-2">ID</th>
              <th className="p-2">名称</th>
              <th className="p-2">状态</th>
              <th className="p-2">进度</th>
              <th className="p-2">心跳</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((t: TaskPublic) => (
              <tr key={t.id} className="border-b">
                <td className="p-2">{t.id}</td>
                <td className="p-2">{t.name}</td>
                <td className="p-2">
                  <StatusBadge status={t.status} />
                </td>
                <td className="p-2">
                  {t.current_step}/{t.total_steps}
                </td>
                <td className="p-2">
                  {t.heartbeat_at
                    ? new Date(t.heartbeat_at).toLocaleTimeString()
                    : "-"}
                </td>
              </tr>
            ))}
            {recent.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="p-6 text-center text-muted-foreground"
                >
                  暂无任务
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Dashboard() {
  return <DashboardContent />
}
