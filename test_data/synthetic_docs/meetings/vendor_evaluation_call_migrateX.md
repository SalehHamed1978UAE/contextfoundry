# Vendor Evaluation: MigrateX Discovery Call
**Date:** October 25, 2024
**Attendees (Internal):** Alex Rivera, Brian Taylor, Lisa Park
**Attendees (Vendor):** Jennifer Walsh (MigrateX Account Executive), Mark Stevens (Solutions Architect)

---

## Context
Following concerns about CloudShift responsiveness, Alex Rivera arranged this discovery call to evaluate MigrateX as an alternative vendor for cloud migration tooling.

---

## Presentation Summary

**Jennifer Walsh:** MigrateX specializes in enterprise cloud migrations. We've helped over 200 companies migrate critical workloads.

**Mark Stevens:** Our platform handles three main scenarios:
1. Database migration with zero downtime
2. Application containerization and orchestration
3. Hybrid cloud connectivity

---

## Technical Discussion

**Alex Rivera:** Our biggest pain point is Payment Service. It has legacy integrations with Fraud Detection Service that need careful handling.

**Mark Stevens:** We see this often. Our approach is incremental - we can migrate components one at a time while maintaining connectivity to legacy systems.

**Brian Taylor:** What about rollback capabilities? If something goes wrong, how quickly can we revert?

**Mark Stevens:** Every migration includes automated rollback checkpoints. Average rollback time is under 15 minutes for most workloads.

**Lisa Park:** We had issues with CloudShift's database replication. Their tool couldn't handle our PostgreSQL extensions.

**Mark Stevens:** We have native support for most PostgreSQL extensions including pgvector. Let me share our compatibility matrix after the call.

---

## Pricing Discussion

**Jennifer Walsh:** Our enterprise tier is $85,000 annually, which includes:
- Unlimited migrations
- 24/7 support with 1-hour SLA
- Dedicated migration specialist for first 90 days
- Training for up to 10 team members

**Alex Rivera:** That's significantly more than CloudShift's $60,000.

**Jennifer Walsh:** True, but CloudShift's support is business hours only with 24-hour SLA. Many customers switch to us after experiencing support delays during critical migrations.

**Brian Taylor:** That resonates. We had a Friday night issue with CloudShift and didn't get a response until Monday.

---

## References

**Jennifer Walsh:** I can connect you with two references:
1. FinanceApp Inc - similar scale, migrated Payment and Auth services
2. DataCorp - complex PostgreSQL migration with pgvector

**Alex Rivera:** Lisa, can you follow up with FinanceApp? Their payment stack sounds similar to ours.

**Lisa Park:** Will do.

---

## Concerns Raised

**Alex Rivera:** What's your track record with regulatory compliance? We're PCI-DSS certified and need to maintain that.

**Mark Stevens:** We're SOC 2 Type II certified and have helped 40+ PCI-compliant companies migrate. I'll include our compliance documentation in the follow-up.

**Brian Taylor:** Timeline question - if we decide to switch from CloudShift, how long to get started?

**Jennifer Walsh:** Onboarding takes about 2 weeks. We can begin migration work immediately after.

---

## Next Steps
1. MigrateX sends formal proposal and compliance docs
2. Lisa Park contacts FinanceApp reference
3. Alex Rivera presents comparison to Mia White by October 31
4. Decision meeting scheduled for November 1

---

## Initial Assessment
**Alex Rivera's Notes:** MigrateX seems more capable than CloudShift, especially for complex migrations. The 40% price increase is significant but may be justified by better support and features. Need to validate with references before recommending.

**Brian Taylor's Notes:** Their rollback capabilities address my main concern. I'm leaning toward recommending the switch.

**Lisa Park's Notes:** The PostgreSQL extension support is crucial for our Payments work. CloudShift failed us there.
