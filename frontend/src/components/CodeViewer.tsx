import { EditorState, type Extension } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  EditorView,
  MatchDecorator,
  ViewPlugin,
  type ViewUpdate
} from "@codemirror/view";
import { markdown } from "@codemirror/lang-markdown";
import { python } from "@codemirror/lang-python";
import { json } from "@codemirror/lang-json";
import { unifiedMergeView } from "@codemirror/merge";
import { basicSetup } from "codemirror";
import React, { useEffect, useRef } from "react";

import "./CodeViewer.css";

export type CodeViewerProps = {
  label: string;
  language: "json" | "markdown-jinja" | "python" | "text";
  value: string;
};

export type DiffViewerProps = {
  label: string;
  language: "markdown-jinja" | "python";
  original: string;
  value: string;
};

type CodeLanguage = CodeViewerProps["language"];

const canUseDOM = () =>
  typeof window !== "undefined" && typeof document !== "undefined";

const jinjaDecorator = new MatchDecorator({
  regexp: /\{\{[^\n]*?\}\}|\{%[^\n]*?%\}|\{#[^\n]*?#\}|<<MODEL>>/g,
  decoration: (match) => {
    const token = match[0];
    if (token === "<<MODEL>>") {
      return Decoration.mark({
        class: "cm-model-marker"
      });
    }
    if (token.startsWith("{#")) {
      return Decoration.mark({
        class: "cm-jinja-token cm-jinja-comment"
      });
    }
    if (token.startsWith("{%")) {
      return Decoration.mark({
        class: "cm-jinja-token cm-jinja-block"
      });
    }
    return Decoration.mark({
      class: "cm-jinja-token cm-jinja-variable"
    });
  }
});

const jinjaTokenHighlighting = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;

    constructor(view: EditorView) {
      this.decorations = jinjaDecorator.createDeco(view);
    }

    update(update: ViewUpdate) {
      this.decorations = jinjaDecorator.updateDeco(update, this.decorations);
    }
  },
  {
    decorations: (plugin) => plugin.decorations
  }
);

function languageExtensions(language: CodeLanguage): Extension[] {
  if (language === "python") {
    return [python()];
  }
  if (language === "json") {
    return [json()];
  }
  if (language === "text") {
    return [];
  }

  return [markdown({ addKeymap: false }), jinjaTokenHighlighting];
}

function readOnlyExtensions(language: CodeLanguage): Extension[] {
  return [
    basicSetup,
    ...languageExtensions(language),
    EditorView.lineWrapping,
    EditorView.editable.of(false),
    EditorState.readOnly.of(true)
  ];
}

function renderFallback(props: {
  label: string;
  language: CodeLanguage;
  value: string;
  original?: string;
}) {
  const { label, language, value, original } = props;

  return React.createElement(
    "section",
    {
      "aria-label": label,
      className: "code-viewer code-viewer-fallback",
      "data-language": language
    },
    React.createElement("div", { className: "code-viewer-label" }, label),
    original === undefined
      ? React.createElement(
          "pre",
          { className: "code-viewer-fallback-content" },
          React.createElement("code", null, value)
        )
      : React.createElement(
          "div",
          { className: "code-viewer-fallback-diff" },
          React.createElement(
            "pre",
            { className: "code-viewer-fallback-content" },
            React.createElement("code", null, original)
          ),
          React.createElement(
            "pre",
            { className: "code-viewer-fallback-content" },
            React.createElement("code", null, value)
          )
        )
  );
}

export function CodeViewer(props: CodeViewerProps) {
  const { label, language, value } = props;
  const editorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!editorRef.current) {
      return undefined;
    }

    const view = new EditorView({
      parent: editorRef.current,
      state: EditorState.create({
        doc: value,
        extensions: readOnlyExtensions(language)
      })
    });

    return () => {
      view.destroy();
    };
  }, [language, value]);

  if (!canUseDOM()) {
    return renderFallback({ label, language, value });
  }

  return React.createElement(
    "section",
    {
      "aria-label": label,
      className: "code-viewer",
      "data-language": language
    },
    React.createElement("div", { className: "code-viewer-label" }, label),
    React.createElement("div", {
      className: "code-viewer-editor",
      ref: editorRef
    })
  );
}

export function DiffViewer(props: DiffViewerProps) {
  const { label, language, original, value } = props;
  const editorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!editorRef.current) {
      return undefined;
    }

    const view = new EditorView({
      parent: editorRef.current,
      state: EditorState.create({
        doc: value,
        extensions: [
          ...readOnlyExtensions(language),
          unifiedMergeView({
            allowInlineDiffs: true,
            mergeControls: false,
            original
          })
        ]
      })
    });

    return () => {
      view.destroy();
    };
  }, [language, original, value]);

  if (!canUseDOM()) {
    return renderFallback({ label, language, original, value });
  }

  return React.createElement(
    "section",
    {
      "aria-label": label,
      className: "code-viewer code-viewer-diff",
      "data-language": language
    },
    React.createElement("div", { className: "code-viewer-label" }, label),
    React.createElement("div", {
      className: "code-viewer-editor",
      ref: editorRef
    })
  );
}
