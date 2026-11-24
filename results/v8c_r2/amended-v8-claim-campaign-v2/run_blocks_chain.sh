#!/bin/zsh
# Usage: run_blocks_chain.sh <first-block> <slots per block...>; stops at the first non-zero block.
V=/Users/fgtek002/dynapm-v8c-frozen/results/v8c_r2/amended-v8-claim-campaign-v2
N=$1; shift
for S in "$@"; do
  $V/run_block.sh $N $S || exit $?
  N=$((N+1))
done
