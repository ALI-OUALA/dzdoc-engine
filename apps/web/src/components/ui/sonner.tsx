"use client"

import { CheckCircle, Info, SpinnerGap, Warning, XCircle } from "@phosphor-icons/react"
import { Toaster as Sonner, type ToasterProps } from "sonner"

const Toaster = (props: ToasterProps) => (
  <Sonner
    theme="system"
    className="toaster group"
    icons={{
      success: <CheckCircle />,
      info: <Info />,
      warning: <Warning />,
      error: <XCircle />,
      loading: <SpinnerGap className="animate-spin" />,
    }}
    style={{
      "--normal-bg": "var(--popover)",
      "--normal-text": "var(--popover-foreground)",
      "--normal-border": "var(--border)",
      "--border-radius": "var(--radius)",
    } as React.CSSProperties}
    {...props}
  />
)

export { Toaster }
