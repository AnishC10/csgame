import arcade
import math
import random
import time
import os


# ---------------------------------------------------------------------------
# Window / arena
#  - Global constants that define the game window and playable arena.
#  - Changing these affects layout, not core logic.
# ---------------------------------------------------------------------------
SCREEN_WIDTH, SCREEN_HEIGHT = 1000, 640
SCREEN_TITLE = "StoryQuest+++"
ARENA_MARGIN, GROUND_Y, GRID_SPACING = 48, 56, 32

# ---------------------------------------------------------------------------
# Player base stats
#  - These are the "default" values before perks modify them.
#  - Player object reads these to initialize its stats.
# ---------------------------------------------------------------------------
PLAYER_RADIUS, PLAYER_MAX_HP = 19, 60
PLAYER_BASE_SPEED, PLAYER_BASE_DASH_SPEED = 4.0, 12.0
PLAYER_DASH_TIME, PLAYER_DASH_IFRAME, PLAYER_DASH_CD = 0.18, 0.36, 1.2
MELEE_CD, MELEE_RANGE, MELEE_DAMAGE = 0.5, 46, 7

# ---------------------------------------------------------------------------
# Weapon base stats
#  - Define projectile behavior and firing pace.
#  - Perks later modify these values on the Player instance.
# ---------------------------------------------------------------------------
BASE_BULLET_SPEED, BASE_FIRE_CD, BASE_DAMAGE = 11.5, 0.26, 3
SHOTGUN_SPREAD, SHOTGUN_PELLETS = math.radians(6), 4

# ---------------------------------------------------------------------------
# XP / Progression
#  - Controls leveling pace and wave rewards.
#  - Used by GameView to handle XP gain and level-ups.
# ---------------------------------------------------------------------------
XP_PER_WAVE_CLEAR, XP_ORB_VALUE, XP_TO_LEVEL_BASE = 6, 1, 5
TOTAL_WAVES = 5

# ---------------------------------------------------------------------------
# Colors
#  - Centralized palette for UI, backgrounds, effects, etc.
#  - Used across rendering functions.
# ---------------------------------------------------------------------------
BG_TOP, BG_BOTTOM = (26, 33, 53), (39, 48, 77)
GRID_COLOR, UI_COLOR, TEXT_SHADOW = (255, 255, 255, 18), arcade.color.ALMOND, (0, 0, 0, 180)
DANGER_FILL, DANGER_EDGE = (255, 140, 0, 40), arcade.color.YELLOW_ORANGE
BULLET_COLOR_PLAYER, BULLET_COLOR_ENEMY = arcade.color.BANANA_YELLOW, arcade.color.LIGHT_SALMON
PLAYER_BODY, PLAYER_OUT = arcade.color.CYAN, arcade.color.WHITE
CHASER_BODY, SHOOTR_BODY, BOMBER_BODY = arcade.color.DARK_ORANGE, arcade.color.DARK_CERULEAN, arcade.color.BRICK_RED
ELITE_BODY, ENEMY_OUT = arcade.color.LIGHT_RED_OCHRE, arcade.color.WHITE
BOSS_BODY, BOSS_OUT = arcade.color.ORANGE_RED, arcade.color.WHITE
HP_BAR_BACK, HP_BAR_GREEN = (0, 0, 0, 160), arcade.color.SPRING_BUD
HP_BAR_RED, HP_BAR_YELLOW = arcade.color.PASTEL_RED, arcade.color.GOLD

# ---------------------------------------------------------------------------
# Asset path helper
#  - Centralizes where images are loaded from.
#  - If you move the "photos" folder, update ASSET_DIR only.
# ---------------------------------------------------------------------------
ASSET_DIR = os.path.join(os.path.dirname(__file__), "photos")


def asset(name: str) -> str:
    """Return absolute path to an image in the photos folder."""
    return os.path.join(ASSET_DIR, name)


# Small helpers for math / coord handling

# snap() forces coordinates to integers for cleaner rendering (no subpixel jitter).
snap = lambda v: float(int(round(v)))


def dist(x1, y1, x2, y2):
    """Euclidean distance helper, used for XP magnet, melee range, etc."""
    return math.hypot(x2 - x1, y2 - y1)


class Timer:
    """
    Generic cooldown timer.
    - Used for shooting, dashing, melee, etc.
    - Encapsulates 'is this action ready yet?' logic.
    """
    def __init__(self, cd=0.0):
        self.cd, self.t = cd, 0.0

    def ready(self):
        """Return True when cooldown has expired."""
        return self.t <= 0.0

    def trigger(self):
        """Start / reset the cooldown."""
        self.t = self.cd

    def update(self, dt):
        """Tick the timer down each frame."""
        self.t = max(0, self.t - dt) if self.t > 0 else 0


# ---------------------------------------------------------------------------
# Perks system
#  - Each Perk modifies player stats/flags when chosen.
#  - GameView periodically offers perk choices on level up.
# ---------------------------------------------------------------------------
class Perk:
    def __init__(self, name, desc, apply_fn):
        # apply_fn is a function that directly mutates the Player object
        self.name, self.desc, self.apply = name, desc, apply_fn


def perk_pool():
    """Return the full list of possible perks (pool to sample from)."""
    return [
        Perk("Damage +2", "Increase bullet damage by 2.", lambda p: setattr(p, "damage", p.damage + 2)),
        Perk("Fire Rate +20%", "Shoot faster.", lambda p: setattr(p, "fire_cd", p.fire_cd * 0.8)),
        Perk("Spread Shot", "Shotgun pellets in a cone.", lambda p: setattr(p, "has_spread", True)),
        Perk("Dash Mastery", "Dash CD -25%, +20% i-frames.",
             lambda p: (setattr(p, "dash_cd", p.dash_cd * 0.75),
                        setattr(p, "dash_iframe", p.dash_iframe * 1.2))),
        Perk("Crit 15%", "15% crit chance (2x dmg).",
             lambda p: setattr(p, "crit_chance", min(1.0, p.crit_chance + 0.15))),
        Perk("Burn", "Hits ignite for DoT.", lambda p: setattr(p, "burn_on_hit", True)),
        Perk("Slow", "Hits slow briefly.", lambda p: setattr(p, "slow_on_hit", True)),
        Perk("Regen", "Heal 1 HP every 8s out of combat.", lambda p: setattr(p, "regen_on", True)),
        Perk("Magnet", "Bigger XP pickup radius.",
             lambda p: setattr(p, "magnet_radius", p.magnet_radius + 40)),
        Perk("Pierce", "Bullets pierce one extra target.",
             lambda p: setattr(p, "pierce", p.pierce + 1))
    ]


