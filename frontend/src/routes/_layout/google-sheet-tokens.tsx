import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { GoogleSheetTokensService } from "@/client"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"

export const Route = createFileRoute("/_layout/google-sheet-tokens")({
  component: TokensPage,
  head: () => ({ meta: [{ title: "Token 池" }] }),
})

function TokensPage() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [importText, setImportText] = useState("")

  const { data } = useQuery<any>({
    queryKey: ["google-sheet-tokens"],
    queryFn: async () =>
      (
        await GoogleSheetTokensService.sheetTokensReadGoogleSheetTokens({
          query: { limit: 200 },
        })
      ).data,
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["google-sheet-tokens"] })

  const importToken = useMutation({
    mutationFn: () =>
      GoogleSheetTokensService.sheetTokensImportGoogleSheetTokens({
        body: [
          {
            name: `imported-${Date.now()}`,
            token_context: JSON.parse(importText),
          },
        ],
      }),
    onSuccess: () => {
      showSuccessToast("Token 已导入")
      setImportText("")
      invalidate()
    },
    onError: (err: any) =>
      showErrorToast(String(err?.body?.detail ?? "导入失败（需合法 JSON）")),
  })

  const toggle = useMutation({
    mutationFn: (args: { id: number; is_active: boolean }) =>
      GoogleSheetTokensService.sheetTokensUpdateGoogleSheetToken({
        path: { id: args.id },
        body: { is_active: args.is_active },
      }),
    onSuccess: invalidate,
    onError: (err: any) =>
      showErrorToast(String(err?.body?.detail ?? "更新失败")),
  })

  const reconcile = useMutation({
    mutationFn: async (): Promise<any> =>
      await GoogleSheetTokensService.sheetTokensReconcileGoogleSheetTokens(),
    onSuccess: (r: any) => {
      showSuccessToast(r?.data?.message ?? r?.message ?? "对账完成")
      invalidate()
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) =>
      GoogleSheetTokensService.sheetTokensDeleteGoogleSheetToken({
        path: { id },
      }),
    onSuccess: () => {
      showSuccessToast("已删除")
      invalidate()
    },
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Token 池</h1>
          <p className="text-muted-foreground">
            OAuth 令牌用量与配额（上下文不回显明文）
          </p>
        </div>
        <Button
          variant="secondary"
          disabled={reconcile.isPending}
          onClick={() => reconcile.mutate()}
        >
          占用对账
        </Button>
      </div>

      <div className="grid gap-2">
        <Textarea
          placeholder="粘贴 token JSON（OAuth 用户令牌文件内容）后点击导入"
          value={importText}
          onChange={(e) => setImportText(e.target.value)}
          className="min-h-24 font-mono text-xs"
        />
        <Button
          disabled={!importText.trim() || importToken.isPending}
          onClick={() => importToken.mutate()}
        >
          导入 Token
        </Button>
      </div>

      <div className="overflow-auto rounded-lg border">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="p-2">ID</th>
              <th className="p-2">名称</th>
              <th className="p-2">占用/上限</th>
              <th className="p-2">累计使用</th>
              <th className="p-2">状态</th>
              <th className="p-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {(data?.data ?? []).map((t: any) => {
              const pct =
                t.max_usage_count && t.max_usage_count > 0
                  ? Math.min(
                      100,
                      Math.round(
                        ((t.current_in_use_count ?? 0) / t.max_usage_count) *
                          100,
                      ),
                    )
                  : 0
              return (
                <tr key={t.id} className="border-b">
                  <td className="p-2">{t.id}</td>
                  <td className="p-2">{t.name ?? `Token #${t.id}`}</td>
                  <td className="p-2">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-24 overflow-hidden rounded bg-muted">
                        <div
                          className="h-full bg-primary"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs">
                        {t.current_in_use_count}/{t.max_usage_count ?? "∞"}
                      </span>
                    </div>
                  </td>
                  <td className="p-2">{t.total_usage_count}</td>
                  <td className="p-2">{t.is_active ? "启用" : "停用"}</td>
                  <td className="p-2 flex gap-1">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        toggle.mutate({ id: t.id, is_active: !t.is_active })
                      }
                    >
                      {t.is_active ? "停用" : "启用"}
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => remove.mutate(t.id)}
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
                  colSpan={6}
                  className="p-6 text-center text-muted-foreground"
                >
                  Token 池为空
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
