import { ClerkProvider } from "@clerk/tanstack-react-start"
import { shadcn } from "@clerk/ui/themes"
import { HeadContent, Scripts, createRootRoute } from "@tanstack/react-router"
import { useEffect } from "react"
import { Toaster } from "sonner"

import { TooltipProvider } from "@workspace/ui/components/tooltip"
import appCss from "@workspace/ui/globals.css?url"

const THEME_STORAGE_KEY = "quama-theme"
const THEME_BOOTSTRAP_SCRIPT = `
  try {
    const theme = window.localStorage.getItem("${THEME_STORAGE_KEY}")
    document.documentElement.classList.toggle("dark", theme !== "light")
  } catch {}
`

export const Route = createRootRoute({
  head: () => ({
    meta: [
      {
        charSet: "utf-8",
      },
      {
        name: "viewport",
        content: "width=device-width, initial-scale=1",
      },
      {
        title: "Quama",
      },
    ],
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
    ],
  }),
  notFoundComponent: () => (
    <div className="p-4 text-center">
      <h1>404 Not Found</h1>
      <p>The page you are looking for does not exist.</p>
    </div>
  ),
  shellComponent: RootDocument,
})

function RootDocument({ children }: { children: React.ReactNode }) {
  const clerkKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP_SCRIPT }} />
        <HeadContent />
      </head>
      <body className="min-h-svh bg-background text-foreground antialiased">
        <ThemeKeyboardShortcut />
        {clerkKey ? (
          <ClerkProvider
            publishableKey={clerkKey}
            appearance={{ theme: shadcn }}
            signInUrl="/sign-in"
            signUpUrl="/sign-up"
            signInFallbackRedirectUrl="/"
            signUpFallbackRedirectUrl="/"
          >
            <TooltipProvider>
              {children}
              <Toaster richColors position="top-right" />
            </TooltipProvider>
          </ClerkProvider>
        ) : (
          <TooltipProvider>
            {children}
            <Toaster richColors position="top-right" />
          </TooltipProvider>
        )}
        <Scripts />
      </body>
    </html>
  )
}

function ThemeKeyboardShortcut() {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (
        event.defaultPrevented ||
        event.repeat ||
        event.metaKey ||
        event.ctrlKey ||
        event.altKey ||
        event.key.toLowerCase() !== "d" ||
        isEditableTarget(event.target)
      ) {
        return
      }

      const root = document.documentElement
      const useDarkTheme = !root.classList.contains("dark")
      root.classList.toggle("dark", useDarkTheme)

      try {
        window.localStorage.setItem(
          THEME_STORAGE_KEY,
          useDarkTheme ? "dark" : "light"
        )
      } catch {}
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])

  return null
}

function isEditableTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) {
    return false
  }

  return Boolean(
    target.closest("input, textarea, select, [contenteditable='true']")
  )
}