# ---------------------------------------------------------------------------
# Sprites USING IMAGES
#  - Player, enemies, boss, bullets, XP orbs, pickups are all Sprites.
#  - GameView uses these lists to update and render the world.
# ---------------------------------------------------------------------------
class Player(arcade.Sprite):
    """
    Main controllable character.

    Holds:
    - Core combat stats (hp, damage, fire_cd, bullet_speed, pierce, etc.).
    - Perk-related flags (burn_on_hit, slow_on_hit, regen_on, magnet_radius).
    - Movement/dash state (dashing, iframes, dash_cd).
    - Combo state for score multiplier.
    """
    def __init__(self):
        # 1/10th of previous 0.25 scale
        super().__init__(asset("Mattguitar(main).jpg"), scale=0.135)
        self.hp_max, self.hp, self.speed = PLAYER_MAX_HP, PLAYER_MAX_HP, PLAYER_BASE_SPEED
        self.damage, self.fire_cd, self.bullet_speed, self.pierce = BASE_DAMAGE, BASE_FIRE_CD, BASE_BULLET_SPEED, 0
        self.has_spread, self.crit_chance, self.burn_on_hit = False, 0.0, False
        self.slow_on_hit, self.regen_on, self.regen_timer, self.magnet_radius = False, False, 8.0, 90
        self.aim_x, self.aim_y = SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2
        self.dash_speed, self.dash_time, self.dash_iframe = (
            PLAYER_BASE_DASH_SPEED, PLAYER_DASH_TIME, PLAYER_DASH_IFRAME
        )
        self.dashing, self.iframes, self.dash_cd, self.shield = 0.0, 0.0, PLAYER_DASH_CD, 0
        self.combo, self.combo_t = 1, 0.0

    def facing(self):
        """Return normalized direction vector from player to aim position (mouse)."""
        dx, dy = self.aim_x - self.center_x, self.aim_y - self.center_y
        d = math.hypot(dx, dy) or 1.0
        return dx / d, dy / d

    def update_timers(self, dt):
        """Handle dash/iframe timers, combo timer, and regen logic."""
        if self.dashing > 0:
            self.dashing -= dt
        if self.iframes > 0:
            self.iframes -= dt
        if self.combo_t > 0:
            self.combo_t -= dt
            if self.combo_t <= 0:
                self.combo, self.combo_t = 1, 0.0
        if self.regen_on:
            self.regen_timer -= dt
            if self.regen_timer <= 0 and self.hp < self.hp_max:
                self.hp, self.regen_timer = self.hp + 1, 8.0

    def take_hit(self, dmg):
        """
        Process damage taken:
        - Ignore hit if currently in i-frames.
        - Consume shield if available.
        - Otherwise, reduce HP and reset combo.
        """
        if self.iframes > 0:
            return False
        if self.shield > 0:
            self.shield -= 1
            return True
        self.hp, self.combo, self.combo_t = self.hp - dmg, 1, 0
        return True


class Enemy(arcade.Sprite):
    """
    Base class for all enemy types.
    - Provides HP and status effects (burn/slow).
    - Movement behavior is implemented in subclasses.
    """
    def __init__(self, texture_name: str, scale: float):
        super().__init__(asset(texture_name), scale=0.08)
        self.hp = self.max_hp = 1
        self.slow_t = self.burn_t = self.burn_tick = 0.0
        self.wander_phase = random.uniform(0, math.tau)

    def apply_status(self, burn, slow):
        """Apply or extend burn/slow status durations."""
        if burn:
            self.burn_t = max(self.burn_t, 2.0)
        if slow:
            self.slow_t = max(self.slow_t, 1.2)

    def update_status(self, dt, apply_burn_damage):
        """
        Tick status timers.
        - Burn periodically calls apply_burn_damage(1) to reduce HP.
        """
        if self.slow_t > 0:
            self.slow_t -= dt
        if self.burn_t > 0:
            self.burn_t -= dt
            self.burn_tick -= dt
            if self.burn_tick <= 0:
                self.burn_tick = 0.5
                apply_burn_damage(1)


class Chaser(Enemy):
    """Enemy that directly chases the player, with some wander wiggle."""
    def __init__(self, x, y, elite=False):
        tex = "enemy1.png"
        # smaller than before
        scale = 0.1 if elite else 0.05
        super().__init__(tex, scale)
        self.center_x, self.center_y = x, y
        self.hp = self.max_hp = (10 if elite else 5)
        self.elite = elite

    def step(self, player, dt):
        """Chase the player with some sine-based wandering."""
        self.wander_phase += dt
        wx = math.cos(self.wander_phase * 2.0) * (0.5 if self.slow_t <= 0 else 0.25)
        wy = math.sin(self.wander_phase * 1.6) * (0.4 if self.slow_t <= 0 else 0.2)
        dx, dy = player.center_x - self.center_x, player.center_y - self.center_y
        d = max(1.0, math.hypot(dx, dy))
        seek = (2.6 if self.slow_t <= 0 else 1.4) * (1.2 if self.elite else 1)
        self.center_x = snap(self.center_x + (dx / d) * seek + wx)
        self.center_y = snap(self.center_y + (dy / d) * seek + wy)


class Shooter(Enemy):
    """Enemy that patrols in a pattern and shoots (handled elsewhere)."""
    def __init__(self, x, y):
        super().__init__("enemy2.png", scale=0.08)
        self.center_x, self.center_y, self.t = x, y, random.random() * 5
        self.hp = self.max_hp = 12

    def step(self, player, dt):
        """Oscillating patrol motion; aiming handled when boss/enemy fires."""
        self.t += dt
        patrol = 1.8 if self.slow_t <= 0 else 0.9
        self.center_x = snap(self.center_x + math.sin(self.t * 1.4) * patrol)
        self.center_y = snap(self.center_y + math.cos(self.t * 0.9) * 0.4)


class Bomber(Enemy):
    """Enemy that falls downward and telegraphs ring explosions."""
    def __init__(self, x, y):
        super().__init__("enemy3.png", scale=0.08)
        self.center_x, self.center_y = x, y
        self.hp = self.max_hp = 10
        self.telegraphs, self.t = [], 0.0

    def step(self, player, dt):
        """Fall down plus slight horizontal wiggle; explosions handled in GameView."""
        self.t += dt
        fall = 1.1 if self.slow_t <= 0 else 0.6
        self.center_y = snap(self.center_y - fall)
        self.center_x = snap(self.center_x + math.sin(self.t * 1.3) * (0.6 if self.slow_t <= 0 else 0.3))


class Bullet(arcade.SpriteCircle):
    """
    Generic bullet.
    - owner = "player" or "enemy" (used for collision routing).
    - pierce_left controls how many extra targets it can pass through.
    """
    def __init__(self, x, y, dx, dy, speed, color, owner, radius=3, pierce_left=0):
        super().__init__(radius, color)
        self.center_x, self.center_y = x, y
        self.change_x, self.change_y = dx * speed, dy * speed
        self.owner, self.pierce_left = owner, pierce_left


class XPOrb(arcade.SpriteCircle):
    """
    XP pickup.
    - Spawned from dead enemies.
    - Initially drifts, then can be pulled by magnet effect.
    """
    def __init__(self, x, y):
        super().__init__(6, arcade.color.SPRING_BUD)
        self.center_x, self.center_y = x, y
        self.vx, self.vy = random.uniform(-0.8, 0.8), random.uniform(0.6, 1.2)

    def update(self, delta_time=0.0, *args, **kwargs):
        self.center_x, self.center_y = self.center_x + self.vx, self.center_y + self.vy
        self.vx, self.vy = self.vx * 0.98, self.vy * 0.98 - 0.02


class Pickup(arcade.SpriteCircle):
    """
    Health/shield pickup.
    - kind = "health" or "shield".
    - Slowly falls with some drag.
    """
    def __init__(self, x, y, kind):
        super().__init__(7, arcade.color.SKY_BLUE if kind == "shield" else arcade.color.SPRING_GREEN)
        self.center_x, self.center_y, self.kind, self.vy = x, y, kind, 1.2

    def update(self, delta_time=0.0, *args, **kwargs):
        self.center_y, self.vy = self.center_y + self.vy, self.vy * 0.98 - 0.02


