# Pexels

Guide the user to [Pexels API](https://www.pexels.com/api/) and the account's API key page. Save it using hidden interactive `editor.py pexels-key`; alternatively use `PEXELS_API_KEY` from the user's secret manager. Never print the key. The local credentials file has mode 0600 where supported; on Windows use an OS secret manager if stronger protection is needed. Exclude runtime config from all project bundles and source control.

Search returns candidates with ID, original page, creator, preview, downloadable media URL and dimensions. Save the chosen candidate JSON. Show the proposed media before asking for inclusion authorization. Record the user's actual quote or an existing grant (project or broader scope) in decisions, with source and date. Never fabricate authorization to satisfy a CLI flag. Download is idempotent per candidate ID and media URL; existing files are checked against recorded hashes. Credentials are only sent to `api.pexels.com`; downloads use HTTPS Pexels media domains without the API key.

Current API references: [Pexels API documentation](https://www.pexels.com/api/documentation/). Check current terms, limits, and attribution guidance for the user's intended delivery. A recorded grant can cover future assets; interpret its scope literally and allow revocation. Downloading a candidate does not automatically put it into the timeline.
