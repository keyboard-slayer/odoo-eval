// @odoo-module ignore

/* eslint-disable no-restricted-globals */
const cacheName = "odoo-sw-cache";
const staticCacheName = "odoo-static-cache";
const dynamicCacheName = "odoo-dynamic-cache";
const cachedRequests = ["/odoo/offline"];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(cacheName).then((cache) => cache.addAll(cachedRequests)));
});

const navigateOrDisplayOfflinePage = async (request) => {
    try {
        return await fetch(request);
    } catch (requestError) {
        if (
            request.method === "GET" &&
            ["Failed to fetch", "Load failed"].includes(requestError.message)
        ) {
            if (cachedRequests.includes("/odoo/offline")) {
                const cache = await caches.open(cacheName);
                const cachedResponse = await cache.match("/odoo/offline");
                if (cachedResponse) {
                    return cachedResponse;
                }
            }
        }
        throw requestError;
    }
};

const serveShareTarget = (event) => {
    // Redirect so the user can refresh the page without resending data.
    event.respondWith(Response.redirect("/odoo?share_target=trigger"));
    event.waitUntil(
        (async () => {
            // The page sends this message to tell the service worker it's ready to receive the file.
            await waitingMessage("odoo_share_target");
            const client = await self.clients.get(event.resultingClientId || event.clientId);
            const data = await event.request.formData();
            client.postMessage({
                shared_files: data.getAll("externalMedia") || [],
                action: "odoo_share_target_ack",
            });
        })()
    );
};

self.addEventListener("fetch", (event) => {
    if (
        event.request.method === "POST" &&
        new URL(event.request.url).searchParams.has("share_target")
    ) {
        return serveShareTarget(event);
    }
    if (
        event.request.method === "GET"
    ) {
        if (
            (event.request.mode === "navigate" && event.request.destination === "document") ||
            // request.mode = navigate isn't supported in all browsers => check for http header accept:text/html
            event.request.headers.get("accept").includes("text/html")
        ) {
            event.respondWith(navigateOrDisplayOfflinePage(event.request));
        } else {
            event.respondWith(handleAssetRequest(event));
        }
    } else {
        event.respondWith(navigateOrDisplayOfflinePage(event.request));
    }
});


// Handle page request with cache-first strategy
const handlePageRequest = async (event) => {
    const { request } = event;
    try {
        const cache = await caches.open(dynamicCacheName);
        const cachedResponse = await cache.match(request);

        if (cachedResponse) {
            // Return cached response if found
            return cachedResponse;
        }

        // Fetch from network
        const networkResponse = await fetch(request);
        // Cache the fetched response if it's successful
        if (networkResponse.ok) {
            if(request.method === "GET"){
                cache.put(request, networkResponse.clone());
            }
        }
        return networkResponse;
    } catch (error) {
        // Serve offline page if network request fails
        return caches.match("/odoo/offline");
    }
};

// Handle asset requests
const handleAssetRequest = async (event) => {
    const { request } = event;

    // Check if request URL is valid and supported
    const requestURL = new URL(request.url);
    if (requestURL.protocol === 'http:' || requestURL.protocol === 'https:') {
        try {
            // Try to serve from cache
            const cachedResponse = await caches.match(request);
            if (cachedResponse) {
                return cachedResponse; // Serve from cache
            }

            // Fetch from network and cache dynamically
            const networkResponse = await fetch(request);
            if (networkResponse.ok) {
                const cache = await caches.open(dynamicCacheName);
                if(request.method==="GET"){
                    cache.put(request, networkResponse.clone());
                }
            }
            return networkResponse;
        } catch (error) {
            // Serve offline page if network request fails and no cache available
            return caches.match("/odoo/offline");
        }
    } else {
        // For unsupported request schemes, don't attempt to cache
        return await fetch(request);
    }
};


/**
 *
 * @type {Map<String, Function[]>}
 */
const nextMessageMap = new Map();
/**
 *
 * @param message : string
 * @return {Promise}
 */
const waitingMessage = async (message) => {
    return new Promise((resolve) => {
        if (!nextMessageMap.has(message)) {
            nextMessageMap.set(message, []);
        }
        nextMessageMap.get(message).push(resolve);
    });
};

self.addEventListener("message", (event) => {
    const messageNotifiers = nextMessageMap.get(event.data);
    if (messageNotifiers) {
        for (const messageNotified of messageNotifiers) {
            messageNotified();
        }
        nextMessageMap.delete(event.data);
    }
});