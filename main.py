"""
StoryQuest+ — Twin Guardians (Arcade 3.x, single-file)

New stuff:
  • Mouse aiming + crosshair
  • Dash (SHIFT) with invulnerability frames (i-frames)
  • Combo multiplier that decays if you get hit / wait too long
  • Power-ups: Heal, Shield, RapidFire, Spread (auto-spawn + boss drops)
  • Minions in Stage 2
  • Telegraphs (danger zones) for big boss attacks
  • Pause/Resume (ESC), Restart (R), Menu (M)

Controls:
  Move: WASD / Arrows
  Shoot: SPACE or Left Click (mouse aimed)
  Melee: Z (short range, small AOE)
  Dash: Left Shift (i-frames + burst speed)
  Pause: ESC
"""

import arcade
import math
import random
from typing import Optional

# ------------------ Window / globals ------------------
SCREEN_WIDTH = 960
SCREEN_HEIGHT = 600
SCREEN_TITLE = "StoryQuest+ : The Twin Guardians"

# Player
PLAYER_RADIUS = 20
PLAYER_SPEED = 4.2
PLAYER_MAX_HEALTH = 8
PLAYER_DASH_SPEED = 10.0
PLAYER_DASH_TIME = 0.18
PLAYER_DASH_COOLDOWN = 1.1
PLAYER_IFRAME_TIME = 0.35  # includes dash duration
PLAYER_MELEE_RANGE = 40
PLAYER_MELEE_DAMAGE = 2
PLAYER_MELEE_COOLDOWN = 0.55

# Shooting
BULLET_SPEED = 10.0
BULLET_COOLDOWN = 0.28
SPREAD_ANGLE = math.radians(10)

# Boss / game
BOSS_COUNT = 2
BG_COLOR = arcade.color.DARK_SLATE_BLUE
UI_COLOR = arcade.color.ALMOND

# Power-ups
POWERUP_DROP_PERIOD = (6.0, 9.0)  # random seconds
POWERUP_DURATION = 7.0
POWERUP_TYPES = ("HEAL", "SHIELD", "RAPID", "SPREAD")
HEAL_AMOUNT = 2

# Combo
COMBO_WINDOW = 3.0  # seconds to extend combo
COMBO_MAX = 5

# Telegraphs
TELEGRAPH_TIME = 0.9  # how long a danger zone shows before firing

# Utility ------------------------------------------------
class Timer:
    def __init__(self, cooldown: float = 0.0):
        self.cooldown = cooldown
        self.t = 0.0

    def set(self, val: float):
        self.t = max(0.0, val)

    def trigger(self):
        self.t = self.cooldown

    def ready(self) -> bool:
        return self.t <= 0.0

    def update(self, dt: float):
        if self.t > 0.0:
            self.t -= dt
            if self.t < 0.0:
                self.t = 0.0


# ------------------ Views ------------------
class MenuView(arcade.View):
    def on_show(self):
        arcade.set_background_color(BG_COLOR)

    def on_draw(self):
        self.clear()
        arcade.draw_text("STORYQUEST+ : THE TWIN GUARDIANS", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.68,
                         arcade.color.GOLD, 36, anchor_x="center")
        arcade.draw_text("Mouse aim • Dash (SHIFT) • Power-ups • Minions • Combo", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.6,
                         arcade.color.LIGHT_GRAY, 16, anchor_x="center")
        arcade.draw_text("Controls: WASD/Arrows to move, SPACE/LeftClick to shoot, Z melee, SHIFT dash, ESC pause",
                         SCREEN_WIDTH/2, SCREEN_HEIGHT*0.53, arcade.color.WHITE, 12, anchor_x="center")
        arcade.draw_text("Press ENTER to Start", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.32,
                         arcade.color.LIGHT_GREEN, 22, anchor_x="center")
        arcade.draw_text("Press ESC to Quit", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.26,
                         arcade.color.LIGHT_GRAY, 14, anchor_x="center")

    def on_key_press(self, key, modifiers):
        if key in (arcade.key.ENTER, arcade.key.RETURN):
            story = StoryView(stage=1)
            self.window.show_view(story)
        elif key == arcade.key.ESCAPE:
            arcade.close_window()


