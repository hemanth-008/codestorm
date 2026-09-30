/**
 * Frontend type definitions mirroring backend/app/contract/schemas.py.
 * Uses JSDoc for type documentation since the project uses plain JS.
 *
 * Units: meters, seconds, radians, battery %, degC, amps, g RMS.
 * Time `ts` is simulation seconds.
 */

/**
 * @typedef {'rover' | 'drone' | 'agv'} RobotType
 * @typedef {'synced' | 'dead_reckoning'} TwinMode
 * @typedef {'info' | 'warn' | 'critical'} Severity
 * @typedef {'ok' | 'watch' | 'maintenance' | 'critical'} HealthStatus
 * @typedef {'CONTINUE' | 'REROUTE' | 'RETURN_TO_BASE' | 'QUARANTINE_TELEMETRY' | 'SCHEDULE_MAINTENANCE'} Action
 * @typedef {'noise' | 'dropout' | 'spoof_freeze' | 'spoof_jump' | 'spoof_drift' | 'spoof_battery'} AttackKind
 * @typedef {'deviation' | 'deviation_cleared' | 'spoof_suspected' | 'noise_high' | 'noise_cleared' | 'dropout' | 'link_recovered' | 'health_warning' | 'maintenance_due' | 'mission_deployed' | 'override' | 'attack_injected' | 'attack_cleared'} EventKind
 */

/**
 * @typedef {Object} StateVec
 * @property {number} x
 * @property {number} y
 * @property {number} z
 * @property {number} heading - radians CCW from +x
 * @property {number} speed - m/s
 * @property {number} battery - %
 * @property {number} motor_temp - degC
 * @property {number} current - amps
 * @property {number} vibration - g RMS
 */

/**
 * @typedef {Object} Telemetry
 * @property {string} robot_id
 * @property {RobotType} robot_type
 * @property {number} ts
 * @property {number} seq
 * @property {string|null} sig
 * @property {number} x
 * @property {number} y
 * @property {number} z
 * @property {number} heading
 * @property {number} speed
 * @property {number} battery
 * @property {number} motor_temp
 * @property {number} current
 * @property {number} vibration
 */

/**
 * @typedef {Object} Waypoint
 * @property {number} x
 * @property {number} y
 * @property {number} z
 */

/**
 * @typedef {Object} Mission
 * @property {string} mission_id
 * @property {string} robot_id
 * @property {Waypoint[]} waypoints
 * @property {number} cruise_speed
 * @property {boolean} loop
 */

/**
 * @typedef {Object} TwinState
 * @property {string} robot_id
 * @property {number} ts
 * @property {TwinMode} mode
 * @property {StateVec} pred
 * @property {StateVec} est
 * @property {number} residual_pos
 * @property {number} residual_norm
 * @property {number} cross_track_err
 * @property {number} heading_err
 * @property {number|null} plan_x
 * @property {number|null} plan_y
 * @property {number} sync_score
 * @property {number} confidence
 * @property {number} since_last_packet_s
 */

/**
 * @typedef {Object} TwinSnapshot
 * @property {string} robot_id
 * @property {RobotType} robot_type
 * @property {number} ts
 * @property {StateVec} est
 * @property {Mission|null} mission
 * @property {number} waypoint_idx
 */

/**
 * @typedef {Object} HealthReport
 * @property {string} robot_id
 * @property {number} ts
 * @property {number} health_index - 1.0 healthy -> 0.0 failed
 * @property {number|null} rul_s - remaining useful life (seconds)
 * @property {number|null} rul_low_s
 * @property {number|null} rul_high_s
 * @property {HealthStatus} status
 * @property {Object<string, number>} drivers
 */

/**
 * @typedef {Object} Event
 * @property {string} id
 * @property {number} ts
 * @property {string|null} robot_id
 * @property {EventKind} kind
 * @property {Severity} severity
 * @property {string} message
 * @property {Object} detail
 */

/**
 * @typedef {Object} Decision
 * @property {Action} action
 * @property {string} reason
 * @property {number} confidence
 * @property {string|null} robot_id
 * @property {boolean} override_active
 */

/**
 * @typedef {Object} OverrideState
 * @property {string|null} robot_id
 * @property {Action} action
 * @property {number} seconds_left
 */

/**
 * @typedef {Object} AttackSpec
 * @property {string} robot_id
 * @property {AttackKind} kind
 * @property {number} magnitude
 * @property {number} duration_s
 */

/**
 * @typedef {Object} GroundTruth
 * @property {string} robot_id
 * @property {number} wear
 * @property {number|null} time_to_failure_s
 * @property {AttackKind|null} attack_active
 */

/**
 * @typedef {Object} SimResult
 * @property {string} mission_id
 * @property {string} robot_id
 * @property {number} eta_s
 * @property {number} end_battery
 * @property {number} risk
 * @property {[number,number][]} path
 * @property {string[]} violations
 * @property {boolean} safe_to_deploy
 * @property {string} notes
 */

/**
 * @typedef {Object} RobotFrame
 * @property {string} robot_id
 * @property {RobotType} robot_type
 * @property {string} name
 * @property {Telemetry} telemetry
 * @property {TwinState} twin
 * @property {HealthReport} health
 * @property {Decision} decision
 * @property {Mission|null} mission
 * @property {AttackKind[]} active_attacks
 */

/**
 * @typedef {Object} IngestStats
 * @property {number} msgs_per_s
 * @property {number} dropped
 * @property {number} lag_ms
 */

/**
 * @typedef {Object} StreamFrame
 * @property {number} ts
 * @property {RobotFrame[]} robots
 * @property {Event[]} events
 * @property {number} fleet_sync
 * @property {IngestStats} ingest
 */

/**
 * @typedef {Object} EvalRow
 * @property {string} scenario
 * @property {string} kind
 * @property {number} magnitude
 * @property {boolean} detected
 * @property {number|null} time_to_detect_s
 * @property {number} false_alarms
 * @property {number} min_sync
 * @property {number|null} recovery_s
 */

/**
 * @typedef {Object} EvalSummary
 * @property {number} detection_rate
 * @property {number} false_alarms_per_hour
 * @property {number|null} mean_time_to_detect_s
 * @property {number|null} mean_recovery_s
 * @property {number|null} rul_error_pct
 * @property {number} mean_sync_clean
 * @property {number} mean_sync_attacked
 */

/**
 * @typedef {Object} EvalResult
 * @property {number} seed
 * @property {number} ts
 * @property {EvalRow[]} rows
 * @property {EvalSummary} summary
 */

/**
 * @typedef {Object} Token
 * @property {string} access_token
 * @property {string} role - 'operator' | 'viewer'
 */

// export nothing – this file is pure JSDoc for IDE support
export {};
