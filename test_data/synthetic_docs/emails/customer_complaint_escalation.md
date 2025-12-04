# Email Thread: Customer Escalation - Notification Delays

---

**From:** Tom Baker <tom.baker@company.com>
**To:** Mia White <mia.white@company.com>
**CC:** Michael Torres <michael.torres@company.com>
**Date:** October 23, 2024, 4:15 PM
**Subject:** URGENT: Enterprise Customer Threatening Churn - Notification Issues

Mia,

I just got off a call with Jennifer Walsh at Enterprise Corp (our 3rd largest customer). She's furious.

Their payment notification emails are delayed by 15-45 minutes, causing significant operational issues on their end. Their finance team depends on real-time payment confirmations.

This is the third time she's complained in the past month. She explicitly said they're evaluating competitors if we can't fix it.

This customer represents $180K ARR. We cannot afford to lose them.

What's the status of the Notification Service reliability work? She needs a timeline she can take to her leadership.

Tom

---

**From:** Mia White <mia.white@company.com>
**To:** Tom Baker <tom.baker@company.com>
**CC:** Michael Torres <michael.torres@company.com>, Alex Rivera <alex.rivera@company.com>
**Date:** October 23, 2024, 4:45 PM
**Subject:** RE: URGENT: Enterprise Customer Threatening Churn - Notification Issues

Tom,

Thank you for escalating this quickly.

The Notification Service has been on our radar. We've had three incidents this month related to it. The circuit breaker implementation is in progress and should address the root cause.

Alex - can you provide a timeline for Tom to share with the customer?

I also want Alex Thompson on this thread - he's been doing the incident triage and has the best visibility into the failure patterns.

Mia

---

**From:** Alex Rivera <alex.rivera@company.com>
**To:** Mia White <mia.white@company.com>
**CC:** Tom Baker <tom.baker@company.com>, Michael Torres <michael.torres@company.com>, Alex Thompson <alex.thompson@company.com>
**Date:** October 23, 2024, 5:30 PM
**Subject:** RE: URGENT: Enterprise Customer Threatening Churn - Notification Issues

Tom,

Here's what I can share with the customer:

**Root Cause:** The Notification Service is getting overwhelmed during peak payment processing times. When the upstream queue backs up, emails are delayed while the service processes the backlog.

**Fix in Progress:** We're implementing a circuit breaker pattern that will:
1. Prevent queue overflow
2. Provide graceful degradation (priority notifications first)
3. Add real-time alerting so we know before customers do

**Timeline:**
- Circuit breaker deployment: November 1 (next Friday)
- Monitoring stabilization: November 8
- Full confidence in fix: November 15

**Interim Mitigation:** Alex Thompson has implemented a temporary workaround that increases queue capacity by 50%. This should reduce delays while we deploy the permanent fix.

Can you share this with Jennifer? I'm also happy to join a call if she wants to hear directly from engineering.

Alex

---

**From:** Tom Baker <tom.baker@company.com>
**To:** Alex Rivera <alex.rivera@company.com>
**CC:** Mia White <mia.white@company.com>, Michael Torres <michael.torres@company.com>
**Date:** October 24, 2024, 10:00 AM
**Subject:** RE: URGENT: Enterprise Customer Threatening Churn - Notification Issues

Alex,

I shared this with Jennifer. She appreciated the transparency and the offer to have engineering on a call.

She had one follow-up question: "What's preventing this from happening again after November 15?"

She wants assurance this is a permanent fix, not a patch.

Can you address that? I think it would go a long way toward rebuilding trust.

Tom

---

**From:** Alex Thompson <alex.thompson@company.com>
**To:** Tom Baker <tom.baker@company.com>
**CC:** Alex Rivera <alex.rivera@company.com>, Mia White <mia.white@company.com>
**Date:** October 24, 2024, 11:30 AM
**Subject:** RE: URGENT: Enterprise Customer Threatening Churn - Notification Issues

Tom,

I can address the "permanent fix" question:

The circuit breaker isn't just a patch - it's an architectural change that fundamentally prevents the failure mode we've been experiencing.

Here's how it works:
1. **Rate Limiting:** The system now limits incoming notifications to a sustainable rate
2. **Priority Queue:** Critical notifications (like payment confirmations) get processed first
3. **Backpressure:** If the system is overloaded, it signals upstream services to slow down rather than crashing
4. **Alerting:** We'll know about capacity issues 30 minutes before customers experience delays

Additionally, we're adding this to our SRE runbook with automated monitoring. If the circuit breaker ever trips, I get paged immediately.

This is the same pattern used by Netflix and other high-scale services. It's been proven at much larger scale than ours.

Happy to explain further on a call if helpful.

Alex Thompson
SRE Team

---

**From:** Tom Baker <tom.baker@company.com>
**To:** All Recipients
**Date:** October 28, 2024, 2:00 PM
**Subject:** RE: URGENT: Enterprise Customer Threatening Churn - UPDATE

Team,

Good news - I had a follow-up call with Jennifer at Enterprise Corp.

She was impressed by Alex Thompson's detailed explanation and appreciates the engineering team's responsiveness. She's agreed to stay with us through the fix deployment and evaluate in mid-November.

Her exact words: "This is the first time I've felt like your engineering team actually understands our pain. Please thank Alex Thompson for me."

Still need to deliver on the November 15 timeline, but we've bought ourselves time.

Thank you all for the rapid response.

Tom
