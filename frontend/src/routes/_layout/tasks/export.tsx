import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { TasksService } from "@/client"
import { StatusBadge } from "@/components/Migration/StatusBadge"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"

export const Route = createFileRoute("/_layout/tasks/export")({
  component: ExportPage,
  head: () => ({ meta: [{ title: "任务导出" }] }),
})

function ExportPage() {
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [selected, setSelected] = useState<number[]>([])
  const [busy, setBusy] = useState(false)

  const { data } = useQuery<any>({
    queryKey: ["tasks", "export"],
    queryFn: async () =>
      (
        await TasksService.readTasks({
          query: { skip: 0, limit: 100, status: "success" },
        })
      ).data,
  })

  const toggle = (id: number) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    )
  }

  const download = async (taskId: number) => {
    setBusy(true)
    try {
      const response = await fetch(`/api/v1/exports/tasks/${taskId}?format=csv`)
      if (!response.ok) throw new Error(await response.text())
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `task_${taskId}_results.csv`
      a.click()
      URL.revokeObjectURL(url)
      showSuccessToast("已下载")
    } catch (err) {
      showErrorToast(String(err).slice(0, 200))
    } finally {
      setBusy(false)
    }
  }

  const downloadBatch = async () => {
    setBusy(true)
    try {
      const response = await fetch("/api/v1/exports/tasks/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(selected),
      })
      if (!response.ok) throw new Error(await response.text())
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = "tasks_export.zip"
      a.click()
      URL.revokeObjectURL(url)
      showSuccessToast(`已打包 ${selected.length} 个任务`)
      setSelected([])
    } catch (err) {
      showErrorToast(String(err).slice(0, 200))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">任务导出</h1>
          <p className="text-muted-foreground">
            多任务勾选合并导出 ZIP（≤10 个），或单任务 CSV 下载
          </p>
        </div>
        <Button
          disabled={selected.length === 0 || busy}
          onClick={downloadBatch}
        >
          打包下载（{selected.length}/10）
        </Button>
      </div>

      <div className="overflow-auto rounded-lg border">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="p-2">选</th>
              <th className="p-2">ID</th>
              <th className="p-2">名称</th>
              <th className="p-2">状态</th>
              <th className="p-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {((data?.data ?? []) as any[]).map((t: any) => (
              <tr key={t.id} className="border-b">
                <td className="p-2">
                  <input
                    type="checkbox"
                    checked={selected.includes(t.id)}
                    onChange={() => toggle(t.id)}
                  />
                </td>
                <td className="p-2">{t.id}</td>
                <td className="p-2">{t.name}</td>
                <td className="p-2">
                  <StatusBadge status={t.status} />
                </td>
                <td className="p-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => download(t.id)}
                  >
                    CSV
                  </Button>
                </td>
              </tr>
            ))}
            {(data?.data ?? []).length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="p-6 text-center text-muted-foreground"
                >
                  暂无已完成任务
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
