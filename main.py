"""
StoryQuest++ — Arena Roguelite (Clarity Pass, Arcade 3.x)

Visual clarity & UX upgrades:
  • High-contrast HUD with text shadows
  • Subtle gradient + grid background (no assets)
  • Telegraphs: filled translucent discs + thick outlines
  • Player/enemy crisp outlines and brighter projectiles
  • Particle alpha decay (cleaner bursts, less smear)
  • Pixel snapping on sprite positions to avoid blur
  • Larger, consistent font sizes; improved spacing

Controls:
  Move:   WASD / Arrows
  Shoot:  SPACE or Left Click (hold)
  Dash:   Left Shift (i-frames)
  Pause:  ESC
  Restart (from pause/over): R
  Menu:   M
"""

import arcade
import math
import random
import time
from typing import Optional, List, Tuple

# ---------------- Window / arena ----------------
SCREEN_WIDTH  = 1000
SCREEN_HEIGHT = 640
SCREEN_TITLE  = "StoryQuest++ — Arena Roguelite (Clarity)"

ARENA_MARGIN = 48
GROUND_Y     = 56
GRID_SPACING = 32

# ---------------- Player ----------------
PLAYER_RADIUS         = 19
PLAYER_MAX_HP         = 9
PLAYER_BASE_SPEED     = 4.0
PLAYER_BASE_DASH_SPEED= 12.0
PLAYER_DASH_TIME      = 0.18
PLAYER_DASH_IFRAME    = 0.36
PLAYER_DASH_CD        = 1.2

# ---------------- Weapons ----------------
BASE_BULLET_SPEED = 11.5
BASE_FIRE_CD      = 0.26
BASE_DAMAGE       = 3
SHOTGUN_SPREAD    = math.radians(12)
SHOTGUN_PELLETS   = 5

# ---------------- XP / Perks ----------------
XP_PER_WAVE_CLEAR = 6
XP_ORB_VALUE      = 1
XP_TO_LEVEL_BASE  = 5

# ---------------- Waves ----------------
TOTAL_WAVES = 5

# ---------------- Colors ----------------
BG_TOP     = (26, 33, 53)     # darker slate
BG_BOTTOM  = (39, 48, 77)     # lighter slate
GRID_COLOR = (255, 255, 255, 18)
UI_COLOR   = arcade.color.ALMOND
TEXT_SHADOW= (0, 0, 0, 180)

DANGER_FILL = (255, 140, 0, 40)    # translucent orange
DANGER_EDGE = arcade.color.YELLOW_ORANGE

BULLET_COLOR_PLAYER = arcade.color.BANANA_YELLOW
BULLET_COLOR_ENEMY  = arcade.color.LIGHT_SALMON

PLAYER_BODY = arcade.color.CYAN
PLAYER_OUT  = arcade.color.WHITE

CHASER_BODY = arcade.color.DARK_ORANGE
SHOOTR_BODY = arcade.color.DARK_CERULEAN
BOMBER_BODY = arcade.color.BRICK_RED
ENEMY_OUT   = arcade.color.WHITE

BOSS_BODY   = arcade.color.ORANGE_RED
BOSS_OUT    = arcade.color.WHITE

# ---------------- Helpers ----------------
def clamp(v, a, b): 
    return a if v < a else b if v > b else v

def snap(x: float) -> float:
    """Pixel snap to avoid sub-pixel blur on lines/sprites."""
    return float(int(round(x)))

def text_shadowed(text, x, y, color, size=16, anchor_x="left", anchor_y="baseline"):
    # shadow
    arcade.draw_text(text, x+1, y-1, TEXT_SHADOW, size, anchor_x=anchor_x, anchor_y=anchor_y)
    # main
    arcade.draw_text(text, x,   y,   color,       size, anchor_x=anchor_x, anchor_y=anchor_y)

class Timer:
    def __init__(self, cd=0.0): self.cd, self.t = cd, 0.0
    def set(self, val: float): self.t = max(0.0, val)
    def ready(self): return self.t <= 0.0
    def trigger(self): self.t = self.cd
    def update(self, dt): 
        if self.t > 0: 
            self.t -= dt
            if self.t < 0: self.t = 0

# ---------------- Perks ----------------
class Perk:
    def __init__(self, name, desc, apply_fn):
        self.name = name; self.desc = desc; self.apply = apply_fn

def perk_pool():
    pool = []
    pool.append(Perk("Damage +2", "Increase bullet damage by 2.", lambda p: setattr(p, "damage", p.damage + 2)))
    pool.append(Perk("Fire Rate +20%", "Shoot faster.", lambda p: setattr(p, "fire_cd", p.fire_cd * 0.8)))
    pool.append(Perk("Spread Shot", "Shotgun: +pellets, cone spread.", lambda p: setattr(p, "has_spread", True)))
    pool.append(Perk("Dash Mastery", "Dash CD -25%, +20% i-frames.", lambda p: (setattr(p, "dash_cd", p.dash_cd * 0.75),
                                                                                setattr(p, "dash_iframe", p.dash_iframe * 1.2))))
    pool.append(Perk("Crit 15%", "15% crit chance (x2 dmg).", lambda p: setattr(p, "crit_chance", min(1.0, p.crit_chance + 0.15))))
    pool.append(Perk("Burn", "Hits ignite for DoT.", lambda p: setattr(p, "burn_on_hit", True)))
    pool.append(Perk("Slow", "Hits slow briefly.", lambda p: setattr(p, "slow_on_hit", True)))
    pool.append(Perk("Regen", "Heal 1 HP every 8s out of combat.", lambda p: setattr(p, "regen_on", True)))
    pool.append(Perk("Magnet", "Bigger XP pickup radius.", lambda p: setattr(p, "magnet_radius", p.magnet_radius + 40)))
    return pool

