/**
 * Built-in mock stream generator.
 *
 * Emits realistic StreamFrame objects for 3 robots (R1 rover, D1 drone,
 * G1 AGV) moving on looping missions inside the 200 m arena. Occasional
 * events are generated. Used when VITE_USE_MOCK=1 so the frontend can be
 * developed without the backend.
 *
 * @module mock
 */

const ARENA = 200;
const DT = 0.2;  // 5 Hz

// ─── Missions (looping waypoint sequences) ──────────────────

/** @type {Object<string, {type: import('./types').RobotType, name: string, cruise: number, z: number, wps: [number,number][]}>} */
const ROBOTS = {
  R1: {
    type: 'rover',
    name: 'Rover-1',
    cruise: 1.5,
    z: 0,
    wps: [[30, 30], [170, 30], [170, 100], [100, 100], [100, 170], [30, 170]],
  },
  D1: {
    type: 'drone',
    name: 'Drone-1',
    cruise: 6.0,
    z: 20,
    wps: [[40, 160], [160, 160], [160, 40], [40, 40]],
  },
  G1: {
    type: 'agv',
    name: 'AGV-1',
    cruise: 2.0,
    z: 0,
    wps: [[20, 100], [100, 20], [180, 100], [100, 180]],
  },
};

/** Seeded pseudo-random (xorshift32) for reproducible mock data */
function makeRng(seed = 42) {
  let s = seed | 0;
  return () => {
    s ^= s << 13;
    s ^= s >> 17;
    s ^= s << 5;
    return (s >>> 0) / 4294967296;
  };
}

const rng = makeRng(42);

