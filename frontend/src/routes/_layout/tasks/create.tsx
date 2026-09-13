import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useState } from "react"

import {
  GoogleSheetsService,
  TasksService,
  TaskTemplatesService,
} from "@/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"

export const Route = createFileRoute("/_layout/tasks/create")({
  component: CreateTaskPage,
  head: () => ({ meta: [{ title: "创建任务" }] }),
})

const TASK_TYPES = [
  { value: "google_sheet", label: "C3 · Google Sheet" },
  { value: "google_sheet_c4", label: "C4 · 多市场" },
  { value: "google_sheet_c5", label: "C5 · 参数扫描" },
  { value: "google_sheet_c7", label: "C7 · 随机价" },
  { value: "backtest_training", label: "单品回测" },
  { value: "backtest_multi_product", label: "多品回测" },
]

const DEFAULT_CONFIGS: Record<string, object> = {
  google_sheet: {
    spreadsheet_id: "",
    sheet_name: "",
    stock_code: "",
    year_n: "1y",
    price_mode: "vwap_price",
    kline_data_source: "dfcf",
    kline_adjustment: "forward",
    parameters: [[1]],
  },
  google_sheet_c7: {
    sheets: [],
    stock_code: "",
    price_mode: "vwap_price",
    kline_source: "auto",
  },
  backtest_training: {
    sheet: { google_sheet_id: 0, spreadsheet_id: "", sheet_name: "" },
    stock_code: "",
    price_mode: "vwap_price",
    kline_data_source: "akshare",
  },
}

function CreateTaskPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const [taskType, setTaskType] = useState("google_sheet")
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [configText, setConfigText] = useState(
    JSON.stringify(DEFAULT_CONFIGS.google_sheet, null, 2),
  )

  const { data: sheets } = useQuery<any>({
    queryKey: ["google-sheets", "available"],
    queryFn: () =>
      GoogleSheetsService.sheetsReadGoogleSheets({ query: { limit: 100 } }),
  })
  const { data: templates } = useQuery<any>({
    queryKey: ["task-templates"],
    queryFn: async (): Promise<any> =>
      await TaskTemplatesService.templatesReadTaskTemplates({
        query: { limit: 50 },
      }),
  })

  const applyTemplate = (id: number) => {
    const list: any[] =
      templates !== undefined ? ((templates.data as any[]) ?? []) : []
    const tpl = list.find((t: any) => t.id === id)
    if (tpl !== undefined && tpl.config != null) {
      setConfigText(JSON.stringify(tpl.config, null, 2))
      if (tpl.name) setName(`${tpl.name} 任务`)
    }
  }

  const pickSheet = (spreadsheetId: string) => {
    setConfigText((prev) => {
      const config = JSON.parse(prev)
      config.spreadsheet_id = spreadsheetId
      return JSON.stringify(config, null, 2)
    })
  }

  const createMutation = useMutation({
    mutationFn: async ({ input }: { input: any }): Promise<any> =>
      await TasksService.createTask({ body: input }),
    onSuccess: (task: any) => {
      showSuccessToast(`任务 #${task.id} 已创建（pending）`)
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      void navigate({
        to: "/tasks/$taskId",
        params: { taskId: String(task.id) },
      })
    },
    onError: (err: any) => {
      showErrorToast(String(err?.body?.detail ?? err?.message ?? "创建失败"))
    },
  })

  const submit = () => {
    let config: object
    try {
      config = JSON.parse(configText)
    } catch {
      showErrorToast("配置不是有效 JSON")
      return
    }
    if (!name.trim()) {
      showErrorToast("任务名不能为空")
      return
    }
    createMutation.mutate({
      input: {
        name: name.trim(),
        description: description || undefined,
        task_type: taskType,
        config,
      },
    })
  }

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <h1 className="text-2xl font-bold tracking-tight">创建任务</h1>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="grid gap-2">
          <Label htmlFor="task-type">任务类型</Label>
          <Select
            value={taskType}
            onValueChange={(v) => {
              setTaskType(v)
              if (DEFAULT_CONFIGS[v])
                setConfigText(JSON.stringify(DEFAULT_CONFIGS[v], null, 2))
            }}
          >
            <SelectTrigger id="task-type">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TASK_TYPES.map((t: any) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="task-name">任务名</Label>
          <Input
            id="task-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="task-desc">描述（可选）</Label>
        <Input
          id="task-desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      <div className="grid gap-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="task-config">任务配置（JSON）</Label>
          <div className="flex gap-2">
            {templates && templates.data.length > 0 && (
              <Select onValueChange={(v) => applyTemplate(Number(v))}>
                <SelectTrigger className="h-8 w-36 text-xs">
                  <SelectValue placeholder="载入模板" />
                </SelectTrigger>
                <SelectContent>
                  {templates.data.map((t: any) => (
                    <SelectItem key={t.id} value={String(t.id)}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            {sheets && sheets.data.length > 0 && (
              <Select onValueChange={pickSheet}>
                <SelectTrigger className="h-8 w-36 text-xs">
                  <SelectValue placeholder="选择 Sheet" />
                </SelectTrigger>
                <SelectContent>
                  {(sheets.data as any[]).map((s: any) => (
                    <SelectItem key={s.id} value={s.spreadsheet_id}>
                      {s.name ?? s.spreadsheet_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
        </div>
        <Textarea
          id="task-config"
          className="min-h-72 font-mono text-xs"
          value={configText}
          onChange={(e) => setConfigText(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          批量任务（C31 股票×参数×Sheet 笛卡尔积）通过 API 的 batch-create
          完成，表单批量入口在任务列表页。
        </p>
      </div>
      <div className="flex gap-2">
        <Button onClick={submit} disabled={createMutation.isPending}>
          {createMutation.isPending ? "创建中…" : "创建任务（pending）"}
        </Button>
        <Button variant="ghost" onClick={() => window.history.back()}>
          取消
        </Button>
      </div>
    </div>
  )
}