# ---------------- Sprites ----------------
class Player(arcade.SpriteCircle):
    def __init__(self):
        super().__init__(PLAYER_RADIUS, PLAYER_BODY)
        self.hp_max = PLAYER_MAX_HP
        self.hp     = self.hp_max
        self.speed  = PLAYER_BASE_SPEED

        self.damage       = BASE_DAMAGE
        self.fire_cd      = BASE_FIRE_CD
        self.bullet_speed = BASE_BULLET_SPEED

        self.has_spread   = False
        self.crit_chance  = 0.0
        self.burn_on_hit  = False
        self.slow_on_hit  = False
        self.regen_on     = False
        self.regen_timer  = 8.0
        self.magnet_radius= 90

        self.aim_x = SCREEN_WIDTH/2
        self.aim_y = SCREEN_HEIGHT/2

        self.dash_speed = PLAYER_BASE_DASH_SPEED
        self.dash_time  = PLAYER_DASH_TIME
        self.dash_iframe= PLAYER_DASH_IFRAME
        self.dashing    = 0.0
        self.iframes    = 0.0
        self.dash_cd    = PLAYER_DASH_CD

        self.combo   = 1
        self.combo_t = 0.0

    def facing(self) -> Tuple[float,float]:
        dx, dy = self.aim_x - self.center_x, self.aim_y - self.center_y
        d = math.hypot(dx, dy) or 1.0
        return dx/d, dy/d

    def update_timers(self, dt):
        if self.dashing > 0: self.dashing -= dt
        if self.iframes > 0: self.iframes -= dt
        if self.combo_t > 0:
            self.combo_t -= dt
            if self.combo_t <= 0: self.combo, self.combo_t = 1, 0.0
        if self.regen_on:
            self.regen_timer -= dt
            if self.regen_timer <= 0 and self.hp < self.hp_max:
                self.hp += 1
                self.regen_timer = 8.0

    def take_hit(self, dmg):
        if self.iframes > 0: 
            return False
        self.hp -= dmg
        self.combo = 1
        self.combo_t = 0
        return True

class Enemy(arcade.SpriteCircle):
    def __init__(self, r, color):
        super().__init__(r, color)
        self.hp = 1; self.max_hp = 1
        self.slow_t = 0.0
        self.burn_t = 0.0
        self.burn_tick = 0.0
    def apply_status(self, burn: bool, slow: bool):
        if burn: self.burn_t = max(self.burn_t, 2.0)
        if slow: self.slow_t = max(self.slow_t, 1.2)
    def update_status(self, dt, apply_burn_damage):
        if self.slow_t > 0: self.slow_t -= dt
        if self.burn_t > 0:
            self.burn_t -= dt
            self.burn_tick -= dt
            if self.burn_tick <= 0:
                self.burn_tick = 0.5
                apply_burn_damage(1)

class Chaser(Enemy):
    def __init__(self, x, y):
        super().__init__(12, CHASER_BODY)
        self.center_x, self.center_y = x, y
        self.hp = self.max_hp = 5
    def step(self, player: Player, dt):
        dx, dy = player.center_x - self.center_x, player.center_y - self.center_y
        d = math.hypot(dx, dy) or 1
        s = 2.5 * (0.6 if self.slow_t>0 else 1.0)
        self.center_x = snap(self.center_x + (dx/d) * s)
        self.center_y = snap(self.center_y + (dy/d) * s)

class Shooter(Enemy):
    def __init__(self, x, y):
        super().__init__(12, SHOOTR_BODY)
        self.center_x, self.center_y = x, y
        self.hp = self.max_hp = 7
        self.t = 0.0
    def step(self, player: Player, dt):
        self.t += dt
        self.center_x = snap(self.center_x + math.sin(self.t*1.5) * (1.6 if self.slow_t<=0 else 0.8))
        self.center_y = snap(self.center_y + math.cos(self.t*1.1) * 0.4)

class Bomber(Enemy):
    def __init__(self, x, y):
        super().__init__(13, BOMBER_BODY)
        self.center_x, self.center_y = x, y
        self.hp = self.max_hp = 8
        self.telegraphs: List[Tuple[float,float,float,float,str]] = []
        self.t = 0.0
    def step(self, player: Player, dt):
        self.t += dt
        self.center_y = snap(self.center_y - (1.1 if self.slow_t<=0 else 0.6))

class Bullet(arcade.SpriteCircle):
    def __init__(self, x, y, dx, dy, speed, color, owner: str, radius=3):
        super().__init__(radius, color)
        self.center_x, self.center_y = x, y
        self.change_x, self.change_y = dx*speed, dy*speed
        self.owner = owner

