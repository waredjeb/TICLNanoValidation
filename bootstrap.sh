#!/usr/bin/env bash

# Bootstrap file for HTCondor jobs
# Sources the setup script to configure the environment on worker nodes

action() {
    source "{{validation_path}}/setup.sh" "$@"
}
action "$@"
