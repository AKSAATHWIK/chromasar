/** Proxy /api to the FastAPI backend so the browser sees one origin.
 *  Keeps the Python service unchanged and avoids CORS entirely. */
const nextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" }];
  },
};
export default nextConfig;
