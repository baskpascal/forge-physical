"""Real MAVSDK smoke scenario, executed in the PX4 container network namespace."""

import asyncio

from mavsdk import System


async def main() -> None:
    drone = System()
    await drone.connect(system_address="udpin://0.0.0.0:14540")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("vehicle_discovery=passed")
            break
    async for health in drone.telemetry.health():
        print(f"health_global_position_ok={health.is_global_position_ok}")
        break
    await drone.action.arm()
    print("arming=passed")
    await drone.action.takeoff()
    await asyncio.sleep(7)
    async for position in drone.telemetry.position():
        print(f"hover_altitude_m={position.relative_altitude_m:.2f}")
        break
    await drone.action.land()
    async for in_air in drone.telemetry.in_air():
        if not in_air:
            print("landing=passed")
            return


asyncio.run(asyncio.wait_for(main(), timeout=90))
