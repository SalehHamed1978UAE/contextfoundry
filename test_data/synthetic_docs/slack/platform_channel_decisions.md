# Slack Export: #platform-team Channel
**Date Range:** October 20-28, 2024

---

**Oct 20, 9:15 AM**
**@alex.rivera:** Team - quick decision needed. CloudShift training scheduled for tomorrow. Should we proceed given the vendor concerns, or postpone?

**Oct 20, 9:18 AM**
**@brian.taylor:** I'd postpone. No point learning a tool we might not use.

**Oct 20, 9:22 AM**
**@sarah.chen:** Agree with Brian. Let's wait for the vendor evaluation outcome.

**Oct 20, 9:25 AM**
**@alex.rivera:** OK, postponing CloudShift training. Will reschedule once we have a final vendor decision.

---

**Oct 22, 2:30 PM**
**@amy.chen:** Anyone else seeing high latency on the staging Auth Service? Getting 2-3 second response times.

**Oct 22, 2:32 PM**
**@ryan.adams:** I just pushed a change to connection pool settings. Might be related. Let me check.

**Oct 22, 2:40 PM**
**@ryan.adams:** Found it. Pool size was set too low for the new cloud environment. Pushing a fix now.

**Oct 22, 2:45 PM**
**@amy.chen:** Confirmed - latency back to normal. Thanks Ryan!

**Oct 22, 2:47 PM**
**@sarah.chen:** @ryan.adams can you add that to the migration runbook? Others might hit the same issue.

**Oct 22, 2:50 PM**
**@ryan.adams:** Good call. Added: "Cloud environment requires minimum 50 connections per pool (vs 20 on-prem)"

---

**Oct 24, 11:00 AM**
**@george.brown:** Heads up - George here. DataDog is showing some weird spikes in the Notification Service. Not an incident yet, but keeping an eye on it.

**Oct 24, 11:15 AM**
**@alex.thompson:** I see them too. Looks like the queue is backing up during peak hours. This is exactly what the circuit breaker will fix.

**Oct 24, 11:20 AM**
**@kevin.lee:** ETA on the circuit breaker deployment?

**Oct 24, 11:22 AM**
**@alex.thompson:** November 1st, if nothing else comes up.

**Oct 24, 11:25 AM**
**@kevin.lee:** Let's make sure nothing else comes up. This is affecting customers.

---

**Oct 25, 3:00 PM**
**@alex.rivera:** Just got off a call with MigrateX. Very impressive demo. Their PostgreSQL support is miles ahead of CloudShift.

**Oct 25, 3:05 PM**
**@lisa.park:** What about the price difference?

**Oct 25, 3:08 PM**
**@alex.rivera:** 40% more expensive. But the support SLA is 1 hour vs 24 hours. Given our Friday night incident, that matters.

**Oct 25, 3:12 PM**
**@brian.taylor:** I'm sold on the rollback capability alone. 15 minutes vs 45 minutes is huge for production cutover.

**Oct 25, 3:15 PM**
**@sarah.chen:** Who makes the final call on this?

**Oct 25, 3:18 PM**
**@alex.rivera:** Mia. I'll present both options at Friday's meeting.

---

**Oct 28, 10:30 AM**
**@priya.sharma:** Hi everyone! Just joined the Slack. Looking forward to starting next week!

**Oct 28, 10:32 AM**
**@amy.chen:** Welcome Priya! Can't wait to work with you. I'll be your onboarding buddy.

**Oct 28, 10:35 AM**
**@kevin.lee:** Welcome to the team! You'll fit right in.

**Oct 28, 10:38 AM**
**@brian.taylor:** 👋 Welcome! Let me know if you have questions about the infrastructure setup.

**Oct 28, 10:40 AM**
**@sarah.chen:** Excited to have you! We need the Terraform expertise.

**Oct 28, 10:45 AM**
**@alex.rivera:** Welcome Priya! Looking forward to having you shadow the Auth Service migration. Great way to learn our systems.

---

**Oct 28, 4:00 PM**
**@alex.rivera:** FYI - just confirmed we're switching to MigrateX. Mia approved it in today's meeting. CloudShift training is officially cancelled.

**Oct 28, 4:02 PM**
**@brian.taylor:** 🎉 Best decision we've made in a while.

**Oct 28, 4:05 PM**
**@sarah.chen:** Agreed. The PostgreSQL support alone makes it worth it.

**Oct 28, 4:08 PM**
**@ryan.adams:** What happens to the CloudShift config work I did?

**Oct 28, 4:12 PM**
**@alex.rivera:** Archive it but don't delete. Some concepts might translate. We'll start MigrateX onboarding next week.
