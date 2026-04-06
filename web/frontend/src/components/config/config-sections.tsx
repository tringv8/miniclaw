import type { ReactNode } from "react"

import {
  type CoreConfigForm,
  type LauncherForm,
} from "@/components/config/form-model"
import { Field, SwitchCardField } from "@/components/shared-form"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { useTranslation } from "react-i18next"

type UpdateCoreField = <K extends keyof CoreConfigForm>(
  key: K,
  value: CoreConfigForm[K],
) => void

type UpdateLauncherField = <K extends keyof LauncherForm>(
  key: K,
  value: LauncherForm[K],
) => void

interface ConfigSectionCardProps {
  title: string
  description?: string
  children: ReactNode
}

function ConfigSectionCard({
  title,
  description,
  children,
}: ConfigSectionCardProps) {
  return (
    <Card size="sm">
      <CardHeader className="border-border border-b">
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent className="pt-0">
        <div className="divide-border/70 divide-y">{children}</div>
      </CardContent>
    </Card>
  )
}

interface AgentSectionProps {
  form: CoreConfigForm
  onFieldChange: UpdateCoreField
}

export function AgentSection({ form, onFieldChange }: AgentSectionProps) {
  const { t } = useTranslation()
  return (
    <ConfigSectionCard
      title={t("pages.config.agent_title")}
      description={t("pages.config.agent_desc")}
    >
      <Field
        label={t("pages.config.workspace_label")}
        hint={t("pages.config.workspace_label_hint")}
        layout="setting-row"
      >
        <Input
          value={form.workspace}
          onChange={(e) => onFieldChange("workspace", e.target.value)}
          placeholder="~/.miniclaw/workspace"
        />
      </Field>

      <SwitchCardField
        label={t("pages.config.restrict_tools_label")}
        hint={t("pages.config.restrict_tools_hint")}
        layout="setting-row"
        checked={form.restrictToWorkspace}
        onCheckedChange={(checked) =>
          onFieldChange("restrictToWorkspace", checked)
        }
      />

      <SwitchCardField
        label={t("pages.config.split_marker_label")}
        hint={t("pages.config.split_marker_hint")}
        layout="setting-row"
        checked={form.splitOnMarker}
        onCheckedChange={(checked) => onFieldChange("splitOnMarker", checked)}
      />

      <SwitchCardField
        label={t("pages.config.tool_feedback_label")}
        hint={t("pages.config.tool_feedback_hint_toggle")}
        layout="setting-row"
        checked={form.toolFeedbackEnabled}
        onCheckedChange={(checked) =>
          onFieldChange("toolFeedbackEnabled", checked)
        }
      />

      {form.toolFeedbackEnabled ? (
        <Field
          label={t("pages.config.tool_feedback_max_args_label")}
          hint={t("pages.config.tool_feedback_max_args_hint")}
          layout="setting-row"
        >
          <Input
            type="number"
            min={0}
            value={form.toolFeedbackMaxArgsLength}
            onChange={(e) =>
              onFieldChange("toolFeedbackMaxArgsLength", e.target.value)
            }
          />
        </Field>
      ) : null}

      <Field
        label={t("pages.config.max_tokens_label")}
        hint={t("pages.config.max_tokens_label_hint")}
        layout="setting-row"
      >
        <Input
          type="number"
          min={1}
          value={form.maxTokens}
          onChange={(e) => onFieldChange("maxTokens", e.target.value)}
        />
      </Field>

      <Field
        label={t("pages.config.context_window_label")}
        hint={t("pages.config.context_window_label_hint")}
        layout="setting-row"
      >
        <Input
          type="number"
          min={1}
          value={form.contextWindowTokens}
          onChange={(e) => onFieldChange("contextWindowTokens", e.target.value)}
        />
      </Field>

      <Field
        label={t("pages.config.max_tool_iter_label")}
        hint={t("pages.config.max_tool_iter_hint")}
        layout="setting-row"
      >
        <Input
          type="number"
          min={1}
          value={form.maxToolIterations}
          onChange={(e) => onFieldChange("maxToolIterations", e.target.value)}
        />
      </Field>

      <Field
        label={t("pages.config.summarize_threshold_label")}
        hint={t("pages.config.summarize_threshold_label_hint")}
        layout="setting-row"
      >
        <Input
          type="number"
          min={1}
          value={form.summarizeMessageThreshold}
          onChange={(e) =>
            onFieldChange("summarizeMessageThreshold", e.target.value)
          }
        />
      </Field>

      <Field
        label={t("pages.config.summarize_token_label")}
        hint={t("pages.config.summarize_token_hint")}
        layout="setting-row"
      >
        <Input
          type="number"
          min={1}
          max={100}
          value={form.summarizeTokenPercent}
          onChange={(e) =>
            onFieldChange("summarizeTokenPercent", e.target.value)
          }
        />
      </Field>

      <Field
        label={t("pages.config.temperature_label")}
        hint={t("pages.config.temperature_hint")}
        layout="setting-row"
      >
        <Input
          value={form.temperature}
          onChange={(e) => onFieldChange("temperature", e.target.value)}
        />
      </Field>

      <Field
        label={t("pages.config.reasoning_label")}
        hint={t("pages.config.reasoning_hint")}
        layout="setting-row"
      >
        <Input
          value={form.reasoningEffort}
          onChange={(e) => onFieldChange("reasoningEffort", e.target.value)}
          placeholder="medium"
        />
      </Field>

      <Field
        label={t("pages.config.timezone_label")}
        hint={t("pages.config.timezone_hint")}
        layout="setting-row"
      >
        <Input
          value={form.timezone}
          onChange={(e) => onFieldChange("timezone", e.target.value)}
          placeholder="Asia/Saigon"
        />
      </Field>
    </ConfigSectionCard>
  )
}