class StoryView(arcade.View):
    STORIES = {
        1: [
            "You are Arin, a courier with a secret blade.",
            "An ancient guardian blocks the forest pass.",
            "Defeat it to reach the twin at the peak.",
            "Steel your will..."
        ],
        2: [
            "The first guardian falls. The summit nears.",
            "The twin is faster, crueler—and it never fights alone.",
            "Learn its tells. Punish its patterns.",
            "Breathe. Then strike."
        ],
    }

    def __init__(self, stage: int):
        super().__init__()
        self.stage = stage
        self.index = 0

    def on_show(self):
        arcade.set_background_color(BG_COLOR)

    def on_draw(self):
        self.clear()
        arcade.draw_text(f"Stage {self.stage}", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.68,
                         arcade.color.BEIGE, 28, anchor_x="center")
        arcade.draw_rectangle_filled(SCREEN_WIDTH/2, SCREEN_HEIGHT/2 - 20, 780, 180,
                                     (*arcade.color.BLACK, 190))
        arcade.draw_text(self.STORIES[self.stage][self.index],
                         SCREEN_WIDTH/2 - 360, SCREEN_HEIGHT/2 - 10,
                         arcade.color.WHITE, 18)
        arcade.draw_text("Press ENTER to continue",
                         SCREEN_WIDTH/2, SCREEN_HEIGHT*0.18,
                         arcade.color.LIGHT_GRAY, 12, anchor_x="center")

    def on_key_press(self, key, modifiers):
        if key in (arcade.key.ENTER, arcade.key.RETURN):
            self.index += 1
            if self.index >= len(self.STORIES[self.stage]):
                game = GameView(stage=self.stage)
                game.setup()
                self.window.show_view(game)


# ------------------ Sprites ------------------
class Player(arcade.SpriteCircle):
    def __init__(self):
        super().__init__(PLAYER_RADIUS, arcade.color.CYAN)
        self.health = PLAYER_MAX_HEALTH
        self.aim_x = SCREEN_WIDTH/2
        self.aim_y = SCREEN_HEIGHT/2
        self.iframes = 0.0
        self.dashing = 0.0
        self.shield = 0.0  # time left
        self.spread = 0.0
        self.rapid = 0.0
        self.combo = 1
        self.combo_timer = 0.0

    def facing_vec(self):
        dx = self.aim_x - self.center_x
        dy = self.aim_y - self.center_y
        d = math.hypot(dx, dy) or 1.0
        return dx/d, dy/d

    def update_invuln(self, dt):
        if self.iframes > 0:
            self.iframes -= dt
            if self.iframes < 0:
                self.iframes = 0
        if self.dashing > 0:
            self.dashing -= dt
            if self.dashing < 0:
                self.dashing = 0
        if self.shield > 0:
            self.shield -= dt
        if self.spread > 0:
            self.spread -= dt
        if self.rapid > 0:
            self.rapid -= dt
        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 1

    def take_hit(self, dmg: int):
        if self.iframes > 0 or self.shield > 0:
            # shield absorbs 1 instance entirely and drops
            if self.shield > 0:
                self.shield = 0
            return False
        self.health -= dmg
        self.combo = 1
        self.combo_timer = 0.0
        return True


class Boss(arcade.SpriteCircle):
    def __init__(self, stage: int):
        size = 38 + 10 * stage
        color = arcade.color.RED if stage == 1 else arcade.color.ORANGE_RED
        super().__init__(size, color)
        self.stage = stage
        self.max_health = 40 + (stage - 1) * 28
        self.health = self.max_health
        self.phase = 0
        self.phase_timer = 0.0
        self.telegraphs = []  # list of (x,y,r,time_left,type)

    def hp_norm(self):
        return max(0.0, self.health / self.max_health)


class Bullet(arcade.SpriteCircle):
    def __init__(self, x, y, dx, dy, speed, color, owner="player", radius=3):
        super().__init__(radius, color)
        self.center_x = x
        self.center_y = y
        self.change_x = dx * speed
        self.change_y = dy * speed
        self.owner = owner


