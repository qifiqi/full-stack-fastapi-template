import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import {
  ConfigsService,
  LogsService,
  NavigationService,
  TaskTemplatesService,
} from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"

export const Route = createFileRoute("/_layout/system")({
  component: SystemAdminPage,
  head: () => ({ meta: [{ title: "系统管理" }] }),
})

function TemplatesTab() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [name, setName] = useState("")
  const [config, setConfig] = useState("{}")

  const { data } = useQuery<any>({
    queryKey: ["task-templates"],
    queryFn: async () =>
      (
        await TaskTemplatesService.templatesReadTaskTemplates({
          query: { limit: 100 },
        })
      ).data,
  })
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["task-templates"] })

  const create = useMutation({
    mutationFn: () => {
      const parsed = JSON.parse(config)
      return TaskTemplatesService.templatesCreateTaskTemplate({
        body: { name, config: parsed },
      })
    },
    onSuccess: () => {
      showSuccessToast("模板已保存")
      setName("")
      setConfig("{}")
      invalidate()
    },
    onError: (err: any) =>
      showErrorToast(String(err?.body?.detail ?? "保存失败（JSON 非法）")),
  })
  const remove = useMutation({
    mutationFn: (id: number) =>
      TaskTemplatesService.templatesDeleteTaskTemplate({ path: { id } }),
    onSuccess: () => {
      showSuccessToast("已删除")
      invalidate()
    },
  })

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-2 md:grid-cols-2">
        <Input
          placeholder="模板名"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Textarea
          placeholder="配置 JSON"
          value={config}
          onChange={(e) => setConfig(e.target.value)}
          className="font-mono text-xs"
        />
      </div>
      <Button
        disabled={!name.trim() || create.isPending}
        onClick={() => create.mutate()}
      >
        保存模板
      </Button>
      <div className="overflow-auto rounded-lg border">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="p-2">ID</th>
              <th className="p-2">名称</th>
              <th className="p-2">更新时间</th>
              <th className="p-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {((data?.data ?? []) as any[]).map((t: any) => (
              <tr key={t.id} className="border-b">
                <td className="p-2">{t.id}</td>
                <td className="p-2">{t.name}</td>
                <td className="p-2">
                  {t.updated_at ? new Date(t.updated_at).toLocaleString() : "-"}
                </td>
                <td className="p-2">
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => remove.mutate(t.id)}
                  >
                    删除
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ConfigsTab() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [edits, setEdits] = useState<Record<string, string>>({})

  const { data } = useQuery<any>({
    queryKey: ["system-configs"],
    queryFn: async () =>
      (await ConfigsService.readConfigs({ query: { limit: 200 } })).data,
  })
  const save = useMutation({
    mutationFn: (args: { key: string; value: string }) =>
      ConfigsService.updateConfig({
        path: { key: args.key },
        body: { value: args.value },
      }),
    onSuccess: () => {
      showSuccessToast("已保存")
      queryClient.invalidateQueries({ queryKey: ["system-configs"] })
    },
    onError: (err: any) =>
      showErrorToast(String(err?.body?.detail ?? "保存失败")),
  })

  return (
    <div className="overflow-auto rounded-lg border">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="p-2">Key</th>
            <th className="p-2">Value（敏感值已遮蔽）</th>
            <th className="p-2">更新时间</th>
            <th className="p-2">操作</th>
          </tr>
        </thead>
        <tbody>
          {((data?.data ?? []) as any[]).map((c: any) => (
            <tr key={c.key} className="border-b">
              <td className="p-2 font-mono text-xs">{c.key}</td>
              <td className="p-2">
                <Input
                  value={edits[c.key] ?? c.value}
                  onChange={(e) =>
                    setEdits((prev) => ({ ...prev, [c.key]: e.target.value }))
                  }
                  className="h-8 max-w-md font-mono text-xs"
                />
              </td>
              <td className="p-2 text-xs text-muted-foreground">
                {c.updated_at ? new Date(c.updated_at).toLocaleString() : "-"}
              </td>
              <td className="p-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    save.mutate({ key: c.key, value: edits[c.key] ?? c.value })
                  }
                >
                  保存
                </Button>
              </td>
            </tr>
          ))}
          {((data?.data ?? []) as any[]).length === 0 && (
            <tr>
              <td colSpan={4} className="p-6 text-center text-muted-foreground">
                暂无系统配置（worker 写入或手动添加）
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function LogsTab() {
  const [level, setLevel] = useState<string | undefined>()
  const { data } = useQuery<any>({
    queryKey: ["global-logs", level ?? "all"],
    queryFn: async (): Promise<any> =>
      await LogsService.readLogs({ query: { limit: 200, level } }),
    refetchInterval: 30_000,
  })
  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
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
      <div className="max-h-96 space-y-1 overflow-auto rounded-lg border p-3 font-mono text-xs">
        {((data?.data ?? []) as any[]).map((log: any) => (
          <div key={log.id} className="flex gap-2">
            <span className="text-muted-foreground">
              {log.created_at ? new Date(log.created_at).toLocaleString() : ""}
            </span>
            <Badge variant={log.level === "ERROR" ? "destructive" : "outline"}>
              {log.level}
            </Badge>
            <span className="whitespace-pre-wrap">
              [{log.task_id}] {log.message}
            </span>
          </div>
        ))}
        {((data?.data ?? []) as any[]).length === 0 && (
          <p className="text-muted-foreground">暂无日志</p>
        )}
      </div>
    </div>
  )
}

function NavigationTab() {
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const { data } = useQuery<any>({
    queryKey: ["navigation-items"],
    queryFn: async () =>
      (await NavigationService.readNavigationItems({ query: { limit: 100 } }))
        .data,
  })
  const remove = useMutation({
    mutationFn: (id: number) =>
      NavigationService.deleteNavigationItem({ path: { id } }),
    onSuccess: () => {
      showSuccessToast("已删除")
      queryClient.invalidateQueries({ queryKey: ["navigation-items"] })
    },
  })
  return (
    <div className="overflow-auto rounded-lg border">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="p-2">ID</th>
            <th className="p-2">标题</th>
            <th className="p-2">路径</th>
            <th className="p-2">排序</th>
            <th className="p-2">可见</th>
            <th className="p-2">操作</th>
          </tr>
        </thead>
        <tbody>
          {((data?.data ?? []) as any[]).map((n: any) => (
            <tr key={n.id} className="border-b">
              <td className="p-2">{n.id}</td>
              <td className="p-2">{n.title}</td>
              <td className="p-2 font-mono text-xs">{n.path}</td>
              <td className="p-2">{n.sort_order}</td>
              <td className="p-2">{n.is_visible ? "✓" : "-"}</td>
              <td className="p-2">
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => remove.mutate(n.id)}
                >
                  删除
                </Button>
              </td>
            </tr>
          ))}
          {((data?.data ?? []) as any[]).length === 0 && (
            <tr>
              <td colSpan={6} className="p-6 text-center text-muted-foreground">
                暂无导航项（前端侧边栏为本地定义，此表为旧数据兼容视图）
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function SystemAdminPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">系统管理</h1>
        <p className="text-muted-foreground">
          任务模板 / 系统配置 / 日志查询 / 导航数据
        </p>
      </div>
      <Tabs defaultValue="templates" className="gap-4">
        <TabsList>
          <TabsTrigger value="templates">任务模板</TabsTrigger>
          <TabsTrigger value="configs">系统配置</TabsTrigger>
          <TabsTrigger value="logs">日志查询</TabsTrigger>
          <TabsTrigger value="navigation">导航数据</TabsTrigger>
        </TabsList>
        <TabsContent value="templates">
          <TemplatesTab />
        </TabsContent>
        <TabsContent value="configs">
          <ConfigsTab />
        </TabsContent>
        <TabsContent value="logs">
          <LogsTab />
        </TabsContent>
        <TabsContent value="navigation">
          <NavigationTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