interface GatewaySectionProps {
  form: CoreConfigForm
  onFieldChange: UpdateCoreField
}

export function GatewaySection({
  form,
  onFieldChange,
}: GatewaySectionProps) {
  const { t } = useTranslation()
  return (
    <ConfigSectionCard
      title={t("pages.config.gateway_title")}
      description={t("pages.config.gateway_desc")}
    >
      <Field
        label={t("pages.config.gateway_host_label")}
        hint={t("pages.config.gateway_host_hint")}
        layout="setting-row"
      >
        <Input
          value={form.gatewayHost}
          onChange={(e) => onFieldChange("gatewayHost", e.target.value)}
          placeholder="0.0.0.0"
        />
      </Field>

      <Field
        label={t("pages.config.gateway_port_label")}
        hint={t("pages.config.gateway_port_hint")}
        layout="setting-row"
      >
        <Input
          type="number"
          min={1}
          max={65535}
          value={form.gatewayPort}
          onChange={(e) => onFieldChange("gatewayPort", e.target.value)}
        />
      </Field>

      <SwitchCardField
        label={t("pages.config.heartbeat_label")}
        hint={t("pages.config.heartbeat_hint_toggle")}
        layout="setting-row"
        checked={form.heartbeatEnabled}
        onCheckedChange={(checked) =>
          onFieldChange("heartbeatEnabled", checked)
        }
      />

      {form.heartbeatEnabled ? (
        <>
          <Field
            label={t("pages.config.heartbeat_interval_label")}
            hint={t("pages.config.heartbeat_interval_label_hint")}
            layout="setting-row"
          >
            <Input
              type="number"
              min={1}
              value={form.heartbeatIntervalSeconds}
              onChange={(e) =>
                onFieldChange("heartbeatIntervalSeconds", e.target.value)
              }
            />
          </Field>

          <Field
            label={t("pages.config.heartbeat_keep_label")}
            hint={t("pages.config.heartbeat_keep_hint")}
            layout="setting-row"
          >
            <Input
              type="number"
              min={0}
              value={form.heartbeatKeepRecentMessages}
              onChange={(e) =>
                onFieldChange("heartbeatKeepRecentMessages", e.target.value)
              }
            />
          </Field>
        </>
      ) : null}
    </ConfigSectionCard>
  )
}

interface ExecSectionProps {
  form: CoreConfigForm
  onFieldChange: UpdateCoreField
}

export function ExecSection({ form, onFieldChange }: ExecSectionProps) {
  const { t } = useTranslation()
  return (
    <ConfigSectionCard
      title={t("pages.config.exec_title")}
      description={t("pages.config.exec_desc")}
    >
      <SwitchCardField
        label={t("pages.config.exec_enable_label")}
        hint={t("pages.config.exec_enable_hint")}
        layout="setting-row"
        checked={form.execEnabled}
        onCheckedChange={(checked) => onFieldChange("execEnabled", checked)}
      />

      <Field
        label={t("pages.config.exec_timeout_label")}
        hint={t("pages.config.exec_timeout_hint")}
        layout="setting-row"
      >
        <Input
          type="number"
          min={0}
          value={form.execTimeout}
          disabled={!form.execEnabled}
          onChange={(e) => onFieldChange("execTimeout", e.target.value)}
        />
      </Field>

      <Field
        label={t("pages.config.exec_path_label")}
        hint={t("pages.config.exec_path_hint")}
        layout="setting-row"
      >
        <Textarea
          value={form.execPathAppend}
          disabled={!form.execEnabled}
          className="min-h-[88px]"
          onChange={(e) => onFieldChange("execPathAppend", e.target.value)}
          placeholder="C:\\Tools\\bin"
        />
      </Field>
    </ConfigSectionCard>
  )
}

