# Operator Guide: Gateway Pi

## Scope

This guide covers setup and upgrade flow for fixed-site Raspberry Pi gateways such as `ag01` and `bg02`.

## Deployment Shape

Recommended starting shape:

- gateway application released through GitHub Actions
- deployed as a pinned container image or packaged application
- local persistent storage for SQLite state and logs
- USB-attached Heltec radio

## Prerequisites

- Raspberry Pi with stable power
- persistent storage sized for queue and log retention
- working network path to the MQTT broker
- assigned gateway identifier and site code
- private configuration for broker credentials, channel policy, and local paths

## Initial Setup

1. Prepare the Pi OS image and apply baseline system updates.
2. Attach persistent storage or confirm the local data path survives reboot.
3. Install Docker or the selected service runtime.
4. Place the private environment file and policy configuration on the host.
5. Connect the Heltec radio over USB.
6. Deploy the pinned gateway artifact.
7. Start the gateway service with restart policy enabled.
8. Validate that the gateway can:
   - load config
   - connect to the broker
   - detect the radio state
   - write queue state and logs
9. Record the deployed application version and config revision.

## Validation Checklist

- gateway publishes health state
- queue database initializes successfully
- logs are written to the expected location
- broker authentication succeeds
- radio presence is reported correctly
- inbound traffic is not consumed when the radio is unavailable unless bounded queueing is explicitly enabled

## Upgrade Procedure

1. Review the target release notes and schema compatibility.
2. Back up the local queue database and logs.
3. Copy in the new artifact or pull the new image tag.
4. Stop the running service.
5. Start the new version with the same persistent state mounted.
6. Verify health publication, queue depth, and broker connectivity.
7. Observe the management dashboard before declaring success.

## Rollback Procedure

1. Stop the new version.
2. Restart the prior known-good image or package.
3. Restore the previous config revision if the change included config edits.
4. Validate queue replay and health publication.
5. Document whether the rollback was caused by runtime behavior, configuration, or radio interaction.

## Local State Ownership

The gateway owns:

- SQLite queue and event database
- local file logs
- gateway-specific runtime config
- radio attachment state

That state should not be embedded in the image or lost during upgrade.
