# Executive Team Weekly Sync
**Date:** October 15, 2024
**Attendees:** Mia White (VP Engineering), Michael Torres (VP Product), Tom Baker (Director of Brand), Kevin Lee (Engineering Manager)
**Facilitator:** Mia White

## Agenda
1. Cloud Migration Update
2. Q4 Budget Review
3. Hiring Pipeline
4. Open Items

---

## 1. Cloud Migration Update

**Mia White:** Let's start with cloud migration. Alex Rivera's team has made good progress on the Auth Service migration. We're about 40% complete.

**Michael Torres:** What's the timeline looking like? Product has several features blocked on this.

**Mia White:** We're targeting end of Q4 for the core services. Auth Service and API Gateway should be done by November. Payment Service is more complex - Sarah Chen raised concerns about the database migration strategy.

**Kevin Lee:** Sarah mentioned the Payment Service has some legacy dependencies that aren't cloud-native. We might need to refactor before migrating.

**Mia White:** That's a valid concern. Let's schedule a technical review with Sarah and Alex Rivera next week. I want to understand the full scope before we commit to the Q4 deadline.

**ACTION:** Schedule cloud migration technical review with Sarah Chen and Alex Rivera

---

## 2. Q4 Budget Review

**Tom Baker:** Marketing is requesting an additional $50K for the product launch campaign in November.

**Michael Torres:** That's aggressive. Can we justify the ROI?

**Tom Baker:** Based on our Q2 campaign performance, we expect a 3x return. Nancy Wright has the detailed analysis.

**Mia White:** Engineering is under budget by about $30K due to the delayed infrastructure purchases. We could reallocate.

**DECISION:** Approved $30K reallocation from Engineering to Marketing. Remaining $20K pending CFO approval.

---

## 3. Hiring Pipeline

**Kevin Lee:** We have three strong candidates for the Senior Platform Engineer role. Amy Chen has been doing the technical screens.

**Mia White:** What's the timeline?

**Kevin Lee:** Final interviews next week. Oscar Hernandez from HR is coordinating the offers.

**Michael Torres:** Product also needs a PM. Julia Adams has been stretched thin covering two product areas.

**DECISION:** Fast-track the engineering hire. Product PM role to be discussed in next week's planning.

---

## 4. Open Items

**Mia White:** One concern I want to raise - we've had three incidents in the past month related to the Notification Service. Alex Thompson has been doing great triage work, but we need a more permanent fix.

**Kevin Lee:** Hannah White suggested we implement a circuit breaker pattern. Should we prioritize this?

**Mia White:** Yes. Let's add it to the Q4 reliability initiatives. I want a proposal from the Platform Team by end of week.

**Michael Torres:** Agreed. Customer complaints about notification delays are increasing.

---

## Next Meeting
October 22, 2024 - Same time
