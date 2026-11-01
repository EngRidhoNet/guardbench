# ADR-003: Classification metrics and execution coverage

**Status:** Accepted

Classification metrics use only successfully normalized three-class decisions. Every report separately discloses attempted, scored, excluded, and failed counts plus coverage and indeterminate rate. Zero-denominator metrics are unavailable (`null`), not zero. This prevents target failures from improving apparent accuracy.

