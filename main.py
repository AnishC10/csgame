# minion_escape_plus_fixed.py
import arcade
import random
import math
from enum import Enum

# --------------------- CONFIG ---------------------
SCREEN_WIDTH = 900
SCREEN_HEIGHT = 650
SCREEN_TITLE = "Minion Escape: Upgrade Edition"

PLAYER_SPEED = 5.5
PLAYER_MAX_HEALTH = 100

BULLET_SPEED = 12
BULLET_LIFETIME = 2.0  # seconds
PLAYER_FIRE_COOLDOWN = 0.35  # seconds (base)

MINION_BASE_COUNT = 4
MINION_BASE_SPEED = 2.0
MINION_BASE_HEALTH = 18

BOSS_HEALTH = 300
BOSS_SPEED = 1.6

POWERUP_SIZE = 20
POWERUP_DURATION = 6.0  # seconds for temporary buffs

# Colors
COLOR_BG = arcade.color.ANTIQUE_WHITE
COLOR_PLAYER = arcade.color.BLUE_GRAY
COLOR_BULLET = arcade.color.BLACK
COLOR_MINION = arcade.color.YELLOW_ORANGE
COLOR_MINION_ANGRY = arcade.color.RED_ORANGE
COLOR_BOSS = arcade.color.DARK_RED
COLOR_HEALTH_BAR_BG = arcade.color.LIGHT_GRAY
COLOR_HEALTH_BAR = arcade.color.GREEN
COLOR_TEXT = arcade.color.DARK_SLATE_GRAY

# --------------------- UTIL ---------------------
def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)

# --------------------- GAME STATES ---------------------
class GameState(Enum):
    MENU = 1
    PLAYING = 2
    LEVEL_TRANSITION = 3
    GAME_OVER = 4
    VICTORY = 5
    INSTRUCTIONS = 6

# --------------------- SPRITES ---------------------
class Player(arcade.SpriteSolidColor):
    def __init__(self):
        super().__init__(32, 32, COLOR_PLAYER)
        self.center_x = SCREEN_WIDTH // 2
        self.center_y = SCREEN_HEIGHT // 2
        self.health = PLAYER_MAX_HEALTH
        self.max_health = PLAYER_MAX_HEALTH
        self.speed = PLAYER_SPEED
        self.fire_cooldown = PLAYER_FIRE_COOLDOWN
        self.fire_timer = 0.0
        self.double_damage = False
        self.rapid_fire = False
        self.rapid_fire_timer = 0.0
        self.double_damage_timer = 0.0

    def update_powerups(self, delta_time):
        if self.rapid_fire:
            self.rapid_fire_timer -= delta_time
            if self.rapid_fire_timer <= 0:
                self.rapid_fire = False
                self.fire_cooldown = PLAYER_FIRE_COOLDOWN

        if self.double_damage:
            self.double_damage_timer -= delta_time
            if self.double_damage_timer <= 0:
                self.double_damage = False

class Bullet(arcade.SpriteSolidColor):
    def __init__(self, dx, dy, damage, lifetime=BULLET_LIFETIME):
        super().__init__(6, 6, COLOR_BULLET)
        self.change_x = dx
        self.change_y = dy
        self.damage = damage
        self.lifetime = lifetime
        self.age = 0.0

    def update(self):
        super().update()

class Minion(arcade.SpriteSolidColor):
    def __init__(self, level):
        size = random.randint(22, 30)
        super().__init__(size, size, COLOR_MINION)
        side = random.choice(['top', 'bottom', 'left', 'right'])
        if side == 'top':
            self.center_x = random.randint(20, SCREEN_WIDTH - 20)
            self.center_y = SCREEN_HEIGHT + random.randint(10, 80)
        elif side == 'bottom':
            self.center_x = random.randint(20, SCREEN_WIDTH - 20)
            self.center_y = -random.randint(10, 80)
        elif side == 'left':
            self.center_x = -random.randint(10, 80)
            self.center_y = random.randint(20, SCREEN_HEIGHT - 20)
        else:
            self.center_x = SCREEN_WIDTH + random.randint(10, 80)
            self.center_y = random.randint(20, SCREEN_HEIGHT - 20)

        self.speed = MINION_BASE_SPEED + 0.3 * level + random.random() * 0.7
        self.max_health = MINION_BASE_HEALTH + 4 * level + random.randint(-2, 3)
        self.health = self.max_health
        self.damage = 12 + level * 2
        self.angry = False

    def become_angry(self):
        if not self.angry:
            self.angry = True
            self.color = COLOR_MINION_ANGRY
            self.speed *= 1.5

