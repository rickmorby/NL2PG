#!/usr/bin/env bash
ssh -f -N -o "ServerAliveInterval 30" -o "ServerAliveCountMax 3" -L 11434:127.0.0.1:11434 manuel
