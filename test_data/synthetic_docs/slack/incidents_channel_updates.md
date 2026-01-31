# Slack Export: #incidents Channel
**Date Range:** October 18 - November 6, 2024

---

**Oct 18, 9:15 PM (FRIDAY)**
**@alex.thompson:** 🚨 INCIDENT: Auth Service latency spike detected. Investigating.

**Oct 18, 9:20 PM**
**@alex.thompson:** Root cause identified - CloudShift migration tool left a debug mode enabled. Connection to vendor support...

**Oct 18, 9:45 PM**
**@alex.thompson:** CloudShift support contacted. No response yet (weekend hours).

**Oct 19, 8:00 AM (SATURDAY)**
**@alex.thompson:** Still no response from CloudShift. Implemented workaround manually. Service restored.

**Oct 19, 10:00 AM**
**@brian.taylor:** Just saw this. I can help debug if needed.

**Oct 19, 10:15 AM**
**@alex.thompson:** Thanks Brian. It's stable now. But this CloudShift support response time is unacceptable.

**Oct 21, 9:00 AM (MONDAY)**
**@alex.thompson:** Postmortem scheduled for Tuesday 2pm. CloudShift finally responded this morning - 60+ hours later.

---

**Oct 23, 2:30 PM**
**@george.brown:** ⚠️ WARNING: Notification Service queue depth increasing. Not critical yet but trending up.

**Oct 23, 2:45 PM**
**@alex.thompson:** Monitoring. This is the pattern we've seen before Black Friday traffic.

**Oct 23, 3:00 PM**
**@alex.thompson:** Implementing temporary capacity increase. Should hold until circuit breaker deploys.

**Oct 23, 4:00 PM**
**@george.brown:** Queue depth stabilized. Good catch everyone.

---

**Oct 25, 11:00 AM**
**@ryan.adams:** 🟡 INFO: Auth Service staging environment down for maintenance. Migration testing in progress.

**Oct 25, 11:30 AM**
**@sarah.chen:** Staging is back up. Load testing shows 3x capacity improvement. Good work Ryan.

---

**Nov 1, 10:00 AM**
**@alex.thompson:** 🎉 RESOLVED: Circuit breaker deployed to production. Notification Service now has backpressure handling.

**Nov 1, 10:05 AM**
**@george.brown:** Dashboards updated to track circuit breaker metrics. All green.

**Nov 1, 10:10 AM**
**@mia.white:** Excellent work team. This closes out the reliability initiative from Q3. 🙏

---

**Nov 2, 3:00 PM**
**@amy.chen:** 🟡 INFO: Seeing some connection timeouts to API Gateway staging. Investigating.

**Nov 2, 3:15 PM**
**@brian.taylor:** Found it - SSL certificate was about to expire on staging. Renewed.

**Nov 2, 3:20 PM**
**@amy.chen:** Confirmed - staging back to normal. Should we add certificate expiry monitoring?

**Nov 2, 3:25 PM**
**@george.brown:** Great idea. I'll add it to the observability platform requirements.

---

**Nov 6, 8:30 AM**
**@alex.thompson:** 🚨 INCIDENT: API Gateway production - elevated error rates (0.5%). Investigating.

**Nov 6, 8:35 AM**
**@alex.thompson:** Root cause: Upstream dependency (third-party fraud check API) is slow. Not our issue but affecting us.

**Nov 6, 8:40 AM**
**@lisa.park:** I'll contact the fraud check vendor. This is the second time this month.

**Nov 6, 8:50 AM**
**@alex.thompson:** Enabling graceful degradation. Bypassing slow fraud check for low-risk transactions.

**Nov 6, 9:00 AM**
**@alex.thompson:** Error rate back to normal (0.02%). Graceful degradation working as designed.

**Nov 6, 9:15 AM**
**@lisa.park:** Vendor acknowledged the issue. They're working on a fix. ETA 2 hours.

**Nov 6, 11:30 AM**
**@lisa.park:** Vendor issue resolved. Disabling graceful degradation, full fraud checks restored.

**Nov 6, 11:35 AM**
**@mia.white:** Good incident response. The graceful degradation saved us from a customer-impacting outage. 👏

---

**Nov 6, 2:00 PM**
**@alex.thompson:** Postmortem scheduled for Nov 8. Key question: Should we have our own fraud check fallback instead of relying on vendor?

**Nov 6, 2:05 PM**
**@lisa.park:** I've been thinking the same thing. Let's discuss in the postmortem.
