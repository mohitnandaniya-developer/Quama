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

export function createNetworkError() {
  return new ApiError({
    status: null,
    code: "network_error",
    kind: "network",
    message: `Could not connect to the backend at ${getApiBaseUrl()}. Verify that the backend is online and allows requests from this frontend origin.`,
  })
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
    // Add 45s timeout to fetch requests
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 45000)

    try {
      response = await fetch(`${getApiBaseUrl()}${path}`, {
        ...init,
        headers,
        signal: controller.signal,
      })
    } finally {
      clearTimeout(timeoutId)
    }
  } catch (error) {
    if (isAbortError(error)) {
      throw createNetworkError()
    }

    throw createNetworkError()
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

function getChatUserId() {
  return import.meta.env.VITE_CHAT_USER_ID?.trim() ?? ""
}

export function canUseUserIdFallback() {
  return Boolean(getChatUserId())
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
