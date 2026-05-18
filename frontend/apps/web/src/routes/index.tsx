import * as React from "react"
import { createFileRoute } from "@tanstack/react-router"
import { UserButton, useAuth, useUser } from "@clerk/tanstack-react-start"
import {
  AlertCircle,
  ArrowLeft,
  ArrowUp,
  ArrowUpDown,
  AudioLines,
  Brain,
  ChartCandlestick,
  Check,
  Copy,
  Ellipsis,
  Eye,
  EyeOff,
  FileUp,
  Folder,
  Handshake,
  ImageUp,
  LoaderCircle,
  Mic,
  MoreHorizontal,
  Newspaper,
  Plus,
  RefreshCw,
  Share2,
  SquarePen,
  ToolCase,
  Trash2,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "@workspace/ui/components/chart"
import {
  CartesianGrid,
  Cell,
  Line,
  Pie,
  LineChart as RechartsLineChart,
  PieChart as RechartsPieChart,
  XAxis,
  YAxis,
} from "recharts"
import { Avatar, AvatarFallback } from "@workspace/ui/components/avatar"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@workspace/ui/components/alert-dialog"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@workspace/ui/components/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@workspace/ui/components/dropdown-menu"
import { ScrollArea } from "@workspace/ui/components/scroll-area"
import { Input } from "@workspace/ui/components/input"
import { Skeleton } from "@workspace/ui/components/skeleton"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from "@workspace/ui/components/sidebar"
import { Switch } from "@workspace/ui/components/switch"
import { Textarea } from "@workspace/ui/components/textarea"
import { Separator } from "@workspace/ui/components/separator"
import { cn } from "@workspace/ui/lib/utils"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { toast } from "sonner"
import type { ChartConfig } from "@workspace/ui/components/chart"
import type {
  ApiAttachmentInput,
  ApiBrokerPortfolioSummary,
  ApiBrokerStatusItem,
  ApiConversation,
  ApiMcpConnection,
  ApiMcpProvider,
  ApiMessage,
  ApiMessageAttachment,
  ApiModelsResponse,
  ApiProviderInfo,
  ApiStoredAsset,
} from "@/lib/chat-api"
import {
  ApiError,
  connectAngelOneBroker,
  connectGrowwBroker,
  connectMcpProvider,
  createConversation,
  deleteAsset,
  deleteConversation,
  disconnectAngelOneBroker,
  disconnectGrowwBroker,
  disconnectMcpProvider,
  fetchAngelOnePortfolio,
  fetchBrokerPortfolioHistory,
  fetchBrokerStatus,
  fetchConversationDetail,
  fetchGrowwPortfolio,
  fetchModels,
  getChatUserId,
  isAbortError,
  listAssets,
  listConversations,
  listMcpConnections,
  listMcpProviders,
  sendMessage,
  setAuthTokenProvider,
  uploadAssets,
} from "@/lib/chat-api"
import { MarketCanvas } from "@/components/market-canvas"
import { useStreamingChat } from "@/hooks/use-streaming-chat"

export const Route = createFileRoute("/")({
  component: App,
})

type ModelOption = {
  key: string
  provider: string
  id: string
  name: string
  description: string
}

type LocalMessage = ApiMessage & {
  isPending?: boolean
}

type ComposerAttachment = {
  id: string
  kind: "file" | "image"
  name: string
  mimeType: string
  size: number
  file: File
  previewUrl?: string
}

type BrokerOption = "angel-one" | "kite" | "groww"
type BrokerStatusMap = Partial<Record<BrokerOption, ApiBrokerStatusItem>>

interface SpeechRecognitionResultEntry {
  isFinal: boolean
  [index: number]: {
    transcript: string
  }
}

interface SpeechRecognitionEvent extends Event {
  resultIndex: number
  results: {
    length: number
    [index: number]: SpeechRecognitionResultEntry
  }
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean
  interimResults: boolean
  lang: string
  onend: ((this: SpeechRecognition, event: Event) => void) | null
  onerror:
    | ((this: SpeechRecognition, event: SpeechRecognitionErrorEvent) => void)
    | null
  onresult:
    | ((this: SpeechRecognition, event: SpeechRecognitionEvent) => void)
    | null
  start: () => void
  stop: () => void
  abort: () => void
}

interface SpeechRecognitionConstructor {
  new (): SpeechRecognition
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor
    webkitSpeechRecognition?: SpeechRecognitionConstructor
  }
}

const MAX_DRAFT_HEIGHT = 260
const MAX_ATTACHMENT_COUNT = 8
const MAX_IMAGE_ATTACHMENT_BYTES = 8 * 1024 * 1024
const MAX_TEXT_ATTACHMENT_BYTES = 2 * 1024 * 1024
const MAX_ASSET_UPLOAD_COUNT = 20
const MAX_ASSET_UPLOAD_BYTES = 25 * 1024 * 1024

const SUPPORTED_TEXT_FILE_EXTENSIONS = new Set([
  "c",
  "cpp",
  "css",
  "go",
  "html",
  "java",
  "js",
  "json",
  "md",
  "pdf",
  "py",
  "rb",
  "rs",
  "sh",
  "sql",
  "svg",
  "toml",
  "ts",
  "tsx",
  "txt",
  "xml",
  "yaml",
  "yml",
])

const primaryActions = [
  {
    icon: SquarePen,
    label: "New chat",
    action: "new-chat",
  },
  {
    icon: ChartCandlestick,
    label: "Market",
    action: "market",
  },
  {
    icon: Handshake,
    label: "Brokers",
    action: "brokers",
  },
  {
    icon: Folder,
    label: "Assets",
    action: "assets",
  },
  {
    icon: ToolCase,
    label: "MCP",
    action: "tools",
  },
  {
    icon: Ellipsis,
    label: "More",
    action: "more",
  },
] as const

const brokerCards: Array<{
  id: BrokerOption
  name: string
  isAvailable: boolean
}> = [
  {
    id: "angel-one",
    name: "Angel One",
    isAvailable: true,
  },
  {
    id: "kite",
    name: "Kite",
    isAvailable: false,
  },
  {
    id: "groww",
    name: "Groww",
    isAvailable: true,
  },
]

function fromApiBrokerName(broker: string): BrokerOption | null {
  switch (broker) {
    case "angel_one":
      return "angel-one"
    case "kite":
      return "kite"
    case "groww":
      return "groww"
    default:
      return null
  }
}

function getConnectedBrokerIds(status: BrokerStatusMap): Array<BrokerOption> {
  return brokerCards
    .filter((broker) => broker.isAvailable)
    .filter((broker) => status[broker.id]?.is_active === true)
    .map((broker) => broker.id)
}

function getFirstConnectableBroker(status: BrokerStatusMap): BrokerOption {
  return (
    brokerCards.find(
      (broker) => broker.isAvailable && status[broker.id]?.is_active !== true
    )?.id ?? "angel-one"
  )
}

function getBrokerInitials(broker: BrokerOption) {
  switch (broker) {
    case "angel-one":
      return "AO"
    case "kite":
      return "KT"
    case "groww":
      return "GW"
  }
}

