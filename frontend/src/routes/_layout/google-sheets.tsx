import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { type GoogleSheetPublic, GoogleSheetsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import useCustomToast from "@/hooks/useCustomToast"

export const Route = createFileRoute("/_layout/google-sheets")({
  component: GoogleSheetsPage,
  head: () => ({ meta: [{ title: "Google Sheets" }] }),
})

function GoogleSheetsPage() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [newId, setNewId] = useState("")
  const [newName, setNewName] = useState("")

  const { data } = useQuery<any>({
    queryKey: ["google-sheets", "all"],
    queryFn: async () =>
      (
        await GoogleSheetsService.sheetsReadGoogleSheets({
          query: { limit: 200 },
        })
      ).data,
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["google-sheets"] })

  const create = useMutation({
    mutationFn: () =>
      GoogleSheetsService.sheetsCreateGoogleSheet({
        body: { spreadsheet_id: newId, name: newName || newId },
      }),
    onSuccess: () => {
      showSuccessToast("Sheet 已注册")
      setNewId("")
      setNewName("")
      invalidate()
    },
    onError: (err: any) =>
      showErrorToast(String(err?.body?.detail ?? "创建失败")),
  })

  const remove = useMutation({
    mutationFn: (id: number) =>
      GoogleSheetsService.sheetsDeleteGoogleSheet({ path: { id } }),
    onSuccess: () => {
      showSuccessToast("已删除")
      invalidate()
    },
    onError: (err: any) =>
      showErrorToast(String(err?.body?.detail ?? "删除失败（占用中不可删）")),
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Google Sheets</h1>
        <p className="text-muted-foreground">Sheet 注册表与运行占用状态</p>
      </div>
      <div className="flex gap-2">
        <Input
          placeholder="spreadsheet_id"
          value={newId}
          onChange={(e) => setNewId(e.target.value)}
          className="max-w-xs"
        />
        <Input
          placeholder="名称（可选）"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          className="max-w-xs"
        />
        <Button
          disabled={!newId.trim() || create.isPending}
          onClick={() => create.mutate()}
        >
          注册
        </Button>
      </div>
      <div className="overflow-auto rounded-lg border">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="p-2">ID</th>
              <th className="p-2">名称</th>
              <th className="p-2">Spreadsheet</th>
              <th className="p-2">分组</th>
              <th className="p-2">占用状态</th>
              <th className="p-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {(data?.data ?? []).map((s: GoogleSheetPublic) => (
              <tr key={s.id} className="border-b">
                <td className="p-2">{s.id}</td>
                <td className="p-2">{s.name ?? "-"}</td>
                <td className="p-2 font-mono text-xs">{s.spreadsheet_id}</td>
                <td className="p-2">{s.registry_scope}</td>
                <td className="p-2">
                  {s.is_in_use ? (
                    <span className="text-amber-600">
                      占用中（任务 {s.current_task_id}）
                    </span>
                  ) : (
                    <span className="text-green-600">空闲</span>
                  )}
                </td>
                <td className="p-2">
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={s.is_in_use}
                    onClick={() => remove.mutate(s.id)}
                  >
                    删除
                  </Button>
                </td>
              </tr>
            ))}
            {(data?.data ?? []).length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="p-6 text-center text-muted-foreground"
                >
                  暂无注册的 Sheet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
