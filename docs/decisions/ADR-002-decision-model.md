# ADR-002: Three-class canonical decision model

**Status:** Accepted

Policy ground truth contains exactly `allow`, `block`, or `escalate`. Execution failures, timeouts, and malformed non-decisions are outcomes rather than policy labels. No transport status, refusal text, or exception is allowed to default to ALLOW.

