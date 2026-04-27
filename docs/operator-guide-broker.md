# Operator Guide: MQTT Broker

## Scope

This guide covers setup and upgrade flow for the shared MQTT broker used by site gateways.

## Deployment Shape

Recommended starting shape:

- infrastructure provisioned with `Terraform`
- broker runtime deployed with Docker
- persistent volume for broker data and mounted configuration

## Prerequisites

- reachable host or VM
- DNS name for the broker
- TLS certificate plan
- firewall rules that allow only required client access
- private configuration source for credentials and runtime values

## Initial Setup

1. Provision the host, network, storage, and DNS with `Terraform`.
2. Create the persistent data and config locations on the host.
3. Place broker configuration from the private deployment source onto the host.
4. Start the broker container with pinned image tags.
5. Verify listener reachability from the target gateway network.
6. Verify authentication and topic access with a test client.
7. Record the deployed version, image tag, and configuration revision.

## Validation Checklist

- gateways can resolve the broker DNS name
- TLS or other transport policy matches the deployment intent
- credentials are unique per gateway or client family
- retained test messages behave as expected
- logs and health signals are visible to operators

## Upgrade Procedure

1. Review release notes for the target broker image or package.
2. Snapshot or back up broker data and configuration.
3. Stage the new image tag and configuration in a test environment first.
4. Upgrade one non-production broker path before production.
5. Deploy the new container or package.
6. Re-run authentication and publish/subscribe validation.
7. Monitor connection churn, message failures, and resource usage.

## Rollback Procedure

1. Stop the upgraded runtime.
2. Revert to the previous image or package version.
3. Restore the prior configuration if the change included config updates.
4. Validate client reconnect behavior.
5. Record the rollback reason and observed fault.

## Operational Notes

- keep broker config revision separate from infrastructure revision
- do not store live credentials in this repository
- define topic ACLs before enabling control traffic
- retain enough logs to diagnose client reconnect storms and authentication failures