class Boss(arcade.Sprite):
    """
    Boss enemy.
    - Has phases and attacks controlled by GameView._boss_logic().
    - 'giant' toggles a different pattern for Level 3.
    """
    def __init__(self, giant=False):
        tex = "boss.png"
        # smaller than before
        scale = 0.25 if giant else 0.15
        super().__init__(asset(tex), scale=scale)

        self.center_x, self.center_y = SCREEN_WIDTH / 2, SCREEN_HEIGHT - 150
        self.max_hp = 3000 if giant else 2400
        self.hp, self.phase_timer, self.telegraphs, self.phase = self.max_hp, 0.0, [], 1
        self.giant = giant

    def hp_norm(self):
        """Return HP ratio 0..1 for boss health bar."""
        return max(0.0, self.hp / self.max_hp)


# ---------------------------------------------------------------------------
# Text helpers (for UI / HUD)
# ---------------------------------------------------------------------------
def make_text(txt, size, color, ax="left", ay="baseline"):
    """Wrapper around arcade.Text that remembers original color for shadow rendering."""
    t = arcade.Text(txt, 0, 0, color, size, anchor_x=ax, anchor_y=ay)
    t._orig_color = color
    return t


def draw_text_shadowed(text_obj, x, y, sdx=1, sdy=-1):
    """
    Draw text with a simple shadow.
    - Moves text slightly for the shadow, then restores original position/color.
    """
    text_obj.position = (x + sdx, y + sdy)
    text_obj.color = TEXT_SHADOW
    text_obj.draw()
    text_obj.position = (x, y)
    text_obj.color = text_obj._orig_color
    text_obj.draw()


def draw_lrbt_rect_filled_center(cx, cy, w, h, color):
    """Helper for drawing a filled rect centered at (cx, cy)."""
    arcade.draw_lrbt_rectangle_filled(cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2, color)


def draw_lrbt_rect_outline_center(cx, cy, w, h, color, line_width=1):
    """Helper for drawing an outlined rect centered at (cx, cy)."""
    arcade.draw_lrbt_rectangle_outline(cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2, color, line_width)


def draw_health_bar(x, y, width, height, hp, hp_max, edge_color=arcade.color.WHITE):
    """
    Generic health bar renderer.
    - Used for player, normal enemies, and boss bar background.
    """
    if hp_max <= 0:
        return
    ratio = max(0.0, min(1.0, hp / hp_max))
    draw_lrbt_rect_filled_center(x, y, width, height, HP_BAR_BACK)
    if ratio > 0:
        l = x - width / 2
        arcade.draw_lrbt_rectangle_filled(
            l, l + width * ratio,
            y - (height - 2) / 2, y + (height - 2) / 2,
            HP_BAR_GREEN if ratio > 0.6 else HP_BAR_YELLOW if ratio > 0.3 else HP_BAR_RED
        )
    draw_lrbt_rect_outline_center(x, y, width, height, edge_color, 1)


# ---------------------------------------------------------------------------
# Views
# - Each View is a separate screen/state (Menu, Perk selection, Game Over, Game).
# - arcade.Window switches between these.
# ---------------------------------------------------------------------------
class MenuView(arcade.View):
    """
    Main menu screen.
    - Draws title, controls, and waits for ENTER or ESCAPE.
    """
    def __init__(self):
        super().__init__()
        self.title = make_text("STORYQUEST+++ (3 LEVELS)", 40, arcade.color.GOLD, "center")
        self.subtitle = make_text("L1: Reach 90 score • L2: Reach 90 score • L3: Giant Boss", 16,
                                  arcade.color.LIGHT_GRAY, "center")
        self.controls = make_text("WASD: Move • SPACE/Click: Shoot • Z: Melee • LSHIFT: Dash", 12,
                                  arcade.color.WHITE, "center")
        self.start = make_text("Press ENTER to Start", 22, arcade.color.LIGHT_GREEN, "center")

    def on_show(self):
        arcade.set_background_color(BG_BOTTOM)

    def on_draw(self):
        """Render menu background and text."""
        self.clear()
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT, BG_BOTTOM)
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, SCREEN_HEIGHT * 0.55, SCREEN_HEIGHT, BG_TOP)
        for x in range(ARENA_MARGIN, SCREEN_WIDTH - ARENA_MARGIN + 1, GRID_SPACING):
            arcade.draw_line(x, GROUND_Y, x, SCREEN_HEIGHT - ARENA_MARGIN, GRID_COLOR, 1)
        for y in range(GROUND_Y, SCREEN_HEIGHT - ARENA_MARGIN + 1, GRID_SPACING):
            arcade.draw_line(ARENA_MARGIN, y, SCREEN_WIDTH - ARENA_MARGIN, y, GRID_COLOR, 1)
        draw_text_shadowed(self.title, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.68)
        draw_text_shadowed(self.subtitle, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.60)
        draw_text_shadowed(self.controls, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.54)
        draw_text_shadowed(self.start, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.30)

    def on_key_press(self, key, modifiers):
        """Start game on ENTER, quit on ESC."""
        if key in (arcade.key.ENTER, arcade.key.RETURN):
            gv = GameView(1)
            gv.setup()
            self.window.show_view(gv)
        elif key == arcade.key.ESCAPE:
            arcade.close_window()


class PerkDraftView(arcade.View):
    """
    Perk selection screen after level up.
    - Pauses the game logic and lets player choose one perk out of 3.
    """
    def __init__(self, game, options):
        super().__init__()
        self.game, self.options, self.selected = game, options, 0
        self.title = make_text("Choose a Perk", 28, arcade.color.GOLD, "center")
        self.hint = make_text("↑/↓ to select • ENTER to confirm", 12, arcade.color.WHITE, "center")

    def on_show(self):
        arcade.set_background_color(BG_BOTTOM)

    def on_draw(self):
        """Draw perk list with highlight on currently selected option."""
        self.clear()
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT, BG_BOTTOM)
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, SCREEN_HEIGHT * 0.55, SCREEN_HEIGHT, BG_TOP)
        draw_text_shadowed(self.title, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.72)
        for i, perk in enumerate(self.options):
            y = SCREEN_HEIGHT * 0.52 - i * 84
            col = arcade.color.LIGHT_GREEN if i == self.selected else arcade.color.LIGHT_GRAY
            arcade.draw_lrbt_rectangle_filled(SCREEN_WIDTH / 2 - 340, SCREEN_WIDTH / 2 + 340,
                                              y - 32, y + 32, (0, 0, 0, 140))
            draw_text_shadowed(make_text(perk.name, 18, col), SCREEN_WIDTH / 2 - 320, y + 12)
            draw_text_shadowed(make_text(perk.desc, 12, arcade.color.WHITE), SCREEN_WIDTH / 2 - 320, y - 12)
        draw_text_shadowed(self.hint, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.20)

    def on_key_press(self, key, modifiers):
        """Move selection up/down and confirm with ENTER."""
        if key in (arcade.key.UP, arcade.key.W):
            self.selected = (self.selected - 1) % len(self.options)
        elif key in (arcade.key.DOWN, arcade.key.S):
            self.selected = (self.selected + 1) % len(self.options)
        elif key in (arcade.key.ENTER, arcade.key.RETURN):
            # Apply selected perk directly to persisted player instance
            self.options[self.selected].apply(self.game.player)
            self.window.show_view(self.game)


