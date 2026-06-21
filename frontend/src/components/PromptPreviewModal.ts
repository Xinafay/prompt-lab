import React from "react";

import type { PromptPreviewItem, PromptPreviewResponse } from "../types";
import { CodeViewer } from "./CodeViewer";

interface PromptPreviewModalProps {
  preview: PromptPreviewResponse;
  isAccepting: boolean;
  onAccept: () => void;
  onReject: () => void;
}

function promptMeta(prompt: PromptPreviewItem): string[] {
  const items = [`Model ${prompt.model}`];
  if (prompt.case_id) items.push(`Case ${prompt.case_id}`);
  if (prompt.repeat_index !== null && prompt.repeat_index !== undefined) {
    items.push(`repeat ${prompt.repeat_index}`);
  }
  if (prompt.validator_id) items.push(`Validator ${prompt.validator_id}`);
  items.push(`${prompt.character_count} characters`);
  items.push(`${prompt.word_count} words`);
  return items;
}

export function PromptPreviewModal({
  preview,
  isAccepting,
  onAccept,
  onReject
}: PromptPreviewModalProps) {
  return React.createElement(
    "div",
    {
      className: "modal-backdrop prompt-preview-backdrop",
      onMouseDown: onReject
    },
    React.createElement(
      "section",
      {
        "aria-label": "Prompt preview",
        "aria-modal": "true",
        className: "prompt-preview-modal",
        onMouseDown: (event: React.MouseEvent) => event.stopPropagation(),
        role: "dialog"
      },
      React.createElement(
        "header",
        { className: "prompt-preview-header" },
        React.createElement("div", null, [
          React.createElement("h2", { key: "title" }, "Preview prompts"),
          React.createElement(
            "p",
            { key: "summary" },
            `${preview.prompts.length} prompt${
              preview.prompts.length === 1 ? "" : "s"
            } prepared`
          )
        ])
      ),
      preview.warnings.length > 0
        ? React.createElement(
            "div",
            { className: "prompt-preview-warnings" },
            preview.warnings.map((warning) =>
              React.createElement("p", { key: warning }, warning)
            )
          )
        : null,
      React.createElement(
        "div",
        {
          className:
            preview.prompts.length === 1
              ? "prompt-preview-list prompt-preview-list-single"
              : "prompt-preview-list"
        },
        preview.prompts.map((prompt, index) =>
          React.createElement(
            "article",
            { className: "prompt-preview-card", key: `${prompt.kind}-${index}` },
            React.createElement("div", { className: "prompt-preview-card-header" }, [
              React.createElement("h3", { key: "title" }, prompt.title),
              React.createElement(
                "div",
                { className: "prompt-preview-meta", key: "meta" },
                promptMeta(prompt).map((item) =>
                  React.createElement("span", { key: item }, item)
                )
              )
            ]),
            React.createElement(CodeViewer, {
              label: "Prompt",
              language: "markdown-jinja",
              value: prompt.prompt
            })
          )
        )
      ),
      React.createElement("footer", { className: "prompt-preview-footer" }, [
        React.createElement(
          "button",
          {
            className: "secondary-action",
            disabled: isAccepting,
            key: "reject",
            onClick: onReject,
            type: "button"
          },
          "Reject"
        ),
        React.createElement(
          "button",
          {
            className: "primary-action",
            disabled: isAccepting,
            key: "accept",
            onClick: onAccept,
            type: "button"
          },
          isAccepting ? "Sending..." : "Accept"
        )
      ])
    )
  );
}
