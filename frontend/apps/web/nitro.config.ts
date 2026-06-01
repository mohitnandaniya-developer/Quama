import { defineNitroConfig } from "nitro/config"

export default defineNitroConfig({
  presets: ["vercel"],
  output: {
    dir: ".output",
    public: ".output/public",
    server: ".output/server",
  },
  typescript: {
    strict: false,
    esbuild: {
      options: {
        target: "esnext",
      },
    },
  },
})