/** @returns {number} Gaussian sample ~ N(0,1) via Box-Muller */
function randn() {
  const u1 = rng() || 0.0001;
  const u2 = rng();
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

// ─── Per-robot simulation state ─────────────────────────────

/** @typedef {{x:number, y:number, heading:number, speed:number, battery:number, temp:number, current:number, vibration:number, seq:number, wpIdx:number, wear:number}} RobotSim */

/** @type {Object<string, RobotSim>} */
const states = {};

for (const [id, cfg] of Object.entries(ROBOTS)) {
  const [wx, wy] = cfg.wps[0];
  states[id] = {
    x: wx,
    y: wy,
    heading: 0,
    speed: 0,
    battery: 100,
    temp: 30,
    current: cfg.type === 'drone' ? 6.0 : 2.0,
    vibration: 0.1,
    seq: 0,
    wpIdx: 0,
    wear: 0,
  };
}

let simTime = 0;

/** Step one robot forward by dt */
function stepRobot(id, dt) {
  const cfg = ROBOTS[id];
  const s = states[id];
  const wps = cfg.wps;

  // Pure pursuit toward next waypoint
  const [tx, ty] = wps[s.wpIdx];
  const dx = tx - s.x;
  const dy = ty - s.y;
  const dist = Math.sqrt(dx * dx + dy * dy);

  if (dist < 3) {
    // reached waypoint, advance (loop)
    s.wpIdx = (s.wpIdx + 1) % wps.length;
  }

  const desired = Math.atan2(dy, dx);
  let headErr = desired - s.heading;
  // wrap to [-PI, PI]
  while (headErr > Math.PI) headErr -= 2 * Math.PI;
  while (headErr < -Math.PI) headErr += 2 * Math.PI;

  const maxYaw = cfg.type === 'agv' ? 0.8 : cfg.type === 'drone' ? 2.5 : 1.5;
  const yawCmd = Math.max(-maxYaw, Math.min(maxYaw, headErr / dt));
  s.heading += yawCmd * dt;

  // speed ramp
  s.speed = cfg.cruise * Math.min(1, dist / 8);

  // move
  s.x += s.speed * Math.cos(s.heading) * dt;
  s.y += s.speed * Math.sin(s.heading) * dt;

  // clamp to arena
  s.x = Math.max(0, Math.min(ARENA, s.x));
  s.y = Math.max(0, Math.min(ARENA, s.y));

  // wear accumulates slowly
  const wearRate = cfg.type === 'rover' ? 0.0014 : cfg.type === 'drone' ? 0.0011 : 0.0008;
  s.wear = Math.min(1, s.wear + wearRate * dt);

  // battery drain
  const drainBase = cfg.type === 'rover' ? 0.010 : cfg.type === 'drone' ? 0.030 : 0.012;
  const drainSpeed = cfg.type === 'rover' ? 0.004 : cfg.type === 'drone' ? 0.003 : 0.004;
  s.battery = Math.max(5, s.battery - (drainBase + drainSpeed * s.speed) * dt);

  // current rises with wear
  const curBase = cfg.type === 'rover' ? 2.0 : cfg.type === 'drone' ? 6.0 : 3.0;
  const curSpeed = cfg.type === 'rover' ? 3.0 : cfg.type === 'drone' ? 1.0 : 4.0;
  s.current = (curBase + curSpeed * s.speed) * (1 + 0.6 * s.wear) + randn() * 0.1;

  // temperature first-order lag
  const tss = 30 + 2.0 * s.current;
  s.temp += (tss - s.temp) * dt / 25;

  // vibration
  const vibBase = cfg.type === 'rover' ? 0.10 : cfg.type === 'drone' ? 0.20 : 0.08;
  s.vibration = vibBase + 0.03 * s.speed + 1.5 * s.wear + randn() * 0.02;

  s.seq += 1;
}

/**
 * Build the next StreamFrame.
 * @returns {import('./types').StreamFrame}
 */
function nextFrame() {
  simTime += DT;

  /** @type {import('./types').RobotFrame[]} */
  const robots = [];
  /** @type {import('./types').Event[]} */
  const events = [];

  let syncSum = 0;

  for (const [id, cfg] of Object.entries(ROBOTS)) {
    stepRobot(id, DT);
    const s = states[id];

    // synthesize twin prediction (slightly ahead of observed, small residual)
    const residualPos = Math.abs(randn()) * 0.3;
    const syncScore = Math.max(0, Math.min(100, 100 * (1 - residualPos / 3)));
    syncSum += syncScore;

    const healthIndex = Math.max(0, 1 - s.wear);
    const rulS = s.wear < 1 ? ((1 - s.wear) / (cfg.type === 'rover' ? 0.0014 : cfg.type === 'drone' ? 0.0011 : 0.0008)) : 0;

    const telemetry = {
      robot_id: id,
      robot_type: cfg.type,
      ts: simTime,
      seq: s.seq,
      sig: null,
      x: s.x,
      y: s.y,
      z: cfg.z,
      heading: s.heading,
      speed: s.speed,
      battery: s.battery,
      motor_temp: s.temp,
      current: s.current,
      vibration: s.vibration,
    };

    const twin = {
      robot_id: id,
      ts: simTime,
      mode: 'synced',
      pred: {
        x: s.x + randn() * 0.2,
        y: s.y + randn() * 0.2,
        z: cfg.z,
        heading: s.heading + randn() * 0.01,
        speed: s.speed + randn() * 0.05,
        battery: s.battery + 0.1,
        motor_temp: s.temp - 0.3,
        current: s.current * 0.97,
        vibration: s.vibration * 0.95,
      },
      est: {
        x: s.x,
        y: s.y,
        z: cfg.z,
        heading: s.heading,
        speed: s.speed,
        battery: s.battery,
        motor_temp: s.temp,
        current: s.current,
        vibration: s.vibration,
      },
      residual_pos: residualPos,
      residual_norm: residualPos / 3,
      cross_track_err: Math.abs(randn()) * 0.5,
      heading_err: Math.abs(randn()) * 0.05,
      plan_x: s.x + randn() * 0.4,
      plan_y: s.y + randn() * 0.4,
      sync_score: syncScore,
      confidence: 1.0,
      since_last_packet_s: 0,
    };

    const health = {
      robot_id: id,
      ts: simTime,
      health_index: healthIndex,
      rul_s: rulS,
      rul_low_s: rulS * 0.8,
      rul_high_s: rulS * 1.2,
      status: healthIndex > 0.7 ? 'ok' : healthIndex > 0.4 ? 'watch' : healthIndex > 0.2 ? 'maintenance' : 'critical',
      drivers: {
        current: s.current,
        temp: s.temp,
        vib: s.vibration,
      },
    };

    const decision = {
      action: 'CONTINUE',
      reason: 'All systems nominal',
      confidence: 0.95,
      robot_id: id,
      override_active: false,
    };

    const mission = {
      mission_id: `mission-${id}`,
      robot_id: id,
      waypoints: cfg.wps.map(([wx, wy]) => ({ x: wx, y: wy, z: cfg.z })),
      cruise_speed: cfg.cruise,
      loop: true,
    };

    robots.push({
      robot_id: id,
      robot_type: cfg.type,
      name: cfg.name,
      telemetry,
      twin,
      health,
      decision,
      mission,
      active_attacks: [],
    });
  }

  // Generate occasional events (about 1 every 10s per robot)
  if (rng() < 0.02) {
    const rid = ['R1', 'D1', 'G1'][Math.floor(rng() * 3)];
    const kinds = ['deviation', 'noise_high', 'health_warning'];
    const kind = kinds[Math.floor(rng() * kinds.length)];
    const severity = kind === 'health_warning' ? 'warn' : kind === 'deviation' ? 'warn' : 'info';
    events.push({
      id: `evt-${simTime.toFixed(1)}-${rid}`,
      ts: simTime,
      robot_id: rid,
      kind,
      severity,
      message: `${kind.replace(/_/g, ' ')} on ${rid}`,
      detail: {},
    });
  }

  return {
    ts: simTime,
    robots,
    events,
    fleet_sync: syncSum / 3,
    ingest: { msgs_per_s: 15, dropped: 0, lag_ms: Math.abs(randn()) * 2 },
  };
}

/** Reset mock state (for testing) */
export function resetMock() {
  simTime = 0;
  for (const [id, cfg] of Object.entries(ROBOTS)) {
    const [wx, wy] = cfg.wps[0];
    Object.assign(states[id], {
      x: wx, y: wy, heading: 0, speed: 0, battery: 100,
      temp: 30, current: 2, vibration: 0.1, seq: 0, wpIdx: 0, wear: 0,
    });
  }
}

/**
 * Start a mock stream that calls `onFrame` at 5 Hz.
 * Returns a cleanup function that stops the interval.
 * @param {(frame: import('./types').StreamFrame) => void} onFrame
 * @returns {() => void}
 */
export function startMockStream(onFrame) {
  const id = setInterval(() => {
    onFrame(nextFrame());
  }, DT * 1000);
  return () => clearInterval(id);
}
