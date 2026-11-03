import js from "@eslint/js";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "node_modules", "src/api/schema.ts", "playwright-report", "test-results"] },
  js.configs.recommended,
  ...tseslint.configs.strict,
  jsxA11y.flatConfigs.strict,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: { globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: reactHooks.configs.recommended.rules,
  },
  {
    files: ["scripts/**/*.mjs", "*.config.{js,ts}"],
    languageOptions: { globals: globals.node },
  },
);
