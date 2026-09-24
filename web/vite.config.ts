import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { missingStudyDetails } from "./src/studyConfig";

function requireStudyDetails() {
  return {
    name: "require-study-details",
    apply: "build" as const,
    buildStart() {
      const missing = missingStudyDetails();
      if (missing.length) {
        const lines = [
          "",
          "The privacy notice is incomplete.",
          "",
          "These values are blank in web/src/studyConfig.ts and only the study",
          "team can supply them:",
          "",
          ...missing.map((key) => `  - ${key}`),
          "",
          "See the repository README. A notice that ships with these blank makes",
          "promises to participants about their medical record with the",
          "specifics missing.",
          "",
        ];
        throw new Error(lines.join("\n"));
      }
    },
  };
}

function refuseUnsafeBundle() {
  return {
    name: "refuse-unsafe-bundle",
    apply: "build" as const,
    writeBundle(_options: unknown, bundle: Record<string, unknown>) {
      const names = Object.keys(bundle);

      const maps = names.filter((n) => n.endsWith(".map"));
      if (maps.length) {
        throw new Error(
          "This build emitted source maps, which republish the application " +
            "source to anyone who opens devtools on a page handling PHI. " +
            "Set build.sourcemap to false."
        );
      }

      const local = /https?:\/\/(localhost|127\.0\.0\.1)/;
      for (const name of names) {
        const chunk = bundle[name] as { code?: string; source?: string };
        const text = chunk.code ?? String(chunk.source ?? "");
        if (local.test(text)) {
          throw new Error(
            `${name} points at a local development server. This bundle was ` +
              "built with the wrong .env and would fail for every participant."
          );
        }
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), requireStudyDetails(), refuseUnsafeBundle()],
  build: {
    sourcemap: false,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
  },
});