class XPOrb(arcade.SpriteCircle):
    def __init__(self, x, y):
        super().__init__(6, arcade.color.SPRING_BUD)
        self.center_x, self.center_y = x, y
        self.vx = random.uniform(-0.8,0.8)
        self.vy = random.uniform(0.6,1.2)
    def update(self):
        self.center_x += self.vx
        self.center_y += self.vy
        self.vx *= 0.98
        self.vy = self.vy*0.98 - 0.02

class Boss(arcade.SpriteCircle):
    def __init__(self):
        super().__init__(44, BOSS_BODY)
        self.center_x = SCREEN_WIDTH/2
        self.center_y = SCREEN_HEIGHT-150
        self.max_hp = 220; self.hp = self.max_hp
        self.phase_timer = 0.0
        self.telegraphs: List[Tuple[float,float,float,float,str]] = []
        self.phase = 1
    def hp_norm(self): return max(0.0, self.hp / self.max_hp)

# ---------------- Views ----------------
class MenuView(arcade.View):
    def on_show(self):
        arcade.set_background_color(BG_BOTTOM)
    def on_draw(self):
        self.clear()
        self._draw_background()
        text_shadowed("STORYQUEST++", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.68, arcade.color.GOLD, 40, anchor_x="center")
        text_shadowed("Clarity pass: higher contrast HUD • sharper telegraphs • cleaner visuals", 
                      SCREEN_WIDTH/2, SCREEN_HEIGHT*0.60, arcade.color.LIGHT_GRAY, 16, anchor_x="center")
        text_shadowed("WASD move • SPACE/LeftClick shoot • LSHIFT dash • ESC pause",
                      SCREEN_WIDTH/2, SCREEN_HEIGHT*0.54, arcade.color.WHITE, 12, anchor_x="center")
        text_shadowed("Press ENTER to Start", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.30, arcade.color.LIGHT_GREEN, 22, anchor_x="center")
        text_shadowed("Press ESC to Quit", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.25, arcade.color.LIGHT_GRAY, 14, anchor_x="center")
    def _draw_background(self):
        # Gradient
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT, BG_BOTTOM)
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, SCREEN_HEIGHT*0.55, SCREEN_HEIGHT, BG_TOP)
        # Grid
        for x in range(ARENA_MARGIN, SCREEN_WIDTH-ARENA_MARGIN+1, GRID_SPACING):
            arcade.draw_line(x, GROUND_Y, x, SCREEN_HEIGHT-ARENA_MARGIN, GRID_COLOR, 1)
        for y in range(GROUND_Y, SCREEN_HEIGHT-ARENA_MARGIN+1, GRID_SPACING):
            arcade.draw_line(ARENA_MARGIN, y, SCREEN_WIDTH-ARENA_MARGIN, y, GRID_COLOR, 1)
    def on_key_press(self, key, modifiers):
        if key in (arcade.key.ENTER, arcade.key.RETURN):
            gv = GameView(); gv.setup(); self.window.show_view(gv)
        elif key == arcade.key.ESCAPE:
            arcade.close_window()

class PerkDraftView(arcade.View):
    def __init__(self, game: "GameView", options: List[Perk]):
        super().__init__()
        self.game = game
        self.options = options
        self.selected = 0
    def on_show(self):
        arcade.set_background_color(BG_BOTTOM)
    def on_draw(self):
        self.clear()
        self._draw_background()
        text_shadowed("Choose a Perk", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.72, arcade.color.GOLD, 28, anchor_x="center")
        for i, perk in enumerate(self.options):
            y = SCREEN_HEIGHT*0.52 - i*84
            col = arcade.color.LIGHT_GREEN if i==self.selected else arcade.color.LIGHT_GRAY
            arcade.draw_rectangle_filled(SCREEN_WIDTH/2, y, 680, 64, (0,0,0,140))
            text_shadowed(perk.name, SCREEN_WIDTH/2 - 320, y+12, col, 18)
            text_shadowed(perk.desc, SCREEN_WIDTH/2 - 320, y-12, arcade.color.WHITE, 12)
        text_shadowed("↑/↓ to select • ENTER to confirm", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.20, arcade.color.WHITE, 12, anchor_x="center")
    def _draw_background(self):
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT, BG_BOTTOM)
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, SCREEN_HEIGHT*0.55, SCREEN_HEIGHT, BG_TOP)
    def on_key_press(self, key, modifiers):
        if key in (arcade.key.UP, arcade.key.W): self.selected = (self.selected - 1) % len(self.options)
        elif key in (arcade.key.DOWN, arcade.key.S): self.selected = (self.selected + 1) % len(self.options)
        elif key in (arcade.key.ENTER, arcade.key.RETURN):
            self.options[self.selected].apply(self.game.player)
            self.window.show_view(self.game)

