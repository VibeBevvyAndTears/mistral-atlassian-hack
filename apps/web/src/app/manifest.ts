import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Conve",
    short_name: "Conve",
    description:
      "Cross-team communication with topic graphs, conflict detection, and audience adaptation.",
    start_url: "/",
    display: "standalone",
    background_color: "#0E0F12",
    theme_color: "#0E0F12",
    icons: [
      {
        src: "/favicon.ico",
        sizes: "any",
        type: "image/x-icon",
      },
      {
        src: "/icon-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
      },
    ],
  };
}
