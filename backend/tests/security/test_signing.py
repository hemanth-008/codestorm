from app.contract.schemas import Telemetry
from app.security.signing import sign_telemetry, verify_telemetry


def packet(**changes):
    values = {
        "robot_id": "R1",
        "robot_type": "rover",
        "ts": 1.23456,
        "seq": 7,
        "x": 4.5678,
        "y": 9.8765,
        "z": 0.0,
        "heading": 0.1,
        "speed": 1.2345,
        "battery": 98.765,
        "motor_temp": 25.0,
        "current": 3.0,
        "vibration": 0.1,
    }
    values.update(changes)
    return Telemetry(**values)


def test_signing_matches_contract_rounding_and_verifies():
    tel = packet()
    signature = sign_telemetry(tel, "secret")
    assert signature == "9c2a57be79a41eb76dca0a93ba045ac6966e538bfad8b7ae2e603c3d8e7da2f5"
    assert verify_telemetry(tel.model_copy(update={"sig": signature}), "secret")


def test_signature_rejects_packet_mutation_and_unsigned_packet():
    tel = packet()
    signature = sign_telemetry(tel, "secret")
    assert not verify_telemetry(tel.model_copy(update={"sig": signature, "x": tel.x + 1}), "secret")
    assert not verify_telemetry(tel, "secret")
