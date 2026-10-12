import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 컨테이너 밖(브라우저)에서 접근할 수 있도록 0.0.0.0 으로 연다
export default defineConfig({
  plugins: [react()],
  server: { host: "0.0.0.0", port: 3000 },
});
