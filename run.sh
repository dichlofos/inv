#!/usr/bin/env bash
days="$1"
if [ -z "$days" ] ; then
    days=100
fi
python3 ./counter.py --days $days
