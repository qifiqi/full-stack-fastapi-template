import {
  Calendar,
  ClipboardList,
  FileText,
  FolderOpen,
  Home,
  KeyRound,
  LayoutList,
  LineChart,
  PieChart,
  Table2,
} from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = [
  { icon: Home, title: "仪表盘", path: "/" },
  { icon: ClipboardList, title: "任务管理", path: "/tasks" },
  { icon: Table2, title: "结果查询", path: "/results" },
  { icon: FolderOpen, title: "回测域", path: "/backtest" },
  { icon: PieChart, title: "模型汇总", path: "/model-summary" },
  { icon: LineChart, title: "性能分析", path: "/performance-analysis" },
  { icon: FileText, title: "Google Sheets", path: "/google-sheets" },
  { icon: KeyRound, title: "Token 池", path: "/google-sheet-tokens" },
  { icon: Calendar, title: "调度任务", path: "/scheduled-tasks" },
  { icon: LayoutList, title: "系统管理", path: "/system" },
]

export function AppSidebar() {
  const { user: currentUser } = useAuth()

  const items = currentUser?.is_superuser
    ? [
        ...baseItems,
        { icon: ClipboardList, title: "任务导出", path: "/tasks/export" },
      ]
    : baseItems

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
