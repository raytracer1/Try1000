"""Collision detection between ball, players, and pitch boundaries."""

import math
from try1000_engine.config import PLAYER_RADIUS, BALL_RADIUS, BALL_CONTROL_RADIUS, PITCH_LENGTH, PITCH_WIDTH
from try1000_engine.physics.player import Player
from try1000_engine.physics.ball import Ball


class CollisionSystem:
    """Resolves ball-player possession and player-player collisions."""

    def find_nearest_player(self, ball: Ball, players: list[Player],
                            exclude_team: str | None = None) -> Player | None:
        """Find the player nearest to the ball, optionally excluding a team."""
        nearest = None
        min_dist = float("inf")
        control_radius = BALL_CONTROL_RADIUS

        for p in players:
            if exclude_team and p.team == exclude_team:
                continue
            dist = p.distance_to(ball.x, ball.y)
            if dist < control_radius and dist < min_dist:
                min_dist = dist
                nearest = p

        return nearest

    def resolve_ball_possession(self, ball: Ball, players: list[Player]):
        """Assign ball possession to nearest player.

        If multiple players from both teams are contesting, resolve as 50/50.
        Otherwise, nearest player picks up the ball (they actively chase it).
        """
        # Always pick up if within generous range, or assign to nearest
        pickup_range = 20.0  # players actively run to loose balls

        # Find nearest player overall
        nearest = None
        min_dist = float("inf")
        for p in players:
            dist = p.distance_to(ball.x, ball.y)
            if dist < min_dist:
                min_dist = dist
                nearest = p

        if nearest is None or min_dist > pickup_range:
            # No one near the ball — loose ball
            for p in players:
                p.has_ball = False
            return

        # Check for contested ball (players from both teams within 3m)
        contested = []
        for p in players:
            dist = p.distance_to(ball.x, ball.y)
            if dist < 3.0:
                contested.append(p)

        teams = {p.team for p in contested}
        if len(teams) > 1:
            # 50/50 challenge
            home_players = [p for p in contested if p.team == "home"]
            away_players = [p for p in contested if p.team == "away"]
            best_home = min(home_players, key=lambda p: p.distance_to(ball.x, ball.y)) if home_players else None
            best_away = min(away_players, key=lambda p: p.distance_to(ball.x, ball.y)) if away_players else None

            if best_home and best_away:
                h_dist = best_home.distance_to(ball.x, ball.y)
                a_dist = best_away.distance_to(ball.x, ball.y)
                h_score = best_home.physicality + (a_dist - h_dist) * 20
                a_score = best_away.physicality + (h_dist - a_dist) * 20
                winner = best_home if h_score >= a_score else best_away
            else:
                winner = best_home or best_away
        else:
            winner = min(contested, key=lambda p: p.distance_to(ball.x, ball.y)) if contested else nearest

        # Assign possession
        for p in players:
            p.has_ball = (p.player_id == winner.player_id)

        ball.last_touch_team = winner.team
        ball.last_touch_player = winner.player_id

    def clamp_to_pitch(self, player: Player):
        """Keep player within pitch boundaries."""
        half_length = PITCH_LENGTH / 2
        half_width = PITCH_WIDTH / 2

        player.x = max(-half_length, min(half_length, player.x))
        player.y = max(-half_width, min(half_width, player.y))

    def players_colliding(self, p1: Player, p2: Player) -> bool:
        """Check if two players are colliding."""
        dist = math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)
        return dist < PLAYER_RADIUS * 2

    def separate_players(self, p1: Player, p2: Player):
        """Push overlapping players apart."""
        dx = p1.x - p2.x
        dy = p1.y - p2.y
        dist = math.sqrt(dx ** 2 + dy ** 2)

        if dist < 0.01:
            # Avoid division by zero — nudge randomly
            p1.x += 0.1
            return

        overlap = PLAYER_RADIUS * 2 - dist
        if overlap > 0:
            push = overlap / 2
            p1.x += (dx / dist) * push
            p1.y += (dy / dist) * push
            p2.x -= (dx / dist) * push
            p2.y -= (dy / dist) * push
