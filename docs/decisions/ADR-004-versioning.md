# ADR-004: Immutable benchmark snapshots

**Status:** Accepted

Published dataset versions are immutable and content-hashed. Correcting a ground-truth label creates a new version. Directly equivalent regression comparisons require the same dataset and policy version; mismatches remain visible but carry compatibility warnings.

