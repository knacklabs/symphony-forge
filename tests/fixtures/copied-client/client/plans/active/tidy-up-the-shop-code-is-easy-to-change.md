---
issue: tidy-up
title: The shop code is easy to change
status: approved
saved: 2026-09-05T10:00:00+00:00
story: tidy-up
---

# tidy-up — The shop code is easy to change

## Problem

Changing the checkout takes too long.

## Scope / Non-goals

- The checkout code is split into one module per step.

## Acceptance Criteria

- AC1: checkout is split into one module per step.
- AC2: the old checkout helpers are gone.

## Task Decomposition

- tidy-up-T1: split checkout.
- tidy-up-T2: remove the old helpers.

## Risks

- A missed caller of an old helper.