class PowerUp(arcade.SpriteCircle):
    COLOR_MAP = {
        "HEAL": arcade.color.SPRING_BUD,
        "SHIELD": arcade.color.LIGHT_SKY_BLUE,
        "RAPID": arcade.color.PALE_GOLDENROD,
        "SPREAD": arcade.color.PLUM,
    }
    def __init__(self, kind: str, x: float, y: float):
        super().__init__(10, PowerUp.COLOR_MAP[kind])
        self.kind = kind
        self.center_x = x
        self.center_y = y
        self.vy = -0.5

    def update(self):
        self.center_y += self.vy
        if self.bottom < 62:
            self.bottom = 62
            self.vy = 0.2  # bounce a bit
        else:
            self.vy *= 0.98


class Minion(arcade.SpriteCircle):
    def __init__(self, x, y):
        super().__init__(12, arcade.color.DARK_ORANGE)
        self.center_x = x
        self.center_y = y
        self.health = 3
        self.phase = 0.0

    def update_logic(self, player: Player, dt: float):
        self.phase += dt
        # orbit-ish wobble + home in
        dx = player.center_x - self.center_x
        dy = player.center_y - self.center_y
        d = math.hypot(dx, dy) or 1.0
        sx, sy = dx/d, dy/d
        self.center_x += sx * 1.8 + math.sin(self.phase*3.0) * 0.8
        self.center_y += sy * 1.8 + math.cos(self.phase*2.2) * 0.6


