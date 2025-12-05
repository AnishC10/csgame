"""
StoryQuest - 2D Story-Based Boss-Fight Game (single-file)

Controls:
  Move: arrow keys or WASD
  Melee attack (short range): Z
  Ranged shot: SPACE
  Pause/Menu: ESC

Structure:
  - MenuView: title & "Press ENTER"
  - StoryView: short dialog / transition before each boss
  - GameView: main gameplay; two boss stages with different AI
  - GameOverView: win/lose + replay/menu

Designed to be easy to read and modify for presentation.
"""

import arcade
import random
import math
from typing import Optional

# --- Window / game constants ---
SCREEN_WIDTH = 900
SCREEN_HEIGHT = 600
SCREEN_TITLE = "StoryQuest: The Twin Guardians"

PLAYER_SPEED = 4.0
PLAYER_SIZE = 20
PLAYER_MAX_HEALTH = 8

BULLET_SPEED = 9
BULLET_COOLDOWN = 0.35  # seconds between shots
MELEE_COOLDOWN = 0.6
MELEE_RANGE = 36
MELEE_DAMAGE = 2

BOSS_COUNT = 2

# Colors for convenience
BG_COLOR = arcade.color.DARK_SLATE_BLUE
UI_COLOR = arcade.color.ALMOND


class SimpleTimer:
    """Utility simple cooldown timer."""
    def __init__(self, cooldown: float = 0.0):
        self.cooldown = cooldown
        self.time_left = 0.0

    def update(self, delta: float):
        if self.time_left > 0:
            self.time_left -= delta
            if self.time_left < 0:
                self.time_left = 0.0

    def ready(self):
        return self.time_left == 0.0

    def trigger(self):
        self.time_left = self.cooldown


class MenuView(arcade.View):
    """Main menu screen."""

    def on_show(self):
        arcade.set_background_color(BG_COLOR)

    def on_draw(self):
        self.clear()
        arcade.draw_text("STORYQUEST: THE TWIN GUARDIANS",
                         SCREEN_WIDTH // 2, SCREEN_HEIGHT * 0.65,
                         arcade.color.GOLD, font_size=36, anchor_x="center")
        arcade.draw_text("A mini story-based boss-fight game",
                         SCREEN_WIDTH // 2, SCREEN_HEIGHT * 0.55,
                         arcade.color.LIGHT_GRAY, font_size=16, anchor_x="center")
        arcade.draw_text("Controls: Move - WASD/Arrows   Melee - Z   Shoot - SPACE",
                         SCREEN_WIDTH // 2, SCREEN_HEIGHT * 0.45,
                         arcade.color.WHITE, font_size=14, anchor_x="center")

        arcade.draw_text("Press ENTER to Start", SCREEN_WIDTH // 2, SCREEN_HEIGHT * 0.28,
                         arcade.color.LIGHT_GREEN, font_size=20, anchor_x="center")
        arcade.draw_text("Press ESC to Quit", SCREEN_WIDTH // 2, SCREEN_HEIGHT * 0.22,
                         arcade.color.LIGHT_GRAY, font_size=12, anchor_x="center")

    def on_key_press(self, key, modifiers):
        if key in (arcade.key.ENTER, arcade.key.RETURN):
            # Start first story/boss stage
            story = StoryView(stage=1)
            self.window.show_view(story)
        elif key == arcade.key.ESCAPE:
            arcade.close_window()


