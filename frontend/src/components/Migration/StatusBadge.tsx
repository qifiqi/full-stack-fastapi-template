import type { TaskPublic } from "@/client"
import { Badge } from "@/components/ui/badge"

const STATUS_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  success: "default",
  running: "secondary",
  pending: "outline",
  queued: "outline",
  cancelled: "secondary",
  error: "destructive",
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge variant={STATUS_VARIANT[status] ?? "outline"}>{status}</Badge>
}

export const statusBadgeColumn = {
  accessorKey: "status",
  header: "Status",
  cell: ({ row }: { row: { original: TaskPublic } }) => (
    <StatusBadge status={row.original.status} />
  ),
}
