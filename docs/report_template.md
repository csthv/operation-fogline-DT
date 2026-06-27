# Operation Fogline Engineering Report Template

## 1. Design Overview

Summarize the final communication design and the main scenario risks it addresses.

## 2. Frame Format

Describe header fields, payload handling, size calculation, and any compact/emergency encoding choices.

## 3. Error-Control Strategy

Explain which protection methods are used and why. Discuss detection, correction, overhead, and failure cases.

## 4. Multiplexing Strategy

Explain when TDM or FDM is used and how resources are allocated among Radar, Watchtower, and Command traffic.

## 5. Receiver Decision Policy

Explain how valid, invalid, ambiguous, corrupted, and retransmission-request cases are handled.

## 6. Retransmission Policy

Discuss retry limits, deadline behavior, capacity pressure, and priority trade-offs.

## 7. Adaptation Policy

Describe any rule-based or mathematical adaptation performed at freeze points.

## 8. Results by Scenario

For each scenario, include key metrics from logs and explain what changed after each design iteration.

## 9. Rejected Alternatives

Describe at least one plausible design that was tested or considered but rejected.

## 10. Final Engineering Justification

Use log evidence and calculations to justify the final design.
