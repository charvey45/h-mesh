# Operator Guide: Meshtastic Radios

## Scope

This guide covers setup and upgrade flow for Meshtastic radios used as local RF devices.

## Deployment Shape

Radios are configuration-managed devices.

- firmware version matters
- channel and identity settings matter
- application package deployment usually does not apply to stock radios

## Prerequisites

- assigned device identifier such as `ar01` or `br02`
- selected role and site assignment
- approved channel configuration
- expected GPS reporting behavior
- access to the Meshtastic client used for provisioning

## Initial Setup

1. Flash the approved Meshtastic firmware version.
2. Assign the device identifier that matches the fleet naming model.
3. Apply the site-specific channel profile.
4. Configure role, radio parameters, and GPS reporting interval.
5. Join the device to the expected local mesh.
6. Verify that the device can exchange traffic with the site gateway or other local nodes.

## Validation Checklist

- device identifier matches fleet inventory
- firmware version matches the approved site baseline
- channel secrets match the intended local mesh only
- GPS behavior matches the device role
- radio is not unintentionally cross-talking with colocated lab meshes

## Upgrade Procedure

1. Confirm the target firmware is approved for the site.
2. Export or record the current config profile.
3. Flash the new firmware.
4. Re-apply the validated config profile if the upgrade process resets settings.
5. Verify message flow and GPS reporting after the upgrade.

## Rollback Procedure

1. Reflash the previous approved firmware.
2. Re-apply the previous config profile.
3. Validate local mesh participation.

## Operational Notes

- manage radios through versioned profiles and inventory records
- use separate lab profiles when multiple logical sites are within RF range
- do not depend on the radio alone for inter-site observability or durable queueing
