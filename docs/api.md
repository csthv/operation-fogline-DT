# Operation Fogline Plug-in API

The simulator imports `student_modules.py` and calls a fixed set of functions. Keep the names and return structures compatible with this reference.

## Strategy functions

### `list_strategies()`

Returns a dictionary mapping scenario identifiers to available strategy names.

### `get_strategy(strategy_name)`

Returns a `StrategyConfig` object. The simulator passes this configuration to the plug-in functions during a run.

## Frame preparation

### `prepare_frame(message, system_state, strategy_config)`

Builds a `Frame` from a `MissionMessage`.

Expected responsibilities:

- preserve message identity;
- create header metadata;
- keep payload bits available for later protection;
- set size fields consistently;
- include enough metadata for debugging and receiver decisions.

## Error control

### `attach_error_control(frame, system_state, strategy_config)`

Returns a `ProtectedFrame` with protected bits, overhead size, total size, and method metadata.

### `verify_error_control(received_frame, strategy_config)`

Returns a dictionary describing whether the received frame is valid, corrected, ambiguous, or invalid. The receiver decision function consumes this result.

## Multiplexing

### `choose_multiplexing_plan(protected_frames, system_state, queue_state, strategy_config)`

Returns a scheduling plan that assigns frames to TDM slots or FDM bands while respecting capacity and allocation decisions.

A good plan should consider:

- priority;
- department allocation;
- frame size;
- backlog;
- avoided slots/bands;
- emergency traffic.

## Receiver decision

### `decide_received_frame(received_frame, verification_result, system_state, strategy_config)`

Returns a `ReceiverDecision`. The decision should distinguish accepted frames, rejected frames, retransmission requests, ambiguous frames, and invalid frames.

## Retransmission

### `decide_retransmission(frame_status, message_context, system_state, strategy_config)`

Returns a `RetransmissionDecision`. The decision should account for attempts, deadlines, priority, capacity pressure, and whether another retry is likely to help.

## Adaptation

### `adapt_strategy(dashboard_snapshot, current_strategy_config, capabilities)`

Returns the strategy configuration to use after a freeze point. The starter behavior keeps the current strategy unchanged. More advanced implementations may change error control, receiver strictness, allocation, or suppression policies based on observed metrics.

## Compatibility rules

- Do not rename required functions.
- Do not change required parameter order.
- Return the expected dataclass or dictionary shape.
- Prefer adding metadata over removing fields.
- Run short smoke tests after each module change.
