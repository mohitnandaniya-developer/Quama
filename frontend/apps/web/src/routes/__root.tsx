import { ClerkProvider } from "@clerk/tanstack-react-start"
import { shadcn } from "@clerk/ui/themes"
import { HeadContent, Scripts, createRootRoute } from "@tanstack/react-router"
import { Toaster } from "sonner"

import { TooltipProvider } from "@workspace/ui/components/tooltip"
import appCss from "@workspace/ui/globals.css?url"

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
    <html lang="en" className="dark">
      <head>
        <HeadContent />
      </head>
      <body className="min-h-svh bg-background text-foreground antialiased">
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
