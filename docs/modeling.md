# Modeling

Morti Score uses simple statistical football models to demonstrate how a
backend can combine domain data, model calculation, caching and API response
schemas. The models are intentionally transparent and lightweight: they are
useful for engineering demonstration and model explainability, not for betting
or trading decisions.

## Basic Poisson model

The basic Poisson model treats goals as count events. For each team it estimates
attack and defense strength from historical finished matches, then combines
those strengths with league-average home and away scoring rates.

Poisson is a common baseline for football because goals are low-frequency
integer events. In this project it is used as an interpretable first model:
calculate expected goals for both teams, generate probabilities for scorelines,
and aggregate those scorelines into home-win, draw and away-win probabilities.

## Data used

The current models use only local project data:

- teams from the `teams` table, loaded from `data/teams.json`;
- matches from the `matches` table, loaded from `data/matches.json`;
- only finished matches with both `home_goals` and `away_goals` present;
- match dates, team ids, scorelines and match status;
- derived values such as team form, league averages and xG-proxy.

The prediction endpoint does not call an external football data provider. This
keeps the demo reproducible, but also limits model quality.

## Expected goals calculation

For the basic model, the service calculates league-level averages first:

- average home goals per finished match;
- average away goals per finished match.

Then it calculates team strength metrics:

- home attack: team home goals scored compared with league home average;
- home defense: team home goals conceded compared with league away average;
- away attack: team away goals scored compared with league away average;
- away defense: team away goals conceded compared with league home average.

Expected goals are then estimated as:

```text
expected_home_goals = league_home_goals
  * home_team_home_attack
  * away_team_away_defense

expected_away_goals = league_away_goals
  * away_team_away_attack
  * home_team_home_defense
```

The score matrix applies Poisson probabilities for scores from 0-0 to 5-5 and
returns the most likely scorelines plus normalized match-result probabilities.

## Improved Poisson model

The improved Poisson model keeps the same baseline structure but adds recent
team form and an xG-proxy adjustment.

It uses a rolling window of recent matches for each team and applies a recency
weight, so newer matches influence the estimate more than older matches. The
model blends long-term team strengths with recent attacking and defensive form.
This helps the model react when a team is currently stronger or weaker than its
season-level averages imply.

## xG-proxy in this project

Real expected goals require shot-level data: shot location, body part, assist
type, pressure, game state and other contextual features. The seed data in this
project does not contain those fields.

Because of that, Morti Score uses an xG-proxy rather than real xG. The proxy is
a deterministic heuristic derived from available match data:

- goals scored increase the attacking proxy;
- goals conceded add a smaller defensive/game-state adjustment;
- home and away contexts use a small multiplier difference;
- the value is bounded so it cannot collapse to zero.

This proxy is useful for demonstrating where an xG-like signal would enter the
architecture. It should not be interpreted as real expected goals.

## Elo-based model

The Elo model assigns every team a rating and updates it after each finished
match. A team gains rating points when it performs better than expected and
loses points when it performs worse than expected.

In this project Elo uses:

- a base rating for new teams;
- a K-factor to control update size;
- home advantage in the pre-match expectancy calculation;
- a goal-margin multiplier so larger wins move ratings more;
- match ordering by date and id before rating updates.

For prediction, the model converts the rating gap into win expectancy, then
uses that expectancy to shift league-average home and away expected goals.

## Why this is not a production betting model

These models are not production betting models because they lack the data,
validation and risk controls required for that use case.

Important missing pieces include:

- real xG and shot-level event data;
- injuries, suspensions, lineups and rotation information;
- market odds and closing-line comparison;
- home/away schedule congestion and travel effects;
- opponent-adjusted strength over multiple seasons;
- calibration checks and backtesting on out-of-sample data;
- bankroll, risk and uncertainty management;
- monitoring for data drift and broken data feeds.

The current implementation is best understood as an explainable analytics demo
and backend architecture sample.

## Limitations of the seed-data approach

Seed data makes the project easy to run, but it has clear modeling limits:

- the dataset is small and static;
- it may not represent current team strength;
- it has no lineups, shots, possession, odds or event-level features;
- the same data is used for demonstration and tests;
- there is no train/test split by time;
- prediction quality cannot be measured reliably from such a small sample.

This means model output should be treated as illustrative rather than accurate.

## How to validate on real data

A stronger validation process would use historical real-world fixtures and a
strict time-based split:

1. Import several seasons of fixtures, results and event-level data.
2. Train or fit model parameters only on matches before a cutoff date.
3. Predict future matches after that cutoff without using future information.
4. Measure log loss, Brier score and calibration for 1X2 probabilities.
5. Measure scoreline quality with ranked probability score or likelihood.
6. Compare against baselines such as league-average, Elo-only and bookmaker
   closing odds where legally available.
7. Re-run validation by league, season, home/away split and team strength tier.
8. Track model drift over time and alert when calibration degrades.

This would turn the current demo models into a measurable analytics pipeline.