class GameOverView(arcade.View):
    """
    Game over screen.
    - Shows victory/defeat, score, time, and basic restart/menu options.
    """
    def __init__(self, score, win, seconds, game_level):
        super().__init__()
        self.score, self.win, self.seconds, self.game_level = score, win, seconds, game_level
        self.title = make_text("VICTORY!" if self.win else "DEFEAT", 40,
                               arcade.color.LIGHT_GREEN if self.win else arcade.color.SALMON, "center")
        self.hint = make_text("R: Replay • M: Menu • ESC: Quit", 16, arcade.color.LIGHT_GRAY, "center")

    def on_show(self):
        arcade.set_background_color(BG_BOTTOM)

    def on_draw(self):
        """Render simple summary of the run."""
        self.clear()
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT, BG_BOTTOM)
        draw_text_shadowed(self.title, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.64)
        draw_text_shadowed(
            make_text(f"Level {self.game_level} • Score: {self.score}", 18, arcade.color.WHITE, "center"),
            SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.54)
        draw_text_shadowed(make_text(f"Time: {int(self.seconds)}s", 16, arcade.color.WHITE, "center"),
                           SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.48)
        draw_text_shadowed(self.hint, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.34)

    def on_key_press(self, key, modifiers):
        """Handle restart, menu, or quit from game over screen."""
        if key == arcade.key.R:
            # Reset the persistent player so a fresh one is created on restart
            self.window.player_persistent = None

            g = GameView(1)
            g.setup()
            self.window.show_view(g)
        elif key == arcade.key.M:
            # Also reset the persistent player when returning to the main menu
            self.window.player_persistent = None
            self.window.show_view(MenuView())
        elif key == arcade.key.ESCAPE:
            arcade.close_window()