function formatBrokerCurrency(value: number | null): string {
  if (value === null) {
    return "-"
  }

  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

function truncateLabel(text: string, maxLength: number) {
  if (text.length <= maxLength) {
    return text
  }

  return `${text.slice(0, maxLength).trimEnd()}...`
}

function createModelKey(provider: string, modelId: string) {
  return `${provider}:${modelId}`
}

function flattenModelOptions(
  providers: Array<ApiProviderInfo>
): Array<ModelOption> {
  return providers.flatMap((provider) =>
    provider.models.map((model) => ({
      key: createModelKey(provider.name, model.id),
      provider: provider.name,
      id: model.id,
      name: model.name,
      description: model.description,
    }))
  )
}

function getPreferredModel(options: Array<ModelOption>): ModelOption | null {
  return (
    options.find((option) => option.provider === "groq") || options[0] || null
  )
}

function buildConversationTitle(
  content: string,
  attachments: Array<Pick<ComposerAttachment, "name">> = []
) {
  const compact = content.replace(/\s+/g, " ").trim()
  if (!compact) {
    if (attachments.length === 1) {
      return truncateLabel(`Discuss ${attachments[0].name}`, 40)
    }
    if (attachments.length > 1) {
      return `Discuss ${attachments.length} attachments`
    }
    return "New Chat"
  }

  return truncateLabel(compact, 40)
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 102.4) / 10} KB`
  }
  return `${Math.round(bytes / 104857.6) / 10} MB`
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

function createAttachmentId(file: File) {
  return `${file.name}-${file.size}-${file.lastModified}`
}

function isSupportedTextAttachment(file: File) {
  if (file.type.startsWith("text/")) {
    return true
  }

  if (
    [
      "application/json",
      "application/ld+json",
      "application/sql",
      "application/xml",
      "application/x-sh",
      "application/x-yaml",
      "text/csv",
    ].includes(file.type)
  ) {
    return true
  }

  const extension = file.name.split(".").at(-1)?.toLowerCase()
  return Boolean(extension && SUPPORTED_TEXT_FILE_EXTENSIONS.has(extension))
}

function revokeAttachmentPreviews(attachments: Array<ComposerAttachment>) {
  attachments.forEach((attachment) => {
    if (attachment.previewUrl) {
      URL.revokeObjectURL(attachment.previewUrl)
    }
  })
}

function getSpeechRecognitionConstructor() {
  if (typeof window === "undefined") {
    return null
  }

  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null
}

function mergeDraftWithTranscript(seed: string, transcript: string) {
  const cleanedTranscript = transcript.trim()
  if (!cleanedTranscript) {
    return seed
  }

  const cleanedSeed = seed.trimEnd()
  return cleanedSeed ? `${cleanedSeed} ${cleanedTranscript}` : cleanedTranscript
}

function readFileAsDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => {
      reject(new Error(`Could not read ${file.name}.`))
    }
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result)
        return
      }
      reject(new Error(`Could not read ${file.name}.`))
    }
    reader.readAsDataURL(file)
  })
}

function toApiError(error: unknown) {
  if (error instanceof ApiError) {
    return error
  }

  return new ApiError({
    status: null,
    code: "unexpected_error",
    kind: "http",
    message:
      error instanceof Error ? error.message : "An unexpected error occurred.",
  })
}

function getErrorPresentation(error: ApiError | null) {
  if (!error) {
    return null
  }

  if (error.kind === "network") {
    return {
      title: "Network error",
      message: error.message,
    }
  }

  if (error.kind === "validation") {
    return {
      title: "Validation error",
      message: error.message,
    }
  }

  if (error.kind === "provider") {
    return {
      title: "Model provider error",
      message: error.message,
    }
  }

  if (error.kind === "not_found") {
    return {
      title: "Conversation unavailable",
      message: error.message,
    }
  }

  if (error.kind === "server") {
    return {
      title: "Server error",
      message: error.message,
    }
  }

  return {
    title: "Request failed",
    message: error.message,
  }
}

function normalizeAssistantMessage(response: {
  message_id: string
  role: "assistant"
  content: string
  created_at: string
  token_count: number | null
}): LocalMessage {
  return {
    id: response.message_id,
    role: response.role,
    content: response.content,
    attachments: [],
    token_count: response.token_count,
    created_at: response.created_at,
  }
}

function MessageMarkdown({
  content,
  className,
}: {
  content: string
  className?: string
}) {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => (
            <p className="leading-7 whitespace-pre-wrap [&:not(:first-child)]:mt-4">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="mt-4 list-disc space-y-2 pl-6">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mt-4 list-decimal space-y-2 pl-6">{children}</ol>
          ),
          li: ({ children }) => <li className="leading-7">{children}</li>,
          a: ({ children, href }) => (
            <a
              className="text-foreground underline underline-offset-4"
              href={href}
              target="_blank"
              rel="noreferrer"
            >
              {children}
            </a>
          ),
          h1: ({ children }) => (
            <h1 className="mt-6 text-2xl font-semibold tracking-tight first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-6 text-xl font-semibold tracking-tight first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-5 text-lg font-semibold tracking-tight first:mt-0">
              {children}
            </h3>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mt-4 border-s-2 border-border ps-4 text-muted-foreground italic">
              {children}
            </blockquote>
          ),
          code: ({ children, className: codeClassName }) => {
            const isBlock = Boolean(codeClassName)
            if (!isBlock) {
              return (
                <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[0.9em]">
                  {children}
                </code>
              )
            }

            return (
              <code className="block overflow-x-auto rounded-2xl border border-border/70 bg-muted px-4 py-3 font-mono text-sm leading-6">
                {children}
              </code>
            )
          },
          pre: ({ children }) => <div className="mt-4">{children}</div>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

function MessageAttachmentChips({
  attachments,
}: {
  attachments: Array<ApiMessageAttachment>
}) {
  if (attachments.length === 0) {
    return null
  }

  return (
    <div className="flex flex-wrap gap-2">
      {attachments.map((attachment) => {
        const Icon = attachment.kind === "image" ? ImageUp : FileUp
        return (
          <div
            key={`${attachment.kind}-${attachment.name}`}
            className="inline-flex max-w-full items-center gap-2 rounded-full border border-border/70 bg-background px-3 py-1.5 text-xs text-muted-foreground"
          >
            <Icon />
            <span className="truncate">{attachment.name}</span>
          </div>
        )
      })}
    </div>
  )
}

function GitHubMark(props: React.ComponentProps<"svg">) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d="M9.5 18c-3 1-3-1.5-4.5-2" />
      <path d="M15 21v-2.5a2.2 2.2 0 0 0-.6-1.6c2.1-.2 4.3-1 4.3-4.5a3.5 3.5 0 0 0-1-2.4 3.2 3.2 0 0 0-.1-2.3s-.8-.2-2.5 1a8.7 8.7 0 0 0-4.6 0c-1.7-1.2-2.5-1-2.5-1a3.2 3.2 0 0 0-.1 2.3 3.5 3.5 0 0 0-1 2.4c0 3.4 2.1 4.3 4.2 4.5a2.2 2.2 0 0 0-.6 1.6V21" />
      <path d="M12 3.2a8.8 8.8 0 0 1 0 17.6" />
    </svg>
  )
}

function ZerodhaIcon(props: React.ComponentProps<"svg">) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
      <rect x="2" y="4" width="6" height="6" rx="1" />
      <rect x="9" y="4" width="6" height="6" rx="1" />
      <rect x="16" y="4" width="6" height="6" rx="1" />
      <rect x="2" y="11" width="6" height="6" rx="1" opacity="0.6" />
      <rect x="9" y="11" width="6" height="6" rx="1" />
      <rect x="16" y="11" width="6" height="6" rx="1" opacity="0.6" />
    </svg>
  )
}

function ThinkingSteps({ metadata }: { metadata: ApiMessage["metadata"] }) {
  if (!metadata) {
    return null
  }

  return null
}

type HoldingRow = {
  symbol: string
  qty: number
  avgPrice: number
  ltp: number
  investedValue: number
  currentValue: number
  pnl: number
  pnlPct: number
  sector: string | null
}

type PerformancePoint = {
  date: string
  value: number
  invested?: number
  sortKey: number
}

function _pickNum(
  h: Record<string, unknown>,
  keys: Array<string>
): number | null {
  for (const key of keys) {
    const val = h[key]
    if (val === null || val === undefined) continue
    if (typeof val === "number" && !isNaN(val)) return val
    if (typeof val === "string") {
      const n = parseFloat(val.replace(/[\u20b9,%\s,]/g, ""))
      if (!isNaN(n)) return n
    }
  }
  return null
}

function _pickOptionalStr(
  h: Record<string, unknown>,
  keys: Array<string>
): string | null {
  for (const key of keys) {
    const val = h[key]
    if (typeof val === "string" && val.trim()) return val.trim()
  }
  return null
}

function _pickStr(h: Record<string, unknown>, keys: Array<string>): string {
  const value = _pickOptionalStr(h, keys)
  if (value) return value
  return "-"
}

function normalizeHolding(h: Record<string, unknown>): HoldingRow | null {
  const symbol = _pickStr(h, [
    "trading_symbol",
    "tradingSymbol",
    "tradingsymbol",
    "groww_symbol",
    "growwSymbol",
    "symbol",
    "nse_symbol",
    "nseSymbol",
    "name",
    "scrip",
    "symboltoken",
  ])
  const settled =
    _pickNum(h, ["realisedquantity", "realisedQuantity", "realizedquantity"]) ??
    0
  const t1 = _pickNum(h, ["t1quantity", "t1Quantity"]) ?? 0
  const qty =
    _pickNum(h, [
      "quantity",
      "qty",
      "holdingquantity",
      "holdingQuantity",
      "holding_quantity",
      "totalquantity",
      "totalQuantity",
      "total_quantity",
      "freequantity",
      "freeQuantity",
      "free_quantity",
    ]) ?? settled + t1

  const avgPrice =
    _pickNum(h, [
      "average_price",
      "average_buy_price",
      "averageBuyPrice",
      "averagebuyprice",
      "averageprice",
      "averagePrice",
      "avg_buy_price",
      "avgBuyPrice",
      "avgbuyprice",
      "avgprice",
      "avgPrice",
      "avg_price",
      "buy_price",
      "buyPrice",
      "buyprice",
      "costprice",
      "costPrice",
      "cost_price",
    ]) ?? 0

  const ltp =
    _pickNum(h, [
      "ltp",
      "last_price",
      "lastprice",
      "lastPrice",
      "close",
      "close_price",
      "closeprice",
      "closePrice",
      "current_price",
      "currentPrice",
      "currentprice",
    ]) ?? 0

  let investedValue =
    _pickNum(h, [
      "invested",
      "invested_amount",
      "investedamount",
      "investedAmount",
      "investment_amount",
      "investmentAmount",
      "investmentamount",
      "total_investment",
      "totalInvestment",
      "totalinvestment",
      "buy_amount",
      "buyamount",
      "buyAmount",
      "bought_value",
      "boughtValue",
      "boughtvalue",
      // Groww uses holdingValue for current market value, not invested cost.
    ]) ?? qty * avgPrice

  const currentValue =
    _pickNum(h, [
      "currentvalue",
      "currentValue",
      "current_value",
      "marketvalue",
      "marketValue",
      "market_value",
      "ltpvalue",
      "ltpValue",
      "ltp_value",
    ]) ?? qty * ltp

  const resolvedAvgPrice =
    avgPrice > 0
      ? avgPrice
      : qty > 0 && investedValue > 0
        ? investedValue / qty
        : 0
  if (investedValue <= 0 && qty > 0 && resolvedAvgPrice > 0) {
    investedValue = qty * resolvedAvgPrice
  }
  const resolvedLtp =
    ltp > 0 ? ltp : qty > 0 && currentValue > 0 ? currentValue / qty : 0

  const pnl =
    _pickNum(h, [
      "pnl",
      "profit_and_loss",
      "profitandloss",
      "profitAndLoss",
      "unrealised_pnl",
      "unrealisedpnl",
      "unrealisedPnl",
      "unrealisedPnL",
      "unrealized_pnl",
      "unrealizedpnl",
      "unrealizedPnl",
      "unrealizedPnL",
      "gain_loss",
      "gainloss",
      "gainLoss",
      "m2m",
    ]) ?? currentValue - investedValue

  const pnlPct =
    _pickNum(h, [
      "pnl_percentage",
      "pnlPercentage",
      "pnlpercentage",
      "profit_loss_percentage",
      "profitLossPercentage",
      "profitlosspercentage",
      "gain_loss_percentage",
      "gainLossPercentage",
      "gainlosspercentage",
      "return_percent",
      "returnPercent",
    ]) ?? (investedValue > 0 ? (pnl / investedValue) * 100 : 0)
  const sector = _pickOptionalStr(h, [
    "sector",
    "industry",
    "asset_class",
    "assetClass",
    "category",
  ])

  if (qty <= 0 && currentValue <= 0) return null
  return {
    symbol,
    qty,
    avgPrice: resolvedAvgPrice,
    ltp: resolvedLtp,
    investedValue,
    currentValue,
    pnl,
    pnlPct,
    sector,
  }
}

function normalizePerformancePoint(
  point: Record<string, unknown>
): PerformancePoint | null {
  const value = _pickNum(point, [
    "value",
    "portfolio_value",
    "portfolioValue",
    "current_value",
    "currentValue",
    "market_value",
    "marketValue",
    "close",
  ])
  if (value === null) return null

  const rawDate = _pickOptionalStr(point, [
    "date",
    "timestamp",
    "time",
    "datetime",
    "day",
  ])
  if (!rawDate) return null

  const invested =
    _pickNum(point, ["invested", "cost_basis", "costBasis"]) ?? undefined

  const parsed = new Date(rawDate)
  const isValidDate = !Number.isNaN(parsed.getTime())
  return {
    date: isValidDate
      ? parsed.toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
        })
      : rawDate,
    value,
    invested,
    sortKey: isValidDate ? parsed.getTime() : 0,
  }
}

const PIE_COLORS = [
  "#6366f1",
  "#22c55e",
  "#f97316",
  "#ec4899",
  "#06b6d4",
  "#eab308",
  "#94a3b8",
]
const PIE_OTHERS_COLOR = PIE_COLORS[6]

const INDIAN_STOCK_SECTOR_MAP: Record<string, string> = {
  // Banking
  HDFCBANK: "Banking",
  ICICIBANK: "Banking",
  SBIN: "Banking",
  KOTAKBANK: "Banking",
  AXISBANK: "Banking",
  BANDHANBNK: "Banking",
  FEDERALBNK: "Banking",
  IDFCFIRSTB: "Banking",
  INDUSINDBK: "Banking",
  PNB: "Banking",
  BANKBARODA: "Banking",
  CANBK: "Banking",
  UNIONBANK: "Banking",
  YESBANK: "Banking",
  RBLBANK: "Banking",
  // Financial Services
  BAJFINANCE: "Financial Services",
  BAJAJFINSV: "Financial Services",
  HDFCLIFE: "Insurance",
  SBILIFE: "Insurance",
  ICICIGI: "Insurance",
  MUTHOOTFIN: "Financial Services",
  CHOLAFIN: "Financial Services",
  RECLTD: "Financial Services",
  PFC: "Financial Services",
  LICHSGFIN: "Financial Services",
  MANAPPURAM: "Financial Services",
  // IT
  TCS: "IT",
  INFY: "IT",
  WIPRO: "IT",
  HCLTECH: "IT",
  TECHM: "IT",
  LTIM: "IT",
  MPHASIS: "IT",
  PERSISTENT: "IT",
  COFORGE: "IT",
  OFSS: "IT",
  HEXAWARE: "IT",
  // Energy
  RELIANCE: "Energy",
  ONGC: "Energy",
  COALINDIA: "Energy",
  OIL: "Energy",
  NTPC: "Power",
  POWERGRID: "Power",
  TATAPOWER: "Power",
  ADANIPOWER: "Power",
  ADANIGREEN: "Renewable Energy",
  TORNTPOWER: "Power",
  CESC: "Power",
  // Pharma
  SUNPHARMA: "Pharma",
  CIPLA: "Pharma",
  DRREDDY: "Pharma",
  DIVISLAB: "Pharma",
  BIOCON: "Pharma",
  AUROPHARMA: "Pharma",
  LUPIN: "Pharma",
  IPCALAB: "Pharma",
  ALKEM: "Pharma",
  TORNTPHARM: "Pharma",
  GLENMARK: "Pharma",
  // FMCG
  HINDUNILVR: "FMCG",
  ITC: "FMCG",
  BRITANNIA: "FMCG",
  NESTLEIND: "FMCG",
  DABUR: "FMCG",
  COLPAL: "FMCG",
  MARICO: "FMCG",
  TATACONSUM: "FMCG",
  GODREJCP: "FMCG",
  VBL: "FMCG",
  // Automobiles
  MARUTI: "Automobiles",
  TATAMOTORS: "Automobiles",
  "M&M": "Automobiles",
  "BAJAJ-AUTO": "Automobiles",
  HEROMOTOCO: "Automobiles",
  EICHERMOT: "Automobiles",
  TVSMOTORS: "Automobiles",
  MOTHERSON: "Auto Components",
  BHARATFORG: "Auto Components",
  BALKRISIND: "Auto Components",
  // Metals
  TATASTEEL: "Metals & Mining",
  JSWSTEEL: "Metals & Mining",
  HINDALCO: "Metals & Mining",
  VEDL: "Metals & Mining",
  SAIL: "Metals & Mining",
  NATIONALUM: "Metals & Mining",
  NMDC: "Metals & Mining",
  HINDCOPPER: "Metals & Mining",
  // Cement
  ULTRACEMCO: "Cement",
  SHREECEM: "Cement",
  AMBUJACEM: "Cement",
  ACC: "Cement",
  DALMIACEM: "Cement",
  RAMCOCEM: "Cement",
  // Telecom
  BHARTIARTL: "Telecom",
  IDEA: "Telecom",
  TATACOMM: "Telecom",
  // Real Estate
  DLF: "Real Estate",
  GODREJPROP: "Real Estate",
  PRESTIGE: "Real Estate",
  OBEROIRLTY: "Real Estate",
  PHOENIXLTD: "Real Estate",
  // Infrastructure & Capital Goods
  LT: "Infrastructure",
  ADANIPORTS: "Infrastructure",
  ADANIENT: "Conglomerate",
  SIEMENS: "Capital Goods",
  ABB: "Capital Goods",
  BHEL: "Capital Goods",
  THERMAX: "Capital Goods",
  // Consumer & Tech
  TITAN: "Consumer",
  TRENT: "Retail",
  DMART: "Retail",
  NYKAA: "Consumer Tech",
  ZOMATO: "Consumer Tech",
  PAYTM: "Fintech",
}

type BrokerCanvasProps = {
  summary: ApiBrokerPortfolioSummary | null
  holdings: Array<Record<string, unknown>>
  isPortfolioLoading: boolean
  portfolioError: string | null
  onRetry: () => void
  brokerName: string
}

function BrokerCanvas({
  summary,
  holdings,
  isPortfolioLoading,
  portfolioError,
  onRetry,
  brokerName,
}: BrokerCanvasProps) {
  const [pnlSortDir, setPnlSortDir] = React.useState<"asc" | "desc">("desc")
  const [chartPeriod, setChartPeriod] = React.useState<
    "1H" | "1D" | "1M" | "1Y"
  >("1M")

  const holdingRows = React.useMemo<Array<HoldingRow>>(() => {
    const rows = holdings
      .map((h) => normalizeHolding(h))
      .filter((r): r is HoldingRow => r !== null)
    return [...rows].sort((a, b) =>
      pnlSortDir === "desc" ? b.pnl - a.pnl : a.pnl - b.pnl
    )
  }, [holdings, pnlSortDir])

  const totalInvested = holdingRows.reduce((s, r) => s + r.investedValue, 0)
  const totalCurrent = holdingRows.reduce((s, r) => s + r.currentValue, 0)
  const totalPnl = holdingRows.reduce((s, r) => s + r.pnl, 0)
  const resolvedTotalInvested =
    totalInvested > 0 ? totalInvested : (summary?.investment ?? null)
  const resolvedOverallGain =
    holdingRows.length > 0 ? totalPnl : (summary?.overall_gain ?? null)
  const resolvedTotalCurrent =
    totalCurrent > 0
      ? totalCurrent
      : resolvedTotalInvested !== null && resolvedOverallGain !== null
        ? resolvedTotalInvested + resolvedOverallGain
        : null

  // Pie: top-6 sectors shown individually, rest collapsed into "Others"
  const pieData = React.useMemo(() => {
    const sectorMap = new Map<string, { value: number; count: number }>()
    holdingRows.forEach((r) => {
      if (r.currentValue <= 0) return
      let symbolKey = r.symbol.toUpperCase()
      symbolKey = symbolKey.replace(/^(NSE_|BSE_)/, "")
      symbolKey = symbolKey.replace(/-(EQ|BE|BZ|IQ)$/, "")
      symbolKey = symbolKey.replace(/[- ]/g, "")

      let sector =
        (r.sector && r.sector.trim()) ||
        INDIAN_STOCK_SECTOR_MAP[symbolKey] ||
        INDIAN_STOCK_SECTOR_MAP[r.symbol.toUpperCase()] ||
        "Others"

      if (
        sector.toLowerCase() === "other" ||
        sector.toLowerCase() === "others"
      ) {
        sector = "Others"
      }

      const sectorData = sectorMap.get(sector) ?? { value: 0, count: 0 }
      sectorData.value += r.currentValue
      sectorData.count += 1
      sectorMap.set(sector, sectorData)
    })

    let othersValue = sectorMap.get("Others")?.value ?? 0
    let othersCount = sectorMap.get("Others")?.count ?? 0
    sectorMap.delete("Others")

    const sorted = Array.from(sectorMap.entries())
      .map(([name, data]) => ({ name, value: data.value, count: data.count }))
      .sort((a, b) => b.value - a.value)

    const MAX_SLICES = 6
    const top = sorted.slice(0, MAX_SLICES)
    const rest = sorted.slice(MAX_SLICES)

    othersValue += rest.reduce((s, x) => s + x.value, 0)
    othersCount += rest.reduce((s, x) => s + x.count, 0)

    if (othersValue > 0) {
      top.push({ name: "Others", value: othersValue, count: othersCount })
    }

    return top
  }, [holdingRows])

  const chartConfig = React.useMemo<ChartConfig>(() => {
    const cfg: ChartConfig = {}
    pieData.forEach((item) => {
      const idx =
        item.name === "Others" ? 6 : Math.min(pieData.indexOf(item), 5)
      cfg[item.name] = {
        label: item.name,
        color: PIE_COLORS[idx],
      }
    })
    return cfg
  }, [pieData])

  const [historyData, setHistoryData] = React.useState<Array<PerformancePoint>>(
    []
  )
  const [isHistoryLoading, setIsHistoryLoading] = React.useState(false)

  React.useEffect(() => {
    let active = true
    setIsHistoryLoading(true)

    fetchBrokerPortfolioHistory(brokerName, chartPeriod)
      .then((res) => {
        if (!active) return
        const points = res.history
          .map((point) => normalizePerformancePoint(point))
          .filter((point): point is PerformancePoint => point !== null)
          .sort((a, b) => a.sortKey - b.sortKey)
        setHistoryData(points)
      })
      .catch((err) => {
        console.error("Failed to fetch history:", err)
        if (active) setHistoryData([])
      })
      .finally(() => {
        if (active) setIsHistoryLoading(false)
      })

    return () => {
      active = false
    }
  }, [brokerName, chartPeriod])

  const lineData = React.useMemo(() => {
    const invested = resolvedTotalInvested ?? 0
    const allPoints = historyData

    if (allPoints.length === 0 && invested > 0) {
      const today = new Date().toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      })
      const currentVal = resolvedTotalCurrent ?? invested
      return [
        {
          date: today,
          sortKey: Date.now(),
          value: currentVal,
          current: currentVal,
          invested,
        },
      ]
    }

    return allPoints.map((p) => {
      let displayDate = p.date
      if (chartPeriod === "1H" || chartPeriod === "1D") {
        try {
          const parsed = new Date(p.sortKey)
          if (!isNaN(parsed.getTime())) {
            displayDate = parsed.toLocaleTimeString("en-US", {
              hour: "numeric",
              minute: "2-digit",
            })
          }
        } catch {
          displayDate = p.date
        }
      } else {
        try {
          const parsed = new Date(p.sortKey)
          if (!isNaN(parsed.getTime())) {
            displayDate = parsed.toLocaleDateString("en-IN", {
              month: "short",
              day: "numeric",
            })
          }
        } catch {
          displayDate = p.date
        }
      }
      const pointInvested = p.invested ?? invested
      return {
        ...p,
        date: displayDate,
        current: p.value,
        invested: pointInvested,
      }
    })
  }, [historyData, chartPeriod, resolvedTotalInvested, resolvedTotalCurrent])

  const isPositivePnl = (resolvedOverallGain ?? 0) >= 0

  const fmt = (v: number | null) => formatBrokerCurrency(v)
  const fmtPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`

  if (portfolioError && !isPortfolioLoading) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <div className="flex items-center gap-3">
              <AlertCircle className="size-5 text-destructive" />
              <CardTitle className="text-destructive">
                Failed to load portfolio
              </CardTitle>
            </div>
            <CardDescription>{portfolioError}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="outline"
              size="sm"
              onClick={onRetry}
              className="gap-2"
            >
              <RefreshCw data-icon="inline-start" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto bg-background">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 p-4 sm:p-6">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Card>
            <CardHeader className="pb-1">
              <CardDescription>Total Invested</CardDescription>
              <CardTitle className="text-2xl">
                {isPortfolioLoading ? (
                  <Skeleton className="h-7 w-28" />
                ) : (
                  <span>Rs {fmt(resolvedTotalInvested)}</span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isPortfolioLoading ? (
                <Skeleton className="h-4 w-20" />
              ) : (
                <Badge variant="secondary">
                  <TrendingUp data-icon="inline-start" />
                  Portfolio cost
                </Badge>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-1">
              <CardDescription>Current Value</CardDescription>
              <CardTitle className="text-2xl">
                {isPortfolioLoading ? (
                  <Skeleton className="h-7 w-28" />
                ) : (
                  <span>Rs {fmt(resolvedTotalCurrent)}</span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isPortfolioLoading ? (
                <Skeleton className="h-4 w-20" />
              ) : (
                <Badge variant="secondary">
                  <ChartCandlestick data-icon="inline-start" />
                  Live market value
                </Badge>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-1">
              <CardDescription>Overall Gain / Loss</CardDescription>
              <CardTitle className="text-2xl">
                {isPortfolioLoading ? (
                  <Skeleton className="h-7 w-28" />
                ) : (
                  <span
                    className={cn(
                      (resolvedOverallGain ?? 0) >= 0
                        ? "text-emerald-500"
                        : "text-destructive"
                    )}
                  >
                    Rs {fmt(resolvedOverallGain)}
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isPortfolioLoading ? (
                <Skeleton className="h-4 w-20" />
              ) : (resolvedOverallGain ?? 0) >= 0 ? (
                <Badge variant="secondary" className="text-emerald-500">
                  <TrendingUp data-icon="inline-start" />
                  {resolvedTotalInvested && resolvedTotalInvested > 0
                    ? fmtPct(
                        ((resolvedOverallGain ?? 0) / resolvedTotalInvested) *
                          100
                      )
                    : "Unrealised gain"}
                </Badge>
              ) : (
                <Badge variant="secondary" className="text-destructive">
                  <TrendingDown data-icon="inline-start" />
                  {resolvedTotalInvested && resolvedTotalInvested > 0
                    ? fmtPct(
                        ((resolvedOverallGain ?? 0) / resolvedTotalInvested) *
                          100
                      )
                    : "Unrealised loss"}
                </Badge>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-1">
              <CardDescription>Available Funds</CardDescription>
              <CardTitle className="text-2xl">
                {isPortfolioLoading ? (
                  <Skeleton className="h-7 w-28" />
                ) : (
                  <span>Rs {fmt(summary?.funds ?? null)}</span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isPortfolioLoading ? (
                <Skeleton className="h-4 w-20" />
              ) : (
                <Badge variant="secondary">Cash balance</Badge>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <Card className="xl:col-span-2">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <div className="space-y-1">
                <CardTitle>Portfolio Value</CardTitle>
                <CardDescription>
                  Invested amount vs current market value
                </CardDescription>
              </div>
              <div className="flex items-center gap-1 text-xs">
                {(["1H", "1D", "1M", "1Y"] as const).map((p) => (
                  <button
                    key={p}
                    onClick={() => setChartPeriod(p)}
                    className={[
                      "rounded px-2 py-1 font-medium transition-colors",
                      chartPeriod === p
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground",
                    ].join(" ")}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              {isPortfolioLoading || isHistoryLoading ? (
                <div className="flex h-[260px] items-center justify-center">
                  <Skeleton className="h-full w-full" />
                </div>
              ) : lineData.length === 0 ? (
                <div className="flex h-[260px] flex-col items-center justify-center gap-2 text-center">
                  <ChartCandlestick className="size-8 text-muted-foreground/40" />
                  <p className="text-sm text-muted-foreground">
                    No data for {chartPeriod} - try a longer period
                  </p>
                </div>
              ) : (
                <ChartContainer
                  config={{
                    current: { label: "Current Value", color: "#22c55e" },
                    invested: { label: "Invested", color: "#94a3b8" },
                  }}
                  className="h-[260px] w-full"
                >
                  <RechartsLineChart
                    data={lineData}
                    margin={{ top: 20, right: 20, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      vertical={false}
                      opacity={0.3}
                    />
                    <XAxis
                      dataKey="date"
                      tickLine={false}
                      axisLine={false}
                      tickMargin={10}
                      fontSize={11}
                    />
                    <YAxis
                      tickFormatter={(val: number) => {
                        if (val >= 10000000)
                          return `Rs ${(val / 10000000).toFixed(1)}Cr`
                        if (val >= 100000)
                          return `Rs ${(val / 100000).toFixed(1)}L`
                        if (val >= 1000) return `Rs ${(val / 1000).toFixed(0)}k`
                        return `Rs ${val.toFixed(0)}`
                      }}
                      tickLine={false}
                      axisLine={false}
                      tickMargin={8}
                      fontSize={11}
                      width={68}
                    />
                    <ChartTooltip
                      content={
                        <ChartTooltipContent
                          formatter={(value, name) => {
                            const v = value as number
                            const label =
                              name === "current" ? "Current" : "Invested"
                            const color =
                              name === "current" ? "#22c55e" : "#94a3b8"
                            return (
                              <div className="flex items-center gap-2">
                                <span
                                  className="inline-block h-2 w-2 rounded-full"
                                  style={{ background: color }}
                                />
                                <span className="text-xs text-muted-foreground">
                                  {label}
                                </span>
                                <span className="ml-auto text-xs font-semibold">
                                  Rs {formatBrokerCurrency(v)}
                                </span>
                              </div>
                            )
                          }}
                        />
                      }
                    />
                    <Line
                      type="monotone"
                      dataKey="invested"
                      stroke="#94a3b8"
                      strokeWidth={2}
                      strokeDasharray="5 4"
                      dot={false}
                      activeDot={{ r: 4, strokeWidth: 0 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="current"
                      stroke={isPositivePnl ? "#22c55e" : "#ef4444"}
                      strokeWidth={3}
                      dot={false}
                      activeDot={{
                        r: 5,
                        fill: isPositivePnl ? "#16a34a" : "#dc2626",
                        strokeWidth: 0,
                      }}
                    />
                  </RechartsLineChart>
                </ChartContainer>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Portfolio Allocation</CardTitle>
              <CardDescription>By current market value</CardDescription>
            </CardHeader>
            <CardContent>
              {isPortfolioLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Skeleton className="size-40 rounded-full" />
                </div>
              ) : pieData.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-10 text-center">
                  <ChartCandlestick className="size-8 text-muted-foreground/40" />
                  <p className="text-sm text-muted-foreground">No data</p>
                </div>
              ) : (
                <ChartContainer
                  config={chartConfig}
                  className="mx-auto aspect-square max-h-[250px]"
                >
                  <RechartsPieChart>
                    <ChartTooltip
                      content={
                        <ChartTooltipContent
                          nameKey="name"
                          formatter={(value, name) => (
                            <div className="flex flex-col gap-0.5">
                              <span className="font-medium">{name}</span>
                              <span className="text-muted-foreground">
                                Rs {formatBrokerCurrency(value as number)}
                              </span>
                              <span className="text-muted-foreground">
                                {resolvedTotalCurrent &&
                                resolvedTotalCurrent > 0
                                  ? fmtPct(
                                      ((value as number) /
                                        resolvedTotalCurrent) *
                                        100
                                    )
                                  : "-"}
                              </span>
                            </div>
                          )}
                        />
                      }
                    />
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius="50%"
                      outerRadius="80%"
                      paddingAngle={2}
                    >
                      {pieData.map((entry, index) => (
                        <Cell
                          key={entry.name}
                          fill={
                            entry.name === "Others"
                              ? PIE_OTHERS_COLOR
                              : PIE_COLORS[Math.min(index, 5)]
                          }
                          stroke="transparent"
                        />
                      ))}
                    </Pie>
                    <ChartLegend
                      content={<ChartLegendContent nameKey="name" />}
                      className="mt-2 flex-wrap justify-center gap-x-4 gap-y-2"
                    />
                  </RechartsPieChart>
                </ChartContainer>
              )}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Holdings</CardTitle>
            <CardDescription>
              {isPortfolioLoading
                ? "Loading..."
                : `${holdingRows.length} position${holdingRows.length !== 1 ? "s" : ""}`}
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {isPortfolioLoading ? (
              <div className="flex flex-col gap-2 p-4">
                {[...Array(5)].map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : holdingRows.length === 0 ? (
              <div className="flex flex-col items-center gap-2 p-10 text-center">
                <ChartCandlestick className="size-10 text-muted-foreground/40" />
                <p className="text-sm text-muted-foreground">
                  No holdings found
                </p>
              </div>
            ) : (
              <div className="max-h-[420px] overflow-y-auto">
                <Table>
                  <TableHeader className="sticky top-0 z-10 bg-card">
                    <TableRow>
                      <TableHead>Stock</TableHead>
                      <TableHead className="text-end">LTP</TableHead>
                      <TableHead className="text-end">Qty</TableHead>
                      <TableHead className="text-end">Avg Buy</TableHead>
                      <TableHead className="text-end">
                        <button
                          className="inline-flex items-center gap-1 font-medium text-foreground"
                          onClick={() =>
                            setPnlSortDir((d) =>
                              d === "desc" ? "asc" : "desc"
                            )
                          }
                        >
                          P/L (Rs)
                          <ArrowUpDown className="size-3" />
                        </button>
                      </TableHead>
                      <TableHead className="text-end">P/L %</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {holdingRows.map((row) => {
                      const displaySymbol =
                        row.symbol
                          .replace(/^(NSE_|BSE_)/i, "")
                          .replace(/(-EQ|:EQ)$/i, "") || row.symbol
                      return (
                        <TableRow key={row.symbol}>
                          <TableCell className="font-medium">
                            {displaySymbol}
                          </TableCell>
                          <TableCell className="text-end">
                            Rs {formatBrokerCurrency(row.ltp)}
                          </TableCell>
                          <TableCell className="text-end">{row.qty}</TableCell>
                          <TableCell className="text-end">
                            Rs {formatBrokerCurrency(row.avgPrice)}
                          </TableCell>
                          <TableCell
                            className={cn(
                              "text-end font-medium",
                              row.pnl >= 0
                                ? "text-emerald-500"
                                : "text-destructive"
                            )}
                          >
                            {row.pnl >= 0 ? "+" : ""}
                            {formatBrokerCurrency(row.pnl)}
                          </TableCell>
                          <TableCell className="text-end">
                            <Badge
                              variant="secondary"
                              className={cn(
                                row.pnlPct >= 0
                                  ? "text-emerald-500"
                                  : "text-destructive"
                              )}
                            >
                              {fmtPct(row.pnlPct)}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                  <TableFooter>
                    <TableRow>
                      <TableCell colSpan={3} className="font-semibold">
                        Total
                      </TableCell>
                      <TableCell className="text-end font-semibold">
                        Rs {formatBrokerCurrency(resolvedTotalInvested ?? 0)}
                      </TableCell>
                      <TableCell
                        className={cn(
                          "text-end font-semibold",
                          (resolvedOverallGain ?? 0) >= 0
                            ? "text-emerald-500"
                            : "text-destructive"
                        )}
                      >
                        {(resolvedOverallGain ?? 0) >= 0 ? "+" : ""}
                        {formatBrokerCurrency(resolvedOverallGain ?? 0)}
                      </TableCell>
                      <TableCell className="text-end">
                        <Badge
                          variant="secondary"
                          className={cn(
                            (resolvedOverallGain ?? 0) >= 0
                              ? "text-emerald-500"
                              : "text-destructive"
                          )}
                        >
                          {resolvedTotalInvested && resolvedTotalInvested > 0
                            ? fmtPct(
                                ((resolvedOverallGain ?? 0) /
                                  resolvedTotalInvested) *
                                  100
                              )
                            : "-"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  </TableFooter>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function App() {
  const {
    getToken,
    isLoaded: isClerkLoaded,
    isSignedIn,
    userId: clerkUserId,
  } = useAuth()
  const { user } = useUser()
  const { sendStreamingMessage } = useStreamingChat()
  const [modelCatalog, setModelCatalog] = React.useState<
    Array<ApiModelsResponse["providers"][number]>
  >([])
  const [selectedModelKey, setSelectedModelKey] = React.useState("")
  const [conversations, setConversations] = React.useState<
    Array<ApiConversation>
  >([])
  const [currentConversationId, setCurrentConversationId] = React.useState<
    string | null
  >(null)
  const [messages, setMessages] = React.useState<Array<LocalMessage>>([])
  const [draft, setDraft] = React.useState("")
  const [attachments, setAttachments] = React.useState<
    Array<ComposerAttachment>
  >([])
  const [composerIssue, setComposerIssue] = React.useState<string | null>(null)
  const [composerNotice, setComposerNotice] = React.useState<string | null>(
    null
  )
  const [error, setError] = React.useState<ApiError | null>(null)
  const [isBootstrapping, setIsBootstrapping] = React.useState(true)
  const [isConversationLoading, setIsConversationLoading] =
    React.useState(false)
  const [isSending, setIsSending] = React.useState(false)
  const [isListening, setIsListening] = React.useState(false)
  const [isAssetsDialogOpen, setIsAssetsDialogOpen] = React.useState(false)
  const [assets, setAssets] = React.useState<Array<ApiStoredAsset>>([])
  const [isAssetsLoading, setIsAssetsLoading] = React.useState(false)
  const [isUploadingAssets, setIsUploadingAssets] = React.useState(false)
  const [deletingAssetId, setDeletingAssetId] = React.useState<string | null>(
    null
  )
  const [isMoreDialogOpen, setIsMoreDialogOpen] = React.useState(false)
  const [isToolsDialogOpen, setIsToolsDialogOpen] = React.useState(false)
  const [activeView, setActiveView] = React.useState<
    "chat" | "market" | "broker"
  >("chat")
  const [isBrokersDialogOpen, setIsBrokersDialogOpen] = React.useState(false)
  const [isDisconnectConfirmOpen, setIsDisconnectConfirmOpen] =
    React.useState(false)
  const [brokerStep, setBrokerStep] = React.useState<1 | 2>(1)
  const [selectedBroker, setSelectedBroker] =
    React.useState<BrokerOption>("angel-one")
  const [selectedConnectedBroker, setSelectedConnectedBroker] =
    React.useState<BrokerOption | null>(null)
  const [brokerClientId, setBrokerClientId] = React.useState("")
  const [brokerPassword, setBrokerPassword] = React.useState("")
  const [showBrokerPassword, setShowBrokerPassword] = React.useState(false)
  const [brokerTotp, setBrokerTotp] = React.useState("")
  const [brokerStatus, setBrokerStatus] = React.useState<BrokerStatusMap>({})
  const [brokerFormError, setBrokerFormError] = React.useState<string | null>(
    null
  )
  const [brokerStatusError, setBrokerStatusError] = React.useState<
    string | null
  >(null)
  const [isBrokerStatusLoading, setIsBrokerStatusLoading] =
    React.useState(false)
  const [isBrokerConnecting, setIsBrokerConnecting] = React.useState(false)
  const [isBrokerDisconnecting, setIsBrokerDisconnecting] =
    React.useState(false)
  const [brokerPortfolioSummary, setBrokerPortfolioSummary] =
    React.useState<ApiBrokerPortfolioSummary | null>(null)
  const [brokerPortfolioHoldings, setBrokerPortfolioHoldings] = React.useState<
    Array<Record<string, unknown>>
  >([])
  const [brokerPortfolioError, setBrokerPortfolioError] = React.useState<
    string | null
  >(null)
  const [brokerRetryTrigger, setBrokerRetryTrigger] = React.useState(0)
  const [isBrokerPortfolioLoading, setIsBrokerPortfolioLoading] =
    React.useState(false)
  const [isClearingAllConversations, setIsClearingAllConversations] =
    React.useState(false)
  const [mcpProviders, setMcpProviders] = React.useState<Array<ApiMcpProvider>>(
    []
  )
  const [mcpConnections, setMcpConnections] = React.useState<
    Array<ApiMcpConnection>
  >([])
  const [isMcpLoading, setIsMcpLoading] = React.useState(false)
  const [mcpBusyProvider, setMcpBusyProvider] = React.useState<string | null>(
    null
  )
  const [mcpError, setMcpError] = React.useState<string | null>(null)
  const [copiedMessageId, setCopiedMessageId] = React.useState<string | null>(
    null
  )
  const loadConversationAbortRef = React.useRef<AbortController | null>(null)
  const messageEndRef = React.useRef<HTMLDivElement | null>(null)
  const draftTextareaRef = React.useRef<HTMLTextAreaElement | null>(null)
  const attachmentInputRef = React.useRef<HTMLInputElement | null>(null)
  const assetInputRef = React.useRef<HTMLInputElement | null>(null)
  const recognitionRef = React.useRef<SpeechRecognition | null>(null)
  const attachmentsRef = React.useRef<Array<ComposerAttachment>>([])
  const speechDraftSeedRef = React.useRef("")
  const speechFinalTranscriptRef = React.useRef("")
  const shouldKeepListeningRef = React.useRef(false)
  const sendLockRef = React.useRef(false)
  const isAuthenticated = isClerkLoaded && isSignedIn === true
  const profileDisplayName =
    user?.fullName || user?.username || user?.firstName || "Account"

  const modelOptions = flattenModelOptions(modelCatalog)
  const currentConversation: ApiConversation | null =
    conversations.find(
      (conversation) => conversation.id === currentConversationId
    ) || null
  const selectedModel: ModelOption | null =
    modelOptions.find((option) => option.key === selectedModelKey) ||
    getPreferredModel(modelOptions)
  const mcpConnectionByProvider = React.useMemo(
    () =>
      new Map(
        mcpConnections.map((connection) => [connection.provider, connection])
      ),
    [mcpConnections]
  )
  const errorPresentation = getErrorPresentation(error)
  const connectedBrokerOptions = React.useMemo(() => {
    return brokerCards.filter((broker) =>
      getConnectedBrokerIds(brokerStatus).includes(broker.id)
    )
  }, [brokerStatus])
  const connectedBrokerIds = React.useMemo(
    () => connectedBrokerOptions.map((broker) => broker.id),
    [connectedBrokerOptions]
  )
  const selectedConnectedBrokerId =
    selectedConnectedBroker &&
    connectedBrokerIds.includes(selectedConnectedBroker)
      ? selectedConnectedBroker
      : (connectedBrokerIds.at(0) ?? null)
  const isBrokerConnected = selectedConnectedBrokerId !== null
  const activeConnectedBroker =
    brokerCards.find((broker) => broker.id === selectedConnectedBrokerId) ??
    null
  const selectedBrokerStatus = brokerStatus[selectedBroker] ?? null
  const canAddBroker = brokerCards.some(
    (broker) =>
      broker.isAvailable && brokerStatus[broker.id]?.is_active !== true
  )
  const activeProvider =
    currentConversation?.provider ?? selectedModel?.provider ?? null
  const canAttachImages =
    activeProvider === "openai" || activeProvider === "google"
  const hasComposerContent = draft.trim().length > 0 || attachments.length > 0

  const redirectToSignIn = React.useCallback(() => {
    if (typeof window === "undefined") {
      return
    }

    const redirectUrl = encodeURIComponent(
      `${window.location.pathname}${window.location.search}`
    )
    window.location.assign(`/sign-in?redirect_url=${redirectUrl}`)
  }, [])

  const resetBrokerDialogState = React.useCallback(() => {
    setSelectedBroker("angel-one")
    setBrokerClientId("")
    setBrokerPassword("")
    setShowBrokerPassword(false)
    setBrokerTotp("")
    setBrokerStep(1)
    setBrokerFormError(null)
    setBrokerStatusError(null)
  }, [])

  React.useEffect(() => {
    setSelectedConnectedBroker((currentBroker) => {
      if (currentBroker && connectedBrokerIds.includes(currentBroker)) {
        return currentBroker
      }

      return connectedBrokerIds.at(0) ?? null
    })
  }, [connectedBrokerIds])

  const loadBrokerStatus = React.useCallback(
    async ({ silent = false }: { silent?: boolean } = {}) => {
      if (!silent) {
        setIsBrokerStatusLoading(true)
      }
      setBrokerStatusError(null)

      try {
        const response = await fetchBrokerStatus()
        const nextStatus: BrokerStatusMap = {}

        for (const item of response.items) {
          const brokerKey = fromApiBrokerName(item.broker)
          if (brokerKey) {
            nextStatus[brokerKey] = item
          }
        }

        setBrokerStatus(nextStatus)

        return nextStatus
      } catch (caughtError) {
        const nextError = toApiError(caughtError)
        setBrokerStatusError(nextError.message)
        if (!silent) {
          throw nextError
        }
        return null
      } finally {
        if (!silent) {
          setIsBrokerStatusLoading(false)
        }
      }
    },
    []
  )

  const handleBrokerDialogOpenChange = React.useCallback(
    (open: boolean) => {
      setIsBrokersDialogOpen(open)
      if (open) {
        setBrokerFormError(null)
        void loadBrokerStatus()
        return
      }
      resetBrokerDialogState()
    },
    [loadBrokerStatus, resetBrokerDialogState]
  )

  const openAddBrokerDialog = React.useCallback(() => {
    setSelectedBroker(getFirstConnectableBroker(brokerStatus))
    setBrokerStep(1)
    handleBrokerDialogOpenChange(true)
  }, [brokerStatus, handleBrokerDialogOpenChange])

  const handleBrokerConnect = React.useCallback(async () => {
    if (!isAuthenticated) {
      redirectToSignIn()
      return
    }

    if (selectedBroker !== "angel-one" && selectedBroker !== "groww") {
      setBrokerFormError("This broker is not available yet.")
      return
    }

    setIsBrokerConnecting(true)
    setBrokerFormError(null)

    try {
      if (selectedBroker === "angel-one") {
        await connectAngelOneBroker({
          client_code: brokerClientId.trim(),
          password: brokerPassword,
          totp: brokerTotp,
        })
      } else {
        await connectGrowwBroker({
          api_key: brokerClientId.trim(),
          totp: brokerTotp,
        })
      }
      await loadBrokerStatus()
      setSelectedConnectedBroker(selectedBroker)
      setIsBrokersDialogOpen(false)
      resetBrokerDialogState()
      setActiveView("broker")
      toast.success(
        `${selectedBroker === "angel-one" ? "Angel One" : "Groww"} connected`
      )
    } catch (caughtError) {
      const nextError = toApiError(caughtError)
      setBrokerFormError(nextError.message)
    } finally {
      setIsBrokerConnecting(false)
    }
  }, [
    brokerClientId,
    brokerPassword,
    brokerTotp,
    isAuthenticated,
    loadBrokerStatus,
    redirectToSignIn,
    resetBrokerDialogState,
    selectedBroker,
  ])

  const handleBrokerDisconnect = React.useCallback(async () => {
    const brokerToDisconnect = selectedConnectedBrokerId
    if (!brokerToDisconnect) {
      setIsDisconnectConfirmOpen(false)
      return
    }

    setIsBrokerDisconnecting(true)
    setBrokerFormError(null)
    setBrokerStatusError(null)

    try {
      if (brokerToDisconnect === "angel-one") {
        await disconnectAngelOneBroker()
      } else if (brokerToDisconnect === "groww") {
        await disconnectGrowwBroker()
      } else {
        setBrokerStatusError("This broker is not available yet.")
        return
      }

      const nextStatus = await loadBrokerStatus()
      const nextConnectedBroker =
        nextStatus === null
          ? null
          : (getConnectedBrokerIds(nextStatus).at(0) ?? null)

      setSelectedConnectedBroker(nextConnectedBroker)
      setBrokerPortfolioSummary(null)
      setBrokerPortfolioHoldings([])
      setBrokerStep(1)
      setIsDisconnectConfirmOpen(false)
      if (!nextConnectedBroker) {
        setActiveView("chat")
      }
      toast.success(
        `${
          brokerToDisconnect === "angel-one" ? "Angel One" : "Groww"
        } disconnected`
      )
    } catch (caughtError) {
      const nextError = toApiError(caughtError)
      setBrokerStatusError(nextError.message)
    } finally {
      setIsBrokerDisconnecting(false)
    }
  }, [loadBrokerStatus, selectedConnectedBrokerId])

  const loadMcpTools = React.useCallback(async () => {
    setIsMcpLoading(true)
    setMcpError(null)

    try {
      const [providersResponse, connectionsResponse] = await Promise.all([
        listMcpProviders(),
        listMcpConnections(),
      ])
      setMcpProviders(providersResponse)
      setMcpConnections(connectionsResponse.items)
    } catch (caughtError) {
      const nextError = toApiError(caughtError)
      setMcpError(nextError.message)
    } finally {
      setIsMcpLoading(false)
    }
  }, [])

  const handleToolsDialogOpenChange = React.useCallback(
    (open: boolean) => {
      setIsToolsDialogOpen(open)
      if (open) {
        void loadMcpTools()
      }
    },
    [loadMcpTools]
  )

  const handleMcpProviderToggle = React.useCallback(
    async (provider: ApiMcpProvider, checked: boolean) => {
      setMcpBusyProvider(provider.provider)
      setMcpError(null)

      try {
        if (checked) {
          await connectMcpProvider({
            provider: provider.provider,
            transport: provider.transport,
            server_url: provider.server_url,
          })
          toast.success(`${provider.label} MCP connected`)
        } else {
          await disconnectMcpProvider(provider.provider)
          toast.success(`${provider.label} MCP disconnected`)
        }

        const connectionsResponse = await listMcpConnections()
        setMcpConnections(connectionsResponse.items)
      } catch (caughtError) {
        const nextError = toApiError(caughtError)
        setMcpError(nextError.message)
      } finally {
        setMcpBusyProvider(null)
      }
    },
    []
  )

  React.useEffect(() => {
    if (activeView !== "broker" || !selectedConnectedBrokerId) {
      if (!selectedConnectedBrokerId) {
        setBrokerPortfolioSummary(null)
        setBrokerPortfolioHoldings([])
        setBrokerPortfolioError(null)
      }
      setIsBrokerPortfolioLoading(false)
      return
    }

    let isCancelled = false
    const brokerToLoad = selectedConnectedBrokerId

    async function loadBrokerPortfolio() {
      setIsBrokerPortfolioLoading(true)
      setBrokerPortfolioError(null)

      try {
        let response
        if (brokerToLoad === "angel-one") {
          response = await fetchAngelOnePortfolio()
        } else if (brokerToLoad === "groww") {
          response = await fetchGrowwPortfolio()
        } else {
          setBrokerPortfolioSummary(null)
          setBrokerPortfolioHoldings([])
          setBrokerPortfolioError("Portfolio is not available for this broker.")
          return
        }

        if (isCancelled) {
          return
        }

        setBrokerPortfolioSummary(response.summary)
        setBrokerPortfolioHoldings(response.holdings)
      } catch (caughtError) {
        if (isCancelled) {
          return
        }

        const nextError = toApiError(caughtError)
        if (nextError.code === "broker_session_not_found") {
          setBrokerPortfolioSummary(null)
          setBrokerPortfolioHoldings([])
          setBrokerStatus((currentStatus) => {
            const nextStatus = { ...currentStatus }
            delete nextStatus[brokerToLoad]
            return nextStatus
          })
          const nextConnectedBroker =
            connectedBrokerIds.find((broker) => broker !== brokerToLoad) ?? null
          setSelectedConnectedBroker(nextConnectedBroker)
          if (!nextConnectedBroker) {
            setActiveView("chat")
          }
          toast.error(
            `Broker session expired. Please reconnect ${
              brokerToLoad === "angel-one" ? "Angel One" : "Groww"
            }.`
          )
          return
        }

        setBrokerPortfolioSummary(null)
        setBrokerPortfolioHoldings([])
        setBrokerPortfolioError(nextError.message)
      } finally {
        if (!isCancelled) {
          setIsBrokerPortfolioLoading(false)
        }
      }
    }

    void loadBrokerPortfolio()

    return () => {
      isCancelled = true
    }
  }, [
    activeView,
    brokerRetryTrigger,
    connectedBrokerIds,
    selectedConnectedBrokerId,
  ])

  React.useEffect(() => {
    setAuthTokenProvider(isAuthenticated ? () => getToken() : null)

    return () => {
      setAuthTokenProvider(null)
    }
  }, [getToken, isAuthenticated])

  React.useEffect(() => {
    if (!isClerkLoaded) {
      return
    }

    async function bootstrap() {
      if (!clerkUserId) {
        getChatUserId()
      }
      setIsBootstrapping(true)
      setError(null)

      try {
        const [modelsResponse, conversationsResponse] = await Promise.all([
          fetchModels(),
          listConversations(),
        ])

        const nextModelOptions = flattenModelOptions(modelsResponse.providers)
        const preferredModel = getPreferredModel(nextModelOptions)

        setModelCatalog(modelsResponse.providers)
        await loadBrokerStatus({ silent: true })
        setSelectedModelKey(preferredModel ? preferredModel.key : "")
        React.startTransition(() => {
          setConversations(conversationsResponse.items)
        })

        const firstConversation = conversationsResponse.items.at(0)
        if (firstConversation) {
          await loadConversation(firstConversation.id, nextModelOptions)
        }
      } catch (caughtError) {
        if (isAbortError(caughtError)) {
          return
        }
        setError(toApiError(caughtError))
      } finally {
        setIsBootstrapping(false)
      }
    }

    void bootstrap()
  }, [clerkUserId, isClerkLoaded, loadBrokerStatus])

  React.useEffect(() => {
    attachmentsRef.current = attachments
  }, [attachments])

  React.useEffect(() => {
    return () => {
      loadConversationAbortRef.current?.abort()
      recognitionRef.current?.abort()
      revokeAttachmentPreviews(attachmentsRef.current)
    }
  }, [])

  React.useEffect(() => {
    messageEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    })
  }, [currentConversationId, messages.length])

  React.useLayoutEffect(() => {
    const textarea = draftTextareaRef.current
    if (!textarea) {
      return
    }

    textarea.style.height = "0px"
    const nextHeight = Math.min(textarea.scrollHeight, MAX_DRAFT_HEIGHT)
    textarea.style.height = `${nextHeight}px`
    textarea.style.overflowY =
      textarea.scrollHeight > MAX_DRAFT_HEIGHT ? "auto" : "hidden"
  }, [draft])

  function stopVoiceInput() {
    shouldKeepListeningRef.current = false
    recognitionRef.current?.stop()
    setIsListening(false)
  }

  function handleVoiceInputToggle() {
    if (isListening) {
      stopVoiceInput()
      return
    }

    const Recognition = getSpeechRecognitionConstructor()
    if (!Recognition) {
      setComposerIssue(
        "Speech recognition is not available in this browser. Use Chrome or Edge for voice input."
      )
      return
    }

    const recognition = recognitionRef.current ?? new Recognition()
    recognitionRef.current = recognition
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang =
      typeof navigator !== "undefined" ? navigator.language : "en-US"

    speechDraftSeedRef.current = draft.trimEnd()
    speechFinalTranscriptRef.current = ""
    shouldKeepListeningRef.current = true

    recognition.onresult = (event) => {
      let nextFinalTranscript = speechFinalTranscriptRef.current
      let interimTranscript = ""

      for (
        let index = event.resultIndex;
        index < event.results.length;
        index += 1
      ) {
        const result = event.results[index]
        const transcript = result[0].transcript
        if (result.isFinal) {
          nextFinalTranscript += transcript
        } else {
          interimTranscript += transcript
        }
      }

      speechFinalTranscriptRef.current = nextFinalTranscript
      setDraft(
        mergeDraftWithTranscript(
          speechDraftSeedRef.current,
          `${nextFinalTranscript} ${interimTranscript}`
        )
      )
    }

    recognition.onerror = (event) => {
      if (event.error === "aborted" || event.error === "no-speech") {
        return
      }

      shouldKeepListeningRef.current = false
      setIsListening(false)

      if (
        event.error === "not-allowed" ||
        event.error === "service-not-allowed"
      ) {
        setComposerIssue(
          "Microphone access is blocked. Allow microphone permissions and try again."
        )
        return
      }

      if (event.error === "audio-capture") {
        setComposerIssue(
          "No microphone was found. Connect a microphone and try again."
        )
        return
      }

      setComposerIssue("Speech recognition stopped unexpectedly. Try again.")
    }

    recognition.onend = () => {
      if (!shouldKeepListeningRef.current) {
        setIsListening(false)
        return
      }

      try {
        recognition.start()
      } catch {
        shouldKeepListeningRef.current = false
        setIsListening(false)
      }
    }

    try {
      recognition.start()
      setComposerIssue(null)
      setIsListening(true)
    } catch {
      shouldKeepListeningRef.current = false
      setIsListening(false)
      setComposerIssue(
        "Speech recognition could not start. Check microphone permissions and try again."
      )
    }
  }

  function handleRemoveAttachment(attachmentId: string) {
    setAttachments((currentAttachments) => {
      const attachmentToRemove = currentAttachments.find(
        (attachment) => attachment.id === attachmentId
      )
      if (attachmentToRemove?.previewUrl) {
        URL.revokeObjectURL(attachmentToRemove.previewUrl)
      }

      return currentAttachments.filter(
        (attachment) => attachment.id !== attachmentId
      )
    })
  }

  function addComposerAttachments(fileList: FileList | null) {
    if (!fileList) {
      return
    }

    const nextAttachments = [...attachments]
    const existingIds = new Set(
      nextAttachments.map((attachment) => attachment.id)
    )
    let nextComposerIssue: string | null = null

    for (const file of Array.from(fileList)) {
      if (nextAttachments.length >= MAX_ATTACHMENT_COUNT) {
        nextComposerIssue = `You can attach up to ${MAX_ATTACHMENT_COUNT} items per message.`
        break
      }

      const attachmentId = createAttachmentId(file)
      if (existingIds.has(attachmentId)) {
        continue
      }

      const kind: ComposerAttachment["kind"] = file.type.startsWith("image/")
        ? "image"
        : "file"

      if (kind === "image") {
        if (!file.type.startsWith("image/")) {
          nextComposerIssue = `${file.name} is not a supported image.`
          continue
        }
        if (file.size > MAX_IMAGE_ATTACHMENT_BYTES) {
          nextComposerIssue = `${file.name} is too large. Images must be under 4 MB.`
          continue
        }

        nextAttachments.push({
          id: attachmentId,
          kind,
          name: file.name,
          mimeType: file.type || "image/png",
          size: file.size,
          file,
          previewUrl: URL.createObjectURL(file),
        })
        existingIds.add(attachmentId)
        continue
      }

      if (!isSupportedTextAttachment(file)) {
        nextComposerIssue = `${file.name} is not supported yet. Use text, code, JSON, Markdown, CSV, XML, or YAML files.`
        continue
      }

      if (file.size > MAX_TEXT_ATTACHMENT_BYTES) {
        nextComposerIssue = `${file.name} is too large. Files must be under 200 KB.`
        continue
      }

      nextAttachments.push({
        id: attachmentId,
        kind,
        name: file.name,
        mimeType: file.type || "text/plain",
        size: file.size,
        file,
      })
      existingIds.add(attachmentId)
    }

    setAttachments(nextAttachments)
    setComposerNotice(null)
    if (
      !nextComposerIssue &&
      nextAttachments.some((attachment) => attachment.kind === "image") &&
      !canAttachImages
    ) {
      setComposerIssue(
        "Images are attached. Switch to GPT-4o or Gemini before sending them."
      )
      return
    }

    setComposerIssue(nextComposerIssue)
  }

  async function buildChatRequestAttachments(
    items: Array<ComposerAttachment>
  ): Promise<Array<ApiAttachmentInput>> {
    return Promise.all(
      items.map(async (attachment) => {
        if (attachment.kind === "image") {
          return {
            kind: "image",
            name: attachment.name,
            mime_type: attachment.mimeType,
            data_url: await readFileAsDataUrl(attachment.file),
          }
        }

        const textContent = await attachment.file.text()
        return {
          kind: "file",
          name: attachment.name,
          mime_type: attachment.mimeType,
          text_content: textContent || "[Empty file]",
        }
      })
    )
  }

  async function buildAssetUploadAttachments(
    files: Array<File>
  ): Promise<Array<ApiAttachmentInput>> {
    return Promise.all(
      files.map(async (file) => {
        const kind: ApiAttachmentInput["kind"] = file.type.startsWith("image/")
          ? "image"
          : "file"
        return {
          kind,
          name: file.name,
          mime_type: file.type || "application/octet-stream",
          data_url: await readFileAsDataUrl(file),
        }
      })
    )
  }

  function toMessageAttachments(items: Array<ComposerAttachment>) {
    return items.map((attachment) => ({
      kind: attachment.kind,
      name: attachment.name,
      mime_type: attachment.mimeType,
    }))
  }

  async function loadConversation(
    conversationId: string,
    availableModels = modelOptions
  ) {
    loadConversationAbortRef.current?.abort()
    const controller = new AbortController()
    loadConversationAbortRef.current = controller
    setIsConversationLoading(true)
    setError(null)

    try {
      const detail = await fetchConversationDetail(
        conversationId,
        controller.signal
      )
      setCurrentConversationId(detail.conversation.id)
      setMessages(detail.messages)
      setComposerNotice(null)

      const conversationModelKey = createModelKey(
        detail.conversation.provider,
        detail.conversation.model_name
      )
      const matchingModel = availableModels.find(
        (option) => option.key === conversationModelKey
      )
      if (matchingModel) {
        setSelectedModelKey(matchingModel.key)
      }
    } catch (caughtError) {
      if (isAbortError(caughtError)) {
        return
      }

      const apiError = toApiError(caughtError)
      if (apiError.kind === "not_found") {
        await handleUnavailableConversation(conversationId, apiError)
        return
      }

      setError(apiError)
    } finally {
      if (loadConversationAbortRef.current === controller) {
        loadConversationAbortRef.current = null
      }
      if (!controller.signal.aborted) {
        setIsConversationLoading(false)
      }
    }
  }

  async function loadAssets() {
    setIsAssetsLoading(true)
    setError(null)

    try {
      const response = await listAssets()
      setAssets(response.items)
    } catch (caughtError) {
      if (isAbortError(caughtError)) {
        return
      }
      setError(toApiError(caughtError))
    } finally {
      setIsAssetsLoading(false)
    }
  }

  async function handleAssetsDialogChange(open: boolean) {
    setIsAssetsDialogOpen(open)
    if (!open) {
      return
    }
    await loadAssets()
  }

  async function handleAssetLibraryUpload(fileList: FileList | null) {
    if (!fileList || isUploadingAssets) {
      return
    }

    const files = Array.from(fileList)
    if (files.length > MAX_ASSET_UPLOAD_COUNT) {
      setComposerIssue(
        `You can store up to ${MAX_ASSET_UPLOAD_COUNT} sources at a time.`
      )
      return
    }

    for (const file of files) {
      if (file.size > MAX_ASSET_UPLOAD_BYTES) {
        setComposerIssue(
          `${file.name} is too large. Sources must be under 8 MB.`
        )
        return
      }
    }

    setIsUploadingAssets(true)
    setComposerIssue(null)
    setComposerNotice(null)
    setError(null)

    try {
      const payload = await buildAssetUploadAttachments(files)
      const response = await uploadAssets({ attachments: payload })
      await loadAssets()
      setComposerNotice(
        `Stored ${response.items.length} asset${
          response.items.length === 1 ? "" : "s"
        } in Sources.`
      )
    } catch (caughtError) {
      if (isAbortError(caughtError)) {
        return
      }
      setError(toApiError(caughtError))
    } finally {
      setIsUploadingAssets(false)
    }
  }

  async function handleDeleteAsset(assetId: string) {
    if (deletingAssetId) {
      return
    }

    setDeletingAssetId(assetId)
    setError(null)

    try {
      await deleteAsset(assetId)
      setAssets((currentAssets) =>
        currentAssets.filter((asset) => asset.id !== assetId)
      )
    } catch (caughtError) {
      if (isAbortError(caughtError)) {
        return
      }
      setError(toApiError(caughtError))
    } finally {
      setDeletingAssetId(null)
    }
  }

  async function handleSendMessage() {
    const content = draft.trim()
    const pendingAttachments = attachments
    if ((!content && pendingAttachments.length === 0) || sendLockRef.current) {
      return
    }

    sendLockRef.current = true
    let conversationId = currentConversationId
    const fallbackModel = modelOptions.at(0) ?? null
    const modelToUse = selectedModel ?? fallbackModel
    const optimisticAttachments = toMessageAttachments(pendingAttachments)
    let updatedAt = new Date().toISOString()

    if (modelToUse === null) {
      setComposerIssue(
        "No model is available yet. Wait for the catalog to load."
      )
      sendLockRef.current = false
      return
    }

    if (
      optimisticAttachments.some((attachment) => attachment.kind === "image") &&
      !canAttachImages
    ) {
      setComposerIssue(
        "The selected model does not support image attachments. Choose GPT-4o or Gemini to send images."
      )
      sendLockRef.current = false
      return
    }

    if (isListening) {
      stopVoiceInput()
    }

    const optimisticUserMessage: LocalMessage = {
      id: `pending-${Date.now()}`,
      role: "user",
      content,
      attachments: optimisticAttachments,
      token_count: null,
      created_at: new Date().toISOString(),
      isPending: true,
    }
    const optimisticAssistantMessage: LocalMessage = {
      id: `pending-assistant-${Date.now()}`,
      role: "assistant",
      content: "",
      attachments: [],
      token_count: null,
      created_at: new Date().toISOString(),
      metadata: null,
      isPending: true,
    }

    setDraft("")
    setAttachments([])
    setComposerIssue(null)
    setComposerNotice(null)
    setError(null)
    setIsSending(true)
    setMessages((currentMessages) => [
      ...currentMessages,
      optimisticUserMessage,
      optimisticAssistantMessage,
    ])

    try {
      if (!conversationId) {
        const createdConversation = await createConversation({
          provider: modelToUse.provider,
          model_name: modelToUse.id,
          title: buildConversationTitle(content, pendingAttachments),
        })
        conversationId = createdConversation.id
        setCurrentConversationId(createdConversation.id)
        React.startTransition(() => {
          setConversations((currentConversations) => [
            createdConversation,
            ...currentConversations.filter(
              (conversation) => conversation.id !== createdConversation.id
            ),
          ])
        })
      }
      const requestAttachments =
        await buildChatRequestAttachments(pendingAttachments)
      const streamState = {
        receivedChunk: false,
        completed: false,
      }

      try {
        await sendStreamingMessage({
          conversation_id: conversationId,
          content,
          attachments: requestAttachments,
          provider: modelToUse.provider,
          model_name: modelToUse.id,
          onChunk: (chunk) => {
            streamState.receivedChunk = true
            setMessages((currentMessages) =>
              currentMessages.map((message) =>
                message.id === optimisticAssistantMessage.id
                  ? {
                      ...message,
                      content: `${message.content}${chunk}`,
                    }
                  : message.id === optimisticUserMessage.id
                    ? { ...message, isPending: false }
                    : message
              )
            )
          },
        })
        streamState.completed = true
      } catch (caughtError) {
        if (isAbortError(caughtError)) {
          throw caughtError
        }

        if (streamState.receivedChunk) {
          throw caughtError
        }

        const assistantMessage = await sendMessage({
          conversation_id: conversationId,
          content,
          attachments: requestAttachments,
          provider: modelToUse.provider,
          model_name: modelToUse.id,
        })
        updatedAt = assistantMessage.created_at

        setMessages((currentMessages) =>
          currentMessages.map((message) => {
            if (message.id === optimisticUserMessage.id) {
              return { ...optimisticUserMessage, isPending: false }
            }
            if (message.id === optimisticAssistantMessage.id) {
              return {
                ...normalizeAssistantMessage(assistantMessage),
                isPending: false,
              }
            }
            return message
          })
        )
      }

      if (streamState.completed) {
        const detail = await fetchConversationDetail(conversationId)
        updatedAt = detail.conversation.updated_at
        setMessages(detail.messages)
      }

      revokeAttachmentPreviews(pendingAttachments)
      React.startTransition(() => {
        setConversations((currentConversations) => {
          const existingConversation = currentConversations.find(
            (conversation) => conversation.id === conversationId
          )
          if (!existingConversation) {
            return currentConversations
          }

          const updatedConversation = {
            ...existingConversation,
            provider: modelToUse.provider,
            model_name: modelToUse.id,
            updated_at: updatedAt,
          }
          return [
            updatedConversation,
            ...currentConversations.filter(
              (conversation) => conversation.id !== updatedConversation.id
            ),
          ]
        })
      })
    } catch (caughtError) {
      setDraft(content)
      setAttachments(pendingAttachments)
      setMessages((currentMessages) =>
        currentMessages.filter(
          (message) =>
            message.id !== optimisticUserMessage.id &&
            message.id !== optimisticAssistantMessage.id
        )
      )
      const apiError = toApiError(caughtError)
      if (apiError.kind === "not_found" && conversationId) {
        await handleUnavailableConversation(conversationId, apiError)
      } else {
        setError(apiError)
      }
    } finally {
      sendLockRef.current = false
      setIsSending(false)
    }
  }

  function handleNewChat() {
    loadConversationAbortRef.current?.abort()
    stopVoiceInput()
    revokeAttachmentPreviews(attachments)
    setCurrentConversationId(null)
    setMessages([])
    setDraft("")
    setAttachments([])
    setComposerIssue(null)
    setComposerNotice(null)
    setError(null)
    setSelectedModelKey(getPreferredModel(modelOptions)?.key ?? "")
  }

  async function handleClearAllConversations() {
    if (conversations.length === 0 || isClearingAllConversations) {
      return
    }

    setIsClearingAllConversations(true)
    setError(null)

    try {
      const conversationSnapshot = [...conversations]
      await Promise.all(
        conversationSnapshot.map((conversation) =>
          deleteConversation(conversation.id)
        )
      )

      loadConversationAbortRef.current?.abort()
      revokeAttachmentPreviews(attachments)
      setConversations([])
      setCurrentConversationId(null)
      setMessages([])
      setDraft("")
      setAttachments([])
      setComposerIssue(null)
      setComposerNotice(null)
      setSelectedModelKey(getPreferredModel(modelOptions)?.key ?? "")
      setIsMoreDialogOpen(false)
    } catch (caughtError) {
      if (isAbortError(caughtError)) {
        return
      }

      setError(toApiError(caughtError))
    } finally {
      setIsClearingAllConversations(false)
    }
  }

  function handleEditUserMessage(message: LocalMessage) {
    loadConversationAbortRef.current?.abort()
    stopVoiceInput()
    revokeAttachmentPreviews(attachments)
    setCurrentConversationId(null)
    setMessages([])
    setDraft(message.content)
    setAttachments([])
    setError(null)
    setComposerNotice(null)
    setComposerIssue(
      message.attachments.length > 0
        ? "This prompt included attachments. Add them again before sending."
        : null
    )

    requestAnimationFrame(() => {
      draftTextareaRef.current?.focus()
      const textLength = draftTextareaRef.current?.value.length ?? 0
      draftTextareaRef.current?.setSelectionRange(textLength, textLength)
    })
  }

  async function handleDeleteConversation(conversationId: string) {
    try {
      await deleteConversation(conversationId)
      await handleUnavailableConversation(conversationId, null)
    } catch (caughtError) {
      if (isAbortError(caughtError)) {
        return
      }

      const apiError = toApiError(caughtError)
      if (apiError.kind === "not_found") {
        await handleUnavailableConversation(conversationId, apiError)
        return
      }

      setError(apiError)
    }
  }

  async function handleShareConversation(
    conversationId = currentConversationId
  ) {
    if (!conversationId || typeof window === "undefined") {
      return
    }

    const conversationToShare =
      conversations.find(
        (conversation) => conversation.id === conversationId
      ) || currentConversation
    const shareUrl = `${window.location.origin}/?conversation=${conversationId}`

    if (typeof navigator.share === "function") {
      await navigator.share({
        title: conversationToShare ? conversationToShare.title : "Conversation",
        url: shareUrl,
      })
      return
    }

    await navigator.clipboard.writeText(shareUrl)
  }

  async function handleCopyMessage(messageId: string, content: string) {
    await navigator.clipboard.writeText(content)
    setCopiedMessageId(messageId)
    window.setTimeout(() => {
      setCopiedMessageId((currentMessageId) =>
        currentMessageId === messageId ? null : currentMessageId
      )
    }, 1500)
  }

  async function handleUnavailableConversation(
    conversationId: string,
    nextError: ApiError | null
  ) {
    loadConversationAbortRef.current?.abort()
    const remainingConversations = conversations.filter(
      (conversation) => conversation.id !== conversationId
    )
    const nextConversationId = remainingConversations.at(0)?.id ?? null
    setConversations(remainingConversations)

    if (conversationId === currentConversationId) {
      setCurrentConversationId(null)
      setMessages([])
      setSelectedModelKey(getPreferredModel(modelOptions)?.key ?? "")

      if (nextConversationId) {
        await loadConversation(nextConversationId)
      }
    }

    setError(nextError)
  }

  return (
    <SidebarProvider defaultOpen>
      <Sidebar>
        <SidebarHeader className="gap-3 p-3 pt-4">
          <div className="px-3 py-2">
            <div className="truncate text-sm font-medium text-foreground">
              Quama
            </div>
          </div>
          <SidebarMenu className="gap-1.5">
            {primaryActions.map((action) => (
              <SidebarMenuItem key={action.label}>
                {action.action === "market" ? (
                  <SidebarMenuButton
                    isActive={activeView === "market"}
                    tooltip={action.label}
                    className="h-10 rounded-lg px-3"
                    onClick={() => {
                      setActiveView("market")
                    }}
                  >
                    <action.icon />
                    <span>{action.label}</span>
                  </SidebarMenuButton>
                ) : action.action === "assets" ? (
                  <Dialog
                    open={isAssetsDialogOpen}
                    onOpenChange={(open: boolean) => {
                      void handleAssetsDialogChange(open)
                    }}
                  >
                    <DialogTrigger asChild>
                      <SidebarMenuButton
                        tooltip={action.label}
                        className="h-10 rounded-lg px-3"
                      >
                        <action.icon />
                        <span>{action.label}</span>
                      </SidebarMenuButton>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Sources</DialogTitle>
                        <DialogDescription>
                          Files in Sources are indexed for Pinecone-backed
                          retrieval and stay in your library until removed.
                        </DialogDescription>
                      </DialogHeader>
                      <div className="flex flex-col gap-4 px-4 pb-2">
                        <input
                          ref={assetInputRef}
                          type="file"
                          multiple
                          className="hidden"
                          onChange={(event) => {
                            void handleAssetLibraryUpload(event.target.files)
                            event.target.value = ""
                          }}
                        />
                        <div className="space-y-3">
                          <div className="flex items-center justify-between gap-3 rounded-2xl border border-border/70 bg-gradient-to-br from-primary/10 to-primary/5 px-4 py-3">
                            <div className="flex min-w-0 flex-col gap-0.5">
                              <div className="text-sm font-semibold text-foreground">
                                Stored Sources
                              </div>
                              <div className="text-xs text-muted-foreground">
                                Indexed for AI retrieval
                              </div>
                            </div>
                            <div className="flex items-center justify-center rounded-lg bg-primary/20 px-3 py-1.5">
                              <div className="text-sm font-bold text-primary">
                                {assets.length}
                              </div>
                            </div>
                          </div>
                          <Button
                            onClick={() => {
                              assetInputRef.current?.click()
                            }}
                            disabled={isUploadingAssets}
                            size="sm"
                            className="w-full"
                          >
                            {isUploadingAssets ? (
                              <LoaderCircle
                                data-icon="inline-start"
                                className="animate-spin"
                              />
                            ) : (
                              <FileUp data-icon="inline-start" />
                            )}
                            Add file to Sources
                          </Button>
                        </div>
                        <Separator className="my-2" />
                        <div className="space-y-2">
                          <div className="px-1 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                            Your Sources
                          </div>
                          <div className="max-h-80 space-y-2 overflow-y-auto">
                            {isAssetsLoading ? (
                              <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
                                <LoaderCircle className="size-4 animate-spin" />
                                Loading sources...
                              </div>
                            ) : assets.length === 0 ? (
                              <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 px-4 py-8 text-center">
                                <div className="mb-2 flex justify-center">
                                  <Folder className="size-8 text-muted-foreground/50" />
                                </div>
                                <div className="text-sm font-medium text-muted-foreground">
                                  No sources stored yet
                                </div>
                                <div className="mt-1 text-xs text-muted-foreground/70">
                                  Add files to get started
                                </div>
                              </div>
                            ) : (
                              <div className="flex flex-col gap-2">
                                {assets.map((asset) => {
                                  const Icon =
                                    asset.kind === "image" ? ImageUp : FileUp
                                  return (
                                    <div
                                      key={asset.id}
                                      className="flex items-center justify-between gap-3 rounded-2xl border border-border/70 bg-gradient-to-r from-muted/40 to-muted/10 px-3 py-2.5 transition-colors hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/20"
                                    >
                                      <div className="flex min-w-0 items-center gap-3">
                                        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border/50 bg-background text-foreground shadow-xs">
                                          <Icon className="size-4" />
                                        </div>
                                        <div className="min-w-0">
                                          <div className="truncate text-sm font-medium text-foreground">
                                            {asset.name}
                                          </div>
                                          <div className="text-xs text-muted-foreground">
                                            {formatFileSize(asset.size_bytes)} -{" "}
                                            {formatDateTime(asset.created_at)}
                                          </div>
                                        </div>
                                      </div>
                                      <div className="flex items-center gap-0.5">
                                        <Button
                                          variant="ghost"
                                          size="icon-xs"
                                          className="h-7 w-7 rounded-md text-muted-foreground hover:text-destructive"
                                          disabled={
                                            deletingAssetId === asset.id
                                          }
                                          onClick={() => {
                                            void handleDeleteAsset(asset.id)
                                          }}
                                        >
                                          {deletingAssetId === asset.id ? (
                                            <LoaderCircle className="animate-spin" />
                                          ) : (
                                            <Trash2 />
                                          )}
                                          <span className="sr-only">
                                            Delete {asset.name}
                                          </span>
                                        </Button>
                                      </div>
                                    </div>
                                  )
                                })}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                      <DialogFooter>
                        <DialogClose asChild>
                          <Button variant="outline">Close</Button>
                        </DialogClose>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                ) : action.action === "brokers" ? (
                  <>
                    <SidebarMenuButton
                      tooltip={action.label}
                      className="h-10 rounded-lg px-3"
                      isActive={activeView === "broker" || isBrokersDialogOpen}
                      onClick={() => {
                        if (!isAuthenticated) {
                          redirectToSignIn()
                          return
                        }
                        if (!isBrokerConnected) {
                          openAddBrokerDialog()
                          return
                        }
                        setActiveView("broker")
                      }}
                    >
                      <action.icon />
                      {isBrokerConnected ? (
                        <span className="flex items-center gap-1.5">
                          Broker
                          <span className="size-1.5 rounded-full bg-emerald-500" />
                        </span>
                      ) : (
                        <span>{action.label}</span>
                      )}
                    </SidebarMenuButton>
                    {null}
                    <Dialog
                      open={isBrokersDialogOpen}
                      onOpenChange={handleBrokerDialogOpenChange}
                    >
                      <DialogContent className="max-h-[calc(100svh-2rem)] overflow-hidden">
                        <DialogHeader>
                          <DialogTitle>
                            {brokerStep === 1
                              ? "Brokers"
                              : `Connect ${brokerCards.find((b) => b.id === selectedBroker)?.name}`}
                          </DialogTitle>
                          <DialogDescription>
                            {brokerStep === 1
                              ? "Choose a broker connection to authenticate."
                              : "Enter your credentials to securely connect your account."}
                          </DialogDescription>
                        </DialogHeader>
                        <ScrollArea className="min-h-0 flex-1">
                          <div className="flex flex-col gap-4 px-4 pb-2">
                            {brokerStatusError ? (
                              <div className="rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                                {brokerStatusError}
                              </div>
                            ) : null}
                            {brokerStep === 1 ? (
                              <div className="grid gap-3 sm:grid-cols-3">
                                {brokerCards.map((broker) => {
                                  const isSelected =
                                    selectedBroker === broker.id
                                  const fallback = getBrokerInitials(broker.id)
                                  return (
                                    <button
                                      key={broker.id}
                                      type="button"
                                      className={cn(
                                        "flex flex-col items-center gap-2 rounded-xl border px-3 py-3 transition-colors",
                                        "border-border/70 bg-muted/30",
                                        isSelected &&
                                          "border-foreground/30 bg-background shadow-xs ring-2 ring-foreground/5"
                                      )}
                                      onClick={() => {
                                        setSelectedBroker(broker.id)
                                        setBrokerFormError(null)
                                      }}
                                    >
                                      <Avatar size="lg">
                                        <AvatarFallback>
                                          {fallback}
                                        </AvatarFallback>
                                      </Avatar>
                                      <div className="truncate text-sm font-medium text-foreground">
                                        {broker.name}
                                      </div>
                                    </button>
                                  )
                                })}
                              </div>
                            ) : (
                              (() => {
                                const selectedBrokerCard =
                                  brokerCards.find(
                                    (b) => b.id === selectedBroker
                                  ) || brokerCards[0]
                                const fallback = getBrokerInitials(
                                  selectedBrokerCard.id
                                )
                                const isGrowwBroker =
                                  selectedBrokerCard.id === "groww"
                                return (
                                  <div className="mt-2 rounded-3xl border border-border/70 bg-muted/25 p-5 shadow-sm">
                                    <div className="mb-5 flex items-start gap-4">
                                      <Avatar
                                        size="lg"
                                        className="border border-border/50 shadow-sm"
                                      >
                                        <AvatarFallback className="bg-background font-semibold tracking-wider text-foreground">
                                          {fallback}
                                        </AvatarFallback>
                                      </Avatar>
                                      <div>
                                        <div className="text-base font-semibold text-foreground">
                                          {selectedBrokerCard.name} Login
                                        </div>
                                        <div className="mt-1 text-sm leading-relaxed text-muted-foreground">
                                          Enter your broker credentials to
                                          securely connect your account.
                                        </div>
                                      </div>
                                    </div>
                                    {brokerFormError ? (
                                      <div className="mb-5 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                                        {brokerFormError}
                                      </div>
                                    ) : null}

                                    <div className="rounded-2xl p-4">
                                      <div className="grid gap-4">
                                        <div className="grid gap-2">
                                          <label
                                            htmlFor="broker-client-id"
                                            className="text-xs font-medium tracking-widest text-muted-foreground uppercase"
                                          >
                                            {isGrowwBroker
                                              ? "User API Key"
                                              : "Client ID"}
                                          </label>
                                          <Input
                                            id="broker-client-id"
                                            type={
                                              isGrowwBroker
                                                ? "password"
                                                : "text"
                                            }
                                            value={brokerClientId}
                                            onChange={(event) => {
                                              setBrokerClientId(
                                                event.target.value
                                              )
                                            }}
                                            placeholder={
                                              isGrowwBroker
                                                ? "Enter your Groww API key"
                                                : "Enter your client ID"
                                            }
                                            className="border-border/50 bg-background"
                                          />
                                        </div>

                                        {isGrowwBroker ? null : (
                                          <div className="grid gap-2">
                                            <label
                                              htmlFor="broker-password"
                                              className="text-xs font-medium tracking-widest text-muted-foreground uppercase"
                                            >
                                              Password
                                            </label>
                                            <div className="relative">
                                              <Input
                                                id="broker-password"
                                                type={
                                                  showBrokerPassword
                                                    ? "text"
                                                    : "password"
                                                }
                                                value={brokerPassword}
                                                onChange={(event) => {
                                                  setBrokerPassword(
                                                    event.target.value
                                                  )
                                                }}
                                                placeholder="Enter your password"
                                                className="border-border/50 bg-background pr-10"
                                              />
                                              <button
                                                type="button"
                                                onClick={() =>
                                                  setShowBrokerPassword(
                                                    !showBrokerPassword
                                                  )
                                                }
                                                className="absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                              >
                                                {showBrokerPassword ? (
                                                  <EyeOff className="size-4" />
                                                ) : (
                                                  <Eye className="size-4" />
                                                )}
                                              </button>
                                            </div>
                                          </div>
                                        )}

                                        <div className="grid gap-2">
                                          <label
                                            htmlFor="broker-totp"
                                            className="text-xs font-medium tracking-widest text-muted-foreground uppercase"
                                          >
                                            {isGrowwBroker
                                              ? "TOTP Code"
                                              : "TOTP"}
                                          </label>
                                          <Input
                                            id="broker-totp"
                                            inputMode="numeric"
                                            maxLength={6}
                                            value={brokerTotp}
                                            className="border-border/50 bg-background font-mono tracking-[0.28em]"
                                            onChange={(event) => {
                                              setBrokerTotp(
                                                event.target.value
                                                  .replace(/\D/g, "")
                                                  .slice(0, 6)
                                              )
                                            }}
                                            placeholder="6-digit code"
                                          />
                                          <div className="text-xs text-muted-foreground">
                                            {isGrowwBroker
                                              ? "Enter the TOTP code for your Groww API key."
                                              : "Enter the 6-digit code from your authenticator app."}
                                          </div>
                                        </div>
                                      </div>
                                    </div>
                                  </div>
                                )
                              })()
                            )}
                          </div>
                        </ScrollArea>
                        <DialogFooter className="border-t border-border/70 pt-4">
                          {brokerStep === 1 ? (
                            <>
                              <DialogClose asChild>
                                <Button variant="outline">Close</Button>
                              </DialogClose>
                              {(() => {
                                const selectedBrokerCard =
                                  brokerCards.find(
                                    (b) => b.id === selectedBroker
                                  ) || brokerCards[0]
                                return (
                                  <Button
                                    onClick={() => setBrokerStep(2)}
                                    disabled={
                                      !selectedBrokerCard.isAvailable ||
                                      selectedBrokerStatus?.is_active ===
                                        true ||
                                      isBrokerStatusLoading
                                    }
                                  >
                                    {isBrokerStatusLoading ? (
                                      <LoaderCircle className="animate-spin" />
                                    ) : null}
                                    {selectedBrokerStatus?.is_active
                                      ? "Connected"
                                      : "Next"}
                                  </Button>
                                )
                              })()}
                            </>
                          ) : (
                            <>
                              <Button
                                variant="outline"
                                onClick={() => {
                                  setBrokerStep(1)
                                  setBrokerFormError(null)
                                }}
                              >
                                Back
                              </Button>
                              {(() => {
                                const selectedBrokerCard =
                                  brokerCards.find(
                                    (b) => b.id === selectedBroker
                                  ) || brokerCards[0]
                                const requiresPassword =
                                  selectedBrokerCard.id === "angel-one"
                                return (
                                  <Button
                                    onClick={() => {
                                      void handleBrokerConnect()
                                    }}
                                    disabled={
                                      isBrokerConnecting ||
                                      !selectedBrokerCard.isAvailable ||
                                      brokerClientId.trim().length === 0 ||
                                      (requiresPassword &&
                                        brokerPassword.trim().length === 0) ||
                                      brokerTotp.length !== 6
                                    }
                                  >
                                    {isBrokerConnecting ? (
                                      <LoaderCircle className="animate-spin" />
                                    ) : null}
                                    Continue with {selectedBrokerCard.name}
                                  </Button>
                                )
                              })()}
                            </>
                          )}
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </>
                ) : action.action === "more" ? (
                  <Dialog
                    open={isMoreDialogOpen}
                    onOpenChange={setIsMoreDialogOpen}
                  >
                    <DialogTrigger asChild>
                      <SidebarMenuButton
                        tooltip={action.label}
                        className="h-10 rounded-lg px-3"
                      >
                        <action.icon />
                        <span>{action.label}</span>
                      </SidebarMenuButton>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>More</DialogTitle>
                        <DialogDescription>
                          Additional workspace actions and shortcuts live here.
                        </DialogDescription>
                      </DialogHeader>
                      <div className="flex flex-col gap-3 px-4 pb-2">
                        <div className="flex items-center justify-between gap-3 rounded-2xl border border-border/70 bg-muted/30 px-4 py-3">
                          <div className="flex min-w-0 flex-col gap-0.5">
                            <div className="text-sm font-medium text-foreground">
                              Conversations
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {conversations.length} saved conversation
                              {conversations.length === 1 ? "" : "s"}
                            </div>
                          </div>
                          <div className="text-sm font-medium text-foreground">
                            {conversations.length}
                          </div>
                        </div>
                        <div className="flex items-center justify-between gap-3 rounded-2xl border border-border/70 bg-muted/30 px-4 py-3">
                          <div className="flex min-w-0 flex-col gap-0.5">
                            <div className="text-sm font-medium text-foreground">
                              Models
                            </div>
                            <div className="text-sm text-muted-foreground">
                              Available in this workspace
                            </div>
                          </div>
                          <div className="text-sm font-medium text-foreground">
                            {modelOptions.length}
                          </div>
                        </div>
                        <Separator />
                        <p className="text-sm leading-6 text-muted-foreground">
                          More actions can be added here without crowding the
                          sidebar.
                        </p>
                        <Button
                          variant="destructive"
                          disabled={
                            conversations.length === 0 ||
                            isClearingAllConversations
                          }
                          onClick={() => {
                            void handleClearAllConversations()
                          }}
                        >
                          {isClearingAllConversations ? (
                            <LoaderCircle
                              data-icon="inline-start"
                              className="animate-spin"
                            />
                          ) : (
                            <Trash2 data-icon="inline-start" />
                          )}
                          Clear all conversations
                        </Button>
                      </div>
                      <DialogFooter>
                        <DialogClose asChild>
                          <Button variant="outline">Close</Button>
                        </DialogClose>
                        <DialogClose asChild>
                          <Button
                            onClick={() => {
                              handleNewChat()
                            }}
                          >
                            <SquarePen data-icon="inline-start" />
                            New chat
                          </Button>
                        </DialogClose>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                ) : action.action === "tools" ? (
                  <Dialog
                    open={isToolsDialogOpen}
                    onOpenChange={handleToolsDialogOpenChange}
                  >
                    <DialogTrigger asChild>
                      <SidebarMenuButton
                        tooltip={action.label}
                        className="h-10 rounded-lg px-3"
                      >
                        <action.icon />
                        <span>{action.label}</span>
                      </SidebarMenuButton>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>MCP</DialogTitle>
                        <DialogDescription>
                          Connect external tools and expose their MCP tools to
                          the agent.
                        </DialogDescription>
                      </DialogHeader>
                      <div className="flex flex-col gap-3 px-4 pb-2">
                        {mcpError ? (
                          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                            {mcpError}
                          </div>
                        ) : null}

                        {isMcpLoading ? (
                          <div className="flex flex-col gap-3">
                            <Skeleton className="h-20 w-full" />
                            <Skeleton className="h-20 w-full" />
                          </div>
                        ) : (
                          mcpProviders.map((provider) => {
                            const connection = mcpConnectionByProvider.get(
                              provider.provider
                            )
                            const isConnected = Boolean(connection)
                            const isBusy = mcpBusyProvider === provider.provider
                            const switchId = `mcp-${provider.provider}`

                            return (
                              <div
                                key={provider.provider}
                                className="flex flex-col gap-3 rounded-2xl border border-border/70 bg-gradient-to-br from-muted/50 to-muted/20 px-4 py-4 transition-all hover:border-border/100"
                              >
                                <div className="flex items-center justify-between gap-3">
                                  <div className="flex min-w-0 items-center gap-3">
                                    <div className="flex size-12 shrink-0 items-center justify-center rounded-2xl border border-border/70 bg-background text-foreground shadow-sm">
                                      {provider.provider === "github" ? (
                                        <GitHubMark className="size-6" />
                                      ) : provider.provider === "zerodha" ? (
                                        <ZerodhaIcon className="size-6" />
                                      ) : provider.provider === "newsapi" ? (
                                        <Newspaper className="size-6" />
                                      ) : (
                                        <Handshake className="size-6" />
                                      )}
                                    </div>
                                    <div className="flex min-w-0 flex-col gap-0.5">
                                      <label
                                        htmlFor={switchId}
                                        className="text-sm font-semibold text-foreground"
                                      >
                                        {provider.label}
                                      </label>
                                      <div className="line-clamp-1 text-sm text-muted-foreground">
                                        {provider.description}
                                      </div>
                                    </div>
                                  </div>
                                  <Switch
                                    id={switchId}
                                    checked={isConnected}
                                    disabled={isBusy}
                                    onCheckedChange={(checked) => {
                                      void handleMcpProviderToggle(
                                        provider,
                                        checked
                                      )
                                    }}
                                    aria-label={`Toggle ${provider.label} MCP`}
                                  />
                                </div>
                                {connection ? (
                                  <div className="flex flex-col gap-2">
                                    <div className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
                                      Available Tools ({connection.tools.length}
                                      )
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                      {connection.tools.map((tool) => (
                                        <Badge
                                          key={tool.name}
                                          variant="secondary"
                                          className="font-medium"
                                        >
                                          {tool.name}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                ) : null}
                              </div>
                            )
                          })
                        )}
                      </div>
                      <DialogFooter>
                        <DialogClose asChild>
                          <Button variant="outline">Close</Button>
                        </DialogClose>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                ) : (
                  <SidebarMenuButton
                    isActive={
                      activeView === "chat" && currentConversationId === null
                    }
                    tooltip={action.label}
                    className="h-10 rounded-lg px-3"
                    onClick={() => {
                      setActiveView("chat")
                      handleNewChat()
                    }}
                  >
                    <action.icon />
                    <span>{action.label}</span>
                  </SidebarMenuButton>
                )}
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarHeader>

        <SidebarContent className="min-h-0 overflow-hidden">
          <ScrollArea className="h-full px-2 pb-2">
            <SidebarGroup className="gap-2 px-2 py-3">
              <SidebarGroupLabel className="px-2 text-[0.65rem] tracking-[0.28em] uppercase">
                Recents
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu className="gap-1">
                  {conversations.length === 0 ? (
                    <SidebarMenuItem>
                      <div className="px-2.5 py-2 text-sm text-muted-foreground">
                        {isBootstrapping
                          ? "Loading conversations..."
                          : "No conversations yet."}
                      </div>
                    </SidebarMenuItem>
                  ) : (
                    conversations.map((conversation) => (
                      <SidebarMenuItem key={conversation.id}>
                        <SidebarMenuButton
                          isActive={
                            activeView === "chat" &&
                            currentConversationId === conversation.id
                          }
                          className="h-auto rounded-lg px-2.5 py-2 pe-12 text-sm leading-5 text-sidebar-foreground/90"
                          onClick={() => {
                            setActiveView("chat")
                            void loadConversation(conversation.id)
                          }}
                        >
                          <span className="flex min-w-0 items-center gap-2">
                            <span
                              className="block truncate"
                              title={conversation.title}
                            >
                              {truncateLabel(conversation.title, 19)}
                            </span>
                          </span>
                        </SidebarMenuButton>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <SidebarMenuAction
                              showOnHover
                              className="inset-y-0 right-1.5 my-auto size-7 rounded-md bg-transparent text-sidebar-foreground/90 hover:bg-transparent hover:text-sidebar-accent-foreground data-[state=open]:bg-transparent data-[state=open]:text-sidebar-accent-foreground"
                            >
                              <MoreHorizontal strokeWidth={2.25} />
                              <span className="sr-only">
                                Actions for{" "}
                                {truncateLabel(conversation.title, 13)}
                              </span>
                            </SidebarMenuAction>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent
                            align="end"
                            className="w-36 rounded-lg"
                          >
                            <DropdownMenuItem>
                              <SquarePen />
                              Rename
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onSelect={() => {
                                void handleShareConversation(conversation.id)
                              }}
                            >
                              <Share2 />
                              Share
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              variant="destructive"
                              onSelect={() => {
                                void handleDeleteConversation(conversation.id)
                              }}
                            >
                              <Trash2 />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </SidebarMenuItem>
                    ))
                  )}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </ScrollArea>
        </SidebarContent>

        <SidebarFooter className="p-3 pt-2">
          <SidebarMenu>
            <SidebarMenuItem>
              {isAuthenticated ? (
                <div className="flex items-center gap-3 rounded-lg px-2.5 py-2.5">
                  <UserButton
                    appearance={{
                      elements: {
                        avatarBox: "size-10",
                      },
                    }}
                  />
                  <span className="min-w-0 truncate text-sm font-medium">
                    {profileDisplayName}
                  </span>
                </div>
              ) : (
                <div className="grid gap-2 rounded-lg px-2.5 py-2.5">
                  <Button asChild size="sm" className="w-full rounded-full">
                    <a href="/sign-in">Sign in</a>
                  </Button>
                  <Button
                    asChild
                    variant="outline"
                    size="sm"
                    className="w-full rounded-full"
                  >
                    <a href="/sign-up">Sign up</a>
                  </Button>
                </div>
              )}
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>

        <SidebarRail />
      </Sidebar>

      <SidebarInset className="relative flex h-svh min-h-0 flex-col overflow-hidden bg-background">
        <header className="relative z-10 flex h-14 items-center px-4 md:px-6">
          <div className="flex min-w-0 flex-1 items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <SidebarTrigger className="rounded-lg" />
            </div>
            {activeView === "market" ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="rounded-full"
                onClick={() => {
                  setActiveView("chat")
                }}
              >
                <ArrowLeft data-icon="inline-start" />
                Back to chat
              </Button>
            ) : null}
            {activeView === "broker" && activeConnectedBroker ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="rounded-full">
                    {activeConnectedBroker.name}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuLabel>Connected brokers</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuRadioGroup
                    value={selectedConnectedBrokerId ?? ""}
                    onValueChange={(value) => {
                      const nextBroker = value as BrokerOption
                      if (!connectedBrokerIds.includes(nextBroker)) {
                        return
                      }

                      setSelectedConnectedBroker(nextBroker)
                      setBrokerPortfolioSummary(null)
                      setBrokerPortfolioHoldings([])
                      setBrokerPortfolioError(null)
                    }}
                  >
                    {connectedBrokerOptions.map((broker) => {
                      const status = brokerStatus[broker.id]
                      return (
                        <DropdownMenuRadioItem
                          key={broker.id}
                          value={broker.id}
                        >
                          <span>{broker.name}</span>
                          {status?.client_code ? (
                            <span className="ms-auto max-w-24 truncate text-xs text-muted-foreground">
                              {status.client_code}
                            </span>
                          ) : null}
                        </DropdownMenuRadioItem>
                      )
                    })}
                  </DropdownMenuRadioGroup>
                  <DropdownMenuSeparator />
                  <DropdownMenuGroup>
                    <DropdownMenuItem
                      disabled={!canAddBroker}
                      onSelect={openAddBrokerDialog}
                    >
                      <Plus data-icon="inline-start" />
                      Add Broker
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      variant="destructive"
                      disabled={isBrokerDisconnecting}
                      onClick={() => setIsDisconnectConfirmOpen(true)}
                    >
                      {isBrokerDisconnecting ? (
                        <LoaderCircle
                          data-icon="inline-start"
                          className="animate-spin"
                        />
                      ) : null}
                      Disconnect
                    </DropdownMenuItem>
                  </DropdownMenuGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : null}
          </div>
        </header>

        <AlertDialog
          open={isDisconnectConfirmOpen}
          onOpenChange={setIsDisconnectConfirmOpen}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Disconnect broker?</AlertDialogTitle>
              <AlertDialogDescription>
                This will clear the live portfolio view and require a fresh
                login before the broker dashboard can load again.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                disabled={isBrokerDisconnecting}
                onClick={() => {
                  void handleBrokerDisconnect()
                }}
              >
                {isBrokerDisconnecting ? (
                  <span className="inline-flex items-center gap-2">
                    <LoaderCircle className="size-4 animate-spin" />
                    Disconnecting
                  </span>
                ) : (
                  "Disconnect"
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {activeView === "market" ? (
          <MarketCanvas />
        ) : activeView === "broker" ? (
          <BrokerCanvas
            summary={brokerPortfolioSummary}
            holdings={brokerPortfolioHoldings}
            isPortfolioLoading={isBrokerPortfolioLoading}
            portfolioError={brokerPortfolioError}
            onRetry={() => setBrokerRetryTrigger((n) => n + 1)}
            brokerName={selectedConnectedBroker ?? "groww"}
          />
        ) : (
          <>
            <main className="relative z-10 flex min-h-0 flex-1 flex-col">
              <div className="relative mx-auto flex min-h-0 w-full max-w-6xl flex-1 flex-col px-4 md:px-8">
                <ScrollArea className="min-h-0 flex-1">
                  {messages.length === 0 ? (
                    <div className="mx-auto flex min-h-[58vh] w-full max-w-2xl flex-col items-center justify-center gap-4 text-center">
                      <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
                        {isBootstrapping
                          ? "Connecting to the backend..."
                          : "Where should we begin?"}
                      </h1>
                      {errorPresentation ? (
                        <div className="flex w-full max-w-2xl items-start justify-between gap-3 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-start text-sm text-destructive">
                          <div>
                            <span className="font-medium">
                              {errorPresentation.title}:
                            </span>{" "}
                            {errorPresentation.message}
                          </div>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            className="shrink-0 rounded-full text-destructive hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => {
                              setError(null)
                            }}
                          >
                            <X />
                            <span className="sr-only">Dismiss error</span>
                          </Button>
                        </div>
                      ) : (
                        <p className="max-w-2xl text-sm leading-7 text-muted-foreground">
                          {modelOptions.length > 0
                            ? "Ask for code, product thinking, or implementation detail."
                            : "Load the backend model catalog to start chatting."}
                        </p>
                      )}
                    </div>
                  ) : (
                    <div className="mx-auto flex w-full max-w-2xl flex-col gap-8 pt-2 pb-8">
                      {messages.map((message, index) =>
                        message.role === "user" ? (
                          <section
                            key={message.id}
                            className="flex justify-end"
                          >
                            <div className="w-full max-w-[85%] rounded-[1.75rem] border border-border/70 bg-muted/35 px-5 py-4 md:max-w-[50%] md:px-6">
                              {message.attachments.length > 0 ? (
                                <div className="mb-3">
                                  <MessageAttachmentChips
                                    attachments={message.attachments}
                                  />
                                </div>
                              ) : null}
                              {message.content ? (
                                <p className="text-[0.98rem] leading-7 whitespace-pre-wrap text-foreground">
                                  {message.content}
                                </p>
                              ) : null}
                              <div className="mt-3 flex items-center justify-end gap-3 text-xs text-muted-foreground">
                                <div className="flex items-center gap-1">
                                  <Button
                                    variant="ghost"
                                    size="icon-sm"
                                    className="rounded-full text-muted-foreground"
                                    disabled={message.isPending || isSending}
                                    onClick={() => {
                                      handleEditUserMessage(message)
                                    }}
                                  >
                                    <SquarePen />
                                    <span className="sr-only">
                                      Edit message
                                    </span>
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon-sm"
                                    className="rounded-full text-muted-foreground"
                                    onClick={() => {
                                      void handleCopyMessage(
                                        message.id,
                                        message.content
                                      )
                                    }}
                                  >
                                    {copiedMessageId === message.id ? (
                                      <Check />
                                    ) : (
                                      <Copy />
                                    )}
                                    <span className="sr-only">
                                      {copiedMessageId === message.id
                                        ? "Copied"
                                        : "Copy message"}
                                    </span>
                                  </Button>
                                </div>
                              </div>
                            </div>
                          </section>
                        ) : (
                          <section
                            key={message.id}
                            className={cn(index !== 0 && "pt-8")}
                          >
                            <ThinkingSteps metadata={message.metadata} />
                            <div className="text-[1.02rem] text-pretty text-foreground md:text-[1.08rem]">
                              <MessageMarkdown content={message.content} />
                              {message.isPending ? (
                                <span className="ms-2 inline-block h-5 w-2 animate-pulse rounded-full bg-foreground/70 align-middle" />
                              ) : null}
                            </div>
                            <div className="mt-4 flex items-center justify-end gap-3 text-xs text-muted-foreground">
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                className="rounded-full text-muted-foreground"
                                disabled={message.isPending || !message.content}
                                onClick={() => {
                                  void handleCopyMessage(
                                    message.id,
                                    message.content
                                  )
                                }}
                              >
                                {copiedMessageId === message.id ? (
                                  <Check />
                                ) : (
                                  <Copy />
                                )}
                                <span className="sr-only">
                                  {copiedMessageId === message.id
                                    ? "Copied"
                                    : "Copy message"}
                                </span>
                              </Button>
                            </div>
                          </section>
                        )
                      )}

                      {isConversationLoading ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <LoaderCircle className="size-4 animate-spin" />
                          Loading conversation...
                        </div>
                      ) : null}
                      <div ref={messageEndRef} />
                    </div>
                  )}
                </ScrollArea>
              </div>
            </main>

            <div className="flex shrink-0 justify-center px-4 pt-3 pb-4 md:px-8">
              <div className="flex w-full max-w-2xl flex-col items-center gap-3">
                <input
                  ref={attachmentInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(event) => {
                    addComposerAttachments(event.target.files)
                    event.target.value = ""
                  }}
                />

                {errorPresentation && messages.length > 0 ? (
                  <div className="flex w-full items-start justify-between gap-3 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                    <div>
                      <span className="font-medium">
                        {errorPresentation.title}:
                      </span>{" "}
                      {errorPresentation.message}
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-xs"
                      className="shrink-0 rounded-full text-destructive hover:bg-destructive/10 hover:text-destructive"
                      onClick={() => {
                        setError(null)
                      }}
                    >
                      <X />
                      <span className="sr-only">Dismiss error</span>
                    </Button>
                  </div>
                ) : null}

                {composerIssue ? (
                  <div className="flex w-full items-start justify-between gap-3 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                    <div>{composerIssue}</div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-xs"
                      className="shrink-0 rounded-full text-destructive hover:bg-destructive/10 hover:text-destructive"
                      onClick={() => {
                        setComposerIssue(null)
                      }}
                    >
                      <X />
                      <span className="sr-only">Dismiss notification</span>
                    </Button>
                  </div>
                ) : null}

                {composerNotice ? (
                  <div className="flex w-full items-start justify-between gap-3 rounded-2xl border border-border/70 bg-muted/35 px-4 py-3 text-sm text-foreground">
                    <div>{composerNotice}</div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-xs"
                      className="shrink-0 rounded-full text-muted-foreground"
                      onClick={() => {
                        setComposerNotice(null)
                      }}
                    >
                      <X />
                      <span className="sr-only">Dismiss notice</span>
                    </Button>
                  </div>
                ) : null}

                <div className="flex w-full flex-col gap-2 rounded-[1.5rem] border border-border/70 bg-muted/35 px-2.5 py-2 shadow-none">
                  {attachments.length > 0 ? (
                    <div className="flex flex-wrap gap-2 px-1">
                      {attachments.map((attachment) => (
                        <div
                          key={attachment.id}
                          className="inline-flex items-center gap-2 rounded-2xl border border-border/70 bg-background/80 px-2 py-2 text-xs text-muted-foreground"
                        >
                          {attachment.previewUrl ? (
                            <img
                              src={attachment.previewUrl}
                              alt={attachment.name}
                              className="size-10 rounded-xl object-cover"
                            />
                          ) : (
                            <div className="flex size-10 items-center justify-center rounded-xl bg-muted">
                              <FileUp />
                            </div>
                          )}
                          <div className="flex min-w-0 flex-col gap-0.5">
                            <span className="max-w-44 truncate font-medium text-foreground">
                              {attachment.name}
                            </span>
                            <span>{formatFileSize(attachment.size)}</span>
                          </div>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            className="rounded-full text-muted-foreground"
                            onClick={() => {
                              handleRemoveAttachment(attachment.id)
                            }}
                          >
                            <X />
                            <span className="sr-only">
                              Remove {attachment.name}
                            </span>
                          </Button>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  <div className="flex min-h-11 items-center gap-1.5">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="shrink-0 rounded-full text-muted-foreground"
                      disabled={isSending}
                      onClick={() => {
                        attachmentInputRef.current?.click()
                      }}
                    >
                      <Plus />
                      <span className="sr-only">Add attachments</span>
                    </Button>

                    <Textarea
                      ref={draftTextareaRef}
                      placeholder="Ask anything"
                      rows={1}
                      value={draft}
                      onChange={(event) => setDraft(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" && !event.shiftKey) {
                          event.preventDefault()
                          void handleSendMessage()
                        }
                      }}
                      className="field-sizing-fixed max-h-36 min-h-10 flex-1 resize-none self-center overflow-y-hidden border-none bg-transparent px-0 py-2 text-base leading-6 shadow-none focus-visible:ring-0 md:text-[1.05rem] dark:bg-transparent"
                    />

                    <div className="flex shrink-0 items-center gap-1">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="rounded-full text-muted-foreground"
                            disabled={modelOptions.length === 0}
                          >
                            <Brain />
                            <span className="sr-only">Open model list</span>
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent
                          align="end"
                          className="w-72 rounded-2xl p-2"
                        >
                          <ScrollArea className="max-h-64">
                            <DropdownMenuRadioGroup
                              value={selectedModel ? selectedModel.key : ""}
                              onValueChange={(value: string) => {
                                setSelectedModelKey(value)
                              }}
                            >
                              {modelOptions.map((model) => (
                                <DropdownMenuRadioItem
                                  key={model.key}
                                  value={model.key}
                                  className="min-w-0 rounded-xl px-3 py-2.5 text-xs"
                                >
                                  {model.name}
                                </DropdownMenuRadioItem>
                              ))}
                            </DropdownMenuRadioGroup>
                          </ScrollArea>
                        </DropdownMenuContent>
                      </DropdownMenu>

                      <Button
                        variant="ghost"
                        size="icon"
                        className={cn(
                          "rounded-full text-muted-foreground",
                          isListening && "bg-background text-foreground"
                        )}
                        disabled={isSending}
                        onClick={handleVoiceInputToggle}
                      >
                        {isListening ? <AudioLines /> : <Mic />}
                        <span className="sr-only">
                          {isListening
                            ? "Stop voice input"
                            : "Start voice input"}
                        </span>
                      </Button>

                      <Button
                        size="icon"
                        className="rounded-full bg-foreground text-background shadow-sm hover:bg-foreground/90"
                        disabled={
                          isSending ||
                          modelOptions.length === 0 ||
                          !hasComposerContent
                        }
                        onClick={() => {
                          void handleSendMessage()
                        }}
                      >
                        {isSending ? (
                          <LoaderCircle className="animate-spin" />
                        ) : (
                          <ArrowUp />
                        )}
                        <span className="sr-only">Send prompt</span>
                      </Button>
                    </div>
                  </div>
                </div>

                <p className="text-center text-xs text-muted-foreground">
                  Chat can make mistakes. Check important info.
                </p>
              </div>
            </div>
          </>
        )}
      </SidebarInset>
    </SidebarProvider>
  )
}
