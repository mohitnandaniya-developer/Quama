import { defineNitroConfig } from "nitro/config"

export default defineNitroConfig({
  preset: "vercel",
  typescript: {
    strict: false,
    tsConfig: {
      compilerOptions: {
        target: "esnext",
      },
    },
  },
})