# ---------------------------------------------------------------------------
# Game View
#  - Core gameplay loop happens here:
#    * spawning waves / bosses
#    * updating player/enemies/bullets
#    * handling collisions, XP, perks, level transitions
#    * drawing background, arena, HUD
# ---------------------------------------------------------------------------
class GameView(arcade.View):
    def __init__(self, game_level=1):
        super().__init__()
        self.game_level = game_level
        self.shake_t = self.flash_t = 0.0

        # Background sprite + list for Arcade 3.x
        self.bg_sprite = None
        self.bg_list = arcade.SpriteList()

        # Sprite lists for all active entities in the scene
        self.player = None
        self.player_list = arcade.SpriteList()
        self.enemy_list = arcade.SpriteList()
        self.boss_list = arcade.SpriteList()
        self.bullets = arcade.SpriteList()
        self.enemy_bullets = arcade.SpriteList()
        self.xp_orbs = arcade.SpriteList()
        self.pickups = arcade.SpriteList()
        self.particles = arcade.SpriteList()

        # Input state flags for WASD
        self.up = self.down = self.left = self.right = 0

        # Shooting / timers
        self.shoot_hold = False
        self.fire_timer = Timer(BASE_FIRE_CD)
        self.dash_timer = Timer(PLAYER_DASH_CD)
        self.melee_timer = Timer(MELEE_CD)

        # Wave / progression state
        self.wave = 1
        self.wave_clear_bonus_pending = False
        self.xp = self.level = self.score = 0
        self.paused = False
        self.start_time = self.end_time = 0.0
        self.intro_t = 0.9  # small fade-in / title at start of level

        # HUD text objects
        self.hud_hp = make_text("", 18, UI_COLOR)
        self.hud_lv = make_text("", 14, UI_COLOR)
        self.hud_level = make_text("", 14, UI_COLOR)
        self.hud_wave = make_text("", 14, UI_COLOR)
        self.hud_score = make_text("", 14, UI_COLOR)
        self.hud_dash = make_text("", 12, arcade.color.LIGHT_GRAY)
        self.hud_boss = make_text("BOSS", 12, arcade.color.WHITE, "center")

    def setup(self):
        """
        Initialize a run of this GameView:
        - Set up background image based on level.
        - Clear sprite lists.
        - Create or reuse persistent player.
        - Reset timers, wave/score/xp, and spawn first wave.
        """
        arcade.set_background_color(BG_BOTTOM)

        # ---------------------------------------------------------
        # Load level-specific gradient background image
        # ---------------------------------------------------------
        bg_files = {
            1: "backgrounds/bluegradient.jpg",
            2: "backgrounds/greengradient.png",
            3: "backgrounds/redgradient.png",
        }
        bg_path = asset(bg_files[self.game_level])
        self.bg_sprite = arcade.Sprite(bg_path)
        self.bg_sprite.center_x = SCREEN_WIDTH / 2
        self.bg_sprite.center_y = SCREEN_HEIGHT / 2
        self.bg_sprite.width = SCREEN_WIDTH
        self.bg_sprite.height = SCREEN_HEIGHT

        self.bg_list = arcade.SpriteList()
        self.bg_list.append(self.bg_sprite)
        # ---------------------------------------------------------

        # Clear all sprite lists for a fresh level
        for lst in [self.player_list, self.enemy_list, self.boss_list, self.bullets,
                    self.enemy_bullets, self.xp_orbs, self.pickups, self.particles]:
            lst.clear()

        # --------------------------------------------------
        # Persistent player — do NOT reset perks between levels/waves
        #  - window.player_persistent is shared across GameView instances.
        # --------------------------------------------------
        if self.window.player_persistent is None:
            # First time creating player
            self.player = Player()
            self.window.player_persistent = self.player
        else:
            # Reuse upgraded persistent player
            self.player = self.window.player_persistent

        # Reset ONLY position, not perks/stats
        self.player.center_x = SCREEN_WIDTH / 2
        self.player.center_y = GROUND_Y + 60

        self.player_list.append(self.player)
        # --------------------------------------------------

        # Timers use the current player stats (since perks may have modified them)
        self.fire_timer, self.dash_timer, self.melee_timer = (
            Timer(self.player.fire_cd), Timer(self.player.dash_cd), Timer(MELEE_CD)
        )

        # Reset run-level state
        self.wave, self.wave_clear_bonus_pending, self.xp, self.level = 1, False, 0, 1
        self.score, self.paused, self.intro_t = 0, False, 0.9
        self.start_time, self.shake_t, self.flash_t = time.time(), 0.0, 0.0

        # Spawn initial wave or boss depending on level
        self._spawn_wave(self.wave)

    def _spawn_wave(self, w):
        """
        Spawn a wave of enemies or boss based on:
        - game_level (1/2 = waves + boss, 3 = giant boss only)
        - current wave number w
        """
        rngx = lambda: random.randint(ARENA_MARGIN, SCREEN_WIDTH - ARENA_MARGIN)
        rngy = lambda: random.randint(SCREEN_HEIGHT // 2, SCREEN_HEIGHT - ARENA_MARGIN - 20)

        if self.game_level == 3:
            # Level 3 always spawns the giant boss
            self.boss_list.append(Boss(giant=True))
        elif w < TOTAL_WAVES:
            # Regular waves (Level 1/2)
            mult = 1.5 if self.game_level == 2 else 1.0
            for _ in range(int((4 + w) * mult)):
                self.enemy_list.append(Chaser(rngx(), rngy()))
            for _ in range(int((2 + w // 2) * mult)):
                self.enemy_list.append(Shooter(rngx(), rngy()))
            for _ in range(int((1 + w // 2) * mult)):
                self.enemy_list.append(Bomber(rngx(), rngy()))
            if random.random() < 0.3:
                self.enemy_list.append(Chaser(rngx(), rngy(), elite=True))
        else:
            # After last wave, spawn non-giant boss
            self.boss_list.append(Boss(giant=False))

    def _draw_background(self):
        """
        Draws the arena floor strip and the grid + border overlay.
        - Gradient image behind this is drawn in on_draw.
        """
        arcade.draw_lrbt_rectangle_filled(SCREEN_WIDTH / 2 - (SCREEN_WIDTH - 40) / 2,
                                          SCREEN_WIDTH / 2 + (SCREEN_WIDTH - 40) / 2,
                                          GROUND_Y - 46, GROUND_Y + 46, arcade.color.DARK_OLIVE_GREEN)
        arcade.draw_lrbt_rectangle_outline(ARENA_MARGIN, SCREEN_WIDTH - ARENA_MARGIN, GROUND_Y,
                                           SCREEN_HEIGHT - ARENA_MARGIN,
                                           arcade.color.WHITE, 2)
        for x in range(ARENA_MARGIN, SCREEN_WIDTH - ARENA_MARGIN + 1, GRID_SPACING):
            arcade.draw_line(x, GROUND_Y, x, SCREEN_HEIGHT - ARENA_MARGIN, GRID_COLOR, 1)
        for y in range(GROUND_Y, SCREEN_HEIGHT - ARENA_MARGIN + 1, GRID_SPACING):
            arcade.draw_line(ARENA_MARGIN, y, SCREEN_WIDTH - ARENA_MARGIN, y, GRID_COLOR, 1)

    def _draw_telegraphs(self):
        """
        Draw telegraphed danger zones (rings) for Bombers and Boss.
        - Uses the telegraphs list on each enemy/boss.
        """
        for e in list(self.enemy_list) + list(self.boss_list):
            if hasattr(e, 'telegraphs'):
                for (x, y, r, t, kind) in e.telegraphs:
                    alpha = int(60 + 120 * (t / 0.9))
                    arcade.draw_circle_filled(x, y, r, DANGER_FILL)
                    arcade.draw_circle_outline(x, y, r, (*DANGER_EDGE[:3], alpha), 3)

    def _draw_outlines(self):
        """
        Draw outlines around player, enemies, and boss for readability.
        """
        pr = max(self.player.width, self.player.height) / 2 + 2
        arcade.draw_circle_outline(self.player.center_x, self.player.center_y, pr, PLAYER_OUT, 2)
        for e in self.enemy_list:
            arcade.draw_circle_outline(e.center_x, e.center_y, e.width / 2 + 2, ENEMY_OUT, 2)
        for b in self.boss_list:
            arcade.draw_circle_outline(b.center_x, b.center_y, b.width / 2 + 3, BOSS_OUT, 3)

    def _draw_health_bars(self):
        """
        Draw health bars for:
        - Player above head.
        - Each normal enemy.
        - Boss bar at top-right.
        """
        # Player bar
        pr = max(self.player.width, self.player.height) / 2
        px, py = self.player.center_x, self.player.center_y + pr + 14
        draw_health_bar(px, py, 60, 8, self.player.hp, self.player.hp_max)
        if self.player.shield > 0:
            arcade.draw_circle_outline(px, py + 18, 8, arcade.color.SKY_BLUE, 2)

        # Enemy bars
        for e in self.enemy_list:
            draw_health_bar(e.center_x, e.center_y + e.height / 2 + 10, 46, 6, e.hp, e.max_hp)

        # Boss bar
        if len(self.boss_list):
            b = self.boss_list[0]
            bw, bx, by = 460, SCREEN_WIDTH - 20 - 460, SCREEN_HEIGHT - 42
            arcade.draw_lrbt_rectangle_outline(bx - 2, bx + bw + 2, by - 12, by + 12, arcade.color.WHITE, 2)
            fill_w = int(bw * b.hp_norm())
            if fill_w > 0:
                arcade.draw_lrbt_rectangle_filled(bx, bx + fill_w, by - 10, by + 10, arcade.color.RED)
            self.hud_boss.position = (bx + bw / 2, by - 10)
            draw_text_shadowed(self.hud_boss, *self.hud_boss.position)

    def on_draw(self):
        """
        Main render function:
        - Background image, arena grid
        - Telegraphs, sprites, particles
        - Cursor, health bars, HUD
        - Intro overlay, damage flash, pause screen
        """
        self.clear()

        # Draw gradient background image
        if self.bg_sprite and self.bg_list:
            self.bg_list.draw()

        # Then arena + grid overlay
        self._draw_background()

        self._draw_telegraphs()
        self.player_list.draw()
        self._draw_outlines()
        self.enemy_list.draw()
        self.boss_list.draw()
        self.bullets.draw()
        self.enemy_bullets.draw()
        self.xp_orbs.draw()
        self.pickups.draw()

        # Particle effects (hit sparks, etc.)
        for p in list(self.particles):
            life = getattr(p, "life", 0.0)
            if life <= 0:
                p.remove_from_sprite_lists()
            else:
                alpha = int(255 * min(1.0, life / 0.5))
                p.color = (p.color[0], p.color[1], p.color[2], max(40, min(255, alpha)))
                p.center_x = snap(p.center_x + getattr(p, "change_x", 0.0))
                p.center_y = snap(p.center_y + getattr(p, "change_y", 0.0))
                p.life = life - 1 / 60
        self.particles.draw()

        # Aim cursor
        arcade.draw_circle_outline(self.player.aim_x, self.player.aim_y, 11, arcade.color.LIGHT_GRAY, 2)

        self._draw_health_bars()
        self._draw_hud()

        # Intro fade/title
        if self.intro_t > 0:
            a = int(min(self.intro_t * 400, 220))
            arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT, (0, 0, 0, a))
            if self.game_level == 3:
                title_txt = "Level 3 - Giant Boss"
            else:
                title_txt = f"Level {self.game_level} - Wave {self.wave}"
            title = make_text(title_txt, 30, arcade.color.WHITE, "center")
            draw_text_shadowed(title, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 8)

        # Damage flash overlay
        if self.flash_t > 0:
            alpha = int(150 * min(1.0, self.flash_t / 0.15))
            arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT, (255, 40, 40, alpha))

        # Pause menu overlay
        if self.paused:
            cx, cy, w, h = SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, 560, 180
            arcade.draw_lrbt_rectangle_filled(cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2, (0, 0, 0, 200))
            draw_text_shadowed(make_text("PAUSED", 28, arcade.color.GOLD, "center"), cx, cy + 26)
            draw_text_shadowed(make_text("ESC: resume • R: restart • M: menu", 14, arcade.color.LIGHT_GRAY, "center"),
                               cx, cy - 12)

    def _draw_hud(self):
        """
        Draws HUD info:
        - HP, level, wave, score, dash cooldown
        - XP bar for next level
        """
        self.hud_hp.text = f"HP {self.player.hp}/{self.player.hp_max}"
        self.hud_lv.text = f"LV {self.level}"
        self.hud_level.text = f"GAME LV {self.game_level}"
        self.hud_wave.text = f"Wave {self.wave}/{TOTAL_WAVES}"
        self.hud_score.text = f"Score {self.score}"
        dash_msg = "Ready" if self.dash_timer.ready() else f"{self.dash_timer.t:.1f}s"
        self.hud_dash.text = f"Dash: {dash_msg}"

        self.hud_hp.position = (12, SCREEN_HEIGHT - 26)
        self.hud_lv.position = (12, SCREEN_HEIGHT - 48)
        draw_text_shadowed(self.hud_hp, *self.hud_hp.position)
        draw_text_shadowed(self.hud_lv, *self.hud_lv.position)

        # XP bar
        need = XP_TO_LEVEL_BASE + (self.level - 1) * 2
        bar_w = 220
        arcade.draw_lrbt_rectangle_outline(12, 12 + bar_w, SCREEN_HEIGHT - 62, SCREEN_HEIGHT - 48,
                                           arcade.color.WHITE, 2)
        filled = int(bar_w * (self.xp / need)) if need else 0
        if filled > 0:
            arcade.draw_lrbt_rectangle_filled(12, 12 + filled, SCREEN_HEIGHT - 62, SCREEN_HEIGHT - 48,
                                              arcade.color.SPRING_BUD)

        # Other HUD labels
        self.hud_level.position = (12, SCREEN_HEIGHT - 72)
        self.hud_wave.position = (12, SCREEN_HEIGHT - 92)
        self.hud_score.position = (12, SCREEN_HEIGHT - 112)
        self.hud_dash.position = (12, SCREEN_HEIGHT - 132)
        draw_text_shadowed(self.hud_level, *self.hud_level.position)
        draw_text_shadowed(self.hud_wave, *self.hud_wave.position)
        draw_text_shadowed(self.hud_score, *self.hud_score.position)
        draw_text_shadowed(self.hud_dash, *self.hud_dash.position)

    def on_update(self, dt):
        """
        Core game logic tick:
        - Handles progression (wave, level changes).
        - Updates timers, player movement, enemies, boss AI.
        - Manages collisions, XP, pickups, and win/lose conditions.
        """
        if self.paused:
            return
        if self.intro_t > 0:
            self.intro_t -= dt
            return

        # Level progression condition:
        # Reach score >= 90, finish waves/boss, then advance (for level < 3).
        if self.score >= 90 and self.game_level < 3:
            if not len(self.enemy_list) and not len(self.boss_list) and not self.wave_clear_bonus_pending:
                self._advance_level()
                return

        # Sync timers with current player stats (modified by perks)
        self.fire_timer.cd = self.player.fire_cd
        self.dash_timer.cd = self.player.dash_cd
        self.fire_timer.update(dt)
        self.dash_timer.update(dt)
        self.melee_timer.update(dt)
        self.player.update_timers(dt)

        if self.shake_t > 0:
            self.shake_t -= dt
        if self.flash_t > 0:
            self.flash_t -= dt

        # Auto-fire when holding shoot
        if self.shoot_hold and self.fire_timer.ready():
            self._player_shoot()

        # Player movement (WASD)
        dx = (self.right - self.left)
        dy = (self.up - self.down)
        speed = self.player.speed
        # Normalize diagonal speed
        if dx and dy:
            speed *= 0.7071
        if self.player.dashing > 0:
            speed = self.player.dash_speed
        self.player.center_x = snap(self.player.center_x + dx * speed)
        self.player.center_y = snap(self.player.center_y + dy * speed)

        # Keep player inside arena
        if self.player.left < ARENA_MARGIN:
            self.player.left = ARENA_MARGIN
        if self.player.right > SCREEN_WIDTH - ARENA_MARGIN:
            self.player.right = SCREEN_WIDTH - ARENA_MARGIN
        if self.player.bottom < GROUND_Y:
            self.player.bottom = GROUND_Y
        if self.player.top > SCREEN_HEIGHT - ARENA_MARGIN:
            self.player.top = SCREEN_HEIGHT - ARENA_MARGIN

        # Update projectiles and pickups
        self.bullets.update()
        self.enemy_bullets.update()
        self.xp_orbs.update()
        self.pickups.update()

        # XP magnet behavior
        for orb in self.xp_orbs:
            d = dist(self.player.center_x, self.player.center_y, orb.center_x, orb.center_y)
            if d < self.player.magnet_radius:
                vx, vy = (self.player.center_x - orb.center_x) / (d or 1), (
                        self.player.center_y - orb.center_y) / (d or 1)
                orb.center_x = snap(orb.center_x + vx * 4.2)
                orb.center_y = snap(orb.center_y + vy * 4.2)

        # Enemy AI updates + status ticks
        for e in list(self.enemy_list):
            e.update_status(dt, lambda dmg, _e=e: setattr(_e, "hp", _e.hp - dmg))
            if isinstance(e, (Chaser, Shooter, Bomber)):
                e.step(self.player, dt)
            # Keep enemies in arena
            if e.left < ARENA_MARGIN:
                e.left = ARENA_MARGIN
            if e.right > SCREEN_WIDTH - ARENA_MARGIN:
                e.right = SCREEN_WIDTH - ARENA_MARGIN
            if e.bottom < GROUND_Y:
                e.bottom = GROUND_Y
            if e.top > SCREEN_HEIGHT - ARENA_MARGIN:
                e.top = SCREEN_HEIGHT - ARENA_MARGIN
            # Handle death
            if e.hp <= 0:
                self._enemy_die(e)

        # Bomber attack telegraphs & ring shots
        for e in self.enemy_list:
            if isinstance(e, Bomber):
                # Randomly create telegraphed rings
                if random.random() < (0.006 if e.slow_t <= 0 else 0.003):
                    e.telegraphs.append((e.center_x, e.center_y - 4, 36, 0.9, "RING"))
                nt = []
                for (x, y, r, t, k) in e.telegraphs:
                    t -= dt
                    if t <= 0:
                        self._spawn_ring_bullets(x, y, r, count=16, speed=6.2)
                        self.shake_t = 0.12
                    else:
                        nt.append((x, y, r, t, k))
                e.telegraphs = nt

        # Boss AI
        if len(self.boss_list):
            self._boss_logic(dt)
            b = self.boss_list[0]
            # Keep boss in arena
            if b.left < ARENA_MARGIN:
                b.left = ARENA_MARGIN
            if b.right > SCREEN_WIDTH - ARENA_MARGIN:
                b.right = SCREEN_WIDTH - ARENA_MARGIN
            if b.bottom < GROUND_Y:
                b.bottom = GROUND_Y
            if b.top > SCREEN_HEIGHT - ARENA_MARGIN:
                b.top = SCREEN_HEIGHT - ARENA_MARGIN

        # Resolves all collision types (bullets vs enemies, player vs bullets, pickups, etc.)
        self._handle_collisions()

        # Remove bullets that leave arena
        for b in list(self.bullets) + list(self.enemy_bullets):
            if (b.right < ARENA_MARGIN or b.left > SCREEN_WIDTH - ARENA_MARGIN or
                    b.top > SCREEN_HEIGHT - ARENA_MARGIN or b.bottom < GROUND_Y):
                b.remove_from_sprite_lists()

        # Wave clear -> spawn bonus XP and schedule next wave
        if self.wave < TOTAL_WAVES and not len(self.enemy_list) and not self.wave_clear_bonus_pending:
            self.wave_clear_bonus_pending = True
            for _ in range(XP_PER_WAVE_CLEAR):
                self.xp_orbs.append(XPOrb(self.player.center_x + random.uniform(-20, 20),
                                          self.player.center_y + random.uniform(-10, 10)))
            arcade.schedule(self._start_next_wave, 1.2)

        # After final wave and boss:
        if self.wave == TOTAL_WAVES and not len(self.boss_list) and not self.wave_clear_bonus_pending:
            if self.game_level < 3 and self.score >= 90:
                self._advance_level()
            elif self.game_level == 3:
                self._win()

    def _boss_logic(self, dt):
        """
        Controls boss movement and attack patterns.
        - Different behavior for giant vs non-giant boss and phases.
        """
        b = self.boss_list[0]
        b.phase_timer += dt

        # Phase switch at 50% HP for non-giant boss
        if b.phase == 1 and b.hp < b.max_hp * 0.5:
            b.phase = 2
            b.phase_timer = 0.0

        # Horizontal oscillation
        b.center_x = snap(b.center_x + math.sin(b.phase_timer * 0.9) * (1.6 if b.phase == 2 else 1.2))

        if b.giant:
            # Giant boss (Level 3) attack pattern
            if int(b.phase_timer * 10) % 8 == 0 and b.phase_timer % 0.1 < dt:
                angle = random.uniform(0, math.tau)
                self.enemy_bullets.append(
                    Bullet(b.center_x, b.center_y, math.cos(angle), math.sin(angle),
                           7.5, arcade.color.LIGHT_CORAL, "enemy"))
            if random.random() < 0.015:
                b.telegraphs.append((b.center_x + random.uniform(-40, 40),
                                     b.center_y - 8 + random.uniform(-20, 20),
                                     random.choice((42, 52, 62)), 0.9, "RING_BIG"))
        else:
            # Normal boss (Levels 1–2)
            if b.phase == 1:
                # Single directed shots + occasional ring telegraph
                if b.phase_timer > 1.0:
                    b.phase_timer = 0.0
                    dx, dy = self.player.center_x - b.center_x, self.player.center_y - b.center_y
                    d = math.hypot(dx, dy) or 1
                    self.enemy_bullets.append(
                        Bullet(b.center_x, b.center_y, dx / d, dy / d, 7.2, arcade.color.PURPLE, "enemy"))
                    if random.random() < 0.35:
                        b.telegraphs.append((b.center_x, b.center_y - 6, 40, 0.9, "RING"))
            else:
                # Phase 2: fan spreads + more dangerous rings
                if int(b.phase_timer * 10) % 16 == 0 and b.phase_timer % 0.1 < dt:
                    dx, dy = self.player.center_x - b.center_x, self.player.center_y - b.center_y
                    base = math.atan2(dy, dx)
                    spread = math.radians(90)
                    for i in range(9):
                        ang = base + spread * (i / 8 - 0.5)
                        self.enemy_bullets.append(
                            Bullet(b.center_x, b.center_y, math.cos(ang), math.sin(ang),
                                   7.8, arcade.color.LIGHT_CORAL, "enemy"))
                if random.random() < 0.018:
                    b.telegraphs.append((b.center_x, b.center_y - 8,
                                         random.choice((42, 52)), 0.9, "RING_BIG"))

        # Resolve telegraphs -> spawn ring bullets
        nt = []
        for (x, y, r, t, k) in b.telegraphs:
            t -= dt
            if t <= 0:
                self._spawn_ring_bullets(x, y, r, count=12 if k == "RING" else 18, speed=5.0)
                self.shake_t = 0.18
            else:
                nt.append((x, y, r, t, k))
        b.telegraphs = nt

    def _spawn_ring_bullets(self, x, y, r, count=18, speed=6.6):
        """
        Spawn a ring of enemy bullets around (x,y).
        - Used by Bombers and Boss telegraphs.
        """
        for i in range(count):
            a = 2 * math.pi * i / count
            self.enemy_bullets.append(Bullet(x, y, math.cos(a), math.sin(a), speed, BULLET_COLOR_ENEMY, "enemy"))

    def _handle_collisions(self):
        """
        All collision handling:
        - Player bullets vs enemies/boss.
        - Enemy bullets vs player.
        - Player vs enemies/boss (contact damage).
        - Player vs XP orbs/pickups.
        """
        # ---------------------------
        # Player bullets vs enemies
        # ---------------------------
        for e in list(self.enemy_list):
            hits = arcade.check_for_collision_with_list(e, self.bullets)
            if hits:
                for proj in hits:
                    # Pierce handling
                    if proj.pierce_left > 0:
                        proj.pierce_left -= 1
                    else:
                        proj.remove_from_sprite_lists()
                # Check if bullet is a spread pellet
                is_spread = hasattr(proj, "spread_pellet")

                NERF_MULT = 0.6  # 60% damage for spread pellets
                base = self.player.damage * (NERF_MULT if is_spread else 1.0)
                dmg_per = base * (2 if random.random() < self.player.crit_chance else 1)
                e.hp -= dmg_per * len(hits)
                e.apply_status(self.player.burn_on_hit, self.player.slow_on_hit)
                self._hit_particles(e.center_x, e.center_y, color=arcade.color.GOLD)
                if e.hp <= 0:
                    self._enemy_die(e)

        # ---------------------------
        # Player bullets vs boss
        # ---------------------------
        if len(self.boss_list):
            boss = self.boss_list[0]
            hits = arcade.check_for_collision_with_list(boss, self.bullets)
            if hits:
                for proj in hits:
                    if proj.pierce_left > 0:
                        proj.pierce_left -= 1
                    else:
                        proj.remove_from_sprite_lists()
                dmg_per = self.player.damage * (2 if random.random() < self.player.crit_chance else 1)
                boss.hp -= dmg_per * len(hits)
                self._hit_particles(boss.center_x, boss.center_y, color=arcade.color.GOLD)
                # Combo system -> increases score multiplier if you keep hitting boss
                self.player.combo = min(5, self.player.combo + 1)
                self.player.combo_t = 3.0
                self.score += 8 * self.player.combo * len(hits)
                if boss.hp <= 0:
                    self._boss_die(boss)

        # ---------------------------
        # Enemy bullets vs player
        # ---------------------------
        pb = arcade.check_for_collision_with_list(self.player, self.enemy_bullets)
        for proj in pb:
            proj.remove_from_sprite_lists()
            if self.player.take_hit(1):
                self.flash_t = 0.15
                self.shake_t = 0.12
                if self.player.hp <= 0:
                    self._lose()
                    return

        # ---------------------------
        # Player vs enemies (contact damage + knockback)
        # ---------------------------
        for e in list(self.enemy_list):
            if arcade.check_for_collision(self.player, e):
                if self.player.iframes <= 0:
                    if self.player.take_hit(1):
                        self.flash_t = 0.15
                        self.shake_t = 0.12
                        self.player.iframes = 2
                        if self.player.hp <= 0:
                            self._lose()
                            return
                    # Knock player away from enemy
                    ang = math.atan2(self.player.center_y - e.center_y,
                                     self.player.center_x - e.center_x)
                    self.player.center_x = snap(self.player.center_x + math.cos(ang) * 16)
                    self.player.center_y = snap(self.player.center_y + math.sin(ang) * 16)

        # ---------------------------
        # Player vs boss (contact damage)
        # ---------------------------
        for b in self.boss_list:
            if arcade.check_for_collision(self.player, b):
                if self.player.iframes <= 0:
                    if self.player.take_hit(1):
                        self.flash_t = 0.15
                        self.shake_t = 0.12
                        self.player.iframes = 2
                        if self.player.hp <= 0:
                            self._lose()
                            return

        # ---------------------------
        # Player vs XP orbs
        # ---------------------------
        for o in arcade.check_for_collision_with_list(self.player, self.xp_orbs):
            o.remove_from_sprite_lists()
            self._gain_xp(XP_ORB_VALUE)

        # ---------------------------
        # Player vs pickups
        # ---------------------------
        for p in arcade.check_for_collision_with_list(self.player, self.pickups):
            if p.kind == "health" and self.player.hp < self.player.hp_max:
                self.player.hp += 1
            elif p.kind == "shield":
                self.player.shield += 1
            p.remove_from_sprite_lists()

    def _enemy_die(self, e):
        """
        Enemy death:
        - Spawn particles, give score, drop XP and rare health/shield pickups.
        """
        self._hit_particles(e.center_x, e.center_y, count=10, color=arcade.color.BANGLADESH_GREEN)
        e.remove_from_sprite_lists()
        self.score += 12 * self.player.combo
        if random.random() < 0.9:
            self.xp_orbs.append(XPOrb(e.center_x, e.center_y))
        if random.random() < 0.08:
            self.pickups.append(Pickup(e.center_x, e.center_y,
                                       "health" if random.random() < 0.6 else "shield"))

    def _boss_die(self, boss):
        """
        Boss death:
        - Big explosion of particles + huge score bonus.
        """
        for _ in range(28):
            self._hit_particles(boss.center_x + random.uniform(-12, 12),
                                boss.center_y + random.uniform(-12, 12),
                                count=1, color=arcade.color.ORANGE, vel=4.0)
        boss.remove_from_sprite_lists()
        self.score += 400

    def _gain_xp(self, amount):
        """
        Add XP and handle level-up:
        - On level-up, subtract required XP and show perk selection view.
        """
        self.xp += amount
        need = XP_TO_LEVEL_BASE + (self.level - 1) * 2
        if self.xp >= need:
            self.xp -= need
            self.level += 1
            self._offer_perk()

    def _offer_perk(self):
        """
        Show PerkDraftView with 3 random choices from perk_pool().
        """
        choices = random.sample(perk_pool(), 3)
        self.window.show_view(PerkDraftView(self, choices))

    def _player_shoot(self):
        """
        Create player bullets:
        - If has_spread is True, spawn shotgun of pellets.
        - Otherwise, single bullet in facing direction.
        """
        self.fire_timer.trigger()
        vx, vy = self.player.facing()
        pierce_left = self.player.pierce

        if self.player.has_spread:
            spread = SHOTGUN_SPREAD
            for i in range(SHOTGUN_PELLETS):
                t = i / (SHOTGUN_PELLETS - 1) - 0.5
                a = math.atan2(vy, vx) + spread * t

                b = Bullet(
                    self.player.center_x, self.player.center_y,
                    math.cos(a), math.sin(a),
                    self.player.bullet_speed,
                    BULLET_COLOR_PLAYER,
                    "player",
                    pierce_left=pierce_left
                )
                # Mark as spread pellet so we can nerf damage later
                b.spread_pellet = True
                self.bullets.append(b)
        else:
            self.bullets.append(
                Bullet(self.player.center_x, self.player.center_y, vx, vy,
                       self.player.bullet_speed, BULLET_COLOR_PLAYER, "player",
                       pierce_left=pierce_left))

    def _melee_slash(self):
        """
        Melee attack:
        - Damages enemies in range.
        - Applies burn/slow if player has those perks.
        - Adds score if you hit anything.
        """
        if not self.melee_timer.ready():
            return
        self.melee_timer.trigger()
        hit_any = False
        for e in list(self.enemy_list):
            d = dist(self.player.center_x, self.player.center_y, e.center_x, e.center_y)
            if d <= MELEE_RANGE + e.width / 2:
                e.hp -= MELEE_DAMAGE
                e.apply_status(self.player.burn_on_hit, self.player.slow_on_hit)
                self._hit_particles(e.center_x, e.center_y, color=arcade.color.GOLD)
                if e.hp <= 0:
                    self._enemy_die(e)
                hit_any = True
        if hit_any:
            self.score += 5 * self.player.combo
        self._hit_particles(self.player.center_x, self.player.center_y,
                            count=6, color=arcade.color.LIGHT_CYAN)

    def _hit_particles(self, x, y, count=8, color=arcade.color.GOLD, vel=2.2):
        """
        Spawn particle sprites for hit/explosion effects.
        - Uses a small lifetime and random velocity.
        """
        for _ in range(count):
            p = arcade.SpriteCircle(3, color)
            p.center_x = x + random.uniform(-6, 6)
            p.center_y = y + random.uniform(-6, 6)
            p.change_x = random.uniform(-vel, vel)
            p.change_y = random.uniform(-vel, vel)
            p.life = 0.45
            self.particles.append(p)

    def _start_next_wave(self, dt):
        """
        Scheduled callback to start the next wave after a delay.
        - Called once wave-clear bonus was given.
        """
        arcade.unschedule(self._start_next_wave)
        if self.wave < TOTAL_WAVES - 1:
            self.wave += 1
            self.wave_clear_bonus_pending = False
            self.intro_t = 0.9
            self._spawn_wave(self.wave)
        elif self.wave == TOTAL_WAVES - 1:
            self.wave = TOTAL_WAVES
            self.wave_clear_bonus_pending = False
            self.intro_t = 0.9
            self._spawn_wave(self.wave)

    def _advance_level(self):
        """
        Go to the next game_level (1 -> 2 -> 3).
        - New GameView is created, but shares the same window and persistent player.
        """
        self.game_level += 1
        gv = GameView(self.game_level)

        # Keep same window + same player
        gv.window = self.window

        gv.setup()
        self.window.show_view(gv)

    def _win(self):
        """
        Called when player clears final required level condition.
        """
        self.end_time = time.time()
        self.window.show_view(
            GameOverView(self.score, True, self.end_time - self.start_time, self.game_level))

    def _lose(self):
        """
        Called when player's HP reaches 0.
        """
        self.end_time = time.time()
        self.window.show_view(
            GameOverView(self.score, False, self.end_time - self.start_time, self.game_level))

    # -----------------------------------------------------------------------
    # Input handling (keyboard + mouse)
    # -----------------------------------------------------------------------
    def on_key_press(self, key, modifiers):
        """
        Handle movement, firing, melee, dash, pause, restart, menu.
        """
        if key in (arcade.key.W, arcade.key.UP):
            self.up = 1
        elif key in (arcade.key.S, arcade.key.DOWN):
            self.down = 1
        elif key in (arcade.key.A, arcade.key.LEFT):
            self.left = 1
        elif key in (arcade.key.D, arcade.key.RIGHT):
            self.right = 1
        elif key == arcade.key.SPACE:
            # Keyboard shooting (hold to autofire)
            self.shoot_hold = True
            if self.fire_timer.ready():
                self._player_shoot()
        elif key == arcade.key.Z:
            # Melee attack
            self._melee_slash()
        elif key == arcade.key.LSHIFT:
            # Dash: teleport slightly and apply i-frames
            if self.dash_timer.ready():
                self.dash_timer.trigger()
                self.player.dashing = self.player.dash_time
                self.player.iframes = max(self.player.iframes, self.player.dash_iframe)
                vx, vy = self.player.facing()
                self.player.center_x = snap(self.player.center_x + vx * 20)
                self.player.center_y = snap(self.player.center_y + vy * 20)
        elif key == arcade.key.ESCAPE:
            # Toggle pause
            self.paused = not self.paused
        elif key == arcade.key.R:
            # Restart current level if paused
            if self.paused:
                self.setup()
        elif key == arcade.key.M:
            # Go back to menu (keeps or resets persistent player based on GameOverView)
            self.window.show_view(MenuView())

    def on_key_release(self, key, modifiers):
        """Stop movement / shooting when keys are released."""
        if key in (arcade.key.W, arcade.key.UP):
            self.up = 0
        elif key in (arcade.key.S, arcade.key.DOWN):
            self.down = 0
        elif key in (arcade.key.A, arcade.key.LEFT):
            self.left = 0
        elif key in (arcade.key.D, arcade.key.RIGHT):
            self.right = 0
        elif key == arcade.key.SPACE:
            self.shoot_hold = False

    def on_mouse_motion(self, x, y, dx, dy):
        """Update player aim position to current mouse position."""
        self.player.aim_x, self.player.aim_y = snap(x), snap(y)

    def on_mouse_press(self, x, y, button, modifiers):
        """Mouse left = shoot (hold for autofire)."""
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.shoot_hold = True
            if self.fire_timer.ready():
                self._player_shoot()

    def on_mouse_release(self, x, y, button, modifiers):
        """Stop autofire on mouse release."""
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.shoot_hold = False


# ---------------------------------------------------------------------------
# Main entry point
#  - Creates the window and sets initial View to MenuView.
#  - Also attaches player_persistent storage to the window object.
# ---------------------------------------------------------------------------
def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)

    # Create persistent player storage (shared across GameView instances)
    window.player_persistent = None

    window.show_view(MenuView())

    arcade.run()


if __name__ == "__main__":
    main()