class StoryView(arcade.View):
    """Short dialog / transition screen before each boss."""

    STORIES = {
        1: [
            "You are Arin, a courier with a secret blade.",
            "An ancient guardian blocks the forest road, allowing none to pass.",
            "Defeat it, and the path to the mountain opens.",
            "Prepare yourself..."
        ],
        2: [
            "Having bested the first guardian, Arin presses on.",
            "A twin guardian, more cunning and swift, awaits at the peak.",
            "This fight will test everything you've learned.",
            "Steady your heart."
        ]
    }

    def __init__(self, stage: int):
        super().__init__()
        self.stage = stage
        self.index = 0
        self.advance_cooldown = 0.1

    def on_show(self):
        arcade.set_background_color(BG_COLOR)

    def on_draw(self):
        self.clear()
        # Decorative background
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT, BG_COLOR)

        # Title
        arcade.draw_text(f"Stage {self.stage}", SCREEN_WIDTH // 2, SCREEN_HEIGHT * 0.65,
                         arcade.color.BEIGE, font_size=28, anchor_x="center")
        # Dialog box
        arcade.draw_rectangle_filled(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20, 760, 180, arcade.color.BLACK + (180,))
        arcade.draw_text(self.STORIES[self.stage][self.index],
                         SCREEN_WIDTH // 2 - 340, SCREEN_HEIGHT // 2 - 10,
                         arcade.color.WHITE, font_size=18)
        arcade.draw_text("Press ENTER to continue", SCREEN_WIDTH // 2, SCREEN_HEIGHT * 0.18,
                         arcade.color.LIGHT_GRAY, font_size=12, anchor_x="center")

    def on_key_press(self, key, modifiers):
        if key in (arcade.key.ENTER, arcade.key.RETURN):
            self.index += 1
            if self.index >= len(self.STORIES[self.stage]):
                # Start the game view for this stage
                game = GameView(stage=self.stage)
                game.setup()
                self.window.show_view(game)


class Player(arcade.Sprite):
    """Player sprite using a simple circle texture."""

    def __init__(self):
        # Use a small texture circle via SpriteCircle helper
        super().__init__()
        self.texture = arcade.make_circle_texture(PLAYER_SIZE * 2, arcade.color.CYAN)
        self.width = PLAYER_SIZE * 2
        self.height = PLAYER_SIZE * 2
        self.center_x = SCREEN_WIDTH // 2
        self.center_y = SCREEN_HEIGHT // 2
        self.health = PLAYER_MAX_HEALTH
        self.facing_angle = 0.0  # radians


class Boss(arcade.Sprite):
    """Boss with health and simple behavior configuration."""

    def __init__(self, stage: int):
        # Visual size scales with stage
        size = 36 + 8 * stage
        super().__init__()
        color = arcade.color.RED if stage == 1 else arcade.color.ORANGE_RED
        self.texture = arcade.make_circle_texture(size * 2, color)
        self.width = size * 2
        self.height = size * 2
        self.center_x = SCREEN_WIDTH // 2
        self.center_y = SCREEN_HEIGHT - 120
        self.max_health = 30 + (stage - 1) * 20
        self.health = self.max_health
        self.stage = stage
        self.phase_timer = 0.0  # used for different behavior phases

    def normalized_health(self):
        return max(self.health / self.max_health, 0.0)


class Bullet(arcade.Sprite):
    """Simple bullet sprite."""

    def __init__(self, x, y, dx, dy, color=arcade.color.YELLOW, speed=1.0, owner="player"):
        super().__init__()
        self.texture = arcade.make_circle_texture(6, color)
        self.center_x = x
        self.center_y = y
        self.change_x = dx * speed
        self.change_y = dy * speed
        self.owner = owner  # "player" or "boss"


