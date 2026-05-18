export type ApiMessage = {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  attachments: Array<ApiMessageAttachment>
  token_count: number | null
  metadata?: Record<string, unknown> | null
  created_at: string
}

export type ApiMessageAttachment = {
  kind: "file" | "image"
  name: string
  mime_type: string
}

export type ApiConversation = {
  id: string
  user_id: string
  title: string
  provider: string
  model_name: string
  created_at: string
  updated_at: string
}

export type ApiConversationList = {
  items: Array<ApiConversation>
  total: number
  skip: number
  limit: number
}

export type ApiConversationDetail = {
  conversation: ApiConversation
  messages: Array<ApiMessage>
}

export type ApiModelInfo = {
  id: string
  name: string
  description: string
}

export type ApiProviderInfo = {
  name: string
  models: Array<ApiModelInfo>
}

export type ApiModelsResponse = {
  providers: Array<ApiProviderInfo>
}

export type CreateConversationPayload = {
  provider?: string
  model_name?: string
  title?: string
}

export type SendMessagePayload = {
  conversation_id: string
  content: string
  provider?: string
  model_name?: string
  attachments?: Array<ApiAttachmentInput>
}

export type ApiAttachmentInput = {
  kind: "file" | "image"
  name: string
  mime_type: string
  text_content?: string
  data_url?: string
}

export type SendMessageResponse = {
  message_id: string
  role: "assistant"
  content: string
  created_at: string
  token_count: number | null
}

export type AssetUploadPayload = {
  attachments: Array<ApiAttachmentInput>
}

export type ApiStoredAsset = {
  id: string
  name: string
  kind: "file" | "image"
  mime_type: string
  size_bytes: number
  pinecone_indexed: boolean
  created_at: string
  updated_at: string
}

export type AssetListResponse = {
  items: Array<ApiStoredAsset>
}

export type AssetUploadResponse = {
  items: Array<ApiStoredAsset>
}

export type BrokerConnectPayload = {
  client_code: string
  password: string
  totp: string
}

export type GrowwConnectPayload = {
  api_key: string
  totp: string
}

export type ApiBrokerConnectResponse = {
  broker: string
  client_code: string
  connected: boolean
  connected_at: string
}

export type ApiBrokerDisconnectResponse = {
  disconnected: boolean
}

export type ApiBrokerStatusItem = {
  broker: string
  client_code: string
  connected_at: string
  is_active: boolean
}

export type ApiBrokerStatusResponse = {
  items: Array<ApiBrokerStatusItem>
}

export type ApiBrokerPortfolioSummary = {
  funds: number | null
  investment: number | null
  overall_gain: number | null
}

export type ApiBrokerPortfolioResponse = {
  holdings: Array<Record<string, unknown>>
  funds: Record<string, unknown>
  summary: ApiBrokerPortfolioSummary
  connected_broker: string
  performance_history: Array<Record<string, unknown>>
}

export type ApiMarketInstrument = {
  exchange_type: number
  instrument_token: string
}

export type MarketSubscriptionPayload = {
  mode?: number
  replace?: boolean
  instruments: Array<ApiMarketInstrument>
}

export type ApiMarketSubscriptionResponse = {
  user_id: string
  broker: string
  mode: number
  replace: boolean
  instruments: Array<ApiMarketInstrument>
  subscription_key: string
  command_channel: string
}

export type ApiMarketTick = {
  instrument_token: string
  exchange_type: number | null
  subscription_mode: number | null
  sequence_number: number | null
  price: number | null
  price_raw: number | null
  volume: number | null
  timestamp: string | null
  source: string
  published_at: string
}

export type ApiMarketStreamEvent = {
  channel: string
  tick: ApiMarketTick
  snapshot: boolean
}

export type ApiMcpTool = {
  name: string
  description: string
  input_schema: Record<string, unknown>
}

export type ApiMcpProvider = {
  provider: string
  label: string
  description: string
  transport: "mock" | "http_jsonrpc"
  server_url: string | null
}

export type ApiMcpConnection = {
  provider: string
  label: string
  transport: "mock" | "http_jsonrpc"
  server_url: string | null
  connected: boolean
  tools: Array<ApiMcpTool>
}

