---
issue: SHIP-1
title: Shoppers can save a basket
status: approved
saved: 2026-09-01T10:00:00+00:00
story: SHIP-1
decisions_reviewed:
  - 0001-client-signoff
---

# SHIP-1 — Shoppers can save a basket

## Problem

Shoppers lose their basket when they leave the site.

## Scope / Non-goals

- A shopper can save a basket and see it again after signing in.

**Non-goals**: sharing a basket with someone else.

## Acceptance Criteria

- AC1: a shopper can save a basket with one click.
- AC2: a saved basket shows again after sign-in.
- AC3: the existing tests pass.

## Technical Approach

Keep the basket in the session table.

## Task Decomposition

- SHIP-1-T1: save a basket. Contract: AC1.
- SHIP-1-T2: show a saved basket. Contract: AC2.
- SHIP-1-T3: tidy the basket code.

## Risks

- A very large basket could slow sign-in.

## Verify Plan

`npm test`.