class GameView(arcade.View):
    """Main gameplay. Handles player, bosses, bullets, attacks, UI."""

    def __init__(self, stage: int = 1):
        super().__init__()
        self.stage = stage
        # Sprite lists
        self.player_list = None
        self.boss_list = None
        self.player_bullets = None
        self.enemy_bullets = None
        self.particles = None

        # Entities
        self.player: Optional[Player] = None
        self.boss: Optional[Boss] = None

        # Movement state
        self.up = self.down = self.left = self.right = False

        # Timers
        self.shoot_timer = SimpleTimer(BULLET_COOLDOWN)
        self.melee_timer = SimpleTimer(MELEE_COOLDOWN)

        # Score / state
        self.score = 0
        self.game_over = False
        self.win = False

        # For presentation: small stage intro pause
        self.intro_timer = 0.5

    def setup(self):
        arcade.set_background_color(BG_COLOR)
        # Create sprite lists
        self.player_list = arcade.SpriteList()
        self.boss_list = arcade.SpriteList()
        self.player_bullets = arcade.SpriteList()
        self.enemy_bullets = arcade.SpriteList()
        self.particles = arcade.SpriteList()

        # Create player
        self.player = Player()
        self.player.center_x = SCREEN_WIDTH // 2
        self.player.center_y = 100
        self.player_list.append(self.player)

        # Spawn boss for this stage
        self.boss = Boss(stage=self.stage)
        # Boss positions vary slightly
        if self.stage == 1:
            self.boss.center_x = SCREEN_WIDTH // 2
            self.boss.center_y = SCREEN_HEIGHT - 120
        else:
            self.boss.center_x = SCREEN_WIDTH // 2
            self.boss.center_y = SCREEN_HEIGHT - 140
        self.boss_list.append(self.boss)

        # Reset state
        self.score = 0
        self.shoot_timer.time_left = 0.0
        self.melee_timer.time_left = 0.0
        self.game_over = False
        self.win = False
        self.intro_timer = 0.6

    def on_show(self):
        arcade.set_background_color(BG_COLOR)

    def on_draw(self):
        self.clear()

        # Background subtle gradient (simple)
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT, BG_COLOR)

        # Ground platform
        arcade.draw_rectangle_filled(SCREEN_WIDTH // 2, 60, SCREEN_WIDTH - 40, 120, arcade.color.DARK_OLIVE_GREEN)

        # Draw all sprites
        self.player_list.draw()
        self.boss_list.draw()
        self.player_bullets.draw()
        self.enemy_bullets.draw()
        self.particles.draw()

        # UI: Health, boss bar, score
        arcade.draw_text(f"Health: {self.player.health}", 12, SCREEN_HEIGHT - 26, UI_COLOR, 16)
        arcade.draw_text(f"Score: {self.score}", 12, SCREEN_HEIGHT - 50, UI_COLOR, 14)

        # Boss health bar (if boss exists)
        if self.boss and self.boss in self.boss_list:
            bar_width = 400
            bar_x = SCREEN_WIDTH - bar_width - 20
            bar_y = SCREEN_HEIGHT - 40
            # outline
            arcade.draw_rectangle_outline(bar_x + bar_width / 2, bar_y, bar_width + 4, 22, arcade.color.WHITE)
            # fill
            fill_w = int(bar_width * self.boss.normalized_health())
            arcade.draw_rectangle_filled(bar_x + fill_w / 2, bar_y, fill_w, 18, arcade.color.RED)
            arcade.draw_text(f"Boss HP: {self.boss.health}/{self.boss.max_health}", bar_x + bar_width / 2, bar_y - 6,
                             arcade.color.WHITE, 12, anchor_x="center")

        # If in intro pause, overlay text
        if self.intro_timer > 0:
            alpha = int(min(self.intro_timer * 400, 220))
            arcade.draw_rectangle_filled(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, SCREEN_WIDTH, SCREEN_HEIGHT, (0, 0, 0, alpha))
            arcade.draw_text(f"Stage {self.stage} - Face the Guardian", SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 10,
                             arcade.color.WHITE, 24, anchor_x="center")

        # If game over, show overlay instructions (final message will be shown in GameOverView)
        if self.game_over:
            msg = "YOU WIN!" if self.win else "YOU DIED"
            arcade.draw_rectangle_filled(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, 560, 140, (0, 0, 0, 200))
            arcade.draw_text(msg, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 12, arcade.color.GOLD, 28, anchor_x="center")
            arcade.draw_text("Press R to replay, M for menu", SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 18,
                             arcade.color.LIGHT_GRAY, 14, anchor_x="center")

    def on_update(self, delta_time: float):
        # Update timers
        self.shoot_timer.update(delta_time)
        self.melee_timer.update(delta_time)
        if self.intro_timer > 0:
            self.intro_timer -= delta_time
            return  # freeze gameplay briefly for story feel

        if self.game_over:
            return

        # Update movement
        dx = dy = 0
        if self.up:
            dy += PLAYER_SPEED
        if self.down:
            dy -= PLAYER_SPEED
        if self.left:
            dx -= PLAYER_SPEED
        if self.right:
            dx += PLAYER_SPEED
        # Simple diagonal normalization
        if dx != 0 and dy != 0:
            dx *= 0.7071
            dy *= 0.7071
        self.player.center_x += dx
        self.player.center_y += dy

        # Keep player on screen / ground limits
        if self.player.left < 10:
            self.player.left = 10
        if self.player.right > SCREEN_WIDTH - 10:
            self.player.right = SCREEN_WIDTH - 10
        if self.player.bottom < 62:
            self.player.bottom = 62
        if self.player.top > SCREEN_HEIGHT - 10:
            self.player.top = SCREEN_HEIGHT - 10

        # Update bullets and particles
        self.player_bullets.update()
        self.enemy_bullets.update()
        self.particles.update()

        # Remove off-screen bullets
        for bullet in list(self.player_bullets) + list(self.enemy_bullets):
            if bullet.right < 0 or bullet.left > SCREEN_WIDTH or bullet.top < 0 or bullet.bottom > SCREEN_HEIGHT:
                bullet.remove_from_sprite_lists()

        # Boss AI behavior depends on stage and phase
        if self.boss and self.boss in self.boss_list:
            self._boss_ai(self.boss, delta_time)

        # Collisions: player bullets hit boss
        if self.boss and self.boss in self.boss_list:
            hits = arcade.check_for_collision_with_list(self.boss, self.player_bullets)
            for b in hits:
                b.remove_from_sprite_lists()
                self.boss.health -= 3  # bullet damage
                self._spawn_hit_particles(self.boss.center_x, self.boss.center_y)
                self.score += 10

            if self.boss.health <= 0:
                # Boss defeated
                self._spawn_explosion(self.boss.center_x, self.boss.center_y)
                self.boss.remove_from_sprite_lists()
                self.score += 200
                # If there is another stage, move to StoryView for next stage, else show win.
                if self.stage < BOSS_COUNT:
                    next_stage = StoryView(stage=self.stage + 1)
                    self.window.show_view(next_stage)
                else:
                    self._end_game(win=True)
                return

        # Boss bullets hit player
        hits = arcade.check_for_collision_with_list(self.player, self.enemy_bullets)
        for b in hits:
            b.remove_from_sprite_lists()
            self.player.health -= 1
            self._spawn_hit_particles(self.player.center_x, self.player.center_y)
            if self.player.health <= 0:
                self._end_game(win=False)
                return

        # Enemy contact (boss touching player)
        if self.boss and self.boss in self.boss_list:
            if arcade.check_for_collision(self.player, self.boss):
                # contact damage + small knockback
                self.player.health -= 1
                # nudge player away
                angle = math.atan2(self.player.center_y - self.boss.center_y,
                                   self.player.center_x - self.boss.center_x)
                self.player.center_x += math.cos(angle) * 24
                self.player.center_y += math.sin(angle) * 24
                self._spawn_hit_particles(self.player.center_x, self.player.center_y)
                if self.player.health <= 0:
                    self._end_game(win=False)
                    return

    def _boss_ai(self, boss: Boss, delta: float):
        boss.phase_timer += delta
        # Stage 1: slow move left-right and fire aimed shots
        if boss.stage == 1:
            # horizontal patrol
            patrol_speed = 1.2
            boss.center_x += math.sin(boss.phase_timer * 0.9) * patrol_speed
            # every 1.0 seconds, fire an aimed bullet
            if boss.phase_timer > 1.0:
                boss.phase_timer = 0.0
                self._boss_shoot_aimed(boss)
        else:
            # Stage 2: more aggressive - dash + burst shots
            # Move towards a position above the player sometimes
            # Every 1.8s do a burst of fan bullets; every 3s do a dash
            if int(boss.phase_timer * 10) % 18 == 0 and boss.phase_timer % 0.1 < delta:
                self._boss_shoot_fan(boss, count=7)
            # occasional dash toward player
            if boss.phase_timer > 3.0:
                boss.phase_timer = 0.0
                self._boss_dash_toward_player(boss)

    def _boss_shoot_aimed(self, boss: Boss):
        # Aim at player
        dx = self.player.center_x - boss.center_x
        dy = self.player.center_y - boss.center_y
        dist = math.hypot(dx, dy) or 1
        ndx, ndy = dx / dist, dy / dist
        b = Bullet(boss.center_x, boss.center_y, ndx, ndy, color=arcade.color.PURPLE, speed=BULLET_SPEED * 0.65, owner="boss")
        self.enemy_bullets.append(b)

    def _boss_shoot_fan(self, boss: Boss, count=5):
        # Fan spread centered toward player
        dx = self.player.center_x - boss.center_x
        dy = self.player.center_y - boss.center_y
        angle = math.atan2(dy, dx)
        spread = math.radians(40)
        for i in range(count):
            a = angle + spread * (i / (count - 1) - 0.5)
            bdx = math.cos(a)
            bdy = math.sin(a)
            b = Bullet(boss.center_x, boss.center_y, bdx, bdy, color=arcade.color.LIGHT_PURPLE, speed=BULLET_SPEED * 0.7, owner="boss")
            self.enemy_bullets.append(b)

    def _boss_dash_toward_player(self, boss: Boss):
        # dash movement: teleport-ish with particle trail
        # linear interpolation to player position
        tx = self.player.center_x + random.uniform(-40, 40)
        ty = min(max(self.player.center_y + 40, SCREEN_HEIGHT // 2), SCREEN_HEIGHT - 60)
        # create particles along the path
        for i in range(12):
            t = i / 12
            x = boss.center_x * (1 - t) + tx * t + random.uniform(-6, 6)
            y = boss.center_y * (1 - t) + ty * t + random.uniform(-6, 6)
            self._spawn_trail_particle(x, y)
        boss.center_x = tx
        boss.center_y = ty
        # after dash, fire a quick fan
        self._boss_shoot_fan(boss, count=9)

    def _spawn_hit_particles(self, x, y, count=8):
        for _ in range(count):
            p = arcade.SpriteCircle(3, arcade.color.GOLD)
            p.center_x = x + random.uniform(-6, 6)
            p.center_y = y + random.uniform(-6, 6)
            p.change_x = random.uniform(-2, 2)
            p.change_y = random.uniform(-2, 2)
            # attach life attribute and simple decay in update
            p.life = 0.4 + random.random() * 0.4
            self.particles.append(p)

    def _spawn_trail_particle(self, x, y):
        p = arcade.SpriteCircle(4, arcade.color.LIGHT_GRAY)
        p.center_x = x
        p.center_y = y
        p.change_x = random.uniform(-0.6, 0.6)
        p.change_y = random.uniform(-0.6, 0.6)
        p.life = 0.5
        self.particles.append(p)

    def _spawn_explosion(self, x, y, count=24):
        for _ in range(count):
            p = arcade.SpriteCircle(4, arcade.color.ORANGE)
            p.center_x = x + random.uniform(-12, 12)
            p.center_y = y + random.uniform(-12, 12)
            p.change_x = random.uniform(-4, 4)
            p.change_y = random.uniform(-4, 4)
            p.life = 0.6 + random.random() * 0.6
            self.particles.append(p)

    def on_key_press(self, key, modifiers):
        if key in (arcade.key.W, arcade.key.UP):
            self.up = True
        elif key in (arcade.key.S, arcade.key.DOWN):
            self.down = True
        elif key in (arcade.key.A, arcade.key.LEFT):
            self.left = True
        elif key in (arcade.key.D, arcade.key.RIGHT):
            self.right = True
        elif key == arcade.key.SPACE:
            # shoot if ready
            if self.shoot_timer.ready():
                # shoot straight upward-ish from player
                dx, dy = 0, 1
                b = Bullet(self.player.center_x, self.player.center_y + 8, dx, dy, color=arcade.color.YELLOW, speed=BULLET_SPEED, owner="player")
                self.player_bullets.append(b)
                self.shoot_timer.trigger()
        elif key == arcade.key.Z:
            # melee attack: check boss in range
            if self.melee_timer.ready():
                self.melee_timer.trigger()
                # visual effect
                self._spawn_hit_particles(self.player.center_x + 16 * (1 if self.right else -1), self.player.center_y)
                # do AOE in front
                if self.boss and self.boss in self.boss_list:
                    dist = math.hypot(self.boss.center_x - self.player.center_x, self.boss.center_y - self.player.center_y)
                    if dist <= MELEE_RANGE + self.boss.width / 2:
                        self.boss.health -= MELEE_DAMAGE
                        self._spawn_hit_particles(self.boss.center_x, self.boss.center_y)
                        self.score += 5
        elif key == arcade.key.ESCAPE:
            # Back to menu immediately
            menu = MenuView()
            self.window.show_view(menu)
        elif key == arcade.key.R:
            # restart stage quickly
            self.setup()
        elif key == arcade.key.M:
            menu = MenuView()
            self.window.show_view(menu)

    def on_key_release(self, key, modifiers):
        if key in (arcade.key.W, arcade.key.UP):
            self.up = False
        elif key in (arcade.key.S, arcade.key.DOWN):
            self.down = False
        elif key in (arcade.key.A, arcade.key.LEFT):
            self.left = False
        elif key in (arcade.key.D, arcade.key.RIGHT):
            self.right = False

    def _end_game(self, win: bool):
        self.game_over = True
        self.win = win
        # Delay a little then show GameOverView for a nicer presentation
        go = GameOverView(final_score=self.score, win=win)
        self.window.show_view(go)

    def update(self, delta_time: float = 1 / 60):
        """Arcade calls update or on_update depending on setup; we keep it for completeness."""
        self.on_update(delta_time)

    # Provide compatibility for particle lifetimes by hooking into normal update
    def on_update(self, delta_time: float):
        # For backward compatibility, call the main logic method
        # (We already used on_update above, but ensure both work)
        # But to avoid duplicating, do nothing here; main update is above in on_update definition.
        pass


# Note: above we defined on_update twice by mistake if using the same name.
# To keep the code correct we will rebind GameView.on_update to the primary one.
# (This small fix keeps the single-file structure simple.)
def _gameview_on_update(self, delta_time: float):
    # call the game loop function implemented earlier
    # we purposely placed the main loop function under the other name; now run it
    # to avoid duplication issues we reimplement the actual logic here:
    # Update timers
    self.shoot_timer.update(delta_time)
    self.melee_timer.update(delta_time)
    if self.intro_timer > 0:
        self.intro_timer -= delta_time
        return  # freeze gameplay briefly for story feel

    if self.game_over:
        return

    # Update movement
    dx = dy = 0
    if self.up:
        dy += PLAYER_SPEED
    if self.down:
        dy -= PLAYER_SPEED
    if self.left:
        dx -= PLAYER_SPEED
    if self.right:
        dx += PLAYER_SPEED
    if dx != 0 and dy != 0:
        dx *= 0.7071
        dy *= 0.7071
    self.player.center_x += dx
    self.player.center_y += dy

    # Keep player onscreen
    if self.player.left < 10:
        self.player.left = 10
    if self.player.right > SCREEN_WIDTH - 10:
        self.player.right = SCREEN_WIDTH - 10
    if self.player.bottom < 62:
        self.player.bottom = 62
    if self.player.top > SCREEN_HEIGHT - 10:
        self.player.top = SCREEN_HEIGHT - 10

    # Update bullets & particles
    self.player_bullets.update()
    self.enemy_bullets.update()
    # Particles simple life decay
    for p in list(self.particles):
        if hasattr(p, "life"):
            p.life -= delta_time
            p.center_x += getattr(p, "change_x", 0)
            p.center_y += getattr(p, "change_y", 0)
            if p.life <= 0:
                p.remove_from_sprite_lists()

    # Remove off-screen bullets
    for bullet in list(self.player_bullets) + list(self.enemy_bullets):
        if bullet.right < 0 or bullet.left > SCREEN_WIDTH or bullet.top < 0 or bullet.bottom > SCREEN_HEIGHT:
            bullet.remove_from_sprite_lists()

    # Boss AI
    if self.boss and self.boss in self.boss_list:
        self._boss_ai(self.boss, delta_time)

    # Collisions: player bullets hit boss
    if self.boss and self.boss in self.boss_list:
        hits = arcade.check_for_collision_with_list(self.boss, self.player_bullets)
        for b in hits:
            b.remove_from_sprite_lists()
            self.boss.health -= 3
            self._spawn_hit_particles(self.boss.center_x, self.boss.center_y)
            self.score += 10
        if self.boss.health <= 0:
            self._spawn_explosion(self.boss.center_x, self.boss.center_y)
            self.boss.remove_from_sprite_lists()
            self.score += 200
            if self.stage < BOSS_COUNT:
                next_stage = StoryView(stage=self.stage + 1)
                self.window.show_view(next_stage)
            else:
                self._end_game(win=True)
            return

    # Enemy bullets hit player
    hits = arcade.check_for_collision_with_list(self.player, self.enemy_bullets)
    for b in hits:
        b.remove_from_sprite_lists()
        self.player.health -= 1
        self._spawn_hit_particles(self.player.center_x, self.player.center_y)
        if self.player.health <= 0:
            self._end_game(win=False)
            return

    # Boss touching player
    if self.boss and self.boss in self.boss_list:
        if arcade.check_for_collision(self.player, self.boss):
            self.player.health -= 1
            angle = math.atan2(self.player.center_y - self.boss.center_y,
                               self.player.center_x - self.boss.center_x)
            self.player.center_x += math.cos(angle) * 24
            self.player.center_y += math.sin(angle) * 24
            self._spawn_hit_particles(self.player.center_x, self.player.center_y)
            if self.player.health <= 0:
                self._end_game(win=False)
                return


# Bind the correct on_update method
GameView.on_update = _gameview_on_update


class GameOverView(arcade.View):
    """Final screen showing win / loss and options."""

    def __init__(self, final_score: int, win: bool):
        super().__init__()
        self.final_score = final_score
        self.win = win

    def on_show(self):
        arcade.set_background_color(BG_COLOR)

    def on_draw(self):
        self.clear()
        title = "VICTORY!" if self.win else "DEFEAT"
        color = arcade.color.LIGHT_GREEN if self.win else arcade.color.SALMON
        arcade.draw_text(title, SCREEN_WIDTH // 2, SCREEN_HEIGHT * 0.64, color, 40, anchor_x="center")
        arcade.draw_text(f"Final Score: {self.final_score}", SCREEN_WIDTH // 2, SCREEN_HEIGHT * 0.52, arcade.color.WHITE, 18, anchor_x="center")
        arcade.draw_text("Press R to Replay", SCREEN_WIDTH // 2, SCREEN_HEIGHT * 0.38, arcade.color.LIGHT_GRAY, 16, anchor_x="center")
        arcade.draw_text("Press M for Menu   ESC to Quit", SCREEN_WIDTH // 2, SCREEN_HEIGHT * 0.32, arcade.color.LIGHT_GRAY, 14, anchor_x="center")

    def on_key_press(self, key, modifiers):
        if key == arcade.key.R:
            # Restart from stage 1
            game = GameView(stage=1)
            game.setup()
            self.window.show_view(game)
        elif key == arcade.key.M:
            menu = MenuView()
            self.window.show_view(menu)
        elif key == arcade.key.ESCAPE:
            arcade.close_window()


def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    menu = MenuView()
    window.show_view(menu)
    arcade.run()

if __name__ == "__main__":
    main()

