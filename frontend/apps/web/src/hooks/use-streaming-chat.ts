import {
  ApiError,
  applyUserAuthHeader,
  isAbortError,
  resolveApiUrl,
} from "@/lib/chat-api"

type SendStreamingMessageParams = {
  conversation_id: string
  content: string
  provider?: string
  model_name?: string
  attachments?: Array<{
    kind: "file" | "image"
    name: string
    mime_type: string
    text_content?: string
    data_url?: string
  }>
  signal?: AbortSignal
  onChunk: (chunk: string) => void
}

export function useStreamingChat() {
  async function sendStreamingMessage({
    conversation_id,
    content,
    provider,
    model_name,
    attachments = [],
    signal,
    onChunk,
  }: SendStreamingMessageParams) {
    let response: Response

    try {
      const headers = new Headers({
        Accept: "text/event-stream",
        "Content-Type": "application/json",
      })
      await applyUserAuthHeader(headers)

      response = await fetch(resolveApiUrl("/api/v1/chat/stream"), {
        method: "POST",
        headers,
        body: JSON.stringify({
          conversation_id,
          content,
          provider,
          model_name,
          attachments,
        }),
        signal,
      })
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
        kind:
          response.status === 404
            ? "not_found"
            : response.status === 422
              ? "validation"
              : response.status === 502
                ? "provider"
                : response.status >= 500
                  ? "server"
                  : "http",
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

    let readResult = await reader.read()
    while (!readResult.done) {
      buffer += decoder.decode(readResult.value, { stream: true })
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
        onChunk(data)
      }

      readResult = await reader.read()
    }
  }

  return { sendStreamingMessage }
}
