# Northstar Public Ad Capture extension

This unpacked Manifest V3 extension saves evidence from the active public ad page
to the local Northstar ad library. It has no background crawler and no access to
private accounts. Opening the popup grants temporary `activeTab` access only to the
current page.

## Install in Chrome or Edge

1. Start Northstar with `start-northstar.ps1`.
2. Open `chrome://extensions` in Chrome or `edge://extensions` in Edge.
3. Enable **Developer mode**.
4. Choose **Load unpacked**.
5. Select this repository's `extension` directory.
6. Pin **Northstar Public Ad Capture** to the browser toolbar.

## Capture an ad

1. Open a public Meta Ad Library, TikTok Creative Center, Google Ads Transparency,
   or other public ad page.
2. Select the visible ad copy when possible.
3. Open the Northstar extension.
4. Review and correct the source, platform, advertiser, copy, media, CTA, and
   landing-page fields. Expand **Visible analytics** to record only values displayed
   by the source, such as `34K` likes or `Top 18%` CTR.
5. Choose **Save to Northstar**.

The extension uses versioned adapters for Meta Ad Library, TikTok Creative Center,
and Google Ads Transparency Center, with the selected-text adapter as fallback. A
preview shows adapter confidence, captured fields, and partial-capture warnings before
save. Public ad-library DOM structures change, so every inferred field remains editable
and must be reviewed.

Capture provenance is saved with the ad and appears in Ad Autopsy. Re-capturing the
same normalized public source URL updates that Northstar record and adds new metric
observations without duplicating its landing relationship.

Analytics remain typed as reported values or percentiles. The extension does not turn
rounded text into exact counts and does not infer impressions, spend, or ROAS.

## Permissions

- `activeTab` and `scripting`: inspect only the current page after you invoke the extension.
- `storage`: retain the local Northstar login token.
- loopback host permissions: communicate only with Northstar at port 8000.

The extension does not request persistent access to all websites.

## Offline adapter verification

The fixture snapshots contain no live credentials or network dependencies:

```powershell
cd extension
node --test tests\adapters.test.js
```
