import { defineConfig } from "eslint/config";

export default defineConfig([
  {
    files: ["datamind/console/static/assets/**/*.js", "frontend-tests/**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        document: "readonly",
        window: "readonly",
        navigator: "readonly",
        EventSource: "readonly",
        FormData: "readonly",
        File: "readonly",
        Blob: "readonly",
        Element: "readonly",
        Event: "readonly",
        Node: "readonly",
        URL: "readonly",
        fetch: "readonly",
        setTimeout: "readonly",
        HTMLElement: "readonly",
        HTMLInputElement: "readonly",
        HTMLButtonElement: "readonly",
        HTMLFormElement: "readonly",
        HTMLDialogElement: "readonly",
        HTMLSelectElement: "readonly",
        HTMLTextAreaElement: "readonly",
        URLSearchParams: "readonly",
        requestAnimationFrame: "readonly",
        cancelAnimationFrame: "readonly",
      },
    },
    rules: {
      "no-undef": "error",
      "no-unreachable": "error",
      "no-unused-vars": ["warn", {
        "argsIgnorePattern": "^_",
        "caughtErrorsIgnorePattern": "^_",
        "varsIgnorePattern": "^_"
      }],
    },
  },
]);