class GameOverView(arcade.View):
    def __init__(self, score: int, win: bool, seconds: float):
        super().__init__()
        self.score = score; self.win = win; self.seconds = seconds
    def on_show(self):
        arcade.set_background_color(BG_BOTTOM)
    def on_draw(self):
        self.clear()
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT, BG_BOTTOM)
        title = "VICTORY!" if self.win else "DEFEAT"
        color = arcade.color.LIGHT_GREEN if self.win else arcade.color.SALMON
        text_shadowed(title, SCREEN_WIDTH/2, SCREEN_HEIGHT*0.64, color, 40, anchor_x="center")
        text_shadowed(f"Score: {self.score}", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.54, arcade.color.WHITE, 18, anchor_x="center")
        text_shadowed(f"Time: {int(self.seconds)}s", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.48, arcade.color.WHITE, 16, anchor_x="center")
        text_shadowed("R: Replay   M: Menu   ESC: Quit", SCREEN_WIDTH/2, SCREEN_HEIGHT*0.34, arcade.color.LIGHT_GRAY, 16, anchor_x="center")
    def on_key_press(self, key, modifiers):
        if key == arcade.key.R:
            g = GameView(); g.setup(); self.window.show_view(g)
        elif key == arcade.key.M:
            self.window.show_view(MenuView())
        elif key == arcade.key.ESCAPE:
            arcade.close_window()