interface WebSearchSectionProps {
  form: CoreConfigForm
  onFieldChange: UpdateCoreField
}

export function WebSearchSection({
  form,
  onFieldChange,
}: WebSearchSectionProps) {
  const { t } = useTranslation()
  return (
    <ConfigSectionCard
      title={t("pages.config.web_title")}
      description={t("pages.config.web_desc")}
    >
      <Field
        label={t("pages.config.web_proxy_label")}
        hint={t("pages.config.web_proxy_hint")}
        layout="setting-row"
      >
        <Input
          value={form.webProxy}
          onChange={(e) => onFieldChange("webProxy", e.target.value)}
          placeholder="http://127.0.0.1:7890"
        />
      </Field>

      <Field
        label={t("pages.config.web_search_provider_label")}
        hint={t("pages.config.web_search_provider_hint")}
        layout="setting-row"
      >
        <Input
          value={form.webSearchProvider}
          onChange={(e) => onFieldChange("webSearchProvider", e.target.value)}
          placeholder="brave"
        />
      </Field>

      <Field
        label={t("pages.config.web_search_api_key_label")}
        hint={t("pages.config.web_search_api_key_hint")}
        layout="setting-row"
      >
        <Input
          value={form.webSearchApiKey}
          onChange={(e) => onFieldChange("webSearchApiKey", e.target.value)}
          placeholder={t("pages.config.web_search_api_key_label")}
        />
      </Field>

      <Field
        label={t("pages.config.web_search_base_url_label")}
        hint={t("pages.config.web_search_base_url_hint")}
        layout="setting-row"
      >
        <Input
          value={form.webSearchBaseUrl}
          onChange={(e) => onFieldChange("webSearchBaseUrl", e.target.value)}
          placeholder="https://search.example.com"
        />
      </Field>

      <Field
        label={t("pages.config.web_max_results_label")}
        hint={t("pages.config.web_max_results_hint")}
        layout="setting-row"
      >
        <Input
          type="number"
          min={1}
          value={form.webSearchMaxResults}
          onChange={(e) => onFieldChange("webSearchMaxResults", e.target.value)}
        />
      </Field>
    </ConfigSectionCard>
  )
}

interface LauncherSectionProps {
  launcherForm: LauncherForm
  onFieldChange: UpdateLauncherField
  disabled: boolean
}

export function LauncherSection({
  launcherForm,
  onFieldChange,
  disabled,
}: LauncherSectionProps) {
  const { t } = useTranslation()
  return (
    <ConfigSectionCard
      title={t("pages.config.launcher_title")}
      description={t("pages.config.launcher_desc")}
    >
      <SwitchCardField
        label={t("pages.config.launcher_public_label")}
        hint={t("pages.config.launcher_public_hint")}
        layout="setting-row"
        checked={launcherForm.publicAccess}
        disabled={disabled}
        onCheckedChange={(checked) => onFieldChange("publicAccess", checked)}
      />

      <Field
        label={t("pages.config.launcher_port_label")}
        hint={t("pages.config.launcher_port_hint")}
        layout="setting-row"
      >
        <Input
          type="number"
          min={1}
          max={65535}
          value={launcherForm.port}
          disabled={disabled}
          onChange={(e) => onFieldChange("port", e.target.value)}
        />
      </Field>

      <Field
        label={t("pages.config.launcher_cidrs_label")}
        hint={t("pages.config.launcher_cidrs_hint")}
        layout="setting-row"
      >
        <Textarea
          value={launcherForm.allowedCIDRsText}
          disabled={disabled}
          placeholder="127.0.0.1/32"
          className="min-h-[88px]"
          onChange={(e) => onFieldChange("allowedCIDRsText", e.target.value)}
        />
      </Field>
    </ConfigSectionCard>
  )
}

interface AutoStartSectionProps {
  enabled: boolean
  hint: string
  disabled: boolean
  onChange: (checked: boolean) => void
}

export function AutoStartSection({
  enabled,
  hint,
  disabled,
  onChange,
}: AutoStartSectionProps) {
  const { t } = useTranslation()
  return (
    <ConfigSectionCard
      title={t("pages.config.autostart_title")}
      description={t("pages.config.autostart_desc")}
    >
      <SwitchCardField
        label={t("pages.config.autostart_login_label")}
        hint={hint}
        layout="setting-row"
        checked={enabled}
        disabled={disabled}
        onCheckedChange={onChange}
      />
    </ConfigSectionCard>
  )
}
