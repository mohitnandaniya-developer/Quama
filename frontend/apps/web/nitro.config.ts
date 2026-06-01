import { defineNitroConfig } from "nitro/config"

export default defineNitroConfig({
  preset: "vercel",
  output: {
    dir: ".output",
    publicDir: ".output/public",
    serverDir: ".output/server",
  },
  typescript: {
    strict: false,
    tsConfig: {
      compilerOptions: {
        target: "esnext",
      },
    },
  },
})
