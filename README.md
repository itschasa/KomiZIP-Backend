# KomiZIP-Backend
A python server for handling CDN and API calls for api.komi.zip and cdn.komi.zip using the Flask framework.

### All repositories:
[Reader](https://github.com/itschasa/KomiZIP-Reader) | [Home](https://github.com/itschasa/KomiZIP-Home) | [Backend](https://github.com/itschasa/KomiZIP-Backend)

## CDN
The CDN isn't meant to be fast at serving files, as it expects Cloudflare to do the heavy lifting.
Cloudflare Tiered Cache should be enabled to minimize the traffic to the Origin Server.
Caching Headers are provided by the server.

### No Caching on 404?
This is to ensure updates to users when new chapters are releases are real-time, and not delayed by cache updates.
Serving a 404 message shouldn't be taxful on the server.

### X-Page-Count?
Clients can request the first image (01) of a chapter to see if it exists, instead of asking the (dynamic) API.

If it does exist:
- No additional requests will have to be done to get the total page count.
- Zero communications to Origin Server are needed, as Cloudflare caches both the image data and headers.

If it doesn't:
- Origin Server will be hit, but this is unlikely to cause huge amounts of resource usage (it's a simple 404).

### CDN Folder
As the CDN isn't technically it's own server, the folder is used to store all the images needed. They are then served to Cloudflare and clients.

### "chapters.json"
Used to retain chapter data on server reboot, crash, etc.
It is loaded into memory on bootup, and is saved to whenever it is changed.

### Scraping
`scrape.py` acts as a library/API for Viz Manga. `web.py:scrape_thread` uses this library to fetch info every 15 seconds.

### Deobfuscation
Images from Viz Manga are obfuscated. [minormending's viz-image-deobfuscate](https://github.com/minormending/viz-image-deobfuscate) library is used to deobfuscate these images.

### i.komi.zip Redirect
Cloudflare Page Rules is used for this:

![image](https://github.com/itschasa/KomiZIP-Backend/assets/79016507/33aa5d0a-8fe0-42ac-a1cd-fa95be4b1e80)


## API
The API is a dynamic endpoint that needs to use a little resources as possible, to prevent server overload.
It serves "semi" dynamic content. Content is updated every 15 seconds. The API fetches that content from RAM, instead of making the content on each request.
This keeps the content dynamic, whilst also ensuring DoS is kept to a low risk.

### Endpoints
**/v1/chapters**
- Returns all chapter data:
    - Titles
    - Viz Links
    - Page Count
    - Reader Links
