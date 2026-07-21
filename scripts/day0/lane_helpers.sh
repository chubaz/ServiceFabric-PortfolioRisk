#!/usr/bin/env bash
# Day 0 worktree synchronization helpers.

sync_day0_lane() {
  if [[ "$#" -lt 2 || "$#" -gt 3 ]]; then
    echo "usage: sync_day0_lane WORKTREE EXPECTED_BRANCH [TARGET_BRANCH]" >&2
    return 2
  fi

  local worktree="$1"
  local expected_branch="$2"
  local target_branch="${3:-integration/day0}"
  local current_branch
  local dirty
  local current_pin
  local target_pin
  local preserve_dirty_servicefabric=false

  if [[ ! -d "$worktree" ]]; then
    echo "ERROR: worktree does not exist: $worktree" >&2
    return 1
  fi

  current_branch="$(git -C "$worktree" branch --show-current)" || return 1
  if [[ "$current_branch" != "$expected_branch" ]]; then
    echo "ERROR: $worktree is on $current_branch, expected $expected_branch" >&2
    return 1
  fi

  if ! git -C "$worktree" merge-base --is-ancestor "$expected_branch" "$target_branch"; then
    echo "ERROR: $expected_branch cannot fast-forward to $target_branch" >&2
    return 1
  fi

  dirty="$(git -C "$worktree" status --porcelain)"
  if [[ -n "$dirty" ]]; then
    if [[ "${SYNC_DAY0_PRESERVE_DIRTY_SERVICEFABRIC:-0}" == "1" && "$dirty" == " M vendor/servicefabric" ]]; then
      current_pin="$(git -C "$worktree/vendor/servicefabric" rev-parse HEAD)" || return 1
      target_pin="$(git -C "$worktree" rev-parse "$target_branch:vendor/servicefabric")" || return 1
      if [[ "$current_pin" != "$target_pin" ]]; then
        echo "ERROR: refusing to preserve a dirty ServiceFabric submodule across a pin change" >&2
        return 1
      fi
      preserve_dirty_servicefabric=true
    else
      echo "ERROR: $worktree is dirty; refusing to synchronize" >&2
      git -C "$worktree" status --short
      return 1
    fi
  fi

  git -C "$worktree" merge --ff-only "$target_branch" || return 1

  if [[ "$preserve_dirty_servicefabric" == true ]]; then
    echo "Preserved dirty vendor/servicefabric at $current_pin"
  else
    git -C "$worktree" submodule update --init --recursive || return 1
  fi

  echo "Synchronized $expected_branch to $(git -C "$worktree" rev-parse --short HEAD)"
}
