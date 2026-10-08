// Minimal service worker: needed so Chrome treats the site as an installable app.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {}); // always go to the network
