import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import type { ColumnDef } from "@tanstack/react-table"
import { Suspense, useState } from "react"

import { type TaskPublic, TasksService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { StatusBadge } from "@/components/Migration/StatusBadge"
import PendingItems from "@/components/Pending/PendingItems"
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

export const Route = createFileRoute("/_layout/tasks/")({
  component: TasksPage,
  head: () => ({ meta: [{ title: "任务管理" }] }),
})

function TaskActionsMenu({ task }: { task: TaskPublic }) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [busy, setBusy] = useState(false)

  const mutation = useMutation({
    mutationFn: async (action: "cancel" | "createRestart" | "deleteTask") => {
      setBusy(true)
      try {
        if (action === "cancel") {
          await TasksService.cancelTask({ path: { id: task.id } })
          showSuccessToast("已请求取消，等待 worker 桥接")
        } else if (action === "createRestart") {
          await TasksService.createRestart({ path: { id: task.id } })
          showSuccessToast("已创建重启任务")
        } else {
          await TasksService.deleteTask({ path: { id: task.id } })
          showSuccessToast("任务已删除")
        }
      } finally {
        setBusy(false)
      }
      await queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
    onError: (err: any) => {
      const detail = err?.body?.detail ?? "操作失败"
      showErrorToast(String(detail))
    },
  })

  return (
    <div className="flex gap-1">
      <Button asChild size="sm" variant="ghost">
        <Link to="/tasks/$taskId" params={{ taskId: String(task.id) }}>
          详情
        </Link>
      </Button>
      {task.status === "running" && (
        <Button
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() => mutation.mutate("cancel")}
        >
          取消
        </Button>
      )}
      <Button
        size="sm"
        variant="ghost"
        disabled={busy}
        onClick={() => mutation.mutate("createRestart")}
      >
        重建
      </Button>
      {task.status !== "running" && (
        <Button
          size="sm"
          variant="destructive"
          disabled={busy}
          onClick={() => mutation.mutate("deleteTask")}
        >
          删除
        </Button>
      )}
    </div>
  )
}

const columns: ColumnDef<TaskPublic>[] = [
  { accessorKey: "id", header: "ID" },
  { accessorKey: "name", header: "名称" },
  {
    accessorKey: "task_type",
    header: "类型",
    cell: ({ row }) => (
      <Badge variant="outline">{row.original.task_type}</Badge>
    ),
  },
  {
    accessorKey: "status",
    header: "状态",
    cell: ({ row }) => <StatusBadge status={row.original.status} />,
  },
  {
    id: "progress",
    header: "进度",
    cell: ({ row }) =>
      `${row.original.current_step}/${row.original.total_steps}`,
  },
  { accessorKey: "stock_code", header: "股票" },
  {
    accessorKey: "created_at",
    header: "创建时间",
    cell: ({ row }) =>
      row.original.created_at
        ? new Date(row.original.created_at).toLocaleString()
        : "-",
  },
  {
    id: "actions",
    header: "操作",
    cell: ({ row }) => <TaskActionsMenu task={row.original} />,
  },
]

function TasksTableContent() {
  const [status, setStatus] = useState<string>("all")
  const [keyword, setKeyword] = useState("")
  const [search, setSearch] = useState("")

  const { data } = useQuery<any>({
    queryKey: ["tasks", status, search],
    queryFn: async () =>
      (
        await TasksService.readTasks({
          query: {
            skip: 0,
            limit: 100,
            status: status === "all" ? undefined : status,
            keyword: search || undefined,
          },
        })
      ).data,
    placeholderData: (prev: any) => prev,
    refetchInterval: (query: any) => {
      const running: any[] = query.state.data?.data ?? []
      return running.some((t: any) => t.status === "running") ? 15_000 : false
    },
  })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="状态" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
            {[
              "pending",
              "queued",
              "running",
              "success",
              "error",
              "cancelled",
            ].map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          placeholder="按名称/描述前缀搜索（回车）"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") setSearch(keyword)
          }}
          className="max-w-xs"
        />
        <Button variant="secondary" onClick={() => setSearch(keyword)}>
          搜索
        </Button>
      </div>
      {data && data.data.length === 0 ? (
        <div className="py-12 text-center text-muted-foreground">
          暂无任务，点击右上角"创建任务"开始
        </div>
      ) : (
        <DataTable columns={columns} data={data?.data ?? []} />
      )}
    </div>
  )
}

function TasksPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">任务管理</h1>
          <p className="text-muted-foreground">
            Google Sheet 校验与回测任务的创建、执行与追踪
          </p>
        </div>
        <Button asChild>
          <Link to="/tasks/create">创建任务</Link>
        </Button>
      </div>
      <Suspense fallback={<PendingItems />}>
        <TasksTableContent />
      </Suspense>
    </div>
  )
}
