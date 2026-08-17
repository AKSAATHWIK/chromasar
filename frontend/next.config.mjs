/** Proxy /api to the FastAPI backend so the browser sees one origin.
 *  Keeps the Python service unchanged and avoids CORS entirely.
 *
 *  The port is read from the environment because this is the ONLY route from the
 *  browser to the model - lib/api.ts issues purely relative fetches. Move the backend
 *  off 8000 to dodge a port clash and forget to change it here, and every request in
 *  the UI 404s at the proxy with the backend running perfectly. One variable now
 *  drives both sides: set CHROMASAR_PORT for the Python process and put the same
 *  value in frontend/.env.local, which Next reads automatically. */
const port = process.env.CHROMASAR_PORT ?? "8000";

const nextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `http://127.0.0.1:${port}/api/:path*` }];
  },
};
export default nextConfig;
