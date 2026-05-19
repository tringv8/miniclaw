import { PageHeader } from "@/components/page-header"

import { DeviceCodeSheet } from "./device-code-sheet"
import { LogoutConfirmDialog } from "./logout-confirm-dialog"
import { OpenAICredentialCard } from "./openai-credential-card"
import { useCredentialsPage } from "@/hooks/use-credentials-page"

export function CredentialsPage() {
  const {
    loading,
    error,
    activeAction,
    flowHint,
    openAIToken,
    openaiStatus,
    logoutDialogOpen,
    logoutProviderLabel,
    deviceSheetOpen,
    deviceFlow,
    setOpenAIToken,
    startBrowserOAuth,
    startOpenAIDeviceCode,
    stopLoading,
    saveToken,
    askLogout,
    handleConfirmLogout,
    handleLogoutDialogOpenChange,
    handleDeviceSheetOpenChange,
  } = useCredentialsPage()

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Credentials" />

      <div className="min-h-0 flex-1 overflow-y-auto px-4 sm:px-6">
        <div className="pt-2">
          <p className="text-muted-foreground text-sm">
            Manage OAuth and token-based credentials for supported providers.
          </p>
        </div>

        {error ? (
          <div className="text-destructive bg-destructive/10 mt-4 rounded-lg px-4 py-3 text-sm">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="text-muted-foreground py-8 text-sm">Loading...</div>
        ) : (
          <div className="grid grid-cols-1 gap-4 py-5 xl:grid-cols-1">
            <OpenAICredentialCard
              status={openaiStatus}
              activeAction={activeAction}
              token={openAIToken}
              onTokenChange={setOpenAIToken}
              onStartBrowserOAuth={() => void startBrowserOAuth("openai")}
              onStartDeviceCode={() => void startOpenAIDeviceCode()}
              onStopLoading={stopLoading}
              onSaveToken={() => void saveToken("openai", openAIToken)}
              onAskLogout={() => askLogout("openai")}
            />
          </div>
        )}
      </div>

      <LogoutConfirmDialog
        open={logoutDialogOpen}
        providerLabel={logoutProviderLabel}
        isSubmitting={activeAction.endsWith(":logout")}
        onOpenChange={handleLogoutDialogOpenChange}
        onConfirm={handleConfirmLogout}
      />

      <DeviceCodeSheet
        open={deviceSheetOpen}
        flow={deviceFlow}
        flowHint={flowHint}
        onOpenChange={handleDeviceSheetOpenChange}
      />
    </div>
  )
}