# ------------------ Game View ------------------
class GameView(arcade.View):
    def __init__(self, stage: int = 1):
        super().__init__()
        self.stage = stage

        # Sprites/lists
        self.player_list = arcade.SpriteList()
        self.boss_list = arcade.SpriteList()
        self.player_bullets = arcade.SpriteList()
        self.enemy_bullets = arcade.SpriteList()
        self.particles = arcade.SpriteList()
        self.powerups = arcade.SpriteList()
        self.minions = arcade.SpriteList()

        self.player: Optional[Player] = None
        self.boss: Optional[Boss] = None

        # Input state
        self.up = self.down = self.left = self.right = False
        self.shoot_hold = False

        # Timers
        self.shoot_cd = Timer(BULLET_COOLDOWN)
        self.melee_cd = Timer(PLAYER_MELEE_COOLDOWN)
        self.dash_cd = Timer(PLAYER_DASH_COOLDOWN)
        self.powerup_spawn_t = random.uniform(*POWERUP_DROP_PERIOD)

        # State
        self.score = 0
        self.win = False
        self.game_over = False
        self.paused = False
        self.intro_timer = 0.7

    # ---------- Setup ----------
    def setup(self):
        arcade.set_background_color(BG_COLOR)

        self.player_list = arcade.SpriteList()
        self.boss_list = arcade.SpriteList()
        self.player_bullets = arcade.SpriteList()
        self.enemy_bullets = arcade.SpriteList()
        self.particles = arcade.SpriteList()
        self.powerups = arcade.SpriteList()
        self.minions = arcade.SpriteList()

        self.player = Player()
        self.player.center_x = SCREEN_WIDTH // 2
        self.player.center_y = 100
        self.player_list.append(self.player)

        self.boss = Boss(self.stage)
        self.boss.center_x = SCREEN_WIDTH // 2
        self.boss.center_y = SCREEN_HEIGHT - (130 if self.stage == 1 else 150)
        self.boss_list.append(self.boss)

        self.score = 0
        self.win = False
        self.game_over = False
        self.paused = False
        self.intro_timer = 0.8

        self.shoot_cd.set(0.0)
        self.melee_cd.set(0.0)
        self.dash_cd.set(0.0)
        self.player.combo = 1
        self.player.combo_timer = 0.0

    # ---------- Draw ----------
    def on_draw(self):
        self.clear()

        # Background + ground
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT, BG_COLOR)
        arcade.draw_rectangle_filled(SCREEN_WIDTH/2, 56, SCREEN_WIDTH-40, 112, arcade.color.DARK_OLIVE_GREEN)

        # Danger telegraphs
        self._draw_telegraphs()

        # Sprites
        self.player_list.draw()
        self.boss_list.draw()
        self.minions.draw()
        self.player_bullets.draw()
        self.enemy_bullets.draw()
        self.powerups.draw()
        self.particles.draw()

        # Crosshair
        arcade.draw_circle_outline(self.player.aim_x, self.player.aim_y, 10, arcade.color.LIGHT_GRAY, 2)

        # UI
        self._draw_ui()

        # Intro overlay
        if self.intro_timer > 0:
            a = int(min(self.intro_timer * 400, 220))
            arcade.draw_rectangle_filled(SCREEN_WIDTH/2, SCREEN_HEIGHT/2, SCREEN_WIDTH, SCREEN_HEIGHT, (0, 0, 0, a))
            arcade.draw_text(f"Stage {self.stage} — Face the Guardian", SCREEN_WIDTH/2, SCREEN_HEIGHT/2 + 8,
                             arcade.color.WHITE, 24, anchor_x="center")

        if self.paused:
            arcade.draw_rectangle_filled(SCREEN_WIDTH/2, SCREEN_HEIGHT/2, 520, 160, (0, 0, 0, 200))
            arcade.draw_text("PAUSED", SCREEN_WIDTH/2, SCREEN_HEIGHT/2 + 26, arcade.color.GOLD, 28, anchor_x="center")
            arcade.draw_text("ESC: resume   R: restart   M: menu", SCREEN_WIDTH/2, SCREEN_HEIGHT/2 - 10,
                             arcade.color.LIGHT_GRAY, 14, anchor_x="center")

        if self.game_over:
            msg = "YOU WIN!" if self.win else "YOU DIED"
            arcade.draw_rectangle_filled(SCREEN_WIDTH/2, SCREEN_HEIGHT/2, 580, 160, (0, 0, 0, 210))
            arcade.draw_text(msg, SCREEN_WIDTH/2, SCREEN_HEIGHT/2 + 18, arcade.color.GOLD, 30, anchor_x="center")
            arcade.draw_text("R: replay   M: menu", SCREEN_WIDTH/2, SCREEN_HEIGHT/2 - 18,
                             arcade.color.LIGHT_GRAY, 16, anchor_x="center")

    def _draw_ui(self):
        # Health, score, combo
        arcade.draw_text(f"HP: {self.player.health}/{PLAYER_MAX_HEALTH}", 10, SCREEN_HEIGHT - 26, UI_COLOR, 16)
        arcade.draw_text(f"Score: {self.score}", 10, SCREEN_HEIGHT - 48, UI_COLOR, 14)
        if self.player.combo > 1:
            arcade.draw_text(f"Combo x{self.player.combo}", 10, SCREEN_HEIGHT - 70, arcade.color.LIGHT_GREEN, 14)

        # Power-up icons
        x = 180
        if self.player.shield > 0:
            arcade.draw_text("Shield", x, SCREEN_HEIGHT - 26, arcade.color.LIGHT_SKY_BLUE, 14); x += 70
        if self.player.rapid > 0:
            arcade.draw_text("Rapid", x, SCREEN_HEIGHT - 26, arcade.color.PALE_GOLDENROD, 14); x += 60
        if self.player.spread > 0:
            arcade.draw_text("Spread", x, SCREEN_HEIGHT - 26, arcade.color.PLUM, 14); x += 70

        # Boss bar
        if self.boss and self.boss in self.boss_list:
            bar_w = 420
            bar_x = SCREEN_WIDTH - bar_w - 20
            bar_y = SCREEN_HEIGHT - 40
            # outline
            arcade.draw_lrbt_rectangle_outline(bar_x - 2, bar_x + bar_w + 2, bar_y - 12, bar_y + 12,
                                               arcade.color.WHITE, 1)
            # fill
            fill_w = int(bar_w * self.boss.hp_norm())
            if fill_w > 0:
                arcade.draw_rectangle_filled(bar_x + fill_w/2, bar_y, fill_w, 20, arcade.color.RED)
            arcade.draw_text(f"Boss: {self.boss.health}/{self.boss.max_health}",
                             bar_x + bar_w/2, bar_y - 8, arcade.color.WHITE, 12, anchor_x="center")

    def _draw_telegraphs(self):
        if not self.boss:
            return
        for (x, y, r, tleft, kind) in self.boss.telegraphs:
            alpha = int(60 + 120 * (tleft / TELEGRAPH_TIME))
            col = arcade.color.YELLOW_ORANGE if kind == "RING" else arcade.color.LIGHT_SALMON
            arcade.draw_circle_outline(x, y, r, (*col, alpha), 3)

    # ---------- Update ----------
    def on_update(self, dt: float):
        if self.paused or self.game_over:
            return
        # Intro freeze
        if self.intro_timer > 0:
            self.intro_timer -= dt
            return

        # Timers
        self.shoot_cd.update(dt)
        self.melee_cd.update(dt)
        self.dash_cd.update(dt)
        self.player.update_invuln(dt)

        # Autoshot if holding
        if self.shoot_hold and self.shoot_cd.ready():
            self._player_shoot()

        # Movement
        dx = (self.right - self.left) * 1.0
        dy = (self.up - self.down) * 1.0
        speed = PLAYER_SPEED
        if dx and dy:
            speed *= 0.7071
        if self.player.dashing > 0:
            speed = PLAYER_DASH_SPEED
        self.player.center_x += dx * speed
        self.player.center_y += dy * speed

        # Bounds
        if self.player.left < 10: self.player.left = 10
        if self.player.right > SCREEN_WIDTH - 10: self.player.right = SCREEN_WIDTH - 10
        if self.player.bottom < 62: self.player.bottom = 62
        if self.player.top > SCREEN_HEIGHT - 10: self.player.top = SCREEN_HEIGHT - 10

        # Update bullets
        self.player_bullets.update()
        self.enemy_bullets.update()

        # Minions logic
        for m in list(self.minions):
            m.update_logic(self.player, dt)
            if m.center_x < -40 or m.center_x > SCREEN_WIDTH+40 or m.center_y < -40 or m.center_y > SCREEN_HEIGHT+40:
                m.remove_from_sprite_lists()

        # Power-ups
        self.powerups.update()
        self.powerup_spawn_t -= dt
        if self.powerup_spawn_t <= 0:
            self._spawn_random_powerup()
            self.powerup_spawn_t = random.uniform(*POWERUP_DROP_PERIOD)

        # Boss AI & telegraphs
        if self.boss and self.boss in self.boss_list:
            self._boss_ai(dt)
            self._update_telegraphs(dt)

        # Collisions
        self._handle_collisions()

        # Clean bullets off-screen
        for b in list(self.player_bullets) + list(self.enemy_bullets):
            if b.right < 0 or b.left > SCREEN_WIDTH or b.top < 0 or b.bottom > SCREEN_HEIGHT:
                b.remove_from_sprite_lists()

    # ---------- Input ----------
    def on_key_press(self, key, modifiers):
        if key in (arcade.key.W, arcade.key.UP): self.up = 1
        elif key in (arcade.key.S, arcade.key.DOWN): self.down = 1
        elif key in (arcade.key.A, arcade.key.LEFT): self.left = 1
        elif key in (arcade.key.D, arcade.key.RIGHT): self.right = 1

        elif key == arcade.key.SPACE:
            self.shoot_hold = True
            if self.shoot_cd.ready(): self._player_shoot()

        elif key == arcade.key.Z:
            # melee
            if self.melee_cd.ready():
                self.melee_cd.trigger()
                self._melee_attack()

        elif key == arcade.key.LSHIFT:
            # dash
            if self.dash_cd.ready():
                self.dash_cd.trigger()
                self.player.dashing = PLAYER_DASH_TIME
                self.player.iframes = max(self.player.iframes, PLAYER_IFRAME_TIME)
                # dash impulse toward aim
                vx, vy = self.player.facing_vec()
                self.player.center_x += vx * 16
                self.player.center_y += vy * 16

        elif key == arcade.key.ESCAPE:
            if not self.game_over:
                self.paused = not self.paused
            else:
                menu = MenuView(); self.window.show_view(menu)

        elif key == arcade.key.R:
            self.setup()

        elif key == arcade.key.M:
            menu = MenuView(); self.window.show_view(menu)

    def on_key_release(self, key, modifiers):
        if key in (arcade.key.W, arcade.key.UP): self.up = 0
        elif key in (arcade.key.S, arcade.key.DOWN): self.down = 0
        elif key in (arcade.key.A, arcade.key.LEFT): self.left = 0
        elif key in (arcade.key.D, arcade.key.RIGHT): self.right = 0
        elif key == arcade.key.SPACE:
            self.shoot_hold = False

    def on_mouse_motion(self, x, y, dx, dy):
        self.player.aim_x = x
        self.player.aim_y = y

    def on_mouse_press(self, x, y, button, modifiers):
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.shoot_hold = True
            if self.shoot_cd.ready():
                self._player_shoot()

    def on_mouse_release(self, x, y, button, modifiers):
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.shoot_hold = False

    # ---------- Player combat ----------
    def _player_shoot(self):
        base_cd = 0.18 if self.player.rapid > 0 else BULLET_COOLDOWN
        self.shoot_cd.cooldown = base_cd
        self.shoot_cd.trigger()

        vx, vy = self.player.facing_vec()
        shots = []

        if self.player.spread > 0:
            for a in (-SPREAD_ANGLE, 0.0, SPREAD_ANGLE):
                ca, sa = math.cos(a), math.sin(a)
                dx = vx * ca - vy * sa
                dy = vx * sa + vy * ca
                shots.append((dx, dy))
        else:
            shots.append((vx, vy))

        for dx, dy in shots:
            b = Bullet(self.player.center_x, self.player.center_y, dx, dy, BULLET_SPEED,
                       arcade.color.YELLOW, owner="player", radius=3)
            self.player_bullets.append(b)

    def _melee_attack(self):
        # Punch particles
        for _ in range(10):
            p = arcade.SpriteCircle(3, arcade.color.GOLD)
            p.center_x = self.player.center_x + random.uniform(-8, 8)
            p.center_y = self.player.center_y + random.uniform(-8, 8)
            p.change_x = random.uniform(-2, 2)
            p.change_y = random.uniform(-2, 2)
            p.life = 0.35 + random.random() * 0.25
            self.particles.append(p)

        # Damage boss if close
        if self.boss and self.boss in self.boss_list:
            d = arcade.get_distance(self.player.center_x, self.player.center_y, self.boss.center_x, self.boss.center_y)
            if d <= PLAYER_MELEE_RANGE + self.boss.width/2:
                self._damage_boss(PLAYER_MELEE_DAMAGE)

        # Damage minions in range
        for m in list(self.minions):
            d = arcade.get_distance(self.player.center_x, self.player.center_y, m.center_x, m.center_y)
            if d <= PLAYER_MELEE_RANGE + m.width/2:
                m.health -= PLAYER_MELEE_DAMAGE
                if m.health <= 0:
                    self._minion_die(m)

    # ---------- Boss / enemy logic ----------
    def _boss_ai(self, dt: float):
        b = self.boss
        b.phase_timer += dt

        if b.stage == 1:
            # Simple L/R sway + aimed shot + telegraphed ring blast
            b.center_x += math.sin(b.phase_timer * 0.9) * 1.2
            if b.phase_timer > 1.0:
                b.phase_timer = 0.0
                self._boss_fire_aimed(b, speed=7.0, color=arcade.color.PURPLE)
                # 1-in-3 chance to telegraph a ring
                if random.random() < 0.33:
                    b.telegraphs.append((b.center_x, b.center_y - 10, 28, TELEGRAPH_TIME, "RING"))
        else:
            # Stage 2: fan bursts + dashes + minion spawns + telegraphs
            # Fan every ~1.6s
            if int(b.phase_timer * 10) % 16 == 0 and b.phase_timer % 0.1 < dt:
                self._boss_fire_fan(b, count=7, speed=7.2, spread_deg=42)

            # Dash every 3s with post-dash volley
            if b.phase_timer > 3.0:
                b.phase_timer = 0.0
                self._boss_dash_to_player(b)
                self._boss_fire_fan(b, count=9, speed=7.5, spread_deg=48)

            # Random telegraphed big ring or line
            if random.random() < 0.02:
                kind = random.choice(("RING", "RING", "RING", "RING_BIG"))
                radius = 28 if kind == "RING" else 48
                b.telegraphs.append((b.center_x, b.center_y - 10, radius, TELEGRAPH_TIME, kind))

            # Minions occasionally
            if random.random() < 0.012 and len(self.minions) < 6:
                mx = random.choice((80, SCREEN_WIDTH-80))
                my = SCREEN_HEIGHT - random.randint(120, 180)
                self.minions.append(Minion(mx, my))

    def _update_telegraphs(self, dt: float):
        b = self.boss
        nt = []
        for (x, y, r, tleft, kind) in b.telegraphs:
            tleft -= dt
            if tleft <= 0:
                # fire event
                if kind in ("RING", "RING_BIG"):
                    self._spawn_ring_bullets(x, y, r, count=18 if kind == "RING" else 32, speed=6.8)
                # (room for other kinds)
            else:
                nt.append((x, y, r, tleft, kind))
        b.telegraphs = nt

    def _boss_fire_aimed(self, boss: Boss, speed=7.0, color=arcade.color.PURPLE):
        dx = self.player.center_x - boss.center_x
        dy = self.player.center_y - boss.center_y
        d = math.hypot(dx, dy) or 1.0
        b = Bullet(boss.center_x, boss.center_y, dx/d, dy/d, speed, color, owner="boss", radius=3)
        self.enemy_bullets.append(b)

    def _boss_fire_fan(self, boss: Boss, count=7, speed=7.0, spread_deg=40):
        # fan centered at player
        dx = self.player.center_x - boss.center_x
        dy = self.player.center_y - boss.center_y
        angle = math.atan2(dy, dx)
        spread = math.radians(spread_deg)
        for i in range(count):
            a = angle + spread * (i / (count - 1) - 0.5)
            bdx, bdy = math.cos(a), math.sin(a)
            b = Bullet(boss.center_x, boss.center_y, bdx, bdy, speed, arcade.color.LIGHT_PURPLE, owner="boss", radius=3)
            self.enemy_bullets.append(b)

    def _boss_dash_to_player(self, boss: Boss):
        tx = self.player.center_x + random.uniform(-50, 50)
        ty = min(max(self.player.center_y + 50, SCREEN_HEIGHT//2), SCREEN_HEIGHT - 60)
        # trail particles
        for i in range(14):
            t = i / 14
            x = boss.center_x * (1 - t) + tx * t + random.uniform(-6, 6)
            y = boss.center_y * (1 - t) + ty * t + random.uniform(-6, 6)
            p = arcade.SpriteCircle(4, arcade.color.LIGHT_GRAY)
            p.center_x, p.center_y = x, y
            p.change_x = random.uniform(-0.6, 0.6)
            p.change_y = random.uniform(-0.6, 0.6)
            p.life = 0.45
            self.particles.append(p)
        boss.center_x, boss.center_y = tx, ty

    def _spawn_ring_bullets(self, x, y, r, count=18, speed=6.8):
        for i in range(count):
            a = 2*math.pi * i / count
            dx, dy = math.cos(a), math.sin(a)
            b = Bullet(x, y, dx, dy, speed, arcade.color.SALMON, owner="boss", radius=3)
            self.enemy_bullets.append(b)

    # ---------- Collisions / results ----------
    def _handle_collisions(self):
        # Player bullets vs boss
        if self.boss and self.boss in self.boss_list:
            hits = arcade.check_for_collision_with_list(self.boss, self.player_bullets)
            for b in hits:
                b.remove_from_sprite_lists()
                self._damage_boss(3)

            if self.boss.health <= 0:
                self._boss_die()

        # Player bullets vs minions
        for m in list(self.minions):
            hits = arcade.check_for_collision_with_list(m, self.player_bullets)
            for b in hits:
                b.remove_from_sprite_lists()
                m.health -= 2
            if m.health <= 0:
                self._minion_die(m)

        # Enemy bullets vs player
        hits = arcade.check_for_collision_with_list(self.player, self.enemy_bullets)
        for b in hits:
            b.remove_from_sprite_lists()
            took = self.player.take_hit(1)
            if took and self.player.health <= 0:
                self._end_game(False)
                return

        # Minion touch damage
        for m in list(self.minions):
            if arcade.check_for_collision(self.player, m):
                if self.player.take_hit(1):
                    # small knockback
                    ang = math.atan2(self.player.center_y - m.center_y, self.player.center_x - m.center_x)
                    self.player.center_x += math.cos(ang)*18
                    self.player.center_y += math.sin(ang)*18
                    if self.player.health <= 0:
                        self._end_game(False)
                        return

        # Player vs power-ups
        for p in arcade.check_for_collision_with_list(self.player, self.powerups):
            kind = p.kind
            p.remove_from_sprite_lists()
            if kind == "HEAL":
                self.player.health = min(PLAYER_MAX_HEALTH, self.player.health + HEAL_AMOUNT)
            elif kind == "SHIELD":
                self.player.shield = POWERUP_DURATION
            elif kind == "RAPID":
                self.player.rapid = POWERUP_DURATION
            elif kind == "SPREAD":
                self.player.spread = POWERUP_DURATION

    def _damage_boss(self, dmg: int):
        self.boss.health -= dmg
        # particles
        for _ in range(8):
            p = arcade.SpriteCircle(3, arcade.color.GOLD)
            p.center_x = self.boss.center_x + random.uniform(-8, 8)
            p.center_y = self.boss.center_y + random.uniform(-8, 8)
            p.change_x = random.uniform(-2, 2)
            p.change_y = random.uniform(-2, 2)
            p.life = 0.4
            self.particles.append(p)
        # combo
        self.player.combo = min(COMBO_MAX, self.player.combo + 1)
        self.player.combo_timer = COMBO_WINDOW
        self.score += 10 * self.player.combo
        # chance to drop a power-up shard on big hits
        if random.random() < 0.12:
            self._drop_powerup_near(self.boss.center_x, self.boss.center_y)

    def _boss_die(self):
        # explosion
        for _ in range(26):
            p = arcade.SpriteCircle(4, arcade.color.ORANGE)
            p.center_x = self.boss.center_x + random.uniform(-12, 12)
            p.center_y = self.boss.center_y + random.uniform(-12, 12)
            p.change_x = random.uniform(-4, 4)
            p.change_y = random.uniform(-4, 4)
            p.life = 0.7
            self.particles.append(p)

        self.boss.remove_from_sprite_lists()
        self.score += 200

        if self.stage < BOSS_COUNT:
            # stage transition
            next_story = StoryView(stage=self.stage + 1)
            self.window.show_view(next_story)
        else:
            self._end_game(True)

    def _minion_die(self, m: Minion):
        for _ in range(8):
            p = arcade.SpriteCircle(3, arcade.color.BANGLADESH_GREEN)
            p.center_x = m.center_x + random.uniform(-6, 6)
            p.center_y = m.center_y + random.uniform(-6, 6)
            p.change_x = random.uniform(-2, 2)
            p.change_y = random.uniform(-2, 2)
            p.life = 0.35
            self.particles.append(p)
        m.remove_from_sprite_lists()
        self.score += 25 * self.player.combo
        # small chance to drop powerup
        if random.random() < 0.18:
            self._drop_powerup_near(m.center_x, m.center_y)

    # ---------- Power-ups ----------
    def _spawn_random_powerup(self):
        kind = random.choice(POWERUP_TYPES)
        x = random.randint(80, SCREEN_WIDTH - 80)
        y = random.randint(int(SCREEN_HEIGHT*0.55), int(SCREEN_HEIGHT*0.8))
        self.powerups.append(PowerUp(kind, x, y))

    def _drop_powerup_near(self, x, y):
        kind = random.choice(POWERUP_TYPES)
        dx, dy = random.uniform(-30, 30), random.uniform(-30, 30)
        self.powerups.append(PowerUp(kind, x + dx, y + dy))

    # ---------- End game ----------
    def _end_game(self, win: bool):
        self.game_over = True
        self.win = win
        self.window.show_view(GameOverView(self.score, win))


# ------------------ Game Over ------------------
class GameOverView(arcade.View):
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
        arcade.draw_text(title, SCREEN_WIDTH/2, SCREEN_HEIGHT*0.64, color, 40, anchor_x="center")
        arcade.draw_text(f"Final Score: {self.final_score}", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.52,
                         arcade.color.WHITE, 18, anchor_x="center")
        arcade.draw_text("Press R to Replay", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.38,
                         arcade.color.LIGHT_GRAY, 16, anchor_x="center")
        arcade.draw_text("Press M for Menu   ESC to Quit", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.32,
                         arcade.color.LIGHT_GRAY, 14, anchor_x="center")

    def on_key_press(self, key, modifiers):
        if key == arcade.key.R:
            game = GameView(stage=1); game.setup(); self.window.show_view(game)
        elif key == arcade.key.M:
            self.window.show_view(MenuView())
        elif key == arcade.key.ESCAPE:
            arcade.close_window()


# ------------------ Main ------------------
def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    window.show_view(MenuView())
    arcade.run()

if __name__ == "__main__":
    main()