export type ApiMcpConnectionList = {
  items: Array<ApiMcpConnection>
}

export type ConnectMcpProviderPayload = {
  provider: string
  transport?: "mock" | "http_jsonrpc"
  server_url?: string | null
  access_token?: string | null
}

export type ApiAgentQueryResponse = {
  answer: string
  tool_calls: Array<{
    provider: string
    tool: string
    arguments: Record<string, unknown>
    result: unknown
  }>
  available_tools: Array<ApiMcpTool>
}

const CHAT_USER_STORAGE_KEY = "quama-chat-user-id"
type AuthTokenProvider = () => Promise<string | null>
let authTokenProvider: AuthTokenProvider | null = null

export type ApiErrorKind =
  | "network"
  | "validation"
  | "provider"
  | "not_found"
  | "server"
  | "http"

export class ApiError extends Error {
  status: number | null
  code: string
  kind: ApiErrorKind

  constructor({
    message,
    status,
    code,
    kind,
  }: {
    message: string
    status: number | null
    code: string
    kind: ApiErrorKind
  }) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.kind = kind
  }
}

function getApiBaseUrl() {
  const value = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
  return value.replace(/\/$/, "")
}

type ApiRequestOptions = {
  init?: RequestInit
  includeUserId?: boolean
}

async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const { init, includeUserId = true } = options
  const headers = new Headers(init?.headers)
  headers.set("Accept", "application/json")

  if (init?.body) {
    headers.set("Content-Type", "application/json")
  }

  if (includeUserId) {
    await applyUserAuthHeader(headers)
  }

  let response: Response

  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      headers,
    })
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }

    throw new ApiError({
      status: null,
      code: "network_error",
      kind: "network",
      message: `Could not reach the backend at ${getApiBaseUrl()}. Make sure the backend server is running on port 8000.`,
    })
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`
    let code = "http_error"
    const rawBody = await response.text()

    try {
      const payload = JSON.parse(rawBody) as {
        error?: { code?: string; message?: string }
        detail?: string
      }
      if (payload.error?.message) {
        detail = payload.error.message
      } else if (payload.detail) {
        detail = payload.detail
      }
      if (payload.error?.code) {
        code = payload.error.code
      }
    } catch {
      if (rawBody.trim()) {
        detail = rawBody
      } else {
        detail = response.statusText || detail
      }
    }

    throw new ApiError({
      status: response.status,
      code,
      kind: getErrorKind(response.status),
      message: detail,
    })
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

function normalizeMessage(message: ApiMessage): ApiMessage {
  return {
    ...message,
    metadata: message.metadata ?? null,
  }
}

export function getChatUserId() {
  const configuredUserId = import.meta.env.VITE_CHAT_USER_ID
  if (configuredUserId) {
    return configuredUserId
  }

  if (typeof window === "undefined") {
    return "local-dev-user"
  }

  const existingUserId = window.localStorage.getItem(CHAT_USER_STORAGE_KEY)
  if (existingUserId) {
    return existingUserId
  }

  const generatedUserId = crypto.randomUUID()

  window.localStorage.setItem(CHAT_USER_STORAGE_KEY, generatedUserId)
  return generatedUserId
}

function canUseUserIdFallback() {
  return import.meta.env.DEV || Boolean(import.meta.env.VITE_CHAT_USER_ID)
}

export function setAuthTokenProvider(provider: AuthTokenProvider | null) {
  authTokenProvider = provider
}

export async function applyUserAuthHeader(headers: Headers) {
  if (authTokenProvider) {
    const token = await authTokenProvider()

    headers.delete("X-User-Id")
    if (token) {
      headers.set("Authorization", `Bearer ${token}`)
    }
    return
  }

  if (!canUseUserIdFallback()) {
    headers.delete("X-User-Id")
    return
  }

  headers.set("X-User-Id", getChatUserId())
}

export async function fetchModels() {
  return apiRequest<ApiModelsResponse>("/api/v1/models", {
    includeUserId: false,
  })
}

export async function listConversations() {
  return apiRequest<ApiConversationList>(
    "/api/v1/conversations?skip=0&limit=50"
  )
}

export async function fetchConversationDetail(
  conversationId: string,
  signal?: AbortSignal
) {
  const response = await apiRequest<ApiConversationDetail>(
    `/api/v1/conversations/${conversationId}`,
    { init: { signal } }
  )
  return {
    ...response,
    messages: response.messages.map((message) => normalizeMessage(message)),
  }
}

export async function createConversation(payload: CreateConversationPayload) {
  return apiRequest<ApiConversation>("/api/v1/conversations", {
    init: {
      method: "POST",
      body: JSON.stringify(payload),
    },
  })
}

export async function sendMessage(payload: SendMessagePayload) {
  return apiRequest<SendMessageResponse>("/api/v1/chat/message", {
    init: {
      method: "POST",
      body: JSON.stringify(payload),
    },
  })
}

export async function listAssets() {
  return apiRequest<AssetListResponse>("/api/v1/assets")
}

export async function uploadAssets(payload: AssetUploadPayload) {
  return apiRequest<AssetUploadResponse>("/api/v1/assets", {
    init: {
      method: "POST",
      body: JSON.stringify(payload),
    },
  })
}

export async function deleteAsset(assetId: string) {
  await apiRequest<void>(`/api/v1/assets/${assetId}`, {
    init: { method: "DELETE" },
  })
}

export async function deleteConversation(conversationId: string) {
  await apiRequest<void>(`/api/v1/conversations/${conversationId}`, {
    init: { method: "DELETE" },
  })
}

export async function connectAngelOneBroker(payload: BrokerConnectPayload) {
  return apiRequest<ApiBrokerConnectResponse>(
    "/api/v1/brokers/angel-one/connect",
    {
      init: {
        method: "POST",
        body: JSON.stringify(payload),
      },
    }
  )
}

export async function disconnectAngelOneBroker() {
  return apiRequest<ApiBrokerDisconnectResponse>(
    "/api/v1/brokers/angel-one/disconnect",
    {
      init: { method: "DELETE" },
    }
  )
}

export async function connectGrowwBroker(payload: GrowwConnectPayload) {
  return apiRequest<ApiBrokerConnectResponse>("/api/v1/brokers/groww/connect", {
    init: {
      method: "POST",
      body: JSON.stringify(payload),
    },
  })
}

export async function disconnectGrowwBroker() {
  return apiRequest<ApiBrokerDisconnectResponse>(
    "/api/v1/brokers/groww/disconnect",
    {
      init: { method: "DELETE" },
    }
  )
}

export async function fetchBrokerStatus() {
  return apiRequest<ApiBrokerStatusResponse>("/api/v1/brokers/status")
}

export async function fetchAngelOneHoldings() {
  return apiRequest<Array<Record<string, unknown>>>(
    "/api/v1/brokers/angel-one/holdings"
  )
}

export async function fetchAngelOnePositions() {
  return apiRequest<Array<Record<string, unknown>>>(
    "/api/v1/brokers/angel-one/positions"
  )
}

export async function fetchAngelOneFunds() {
  return apiRequest<Record<string, unknown>>("/api/v1/brokers/angel-one/funds")
}

export async function fetchAngelOnePortfolio() {
  return apiRequest<ApiBrokerPortfolioResponse>(
    "/api/v1/brokers/angel-one/portfolio"
  )
}

export async function fetchBrokerPortfolioHistory(
  broker: string,
  period: string
) {
  return apiRequest<{
    period: string
    history: Array<Record<string, unknown>>
  }>(`/api/v1/portfolio/${broker}/history?period=${period}`)
}

export async function fetchGrowwPortfolio() {
  return apiRequest<ApiBrokerPortfolioResponse>(
    "/api/v1/brokers/groww/portfolio"
  )
}

export async function listMcpProviders() {
  return apiRequest<Array<ApiMcpProvider>>("/api/v1/mcp/providers")
}

export async function listMcpConnections() {
  return apiRequest<ApiMcpConnectionList>("/api/v1/mcp/connections")
}

export async function connectMcpProvider(payload: ConnectMcpProviderPayload) {
  return apiRequest<ApiMcpConnection>("/api/v1/mcp/connections", {
    init: {
      method: "POST",
      body: JSON.stringify({
        provider: payload.provider,
        transport: payload.transport ?? "mock",
        server_url: payload.server_url ?? null,
        access_token: payload.access_token ?? null,
      }),
    },
  })
}

export async function disconnectMcpProvider(provider: string) {
  await apiRequest<void>(
    `/api/v1/mcp/connections/${encodeURIComponent(provider)}`,
    {
      init: { method: "DELETE" },
    }
  )
}

export async function queryAgent(message: string) {
  return apiRequest<ApiAgentQueryResponse>("/api/v1/agent/query", {
    init: {
      method: "POST",
      body: JSON.stringify({ message }),
    },
  })
}

export async function registerMarketSubscriptions(
  payload: MarketSubscriptionPayload
) {
  return apiRequest<ApiMarketSubscriptionResponse>(
    "/api/v1/market/subscriptions",
    {
      init: {
        method: "POST",
        body: JSON.stringify({
          mode: payload.mode ?? 1,
          replace: payload.replace ?? true,
          instruments: payload.instruments,
        }),
      },
    }
  )
}

export async function streamMarketData({
  instrumentTokens,
  signal,
  onEvent,
}: {
  instrumentTokens: Array<string>
  signal?: AbortSignal
  onEvent: (event: ApiMarketStreamEvent) => void
}) {
  const uniqueTokens = Array.from(
    new Set(
      instrumentTokens
        .map((token) => token.trim())
        .filter((token) => token.length > 0)
    )
  )

  if (uniqueTokens.length === 0) {
    return
  }

  const query = new URLSearchParams()
  uniqueTokens.forEach((instrumentToken) => {
    query.append("instrument_token", instrumentToken)
  })

  let response: Response

  try {
    response = await fetch(
      resolveApiUrl(`/api/v1/market/stream?${query.toString()}`),
      {
        headers: await buildStreamHeaders(),
        signal,
      }
    )
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }

    throw new ApiError({
      status: null,
      code: "network_error",
      kind: "network",
      message: `Could not reach the backend at ${resolveApiUrl("")}. Make sure the backend server is running on port 8000.`,
    })
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`
    let code = "http_error"
    const rawBody = await response.text()

    try {
      const payload = JSON.parse(rawBody) as {
        error?: { code?: string; message?: string }
        detail?: string
      }
      if (payload.error?.message) {
        detail = payload.error.message
      } else if (payload.detail) {
        detail = payload.detail
      }
      if (payload.error?.code) {
        code = payload.error.code
      }
    } catch {
      if (rawBody.trim()) {
        detail = rawBody
      }
    }

    throw new ApiError({
      status: response.status,
      code,
      kind: getErrorKind(response.status),
      message: detail,
    })
  }

  if (!response.body) {
    throw new ApiError({
      status: 500,
      code: "stream_unavailable",
      kind: "server",
      message: "Streaming is unavailable in this browser.",
    })
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  for (;;) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split("\n\n")
    buffer = events.pop() ?? ""

    for (const event of events) {
      const dataLines = event
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice(6))

      if (dataLines.length === 0) {
        continue
      }

      const data = dataLines.join("\n")
      if (data === "[DONE]") {
        return
      }

      onEvent(JSON.parse(data) as ApiMarketStreamEvent)
    }
  }
}

async function buildStreamHeaders() {
  const headers = new Headers({
    Accept: "text/event-stream",
  })
  await applyUserAuthHeader(headers)
  return headers
}

export function resolveApiUrl(path: string) {
  if (/^https?:\/\//.test(path)) {
    return path
  }

  if (!path.startsWith("/")) {
    return `${getApiBaseUrl()}/${path}`
  }

  return `${getApiBaseUrl()}${path}`
}

function getErrorKind(status: number): ApiErrorKind {
  if (status === 404) {
    return "not_found"
  }
  if (status === 422) {
    return "validation"
  }
  if (status === 502) {
    return "provider"
  }
  if (status >= 500) {
    return "server"
  }
  return "http"
}

export function isAbortError(error: unknown): error is DOMException {
  return error instanceof DOMException && error.name === "AbortError"
}