class Boss(arcade.SpriteSolidColor):
    def __init__(self):
        size = 110
        super().__init__(size, size, COLOR_BOSS)  # Solid color boss, like minions
        self.center_x = SCREEN_WIDTH // 2
        self.center_y = SCREEN_HEIGHT + 120
        self.max_health = BOSS_HEALTH
        self.health = self.max_health
        self.speed = BOSS_SPEED
        self.phase_timer = 0.0
        self.shoot_timer = 0.0



# --------------------- POWERUPS ---------------------
class PowerUp(arcade.SpriteSolidColor):
    TYPE_HEAL = "heal"
    TYPE_RAPID = "rapid"
    TYPE_DOUBLE = "double"

    def __init__(self, x, y, ptype):
        super().__init__(POWERUP_SIZE, POWERUP_SIZE, arcade.color.WHITE)
        self.center_x = x
        self.center_y = y
        self.ptype = ptype
        if ptype == self.TYPE_HEAL:
            self.color = arcade.color.FOREST_GREEN
        elif ptype == self.TYPE_RAPID:
            self.color = arcade.color.DARK_GREEN
        elif ptype == self.TYPE_DOUBLE:
            self.color = arcade.color.DARK_ORANGE

# --------------------- MAIN WINDOW ---------------------
class MinionEscapePlus(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
        arcade.set_background_color(COLOR_BG)

        self.player_list = None
        self.bullet_list = None
        self.minion_list = None
        self.powerup_list = None
        self.enemy_bullets = None

        self.player = None

        self.keys = {arcade.key.W: False, arcade.key.A: False, arcade.key.S: False, arcade.key.D: False}

        self.state = GameState.MENU
        self.level = 1
        self.score = 0
        self.level_transition_timer = 0.0
        self.total_time = 0.0
        self.font_size = 18
        self.mouse_x = 0
        self.mouse_y = 0
        self.boss = None

    def setup(self):
        self.player_list = arcade.SpriteList()
        self.bullet_list = arcade.SpriteList()
        self.minion_list = arcade.SpriteList()
        self.powerup_list = arcade.SpriteList()
        self.enemy_bullets = arcade.SpriteList()

        self.player = Player()
        self.player_list.append(self.player)

        self.state = GameState.MENU
        self.level = 1
        self.score = 0
        self.total_time = 0.0
        self.boss = None

    def start_level(self, level):
        self.level = level
        self.bullet_list = arcade.SpriteList()
        self.minion_list = arcade.SpriteList()
        self.powerup_list = arcade.SpriteList()
        self.enemy_bullets = arcade.SpriteList()

        self.player.center_x = SCREEN_WIDTH // 2
        self.player.center_y = SCREEN_HEIGHT // 2
        self.player.fire_timer = 0.0
        self.player.update_powerups(9999)

        if level < 3:
            count = MINION_BASE_COUNT + level * 2
            for _ in range(count):
                m = Minion(level)
                self.minion_list.append(m)
        else:
            count = MINION_BASE_COUNT + 2 * level
            for _ in range(count):
                m = Minion(level)
                self.minion_list.append(m)
            self.boss = Boss()

        self.state = GameState.PLAYING

    def new_game(self):
        self.score = 0
        self.level = 1
        self.player.health = PLAYER_MAX_HEALTH
        self.player.double_damage = False
        self.player.rapid_fire = False
        self.start_level(1)

    # --------------------- DRAW ---------------------
    def on_draw(self):
        self.clear()

        if self.state == GameState.MENU:
            arcade.draw_text("MINION ESCAPE: UPGRADE EDITION", SCREEN_WIDTH / 2, SCREEN_HEIGHT - 120,
                             COLOR_TEXT, 30, anchor_x="center", bold=True)
            arcade.draw_text("WASD to move, Click to shoot", SCREEN_WIDTH / 2, SCREEN_HEIGHT - 170,
                             COLOR_TEXT, 18, anchor_x="center")
            arcade.draw_text("Press ENTER to Start", SCREEN_WIDTH / 2, SCREEN_HEIGHT - 240, COLOR_TEXT, 22, anchor_x="center")
            arcade.draw_text("Press I for Instructions", SCREEN_WIDTH / 2, SCREEN_HEIGHT - 280, COLOR_TEXT, 14, anchor_x="center")
            arcade.draw_text("Levels: 3 | Boss fight on level 3 | Health & Powerups", SCREEN_WIDTH / 2, 90, COLOR_TEXT, 14, anchor_x="center")

        elif self.state == GameState.INSTRUCTIONS:
            arcade.draw_text("INSTRUCTIONS", SCREEN_WIDTH/2, SCREEN_HEIGHT - 80, COLOR_TEXT, 24, anchor_x="center")
            arcade.draw_text("Move: W A S D\nShoot: Left Mouse Click\nPickups: Green=Heal, DarkGreen=Rapid Fire, Orange=Double Damage\nSurvive and clear minions to progress.\nLevel 3 contains a boss.", 60, SCREEN_HEIGHT - 150, COLOR_TEXT, 16)
            arcade.draw_text("Press ESC to go back to menu", SCREEN_WIDTH / 2, 60, COLOR_TEXT, 14, anchor_x="center")

        elif self.state in (GameState.PLAYING, GameState.LEVEL_TRANSITION):
            self.player_list.draw()
            self.minion_list.draw()
            if self.boss:
                self.boss.draw()
            self.bullet_list.draw()
            self.enemy_bullets.draw()
            self.powerup_list.draw()

            self._draw_health_bar(self.player, 40, 8, PLAYER_MAX_HEALTH, self.player.health, label="You")

            for m in self.minion_list:
                self._draw_health_bar(m, 28, 5, m.max_health, m.health)

            if self.boss:
                bar_w = SCREEN_WIDTH - 120
                x = 60
                y = SCREEN_HEIGHT - 30
                width = bar_w
                height = 32
                left = x
                right = x + width
                bottom = y - height/2
                top = y + height/2
                arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, COLOR_HEALTH_BAR_BG)
                health_frac = max(0, self.boss.health) / self.boss.max_health
                health_width = width * health_frac
                arcade.draw_lrbt_rectangle_filled(left, left + health_width, bottom, top, COLOR_HEALTH_BAR)
                arcade.draw_text(f"Boss Health: {int(self.boss.health)}", SCREEN_WIDTH/2, y - 6, COLOR_TEXT, 14, anchor_x="center")

            arcade.draw_text(f"Score: {self.score}", 10, SCREEN_HEIGHT - 26, COLOR_TEXT, 16)
            arcade.draw_text(f"Level: {self.level}", 10, SCREEN_HEIGHT - 50, COLOR_TEXT, 14)
            arcade.draw_text(f"Health: {int(self.player.health)}", 150, SCREEN_HEIGHT - 26, COLOR_TEXT, 14)

            if self.state == GameState.LEVEL_TRANSITION:
                arcade.draw_text(f"Level {self.level - 1} Cleared!", SCREEN_WIDTH/2, SCREEN_HEIGHT/2 + 20, COLOR_TEXT, 28, anchor_x="center")
                arcade.draw_text("Prepare for the next wave...", SCREEN_WIDTH/2, SCREEN_HEIGHT/2 - 20, COLOR_TEXT, 16, anchor_x="center")

        elif self.state == GameState.GAME_OVER:
            arcade.draw_text("GAME OVER", SCREEN_WIDTH/2, SCREEN_HEIGHT/2 + 40, COLOR_TEXT, 36, anchor_x="center", bold=True)
            arcade.draw_text(f"Score: {self.score}", SCREEN_WIDTH/2, SCREEN_HEIGHT/2 - 10, COLOR_TEXT, 20, anchor_x="center")
            arcade.draw_text("Press R to Restart or ESC to Menu", SCREEN_WIDTH/2, SCREEN_HEIGHT/2 - 60, COLOR_TEXT, 16, anchor_x="center")

        elif self.state == GameState.VICTORY:
            arcade.draw_text("VICTORY!", SCREEN_WIDTH/2, SCREEN_HEIGHT/2 + 40, COLOR_TEXT, 36, anchor_x="center", bold=True)
            arcade.draw_text(f"You defeated the boss! Score: {self.score}", SCREEN_WIDTH/2, SCREEN_HEIGHT/2 - 10, COLOR_TEXT, 20, anchor_x="center")
            arcade.draw_text("Press R to Play Again or ESC to Menu", SCREEN_WIDTH/2, SCREEN_HEIGHT/2 - 60, COLOR_TEXT, 16, anchor_x="center")

    def _draw_health_bar(self, sprite, width, height, max_hp, cur_hp, label=None):
        x = sprite.center_x
        y = sprite.center_y + sprite.height // 2 + 6
        # Use lrbt for filled rectangles
        left = x - width / 2
        right = x + width / 2
        bottom = y - height / 2
        top = y + height / 2
        arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, COLOR_HEALTH_BAR_BG)
        frac = max(0, cur_hp) / max_hp if max_hp > 0 else 0
        arcade.draw_lrbt_rectangle_filled(left, left + width * frac, bottom, top, COLOR_HEALTH_BAR)
        if label:
            arcade.draw_text(f"{label}: {int(cur_hp)}", x, y + 10, COLOR_TEXT, 10, anchor_x="center")

    # --------------------- INPUT ---------------------
    def on_key_press(self, key, modifiers):
        if self.state == GameState.MENU:
            if key == arcade.key.ENTER:
                self.new_game()
            elif key == arcade.key.I:
                self.state = GameState.INSTRUCTIONS
        elif self.state == GameState.INSTRUCTIONS:
            if key == arcade.key.ESCAPE:
                self.state = GameState.MENU
        elif self.state in (GameState.PLAYING, GameState.LEVEL_TRANSITION):
            if key in self.keys:
                self.keys[key] = True
            if key == arcade.key.ESCAPE:
                self.state = GameState.MENU
        elif self.state in (GameState.GAME_OVER, GameState.VICTORY):
            if key == arcade.key.R:
                self.new_game()
            elif key == arcade.key.ESCAPE:
                self.state = GameState.MENU

    def on_key_release(self, key, modifiers):
        if key in self.keys:
            self.keys[key] = False

    def on_mouse_motion(self, x, y, dx, dy):
        self.mouse_x = x
        self.mouse_y = y

    def on_mouse_press(self, x, y, button, modifiers):
        if self.state == GameState.MENU:
            self.new_game()
            return
        if self.state != GameState.PLAYING:
            return
        if button == arcade.MOUSE_BUTTON_LEFT:
            self.try_shoot(x, y)

    def try_shoot(self, x, y):
        now_cd = self.player.fire_timer
        if now_cd <= 0:
            dx = x - self.player.center_x
            dy = y - self.player.center_y
            distance_norm = math.hypot(dx, dy)
            if distance_norm == 0:
                return
            vx = dx / distance_norm * BULLET_SPEED
            vy = dy / distance_norm * BULLET_SPEED
            damage = 12
            if self.player.double_damage:
                damage *= 2
            b = Bullet(vx, vy, damage)
            b.center_x = self.player.center_x
            b.center_y = self.player.center_y
            self.bullet_list.append(b)
            self.player.fire_timer = self.player.fire_cooldown

    # --------------------- UPDATE ---------------------
    def on_update(self, delta_time):
        if self.state == GameState.PLAYING:
            self._update_playing(delta_time)
        elif self.state == GameState.LEVEL_TRANSITION:
            self.level_transition_timer -= delta_time
            if self.level_transition_timer <= 0:
                if self.level <= 3:
                    self.start_level(self.level)
                else:
                    self.state = GameState.VICTORY

    def _update_playing(self, delta_time):
        self.total_time += delta_time
        if self.player.fire_timer > 0:
            self.player.fire_timer -= delta_time
        self.player.update_powerups(delta_time)

        dx = dy = 0
        if self.keys[arcade.key.W]:
            dy += self.player.speed
        if self.keys[arcade.key.S]:
            dy -= self.player.speed
        if self.keys[arcade.key.A]:
            dx -= self.player.speed
        if self.keys[arcade.key.D]:
            dx += self.player.speed
        self.player.center_x = max(10, min(SCREEN_WIDTH - 10, self.player.center_x + dx))
        self.player.center_y = max(10, min(SCREEN_HEIGHT - 10, self.player.center_y + dy))

        self.player.fire_cooldown = max(0.07, PLAYER_FIRE_COOLDOWN * 0.3) if self.player.rapid_fire else PLAYER_FIRE_COOLDOWN

        for bullet in list(self.bullet_list):
            bullet.age += delta_time
            if bullet.age > bullet.lifetime:
                bullet.remove_from_sprite_lists()
            else:
                bullet.update()

        for eb in list(self.enemy_bullets):
            eb.age += delta_time
            if eb.age > eb.lifetime:
                eb.remove_from_sprite_lists()
            else:
                eb.update()

        for m in list(self.minion_list):
            target = min(self.powerup_list, key=lambda p: dist(m.center_x, m.center_y, p.center_x, p.center_y)) if self.powerup_list else self.player
            dx = target.center_x - m.center_x
            dy = target.center_y - m.center_y
            d = math.hypot(dx, dy) + 1e-6
            m.center_x += (dx / d) * m.speed
            m.center_y += (dy / d) * m.speed

            if arcade.check_for_collision(m, self.player):
                self.player.health -= m.damage * 0.4
                angle = math.atan2(m.center_y - self.player.center_y, m.center_x - self.player.center_x)
                m.center_x += math.cos(angle) * 20
                m.center_y += math.sin(angle) * 20
                if random.random() < 0.6:
                    m.become_angry()

        if self.boss:
            if self.boss.center_y > SCREEN_HEIGHT - 160:
                self.boss.center_y -= self.boss.speed * 1.5
            else:
                self.boss.phase_timer += delta_time
                self.boss.shoot_timer += delta_time
                self.boss.center_x += math.sin(self.total_time * 0.9) * 0.9
                if self.boss.shoot_timer > 1.2:
                    self.boss.shoot_timer = 0
                    num = 8
                    for i in range(num):
                        angle = i * (2 * math.pi / num) + random.uniform(-0.2, 0.2)
                        vx = math.cos(angle) * 3.5
                        vy = math.sin(angle) * 3.5
                        eb = Bullet(vx, vy, damage=8, lifetime=6.0)
                        eb.center_x = self.boss.center_x
                        eb.center_y = self.boss.center_y
                        self.enemy_bullets.append(eb)

        for b in list(self.bullet_list):
            hit_minions = arcade.check_for_collision_with_list(b, self.minion_list)
            if self.boss and arcade.check_for_collision(b, self.boss):
                self.boss.health -= b.damage
                b.remove_from_sprite_lists()
                self.score += 8
                continue
            if hit_minions:
                for m in hit_minions:
                    m.health -= b.damage
                    if random.random() < 0.4:
                        m.become_angry()
                    if m.health <= 0:
                        self.score += 10
                        if random.random() < 0.28:
                            ptype = random.choice([PowerUp.TYPE_HEAL, PowerUp.TYPE_RAPID, PowerUp.TYPE_DOUBLE])
                            pu = PowerUp(m.center_x, m.center_y, ptype)
                            self.powerup_list.append(pu)
                        m.remove_from_sprite_lists()
                    b.remove_from_sprite_lists()
                    break

        for eb in list(self.enemy_bullets):
            if arcade.check_for_collision(eb, self.player):
                self.player.health -= eb.damage
                eb.remove_from_sprite_lists()

        hits = arcade.check_for_collision_with_list(self.player, self.powerup_list)
        for pu in hits:
            if pu.ptype == PowerUp.TYPE_HEAL:
                self.player.health = min(self.player.max_health, self.player.health + 28)
            elif pu.ptype == PowerUp.TYPE_RAPID:
                self.player.rapid_fire = True
                self.player.rapid_fire_timer = POWERUP_DURATION
            elif pu.ptype == PowerUp.TYPE_DOUBLE:
                self.player.double_damage = True
                self.player.double_damage_timer = POWERUP_DURATION
            pu.remove_from_sprite_lists()

        if self.boss and self.boss.health <= 0:
            self.boss = None
            self.minion_list = arcade.SpriteList()
            self.enemy_bullets = arcade.SpriteList()
            self.score += 150
            self.state = GameState.VICTORY
            return

        for m in list(self.minion_list):
            if m.health <= 0:
                m.remove_from_sprite_lists()
                self.score += 10
                if random.random() < 0.25:
                    ptype = random.choice([PowerUp.TYPE_HEAL, PowerUp.TYPE_RAPID, PowerUp.TYPE_DOUBLE])
                    pu = PowerUp(m.center_x, m.center_y, ptype)
                    self.powerup_list.append(pu)

        if len(self.minion_list) == 0 and (not self.boss):
            if self.level < 3:
                self.level += 1
                self.state = GameState.LEVEL_TRANSITION
                self.level_transition_timer = 2.0
            else:
                self.state = GameState.VICTORY

        if self.player.health <= 0:
            self.state = GameState.GAME_OVER

        for p in self.powerup_list:
            p.center_y += math.sin(self.total_time * 2 + p.center_x) * 0.3

# --------------------- RUN ---------------------
def main():
    window = MinionEscapePlus()
    window.setup()
    arcade.run()

if __name__ == "__main__":
    main()