# ---------------- Game View ----------------
class GameView(arcade.View):
    def __init__(self):
        super().__init__()
        self.player: Optional[Player] = None
        self.player_list = arcade.SpriteList()
        self.enemy_list  = arcade.SpriteList()
        self.boss_list   = arcade.SpriteList()
        self.bullets     = arcade.SpriteList()
        self.enemy_bullets = arcade.SpriteList()
        self.xp_orbs     = arcade.SpriteList()
        self.particles   = arcade.SpriteList()

        self.up=self.down=self.left=self.right=0
        self.shoot_hold=False

        self.fire_timer = Timer(BASE_FIRE_CD)
        self.dash_timer = Timer(PLAYER_DASH_CD)

        self.wave = 1
        self.wave_active = True
        self.wave_clear_bonus_pending = False

        self.xp = 0
        self.level = 1
        self.score = 0
        self.paused = False
        self.start_time = 0.0
        self.end_time = 0.0

        self.intro_t = 0.9

    # ---------- setup ----------
    def setup(self):
        arcade.set_background_color(BG_BOTTOM)
        self.player_list = arcade.SpriteList()
        self.enemy_list  = arcade.SpriteList()
        self.boss_list   = arcade.SpriteList()
        self.bullets     = arcade.SpriteList()
        self.enemy_bullets = arcade.SpriteList()
        self.xp_orbs     = arcade.SpriteList()
        self.particles   = arcade.SpriteList()

        self.player = Player()
        self.player.center_x = SCREEN_WIDTH/2
        self.player.center_y = GROUND_Y + 60
        self.player_list.append(self.player)

        self.fire_timer = Timer(self.player.fire_cd)
        self.dash_timer = Timer(self.player.dash_cd)

        self.wave = 1
        self.wave_active = True
        self.wave_clear_bonus_pending = False
        self.xp = 0
        self.level = 1
        self.score = 0
        self.paused = False
        self.intro_t = 0.9
        self.start_time = time.time()

        self._spawn_wave(self.wave)

    # ---------- spawning ----------
    def _spawn_wave(self, w):
        rngx = lambda: random.randint(ARENA_MARGIN, SCREEN_WIDTH-ARENA_MARGIN)
        top = SCREEN_HEIGHT - 80
        if w < TOTAL_WAVES:
            for _ in range(4 + w):
                self.enemy_list.append(Chaser(rngx(), top))
            for _ in range(2 + w//2):
                self.enemy_list.append(Shooter(rngx(), top - random.randint(0,120)))
            for _ in range(1 + (w//2)):
                self.enemy_list.append(Bomber(rngx(), top - random.randint(40,140)))
        else:
            self.boss_list.append(Boss())

    # ---------- drawing ----------
    def _draw_background(self):
        # Gradient sky
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT, BG_BOTTOM)
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, SCREEN_HEIGHT*0.55, SCREEN_HEIGHT, BG_TOP)
        # Ground slab
        arcade.draw_rectangle_filled(SCREEN_WIDTH/2, GROUND_Y, SCREEN_WIDTH-40, 92, arcade.color.DARK_OLIVE_GREEN)
        # Arena border
        arcade.draw_lrbt_rectangle_outline(ARENA_MARGIN, SCREEN_WIDTH-ARENA_MARGIN, GROUND_Y, SCREEN_HEIGHT-ARENA_MARGIN, arcade.color.WHITE, 2)
        # Grid lines inside arena (subtle)
        for x in range(ARENA_MARGIN, SCREEN_WIDTH-ARENA_MARGIN+1, GRID_SPACING):
            arcade.draw_line(x, GROUND_Y, x, SCREEN_HEIGHT-ARENA_MARGIN, GRID_COLOR, 1)
        for y in range(GROUND_Y, SCREEN_HEIGHT-ARENA_MARGIN+1, GRID_SPACING):
            arcade.draw_line(ARENA_MARGIN, y, SCREEN_WIDTH-ARENA_MARGIN, y, GRID_COLOR, 1)

    def _draw_telegraphs(self):
        # Bombers
        for e in self.enemy_list:
            if isinstance(e, Bomber):
                for (x,y,r,t,kind) in e.telegraphs:
                    alpha = int(60 + 120*(t/0.9))
                    arcade.draw_circle_filled(x, y, r, DANGER_FILL)
                    arcade.draw_circle_outline(x, y, r, (*DANGER_EDGE[:3], alpha), 3)
        # Boss
        for b in self.boss_list:
            for (x,y,r,t,kind) in b.telegraphs:
                alpha = int(60 + 120*(t/0.9))
                arcade.draw_circle_filled(x, y, r, DANGER_FILL)
                arcade.draw_circle_outline(x, y, r, (*DANGER_EDGE[:3], alpha), 3)

    def _draw_player_outline(self):
        # simple white outline for clarity
        arcade.draw_circle_outline(self.player.center_x, self.player.center_y, PLAYER_RADIUS+2, PLAYER_OUT, 2)

    def _draw_enemy_outlines(self):
        for e in self.enemy_list:
            arcade.draw_circle_outline(e.center_x, e.center_y, e.width/2+2, ENEMY_OUT, 2)
        for b in self.boss_list:
            arcade.draw_circle_outline(b.center_x, b.center_y, b.width/2+3, BOSS_OUT, 3)

    def on_draw(self):
        self.clear()
        self._draw_background()
        self._draw_telegraphs()

        # Sprites
        self.player_list.draw()
        self._draw_player_outline()
        self.enemy_list.draw()
        self._draw_enemy_outlines()
        self.boss_list.draw()
        self.bullets.draw()
        self.enemy_bullets.draw()
        self.xp_orbs.draw()

        # Particles (manual: apply alpha decay)
        for p in list(self.particles):
            life = getattr(p, "life", 0.0)
            if life <= 0:
                p.remove_from_sprite_lists()
            else:
                alpha = int(255 * min(1.0, life / 0.5))
                p.color = (p.color[0], p.color[1], p.color[2], max(40, min(255, alpha)))
                p.center_x = snap(p.center_x + getattr(p, "change_x", 0.0))
                p.center_y = snap(p.center_y + getattr(p, "change_y", 0.0))
                p.life = life - 1/60

        self.particles.draw()

        # Crosshair (always visible)
        arcade.draw_circle_outline(self.player.aim_x, self.player.aim_y, 11, arcade.color.LIGHT_GRAY, 2)

        # HUD
        self._draw_hud()

        # Intro/pause overlays
        if self.intro_t > 0:
            a = int(min(self.intro_t*400, 220))
            arcade.draw_rectangle_filled(SCREEN_WIDTH/2, SCREEN_HEIGHT/2, SCREEN_WIDTH, SCREEN_HEIGHT, (0,0,0,a))
            title = f"Wave {self.wave}" if self.wave < TOTAL_WAVES else "Boss"
            text_shadowed(title, SCREEN_WIDTH/2, SCREEN_HEIGHT/2 + 8, arcade.color.WHITE, 30, anchor_x="center")

        if self.paused:
            arcade.draw_rectangle_filled(SCREEN_WIDTH/2, SCREEN_HEIGHT/2, 560, 180, (0,0,0,200))
            text_shadowed("PAUSED", SCREEN_WIDTH/2, SCREEN_HEIGHT/2 + 26, arcade.color.GOLD, 28, anchor_x="center")
            text_shadowed("ESC: resume   R: restart   M: menu", SCREEN_WIDTH/2, SCREEN_HEIGHT/2 - 12, arcade.color.LIGHT_GRAY, 14, anchor_x="center")

    def _draw_hud(self):
        # HP
        text_shadowed(f"HP {self.player.hp}/{self.player.hp_max}", 12, SCREEN_HEIGHT-24, UI_COLOR, 18)
        # XP
        need = self._xp_needed()
        text_shadowed(f"LV {self.level}", 12, SCREEN_HEIGHT-48, UI_COLOR, 14)
        bar_w = 220
        filled = int(bar_w * (self.xp/need))
        arcade.draw_lrbt_rectangle_outline(12, 12+bar_w, SCREEN_HEIGHT-62, SCREEN_HEIGHT-48, arcade.color.WHITE, 2)
        if filled>0:
            arcade.draw_rectangle_filled(12+filled/2, SCREEN_HEIGHT-55, filled, 12, arcade.color.SPRING_BUD)
        # Wave & score
        text_shadowed(f"Wave {self.wave}/{TOTAL_WAVES}", 12, SCREEN_HEIGHT-82, UI_COLOR, 14)
        text_shadowed(f"Score {self.score}", 12, SCREEN_HEIGHT-102, UI_COLOR, 14)
        # Dash indicator
        dash_msg = "Ready" if self.dash_timer.ready() else f"{self.dash_timer.t:.1f}s"
        text_shadowed(f"Dash: {dash_msg}", 12, SCREEN_HEIGHT-122, arcade.color.LIGHT_GRAY, 12)
        # Boss bar
        if len(self.boss_list):
            b: Boss = self.boss_list[0]
            bw, bx, by = 460, SCREEN_WIDTH-20-460, SCREEN_HEIGHT-42
            arcade.draw_lrbt_rectangle_outline(bx-2, bx+bw+2, by-12, by+12, arcade.color.WHITE, 2)
            fill_w = int(bw * b.hp_norm())
            if fill_w>0:
                arcade.draw_rectangle_filled(bx+fill_w/2, by, fill_w, 20, arcade.color.RED)
            text_shadowed("BOSS", bx + bw/2, by-10, arcade.color.WHITE, 12, anchor_x="center")

    # ---------- update ----------
    def on_update(self, dt: float):
        if self.paused: return
        if self.intro_t > 0: self.intro_t -= dt; return

        self.fire_timer.cd = self.player.fire_cd
        self.dash_timer.cd = self.player.dash_cd
        self.fire_timer.update(dt); self.dash_timer.update(dt)
        self.player.update_timers(dt)

        # shooting
        if self.shoot_hold and self.fire_timer.ready():
            self._player_shoot()

        # movement with pixel snap
        dx = (self.right - self.left); dy = (self.up - self.down)
        speed = self.player.speed
        if dx and dy: speed *= 0.7071
        if self.player.dashing>0: speed = self.player.dash_speed
        self.player.center_x = snap(self.player.center_x + dx * speed)
        self.player.center_y = snap(self.player.center_y + dy * speed)

        # bounds
        if self.player.left < ARENA_MARGIN: self.player.left = ARENA_MARGIN
        if self.player.right > SCREEN_WIDTH-ARENA_MARGIN: self.player.right = SCREEN_WIDTH-ARENA_MARGIN
        if self.player.bottom < GROUND_Y: self.player.bottom = GROUND_Y
        if self.player.top > SCREEN_HEIGHT-ARENA_MARGIN: self.player.top = SCREEN_HEIGHT-ARENA_MARGIN

        # bullets & xp
        self.bullets.update()
        self.enemy_bullets.update()
        self.xp_orbs.update()

        # xp magnet
        for orb in self.xp_orbs:
            d = arcade.get_distance(self.player.center_x, self.player.center_y, orb.center_x, orb.center_y)
            if d < self.player.magnet_radius:
                vx, vy = (self.player.center_x - orb.center_x) / (d or 1), (self.player.center_y - orb.center_y) / (d or 1)
                orb.center_x = snap(orb.center_x + vx * 4.2)
                orb.center_y = snap(orb.center_y + vy * 4.2)

        # enemies
        for e in list(self.enemy_list):
            e.update_status(dt, lambda dmg, _e=e: setattr(_e, "hp", _e.hp - dmg))
            if isinstance(e, (Chaser, Shooter, Bomber)):
                e.step(self.player, dt)
            if e.hp <= 0:
                self._enemy_die(e)

        # bombers: telegraph -> detonate
        for e in self.enemy_list:
            if isinstance(e, Bomber):
                if random.random() < (0.005 if e.slow_t<=0 else 0.003):
                    e.telegraphs.append((e.center_x, e.center_y-4, 36, 0.9, "RING"))
                nt=[]
                for (x,y,r,t,k) in e.telegraphs:
                    t -= dt
                    if t<=0:
                        self._spawn_ring_bullets(x,y,r, count=16, speed=6.2)
                    else: nt.append((x,y,r,t,k))
                e.telegraphs = nt

        # boss AI
        if len(self.boss_list):
            self._boss_logic(dt)

        # collisions
        self._handle_collisions()

        # clean bullets
        for b in list(self.bullets)+list(self.enemy_bullets):
            if b.right<ARENA_MARGIN or b.left>SCREEN_WIDTH-ARENA_MARGIN or b.top>SCREEN_HEIGHT-ARENA_MARGIN or b.bottom<GROUND_Y:
                b.remove_from_sprite_lists()

        # wave progression
        if self.wave < TOTAL_WAVES and not len(self.enemy_list) and not self.wave_clear_bonus_pending:
            self.wave_clear_bonus_pending = True
            for _ in range(XP_PER_WAVE_CLEAR):
                self.xp_orbs.append(XPOrb(self.player.center_x+random.uniform(-20,20), self.player.center_y+random.uniform(-10,10)))
            arcade.schedule(self._start_next_wave, 1.2)
        if self.wave == TOTAL_WAVES and not len(self.boss_list):
            self._win()

    # ---------- boss ----------
    def _boss_logic(self, dt):
        b: Boss = self.boss_list[0]
        b.phase_timer += dt
        if b.phase==1 and b.hp < b.max_hp*0.5:
            b.phase=2; b.phase_timer = 0.0
        b.center_x = snap(b.center_x + math.sin(b.phase_timer*0.9) * (1.6 if b.phase==2 else 1.2))
        if b.phase==1:
            if b.phase_timer>1.0:
                b.phase_timer=0.0
                self._boss_fire_aimed(b, speed=7.4, color=arcade.color.PURPLE)
                if random.random()<0.35:
                    b.telegraphs.append((b.center_x, b.center_y-6, 40, 0.9, "RING"))
        else:
            if int(b.phase_timer*10)%16==0 and b.phase_timer%0.1<dt:
                self._boss_fire_fan(b, count=9, spread_deg=54, speed=7.8)
            if b.phase_timer>3.0:
                b.phase_timer=0.0
                self._boss_dash_to_player(b)
                self._boss_fire_fan(b, count=11, spread_deg=60, speed=8.2)
            if random.random()<0.018 and len(self.enemy_list)<10:
                self.enemy_list.append(Chaser(random.randint(ARENA_MARGIN, SCREEN_WIDTH-ARENA_MARGIN), SCREEN_HEIGHT-120))
            if random.random()<0.012 and len(self.enemy_list)<12:
                self.enemy_list.append(Shooter(random.randint(ARENA_MARGIN, SCREEN_WIDTH-ARENA_MARGIN), SCREEN_HEIGHT-150))
            if random.random()<0.018:
                b.telegraphs.append((b.center_x, b.center_y-8, random.choice((42,52)), 0.9, "RING_BIG"))
        nt=[]
        for (x,y,r,t,k) in b.telegraphs:
            t -= dt
            if t<=0:
                self._spawn_ring_bullets(x,y,r, count=24 if k=="RING" else 36, speed=7.0)
            else:
                nt.append((x,y,r,t,k))
        b.telegraphs = nt

    def _boss_fire_aimed(self, boss: Boss, speed=7.0, color=arcade.color.PURPLE):
        dx,dy = self.player.center_x-boss.center_x, self.player.center_y-boss.center_y
        d = math.hypot(dx,dy) or 1
        self.enemy_bullets.append(Bullet(boss.center_x, boss.center_y, dx/d, dy/d, speed, color, "enemy"))

    def _boss_fire_fan(self, boss: Boss, count=7, spread_deg=40, speed=7.0):
        dx,dy = self.player.center_x-boss.center_x, self.player.center_y-boss.center_y
        base = math.atan2(dy,dx); spread = math.radians(spread_deg)
        for i in range(count):
            ang = base + spread*(i/(count-1)-0.5)
            self.enemy_bullets.append(Bullet(boss.center_x, boss.center_y, math.cos(ang), math.sin(ang),
                                             speed, arcade.color.LIGHT_PURPLE, "enemy"))

    def _boss_dash_to_player(self, boss: Boss):
        tx = self.player.center_x + random.uniform(-60,60)
        ty = min(max(self.player.center_y+60, SCREEN_HEIGHT/2), SCREEN_HEIGHT-ARENA_MARGIN-20)
        for i in range(16):
            t = i/16
            x = boss.center_x*(1-t)+tx*t + random.uniform(-6,6)
            y = boss.center_y*(1-t)+ty*t + random.uniform(-6,6)
            p = arcade.SpriteCircle(4, arcade.color.LIGHT_GRAY)
            p.center_x, p.center_y = x, y
            p.change_x = random.uniform(-0.6,0.6)
            p.change_y = random.uniform(-0.6,0.6)
            p.life = 0.5
            self.particles.append(p)
        boss.center_x, boss.center_y = snap(tx), snap(ty)

    def _spawn_ring_bullets(self, x, y, r, count=18, speed=6.6):
        for i in range(count):
            a = 2*math.pi*i/count
            self.enemy_bullets.append(Bullet(x,y,math.cos(a),math.sin(a),speed, BULLET_COLOR_ENEMY, "enemy"))

    # ---------- collisions ----------
    def _handle_collisions(self):
        # player bullets vs enemies
        for e in list(self.enemy_list):
            hits = arcade.check_for_collision_with_list(e, self.bullets)
            if hits:
                for b in hits:
                    b.remove_from_sprite_lists()
                    dmg = self.player.damage * (2 if random.random()<self.player.crit_chance else 1)
                    e.hp -= dmg
                    e.apply_status(self.player.burn_on_hit, self.player.slow_on_hit)
                self._hit_particles(e.center_x, e.center_y, color=arcade.color.GOLD)
                if e.hp <= 0:
                    self._enemy_die(e)
        # player bullets vs boss
        if len(self.boss_list):
            boss = self.boss_list[0]
            hits = arcade.check_for_collision_with_list(boss, self.bullets)
            for proj in hits:
                proj.remove_from_sprite_lists()
                dmg = self.player.damage * (2 if random.random()<self.player.crit_chance else 1)
                boss.hp -= dmg
                self._hit_particles(boss.center_x, boss.center_y, color=arcade.color.GOLD)
                self.player.combo = min(5, self.player.combo+1)
                self.player.combo_t = 3.0
                self.score += 8 * self.player.combo
            if boss.hp <= 0:
                self._boss_die(boss)
        # enemy bullets vs player
        pb = arcade.check_for_collision_with_list(self.player, self.enemy_bullets)
        for proj in pb:
            proj.remove_from_sprite_lists()
            if self.player.take_hit(1) and self.player.hp <= 0:
                self._lose(); return
        # enemy touch
        for e in list(self.enemy_list):
            if arcade.check_for_collision(self.player, e):
                if self.player.take_hit(1) and self.player.hp <= 0:
                    self._lose(); return
                ang = math.atan2(self.player.center_y - e.center_y, self.player.center_x - e.center_x)
                self.player.center_x = snap(self.player.center_x + math.cos(ang)*16)
                self.player.center_y = snap(self.player.center_y + math.sin(ang)*16)
        # boss touch
        for b in self.boss_list:
            if arcade.check_for_collision(self.player, b):
                if self.player.take_hit(1) and self.player.hp<=0:
                    self._lose(); return
        # xp pickup
        for o in arcade.check_for_collision_with_list(self.player, self.xp_orbs):
            o.remove_from_sprite_lists()
            self._gain_xp(XP_ORB_VALUE)

    def _enemy_die(self, e: Enemy):
        self._hit_particles(e.center_x, e.center_y, count=10, color=arcade.color.BANGLADESH_GREEN)
        e.remove_from_sprite_lists()
        self.score += 12 * self.player.combo
        if random.random()<0.9:
            self.xp_orbs.append(XPOrb(e.center_x, e.center_y))

    def _boss_die(self, boss: Boss):
        for _ in range(28):
            self._hit_particles(boss.center_x+random.uniform(-12,12), boss.center_y+random.uniform(-12,12),
                                count=1, color=arcade.color.ORANGE, vel=4.0)
        boss.remove_from_sprite_lists()
        self.score += 400
        self._win()

    # ---------- XP / level ----------
    def _xp_needed(self): return XP_TO_LEVEL_BASE + (self.level-1)*2
    def _gain_xp(self, amount):
        self.xp += amount
        need = self._xp_needed()
        if self.xp >= need:
            self.xp -= need
            self.level += 1
            self._offer_perk()

    def _offer_perk(self):
        choices = random.sample(perk_pool(), 3)
        self.window.show_view(PerkDraftView(self, choices))

    # ---------- shooting ----------
    def _player_shoot(self):
        self.fire_timer.trigger()
        vx, vy = self.player.facing()
        if self.player.has_spread:
            spread = SHOTGUN_SPREAD
            for i in range(SHOTGUN_PELLETS):
                t = i/(SHOTGUN_PELLETS-1) - 0.5
                a = math.atan2(vy,vx) + spread*t
                self.bullets.append(Bullet(self.player.center_x, self.player.center_y,
                                            math.cos(a), math.sin(a),
                                            self.player.bullet_speed, BULLET_COLOR_PLAYER, "player"))
        else:
            self.bullets.append(Bullet(self.player.center_x, self.player.center_y, vx, vy,
                                       self.player.bullet_speed, BULLET_COLOR_PLAYER, "player"))

    # ---------- visuals ----------
    def _hit_particles(self, x, y, count=8, color=arcade.color.GOLD, vel=2.2):
        for _ in range(count):
            p = arcade.SpriteCircle(3, color)
            p.center_x = x + random.uniform(-6,6)
            p.center_y = y + random.uniform(-6,6)
            p.change_x = random.uniform(-vel,vel)
            p.change_y = random.uniform(-vel,vel)
            p.life = 0.45
            self.particles.append(p)

    # ---------- wave flow ----------
    def _start_next_wave(self, dt):
        arcade.unschedule(self._start_next_wave)
        if self.wave < TOTAL_WAVES-1:
            self.wave += 1
            self.wave_clear_bonus_pending = False
            self.intro_t = 0.9
            self._spawn_wave(self.wave)
        elif self.wave == TOTAL_WAVES-1:
            self.wave = TOTAL_WAVES
            self.wave_clear_bonus_pending = False
            self.intro_t = 0.9
            self._spawn_wave(self.wave)

    def _win(self):
        self.end_time = time.time()
        self.window.show_view(GameOverView(self.score, True, self.end_time-self.start_time))
    def _lose(self):
        self.end_time = time.time()
        self.window.show_view(GameOverView(self.score, False, self.end_time-self.start_time))

    # ---------- input ----------
    def on_key_press(self, key, modifiers):
        if key in (arcade.key.W, arcade.key.UP): self.up = 1
        elif key in (arcade.key.S, arcade.key.DOWN): self.down = 1
        elif key in (arcade.key.A, arcade.key.LEFT): self.left = 1
        elif key in (arcade.key.D, arcade.key.RIGHT): self.right = 1
        elif key == arcade.key.SPACE:
            self.shoot_hold = True
            if self.fire_timer.ready(): self._player_shoot()
        elif key == arcade.key.LSHIFT:
            if self.dash_timer.ready():
                self.dash_timer.trigger()
                self.player.dashing = self.player.dash_time
                self.player.iframes = max(self.player.iframes, self.player.dash_iframe)
                vx,vy = self.player.facing()
                self.player.center_x = snap(self.player.center_x + vx*20)
                self.player.center_y = snap(self.player.center_y + vy*20)
        elif key == arcade.key.ESCAPE:
            self.paused = not self.paused
        elif key == arcade.key.R:
            if self.paused:
                self.setup()
        elif key == arcade.key.M:
            self.window.show_view(MenuView())

    def on_key_release(self, key, modifiers):
        if key in (arcade.key.W, arcade.key.UP): self.up = 0
        elif key in (arcade.key.S, arcade.key.DOWN): self.down = 0
        elif key in (arcade.key.A, arcade.key.LEFT): self.left = 0
        elif key in (arcade.key.D, arcade.key.RIGHT): self.right = 0
        elif key == arcade.key.SPACE: self.shoot_hold = False

    def on_mouse_motion(self, x, y, dx, dy):
        self.player.aim_x, self.player.aim_y = snap(x), snap(y)
    def on_mouse_press(self, x, y, button, modifiers):
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.shoot_hold = True
            if self.fire_timer.ready(): self._player_shoot()
    def on_mouse_release(self, x, y, button, modifiers):
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.shoot_hold = False

# ---------------- Main ----------------
def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    window.show_view(MenuView())
    arcade.run()

if __name__ == "__main__":
    main()
