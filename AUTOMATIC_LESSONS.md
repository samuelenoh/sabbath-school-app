# Automatic daily and weekly study

The Lesson study screen automatically selects the current **English Standard Adult** guide and daily reading, using published dates and Ghana/UTC time. Church staff do not need to add each week's published lesson. Existing class-specific notes and attendance study-completion records stay independent.

The General Conference identifies the Adventech-powered service as its official Sabbath School and Personal Ministries app: https://sspmadventist.org/sspmapp . Its adult reader is https://absg.sspmadventist.org/this-week .

## Verified source

The app reads public bibliographic metadata from `https://sabbath-school.adventech.io/api/v3/en/ss/index.json`, then the current publication's `sections/index.json`. It selects a uniquely dated publication and weekly document, rather than assuming quarter boundaries or week numbers. Daily links use the offset from that document's published Saturday start date.

On 14 October 2026, the live source returned **The Gift of Prophecy**, **Old Testament Prophets**, 10–16 October, week 3. The daily reader URL resolved to **Women Prophets**: https://absg.sspmadventist.org/en/2026-04/03/05 .

The provider's current implementation and paths were inspected in https://github.com/Adventech/sabbath-school-web/blob/stage/src/views/ABSG/ABSGThisWeek.vue and https://github.com/Adventech/sabbath-school-web/blob/stage/src/router/index.js . The old API documentation link redirects to a generic documentation page, so the verified current v3 feed is used. Upstream schema/availability can change; this app validates its narrow metadata contract and provides a publisher link if it cannot select a unique valid current lesson.

## Operation

- The signed-in app fetches metadata on opening Lesson study. A page left open checks for a new UTC date each minute; it postpones changes while a dialog is open.
- The backend caches only selected metadata for 15 minutes, invalidates it on a new date, and backs off for five minutes after an upstream failure. Network requests are bounded, use fixed publisher paths and transmit no member information or credentials.
- No lesson records are inserted or overwritten, no messages are sent, and no scheduled job, paid service or extra dependency is needed.
- Full readings open in the publisher's website. Other ages, editions and languages are linked to the official reader catalogue; automatic selection currently covers English Standard Adult only.
- Provider outages or missing future publications show a current-study fallback instead of displaying stale material as today's lesson. An internet connection is needed for the publisher's full study. There is no full-text offline copy.

## Content reuse

The provider repository distinguishes its open-source software license from the General Conference's lesson-content copyright: https://github.com/Adventech/sabbath-school-lessons#copyright . This integration displays titles, date ranges and reading links only. It does not copy, modify, translate or republish lesson bodies. Hosting full lesson text in this app requires the content owner's authorization and an approved integration arrangement.

Tests use synthetic metadata, including new-year and Saturday/Friday boundaries, ambiguous/missing publications, invalid paths/dates, cache rollover, upstream failure, metadata-only storage, authentication and browser fallback behavior. They do not depend on the external publisher remaining online.
