export function MarketCanvas() {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background">
      <div className="flex min-h-0 flex-1 items-center justify-center p-4 sm:p-6">
        <div className="flex max-w-sm flex-col items-center gap-2 text-center">
          <div className="text-sm font-medium text-foreground">Market</div>
          <p className="text-sm text-muted-foreground">
            Live market tools will appear here.
          </p>
        </div>
      </div>
    </div>
  )
}
