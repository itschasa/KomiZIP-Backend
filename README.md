# KomiZIP-Backend
A python server for handling CDN and API calls for api.komi.zip, cdn.komi.zip and i.komi.zip using the Flask library.

### All repositories:
[Reader](https://github.com/itschasa/KomiZIP-Reader) | [Home](https://github.com/itschasa/KomiZIP-Home) | [Backend](https://github.com/itschasa/KomiZIP-Backend)

## CDN
The CDN isn't meant to be fast at serving files, as it expects Cloudflare to do the heavy lifting.
Cloudflare Tiered Cache should be enabled to minimize the traffic to the Origin Server.
Caching Headers are provided by the server.

### No Caching on 404
This is to ensure updates to users when new chapters are releases are real-time, and not delayed by cache updates.
Serving a 404 message shouldn't be taxful on the server.

### CDN non-image serving ( /cdn/{ chapter } )
The CDN is also used to serve semi-realtime data to users, in the form of headers (HEAD request).
This puts less stress on the origin server, whilst keeping metadata relatively up to date.

All requests to this endpoint will have the header `X-Metadata`, containing the data of that chapter from the API.
This is used to prevent the client having to contact the (non-cached) API for information.

### CDN Folder
As the CDN isn't technically it's own server, the folder is used to store all the images needed. They are then served to Cloudflare and clients.

### "chapters.json"
Used to retain chapter data on server reboot, crash, etc.
It is loaded into memory on bootup, and is saved to whenever it is changed.

### Scraping
`scrape.py` acts as a library/API for Viz Manga. `web.py:scrape_thread` uses this library to fetch info every 15 seconds.

### Deobfuscation
Images from Viz Manga are obfuscated. [minormending's viz-image-deobfuscate](https://github.com/minormending/viz-image-deobfuscate) library is used to deobfuscate these images. Thank you <3

### i.komi.zip Redirect
This zone/subdomain can be used for easily embeding images (on Discord and other social platforms).
Using this seperate zone prevents the need for `0` padding on the page number.

`https://i.komi.zip/{ chapter }/{ page }`

Additionally, everything on this zone is cached for 24 hours.


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
- and the new release time.
