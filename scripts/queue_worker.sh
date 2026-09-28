#!/usr/bin/env bash
# queue_worker.sh <queue_file> <worker_id> -- pops case dirs atomically from queue_file and runs them.
Q="$1"; W="${2:-w}"; LOCK="$Q.lock"
while :; do
  D=$(flock "$LOCK" bash -c "head -n1 '$Q'; sed -i '1d' '$Q'")
  [ -z "$D" ] && break
  bash /home/ubuntu/run_hx_case.sh "$D" >> /home/ubuntu/hx_sweep/campaign_$W.log 2>&1
done
echo "[$(date +%H:%M:%S)] worker $W: queue empty" >> /home/ubuntu/hx_sweep/campaign_$W.log
