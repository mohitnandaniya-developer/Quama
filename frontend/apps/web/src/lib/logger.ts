/**
 * Lightweight structured logger for the Quama frontend.
 * In production builds, debug and info logs are suppressed.
 */

const isDev = import.meta.env.DEV

type LogLevel = "debug" | "info" | "warn" | "error"

function log(level: LogLevel, message: string, meta?: unknown): void {
  if (!isDev && (level === "debug" || level === "info")) {
    return
  }

  const prefix = `[quama:${level.toUpperCase()}]`
  if (meta !== undefined) {
    console[level](prefix, message, meta)
  } else {
    console[level](prefix, message)
  }
}

export const logger = {
  debug: (message: string, meta?: unknown) => log("debug", message, meta),
  info: (message: string, meta?: unknown) => log("info", message, meta),
  warn: (message: string, meta?: unknown) => log("warn", message, meta),
  error: (message: string, meta?: unknown) => log("error", message, meta),
}
