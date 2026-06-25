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

export type CodeEditorProps = CodeViewerProps & {
  disabled?: boolean;
  onChange: (value: string) => void;
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

function editorExtensions(props: {
  editable: boolean;
  language: CodeLanguage;
  onChange?: (value: string) => void;
}): Extension[] {
  const extensions: Extension[] = [
    basicSetup,
    ...languageExtensions(props.language),
    EditorView.lineWrapping,
    EditorView.editable.of(props.editable),
    EditorState.readOnly.of(!props.editable)
  ];
  if (props.onChange !== undefined) {
    extensions.push(
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          props.onChange?.(update.state.doc.toString());
        }
      })
    );
  }
  return extensions;
}

function readOnlyExtensions(language: CodeLanguage): Extension[] {
  return editorExtensions({ editable: false, language });
}

function renderFallback(props: {
  editable?: boolean;
  label: string;
  language: CodeLanguage;
  value: string;
  original?: string;
}) {
  const { editable = false, label, language, value, original } = props;

  return React.createElement(
    "section",
    {
      "aria-label": label,
      className: editable
        ? "code-viewer code-editor code-viewer-fallback"
        : "code-viewer code-viewer-fallback",
      "data-language": language
    },
    React.createElement("div", { className: "code-viewer-label" }, label),
    editable
      ? React.createElement("textarea", {
          className: "code-viewer-fallback-content code-editor-fallback-input",
          defaultValue: value
        })
      : original === undefined
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

export function CodeEditor(props: CodeEditorProps) {
  const { disabled = false, label, language, onChange, value } = props;
  const editorRef = useRef<HTMLDivElement | null>(null);
  const onChangeRef = useRef(onChange);
  const viewRef = useRef<EditorView | null>(null);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    if (!editorRef.current) {
      return undefined;
    }

    const view = new EditorView({
      parent: editorRef.current,
      state: EditorState.create({
        doc: value,
        extensions: editorExtensions({
          editable: !disabled,
          language,
          onChange: (nextValue) => onChangeRef.current(nextValue)
        })
      })
    });
    viewRef.current = view;

    return () => {
      viewRef.current = null;
      view.destroy();
    };
  }, [disabled, language]);

  useEffect(() => {
    const view = viewRef.current;
    if (view === null) {
      return;
    }
    const currentValue = view.state.doc.toString();
    if (currentValue === value) {
      return;
    }
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: value }
    });
  }, [value]);

  if (!canUseDOM()) {
    return renderFallback({ editable: true, label, language, value });
  }

  return React.createElement(
    "section",
    {
      "aria-label": label,
      className: "code-viewer code-editor",
      "data-language": language
    },
    React.createElement("div", { className: "code-viewer-label" }, label),
    React.createElement("div", {
      className: "code-viewer-editor",
      ref: editorRef
    })
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
